"""Validation checks. Each check returns {check, passed, bad_rows}."""
import numpy as np
import pandas as pd

from generator.config import CLAIM_TYPES, PRODUCTS, REFERENCE_DATE
from generator.ids import ID_PATTERNS
from generator.reference_data import (
    ALL_EXCLUSIONS, DOCUMENT_TYPES, ITEM_CATEGORIES, REQUIRED_DOCUMENTS,
)

POLICY_STATUSES = ["IN_FORCE", "EXPIRED", "LAPSED", "CANCELLED"]
RISK_TIERS = ["LOW", "MEDIUM", "HIGH"]
SENIORITIES = ["JUNIOR", "SENIOR", "MANAGER"]
DOC_STATUSES = ["REQUESTED", "RECEIVED", "VERIFIED", "REJECTED"]


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

def print_report(results):
    for res in results:
        tag = "PASS" if res["passed"] else "FAIL"
        extra = "" if res["passed"] else f"  ({res['bad_rows']} bad rows)"
        print(f"[{tag}] {res['check']}{extra}")
    failed = sum(not res["passed"] for res in results)
    print(f"\n{len(results) - failed}/{len(results)} checks passed")
    return failed