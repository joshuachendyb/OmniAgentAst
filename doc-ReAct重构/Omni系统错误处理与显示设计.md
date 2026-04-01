# Omni系统错误处理与显示设计

**版本**: v2.2
**创建时间**: 2026-04-01 13:07:28
**作者**: 小沈
**更新时间**: 2026-04-01 15:16:08

---

## 1. 原始设计（2026-03-22）

### 1.1 error_handler.py 统一错误处理设计

**来源**: `doc-多意图/多意图系统与现有代码整合架构设计-2026-03-22.md` 第3.4节

**设计时间**: 2026-03-22
**设计人**: 小沈

#### 1.1.1 设计目标

将 `chat_stream.py` 中的错误处理逻辑拆分出来，形成**统一的错误处理模块**。

#### 1.1.2 文件位置

- 当前文件：`app/chat_stream/error_handler.py`（180行）
- 原始行号：86-139, 383-463, 1277-1286

#### 1.1.3 核心函数

| 函数 | 说明 | 返回 |
|------|------|------|
| create_error_response() | 创建错误响应（SSE格式） | str |
| get_user_friendly_error() | 根据Exception获取友好错误 | Dict |
| ERROR_TYPE_MAP | 错误类型映射表（7种→2种） | Dict |
| classify_error() | 根据error_type分类 | tuple(code, message) |

#### 1.1.4 错误类型映射表（原始设计 - 有问题）

```
| 错误类型 | code | 消息 |
| idle_timeout | timeout | 请求超时：AI模型30秒内未返回任何内容 |
| timeout_error | timeout | 请求超时，请重试 |
| read_error | server | 读取响应失败，请重试 |
| connect_error | network | 连接失败，请检查网络 | ← 问题1
| protocol_error | server | 协议错误，请重试 | ← 问题2
| proxy_error | network | 代理错误，请检查网络配置 | ← 问题3
| write_error | server | 发送请求失败 |
| network_error | network | 网络错误，请检查网络连接 |
```

#### 1.1.5 原始设计的问题

| 问题 | 当前映射 | 正确映射 | 说明 |
|------|---------|---------|------|
| 1 | connect_error → network | connect | 连接失败≠网络不通 |
| 2 | protocol_error → server | protocol | 协议错误应单独分类 |
| 3 | proxy_error → network | protocol | 代理错误也是协议问题 |

---

## 2. 代码架构（当前实现）

### 2.1 文件分布

| 文件 | 职责 | 位置 |
|------|------|------|
| **error_handler.py** | 统一的错误处理函数（核心） | app/chat_stream/ |
| **llm_core.py** | 捕获httpx/httpcore异常 | app/services/ |
| **chat_stream_query.py** | LLM调用错误处理 | app/chat_stream/ |
| **react_sse_wrapper.py** | Agent层错误处理 | app/services/ |

### 2.2 错误处理函数说明

#### 2.2.1 error_handler.py（统一错误处理核心）

```
位置: backend/app/chat_stream/error_handler.py
职责: 统一的错误处理函数库
```

| 函数 | 说明 | 返回 |
|------|------|------|
| create_error_step() | 创建保存到数据库的error步骤 | Dict |
| create_error_response() | 生成SSE格式错误响应 | str |
| get_user_friendly_error() | 根据Exception获取友好错误 | Dict |
| classify_error() | 根据error_type分类 | tuple(code, message) |
| ERROR_TYPE_MAP | 错误类型映射表（7种→2种） | Dict |

**ERROR_TYPE_MAP（当前实现 - 有问题）**:
```python
ERROR_TYPE_MAP = {
    'idle_timeout': ('timeout', '...'),      # 空闲超时
    'timeout_error': ('timeout', '...'),     # 超时
    'read_error': ('server', '...'),        # ✅ 正确
    'connect_error': ('network', '...'),    # ❌ 应为connect
    'protocol_error': ('server', '...'),    # ❌ 应为protocol
    'proxy_error': ('network', '...'),       # ❌ 应为protocol
    'write_error': ('server', '...'),        # ✅ 正确
    'network_error': ('network', '...'),     # ✅ 正确
}
```

#### 2.2.2 llm_core.py（异常捕获层）

```
位置: backend/app/services/llm_core.py
职责: 捕获httpx/httpcore异常，生成StreamChunk
```

