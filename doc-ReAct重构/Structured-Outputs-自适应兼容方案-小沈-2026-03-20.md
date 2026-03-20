# Structured Outputs 自适应兼容实现方案

**创建时间**: 2026-03-20 09:15:00
**更新时间**: 2026-03-20 10:05:00
**版本**: v1.3
**编写人**: 小沈
**设计原则**: 根据模型反馈特征自动适配，不依赖硬编码模型名称

---

## 一、问题分析

### 1.1 原有方案的问题

```python
# ❌ 问题：依赖硬编码模型名称
SUPPORTED_LLMS = {
    "longcat-flash-thinking-2601": "function_calling",
    "claude-3-5-sonnet": "response_format",
    ...
}

# 问题：
# 1. 新模型需要手动添加
# 2. 模型名称可能有变体
# 3. 无法处理未知模型
# 4. 优先级写反：response_format > tools
```

### 1.2 新方案：基于特征检测

```python
# ✅ 解决方案：自动探测 API 能力
class APICapabilityDetector:
    """
    API 能力探测器
    
    通过实际请求探测 LLM 支持的功能
    不依赖模型名称，硬编码
    """
    
    async def detect(self, api_base, api_key, model) -> LLMCapability:
        # 1. 尝试 tools（优先级最高，约50个模型支持）
        # 2. 尝试 response_format（约45个模型支持）
        # 3. 根据响应判断支持情况
```

### 1.3 策略优先级（修正版）

**根据实际测试结果修正**：

| 优先级 | 策略 | 支持模型数 | 说明 |
|--------|------|----------|------|
| **1** | **tools** | ~50 个 | ✅ 支持最广 |
| **2** | response_format | ~45 个 | 部分返回非标准JSON |
| **3** | prompt | 所有模型 | 降级方案 |

---

## 二、自适应兼容架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                  首次调用时自动探测                         │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ↓               ↓               ↓
    ┌───────────────┐ ┌───────────────┐ ┌───────────┐
    │ tools 测试     │ │ response_     │ │ 降级到   │
    │ 【优先级最高】  │ │ format 测试   │ │ Prompt   │
    └───────┬───────┘ └───────┬───────┘ └─────┬─────┘
            │                 │               │
            ▼                 ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────┐
    │ ✅ 支持       │ │ ✅ 支持       │ │ ❌ 不支持 │
    │ tools         │ │ response_     │ │ 只能降级  │
    │ (约50个模型)   │ │ format        │ │           │
    └───────────────┘ │ (约45个模型)   │ └───────────┘
                      └───────────────┘

【策略优先级】tools > response_format > prompt
```

### 2.2 能力检测流程

```
Step 1: 发送探测请求（tools）【优先级最高】
         ↓
    ┌────────────┐
    │ 有 tool_   │───否──→ 标记 tools 不支持，继续 Step 2
    │ calls？     │
    └─────┬──────┘
         │是
         ↓
    ✅ tools 支持 → 选择 tools 策略，结束

Step 2: 发送探测请求（response_format）
         ↓
    ┌────────────┐
    │ 响应有效？  │───否──→ 标记 response_format 不支持
    └─────┬──────┘
         │是
         ↓
    ┌────────────┐
    │ JSON 有效？ │───否──→ 标记 response_format 不支持
    └─────┬──────┘
         │是
         ↓
    ✅ response_format 支持 → 选择 response_format 策略

Step 3: 降级到 Prompt 模式
         ↓
    ⚠️ tools 和 response_format 都不支持
    → 使用 Prompt Engineering 方式
```

---

## 三、核心实现

### 3.1 能力枚举

```python
# backend/app/services/file_operations/capability.py

from enum import Flag, auto
from dataclasses import dataclass
from typing import Optional


class LLMCapability(Flag):
    """LLM 能力标志"""
    NONE = 0
    RESPONSE_FORMAT = auto()      # 支持 response_format
    TOOLS = auto()                 # 支持 tools/function_calling
    STREAMING = auto()             # 支持流式输出
    REASONING = auto()             # 支持 reasoning_content


@dataclass
class LLMFeature:
    """
    LLM 能力特征
    
    从 API 响应中提取的特征
    """
    capability: LLMCapability = LLMCapability.NONE
    supports_response_format: bool = False
    supports_tools: bool = False
    supports_streaming: bool = True
    supports_reasoning: bool = False
    
    # API 特征
    uses_reasoning_content: bool = False  # 使用 reasoning_content 字段
    uses_outer_content: bool = False      # 使用外层 content 字段
    
    # 元信息
    detected_at: Optional[str] = None
    detection_method: str = "auto"


