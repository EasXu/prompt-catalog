"""
augment — 自然语言提示词智能增强引擎

从用户自由文本中提取物体关键词，按数量随机抽取预制提示词拼接返回。

核心机制：
1. jieba 分词 + 词性标注 → 提取名词
2. 三级关键词索引（名称 > 标签 > 分词）匹配
3. 语义同义词组扩展（"小孩"→"儿童"、"围墙"→"栅栏"）
4. 数量检测（"三个球"→3条、"很多玩具"→3~6条）
5. 否定检测（"没有足球"→跳过）
"""

import random
import os
from typing import Any

from prompt_catalog import _data

PROMPTS = _data.PROMPTS


# ============================================================
# 语义同义词组
# ============================================================
# 每组是一个 set，组内所有词在语义上等价。
# 索引构建时：对每组中的每个词，关联到该组对应的所有 catalog tag。
# 这样用户说"小朋友"、"围墙"、"狗狗"都能自动匹配。

SYNONYM_GROUPS: list[tuple[set[str], list[str]]] = [
    # ── 人物 ──
    ({"儿童", "小孩", "小孩子", "孩子", "小朋友", "幼童", "娃娃", "宝宝",
      "孩童", "小儿", "稚童", "小娃", "小屁孩", "娃儿", "娃子", "崽"},
     ["儿童"]),

    ({"成人", "大人", "成年人", "家长", "父母", "爸妈", "爸爸", "妈妈",
      "老人", "老头", "老太太", "长者", "年长者"},
     ["成人"]),

    ({"人物", "人影", "人", "有人", "行人", "路人"},
     ["人物"]),

    # ── 栅栏/围墙 ──
    ({"栅栏", "围栏", "围墙", "篱笆", "护栏", "栏杆", "藩篱", "篱栅",
      "栅栏墙", "院墙", "墙围", "铁栅栏", "木栅栏"},
     ["栅栏", "围栏"]),

    # ── 宠物/动物 ──
    ({"宠物", "狗", "狗狗", "小狗", "猫", "猫咪", "小猫", "兔子", "兔兔",
      "仓鼠", "豚鼠", "动物", "小动物", "毛孩子", "汪星人", "喵星人",
      "小狗儿", "小狗狗", "大狗", "猫猫"},
     ["宠物", "狗", "猫", "兔子", "豚鼠", "仓鼠"]),

    # ── 玩具 ──
    ({"玩具", "玩物", "玩偶", "玩意儿", "玩具车", "积木", "乐高", "娃娃",
      "公仔", "布偶", "毛绒玩具", "小玩具", "儿童玩具"},
     ["玩具"]),

    ({"球", "皮球", "球球", "小球", "大球", "圆球", "球类"},
     ["球类"]),

    # ── 盆栽/花盆 ──
    ({"花盆", "盆栽", "盆景", "盆花", "花钵", "花缸", "花盆儿", "花盆子",
      "种花的盆", "花盘", "盆", "花坛"},
     ["盆栽", "花盆"]),

    # ── 杂物/垃圾 ──
    ({"杂物", "垃圾", "废品", "破烂", "废旧物品", "废弃物", "乱七八糟",
      "零碎", "杂七杂八", "杂碎", "垃圾堆"},
     ["杂物"]),

    ({"瓶子", "塑料瓶", "饮料瓶", "矿泉水瓶", "空瓶", "瓶"},
     ["瓶子"]),

    ({"纸箱", "箱子", "快递盒", "包装箱", "纸盒", "盒子", "包装盒"},
     ["纸箱"]),

    ({"报纸", "报刊", "纸", "废纸", "纸张"},
     ["报纸", "纸制品"]),

    ({"衣服", "衣物", "衣裳", "服装", "穿着", "T恤", "外套", "裤子",
      "袜子", "鞋", "鞋子", "拖鞋", "运动鞋", "布鞋"},
     ["衣物", "鞋类"]),

    # ── 家具 ──
    ({"家具", "桌", "桌子", "椅", "椅子", "凳", "凳子", "长椅", "躺椅",
      "茶几", "沙发", "板凳", "木椅", "塑料椅", "折叠椅"},
     ["家具", "座椅"]),

    ({"遮阳伞", "太阳伞", "伞", "大伞", "凉伞", "遮阳", "遮阳篷"},
     ["遮阳", "伞"]),

    # ── 园艺工具 ──
    ({"工具", "园艺工具", "园丁工具", "器械", "农具", "铲子", "铁锹",
      "锄头", "耙子", "镰刀", "剪刀", "修枝剪"},
     ["工具"]),

    ({"割草机", "除草机", "打草机", "剪草机", "草坪机"},
     ["割草机", "打草机"]),

    # ── 洒水/浇水 ──
    ({"洒水器", "喷水器", "浇水器", "喷灌", "喷头", "洒水", "浇水",
      "喷水", "灌溉", "浇灌"},
     ["洒水器"]),

    ({"水管", "软管", "橡胶管", "塑料管", "浇水软管", "皮管", "水喉"},
     ["水管"]),

    ({"水桶", "桶", "水盆", "提桶", "塑料桶", "桶子"},
     ["水桶"]),

    # ── 晾晒 ──
    ({"晾衣架", "晾衣杆", "衣架", "晾晒架", "晾衣绳", "晒衣架",
      "晒衣绳", "晾晒", "晒衣服"},
     ["晾晒", "衣架"]),

    # ── 电器/线缆 ──
    ({"电线", "线缆", "电缆", "延长线", "电源线", "插线板", "接线板",
      "插座", "排插", "插头"},
     ["电器", "电缆", "延长线"]),

    ({"灯", "灯具", "庭院灯", "路灯", "落地灯", "草坪灯", "灭蚊灯",
      "太阳能灯", "灯泡", "照明"},
     ["灯具", "庭院灯"]),

    # ── 装饰品 ──
    ({"装饰", "装饰品", "摆件", "摆设", "饰物", "饰品", "点缀",
      "小装饰", "风铃", "彩旗", "石雕"},
     ["装饰"]),

    # ── 自行车/交通工具 ──
    ({"自行车", "单车", "脚踏车", "车子", "童车", "三轮车",
      "滑板", "滑板车", "推车", "婴儿车"},
     ["交通工具", "自行车", "三轮车", "滑板"]),

    # ── 游乐设施 ──
    ({"秋千", "荡秋千", "秋千架", "摇摆"},
     ["秋千"]),

    ({"滑梯", "滑滑梯", "滑道", "溜溜板", "滑坡"},
     ["滑梯"]),

    ({"蹦床", "弹跳床", "跳床", "蹦蹦床"},
     ["蹦床"]),

    ({"沙坑", "沙池", "沙地", "玩沙的地方", "沙堆"},
     ["沙坑"]),

    ({"泳池", "充气泳池", "戏水池", "小泳池", "水池", "儿童泳池"},
     ["泳池", "夏季"]),

    # ── 树木/植物 ──
    ({"树桩", "树墩", "树根", "树头", "木桩", "残桩", "树茬"},
     ["树桩", "树根"]),

    ({"灌木", "灌木丛", "树丛", "矮树", "灌丛", "草丛"},
     ["灌木"]),

    ({"树干", "倒树", "倒下的树", "枯树", "枯木", "断木", "木头"},
     ["树干", "倒木"]),

    ({"竹子", "竹丛", "竹林", "竹竿", "竹", "毛竹"},
     ["竹子"]),

    ({"观赏草", "芒草", "蒲苇", "芦苇", "茅草", "长草", "高草"},
     ["观赏草"]),

    # ── 野生动物 ──
    ({"野生动物", "小动物", "刺猬", "松鼠", "野兔", "兔子", "鸽子",
      "鸟", "鸟儿", "小鸟", "麻雀", "乌鸦", "喜鹊", "知更鸟",
      "蜗牛", "青蛙", "蟾蜍", "蜥蜴", "壁虎", "四脚蛇"},
     ["野生动物", "鸟类", "哺乳动物", "爬行", "两栖"]),

    # ── 小路 ──
    ({"小路", "步道", "小径", "路面", "石板路", "石子路", "砖路",
      "人行道", "走道", "通道", "路", "径"},
     ["小路"]),
]

