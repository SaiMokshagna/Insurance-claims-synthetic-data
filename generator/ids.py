"""ID builders and the regex patterns used to validate them."""
from generator.config import DATASET_YEAR


def customer_id(n): return f"CUS-{n:06d}"
def coverage_id(product, n): return f"COV-{product}-{n:02d}"
def policy_id(product, n): return f"POL-{product}-{DATASET_YEAR}-{n:06d}"
def policy_coverage_id(pol_id, n): return f"PCV-{pol_id}-{n:02d}"
def adjuster_id(n): return f"ADJ-{n:04d}"

# Used in later milestones:
def incident_id(n): return f"INC-{DATASET_YEAR}-{n:06d}"
def claim_id(n): return f"CLM-{DATASET_YEAR}-{n:06d}"
def claim_item_id(clm, n): return f"ITM-{clm}-{n:03d}"
def document_id(clm, n): return f"DOC-{clm}-{n:03d}"
def assignment_id(clm, n): return f"ASN-{clm}-{n:03d}"
def assessment_id(clm, n): return f"ASM-{clm}-{n:03d}"
def reserve_id(clm, n): return f"RSV-{clm}-{n:03d}"
def settlement_id(clm, n): return f"SET-{clm}-{n:03d}"
def event_id(n): return f"EVT-{n:08d}"
def ground_truth_id(n): return f"GT-{n:06d}"


# The year is written as 2026 on purpose: the assignment fixes it.
_P = "(AUTO|HOME|HLTH|LIAB)"
ID_PATTERNS = {
    "customer": r"^CUS-\d{6}$",
    "coverage": rf"^COV-{_P}-\d" + r"{2}$",
    "policy": rf"^POL-{_P}-2026-" + r"\d{6}$",
    "policy_coverage": rf"^PCV-POL-{_P}-2026-" + r"\d{6}-\d{2}$",
    "adjuster": r"^ADJ-\d{4}$",
    "incident": r"^INC-2026-\d{6}$",
    "claim": r"^CLM-2026-\d{6}$",
    "claim_item": r"^ITM-CLM-2026-\d{6}-\d{3}$",
    "document": r"^DOC-CLM-2026-\d{6}-\d{3}$",
    "assignment": r"^ASN-CLM-2026-\d{6}-\d{3}$",
    "assessment": r"^ASM-CLM-2026-\d{6}-\d{3}$",
    "reserve": r"^RSV-CLM-2026-\d{6}-\d{3}$",
    "settlement": r"^SET-CLM-2026-\d{6}-\d{3}$",
    "event": r"^EVT-\d{8}$",
    "ground_truth": r"^GT-\d{6}$",
}