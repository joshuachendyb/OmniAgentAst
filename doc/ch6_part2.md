
### 6.3 `_create_action_result_from_dict` — `react_output_parser.py:1128` (101行)

**当前规模**: 101 行 | **文件位置**: `backend/app/services/agent/react_output_parser.py:1128`

#### 6.3.1 当前结构拆解

`_create_action_result_from_dict` 实际函数体仅 ~20 行（1128-1148），其余 ~80 行（1149-1228）为游离的列表处理代码（缺 `def` 定义）。

**实际函数结构（1128-1148）**，共 5 个决策点：

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **V1 输入校验** | V1a | data 为空/非 dict | _make_action_result_dict parse_error | 1133-1134 | 中层校验 |
| **T1 类型分发** | T1a | type == "parse_error" | _build_parse_error_result | 1137-1138 | 中层分发 |
| | T1b | type == "answer" | _build_answer_result | 1139-1140 | 中层分发 |
| | T1c | type == "chunk" | _build_chunk_result | 1141-1142 | 中层分发 |
| **O1 旧格式检测** | O1a | "action" in data 且 "tool_name" 不在 | _build_action_from_old_format | 1144-1146 | 中层兼容 |
| **R1 最终解析** | R1a | 默认 | _resolve_return_type | 1148 | 中层分发 |

**游离列表处理代码（1149-1228）**，共 5 个决策点：

| 决策层 | 分支 | 条件 | 处理 | 行号 |
|-------|------|------|------|------|
| **E1 空数组** | E1a | data 为空 list | 返回 parse_error | 1160-1171 |
| **V2 有效元素** | V2a | 无有效 dict | 返回 parse_error | 1177-1188 |
| **C2 取最后一个** | C2a | 默认 | valid_items[-1] | 1191 |
| **F1 Function Calling** | F1a | Function Calling 格式 | 全部转换 + 取最后一个 | 1196-1226 |
| **R2 递归** | R2a | 取最后一个 | 递归调用 _create_action_result_from_dict | 1228 |

**重复/冗余**:
- parse_error 的返回 dict（4 次：1133-1134、1162-1171、1179-1188、同名 `_make_action_result_dict`）— 至少 3 份重复
- Function Calling 格式的遍历+转换（1196-1211）写为内联 ~15 行，可提取辅助函数
- 空数组和无效 dict 的 parse_error 返回结构完全一致，但分散在两处独立 if 块

#### 6.3.2 违反原则分析

- **DRY 严重违反**: parse_error 的 9 字段 dict 重复构建 4 次。Function Calling 转换 15 行内联。
- **SLAP 基本遵守**: 类型分发模式清晰，各分支职责明确。
- **SRP 中度违反**: dict 处理 + list 处理 + Function Calling 转换共 3 个职责不应在同一个作用域。
- **KISS 轻度违反**: list 处理部分缺少函数定义，游离在模块级，增加理解难度。
- **架构缺陷**: list 处理代码缺少函数定义（`def`），导致 101 行被错误归入 `_create_action_result_from_dict`。

#### 6.3.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_make_action_result_dict` | `react_output_parser.py` ✅ | 已有 |
| `_build_parse_error_result` | `react_output_parser.py` ✅ | 已有 |
| `_build_answer_result` | `react_output_parser.py` ✅ | 已有 |
| `_build_chunk_result` | `react_output_parser.py` ✅ | 已有 |
| Function Calling 转换 | 无 | 建议提取为 `_convert_function_calling_items(items)` |

#### 6.3.4 重构方案（详细代码设计）

**目标**: 补全缺失的 `def` 定义 + 消除 parse_error dict 重复 + 提取 Function Calling 转换。

**组件1: 补全 `_create_action_result_from_list`** — 将游离列表处理代码包装为函数

```python
def _create_action_result_from_list(data: List) -> Dict[str, Any]:
    """从 list 输入创建统一格式的结果（原游离模块级代码）。"""
    if not data:
        return _make_action_result_dict("parse_error", "", "", "", None, None, "", "Empty list input from LLM")

    valid_items = [item for item in data if isinstance(item, dict)]
    if not valid_items:
        return _make_action_result_dict("parse_error", "", "", "", None, None, "", "No valid dict items in list")

    last_item = valid_items[-1]

    # Function Calling 格式检测
    if "tool_name" not in valid_items[0] and "function" in valid_items[0]:
        converted = _convert_function_calling_items(valid_items)
        last_converted = converted[-1]
        last_item = {
            "tool_name": last_converted["name"], "tool_params": last_converted["args"],
            "content": last_item.get("content", ""),
            "thought": last_item.get("thought", last_item.get("content", "")),
            "reasoning": last_item.get("reasoning", ""),
        }
        if len(converted) > 1:
            last_item["_pending_calls"] = converted[:-1]

    logger.info(f"[parse_react_response] list解析成功，使用最后一个元素")
    return _create_action_result_from_dict(last_item)
```

