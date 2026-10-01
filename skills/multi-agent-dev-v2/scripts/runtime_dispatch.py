#!/usr/bin/env python3
"""Lifecycle and provenance gate for an explicit Codex child-thread dispatch.

This module is deliberately transport-neutral.  A caller feeds it the raw
app-server events from one parent/child dispatch.  It never trusts the model's
tool-call arguments as observed provenance and never treats a Hook receipt as
model evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from parallel_manifest import ContractError, HOOK_STATUSES, validate_id
from route_provenance import RouteProvenance
from route_contract import (
    AUDIT_PROFILE,
    IMPLEMENTATION_PROFILE,
    PROFILE_ROUTE_CONTRACT,
    SOURCE_FIDELITY_PROFILE,
    THINK_PROFILE,
)


TERMINAL_EVENTS = {"turn/completed", "turn/failed", "turn/cancelled", "turn/interrupted"}


class RuntimeDispatchError(ContractError):
    """A child dispatch cannot be accepted as a completed, evidenced run."""


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return value


def _event_method(event: Mapping[str, Any]) -> str:
    method = event.get("method")
    return method if isinstance(method, str) else ""


def _params(event: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(event.get("params"))


def _event_thread_id(event: Mapping[str, Any]) -> str | None:
    params = _params(event)
    value = params.get("threadId")
    if isinstance(value, str) and value:
        return value
    thread = _mapping(params.get("thread"))
    value = thread.get("id")
    return value if isinstance(value, str) and value else None


def _child_id_from_event(event: Mapping[str, Any], parent_thread_id: str) -> str | None:
    method = _event_method(event)
    params = _params(event)
    thread = _mapping(params.get("thread"))
    if method == "thread/started":
        if thread.get("parentThreadId") == parent_thread_id:
            value = thread.get("id")
            return value if isinstance(value, str) and value else None
    item = _mapping(params.get("item"))
    # Activity items are only child evidence when the runtime scopes the item
    # to this parent.  An unscoped activity item may belong to another thread
    # (or be an ordinary UI event), so it must never bind a child by itself.
    if item.get("type") == "subAgentActivity" and _event_thread_id(event) == parent_thread_id:
        value = item.get("agentThreadId")
        return value if isinstance(value, str) and value else None
    return None


def _thread_settings(event: Mapping[str, Any], child_thread_id: str) -> tuple[str | None, str | None] | None:
    if _event_method(event) != "thread/settings/updated" or _event_thread_id(event) != child_thread_id:
        return None
    settings = _mapping(_params(event).get("threadSettings"))
    model = settings.get("model")
    effort = settings.get("effort", settings.get("reasoning_effort"))
    return (
        model if isinstance(model, str) and model else None,
        effort if isinstance(effort, str) and effort else None,
    )


def _is_terminal_child_event(event: Mapping[str, Any], child_thread_id: str) -> bool:
    return _event_method(event) in TERMINAL_EVENTS and _event_thread_id(event) == child_thread_id


def _is_spawn_failure(event: Mapping[str, Any]) -> bool:
    if _event_method(event) in {"collaboration/spawn_failed", "thread/failed"}:
        return True
    if _event_method(event) != "rawResponseItem/completed":
        return False
    item = _mapping(_params(event).get("item"))
    if item.get("type") != "function_call_output":
        return False
    output = item.get("output")
    return isinstance(output, str) and "collab spawn failed" in output.lower()


def _is_parent_terminal_event(event: Mapping[str, Any], parent_thread_id: str) -> bool:
    return _event_method(event) in TERMINAL_EVENTS and _event_thread_id(event) == parent_thread_id


@dataclass(frozen=True)
class RuntimeDispatchRequest:
    parent_thread_id: str
    task_id: str
    requested_model: str
    requested_effort: str
    profile_id: str
    hook_status: str = "HOOK_UNVERIFIED"
    child_thread_id: str | None = None
    sandbox_mode: str = "workspace-write"
    role: str = "execute"

    def __post_init__(self) -> None:
        validate_id(self.parent_thread_id, "parent_thread_id")
        validate_id(self.task_id, "task_id")
        if not all(isinstance(value, str) and value for value in (self.requested_model, self.requested_effort, self.profile_id)):
            raise ContractError("requested route fields are required")
        role_profiles = {
            "think": {THINK_PROFILE},
            "execute": set(IMPLEMENTATION_PROFILE.values()),
            "audit": set(AUDIT_PROFILE.values()),
            "source_fidelity": set(SOURCE_FIDELITY_PROFILE.values()),
        }
        if self.role not in role_profiles or self.profile_id not in role_profiles[self.role]:
            raise ContractError("profile is not permitted for the requested runtime role")
        expected_route = PROFILE_ROUTE_CONTRACT.get(self.profile_id)
        if expected_route is None:
            raise ContractError("profile is not in the frozen V2 route contract")
        if (self.requested_model, self.requested_effort, self.sandbox_mode) != expected_route:
            raise ContractError("requested route does not match the frozen V2 profile contract")
        if self.hook_status not in HOOK_STATUSES:
            raise ContractError("invalid hook status")
        if self.child_thread_id is not None:
            validate_id(self.child_thread_id, "child_thread_id")


@dataclass(frozen=True)
class RuntimeDispatchResult:
    request: RuntimeDispatchRequest
    lifecycle: str
    route_provenance: RouteProvenance
    child_thread_id: str | None
    child_started_observed: bool
    observed_model: str | None
    observed_effort: str | None
    child_completed: bool
    parent_close_allowed: bool
    evidence_refs: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()

    @property
    def admissible(self) -> bool:
        return (
            self.lifecycle == "CHILD_COMPLETED"
            and self.child_started_observed
            and self.child_completed
            and self.parent_close_allowed
            and self.route_provenance.route_status in {"PROFILE_VERIFIED", "EXPLICIT_ROUTE_VERIFIED"}
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "parent_thread_id": self.request.parent_thread_id,
            "task_id": self.request.task_id,
            "role": self.request.role,
            "profile_id": self.request.profile_id,
            "request": {
                "parent_thread_id": self.request.parent_thread_id,
                "role": self.request.role,
                "task_id": self.request.task_id,
                "profile_id": self.request.profile_id,
                "requested_model": self.request.requested_model,
                "requested_effort": self.request.requested_effort,
                "requested_sandbox_mode": self.request.sandbox_mode,
                "hook_status": self.request.hook_status,
            },
            "lifecycle": self.lifecycle,
            "child_thread_id": self.child_thread_id,
            "child_started_observed": self.child_started_observed,
            "observed_model": self.observed_model,
            "observed_effort": self.observed_effort,
            "sandbox_observed": False,
            "child_completed": self.child_completed,
            "parent_close_allowed": self.parent_close_allowed,
            "route_provenance": self.route_provenance.as_dict(),
            "evidence_refs": list(self.evidence_refs),
            "blockers": list(self.blockers),
            "admissible": self.admissible,
        }


@dataclass
class RuntimeDispatchSession:
    """Collect one dispatch without allowing premature parent shutdown."""

    request: RuntimeDispatchRequest
    _events: list[Mapping[str, Any]] = field(default_factory=list)
    _parent_closed: bool = False

    def observe(self, event: Mapping[str, Any]) -> None:
        if self._parent_closed:
            raise RuntimeDispatchError("PARENT_ALREADY_CLOSED")
        if not isinstance(event, Mapping):
            raise RuntimeDispatchError("runtime event must be an object")
        self._events.append(dict(event))

    def observe_many(self, events: Iterable[Mapping[str, Any]]) -> None:
        for event in events:
            self.observe(event)

    def _child_id(self) -> str | None:
        if self.request.child_thread_id:
            return self.request.child_thread_id
        for event in self._events:
            value = _child_id_from_event(event, self.request.parent_thread_id)
            if value:
                return value
        return None

    def result(self) -> RuntimeDispatchResult:
        child_id = self._child_id()
        observed_child_ids = {
            value
            for value in (_child_id_from_event(event, self.request.parent_thread_id) for event in self._events)
            if value
        }
        child_started_observed = bool(child_id and child_id in observed_child_ids)
        refs: list[str] = []
        if child_id:
            refs.append(f"child-thread:{child_id}")
        observed_model: str | None = None
        observed_effort: str | None = None
        child_completed = False
        failed = False
        parent_terminal_before_child = False
        observed_pairs: set[tuple[str, str]] = set()
        settings_source = ""
        for index, event in enumerate(self._events):
            if _is_spawn_failure(event):
                failed = True
                refs.append(f"event:{index}:spawn-failed")
            if _is_parent_terminal_event(event, self.request.parent_thread_id):
                if not child_completed:
                    parent_terminal_before_child = True
                refs.append(f"event:{index}:parent-terminal")
            if child_id:
                # Only the explicit runtime settings update is route
                # provenance.  Values copied into thread/started are useful
                # context, but are not independently verified settings.
                settings = _thread_settings(event, child_id)
                if settings:
                    model, effort = settings
                    settings_source = "codex-app-server.thread.settings"
                    if model and effort:
                        observed_pairs.add((model, effort))
                    observed_model = model or observed_model
                    observed_effort = effort or observed_effort
                    refs.append(f"event:{index}:settings")
                if _is_terminal_child_event(event, child_id):
                    child_completed = True
                    refs.append(f"event:{index}:child-terminal")
        if failed:
            lifecycle = "SPAWN_FAILED"
        elif child_id is None or not child_started_observed:
            lifecycle = "SPAWN_REQUESTED"
        elif child_completed:
            lifecycle = "CHILD_COMPLETED"
        else:
            lifecycle = "CHILD_STARTED"

        route_conflict = len(observed_pairs) > 1
        if observed_model is None or observed_effort is None:
            route_status = "ROUTE_UNVERIFIED"
        elif route_conflict:
            route_status = "ROUTE_MISMATCH"
        elif (observed_model, observed_effort) != (self.request.requested_model, self.request.requested_effort):
            route_status = "ROUTE_MISMATCH"
        else:
            route_status = "EXPLICIT_ROUTE_VERIFIED"
        route = RouteProvenance(
            requested_model=self.request.requested_model,
            requested_effort=self.request.requested_effort,
            route_status=route_status,
            hook_status=self.request.hook_status,
            observed_model=observed_model,
            observed_effort=observed_effort,
            source=settings_source,
            evidence_refs=tuple(refs),
        )
        blockers: list[str] = []
        if child_id is None:
            blockers.append("CHILD_THREAD_NOT_STARTED")
        elif not child_started_observed:
            blockers.append("CHILD_START_EVENT_MISSING")
        if not child_completed:
            blockers.append("CHILD_NOT_TERMINAL")
        if route_status == "ROUTE_UNVERIFIED":
            blockers.append("ROUTE_PROVENANCE_MISSING")
        if route_status == "ROUTE_MISMATCH":
            blockers.append("ROUTE_MISMATCH")
        if route_conflict:
            blockers.append("ROUTE_CONFLICT")
        if failed:
            blockers.append("SPAWN_FAILED")
        if parent_terminal_before_child:
            blockers.append("PARENT_TERMINATED_BEFORE_CHILD_TERMINAL")
        if self._parent_closed and not child_completed:
            blockers.append("PARENT_CLOSED_BEFORE_CHILD_TERMINAL")
        return RuntimeDispatchResult(
            request=self.request,
            lifecycle=lifecycle,
            route_provenance=route,
            child_thread_id=child_id,
            child_started_observed=child_started_observed,
            observed_model=observed_model,
            observed_effort=observed_effort,
            child_completed=child_completed,
            parent_close_allowed=child_completed and not failed and not parent_terminal_before_child,
            evidence_refs=tuple(refs),
            blockers=tuple(dict.fromkeys(blockers)),
        )

    def close_parent(self) -> None:
        result = self.result()
        if not result.child_completed:
            self._parent_closed = True
            raise RuntimeDispatchError("PARENT_CLOSE_BEFORE_CHILD_TERMINAL")
        self._parent_closed = True

    def require_admissible(self) -> RuntimeDispatchResult:
        result = self.result()
        if not result.admissible:
            raise RuntimeDispatchError("RUNTIME_DISPATCH_NOT_ADMISSIBLE:" + ",".join(result.blockers))
        return result


def collect_child_provenance(request: RuntimeDispatchRequest, events: Iterable[Mapping[str, Any]]) -> RuntimeDispatchResult:
    session = RuntimeDispatchSession(request)
    session.observe_many(events)
    return session.result()
