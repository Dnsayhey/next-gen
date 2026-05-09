"""Testcase file utilities."""

from pathlib import Path


def resolve_case_path(path_str: str, base_dir: str | Path | None = None) -> Path:
    """Resolve a path relative to the testcase file."""
    path = Path(path_str)
    if path.is_absolute() or base_dir is None:
        return path
    return Path(base_dir) / path


def load_file_content(path_str: str, base_dir: str | Path | None = None) -> bytes | str:
    """Load file content referenced by an @-prefixed value."""
    if not path_str.startswith("@"):
        return path_str

    file_path = resolve_case_path(path_str[1:], base_dir)
    if not file_path.exists():
        raise FileNotFoundError(f"file does not exist: {file_path}")

    text_exts = {".txt", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".md"}
    if file_path.suffix.lower() in text_exts:
        return file_path.read_text(encoding="utf-8")
    return file_path.read_bytes()
