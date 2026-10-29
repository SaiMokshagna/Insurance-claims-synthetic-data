import numpy as np

from generator.master import generate_master
from generator.transactions import generate_transactions
from generator.validate import validate_master, validate_transactions, validate_workflow
from generator.workflow import generate_workflow


def make(seed=20261022, policies=300, claims=200):
    rng = np.random.default_rng(seed)
    master = generate_master(rng, policies, claims)
    tx = generate_transactions(rng, master, claims)
    wf = generate_workflow(rng, {**master, **tx})
    return {**master, **tx, **wf}


def test_validation_passes():
    t = make()
    failed = [r for r in validate_master(t) + validate_transactions(t) + validate_workflow(t)
              if not r["passed"]]
    assert failed == []


def test_same_seed_gives_identical_tables():
    a, b = make(), make()
    for name in a:
        assert a[name].equals(b[name]), name


def test_every_claim_has_a_submitted_event_and_a_status():
    t = make()
    submitted = set(t["status_events"].query("event_type == 'CLAIM_SUBMITTED'")["entity_id"])
    assert submitted == set(t["claims"]["claim_id"])
    assert t["claims"]["current_status"].notna().all()


def test_pending_document_claims_have_a_reserve_but_no_settlement():
    t = make()
    pending = t["assessments"].query("eligibility_decision == 'PENDING_DOCUMENTS'")
    assert set(pending["claim_id"]).isdisjoint(set(t["settlements"]["claim_id"]))
    assert set(pending["assessment_id"]) <= set(t["reserves"]["assessment_id"])


def test_rejected_settlements_are_never_paid():
    t = make()
    rejected = t["settlements"].query("routing_decision == 'REJECT'")
    assert (rejected["settlement_status"] != "PAID").all()


def test_every_paid_settlement_has_a_released_reserve():
    t = make()
    paid = (t["settlements"]["settlement_status"] == "PAID").sum()
    released = (t["reserves"]["reserve_type"] == "REVISED").sum()
    assert paid == released