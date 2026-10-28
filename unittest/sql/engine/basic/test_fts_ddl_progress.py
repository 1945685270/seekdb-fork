#!/usr/bin/env python3
"""Concurrent FTS DDL regression; recreates only fts_ddl_progress on a test instance."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, required=True)
    args = p.parse_args()
    command = ["mysql", "-h127.0.0.1", "-P" + str(args.port), "-uroot", "-N", "-B",
               "--default-character-set=utf8mb4"]

    def sql(statement, fail=False):
        result = subprocess.run(command, input="SET ob_query_timeout=120000000;" + statement,
                                text=True, encoding="utf-8", capture_output=True, timeout=150)
        if fail:
            assert result.returncode != 0, "Expected duplicate index error"
            assert "1061" in result.stderr, result.stderr
        elif result.returncode:
            raise AssertionError(result.stderr)
        return result.stdout.strip()

    sql("DROP DATABASE IF EXISTS fts_ddl_progress; CREATE DATABASE fts_ddl_progress;")

    def build(number):
        table = "fts_ddl_progress.t%d" % number
        parser = "ik" if number % 2 == 0 else "beng"
        sql("CREATE TABLE %s(id INT PRIMARY KEY, title VARCHAR(100), body TEXT)" % table)
        # Build on an empty table, then verify DML maintenance.
        sql("ALTER TABLE %s ADD FULLTEXT INDEX ft(title,body) WITH PARSER %s" % (table, parser))
        sql("INSERT INTO %s VALUES(1,'alpha','database 数据库'),(2,'beta','gamma')" % table)
        check = "SELECT id FROM %s WHERE MATCH(title,body) AGAINST('alpha') ORDER BY id" % table
        assert sql(check) == "1"
        sql("ALTER TABLE %s ADD FULLTEXT INDEX ft(title,body) WITH PARSER %s" % (table, parser), fail=True)
        # A rejected DDL must not invalidate the existing index or block rebuild.
        assert sql(check) == "1"
        sql("ALTER TABLE %s DROP INDEX ft; ALTER TABLE %s ADD FULLTEXT INDEX ft(title,body) WITH PARSER %s" % (table, table, parser))
        assert sql(check) == "1"
        sql("UPDATE %s SET title='alpha' WHERE id=2; DELETE FROM %s WHERE id=1" % (table, table))
        assert sql(check) == "2"
        sql("DROP TABLE %s" % table)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(build, range(8)))
    print("PASS: 8 concurrent table lifecycles, IK/BENG, empty/nonempty builds, duplicate DDL, rebuild and DML")


if __name__ == "__main__":
    main()
