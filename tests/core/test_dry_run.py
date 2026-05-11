"""dry_run.py unit tests"""

from pathlib import Path

import pytest

from nextgen.bootstrap import load_builtin_actions
from nextgen.core.dry_run import dry_run_inputs, dry_run_suite, dry_run_testcase
from nextgen.core.hooks import get_hook
from nextgen.core.model import Suite
from nextgen.core.errors import ParseError


@pytest.fixture(autouse=True)
def builtin_actions():
    load_builtin_actions()


def write_case(path: Path, extra_step_lines: list[str] | None = None) -> None:
    lines = [
        "version: 1",
        "vars:",
        "  base_url: https://default.example.com",
        "steps:",
        "  login:",
        "    tags: [auth]",
        "    request:",
        "      method: POST",
        "      url: ${base_url}/login",
        "    export:",
        "      token: ${base_url}",
    ]
    lines.extend(extra_step_lines or [])
    path.write_text("\n".join(lines), encoding="utf-8")


def test_dry_run_testcase_serializes_plan_without_rendering_values(tmp_path):
    case_file = tmp_path / "case.yaml"
    env_file = tmp_path / "env.yaml"
    env_file.write_text("base_url: https://staging.example.com\nsecret: hidden\n", encoding="utf-8")
    write_case(case_file, [
        "  profile:",
        "    depends_on: [login]",
        "    tags: [smoke]",
        "    when:",
        "      - eq: ['${env}', staging]",
        "    hooks:",
        "      before:",
        "        - log: before profile",
        "    config:",
        "      retry: 2",
        "      timeout: 5",
        "    request:",
        "      method: GET",
        "      url: ${base_url}/profile",
    ])

    plan = dry_run_testcase(case_file, [env_file])

    assert plan["testcase"] == str(case_file.resolve())
    assert plan["mode"] == "sequential"
    assert plan["fail_fast"] is True
    assert plan["env_keys"] == ["base_url", "secret"]
    assert plan["declared_export_keys"] == ["token"]
    assert plan["execution_order"] == [["login"], ["profile"]]
    assert plan["steps"][0]["summary"] == "POST ${base_url}/login"
    assert plan["steps"][0]["tags"] == ["auth"]
    assert plan["steps"][1]["has_when"] is True
    assert plan["steps"][1]["hooks"] == {"before": 1, "after": 0}
    assert plan["steps"][1]["retry"] == 2
    assert plan["steps"][1]["timeout"] == 5
    assert plan["filters"] == {"tags": [], "skip_tags": []}


def test_dry_run_matrix_uses_expanded_step_names(tmp_path):
    case_file = tmp_path / "matrix.yaml"
    case_file.write_text(
        "\n".join([
            "version: 1",
            "steps:",
            "  login:",
            "    matrix:",
            "      user: [admin, guest]",
            "    request:",
            "      method: POST",
            "      url: https://example.com/login",
        ]),
        encoding="utf-8",
    )

    plan = dry_run_testcase(case_file, [])

    assert [step["name"] for step in plan["steps"]] == [
        "login[user=admin]",
        "login[user=guest]",
    ]


def test_dry_run_discovers_hooks_without_loading_them(tmp_path):
    hooks_file = tmp_path / "hooks.py"
    hooks_file.write_text(
        "\n".join([
            "from nextgen import hook",
            "@hook",
            "def dry_run_should_not_load():",
            "    pass",
        ]),
        encoding="utf-8",
    )
    case_file = tmp_path / "case.yaml"
    write_case(case_file)

    plan = dry_run_testcase(case_file, [])

    assert plan["hook_files"] == [str(hooks_file)]
    assert get_hook("dry_run_should_not_load") is None


def test_dry_run_suite_serializes_setup_tests_and_export_keys(tmp_path):
    setup_file = tmp_path / "setup.yaml"
    test_file = tmp_path / "test.yaml"
    env_file = tmp_path / "base.yaml"
    env_file.write_text("base_url: https://suite.example.com\n", encoding="utf-8")
    write_case(setup_file)
    write_case(test_file)
    suite = Suite(
        name="smoke",
        env=[str(env_file)],
        setup=[str(setup_file)],
        tests=[str(test_file)],
    )

    plan = dry_run_suite(suite, [])

    assert plan["suite"] == "smoke"
    assert plan["env_keys"] == ["base_url"]
    assert plan["setup_export_keys"] == ["token"]
    assert plan["runtime_setup_exports"] is True
    assert plan["setup"][0]["testcase"] == str(setup_file.resolve())
    assert plan["tests"][0]["testcase"] == str(test_file.resolve())


def test_dry_run_inputs_multiple_files_returns_cli_suite_plan(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "second.yaml"
    write_case(first)
    write_case(second)

    plan = dry_run_inputs([first, second, first], [])

    assert plan["suite"] == "cli"
    assert [test["testcase"] for test in plan["tests"]] == [
        str(first.resolve()),
        str(second.resolve()),
    ]


def test_dry_run_inputs_directory_returns_cli_suite_plan(tmp_path):
    first = tmp_path / "first.yaml"
    second = tmp_path / "nested" / "second.yaml"
    second.parent.mkdir()
    write_case(first)
    write_case(second)
    (tmp_path / "env.yaml").write_text("base_url: https://ignored.example.com\n", encoding="utf-8")
    (tmp_path / "all.yaml").write_text("name: all\ntests:\n  - first.yaml\n", encoding="utf-8")

    plan = dry_run_inputs([tmp_path], [])

    assert plan["suite"] == "cli"
    assert [test["testcase"] for test in plan["tests"]] == [
        str(first.resolve()),
        str(second.resolve()),
    ]


def test_dry_run_inputs_directory_with_one_testcase_returns_cli_suite_plan(tmp_path):
    case_file = tmp_path / "case.yaml"
    write_case(case_file)

    plan = dry_run_inputs([tmp_path], [])

    assert plan["suite"] == "cli"
    assert [test["testcase"] for test in plan["tests"]] == [str(case_file.resolve())]


def test_dry_run_suite_parse_error_fails_fast(tmp_path):
    good = tmp_path / "good.yaml"
    bad = tmp_path / "bad.yaml"
    write_case(good)
    bad.write_text("version: 1\nsteps: {}\n", encoding="utf-8")
    suite = Suite(name="smoke", tests=[str(bad), str(good)])

    with pytest.raises(ParseError, match="missing steps field"):
        dry_run_suite(suite, [])


def test_dry_run_applies_tag_filters(tmp_path):
    case_file = tmp_path / "case.yaml"
    write_case(case_file, [
        "  profile:",
        "    depends_on: [login]",
        "    tags: [smoke]",
        "    request:",
        "      method: GET",
        "      url: ${base_url}/profile",
        "  audit:",
        "    tags: [slow]",
        "    request:",
        "      method: GET",
        "      url: ${base_url}/audit",
    ])

    plan = dry_run_testcase(case_file, [], include_tags={"smoke"}, skip_tags={"slow"})

    assert [step["name"] for step in plan["steps"]] == ["login", "profile"]
    assert plan["filters"] == {"tags": ["smoke"], "skip_tags": ["slow"]}
