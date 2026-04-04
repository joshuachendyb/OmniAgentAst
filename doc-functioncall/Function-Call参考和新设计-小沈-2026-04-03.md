# Function Call 网上学习总结

**学习时间**: 2026-04-04 05:08:51
**编写人**: 小沈
**版本**: v1.1
**更新说明**: 
- 2026-04-04 06:56:00 - 修正第16-17章内容，补充准确的模型工具限制数据
- 2026-04-04 09:00:00 - 修正第20章：MCP Filesystem Server 工具数量 14→13 个，修正搜索标记错误，同步修正第21章汇总数据

---

## 一、Function Calling 是什么

Function Calling 让 LLM 能够调用外部函数/工具，完成诸如：
- 查询数据库
- 调用 API
- 读写文件
- 执行计算

**核心流程**:
```
用户输入 → LLM 判断需要调用工具 → 返回工具名+参数 → 执行函数 → 返回结果 → LLM 生成最终回答
```

---

## 二、主流 LLM 平台的实现

### 2.1 OpenAI Function Calling

**官方文档**: https://developers.openai.com/api/docs/guides/function-calling/

#### 工具定义 JSON Schema 完整示例

```python
# 来源: OpenAI 官方示例
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "获取指定位置的当前天气",
            "strict": True,  # 2024年后新增严格模式
            "parameters": {
                "type": "object",
                "required": ["location"],
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "城市名称，格式：城市+省，如 北京、上海"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位",
                        "default": "celsius"
                    }
                },
                "additionalProperties": False
            }
        }
    }
]
```

#### 完整调用代码（来自网上教程）

```python
# 来源: reintech.io 教程
from openai import OpenAI
import json

client = OpenAI(api_key="your-api-key")

# 定义工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get the current weather in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "The temperature unit to use"
                    }
                },
                "required": ["location"]
            }
        }
    }
]

# 实际天气函数
def get_current_weather(location, unit="fahrenheit"):
    weather_data = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"]
    }
    return json.dumps(weather_data)

# 执行对话
def run_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    
    # 第一次调用 - LLM 决定是否调用工具
    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=messages,
        tools=tools,
        tool_choice="auto"
    )
    
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls
    
    if tool_calls:
        messages.append(response_message)
        
        # 执行工具调用
        available_functions = {"get_current_weather": get_current_weather}
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            
            # 调用函数并获取结果
            function_response = function_to_call(
                location=function_args.get("location"),
                unit=function_args.get("unit", "fahrenheit")
            )
            
            # 将结果返回给 LLM
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": function_response,
            })
        
        # 第二次调用 - LLM 生成最终回复
        second_response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages
        )
        
        return second_response.choices[0].message.content
    
    return response_message.content

# 使用
result = run_conversation("What's the weather like in Boston?")
print(result)
```

---

### 2.2 Claude Tool Use (Anthropic)

**官方文档**: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview

#### 工具定义格式

```python
# 来源: Claude 官方文档
tools = [
    {
        "name": "web_search",
        "description": "Search the web for current information on any topic",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    }
]
```

#### 关键特性
- **Strict Tool Use**: 使用 grammar-constrained sampling 保证输入符合 schema
- **Tool Search Tool**: 支持动态发现工具（适用于大量工具场景）

---

### 2.3 Pydantic AI 的工具定义

**官方文档**: https://ai.pydantic.dev/tools/

#### 使用装饰器定义工具（来自官方示例）

```python
# 来源: Pydantic AI 官方示例
import random
from pydantic_ai import Agent, RunContext

agent = Agent(
    'gemini-2.0-flash',
    deps_type=str,
    instructions="你是掷骰子游戏"
)

@agent.tool_plain  # 不需要 context 的工具
def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    return str(random.randint(1, 6))

@agent.tool  # 需要 context 的工具
def get_player_name(ctx: RunContext[str]) -> str:
    """Get the player's name."""
    return ctx.deps

# 运行
result = agent.run_sync('My guess is 4', deps='Anne')
print(result.output)
```

#### 自动生成 Schema（来自官方示例）

```python
# 来源: Pydantic AI 官方示例 - 自动从 docstring 提取参数描述
@agent.tool_plain(docstring_format='google', require_parameter_descriptions=True)
def foobar(a: int, b: str, c: dict[str, list[float]]) -> str:
    """Get me foobar.

    Args:
        a: apple pie
        b: banana cake
        c: carrot smoothie
    """
    return f'{a} {b} {c}'

# 生成的 schema:
{
    'additionalProperties': False,
    'properties': {
        'a': {'description': 'apple pie', 'type': 'integer'},
        'b': {'description': 'banana cake', 'type': 'string'},
        'c': {
            'additionalProperties': {'items': {'type': 'number'}, 'type': 'array'},
            'description': 'carrot smoothie',
            'type': 'object',
        },
    },
    'required': ['a', 'b', 'c'],
    'type': 'object',
}
```

---

### 2.4 MCP (Model Context Protocol)

**官方文档**: https://modelcontextprotocol.io/specification/2025-11-25/server/tools

#### 工具定义格式（来自官方示例）

```json
{
  "name": "get_weather",
  "title": "天气信息查询",
  "description": "获取指定位置的当前天气信息",
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "城市名称或邮编"
      }
    },
    "required": ["location"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "temperature": {"type": "number", "description": "温度（摄氏度）"},
      "conditions": {"type": "string", "description": "天气状况"}
    }
  }
}
```

---

## 三、Python 函数转 JSON Schema 的方法

### 3.1 方法1：纯 Python + inspect（来自 amitness.com）

```python
# 来源: https://amitness.com/posts/function-calling-schema/
import inspect

type_map = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null",
}

def function_to_json(func):
    signature = inspect.signature(func)
    
    parameters = {}
    required = []
    
    for name, param in signature.parameters.items():
        param_type = type_map.get(param.annotation, "string")
        parameters[name] = {"type": param_type}
        
        # 必填参数判断
        if param.default == inspect._empty:
            required.append(name)
    
    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": func.__doc__ or "",
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": required
            }
        }
    }

# 使用
def add(a: int, b: int) -> int:
    """Adds two integers together"""
    return a + b

print(function_to_json(add))
# 输出:
# {
#     'type': 'function',
#     'function': {
#         'name': 'add',
#         'description': 'Adds two integers together',
#         'parameters': {
#             'type': 'object',
#             'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}},
#             'required': ['a', 'b']
#         }
#     }
# }
```

### 3.2 方法2：使用 Pydantic 动态模型（来自 amitness.com）

```python
# 来源: https://amitness.com/posts/function-calling-schema/
import inspect
from pydantic import create_model

def schema(f):
    kws = {
        name: (
            param.annotation,
            ... if param.default == inspect._empty else param.default,
        )
        for name, param in inspect.signature(f).parameters.items()
    }
    
    # 创建 Pydantic 模型
    p = create_model(f"`{f.__name__}`", **kws)
    
    return {
        "type": "function",
        "function": {
            "name": f.__name__,
            "description": f.__doc__,
            "parameters": p.model_json_schema(),
        },
    }

# 使用
def add(a: int, b: int) -> int:
    """Adds two integers together"""
    return a + b

print(schema(add))
```

### 3.3 方法3：使用 Pydantic TypeAdapter（来自 amitness.com）

```python
# 来源: https://amitness.com/posts/function-calling-schema/
from pydantic import TypeAdapter

def schema(f):
    schema = TypeAdapter(f).json_schema()
    return {
        "type": "function",
        "function": {
            "name": f.__name__,
            "description": f.__doc__,
            "parameters": schema,
        },
    }

# 使用
def add(a: int, b: int) -> int:
    """Adds two integers together"""
    return a + b

print(schema(add))
```

### 3.4 方法4：使用装饰器模式（来自 amitness.com）

```python
# 来源: https://amitness.com/posts/function-calling-schema/
def tool(func):
    """装饰器：自动添加 json_schema 方法"""
    def json_schema():
        return function_to_json(func)
    func.json_schema = json_schema
    return func

@tool
def add(a: int, b: int) -> int:
    """Adds two numbers"""
    return a + b

# 使用
print(add.json_schema())
```

---

## 四、JSON Schema 参数类型详解

### 4.1 基本类型（来自 jsonindenter.com）

| JSON Schema | 说明 |
|-------------|------|
| `string` | 字符串 |
| `integer` | 整数 |
| `number` | 数字（整数或浮点） |
| `boolean` | 布尔值 |
| `array` | 数组 |
| `object` | 对象 |
| `null` | 空值 |

### 4.2 参数约束示例

```json
{
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "用户名称"
        },
        "age": {
            "type": "integer",
            "minimum": 0,
            "maximum": 150
        },
        "email": {
            "type": "string",
            "format": "email"
        },
        "priority": {
            "type": "string",
            "enum": ["low", "medium", "high"]
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"}
        },
        "config": {
            "type": "object",
            "properties": {
                "timeout": {"type": "integer"},
                "retries": {"type": "integer"}
            }
        }
    },
    "required": ["name"]
}
```

---

## 五、常见错误和最佳实践

### 5.1 常见错误（来自 jsonindenter.com）

