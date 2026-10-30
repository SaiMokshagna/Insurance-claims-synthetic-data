# Insurance claims synthetic dataset

Synthetic data for an insurance claims workflow (intake, coverage validation, document
requests, eligibility assessment, settlement routing). Generated with a fixed seed.

- Seed: 20261022
- Reference date ("today" for all derived values): 2026-10-22
- Size: 2000 policies, 1000 claims, 5 claim types
- Regenerate: `python -m generator --seed 20261022 --policies 2000 --claims 1000`

## Folders

| Path | Contents |
|---|---|
| `csv/`, `json/` | The input tables, one file per table |
| `sql/` | `schema.sql` (keys, foreign keys, indexes) and `seed.sql` |
| `ground_truth/` | Labels for known anomalies and expected decisions (1000 rows, one per claim) |
| `reports/` | `validation_summary.md` and `validation_results.csv` |
| `manifest.json` | Seed, command, environment, row counts and a SHA-256 checksum of every file |
| `data_dictionary.md` | Every field: type, allowed values, uniqueness, validation rule |

## Tables

| Table | Rows |
|---|---|
| customers | 1200 |
| coverages | 6 |
| adjusters | 40 |
| policies | 2000 |
| policy_coverages | 3308 |
| incidents | 985 |
| claims | 1000 |
| claim_items | 2510 |
| documents | 3239 |
| claim_assignments | 1601 |
| assessments | 973 |
| reserves | 1758 |
| settlements | 975 |
| status_events | 16718 |

## Ground truth

`ground_truth/` must never be used as an input feature. It is not part of the table
exports or the SQL seed. Expected decisions in it come from the documented rules.

## Provenance

No external data was used and no personal data was collected. Names come from short fictional
lists, email addresses use the reserved `example.com` domain, and all amounts are in USD.
