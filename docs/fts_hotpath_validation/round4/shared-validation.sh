#!/bin/bash
set -euo pipefail
root=/workspace/seekdb/file-sql-validation
out=/workspace/seekdb/fts-round4
bins=/root/seekdb-fts-round4-binaries
test -d "$out" && test -d "$bins"
export MYSQL='mysql -h127.0.0.1 -P32851 -uroot -N -s -A --default-character-set=utf8mb4'
export MYSQL_VERBOSE='mysql -h127.0.0.1 -P32851 -uroot -A --default-character-set=utf8mb4'
if $MYSQL -e 'SELECT 1' >/dev/null 2>&1; then echo 'Dedicated port already in use'; exit 1; fi
pid=''
stop() { if [ -n "$pid" ]; then kill -TERM "$pid"; wait "$pid" || true; pid=''; fi; }
trap stop EXIT
start() {
 "$1" --nodaemon --base-dir /workspace/seekdb/fts-round2/run --port 32851 --parameter rpc_port=32852 --parameter memory_budget=16G --parameter datafile_size=2G --parameter datafile_maxsize=3G --parameter log_disk_size=2G --log-level WARN > "$out/console-$2.log" 2>&1 &
 pid=$!
 for i in $(seq 1 90); do
  if $MYSQL -e 'SELECT 1' >/dev/null 2>&1; then return; fi
  kill -0 "$pid" || return 1
  sleep 1
 done
 return 1
}
build() {
 cmake --build "$root/build_release" --target seekdb -j8 > "$out/$1-build.log" 2>&1
 cp "$root/build_release/src/observer/seekdb" "$bins/seekdb-$1"
}
bench() {
 test ! -e "$out/$1-report.txt"
 LABEL="$1" ROWS=20000 BATCH=500 ROUNDS=3000 QUERY_ROUNDS=200 SAMPLES=3 WARMUP=30 SKIP_LOAD=0 OUTPUT="$out/$1-report.txt" bash "$root/tools/benchmark/fts_large_bench.sh" > "$out/$1-bench.log" 2>&1
}
for version in before after; do
 start "$bins/seekdb-$version" "shared-$version"
 mode=--compare
 if [ "$version" = before ]; then mode=--record; fi
 python3 /workspace/seekdb/test_fts_shared_projection.py --port 32851 "$mode" "$out/shared-reference.json" > "$out/$version-shared.log"
 stop
done
echo SHARED_COMPLETE
