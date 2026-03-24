# LLM工具调用参数命名规范 - 实现说明文档

**创建时间**: 2026-03-20 05:28:26
**版本**: v1.0
**编写人**: 小强
**文档类型**: 实现说明文档

---

## 1. 问题背景

### 1.1 问题描述

在文件操作Agent开发过程中，遇到LongCat模型返回参数名与系统预期不一致的问题：

| 问题 | 系统预期 | LongCat返回 |
|------|---------|------------|
| 参数名不一致 | `dir_path` | `directory_path` |
| 后果 | 工具调用失败 | 报错 |

这导致文件操作功能无法正常工作，用户体验受损。

### 1.2 临时解决方案及问题

**最初的临时解决方案**：在agent.py中添加参数映射代码

```python
# agent.py - 临时映射方案
elif action == "list_directory":
    if "path" in action_input and "dir_path" not in action_input:
        action_input["dir_path"] = action_input.pop("path")
```

**问题**：
1. 头疼医头，脚疼医脚
2. 每发现一个问题加一段映射代码
3. 不同LLM可能有不同变体（path/directory_path/dir_path）
4. 维护成本持续增加
5. 无法根本解决问题

### 1.3 问题根因分析

| 层级 | 问题 | 影响 |
|-----|------|------|
| **工具定义层** | description过于简单 | LLM不知道如何正确调用 |
| **Prompt层** | 没有参数命名规则 | LLM随意命名 |
| **执行层** | 依赖参数映射 | 治标不治本 |

---

## 2. 解决方案设计

### 2.1 设计原则

采用**三层防御策略**，从根本上解决LLM参数命名问题：

```
第一层：增强System Prompt（全局规则）
      ↓
第二层：详细工具Description（每个工具）
      ↓
第三层：添加Examples（正确用法示范）
```

### 2.2 方案选型

经过分析对比，决定采用以下技术方案：

| 组件 | 选择 | 理由 |
|------|------|------|
| **参数定义** | Pydantic模型 | 自动生成Schema，类型安全，已有依赖 |
| **装饰器** | 自定义register_tool | 支持Pydantic模型 |
| **白名单** | 动态生成 | 自动添加所有存在的盘符 |
| **示例** | input_examples | Claude官方推荐 |

### 2.3 技术方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| **Schema严格定义** | 结构保证 | 无法控制参数名 | OpenAI Structured Outputs |
| **Examples示例** | 明确用法 | 增加token消耗 | 所有LLM |
| **System Prompt规则** | 全局生效 | 可能被忽略 | 作为补充约束 |
| **后端参数映射** | 简单直接 | 维护成本高 | 临时方案（已废弃） |

---

## 3. 业界最佳实践研究

### 3.1 研究来源

| 来源 | 项目/文档 | 核心价值 |
|------|----------|---------|
| Anthropic官方 | Claude Tool Use Docs | input_examples规范 |
| Prefect | FastMCP | 装饰器自动生成Schema |
| MarcusJellinghaus | mcp_server_filesystem | 安全白名单机制 |
| LangChain | Tools | Pydantic模型定义参数 |
| mcp.pizza | mcp-filesystem | 大文件处理优化 |

### 3.2 Claude官方Tool Use最佳实践

**核心观点**：
> "JSON schemas define what's structurally valid, but can't express usage patterns"

翻译：JSON Schema只能定义结构有效性，但无法表达使用模式。

**解决方案**：使用 **input_examples** 来教LLM正确用法

**推荐做法**：
1. **Description要详细**（至少3-4句话）
   - 工具做什么
   - 何时使用
   - 每个参数的含义和对行为的影响

2. **使用input_examples展示正确用法**
   ```json
   {
     "name": "get_weather",
     "description": "Get the current weather...",
     "input_schema": {...},
     "input_examples": [
       {"location": "San Francisco, CA"},
       {"location": "Beijing, China", "unit": "celsius"}
     ]
   }
   ```

3. **参数命名一致性**
   - 相同概念的参数使用相同名称
   - 使用完整名称（如 `file_path` 而非 `path`）

### 3.3 FastMCP装饰器模式

**核心实现**：
```python
@mcp.tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file's contents.
    
    Args:
        path: Path to the file to read
        encoding: File encoding (default: utf-8)
    """
```

