"""Rules-based detector. It looks ONLY at the final tables (never at ground_truth)
and predicts ONE issue label per claim; report.py scores it against ground_truth.

Defect types are detected with independent pandas logic (not rules.py), so a
perfect score proves the defects are detectable from the recorded data.
The three 'natural' types (fraud, incomplete evidence, over-limit) use the
documented rules engine, so for those the score only shows the labels agree
with the rules.
"""
import pandas as pd

from generator.anomalies import _natural_label
from generator.context import build_claim_contexts
from generator.rules import evaluate_claim

# If several signals fire for one claim, the first one in this list wins.
PRIORITY = [
    "CLAIM_PAID_TWICE", "SETTLEMENT_EXCEEDS_LIMIT", "MISSING_MANDATORY_DOCUMENT",
    "CLAIM_BEFORE_POLICY_START", "POLICY_CANCELLED_BEFORE_INCIDENT",
    "INCIDENT_OUTSIDE_COVERAGE", "DUPLICATE_CLAIM", "DUPLICATE_INCIDENT",
    "FRAUD_SUSPECTED", "INCOMPLETE_EVIDENCE", "AMOUNT_OVER_LIMIT",
]
ISSUE_TYPES = PRIORITY + ["NONE"]


def detect(tables):
    clm, inc, pol = tables["claims"], tables["incidents"], tables["policies"]
    pc, stl, doc = tables["policy_coverages"], tables["settlements"], tables["documents"]

    d = (clm[["claim_id", "policy_id", "incident_id", "coverage_id", "submitted_date"]]
         .merge(inc[["incident_id", "incident_type", "incident_date"]], on="incident_id")
         .merge(pol[["policy_id", "effective_date", "expiry_date", "cancellation_date", "lapse_date"]],
                on="policy_id")
         .merge(pc[["policy_id", "coverage_id", "coverage_limit"]], on=["policy_id", "coverage_id"])
         .sort_values("claim_id").reset_index(drop=True))

    # --- coverage defects (same order as the written rules: first match wins) ---
    sub, idate = pd.to_datetime(d["submitted_date"]), pd.to_datetime(d["incident_date"])
    eff, exp = pd.to_datetime(d["effective_date"]), pd.to_datetime(d["expiry_date"])
    can, lap = pd.to_datetime(d["cancellation_date"]), pd.to_datetime(d["lapse_date"])
    claim_before = sub < eff
    inc_before = (idate < eff) & ~claim_before
    cancelled = can.notna() & (idate > can) & ~claim_before & ~inc_before
    after_end = (((lap.notna() & (idate > lap)) | (idate > exp))
                 & ~claim_before & ~inc_before & ~cancelled)

    # --- payment defects ---
    paid = stl[stl["settlement_status"] == "PAID"]
    paid_twice = d["claim_id"].map(paid.groupby("claim_id").size()).fillna(0) > 1
    limit_of = d.set_index("claim_id")["coverage_limit"]
    over = stl.assign(limit=stl["claim_id"].map(limit_of))
    over = over[over["approved_amount"] > over["limit"] + 0.005]
    exceeds = d["claim_id"].isin(set(over["claim_id"]))
    missing = doc[doc["is_mandatory"].astype(bool) & ~doc["status"].isin(["RECEIVED", "VERIFIED"])]
    missing_paid = d["claim_id"].isin(set(missing["claim_id"]) & set(paid["claim_id"]))

    # --- duplicates: the earliest claim for (policy, type, date) is the original ---
    keys = ["policy_id", "incident_type", "incident_date"]
    first_incident = d.groupby(keys)["incident_id"].transform("first")
    later = d.duplicated(keys, keep="first")
    dup_claim = later & (d["incident_id"] == first_incident)
    dup_incident = later & (d["incident_id"] != first_incident)

    # --- natural types, from the documented rules engine ---
    natural = {cid: _natural_label(evaluate_claim(ctx)["reason_code"])
               for cid, ctx in build_claim_contexts(tables).items()}
    nat = d["claim_id"].map(natural)

    flags = {
        "CLAIM_PAID_TWICE": paid_twice,
        "SETTLEMENT_EXCEEDS_LIMIT": exceeds,
        "MISSING_MANDATORY_DOCUMENT": missing_paid,
        "CLAIM_BEFORE_POLICY_START": claim_before,
        "POLICY_CANCELLED_BEFORE_INCIDENT": cancelled,
        "INCIDENT_OUTSIDE_COVERAGE": inc_before | after_end,
        "DUPLICATE_CLAIM": dup_claim,
        "DUPLICATE_INCIDENT": dup_incident,
        "FRAUD_SUSPECTED": nat == "FRAUD_SUSPECTED",
        "INCOMPLETE_EVIDENCE": nat == "INCOMPLETE_EVIDENCE",
        "AMOUNT_OVER_LIMIT": nat == "AMOUNT_OVER_LIMIT",
    }
    predicted = pd.Series("NONE", index=d.index)
    for issue in reversed(PRIORITY):            # apply low priority first so high priority overwrites
        predicted = predicted.mask(flags[issue], issue)
    return pd.DataFrame({"claim_id": d["claim_id"], "predicted_issue": predicted})


def score_detection(ground_truth, predictions):
    """Per-issue precision / recall / F1, plus the list of misclassified claims."""
    m = ground_truth[["claim_id", "issue_type"]].merge(predictions, on="claim_id")
    rows = []
    for issue in ISSUE_TYPES:
        truth, pred = m["issue_type"] == issue, m["predicted_issue"] == issue
        tp = int((truth & pred).sum())
        fp = int((~truth & pred).sum())
        fn = int((truth & ~pred).sum())
        precision = tp / (tp + fp) if tp + fp else float("nan")
        recall = tp / (tp + fn) if tp + fn else float("nan")
        f1 = 2 * precision * recall / (precision + recall) if tp else float("nan")
        rows.append({"issue_type": issue, "support": int(truth.sum()), "predicted": int(pred.sum()),
                     "tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1})
    mismatches = m[m["issue_type"] != m["predicted_issue"]].reset_index(drop=True)
    return pd.DataFrame(rows), mismatches