from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import validate
from importlib.resources import files

from locus_md.cli import main
from locus_md.config import load_config
from locus_md.engine import Engine
from locus_md.errors import ConfigError


def _workspace(tmp_path: Path, *, docs: str = "") -> Path:
    (tmp_path / ".locus").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("---\ndescription: readme\n---\n# Readme\n\n## Install\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# Agent contract\n", encoding="utf-8")
    (tmp_path / "docs" / "index.md").write_text("---\ndescription: index\n---\n# Index\n", encoding="utf-8")
    config = f'''[locus-md]
schema = 1
surfaces = ["root", "docs"]

[locus-md.surface.root]
root = "."
include = ["README.md", "AGENTS.md"]
frontmatter = "optional"

[locus-md.surface.docs]
root = "docs"
include = ["**/*.md"]

[locus-md.document.readme]
surface = "root"
path = "README.md"
description = "Human entry point."
guidance = "Explain installation."

[locus-md.document.readme.sections.install]
heading = "Install"
required = true
guidance = "Show one command."

[locus-md.document.agents]
surface = "root"
path = "AGENTS.md"
description = "Agent contract."

{docs}
'''
    path = tmp_path / ".locus" / "locus-md.toml"
    path.write_text(config, encoding="utf-8")
    return path


def test_root_agents_is_the_only_frontmatter_envelope_exception(tmp_path: Path) -> None:
    config = load_config(explicit=_workspace(tmp_path))
    report = Engine(config).lint()
    assert report.state.value == "passed"


def test_required_heading_and_nested_agents_frontmatter_are_findings(tmp_path: Path) -> None:
    config_path = _workspace(tmp_path, docs='''[locus-md.document.nested-agents]
surface = "docs"
path = "AGENTS.md"
description = "Nested agent instructions."
''')
    (tmp_path / "docs" / "AGENTS.md").write_text("# Nested\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("---\ndescription: readme\n---\n# Readme\n", encoding="utf-8")
    report = Engine(load_config(explicit=config_path)).lint()
    codes = {finding.code for finding in report.findings}
    assert {"DOC-SECTION-001", "DOC-ENV-001"}.issubset(codes)


def test_document_path_selection_and_heading_normalization_are_config_errors(tmp_path: Path) -> None:
    path = _workspace(tmp_path, docs='''[locus-md.document.bad]
surface = "docs"
path = "../README.md"
description = "Bad."
''')
    with pytest.raises(ConfigError, match="CFG-050"):
        load_config(explicit=path)


@pytest.mark.parametrize(
    ("name", "fragment", "code"),
    [
        ("duplicate", '''[locus-md.document.other]\nsurface = "root"\npath = "README.md"\ndescription = "Other."\n''', "CFG-053"),
        ("inactive", '''[locus-md.document.other]\nsurface = "missing"\npath = "other.md"\ndescription = "Other."\n''', "CFG-010"),
    ],
)
def test_document_declarations_validate_identity_surface_and_selection(tmp_path: Path, name: str, fragment: str, code: str) -> None:
    path = _workspace(tmp_path, docs=fragment)
    with pytest.raises(ConfigError, match=code):
        load_config(explicit=path)


def test_duplicate_normalized_headings_are_config_errors(tmp_path: Path) -> None:
    path = _workspace(tmp_path, docs='''[locus-md.document.readme.sections.first]
heading = "Install   now"

[locus-md.document.readme.sections.second]
heading = "Install now"
''')
    with pytest.raises(ConfigError, match="CFG-059"):
        load_config(explicit=path)


def test_document_path_excluded_by_surface_is_rejected_even_when_missing(tmp_path: Path) -> None:
    path = _workspace(tmp_path, docs='''[locus-md.document.other]
surface = "docs"
path = "missing.md"
description = "Missing."
''')
    text = path.read_text(encoding="utf-8").replace('include = ["**/*.md"]', 'include = ["**/*.md"]\nexclude = ["missing.md"]')
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ConfigError, match="CFG-054"):
        load_config(explicit=path)


def test_missing_document_and_ordinary_root_readme_frontmatter_are_findings(tmp_path: Path) -> None:
    path = _workspace(tmp_path, docs='''[locus-md.document.missing]
surface = "root"
path = "MISSING.md"
description = "Missing."
''')
    path.write_text(path.read_text(encoding="utf-8").replace('include = ["README.md", "AGENTS.md"]', 'include = ["README.md", "AGENTS.md", "MISSING.md"]'), encoding="utf-8")
    (tmp_path / "README.md").write_text("# Readme\n", encoding="utf-8")
    report = Engine(load_config(explicit=path)).lint()
    codes = {finding.code for finding in report.findings}
    assert {"DOC-DECL-001", "DOC-ENV-001"}.issubset(codes)


def test_heading_tokens_normalize_atx_setext_and_inline_text(tmp_path: Path) -> None:
    path = _workspace(tmp_path)
    (tmp_path / "README.md").write_text("---\ndescription: readme\n---\nInstall **now**\n------------\n\n##  Deploy  `safely`\n", encoding="utf-8")
    text = path.read_text(encoding="utf-8").replace('heading = "Install"', 'heading = "Install now"')
    path.write_text(text + '''[locus-md.document.readme.sections.deploy]
heading = "Deploy safely"
''', encoding="utf-8")
    report = Engine(load_config(explicit=path)).lint()
    assert not any(finding.code == "DOC-SECTION-001" for finding in report.findings)


def test_guide_json_is_inert_and_has_stable_schema(tmp_path: Path, capsys) -> None:
    path = _workspace(tmp_path)
    before = Engine(load_config(explicit=path)).lint().to_dict()
    assert main(["--config", str(path), "guide", "--format", "json", "readme"]) == 0
    payload = json.loads(capsys.readouterr().out)
    after = Engine(load_config(explicit=path)).lint().to_dict()
    assert payload["schema"] == "locus-md.guide.v1"
    assert payload["document"]["sections"][0]["heading"] == "Install"
    assert before["state"] == after["state"]
    assert before["findings"] == after["findings"]
    schema = json.loads(files("locus_md").joinpath("schemas/guide.v1.schema.json").read_text(encoding="utf-8"))
    validate(payload, schema)


def test_guide_human_output_and_unknown_id_are_actionable(tmp_path: Path, capsys) -> None:
    path = _workspace(tmp_path)
    assert main(["--config", str(path), "guide", "readme"]) == 0
    output = capsys.readouterr().out
    assert "Document: readme" in output
    assert "Section: Install (required)" in output
    assert main(["--config", str(path), "guide", "unknown"]) == 2
    assert "available ids: agents, readme" in capsys.readouterr().err


def test_guidance_removal_does_not_change_validation_or_authored_bytes(tmp_path: Path) -> None:
    path = _workspace(tmp_path)
    config = load_config(explicit=path)
    before = Engine(config).lint()
    authored_before = {str(item): item.read_bytes() for item in tmp_path.rglob("*.md")}
    text = path.read_text(encoding="utf-8").replace('guidance = "Explain installation."\n', "")
    text = text.replace('guidance = "Show one command."\n', "")
    path.write_text(text, encoding="utf-8")
    after = Engine(load_config(explicit=path)).lint()
    authored_after = {str(item): item.read_bytes() for item in tmp_path.rglob("*.md")}
    assert after.state == before.state
    assert [item.to_dict() for item in after.sorted_findings()] == [item.to_dict() for item in before.sorted_findings()]
    assert after.patches == before.patches
    assert authored_after == authored_before
    assert after.config_digest != before.config_digest
