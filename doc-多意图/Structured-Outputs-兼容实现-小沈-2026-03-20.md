# Structured Outputs 兼容实现方案

**创建时间**: 2026-03-20 09:05:00
**版本**: v1.0
**编写人**: 小沈
**存放位置**: `D:\OmniAgentAs-desk\doc-ReAct重构\Structured-Outputs-兼容实现-小沈-2026-03-20.md`

---

## 一、问题背景

### 1.1 不同 LLM 支持情况

| LLM | response_format | tools/function_calling | 推荐策略 |
|-----|----------------|------------------------|---------|
| Claude | ✅ 支持 | ✅ 支持 | response_format |
| GPT-4 | ✅ 支持 | ✅ 支持 | response_format |
| LongCat | ❌ 不支持 | ✅ **已验证** | tools |
| GLM | ⚠️ 待测试 | ⚠️ 待测试 | - |
| DeepSeek | ⚠️ 待测试 | ⚠️ 待测试 | - |

### 1.2 兼容实现需求

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM 类型自动检测                          │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ↓               ↓               ↓
      Claude/GPT-4     LongCat          其他
            │               │               │
            ↓               ↓               ↓
    response_format    tools        降级到 Prompt
```

---

## 二、兼容实现架构

### 2.1 文件结构

```
backend/
├── app/
│   └── services/
│       ├── base.py                          【修改】
│       │   ├── BaseAIService.chat_stream()
│       │   └── BaseAIService.chat_structured()  【新增】
│       │
│       └── file_operations/
│           ├── react_schema.py              【新建】
│           │   ├── get_response_format_schema()  # Claude/GPT-4
│           │   └── get_tools_schema()              # LongCat/其他
│           │
│           ├── tools.py                     【修改】
│           │   └── get_llm_tools_config()      # 获取 LLM 适配配置
│           │
│           └── agent.py                     【修改】
│               └── FileOperationAgent       # 兼容模式
```

### 2.2 LLM 策略枚举

```python
# backend/app/services/file_operations/llm_strategy.py

from enum import Enum
from typing import Optional, List, Dict, Any


class LLMStrategy(Enum):
    """
    LLM Structured Output 策略
    
    根据不同 LLM 类型选择合适的实现方式
    """
    # Claude / GPT-4: 使用 response_format
    RESPONSE_FORMAT = "response_format"
    
    # LongCat / OpenAI兼容: 使用 tools/function_calling
    FUNCTION_CALLING = "function_calling"
    
    # 不支持: 降级到 Prompt 方式
    PROMPT_FALLBACK = "prompt_fallback"


class LLMCompatibility:
    """
    LLM 兼容性配置
    
    定义每个 LLM 支持的功能
    """
    
    # 已验证支持的 LLM
    SUPPORTED_LLMS = {
        # Claude 系列
        "claude": {
            "strategy": LLMStrategy.RESPONSE_FORMAT,
            "supports": ["response_format", "tools"]
        },
        "claude-3-5-sonnet": {
            "strategy": LLMStrategy.RESPONSE_FORMAT,
            "supports": ["response_format", "tools"]
        },
        "claude-3-opus": {
            "strategy": LLMStrategy.RESPONSE_FORMAT,
            "supports": ["response_format", "tools"]
        },
        
        # GPT 系列
        "gpt-4": {
            "strategy": LLMStrategy.RESPONSE_FORMAT,
            "supports": ["response_format", "tools"]
        },
        "gpt-4o": {
            "strategy": LLMStrategy.RESPONSE_FORMAT,
            "supports": ["response_format", "tools"]
        },
        "gpt-4-turbo": {
            "strategy": LLMStrategy.RESPONSE_FORMAT,
            "supports": ["response_format", "tools"]
        },
        
        # LongCat 系列
        "longcat-flash-thinking": {
            "strategy": LLMStrategy.FUNCTION_CALLING,
            "supports": ["tools"]
        },
        "longcat-flash-thinking-2601": {
            "strategy": LLMStrategy.FUNCTION_CALLING,
            "supports": ["tools"]
        },
    }
    
    @classmethod
    def get_strategy(cls, model: str) -> LLMStrategy:
        """
        获取 LLM 使用的策略
        
        Args:
            model: 模型名称（如 "longcat-flash-thinking-2601"）
        
        Returns:
            LLMStrategy 枚举值
        """
        model_lower = model.lower()
        
        for supported_model, config in cls.SUPPORTED_LLMS.items():
            if supported_model in model_lower:
                return config["strategy"]
        
        # 默认降级到 Prompt 方式
        return LLMStrategy.PROMPT_FALLBACK
    
    @classmethod
    def supports(cls, model: str, feature: str) -> bool:
        """
        检查 LLM 是否支持某个功能
        
        Args:
            model: 模型名称
            feature: 功能名称（response_format, tools）
        
        Returns:
            True 如果支持
        """
        strategy = cls.get_strategy(model)
        
        if strategy == LLMStrategy.RESPONSE_FORMAT:
            return feature in ["response_format", "tools"]
        elif strategy == LLMStrategy.FUNCTION_CALLING:
            return feature == "tools"
        else:
            return False
