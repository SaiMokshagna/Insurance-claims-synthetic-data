from datetime import date

DEFAULT_SEED = 20261022

# Fixed "today". Never call date.today() or datetime.now() in the generator.
REFERENCE_DATE = date(2026, 10, 22)
DATASET_YEAR = 2026

DEFAULT_POLICIES = 2000
DEFAULT_CLAIMS = 1000

PRODUCTS = ["AUTO", "HOME", "HLTH", "LIAB"]
CLAIM_TYPES = [
    "AUTO_COLLISION",
    "PROPERTY_DAMAGE",
    "THEFT",
    "MEDICAL",
    "LIABILITY",
]

# --- Master data parameters ---
CUSTOMER_RATIO = 0.6          # customers = 60% of policies, so some hold several
TERM_DAYS = 364               # expiry = effective + 364 days (a 365-day term)
POLICY_WINDOW_START = date(2025, 6, 1)    # earliest policy effective date
POLICY_WINDOW_END = date(2026, 9, 30)     # latest policy effective date
P_CANCELLED = 0.08            # share of policies cancelled mid-term
P_LAPSED = 0.06               # share of policies lapsed mid-term