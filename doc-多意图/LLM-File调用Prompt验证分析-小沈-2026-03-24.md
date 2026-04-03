# ReAct File调用Prompt验证分析文档

**创建时间**: 2026-03-24 13:22:40
**版本**: v1.0
**编写人**: 小沈
**文档类型**: 验证分析报告

---

## 1. 检查目的

基于小强文档《LLM工具调用参数-prompt约束设计报告》第3章的问题分析，检查当前系统是否仍存在问题。

---

## 2. 小强第3章问题分析回顾

### 2.1 三个问题层级

| 层级 | 小强分析的问题 |
|------|--------------|
| **3.1 工具定义层** | description过于简单，LLM不知道如何正确调用 |
| **3.2 Prompt层** | 没有参数命名规则，LLM随意命名 |
| **3.3 执行层** | 依赖参数映射，治标不治本 |

### 2.2 问题根因

```
第一层：工具定义层 → description过于简单
第二层：Prompt层 → 没有参数命名规则
第三层：执行层 → 依赖参数映射
```

---

## 3. 当前系统检查结果

### 3.1 检查时间

2026-03-24 13:22:40

### 3.2 检查结果汇总

| 层级 | 小强分析的问题 | 当前状态 | 说明 |
|------|--------------|---------|------|
| **3.1 工具定义层** | description过于简单 | ✅ 已改进 | 使用Pydantic模型，有详细description和examples |
| **3.2 Prompt层** | 没有参数命名规则 | ✅ 已改进 | file_prompts.py第35-47行有完整规则 |
| **3.3 执行层** | 依赖参数映射 | ❌ **仍存在** | tool_executor.py第93-123行仍有大量映射代码 |

---

## 4. 小强第4章解决方案设计检查

### 4.1 检查目的

对照小强文档第4章的解决方案设计，检查当前代码是否按设计实现。

### 4.2 三层防御策略对比

| 层级 | 小强设计建议 | 当前实现 | 状态 |
|------|-------------|---------|------|
| **第一层** | 增强System Prompt（全局规则） | file_prompts.py 第35-47行 | ✅ 已实现 |
| **第二层** | 详细工具Description | file_tools.py list_directory description | ✅ 已实现 |
| **第三层** | 添加Examples（正确用法示范） | Prompt中工具调用示例 + input_examples | ✅ 已实现 |

### 4.3 第一层：增强System Prompt ✅

**小强建议**（第4.2节）：
```
【重要】参数命名规则：
- list_directory 必须使用 dir_path，不是 directory_path 或 path
- read_file 必须使用 file_path，不是 filepath 或 path
...
禁止使用以下参数名：
- ❌ directory_path (应使用 dir_path)
...
```

**当前实现**（file_prompts.py 第35-47行）：
```python
【IMPORTANT】Parameter Naming Rules - MUST follow these exactly:
- list_directory → use dir_path (NOT directory_path, NOT path)
- read_file → use file_path (NOT filepath, NOT path)
...

【FORBIDDEN parameter names - DO NOT use】:
- ❌ directory_path (correct: dir_path)
- ❌ filepath (correct: file_path)
...
```

**结论**：✅ 完全实现

### 4.4 第二层：详细工具Description ✅

**小强建议**（第4.3节）：
```python
@register_tool(
    name="list_directory",
    description="""列出指定目录的内容和文件列表
    
    使用场景：
    - 当用户想要查看某个文件夹里有什么文件时
    ...
    
    【重要】必须使用 dir_path 作为参数名，不要使用 directory_path 或 path"""
)
```

**当前实现**（file_tools.py 第610-629行）：
```python
@register_tool(
    name="list_directory",
    description="""列出指定目录中的所有文件和子目录。

    使用场景：
    - 当用户想要查看某个文件夹里有什么文件时使用此工具
    ...
    
    【重要】必须使用 dir_path 作为参数名，不要使用 directory_path、path 或其他名称。
    错误示例: {"directory_path": "..."} 或 {"path": "..."}
    正确示例: {"dir_path": "D:/项目代码"} ..."""
)
```

**结论**：✅ 完全实现，且更详细

### 4.5 第三层：添加Examples ✅

**小强建议**（第4.4节）：
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
```

**当前实现**（file_prompts.py 第101-110行）：
```python
【Tool Call Examples - Follow this format exactly】:

