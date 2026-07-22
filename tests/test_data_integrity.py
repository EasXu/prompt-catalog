"""
数据完整性测试

确保 _data.py 中所有提示词数据结构完整、无重复ID、无空字段。
"""

import pytest
from prompt_catalog._data import PROMPTS


class TestDataIntegrity:
    """数据完整性验证。"""

    def test_all_categories_have_required_fields(self):
        """每个大类必须有 label、meta、items 字段。"""
        for cat_key, cat in PROMPTS.items():
            assert "label" in cat, f"{cat_key} 缺少 label"
            assert isinstance(cat["label"], str), f"{cat_key} label 必须是字符串"
            assert len(cat["label"]) > 0, f"{cat_key} label 不能为空"

            assert "meta" in cat, f"{cat_key} 缺少 meta"
            assert "structural" in cat["meta"], f"{cat_key} meta 缺少 structural"
            assert isinstance(cat["meta"]["structural"], bool), (
                f"{cat_key} meta.structural 必须是布尔值"
            )
            assert "max_per_scene" in cat["meta"], f"{cat_key} meta 缺少 max_per_scene"
            assert isinstance(cat["meta"]["max_per_scene"], int), (
                f"{cat_key} meta.max_per_scene 必须是整数"
            )
            assert cat["meta"]["max_per_scene"] >= 1, (
                f"{cat_key} meta.max_per_scene 必须 >= 1"
            )

            assert "items" in cat, f"{cat_key} 缺少 items"
            assert isinstance(cat["items"], dict), f"{cat_key} items 必须是字典"
            assert len(cat["items"]) > 0, f"{cat_key} items 不能为空"

    def test_all_items_have_required_fields(self):
        """每个 item 必须有 name、prompt、tags 字段。"""
        for cat_key, cat in PROMPTS.items():
            for item_id, item in cat["items"].items():
                assert "name" in item, f"{cat_key}/{item_id} 缺少 name"
                assert isinstance(item["name"], str), f"{cat_key}/{item_id} name 必须是字符串"
                assert len(item["name"]) > 0, f"{cat_key}/{item_id} name 不能为空"

                assert "prompt" in item, f"{cat_key}/{item_id} 缺少 prompt"
                assert isinstance(item["prompt"], str), (
                    f"{cat_key}/{item_id} prompt 必须是字符串"
                )
                assert len(item["prompt"]) > 0, f"{cat_key}/{item_id} prompt 不能为空"

                assert "tags" in item, f"{cat_key}/{item_id} 缺少 tags"
                assert isinstance(item["tags"], list), f"{cat_key}/{item_id} tags 必须是列表"
                assert len(item["tags"]) >= 1, f"{cat_key}/{item_id} tags 不能为空"

    def test_no_duplicate_ids(self):
        """全局范围内不允许有重复的 item ID。"""
        all_ids: dict[str, list[str]] = {}
        for cat_key, cat in PROMPTS.items():
            for item_id in cat["items"]:
                if item_id not in all_ids:
                    all_ids[item_id] = []
                all_ids[item_id].append(cat_key)

        duplicates = {k: v for k, v in all_ids.items() if len(v) > 1}
        assert len(duplicates) == 0, f"发现重复 ID: {duplicates}"

    def test_id_format(self):
        """ID 格式检查：应为 2~4 个大写字母 + 2 位数字。"""
        import re
        for cat_key, cat in PROMPTS.items():
            for item_id in cat["items"]:
                assert re.match(r'^[A-Z]{2,4}\d{2}$', item_id), (
                    f"{cat_key}/{item_id} ID 格式不符合规范（应为 2~4 字母 + 2 数字）"
                )

    def test_all_prompts_non_empty(self):
        """所有 prompt 字符串不能仅由空白字符组成。"""
        for cat_key, cat in PROMPTS.items():
            for item_id, item in cat["items"].items():
                assert item["prompt"].strip(), (
                    f"{cat_key}/{item_id} prompt 为空或仅含空白字符"
                )

    def test_total_count(self):
        """确认提示词总数在合理范围内（>= 100）。"""
        total = sum(len(cat["items"]) for cat in PROMPTS.values())
        assert total >= 100, f"提示词总数 {total} 少于预期（>= 100）"
