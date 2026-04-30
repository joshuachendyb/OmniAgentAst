# 跨分类工具访问设计方案

**创建时间**: 2026-04-30 11:39:42
**更新时间**: 2026-04-30 13:30:00
**版本**: v1.5
**作者**: 小沈
**状态**: 详细设计

---

## 一、问题背景

当前系统按工具分类（FILE、TIME、SHELL等）划分了子Agent，但**子Agent被锁死在对应分类的工具箱中**：

1. 意图分类 → FILE Agent → 只能看到FILE工具 → 无法执行 `execute_command`、`get_current_time` 等
2. 一个任务天然需要多种工具类型，初始分类不应限制后续工具选择
3. 典型场景：LLM创建了bat脚本后，工具集中没有 `execute_command`，只能继续创建更多脚本

---

## 二、设计原则

| 原则 | 说明 |
|------|------|
| **意图分类保留** | 初始意图分类决定prompt风格和上下文，但**不限制工具访问** |
| **工具全集可见** | LLM每轮循环都能看到所有分类的工具 |
| **分层展示** | 概要层（名称+参数概要）+ 详细层（完整schema按需提供） |
| **自动纳入** | 新增工具时自动加入概要，无需手动修改Agent代码 |
| **执行器统一** | ToolExecutor 从全局 `tool_registry` 查找工具实现，不限于子Agent本地字典 |
| **低侵入** | 不改变现有注册体系，只改变工具列表的提供方式和执行器查找范围 |

---

## 三、总体架构

```
用户消息
    │
    ▼
意图分类器 ───→ FILE / TIME / SHELL / ...
    │
    ▼
子Agent（如 FileReactAgent / TimeReactAgent）
    │
    ├── System Prompt（分类特有的场景上下文）
    │
    ├── 会话管理（分类特有的，如FILE的回滚）
    │
    └── 每轮LLM调用
           ├── system prompt
           ├── 对话历史
           └── 当前消息（末尾追加【跨分类工具概要】）
               │
               ▼
           LLM返回 → tool_name + tool_params（可能来自任何分类）
               │
               ▼
           ToolExecutor
               ├── 优先查子Agent本地 _tools_dict（快速查找）
               └── fallback → tool_registry.get_implementation()（跨分类查找）
```

### 3.1 意图分类优化

#### 3.1.1 当前架构的问题分析

**双重检测且相互覆盖**（详见同目录下 `2026-04-30-intent-analysis.md`）

当前意图分类存在两条并行的检测路径，存在严重问题：

| 问题 | 严重程度 | 说明 |
|------|---------|------|
| LLM 分类结果被 CRSS 完全覆盖 | P0 | `chat_router.py:271-283` — 步骤1调LLM后，步骤2的CRSS直接覆盖结果，LLM调用纯属浪费 |
| CRSS 把所有操作类意图都归为 file | P0 | `chat_router.py:121-140` — network/desktop关键词全部返回file，对应Agent永远收不到请求 |
| 缺少 time/shell/env 等意图 | P1 | `intent_classifier.py:96-99` — 只有4类，无法覆盖全部使用场景 |
| 错误处理全部 fallback 到 chat | P1 | 任何API失败都当作普通对话，操作命令丢失 |
| `detect_intent_from_crss` 只输出2类 | P1 | 与 `INTENT_LABELS` 的4类不匹配，架构不一致 |

#### 3.1.2 优化方案

**目标**：统一意图分类逻辑，消除冗余LLM调用，使分类结果与 `ToolCategory` 枚举完全对齐。采用 **CRSS快速匹配 + LLM兜底** 两阶段策略，兼顾速度和精度。

**两阶段分类流程**：

```
用户输入
    │
    ▼
阶段1: CRSS规则快速匹配
    ├─ 匹配成功且唯一 → 直接返回对应ToolCategory
    ├─ 匹配成功但多个 → 标记为top-2候选，进入阶段2
    └─ 无匹配 → 进入阶段2
                │
                ▼
        阶段2: LLM语义分类
                ├─ 传入候选列表（阶段1的结果或全部类别）
                ├─ LLM返回: {intent, confidence, all_intents[]}
                └─ 解析返回结果
                    │
                    ▼
              最终意图
```

