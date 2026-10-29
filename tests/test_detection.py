import inspect

import pandas as pd

from generator.anomalies import check_expected_failures
from generator.detect import detect, score_detection
from generator.report import build_report, categorize, write_report
from generator.validate import validate_all


def test_detector_makes_no_mistakes_on_the_final_dataset(dataset):
    _, final, gt = dataset
    predictions = detect(final)
    scores, mismatches = score_detection(gt, predictions)
    assert len(predictions) == len(gt)
    assert mismatches.empty
    assert (scores["fp"] == 0).all() and (scores["fn"] == 0).all()


def test_detector_only_receives_the_tables():
    assert list(inspect.signature(detect).parameters) == ["tables"]


def test_scoring_arithmetic():
    gt = pd.DataFrame({"claim_id": list("abcd"),
                       "issue_type": ["CLAIM_PAID_TWICE", "CLAIM_PAID_TWICE", "FRAUD_SUSPECTED", "NONE"]})
    pred = pd.DataFrame({"claim_id": list("abcd"),
                         "predicted_issue": ["CLAIM_PAID_TWICE", "FRAUD_SUSPECTED", "FRAUD_SUSPECTED", "NONE"]})
    scores, mismatches = score_detection(gt, pred)
    row = scores.set_index("issue_type")
    assert (row.loc["CLAIM_PAID_TWICE", ["tp", "fp", "fn"]] == [1, 0, 1]).all()
    assert row.loc["CLAIM_PAID_TWICE", "precision"] == 1.0
    assert row.loc["CLAIM_PAID_TWICE", "recall"] == 0.5
    assert (row.loc["FRAUD_SUSPECTED", ["tp", "fp", "fn"]] == [1, 1, 0]).all()
    assert row.loc["FRAUD_SUSPECTED", "precision"] == 0.5
    assert row.loc["FRAUD_SUSPECTED", "recall"] == 1.0
    assert list(mismatches["claim_id"]) == ["b"]


def test_check_families():
    assert categorize("customers.customer_id is unique") == "Primary-key uniqueness"
    assert categorize("FK claims.policy_id -> policies") == "Foreign keys and joins"
    assert categorize("status_events: every transition is legal for its lifecycle") == "Lifecycle and audit trail"
    assert categorize("claims: claimed_amount equals sum of its items") == "Arithmetic reconciliation"
    assert categorize("rules: every claim is paid at most once") == "Duplicate checks"


def test_report_has_every_section_and_is_written(dataset, tmp_path):
    clean, final, gt = dataset
    clean_results, final_results = validate_all(clean), validate_all(final)
    problems = check_expected_failures(final_results, gt)
    scores, mismatches = score_detection(gt, detect(final))
    run = {"seed": 20261022, "policies": 2000, "claims": 1000}
    text = build_report(run, final, gt, clean_results, final_results, problems, scores, mismatches)
    for heading in ["# Validation Summary", "## 1. Dataset", "## 2. Validation of the clean dataset",
                    "## 3. Injected defects", "## 4. Ground truth", "## 5. Detection",
                    "## 6. Distributions", "## 7. Known limitations"]:
        assert heading in text
    write_report(tmp_path, text, clean_results, final_results)
    assert (tmp_path / "validation_summary.md").exists()
    assert (tmp_path / "validation_results.csv").exists()