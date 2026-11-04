# 工具结果给LLM数据统一格式设计方案

**创建时间**: 2026-06-20 15:27:14  
**更新时间**: 2026-06-20 16:45:00  
**版本**: v3.0  
**作者**: 小欧  
**批准人**: 北京老陈

> **设计目标**：所有工具返回给LLM的数据格式统一、完整、优美，让LLM能准确理解执行结果。

---

## 一、核心概念厘清

### 1.1 给LLM的数据到底是什么？

tool 的执行结果给 LLM 有两层含义：

| 层级 | 是什么 | 流向 | LLM 能否直接看到 |
|------|--------|------|-----------------|
| **原始数据层** | tool 返回的完整 dict，含 `code/data/message/result` | 存入 conversation history + ToolStep + SSE 给前端 | ❌ |
| **展示层** | `role: "tool"` 消息的 `content` 字段值（即 observation 文本） | → LLM 的上下文窗口 | ✅ |

**两者本质是一回事**：展示层文本 = 原始数据的序列化表示。

所以设计必须同时覆盖两层：
1. **原始数据层**（`result` 字段）— 统一结构、完整信息、类型化
2. **展示层**（observation 文本）— `result` 的机械序列化，LLM 的完整数据源

### 1.2 解决什么问题

| # | 问题 | 严重程度 | 方案 |
|---|------|---------|------|
| 1 | `llm_data` 字段在各 tool 间格式千奇百怪、中英混用 | **High** | 废除 `llm_data`，统一为 `result` 结构 |
| 2 | `llm_data` 被 `build_execution_result_dict` 静默丢弃 | **Critical** | 统一用 `result`，通过 pipeline 直达 LLM |
| 3 | `data` 与 `llm_data` 职责混淆、互相重复 | **High** | `result` 给 LLM，`data` 给前端，一刀切 |
| 4 | Warning 路径硬编码 `use_llm_data=False` 禁用 llm_data | **Medium** | `result` 在所有路径统一使用 |
| 5 | observation 文本混合自然语言 + kv + JSON | **Medium** | 新三板：纯结构化文本，无 JSON 无中文标记 |

---

## 二、设计原则

| 原则 | 说明 |
|------|------|
| **SRP** | `result` 给 LLM，`data` 给前端，职责一刀切不重叠 |
| **DRY** | 所有 tool 使用 `build_result()` 构建 result，不各自造轮子 |
| **KISS-DIRECT** | result 只有 `type/entity/ok/metric*` 四个概念，平铺无嵌套 |
| **Self-Describing** | `type` 字段让 LLM 一眼知道这是什么结果类型 |
| **Zero-overlap** | result 不含 data 中的原始大文本，只含关键指标 |
| **No-backward** | 一次性迁移，不兼容旧 `llm_data`，不留过渡代码 |

---

## 三、Result Schema（原始数据层）

所有 tool 必须返回 `result` 字段，作为给 LLM 的结构化数据源。**`llm_data` 字段废除**，不再使用。

### 3.1 通用结构

```python
result = {
    # 核心字段
    "type": "file_read",         # 结果类型标识
    "entity": "/path/file.txt",  # 操作主体
    "ok": True,                  # 成功标识

    # 关键指标（类型相关，扁平 key-value）
    "lines": 500,
    "total": 1000,
    "size": 12288,
    "encoding": "utf-8",

    # 错误信息（仅 ok=False 时）
    # "error_code": "ERR_FILE_NOT_FOUND",
    # "error_hint": "请检查路径是否正确",
}
```

### 3.2 字段定义

| 字段 | 必填 | 类型 | 说明 |
|------|------|------|------|
| `type` | ✅ | str | 结果类型，全小写+下划线，如 `file_read`/`shell_exec` |
| `entity` | ✅ | str | 操作主体。无实体时传 `""` |
| `ok` | ✅ | bool | true=成功，false=失败 |
| `error_code` | ❌ | str | 错误码，`ok=False` 时建议填写 |
| `error_hint` | ❌ | str | 恢复建议，`ok=False` 时建议填写 |

其余字段为按 type 约定的关键指标（metric），均为扁平 key-value，**禁止嵌套**。

### 3.3 entity 取值规则

