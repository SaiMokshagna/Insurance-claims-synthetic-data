"""Build the per-claim context (a plain dict) that the rules engine consumes."""
import pandas as pd

from generator.config import REFERENCE_DATE
from generator.rules import find_duplicates


def _clean(value):
    """Turn pandas missing values (NaN / NaT / NA) into None."""
    return None if pd.isna(value) else value


def build_claim_contexts(tables):
    claims, incidents = tables["claims"], tables["incidents"]
    policies = tables["policies"].set_index("policy_id").to_dict("index")
    risk_tier = tables["customers"].set_index("customer_id")["risk_tier"].to_dict()
    pcs = tables["policy_coverages"].set_index(["policy_id", "coverage_id"]).to_dict("index")
    inc = incidents.set_index("incident_id").to_dict("index")

    docs_by_claim = {}
    for d in tables["documents"].to_dict("records"):
        docs_by_claim.setdefault(d["claim_id"], []).append({
            "is_mandatory": bool(d["is_mandatory"]),
            "status": d["status"],
            "requested_date": _clean(d["requested_date"]),
        })
    duplicates = find_duplicates(claims, incidents)

    contexts = {}
    for c in claims.to_dict("records"):
        pol = policies[c["policy_id"]]
        pc = pcs[(c["policy_id"], c["coverage_id"])]
        i = inc[c["incident_id"]]
        contexts[c["claim_id"]] = {
            "claim_id": c["claim_id"],
            "incident_date": i["incident_date"],
            "submitted_date": c["submitted_date"],
            "policy_effective": pol["effective_date"],
            "policy_expiry": pol["expiry_date"],
            "policy_cancellation": _clean(pol["cancellation_date"]),
            "policy_lapse": _clean(pol["lapse_date"]),
            "exclusion_triggered": _clean(i["exclusion_triggered"]),
            "claimed_amount": float(c["claimed_amount"]),
            "coverage_limit": float(pc["coverage_limit"]),
            "deductible": float(pc["deductible"]),
            "documents": docs_by_claim.get(c["claim_id"], []),
            "duplicate_reason": duplicates.get(c["claim_id"]),
            "prior_claims_12m": int(c["prior_claims_12m"]),
            "reporting_delay_days": int(c["reporting_delay_days"]),
            "customer_risk_tier": risk_tier[pol["customer_id"]],
            "reference_date": REFERENCE_DATE,
        }
    return contexts