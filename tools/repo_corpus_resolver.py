#!/usr/bin/env python3
"""Deterministic Repo Corpus Resolver for SSDLC Real Repo Assessments (Phase S1-B).

Materializes authoritative documentation files from a target Git repository
at a fixed commit SHA based on the authority surface (include/exclude) defined
in the Target Manifest.

Architectural Guarantees:
- DDD Domain Models: Immutable CorpusFile and CorpusSnapshot value objects.
- SDD Interface First: ICorpusGitClient and IRepoCorpusResolver protocols.
- Zero Working-Tree Checkout: Inspects Git tree objects directly via git ls-tree
  and git cat-file without touching or dirtying the local working directory.
- Exclude Always Wins: Exclude globs unconditionally override include matches.
- Regular Files Only: Symlinks (git mode 120000) are safely ignored.
- UTF-8 Enforcement: Prohibits non-UTF-8 or binary files (fail-closed).
- Deterministic Digest: Computes reproducible SHA-256 corpus digest based on
  strictly sorted relative paths and file content hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

try:
    from tools.validate_target_manifest import (
        TargetManifest,
        TargetManifestValidationError,
        parse_target_manifest,
        validate_target_manifest_file,
    )
except ModuleNotFoundError:
    from validate_target_manifest import (
        TargetManifest,
        TargetManifestValidationError,
        parse_target_manifest,
        validate_target_manifest_file,
    )


class CorpusResolverError(RuntimeError):
    """Raised when repository corpus resolution fails closed."""


@dataclass(frozen=True)
class CorpusFile:
    """Immutable domain model representing an authoritative document in the corpus."""

    relative_path: str
    content_hash: str
    byte_size: int
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "content_hash": self.content_hash,
            "byte_size": self.byte_size,
        }


@dataclass(frozen=True)
class CorpusSnapshot:
    """Immutable aggregate root representing a materialized documentation corpus."""

    manifest: TargetManifest
    target_commit: str
    files: tuple[CorpusFile, ...]
    total_files: int
    total_bytes: int
    corpus_digest: str
    manifest_digest: str = ""

    def __post_init__(self) -> None:
        if not self.manifest_digest:
            canonical = {
                "target": {
                    "source_type": self.manifest.target.source_type,
                    "repo": self.manifest.target.repo,
                    "commit": self.manifest.target.commit,
                },
                "authority_surface": {
                    "include": list(self.manifest.authority_surface.include),
                    "exclude": list(self.manifest.authority_surface.exclude),
                },
                "baseline": {
                    "framework": self.manifest.baseline.framework,
                    "version": self.manifest.baseline.version,
                },
                "mode": {
                    "read_only": self.manifest.mode.read_only,
                },
            }
            raw = json.dumps(canonical, sort_keys=True).encode("utf-8")
            object.__setattr__(self, "manifest_digest", hashlib.sha256(raw).hexdigest())

    def paths(self) -> tuple[str, ...]:
        return tuple(f.relative_path for f in self.files)

    def get_file(self, path: str) -> CorpusFile | None:
        normalized = path.replace("\\", "/").strip("/")
        for f in self.files:
            if f.relative_path == normalized:
                return f
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_commit": self.target_commit,
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "manifest_digest": self.manifest_digest,
            "corpus_digest": self.corpus_digest,
            "files": [f.to_dict() for f in self.files],
        }


UNSUPPORTED_GLOB_CHARS = set("[]{}!~^")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a POSIX repository-relative glob pattern into an anchored regex.

    Only supports '*', '**', and '?' (Supported Glob Subset v1).
    Other glob syntax (e.g. bracket classes, braces, negation) is rejected fail-closed.
    """
    for ch in UNSUPPORTED_GLOB_CHARS:
        if ch in pattern:
            raise CorpusResolverError(
                f"Unsupported glob syntax character '{ch}' in pattern '{pattern}'; "
                "only '*', '**', '?' are supported in Supported Glob Subset v1."
            )

    pattern = pattern.replace("\\", "/").strip()
    if pattern.startswith("/"):
        pattern = pattern[1:]

    regex_parts = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i : i + 3] == "**/":
            regex_parts.append("(?:.+/)?")
            i += 3
        elif pattern[i : i + 3] == "/**":
            regex_parts.append("(?:/.*)?")
            i += 3
        elif pattern[i : i + 2] == "**":
            regex_parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            regex_parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            regex_parts.append("[^/]")
            i += 1
        else:
            regex_parts.append(re.escape(pattern[i]))
            i += 1
    regex_parts.append("$")
    return re.compile("".join(regex_parts))