| 场景 | 取值 | 示例 |
|------|------|------|
| 文件操作 | 文件/目录的绝对路径 | `"D:/project/main.py"` |
| 网络请求 | URL | `"https://api.example.com/users"` |
| Shell 命令 | 命令摘要（前 80 字符） | `"node build.js --production"` |
| 系统信息 | info_type | `"cpu"` |
| 事件日志 | log_name | `"System"` |
| 定时器 | timer_id | `"timer_abc123"` |
| 数据库查询 | 表名 | `"users"` |
| 无主体操作 | 空字符串 | `""` |

### 3.4 各类工具 Result 规范

| type | entity | 关键指标（metric） | 示例 |
|------|--------|------------------|------|
| `file_read` | 文件路径 | `lines,total,size,encoding` | `{"type":"file_read","entity":"D:/main.py","ok":true,"lines":500,"total":1000,"size":12288,"encoding":"utf-8"}` |
| `file_write` | 文件路径 | `bytes` | `{"type":"file_write","entity":"D:/main.py","ok":true,"bytes":2048}` |
| `file_append` | 文件路径 | `bytes` | 同上 |
| `file_delete` | 文件路径 | — | `{"type":"file_delete","entity":"D:/old.py","ok":true}` |
| `file_move` | 源路径 | `destination` | `{"type":"file_move","entity":"D:/a.py","ok":true,"destination":"D:/b.py"}` |
| `file_copy` | 源路径 | `destination` | 同上 |
| `file_rename` | 原路径 | `new_name` | 同上 |
| `file_list` | 目录路径 | `count,preview` | `{"type":"file_list","entity":"D:/project","ok":true,"count":42,"preview":["a.txt","b.txt"]}` |
| `file_search` | 搜索目录 | `count,matches` | `{"type":"file_search","entity":"D:/project","ok":true,"count":3,"matches":["a.py","b.py"]}` |
| `file_media` | 文件路径 | `mime_type,size` | `{"type":"file_media","entity":"img.png","ok":true,"mime_type":"image/png","size":102400}` |
| `shell_exec` | 命令摘要 | `exit_code,stdout,stderr` | `{"type":"shell_exec","entity":"dir /s","ok":true,"exit_code":0,"stdout":"(3000 chars)","stderr":""}` |
| `http_request` | URL | `status_code,content_type,body_len` | `{"type":"http_request","entity":"https://api.ex.com/users","ok":true,"status_code":200,"content_type":"json","body_len":5000}` |
| `system_info` | info_type | 各指标平铺 | `{"type":"system_info","entity":"cpu","ok":true,"usage":45,"cores":8}` |
| `event_log` | 日志源 | `count,level` | `{"type":"event_log","entity":"System","ok":true,"count":15,"level":"error"}` |
| `process_list` | `"all"` | `count` | `{"type":"process_list","entity":"all","ok":true,"count":120}` |
| `service_list` | `"all"` | `count` | `{"type":"service_list","entity":"all","ok":true,"count":80}` |
| `system_reboot` | `"scheduled"` | `delay` | `{"type":"system_reboot","entity":"scheduled","ok":true,"delay":60}` |
| `timer_create` | timer_id | `interval,repeat` | `{"type":"timer_create","entity":"timer_abc","ok":true,"interval":60,"repeat":0}` |
| `timer_cancel` | timer_id | — | `{"type":"timer_cancel","entity":"timer_abc","ok":true}` |
| `timer_list` | `"all"` | `count,timers` | `{"type":"timer_list","entity":"all","ok":true,"count":2,"timers":["ta","tb"]}` |
| `db_query` | 表名 | `rows,columns` | `{"type":"db_query","entity":"users","ok":true,"rows":100,"columns":["id","name"]}` |
| `data_analysis` | 数据源 | `rows,cols` | `{"type":"data_analysis","entity":"sales.csv","ok":true,"rows":1000,"cols":5}` |
| `desktop_screenshot` | 文件路径 | `size,width,height` | `{"type":"desktop_screenshot","entity":"shot.png","ok":true,"size":512000,"width":1920,"height":1080}` |
| `desktop_mouse` | `"click"`/`"move"` | `x,y,button` | `{"type":"desktop_mouse","entity":"click","ok":true,"x":100,"y":200,"button":"left"}` |
| `desktop_keyboard` | `"type"`/`"press"` | `text` | `{"type":"desktop_keyboard","entity":"type","ok":true,"text":"hello"}` |
| `desktop_window` | 窗口标题 | `action,x,y,w,h` | `{"type":"desktop_window","entity":"记事本","ok":true,"action":"move","x":0,"y":0}` |
| `fundamental_ask` | `"question"`/`"confirm"` | — | `{"type":"fundamental_ask","entity":"question","ok":true}` |
| `fundamental_finish` | `"success"`/`"failed"` | `reason` | `{"type":"fundamental_finish","entity":"success","ok":true}` |
| `fundamental_think` | `""` | `thought` | `{"type":"fundamental_think","entity":"","ok":true}` |
| `registry_read` | 注册表路径 | `value,type` | `{"type":"registry_read","entity":"HKLM\\...\\key","ok":true,"value":"data","type":"REG_SZ"}` |
| `registry_write` | 注册表路径 | `type` | `{"type":"registry_write","entity":"HKLM\\...\\key","ok":true,"type":"REG_SZ"}` |
| `registry_delete` | 注册表路径 | — | `{"type":"registry_delete","entity":"HKLM\\...\\key","ok":true}` |
| `code_exec` | 语言 | `exit_code,stdout,stderr` | `{"type":"code_exec","entity":"python","ok":true,"exit_code":0,"stdout":"hello","stderr":""}` |
| `time_current` | `"local"`/`"utc"` | `datetime,timezone` | `{"type":"time_current","entity":"local","ok":true,"datetime":"2026-06-20 15:30:00","timezone":"Asia/Shanghai"}` |

