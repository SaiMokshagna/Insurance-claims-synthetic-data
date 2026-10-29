"""Status-event audit log: every state change is a NEW row, never an update."""
from datetime import timedelta

import pandas as pd

from generator import ids
from generator.config import REFERENCE_DATE


class EventLog:
    def __init__(self):
        self._rows = []
        self._last_status = {}
        self._last_day = {}
        self._count = {}

    def add(self, entity_type, entity_id, event_type, to_status, day,
            actor_type="SYSTEM", actor_id=None, reason_code=None):
        key = (entity_type, entity_id)
        if day < self._last_day.get(key, day):
            raise ValueError(f"Event for {key} goes backwards in time: "
                             f"{event_type} on {day} after {self._last_day[key]}")
        k = self._count.get(key, 0)
        self._rows.append({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "event_type": event_type,
            "from_status": self._last_status.get(key),       # computed, never typed by hand
            "to_status": to_status,
            "event_ts": f"{day.isoformat()}T{min(8 + k, 23):02d}:00:00Z",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "reason_code": reason_code,
        })
        self._last_status[key] = to_status
        self._last_day[key] = day
        self._count[key] = k + 1

    def last_status(self, entity_type, entity_id):
        return self._last_status.get((entity_type, entity_id))

    def to_frame(self):
        """Sort chronologically, then number the events EVT-00000001..."""
        rows = sorted(self._rows, key=lambda r: (r["event_ts"], r["entity_type"], r["entity_id"]))
        return pd.DataFrame([{"event_id": ids.event_id(n), **r}
                             for n, r in enumerate(rows, start=1)])


def add_policy_events(log, policies):
    for p in policies.itertuples(index=False):
        log.add("POLICY", p.policy_id, "POLICY_ISSUED", "IN_FORCE", p.effective_date)
        if pd.notna(p.cancellation_date):
            log.add("POLICY", p.policy_id, "POLICY_CANCELLED", "CANCELLED", p.cancellation_date)
        elif pd.notna(p.lapse_date):
            log.add("POLICY", p.policy_id, "POLICY_LAPSED", "LAPSED", p.lapse_date)
        elif p.expiry_date < REFERENCE_DATE:
            log.add("POLICY", p.policy_id, "POLICY_EXPIRED", "EXPIRED",
                    p.expiry_date + timedelta(days=1))


def add_document_events(rng, log, documents):
    for d in documents.itertuples(index=False):
        if pd.notna(d.requested_date):
            log.add("DOCUMENT", d.document_id, "DOCUMENT_REQUESTED", "REQUESTED", d.requested_date)
        if d.status in ("RECEIVED", "VERIFIED"):
            log.add("DOCUMENT", d.document_id, "DOCUMENT_RECEIVED", "RECEIVED",
                    d.received_date, actor_type="CUSTOMER")
        if d.status == "VERIFIED":
            verified = min(d.received_date + timedelta(days=int(rng.integers(0, 3))), REFERENCE_DATE)
            log.add("DOCUMENT", d.document_id, "DOCUMENT_VERIFIED", "VERIFIED", verified)