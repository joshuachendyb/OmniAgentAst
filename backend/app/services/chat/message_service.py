# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 消息业务服务(方案4.7.3步骤3)。从 api/v1/messages.py 复制 get_session_messages/save_message
#   + display_name_cache(缓存归本服务独占), 仅改导入归属, 业务逻辑一字不改; 新增 delete_session_display_names 供
#   session_service 删除会话时联动清理(经方法调用, 不直接 import 本服务缓存对象, 单向方法调用)。API 层薄壳化改调本服务。
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.3+9.6): save_message删除execution_steps列写入;
#   user消息同步写chat_user_message(user_message_id=cursor.lastrowid一对一贯通, 根除两套自增id错位);
#   合并重复的 if role=="user" 判断块(DRY, 三堂会审)
# 2026-08-21 - 小欧 - 计数单口径(按文档 diff设计落地): chat_sessions.message_count 绝对值覆盖→SQL自增
#   (message_count + 1), 与 storage.py allocate 路径同口径, 消除并发写入丢计数; new_message_count 保留供返回值
# 2026-08-22 - 小欧 - 北京老陈铁律(chat_messages 只写严禁读): get_session_messages 改读 chat_user_message+chat_tasks(复用 fetch_session_user_message_pairs);
#   assistant 正文取 response、thought 从 execution_steps 的 thought 类型步骤派生(不退化/不加列/不读 chat_messages)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 定: L2 会话级模型覆盖 sessionModel 结构化对齐: ①import SessionModelOverride; ②get_session_messages
#     SELECT sessionModel 列(替原 model_override); ③新增 _parse_session_model(dict→SessionModelOverride, 容错返 None); ④返回 sessionModel 结构(替原 model_override 字符串)
# 2026-08-22 - 小欧 - 三堂会审复核整改(北京老陈 2026-08-22): 删除本文件重复的 _parse_session_model, 改从 storage 导入全系统唯一 parse_session_model(DRY); 同步移除不再使用的 json/SessionModelOverride 导入
# 2026-08-23 - 小欧 - 锚A解除(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): save_message user 分支
#   重构——权威源 chat_user_message 先落库(insert_user_message 原生自增分配 id), 再镜像写 chat_messages
#   (同 id 对齐/失败仅留痕); 权威写失败改 fail-loud 抛 HTTPException(旧路径吞异常返 success 但权威缺行,
#   历史回放丢消息属假成功); assistant legacy 直存分支行为不变; W1 两处镜像 INSERT 加 TODO 删除注释
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整体移除W1镜像写点(user/assistant两处INSERT chat_messages), 删除后assistant消息由任务/步骤体系(chat_tasks.ai_message_id/chat_task_steps)管理, 系统对该表零写依赖
# 2026-09-22 小欧 - constants.py 配置化迁移：import MAX_CACHE_SIZE 改别名 + cache 改读 tuning 配置
# 2026-09-24 21:36:38 小欧 - 配置组改名 tuning.stream_task→tuning.live_front：display_name 缓存上限读取键路径同步，
#   缓存逻辑/_D_CACHE_SIZE 默认值零改动 — 小欧-2026-09-24
# 2026-09-28 19:07:28 小欧 - 活跃任务注入展示层(设计文档[76] 5.5/6.9): ①新增 _merge_orphan_user_pairs —
#   连续无独立配对(ai_content空)的注入行合并成 1 个 user 气泡(与 _absorb_inbox 内存合并同一规则, 修刷新前后
#   UI 跳变); ②渲染循环加 seen_ai_ids — 同一任务 ai_message_id 至多渲染 1 次 assistant(修"同一 assistant
#   连同 steps 重复 N 次")。compliance: SRP/DRY/KISS/复用优先 — 小欧-2026-09-28
# 2026-09-28 19:32:44 小欧 - 三堂会审修复: ①合并加 pair_task_id 同任务约束(防相邻不同任务空回复行
#   串成一个气泡); ②assistant 配对改合并渲染载体(设计[76]决策2): 载体=首个有内容行, 全空回落首见行
#   (原首见即渲会渲空正文, 真答案落锚行时被跳过) — 小欧-2026-09-28
# 2026-09-30 20:05:00 小欧 - 计数器退役: save_message 删 message_count+1 只留刷 updated_at(列表按其排序),
#   SELECT 不再取该列, 返回值删 message_count 影子字段(前端未消费); 读取侧改走 count_session_messages 真值;
#   _try_mark_valid 与 is_valid 语义不动 — 小欧-2026-09-30
# 2026-10-01 小欧 - 解 [1] E3/E4/E11: ①消息对象补 task_id 字段(取 p["pair_task_id"], 归属以 LEFT JOIN 配对结果为准, cum.task_id 是消息侧原值、起始消息可能为 NULL); ②load_execution_steps 调用补传该 task_id(同 ai_message_id 可挂多任务, 不传则跨任务混读); ③thought 取键改 thought/reasoning(content 已被 _strip_thought_content 剥除, 且 reasoning-only 分支正文落在 thought 键上, 原式两键皆空致消息级 thought 退化为 None、历史回放推理区空白); ④删 get_user_message_id 导入(随 E8 空壳退役)
# 2026-10-03 - 小欧 - 文档[4] 5.7 项13: get_session_messages 响应补 link_enabled(前端读真源主路径)
# 2026-10-08 - 小欧 - 文档[11] 3.4.5.2: save_message 改调 resolve_session_interject(携带值先落库再判 409, 破插话死锁)
"""
message_service — 消息业务服务(services/chat)

职责(方案4.7.3, 小欧 2026-08-13): 会话消息历史读取/保存 + display_name 缓存(独占)。
API 层仅路由薄壳 + DTO, 业务逻辑单一归属本服务(SRP)。
"""
from typing import Optional

