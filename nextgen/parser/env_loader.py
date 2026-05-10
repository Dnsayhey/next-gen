"""Environment variable file loader."""

import json
from pathlib import Path
from typing import Any

import yaml

from nextgen.core.errors import ParseError

SUPPORTED_ENV_EXTENSIONS = {".yaml", ".yml", ".json"}


def load_env_file(path: str | Path) -> dict[str, Any]:
    """Load variables from a YAML or JSON environment file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"env file does not exist: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_ENV_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_ENV_EXTENSIONS))
        raise ParseError(f"unsupported env file format: {ext}; supported: {supported}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            if ext == ".json":
                data = json.load(f)
            else:
                data = yaml.safe_load(f)
        except (json.JSONDecodeError, yaml.YAMLError) as exc:
            raise ParseError(f"invalid env file format: {exc}") from exc

    if not isinstance(data, dict):
        raise ParseError(f"invalid env file format: expected dict, got {type(data).__name__}")

    for key in data:
        if not isinstance(key, str):
            raise ParseError(f"invalid env variable key: expected str, got {type(key).__name__}")

    return data


def load_env_files(paths: list[str | Path]) -> dict[str, Any]:
    """Load and shallow-merge environment files in order."""
    env: dict[str, Any] = {}
    for path in paths:
        env.update(load_env_file(path))
    return env
