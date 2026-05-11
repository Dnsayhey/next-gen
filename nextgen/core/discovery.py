"""CLI input discovery for files, directories, and glob patterns."""

from dataclasses import dataclass
import glob
from pathlib import Path

from loguru import logger

from nextgen.core.errors import ParseError
from nextgen.parser.loader import FileKind, SUPPORTED_EXTENSIONS, classify_loaded_file_optional, load_file


@dataclass(frozen=True)
class DiscoveredInputs:
    """Resolved CLI inputs after directory and glob expansion."""

    files: list[Path]
    used_discovery: bool = False


def resolve_cli_inputs(inputs: list[Path]) -> DiscoveredInputs:
    """Resolve explicit files plus directory/glob discovery into runnable files."""
    if not inputs:
        raise ValueError("at least one file is required")

    files: list[Path] = []
    used_discovery = False

    for raw_input in inputs:
        raw_text = str(raw_input)
        if has_glob_magic(raw_text):
            used_discovery = True
            matches = expand_glob(raw_text)
            if not matches:
                raise ParseError(f"glob pattern matched no files: {raw_text}")
            files.extend(collect_discovered_files(matches))
            continue

        path = raw_input
        if path.is_dir():
            used_discovery = True
            files.extend(collect_discovered_files([path]))
            continue

        files.append(path)

    if used_discovery and not files:
        raise ParseError("no testcase files found")

    return DiscoveredInputs(files=files, used_discovery=used_discovery)


def has_glob_magic(pattern: str) -> bool:
    """Return whether the path string contains glob metacharacters."""
    return glob.has_magic(pattern)


def expand_glob(pattern: str) -> list[Path]:
    """Expand a glob pattern in stable path order."""
    return [
        Path(match)
        for match in sorted(glob.glob(pattern, recursive=True))
    ]


def collect_discovered_files(paths: list[Path]) -> list[Path]:
    """Collect testcase files from discovered paths."""
    files: list[Path] = []
    for path in paths:
        for candidate in iter_supported_files(path):
            kind = classify_discovered_file(candidate)
            if kind == FileKind.TESTCASE:
                files.append(candidate)
    return files


def iter_supported_files(path: Path) -> list[Path]:
    """Return supported YAML/JSON files under a discovered path."""
    if path.is_dir():
        return sorted(
            file
            for file in path.rglob("*")
            if file.is_file() and file.suffix.lower() in SUPPORTED_EXTENSIONS
        )
    if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
        return [path]
    return []


def classify_discovered_file(path: Path) -> FileKind | None:
    """Classify a discovered file using directory/glob-tolerant rules."""
    kind = classify_loaded_file_optional(load_file(path))

    if kind == FileKind.SUITE:
        logger.warning(f"skipping suite file discovered by directory/glob input: {path}")
        return None
    return kind
