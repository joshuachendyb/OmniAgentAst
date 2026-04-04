# Omni 系统工具定义说明书

**创建时间**: 2026-04-04 06:15:11
**编写人**: 小沈
**版本**: v1.0

---

## 一、工具定义核心（精要）

### 1.1 工具定义四要素

每个工具定义包含以下4个核心要素：

| 要素 | 来源 | 说明 |
|------|------|------|
| **name** | 手动指定 | 工具名称，LLM 通过此名称调用 |
| **description** | 手动指定 | 工具用途说明，告诉 LLM 何时使用 |
| **parameters** | Pydantic模型自动生成 | 参数类型、必选/可选、参数描述 |
| **examples** | 手动指定 | 使用示例（可选，帮助 LLM 理解） |

### 1.2 一个函数的完整定义包含

| 序号 | 字段 | 来源 | 说明 |
|------|------|------|------|
| 1 | name | @register_tool 手动指定 | 工具名称 |
| 2 | description | @register_tool 手动指定 | 工具用途说明 |
| 3 | input_schema | Pydantic 模型自动生成 | 参数类型、必选/可选、描述 |
| 4 | input_examples | @register_tool 手动指定 | 使用示例（可选） |

### 1.2 工具定义代码结构

```python
@register_tool(
    name="工具名",                                    # ← 1. name
    description="工具用途说明...",                     # ← 2. description
    input_model=工具参数模型,                         # ← 3. Pydantic模型 → 自动生成parameters
    examples=[{...}]                                  # ← 4. examples（可选）
)
async def 工具函数(self, 参数...):
    ...
```

### 1.3 Pydantic 模型定义参数

```python
class 工具名Input(BaseModel):
    参数名: 类型 = Field(..., description="参数说明")           # 必填参数
    参数名: 类型 = Field(default=默认值, description="参数说明")  # 可选参数
```

### 1.4 最终输出格式（OpenAI兼容）

```python
{
    "type": "function",
    "function": {
        "name": "工具名",
        "description": "工具用途...",
        "parameters": {
            "type": "object",
            "properties": {
                "参数名": {
                    "type": "类型",
                    "description": "参数说明"
                }
            },
            "required": ["必填参数"]
        }
    }
}
```

---

## 二、详细说明与示例

### 2.1 @register_tool 装饰器

**作用**：注册工具，将其添加到工具注册表

**参数**：
- `name`: 工具名称（必填）
- `description`: 工具描述，说明使用场景和参数说明（必填）
- `input_model`: Pydantic 模型类，用于生成参数 Schema（必填）
- `examples`: 使用示例列表，可选，帮助 LLM 理解参数格式

### 2.2 Pydantic 模型

**作用**：用 Pydantic 定义工具参数的结构、类型、验证规则
 
类型是什么？（str、int、bool）
必填还是可选？（... 必填，default=xxx 可选）
参数描述是什么？

**关键特性**：
- `...` 表示必填参数
- `default=xxx` 表示可选参数
- `Field(description="xxx")` 添加参数描述
- `ge`、`le`、`gt`、`lt` 用于数值范围限制

### 2.3 自动 Schema 生成- Pydantic 自动转换

**原理**：通过 `model_json_schema()` 将 Pydantic 模型转换为 JSON Schema

```
Pydantic 模型                          JSON Schema
─────────────────────────────────────────────────────────
str                                  → "type": "string"
int                                  → "type": "integer"
bool                                 → "type": "boolean"
... 必填                             → "required": ["参数名"]
Field(description="xxx")              → "description": "xxx"
Field(default=1)                      → 省略（默认值的参数不在 required 中）
```

### 2.4 最终 Schema 格式 —— 给 LLM 看的"说明书"
```python
{
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "读取文件的内容。使用场景：...",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件的完整路径"
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行号，从1开始"
                },
                "limit": {
                    "type": "integer", 
                    "description": "最大读取行数"
                },
                "encoding": {
                    "type": "string",
                    "description": "文件编码"
                }
            },
            "required": ["file_path"]   # 只file_path必填
        }
    }
}
```
LLM 看到后就知道：
- "有个 read_file 工具"
- "必须传 file_path 参数"
- "可以选填 offset、limit、encoding"

### 2.5 一句话总结

| 步骤 | 比喻 |
|------|------|
| 1. 工具注册 | 告诉系统"我有一个工具" |
| 2. Pydantic模型 | 定义工具的参数长什么样 |
| 3. 自动生成Schema | 自动转换成LLM能看懂的格式 |
| 4. 最终Schema | 给 LLM 的完整说明书 |

## 三、示例：list_directory 工具

### 3.1 Pydantic 模型（file_schema.py）

```python
class ListDirectoryInput(BaseModel):
    """list_directory 工具的输入参数"""
    dir_path: str = Field(
        description="目录的完整路径（必须是绝对路径，如 D:/项目代码）"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归列出所有子目录，默认为False（不递归）"
    )
    max_depth: int = Field(
        default=10,
        ge=1,
        le=50,
        description="最大递归深度，仅当 recursive=True 时有效，默认为10"
    )
```