1. **缺少 `type: "object"`**: parameters 必须以 object 类型为根
2. **尾随逗号**: JSON 不允许尾随逗号
3. **参数名错误**: LLM 调用时必须使用 schema 中定义的参数名
4. **required 遗漏**: 必填参数必须添加到 required 数组
5. **描述为空**: description 帮助 LLM 理解何时调用工具

### 5.2 最佳实践

**好的描述**:
```python
description="获取指定位置的当前天气信息，包括温度、湿度、风力等"
```

**差的描述**:
```python
description="这是一个天气函数"
```

---

## 六、参考资料

1. OpenAI Function Calling: https://developers.openai.com/api/docs/guides/function-calling/
2. OpenAI 教程: https://reintech.io/blog/openai-function-calling-complete-tutorial-with-examples
3. JSON Schema 指南: https://jsonindenter.com/blog/json-for-ai-function-calling
4. Claude Tool Use: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
5. DeepSeek Tool Calls: https://api-docs.deepseek.com/guides/tool_calls
6. MCP 规范: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
7. Pydantic AI: https://ai.pydantic.dev/tools/
8. 函数转 Schema: https://amitness.com/posts/function-calling-schema/

---

## 七、MCP Filesystem Server 文件操作工具（来自官方）

**官方仓库**: https://github.com/modelcontextprotocol/servers
**官方文档**: https://mcprepository.com/modelcontextprotocol/filesystem

MCP Filesystem Server 提供了 11 个文件操作工具，是最完整的文件操作参考实现。

### 7.1 read_file - 读取文件

```json
{
  "name": "read_file",
  "description": "Read the complete contents of a file from the file system. Handles various text encodings and provides detailed error messages if the file cannot be read. Use this tool when you need to examine the contents of a single file. Only works within allowed directories.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The path to the file to read"
      }
    },
    "required": ["path"]
  }
}
```

**参数**:
- `path` (string, required): 文件路径

**实现示例**:
```python
def read_file(path: str) -> str:
    """Read complete contents of a file"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
```

### 7.2 read_multiple_files - 读取多个文件

```json
{
  "name": "read_multiple_files",
  "description": "Read the contents of multiple files simultaneously. This is more efficient than reading files one by one when you need to analyze or compare multiple files. Each file's content is returned with its path as a reference. Failed reads for individual files won't stop the entire operation.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "paths": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Array of file paths to read"
      }
    },
    "required": ["paths"]
  }
}
```

**参数**:
- `paths` (string[], required): 文件路径数组

### 7.3 write_file - 写入文件

```json
{
  "name": "write_file",
  "description": "Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Handles text content with proper encoding.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The location where the file should be created or written"
      },
      "content": {
        "type": "string",
        "description": "The content to write to the file"
      }
    },
    "required": ["path", "content"]
  }
}
```

**参数**:
- `path` (string, required): 文件路径
- `content` (string, required): 文件内容

**实现示例**:
```python
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"File written successfully: {path}"
```

### 7.4 edit_file - 编辑文件

```json
{
  "name": "edit_file",
  "description": "Make line-based edits to a text file. Each edit replaces exact line sequences with new content. Returns a git-style diff showing the changes made.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The path to the file to edit"
      },
      "edits": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "oldText": {
              "type": "string",
              "description": "Text to search for (can be substring)"
            },
            "newText": {
              "type": "string",
              "description": "Text to replace with"
            }
          }
        },
        "description": "List of edit operations to perform"
      },
      "dryRun": {
        "type": "boolean",
        "description": "Preview changes without applying (default: false)",
        "default": false
      }
    },
    "required": ["path", "edits"]
  }
}
```

**参数**:
- `path` (string, required): 文件路径
- `edits` (array, required): 编辑操作数组
  - `oldText` (string): 要替换的文本
  - `newText` (string): 替换后的文本
- `dryRun` (boolean, optional): 预览模式，默认 false

### 7.5 create_directory - 创建目录

```json
{
  "name": "create_directory",
  "description": "Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The path of the directory to create"
      }
    },
    "required": ["path"]
  }
}
```

**参数**:
- `path` (string, required): 目录路径

### 7.6 list_directory - 列出目录

```json
{
  "name": "list_directory",
  "description": "Get a detailed listing of all files and directories in a specified path. Results clearly distinguish between files and directories with [FILE] and [DIR] prefixes.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The path to the directory to list"
      }
    },
    "required": ["path"]
  }
}
```

**参数**:
- `path` (string, required): 目录路径

### 7.7 directory_tree - 目录树

```json
{
  "name": "directory_tree",
  "description": "Get a recursive tree view of files and directories as a JSON structure. Each entry includes 'name', 'type' (file/directory), and 'children' for directories.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The path to the directory to get tree view"
      }
    },
    "required": ["path"]
  }
}
```

**参数**:
- `path` (string, required): 目录路径

### 7.8 move_file - 移动/重命名文件

```json
{
  "name": "move_file",
  "description": "Move or rename files and directories. Can move files between directories and rename them in a single operation. If the destination exists, the operation will fail.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "source": {
        "type": "string",
        "description": "The current path of the file or directory"
      },
      "destination": {
        "type": "string",
        "description": "The new path for the file or directory"
      }
    },
    "required": ["source", "destination"]
  }
}
```

**参数**:
- `source` (string, required): 源路径
- `destination` (string, required): 目标路径

### 7.9 search_files - 搜索文件

```json
{
  "name": "search_files",
  "description": "Recursively search for files and directories matching a pattern. Searches through all subdirectories from the starting path. The search is case-insensitive and matches partial names.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The starting directory for the search"
      },
      "pattern": {
        "type": "string",
        "description": "The pattern to search for"
      },
      "excludePatterns": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Patterns to exclude from search (glob formats supported)",
        "default": []
      }
    },
    "required": ["path", "pattern"]
  }
}
```

**参数**:
- `path` (string, required): 搜索起始目录
- `pattern` (string, required): 搜索模式
- `excludePatterns` (string[], optional): 排除模式

### 7.10 get_file_info - 获取文件信息

```json
{
  "name": "get_file_info",
  "description": "Retrieve detailed metadata about a file or directory. Returns comprehensive information including size, creation time, last modified time, permissions, and type.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "The path to the file or directory"
      }
    },
    "required": ["path"]
  }
}
```

**参数**:
- `path` (string, required): 文件/目录路径

**返回**:
- size (number): 文件大小
- creationTime (string): 创建时间
- lastModifiedTime (string): 修改时间
- accessTime (string): 访问时间
- type (string): 类型 (file/directory)
- permissions (string): 权限

### 7.11 list_allowed_directories - 列出允许的目录

```json
{
  "name": "list_allowed_directories",
  "description": "Returns the list of directories that this server is allowed to access. Use this to understand which directories are available before trying to access files.",
  "inputSchema": {
    "type": "object",
    "properties": {}
  }
}
```

**参数**: 无

---

## 八、文件操作工具参数对比总结

| 工具 | 核心参数 | 来源 |
|-----|---------|------|
| read_file | path: string | MCP |
| read_multiple_files | paths: string[] | MCP |
| write_file | path, content: string | MCP |
| edit_file | path, edits: array, dryRun?: boolean | MCP |
| create_directory | path: string | MCP |
| list_directory | path: string | MCP |
| directory_tree | path: string | MCP |
| move_file | source, destination: string | MCP |
| search_files | path, pattern, excludePatterns?: string[] | MCP |
| get_file_info | path: string | MCP |
| list_allowed_directories | (无) | MCP |

---

## 九、DeepSeek Function Calling

**官方文档**: https://api-docs.deepseek.com/guides/tool_calls

DeepSeek 兼容 OpenAI 的 function calling 格式，支持以下模型：
- DeepSeek V3 系列
- DeepSeek R1 系列

**调用示例**（来自官方）:

```python
# 来源: DeepSeek 官方文档
from openai import OpenAI

client = OpenAI(api_key="sk-xxx", base_url="https://api.deepseek.com")

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "What's the weather like in Beijing?"}],
    tools=[
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather info for a specific location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]
)
```

**注意**: 需要添加 `"strict": true` 到 tool definitions（来自 GitHub issue #910）

---

## 十、参考资料（续）

9. MCP Filesystem Server: https://mcprepository.com/modelcontextprotocol/filesystem
10. MCP GitHub: https://github.com/modelcontextprotocol/servers
11. DeepSeek Tool Calls: https://api-docs.deepseek.com/guides/tool_calls


## 十一、LangChain 文件管理工具

**官方文档**: https://python.langchain.com/docs/how_to/tool_calling

LangChain 提供了完整的文件管理工具集，基于 Pydantic 模型定义参数。

### 11.1 ReadFileTool - 读取文件

**来源**: LangChain 官方 API 文档

```python
# LangChain ReadFileInput (Pydantic 模型)
class ReadFileInput(BaseModel):
    file_path: str = Field(..., description='name of file')
```

**JSON Schema 参数**:
```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "name of file"
    }
  },
  "required": ["file_path"]
}
```

**实现示例**:
```python
from langchain_community.tools.file_management import ReadFileTool

tool = ReadFileTool()
# 调用时参数: file_path (string, required)
```

### 11.2 WriteFileTool - 写入文件

**来源**: LangChain 官方 API 文档

```python
# LangChain WriteFileInput (Pydantic 模型)
class WriteFileInput(BaseModel):
    file_path: str = Field(..., description='name of file')
    text: str = Field(..., description='text to write to file')
    append: bool = Field(False, description='whether to append to file')
```

