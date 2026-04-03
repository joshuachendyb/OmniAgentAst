# Structured Outputs 实现方案

**创建时间**: 2026-03-20 08:30:00
**版本**: v1.0
**编写人**: 小沈
**存放位置**: `D:\OmniAgentAs-desk\doc-ReAct重构\Structured-Outputs-实现方案-小沈-2026-03-20.md`

---

## 一、问题背景

### 1.1 当前方案

小强实现的**三层防御策略**（软约束）：
```
第一层：System Prompt全局规则（FORBIDDEN参数名）
       ↓
第二层：详细工具Description（每个工具）
       ↓
第三层：input_examples示例（正确用法示范）
       ↓
兜底：agent.py参数映射代码
```

**优点**：无需 LLM API 支持，通用性强
**缺点**：依赖 LLM 理解能力，可能偶尔出错

### 1.2 Structured Outputs 方案

Structured Outputs 是 Claude/OpenAI 等 LLM API 提供的**强制约束**功能：

```
┌─────────────────────────────────────────────────┐
│              LLM API 层强制约束                  │
│   只能输出 Schema 定义的字段，参数名必须匹配      │
│   不可能输出 directory_path，只能是 dir_path     │
└─────────────────────────────────────────────────┘
```

**优点**：参数名绝对正确，无需容错代码
**缺点**：需要 LLM API 支持

### 1.3 两种方案的关系

```
当前（3层软约束）：
Prompt → Description → Examples → agent.py容错

Structured Outputs（硬约束）：
API层强制约束 → 可简化agent.py容错

关系：互补/增强，不是替代
```

---

## 二、技术方案

### 2.1 支持 Structured Outputs 的 LLM

| LLM | response_format | tools/function_calling | 推荐方案 |
|-----|----------------|------------------------|---------|
| **Claude** | ✅ 支持 | ✅ 支持 | response_format |
| **GPT-4** | ✅ 支持 | ✅ 支持 | response_format |
| **LongCat** | ❌ 不支持 | ✅ **支持** | tools (Function Calling) |
| **GLM** | ⚠️ 待测试 | ⚠️ 待测试 | - |
| **DeepSeek** | ⚠️ 待测试 | ⚠️ 待测试 | - |

**测试时间**: 2026-03-20 08:51:00

**LongCat 测试结果**:
```
# response_format 测试
Status: 200
Content-Length: 0  ← 不支持，返回空响应

# tools/function_calling 测试
Status: 200
tool_calls: [{'id': 'call_xxx', 'type': 'function', 
              'function': {'name': 'list_directory', 
                           'arguments': '{"dir_path": "D:\\"}'}}]
              ← 正确返回了 tool_calls，参数名正确
```

**结论**: LongCat **不支持** `response_format`，但 **支持** `tools/function_calling`，可以通过 Function Calling 实现参数约束！

### 2.2 Claude API 实现方式

```python
# Claude API 调用示例
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[...],
    system="You are a helpful assistant.",
    # Structured Outputs 配置
    extra_headers={
        "anthropic-beta": "structured-outputs-2025-05-14"
    },
    response_format={
        "type": "json_object",
        "json_schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string"},
                "action_tool": {"type": "string"},
                "params": {
                    "type": "object",
                    "properties": {
                        "dir_path": {"type": "string"},
                        "recursive": {"type": "boolean"}
                    },
                    "required": ["dir_path"]
                }
            },
            "required": ["thought", "action_tool", "params"]
        }
    }
)
```

### 2.3 OpenAI 兼容 API 实现方式

```python
# OpenAI 兼容 API 调用示例
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    response_format={
        "type": "json_object",
        "json_schema": {
            "type": "object",
            "properties": {
                "thought": {"type": "string"},
                "action_tool": {"type": "string"},
                "params": {"type": "object"}
            },
            "required": ["thought", "action_tool", "params"]
        }
    }
)
```

### 2.4 LongCat Function Calling 实现方式（已验证支持）

**测试结果**: LongCat **支持** `tools` (Function Calling) 参数，可以正确约束参数名！

