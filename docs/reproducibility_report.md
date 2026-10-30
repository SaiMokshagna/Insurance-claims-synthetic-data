# Reproducibility report

Command: `python -m generator --seed 20261022 --policies 2000 --claims 1000`

Environment: Python 3.11.9, pandas 3.1.0, numpy 2.4.6.

The generator was run twice with the same seed, each time in a separate process. A third run with a different seed is a control.

## Result

- Run 1 vs run 2: **36 of 36 files identical**, row counts identical: **True**.
- Control (seed 20261023): 32 of 36 files differ, so the comparison does detect changes.

## Row counts

| Table | Run 1 | Run 2 |
|---|---|---|
| customers | 1200 | 1200 |
| coverages | 6 | 6 |
| adjusters | 40 | 40 |
| policies | 2000 | 2000 |
| policy_coverages | 3308 | 3308 |
| incidents | 985 | 985 |
| claims | 1000 | 1000 |
| claim_items | 2510 | 2510 |
| documents | 3239 | 3239 |
| claim_assignments | 1601 | 1601 |
| assessments | 973 | 973 |
| reserves | 1758 | 1758 |
| settlements | 975 | 975 |
| status_events | 16718 | 16718 |
| ground_truth | 1000 | 1000 |

## Checksums (first 16 characters of SHA-256; the manifest has the full values)

| File | Run 1 | Run 2 | Match |
|---|---|---|---|
| README.md | 133b7b58d99dceb1 | 133b7b58d99dceb1 | yes |
| csv/adjusters.csv | 27fb31d001a81247 | 27fb31d001a81247 | yes |
| csv/assessments.csv | 64a9d2ab65d87498 | 64a9d2ab65d87498 | yes |
| csv/claim_assignments.csv | eb811c327afa613a | eb811c327afa613a | yes |
| csv/claim_items.csv | a677f4d2ce3967b0 | a677f4d2ce3967b0 | yes |
| csv/claims.csv | 05fba3e64d62da88 | 05fba3e64d62da88 | yes |
| csv/coverages.csv | 54d07ca04f422da7 | 54d07ca04f422da7 | yes |
| csv/customers.csv | a547e409edd27710 | a547e409edd27710 | yes |
| csv/documents.csv | e68206468d0b2233 | e68206468d0b2233 | yes |
| csv/incidents.csv | a3de050c1470b1a0 | a3de050c1470b1a0 | yes |
| csv/policies.csv | a2f7fae10677ae71 | a2f7fae10677ae71 | yes |
| csv/policy_coverages.csv | 209cf5e61685a2e4 | 209cf5e61685a2e4 | yes |
| csv/reserves.csv | 1510b23016801ea8 | 1510b23016801ea8 | yes |
| csv/settlements.csv | 6ce2e137cbd8e6b1 | 6ce2e137cbd8e6b1 | yes |
| csv/status_events.csv | 30cc76104382fe9a | 30cc76104382fe9a | yes |
| data_dictionary.md | 6c3df3360a53f684 | 6c3df3360a53f684 | yes |
| ground_truth/ground_truth.csv | c7bc6299bfdf327d | c7bc6299bfdf327d | yes |
| ground_truth/ground_truth.json | 2fa58db9a58d5e5f | 2fa58db9a58d5e5f | yes |
| json/adjusters.json | 18d0b8dc926bd55e | 18d0b8dc926bd55e | yes |
| json/assessments.json | 90df7a2ab262425a | 90df7a2ab262425a | yes |
| json/claim_assignments.json | 7fd5a1a931ca14a0 | 7fd5a1a931ca14a0 | yes |
| json/claim_items.json | 96613a9267f345ad | 96613a9267f345ad | yes |
| json/claims.json | 256ee75a92f630c3 | 256ee75a92f630c3 | yes |
| json/coverages.json | c634661b79eddb3f | c634661b79eddb3f | yes |
| json/customers.json | 13d1778ba424c99f | 13d1778ba424c99f | yes |
| json/documents.json | bde27b904054a602 | bde27b904054a602 | yes |
| json/incidents.json | 7e09200269ff0520 | 7e09200269ff0520 | yes |
| json/policies.json | 017cecd6f887a547 | 017cecd6f887a547 | yes |
| json/policy_coverages.json | 8d4aa592177f86dc | 8d4aa592177f86dc | yes |
| json/reserves.json | e3d2b90b99780c79 | e3d2b90b99780c79 | yes |
| json/settlements.json | f6668c6dd17e16bb | f6668c6dd17e16bb | yes |
| json/status_events.json | 1a8d328609dcbf0d | 1a8d328609dcbf0d | yes |
| reports/validation_results.csv | 8d3d3039f9a30bc0 | 8d3d3039f9a30bc0 | yes |
| reports/validation_summary.md | d1f3a0b06cfa4cff | d1f3a0b06cfa4cff | yes |
| sql/schema.sql | 161af05b47772ecc | 161af05b47772ecc | yes |
| sql/seed.sql | bbe8726cf9beeb3b | bbe8726cf9beeb3b | yes |