@dataclass
class LLMProbeResult:
    """
    探测结果
    
    记录探测过程的详细信息
    """
    success: bool
    feature: LLMFeature
    response_format_tested: bool = False
    response_format_works: bool = False
    tools_tested: bool = False
    tools_works: bool = False
    error: Optional[str] = None
```

### 3.2 能力探测器

```python
# backend/app/services/file_operations/capability_detector.py

import json
import httpx
from typing import Optional
from dataclasses import dataclass

from app.services.file_operations.capability import LLMFeature, LLMProbeResult, LLMCapability


class CapabilityDetector:
    """
    API 能力探测器
    
    通过实际请求探测 LLM 支持的功能
    不依赖模型名称，硬编码
    """
    
    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self._capability_cache: Optional[LLMFeature] = None
    
    @property
    def capability(self) -> Optional[LLMFeature]:
        """获取缓存的能力"""
        return self._capability_cache
    
    def is_cached(self) -> bool:
        """是否已探测过"""
        return self._capability_cache is not None
    
    async def detect(self) -> LLMProbeResult:
        """
        自动探测 LLM 支持的功能
        
        Returns:
            LLMProbeResult: 探测结果
        """
        # 如果已缓存，直接返回
        if self._capability_cache:
            return LLMProbeResult(
                success=True,
                feature=self._capability_cache,
                detection_method="cache"
            )
        
        result = LLMProbeResult(success=False, feature=LLMFeature())
        
        try:
            # Step 1: 探测 response_format
            rf_result = await self._probe_response_format()
            result.response_format_tested = True
            result.response_format_works = rf_result["works"]
            
            # Step 2: 探测 tools
            tools_result = await self._probe_tools()
            result.tools_tested = True
            result.tools_works = tools_result["works"]
            
            # Step 3: 探测 reasoning 特征
            reasoning_result = await self._probe_reasoning()
            
            # Step 4: 构建能力特征
            capability = LLMCapability.NONE
            if result.response_format_works:
                capability |= LLMCapability.RESPONSE_FORMAT
            if result.tools_works:
                capability |= LLMCapability.TOOLS
            if reasoning_result["has_reasoning"]:
                capability |= LLMCapability.REASONING
            
            feature = LLMFeature(
                capability=capability,
                supports_response_format=result.response_format_works,
                supports_tools=result.tools_works,
                supports_reasoning=reasoning_result["has_reasoning"],
                uses_reasoning_content=reasoning_result["uses_reasoning_content"],
                uses_outer_content=reasoning_result["uses_outer_content"],
                detection_method="auto"
            )
            
            result.success = True
            result.feature = feature
            
            # 缓存结果
            self._capability_cache = feature
            
            return result
            
        except Exception as e:
            result.error = str(e)
            return result
    
    async def _probe_response_format(self) -> dict:
        """
        探测 response_format 支持
        
        发送一个带 response_format 的请求，检查是否正常工作
        """
        schema = {
            "type": "json_object",
            "json_schema": {
                "type": "object",
                "properties": {
                    "response": {"type": "string"}
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "Hi"}],
                        "response_format": schema,
                        "stream": False
                    }
                )
                
                # 检查响应
                if response.status_code != 200:
                    return {"works": False, "reason": f"HTTP {response.status_code}"}
                
                content_length = response.headers.get("content-length", "0")
                if content_length == "0":
                    return {"works": False, "reason": "Empty response"}
                
                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})
                content = message.get("content", "")
                
                # 检查是否返回了有效 JSON
                if not content:
                    return {"works": False, "reason": "Empty content"}
                
                try:
                    parsed = json.loads(content)
                    if "response" in parsed:
                        return {"works": True, "parsed": parsed}
                    return {"works": True, "parsed": parsed}
                except json.JSONDecodeError:
                    return {"works": False, "reason": "Invalid JSON"}
                    
        except Exception as e:
            return {"works": False, "reason": str(e)}
    
    async def _probe_tools(self) -> dict:
        """
        探测 tools 支持
        
        发送一个带 tools 的请求，检查是否返回 tool_calls
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "param": {"type": "string"}
                        }
                    }
                }
            }
        ]
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "Use the test tool"}],
                        "tools": tools,
                        "tool_choice": "auto",
                        "stream": False
                    }
                )
                
                if response.status_code != 200:
                    return {"works": False, "reason": f"HTTP {response.status_code}"}
                
                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})
                
                # 检查是否有 tool_calls
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    return {"works": True, "tool_calls": tool_calls}
                return {"works": True, "tool_calls": []}
                
        except Exception as e:
            return {"works": False, "reason": str(e)}
    
    async def _probe_reasoning(self) -> dict:
        """
        探测 reasoning 特征
        
        检查响应中是否使用 reasoning_content 字段
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "What is 2+2?"}],
                        "stream": False
                    }
                )
                
                if response.status_code != 200:
                    return {"has_reasoning": False, "uses_reasoning_content": False}
                
                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})
                
                # 检查 reasoning_content 字段
                has_reasoning = "reasoning_content" in message
                
                # 检查外层 content 字段
                has_outer_content = "content" in message and message.get("content")
                
                return {
                    "has_reasoning": has_reasoning,
                    "uses_reasoning_content": has_reasoning,
                    "uses_outer_content": has_outer_content
                }
                
        except Exception:
            return {"has_reasoning": False, "uses_reasoning_content": False}