```python
# LongCat API 调用示例（Function Calling）
data = {
    "model": "LongCat-Flash-Thinking-2601",
    "messages": [{"role": "user", "content": "查看D盘根目录"}],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "列出目录内容",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dir_path": {
                            "type": "string",
                            "description": "目录的完整路径（必须是绝对路径）"
                        },
                        "recursive": {
                            "type": "boolean",
                            "description": "是否递归列出子目录"
                        }
                    },
                    "required": ["dir_path"]
                }
            }
        }
    ],
    "tool_choice": "auto"
}

# 响应示例
{
    "choices": [{
        "message": {
            "role": "assistant",
            "tool_calls": [{
                "id": "call_xxx",
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "arguments": '{"dir_path": "D:\\\\"}'
                }
            }]
        }
    }]
}
```

**优势**:
1. **参数名强制正确**: LLM 只能使用 Schema 中定义的参数名
2. **自动 JSON 解析**: `arguments` 已经是正确的 JSON 格式
3. **无需容错代码**: 不再需要 agent.py 的参数映射

**与 response_format 的区别**:

| 特性 | response_format | tools (Function Calling) |
|------|----------------|---------------------------|
| 适用 LLM | Claude, GPT-4 | 所有 OpenAI 兼容 API |
| 返回格式 | 纯 JSON | tool_calls 格式 |
| 参数约束 | 完整 Schema | 每个工具独立 Schema |
| 实现复杂度 | 较高 | 中等 |

**推荐策略**:

```
Claude / GPT-4 → 使用 response_format（更灵活）
LongCat       → 使用 tools/function_calling（已验证支持）
其他 LLM     → 根据测试结果选择
```

---

## 三、实现方案

### 3.1 文件结构

```
backend/
├── app/
│   └── services/
│       ├── base.py                          【修改】
│       │   ├── BaseAIService.chat_stream()  添加response_format参数
│       │   └── StreamChunk                  添加raw_data字段
│       │
│       └── file_operations/
│           ├── tools.py                     【新增/修改】
│           │   └── ReActOutputSchema         ReAct输出Schema定义
│           │
│           ├── prompts.py                   
│           │   └── get_react_output_schema() 获取当前工具的Schema
│           │
│           └── agent.py                     【修改】
│               └── FileOperationAgent       支持Structured Outputs
```

### 3.2 实现步骤

#### 步骤1：定义 ReAct Output Schema

**文件**: `backend/app/services/file_operations/react_schema.py`（新建）

```python
"""
ReAct Agent 输出 Schema 定义

定义 LLM 必须返回的 JSON Schema，确保参数名正确

【新增】2026-03-20 小沈
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class ToolParams(BaseModel):
    """工具参数 Schema（根据不同工具动态生成）"""
    
    # list_directory 参数
    dir_path: Optional[str] = Field(default=None, description="目录的完整路径")
    recursive: Optional[bool] = Field(default=False, description="是否递归列出子目录")
    max_depth: Optional[int] = Field(default=10, ge=1, le=50, description="最大递归深度")
    page_size: Optional[int] = Field(default=100, ge=1, le=500, description="每页返回数量")
    
    # read_file/write_file/delete_file 参数
    file_path: Optional[str] = Field(default=None, description="文件的完整路径")
    offset: Optional[int] = Field(default=1, ge=1, description="起始行号")
    limit: Optional[int] = Field(default=2000, ge=1, le=10000, description="最大读取行数")
    content: Optional[str] = Field(default=None, description="要写入文件的内容")
    encoding: Optional[str] = Field(default="utf-8", description="文件编码")
    
    # move_file 参数
    source_path: Optional[str] = Field(default=None, description="源文件或目录的完整路径")
    destination_path: Optional[str] = Field(default=None, description="目标路径")
    
    # search_files 参数
    pattern: Optional[str] = Field(default=None, description="搜索内容的关键字或正则表达式")
    path: Optional[str] = Field(default=".", description="搜索的起始目录")
    file_pattern: Optional[str] = Field(default="*", description="文件名匹配模式")
    use_regex: Optional[bool] = Field(default=False, description="是否使用正则表达式搜索")
    max_results: Optional[int] = Field(default=1000, ge=1, le=10000, description="最大搜索结果数量")
    
    # generate_report 参数
    output_dir: Optional[str] = Field(default=None, description="报告输出目录")


class ReActOutput(BaseModel):
    """
    ReAct Agent 输出 Schema
    
    LLM 必须严格按照此 Schema 输出，否则调用失败
    """
    thought: str = Field(description="思考过程，解释为什么选择这个工具")
    action_tool: str = Field(
        description="工具名称，必须是以下之一：finish, read_file, write_file, list_directory, delete_file, move_file, search_files, generate_report"
    )
    params: ToolParams = Field(description="工具参数，必须使用正确的参数名")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "thought": "用户想查看D盘根目录的文件列表",
                    "action_tool": "list_directory",
                    "params": {
                        "dir_path": "D:/",
                        "recursive": False
                    }
                },
                {
                    "thought": "用户想读取配置文件查看内容",
                    "action_tool": "read_file",
                    "params": {
                        "file_path": "C:/Users/username/config.json",
                        "offset": 1,
                        "limit": 100
                    }
                },
                {
                    "thought": "任务已完成，用户的请求已满足",
                    "action_tool": "finish",
                    "params": {
                        "result": "已完成用户请求的所有操作"
                    }
                }
            ]
        }


def get_react_output_schema() -> Dict[str, Any]:
    """
    获取 ReAct Output 的 JSON Schema
    
    用于 LLM API 的 response_format 参数
    """
    return ReActOutput.model_json_schema()


def get_react_output_schema_strict() -> Dict[str, Any]:
    """
    获取严格模式的 ReAct Output Schema（用于 Claude）
    """
    schema = ReActOutput.model_json_schema()
    return {
        "type": "json_object",
        "json_schema": schema
    }
```

