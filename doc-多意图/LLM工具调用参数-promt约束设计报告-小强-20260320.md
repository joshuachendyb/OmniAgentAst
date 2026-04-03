# LLM工具调用参数命名规范设计报告

**创建时间**: 2026-03-19 22:57:55
**版本**: v1.0
**编写人**: 小强
**文档类型**: 设计报告

---

## 1. 研究背景与目标

### 1.1 研究背景

在文件操作Agent开发过程中，遇到LongCat模型返回参数名与系统预期不一致的问题：
- **系统预期**: `dir_path`
- **LongCat返回**: `directory_path`
- **结果**: 工具调用失败

这促使我们研究如何让LLM按照我们定义的参数名称返回，而不是在代码层面做映射。

### 1.2 研究目标

1. 了解业界如何解决LLM工具调用参数命名不一致问题
2. 分析我们当前系统的实现方式
3. 设计一套完整的解决方案，确保LLM返回正确的参数名

---

## 2. 业界最佳实践研究

### 2.1 Claude官方文档核心观点

**来源**: Anthropic官方文档 - Advanced Tool Use (https://www.anthropic.com/engineering/advanced-tool-use)

**核心洞见**:

> "JSON schemas define what's structurally valid, but can't express usage patterns"

翻译：JSON Schema只能定义结构有效性，但无法表达使用模式。

**具体问题**：
| Schema能定义 | Schema无法定义 |
|-------------|--------------|
| 参数类型 | 何时包含可选参数 |
| 必填字段 | 参数组合的合理性 |
| 枚举值 | API期望的命名约定 |

**解决方案**: 使用 **Tool Use Examples**（示例）来教LLM正确用法

### 2.2 Claude官方推荐做法

**来源**: Claude API Docs - Tool Use (https://platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)

**最佳实践**:

1. **Description要详细** (至少3-4句话)
   - 工具做什么
   - 何时使用
   - 每个参数的含义和对行为的影响

2. **使用input_examples展示正确用法**
   ```json
   {
     "name": "get_weather",
     "description": "Get the current weather in a given location...",
     "input_schema": {...},
     "input_examples": [
       {"location": "San Francisco, CA"},
       {"location": "Beijing, China", "unit": "celsius"}
     ]
   }
   ```

3. **工具名称要有意义且一致**
   - 使用有描述性的名称
   - 统一命名风格

### 2.3 OpenAI官方推荐做法

**来源**: OpenAI API Docs + Structured Outputs

**Structured Outputs特性**:
- 保证输出严格符合Schema
- 但仍然需要清晰的description引导

**Function Calling Best Practices**:
1. 工具description要清晰描述用途和参数
2. 使用consistent的参数命名约定
3. 考虑在system prompt中添加全局规则

### 2.4 业界经验总结

| 方案 | 优点 | 缺点 | 适用场景 |
|-----|------|------|---------|
| **Schema严格定义** | 结构保证 | 无法控制参数名 | OpenAI Structured Outputs |
| **Examples示例** | 明确用法 | 增加token消耗 | 所有LLM |
| **System Prompt规则** | 全局生效 | 可能被忽略 | 作为补充约束 |
| **后端参数映射** | 简单直接 | 维护成本高 | 临时方案 |

---

## 3. 我们系统的现状分析

### 3.1 当前工具定义

**文件**: `backend/app/services/file_operations/tools.py`

**工具列表**:

| 工具名 | 功能 | 参数定义方式 |
|-------|------|------------|
| read_file | 读取文件 | @register_tool + docstring |
| write_file | 写入文件 | @register_tool + docstring |
| list_directory | 列出目录 | @register_tool + docstring |
| delete_file | 删除文件 | @register_tool + docstring |
| move_file | 移动文件 | @register_tool + docstring |
| search_files | 搜索文件 | @register_tool + docstring |

### 3.2 当前System Prompt

**文件**: `backend/app/services/file_operations/prompts.py`

**当前内容**:
```
You are a file management assistant. You help users organize, analyze, and manage files and directories.

You have access to the following tools:
1. read_file - Read file content with optional offset and limit
2. write_file - Write content to a file
3. list_directory - List directory contents
4. delete_file - Delete a file (with automatic backup)
5. move_file - Move or rename a file
6. search_files - Search files by content pattern
...
```

**问题**:
1. ❌ 只有工具名和一句话描述
2. ❌ 没有明确参数名称要求
3. ❌ 没有Examples示范
4. ❌ 没有全局参数命名规则

### 3.3 当前Agent处理方式

**文件**: `backend/app/services/file_operations/agent.py`

**参数处理逻辑**:
```python
elif action == "list_directory":
    # 处理 path 和 dir_path 参数名不一致问题
    if "path" in action_input and "dir_path" not in action_input:
        action_input["dir_path"] = action_input.pop("path")
```

**问题**:
1. ❌ 头疼医头，脚疼医脚
2. ❌ 每发现一个问题加一段映射代码
3. ❌ 不同LLM可能有不同变体（path/directory_path/dir_path）
4. ❌ 维护成本持续增加

### 3.4 问题根因分析

| 层级 | 问题 | 影响 |
|-----|------|------|
| **工具定义层** | description过于简单 | LLM不知道如何正确调用 |
| **Prompt层** | 没有参数命名规则 | LLM随意命名 |
| **执行层** | 依赖参数映射 | 治标不治本 |

---

## 4. 解决方案设计

### 4.1 解决方案概述

采用**三层防御策略**：

```
第一层：增强System Prompt（全局规则）
     ↓
第二层：详细工具Description（每个工具）
     ↓
第三层：添加Examples（正确用法示范）
```

### 4.2 第一层：增强System Prompt

**目标**: 在全局层面告诉LLM参数命名规则

**新增内容**:

```
【重要】参数命名规则：
- list_directory 必须使用 dir_path，不是 directory_path 或 path
- read_file 必须使用 file_path，不是 filepath 或 path
- write_file 必须使用 file_path，不是 filepath 或 path
- delete_file 必须使用 file_path，不是 filepath 或 path
- move_file 必须使用 source_path 和 destination_path
- search_files 必须使用 pattern 和 path

禁止使用以下参数名：
- ❌ directory_path (应使用 dir_path)
- ❌ filepath (应使用 file_path)
- ❌ src 或 source (应使用 source_path)
- ❌ dst 或 dest (应使用 destination_path)
```

### 4.3 第二层：详细工具Description

**目标**: 每个工具的description都要详细说明参数

**以list_directory为例**:

**当前**:
```python
@register_tool(name="list_directory", description="列出目录内容，支持过滤和排序")
```

**改进后**:
```python
@register_tool(
    name="list_directory",
    description="""列出指定目录的内容和文件列表
    
    使用场景：
    - 当用户想要查看某个文件夹里有什么文件时
    - 当需要了解目录结构时
    - 当需要获取文件列表进行进一步操作时
    
    必需参数：
    - dir_path: 目录路径（必须是完整路径，如 C:/Users/xxx/Documents）
    
    可选参数：
    - recursive: 是否递归列出子目录，默认False
    - max_depth: 最大递归深度，默认10（仅recursive=True时有效）
    
    【重要】必须使用 dir_path 作为参数名，不要使用 directory_path 或 path"""
)
```

### 4.4 第三层：添加Examples

**目标**: 通过示例让LLM理解正确用法

**实现方式**: 在System Prompt中添加工具调用示例

```
【工具调用示例】

示例1：列出目录
{
    "thought": "用户想查看D盘根目录下的文件列表",
    "action": "list_directory",
    "action_input": {
        "dir_path": "D:/"  // 注意：必须使用 dir_path，不是 directory_path
    }
}

示例2：读取文件
{
    "thought": "用户想读取一个配置文件查看内容",
    "action": "read_file",
    "action_input": {
        "file_path": "C:/Users/xxx/config.json"  // 注意：必须使用 file_path
    }
}

示例3：搜索文件
{
    "thought": "用户想搜索包含关键词的文件",
    "action": "search_files",
    "action_input": {
        "pattern": "TODO",  // 搜索内容
        "path": "."  // 搜索路径，默认当前目录
    }
}
```

### 4.5 完整改进后的System Prompt结构

```
你是一个文件管理助手，帮助用户组织、分析和管理文件和目录。

【重要】参数命名规则：
（全局规则，禁止使用其他参数名）
- list_directory → dir_path
- read_file → file_path  
- write_file → file_path
- delete_file → file_path
- move_file → source_path + destination_path
- search_files → pattern + path

【工具列表】

1. read_file(file_path, offset=0, limit=2000, encoding="utf-8")
   读取文件内容
   - file_path: 文件完整路径（必须使用此参数名）
   - offset: 起始行号
   - limit: 最大读取行数
   
2. write_file(file_path, content, encoding="utf-8")
   写入内容到文件
   - file_path: 文件完整路径（必须使用此参数名）
   - content: 要写入的内容
   
3. list_directory(dir_path, recursive=False, max_depth=10)
   列出目录内容
   - dir_path: 目录完整路径（必须使用此参数名，不是 directory_path）
   - recursive: 是否递归
   
... 其他工具类似 ...

【工具调用示例】
（展示正确的参数命名）
...
```

---

## 5. 工具参数完整汇总表

| 工具 | 参数 | 类型 | 必填 | 重要约定 |
|------|-----|------|-----|---------|
| **read_file** | file_path | str | ✅ | 必须用 `file_path`，不是 `path` |
| | offset | int | ❌ | 默认0 |
| | limit | int | ❌ | 默认2000 |
| | encoding | str | ❌ | 默认utf-8 |
| **write_file** | file_path | str | ✅ | 必须用 `file_path` |
| | content | str | ✅ | 要写入的内容 |
| | encoding | str | ❌ | 默认utf-8 |
| **list_directory** | dir_path | str | ✅ | 必须用 `dir_path`，不是 `directory_path` 或 `path` |
| | recursive | bool | ❌ | 默认False |
| | max_depth | int | ❌ | 默认10 |
| **delete_file** | file_path | str | ✅ | 必须用 `file_path` |
| | recursive | bool | ❌ | 默认False |
| **move_file** | source_path | str | ✅ | 源文件路径 |
| | destination_path | str | ✅ | 目标路径 |
| **search_files** | pattern | str | ✅ | 搜索内容 |
| | path | str | ❌ | 搜索路径，默认"." |
| | file_pattern | str | ❌ | 文件匹配，默认"*" |
| | use_regex | bool | ❌ | 默认False |
| | max_results | int | ❌ | 默认1000 |

---

## 6. 实施计划

### 6.1 修改文件清单

| 序号 | 文件 | 修改内容 | 优先级 |
|-----|------|---------|-------|
| 1 | prompts.py | 增强System Prompt，添加全局规则 | 高 |
| 2 | tools.py | 增强每个工具的description | 高 |

**文件位置**:
- prompts.py: `backend/app/services/file_operations/prompts.py`
- tools.py: `backend/app/services/file_operations/tools.py`

### 6.2 修改顺序

1. 先修改 `prompts.py` 的 `get_system_prompt()`
2. 再修改 `tools.py` 中每个工具的 `@register_tool` description

### 6.3 验证方法

1. 使用LongCat模型测试 "查看D盘文件"
2. 检查返回的action_input中的参数名是否为 `dir_path`
3. 测试其他工具是否也遵守参数命名规则

---

## 7. 预期效果

### 7.1 短期效果

- ✅ LongCat返回正确参数名 `dir_path`
- ✅ 不再需要代码层面的参数映射
- ✅ 其他LLM也能遵守规则

### 7.2 长期价值

- ✅ 减少参数映射代码维护
- ✅ 提高工具调用成功率
- ✅ 建立统一的参数命名规范

---

## 8. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|-----|------|------|------|
| LLM仍然不遵守规则 | 中 | 中 | 保留参数映射作为兜底 |
| Prompt过长影响性能 | 低 | 低 | 精简描述，保持简洁 |
| 不同LLM行为不一致 | 中 | 中 | 针对不同LLM调整规则 |

---

## 9. tools.py 代码质量深度分析

**分析时间**: 2026-03-19 23:10:00
**分析文件**: `backend/app/services/file_operations/tools.py`
**代码行数**: 1007行

### 9.1 问题汇总表

| 序号 | 问题类型 | 严重程度 | 问题描述 | 位置 | 影响 |
|-----|---------|---------|---------|------|------|
| 1 | **安全漏洞** | 🔴 P0-紧急 | `search_files`没有路径验证 | 第698行 | 任何路径都可访问 |
| 2 | **参数Schema缺失** | 🔴 P0-紧急 | 装饰器没有保存参数定义 | 第66-74行 | LLM无法知道参数类型 |
| 3 | **description太简单** | 🟡 P1-高 | 只有一句话，无法引导LLM | 所有工具 | LLM随意命名参数 |
| 4 | **白名单不完整** | 🟡 P1-高 | ALLOWED_PATHS没有D盘 | 第119-125行 | D盘访问被拒绝 |
| 5 | **代码重复** | 🟡 P1-高 | PAGE_SIZE定义两次 | 第35/977行 | 维护混乱 |
| 6 | **返回数据不一致** | 🟡 P1-高 | 各工具返回字段名不同 | 各工具 | LLM解析困难 |
| 7 | **缺少参数类型注解** | 🟡 P1-高 | 装饰器不保存参数schema | 第66-74行 | 无法生成tool定义 |
| 8 | **注释标注不一致** | 🟢 P2-中 | 修复标注格式不统一 | 各处 | 维护困难 |

### 9.2 问题1：search_files 安全漏洞 🔴 P0

**问题位置**: 第698行

**问题代码**:
```python
# 第676-684行
@register_tool(name="search_files", description="搜索文件内容，支持正则表达式", category="search")
async def search_files(
    self,
    pattern: str,
    path: str = ".",
    file_pattern: str = "*",
    use_regex: bool = False,
    max_results: int = 1000
) -> Dict[str, Any]:
    """
    搜索文件内容
    ...
    """
    search_path = Path(path)  # ← 没有验证路径是否合法！
    
    try:
        if not search_path.exists():
            ...
```

**问题分析**:
- `read_file`、`write_file`、`list_directory`、`delete_file`、`move_file` 都在开头调用了 `self._validate_path(path)`
- 只有 `search_files` 没有调用！
- 这意味着LLM可以搜索任何路径，包括系统敏感目录

**对比其他工具**:
```python
# read_file - 有验证 ✅
is_valid, error_msg = self._validate_path(file_path)
if not is_valid:
    return _to_unified_format({...}, "read_file")

# search_files - 没有验证 ❌
search_path = Path(path)  # 直接使用，没有验证！
```

**必须修复**: 在 `search_files` 开头添加路径验证

---

### 9.3 问题2：装饰器缺少参数Schema 🔴 P0

**问题位置**: 第47-82行

**当前代码**:
```python
def register_tool(name: Optional[str] = None, description: str = "", category: str = "file"):
    def decorator(func):
        tool_name = name or func.__name__
        tool_info = {
            "name": tool_name,
            "description": description or func.__doc__ or "",  # ← 只有description
            "category": category,
            "function": func,
            "registered_at": datetime.now().isoformat()
            # ← 缺少 parameters/schema 定义！
        }
        _TOOL_REGISTRY[tool_name] = tool_info
        return func
    return decorator
```

**问题分析**:
- 当前 `tool_info` 只保存了 `description`
- 没有保存参数的 `JSON Schema`
- 当 Agent 需要生成给 LLM 的 tool 定义时，无法提供参数类型信息

**Claude官方要求**:
```json
{
  "name": "get_weather",
  "description": "...",
  "input_schema": {
    "type": "object",
    "properties": {
      "location": {"type": "string", "description": "..."}
    },
    "required": ["location"]
  }
}
```

**必须修复**: 装饰器需要支持参数Schema定义

---

### 9.4 问题3：工具description太简单 🟡 P1

**问题位置**: 所有 `@register_tool` 装饰器

**当前代码**:
```python
@register_tool(name="list_directory", description="列出目录内容，支持过滤和排序", category="file")
@register_tool(name="read_file", description="读取文件内容，支持指定偏移量和行数限制", category="file")
@register_tool(name="write_file", description="写入文件内容，自动创建目录", category="file")
```

**问题分析**:
- description只有1句话
- 没有说明每个参数的作用
- 没有告诉LLM必须使用特定参数名
- 没有示例

**Claude官方要求**:
> "Description should be at least 3-4 sentences explaining what the tool does, when to use it, and what each parameter means."

**必须修复**: 详细描述每个参数及命名要求

---

### 9.5 问题4：ALLOWED_PATHS白名单不完整 🟡 P1

**问题位置**: 第119-125行

**当前代码**:
```python
ALLOWED_PATHS = [
    Path.home(),  # 用户主目录
    Path("/tmp"),  # Linux临时目录
    Path("/var/tmp"),  # Linux临时目录
    Path(os.environ.get("TEMP", "C:/Windows/Temp")),  # Windows临时目录
    Path(os.environ.get("TMP", "/tmp")),  # 通用临时目录
]
```

**问题分析**:
- 没有包含 `D:\` 盘符
- 没有包含其他常用盘符（A-J盘）
- 用户想访问自己的项目目录可能被拒绝

**建议修复**:
```python
ALLOWED_PATHS = [
    Path.home(),  # 用户主目录
    Path("/tmp"),
    Path("/var/tmp"),
    Path(os.environ.get("TEMP", "C:/Windows/Temp")),
    Path(os.environ.get("TMP", "/tmp")),
    # 添加常用盘符
    Path("D:/"),
    Path("E:/"),  # 如果存在
    Path("F:/"),  # 如果存在
    # 或者更灵活的方式：允许用户主目录下的所有路径
]
```

---

### 9.6 问题5：代码重复 🟡 P1

**问题位置**: 第35行和第977行

**重复代码**:
```python
# 第35行
PAGE_SIZE = 100  # 每页返回数量

# 第977行（文件末尾）
PAGE_SIZE = 100  # 每页返回数量 ← 重复定义！
MAX_PAGE_SIZE = 500  # 最大单页数量 ← 也重复定义
```

**问题分析**:
- 两个地方定义了相同的常量
- 可能导致维护混乱
- 应该只在一处定义

**建议修复**: 删除第977行的重复定义

---

### 9.7 问题6：返回数据结构不一致 🟡 P1

**问题分析**:

| 工具 | 返回字段 | 用途 |
|------|---------|------|
| read_file | `content` | 文件内容 |
| list_directory | `entries` | 文件列表 |
| search_files | `matches` | 搜索结果 |
| write_file | `file_path` | 文件路径 |
| delete_file | `deleted_path` | 删除路径 |
| move_file | `source`, `destination` | 源/目标 |

**问题**:
- 虽然外层有统一格式 `{status, summary, data, retry_count}`
- 但 `data` 内部结构不统一
- LLM需要理解不同工具返回不同字段

**建议**: 保持现状，因为不同工具确实返回不同数据，但需要确保description中说明

---

### 9.8 问题7：缺少完整参数类型定义 🟡 P1

**问题分析**:
- 装饰器 `@register_tool` 只接受 `description` 字符串
- 无法传递参数类型信息
- 需要扩展装饰器支持 `parameters` 参数

**建议改进**:
```python
@register_tool(
    name="list_directory",
    description="""...""",
    parameters={
        "type": "object",
        "properties": {
            "dir_path": {
                "type": "string",
                "description": "目录路径（必须使用 dir_path，不是 directory_path）"
            },
            "recursive": {
                "type": "boolean",
                "description": "是否递归列出子目录"
            }
        },
        "required": ["dir_path"]
    }
)
```

---

### 9.9 代码结构总结

**当前架构**:
```
tools.py (1007行)
├── 全局常量和装饰器 (1-106行)
│   ├── _TOOL_REGISTRY
│   ├── register_tool() 装饰器
│   ├── get_registered_tools()
│   └── get_tool()
├── FileTools 类 (108-855行)
│   ├── 6个工具方法
│   ├── _validate_path()
│   ├── _get_next_sequence()
│   └── 其他辅助方法
├── 辅助函数 (858-1007行)
│   ├── get_file_tools()
│   ├── _generate_summary()
│   ├── _to_unified_format()
│   ├── encode_page_token()
│   └── decode_page_token()
```

**问题总结**:
1. FileTools类方法过多（6个工具+2个辅助方法）
2. 装饰器功能不完整
3. 缺少工具Schema定义
4. 部分安全检查缺失

---

## 10. 完整修复计划

### 10.1 修复优先级

| 优先级 | 问题 | 修复内容 |
|-------|------|---------|
| **P0-紧急** | search_files安全漏洞 | 添加路径验证 |
| **P0-紧急** | 装饰器缺少参数Schema | 扩展装饰器支持parameters |
| **P1-高** | description太简单 | 详细描述每个参数 |
| **P1-高** | ALLOWED_PATHS不完整 | 添加常用盘符 |
| **P1-高** | 代码重复 | 删除重复定义 |
| **P2-中** | 注释标注不一致 | 统一注释格式 |

### 10.2 修复文件清单

| 序号 | 文件 | 修复内容 |
|-----|------|---------|
| 1 | tools.py | 修复所有P0/P1问题 |
| 2 | prompts.py | 增强System Prompt |
| 3 | agent.py | 可选：保留参数映射作为兜底 |

### 10.3 修复后预期效果

| 效果 | 说明 |
|------|------|
| ✅ 安全性提升 | search_files有路径验证 |
| ✅ LLM理解更好 | 详细description + 参数Schema |
| ✅ 参数命名正确 | System Prompt规则 + Examples |
| ✅ 访问范围扩大 | 白名单包含常用盘符 |
| ✅ 代码质量提高 | 消除重复代码 |

---

## 11. 业界最佳实践综合分析

**更新时间**: 2026-03-19 23:36:12
**更新人**: 小强

### 11.1 业界优秀项目汇总

| 项目 | 语言 | 特点 | 参考价值 |
|------|------|------|---------|
| **FastMCP/Prefect** | Python | 官方MCP SDK，装饰器自动生成Schema | ⭐⭐⭐⭐⭐ |
| **MarcusJellinghaus/mcp_server_filesystem** | Python | 安全验证完善，白名单机制 | ⭐⭐⭐⭐⭐ |
| **mcp.pizza/mcp-filesystem** | TypeScript | 大文件优化，流式处理 | ⭐⭐⭐⭐ |
| **cyanheads/filesystem-mcp-server** | TypeScript | 详细Schema定义 | ⭐⭐⭐⭐ |
| **LangChain tools** | Python | Pydantic模型定义参数 | ⭐⭐⭐⭐⭐ |
| **Anthropic Claude** | - | 官方Tool Use最佳实践 | ⭐⭐⭐⭐⭐ |

---

### 11.2 FastMCP装饰器模式分析

**来源**: https://github.com/PrefectHQ/fastmcp

**核心实现**:
```python
from fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
async def read_file(path: str, encoding: str = "utf-8") -> str:
    """Read a file's contents.
    
    Args:
        path: Path to the file to read
        encoding: File encoding (default: utf-8)
    """
    with open(path) as f:
        return f.read()
```

**优点**:
1. 装饰器自动从函数签名提取参数类型
2. 自动从docstring提取description
3. 自动生成JSON Schema
4. 类型提示自动转换为Schema类型

**我们可以借鉴**:
- 改进 `@register_tool` 装饰器，支持从类型注解自动生成Schema
- 使用 `inspect` 模块提取函数签名信息

---

### 11.3 MarcusJellinghaus安全白名单机制

**来源**: https://github.com/MarcusJellinghaus/mcp_server_filesystem

**安全验证实现**:
```python
class FileSystemServer:
    def __init__(self, allowed_directories: List[str]):
        self.allowed_directories = [
            os.path.realpath(d) for d in allowed_directories
        ]
    
    def _is_path_allowed(self, path: str) -> bool:
        """验证路径是否在白名单内"""
        real_path = os.path.realpath(os.path.expanduser(path))
        return any(
            real_path.startswith(os.path.realpath(allowed))
            for allowed in self.allowed_directories
        )
    
    def read_file(self, path: str) -> str:
        if not self._is_path_allowed(path):
            raise ValueError(f"Path {path} is not in allowed directories")
        # ... 读取文件逻辑
```

**优点**:
1. 规范化路径（处理 `..`、`~` 等）
2. 前缀匹配判断是否在白名单内
3. 对每个操作都进行验证

**我们可以借鉴**:
- 在 `_validate_path` 中使用 `os.path.realpath` 规范化路径
- 使用前缀匹配代替精确匹配
- 对所有工具（包括 `search_files`）都进行验证

---

### 11.4 mcp.pizza大文件处理优化

**来源**: https://github.com/mcp.pizza/mcp-filesystem

**大文件处理策略**:
```python
async def search_files(self, path: str, pattern: str, max_results: int = 100):
    """搜索文件，支持大目录优化"""
    
    # 1. 先检查路径是否存在
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path not found: {path}")
    
    # 2. 使用 generator 惰性加载，避免一次性加载所有结果
    results = []
    for root, dirs, files in os.walk(path):
        for filename in files:
            if pattern_match(filename, pattern):
                results.append(...)
                if len(results) >= max_results:
                    return results
    
    return results
```

**优化点**:
1. 使用 `os.walk()` 惰性遍历
2. 设置 `max_results` 限制返回数量
3. 发现足够结果立即返回

---

### 11.5 cyanheads详细Schema定义

**来源**: https://github.com/cyanheads/filesystem-mcp-server

**详细Schema示例**:
```typescript
const readFileSchema = {
  name: "read_file",
  description: "Read the complete contents of a file from the file system",
  inputSchema: {
    type: "object",
    properties: {
      path: {
        type: "string",
        description: "The fully qualified path to the file (e.g., /Users/name/project/file.txt)",
      },
      position: {
        type: "integer",
        description: "The byte offset to start reading from (default: 0)",
        minimum: 0,
      },
      length: {
        type: "integer",
        description: "Maximum number of bytes to read (default: all bytes)",
        minimum: 1,
      },
    },
    required: ["path"],
  },
};
```

**优点**:
1. 每个参数都有详细description
2. 使用 `minimum`、`maximum` 约束数值范围
3. 标注 `required` 必填参数
4. 提供使用示例（路径格式）

---

### 11.6 LangChain Pydantic模型方式

**来源**: LangChain Tools

**Pydantic定义方式**:
```python
from pydantic import BaseModel, Field

class ReadFileInput(BaseModel):
    """Input for read_file tool."""
    
    path: str = Field(
        description="The fully qualified path to the file to read"
    )
    line_start: Optional[int] = Field(
        default=None,
        description="The line number to start reading from (0-indexed)"
    )
    line_end: Optional[int] = Field(
        default=None,
        description="The line number to stop reading at (exclusive)"
    )

def read_file(file_path: str, line_start: int = None, line_end: int = None):
    """Read file contents with optional line range."""
    ...
```

**优点**:
1. 使用Pydantic定义输入模型
2. Field支持详细description
3. 类型注解自动推断
4. 可自动生成JSON Schema

**我们可以借鉴**:
- 为每个工具定义Pydantic Input模型
- 使用模型自动生成Schema

---

### 11.7 Anthropic Claude官方Tool Use最佳实践

**来源**: https://docs.anthropic.com/claude/docs/tool-use

**核心建议**:

1. **Description编写规范**:
```
Good description:
"Read the complete contents of a file. Use this when you need to see 
the full content of a file. The path must be absolute, not relative."

Bad description:
"Reads a file"
```

2. **使用input_examples**:
```json
{
  "name": "read_file",
  "description": "Read file contents...",
  "input_schema": {...},
  "input_examples": [
    {"path": "/Users/name/project/file.txt"},
    {"path": "C:/Users/name/config.json", "line_start": 0, "line_end": 100}
  ]
}
```

3. **参数命名一致性**:
- 相同概念的参数使用相同名称
- 使用完整名称（如 `file_path` 而非 `path`）

---

### 11.8 综合最佳实践清单

基于以上分析，总结出**必须借鉴的最佳实践**：

#### 11.8.1 装饰器改进

| 当前问题 | 改进方案 | 优先级 |
|---------|---------|-------|
| 不提取类型注解 | 使用 `inspect` 提取函数签名生成Schema | P0 |
| 不解析docstring | 从docstring提取参数description | P1 |

#### 11.8.2 安全验证改进

| 当前问题 | 改进方案 | 优先级 |
|---------|---------|-------|
| search_files无验证 | 所有工具添加路径验证 | P0 |
| 路径规范化不足 | 使用 `os.path.realpath` 规范化 | P1 |
| 白名单不含D盘 | 动态添加可用盘符 | P1 |

#### 11.8.3 Description改进

| 当前问题 | 改进方案 | 优先级 |
|---------|---------|-------|
| 描述太简单 | 每个参数至少3-5句话 | P0 |
| 无示例 | 添加 `input_examples` | P1 |
| 无使用场景 | 说明何时应该调用此工具 | P1 |

#### 11.8.4 Schema定义改进

| 当前问题 | 改进方案 | 优先级 |
|---------|---------|-------|
| 无Schema | 添加JSON Schema定义 | P0 |
| 无参数类型 | 使用Python类型注解 | P1 |
| 无约束 | 添加 `minimum`、`max_length` 等约束 | P2 |

---

### 11.9 tools.py重写指导方案

#### 11.9.1 新的文件结构

```python
# tools.py 重写结构
"""
文件操作工具模块 - 重写版本

参考了以下最佳实践：
- FastMCP装饰器模式
- MarcusJellinghaus安全白名单
- mcp.pizza大文件处理
- LangChain Pydantic模型
- Claude官方Tool Use规范
"""

import os
import re
import json
import inspect
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, get_type_hints
from datetime import datetime

# ============================================================
# 第一部分：常量定义
# ============================================================

PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

# 动态构建白名单，包含用户主目录和常用盘符
def _get_default_allowed_paths() -> List[Path]:
    """获取默认允许的路径列表"""
    paths = [
        Path.home(),  # 用户主目录
        Path("/tmp"),
        Path("/var/tmp"),
    ]
    
    # Windows盘符
    if os.name == 'nt':
        for letter in 'ABCDEFGHIJ':
            drive = Path(f"{letter}:/")
            if drive.exists():
                paths.append(drive)
    
    return paths

ALLOWED_PATHS = _get_default_allowed_paths()

# ============================================================
# 第二部分：改进的装饰器
# ============================================================

class ToolParameter:
    """工具参数定义"""
    def __init__(
        self,
        name: str,
        type: str,
        description: str,
        required: bool = True,
        default: Any = None,
        **kwargs
    ):
        self.name = name
        self.type = type
        self.description = description
        self.required = required
        self.default = default
        self.extra = kwargs

class ToolDefinition:
    """工具定义"""
    def __init__(
        self,
        name: str,
        description: str,
        parameters: List[ToolParameter],
        examples: Optional[List[Dict]] = None
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.examples = examples or []
    
    def to_schema(self) -> Dict[str, Any]:
        """转换为JSON Schema格式"""
        properties = {}
        required = []
        
        for param in self.parameters:
            prop = {
                "type": param.type,
                "description": param.description
            }
            # 添加额外约束
            prop.update(param.extra)
            properties[param.name] = prop
            
            if param.required:
                required.append(param.name)
        
        schema = {
            "type": "object",
            "properties": properties
        }
        if required:
            schema["required"] = required
        
        return schema
    
    def to_mcp_format(self) -> Dict[str, Any]:
        """转换为MCP工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.to_schema(),
            "input_examples": self.examples
        }


def register_tool(
    name: Optional[str] = None,
    description: str = "",
    parameters: Optional[List[ToolParameter]] = None,
    examples: Optional[List[Dict]] = None
):
    """
    改进的装饰器，支持参数Schema定义
    
    用法示例:
    @register_tool(
        name="list_directory",
        description="列出目录中的所有文件和子目录...",
        parameters=[
            ToolParameter("dir_path", "string", "目录的完整路径...", required=True),
            ToolParameter("recursive", "boolean", "是否递归列出子目录...", required=False, default=False),
        ],
        examples=[
            {"dir_path": "C:/Users/用户名/Documents"},
            {"dir_path": "D:/项目代码", "recursive": True}
        ]
    )
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        
        # 如果没有提供parameters，尝试从函数签名自动提取
        auto_parameters = parameters
        if auto_parameters is None:
            auto_parameters = _extract_parameters_from_signature(func)
        
        tool_def = ToolDefinition(
            name=tool_name,
            description=description or func.__doc__ or "",
            parameters=auto_parameters,
            examples=examples
        )
        
        tool_info = {
            "name": tool_name,
            "definition": tool_def,
            "function": func,
            "registered_at": datetime.now().isoformat()
        }
        _TOOL_REGISTRY[tool_name] = tool_info
        return func
    return decorator


def _extract_parameters_from_signature(func: Callable) -> List[ToolParameter]:
    """从函数签名自动提取参数信息"""
    params = []
    sig = inspect.signature(func)
    type_hints = get_type_hints(func)
    
    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue
        
        # 获取类型
        py_type = type_hints.get(param_name, str)
        schema_type = _python_type_to_json_type(py_type)
        
        # 判断是否必填
        required = param.default is inspect.Parameter.empty
        
        # 获取默认值
        default = param.default if not required else None
        
        params.append(ToolParameter(
            name=param_name,
            type=schema_type,
            description=f"参数 {param_name}",  # 需要从docstring提取
            required=required,
            default=default
        ))
    
    return params


def _python_type_to_json_type(py_type) -> str:
    """Python类型转换为JSON Schema类型"""
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
        Any: "any"
    }
    return type_map.get(py_type, "string")


# ============================================================
# 第三部分：工具注册表
# ============================================================

_TOOL_REGISTRY: Dict[str, Dict] = {}


def get_registered_tools() -> List[Dict[str, Any]]:
    """获取所有注册的工具"""
    return [
        info["definition"].to_mcp_format()
        for info in _TOOL_REGISTRY.values()
    ]


def get_tool(name: str) -> Optional[Dict]:
    """获取指定工具"""
    return _TOOL_REGISTRY.get(name)


# ============================================================
# 第四部分：FileTools类（重写版）
# ============================================================

class FileTools:
    """文件操作工具类"""
    
    def __init__(self, allowed_paths: Optional[List[Path]] = None):
        self.allowed_paths = allowed_paths or ALLOWED_PATHS
        self._sequence = 0
    
    def _validate_path(self, path: str) -> tuple[bool, Optional[str]]:
        """
        验证路径是否在白名单内
        
        改进点:
        1. 使用 os.path.realpath 规范化路径
        2. 处理 ~ 和 .. 等特殊路径
        3. 前缀匹配判断
        """
        try:
            # 规范化路径
            real_path = Path(os.path.realpath(os.path.expanduser(path)))
            
            # 检查是否在白名单内
            for allowed in self.allowed_paths:
                allowed_real = Path(os.path.realpath(allowed))
                if str(real_path).startswith(str(allowed_real)):
                    return True, None
            
            return False, f"路径不在允许范围内: {path}"
        except Exception as e:
            return False, f"路径验证失败: {str(e)}"
    
    def _get_next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence
    
    # ============================================================
    # 工具1: list_directory
    # ============================================================
    @register_tool(
        name="list_directory",
        description="""列出指定目录中的所有文件和子目录。

        使用场景：
        - 当用户想要查看某个文件夹里有什么文件时使用
        - 当需要了解目录结构时使用
        - 当需要获取文件列表进行进一步操作时使用

        参数说明：
        - dir_path: 目录的完整路径（必须是绝对路径，如 C:/Users/用户名/Documents）
        - recursive: 是否递归列出子目录内容，默认为False

        【重要】必须使用 dir_path 作为参数名，不要使用 directory_path、path 或其他名称。
        错误示例: {"directory_path": "..."} 或 {"path": "..."}
        正确示例: {"dir_path": "C:/Users/用户名/Documents"}""",
        parameters=[
            ToolParameter("dir_path", "string", 
                "目录的完整路径（必须使用 dir_path，不是 directory_path 或 path）",
                required=True),
            ToolParameter("recursive", "boolean",
                "是否递归列出所有子目录，默认为False（不递归）",
                required=False, default=False),
            ToolParameter("max_depth", "integer",
                "最大递归深度，仅当 recursive=True 时有效，默认10",
                required=False, default=10),
        ],
        examples=[
            {"dir_path": "C:/Users/用户名/Documents"},
            {"dir_path": "D:/项目代码", "recursive": True, "max_depth": 3},
            {"dir_path": "C:/Users/用户名/Desktop", "recursive": False}
        ]
    )
    async def list_directory(
        self,
        dir_path: str,
        recursive: bool = False,
        max_depth: int = 10
    ) -> Dict[str, Any]:
        """列出目录内容"""
        # 路径验证
        is_valid, error_msg = self._validate_path(dir_path)
        if not is_valid:
            return self._error_result(error_msg, "list_directory")
        
        # ... 实现逻辑 ...
        
    # ============================================================
    # 工具2: read_file
    # ============================================================
    @register_tool(
        name="read_file",
        description="""读取文件的内容。

        使用场景：
        - 当用户想要查看文件内容时使用
        - 当需要读取配置文件、日志文件等时使用

        参数说明：
        - file_path: 文件的完整路径（必须是绝对路径）
        - offset: 起始行号，从0开始，默认为0
        - limit: 最大读取行数，默认为2000

        【重要】必须使用 file_path 作为参数名，不要使用 filepath、path 或其他名称。""",
        parameters=[
            ToolParameter("file_path", "string",
                "文件的完整路径（必须使用 file_path，不是 filepath 或 path）",
                required=True),
            ToolParameter("offset", "integer",
                "起始行号，从0开始计数，默认为0",
                required=False, default=0),
            ToolParameter("limit", "integer",
                "最大读取行数，默认为2000行",
                required=False, default=2000),
        ],
        examples=[
            {"file_path": "C:/Users/用户名/config.json"},
            {"file_path": "D:/项目代码/README.md", "offset": 0, "limit": 100}
        ]
    )
    async def read_file(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000
    ) -> Dict[str, Any]:
        """读取文件内容"""
        # 路径验证
        is_valid, error_msg = self._validate_path(file_path)
        if not is_valid:
            return self._error_result(error_msg, "read_file")
        
        # ... 实现逻辑 ...
    
    # ... 其他工具类似 ...
    
    # ============================================================
    # 工具6: search_files (修复版)
    # ============================================================
    @register_tool(
        name="search_files",
        description="""搜索文件名匹配特定模式的文件。

        使用场景：
        - 当用户想要查找特定类型的文件时使用
        - 当用户想要在目录中搜索文件时使用

        参数说明：
        - pattern: 搜索模式，支持通配符（* 匹配任意字符）
        - path: 搜索的起始目录，默认为当前目录 "."
        - file_pattern: 文件名匹配模式，默认为 "*"（匹配所有文件）
        - max_results: 最大返回结果数，默认为1000

        【重要】必须使用 pattern 和 path 作为参数名。""",
        parameters=[
            ToolParameter("pattern", "string",
                "搜索内容的关键字或模式",
                required=True),
            ToolParameter("path", "string",
                "搜索的起始目录，默认为当前目录",
                required=False, default="."),
            ToolParameter("file_pattern", "string",
                "文件名匹配模式，默认为 *（匹配所有文件）",
                required=False, default="*"),
            ToolParameter("max_results", "integer",
                "最大返回结果数，超过此数量将截断",
                required=False, default=1000),
        ],
        examples=[
            {"pattern": "TODO", "path": "."},
            {"pattern": "config", "path": "C:/项目", "file_pattern": "*.json", "max_results": 50}
        ]
    )
    async def search_files(
        self,
        pattern: str,
        path: str = ".",
        file_pattern: str = "*",
        max_results: int = 1000
    ) -> Dict[str, Any]:
        """搜索文件"""
        # 【修复】添加路径验证！
        is_valid, error_msg = self._validate_path(path)
        if not is_valid:
            return self._error_result(error_msg, "search_files")
        
        # ... 实现逻辑 ...


# ============================================================
# 第五部分：辅助函数
# ============================================================

def get_file_tools(allowed_paths: Optional[List[Path]] = None) -> FileTools:
    """获取FileTools实例"""
    return FileTools(allowed_paths=allowed_paths)


def _to_unified_format(
    data: Any,
    tool_name: str,
    status: str = "success",
    summary: Optional[str] = None
) -> Dict[str, Any]:
    """统一返回格式"""
    return {
        "status": status,
        "summary": summary or _generate_summary(tool_name, data),
        "data": data,
        "retry_count": 0
    }


def _generate_summary(tool_name: str, data: Any) -> str:
    """生成摘要信息"""
    # ... 实现 ...


def _error_result(error_msg: str, tool_name: str) -> Dict[str, Any]:
    """错误结果"""
    return _to_unified_format(
        None, tool_name, "error", f"操作失败: {error_msg}"
    )
```

---

### 11.10 prompts.py增强版

```python
def get_system_prompt() -> str:
    """生成增强版的System Prompt"""
    
    return """你是一个专业的文件管理助手，帮助用户组织、分析和管理文件与目录。

【重要】参数命名规则（必须严格遵守）：
- list_directory → dir_path（不是 directory_path 或 path）
- read_file → file_path（不是 filepath 或 path）
- write_file → file_path（不是 filepath 或 path）
- delete_file → file_path（不是 filepath 或 path）
- move_file → source_path + destination_path（不是 src/dst）
- search_files → pattern + path（搜索内容和起始目录）

【禁止使用的参数名】：
- ❌ directory_path（正确：dir_path）
- ❌ filepath（正确：file_path）
- ❌ src / source（正确：source_path）
- ❌ dst / dest（正确：destination_path）

【可用工具】：

1. read_file(file_path, offset=0, limit=2000)
   读取文件内容
   - file_path: 文件完整路径（必须用此参数名）
   - offset: 起始行号（从0开始）
   - limit: 最大读取行数

2. write_file(file_path, content)
   写入内容到文件
   - file_path: 文件完整路径（必须用此参数名）
   - content: 要写入的内容

3. list_directory(dir_path, recursive=False, max_depth=10)
   列出目录内容
   - dir_path: 目录完整路径（必须用此参数名，不是 directory_path）
   - recursive: 是否递归子目录
   - max_depth: 最大递归深度

4. delete_file(file_path, recursive=False)
   删除文件或目录
   - file_path: 文件完整路径（必须用此参数名）

5. move_file(source_path, destination_path)
   移动或重命名文件
   - source_path: 源文件路径
   - destination_path: 目标路径

6. search_files(pattern, path=".", file_pattern="*", max_results=1000)
   搜索文件
   - pattern: 搜索内容
   - path: 搜索起始目录
   - file_pattern: 文件名匹配模式

【工具调用示例】：

示例1：列出目录
{
    "thought": "用户想查看D盘根目录下的文件列表",
    "action": "list_directory",
    "action_input": {
        "dir_path": "D:/"  // ✅ 正确：使用 dir_path
    }
}
// ❌ 错误：使用 directory_path 或 path

示例2：读取文件
{
    "thought": "用户想读取配置文件",
    "action": "read_file",
    "action_input": {
        "file_path": "C:/Users/用户名/config.json"  // ✅ 正确
    }
}
// ❌ 错误：使用 filepath 或 path

示例3：搜索文件
{
    "thought": "用户想搜索包含关键词的文件",
    "action": "search_files",
    "action_input": {
        "pattern": "TODO",
        "path": "."  // ✅ 正确
    }
}

【路径格式要求】：
- Windows: C:/Users/用户名/... 或 C:\\Users\\用户名\\...
- Linux/Mac: /home/用户名/...
- 禁止使用相对路径（如 ./file.txt）
- 禁止使用 ~ 代替用户主目录

"""
```

---

### 11.11 实施检查清单

重写tools.py和prompts.py时的检查项：

#### 11.11.1 装饰器检查

- [ ] `@register_tool` 是否支持 `parameters` 参数？
- [ ] 是否能从函数签名自动提取类型？
- [ ] 是否生成了完整的JSON Schema？
- [ ] 是否有 `input_examples`？

#### 11.11.2 安全检查

- [ ] 所有工具是否都调用了 `_validate_path`？
- [ ] `search_files` 是否添加了路径验证？
- [ ] 路径是否使用 `os.path.realpath` 规范化？
- [ ] 白名单是否包含常用盘符？

#### 11.11.3 Description检查

- [ ] 每个工具的description是否至少3-5句话？
- [ ] 是否说明了使用场景？
- [ ] 是否说明了每个参数的作用？
- [ ] 是否有【重要】标注禁止的参数名？

#### 11.11.4 Schema检查

- [ ] 是否有完整的 `input_schema`？
- [ ] 参数类型是否正确？
- [ ] 是否标注了 `required` 参数？
- [ ] 是否有 `minimum`、`max_length` 等约束？

---

**第11章完成**

---

**报告结束**

**编写时间**: 2026-03-19 22:57:55
**更新说明**:
- 2026-03-19 23:10:00 小强 追加第9章 tools.py代码质量深度分析
- 2026-03-19 23:36:12 小强 追加第11章 业界最佳实践综合分析
**版本**: v1.1
