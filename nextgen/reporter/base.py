"""报告器接口与注册表"""

from __future__ import annotations

from typing import Protocol

from nextgen.core.result import TestResult


class Reporter(Protocol):
    """测试结果报告器接口"""

    name: str

    def render(self, result: TestResult) -> str:
        ...


REPORTER_REGISTRY: dict[str, Reporter] = {}


def register_reporter(reporter: Reporter) -> None:
    """注册报告器实现"""
    REPORTER_REGISTRY[reporter.name] = reporter


def get_reporter(name: str) -> Reporter | None:
    """获取报告器实现"""
    return REPORTER_REGISTRY.get(name)


def list_reporters() -> list[str]:
    """列出已注册报告器名称"""
    return list(REPORTER_REGISTRY)