#### 步骤2：修改 BaseAIService 支持 response_format

**文件**: `backend/app/services/base.py`

**修改点**：

```python
# 1. 修改 StreamChunk 类，添加 raw_data 字段
class StreamChunk:
    def __init__(self, content: str, model: str, is_done: bool = False, 
                 stream_error: Optional[str] = None, 
                 raw_data: Optional[Dict[str, Any]] = None,  # 【新增】Structured Output
                 ...):
        self.raw_data = raw_data  # 存储完整的结构化输出

# 2. 修改 chat_stream 方法签名
async def chat_stream(
    self, 
    message: str, 
    history: Optional[List[Message]] = None,
    response_format: Optional[Dict[str, Any]] = None  # 【新增】Structured Outputs
) -> AsyncGenerator[StreamChunk, None]:
    
    # 3. 构建请求时添加 response_format
    request_json = {
        "model": self.model,
        "messages": messages,
        "stream": True
    }
    
    # 【新增】如果提供了 response_format，添加到请求中
    if response_format:
        request_json["response_format"] = response_format
    
    # 4. 解析响应时，提取完整结构化输出
    # （根据实际 API 返回格式处理）

# 4. 添加新方法：chat_structured（非流式，用于 Structured Outputs）
async def chat_structured(
    self, 
    message: str, 
    history: Optional[List[Message]] = None,
    response_format: Optional[Dict[str, Any]] = None
) -> ChatResponse:
    """
    发送对话请求（Structured Output）
    
    适用于需要强制输出格式的场景（如 ReAct Agent）
    """
    try:
        messages = self._build_messages(message, history)
        
        request_json = {
            "model": self.model,
            "messages": messages
        }
        
        if response_format:
            request_json["response_format"] = response_format
        
        response = await self.client.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json=request_json
        )
        
        if response.status_code != 200:
            return ChatResponse(content="", model=self.model, error=f"API Error: {response.status_code}")
        
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            return ChatResponse(content=content, model=self.model)
        else:
            return ChatResponse(content="", model=self.model, error="No response")
            
    except Exception as e:
        return ChatResponse(content="", model=self.model, error=str(e))
```

#### 步骤3：修改 FileOperationAgent 支持 Structured Outputs

**文件**: `backend/app/services/file_operations/agent.py`

**修改点**：

