import re
from generator import ids


def test_example_ids_match_assignment_format():
    assert ids.customer_id(1) == "CUS-000001"
    assert ids.policy_id("AUTO", 1) == "POL-AUTO-2026-000001"
    assert ids.claim_id(1) == "CLM-2026-000001"
    assert ids.document_id("CLM-2026-000001", 1) == "DOC-CLM-2026-000001-001"
    assert ids.assignment_id("CLM-2026-000001", 1) == "ASN-CLM-2026-000001-001"
    assert ids.settlement_id("CLM-2026-000001", 1) == "SET-CLM-2026-000001-001"


def test_builders_match_their_patterns():
    assert re.match(ids.ID_PATTERNS["policy"], ids.policy_id("HLTH", 1999))
    assert re.match(ids.ID_PATTERNS["policy_coverage"],
                    ids.policy_coverage_id(ids.policy_id("HOME", 7), 2))
    assert re.match(ids.ID_PATTERNS["coverage"], ids.coverage_id("LIAB", 1))