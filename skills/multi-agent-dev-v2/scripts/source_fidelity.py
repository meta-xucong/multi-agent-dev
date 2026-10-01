#!/usr/bin/env python3
"""Deterministic source-fidelity evidence for source-driven V2 tasks.

This module deliberately proves only what it can inspect: fixed manifests,
mapping coverage, required symbols/fragments and conservative structural
signals.  It never executes a reference repository and never treats a
mapping or an agent assertion as semantic proof by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from parallel_manifest import ContractError, SHA256, validate_id, validate_path

STATUSES = {
    "PASS",
    "WARN",
    "BLOCK",
    "NEEDS_USER_DECISION",
    "INSUFFICIENT_EVIDENCE",
    "REFERENCE_UNVERIFIED",
}
CLASSIFICATIONS = {"DIRECT_REUSE", "THIN_ADAPTER", "PLATFORM_SHELL", "AUTHORIZED_NEW"}

_IDENTIFIER = re.compile(r"(?<![A-Za-z0-9_])[_A-Za-z][_A-Za-z0-9]*")
_LITERAL = re.compile(r"(?:\b\d+(?:\.\d+)?\b|'[^'\n]*'|\"[^\"\n]*\")")
_STRUCTURAL = re.compile(r"\b(if|elif|else|for|while|try|except|finally|raise|return|yield|match|case)\b")
_OPERATORS = re.compile(r"(===|!==|==|!=|<=|>=|//|\*\*|->|[+\-*/%<>=])")
_TOKEN = re.compile(r"(?:[_A-Za-z][_A-Za-z0-9]*|\d+(?:\.\d+)?|'[^'\n]*'|\"[^\"\n]*\"|===|!==|==|!=|<=|>=|//|\*\*|->|[^\s])")
_IGNORED_IDENTIFIERS = {
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def",
    "del", "elif", "else", "except", "false", "finally", "for", "from", "global",
    "if", "import", "in", "is", "lambda", "none", "not", "or", "pass", "raise",
    "return", "true", "try", "while", "with", "yield", "const", "let", "var",
    "function", "new", "public", "private", "protected", "readonly", "static",
}


def _is_reparse(path: Path) -> bool:
    checker = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(checker and checker())


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ContractError(f"cannot read text source: {path}") from exc


def _safe_root(value: str | Path, name: str) -> Path:
    raw = Path(value).expanduser()
    if _is_reparse(raw):
        raise ContractError(f"{name} must not be a symlink/reparse path")
    root = raw.resolve()
    if not root.is_dir():
        raise ContractError(f"{name} must be a real directory")
    current = raw.absolute()
    parts = current.parts
    probe = Path(parts[0])
    for part in parts[1:]:
        probe = probe / part
        if _is_reparse(probe):
            raise ContractError(f"{name} contains a symlink/reparse path")
    return root


def _safe_file(root: Path, relative: str, name: str) -> Path:
    normalized = validate_path(relative)
    raw = root / PurePosixPath(normalized)
    if _is_reparse(raw):
        raise ContractError(f"{name} is a symlink/reparse path: {relative}")
    path = raw.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"{name} escapes its root") from exc
    if not path.is_file() or path.is_symlink():
        raise ContractError(f"{name} is missing or unsafe: {relative}")
    return path


def file_manifest(root: str | Path) -> tuple[dict[str, str], str]:
    """Return file hashes and the canonical manifest hash for a root."""
    base = _safe_root(root, "manifest root")
    entries: dict[str, str] = {}
    for path in base.rglob("*"):
        if _is_reparse(path):
            raise ContractError(f"manifest contains a symlink/reparse path: {path.relative_to(base)}")
        if not path.is_file() or any(part in {"__pycache__", ".git"} for part in path.relative_to(base).parts):
            continue
        relative = path.relative_to(base).as_posix()
        entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    lines = "".join(f"{relative} {entries[relative]}\n" for relative in sorted(entries, key=str.lower))
    return entries, hashlib.sha256(lines.encode("utf-8")).hexdigest()


def mapping_manifest_hash(mappings: tuple["SourceMapping", ...]) -> str:
    payload = [mapping.as_dict() for mapping in mappings]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def diff_manifest_hash(base_root: str | Path, target_root: str | Path, changed_paths: tuple[str, ...]) -> str:
    """Hash only the frozen changed paths from baseline to target."""
    base = _safe_root(base_root, "target_base_root")
    target = _safe_root(target_root, "target_root")
    lines: list[str] = []
    for relative in sorted(set(changed_paths), key=str.lower):
        base_path = base / PurePosixPath(validate_path(relative))
        target_path = target / PurePosixPath(validate_path(relative))
        if _is_reparse(base_path) or _is_reparse(target_path):
            raise ContractError(f"diff contains a symlink/reparse path: {relative}")
        base_hash = hashlib.sha256(base_path.read_bytes()).hexdigest() if base_path.is_file() else "MISSING"
        target_hash = hashlib.sha256(target_path.read_bytes()).hexdigest() if target_path.is_file() else "MISSING"
        lines.append(f"{relative} {base_hash} {target_hash}\n")
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()


def _identifiers(text: str) -> set[str]:
    return {item for item in _IDENTIFIER.findall(text) if item.lower() not in _IGNORED_IDENTIFIERS}


def _literals(text: str) -> set[str]:
    return set(_LITERAL.findall(text))


def _structural(text: str) -> tuple[str, ...]:
    return tuple(_STRUCTURAL.findall(text))


def _operators(text: str) -> tuple[str, ...]:
    return tuple(_OPERATORS.findall(text))


def _tokens(text: str) -> tuple[str, ...]:
    """Conservative language-agnostic token sequence; not claimed as AST proof."""
    return tuple(_TOKEN.findall(text))


@dataclass(frozen=True)
class SourceMapping:
    mapping_id: str
    source_path: str | None
    target_path: str
    classification: str
    source_symbols: tuple[str, ...] = ()
    required_source_fragments: tuple[str, ...] = ()
    required_target_fragments: tuple[str, ...] = ()
    allowed_added_identifiers: tuple[str, ...] = ()
    allowed_removed_identifiers: tuple[str, ...] = ()
    allowed_added_literals: tuple[str, ...] = ()
    allowed_removed_literals: tuple[str, ...] = ()
    forbidden_patterns: tuple[str, ...] = ()
    regression_tests: tuple[str, ...] = ()
    authorization: str = ""

    def __post_init__(self) -> None:
        validate_id(self.mapping_id, "mapping_id")
        validate_path(self.target_path)
        if self.source_path:
            validate_path(self.source_path)
        if self.classification not in CLASSIFICATIONS:
            raise ContractError("invalid source mapping classification")
        if self.classification in {"PLATFORM_SHELL", "AUTHORIZED_NEW"} and not self.authorization.strip():
            raise ContractError("new/platform mapping requires explicit authorization")

    def as_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "classification": self.classification,
            "source_symbols": list(self.source_symbols),
            "required_source_fragments": list(self.required_source_fragments),
            "required_target_fragments": list(self.required_target_fragments),
            "allowed_added_identifiers": list(self.allowed_added_identifiers),
            "allowed_removed_identifiers": list(self.allowed_removed_identifiers),
            "allowed_added_literals": list(self.allowed_added_literals),
            "allowed_removed_literals": list(self.allowed_removed_literals),
            "forbidden_patterns": list(self.forbidden_patterns),
            "regression_tests": list(self.regression_tests),
            "authorization": self.authorization,
        }


@dataclass(frozen=True)
class ReferenceSpec:
    reference_id: str
    repository: str
    commit: str
    reference_root: str
    target_root: str
    source_manifest_sha256: str
    run_id: str
    task_id: str
    target_manifest_sha256: str | None = None
    target_base_root: str | None = None
    target_base_manifest_sha256: str | None = None
    scope_manifest_hash: str | None = None
    mapping_manifest_sha256: str | None = None
    mapping_revision: str = "sfm-1"
    source_files: tuple[str, ...] = ()
    changed_paths: tuple[str, ...] = ()
    allowed_new_paths: tuple[str, ...] = ()
    mappings: tuple[SourceMapping, ...] = ()

    def __post_init__(self) -> None:
        validate_id(self.reference_id, "reference_id")
        validate_id(self.run_id, "run_id")
        validate_id(self.task_id, "task_id")
        if not self.repository.strip() or not self.commit.strip() or not self.mapping_revision.strip():
            raise ContractError("reference repository, commit and mapping revision are required")
        if re.fullmatch(SHA256, self.source_manifest_sha256) is None:
            raise ContractError("invalid source manifest hash")
        if self.target_manifest_sha256 is not None and re.fullmatch(SHA256, self.target_manifest_sha256) is None:
            raise ContractError("invalid target manifest hash")
        if self.target_base_manifest_sha256 is not None and re.fullmatch(SHA256, self.target_base_manifest_sha256) is None:
            raise ContractError("invalid target base manifest hash")
        if self.scope_manifest_hash is not None and re.fullmatch(SHA256, self.scope_manifest_hash) is None:
            raise ContractError("invalid scope manifest hash")
        if self.mapping_manifest_sha256 is not None and re.fullmatch(SHA256, self.mapping_manifest_sha256) is None:
            raise ContractError("invalid mapping manifest hash")
        for collection in (self.source_files, self.changed_paths, self.allowed_new_paths):
            for path in collection:
                validate_path(path)
        seen = set()
        for mapping in self.mappings:
            if mapping.mapping_id in seen:
                raise ContractError("duplicate source mapping id")
            seen.add(mapping.mapping_id)
            if mapping.source_path and self.source_files and mapping.source_path not in self.source_files:
                raise ContractError("mapping source path is absent from source_files")
        mapped_targets = {mapping.target_path for mapping in self.mappings}
        uncovered = set(self.changed_paths) - mapped_targets - set(self.allowed_new_paths)
        if uncovered:
            raise ContractError("changed source-sensitive path is not mapped: " + sorted(uncovered)[0])

    def as_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "repository": self.repository,
            "commit": self.commit,
            "source_manifest_sha256": self.source_manifest_sha256,
            "run_id": self.run_id,
            "task_id": self.task_id,
            "target_manifest_sha256": self.target_manifest_sha256,
            "target_base_root": self.target_base_root,
            "target_base_manifest_sha256": self.target_base_manifest_sha256,
            "scope_manifest_hash": self.scope_manifest_hash,
            "mapping_manifest_sha256": self.mapping_manifest_sha256,
            "mapping_revision": self.mapping_revision,
            "source_files": list(self.source_files),
            "changed_paths": list(self.changed_paths),
            "allowed_new_paths": list(self.allowed_new_paths),
            "mappings": [mapping.as_dict() for mapping in self.mappings],
        }


@dataclass(frozen=True)
class SourceFidelityReceipt:
    receipt_id: str
    run_id: str
    task_id: str
    target_manifest_hash: str
    target_result_revision: str
    target_diff_hash: str
    reference: dict[str, Any]
    mapping_revision: str
    status: str
    checked_files: tuple[str, ...] = ()
    checked_symbols: tuple[str, ...] = ()
    direct_reuse: tuple[str, ...] = ()
    thin_adaptations: tuple[str, ...] = ()
    platform_shell: tuple[str, ...] = ()
    authorized_new: tuple[str, ...] = ()
    deviations: tuple[str, ...] = ()
    source_gaps: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    next_action: str = "hold"
    scope_manifest_hash: str | None = None
    target_base_manifest_sha256: str | None = None
    mapping_manifest_sha256: str | None = None
    producer_role: str = ""
    producer_thread_id: str = ""

    def __post_init__(self) -> None:
        for field_name, value in (("receipt_id", self.receipt_id), ("run_id", self.run_id), ("task_id", self.task_id)):
            validate_id(value, field_name)
        if self.status not in STATUSES:
            raise ContractError("invalid source fidelity status")
        if self.status == "PASS" and self.producer_role != "source-fidelity-agent":
            raise ContractError("PASS requires source-fidelity-agent producer role")
        for field_name, value in (("target_manifest_hash", self.target_manifest_hash), ("target_diff_hash", self.target_diff_hash)):
            if re.fullmatch(SHA256, value) is None:
                raise ContractError(f"invalid {field_name}")
        if self.scope_manifest_hash is not None and re.fullmatch(SHA256, self.scope_manifest_hash) is None:
            raise ContractError("invalid scope manifest hash")
        if self.target_base_manifest_sha256 is not None and re.fullmatch(SHA256, self.target_base_manifest_sha256) is None:
            raise ContractError("invalid target baseline manifest hash")
        if self.mapping_manifest_sha256 is not None and re.fullmatch(SHA256, self.mapping_manifest_sha256) is None:
            raise ContractError("invalid receipt mapping manifest hash")
        if not self.target_result_revision:
            raise ContractError("target result revision is required")
        if not isinstance(self.reference, dict) or not self.reference.get("repository") or not self.reference.get("commit") or re.fullmatch(SHA256, str(self.reference.get("manifest_sha256", ""))) is None:
            raise ContractError("receipt reference is incomplete")
        if self.status == "PASS" and (self.deviations or self.source_gaps):
            raise ContractError("PASS cannot contain deviations or source gaps")
        if self.status == "PASS" and (not self.evidence_refs or not self.checked_files or not self.tests or not (self.direct_reuse or self.thin_adaptations or self.platform_shell or self.authorized_new) or self.next_action != "integrate" or not self.target_base_manifest_sha256 or not self.mapping_manifest_sha256):
            raise ContractError("PASS requires checked mappings, tests, evidence and integrate action")
        if self.status == "PASS" and self.scope_manifest_hash is None:
            raise ContractError("PASS requires scope manifest binding")

    def as_dict(self) -> dict[str, Any]:
        result = {"receipt_id": self.receipt_id, "run_id": self.run_id, "task_id": self.task_id,
                  "target_manifest_hash": self.target_manifest_hash, "target_result_revision": self.target_result_revision,
                  "target_diff_hash": self.target_diff_hash, "scope_manifest_hash": self.scope_manifest_hash, "target_base_manifest_sha256": self.target_base_manifest_sha256, "mapping_manifest_sha256": self.mapping_manifest_sha256, "reference": self.reference, "mapping_revision": self.mapping_revision, "producer_role": self.producer_role,
                  "producer_thread_id": self.producer_thread_id,
                  "status": self.status, "checked_files": list(self.checked_files), "checked_symbols": list(self.checked_symbols),
                  "direct_reuse": list(self.direct_reuse), "thin_adaptations": list(self.thin_adaptations),
                  "platform_shell": list(self.platform_shell), "authorized_new": list(self.authorized_new),
                  "deviations": list(self.deviations), "source_gaps": list(self.source_gaps), "tests": list(self.tests),
                  "evidence_refs": list(self.evidence_refs), "next_action": self.next_action}
        return result

    def as_evidence_payload(self) -> dict[str, Any]:
        return {"kind": "SOURCE_FIDELITY_RECEIPT", "source": "source-fidelity-agent", "payload": self.as_dict()}


def _mapping_findings(mapping: SourceMapping, source_text: str | None, target_text: str) -> tuple[list[str], list[str], list[str]]:
    hard: list[str] = []
    checked_symbols: list[str] = list(mapping.source_symbols)
    checked_fragments: list[str] = []
    if mapping.classification in {"PLATFORM_SHELL", "AUTHORIZED_NEW"}:
        return hard, checked_symbols, checked_fragments
    if source_text is None:
        return [f"SOURCE_GAP:{mapping.mapping_id}:source text unavailable"], checked_symbols, checked_fragments
    for symbol in mapping.source_symbols:
        if symbol not in source_text or symbol not in target_text:
            hard.append(f"MISSING_SYMBOL:{mapping.mapping_id}:{symbol}")
    for fragment in mapping.required_source_fragments:
        if fragment not in source_text:
            hard.append(f"SOURCE_FRAGMENT_MISSING:{mapping.mapping_id}:{fragment}")
        else:
            checked_fragments.append(fragment)
    for fragment in mapping.required_target_fragments:
        if fragment not in target_text:
            hard.append(f"TARGET_FRAGMENT_MISSING:{mapping.mapping_id}:{fragment}")
    for pattern in mapping.forbidden_patterns:
        try:
            matched = re.search(pattern, target_text, flags=re.MULTILINE) is not None
        except re.error as exc:
            raise ContractError(f"invalid forbidden pattern: {pattern}") from exc
        if matched:
            hard.append(f"FORBIDDEN_PATTERN:{mapping.mapping_id}:{pattern}")
    source_ids, target_ids = _identifiers(source_text), _identifiers(target_text)
    added = target_ids - source_ids - set(mapping.allowed_added_identifiers)
    removed = source_ids - target_ids - set(mapping.allowed_removed_identifiers)
    if added:
        hard.append(f"UNAUTHORIZED_IDENTIFIER:{mapping.mapping_id}:{','.join(sorted(added))}")
    if removed:
        hard.append(f"UNAUTHORIZED_REMOVAL:{mapping.mapping_id}:{','.join(sorted(removed))}")
    source_literals, target_literals = _literals(source_text), _literals(target_text)
    added_literals = target_literals - source_literals - set(mapping.allowed_added_literals)
    removed_literals = source_literals - target_literals - set(mapping.allowed_removed_literals)
    if added_literals:
        hard.append(f"SOURCE_DRIFT_LITERAL:{mapping.mapping_id}:{','.join(sorted(added_literals))}")
    if removed_literals:
        hard.append(f"SOURCE_DRIFT_LITERAL_REMOVED:{mapping.mapping_id}:{','.join(sorted(removed_literals))}")
    if mapping.classification == "DIRECT_REUSE" and _structural(source_text) != _structural(target_text):
        hard.append(f"SOURCE_DRIFT_STRUCTURE:{mapping.mapping_id}")
    if mapping.classification == "DIRECT_REUSE" and _operators(source_text) != _operators(target_text):
        hard.append(f"SOURCE_DRIFT_OPERATOR:{mapping.mapping_id}")
    if mapping.classification == "DIRECT_REUSE" and _tokens(source_text) != _tokens(target_text):
        hard.append(f"SOURCE_DRIFT_TOKEN_SEQUENCE:{mapping.mapping_id}")
    return hard, checked_symbols, checked_fragments


def inspect(spec: ReferenceSpec, receipt_id: str, result_revision: str, diff_hash: str, evidence_refs: tuple[str, ...] = ()) -> SourceFidelityReceipt:
    """Inspect a frozen mapping and return a receipt; never writes project files."""
    try:
        source_root = _safe_root(spec.reference_root, "reference_root")
        target_root = _safe_root(spec.target_root, "target_root")
        source_entries, source_manifest = file_manifest(source_root)
        target_entries, target_manifest = file_manifest(target_root)
    except ContractError:
        raise
    if source_manifest != spec.source_manifest_sha256:
        return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
            {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
            "REFERENCE_UNVERIFIED", next_action="freeze_reference", scope_manifest_hash=spec.scope_manifest_hash)
    for source_file in spec.source_files:
        _safe_file(source_root, source_file, "declared source file")
    if not spec.target_manifest_sha256 or target_manifest != spec.target_manifest_sha256:
        return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
            {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
            "INSUFFICIENT_EVIDENCE", next_action="freeze_target", scope_manifest_hash=spec.scope_manifest_hash, target_base_manifest_sha256=spec.target_base_manifest_sha256)
    if not spec.target_base_root:
        return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
            {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
            "INSUFFICIENT_EVIDENCE", next_action="freeze_target_baseline", scope_manifest_hash=spec.scope_manifest_hash)
    _, target_base_manifest = file_manifest(spec.target_base_root)
    if not spec.target_base_manifest_sha256 or target_base_manifest != spec.target_base_manifest_sha256:
        return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
            {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
            "INSUFFICIENT_EVIDENCE", next_action="freeze_target_baseline", scope_manifest_hash=spec.scope_manifest_hash, target_base_manifest_sha256=target_base_manifest)
    computed_diff_hash = diff_manifest_hash(spec.target_base_root, spec.target_root, spec.changed_paths)
    if computed_diff_hash != diff_hash:
        return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
            {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
            "BLOCK", deviations=(f"DIFF_HASH_MISMATCH:expected={computed_diff_hash}:observed={diff_hash}",), next_action="freeze_target", scope_manifest_hash=spec.scope_manifest_hash)
    if not spec.scope_manifest_hash:
        return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
            {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
            "INSUFFICIENT_EVIDENCE", next_action="freeze_scope", target_base_manifest_sha256=target_base_manifest)
    actual_mapping_hash = mapping_manifest_hash(spec.mappings)
    if not spec.mapping_manifest_sha256 or actual_mapping_hash != spec.mapping_manifest_sha256:
        return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
            {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
            "INSUFFICIENT_EVIDENCE", next_action="freeze_mapping", scope_manifest_hash=spec.scope_manifest_hash, target_base_manifest_sha256=target_base_manifest, mapping_manifest_sha256=actual_mapping_hash)
    hard: list[str] = []
    checked_files: list[str] = []
    checked_symbols: list[str] = []
    direct_reuse: list[str] = []
    thin_adaptations: list[str] = []
    platform_shell: list[str] = []
    authorized_new: list[str] = []
    tests: list[str] = []
    for mapping in spec.mappings:
        target_path = _safe_file(target_root, mapping.target_path, "target path")
        target_text = _read_text(target_path)
        source_text = None
        if mapping.source_path:
            source_path = _safe_file(source_root, mapping.source_path, "source path")
            source_text = _read_text(source_path)
            checked_files.extend((mapping.source_path, mapping.target_path))
        else:
            checked_files.append(mapping.target_path)
        findings, symbols, _ = _mapping_findings(mapping, source_text, target_text)
        hard.extend(findings); checked_symbols.extend(symbols); tests.extend(mapping.regression_tests)
        if mapping.classification == "DIRECT_REUSE": direct_reuse.append(mapping.mapping_id)
        elif mapping.classification == "THIN_ADAPTER": thin_adaptations.append(mapping.mapping_id)
        elif mapping.classification == "PLATFORM_SHELL": platform_shell.append(mapping.mapping_id)
        else: authorized_new.append(mapping.mapping_id)
    status = "BLOCK" if hard else "PASS"
    return SourceFidelityReceipt(receipt_id, spec.run_id, spec.task_id, target_manifest, result_revision, diff_hash,
        {"repository": spec.repository, "commit": spec.commit, "manifest_sha256": source_manifest}, spec.mapping_revision,
        status, tuple(sorted(set(checked_files))), tuple(sorted(set(checked_symbols))), tuple(direct_reuse), tuple(thin_adaptations),
        tuple(platform_shell), tuple(authorized_new), tuple(hard), (), tuple(tests), tuple(evidence_refs),
        "integrate" if status == "PASS" else "correct", scope_manifest_hash=spec.scope_manifest_hash, target_base_manifest_sha256=target_base_manifest, mapping_manifest_sha256=actual_mapping_hash, producer_role="source-fidelity-agent")


def load_spec(path: str | Path) -> ReferenceSpec:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid source fidelity spec") from exc
    if not isinstance(raw, Mapping):
        raise ContractError("source fidelity spec must be an object")
    mappings = tuple(SourceMapping(**item) for item in raw.get("mappings", ()))
    values = dict(raw); values["mappings"] = mappings
    for key in ("source_files", "changed_paths", "allowed_new_paths"):
        values[key] = tuple(values.get(key, ()))
    return ReferenceSpec(**values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="inspect a frozen source-fidelity mapping")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--receipt-id", required=True)
    parser.add_argument("--result-revision", required=True)
    parser.add_argument("--diff-hash", required=True)
    parser.add_argument("--evidence-ref", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        receipt = inspect(load_spec(args.spec), args.receipt_id, args.result_revision, args.diff_hash, tuple(args.evidence_ref))
    except (ContractError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, separators=(",", ":")))
        return 2
    print(json.dumps({"ok": receipt.status == "PASS", "receipt": receipt.as_dict()}, ensure_ascii=False, separators=(",", ":")))
    return 0 if receipt.status == "PASS" else 4


if __name__ == "__main__":
    raise SystemExit(main())
