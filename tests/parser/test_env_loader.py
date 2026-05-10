"""env_loader.py unit tests"""

import json

import pytest
import yaml

from nextgen.core.errors import ParseError
from nextgen.parser.env_loader import load_env_file, load_env_files


class TestLoadEnvFile:
    """Test loading a single environment file."""

    def test_load_yaml_env(self, tmp_path):
        env_file = tmp_path / "staging.yaml"
        env_file.write_text(
            yaml.dump({
                "base_url": "https://staging.example.com",
                "timeout": 5,
                "debug": False,
            }),
            encoding="utf-8",
        )

        assert load_env_file(env_file) == {
            "base_url": "https://staging.example.com",
            "timeout": 5,
            "debug": False,
        }

    def test_load_json_env(self, tmp_path):
        env_file = tmp_path / "staging.json"
        env_file.write_text(
            json.dumps({"base_url": "https://staging.example.com"}),
            encoding="utf-8",
        )

        assert load_env_file(env_file) == {"base_url": "https://staging.example.com"}

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError, match="env file does not exist"):
            load_env_file("/nonexistent/env.yaml")

    def test_unsupported_extension(self, tmp_path):
        env_file = tmp_path / "env.toml"
        env_file.write_text("base_url = 'https://example.com'", encoding="utf-8")

        with pytest.raises(ParseError, match="unsupported env file format"):
            load_env_file(env_file)

    def test_non_dict_top_level(self, tmp_path):
        env_file = tmp_path / "env.yaml"
        env_file.write_text("- one\n- two\n", encoding="utf-8")

        with pytest.raises(ParseError, match="expected dict, got list"):
            load_env_file(env_file)

    def test_non_string_key(self, tmp_path):
        env_file = tmp_path / "env.yaml"
        env_file.write_text("1: value\n", encoding="utf-8")

        with pytest.raises(ParseError, match="invalid env variable key"):
            load_env_file(env_file)


class TestLoadEnvFiles:
    """Test merging multiple environment files."""

    def test_later_files_override_earlier_files(self, tmp_path):
        base = tmp_path / "base.yaml"
        staging = tmp_path / "staging.yaml"
        base.write_text(
            yaml.dump({"base_url": "https://default.example.com", "timeout": 3}),
            encoding="utf-8",
        )
        staging.write_text(
            yaml.dump({"base_url": "https://staging.example.com"}),
            encoding="utf-8",
        )

        assert load_env_files([base, staging]) == {
            "base_url": "https://staging.example.com",
            "timeout": 3,
        }
