# Function Call 缃戜笂瀛︿範鎬荤粨

**瀛︿範鏃堕棿**: 2026-04-04 05:08:51
**缂栧啓浜?*: 灏忔矆
**鐗堟湰**: v1.1
**鏇存柊璇存槑**: 
- 2026-04-04 06:56:00 - 淇绗?6-17绔犲唴瀹癸紝琛ュ厖鍑嗙‘鐨勬ā鍨嬪伐鍏烽檺鍒舵暟鎹?- 2026-04-04 09:00:00 - 淇绗?0绔狅細MCP Filesystem Server 宸ュ叿鏁伴噺 14鈫?3 涓紝淇鎼滅储鏍囪閿欒锛屽悓姝ヤ慨姝ｇ21绔犳眹鎬绘暟鎹?
---

## 涓€銆丗unction Calling 鏄粈涔?
Function Calling 璁?LLM 鑳藉璋冪敤澶栭儴鍑芥暟/宸ュ叿锛屽畬鎴愯濡傦細
- 鏌ヨ鏁版嵁搴?- 璋冪敤 API
- 璇诲啓鏂囦欢
- 鎵ц璁＄畻

**鏍稿績娴佺▼**:
```
鐢ㄦ埛杈撳叆 鈫?LLM 鍒ゆ柇闇€瑕佽皟鐢ㄥ伐鍏?鈫?杩斿洖宸ュ叿鍚?鍙傛暟 鈫?鎵ц鍑芥暟 鈫?杩斿洖缁撴灉 鈫?LLM 鐢熸垚鏈€缁堝洖绛?```

---

## 浜屻€佷富娴?LLM 骞冲彴鐨勫疄鐜?
### 2.1 OpenAI Function Calling

**瀹樻柟鏂囨。**: https://developers.openai.com/api/docs/guides/function-calling/

#### 宸ュ叿瀹氫箟 JSON Schema 瀹屾暣绀轰緥

```python
# 鏉ユ簮: OpenAI 瀹樻柟绀轰緥
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "鑾峰彇鎸囧畾浣嶇疆鐨勫綋鍓嶅ぉ姘?,
            "strict": True,  # 2024骞村悗鏂板涓ユ牸妯″紡
            "parameters": {
                "type": "object",
                "required": ["location"],
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "鍩庡競鍚嶇О锛屾牸寮忥細鍩庡競+鐪侊紝濡?鍖椾含銆佷笂娴?
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "娓╁害鍗曚綅",
                        "default": "celsius"
                    }
                },
                "additionalProperties": False
            }
        }
    }
]
```

#### 瀹屾暣璋冪敤浠ｇ爜锛堟潵鑷綉涓婃暀绋嬶級

```python
# 鏉ユ簮: reintech.io 鏁欑▼
from openai import OpenAI
import json

client = OpenAI(api_key="your-api-key")

# 瀹氫箟宸ュ叿
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

# 瀹為檯澶╂皵鍑芥暟
def get_current_weather(location, unit="fahrenheit"):
    weather_data = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"]
    }
    return json.dumps(weather_data)

# 鎵ц瀵硅瘽
def run_conversation(user_message):
    messages = [{"role": "user", "content": user_message}]
    
    # 绗竴娆¤皟鐢?- LLM 鍐冲畾鏄惁璋冪敤宸ュ叿
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
        
        # 鎵ц宸ュ叿璋冪敤
        available_functions = {"get_current_weather": get_current_weather}
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            
            # 璋冪敤鍑芥暟骞惰幏鍙栫粨鏋?            function_response = function_to_call(
                location=function_args.get("location"),
                unit=function_args.get("unit", "fahrenheit")
            )
            
            # 灏嗙粨鏋滆繑鍥炵粰 LLM
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": function_response,
            })
        
        # 绗簩娆¤皟鐢?- LLM 鐢熸垚鏈€缁堝洖澶?        second_response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages
        )
        
        return second_response.choices[0].message.content
    
    return response_message.content

# 浣跨敤
result = run_conversation("What's the weather like in Boston?")
print(result)
```

---

### 2.2 Claude Tool Use (Anthropic)

**瀹樻柟鏂囨。**: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview

#### 宸ュ叿瀹氫箟鏍煎紡

```python
# 鏉ユ簮: Claude 瀹樻柟鏂囨。
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

#### 鍏抽敭鐗规€?- **Strict Tool Use**: 浣跨敤 grammar-constrained sampling 淇濊瘉杈撳叆绗﹀悎 schema
- **Tool Search Tool**: 鏀寔鍔ㄦ€佸彂鐜板伐鍏凤紙閫傜敤浜庡ぇ閲忓伐鍏峰満鏅級

---

### 2.3 Pydantic AI 鐨勫伐鍏峰畾涔?
**瀹樻柟鏂囨。**: https://ai.pydantic.dev/tools/

#### 浣跨敤瑁呴グ鍣ㄥ畾涔夊伐鍏凤紙鏉ヨ嚜瀹樻柟绀轰緥锛?
```python
# 鏉ユ簮: Pydantic AI 瀹樻柟绀轰緥
import random
from pydantic_ai import Agent, RunContext

agent = Agent(
    'gemini-2.0-flash',
    deps_type=str,
    instructions="浣犳槸鎺烽瀛愭父鎴?
)

@agent.tool_plain  # 涓嶉渶瑕?context 鐨勫伐鍏?def roll_dice() -> str:
    """Roll a six-sided die and return the result."""
    return str(random.randint(1, 6))

@agent.tool  # 闇€瑕?context 鐨勫伐鍏?def get_player_name(ctx: RunContext[str]) -> str:
    """Get the player's name."""
    return ctx.deps

# 杩愯
result = agent.run_sync('My guess is 4', deps='Anne')
print(result.output)
```

#### 鑷姩鐢熸垚 Schema锛堟潵鑷畼鏂圭ず渚嬶級

```python
# 鏉ユ簮: Pydantic AI 瀹樻柟绀轰緥 - 鑷姩浠?docstring 鎻愬彇鍙傛暟鎻忚堪
@agent.tool_plain(docstring_format='google', require_parameter_descriptions=True)
def foobar(a: int, b: str, c: dict[str, list[float]]) -> str:
    """Get me foobar.

    Args:
        a: apple pie
        b: banana cake
        c: carrot smoothie
    """
    return f'{a} {b} {c}'

# 鐢熸垚鐨?schema:
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

**瀹樻柟鏂囨。**: https://modelcontextprotocol.io/specification/2025-11-25/server/tools

#### 宸ュ叿瀹氫箟鏍煎紡锛堟潵鑷畼鏂圭ず渚嬶級

```json
{
  "name": "get_weather",
  "title": "澶╂皵淇℃伅鏌ヨ",
  "description": "鑾峰彇鎸囧畾浣嶇疆鐨勫綋鍓嶅ぉ姘斾俊鎭?,
  "inputSchema": {
    "type": "object",
    "properties": {
      "location": {
        "type": "string",
        "description": "鍩庡競鍚嶇О鎴栭偖缂?
      }
    },
    "required": ["location"]
  },
  "outputSchema": {
    "type": "object",
    "properties": {
      "temperature": {"type": "number", "description": "娓╁害锛堟憚姘忓害锛?},
      "conditions": {"type": "string", "description": "澶╂皵鐘跺喌"}
    }
  }
}
```

---

## 涓夈€丳ython 鍑芥暟杞?JSON Schema 鐨勬柟娉?
### 3.1 鏂规硶1锛氱函 Python + inspect锛堟潵鑷?amitness.com锛?
```python
# 鏉ユ簮: https://amitness.com/posts/function-calling-schema/
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
        
        # 蹇呭～鍙傛暟鍒ゆ柇
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

# 浣跨敤
def add(a: int, b: int) -> int:
    """Adds two integers together"""
    return a + b

print(function_to_json(add))
# 杈撳嚭:
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

### 3.2 鏂规硶2锛氫娇鐢?Pydantic 鍔ㄦ€佹ā鍨嬶紙鏉ヨ嚜 amitness.com锛?
```python
# 鏉ユ簮: https://amitness.com/posts/function-calling-schema/
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
    
    # 鍒涘缓 Pydantic 妯″瀷
    p = create_model(f"`{f.__name__}`", **kws)
    
    return {
        "type": "function",
        "function": {
            "name": f.__name__,
            "description": f.__doc__,
            "parameters": p.model_json_schema(),
        },
    }

# 浣跨敤
def add(a: int, b: int) -> int:
    """Adds two integers together"""
    return a + b

print(schema(add))
```

### 3.3 鏂规硶3锛氫娇鐢?Pydantic TypeAdapter锛堟潵鑷?amitness.com锛?
```python
# 鏉ユ簮: https://amitness.com/posts/function-calling-schema/
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

# 浣跨敤
def add(a: int, b: int) -> int:
    """Adds two integers together"""
    return a + b

print(schema(add))
```

### 3.4 鏂规硶4锛氫娇鐢ㄨ楗板櫒妯″紡锛堟潵鑷?amitness.com锛?
```python
# 鏉ユ簮: https://amitness.com/posts/function-calling-schema/
def tool(func):
    """瑁呴グ鍣細鑷姩娣诲姞 json_schema 鏂规硶"""
    def json_schema():
        return function_to_json(func)
    func.json_schema = json_schema
    return func

@tool
def add(a: int, b: int) -> int:
    """Adds two numbers"""
    return a + b

