全文索引第四轮：DAAT、批量投影、索引构建投影联合优化

按用户要求联合实现、整体评测，不做单项消融。
对照为上一版 244c100deb8680f6047fb66ec3d510fc8ac9aeee 对应服务器二进制。

修改
1. ObTextDaaTIter：1～3个词项的自然语言查询维护各倒排列表的当前项，直接选取最小文档ID。
   省去逐文档的通用队列push/rebuild/top/pop；相同ID按词项下标升序累加，保持原浮点运算顺序。
   保留分数收集、过滤、OFFSET/LIMIT处理；布尔模式和更多词项走原有合并路径。
   reuse/reset清空专用路径的活动状态，保留原有扫描和事务可见性语义。
2. ObSRDaaTIterImpl：批量结果一次准备ID与分数的输出缓冲区，在一次循环中投影，再批量设置求值标记。
   标量表达式和非向量执行保留旧路径。保留倒排ID的必要独立副本，防止被后续扫描覆盖。
3. ObTableScanOp：全文索引构建时在inner_open绑定四个输出表达式，逐文档分词和逐词投影复用绑定。
   使用原列查找函数完成初始校验；普通扫描路径不使用该缓存。

验证（均已完成，用户随后要求停止追加评测并推送）
- 服务器编译成功。
- 1196个TOKENIZE用例及240组完整MATCH/LIMIT结果与上一版一致。
- 扩充至216组查询，覆盖1/2/3/4词项、重复词、无命中、布尔模式、长查询、批次/分区边界、DML及重建。
  包括完整ID、原始分数和排序LIMIT/OFFSET的差分；两条参考版已有4016错误（生成SQL第450、918行）保持一致。
  这两条属于已知基线问题，并非成功查询；没有新增差分错误。
- 8个并发IK/BENG表生命周期测试通过。
- 共享投影补充48条稀疏向量查询和4条普通扫描查询，前后输出一致。

三轮完整官方参数的同机对照（各指标取三次均值）
指标                      before       after       耗时下降
build_ik_all_sec           4.31833      4.19033      2.964%
build_ik_content_sec       3.30733      3.23133      2.298%
build_beng_en_sec          1.73067      1.72667      0.231%
tokenize_ik_avg_ms         0.10270      0.09897      3.635%
tokenize_beng_avg_ms       0.06447      0.05813      9.824%
query_cn_avg_ms            1.83413      1.55763     15.075%
query_beng_avg_ms          2.69543      2.29447     14.876%
query_mixed_avg_ms         2.00723      1.73423     13.601%
query_limit_avg_ms         2.28760      2.30327     -0.685%

构建类1.831%，分词类6.730%，查询类10.717%，三类等权综合改善6.426%。
本轮未修改分词算法；其计时变化不应解释为独立分词优化效果。
这是同机上一版对照，不是固定CI基线得分，也不代表正式成绩提高6.426分。
前三项查询在三轮中均改善；LIMIT未改善。共享排序、外部归并、BM25公式、分词规则未改变。

配置与复现
ROWS=20000 BATCH=500 ROUNDS=3000 QUERY_ROUNDS=200 SAMPLES=3 WARMUP=30 SKIP_LOAD=0。
专用实例32851/32852，memory_budget=16G，datafile_size=2G/maxsize=3G，log_disk_size=2G。
每轮完整重建基准库，报告各用新文件；官方测试数据、SQL、计时、评分和基线文件未修改。
构建目录 /workspace/seekdb/file-sql-validation；测试输出 /workspace/seekdb/fts-round4。
复用已停止的 /workspace/seekdb/fts-round2/run；测试结束已退出专用实例，未改动2881主实例。
before SHA256 d518dc280d1488a78abceea05f65a1ade6fd3808ed0d6ee8fa5f889c4f26092e
after  SHA256 99e5d57c3b9fcd353192660eb0504585b689ae353f2fe82711383aed3c2a23a2
二进制在 /root/seekdb-fts-round4-binaries/。使用既有服务器构建目录，正式提交仍以统一CI为准。
本地源代码恢复了两行被Windows编码转换影响的原注释；与实测候选的可执行代码一致。
run.sh和shared-validation.sh保存本次流程，重新运行需准备源代码ZIP及参考二进制，并改用新的输出目录。
candidate-combined.patch保存内核改动；comparison.json及六份原始报告保存全部计分指标。