**JSON Schema 参数**:
```json
{
  "type": "object",
  "properties": {
    "file_path": {
      "type": "string",
      "description": "name of file"
    },
    "text": {
      "type": "string",
      "description": "text to write to file"
    },
    "append": {
      "type": "boolean",
      "description": "whether to append to file",
      "default": false
    }
  },
  "required": ["file_path", "text"]
}
```

**实现示例**:
```python
from langchain_community.tools.file_management import WriteFileTool

tool = WriteFileTool()
# 调用时参数: file_path (string), text (string), append (boolean, optional)
```

### 11.3 LangChain 工具特点

1. **Pydantic 模型定义**: 使用 Pydantic BaseModel 自动生成 JSON Schema
2. **args_schema 属性**: 每个工具都有 `args_schema` 属性指向 Pydantic 模型
3. **类型安全**: 自动验证参数类型
4. **与 LangChain Agent 集成**: 可以直接传递给 agent

---

## 十二、LlamaIndex Function Calling

**官方文档**: https://docs.llamaindex.ai/en/stable/examples/workflow/function_calling_agent/

LlamaIndex 使用 `FunctionTool` 来定义工具。

### 12.1 FunctionTool 定义

**来源**: LlamaIndex 官方教程

```python
from llama_index.core.tools import FunctionTool

def add(x: int, y: int) -> int:
    """Useful function to add two numbers."""
    return x + y

def multiply(x: int, y: int) -> int:
    """Useful function to multiply two numbers."""
    return x * y

tools = [
    FunctionTool.from_defaults(add),
    FunctionTool.from_defaults(multiply),
]
```

### 12.2 LlamaIndex 工具特点

1. **自动生成 Schema**: `FunctionTool.from_defaults()` 自动从函数签名生成 JSON Schema
2. **Docstring 提取**: 使用函数的 docstring 作为工具描述
3. **类型提示**: 使用 Python 类型提示定义参数类型
4. **Workflow 集成**: 可以与 LlamaIndex Workflow 深度集成

---

## 十三、AutoGen Function Calling

**官方文档**: https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/components/tools.html

AutoGen 是微软的开源多智能体框架。

### 13.1 AutoGen 工具特点

1. **MCP 集成**: 支持连接 MCP (Model Context Protocol) 服务器
2. **代码执行工具**: 内置代码执行工具
3. **类型安全**: 支持强类型函数定义

### 13.2 AutoGen 文件操作

**来源**: AutoGen 官方文档

```python
from autogen_core import CancellationToken
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool

# 创建代码执行工具
code_executor = DockerCommandLineCodeExecutor()
await code_executor.start()
```

---

## 十四、CrewAI 文件工具

**官方文档**: https://docs.crewai.com/en/tools/file-document/jsonsearchtool

CrewAI 提供了多种文件操作工具。

### 14.1 JSONSearchTool

**来源**: CrewAI 官方文档

```python
from crewai_tools import JSONSearchTool

# 通用 JSON 搜索
tool = JSONSearchTool()

# 限制搜索特定 JSON 文件
tool = JSONSearchTool(json_path='./path/to/your/file.json')
```

**参数**:
- `json_path` (str, optional): 指定要搜索的 JSON 文件路径

### 14.2 CrewAI 工具特点

1. **RAG 搜索**: 使用 RAG (Retrieve and Generate) 机制搜索
2. **可配置**: 支持配置不同的 LLM 和 embedding 模型
3. **实验性**: 部分工具标记为实验阶段

---

## 十五、Azure OpenAI Function Calling

**官方文档**: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/function-calling

Azure OpenAI 兼容 OpenAI 的 function calling 格式。

### 15.1 Azure OpenAI 特点

1. **兼容 OpenAI**: 使用与 OpenAI 相同的 JSON Schema 格式
2. **企业级**: 支持 Azure 的安全和合规特性
3. **部署选项**: 支持多种模型部署

### 15.2 调用示例

```python
# 来源: Azure OpenAI 官方示例
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="your-azure-api-key",
    api_version="2024-02-01",
    azure_endpoint="https://your-resource.openai.azure.com/"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's the weather like?"}],
    tools=tools  # 与 OpenAI 格式相同
)
```

---

## 十六、各主流模型 Function Calling 工具数量限制（准确数据）

### 16.1 OpenAI 模型工具数量限制

**官方文档**: https://platform.openai.com/docs/guides/function-calling

**关键发现**:
- **工具数量限制**: 最大 **128 个**工具（2023年12月确认）
- **来源**: OpenAI 开发者社区讨论（https://community.openai.com/t/limit-on-the-number-of-functions-definitions-for-assistant/537992）
- **说明**: 每个工具定义的平均 token 消耗约 123 tokens，128个工具约消耗 15.7k tokens，接近 128k 上下文窗口的限制

**实际建议**:
- 工具数量超过 128 个时，模型选择工具的准确率会显著下降
- 解决方案：使用**工具分组**或**微调模型**

---

### 16.2 Claude Code 内置工具（2025年12月数据）

**数据来源**: https://blog.thepete.net/claude-code-tools/（2025年12月9日更新）

**内置工具总数**: **18 个**

| 工具名称 | 功能描述 | 参数 |
|---------|---------|------|
| **Task** | 启动子 agent 处理复杂任务 | description, prompt, subagent_type, model, resume |
| **Bash** | 执行终端命令 | command, timeout, description, run_in_background, dangerouslyDisableSandbox |
| **Glob** | 文件名模式匹配 | pattern, path |
| **Grep** | 文件内容搜索 | pattern, path, glob, output_mode, -B, -A, -C, -n, -i, type, head_limit, offset, multiline |
| **ExitPlanMode** | 退出计划模式 | (无参数) |
| **Read** | 读取文件 | file_path, offset, limit |
| **Edit** | 编辑文件 | file_path, old_string, new_string, replace_all |
| **Write** | 写入文件 | file_path, content |
| **NotebookEdit** | 编辑 Jupyter notebook | notebook_path, cell_id, new_source, cell_type, edit_mode |
| **WebFetch** | 获取网页内容 | url, prompt |
| **TodoWrite** | 任务列表管理 | todos |
| **WebSearch** | 网络搜索 | query, allowed_domains, blocked_domains |
| **BashOutput** | 获取后台命令输出 | bash_id, filter |
| **KillShell** | 终止后台命令 | shell_id |
| **AskUserQuestion** | 向用户提问 | questions, answers |
| **Skill** | 执行 skill | skill |
| **SlashCommand** | 执行斜杠命令 | command |
| **EnterPlanMode** | 进入计划模式 | (无参数) |

**特点**:
- Claude Code 内置工具是固定的，**不支持自定义工具**（与 MCP 集成时可通过 MCP 添加外部工具）
- 工具按功能分类：文件操作（Read/Edit/Write/Glob/Grep）、命令执行（Bash）、网络（WebFetch/WebSearch）、任务管理（Task/TodoWrite）、用户交互（AskUserQuestion）

---

### 16.3 MCP Filesystem Server 工具（官方最新）

**数据来源**: https://github.com/modelcontextprotocol/servers（2025年最新）

**工具总数**: **14 个**（注意：比早期文档中的 11 个多了 2 个）

| 工具名称 | 功能 | 参数 |
|---------|------|------|
| **read_text_file** | 读取文本文件 | path (string), head (number, optional), tail (number, optional) |
| **read_media_file** | 读取图片/音频文件 | path (string) |
| **read_multiple_files** | 读取多个文件 | paths (string[]) |
| **write_file** | 写入/覆盖文件 | path (string), content (string) |
| **edit_file** | 编辑文件 | path (string), edits (array), dryRun (boolean, optional) |
| **create_directory** | 创建目录 | path (string) |
| **list_directory** | 列出目录内容 | path (string) |
| **list_directory_with_sizes** | 列出目录内容（含文件大小） | path (string), sortBy (string, optional) |
| **move_file** | 移动/重命名文件 | source (string), destination (string) |
| **search_files** | 递归搜索文件 | path (string), pattern (string), excludePatterns (string[], optional) |
| **directory_tree** | 获取目录树结构 | path (string), excludePatterns (string[], optional) |
| **get_file_info** | 获取文件/目录元数据 | path (string) |
| **list_allowed_directories** | 列出允许访问的目录 | (无参数) |
| **resource_templates** | 资源模板（新增） | (无参数) |
| **read_resource** | 读取资源（新增） | uri (string) |

**注意**: 
- 官方 README 显示 14 个工具，之前的文档可能只记录了 11 个
- 新增了 `read_media_file`（读取媒体文件）和 `list_directory_with_sizes`（带大小的目录列表）
- 详细参数见官方文档：https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem

---

### 16.4 通义千问 (Qwen) Function Calling

**官方文档**: 
- https://help.aliyun.com/zh/model-studio/qwen-function-calling
- https://qwen.readthedocs.io/en/stable/framework/function_call.html

**支持的模型**:
- 通义千问-Max
- 通义千问-Plus
- 通义千问-Turbo
- Qwen2.5 系列
- Qwen2 系列
- Qwen1.5 系列

**工具定义格式**: 兼容 OpenAI 格式

