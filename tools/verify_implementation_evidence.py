"""S2-C2 CLI: explicit JSON ACL inputs, one format, one atomic report destination."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import tempfile

from tools.implementation_matchers import _parse_json_document
from tools.implementation_renderer import DeterministicImplementationRenderer
from tools.implementation_verification import ImplementationVerificationOrchestrator, VerificationInputError
from tools.repo_corpus_resolver import GitCapabilityError


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise VerificationInputError("Invalid CLI arguments; use --help for the required inputs.") from None


def _load_json(path):
    return _parse_json_document(Path(path).read_bytes().decode("utf-8", errors="strict"))


def _output_destination(output, inputs, repositories):
    raw = Path(output).absolute()
    if raw.is_symlink() or (raw.exists() and not raw.is_file()):
        raise VerificationInputError("Report destination must be a regular file or a new path.")
    destination = raw.parent.resolve() / raw.name
    if not destination.parent.is_dir():
        raise VerificationInputError("Report parent directory must already exist.")
    if any(destination == Path(p).resolve() for p in inputs):
        raise VerificationInputError("Report destination cannot replace an input file.")
    if any(destination.is_relative_to(Path(p).resolve()) for p in repositories):
        raise VerificationInputError("Read-only source repositories cannot contain the report destination.")
    return destination


def atomic_write(destination: Path, content: bytes) -> None:
    """Publish fully prepared bytes once; remove the temp on every failure path."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=destination.parent,
                                         prefix=".s2-report-", delete=False) as stream:
            temporary = Path(stream.name)
            if stream.write(content) != len(content):
                raise OSError("Incomplete temporary report write.")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None) -> int:
    try:
        parser = _Parser(description="Verify explicitly supplied S2 rules against pinned static repository evidence.")
        parser.add_argument("--verification-id", required=True)
        for name in ("assessment", "policy-manifest", "policy-repo", "product-manifest", "product-repo",
                     "ruleset", "expectations"):
            parser.add_argument("--" + name, required=True, type=Path)
        parser.add_argument("--allow-unverified-provenance", action="store_true")
        parser.add_argument("--format", choices=("json", "markdown"), default="json")
        parser.add_argument("--output", type=Path, help="One report file; default is stdout. Parent must exist.")
        args = parser.parse_args(argv)
        inputs = (args.assessment, args.policy_manifest, args.product_manifest, args.ruleset, args.expectations)
        destination = (_output_destination(args.output, inputs, (args.policy_repo, args.product_repo))
                       if args.output else None)
        record = ImplementationVerificationOrchestrator().verify(
            verification_id=args.verification_id, assessment_path=args.assessment,
            policy_manifest_path=args.policy_manifest, policy_repo_path=args.policy_repo,
            product_manifest_path=args.product_manifest, product_repo_path=args.product_repo,
            ruleset_data=_load_json(args.ruleset), expectation_set_data=_load_json(args.expectations),
            allow_unverified_provenance=args.allow_unverified_provenance)
        renderer = DeterministicImplementationRenderer()
        rendered = renderer.render_json(record) if args.format == "json" else renderer.render_markdown(record)
        content = rendered.encode("utf-8", errors="strict")
        if destination is not None:
            atomic_write(destination, content)
        else:
            # UTF-8 bytes on Windows as well as POSIX, after complete rendering.
            sys.stdout.buffer.write(content)
            sys.stdout.buffer.flush()
        return 0
    except Exception as exc:
        prerequisite = str(GitCapabilityError())
        message = prerequisite if type(exc) is VerificationInputError and str(exc) == prerequisite else "S2 verification or report publication failed closed."
        sys.stderr.write(message + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