# 位置词——这些词不应触发匹配
_LOCATION_WORDS: set[str] = {
    "草坪", "草地", "庭院", "花园", "院子", "后院", "前院", "地面",
    "空地", "草坪上", "草地上",
}


# ============================================================
# 关键词索引
# ============================================================

_NAME_INDEX: dict[str, list[tuple[str, str]]] = {}
_TAG_INDEX: dict[str, list[tuple[str, str]]] = {}
_TOKEN_INDEX: dict[str, list[tuple[str, str]]] = {}


def _build_index() -> None:
    """遍历 PROMPTS 构建三级关键词索引 + 同义词扩展。"""
    try:
        import jieba.posseg as pseg  # noqa: F811
        _has_jieba = True
    except ImportError:
        pseg = None
        _has_jieba = False

    for cat_key, cat in PROMPTS.items():
        for item_id, item in cat["items"].items():
            name = item.get("name", "")
            tags = item.get("tags", [])

            # 1) 名称索引
            _NAME_INDEX.setdefault(name, []).append((cat_key, item_id))

            # 2) 标签索引
            for tag in tags:
                _TAG_INDEX.setdefault(tag, []).append((cat_key, item_id))

            # 3) 分词索引
            if _has_jieba:
                for text in [name] + tags:
                    for word, flag in pseg.cut(text):
                        if flag.startswith("n"):
                            _TOKEN_INDEX.setdefault(word, []).append(
                                (cat_key, item_id)
                            )
                            if len(word) >= 2:
                                for ch in word:
                                    _TOKEN_INDEX.setdefault(ch, []).append(
                                        (cat_key, item_id)
                                    )

    # 4) 同义词扩展：将同义词组映射为 tag index 的扩展项
    for syn_set, target_tags in SYNONYM_GROUPS:
        # 收集 target_tags 对应的所有 items
        expanded_items: list[tuple[str, str]] = []
        seen: set[str] = set()
        for tag in target_tags:
            if tag in _TAG_INDEX:
                for cat_key, item_id in _TAG_INDEX[tag]:
                    if item_id not in seen:
                        seen.add(item_id)
                        expanded_items.append((cat_key, item_id))

        if not expanded_items:
            continue

        # 将同义词组中每个词都映射到这些 items
        for word in syn_set:
            if word not in _TAG_INDEX:
                _TAG_INDEX[word] = []
            existing = {item_id for _, item_id in _TAG_INDEX[word]}
            for ci in expanded_items:
                if ci[1] not in existing:
                    _TAG_INDEX[word].append(ci)