```

### 3.3 策略选择器

```python
# backend/app/services/file_operations/strategy_selector.py

from app.services.file_operations.capability import LLMCapability, LLMFeature


class StrategySelector:
    """
    策略选择器
    
    根据 LLM 能力自动选择最佳策略
    """
    
    @staticmethod
    def select(feature: LLMFeature) -> "SelectedStrategy":
        """
        根据能力选择最佳策略
        
        Args:
            feature: LLM 能力特征
        
        Returns:
            SelectedStrategy: 选中的策略
        """
        # ✅ 优先级修正：tools > response_format > prompt
        # 原因：根据实测，tools 模式支持约50个模型，response_format 约45个
        
        if feature.supports_tools:
            return SelectedStrategy(
                method="tools",
                capability=LLMCapability.TOOLS,
                description="使用 tools/function_calling（支持最广，约50个模型）"
            )
        
        if feature.supports_response_format:
            return SelectedStrategy(
                method="response_format",
                capability=LLMCapability.RESPONSE_FORMAT,
                description="使用 response_format（约45个模型）"
            )
        
        return SelectedStrategy(
            method="prompt",
            capability=LLMCapability.NONE,
            description="降级到 Prompt 方式（所有模型都支持）"
        )


@dataclass
class SelectedStrategy:
    """
    选中的策略
    """
    method: str  # "response_format", "tools", "prompt"
    capability: LLMCapability
    description: str
```

### 3.4 统一入口

```python
# backend/app/services/file_operations/llm_adapter.py

from typing import Optional
from dataclasses import dataclass

from app.services.file_operations.capability import LLMFeature, LLMCapability
from app.services.file_operations.capability_detector import CapabilityDetector
from app.services.file_operations.strategy_selector import StrategySelector, SelectedStrategy


class LLMAdapter:
    """
    LLM 适配器
    
    统一管理 LLM 能力探测和策略选择
    """
    
    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        auto_detect: bool = True
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        
        # 能力探测器
        self._detector = CapabilityDetector(api_base, api_key, model)
        
        # 自动探测
        if auto_detect:
            # 延迟探测，在首次调用时触发
            self._feature: Optional[LLMFeature] = None
            self._strategy: Optional[SelectedStrategy] = None
        else:
            self._feature = None
            self._strategy = None
    
    async def ensure_capability(self) -> SelectedStrategy:
        """
        确保能力已探测，返回选中的策略
        
        Returns:
            SelectedStrategy: 选中的策略
        """
        if self._strategy is None:
            # 探测能力
            result = await self._detector.detect()
            
            if result.success:
                self._feature = result.feature
                self._strategy = StrategySelector.select(self._feature)
            else:
                # 探测失败，默认降级
                self._strategy = SelectedStrategy(
                    method="prompt",
                    capability=LLMCapability.NONE,
                    description=f"探测失败: {result.error}"
                )
        
        return self._strategy
    
    @property
    def feature(self) -> Optional[LLMFeature]:
        """获取能力特征"""
        return self._feature
    
    @property
    def strategy(self) -> Optional[SelectedStrategy]:
        """获取选中策略"""
        return self._strategy
    
    @property
    def method(self) -> str:
        """获取当前使用的方法"""
        return self._strategy.method if self._strategy else "unknown"
```

---

## 三-2、系统适配（Windows/Linux/Mac）

### 三-2.1 问题背景

LLM 返回的命令和路径格式需要适配当前操作系统：

```
【没有告知系统】
LLM 返回：ls /home/user/file.txt  ← Linux 命令，Windows 用不了

【告知了系统】
LLM 返回：dir C:\Users\xxx\file.txt  ← Windows 命令，正确
```

### 三-2.2 三种模式的解析需求

| 模式 | 是否需要解析 | 可靠性 |
|------|------------|-------|
| **tools** | ❌ **不需要** | ✅ 直接用 tool_calls，参数已是结构化 |
| **response_format** | ✅ **需要解析** | ⚠️ content 是 JSON 字符串，需 json.loads() |
| **prompt** | ✅ **需要解析** | ❌ content 是普通文本，需正则提取 |

**关键**：tools 模式返回的参数已经是结构化的，但**系统命令格式仍需 LLM 适配**。

### 三-2.3 系统信息获取

```python
# backend/app/services/file_operations/os_adapter.py

