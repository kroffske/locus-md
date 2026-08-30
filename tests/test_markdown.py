from __future__ import annotations

from locus_md.markdown import scan_managed_blocks


def test_marker_in_fenced_code_is_ignored() -> None:
    text = """# Example

```md
<!-- locus:milestone fake begin -->
ignored
<!-- locus:milestone fake end -->
```

<!-- locus:milestone tasks begin -->
body
<!-- locus:milestone tasks end -->
"""
    blocks, findings = scan_managed_blocks(text, display_path="docs/a.md", surface_name="docs")
    assert findings == []
    assert [(block.kind, block.block_id) for block in blocks] == [("milestone", "tasks")]
    assert text[blocks[0].body_start : blocks[0].body_end] == "body\n"


def test_unclosed_nested_and_duplicate_markers_are_reported() -> None:
    nested = """<!-- locus:a one begin -->\n<!-- locus:b two begin -->\n<!-- locus:a one end -->\n"""
    _, findings = scan_managed_blocks(nested, display_path="docs/a.md", surface_name="docs")
    assert "DOC-BLOCK-002" in {finding.code for finding in findings}
    duplicate = """<!-- locus:a one begin -->\nx\n<!-- locus:a one end -->\n<!-- locus:a one begin -->\ny\n<!-- locus:a one end -->\n"""
    _, findings = scan_managed_blocks(duplicate, display_path="docs/a.md", surface_name="docs")
    assert "DOC-BLOCK-003" in {finding.code for finding in findings}
    _, findings = scan_managed_blocks("<!-- locus:a one begin -->\n", display_path="docs/a.md", surface_name="docs")
    assert "DOC-BLOCK-001" in {finding.code for finding in findings}


def test_malformed_locus_marker_is_reported() -> None:
    _, findings = scan_managed_blocks("<!-- locus:Bad missing -->\n", display_path="docs/a.md", surface_name="docs")
    assert [finding.code for finding in findings] == ["DOC-BLOCK-006"]


def test_colon_namespaced_registry_markers_are_foreign_and_ignored() -> None:
    text = "<!-- locus:nav:v1:begin -->\ncontent\n<!-- locus:nav:v1:end -->\n"
    blocks, findings = scan_managed_blocks(text, display_path="AGENTS.md", surface_name="root")
    assert blocks == ()
    assert findings == []


def test_whitespace_locus_marker_remains_malformed() -> None:
    _, findings = scan_managed_blocks("<!-- locus:nav malformed -->\n", display_path="AGENTS.md", surface_name="root")
    assert [finding.code for finding in findings] == ["DOC-BLOCK-006"]
