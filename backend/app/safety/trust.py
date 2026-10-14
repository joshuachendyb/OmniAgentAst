# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 - 新建: trust 三合一提取下沉, 解环 action_handler → trust 单向依赖 - 小健-2026-09-04
# 2026-09-16 小欧 - 问题修复(文档落码): extract_trust_path 补非文件信任域专用提取 —— 仅认规范 path 及
#   定向别名(key_path/registry_key/db_path → path), 排除 data→value 非路径别名污染; 不动 _parse_paths
#   (保护 conflict_detector 并查集分组); 与 FILE 流程共用 PARAM_ALIASES 只取规范 path — 小欧-2026-09-16
# 2026-10-06 - 小欧 - save_session_trust 落库日志补 raw_path 与「登记范围」两字段: 原先只打 tool_name,
#   实际登记的是文件还是目录从日志无从判断, 「信任4次仍反复弹窗」正是因此长期查不出根因。
#   落库侧粒度修复见 app/safety/trust_db.py trust_scope_path。 — 小欧-2026-10-06
# 2026-10-14 - 小欧 - SA2标注: 本文件=权限信任框架SA2(会话信任预查resolve_skip/check_session_trust,执行第2步,上游SA1下游SA3) — 小欧-2026-10-14
# 2026-10-14 - 小欧 - 文档[33] 4.11-B/4.11-C: WINDOW_TARGET_TOOLS 迁 tool_constants, _parse_paths 迁 conflict_detector; 本模块旧定义删改由 import 解析(不留双份)
# 2026-10-14 - 小欧 - 文档[33] 4.2: 本文件由 app/tools/trust.py 迁入 app/safety/(业务逻辑一字不改); 模块内 3 处 app.tools.trust_db 延迟导入改同包 app.safety.trust_db。
# 2026-10-14 - 小欧 - 文档[33] 4.2/步9: 本文件由 app/tools/trust.py 迁入 app/safety/; 模块内 3 处 app.tools.trust_db 延迟导入改同包 app.safety.trust_db; 旧文件已删(不留双份)。
# 2026-10-15 - 小欧 - 文档[33] 5.12 核查订正: 删 3 个死导入 Set/FILE_OPERATION_TOOLS/WINDOW_TARGET_TOOLS。
#   病根: 5.5 把 _parse_paths 迁往 conflict_detector 后, 这三者在本模块均无消费方
#   (AST 实证代码与注解皆未引用)。其中 Set 设计 5.12 明文要求删, 而
#   WINDOW_TARGET_TOOLS 系实施时多补的 import(设计只要求删本地定义, 未要求新增 import)。
#   剩余 Dict/Optional/PARAM_ALIASES/normalize_tool_name/NON_FILE_TRUST_TOOLS/_parse_paths 均有真实引用。— 小欧-2026-10-15
# 2026-10-14 - 小欧 - 文档[33] 4.2: 本文件由 app/tools/trust.py 迁入 app/safety/(业务逻辑一字不改); 模块内 3 处 app.tools.trust_db 延迟导入改同包 app.safety.trust_db。
"""
trust — 信任域三合一: 路径解析 + 信任路径提取 + 信任跳过判定 + 信任落库

从 action_handler.py 提取:
- _parse_paths: 路径/窗口冲突键解析（纯函数）
- extract_trust_path: 信任落库/查询的目标路径提取（纯函数）
- resolve_skip: 会话级信任查询, 决定是否跳过HITL确认（async）

从 hitl_confirmation.py 提取:
- save_session_trust: 用户确认后将工具+路径写入会话信任记录（async）

原则: 完整复制, 保留原始功能分支和逻辑, 禁止简化退化
"""
from typing import Dict, Optional
from app.tools.tools_alias_mapper import PARAM_ALIASES, normalize_tool_name
from app.tools.tool_constants import NON_FILE_TRUST_TOOLS
# 2026-10-14 小欧 - 文档[33] 4.11-B/4.11-C: WINDOW_TARGET_TOOLS 归 tool_constants,
#   _parse_paths 归 conflict_detector。本模块旧定义已删, 改由 import 解析(不留双份)。
from app.tools.conflict_detector import _parse_paths


# ════════════════════════════════════════════════════════════
# 纯函数：路径解析（迁至 app/tools/conflict_detector.py — 文档[33] 4.11-C）
# ════════════════════════════════════════════════════════════
# 2026-10-14 小欧 - 原 _parse_paths 定义已迁至 conflict_detector; 本模块仍需它故 import 之(同一对象)。


