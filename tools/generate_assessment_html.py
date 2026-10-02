"""REPORT-4D: admit recorded data, verify REPORT-4C Markdown, render offline HTML.

This is a presentation adapter. It reuses the shared reader and fixed templates,
and copies the verified Markdown unchanged into a separate local reading bundle.
No prose inference, assessment updates, public hosting or lifecycle decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.assessment_markdown import MarkdownProjectionError, filenames, render_markdown
from tools.generate_assessment_markdown import TEMPLATE_FILES, TEMPLATE_ROOT, _no_link_ancestors, _source_links, _write_bundle
from tools.generate_assessment_web import ReportError, TEMPLATE, render_bundle
from tools.report_data_contract import ArtifactRef, ArtifactStore, ReportContractError
from tools.review_lifecycle_contract import load_review_lifecycle


def generate(report_root: Path, lifecycle: str, markdown_dir: Path, out_dir: Path, *,
             date: str, title: str = "SSDLC 文件評估",
             authorized_auxiliary_sources: frozenset[str] = frozenset()) -> dict:
    store = ArtifactStore(report_root)
    source = ArtifactStore(markdown_dir)
    _no_link_ancestors(out_dir.absolute())
    out = out_dir.resolve()
    for protected in (store.root, source.root, TEMPLATE_ROOT):
        if out.is_relative_to(protected) or protected.is_relative_to(out):
            raise MarkdownProjectionError("HTML output must be disjoint from inputs and templates")
    loaded = load_review_lifecycle(lifecycle, store.root,
                                  authorized_auxiliary_sources=authorized_auxiliary_sources)
    lifecycle_path = store.resolve(lifecycle)
    links = _source_links(loaded, store, lifecycle_path, source.root)
    if links != _source_links(loaded, store, lifecycle_path, out):
        raise MarkdownProjectionError("unchanged Markdown requires the same relative source links; choose a sibling reading directory")
    templates = {kind: (TEMPLATE_ROOT / name).read_text(encoding="utf-8")
                 for kind, name in TEMPLATE_FILES.items()}
    expected = render_markdown(loaded, date=date, title=title, templates=templates, source_links=links)
    documents = {}
    for name, body in expected.items():
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        _, raw = source.read_ref(ArtifactRef(name, digest), source.root / name)
        documents[name] = raw.decode("utf-8")
    names = filenames(loaded.report_data.data.report_id)
    html_name = loaded.report_data.data.report_id + "-report.html"
    metadata_path = store.resolve(loaded.report_data.data.corpus_metadata_ref.path, loaded.report_data.path)
    page = render_bundle(*(out / names[k] for k in ("summary", "actions", "technical")),
                         metadata_path, out / html_name, projection=loaded,
                         verified_documents=[documents[names[k]] for k in ("summary", "actions", "technical")])
    documents[html_name] = page
    result = _write_bundle(out, documents)
    return {"status": result, "report_id": loaded.report_data.data.report_id,
            "date": date, "output_directory": str(out),
            "output_sha256": {n: hashlib.sha256(v.encode("utf-8")).hexdigest() for n, v in documents.items()},
            "markdown_source_sha256": {n: hashlib.sha256(v.encode("utf-8")).hexdigest() for n, v in expected.items()},
            "report_data_sha256": loaded.report_data.sha256,
            "assessment_sha256": loaded.report_data.assessment.sha256,
            "template_sha256": hashlib.sha256(TEMPLATE.read_bytes()).hexdigest(),
            "tool_sha256": {n: hashlib.sha256((Path(__file__).parent / n).read_bytes()).hexdigest()
                            for n in ("generate_assessment_html.py", "generate_assessment_web.py", "assessment_markdown.py", "generate_assessment_markdown.py")},
            "accepted_record": loaded.accepted, "sync_state": loaded.lifecycle.sync.state,
            "html_generated": True, "inputs_written": False, "published": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--lifecycle", default="review-lifecycle.json")
    parser.add_argument("--markdown-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--title", default="SSDLC 文件評估")
    parser.add_argument("--allow-auxiliary-source", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = generate(args.report_root, args.lifecycle, args.markdown_dir, args.out_dir,
                          date=args.date, title=args.title,
                          authorized_auxiliary_sources=frozenset(args.allow_auxiliary_source))
    except (ReportContractError, MarkdownProjectionError, ReportError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
