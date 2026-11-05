# -*- coding: utf-8 -*-
"""upward.py — 向上翻译: 下游 CLI 回复 → 宿主 OpenAI tool_calls/文本/usage（纯函数）。

编写人: 小欧    创建时间: 2026-11-05 08:31:00
编辑历史:
  2026-11-05 按方向重排: 本文件收口全部向上翻译(调用块解析+类型转换+usage) -- 小欧
  2026-11-05 parse_calls 拆出 _one_block, _coerce_args 去冗余分支 -- 小欧
  2026-11-05 组装序重排 + 协议文案重写 + 块内 JSON 容错抢救 -- 小欧
  2026-11-05 界符改回训练同形; </call_out> 残收尾与未闭合残块做容错清理 -- 小欧
  2026-11-05 截断调用不再静默: 块内未闭合对象计入 protocol_invalid 并落 WARN -- 小欧
  2026-11-05 更名 upward.py: 还管 usage 计量与正文抽取, 与 mapping(向下)成对 -- 小欧
  2026-11-05 复数壳内裸对象原被剥标记后当正文泄漏; 改壳内先按块解析再清标记 -- 小欧
  2026-11-05 注释规范化: 压缩到两行内并统一署名日期 -- 小欧
"""
from __future__ import annotations

import json
import re
import uuid

from mapping import BLOCK_RE, CALL_OPEN    # 输出规格唯一定义在向下侧, 解析复用同一组 — 小欧 2026-11-05

_FENCE_RE = re.compile(r"^[ \t]*```[^\n]*\n?|[ \t]*```[ \t]*$")   # 块内 JSON 被代码围栏包住

# 复数包装: 训练格式把多个调用包在 <tool_calls>…</tool_calls> 里, 壳内按块解析 — 小欧 2026-11-05
_WRAPPER_RE = re.compile(r"</?tool_calls\s*>", re.I)
_CALLS_RE = re.compile(r"<tool_calls\s*>(.*?)</tool_calls\s*>", re.S | re.I)
_CALLS_OPEN = "<tool_calls>"


def usage_from_counts(counts):
    """驱动原始计数 → OpenAI usage（缺失返回 None, 绝不填 0）。
    prompt=input+cached+written, completion=output+reasoning。— 小欧 2026-11-05"""
    if not counts:
        return None
    prompt = int(counts["input"]) + int(counts["cached"]) + int(counts["written"])
    completion = int(counts["output"]) + int(counts["reasoning"])
    return {"prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": prompt + completion,
            "prompt_tokens_details": {"cached_tokens": int(counts["cached"])}}


def _coerce(value, jtype):
    """单值转类型, 失败保留原值; boolean 按字面判(bool("false") 为 True)。— 小欧 2026-11-05"""
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
    """按 tools[i].function.parameters 逐参数转类型。返回 (args, warns)。— 小欧 2026-11-05"""
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
    """从 start 处 '{' 起字符串感知配对 → (配对下标或 -1, 未闭合层数, 是否停在串内)。— 小欧 2026-11-05"""
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
    """块内 JSON 容错抢救: 字符串感知配对截取完整 JSON, 未配平按嵌套深度补齐右括号。
    返回 dict 或 None。— 小欧 2026-11-05"""
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
    """信封/原生形状摊平: {"tool_calls":[…]}、{"calls":[…]}、{"function":{…}} → 调用对象 — 小欧 2026-11-05"""
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


def _first_open(text):
    """最早出现的块开口 → (下标, 开口长度) 或 (-1, 0); 兼容单块与复数壳（截断残形）。"""
    best = (-1, 0)
    for token in (CALL_OPEN, _CALLS_OPEN):
        idx = text.find(token)
        if idx >= 0 and (best[0] < 0 or idx < best[0]):
            best = (idx, len(token))
    return best


def parse_calls(answer, tools):
    """模型输出 → {"calls", "content", "invalid", "warns"}; 失败形态一律不抛错。
    无块则放行正文; JSON 非法/未闭合/编造工具名计入 invalid 并落 WARN。— 小欧 2026-11-05"""
    known = {}
    for tool in tools or []:
        fn = tool.get("function") if isinstance(tool, dict) else None
        fn = fn if isinstance(fn, dict) else {}
        if fn.get("name"):
            known[fn["name"]] = fn.get("parameters") or {}
    calls, outs, invalid, warns = [], [], 0, []
    answer = answer or ""
    # 复数壳先整体成块: 壳内裸对象/多对象都能解析; 只有解析出调用才摘除该段,
    # 未解析成功时退回老口径(仅清标记, 正文保留) — 小欧 2026-11-05
    for m in _CALLS_RE.finditer(answer):
        found, bad, w = _one_block(m.group(1), known)
        if found:
            calls.extend(found)
            invalid += bad
            warns.extend(w)
            answer = answer.replace(m.group(0), "", 1)
    answer = _WRAPPER_RE.sub("", answer)   # 剥掉残余 <tool_calls> 标记
    pos = 0
    for m in BLOCK_RE.finditer(answer):
        outs.append(answer[pos:m.start()].strip())
        pos = m.end()
        found, bad, w = _one_block(m.group(1), known)
        calls.extend(found)
        invalid += bad
        warns.extend(w)
    # 未闭合残块（老版本漏到 UI 的 <tool_call>{… 无收尾, 或 <tool_calls> 被截断）:
    # 先按截断抢救, 抢不回就整段丢弃, 绝不把界符原样透给宿主 UI — 小欧 2026-11-05
    tail = answer[pos:]
    cut, span = _first_open(tail)
    if cut >= 0:
        outs.append(tail[:cut].strip())
        found, bad, w = _one_block(tail[cut + span:], known)
        calls.extend(found)
        invalid += bad
        warns.extend(w)
    else:
        outs.append(tail.strip())
    content = "\n".join(o for o in outs if o).strip()
    return {"calls": calls, "content": content, "invalid": invalid, "warns": warns}