_build_index()


# ============================================================
# 辅助函数
# ============================================================

_NUM_MAP: dict[str, int] = {
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}

_NEG_WORDS: set[str] = {"不", "没", "没有", "非", "无", "别", "不是", "不要", "不会"}


def _resolve_quantity(tokens: list[str], match_pos: int) -> int | None:
    """从匹配位置向前回溯，解析数量词。"""
    for offset in range(1, min(match_pos + 1, 4)):
        prev = tokens[match_pos - offset]

        if prev in _NUM_MAP:
            return _NUM_MAP[prev]

        if prev.isdigit():
            return int(prev)

        if prev in ("几个", "一些", "多个", "若干"):
            return None

        if prev in ("很多", "大量", "好多", "不少"):
            return -1

        if len(prev) >= 2:
            first_char = prev[0]
            if first_char in _NUM_MAP and prev.endswith("个"):
                return _NUM_MAP[first_char]

    return 1


def _is_negated(tokens: list[str], match_pos: int) -> bool:
    """检查匹配位置前 3 个 token 内是否包含否定词。"""
    start = max(0, match_pos - 3)
    for i in range(start, match_pos):
        if tokens[i] in _NEG_WORDS:
            return True
    return False


def _pick_items(
    candidates: list[tuple[str, str]],
    qty: int | None,
    seen_ids: set[str],
    results: list[tuple[int, str, str]],
    position: int,
) -> None:
    """从候选中随机抽取 qty 个，加入结果列表。"""
    available = [(c, i) for c, i in candidates if i not in seen_ids]
    if not available:
        return

    if qty is None:
        qty = random.randint(2, 4)
    elif qty == -1:
        qty = random.randint(3, 6)

    n = min(qty, len(available))
    picked = random.sample(available, n)

    for cat_key, item_id in picked:
        seen_ids.add(item_id)
        results.append((position, cat_key, item_id))


