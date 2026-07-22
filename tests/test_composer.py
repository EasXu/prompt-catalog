"""
组合逻辑测试

确保组合引擎的模板、排除规则、抽取行为符合预期。
"""

import pytest
from prompt_catalog._composer import (
    _compose_from_template,
    _check_exclusions,
    TEMPLATES,
)
from prompt_catalog._data import PROMPTS


class TestTemplates:
    """模板配置测试。"""

    def test_all_templates_have_required_fields(self):
        """每个模板必须有 name 和 scattered 字段。"""
        for t in TEMPLATES:
            assert "name" in t, "模板缺少 name"
            assert "scattered" in t, "模板缺少 scattered"
            assert len(t["scattered"]) > 0, f"模板 '{t['name']}' scattered 为空"

    def test_template_categories_exist(self):
        """模板中引用的所有类目必须在 PROMPTS 中存在。"""
        for t in TEMPLATES:
            for cat in t.get("structural", []):
                assert cat in PROMPTS, f"模板 '{t['name']}' 引用了不存在的大类: {cat}"
            for cat in t.get("functional", []):
                assert cat in PROMPTS, f"模板 '{t['name']}' 引用了不存在的大类: {cat}"
            for cat in t.get("scattered", []):
                assert cat in PROMPTS, f"模板 '{t['name']}' 引用了不存在的大类: {cat}"


class TestExclusions:
    """排除规则测试。"""

    def test_hard_exclusion_returns_false(self):
        """洒水器 + 晾晒应触发硬互斥"""
        result = _check_exclusions(
            {"sprinklers", "drying"},
            set(),
        )
        assert result is False

    def test_valid_combination_returns_true(self):
        """正常组合应通过"""
        result = _check_exclusions(
            {"toys", "pets", "clutter"},
            set(),
        )
        assert result is True

    def test_tag_conflict_returns_false(self):
        """tag 冲突应被检测到"""
        result = _check_exclusions(
            set(),
            {"圣诞", "夏季"},
        )
        assert result is False

    def test_single_category_no_conflict(self):
        """单个类目不应触发互斥"""
        result = _check_exclusions(
            {"sprinklers"},
            set(),
        )
        assert result is True


class TestComposeFromTemplate:
    """模板组合逻辑测试。"""

    def test_compose_returns_valid_result(self):
        """正常模板应返回有效结果。"""
        result = _compose_from_template(TEMPLATES[0])
        assert result["valid"] is True
        assert "picks" in result
        assert len(result["picks"]) > 0

    def test_compose_picks_structure(self):
        """picks 的 value 应为 item ID 列表。"""
        result = _compose_from_template(TEMPLATES[1])
        for cat_key, item_ids in result["picks"].items():
            assert isinstance(item_ids, list)
            assert len(item_ids) > 0
            for iid in item_ids:
                assert iid in PROMPTS[cat_key]["items"], (
                    f"{iid} 不在 {cat_key} 的 items 中"
                )

    def test_compose_structural_limit(self):
        """结构层应最多 1 个类目。"""
        for _ in range(20):
            result = _compose_from_template(TEMPLATES[0])
            struct_count = sum(
                1 for cat in result["picks"]
                if PROMPTS[cat]["meta"].get("structural", False)
            )
            assert struct_count <= 1, (
                f"结构层类目数量 {struct_count} > 1"
            )

    def test_all_templates_produce_valid_results(self):
        """所有模板在多次尝试中都应产生有效结果。"""
        for template in TEMPLATES:
            for _ in range(10):
                result = _compose_from_template(template)
                # 不要求每次都 valid（可能因排除规则失败），
                # 但 picks 至少不能为空
                if result["valid"]:
                    assert len(result["picks"]) > 0
                    break
            else:
                # 10 次都没有 valid 结果——模板可能有问题
                pytest.fail(
                    f"模板 '{template['name']}' 在 10 次尝试中未产生有效结果"
                )