### 3.2 工具注册（file_tools.py）

```python
@register_tool(
    name="list_directory",
    description="""列出指定目录中的所有文件和子目录。

使用场景：
- 当用户想要查看某个文件夹里有什么文件时使用此工具
- 当需要了解目录结构时使用
- 当需要获取文件列表进行进一步操作时使用

参数说明：
- dir_path: 目录的完整路径（必须是绝对路径，如 D:/项目代码）
- recursive: 是否递归列出子目录内容，默认为False
- max_depth: 最大递归深度，仅当 recursive=True 时有效

【重要】必须使用 dir_path 作为参数名""",
    input_model=ListDirectoryInput,
    examples=[
        {"dir_path": "C:/Users/用户名/Documents", "recursive": False},
        {"dir_path": "D:/项目代码", "recursive": True, "max_depth": 3}
    ]
)
async def list_directory(
    self,
    dir_path: str,
    recursive: bool = False,
    max_depth: int = 100000,
) -> Dict[str, Any]:
    """列出目录内容"""
    ...
```

### 3.3 最终生成的 Schema

```python
{
    "type": "function",
    "function": {
        "name": "list_directory",
        "description": "列出指定目录中的所有文件和子目录。\n\n使用场景：...\n\n参数说明：\n- dir_path: 目录的完整路径...\n- recursive: 是否递归...\n- max_depth: 最大递归深度...",
        "parameters": {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "目录的完整路径（必须是绝对路径，如 D:/项目代码）"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归列出所有子目录，默认为False（不递归）",
                    "default": False
                },
                "max_depth": {
                    "type": "integer",
                    "description": "最大递归深度，仅当 recursive=True 时有效，默认为10",
                    "default": 10
                }
            },
            "required": ["dir_path"]
        }
    }
}
```

---

## 四、工具注册流程图

```
┌─────────────────────────────────────────────────────────────┐
│                      定义 Pydantic 模型                      │
│   class ListDirectoryInput(BaseModel):                     │
│       dir_path: str = Field(...)  # 必填                   │
│       recursive: bool = Field(default=False)  # 可选        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    @register_tool 注册                      │
│   @register_tool(                                           │
│       name="list_directory",                                │
│       description="...",                                    │
│       input_model=ListDirectoryInput,                       │
│       examples=[...]                                        │
│   )                                                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│              自动生成 OpenAI 格式 Schema                     │
│   get_tools_schema_for_function_calling()                  │
│   → 输出给 LLM 的 tools 参数                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 五、定义一个 Function 的核心事项

### 5.1 什么是"定义"

**"定义"** = 在系统中**创建并注册**一个工具，让 LLM 能够发现并调用它。

核心动作：
1. 告诉系统工具的名称
2. 告诉系统工具的用途
3. 告诉系统工具需要什么参数
4. （可选）给出使用示例

### 5.2 定义核心事项总结

| 核心事项 | 说明 | 必须？ |
|---------|------|--------|
| **name** | 工具叫什么（LLM 通过此名称调用） | ✅ 必填 |
| **description** | 工具干什么用（告诉 LLM 何时使用） | ✅ 必填 |
| **parameters** | 工具需要什么参数（类型、必填/可选、说明） | ✅ 必填 |
| **examples** | 使用示例（帮助 LLM 理解参数格式） | ❌ 可选 |

### 5.3 定义流程

```
1. 定义 Pydantic 模型
   ↓
2. 使用 @register_tool 注册
   ↓
3. 自动生成 OpenAI 格式 Schema
   ↓
4. LLM 调用时使用
```

### 5.4 核心定义工作（name 确定后）

在 **name** 确定后，**定义一个 Function 的核心工作就是 2 件事**：

| 核心工作 | 说明 | 关键点 |
|----------|------|--------|
| **1. 写准确的 description** | 告诉 LLM 何时使用这个工具 | 使用场景、用途说明 |
| **2. 写完整和准确的 parameters** | 告诉 LLM 需要传什么参数 | 类型、必填/可选、参数说明 |

### 5.5 核心工作如何实现到 2.1-2.3 步骤中

| 核心工作 | 对应步骤 | 实现方式 |
|----------|----------|----------|
| **description** | 2.1 @register_tool | 在装饰器中通过 `description` 参数手动编写 |
| **parameters** | 2.2 Pydantic模型 | 通过 Pydantic 模型类定义参数（类型、必填/可选） |
| | 2.3 自动生成 | 通过 `model_json_schema()` 自动转换为 JSON Schema |

**实现流程**：
```
编写 description → @register_tool(description="...")
                    ↓
定义 parameters → Pydantic 模型类
                    ↓
自动生成 → model_json_schema() → 最终 parameters Schema
```

---

**更新后的总结**：

> **定义一个 Function = name + 准确的 description + 完整准确的 parameters**

（其中 name 确定后，核心就是 description 和 parameters）

---

**更新时间**: 2026-04-04 06:30:00