# ════════════════════════════════════════════════════════════
# 纯函数：信任路径提取（复制自 action_handler.py:581-587）
# ════════════════════════════════════════════════════════════

def extract_trust_path(name: str, params: Dict) -> Optional[str]:
    """提取工具调用用于信任落库/查询的目标路径(复用 _parse_paths, DRY) — 小欧 2026-09-02
    取首个非 window: 键的文件路径; 无路径参数/窗口工具/提取失败返回 None(=工具级通配)
    2026-09-16 小欧 问题A修复: 非文件信任域(registry/sql)补专用提取 —— _parse_paths 按
      FILE_OPERATION_TOOLS 过滤, registry_write 等不在其中致 trust_path 恒 None(查询侧永不命中);
      此处仅认规范 path 及定向别名(key_path/registry_key/db_path → path), 排除 data→value 等
      非路径别名, 防注册表值/数据污染信任路径; 不动 _parse_paths(保护 conflict_detector 并查集分组) — 小欧-2026-09-16
    完整复制自 action_handler.py:581-587，取首个非 window: 键的文件路径
    """
    for p in _parse_paths(name, params or {}):
        if not p.startswith("window:"):
            return p
    if name in NON_FILE_TRUST_TOOLS:          # 小欧 2026-09-16
        _params = params or {}
        for _akey, _acn in PARAM_ALIASES.get(name, {}).items():
            if _acn == "path":                # 仅规范 path 的定向别名(key_path/registry_key/db_path...)
                _v = _params.get(_akey)
                if isinstance(_v, str) and _v:
                    return _v
        _v = _params.get("path")              # 规范名兜底
        return _v if isinstance(_v, str) and _v else None
    return None


# ════════════════════════════════════════════════════════════
# async函数：信任跳过判定（复制自 action_handler.py:297-327）
# ════════════════════════════════════════════════════════════

async def resolve_skip(agent_task_id: str, tool_name: str, params: dict) -> bool:
    """信任跳过判定: 查询会话级信任记录,决定是否跳过HITL确认
    完整复制自 action_handler.py:297-327（check_safety_and_confirm内联逻辑提取）
    [SA2] 权限信任框架第2步: 上游SA1 safety_gate预查, 下游SA3总闸skip_confirmation — 小欧-2026-10-14
    """
    from app.db import db
    from app.safety.trust_db import get_session_id_by_task, check_session_trust
    try:
        _sid = await db.atxn("chat", lambda conn: get_session_id_by_task(conn, agent_task_id))
    except Exception:
        return False
    if not _sid:
        return False
    _tgt = extract_trust_path(tool_name, params)
    try:
        return await db.atxn("chat", lambda conn: check_session_trust(conn, _sid, normalize_tool_name(tool_name), _tgt))
    except Exception as _te:
        from app.logger import logger
        logger.warning(f"[trust] 会话信任查询失败: task={agent_task_id}, tool={tool_name}, err={_te}")
        return False


# ════════════════════════════════════════════════════════════
# async函数：信任落库（复制自 hitl_confirmation.py:184-200）
# ════════════════════════════════════════════════════════════

async def save_session_trust(task_id: str, tool_name: str, path) -> None:
    """会话信任落库: 用户确认后将工具+路径写入会话信任记录
    完整复制自 hitl_confirmation.py:184-200（resolve_confirmation内联逻辑提取）
    [SA6] 权限信任框架第6步: HITL确认后落库, 供SA2下次预查豁免 — 小欧-2026-10-14
    """
    from app.db import db
    from app.safety.trust_db import get_session_id_by_task, insert_session_trust
    from app.logger import logger

    def _do(conn):
        _sid = get_session_id_by_task(conn, task_id)
        if not _sid:
            raise ValueError(f"[HITL] task_id={task_id} 无 session_id 可反查,信任禁止落库")
        insert_session_trust(conn, _sid, normalize_tool_name(tool_name), path)

    await db.atxn("chat", _do)
    # 2026-10-06 小欧 - 日志补登记范围: 原先只打 tool_name, 落库的是文件还是目录根本看不出来,
    #   "信任4次仍反复弹窗"正是因此查不出根因(表里4行全是叶子文件)。改为打印 trust_scope_path 归一后的值。
    #   弹了弹窗但登记范围不符预期时, 这一行即第一现场证据。
    from app.safety.trust_db import trust_scope_path as _scope
    logger.info(
        f"[HITL] 会话信任落库: task_id={task_id}, tool_name={normalize_tool_name(tool_name)}, "
        f"raw_path={path!r}, 登记范围={_scope(path, normalize_tool_name(tool_name))!r}"
    )
