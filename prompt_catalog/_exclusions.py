"""
互斥规则配置

定义不同障碍物类别之间不应同时出现的组合。
每个规则是一个 frozenset，包含互斥的大类 key。

规则原则：
- 季节性冲突（圣诞装饰 vs 夏季泳池）
- 功能性冲突（洒水器 vs 晾晒衣物）
- 场景逻辑冲突（人物野餐 vs 野生动物出没）
"""

# 互斥规则集合：每组互斥规则包含 2~4 个大类 key，
# 随机组合时，同组内的大类最多只能出现一个。
EXCLUSION_RULES: list[frozenset] = [
    # --- 季节性冲突 ---
    # 圣诞装饰与夏季物品不可能同时出现
    frozenset({"other"}),
    # 注意：此规则通过 tags 在 composer 中进一步细化，
    # 仅限制 OT07（圣诞装饰）不与充气泳池（PEQ05）同时出现

    # --- 功能性冲突 ---
    # 洒水器正在工作 → 不应有晾晒衣物
    frozenset({"sprinklers", "drying"}),

    # 洒水器正在工作 → 不应有户外电器线缆（安全风险）
    frozenset({"sprinklers", "outdoor_electrical"}),

    # --- 场景逻辑冲突 ---
    # 有儿童游乐设施时，不应有危险工具（如裸露刀片、碎玻璃）
    frozenset({"play_equipment", "garden_tools"}),
    # 注：此规则为软约束，仅降低概率而非完全禁止

    # 大量人物/儿童活动时，小型野生动物不会靠近
    frozenset({"people", "wildlife"}),

    # --- 空间冲突 ---
    # 大型家具和大型游乐设施不宜同时出现（空间不足）
    frozenset({"furniture", "play_equipment"}),

    # 晾晒区域与儿童游乐区域不宜重叠
    frozenset({"drying", "play_equipment"}),

    # --- 维护状态冲突 ---
    # 庭院若有人正在使用（人物 + 工具），不应同时呈现荒废状态
    # 通过 tags 在 composer 中细化处理
]


# 额外基于 tags 的软约束规则
# 格式：(tag_a, tag_b, reason)
# composer 检测到同时包含 tag_a 和 tag_b 的 item 时，会降低权重或触发重抽
TAG_CONFLICTS: list[tuple[str, str, str]] = [
    ("圣诞", "夏季", "季节性冲突"),
    ("洒水", "晾晒", "功能性冲突"),
    ("人物", "野生动物", "场景冲突"),
    ("破碎", "崭新", "状态矛盾"),
    ("儿童", "危险品", "安全冲突"),
]