**工具数量限制**: 
- 官方未明确公布具体数量限制
- 推测与 OpenAI 类似，受限于上下文窗口大小
- 建议控制在 128 个以内以获得最佳效果

---

### 16.5 其他国内大模型

| 模型 | Function Calling 支持 | 工具数量限制 | 格式 |
|-----|----------------------|-------------|------|
| **百度文心** | 支持 | 未公开 | 兼容 OpenAI |
| **讯飞星火** | 部分支持 | 未公开 | 部分兼容 |
| **智谱清言** | 支持 | 未公开 | 兼容 OpenAI |
| **DeepSeek** | 支持 | 未公开 | 兼容 OpenAI，需添加 strict: true |

---

### 16.6 关键数据汇总表

| 平台/模型 | 工具数量 | 数据来源 | 备注 |
|----------|---------|---------|------|
| **OpenAI (GPT-4)** | 最大 128 | 社区讨论 2023-12 | 超过后准确率下降 |
| **Claude Code** | 18 个内置 | 博客 2025-12 | 固定工具集 |
| **MCP Filesystem** | 14 个 | 官方 GitHub 2025 | 官方最新数据 |
| **通义千问** | 未公开 | 官方文档 | 建议 <128 |
| **百度/讯飞/智谱** | 未公开 | 官方文档 | 兼容 OpenAI 格式 |

---

### 16.7 重要结论

1. **工具数量不是越多越好**：超过 128 个工具后，模型选择准确率会显著下降
2. **MCP 是最完整的文件操作方案**：14 个工具，覆盖读、写、编辑、搜索、元数据等
3. **Claude Code 工具固定**：内置 18 个工具，不支持自定义（需通过 MCP 扩展）
4. **国内大模型兼容 OpenAI**：工具定义格式与 OpenAI 相同

---

## 十七、Windows 平台 的 工具汇总（重点！）

### 17.1 Windows 专用 MCP 服务器概览

| 服务器 | 工具数量 | Stars | 核心功能 |
|--------|---------|-------|---------|
| **Windows-MCP** (CursorTouch) | 15+ | 5000+ | 鼠标/键盘/截图/窗口/Shell/注册表 |
| **MCPControl** | 10+ | 307 | 鼠标/键盘/窗口/屏幕/剪贴板 |
| **WinRemote-MCP** | 40+ | 89 | 桌面控制/进程/服务/注册表/网络/OCR |

---

### 17.2 Windows-MCP (CursorTouch) - 最流行的 Windows MCP

**GitHub**: https://github.com/CursorTouch/Windows-MCP（5000+ stars）

**支持的客户端**: Claude Desktop, Claude Code, Cursor, Perplexity, Gemini CLI, Codex, Qwen Code

**工具列表**:

| 工具 | 功能描述 | 核心参数 |
|-----|---------|----------|
| **Click** | 鼠标点击 | x, y, button (left/right/middle), click_type (single/double) |
| **Type** | 键盘输入 | text, clear (可选清除现有文本) |
| **Scroll** | 滚动 | direction (up/down/left/right), amount |
| **Move** | 鼠标移动/拖拽 | x, y, drag (布尔值) |
| **Shortcut** | 快捷键 | keys (如 Ctrl+c, Alt+Tab) |
| **Wait** | 暂停等待 | duration (秒) |
| **Screenshot** | 快速截图 | display (可选屏幕编号), scale (缩放) |
| **Snapshot** | 完整桌面状态 | use_vision, use_dom, display |
| **App** | 应用操作 | action (launch/switch/resize), name, args |
| **Shell** | PowerShell执行 | command, cwd (可选工作目录) |
| **Scrape** | 网页抓取 | url |
| **MultiSelect** | 多选 | coordinates[], ctrl (是否按Ctrl) |
| **MultiEdit** | 多处编辑 | fields [{x, y, text}] |
| **Clipboard** | 剪贴板 | action (read/write), content |
| **Process** | 进程管理 | action (list/kill), pid, name |
| **Notification** | Windows通知 | title, message |
| **Registry** | 注册表 | action (read/write/delete/list), path, name, value |

**安装方式**:
```bash
# 推荐使用 uvx
uvx windows-mcp

# 或通过 Claude Code
claude mcp add --transport stdio windows-mcp -- uvx windows-mcp
```

**特点**:
- ✅ 支持任何 LLM（不依赖特定视觉模型）
- ✅ 轻量级开源
- ✅ 延迟 0.2-0.9 秒
- ✅ 支持本地/远程模式

---

### 17.3 MCPControl - Windows OS 自动化

**GitHub**: https://github.com/claude-did-this/MCPControl（307 stars）

**工具列表**:

| 工具 | 功能描述 | 核心参数 |
|-----|---------|----------|
| **Window Management** | 窗口管理 | list_windows, get_active_window, focus_window, resize_window |
| **Mouse Control** | 鼠标控制 | move, click, drag, scroll, position |
| **Keyboard Control** | 键盘控制 | type_text, key_combo, press_key, hold_key |
| **Screen Capture** | 屏幕截图 | screenshot, capture_window, screen_size |
| **Clipboard** | 剪贴板 | read, write |

**安装方式**:
```bash
npm install -g mcp-control
mcp-control --sse
```

**安全提示**: 实验性软件，有风险

---

### 17.4 WinRemote-系统 - 40+ 工具的企业级方案

**GitHub**: https://github.com/dddabtc/winremote-mcp（89 stars）

**详细工具列表**:

**桌面控制**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| Snapshot | 截图 | quality, max_width, monitor |
| AnnotatedSnapshot | 标注截图 | - |
| OCR | 文字识别 | - |
| ScreenRecord | 屏幕录制 | - |

**输入控制**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| Click | 点击 | x, y, button, click_type |
| Type | 输入 | text, x, y |
| Scroll | 滚动 | direction, amount |
| Move | 移动 | x, y, drag |
| Shortcut | 快捷键 | keys |
| Wait | 等待 | duration |

**窗口管理**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| FocusWindow | 聚焦窗口 | title |
| MinimizeAll | 最小化全部 | - |
| App | 应用操作 | action, name, args |

**系统操作**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| Shell | PowerShell | command, cwd |
| GetClipboard | 读剪贴板 | - |
| SetClipboard | 写剪贴板 | content |
| ListProcesses | 进程列表 | - |
| KillProcess | 终止进程 | pid, name |
| GetSystemInfo | 系统信息 | - |
| Notification | 通知 | title, message |
| LockScreen | 锁屏 | - |

**文件操作**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| FileRead | 读取 | path |
| FileWrite | 写入 | path, content |
| FileList | 列表 | path |
| FileSearch | 搜索 | path, pattern |
| FileDownload | 下载 | path |
| FileUpload | 上传 | content, path |

**注册表/服务**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| RegRead | 读注册表 | path, name |
| RegWrite | 写注册表 | path, name, value |
| ServiceList | 服务列表 | - |
| ServiceStart | 启动服务 | name |
| ServiceStop | 停止服务 | name |

**计划任务**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| TaskList | 任务列表 | - |
| TaskCreate | 创建任务 | name, command, schedule |
| TaskDelete | 删除任务 | name |

**网络工具**:
| 工具 | 功能 | 参数 |
|-----|------|------|
| Scrape | 网页抓取 | url |
| Ping | Ping | host |
| PortCheck | 端口检查 | host, port |
| NetConnections | 网络连接 | - |
| EventLog | 事件日志 | - |

**安全层级**:
- **Tier 1** (只读): Snapshot, GetSystemInfo, ListProcesses - 默认启用
- **Tier 2** (交互): Click, Type, Shortcut, App - 默认启用
- **Tier 3** (危险): Shell, FileWrite, KillProcess, RegWrite - 默认禁用

---

### 17.5 Windows 特有工具对比

| 功能 | Windows-MCP | MCPControl | WinRemote-MCP |
|-----|------------|------------|---------------|
| 鼠标控制 | ✅ | ✅ | ✅ |
| 键盘输入 | ✅ | ✅ | ✅ |
| 截图 | ✅ | ✅ | ✅ |
| 窗口管理 | ✅ | ✅ | ✅ |
| Shell/PowerShell | ✅ | ❌ | ✅ |
| 进程管理 | ✅ | ❌ | ✅ |
| 注册表 | ✅ | ❌ | ✅ |
| 服务管理 | ❌ | ❌ | ✅ |
| 剪贴板 | ✅ | ✅ | ✅ |
| OCR | ❌ | ❌ | ✅ |
| 屏幕录制 | ❌ | ❌ | ✅ |
| 网络工具 | ❌ | ❌ | ✅ |

---

### 17.6 Windows MCP 工具参数命名规范

**路径类**:
- `path` - 文件/目录路径
- `cwd` - 当前工作目录

**坐标类**:
- `x`, `y` - 屏幕坐标
- `display` - 显示器编号

**操作类**:
- `action` - 操作类型 (list/kill/read/write 等)
- `button` - 鼠标按钮 (left/right/middle)
- `click_type` - 点击类型 (single/double)

**内容类**:
- `text` / `content` - 文本内容
- `command` - 命令字符串

**控制类**:
- `drag` - 是否拖拽
- `scale` - 缩放比例

---

## 十八、主流 Agent 工具数量对比与选择建议

### 18.1 各平台工具数量总览