**优点**：
1. 装饰器自动从函数签名提取参数类型
2. 自动从docstring提取description
3. 自动生成JSON Schema

### 3.4 MarcusJellinghaus安全白名单机制

**安全验证实现**：
```python
def _is_path_allowed(self, path: str) -> bool:
    real_path = os.path.realpath(os.path.expanduser(path))
    return any(
        real_path.startswith(os.path.realpath(allowed))
        for allowed in self.allowed_directories
    )
```

**优点**：
1. 规范化路径（处理 `..`、`~` 等）
2. 前缀匹配判断是否在白名单内

---

## 4. tools.py 重写详解

### 4.1 文件结构

```
tools.py (约900行)
├── 第一部分：分页配置常量 (PAGE_SIZE, MAX_PAGE_SIZE)
├── 第二部分：动态白名单 (_get_default_allowed_paths)
├── 第三部分：Pydantic参数模型 (ReadFileInput, WriteFileInput, ...)
├── 第四部分：ToolDefinition类
├── 第五部分：工具注册表 (_TOOL_REGISTRY, register_tool)
├── 第六部分：FileTools类 (7个工具方法)
├── 第七部分：工具函数导出
├── 第八部分：统一返回格式辅助函数
└── 第九部分：分页支持函数
```

### 4.2 动态白名单实现

**代码位置**：第二部分（第30-55行）

```python
def _get_default_allowed_paths() -> List[Path]:
    """
    获取默认允许的路径列表
    
    【改进】动态添加所有存在的盘符
    2026-03-19 小强
    """
    paths = [
        Path.home(),  # 用户主目录
        Path("/tmp"),  # Linux临时目录
        Path("/var/tmp"),  # Linux临时目录
    ]
    
    # Windows盘符（A-J）
    if os.name == 'nt':
        for letter in 'ABCDEFGHIJ':
            drive = Path(f"{letter}:/")
            if drive.exists():
                paths.append(drive)
    
    return paths

ALLOWED_PATHS = _get_default_allowed_paths()
```

**改进点**：
| 旧实现 | 新实现 |
|-------|-------|
| 硬编码盘符 | 动态检测所有存在的盘符 |
| 可能遗漏D盘 | 自动包含所有可用盘符 |
| 需要手动维护 | 启动时自动生成 |

### 4.3 Pydantic参数模型

**代码位置**：第三部分（第58-145行）

共定义了7个Pydantic模型：

#### 4.3.1 ReadFileInput

```python
class ReadFileInput(BaseModel):
    """read_file 工具的输入参数"""
    file_path: str = Field(
        description="文件的完整路径（必须是绝对路径，如 C:/Users/用户名/Documents/file.txt）"
    )
    offset: int = Field(
        default=1,
        ge=1,
        description="起始行号，从1开始计数，默认为1"
    )
    limit: int = Field(
        default=2000,
        ge=1,
        le=10000,
        description="最大读取行数，默认为2000行，最大10000行"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码，默认为utf-8"
    )
```

**设计要点**：
- `ge=1` 约束offset最小值为1
- `le=10000` 约束limit最大值为10000
- description详细说明参数用途

#### 4.3.2 WriteFileInput

```python
class WriteFileInput(BaseModel):
    file_path: str = Field(description="文件的完整路径（必须是绝对路径）")
    content: str = Field(description="要写入文件的内容")
    encoding: str = Field(default="utf-8", description="文件编码")
```

#### 4.3.3 ListDirectoryInput

```python
class ListDirectoryInput(BaseModel):
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
    page_token: Optional[str] = Field(
        default=None,
        description="分页令牌，用于获取下一页结果，默认为None"
    )
    page_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="每页返回数量，默认为100，最大500"
    )
```

**关键设计**：
- `dir_path` 是必填参数（不是directory_path或path）
- `max_depth` 限制最大递归深度（防止无限递归）
- `page_size` 限制最大返回数量

#### 4.3.4 DeleteFileInput

```python
class DeleteFileInput(BaseModel):
    file_path: str = Field(description="要删除的文件或目录的完整路径")
    recursive: bool = Field(
        default=False,
        description="是否递归删除目录（目录非空时需要设为True）"
    )
```

