#!/bin/bash
set -euo pipefail
root=/workspace/seekdb/file-sql-validation
out=/workspace/seekdb/fts-round2
export MYSQL='mysql -h127.0.0.1 -P32851 -uroot -N -s -A --default-character-set=utf8mb4'
export MYSQL_VERBOSE='mysql -h127.0.0.1 -P32851 -uroot -A --default-character-set=utf8mb4'
start() {
 "$1" --nodaemon --base-dir "$out/run" --port 32851 --parameter rpc_port=32852 --parameter memory_budget=16G --parameter datafile_size=2G --parameter datafile_maxsize=3G --parameter log_disk_size=2G --log-level WARN > "$out/console-$2.log" 2>&1 &
 pid=$!
 for i in $(seq 1 90); do
  if $MYSQL -e 'SELECT 1' >/dev/null 2>&1; then return; fi
  kill -0 "$pid" || return 1
  sleep 1
 done
 return 1
}
stop() { kill -TERM "$pid"; wait "$pid" || true; }
bench() {
 test ! -e "$out/$1-report.txt"
 LABEL="$1" ROWS=20000 BATCH=500 ROUNDS=3000 QUERY_ROUNDS=200 SAMPLES=3 WARMUP=30 SKIP_LOAD=0 OUTPUT="$out/$1-report.txt" bash "$root/tools/benchmark/fts_large_bench.sh" > "$out/$1-bench.log" 2>&1
}
grep -q 'Built target seekdb' "$out/build.log"
start "$root/build_release/src/observer/seekdb" after
echo 'PHASE correctness'
python3 "$root/unittest/sql/engine/basic/test_fts_hotpath.py" --port 32851 --compare "$out/reference.json" | tee "$out/after-correctness.log"
echo 'PHASE after'
bench after
stop
for n in 2 3; do
 echo "PHASE before-$n"
 start "$out/seekdb-before" "before-$n"
 bench "before-$n"
 stop
 echo "PHASE after-$n"
 start "$root/build_release/src/observer/seekdb" "after-$n"
 bench "after-$n"
 stop
done
echo COMPLETE
