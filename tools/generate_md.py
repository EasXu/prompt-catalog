#!/usr/bin/env python3
"""
从 _data.py 反向生成 prompts.md（人类可读的提示词库文档）。

用法:
    python tools/generate_md.py

输出:
    在项目根目录生成/覆盖 prompts.md
"""

import os
import sys

# 确保项目根目录在 path 中，以便 import prompt_catalog
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_catalog._data import PROMPTS  # noqa: E402


# ============================================================
# 大类排序（按 md 中的展示顺序）
# ============================================================
CATEGORY_ORDER = [
    "potted_plants",
    "toys",
    "hoses",
    "people",
    "pets",
    "wildlife",
    "clutter",
    "garden_tools",
    "furniture",
    "other",
    "fences",
    "paths",
    "play_equipment",
    "drying",
    "decor",
    "bicycles",
    "trees_plants",
    "outdoor_electrical",
]


def _generate_md() -> str:
    """生成完整的 markdown 内容。"""
    lines: list[str] = []

    # 头部
    lines.append("# prompt-catalog — 预制提示词库")
    lines.append("")
    lines.append("> **用途**：在现有庭院草坪照片上通过 SD inpaint 叠加障碍物，扩充训练数据集。")
    lines.append("> **原则**：每个物体独立描述，不含草坪等背景信息。描述自然流畅，力求全面但不脱离真实庭院场景。")
    lines.append("> **自动生成**：本文档由 `tools/generate_md.py` 从 `_data.py` 自动生成，请勿手动编辑。")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 使用方式")
    lines.append("")
    lines.append("从下方各分类中选取需要的障碍物，复制对应提示词，在 SD 的 inpaint 区域中生成，叠加到真实草坪照片上。")
    lines.append("")

    # 按顺序遍历各大类
    section_num = 0
    for cat_key in CATEGORY_ORDER:
        if cat_key not in PROMPTS:
            continue
        cat = PROMPTS[cat_key]
        section_num += 1

        # 大类标题
        lines.append("---")
        lines.append("")

        # 生成中文序号
        chinese_nums = [
            "", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
            "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
        ]
        num_str = chinese_nums[section_num] if section_num < len(chinese_nums) else str(section_num)

        lines.append(f"## {num_str}、{cat['label']}")
        lines.append("")

        # 统计条目数
        total_items = len(cat["items"])
        meta_structural = cat["meta"].get("structural", False)
        max_per = cat["meta"].get("max_per_scene", 1)

        lines.append(f"> {total_items} 条 | structural={meta_structural} | max_per_scene={max_per}")
        lines.append("")

        # 表格头
        lines.append("| ID | 名称 | 预制提示词 |")
        lines.append("|----|------|-----------|")

        # 表格行——按 ID 排序
        for item_id in sorted(cat["items"].keys()):
            item = cat["items"][item_id]
            name = item.get("name", "")
            prompt = item.get("prompt", "")
            tags = item.get("tags", [])
            # 将 tags 附加到名称后面
            name_with_tags = name
            if tags:
                name_with_tags += f"（{'，'.join(tags)}）"
            lines.append(f"| {item_id} | {name_with_tags} | {prompt} |")

        lines.append("")

    # 尾部
    lines.append("---")
    lines.append("")
    lines.append(f"> 本文档由 `tools/generate_md.py` 自动生成，共 {section_num} 大类。")
    lines.append("> 如需修改提示词内容，请编辑 `prompt_catalog/_data.py` 后重新运行此脚本。")

    return "\n".join(lines)


def main():
    """主函数：生成 markdown 文件。"""
    # 确定输出路径（项目根目录）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    output_path = os.path.join(project_root, "prompts.md")

    md_content = _generate_md()

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    # 统计信息
    total_items = sum(len(cat["items"]) for cat in PROMPTS.values())
    print(f"✅ 已生成 {output_path}")
    print(f"   大类: {len(PROMPTS)} | 条目: {total_items}")


if __name__ == "__main__":
    main()
