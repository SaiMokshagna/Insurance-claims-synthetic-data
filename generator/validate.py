"""Validation checks. Each check returns {check, passed, bad_rows}."""
import numpy as np
import pandas as pd
from generator.rules import REASON_CODES

from generator.config import CLAIM_TYPES, PRODUCTS, REFERENCE_DATE
from generator.ids import ID_PATTERNS
from generator.reference_data import (
    ALL_EXCLUSIONS, DOCUMENT_TYPES, ITEM_CATEGORIES, REQUIRED_DOCUMENTS,
)

POLICY_STATUSES = ["IN_FORCE", "EXPIRED", "LAPSED", "CANCELLED"]
RISK_TIERS = ["LOW", "MEDIUM", "HIGH"]
SENIORITIES = ["JUNIOR", "SENIOR", "MANAGER"]
DOC_STATUSES = ["REQUESTED", "RECEIVED", "VERIFIED", "REJECTED"]
CLAIM_TRANSITIONS = {
    None: {"SUBMITTED"}, "SUBMITTED": {"UNDER_REVIEW"},
    "UNDER_REVIEW": {"DOCS_REQUESTED", "ASSESSED"}, "DOCS_REQUESTED": {"UNDER_REVIEW"},
    "ASSESSED": {"APPROVED", "REJECTED", "REFERRED"}, "APPROVED": {"PAID"},
    "PAID": {"CLOSED"}, "REJECTED": {"CLOSED"}, "REFERRED": {"APPROVED", "REJECTED"},
}
SETTLEMENT_TRANSITIONS = {None: {"RECOMMENDED"}, "RECOMMENDED": {"APPROVED", "REJECTED"},
                          "APPROVED": {"PAID", "CANCELLED"}}
DOCUMENT_TRANSITIONS = {None: {"REQUESTED", "RECEIVED"}, "REQUESTED": {"RECEIVED"},
                        "RECEIVED": {"VERIFIED", "REJECTED"}}
POLICY_TRANSITIONS = {None: {"IN_FORCE"}, "IN_FORCE": {"CANCELLED", "LAPSED", "EXPIRED"}}
TRANSITIONS = {"CLAIM": CLAIM_TRANSITIONS, "SETTLEMENT": SETTLEMENT_TRANSITIONS,
               "DOCUMENT": DOCUMENT_TRANSITIONS, "POLICY": POLICY_TRANSITIONS}
ELIGIBILITY_DECISIONS = ["ELIGIBLE", "PARTIALLY_ELIGIBLE", "INELIGIBLE",
                         "PENDING_DOCUMENTS", "REFER_INVESTIGATION"]

def _result(name, bad_count):
    return {"check": name, "passed": int(bad_count) == 0, "bad_rows": int(bad_count)}


def _unique(df, col, table):
    return _result(f"{table}.{col} is unique", df[col].duplicated().sum())


def _pattern(df, col, key, table):
    bad = ~df[col].astype(str).str.match(ID_PATTERNS[key])
    return _result(f"{table}.{col} matches ID format", bad.sum())


def _fk(child, col, parent, pcol, label):
    return _result(f"FK {label}", (~child[col].isin(parent[pcol])).sum())


def _enum(df, col, allowed, table):
    return _result(f"{table}.{col} has allowed values", (~df[col].isin(allowed)).sum())


