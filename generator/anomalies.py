"""Layer B: inject labelled DEFECTS into the finished dataset, then build ground_truth.

Layer A scenarios (duplicates, fraud pattern) were created earlier as inputs, so the
workflow handled them by the rules. Layer B edits FINISHED records, so the recorded
data breaks a documented rule on purpose, and every edit is labelled.
"""
from datetime import timedelta

import pandas as pd

from generator import ids
from generator.config import ANOMALY_PLAN_PER_1000, REFERENCE_DATE as REF
from generator.context import build_claim_contexts
from generator.rules import evaluate_claim

LAYER_A_DETAILS = {
    "DUPLICATE_CLAIM": ("claims", "incident_id",
                        "A second claim was filed on an incident that is already claimed."),
    "DUPLICATE_INCIDENT": ("incidents", "incident_date",
                           "The incident was re-reported as a new incident with the same policy, type and date."),
    "FRAUD_SUSPECTED": ("claims|incidents", "claimed_amount|incident_date|submitted_date",
                        "Early claim, reported late, amount near the limit, high-risk customer."),
}
NATURAL_NOTES = {
    "AMOUNT_OVER_LIMIT": "Claim exceeds what the coverage can pay; payout is capped at the limit (handled correctly).",
    "INCOMPLETE_EVIDENCE": "A mandatory document is outstanding; the claim waits or is closed for non-response (handled correctly).",
    "FRAUD_SUSPECTED": "Fraud indicators arose naturally in the baseline; the claim was referred (handled correctly).",
}

# Checks that are SUPPOSED to fail after injection, and which issue types explain them.
EXPECTED_FAILURES = {
    "incidents: incident_date inside policy coverage period":
        ["CLAIM_BEFORE_POLICY_START", "POLICY_CANCELLED_BEFORE_INCIDENT", "INCIDENT_OUTSIDE_COVERAGE"],
    "claims: submitted_date on or after policy effective_date": ["CLAIM_BEFORE_POLICY_START"],
    "settlements: at most one per claim (baseline)": ["CLAIM_PAID_TWICE"],
    "settlements: approved_amount equals recommended_amount": ["SETTLEMENT_EXCEEDS_LIMIT"],
    "settlements: recommended and approved amounts do not exceed the limit": ["SETTLEMENT_EXCEEDS_LIMIT"],
    "rules: every claim is paid at most once": ["CLAIM_PAID_TWICE"],
    "rules: paid claims have every mandatory document": ["MISSING_MANDATORY_DOCUMENT"],
}
# May fail for SOME of an issue's claims (depends on which approver was picked): only an upper bound.
MAY_ALSO_FAIL = {"settlements: approver authority covers approved_amount": "SETTLEMENT_EXCEEDS_LIMIT"}


def scale_plan(n_claims):
    return {k: max(1, round(v * n_claims / 1000)) for k, v in ANOMALY_PLAN_PER_1000.items()}


# ---------------------------------------------------------------------------
# Edits to the status_events table (IDs are re-assigned in time order at the end)
# ---------------------------------------------------------------------------
def _ts(day, hour=8):
    return f"{day.isoformat()}T{hour:02d}:00:00Z"


class _Events:
    def __init__(self, events):
        self.df = events.drop(columns="event_id")
        self.new = []

    def move_policy_issue(self, policy_id, day):
        mask = (self.df["entity_id"] == policy_id) & (self.df["event_type"] == "POLICY_ISSUED")
        self.df.loc[mask, "event_ts"] = _ts(day)

    def drop_entity(self, entity_type, entity_id):
        self.df = self.df[~((self.df["entity_type"] == entity_type) & (self.df["entity_id"] == entity_id))]

    def add(self, entity_type, entity_id, event_type, from_status, to_status, day, hour,
            actor_type="SYSTEM", actor_id=None, reason_code=None):
        self.new.append({
            "entity_type": entity_type, "entity_id": entity_id, "event_type": event_type,
            "from_status": from_status, "to_status": to_status, "event_ts": _ts(day, hour),
            "actor_type": actor_type, "actor_id": actor_id, "reason_code": reason_code,
        })

    def finish(self):
        df = pd.concat([self.df, pd.DataFrame(self.new)], ignore_index=True) if self.new else self.df
        df = df.sort_values(["event_ts", "entity_type", "entity_id"]).reset_index(drop=True)
        df.insert(0, "event_id", [ids.event_id(n) for n in range(1, len(df) + 1)])
        return df


