"""condition.py 单元测试"""

import pytest

from nextgen.core.condition import evaluate_condition
from nextgen.core.context import Context


class TestEvaluateCondition:
    """测试 evaluate_condition"""

    def test_none_returns_true(self):
        ctx = Context()
        assert evaluate_condition(None, ctx) is True

    def test_empty_list_returns_true(self):
        ctx = Context()
        assert evaluate_condition([], ctx) is True

    def test_simple_eq_pass(self):
        ctx = Context({"code": 0})
        condition = [{"eq": ["${code}", 0]}]
        assert evaluate_condition(condition, ctx) is True

    def test_simple_eq_fail(self):
        ctx = Context({"code": 1})
        condition = [{"eq": ["${code}", 0]}]
        assert evaluate_condition(condition, ctx) is False

    def test_simple_ne(self):
        ctx = Context({"status": "active"})
        condition = [{"ne": ["${status}", "inactive"]}]
        assert evaluate_condition(condition, ctx) is True

    def test_simple_gt(self):
        ctx = Context({"count": 10})
        condition = [{"gt": ["${count}", 5]}]
        assert evaluate_condition(condition, ctx) is True

    def test_condition_uses_context_render_to_preserve_pure_var_type(self):
        ctx = Context({"payload": {"code": 0}, "expected": {"code": 0}})
        condition = [{"eq": ["${payload}", "${expected}"]}]
        assert evaluate_condition(condition, ctx) is True

    def test_simple_contains(self):
        ctx = Context({"message": "hello world"})
        condition = [{"contains": ["${message}", "world"]}]
        assert evaluate_condition(condition, ctx) is True

    @pytest.mark.parametrize(
        ("condition", "vars"),
        [
            ([{"not_contains": ["${message}", "error"]}], {"message": "success"}),
            ([{"starts_with": ["${name}", "user_"]}], {"name": "user_admin"}),
            ([{"ends_with": ["${file}", ".json"]}], {"file": "report.json"}),
            ([{"in": ["${status}", ["active", "pending"]]}], {"status": "active"}),
            ([{"not_in": ["${role}", ["banned"]]}], {"role": "admin"}),
            ([{"matches": ["${email}", r"^[^@]+@[^@]+$"]}], {"email": "u@example.com"}),
            ([{"len_gt": ["${items}", 1]}], {"items": [1, 2]}),
        ],
    )
    def test_extended_operators(self, condition, vars):
        ctx = Context(vars)
        assert evaluate_condition(condition, ctx) is True

    def test_len_operator_with_value_without_length_returns_false(self):
        ctx = Context({"count": 1})
        condition = [{"len_gt": ["${count}", 0]}]
        assert evaluate_condition(condition, ctx) is False

    def test_and_list_all_pass(self):
        ctx = Context({"a": 1, "b": 2})
        condition = [
            {"eq": ["${a}", 1]},
            {"eq": ["${b}", 2]},
        ]
        assert evaluate_condition(condition, ctx) is True

    def test_and_list_one_fail(self):
        ctx = Context({"a": 1, "b": 3})
        condition = [
            {"eq": ["${a}", 1]},
            {"eq": ["${b}", 2]},
        ]
        assert evaluate_condition(condition, ctx) is False

    def test_explicit_and(self):
        ctx = Context({"a": 1, "b": 2})
        condition = {
            "and": [
                {"eq": ["${a}", 1]},
                {"eq": ["${b}", 2]},
            ]
        }
        assert evaluate_condition(condition, ctx) is True

    def test_explicit_and_fail(self):
        ctx = Context({"a": 1, "b": 3})
        condition = {
            "and": [
                {"eq": ["${a}", 1]},
                {"eq": ["${b}", 2]},
            ]
        }
        assert evaluate_condition(condition, ctx) is False

    def test_explicit_or_one_pass(self):
        ctx = Context({"env": "staging"})
        condition = {
            "or": [
                {"eq": ["${env}", "staging"]},
                {"eq": ["${env}", "development"]},
            ]
        }
        assert evaluate_condition(condition, ctx) is True

    def test_explicit_or_all_fail(self):
        ctx = Context({"env": "production"})
        condition = {
            "or": [
                {"eq": ["${env}", "staging"]},
                {"eq": ["${env}", "development"]},
            ]
        }
        assert evaluate_condition(condition, ctx) is False

    def test_nested_and_or(self):
        ctx = Context({"role": "admin", "level": 10})
        condition = {
            "and": [
                {"eq": ["${role}", "admin"]},
                {
                    "or": [
                        {"gt": ["${level}", 5]},
                        {"eq": ["${role}", "superadmin"]},
                    ]
                },
            ]
        }
        assert evaluate_condition(condition, ctx) is True

    def test_invalid_dict_key(self):
        ctx = Context()
        condition = {"invalid": []}
        with pytest.raises(ValueError, match="未知的条件格式"):
            evaluate_condition(condition, ctx)

    def test_invalid_expression_format(self):
        ctx = Context()
        condition = [{"invalid": [1, 2, 3]}]  # 不是单键 dict
        with pytest.raises(ValueError, match="表达式参数错误"):
            evaluate_condition(condition, ctx)

    def test_variable_not_found(self):
        ctx = Context()
        condition = [{"eq": ["${nonexistent}", "${nonexistent}"]}]
        assert evaluate_condition(condition, ctx) is True

    def test_unknown_operator(self):
        ctx = Context()
        condition = [{"unknown": [1, 1]}]
        with pytest.raises(ValueError, match="不支持的操作符"):
            evaluate_condition(condition, ctx)