### 3.5 禁止

- ❌ 用中文 key（如 `{"文件名": ...}`）— LLM 对英文 key 理解更准确
- ❌ 把原始大文本放入 result（如 file content）— 放 `data` 给前端
- ❌ 嵌套结构（如 `{"metrics": {"lines": 500}}`）— 一律平铺
- ❌ 与 `data` 重复的字段 — result 只放关键指标
- ❌ 一个 tool 返回多种 type — 每个 tool 只有一个 type

---

## 四、Observation 文本格式（展示层）

### 4.1 三板结构

```
第1行: Observation: {STATUS} | {message}
第2行:   {type}: {entity} | {key=value key=value ...}
第3行:   > {error_hint}                             # 仅 error
         ⚠ {warning_detail}                         # 仅 warning
```

| STATUS | 对应 code |
|--------|-----------|
| `SUCCESS` | `SUCCESS` |
| `WARNING` | `WARNING_*` |
| `ERROR` | `ERR_*` |

### 4.2 成功示例

```
Observation: SUCCESS | 读取文件成功: /path/file.txt (500/1000行, 12KB)
  file_read: /path/file.txt | lines=500 total=1000 size=12288 encoding=utf-8
```

```
Observation: SUCCESS | 命令执行成功 (exit code 0)
  shell_exec: "node build.js" | exit_code=0 stdout="(3000 chars)" stderr="(empty)"
```

```
Observation: SUCCESS | HTTP 200: https://api.example.com/users
  http_request: https://api.example.com/users | status_code=200 content_type=json body_len=12400
```

```
Observation: SUCCESS | 列出目录成功: /home/user (42项)
  file_list: /home/user | count=42 preview=["doc1.txt", "doc2.txt", "doc3.txt", ...]
```

### 4.3 错误示例

```
Observation: ERROR [ERR_FILE_NOT_FOUND] | 文件不存在: /path/missing.txt
  file_read: /path/missing.txt
  > 请检查路径是否正确，可用 list_directory 查找文件
```

### 4.4 Warning 示例

```
Observation: WARNING [WARNING_FILE_DELETE_PERMANENT] | 文件已永久删除: /path/file.txt
  file_delete: /path/file.txt
  ⚠ 文件已永久删除，无法恢复
```

### 4.5 无 entity/无 metrics 示例

```
Observation: SUCCESS | 文件已永久删除: /tmp/test.txt
  file_delete: /tmp/test.txt
```

```
Observation: SUCCESS | 思考中...
  fundamental_think
```

### 4.6 key=value 格式化规则

| value 类型 | 示例 | 说明 |
|-----------|------|------|
| 数字 | `lines=500` | 直接显示 |
| 布尔 | `ok=true` | 小写 |
| 无空格字符串 | `encoding=utf-8` | 等号后直接接值 |
| 有空格字符串 | `stdout="(3000 chars)"` | 等号后加双引号 |
| 空字符串 | `stderr=""` | 等号后加空引号 |
| 列表（≤5项） | `preview=["a","b","c"]` | 方括号 |
| 列表（>5项） | `preview=["a","b",...,"(42 total)"]` | 显示前 3 + 总数 |
| None | `value=none` | 小写 |

### 4.7 entity 显示规则