def _fallback_match(user_prompt: str) -> str:
    """jieba 不可用时的降级方案。"""
    raw_matches: list[tuple[int, str, str]] = []
    seen_ids: set[str] = set()

    for cat_key, cat in PROMPTS.items():
        for item_id, item in cat["items"].items():
            if item_id in seen_ids:
                continue
            for tag in item.get("tags", []):
                if len(tag) < 2:
                    continue
                pos = user_prompt.find(tag)
                if pos != -1:
                    seen_ids.add(item_id)
                    raw_matches.append((pos, cat_key, item_id))
                    break

    raw_matches.sort(key=lambda m: m[0])
    if not raw_matches:
        return user_prompt

    lines = [user_prompt]
    for _, cat_key, item_id in raw_matches:
        item = PROMPTS[cat_key]["items"].get(item_id)
        if item:
            lines.append(item["prompt"])
    return "\n".join(lines)


# ============================================================
# augment() 主函数
# ============================================================

def augment(user_prompt: str) -> str:
    """从用户自然语言提示词中提取物体关键词，按数量随机抽取预制提示词并拼接。

    算法：
    1. 输入校验（空/纯空白直接返回）
    2. jieba 分词提取名词（不可用时降级为简易子串匹配）
    3. 否定检测（"没有足球"→跳过）
    4. 三级索引匹配（名称 → 标签 → 分词）+ 位置词过滤
    5. 数量检测 + 随机抽取 + 去重 + 排序拼接

    Returns:
        原始文本 + 换行 + 匹配到的预制提示词
        无匹配/异常则原样返回
    """
    if not user_prompt or not user_prompt.strip():
        return user_prompt or ""

    try:
        try:
            import jieba.posseg as pseg
            _use_jieba = True
        except ImportError:
            _use_jieba = False

        if not _use_jieba:
            return _fallback_match(user_prompt)

        words = list(pseg.cut(user_prompt))
        tokens = [w.word for w in words]

        raw_matches: list[tuple[int, str, str]] = []
        seen_ids: set[str] = set()

        for pos, (word, flag) in enumerate(words):
            if not (flag.startswith("n") or flag in ("eng", "x")):
                continue

            # 位置词过滤
            if word in _LOCATION_WORDS:
                continue

            # 否定检测
            if _is_negated(tokens, pos):
                continue

            candidates: list[tuple[str, str]] = []
            if word in _NAME_INDEX:
                candidates = list(_NAME_INDEX[word])
            else:
                if word in _TAG_INDEX:
                    candidates.extend(_TAG_INDEX[word])
                if word in _TOKEN_INDEX:
                    candidates.extend(_TOKEN_INDEX[word])
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

        raw_matches.sort(key=lambda m: m[0])

        if not raw_matches:
            return user_prompt

        prompt_lines = [user_prompt]
        for _, cat_key, item_id in raw_matches:
            item = PROMPTS[cat_key]["items"].get(item_id)
            if item:
                prompt_lines.append(item["prompt"])

        return "\n".join(prompt_lines)

    except Exception:
        return user_prompt
