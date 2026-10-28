#!/usr/bin/env python3
"""Supplemental TAAT diagnostic, never used as an official benchmark score."""
import hashlib
import json
import subprocess
import sys
import time

client = ['mysql', '-h127.0.0.1', '-P32851', '-uroot', '-N', '-B', '--raw', '--default-character-set=utf8mb4']
terms = ['term' + chr(97 + i // 26) + chr(97 + i % 26) for i in range(270)]
def run(sql):
    p = subprocess.run(client, input=sql, text=True, capture_output=True, check=True)
    return p.stdout

if '--setup' in sys.argv:
    sql = ['DROP DATABASE IF EXISTS fts_taat_probe', 'CREATE DATABASE fts_taat_probe',
           'USE fts_taat_probe', 'CREATE TABLE docs(id INT PRIMARY KEY, body TEXT) CHARSET=utf8mb4']
    for start in range(1, 5001, 500):
        values = ["(%d,'%s')" % (i, ' '.join(terms[(i + j) % 270] for j in range(16)))
                  for i in range(start, start + 500)]
        sql.append('INSERT INTO docs VALUES ' + ','.join(values))
    sql.append('ALTER TABLE docs ADD FULLTEXT INDEX ft(body) WITH PARSER beng')
    run(';\n'.join(sql) + ';')
query = "SELECT COUNT(*) FROM fts_taat_probe.docs WHERE MATCH(body) AGAINST('%s');\n" % ' '.join(terms)
run(query * 5)
results = []
for sample in range(3):
    start = time.perf_counter()
    output = run(query * 30)
    elapsed = time.perf_counter() - start
    if output.splitlines() != ['5000'] * 30:
        raise SystemExit('Unexpected result: ' + output[:300])
    results.append(elapsed * 1000 / 30)
print(json.dumps({'diagnostic_only': True, 'rows': 5000, 'terms': 270,
                  'sample_ms': results, 'sql_sha256': hashlib.sha256(query.encode()).hexdigest()}))
