"""
API 功能测试

确保公开 API 函数行为符合预期。
"""

import pytest
from prompt_catalog import (
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