| 平台/模型 | 文件操作 | Windows 特有 | 总计约 |
|---------|---------|-------------|-------|
| **MCP Filesystem** | 14 | 0 | 14 |
| **LangChain** | 7 | 0 | 7 |
| **Claude Code** | 4 | 14 | 18 |
| **Windows-MCP** | 0 | 15+ | 15+ |
| **WinRemote-MCP** | 6 | 40+ | 40+ |
| **OpenAI (GPT-4)** | 自定义 | 自定义 | ≤128 |

### 18.2 选择建议

**文件操作为主**:
- 推荐 MCP Filesystem (14个工具) - 官方维护，最稳定

**Windows 桌面自动化**:
- 推荐 Windows-MCP (15+工具) - 5000+ stars，最流行
- 或 WinRemote-MCP (40+工具) - 功能最全，企业级

**综合应用**:
- OpenAI + MCP Filesystem + Windows-MCP 组合

---

### 18.3 重要结论

1. **Windows MCP 工具生态丰富**: 有多种开源方案可选
2. **工具数量与复杂度正相关**: WinRemote 有 40+ 工具，但配置更复杂
3. **安全层级很重要**: WinRemote 的 Tier 系统值得借鉴
4. **远程访问是趋势**: Windows-MCP 支持本地/远程模式

---

### 18.4 参考价值排名

| 来源 | 价值 | 适用场景 |
|-----|------|---------|
| Windows-MCP (CursorTouch) | ★★★★★ | Windows 桌面自动化首选 |
| WinRemote-MCP | ★★★★★ | 企业级 Windows 控制 |
| MCPControl | ★★★★☆ | 轻量级自动化 |
| MCP Filesystem | ★★★★★ | 跨平台文件操作 |
| OpenAI Function Calling | ★★★★★ | 通用工具定义标准 |

---

## 十九、参考资料（续2）

12. LangChain Tools: https://python.langchain.com/docs/how_to/tool_calling
13. LangChain File Management: https://docs.langchain.com/oss/python/integrations/tools/filesystem
14. LlamaIndex Workflow: https://docs.llamaindex.ai/en/stable/examples/workflow/function_calling_agent/
15. AutoGen Tools: https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/components/tools.html
16. CrewAI Tools: https://docs.crewai.com/en/concepts/tools
17. Azure OpenAI: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/function-calling
18. 通义千问 Function Calling: https://help.aliyun.com/zh/model-studio/qwen-function-calling
19. Qwen Framework: https://qwen.readthedocs.io/en/stable/framework/function_call.html

---

**编写人**: 小沈
**更新时间**: 2026-04-04 07:15:00
**更新说明**: 
- 修正第16-17章内容，补充准确的模型工具限制数据（OpenAI 128个限制、Claude Code 18个、MCP 14个）
- 新增第17章：Windows 平台 MCP 工具汇总（Windows-MCP 5000+ stars、MCPControl 307 stars、WinRemote-MCP 40+ tools）
- 新增第18章：主流 Agent 工具数量对比与选择建议

---

## 二十、工具类型分类与对比总结

### 20.1 MCP Filesystem Server (13个工具) - 官方最新数据

**来源**: 官方 GitHub 仓库 https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem（2026年1月更新）

**重要说明**: 
- 官方最新显示 **13 个**工具
- 新增工具：`read_media_file`、`list_directory_with_sizes`
- 注意：`resource_templates` 和 `read_resource` 属于 MCP Resources 能力，不属于 Tools
- 以下是详细参数（来自官方 README）：

| 工具名称 | 参数 | 参数类型 | 必填 | 说明 |
|---------|------|---------|-----|------|
| **read_text_file** | path | string | ✅ 是 | 文件路径 |
| | head | number | ❌ 否 | 读取前 N 行（不能与 tail 同时用） |
| | tail | number | ❌ 否 | 读取后 N 行 |
| **read_media_file** | path | string | ✅ 是 | 图片/音频文件路径，返回 base64 + MIME 类型 |
| **read_multiple_files** | paths | string[] | ✅ 是 | 文件路径数组，单个失败不会中断 |
| **write_file** | path | string | ✅ 是 | 文件路径 |
| | content | string | ✅ 是 | 文件内容 |
| **edit_file** | path | string | ✅ 是 | 文件路径 |
| | edits | array | ✅ 是 | 编辑操作数组 [{oldText, newText}] |
| | dryRun | boolean | ❌ 否 | 预览模式，默认 false |
| **create_directory** | path | string | ✅ 是 | 目录路径，会创建父目录 |
| **list_directory** | path | string | ✅ 是 | 目录路径，带 [FILE]/[DIR] 前缀 |
| **list_directory_with_sizes** | path | string | ✅ 是 | 目录路径 |
| | sortBy | string | ❌ 否 | 排序方式 (name/size)，默认 name |
| **move_file** | source | string | ✅ 是 | 源路径 |
| | destination | string | ✅ 是 | 目标路径，目标存在会失败 |
| **search_files** | path | string | ✅ 是 | 搜索起始目录 |
| | pattern | string | ✅ 是 | 搜索模式（glob 风格） |
| | excludePatterns | string[] | ❌ 否 | 排除模式 |
| **directory_tree** | path | string | ✅ 是 | 目录路径，返回 JSON 树结构 |
| | excludePatterns | string[] | ❌ 否 | 排除模式 |
| **get_file_info** | path | string | ✅ 是 | 文件/目录路径，返回大小、创建/修改/访问时间、类型、权限 |
| **list_allowed_directories** | (无) | - | - | 无参数，返回允许访问的目录列表 |

---

### 20.1.1 MCP ToolAnnotations（重要安全提示）

MCP 官方定义了工具的**只读**、**幂等**、**破坏性**属性，帮助客户端正确处理工具：

| 工具 | readOnly | idempotent | destructive | 说明 |
|-----|----------|------------|-------------|------|
| read_text_file | ✅ true | - | - | 纯读操作 |
| read_media_file | ✅ true | - | - | 纯读操作 |
| read_multiple_files | ✅ true | - | - | 纯读操作 |
| list_directory | ✅ true | - | - | 纯读操作 |
| list_directory_with_sizes | ✅ true | - | - | 纯读操作 |
| directory_tree | ✅ true | - | - | 纯读操作 |
| search_files | ✅ true | - | - | 纯读操作 |
| get_file_info | ✅ true | - | - | 纯读操作 |
| list_allowed_directories | ✅ true | - | - | 纯读操作 |
| **create_directory** | ❌ false | ✅ true | ❌ false | 重复创建是空操作 |
| **write_file** | ❌ false | ✅ true | ✅ true | 覆盖已有文件 |
| **edit_file** | ❌ false | ❌ false | ✅ true | 重复编辑可能失败或重复应用 |
| **move_file** | ❌ false | ❌ false | ✅ true | 删除源文件 |

**安全建议**:
- `readOnly=false` 且 `destructive=true` 的工具（write_file, edit_file, move_file）需谨慎使用
- `edit_file` 建议始终先用 `dryRun=true` 预览
- `move_file` 目标存在会失败

---

### 20.2 LangChain FileManagementToolkit (7个工具)

**来源**: 官方 GitHub 仓库 https://github.com/langchain-ai/langchain-community

| 工具名称 | 参数 | 参数类型 | 必填 | 说明 |
|---------|------|---------|-----|------|
| **ReadFileTool** | file_path | string | ✅ 是 | 文件路径 |
| **WriteFileTool** | file_path | string | ✅ 是 | 文件路径 |
| | text | string | ✅ 是 | 写入文本 |
| | append | boolean | ❌ 否 | 是否追加，默认 false |
| **CopyFileTool** | source_path | string | ✅ 是 | 源文件路径 |
| | destination_path | string | ✅ 是 | 目标文件路径 |
| **MoveFileTool** | source_path | string | ✅ 是 | 源文件路径 |
| | destination_path | string | ✅ 是 | 目标文件路径 |
| **DeleteFileTool** | file_path | string | ✅ 是 | 要删除的文件路径 |
| **FileSearchTool** | pattern | string | ✅ 是 | Unix shell 匹配模式 |
| | dir_path | string | ❌ 否 | 搜索目录，默认 "." |
| **ListDirectoryTool** | dir_path | string | ❌ 否 | 列出目录，默认 "." |

**LangChain JSON Schema 示例**:
```python
# ReadFileTool
class ReadFileInput(BaseModel):
    file_path: str = Field(..., description='name of file')

# WriteFileTool  
class WriteFileInput(BaseModel):
    file_path: str = Field(..., description='name of file')
    text: str = Field(..., description='text to write to file')
    append: bool = Field(False, description='whether to append to file')

# CopyFileTool
class FileCopyInput(BaseModel):
    source_path: str = Field(..., description='Path of the file to copy')
    destination_path: str = Field(..., description='Path to save the copied file')

# MoveFileTool
class FileMoveInput(BaseModel):
    source_path: str = Field(..., description='Path of the file to move')
    destination_path: str = Field(..., description='New path for the moved file')

# DeleteFileTool
class FileDeleteInput(BaseModel):
    file_path: str = Field(..., description='Path of the file to delete')

# FileSearchTool
class FileSearchInput(BaseModel):
    dir_path: str = Field(default=".", description="Subdirectory to search in.")
    pattern: str = Field(..., description="Unix shell regex, where * matches everything.")

# ListDirectoryTool
class DirectoryListingInput(BaseModel):
    dir_path: str = Field(default=".", description="Subdirectory to list.")
```

