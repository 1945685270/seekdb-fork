#!/usr/bin/env python3
"""Differential coverage for sparse-vector projection and ordinary scan/DDL."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def statements():
    sql = ["DROP DATABASE IF EXISTS fts_projection_regression",
           "CREATE DATABASE fts_projection_regression", "USE fts_projection_regression",
           "CREATE TABLE docs(id INT PRIMARY KEY, v SPARSEVECTOR, tag INT)"]
    for start in range(1, 514, 100):
        rows = ["(%d,'{1:%d,2:%d,3:%d}',%d)" % (i, i, 2*i, i % 7, i % 11)
                for i in range(start, min(start+100, 514))]
        sql.append("INSERT INTO docs VALUES " + ",".join(rows))
    sql += ["CREATE INDEX ordinary ON docs(tag)",
            "CREATE VECTOR INDEX sparse_idx ON docs(v) WITH (lib=vsag,type=sindi,distance=inner_product)"]
    for stage in range(2):
        if stage:
            sql += ["UPDATE docs SET v='{1:1024,2:2048,3:1}' WHERE id=10",
                    "DELETE FROM docs WHERE id=513"]
        for query in ("{1:1}", "{1:1,2:2}", "{1:1,2:2,3:3}", "{99:1}"):
            for predicate in ("1=1", "tag=3"):
                expr = "negative_inner_product(v,'%s')" % query
                for limit in (7, 257, 513):
                    sql += ["SELECT '%s_%s_%s_%s'" % (stage, query, predicate, limit),
                            "SELECT id,%s FROM docs WHERE %s ORDER BY %s APPROX LIMIT %d"
                            % (expr, predicate, expr, limit)]
        sql += ["SELECT id,tag FROM docs FORCE INDEX(ordinary) WHERE tag=3 ORDER BY id",
                "SELECT id FROM docs ORDER BY id DESC LIMIT 17 OFFSET 250"]
    return ";\n".join(sql) + ";\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, required=True)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--record", type=Path)
    g.add_argument("--compare", type=Path)
    args = p.parse_args()
    sql = statements()
    result = subprocess.run(["mysql", "-h127.0.0.1", "-P" + str(args.port), "-uroot",
                             "-N", "-B", "--raw", "--default-character-set=utf8mb4"],
                            input=sql, encoding="utf-8", capture_output=True, timeout=600)
    if result.returncode:
        raise SystemExit(result.stderr)
    data = {"sql_sha256": hashlib.sha256(sql.encode()).hexdigest(), "rows": result.stdout.splitlines()}
    if args.record:
        args.record.write_text(json.dumps(data), encoding="utf-8")
        print("Recorded 48 sparse-vector queries and 4 ordinary scan queries")
    else:
        if data != json.loads(args.compare.read_text(encoding="utf-8")):
            actual = args.compare.with_suffix(".actual.json")
            actual.write_text(json.dumps(data), encoding="utf-8")
            raise SystemExit("Shared projection mismatch: " + str(actual))
        print("PASS: 48 sparse-vector queries and 4 ordinary scan queries match baseline")


if __name__ == "__main__":
    main()
