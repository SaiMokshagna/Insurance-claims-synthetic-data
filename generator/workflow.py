"""Claim workflow simulation: assignments, assessments, reserves, settlements, events."""
from datetime import timedelta

import pandas as pd

from generator import ids
from generator.config import DOC_DEADLINE_DAYS, REFERENCE_DATE as REF, RULE_VERSION
from generator.context import _clean, build_claim_contexts
from generator.events import EventLog, add_document_events, add_policy_events
from generator.master import pick
from generator.rules import evaluate_claim

RANK = {"JUNIOR": 0, "SENIOR": 1, "MANAGER": 2}


def _days(n):
    return timedelta(days=int(n))


def _record_assessment(out, cid, result, assessed, adjuster_id):
    """Create the assessment and its INITIAL reserve."""
    asm = ids.assessment_id(cid, 1)
    out["assessments"].append({
        "assessment_id": asm, "claim_id": cid, "adjuster_id": adjuster_id,
        "assessed_date": assessed,
        "incident_in_coverage_period": result["incident_in_coverage_period"],
        "documents_complete": result["documents_complete"],
        "duplicate_suspected": result["duplicate_suspected"],
        "fraud_risk_score": result["fraud_risk_score"],
        "eligible_amount": result["eligible_amount"],
        "eligibility_decision": result["eligibility_decision"],
        "reason_code": result["reason_code"],
        "reason_text": result["reason_text"],
        "rule_version": RULE_VERSION,
    })
    out["reserves"].append({
        "reserve_id": ids.reserve_id(cid, 1), "claim_id": cid, "assessment_id": asm,
        "reserve_type": "INITIAL", "reserve_amount": result["reserve_amount"],
        "effective_date": assessed, "supersedes_reserve_id": None,
    })
    return asm


