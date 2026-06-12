# 002LLM Prompt与Message Conversation History全系统分析

**创建时间**: 2026-06-10 15:15:59  
**版本**: v2.1  
**作者**: 小沈  
**复查次数**: 5遍  

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-10 15:15:59 | 小沈 | 初始版本，全系统分析完成 |
| v1.1 | 2026-06-11 04:43:57 | 小沈 | 逐问题验证准确性+10大原则符合性+补充遗漏关键问题 |
| v1.2 | 2026-06-11 | 小健 | 逐问题修复复核，标注修复状态（✅已修复/⚠️未修复/✅不修改） |
| v1.3 | 2026-06-11 09:19:07 | 小沈 | 新增FC-only全系统文件检查清单（补充第2/3/4/5章未覆盖范围）|
| v1.4 | 2026-06-11 09:37:46 | 小沈 | 六↔七章节号互换；新增7.1.1降级路径必要性分析 |
| v1.5 | 2026-06-11 | 小沈 | 7.5.5补充_utils.py/_tool_params.py；7.5.6补充fc_context构建代码+L144删除说明；7.8.4精确区分mock类型；第三章新增P0历史污染问题；第五章新增3个P2问题 |
| v1.6 | 2026-06-11 14:30:00 | 小健 | 7.5.7补充审核发现6个问题（#1 fc_context死代码 #2 L144多余消息 #3 handler不写入history #4 yield协议变更崩溃P0 #5 answer_handler.strip依赖 #6 trim分离逻辑），推荐方案A保持str类型
| v2.0 | 2026-06-12 15:30:00 | 小欧 | FC-only全系统更新：第1章三层架构+图；第2.2 FileOperationPrompts/2.3 SystemAdapter/2.4 universal_agent（删除_call_llm_text_stream/_convert_fc_messages_to_text);第5.1 react_cycle（dict类型+删除parse_llm_response/TOOL_REMINDER/_TYPE_HANDLERS精简）;第5.2 parse_llm_response.py标记删除;第6章流程示例FC-only更新;删除OUTPUT_FORMAT/TOOL_REMINDER引用
| v2.1 | 2026-06-12 12:22:05 | 小欧 | FC-only精简化改造: TOOL_CALL_RULES合并AVOID_REPEAT_RULES(4条→3段); AVOID_REPEAT_RULES常量删除; build_full_system_prompt从8段→4段(移除rollback/AVOID_REPEAT/get_tool_details可选段, safety合并入规则段); _get_system_prompt简化; candidates_hint+cross_tool_hint移至_call_llm每轮注入; FileOperationPrompts删除get_rollback_instructions覆盖

---
## 一、核心架构总览

### 1.1 FC-only三层架构

```
┌─────────────────────────────────────────────────────────────┐
│  第一层：Prompt构建层（BasePrompts + 子类）                    │
│  职责：生成System Prompt + Task Prompt                       │
│  入口：build_full_system_prompt(include_tool_details)        │
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│  第二层：Message管理层（MessageBuilder）                      │
│  职责：管理conversation_history状态（FC协议）                  │
│  核心：init_history / add_observation(fc_context必传)        │
│  ※ add_assistant 已删除（FC协议由_append_observation统一处理）│
└─────────────────────────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────┐
│  第三层：LLM调用层（LLMClient）                               │
│  职责：发送messages给LLM，接收响应                             │
│  入口：request_stream(messages, tools, tool_choice)          │
│  ※ BaseAIService中间层已移除                                 │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 FC-only架构图

```
用户请求
    ↓
chat_router.py (路由层)
    ↓
AgentFactory.create(intent_type)
    ↓
UniversalAgent.__init__()
    ├─ 加载Prompt模板: config.prompt_class()
    │  └─ config.exclude_tool_details_from_prompt 控制工具描述注入
    └─ 初始化工具: ToolManager.init_tools()
    ↓
run_react_cycle() ─────────────────────────────────────┐
    ↓                                                  │
_initialize_run_state()                                │
    ├─ _get_system_prompt()                            │
    │   └─ prompts.build_full_system_prompt()          │
    ├─ _get_task_prompt(task, context)                 │
    └─ message_builder.init_history(sys, task)         │
        └─ conversation_history = [system, user]       │
    ↓                                                  │
循环开始 ←─────────────────────────────────────────────┤
    ↓                                                  │
_call_llm()                                            │
    ├─ message_builder.prepare_messages_for_llm()      │
    │   └─ 返回 conversation_history + temp_history    │
    ├─ _build_executed_tool_summary() → system注入     │
    ├─ _build_candidates_hint()      → system注入[v2.1]│
    ├─ _build_cross_tool_hint()      → system注入[v2.1]│
    └─ _call_llm_fc_stream(messages, tools)            │
       └─ llm_client.request_stream(messages, tools)   │
    ↓                                                  │
    ├─ yield ChunkStep（文本）+ ChunkStep（reasoning） │
    └─ yield Response（dict: action/answer）           │
    ↓                                                  │
  [内联JSON解析 — 无parse_llm_response]                │
  _call_llm_fc_stream() 内判断:                        │
    └─ 有tool_name → action（含fc_context）              │
    └─ 无tool_name → answer                             │
    ↓                                                  │
