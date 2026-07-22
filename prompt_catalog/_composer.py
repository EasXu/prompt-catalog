"""
组合引擎：分层模板、随机抽取、排除规则、dry-run 模式

核心设计：
- 21 个大类按 meta.structural 分为三个层级
- 结构层：决定画面骨架，每场景 0~1 个（栅栏、小路、树木等）
- 功能层：庭院常见设施，每场景 0~2 个（家具、洒水器、晾晒等）
- 散落层：小型可移动物品，每场景 1~4 个（玩具、杂物、盆栽等）

组合策略：
- 预设多套组合模板，每套模板规定了各层级可选的类目范围
- random_scene() 随机选模板 → 按模板从对应类目中随机抽取 → 应用排除规则 → 拼接
"""

import random
import os
from typing import Any

from prompt_catalog import _data
from prompt_catalog import _exclusions


# ============================================================
# 组合模板
# ============================================================
# 每个模板是一个 dict：
#   name: 模板名称（中文）
#   structural: 结构层可选类目列表，随机选 0~1 个
#   functional: 功能层可选类目列表，随机选 0~2 个
#   scattered: 散落层可选类目列表，随机选 1~4 个
# 注意：模板中的每个类目是否真的出现在最终结果中，
#       取决于该类的 meta.max_per_scene 和随机概率。

TEMPLATES = [
    {
        "name": "简洁场景",
        "structural": ["fences", "paths", "trees_plants"],
        "functional": [],
        "scattered": ["toys", "pets", "wildlife", "clutter"],
        "scattered_min": 1,
        "scattered_max": 2,
    },
    {
        "name": "日常庭院",
        "structural": ["fences", "paths", "trees_plants"],
        "functional": ["furniture", "sprinklers", "garden_tools"],
        "scattered": ["potted_plants", "toys", "pets", "clutter", "decor"],
        "scattered_min": 1,
        "scattered_max": 3,
    },
    {
        "name": "丰富场景",
        "structural": ["fences", "paths", "trees_plants"],
        "functional": ["furniture", "sprinklers", "drying", "garden_tools", "play_equipment"],
        "scattered": [
            "potted_plants", "toys", "hoses", "clutter",
            "pets", "wildlife", "decor", "outdoor_electrical", "other"
        ],
        "scattered_min": 2,
        "scattered_max": 4,
    },
    {
        "name": "杂乱庭院",
        "structural": [],
        "functional": ["furniture", "drying", "garden_tools"],
        "scattered": [
            "potted_plants", "toys", "hoses", "clutter",
            "pets", "bicycles", "other"
        ],
        "scattered_min": 3,
        "scattered_max": 5,
    },
    {
        "name": "纯散落物品",
        "structural": [],
        "functional": [],
        "scattered": [
            "toys", "clutter", "potted_plants", "pets",
            "hoses", "decor", "other"
        ],
        "scattered_min": 1,
        "scattered_max": 3,
    },
    {
        "name": "人物活动",
        "structural": ["fences", "paths"],
        "functional": ["furniture", "garden_tools"],
        "scattered": ["toys", "clutter", "pets", "bicycles", "play_equipment"],
        "scattered_min": 1,
        "scattered_max": 3,
        # 人物活动场景——允许出现人物
        "include_people": True,
    },
]


# ============================================================
# 层级分类（从 meta 中自动推导，此处显式声明以保证可读性）
# ============================================================
# 结构层：structural=True 的大类
STRUCTURAL_CATEGORIES = {
    k for k, v in _data.PROMPTS.items()
    if v["meta"].get("structural", False)
}

# 功能层：structural=False 但非小型散落物品的大类
FUNCTIONAL_CATEGORIES = {
    "furniture", "sprinklers", "drying", "garden_tools",
    "play_equipment", "bicycles",
}

# 散落层：其余均为散落物品
SCATTERED_CATEGORIES = (
    set(_data.PROMPTS.keys())
    - STRUCTURAL_CATEGORIES
    - FUNCTIONAL_CATEGORIES
    - {"people"}  # 人物单独处理
)


# ============================================================
# 排除规则检查
# ============================================================