def _simulate_claim(rng, log, claim, result, docs, pool):
    cid, sub = claim["claim_id"], claim["submitted_date"]
    out = {"assignments": [], "assessments": [], "reserves": [], "settlements": []}
    decision, reason, routing = (result["eligibility_decision"], result["reason_code"],
                                 result["routing_decision"])

    # --- Stage 1: submitted -------------------------------------------------
    log.add("CLAIM", cid, "CLAIM_SUBMITTED", "SUBMITTED", sub, "CUSTOMER")

    # --- Stage 2: assigned and under review (the next day) -------------------
    review = sub + _days(1)
    if review > REF:
        return out
    primaries = [a for a in pool if a["seniority"] != "MANAGER"]   # managers approve, not handle
    primary = pick(rng, primaries)
    pid = primary["adjuster_id"]
    out["assignments"].append({
        "assignment_id": ids.assignment_id(cid, 1), "claim_id": cid, "adjuster_id": pid,
        "assignment_role": "PRIMARY", "assigned_date": review, "unassigned_date": None,
    })
    log.add("CLAIM", cid, "REVIEW_STARTED", "UNDER_REVIEW", review, "ADJUSTER", pid)

    # --- Stage 3: documents --------------------------------------------------
    resume = review
    req_docs = [d for d in docs if d["is_mandatory"] and d["requested_date"] is not None]
    if req_docs:
        first_req = min(d["requested_date"] for d in req_docs)
        log.add("CLAIM", cid, "DOCUMENTS_REQUESTED", "DOCS_REQUESTED", first_req, "ADJUSTER", pid)
        outstanding = [d for d in req_docs if d["status"] == "REQUESTED"]

        if decision == "PENDING_DOCUMENTS":      # waiting: assess and hold a reserve, then stop
            _record_assessment(out, cid, result, first_req, pid)
            return out
        if not outstanding:
            resume, why, actor = max(d["received_date"] for d in req_docs), "DOCUMENTS_RECEIVED", ("CUSTOMER", None)
        elif reason == "DOCUMENTS_OVERDUE":
            resume = max(d["requested_date"] for d in outstanding) + _days(DOC_DEADLINE_DAYS + 1)
            why, actor = "DOCUMENTS_OVERDUE", ("SYSTEM", None)
        else:                                    # decided on other grounds, without waiting
            resume, why, actor = first_req + _days(1), "DECIDED_WITHOUT_DOCUMENTS", ("ADJUSTER", pid)
        if resume > REF:
            return out
        log.add("CLAIM", cid, "REVIEW_RESUMED", "UNDER_REVIEW", resume, actor[0], actor[1], why)

    # --- Stage 4: assessment ---------------------------------------------------
    assessed = resume + _days(0 if reason == "DOCUMENTS_OVERDUE" else rng.integers(1, 5))
    if assessed > REF:
        return out
    log.add("CLAIM", cid, "CLAIM_ASSESSED", "ASSESSED", assessed, "ADJUSTER", pid, reason)
    asm = _record_assessment(out, cid, result, assessed, pid)

    sid = ids.settlement_id(cid, 1)
    stl = {
        "settlement_id": sid, "claim_id": cid, "assessment_id": asm, "routing_decision": routing,
        "recommended_amount": result["recommended_amount"],
        "deductible_applied": result["deductible_applied"],
        "limit_applied": result["limit_applied"], "approved_amount": None,
        "settlement_status": "RECOMMENDED", "approver_id": None,
        "approved_date": None, "paid_date": None,
    }
    out["settlements"].append(stl)
    log.add("SETTLEMENT", sid, "SETTLEMENT_RECOMMENDED", "RECOMMENDED", assessed)

    def senior_pool(min_level, amount):
        return [a for a in pool if a["adjuster_id"] != pid and RANK[a["seniority"]] >= RANK[min_level]
                and a["approval_authority"] >= amount]

    # --- Stage 5: outcome, by routing ---------------------------------------
    if routing == "REJECT":
        rejected = assessed + _days(rng.integers(0, 2))
        if rejected <= REF:
            log.add("CLAIM", cid, "CLAIM_REJECTED", "REJECTED", rejected, "ADJUSTER", pid, reason)
            stl["settlement_status"] = "REJECTED"
            log.add("SETTLEMENT", sid, "SETTLEMENT_REJECTED", "REJECTED", rejected, "ADJUSTER", pid)
            closed = rejected + _days(rng.integers(1, 4))
            if closed <= REF:
                log.add("CLAIM", cid, "CLAIM_CLOSED", "CLOSED", closed)

    elif routing == "INVESTIGATION":
        referred = assessed + _days(rng.integers(0, 2))
        if referred <= REF:
            reviewer = pick(rng, senior_pool(result["approver_level"], 0.0))
            out["assignments"].append({
                "assignment_id": ids.assignment_id(cid, 2), "claim_id": cid,
                "adjuster_id": reviewer["adjuster_id"], "assignment_role": "REVIEWER",
                "assigned_date": referred, "unassigned_date": None,
            })
            log.add("CLAIM", cid, "CLAIM_REFERRED", "REFERRED", referred,
                    "ADJUSTER", reviewer["adjuster_id"], reason)

    else:                                        # AUTO_APPROVE or SENIOR_REVIEW
        if routing == "AUTO_APPROVE":
            approver, approved = None, assessed
        else:
            approver = pick(rng, senior_pool(result["approver_level"], result["recommended_amount"]))
            approved = assessed + _days(rng.integers(2, 8))
            out["assignments"].append({
                "assignment_id": ids.assignment_id(cid, 2), "claim_id": cid,
                "adjuster_id": approver["adjuster_id"], "assignment_role": "REVIEWER",
                "assigned_date": assessed, "unassigned_date": None,
            })
        actor = ("ADJUSTER", approver["adjuster_id"]) if approver else ("SYSTEM", None)

        if approved <= REF:
            log.add("CLAIM", cid, "CLAIM_APPROVED", "APPROVED", approved, *actor)
            stl.update(approved_amount=stl["recommended_amount"], settlement_status="APPROVED",
                       approver_id=actor[1], approved_date=approved)
            log.add("SETTLEMENT", sid, "SETTLEMENT_APPROVED", "APPROVED", approved, *actor)

            paid = approved + _days(rng.integers(2, 11))
            if paid <= REF:
                log.add("CLAIM", cid, "CLAIM_PAID", "PAID", paid)
                stl.update(settlement_status="PAID", paid_date=paid)
                log.add("SETTLEMENT", sid, "SETTLEMENT_PAID", "PAID", paid)
                out["reserves"].append({           # release the reserve: a NEW row, history kept
                    "reserve_id": ids.reserve_id(cid, 2), "claim_id": cid, "assessment_id": asm,
                    "reserve_type": "REVISED", "reserve_amount": 0.0, "effective_date": paid,
                    "supersedes_reserve_id": ids.reserve_id(cid, 1),
                })
                closed = paid + _days(rng.integers(1, 4))
                if closed <= REF:
                    log.add("CLAIM", cid, "CLAIM_CLOSED", "CLOSED", closed)
    return out


def generate_workflow(rng, tables):
    claims = tables["claims"]
    contexts = build_claim_contexts(tables)

    docs_by_claim = {}
    for d in tables["documents"].to_dict("records"):
        docs_by_claim.setdefault(d["claim_id"], []).append({
            "is_mandatory": bool(d["is_mandatory"]), "status": d["status"],
            "requested_date": _clean(d["requested_date"]),
            "received_date": _clean(d["received_date"]),
        })
    pools = {}
    for a in tables["adjusters"].to_dict("records"):
        if a["is_active"]:
            pools.setdefault(a["specialty"], []).append(a)

    log = EventLog()
    add_policy_events(log, tables["policies"])
    add_document_events(rng, log, tables["documents"])

    produced = {"assignments": [], "assessments": [], "reserves": [], "settlements": []}
    for claim in claims.to_dict("records"):
        cid = claim["claim_id"]
        result = evaluate_claim(contexts[cid])
        out = _simulate_claim(rng, log, claim, result, docs_by_claim.get(cid, []),
                              pools[claim["claim_type"]])
        for key in produced:
            produced[key].extend(out[key])

    claims = claims.copy()
    claims["current_status"] = [log.last_status("CLAIM", c) for c in claims["claim_id"]]
    return {
        "claims": claims,                                   # same table, status now derived
        "claim_assignments": pd.DataFrame(produced["assignments"]),
        "assessments": pd.DataFrame(produced["assessments"]),
        "reserves": pd.DataFrame(produced["reserves"]),
        "settlements": pd.DataFrame(produced["settlements"]),
        "status_events": log.to_frame(),
    }