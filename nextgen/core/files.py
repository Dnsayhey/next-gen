"""测试用例文件工具"""

from pathlib import Path


def resolve_case_path(path_str: str, base_dir: str | Path | None = None) -> Path:
    """解析 testcase 相对路径"""
    path = Path(path_str)
    if path.is_absolute() or base_dir is None:
        return path
    return Path(base_dir) / path


def load_file_content(path_str: str, base_dir: str | Path | None = None) -> bytes | str:
    """加载 @ 前缀的文件内容"""
    if not path_str.startswith("@"):
        return path_str

    file_path = resolve_case_path(path_str[1:], base_dir)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    text_exts = {".txt", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".md"}
    if file_path.suffix.lower() in text_exts:
        return file_path.read_text(encoding="utf-8")
    return file_path.read_bytes()
