#!/bin/bash
set -euo pipefail
root=/workspace/seekdb/file-sql-validation
out=/workspace/seekdb/fts-round2
export MYSQL='mysql -h127.0.0.1 -P32851 -uroot -N -s -A --default-character-set=utf8mb4'
export MYSQL_VERBOSE='mysql -h127.0.0.1 -P32851 -uroot -A --default-character-set=utf8mb4'
python3 "$root/unittest/sql/engine/basic/test_fts_hotpath.py" --port 32851 --record "$out/reference.json" > "$out/before-correctness.log"
LABEL=round2-before OUTPUT="$out/before-report.txt" bash "$root/tools/benchmark/fts_large_bench.sh" > "$out/before-bench.log" 2>&1
$MYSQL -e "EXPLAIN SELECT COUNT(*) FROM fts_large_bench.docs WHERE MATCH(content) AGAINST('倒排索引 tokenizer');" > "$out/query-plan.txt"
$MYSQL -e "SELECT query_sql,elapsed_time,execute_time,total_wait_time_micro FROM oceanbase.GV\$OB_SQL_AUDIT ORDER BY request_time DESC LIMIT 15;" > "$out/audit.txt"
