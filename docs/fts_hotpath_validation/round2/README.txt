全文索引第二轮优化实验记录（2026-10-28）

状态：未取得可确认的稳定性能收益。三组已评测内核候选均已从工作区撤回；保留实验补丁和原始报告。
工作区当前为第四组“参数 JSON 对象复用”候选，尚未进行服务器编译和运行验证，不应视为可提交成果。

实验与结果（各组独立对照，均为完整官方参数，每个版本各三轮）：
1. 词典内存复用、英文缓冲区、单次哈希联合实验：综合提升 +0.583%。目标收益不稳定，已撤回。
2. 仅英文缓冲区：综合提升 +1.320%；目标 BENG 分词提升 -1.037%，不支持有效优化判断，已撤回。
3. 全文索引状态有界连续推进：综合提升 +0.594%；目标构建类提升 -0.840%，已撤回。

正确性：联合候选通过 488 个 token 用例和 240 组完整 MATCH/LIMIT 结果差分。
英文缓冲区候选首次回归发现 binary/8bit 字符集原地大小写转换契约不匹配；修复后通过 536 个 token 用例与 240 组完整查询差分。
状态机候选通过同样的 536/240 差分及 8 个表生命周期的并发 DDL 测试（IK/BENG、空表、重建、重复 DDL 错误、增删改）。
这些通过记录仅对应当时的候选；不能用来宣称第四组候选已经通过。

诊断：服务器无 perf/GDB；临时插桩测量 parser 初始化、get_next_token、总 segment 时间。插桩输出在 seekdb 自身日志，而非启动控制台。
profile-samples.txt 保存原始累计计时；混合分词器、包含冷启动与计时开销，不能当作无插桩性能成绩。profile-report.txt 仅用于诊断，重复追加且 SKIP_LOAD=1，不参与任何评分。
query-plan.txt 显示混合查询走 TEXT RETRIEVAL SCAN，计算 relevance，无索引回表。该版本没有 oceanbase.GV$OB_SQL_AUDIT 视图。
状态机默认调度空闲间隔为 10ms；实测不能证明连续推进能降低整体构建耗时。

第四组当前实现：TOKENIZE 保留校验与默认属性补全后的 ObFTParserJsonProps 对象，直接交给 ObFTParseHelper；避免格式化为 JSON 后立即再次解析。
原有接受 JSON 字符串的入口继续保留；抽取共用属性读取逻辑，保持原空字符串默认值处理。没有跨查询缓存，也未跳过参数校验。
回归脚本已扩充至 NGRAM/NGRAM2、默认输出、min/max token 自定义参数；完成本地 Python 语法、JSON 字面量、git diff --check 检查，未运行扩充后的全套用例。
下一步必须：上传本地修正后的 fts-round2-properties.zip，再编译，运行 properties 验证脚本；基准仍保持不变。

阻塞：服务器部署及编译命令的自动权限审批连续两次超时，工具确认命令未执行；并非风险拒绝。已向用户请求继续执行的明确授权。
服务器当前源码仍是第三组状态机候选；本地已撤回该候选。远端已上传的旧 properties ZIP 尚未解压，且不含最后的测试 JSON 修正，务必重新上传本地 ZIP。
前述测试专用实例已随脚本退出；未修改 2881 主服务。测试目录 /workspace/seekdb/fts-round2；构建目录 /workspace/seekdb/file-sql-validation。
测试配置 memory_budget=16G, datafile_size=2G, maxsize=3G, log_disk_size=2G；本轮前后相同。不能直接同上轮 4G 初始数据文件配置比较。
原始报告保留服务器时区时间戳，不等同于北京时间。测试参数 ROWS=20000 BATCH=500 ROUNDS=3000 QUERY_ROUNDS=200 SAMPLES=3 WARMUP=30 SKIP_LOAD=0。
官方基准及基线未修改；正式评分基线与本地不一致的问题仍未解决，不能预测正式得分。
文件：candidate-combined.patch / candidate-buffer.patch / candidate-ddl.patch 为已撤回实验；candidate-properties-unvalidated.patch 为当前未验证候选。reproduction/ 保存执行脚本。

保存说明：按用户要求将当前候选代码与实验报告保存到 GitHub 2026-competition 分支；此推送仅用于版本留存，不代表第四组候选已通过编译、正确性或性能验收。

