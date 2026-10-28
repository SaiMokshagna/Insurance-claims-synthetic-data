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