def validate_master(t):
    c, cov, a = t["customers"], t["coverages"], t["adjusters"]
    p, pc = t["policies"], t["policy_coverages"]
    ref = pd.Timestamp(REFERENCE_DATE)
    r = []

    # --- customers ---
    r += [_unique(c, "customer_id", "customers"), _pattern(c, "customer_id", "customer", "customers"),
          _unique(c, "email", "customers"), _enum(c, "risk_tier", RISK_TIERS, "customers")]
    dob, since = pd.to_datetime(c["date_of_birth"]), pd.to_datetime(c["customer_since"])
    age = (ref - dob).dt.days / 365.25
    r.append(_result("customers: age between 18 and 85", ((age < 18) | (age > 85)).sum()))
    r.append(_result("customers: customer_since after 18th birthday and not in future",
                     (((since - dob).dt.days < 18 * 365) | (since > ref)).sum()))

    # --- coverages ---
    r += [_unique(cov, "coverage_id", "coverages"), _pattern(cov, "coverage_id", "coverage", "coverages"),
          _enum(cov, "product_code", PRODUCTS, "coverages"), _enum(cov, "coverage_type", CLAIM_TYPES, "coverages")]
    r.append(_result("coverages: default_deductible < default_limit",
                     (cov["default_deductible"] >= cov["default_limit"]).sum()))

    # --- adjusters ---
    r += [_unique(a, "adjuster_id", "adjusters"), _pattern(a, "adjuster_id", "adjuster", "adjusters"),
          _enum(a, "seniority", SENIORITIES, "adjusters"), _enum(a, "specialty", CLAIM_TYPES, "adjusters")]
    auth = a.groupby("seniority")["approval_authority"].agg(["min", "max"])
    ordered = (auth.loc["JUNIOR", "max"] < auth.loc["SENIOR", "min"]
               and auth.loc["SENIOR", "max"] < auth.loc["MANAGER", "min"])
    r.append(_result("adjusters: authority JUNIOR < SENIOR < MANAGER", 0 if ordered else 1))
    managers = set(a[(a["seniority"] == "MANAGER") & a["is_active"]]["specialty"])
    r.append(_result("adjusters: active manager exists for every claim type", len(set(CLAIM_TYPES) - managers)))

    # --- policies ---
    r += [_unique(p, "policy_id", "policies"), _pattern(p, "policy_id", "policy", "policies"),
          _fk(p, "customer_id", c, "customer_id", "policies.customer_id -> customers"),
          _enum(p, "product_code", PRODUCTS, "policies"), _enum(p, "status", POLICY_STATUSES, "policies")]
    r.append(_result("policies: product in policy_id equals product_code",
                     (p["policy_id"].str.split("-").str[1] != p["product_code"]).sum()))
    eff, exp = pd.to_datetime(p["effective_date"]), pd.to_datetime(p["expiry_date"])
    can, lap = pd.to_datetime(p["cancellation_date"]), pd.to_datetime(p["lapse_date"])
    r.append(_result("policies: effective_date < expiry_date", (eff >= exp).sum()))
    r.append(_result("policies: cancellation_date set iff CANCELLED",
                     ((p["status"] == "CANCELLED") != can.notna()).sum()))
    r.append(_result("policies: lapse_date set iff LAPSED",
                     ((p["status"] == "LAPSED") != lap.notna()).sum()))
    r.append(_result("policies: cancellation/lapse inside policy term",
                     ((can.notna() & ((can < eff) | (can > exp))) | (lap.notna() & ((lap < eff) | (lap > exp)))).sum()))
    expected = np.where(can.notna(), "CANCELLED", np.where(lap.notna(), "LAPSED",
                        np.where(exp < ref, "EXPIRED", "IN_FORCE")))
    r.append(_result("policies: status matches independent re-derivation", (p["status"].values != expected).sum()))
    m = p.merge(c[["customer_id", "customer_since"]], on="customer_id")
    r.append(_result("policies: effective_date not before customer_since",
                     (pd.to_datetime(m["effective_date"]) < pd.to_datetime(m["customer_since"])).sum()))

    # --- policy_coverages (bridge) ---
    r += [_unique(pc, "policy_coverage_id", "policy_coverages"),
          _pattern(pc, "policy_coverage_id", "policy_coverage", "policy_coverages"),
          _fk(pc, "policy_id", p, "policy_id", "policy_coverages.policy_id -> policies"),
          _fk(pc, "coverage_id", cov, "coverage_id", "policy_coverages.coverage_id -> coverages")]
    r.append(_result("policy_coverages: (policy_id, coverage_id) pair is unique",
                     pc.duplicated(["policy_id", "coverage_id"]).sum()))
    r.append(_result("policy_coverages: deductible < coverage_limit", (pc["deductible"] >= pc["coverage_limit"]).sum()))
    bad_excl = pc["exclusions"].fillna("").apply(
        lambda s: any(code not in ALL_EXCLUSIONS for code in s.split("|") if code))
    r.append(_result("policy_coverages: exclusion codes are allowed", bad_excl.sum()))
    pm = (pc.merge(p[["policy_id", "product_code", "effective_date", "expiry_date"]],
                   on="policy_id", suffixes=("", "_policy"))
            .merge(cov[["coverage_id", "product_code"]], on="coverage_id",
                   suffixes=("_policy", "_coverage")))
    r.append(_result("policy_coverages: coverage product matches policy product",
                     (pm["product_code_policy"] != pm["product_code_coverage"]).sum()))
    r.append(_result("policy_coverages: dates inside policy term",
                     ((pd.to_datetime(pm["effective_date"]) < pd.to_datetime(pm["effective_date_policy"])) |
                      (pd.to_datetime(pm["expiry_date"]) > pd.to_datetime(pm["expiry_date_policy"]))).sum()))
    return r