```python
# 1. 添加 structured_output 参数
class FileOperationAgent:
    def __init__(
        self,
        llm_client: Callable[..., Any],
        session_id: str,
        file_tools: Optional[FileTools] = None,
        max_steps: int = 20,
        use_structured_output: bool = False  # 【新增】
    ):
        self.use_structured_output = use_structured_output
        
        # 导入 Schema 定义
        if use_structured_output:
            from app.services.file_operations.react_schema import get_react_output_schema_strict
            self.response_format = get_react_output_schema_strict()
        else:
            self.response_format = None
    
    # 2. 修改 _get_llm_response 方法
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应"""
        # ... 现有代码 ...
        
        # 【修改】根据配置决定是否使用 Structured Output
        if self.use_structured_output and hasattr(self.llm_client, 'chat_structured'):
            response = await self.llm_client.chat_structured(
                message=last_message,
                history=history_messages,
                response_format=self.response_format
            )
        else:
            response = await self.llm_client(
                message=last_message,
                history=history_messages
            )
        
        # ... 后续代码 ...

# 3. 添加 run_structured 方法
async def run_structured(
    self,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    system_prompt: Optional[str] = None
) -> AgentResult:
    """
    使用 Structured Output 运行 Agent
    
    强制 LLM 按 Schema 输出，确保参数名正确
    """
    return await self._run_internal(task, context, system_prompt, use_structured_output=True)
```

#### 步骤4：添加配置开关

**文件**: `backend/app/config.py` 或 `config.yaml`

```yaml
# config.yaml
llm:
  # Structured Outputs 配置
  structured_output:
    enabled: false  # 是否启用 Structured Outputs
    fallback_to_text: true  # 如果不支持，是否回退到文本解析
    
  # 支持的 LLM
  supported_providers:
    - claude: response_format
    - gpt4: response_format
    - longcat: tools  # 使用 Function Calling
```

---

#### 步骤5：LongCat Function Calling 实现（推荐用于 LongCat）

**文件**: `backend/app/services/base.py`

**新增方法**:

```python
async def chat_with_tools(
    self,
    message: str,
    history: Optional[List[Message]] = None,
    tools: Optional[List[Dict[str, Any]]] = None
) -> ChatResponse:
    """
    发送对话请求（使用 Function Calling）
    
    适用于 LongCat 等支持 tools 的 LLM
    """
    try:
        messages = self._build_messages(message, history)
        
        request_json = {
            "model": self.model,
            "messages": messages
        }
        
        # 如果提供了 tools，添加到请求中
        if tools:
            request_json["tools"] = tools
            request_json["tool_choice"] = "auto"
        
        response = await self.client.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json=request_json
        )
        
        if response.status_code != 200:
            return ChatResponse(content="", model=self.model, error=f"API Error: {response.status_code}")
        
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            msg = choices[0].get("message", {})
            # 检查是否有 tool_calls
            tool_calls = msg.get("tool_calls", [])
            if tool_calls:
                # 返回工具调用信息
                return ChatResponse(
                    content=json.dumps(tool_calls),
                    model=self.model,
                    provider=self.provider
                )
            else:
                # 普通文本响应
                content = msg.get("content", "")
                return ChatResponse(content=content, model=self.model, provider=self.provider)
        else:
            return ChatResponse(content="", model=self.model, error="No response")
            
    except Exception as e:
        return ChatResponse(content="", model=self.model, error=str(e))
```

**文件**: `backend/app/services/file_operations/react_schema.py`

**新增工具 Schema 生成**:

```python
def get_tools_schema(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    从工具定义生成 Function Calling Schema
    
    Args:
        tools: 工具定义列表（来自 get_registered_tools）
    
    Returns:
        OpenAI 格式的 tools 列表
    """
    openai_tools = []
    
    for tool in tools:
        name = tool.get("name", "")
        description = tool.get("description", "")
        schema = tool.get("input_schema", {})
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        
        # 转换为 OpenAI tools 格式
        openai_tool = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        openai_tools.append(openai_tool)
    
    return openai_tools


def get_finish_tool() -> Dict[str, Any]:
    """
    获取 finish 工具定义（用于结束任务）
    
    注意: finish 不是真正的工具调用，而是通过文本响应告知 Agent 任务完成
    """
    return {
        "type": "finish",
        "description": "结束任务，返回最终结果"
    }
```

