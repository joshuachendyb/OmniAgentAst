# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 新增allocate_and_insert_message/append_execution_step/load_execution_steps/finalize_message四函数,支撑运行期逐步落库+渐进耐久
# 2026-07-14 - 小欧 - 修复load_execution_steps: 无步骤且无legacy blob时返回[]而非None,避免API返回execution_steps=None
# 2026-07-18 - 小欧 - FinalStep多态自包含终态重构: derive_status_from_steps改为读最后一条final.outcome
#   【病根】原derive_status_from_steps基于type推断终态(cancelled→cancelled, error→failed),
#          与FinalStep多态设计不一致; 且type=final始终返回completed, 无法区分failed终态。
#   【改法】改为遍历找最后一条type=final, 读其outcome字段返回; 无final时兜底返回completed。
# 2026-07-18 - 小欧 - create_timestamp→get_utc_timestamp() (3处); append_execution_step 补 created_at 入库
# 2026-07-18 - 小欧 - 修复#1空步骤谎报完成: derive_status_from_steps 空/无final步默认"failed"(fail-safe, 对齐agent_runner兜底); 修复#6拼写错 ccancelled→cancelled
# 2026-07-18 - 小欧 - #17 fix: allocate_and_insert_message 首行补 ensure_session_exists, 消除孤儿消息风险
# 2026-07-18 - 小欧 - #22 fix: allocator锁范围扩大覆盖SELECT+dict写入,消除竞态
# 2026-07-21 - 小欧 - SQLite存储适配: MAX_TOOL_RESULT_STR_LEN=100(0a054a05e)→10000(4ee3ff070), _truncate_tool_result_strings方法, 写入前截断tool_result超长字符串防SQLite行溢出; _truncate_step_dict调用链; 不碰observation字段
# 2026-07-23 - 小欧 - 北京老陈驱动: 安全兜底 MAX_TOOL_RESULT_STR_LEN
#         10000→100000 (各tool自行截断输出后, storage仅兜底,
#         不再做激进取舍)
# 2026-08-08 - 小欧 - 全程统一本地时区: get_utc_timestamp→get_local_iso_timestamp (L147/189/232/329 4处写入), 本地ISO无Z入库
# 2026-08-11 - 小欧 - task006方案5落地: 截断字符串附加"原长N字符"标记, 让LLM感知base64/长文本被截断, 影像分析类任务不被截断误导
# 2026-08-13 - 小欧 - 三堂会审修复#1/#9: #1 allocate_and_insert_message 的 local_time 提前到 if is_new 外赋值,
#   消除 is_new=False(同session二次任务 agent_runner路径)时 UPDATE 引用未绑定变量 NameError;
#   #9 _truncate_tool_result 递归返回值统一回写父节点, 修复 list 内嵌超长 list 截断失效(如 {"rows":[[…1001…]]})
# 2026-08-16 - 小欧 - S2(10.1.7②, 北京老陈 2026-08-16 定案): 任务级读写落库扩展——
#   ②-1 insert_task/update_task(chat_tasks 建行+终态, update 幂等缺省不覆盖); ②-2 allocate_and_insert_message/
#   append_execution_step 增 task_id 列(任务级贯通), load_execution_steps 增 task_id 双条件(未传退化按 message_id);
#   ②-3 token_usage_insert; ②-4 get_session_model_override; ②-5 insert_session_trust/check_session_trust +
#   get_session_id_by_task(task_id→session_id 反查, HITL trust 落库/豁免用, 禁伪 agent.session_id);
#   ②-6 query_token_usage 四维聚合 + get_previous_task_chain(S1 链根计算)
# 2026-08-17 - 小健 - 三堂会审修复(北京老陈驱动, 11 bug 复核3遍):
#   E2: line69-77 新增 get_last_user_message_id(DB兜底), 供 orchestrator 在 track 缺失时为 linked 续聊恢复 upper 上界。
#   AM2/STORAGE_1: AssistantMessageIdAllocator.allocate 增 always_new 参数(默认False保留legacy复用语义);
#       allocate_and_insert_message 设 always_new=True 每任务独立新行——绝 user 未track时 expected 命中已存在
#       assistant 行导致内容覆盖(is_new=False仍message_count+1虚高, 同session多任务共用一行)。
#   STORAGE_2: 每任务独立行后, load_execution_steps 按 task_id 双条件不再混任务步骤。
# 2026-08-17 - 小健 - 必备日志补齐(老陈驱动「昨天今天提交代码都必须加」): allocate 的 always_new 递增寻空位
#   打 logger.warning 留痕(异常回落/越界审计点, 仅落文件不刷 console)。
# 2026-08-18 - 小健 - 三堂会审 Bug#5: _truncate_step_dict 补新 ActionStep 字段 tools[i].params 超长字符串截断(旧实现仅截断 execution_result/parallel_results, 漏 tools 致长SQL/content撑爆SQLite); 已核实 ActionStep.to_dict() 输出键为 tools, 非死代码
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.1→9.4→9.6→9.9): append_execution_step参数message_id→ai_message_id
#   +新增usage/user_message_id列、load_execution_steps去掉chat_messages.execution_steps回退、allocate_and_insert_message
#   加user_message_id参数、insert_task加ai_message_id参数、新增6函数(insert_user_message/update_user_message_final/
#   load_user_message_by_task/get_task_detail/get_task_tool_stats/load_steps_by_task)
# 2026-08-19 - 小欧 - 三堂会审Bug#2修复: insert_assistant_message INSERT列 reply_to_message_id→user_message_id
#   (v2.2列改名后旧列名新库不存在, 执行即OperationalError; 模型字段名保留API层, DB列名对齐v2改名)
"""
storage — 会话存储业务逻辑
从 conversation_storage.py 移入
小欧 2026-07-10

编辑历史: 2026-07-21 小欧
2026-07-21 小欧: 修复 _truncate_step_dict 漏掉 execution_result+parallel_results 截断;
2026-07-21: 小欧 加 _truncate_tool_result_strings (带 tag 日志, 不碰 observation);
2026-07-21  小欧: 移动 MAX_TOOL_RESULT_STR_LEN 等常量; 
"""