handler分派（_TYPE_HANDLERS注册式）                    │
    ├─ action → 执行工具                               │
    │   ├─ yield ThoughtStep                           │
    │   ├─ check_safety_and_confirm()                  │
    │   ├─ 执行工具 → result                           │
    │   ├─ yield ActionToolStep                        │
    │   ├─ yield ObservationStep                       │
    │   └─ message_builder.add_observation(fc_context) │
    │      ← FC协议: assistant(tool_calls) + role:tool │
    ├─ answer → 任务完成                               │
    │   └─ yield FinalStep                             │
    │      agent.status = AgentStatus.COMPLETED        │
    ↓                                                  │
判断是否继续循环 ───────────────────────────────────────┘
```

---

## 二、Prompt构建层详细分析（FC-only架构）

### 2.1 BasePrompts基类（base_prompt_template.py）

**文件路径**: `backend/app/services/prompts/base_prompt_template.py`

**核心职责**:
- 定义Prompt模板基类接口
- 统一System Prompt组装顺序
- 提供公共规则常量

**关键常量**:

#### 2.1.1 TOOL_CALL_RULES（工具调用规则 — v2.1合并AVOID_REPEAT_RULES）

```python
TOOL_CALL_RULES = """【回答要求】:
- reasoning简短(1-2句),不要长篇分析
- 始终用中文回复

【停止条件 — 满足以下任一即可结束】:
- 用户请求的操作已全部完成
- 信息已获取足够,可以回答用户问题
- 遇到无法解决的错误,已向用户报告原因和建议

【执行效率】:
- 同一工具成功后不要重复执行
- 已获取的信息直接使用,不重新获取
- 失败后换其他工具或方法,不要重试同一操作
- 连续3次不同方法都失败→停止尝试,向用户报告"""
```

**v2.1变更**:
- 合并原`AVOID_REPEAT_RULES`为【执行效率】段
- 移除FC冗余规则#1/#3/#4（FC协议的`tool_choice="auto"`已覆盖"何时调用工具"）
- 原规则#2（reasoning简短）保留，#5（中文回复）保留

**分析**:
- ✅ 精简为3段：回答要求/停止条件/执行效率，职责清晰
- ✅ 不再与FC协议语义重叠
- ✅ 消除SRP/DRY违反（原AVOID_REPEAT_RULES独立常量违反DRY）

#### 2.1.2 build_full_system_prompt()（唯一组装入口 — v2.1精简化版）

```python
def build_full_system_prompt(self, include_tool_details: bool = None) -> str:
    """构建完整的系统Prompt — FC-only版

    组装顺序:
    ① _get_system_info()        — 公共:系统信息(OS/路径规则)
    ② _get_project_context()    — 公共:项目上下文(README.md)
    ③ get_core_system_prompt() — 分类特有(角色+业务规则)
    ④ TOOL_CALL_RULES + safety — 公共:回答要求+停止条件+执行效率+安全提醒
    """
    if include_tool_details is not None:
        self._include_tool_details = include_tool_details

    parts = [self._get_system_info()]

    project_ctx = self._get_project_context()
    if project_ctx:
        parts.append(project_ctx)

    parts.append(self.get_core_system_prompt())

    # Rules section: TOOL_CALL_RULES + safety merged
    rules = [self.TOOL_CALL_RULES]
    safety = self.get_safety_reminder()
    if safety:
        rules.append(f"【安全提醒】:\n{safety}")
    parts.append("\n\n".join(rules))

    return "\n\n".join(parts)
