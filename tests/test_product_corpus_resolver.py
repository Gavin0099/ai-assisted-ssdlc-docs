from __future__ import annotations

import os
import hashlib
import subprocess
import unittest
from pathlib import Path
from dataclasses import replace
from tempfile import TemporaryDirectory

from tools.product_corpus_resolver import (
    CorpusResolverError,
    ProductCorpusResolver,
    resolve_product_corpus_from_manifest,
    verify_admitted_product_snapshot,
)
from tools.repo_corpus_resolver import RepoCorpusResolver, GitCliClient
from tools.validate_product_target_manifest import parse_product_target_manifest


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )


class StaticGitClient:
    def verify_commit_exists(self, repo_path: Path, commit: str) -> bool:
        return True

    def get_remote_url(self, repo_path: Path, remote_name: str = "origin") -> str | None:
        return None

    def list_tree_entries(self, repo_path: Path, commit: str) -> list[tuple[str, str, str, str]]:
        return [
            ("100644", "blob", "a" * 40, "src/real.yml"),
            ("120000", "blob", "b" * 40, "src/linked.yml"),
        ]

    def read_blob_bytes(self, repo_path: Path, commit: str, rel_path: str) -> bytes:
        return b"value: real\n"


class ProductCorpusResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repo_dir = Path(self.temp_dir.name)
        run_git(["init", "-b", "main"], cwd=self.repo_dir)
        run_git(["config", "user.name", "S2 Test Assessor"], cwd=self.repo_dir)
        run_git(["config", "user.email", "s2-test@example.invalid"], cwd=self.repo_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _commit_files(self, files: dict[str, str | bytes], message: str) -> str:
        for relative_path, content in files.items():
            path = self.repo_dir / relative_path
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                path.write_text(content, encoding="utf-8", newline="\n")
            else:
                path.write_bytes(content)
        run_git(["add", "."], cwd=self.repo_dir)
        run_git(["commit", "-m", message], cwd=self.repo_dir)
        return run_git(["rev-parse", "HEAD"], cwd=self.repo_dir).stdout.strip()

    def _manifest(self, commit: str, include: list[str], exclude: list[str] | None = None):
        authority_surface = {"include": include}
        if exclude is not None:
            authority_surface["exclude"] = exclude
        return parse_product_target_manifest(
            {
                "manifest_version": "1.0",
                "target": {
                    "source_type": "local_git",
                    "repo": str(self.repo_dir),
                    "commit": commit,
                },
                "authority_surface": authority_surface,
                "mode": {"read_only": True},
            }
        )

    def test_snapshot_uses_fixed_commit_and_spec_golden_digests(self) -> None:
        first_commit = self._commit_files({"src/app.yml": "value: one\n"}, "first")
        second_commit = self._commit_files({"src/app.yml": "value: two\n"}, "second")
        manifest = self._manifest(first_commit, ["src/**"])
        (self.repo_dir / "src/app.yml").write_bytes(b"value: staged\n")
        run_git(["add", "src/app.yml"], cwd=self.repo_dir)
        (self.repo_dir / "src/app.yml").write_bytes(b"value: dirty\n")
        (self.repo_dir / "src/untracked.yml").write_bytes(b"value: untracked\n")
        status_before = run_git(
            ["status", "--porcelain", "--untracked-files=all"], cwd=self.repo_dir
        ).stdout

        snapshot = ProductCorpusResolver().resolve(manifest, self.repo_dir)

        self.assertEqual(snapshot.target_commit, first_commit)
        self.assertEqual(
            run_git(["rev-parse", "HEAD"], cwd=self.repo_dir).stdout.strip(),
            second_commit,
        )
        self.assertEqual(
            run_git(["status", "--porcelain", "--untracked-files=all"], cwd=self.repo_dir).stdout,
            status_before,
        )
        self.assertEqual(snapshot.paths(), ("src/app.yml",))
        self.assertEqual(snapshot.get_file("src/app.yml").content, "value: one\n")
        self.assertEqual(
            snapshot.get_file("src/app.yml").content_hash,
            "549aa4d1f1772ca92d96a87e26660b2674dfaa167b926d9ce38a6f3a8d37b853",
        )
        self.assertEqual(
            snapshot.corpus_digest,
            "0dcabde8356d38ccb34e2233c81d38ab1ae96d69ae2fa3f45e841bcc75307e04",
        )
        self.assertEqual(snapshot.manifest_digest, manifest.digest)

    def test_exclude_always_wins_for_product_authority_surface(self) -> None:
        commit = self._commit_files(
            {"src/app.yml": "app\n", "src/generated/build.yml": "generated\n"},
            "authority files",
        )

        snapshot = ProductCorpusResolver().resolve(
            self._manifest(commit, ["src/**"], ["src/generated/**"]), self.repo_dir
        )

        self.assertEqual(snapshot.paths(), ("src/app.yml",))

    def test_replace_refs_cannot_substitute_pinned_commit_or_blob(self) -> None:
        old_commit = self._commit_files({"src/app.yml": b"value: old\n"}, "original")
        old_blob = run_git(["rev-parse", f"{old_commit}:src/app.yml"], self.repo_dir).stdout.strip()
        new_commit = self._commit_files({"src/app.yml": b"value: new\n"}, "replacement")
        new_blob = run_git(["rev-parse", f"{new_commit}:src/app.yml"], self.repo_dir).stdout.strip()
        for old, new in ((old_commit, new_commit), (old_blob, new_blob)):
            with self.subTest(object=old):
                run_git(["replace", old, new], self.repo_dir)
                try:
                    oracle = subprocess.run(
                        ["git", "--no-replace-objects", "cat-file", "-p", f"{old_commit}:src/app.yml"],
                        cwd=self.repo_dir, capture_output=True, check=True,
                    ).stdout
                    snapshot = ProductCorpusResolver().resolve(self._manifest(old_commit, ["src/**"]), self.repo_dir)
                    self.assertEqual(oracle, b"value: old\n")
                    self.assertEqual(snapshot.get_file("src/app.yml").content.encode("utf-8"), oracle)
                    self.assertEqual(snapshot.get_file("src/app.yml").content_hash, hashlib.sha256(oracle).hexdigest())
                finally:
                    run_git(["replace", "-d", old], self.repo_dir)

    def test_commit_field_rejects_annotated_tag_tree_and_blob_object_ids(self) -> None:
        commit = self._commit_files({"src/app.yml": b"fixture\n"}, "commit object")
        run_git(["-c", "tag.gpgsign=false", "tag", "-a", "fixture-tag", "-m", "synthetic tag", commit], self.repo_dir)
        objects = [run_git(["rev-parse", selector], self.repo_dir).stdout.strip()
                   for selector in ("fixture-tag", f"{commit}^{{tree}}", f"{commit}:src/app.yml")]
        for object_id in objects:
            with self.subTest(object_id=object_id), self.assertRaises(CorpusResolverError):
                ProductCorpusResolver().resolve(self._manifest(object_id, ["src/**"]), self.repo_dir)

    def test_terminal_newline_path_is_not_silently_excluded(self) -> None:
        # Build actual Git objects: Windows cannot create this filename, but
        # such a pinned tree must still materialize precisely on all hosts.
        def write_object(kind, content):
            return subprocess.run(
                ["git", "hash-object", "-t", kind, "-w", "--stdin"],
                input=content, cwd=self.repo_dir, capture_output=True, check=True,
            ).stdout.decode("ascii").strip()

        blob = bytes.fromhex(write_object("blob", b"fixture\n"))
        subtree = write_object("tree", b"".join(
            b"100644 " + path + b"\0" + blob
            for path in (b"keep.yml", b"secret.yml", b"secret.yml\n")
        ))
        tree = write_object("tree", b"40000 src\0" + bytes.fromhex(subtree))
        commit = run_git(["commit-tree", tree, "-m", "raw path fixture"], self.repo_dir).stdout.strip()
        resolver = ProductCorpusResolver()
        snapshot = resolver.resolve(self._manifest(commit, ["src/*"], ["src/secret.yml"]), self.repo_dir)
        self.assertEqual(snapshot.paths(), ("src/keep.yml", "src/secret.yml\n"))
        exact = resolver.resolve(self._manifest(commit, ["src/secret.yml"]), self.repo_dir)
        self.assertEqual(exact.paths(), ("src/secret.yml",))

    def test_symlink_is_skipped_from_product_evidence_snapshot(self) -> None:
        self._commit_files({"src/real.yml": "value: real\n"}, "regular file")
        link = self.repo_dir / "src" / "linked.yml"
        try:
            os.symlink("real.yml", link)
        except (OSError, NotImplementedError):
            self.skipTest("The current Windows account cannot create Git symlinks")
        run_git(["add", "src/linked.yml"], cwd=self.repo_dir)
        run_git(["commit", "-m", "symlink"], cwd=self.repo_dir)
        commit = run_git(["rev-parse", "HEAD"], cwd=self.repo_dir).stdout.strip()

        snapshot = ProductCorpusResolver().resolve(
            self._manifest(commit, ["src/**"]), self.repo_dir
        )

        self.assertEqual(snapshot.paths(), ("src/real.yml",))

    def test_git_symlink_mode_is_skipped_without_os_symlink_support(self) -> None:
        manifest = self._manifest("a" * 40, ["src/**"])
        resolver = ProductCorpusResolver(RepoCorpusResolver(git_client=StaticGitClient()))

        snapshot = resolver.resolve(manifest, self.repo_dir)

        self.assertEqual(snapshot.paths(), ("src/real.yml",))

    def test_empty_product_corpus_fails_closed(self) -> None:
        commit = self._commit_files({"docs/readme.md": "not in scope\n"}, "out of scope")

        with self.assertRaises(CorpusResolverError):
            ProductCorpusResolver().resolve(
                self._manifest(commit, ["src/**"]), self.repo_dir
            )

    def test_github_source_requires_matching_local_origin(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        manifest = parse_product_target_manifest(
            {
                "manifest_version": "1.0",
                "target": {
                    "source_type": "github",
                    "repo": "example/product",
                    "commit": commit,
                },
                "authority_surface": {"include": ["src/**"]},
                "mode": {"read_only": True},
            }
        )

        with self.assertRaises(CorpusResolverError):
            ProductCorpusResolver().resolve(manifest, self.repo_dir)

    def test_local_repo_path_override_cannot_change_declared_target(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        manifest = self._manifest(commit, ["src/**"])
        different_repo = self.repo_dir.parent / f"{self.repo_dir.name}-different"
        different_repo.mkdir()
        try:
            with self.assertRaises(CorpusResolverError):
                ProductCorpusResolver().resolve(manifest, different_repo)
        finally:
            different_repo.rmdir()

    def test_file_entrypoint_admits_manifest_before_resolving(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        manifest_path = self.repo_dir.parent / f"{self.repo_dir.name}-manifest.yaml"
        manifest_path.write_text(
            "\n".join(
                (
                    'manifest_version: "1.0"',
                    "target:",
                    "  source_type: local_git",
                    f"  repo: {self.repo_dir.as_posix()}",
                    f"  commit: {commit}",
                    "authority_surface:",
                    "  include:",
                    "    - src/**",
                    "mode:",
                    "  read_only: true",
                    "",
                )
            ),
            encoding="utf-8",
        )
        try:
            snapshot = resolve_product_corpus_from_manifest(manifest_path, self.repo_dir)
        finally:
            manifest_path.unlink(missing_ok=True)

        self.assertEqual(snapshot.paths(), ("src/app.yml",))

    def test_unvalidated_direct_manifest_cannot_cross_materialization_boundary(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        manifest = self._manifest(commit, ["src/**"])
        with self.assertRaises((CorpusResolverError, ValueError)):
            invalid = replace(manifest, mode=replace(manifest.mode, read_only=False))
            ProductCorpusResolver().resolve(invalid, self.repo_dir)

    def test_snapshot_replace_does_not_copy_admission(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        snapshot = ProductCorpusResolver().resolve(self._manifest(commit, ["src/**"]), self.repo_dir)
        with self.assertRaises(CorpusResolverError):
            verify_admitted_product_snapshot(replace(snapshot))

    def test_recomputed_content_cannot_inherit_snapshot_admission(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        snapshot = ProductCorpusResolver().resolve(self._manifest(commit, ["src/**"]), self.repo_dir)
        content = "value: injected\n"
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        entry = replace(snapshot.files[0], content=content, content_hash=file_hash, byte_size=len(content))
        corpus_hash = hashlib.sha256(f"src/app.yml\t{file_hash}\n".encode()).hexdigest()
        seal = hashlib.sha256((f"manifest\t{snapshot.manifest_digest}\ncommit\t{commit}\n"
                               f"corpus\t{corpus_hash}\nsrc/app.yml\t{file_hash}\t{len(content)}\n").encode()).hexdigest()
        with self.assertRaises((TypeError, ValueError)):
            replace(snapshot, files=(entry,), corpus_digest=corpus_hash,
                    total_bytes=len(content), _admission_digest=seal)
        # The protected constructor argument must not hide the independent
        # downstream test: valid recomputed content still lacks admission.
        changed = replace(snapshot, files=(entry,), corpus_digest=corpus_hash,
                          total_bytes=len(content))
        with self.assertRaises(CorpusResolverError):
            verify_admitted_product_snapshot(changed)

    def test_github_matching_repo_on_wrong_host_is_rejected(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        run_git(["remote", "add", "origin", "https://elsewhere.example/example/product.git"], cwd=self.repo_dir)
        manifest = parse_product_target_manifest({
            "manifest_version": "1.0", "target": {"source_type": "github", "repo": "example/product", "commit": commit},
            "authority_surface": {"include": ["src/**"]}, "mode": {"read_only": True}})
        with self.assertRaises(CorpusResolverError):
            ProductCorpusResolver().resolve(manifest, self.repo_dir)

    def test_snapshot_retains_separate_identity_and_integrity(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        snapshot = ProductCorpusResolver().resolve(self._manifest(commit, ["src/**"]), self.repo_dir)
        self.assertTrue(snapshot.product_snapshot_integrity_verified)
        self.assertEqual(snapshot.product_repository_identity_status.value, "VERIFIED")
        self.assertEqual(snapshot.product_unverified_reason_codes, ())
        self.assertIs(verify_admitted_product_snapshot(snapshot), snapshot)

    def test_selected_non_regular_or_unsafe_tree_entry_is_rejected_before_blob_read(self) -> None:
        class DangerousClient(StaticGitClient):
            reads = 0
            def list_tree_entries(self, repo_path: Path, commit: str) -> list:
                return [self.entry]
            def read_blob_bytes(self, repo_path: Path, commit: str, rel_path: str) -> bytes:
                self.reads += 1
                return b"value: fake\n"
        manifest = self._manifest("a" * 40, ["**"])
        for mode, path in (("040000", "src/invalid.yml"), ("100644", "../secret.yml"),
                           ("100644", "/outside.yml"), ("100644", "C:/outside.yml")):
            with self.subTest(mode=mode, path=path):
                client = DangerousClient()
                client.entry = (mode, "blob", "a" * 40, path)
                with self.assertRaises(CorpusResolverError):
                    ProductCorpusResolver(RepoCorpusResolver(git_client=client)).resolve(manifest, self.repo_dir)
                self.assertEqual(client.reads, 0)

    def test_raw_crlf_and_unicode_paths_have_independent_corpus_byte_oracle(self) -> None:
        raw = b"value: one\r\n"
        path = "src/\u8a2d\u5b9a file.yml"
        commit = self._commit_files({path: raw}, "raw bytes")
        (self.repo_dir / path).write_bytes(b"dirty working file\n")
        before = run_git(["status", "--porcelain"], cwd=self.repo_dir).stdout
        snapshot = ProductCorpusResolver().resolve(self._manifest(commit, ["src/**"]), self.repo_dir)
        expected_file_hash = hashlib.sha256(raw).hexdigest()
        expected_corpus_hash = hashlib.sha256((path + "\t" + expected_file_hash + "\n").encode()).hexdigest()
        self.assertEqual(snapshot.files[0].content.encode(), raw)
        self.assertEqual(snapshot.corpus_digest, expected_corpus_hash)
        self.assertEqual(run_git(["status", "--porcelain"], cwd=self.repo_dir).stdout, before)

    def test_bad_blob_and_missing_commit_fail_closed(self) -> None:
        for raw in (b"value:\x00x", b"value:\x01x", b"value:\xffx"):
            with self.subTest(raw=raw):
                commit = self._commit_files({"src/bad.yml": raw}, "bad input")
                with self.assertRaises(CorpusResolverError):
                    ProductCorpusResolver().resolve(self._manifest(commit, ["src/**"]), self.repo_dir)
        with self.assertRaises(CorpusResolverError):
            ProductCorpusResolver().resolve(self._manifest("f" * 40, ["src/**"]), self.repo_dir)

    def test_resolver_exception_traceback_does_not_copy_raw_source(self) -> None:
        import traceback
        class BrokenClient(StaticGitClient):
            def read_blob_bytes(self, repo_path: Path, commit: str, rel_path: str) -> bytes:
                raise RuntimeError("SYNTHETIC_PRIVATE_SOURCE_MUST_NOT_ESCAPE")
        try:
            ProductCorpusResolver(RepoCorpusResolver(git_client=BrokenClient())).resolve(
                self._manifest("a" * 40, ["src/**"]), self.repo_dir)
        except CorpusResolverError as error:
            self.assertNotIn("SYNTHETIC_PRIVATE_SOURCE_MUST_NOT_ESCAPE", "".join(traceback.format_exception(error)))
        else:
            self.fail("Broken materialization was admitted")

    def test_real_git_symlink_mode_is_never_read_without_os_symlink_privileges(self) -> None:
        self._commit_files({"src/real.yml": "value: real\n"}, "regular")
        result = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=self.repo_dir,
                                input=b"real.yml", capture_output=True, check=True)
        link_oid = result.stdout.decode().strip()
        run_git(["update-index", "--add", "--cacheinfo", "120000", link_oid, "src/linked.yml"], cwd=self.repo_dir)
        run_git(["commit", "-m", "Git-object symlink"], cwd=self.repo_dir)
        commit = run_git(["rev-parse", "HEAD"], cwd=self.repo_dir).stdout.strip()
        class RecordingClient(GitCliClient):
            reads: list[str]
            def __init__(self) -> None:
                super().__init__()
                self.reads = []
            def read_blob_bytes(self, repo_path: Path, commit: str, rel_path: str) -> bytes:
                self.reads.append(rel_path)
                return super().read_blob_bytes(repo_path, commit, rel_path)
        client = RecordingClient()
        before = run_git(["status", "--porcelain"], cwd=self.repo_dir).stdout
        snapshot = ProductCorpusResolver(RepoCorpusResolver(git_client=client)).resolve(
            self._manifest(commit, ["src/**"]), self.repo_dir)
        self.assertEqual(client.reads, ["src/real.yml"])
        self.assertEqual(snapshot.paths(), ("src/real.yml",))
        self.assertEqual(run_git(["status", "--porcelain"], cwd=self.repo_dir).stdout, before)

    def test_snapshot_strict_totals_authority_and_file_invariants(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        snapshot = ProductCorpusResolver().resolve(self._manifest(commit, ["src/**"]), self.repo_dir)
        for changes in ({"total_files": True}, {"total_bytes": float(snapshot.total_bytes)},
                        {"files": list(snapshot.files)}, {"files": ()}, {"corpus_digest": "A" * 64},
                        {"files": (snapshot.files[0], snapshot.files[0])}):
            with self.subTest(changes=changes):
                with self.assertRaises(CorpusResolverError):
                    replace(snapshot, **changes)
        outside_file = replace(snapshot.files[0], relative_path="outside/app.yml")
        outside_digest = hashlib.sha256(f"outside/app.yml\t{outside_file.content_hash}\n".encode()).hexdigest()
        with self.assertRaises(CorpusResolverError):
            replace(snapshot, files=(outside_file,), corpus_digest=outside_digest)
        prototype = replace(snapshot)
        self.assertFalse(prototype.product_snapshot_integrity_verified)
        with self.assertRaises(CorpusResolverError):
            _ = prototype.product_repository_identity_status

    def test_git_parent_discovery_cannot_replace_the_declared_source_root(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        nested = self.repo_dir / "nested"
        nested.mkdir()
        manifest = parse_product_target_manifest({
            "manifest_version": "1.0", "target": {"source_type": "local_git", "repo": str(nested), "commit": commit},
            "authority_surface": {"include": ["src/**"]}, "mode": {"read_only": True}})
        with self.assertRaises(CorpusResolverError):
            ProductCorpusResolver().resolve(manifest, nested)

    def test_bare_repository_fixed_objects_remain_supported(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        bare_root = self.repo_dir / "bare.git"
        run_git(["clone", "--bare", str(self.repo_dir), str(bare_root)], cwd=self.repo_dir)
        manifest = parse_product_target_manifest({
            "manifest_version": "1.0", "target": {"source_type": "local_git", "repo": str(bare_root), "commit": commit},
            "authority_surface": {"include": ["src/**"]}, "mode": {"read_only": True}})
        snapshot = ProductCorpusResolver().resolve(manifest, bare_root)
        self.assertEqual(snapshot.files[0].content, "value: one\n")

    def test_partial_clone_missing_blob_never_fetches_or_changes_object_store(self) -> None:
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "partial source")
        blob = run_git(["rev-parse", f"{commit}:src/app.yml"], self.repo_dir).stdout.strip()
        run_git(["config", "uploadpack.allowFilter", "true"], self.repo_dir)
        environment_before = dict(os.environ)
        for reader in ("direct", "product"):
            with self.subTest(reader=reader):
                clone = self.repo_dir / f"partial-{reader}"
                run_git(["-c", "protocol.file.allow=always", "clone", "--filter=blob:none",
                         "--no-checkout", self.repo_dir.as_uri(), str(clone)], self.repo_dir)
                def missing() -> bool:
                    return subprocess.run(
                        ["git", "--no-lazy-fetch", "cat-file", "-e", blob], cwd=clone,
                        capture_output=True, check=False,
                    ).returncode != 0
                def object_store() -> dict[str, str]:
                    root = clone / ".git/objects"
                    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in root.rglob("*") if p.is_file()}
                self.assertTrue(missing(), "Fixture must start without the selected blob")
                before = object_store()
                with self.assertRaises(CorpusResolverError):
                    if reader == "direct":
                        GitCliClient().read_blob_bytes(clone, commit, "src/app.yml")
                    else:
                        manifest = parse_product_target_manifest({
                            "manifest_version": "1.0",
                            "target": {"source_type": "local_git", "repo": str(clone), "commit": commit},
                            "authority_surface": {"include": ["src/**"]}, "mode": {"read_only": True}})
                        ProductCorpusResolver().resolve(manifest, clone)
                self.assertTrue(missing())
                self.assertEqual(object_store(), before)
                self.assertEqual(dict(os.environ), environment_before)

    def test_custom_client_preserves_fixed_git_prerequisite_error(self) -> None:
        from unittest.mock import patch
        commit = self._commit_files({"src/app.yml": "value: one\n"}, "source")
        resolver = ProductCorpusResolver(RepoCorpusResolver(git_client=StaticGitClient()))
        manifest = self._manifest(commit, ["src/**"])
        unsupported = subprocess.CompletedProcess(["git"], 129, "", "SYNTHETIC_PRIVATE_STDERR")
        with patch("tools.repo_corpus_resolver.subprocess.run", return_value=unsupported):
            with self.assertRaisesRegex(CorpusResolverError, "Git.*--no-lazy-fetch.*required") as caught:
                resolver.resolve(manifest, self.repo_dir)
        import traceback
        self.assertNotIn("SYNTHETIC_PRIVATE_STDERR", "".join(traceback.format_exception(caught.exception)))


if __name__ == "__main__":
    unittest.main()
