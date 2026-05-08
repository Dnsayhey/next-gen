"""HTTP action 内部模型"""

from dataclasses import dataclass, field
from typing import Any


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
