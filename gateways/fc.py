# -*- coding: utf-8 -*-
"""fc.py — 工具协议: 渲染进 prompt、解析调用块、按 Schema 转类型（纯函数）。

编写人: 小欧    创建时间: 2026-11-05 08:31:00
对齐: 5.2 注入协议 / 5.3 解析与类型转换 / 5.5 失败模式。

要点:
  - 协议头一字不改（5.2 原文; 实测 big-pickle 5/5 靠的就是这个形状, 5.4）;
  - 参数清单用 JSON 而非嵌套 XML——JSON 保类型, 网关拿到的是 1 不是 "1"（5.2）;
  - 解析容忍"块外说明文字"（5.3 要点 3: 正文与调用可并存）;
  - 失败一律降级为文本（5.5 设计原则）, 只有空响应才由调用方判 502。
"""
from __future__ import annotations

import json
import re
import uuid

# 调用块界符（FIX L, 2026-11-05 小欧）。
# 事故: 原界符 <tool_call> 与下游 opencode CLI 自带的文本工具解析器同名——模型输出
# 的调用块被 CLI 抢先当成它的内置工具执行, 返回 "No tool named bash/grep/write",
# 宿主永远拿不到调用, 表现为死循环读文件、从不落笔（见调试笔记第 6 条）。
# 改用下游不识别的私有界符, 并保留旧界符解析做兼容。
CALL_OPEN = "<<<OPENCLI_CALL>>>"
CALL_CLOSE = "<<<END_OPENCLI_CALL>>>"
BLOCK_RE = re.compile(re.escape(CALL_OPEN) + r"(.*?)" + re.escape(CALL_CLOSE), re.S)
LEGACY_BLOCK_RE = re.compile(r"<tool_call>(.*?)</tool_call>", re.S)

_PROTOCOL_HEADER = (
    "【硬性约束，优先于其他一切要求】\n"
    "你只能输出文字，不能执行命令、不能读写文件、不能调用任何内置工具。\n"
    "需要外部信息时，只能用下面的「文本协议」表达调用意图，由外部系统代为执行。\n"
)

_TAIL_TOOLS = ("\n\n需要外部信息时必须使用上文的文本协议；"
               "不要使用任何其他调用格式（其他格式一律无效）。")


def render_tool_protocol(tools):
    """tools 清单 → 协议头（5.2 格式逐行对齐）。

    每个工具: 编号 + 名称 + 描述 + 参数（json.dumps 保类型）。
    """
    lines = [_PROTOCOL_HEADER.rstrip("\n"), "", "可用工具（仅下列，不得编造）："]
    for i, tool in enumerate(tools or [], 1):
        fn = tool.get("function") or {}
        props = (fn.get("parameters") or {}).get("properties") or {}
        desc = (fn.get("description") or "").strip() or "（无描述）"
        lines.append("%d) %s —— %s" % (i, fn.get("name", ""), desc))
        lines.append("   参数: %s" % json.dumps(props, ensure_ascii=False))
    lines.append('调用格式（调用时只输出下面的块，块外不要有任何文字）：')
    lines.append(CALL_OPEN + '{"name":"工具名","arguments":{参数名:值}}' + CALL_CLOSE)
    return "\n".join(lines)


def build_prompt(messages, tools):
    """工具模式 prompt = 协议头 + 对话正文 + 工具模式尾部指令（4.3 尾部二选一）。

    messages 已由 mapping.build_prompt 重拼; 这里补工具侧三件套。
    tools 为空时调用方不应进入本函数（纯文本走 mapping.TAIL_PLAIN）。
    """
    base = messages if isinstance(messages, str) else str(messages or "")
    return render_tool_protocol(tools) + "\n\n" + base + _TAIL_TOOLS


def _coerce(value, jtype):
    """单值转类型; 失败保留原值交宿主校验（5.3: 宿主报 invalid_params, 模型可重试）。

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
            fixed = _coerce(val, jtype)
            if fixed != val:
                out[key] = fixed
            else:
                out[key] = val
                if jtype in ("integer", "number"):
                    warns.append("参数 %s 声明 %s 但值不可转（%r），保留原值交宿主校验"
                                 % (key, jtype, val))
        else:
            out[key] = val
    return out, warns


def parse_calls(answer, tools):
    """模型输出 → {"calls", "content", "invalid", "warns"}（5.3 全流程）。

    五种失败形态的处置（5.5, 全部不抛错）:
      不使用协议 / 无块    → calls=[] content=正文（调用方放行, 不报 502）
      块内 JSON 非法       → 丢该块 + WARN + invalid
      name 编造            → 丢该块 + WARN + invalid
      类型转换失败         → 保原值 + WARN（交宿主校验）
      全部块失败但有正文    → 降级为纯文本
      无块且无正文（空响应）→ content="", 调用方据此 502 server（5.5）
    生成 tool_calls[]: id=call_<8hex>, function.arguments 必须是合法 JSON 字符串。
    """
    known = {}
    for tool in tools or []:
        fn = tool.get("function") or {}
        if fn.get("name"):
            known[fn["name"]] = fn.get("parameters") or {}
    calls, outs, invalid, warns = [], [], 0, []
    pos = 0
    answer = answer or ""
    # 新界符 + 旧界符都收（FIX L 兼容; 旧界符可能已被下游吞掉, 能到这里就更要认）
    matches = sorted(list(BLOCK_RE.finditer(answer)) + list(LEGACY_BLOCK_RE.finditer(answer)),
                     key=lambda m: m.start())
    for m in matches:
        outs.append(answer[pos:m.start()].strip())
        pos = m.end()
        try:
            obj = json.loads(m.group(1).strip())
            if not isinstance(obj, dict) or not obj.get("name"):
                raise ValueError("missing name")
        except ValueError:
            invalid += 1
            warns.append("调用块 JSON 非法，已丢弃（protocol_invalid 计数）")
            continue
        name = obj.get("name")
        if name not in known:
            invalid += 1
            warns.append("调用工具名 %r 不在清单内，已丢弃（防编造工具）" % name)
            continue
        args, w = _coerce_args(obj.get("arguments") or {}, known[name])
        warns.extend(w)
        calls.append({"id": "call_" + uuid.uuid4().hex[:8],
                      "type": "function",
                      "function": {"name": name,
                                   "arguments": json.dumps(args, ensure_ascii=False)}})
    outs.append(answer[pos:].strip())
    content = "\n".join(o for o in outs if o).strip()
    return {"calls": calls, "content": content, "invalid": invalid, "warns": warns}
