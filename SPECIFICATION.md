# prompt-catalog — 预制提示词库 项目规范

---

## 一、项目更新记录

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|----------|------|
| 0.2.0 | 2025-07-22 | 新增 augment() 函数，基于 jieba 分词 + 语义同义词组 + 数量检测，从自然语言中智能匹配预制提示词 | Easton |
| 0.1.0 | 2025-07-18 | 初始版本，包含 19 大类约 175 条障碍物提示词，支持指定类目组合和随机场景生成 | Easton |

> 每次更新须在上述表格中追加一行，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/) 规范。

---

## 二、项目性质描述

本项目是一个**通用的预制提示词管理工具**，最初为庭院除草机器人障碍物检测数据集设计。

- **目标**：管理、检索、组合预制提示词，可用于 SD inpainting 数据增强、LLM prompt 管理等任何需要预制提示词库的场景。
- **交付物**：一个可 `import` 的 Python 包 (`prompt-catalog`)，提供提示词的查询、随机抽取和场景组合功能。
- **数据流**：`prompt_catalog/_data.py` 是提示词的**唯一数据源**；`prompts.md` 由脚本自动生成，仅供人类查阅。

---

## 三、项目文件结构及依赖关系

```
prompt_catalog/
  SPECIFICATION.md              # 本文件：项目规范
  README.md                     # 快速入门与使用示例
  pyproject.toml                # 包元数据、版本号、构建配置
  prompt_catalog/               # 包主体
    __init__.py                 # 公开 API 入口
    _data.py                    # 【唯一数据源】所有提示词 + 元数据
    _composer.py                # 组合引擎：分层模板、随机抽取、排除规则、dry-run
    _exclusions.py              # 互斥规则配置
    _augment.py                 # 自然语言增强引擎：jieba分词 + 同义词组 + 三级索引 + 数量检测
  tools/
    generate_md.py              # 从 _data.py 反向生成 prompts.md
  tests/
    test_data_integrity.py      # 数据完整性测试
    test_api.py                 # API 功能测试
    test_composer.py            # 组合逻辑测试
  prompts.md                    # 【生成文件】人类可读的提示词库文档
```

### 依赖关系

```
prompt_catalog/_data.py        ← 无依赖（纯数据）
prompt_catalog/_exclusions.py  ← 无依赖（纯配置）
prompt_catalog/_composer.py    ← 依赖 _data.py, _exclusions.py
prompt_catalog/_augment.py     ← 依赖 _data.py, jieba（中文分词）
prompt_catalog/__init__.py     ← 依赖 _composer.py, _augment.py, _data.py
tools/generate_md.py           ← 依赖 _data.py
prompts.md                     ← 由 generate_md.py 生成
```

### 外部依赖