| 异常类型 | stream_error_type | 错误提示 |
|---------|------------------|---------|
| httpx.TimeoutException | timeout_error | "请求超时，请重试" |
| httpx.ConnectError | connect_error | "连接失败，请检查网络" |
| httpx.NetworkError | network_error | "网络不通，请检查网络连接" |
| httpx.ReadError | read_error | "读取响应失败，请重试" |
| httpx.WriteError | write_error | "发送请求失败" |
| httpx.ProtocolError | protocol_error | "协议错误，请重试" |
| httpx.ProxyError | proxy_error | "代理错误，请检查网络配置" |

#### 2.2.3 chat_stream_query.py（LLM调用错误处理）

```
位置: backend/app/chat_stream/chat_stream_query.py
职责: LLM调用错误处理和映射
```

| 函数 | 说明 |
|------|------|
| get_ai_service() | 获取AI服务 |
| call_llm_with_retry() | 带重试的LLM调用 |
| 错误映射 | stream_error_type → error_type |

**错误映射（当前实现 - 有问题）**:
```python
error_type_map = {
    'idle_timeout': ('timeout', '...'),
    'timeout_error': ('timeout', '...'),       # ✅
    'read_error': ('server', '...'),           # ✅
    'connect_error': ('network', '...'),       # ❌ 应为connect
    'protocol_error': ('server', '...'),       # ❌ 应为protocol
    'proxy_error': ('network', '...'),         # ❌ 应为protocol
    'write_error': ('server', '...'),          # ✅
    'network_error': ('network', '...'),        # ✅
}
```

#### 2.2.4 react_sse_wrapper.py（Agent层错误处理）

```
位置: backend/app/services/react_sse_wrapper.py
职责: Agent层的错误处理（安全拦截、任务中断等）
```

| 错误类型 | 说明 |
|---------|------|
| 安全拦截 | security_check失败 |
| 任务中断 | 用户主动中断 |
| 暂停恢复 | 任务暂停/恢复 |
| 通用错误 | 其他异常 |

---

## 3. 错误处理流程

### 3.1 完整调用链

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           LLM服务层 (LLM Providers)                          │
│   LongCat / DMXAPI / OpenCode / Qiniu                                       │
│   └── API返回异常 → httpx/httpcore异常                                       │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        llm_core.py (异常捕获层)                              │
│   except httpx.TimeoutException:                                            │
│       yield StreamChunk(stream_error_type="timeout_error")                 │
│   except httpx.ConnectError:                                               │
│       yield StreamChunk(stream_error_type="connect_error")                 │
│   ...                                                                       │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼ StreamChunk
┌─────────────────────────────────────────────────────────────────────────────┐
│                    chat_stream_query.py (错误映射层)                        │
│   if chunk.stream_error:                                                    │
│       last_error_type = chunk.stream_error_type  # timeout_error           │
│       error_type_map[last_error_type] = ("timeout", "请求超时...")          │
│   create_error_response(error_type="timeout", message="请求超时...")       │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼ create_error_response()
┌─────────────────────────────────────────────────────────────────────────────┐
│                    error_handler.py (统一处理函数)                          │
│   create_error_response() → SSE格式错误响应                                 │
│   create_error_step() → 数据库错误步骤                                      │
│   ERROR_TYPE_MAP → 错误类型映射表                                           │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          react_sse_wrapper.py (Agent层)                     │
│   yield create_error_response() → 前端                                      │
│   error_step = create_error_step() → add_step_and_save() → 数据库           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 错误传播流程

```
1. LLM API异常
   └→ httpx/httpcore异常
   
2. llm_core.py捕获
   └→ StreamChunk(stream_error_type="connect_error")
   
3. chat_stream_query.py处理
   └→ error_type_map["connect_error"] = ("network", "连接失败...")
   └→ create_error_response(error_type="network", message="连接失败...")
   
4. react_sse_wrapper.py发送
   └→ yield create_error_response() → SSE推送
   └→ create_error_step() → 保存到数据库
```

---

## 4. 问题分析

### 4.1 当前问题

**问题：connect_error和protocol_error被错误归类**

| stream_error_type | 当前映射 | 正确映射 |
|-------------------|---------|---------|
| connect_error | network ❌ | connect ✅ |
| protocol_error | server ❌ | protocol ✅ |
| proxy_error | network ❌ | protocol ✅ |

### 4.2 需要修改的文件

