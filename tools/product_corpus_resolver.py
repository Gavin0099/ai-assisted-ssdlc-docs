#!/usr/bin/env python3
"""Admit immutable, authority-bound S2 Product snapshots from pinned Git bytes."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.implementation_contracts import RepositoryIdentityStatus, _verify_repository_identity
from tools.repo_corpus_resolver import (
    CorpusFile, CorpusResolverError, GitCapabilityError, DISALLOWED_C0_BYTES, RepoCorpusResolver, glob_to_regex,
)
from tools.validate_product_target_manifest import (
    ProductTargetManifest, parse_product_target_manifest_file, verify_admitted_product_manifest,
)

_PRODUCT_SNAPSHOT_TOKEN = object()


def _relative_path(path: Any) -> str:
    if (type(path) is not str or not path or path.startswith("/") or "\\" in path
            or re.match(r"^[A-Za-z]:", path)
            or any(part in {"", ".", ".."} for part in path.split("/"))):
        raise CorpusResolverError("Product snapshot contains an invalid relative path.")
    path.encode("utf-8", errors="strict")
    return path


def _digest(value: Any) -> None:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise CorpusResolverError("Product snapshot requires lowercase SHA-256 fields.")


def product_snapshot_integrity_digest(
    *, manifest_digest: str, target_commit: str, corpus_digest: str,
    files: tuple[CorpusFile, ...],
) -> str:
    """Internal content seal; this fingerprint alone never admits a snapshot."""
    _digest(manifest_digest)
    _digest(corpus_digest)
    if type(target_commit) is not str or not re.fullmatch(r"[0-9a-f]{40}", target_commit):
        raise CorpusResolverError("Product snapshot commit must be a full lowercase SHA-1.")
    if type(files) is not tuple or not files or any(type(item) is not CorpusFile for item in files):
        raise CorpusResolverError("Product snapshot needs a non-empty immutable file tuple.")
    paths = tuple(_relative_path(item.relative_path) for item in files)
    if paths != tuple(sorted(set(paths))):
        raise CorpusResolverError("Product snapshot paths must be unique and sorted.")
    hasher = hashlib.sha256()
    hasher.update(f"manifest\t{manifest_digest}\ncommit\t{target_commit}\n".encode())
    hasher.update(f"corpus\t{corpus_digest}\n".encode())
    corpus_hasher = hashlib.sha256()
    for item in files:
        _digest(item.content_hash)
        if type(item.content) is not str or type(item.byte_size) is not int or item.byte_size < 0:
            raise CorpusResolverError("Product file metadata has incompatible types.")
        raw = item.content.encode("utf-8", errors="strict")
        if b"\x00" in raw or any(byte in DISALLOWED_C0_BYTES for byte in raw):
            raise CorpusResolverError("Product blob contains prohibited control bytes.")
        if hashlib.sha256(raw).hexdigest() != item.content_hash or len(raw) != item.byte_size:
            raise CorpusResolverError("Product file digest or byte size differs from its content.")
        corpus_hasher.update(f"{item.relative_path}\t{item.content_hash}\n".encode("utf-8"))
        hasher.update(f"{item.relative_path}\t{item.content_hash}\t{item.byte_size}\n".encode("utf-8"))
    if corpus_hasher.hexdigest() != corpus_digest:
        raise CorpusResolverError("Product corpus digest differs from its files.")
    return hasher.hexdigest()


@dataclass(frozen=True)
class ProductCorpusSnapshot:
    manifest: ProductTargetManifest
    target_commit: str
    files: tuple[CorpusFile, ...]
    total_files: int
    total_bytes: int
    manifest_digest: str
    corpus_digest: str
    _admission_token: object = field(init=False, repr=False, compare=False, default=None)
    _admission_digest: str | None = field(init=False, repr=False, compare=False, default=None)
    _identity_status: RepositoryIdentityStatus | None = field(init=False, repr=False, compare=False, default=None)
    _reason_codes: tuple[str, ...] = field(init=False, repr=False, compare=False, default=())
    _integrity_verified: bool = field(init=False, repr=False, compare=False, default=False)

    def __post_init__(self) -> None:
        try:
            manifest = verify_admitted_product_manifest(self.manifest)
            if (type(self.total_files) is not int or type(self.total_bytes) is not int
                    or self.total_files < 1 or self.total_bytes < 0):
                raise CorpusResolverError("Product snapshot totals must be strict non-negative integers.")
            if manifest.digest != self.manifest_digest or manifest.target.commit != self.target_commit:
                raise CorpusResolverError("Product snapshot identity differs from its manifest.")
            product_snapshot_integrity_digest(
                manifest_digest=self.manifest_digest, target_commit=self.target_commit,
                corpus_digest=self.corpus_digest, files=self.files,
            )
            if len(self.files) != self.total_files or sum(item.byte_size for item in self.files) != self.total_bytes:
                raise CorpusResolverError("Product snapshot file totals are inconsistent.")
            include = tuple(glob_to_regex(pattern) for pattern in manifest.authority_surface.include)
            exclude = tuple(glob_to_regex(pattern) for pattern in manifest.authority_surface.exclude)
            for item in self.files:
                if (not any(pattern.fullmatch(item.relative_path) for pattern in include)
                        or any(pattern.fullmatch(item.relative_path) for pattern in exclude)):
                    raise CorpusResolverError("Product file is outside the manifest authority surface.")
        except CorpusResolverError:
            raise
        except Exception:
            raise CorpusResolverError("Product snapshot shape or integrity is invalid.") from None

    @property
    def product_snapshot_integrity_verified(self) -> bool:
        return self._integrity_verified

    @property
    def product_repository_identity_status(self) -> RepositoryIdentityStatus:
        if self._admission_token is not _PRODUCT_SNAPSHOT_TOKEN or self._identity_status is None:
            raise CorpusResolverError("Repository identity requires an admitted Product snapshot.")
        return self._identity_status

    @property
    def product_unverified_reason_codes(self) -> tuple[str, ...]:
        return self._reason_codes

    def paths(self) -> tuple[str, ...]:
        return tuple(item.relative_path for item in self.files)

    def get_file(self, path: str) -> CorpusFile | None:
        try:
            _relative_path(path)
        except (CorpusResolverError, UnicodeError):
            return None
        return next((item for item in self.files if item.relative_path == path), None)


class _GuardedProductGitClient:
    """Vet selected tree entries before the shared materializer reads any blob."""

    def __init__(self, client: Any, manifest: ProductTargetManifest) -> None:
        self.client = client
        self.include = tuple(glob_to_regex(pattern) for pattern in manifest.authority_surface.include)
        self.exclude = tuple(glob_to_regex(pattern) for pattern in manifest.authority_surface.exclude)

    def verify_commit_exists(self, repo_path: Path, commit: str) -> bool:
        return self.client.verify_commit_exists(repo_path, commit)

    def get_remote_url(self, repo_path: Path, remote_name: str = "origin") -> str | None:
        return self.client.get_remote_url(repo_path, remote_name)

    def list_tree_entries(self, repo_path: Path, commit: str) -> list:
        entries = self.client.list_tree_entries(repo_path, commit)
        for mode, object_type, _, path in entries:
            if object_type != "blob" or mode == "120000":
                continue
            # Selection is exact on both sides of the shared materializer.
            if (not any(pattern.fullmatch(path) for pattern in self.include)
                    or any(pattern.fullmatch(path) for pattern in self.exclude)):
                continue
            _relative_path(path)
            if mode not in {"100644", "100755"}:
                raise CorpusResolverError("Selected Git blob is not a regular file.")
        return entries

    def read_blob_bytes(self, repo_path: Path, commit: str, rel_path: str) -> bytes:
        return self.client.read_blob_bytes(repo_path, commit, rel_path)


class ProductCorpusResolver:
    """Default strict identity admission; identity-only opt-in belongs to C1."""

    def __init__(self, resolver: RepoCorpusResolver | None = None) -> None:
        self._resolver = resolver or RepoCorpusResolver()

    def resolve(self, manifest: ProductTargetManifest, repo_path: Path | str | None = None) -> ProductCorpusSnapshot:
        try:
            verify_admitted_product_manifest(manifest)
            if repo_path is None and manifest.target.source_type != "local_git":
                raise CorpusResolverError("GitHub product materialization requires an explicit local root.")
            repository = Path(repo_path if repo_path is not None else manifest.target.repo).resolve()
            _verify_repository_identity(manifest.target.source_type, manifest.target.repo, repository)
            guarded_client = _GuardedProductGitClient(self._resolver.git_client, manifest)
            snapshot = RepoCorpusResolver(git_client=guarded_client).resolve(manifest, repository)
            _verify_repository_identity(manifest.target.source_type, manifest.target.repo, repository)
            admitted = ProductCorpusSnapshot(
                manifest=manifest, target_commit=snapshot.target_commit, files=snapshot.files,
                total_files=snapshot.total_files, total_bytes=snapshot.total_bytes,
                manifest_digest=snapshot.manifest_digest, corpus_digest=snapshot.corpus_digest,
            )
            seal = product_snapshot_integrity_digest(
                manifest_digest=admitted.manifest_digest, target_commit=admitted.target_commit,
                corpus_digest=admitted.corpus_digest, files=admitted.files,
            )
            object.__setattr__(admitted, "_admission_token", _PRODUCT_SNAPSHOT_TOKEN)
            object.__setattr__(admitted, "_admission_digest", seal)
            object.__setattr__(admitted, "_identity_status", RepositoryIdentityStatus.VERIFIED)
            object.__setattr__(admitted, "_integrity_verified", True)
            return admitted
        except GitCapabilityError:
            raise GitCapabilityError() from None
        except Exception:
            raise CorpusResolverError("Product corpus admission failed closed.") from None


def verify_admitted_product_snapshot(snapshot: object) -> ProductCorpusSnapshot:
    if (type(snapshot) is not ProductCorpusSnapshot
            or getattr(snapshot, "_admission_token", None) is not _PRODUCT_SNAPSHOT_TOKEN):
        raise CorpusResolverError("An admitted Product snapshot is required.")
    try:
        if (snapshot._integrity_verified is not True or snapshot._identity_status is not RepositoryIdentityStatus.VERIFIED
                or snapshot._reason_codes != () or type(snapshot._reason_codes) is not tuple):
            raise CorpusResolverError("Product admission identity or integrity metadata is inconsistent.")
        snapshot.__post_init__()
        seal = product_snapshot_integrity_digest(
            manifest_digest=snapshot.manifest_digest, target_commit=snapshot.target_commit,
            corpus_digest=snapshot.corpus_digest, files=snapshot.files,
        )
        if seal != snapshot._admission_digest:
            raise CorpusResolverError("Product snapshot differs from its admitted fingerprint.")
    except Exception:
        raise CorpusResolverError("Product snapshot failed integrity revalidation.") from None
    return snapshot


def resolve_product_corpus_from_manifest(manifest_path: Path | str, repo_path: Path | str | None = None) -> ProductCorpusSnapshot:
    manifest = parse_product_target_manifest_file(manifest_path)
    return ProductCorpusResolver().resolve(manifest, repo_path)


__all__ = ["CorpusResolverError", "ProductCorpusResolver", "ProductCorpusSnapshot",
           "resolve_product_corpus_from_manifest", "verify_admitted_product_snapshot"]