| entity 值 | 显示 | 示例 |
|-----------|------|------|
| `""` | 省略 entity 及冒号 | `fundamental_think` |
| `"all"` | 保留 | `process_list: all` |
| >60 字符 | 截断 | `shell_exec: "npm install --save-dev eslint..."` |

### 4.8 设计规则

| 规则 | 说明 |
|------|------|
| **第1行** | `Observation: {STATUS} \| {message}` — 状态+摘要一键可知 |
| **第2行** | `{type}: {entity} \| {key=value ...}` — 结构化数据 |
| **第3行** | 仅 error/warning 有提示行 |
| **无 JSON** | 禁止在 observation 文本中嵌入 JSON |
| **无中文标记** | 禁止 `【摘要】` `【数据】` `【摘要】` 等标记 |
| **\| 分隔** | pipe 分隔不同语义段 |

---

## 五、完整数据流

```
工具实现函数 (file_tools.py)
  │
  │  build_success(
  │    data={content, total_lines, ...},          # 给前端
  │    message="读取文件成功: /path/file.txt...",  # 给 LLM 的摘要
  │    result=build_result("file_read", file_path, # 给 LLM 的结构化数据
  │                        lines=500, total=1000, size=12288, encoding="utf-8"),
  │  )
  │
  ▼
原始 dict: {code, data, message, result}
  │
  ├──→ ToolStep (SSE → 前端)
  │      execution_result 含 result
  │
  └──→ build_observation_text(raw_dict)
         │
         │  build_execution_result_dict(raw_dict)
         │    → {status, summary, data, result, ...}  ★ result 在这里通过
         │
         │  format_llm_observation(exec_dict)
         │    → _format_success_observation / _format_error / _format_warning
         │
         └──→ ToolResultMessage (role: "tool")
                content = "Observation: SUCCESS | ...\n  file_read: ..."
                tool_call_id: "call_xxx"
                 │
                 ▼
                LLM 上下文窗口
```

---

## 六、实施规范

### 6.1 `tool_response.py` — 构建层

#### 6.1.1 新增 `build_result()`

```python
def build_result(
    type_name: str,
    entity: str = "",
    ok: bool = True,
    error_code: str = "",
    error_hint: str = "",
    **metrics: Any,
) -> dict:
    """统一构建 result 对象

    每个工具执行结果必须调用此函数构建 result，禁止手动拼 dict。
    llm_data 字段已废除，所有给 LLM 的数据必须通过 result 传递。

    Args:
        type_name: 结果类型标识，全小写+下划线
        entity: 操作主体，文件路径/URL/命令等。无主体时传 ""
        ok: 成功标识
        error_code: 错误码（ok=False 时建议填写）
        error_hint: 恢复建议（ok=False 时建议填写）
        **metrics: 关键指标，扁平 key-value

    Raises:
        TypeError: type_name 含中文或大写字母
        ValueError: type_name 为空
    """
    if not type_name or not isinstance(type_name, str):
        raise ValueError(f"type_name 不能为空: {type_name}")
    if not type_name.isascii() or any(c.isupper() for c in type_name):
        raise TypeError(f"type_name 必须全小写 ASCII: {type_name}")

    result: dict = {"type": type_name, "entity": entity, "ok": ok}
    if error_code:
        result["error_code"] = error_code
    if error_hint:
        result["error_hint"] = error_hint
    for k, v in metrics.items():
        if k in ("type", "entity", "ok"):
            continue  # 禁止覆盖核心字段
        result[k] = v
    return result
```

#### 6.1.2 `_OPTIONAL_FIELDS` — 移除 `llm_data`

```python
_OPTIONAL_FIELDS = {
    "result": None,         # ← 给 LLM 的结构化数据
    "warning": None,
    "retry_count": 0,
    "return_direct": False,
    "attachment": None,
    # llm_data 已废除
}
```

#### 6.1.3 `build_success()` — 新签名

```python
def build_success(
    data: Any = None,
    message: str = "执行成功",
    result: Optional[dict] = None,     # ← 新增，替代 llm_data
    warning: Optional[str] = None,
    retry_count: int = 0,
    return_direct: bool = False,
    attachment: Optional[dict] = None,
    code: Optional[str] = None,
    **extra: Any,
) -> dict:
```

#### 6.1.4 `build_error()` — 新签名

```python
def build_error(
    code: str,
    message: str,
    data: Any = None,
    result: Optional[dict] = None,     # ← 新增
    warning: Optional[str] = None,
    attachment: Optional[dict] = None,
    **extra: Any,
) -> dict:
```