```

---

## 三、Schema 生成兼容实现

### 3.1 react_schema.py

**文件**: `backend/app/services/file_operations/react_schema.py`

```python
"""
ReAct Agent Structured Output Schema 定义

提供两种 Schema 生成方式：
1. response_format: Claude/GPT-4 使用
2. tools: LongCat/其他 LLM 使用

【新增】2026-03-20 小沈
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field

from app.services.file_operations.llm_strategy import LLMStrategy, LLMCompatibility


# ============================================================
# 1. ReAct Output Schema（用于 response_format）
# ============================================================

class ToolParams(BaseModel):
    """工具参数 Schema"""
    
    # list_directory
    dir_path: Optional[str] = None
    recursive: Optional[bool] = False
    max_depth: Optional[int] = 10
    page_size: Optional[int] = 100
    page_token: Optional[str] = None
    
    # read_file / write_file / delete_file
    file_path: Optional[str] = None
    offset: Optional[int] = 1
    limit: Optional[int] = 2000
    content: Optional[str] = None
    encoding: Optional[str] = "utf-8"
    
    # move_file
    source_path: Optional[str] = None
    destination_path: Optional[str] = None
    
    # search_files
    pattern: Optional[str] = None
    path: Optional[str] = "."
    file_pattern: Optional[str] = "*"
    use_regex: Optional[bool] = False
    max_results: Optional[int] = 1000
    
    # generate_report
    output_dir: Optional[str] = None
    
    # finish
    result: Optional[str] = None


class ReActOutput(BaseModel):
    """
    ReAct Agent 输出 Schema
    
    用于 Claude/GPT-4 的 response_format
    """
    thought: str = Field(description="思考过程，解释为什么选择这个工具")
    action_tool: str = Field(
        description="工具名称：finish, read_file, write_file, list_directory, delete_file, move_file, search_files, generate_report"
    )
    params: ToolParams = Field(description="工具参数")


def get_response_format_schema() -> Dict[str, Any]:
    """
    获取 response_format 的 JSON Schema
    
    用于 Claude/GPT-4
    """
    schema = ReActOutput.model_json_schema()
    return {
        "type": "json_object",
        "json_schema": schema
    }


# ============================================================
# 2. Tools Schema（用于 function_calling）
# ============================================================

def get_tools_schema_from_tool_def(tool_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    从工具定义生成 OpenAI tools 格式
    
    Args:
        tool_def: 工具定义（来自 get_registered_tools）
    
    Returns:
        OpenAI tools 格式
    """
    name = tool_def.get("name", "")
    description = tool_def.get("description", "")
    schema = tool_def.get("input_schema", {})
    examples = tool_def.get("input_examples", [])
    
    # 提取 properties 和 required
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    
    # 转换为 OpenAI tools 格式
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": _build_description(description, examples),
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }
    }


