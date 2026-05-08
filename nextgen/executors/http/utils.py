"""HTTP action 工具函数"""

from loguru import logger

from nextgen.executors.http.model import RequestConfig


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