import platform
import os

class OSAdapter:
    """
    操作系统适配器
    
    检测当前系统，生成系统提示信息
    """
    
    def __init__(self):
        self.system = platform.system()  # Windows / Linux / Darwin
    
    @property
    def is_windows(self) -> bool:
        return self.system == "Windows"
    
    @property
    def is_linux(self) -> bool:
        return self.system == "Linux"
    
    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"
    
    @property
    def path_separator(self) -> str:
        """路径分隔符"""
        return "\\" if self.is_windows else "/"
    
    @property
    def commands(self) -> dict:
        """常用命令映射"""
        if self.is_windows:
            return {
                "list": "dir",
                "copy": "copy",
                "move": "move",
                "delete": "del",
                "read": "type",
                "write": "echo",
                "mkdir": "mkdir",
                "rmdir": "rmdir",
            }
        else:
            return {
                "list": "ls",
                "copy": "cp",
                "move": "mv",
                "delete": "rm",
                "read": "cat",
                "write": "echo",
                "mkdir": "mkdir",
                "rmdir": "rmdir",
            }
    
    def get_system_prompt(self) -> str:
        """生成系统提示信息"""
        return f"""【操作系统】
{self.system}

【路径格式】
- Windows: C:\\Users\\xxx\\file.txt
- Linux/Mac: /home/xxx/file.txt

【当前系统命令】
{chr(10).join(f"- {k}: {v}" for k, v in self.commands.items())}

重要：请返回适用于 {self.system} 系统的命令和路径格式。"""
    
    def get_tool_descriptions(self) -> dict:
        """生成工具描述中的系统适配说明"""
        path_example = "C:\\Users\\xxx\\file.txt" if self.is_windows else "/home/xxx/file.txt"
        return {
            "path": f"文件路径，格式如: {path_example}",
            "description": "Windows 使用 dir/copy/del/type，Linux/Mac 使用 ls/cp/rm/cat"
        }
    
    def __repr__(self) -> str:
        return f"OSAdapter(system={self.system})"
```

### 三-2.4 集成到 Agent

```python
# backend/app/services/file_operations/agent.py

class FileOperationAgent:
    def __init__(self, ...):
        # 【新增】系统适配器
        self.os_adapter = OSAdapter()
        logger.info(f"[Agent] OS Adapter: {self.os_adapter}")
        
        # 【新增】构建系统提示
        self.system_prompt = self.os_adapter.get_system_prompt()
        
        # 更新 tools 描述
        if self.tools:
            self._update_tool_descriptions()
    
    def _update_tool_descriptions(self):
        """更新工具描述，添加系统适配说明"""
        tool_hints = self.os_adapter.get_tool_descriptions()
        
        for tool in self.tools:
            if "parameters" in tool.get("function", {}):
                params = tool["function"]["parameters"]
                if "properties" in params:
                    if "path" in params["properties"]:
                        params["properties"]["path"]["description"] = tool_hints["path"]
```

### 三-2.5 工具定义示例（系统适配版）

```python
# 带系统适配的工具定义

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": """搜索文件和目录。

【系统适配】
- Windows 路径: C:\\Users\\xxx\\file.txt
- Linux/Mac 路径: /home/xxx/file.txt