```

**组装顺序分析（v2.1精简，从8段→4段）**:
```
① _get_system_info()         [公共]     → 系统信息(OS/路径规则)
② _get_project_context()     [公共]     → 项目上下文(README.md)
③ get_core_system_prompt()  [分类特有] → 角色+业务规则
④ TOOL_CALL_RULES+safety    [公共]     → 回答要求+停止条件+执行效率+安全提醒
```

**v2.1移除**:
- `get_tool_details()` → 由FC Schema承载，不再Prompt中注入
- `get_rollback_instructions()` → LLM能从`role:tool`错误消息理解失败原因，无需额外指令
- `AVOID_REPEAT_RULES` → 合并入`TOOL_CALL_RULES`【执行效率】段
- `get_safety_reminder()` → 从独立段改为附在规则段尾部

**分析**:
- ✅ 从8段精简至4段，组装更轻量
- ✅ 公共规则统一注入，避免重复
- ✅ 移除`include_tool_details`逻辑（FC模式不再需要工具描述在Prompt中）
- ✅ `get_rollback_instructions()` 方法删除（基类和FileOperationPrompts均删除）

---

### 2.2 FileOperationPrompts子类（file_prompts.py）

**文件路径**: `backend/app/services/prompts/file/file_prompts.py`

**核心职责**:
- 定义文件操作Agent的System Prompt
- 提供get_core_system_prompt()（角色+业务规则）
- 提供get_tool_details()（工具描述+示例，FC模式可选）

**FC-only重构（2026-06-11）**: `get_system_prompt()` 拆分为 `get_core_system_prompt()` + `get_tool_details()`。系统信息由基类 `_get_system_info()` 统一注入。

**get_core_system_prompt()实现**:

```python
def get_core_system_prompt(self) -> str:
    """获取核心系统Prompt(角色+业务规则) - 小沈 2026-06-11 系统信息提到Base公共层"""
    return """
【互斥参数规则 - 同一工具内禁止同时使用】:
- read_file: file_paths 单路径=单文件,多路径=批量
- edit_file: old_string 与 edits 互斥
- rename_file: path 与 directory 互斥
- archive_tool: compress→source+destination; extract→source
- file_operation: move/copy→destination; delete→无需destination

【write_text_file content规则】:
- content 参数必须传实际文件内容(代码/文本/正文)
- ❌ 禁止传入思考/计划/状态确认
- ✅ content=\"第一章:觉醒\\n\\n林凡是一名普通的大学生...\""""
```

**get_tool_details()实现**:

```python
def get_tool_details(self) -> str:
    """获取工具描述和示例(FC模式下由Schema承载,可选跳过) - 小沈 2026-06-11"""
    tools = [
        "read_file", "write_text_file", "list_directory",
        "search_files", "grep_file_content", "edit_file",
        "rename_file", "file_operation", "archive_tool",
        "read_media_file", "data_file_format",
    ]
    tool_descriptions = self.build_tool_descriptions(tools, category_label="FILE")
    return f"""# File Operation Tools

{tool_descriptions}
【调用决策示例】:
用户: "读取C:/config.json"
→ 判断: 单文件读取 → 调用read_file(file_paths=["C:/config.json"])

用户: "搜索D:/project下所有包含TODO的Python文件"
→ 判断: 内容搜索+文件过滤 → 调用grep_file_content(pattern="TODO", search_dir="D:/project", glob="*.py")

用户: "把Hello World写入D:/output.txt"
→ 判断: 写入新文件 → 调用write_text_file(file_path="D:/output.txt", content="Hello World")"""
```

**分析**:
- ✅ 动态生成工具描述，避免硬编码
- ✅ SRP分离：get_core_system_prompt()只负责业务规则，get_tool_details()只负责工具描述+示例
- ✅ 系统信息由基类 `_get_system_info()` 统一注入，各子类不再自行 `get_system_prompt_string()`
- ✅ FC模式可选跳过 `get_tool_details()`（由 `include_tool_details` 控制）
- ⚠️ **问题**: 示例硬编码在字符串中，应提取为模板池

---

### 2.3 SystemAdapter中间层（system_adapter.py）

**文件路径**: `backend/app/services/prompts/middle/system_adapter.py`

**核心职责**:
- 根据服务器OS生成系统自适应Prompt
- 提供路径格式、命令格式映射

**generate_system_prompt()实现**:

```python
def _get_environment_info(self) -> str:
    """获取环境信息(工作目录/Git状态/日期) — 小沈 2026-06-11"""
    cwd = os.getcwd()
    today = date.today().strftime("%Y-%m-%d")
    is_git = self._check_is_git_repo(cwd)
    git_status = "是" if is_git else "否"
    return f"""【环境信息】
- 工作目录: {cwd}
- Git仓库: {git_status}
- 当前日期: {today}
"""

def generate_system_prompt(self, include_commands: bool = True) -> str:
    """生成系统信息Prompt"""
    system_name = self.get_system_name()
    path_format = self.get_path_format()
    env_info = self._get_environment_info()
    
    prompt = env_info + f"""【当前系统】
{system_name}

【路径格式】
- 当前系统: {path_format}
"""
    if include_commands:
        commands = self.get_commands()
        cmd_lines = "\n".join(f"- {k}: {v}" for k, v in commands.items())
        prompt += f"""
【命令格式】
{cmd_lines}
"""
    
    prompt += """
【路径规则】
- 必须使用绝对路径(禁止相对路径如 ./file.txt)
- 禁止用 ~ 表示家目录
- ❌ 路径中的中文字符必须原样保留,禁止翻译或转换!
"""
    
    return prompt
