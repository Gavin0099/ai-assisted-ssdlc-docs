"""REPORT-3B v0.1: report data models and read-only, fail-closed admission.

parse_report_data is structural only. load_report_data also checks fixed inputs,
source relationships and every ArtifactRef. It never migrates or renders data.
The legacy corpus export has no repo: its pinned manifest supplies that identity.
Matching metadata is not Git, quote/span, execution or approval verification.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

import yaml

from tools.corpus_assessment_engine import CorpusAssessmentReport, parse_corpus_assessment_dict
from tools.repo_corpus_resolver import CorpusResolverError, glob_to_regex
from tools.validate_ssdf_assessment import (
    ALLOWED_BASIS_TYPES, DEFAULT_TASKS_REF, load_and_validate_reference,
    validate_ssdf_assessment,
)
from tools.validate_target_manifest import parse_target_manifest

DETAIL_KEYS = (
    "規則依據與效力", "目前哪裡有問題", "要修改或補什麼", "完成確認方式",
    "適用條件與待確認事項", "對判定的影響與不能宣稱", "修訂句",
)


class ReportContractError(ValueError):
    """An invalid input; no accepted bundle is returned on this path."""


def _fail(label: str, message: str) -> None:
    raise ReportContractError(f"{label}: {message}")


def _object(value: Any, label: str, required: set[str], optional: set[str] = frozenset()) -> dict:
    if type(value) is not dict or any(type(k) is not str for k in value):
        _fail(label, "expected an object with string keys")
    if required - value.keys() or value.keys() - required - optional:
        _fail(label, f"missing/unknown fields: {sorted(required - value.keys())}/{sorted(value.keys() - required - optional)}")
    return value


def _text(value: Any, label: str) -> str:
    if type(value) is not str or not value.strip():
        _fail(label, "expected a non-empty string")
    return value


def _list(value: Any, label: str) -> list:
    if type(value) is not list:
        _fail(label, "expected an array")
    return value


def _texts(value: Any, label: str) -> tuple[str, ...]:
    return tuple(_text(x, label) for x in _list(value, label))


def _choice(value: Any, choices: set[str], label: str) -> str:
    value = _text(value, label)
    if value not in choices:
        _fail(label, "unknown value")
    return value


def _digest(value: Any, label: str, length: int = 64) -> str:
    value = _text(value, label)
    if not re.fullmatch(r"[0-9a-fA-F]{" + str(length) + r"}", value):
        _fail(label, f"expected {length} hex characters")
    return value.lower()


def _relative_path(value: Any, label: str) -> str:
    value = _text(value, label)
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if (value != value.strip() or normalized.startswith("/") or PureWindowsPath(value).drive
            or ":" in value or any(ord(c) < 32 for c in value)
            or any(p in ("", ".", "..") or p.endswith((" ", ".")) for p in parts)):
        _fail(label, "expected a clean relative path; absolute/traversal/ambiguous paths forbidden")
    return normalized


def _unique(values: list | tuple, label: str) -> None:
    if len(values) != len(set(values)):
        _fail(label, "duplicate identity")


def decode_json(raw: bytes, label: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail(label, "duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: _fail(label, "non-finite JSON number"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ReportContractError):
            raise
        _fail(label, f"invalid UTF-8 JSON: {exc}")


class _UniqueYamlLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    pairs = loader.construct_pairs(node, deep=deep)
    result = {}
    for key, value in pairs:
        if type(key) is not str or key in result:
            _fail("yaml", "non-string or duplicate mapping key")
        result[key] = value
    return result


_UniqueYamlLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def _decode_yaml(raw: bytes, label: str) -> dict:
    try:
        data = yaml.load(raw.decode("utf-8"), Loader=_UniqueYamlLoader)
        if type(data) is not dict:
            _fail(label, "expected a YAML object")
        return data
    except (UnicodeError, yaml.YAMLError, RecursionError) as exc:
        _fail(label, f"invalid YAML: {exc}")


@dataclass(frozen=True)
class ArtifactRef:
    path: str
    sha256: str


def parse_artifact_ref(value: Any, label: str = "artifact_ref") -> ArtifactRef:
    value = _object(value, label, {"path", "sha256"})
    return ArtifactRef(_relative_path(value["path"], label), _digest(value["sha256"], label))


class ArtifactStore:
    """Infrastructure: caller-owned root, opened-handle verification, no writes.

    Symlinks/junctions inside the root are allowed; targets outside it are not.
    Verify the actual opened file before reading; the descriptor pins the file
    even if a concurrent process replaces its pathname after verification.
    """
    def __init__(self, report_root: Path):
        try:
            self.root = Path(report_root).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            _fail("report_root", str(exc))
        if not self.root.is_dir():
            _fail("report_root", "expected a directory")

    def resolve(self, relative: str, from_file: Path | None = None) -> Path:
        relative = _relative_path(relative, "artifact.path")
        base = self.root if from_file is None else Path(from_file).parent
        if not base.is_relative_to(self.root):
            _fail("artifact.path", "reference base escapes report root")
        try:
            resolved = (base / relative).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            _fail("artifact.path", f"unavailable: {exc}")
        if not resolved.is_relative_to(self.root):
            _fail("artifact.path", "resolved target escapes report root")
        if not resolved.is_file():
            _fail("artifact.path", "expected a regular file")
        return resolved

    def read_path(self, relative: str, from_file: Path | None = None) -> tuple[Path, bytes]:
        path = self.resolve(relative, from_file)
        try:
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
            with os.fdopen(os.open(path, flags), "rb") as opened:
                if not stat.S_ISREG(os.fstat(opened.fileno()).st_mode):
                    _fail("artifact.read", "opened target is not a regular file")
                actual = self._opened_path(opened.fileno())
                if not actual.is_relative_to(self.root):
                    _fail("artifact.path", "opened target escapes report root")
                return actual, opened.read()
        except OSError as exc:
            _fail("artifact.read", str(exc))

    @staticmethod
    def _opened_path(descriptor: int) -> Path:
        """OS-backed handle identity, never a re-resolution of the input name.

        Windows uses GetFinalPathNameByHandleW; Linux uses procfs descriptor
        metadata. If that metadata is unavailable, reject before reading bytes.
        """
        if os.name == "nt":
            import ctypes
            import msvcrt
            from ctypes import wintypes

            final_path = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
            final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
            final_path.restype = wintypes.DWORD
            buffer = ctypes.create_unicode_buffer(32768)
            count = final_path(msvcrt.get_osfhandle(descriptor), buffer, len(buffer), 0)
            if not count:
                raise ctypes.WinError(ctypes.get_last_error())
            if count >= len(buffer):
                raise OSError("opened artifact path exceeds the handle-path buffer")
            name = buffer.value
            if name.startswith("\\\\?\\UNC\\"):
                name = "\\\\" + name[8:]
            elif name.startswith("\\\\?\\"):
                name = name[4:]
            return Path(name)
        return Path(os.readlink(f"/proc/self/fd/{descriptor}"))

    def read_ref(self, ref: ArtifactRef, from_file: Path) -> tuple[Path, bytes]:
        # Revalidate values even if a caller directly constructed the dataclass.
        ref = parse_artifact_ref({"path": ref.path, "sha256": ref.sha256})
        path, raw = self.read_path(ref.path, from_file)
        if hashlib.sha256(raw).hexdigest() != ref.sha256:
            _fail("artifact.hash", f"digest mismatch: {ref.path}")
        return path, raw


@dataclass(frozen=True)
class BasisRecord:
    type: str
    rationale: str
    task_id: str | None
    source: str | None


def _basis(value: Any, label: str) -> BasisRecord:
    v = _object(value, label, {"type", "rationale"}, {"task_id", "source"})
    kind = _choice(v["type"], ALLOWED_BASIS_TYPES, label)
    task = _text(v["task_id"], label) if "task_id" in v else None
    source = _text(v["source"], label) if "source" in v else None
    if kind == "nist_normative" and (task is None or source is None):
        _fail(label, "normative basis requires task_id and source")
    return BasisRecord(kind, _text(v["rationale"], label), task, source)


@dataclass(frozen=True)
class SupplementItem:
    text: str
    source_refs: tuple[str, ...]
    basis_refs: tuple[int, ...]


@dataclass(frozen=True)
class TaskSupplement:
    finding_id: str
    document_refs: tuple[str, ...]
    gap_items: tuple[SupplementItem, ...] | None
    improvement_items: tuple[SupplementItem, ...] | None


def _items(value: Any, label: str) -> tuple[SupplementItem, ...] | None:
    if value is None:
        return None
    result = []
    for item in _list(value, label):
        v = _object(item, label, {"text", "source_refs", "basis_refs"})
        indexes = _list(v["basis_refs"], label)
        if any(type(i) is not int or i < 0 for i in indexes):
            _fail(label, "basis indexes must be non-negative integers")
        result.append(SupplementItem(_text(v["text"], label), _texts(v["source_refs"], label), tuple(indexes)))
    return tuple(result)


@dataclass(frozen=True)
class ActionLocation:
    source_ref: str
    source_scope: str
    display_text: str


@dataclass(frozen=True)
class TextEvidence:
    statement: str
    evidence_refs: tuple[ArtifactRef, ...]


@dataclass(frozen=True)
class EngineerAction:
    action_id: str
    group: str
    kind: str
    priority: str | None
    priority_reason: str | None
    scope_labels: tuple[str, ...]
    finding_refs: tuple[str, ...]
    locations: tuple[ActionLocation, ...]
    basis: tuple[BasisRecord, ...]
    details: tuple[tuple[str, str], ...]
    tracking: TextEvidence | None


@dataclass(frozen=True)
class AuxiliarySource:
    source_ref: str
    artifact_ref: ArtifactRef


@dataclass(frozen=True)
class SourceAuthority:
    path: str
    state: str | None
    raw_status: str | None
    status_source_ref: str | ArtifactRef | None
    approval_ref: ArtifactRef | None


@dataclass(frozen=True)
class ReportData:
    contract_version: str
    report_id: str
    assessment_ref: ArtifactRef
    corpus_metadata_ref: ArtifactRef
    task_supplements: tuple[TaskSupplement, ...]
    actions: tuple[EngineerAction, ...] | None
    auxiliary_sources: tuple[AuxiliarySource, ...]
    source_authority: tuple[SourceAuthority, ...]
    retained_content_refs: tuple[ArtifactRef, ...]


def _action(value: Any) -> EngineerAction:
    v = _object(value, "action", {"action_id", "group", "kind", "priority", "priority_reason",
                                "scope_labels", "finding_refs", "locations", "basis", "details", "tracking"})
    aid = _text(v["action_id"], "action_id")
    if not re.fullmatch(r"E-\d{2,}", aid):
        _fail("action_id", "expected stable E-xx ID")
    priority = None if v["priority"] is None else _choice(v["priority"], {"P0", "P1", "P2", "P3"}, "priority")
    reason = None if v["priority_reason"] is None else _text(v["priority_reason"], "priority_reason")
    if (priority is None) != (reason is None):
        _fail("priority", "priority and reason must both be null or both provided")
    locations = []
    for location in _list(v["locations"], "locations"):
        loc = _object(location, "location", {"source_ref", "source_scope", "display_text"})
        locations.append(ActionLocation(_text(loc["source_ref"], "location"),
                                       _choice(loc["source_scope"], {"corpus", "auxiliary"}, "source_scope"),
                                       _text(loc["display_text"], "location")))
    basis = tuple(_basis(b, "action.basis") for b in _list(v["basis"], "action.basis"))
    if not locations or not basis:
        _fail("action", "locations and basis cannot be empty")
    details = _object(v["details"], "action.details", set(DETAIL_KEYS))
    tracking = None
    if v["tracking"] is not None:
        t = _object(v["tracking"], "tracking", {"statement", "evidence_refs"})
        tracking = TextEvidence(_text(t["statement"], "tracking"), tuple(parse_artifact_ref(r) for r in _list(t["evidence_refs"], "tracking")))
    return EngineerAction(aid, _choice(v["group"], {"A", "B", "C"}, "group"), _text(v["kind"], "kind"),
                          priority, reason, _texts(v["scope_labels"], "scope_labels"),
                          _texts(v["finding_refs"], "finding_refs"), tuple(locations), basis,
                          tuple((key, _text(details[key], "action.details")) for key in DETAIL_KEYS), tracking)


def parse_report_data(value: Any) -> ReportData:
    """Pure strict parsing; null is retained and never replaced with []."""
    v = _object(value, "report_data", {"contract_version", "report_id", "assessment_ref", "corpus_metadata_ref",
                                     "task_supplements", "actions", "auxiliary_sources", "source_authority", "retained_content_refs"})
    supplements = []
    for item in _list(v["task_supplements"], "task_supplements"):
        s = _object(item, "supplement", {"finding_id", "document_refs", "gap_items", "improvement_items"})
        supplements.append(TaskSupplement(_text(s["finding_id"], "finding_id"), _texts(s["document_refs"], "document_refs"),
                                          _items(s["gap_items"], "gap_items"), _items(s["improvement_items"], "improvement_items")))
    auxiliary = []
    for item in _list(v["auxiliary_sources"], "auxiliary_sources"):
        a = _object(item, "auxiliary_source", {"source_ref", "artifact_ref"})
        auxiliary.append(AuxiliarySource(_relative_path(a["source_ref"], "auxiliary_source"), parse_artifact_ref(a["artifact_ref"])))
    authority = []
    for item in _list(v["source_authority"], "source_authority"):
        a = _object(item, "authority", {"path", "state", "raw_status", "status_source_ref", "approval_ref"})
        state = None if a["state"] is None else _choice(a["state"], {"draft", "under_review", "approved", "unspecified"}, "authority.state")
        raw_status = None if a["raw_status"] is None else _text(a["raw_status"], "raw_status")
        status_ref = a["status_source_ref"]
        if status_ref is not None:
            status_ref = parse_artifact_ref(status_ref) if type(status_ref) is dict else _text(status_ref, "status_source_ref")
        approval = None if a["approval_ref"] is None else parse_artifact_ref(a["approval_ref"])
        if (state is None and (raw_status is not None or status_ref is not None or approval is not None)
                or state == "unspecified" and (raw_status is not None or status_ref is None)
                or state in {"draft", "under_review", "approved"} and (raw_status is None or status_ref is None)):
            _fail("authority", "state/raw status/source are contradictory or lack observation evidence")
        authority.append(SourceAuthority(_relative_path(a["path"], "authority.path"), state, raw_status, status_ref, approval))
    return ReportData(_choice(v["contract_version"], {"0.1"}, "contract_version"), _text(v["report_id"], "report_id"),
                      parse_artifact_ref(v["assessment_ref"]), parse_artifact_ref(v["corpus_metadata_ref"]), tuple(supplements),
                      None if v["actions"] is None else tuple(_action(a) for a in _list(v["actions"], "actions")),
                      tuple(auxiliary), tuple(authority), tuple(parse_artifact_ref(r) for r in _list(v["retained_content_refs"], "retained_content_refs")))


@dataclass(frozen=True)
class CorpusMetadata:
    repo: str
    commit: str
    manifest_digest: str
    corpus_digest: str
    # Exact legacy file records; auxiliary files never enter this tuple.
    files: tuple[tuple[str, str, int], ...]


@dataclass(frozen=True)
class AssessmentDocument:
    report: CorpusAssessmentReport
    sha256: str
    # Canonical full input, including observations and original basis order.
    comparison: str


@dataclass(frozen=True)
class ReportValidation:
    incomplete: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.incomplete


@dataclass(frozen=True)
class LoadedReportData:
    data: ReportData
    assessment: AssessmentDocument
    corpus: CorpusMetadata
    validation: ReportValidation
    path: Path
    sha256: str


def _source_file(ref: str, members: set[str], label: str, sentinel: bool = False) -> None:
    if ref == "<corpus>#unmentioned" and sentinel:
        return
    path = _relative_path(ref.split("#", 1)[0], label)
    if path not in members:
        _fail(label, "source not in the declared scope")


def validate_report_data(data: ReportData, assessment: CorpusAssessmentReport, corpus: CorpusMetadata,
                         reference_tasks: set[str]) -> ReportValidation:
    """Pure relationship checks, with no inference and no input mutation."""
    target = assessment.target
    if (target.repo, target.commit, target.manifest_digest, target.corpus_digest) != (
            corpus.repo, corpus.commit, corpus.manifest_digest, corpus.corpus_digest):
        _fail("assessment/corpus", "repo, commit or digest mismatch")
    members = {f[0] for f in corpus.files}
    findings = {f.finding_id: f for f in assessment.findings}
    all_ids = set(findings) | {o.finding_id for o in assessment.observations}
    _unique([s.finding_id for s in data.task_supplements], "supplement")
    incomplete = [f"supplement missing: {fid}" for fid in sorted(set(findings) - {s.finding_id for s in data.task_supplements})]
    for s in data.task_supplements:
        if s.finding_id not in findings:
            _fail("supplement", "finding does not exist or is not a task finding")
        f = findings[s.finding_id]
        for ref in s.document_refs:
            _source_file(ref, members, "document_ref")
        for label, items in [("gap", s.gap_items), ("improvement", s.improvement_items)]:
            if items is None:
                incomplete.append(f"{s.finding_id}: {label} not organized")
                continue
            for item in items:
                for index in item.basis_refs:
                    if index >= len(f.basis):
                        _fail("basis_refs", "index outside original finding basis")
                for ref in item.source_refs:
                    _source_file(ref, members, "item.source_ref", f.company_source_ref == "<corpus>#unmentioned" and f.coverage_verdict in {"MISSING", "UNRESOLVED"})
                if label == "gap" and (not item.source_refs or not any(f.basis[i].type == "nist_normative" for i in item.basis_refs)):
                    _fail("gap", "needs source comparison and normative task basis")
        if (f.coverage_verdict == "COVERED" and s.gap_items
                or f.coverage_verdict == "PARTIAL" and s.gap_items == ()):
            _fail("verdict/gap", "contradictory recorded dimensions")
    aux = {a.source_ref for a in data.auxiliary_sources}
    _unique([a.source_ref for a in data.auxiliary_sources], "auxiliary_sources")
    if aux & members:
        _fail("auxiliary_sources", "corpus member cannot be relabeled auxiliary")
    if data.actions is None:
        incomplete.append("actions not organized")
    else:
        _unique([a.action_id for a in data.actions], "action_id")
        for a in data.actions:
            if set(a.finding_refs) - all_ids:
                _fail("finding_refs", "unknown finding/observation")
            for loc in a.locations:
                _source_file(loc.source_ref, members if loc.source_scope == "corpus" else aux, "location.scope")
            for b in a.basis:
                if b.type == "nist_normative" and (b.task_id not in reference_tasks or b.source != assessment.baseline):
                    _fail("action.basis", "normative source/task does not match the baseline")
    _unique([a.path for a in data.source_authority], "source_authority")
    if {a.path for a in data.source_authority} != members:
        _fail("source_authority", "missing or extra corpus member")
    for a in data.source_authority:
        if a.state is None:
            incomplete.append(f"authority uncollected: {a.path}")
        if isinstance(a.status_source_ref, str):
            _source_file(a.status_source_ref, members, "status_source_ref")
    return ReportValidation(tuple(incomplete))


@dataclass(frozen=True)
class _PinnedAssessmentInput:
    """Adapter to reuse the existing linter against already verified bytes."""
    text: str

    def exists(self):
        return True

    def read_text(self, encoding="utf-8"):
        return self.text


def load_assessment_bytes(raw: bytes) -> AssessmentDocument:
    payload = _decode_yaml(raw, "assessment")
    # Prevent coercion/crashes in the legacy parser/linter before using them.
    header = _object(payload.get("assessment"), "assessment.header", {"id", "baseline", "target", "scope_tasks", "claim_boundary"})
    _text(header["id"], "assessment.id")
    _text(header["baseline"], "assessment.baseline")
    _texts(header["scope_tasks"], "scope_tasks")
    _texts(header["claim_boundary"], "claim_boundary")
    target = _object(header["target"], "assessment.target", {"type", "repo", "commit", "manifest_path", "manifest_digest", "corpus_digest"})
    for key in target:
        _text(target[key], "assessment.target")
    _relative_path(target["manifest_path"], "manifest_path")
    for f in _list(payload.get("results"), "assessment.results"):
        f = _object(f, "assessment.finding", {"finding_id", "finding_type", "task_id", "company_source_ref", "company_statement", "coverage_verdict", "basis", "assessment_rationale", "identified_evidence", "evidence_strength", "review_queue_recommendation", "cannot_claim"})
        for key in ["finding_id", "finding_type", "task_id", "company_source_ref", "company_statement", "coverage_verdict", "evidence_strength", "review_queue_recommendation"]:
            _text(f[key], "assessment.finding")
        for key in ["assessment_rationale", "cannot_claim"]:
            _texts(f[key], "assessment.finding")
        for b in _list(f["basis"], "basis"):
            _basis(b, "assessment.basis")
        for e in _list(f["identified_evidence"], "identified_evidence"):
            e = _object(e, "identified_evidence", {"type", "source_ref"})
            _text(e["type"], "identified_evidence")
            _text(e["source_ref"], "identified_evidence")
    for o in _list(payload.get("non_normative_observations", []), "observations"):
        o = _object(o, "observation", {"finding_id", "finding_type", "company_source_ref", "observation", "basis", "review_queue_recommendation", "cannot_claim"})
        for key in ["finding_id", "finding_type", "company_source_ref", "observation", "review_queue_recommendation"]:
            _text(o[key], "observation")
        _texts(o["cannot_claim"], "observation")
        if type(o["basis"]) is not str:
            for b in _list(o["basis"], "observation.basis"):
                if type(b) is not str:
                    _basis(b, "observation.basis")
    try:
        errors = validate_ssdf_assessment(_PinnedAssessmentInput(raw.decode("utf-8")))
        if errors:
            _fail("assessment", "; ".join(errors))
        report = parse_corpus_assessment_dict(payload)
        # ID may differ across a documented sync. Everything else stays bound.
        comparison_header = {k: v for k, v in header.items() if k != "id"}
        comparison_header["target"] = {
            **{k: v for k, v in target.items() if k != "manifest_path"},
            "commit": report.target.commit,
            "manifest_digest": report.target.manifest_digest,
            "corpus_digest": report.target.corpus_digest,
        }
        comparison_payload = {**payload, "assessment": comparison_header}
        comparison = json.dumps(comparison_payload, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        if isinstance(exc, ReportContractError):
            raise
        _fail("assessment", str(exc))
    return AssessmentDocument(report, hashlib.sha256(raw).hexdigest(), comparison)


def _load_corpus(raw: bytes, manifest_raw: bytes) -> CorpusMetadata:
    m = _object(decode_json(raw, "corpus_metadata"), "corpus_metadata", {"target_commit", "total_files", "total_bytes", "manifest_digest", "corpus_digest", "files"})
    try:
        manifest = parse_target_manifest(_decode_yaml(manifest_raw, "manifest"))
    except ValueError as exc:
        _fail("manifest", str(exc))
    commit = _digest(m["target_commit"], "corpus.commit", 40)
    manifest_digest = _digest(m["manifest_digest"], "manifest_digest")
    if manifest.digest != manifest_digest or manifest.target.commit.lower() != commit:
        _fail("manifest/corpus", "manifest digest or commit mismatch")
    records = []
    for item in _list(m["files"], "corpus.files"):
        f = _object(item, "corpus.file", {"relative_path", "content_hash", "byte_size"})
        if type(f["byte_size"]) is not int or f["byte_size"] < 0:
            _fail("byte_size", "expected a non-negative integer")
        records.append((_relative_path(f["relative_path"], "corpus.path"), _digest(f["content_hash"], "content_hash"), f["byte_size"]))
    _unique([f[0] for f in records], "corpus.files")
    try:
        includes = [glob_to_regex(p) for p in manifest.authority_surface.include]
        excludes = [glob_to_regex(p) for p in manifest.authority_surface.exclude]
    except CorpusResolverError as exc:
        _fail("manifest.authority_surface", str(exc))
    for path, _, _ in records:
        if not any(p.fullmatch(path) for p in includes) or any(p.fullmatch(path) for p in excludes):
            _fail("corpus.scope", "file is outside the pinned manifest authority surface")
    if (not records or type(m["total_files"]) is not int or type(m["total_bytes"]) is not int
            or m["total_files"] != len(records) or m["total_bytes"] != sum(f[2] for f in records)):
        _fail("corpus.totals", "invalid/mismatched counts")
    digest = _digest(m["corpus_digest"], "corpus_digest")
    actual = hashlib.sha256("".join(f"{p}\t{h}\n" for p, h, _ in sorted(records)).encode("utf-8")).hexdigest()
    if digest != actual:
        _fail("corpus_digest", "file membership fingerprint mismatch")
    return CorpusMetadata(manifest.target.repo, commit, manifest_digest, digest, tuple(records))


def load_report_data(relative_path: str, report_root: Path, *, authorized_auxiliary_sources: frozenset[str] = frozenset()) -> LoadedReportData:
    """Full read-only admission. The caller, not JSON, authorizes auxiliary paths.

    A complete=False result is valid but explicitly unfinished; future renderers
    must not use it for a complete handoff. All invalid references raise instead.
    """
    store = ArtifactStore(report_root)
    path, raw = store.read_path(relative_path)
    data = parse_report_data(decode_json(raw, "report_data"))
    auxiliary_paths = {a.source_ref for a in data.auxiliary_sources}
    if auxiliary_paths - authorized_auxiliary_sources:
        _fail("auxiliary.authorization", "source is not in caller-authorized scope")
    assessment_path, assessment_raw = store.read_ref(data.assessment_ref, path)
    assessment = load_assessment_bytes(assessment_raw)
    _, metadata_raw = store.read_ref(data.corpus_metadata_ref, path)
    _, manifest_raw = store.read_path(assessment.report.target.manifest_path, assessment_path)
    corpus = _load_corpus(metadata_raw, manifest_raw)
    members = {f[0] for f in corpus.files}
    for finding in assessment.report.findings:
        sentinel = finding.coverage_verdict in {"MISSING", "UNRESOLVED"}
        _source_file(finding.company_source_ref, members, "assessment.source_ref", sentinel)
        for evidence in finding.identified_evidence:
            _source_file(evidence.source_ref, members, "assessment.evidence_ref", sentinel)
    for observation in assessment.report.observations:
        _source_file(observation.company_source_ref, members, "observation.source_ref")
    tasks, _, errors = load_and_validate_reference(DEFAULT_TASKS_REF)
    if errors:
        _fail("reference", "; ".join(errors))
    validation = validate_report_data(data, assessment.report, corpus, tasks)
    refs = list(data.retained_content_refs) + [a.artifact_ref for a in data.auxiliary_sources]
    for authority in data.source_authority:
        if isinstance(authority.status_source_ref, ArtifactRef):
            refs.append(authority.status_source_ref)
        if authority.approval_ref is not None:
            refs.append(authority.approval_ref)
    for action in data.actions or ():
        if action.tracking is not None:
            refs.extend(action.tracking.evidence_refs)
    for ref in refs:
        store.read_ref(ref, path)
    return LoadedReportData(data, assessment, corpus, validation, path, hashlib.sha256(raw).hexdigest())
