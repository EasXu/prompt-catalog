"""
API 功能测试

确保公开 API 函数行为符合预期。
"""

import pytest
from prompt_catalog import (
    augment,
    compose,
    random_scene,
    search,
    list_categories,
    list_items,
    version,
)


class TestVersion:
    """版本号测试。"""

    def test_version_is_string(self):
        assert isinstance(version(), str)

    def test_version_format(self):
        """版本号应遵循语义化版本格式。"""
        import re
        assert re.match(r"^\d+\.\d+\.\d+$", version()), (
            f"版本号 '{version()}' 不符合 semver 格式"
        )


class TestListCategories:
    """list_categories 测试。"""

    def test_returns_list_of_dicts(self):
        result = list_categories()
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "key" in item
            assert "label" in item
            assert "structural" in item
            assert "count" in item
            assert isinstance(item["count"], int)
            assert item["count"] > 0

    def test_all_keys_are_strings(self):
        for item in list_categories():
            assert isinstance(item["key"], str)


class TestListItems:
    """list_items 测试。"""

    def test_valid_category(self):
        result = list_items("toys")
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "id" in item
            assert "name" in item
            assert "tags" in item

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="未知的大类"):
            list_items("nonexistent_category_xyz")


class TestSearch:
    """search 测试。"""

    def test_search_returns_list(self):
        result = search("足球")
        assert isinstance(result, list)
        # 足球应该至少有一个匹配
        assert len(result) >= 1

    def test_search_result_structure(self):
        result = search("花盆")
        for item in result:
            assert "category" in item
            assert "id" in item
            assert "name" in item
            assert "prompt_snippet" in item

    def test_search_no_match(self):
        result = search("不存在的关键词xyz123")
        assert isinstance(result, list)
        assert len(result) == 0

    def test_search_case_insensitive(self):
        """搜索应不区分大小写（对 ASCII 部分）。"""
        # 至少保证不会因大小写而漏掉结果
        result_lower = search("toy")
        # 这里主要测试不抛异常
        assert isinstance(result_lower, list)


class TestCompose:
    """compose 测试。"""

    def test_compose_single_category(self):
        result = compose(["toys"])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_compose_multiple_categories(self):
        result = compose(["toys", "pets", "clutter"])
        assert isinstance(result, str)
        assert len(result) > 0
        # 应包含换行符（多个类目）
        assert "\n" in result

    def test_compose_invalid_category_raises(self):
        with pytest.raises(ValueError, match="未知的大类"):
            compose(["nonexistent_xyz"])

    def test_compose_all_valid_categories(self):
        """对所有已知类目调用 compose，确保不抛异常。"""
        from prompt_catalog._data import PROMPTS
        for cat_key in PROMPTS:
            result = compose([cat_key])
            assert isinstance(result, str)
            assert len(result) > 0


class TestAugment:
    """augment 测试 — jieba 分词 + 数量检测 + 随机抽取。"""

    def test_exact_name_match(self):
        """精确名称匹配：'足球'应精准命中 TY01。"""
        result = augment("草坪上有个足球")
        assert "足球" in result
        assert result.count("\n") == 1  # 仅 1 条匹配

    def test_quantity_parsing(self):
        """数量检测：'三个球'应返回 3 条球类提示词。"""
        result = augment("三个球")
        assert result.count("\n") == 3

    def test_tag_match_with_quantity(self):
        """标签匹配 + 数量：'两个玩具'应返回 2 条。"""
        result = augment("两个玩具")
        assert result.count("\n") == 2

    def test_fuzzy_quantity(self):
        """模糊数量：'几个花盆'应返回 2~4 条。"""
        result = augment("几个花盆")
        n = result.count("\n")
        assert 2 <= n <= 4, f"期望 2~4 条，实际 {n} 条"

    def test_no_match_returns_original(self):
        """无匹配时原样返回，不含换行。"""
        result = augment("xyz不存在的物品abc123")
        assert result == "xyz不存在的物品abc123"

    def test_returns_string(self):
        """返回值类型检查。"""
        assert isinstance(augment("测试"), str)

    def test_multiple_keywords(self):
        """多关键词：秋千和滑梯各匹配。"""
        result = augment("秋千和滑梯")
        assert result.count("\n") >= 2

    # ---- 鲁棒性边界测试 ----

    def test_negation_skips_match(self):
        """否定检测：'没有足球'不应匹配足球。"""
        assert augment("没有足球") == "没有足球"
        assert augment("不是花盆") == "不是花盆"
        assert augment("这里没球") == "这里没球"

    def test_empty_input(self):
        """空白输入：空字符串和纯空白直接返回。"""
        assert augment("") == ""
        assert augment("   ") == "   "

    def test_large_quantity_clamped(self):
        """大数量封顶：'一百个球'不超过实际候选数。"""
        result = augment("一百个球")
        n = result.count("\n")
        # 球类共 9 条，即使要 100 条也应 ≤ 9
        assert 1 <= n <= 9, f"一百个球应 ≤9 条，实际 {n}"

    def test_many_quantity(self):
        """'很多'数量词应返回 3~6 条。"""
        result = augment("很多玩具")
        n = result.count("\n")
        assert 3 <= n <= 6, f"很多玩具期望 3~6 条，实际 {n}"

    def test_repeated_keyword(self):
        """重复关键词应去重处理。"""
        result = augment("球和球和球")
        n = result.count("\n")
        assert 1 <= n <= 9

    # ---- 同义词语义匹配 ----

    def test_synonym_child(self):
        """'小孩'应通过同义词组匹配到儿童类。"""
        result = augment("两个小孩在玩")
        assert result.count("\n") >= 2  # "两个" → 2条

    def test_synonym_fence(self):
        """'围墙'应通过同义词组匹配到栅栏类。"""
        result = augment("一些围墙")
        n = result.count("\n")
        assert 2 <= n <= 4  # "一些" → 2~4条

    def test_synonym_dog(self):
        """'狗狗'应通过同义词组匹配到宠物类。"""
        result = augment("一只狗狗")
        assert result.count("\n") == 1

    def test_synonym_trash(self):
        """'垃圾'应通过同义词组匹配到杂物类。"""
        result = augment("一些垃圾")
        n = result.count("\n")
        assert 2 <= n <= 4

    def test_location_filtered(self):
        """位置词'草坪''庭院'不应触发匹配。"""
        result = augment("草坪和庭院都很漂亮")
        assert result == "草坪和庭院都很漂亮"

    def test_complex_scene(self):
        """综合场景：玩具+花盆+小孩+栅栏全匹配。"""
        result = augment("两个玩具和一个花盆，两个小孩在玩，远处有栅栏")
        n = result.count("\n")
        # 期望：2玩具 + 1花盆 + 2儿童 + 2~4栅栏 = 7~9
        assert n >= 5, f"复杂场景期望≥5条，实际{n}条"


class TestRandomScene:
    """random_scene 测试。"""

    def test_random_scene_returns_string(self):
        result = random_scene()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_random_scene_dry_run(self):
        result = random_scene(dry_run=True)
        assert isinstance(result, dict)
        assert "template_name" in result
        assert "picks" in result
        assert "prompt_preview" in result
        assert isinstance(result["picks"], dict)

    def test_random_scene_consistency(self):
        """多次调用应产生不同结果（概率极高）。"""
        results = {random_scene() for _ in range(5)}
        # 5 次调用至少产生 2 种不同结果（概率 > 99.9%）
        assert len(results) >= 2, "random_scene 多次调用产生的结果过于一致"
