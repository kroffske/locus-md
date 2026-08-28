from __future__ import annotations

import os
import stat
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .errors import WriteConflict
from .markdown import scan_managed_blocks
from .models import Patch
from .utils import digest_bytes, is_inside


def _read_utf8(path: Path) -> tuple[bytes, str, bool]:
    if not path.exists():
        return b"", "", False
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    payload = raw[3:] if bom else raw
    try:
        return raw, payload.decode("utf-8"), bom
    except UnicodeDecodeError as exc:
        raise WriteConflict(path, f"target is not UTF-8: {exc}") from exc


def apply_patches(patches: Iterable[Patch], *, workspace_root: Path, lock_path: Path | None = None) -> list[Path]:
    grouped: dict[Path, list[Patch]] = defaultdict(list)
    for patch in patches:
        if not is_inside(patch.absolute_path, workspace_root):
            raise WriteConflict(patch.absolute_path, "target escapes workspace")
        grouped[patch.absolute_path].append(patch)
    prepared: dict[Path, tuple[Path, str, int | None]] = {}
    try:
        for path, file_patches in grouped.items():
            if path.is_symlink():
                raise WriteConflict(path, "refusing to rewrite a symlink")
            raw, text, bom = _read_utf8(path)
            expected_digests = {patch.original_digest for patch in file_patches}
            if len(expected_digests) != 1 or digest_bytes(raw) not in expected_digests:
                raise WriteConflict(path, "source file changed since scan")
            ordered = sorted(file_patches, key=lambda patch: (patch.start, patch.end))
            previous_end = -1
            for patch in ordered:
                if patch.start < previous_end:
                    raise WriteConflict(path, "overlapping patches")
                if patch.start < 0 or patch.end < patch.start or patch.end > len(text):
                    raise WriteConflict(path, "patch span is outside the source text")
                if text[patch.start:patch.end] != patch.old_text:
                    raise WriteConflict(path, "patch source span no longer matches")
                previous_end = patch.end
            updated = text
            for patch in reversed(ordered):
                updated = updated[: patch.start] + patch.replacement + updated[patch.end :]
            if path.suffix.lower() in {".md", ".markdown"}:
                _, marker_findings = scan_managed_blocks(updated, display_path=str(path), surface_name="rewrite")
                if marker_findings:
                    raise WriteConflict(path, f"patched Markdown has invalid managed markers: {marker_findings[0].message}")
            encoded = updated.encode("utf-8")
            if bom:
                encoded = b"\xef\xbb\xbf" + encoded
            path.parent.mkdir(parents=True, exist_ok=True)
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else None
            handle = tempfile.NamedTemporaryFile(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False)
            temp_path = Path(handle.name)
            try:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                handle.close()
            if mode is not None:
                os.chmod(temp_path, mode)
            prepared[path] = (temp_path, digest_bytes(raw), mode)
        for path, (_, original_digest, _) in prepared.items():
            current = path.read_bytes() if path.exists() else b""
            if digest_bytes(current) != original_digest:
                raise WriteConflict(path, "source file changed while preparing transaction")
        ordered_paths = sorted(prepared, key=lambda path: (path == lock_path, str(path)))
        for path in ordered_paths:
            temp_path = prepared[path][0]
            os.replace(temp_path, path)
        return ordered_paths
    finally:
        for temp_path, _, _ in prepared.values():
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
