"""filtering.py unit tests"""

import pytest

from nextgen.core.errors import ParseError
from nextgen.core.filtering import filter_testcase_by_tags
from nextgen.core.model import (
    ActionNode,
    HookAction,
    StepNode,
    TestCase as CaseModel,
    TestCaseHooks as CaseHooks,
)


def make_step(
    name: str,
    tags: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> StepNode:
    return StepNode(
        name=name,
        action=ActionNode(type="request", config={"method": "GET", "url": "https://example.com"}),
        tags=tags or [],
        depends_on=depends_on or [],
    )


def make_case() -> CaseModel:
    return CaseModel(
        version=1,
        vars={"base_url": "https://example.com"},
        mode="parallel",
        fail_fast=False,
        hooks=CaseHooks(before_all=[HookAction(type="log", params="start")]),
        source_path="/tmp/case.yaml",
        base_dir="/tmp",
        steps={
            "login": make_step("login", ["auth"]),
            "profile": make_step("profile", ["smoke"], ["login"]),
            "audit": make_step("audit", ["slow"], ["profile"]),
        },
    )


def test_filter_include_tag_adds_dependencies():
    filtered = filter_testcase_by_tags(make_case(), {"smoke"}, set())

    assert list(filtered.steps) == ["login", "profile"]


def test_filter_skip_tag_removes_steps():
    filtered = filter_testcase_by_tags(make_case(), set(), {"slow"})

    assert list(filtered.steps) == ["login", "profile"]


def test_filter_include_and_skip_same_target_silently_excludes_it_when_other_targets_remain():
    filtered = filter_testcase_by_tags(make_case(), {"smoke", "slow"}, {"slow"})

    assert list(filtered.steps) == ["login", "profile"]


def test_filter_reports_conflict_when_dependency_is_skipped():
    with pytest.raises(ParseError, match="requires skipped dependency 'login'"):
        filter_testcase_by_tags(make_case(), {"smoke"}, {"auth"})


def test_filter_skip_only_reports_conflict_when_dependency_is_skipped():
    testcase = CaseModel(
        version=1,
        steps={
            "setup": make_step("setup", ["slow"]),
            "run": make_step("run", depends_on=["setup"]),
        },
    )

    with pytest.raises(ParseError, match="requires skipped dependency 'setup'"):
        filter_testcase_by_tags(testcase, set(), {"slow"})


def test_filter_reports_empty_selection():
    with pytest.raises(ParseError, match="selected no steps"):
        filter_testcase_by_tags(make_case(), {"missing"}, set())


def test_filter_preserves_testcase_metadata_and_hooks():
    testcase = make_case()

    filtered = filter_testcase_by_tags(testcase, {"smoke"}, set())

    assert filtered.vars == testcase.vars
    assert filtered.mode == testcase.mode
    assert filtered.fail_fast == testcase.fail_fast
    assert filtered.hooks == testcase.hooks
    assert filtered.source_path == testcase.source_path
    assert filtered.base_dir == testcase.base_dir