**组件2: `_convert_function_calling_items`** — 提取 Function Calling 转换

```python
def _convert_function_calling_items(items: List[Dict]) -> List[Dict]:
    """转换 Function Calling 格式为统一格式。"""
    converted = []
    for item in items:
        if isinstance(item, dict) and "function" in item:
            func = item["function"]
            fname = func.get("name", "") if isinstance(func, dict) else ""
            fargs_str = func.get("arguments", "{}") if isinstance(func, dict) else "{}"
            try:
                fargs = json.loads(fargs_str) if isinstance(fargs_str, str) else (fargs_str or {})
            except (json.JSONDecodeError, TypeError):
                fargs = {}
            converted.append({"name": fname, "args": fargs})
        else:
            converted.append(item)
    return converted
```

**优势**: 补全函数定义，将 101 行分解为 3 个独立函数。消除 parse_error dict 的 3 份重复（统一使用 `_make_action_result_dict`）。Function Calling 转换 15 行提取为可测试函数。

---

### 6.4 `fetch_webpage` — `network_tools.py:380` (101行)

**当前规模**: 101 行 | **文件位置**: `backend/app/services/tools/network/network_tools.py:380`

#### 6.4.1 当前结构拆解

`fetch_webpage` 实现网页内容获取（URL校验+Playwright/httpx双路径+结果构建），共 9 个决策点：

**调用路径**: `LLM意图` → `fetch_webpage(url, prompt, extract_format, js_render, ...)` → httpx/Playwright → `_extract_html_content`

| 决策层 | 分支 | 条件 | 处理 | 行号 | 抽象层次 |
|-------|------|------|------|------|---------|
| **U1 URL校验** | U1a | _validate_url 失败 | ERR_INVALID_URL | 393-395 | 中层校验 |
| **N1 网络检查** | N1a | _check_network 失败 | ERR_NETWORK_DOWN | 397-399 | 中层校验 |
| **H1 请求头** | H1a | 固定 | User-Agent + Accept + Language + Encoding | 401-406 | 低层配置 |
| **J1 Playwright** | J1a | js_render=True | _fetch_via_playwright | 408-416 | 低层IO |
| **H2 httpx** | H2a | js_render=False | httpx.AsyncClient.get | 418-443 | 低层IO |
| | H2b | status==403 + cf-mitigated | 降级 UA 重试 | 425-429 | 低层IO |
| | H2c | image/pdf 响应 | _build_media_result | 435-437 | 中层分发 |
| **E1 提取** | E1a | html_content | _extract_html_content | 442 | 低层数据处理 |
| **R1 结果构建** | R1a | prompt 非空 | 添加 prompt + note | 454-456 | 中层数据处理 |
| | R1b | content > 5000 | 截断 + 提示原文长度 | 459-460 | 中层数据处理 |
| **X1 异常** | X1a | httpx.TimeoutException | ERR_NETWORK_TIMEOUT | 472-473 | 中层错误 |
| | X1b | httpx.HTTPStatusError | ERR_NETWORK_HTTP_ERROR | 474-475 | 中层错误 |
| | X1c | httpx.RequestError | ERR_NETWORK_REQUEST_ERROR | 476-477 | 中层错误 |
| | X1d | Exception | ERR_NET_UNKNOWN | 478-480 | 中层异常 |

**重复/冗余**:
- 代理配置（421）与 `http_request` 代理配置重复 — `_resolve_proxy` 可消除
- 请求头构建（401-406）与 `http_request` 的 headers 构建模式相似
- URL校验 + 网络检查 + httpx 异常处理 3 层与 `http_request` 完全重复

#### 6.4.2 违反原则分析

- **DRY 中度违反**: 代理配置 + URL校验 + 网络检查 + httpx 异常处理与 `http_request` 重复 20+ 行。
- **SLAP 基本遵守**: URL校验(中层) → 双路径分发(中层) → 数据提取(低层) → 结果构建(中层)，层次清晰。
- **SRP 中度违反**: URL校验 + 网络检查 + Playwright + httpx + 提取 + 结果构建共 6 个职责。
- **KISS 基本遵守**: js_render 分支清晰，httpx 分支的 Cloudflare 降级处理可读性好。

#### 6.4.3 可复用性检查