1. **error_handler.py** - 3处修改
   - ERROR_TYPE_MAP：修正 connect/protocol 映射
   - get_user_friendly_error()：改为调用 ERROR_TYPE_MAP
   - get_error_info_by_type()：**新增**辅助函数

2. **chat_stream_query.py** - 1处修改
   - 调用 get_error_info_by_type() 获取错误信息

**不需要修改的文件**：
- **react_sse_wrapper.py** - react loop 中已经调用 `get_user_friendly_error(e)`，会自动使用更新后的 error_type

### 4.3 小健检查意见（2026-04-01）

**小健检查后的优化建议**：

| 序号 | 建议 | 理由 |
|------|------|------|
| 1 | **明确 get_user_friendly_error() 的处理策略** | 该函数被 `__init__.py` 导出，可能被外部调用。需要明确：是只处理 httpx 异常并使用 ERROR_TYPE_MAP，还是保留对其他异常的处理？ |
| 2 | **补充前端配合说明** | 5种错误类型需要前端显示对应图标/颜色（第6章已设计），需确认前端代码是否已实现 |
| 3 | **增加 IdleTimeoutError 映射** | ERROR_TYPE_MAP 有 'idle_timeout'，但代码中 llm_core.py 未产生此 stream_error_type，需确认是否需要处理 |

**小健检查结论**：

> 设计总体合理，但有3点需补充：
> 1. 明确 get_user_friendly_error() 对非 httpx 异常的处理方式
> 2. 确认前端是否已实现5种错误类型的显示
> 3. 补充 IdleTimeoutError 的处理逻辑

---

## 5. 错误分类设计（2026-04-01 扩展）

### 5.1 底层异常（httpx/httpcore）

| 异常类型 | 说明 |
|---------|------|
| TimeoutException | 超时（包含ReadTimeout + ConnectTimeout） |
| ConnectError | TCP连接失败 |
| NetworkError | 网络不通（DNS失败、路由不可达、网线断开） |
| ReadError | 读取响应失败 |
| WriteError | 发送请求失败 |
| ProtocolError | 协议错误 |
| ProxyError | 代理错误 |

### 5.2 前端展示类型（5种）

```
network_error（网络问题）
│
├── timeout（超时）
│   └── TimeoutException（ReadTimeout + ConnectTimeout）
│
├── connect（连接）
│   └── ConnectError
│
├── protocol（协议）
│   ├── ProtocolError（通信协议不对）
│   └── ProxyError（代理配置问题）
│
├── server（服务器问题）
│   ├── ReadError（读取响应失败）
│   └── WriteError（发送请求失败）
│
└── network（网络不通）
    └── NetworkError（DNS失败、路由不可达、网线断开）
```

### 5.3 正确映射关系（修正后）

| 前端类型 | 底层异常 | 用户看到的提示 |
|---------|---------|---------------|
| timeout | ReadTimeout | "请求超时（读取等待），请重试" |
| timeout | ConnectTimeout | "请求超时（连接等待），请检查网络" |
| connect | ConnectError | "连接失败，请检查网络" |
| protocol | ProtocolError | "协议错误，请重试" |
| protocol | ProxyError | "代理配置错误，请检查网络配置" |
| server | ReadError | "服务器响应过慢，请重试" |
| server | WriteError | "发送请求失败，请重试" |
| network | NetworkError(DNS) | "网络不通（DNS解析失败），请检查网络连接" |
| network | NetworkError(路由) | "网络不通（路由不可达），请检查网络连接" |
| network | NetworkError(断开) | "网络不通（连接已断开），请检查网络连接" |

---

## 6. 前端显示设计

### 6.1 错误类型显示

| error_type | 图标 | 颜色 | 错误提示 |
|-----------|------|------|---------|
| timeout | ⏱️ 时钟 | 橙色 | "请求超时（读取等待），请重试" 或 "请求超时（连接等待），请检查网络" |
| connect | 🔗 连接 | 红色 | "连接失败，请检查网络" |
| protocol | 📋 协议 | 黄色 | "协议错误，请重试" 或 "代理配置错误，请检查网络配置" |
| server | 🖥️ 服务器 | 蓝色 | "服务器响应过慢，请重试" 或 "发送请求失败，请重试" |
| network | 📵 断网 | 红色 | "网络不通（DNS解析失败），请检查网络连接" 或 "网络不通（路由不可达），请检查网络连接" 或 "网络不通（连接已断开），请检查网络连接" |

### 6.2 错误步骤数据结构