from app.logger import logger
from app.utils.json_utils import safe_json_dumps, parse_json
from app.utils.cache import LRUCache
from app.constants import MAX_CACHE_SIZE as _D_CACHE_SIZE
from app.config import get_config
from app.utils.time_utils import ensure_timestamp_milliseconds, get_local_iso_timestamp, to_local_iso, format_timestamp  # 小欧 2026-08-08 全程统一本地时区
from app.db import db
from app.db.models.chat_models import MessageResponse
from app.services.chat.storage import track_user_message, load_execution_steps
from app.services.chat.storage import insert_user_message  # v2.0 改动2: user消息同步写chat_user_message — 小欧 2026-08-19
from app.services.chat.storage import fetch_session_user_message_pairs, parse_session_model  # 北京老陈 2026-08-22: 替代 chat_messages 读取(只写铁律) + 结构化 sessionModel 统一解析(DRY)
from app.utils.display_utils import extract_display_name_from_steps, build_display_name
from app.services.task.task_registry import has_active_task_in_session   # 2026-10-07 小欧 - 文档[11] 3.4.5.1
from app.services.chat.storage import resolve_session_interject         # 2026-10-08 小欧 - 文档[11] 3.4.5.2 单一真源(取+落同函数)


# 消息模块共享的 display_name 缓存(A7 迁移边界: 归 message_service 独占) — 小欧 2026-08-13
display_name_cache = LRUCache(max_size=get_config().get("tuning.live_front.max_cache_size", _D_CACHE_SIZE))  # 2026-09-24 小欧 组名 stream_task→live_front — 小欧-2026-09-24


def delete_session_display_names(session_id: str) -> None:
    """联动清理: session_service 删除会话时调用, 防止 session_service 直接 import 本服务缓存对象 — 小欧 2026-08-13"""
    display_name_cache.delete(session_id)


