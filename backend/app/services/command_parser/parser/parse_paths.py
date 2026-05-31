# -*- coding: utf-8 -*-
"""
parse_paths — 从 parser.py 拷出

拷贝来源: parser.py 第78-106行
"""

import re
from typing import List, Dict


def parse_paths(command: str, cn_patterns: list, en_patterns: list) -> Dict[str, List[str]]:
    """拷贝自 parser.py 第78-106行"""
    sources, targets = [], []
    for pattern, ptype in cn_patterns:
        match = re.search(pattern, command)
        if match:
            src = match.group(1).strip()
            tgt = match.group(2).strip() if match.lastindex >= 2 else ''
            if src: sources.append(src)
            if tgt: targets.append(tgt)
            return {'sources': sources, 'targets': targets}
    for pattern, ptype in en_patterns:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            src = match.group(1).strip()
            tgt = match.group(2).strip() if match.lastindex >= 2 else ''
            if src: sources.append(src)
            if tgt: targets.append(tgt)
            return {'sources': sources, 'targets': targets}
    parts = command.split()
    if len(parts) >= 2:
        cmd_words = ['cp', 'copy', 'mv', 'move', 'rm', 'del', 'cat', 'mkdir', 'touch', 'echo']
        found_cmd = False
        for part in parts:
            if part.lower() in cmd_words:
                found_cmd = True; continue
            if found_cmd:
                if not sources: sources.append(part)
                elif not targets: targets.append(part)
    return {'sources': sources, 'targets': targets}