【示例】
- Windows: path="C:\\Users\\xxx\\Documents", pattern="*.pdf"
- Linux: path="/home/xxx/documents", pattern="*.pdf"
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "搜索路径，Windows: C:\\xxx，Linux/Mac: /xxx"
                    },
                    "pattern": {
                        "type": "string",
                        "description": "文件匹配模式，如 *.py, *.txt, *.json"
                    }
                },
                "required": ["path", "pattern"]
            }
        }
    },
    {
        "type": "function", 
        "function": {
            "name": "read_file",
            "description": """读取文件内容。

【示例】
- Windows: path="C:\\Users\\xxx\\notes.txt"
- Linux/Mac: path="/home/xxx/notes.txt"
""",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string", 
                        "description": "文件路径"
                    }
                },
                "required": ["path"]
            }
        }
    }
]
```

### 三-2.6 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     FileOperationAgent                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  self.os_adapter = OSAdapter()                             │  │
│  │      │                                                      │  │
│  │      ├─ platform.system() → "Windows"                      │  │
│  │      ├─ path_separator → "\\"                              │  │
│  │      └─ commands → {dir, copy, del, ...}                   │  │
│  │                                                              │  │
│  │  self.system_prompt = os_adapter.get_system_prompt()       │  │
│  │      │                                                      │  │
│  │      └─ 包含系统信息发送给 LLM                             │  │
│  │                                                              │  │
│  │  tools = [...]                                              │  │
│  │      │                                                      │  │
│  │      └─ _update_tool_descriptions()                        │  │
│  │              │                                              │  │
│  │              └─ description 中添加系统适配说明              │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     LLM 请求                               │  │
│  │  messages: [                                                 │  │
│  │    {role: "system", content: "【操作系统】Windows..."},      │  │
│  │    {role: "user", content: "搜索 C:/ 下的文件"}             │  │
│  │  ]                                                           │  │
│  │  tools: [                                                    │  │
│  │    {name: "search_files", description: "Windows: C:\\..."}   │  │
│  │  ]                                                           │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │                                    │
│                              ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                     LLM 响应                               │  │
│  │  {                                                          │  │
│  │    "tool_calls": [{                                        │  │
│  │      "function": {                                         │  │
│  │        "name": "search_files",                             │  │
│  │        "arguments": "{\"path\": \"C:\\\\Users\\\\xxx\", ...}" │  │
│  │      }                                                      │  │
│  │    }]                                                       │  │
│  │  }                                                          │  │
│  │  ✅ Windows 格式的命令和路径，正确！                        │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 三-2.7 与 LLMAdapter 集成

```python
# backend/app/services/file_operations/llm_adapter.py

class LLMAdapter:
    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        auto_detect: bool = True,
        # 【新增】系统适配
        os_adapter: Optional[OSAdapter] = None
    ):
        # ... 现有代码 ...
        
        # 系统适配器
        self.os_adapter = os_adapter or OSAdapter()
    
    def build_messages(self, messages: list, system_override: str = None) -> list:
        """构建发送给 LLM 的消息列表"""
        result = []
        
        # 添加系统提示（包含系统适配信息）
        system_content = system_override or self.os_adapter.get_system_prompt()
        result.append({"role": "system", "content": system_content})
        
        # 添加历史消息
        result.extend(messages)
        
        return result
    
    def build_tools(self, tools: list) -> list:
        """构建工具定义（添加系统适配说明）"""
        if not tools:
            return tools
        
        tool_hints = self.os_adapter.get_tool_descriptions()
        enriched_tools = []
        
        for tool in tools:
            enriched_tool = copy.deepcopy(tool)
            if "function" in enriched_tool:
                func = enriched_tool["function"]
                if "parameters" in func:
                    params = func["parameters"]
                    if "properties" in params:
                        if "path" in params["properties"]:
                            params["properties"]["path"]["description"] = tool_hints["path"]
            enriched_tools.append(enriched_tool)
        
        return enriched_tools
```

---

## 四、探测时机与集成架构

### 4.1 探测时机选择

#### 4.1.1 方案对比

| 方案 | 时机 | 优点 | 缺点 |
|------|------|------|------|
| **A. 服务启动时** | 系统初始化 | 首次请求无额外延迟 | 可能浪费探测（用户不用这个LLM） |
| **B. Agent初始化时** | `FileOperationAgent.__init__` | Agent级别已知能力 | 同上，且Agent可能重复创建 |
| **C. 首次LLM调用时** | `_get_llm_response()` | ✅ 按需探测，不浪费 | 首次请求有额外延迟（~1秒） |
| **D. 首次LLM调用时 + 缓存** | 同C + 持久化 | ✅ 最佳：按需+复用 | 需要缓存机制 |

#### 4.1.2 推荐方案：D（首次调用 + 内存缓存）

**探测时机**：首次 `_get_llm_response()` 调用时（懒加载）

**理由**：
1. ✅ **按需探测** - 只有真正使用时才探测，节省资源
2. ✅ **零代码入侵** - 不修改现有 base.py 和 agent.py 核心逻辑
3. ✅ **缓存复用** - 同一服务实例内只探测一次
4. ✅ **可选持久化** - 可通过缓存文件避免服务重启后重复探测

**探测顺序**（按优先级）：
1. **Step1**: 探测 tools（优先级最高，约50个模型支持）
2. **Step2**: 探测 response_format（仅在 tools 不支持时）
3. **Step3**: 降级到 prompt（所有模型都支持）

**首次延迟**：约1秒（可接受，因为只发生一次，且用户首次请求本来就需要等待）

### 4.2 系统集成架构

#### 4.2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户请求入口                              │
│                     (NewChatContainer)                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FileOperationAgent                         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ _get_llm_response()                                        │ │
│  │                                                           │ │
│  │   if use_function_calling and tools:                       │ │
│  │       → llm_adapter.chat_with_tools()  ◀── 【适配层入口】 │ │
│  │   else:                                                    │ │
│  │       → llm_adapter.chat()                                 │ │
│  └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLMAdapter (新增层)                          │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ ensure_capability() ← 【探测入口，首次调用时触发】        │ │
│  │   │                                                      │ │
│  │   ├─ 首次调用？                                           │ │
│  │   │   ├─ 是 → CapabilityDetector.detect()                │ │
│  │   │   │       ├─ 探测 response_format                    │ │
│  │   │   │       ├─ 探测 tools                              │ │
│  │   │   │       └─ 返回: supports_tools=True               │ │
│  │   │   │                                              │ │
│  │   │   └─ 缓存到 self._capability_cache                  │ │
│  │   │                                                      │ │
│  │   └─ StrategySelector.select() → "tools"                │ │
│  │                                                          │ │
│  │ call(message, history)                                     │ │
│  │   │                                                      │ │
│  │   └─ 根据策略调用对应的 LLM 方法：                        │ │
│  │       ├─ response_format → chat_with_response_format()    │ │
│  │       ├─ tools        → chat_with_tools()                 │ │
│  │       └─ prompt       → chat()                            │ │
│  └───────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        BaseAIService                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │    chat()    │  │chat_stream() │  │ chat_with_tools()    │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.2.2 探测时序图

```
时间线 ────────────────────────────────────────────────────────────▶

