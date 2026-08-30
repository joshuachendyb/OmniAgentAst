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
# 2026-07-21 - 小欧 - 修复 _truncate_step_dict 漏掉 execution_result+parallel_results 截断;
# 2026-07-21 - 小欧 - 加 _truncate_tool_result_strings (带 tag 日志, 不碰 observation);
# 2026-07-21 - 小欧 - 移动 MAX_TOOL_RESULT_STR_LEN 等常量;
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
# 2026-08-20 - 小欧 - 11.1 token 四层同构累计三堂会审修复: ①import types; ②_EMPTY_TOKEN 改 types.MappingProxyType 冻结(防外部 mutate 污染全局); ③新增 _normalize_acc() 显式判键归一(parse_json('{}') 返 truthy 空对象, 原 `or dict` 不兜底致下游 _old['prompt_tokens'] KeyError 致命bug, 现统一归一含3键零值); ④query_task/session_accumulation 加 row 缺失守卫+改调 _normalize_acc; ⑤update_task/session_accumulation 加 rowcount==0 告警(检测累计静默丢失)
# 2026-08-20 - 小欧 - 11.1 测试驱动修复(_normalize_acc, 小欧单测 tests/test_token_accumulation_11_1.py 锁定): 原仅对非法/空对象归一, 对"含部分键"的 JSON(如 {'prompt_tokens':5})原样返回 → query 返回缺键 dict(违反设计11.1.2含3键零值)、update 下游 _old[k] KeyError 崩溃、react_cycle 基线 [k] KeyError 被 except 吞致历史累计静默清零; 现改为缺键统一补零并 int 强转, 保留已存键。3 用例(部分键归一/update不崩/基线)已加。
# 2026-08-20 - 小欧 - 10.5 问题4/6 三堂会审落地: 新增 list_session_tasks(会话任务列表+总数, B1/问题6 任务数=用户消息数, chat_tasks 行数新口径) + list_session_trust(D1 信任清单) + delete_session_trust(D3 撤销信任)。
# 2026-08-21 - 小欧 - 11.6.4: update_task 新增 artifacts 参数+safe_json_dumps 写库; get_task_detail parse_json 反序列化 artifacts 为 list
# 2026-08-22 - 小欧 - 新增 load_user_messages_by_session (按 session_id 读 chat_user_message 列表，替代 chat_messages)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 定: L2 会话级模型覆盖 sessionModel 结构化: ① get_session_model_override 改名 get_session_model,
#     读 sessionModel 列(JSON)→dict(provider+model, 用 parse_json 容错); ②关联调用点 stream_orchestrator 同步改名引用
# 2026-08-22 - 小欧 - 三堂会审复核整改(北京老陈 2026-08-22): ①新增全系统唯一 parse_session_model(消除 message_service/session_service 重复实现, DRY), 返回 SessionModelOverride; ②get_session_model 返回值由 dict 改为 SessionModelOverride(类型统一, 杜绝调用方误用 .get 致 AttributeError); 关联 stream_orchestrator 消费点改属性访问(.model/.provider)
# 2026-08-22 - 小欧 - BUG修复(北京老陈 2026-08-22 铁律"系统代码不得退化"): 铁律后占用检查改读 chat_user_message+chat_tasks(禁读 chat_messages), 若 chat_messages 已存在该 id(如 legacy 直写助手消息未镜像至 chat_tasks)落库时 UNIQUE 撞键→500; save_execution_steps 改为撞键时退化为复用该消息(UPDATE, is_new 置 False 不重复计数), 与铁律前 chat_messages 占用检查"复用而非新建"语义一致, 不读 chat_messages、不污染 chat_tasks
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.3: 写侧三函数归一——insert_task(provider/model/display_name 三参→task_model: ModelRef 必填, 落 sessionModel JSON 单列)、token_usage_insert(model/provider→task_model: ModelRef 必填, NOT NULL)、update_user_message_final(model/provider→task_model: Optional[ModelRef], SET chat_model); 六读者派生——query_token_usage(model=→model_ref: json_extract 双键)、load_user_message_by_task/load_user_messages_by_session/fetch_session_user_message_pairs/get_task_detail/list_session_tasks (chat_model/sessionModel JSON→parse_session_model 派生 model/provider 键, 键名不变); import 补 ModelRef
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P1): insert_task 删 `if task_model else None` 死防御——参数已必填, Pydantic 实例恒真值, else 分支永不可达(SLAP); 直取 model_dump_json()
# 2026-08-23 - 小欧 - 锚A解除(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): insert_user_message id 分配锚迁移——user_message_id 显式入参退役(原=chat_messages.lastrowid 一对一贯通), 改 chat_user_message AUTOINCREMENT 原生自增并返回 lastrowid; INSERT OR REPLACE 随显式 id 退役(自增无撞键)改普通 INSERT; W2/W3/W4/W5 四个镜像写点加 TODO 删除注释(写保留, 系统零依赖 chat_messages)
# 2026-08-23 - 小欧 - D4 截断退役(文档[1]11.8.6/11.8.11/11.9 P7, 10.6.2 定案"现役表不截断"): 删 _truncate_tool_result/_truncate_step_dict/_truncate_tool_result_strings 三函数+两 MAX_TOOL_RESULT_* 常量, 新增 _warn_oversize_step_dict 超限 error 告警扫描(安全网不砍数据); append_execution_step 改完整 step_json 落库保历史回放权威源(5.1 铁律), 签名/返回值 -> None 原样零感知; 原"实验性的功能:TODO"占位随删除块一并清理(11.7.14-1)
# 2026-08-26 - 小欧 - D-1(文档2 8.D): list_session_tasks SELECT 补 context_link_mode 列, 前端左列"续聊/新任务"类型徽标数据源(4.8.3-B 契约已含该字段, 后端 SELECT 遗漏)
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整体移除镜像写点W2(insert_assistant_message)/W3(allocate_and_insert_message内INSERT空白行)/W4(update_message_fields)/W5(finalize_message内UPDATE)及save_execution_steps中对W2/W4的调用; 删除后终态/步骤真实存储由chat_task_steps.step_json与chat_tasks承载; 同步清理孤儿import(IntegrityError/extract_metadata_from_steps)
# 2026-08-27 - 小欧 - B1 SELECT 补 response 列: list_session_tasks 查询增加 response 字段返回，支撑左列任务列表显示任务结果全文（设计文档4.8.2要求user_input+response双列显示）
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整删finalize_message函数(原W5写chat_messages终态), 同步移除stream_orchestrator.db_ops.finalize=传参与agent_runner调用块(行446-461), 终态由append_execution_step(step_json)与_finalize_task_db(update_task+回填chat_user_message)承载
# 2026-08-29 - 小沈 - BugFix #7: update_task 的 response 默认从 "" 改为 None; 循环内 `if _val is not None` 已存在, 故未显式传 response 时不再用空串覆盖已有列(幂等缺省不覆盖语义落地)。
# 2026-08-30 - 小欧 - 第十二章 v1.103(设计文档[2]12.2 G1): list_session_tasks 排序 DESC→ASC(左列时间线=会话全部任务时间线清单, 新任务在底部, 4.3.2; 原 DESC 是 8.C-④ 顶栏锚点"首行=最新"的专用依赖, 一手排序喂两个反方向职责违反 SRP); 新增返回 latest_task_id(最新任务显式锚点, 顶栏/默认选中/结束沿 token 锚点统一消费, 排序一义+显式锚点解耦)。调用方 sessions.py 同步解包三元组(见 diff②)。
# 2026-08-30 - 小欧 - 第十三章13.7 C2 收口(设计文档[2]13.12.8, 北京老陈 2026-08-30 批准): load_steps_by_task 对 thought 步骤剥离 content 键出参(回放只取 thought/reasoning 两字段契约, 13.3/13.6), 仅剥 content、其余键原样保全
"""
storage — 会话存储业务逻辑
从 conversation_storage.py 移入
小欧 2026-07-10
"""

