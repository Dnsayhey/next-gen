"""DB action 内部模型"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DbConfig:
    """DB action 配置"""

    url: str
    query: str
    params: list[Any] = field(default_factory=list)
