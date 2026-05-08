"""extract.py 单元测试"""

from nextgen.core.extract import extract_value, jsonpath_value, parse_extract_rule


class TestExtractRule:
    """测试通用提取规则"""

    def test_parse_string_rule_as_jsonpath(self):
        rule = parse_extract_rule("$.data.token")

        assert rule.method == "jsonpath"
        assert rule.expr == "$.data.token"


class TestExtractValue:
    """测试通用提取逻辑"""

    def test_jsonpath_single_match_returns_value(self):
        value = extract_value({"users": [{"name": "Alice"}]}, "$.users[0].name")

        assert value == "Alice"

    def test_jsonpath_multiple_matches_returns_all_values(self):
        value = extract_value(
            {"users": [{"name": "Alice"}, {"name": "Bob"}]},
            "$.users[*].name",
        )

        assert value == ["Alice", "Bob"]

    def test_jsonpath_missing_match_returns_none(self):
        value = extract_value({"users": []}, "$.users[0].name")

        assert value is None


class TestJsonpathValue:
    """测试公共 JSONPath 提取 helper"""

    def test_single_match_returns_value(self):
        assert jsonpath_value({"users": [{"name": "Alice"}]}, "$.users[0].name") == "Alice"

    def test_multiple_matches_return_values(self):
        assert jsonpath_value(
            {"users": [{"name": "Alice"}, {"name": "Bob"}]},
            "$.users[*].name",
        ) == ["Alice", "Bob"]

    def test_missing_match_returns_none(self):
        assert jsonpath_value({"users": []}, "$.users[0].name") is None
