"""Exports: CSV, JSON, SQL seed, dataset README, manifest with SHA-256 checksums.

Ground truth is written to its OWN folder and is never part of the table exports
or the SQL seed.
"""
import hashlib
import json
import platform
import shutil
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from generator.config import (
    ANOMALY_PLAN_PER_1000, CUSTOMER_RATIO, GENERATOR_VERSION, REFERENCE_DATE,
)
from generator.report import write_report

OWNED_FOLDERS = ("csv", "json", "sql", "ground_truth", "reports")   # wiped and rebuilt on every export
TABLE_ORDER = [
    "customers", "coverages", "adjusters", "policies", "policy_coverages", "incidents",
    "claims", "claim_items", "documents", "claim_assignments", "assessments",
    "reserves", "settlements", "status_events",
]
PRIMARY_KEYS = {
    "customers": "customer_id", "coverages": "coverage_id", "adjusters": "adjuster_id",
    "policies": "policy_id", "policy_coverages": "policy_coverage_id", "incidents": "incident_id",
    "claims": "claim_id", "claim_items": "claim_item_id", "documents": "document_id",
    "claim_assignments": "assignment_id", "assessments": "assessment_id",
    "reserves": "reserve_id", "settlements": "settlement_id", "status_events": "event_id",
}
# status_events.entity_id points to one of four tables, so it has no foreign key.
FOREIGN_KEYS = {
    "policies": [("customer_id", "customers", "customer_id")],
    "policy_coverages": [("policy_id", "policies", "policy_id"),
                         ("coverage_id", "coverages", "coverage_id")],
    "incidents": [("policy_id", "policies", "policy_id")],
    "claims": [("policy_id", "policies", "policy_id"), ("incident_id", "incidents", "incident_id"),
               ("coverage_id", "coverages", "coverage_id")],
    "claim_items": [("claim_id", "claims", "claim_id")],
    "documents": [("claim_id", "claims", "claim_id")],
    "claim_assignments": [("claim_id", "claims", "claim_id"),
                          ("adjuster_id", "adjusters", "adjuster_id")],
    "assessments": [("claim_id", "claims", "claim_id"), ("adjuster_id", "adjusters", "adjuster_id")],
    "reserves": [("claim_id", "claims", "claim_id"), ("assessment_id", "assessments", "assessment_id"),
                 ("supersedes_reserve_id", "reserves", "reserve_id")],
    "settlements": [("claim_id", "claims", "claim_id"),
                    ("assessment_id", "assessments", "assessment_id"),
                    ("approver_id", "adjusters", "adjuster_id")],
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _py(v):
    """Convert one cell to a plain Python value (None, bool, int, float, str)."""
    if v is None:
        return None
    if isinstance(v, date):
        return v.isoformat()
    if pd.isna(v):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), 2)
    return v


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_csv(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, float_format="%.2f", lineterminator="\n")


def _write_json(df, path):
    cols = list(df.columns)
    lines = [json.dumps(dict(zip(cols, map(_py, row))), separators=(",", ":"))
             for row in df.itertuples(index=False, name=None)]
    _write_text(path, "[\n" + ",\n".join(lines) + "\n]\n")


def _sql_type(series):
    if pd.api.types.is_bool_dtype(series) or pd.api.types.is_integer_dtype(series):
        return "INTEGER"
    if pd.api.types.is_float_dtype(series):
        return "REAL"
    values = series.dropna()
    if len(values) and all(isinstance(v, (bool, np.bool_)) for v in values):
        return "INTEGER"
    return "TEXT"                                  # ids, enums, ISO dates, text


def _sql_literal(v):
    v = _py(v)
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.2f}"
    return "'" + str(v).replace("'", "''") + "'"


def create_table_sql(name, df):
    lines = []
    for col in df.columns:
        extra = " PRIMARY KEY NOT NULL" if col == PRIMARY_KEYS[name] else ""
        lines.append(f"    {col} {_sql_type(df[col])}{extra}")
    for col, ref_table, ref_col in FOREIGN_KEYS.get(name, []):
        lines.append(f"    FOREIGN KEY ({col}) REFERENCES {ref_table}({ref_col})")
    statements = [f"CREATE TABLE {name} (\n" + ",\n".join(lines) + "\n);"]
    statements += [f"CREATE INDEX idx_{name}_{col} ON {name}({col});"
                   for col, _, _ in FOREIGN_KEYS.get(name, [])]
    return "\n".join(statements) + "\n"