def validate_transactions(t):
    p, cov, pc = t["policies"], t["coverages"], t["policy_coverages"]
    inc, clm, itm, doc = t["incidents"], t["claims"], t["claim_items"], t["documents"]
    ref = pd.Timestamp(REFERENCE_DATE)
    r = []

    # --- incidents ---
    r += [_unique(inc, "incident_id", "incidents"),
          _pattern(inc, "incident_id", "incident", "incidents"),
          _fk(inc, "policy_id", p, "policy_id", "incidents.policy_id -> policies"),
          _enum(inc, "incident_type", CLAIM_TYPES, "incidents")]
    im = inc.merge(p[["policy_id", "effective_date", "expiry_date",
                      "cancellation_date", "lapse_date"]], on="policy_id")
    idate, eff = pd.to_datetime(im["incident_date"]), pd.to_datetime(im["effective_date"])
    end = pd.concat([pd.to_datetime(im["expiry_date"]), pd.to_datetime(im["cancellation_date"]),
                     pd.to_datetime(im["lapse_date"])], axis=1).min(axis=1)
    r.append(_result("incidents: incident_date inside policy coverage period",
                     ((idate < eff) | (idate > end)).sum()))
    r.append(_result("incidents: incident_date not in the future", (idate > ref).sum()))

    # --- claims ---
    r += [_unique(clm, "claim_id", "claims"), _pattern(clm, "claim_id", "claim", "claims"),
          _fk(clm, "policy_id", p, "policy_id", "claims.policy_id -> policies"),
          _fk(clm, "incident_id", inc, "incident_id", "claims.incident_id -> incidents"),
          _fk(clm, "coverage_id", cov, "coverage_id", "claims.coverage_id -> coverages")]
    pc_pairs = set(zip(pc["policy_id"], pc["coverage_id"]))
    r.append(_result("claims: coverage is attached to the claim's policy",
                     sum(pair not in pc_pairs for pair in zip(clm["policy_id"], clm["coverage_id"]))))
    cm = (clm.merge(inc[["incident_id", "policy_id", "incident_type", "incident_date",
                         "exclusion_triggered"]], on="incident_id", suffixes=("", "_inc"))
             .merge(cov[["coverage_id", "coverage_type"]], on="coverage_id"))
    r.append(_result("claims: incident belongs to the same policy",
                     (cm["policy_id"] != cm["policy_id_inc"]).sum()))
    r.append(_result("claims: claim_type equals incident_type",
                     (cm["claim_type"] != cm["incident_type"]).sum()))
    r.append(_result("claims: claim_type equals coverage_type",
                     (cm["claim_type"] != cm["coverage_type"]).sum()))
    sub, inc_d = pd.to_datetime(cm["submitted_date"]), pd.to_datetime(cm["incident_date"])
    r.append(_result("claims: submitted_date >= incident_date and <= reference date",
                     ((sub < inc_d) | (sub > ref)).sum()))
    r.append(_result("claims: reporting_delay_days = submitted - incident",
                     (cm["reporting_delay_days"] != (sub - inc_d).dt.days).sum()))
    sums = itm.groupby("claim_id")["claimed_amount"].sum()
    item_total = clm["claim_id"].map(sums)
    r.append(_result("claims: claimed_amount equals sum of its items",
                     (((clm["claimed_amount"] - item_total).abs() > 0.005) | item_total.isna()).sum()))
    em = cm[cm["exclusion_triggered"].notna()].merge(
        pc[["policy_id", "coverage_id", "exclusions"]], on=["policy_id", "coverage_id"])
    r.append(_result("incidents: triggered exclusion is one the coverage actually has",
                     sum(ex not in exs.split("|")
                         for ex, exs in zip(em["exclusion_triggered"], em["exclusions"]))))
    cust = p.set_index("policy_id")["customer_id"]
    cc = clm[["claim_id", "policy_id", "submitted_date"]].copy()
    cc["customer_id"] = cc["policy_id"].map(cust)
    cc["submitted_date"] = pd.to_datetime(cc["submitted_date"])
    pairs = cc.merge(cc, on="customer_id", suffixes=("", "_prev"))
    earlier = pairs[(pairs["claim_id_prev"] < pairs["claim_id"]) &
                    ((pairs["submitted_date"] - pairs["submitted_date_prev"]).dt.days <= 365)]
    expected = earlier.groupby("claim_id").size().reindex(clm["claim_id"]).fillna(0).astype(int).values
    r.append(_result("claims: prior_claims_12m matches independent recount",
                     (clm["prior_claims_12m"].values != expected).sum()))

    # --- claim_items ---
    r += [_unique(itm, "claim_item_id", "claim_items"),
          _pattern(itm, "claim_item_id", "claim_item", "claim_items"),
          _fk(itm, "claim_id", clm, "claim_id", "claim_items.claim_id -> claims")]
    r.append(_result("claim_items: claimed_amount > 0", (itm["claimed_amount"] <= 0).sum()))
    r.append(_result("claims: every claim has at least one item",
                     len(set(clm["claim_id"]) - set(itm["claim_id"]))))
    ic = itm.merge(clm[["claim_id", "claim_type"]], on="claim_id")
    r.append(_result("claim_items: category allowed for the claim type",
                     sum(c not in ITEM_CATEGORIES[ct] for c, ct in zip(ic["item_category"], ic["claim_type"]))))
    r.append(_result("claim_items: item ID embeds its claim_id",
                     sum(not i.startswith(f"ITM-{c}-") for i, c in zip(itm["claim_item_id"], itm["claim_id"]))))

    # --- documents ---
    r += [_unique(doc, "document_id", "documents"),
          _pattern(doc, "document_id", "document", "documents"),
          _fk(doc, "claim_id", clm, "claim_id", "documents.claim_id -> claims"),
          _enum(doc, "document_type", DOCUMENT_TYPES, "documents"),
          _enum(doc, "status", DOC_STATUSES, "documents")]
    r.append(_result("documents: document ID embeds its claim_id",
                     sum(not i.startswith(f"DOC-{c}-") for i, c in zip(doc["document_id"], doc["claim_id"]))))
    dm = doc.merge(clm[["claim_id", "claim_type", "submitted_date"]], on="claim_id")
    r.append(_result("documents: is_mandatory matches the required-documents rule",
                     sum(bool(m) != (d in REQUIRED_DOCUMENTS[ct]) for m, d, ct in
                         zip(dm["is_mandatory"], dm["document_type"], dm["claim_type"]))))
    got = dm["status"].isin(["RECEIVED", "VERIFIED", "REJECTED"])
    r.append(_result("documents: received_date set iff status is received",
                     (got != dm["received_date"].notna()).sum()))
    r.append(_result("documents: file_name and file_size_kb set iff received",
                     ((got != dm["file_name"].notna()) | (got != dm["file_size_kb"].notna())).sum()))
    d_sub = pd.to_datetime(dm["submitted_date"])
    d_rec, d_req = pd.to_datetime(dm["received_date"]), pd.to_datetime(dm["requested_date"])
    r.append(_result("documents: received_date between submitted_date and reference date",
                     (d_rec.notna() & ((d_rec < d_sub) | (d_rec > ref))).sum()))
    r.append(_result("documents: requested_date between submitted_date and reference date",
                     (d_req.notna() & ((d_req < d_sub) | (d_req > ref))).sum()))
    r.append(_result("documents: REQUESTED rows have a requested_date",
                     ((dm["status"] == "REQUESTED") & d_req.isna()).sum()))
    have = doc[doc["is_mandatory"]].groupby("claim_id")["document_type"].apply(list)
    r.append(_result("documents: each claim has every mandatory document type exactly once",
                     sum(sorted(REQUIRED_DOCUMENTS[ct]) != sorted(have.get(cid, []))
                         for cid, ct in zip(clm["claim_id"], clm["claim_type"]))))
    return r