**优化内容**：

1. **阶段1：CRSS规则扩展（覆盖所有 ToolCategory）**

   ```python
   返回值: (intent: Optional[ToolCategory], candidates: List[ToolCategory])
   # intent: 唯一匹配结果（None表示无唯一匹配）
   # candidates: 候选列表（匹配到的所有可能分类）
   ```

   规则扩展：
   - `FILE`：文件操作关键词（原有规则 + 词边界检查 `\bkeyword\b` 防止误匹配）
   - `SHELL`：命令执行关键词（`npm`, `pip`, `node`, `build`, `run` 等 + 词边界检查）
   - `TIME`：时间日期关键词（`几点`, `日期`, `时间`, `现在几点` 等）
   - `NETWORK`：网络操作关键词（`ping`, `curl`, `下载`, `http` 等 + 词边界检查）
   - `DESKTOP`：桌面操作关键词（`截图`, `点击`, `screenshot` 等）
   - `ENV`：环境变量关键词（`PATH`, `环境变量`, `set` 等）
   - `SYSTEM`：系统信息关键词（`CPU`, `内存`, `进程`, `tasklist` 等）
   - `DATABASE`：数据库操作关键词（`查询`, `SQL`, `select` 等）
   - `CHAT`：不返回（仅在无任何匹配时作为兜底）

   **词边界检查**：所有英文关键词使用正则 `\bkeyword\b` 替代 `in` 判断，防止 `"ping一下"` 误配 `"ping"`、`"builder"` 误配 `"build"`。

2. **阶段2：LLM语义分类（作为CRSS的补充，不是替代）**

   - 仅在以下情况触发LLM：
     a. CRSS无匹配 → LLM从全部分类中选择
     b. CRSS匹配到多个候选（如用户输入同时含文件+网络关键词）
   - LLM使用主聊天模型的lite版本（或独立配置的小模型，不强制用七牛）
   - 返回完整置信度分布：`{"FILE": 0.85, "NETWORK": 0.10, "CHAT": 0.05}`
   - 带文本矫正功能（原有的文本矫正能力保留）

3. **消除冗余LLM调用**

   - `chat_router.py` 中删除 `PreprocessingPipeline.process()` 的LLM调用
   - 保留 `PreprocessingPipeline` 作为架构，但内部改为先CRSS后LLM
   - `intent_classifier.py` 保留但改造为阶段2的LLM分类器

4. **多意图支持**

   - 支持返回 **top-3 意图列表**，每个带置信度
   - 路由层根据主意图选择Agent，但将候选意图列表也传递给Agent
   - Agent可从候选列表中调整自己的 `priority_category` 策略

5. **与跨分类工具访问的结合**

   - 分类结果决定了**初始 system prompt 的风格**和**初始优先级分类**（`priority_category`）
   - 候选意图列表传递给Agent，Agent在运行时可根据任务进展切换优先级
   - 分类结果**不限制**后续LLM可用的工具范围（工具全集可见）
   - 示例：分类为 `FILE` → system prompt用文件场景 → 工具概要 `priority_category=FILE`，但LLM仍然可以用 `execute_command` 等

6. **prompt 优化**

   - 根据意图类型选择不同的 system prompt 模板
   - 模板中必须包含一句话："注意：你也可以使用其他分类的工具（如Shell命令执行、时间查询等），根据任务需要自由选择"
   - 示例说明LLM可以使用非本分类的工具

#### 3.1.3 意图分类与工具概要排序的联动

**单意图场景**（CRSS匹配成功且唯一）：

```
意图分类结果 → 决定 priority_category → 决定工具概要中哪个分类排最前面
                                        ↓
                               不影响工具全集（所有工具都展示）
```

**多意图场景**（CRSS匹配多个或LLM补充）：

```
CRSS/LLM 返回 top-3 意图列表
    │
    ├─ 主意图（置信度最高）→ 选择对应Agent、初始system prompt风格
    ├─ 次意图（置信度第二）→ 传递给Agent作为备选
    └─ 第三意图 → 传递给Agent（Agent运行中可能切换优先级）

Agent内部：
    ├─ 初始 priority_category = 主意图
    └─ 运行中可根据task进展调整为其他分类
```

