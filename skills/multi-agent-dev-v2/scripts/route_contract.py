#!/usr/bin/env python3
"""Validate the V2 dispatch-intent marker; this does not enforce or prove runtime routing."""

from __future__ import annotations

import json
import re
from typing import Any


MARKER = "MAD_ROUTE_V2"
CONTRACT_REV = "v2.0.0-route-contract"
FIELDS = frozenset(
    {
        "role",
        "design_ambiguity",
        "implementation",
        "audit_risk",
        "stage",
        "profile_id",
        "task_id",
        "contract_rev",
    }
)
SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
IMPLEMENTATION_PROFILE = {
    "I0": "madv2_execute_i0_luna_low",
    "I1": "madv2_execute_i1_luna_high",
    "I2": "madv2_execute_i2_luna_xhigh",
    "I3": "madv2_execute_i3_luna_max",
}
AUDIT_PROFILE = {
    "A0": "madv2_audit_a0_luna_high",
    "A1": "madv2_audit_a1_luna_xhigh",
    "A2": "madv2_audit_a2_luna_max",
}
THINK_PROFILE = "madv2_think_sol_xhigh"


class RouteContractError(ValueError):
    """A marked V2 dispatch intent is malformed or internally inconsistent."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RouteContractError(f"duplicate field: {key}")
        result[key] = value
    return result


def validate_payload(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict) or frozenset(payload) != FIELDS:
        raise RouteContractError("payload fields do not match V2 contract")
    if not all(isinstance(value, str) for value in payload.values()):
        raise RouteContractError("all V2 contract values must be strings")
    if payload["contract_rev"] != CONTRACT_REV:
        raise RouteContractError("unsupported contract revision")
    if SAFE_TASK_ID.fullmatch(payload["task_id"]) is None:
        raise RouteContractError("unsafe task_id")
    if payload["design_ambiguity"] not in {"D0", "D1"}:
        raise RouteContractError("invalid design_ambiguity")
    if payload["implementation"] not in IMPLEMENTATION_PROFILE:
        raise RouteContractError("invalid implementation tier")
    if payload["audit_risk"] not in AUDIT_PROFILE:
        raise RouteContractError("invalid audit_risk")

    role = payload["role"]
    stage = payload["stage"]
    if role == "think":
        if stage != "PRE_CONTRACT" or payload["design_ambiguity"] != "D1":
            raise RouteContractError("think requires D1 at PRE_CONTRACT")
        expected_profile = THINK_PROFILE
    elif role == "execute":
        if stage != "CONTRACT_FROZEN" or payload["design_ambiguity"] != "D0":
            raise RouteContractError("execute requires D0 at CONTRACT_FROZEN")
        expected_profile = IMPLEMENTATION_PROFILE[payload["implementation"]]
    elif role == "audit":
        if stage != "VERSION_FROZEN" or payload["design_ambiguity"] != "D0":
            raise RouteContractError("audit requires D0 at VERSION_FROZEN")
        expected_profile = AUDIT_PROFILE[payload["audit_risk"]]
    else:
        raise RouteContractError("invalid role")
    if payload["profile_id"] != expected_profile:
        raise RouteContractError("profile_id does not match role and tier")
    return dict(payload)


def build_marker(payload: dict[str, Any]) -> str:
    checked = validate_payload(payload)
    encoded = json.dumps(checked, ensure_ascii=False, separators=(",", ":"))
    return f"{MARKER} {encoded}"


def parse_marker(message: str) -> dict[str, str] | None:
    """Parse only when the first non-empty line is the marker; ignore plain text."""

    if not isinstance(message, str):
        return None
    first = next((line.strip() for line in message.splitlines() if line.strip()), None)
    if first is None or not first.startswith(MARKER):
        return None
    if not first.startswith(MARKER + " "):
        raise RouteContractError("malformed V2 marker prefix")
    raw = first[len(MARKER) + 1 :]
    try:
        payload = json.loads(raw, object_pairs_hook=_reject_duplicate_keys)
    except RouteContractError:
        raise
    except (TypeError, json.JSONDecodeError) as exc:
        raise RouteContractError("invalid V2 marker JSON") from exc
    return validate_payload(payload)