def validate_workflow(t):
    p, doc, clm, pc = t["policies"], t["documents"], t["claims"], t["policy_coverages"]
    adj, asg, asm = t["adjusters"], t["claim_assignments"], t["assessments"]
    rsv, stl, ev = t["reserves"], t["settlements"], t["status_events"]
    ref = pd.Timestamp(REFERENCE_DATE)
    r = []

    def days(series):
        return pd.to_datetime(series)

    # --- claim_assignments ---
    r += [_unique(asg, "assignment_id", "claim_assignments"),
          _pattern(asg, "assignment_id", "assignment", "claim_assignments"),
          _fk(asg, "claim_id", clm, "claim_id", "claim_assignments.claim_id -> claims"),
          _fk(asg, "adjuster_id", adj, "adjuster_id", "claim_assignments.adjuster_id -> adjusters"),
          _enum(asg, "assignment_role", ["PRIMARY", "REVIEWER"], "claim_assignments")]
    am = (asg.merge(clm[["claim_id", "claim_type", "submitted_date"]], on="claim_id")
             .merge(adj[["adjuster_id", "specialty", "is_active"]], on="adjuster_id"))
    r.append(_result("claim_assignments: adjuster is active", (~am["is_active"].astype(bool)).sum()))
    r.append(_result("claim_assignments: adjuster specialty matches claim type",
                     (am["specialty"] != am["claim_type"]).sum()))
    r.append(_result("claim_assignments: assigned_date between submitted_date and reference date",
                     ((days(am["assigned_date"]) < days(am["submitted_date"])) |
                      (days(am["assigned_date"]) > ref)).sum()))
    primaries = asg[asg["assignment_role"] == "PRIMARY"].groupby("claim_id").size()
    r.append(_result("claim_assignments: exactly one PRIMARY per assigned claim",
                     int((primaries != 1).sum()) + len(set(asg["claim_id"]) - set(primaries.index))))
    rev = (asg[asg["assignment_role"] == "REVIEWER"]
           .merge(asg[asg["assignment_role"] == "PRIMARY"][["claim_id", "adjuster_id"]],
                  on="claim_id", suffixes=("", "_primary")))
    r.append(_result("claim_assignments: reviewer differs from primary adjuster",
                     (rev["adjuster_id"] == rev["adjuster_id_primary"]).sum()))

    # --- assessments ---
    r += [_unique(asm, "assessment_id", "assessments"),
          _pattern(asm, "assessment_id", "assessment", "assessments"),
          _fk(asm, "claim_id", clm, "claim_id", "assessments.claim_id -> claims"),
          _fk(asm, "adjuster_id", adj, "adjuster_id", "assessments.adjuster_id -> adjusters"),
          _enum(asm, "eligibility_decision", ELIGIBILITY_DECISIONS, "assessments"),
          _enum(asm, "reason_code", REASON_CODES, "assessments")]
    r.append(_result("assessments: fraud_risk_score between 0 and 100",
                     ((asm["fraud_risk_score"] < 0) | (asm["fraud_risk_score"] > 100)).sum()))
    r.append(_result("assessments: every decision has a reason_text",
                     (asm["reason_text"].fillna("").str.len() == 0).sum()))
    r.append(_result("assessments: at most one per claim (baseline)", asm.duplicated("claim_id").sum()))
    a2 = asm.merge(clm[["claim_id", "claimed_amount", "submitted_date"]], on="claim_id")
    r.append(_result("assessments: eligible_amount <= claimed_amount",
                     (a2["eligible_amount"] > a2["claimed_amount"] + 0.005).sum()))
    r.append(_result("assessments: assessed_date between submitted_date and reference date",
                     ((days(a2["assessed_date"]) < days(a2["submitted_date"])) |
                      (days(a2["assessed_date"]) > ref)).sum()))
    pairs = set(zip(asg["claim_id"], asg["adjuster_id"]))
    r.append(_result("assessments: assessing adjuster is assigned to the claim",
                     sum((c, a) not in pairs for c, a in zip(asm["claim_id"], asm["adjuster_id"]))))

    # --- reserves ---
    r += [_unique(rsv, "reserve_id", "reserves"), _pattern(rsv, "reserve_id", "reserve", "reserves"),
          _fk(rsv, "claim_id", clm, "claim_id", "reserves.claim_id -> claims"),
          _fk(rsv, "assessment_id", asm, "assessment_id", "reserves.assessment_id -> assessments"),
          _enum(rsv, "reserve_type", ["INITIAL", "REVISED"], "reserves")]
    rm = rsv.merge(asm[["assessment_id", "claim_id", "assessed_date", "eligible_amount"]],
                   on="assessment_id", suffixes=("", "_asm"))
    r.append(_result("reserves: assessment belongs to the same claim", (rm["claim_id"] != rm["claim_id_asm"]).sum()))
    rm = (rm.merge(clm[["claim_id", "policy_id", "coverage_id"]], on="claim_id")
            .merge(pc[["policy_id", "coverage_id", "coverage_limit", "deductible"]],
                   on=["policy_id", "coverage_id"]))
    init = rm[rm["reserve_type"] == "INITIAL"]
    exp_res = np.minimum(np.maximum(init["eligible_amount"] - init["deductible"], 0),
                         init["coverage_limit"]).round(2)
    r.append(_result("reserves: INITIAL equals min(max(eligible - deductible, 0), limit)",
                     ((init["reserve_amount"] - exp_res).abs() > 0.005).sum()))
    r.append(_result("reserves: exactly one INITIAL per assessment",
                     len(set(asm["assessment_id"]) ^ set(init["assessment_id"])) + int(init.duplicated("assessment_id").sum())))
    r.append(_result("reserves: REVISED rows are released (0.00)",
                     (rm[rm["reserve_type"] == "REVISED"]["reserve_amount"] != 0).sum()))
    r.append(_result("reserves: supersedes_reserve_id set iff REVISED",
                     ((rm["reserve_type"] == "REVISED") != rm["supersedes_reserve_id"].notna()).sum()))
    r.append(_result("reserves: supersedes_reserve_id points to an existing reserve",
                     (rm["supersedes_reserve_id"].notna() & ~rm["supersedes_reserve_id"].isin(rsv["reserve_id"])).sum()))
    r.append(_result("reserves: effective_date >= assessed_date",
                     (days(rm["effective_date"]) < days(rm["assessed_date"])).sum()))
    r.append(_result("reserves: 0 <= reserve_amount <= coverage_limit",
                     ((rm["reserve_amount"] < 0) | (rm["reserve_amount"] > rm["coverage_limit"])).sum()))

    # --- settlements ---
    r += [_unique(stl, "settlement_id", "settlements"),
          _pattern(stl, "settlement_id", "settlement", "settlements"),
          _fk(stl, "claim_id", clm, "claim_id", "settlements.claim_id -> claims"),
          _fk(stl, "assessment_id", asm, "assessment_id", "settlements.assessment_id -> assessments"),
          _enum(stl, "settlement_status", ["RECOMMENDED", "APPROVED", "REJECTED", "PAID", "CANCELLED"], "settlements"),
          _enum(stl, "routing_decision", ["AUTO_APPROVE", "SENIOR_REVIEW", "INVESTIGATION", "REJECT"], "settlements")]
    r.append(_result("settlements: at most one per claim (baseline)", stl.duplicated("claim_id").sum()))
    sm = stl.merge(asm[["assessment_id", "claim_id", "eligibility_decision", "eligible_amount"]],
                   on="assessment_id", suffixes=("", "_asm"))
    r.append(_result("settlements: assessment belongs to the same claim", (sm["claim_id"] != sm["claim_id_asm"]).sum()))
    sm = (sm.merge(clm[["claim_id", "policy_id", "coverage_id"]], on="claim_id")
            .merge(pc[["policy_id", "coverage_id", "coverage_limit", "deductible"]],
                   on=["policy_id", "coverage_id"]))
    payable = sm["eligibility_decision"].isin(["ELIGIBLE", "PARTIALLY_ELIGIBLE"])
    exp_rec = np.where(payable, np.minimum(np.maximum(sm["eligible_amount"] - sm["deductible"], 0),
                                           sm["coverage_limit"]), 0.0)
    r.append(_result("settlements: recommended_amount follows deductible and limit rules",
                     ((sm["recommended_amount"] - exp_rec).abs() > 0.005).sum()))
    r.append(_result("settlements: limit_applied equals the coverage limit",
                     ((sm["limit_applied"] - sm["coverage_limit"]).abs() > 0.005).sum()))
    r.append(_result("settlements: recommended and approved amounts do not exceed the limit",
                     ((sm["recommended_amount"] > sm["limit_applied"] + 0.005) |
                      (sm["approved_amount"].fillna(0) > sm["limit_applied"] + 0.005)).sum()))
    approved = stl["settlement_status"].isin(["APPROVED", "PAID"])
    r.append(_result("settlements: approved_amount and approved_date set iff APPROVED or PAID",
                     ((approved != stl["approved_amount"].notna()) | (approved != stl["approved_date"].notna())).sum()))
    r.append(_result("settlements: approved_amount equals recommended_amount",
                     (approved & ((stl["approved_amount"] - stl["recommended_amount"]).abs() > 0.005)).sum()))
    r.append(_result("settlements: paid_date set iff PAID",
                     ((stl["settlement_status"] == "PAID") != stl["paid_date"].notna()).sum()))
    r.append(_result("settlements: paid_date >= approved_date",
                     (days(stl["paid_date"]) < days(stl["approved_date"])).sum()))
    sa = stl.merge(adj[["adjuster_id", "approval_authority"]], left_on="approver_id", right_on="adjuster_id")
    r.append(_result("settlements: approver authority covers approved_amount",
                     (sa["approval_authority"] < sa["approved_amount"]).sum()))

    # --- status_events ---
    r += [_unique(ev, "event_id", "status_events"), _pattern(ev, "event_id", "event", "status_events"),
          _enum(ev, "entity_type", list(TRANSITIONS), "status_events")]
    valid_ids = {"POLICY": set(p["policy_id"]), "CLAIM": set(clm["claim_id"]),
                 "DOCUMENT": set(doc["document_id"]), "SETTLEMENT": set(stl["settlement_id"])}
    r.append(_result("status_events: entity_id exists in its table",
                     sum(eid not in valid_ids.get(et, set())
                         for et, eid in zip(ev["entity_type"], ev["entity_id"]))))
    r.append(_result("status_events: event date not after reference date",
                     (days(ev["event_ts"].str[:10]) > ref).sum()))

    last, bad_chain, bad_transition = {}, 0, 0
    for row in ev.sort_values("event_id").itertuples(index=False):
        key = (row.entity_type, row.entity_id)
        prev = last.get(key)
        from_status = None if pd.isna(row.from_status) else row.from_status
        bad_chain += from_status != prev
        bad_transition += row.to_status not in TRANSITIONS[row.entity_type].get(prev, set())
        last[key] = row.to_status
    r.append(_result("status_events: from_status equals the entity's previous to_status", bad_chain))
    r.append(_result("status_events: every transition is legal for its lifecycle", bad_transition))
    for et, df, id_col, status_col in [("CLAIM", clm, "claim_id", "current_status"),
                                       ("POLICY", p, "policy_id", "status"),
                                       ("DOCUMENT", doc, "document_id", "status"),
                                       ("SETTLEMENT", stl, "settlement_id", "settlement_status")]:
        r.append(_result(f"status_events: last {et.lower()} event equals the {et.lower()}'s stored status",
                         sum(last.get((et, i)) != s for i, s in zip(df[id_col], df[status_col]))))
    return r