#### 6.1.5 `build_warning()` — 新签名

```python
def build_warning(
    code: str,
    message: str,
    data: Any = None,
    result: Optional[dict] = None,     # ← 新增
    attachment: Optional[dict] = None,
    **extra: Any,
) -> dict:
```

#### 6.1.6 `is_success()` / `is_error()` — 不变

状态判断函数不依赖 result，保持不变。

### 6.2 `observation_formatter.py` — 格式化层

#### 6.2.1 `build_execution_result_dict()` — 修正（新增 `result` 传递）

```python
def build_execution_result_dict(execution_result: dict) -> dict:
    _status = extract_status(execution_result)
    return {
        "status": _status,
        "summary": execution_result.get("message", ""),
        "data": execution_result.get("data"),
        "result": execution_result.get("result"),    # ★ 新增
        "retry_count": execution_result.get("retry_count", 0),
        "code": execution_result.get("code", SUCCESS_CODE),
        "warning": execution_result.get("warning"),
        "attachment": execution_result.get("attachment"),
        "return_direct": execution_result.get("return_direct", False),
        "error_message": execution_result.get("error_message", ""),
    }
```

#### 6.2.2 删除的旧函数

| 函数 | 替代 |
|------|------|
| `_extract_display_data()` | 被 `exec_result.get("result")` 替代 |
| `_format_summary_parts()` | 被 `_build_result_line()` 替代 |
| `_append_data()` | 被新三板替代 |
| `_append_warning()` | 逻辑合并到 `_build_hint_line()` |
| `_format_result_observation()` | 被三个独立分支替代 |

#### 6.2.3 新增辅助函数

```python
def _format_metric_value(v: Any) -> str:
    """格式化 metric value 为 key=value 字符串"""
    if v is None:
        return "none"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        if not v:
            return '""'
        if " " in v or "=" in v or "|" in v:
            return f'"{v}"'
        return v
    if isinstance(v, (list, tuple)):
        if len(v) > 5:
            preview = ", ".join(str(x) for x in v[:3])
            return f"[{preview}, ...({len(v)} total)]"
        items = ", ".join(str(x) for x in v)
        return f"[{items}]"
    if isinstance(v, dict):
        return f"({len(v)} keys)"
    return str(v)
```

```python
def _build_observation_line(status: str, message: str) -> str:
    """第1行: Observation: {STATUS} | {message}"""
    status_map = {"success": "SUCCESS", "warning": "WARNING", "error": "ERROR"}
    mapped = status_map.get(status, status.upper())
    return f"Observation: {mapped} | {message}"
```

```python
def _build_result_line(result: dict) -> str:
    """第2行: {type}: {entity} | {key=value ...}"""
    type_name = result.get("type", "unknown")
    entity = result.get("entity", "")

    if entity:
        if len(entity) > 60:
            entity = entity[:57] + "..."
        line = f"  {type_name}: {entity}"
    else:
        line = f"  {type_name}"

    skip_fields = {"type", "entity", "ok", "error_code", "error_hint"}
    parts = []
    for k, v in result.items():
        if k in skip_fields:
            continue
        parts.append(f"{k}={_format_metric_value(v)}")

    if parts:
        line += " | " + " ".join(parts)
    return line
```

```python
def _build_hint_line(result: dict, status: str) -> str:
    """第3行: error → "  > {hint}", warning → "  ⚠ {detail}" """
    if status == "error":
        hint = result.get("error_hint", "")
        if hint:
            return f"  > {hint}"
        return "  > 请尝试其他工具，不要重复调用同一失败操作"
    if status == "warning":
        return result.get("warning", "")
    return ""
```

#### 6.2.4 三板格式化函数

```python
def _format_success_observation(exec_result: dict) -> str:
    """成功三板"""
    result = exec_result.get("result")
    message = exec_result.get("message", "")
    parts = [_build_observation_line("success", message)]
    if result:
        parts.append(_build_result_line(result))
    if exec_result.get("warning"):
        parts.append(f'  ⚠ {exec_result["warning"]}')
    return "\n".join(parts)
```

```python
def _format_warning_observation(exec_result: dict) -> str:
    """Warning 三板 (修复旧版 use_llm_data=False)"""
    result = exec_result.get("result")
    message = exec_result.get("message", "")
    code = exec_result.get("code", "")
    status_line = _build_observation_line("warning", message)
    status_line = status_line.replace("WARNING |", f"WARNING [{code}] |", 1)
    parts = [status_line]
    if result:
        parts.append(_build_result_line(result))
    if exec_result.get("warning"):
        parts.append(f'  ⚠ {exec_result["warning"]}')
    return "\n".join(parts)
```

