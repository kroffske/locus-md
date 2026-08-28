from __future__ import annotations

import json
from pathlib import Path

from locus_md.config import load_config
from locus_md.engine import Engine
from locus_md.models import RunState


def _engine(workspace: Path) -> Engine:
    return Engine(load_config(explicit=workspace / ".locus" / "config.ini"))


def test_example_lint_verify_and_sync_are_clean(example_workspace: Path) -> None:
    engine = _engine(example_workspace)
    assert engine.lint().state == RunState.PASSED
    assert engine.verify(offline=True).state == RunState.PASSED
    assert engine.sync(offline=True).state == RunState.PASSED


def test_provider_change_produces_patch_and_write_is_idempotent(example_workspace: Path) -> None:
    tasks_path = example_workspace / "data" / "tasks.json"
    payload = json.loads(tasks_path.read_text(encoding="utf-8"))
    payload["records"][1]["fields"]["status"] = "done"
    tasks_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    document_path = example_workspace / "docs" / "milestones.md"
    before = document_path.read_text(encoding="utf-8")
    prefix = before.split("<!-- locus:milestone tasks begin -->", 1)[0]
    suffix = before.split("<!-- locus:milestone tasks end -->", 1)[1]
    engine = _engine(example_workspace)
    verify = engine.verify(offline=True)
    assert verify.state == RunState.FAILED
    assert any(finding.code == "DOC-BLOCK-021" for finding in verify.findings)
    check = engine.sync(offline=True)
    assert check.state == RunState.FAILED
    assert check.patches
    write = engine.sync(write=True, offline=True)
    assert write.state == RunState.PASSED
    after = document_path.read_text(encoding="utf-8")
    assert after.split("<!-- locus:milestone tasks begin -->", 1)[0] == prefix
    assert after.split("<!-- locus:milestone tasks end -->", 1)[1] == suffix
    assert "| T-102 | Implement marker parser | done |" in after
    second = _engine(example_workspace).sync(offline=True)
    assert second.state == RunState.PASSED
    assert second.patches == []


def test_manual_projection_edit_is_detected_by_lock(example_workspace: Path) -> None:
    path = example_workspace / "docs" / "milestones.md"
    text = path.read_text(encoding="utf-8").replace("| T-102 | Implement marker parser | doing |", "| T-102 | Hand edited | doing |")
    path.write_text(text, encoding="utf-8")
    report = _engine(example_workspace).lint()
    assert report.state == RunState.FAILED
    assert any(finding.code == "DOC-BLOCK-020" for finding in report.findings)


def test_crlf_is_preserved_during_sync(example_workspace: Path) -> None:
    document = example_workspace / "docs" / "milestones.md"
    document.write_bytes(document.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
    tasks = json.loads((example_workspace / "data" / "tasks.json").read_text(encoding="utf-8"))
    tasks["records"][0]["fields"]["status"] = "open"
    (example_workspace / "data" / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _engine(example_workspace).sync(write=True, offline=True)
    raw = document.read_bytes()
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")


def test_network_provider_uses_declared_snapshot_offline(example_workspace: Path) -> None:
    config_path = example_workspace / ".locus" / "config.ini"
    text = config_path.read_text(encoding="utf-8").replace("network = false", "network = true")
    config_path.write_text(text, encoding="utf-8")
    report = _engine(example_workspace).verify(offline=True)
    assert report.state == RunState.PASSED
    assert report.snapshots["tasks"]["consistency"] == "local"