def _set_start(pol, pc, ev, policy_id, new_start):
    """Move a policy's start date later (policy, its coverages, and its ISSUED event)."""
    pol.at[pol.index[pol["policy_id"] == policy_id][0], "effective_date"] = new_start
    for i in pc.index[pc["policy_id"] == policy_id]:
        pc.at[i, "effective_date"] = new_start
    ev.move_policy_issue(policy_id, new_start)


def _end_policy(pol, ev, policy_id, end_date, kind):
    """Cancel or lapse a policy on `end_date`; status and event history follow."""
    i = pol.index[pol["policy_id"] == policy_id][0]
    pol.at[i, "cancellation_date" if kind == "CANCELLED" else "lapse_date"] = end_date
    pol.at[i, "status"] = kind
    ev.add("POLICY", policy_id, f"POLICY_{kind}", "IN_FORCE", kind, end_date, 9)


def _paid_claims(t):
    """Claims that were paid and closed, with the facts the injectors need."""
    clm, stl, pol, inc = t["claims"], t["settlements"], t["policies"], t["incidents"]
    paid = stl[stl["settlement_status"] == "PAID"][
        ["claim_id", "settlement_id", "paid_date", "approver_id", "limit_applied"]]
    df = (clm[["claim_id", "policy_id", "incident_id", "submitted_date",
               "reporting_delay_days", "current_status"]]
          .merge(inc[["incident_id", "incident_date"]], on="incident_id")
          .merge(paid, on="claim_id")
          .merge(pol[["policy_id", "status", "effective_date", "expiry_date"]]
                 .rename(columns={"status": "policy_status"}), on="policy_id"))
    df = df[df["current_status"] == "CLOSED"].copy()
    df["policy_claims"] = df["policy_id"].map(clm.groupby("policy_id").size())
    df = df.sort_values("claim_id").reset_index(drop=True)
    df["days_to_expiry"] = [(e - s).days for e, s in zip(df["expiry_date"], df["submitted_date"])]
    df["days_since_start"] = [(i - e).days for i, e in zip(df["incident_date"], df["effective_date"])]
    df["days_since_sub"] = [(REF - s).days for s in df["submitted_date"]]
    df["days_since_paid"] = [(REF - d).days for d in df["paid_date"]]
    return df


def _choose(rng, pool, n, taken):
    pool = pool[~pool["claim_id"].isin(taken)]
    k = min(n, len(pool))
    if k == 0:
        return []
    picks = sorted(int(i) for i in rng.choice(len(pool), size=k, replace=False))
    rows = [pool.iloc[i] for i in picks]
    taken.update(r["claim_id"] for r in rows)
    return rows


