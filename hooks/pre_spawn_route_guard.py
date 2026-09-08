#!/usr/bin/env python3
"""Synchronous PreToolUse guard for MAD_ROUTE_V1 spawn requests.

The module deliberately uses only the Python standard library.  Its pure
functions make the route decision testable without a running Codex session;
the CLI is a thin stdin/stdout adapter for the hook protocol.
"""

from __future__ import annotations

import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


MARKER_PREFIX = "MAD_ROUTE_V1"
RECEIPT_PREFIX = "MAD_ROUTE_RECEIPT"
ERROR_PREFIX = "MAD_ROUTE_ERROR"
POLICY_REV = "v1.3.1-route-guard"
HOOK_EVENT_NAME = "PreToolUse"
TARGET_TOOLS = frozenset({"Agent", "spawn_agent", "multi_agent_v1__spawn_agent"})
BUILTIN_AGENT_TYPES = frozenset({"worker", "explorer", "default"})
ALLOWED_ROLES = frozenset({"think", "execute", "audit"})
ALLOWED_GATES = frozenset({"SIMPLE_PROVEN", "ESCALATE_REQUIRED"})
ALLOWED_STAGES = frozenset({"PRE_CONTRACT", "CONTRACT_FROZEN", "VERSION_FROZEN"})
MAX_SHORT_STRING = 128
SAFE_ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
SAFE_ID_RE = re.compile(rf"^{SAFE_ID_PATTERN}$")
_MISSING = object()

ROUTE_TABLE: dict[tuple[str, str], tuple[str, str, str]] = {
    ("think", "ESCALATE_REQUIRED"): ("PRE_CONTRACT", "gpt-5.6-sol", "max"),
    ("execute", "SIMPLE_PROVEN"): ("CONTRACT_FROZEN", "gpt-5.6-luna", "high"),
    ("execute", "ESCALATE_REQUIRED"): ("CONTRACT_FROZEN", "gpt-5.6-luna", "max"),
    ("audit", "SIMPLE_PROVEN"): ("VERSION_FROZEN", "gpt-5.6-luna", "high"),
    ("audit", "ESCALATE_REQUIRED"): ("VERSION_FROZEN", "gpt-5.6-luna", "max"),
}

_TASK_NAME_RE = re.compile(
    r"^madv1_(?P<role>think|execute|audit)_(?P<gate>simple|escalate)_(?P<slug>[a-z0-9]+(?:[_-][a-z0-9]+)*)$"
)


