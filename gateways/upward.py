# -*- coding: utf-8 -*-
"""upward.py — 向上翻译: 下游 CLI 回复 → 宿主 OpenAI tool_calls/文本/usage（纯函数）。

编写人: 小欧    创建时间: 2026-11-05 08:31:00
编辑历史:
  2026-11-05 小欧 - 按方向重排: 本文件收口全部向上翻译(调用块解析+类型转换+usage), 工具清单渲染与 1~5 段组装迁 mapping.py(向下)
  2026-11-05 三堂会审整改: parse_calls 拆出 _one_block, _coerce_args 去冗余分支 -- 小欧
  2026-11-05 14:40:16 组装序重排+协议文案重写+块内JSON容错抢救 -- 小欧
  2026-11-05 界符改回模型训练同形的 <tool_call>…</tool_call>; 老版本 </call_out> 残收尾与未闭合残块做容错+清理 -- 小欧
  2026-11-05 截断调用不再静默: 块内未闭合对象计入 protocol_invalid 并落 WARN -- 小欧
  2026-11-05 更名 fc.py→upward.py: 本文件早不只做 function calling(还管 usage 计量与正文抽取), 与 mapping(向下)成对 -- 小欧
"""
from __future__ import annotations

import json
import re
import uuid

from mapping import BLOCK_RE, CALL_OPEN    # 输出规格唯一定义在向下侧, 解析复用同一组 — 小欧 2026-11-05

_FENCE_RE = re.compile(r"^[ \t]*```[^\n]*\n?|[ \t]*```[ \t]*$")   # 块内 JSON 被代码围栏包住

# 复数包装（训练格式里多个调用包在 <tool_calls>…</tool_calls> 里）: 只剥包装壳, 不扩充单块规格
# — 小欧 2026-11-05
_WRAPPER_RE = re.compile(r"</?tool_calls\s*>", re.I)


