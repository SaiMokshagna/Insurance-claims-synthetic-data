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

# --- Transaction parameters ---
CLAIM_PERIOD_START = date(2026, 1, 1)   # earliest incident date (claims are 2026)
P_INCOMPLETE_EVIDENCE = 0.12            # claims with one mandatory doc not on time
P_LATE_RECEIVED = 0.60                  # of those, share that arrive later
P_EXCLUSION_TRIGGERED = 0.04            # incidents involving an excluded peril
P_EXTRA_DOCUMENT = 0.30                 # claims with a non-mandatory extra document
CLAIM_AMOUNT_MEDIAN_FRACTION = 0.22     # median claim = 22% of coverage limit
CLAIM_AMOUNT_SIGMA = 0.9                # spread; gives roughly 5% over the limit

# --- Business rule parameters ---
DOC_DEADLINE_DAYS = 30        # days a requested document may stay outstanding
EARLY_CLAIM_DAYS = 30         # incident this soon after policy start is a fraud indicator
AUTO_APPROVE_MAX = 5000.0     # payouts up to this (and low fraud score) auto-approve
REVIEW_SCORE = 30             # fraud score that forces senior review
FRAUD_REFERRAL_SCORE = 50     # fraud score that triggers investigation