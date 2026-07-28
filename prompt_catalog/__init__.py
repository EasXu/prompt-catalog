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

import random

# 包版本号（与 pyproject.toml 保持同步）
__version__ = "0.2.0"

# 公开 API
from ._composer import compose, random_scene   # noqa: E402, F401
from ._data import PROMPTS                      # noqa: E402, F401


# ============================================================
# 关键词索引（augment 用，import 时一次性构建）
# ============================================================

# _NAME_INDEX:  item 全名 → [(cat_key, item_id), ...]
# _TAG_INDEX:   tag      → [(cat_key, item_id), ...]
# _TOKEN_INDEX: 对 name 和 tag 做 jieba 分词后的名词 → [(cat_key, item_id), ...]
_NAME_INDEX: dict[str, list[tuple[str, str]]] = {}
_TAG_INDEX: dict[str, list[tuple[str, str]]] = {}
_TOKEN_INDEX: dict[str, list[tuple[str, str]]] = {}


def _build_index() -> None:
    """遍历 PROMPTS 构建三级索引。"""
    try:
        import jieba.posseg as pseg  # noqa: F811
        _has_jieba = True
    except ImportError:
        pseg = None  # type: ignore[assignment]
        _has_jieba = False

    for cat_key, cat in PROMPTS.items():
        for item_id, item in cat["items"].items():
            name = item.get("name", "")
            tags = item.get("tags", [])

            # 1) 名称索引（精确匹配，最高优先级）
            _NAME_INDEX.setdefault(name, []).append((cat_key, item_id))

            # 2) 标签索引
            for tag in tags:
                _TAG_INDEX.setdefault(tag, []).append((cat_key, item_id))

            # 3) 分词索引：对 name 和 tag 再做 jieba 分词，提取名词
            #    对多字名词同时拆单字加入索引（解决 "球类"→"球" 无法匹配的问题）
            if _has_jieba:
                for text in [name] + tags:
                    for word, flag in pseg.cut(text):  # type: ignore[union-attr]
                        if flag.startswith("n"):
                            _TOKEN_INDEX.setdefault(
                                word, []
                            ).append((cat_key, item_id))
                            # 多字名词拆单字（如 "球类"→"球"）
                            if len(word) >= 2:
                                for ch in word:
                                    _TOKEN_INDEX.setdefault(
                                        ch, []
                                    ).append((cat_key, item_id))


_build_index()


# ============================================================
# augment() — 自然语言提示词智能增强
# ============================================================

# 中文数词 → 数值映射
_NUM_MAP: dict[str, int] = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _resolve_quantity(tokens: list[str], match_pos: int) -> int | None:
    """从匹配位置向前回溯，解析数量词。

    支持模式：
        "三个球"   → 3
        "一个足球"  → 1
        "2只猫"    → 2
        "几个花盆"  → None（随机2~4）
        "一些玩具"  → None（随机2~4）
        "球"       → 1（默认）

    Returns:
        int:  明确数量
        None: 模糊数量（"几个"/"一些"）
    """
    for offset in range(1, min(match_pos + 1, 4)):
        prev = tokens[match_pos - offset]

        # "三", "两" 等
        if prev in _NUM_MAP:
            return _NUM_MAP[prev]

        # 阿拉伯数字
        if prev.isdigit():
            return int(prev)

        # "几个", "一些", "多个", "若干" → 模糊数量
        if prev in ("几个", "一些", "多个", "若干"):
            return None

        # "一个", "两个" 等合并为一个 token 的情况
        if len(prev) >= 2:
            first_char = prev[0]
            if first_char in _NUM_MAP and prev.endswith("个"):
                return _NUM_MAP[first_char]
            if prev in ("一个", "两个", "三个", "四个", "五个",
                        "六个", "七个", "八个", "九个", "十个"):
                # jieba 可能将 "一个" 视为一个词
                for num_char, val in _NUM_MAP.items():
                    if prev.startswith(num_char):
                        return val

    return 1  # 默认 1 条