**示例**：
| 用户输入 | 主意图 | 次意图 | priority_category | 概要展示 |
|---------|--------|--------|-----------------|---------|
| "帮我清理桌面文件" | FILE | — | ToolCategory.FILE | 文件工具→Shell→时间→... |
| "现在几点了" | TIME | — | ToolCategory.TIME | 时间工具→文件→Shell→... |
| "运行npm install" | SHELL | — | ToolCategory.SHELL | Shell→文件→时间→... |
| "下载文件并查看" | NETWORK | FILE | ToolCategory.NETWORK | 网络→文件→Shell→... |

---

### 3.2 动态工具发现机制（阶段二）

**说明**：v1.5 的概要层方案为**阶段一**（静态注入全部工具概要）。阶段二在此基础上增加动态机制，但目前仅作为设计方向记录，不在本次实现范围内。

#### 3.2.1 问题

静态注入全部工具（约2.5KB/30个）虽然简单可靠，但有以下不足：
- LLM始终看到30个工具，注意力分散
- 无法根据任务进展动态聚焦
- 无法感知LLM的行为模式并主动推荐工具

#### 3.2.2 方案方向

**方向一：上下文感知的概要裁切**

```
每轮LLM调用时，系统分析对话历史和最近3轮的工具使用记录：
├─ 如果LLM连续多轮使用 FILE 工具 → 保留FILE完整概要，其他分类只保留名称
├─ 如果LLM刚刚创建了脚本文件 → 突出显示 execute_command
└─ 如果LLM最近使用了某个工具 → 在概要中将其排到更前面
```

**方向二：工具热加载**

```
系统检测到LLM的某种行为模式（如连续创建文件但未执行），
主动在下一轮消息中追加提示：
"注意：你已创建了脚本文件，可以使用 execute_command 来运行它。"
```

**方向三：LLM反馈驱动的自动扩展**

```
如果LLM尝试调用的工具不在工具列表中（返回 tool_not_found 错误），
系统自动从全局 registry 查找并提示LLM该工具可用。
（部分功能已在ToolExecutor fallback中实现）
```

#### 3.2.3 实现优先级

| 优先级 | 功能 | 阶段 |
|--------|------|------|
| P0 | 所有工具静态注入（当前方案） | 阶段一 ✅ |
| P1 | ToolExecutor fallback 到全局registry（已支持跨分类执行） | 阶段一 ✅ |
| P2 | 上下文感知的概要裁切 | 阶段二 |
| P3 | LLM行为模式的主动推荐 | 阶段二 |

---

## 四、工具概要层设计

### 4.1 概要层格式

每轮注入到当前轮次的 user message 末尾，按分类组织。**每个工具包含：名称 + 必填参数概要 + 一句话描述**。

格式示例（30个工具时约2.5KB）：

```
=== 可用工具列表 ===

【文件操作工具】
read_file(file_path, offset, limit): 读取文件内容
write_file(file_path, content): 写入文件内容
list_directory(dir_path, recursive): 列出目录内容
delete_file(file_path, recursive): 删除文件/目录（自动备份）
move_file(source_path, destination_path): 移动/重命名文件
search_files(file_pattern, path): 按文件名模式搜索
search_file_content(pattern, path): 按内容搜索文件
generate_report(output_dir): 生成操作报告
copy_file(source_path, destination_path): 复制文件
create_directory(dir_path): 创建目录
get_file_info(file_path): 获取文件信息
compare_files(file_path1, file_path2): 比较两个文件
batch_rename(dir_path, pattern, replacement): 批量重命名
compress_files(source_paths, output_path): 压缩文件
file_checksum(file_path): 计算文件校验值
glob_files(pattern): Glob匹配文件
grep_file_content(pattern, path): 搜索文件内容

【Shell命令工具】
execute_command(command, cwd, timeout): 执行Shell命令
get_working_directory(): 获取当前工作目录
change_directory(path): 切换工作目录
check_path_exists(path): 检查路径是否存在

【时间日期工具】
get_current_time(): 获取当前时间
format_date(date, format): 格式化日期
calculate_date_difference(date1, date2): 计算日期差

【环境变量工具】
get_env(name): 获取环境变量
set_env(name, value): 设置环境变量
list_env(): 列出所有环境变量

【网络通信工具】
（按需列出，格式同上）

【系统信息工具】
（按需列出，格式同上）

【通用工具】
finish(result): 完成任务并返回结果摘要
```