def _build_description(description: str, examples: List[Dict]) -> str:
    """
    构建完整的工具描述（包含使用限制）
    
    Args:
        description: 原始描述
        examples: 示例
    
    Returns:
        完整描述，包含参数命名限制
    """
    # 提取工具名
    if "list_directory" in description:
        restriction = "\n\n【重要】必须使用 dir_path 作为参数名，不要使用 directory_path、path。"
    elif "read_file" in description or "write_file" in description:
        restriction = "\n\n【重要】必须使用 file_path 作为参数名，不要使用 filepath、path。"
    elif "move_file" in description:
        restriction = "\n\n【重要】必须使用 source_path 和 destination_path，不要使用 src、dst。"
    else:
        restriction = ""
    
    return description + restriction


def get_tools_schema(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从工具定义列表生成 tools Schema
    
    用于 LongCat 等使用 Function Calling 的 LLM
    """
    return [get_tools_schema_from_tool_def(tool) for tool in tools]


# ============================================================
# 3. 统一接口
# ============================================================

def get_structured_schema(
    model: str,
    tools: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    统一获取 Schema（根据 LLM 类型自动选择）
    
    Args:
        model: 模型名称
        tools: 工具定义列表（用于 function_calling 模式）
    
    Returns:
        包含 strategy 和 schema 的字典
    """
    strategy = LLMCompatibility.get_strategy(model)
    
    if strategy == LLMStrategy.RESPONSE_FORMAT:
        return {
            "strategy": strategy,
            "schema": get_response_format_schema(),
            "method": "response_format"
        }
    elif strategy == LLMStrategy.FUNCTION_CALLING:
        if tools is None:
            from app.services.file_operations.tools import get_registered_tools
            tools = get_registered_tools()
        return {
            "strategy": strategy,
            "schema": get_tools_schema(tools),
            "method": "tools"
        }
    else:
        return {
            "strategy": strategy,
            "schema": None,
            "method": "prompt"
        }
```

---

## 四、BaseAIService 兼容实现

### 4.1 修改 base.py

**文件**: `backend/app/services/base.py`

```python
class BaseAIService:
    """
    通用 AI 服务（兼容 Structured Outputs）
    """
    
    async def chat_structured(
        self,
        message: str,
        history: Optional[List[Message]] = None,
        schema_info: Optional[Dict[str, Any]] = None
    ) -> ChatResponse:
        """
        发送结构化对话请求（兼容多种 LLM）
        
        Args:
            message: 用户消息
            history: 对话历史
            schema_info: Schema 信息（来自 get_structured_schema）
        
        Returns:
            ChatResponse
        """
        messages = self._build_messages(message, history)
        method = schema_info.get("method", "prompt") if schema_info else "prompt"
        
        request_json = {
            "model": self.model,
            "messages": messages
        }
        
        # 根据方法添加对应参数
        if method == "response_format" and schema_info:
            request_json["response_format"] = schema_info["schema"]
        elif method == "tools" and schema_info:
            request_json["tools"] = schema_info["schema"]
            request_json["tool_choice"] = "auto"
        
        try:
            response = await self.client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json
            )
            
            if response.status_code != 200:
                return ChatResponse(
                    content="", 
                    model=self.model, 
                    error=f"API Error: {response.status_code}"
                )
            
            result = response.json()
            choices = result.get("choices", [])
            if not choices:
                return ChatResponse(content="", model=self.model, error="No response")
            
            msg = choices[0].get("message", {})
            
            # 处理不同类型的响应
            if method == "tools":
                # Function Calling 响应
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    return ChatResponse(
                        content=json.dumps(tool_calls),
                        model=self.model,
                        provider=self.provider
                    )
            
            # 普通响应
            content = msg.get("content", "")
            return ChatResponse(content=content, model=self.model, provider=self.provider)
            
        except Exception as e:
            return ChatResponse(content="", model=self.model, error=str(e))