#### 4.3.5 MoveFileInput

```python
class MoveFileInput(BaseModel):
    source_path: str = Field(description="源文件或目录的完整路径")
    destination_path: str = Field(description="目标路径（可以是新文件名或新目录位置）")
```

**关键设计**：
- 使用完整的 `source_path` 和 `destination_path`
- 避免使用 `src`、`dst` 等缩写

#### 4.3.6 SearchFilesInput

```python
class SearchFilesInput(BaseModel):
    pattern: str = Field(description="搜索内容的关键字或正则表达式")
    path: str = Field(default=".", description="搜索的起始目录")
    file_pattern: str = Field(
        default="*",
        description="文件名匹配模式，支持通配符"
    )
    use_regex: bool = Field(
        default=False,
        description="是否使用正则表达式搜索"
    )
    max_results: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="最大搜索结果数量"
    )
```

#### 4.3.7 GenerateReportInput

```python
class GenerateReportInput(BaseModel):
    output_dir: Optional[str] = Field(
        default=None,
        description="报告输出目录，默认为None"
    )
```

### 4.4 ToolDefinition类

**代码位置**：第四部分（第148-185行）

```python
class ToolDefinition:
    """
    工具定义类
    
    自动从Pydantic模型生成JSON Schema，并添加input_examples
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        input_model: type[BaseModel],
        examples: Optional[List[Dict[str, Any]]] = None
    ):
        self.name = name
        self.description = description
        self.input_model = input_model
        self.examples = examples or []
    
    def to_schema(self) -> Dict[str, Any]:
        """转换为JSON Schema格式"""
        schema = self.input_model.model_json_schema()
        return schema
    
    def to_mcp_format(self) -> Dict[str, Any]:
        """转换为MCP工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.to_schema(),
            "input_examples": self.examples
        }
```

**核心功能**：
1. `to_schema()` - 从Pydantic模型自动生成JSON Schema
2. `to_mcp_format()` - 生成完整的MCP工具定义格式

### 4.5 改进的装饰器

**代码位置**：第五部分（第188-240行）

```python
def register_tool(
    name: Optional[str] = None,
    description: str = "",
    input_model: Optional[type[BaseModel]] = None,
    examples: Optional[List[Dict[str, Any]]] = None
):
    """
    工具注册装饰器（改进版 - 使用Pydantic）
    
    【改进】2026-03-19 小强
    - 使用Pydantic模型自动生成Schema
    - 支持input_examples示例
    
    用法:
        @register_tool(
            name="list_directory",
            description="列出目录内容...",
            input_model=ListDirectoryInput,
            examples=[
                {"dir_path": "C:/Users/用户名/Documents"},
                {"dir_path": "D:/项目代码", "recursive": True}
            ]
        )
        async def list_directory(self, dir_path: str, ...):
            ...
    """
    def decorator(func):
        tool_name = name or func.__name__
        
        if input_model is not None:
            tool_def = ToolDefinition(
                name=tool_name,
                description=description or func.__doc__ or "",
                input_model=input_model,
                examples=examples
            )
        else:
            tool_def = None
        
        tool_info = {
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "definition": tool_def,
            "function": func,
            "input_model": input_model,
            "registered_at": datetime.now().isoformat()
        }
        _TOOL_REGISTRY[tool_name] = tool_info
        
        return func
    
    return decorator
```

**改进点**：
| 旧装饰器 | 新装饰器 |
|---------|---------|
| 只保存description | 保存完整ToolDefinition |
| 无Schema | 自动生成JSON Schema |
| 无examples | 支持input_examples |

### 4.6 路径验证改进

**代码位置**：FileTools类（第310-335行）

```python
def _validate_path(self, file_path: str) -> tuple[bool, Optional[str]]:
    """
    验证文件路径是否合法
    
    【改进】2026-03-19 小强
    - 使用 os.path.realpath 规范化路径
    - 处理 ~ 和 .. 等特殊路径
    - 前缀匹配判断
    """
    try:
        # 规范化路径：解析 ..、.、~
        real_path = Path(os.path.realpath(os.path.expanduser(file_path)))
        
        # 检查路径是否在白名单内
        for allowed in self.allowed_paths:
            allowed_real = Path(os.path.realpath(allowed))
            if str(real_path).startswith(str(allowed_real)):
                return True, None
        
        return False, f"路径 '{file_path}' 不在允许的操作范围内..."
    except Exception as e:
        return False, f"路径验证失败: {str(e)}"
```