def get_session_messages(session_id: str):
    """获取会话消息历史(21.3 重构,小沈 2026-05-25 实施) — 自 api/v1/messages.py 迁入"""
    from fastapi import HTTPException
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()

        cursor.execute('''SELECT id, title, created_at, updated_at,
                          COALESCE(title_locked, 0) as title_locked,
                          COALESCE(title_updated_at, created_at) as title_updated_at,
                           COALESCE(version, 1) as version, COALESCE(is_valid, 1) as is_valid,
                          sessionModel,
                          COALESCE(link_enabled, 0) as link_enabled,
                          -- 2026-10-06 小欧 - 文档[11] 3.4.6: 插话开关读真源(注释符须用 --, # 非 SQLite 注释)
                          COALESCE(allow_interject, 0) as allow_interject
                       FROM chat_sessions WHERE id = ? AND is_deleted = FALSE''', (session_id,))

        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")

        # 北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 改读 chat_user_message+chat_tasks(复用 fetch_session_user_message_pairs)
        pairs = fetch_session_user_message_pairs(conn, session_id)

        # assistant 合并渲染载体(设计[76]决策2, 小欧 2026-09-28 三堂会审): 每 ai_id 仅渲 1 次,
        # 落在首个有内容行(配首条会渲空正文且真答案被跳过); 全空回落首见行(steps 兜底)。
        # 2026-09-28 21:29 小欧 10轮会审 D-01 删 _merge_orphan_user_pairs: 原合并把同任务多条注入行并成
        #   1 个气泡, 但前端 useChatSend.ts:135 每次发送都追加一个 user 气泡(live 就是 N 个) →
        #   后端单方面合并会造成"live N 个 / 刷新 1 个"新跳变, 与 5.5 立意(消除跳变)相反;
        #   且合并挡在 carrier 之前会使真答案行落到 run 外被丢弃。它要治的"同一 assistant 重复渲染 N 次"
        #   已由下方 carrier 根治(每 ai_id 只渲 1 次), 故整段删除而非修判据(KISS-DIRECT: 删代码优于加代码)。
        # 注: conversation_history 侧的合并(为 OpenAI user/assistant 交替性)仍在 _absorb_inbox, 与渲染层无关。
        _first_row: dict = {}
        _carrier: dict = {}
        for _i, _p in enumerate(pairs):
            _aid = _p.get("ai_message_id")
            if _aid is None:
                continue
            _first_row.setdefault(_aid, _i)
            if (_p.get("ai_content") or "") and _aid not in _carrier:
                _carrier[_aid] = _i
        for _aid, _i in _first_row.items():
            _carrier.setdefault(_aid, _i)

        messages = []
        for _i, p in enumerate(pairs):
            # 2026-10-01 小欧: 任务归属以 pair_task_id 为准(LEFT JOIN 配对结果, 注入行与起始行已归一,
            #   见 fetch_session_user_message_pairs 文档); cum.task_id 是消息侧原值, 起始消息可能为 NULL。
            _p_tid = p.get('pair_task_id')
            # 用户消息气泡
            messages.append(MessageResponse(
                id=p['user_id'], session_id=session_id,
                role="user", content=p['user_content'] or "",
                timestamp=format_timestamp(p['created_at']),
                execution_steps=[], display_name=None, thought=None,
                task_id=_p_tid,
            ))
            ai_id = p['ai_message_id']
            if ai_id is None or _carrier.get(ai_id) != _i:
                continue
            # 从 chat_task_steps 表读取步骤列表 — 小欧 2026-07-14; v2.0 表改名 chat_task_steps — 2026-08-19
            # 2026-10-01 小欧: 补传 task_id(解 [1] E3)——同 ai_message_id 可挂多个 task
            #   (同任务多行兼容), 不传则退化为"该 ai_id 的全部步骤"跨任务混读。
            steps = load_execution_steps(conn, ai_id, _p_tid)
            display_name = build_display_name(p['provider'], p['model']) if p['provider'] or p['model'] else None
            if not display_name and steps:
                display_name = extract_display_name_from_steps(steps)
            # thought 派生: 从 execution_steps 的 thought 类型步骤取(北京老陈 2026-08-22: 不读 chat_messages)
            # 2026-10-01 小欧: 取键改 thought/reasoning(解 [1] E11 连带)——content 已被
            #   _strip_thought_content 剥除(回显只取 thought/reasoning), 且 reasoning-only 分支的
            #   thought 步正文落在 thought 键上(ThoughtStep._thought = thought or content),
            #   原式 "content or reasoning" 两键皆空 → 消息级 thought 退化为 None, 历史回放推理区空白。
            thought = None
            if steps:
                for s in steps:
                    if isinstance(s, dict) and s.get("type") == "thought":
                        thought = s.get("thought") or s.get("reasoning")
                        if thought:
                            break

            messages.append(MessageResponse(
                id=ai_id, session_id=session_id,
                role="assistant", content=p['ai_content'] or "",
                timestamp=format_timestamp(p['created_at']),
                execution_steps=steps, display_name=display_name,
                thought=thought, task_id=_p_tid,
            ))

        title_locked = bool(session['title_locked'])
        return {
            "session_id": session_id, "title": session['title'],
            "created_at": format_timestamp(session['created_at']),
            "updated_at": format_timestamp(session['updated_at']),
            "title_locked": title_locked,
            "title_source": "user" if title_locked else "auto",
            "title_updated_at": to_local_iso(session['title_updated_at']),
            "version": session['version'], "is_valid": session['is_valid'],
            "sessionModel": parse_session_model(session['sessionModel']),
            # 2026-10-02 小欧 - 文档[4] 5.7 项13: 随会话下发 link_enabled —— 前端读真源主路径是本端点(非 getSession),
            #   缺此字段则刷新/切会话后镜像恒 false。
            "link_enabled": bool(session['link_enabled']),
            # 2026-10-06 小欧 - 文档[11] 3.4.6: 插话开关随会话下发(唯一读真源, 同 link_enabled)
            "allow_interject": bool(session['allow_interject']),
            "messages": messages,
        }


