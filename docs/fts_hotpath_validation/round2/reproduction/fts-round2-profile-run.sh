#!/bin/bash
set -euo pipefail
out=/workspace/seekdb/fts-round2
root=/workspace/seekdb/file-sql-validation
"$root/build_release/src/observer/seekdb" --nodaemon --base-dir "$out/run" --port 32851 --parameter rpc_port=32852 --parameter memory_budget=16G --parameter datafile_size=2G --parameter datafile_maxsize=3G --parameter log_disk_size=2G --log-level WARN > "$out/profile-console.log" 2>&1 &
pid=$!
echo "$pid" > "$out/profile.pid"
for i in $(seq 1 60); do mysql -h127.0.0.1 -P32851 -uroot -Nse 'SELECT 1' >/dev/null 2>&1 && break; sleep 1; done
export MYSQL='mysql -h127.0.0.1 -P32851 -uroot -N -s -A --default-character-set=utf8mb4'
export MYSQL_VERBOSE='mysql -h127.0.0.1 -P32851 -uroot -A --default-character-set=utf8mb4'
LABEL=profile SKIP_LOAD=1 OUTPUT="$out/profile-report.txt" bash "$root/tools/benchmark/fts_large_bench.sh" > "$out/profile-bench.log" 2>&1
kill -TERM "$pid"
wait "$pid" || true
cp "$out/parser-helper.original.cpp" "$root/src/storage/fts/ob_fts_parser_helper.cpp"
echo PROFILE_COMPLETE
