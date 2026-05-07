"""loader.py 单元测试"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml

from nextgen.bootstrap import load_builtin_actions
from nextgen.core.model import StepNode, TestCase as CaseModel
from nextgen.executors.http.config import validate_request_config
from nextgen.parser.loader import (
    find_action_type,
    load_file,
    load_testcase,
    parse_hook_action,
    parse_assertions,
    parse_step,
    parse_testcase,
)


@pytest.fixture(autouse=True)
def builtin_actions():
    load_builtin_actions()


class TestLoadFile:
    """测试 load_file"""

    def test_load_yaml(self, tmp_path):
        data = {"version": 1, "steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}}}
        file = tmp_path / "test.yaml"
        file.write_text(yaml.dump(data))
        result = load_file(file)
        assert result["version"] == 1

    def test_load_json(self, tmp_path):
        data = {"version": 1, "steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}}}
        file = tmp_path / "test.json"
        file.write_text(json.dumps(data))
        result = load_file(file)
        assert result["version"] == 1

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_file("/nonexistent/file.yaml")

    def test_unsupported_extension(self, tmp_path):
        file = tmp_path / "test.txt"
        file.write_text("content")
        with pytest.raises(ValueError, match="不支持的文件格式"):
            load_file(file)


class TestFindActionType:
    """测试 find_action_type"""

    def test_find_request(self):
        data = {"request": {"method": "GET", "url": "http://test.com"}}
        assert find_action_type(data) == "request"

    def test_no_action(self):
        data = {"depends_on": ["a"]}
        assert find_action_type(data) is None


class TestParseRequest:
    """测试 parse_request"""

    def test_valid_request(self):
        config = {"method": "GET", "url": "http://test.com"}
        validate_request_config(config)  # 不应抛出异常

    def test_missing_method(self):
        config = {"url": "http://test.com"}
        with pytest.raises(ValueError, match="method"):
            validate_request_config(config)

    def test_missing_url(self):
        config = {"method": "GET"}
        with pytest.raises(ValueError, match="url"):
            validate_request_config(config)

    def test_mutual_exclusion(self):
        config = {
            "method": "POST",
            "url": "http://test.com",
            "json": {"key": "value"},
            "form": {"key": "value"},
        }
        with pytest.raises(ValueError, match="不能同时出现"):
            validate_request_config(config)


class TestParseAssertions:
    """测试 parse_assertions"""

    def test_valid_assertions(self):
        data = [
            {"eq": ["$.code", 0]},
            {"contains": ["$.message", "success"]},
        ]
        assertions = parse_assertions(data)
        assert len(assertions) == 2
        assert assertions[0].op == "eq"
        assert assertions[0].left == "$.code"
        assert assertions[0].right == 0

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="断言格式错误"):
            parse_assertions([{"eq": 1, "ne": 2}])

    def test_invalid_args(self):
        with pytest.raises(ValueError, match="两个参数"):
            parse_assertions([{"eq": [1]}])


class TestParseHookAction:
    """测试 parse_hook_action"""

    def test_parse_sleep_shorthand(self):
        action = parse_hook_action({"sleep": 2})
        assert action.type == "sleep"
        assert action.params == {"seconds": 2}

    def test_parse_log_shorthand(self):
        action = parse_hook_action({"log": "hello"})
        assert action.params == {"message": "hello"}

    def test_parse_var_shorthand(self):
        action = parse_hook_action({"getTimestamp": "start"})
        assert action.params == {"var": "start"}

    def test_parse_full_dict(self):
        action = parse_hook_action({"getRandomStr": {"var": "rid", "length": 12}})
        assert action.params == {"var": "rid", "length": 12}

    def test_invalid_hook_format(self):
        with pytest.raises(ValueError, match="hook 格式错误"):
            parse_hook_action({"a": 1, "b": 2})


class TestParseStep:
    """测试 parse_step"""

    def test_valid_step(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
            "extract": {"token": "$.data.token"},
            "validate": [{"eq": ["$.code", 0]}],
        }
        step = parse_step("test", data)
        assert step.name == "test"
        assert step.action_type == "request"
        assert step.extract == {"token": "$.data.token"}
        assert len(step.validate) == 1

    def test_missing_action(self):
        with pytest.raises(ValueError, match="缺少 action 字段"):
            parse_step("test", {"depends_on": ["a"]})

    def test_step_with_when_list(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
            "when": [{"eq": ["${env}", "staging"]}],
        }
        step = parse_step("test", data)
        assert step.when == [{"eq": ["${env}", "staging"]}]

    def test_step_with_when_and(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
            "when": {
                "and": [
                    {"eq": ["${role}", "admin"]},
                    {"gt": ["${level}", 5]},
                ]
            },
        }
        step = parse_step("test", data)
        assert step.when == {
            "and": [
                {"eq": ["${role}", "admin"]},
                {"gt": ["${level}", 5]},
            ]
        }

    def test_step_with_when_or(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
            "when": {
                "or": [
                    {"eq": ["${env}", "staging"]},
                    {"eq": ["${env}", "dev"]},
                ]
            },
        }
        step = parse_step("test", data)
        assert step.when == {
            "or": [
                {"eq": ["${env}", "staging"]},
                {"eq": ["${env}", "dev"]},
            ]
        }

    def test_step_without_when(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
        }
        step = parse_step("test", data)
        assert step.when is None

    def test_step_with_invalid_when_dict(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
            "when": {"invalid": []},
        }
        with pytest.raises(ValueError, match="when 格式错误"):
            parse_step("test", data)

    def test_step_with_set_vars(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
            "set_vars": {
                "user1": "${user}_1",
                "prefix": "test",
            },
        }
        step = parse_step("test", data)
        assert step.set_vars == {"user1": "${user}_1", "prefix": "test"}

    def test_step_without_set_vars(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
        }
        step = parse_step("test", data)
        assert step.set_vars == {}

    def test_step_with_hooks(self):
        data = {
            "request": {"method": "GET", "url": "http://test.com"},
            "hooks": {
                "before": [{"log": "before"}],
                "after": [{"log": {"message": "after", "level": "warning"}}],
            },
        }
        step = parse_step("test", data)
        assert [action.type for action in step.hooks.before] == ["log"]
        assert step.hooks.before[0].params == {"message": "before"}
        assert step.hooks.after[0].params == {"message": "after", "level": "warning"}


class TestParseTestcase:
    """测试 parse_testcase"""

    def test_valid_testcase(self):
        data = {
            "version": 1,
            "vars": {"base_url": "http://test.com"},
            "steps": {
                "test": {
                    "request": {"method": "GET", "url": "${base_url}/api"},
                },
            },
        }
        testcase = parse_testcase(data)
        assert testcase.version == 1
        assert len(testcase.steps) == 1
        assert testcase.vars["base_url"] == "http://test.com"

    def test_missing_version(self):
        data = {"steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}}}
        with pytest.raises(ValueError, match="version"):
            parse_testcase(data)

    def test_missing_steps(self):
        data = {"version": 1}
        with pytest.raises(ValueError, match="steps"):
            parse_testcase(data)

    def test_default_mode(self):
        data = {
            "version": 1,
            "steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}},
        }
        testcase = parse_testcase(data)
        assert testcase.mode == "sequential"

    def test_sequential_mode(self):
        data = {
            "version": 1,
            "mode": "sequential",
            "steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}},
        }
        testcase = parse_testcase(data)
        assert testcase.mode == "sequential"

    def test_parallel_mode(self):
        data = {
            "version": 1,
            "mode": "parallel",
            "steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}},
        }
        testcase = parse_testcase(data)
        assert testcase.mode == "parallel"

    def test_testcase_with_hooks(self):
        data = {
            "version": 1,
            "hooks": {
                "before_all": [{"log": "suite start"}],
                "after_each": [{"sleep": 1}],
            },
            "steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}},
        }
        testcase = parse_testcase(data)
        assert testcase.hooks.before_all[0].type == "log"
        assert testcase.hooks.before_all[0].params == {"message": "suite start"}
        assert testcase.hooks.after_each[0].params == {"seconds": 1}

    def test_invalid_mode(self):
        data = {
            "version": 1,
            "mode": "invalid",
            "steps": {"test": {"request": {"method": "GET", "url": "http://test.com"}}},
        }
        with pytest.raises(ValueError, match="不支持的执行模式"):
            parse_testcase(data)


class TestLoadTestcase:
    """测试 load_testcase"""

    def test_load_yaml(self, tmp_path):
        data = {
            "version": 1,
            "steps": {
                "test": {
                    "request": {"method": "GET", "url": "http://test.com"},
                },
            },
        }
        file = tmp_path / "test.yaml"
        file.write_text(yaml.dump(data))
        testcase = load_testcase(file)
        assert isinstance(testcase, CaseModel)
        assert len(testcase.steps) == 1
        assert testcase.source_path == str(file.resolve())
        assert testcase.base_dir == str(tmp_path.resolve())
