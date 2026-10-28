全文索引第三轮：TAAT 合并优化与上一版参数复用验证

结论
本轮已完成两个版本的服务器编译、完整结果差分、三轮官方参数基准以及独立长查询辅助测试。
保留 TAAT 优化：长查询辅助测试平均 25.8910ms -> 16.4163ms，耗时下降 36.59%。
官方基准查询类仅改善 0.414%，LIMIT 项退化 1.048%；综合改善 0.617%，未证明稳定的竞赛提分。
辅助数据、SQL、计时脚本位于本目录，明确不用于官方评分。官方 benchmark、SQL、数据生成器和评分基线未修改。

瓶颈依据和改动
1. src/storage/retrieval/ob_sparse_taat_iter.cpp 与旧 DAS TAAT 实现：
   分区目标为每区约 1000 篇文档，但 hash_map->create(10) 经 cal_next_prime 只分配 53 个桶。
   将请求桶数改为已有 OB_HASHMAP_DEFAULT_SIZE=1000，实际分配 1543 个桶，降低冲突链查找开销。
   代价是增加每分区桶内存；分区最多 20 个。尚未独立量化峰值内存差异。
2. 已存在文档的相关性分数原先 get_refactored 后再 set_refactored，重复哈希与桶遍历。
   改为 set_or_update；回调保持 cur_relevance + old_relevance 的原运算顺序，不重排词项。
3. 一个分区时直接选择分区 0，保留文档 ID 非空检查，避免计算结果必为零的分区哈希与取模。
4. 当前稀疏检索实现和旧 DAS 实现同步修改；不改变分词、BM25 公式、必要处理和检索过滤。
本轮将三点作为一组评测，未做单点消融，因此不能把全部长查询收益归因于其中某一点。

对照版本
before：上一版 TOKENIZE 参数对象复用 + 原查询合并代码。
after ：相同参数复用 + 本轮查询合并改动。两个版本均撤回上一轮无收益的 DDL 状态推进。
参考正确性使用 /workspace/seekdb/fts-round2/seekdb-before。
before 二进制 SHA256：954c93c4f2d9fcd2d8ad95aa386c6ce6b44eb00a59bc57630824bc54e4dd69dc
after  二进制 SHA256：d518dc280d1488a78abceea05f65a1ade6fd3808ed0d6ee8fa5f889c4f26092e
二进制保存 /root/seekdb-fts-round3-binaries/，原始日志 /workspace/seekdb/fts-round3/。
服务器使用既有隔离构建目录，不是对 GitHub 提交进行全新干净构建；正式提交仍需统一 CI 验证。

正确性
两版本都与旧参考版匹配：1196 个 TOKENIZE 用例、240 组完整 MATCH/LIMIT 结果。
修正原测试中的非法 max_token_size=6 为合法边界值 10，原版本要求范围 [10,84]。
新增 test_fts_query_merge.py：IK/BENG，17/1001/4097 文档，批次/分区边界，重叠词项、重复查询词、无命中、
270 个不同词项加 alpha 的长查询，更新/删除/索引重建；比对 COUNT、完整 ID 和未四舍五入的分数、排序 LIMIT/OFFSET。
126 组共 378 条结果查询，两条查询在参考版已有 ERROR 4016：生成 SQL 第 282、570 行。
测试使用 mysql --force 继续执行后续查询，并将错误文本与行号一并作为差分结果，不能把这两条称为成功查询。
before/after 的成功输出和两条错误均与参考版完全一致，没有新增错误；该已知基线问题尚未修复。
两版本也通过 8 个并发 IK/BENG 表生命周期测试（空表、重复 DDL、重建与 DML）。
上一版参数复用因此已经通过本轮编译与上述差分，但本轮 before/after 都包含它，不能据此量化其独立性能收益。

官方参数基准（三次完整运行取每指标均值）
指标                       before       after        耗时下降
build_ik_all_sec            4.22267      4.12100       2.408%
build_ik_content_sec        3.33433      3.33433       0.000%
build_beng_en_sec           1.72967      1.73167      -0.116%
tokenize_ik_avg_ms          0.10303      0.10103       1.941%
tokenize_beng_avg_ms        0.06157      0.06193      -0.596%
query_cn_avg_ms             1.86407      1.84640       0.948%
query_beng_avg_ms           2.71647      2.68763       1.061%
query_mixed_avg_ms          2.01577      2.00177       0.695%
query_limit_avg_ms          2.28747      2.31143      -1.048%
三类均值：构建 0.764%、分词 0.673%、查询 0.414%，等权综合 0.617%。这是同机对照，不是固定 CI 基线成绩。
未修改的构建和分词也有波动，不能将这些波动认定为查询改动的收益。
六份报告命中数均为中文8001、英文11000、混合7332、LIMIT20；正确性主要依据上述完整差分。
参数：ROWS=20000 BATCH=500 ROUNDS=3000 QUERY_ROUNDS=200 SAMPLES=3 WARMUP=30 SKIP_LOAD=0。
专用端口32851/32852，memory_budget=16G，datafile_size=2G/maxsize=3G，log_disk_size=2G。
复用已停止的 /workspace/seekdb/fts-round2/run 数据目录；每轮完整重建基准库。主实例2881未改动。

辅助长查询实验
taat_probe.py / taat-probe.sh：独立 fts_taat_probe 库，5000文档，每篇16个词项，270个查询词项。
每版本启动3次，每次预热5次、3组每组30次查询，共9个样本；每次校验命中数5000。
所有 after 样本低于所有 before 样本。结果见 taat-comparison.json 和6份原始 taat-*.json。
仅证明该辅助长查询场景受益，不能外推为官方9项指标或总分提升36.59%。

复现与后续
run.sh 是本次完整流程；resume-validation.sh 用于首次参考测试参数修正后的续跑。
运行前必须准备独立构建目录、源代码 ZIP、参考二进制和对应测试文件；按自己的路径调整，使用新的输出目录。
本次 run.sh 初始运行的失败与后续恢复均保留在 progress.log；报告文件使用新名字，不追加重复样本。
candidate-query.patch 保存内核改动；comparison.json 保存官方参数同机对照，sha256.json 校验归档文件。
目前没有证据支持修改共享排序或外部归并，故本轮未动这些公共路径。后续应对官方短查询的 DAAT 执行链路做分阶段计时。