---

## 四、使用示例

### 4.1 Claude / GPT-4: 使用 response_format

```python
from app.services.file_operations.agent import FileOperationAgent

# Claude / GPT-4 使用 response_format
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    use_structured_output=True,  # 启用
    structured_mode="response_format"  # 使用 response_format
)

result = await agent.run_structured("查看D盘有什么文件")
```

### 4.2 LongCat: 使用 Function Calling

```python
from app.services.file_operations.agent import FileOperationAgent
from app.services.file_operations.tools import get_registered_tools
from app.services.file_operations.react_schema import get_tools_schema

# LongCat 使用 Function Calling
tools = get_registered_tools()
tools_schema = get_tools_schema(tools)

agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    use_structured_output=True,
    structured_mode="tools",  # 使用 Function Calling
    tools=tools_schema
)

result = await agent.run_with_tools("查看D盘有什么文件")
```

### 4.3 兼容模式（默认）

```python
# 不启用，使用原有 Prompt 方式
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    use_structured_output=False  # 默认
)

result = await agent.run("查看D盘有什么文件")
```

### 4.4 自动检测

```python
# 根据 LLM 类型自动决定
async def create_agent(llm_provider: str, ...) -> FileOperationAgent:
    provider = llm_provider.lower()
    
    if provider in ["claude", "gpt-4", "gpt-4o"]:
        mode = "response_format"
    elif provider in ["longcat"]:
        mode = "tools"
    else:
        mode = "none"  # 不支持，降级到文本
    
    return FileOperationAgent(
        llm_client=llm_client,
        session_id=session_id,
        use_structured_output=(mode != "none"),
        structured_mode=mode,
        tools=tools_schema if mode == "tools" else None
    )
```

---

## 五、测试计划

### 5.1 单元测试

```python
# tests/test_react_schema.py
def test_react_output_schema_valid():
    """测试 Schema 生成"""
    schema = get_react_output_schema()
    assert "properties" in schema
    assert "thought" in schema["properties"]
    assert "action_tool" in schema["properties"]
    assert "params" in schema["properties"]

def test_react_output_validation():
    """测试输出验证"""
    valid_output = {
        "thought": "用户想查看D盘",
        "action_tool": "list_directory",
        "params": {"dir_path": "D:/"}
    }
    parsed = ReActOutput.model_validate(valid_output)
    assert parsed.action_tool == "list_directory"
    assert parsed.params.dir_path == "D:/"

def test_tools_schema_generation():
    """测试 LongCat Function Calling Schema 生成"""
    from app.services.file_operations.tools import get_registered_tools
    from app.services.file_operations.react_schema import get_tools_schema
    
    tools = get_registered_tools()
    schema = get_tools_schema(tools)
    
    assert len(schema) > 0
    assert schema[0]["type"] == "function"
    assert "function" in schema[0]
    assert "parameters" in schema[0]["function"]

def test_invalid_params_rejected():
    """测试错误参数名被拒绝"""
    invalid_output = {
        "thought": "用户想查看D盘",
        "action_tool": "list_directory",
        "params": {"directory_path": "D:/"}  # 错误参数名
    }
    # Function Calling 会在 API 层拒绝，不会到达这里
```

### 5.2 集成测试

```python
# tests/test_agent_structured.py
@pytest.mark.asyncio
async def test_agent_with_response_format():
    """测试 Claude/GPT-4 使用 response_format"""
    agent = FileOperationAgent(..., use_structured_output=True, structured_mode="response_format")
    
    result = await agent.run_structured("查看D盘根目录")
    
    assert result.success
    assert result.steps[-1].action == "list_directory"
    params = result.steps[-1].action_input
    assert "dir_path" in params

@pytest.mark.asyncio
async def test_agent_with_longcat_tools():
    """测试 LongCat 使用 Function Calling"""
    from app.services.file_operations.tools import get_registered_tools
    from app.services.file_operations.react_schema import get_tools_schema
    
    tools = get_registered_tools()
    schema = get_tools_schema(tools)
    
    agent = FileOperationAgent(
        ..., 
        use_structured_output=True, 
        structured_mode="tools",
        tools=schema
    )
    
    result = await agent.run_with_tools("查看D盘根目录")
    
    assert result.success
    assert result.steps[-1].action == "list_directory"
```