```

**分析**:
- ✅ 系统自适应，支持Windows/Linux/macOS
- ✅ include_commands参数控制是否注入命令格式
- ✅ 路径规则清晰，防止LLM转换中文路径
- ✅ 使用lru_cache单例，避免重复计算
- ✅ 2026-06-11新增环境信息（工作目录/Git状态/日期）

---

### 2.4 UniversalAgent的Prompt组装（universal_agent.py）

**文件路径**: `backend/app/services/agent/universal_agent.py`

**核心职责**:
- 根据ServerConfig加载具体的Prompt类
- 获取和构建完整的System Prompt
- 管理对话历史
- 协调LLM请求和响应

**核心属性**:

```python
class UniversalAgent:
    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        config: Optional[AgentConfig] = None,
        tool_category: Optional[ToolCategory] = None,
        max_steps: Optional[int] = None,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        if not task_id:
            intent_type = config.intent_type if config else "unknown"
            raise ValueError(f"task_id is required for {intent_type} operation tracking")

        effective_category = tool_category or (config.category if config else None)
        if max_steps is None:
            if config and config.max_steps:
                effective_max_steps = config.max_steps
            else:
                from app.config import get_config
                effective_max_steps = get_config().get_max_steps()
        else:
            effective_max_steps = max_steps
        rollback_enabled = config.rollback_enabled if config else True

        super().__init__(
            llm_client=llm_client,
            task_id=task_id,
            tool_category=effective_category,
            max_steps=effective_max_steps,
            rollback_enabled=rollback_enabled,
            candidates=candidates,
            **kwargs
        )

        if config:
            self.config = config
            self.prompts = config.prompt_class()
            # FC-only模式: 跳过Prompt中的工具描述和示例(由FC Schema承载)
            if config.exclude_tool_details_from_prompt:
                self.prompts.include_tool_details = False
            logger.info(
                f"UniversalAgent initialized (intent={config.intent_type}, task_id={task_id}, category={effective_category})"
            )
        else:
            logger.info(
                f"UniversalAgent initialized (task_id={task_id}, category={effective_category})"
            )

    def _get_system_prompt(self) -> str:
        if not hasattr(self, 'prompts') or not self.prompts:
            return "System: 通用助手"
        return self.prompts.build_full_system_prompt()   # ← v2.1: 直接返回4段,无candidates/cross_tool

    def _build_candidates_hint(self) -> str:
        if not self._candidates:
            return ""
        from app.services.agent.agent_config import resolve_agent_config
        names = []
        for c in self._candidates:
            cfg = resolve_agent_config(c)
            if cfg:
                names.append(f"{cfg.category_display_name}({c})")
        if not names:
            return ""
        return f"【候选意图】用户任务可能属于以下分类: {', '.join(names)}。如当前工具无法完成,可尝试其他分类的工具。"

    def _build_cross_tool_hint(self) -> str:
        loaded = getattr(self, '_loaded_categories', set())
        if len(loaded) <= 1:
            return ""
        from app.services.agent.agent_config import AGENT_REGISTRY
        loaded_names = []
        for intent_type, cfg in AGENT_REGISTRY.items():
            if cfg.category.value in loaded:
                loaded_names.append(cfg.category_display_name)
        if not loaded_names:
            return ""
        return f"【跨分类工具】当前已加载多分类工具: {', '.join(loaded_names)}。可跨分类调用工具完成任务。"

    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        return self.prompts.get_task_prompt(task)

    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]] = None):
        pass

    def _on_before_loop(self, sys_prompt: str, task_prompt: str, context: Optional[Dict[str, Any]] = None):
        pass

    def _on_after_loop(self):
        pass

    def _complete_tracked_task(self, success: bool):
        self._step_emitter.complete_task(success)

    async def _execute_tool(self, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
        return await self._retry_engine.execute_tool_with_retry(tool_name, tool_params)

    async def _call_llm(self):
        """调用LLM — 纯FC模式 — FC-only重构 2026-06-11 小沈"""
        self.llm_call_count += 1
        self.message_builder.trim_history()

        messages = self.message_builder.prepare_messages_for_llm()

        executed_summary = self._build_executed_tool_summary()
        if executed_summary:
            messages.append({"role": "system", "content": executed_summary})

        # Inject hints each round — FC-only v2.1 2026-06-12
        candidates_hint = self._build_candidates_hint()
        if candidates_hint:
            messages.append({"role": "system", "content": candidates_hint})
        cross_tool_hint = self._build_cross_tool_hint()
        if cross_tool_hint:
            messages.append({"role": "system", "content": cross_tool_hint})

        openai_tools = self._get_openai_tools()

        if not openai_tools:
            logger.error(f"[call_llm] 无可用工具, category={self.tool_category}")

        async for item in self._call_llm_fc_stream(messages, openai_tools):
            yield item

    async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
        """FC模式流式调用 — 纯FC,无降级 — FC-only重构 2026-06-11 小沈"""
        from app.services.agent.steps import ChunkStep
        from app.utils.json_utils import parse_json

        full_content = ""
        full_reasoning = ""
        stream_error = None
        chunk_step_count = 0

        try:
            async for chunk in self.llm_client.request_stream(
                messages=messages,
                tools=openai_tools, tool_choice="auto",
            ):
                if chunk.stream_error:
                    stream_error = chunk.stream_error
                    break

                if chunk.content:
                    chunk_step_count += 1
                    if getattr(chunk, "is_reasoning", False):
                        full_reasoning += chunk.content
                        yield ("chunk", ChunkStep(step=self.llm_call_count, content=chunk.content, is_reasoning=True))
                    else:
                        full_content += chunk.content
                        yield ("chunk", ChunkStep(step=self.llm_call_count, content=chunk.content, is_reasoning=False))

                if chunk.is_done:
                    break
        except Exception as e:
            logger.error(f"[FC] 流式异常: {e}")
            yield ("response", {"type": "answer", "content": f"LLM调用异常: {e}"})
            return

        if stream_error:
            logger.error(f"[FC] 流式错误: {stream_error}")
            yield ("response", {"type": "answer", "content": f"LLM流式错误: {stream_error}"})
            return

        # 判断是action还是answer
        parsed = parse_json(full_content)
        # 容错: 文本+JSON混合,按"tool_name"标记向前定位{再括号匹配
        if not parsed and full_content:
            _tn = full_content.find('"tool_name"')
            if _tn >= 0:
                _open = full_content.rfind('{', 0, _tn)
                if _open >= 0:
                    _depth = 0
                    for _j in range(_open, len(full_content)):
                        if full_content[_j] == '{':
                            _depth += 1
                        elif full_content[_j] == '}':
                            _depth -= 1
                            if _depth == 0:
                                parsed = parse_json(full_content[_open:_j+1])
                                break
        if parsed and "tool_name" in parsed:
            fc_context = {
                "tool_call_id": parsed.get("tool_call_id") or "",
                "tool_calls": parsed.get("tool_calls", [])
            }
            # 从tool_calls提取平行调用 — 小沈 2026-06-11 修复P0:_pending_calls从未赋值
            _pending_calls = []
            raw_tool_calls = parsed.get("tool_calls", [])
            if len(raw_tool_calls) > 1:
                primary_id = parsed.get("tool_call_id", "")
                for tc in raw_tool_calls:
                    tc_id = tc.get("id", "")
                    if tc_id and tc_id != primary_id:
                        func = tc.get("function", {})
                        try:
                            extra_params = json.loads(func.get("arguments", "{}"))
                        except (json.JSONDecodeError, TypeError):
                            extra_params = {}
                        _pending_calls.append({
                            "tool_name": func.get("name", ""),
                            "tool_params": extra_params,
                            "_tool_call_id": tc_id,
                        })
            logger.info(f"[FC] LLM原始响应(action): {full_content}")
            yield ("response", {"type": "action", "fc_context": fc_context, "_pending_calls": _pending_calls, **parsed})
            return

        # 无tool_name → 这是LLM的最终答复(answer)
        content = full_content or full_reasoning or ""
        logger.info(f"[FC] LLM原始响应(answer): {content}")
        yield ("response", {"type": "answer", "content": content, "thought": ""})

    def _get_openai_tools(self) -> list:
        """获取OpenAI格式工具定义 — 小沈 2026-06-09 添加TTL缓存过期
        P0修复: 多分类加载时传category=None,确保extra_tools对LLM可见 — 小沈 2026-06-11"""
        import time
        current_time = time.time()
        cache_ts = getattr(self, '_cache_timestamp', 0)
        cache_ttl = getattr(self, '_cache_ttl', 300)
        cached = getattr(self, '_cached_openai_tools', None)
        if cached and current_time - cache_ts < cache_ttl:
            return cached
        
        from app.services.tools.registry import tool_registry
        loaded = getattr(self, '_loaded_categories', set())
        category = getattr(self, 'tool_category', None)
        if len(loaded) > 1:
            category = None
        self._cached_openai_tools = tool_registry.to_openai_tools(category=category)
        self._cache_timestamp = current_time
        return self._cached_openai_tools

    def invalidate_tool_cache(self):
        """P2-14修复: 清除工具缓存,工具注册/注销后调用"""
        self._cached_openai_tools = None
        self._cache_timestamp = 0

    def _update_executed_tool_summary(self, tool_name: str, result: dict, tool_params: dict = None):
        """更新已执行工具汇总（含数据摘要）— 小沈 2026-06-09
        
        Args:
            tool_name: 工具名称
            result: 工具执行结果
            tool_params: 工具参数（可选）
        """
        if not hasattr(self, '_executed_tool_summary'):
            self._executed_tool_summary = []
        
        from app.services.agent.observation_formatter import extract_status
        from app.utils.data_utils import extract_data_summary
        
        if isinstance(result, dict):
            status = extract_status(result)
            data_summary = extract_data_summary(result.get("data"))
        else:
            status = "unknown"
            data_summary = ""
        
        entry = f"{tool_name}→{status}"
        if data_summary:
            entry += f"|{data_summary}"
        self._executed_tool_summary.append(entry)

    def _build_executed_tool_summary(self) -> str:
        if not hasattr(self, '_executed_tool_summary') or not self._executed_tool_summary:
            return ""
        done = [s for s in self._executed_tool_summary if '→success' in s]
        if not done:
            return ""
        parts = []
        for entry in done[-8:]:
            if '|' in entry:
                tool_status, data_hint = entry.split('|', 1)
                parts.append(f"{tool_status}({data_hint})")
            else:
                parts.append(entry)
        return ("【已执行工具(勿重复)】" + "; ".join(parts)
                + "\n注意:上述工具已成功执行,结果已在Observation中,禁止再次调用!")

# ... 剩余部分与文档一致
```

**分析**:
- ✅ 注入已执行工具汇总，防止重复调用
- ✅ FC优先：所有场景都过FC流式（2026-06-11小沈重构：无工具时由API处理）
- ✅ 工具提醒惰性注入：不永久写入conversation_history，通过标志位动态注入（2026-06-11小沈）
- ⚠️ **问题**: executed_summary在每次调用时都注入，可能增加上下文长度

**_call_llm_fc_stream()实现（FC-only）**:

```python
async def _call_llm_fc_stream(self, messages: list, openai_tools: list):
    """FC模式流式调用 — 纯FC,无降级 — FC-only重构 2026-06-11 小沈"""
    from app.services.agent.steps import ChunkStep
    from app.utils.json_utils import parse_json

    full_content = ""
    full_reasoning = ""
    stream_error = None
    chunk_step_count = 0

    try:
        async for chunk in self.llm_client.request_stream(
            messages=messages,
            tools=openai_tools, tool_choice="auto",
        ):
            if chunk.stream_error:
                stream_error = chunk.stream_error
                break

            if chunk.content:
                chunk_step_count += 1
                if getattr(chunk, "is_reasoning", False):
                    full_reasoning += chunk.content
                    yield ("chunk", ChunkStep(step=self.llm_call_count, content=chunk.content, is_reasoning=True))
                else:
                    full_content += chunk.content
                    yield ("chunk", ChunkStep(step=self.llm_call_count, content=chunk.content, is_reasoning=False))

            if chunk.is_done:
                break
    except Exception as e:
        logger.error(f"[FC] 流式异常: {e}")
        yield ("response", {"type": "answer", "content": f"LLM调用异常: {e}"})
        return

    if stream_error:
        logger.error(f"[FC] 流式错误: {stream_error}")
        yield ("response", {"type": "answer", "content": f"LLM流式错误: {stream_error}"})
        return

    # 判断是action还是answer
    parsed = parse_json(full_content)
    # 容错: 文本+JSON混合,按"tool_name"标记向前定位{再括号匹配
    if not parsed and full_content:
        _tn = full_content.find('"tool_name"')
        if _tn >= 0:
            _open = full_content.rfind('{', 0, _tn)
            if _open >= 0:
                _depth = 0
                for _j in range(_open, len(full_content)):
                    if full_content[_j] == '{':
                        _depth += 1
                    elif full_content[_j] == '}':
                        _depth -= 1
                        if _depth == 0:
                            parsed = parse_json(full_content[_open:_j+1])
                            break
    if parsed and "tool_name" in parsed:
        fc_context = {
            "tool_call_id": parsed.get("tool_call_id") or "",
            "tool_calls": parsed.get("tool_calls", [])
        }
        # 从tool_calls提取平行调用
        _pending_calls = []
        raw_tool_calls = parsed.get("tool_calls", [])
        if len(raw_tool_calls) > 1:
            primary_id = parsed.get("tool_call_id", "")
            for tc in raw_tool_calls:
                tc_id = tc.get("id", "")
                if tc_id and tc_id != primary_id:
                    func = tc.get("function", {})
                    try:
                        extra_params = json.loads(func.get("arguments", "{}"))
                    except (json.JSONDecodeError, TypeError):
                        extra_params = {}
                    _pending_calls.append({
                        "tool_name": func.get("name", ""),
                        "tool_params": extra_params,
                        "_tool_call_id": tc_id,
                    })
        logger.info(f"[FC] LLM原始响应(action): {full_content}")
        yield ("response", {"type": "action", "fc_context": fc_context, "_pending_calls": _pending_calls, **parsed})
        return

    # 无tool_name → 最终答复(answer)
    content = full_content or full_reasoning or ""
    logger.info(f"[FC] LLM原始响应(answer): {content}")
    yield ("response", {"type": "answer", "content": content, "thought": ""})
```

**分析**:
- ✅ 实时输出chunk给前端（content+reasoning双通道）
- ✅ FC-only: 无降级路径，异常/stream_error直接返回error answer
- ✅ 内联JSON解析：不再依赖 `parse_llm_response.py`
- ✅ 返回dict格式响应（含fc_context），供handler直接使用
- ✅ 支持平行调用提取（从tool_calls解析_pending_calls）

**FC-only重构删除**（2026-06-11）:
- 删除 `_call_llm_text_stream()` 方法
- 删除 `_convert_fc_messages_to_text()` 方法
- 删除 `mode` 参数（`request_stream` 不再有 `mode` 参数）
- 删除 `BaseAIService` 中间层

---

## 五、ReAct循环详细分析

### 5.1 run_react_cycle()（react_cycle.py）

**文件路径**: `backend/app/services/agent/core_agent/react_cycle.py`

**核心职责**:
- 循环调度
- 类型分派
- 产出Step事件

**实现**:

```python
async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step"""
    from app.config import get_config
    if max_steps is None:
        max_steps = get_config().get_max_steps()
    
    # 1. 初始化运行状态
    chunk_buffer = agent._initialize_run_state(task, task_id, context)
    
    step_counter = [0]
    agent.status = AgentStatus.EXECUTING
    
    try:
        while step_counter[0] < max_steps:
            # 2. 处理单步循环
            async for event in _process_single_step(agent, step_counter, chunk_buffer):
                yield event
            
            # 3. 检查是否完成
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED):
                break
            
            # 4. 检查chunk累积超时
            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({step_counter[0]}步),强制停止")
                agent.status = AgentStatus.COMPLETED
                break
    
    except Exception as e:
        logger.error(f"[run_react_cycle] 异常: {e}", exc_info=True)
        yield agent._step_emitter.exit_with_error(
            step_count=step_counter[0], error_type="runtime_error", error_message=str(e),
        )
        agent.status = AgentStatus.FAILED
    
    finally:
        # 5. FAILED时补发FinalStep
        if agent.status == AgentStatus.FAILED and agent.steps:
            last_err = None
            for s in reversed(agent.steps):
                if hasattr(s, '_error_message') and getattr(s, '_error_message', None):
                    last_err = s._error_message
                    break
            yield agent._step_emitter.emit(FinalStep(
                step=step_counter[0],
                response=last_err or "任务执行失败",
                thought="",
            ))
        
        agent._on_after_loop()
        agent._complete_tracked_task(agent.status == AgentStatus.COMPLETED)
```

**_process_single_step()实现（FC-only）**:

```python
async def _process_single_step(agent, step_counter: list, chunk_buffer) -> AsyncGenerator:
    """处理单步循环 — FC-only: llm_response为dict,无需parse_llm_response — 小沈 2026-06-11"""
    step_counter[0] += 1

    llm_response = None
    async for chunk_or_response in agent._call_llm():
        chunk_type, chunk_data = chunk_or_response

        if chunk_type == "chunk":
            yield agent._step_emitter.emit(chunk_data)
        elif chunk_type == "response":
            llm_response = chunk_data

    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        yield agent._step_emitter.exit_with_error(
            step_count=step_counter[0], error_type="empty_response",
            error_message="LLM返回空响应",
        )
        agent.status = AgentStatus.FAILED
        return

    if getattr(getattr(agent, 'llm_client', None), '_cancelled', False):
        yield agent._create_cancelled_chunk()
        yield agent._step_emitter.emit(FinalStep(
            step=step_counter[0],
            response="任务已被中断",
            thought="",
        ))
        agent.status = AgentStatus.COMPLETED
        return

    parsed_type = llm_response.get("type", "answer")
    handler = _TYPE_HANDLERS.get(parsed_type, _DEFAULT_HANDLER)
    async for event in handler(agent, llm_response, "", step_counter, chunk_buffer):
        yield event
```

**_TYPE_HANDLERS映射（FC-only）**:

```python
_TYPE_HANDLERS: OrderedDict[str, callable] = OrderedDict([
    ("action", handle_action),
    ("answer", handle_answer),
])
_DEFAULT_HANDLER = handle_answer
```

**分析**:
- ✅ 薄调度设计，业务逻辑在handlers
- ✅ llm_response现在为dict（非str），无需 `parse_llm_response()` 解析
- ✅ 类型检查改为 `isinstance(llm_response, dict)`（原为 `str`）
- ✅ 从 `llm_response.get("type")` 直接获取类型，跳过解析层
- ✅ 删除了 `TOOL_REMINDER`、`_has_tool_call`、工具提醒标志位逻辑
- ✅ 删除了 `implicit`、`chunk`、`parse_error` 3个handler类型（FC-only下只返回action或answer）

### 5.2 ~~parse_llm_response()~~ **已删除（FC-only重构）**

**原文件**: `backend/app/services/agent/llm_response_parser/parse_llm_response.py`

**重构时删除**（2026-06-11 小沈）:
- `parse_llm_response.py` 文件及目录整体删除
- JSON解析内联到 `_call_llm_fc_stream()` 中（`app/services/agent/universal_agent.py`）
- 原6步解析链（dict→list→JSONArray→Empty→StandardJSON→MixedText）简化为单次 `parse_json()` + 容错括号匹配
- 解析结果类型从5种（action/answer/implicit/chunk/parse_error）精简为2种（action/answer）

---

## 六、重构前的完整流程示例

### 6.1 示例场景：用户要求读取config.json

**Step 1: 用户请求**

```
用户输入: "读取C:/config.json文件内容"
```

**Step 2: 路由层处理**

```python
# chat_stream_v2.py
intent_type = "file"  # CRSS评分判断
agent = AgentFactory.create(intent_type="file", task_id="xxx")
```

**Step 3: Agent初始化**

```python
# UniversalAgent.__init__()
config = resolve_agent_config("file")
self.prompts = FileOperationPrompts()
self.tool_category = ToolCategory.FILE
```

**Step 4: 初始化运行状态**

```python
# _initialize_run_state()
self._on_session_init(task, context)          # 会话初始化回调
sys_prompt = self._get_system_prompt()
# 组装顺序(v2.1精简化版,4段):
# ① _get_system_info()        — 系统信息(OS/路径规则)
# ② _get_project_context()    — 项目上下文(README.md)
# ③ get_core_system_prompt() — 角色+业务规则
# ④ TOOL_CALL_RULES(safety合并) — 回答要求+停止条件+执行效率
# ※ candidates_hint+cross_tool_hint 在_call_llm()每轮注入

task_prompt = self._get_task_prompt("读取C:/config.json文件内容")
self._on_before_loop(sys_prompt, task_prompt, context)  # loop前回调
message_builder.init_history(sys_prompt, task_prompt)
# conversation_history = [
#   {"role": "system", "content": sys_prompt},
#   {"role": "user", "content": task_prompt}
# ]
```

**Step 5: 第一轮LLM调用（FC-only）**

```python
# _call_llm() → _call_llm_fc_stream()
messages = message_builder.prepare_messages_for_llm()
# messages = [
#   {"role": "system", "content": sys_prompt},
#   {"role": "user", "content": task_prompt}
# ]

# LLM返回(FC-only: i...内联解析,直接返回dict)
llm_response = {
  "type": "action",
  "thought": "用户要读取配置文件",
  "reasoning": "调用read_file工具",
  "tool_name": "read_file",
  "tool_params": {"file_paths": ["C:/config.json"]},
  "fc_context": {"tool_call_id": "", "tool_calls": []},
  "_pending_calls": [],
}
```

**Step 6: ~~解析LLM响应~~（FC-only: 跳过,llm_response已是dict）**

在FC-only架构中，`llm_response` 已由 `_call_llm_fc_stream()` 内联解析为dict，无需再调用 `parse_llm_response()`。`_process_single_step()` 直接从 `llm_response.get("type")` 获取类型并分派handler。

**Step 7: 执行工具**

```python
# handle_action()
result = await agent._execute_tool("read_file", {"file_paths": ["C:/config.json"]})
# result = {
#   "code": "SUCCESS",
#   "data": {"content": '{"name": "myapp", "version": "1.0"}'},
#   "message": "文件读取成功"
# }
```

**Step 8: 构建observation（FC-only）**

```python
obs_text = build_observation_text(result, "read_file", {"file_paths": ["C:/config.json"]})
# obs_text = "[Observation] 文件读取成功\n内容: {"name": "myapp", "version": "1.0"}"

# FC-only: add_assistant()已删除,由_append_observation自动构造assistant(tool_calls)配对
message_builder.add_observation(obs_text, llm_call_count=1, fc_context=llm_response.get("fc_context", {}))
# conversation_history末尾追加:
# {"role": "assistant", "tool_calls": [...]}
# {"role": "tool", "content": "[Observation] 文件读取成功...", "tool_call_id": ""}
```

**Step 9: 第二轮LLM调用**

```python
# conversation_history(FC协议格式,role=assistant+tool_calls + role=tool):
# [
#   {"role": "system", "content": sys_prompt},
#   {"role": "user", "content": task_prompt},
#   {"role": "assistant", "tool_calls": [{"function": {"name": "read_file", "arguments": "..."}}]},
#   {"role": "tool", "content": "[Observation] 文件读取成功...", "tool_call_id": ""}
# ]

# LLM返回(FC-only: dict格式)
llm_response = {
  "type": "answer",
  "thought": "文件已成功读取",
  "content": "文件内容: {"name": "myapp", "version": "1.0"}",
  "tool_name": "finish",
}
```

**Step 10: 解析并结束（FC-only）**

```python
# FC-only: llm_response已是dict,直接get("type")="answer"
# _process_single_step()中:
parsed_type = llm_response.get("type", "answer")  # → "answer"
handler = _TYPE_HANDLERS.get("answer", _DEFAULT_HANDLER)  # → handle_answer

# handle_answer()
agent.status = AgentStatus.COMPLETED
yield FinalStep(response="文件内容: ...")
```

---

