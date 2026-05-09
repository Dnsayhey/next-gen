"""HTTP action utilities."""

from loguru import logger

from nextgen.actions.http.model import RequestConfig


def check_content_type_conflict(request: RequestConfig) -> None:
    """Check whether content_type conflicts with body type."""
    body_type = request.body_type()
    if not body_type or not request.content_type:
        return

    # Check whether the user manually set content_type.
    user_content_type = request.headers.get("content-type") or request.headers.get("Content-Type")
    if user_content_type:
        logger.warning(
            f"content type conflict: body_type={body_type}, header content-type={user_content_type}"
        )