import json
import threading
import types  # 11.1 冻结 token 零值常量, 防外部 mutate 污染全局 — 小欧 2026-08-20
from typing import Any, Dict, Optional, Tuple
from sqlite3 import Connection

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.logger import logger
from app.db import db
from app.db.models.chat_models import SessionModelOverride, ModelRef   # 归一: ModelRef=SessionModelOverride 别名 — 小欧 2026-08-22
from app.utils.json_utils import safe_json_dumps, parse_json
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区: 本地ISO无Z入库

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
        "SELECT id FROM chat_user_message WHERE session_id=? ORDER BY id DESC LIMIT 1",
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
    """拷贝自 conversation.py 第34-79行

    【id 枢纽架构(北京老陈 2026-08-23 定调: chat_tasks 是任务中心表)】— 小欧 2026-08-23
      用户侧 id: chat_user_message AUTOINCREMENT 原生自增分配(锚迁移, 本表=回放权威源);
                 登记于 chat_tasks.user_message_id。
      助手侧 id(ai_message_id): 本 allocator 分配, 占用检查并查 chat_user_message.id ∪
                 chat_tasks.ai_message_id 两表——两 id 同属一个历史序列, 必须防撞号
                 (前端同一消息列表渲染 user/assistant 两种气泡 id 不可重号);
                 chat_tasks.ai_message_id 是中心登记点(orchestrator eager 创建任务即写入)。
      引用方: chat_task_steps.ai_message_id/user_message_id(步骤挂靠)、chat_messages(纯镜像行同id,
              北京老陈 2026-08-23 裁定"写保留当空气", 系统零依赖、外键已解除)。
      chat_tasks 持双 id 登记+任务全部终态, 所有回放/统计以它为枢纽——中心地位不动。"""

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
                    "SELECT id FROM chat_user_message WHERE session_id=? ORDER BY id DESC LIMIT 1",
                    (session_id,),
                )
                row = c.fetchone()
                expected = (row["id"] + 1) if row else 1

            c = conn.cursor()
            for _ in range(10):
                # 北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 占用检查改查 chat_user_message(id) + chat_tasks(ai_message_id)
                c.execute(
                    "SELECT 'user' AS role, session_id FROM chat_user_message WHERE id=? "
                    "UNION ALL "
                    "SELECT 'assistant' AS role, session_id FROM chat_tasks WHERE ai_message_id=?",
                    (expected, expected),
                )
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
                # 全局最大 id = chat_user_message.id 与 chat_tasks.ai_message_id 的并集中最大者
                c.execute(
                    "SELECT MAX(m) AS m FROM ("
                    "SELECT MAX(id) AS m FROM chat_user_message "
                    "UNION ALL SELECT MAX(ai_message_id) AS m FROM chat_tasks)"
                )
                max_row = c.fetchone()
                expected = (max_row["m"] + 1) if max_row and max_row["m"] is not None else 1

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