class ICorpusGitClient(Protocol):
    """Protocol for low-level Git repository tree and blob access."""

    def verify_commit_exists(self, repo_path: Path, commit: str) -> bool:
        ...

    def get_remote_url(self, repo_path: Path, remote_name: str = "origin") -> str | None:
        ...

    def list_tree_entries(
        self, repo_path: Path, commit: str
    ) -> list[tuple[str, str, str, str]]:
        """List tree objects returning tuples of (mode, type, object_sha, relative_path)."""
        ...

    def read_blob_bytes(self, repo_path: Path, commit: str, rel_path: str) -> bytes:
        ...


class GitCliClient:
    """Infrastructure implementation of ICorpusGitClient using local Git CLI."""

    def __init__(self, git_binary: str = "git") -> None:
        self.git_binary = git_binary

    def _run(self, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                [self.git_binary] + args,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as exc:
            raise CorpusResolverError(f"Failed to execute git command: {exc}") from exc

    def verify_commit_exists(self, repo_path: Path, commit: str) -> bool:
        if not repo_path.is_dir():
            return False
        res = self._run(["cat-file", "-e", f"{commit}^{{commit}}"], cwd=repo_path)
        return res.returncode == 0

    def get_remote_url(self, repo_path: Path, remote_name: str = "origin") -> str | None:
        if not repo_path.is_dir():
            return None
        res = self._run(["config", "--get", f"remote.{remote_name}.url"], cwd=repo_path)
        if res.returncode == 0:
            val = res.stdout.strip()
            return val if val else None
        return None

    def list_tree_entries(
        self, repo_path: Path, commit: str
    ) -> list[tuple[str, str, str, str]]:
        cmd = [
            self.git_binary,
            "-c",
            "core.quotepath=false",
            "ls-tree",
            "-r",
            "-z",
            "--full-tree",
            commit,
        ]
        try:
            res = subprocess.run(cmd, cwd=repo_path, capture_output=True, check=False)
        except OSError as exc:
            raise CorpusResolverError(f"Failed to execute git command: {exc}") from exc

        if res.returncode != 0:
            err_msg = res.stderr.decode("utf-8", errors="replace").strip()
            raise CorpusResolverError(f"Failed to list git tree at commit {commit}: {err_msg}")

        entries: list[tuple[str, str, str, str]] = []
        # -z flag outputs NUL-delimited records: "<mode> <type> <oid>\t<path>\x00"
        raw_records = res.stdout.split(b"\0")
        for record in raw_records:
            if not record:
                continue
            if b"\t" not in record:
                continue
            meta_b, path_b = record.split(b"\t", 1)
            parts = meta_b.split(b" ", 2)
            if len(parts) == 3:
                mode_b, otype_b, oid_b = parts
                mode = mode_b.decode("ascii", errors="replace")
                otype = otype_b.decode("ascii", errors="replace")
                oid = oid_b.decode("ascii", errors="replace")
                try:
                    rel_path = path_b.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise CorpusResolverError(
                        f"Repository path contains non-UTF-8 bytes: {path_b!r}: {exc}"
                    ) from exc
                # Normalize path separators
                entries.append((mode, otype, oid, rel_path.replace("\\", "/")))
        return entries

    def read_blob_bytes(self, repo_path: Path, commit: str, rel_path: str) -> bytes:
        cmd = [self.git_binary, "cat-file", "-p", f"{commit}:{rel_path}"]
        try:
            res = subprocess.run(cmd, cwd=repo_path, capture_output=True, check=False)
        except OSError as exc:
            raise CorpusResolverError(f"Failed to read git blob: {exc}") from exc

        if res.returncode != 0:
            raise CorpusResolverError(
                f"Failed to read file '{rel_path}' at commit {commit}: {res.stderr.decode('utf-8', errors='replace')}"
            )
        return res.stdout


class IRepoCorpusResolver(Protocol):
    """Protocol for resolving and materializing documentation corpora."""

    def resolve(
        self, manifest: TargetManifest, repo_path: Path | None = None
    ) -> CorpusSnapshot:
        ...


DISALLOWED_C0_BYTES = set(range(0x00, 0x20)) - {0x09, 0x0A, 0x0D}


class RepoCorpusResolver:
    """Deterministic Resolver materializing documentation from a Target Manifest."""

    def __init__(self, git_client: ICorpusGitClient | None = None) -> None:
        self.git_client = git_client or GitCliClient()

    def resolve(
        self, manifest: TargetManifest, repo_path: Path | None = None
    ) -> CorpusSnapshot:
        # Determine actual local filesystem repo path
        actual_repo_path: Path
        if repo_path is not None:
            actual_repo_path = Path(repo_path).resolve()
        elif manifest.target.source_type == "local_git":
            actual_repo_path = Path(manifest.target.repo).resolve()
        else:
            raise CorpusResolverError(
                f"Cannot resolve remote target source_type '{manifest.target.source_type}' without explicit local repo_path."
            )

        if not actual_repo_path.is_dir():
            raise CorpusResolverError(f"Target repository directory not found: {actual_repo_path}")

        # Strict provenance verification for github source_type
        if manifest.target.source_type == "github":
            claimed_repo = manifest.target.repo.strip().lower()
            origin_url = self.git_client.get_remote_url(actual_repo_path, "origin")
            if not origin_url:
                raise CorpusResolverError(
                    f"Repository at '{actual_repo_path}' has no 'origin' remote URL configured; "
                    f"cannot verify claimed github repository '{manifest.target.repo}'."
                )
            normalized_url = origin_url.strip().lower().replace("\\", "/")
            if normalized_url.endswith(".git"):
                normalized_url = normalized_url[:-4]
            if not (
                normalized_url.endswith(f"/{claimed_repo}")
                or normalized_url.endswith(f":{claimed_repo}")
                or normalized_url == claimed_repo
            ):
                raise CorpusResolverError(
                    f"Target repository at '{actual_repo_path}' remote origin '{origin_url}' "
                    f"does not match claimed github repository '{manifest.target.repo}'."
                )

        target_commit = manifest.target.commit
        if not self.git_client.verify_commit_exists(actual_repo_path, target_commit):
            raise CorpusResolverError(
                f"Commit not found in repository {actual_repo_path}: {target_commit}"
            )

        # 1. List all tree entries in target commit (NUL-delimited, unquoted)
        tree_entries = self.git_client.list_tree_entries(actual_repo_path, target_commit)

        # 2. Compile include and exclude regexes
        include_regexes = [glob_to_regex(p) for p in manifest.authority_surface.include]
        exclude_regexes = [glob_to_regex(p) for p in manifest.authority_surface.exclude]

        # 3. Filter candidates:
        # - Must be regular file blob (mode != '120000' symlink and type == 'blob')
        # - Must match at least one include pattern
        # - Must NOT match any exclude pattern (Exclude Always Wins)
        matched_paths: list[str] = []
        for mode, otype, _oid, path in tree_entries:
            if otype != "blob":
                continue
            if mode == "120000":
                # Regular files only; skip symlinks
                continue

            included = any(r.match(path) for r in include_regexes)
            if not included:
                continue

            excluded = any(r.match(path) for r in exclude_regexes)
            if excluded:
                continue

            matched_paths.append(path)

        # 4. Strict deterministic sorting by relative_path
        matched_paths.sort()

        # 5. Read blob contents, enforce strict UTF-8 text (no binary/NUL/C0), and compute file-level hashes
        materialized_files: list[CorpusFile] = []
        digest_hasher = hashlib.sha256()

        for rel_path in matched_paths:
            raw_bytes = self.git_client.read_blob_bytes(actual_repo_path, target_commit, rel_path)

            if b"\x00" in raw_bytes:
                raise CorpusResolverError(
                    f"File '{rel_path}' contains NUL byte (binary files prohibited)."
                )
            if any(b in DISALLOWED_C0_BYTES for b in raw_bytes):
                raise CorpusResolverError(
                    f"File '{rel_path}' contains disallowed C0 control characters (binary files prohibited)."
                )

            try:
                content = raw_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise CorpusResolverError(
                    f"File '{rel_path}' is not valid UTF-8 text (binary files prohibited): {exc}"
                ) from exc

            content_hash = hashlib.sha256(raw_bytes).hexdigest()
            byte_size = len(raw_bytes)

            file_obj = CorpusFile(
                relative_path=rel_path,
                content_hash=content_hash,
                byte_size=byte_size,
                content=content,
            )
            materialized_files.append(file_obj)

            # Update corpus digest: "<relative_path>\t<content_hash>\n"
            digest_hasher.update(f"{rel_path}\t{content_hash}\n".encode("utf-8"))

        # 6. Prohibit empty corpus fail-closed
        if not materialized_files:
            raise CorpusResolverError(
                "Corpus resolution produced 0 authoritative files; empty corpus is prohibited. "
                "Verify authority_surface include/exclude patterns and target commit contents."
            )

        total_bytes = sum(f.byte_size for f in materialized_files)
        total_files = len(materialized_files)
        corpus_digest = digest_hasher.hexdigest()

        return CorpusSnapshot(
            manifest=manifest,
            target_commit=target_commit,
            files=tuple(materialized_files),
            total_files=total_files,
            total_bytes=total_bytes,
            corpus_digest=corpus_digest,
        )


def resolve_corpus_from_manifest(
    manifest_path: Path | str,
    repo_path: Path | str | None = None,
) -> CorpusSnapshot:
    """Convenience helper to load, validate Target Manifest and resolve CorpusSnapshot."""
    import yaml

    m_path = Path(manifest_path)
    if not m_path.is_file():
        raise CorpusResolverError(f"Target Manifest file not found: {m_path}")

    # Validate manifest first fail-closed
    errors = validate_target_manifest_file(m_path)
    if errors:
        raise CorpusResolverError(
            "Target manifest validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    raw_data = yaml.safe_load(m_path.read_text(encoding="utf-8"))
    manifest = parse_target_manifest(raw_data)

    resolved_repo = Path(repo_path) if repo_path is not None else None
    resolver = RepoCorpusResolver()
    return resolver.resolve(manifest, repo_path=resolved_repo)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize authoritative repository documentation into an immutable Corpus Snapshot."
    )
    parser.add_argument("manifest", type=Path, help="Path to target-manifest YAML file")
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help="Optional local path to target repository (required if source_type is github)",
    )
    parser.add_argument(
        "--export-json",
        type=Path,
        default=None,
        help="Optional file path to output corpus metadata JSON",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print human-readable summary of the resolved corpus",
    )
    args = parser.parse_args()

    try:
        snapshot = resolve_corpus_from_manifest(args.manifest, repo_path=args.repo_path)
    except Exception as exc:
        print(f"[FAIL] Corpus resolution failed: {exc}", file=sys.stderr)
        return 1

    if args.export_json:
        args.export_json.write_text(json.dumps(snapshot.to_dict(), indent=2), encoding="utf-8")
        print(f"Corpus metadata exported to: {args.export_json}")

    print("[PASS] Repository corpus materialized successfully.")
    print(f"  Target Commit : {snapshot.target_commit}")
    print(f"  Total Files   : {snapshot.total_files}")
    print(f"  Total Bytes   : {snapshot.total_bytes}")
    print(f"  Corpus Digest : {snapshot.corpus_digest}")

    if args.summary:
        print("\nAuthoritative Files:")
        for f in snapshot.files:
            print(f"  - {f.relative_path} ({f.byte_size} bytes, sha256:{f.content_hash[:8]}...)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