**参数概要的提取规则**（自动生成）：从 `input_schema` 的 `required` 字段中取必填参数名，用括号括起来，逗号分隔。非必填参数不列出。

### 4.2 概要生成函数（代码）

在 `ToolRegistry` 类中新增方法：

```python
def get_all_tools_summary(self, priority_category: Optional[ToolCategory] = None) -> str:
    """
    获取所有工具的概要描述（按分类组织）
    
    自动遍历所有已注册工具，按ToolCategory分组。
    priority_category 对应的分类排在最前面，其余按固定顺序。
    
    每个工具显示：名称(必填参数): 描述
    
    Args:
        priority_category: 优先展示的分类（如FILE Agent传入ToolCategory.FILE）
        
    Returns:
        格式化的工具概要字符串
    """
    lines = []
    lines.append("=== 可用工具列表 ===")
    lines.append("")
    
    from collections import defaultdict
    by_category = defaultdict(list)
    for name, metadata in self._tools.items():
        by_category[metadata.category].append((name, metadata))
    
    # 分类展示顺序
    category_order = [
        ToolCategory.FILE,
        ToolCategory.SHELL,
        ToolCategory.TIME,
        ToolCategory.ENV,
        ToolCategory.SYSTEM,
        ToolCategory.NETWORK,
        ToolCategory.DATABASE,
        ToolCategory.DESKTOP,
    ]
    
    # 如果指定了priority_category，移到最前面
    if priority_category and priority_category in category_order:
        category_order.remove(priority_category)
        category_order.insert(0, priority_category)
    
    category_names = {
        ToolCategory.FILE: "文件操作工具",
        ToolCategory.SHELL: "Shell命令工具",
        ToolCategory.TIME: "时间日期工具",
        ToolCategory.ENV: "环境变量工具",
        ToolCategory.SYSTEM: "系统信息工具",
        ToolCategory.NETWORK: "网络通信工具",
        ToolCategory.DATABASE: "数据库工具",
        ToolCategory.DESKTOP: "桌面工具",
    }
    
    for cat in category_order:
        if cat not in by_category:
            continue
        items = by_category[cat]
        display_name = category_names.get(cat, cat.value)
        lines.append(f"【{display_name}】")
        for name, meta in sorted(items, key=lambda x: x[0]):
            # 只提取必填参数
            params = self._extract_required_params(meta.input_schema)
            param_str = ", ".join(params) if params else ""
            if param_str:
                lines.append(f"  {name}({param_str}): {meta.description}")
            else:
                lines.append(f"  {name}: {meta.description}")
        lines.append("")
    
    return "\n".join(lines)


def _extract_required_params(self, input_schema: Dict) -> List[str]:
    """
    从input_schema中提取必填参数名
    
    Args:
        input_schema: Pydantic模型生成的schema字典
        
    Returns:
        必填参数名列表
    """
    if not input_schema:
        return []
    required = set(input_schema.get("required", []))
    return sorted(required)
```

---

## 五、执行流程详细设计

### 5.1 每轮LLM调用的消息构造

```python
async def _get_llm_response(self, current_message: str) -> str:
    """获取 LLM 响应"""
    
    # 构建系统提示
    sys_prompt = self._build_system_prompt()
    
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(self.conversation_history)
    
    # 【新增】在当前 user message 末尾追加工具概要
    # 每轮都注入，确保LLM不会丢失工具信息
    tools_summary = self._get_tools_summary()
    enhanced_message = current_message + "\n\n---\n当前可用工具列表:\n" + tools_summary
    messages.append({"role": "user", "content": enhanced_message})
    
    # 调用LLM
    response = await self.llm_client(messages)
    return response
```

### 5.2 ToolExecutor 执行（支持跨分类工具）

**修改 ToolExecutor.execute 方法**，当本地字典找不到工具时，从全局注册表查找：

