# -*- coding: utf-8 -*-
"""
allowlist — 免口令 IP 白名单的语法单一权威（写侧落盘校验/归一 与 读侧准入匹配 共用）。

为何独立成模块：白名单语法此前在写侧（保存）与读侧（准入判定）各写一套，
必然漂移，且两边都是静默失败 —— 写侧放行的值读侧可能拒认，反之亦然，
用户只看到"保存成功"却拿不到免口令，或反之。本模块把归一/校验/匹配收在一处。

放 app/utils 而非 app/services：纯 ipaddress 实现，不依赖配置/服务/DB。
api 层 deps.py 要用它，若放 services 会经 app/services/__init__ 拉起
lifecycle→db→logger 整条链，给低层模块引入循环导入风险。

编辑历史:
  2026-09-27 小欧 - 新建：normalize/invalid_entries/matches 三个函数，
    供 settings_service（落盘前归一+校验）与 deps（逐请求匹配）共用。
"""
import ipaddress
from typing import Any, List, Union

RawAllowlist = Union[str, List[Any], None]

# 分隔符含全角与换行：控件是多行文本框，用户会敲回车；只认逗号/分号时，
# 回车分隔的整段被当成一条 → 解析失败 → 整段作废。
_SEPARATORS = ",;\n\r，；"
_SPLIT_TOKEN = "\x00"  # 配置值内不可能出现的占位符


def normalize(raw: RawAllowlist) -> List[str]:
    """任意来源形态 → 干净条目列表。落盘恒为 list，形状不因用户用什么分隔符而变。"""
    if raw is None:
        return []
    parts = raw if isinstance(raw, list) else [raw]
    out: List[str] = []
    for part in parts:
        text = str(part)
        for ch in _SEPARATORS:
            text = text.replace(ch, _SPLIT_TOKEN)
        for piece in text.split(_SPLIT_TOKEN):
            piece = piece.strip()
            if piece:
                out.append(piece)
    return out


def _parse_entry(entry: str):
    """含 '/' 按 CIDR 解析，否则按单 IP 解析；非法返回 None。"""
    try:
        if "/" in entry:
            return ipaddress.ip_network(entry, strict=False)
        return ipaddress.ip_address(entry)
    except ValueError:
        return None


def invalid_entries(raw: RawAllowlist) -> List[str]:
    """非法条目原文，供落盘前报错。

    落盘侧此前只校验值类型（是不是文本），192.168.1.0/33（掩码越界）、abc 这类值
    照样保存成功、页面照样显示已配置，而读侧解析失败静默跳过 → 白名单永不命中，
    用户只看到莫名 401，无从判断是自己写错。校验与匹配共用 _parse_entry，规则同源。
    """
    return [e for e in normalize(raw) if _parse_entry(e) is None]


def matches(ip: str, raw: RawAllowlist) -> bool:
    """来源 IP 是否命中白名单。

    fail-closed 三条（任一不满足即不命中，绝不因配置错误而放行或全站失守）：
      ① 来源 IP 缺失或非法 ② 白名单为空 ③ 单条条目非法（跳过该条，其余照常生效）
    """
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in normalize(raw):
        parsed = _parse_entry(entry)
        if parsed is None:
            continue
        if isinstance(parsed, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
            if addr in parsed:
                return True
        elif parsed == addr:
            return True
    return False