def _try_mark_valid(cursor, session_id: str) -> None:
    """如果会话之前is_valid=False,尝试自愈标记为True — 小健 2026-05-25"""
    cursor.execute("SELECT is_valid FROM chat_sessions WHERE id = ?", (session_id,))
    row = cursor.fetchone()
    if row and not row[0]:
        cursor.execute("UPDATE chat_sessions SET is_valid = 1 WHERE id = ?", (session_id,))
        logger.info(f"[save_message] 会话{session_id}已自愈标记为有效")


def _track_user_message(session_id: str, message_id: str) -> None:
    """线程安全地存储user_message_id,覆盖旧值 — 小健 2026-05-25"""
    track_user_message(session_id, message_id)
    logger.info(f"[save_message] 记录user消息ID: {message_id}, 会话: {session_id}")


async def save_message(session_id: str, message):
    """保存消息到会话 — 小健 2026-05-25 重构 — 自 api/v1/messages.py 迁入"""
    from fastapi import HTTPException
    with db.get_conn("chat") as conn:
        cursor = conn.cursor()
# 2026-10-08 小欧 - 文档[11] 3.4.5.2: 携带值先落会话开关再做下方 409 判定(死锁: 值原先只由
        #   orchestrator 落, 而 409 门读会话当前值 → 插话第一条必被拒)。只拦 user(开关随用户消息携带)。
        _eff_allow = resolve_session_interject(
            conn,
            session_id,
            getattr(message, "allow_interject", None) if message.role == "user" else None,
        )
        # ── 插话开关: 关态且同会话有活跃任务 → 409(落库之前, 消息不入库) ──
        #   2026-10-07 小欧 - 文档[11] 3.4.5: 方案①"门口就拦"。前端 error/handler.ts
        #   已有 409 处理分支, 本方案零新增前端错误分支; 若改在 SSE 生成器内则无法转 409(见 3.3)。
        #   2026-10-07 小欧 三堂会审补：仅拦 user 角色。save_message 同承 assistant/system 直存
        #   （内部流转），一律拦会把任务体系内部写入误伤成 409。
        if message.role == "user" and await has_active_task_in_session(session_id):
            if not _eff_allow:   # 携带值优先, 否则读会话当前值(同 conn 直读, 不另开 atxn)
                raise HTTPException(
                    status_code=409,
                    detail="任务执行中，插话开关未开启；请等待完成或先取消",  # 与编排器兜底 error_message、前端 ERROR_CONFIG_MAP 同文案, 改须三处同步(2026-10-07 小欧)
                )

        cursor.execute(
            "SELECT id, title, COALESCE(title_locked, 0) as title_locked "
            "FROM chat_sessions WHERE id = ? AND is_deleted = FALSE", (session_id,))
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")

        local_time = get_local_iso_timestamp()

        display_name_to_save = message.display_name
        if message.role == "assistant" and not display_name_to_save:
            display_name_to_save = display_name_cache.get(session_id)

        message_id = None
        if message.role == "user":
            # 锚迁移(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): 权威源 chat_user_message
            # 先落库, id 由本表 AUTOINCREMENT 原生自增分配(不再取 chat_messages.lastrowid 一对一贯通);
            # 权威写失败即保存失败 fail-loud(杜绝旧路径"镜像成功但权威缺行→历史回放丢消息"的假成功) — 小欧 2026-08-23
            message_id = insert_user_message(
                conn,
                session_id=session_id,
                content=message.content,
                client_os=message.client_os,
                browser=message.browser,
                device=message.device,
                network=message.network,
            )
            _track_user_message(session_id, message_id)
            # 镜像写点 W1-user(INSERT chat_messages) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27
        # 镜像写点 W1-assistant(legacy 助手直存 INSERT chat_messages) 已随 chat_messages 表退役整体移除;
        # assistant 消息现由任务/步骤体系(chat_tasks.ai_message_id / chat_task_steps)管理 — 小欧 2026-08-27

        # 只刷 updated_at(列表按其排序), 计数器已退役 — 小欧 2026-09-30
        cursor.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (local_time, session_id))

        _try_mark_valid(cursor, session_id)

    return {"success": True, "message_id": message_id}