```python
def _format_error_observation(exec_result: dict, tool_name: str = "",
                               tool_params: Optional[dict] = None) -> str:
    """错误三板"""
    result = exec_result.get("result")
    message = exec_result.get("message", "")
    error_code = ""
    if result and result.get("error_code"):
        error_code = result["error_code"]
    if not error_code:
        error_code = exec_result.get("code", "")
    if error_code:
        status_line = f"Observation: ERROR [{error_code}] | {message}"
    else:
        status_line = f"Observation: ERROR | {message}"
    parts = [status_line]
    if result:
        parts.append(_build_result_line(result))
    hint = _build_hint_line(result or {}, "error")
    if hint:
        parts.append(hint)
    else:
        hint_text = _get_failure_hint(tool_name, tool_params, exec_result)
        if hint_text:
            parts.append(f"  > {hint_text}")
    return "\n".join(parts)
```

#### 6.2.5 `format_llm_observation()` — 入口不变

```python
def format_llm_observation(result: dict, tool_name: str = "",
                            tool_params: Optional[dict] = None) -> str:
    code = result.get("code")
    if code == SUCCESS_CODE:
        return _format_success_observation(result)
    elif isinstance(code, str) and code.startswith("WARNING_"):
        return _format_warning_observation(result)
    else:
        return _format_error_observation(result, tool_name, tool_params)
```

#### 6.2.6 `extract_status()` — 不变

```python
def extract_status(result: dict) -> str:
    code = result.get("code")
    if code == SUCCESS_CODE:
        return "warning" if result.get("warning") else "success"
    elif isinstance(code, str) and code.startswith("WARNING_"):
        return "warning"
    else:
        return "error"
```

### 6.3 各 Tool 修改

#### 6.3.1 通用规则

每个 `build_success` / `build_error` / `build_warning` 调用：
1. 有 `llm_data=` 的 → 删除 `llm_data`，改为 `result=build_result(...)`
2. 没有 `result` 的 → 增加 `result=build_result(...)`
3. 有中文 key 的 → 改为英文 key

#### 6.3.2 `file_tools.py` — 19 处

| 行号 | type | entity | metrics |
|------|------|--------|---------|
| 162 | `file_delete` | `str(path)` | — |
| 367 | `file_list` | `str(path)` | `count=total`, `preview=llm_preview[:30]` |
| 831 | `file_read` | `file_path` | `lines=line_count`, `total=total_lines`, `size=file_size`, `encoding=used_encoding` |
| 990 | `file_write` | `str(path)` | `bytes=bytes_written` |
| 1094 | `file_delete` | `str(path)` | — |
| 1183 | `file_append` | `str(path)` | `bytes=bytes_written` |
| 1448 | `file_media` | `path.name` | `mime_type=mime_type`, `size=path.stat().st_size` |
| 1504 | `file_read` | `str(fp)` | `lines=lcount`, `total=tcount`, `size=fsize`, `encoding=enc` |
| 1531 | 同 1504 | — | — |
| 1616 | `file_search` | `str(path)` | `count=len(matches)`, `matches=preview[:30]` |
| 1763 | `file_list` | `str(path)` | — |
| 1815 | `file_move` | `str(source)` | `destination=str(dst)` |
| 1908 | `file_copy` | `str(source)` | `destination=str(dst)` |
| 2006 | `file_move` | `str(source)` | `destination=str(dst)` |
| 2023 | `file_copy` | `str(source)` | `destination=str(dst)` |
| 2041 | `file_delete` | `str(source)` | — |
| 2059 | `file_rename` | `str(source)` | `new_name=str(dst)` |
| 2097 | `file_rename` | `str(source)` | `new_name=str(new_name)` |
| 2226 | `file_read` | `str(path)` | `size=st.st_size`, `encoding=enc` |

#### 6.3.3 `shell_tools.py` — `_build_shell_result()`

| 场景 | type | entity | metrics |
|------|------|--------|---------|
| 成功 | `shell_exec` | `cmd_preview` | `exit_code=0`, `stdout=stdout_info`, `stderr=stderr_info` |
| 超时 | `shell_exec` | `cmd_preview` | `ok=False`, `error_code="ERR_TIMEOUT"`, `error_hint="请增大timeout参数"` |
| 失败 | `shell_exec` | `cmd_preview` | `ok=False`, `error_code="ERR_EXEC"`, `exit_code=rc`, `stdout=stdout_info`, `stderr=stderr_info` |

