"""Hook 注册与发现"""

from __future__ import annotations

import importlib.util
import hashlib
from pathlib import Path
from typing import Awaitable, Callable

from loguru import logger

from nextgen.core.context import Context

HookHandler = Callable[[Context, dict], Awaitable[None]]

HOOK_REGISTRY: dict[str, HookHandler] = {}
_LOG_LEVELS = {"trace", "debug", "info", "success", "warning", "error", "critical"}


def register_hook(name: str):
    """注册 hook 处理函数"""

    def decorator(func: HookHandler) -> HookHandler:
        HOOK_REGISTRY[name] = func
        return func

    return decorator


def get_hook(name: str) -> HookHandler | None:
    """获取已注册的 hook"""
    return HOOK_REGISTRY.get(name)


async def _hook_sleep(ctx: Context, params: dict) -> None:
    import asyncio

    seconds = params.get("seconds", 0)
    await asyncio.sleep(seconds)


@register_hook("log")
async def _hook_log(ctx: Context, params: dict) -> None:
    level = str(params.get("level", "info")).lower()
    message = ctx.render(params.get("message", ""))
    if level not in _LOG_LEVELS:
        raise ValueError(f"不支持的日志级别: {level}")
    log_fn = getattr(logger, level)
    log_fn(message)


@register_hook("sleep")
async def _hook_sleep_registered(ctx: Context, params: dict) -> None:
    await _hook_sleep(ctx, params)


@register_hook("getTimestamp")
async def _hook_get_timestamp(ctx: Context, params: dict) -> None:
    import time

    ctx.set(_required_var(params), int(time.time() * 1000))


@register_hook("getTimeStr")
async def _hook_get_time_str(ctx: Context, params: dict) -> None:
    from datetime import datetime

    fmt = params.get("format", "%Y-%m-%d %H:%M:%S")
    ctx.set(_required_var(params), datetime.now().strftime(fmt))


@register_hook("getRandomStr")
async def _hook_get_random_str(ctx: Context, params: dict) -> None:
    import secrets
    import string

    length = int(params.get("length", 8))
    alphabet = string.ascii_letters + string.digits
    value = "".join(secrets.choice(alphabet) for _ in range(length))
    ctx.set(_required_var(params), value)


def _required_var(params: dict) -> str:
    var_name = params.get("var")
    if not var_name:
        raise ValueError("hook 参数必须包含 var")
    return str(var_name)


def discover_hooks(testcase_path: str | Path, cwd: str | Path) -> list[Path]:
    """从用例目录向上扫描 hooks.py，到 cwd 为止"""
    current = Path(testcase_path).resolve().parent
    root = Path(cwd).resolve()
    hook_files: list[Path] = []

    if root not in [current, *current.parents]:
        return []

    while True:
        hook_file = current / "hooks.py"
        if hook_file.exists():
            hook_files.append(hook_file)
        if current == root:
            break
        current = current.parent

    return list(reversed(hook_files))


def _load_hooks_module(path: Path) -> None:
    """动态加载单个 hooks.py"""
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    module_name = f"nextgen_user_hooks_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 hooks 模块: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    logger.debug(f"加载 hooks.py: {path}")


def load_discovered_hooks(testcase_path: str | Path, cwd: str | Path) -> list[Path]:
    """发现并加载 hooks.py"""
    loaded = discover_hooks(testcase_path, cwd)
    for hook_file in loaded:
        _load_hooks_module(hook_file)
    return loaded