**改进点**：
1. 使用 `os.path.realpath` 规范化路径
2. 使用 `os.path.expanduser` 处理 `~`
3. 使用前缀匹配而非精确匹配
4. 更友好的错误信息

### 4.7 search_files安全漏洞修复（P0）

**修复位置**：search_files方法开头（第700-715行）

```python
async def search_files(
    self,
    pattern: str,
    path: str = ".",
    file_pattern: str = "*",
    use_regex: bool = False,
    max_results: int = 1000
) -> Dict[str, Any]:
    """搜索文件内容"""
    # 【安全修复】验证搜索路径 - 2026-03-19 小强
    is_valid, error_msg = self._validate_path(path)
    if not is_valid:
        raw_result = {
            "success": False,
            "error": error_msg,
            "matches": []
        }
        return _to_unified_format(raw_result, "search_files")
    
    # ... 后续搜索逻辑
```

**问题**：
- 原代码中只有 `search_files` 没有路径验证
- 其他所有工具都有验证，唯独这个没有
- 这是一个严重的安全漏洞

**修复**：
- 在方法开头添加路径验证
- 如果路径不合法，直接返回错误

### 4.8 工具装饰器完整示例

**代码位置**：每个工具方法

#### list_directory示例

```python
@register_tool(
    name="list_directory",
    description="""列出指定目录中的所有文件和子目录。

使用场景：
- 当用户想要查看某个文件夹里有什么文件时使用此工具
- 当需要了解目录结构时使用
- 当需要获取文件列表进行进一步操作时使用
- 当用户说"查看D盘"、"列出目录"、"文件夹里有什么"时使用

参数说明：
- dir_path: 目录的完整路径（必须是绝对路径）
- recursive: 是否递归列出子目录内容
- max_depth: 最大递归深度
- page_token: 分页令牌
- page_size: 每页返回数量

【重要】必须使用 dir_path 作为参数名，不要使用 directory_path、path 或其他名称。
错误示例: {"directory_path": "..."} 或 {"path": "..."}
正确示例: {"dir_path": "D:/项目代码"} 或 {"dir_path": "C:/Users/用户名/Documents", "recursive": True}""",
    input_model=ListDirectoryInput,
    examples=[
        {
            "dir_path": "C:/Users/用户名/Documents",
            "recursive": False
        },
        {
            "dir_path": "D:/项目代码",
            "recursive": True,
            "max_depth": 3,
            "page_size": 100
        },
        {
            "dir_path": "C:/Users/用户名/Desktop",
            "recursive": False,
            "page_token": None,
            "page_size": 50
        }
    ]
)
async def list_directory(
    self,
    dir_path: str,
    recursive: bool = False,
    max_depth: int = 10,
    page_token: Optional[str] = None,
    page_size: int = 100
) -> Dict[str, Any]:
    """列出目录内容"""
    # 验证路径合法性
    is_valid, error_msg = self._validate_path(dir_path)
    if not is_valid:
        return _to_unified_format({
            "success": False,
            "error": error_msg,
            "entries": []
        }, "list_directory")
    
    # ... 实现逻辑
```

#### search_files示例

```python
@register_tool(
    name="search_files",
    description="""搜索文件名匹配特定模式的文件。

使用场景：
- 当用户想要在目录中搜索包含特定关键字的文件时使用此工具
- 当用户想要查找特定类型的文件时使用
- 当用户说"搜索文件"、"查找包含xxx的文件"时使用

参数说明：
- pattern: 搜索内容的关键字或正则表达式
- path: 搜索的起始目录，默认为当前目录
- file_pattern: 文件名匹配模式
- use_regex: 是否使用正则表达式搜索
- max_results: 最大搜索结果数量

【重要】必须使用 pattern 和 path 作为参数名。""",
    input_model=SearchFilesInput,
    examples=[
        {
            "pattern": "TODO",
            "path": "D:/项目代码",
            "file_pattern": "*.py",
            "use_regex": False,
            "max_results": 100
        },
        {
            "pattern": "config",
            "path": "C:/Users/用户名",
            "file_pattern": "*.json",
            "use_regex": False,
            "max_results": 50
        },
        {
            "pattern": "^class\\s+\\w+",
            "path": "D:/项目代码",
            "file_pattern": "*.py",
            "use_regex": True,
            "max_results": 200
        }
    ]
)
async def search_files(...):
```

