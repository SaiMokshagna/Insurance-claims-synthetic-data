from datetime import date, timedelta

import pandas as pd

from generator.rules import (
    calculate_payout, evaluate_claim, find_duplicates, fraud_risk_score,
    required_seniority,
)

REF = date(2026, 10, 22)


def ctx(**overrides):
    base = {
        "incident_date": date(2026, 6, 1), "submitted_date": date(2026, 6, 5),
        "policy_effective": date(2026, 1, 1), "policy_expiry": date(2026, 12, 31),
        "policy_cancellation": None, "policy_lapse": None,
        "exclusion_triggered": None,
        "claimed_amount": 2000.0, "coverage_limit": 25000.0, "deductible": 500.0,
        "documents": [{"is_mandatory": True, "status": "VERIFIED", "requested_date": None}],
        "duplicate_reason": None, "prior_claims_12m": 0, "reporting_delay_days": 4,
        "customer_risk_tier": "LOW", "reference_date": REF,
    }
    base.update(overrides)
    return base


def pending_doc(days_ago):
    return [{"is_mandatory": True, "status": "REQUESTED",
             "requested_date": REF - timedelta(days=days_ago)}]


# --- the normal case ---
def test_clean_claim_is_eligible_and_auto_approved():
    r = evaluate_claim(ctx())
    assert r["eligibility_decision"] == "ELIGIBLE"
    assert r["reason_code"] == "COVERED_OK"
    assert r["eligible_amount"] == 2000.0
    assert r["reserve_amount"] == 1500.0
    assert r["recommended_amount"] == 1500.0
    assert r["routing_decision"] == "AUTO_APPROVE"
    assert r["approver_level"] is None
    assert r["fraud_risk_score"] == 0


# --- coverage boundaries ---
def test_incident_on_effective_date_is_covered():
    r = evaluate_claim(ctx(incident_date=date(2026, 1, 1)))
    assert r["reason_code"] == "COVERED_OK"


def test_incident_day_before_effective_date_is_rejected():
    r = evaluate_claim(ctx(incident_date=date(2025, 12, 31)))
    assert r["reason_code"] == "INCIDENT_BEFORE_POLICY_START"
    assert r["eligibility_decision"] == "INELIGIBLE"


def test_incident_on_cancellation_date_is_covered_next_day_is_not():
    cancelled = date(2026, 6, 1)
    assert evaluate_claim(ctx(policy_cancellation=cancelled,
                              incident_date=cancelled))["reason_code"] == "COVERED_OK"
    r = evaluate_claim(ctx(policy_cancellation=cancelled,
                           incident_date=date(2026, 6, 2)))
    assert r["reason_code"] == "POLICY_CANCELLED_BEFORE_INCIDENT"


def test_incident_after_expiry_or_lapse_is_rejected():
    r1 = evaluate_claim(ctx(policy_expiry=date(2026, 6, 1), incident_date=date(2026, 6, 2)))
    r2 = evaluate_claim(ctx(policy_lapse=date(2026, 6, 1), incident_date=date(2026, 6, 2)))
    assert r1["reason_code"] == r2["reason_code"] == "INCIDENT_AFTER_COVERAGE_END"


def test_claim_submitted_before_policy_start():
    r = evaluate_claim(ctx(submitted_date=date(2025, 12, 30), incident_date=date(2025, 12, 29)))
    assert r["reason_code"] == "CLAIM_BEFORE_POLICY_START"


# --- exclusions, duplicates, documents ---
def test_excluded_peril_is_rejected_with_zero_reserve():
    r = evaluate_claim(ctx(exclusion_triggered="RACING"))
    assert r["reason_code"] == "EXCLUDED_PERIL"
    assert r["eligible_amount"] == 0.0 and r["reserve_amount"] == 0.0
    assert r["routing_decision"] == "REJECT"
    assert "RACING" in r["reason_text"]


def test_duplicate_claim_is_rejected():
    r = evaluate_claim(ctx(duplicate_reason="DUPLICATE_CLAIM"))
    assert r["reason_code"] == "DUPLICATE_CLAIM"
    assert r["duplicate_suspected"] is True


def test_missing_document_within_deadline_is_pending():
    r = evaluate_claim(ctx(documents=pending_doc(10)))
    assert r["eligibility_decision"] == "PENDING_DOCUMENTS"
    assert r["reason_code"] == "MISSING_MANDATORY_DOCUMENT"
    assert r["routing_decision"] is None
    assert r["recommended_amount"] == 0.0
    assert r["reserve_amount"] == 1500.0          # preliminary reserve is still held


