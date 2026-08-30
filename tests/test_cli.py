from __future__ import annotations

import json
from pathlib import Path

import pytest

from locus_md.cli import main


def test_cli_config_validate_json(example_workspace: Path, capsys) -> None:
    code = main(["--config", str(example_workspace / ".locus" / "locus.md.toml"), "--format", "json", "config", "validate"])
    captured = capsys.readouterr()
    assert code == 0
    payload = json.loads(captured.out)
    assert payload["state"] == "passed"


def test_cli_sync_check_exit_code(example_workspace: Path, capsys) -> None:
    tasks = example_workspace / "data" / "tasks.json"
    text = tasks.read_text(encoding="utf-8").replace('"status": "doing"', '"status": "done"')
    tasks.write_text(text, encoding="utf-8")
    code = main(["--config", str(example_workspace / ".locus" / "locus.md.toml"), "sync", "--check", "--offline"])
    capsys.readouterr()
    assert code == 1


def test_common_options_work_after_subcommand(example_workspace: Path, capsys) -> None:
    code = main(["lint", "--config", str(example_workspace / ".locus" / "locus.md.toml"), "--format", "json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["mode"] == "lint"


def test_cli_version_uses_primary_command_name(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == "locus-md 0.3.0"