- Python ≥ 3.9
- 标准库（`random`, `re`, `json` 等）
- [jieba](https://github.com/fxsjy/jieba) ≥ 0.42（中文分词，仅 augment() 需要）

---

## 四、项目内更新流程标准

### 4.1 添加新提示词

1. 在 `prompt_catalog/_data.py` 中对应大类下追加新条目，分配唯一 ID
2. 若新增补大类，在 `prompt_catalog/_data.py` 的 `PROMPTS` 字典中添加新 key，结构须与现有大类一致
3. 若新条目与已有条目存在不合理的共存组合，在 `prompt_catalog/_exclusions.py` 中添加互斥规则
4. 运行 `python tools/generate_md.py` 重新生成 `prompts.md`
5. 运行测试套件，确保改动没有破坏已有功能：`python -m pytest tests/ -v`
6. 更新 `SPECIFICATION.md` 中的更新记录
7. 更新 `pyproject.toml` 中的 `version` 字段（须与更新记录中的版本号一致）
8. 提交时使用约定式提交信息：`feat: 添加[大类名]类提示词 [数量]条` 或 `fix: 修正[ID]提示词描述`

### 4.2 新增补大类

1. 在 `prompt_catalog/_data.py` 的 `PROMPTS` 字典末尾追加新的 key，结构如下：
   ```python
   "new_category_key": {
       "label": "中文类名",
       "meta": {
           "structural": False,       # 是否为结构级障碍（栅栏/小路/树木）
           "max_per_scene": 2,        # 一个场景中此类物品最多出现几个
       },
       "items": {
           "XX01": {
               "name": "物品中文名",
               "prompt": "提示词文本...",
               "tags": ["标签1", "标签2"],
           },
           ...
       },
   },
   ```
2. ID 前缀规则：用一个大类英文缩写作为前缀（如 Potted Plants → PP, Toys → TY），后跟两位数字从 01 开始
3. 在 `tools/generate_md.py` 的 `CATEGORY_ORDER` 列表末尾追加新 key
4. 在 `prompt_catalog/_composer.py` 的 `TEMPLATES` 中，选择合适的现有模板，将新 key 加入 `structural`/`functional`/`scattered` 列表之一
5. 若新大类与已有大类存在冲突组合，在 `prompt_catalog/_exclusions.py` 中添加互斥规则
6. 执行 §4.1 的步骤 4~8

### 4.3 修改现有提示词

1. 修改 `prompt_catalog/_data.py` 中对应条目的 `prompt` 字段
2. 跑 `generate_md.py` 更新 md
3. 跑测试

### 4.4 修改组合逻辑

1. 修改 `prompt_catalog/_composer.py` 或 `prompt_catalog/_exclusions.py`
2. 跑 `tests/test_composer.py` 确保组合结果符合预期
3. 若 API 签名变化，更新 `prompt_catalog/__init__.py` 和 `README.md`

---

## 五、项目代码编写更新规范

### 5.1 代码风格

- 遵循 [PEP 8](https://peps.python.org/pep-0008/)
- 所有公开函数必须有 **docstring**（中文描述 + 参数说明 + 返回值说明 + 示例）
- 所有私有函数和复杂逻辑必须有 **行内注释**
- 变量名使用英文，注释和文档使用中文

### 5.2 数据规范

- `prompt_catalog/_data.py` 中的每个 item 必须包含：
  - `name`: str — 中文名称
  - `prompt`: str — 英文或中文提示词文本，非空
  - `tags`: list[str] — 至少 1 个标签
- ID 格式：`[A-Z]{1,3}[0-9]{2}`（如 `PP01`, `TY01`, `FC01`）
- 每个大类必须有：
  - `label`: str — 中文类名
  - `meta`: dict — 包含 `structural` (bool) 和 `max_per_scene` (int)

### 5.3 测试规范

**测试框架**：pytest（需单独安装：`pip install pytest`）

**运行方式**：
```bash
pytest tests/ -v          # 跑全部测试
pytest tests/test_data_integrity.py -v   # 只跑数据完整性
```

**三个测试文件**：

| 文件 | 检查内容 | 何时必须通过 |
|------|----------|-------------|
| `test_data_integrity.py` | 无重复ID、无空prompt、必需字段完整、ID 格式正确 | 每次修改 `prompt_catalog/_data.py` 后 |
| `test_api.py` | 7 个公开函数返回值类型、错误处理、dry_run 结构 | 修改 `prompt_catalog/__init__.py` 后 |
| `test_composer.py` | 模板引用有效、排除规则触发、结构层 ≤1 个 | 修改 `prompt_catalog/_composer.py` 或 `prompt_catalog/_exclusions.py` 后 |

**原则**：提交前跑一次全量测试，全部 PASSED 再交。

---

## 六、代码调用方法及接口描述

### 6.1 导入

```python
from prompt_catalog import augment, compose, random_scene, search, list_categories, list_items, version
```

### 6.2 公开 API

#### `compose(categories: list[str]) -> str`

根据指定大类，从每个大类中随机抽取一条提示词并拼接返回。

- **参数**：`categories` — 大类 key 列表，如 `["toys", "clutter", "potted_plants"]`
- **返回**：拼接后的完整提示词字符串，每条用换行符分隔
- **错误**：若 `categories` 包含不存在的大类 key，抛出 `ValueError`

```python
>>> compose(["toys", "pets"])
"足球，黑白五边形图案...\n一只中型金毛犬趴在草坪上..."
```

#### `random_scene(dry_run: bool = False) -> str | dict`

随机生成一组自然合理的障碍物组合。

- **参数**：`dry_run` — 若为 True，返回组合清单而非完整提示词
- **返回**：拼接后的完整提示词字符串，或（dry_run 时）包含 `template`, `picks`, `prompt_preview` 的字典
- **逻辑**：内部随机选模板 → 按模板分层随机填坑 → 应用排除规则校验 → 拼接

```python
>>> random_scene()
"木条栅栏，木材表面有风化灰褐色调...\n足球，黑白五边形图案..."
>>> random_scene(dry_run=True)
{"template": "B", "picks": {"fences": ["FC01"], "toys": ["TY01"], "clutter": ["CL01"]}, "prompt_preview": "..."}
```

#### `search(keyword: str) -> list[dict]`

在所有提示词中模糊搜索关键词。

- **参数**：`keyword` — 中文或英文关键词
- **返回**：匹配条目列表，每条包含 `category`, `id`, `name`, `prompt_snippet`

```python
>>> search("足球")
[{"category": "toys", "id": "TY01", "name": "足球", "prompt_snippet": "标准黑白五边形图案足球..."}]
```

#### `list_categories() -> list[dict]`

列出所有大类。

- **返回**：每项包含 `key`, `label`, `structural`, `count`

```python
>>> list_categories()
[{"key": "potted_plants", "label": "盆栽/花盆", "structural": False, "count": 12}, ...]
```

#### `list_items(category: str) -> list[dict]`

列出指定大类下的所有条目。

- **参数**：`category` — 大类 key
- **返回**：每项包含 `id`, `name`, `tags`

```python
>>> list_items("toys")
[{"id": "TY01", "name": "足球", "tags": ["球类", "运动"]}, ...]
```

#### `augment(user_prompt: str) -> str`

从用户输入的自然语言文本中提取物体关键词，按数量随机抽取预制提示词拼接到原文后。

- **参数**：`user_prompt` — 自然语言描述，如 `"草坪上有个足球和三个花盆"`
- **返回**：原文 + 换行 + 匹配到的预制提示词；无匹配则原样返回
- **匹配策略**：jieba 分词 → 三级索引匹配（精确名称 > 标签 > 分词名词），支持数量检测（"三个球"→3条，"几个花盆"→2~4条）
- **依赖**：需要 `jieba` 分词库

```python
>>> augment("三个球")
"三个球\n标准黑白五边形图案足球...\n橙色篮球...\n黄绿色毛绒网球..."
>>> augment("空无一物")
"空无一物"
```

#### `version() -> str`

返回包版本号。

```python
>>> version()
"0.2.0"
```

### 6.3 调试日志

设置环境变量 `PROMPT_CATALOG_DEBUG=1` 可开启组合引擎的详细日志输出，便于排查组合结果不符合预期的问题。
