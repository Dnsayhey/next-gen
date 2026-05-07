"""HTTP action 配置校验"""

from typing import Any


def validate_request_config(config: dict[str, Any]) -> None:
    """验证 request 配置"""
    if "method" not in config:
        raise ValueError("request 必须包含 method 字段")
    if "url" not in config:
        raise ValueError("request 必须包含 url 字段")

    body_fields = [f for f in ["json", "form", "multipart", "body"] if config.get(f) is not None]
    if len(body_fields) > 1:
        raise ValueError("json/form/multipart/body 不能同时出现，只能选择一种")
