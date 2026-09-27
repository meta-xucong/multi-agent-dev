#!/usr/bin/env python3
"""Deterministic pending notification state; transport is deliberately separate."""
from __future__ import annotations
import hashlib, json, uuid
from typing import Any
from state_store import StateStore, StateError

class NotificationState:
    def __init__(self, state: StateStore): self.state=state
    def record(self, run_id: str|None, task_id: str|None, status: str, message: dict[str,Any], idempotency_key: str|None=None):
        seed={"run_id":run_id,"task_id":task_id,"status":status,"message":message}
        key=idempotency_key or hashlib.sha256(json.dumps(seed,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return self.state.record_notification_intent(str(uuid.uuid4()),key,{"status":status,"message":message},run_id,task_id)
    def mark_sent(self, intent_id: str): return self.state.update_notification_intent(intent_id,"SENT")
    def mark_failed(self, intent_id: str, error: str): return self.state.update_notification_intent(intent_id,"FAILED",error[:256])
    def suppress(self, intent_id: str): return self.state.update_notification_intent(intent_id,"SUPPRESSED")
    def pending(self): return self.state.pending_notifications()
    def replayable(self): return [row for row in self.pending() if row["status"] in {"PENDING","FAILED"}]