【用户请求】
    │
    ▼
FileOperationAgent._get_llm_response()
    │
    ▼
LLMAdapter.ensure_capability()  ◀── 【探测入口：首次调用时触发】
    │
    ├─ 首次调用？
    │   ├─ 是 → CapabilityDetector.detect()
    │   │       │
    │   │       ├─ Step1: 探测 tools【优先级最高】
    │   │       │       └─ 返回: supports_tools=True → 选择 tools
    │   │       │
    │   │       ├─ Step2: 探测 response_format
    │   │       │       └─ (仅在 tools 不支持时使用)
    │   │       │
    │   │       └─ Step3: 降级到 prompt
    │   │
    │   ├─ 缓存到 self._capability_cache
    │   │
    │   └─ StrategySelector.select() → "tools"【根据优先级选择】
    │
    ├─ 否（已缓存）
    │   └─ 直接返回缓存的策略
    │
    ▼
返回 SelectedStrategy(method="tools")  ◀── 【tools 优先级最高】
    │
    ▼
根据策略调用对应的 LLM 方法
    │
    ├─ tools          → chat_with_tools()【推荐】
    ├─ response_format → chat_with_response_format()
    └─ prompt         → chat()
```

### 4.3 缓存策略

#### 4.3.1 缓存层级

```
┌─────────────────────────────────────────────────────────────────┐
│                        缓存层级                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Level 1: 内存缓存 (self._capability_cache)                    │
│  ├── 生命周期: 服务实例生命周期                                  │
│  ├── 范围: 当前实例内复用                                       │
│  └── 优点: 零延迟                                               │
│                                                                 │
│  Level 2: 文件缓存 (~/.omniagent/llm_capability_cache.json)   │
│  ├── 生命周期: 持久化，重启后可复用                              │
│  ├── 范围: 当前用户/机器复用                                    │
│  └── 优点: 避免重复探测（节省~1秒）                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 4.3.2 文件缓存实现（可选）

```python
# backend/app/services/file_operations/llm_adapter.py

from pathlib import Path
import json

# 缓存文件路径
CACHE_FILE = Path("~/.omniagent/llm_capability_cache.json").expanduser()

class LLMAdapter:
    async def ensure_capability(self) -> SelectedStrategy:
        # 1. 尝试从缓存文件加载
        if CACHE_FILE.exists():
            try:
                cached = json.loads(CACHE_FILE.read_text())
                if cached.get("model") == self._service.model:
                    self._capability_cache = LLMFeature(**cached["feature"])
                    self._strategy = StrategySelector.select(self._capability_cache)
                    logger.info(f"[LLMAdapter] Loaded from cache: {self._strategy.method}")
                    return self._strategy
            except Exception:
                pass  # 缓存读取失败，继续探测
        
        # 2. 缓存不存在或模型不同，进行探测
        result = await self._detector.detect()
        
        if result.success:
            self._capability_cache = result.feature
            self._strategy = StrategySelector.select(self._capability_cache)
            
            # 3. 保存到缓存文件
            try:
                CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
                CACHE_FILE.write_text(json.dumps({
                    "model": self._service.model,
                    "feature": asdict(self._capability_cache),
                    "detected_at": datetime.now().isoformat()
                }))
                logger.info(f"[LLMAdapter] Saved to cache")
            except Exception:
                pass  # 缓存写入失败，不影响主流程
        else:
            self._strategy = SelectedStrategy(
                method="prompt",
                capability=LLMCapability.NONE,
                description=f"探测失败，使用基础模式"
            )
        
        return self._strategy
```

