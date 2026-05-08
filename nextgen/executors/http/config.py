"""HTTP action 配置校验"""

from typing import Any

from nextgen.core.errors import ParseError
from nextgen.executors.http.model import RequestConfig


def parse_request_config(config: dict[str, Any]) -> RequestConfig:
    """解析 request 配置"""
    if "method" not in config:
        raise ParseError("request 必须包含 method 字段")
    if "url" not in config:
        raise ParseError("request 必须包含 url 字段")

    body_fields = [f for f in ["json", "form", "multipart", "body"] if config.get(f) is not None]
    if len(body_fields) > 1:
        raise ParseError("json/form/multipart/body 不能同时出现，只能选择一种")

    return RequestConfig(
        method=config.get("method", "").upper(),
        url=config.get("url", ""),
        headers=config.get("headers", {}),
        params=config.get("params", {}),
        json=config.get("json"),
        form=config.get("form"),
        multipart=config.get("multipart"),
        body=config.get("body"),
        content_type=config.get("content_type"),
        timeout=config.get("timeout"),
    )


def summarize_request(config: RequestConfig) -> str:
    """生成 request action 摘要"""
    return f"{config.method} {config.url}"