def _write_sql(tables, sql_dir):
    schema = ["-- Insurance claims synthetic dataset: schema (SQLite).",
              "-- Parent tables come first. Dates are ISO text; booleans are 0/1.", ""]
    schema += [create_table_sql(name, tables[name]) for name in TABLE_ORDER]
    _write_text(sql_dir / "schema.sql", "\n".join(schema))

    seed = ["-- Insurance claims synthetic dataset: seed data. Run schema.sql first.",
            "BEGIN TRANSACTION;"]
    for name in TABLE_ORDER:
        df = tables[name]
        cols = ", ".join(df.columns)
        rows = ["(" + ", ".join(_sql_literal(v) for v in row) + ")"
                for row in df.itertuples(index=False, name=None)]
        for i in range(0, len(rows), 200):
            seed.append(f"INSERT INTO {name} ({cols}) VALUES\n" + ",\n".join(rows[i:i + 200]) + ";")
    seed.append("COMMIT;")
    _write_text(sql_dir / "seed.sql", "\n".join(seed) + "\n")


def _readme(run, tables, ground_truth):
    command = _command(run)
    rows = "\n".join(f"| {name} | {len(tables[name])} |" for name in TABLE_ORDER)
    return f"""# Insurance claims synthetic dataset

Synthetic data for an insurance claims workflow (intake, coverage validation, document
requests, eligibility assessment, settlement routing). Generated with a fixed seed.

- Seed: {run['seed']}
- Reference date ("today" for all derived values): {REFERENCE_DATE}
- Size: {run['policies']} policies, {run['claims']} claims, 5 claim types
- Regenerate: `{command}`

## Folders

| Path | Contents |
|---|---|
| `csv/`, `json/` | The input tables, one file per table |
| `sql/` | `schema.sql` (keys, foreign keys, indexes) and `seed.sql` |
| `ground_truth/` | Labels for known anomalies and expected decisions ({len(ground_truth)} rows, one per claim) |
| `reports/` | `validation_summary.md` and `validation_results.csv` |
| `manifest.json` | Seed, command, environment, row counts and a SHA-256 checksum of every file |
| `data_dictionary.md` | Every field: type, allowed values, uniqueness, validation rule |

## Tables

| Table | Rows |
|---|---|
{rows}

## Ground truth

`ground_truth/` must never be used as an input feature. It is not part of the table
exports or the SQL seed. Expected decisions in it come from the documented rules.

## Provenance

No external data was used and no personal data was collected. Names come from short fictional
lists, email addresses use the reserved `example.com` domain, and all amounts are in USD.
"""


def _command(run):
    return f"python -m generator --seed {run['seed']} --policies {run['policies']} --claims {run['claims']}"


def write_manifest(out_dir, tables, ground_truth, run):
    out = Path(out_dir)
    paths = [out / "README.md", out / "data_dictionary.md"]
    for sub in OWNED_FOLDERS:
        paths += [p for p in (out / sub).rglob("*") if p.is_file()]
    files = [{"path": p.relative_to(out).as_posix(), "bytes": p.stat().st_size,
              "sha256": sha256_file(p)} for p in sorted(paths) if p.exists()]
    counts = {name: {"rows": len(tables[name])} for name in TABLE_ORDER}
    counts["ground_truth"] = {"rows": len(ground_truth)}
    manifest = {
        "dataset": "insurance-claims-synthetic-data",
        "generator_version": GENERATOR_VERSION,
        "command": _command(run),
        "seed": run["seed"],
        "reference_date": REFERENCE_DATE.isoformat(),
        "parameters": {"policies": run["policies"], "claims": run["claims"],
                       "customer_ratio": CUSTOMER_RATIO,
                       "anomaly_plan_per_1000_claims": ANOMALY_PLAN_PER_1000},
        "environment": {"python": platform.python_version(),
                        "pandas": pd.__version__, "numpy": np.__version__},
        "external_data": [],
        "provenance": ("All values are generated by code from the fixed seed. No external datasets, "
                       "no scraping, no personal data. Source URL, license and retrieval date fields "
                       "are not needed because the external_data list is empty."),
        "tables": counts,
        "files": files,
    }
    _write_text(out / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    return manifest


def export_dataset(out_dir, tables, ground_truth, run, report=None):
    """Write every artifact. `report` is (markdown_text, clean_results, final_results) or None."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for sub in OWNED_FOLDERS:
        shutil.rmtree(out / sub, ignore_errors=True)       # no stale files can reach the manifest
    for name in ("manifest.json", "README.md", "data_dictionary.md"):
        (out / name).unlink(missing_ok=True)

    for name in TABLE_ORDER:
        _write_csv(tables[name], out / "csv" / f"{name}.csv")
        _write_json(tables[name], out / "json" / f"{name}.json")
    _write_sql(tables, out / "sql")

    _write_csv(ground_truth, out / "ground_truth" / "ground_truth.csv")
    _write_json(ground_truth, out / "ground_truth" / "ground_truth.json")

    if report is not None:
        write_report(out / "reports", *report)

    _write_text(out / "README.md", _readme(run, tables, ground_truth))
    dictionary = Path(__file__).resolve().parent.parent / "docs" / "data_dictionary.md"
    if dictionary.exists():
        shutil.copyfile(dictionary, out / "data_dictionary.md")
    return write_manifest(out, tables, ground_truth, run)