```python
class ToolExecutor:
    def __init__(self, tools: Dict[str, Callable] = None):
        if tools is not None:
            self.available_tools = tools
        else:
            from app.services.tools.registry import get_implementations_from_registry
            self.available_tools = get_implementations_from_registry()
    
    async def execute(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        if action == "finish":
            return {"success": True, "result": "Task finished"}
        
        # 查找工具实现
        impl = self.available_tools.get(action)
        
        # 【新增】如果本地没有，从全局注册表查找
        if not impl:
            from app.services.tools.registry import tool_registry
            impl = tool_registry.get_implementation(action)
            if not impl:
                return {
                    "success": False,
                    "error": f"Tool '{action}' not found"
                }
            # 【新增】缓存到本地，下次快速查找
            self.available_tools[action] = impl
        
        # 执行工具
        try:
            # 调用工具实现
            result = impl(**action_input)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
```

---

## 六、FileReactAgent 修改

### 6.1 代码修改

```python
class FileReactAgent(ToolLoaderMixin, BaseAgent):
    def __init__(self, ...):
        # 【保留】加载FILE工具到本地缓存（用于快速执行）
        self._tools_dict = ToolLoaderMixin._load_tools(self, ToolCategory.FILE)
        
        # 【修改】ToolExecutor传入本地工具字典 + 支持fallback到全局
        self.executor = ToolExecutor(self._tools_dict)
        
        # 【新增】缓存工具概要（避免每轮都生成）
        self._tools_summary = None
    
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        base_prompt = self.prompts.get_system_prompt()
        # 【修改】追加跨工具提示，告知LLM可使用所有分类的工具
        cross_tool_hint = (
            "\n\n【注意】除了文件操作工具，你还可以使用其他分类的工具。"
            "例如：创建脚本后可以用 execute_command 来运行它，"
            "需要时间信息时可以用 get_current_time 等。"
            "根据任务需要自由选择合适的工具，不受初始分类限制。"
        )
        return base_prompt + cross_tool_hint
    
    def _get_tools_summary(self) -> str:
        """获取工具概要（带缓存）"""
        if self._tools_summary is None:
            from app.services.tools.registry import tool_registry
            # FILE Agent：FILE工具排最前面
            self._tools_summary = tool_registry.get_all_tools_summary(
                priority_category=ToolCategory.FILE
            )
        return self._tools_summary
    
    async def _get_llm_response(self, current_message: str) -> str:
        """获取 LLM 响应"""
        sys_prompt = self._build_system_prompt()
        
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(self.conversation_history)
        
        # 【修改】在当前 user message 末尾追加跨分类工具概要
        tools_summary = self._get_tools_summary()
        enhanced = current_message + "\n\n---\n当前可用工具列表:\n" + tools_summary
        messages.append({"role": "user", "content": enhanced})
        
        # ... 调用LLM，其余逻辑不变
```

### 6.2 ToolExecutor 使用场景说明

| 场景 | 查找路径 | 结果 |
|------|---------|------|
| LLM调用 `read_file`（FILE工具） | `self.available_tools["read_file"]` | ✅ 本地找到 |
| LLM调用 `execute_command`（SHELL工具） | 本地无 → `tool_registry.get_implementation("execute_command")` | ✅ fallback找到 |
| LLM调用不存在的工具 | 两处都找不到 | ❌ 返回错误 |

---

## 七、TimeReactAgent 修改

### 7.1 代码修改