```python
# 后端 create_error_response() 生成（示例）
{
    "type": "error",
    "step": 5,
    "timestamp": 1774998665000,
    "error_type": "timeout",  # 5种之一
    "message": "请求超时（读取等待），请重试",  # 细化后的具体提示
    "retryable": True,
    "retry_after": 3,
    "model": "LongCat-Flash-Thinking-2601",
    "provider": "longcat"
}
```

---

## 7. 代码更新方案（2026-04-01）

### 7.1 核心原则：统一使用 ERROR_TYPE_MAP

**问题分析**：
- get_user_friendly_error() 基于 Exception 类型返回 error_type
- chat_stream_query.py 基于 stream_error_type 返回 error_type
- **两者不一致会导致前端显示不同！**

**解决方案**：
get_user_friendly_error() 也要调用 ERROR_TYPE_MAP，保持与 chat_stream_query.py 一致。

### 7.2 需要修改的位置汇总

| 序号 | 文件 | 位置 | 说明 |
|------|------|------|------|
| 1 | error_handler.py | ERROR_TYPE_MAP | 统一错误映射定义（修正connect/protocol映射） |
| 2 | error_handler.py | get_user_friendly_error() | 改为调用 ERROR_TYPE_MAP |
| 3 | error_handler.py | get_error_info_by_type() | **新增**辅助函数，供 chat_stream_query.py 调用 |
| 4 | chat_stream_query.py | 第326-335行 | 调用 get_error_info_by_type() 获取错误信息 |

**说明**：react_sse_wrapper.py 的 react loop（约第544-566行）**不需要修改**，原因同上。

### 7.3 第一步：修改 error_handler.py 的 ERROR_TYPE_MAP

**文件**: `backend/app/chat_stream/error_handler.py`
**位置**: 第199-208行

**当前代码（有问题的）**:
```python
# 错误类型映射表（用于重试失败后的错误分类）
ERROR_TYPE_MAP = {
    'idle_timeout': ('timeout', '请求超时：AI模型30秒内未返回任何内容，已重试3次，请更换问题或稍后重试'),
    'timeout_error': ('timeout', '请求超时，请重试'),
    'read_error': ('server', '读取响应失败，请重试'),
    'connect_error': ('network', '连接失败，请检查网络'),           # ❌ 应为 connect
    'protocol_error': ('server', '协议错误，请重试'),                 # ❌ 应为 protocol
    'proxy_error': ('network', '代理错误，请检查网络配置'),           # ❌ 应为 protocol
    'write_error': ('server', '发送请求失败'),
    'network_error': ('network', '网络错误，请检查网络连接'),
}
```

**修改后（正确的）**:
```python
# 错误类型映射表（用于重试失败后的错误分类）
# 【小沈修复 2026-04-01】修正错误分类：connect→connect, protocol→protocol
ERROR_TYPE_MAP = {
    'idle_timeout': ('timeout', '请求超时：AI模型30秒内未返回任何内容，已重试3次，请更换问题或稍后重试'),
    'timeout_error': ('timeout', '请求超时，请重试'),
    'read_error': ('server', '读取响应失败，请重试'),
    'connect_error': ('connect', '连接失败，请检查网络'),            # ✅ 修正：network → connect
    'protocol_error': ('protocol', '协议错误，请重试'),              # ✅ 修正：server → protocol
    'proxy_error': ('protocol', '代理错误，请检查网络配置'),         # ✅ 修正：network → protocol
    'write_error': ('server', '发送请求失败'),
    'network_error': ('network', '网络错误，请检查网络连接'),
}
```

**修改说明**：
- `connect_error`: `'network'` → `'connect'` （连接失败≠网络不通）
- `protocol_error`: `'server'` → `'protocol'` （协议错误应单独分类）
- `proxy_error`: `'network'` → `'protocol'` （代理错误也是协议问题）

### 7.4 第二步：修改 error_handler.py 的 get_user_friendly_error()

**文件**: `backend/app/chat_stream/error_handler.py`

**当前问题**：get_user_friendly_error() 独立判断 Exception 类型，不使用 ERROR_TYPE_MAP