def _check_exclusions(picked_categories: set[str], picked_tags: set[str]) -> bool:
    """检查选中的类目和标签是否触发互斥规则。

    Args:
        picked_categories: 已选中大类的 key 集合
        picked_tags: 已选中 item 的 tags 合集

    Returns:
        True 表示组合有效，False 表示触发互斥需重抽
    """
    # 硬约束：大类互斥规则
    for rule in _exclusions.EXCLUSION_RULES:
        overlap = rule & picked_categories
        if len(overlap) >= 2:
            if _is_debug():
                print(f"[composer] 触发互斥规则: {rule} ← 已选 {overlap}")
            return False

    # 软约束：tag 冲突
    for tag_a, tag_b, reason in _exclusions.TAG_CONFLICTS:
        if tag_a in picked_tags and tag_b in picked_tags:
            if _is_debug():
                print(f"[composer] 触发 tag 冲突 ({reason}): {tag_a} vs {tag_b}")
            return False

    return True


# ============================================================
# 随机抽取
# ============================================================

def _random_pick_from_category(category_key: str) -> str | None:
    """从指定大类中随机抽取一个 item 的 ID。

    Args:
        category_key: 大类 key

    Returns:
        item ID 字符串，或 None（若该大类不存在或为空）
    """
    cat = _data.PROMPTS.get(category_key)
    if not cat or not cat["items"]:
        return None
    return random.choice(list(cat["items"].keys()))


def _collect_tags(category_key: str, item_id: str) -> set[str]:
    """收集某个 item 的 tags。

    Args:
        category_key: 大类 key
        item_id: item ID

    Returns:
        tags 集合
    """
    cat = _data.PROMPTS.get(category_key)
    if not cat:
        return set()
    item = cat["items"].get(item_id)
    if not item:
        return set()
    return set(item.get("tags", []))


# ============================================================
# 核心组合逻辑
# ============================================================

def _compose_from_template(
    template: dict[str, Any],
    max_retries: int = 20,
) -> dict[str, Any]:
    """根据模板执行一次随机组合，返回组合结果。

    组合流程：
    1. 结构层：从模板 structural 列表中随机选 0~1 个类目
    2. 功能层：从模板 functional 列表中随机选 0~2 个类目
    3. 散落层：从模板 scattered 列表中随机选 scattered_min~scattered_max 个类目
    4. 可选人物：若模板标记 include_people，有一定概率添加人物
    5. 对每个选中的类目，随机抽取 1 个 item
    6. 应用排除规则校验，不通过则重抽（最多 max_retries 次）

    Args:
        template: 组合模板字典
        max_retries: 最大重试次数

    Returns:
        {"picks": {category_key: [item_id, ...]}, "valid": bool, "template_name": str}
    """
    for _ in range(max_retries):
        picks: dict[str, list[str]] = {}
        picked_categories: set[str] = set()
        picked_tags: set[str] = set()

        # --- 结构层：0~1 个 ---
        if template.get("structural") and random.random() < 0.6:
            cat = random.choice(template["structural"])
            item_id = _random_pick_from_category(cat)
            if item_id:
                picks[cat] = [item_id]
                picked_categories.add(cat)
                picked_tags |= _collect_tags(cat, item_id)

        # --- 功能层：0~2 个 ---
        if template.get("functional"):
            n_func = random.randint(0, min(2, len(template["functional"])))
            func_candidates = list(template["functional"])
            random.shuffle(func_candidates)
            for cat in func_candidates[:n_func]:
                item_id = _random_pick_from_category(cat)
                if item_id:
                    picks[cat] = [item_id]
                    picked_categories.add(cat)
                    picked_tags |= _collect_tags(cat, item_id)

        # --- 散落层：scattered_min ~ scattered_max 个 ---
        scat_min = template.get("scattered_min", 1)
        scat_max = template.get("scattered_max", 3)
        n_scat = random.randint(scat_min, min(scat_max, len(template.get("scattered", []))))
        scat_candidates = list(template.get("scattered", []))
        random.shuffle(scat_candidates)
        for cat in scat_candidates[:n_scat]:
            # 按 meta.max_per_scene 限制该类的抽取数量
            max_n = _data.PROMPTS[cat]["meta"]["max_per_scene"]
            n_items = random.randint(1, max_n)
            for _ in range(n_items):
                item_id = _random_pick_from_category(cat)
                if item_id:
                    if cat not in picks:
                        picks[cat] = []
                    # 避免同一类目重复抽取同一 item
                    if item_id not in picks[cat]:
                        picks[cat].append(item_id)
                        picked_categories.add(cat)
                        picked_tags |= _collect_tags(cat, item_id)

        # --- 可选人物 ---
        if template.get("include_people") and random.random() < 0.5:
            item_id = _random_pick_from_category("people")
            if item_id:
                picks["people"] = [item_id]
                picked_categories.add("people")
                picked_tags |= _collect_tags("people", item_id)

        # --- 排除规则校验 ---
        if _check_exclusions(picked_categories, picked_tags):
            return {
                "picks": picks,
                "valid": True,
                "template_name": template["name"],
            }

    # 重试用尽，返回最后一次尝试（标记为无效）
    return {
        "picks": picks,
        "valid": False,
        "template_name": template["name"],
    }


