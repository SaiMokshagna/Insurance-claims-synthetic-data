"""Business rules. Pure functions: same inputs always give the same outputs."""


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