# 镜像写点 W2(insert_assistant_message 写 chat_messages) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27


# 镜像写点 W4(update_message_fields 写 chat_messages) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27


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
    """拷贝自 conversation.py 第198-221行; 镜像写点 W2/W4(insert_assistant_message / update_message_fields 均写 chat_messages)
    已随 chat_messages 表退役整体移除, 本函数仅负责分配 assistant id + 会话消息计数 — 小欧 2026-08-27"""
    try:
        with db.get_conn("chat") as conn:
            ensure_session_exists(session_id, conn)
            ai_message_id, is_new = _allocator.allocate(session_id, conn)
            # 镜像写点 W2/W4 已移除, 终态/步骤真实存储由 chat_task_steps / chat_tasks 承载 — 小欧 2026-08-27
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
    # 镜像写点 W3(INSERT chat_messages 空白 assistant 行) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27
    conn.execute(
        "UPDATE chat_sessions SET message_count=message_count+1, updated_at=? WHERE id=?",
        (local_time, session_id),
    )
    return ai_message_id


# 告警线(原截断阈值转告警线) — 10.6.2 定案(北京老陈 2026-08-23): 现役表不截断 — 小欧 2026-08-23
# (原"实验性的功能:TODO做正式的持久化设计后进行更新"占位随截断退役一并清理, 正式定案=文档[1]11.7/11.8 — 11.7.14-1)
_ALARM_STEP_ITEMS: int = 1000
_ALARM_STEP_STR_LEN: int = 100000