import threading
from typing import Any, Dict, Optional, Tuple
from sqlite3 import Connection

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.logger import logger
from app.db import db
from app.utils.json_utils import safe_json_dumps, parse_json
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区: 本地ISO无Z入库
from app.utils.display_utils import extract_metadata_from_steps

# 存储每个session的消息ID
# key: session_id, value: user_message_id 或 assistant_message_id
_user_message_ids: Dict[str, int] = {}
_message_ids_lock = threading.Lock()


def track_user_message(session_id: str, message_id: int):
    """记录用户消息ID"""
    with _message_ids_lock:
        _user_message_ids[session_id] = message_id


def get_user_message_id(session_id: str) -> Optional[int]:
    """获取用户消息ID"""
    return _user_message_ids.get(session_id)


def get_last_user_message_id(conn: Connection, session_id: str) -> Optional[int]:
    """取本会话最后一条 user 消息 id(DB兜底) — 小健 2026-08-17 三堂会审-E2修复:
    track(_user_message_ids) 为内存 dict, 服务重启即丢; 该函数从 DB 恢复,
    供 orchestrator 在 track 缺失时为 linked 续聊提供 upper 上界(防链外/全部消息进上下文)"""
    row = conn.execute(
        "SELECT id FROM chat_messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    return row["id"] if row else None


class ExecutionStepsUpdate(BaseModel):
    """执行步骤更新请求体 — 小欧 2026-07-10"""
    execution_steps: Optional[list] = Field(None, description="执行步骤详情列表")
    content: Optional[str] = Field(None, description="AI生成的文本内容")
    reply_to_message_id: Optional[int] = Field(None, description="回复的用户消息ID")
    status: Optional[str] = Field(None, description="任务终态: completed/failed/cancelled/paused — 小欧 2026-07-13")


def derive_status_from_steps(steps: Optional[list]) -> str:
    """从 execution_steps 推导任务终态(status列兜底) — 小欧 2026-07-13 初版
    2026-07-18 小欧 重构: 读最后一条 final.outcome(显式声明终态结果),
    无向后/旧数据兼容(用户: 旧数据不合适可删除或清库)。
    失败默认"failed"(fail-safe, 与 agent_runner 终态兜底一致): 空步骤/无终态步一律判失败,
    杜绝"空步骤谎报完成"。— 北京老陈 2026-07-18"""
    if not steps:
        return "failed"
    last_final = None
    for s in steps:
        if isinstance(s, dict) and s.get("type") == "final":
            last_final = s
    return last_final.get("outcome", "failed") if last_final else "failed"


class AssistantMessageIdAllocator:
    """拷贝自 conversation.py 第34-79行"""

    def __init__(self, user_ids: Dict[str, int], lock: threading.Lock):
        self._user_ids = user_ids
        self._assistant_ids: Dict[str, int] = {}
        self._lock = lock

    def allocate(self, session_id: str, conn: Connection,
                 always_new: bool = False) -> Tuple[int, bool]:
        """拷贝自 conversation.py 第48-79行

        10规范(SRP): 只负责分配assistant消息ID
        10规范(DRY): 复用conn执行查询
        修复: 并发场景下检查session_id归属+递增寻空位
        #22 fix: 锁范围扩大覆盖 SELECT+dict写,消除竞态 — 小欧 2026-07-18
        2026-08-17 小健 三堂会审-AM2/STORAGE_1修复: 增 always_new 参数——
          always_new=True(任务级 allocate_and_insert_message)时, 若 expected 命中已存在的
          assistant 行(多为 user 未 track/未落库导致 expected 回落为1), 递增寻新空位而非复用,
          使每个任务独立成行(杜绝内容覆盖/虚高); 默认 False 保留 legacy save_execution_steps 复用语义
        """
        with self._lock:
            user_id = self._user_ids.get(session_id)

            if user_id is not None:
                expected = user_id + 1
            else:
                c = conn.cursor()
                c.execute(
                    "SELECT id FROM chat_messages WHERE session_id=? AND role='user' ORDER BY id DESC LIMIT 1",
                    (session_id,),
                )
                row = c.fetchone()
                expected = (row["id"] + 1) if row else 1

            c = conn.cursor()
            for _ in range(10):
                c.execute("SELECT id, role, session_id FROM chat_messages WHERE id=?", (expected,))
                existing = c.fetchone()
                if existing is None:
                    break
                if existing["role"] == "assistant" and existing["session_id"] == session_id:
                    if not always_new:
                        return expected, False
                    # always_new: 跳过本会话已占用的行, 递增寻新空位(每任务独立成行)
                    logger.warning(f"[allocator] {session_id} id={expected} 本会话行已占用, always_new 递增寻空位(防复用/覆盖)")
                    expected += 1
                    continue
                logger.warning(f"[allocator] {session_id} id={expected} 被占用(role={existing['role']}, sid={existing['session_id']}), 递增寻空位")
                expected += 1
            else:
                c.execute("SELECT id FROM chat_messages ORDER BY id DESC LIMIT 1")
                max_row = c.fetchone()
                expected = (max_row["id"] + 1) if max_row else 1

            self._assistant_ids[session_id] = expected
        return expected, True


# 模块级单例:AssistantMessageIdAllocator复用实例(避免每次调用新建,缓存失效)
_allocator = AssistantMessageIdAllocator(_user_message_ids, _message_ids_lock)


def ensure_session_exists(session_id: str, conn: Connection) -> None:
    """拷贝自 conversation.py 第104-112行"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id=? AND is_deleted=FALSE", (session_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


def insert_assistant_message(
    conn: Connection, ai_message_id: int, session_id: str,
    display_name: Optional[str], update_data,
) -> None:
    """拷贝自 conversation.py 第115-131行"""
    cursor = conn.cursor()
    local_time = get_local_iso_timestamp()
    initial_content = update_data.content or ""
    reply_to = getattr(update_data, 'reply_to_message_id', None)
    cursor.execute(
        """INSERT INTO chat_messages
           (id, session_id, role, content, timestamp, display_name, user_message_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (ai_message_id, session_id, "assistant", initial_content, local_time, display_name, reply_to),
    )
    logger.info(f"新消息创建: ai_message_id={ai_message_id}, session_id={session_id}, display_name={display_name}")


def update_message_fields(
    conn: Connection, ai_message_id: int,
    update_data, display_name: str,
) -> None:
    """拷贝自 conversation.py 第134-156行"""
    cursor = conn.cursor()
    fields: list = []
    values: list = []
    if update_data.content is not None:
        fields.append("content = ?")
        values.append(update_data.content)
    if getattr(update_data, "status", None) is not None:
        fields.append("status = ?")
        values.append(update_data.status)
    if fields:
        values.append(ai_message_id)
        cursor.execute(
            f'UPDATE chat_messages SET {", ".join(fields)} WHERE id = ?',
            values,
        )


def update_session_message_count(
    conn: Connection, session_id: str, increment: bool,
) -> None:
    """拷贝自 conversation.py 第159-177行"""
    cursor = conn.cursor()
    local_time = get_local_iso_timestamp()
    if increment:
        cursor.execute(
            "UPDATE chat_sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
            (local_time, session_id),
        )
    else:
        cursor.execute(
            "UPDATE chat_sessions SET updated_at=? WHERE id=?",
            (local_time, session_id),
        )


async def save_execution_steps(session_id: str, update_data):
    """拷贝自 conversation.py 第198-221行"""
    try:
        with db.get_conn("chat") as conn:
            ensure_session_exists(session_id, conn)
            ai_message_id, is_new = _allocator.allocate(session_id, conn)
            metadata = extract_metadata_from_steps(update_data.execution_steps)
            display_name = metadata.get("display_name")
            if is_new:
                insert_assistant_message(conn, ai_message_id, session_id, display_name, update_data)
            update_message_fields(conn, ai_message_id, update_data, display_name)
            update_session_message_count(conn, session_id, is_new)
        logger.info(f"保存执行步骤成功: session_id={session_id}, ai_message_id={ai_message_id}, is_new={is_new}")
        return {"success": True, "ai_message_id": ai_message_id, "is_new_message": is_new}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存执行步骤失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存执行步骤失败: {str(e)}")


# ====================================================================
# 独立步骤表操作 — 小欧 2026-07-14
# ====================================================================

def allocate_and_insert_message(conn: Connection, session_id: str, task_id: Optional[str] = None,
                                user_message_id: Optional[int] = None) -> int:
    """预分配 assistant 消息ID + 插入空白行 — 小欧 2026-07-14
    2026-08-13 - 小欧 - 三堂会审修复#1: local_time 提前到 if is_new 之外赋值,
      消除 is_new=False(同session二次任务, agent_runner路径)时 UPDATE 引用未绑定变量 NameError
    2026-08-16 - 小欧 - S2②-2: chat_messages 补 task_id 列（任务级贯通，10.1.7②-2）
    2026-08-17 - 小健 - 三堂会审-AM2/STORAGE_1修复: 任务级分配新行(always_new=True),
      杜绝同 session 多任务复用同一 assistant 行(内容互相覆盖)与 is_new=False 仍 message_count+1(虚高);
      is_new 恒 True 后每次+1 正确, 且各任务独立行 -> load_execution_steps 不再混任务步骤(STORAGE_2)
    2026-08-19 - 小欧 - v2.0: 加 user_message_id 参数，INSERT 同步写入 assistant→user 互指"""
    ensure_session_exists(session_id, conn)  # #17 fix: 写入前确保会话存在, 消除孤儿消息 — 小欧 2026-07-18
    ai_message_id, is_new = _allocator.allocate(session_id, conn, always_new=True)
    local_time = get_local_iso_timestamp()
    if is_new:
        conn.execute(
            "INSERT INTO chat_messages(id, task_id, session_id, role, content, timestamp, user_message_id) "
            "VALUES (?, ?, ?, 'assistant', ?, ?, ?)",
            (ai_message_id, task_id, session_id, "", local_time, user_message_id),
        )
    conn.execute(
        "UPDATE chat_sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
        (local_time, session_id),
    )
    return ai_message_id


# 工具结果截断阈值 — 小欧 2026-07-21
# tool_result/parallel_results 中任何列表超过此数即截断,防止 SQLite TEXT 超限
# 实验性的功能 :TODO做正式的持久化设计后进行更新
MAX_TOOL_RESULT_ITEMS: int = 1000
MAX_TOOL_RESULT_STR_LEN: int = 100000

def _truncate_tool_result(tr: Any, tag: str = "") -> Any:
    """递归截断 tool_result 中过大的列表 — 小欧 2026-07-21
    2026-07-21 小欧: 修复短列表不递归元素内大列表+ActionStep execution_result 遗漏
    2026-08-13 - 小欧 - 三堂会审修复#9: 递归返回值统一回写父节点(list分支return不再被丢弃),
      彻底覆盖"list内嵌超长list"(如 {"rows":[[…1001…]]}) 截断失效场景
    """
    if isinstance(tr, dict):
        for key, val in list(tr.items()):
            tr[key] = _truncate_tool_result(val, tag)
    elif isinstance(tr, list):
        if len(tr) > MAX_TOOL_RESULT_ITEMS:
            logger.warning(f"[storage] {tag}tool_result 列表过大,截断至{MAX_TOOL_RESULT_ITEMS}条(原{len(tr)}条)")
            tr = tr[:MAX_TOOL_RESULT_ITEMS]
        for i, item in enumerate(tr):
            tr[i] = _truncate_tool_result(item, tag)
    return tr


def _truncate_step_dict(step_dict: dict) -> dict:
    """截断 step_dict 中 tool/execution_result — 小欧 2026-07-21
    2026-07-21 小欧: 补 ActionStep.execution_result 截断; 加字符串截断防 SQLite 撑爆(不碰 observation)
    """
    if not isinstance(step_dict, dict):
        return step_dict
    if "tool_result" in step_dict:
        step_dict["tool_result"] = _truncate_tool_result(step_dict["tool_result"], "")
        _truncate_tool_result_strings(step_dict["tool_result"])
    if "execution_result" in step_dict:
        step_dict["execution_result"] = _truncate_tool_result(step_dict["execution_result"], "")
        _truncate_tool_result_strings(step_dict["execution_result"])
    # 2026-08-18 小健 三堂会审 Bug#5: 新 ActionStep 字段已由 execution_result 改名 tools,
    #   须对新 tools[i].params 做超长字符串截断, 防长 SQL/content 撑爆 SQLite(旧实现遗漏此键)
    tools = step_dict.get("tools")
    if isinstance(tools, list):
        for i, entry in enumerate(tools):
            if isinstance(entry, dict) and "params" in entry:
                entry["params"] = _truncate_tool_result(entry["params"], f"tools[{i}].params.")
                _truncate_tool_result_strings(entry["params"])
    pr = step_dict.get("parallel_results")
    if isinstance(pr, list):
        for i, entry in enumerate(pr):
            if isinstance(entry, dict):
                if "tool_result" in entry:
                    entry["tool_result"] = _truncate_tool_result(entry["tool_result"], f"parallel_results[{i}].")
                    _truncate_tool_result_strings(entry["tool_result"])
                if "execution_result" in entry:
                    entry["execution_result"] = _truncate_tool_result(entry["execution_result"], f"parallel_results[{i}].")
                    _truncate_tool_result_strings(entry["execution_result"])
    return step_dict


# tool_result 中单字符串最大字符数 — 小欧 2026-07-21
# formatter 行×列门限(tool_constants)已控制 observation 大小;
# tool_result 原始数据可能含超大字符串(如 base64/长文本), 在此做安全截断防 SQLite 撑爆



def _truncate_tool_result_strings(obj: Any, tag: str = "") -> None:
    """递归截 tool_result 中所有超长字符串 — 小欧 2026-07-21"""
    if isinstance(obj, dict):
        for key, val in list(obj.items()):
            if isinstance(val, str) and len(val) > MAX_TOOL_RESULT_STR_LEN:
                obj[key] = val[:MAX_TOOL_RESULT_STR_LEN] + f"...(storage截断,原长{len(val)}字符)"
                logger.warning(f"[storage] {tag}tool_result.{key} 字符串过大({len(val)}字符),截断至{MAX_TOOL_RESULT_STR_LEN}")
            elif isinstance(val, (dict, list)):
                _truncate_tool_result_strings(val, tag)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, str) and len(item) > MAX_TOOL_RESULT_STR_LEN:
                obj[i] = item[:MAX_TOOL_RESULT_STR_LEN] + f"...(storage截断,原长{len(item)}字符)"
                logger.warning(f"[storage] {tag}tool_result[{i}] 字符串过大({len(item)}字符),截断至{MAX_TOOL_RESULT_STR_LEN}")
            elif isinstance(item, (dict, list)):
                _truncate_tool_result_strings(item, tag)