Example 1: List directory
{
    "thought": "User wants to see files in D drive root",
    "action": "list_directory",
    "action_input": {
        "dir_path": "D:/"  // ✅ CORRECT: uses dir_path
    }
}
// ❌ WRONG: {"directory_path": "D:/"} or {"path": "D:/"}
```

**额外实现**：工具定义中也有 input_examples：
```python
examples=[
    {
        "dir_path": "C:/Users/用户名/Documents",
        "recursive": False
    },
    ...
]
```

**结论**：✅ 完全实现，且更丰富（Prompt示例 + 工具input_examples）

---

## 5. 执行层检查 ❌ 仍存在问题

### 5.1 检查文件

- `backend/app/services/agent/tool_executor.py`

### 5.2 检查结果

第93-123行仍有大量参数映射代码：

```python
# 第93-96行: read_file
if "path" in params and "file_path" not in params:
    params["file_path"] = params.pop("path")

# 第98-102行: list_directory
if "path" in params and "dir_path" not in params:
    params["dir_path"] = params.pop("path")

# 第104-115行: move_file
if "source" in params and "source_path" not in params:
    params["source_path"] = params.pop("source")
if "src" in params and "source_path" not in params:
    params["source_path"] = params.pop("src")
if "destination" in params and "destination_path" not in params:
    params["destination_path"] = params.pop("destination")
if "dest" in params and "destination_path" not in params:
    params["destination_path"] = params.pop("dest")
if "target" in params and "destination_path" not in params:
    params["destination_path"] = params.pop("target")

# 第117-119行: search_files
if "path" not in params:
    params["path"] = "."

# 第121-123行: generate_report
if "output" in params and "output_dir" not in params:
    params["output_dir"] = params.pop("output")
```

### 5.3 问题分析

这正是小强文档第1.2节所说的"头疼医头，脚疼医脚"问题：

| 问题 | 说明 |
|------|------|
| 头疼医头，脚疼医脚 | 每发现一个问题加一段映射代码 |
| 维护成本高 | 不同LLM可能有不同参数变体 |
| 治标不治本 | 无法根本解决参数命名问题 |

---

## 6. 结论与建议

### 6.1 第4章设计检查结论

| 层级 | 小强建议 | 当前状态 |
|------|---------|---------|
| **第一层** | 增强System Prompt | ✅ 完全实现 |
| **第二层** | 详细工具Description | ✅ 完全实现 |
| **第三层** | 添加Examples | ✅ 完全实现 |

### 6.2 结论

| 层级 | 状态 | 说明 |
|------|------|------|
| 工具定义层 | ✅ 已解决 | Pydantic模型 + 详细description + examples |
| Prompt层 | ✅ 已解决 | 完整的参数命名规则 + FORBIDDEN列表 |
| 执行层 | ❌ 遗留问题 | 仍有大量参数映射代码 |

### 6.3 建议方案

| 方案 | 做法 | 风险 |
|------|------|------|
| **激进方案** | 删除执行层参数映射代码，让LLM严格遵守Prompt规则 | 可能导致部分调用失败 |
| **保守方案** | 保留映射代码作为兜底，同时优化Prompt | 维护成本高但风险低 |

### 6.3 推荐做法

考虑到 Prompt 层已经规范了参数命名规则，建议：

1. **短期**：保留映射代码作为兜底
2. **长期**：监控 LLM 返回的参数名，逐步删除不需要的映射
3. **验证**：在测试环境中验证激进方案的可行性

---

## 7. 执行层参数映射问题解决方案

### 7.1 问题现状

**文件**: `backend/app/services/agent/tool_executor.py` 第93-123行

**问题代码**:
```python
# read_file: path → file_path
if "path" in params and "file_path" not in params:
    params["file_path"] = params.pop("path")

# list_directory: path → dir_path
if "path" in params and "dir_path" not in params:
    params["dir_path"] = params.pop("path")

# move_file: source/src/destination/dest/target → 标准名
if "source" in params and "source_path" not in params:
    params["source_path"] = params.pop("source")
# ... 等等

# search_files: 默认 path
if "path" not in params:
    params["path"] = "."

# generate_report: output → output_dir
if "output" in params and "output_dir" not in params:
    params["output_dir"] = params.pop("output")
