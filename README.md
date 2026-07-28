# prompt-catalog — 预制提示词库

可组合、可检索的提示词管理工具。最初为庭院除草机器人障碍物检测数据集设计，可用于任何需要预制提示词的场景。

## 安装

```bash
pip install -e .        # 开发模式安装
pip install jieba       # augment() 需要 jieba 中文分词
```

依赖：Python ≥ 3.9 + [jieba](https://github.com/fxsjy/jieba)（中文分词）。

## 快速开始

```python
from prompt_catalog import augment, compose, random_scene, search

# 智能增强：从自然语言中提取物体关键词，按数量随机抽取预制提示词拼接
result = augment("草坪上有个足球和两个花盆")
print(result)

# 指定类目随机抽取
prompt = compose(["toys", "clutter", "potted_plants"])
print(prompt)

# 完全随机场景
prompt = random_scene()
print(prompt)

# 搜索关键词
results = search("足球")
for r in results:
    print(r["id"], r["name"])
```

## API

| 函数 | 说明 |
|------|------|
| `augment(user_prompt)` | 从自然语言中提取关键词，按数量随机抽取预制提示词拼接到原文后 |
| `compose(categories)` | 从指定大类中各随机取一条，拼接返回 |
| `random_scene(dry_run=False)` | 随机生成一组自然合理的障碍物组合 |
| `search(keyword)` | 模糊搜索提示词 |
| `list_categories()` | 列出所有障碍物大类 |
| `list_items(category)` | 列出某大类下所有条目 |
| `version()` | 返回包版本号 |

详见 [SPECIFICATION.md](SPECIFICATION.md) 中的接口描述。

## 快速验证

```bash
python test_import.py       # 不需要装任何依赖，直接跑
```

这个脚本会调用所有公开 API 并打印结果，方便快速确认包能正常 import 和使用。

## 测试

```bash
pip install pytest          # 首次需要安装
pytest tests/ -v            # 跑全部自动化测试
```

三个测试文件的作用：

| 文件 | 检查内容 |
|------|----------|
| `test_data_integrity.py` | 数据有没有毛病（重复ID、空prompt、缺失字段） |
| `test_api.py` | 7 个公开函数行为对不对（返回值类型、错误处理） |
| `test_composer.py` | 随机组合逻辑是否正常（模板有效、排除规则触发、结构层不超限） |

提交改动前跑一次，全绿再交。

## 调试

```bash
PROMPT_CATALOG_DEBUG=1 python your_script.py
```

## 项目结构

```
prompt_catalog/
  SPECIFICATION.md          # 项目规范
  README.md                 # 本文件
  pyproject.toml            # 包配置
  prompts.md                # 人类可读提示词库（由脚本生成）
  prompt_catalog/
    __init__.py             # 公开 API
    _data.py                # 唯一数据源
    _composer.py            # 组合引擎
    _exclusions.py          # 互斥规则
  tools/
    generate_md.py          # 从 _data.py 生成 prompts.md
  tests/
    test_data_integrity.py  # 数据完整性
    test_api.py             # API 功能
    test_composer.py        # 组合逻辑
```

## 更新提示词

完整规范见 [SPECIFICATION.md §四](SPECIFICATION.md)。

**日常流程**：

1. 编辑 `prompt_catalog/_data.py`（加条目/改描述）
2. 若新条目与已有条目不应共存，在 `_exclusions.py` 添加互斥规则
3. 运行 `python tools/generate_md.py` 更新 `prompts.md`
4. 运行 `python -m pytest tests/ -v` 确保测试通过
5. 在 `SPECIFICATION.md` 顶部更新版本记录
6. 在 `pyproject.toml` 中更新 `version` 字段

**新增大类时**：

- 在 `_data.py` 的 `PROMPTS` 末尾追加，结构参照现有大类（`label` / `meta` / `items`）
- 在 `tools/generate_md.py` 的 `CATEGORY_ORDER` 中追加新 key
- 在 `_composer.py` 的 `TEMPLATES` 中选择合适模板加入新 key
