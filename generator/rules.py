"""Business rules. Pure functions: same inputs always give the same outputs."""
from generator.config import (
    AUTO_APPROVE_MAX, DOC_DEADLINE_DAYS, EARLY_CLAIM_DAYS,
    FRAUD_REFERRAL_SCORE, REVIEW_SCORE,
)
from generator.reference_data import APPROVAL_AUTHORITY

def derive_policy_status(cancellation_date, lapse_date, expiry_date, reference_date):
    """Policy status as of the reference date (data dictionary, section 5.1)."""
    if cancellation_date is not None and cancellation_date <= reference_date:
        return "CANCELLED"
    if lapse_date is not None and lapse_date <= reference_date:
        return "LAPSED"
    if expiry_date < reference_date:
        return "EXPIRED"
    return "IN_FORCE"

def derive_prior_claims(claims, policies):
    """For each claim, count the same customer's earlier claims in the prior
    365 days. `claims` must be in submission-time order (claim_id order)."""
    customer_of = policies.set_index("policy_id")["customer_id"]
    history, counts = {}, []
    for policy_id, submitted in zip(claims["policy_id"], claims["submitted_date"]):
        past = history.setdefault(customer_of[policy_id], [])
        counts.append(sum(1 for d in past if (submitted - d).days <= 365))
        past.append(submitted)
    return counts

# ---------------------------------------------------------------------------
# Reason codes: every decision carries one of these (requirement R14)
# ---------------------------------------------------------------------------
REASON_TEXT = {
    "COVERED_OK": "Incident within coverage period, documents complete, no exclusion or duplicate; claim is payable.",
    "COVERED_LIMIT_CAPPED": "Claim is covered but the payout is capped at the coverage limit.",
    "INCIDENT_BEFORE_POLICY_START": "Incident occurred before the policy effective date.",
    "INCIDENT_AFTER_COVERAGE_END": "Incident occurred after the policy expired or lapsed.",
    "POLICY_CANCELLED_BEFORE_INCIDENT": "Policy was cancelled before the incident date.",
    "CLAIM_BEFORE_POLICY_START": "Claim was submitted before the policy effective date.",
    "EXCLUDED_PERIL": "The incident involves an excluded peril.",
    "MISSING_MANDATORY_DOCUMENT": "A mandatory document has not been received yet.",
    "DOCUMENTS_OVERDUE": "A requested mandatory document was not received within the deadline.",
    "DUPLICATE_CLAIM": "The same incident has already been claimed.",
    "DUPLICATE_INCIDENT": "An incident with the same policy, type and date is already recorded.",
    "FRAUD_REFERRAL": "Fraud risk score is above the referral threshold.",
    "BELOW_DEDUCTIBLE": "Claimed amount does not exceed the deductible, so nothing is payable.",
    "PAID_TWICE": "More than one payment was made on this claim.",
}
REASON_CODES = list(REASON_TEXT)


# ---------------------------------------------------------------------------
# Coverage rules
# ---------------------------------------------------------------------------
def coverage_end_date(expiry, cancellation, lapse):
    """Coverage ends on the earliest of expiry, cancellation and lapse dates."""
    return min(d for d in (expiry, cancellation, lapse) if d is not None)


def incident_in_period(incident_date, effective, expiry, cancellation, lapse):
    """True if effective <= incident <= coverage end (end date itself is covered)."""
    return effective <= incident_date <= coverage_end_date(expiry, cancellation, lapse)


def check_coverage(incident_date, submitted_date, effective, expiry, cancellation, lapse):
    """Return COVERED_OK or the reason code explaining why coverage fails."""
    if submitted_date < effective:
        return "CLAIM_BEFORE_POLICY_START"
    if incident_date < effective:
        return "INCIDENT_BEFORE_POLICY_START"
    if cancellation is not None and incident_date > cancellation:
        return "POLICY_CANCELLED_BEFORE_INCIDENT"
    if (lapse is not None and incident_date > lapse) or incident_date > expiry:
        return "INCIDENT_AFTER_COVERAGE_END"
    return "COVERED_OK"


# ---------------------------------------------------------------------------
# Document rules
# ---------------------------------------------------------------------------
def document_state(documents, reference_date, deadline_days=DOC_DEADLINE_DAYS):
    """COMPLETE, PENDING (outstanding but within the deadline) or OVERDUE."""
    outstanding = [d for d in documents
                   if d["is_mandatory"] and d["status"] in ("REQUESTED", "REJECTED")]
    if not outstanding:
        return "COMPLETE"
    for d in outstanding:
        requested = d.get("requested_date")
        if requested is not None and (reference_date - requested).days > deadline_days:
            return "OVERDUE"
    return "PENDING"


# ---------------------------------------------------------------------------
# Duplicate rule
# ---------------------------------------------------------------------------
def find_duplicates(claims, incidents):
    """Return {claim_id: reason} for each claim duplicating an EARLIER claim.

    Key = policy + incident type + incident date (location is ignored).
    Same incident_id as the original -> DUPLICATE_CLAIM; a different
    incident_id -> DUPLICATE_INCIDENT. The earliest claim is the original
    and is never flagged."""
    df = (claims[["claim_id", "policy_id", "incident_id"]]
          .merge(incidents[["incident_id", "incident_type", "incident_date"]], on="incident_id")
          .sort_values("claim_id"))
    first_seen, flagged = {}, {}
    for row in df.itertuples(index=False):
        key = (row.policy_id, row.incident_type, row.incident_date)
        if key in first_seen:
            flagged[row.claim_id] = ("DUPLICATE_CLAIM" if row.incident_id == first_seen[key]
                                     else "DUPLICATE_INCIDENT")
        else:
            first_seen[key] = row.incident_id
    return flagged