```

### 7.2 根本原因

小强文档第1.2节指出：
> 头疼医头，脚疼医脚，每发现一个问题加一段映射代码，不同LLM可能有不同参数变体，维护成本持续增加。

### 7.3 解决方案

#### 方案一：渐进式删除映射（推荐）

**思路**：既然 Prompt 层已经规范了参数命名规则，可以逐步删除不再需要的映射代码。

**实施步骤**：
1. **监控阶段**：记录 LLM 返回的实际参数名，统计各参数名的使用频率
2. **分析阶段**：如果某个"错误"参数名长期没有出现，标记为可删除
3. **删除阶段**：逐步删除不再需要的映射代码

**优点**：风险可控，可回滚
**缺点**：需要较长时间验证

#### 方案二：统一Response Parser校验（替代方案）

**思路**：在 LLM Response 解析层做参数名统一转换，而不是在执行层做。

**实施位置**：
- `backend/app/services/agent/tool_parser.py` - 解析 LLM Response 时做转换
- 或者 `backend/app/services/agent/agent.py` - 统一做参数名标准化

**优点**：集中处理，代码更清晰
**缺点**：仍是治标不治本

#### 方案三：严格要求 LLM（激进方案）

**思路**：删除所有映射代码，让 LLM 严格遵守 Prompt 中的参数命名规则。

**实施**：
```python
# 直接删除 tool_executor.py 中的参数映射代码
# 如果 LLM 返回的参数名不正确，直接报错
```

**优点**：根本解决问题，维护成本低
**缺点**：可能导致部分调用失败，需要 LLM 配合

### 7.4 推荐实施路径

1. **第一步**：在 tool_executor.py 中添加日志，记录每次参数映射的情况
   ```python
   if "path" in params and "file_path" not in params:
       logger.warning(f"Parameter mapping used: path -> file_path for {action}")
       params["file_path"] = params.pop("path")
   ```

2. **第二步**：运行一段时间后，统计映射使用频率

3. **第三步**：根据统计结果，逐步删除使用频率为0的映射

4. **第四步**：最终验证激进方案的可行性

### 7.5 快速修复建议（可选）

如果希望快速改善现状，可以：

1. **保留必要映射**：只保留 `path` → `file_path`/`dir_path` 这种常见错误
2. **删除冗余映射**：删除 `src`/`dest`/`target` 等不太可能出现的映射
3. **添加注释**：在每个映射处标注为什么需要这个映射

---

## 8. 小强第5章（prompts.py增强）实现检查

### 8.1 文件结构

| 小强建议 | 当前代码 | 状态 |
|---------|---------|------|
| FileOperationPrompts类 | file_prompts.py 第26行 | ✅ |
| get_system_prompt() | 第29行 | ✅ |
| get_task_prompt() | 第176行 | ✅ |
| get_observation_prompt() | 第207行 | ✅ |
| get_available_tools_prompt() | 第241行 | ✅ |
| get_rollback_instructions() | 第301行 | ✅ |
| get_safety_reminder() | 第316行 | ✅ |
| get_parameter_reminder() | 第326行 | ✅ |
| TaskTemplates类 | 第346行 | ✅ |

### 8.2 增强版System Prompt

| 小强建议 | 当前代码 | 状态 |
|---------|---------|------|
| 参数命名规则（全局约束） | 第35-47行 | ✅ |
| 详细工具描述 | 第51-97行 | ✅ |
| Tool Call Examples | 第101-165行 | ✅ |

### 8.3 get_available_tools_prompt

| 小强建议 | 当前代码 | 状态 |
|---------|---------|------|
| 动态生成工具列表 | 第241-300行 | ✅ |
| 支持input_examples | 第266行 | ✅ |

### 8.4 get_parameter_reminder

| 小强建议 | 当前代码 | 状态 |
|---------|---------|------|
| 独立的参数命名提醒 | 第326-342行 | ✅ |

### 8.5 检查结论

✅ **第5章完全实现**

---

## 10. 第6章检查结果 - 工具定义示例

### 10.1 检查内容

对照小强文档第6章，检查生成的list_directory工具定义是否完整实现。

### 10.2 检查结果

| 检查项 | 小强文档要求 | 实际实现 | 状态 |
|--------|-------------|---------|------|
| **name** | list_directory | list_directory | ✅ |
| **description** | 3-5句话详细描述+使用场景 | ✅ 完整实现（第515-532行） | ✅ |
| **参数说明** | dir_path, recursive, max_depth, page_token, page_size | ✅ 完整实现 | ✅ |
| **【重要】约束** | 必须使用dir_path | ✅ 第530行明确约束 | ✅ |
| **错误示例** | directory_path, path | ✅ 第531行明确标注 | ✅ |
| **正确示例** | dir_path: "D:/项目代码" | ✅ 第532行 | ✅ |
| **input_schema** | 完整JSON Schema | ✅ ListDirectoryInput生成 | ✅ |
| **input_examples** | 3个示例 | ✅ 第534-551行 | ✅ |

### 10.3 list_directory实现验证

**代码位置**: `backend/app/services/tools/file/file_tools.py` 第513-560行

**实现要点**:
```python
@register_tool(
    name="list_directory",
    description="""列出指定目录中的所有文件和子目录。

使用场景：...（4个场景）
参数说明：...（5个参数）
【重要】必须使用 dir_path 作为参数名，不要使用 directory_path、path 或其他名称。
错误示例: {"directory_path": "..."} 或 {"path": "..."}
正确示例: {"dir_path": "D:/项目代码"}""",
    input_model=ListDirectoryInput,
    examples=[
        {"dir_path": "C:/Users/用户名/Documents", "recursive": False},
        {"dir_path": "D:/项目代码", "recursive": True, "max_depth": 3, "page_size": 100},
        {"dir_path": "C:/Users/用户名/Desktop", "recursive": False, "page_token": None, "page_size": 50}
    ]
)
```

### 10.4 结论

✅ **第6章检查通过** - list_directory工具定义与文档要求完全一致。

---

## 11. 第7章检查结果 - 测试验证

### 11.1 检查内容

对照小强文档第7章，检查单元测试实现情况。

### 11.2 测试文件分析

**测试文件**: `backend/tests/test_tools.py`

| 测试用例 | 数量 | 说明 |
|---------|------|------|
| TestReadFile | 5个 | TC001-TC005 |
| TestWriteFile | 3个 | TC006-TC008 |
| TestListDirectory | 4个 | TC009-TC012 |
| TestDeleteFile | 4个 | TC013-TC016 |
| TestMoveFile | 3个 | TC017-TC019 |
| TestSearchFiles | 5个 | TC020-TC024 |
| TestGenerateReport | 2个 | TC025-TC026 |
| TestFileToolsIntegration | 2个 | TC027-TC028 |

**总计**: 28个测试用例（TC001-TC028）

### 11.3 测试运行问题

**问题**: 测试文件导入路径错误

```
from app.services.agent.tools import FileTools  # ❌ 错误路径
```

**实际路径**:
```
class FileTools 位于: app/services/tools/file/file_tools.py
```

**影响**: 无法直接运行pytest，需要修复导入路径或使用正确的运行方式。

### 11.4 结论

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 测试用例数量 | ✅ | 28个测试用例（小强文档要求28个） |
| 工具覆盖 | ✅ | 7个工具全覆盖 |
| 测试可运行性 | ✅ | 28/28 通过 |

### 11.5 修复记录

**修复内容**: test_tools.py 导入路径修复

**修复前**:
```python
from app.services.agent.tools import FileTools  # ❌ 错误路径
```

**修复后**:
```python
from app.services.tools.file.file_tools import FileTools  # ✅ 正确
```

**测试结果**:
```
======================= 28 passed, 21 warnings in 1.85s =======================
```

---

## 12. 代码架构优化 - 小沈

### 12.1 优化内容

小沈对原始代码进行了架构优化，将Pydantic模型从tools.py独立到file_schema.py：

| 文件 | 职责 | 说明 |
|------|------|------|
| file_schema.py | Schema定义 | 唯一Pydantic模型定义位置 |
| file_tools.py | 工具实现 | 导入并使用file_schema的模型 |
| file_prompts.py | Prompt模板 | 提供增强的Prompt |

### 12.2 修复的问题

**问题**: 之前file_tools.py中存在约110行Pydantic模型重复定义

**修复**: 删除重复定义，统一从file_schema.py导入

```python
# 修复后的导入（第29-37行）
from app.services.tools.file.file_schema import (
    ReadFileInput,
    WriteFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFilesInput,
    GenerateReportInput,
)
```

### 12.3 结论

✅ 代码架构更清晰，避免了重复定义问题。

---

## 9. 参考文档

- 《LLM工具调用参数-prompt约束设计报告》- 小强-2026-03-20
- 《LLM工具调用参数-prompt约束-实现说明文档》- 小强-2026-03-20

---

**更新信息**:

| 版本 | 时间 | 更新人 | 更新内容 |
|------|------|--------|---------|
| v1.5 | 2026-03-24 15:00:00 | 小沈 | 修复第7章测试导入路径问题，测试28/28通过 |
| v1.4 | 2026-03-24 14:30:00 | 小沈 | 新增第10章：第6章工具定义示例检查 + 第11章：第7章测试验证检查 + 第12章：代码架构优化 |
| v1.3 | 2026-03-24 13:58:00 | 小沈 | 新增第8章：小强第5章prompts.py增强检查 |
| v1.2 | 2026-03-24 13:36:17 | 小沈 | 新增第7章：执行层参数映射问题解决方案 |
| v1.1 | 2026-03-24 13:25:00 | 小沈 | 新增第4章：小强第4章解决方案设计检查 |
| v1.0 | 2026-03-24 13:22:40 | 小沈 | 初始版本：基于第3章的现状检查 |

---

**文档结束**

**创建时间**: 2026-03-24 13:22:40
**编写人**: 小沈
**版本**: v1.5
