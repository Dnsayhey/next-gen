"""discovery.py unit tests"""

from pathlib import Path

import pytest

from nextgen.core.discovery import resolve_cli_inputs
from nextgen.core.errors import ParseError


def write_case(path: Path) -> None:
    path.write_text(
        "\n".join([
            "version: 1",
            "steps:",
            "  one:",
            "    request:",
            "      method: GET",
            "      url: https://example.com",
        ]),
        encoding="utf-8",
    )


def test_resolve_cli_inputs_discovers_testcases_recursively_in_stable_order(tmp_path):
    nested = tmp_path / "api" / "nested"
    nested.mkdir(parents=True)
    z_case = nested / "z.yaml"
    a_case = tmp_path / "a.json"
    write_case(z_case)
    a_case.write_text(
        '{"version": 1, "steps": {"one": {"request": {"method": "GET", "url": "https://example.com"}}}}',
        encoding="utf-8",
    )

    resolved = resolve_cli_inputs([tmp_path])

    assert resolved.used_discovery is True
    assert resolved.files == [a_case, z_case]


def test_resolve_cli_inputs_ignores_discovered_non_runnable_yaml(tmp_path):
    env_dir = tmp_path / "env"
    env_dir.mkdir()
    env_file = env_dir / "base.yaml"
    env_file.write_text("base_url: https://example.com\n", encoding="utf-8")
    case_file = tmp_path / "case.yaml"
    write_case(case_file)

    resolved = resolve_cli_inputs([tmp_path])

    assert resolved.files == [case_file]


def test_resolve_cli_inputs_warns_and_skips_discovered_suite(tmp_path):
    suite_file = tmp_path / "all.yaml"
    suite_file.write_text("name: all\ntests:\n  - case.yaml\n", encoding="utf-8")
    case_file = tmp_path / "case.yaml"
    write_case(case_file)

    resolved = resolve_cli_inputs([tmp_path])

    assert resolved.files == [case_file]


def test_resolve_cli_inputs_errors_on_discovered_ambiguous_file(tmp_path):
    ambiguous = tmp_path / "bad.yaml"
    ambiguous.write_text("steps: {}\ntests: []\n", encoding="utf-8")

    with pytest.raises(ParseError, match="ambiguous file format"):
        resolve_cli_inputs([tmp_path])


def test_resolve_cli_inputs_errors_when_discovery_finds_no_testcases(tmp_path):
    suite_file = tmp_path / "all.yaml"
    suite_file.write_text("name: all\ntests:\n  - case.yaml\n", encoding="utf-8")

    with pytest.raises(ParseError, match="no testcase files found"):
        resolve_cli_inputs([tmp_path])


def test_resolve_cli_inputs_expands_globs(tmp_path):
    first = tmp_path / "one.yaml"
    second = tmp_path / "two.yml"
    write_case(first)
    write_case(second)

    resolved = resolve_cli_inputs([tmp_path / "*.y*ml"])

    assert resolved.used_discovery is True
    assert resolved.files == [first, second]


def test_resolve_cli_inputs_errors_when_glob_matches_nothing(tmp_path):
    with pytest.raises(ParseError, match="glob pattern matched no files"):
        resolve_cli_inputs([tmp_path / "*.yaml"])