# 浣跨敤
print(add.json_schema())
```

---

## 鍥涖€丣SON Schema 鍙傛暟绫诲瀷璇﹁В

### 4.1 鍩烘湰绫诲瀷锛堟潵鑷?jsonindenter.com锛?
| JSON Schema | 璇存槑 |
|-------------|------|
| `string` | 瀛楃涓?|
| `integer` | 鏁存暟 |
| `number` | 鏁板瓧锛堟暣鏁版垨娴偣锛?|
| `boolean` | 甯冨皵鍊?|
| `array` | 鏁扮粍 |
| `object` | 瀵硅薄 |
| `null` | 绌哄€?|

### 4.2 鍙傛暟绾︽潫绀轰緥

```json
{
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": "鐢ㄦ埛鍚嶇О"
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

## 浜斻€佸父瑙侀敊璇拰鏈€浣冲疄璺?
### 5.1 甯歌閿欒锛堟潵鑷?jsonindenter.com锛?
1. **缂哄皯 `type: "object"`**: parameters 蹇呴』浠?object 绫诲瀷涓烘牴
2. **灏鹃殢閫楀彿**: JSON 涓嶅厑璁稿熬闅忛€楀彿
3. **鍙傛暟鍚嶉敊璇?*: LLM 璋冪敤鏃跺繀椤讳娇鐢?schema 涓畾涔夌殑鍙傛暟鍚?4. **required 閬楁紡**: 蹇呭～鍙傛暟蹇呴』娣诲姞鍒?required 鏁扮粍
5. **鎻忚堪涓虹┖**: description 甯姪 LLM 鐞嗚В浣曟椂璋冪敤宸ュ叿

### 5.2 鏈€浣冲疄璺?
**濂界殑鎻忚堪**:
```python
description="鑾峰彇鎸囧畾浣嶇疆鐨勫綋鍓嶅ぉ姘斾俊鎭紝鍖呮嫭娓╁害銆佹箍搴︺€侀鍔涚瓑"
```

**宸殑鎻忚堪**:
```python
description="杩欐槸涓€涓ぉ姘斿嚱鏁?
```

---

## 鍏€佸弬鑰冭祫鏂?
1. OpenAI Function Calling: https://developers.openai.com/api/docs/guides/function-calling/
2. OpenAI 鏁欑▼: https://reintech.io/blog/openai-function-calling-complete-tutorial-with-examples
3. JSON Schema 鎸囧崡: https://jsonindenter.com/blog/json-for-ai-function-calling
4. Claude Tool Use: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
5. DeepSeek Tool Calls: https://api-docs.deepseek.com/guides/tool_calls
6. MCP 瑙勮寖: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
7. Pydantic AI: https://ai.pydantic.dev/tools/
8. 鍑芥暟杞?Schema: https://amitness.com/posts/function-calling-schema/

---

## 涓冦€丮CP Filesystem Server 鏂囦欢鎿嶄綔宸ュ叿锛堟潵鑷畼鏂癸級

**瀹樻柟浠撳簱**: https://github.com/modelcontextprotocol/servers
**瀹樻柟鏂囨。**: https://mcprepository.com/modelcontextprotocol/filesystem

MCP Filesystem Server 鎻愪緵浜?11 涓枃浠舵搷浣滃伐鍏凤紝鏄渶瀹屾暣鐨勬枃浠舵搷浣滃弬鑰冨疄鐜般€?
### 7.1 read_file - 璇诲彇鏂囦欢

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

**鍙傛暟**:
- `path` (string, required): 鏂囦欢璺緞

**瀹炵幇绀轰緥**:
```python
def read_file(path: str) -> str:
    """Read complete contents of a file"""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()
```

### 7.2 read_multiple_files - 璇诲彇澶氫釜鏂囦欢

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

**鍙傛暟**:
- `paths` (string[], required): 鏂囦欢璺緞鏁扮粍

### 7.3 write_file - 鍐欏叆鏂囦欢

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

**鍙傛暟**:
- `path` (string, required): 鏂囦欢璺緞
- `content` (string, required): 鏂囦欢鍐呭

**瀹炵幇绀轰緥**:
```python
def write_file(path: str, content: str) -> str:
    """Create or overwrite a file"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return f"File written successfully: {path}"
```

### 7.4 edit_file - 缂栬緫鏂囦欢

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

**鍙傛暟**:
- `path` (string, required): 鏂囦欢璺緞
- `edits` (array, required): 缂栬緫鎿嶄綔鏁扮粍
  - `oldText` (string): 瑕佹浛鎹㈢殑鏂囨湰
  - `newText` (string): 鏇挎崲鍚庣殑鏂囨湰
- `dryRun` (boolean, optional): 棰勮妯″紡锛岄粯璁?false

### 7.5 create_directory - 鍒涘缓鐩綍

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

**鍙傛暟**:
- `path` (string, required): 鐩綍璺緞

### 7.6 list_directory - 鍒楀嚭鐩綍

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

**鍙傛暟**:
- `path` (string, required): 鐩綍璺緞

### 7.7 directory_tree - 鐩綍鏍?
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

**鍙傛暟**:
- `path` (string, required): 鐩綍璺緞

### 7.8 move_file - 绉诲姩/閲嶅懡鍚嶆枃浠?
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

**鍙傛暟**:
- `source` (string, required): 婧愯矾寰?- `destination` (string, required): 鐩爣璺緞

### 7.9 search_files - 鎼滅储鏂囦欢

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

**鍙傛暟**:
- `path` (string, required): 鎼滅储璧峰鐩綍
- `pattern` (string, required): 鎼滅储妯″紡
- `excludePatterns` (string[], optional): 鎺掗櫎妯″紡

### 7.10 get_file_info - 鑾峰彇鏂囦欢淇℃伅

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

**鍙傛暟**:
- `path` (string, required): 鏂囦欢/鐩綍璺緞

**杩斿洖**:
- size (number): 鏂囦欢澶у皬
- creationTime (string): 鍒涘缓鏃堕棿
- lastModifiedTime (string): 淇敼鏃堕棿
- accessTime (string): 璁块棶鏃堕棿
- type (string): 绫诲瀷 (file/directory)
- permissions (string): 鏉冮檺

### 7.11 list_allowed_directories - 鍒楀嚭鍏佽鐨勭洰褰?
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

**鍙傛暟**: 鏃?
---

## 鍏€佹枃浠舵搷浣滃伐鍏峰弬鏁板姣旀€荤粨

| 宸ュ叿 | 鏍稿績鍙傛暟 | 鏉ユ簮 |
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
| list_allowed_directories | (鏃? | MCP |

---

## 涔濄€丏eepSeek Function Calling

**瀹樻柟鏂囨。**: https://api-docs.deepseek.com/guides/tool_calls

DeepSeek 鍏煎 OpenAI 鐨?function calling 鏍煎紡锛屾敮鎸佷互涓嬫ā鍨嬶細
- DeepSeek V3 绯诲垪
- DeepSeek R1 绯诲垪

**璋冪敤绀轰緥**锛堟潵鑷畼鏂癸級:

```python
# 鏉ユ簮: DeepSeek 瀹樻柟鏂囨。
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

**娉ㄦ剰**: 闇€瑕佹坊鍔?`"strict": true` 鍒?tool definitions锛堟潵鑷?GitHub issue #910锛?
---

## 鍗併€佸弬鑰冭祫鏂欙紙缁級

9. MCP Filesystem Server: https://mcprepository.com/modelcontextprotocol/filesystem
10. MCP GitHub: https://github.com/modelcontextprotocol/servers
11. DeepSeek Tool Calls: https://api-docs.deepseek.com/guides/tool_calls

---

**缂栧啓浜?*: 灏忔矆
**鏇存柊鏃堕棿**: 2026-04-04 05:24:55

---

## 鍗佷竴銆丩angChain 鏂囦欢绠＄悊宸ュ叿

**瀹樻柟鏂囨。**: https://python.langchain.com/docs/how_to/tool_calling

LangChain 鎻愪緵浜嗗畬鏁寸殑鏂囦欢绠＄悊宸ュ叿闆嗭紝鍩轰簬 Pydantic 妯″瀷瀹氫箟鍙傛暟銆?
### 11.1 ReadFileTool - 璇诲彇鏂囦欢

**鏉ユ簮**: LangChain 瀹樻柟 API 鏂囨。

```python
# LangChain ReadFileInput (Pydantic 妯″瀷)
class ReadFileInput(BaseModel):
    file_path: str = Field(..., description='name of file')
```

**JSON Schema 鍙傛暟**:
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

**瀹炵幇绀轰緥**:
```python
from langchain_community.tools.file_management import ReadFileTool

tool = ReadFileTool()
# 璋冪敤鏃跺弬鏁? file_path (string, required)
```

### 11.2 WriteFileTool - 鍐欏叆鏂囦欢

**鏉ユ簮**: LangChain 瀹樻柟 API 鏂囨。

```python
# LangChain WriteFileInput (Pydantic 妯″瀷)
class WriteFileInput(BaseModel):
    file_path: str = Field(..., description='name of file')
    text: str = Field(..., description='text to write to file')
    append: bool = Field(False, description='whether to append to file')
```

**JSON Schema 鍙傛暟**:
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

**瀹炵幇绀轰緥**:
```python
from langchain_community.tools.file_management import WriteFileTool

tool = WriteFileTool()
# 璋冪敤鏃跺弬鏁? file_path (string), text (string), append (boolean, optional)
```

### 11.3 LangChain 宸ュ叿鐗圭偣

1. **Pydantic 妯″瀷瀹氫箟**: 浣跨敤 Pydantic BaseModel 鑷姩鐢熸垚 JSON Schema
2. **args_schema 灞炴€?*: 姣忎釜宸ュ叿閮芥湁 `args_schema` 灞炴€ф寚鍚?Pydantic 妯″瀷
3. **绫诲瀷瀹夊叏**: 鑷姩楠岃瘉鍙傛暟绫诲瀷
4. **涓?LangChain Agent 闆嗘垚**: 鍙互鐩存帴浼犻€掔粰 agent

---

## 鍗佷簩銆丩lamaIndex Function Calling

**瀹樻柟鏂囨。**: https://docs.llamaindex.ai/en/stable/examples/workflow/function_calling_agent/

LlamaIndex 浣跨敤 `FunctionTool` 鏉ュ畾涔夊伐鍏枫€?
### 12.1 FunctionTool 瀹氫箟

**鏉ユ簮**: LlamaIndex 瀹樻柟鏁欑▼

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

### 12.2 LlamaIndex 宸ュ叿鐗圭偣

1. **鑷姩鐢熸垚 Schema**: `FunctionTool.from_defaults()` 鑷姩浠庡嚱鏁扮鍚嶇敓鎴?JSON Schema
2. **Docstring 鎻愬彇**: 浣跨敤鍑芥暟鐨?docstring 浣滀负宸ュ叿鎻忚堪
3. **绫诲瀷鎻愮ず**: 浣跨敤 Python 绫诲瀷鎻愮ず瀹氫箟鍙傛暟绫诲瀷
4. **Workflow 闆嗘垚**: 鍙互涓?LlamaIndex Workflow 娣卞害闆嗘垚

---

## 鍗佷笁銆丄utoGen Function Calling

**瀹樻柟鏂囨。**: https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/components/tools.html

AutoGen 鏄井杞殑寮€婧愬鏅鸿兘浣撴鏋躲€?
### 13.1 AutoGen 宸ュ叿鐗圭偣

1. **MCP 闆嗘垚**: 鏀寔杩炴帴 MCP (Model Context Protocol) 鏈嶅姟鍣?2. **浠ｇ爜鎵ц宸ュ叿**: 鍐呯疆浠ｇ爜鎵ц宸ュ叿
3. **绫诲瀷瀹夊叏**: 鏀寔寮虹被鍨嬪嚱鏁板畾涔?
### 13.2 AutoGen 鏂囦欢鎿嶄綔

**鏉ユ簮**: AutoGen 瀹樻柟鏂囨。

```python
from autogen_core import CancellationToken
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.tools.code_execution import PythonCodeExecutionTool

# 鍒涘缓浠ｇ爜鎵ц宸ュ叿
code_executor = DockerCommandLineCodeExecutor()
await code_executor.start()
```

---

## 鍗佸洓銆丆rewAI 鏂囦欢宸ュ叿

**瀹樻柟鏂囨。**: https://docs.crewai.com/en/tools/file-document/jsonsearchtool

CrewAI 鎻愪緵浜嗗绉嶆枃浠舵搷浣滃伐鍏枫€?
### 14.1 JSONSearchTool

**鏉ユ簮**: CrewAI 瀹樻柟鏂囨。

```python
from crewai_tools import JSONSearchTool

# 閫氱敤 JSON 鎼滅储
tool = JSONSearchTool()

# 闄愬埗鎼滅储鐗瑰畾 JSON 鏂囦欢
tool = JSONSearchTool(json_path='./path/to/your/file.json')
```

**鍙傛暟**:
- `json_path` (str, optional): 鎸囧畾瑕佹悳绱㈢殑 JSON 鏂囦欢璺緞

### 14.2 CrewAI 宸ュ叿鐗圭偣

1. **RAG 鎼滅储**: 浣跨敤 RAG (Retrieve and Generate) 鏈哄埗鎼滅储
2. **鍙厤缃?*: 鏀寔閰嶇疆涓嶅悓鐨?LLM 鍜?embedding 妯″瀷
3. **瀹為獙鎬?*: 閮ㄥ垎宸ュ叿鏍囪涓哄疄楠岄樁娈?
---

## 鍗佷簲銆丄zure OpenAI Function Calling

**瀹樻柟鏂囨。**: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/function-calling

Azure OpenAI 鍏煎 OpenAI 鐨?function calling 鏍煎紡銆?
### 15.1 Azure OpenAI 鐗圭偣

1. **鍏煎 OpenAI**: 浣跨敤涓?OpenAI 鐩稿悓鐨?JSON Schema 鏍煎紡
2. **浼佷笟绾?*: 鏀寔 Azure 鐨勫畨鍏ㄥ拰鍚堣鐗规€?3. **閮ㄧ讲閫夐」**: 鏀寔澶氱妯″瀷閮ㄧ讲

### 15.2 璋冪敤绀轰緥

```python
# 鏉ユ簮: Azure OpenAI 瀹樻柟绀轰緥
from openai import AzureOpenAI

client = AzureOpenAI(
    api_key="your-azure-api-key",
    api_version="2024-02-01",
    azure_endpoint="https://your-resource.openai.azure.com/"
)

response = client.chat.completions.create(
    model="gpt-4",
    messages=[{"role": "user", "content": "What's the weather like?"}],
    tools=tools  # 涓?OpenAI 鏍煎紡鐩稿悓
)
```

---

## 鍗佸叚銆佸悇涓绘祦妯″瀷 Function Calling 宸ュ叿鏁伴噺闄愬埗锛堝噯纭暟鎹級

### 16.1 OpenAI 妯″瀷宸ュ叿鏁伴噺闄愬埗

**瀹樻柟鏂囨。**: https://platform.openai.com/docs/guides/function-calling

**鍏抽敭鍙戠幇**:
- **宸ュ叿鏁伴噺闄愬埗**: 鏈€澶?**128 涓?*宸ュ叿锛?023骞?2鏈堢‘璁わ級
- **鏉ユ簮**: OpenAI 寮€鍙戣€呯ぞ鍖鸿璁猴紙https://community.openai.com/t/limit-on-the-number-of-functions-definitions-for-assistant/537992锛?- **璇存槑**: 姣忎釜宸ュ叿瀹氫箟鐨勫钩鍧?token 娑堣€楃害 123 tokens锛?28涓伐鍏风害娑堣€?15.7k tokens锛屾帴杩?128k 涓婁笅鏂囩獥鍙ｇ殑闄愬埗

**瀹為檯寤鸿**:
- 宸ュ叿鏁伴噺瓒呰繃 128 涓椂锛屾ā鍨嬮€夋嫨宸ュ叿鐨勫噯纭巼浼氭樉钁椾笅闄?- 瑙ｅ喅鏂规锛氫娇鐢?*宸ュ叿鍒嗙粍**鎴?*寰皟妯″瀷**

---

### 16.2 Claude Code 鍐呯疆宸ュ叿锛?025骞?2鏈堟暟鎹級

**鏁版嵁鏉ユ簮**: https://blog.thepete.net/claude-code-tools/锛?025骞?2鏈?鏃ユ洿鏂帮級

**鍐呯疆宸ュ叿鎬绘暟**: **18 涓?*

| 宸ュ叿鍚嶇О | 鍔熻兘鎻忚堪 | 鍙傛暟 |
|---------|---------|------|
| **Task** | 鍚姩瀛?agent 澶勭悊澶嶆潅浠诲姟 | description, prompt, subagent_type, model, resume |
| **Bash** | 鎵ц缁堢鍛戒护 | command, timeout, description, run_in_background, dangerouslyDisableSandbox |
| **Glob** | 鏂囦欢鍚嶆ā寮忓尮閰?| pattern, path |
| **Grep** | 鏂囦欢鍐呭鎼滅储 | pattern, path, glob, output_mode, -B, -A, -C, -n, -i, type, head_limit, offset, multiline |
| **ExitPlanMode** | 閫€鍑鸿鍒掓ā寮?| (鏃犲弬鏁? |
| **Read** | 璇诲彇鏂囦欢 | file_path, offset, limit |
| **Edit** | 缂栬緫鏂囦欢 | file_path, old_string, new_string, replace_all |
| **Write** | 鍐欏叆鏂囦欢 | file_path, content |
| **NotebookEdit** | 缂栬緫 Jupyter notebook | notebook_path, cell_id, new_source, cell_type, edit_mode |
| **WebFetch** | 鑾峰彇缃戦〉鍐呭 | url, prompt |
| **TodoWrite** | 浠诲姟鍒楄〃绠＄悊 | todos |
| **WebSearch** | 缃戠粶鎼滅储 | query, allowed_domains, blocked_domains |
| **BashOutput** | 鑾峰彇鍚庡彴鍛戒护杈撳嚭 | bash_id, filter |
| **KillShell** | 缁堟鍚庡彴鍛戒护 | shell_id |
| **AskUserQuestion** | 鍚戠敤鎴锋彁闂?| questions, answers |
| **Skill** | 鎵ц skill | skill |
| **SlashCommand** | 鎵ц鏂滄潬鍛戒护 | command |
| **EnterPlanMode** | 杩涘叆璁″垝妯″紡 | (鏃犲弬鏁? |

**鐗圭偣**:
- Claude Code 鍐呯疆宸ュ叿鏄浐瀹氱殑锛?*涓嶆敮鎸佽嚜瀹氫箟宸ュ叿**锛堜笌 MCP 闆嗘垚鏃跺彲閫氳繃 MCP 娣诲姞澶栭儴宸ュ叿锛?- 宸ュ叿鎸夊姛鑳藉垎绫伙細鏂囦欢鎿嶄綔锛圧ead/Edit/Write/Glob/Grep锛夈€佸懡浠ゆ墽琛岋紙Bash锛夈€佺綉缁滐紙WebFetch/WebSearch锛夈€佷换鍔＄鐞嗭紙Task/TodoWrite锛夈€佺敤鎴蜂氦浜掞紙AskUserQuestion锛?
---

### 16.3 MCP Filesystem Server 宸ュ叿锛堝畼鏂规渶鏂帮級

**鏁版嵁鏉ユ簮**: https://github.com/modelcontextprotocol/servers锛?025骞存渶鏂帮級

**宸ュ叿鎬绘暟**: **14 涓?*锛堟敞鎰忥細姣旀棭鏈熸枃妗ｄ腑鐨?11 涓浜?2 涓級

| 宸ュ叿鍚嶇О | 鍔熻兘 | 鍙傛暟 |
|---------|------|------|
| **read_text_file** | 璇诲彇鏂囨湰鏂囦欢 | path (string), head (number, optional), tail (number, optional) |
| **read_media_file** | 璇诲彇鍥剧墖/闊抽鏂囦欢 | path (string) |
| **read_multiple_files** | 璇诲彇澶氫釜鏂囦欢 | paths (string[]) |
| **write_file** | 鍐欏叆/瑕嗙洊鏂囦欢 | path (string), content (string) |
| **edit_file** | 缂栬緫鏂囦欢 | path (string), edits (array), dryRun (boolean, optional) |
| **create_directory** | 鍒涘缓鐩綍 | path (string) |
| **list_directory** | 鍒楀嚭鐩綍鍐呭 | path (string) |
| **list_directory_with_sizes** | 鍒楀嚭鐩綍鍐呭锛堝惈鏂囦欢澶у皬锛?| path (string), sortBy (string, optional) |
| **move_file** | 绉诲姩/閲嶅懡鍚嶆枃浠?| source (string), destination (string) |
| **search_files** | 閫掑綊鎼滅储鏂囦欢 | path (string), pattern (string), excludePatterns (string[], optional) |
| **directory_tree** | 鑾峰彇鐩綍鏍戠粨鏋?| path (string), excludePatterns (string[], optional) |
| **get_file_info** | 鑾峰彇鏂囦欢/鐩綍鍏冩暟鎹?| path (string) |
| **list_allowed_directories** | 鍒楀嚭鍏佽璁块棶鐨勭洰褰?| (鏃犲弬鏁? |
| **resource_templates** | 璧勬簮妯℃澘锛堟柊澧烇級 | (鏃犲弬鏁? |
| **read_resource** | 璇诲彇璧勬簮锛堟柊澧烇級 | uri (string) |

**娉ㄦ剰**: 
- 瀹樻柟 README 鏄剧ず 14 涓伐鍏凤紝涔嬪墠鐨勬枃妗ｅ彲鑳藉彧璁板綍浜?11 涓?- 鏂板浜?`read_media_file`锛堣鍙栧獟浣撴枃浠讹級鍜?`list_directory_with_sizes`锛堝甫澶у皬鐨勭洰褰曞垪琛級
- 璇︾粏鍙傛暟瑙佸畼鏂规枃妗ｏ細https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem

---

### 16.4 閫氫箟鍗冮棶 (Qwen) Function Calling

**瀹樻柟鏂囨。**: 
- https://help.aliyun.com/zh/model-studio/qwen-function-calling
- https://qwen.readthedocs.io/en/stable/framework/function_call.html

**鏀寔鐨勬ā鍨?*:
- 閫氫箟鍗冮棶-Max
- 閫氫箟鍗冮棶-Plus
- 閫氫箟鍗冮棶-Turbo
- Qwen2.5 绯诲垪
- Qwen2 绯诲垪
- Qwen1.5 绯诲垪

**宸ュ叿瀹氫箟鏍煎紡**: 鍏煎 OpenAI 鏍煎紡

**宸ュ叿鏁伴噺闄愬埗**: 
- 瀹樻柟鏈槑纭叕甯冨叿浣撴暟閲忛檺鍒?- 鎺ㄦ祴涓?OpenAI 绫讳技锛屽彈闄愪簬涓婁笅鏂囩獥鍙ｅぇ灏?- 寤鸿鎺у埗鍦?128 涓互鍐呬互鑾峰緱鏈€浣虫晥鏋?
---

### 16.5 鍏朵粬鍥藉唴澶фā鍨?
| 妯″瀷 | Function Calling 鏀寔 | 宸ュ叿鏁伴噺闄愬埗 | 鏍煎紡 |
|-----|----------------------|-------------|------|
| **鐧惧害鏂囧績** | 鏀寔 | 鏈叕寮€ | 鍏煎 OpenAI |
| **璁鏄熺伀** | 閮ㄥ垎鏀寔 | 鏈叕寮€ | 閮ㄥ垎鍏煎 |
| **鏅鸿氨娓呰█** | 鏀寔 | 鏈叕寮€ | 鍏煎 OpenAI |
| **DeepSeek** | 鏀寔 | 鏈叕寮€ | 鍏煎 OpenAI锛岄渶娣诲姞 strict: true |

---

### 16.6 鍏抽敭鏁版嵁姹囨€昏〃

| 骞冲彴/妯″瀷 | 宸ュ叿鏁伴噺 | 鏁版嵁鏉ユ簮 | 澶囨敞 |
|----------|---------|---------|------|
| **OpenAI (GPT-4)** | 鏈€澶?128 | 绀惧尯璁ㄨ 2023-12 | 瓒呰繃鍚庡噯纭巼涓嬮檷 |
| **Claude Code** | 18 涓唴缃?| 鍗氬 2025-12 | 鍥哄畾宸ュ叿闆?|
| **MCP Filesystem** | 14 涓?| 瀹樻柟 GitHub 2025 | 瀹樻柟鏈€鏂版暟鎹?|
| **閫氫箟鍗冮棶** | 鏈叕寮€ | 瀹樻柟鏂囨。 | 寤鸿 <128 |
| **鐧惧害/璁/鏅鸿氨** | 鏈叕寮€ | 瀹樻柟鏂囨。 | 鍏煎 OpenAI 鏍煎紡 |

---

### 16.7 閲嶈缁撹

1. **宸ュ叿鏁伴噺涓嶆槸瓒婂瓒婂ソ**锛氳秴杩?128 涓伐鍏峰悗锛屾ā鍨嬮€夋嫨鍑嗙‘鐜囦細鏄捐憲涓嬮檷
2. **MCP 鏄渶瀹屾暣鐨勬枃浠舵搷浣滄柟妗?*锛?4 涓伐鍏凤紝瑕嗙洊璇汇€佸啓銆佺紪杈戙€佹悳绱€佸厓鏁版嵁绛?3. **Claude Code 宸ュ叿鍥哄畾**锛氬唴缃?18 涓伐鍏凤紝涓嶆敮鎸佽嚜瀹氫箟锛堥渶閫氳繃 MCP 鎵╁睍锛?4. **鍥藉唴澶фā鍨嬪吋瀹?OpenAI**锛氬伐鍏峰畾涔夋牸寮忎笌 OpenAI 鐩稿悓

---

## 鍗佷竷銆乄indows 骞冲彴 MCP 宸ュ叿姹囨€伙紙閲嶇偣锛侊級

### 17.1 Windows 涓撶敤 MCP 鏈嶅姟鍣ㄦ瑙?
| 鏈嶅姟鍣?| 宸ュ叿鏁伴噺 | Stars | 鏍稿績鍔熻兘 |
|--------|---------|-------|---------|
| **Windows-MCP** (CursorTouch) | 15+ | 5000+ | 榧犳爣/閿洏/鎴浘/绐楀彛/Shell/娉ㄥ唽琛?|
| **MCPControl** | 10+ | 307 | 榧犳爣/閿洏/绐楀彛/灞忓箷/鍓创鏉?|
| **WinRemote-MCP** | 40+ | 89 | 妗岄潰鎺у埗/杩涚▼/鏈嶅姟/娉ㄥ唽琛?缃戠粶/OCR |

---

### 17.2 Windows-MCP (CursorTouch) - 鏈€娴佽鐨?Windows MCP

**GitHub**: https://github.com/CursorTouch/Windows-MCP锛?000+ stars锛?
**鏀寔鐨勫鎴风**: Claude Desktop, Claude Code, Cursor, Perplexity, Gemini CLI, Codex, Qwen Code

**宸ュ叿鍒楄〃**:

| 宸ュ叿 | 鍔熻兘鎻忚堪 | 鏍稿績鍙傛暟 |
|-----|---------|----------|
| **Click** | 榧犳爣鐐瑰嚮 | x, y, button (left/right/middle), click_type (single/double) |
| **Type** | 閿洏杈撳叆 | text, clear (鍙€夋竻闄ょ幇鏈夋枃鏈? |
| **Scroll** | 婊氬姩 | direction (up/down/left/right), amount |
| **Move** | 榧犳爣绉诲姩/鎷栨嫿 | x, y, drag (甯冨皵鍊? |
| **Shortcut** | 蹇嵎閿?| keys (濡?Ctrl+c, Alt+Tab) |
| **Wait** | 鏆傚仠绛夊緟 | duration (绉? |
| **Screenshot** | 蹇€熸埅鍥?| display (鍙€夊睆骞曠紪鍙?, scale (缂╂斁) |
| **Snapshot** | 瀹屾暣妗岄潰鐘舵€?| use_vision, use_dom, display |
| **App** | 搴旂敤鎿嶄綔 | action (launch/switch/resize), name, args |
| **Shell** | PowerShell鎵ц | command, cwd (鍙€夊伐浣滅洰褰? |
| **Scrape** | 缃戦〉鎶撳彇 | url |
| **MultiSelect** | 澶氶€?| coordinates[], ctrl (鏄惁鎸塁trl) |
| **MultiEdit** | 澶氬缂栬緫 | fields [{x, y, text}] |
| **Clipboard** | 鍓创鏉?| action (read/write), content |
| **Process** | 杩涚▼绠＄悊 | action (list/kill), pid, name |
| **Notification** | Windows閫氱煡 | title, message |
| **Registry** | 娉ㄥ唽琛?| action (read/write/delete/list), path, name, value |

**瀹夎鏂瑰紡**:
```bash
# 鎺ㄨ崘浣跨敤 uvx
uvx windows-mcp

# 鎴栭€氳繃 Claude Code
claude mcp add --transport stdio windows-mcp -- uvx windows-mcp
```

**鐗圭偣**:
- 鉁?鏀寔浠讳綍 LLM锛堜笉渚濊禆鐗瑰畾瑙嗚妯″瀷锛?- 鉁?杞婚噺绾у紑婧?- 鉁?寤惰繜 0.2-0.9 绉?- 鉁?鏀寔鏈湴/杩滅▼妯″紡

---

### 17.3 MCPControl - Windows OS 鑷姩鍖?
**GitHub**: https://github.com/claude-did-this/MCPControl锛?07 stars锛?
**宸ュ叿鍒楄〃**:

| 宸ュ叿 | 鍔熻兘鎻忚堪 | 鏍稿績鍙傛暟 |
|-----|---------|----------|
| **Window Management** | 绐楀彛绠＄悊 | list_windows, get_active_window, focus_window, resize_window |
| **Mouse Control** | 榧犳爣鎺у埗 | move, click, drag, scroll, position |
| **Keyboard Control** | 閿洏鎺у埗 | type_text, key_combo, press_key, hold_key |
| **Screen Capture** | 灞忓箷鎴浘 | screenshot, capture_window, screen_size |
| **Clipboard** | 鍓创鏉?| read, write |

**瀹夎鏂瑰紡**:
```bash
npm install -g mcp-control
mcp-control --sse
```

**瀹夊叏鎻愮ず**: 瀹為獙鎬ц蒋浠讹紝鏈夐闄?
---

### 17.4 WinRemote-MCP - 40+ 宸ュ叿鐨勪紒涓氱骇鏂规

**GitHub**: https://github.com/dddabtc/winremote-mcp锛?9 stars锛?
**璇︾粏宸ュ叿鍒楄〃**:

**妗岄潰鎺у埗**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| Snapshot | 鎴浘 | quality, max_width, monitor |
| AnnotatedSnapshot | 鏍囨敞鎴浘 | - |
| OCR | 鏂囧瓧璇嗗埆 | - |
| ScreenRecord | 灞忓箷褰曞埗 | - |

**杈撳叆鎺у埗**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| Click | 鐐瑰嚮 | x, y, button, click_type |
| Type | 杈撳叆 | text, x, y |
| Scroll | 婊氬姩 | direction, amount |
| Move | 绉诲姩 | x, y, drag |
| Shortcut | 蹇嵎閿?| keys |
| Wait | 绛夊緟 | duration |

**绐楀彛绠＄悊**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| FocusWindow | 鑱氱劍绐楀彛 | title |
| MinimizeAll | 鏈€灏忓寲鍏ㄩ儴 | - |
| App | 搴旂敤鎿嶄綔 | action, name, args |

**绯荤粺鎿嶄綔**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| Shell | PowerShell | command, cwd |
| GetClipboard | 璇诲壀璐存澘 | - |
| SetClipboard | 鍐欏壀璐存澘 | content |
| ListProcesses | 杩涚▼鍒楄〃 | - |
| KillProcess | 缁堟杩涚▼ | pid, name |
| GetSystemInfo | 绯荤粺淇℃伅 | - |
| Notification | 閫氱煡 | title, message |
| LockScreen | 閿佸睆 | - |

**鏂囦欢鎿嶄綔**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| FileRead | 璇诲彇 | path |
| FileWrite | 鍐欏叆 | path, content |
| FileList | 鍒楄〃 | path |
| FileSearch | 鎼滅储 | path, pattern |
| FileDownload | 涓嬭浇 | path |
| FileUpload | 涓婁紶 | content, path |

**娉ㄥ唽琛?鏈嶅姟**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| RegRead | 璇绘敞鍐岃〃 | path, name |
| RegWrite | 鍐欐敞鍐岃〃 | path, name, value |
| ServiceList | 鏈嶅姟鍒楄〃 | - |
| ServiceStart | 鍚姩鏈嶅姟 | name |
| ServiceStop | 鍋滄鏈嶅姟 | name |

**璁″垝浠诲姟**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| TaskList | 浠诲姟鍒楄〃 | - |
| TaskCreate | 鍒涘缓浠诲姟 | name, command, schedule |
| TaskDelete | 鍒犻櫎浠诲姟 | name |

**缃戠粶宸ュ叿**:
| 宸ュ叿 | 鍔熻兘 | 鍙傛暟 |
|-----|------|------|
| Scrape | 缃戦〉鎶撳彇 | url |
| Ping | Ping | host |
| PortCheck | 绔彛妫€鏌?| host, port |
| NetConnections | 缃戠粶杩炴帴 | - |
| EventLog | 浜嬩欢鏃ュ織 | - |

**瀹夊叏灞傜骇**:
- **Tier 1** (鍙): Snapshot, GetSystemInfo, ListProcesses - 榛樿鍚敤
- **Tier 2** (浜や簰): Click, Type, Shortcut, App - 榛樿鍚敤
- **Tier 3** (鍗遍櫓): Shell, FileWrite, KillProcess, RegWrite - 榛樿绂佺敤

---

### 17.5 Windows 鐗规湁宸ュ叿瀵规瘮

| 鍔熻兘 | Windows-MCP | MCPControl | WinRemote-MCP |
|-----|------------|------------|---------------|
| 榧犳爣鎺у埗 | 鉁?| 鉁?| 鉁?|
| 閿洏杈撳叆 | 鉁?| 鉁?| 鉁?|
| 鎴浘 | 鉁?| 鉁?| 鉁?|
| 绐楀彛绠＄悊 | 鉁?| 鉁?| 鉁?|
| Shell/PowerShell | 鉁?| 鉂?| 鉁?|
| 杩涚▼绠＄悊 | 鉁?| 鉂?| 鉁?|
| 娉ㄥ唽琛?| 鉁?| 鉂?| 鉁?|
| 鏈嶅姟绠＄悊 | 鉂?| 鉂?| 鉁?|
| 鍓创鏉?| 鉁?| 鉁?| 鉁?|
| OCR | 鉂?| 鉂?| 鉁?|
| 灞忓箷褰曞埗 | 鉂?| 鉂?| 鉁?|
| 缃戠粶宸ュ叿 | 鉂?| 鉂?| 鉁?|

---

### 17.6 Windows MCP 宸ュ叿鍙傛暟鍛藉悕瑙勮寖

**璺緞绫?*:
- `path` - 鏂囦欢/鐩綍璺緞
- `cwd` - 褰撳墠宸ヤ綔鐩綍

**鍧愭爣绫?*:
- `x`, `y` - 灞忓箷鍧愭爣
- `display` - 鏄剧ず鍣ㄧ紪鍙?
**鎿嶄綔绫?*:
- `action` - 鎿嶄綔绫诲瀷 (list/kill/read/write 绛?
- `button` - 榧犳爣鎸夐挳 (left/right/middle)
- `click_type` - 鐐瑰嚮绫诲瀷 (single/double)

**鍐呭绫?*:
- `text` / `content` - 鏂囨湰鍐呭
- `command` - 鍛戒护瀛楃涓?
**鎺у埗绫?*:
- `drag` - 鏄惁鎷栨嫿
- `scale` - 缂╂斁姣斾緥

---

## 鍗佸叓銆佷富娴?Agent 宸ュ叿鏁伴噺瀵规瘮涓庨€夋嫨寤鸿

### 18.1 鍚勫钩鍙板伐鍏锋暟閲忔€昏

| 骞冲彴/妯″瀷 | 鏂囦欢鎿嶄綔 | Windows 鐗规湁 | 鎬昏绾?|
|---------|---------|-------------|-------|
| **MCP Filesystem** | 14 | 0 | 14 |
| **LangChain** | 7 | 0 | 7 |
| **Claude Code** | 4 | 14 | 18 |
| **Windows-MCP** | 0 | 15+ | 15+ |
| **WinRemote-MCP** | 6 | 40+ | 40+ |
| **OpenAI (GPT-4)** | 鑷畾涔?| 鑷畾涔?| 鈮?28 |

### 18.2 閫夋嫨寤鸿

**鏂囦欢鎿嶄綔涓轰富**:
- 鎺ㄨ崘 MCP Filesystem (14涓伐鍏? - 瀹樻柟缁存姢锛屾渶绋冲畾

**Windows 妗岄潰鑷姩鍖?*:
- 鎺ㄨ崘 Windows-MCP (15+宸ュ叿) - 5000+ stars锛屾渶娴佽
- 鎴?WinRemote-MCP (40+宸ュ叿) - 鍔熻兘鏈€鍏紝浼佷笟绾?
**缁煎悎搴旂敤**:
- OpenAI + MCP Filesystem + Windows-MCP 缁勫悎

---

### 18.3 閲嶈缁撹

1. **Windows MCP 宸ュ叿鐢熸€佷赴瀵?*: 鏈夊绉嶅紑婧愭柟妗堝彲閫?2. **宸ュ叿鏁伴噺涓庡鏉傚害姝ｇ浉鍏?*: WinRemote 鏈?40+ 宸ュ叿锛屼絾閰嶇疆鏇村鏉?3. **瀹夊叏灞傜骇寰堥噸瑕?*: WinRemote 鐨?Tier 绯荤粺鍊煎緱鍊熼壌
4. **杩滅▼璁块棶鏄秼鍔?*: Windows-MCP 鏀寔鏈湴/杩滅▼妯″紡

---

### 18.4 鍙傝€冧环鍊兼帓鍚?
| 鏉ユ簮 | 浠峰€?| 閫傜敤鍦烘櫙 |
|-----|------|---------|
| Windows-MCP (CursorTouch) | 鈽呪槄鈽呪槄鈽?| Windows 妗岄潰鑷姩鍖栭閫?|
| WinRemote-MCP | 鈽呪槄鈽呪槄鈽?| 浼佷笟绾?Windows 鎺у埗 |
| MCPControl | 鈽呪槄鈽呪槄鈽?| 杞婚噺绾ц嚜鍔ㄥ寲 |
| MCP Filesystem | 鈽呪槄鈽呪槄鈽?| 璺ㄥ钩鍙版枃浠舵搷浣?|
| OpenAI Function Calling | 鈽呪槄鈽呪槄鈽?| 閫氱敤宸ュ叿瀹氫箟鏍囧噯 |

---

## 鍗佷節銆佸弬鑰冭祫鏂欙紙缁?锛?
12. LangChain Tools: https://python.langchain.com/docs/how_to/tool_calling
13. LangChain File Management: https://docs.langchain.com/oss/python/integrations/tools/filesystem
14. LlamaIndex Workflow: https://docs.llamaindex.ai/en/stable/examples/workflow/function_calling_agent/
15. AutoGen Tools: https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/components/tools.html
16. CrewAI Tools: https://docs.crewai.com/en/concepts/tools
17. Azure OpenAI: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/function-calling
18. 閫氫箟鍗冮棶 Function Calling: https://help.aliyun.com/zh/model-studio/qwen-function-calling
19. Qwen Framework: https://qwen.readthedocs.io/en/stable/framework/function_call.html

---

**缂栧啓浜?*: 灏忔矆
**鏇存柊鏃堕棿**: 2026-04-04 07:15:00
**鏇存柊璇存槑**: 
- 淇绗?6-17绔犲唴瀹癸紝琛ュ厖鍑嗙‘鐨勬ā鍨嬪伐鍏烽檺鍒舵暟鎹紙OpenAI 128涓檺鍒躲€丆laude Code 18涓€丮CP 14涓級
- 鏂板绗?7绔狅細Windows 骞冲彴 MCP 宸ュ叿姹囨€伙紙Windows-MCP 5000+ stars銆丮CPControl 307 stars銆乄inRemote-MCP 40+ tools锛?- 鏂板绗?8绔狅細涓绘祦 Agent 宸ュ叿鏁伴噺瀵规瘮涓庨€夋嫨寤鸿

---

## 浜屽崄銆佹墍鏈?File Tool 瀹屾暣鍙傛暟鎬荤粨锛堝繀璇伙級

### 20.1 MCP Filesystem Server (13涓伐鍏? - 瀹樻柟鏈€鏂版暟鎹?
**鏉ユ簮**: 瀹樻柟 GitHub 浠撳簱 https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem锛?026骞?鏈堟洿鏂帮級

**閲嶈璇存槑**: 
- 瀹樻柟鏈€鏂版樉绀?**13 涓?*宸ュ叿
- 鏂板宸ュ叿锛歚read_media_file`銆乣list_directory_with_sizes`
- 娉ㄦ剰锛歚resource_templates` 鍜?`read_resource` 灞炰簬 MCP Resources 鑳藉姏锛屼笉灞炰簬 Tools
- 浠ヤ笅鏄缁嗗弬鏁帮紙鏉ヨ嚜瀹樻柟 README锛夛細

| 宸ュ叿鍚嶇О | 鍙傛暟 | 鍙傛暟绫诲瀷 | 蹇呭～ | 璇存槑 |
|---------|------|---------|-----|------|
| **read_text_file** | path | string | 鉁?鏄?| 鏂囦欢璺緞 |
| | head | number | 鉂?鍚?| 璇诲彇鍓?N 琛岋紙涓嶈兘涓?tail 鍚屾椂鐢級 |
| | tail | number | 鉂?鍚?| 璇诲彇鍚?N 琛?|
| **read_media_file** | path | string | 鉁?鏄?| 鍥剧墖/闊抽鏂囦欢璺緞锛岃繑鍥?base64 + MIME 绫诲瀷 |
| **read_multiple_files** | paths | string[] | 鉁?鏄?| 鏂囦欢璺緞鏁扮粍锛屽崟涓け璐ヤ笉浼氫腑鏂?|
| **write_file** | path | string | 鉁?鏄?| 鏂囦欢璺緞 |
| | content | string | 鉁?鏄?| 鏂囦欢鍐呭 |
| **edit_file** | path | string | 鉁?鏄?| 鏂囦欢璺緞 |
| | edits | array | 鉁?鏄?| 缂栬緫鎿嶄綔鏁扮粍 [{oldText, newText}] |
| | dryRun | boolean | 鉂?鍚?| 棰勮妯″紡锛岄粯璁?false |
| **create_directory** | path | string | 鉁?鏄?| 鐩綍璺緞锛屼細鍒涘缓鐖剁洰褰?|
| **list_directory** | path | string | 鉁?鏄?| 鐩綍璺緞锛屽甫 [FILE]/[DIR] 鍓嶇紑 |
| **list_directory_with_sizes** | path | string | 鉁?鏄?| 鐩綍璺緞 |
| | sortBy | string | 鉂?鍚?| 鎺掑簭鏂瑰紡 (name/size)锛岄粯璁?name |
| **move_file** | source | string | 鉁?鏄?| 婧愯矾寰?|
| | destination | string | 鉁?鏄?| 鐩爣璺緞锛岀洰鏍囧瓨鍦ㄤ細澶辫触 |
| **search_files** | path | string | 鉁?鏄?| 鎼滅储璧峰鐩綍 |
| | pattern | string | 鉁?鏄?| 鎼滅储妯″紡锛坓lob 椋庢牸锛?|
| | excludePatterns | string[] | 鉂?鍚?| 鎺掗櫎妯″紡 |
| **directory_tree** | path | string | 鉁?鏄?| 鐩綍璺緞锛岃繑鍥?JSON 鏍戠粨鏋?|
| | excludePatterns | string[] | 鉂?鍚?| 鎺掗櫎妯″紡 |
| **get_file_info** | path | string | 鉁?鏄?| 鏂囦欢/鐩綍璺緞锛岃繑鍥炲ぇ灏忋€佸垱寤?淇敼/璁块棶鏃堕棿銆佺被鍨嬨€佹潈闄?|
| **list_allowed_directories** | (鏃? | - | - | 鏃犲弬鏁帮紝杩斿洖鍏佽璁块棶鐨勭洰褰曞垪琛?|

---

### 20.1.1 MCP ToolAnnotations锛堥噸瑕佸畨鍏ㄦ彁绀猴級

MCP 瀹樻柟瀹氫箟浜嗗伐鍏风殑**鍙**銆?*骞傜瓑**銆?*鐮村潖鎬?*灞炴€э紝甯姪瀹㈡埛绔纭鐞嗗伐鍏凤細

| 宸ュ叿 | readOnly | idempotent | destructive | 璇存槑 |
|-----|----------|------------|-------------|------|
| read_text_file | 鉁?true | - | - | 绾鎿嶄綔 |
| read_media_file | 鉁?true | - | - | 绾鎿嶄綔 |
| read_multiple_files | 鉁?true | - | - | 绾鎿嶄綔 |
| list_directory | 鉁?true | - | - | 绾鎿嶄綔 |
| list_directory_with_sizes | 鉁?true | - | - | 绾鎿嶄綔 |
| directory_tree | 鉁?true | - | - | 绾鎿嶄綔 |
| search_files | 鉁?true | - | - | 绾鎿嶄綔 |
| get_file_info | 鉁?true | - | - | 绾鎿嶄綔 |
| list_allowed_directories | 鉁?true | - | - | 绾鎿嶄綔 |
| **create_directory** | 鉂?false | 鉁?true | 鉂?false | 閲嶅鍒涘缓鏄┖鎿嶄綔 |
| **write_file** | 鉂?false | 鉁?true | 鉁?true | 瑕嗙洊宸叉湁鏂囦欢 |
| **edit_file** | 鉂?false | 鉂?false | 鉁?true | 閲嶅缂栬緫鍙兘澶辫触鎴栭噸澶嶅簲鐢?|
| **move_file** | 鉂?false | 鉂?false | 鉁?true | 鍒犻櫎婧愭枃浠?|

**瀹夊叏寤鸿**:
- `readOnly=false` 涓?`destructive=true` 鐨勫伐鍏凤紙write_file, edit_file, move_file锛夐渶璋ㄦ厧浣跨敤
- `edit_file` 寤鸿濮嬬粓鍏堢敤 `dryRun=true` 棰勮
- `move_file` 鐩爣瀛樺湪浼氬け璐?
---

### 20.2 LangChain FileManagementToolkit (7涓伐鍏?

**鏉ユ簮**: 瀹樻柟 GitHub 浠撳簱 https://github.com/langchain-ai/langchain-community

| 宸ュ叿鍚嶇О | 鍙傛暟 | 鍙傛暟绫诲瀷 | 蹇呭～ | 璇存槑 |
|---------|------|---------|-----|------|
| **ReadFileTool** | file_path | string | 鉁?鏄?| 鏂囦欢璺緞 |
| **WriteFileTool** | file_path | string | 鉁?鏄?| 鏂囦欢璺緞 |
| | text | string | 鉁?鏄?| 鍐欏叆鏂囨湰 |
| | append | boolean | 鉂?鍚?| 鏄惁杩藉姞锛岄粯璁?false |
| **CopyFileTool** | source_path | string | 鉁?鏄?| 婧愭枃浠惰矾寰?|
| | destination_path | string | 鉁?鏄?| 鐩爣鏂囦欢璺緞 |
| **MoveFileTool** | source_path | string | 鉁?鏄?| 婧愭枃浠惰矾寰?|
| | destination_path | string | 鉁?鏄?| 鐩爣鏂囦欢璺緞 |
| **DeleteFileTool** | file_path | string | 鉁?鏄?| 瑕佸垹闄ょ殑鏂囦欢璺緞 |
| **FileSearchTool** | pattern | string | 鉁?鏄?| Unix shell 鍖归厤妯″紡 |
| | dir_path | string | 鉂?鍚?| 鎼滅储鐩綍锛岄粯璁?"." |
| **ListDirectoryTool** | dir_path | string | 鉂?鍚?| 鍒楀嚭鐩綍锛岄粯璁?"." |

**LangChain JSON Schema 绀轰緥**:
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

### 20.3 鍙傛暟绫诲瀷姹囨€?
| 鍙傛暟绫诲瀷 | 璇存槑 | 绀轰緥 |
|---------|------|------|
| **string** | 瀛楃涓?| path, file_path, source_path |
| **string[]** | 瀛楃涓叉暟缁?| paths, excludePatterns |
| **boolean** | 甯冨皵鍊?| append, dryRun |
| **array** | 鏁扮粍 | edits (鍖呭惈 oldText, newText) |
| **鏃犲弬鏁?* | 涓嶉渶瑕佸弬鏁?| list_allowed_directories |

---

### 20.4 鍙傛暟鍛藉悕瀵规瘮锛圡CP vs LangChain锛?
| 鍔熻兘 | MCP 鍙傛暟鍚?| LangChain 鍙傛暟鍚?|
|-----|-----------|-----------------|
| 璇诲彇鏂囦欢 | path | file_path |
| 鍐欏叆鏂囦欢 | path, content | file_path, text |
| 澶嶅埗鏂囦欢 | - | source_path, destination_path |
| 绉诲姩鏂囦欢 | source, destination | source_path, destination_path |
| 鍒犻櫎鏂囦欢 | - | file_path |
| 鍒楀嚭鐩綍 | path | dir_path |
| 鎼滅储鏂囦欢 | path, pattern | pattern, dir_path |

---

### 20.5 鎵€鏈夊钩鍙?File Tool 瀹屾暣瀵规瘮琛?
| 宸ュ叿鍔熻兘 | MCP (14涓? | LangChain (7涓? | 澶囨敞 |
|---------|-----------|-----------------|------|
| **璇诲彇鍗曚釜鏂囦欢** | read_text_file (path, head, tail) | ReadFileTool (file_path) | MCP 鏀寔 head/tail |
| **璇诲彇澶氫釜鏂囦欢** | read_multiple_files (paths) | 鉂?| MCP 鐙湁 |
| **璇诲彇濯掍綋鏂囦欢** | read_media_file (path) | 鉂?| MCP 鐙湁锛岃繑鍥?base64 |
| **鍐欏叆鏂囦欢** | write_file (path, content) | WriteFileTool (file_path, text, append) | LangChain 鏀寔 append |
| **缂栬緫鏂囦欢** | edit_file (path, edits, dryRun) | 鉂?| MCP 鐙湁锛宒iff 棰勮 |
| **澶嶅埗鏂囦欢** | 鉂?| CopyFileTool (source_path, destination_path) | LangChain 鐙湁 |
| **绉诲姩/閲嶅懡鍚?* | move_file (source, destination) | MoveFileTool (source_path, destination_path) | 鍙傛暟鍚嶄笉鍚?|
| **鍒犻櫎鏂囦欢** | 鉂?| DeleteFileTool (file_path) | LangChain 鐙湁 |
| **鍒涘缓鐩綍** | create_directory (path) | 鉂?| MCP 鐙湁 |
| **鍒楀嚭鐩綍** | list_directory (path) | ListDirectoryTool (dir_path) | 鍙傛暟鍚嶄笉鍚?|
| **鍒楀嚭鐩綍(鍚ぇ灏?** | list_directory_with_sizes (path, sortBy) | 鉂?| MCP 鐙湁 |
| **鎼滅储鏂囦欢(鍐呭)** | search_files (path, pattern, excludePatterns) | FileSearchTool (pattern, dir_path) | MCP 鏀寔 excludePatterns |
| **鎼滅储鏂囦欢(鍚嶇О)** | 鉁?search_files | 鉁?FileSearchTool | 涓よ€呴兘鏈夋枃浠跺悕鎼滅储 |
| **鐩綍鏍?* | directory_tree (path, excludePatterns) | 鉂?| MCP 鐙湁 |
| **鏂囦欢淇℃伅** | get_file_info (path) | 鉂?| MCP 鐙湁锛岃繑鍥炲厓鏁版嵁 |
| **鍏佽鐩綍鍒楄〃** | list_allowed_directories | 鉂?| MCP 鐙湁锛屽畨鍏ㄦ帶鍒?|
| **璧勬簮妯℃澘** | 鉂?| 鉂?| 灞炰簬 MCP Resources 鑳藉姏锛屼笉鏄?Tool |
| **璇诲彇璧勬簮** | 鉂?| 鉂?| 灞炰簬 MCP Resources 鑳藉姏锛屼笉鏄?Tool |

---

### 20.6 Claude Code 鍐呯疆宸ュ叿锛?8涓級- 瀹屾暣鍙傛暟

**鏁版嵁鏉ユ簮**: https://vtrivedy.com/posts/claudecode-tools-reference/锛?025骞?0鏈堟洿鏂帮級

**閲嶈璇存槑**: Claude Code 鏈?18 涓唴缃伐鍏凤紝涓?MCP/LangChain 涓嶅悓锛岃繖浜涙槸 Claude Code 鍥哄畾鎻愪緵鐨勶紝涓嶈兘鑷畾涔夈€?
| 搴忓彿 | 宸ュ叿鍚嶇О | 鍔熻兘鎻忚堪 | 鏍稿績鍙傛暟 |
|-----|---------|---------|----------|
| 1 | **Task** | 鍚姩瀛?agent 澶勭悊澶嶆潅浠诲姟 | subagent_type, prompt, description, model, resume |
| 2 | **Bash** | 鎵ц shell 鍛戒护 | command, description, timeout, run_in_background |
| 3 | **Glob** | 鏂囦欢鍚嶆ā寮忓尮閰嶏紙蹇級 | pattern, path |
| 4 | **Grep** | 鏂囦欢鍐呭鎼滅储锛堝熀浜?ripgrep锛?| pattern, path, output_mode, glob, type, -A, -B, -C, -n, -i, multiline, head_limit |
| 5 | **Read** | 璇诲彇鏂囦欢 | file_path, offset, limit |
| 6 | **Edit** | 缂栬緫鏂囦欢 | file_path, old_string, new_string, replace_all |
| 7 | **Write** | 鍐欏叆/瑕嗙洊鏂囦欢 | file_path, content |
| 8 | **NotebookEdit** | 缂栬緫 Jupyter notebook | notebook_path, cell_id, new_source, cell_type, edit_mode |
| 9 | **WebFetch** | 鑾峰彇缃戦〉鍐呭锛堝甫 AI 鍒嗘瀽锛?| url, prompt |
| 10 | **WebSearch** | 缃戠粶鎼滅储锛堜粎 US锛?| query, allowed_domains, blocked_domains |
| 11 | **TodoWrite** | 浠诲姟鍒楄〃绠＄悊 | todos [{content, activeForm, status}] |
| 12 | **ExitPlanMode** | 閫€鍑鸿鍒掓ā寮?| plan |
| 13 | **BashOutput** | 鑾峰彇鍚庡彴鍛戒护杈撳嚭 | bash_id, filter |
| 14 | **KillShell** | 缁堟鍚庡彴鍛戒护 | shell_id |
| 15 | **SlashCommand** | 鎵ц鏂滄潬鍛戒护 | command |
| 16 | **AskUserQuestion** | 鍚戠敤鎴锋彁闂?| questions, answers |
| 17 | **Skill** | 鎵ц skill | skill |
| 18 | **EnterPlanMode** | 杩涘叆璁″垝妯″紡 | (鏃犲弬鏁? |

**Glob 鍙傛暟璇﹁В**:
- `pattern`: Glob 妯″紡锛坄**/*.js`, `src/**/*.ts`, `*.{json,yaml}`锛?- `path`: 鎼滅储鐩綍锛堝彲閫夛紝榛樿褰撳墠鐩綍锛?- 杩斿洖鎸変慨鏀规椂闂存帓搴忕殑鏂囦欢鍒楄〃

**Grep 鍙傛暟璇﹁В**:
- `pattern`: 姝ｅ垯琛ㄨ揪寮忥紙浣跨敤 ripgrep锛?- `path`: 鎼滅储璺緞
- `output_mode`: "content"锛堣锛夈€?files_with_matches"锛堟枃浠讹級銆?count"锛堣鏁帮級
- `glob`: 鏂囦欢绫诲瀷杩囨护锛堝 "*.ts"锛?- `type`: 璇█绫诲瀷锛堝 "js", "py"锛?- `-A/-B/-C`: 鍖归厤鍚?鍓?鍓嶅悗琛屾暟
- `-i`: 涓嶅尯鍒嗗ぇ灏忓啓
- `-n`: 鏄剧ず琛屽彿
- `multiline`: 澶氳鍖归厤
- `head_limit`: 闄愬埗缁撴灉鏁伴噺

**Claude Code 鎼滅储绛栫暐**:
| 鍦烘櫙 | 鎺ㄨ崘宸ュ叿 |
|-----|---------|
| 鎸夋枃浠跺悕鎼滅储 | Glob |
| 鎸夋枃浠跺唴瀹规悳绱?| Grep |
| 鎼滅储鐗瑰畾鏂囦欢鍐嶈鍐呭 | Read + Grep |
| 澶嶆潅澶氳疆鎼滅储 | Task锛坓eneral-purpose agent锛墊

---

### 20.7 鎼滅储宸ュ叿瀵规瘮鎬荤粨

| 鎼滅储绫诲瀷 | Claude Code | MCP Filesystem | LangChain | 鎴戜滑 Omni |
|---------|-------------|----------------|-----------|-----------|
| **鏂囦欢鍚嶆悳绱?* | Glob (pattern, path) | search_files | FileSearchTool | search_files |
| **鏂囦欢鍐呭鎼滅储** | Grep (pattern, path, output_mode) | 鉂?鏃?| 鉂?鏃?| search_file_content |
| **澶囨敞** | 涓よ€呭垎寮€锛屾渶娓呮櫚 | 鍙湁涓€涓?search_files | 鍙湁涓€涓?FileSearchTool | 鍒嗗紑鐨勪袱涓伐鍏?|

**鍏抽敭鍙戠幇**:
- **Claude Code 鏈€瀹屽杽**: 鏄庣‘鍖哄垎 Glob锛堟枃浠跺悕锛夊拰 Grep锛堝唴瀹癸級
- **MCP/LangChain 涓嶈冻**: 鍙湁鏂囦欢鍚嶆悳绱紝娌℃湁鍐呭鎼滅储
- **鎴戜滑 Omni 绯荤粺**: 鏈?search_files 鍜?search_file_content 涓や釜宸ュ叿

---

**缂栧啓浜?*: 灏忔矆
**鏇存柊鏃堕棿**: 2026-04-04 07:50:00
**鏇存柊璇存槑**: 
- 琛ュ厖 Claude Code 18 涓唴缃伐鍏峰畬鏁村弬鏁帮紙20.6锛?- 鏂板鎼滅储宸ュ叿瀵规瘮鎬荤粨锛?0.7锛?- 鏄庣‘鏂囦欢鍚嶆悳绱?vs 鍐呭鎼滅储鐨勫尯鍒?
---

## 浜屽崄涓€銆佸叏閮?Tool 姹囨€伙紙鎸夌被鍨嬪垎绫伙紝浠呴檺缃戜笂瀛︿範锛?
### 21.1 宸ュ叿姹囨€昏鏄?
鏈珷鑺傛暣鍚堢1-20绔犱腑鎻愬埌鐨?*缃戜笂瀛︿範鐨勫伐鍏?*锛屾寜鍔熻兘绫诲瀷鍒嗙被銆傛瘡涓伐鍏峰寘鍚細
- **宸ュ叿鎻忚堪**: 宸ュ叿鐨勫姛鑳借鏄?- **鍙傛暟鍒楄〃**: 鍙傛暟鍚嶇О + 鍙傛暟绫诲瀷 + 鎻忚堪

**鏁版嵁鏉ユ簮**锛堜粎鏉ヨ嚜缃戜笂瀛︿範锛?
- MCP Filesystem Server锛堝畼鏂规枃妗ｏ級
- LangChain FileManagementToolkit锛堝畼鏂?GitHub锛?- Claude Code 鍐呯疆宸ュ叿锛堝弬鑰冩枃妗ｏ級

**涓嶅寘鎷?*: 鎴戜滑 Omni 绯荤粺鐨勫伐鍏?
---

### 21.2 鏂囦欢璇诲彇绫?
#### 1. 璇诲彇鏂囨湰鏂囦欢锛坮ead_text_file锛?**鎻忚堪**: 璇诲彇鏂囨湰鏂囦欢瀹屾暣鍐呭锛屽缁堜互 UTF-8 鏍煎紡澶勭悊鏂囦欢
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 鏂囦欢鐨勫畬鏁磋矾寰?|
| head | number | 鉂?鍚?| 璇诲彇鍓?N 琛岋紙涓嶈兘涓?tail 鍚屾椂浣跨敤锛?|
| tail | number | 鉂?鍚?| 璇诲彇鍚?N 琛?|

#### 2. 璇诲彇濯掍綋鏂囦欢锛坮ead_media_file锛?**鎻忚堪**: 璇诲彇鍥剧墖鎴栭煶棰戞枃浠讹紝杩斿洖 base64 缂栫爜鏁版嵁鍜屽搴旂殑 MIME 绫诲瀷
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 濯掍綋鏂囦欢鐨勫畬鏁磋矾寰?|

#### 3. 鎵归噺璇绘枃浠讹紙read_batch_file锛?**鎻忚堪**: 鍚屾椂璇诲彇澶氫釜鏂囦欢锛屽崟涓枃浠惰鍙栧け璐ヤ笉浼氫腑鏂暣涓搷浣?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_paths | string[] | 鉁?鏄?| 鏂囦欢璺緞鏁扮粍 |

#### 4. 璇诲彇澶氭牸寮忔枃浠讹紙read_file锛?**鎻忚堪**: 浠庢枃浠剁郴缁熻鍙栨枃浠讹紝鏀寔鏂囨湰銆佸浘鐗囥€丳DF銆丣upyter notebook
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 鏂囦欢鐨勭粷瀵硅矾寰?|
| offset | number | 鉂?鍚?| 璧峰琛屽彿锛屼粠1寮€濮?|
| limit | number | 鉂?鍚?| 璇诲彇琛屾暟锛岄粯璁?000琛?|

---

### 21.3 鏂囦欢鍐欏叆绫?
#### 5. 鍐欏叆鎴栬拷鍔犳枃浠讹紙write_append_file锛?**鎻忚堪**: 鍐欏叆鎴栬拷鍔犲埌鏂囦欢
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 鏂囦欢璺緞 |
| text | string | 鉁?鏄?| 鍐欏叆鐨勬枃鏈唴瀹?|
| append | boolean | 鉂?鍚?| 鏄惁杩藉姞妯″紡锛岄粯璁?false |

---

### 21.4 鏂囦欢缂栬緫绫?
#### 7. 缂栬緫鏂囦欢锛坋dit_file锛?**鎻忚堪**: 浣跨敤楂樼骇妯″紡鍖归厤杩涜閫夋嫨鎬х紪杈戯紝鏀寔澶氬悓鏃剁紪杈戙€佺缉杩涗繚鐣欍€乨ryRun 棰勮
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 瑕佺紪杈戠殑鏂囦欢璺緞 |
| edits | array | 鉁?鏄?| 缂栬緫鎿嶄綔鏁扮粍锛屾瘡涓厓绱犲寘鍚?oldText 鍜?newText |
| dryRun | boolean | 鉂?鍚?| 棰勮妯″紡涓嶅疄闄呬慨鏀癸紝榛樿 false |

#### 6. 绮惧噯鏇挎崲鏂囦欢鍐呭锛坧recise_replace_in_file锛?**鎻忚堪**: 鎵ц绮剧‘鐨勫瓧绗︿覆鏇挎崲
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 鏂囦欢缁濆璺緞 |
| old_string | string | 鉁?鏄?| 瑕佹浛鎹㈢殑绮剧‘鏂囨湰 |
| new_string | string | 鉁?鏄?| 鏇挎崲鍚庣殑鏂囨湰 |
| replace_all | boolean | 鉂?鍚?| 鏇挎崲鎵€鏈夊尮閰嶉」锛岄粯璁?false |

#### 8. 澶嶅埗鏂囦欢锛坈opy_file锛?**鎻忚堪**: 澶嶅埗鏂囦欢
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| source_path | string | 鉁?鏄?| 婧愭枃浠惰矾寰?|
| destination_path | string | 鉁?鏄?| 鐩爣鏂囦欢璺緞 |

#### 9. 绉诲姩鎴栭噸鍛藉悕鏂囦欢锛坢ove_file锛?**鎻忚堪**: 绉诲姩鎴栭噸鍛藉悕鏂囦欢
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| source_path | string | 鉁?鏄?| 婧愭枃浠惰矾寰?|
| destination_path | string | 鉁?鏄?| 鐩爣鏂囦欢璺緞 |

#### 10. 閲嶅懡鍚嶆枃浠讹紙rename_file锛?**鎻忚堪**: 閲嶅懡鍚嶆枃浠舵垨鐩綍锛屼笉鏀瑰彉鎵€鍦ㄧ洰褰?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 褰撳墠鏂囦欢璺緞 |
| new_name | string | 鉁?鏄?| 鏂版枃浠跺悕 |

#### 11. 鍒犻櫎鏂囦欢锛坉elete_file锛?**鎻忚堪**: 鍒犻櫎鏂囦欢
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 瑕佸垹闄ょ殑鏂囦欢璺緞 |

---

### 21.5 鏂囦欢鎼滅储绫伙紙鏂囦欢鍚嶏級

#### 12. 鎼滅储鏂囦欢鎸夋ā寮忥紙search_files锛?**鎻忚堪**: 閫掑綊鎼滅储鍖归厤鎴栨帓闄ゆā寮忕殑鏂囦欢/鐩綍锛岃繑鍥炲畬鏁磋矾寰?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| search_dir | string | 鉁?鏄?| 鎼滅储璧峰鐩綍 |
| pattern | string | 鉁?鏄?| 鎼滅储妯″紡锛坓lob 椋庢牸锛?|
| excludePatterns | string[] | 鉂?鍚?| 鎺掗櫎妯″紡 |

#### 13. 鏂囦欢鍚嶆ā寮忓尮閰嶏紙glob_files锛?**鎻忚堪**: 蹇€熺殑鏂囦欢鍚嶆ā寮忓尮閰嶏紝鎸変慨鏀规椂闂存帓搴忚繑鍥炵粨鏋?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| pattern | string | 鉁?鏄?| Glob 妯″紡锛堝 **/*.js, src/**/*.ts锛?|
| search_dir | string | 鉂?鍚?| 鎼滅储鐩綍锛岄粯璁ゅ綋鍓嶅伐浣滅洰褰?|

---

### 21.6 鏂囦欢鎼滅储绫伙紙鍐呭锛?
#### 14. 鎼滅储鏂囦欢鍐呭锛坓rep_file_content锛?**鎻忚堪**: 鍩轰簬 ripgrep 鐨勫己澶у唴瀹规悳绱紝鏀寔姝ｅ垯琛ㄨ揪寮忓拰澶氶€夐」
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| pattern | string | 鉁?鏄?| 姝ｅ垯琛ㄨ揪寮忔悳绱㈡ā寮?|
| search_dir | string | 鉂?鍚?| 鎼滅储璺緞锛岄粯璁ゅ綋鍓嶇洰褰?|
| output_mode | string | 鉂?鍚?| 杈撳嚭妯″紡锛歝ontent/files_with_matches/count |
| glob | string | 鉂?鍚?| 鏂囦欢绫诲瀷杩囨护锛堝 "*.ts"锛?|
| type | string | 鉂?鍚?| 璇█绫诲瀷锛堝 js, py, rust锛?|
| -A | number | 鉂?鍚?| 鍖归厤鍚庢樉绀鸿鏁?|
| -B | number | 鉂?鍚?| 鍖归厤鍓嶆樉绀鸿鏁?|
| -C | number | 鉂?鍚?| 鍖归厤鍓嶅悗鏄剧ず琛屾暟 |
| -i | boolean | 鉂?鍚?| 涓嶅尯鍒嗗ぇ灏忓啓 |
| -n | boolean | 鉂?鍚?| 鏄剧ず琛屽彿 |
| multiline | boolean | 鉂?鍚?| 鍚敤澶氳鍖归厤锛? 鍖归厤鎹㈣绗︼級 |
| head_limit | number | 鉂?鍚?| 闄愬埗杈撳嚭缁撴灉鏁伴噺 |

---

### 21.7 鐩綍鎿嶄綔绫?
#### 15. 鍒涘缓鐩綍锛坈reate_directory锛?**鎻忚堪**: 鍒涘缓鏂扮洰褰曪紝濡傞渶瑕佷細鍒涘缓鐖剁洰褰曪紝鐩綍宸插瓨鍦ㄥ垯闈欓粯鎴愬姛
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| dir_path | string | 鉁?鏄?| 鐩綍璺緞 |

#### 16. 鍒楀嚭鐩綍鍚ぇ灏忥紙list_directory_with_sizes锛?**鎻忚堪**: 鍒楀嚭鐩綍鍐呭锛屽寘鍚枃浠跺ぇ灏忥紝鎸?name 鎴?size 鎺掑簭锛岃繑鍥炵粺璁′俊鎭?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| dir_path | string | 鉁?鏄?| 鐩綍璺緞 |
| sortBy | string | 鉂?鍚?| 鎺掑簭鏂瑰紡锛歯ame 鎴?size锛岄粯璁?name |

#### 17. 鑾峰彇鐩綍鏍戠粨鏋勶紙get_directory_tree锛?**鎻忚堪**: 鑾峰彇鐩綍鐨勯€掑綊 JSON 鏍戠粨鏋勶紝姣忎釜鏉＄洰鍖呭惈 name銆乼ype锛坒ile/directory锛夈€乧hildren
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| dir_path | string | 鉁?鏄?| 璧峰鐩綍 |
| excludePatterns | string[] | 鉂?鍚?| 鎺掗櫎妯″紡锛坓lob 鏍煎紡锛?|


---

### 21.8 鍏冩暟鎹?淇℃伅绫?
#### 18. 鑾峰彇鏂囦欢淇℃伅锛坓et_file_info锛?**鎻忚堪**: 鑾峰彇鏂囦欢/鐩綍鐨勮缁嗗厓鏁版嵁锛屽寘鎷ぇ灏忋€佸垱寤?淇敼/璁块棶鏃堕棿銆佺被鍨嬨€佹潈闄?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| file_path | string | 鉁?鏄?| 鏂囦欢鎴栫洰褰曡矾寰?|

#### 19. 鍒楀嚭鍏佽璁块棶鐨勭洰褰曪紙list_allowed_directories锛?**鎻忚堪**: 鍒楀嚭鏈嶅姟鍣ㄥ厑璁歌闂殑鎵€鏈夌洰褰?**鍙傛暟**: 鏃犲弬鏁?
---

### 21.9 绯荤粺鎿嶄綔绫?
#### 20. 鎵ц Shell 鍛戒护锛坋xecute_shell_command锛?**鎻忚堪**: 鍦ㄦ寚瀹?shell 鐜涓墽琛屽懡浠ゃ€俉indows 鍘熺敓榛樿 PowerShell锛屽彲閫?CMD锛沚ash 闇€棰濆瀹夎锛堟湭鏉ユ墿灞曪級銆?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| command | string | 鉁?鏄?| 瑕佹墽琛岀殑鍛戒护 |
| shell_type | string | 鉂?鍚?| 鎵ц鐜锛歱owershell锛堥粯璁わ級/ cmd / bash锛堟湭鏉ユ墿灞曪級 |
| timeout | number | 鉂?鍚?| 瓒呮椂姣鏁帮紝榛樿120000锛屾渶澶?00000 |
| run_in_background | boolean | 鉂?鍚?| 鍚庡彴杩愯鍛戒护 |

#### 21. 鑾峰彇 Shell 杈撳嚭锛坓et_shell_output锛?**鎻忚堪**: 鑾峰彇鍚庡彴杩愯鐨?bash 鍛戒护杈撳嚭
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| shell_id | string | 鉁?鏄?| 鍚庡彴 shell 鐨?ID |
| filter | string | 鉂?鍚?| 杩囨护杈撳嚭鐨勬鍒欒〃杈惧紡 |

#### 22. 缁堟 Shell 浼氳瘽锛坱erminate_shell锛?**鎻忚堪**: 缁堟杩愯涓殑鍚庡彴 bash shell
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| shell_id | string | 鉁?鏄?| 瑕佺粓姝㈢殑 shell ID |

---

### 21.10 缃戠粶/閫氫俊绫?
#### 22. 鑾峰彇缃戦〉鍐呭锛坒etch_webpage锛?**鎻忚堪**: 鑾峰彇鍜屽鐞嗙綉椤靛唴瀹癸紝甯?AI 鍒嗘瀽鍔熻兘
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| url | string | 鉁?鏄?| 瀹屽叏鏈夋晥鐨?URL |
| prompt | string | 鉁?鏄?| 瑕佷粠椤甸潰鎻愬彇鐨勪俊鎭?|

#### 23. 缃戠粶鎼滅储锛坰earch_web锛?**鎻忚堪**: 鎼滅储缃戠粶鑾峰彇鏈€鏂颁俊鎭紙浠呯編鍥藉彲鐢級
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| query | string | 鉁?鏄?| 鎼滅储鏌ヨ瀛楃涓诧紙鑷冲皯2瀛楃锛?|
| allowed_domains | string[] | 鉂?鍚?| 鍖呭惈鐨勫煙鍚嶆暟缁?|
| blocked_domains | string[] | 鉂?鍚?| 鎺掗櫎鐨勫煙鍚嶆暟缁?|

---

### 21.11 浠诲姟绠＄悊绫汇€愭娆′笉鍔犺繖閲?鐨則ool銆?
#### 24. 鍚姩瀛?Agent锛坙aunch_subagent锛?**鎻忚堪**: 鍚姩涓撻棬鐨勫瓙 agent 澶勭悊澶嶆潅鐨勫姝ラ浠诲姟
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| subagent_type | string | 鉁?鏄?| 浣跨敤鐨?agent 绫诲瀷锛坓eneral-purpose/statusline-setup/output-style-setup锛?|
| prompt | string | 鉁?鏄?| 浠诲姟鐨勮缁嗘弿杩?|
| description | string | 鉁?鏄?| 浠诲姟鐨勭畝鐭?-5瀛楁弿杩?|
| model | string | 鉂?鍚?| 浣跨敤鐨勬ā鍨?|
| resume | boolean | 鉂?鍚?| 鎭㈠涔嬪墠鐨勪换鍔?|

#### 25. 绠＄悊浠诲姟鍒楄〃锛坢anage_todos锛?**鎻忚堪**: 鍒涘缓鍜岀鐞嗙粨鏋勫寲浠诲姟鍒楄〃璺熻釜杩涘害
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| todos | array | 鉁?鏄?| todo 瀵硅薄鏁扮粍锛屾瘡涓寘鍚?content銆乤ctiveForm銆乻tatus |

#### 26. 閫€鍑鸿鍒掓ā寮忥紙exit_plan_mode锛?**鎻忚堪**: 灞曠ず瀹炵幇璁″垝鍚庨€€鍑鸿鍒掓ā寮?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| plan | string | 鉁?鏄?| 瀹炵幇璁″垝锛堟敮鎸?markdown锛?|

#### 27. 杩涘叆璁″垝妯″紡锛坋nter_plan_mode锛?**鎻忚堪**: 杩涘叆璁″垝妯″紡
**鍙傛暟**: 鏃犲弬鏁?
#### 28. 缂栬緫 Notebook 鍗曞厓鏍硷紙edit_notebook_cell锛?**鎻忚堪**: 缂栬緫 Jupyter notebook 鍗曞厓鏍?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| notebook_path | string | 鉁?鏄?| notebook 缁濆璺緞 |
| new_source | string | 鉁?鏄?| 鏂扮殑鍗曞厓鏍煎唴瀹?|
| cell_id | string | 鉂?鍚?| 瑕佺紪杈戠殑鍗曞厓鏍?ID |
| cell_type | string | 鉂?鍚?| 鍗曞厓鏍肩被鍨嬶細code 鎴?markdown |
| edit_mode | string | 鉂?鍚?| 缂栬緫妯″紡锛歳eplace/insert/delete |

#### 29. 鎵ц鏂滄潬鍛戒护锛坋xecute_slash_command锛?**鎻忚堪**: 鎵ц鏂滄潬鍛戒护
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| command | string | 鉁?鏄?| 鏂滄潬鍛戒护鍙婂弬鏁?|

#### 30. 鍚戠敤鎴锋彁闂紙ask_user_question锛?**鎻忚堪**: 鍚戠敤鎴锋彁闂幏鍙栦氦浜?**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| questions | array | 鉁?鏄?| 闂鏁扮粍 |
| answers | array | 鉂?鍚?| 绛旀鏁扮粍 |

#### 31. 鎵ц Skill锛坋xecute_skill锛?**鎻忚堪**: 鎵ц skill
**鍙傛暟**:
| 鍙傛暟鍚?| 绫诲瀷 | 蹇呭～ | 鎻忚堪 |
|--------|------|------|------|
| skill | string | 鉁?鏄?| skill 鍚嶇О |

---

### 21.12 宸ュ叿鎬绘暟姹囨€?
| 绫诲埆 | MCP | LangChain | Claude Code | 鎬昏 |
|------|-----|-----------|------------|------|
| 鏂囦欢璇诲彇 | 3 | 0 | 1 | 4 |
| 鏂囦欢鍐欏叆 | 0 | 1 | 0 | 1 |
| 鏂囦欢缂栬緫 | 1 | 3 | 1 | 5 |
| 鏂囦欢鎼滅储(鏂囦欢鍚? | 1 | 0 | 1 | 2 |
| 鏂囦欢鎼滅储(鍐呭) | 0 | 0 | 1 | 1 |
| 鐩綍鎿嶄綔 | 3 | 0 | 0 | 3 |
| 鍏冩暟鎹?| 2 | 0 | 0 | 2 |
| 绯荤粺鎿嶄綔 | 0 | 0 | 3 | 3 |
| 缃戠粶/閫氫俊 | 0 | 0 | 2 | 2 |
| 浠诲姟绠＄悊 | 0 | 0 | 7 | 7 |
| **鎬昏** | **10** | **4** | **16** | **30** |

**璇存槑**:
- MCP: 10 涓伐鍏?- LangChain: 4 涓伐鍏?- Claude Code: 16 涓伐鍏?- 鎬昏: 30 涓伐鍏?
---

**缂栧啓浜?*: 灏忔矆
**鏇存柊鏃堕棿**: 2026-04-04 10:31:01
**鏇存柊璇存槑**: 
- 缁熶竴鎵€鏈?tool 鍙傛暟鍛藉悕锛歱ath鈫抐ile_path/dir_path/search_dir锛宲aths鈫抐ile_paths锛宐ash_id鈫抯hell_id
- 娑堥櫎鍙傛暟鍚嶆涔夛紝LLM 璋冪敤鏃朵笉浼氭贩娣?- 鏂板 rename_file 宸ュ叿锛屼粠 29 涓伐鍏峰鍔犱负 30 涓伐鍏?
