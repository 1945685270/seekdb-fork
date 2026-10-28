#!/usr/bin/env python3
"""Compare complete FTS merge results on a dedicated fts_merge_regression DB."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess


def statements():
    terms = ["term" + chr(97 + i // 26) + chr(97 + i % 26) for i in range(270)]
    sql = ["DROP DATABASE IF EXISTS fts_merge_regression",
           "CREATE DATABASE fts_merge_regression", "USE fts_merge_regression"]
    cases = 0
    # Cross batch and hash-partition boundaries; include heavily overlapping postings.
    for parser in ("beng", "ik"):
        for size in (17, 1001, 4097):
            sql.append("CREATE TABLE docs (id INT PRIMARY KEY, body TEXT) CHARSET=utf8mb4")
            for start in range(1, size + 1, 400):
                values = []
                for i in range(start, min(start + 400, size + 1)):
                    body = "alpha " * (1 + i % 4)
                    body += "beta 数据库 " if i % 2 else "gamma 全文索引 "
                    body += "delta " if i % 7 == 0 else ""
                    body += terms[i % len(terms)]
                    values.append("(%d,'%s')" % (i, body))
                sql.append("INSERT INTO docs VALUES " + ",".join(values))
            sql.append("ALTER TABLE docs ADD FULLTEXT INDEX ft(body) WITH PARSER " + parser)
            for stage in range(3):
                if stage == 1:
                    sql += ["UPDATE docs SET body='gamma delta' WHERE id % 11=0",
                            "DELETE FROM docs WHERE id % 13=0"]
                elif stage == 2:
                    sql += ["ALTER TABLE docs DROP INDEX ft",
                            "ALTER TABLE docs ADD FULLTEXT INDEX ft(body) WITH PARSER " + parser]
                for query in ("alpha", "alpha beta gamma", "alpha alpha beta",
                              "delta absent", "数据库 全文索引", "absent",
                              "alpha " + " ".join(terms)):
                    expr = "MATCH(body) AGAINST('%s')" % query
                    sql.append("SELECT 'case_%d'" % cases)
                    sql += ["SELECT COUNT(*) FROM docs WHERE " + expr,
                            "SELECT id,%s FROM docs WHERE %s ORDER BY id" % (expr, expr),
                            "SELECT id,%s FROM docs WHERE %s ORDER BY %s DESC,id LIMIT 7 OFFSET 3"
                            % (expr, expr, expr)]
                    cases += 1
            sql.append("DROP TABLE docs")
    return ";\n".join(sql) + ";\n", cases


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, required=True)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", type=Path)
    group.add_argument("--compare", type=Path)
    args = p.parse_args()
    sql, cases = statements()
    run = subprocess.run(["mysql", "-h127.0.0.1", "-P" + str(args.port), "-uroot",
                          "-N", "-B", "--raw", "--force", "--default-character-set=utf8mb4"],
                         input=sql, encoding="utf-8", capture_output=True, timeout=900)
    if run.returncode:
        raise SystemExit(run.stderr)
    # Keep baseline engine errors visible and compare them too. Do not stop before
    # later query groups, or silently accept a new candidate failure.
    errors = run.stderr.splitlines()
    if any(not re.match(r"ERROR 4016 \(HY000\) at line \d+: Internal error$", e) for e in errors):
        raise SystemExit("Unexpected SQL failure: " + run.stderr)
    result = {"sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
              "cases": cases, "rows": run.stdout.splitlines(), "errors": errors}
    if args.record:
        args.record.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print("Recorded %d query groups; baseline SQL errors: %d" % (cases, len(errors)))
    else:
        if result != json.loads(args.compare.read_text(encoding="utf-8")):
            actual = args.compare.with_suffix(".actual.json")
            actual.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            raise SystemExit("Merge regression mismatch: " + str(actual))
        print("PASS: %d query groups match baseline exactly; preserved baseline SQL errors: %d"
              % (cases, len(errors)))


if __name__ == "__main__":
    main()