#### 6.3.4 `network_tools.py` — 8 处

| 行号 | type | entity | metrics |
|------|------|--------|---------|
| 211 | `http_request` | `url` | `status_code=code`, `content_type=ct`, `body_len=len(body)` |
| 320 | `http_request` | `url` | — |
| 355 | `http_request` | `url` | — |
| 487 | `http_request` | `url` | — |
| 678 | `http_request` | `url` | — |
| 838 | `http_request` | `host` | `reachable=True/False`, `avg_latency=avg` |
| 915 | `http_request` | `host` | `reachable=True`, `port=port` |
| 918 | `http_request` | `host` | `reachable=False`, `port=port` |

#### 6.3.5 `system_tools.py` — 9 处

| 行号 | type | entity |
|------|------|--------|
| 118 | `system_info` | `info_type` |
| 227 | `event_log` | `log_name` |
| 293 | `process_list` | `"all"` |
| 410 | `service_list` | `"all"` |
| 520 | `system_info` | `"disk"` |
| 579 | `system_info` | `"os"` |
| 630 | `system_info` | `"environment"` |
| 676 | `system_info` | `"all"` |
| 714 | `system_reboot` | `"scheduled"` |

#### 6.3.6 其余工具

| 文件 | 原则 |
|------|------|
| `desktop_tools.py` | 所有 `build_success` 增加 `result=build_result(...)` |
| `desktop_gui_tools.py` | 同上 |
| `document_tools.py` | 同上，`llm_data` 全部删除，改 `result` |
| `dataanalysis_tools.py` | 同上 |
| `database_tools.py` | 同上 |
| `win_registry_tools.py` | 同上 |
| `timer_tools.py` | 同上 |
| `code_execution_tools.py` | 同上 |
| `time_tools.py` | 同上 |
| `fundamental_tools.py` | 同上 |
| `toolhelper/` | **不修改** — helper 函数被各 tool 调用，改调用者 |

---

## 七、现有格式 vs 新格式对比

### 7.1 Read File

```
当前: Observation: success - 读取文件成功: /path/file.txt (500/1000行, 12288字节, 编码:utf-8)
      【摘要】 内容=... | 原文长度=10000字符 | 行数=1000
      【数据】 {"content": "...", "total_lines": 1000, "line_count": 500, ...}

新:   Observation: SUCCESS | 读取文件成功: /path/file.txt (500/1000行, 12KB)
        file_read: /path/file.txt | lines=500 total=1000 size=12288 encoding=utf-8
```

### 7.2 Shell Exec

```
当前: Observation: success - 命令执行成功
      【摘要】 stdout=... | stderr=...
      【数据】 {"stdout": "...", "stderr": "...", "returncode": 0}

新:   Observation: SUCCESS | 命令执行成功 (exit code 0)
        shell_exec: "dir /s" | exit_code=0 stdout="(3000 chars)" stderr="(empty)"
```

### 7.3 HTTP Request

```
当前: Observation: success - 请求成功 (HTTP 200)
      【摘要】 状态码=200 | 内容类型=json | 响应体=...
      【数据】 {"status_code": 200, "headers": {...}, "body": "..."}

新:   Observation: SUCCESS | HTTP 200: https://api.example.com/users
        http_request: https://api.example.com/users | status_code=200 content_type=json body_len=5000
```

### 7.4 Error

```
当前: Observation: error [ERR_FILE_NOT_FOUND] - 文件不存在: /path/missing.txt
      请检查路径是否正确。

新:   Observation: ERROR [ERR_FILE_NOT_FOUND] | 文件不存在: /path/missing.txt
        file_read: /path/missing.txt
        > 请检查路径是否正确，可用 list_directory 查找文件
```

### 7.5 File Delete（当前无 llm_data）

```
当前: Observation: success - 文件已永久删除: /tmp/test.txt

新:   Observation: SUCCESS | 文件已永久删除: /tmp/test.txt
        file_delete: /tmp/test.txt
```

---

## 八、`data` 通道规范

### 8.1 新格式下 `data` 的职责