---

## 5. prompts.py 增强详解

### 5.1 文件结构

```
prompts.py (约350行)
├── FileOperationPrompts类
│   ├── get_system_prompt()      【核心：增强版System Prompt】
│   ├── get_task_prompt()
│   ├── get_observation_prompt()
│   ├── get_available_tools_prompt()  【支持input_examples】
│   ├── get_rollback_instructions()
│   ├── get_safety_reminder()
│   └── get_parameter_reminder()   【新增：参数命名提醒】
└── TaskTemplates类（预定义任务模板）
```

### 5.2 增强版System Prompt

**代码位置**：get_system_prompt()方法

#### 5.2.1 参数命名规则（全局约束）

```
【IMPORTANT】Parameter Naming Rules - MUST follow these exactly:
- list_directory → use dir_path (NOT directory_path, NOT path)
- read_file → use file_path (NOT filepath, NOT path)
- write_file → use file_path (NOT filepath, NOT path)
- delete_file → use file_path (NOT filepath, NOT path)
- move_file → use source_path AND destination_path (NOT src, NOT dst, NOT source, NOT destination)
- search_files → use pattern AND path

【FORBIDDEN parameter names - DO NOT use】:
- ❌ directory_path (correct: dir_path)
- ❌ filepath (correct: file_path)
- ❌ src / source (correct: source_path)
- ❌ dst / dest / destination (correct: destination_path)
```

**设计要点**：
- 在最显眼的位置（工具列表之前）
- 使用【IMPORTANT】标记引起LLM注意
- 使用【FORBIDDEN】明确禁止的错误用法
- 提供正确的替代方案

#### 5.2.2 详细工具描述

每个工具都有3个部分的描述：

1. **使用场景**：说明何时应该调用此工具
2. **参数说明**：详细说明每个参数的作用
3. **【重要】约束**：强制要求使用正确的参数名

示例：
```
3. list_directory(dir_path, recursive=False, max_depth=10, page_size=100)
   List directory contents.
   - dir_path: Complete directory path (MUST use dir_path, NOT directory_path or path)
   - recursive: Whether to list subdirectories, default False
   - max_depth: Maximum recursion depth (only when recursive=True), default 10
   Example: {"dir_path": "D:/project/code", "recursive": True, "max_depth": 3}
   Common use: When user says "查看D盘", "列出目录", "文件夹里有什么"
```

#### 5.2.3 Tool Call Examples

**完整示例**（4个）：

```json
Example 1: List directory
{
    "thought": "User wants to see files in D drive root",
    "action": "list_directory",
    "action_input": {
        "dir_path": "D:/"  // ✅ CORRECT: uses dir_path
    }
}
// ❌ WRONG: {"directory_path": "D:/"} or {"path": "D:/"}

Example 2: Read file
{
    "thought": "User wants to read a config file",
    "action": "read_file",
    "action_input": {
        "file_path": "C:/Users/username/config.json"  // ✅ CORRECT
    }
}
// ❌ WRONG: {"filepath": "..."} or {"path": "..."}

Example 3: Search files
{
    "thought": "User wants to search for TODO comments in Python files",
    "action": "search_files",
    "action_input": {
        "pattern": "TODO",
        "path": "D:/project",
        "file_pattern": "*.py"
    }
}

Example 4: Move file
{
    "thought": "User wants to move file to new location",
    "action": "move_file",
    "action_input": {
        "source_path": "C:/old/file.txt",  // ✅ CORRECT
        "destination_path": "D:/new/file.txt"  // ✅ CORRECT
    }
}
// ❌ WRONG: {"src": "...", "dst": "..."}
```

**设计要点**：
- 使用完整的JSON格式（模拟真实调用）
- 使用 `// ✅ CORRECT` 和 `// ❌ WRONG` 标注
- 包含正确的参数名示例
- 包含错误的参数名警示

### 5.3 增强的get_available_tools_prompt

