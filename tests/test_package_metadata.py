from __future__ import annotations

import tomllib
from pathlib import Path


def test_package_exposes_only_locus_md_command() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    scripts = metadata["project"]["scripts"]
    assert scripts == {"locus-md": "locus_md.cli:main"}