### 5.3 LongCat Function Calling 验证测试（已完成）

**测试脚本**: `backend/tools/debug_longcat_response.py`

**验证结果**:
```
Test 1: response_format
Status: 200
Content-Length: 0  ← 不支持

Test 2: tools
Status: 200
tool_calls: [{'id': 'call_xxx', 'type': 'function', 
              'function': {'name': 'list_directory', 
                           'arguments': '{"dir_path": "D:\\"}'}}]
              ← 支持，参数名正确
```

---

## 六、渐进式实现计划

### 阶段1：基础实现（约2小时）
- [ ] 创建 `react_schema.py`
- [ ] 定义 `ReActOutput` Pydantic 模型
- [ ] 生成 JSON Schema

### 阶段2：BaseAIService 修改（约1小时）
- [ ] 修改 `StreamChunk` 添加 `raw_data`
- [ ] 修改 `chat_stream` 支持 `response_format`
- [ ] 添加 `chat_structured` 方法

### 阶段3：Agent 集成（约1小时）
- [ ] 修改 `FileOperationAgent`
- [ ] 添加 `use_structured_output` 参数
- [ ] 添加 `run_structured` 方法

### 阶段4：测试验证（约2小时）
- [ ] 编写 Schema 测试
- [ ] 编写 Agent 集成测试
- [ ] 实际调用测试

### 阶段5：配置和文档（约1小时）
- [ ] 添加配置文件支持
- [ ] 编写使用文档
- [ ] 更新 README

---

## 七、风险和注意事项

### 7.1 LLM 支持情况（已验证）

| LLM | response_format | tools/function_calling | 推荐方案 |
|-----|----------------|------------------------|---------|
| Claude | ✅ 支持 | ✅ 支持 | response_format |
| GPT-4 | ✅ 支持 | ✅ 支持 | response_format |
| LongCat | ❌ 不支持 | ✅ **已验证支持** | tools |
| 其他 | ⚠️ 待测试 | ⚠️ 待测试 | 根据测试选择 |

### 7.2 Schema 变更风险

**问题**：如果工具参数变更，需要同步更新 Schema

**缓解**：
```python
# 自动从 Pydantic 模型生成 Schema
from app.services.file_operations.tools import get_registered_tools

def auto_generate_schema():
    """自动从工具定义生成 Schema"""
    tools = get_registered_tools()
    # 根据工具定义动态生成
```

### 7.3 Token 消耗

Structured Outputs 会增加少量 Token 消耗（Schema 定义），但可以：
- 减少解析失败的 Retry
- 减少 agent.py 容错代码
- 整体可能节省 Token

---

## 八、与现有方案的关系

### 8.1 不是替代，是增强

```
┌─────────────────────────────────────────────────┐
│           小强的三层防御策略（保留）              │
│  System Prompt → Description → Examples         │
│           作为第一道防线                         │
└─────────────────────────────────────────────────┘
                      ↓ 如果 LLM 不遵守
┌─────────────────────────────────────────────────┐
│         Structured Outputs（新增）               │
│         作为强制约束（API层）                   │
└─────────────────────────────────────────────────┘
                      ↓ 如果 API 不支持
┌─────────────────────────────────────────────────┐
│         agent.py 容错映射（保留）               │
│           作为最后兜底                         │
└─────────────────────────────────────────────────┘
```

### 8.2 可以简化的部分

启用 Structured Outputs 后，可以：
- 减少 System Prompt 中的 FORBIDDEN 规则（仍有价值，但不必那么严格）
- 简化 agent.py 的参数映射代码（作为容错保留，但可能用不到）
- 减少 input_examples 数量（仍有价值，但可以减少）

---

**文档结束**

**编写时间**: 2026-03-20 08:30:00
**更新时间**: 2026-03-20 09:00:00
**编写人**: 小沈
**版本**: v2.0

**主要更新**:
- v2.0: 添加 LongCat Function Calling 测试结果（已验证支持）
- v1.0: 初始版本
**版本**: v1.0
