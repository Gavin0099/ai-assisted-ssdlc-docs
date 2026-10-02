from __future__ import annotations

import unittest
import traceback
import sys
from unittest import mock

from tools.implementation_matchers import (
    DiscrepancyCode,
    EvidenceAssertion,
    ExpectedScalar,
    ExpectedScalarKind,
    InvalidEvidenceInputError,
    InvalidRuleError,
    MatcherKind,
    MatcherResult,
    evaluate_assertion,
)
from tools import implementation_matchers as matchers


class ImplementationMatcherTests(unittest.TestCase):
    def _expected(self, kind: ExpectedScalarKind, value: str | bool | int | None):
        return ExpectedScalar(kind=kind, value=value)

    def _equals(self, matcher: MatcherKind, path: str, kind: ExpectedScalarKind, value):
        return EvidenceAssertion(
            matcher=matcher,
            target_path_expression=path,
            expected_value=self._expected(kind, value),
        )

    def test_file_exists_matcher_has_no_structured_locator(self) -> None:
        result = evaluate_assertion(
            EvidenceAssertion(MatcherKind.FILE_EXISTS), "content is not parsed"
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ())
        self.assertIsNone(result.discrepancy_code)

    def test_expected_scalar_rejects_python_bool_as_integer(self) -> None:
        with self.assertRaises(InvalidRuleError):
            ExpectedScalar(ExpectedScalarKind.INTEGER, True)

    def test_matcher_field_combinations_are_fail_closed(self) -> None:
        invalid_assertions = (
            lambda: EvidenceAssertion(
                MatcherKind.FILE_EXISTS, target_path_expression="src/**"
            ),
            lambda: EvidenceAssertion(
                MatcherKind.YAML_PATH_EXISTS,
                target_path_expression="security.enabled",
                expected_value=self._expected(ExpectedScalarKind.BOOLEAN, True),
            ),
            lambda: EvidenceAssertion(
                MatcherKind.JSON_POINTER_EQUALS, target_path_expression="/enabled"
            ),
        )
        for create_assertion in invalid_assertions:
            with self.subTest(create_assertion=create_assertion):
                with self.assertRaises(InvalidRuleError):
                    create_assertion()

    def test_yaml_path_wildcard_returns_only_matching_concrete_nodes(self) -> None:
        assertion = self._equals(
            MatcherKind.YAML_PATH_EQUALS,
            "jobs.security.steps[*].uses",
            ExpectedScalarKind.STRING,
            "sigstore/cosign-installer@v3",
        )

        result = evaluate_assertion(
            assertion,
            "jobs:\n  security:\n    steps:\n"
            "      - uses: actions/checkout@v4\n"
            "      - uses: sigstore/cosign-installer@v3\n",
        )

        self.assertTrue(result.passed)
        self.assertEqual(
            result.resolved_node_paths,
            ("/jobs/security/steps/1/uses",),
        )

    def test_yaml_path_exists_accepts_uncomparable_value_and_equals_does_not(self) -> None:
        content = "release:\n  date: 2026-01-01\n"
        exists = evaluate_assertion(
            EvidenceAssertion(
                MatcherKind.YAML_PATH_EXISTS,
                target_path_expression="release.date",
            ),
            content,
        )
        equals = evaluate_assertion(
            self._equals(
                MatcherKind.YAML_PATH_EQUALS,
                "release.date",
                ExpectedScalarKind.STRING,
                "2026-01-01",
            ),
            content,
        )

        self.assertTrue(exists.passed)
        self.assertEqual(exists.resolved_node_paths, ("/release/date",))
        self.assertFalse(equals.passed)
        self.assertEqual(equals.discrepancy_code, DiscrepancyCode.UNCOMPARABLE_NODE)

    def test_yaml_uses_yaml_12_boolean_resolution(self) -> None:
        assertion = self._equals(
            MatcherKind.YAML_PATH_EQUALS,
            "legacy_flag",
            ExpectedScalarKind.STRING,
            "yes",
        )

        result = evaluate_assertion(assertion, "legacy_flag: yes\n")

        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("/legacy_flag",))

    def test_yaml_integer_core_forms_are_compared_numerically(self) -> None:
        # Independent oracle: YAML 1.2.2 section 10.3.2, not PyYAML 1.1.
        for source, expected in (
            ("012", 12),
            ("+012", 12),
            ("-012", -12),
            ("0o10", 8),
            ("0x10", 16),
        ):
            with self.subTest(source=source):
                assertion = self._equals(
                    MatcherKind.YAML_PATH_EQUALS,
                    "value",
                    ExpectedScalarKind.INTEGER,
                    expected,
                )
                self.assertTrue(evaluate_assertion(assertion, f"value: {source}\n").passed)

    def test_yaml_non_core_numeric_spellings_are_literal_strings(self) -> None:
        # Forms absent from the Core resolution table fall back to strings.
        for source in ("0b10", "1_000", "0O10", "0X10", "-0x10", "1_0.5", "+.nan"):
            with self.subTest(source=source):
                result = evaluate_assertion(self._equals(
                    MatcherKind.YAML_PATH_EQUALS, "value", ExpectedScalarKind.STRING, source
                ), f"value: {source}\n")
                self.assertTrue(result.passed)
                self.assertEqual(result.resolved_node_paths, ("/value",))

    def test_yaml_mapping_key_equality_preserves_core_tags(self) -> None:
        # YAML 1.2.2 section 3.2.1.3: bool true and integer 1 differ by tag.
        result = evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, ""),
                                    'true: flag\n1: count\n"1": text\n')
        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("",))
        literal = evaluate_assertion(self._equals(
            MatcherKind.YAML_PATH_EQUALS, "1", ExpectedScalarKind.STRING, "text"
        ), 'true: flag\n1: count\n"1": text\n')
        self.assertTrue(literal.passed)

    def test_yaml_same_tag_equivalent_numeric_keys_are_duplicates(self) -> None:
        for content in ("0o13: first\n0xB: second\n", "012: first\n12: second\n"):
            with self.subTest(content=content):
                with self.assertRaises(InvalidEvidenceInputError):
                    evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, ""), content)

    def test_equivalent_timestamp_keys_are_duplicates_at_full_precision(self) -> None:
        for keys in (
            ("2001-12-15T02:59:43.1Z", "2001-12-14t21:59:43.10-05:00"),
            ("2001-12-15", "2001-12-15T00:00:00Z"),
            ("2001-12-15T02:59:43", "2001-12-15T02:59:43Z"),
        ):
            with self.subTest(keys=keys):
                content = f"ok: true\n{keys[0]}: first\n{keys[1]}: second\n"
                with self.assertRaises(InvalidEvidenceInputError):
                    evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, "ok"), content)
        content = ("ok: true\n2001-12-15T00:00:00.0000001Z: first\n"
                   "2001-12-15T00:00:00.0000002Z: second\n")
        self.assertTrue(evaluate_assertion(
            EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, "ok"), content).passed)

    def test_shared_alias_dag_is_visited_once_and_cycles_remain_invalid(self) -> None:
        # Independent DAG invariant: each distinct collection should be visited
        # once. Count iteration instead of a machine-dependent timing threshold.
        class CountingList(list):
            visits = 0

            def __iter__(self):
                type(self).visits += 1
                if type(self).visits > 21:
                    raise AssertionError("Shared DAG collections must be visited once")
                return super().__iter__()

        shared = CountingList([0, 0])
        for _ in range(20):
            shared = CountingList([shared, shared])
        matchers._ensure_acyclic_yaml(shared)
        self.assertLessEqual(CountingList.visits, 21)
        nodes = ["a0: &a0 [0, 0]"] + [
            f"a{i}: &a{i} [*a{i-1}, *a{i-1}]" for i in range(1, 30)
        ]
        self.assertTrue(evaluate_assertion(
            EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, "a0"), "\n".join(nodes)).passed)
        with self.assertRaises(InvalidEvidenceInputError):
            evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, ""), "a: &a [*a]")

    def test_json_validation_does_not_leak_recursion_errors(self) -> None:
        # Materialize independently: isolate post-parse validation from CPython's
        # own JSON depth limit, which varies with platform and caller stack.
        value = "leaf"
        for _ in range(2000):
            value = [value]
        with mock.patch.object(matchers.json, "loads", return_value=value):
            result = evaluate_assertion(EvidenceAssertion(MatcherKind.JSON_POINTER_EXISTS, ""), "[]")
        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("",))
        try:
            result = evaluate_assertion(EvidenceAssertion(MatcherKind.JSON_POINTER_EXISTS, ""),
                                        "[" * 2000 + "0" + "]" * 2000)
        except InvalidEvidenceInputError:
            pass  # The decoder's own platform-dependent depth limit is allowed.
        else:
            self.assertTrue(result.passed)
            self.assertEqual(result.resolved_node_paths, ("",))
        with mock.patch.object(matchers.json, "loads", side_effect=RecursionError):
            with self.assertRaises(InvalidEvidenceInputError):
                evaluate_assertion(EvidenceAssertion(MatcherKind.JSON_POINTER_EXISTS, ""), "[]")

    def test_invalid_yaml_formatted_traceback_contains_no_source_snippet(self) -> None:
        marker = "synthetic-token-123"
        content = f'value: "{marker}"\n broken: true\n'
        try:
            evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, ""), content)
        except InvalidEvidenceInputError as error:
            self.assertNotIn(marker, "".join(traceback.format_exception(error)))
        else:
            self.fail("Malformed YAML must fail closed")

    def test_yaml_11_directive_and_invalid_explicit_core_scalars_fail_closed(self) -> None:
        for content in ("%YAML 1.1\n---\non: true\n", "value: !!bool yes\n",
                        "value: !!int 0b10\n", "value: !!null other\n",
                        "value: !!timestamp invalid\n", "value: 2026-02-30\n"):
            with self.subTest(content=content):
                with self.assertRaises(InvalidEvidenceInputError):
                    evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, ""), content)

    def test_yaml_12_directive_and_on_key_are_preserved(self) -> None:
        result = evaluate_assertion(self._equals(
            MatcherKind.YAML_PATH_EQUALS, "on.push", ExpectedScalarKind.NULL, None
        ), "%YAML 1.2\n---\non:\n  push:\n")
        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("/on/push",))

    def test_yaml_rejects_non_core_tags_and_accepts_frozen_tags(self) -> None:
        rejected = ("!!binary Zm9v", "!!set {a: null}", "!!omap [{a: 1}]",
                    "!!pairs [{a: 1}]", "!private value")
        assertion = EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, "value")
        for source in rejected:
            with self.subTest(source=source), self.assertRaises(InvalidEvidenceInputError):
                evaluate_assertion(assertion, f"value: {source}")
        for source in ('!!str "yes"', "!!bool true", "!!int 012", "!!float 1.5",
                       "!!null null", "!!map {a: 1}", "!!seq [1]",
                       "!!timestamp 2001-12-15"):
            with self.subTest(source=source):
                self.assertTrue(evaluate_assertion(assertion, f"value: {source}").passed)

    def test_yaml_rejects_escaped_surrogates_in_keys_and_values(self) -> None:
        for content in ('value: "\\uD800"', 'value: "\\uDFFF"',
                        '"\\uD800": valid', 'value: "\\uD83D\\uDE00"'):
            with self.subTest(content=content), self.assertRaises(InvalidEvidenceInputError):
                evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, ""), content)
        result = evaluate_assertion(self._equals(
            MatcherKind.YAML_PATH_EQUALS, "value", ExpectedScalarKind.STRING, "😀"
        ), 'value: "\\U0001F600"')
        self.assertTrue(result.passed)

    def test_shared_scalar_alias_is_validated_once(self) -> None:
        class CountingString(str):
            visits = 0

            def __iter__(self):
                type(self).visits += 1
                if type(self).visits > 1:
                    raise AssertionError("Shared scalar must be Unicode-validated once")
                return super().__iter__()

        shared = CountingString("safe" * 2500)
        matchers._ensure_acyclic_yaml([shared] * 1000)
        self.assertEqual(CountingString.visits, 1)
        content = 'value: &text "safe"\naliases: [' + ', '.join(['*text'] * 1000) + ']'
        self.assertTrue(evaluate_assertion(
            EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, "aliases"), content).passed)

    def test_valid_large_json_integer_has_no_interpreter_digit_cap(self) -> None:
        original_limit = sys.get_int_max_str_digits()
        digits = "1" * 5000
        expected = (10 ** 5000 - 1) // 9  # Arithmetic oracle, independent of parser.
        for sign, integer in (("", expected), ("-", -expected)):
            with self.subTest(sign=sign):
                source = sign + digits
                self.assertTrue(evaluate_assertion(
                    EvidenceAssertion(MatcherKind.JSON_POINTER_EXISTS, ""), source).passed)
                self.assertTrue(evaluate_assertion(self._equals(
                    MatcherKind.JSON_POINTER_EQUALS, "", ExpectedScalarKind.INTEGER, integer
                ), source).passed)
        self.assertEqual(sys.get_int_max_str_digits(), original_limit)

    def test_valid_large_yaml_integer_has_no_interpreter_digit_cap(self) -> None:
        digits = "1" * 5000
        expected = (10 ** 5000 - 1) // 9
        for sign, integer in (("", expected), ("+", expected), ("-", -expected)):
            with self.subTest(sign=sign):
                self.assertTrue(evaluate_assertion(self._equals(
                    MatcherKind.YAML_PATH_EQUALS, "value", ExpectedScalarKind.INTEGER, integer
                ), "value: " + sign + digits).passed)

    def test_decimal_conversion_uses_balanced_big_integer_multiplications(self) -> None:
        # Independent algorithmic invariant: for uniform nonzero digits, both
        # multiplication operands grow together, rather than one growing linearly
        # while the other stays at a small block width. No timing threshold.
        class TrackedInt(int):
            def __mul__(self, other):
                widths = (self.bit_length(), other.bit_length())
                if min(widths) and max(widths) > 8 * min(widths):
                    raise AssertionError("Decimal conversion must balance large operands")
                return TrackedInt(super().__mul__(other))

            def __add__(self, other):
                return TrackedInt(super().__add__(other))

            def __radd__(self, other):
                return TrackedInt(int(other) + int(self))

        with mock.patch.object(matchers, "int", side_effect=TrackedInt, create=True):
            result = matchers._parse_decimal_integer("1" * 4096)
        self.assertEqual(result, (10 ** 4096 - 1) // 9)

    def test_typed_values_do_not_coerce_in_yaml_or_json(self) -> None:
        cases = (("true", ExpectedScalarKind.INTEGER, 1),
                 ("1", ExpectedScalarKind.BOOLEAN, True),
                 ('"1"', ExpectedScalarKind.INTEGER, 1),
                 ("null", ExpectedScalarKind.STRING, "null"))
        for scalar, kind, value in cases:
            for matcher, path, content in (
                (MatcherKind.YAML_PATH_EQUALS, "value", f"value: {scalar}\n"),
                (MatcherKind.JSON_POINTER_EQUALS, "/value", f'{{"value": {scalar}}}'),
            ):
                with self.subTest(matcher=matcher, scalar=scalar, kind=kind):
                    result = evaluate_assertion(self._equals(matcher, path, kind, value), content)
                    self.assertFalse(result.passed)
                    self.assertEqual(result.discrepancy_code, DiscrepancyCode.VALUE_MISMATCH)

    def test_strings_are_exact_without_trim_case_fold_or_unicode_normalization(self) -> None:
        for source in (" value", "Value", "e\u0301"):
            expected = "é" if source == "e\u0301" else "value"
            with self.subTest(source=source):
                result = evaluate_assertion(self._equals(
                    MatcherKind.JSON_POINTER_EQUALS, "/value", ExpectedScalarKind.STRING, expected
                ), '{"value": "' + source + '"}')
                self.assertFalse(result.passed)

    def test_float_and_collection_nodes_exist_but_are_not_comparable(self) -> None:
        for source in (".5", "1e3", ".nan", "+.INF", "[]", "{}"):
            with self.subTest(source=source):
                content = f"value: {source}\n"
                self.assertTrue(evaluate_assertion(
                    EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, "value"), content).passed)
                result = evaluate_assertion(self._equals(
                    MatcherKind.YAML_PATH_EQUALS, "value", ExpectedScalarKind.STRING, source
                ), content)
                self.assertEqual(result.discrepancy_code, DiscrepancyCode.UNCOMPARABLE_NODE)

    def test_yaml_path_uses_literal_keys_and_wildcard_traversal_order(self) -> None:
        result = evaluate_assertion(self._equals(
            MatcherKind.YAML_PATH_EQUALS, " key/~ .v[*]", ExpectedScalarKind.STRING, "yes"
        ), '" key/~ ":\n  v: [yes, no, yes]\n')
        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("/ key~1~0 /v/0", "/ key~1~0 /v/2"))

    def test_invalid_path_is_rejected_before_parsing_evidence(self) -> None:
        for matcher, path in ((MatcherKind.YAML_PATH_EXISTS, "values[١]"),
                              (MatcherKind.YAML_PATH_EXISTS, "[0]"),
                              (MatcherKind.JSON_POINTER_EXISTS, "#/key")):
            with self.subTest(path=path):
                with self.assertRaises(InvalidRuleError):
                    evaluate_assertion(EvidenceAssertion(matcher, path), "invalid raw evidence")

    def test_json_pointer_root_and_literal_object_index_keys(self) -> None:
        root = evaluate_assertion(self._equals(
            MatcherKind.JSON_POINTER_EQUALS, "", ExpectedScalarKind.NULL, None
        ), "null")
        self.assertTrue(root.passed)
        self.assertEqual(root.resolved_node_paths, ("",))
        result = evaluate_assertion(self._equals(
            MatcherKind.JSON_POINTER_EQUALS, "/01", ExpectedScalarKind.BOOLEAN, True
        ), '{"01": true}')
        self.assertTrue(result.passed)

    def test_result_requires_closed_immutable_field_types(self) -> None:
        for create in (
            lambda: MatcherResult(1, (), None),
            lambda: MatcherResult(True, ["/value"], None),
            lambda: MatcherResult(False, (), "NO_NODE_MATCH"),
            lambda: MatcherResult(True, ("invalid-pointer",), None),
            lambda: MatcherResult(False, ("/value",), DiscrepancyCode.NO_NODE_MATCH),
            lambda: MatcherResult(False, (), DiscrepancyCode.VALUE_MISMATCH),
            lambda: MatcherResult(True, ("/value", "/value"), None),
        ):
            with self.subTest(create=create):
                with self.assertRaises(ValueError):
                    create()

    def test_yaml_collection_keys_are_valid_but_not_path_navigable(self) -> None:
        for document in (
            '? [a, b]\n: value\nordinary: found\n',
            '? {a: 1, b: 2}\n: value\nordinary: found\n',
            '? [{a: [1, 2]}, b]\n: value\nordinary: found\n',
        ):
            with self.subTest(document=document):
                root = evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, ''), document)
                self.assertEqual(root.resolved_node_paths, ('',))
                ordinary = evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, 'ordinary'), document)
                self.assertEqual(ordinary.resolved_node_paths, ('/ordinary',))
                self.assertFalse(evaluate_assertion(EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, 'a, b'), document).passed)

    def test_yaml_collection_key_equality_ignores_mapping_order_and_keeps_tags(self) -> None:
        root = EvidenceAssertion(MatcherKind.YAML_PATH_EXISTS, '')
        for document in (
            '? [a, b]\n: first\n? [a, b]\n: second\n',
            '? {a: 1, b: 2}\n: first\n? {b: 2, a: 1}\n: second\n',
            '? {a: 1, a: 2}\n: value\n',
            '? &loop [*loop]\n: value\n',
            '? [!private raw-secret]\n: value\n',
            '? ["\\uD800"]\n: value\n',
        ):
            with self.subTest(document=document):
                with self.assertRaises(InvalidEvidenceInputError):
                    evaluate_assertion(root, document)
        self.assertTrue(evaluate_assertion(root, '? [true]\n: first\n? [1]\n: second\n').passed)

    def test_yaml_empty_path_targets_document_root(self) -> None:
        result = evaluate_assertion(
            self._equals(
                MatcherKind.YAML_PATH_EQUALS,
                "",
                ExpectedScalarKind.NULL,
                None,
            ),
            "",
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("",))

    def test_yaml_path_rejects_unsupported_and_malformed_tokens(self) -> None:
        invalid_paths = (
            "jobs..steps",
            "jobs.steps[01]",
            "jobs.steps['first']",
            "jobs.steps[?(@.name)]",
            "jobs.steps.",
            "jobs.steps]",
            "jobs.steps\\name",
        )
        for path in invalid_paths:
            with self.subTest(path=path):
                assertion = EvidenceAssertion(
                    MatcherKind.YAML_PATH_EXISTS, target_path_expression=path
                )
                with self.assertRaises(InvalidRuleError):
                    evaluate_assertion(assertion, "jobs: {}\n")

    def test_json_pointer_decodes_escaped_keys_and_reports_canonical_node_path(self) -> None:
        assertion = self._equals(
            MatcherKind.JSON_POINTER_EQUALS,
            "/a~1b/~0key",
            ExpectedScalarKind.STRING,
            "matched",
        )

        result = evaluate_assertion(assertion, '{"a/b": {"~key": "matched"}}')

        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("/a~1b/~0key",))

    def test_json_pointer_array_index_requires_canonical_index(self) -> None:
        assertion = self._equals(
            MatcherKind.JSON_POINTER_EQUALS,
            "/steps/1/name",
            ExpectedScalarKind.STRING,
            "sign",
        )
        result = evaluate_assertion(assertion, '{"steps": [{}, {"name": "sign"}]}')
        self.assertTrue(result.passed)
        self.assertEqual(result.resolved_node_paths, ("/steps/1/name",))

        noncanonical = EvidenceAssertion(
            MatcherKind.JSON_POINTER_EXISTS, target_path_expression="/steps/01"
        )
        self.assertEqual(
            evaluate_assertion(noncanonical, '{"steps": [{}, {"name": "sign"}]}').discrepancy_code,
            DiscrepancyCode.NO_NODE_MATCH,
        )

    def test_json_pointer_invalid_escape_is_an_invalid_rule(self) -> None:
        assertion = EvidenceAssertion(
            MatcherKind.JSON_POINTER_EXISTS, target_path_expression="/a~2b"
        )

        with self.assertRaises(InvalidRuleError):
            evaluate_assertion(assertion, '{"a~2b": true}')

    def test_mismatch_result_contains_no_expected_or_observed_value(self) -> None:
        secret = "raw-token-should-never-appear"
        assertion = self._equals(
            MatcherKind.JSON_POINTER_EQUALS,
            "/credential",
            ExpectedScalarKind.STRING,
            "expected-value",
        )

        result = evaluate_assertion(assertion, f'{{"credential": "{secret}"}}')

        self.assertEqual(result.discrepancy_code, DiscrepancyCode.VALUE_MISMATCH)
        self.assertNotIn(secret, repr(result))
        self.assertNotIn("expected-value", repr(result))

    def test_yaml_duplicate_keys_multiple_documents_custom_tag_and_recursive_alias_fail(self) -> None:
        invalid_documents = (
            "credential: first\ncredential: second\n",
            "value: one\n---\nvalue: two\n",
            "value: !private secret\n",
            "value: &loop [*loop]\n",
            "value: raw-secret\x00\n",
        )
        assertion = EvidenceAssertion(
            MatcherKind.YAML_PATH_EXISTS, target_path_expression="credential"
        )
        for content in invalid_documents:
            with self.subTest(content=content):
                with self.assertRaises(InvalidEvidenceInputError) as context:
                    evaluate_assertion(assertion, content)
                self.assertNotIn("secret", str(context.exception))

    def test_json_duplicate_keys_non_rfc_constant_and_unpaired_surrogate_fail(self) -> None:
        invalid_documents = (
            '{"credential": "first", "credential": "second"}',
            '{"value": NaN}',
            '{"value": "\\ud800"}',
        )
        assertion = EvidenceAssertion(
            MatcherKind.JSON_POINTER_EXISTS, target_path_expression="/credential"
        )
        for content in invalid_documents:
            with self.subTest(content=content):
                with self.assertRaises(InvalidEvidenceInputError):
                    evaluate_assertion(assertion, content)

    def test_yaml_equals_mismatch_reports_all_evaluated_nodes_without_values(self) -> None:
        assertion = self._equals(
            MatcherKind.YAML_PATH_EQUALS,
            "values[*]",
            ExpectedScalarKind.STRING,
            "expected",
        )

        result = evaluate_assertion(assertion, "values:\n  - secret-one\n  - secret-two\n")

        self.assertFalse(result.passed)
        self.assertEqual(result.discrepancy_code, DiscrepancyCode.VALUE_MISMATCH)
        self.assertEqual(result.resolved_node_paths, ("/values/0", "/values/1"))
        self.assertNotIn("secret-one", repr(result))
        self.assertNotIn("secret-two", repr(result))


if __name__ == "__main__":
    unittest.main()