```

---

## 五、Agent 兼容实现

### 5.1 修改 agent.py

**文件**: `backend/app/services/file_operations/agent.py`

```python
class FileOperationAgent:
    """
    文件操作 ReAct Agent（兼容 Structured Outputs）
    """
    
    def __init__(
        self,
        llm_client,
        session_id: str,
        file_tools: Optional[FileTools] = None,
        max_steps: int = 20,
        model: Optional[str] = None  # 【新增】用于自动选择策略
    ):
        # ... 现有初始化 ...
        
        # 【新增】Structured Output 配置
        self.model = model or getattr(llm_client, 'model', 'unknown')
        self._init_structured_config()
    
    def _init_structured_config(self):
        """初始化 Structured Output 配置"""
        from app.services.file_operations.react_schema import get_structured_schema
        from app.services.file_operations.tools import get_registered_tools
        
        tools = get_registered_tools()
        self.schema_info = get_structured_schema(self.model, tools)
        self.strategy = self.schema_info["strategy"]
        
        logger.info(f"[Agent] Using strategy: {self.strategy.value} for model: {self.model}")
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应"""
        # ... 现有代码 ...
        
        # 根据策略选择调用方式
        if self.strategy == LLMStrategy.RESPONSE_FORMAT:
            # Claude/GPT-4: 使用 response_format
            response = await self.llm_client.chat_structured(
                message=last_message,
                history=history_messages,
                schema_info=self.schema_info
            )
        elif self.strategy == LLMStrategy.FUNCTION_CALLING:
            # LongCat: 使用 tools
            response = await self.llm_client.chat_structured(
                message=last_message,
                history=history_messages,
                schema_info=self.schema_info
            )
        else:
            # 降级: 使用普通调用
            response = await self.llm_client(
                message=last_message,
                history=history_messages
            )
        
        # ... 后续处理 ...
    
    def _parse_structured_response(self, content: str) -> Dict[str, Any]:
        """
        解析结构化响应
        
        根据不同策略解析响应
        """
        if self.strategy == LLMStrategy.FUNCTION_CALLING:
            # Function Calling 响应解析
            try:
                tool_calls = json.loads(content)
                if isinstance(tool_calls, list) and tool_calls:
                    tc = tool_calls[0]
                    func = tc.get("function", {})
                    args = json.loads(func.get("arguments", "{}"))
                    return {
                        "content": f"Tool call: {func.get('name')}",
                        "action_tool": func.get("name"),
                        "params": args
                    }
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Prompt 响应解析（原有逻辑）
        return self.parser.parse_response(content)
```

---

## 六、使用示例

### 6.1 自动适配（推荐）

```python
from app.services.file_operations.agent import FileOperationAgent
from app.services.file_operations.tools import get_file_tools

# 方式1: 自动适配（推荐）
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    model="longcat-flash-thinking-2601"  # 自动选择合适策略
)
# 输出: [Agent] Using strategy: function_calling for model: longcat-flash-thinking-2601

agent2 = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    model="claude-3-5-sonnet"  # 自动选择 response_format
)
# 输出: [Agent] Using strategy: response_format for model: claude-3-5-sonnet

# 使用方式不变
result = await agent.run("查看D盘根目录")
```

### 6.2 手动指定

```python
# 方式2: 手动指定
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    model="unknown-model",
    use_structured_output=True,
    force_strategy="function_calling"  # 强制使用 Function Calling
)
```

### 6.3 降级模式

```python
# 方式3: 降级到 Prompt 方式
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    model="unknown-model"  # 不支持的模型
)
# 输出: [Agent] Using strategy: prompt_fallback for model: unknown-model
# 自动降级到原有的 Prompt 方式
```

---

## 七、策略选择流程图

```
                    ┌─────────────────────────┐
                    │  获取 model 名称        │
                    └───────────┬─────────────┘
                                │
                    ┌─────────▼─────────────┐
                    │  匹配 LLM 配置        │
                    └─────────┬─────────────┘
                                │
            ┌──────────────────┼──────────────────┐
            │                  │                  │
    ┌───────▼───────┐  ┌───────▼───────┐  ┌─────▼─────┐
    │ Claude/GPT-4  │  │   LongCat     │  │   其他    │
    └───────┬───────┘  └───────┬───────┘  └─────┬─────┘
            │                  │                  │
            ▼                  ▼                  ▼
    ┌──────────────┐  ┌──────────────┐  ┌────────────┐
    │ response_    │  │ tools/       │  │  Prompt   │
    │ format       │  │ function_     │  │  Fallback │
    └──────────────┘  │ calling       │  └────────────┘
                      └──────────────┘
```

---

## 八、测试验证

### 8.1 单元测试

```python
# tests/test_llm_compatibility.py

def test_longcat_strategy():
    """测试 LongCat 使用 Function Calling"""
    from app.services.file_operations.llm_strategy import LLMCompatibility, LLMStrategy
    
    strategy = LLMCompatibility.get_strategy("longcat-flash-thinking-2601")
    assert strategy == LLMStrategy.FUNCTION_CALLING
    
    assert LLMCompatibility.supports("longcat-flash-thinking-2601", "tools") == True
    assert LLMCompatibility.supports("longcat-flash-thinking-2601", "response_format") == False

def test_claude_strategy():
    """测试 Claude 使用 response_format"""
    from app.services.file_operations.llm_strategy import LLMCompatibility, LLMStrategy
    
    strategy = LLMCompatibility.get_strategy("claude-3-5-sonnet")
    assert strategy == LLMStrategy.RESPONSE_FORMAT
    
    assert LLMCompatibility.supports("claude-3-5-sonnet", "response_format") == True
    assert LLMCompatibility.supports("claude-3-5-sonnet", "tools") == True

def test_unknown_strategy():
    """测试未知模型降级"""
    from app.services.file_operations.llm_strategy import LLMCompatibility, LLMStrategy
    
    strategy = LLMCompatibility.get_strategy("unknown-model")
    assert strategy == LLMStrategy.PROMPT_FALLBACK
```

### 8.2 集成测试

```python
# tests/test_agent_compatibility.py

@pytest.mark.asyncio
async def test_longcat_agent():
    """测试 LongCat Agent"""
    agent = FileOperationAgent(
        llm_client=llm_client,
        session_id="test",
        model="longcat-flash-thinking-2601"
    )
    assert agent.strategy == LLMStrategy.FUNCTION_CALLING
    assert agent.schema_info["method"] == "tools"

@pytest.mark.asyncio
async def test_claude_agent():
    """测试 Claude Agent"""
    agent = FileOperationAgent(
        llm_client=llm_client,
        session_id="test",
        model="claude-3-5-sonnet"
    )
    assert agent.strategy == LLMStrategy.RESPONSE_FORMAT
    assert agent.schema_info["method"] == "response_format"
```

---

## 九、实现计划

### 阶段1: 核心模块（约2小时）
- [ ] 创建 `llm_strategy.py`（LLM 策略枚举和配置）
- [ ] 创建 `react_schema.py`（Schema 生成）
- [ ] 修改 `base.py`（添加 `chat_structured` 方法）

### 阶段2: Agent 集成（约1小时）
- [ ] 修改 `agent.py`（适配多种策略）
- [ ] 添加自动检测逻辑

### 阶段3: 测试验证（约1小时）
- [ ] 编写单元测试
- [ ] 编写集成测试
- [ ] 实际调用测试

---

**文档结束**

**编写时间**: 2026-03-20 09:05:00
**编写人**: 小沈
**版本**: v1.0