def _pick_items(
    candidates: list[tuple[str, str]],
    qty: int | None,
    seen_ids: set[str],
    results: list[tuple[int, str, str]],
    position: int,
) -> None:
    """从候选中随机抽取 qty 个，加入结果列表。

    Args:
        candidates: [(cat_key, item_id), ...]
        qty: 期望数量，None 表示随机 2~4
        seen_ids: 已选 item ID 集合（会原地修改）
        results: 结果列表（会原地追加）
        position: 匹配位置（用于排序）
    """
    available = [(c, i) for c, i in candidates if i not in seen_ids]
    if not available:
        return

    if qty is None:
        qty = random.randint(2, 4)

    n = min(qty, len(available))
    picked = random.sample(available, n)

    for cat_key, item_id in picked:
        seen_ids.add(item_id)
        results.append((position, cat_key, item_id))


def augment(user_prompt: str) -> str:
    """从用户自然语言提示词中提取物体关键词，按数量随机抽取预制提示词并拼接。

    算法：
    1. 用 jieba 分词，提取名词
    2. 对每个名词查关键词索引（名称 → 标签 两级）
    3. 回溯检测数量词（"三个球"→3条、"一个花盆"→1条、"几个玩具"→随机2~4条）
    4. 从匹配候选中随机抽取指定数量
    5. 按原文位置排序拼接返回

    Args:
        user_prompt: 用户输入的自然语言提示词

    Returns:
        原始文本 + 换行 + 匹配到的预制提示词（数量由原文决定）
        若无任何匹配，原样返回

    Example:
        >>> augment("草坪上有个足球")
        "草坪上有个足球\\n标准黑白五边形图案足球，表面有草渍和泥土污痕..."
        >>> augment("三个球")
        "三个球\\n<随机3条球类提示词>"
        >>> augment("空无一物")
        "空无一物"
    """
    try:
        import jieba.posseg as pseg
    except ImportError:
        raise ImportError(
            "augment() 需要 jieba 分词库，请执行: pip install jieba"
        )

    # 1. 分词 + 词性标注
    words = list(pseg.cut(user_prompt))
    tokens = [w.word for w in words]

    # 2. 扫描匹配
    raw_matches: list[tuple[int, str, str]] = []  # (pos, cat_key, item_id)
    seen_ids: set[str] = set()

    for pos, (word, flag) in enumerate(words):
        # 匹配名词类 token（n* = 名词/人名/地名/专名）
        if not (flag.startswith("n") or flag in ("eng", "x")):
            continue

        # 合并所有匹配层级的候选项（名称 > 标签 > 分词）
        candidates: list[tuple[str, str]] = []
        if word in _NAME_INDEX:
            candidates = list(_NAME_INDEX[word])
        else:
            if word in _TAG_INDEX:
                candidates.extend(_TAG_INDEX[word])
            if word in _TOKEN_INDEX:
                candidates.extend(_TOKEN_INDEX[word])
            # 去重（同一 item 可能在 tag 和 token 两层都被索引到）
            seen_in_word: set[str] = set()
            unique: list[tuple[str, str]] = []
            for c in candidates:
                if c[1] not in seen_in_word:
                    seen_in_word.add(c[1])
                    unique.append(c)
            candidates = unique

        if candidates:
            qty = _resolve_quantity(tokens, pos)
            _pick_items(candidates, qty, seen_ids, raw_matches, pos)

    # 3. 按原文位置排序
    raw_matches.sort(key=lambda m: m[0])

    if not raw_matches:
        return user_prompt

    # 4. 拼接
    prompt_lines = [user_prompt]
    for _, cat_key, item_id in raw_matches:
        item = PROMPTS[cat_key]["items"].get(item_id)
        if item:
            prompt_lines.append(item["prompt"])

    return "\n".join(prompt_lines)


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
