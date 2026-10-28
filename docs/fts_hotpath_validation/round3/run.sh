#!/bin/bash
set -euo pipefail
root=/workspace/seekdb/file-sql-validation
out=/workspace/seekdb/fts-round3
bins=/root/seekdb-fts-round3-binaries
mkdir "$out" "$bins"
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
echo PREPARE
python3 - <<'PY'
from pathlib import Path
import zipfile, shutil
root=Path('/workspace/seekdb/file-sql-validation')
out=Path('/workspace/seekdb/fts-round3')
queries={'src/sql/das/iter/ob_das_text_retrieval_merge_iter.cpp','src/storage/retrieval/ob_sparse_taat_iter.cpp'}
with zipfile.ZipFile('/workspace/seekdb/fts-round3-source.zip') as z:
 for name in z.namelist():
  target=root/name
  if target.exists():
   backup=out/'original'/name; backup.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(target,backup)
  if name in queries:
   candidate=out/'candidate'/name; candidate.parent.mkdir(parents=True,exist_ok=True); candidate.write_bytes(z.read(name))
  else:
   target.write_bytes(z.read(name))
PY
echo BUILD_PROPERTIES_REFERENCE
build before
echo BUILD_QUERY_CANDIDATE
cp "$out/candidate/src/sql/das/iter/ob_das_text_retrieval_merge_iter.cpp" "$root/src/sql/das/iter/"
cp "$out/candidate/src/storage/retrieval/ob_sparse_taat_iter.cpp" "$root/src/storage/retrieval/"
build after
echo RECORD_OLD_BASELINE
start /workspace/seekdb/fts-round2/seekdb-before old
python3 "$root/unittest/sql/engine/basic/test_fts_hotpath.py" --port 32851 --record "$out/token-reference.json" > "$out/old-correctness.log"
python3 /workspace/seekdb/test_fts_query_merge.py --port 32851 --record "$out/merge-reference.json" > "$out/old-merge.log"
stop
for n in 1 2 3; do
 for version in before after; do
  echo "PHASE $version-$n"
  start "$bins/seekdb-$version" "$version-$n"
  if [ "$n" = 1 ]; then
   python3 "$root/unittest/sql/engine/basic/test_fts_hotpath.py" --port 32851 --compare "$out/token-reference.json" > "$out/$version-correctness.log"
   python3 /workspace/seekdb/test_fts_query_merge.py --port 32851 --compare "$out/merge-reference.json" > "$out/$version-merge.log"
   python3 "$root/unittest/sql/engine/basic/test_fts_ddl_progress.py" --port 32851 > "$out/$version-ddl.log"
  fi
  bench "$version-$n"
  stop
 done
done
echo COMPLETE