def test_document_deadline_boundary_30_pending_31_overdue():
    assert evaluate_claim(ctx(documents=pending_doc(30)))["reason_code"] == "MISSING_MANDATORY_DOCUMENT"
    r = evaluate_claim(ctx(documents=pending_doc(31)))
    assert r["reason_code"] == "DOCUMENTS_OVERDUE"
    assert r["reserve_amount"] == 0.0


# --- fraud ---
def test_fraud_score_components_and_cap():
    assert fraud_risk_score(4, 0, 2000, 25000, 100, "LOW") == 0
    assert fraud_risk_score(40, 3, 30000, 25000, 5, "HIGH") == 20 + 25 + 15 + 15 + 10
    assert fraud_risk_score(15, 1, 20000, 25000, 100, "LOW") == 10 + 5 + 10


def test_fraud_referral_at_score_55():
    r = evaluate_claim(ctx(reporting_delay_days=40, prior_claims_12m=3, claimed_amount=21000.0))
    assert r["fraud_risk_score"] == 55
    assert r["eligibility_decision"] == "REFER_INVESTIGATION"
    assert r["routing_decision"] == "INVESTIGATION"
    assert r["approver_level"] == "SENIOR"
    assert r["recommended_amount"] == 0.0
    assert r["reserve_amount"] == 20500.0


def test_score_30_forces_senior_review_but_not_referral():
    r = evaluate_claim(ctx(reporting_delay_days=40, customer_risk_tier="HIGH"))
    assert r["fraud_risk_score"] == 30
    assert r["eligibility_decision"] == "ELIGIBLE"
    assert r["routing_decision"] == "SENIOR_REVIEW"
    assert r["approver_level"] == "SENIOR"


# --- money ---
def test_payout_math():
    assert calculate_payout(10000, 500, 25000)["payout"] == 9500.0
    capped = calculate_payout(30000, 500, 25000)
    assert capped["payout"] == 25000.0 and capped["capped"] is True
    small = calculate_payout(300, 500, 25000)
    assert small["payout"] == 0.0 and small["deductible_applied"] == 300.0


def test_below_deductible_boundary():
    for claimed in (400.0, 500.0):                 # equal to the deductible is still nothing payable
        r = evaluate_claim(ctx(claimed_amount=claimed))
        assert r["reason_code"] == "BELOW_DEDUCTIBLE"
    assert evaluate_claim(ctx(claimed_amount=500.01))["reason_code"] == "COVERED_OK"


def test_limit_cap_boundary():
    over = evaluate_claim(ctx(claimed_amount=30000.0))
    assert over["eligibility_decision"] == "PARTIALLY_ELIGIBLE"
    assert over["reason_code"] == "COVERED_LIMIT_CAPPED"
    assert over["recommended_amount"] == 25000.0
    exact = evaluate_claim(ctx(claimed_amount=25500.0))   # net equals the limit: not capped
    assert exact["eligibility_decision"] == "ELIGIBLE"
    assert exact["recommended_amount"] == 25000.0


# --- routing and approval level ---
def test_large_payout_goes_to_senior_review():
    r = evaluate_claim(ctx(claimed_amount=6000.0))
    assert r["recommended_amount"] == 5500.0
    assert r["routing_decision"] == "SENIOR_REVIEW"
    assert r["approver_level"] == "SENIOR"


def test_required_seniority_boundaries():
    assert required_seniority(5000.0) == "JUNIOR"
    assert required_seniority(5000.01) == "SENIOR"
    assert required_seniority(25000.0) == "SENIOR"
    assert required_seniority(25000.01) == "MANAGER"


# --- duplicate finder ---
def test_find_duplicates_flags_only_the_later_claims():
    claims = pd.DataFrame({
        "claim_id": ["CLM-1", "CLM-2", "CLM-3", "CLM-4"],
        "policy_id": ["P1", "P1", "P1", "P2"],
        "incident_id": ["INC-1", "INC-1", "INC-3", "INC-4"],
    })
    incidents = pd.DataFrame({
        "incident_id": ["INC-1", "INC-3", "INC-4"],
        "incident_type": ["THEFT", "THEFT", "THEFT"],
        "incident_date": [date(2026, 3, 1), date(2026, 3, 1), date(2026, 3, 1)],
    })
    assert find_duplicates(claims, incidents) == {
        "CLM-2": "DUPLICATE_CLAIM",       # same incident claimed twice
        "CLM-3": "DUPLICATE_INCIDENT",    # new incident row, same policy/type/date
    }