---

### 20.3 参数类型汇总

| 参数类型 | 说明 | 示例 |
|---------|------|------|
| **string** | 字符串 | path, file_path, source_path |
| **string[]** | 字符串数组 | paths, excludePatterns |
| **boolean** | 布尔值 | append, dryRun |
| **array** | 数组 | edits (包含 oldText, newText) |
| **无参数** | 不需要参数 | list_allowed_directories |

---

### 20.4 参数命名对比（MCP vs LangChain）

| 功能 | MCP 参数名 | LangChain 参数名 |
|-----|-----------|-----------------|
| 读取文件 | path | file_path |
| 写入文件 | path, content | file_path, text |
| 复制文件 | - | source_path, destination_path |
| 移动文件 | source, destination | source_path, destination_path |
| 删除文件 | - | file_path |
| 列出目录 | path | dir_path |
| 搜索文件 | path, pattern | pattern, dir_path |

---

### 20.5 所有平台 File Tool 完整对比表

| 工具功能 | MCP (14个) | LangChain (7个) | 备注 |
|---------|-----------|-----------------|------|
| **读取单个文件** | read_text_file (path, head, tail) | ReadFileTool (file_path) | MCP 支持 head/tail |
| **读取多个文件** | read_multiple_files (paths) | ❌ | MCP 独有 |
| **读取媒体文件** | read_media_file (path) | ❌ | MCP 独有，返回 base64 |
| **写入文件** | write_file (path, content) | WriteFileTool (file_path, text, append) | LangChain 支持 append |
| **编辑文件** | edit_file (path, edits, dryRun) | ❌ | MCP 独有，diff 预览 |
| **复制文件** | ❌ | CopyFileTool (source_path, destination_path) | LangChain 独有 |
| **移动/重命名** | move_file (source, destination) | MoveFileTool (source_path, destination_path) | 参数名不同 |
| **删除文件** | ❌ | DeleteFileTool (file_path) | LangChain 独有 |
| **创建目录** | create_directory (path) | ❌ | MCP 独有 |
| **列出目录** | list_directory (path) | ListDirectoryTool (dir_path) | 参数名不同 |
| **列出目录(含大小)** | list_directory_with_sizes (path, sortBy) | ❌ | MCP 独有 |
| **搜索文件(内容)** | search_files (path, pattern, excludePatterns) | FileSearchTool (pattern, dir_path) | MCP 支持 excludePatterns |
| **搜索文件(名称)** | ✅ search_files | ✅ FileSearchTool | 两者都有文件名搜索 |
| **目录树** | directory_tree (path, excludePatterns) | ❌ | MCP 独有 |
| **文件信息** | get_file_info (path) | ❌ | MCP 独有，返回元数据 |
| **允许目录列表** | list_allowed_directories | ❌ | MCP 独有，安全控制 |
| **资源模板** | ❌ | ❌ | 属于 MCP Resources 能力，不是 Tool |
| **读取资源** | ❌ | ❌ | 属于 MCP Resources 能力，不是 Tool |

---

### 20.6 Claude Code 内置工具（18个）- 完整参数

**数据来源**: https://vtrivedy.com/posts/claudecode-tools-reference/（2025年10月更新）

**重要说明**: Claude Code 有 18 个内置工具，与 MCP/LangChain 不同，这些是 Claude Code 固定提供的，不能自定义。

| 序号 | 工具名称 | 功能描述 | 核心参数 |
|-----|---------|---------|----------|
| 1 | **Task** | 启动子 agent 处理复杂任务 | subagent_type, prompt, description, model, resume |
| 2 | **Bash** | 执行 shell 命令 | command, description, timeout, run_in_background |
| 3 | **Glob** | 文件名模式匹配（快） | pattern, path |
| 4 | **Grep** | 文件内容搜索（基于 ripgrep） | pattern, path, output_mode, glob, type, -A, -B, -C, -n, -i, multiline, head_limit |
| 5 | **Read** | 读取文件 | file_path, offset, limit |
| 6 | **Edit** | 编辑文件 | file_path, old_string, new_string, replace_all |
| 7 | **Write** | 写入/覆盖文件 | file_path, content |
| 8 | **NotebookEdit** | 编辑 Jupyter notebook | notebook_path, cell_id, new_source, cell_type, edit_mode |
| 9 | **WebFetch** | 获取网页内容（带 AI 分析） | url, prompt |
| 10 | **WebSearch** | 网络搜索（仅 US） | query, allowed_domains, blocked_domains |
| 11 | **TodoWrite** | 任务列表管理 | todos [{content, activeForm, status}] |
| 12 | **ExitPlanMode** | 退出计划模式 | plan |
| 13 | **BashOutput** | 获取后台命令输出 | bash_id, filter |
| 14 | **KillShell** | 终止后台命令 | shell_id |
| 15 | **SlashCommand** | 执行斜杠命令 | command |
| 16 | **AskUserQuestion** | 向用户提问 | questions, answers |
| 17 | **Skill** | 执行 skill | skill |
| 18 | **EnterPlanMode** | 进入计划模式 | (无参数) |

**Glob 参数详解**:
- `pattern`: Glob 模式（`**/*.js`, `src/**/*.ts`, `*.{json,yaml}`）
- `path`: 搜索目录（可选，默认当前目录）
- 返回按修改时间排序的文件列表

**Grep 参数详解**:
- `pattern`: 正则表达式（使用 ripgrep）
- `path`: 搜索路径
- `output_mode`: "content"（行）、"files_with_matches"（文件）、"count"（计数）
- `glob`: 文件类型过滤（如 "*.ts"）
- `type`: 语言类型（如 "js", "py"）
- `-A/-B/-C`: 匹配后/前/前后行数
- `-i`: 不区分大小写
- `-n`: 显示行号
- `multiline`: 多行匹配
- `head_limit`: 限制结果数量

**Claude Code 搜索策略**:
| 场景 | 推荐工具 |
|-----|---------|
| 按文件名搜索 | Glob |
| 按文件内容搜索 | Grep |
| 搜索特定文件再读内容 | Read + Grep |
| 复杂多轮搜索 | Task（general-purpose agent）|

---

### 20.7 搜索工具对比总结

| 搜索类型 | Claude Code | MCP Filesystem | LangChain | 我们 Omni |
|---------|-------------|----------------|-----------|-----------|
| **文件名搜索** | Glob (pattern, path) | search_files | FileSearchTool | search_files |
| **文件内容搜索** | Grep (pattern, path, output_mode) | ❌ 无 | ❌ 无 | search_file_content |
| **备注** | 两者分开，最清晰 | 只有一个 search_files | 只有一个 FileSearchTool | 分开的两个工具 |

**关键发现**:
- **Claude Code 最完善**: 明确区分 Glob（文件名）和 Grep（内容）
- **MCP/LangChain 不足**: 只有文件名搜索，没有内容搜索
- **我们 Omni 系统**: 有 search_files 和 search_file_content 两个工具

---

### 20.8 工具类型分类（按系统执行能力）

**核心结论**：没有任何工具必须依赖 MCP。MCP 只是可选的跨进程通信协议。我们的系统用 Python 直接实现所有功能即可。分类依据 2026 年 Q1 最新 Agentic AI 工具生态标准。

#### 一、核心业务工具（零依赖，Python 标准库实现）【一级实现的工具】

**说明**：Agent 最基础、最高频使用的能力，Python 标准库即可实现，无需安装任何第三方包。

| 类型 | 包含工具 | 实现方式 | 说明 |
|------|---------|---------|------|
| **1. 文件操作** | read_text_file, read_media_file, read_batch_file, read_file, write_append_file, precise_replace_in_file, edit_file, copy_file, move_file, rename_file, delete_file, search_files, glob_files, grep_file_content, create_directory, list_directory_with_sizes, get_directory_tree, get_file_info, list_allowed_directories | `os`, `shutil`, `pathlib`, `glob` | 基础文件读写、编辑、搜索、目录管理、重命名、媒体读取 |
| **2. Shell 命令执行** | execute_shell_command, get_shell_output, terminate_shell | `subprocess` | PowerShell/CMD 命令执行、后台任务管理 |
| **3. API/HTTP 调用** | http_request | `urllib`, `http.client` | Agent 调用外部 REST API、Webhook、微服务（通用方法覆盖 GET/POST/PUT/DELETE） |
| **4. 网络通信** | fetch_webpage, search_web | `urllib`, `http.client` | 网页内容获取、网络搜索 |
| **5. 时间/日期** | get_current_time, calculate_date | `datetime`, `time` | Agent 获取当前时间、计算日期差、定时任务 |
| **6. 环境变量** | get_env, set_env | `os.environ` | 读取/设置系统环境变量 |
| **7. 系统信息** | get_system_info | `psutil` 或 `wmi` | `pip install psutil` |
| **8. 网络连接** | net_connections, event_log | `psutil` | `pip install psutil` |
| **9. 压缩/解压** | compress_archive, extract_archive | `shutil.make_archive` / `zipfile` | Python 标准库，零依赖 |
| **10. 文件哈希** | get_file_hash | `hashlib` | Python 标准库，零依赖 |