**当前代码**:
```python
def get_user_friendly_error(error: Exception) -> Dict[str, Any]:
    error_type = type(error).__name__
    error_msg = str(error).lower()
    
    if error_type == "TimeoutError" or "timeout" in error_msg:
        return {
            "code": "TIMEOUT",
            "message": "请求超时，请重试",
            "error_type": "network",  # ❌ 独立判断，与 ERROR_TYPE_MAP 不一致
            ...
        }
    elif error_type == "ConnectionError" or "connection" in error_msg:
        return {
            "code": "CONNECTION_ERROR",
            "message": "网络连接失败，请检查网络",
            "error_type": "network",  # ❌
            ...
        }
```

**修改后**:
```python
def get_user_friendly_error(error: Exception) -> Dict[str, Any]:
    """
    获取用户友好的错误信息
    【小沈修复 2026-04-01】统一使用 ERROR_TYPE_MAP，与 chat_stream_query.py 保持一致
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()
    
    # 将 Exception 类型转换为 stream_error_type
    exception_to_stream_error = {
        "TimeoutError": "timeout_error",
        "IdleTimeoutError": "idle_timeout",
        "ConnectionError": "connect_error",
        "httpx.TimeoutException": "timeout_error",
        "httpx.ConnectError": "connect_error",
        "httpx.ReadError": "read_error",
        "httpx.WriteError": "write_error",
        "httpx.ProtocolError": "protocol_error",
        "httpx.ProxyError": "proxy_error",
        "httpx.NetworkError": "network_error",
    }
    
    # 转换为 stream_error_type，查询 ERROR_TYPE_MAP
    stream_error_type = exception_to_stream_error.get(error_type, "")
    
    if stream_error_type in ERROR_TYPE_MAP:
        code, message = ERROR_TYPE_MAP[stream_error_type]
        return {
            "code": code,
            "message": message,
            "error_type": code,  # 使用 ERROR_TYPE_MAP 的 code
            "retryable": True,
            "retry_after": 5
        }
    
    # 未匹配的异常使用默认处理
    return {
        "code": "UNKNOWN_ERROR",
        "message": "AI 处理异常，请稍后重试",
        "error_type": "server",
        "retryable": True,
        "retry_after": 5
    }
```

**修改要点**：
1. 建立 Exception 类型 → stream_error_type 的映射表
2. 使用 ERROR_TYPE_MAP 获取统一的 error_type 和 message
3. 与 chat_stream_query.py 的处理逻辑完全一致

### 7.5 第三步：修改 chat_stream_query.py 调用 ERROR_TYPE_MAP

**文件**: `backend/app/chat_stream/chat_stream_query.py`
**位置**: 第326-335行

**当前代码（有问题的 - 硬编码复制）**:
```python
# 第326-335行
error_type_map = {
    'idle_timeout': ('timeout', f'请求超时：AI模型({display_name}) {chat_timeout}秒内未返回任何内容，已重试{max_retries}次，合计{total_timeout}秒，请更换问题或稍后重试'),
    'timeout_error': ('timeout', '请求超时，请重试'),
    'read_error': ('server', '读取响应失败，请重试'),
    'connect_error': ('network', '连接失败，请检查网络'),            # ❌ 应为 connect
    'protocol_error': ('server', '协议错误，请重试'),                  # ❌ 应为 protocol
    'proxy_error': ('network', '代理错误，请检查网络配置'),           # ❌ 应为 protocol
    'write_error': ('server', '发送请求失败'),
    'network_error': ('network', '网络错误，请检查网络连接'),
}
```

**方案C：调用 error_handler 辅助函数（最佳 - 与 react_sse_wrapper 一致）**

参考 react_sse_wrapper.py 的做法，创建一个辅助函数，根据 error_type 字符串返回 error_info：

```python
# 在 error_handler.py 中新增函数
def get_error_info_by_type(error_type: str) -> Dict[str, Any]:
    """
    根据 stream_error_type 获取错误信息
    用于 chat_stream_query.py（没有 Exception 对象，只有 error_type 字符串）
    
    Args:
        error_type: stream_error_type 字符串，如 'connect_error', 'timeout_error' 等
    
    Returns:
        错误信息字典，包含 code, message, error_type, retryable
    """
    if error_type in ERROR_TYPE_MAP:
        code, message = ERROR_TYPE_MAP[error_type]
        return {
            "code": code,
            "message": message,
            "error_type": code,
            "retryable": True,
            "retry_after": 5
        }
    # 未匹配的 error_type
    return {
        "code": "UNKNOWN_ERROR",
        "message": "AI 处理异常，请稍后重试",
        "error_type": "server",
        "retryable": True,
        "retry_after": 5
    }
```

然后 chat_stream_query.py 可以这样调用：

