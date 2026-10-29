import pytest

from generator.anomalies import check_expected_failures, scale_plan
from generator.pipeline import build_dataset
from generator.validate import validate_all

SEED, POLICIES, CLAIMS = 20261022, 2000, 1000


@pytest.fixture(scope="module")
def data():
    return build_dataset(SEED, POLICIES, CLAIMS)     # (clean, final, ground_truth)


def test_clean_dataset_passes_every_check(data):
    clean, _, _ = data
    assert [r for r in validate_all(clean) if not r["passed"]] == []


def test_injected_defects_are_the_only_failures(data):
    _, final, gt = data
    assert check_expected_failures(validate_all(final), gt) == []


def test_one_ground_truth_row_per_claim(data):
    _, final, gt = data
    assert len(gt) == len(final["claims"]) == CLAIMS
    assert list(gt["claim_id"]) == list(final["claims"]["claim_id"])


def test_every_planned_defect_was_injected(data):
    _, _, gt = data
    injected = gt[gt["origin"] == "INJECTED"]["issue_type"].value_counts().to_dict()
    assert injected == scale_plan(CLAIMS)


def test_all_required_edge_cases_are_present(data):
    _, _, gt = data
    required = {"CLAIM_BEFORE_POLICY_START", "POLICY_CANCELLED_BEFORE_INCIDENT",
                "DUPLICATE_INCIDENT", "SETTLEMENT_EXCEEDS_LIMIT",
                "MISSING_MANDATORY_DOCUMENT", "CLAIM_PAID_TWICE",
                "INCIDENT_OUTSIDE_COVERAGE", "DUPLICATE_CLAIM", "FRAUD_SUSPECTED"}
    assert required <= set(gt[gt["origin"] == "INJECTED"]["issue_type"])
    natural = set(gt[gt["origin"] == "NATURAL"]["issue_type"])
    assert {"AMOUNT_OVER_LIMIT", "INCOMPLETE_EVIDENCE"} <= natural


def test_ground_truth_does_not_leak_into_input_tables(data):
    _, final, gt = data
    forbidden = set(gt.columns) - {"claim_id"}
    for name, df in final.items():
        assert forbidden.isdisjoint(df.columns), name


def test_expected_labels_follow_the_rules(data):
    _, _, gt = data
    inj = gt[gt["origin"] == "INJECTED"]

    def reasons(issue):
        return set(inj[inj["issue_type"] == issue]["expected_reason_code"])

    assert reasons("CLAIM_BEFORE_POLICY_START") == {"CLAIM_BEFORE_POLICY_START"}
    assert reasons("POLICY_CANCELLED_BEFORE_INCIDENT") == {"POLICY_CANCELLED_BEFORE_INCIDENT"}
    assert reasons("INCIDENT_OUTSIDE_COVERAGE") == {"INCIDENT_BEFORE_POLICY_START",
                                                    "INCIDENT_AFTER_COVERAGE_END"}
    assert reasons("DUPLICATE_CLAIM") == {"DUPLICATE_CLAIM"}
    assert reasons("DUPLICATE_INCIDENT") == {"DUPLICATE_INCIDENT"}
    assert reasons("MISSING_MANDATORY_DOCUMENT") <= {"MISSING_MANDATORY_DOCUMENT", "DOCUMENTS_OVERDUE"}
    assert set(inj[inj["issue_type"] == "FRAUD_SUSPECTED"]["expected_decision"]) == {"REFER_INVESTIGATION"}
    for issue in ("SETTLEMENT_EXCEEDS_LIMIT", "CLAIM_PAID_TWICE"):
        decisions = set(inj[inj["issue_type"] == issue]["expected_decision"])
        assert decisions <= {"ELIGIBLE", "PARTIALLY_ELIGIBLE"}


def test_same_seed_gives_identical_output(data):
    _, final, gt = data
    _, final2, gt2 = build_dataset(SEED, POLICIES, CLAIMS)
    for name in final:
        assert final[name].equals(final2[name]), name
    assert gt.equals(gt2)