**功能**：动态生成工具列表Prompt，支持input_examples

```python
@staticmethod
def get_available_tools_prompt(tools: List[Dict[str, Any]]) -> str:
    """
    获取可用工具列表Prompt（增强版 - 支持input_examples）
    """
    if not tools:
        return "No tools available."
    
    tool_descriptions = []
    
    for tool in tools:
        name = tool.get("name", "unknown")
        description = tool.get("description", "No description")
        schema = tool.get("input_schema", {})
        examples = tool.get("input_examples", [])
        
        # 构建参数描述
        params = []
        for param_name, param_info in properties.items():
            # ... 参数构建逻辑
        
        # 构建示例
        example_str = ""
        if examples:
            example_str = f"\n  Examples:\n"
            for i, ex in enumerate(examples[:2], 1):
                example_str += f"    {i}. {ex}\n"
        
        tool_desc = f"""
{name}:
  Description: ...
  Parameters:
{chr(10).join(params)}
{example_str}"""
        
        tool_descriptions.append(tool_desc)
    
    return "Available Tools:\n" + "\n\n".join(tool_descriptions)
```

### 5.4 新增get_parameter_reminder方法

**功能**：独立的参数命名提醒Prompt

```python
@staticmethod
def get_parameter_reminder() -> str:
    """获取参数命名提醒Prompt"""
    return """【Parameter Naming Reminder】

Correct parameter names to use:
- list_directory: dir_path
- read_file: file_path
- write_file: file_path
- delete_file: file_path
- move_file: source_path, destination_path
- search_files: pattern, path

Common mistakes to avoid:
- ❌ directory_path (use: dir_path)
- ❌ filepath (use: file_path)
- ❌ src/dst (use: source_path/destination_path)
- ❌ path for read/write (use: file_path)"""
```

---

## 6. 生成的工具定义示例

### 6.1 list_directory完整定义

```json
{
  "name": "list_directory",
  "description": "列出指定目录中的所有文件和子目录。\n\n使用场景：\n- 当用户想要查看某个文件夹里有什么文件时使用此工具\n- 当需要了解目录结构时使用\n- 当需要获取文件列表进行进一步操作时使用\n- 当用户说\"查看D盘\"、\"列出目录\"、\"文件夹里有什么\"时使用\n\n参数说明：\n- dir_path: 目录的完整路径（必须是绝对路径，如 D:/项目代码 或 C:/Users/用户名/Documents）\n- recursive: 是否递归列出子目录内容，默认为False（不递归）\n- max_depth: 最大递归深度，仅当 recursive=True 时有效，默认为10\n- page_token: 分页令牌，用于获取下一页结果\n- page_size: 每页返回数量，默认为100\n\n【重要】必须使用 dir_path 作为参数名，不要使用 directory_path、path 或其他名称。\n错误示例: {\"directory_path\": \"...\"} 或 {\"path\": \"...\"}\n正确示例: {\"dir_path\": \"D:/项目代码\"} 或 {\"dir_path\": \"C:/Users/用户名/Documents\", \"recursive\": True}",
  "input_schema": {
    "description": "list_directory 工具的输入参数",
    "properties": {
      "dir_path": {
        "description": "目录的完整路径（必须是绝对路径，如 D:/项目代码）",
        "title": "Dir Path",
        "type": "string"
      },
      "recursive": {
        "default": false,
        "description": "是否递归列出所有子目录，默认为False（不递归）",
        "title": "Recursive",
        "type": "boolean"
      },
      "max_depth": {
        "default": 10,
        "description": "最大递归深度，仅当 recursive=True 时有效，默认为10",
        "maximum": 50,
        "minimum": 1,
        "title": "Max Depth",
        "type": "integer"
      },
      "page_token": {
        "anyOf": [
          { "type": "string" },
          { "type": "null" }
        ],
        "default": null,
        "description": "分页令牌，用于获取下一页结果，默认为None",
        "title": "Page Token"
      },
      "page_size": {
        "default": 100,
        "description": "每页返回数量，默认为100，最大500",
        "maximum": 500,
        "minimum": 1,
        "title": "Page Size",
        "type": "integer"
      }
    },
    "required": ["dir_path"],
    "title": "ListDirectoryInput",
    "type": "object"
  },
  "input_examples": [
    {
      "dir_path": "C:/Users/用户名/Documents",
      "recursive": false
    },
    {
      "dir_path": "D:/项目代码",
      "recursive": true,
      "max_depth": 3,
      "page_size": 100
    },
    {
      "dir_path": "C:/Users/用户名/Desktop",
      "recursive": false,
      "page_token": null,
      "page_size": 50
    }
  ]
}
```

