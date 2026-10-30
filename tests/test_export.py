import json
import sqlite3

from generator.export import export_dataset, sha256_file

RUN = {"seed": 20261022, "policies": 2000, "claims": 1000}


def test_sql_seed_loads_with_foreign_keys_enforced(dataset, tmp_path):
    _, final, gt = dataset
    export_dataset(tmp_path, final, gt, RUN)
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((tmp_path / "sql" / "schema.sql").read_text(encoding="utf-8"))
    con.executescript((tmp_path / "sql" / "seed.sql").read_text(encoding="utf-8"))
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    for name, df in final.items():
        assert con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] == len(df), name
    # reconciliation, checked in SQL instead of pandas
    bad = con.execute("""SELECT COUNT(*) FROM claims c WHERE ABS(c.claimed_amount -
                         (SELECT SUM(claimed_amount) FROM claim_items i WHERE i.claim_id = c.claim_id)) > 0.005""")
    assert bad.fetchone()[0] == 0
    paid_twice = con.execute("""SELECT COUNT(*) FROM (SELECT claim_id FROM settlements
                                WHERE settlement_status = 'PAID' GROUP BY claim_id HAVING COUNT(*) > 1)""")
    assert paid_twice.fetchone()[0] == (gt["issue_type"] == "CLAIM_PAID_TWICE").sum()


def test_json_files_match_the_tables(dataset, tmp_path):
    _, final, gt = dataset
    export_dataset(tmp_path, final, gt, RUN)
    for name, df in final.items():
        records = json.loads((tmp_path / "json" / f"{name}.json").read_text(encoding="utf-8"))
        assert len(records) == len(df), name
        assert list(records[0]) == list(df.columns), name
    claims = json.loads((tmp_path / "json" / "claims.json").read_text(encoding="utf-8"))
    assert claims[0]["submitted_date"].startswith("2026-")


def test_manifest_checksums_match_and_ground_truth_stays_separate(dataset, tmp_path):
    _, final, gt = dataset
    export_dataset(tmp_path, final, gt, RUN)
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    paths = [f["path"] for f in manifest["files"]]
    assert "manifest.json" not in paths
    for f in manifest["files"]:
        assert sha256_file(tmp_path / f["path"]) == f["sha256"], f["path"]
    assert manifest["tables"]["claims"]["rows"] == len(final["claims"])
    assert manifest["tables"]["ground_truth"]["rows"] == len(gt)
    assert manifest["external_data"] == []
    assert not any("ground_truth" in p for p in paths if p.startswith(("csv/", "json/", "sql/")))
    for sql_file in ("schema.sql", "seed.sql"):
        assert "ground_truth" not in (tmp_path / "sql" / sql_file).read_text(encoding="utf-8")


def test_two_exports_are_byte_identical(dataset, tmp_path):
    _, final, gt = dataset
    first = export_dataset(tmp_path / "a", final, gt, RUN)
    second = export_dataset(tmp_path / "b", final, gt, RUN)
    assert first == second