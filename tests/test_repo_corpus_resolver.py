from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from tools.repo_corpus_resolver import (
    CorpusFile,
    CorpusResolverError,
    CorpusSnapshot,
    GitCliClient,
    RepoCorpusResolver,
    resolve_corpus_from_manifest,
)
from tools.validate_target_manifest import (
    AuthoritySurfaceSpec,
    BaselineSpec,
    ModeSpec,
    TargetManifest,
    TargetSpec,
)


def run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    )


class RepoCorpusResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.repo_dir = Path(self.temp_dir.name)
        # Initialize a real git repository
        run_git(["init", "-b", "main"], cwd=self.repo_dir)
        run_git(["config", "user.name", "Test Assessor"], cwd=self.repo_dir)
        run_git(["config", "user.email", "assessor@test.local"], cwd=self.repo_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _commit_files(self, files: dict[str, str | bytes], commit_msg: str = "commit files") -> str:
        for rel_path, content in files.items():
            p = self.repo_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                p.write_text(content, encoding="utf-8")
            else:
                p.write_bytes(content)
        run_git(["add", "."], cwd=self.repo_dir)
        run_git(["commit", "-m", commit_msg], cwd=self.repo_dir)
        res = run_git(["rev-parse", "HEAD"], cwd=self.repo_dir)
        return res.stdout.strip()

    def test_resolve_basic_corpus_success(self) -> None:
        files = {
            "policy/access-control.md": "# Access Control Policy\nStrict access enforced.\n",
            "process/code-review.md": "# Code Review Process\nTwo reviewers required.\n",
            "ignored/temp.txt": "Should be ignored by include surface.\n",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**", "process/**"),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        snapshot = resolver.resolve(manifest, repo_path=self.repo_dir)

        self.assertIsInstance(snapshot, CorpusSnapshot)
        self.assertEqual(snapshot.target_commit, commit_sha)
        self.assertEqual(snapshot.total_files, 2)
        self.assertEqual(snapshot.paths(), ("policy/access-control.md", "process/code-review.md"))

        f1 = snapshot.get_file("policy/access-control.md")
        self.assertIsNotNone(f1)
        self.assertEqual(f1.relative_path, "policy/access-control.md")
        self.assertEqual(f1.content, "# Access Control Policy\nStrict access enforced.\n")
        self.assertEqual(len(f1.content_hash), 64)

        self.assertIsNone(snapshot.get_file("ignored/temp.txt"))
        self.assertEqual(len(snapshot.corpus_digest), 64)

    def test_exclude_always_wins(self) -> None:
        files = {
            "docs/policy.md": "Main policy document.\n",
            "docs/drafts/wip.md": "Work in progress draft.\n",
            "docs/archived/old.md": "Archived old policy.\n",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("docs/**",),
                exclude=("docs/drafts/**", "docs/archived/**"),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        snapshot = resolver.resolve(manifest, repo_path=self.repo_dir)

        self.assertEqual(snapshot.total_files, 1)
        self.assertEqual(snapshot.paths(), ("docs/policy.md",))

    def test_symlinks_are_skipped(self) -> None:
        files = {
            "policy/real-policy.md": "Real policy content.\n",
        }
        commit_sha = self._commit_files(files)

        # Create symlink inside repo
        symlink_path = self.repo_dir / "policy" / "symlink-policy.md"
        try:
            os.symlink("real-policy.md", symlink_path)
            run_git(["add", "policy/symlink-policy.md"], cwd=self.repo_dir)
            run_git(["commit", "-m", "add symlink"], cwd=self.repo_dir)
            new_commit = run_git(["rev-parse", "HEAD"], cwd=self.repo_dir).stdout.strip()
        except (OSError, NotImplementedError):
            # If OS privileges disallow symlinks without admin on Windows, test passes gracefully
            return

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=new_commit),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        snapshot = resolver.resolve(manifest, repo_path=self.repo_dir)

        # Only real-policy.md is materialized, symlink is skipped
        self.assertEqual(snapshot.paths(), ("policy/real-policy.md",))

    def test_commit_not_found_fails_closed(self) -> None:
        self._commit_files({"test.md": "hello\n"})
        fake_commit = "a" * 40

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=fake_commit),
            authority_surface=AuthoritySurfaceSpec(
                include=("**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("commit not found", str(ctx.exception).lower())

    def test_non_utf8_binary_fails_closed(self) -> None:
        files = {
            "policy/valid.md": "Valid policy text.\n",
            "policy/bad_binary.bin": b"\x80\x81\x82\xff\xfe",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("utf-8", str(ctx.exception).lower())

    def test_deterministic_corpus_digest(self) -> None:
        # Create repo with multiple files
        files = {
            "c_policy.md": "Policy C content.\n",
            "a_policy.md": "Policy A content.\n",
            "b_policy.md": "Policy B content.\n",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("*.md",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        s1 = resolver.resolve(manifest, repo_path=self.repo_dir)
        s2 = resolver.resolve(manifest, repo_path=self.repo_dir)

        # Ordering must be deterministic
        self.assertEqual(s1.paths(), ("a_policy.md", "b_policy.md", "c_policy.md"))
        self.assertEqual(s1.corpus_digest, s2.corpus_digest)

    def test_resolve_from_manifest_file_with_yaml(self) -> None:
        files = {
            "policy/crypto.md": "# Cryptography Policy\nUse modern ciphers.\n",
        }
        commit_sha = self._commit_files(files)

        manifest_content = f"""
schema_name: target-manifest
schema_version: "1.0.0"
target:
  source_type: local_git
  repo: "{self.repo_dir.as_posix()}"
  commit: "{commit_sha}"
authority_surface:
  include:
    - "policy/**"
baseline:
  framework: NIST_SP_800_218
  version: "1.1"
mode:
  read_only: true
"""
        manifest_path = self.repo_dir / "target-manifest.yaml"
        manifest_path.write_text(manifest_content, encoding="utf-8")

        snapshot = resolve_corpus_from_manifest(manifest_path)
        self.assertEqual(snapshot.total_files, 1)
        self.assertEqual(snapshot.paths(), ("policy/crypto.md",))

    def test_github_source_type_requires_local_repo_path(self) -> None:
        commit_sha = "1" * 40
        manifest = TargetManifest(
            target=TargetSpec(source_type="github", repo="org/repo", commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=None)
        self.assertIn("without explicit local repo_path", str(ctx.exception))

    def test_cli_invocation_success(self) -> None:
        files = {
            "policy/sec.md": "# Security Policy\n",
        }
        commit_sha = self._commit_files(files)
        manifest_content = f"""
target:
  source_type: local_git
  repo: "{self.repo_dir.as_posix()}"
  commit: "{commit_sha}"
authority_surface:
  include:
    - "policy/**"
baseline:
  framework: NIST_SP_800_218
  version: "1.1"
mode:
  read_only: true
"""
        manifest_path = self.repo_dir / "test-manifest.yaml"
        manifest_path.write_text(manifest_content, encoding="utf-8")

        export_json_path = self.repo_dir / "export.json"
        cmd = [
            sys.executable,
            str(Path(__file__).resolve().parent.parent / "tools" / "repo_corpus_resolver.py"),
            str(manifest_path),
            "--export-json",
            str(export_json_path),
            "--summary",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("[PASS] Repository corpus materialized successfully", res.stdout)
        self.assertTrue(export_json_path.is_file())

    def test_chinese_and_spaces_in_filenames_materialize_correctly(self) -> None:
        files = {
            "policy/安全政策.md": "# 安全政策內容\n",
            "policy/code review process.md": "# Code Review With Spaces\n",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        snapshot = resolver.resolve(manifest, repo_path=self.repo_dir)

        self.assertEqual(snapshot.total_files, 2)
        self.assertEqual(
            snapshot.paths(),
            ("policy/code review process.md", "policy/安全政策.md"),
        )
        chinese_file = snapshot.get_file("policy/安全政策.md")
        self.assertIsNotNone(chinese_file)
        self.assertEqual(chinese_file.content, "# 安全政策內容\n")

    def test_empty_corpus_due_to_no_include_match_fails_closed(self) -> None:
        files = {"policy/test.md": "content\n"}
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("nonexistent/**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("0 authoritative files", str(ctx.exception))

    def test_empty_corpus_due_to_all_excluded_fails_closed(self) -> None:
        files = {
            "docs/draft.md": "draft\n",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("docs/**",),
                exclude=("docs/**",),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("0 authoritative files", str(ctx.exception))

    def test_utf8_decodable_binary_with_nul_fails_closed(self) -> None:
        # b"a\x00b" is decodable in UTF-8, but contains NUL byte (binary)
        files = {
            "policy/bad_null.md": b"a\x00b",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("binary files prohibited", str(ctx.exception).lower())

    def test_binary_with_disallowed_c0_control_char_fails_closed(self) -> None:
        # 0x01 (SOH) is a C0 control char not allowed in plain text
        files = {
            "policy/bad_ctrl.md": b"hello\x01world",
        }
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("binary files prohibited", str(ctx.exception).lower())

    def test_github_source_type_unverified_origin_fails_closed(self) -> None:
        files = {"policy/test.md": "policy\n"}
        commit_sha = self._commit_files(files)

        manifest = TargetManifest(
            target=TargetSpec(source_type="github", repo="Company/official-ssdlc", commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/**",),
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        # Case 1: no remote origin configured in local repo
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        err_lower = str(ctx.exception).lower()
        self.assertTrue("remote" in err_lower and "origin" in err_lower)

        # Case 2: wrong remote origin configured
        run_git(["remote", "add", "origin", "https://github.com/OtherOrg/wrong-repo.git"], cwd=self.repo_dir)
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("does not match claimed github repository", str(ctx.exception).lower())

        # Case 3: correct remote origin matches manifest repo
        run_git(["remote", "set-url", "origin", "https://github.com/Company/official-ssdlc.git"], cwd=self.repo_dir)
        snapshot = resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertEqual(snapshot.total_files, 1)

    def test_unsupported_glob_syntax_fails_closed(self) -> None:
        commit_sha = self._commit_files({"policy/a.md": "a\n"})
        manifest = TargetManifest(
            target=TargetSpec(source_type="local_git", repo=str(self.repo_dir), commit=commit_sha),
            authority_surface=AuthoritySurfaceSpec(
                include=("policy/[abc].md",),  # bracket character class not supported
                exclude=(),
            ),
            baseline=BaselineSpec(framework="NIST_SP_800_218", version="1.1"),
            mode=ModeSpec(read_only=True),
        )

        resolver = RepoCorpusResolver()
        with self.assertRaises(CorpusResolverError) as ctx:
            resolver.resolve(manifest, repo_path=self.repo_dir)
        self.assertIn("unsupported glob syntax", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