# 10.6.2 定案(北京老陈 2026-08-23): 截断整体退役 → 仅超限 error 告警扫描(安全网不砍数据)
# 2026-08-23 - 小欧 - D4(文档[1]11.8.6/11.8.11): 删 _truncate_tool_result/_truncate_step_dict/
#   _truncate_tool_result_strings 三函数, 换 _warn_oversize_step_dict 告警扫描 —
#   step_json.tool_result 数组是历史回放唯一权威数据源(5.1 铁律), storage 二次截断=砍坏回放源;
#   工具层自截断(5.7)为唯一合法截断层, 文件A 全量落盘不截断
def _warn_oversize_step_dict(step_dict, tag: str = "") -> None:
    """递归统计超限(列表>1000项/字符串>10万字符)仅 error 告警 — 安全网不砍数据 — 小欧 2026-08-23"""
    if isinstance(step_dict, dict):
        for k, v in step_dict.items():
            _warn_oversize_step_dict(v, f"{tag}{k}.")
    elif isinstance(step_dict, list):
        if len(step_dict) > _ALARM_STEP_ITEMS:
            logger.error(f"[storage]{tag}列表超大({len(step_dict)}项>告警线{_ALARM_STEP_ITEMS}), 请核查工具层自截断")
        for i, item in enumerate(step_dict):
            _warn_oversize_step_dict(item, f"{tag}[{i}].")
    elif isinstance(step_dict, str):
        if len(step_dict) > _ALARM_STEP_STR_LEN:
            logger.error(f"[storage]{tag}字符串超长({len(step_dict)}字符>告警线{_ALARM_STEP_STR_LEN}), 请核查工具层自截断")


def append_execution_step(conn: Connection, ai_message_id: int, session_id: str,
                          step_index: int, step_dict: dict, task_id: Optional[str] = None,
                          usage: Optional[str] = None,
                          user_message_id: Optional[int] = None) -> None:
    """运行期逐步落库 — 小欧 2026-07-14
    小欧 2026-07-21: 落库前截断超大 tool_result(列表+字符串)防 SQLite 撑爆; 不碰 observation
    2026-08-16 - 小欧 - S2②-2: chat_task_steps 补 task_id 列（任务级贯通，10.1.7②-2）
    2026-08-19 - 小欧 - v2.0: 表改名 chat_task_steps + 参数 message_id→ai_message_id + 新增 usage/user_message_id 列
    2026-08-23 - 小欧 - D4(文档[1]11.8.6/11.9 P7): 截断退役→超限 error 告警(10.6.2 现役表不截断);
      完整 step_json 落库保回放源(5.1); 签名/返回值保持原样(-> None)——文件A 定位键已改
      step/tool_no/retry_no 三键组(实时落盘), 不再需要本函数返回主键"""
    _warn_oversize_step_dict(step_dict)
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




# ====================================================================
# S2 任务级读写落库（10.1.7②，北京老陈 2026-08-16 定案）— 小欧 2026-08-16
# ====================================================================

# ---- ②-1 chat_tasks 任务行落库 ----