| 应该放 | 不应该放 |
|--------|---------|
| 完整的原始内容（文件内容、网页 HTML 等） | 与 `result` 重复的摘要信息 |
| 前端渲染所需的结构化数据（列表、树、表格） | 纯给 LLM 看的数据 |
| Base64 附件 | 关键指标统计值 |
| 分页/滚动所需的全量数据 | 状态标识（已经在 code/message 中） |

### 8.2 原则

- `data` = 给前端的原始数据（完整、无损失）
- `result` = 给 LLM 的精简结构化数据（关键指标、扁平）
- 允许部分重叠（如 `file_path` 字段），但 `result` 不包含 `data` 中的大文本

---

## 九、单元测试

### 9.1 修改现有测试

| 测试文件 | 修改点 |
|---------|--------|
| `tests/test_observation_formatter.py` | 所有 observation 文本断言，更新为新三板格式 |
| `tests/test_tool_response.py` | `build_success/error/warning` 增加 `result` 参数测试 |
| `tests/test_tool_{category}.py` | mock `build_success` 调用，增加 `result` 断言 |

### 9.2 新增测试

| 测试 | 内容 |
|------|------|
| `test_build_result()` | 正常构建、entity 空、error 场景、中文 key 拒绝 |
| `test_build_result_line()` | 各种 type+entity+metrics 组合 |
| `test_format_success_observation()` | 成功三板文本匹配 |
| `test_format_error_observation()` | 错误三板文本匹配 |
| `test_format_warning_observation()` | warning 三板文本匹配 |
| `test_metric_value_format()` | 数字/字符串/列表/None/空字符串 格式化 |

---

## 十、执行计划

| Phase | 文件 | 变更 | 时间 |
|-------|------|------|------|
| **1** | `tool_response.py` | 新增 `build_result()`，3 build 函数加 `result` 参数，删除 `llm_data` | 30min |
| **2** | `observation_formatter.py` | 修正 `build_execution_result_dict`，新三板格式化，删除旧函数 | 1h |
| **3** | `file_tools.py` | 19 处 build_success 增删改 | 40min |
| **4** | `shell_tools.py` | `_build_shell_result` + 其余 build 调用 | 20min |
| **5** | `network_tools.py` | 8 处 build 调用 | 15min |
| **6** | `system_tools.py` | 9 处 build 调用 | 15min |
| **7** | `desktop_tools.py` + `desktop_gui_tools.py` | 20+ 处 build 调用 | 40min |
| **8** | `document_tools.py` | 16+ 处 build 调用 | 30min |
| **9** | 剩余工具 | dataanalysis/database/win_registry/timer/code_exec/time/fundamental | 30min |
| **10** | 全部测试 | 更新现有测试 + 新增测试 | 1h |
| **11** | 集成验证 | 启动后端，逐个工具手动验证 | 1h |

**总估计**: 6-7h（原子操作，一次完成，不拆分批）

---

## 十一、变更文件清单

| 文件 | 变更 |
|------|------|
| `backend/app/tools/tool_response.py` | 新增 `build_result()`，3 build 函数加 `result` 参，删 `llm_data` |
| `backend/app/services/agent/observation_formatter.py` | 修复 bug + 新三板格式化 + 删除 5 个旧函数 |
| `backend/app/tools/file/file_tools.py` | 19 处修改 |
| `backend/app/tools/shell/shell_tools.py` | 12+ 处修改 |
| `backend/app/tools/network/network_tools.py` | 8 处修改 |
| `backend/app/tools/system/system_tools.py` | 9 处修改 |
| `backend/app/tools/desktop/desktop_tools.py` | 多处修改 |
| `backend/app/tools/desktop/desktop_gui_tools.py` | 多处修改 |
| `backend/app/tools/document/document_tools.py` | 16+ 处修改 |
| `backend/app/tools/dataanalysis/dataanalysis_tools.py` | 修改 |
| `backend/app/tools/database/database_tools.py` | 修改 |
| `backend/app/tools/win_registry/win_registry_tools.py` | 修改 |
| `backend/app/tools/timer/timer_tools.py` | 修改 |
| `backend/app/tools/code_execution/code_execution_tools.py` | 修改 |
| `backend/app/tools/time/time_tools.py` | 修改 |
| `backend/app/tools/fundamental/fundamental_tools.py` | 修改 |
| `backend/app/tools/toolhelper/` | **不修改** |

---

**版本**: v3.0  
**创建时间**: 2026-06-20 15:27:14  
**更新时间**: 2026-06-20 16:45:00  
**作者**: 小欧  
**批准人**: 北京老陈