```python
class TimeReactAgent(ToolLoaderMixin, BaseAgent):
    def __init__(self, ...):
        # 【保留】加载TIME工具到本地缓存
        self._tools_dict = ToolLoaderMixin._load_tools(self, ToolCategory.TIME)
        
        # 【修改】ToolExecutor传入本地工具字典 + 支持fallback到全局
        self.executor = ToolExecutor(self._tools_dict)
        
        # 【新增】缓存工具概要
        self._tools_summary = None
    
    def _get_tools_summary(self) -> str:
        """获取工具概要（带缓存）"""
        if self._tools_summary is None:
            from app.services.tools.registry import tool_registry
            # Time Agent：TIME工具排最前面
            self._tools_summary = tool_registry.get_all_tools_summary(
                priority_category=ToolCategory.TIME
            )
        return self._tools_summary
    
    def _build_system_prompt(self) -> str:
        """构建系统提示（含跨工具提示）"""
        base_prompt = self.prompts.get_system_prompt()
        cross_tool_hint = (
            "\n\n【注意】除了时间日期工具，你还可以使用其他分类的工具。"
            "例如：需要操作文件时可以用 read_file/write_file，"
            "需要执行命令时可以用 execute_command 等。"
            "根据任务需要自由选择合适的工具。"
        )
        return base_prompt + cross_tool_hint
    
    async def _get_llm_response(self, current_message: str) -> str:
        # system prompt（Time场景）
        sys_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(self.conversation_history)
        
        # 【修改】在当前 user message 末尾追加跨分类工具概要
        tools_summary = self._get_tools_summary()
        enhanced = current_message + "\n\n---\n当前可用工具列表:\n" + tools_summary
        messages.append({"role": "user", "content": enhanced})
        
        # ... 调用LLM
```

### 7.2 TimeReactAgent 特有的部分

| 项目 | 说明 |
|------|------|
| System prompt | 时间日期场景的上下文和示例 |
| 会话管理 | 不需要回滚等复杂会话管理 |
| 初始工具缓存 | TIME分类的3个工具 |

---

## 八、后续新增子Agent的规范

后续新增子Agent（如 SHELL Agent、ENV Agent、NETWORK Agent）时，遵循以下规范：

```python
class NewAgent(ToolLoaderMixin, BaseAgent):
    def __init__(self, ...):
        # 1. 加载本分类工具到本地缓存
        self._tools_dict = ToolLoaderMixin._load_tools(self, ToolCategory.XXX)
        
        # 2. 创建ToolExecutor（自动支持跨分类fallback）
        self.executor = ToolExecutor(self._tools_dict)
        
        # 3. 缓存工具概要
        self._tools_summary = None
    
    def _build_system_prompt(self) -> str:
        """构建系统提示（含跨工具提示）"""
        base_prompt = self.xxx_prompts.get_system_prompt()  # 使用对应分类的prompts
        cross_tool_hint = (
            "\n\n【注意】除了本分类工具，你还可以使用其他分类的工具。"
            "根据任务需要自由选择合适的工具，不受初始分类限制。"
        )
        return base_prompt + cross_tool_hint
    
    def _get_tools_summary(self) -> str:
        """获取工具概要（复制此方法到新Agent）"""
        if self._tools_summary is None:
            from app.services.tools.registry import tool_registry
            self._tools_summary = tool_registry.get_all_tools_summary(
                priority_category=ToolCategory.XXX  # 传入自己对应的分类
            )
        return self._tools_summary
    
    async def _get_llm_response(self, current_message: str) -> str:
        """获取LLM响应（复制此模式）"""
        sys_prompt = self._build_system_prompt()
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(self.conversation_history)
        
        # 在当前 user message 末尾跨分类工具概要
        tools_summary = self._get_tools_summary()
        enhanced = current_message + "\n\n---\n当前可用工具列表:\n" + tools_summary
        messages.append({"role": "user", "content": enhanced})
        
        # ... 调用LLM
```

**子Agent只需关注**：
1. 自己的System prompt内容（场景语境）
2. 自己的会话管理逻辑
3. 自己的初始工具缓存分类

**不需要关注**：
1. 跨分类工具问题（`ToolExecutor` + `get_all_tools_summary()` 自动处理）
2. 工具注册问题（遵循 `@register_tool` 规则自动纳入）

---

## 九、后续新增工具的规则

| 规则 | 说明 |
|------|------|
| **必须填 description** | `@register_tool(description="一句话描述")` — 概要层展示的依据 |
| **必须用 Pydantic input_model** | 自动生成schema，概要层自动提取参数名 |
| **自动纳入概要** | `get_all_tools_summary()` 自动遍历所有已注册工具，新增工具自动出现 |
| **不需要改Agent代码** | 任何Agent的 `_get_tools_summary()` 都从全局注册表获取 |

