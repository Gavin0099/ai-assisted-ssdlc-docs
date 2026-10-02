"""REPORT-4C application: admit fixed inputs, project, stage three new files.

Run with python -m tools.generate_assessment_markdown --help. A caller-owned
auxiliary allowlist is explicit. Existing bundles are never replaced: identical
reruns are no-ops; differing output requires a new output directory.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from urllib.parse import quote

from tools.assessment_markdown import MarkdownProjectionError, render_markdown
from tools.report_data_contract import ArtifactStore, ReportContractError
from tools.review_lifecycle_contract import load_review_lifecycle


TEMPLATE_ROOT = Path(__file__).resolve().parents[1] / "templates"
TEMPLATE_FILES = {"summary": "s1-assessment-summary.md", "actions": "s1-assessment-actions.md", "technical": "s1-assessment-technical-review.md"}


def _no_link_ancestors(path: Path) -> None:
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise MarkdownProjectionError("output path cannot contain symlink/junction components")


@contextmanager
def _directory_chain(path: Path, *, create: bool = False, renamable: bool = False):
    """Pin the intended directories during output, including actual OS identity.

    Windows directory handles omit FILE_SHARE_DELETE to prevent replacement of
    the directory chain while files are written. Linux uses O_NOFOLLOW directory
    descriptors, relative opens and relative rename; pathname swaps cannot
    redirect data writes. Unsupported platforms fail closed.
    """
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                      wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
    elif not sys_platform_linux():
        raise MarkdownProjectionError("safe directory output supports Windows and Linux only")
    with ExitStack() as held:
        descriptor = None
        for directory in reversed((path, *path.parents)):
            if os.name == "nt":
                if create:
                    directory.mkdir(exist_ok=True)
                _no_link_ancestors(directory)
                access = 0x80 | (0x10000 if renamable and directory == path else 0)
                handle = kernel.CreateFileW(str(directory), access, 0x1 | 0x2, None, 3, 0x02000000, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                try:
                    fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
                except BaseException:
                    kernel.CloseHandle(handle)
                    raise
            else:
                if descriptor is not None and create:
                    try:
                        os.mkdir(directory.name, dir_fd=descriptor)
                    except FileExistsError:
                        pass
                fd = os.open(str(directory) if descriptor is None else directory.name,
                             os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            held.callback(os.close, fd)
            if ArtifactStore._opened_path(fd) != directory:
                raise MarkdownProjectionError("opened output directory differs from intended boundary")
            descriptor = fd
        yield descriptor


def sys_platform_linux() -> bool:
    import sys
    return sys.platform.startswith("linux")


def _write_file(stage: Path, directory_fd: int, name: str, raw: bytes) -> None:
    fd = os.open(str(stage / name) if os.name == "nt" else name,
                 os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
                 0o600, **({} if os.name == "nt" else {"dir_fd": directory_fd}))
    with os.fdopen(fd, "wb") as opened:
        if not stat.S_ISREG(os.fstat(opened.fileno()).st_mode) or ArtifactStore._opened_path(opened.fileno()) != stage / name:
            raise MarkdownProjectionError("opened output file differs from intended stage")
        opened.write(raw)



def _rename_noreplace(source: str, destination: str, source_fd: int, destination_fd: int) -> None:
    """Linux atomic publication must never replace a concurrently created name."""
    import ctypes
    library = ctypes.CDLL(None, use_errno=True)
    rename = getattr(library, "renameat2", None)
    if rename is None:
        raise MarkdownProjectionError("atomic no-replace publication is unavailable")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_fd, os.fsencode(source), destination_fd, os.fsencode(destination), 1) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), destination)


def _publish_stage(stage: Path, stage_fd: int, temp_fd: int, parent_fd: int, out: Path) -> None:
    """Publish the pinned directory, then confirm the published OS identity."""
    if ArtifactStore._opened_path(stage_fd) != stage or ArtifactStore._opened_path(parent_fd) != out.parent:
        raise MarkdownProjectionError("staging identity or output boundary changed")
    if out.exists() or out.is_symlink():
        raise MarkdownProjectionError("output appeared while staging; refusing replacement")
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        class RenameInfo(ctypes.Structure):
            _fields_ = [("ReplaceIfExists", wintypes.BOOL), ("RootDirectory", wintypes.HANDLE),
                        ("FileNameLength", wintypes.DWORD), ("FileName", wintypes.WCHAR * 1)]
        # FileRenameInfo: rename through the still-held DELETE-capable source
        # handle with a still-pinned destination chain. Never reopen stage by
        # pathname. The Win32 entry point uses NULL RootDirectory and full name.
        name = str(out).encode("utf-16-le")
        raw = ctypes.create_string_buffer(RenameInfo.FileName.offset + len(name) + 2)
        info = RenameInfo.from_buffer(raw)
        info.ReplaceIfExists = False
        info.RootDirectory = None
        info.FileNameLength = len(name)
        ctypes.memmove(ctypes.addressof(raw) + RenameInfo.FileName.offset, name, len(name))
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetFileInformationByHandle.restype = wintypes.BOOL
        if not kernel.SetFileInformationByHandle(msvcrt.get_osfhandle(stage_fd), 3, raw, len(raw)):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        _rename_noreplace(stage.name, out.name, temp_fd, parent_fd)
        published_fd = os.open(out.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            original, published = os.fstat(stage_fd), os.fstat(published_fd)
            if (original.st_dev, original.st_ino) != (published.st_dev, published.st_ino):
                raise MarkdownProjectionError("published directory is not the pinned stage")
        finally:
            os.close(published_fd)
    if ArtifactStore._opened_path(stage_fd) != out:
        raise MarkdownProjectionError("published handle is outside the intended output")


def _source_links(loaded, store: ArtifactStore, lifecycle_path: Path, out: Path) -> dict[str, str]:
    rd = loaded.report_data
    paths = {"report-data": rd.path, "review lifecycle": lifecycle_path}
    assessment_path = store.resolve(rd.data.assessment_ref.path, rd.path)
    paths["assessment"] = assessment_path
    paths["corpus metadata"] = store.resolve(rd.data.corpus_metadata_ref.path, rd.path)
    paths["manifest"] = store.resolve(rd.assessment.report.target.manifest_path, assessment_path)
    for ref in rd.data.retained_content_refs:
        paths["retained " + ref.path] = store.resolve(ref.path, rd.path)
    for a in rd.data.auxiliary_sources:
        paths["auxiliary " + a.source_ref] = store.resolve(a.artifact_ref.path, rd.path)
    lifecycle_refs = {"machine baseline": loaded.lifecycle.machine_baseline_ref,
                      "acceptance decision": loaded.lifecycle.acceptance_ref,
                      "sync target": loaded.lifecycle.sync.target_ref,
                      "sync decision": loaded.lifecycle.sync.decision_ref,
                      "sync verification": loaded.lifecycle.sync.verification_ref}
    for label, ref in lifecycle_refs.items():
        if ref is not None:
            paths[label] = store.resolve(ref.path, lifecycle_path)
    return {label: quote(os.path.relpath(path, out).replace(os.sep, "/"), safe="/.-_~") for label, path in paths.items()}


def _write_bundle(out: Path, documents: dict[str, str]) -> str:
    encoded = {name: body.encode("utf-8") for name, body in documents.items()}
    _no_link_ancestors(out)
    with _directory_chain(out.parent, create=True) as parent_fd:
        if out.exists():
            with _directory_chain(out):
                if {p.name for p in out.iterdir()} != set(encoded):
                    raise MarkdownProjectionError("existing output is not the identical three-file bundle")
                store = ArtifactStore(out)
                for name, raw in encoded.items():
                    _no_link_ancestors(out / name)
                    actual, observed = store.read_path(name)
                    if actual != out / name or observed != raw:
                        raise MarkdownProjectionError("existing output differs; choose a new output directory")
            return "unchanged"
        with tempfile.TemporaryDirectory(prefix=".report-4c-", dir=out.parent) as temp:
            stage = Path(temp) / "bundle"
            with _directory_chain(Path(temp)) as temp_fd:
                with _directory_chain(stage, create=True, renamable=True) as stage_fd:
                    for name, raw in encoded.items():
                        _write_file(stage, stage_fd, name, raw)
                    _publish_stage(stage, stage_fd, temp_fd, parent_fd, out)
                    _no_link_ancestors(out)
                    if {p.name for p in out.iterdir()} != set(encoded):
                        raise MarkdownProjectionError("published file set differs from rendered bundle")
                    published = ArtifactStore(out)
                    for name, raw in encoded.items():
                        actual, observed = published.read_path(name)
                        if actual != out / name or observed != raw:
                            raise MarkdownProjectionError("published bytes differ from rendered bundle")
    return "created"


def generate(report_root: Path, lifecycle: str, out_dir: Path, *, date: str,
             title: str = "SSDLC 文件評估", authorized_auxiliary_sources: frozenset[str] = frozenset()) -> dict:
    store = ArtifactStore(report_root)
    _no_link_ancestors(out_dir.absolute())
    out = out_dir.resolve()
    if (out.is_relative_to(store.root) or store.root.is_relative_to(out)
            or out.is_relative_to(TEMPLATE_ROOT) or TEMPLATE_ROOT.is_relative_to(out)):
        raise MarkdownProjectionError("output must be disjoint from input bundle and templates")
    loaded = load_review_lifecycle(lifecycle, store.root, authorized_auxiliary_sources=authorized_auxiliary_sources)
    lifecycle_path = store.resolve(lifecycle)
    template_raw = {kind: (TEMPLATE_ROOT / name).read_bytes() for kind, name in TEMPLATE_FILES.items()}
    # Preserve raw template fingerprints; match Path.read_text universal newline
    # semantics for presentation text in normal Windows CRLF checkouts.
    templates = {kind: raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
                 for kind, raw in template_raw.items()}
    docs = render_markdown(loaded, date=date, title=title, templates=templates,
                           source_links=_source_links(loaded, store, lifecycle_path, out))
    write_status = _write_bundle(out, docs)
    return {"status": write_status, "report_id": loaded.report_data.data.report_id,
            "date": date, "report_data_sha256": loaded.report_data.sha256,
            "assessment_sha256": loaded.report_data.assessment.sha256,
            "template_sha256": {kind: hashlib.sha256(raw).hexdigest() for kind, raw in template_raw.items()},
            "output_sha256": {name: hashlib.sha256(body.encode("utf-8")).hexdigest() for name, body in docs.items()},
            "accepted_record": loaded.accepted, "sync_state": loaded.lifecycle.sync.state,
            "html_generated": False, "inputs_written": False, "published": False}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--lifecycle", default="review-lifecycle.json", help="relative to report root")
    parser.add_argument("--out-dir", type=Path, required=True, help="new directory disjoint from input bundle")
    parser.add_argument("--date", required=True, help="explicit generation date YYYY-MM-DD")
    parser.add_argument("--title", default="SSDLC 文件評估")
    parser.add_argument("--allow-auxiliary-source", action="append", default=[], help="explicit caller-approved source path; repeat as needed")
    args = parser.parse_args(argv)
    try:
        result = generate(args.report_root, args.lifecycle, args.out_dir, date=args.date, title=args.title,
                          authorized_auxiliary_sources=frozenset(args.allow_auxiliary_source))
    except (ReportContractError, MarkdownProjectionError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