def append_execution_step(conn: Connection, ai_message_id: int, session_id: str,
                          step_index: int, step_dict: dict, task_id: Optional[str] = None,
                          usage: Optional[str] = None,
                          user_message_id: Optional[int] = None) -> None:
    """运行期逐步落库 — 小欧 2026-07-14
    小欧 2026-07-21: 落库前截断超大 tool_result(列表+字符串)防 SQLite 撑爆; 不碰 observation
    2026-08-16 - 小欧 - S2②-2: chat_task_steps 补 task_id 列（任务级贯通，10.1.7②-2）
    2026-08-19 - 小欧 - v2.0: 表改名 chat_task_steps + 参数 message_id→ai_message_id + 新增 usage/user_message_id 列"""
    step_dict = _truncate_step_dict(step_dict)
    conn.execute(
        "INSERT INTO chat_task_steps(ai_message_id, task_id, session_id, step_index, step_json, created_at, usage, user_message_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (ai_message_id, task_id, session_id, step_index, safe_json_dumps(step_dict),
         get_local_iso_timestamp(), usage, user_message_id),
    )


def load_execution_steps(conn: Connection, ai_message_id: int, task_id: Optional[str] = None) -> Optional[list]:
    """从 chat_task_steps 表组装步骤列表（v2.0: 不再回退读 chat_messages.execution_steps）
    返回结构与原签名完全一致：命中返回 list[step_dict]（按 step_index 升序），未命中返回 []，
    调用方（_load_previous_messages / stream_reader 回放）行为不变 — 小欧 2026-08-19 P1-8"""
    if task_id is not None:
        rows = conn.execute(
            "SELECT step_json FROM chat_task_steps WHERE ai_message_id=? AND task_id=? ORDER BY step_index ASC",
            (ai_message_id, task_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT step_json FROM chat_task_steps WHERE ai_message_id=? ORDER BY step_index ASC",
            (ai_message_id,),
        ).fetchall()
    if rows:
        return [parse_json(r["step_json"], label="step_json") for r in rows]
    return []


def finalize_message(conn: Connection, message_id: int, content: str, status: str, thought: str = "") -> None:
    """finally 轻量终态 — 小欧 2026-07-14; 2026-07-16 小欧 增 thought 持久化"""
    conn.execute(
        "UPDATE chat_messages SET content=?, status=?, thought=? WHERE id=?",
        (content, status, thought or None, message_id),
    )


# ====================================================================
# S2 任务级读写落库（10.1.7②，北京老陈 2026-08-16 定案）— 小欧 2026-08-16
# ====================================================================

# ---- ②-1 chat_tasks 任务行落库 ----

def insert_task(
    conn: Connection, *,
    task_id: str, session_id: str, user_message_id: Optional[int], ai_message_id: Optional[int] = None,
    user_input: str, context_link_mode: str, context_root_task_id: str,
    provider: str, model: str, display_name: str,
) -> None:
    """chat_tasks 任务行创建 INSERT（随任务启动，stream_orchestrator 建 task_id 后调用）— 小欧 2026-08-16"""
    now = get_local_iso_timestamp()
    conn.execute(
        """INSERT INTO chat_tasks
           (task_id, session_id, user_message_id, ai_message_id, user_input, context_link_mode,
            context_root_task_id, provider, model, display_name, start_time, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (task_id, session_id, user_message_id, ai_message_id, user_input,
         context_link_mode, context_root_task_id,
         provider, model, display_name, now, "executing", now, now),
    )


def update_task(
    conn: Connection, *,
    task_id: str, response: str = "", status: str = None,
    end_time: Optional[str] = None, duration: Optional[float] = None,
    accumulated_usage: Optional[Dict] = None, llm_call_count: Optional[int] = None,
    total_steps: Optional[int] = None, retry_count: Optional[int] = None,
    error_type: Optional[str] = None, error_message: Optional[str] = None,
) -> None:
    """chat_tasks 任务终态 UPDATE（随任务结束，agent_runner finally 落库）— 幂等、缺省字段不覆盖 — 小欧 2026-08-16"""
    _f, _v = [], []
    for _k, _val in (("response", response), ("status", status), ("end_time", end_time),
                     ("duration", duration), ("accumulated_usage", accumulated_usage),
                     ("llm_call_count", llm_call_count), ("total_steps", total_steps),
                     ("retry_count", retry_count), ("error_type", error_type),
                     ("error_message", error_message)):
        if _val is not None:
            _f.append(f"{_k} = ?")
            _v.append(safe_json_dumps(_val) if _k == "accumulated_usage" else _val)
    if not _f:
        return
    _f.append("updated_at = ?"); _v.append(get_local_iso_timestamp())
    _v.append(task_id)
    conn.execute(f"UPDATE chat_tasks SET {', '.join(_f)} WHERE task_id = ?", _v)


# ---- ②-3 token_usage 落库 ----

def token_usage_insert(
    conn: Connection, *,
    session_id: str, task_id: str, llm_call_count: int,
    model: str, provider: Optional[str],
    prompt_tokens: int, completion_tokens: int, total_tokens: int,
) -> None:
    """token_usage 每轮 LLM 调用一行 INSERT — 小欧 2026-08-16"""
    conn.execute(
        """INSERT INTO token_usage
           (session_id, task_id, llm_call_count, model, provider,
            prompt_tokens, completion_tokens, total_tokens, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (session_id, task_id, llm_call_count, model, provider,
         prompt_tokens or 0, completion_tokens or 0, total_tokens or 0,
         get_local_iso_timestamp()),
    )


# ---- ②-4 chat_sessions model_override 生效 ----

def get_session_model_override(conn: Connection, session_id: str) -> Optional[str]:
    """读 chat_sessions.model_override（L2 会话级模型覆盖）— 小欧 2026-08-16"""
    row = conn.execute(
        "SELECT model_override FROM chat_sessions WHERE id=? AND is_deleted=FALSE",
        (session_id,),
    ).fetchone()
    return row["model_override"] if row and row["model_override"] else None


# ---- ②-5 chat_session_trust 落库 ----

def insert_session_trust(conn: Connection, session_id: str, tool_name: str) -> None:
    """HITL"信任本次会话"落库（UNIQUE(session_id, tool_name) 幂等）— 小欧 2026-08-16"""
    conn.execute(
        "INSERT OR IGNORE INTO chat_session_trust(session_id, tool_name, created_at) VALUES (?,?,?)",
        (session_id, tool_name, get_local_iso_timestamp()),
    )


def check_session_trust(conn: Connection, session_id: str, tool_name: str) -> bool:
    """工具安全检查豁免查询：会话已信任该工具则免二次 HITL 确认 — 小欧 2026-08-16"""
    row = conn.execute(
        "SELECT 1 FROM chat_session_trust WHERE session_id=? AND tool_name=?",
        (session_id, tool_name),
    ).fetchone()
    return row is not None


def get_session_id_by_task(conn: Connection, task_id: str) -> Optional[str]:
    """按 task_id 反查 session_id（chat_tasks 已建行时）— HITL trust 落库/豁免用, 禁止伪 agent.session_id — 小欧 2026-08-16"""
    row = conn.execute(
        "SELECT session_id FROM chat_tasks WHERE task_id=?",
        (task_id,),
    ).fetchone()
    return row["session_id"] if row else None


# ---- ②-6 token_usage 四维度查询 API ----

def query_token_usage(
    conn: Connection, *, session_id: Optional[str] = None,
    task_id: Optional[str] = None, model: Optional[str] = None,
) -> Dict:
    """token 四维度聚合查询（按 session/task/model 过滤 + 三个 token 求和）— 口径同 9.7 — 小欧 2026-08-16"""
    _w, _v = [], []
    for _k in ("session_id", "task_id", "model"):
        _x = {"session_id": session_id, "task_id": task_id, "model": model}[_k]
        if _x:
            _w.append(f"{_k} = ?"); _v.append(_x)
    _where = ("WHERE " + " AND ".join(_w)) if _w else ""
    row = conn.execute(
        f"SELECT COUNT(*) AS calls, "
        f"COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
        f"COALESCE(SUM(completion_tokens),0) AS completion_tokens, "
        f"COALESCE(SUM(total_tokens),0) AS total_tokens "
        f"FROM token_usage {_where}", _v,
    ).fetchone()
    return dict(row)


def get_previous_task_chain(conn: Connection, session_id: str) -> Optional[Dict]:
    """取本会话最近一条成功(final 终态=completed)任务的链根 — S1 ④⑧(10.1.4)
    链根计算取最近一条 success 任务；cancelled/failed 跳过不继承(避免链到失败任务) — 北京老陈 2026-08-16
    返回 {task_id, context_root_task_id}；无成功任务返回 None(调用方使自身为链根)"""
    row = conn.execute(
        "SELECT task_id, context_root_task_id FROM chat_tasks "
        "WHERE session_id=? AND status='completed' ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    if row:
        return {"task_id": row["task_id"],
                "context_root_task_id": row["context_root_task_id"] or row["task_id"]}
    return None


# ====================================================================
# v2.0 chat_user_message 读写（2026-08-19）
# ====================================================================

def insert_user_message(
    conn: Connection, *,
    user_message_id: int,
    session_id: str, content: str,
    client_os: str = None, browser: str = None,
    device: str = None, network: str = None,
) -> int:
    """新建 chat_user_message 行（用户发消息时落库）。
    user_message_id 显式传入 chat_messages 的 user 消息 id（一对一贯通：
    chat_user_message.id == chat_messages.id），避免两套自增 id 错位
    （小健 2026-08-19 三堂会审 P0-2 根因修复）。"""
    now = get_local_iso_timestamp()
    cursor = conn.execute(
        """INSERT OR REPLACE INTO chat_user_message
           (id, session_id, content, client_os, browser, device, network, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (user_message_id, session_id, content, client_os, browser, device, network, now),
    )
    return user_message_id


def update_user_message_final(
    conn: Connection, *,
    user_message_id: int, task_id: str,
    response: str, reasoning: str = None,
    outcome: str = None, model: str = None,
    provider: str = None, accumulated_usage: str = None,
) -> None:
    """任务完成后回填 final 字段到 chat_user_message"""
    conn.execute(
        """UPDATE chat_user_message
           SET task_id=?, response=?, reasoning=?, outcome=?,
               model=?, provider=?, accumulated_usage=?
           WHERE id=?""",
        (task_id, response, reasoning, outcome, model, provider,
         accumulated_usage, user_message_id),
    )


def load_user_message_by_task(conn: Connection, task_id: str) -> Optional[dict]:
    """按 task_id 读 chat_user_message（C1 详情用）"""
    row = conn.execute(
        "SELECT * FROM chat_user_message WHERE task_id=?", (task_id,),
    ).fetchone()
    return dict(row) if row else None


# ====================================================================
# v2.0 C1/C2 任务级回放与统计存储（2026-08-19）
# ====================================================================

def get_task_detail(conn: Connection, task_id: str) -> Optional[dict]:
    """C1: 按 task_id 读 chat_tasks 单行详情"""
    row = conn.execute(
        "SELECT * FROM chat_tasks WHERE task_id=?", (task_id,),
    ).fetchone()
    return dict(row) if row else None


def get_task_tool_stats(conn: Connection, task_id: str) -> list:
    """C1: 从 chat_task_steps 统计该任务的工具调用次数"""
    rows = conn.execute(
        """SELECT
             json_extract(step_json, '$.tools[0].name') as tool_name,
             COUNT(*) as call_count
           FROM chat_task_steps
           WHERE task_id=? AND json_extract(step_json, '$.type')='action'
           GROUP BY tool_name""",
        (task_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def load_steps_by_task(conn: Connection, task_id: str) -> list:
    """C2: 按 task_id 读全部步骤（升序）"""
    rows = conn.execute(
        "SELECT step_json FROM chat_task_steps WHERE task_id=? ORDER BY step_index ASC",
        (task_id,),
    ).fetchall()
    return [parse_json(r["step_json"], label="step_json") for r in rows]
