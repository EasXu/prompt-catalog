"""
prompt-catalog — 预制提示词库

可组合、可检索的提示词管理工具。
最初为庭院除草机器人障碍物检测数据集设计，可用于任何需要预制提示词的场景。

主要 API:
    augment(user_prompt)   — 从用户自然语言中提取物体关键词，按数量随机抽取预制提示词拼接到原文后
    compose(categories)    — 指定类目随机抽取组合
    random_scene()          — 完全随机生成自然合理的场景组合
    search(keyword)         — 模糊搜索提示词
    list_categories()       — 列出所有大类
    list_items(category)    — 列出某大类下所有条目
    version()               — 返回包版本号

调试:
    设置环境变量 PROMPT_CATALOG_DEBUG=1 可开启组合引擎调试日志。

Examples:
    >>> from prompt_catalog import augment, compose, random_scene, search
    >>> augment("草坪上有个足球和两个花盆")
    '草坪上有个足球和两个花盆\\n标准黑白五边形图案足球，表面有草渍和泥土污痕...'
    >>> compose(["toys", "pets"])
    '足球，黑白五边形图案...\\n一只中型金毛犬趴在草坪上...'
    >>> random_scene()
    '木条栅栏，木材表面有风化灰褐色调...\\n足球，黑白五边形图案...'
    >>> search("足球")
    [{"category": "toys", "id": "TY01", "name": "足球", "prompt_snippet": "标准黑白五边形图案足球..."}]
"""

# 包版本号（与 pyproject.toml 保持同步）
__version__ = "0.2.0"

# 公开 API
from ._composer import compose, random_scene   # noqa: E402, F401
from ._augment import augment                    # noqa: E402, F401
from ._data import PROMPTS                      # noqa: E402, F401


# ============================================================
# 其余公开 API
# ============================================================

def search(keyword: str) -> list[dict]:
    """在所有提示词中模糊搜索关键词。

    搜索范围：item 的 name 字段和 prompt 字段。
    大小写不敏感，中文精确匹配。

    Args:
        keyword: 中文或英文关键词

    Returns:
        匹配条目列表，每条包含 category, id, name, prompt_snippet
        prompt_snippet 为 prompt 的前 80 个字符（含省略号）

    Example:
        >>> search("足球")
        [{"category": "toys", "id": "TY01", "name": "足球", "prompt_snippet": "标准黑白五边形图案足球..."}]
    """
    results = []
    keyword_lower = keyword.lower()
    for cat_key, cat in PROMPTS.items():
        for item_id, item in cat["items"].items():
            name = item.get("name", "")
            prompt = item.get("prompt", "")
            if (
                keyword_lower in name.lower()
                or keyword_lower in prompt.lower()
            ):
                snippet = prompt[:80] + "..." if len(prompt) > 80 else prompt
                results.append({
                    "category": cat_key,
                    "id": item_id,
                    "name": name,
                    "prompt_snippet": snippet,
                })
    return results


def list_categories() -> list[dict]:
    """列出所有障碍物大类。

    Returns:
        每项包含 key（大类 key）、label（中文名）、
        structural（是否为结构障碍）、count（条目数）

    Example:
        >>> list_categories()
        [{"key": "potted_plants", "label": "盆栽/花盆", "structural": False, "count": 12}, ...]
    """
    return [
        {
            "key": cat_key,
            "label": cat["label"],
            "structural": cat["meta"].get("structural", False),
            "count": len(cat["items"]),
        }
        for cat_key, cat in PROMPTS.items()
    ]


def list_items(category: str) -> list[dict]:
    """列出指定大类下的所有条目。

    Args:
        category: 大类 key（如 "toys", "clutter"）

    Returns:
        每项包含 id, name, tags

    Raises:
        ValueError: 若 category 不存在

    Example:
        >>> list_items("toys")
        [{"id": "TY01", "name": "足球", "tags": ["球类", "运动"]}, ...]
    """
    if category not in PROMPTS:
        raise ValueError(
            f"未知的大类: '{category}'。可用: {list(PROMPTS.keys())}"
        )
    cat = PROMPTS[category]
    return [
        {
            "id": item_id,
            "name": item["name"],
            "tags": item.get("tags", []),
        }
        for item_id, item in cat["items"].items()
    ]


def version() -> str:
    """返回包版本号。

    Example:
        >>> version()
        "0.2.0"
    """
    return __version__
