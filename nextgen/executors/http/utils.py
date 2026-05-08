"""HTTP 执行器工具函数"""

from pathlib import Path

from loguru import logger

from nextgen.executors.http.model import RequestConfig


def resolve_case_path(path_str: str, base_dir: str | Path | None = None) -> Path:
    """解析 testcase 相对路径"""
    path = Path(path_str)
    if path.is_absolute() or base_dir is None:
        return path
    return Path(base_dir) / path


def load_file_content(path_str: str, base_dir: str | Path | None = None) -> bytes | str:
    """加载 @ 前缀的文件内容

    Args:
        path_str: 文件路径，以 @ 开头，如 @./photo.png

    Returns:
        bytes (二进制文件) 或 str (文本文件)
    """
    if not path_str.startswith("@"):
        return path_str

    file_path = resolve_case_path(path_str[1:], base_dir)
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 根据扩展名决定读取模式
    text_exts = {".txt", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".md"}
    if file_path.suffix.lower() in text_exts:
        return file_path.read_text(encoding="utf-8")
    else:
        return file_path.read_bytes()


def check_content_type_conflict(request: RequestConfig) -> None:
    """检查 content_type 与请求体类型是否冲突"""
    body_type = request.body_type()
    if not body_type or not request.content_type:
        return

    # 检查用户是否手动设置了 content_type
    user_content_type = request.headers.get("content-type") or request.headers.get("Content-Type")
    if user_content_type:
        logger.warning(
            f"内容类型冲突：当前请求体类型是 {body_type}，但请求头中设置了 {user_content_type}"
        )