即：**新增工具只需要在注册时填好 `description` 和 `input_model`，跨分类工具展示自动生效，不修改任何Agent代码。**

---

## 十、优缺点评估

| 优点 | 缺点 |
|------|------|
| ✅ 实现简单，不需要动态判断逻辑 | ❌ 概要层每轮都注入system prompt，增加token消耗（30个工具约2.5KB） |
| ✅ LLM每轮都看到完整工具图景 | ❌ 大量工具时LLM可能忽略部分工具 |
| ✅ 新增工具自动纳入，不需要改Agent代码 | |
| ✅ 不改变意图分类和子Agent架构 | |
| ✅ ToolExecutor fallback机制很小改动 | |

### 10.1 Token消耗估算

| 工具数量 | 概要层大小 | 注入位置 | 影响 |
|---------|-----------|---------|------|
| 30个 | ~2.5KB | user message末尾（每轮都有） | 可接受 |
| 100个 | ~8KB | user message末尾（每轮都有） | 偏高，可能需要优化 |
| 200个 | ~16KB | user message末尾（每轮都有） | 可能影响模型注意力 |

**优化措施**（工具数量超过100个时启用）：
- 只列出工具名称和分类，不列出参数
- LLM需要时通过 `get_tool_detail(tool_name)` 获取完整信息

---

## 十一、三个关键决策（已确定）

### 11.1 概要层注入位置

```
每轮都在最后一条 user message 末尾追加
```

**原因**：
- 每轮都在user message末尾，靠近模型输出，LLM注意力更集中
- 统一处理，不需要区分第一轮和后续轮次（避免特殊逻辑）
- 代码实现简单一致

**代码实现**：

```python
async def _get_llm_response(self, current_message: str) -> str:
    sys_prompt = self._build_system_prompt()
    
    messages = [{"role": "system", "content": sys_prompt}]
    messages.extend(self.conversation_history)
    
    # 在当前 user message 末尾追加工具概要（每轮都有）
    tools_summary = self._get_tools_summary()
    enhanced_message = current_message + "\n\n---\n当前可用工具列表:\n" + tools_summary
    messages.append({"role": "user", "content": enhanced_message})
```

### 11.2 按Agent场景调整概要顺序

`get_all_tools_summary()` 增加 `priority_category` 参数：

```python
def get_all_tools_summary(self, priority_category: Optional[ToolCategory] = None) -> str:
    """
    Args:
        priority_category: 优先展示的分类（排在最前面）
    """
    # priority_category 对应的分类排第一，其余按固定顺序
```

**各Agent调用**：
- FileAgent：`tool_registry.get_all_tools_summary(priority_category=ToolCategory.FILE)`
- TimeAgent：`tool_registry.get_all_tools_summary(priority_category=ToolCategory.TIME)`
- 后续新Agent：传入自己对应的分类

### 11.3 参数概要只列必填参数

`_extract_required_params()` 只取 `input_schema` 中 `required` 字段声明的必填参数：

```python
def _extract_required_params(self, input_schema: Dict) -> List[str]:
    if not input_schema:
        return []
    required = set(input_schema.get("required", []))
    # 只返回 mandatory 中的参数
    return sorted(required)
```

---

## 版本记录

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-04-30 11:39:42 | 小沈 | 初始版本（概要设计） |
| v1.1 | 2026-04-30 12:00:00 | 小沈 | 详细设计：代码示例、ToolExecutor修改 |
| v1.2 | 2026-04-30 12:30:00 | 小沈 | 确定三个关键决策：注入位置/排序/必填参数 |
| v1.3 | 2026-04-30 12:45:00 | 小健 | 修复：messages构造方式、system prompt→user message注入位置、新Agent模板统一 |
| v1.4 | 2026-04-30 13:00:00 | 小沈 | 新增3.1节意图分类分析与优化方案 |
| v1.5 | 2026-04-30 13:30:00 | 小健 | 重写3.1.2：废弃LLM→CRSS+LLM两阶段策略；新增3.1.4动态工具发现（阶段二）；修复11.1注入位置一致性问题；新增system prompt跨工具提示；修复4.1节缺少finish工具；增强3.1.3多意图联动 |