def insert_task(
    conn: Connection, *,
    task_id: str, session_id: str, user_message_id: Optional[int], ai_message_id: Optional[int] = None,
    user_input: str, context_link_mode: str, context_root_task_id: str,
    task_model: ModelRef,
) -> None:
    """chat_tasks 任务行创建 INSERT（随任务启动，stream_orchestrator 建 task_id 后调用）— 小欧 2026-08-16
    2026-08-22 小欧 归一报告v1.25 6.3: provider/model/display_name 三分离入参 → task_model: ModelRef 单结构,
    落 sessionModel JSON 单列(display_name 列废弃不写, 设计要求2)"""
    now = get_local_iso_timestamp()
    conn.execute(
        """INSERT INTO chat_tasks
           (task_id, session_id, user_message_id, ai_message_id, user_input, context_link_mode,
            context_root_task_id, sessionModel, start_time, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (task_id, session_id, user_message_id, ai_message_id, user_input,
         context_link_mode, context_root_task_id,
         task_model.model_dump_json(),   # 必填参数直取(三堂会审: 删永不可达的 else None 死防御) — 小欧 2026-08-22
         now, "executing", now, now),
    )


def update_task(
    conn: Connection, *,
    task_id: str, response: Optional[str] = None, status: str = None,
    end_time: Optional[str] = None, duration: Optional[float] = None,
    accumulated_usage: Optional[Dict] = None, llm_call_count: Optional[int] = None,
    total_steps: Optional[int] = None, retry_count: Optional[int] = None,
    error_type: Optional[str] = None, error_message: Optional[str] = None,
    artifacts: Optional[list] = None,
) -> None:
    """chat_tasks 任务终态 UPDATE（随任务结束，agent_runner finally 落库）— 幂等、缺省字段不覆盖 — 小欧 2026-08-16"""
    _f, _v = [], []
    for _k, _val in (("response", response), ("status", status), ("end_time", end_time),
                     ("duration", duration), ("accumulated_usage", accumulated_usage),
                     ("llm_call_count", llm_call_count), ("total_steps", total_steps),
                     ("retry_count", retry_count), ("error_type", error_type),
                     ("error_message", error_message), ("artifacts", artifacts)):
        if _val is not None:
            _f.append(f"{_k} = ?")
            _v.append(safe_json_dumps(_val) if _k in ("accumulated_usage", "artifacts") else _val)
    if not _f:
        return
    _f.append("updated_at = ?"); _v.append(get_local_iso_timestamp())
    _v.append(task_id)
    conn.execute(f"UPDATE chat_tasks SET {', '.join(_f)} WHERE task_id = ?", _v)


# ---- ②-3 token_usage 落库 ----

def token_usage_insert(
    conn: Connection, *,
    session_id: str, task_id: str, llm_call_count: int,
    task_model: ModelRef,
    prompt_tokens: int, completion_tokens: int, total_tokens: int,
) -> None:
    """token_usage 每轮 LLM 调用一行 INSERT — 小欧 2026-08-16
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 两分离入参 → task_model: ModelRef 单结构落 JSON 单列"""
    conn.execute(
        """INSERT INTO token_usage
           (session_id, task_id, llm_call_count, task_model,
            prompt_tokens, completion_tokens, total_tokens, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (session_id, task_id, llm_call_count,
         task_model.model_dump_json(),
         prompt_tokens or 0, completion_tokens or 0, total_tokens or 0,
         get_local_iso_timestamp()),
    )


# ---- 11.1 token 四层同构：任务级/会话级实时累计 + 链级计算派生 — 小欧 2026-08-20 ----

_EMPTY_TOKEN = types.MappingProxyType({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})  # 11.1 冻结常量: 防外部 mutate 污染全局 — 小欧 2026-08-20


def _normalize_acc(raw, label):
    """解析 token 累计 JSON, 空对象/缺键/非法统一归一为含3键零值 — 小欧 2026-08-20
    注: parse_json('{}') 返回 {} 为 truthy, 不能用 `or` 兜底(会漏 KeyError), 故显式判键
    11.1 增强(2026-08-20 小欧): 已存 dict 若只含部分键(如 {'prompt_tokens':5}), 缺键统一补零并强转 int,
        保留已存键, 杜绝下游 update 的 _old[k] KeyError 与 react_cycle 基线 [k] KeyError(历史累计被静默清零)"""
    _p = parse_json(raw, label=label) if raw else None
    if not isinstance(_p, dict) or "prompt_tokens" not in _p:
        return dict(_EMPTY_TOKEN)
    return {
        "prompt_tokens": int(_p.get("prompt_tokens") or 0),
        "completion_tokens": int(_p.get("completion_tokens") or 0),
        "total_tokens": int(_p.get("total_tokens") or 0),
    }


def query_task_accumulation(conn: Connection, *, task_id: str) -> dict:
    """读取任务级 token 当前累计值（JSON）— 11.1"""
    row = conn.execute(
        "SELECT task_accumulated_tokens FROM chat_tasks WHERE task_id = ?",
        (task_id,)).fetchone()
    if not row:  # 11.1 增强: 任务行缺失时返回零值, 避免 None 下标 TypeError 崩溃 — 小欧 2026-08-20
        return dict(_EMPTY_TOKEN)
    return _normalize_acc(row["task_accumulated_tokens"], label="task_acc")


def query_session_accumulation(conn: Connection, *, session_id: str) -> dict:
    """读取会话级 token 当前累计值（JSON）— 11.1"""
    row = conn.execute(
        "SELECT session_accumulated_tokens FROM chat_sessions WHERE id = ?",
        (session_id,)).fetchone()
    if not row:  # 11.1 增强: 会话行缺失时返回零值, 避免 None 下标 TypeError 崩溃 — 小欧 2026-08-20
        return dict(_EMPTY_TOKEN)
    return _normalize_acc(row["session_accumulated_tokens"], label="session_acc")


def update_task_accumulation(conn: Connection, *, task_id: str, llm_call_count_token: dict) -> None:
    """任务级 token 实时累计 — 11.1"""
    _old = query_task_accumulation(conn, task_id=task_id)
    _new = {k: _old[k] + int(llm_call_count_token.get(k) or 0)
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    _rc = conn.execute("UPDATE chat_tasks SET task_accumulated_tokens = ? WHERE task_id = ?",
                       (safe_json_dumps(_new), task_id)).rowcount
    if _rc == 0:  # 11.1 增强: 任务行缺失时 UPDATE 影响0行致累计静默丢失, 显式告警 — 小欧 2026-08-20
        logger.warning(f"[storage] update_task_accumulation 影响0行(task={task_id}): 任务行可能缺失或列未落库")


def update_session_accumulation(conn: Connection, *, session_id: str, llm_call_count_token: dict) -> None:
    """会话级 token 实时累计 — 11.1"""
    _old = query_session_accumulation(conn, session_id=session_id)
    _new = {k: _old[k] + int(llm_call_count_token.get(k) or 0)
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    _rc = conn.execute("UPDATE chat_sessions SET session_accumulated_tokens = ? WHERE id = ?",
                       (safe_json_dumps(_new), session_id)).rowcount
    if _rc == 0:  # 11.1 增强: 会话行缺失时 UPDATE 影响0行致累计静默丢失, 显式告警 — 小欧 2026-08-20
        logger.warning(f"[storage] update_session_accumulation 影响0行(session={session_id}): 会话行可能缺失或列未落库")


def query_chain_accumulation(conn: Connection, *, context_root_task_id: str, current_task_id: str) -> dict:
    """上下文链 token 累计（计算派生，不落库）— 11.1 满足 10.5-2 链根聚合语义
    对同 context_root_task_id 的所有「已完成」任务聚合 token_usage（排除当前运行中任务），
    independent 任务 context_root_task_id=自身 → 仅自身（清零重算）；linked 任务链根共享 → 全链 SUM。
    """
    _row = conn.execute(
        "SELECT COALESCE(SUM(prompt_tokens),0) AS p, COALESCE(SUM(completion_tokens),0) AS c, COALESCE(SUM(total_tokens),0) AS t "
        "FROM token_usage WHERE task_id IN (SELECT task_id FROM chat_tasks WHERE context_root_task_id = ?) "
        "AND task_id <> ?",
        (context_root_task_id, current_task_id)).fetchone()
    return {"prompt_tokens": int(_row["p"] or 0), "completion_tokens": int(_row["c"] or 0), "total_tokens": int(_row["t"] or 0)}


# ---- ②-4 chat_sessions sessionModel 生效 ---- 北京老陈 2026-08-22 L2 会话级模型覆盖(结构化 provider+model)

def parse_session_model(raw) -> Optional[SessionModelOverride]:
    """chat_sessions.sessionModel 列(JSON 文本)反序列化为结构化模型; 空/非法→None — 北京老陈 2026-08-22
    全系统唯一解析点(消除 message_service/session_service 重复实现, DRY), 返回 SessionModelOverride"""
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not data:
            return None
        return SessionModelOverride(**data)
    except Exception:
        logger.warning(f"[session] sessionModel 解析失败, 视为未设置: {raw}")
        return None


def get_session_model(conn: Connection, session_id: str) -> Optional[SessionModelOverride]:
    """读 chat_sessions.sessionModel（L2 会话级模型覆盖, 结构化）— 北京老陈 2026-08-22 改结构化 JSON:
    返回 SessionModelOverride(provider+model) 或 None（未设置）"""
    row = conn.execute(
        "SELECT sessionModel FROM chat_sessions WHERE id=? AND is_deleted=FALSE",
        (session_id,),
    ).fetchone()
    raw = row["sessionModel"] if row and row["sessionModel"] else None
    if not raw:
        return None
    return parse_session_model(raw)


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


def list_session_trust(conn: Connection, session_id: str) -> list:
    """D1(10.5 问题4): 会话已信任工具清单（HITL 信任列表, 供前端展示/撤销）— 小欧 2026-08-20"""
    rows = conn.execute(
        "SELECT tool_name, created_at FROM chat_session_trust "
        "WHERE session_id=? ORDER BY id DESC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_session_trust(conn: Connection, session_id: str, tool_name: str) -> bool:
    """D3(10.5 问题4): 撤销会话对指定工具的信任（HITL 解除豁免）— 小欧 2026-08-20"""
    cur = conn.execute(
        "DELETE FROM chat_session_trust WHERE session_id=? AND tool_name=?",
        (session_id, tool_name),
    )
    return cur.rowcount > 0


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
    task_id: Optional[str] = None, model_ref: Optional[ModelRef] = None,
) -> Dict:
    """token 四维度聚合查询（按 session/task/model 过滤 + 三个 token 求和）— 口径同 9.7 — 小欧 2026-08-16
    2026-08-22 小欧 归一报告v1.25 6.3: model 裸列过滤 → task_model JSON 列 json_extract 双键过滤"""
    _w, _v = [], []
    for _k in ("session_id", "task_id"):
        _x = {"session_id": session_id, "task_id": task_id}[_k]
        if _x:
            _w.append(f"{_k} = ?"); _v.append(_x)
    if model_ref:
        _w.append("json_extract(task_model,'$.provider')=? AND json_extract(task_model,'$.model')=?")
        _v.extend([model_ref.provider, model_ref.model])
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
    session_id: str, content: str,
    client_os: str = None, browser: str = None,
    device: str = None, network: str = None,
) -> int:
    """新建 chat_user_message 行（用户发消息时落库），返回本表原生自增 id。
    锚迁移(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): id 分配锚由
    chat_messages.lastrowid 显式指定 → 本表 AUTOINCREMENT 原生自增, user_message_id 入参退役;
    原 INSERT OR REPLACE 随显式 id 一并退役——自增 id 无撞键场景, 退化为普通 INSERT — 小欧 2026-08-23"""
    now = get_local_iso_timestamp()
    cursor = conn.execute(
        """INSERT INTO chat_user_message
           (session_id, content, client_os, browser, device, network, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (session_id, content, client_os, browser, device, network, now),
    )
    return cursor.lastrowid


def update_user_message_final(
    conn: Connection, *,
    user_message_id: int, task_id: str,
    response: str, reasoning: str = None,
    outcome: str = None, task_model: Optional[ModelRef] = None,
    accumulated_usage: str = None,
) -> None:
    """任务完成后回填 final 字段到 chat_user_message
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 两分离入参 → task_model: ModelRef 落 chat_model JSON 单列"""
    conn.execute(
        """UPDATE chat_user_message
           SET task_id=?, response=?, reasoning=?, outcome=?,
               chat_model=?, accumulated_usage=?
           WHERE id=?""",
        (task_id, response, reasoning, outcome,
         task_model.model_dump_json() if task_model else None,
         accumulated_usage, user_message_id),
    )


def load_user_message_by_task(conn: Connection, task_id: str) -> Optional[dict]:
    """按 task_id 读 chat_user_message（C1 详情用）
    2026-08-22 小欧 归一报告v1.25 6.3: chat_model JSON 派生 model/provider 键(键名不变)"""
    row = conn.execute(
        "SELECT * FROM chat_user_message WHERE task_id=?", (task_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    _cm = parse_session_model(d.pop("chat_model", None))
    d["model"] = _cm.model if _cm else None        # 键名保留供消费方渐进迁移 — 小欧 2026-08-22
    d["provider"] = _cm.provider if _cm else None
    return d


def load_user_messages_by_session(conn: Connection, session_id: str) -> list:
    """按 session_id 读 chat_user_message 列表（替代 chat_messages 读取）— 小欧 2026-08-21
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 键改由 chat_model JSON 列派生(旧列不再读取),
    复用 parse_session_model 唯一解析点(DRY)"""
    rows = conn.execute(
        "SELECT * FROM chat_user_message WHERE session_id=? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        _cm = parse_session_model(d.pop("chat_model", None))
        d["model"] = _cm.model if _cm else None       # 键名保留, 值源自新 JSON 列 — 小欧 2026-08-22
        d["provider"] = _cm.provider if _cm else None
        out.append(d)
    return out


def fetch_session_user_message_pairs(conn: Connection, session_id: str,
                           lower_id: Optional[int] = None,
                           upper_id: Optional[int] = None) -> list:
    """北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 本函数从 chat_user_message
    LEFT JOIN chat_tasks 重建"用户+AI"有序消息对(彻底去 chat_messages 读)。
    供 get_session_messages / _load_previous_messages / execution_stream 复用(10规范 DRY/复用优先)。
    返回 list[dict]: 每行一条 user 消息及其配对 assistant(ai_message_id 为 None 表示暂无 AI 回答),
    字段: user_id, user_content, ai_reasoning, model, provider, task_id, created_at, ai_message_id
    2026-08-22 小欧 归一报告v1.25 6.3: cum.model/cum.provider 两列 → cum.chat_model JSON 单列,
    返回 dict 的 model/provider 键由 chat_model 派生(键名不变, 旧列不再读取)"""
    sql = """SELECT cum.id AS user_id, cum.content AS user_content, cum.response AS ai_content,
                    cum.reasoning AS ai_reasoning,
                    cum.chat_model AS chat_model, cum.task_id AS task_id,
                    cum.created_at AS created_at, ct.ai_message_id AS ai_message_id
             FROM chat_user_message cum
             LEFT JOIN chat_tasks ct ON ct.user_message_id = cum.id
             WHERE cum.session_id = ?"""
    params: list = [session_id]
    if lower_id is not None:
        sql += " AND cum.id >= ?"
        params.append(lower_id)
    if upper_id is not None:
        sql += " AND cum.id < ?"
        params.append(upper_id)
    sql += " ORDER BY cum.id ASC"
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        _cm = parse_session_model(r["chat_model"])
        out.append({
            "user_id": r["user_id"],
            "user_content": r["user_content"],
            "ai_content": r["ai_content"],
            "ai_reasoning": r["ai_reasoning"],
            "model": _cm.model if _cm else None,      # 由 chat_model 派生 — 小欧 2026-08-22
            "provider": _cm.provider if _cm else None,
            "task_id": r["task_id"],
            "created_at": r["created_at"],
            "ai_message_id": r["ai_message_id"],
        })
    return out


# ====================================================================
# v2.0 C1/C2 任务级回放与统计存储（2026-08-19）
# ====================================================================

def get_task_detail(conn: Connection, task_id: str) -> Optional[dict]:
    """C1: 按 task_id 读 chat_tasks 单行详情
    2026-08-22 小欧 归一报告v1.25 6.3: 与 list_session_tasks 同模式——sessionModel JSON 派生
    model/provider 键(键名不变), 复用 parse_session_model 唯一解析点(DRY)"""
    row = conn.execute(
        "SELECT * FROM chat_tasks WHERE task_id=?", (task_id,),
    ).fetchone()
    if not row:
        return None
    _r = dict(row)
    _r["artifacts"] = parse_json(_r.get("artifacts")) if _r.get("artifacts") else []
    _sm = parse_session_model(_r.pop("sessionModel", None))
    _r["model"] = _sm.model if _sm else None       # 键名保留供消费方渐进迁移 — 小欧 2026-08-22
    _r["provider"] = _sm.provider if _sm else None
    return _r


def list_session_tasks(conn: Connection, session_id: str) -> Tuple[list, int, Optional[str]]:
    """B1/问题6(10.5): 会话任务列表 + 总数 + 最新任务id（任务数=用户消息数, 一条用户消息=一个任务;
    失败/取消亦计入, 与文档2 3.5.3 口径一致）。chat_tasks 行数即新统计口径 — 小欧 2026-08-20
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 两列 → sessionModel JSON 列派生(键名不变)
    2026-08-30 小欧 设计文档[2]第十二章 v1.103: 排序 DESC→ASC(左列时间线=4.3.2, 新任务在底部) +
    新增 latest_task_id(显式最新锚点, 顶栏/默认选中/结束沿token锚点统一消费, 解耦 8.C-④ DESC 一手双用)"""
    total = conn.execute(
        "SELECT COUNT(*) FROM chat_tasks WHERE session_id=?",
        (session_id,),
    ).fetchone()[0]
    rows = conn.execute(
        """SELECT task_id, user_input, response, status, duration, sessionModel,
                  total_steps, llm_call_count, context_link_mode,
                  created_at, updated_at
           FROM chat_tasks WHERE session_id=? ORDER BY id ASC""",
        (session_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        _sm = parse_session_model(d.pop("sessionModel", None))
        d["model"] = _sm.model if _sm else None       # 键名保留供消费方渐进迁移 — 小欧 2026-08-22
        d["provider"] = _sm.provider if _sm else None
        out.append(d)
    latest_task_id = out[-1]["task_id"] if out else None   # ASC 后最末行为最新任务, 显式锚点 — 小欧 2026-08-30
    return out, total, latest_task_id


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
    steps = [parse_json(r["step_json"], label="step_json") for r in rows]
    # 13.7 C2 两字段契约收口: thought 步骤剥离 content(回显只取 thought/reasoning, 13.3), 仅出 type/step/timestamp/thought/reasoning — 小欧 2026-08-30
    return [
        s if s.get("type") != "thought" else {k: v for k, v in s.items() if k != "content"}
        for s in steps
    ]