def inject_defects(rng, tables, plan):
    """Return (tables with defects, {claim_id: label info}). The input tables are not changed."""
    t = {name: df.copy() for name, df in tables.items()}
    pol, pc, doc, stl = t["policies"], t["policy_coverages"], t["documents"], t["settlements"]
    ev = _Events(t["status_events"])
    labels, taken, new_settlements = {}, set(), []

    base = _paid_claims(t)
    single = base[(base["policy_claims"] == 1) & (base["policy_status"] == "IN_FORCE")]
    start_pool = single[(single["days_to_expiry"] >= 12) & (single["days_since_sub"] >= 10)]
    end_pool = single[single["days_since_start"] >= 2]
    ontime = doc[doc["is_mandatory"].astype(bool) & doc["requested_date"].isna()
                 & doc["status"].isin(["RECEIVED", "VERIFIED"])]

    def label(cid, issue, table, field, note):
        labels[cid] = {"issue_type": issue, "injected_table": table,
                       "injected_field": field, "notes": note}

    n_out = plan.get("INCIDENT_OUTSIDE_COVERAGE", 0)

    # B1: the policy starts AFTER the claim was submitted
    for r in _choose(rng, start_pool, plan.get("CLAIM_BEFORE_POLICY_START", 0), taken):
        new_start = r["submitted_date"] + timedelta(days=int(rng.integers(1, 11)))
        _set_start(pol, pc, ev, r["policy_id"], new_start)
        label(r["claim_id"], "CLAIM_BEFORE_POLICY_START", "policies", "effective_date",
              f"Policy start moved to {new_start}, after the claim was submitted on {r['submitted_date']}.")

    # B3a: the policy starts AFTER the incident (but before the claim was submitted)
    pool = start_pool[start_pool["reporting_delay_days"] >= 1]
    for r in _choose(rng, pool, (n_out + 1) // 2, taken):
        new_start = r["incident_date"] + timedelta(days=int(rng.integers(1, int(r["reporting_delay_days"]) + 1)))
        _set_start(pol, pc, ev, r["policy_id"], new_start)
        label(r["claim_id"], "INCIDENT_OUTSIDE_COVERAGE", "policies", "effective_date",
              f"Policy start moved to {new_start}, after the incident on {r['incident_date']}.")

    # B2 and B3b: the policy is cancelled / lapsed BEFORE the incident
    for issue, kind, n, field in [
        ("POLICY_CANCELLED_BEFORE_INCIDENT", "CANCELLED",
         plan.get("POLICY_CANCELLED_BEFORE_INCIDENT", 0), "cancellation_date"),
        ("INCIDENT_OUTSIDE_COVERAGE", "LAPSED", n_out // 2, "lapse_date"),
    ]:
        for r in _choose(rng, end_pool, n, taken):
            gap = int(r["days_since_start"])
            end_date = r["incident_date"] - timedelta(days=int(rng.integers(1, min(20, gap - 1) + 1)))
            _end_policy(pol, ev, r["policy_id"], end_date, kind)
            label(r["claim_id"], issue, "policies", field,
                  f"Policy {kind.lower()} on {end_date}, before the incident on {r['incident_date']}.")

    # B4: the approved settlement is 5-40% ABOVE the coverage limit
    for r in _choose(rng, base, plan.get("SETTLEMENT_EXCEEDS_LIMIT", 0), taken):
        new_amount = round(float(r["limit_applied"]) * (1.05 + 0.35 * float(rng.random())), 2)
        stl.at[stl.index[stl["settlement_id"] == r["settlement_id"]][0], "approved_amount"] = new_amount
        label(r["claim_id"], "SETTLEMENT_EXCEEDS_LIMIT", "settlements", "approved_amount",
              f"Approved amount {new_amount:,.2f} exceeds the coverage limit {r['limit_applied']:,.2f}.")

    # B5: the claim was PAID although a mandatory document was never received
    pool = base[base["claim_id"].isin(set(ontime["claim_id"]))]
    for r in _choose(rng, pool, plan.get("MISSING_MANDATORY_DOCUMENT", 0), taken):
        choices = ontime[ontime["claim_id"] == r["claim_id"]]
        d = choices.iloc[int(rng.integers(len(choices)))]
        requested = r["submitted_date"] + timedelta(days=int(rng.integers(1, 3)))
        i = doc.index[doc["document_id"] == d["document_id"]][0]
        doc.at[i, "status"] = "REQUESTED"
        doc.at[i, "requested_date"] = requested
        doc.at[i, "received_date"] = None
        doc.at[i, "file_name"] = None
        doc.at[i, "file_size_kb"] = pd.NA
        ev.drop_entity("DOCUMENT", d["document_id"])
        ev.add("DOCUMENT", d["document_id"], "DOCUMENT_REQUESTED", None, "REQUESTED", requested, 8)
        label(r["claim_id"], "MISSING_MANDATORY_DOCUMENT", "documents", "status",
              f"Mandatory document {d['document_type']} was never received, yet the claim was paid.")

    # B6: the claim is PAID a second time
    for r in _choose(rng, base[base["days_since_paid"] >= 4], plan.get("CLAIM_PAID_TWICE", 0), taken):
        s1 = stl[stl["settlement_id"] == r["settlement_id"]].iloc[0]
        sid2 = ids.settlement_id(r["claim_id"], 2)
        rec = r["paid_date"] + timedelta(days=1)
        appr = rec + timedelta(days=int(rng.integers(0, 2)))
        paid2 = appr + timedelta(days=int(rng.integers(1, 3)))
        row = s1.to_dict()
        row.update(settlement_id=sid2, settlement_status="PAID", approved_date=appr, paid_date=paid2)
        new_settlements.append(row)
        actor = ("ADJUSTER", s1["approver_id"]) if pd.notna(s1["approver_id"]) else ("SYSTEM", None)
        ev.add("SETTLEMENT", sid2, "SETTLEMENT_RECOMMENDED", None, "RECOMMENDED", rec, 8)
        ev.add("SETTLEMENT", sid2, "SETTLEMENT_APPROVED", "RECOMMENDED", "APPROVED", appr, 9, *actor)
        ev.add("SETTLEMENT", sid2, "SETTLEMENT_PAID", "APPROVED", "PAID", paid2, 10)
        label(r["claim_id"], "CLAIM_PAID_TWICE", "settlements", "settlement_id",
              f"A second payment ({sid2}) was recorded on {paid2}.")

    t["status_events"] = ev.finish()
    if new_settlements:
        t["settlements"] = (pd.concat([stl, pd.DataFrame(new_settlements)], ignore_index=True)
                            .sort_values("settlement_id").reset_index(drop=True))
    return t, labels


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------
def _natural_label(reason):
    if reason == "COVERED_LIMIT_CAPPED":
        return "AMOUNT_OVER_LIMIT"
    if reason == "FRAUD_REFERRAL":
        return "FRAUD_SUSPECTED"
    if reason in ("MISSING_MANDATORY_DOCUMENT", "DOCUMENTS_OVERDUE"):
        return "INCOMPLETE_EVIDENCE"
    return "NONE"


def build_ground_truth(tables, labels_a, labels_b):
    """One row per claim. Expected decisions come from the rules engine run on the
    final data; the issue label comes from the injection plan (or the rule outcome)."""
    contexts = build_claim_contexts(tables)
    rows = []
    for n, cid in enumerate(tables["claims"]["claim_id"], start=1):
        res = evaluate_claim(contexts[cid])
        if cid in labels_b:
            info = labels_b[cid]
            issue, origin = info["issue_type"], "INJECTED"
            table, field, note = info["injected_table"], info["injected_field"], info["notes"]
        elif cid in labels_a:
            issue, origin = labels_a[cid], "INJECTED"
            table, field, note = LAYER_A_DETAILS[issue]
        else:
            issue = _natural_label(res["reason_code"])
            origin = "NONE" if issue == "NONE" else "NATURAL"
            table = field = None
            note = NATURAL_NOTES.get(issue)
        rows.append({
            "gt_id": ids.ground_truth_id(n), "claim_id": cid, "issue_type": issue,
            "origin": origin, "injected_table": table, "injected_field": field,
            "expected_decision": res["eligibility_decision"],
            "expected_reason_code": res["reason_code"],
            "expected_payable_amount": res["recommended_amount"], "notes": note,
        })
    return pd.DataFrame(rows)


def check_expected_failures(results, ground_truth):
    """After injection, every failing check must be explained by the ground truth."""
    injected = ground_truth[ground_truth["origin"] == "INJECTED"]["issue_type"].value_counts().to_dict()
    problems = []
    for res in results:
        name, bad = res["check"], res["bad_rows"]
        if name in EXPECTED_FAILURES:
            want = sum(injected.get(issue, 0) for issue in EXPECTED_FAILURES[name])
            if bad != want:
                problems.append(f"{name}: expected {want} bad rows, found {bad}")
        elif name in MAY_ALSO_FAIL:
            cap = injected.get(MAY_ALSO_FAIL[name], 0)
            if bad > cap:
                problems.append(f"{name}: at most {cap} bad rows expected, found {bad}")
        elif not res["passed"]:
            problems.append(f"{name}: UNEXPECTED failure ({bad} bad rows)")
    return problems