# ============================================================
# 指定类目组合（compose）
# ============================================================

def compose(categories: list[str]) -> str:
    """根据指定大类列表，从每个大类中随机抽取一条提示词并拼接。

    这是用户主动指定需要哪些障碍物类目时的调用接口。

    Args:
        categories: 大类 key 列表，如 ["toys", "clutter", "potted_plants"]

    Returns:
        拼接后的提示词字符串，每条用换行符分隔

    Raises:
        ValueError: 若某 key 不存在于数据源中

    Example:
        >>> compose(["toys", "pets"])
        "足球，黑白五边形图案...\\n一只中型金毛犬趴在草坪上..."
    """
    prompts: list[str] = []
    for cat_key in categories:
        if cat_key not in _data.PROMPTS:
            raise ValueError(f"未知的大类: '{cat_key}'。可用: {list(_data.PROMPTS.keys())}")
        item_id = _random_pick_from_category(cat_key)
        if item_id:
            prompt = _data.PROMPTS[cat_key]["items"][item_id]["prompt"]
            prompts.append(prompt)
    return "\n".join(prompts)


# ============================================================
# 随机场景（random_scene）
# ============================================================

def random_scene(dry_run: bool = False) -> str | dict[str, Any]:
    """随机生成一组自然合理的障碍物组合。

    内部流程：
    1. 从 TEMPLATES 中随机选一个模板
    2. 按模板规则从各层级随机抽取类目和 item
    3. 排除规则校验，不通过则换模板重试
    4. 拼接所有选中 item 的 prompt 文本

    Args:
        dry_run: 若为 True，不返回拼接后的 prompt，而是返回组合元数据

    Returns:
        - dry_run=False: 拼接后的完整提示词字符串
        - dry_run=True: {"template_name": str, "picks": dict, "prompt_preview": str}

    Example:
        >>> random_scene()
        "木条栅栏，木材表面有风化灰褐色调...\\n足球，黑白五边形图案..."
        >>> random_scene(dry_run=True)
        {"template_name": "日常庭院", "picks": {"fences": ["FC01"], ...}, "prompt_preview": "..."}
    """
    max_attempts = 10
    for _ in range(max_attempts):
        template = random.choice(TEMPLATES)
        result = _compose_from_template(template)

        if result["valid"] and result["picks"]:
            # 拼接 prompt
            prompt_lines: list[str] = []
            for cat_key, item_ids in result["picks"].items():
                cat = _data.PROMPTS[cat_key]
                for iid in item_ids:
                    item = cat["items"].get(iid)
                    if item:
                        prompt_lines.append(item["prompt"])

            full_prompt = "\n".join(prompt_lines)

            if dry_run:
                return {
                    "template_name": result["template_name"],
                    "picks": result["picks"],
                    "prompt_preview": (
                        full_prompt[:200] + "..."
                        if len(full_prompt) > 200
                        else full_prompt
                    ),
                }
            return full_prompt

    # 所有模板都失败，回退：随机选 2~3 个散落类目
    fallback_cats = random.sample(
        list(SCATTERED_CATEGORIES),
        min(3, len(SCATTERED_CATEGORIES)),
    )
    return compose(fallback_cats)


# ============================================================
# 辅助函数
# ============================================================

def _is_debug() -> bool:
    """检查是否开启了调试模式。"""
    return os.environ.get("PROMPT_CATALOG_DEBUG", "") == "1"
