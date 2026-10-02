"""Executable frozen S2-A Scenario 1–12; actual synthetic Git repos and CLI I/O."""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from string import Template
import unittest
from unittest.mock import patch

import yaml

from tests.test_implementation_contracts import (
    make_policy_admission, run_git, ruleset_data, expectation_set_data,
    rehash_rules, rehash_expectations,
)
from tools.verify_implementation_evidence import atomic_write, main
from tools.implementation_renderer import DeterministicImplementationRenderer
from tools.implementation_verification import ImplementationVerificationOrchestrator, VerificationInputError

PROJECT = Path(__file__).resolve().parents[1]
PRIVATE_VALUE = "SYNTHETIC_PRIVATE_VALUE_DO_NOT_PROJECT"


class ImplementationCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="s2 e2e ")
        self.root = Path(self.temp.name)
        self.policy, self.assessment = make_policy_admission(self.root)
        self.policy_repo = self.root / "policy-repo"
        self.policy_manifest = self.policy_repo / "target-manifest.yaml"
        # Three synthetic policy findings provide explicit task/source authority.
        data = yaml.safe_load(self.assessment.read_text(encoding="utf-8"))
        for task in ("PO.3.1", "PS.2.1"):
            f = copy.deepcopy(data["results"][0])
            f.update(finding_id="FIND-" + task, task_id=task)
            f["basis"][0]["task_id"] = task
            data["results"].append(f)
            data["assessment"]["scope_tasks"].append(task)
        self.assessment.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        self.product_repo = self.root / "product-repo"
        self.product_repo.mkdir()
        run_git(self.product_repo, "init", "-b", "main")
        run_git(self.product_repo, "config", "user.name", "Synthetic S2")
        run_git(self.product_repo, "config", "user.email", "synthetic@example.invalid")
        run_git(self.product_repo, "remote", "add", "origin", "https://github.com/example/product.git")
        self.files = {
            ".github/workflows/security.yml": b"on: push\njobs:\n  security:\n    steps:\n      - uses: actions/checkout@v4\n      - uses: github/codeql-action/analyze@v2\n",
            ".github/workflows/release.yml": b"jobs:\n  release:\n    steps:\n      - uses: actions/checkout@v4\n",
            "src/file.lock": b"locked\n", "src/value.json": b'{"flag":1}\n',
        }
        self.product_manifest = self.root / "product.json"
        self.commit_product()
        self.rules = ruleset_data()
        self.exps = expectation_set_data()
        self.rules_file = self.root / "rules.json"
        self.exps_file = self.root / "expectations.json"
        self.save_acl()

    def tearDown(self):
        self.temp.cleanup()

    def commit_product(self):
        for path in tuple(self.product_repo.rglob("*")):
            if path.is_file() and ".git" not in path.relative_to(self.product_repo).parts:
                path.unlink()
        for name, raw in self.files.items():
            p = self.product_repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        run_git(self.product_repo, "add", "-A")
        run_git(self.product_repo, "commit", "--allow-empty", "-m", "synthetic evidence")
        self.product_commit = run_git(self.product_repo, "rev-parse", "HEAD")
        self.product_payload = {"manifest_version": "1.0", "target": {
            "source_type": "github", "repo": "example/product", "commit": self.product_commit},
            "authority_surface": {"include": [".github/**", "src/**"]}, "mode": {"read_only": True}}
        self.product_manifest.write_text(json.dumps(self.product_payload), encoding="utf-8")

    def save_acl(self):
        rehash_rules(self.rules)
        rehash_expectations(self.exps)
        self.rules_file.write_text(json.dumps(self.rules), encoding="utf-8")
        self.exps_file.write_text(json.dumps(self.exps), encoding="utf-8")

    def set_rule(self, *, task="PW.4.4", selector="src/file.lock", matcher="FILE_EXISTS", path=None,
                 expected=None, quantifier="ANY", na=None):
        rule = self.rules["rules"][0]
        rule.update(task_id=task, candidate_selectors=[selector], candidate_quantifier=quantifier,
                    assertion={"matcher": matcher, "target_path_expression": path, "expected_value": expected},
                    applicability={"status": "NOT_APPLICABLE" if na is not None else "APPLICABLE", "reason": na})
        self.exps["expectations"][0].update(task_id=task,
            policy_finding_id="FIND-1" if task == "PW.4.4" else "FIND-" + task)
        self.save_acl()

    def args(self, *extra):
        return ["--verification-id", "SYNTHETIC-E2E", "--assessment", str(self.assessment),
                "--policy-manifest", str(self.policy_manifest), "--policy-repo", str(self.policy_repo),
                "--product-manifest", str(self.product_manifest), "--product-repo", str(self.product_repo),
                "--ruleset", str(self.rules_file), "--expectations", str(self.exps_file), *map(str, extra)]

    def cli(self, *extra):
        return subprocess.run([sys.executable, "-X", "utf8", "-m", "tools.verify_implementation_evidence",
                               *self.args(*extra)], cwd=PROJECT, capture_output=True)

    def success(self, *extra):
        p = self.cli(*extra)
        self.assertEqual(p.returncode, 0, p.stderr.decode("utf-8"))
        self.assertEqual(p.stderr, b"")
        return json.loads(p.stdout)

    def fatal_outputs_preserved(self, *extra):
        for existing in (False, True):
            out = self.root / ("old-report" if existing else "new-report")
            old = b"\xffOLD\x00report\r\n"
            if existing:
                out.write_bytes(old)
            before = {p.name for p in self.root.iterdir()}
            p = self.cli("--output", out, *extra)
            self.assertEqual(p.returncode, 1)
            self.assertEqual(p.stdout, b"")
            self.assertNotIn(PRIVATE_VALUE.encode(), p.stderr)
            self.assertNotIn(b"Traceback", p.stderr)
            self.assertEqual({p.name for p in self.root.iterdir()}, before)
            self.assertEqual(out.read_bytes(), old) if existing else self.assertFalse(out.exists())
            self.assertFalse(tuple(self.root.glob(".s2-report-*")))

    def test_scenario_1_yaml_match_and_exact_locator_digest(self):
        self.set_rule(task="PO.3.1", selector=".github/workflows/security.yml", matcher="YAML_PATH_EQUALS",
                      path="jobs.security.steps[1].uses",
                      expected={"kind": "STRING", "value": "github/codeql-action/analyze@v2"})
        data = self.success()
        item = data["verified_items"][0]
        self.assertEqual(item["verdict"], "EVIDENCE_FOUND")
        ref = item["evidence_refs"][0]
        self.assertEqual(ref["content_digest"], hashlib.sha256(self.files[ref["repo_path"]]).hexdigest())
        self.assertEqual(ref["locator"], {"kind": "yaml_path", "value": "jobs.security.steps[1].uses"})
        self.assertEqual(ref["resolved_node_paths"], ["/jobs/security/steps/1/uses"])
        self.assertIsNone(ref["matched_snippet"])
        self.assertEqual(len(data["claim_boundary"]), 5)
        self.assertIn("No Tool Effectiveness Claim", data["claim_boundary"][0])

    def test_scenario_2_missing_is_success_without_priority(self):
        self.set_rule(selector="src/missing.lock")
        data = self.success()
        item = data["verified_items"][0]
        self.assertEqual(item["verdict"], "EVIDENCE_MISSING")
        self.assertEqual(item["evidence_refs"], [])
        self.assertIsNone(item["discrepancy_details"])
        self.assertNotIn("priority", json.dumps(data))

    def test_scenario_3_discrepancy_omits_raw_values(self):
        self.set_rule(task="PS.2.1", selector=".github/workflows/release.yml", matcher="YAML_PATH_EQUALS",
                      path="jobs.release.steps[0].uses", expected={"kind": "STRING", "value": PRIVATE_VALUE})
        p = self.cli()
        self.assertEqual(p.returncode, 0)
        self.assertNotIn(PRIVATE_VALUE.encode(), p.stdout)
        self.assertNotIn(b"actions/checkout@v4", p.stdout)
        item = json.loads(p.stdout)["verified_items"][0]
        self.assertEqual(item["verdict"], "EVIDENCE_DISCREPANCY")
        self.assertEqual(json.loads(item["discrepancy_details"]),
                         [{"code": "VALUE_MISMATCH", "repo_path": ".github/workflows/release.yml"}])

    def test_scenario_4_explicit_na_never_parses_candidate(self):
        self.files["src/value.json"] = b"not JSON\n"
        self.commit_product()
        self.set_rule(selector="src/value.json", matcher="JSON_POINTER_EXISTS", path="/flag", na="No Python component")
        item = self.success()["verified_items"][0]
        self.assertEqual(item["verdict"], "RULE_NOT_APPLICABLE")
        self.assertEqual(item["evidence_refs"], [])
        self.assertEqual(item["applicability_reason"], "No Python component")

    def test_scenario_5_missing_origin_default_fails_before_output(self):
        for repo in (self.policy_repo, self.product_repo):
            with self.subTest(repo=repo.name):
                origin = run_git(repo, "remote", "get-url", "origin")
                run_git(repo, "remote", "remove", "origin")
                self.fatal_outputs_preserved()
                run_git(repo, "remote", "add", "origin", origin)

    def test_scenario_6_multi_rules_remain_independent(self):
        second = copy.deepcopy(self.rules["rules"][0])
        second.update(rule_id="RULE-2", candidate_selectors=["src/absent.lock"])
        self.rules["rules"].append(second)
        self.exps["expectations"][0]["verification_rule_ids"].append("RULE-2")
        self.save_acl()
        data = self.success()
        self.assertEqual([(i["rule_id"], i["verdict"]) for i in data["verified_items"]],
                         [("RULE-1", "EVIDENCE_FOUND"), ("RULE-2", "EVIDENCE_MISSING")])
        for forbidden in ("coverage_verdict", "priority", "review_queue", "PARTIAL", "FAILED"):
            self.assertNotIn(forbidden, json.dumps(data))

    def test_scenario_7_identity_opt_in_warns_both_formats(self):
        run_git(self.product_repo, "remote", "remove", "origin")
        p = self.cli("--allow-unverified-provenance")
        self.assertEqual(p.returncode, 0)
        data = json.loads(p.stdout)
        self.assertTrue(p.stdout.decode().startswith('{\n  "warning": "UNVERIFIED PROVENANCE'))
        self.assertEqual(data["policy_repository_identity_status"], "VERIFIED")
        self.assertEqual(data["product_repository_identity_status"], "UNVERIFIED")
        self.assertEqual(data["product_unverified_reason_codes"], ["REPOSITORY_IDENTITY_UNVERIFIED"])
        self.assertTrue(data["policy_snapshot_integrity_verified"])
        self.assertTrue(data["product_snapshot_integrity_verified"])
        self.assertFalse(data["provenance_verified"])
        self.assertTrue(data["policy_provenance_verified"])
        self.assertFalse(data["product_provenance_verified"])
        md = self.cli("--format", "markdown", "--allow-unverified-provenance")
        self.assertEqual(md.returncode, 0)
        self.assertTrue(md.stdout.startswith(b"> [!WARNING]\n> UNVERIFIED PROVENANCE"))
        self.fatal_outputs_preserved()

    def test_scenario_8_missing_product_manifest_cannot_opt_in(self):
        self.product_manifest.unlink()
        self.fatal_outputs_preserved("--allow-unverified-provenance")

    def test_scenario_9_file_any_all_do_not_quantify_nodes(self):
        self.files["src/a.yml"] = b"steps: [{uses: correct}, {uses: wrong}]\n"
        self.files["src/b.yml"] = b"steps: [{uses: wrong}]\n"
        self.commit_product()
        for quantifier, verdict, file, nodes in (
            ("ANY", "EVIDENCE_FOUND", "src/a.yml", ["/steps/0/uses"]),
            ("ALL", "EVIDENCE_DISCREPANCY", "src/b.yml", ["/steps/0/uses"])):
            with self.subTest(quantifier=quantifier):
                self.set_rule(selector="src/*.yml", matcher="YAML_PATH_EQUALS", path="steps[*].uses",
                              expected={"kind": "STRING", "value": "correct"}, quantifier=quantifier)
                item = self.success()["verified_items"][0]
                self.assertEqual(item["verdict"], verdict)
                self.assertEqual([(r["repo_path"], r["resolved_node_paths"]) for r in item["evidence_refs"]], [(file, nodes)])

    def test_scenario_10_typed_scalars_do_not_coerce(self):
        self.files["src/value.yml"] = b"flag: 1\n"
        self.commit_product()
        for matcher, file, path in (("JSON_POINTER_EQUALS", "src/value.json", "/flag"),
                                    ("YAML_PATH_EQUALS", "src/value.yml", "flag")):
            for kind, value, verdict in (("STRING", "1", "EVIDENCE_DISCREPANCY"), ("INTEGER", 1, "EVIDENCE_FOUND")):
                with self.subTest(matcher=matcher, kind=kind):
                    self.set_rule(selector=file, matcher=matcher, path=path, expected={"kind": kind, "value": value})
                    item = self.success()["verified_items"][0]
                    self.assertEqual(item["verdict"], verdict)
                    if kind == "STRING":
                        self.assertEqual(json.loads(item["discrepancy_details"]), [{"code": "VALUE_MISMATCH", "repo_path": file}])

    def test_scenario_11_invalid_acl_and_duplicate_evidence_never_write(self):
        original = self.rules_file.read_bytes()
        for bad in (b'{"rules":[],"rules":[]}', b'{"value":NaN}', b'"\\ud800"',
                    original.replace(self.rules["ruleset_digest"].encode(), b"a" * 64)):
            with self.subTest(bad=bad[:15]):
                self.rules_file.write_bytes(bad)
                self.fatal_outputs_preserved("--allow-unverified-provenance")
        self.rules_file.write_bytes(original)
        self.rules["rules"].append(copy.deepcopy(self.rules["rules"][0]))
        self.save_acl()
        self.fatal_outputs_preserved()
        self.rules["rules"].pop()
        for file, matcher, path, raw in (
            ("src/value.json", "JSON_POINTER_EXISTS", "/flag", b'{"flag":1,"flag":2}'),
            ("src/value.yml", "YAML_PATH_EXISTS", "flag", b"flag: 1\nflag: 2\n")):
            self.files[file] = raw
            self.commit_product()
            self.set_rule(selector=file, matcher=matcher, path=path)
            self.fatal_outputs_preserved("--allow-unverified-provenance")

    def test_scenario_12_known_mismatch_never_opts_in(self):
        run_git(self.product_repo, "remote", "set-url", "origin", "https://github.com/example/other.git")
        self.fatal_outputs_preserved("--allow-unverified-provenance")

    def test_atomic_failures_preserve_old_and_new_destinations(self):
        for operation in ("fsync", "replace"):
            for existing in (False, True):
                with self.subTest(operation=operation, existing=existing):
                    out = self.root / (operation + str(existing))
                    old = b"\x00\xffOLD\r\n"
                    if existing:
                        out.write_bytes(old)
                    before = set(self.root.iterdir())
                    with patch("tools.verify_implementation_evidence.os." + operation, side_effect=OSError(PRIVATE_VALUE)):
                        with self.assertRaises(OSError):
                            atomic_write(out, b"NEW report")
                    self.assertEqual(set(self.root.iterdir()), before)
                    self.assertEqual(out.read_bytes(), old) if existing else self.assertFalse(out.exists())

    def test_partial_write_and_close_failure_cleanup_real_temporary_files(self):
        import tempfile
        original = tempfile.NamedTemporaryFile
        for operation in ("write_error", "short_write", "close_error"):
            for existing in (False, True):
                with self.subTest(operation=operation, existing=existing):
                    out = self.root / (operation + str(existing))
                    old = b"\xffold\x00"
                    if existing:
                        out.write_bytes(old)
                    before = set(self.root.iterdir())
                    class FaultyStream:
                        def __init__(self, stream):
                            self.stream = stream
                        def __getattr__(self, name):
                            return getattr(self.stream, name)
                        def __enter__(self):
                            return self
                        def write(self, content):
                            if operation == "close_error":
                                return self.stream.write(content)
                            size = self.stream.write(content[:3])
                            if operation == "write_error":
                                raise OSError(PRIVATE_VALUE)
                            return size
                        def __exit__(self, *args):
                            self.stream.__exit__(*args)
                            if operation == "close_error":
                                raise OSError(PRIVATE_VALUE)
                    def factory(*args, **kwargs):
                        return FaultyStream(original(*args, **kwargs))
                    with patch("tools.verify_implementation_evidence.tempfile.NamedTemporaryFile", factory):
                        with self.assertRaises(OSError):
                            atomic_write(out, b"complete report bytes")
                    self.assertEqual(set(self.root.iterdir()), before)
                    self.assertEqual(out.read_bytes(), old) if existing else self.assertFalse(out.exists())

    def test_publication_error_is_exit_one_and_sanitized(self):
        out = self.root / "fault-report"
        out.write_bytes(b"\xffOLD")
        error = io.StringIO()
        with patch("tools.verify_implementation_evidence.os.replace", side_effect=OSError(PRIVATE_VALUE)), patch("sys.stderr", error):
            self.assertEqual(main(self.args("--output", out)), 1)
        self.assertNotIn(PRIVATE_VALUE, error.getvalue())
        self.assertEqual(out.read_bytes(), b"\xffOLD")
        self.assertFalse(tuple(self.root.glob(".s2-report-*")))

    def test_full_json_and_markdown_match_independent_golden_templates(self):
        self.set_rule()
        # Independent oracles: raw fixture bytes, native Git identity, B2 reviewed
        # fixture serializer, and frozen §7 prose. No production renderer/digest.
        manifest = copy.deepcopy(self.product_payload)
        manifest["authority_surface"]["exclude"] = []
        hashes = {path: hashlib.sha256(raw).hexdigest() for path, raw in self.files.items()}
        corpus = hashlib.sha256("".join(f"{p}\t{hashes[p]}\n" for p in sorted(hashes)).encode()).hexdigest()
        import re
        section = (PROJECT / "docs/specs/s2-a-implementation-evidence-spec.md").read_text(encoding="utf-8").split("## 7. ", 1)[1].split("## 8. ", 1)[0]
        claims = [re.sub(r"^[1-5]\. ", "", line).replace("**", "")
                  for line in section.splitlines() if re.match(r"^[1-5]\. ", line)]
        variables = {
            "PRODUCT_COMMIT": self.product_commit,
            "PRODUCT_MANIFEST": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            "PRODUCT_CORPUS": corpus, "FILE_SHA": hashes["src/file.lock"],
            "EXP_SET": self.exps["expectation_set_digest"], "RULE_SET": self.rules["ruleset_digest"],
            "EXP": self.exps["expectations"][0]["expectation_digest"], "RULE": self.rules["rules"][0]["rule_digest"],
            "CLAIMS_JSON": json.dumps(claims, ensure_ascii=False, indent=2).replace("\n", "\n  "),
            "CLAIMS_MD": "\n".join("- " + c.replace("`", "\\`").replace("_", "\\_") for c in claims),
        }
        for format in ("json", "markdown"):
            with self.subTest(format=format):
                template = (PROJECT / f"tests/fixtures/s2-c2/expected-{format}.template").read_text(encoding="utf-8")
                expected = Template(template).substitute(variables).encode("utf-8")
                p = self.cli("--format", format)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stdout, expected)

    def test_markdown_root_nodes_are_distinct_from_no_nodes(self):
        self.files["src/root.json"] = b'"root"\n'
        self.files["src/root.yml"] = b'"root"\n'
        self.commit_product()
        for matcher, file in (("JSON_POINTER_EXISTS", "src/root.json"),
                              ("JSON_POINTER_EQUALS", "src/root.json"),
                              ("YAML_PATH_EXISTS", "src/root.yml"),
                              ("YAML_PATH_EQUALS", "src/root.yml")):
            with self.subTest(matcher=matcher):
                expected = {"kind": "STRING", "value": "root"} if matcher.endswith("EQUALS") else None
                self.set_rule(selector=file, matcher=matcher, path="", expected=expected)
                self.assertEqual(self.success()["verified_items"][0]["evidence_refs"][0]["resolved_node_paths"], [""])
                md = self.cli("--format", "markdown")
                self.assertEqual(md.returncode, 0)
                self.assertIn(b'| \\[""\\] |', md.stdout)
        self.set_rule()
        md = self.cli("--format", "markdown")
        self.assertEqual(md.returncode, 0)
        self.assertIn(b"| \\[\\] |", md.stdout)
        self.assertNotIn(b'| \\[""\\] |', md.stdout)

    def test_real_cli_preserves_inputs_and_reproducible_utf8_bytes(self):
        sources = (self.assessment, self.policy_manifest, self.product_manifest, self.rules_file, self.exps_file)
        before = [p.read_bytes() for p in sources]
        for format in ("json", "markdown"):
            a = self.cli("--format", format)
            b = self.cli("--format", format)
            self.assertEqual(a.returncode, 0)
            self.assertEqual(a.stdout, b.stdout)
            a.stdout.decode("utf-8", errors="strict")
            out = self.root / ("report." + format)
            out.write_bytes(b"old")
            p = self.cli("--format", format, "--output", out)
            self.assertEqual(p.returncode, 0)
            self.assertEqual(p.stdout, b"")
            self.assertEqual(out.read_bytes(), a.stdout)
        self.assertEqual([p.read_bytes() for p in sources], before)

    def test_output_cannot_mutate_any_input_or_source_repo(self):
        for out in (self.assessment, self.rules_file, self.product_repo / "src/file.lock", self.policy_repo / "report"):
            before = out.read_bytes() if out.exists() else None
            p = self.cli("--output", out)
            self.assertEqual(p.returncode, 1)
            self.assertEqual(out.read_bytes(), before) if before is not None else self.assertFalse(out.exists())

    def test_cli_bad_arguments_exit_one_without_echoing_input(self):
        p = subprocess.run([sys.executable, "-m", "tools.verify_implementation_evidence", "--unknown", PRIVATE_VALUE],
                           cwd=PROJECT, capture_output=True)
        self.assertEqual(p.returncode, 1)
        self.assertNotIn(PRIVATE_VALUE.encode(), p.stderr)
        self.assertEqual(p.stdout, b"")

    def test_renderer_refuses_mutated_records_and_does_not_repair(self):
        record = ImplementationVerificationOrchestrator().verify(
            verification_id="SYNTHETIC-E2E", assessment_path=self.assessment,
            policy_manifest_path=self.policy_manifest, policy_repo_path=self.policy_repo,
            product_manifest_path=self.product_manifest, product_repo_path=self.product_repo,
            ruleset_data=self.rules, expectation_set_data=self.exps)
        object.__setattr__(record, "claim_boundary", ())
        renderer = DeterministicImplementationRenderer()
        for method in (renderer.render_json, renderer.render_markdown):
            with self.assertRaises(VerificationInputError):
                method(record)
        self.assertEqual(record.claim_boundary, ())

    def test_markdown_hostile_reason_is_text_not_injected_structure(self):
        reason = "<script>bad()</script>\n# injected | [link](https://evil.invalid) `code`"
        self.set_rule(na=reason)
        p = self.cli("--format", "markdown")
        self.assertEqual(p.returncode, 0)
        md = p.stdout.decode()
        self.assertNotIn("<script>", md)
        self.assertNotIn("\n# injected", md)
        self.assertNotIn("[link](", md)
        self.assertIn("&lt;script&gt;", md)


if __name__ == "__main__":
    unittest.main()