```python
# 第326-335行 - 替换为调用辅助函数
from app.chat_stream.error_handler import get_error_info_by_type

# 使用辅助函数获取错误信息
if last_error_type:
    error_info = get_error_info_by_type(last_error_type)
    # 个性化处理 idle_timeout
    if last_error_type == 'idle_timeout':
        total_timeout = chat_timeout * max_retries
        error_info['message'] = f'请求超时：AI模型({display_name}) {chat_timeout}秒内未返回任何内容，已重试{max_retries}次，合计{total_timeout}秒，请更换问题或稍后重试'
    error_type = error_info['error_type']
    error_message = error_info['message']
else:
    error_type, error_message = 'server', f"服务调用失败: {last_error}"
```

**方案对比**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| **方案A** | 引用 ERROR_TYPE_MAP.copy()，维护方便 | 仍需复制和修改 |
| **方案C** | 与 react_sse_wrapper 一致，最规范 | 需要新增辅助函数 |

**推荐采用方案C**，原因：
1. 与 react_sse_wrapper.py 的处理逻辑完全一致
2. 代码更清晰，调用 `get_error_info_by_type(last_error_type)` 即可
3. 后期只需要维护 ERROR_TYPE_MAP 一处

### 7.6 验证步骤

#### 7.6.1 语法检查

```bash
python -m py_compile backend/app/chat_stream/error_handler.py
python -m py_compile backend/app/chat_stream/chat_stream_query.py
```

#### 7.6.2 单元测试

```bash
cd backend
pytest tests/ -v
```

#### 7.6.3 手动验证

1. 启动后端服务
2. 触发各种网络错误场景
3. 验证前端显示的错误提示

### 7.7 回滚方案

```bash
git checkout -- backend/app/chat_stream/error_handler.py
git checkout -- backend/app/chat_stream/chat_stream_query.py
```

### 7.8 执行顺序

```
步骤1: 修改 error_handler.py - ERROR_TYPE_MAP（修正 connect/protocol 映射）
   ↓
步骤2: 修改 error_handler.py - get_user_friendly_error()（改为调用 ERROR_TYPE_MAP）
   ↓
步骤3: 新增 error_handler.py - get_error_info_by_type()（新增辅助函数，供 chat_stream_query 调用）
   ↓
步骤4: 修改 chat_stream_query.py - 调用 get_error_info_by_type()
   ↓
步骤5: 语法检查
   ↓
步骤6: 运行测试
   ↓
步骤7: 手动验证
   ↓
步骤8: 提交代码
```

---

## 8. 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-04-01 13:07:28 | 小沈 | 初始版本 |
| v1.1 | 2026-04-01 13:25:00 | 小沈 | 增加代码架构和当前问题分析 |
| v1.2 | 2026-04-01 13:40:00 | 小沈 | 增加第1章：原始设计（2026-03-22） |
| v1.3 | 2026-04-01 13:50:00 | 小沈 | 调整章节顺序：问题分析移到分类设计前面 |
| v1.4 | 2026-04-01 14:05:40 | 小沈 | 增加第7章：代码更新方案 |
| v1.5 | 2026-04-01 14:20:00 | 小沈 | 优化第7章：消除重复代码 |
| v1.6 | 2026-04-01 14:35:00 | 小沈 | 补充 get_user_friendly_error() 需要修改 |
| v1.7 | 2026-04-01 14:50:00 | 小沈 | get_user_friendly_error() 改为调用 ERROR_TYPE_MAP |
| v1.8 | 2026-04-01 15:20:00 | 小沈 | 补充小健检查意见：增加ERROR_TYPE_MAP完整代码、增加chat_stream_query.py两种修改方案 |
| v1.9 | 2026-04-01 15:30:00 | 小沈 | 补充react_sse_wrapper.py不需要修改的说明，解释原因 |
| v2.0 | 2026-04-01 15:40:00 | 小沈 | 增加方案C：调用error_handler辅助函数，与react_sse_wrapper一致 |
| v2.1 | 2026-04-01 15:05:30 | 小沈 | 删除重复的方案A和方案B，删除多余的620-647行，文档逻辑更清晰 |
| v2.2 | 2026-04-01 15:16:08 | 小沈 | 删除方案A代码残留+统一4.2节与7.2节描述 |

---

**创建时间**: 2026-04-01 13:07:28
**更新时间**: 2026-04-01 15:16:08
