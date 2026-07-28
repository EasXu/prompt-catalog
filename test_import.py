"""
简单测试脚本：验证包是否可正常 import 和调用。

在 VSCode 中右键 → "Run Python File in Terminal" 即可。
"""

import sys
import os

# 确保项目根目录在搜索路径中（以防未 pip install -e .）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prompt_catalog import (
    augment,
    compose,
    random_scene,
    search,
    list_categories,
    list_items,
    version,
)

print("=" * 50)
print(f"包版本: {version()}")
print("=" * 50)

# 1. 列出所有大类
print("\n📦 所有障碍物大类:")
for c in list_categories():
    print(f"  {c['key']:20s}  {c['label']:12s}  {c['count']:3d}条")

# 2. 查看玩具类有哪些
print("\n🧸 玩具类条目:")
for item in list_items("toys"):
    print(f"  {item['id']}  {item['name']}")

# 3. 搜索关键词
print("\n🔍 搜索'足球':")
for r in search("足球"):
    print(f"  [{r['category']}] {r['id']} {r['name']}")
    print(f"  → {r['prompt_snippet']}")

# 4. 指定类目组合
print("\n📝 compose(['toys', 'pets']):")
result = compose(["toys", "pets"])
print(f"  {result[:120]}...")

# 5. 随机场景
print("\n🎲 random_scene():")
result = random_scene()
print(f"  {result[:150]}...")

# 6. 随机场景 dry_run 模式
print("\n🔬 random_scene(dry_run=True):")
preview = random_scene(dry_run=True)
print(f"  模板: {preview['template_name']}")
print(f"  选中: {dict(preview['picks'])}")

# 7. augment — 自然语言智能增强
print("\n🧠 augment('草坪上有两个玩具和一个花盆，草地上有两个小孩正在玩玩耍，远处有一些栅栏围墙'):")
result = augment("草坪上有两个玩具和一个花盆")
print(f"  匹配到 {result.count(chr(10))} 条预制提示词")
lines = result.split("\n")
for i, line in enumerate(lines):
    if i == 0:
        print(f"  原文: {line}")
    else:
        print(line)

print("\n" + "=" * 50)
print("✅ 全部测试通过")
print("=" * 50)