| 当前片段 | 可复用来源 | 说明 |
|---------|-----------|------|
| `_validate_url` | `network_tools.py:22` ✅ | 已有 — 与 http_request 共享 |
| `_check_network` | `network_tools.py:54` ✅ | 已有 — 与 http_request 共享 |
| `_fetch_via_playwright` | `network_tools.py` ✅ | 已有模块级函数 |
| `_extract_html_content` | `network_tools.py` ✅ | 已有模块级函数 |
| 代理配置 | 与 http_request 重复 | 复用 `_resolve_proxy`（5.5.4 组件1）|
| httpx 异常处理 | 与 http_request 重复 | 可复用 `_build_http_error` 模式 |

#### 6.4.4 重构方案（详细代码设计）

**目标**: 101 行 → ~80 行主函数，复用 `_resolve_proxy` 消除代理配置重复。

**组件1: 重构后的 `fetch_webpage`**（~80 行）

```python
async def fetch_webpage(url, prompt=None, extract_format="markdown",
                         js_render=False, timeout=30000, max_tokens=8000, proxy=None) -> dict:
    timeout_sec = timeout / 1000.0
    try:
        url_info = _validate_url(url)
        if not url_info["data"]["valid"]:
            return build_error("ERR_INVALID_URL", f"URL格式无效: {url}")
        net_info = _check_network()
        if not net_info["data"]["connected"]:
            return build_error("ERR_NETWORK_DOWN", "网络不可用")

        headers = {"User-Agent": BROWSER_USER_AGENT,
                   "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                   "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
                   "Accept-Encoding": "gzip, deflate"}

        if js_render:
            pw_result = await _fetch_via_playwright(url, proxy, timeout_sec, extract_format, max_tokens)
            if "code" in pw_result: return pw_result
            html_content = pw_result["html_content"]
            extracted_content = pw_result["extracted_content"]
            truncated = pw_result["truncated"]
            content_type = pw_result["content_type"]
            status_code = pw_result["status_code"]
        else:
            async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_sec),
                follow_redirects=True, proxy=_resolve_proxy(proxy)) as client:
                response = await client.get(url, headers=headers)
                if response.status_code == 403 and response.headers.get("cf-mitigated") == "challenge":
                    logger.info(f"[fetch_webpage] Cloudflare挑战检测，降级UA重试: {url}")
                    response = await client.get(url, headers=headers)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                mime = content_type.split(";")[0].strip().lower() if content_type else ""
                if mime and (mime.startswith("image/") or mime in ("application/pdf",)):
                    return _build_media_result(url, mime, response.content, extract_format, response.status_code)
                html_content = response.text
                content_type = response.headers.get("content-type", "")
            extracted_content, truncated = _extract_html_content(html_content, extract_format, max_tokens)
            status_code = response.status_code

        result_data = {"url": url, "content": extracted_content, "format": extract_format,
                       "content_type": content_type, "status_code": status_code, "truncated": truncated}
        if prompt:
            result_data["prompt"] = prompt; result_data["note"] = "AI提取功能需要LLM后处理"

        preview = result_data.get("content", "")
        if isinstance(preview, str) and len(preview) > 5000:
            preview = preview[:5000] + f"...(原文{len(preview)}字符)"

        return build_success(truncate_data_for_frontend(result_data),
            f"成功获取网页内容（{extract_format}格式）" + ("（已截断）" if truncated else ""),
            llm_data={"URL": url, "格式": extract_format, "状态码": result_data.get("status_code"),
                      "内容预览": preview, "截断": truncated},
            next_actions=build_next_actions([("search_web", "搜索更多网页", "需要搜索更多信息时")]))

    except httpx.TimeoutException:
        return build_error("ERR_NETWORK_TIMEOUT", f"获取网页超时（{timeout_sec:.1f}秒）：{url}")
    except httpx.HTTPStatusError as e:
        return build_error("ERR_NETWORK_HTTP_ERROR", f"获取网页失败 (HTTP {e.response.status_code})：{url}")
    except httpx.RequestError as e:
        return build_error("ERR_NETWORK_REQUEST_ERROR", f"网络请求失败：{str(e)}")
    except Exception as e:
        logger.error(f"[fetch_webpage] 未知错误: {e}")
        return build_error("ERR_NET_UNKNOWN", f"获取网页异常: {str(e)}")
```

**优势**: 101 行 → ~80 行。复用 `_resolve_proxy`（5.5.4 组件1）消除代理配置重复。Cloudflare 降级重试中的 `simple_headers` 中间变量已消除（直接用同一 headers）。

---