---

## 7. 测试验证

### 7.1 单元测试结果

| 测试文件 | 结果 | 通过数 | 总数 |
|---------|------|-------|------|
| test_tools.py | ✅ PASSED | 28 | 28 |

### 7.2 测试覆盖的工具

| 工具 | 测试用例数 |
|------|----------|
| read_file | 5个 |
| write_file | 3个 |
| list_directory | 4个 |
| delete_file | 4个 |
| move_file | 3个 |
| search_files | 5个 |
| generate_report | 2个 |
| FileTools集成 | 2个 |

### 7.3 Schema生成验证

```python
# 验证代码
from app.services.file_operations.tools import get_registered_tools

tools = get_registered_tools()
# 输出：共 7 个工具

# 检查每个工具
for tool in tools:
    print(f"【{tool['name']}】")
    print(f"  参数数量: {len(tool['input_schema']['properties'])}")
    print(f"  必填参数: {tool['input_schema'].get('required', [])}")
    print(f"  示例数量: {len(tool['input_examples'])}")
```

**输出结果**：

| 工具 | 参数数量 | 必填参数 | 示例数量 |
|------|---------|---------|---------|
| read_file | 4 | file_path | 3 |
| write_file | 3 | file_path, content | 2 |
| list_directory | 5 | dir_path | 3 |
| delete_file | 2 | file_path | 2 |
| move_file | 2 | source_path, destination_path | 2 |
| search_files | 5 | pattern | 3 |
| generate_report | 1 | 无 | 2 |

---

## 8. 改进对比

### 8.1 tools.py改进对比

| 方面 | 旧实现 | 新实现 |
|------|-------|-------|
| 参数定义 | docstring | Pydantic模型 |
| Schema生成 | 无 | 自动生成 |
| 白名单 | 硬编码 | 动态生成 |
| search_files安全 | 无验证 | ✅ 有验证 |
| input_examples | 无 | 每个工具2-3个 |
| 代码行数 | 1017行 | ~900行 |

### 8.2 prompts.py改进对比

| 方面 | 旧实现 | 新实现 |
|------|-------|-------|
| 参数规则 | 无 | ✅ 全局规则+FORBIDDEN |
| 工具描述 | 一句话 | 3-5句话+使用场景 |
| 示例 | 无 | ✅ 4个完整示例 |
| 路径格式 | 无 | ✅ 明确说明 |

---

## 9. 预期效果

### 9.1 短期效果

| 效果 | 说明 |
|------|------|
| ✅ LongCat返回正确参数名 | 使用dir_path而非directory_path |
| ✅ 不再需要代码映射 | 根本解决问题 |
| ✅ 其他LLM也能遵守规则 | System Prompt约束 |

### 9.2 长期价值

| 价值 | 说明 |
|------|------|
| ✅ 减少参数映射代码维护 | 不需要维护映射逻辑 |
| ✅ 提高工具调用成功率 | LLM理解正确用法 |
| ✅ 建立统一的参数命名规范 | 标准化设计 |

### 9.3 安全性提升

| 方面 | 改进 |
|------|------|
| ✅ search_files安全漏洞 | 已修复（添加路径验证） |
| ✅ 动态白名单 | 自动包含所有可用盘符 |
| ✅ 路径规范化 | 使用realpath处理特殊路径 |

---

## 10. 提交记录

| 项目 | 内容 |
|------|------|
| **commit信息** | feat: 重写tools.py和prompts.py - 解决LLM参数命名问题 - 小强-2026-03-20 |
| **修改文件** | tools.py, prompts.py |
| **测试结果** | test_tools.py 28/28 通过 |
| **版本** | v0.5.4 → v0.5.5 |

---

**文档结束**

**编写时间**: 2026-03-20 05:28:26
**编写人**: 小强
**版本**: v1.0
