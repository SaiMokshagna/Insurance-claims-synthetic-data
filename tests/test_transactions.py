import numpy as np

from generator.config import CLAIM_TYPES
from generator.master import generate_master
from generator.transactions import generate_transactions
from generator.validate import validate_master, validate_transactions


def make(seed=20261022, policies=300, claims=200):
    rng = np.random.default_rng(seed)
    master = generate_master(rng, policies, claims)
    return {**master, **generate_transactions(rng, master, claims)}


def test_claim_and_incident_counts():
    t = make()
    assert len(t["claims"]) == 200
    assert len(t["incidents"]) == 200


def test_all_five_claim_types_present():
    assert set(make()["claims"]["claim_type"]) == set(CLAIM_TYPES)


def test_claims_are_in_submission_order():
    dates = list(make()["claims"]["submitted_date"])
    assert dates == sorted(dates)


def test_outstanding_documents_exist():
    assert (make()["documents"]["status"] == "REQUESTED").any()


def test_same_seed_gives_identical_tables():
    a, b = make(), make()
    for name in a:
        assert a[name].equals(b[name]), name


def test_validation_passes():
    t = make()
    failed = [r for r in validate_master(t) + validate_transactions(t) if not r["passed"]]
    assert failed == []