def usage_from_counts(counts):
    """驱动提供的原始计数 → OpenAI usage（缺失返回 None, 绝不填 0）。

    prompt_tokens     = input + cached + written   （样例 125+7424+0 → 7549）
    completion_tokens = output + reasoning         （样例 56+17 → 73）
    计量字段的"名字与来源"是下游细节（驱动 token_counts 计）; "算式"是
    上游计量事实（通用计）。下游把非缓存输入与缓存命中分开计量, 只取 input
    会少报 98%——必须按算式相加。
    """
    if not counts:
        return None
    prompt = int(counts["input"]) + int(counts["cached"]) + int(counts["written"])
    completion = int(counts["output"]) + int(counts["reasoning"])
    return {"prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "prompt_tokens_details": {"cached_tokens": int(counts["cached"])}}


def _coerce(value, jtype):
    """单值转类型; 失败保留原值交宿主校验（宿主报 invalid_params, 模型可重试）。

    boolean 的坑: bool("false") is True——必须显式按字面判。
    """
    try:
        if jtype == "integer":
            return int(value)
        if jtype == "number":
            return float(value)
        if jtype == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("1", "true", "yes", "y")
        if jtype == "string":
            return str(value)
    except (TypeError, ValueError):
        return value
    return value                     # array/object 直接采用（已是 JSON 值）; 无类型声明同


def _coerce_args(args, schema):
    """按 tools[i].function.parameters 逐参数转类型。返回 (args, warns)。"""
    out, warns = {}, []
    props = (schema or {}).get("properties") or {}
    for key, val in dict(args or {}).items():
        jtype = ((props.get(key) or {"type": ""}).get("type")) or ""
        if jtype in ("integer", "number", "boolean", "string"):
            val = _coerce(val, jtype)
        out[key] = val
        if jtype in ("integer", "number") and not isinstance(val, (int, float)):
            warns.append("参数 %s 声明 %s 但值不可转（%r），保留原值交宿主校验"
                         % (key, jtype, val))
    return out, warns


def _brace_end(frag, start):
    """从 start 处的 '{' 起做字符串感知配对。

    返回 (配对 '}' 的下标或 -1, 未闭合层数, 是否停在字符串内) — 小欧 2026-11-05
    """
    depth, in_str, esc = 0, False, False
    for j in range(start, len(frag)):
        ch = frag[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return j, 0, False
    return -1, depth, in_str


def _objects(fragment):
    """抠出全部完整 JSON 对象 → (列表, 截断未闭合数); 截断的绝不执行但要计数 — 小欧 2026-11-05"""
    frag = fragment or ""
    out, pos, dropped = [], 0, 0
    while True:
        start = frag.find("{", pos)
        if start < 0:
            return out, dropped
        end, _depth, _in_str = _brace_end(frag, start)
        if end < 0:
            dropped += 1                # 写了一半的调用: 丢掉, 但不能静默
            pos = start + 1             # 跳过它的 '{', 后面完整对象照收
            continue
        try:
            obj = json.loads(frag[start:end + 1])
        except ValueError:
            pos = start + 1             # 这段不是 JSON, 从下一个 { 再试
            continue
        if isinstance(obj, dict) and obj:
            out.append(obj)
        pos = end + 1


def _loads_balanced(fragment):
    """块内 JSON 容错抢救: 括号配对完整提取 + 截断修补 — 小欧 2026-11-05

    步骤1字符串感知配对（引号内大括号不计深度）截取完整 JSON;
    步骤2未配平时按扫描终态截断修补: 补右括号至未闭合层数, 停在字符串内补闭引号
    （吸收宿主 json_utils 截断修补思想, 但按嵌套深度补齐——老实现只逐个试尾部）。
    返回 dict 或 None。
    """
    frag = (fragment or "").strip()
    start = frag.find("{")
    if start < 0:
        return None
    end, depth, in_str = _brace_end(frag, start)
    if end >= 0:
        try:
            obj = json.loads(frag[start:end + 1])
            return obj if isinstance(obj, dict) and obj else None
        except ValueError:
            return None
    # 未配平 = 写了一半: 补右括号至未闭合层数, 停在字符串内先补闭引号
    base = frag[start:] + ('"' if in_str else "")
    for pre in ("", '"', "]"):
        for k in (depth, depth + 1):
            try:
                obj = json.loads(base + pre + "}" * k)
                return obj if isinstance(obj, dict) and obj else None
            except ValueError:
                continue
    return None


def _flatten(objs):
    """信封/原生形状摊平: {"tool_calls":[…]}、{"calls":[…]}、{"function":{…}} → 调用对象
    — 小欧 2026-11-05
    """
    out = []
    for obj in objs:
        items = []
        for key in ("tool_calls", "calls"):
            if isinstance(obj.get(key), list):
                items = [x for x in obj[key] if isinstance(x, dict)]
                break
        if items:
            out.extend(_flatten(items))     # 信封可能还套信封
            continue
        if not obj.get("name") and isinstance(obj.get("function"), dict):
            obj = obj["function"]           # 原生 tool_calls 形状: name/arguments 在 function 里
        out.append(obj)
    return out


def _one_block(raw, known):
    """单个调用块 → (calls, invalid 增量, warns); 块内允许多个工具连续排布。— 小欧 2026-11-05"""
    warns = []
    raw = _FENCE_RE.sub("", raw or "").strip()      # 兼容: 剥掉块内多余代码围栏
    objs, dropped = _objects(raw)                   # 一个块塞多个 tool: 逐个收
    if not objs:
        obj = _loads_balanced(raw)                  # 括号配对先抢救再丢
        if not obj:
            return [], 1, ["调用块 JSON 非法，已丢弃（protocol_invalid 计数）"]
        objs, dropped = [obj], 0                    # 抢救成功: 截断不算丢
        warns.append("块内 JSON 非法，已按括号配对抢救成功")
    calls, invalid = [], dropped
    if dropped:
        warns.append("块内 %d 处 JSON 未闭合，已丢弃（protocol_invalid 计数）" % dropped)
    for obj in _flatten(objs):
        name = obj.get("name")
        if not name:
            invalid += 1
            warns.append("调用块缺 name，已丢弃")
            continue
        if name not in known:
            invalid += 1
            warns.append("调用工具名 %r 不在清单内，已丢弃（防编造工具）" % name)
            continue
        raw_args = obj.get("arguments")
        if raw_args is None:
            raw_args = {}                # 缺 arguments 视为空参, 交宿主校验必填
        elif not isinstance(raw_args, dict):
            invalid += 1
            warns.append("arguments 不是对象（%s），已丢块" % type(raw_args).__name__)
            continue
        args, w = _coerce_args(raw_args, known[name])
        warns.extend(w)
        calls.append({"id": "call_" + uuid.uuid4().hex[:8],
                      "type": "function",
                      "function": {"name": name,
                                   "arguments": json.dumps(args, ensure_ascii=False)}})
    return calls, invalid, warns


def parse_calls(answer, tools):
    """模型输出 → {"calls", "content", "invalid", "warns"}。

    失败形态一律不抛错:
      不使用协议 / 无块    → calls=[] content=正文（调用方放行, 空响应才判 502）
      块内 JSON 非法       → 先括号配对+截断抢救, 抢不回才丢, WARN + invalid
      块内对象未闭合       → 完整的那几个照收, 截断的丢弃, WARN + invalid（绝不执行半截参数）
      name 编造            → 丢该块 + WARN + invalid
      类型转换失败         → 保原值 + WARN（交宿主校验）
      全部块失败但有正文    → 降级为纯文本
      无块且无正文（空响应）→ content="", 调用方据此 502 server
    生成 tool_calls[]: id=call_<8hex>, function.arguments 必须是合法 JSON 字符串。
    一个块里连续排多个工具时逐个提取成多条 tool_calls; <tool_calls> 复数包装只剥壳。
    """
    known = {}
    for tool in tools or []:
        fn = tool.get("function") or {}
        if fn.get("name"):
            known[fn["name"]] = fn.get("parameters") or {}
    calls, outs, invalid, warns = [], [], 0, []
    pos = 0
    answer = _WRAPPER_RE.sub("", answer or "")   # 剥掉 <tool_calls> 复数包装壳
    for m in BLOCK_RE.finditer(answer):
        outs.append(answer[pos:m.start()].strip())
        pos = m.end()
        found, bad, w = _one_block(m.group(1), known)
        calls.extend(found)
        invalid += bad
        warns.extend(w)
    # 未闭合残块（老版本漏到 UI 的 <tool_call>{… 无收尾）: 先按截断抢救, 抢不回就整段丢弃,
    # 绝不把界符原样透给宿主 UI — 小欧 2026-11-05
    tail = answer[pos:]
    cut = tail.find(CALL_OPEN)
    if cut >= 0:
        outs.append(tail[:cut].strip())
        found, bad, w = _one_block(tail[cut + len(CALL_OPEN):], known)
        calls.extend(found)
        invalid += bad
        warns.extend(w)
    else:
        outs.append(tail.strip())
    content = "\n".join(o for o in outs if o).strip()
    return {"calls": calls, "content": content, "invalid": invalid, "warns": warns}
