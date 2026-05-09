"""Hook registration, argument binding, and discovery."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from nextgen.core.context import Context

HookFunc = Callable[..., Any]
_CONTEXT_PARAM_NAMES = {"ctx", "context"}
_LOG_LEVELS = {"trace", "debug", "info", "success", "warning", "error", "critical"}


@dataclass(frozen=True)
class HookSpec:
    """Runtime description for a registered hook."""

    name: str
    func: HookFunc
    signature: inspect.Signature


HOOK_REGISTRY: dict[str, HookSpec] = {}


def hook(name_or_func: str | HookFunc | None = None, *, override: bool = False):
    """Register a hook.

    Supported forms:

    @hook
    def my_hook(...): ...

    @hook("custom_name")
    def my_hook(...): ...
    """

    if callable(name_or_func):
        return _register_hook(name_or_func.__name__, name_or_func, override=override)

    def decorator(func: HookFunc) -> HookFunc:
        hook_name = name_or_func or func.__name__
        return _register_hook(str(hook_name), func, override=override)

    return decorator


def _register_hook(name: str, func: HookFunc, *, override: bool = False) -> HookFunc:
    if name in HOOK_REGISTRY and not override:
        raise ValueError(f"hook already registered: {name}; use override=True to replace it")
    HOOK_REGISTRY[name] = HookSpec(
        name=name,
        func=func,
        signature=inspect.signature(func),
    )
    return func


def _builtin_hook(name_or_func: str | HookFunc | None = None):
    """Register a built-in hook and allow replacement on module reload."""
    if callable(name_or_func):
        return _register_hook(name_or_func.__name__, name_or_func, override=True)

    def decorator(func: HookFunc) -> HookFunc:
        hook_name = str(name_or_func or func.__name__)
        return _register_hook(hook_name, func, override=True)

    return decorator


def get_hook(name: str) -> HookSpec | None:
    """Get a registered hook."""
    return HOOK_REGISTRY.get(name)


def bind_hook_arguments(spec: HookSpec, ctx: Context, raw_params: object) -> dict[str, Any]:
    """Bind YAML parameters according to the hook function signature."""
    params = raw_params if isinstance(raw_params, dict) else _scalar_to_params(spec, raw_params)
    if not isinstance(params, dict):
        raise ValueError(f"hook '{spec.name}' params must be a dict or scalar, got {type(raw_params).__name__}")

    params = dict(params)
    kwargs: dict[str, Any] = {}
    accepts_var_kwargs = False
    keyword_params: set[str] = set()

    for param in spec.signature.parameters.values():
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            accepts_var_kwargs = True
            continue
        if param.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            continue
        if param.name in _CONTEXT_PARAM_NAMES:
            kwargs[param.name] = ctx
        else:
            keyword_params.add(param.name)

    unknown = set(params) - keyword_params
    if unknown and not accepts_var_kwargs:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"hook '{spec.name}' received unknown params: {names}")

    for name in sorted(set(params) & keyword_params):
        kwargs[name] = params.pop(name)

    if accepts_var_kwargs:
        kwargs.update(params)

    missing: list[str] = []
    for param in spec.signature.parameters.values():
        if param.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            continue
        if param.name in kwargs:
            continue
        if param.default is inspect.Parameter.empty:
            missing.append(param.name)

    if missing:
        names = ", ".join(missing)
        raise ValueError(f"hook '{spec.name}' missing required params: {names}")

    return kwargs


def _scalar_to_params(spec: HookSpec, raw_params: object) -> dict[str, Any]:
    bindable = [
        param
        for param in spec.signature.parameters.values()
        if param.kind
        in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        )
        and param.name not in _CONTEXT_PARAM_NAMES
    ]
    required = [
        param
        for param in bindable
        if param.default is inspect.Parameter.empty
    ]

    if len(required) == 1:
        return {required[0].name: raw_params}
    if not required and bindable:
        return {bindable[0].name: raw_params}

    raise ValueError(f"hook '{spec.name}' does not support scalar params; use dict params")


async def call_hook(spec: HookSpec, ctx: Context, raw_params: object) -> None:
    """Bind and execute a hook; warn when a non-None return value is ignored."""
    kwargs = bind_hook_arguments(spec, ctx, raw_params)
    result = spec.func(**kwargs)
    if inspect.isawaitable(result):
        result = await result
    if result is not None:
        logger.warning(
            f"hook '{spec.name}' returned a value and it was ignored; "
            "use ctx.set(...) to write variables"
        )


@_builtin_hook
def log(ctx: Context, message: object = "", level: str = "info") -> None:
    level_name = str(level).lower()
    if level_name not in _LOG_LEVELS:
        raise ValueError(f"unsupported log level: {level}")
    getattr(logger, level_name)(ctx.render_value(message))


@_builtin_hook
async def sleep(seconds: float = 0) -> None:
    import asyncio

    await asyncio.sleep(float(seconds))


@_builtin_hook
def get_timestamp(ctx: Context, var: str) -> None:
    import time

    ctx.set(str(var), int(time.time() * 1000))


@_builtin_hook
def get_time_str(ctx: Context, var: str, format: str = "%Y-%m-%d %H:%M:%S") -> None:
    from datetime import datetime

    ctx.set(str(var), datetime.now().strftime(str(format)))


@_builtin_hook
def get_random_str(ctx: Context, var: str, length: int = 8) -> None:
    import secrets
    import string

    alphabet = string.ascii_letters + string.digits
    value = "".join(secrets.choice(alphabet) for _ in range(int(length)))
    ctx.set(str(var), value)


@_builtin_hook
def set_vars(ctx: Context, **vars: object) -> None:
    for key, value in vars.items():
        ctx.set(str(key), ctx.render_value(value))


def discover_hooks(testcase_path: str | Path, cwd: str | Path) -> list[Path]:
    """Scan upward from the testcase directory to cwd for hooks.py files."""
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
    """Dynamically load one hooks.py module."""
    digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:16]
    module_name = f"nextgen_user_hooks_{digest}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load hooks module: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    logger.debug(f"Loaded hooks.py: {path}")


def load_discovered_hooks(testcase_path: str | Path, cwd: str | Path) -> list[Path]:
    """Discover and load hooks.py files."""
    loaded = discover_hooks(testcase_path, cwd)
    for hook_file in loaded:
        _load_hooks_module(hook_file)
    return loaded