#### 二、系统管理工具（轻量第三方，pip install）【二级实现工具】

**说明**：用于更高级的系统管理功能，需要安装少量第三方库。

| 类型 | 包含工具 | 实现方式 | 依赖 |
|------|---------|---------|------|
| **11. 数据库访问** | query_sql, execute_sql, query_nosql | `sqlite3`（内置）/ `sqlalchemy` | Agent 查询/写入 SQLite、MySQL 等数据库，2026 年 Agent 标配 |
| **12. 注册表操作** | reg_read, reg_write, reg_delete | `winreg` | Python 内置库（Windows 专用），零依赖 |
| **13. 日志记录** | log_message, get_logs | `logging` | Agent 操作日志、审计追踪、错误记录 |
| **14. 数据序列化** | read_json, write_json, read_csv | `json`, `csv` | Agent 读写 JSON/CSV 数据文件 |
| **15. 进程管理** | list_processes, kill_process | `psutil` | `pip install psutil` |
| **16. 服务管理** | service_list, service_start, service_stop | `subprocess` 执行 `sc` 或 `pywin32` | 零依赖 或 `pip install pywin32` |
| **17. 计划任务** | task_list, task_create, task_delete | `subprocess` 执行 `schtasks` | 零依赖 |
| **18. 网络诊断** | ping, port_check | `subprocess` 执行 `ping` / `socket` | 零依赖 |

#### 三、数据处理与代码执行工具（2026 年 Agent 标配）【三级实现工具】

**说明**：2026 年 Agent 的核心能力，用于数据分析、代码验证、图表生成。

| 类型 | 包含工具 | 实现方式 | 依赖 |
|------|---------|---------|------|
| **19. 代码执行** | execute_python, execute_javascript | `subprocess` + 沙箱 | 零依赖（需沙箱隔离） |
| **20. 数据分析** | read_csv, generate_chart, analyze_data | `pandas`, `matplotlib` | `pip install pandas matplotlib` |
| **21. 文档处理** | read_pdf, read_docx, read_xlsx | `pdfplumber`, `python-docx`, `openpyxl` | `pip install` 对应库 |

#### 四、GUI 交互与桌面自动化工具（可选扩展）

**说明**：用于控制桌面 GUI（鼠标、键盘、窗口），属于**可选扩展能力**，不是 Agent 核心需求。

| 类型 | 包含工具 | 实现方式 | 依赖 |
|------|---------|---------|------|
| **22. 鼠标控制** | click, move, scroll | `pyautogui` 或 `ctypes` + `user32.dll` | `pip install pyautogui` 或零依赖 |
| **23. 键盘输入** | type_text, shortcut, key_combo | `pyautogui` 或 `keyboard` | `pip install pyautogui` |
| **24. 截图/屏幕** | screenshot, snapshot, screen_record | `mss` 或 `PIL.ImageGrab` | `pip install mss` 或 `Pillow` |
| **25. OCR 识别** | ocr | `pytesseract` + Tesseract 引擎 | `pip install pytesseract` |
| **26. 窗口管理** | list_windows, focus_window, resize_window | `pywin32` 或 `ctypes` | `pip install pywin32` 或零依赖 |
| **27. 剪贴板操作** | read_clipboard, write_clipboard | `pyperclip` 或 `ctypes` | `pip install pyperclip` 或零依赖 |
| **28. 通知** | send_notification | `win10toast` | `pip install win10toast` |

#### 五、Agent 辅助/配套工具（任务执行保障）

**说明**：这类工具不直接完成核心业务，而是为 Agent 执行主任务提供**环境确认**、**状态检查**、**安全验证**和**异常处理**支持，防止 Agent 盲目操作报错。

**1. 文件操作保障**

| 工具 | 服务对象 | 作用 | 优先级 |
|------|---------|------|--------|
| **check_path_exists** | 所有文件工具 | 确认路径是否存在，避免"找不到文件" | **高** |
| **ensure_directory_exists** | write_file, copy, move | 确保目标目录存在，不存在则创建 | **高** |
| **check_write_permission** | write_file, edit, delete | 确认文件/目录有写入权限 | **高** |
| **check_read_permission** | search, list, tree | 确认目录有读取权限 | 中 |
| **get_file_encoding** | read_text_file | 确认文件编码（UTF-8/GBK），避免乱码 | 中 |
| **get_mime_type** | read_media_file | 确认文件 MIME 类型（image/png 等） | 中 |
| **backup_file** | edit_file, write_file | 编辑/覆盖前自动备份原文件 | 中 |
| **move_to_trash** | delete_file | 删除时进回收站而非永久删除，可恢复 | **高** |

**2. Shell 命令执行保障**

| 工具 | 服务对象 | 作用 | 优先级 |
|------|---------|------|--------|
| **get_current_working_dir** | execute_shell_command | 获取当前工作目录 | 中 |
| **validate_command** | execute_shell_command | 检查命令安全性，防止危险操作（如 rm -rf /） | **高** |
| **check_shell_running** | get_shell_output | 检查后台 Shell 是否还在运行 | 中 |

**3. 数据库访问保障**

| 工具 | 服务对象 | 作用 | 优先级 |
|------|---------|------|--------|
| **check_db_exists** | query_sql, execute_sql | 确认数据库文件/连接是否存在 | **高** |
| **get_table_schema** | query_sql, execute_sql | 获取表结构，Agent 知道有哪些字段 | **高** |
| **begin_transaction** | execute_sql | 开启事务，保证数据一致性 | 中 |
| **commit_transaction** | execute_sql | 提交事务 | 中 |
| **rollback_transaction** | execute_sql | 回滚事务 | 中 |

**4. API/HTTP 调用保障**

| 工具 | 服务对象 | 作用 | 优先级 |
|------|---------|------|--------|
| **check_network_connectivity** | http_request | 检查网络是否连通 | 中 |
| **validate_url** | http_request | 验证 URL 格式是否合法 | 低 |

**设计原则说明**：
- **文件属性操作（get/set_file_attributes）不暴露给 Agent**：这些属于底层实现细节，应内化到 `write_file` 等工具中。例如 `write_file` 内部应自动检测只读属性并尝试解除，而不是让 Agent 手动调用属性修改工具。

#### 六、Agent 框架内置工具（由框架提供）

**说明**：这些工具由 Agent 框架（如 LangChain, AutoGen, Claude Agent SDK 等）提供，用于 Agent 自身的任务调度和交互。2026 年主流框架均内置这些能力。

| 类型 | 包含工具 | 说明 |
|------|---------|------|
| **31. 任务管理** | launch_subagent, manage_todos | Agent 启动子任务、管理待办进度，需框架支持 |
| **32. 用户交互** | ask_user_question | Agent 向用户提问获取输入，需框架支持 |
| **33. Skill 执行** | execute_skill | Agent 执行预定义技能流程，需框架支持 |

#### 七、非工具说明（UI/CLI 逻辑）

**说明**：以下功能属于**用户界面层**（如 CLI 界面、Web 前端）的控制逻辑，**不应作为工具暴露给 LLM**。LLM 不需要调用它们，它们由用户在界面上触发。

| 功能 | 包含命令 | 归属 | 说明 |
|------|---------|------|------|
| **CLI 命令** | execute_slash_command | 前端/CLI | 用户输入 `/help`, `/clear` 等命令，由界面解析执行 |
| **模式切换** | enter_plan_mode, exit_plan_mode | 前端/CLI | 用户切换"计划模式"，由界面控制状态，LLM 只需配合展示 |

---

## 二十一、全部 Tool 汇总（按一级实现10类分类，仅限网上学习）

### 21.1 工具汇总说明

本章节整合第1-20章中提到的**网上学习的工具**，按**20.8章"一、核心业务工具（零依赖，Python 标准库实现）【一级实现的工具】"的10类**进行分类。

**数据来源**（仅来自网上学习）:
- MCP Filesystem Server（官方文档）
- LangChain FileManagementToolkit（官方 GitHub）
- Claude Code 内置工具（参考文档）

**不包括**: 我们 Omni 系统的工具

---

### 21.2 1类：文件操作

**说明**: 使用 `os`, `shutil`, `pathlib`, `glob` 实现，零依赖Python标准库。

#### 1. 读取文本文件（read_text_file）
**描述**: 读取文本文件完整内容，始终以 UTF-8 格式处理文件
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 文件的完整路径 |
| head | number | ❌ 否 | 读取前 N 行（不能与 tail 同时使用） |
| tail | number | ❌ 否 | 读取后 N 行 |

#### 2. 读取媒体文件（read_media_file）
**描述**: 读取图片或音频文件，返回 base64 编码数据和对应的 MIME 类型
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 媒体文件的完整路径 |

#### 3. 批量读文件（read_batch_file）
**描述**: 同时读取多个文件，单个文件读取失败不会中断整个操作
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_paths | string[] | ✅ 是 | 文件路径数组 |

#### 4. 读取多格式文件（read_file）
**描述**: 从文件系统读取文件，支持文本、图片、PDF、Jupyter notebook
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 文件的绝对路径 |
| offset | number | ❌ 否 | 起始行号，从1开始 |
| limit | number | ❌ 否 | 读取行数，默认2000行 |

#### 5. 写入或追加文件（write_append_file）
**描述**: 写入或追加到文件
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 文件路径 |
| text | string | ✅ 是 | 写入的文本内容 |
| append | boolean | ❌ 否 | 是否追加模式，默认 false |