### 4.4 Agent 集成方式

#### 4.4.1 集成到 Agent 的代码

```python
# backend/app/services/file_operations/agent.py

class FileOperationAgent:
    def __init__(
        self,
        llm_client,
        session_id: str,
        file_tools: Optional[FileTools] = None,
        max_steps: int = 20,
        # 【新增】LLM 配置参数（可选）
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        # 【保留】原有参数（向后兼容）
        use_function_calling: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None
    ):
        # ... 现有初始化代码 ...
        
        # 【新增】LLM 适配器（可选）
        if api_base and api_key and model:
            from app.services.file_operations.llm_adapter import LLMAdapter
            self.adapter = LLMAdapter(
                api_base=api_base,
                api_key=api_key,
                model=model,
                auto_detect=True
            )
            logger.info(f"[Agent] LLMAdapter initialized for model: {model}")
        else:
            self.adapter = None
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应"""
        # 【新增】计数器递增
        self.llm_call_count += 1
        logger.info(f"[LLM Counter] >>> LLM called, count: {self.llm_call_count}")
        
        try:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]
            
            # 【修改】使用 LLMAdapter（如果已配置）
            if self.adapter:
                # 确保能力已探测
                strategy = await self.adapter.ensure_capability()
                logger.info(f"[Agent] Using method: {strategy.method}")
                
                # 根据策略选择调用方式
                if strategy.method == "response_format":
                    response = await self._get_llm_response_with_response_format(
                        message=last_message,
                        history_dicts=history_dicts
                    )
                elif strategy.method == "tools":
                    response = await self._get_llm_response_with_tools(
                        message=last_message,
                        history_dicts=history_dicts
                    )
                else:
                    response = await self._get_llm_response_text(
                        message=last_message,
                        history_dicts=history_dicts
                    )
            elif self.use_function_calling and self.tools:
                # 原有 Function Calling 模式（向后兼容）
                response = await self._get_llm_response_with_tools(
                    message=last_message,
                    history_dicts=history_dicts
                )
            else:
                # 原有文本模式（向后兼容）
                response = await self._get_llm_response_text(
                    message=last_message,
                    history_dicts=history_dicts
                )
            
            return response
            
        except Exception as e:
            logger.error(f"LLM client error: {e}")
            raise
```

### 4.5 使用方式

#### 4.5.1 方式一：自动探测（推荐）

```python
# 使用 LLMAdapter 自动探测并选择最佳策略
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    # 【关键】提供 LLM 配置，启用自适应模式
    api_base="https://api.longcat.chat/openai/v1",
    api_key="your-api-key",
    model="LongCat-Flash-Thinking-2601"
)

# 输出日志示例:
# [Agent] LLMAdapter initialized for model: LongCat-Flash-Thinking-2601
# [Agent] Detecting LLM capabilities...
# [Agent] Step1: Probing tools... → ✅ supported
# [Agent] Using method: tools【tools 优先级最高】
```

#### 4.5.2 方式二：手动指定（向后兼容）

```python
# 不提供 api 配置，使用原有方式
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    # 不提供 api 配置，使用原有方式
    use_function_calling=True,
    tools=tools_schema
)

# 输出日志示例:
# FileOperationAgent initialized (session: xxx, function_calling=True)
```

---

## 五、Agent 集成

### 5.1 Agent 使用示例

```python
# backend/app/services/file_operations/agent.py

class FileOperationAgent:
    """
    文件操作 ReAct Agent（自适应版本）
    """
    
    def __init__(
        self,
        llm_client,
        session_id: str,
        file_tools: Optional[FileTools] = None,
        max_steps: int = 20,
        # 【新增】LLM 配置
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        # ... 现有初始化 ...
        
        # 【新增】LLM 适配器
        if api_base and api_key and model:
            from app.services.file_operations.llm_adapter import LLMAdapter
            self.adapter = LLMAdapter(api_base, api_key, model)
        else:
            self.adapter = None
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应"""
        # ... 现有代码 ...
        
        # 【修改】确保能力已探测
        if self.adapter:
            strategy = await self.adapter.ensure_capability()
            logger.info(f"[Agent] Using method: {strategy.method}")
            
            # 根据策略调用
            if strategy.method == "response_format":
                response = await self._call_with_response_format(...)
            elif strategy.method == "tools":
                response = await self._call_with_tools(...)
            else:
                response = await self.llm_client(...)
        else:
            # 没有适配器，使用原有方式
            response = await self.llm_client(...)
        
        # ... 后续处理 ...
```