def print_report(results):
    for res in results:
        tag = "PASS" if res["passed"] else "FAIL"
        extra = "" if res["passed"] else f"  ({res['bad_rows']} bad rows)"
        print(f"[{tag}] {res['check']}{extra}")
    failed = sum(not res["passed"] for res in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return failed

def validate_rules(t):
    """Cross-entity rule checks. All pass on clean data; Layer B defects make some fail."""
    p, clm, doc = t["policies"], t["claims"], t["documents"]
    stl, asm, rsv = t["settlements"], t["assessments"], t["reserves"]
    r = []

    cm = clm.merge(p[["policy_id", "effective_date"]], on="policy_id")
    r.append(_result("claims: submitted_date on or after policy effective_date",
                     (pd.to_datetime(cm["submitted_date"]) < pd.to_datetime(cm["effective_date"])).sum()))
    paid = stl[stl["settlement_status"] == "PAID"]
    r.append(_result("rules: every claim is paid at most once",
                     (paid.groupby("claim_id").size() > 1).sum()))
    mandatory = doc[doc["is_mandatory"].astype(bool)]
    not_received = mandatory[~mandatory["status"].isin(["RECEIVED", "VERIFIED"])]
    r.append(_result("rules: paid claims have every mandatory document",
                     len(set(paid["claim_id"]) & set(not_received["claim_id"]))))

    # --- added in M7 ---
    order = pd.to_datetime(clm.sort_values("claim_id")["submitted_date"])
    r.append(_result("claims: claim_id order follows submitted_date", (order.diff().dt.days < 0).sum()))
    sm = stl.merge(asm[["assessment_id", "assessed_date"]], on="assessment_id")
    r.append(_result("settlements: approved_date on or after assessed_date",
                     (pd.to_datetime(sm["approved_date"]) < pd.to_datetime(sm["assessed_date"])).sum()))
    closed = set(clm.loc[clm["current_status"] == "CLOSED", "claim_id"])
    settled = set(stl.loc[stl["settlement_status"].isin(["PAID", "REJECTED"]), "claim_id"])
    r.append(_result("rules: closed claims have a PAID or REJECTED settlement", len(closed - settled)))
    released = set(rsv.loc[rsv["reserve_type"] == "REVISED", "claim_id"])
    r.append(_result("rules: paid claims have their reserve released", len(set(paid["claim_id"]) - released)))
    return r


def validate_all(t):
    return validate_master(t) + validate_transactions(t) + validate_workflow(t) + validate_rules(t)


def print_report(results, verbose=False):
    failed = [res for res in results if not res["passed"]]
    for res in (results if verbose else failed):
        tag = "PASS" if res["passed"] else "FAIL"
        extra = "" if res["passed"] else f"  ({res['bad_rows']} bad rows)"
        print(f"[{tag}] {res['check']}{extra}")
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    return len(failed)