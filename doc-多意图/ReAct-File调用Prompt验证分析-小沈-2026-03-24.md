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

## 8. 参考文档

- 《LLM工具调用参数-prompt约束设计报告》- 小强-2026-03-20
- 《LLM工具调用参数-prompt约束-实现说明文档》- 小强-2026-03-20

---

**更新信息**:

| 版本 | 时间 | 更新人 | 更新内容 |
|------|------|--------|---------|
| v1.2 | 2026-03-24 13:36:17 | 小沈 | 新增第7章：执行层参数映射问题解决方案 |
| v1.1 | 2026-03-24 13:25:00 | 小沈 | 新增第4章：小强第4章解决方案设计检查 |
| v1.0 | 2026-03-24 13:22:40 | 小沈 | 初始版本：基于第3章的现状检查 |

---

**文档结束**

**创建时间**: 2026-03-24 13:22:40
**编写人**: 小沈
**版本**: v1.1
