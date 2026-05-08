"""HTTP action 内部模型"""

from dataclasses import dataclass, field
from typing import Any

from nextgen.core.errors import ParseError


@dataclass
class RequestConfig:
    """HTTP request action 配置"""

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    # 请求体（互斥，同时出现会报错）
    json: dict[str, Any] | None = None
    form: dict[str, str] | None = None
    multipart: dict[str, str] | None = None
    body: str | None = None
    content_type: str | None = None
    timeout: float | None = None  # 请求超时（秒）

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "RequestConfig":
        """解析 request 配置"""
        if "method" not in config:
            raise ParseError("request 必须包含 method 字段")
        if "url" not in config:
            raise ParseError("request 必须包含 url 字段")

        body_fields = [
            f for f in ["json", "form", "multipart", "body"]
            if config.get(f) is not None
        ]
        if len(body_fields) > 1:
            raise ParseError("json/form/multipart/body 不能同时出现，只能选择一种")

        return cls(
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

    def body_type(self) -> str | None:
        """获取请求体类型"""
        if self.json is not None:
            return "json"
        if self.form is not None:
            return "form"
        if self.multipart is not None:
            return "multipart"
        if self.body is not None:
            return "raw"
        return None

    def summary(self) -> str:
        """生成 request action 摘要"""
        return f"{self.method} {self.url}"