class RouteError(ValueError):
    """An input is understood but cannot be admitted by the route contract."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Marker:
    role: str
    complexity_gate: str
    stage: str
    task_id: str
    contract_rev: str


@dataclass(frozen=True)
class Route:
    model: str
    reasoning_effort: str


def _marker_candidate(message: Any) -> tuple[str | None, str | None]:
    """Return the first non-empty line and the JSON suffix when marked.

    ``None`` as the first tuple item means that the spawn is unmarked and
    should be passed through.  A marker prefix with malformed suffix returns
    the candidate line and lets the caller produce a stable denial.
    """

    if not isinstance(message, str):
        return None, None
    for line in message.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped == MARKER_PREFIX:
            return stripped, ""
        if stripped.startswith(MARKER_PREFIX) and len(stripped) > len(MARKER_PREFIX) and stripped[len(MARKER_PREFIX)] in " \t":
            suffix = stripped[len(MARKER_PREFIX) :].strip()
            return stripped, suffix
        return None, None
    return None, None


def parse_marker(message: Any) -> Marker | None:
    """Parse the marker in ``message`` or return ``None`` when unmarked."""

    line, suffix = _marker_candidate(message)
    if line is None:
        return None
    if not suffix:
        raise RouteError("MAD_ROUTE_JSON_INVALID")
    try:
        parsed = json.loads(suffix)
    except (TypeError, json.JSONDecodeError) as error:
        raise RouteError("MAD_ROUTE_JSON_INVALID") from error
    if not isinstance(parsed, dict):
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")
    expected = {"role", "complexity_gate", "stage", "task_id", "contract_rev"}
    if set(parsed) != expected:
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")
    role = parsed["role"]
    gate = parsed["complexity_gate"]
    stage = parsed["stage"]
    task_id = parsed["task_id"]
    contract_rev = parsed["contract_rev"]
    if not isinstance(role, str) or role not in ALLOWED_ROLES:
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")
    if not isinstance(gate, str) or gate not in ALLOWED_GATES:
        raise RouteError("MAD_ROUTE_GATE_INVALID")
    if not isinstance(stage, str) or stage not in ALLOWED_STAGES:
        raise RouteError("MAD_ROUTE_STAGE_INVALID")
    if not isinstance(task_id, str) or not SAFE_ID_RE.fullmatch(task_id):
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")
    if contract_rev != POLICY_REV:
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")
    expected_stage, _, _ = ROUTE_TABLE.get((role, gate), ("", "", ""))
    if not expected_stage:
        raise RouteError("MAD_ROUTE_GATE_INVALID")
    if stage != expected_stage:
        raise RouteError("MAD_ROUTE_STAGE_INVALID")
    return Marker(role, gate, stage, task_id, contract_rev)


def route_for(marker: Marker) -> Route:
    """Return the sole model/effort pair permitted by a valid marker."""

    route = ROUTE_TABLE.get((marker.role, marker.complexity_gate))
    if route is None:
        raise RouteError("MAD_ROUTE_GATE_INVALID")
    _, model, reasoning_effort = route
    return Route(model, reasoning_effort)


def _validate_task_name(value: Any, marker: Marker) -> None:
    if not isinstance(value, str) or not value or len(value) > MAX_SHORT_STRING:
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")
    match = _TASK_NAME_RE.fullmatch(value)
    if match is None:
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")
    gate_name = "simple" if marker.complexity_gate == "SIMPLE_PROVEN" else "escalate"
    if match.group("role") != marker.role or match.group("gate") != gate_name:
        raise RouteError("MAD_ROUTE_FIELDS_INVALID")


def _validate_agent_type(tool_input: Mapping[str, Any]) -> None:
    if "agent_type" not in tool_input:
        return
    agent_type = tool_input["agent_type"]
    if not isinstance(agent_type, str) or agent_type not in BUILTIN_AGENT_TYPES:
        raise RouteError("MAD_ROUTE_AGENT_TYPE_UNSUPPORTED")


def _validate_fork(tool_input: Mapping[str, Any], has_task_name: bool) -> None:
    if "fork_turns" in tool_input and "fork_context" in tool_input:
        raise RouteError("MAD_ROUTE_FORK_INHERIT_FORBIDDEN")
    if "fork_turns" in tool_input:
        fork_turns = tool_input["fork_turns"]
        if fork_turns != "none":
            raise RouteError("MAD_ROUTE_FORK_INHERIT_FORBIDDEN")
    if "fork_context" in tool_input:
        fork_context = tool_input["fork_context"]
        if not isinstance(fork_context, bool):
            raise RouteError("MAD_ROUTE_FORK_CONTEXT_FORBIDDEN")
        if fork_context:
            raise RouteError("MAD_ROUTE_FORK_CONTEXT_FORBIDDEN")
def _copy_and_update(tool_input: Mapping[str, Any], marker: Marker, route: Route) -> dict[str, Any]:
    updated = dict(tool_input)
    has_task_name = "task_name" in updated
    _validate_agent_type(updated)
    _validate_fork(updated, has_task_name)
    updated["model"] = route.model
    updated["reasoning_effort"] = route.reasoning_effort
    if has_task_name:
        _validate_task_name(updated["task_name"], marker)
        if "fork_turns" not in updated:
            updated["fork_turns"] = "none"
    return updated


def _validate_tool_use_id(payload: Mapping[str, Any]) -> str:
    value = payload.get("tool_use_id")
    if not isinstance(value, str) or SAFE_ID_RE.fullmatch(value) is None:
        raise RouteError("MAD_ROUTE_TOOL_USE_ID_INVALID")
    return value


def _classify_model(value: Any) -> str:
    if value is _MISSING:
        return "omitted"
    if not isinstance(value, str):
        return "invalid_type"
    if value == "gpt-5.6-luna":
        return "luna"
    if value == "gpt-5.6-sol":
        return "sol"
    return "other"


def _classify_effort(value: Any) -> str:
    if value is _MISSING:
        return "omitted"
    if not isinstance(value, str):
        return "invalid_type"
    if value in {"high", "max", "xhigh"}:
        return value
    return "other"


def _receipt(
    tool_use_id: str,
    tool_name: str,
    marker: Marker,
    route: Route,
    requested_model: str,
    requested_reasoning_effort: str,
    corrected: bool,
) -> dict[str, Any]:
    return {
        "type": RECEIPT_PREFIX,
        "policy_rev": POLICY_REV,
        "tool_use_id": tool_use_id,
        "role": marker.role,
        "complexity_gate": marker.complexity_gate,
        "stage": marker.stage,
        "task_id": marker.task_id,
        "tool_name": tool_name,
        "requested_model": requested_model,
        "requested_reasoning_effort": requested_reasoning_effort,
        "enforced_model": route.model,
        "enforced_reasoning_effort": route.reasoning_effort,
        "corrected": corrected,
    }


def _allow_result(
    tool_use_id: str,
    tool_name: str,
    marker: Marker,
    route: Route,
    updated_input: Mapping[str, Any],
    requested_model: str,
    requested_reasoning_effort: str,
    corrected: bool,
) -> dict[str, Any]:
    receipt = _receipt(
        tool_use_id,
        tool_name,
        marker,
        route,
        requested_model,
        requested_reasoning_effort,
        corrected,
    )
    receipt_json = json.dumps(receipt, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "allow",
            "additionalContext": f"{RECEIPT_PREFIX} {receipt_json}",
            "updatedInput": dict(updated_input),
        }
    }


def _deny_result(code: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": f"{ERROR_PREFIX} {code}",
        }
    }


def guard_payload(payload: Any) -> tuple[str, dict[str, Any] | None, int]:
    """Guard one decoded hook payload.

    The returned action is ``passthrough``, ``allow`` or ``deny``.  A
    structured payload error uses exit code 2 so the hook runtime also
    fail-closes when it cannot identify the target input.
    """

    if not isinstance(payload, dict):
        return "deny", _deny_result("MAD_ROUTE_INPUT_INVALID"), 2
    tool_name = payload.get("tool_name")
    if not isinstance(tool_name, str):
        return "deny", _deny_result("MAD_ROUTE_INPUT_INVALID"), 2
    if tool_name not in TARGET_TOOLS:
        return "passthrough", None, 0
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return "deny", _deny_result("MAD_ROUTE_INPUT_INVALID"), 2
    try:
        marker = parse_marker(tool_input.get("message"))
        if marker is None:
            task_name = tool_input.get("task_name")
            if isinstance(task_name, str) and task_name.startswith("madv1_"):
                raise RouteError("MAD_ROUTE_MARKER_INVALID")
            return "passthrough", None, 0
        tool_use_id = _validate_tool_use_id(payload)
        route = route_for(marker)
        requested_model_value = tool_input.get("model", _MISSING)
        requested_reasoning_effort_value = tool_input.get("reasoning_effort", _MISSING)
        requested_model = _classify_model(requested_model_value)
        requested_reasoning_effort = _classify_effort(requested_reasoning_effort_value)
        corrected = (
            requested_model_value != route.model
            or requested_reasoning_effort_value != route.reasoning_effort
        )
        updated_input = _copy_and_update(tool_input, marker, route)
    except RouteError as error:
        return "deny", _deny_result(error.code), 0
    return "allow", _allow_result(
        tool_use_id,
        tool_name,
        marker,
        route,
        updated_input,
        requested_model,
        requested_reasoning_effort,
        corrected,
    ), 0


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        sys.stderr.write(f"{ERROR_PREFIX} MAD_ROUTE_INPUT_INVALID\n")
        return 2
    try:
        action, result, exit_code = guard_payload(payload)
    except Exception:
        sys.stderr.write(f"{ERROR_PREFIX} MAD_ROUTE_GUARD_FAILURE\n")
        return 2
    if exit_code == 2:
        sys.stderr.write(f"{ERROR_PREFIX} MAD_ROUTE_INPUT_INVALID\n")
        return 2
    if action == "passthrough":
        return 0
    assert result is not None
    sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":"), sort_keys=True))
    sys.stdout.write("\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