#### 6. 精准替换文件内容（precise_replace_in_file）
**描述**: 执行精确的字符串替换
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 文件绝对路径 |
| old_string | string | ✅ 是 | 要替换的精确文本 |
| new_string | string | ✅ 是 | 替换后的文本 |
| replace_all | boolean | ❌ 否 | 替换所有匹配项，默认 false |

#### 7. 编辑文件（edit_file）
**描述**: 使用高级模式匹配进行选择性编辑，支持多同时编辑、缩进保留、dryRun 预览
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 要编辑的文件路径 |
| edits | array | ✅ 是 | 编辑操作数组，每个元素包含 oldText 和 newText |
| dryRun | boolean | ❌ 否 | 预览模式不实际修改，默认 false |

#### 8. 复制文件（copy_file）
**描述**: 复制文件
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| source_path | string | ✅ 是 | 源文件路径 |
| destination_path | string | ✅ 是 | 目标文件路径 |

#### 9. 移动或重命名文件（move_file）
**描述**: 移动或重命名文件
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| source_path | string | ✅ 是 | 源文件路径 |
| destination_path | string | ✅ 是 | 目标文件路径 |

#### 10. 重命名文件（rename_file）
**描述**: 重命名文件或目录，不改变所在目录
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 当前文件路径 |
| new_name | string | ✅ 是 | 新文件名 |

#### 11. 删除文件（delete_file）
**描述**: 删除文件
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 要删除的文件路径 |

#### 12. 搜索文件按模式（search_files）
**描述**: 递归搜索匹配或排除模式的文件/目录，返回完整路径
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| search_dir | string | ✅ 是 | 搜索起始目录 |
| pattern | string | ✅ 是 | 搜索模式（glob 风格） |
| excludePatterns | string[] | ❌ 否 | 排除模式 |

#### 13. 文件名模式匹配（glob_files）
**描述**: 快速的文件名模式匹配，按修改时间排序返回结果
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| pattern | string | ✅ 是 | Glob 模式（如 **/*.js, src/**/*.ts） |
| search_dir | string | ❌ 否 | 搜索目录，默认当前工作目录 |

#### 14. 搜索文件内容（grep_file_content）
**描述**: 基于 ripgrep 的强大内容搜索，支持正则表达式和多选项
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| pattern | string | ✅ 是 | 正则表达式搜索模式 |
| search_dir | string | ❌ 否 | 搜索路径，默认当前目录 |
| output_mode | string | ❌ 否 | 输出模式：content/files_with_matches/count |
| glob | string | ❌ 否 | 文件类型过滤（如 "*.ts"） |
| type | string | ❌ 否 | 语言类型（如 js, py, rust） |
| -A | number | ❌ 否 | 匹配后显示行数 |
| -B | number | ❌ 否 | 匹配前显示行数 |
| -C | number | ❌ 否 | 匹配前后显示行数 |
| -i | boolean | ❌ 否 | 不区分大小写 |
| -n | boolean | ❌ 否 | 显示行号 |
| multiline | boolean | ❌ 否 | 启用多行匹配（. 匹配换行符） |
| head_limit | number | ❌ 否 | 限制输出结果数量 |

#### 15. 创建目录（create_directory）
**描述**: 创建新目录，如需要会创建父目录，目录已存在则静默成功
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| dir_path | string | ✅ 是 | 目录路径 |

#### 16. 列出目录含大小（list_directory_with_sizes）
**描述**: 列出目录内容，包含文件大小，按 name 或 size 排序，返回统计信息
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| dir_path | string | ✅ 是 | 目录路径 |
| sortBy | string | ❌ 否 | 排序方式：name 或 size，默认 name |

#### 17. 获取目录树结构（get_directory_tree）
**描述**: 获取目录的递归 JSON 树结构，每个条目包含 name、type（file/directory）、children
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| dir_path | string | ✅ 是 | 起始目录 |
| excludePatterns | string[] | ❌ 否 | 排除模式（glob 格式） |

#### 18. 获取文件信息（get_file_info）
**描述**: 获取文件/目录的详细元数据，包括大小、创建/修改/访问时间、类型、权限
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| file_path | string | ✅ 是 | 文件或目录路径 |

#### 19. 列出允许访问的目录（list_allowed_directories）
**描述**: 列出服务器允许访问的所有目录
**参数**: 无参数

---

### 21.3 2类：Shell 命令执行

**说明**: 使用 `subprocess` 实现，零依赖Python标准库。

#### 20. 执行 Shell 命令（execute_shell_command）
**描述**: 在指定 shell 环境中执行命令。Windows 原生默认 PowerShell，可选 CMD；bash 需额外安装（未来扩展）。
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| command | string | ✅ 是 | 要执行的命令 |
| shell_type | string | ❌ 否 | 执行环境：powershell（默认）/ cmd / bash（未来扩展） |
| timeout | number | ❌ 否 | 超时毫秒数，默认120000，最大600000 |
| run_in_background | boolean | ❌ 否 | 后台运行命令 |

#### 21. 获取 Shell 输出（get_shell_output）
**描述**: 获取后台运行的 bash 命令输出
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| shell_id | string | ✅ 是 | 后台 shell 的 ID |
| filter | string | ❌ 否 | 过滤输出的正则表达式 |

#### 22. 终止 Shell 会话（terminate_shell）
**描述**: 终止运行中的后台 bash shell
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| shell_id | string | ✅ 是 | 要终止的 shell ID |

---

### 21.4 4类：网络通信

**说明**: 使用 `urllib`, `http.client` 实现，零依赖Python标准库。

#### 23. 获取网页内容（fetch_webpage）
**描述**: 获取和处理网页内容，带 AI 分析功能
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| url | string | ✅ 是 | 完全有效的 URL |
| prompt | string | ✅ 是 | 要从页面提取的信息 |

#### 24. 网络搜索（search_web）
**描述**: 搜索网络获取最新信息（仅美国可用）
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| query | string | ✅ 是 | 搜索查询字符串（至少2字符） |
| allowed_domains | string[] | ❌ 否 | 包含的域名数组 |
| blocked_domains | string[] | ❌ 否 | 排除的域名数组 |

---

### 21.5 3类：API/HTTP 调用

**说明**: 使用 `urllib`, `http.client` 实现，零依赖Python标准库。

#### 25. HTTP 请求（http_request）
**描述**: 发送 HTTP 请求到指定的 URL，支持 GET、POST、PUT、DELETE 等方法
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| url | string | ✅ 是 | 请求的目标 URL |
| method | string | ✅ 是 | HTTP 方法：GET、POST、PUT、DELETE、PATCH |
| headers | object | ❌ 否 | 请求头（如 {"Content-Type": "application/json"}） |
| body | string | ❌ 否 | 请求体（用于 POST、PUT、PATCH） |
| timeout | number | ❌ 否 | 超时毫秒数，默认30000 |

---

### 21.6 5类：时间/日期

**说明**: 使用 `datetime`, `time` 实现，零依赖Python标准库。

#### 26. 获取当前时间（get_current_time）
**描述**: 获取当前系统时间，支持多种格式输出
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| timezone | string | ❌ 否 | 时区（如 "Asia/Shanghai"，默认本地时区） |
| format | string | ❌ 否 | 输出格式（如 "YYYY-MM-DD HH:mm:ss"） |

#### 27. 计算日期（calculate_date）
**描述**: 计算指定日期偏移后的日期
**参数**:
| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| date | string | ✅ 是 | 起始日期（如 "2024-01-01"） |
| days | number | ❌ 否 | 偏移天数（正数为未来，负数为过去） |
| format | string | ❌ 否 | 输出格式，默认 "YYYY-MM-DD" |

---

### 21.7 工具总数汇总

| 一级10类 | 总数 | 已有数 | 缺少数 |
|---------|------|--------|--------|
| 1类：文件操作 | 19 | 19 | 0 |
| 2类：Shell命令执行 | 3 | 3 | 0 |
| 3类：API/HTTP调用 | 1 | 1 | 0 |
| 4类：网络通信 | 2 | 2 | 0 |
| 5类：时间/日期 | 2 | 2 | 0 |
| 6类：环境变量 | 2 | 0 | 2 |
| 7类：系统信息 | 1 | 0 | 1 |
| 8类：网络连接 | 2 | 0 | 2 |
| 9类：压缩/解压 | 2 | 0 | 2 |
| 10类：文件哈希 | 1 | 0 | 1 |
| **总计** | **35** | **27** | **8** |

**说明**:
- **总数**: 20.8章定义的每个一级类的工具总数（1类更新为19个）
- **已有数**: 21章中网上学习已收集的工具数量
- **缺少数**: 还需要通过网上学习补充的工具数量

**备注**: 21章仅汇总网上学习的工具，不包括Omni系统自身的工具定义。

---

**编写人**: 小沈
**更新时间**: 2026-04-04 17:50:00
**更新说明**: 
- 按20.8章一级实现的10类序号重新分类21章工具
- 21.2 → 1类：文件操作（19个工具）
- 21.3 → 2类：Shell命令执行（3个工具）
- 21.4 → 4类：网络通信（2个工具）
- 序号与20.8章标准保持一致
- 删除任务管理类7个工具