# ---------------------------------------------------------------------------
# Fraud score
# ---------------------------------------------------------------------------
def fraud_risk_score(reporting_delay_days, prior_claims_12m, claimed_amount,
                     coverage_limit, days_since_policy_start, customer_risk_tier):
    """Weighted indicator score from 0 to 100 (see the table in the README)."""
    score = 0
    if reporting_delay_days > 30:
        score += 20
    elif reporting_delay_days > 14:
        score += 10
    if prior_claims_12m >= 3:
        score += 25
    elif prior_claims_12m == 2:
        score += 15
    elif prior_claims_12m == 1:
        score += 5
    ratio = claimed_amount / coverage_limit
    if ratio > 1.0:
        score += 15
    elif ratio >= 0.8:
        score += 10
    if days_since_policy_start <= EARLY_CLAIM_DAYS:
        score += 15
    if customer_risk_tier == "HIGH":
        score += 10
    return min(score, 100)


# ---------------------------------------------------------------------------
# Money rules
# ---------------------------------------------------------------------------
def calculate_payout(eligible_amount, deductible, coverage_limit):
    """payout = min(max(0, eligible - deductible), limit)."""
    deductible_applied = min(deductible, eligible_amount)
    net = eligible_amount - deductible_applied
    return {
        "deductible_applied": round(deductible_applied, 2),
        "limit_applied": round(coverage_limit, 2),
        "payout": round(min(net, coverage_limit), 2),
        "capped": net > coverage_limit,
    }


def required_seniority(amount):
    """Lowest adjuster seniority whose approval authority covers the amount."""
    if amount <= APPROVAL_AUTHORITY["JUNIOR"]:
        return "JUNIOR"
    if amount <= APPROVAL_AUTHORITY["SENIOR"]:
        return "SENIOR"
    return "MANAGER"


def route_settlement(decision, recommended_amount, fraud_score):
    if decision == "INELIGIBLE":
        return "REJECT"
    if decision == "REFER_INVESTIGATION":
        return "INVESTIGATION"
    if decision == "PENDING_DOCUMENTS":
        return None                      # nothing to settle yet
    if recommended_amount > AUTO_APPROVE_MAX or fraud_score >= REVIEW_SCORE:
        return "SENIOR_REVIEW"
    return "AUTO_APPROVE"


def approver_level(routing, recommended_amount):
    """Minimum seniority of the person who must approve (None = no adjuster needed)."""
    if routing == "SENIOR_REVIEW":
        level = required_seniority(recommended_amount)
        return "SENIOR" if level == "JUNIOR" else level
    if routing == "INVESTIGATION":
        return "SENIOR"
    return None


# ---------------------------------------------------------------------------
# The full evaluation of one claim
# ---------------------------------------------------------------------------
def evaluate_claim(ctx):
    """Apply every rule to one claim context (a plain dict) and explain why."""
    claimed, limit, ded = ctx["claimed_amount"], ctx["coverage_limit"], ctx["deductible"]
    coverage_code = check_coverage(
        ctx["incident_date"], ctx["submitted_date"], ctx["policy_effective"],
        ctx["policy_expiry"], ctx["policy_cancellation"], ctx["policy_lapse"])
    doc_state = document_state(ctx["documents"], ctx["reference_date"])
    dup = ctx.get("duplicate_reason")
    score = fraud_risk_score(
        ctx["reporting_delay_days"], ctx["prior_claims_12m"], claimed, limit,
        (ctx["incident_date"] - ctx["policy_effective"]).days, ctx["customer_risk_tier"])

    if coverage_code != "COVERED_OK":
        decision, reason = "INELIGIBLE", coverage_code
    elif ctx["exclusion_triggered"]:
        decision, reason = "INELIGIBLE", "EXCLUDED_PERIL"
    elif dup:
        decision, reason = "INELIGIBLE", dup
    elif doc_state == "OVERDUE":
        decision, reason = "INELIGIBLE", "DOCUMENTS_OVERDUE"
    elif doc_state == "PENDING":
        decision, reason = "PENDING_DOCUMENTS", "MISSING_MANDATORY_DOCUMENT"
    elif score >= FRAUD_REFERRAL_SCORE:
        decision, reason = "REFER_INVESTIGATION", "FRAUD_REFERRAL"
    elif claimed <= ded:
        decision, reason = "INELIGIBLE", "BELOW_DEDUCTIBLE"
    elif claimed - ded > limit:
        decision, reason = "PARTIALLY_ELIGIBLE", "COVERED_LIMIT_CAPPED"
    else:
        decision, reason = "ELIGIBLE", "COVERED_OK"

    reason_text = REASON_TEXT[reason]
    if reason == "EXCLUDED_PERIL":
        reason_text += f" ({ctx['exclusion_triggered']})"

    eligible = 0.0 if decision == "INELIGIBLE" else claimed
    money = calculate_payout(eligible, ded, limit)
    recommended = money["payout"] if decision in ("ELIGIBLE", "PARTIALLY_ELIGIBLE") else 0.0
    routing = route_settlement(decision, recommended, score)

    return {
        "incident_in_coverage_period": incident_in_period(
            ctx["incident_date"], ctx["policy_effective"], ctx["policy_expiry"],
            ctx["policy_cancellation"], ctx["policy_lapse"]),
        "documents_complete": doc_state == "COMPLETE",
        "duplicate_suspected": bool(dup),
        "fraud_risk_score": score,
        "eligibility_decision": decision,
        "reason_code": reason,
        "reason_text": reason_text,
        "eligible_amount": round(eligible, 2),
        "deductible_applied": money["deductible_applied"],
        "limit_applied": money["limit_applied"],
        "reserve_amount": money["payout"],
        "recommended_amount": recommended,
        "routing_decision": routing,
        "approver_level": approver_level(routing, recommended),
    }