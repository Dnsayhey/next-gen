"""Documentation and checked-in example consistency tests."""

import re
from pathlib import Path

import pytest

from nextgen.bootstrap import load_builtin_actions
from nextgen.parser.loader import (
    FileKind,
    classify_loaded_file_optional,
    load_file,
    load_suite,
    load_testcase,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = [
    PROJECT_ROOT / "README.md",
    *sorted((PROJECT_ROOT / "docs").glob("*.md")),
    *sorted((PROJECT_ROOT / "examples").glob("*/README.md")),
]
EXAMPLE_FILES = sorted(
    path
    for path in (PROJECT_ROOT / "examples").rglob("*")
    if path.suffix.lower() in {".yaml", ".yml", ".json"}
)
MARKDOWN_LINK = re.compile(r"\[[^]]+\]\(([^)]+)\)")
MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def markdown_anchors(document: Path) -> set[str]:
    """Return the GitHub-style anchors used by this repository's headings."""
    anchors = set()
    for heading in MARKDOWN_HEADING.findall(document.read_text(encoding="utf-8")):
        anchor = re.sub(r"[^\w\s-]", "", heading.lower())
        anchor = re.sub(r"[\s-]+", "-", anchor).strip("-")
        anchors.add(anchor)
    return anchors


@pytest.mark.parametrize("document", MARKDOWN_FILES, ids=lambda path: str(path.relative_to(PROJECT_ROOT)))
def test_relative_documentation_links_resolve(document: Path):
    content = document.read_text(encoding="utf-8")

    for target in MARKDOWN_LINK.findall(content):
        if target.startswith(("#", "http://", "https://", "mailto:")):
            continue

        relative_path, _, anchor = target.partition("#")
        resolved = (document.parent / relative_path).resolve()
        assert resolved.exists(), f"broken link in {document}: {target}"
        if anchor and resolved.suffix.lower() == ".md":
            assert anchor in markdown_anchors(resolved), (
                f"broken anchor in {document}: {target}"
            )


@pytest.mark.parametrize("example", EXAMPLE_FILES, ids=lambda path: str(path.relative_to(PROJECT_ROOT)))
def test_runnable_examples_parse(example: Path):
    load_builtin_actions()
    kind = classify_loaded_file_optional(load_file(example))

    if kind == FileKind.TESTCASE:
        load_testcase(example)
    elif kind == FileKind.SUITE:
        load_suite(example)