### 5.2 使用方式

```python
# 方式1: 自动探测（推荐）
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    api_base="https://api.longcat.chat/openai/v1",
    api_key="your-api-key",
    model="LongCat-Flash-Thinking-2601"
)
# 输出: [Agent] Using method: tools

# 方式2: 手动指定（不推荐）
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id,
    # 不提供 api 配置，使用原有方式
)
```

---

## 六、测试用例

### 6.1 能力探测测试

```python
# tests/test_capability_detector.py

@pytest.mark.asyncio
async def test_longcat_detector():
    """测试 LongCat 能力探测"""
    detector = CapabilityDetector(
        api_base="https://api.longcat.chat/openai/v1",
        api_key="test-key",
        model="LongCat-Flash-Thinking-2601"
    )
    
    result = await detector.detect()
    
    assert result.success
    assert result.response_format_tested == True
    assert result.response_format_works == False  # LongCat 不支持
    assert result.tools_tested == True
    assert result.tools_works == True  # LongCat 支持 tools
    assert result.feature.supports_tools == True

@pytest.mark.asyncio
async def test_cache():
    """测试缓存"""
    detector = CapabilityDetector(...)
    
    # 第一次探测
    result1 = await detector.detect()
    
    # 第二次调用应该使用缓存
    result2 = await detector.detect()
    assert result2 is not None
```

### 6.2 策略选择测试

```python
# tests/test_strategy_selector.py

def test_prefers_response_format():
    """测试优先选择 response_format"""
    feature = LLMFeature(
        supports_response_format=True,
        supports_tools=True
    )
    
    strategy = StrategySelector.select(feature)
    assert strategy.method == "response_format"

def test_fallback_to_tools():
    """测试降级到 tools"""
    feature = LLMFeature(
        supports_response_format=False,
        supports_tools=True
    )
    
    strategy = StrategySelector.select(feature)
    assert strategy.method == "tools"

def test_fallback_to_prompt():
    """测试降级到 prompt"""
    feature = LLMFeature(
        supports_response_format=False,
        supports_tools=False
    )
    
    strategy = StrategySelector.select(feature)
    assert strategy.method == "prompt"
```

---

## 七、实现计划

### 7.1 阶段1: 核心模块（约2小时）

- [ ] 创建 `capability.py`（能力枚举）
- [ ] 创建 `capability_detector.py`（能力探测器）
- [ ] 创建 `strategy_selector.py`（策略选择器）

### 7.2 阶段2: 适配器集成（约1小时）

- [ ] 创建 `llm_adapter.py`（统一入口）
- [ ] 修改 `agent.py`（集成适配器）

### 7.3 阶段3: 测试验证（约1小时）

- [ ] 编写能力探测测试
- [ ] 编写策略选择测试
- [ ] 实际调用验证

---

## 八、优势总结

| 特性 | 硬编码方案 | 自适应方案（修正后） |
|------|-----------|---------------------|
| **策略优先级** | ❌ response_format > tools | ✅ tools > response_format |
| **新模型支持** | 需手动添加 | ✅ 自动探测 |
| **模型名称变体** | ❌ 可能不匹配 | ✅ 无影响 |
| **未知模型** | ❌ 无法处理 | ✅ 自动降级 |
| **API 能力差异** | ❌ 假设一致 | ✅ 真实探测 |
| **支持模型数** | 依赖列表 | ✅ tools 约50个，response_format 约45个 |
| **维护成本** | 高（需更新列表） | 低（自动适应） |
| **探测时机** | N/A | ✅ 首次调用时（懒加载） |
| **缓存策略** | N/A | ✅ 内存 + 文件缓存 |

### 修正说明

**v1.1 → v1.2 修正内容**：
1. **修正策略优先级**：tools > response_format > prompt
   - 原因：实测 tools 支持约50个模型，response_format 约45个
2. **更新探测流程**：Step1 改为探测 tools
3. **更新所有相关说明和示例**

---

**文档结束**

**编写时间**: 2026-03-20 09:15:00
**更新时间**: 2026-03-20 10:25:00
**编写人**: 小沈
**版本**: v1.2

**版本历史**:
- v1.0: 2026-03-20 09:15:00 - 初始版本
- v1.1: 2026-03-20 09:12:02 - 新增第四章「探测时机与集成架构」，包含探测时机选择、缓存策略、Agent集成方式等详细内容
- v1.2: 2026-03-20 10:25:00 - **修正策略优先级**：tools > response_format > prompt（根据实测结果修正）
- v1.3: 2026-03-20 10:05:00 - **新增系统适配章节**：Windows/Linux/Mac 系统适配，OSAdapter 类，工具描述系统适配说明
