# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 聊天流编排器(方案4.7.3步骤1)。从 api/v1/chat/openai.py 一次性全迁编排逻辑
#   (chat_stream generate 主体 / _stream_with_control / StreamState / generate_task_id / validate_chat_config /
#   _agent_tasks / step_start), 仅改导入归属, 业务逻辑一字不改(禁止 backward, 无兼容 shim)。依赖路径以真实代码为准:
#   create_stream_buffer/get_stream_buffer 取 app.services.task.task_state, task_cancel_check* 取 app.services.task.task_runtime。
#   orchestrator 不依赖 api/v1 的 DTO(API 层解包 ChatRequest 后传原始参数)。
# 2026-08-13 - 小沈 - BUG-32修复(三堂会审): except Exception 块内 cancel bg_task, 避免后台 agent 继续运行但前端收到错误的
#   状态不一致; bg_task 预初始化 None 防 NameError; cancel 后 run_agent_in_background 的 finally 仍执行 DB 保存(已产出结果不丢失)
# 2026-08-13 - 小沈 - P4 agent→chat反向引用回调解耦: agent_runner 删除对 chat 模块的直接 import,
#   持久化回调(allocate_and_insert_message/append_execution_step/finalize_message/save_execution_steps_to_db/
#   _load_previous_messages/_log_task_end)由本编排器构造 db_ops SimpleNamespace 注入 run_agent_in_background,
#   依赖方向变为 chat→agent 单向。6个属性与原 agent_runner 直接 import 的6个chat函数一一对应,KISS-DIRECT。
# 2026-08-14 - 小欧 - 改名名实相符引用同步: handlers.py→sse_events.py, stream.py→stream_reader.py(4处import更新, 行为不变)
# 2026-08-16 - 小欧 - S1/S2(10.1.4⑤⑥/10.1.7②): db_ops 扩展9属性(insert_task/update_task/insert_token 任务级读写),
#   白名单 context_link_mode + 链根计算注入 load_previous 闭包; load_previous 补传上界 upper_message_id=_user_msg_id;
#   agent 创建后 INSERT chat_tasks 任务行(provider/model 取 agent.llm_client); S2 model_override 编排层覆盖
# 2026-08-16 - 小欧 - S4(10.1.1③/10.1.7④): 取消 orchestrator 旁路(step_start 调用+函数删除), start 构造/emit 移入
#   react_cycle(initialize_run_state 后、while 前, 占 step 0); P4 注入模式: agent._start_step_factory 闭包捕获
#   chat 层装配数据(send_start_step/next_step/链字段/warning), react_cycle 内注入 system_prompt/context_summary 调用,
#   agent 层不 import chat 层; start 落库走 agent_runner 事件流(不再 execution_steps 双写)
# 2026-08-16 - 小欧 - S4 修正(三堂会审/老陈驱动): 删 _model_warning 提前 return 终态分支——S4 后 start 由 react_cycle
#   emit(带 warning 字段), 该分支会不发 start 直接 failed(config_error), 与 start 进 steps 设计冲突(退化);
#   warning 仅作 start 提示字段下传(不终止任务), 同步删 FinalStep/format_agent_sse 死 import
# 2026-08-17 - 小健 - 三堂会审修复(北京老陈驱动, 11 bug 复核3遍):
#   A1: line55 模块级统一 `from app.db import db`, 消除原 line245 裸引用 db 的 NameError(chat_tasks 永不建行)。
#   E2: line168-178 track(_user_message_ids) 内存 dict 重启即丢时, 从 DB 兜底取本会话最后一条 user 消息 id 作
#       linked 续聊 upper 上界(防链外/全部消息进上下文)。
#   AE: 覆盖共享单例 ai_service.model 前保存原值 _orig_model, finally 统一还原(消除单例持久污染/并发会话串 model);
#       _orig_model 预初始化 None 防无覆盖/取消时 NameError(边修 AE 时补该缺陷)。
# 测试: tests/test_s2_s4_review_bugs.py 16 passed, 相关4文件 52 passed。
# 2026-08-17 - 小健 - 必备日志补齐(老陈驱动): AE finally 还原单例 model 打 logger.info(并发审计点);
#   E2 DB 兜底恢复 upper 打 logger.info(诊断 track 缺失)。均仅落文件不刷 console。
# 2026-08-17 - 小健 - start 业务过程收敛(老陈驱动): 闭包 _start_step_factory 只做 P4 捕获传参,
#   context_summary 计算与 StartStep 构造收拢到 sse_events.build_start_step(单一归属); 删本文件 MessageBuilder 死 import
# 2026-08-17 - 小健 - start 业务彻底单归属(老陈驱动, 三思三省): 契约构造逻辑自 sse_events 迁入 start_step 模块,
#   本文件不再承载任何 start 业务——删除 _start_step_factory 闭包与 build_start_step/send_start_step import,
#   改将运行元数据 dict 注入 agent._start_meta(ai_service/task_id/next_step/user_input/session_id/链字段/warning),
#   react_cycle 经 assemble_start_step 从 _start_meta 读齐装配(chat 层退化为纯数据捕获, P4 方向不变)
# 2026-08-17 - 小健 - 最合理核查(老陈追问): _start_meta 删除 ai_service 键(DRY, 与 agent.llm_client 同对象),
#   仅保留 agent 拿不到的 chat 数据; start_step 直接读 agent.llm_client.provider/model — 小健 2026-08-17
# 2026-08-17 - 小健 - 全系统DRY扫描收敛(老陈指示按10大规范): _start_meta 再删 task_id 键(task_id 由 agent.task_id
#   权威持有, base_agent:59, 构造时注入); 仅保留 react_cycle 拿不到的必需运行数据(next_step/session_id/user_input/
#   链字段/warning); 与 ai_service 删除同属真冗余收敛(单一归属, 不退化) — 小健 2026-08-17
# 2026-08-17 - 小健 - 编排分区分号注释(老陈要求按编排步骤注清逻辑): chat_stream_orchestrator 增 ①~⑪ 分区分号
#   注释头(输入校验/取全局服务/算链根/建基元/取续聊边界/建agent/db_ops组装/_start_meta注入/后台任务/流式转发/
#   异常收尾); 仅加注释不改逻辑, 标明编排对象与依赖顺序 — 小健 2026-08-17
# 2026-08-17 - 小健 - 三堂会审深挖(北京老陈): task_cancel_check_and_yield 已删死参数, 调用点同步收敛,
#   不再白算 state.current_content 传入 — 小健 2026-08-17
# 2026-08-18 - 小欧 - §10.4.4 P2(弃用 next_step): 删 next_step = create_step_counter() 赋值; _start_meta 删 next_step 键;
#   run_agent_in_background 去 next_step 传参; _stream_with_control 签名/调用去 next_step; 删 create_step_counter import
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.2+9.4+9.6+9.9): db_ops.append_step加usage参数、
#   allocate_and_insert加user_message_id、insert_task加ai_message_id=None(agent_runner分配后回填)、
#   insert_task后回填chat_messages.task_id(改动7)、_db_ops注入user_msg_id(供agent_runner回填chat_user_message)
# 2026-08-20 - 小欧 - 11.1 token 四层同构: 两 db_ops lambda(insert_task/update_task)改用 storage.query_task/session_accumulation 读真实累计(去重 parse_json), 与 react_cycle 同源基线; 会话级首调用回退 task 累计
# 2026-08-20 - 小欧 - 11.1 修复: db_ops.update_task_accumulation/update_session_accumulation 闭包已绑 task_id/session_id, 原 agent_runner 又经 kwargs 重传致 Python "got multiple values" TypeError 被 except 吞掉→累计永不入DB; 去掉闭包绑定, 改由调用方经 **kw 传入(单一归属, KISS)
# 2026-08-21 - 小欧 - 12.2-Q3/C4(按文档[1]12.2 diff设计落地): ①Q3-D1 :83 导入追加 query_task_accumulation +
#   db_ops 命名空间新增 query_task_acc 条目(终态快照从权威累计列派生); ②C4-D1 编排⑨ eager 分配 assistant 行
#   (allocate_and_insert_message)+创建时即 UPDATE chat_tasks.ai_message_id, _ai_message_id 经 run_agent_in_background
#   新参注入; ③C4 连带清理——db_ops 删 allocate_and_insert 条目(唯一消费点 agent_runner 惰性分支已随 C4-D3 删除)、
#   删 save_steps 条目及 :87 save_execution_steps_to_db 导入(grep 证实仅服务该条目;    sse_events 函数本体保留)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 两处定: ①chat_messages 只写铁律: 编排⑥ _load_previous_messages 调用点改读
#     fetch_session_user_message_pairs(经 chat_user_message+chat_tasks 重建历史, 不读 chat_messages); ②L2 sessionModel 结构化: 读 get_session_model
#     覆盖 ai_service.provider+model(替原单 model_override), finally 双还原 provider+model(防单例污染)
# 2026-08-22 - 小欧 - 三堂会审复核整改(北京老陈 2026-08-22): 编排⑥消费点调用名由残留的 get_session_model_override 修正为 get_session_model(2026-08-22 改名后 import 已改、唯独调用点漏改, 此前任一会话请求必 NameError 崩溃, P0 修复); 因 get_session_model 现返回 SessionModelOverride(非 dict), 消费点改属性访问(.model/.provider, 去 .get/下标); 同步修正 line92 import 注释标明改名
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.3/6.5/6.8: 全链 ModelRef 归一——validate_chat_config 响应
#   provider/model 键归一 model_ref 结构; _orig_model/_orig_provider 双变量 → _orig_llm_model 单 ModelRef
#   原子覆盖/还原(KISS: 消除半覆盖中间态); [TASK_START] 日志 F8 属性迁移; insert_task/token_usage_insert
#   闭包改传 task_model=agent.llm_client.llm_model(ModelRef), display_name 不再拼装落库(设计要求2)
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P1): L2 覆盖与 finally 还原后各调 ai_service.reset_sdk()——SDK 缓存重建,
#   保 api_base/model 实连一致(配 base_service.reset_sdk 新方法)
# 2026-08-23 - 小欧 - 修复P3-2: L265 display_name 补 fallback 逻辑，session 未设置时继承原配置 display_name
# 2026-08-23 - 小欧 - 锚迁移(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): W6 镜像写点
#   (user 消息回填 task_id 的 UPDATE chat_messages)加 TODO 删除注释; :278 _user_msg_id 注释修正为
#   "chat_user_message.id 原生自增权威锚"(原"与chat_messages.id一对一"口径随锚迁移过时)
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档[1]11.8.3 D1/11.8.7.1 D7/11.9 P5): 编排⑨事务内
#   allocate_and_insert_message 之后调 create_task_writer 建 A/B 双文件+header 并挂载 agent.file_persist
#   (局部导入 file_persist/time_utils, #11 必需); model 取 agent.llm_client.llm_model(ModelRef dump);
#   同事务 UPDATE chat_tasks SET files_dir='files/{session_id}/{task_id}/'($dir 排查定位锚, 不重复落文件名)
# 2026-08-24 - 小欧 - 后端卡死修复: 编排⑨事务内落库(insert_task/user消息回填/eager分配assistant+写chat_tasks.ai_message_id/files_dir)整体经 db.atxn 进子线程 offload 出事件循环,
#   loop 不再被同步写大blob+time.sleep锁重试独占, 根治 /health 超时/console 冻结; storage.* 与连接管理零改动复用;
#   create_task_writer(非DB文件写)移出事务块: 成功路径等价, 失败路径更稳(writer 创建失败不再连坐回滚任务落库事务, 任务行保留、file_persist 缺失由 getattr 守卫兜底)
# 2026-08-24 - 小欧 - 后端卡死修复收尾(offload): 编排③链根查询/编排⑤DB兜底user_msg_id/编排⑥sessionModel读取 三处同步 db.get_conn
#   改经 db.atxn 进子线程 offload 出事件循环(复用既有薄壳, 行为等价), 请求编排期 loop 零同步 DB I/O
# 2026-08-24 - 小欧 - 目录前导(北京老陈裁定): chat_tasks.files_dir 落库锚同步改为 files/Sion_{session_id}/Task_{task_id}/,
#   与 TaskFileWriter 物理目录经 file_persist 前缀常量同源拼装(DRY), 排查定位链不断; 旧目录不迁移(禁止backward)
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整体移除W6镜像写点(_setup_task_db内UPDATE chat_messages SET task_id), 系统对该表零写依赖
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 删除finalize_message的import与db_ops.finalize=传参(随finalize_message整删, 终态由append_execution_step/chat_tasks承载)
# 2026-08-28 小欧 - yield日志审计: 编排①输入校验失败/编排②启动前已取消 两处 yield 前补 logger(warning/info), 覆盖7个无日志yield(KISS); 三堂会审无逻辑修正
# 2026-08-29 - 小沈 - 修复#5(彻底快照): 病根为 sessionModel 覆盖直接改进程单例 llm_model(全局副作用, 还原时序竞态致断连误模/跨会话串模)。改为构造本会话独立 LLM 客户端快照(ai_service.snapshot), 后台任务/流均用快照, 单例恒为全局默认不再被污染, 根除两类退化; run_agent_in_background finally 关闭快照释放连接池
# 2026-09-01 - 小欧 - [TASK_START]日志修复(北京老陈驱动): 原在会话覆盖快照生效(编排⑥)之前用 ai_service.llm_model(全局默认)打印, 且 model 字段显示全局而非实际生效模型, 误导排查(如本次会话覆盖 deepseek-v4-flash 生效, 日志却显 agnes)。移至覆盖快照生效后用 agent.llm_client.llm_model(实际生效客户端)打印
# 2026-09-01 - 小欧 - L2 会话级切跨 provider 模型修复(北京老陈驱动, 503/AgnesAI_error): 编排⑥覆盖生效块
#   按目标 provider+model 从 config.yaml 查 api_base/api_key(经 get_ai_config_resolver().get_service_config)+
#   model_params(复用 service.parse_model_params, DRY 唯一权威): 此前仅传 provider/model, 快照沿用全局
#   agnes 的 api_base/api_key/model_params→切 sensenova 仍 503。api_base 必须用目标 provider 的而非 _ov.api_base;
#   并入 snapshot(api_key/extra_body_params/context_limit 三参); 同步 agent._task_llm_model 为生效快照模型,
#   使 react_cycle/telemetry 日志显示真实生效模型(消除显 agnes 盲点); api_key 后端查配置, 不落库不出前端
# 2026-09-02 小欧 三堂会审task005-BUG-004修复: 配置查找失败显式置空(_pv_cfg/_pv_key/_pv_ebp/_pv_ctx),
#   原仅warning无置空, 虽初始化为None但显式表达降级意图, 日志补"放弃会话模型覆盖"便于排查
"""
stream_orchestrator — 聊天流编排器(services 层)

职责(方案4.7.3, 小欧 2026-08-13): 负责任务生命周期、Agent 后台启动、SSE 消费编排。
API 层只保留路由薄壳, 编排逻辑单一归属本模块(SRP/SLAP)。
"""
import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Optional, AsyncGenerator, Dict, List

from app.services import get_service
from app.services.model.resolver import get_ai_config_resolver
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.logger import logger, log_and_print
from app.services.chat.sse_events import create_error_response
from app.services.task.task_registry import register_task
from app.services.task.task_runtime import (
    task_cancel_check, task_pause_check_and_yield, task_cancel_check_and_yield,
)
from app.services.chat.stream_reader import stream_reader
from app.services.agent.agent_runner import run_agent_in_background
from app.services.agent.universal_agent import UniversalAgent
from app.services.task.task_state import create_stream_buffer, get_stream_buffer
from app.services.task.task_context import _current_task_id
from app.logger.shared_handler import set_session_id
from app.services.chat.storage import get_user_message_id, allocate_and_insert_message, append_execution_step, query_task_accumulation  # 12.2-Q3: 追加权威累计查询 — 小欧 2026-08-21
from app.services.chat.storage import insert_task, update_task, token_usage_insert, get_session_model, get_previous_task_chain  # S1/S2 任务级读写(10.1.4/10.1.7②); get_session_model 为 2026-08-22 由 get_session_model_override 改名(北京老陈 2026-08-22 L2 结构化)
from app.services.chat.storage import update_task_accumulation, update_session_accumulation  # 11.1 token 四层同构累计 — 小欧 2026-08-20
from app.db import db  # 小健 2026-08-17 三堂会审-A1修复: 模块级统一导入 db, 消除 line245 裸引用 db 的 NameError(chat_tasks 永不建行)
from app.services.chat.stream_reader import _load_previous_messages, _log_task_end


# 后台 agent 任务强引用表: asyncio 仅持有 Task 弱引用, 若 SSE 消费者(generate)断开后任务再无强引用,
# 会被 GC 回收并取消, 导致 run_agent_in_background 的 finally(DB 保存)被打断、结果丢失(问题2)。
# 与 agent_runner._background_tasks 双重保险(后者 caller-agnostic): 本表在调用点持有引用,
# done 时 discard 防内存泄漏 — 小欧 2026-07-13(自 openai.py 迁入)
_agent_tasks: set = set()


def generate_task_id() -> str:
    """生成统一格式 task-{hex}，全链路唯一贯通 — 小欧 2026-07-16(自 openai.py 迁入)"""
    return f"task-{uuid.uuid4().hex}"


async def validate_chat_config():
    """聊天配置校验 — 自 api/v1/chat/openai.py 迁入 orchestrator — 小欧 2026-08-13
    2026-08-22 小欧 归一报告v1.25 6.6: resolver.validate_config 返回 (is_valid, ModelRef, errors);
    响应键 provider/model 归一为 model_ref 结构(方案B 前端随后端)"""
    from app.logger import logger
    try:
        resolver = get_ai_config_resolver()
        is_valid, config_model, error_messages = resolver.validate_config()
        if not is_valid:
            return {
                "valid": False,
                "message": f"配置验证失败: {', '.join(error_messages)}",
                "model_ref": {"provider": config_model.provider or "unknown",
                              "model": config_model.model or ""},
            }
        return {
            "valid": True,
            "message": f"配置验证通过: {config_model.provider} ({config_model.model})",   # 文本派生, 允许
            "model_ref": {"provider": config_model.provider, "model": config_model.model},
        }
    except Exception as e:
        logger.error(f"验证AI服务配置失败: {e}")
        return {
            "valid": False,
            "message": f"验证失败: {str(e)}",
            "model_ref": None,
        }


@dataclass
class StreamState:
    """流式状态 — 【修复P3-5】明确语义 — 北京老陈 2026-06-13(自 openai.py 迁入)"""
    llm_call_count: int = 0
    current_content: str = ""
    current_thought: str = ""  # 小欧 2026-07-16
    step_events: list = None

    def __post_init__(self):
        if self.step_events is None:
            self.step_events = []


async def chat_stream_orchestrator(
    messages: list,
    session_id: Optional[str] = None,
    context_link_mode: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """聊天流编排入口：负责任务生命周期、Agent 启动、SSE 消费。

    由 API 层解包 ChatRequest 后以 (messages, session_id) 调用；services 层不反向依赖 api/v1 DTO。
    2026-08-16 - 小欧 - S1: 增 context_link_mode(任务上下文链, 10.1.4);
      白名单校验(10.1.4⑧): 非法值/缺失一律按 independent, 防误灌历史(防退化)
    """
    # ── 编排①输入校验(链模式白名单 + 消息非空) ———————————————————————————— 小健 2026-08-17
    # 白名单校验(10.1.4⑧): {"linked","independent"} 之外的非法值按 independent 处理并记 warning
    if context_link_mode not in ("linked", "independent"):
        if context_link_mode is not None:
            logger.warning(f"[chat] context_link_mode 非法值 '{context_link_mode}', 按 independent 处理")
        context_link_mode = "independent"
    if not messages:
        # 2026-08-28 小欧 yield日志审计: 输入校验失败日志(KISS)
        logger.warning("[chat] 输入校验失败: 消息列表为空")
        yield create_error_response(error_type="invalid_request", error_message="消息列表不能为空")
        return
    user_input = messages[-1].content or ""
    if not user_input.strip():
        # 2026-08-28 小欧 yield日志审计: 输入校验失败日志(KISS)
        logger.warning("[chat] 输入校验失败: 消息内容为空")
        yield create_error_response(error_type="invalid_request", error_message="消息内容不能为空")
        return

    # ── 编排②取全局服务(LLM单例/model警告/task_id) ————————————————————————— 小健 2026-08-17
    ai_service = get_service()
    session_id = session_id or str(uuid.uuid4())
    _model_warning = get_ai_config_resolver().pop_model_warning()

    task_id = generate_task_id()
    # ── 编排③算任务上下文链根(linked继承 / independent自为链根) ————————————————— 小健 2026-08-17
    # S1 上下文链计算(10.1.4④⑧)：context_root_task_id
    #   linked=续聊(需显式): 继承本会话最近一条成功任务的链根(曾续则沿链根); 无成功任务则=自身
    #   independent=新任务(默认): =自身(从零自为链根)；cancelled/failed 不继承(防链到失败任务)
    _context_root_task_id = task_id
    if context_link_mode == "linked" and session_id:
        _prev_chain = None
        try:
            # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
            _prev_chain = await db.atxn("chat", lambda conn: get_previous_task_chain(conn, session_id))
        except Exception as _e:
            logger.warning(f"[chat] 取上一任务链根失败(session={session_id}): {_e}")
        if _prev_chain:
            _context_root_task_id = _prev_chain["context_root_task_id"]
    _task_token = _current_task_id.set(task_id)  # try/finally reset, 防 ContextVar 泄漏(方案4.7.3与A4对齐)
    set_session_id(session_id)
    # ── 编排④建运行基元(步号计数器 + SSE流状态容器) ———————————————————————————— 小健 2026-08-17
    # 2026-08-18 小欧 P2(§10.4.4): 删 next_step = create_step_counter()(step 统一 agent.llm_call_count 口径)
    execution_steps = []
    state = StreamState()

    # ── 编排⑤取续聊历史边界(user_msg_id 上界, 服务重启DB兜底) ——————————————————— 小健 2026-08-17
    _task_start_time = time.time()
    _user_msg_id = None
    try:
        _user_msg_id = get_user_message_id(session_id)
    except Exception:
        logger.warning(f"[chat] 获取user_message_id失败: session_id={session_id}")
    # 小健 2026-08-17 三堂会审-E2修复: track 为内存 dict(重启即丢), 缺失时从 DB 兜底取本会话最后一条
    #   user 消息 id 作为 linked 上界, 修复"服务重启后用第二任务续聊"时 upper=None 上界失效令链外/全部消息进上下文
    if not _user_msg_id and session_id:
        try:
            from app.services.chat.storage import get_last_user_message_id
            # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
            _row_u_id = await db.atxn("chat", lambda conn: get_last_user_message_id(conn, session_id))
            if _row_u_id:
                _user_msg_id = _row_u_id
                logger.info(f"[chat] E2 track缺失, DB兜底恢复upper: session={session_id}, user_msg_id={_user_msg_id}")
        except Exception as _eu:
            logger.warning(f"[chat] DB兜底取user消息id失败(session={session_id}): {_eu}")
    log_and_print(f"INFO: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    bg_task = None  # BUG-32修复: 预初始化, 防 except 块 NameError — 小沈 2026-08-13
    try:
        buffer = create_stream_buffer(task_id)
        await register_task(task_id, ai_service)

        is_cancelled, cancel_msg = await task_cancel_check(task_id)
        if is_cancelled:
            # 2026-08-28 小欧 yield日志审计: 任务已取消日志(KISS)
            logger.info(f"[chat] 任务启动前已取消: task={task_id}")
            yield cancel_msg
            return

        # ── 编排⑥建 UniversalAgent + 会话sessionModel(先建才有 llm_client) ——— 小健 2026-08-17
        agent = UniversalAgent(llm_client=ai_service, task_id=task_id)
        # S2 sessionModel 生效(10.1.7②-4/文档2 6.1.1/6.1.8)：编排层读会话覆盖写 ai_service.llm_model(L2 结构化)
        #   归一(小欧 2026-08-22 报告v1.25 6.5): 整个 ModelRef 单变量原子切换——缺省键回退原值合并,
        #   消除原逐属性赋值的半覆盖中间态(KISS-DIRECT 纯增强)
        if session_id:
            try:
                # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
                _ov = await db.atxn("chat", lambda conn: get_session_model(conn, session_id))
                if _ov and (_ov.model or _ov.provider):
                    # 病根修复(小沈 2026-08-29): 旧实现直接改共享单例 ai_service.llm_model + reset_sdk,
                    # 是"用全局副作用表达每会话模型", 单例还原时序竞态→断连后台任务误模/跨会话串模(#5)。
                    # 改为构造本会话独立 LLM 客户端快照(携带覆盖模型), 与进程单例解耦: 会话流与后台任务均用快照,
                    # 共享单例恒定全局默认不变, 不再需要 finally 还原, 根除 #5 两类退化(含断连后跨会话泄漏窄边界)。
                    # 2026-09-01 小欧: L2 切跨 provider 模型, api_base/api_key/model_params(含 context_limit)
                    # 均按目标 provider+model 从 config.yaml 查出(后端内部, 不落库、不出前端);
                    # api_base 必须用目标 provider 的, 而非 _ov.api_base or 全局(全局=agnes 地址, 仍 503)
                    _pv_cfg = None
                    _pv_key = None
                    _pv_ebp = None
                    _pv_ctx = None
                    if _ov.provider and _ov.provider != ai_service.llm_model.provider:
                        try:
                            _pv_cfg = get_ai_config_resolver().get_service_config(
                                _ov.provider, _ov.model or "")
                            _pv_key = (_pv_cfg.get("api_key") or "").strip() or None
                            # model_params 解析复用 service.parse_model_params(DRY 唯一权威, 与全局实例同逻辑)
                            from app.services.lifecycle.service import parse_model_params
                            _pv_ebp, _pv_ctx = parse_model_params(_pv_cfg, _ov.model or "")
                        except Exception as _pv_e:
                            logger.warning(f"[chat] 按 provider 查配置失败({_ov.provider}): {_pv_e}, 放弃会话模型覆盖")
                            _pv_cfg = None
                            _pv_key = None
                            _pv_ebp = None
                            _pv_ctx = None
                    override_ref = ModelRef(
                        provider=_ov.provider or ai_service.llm_model.provider,
                        model=_ov.model or ai_service.llm_model.model,
                        api_base=(_pv_cfg or {}).get("api_base") or ai_service.llm_model.api_base,
                        display_name=_ov.display_name or ai_service.llm_model.display_name,
                    )
                    session_client = ai_service.snapshot(
                        override_ref,
                        api_key=_pv_key,
                        extra_body_params=_pv_ebp,
                        context_limit=_pv_ctx,
                    )
                    agent.llm_client = session_client
                    # 2026-09-01 小欧: 同步 _task_llm_model 为生效快照模型, 使 react_cycle 日志/telemetry
                    # 显示真实生效模型(而非全局 agnes), 与 TASK_START 显示实际生效模型同一精神
                    agent._task_llm_model = getattr(session_client, "llm_model", None)
                    logger.info(f"[chat] L2 sessionModel 已生效(独立客户端快照): session={session_id}, "
                                f"provider={session_client.llm_model.provider}, model={session_client.llm_model.model}")
            except Exception as _ov_e:
                logger.warning(f"[chat] 读会话sessionModel失败(session={session_id}): {_ov_e}")
        # ── [TASK_START] 在会话覆盖快照生效后打印, 用 agent.llm_client(实际生效模型)非全局默认
        #    (修复: 原先打印 ai_service.llm_model 是全局默认且时机在覆盖前, 误导排查) — 小欧 2026-09-01
        log_and_print(
            f"[TASK_START] provider={agent.llm_client.llm_model.provider} model={agent.llm_client.llm_model.model} |\n "
            f"task_id={task_id} session_id={session_id} "
            f"user_message_id={_user_msg_id} |\n "
            f"user_input={user_input}"
        )
        # ── 编排⑦组装 db_ops 持久化回调命名空间(经闭包注入后台, 依赖 ⑥ agent) ——— 小健 2026-08-17
        # P4: 构造 db_ops 命名空间注入 agent_runner, 消除 agent→chat 反向依赖 — 小沈 2026-08-13
        #   10.1.7②-1 9属性(任务级读写扩展) — 小欧 2026-08-16
        import types as _types
        _db_ops = _types.SimpleNamespace(
            append_step=lambda c, mid, sid, idx, d, usage=None: append_execution_step(c, mid, sid, idx, d, task_id, usage=usage, user_message_id=_user_msg_id),  # _user_msg_id即chat_user_message.id（原生自增权威锚, 北京老陈 2026-08-23 锚迁移）— 小健 2026-08-19 P1-4
            load_previous=lambda sid: _load_previous_messages(  # 任务上下文过滤(10.1.4⑤⑥)，经闭包注入链路计算的 context 两字段+上界(_user_msg_id)
                sid, context_link_mode=context_link_mode, context_root_task_id=_context_root_task_id,
                upper_message_id=_user_msg_id),
            log_task_end=_log_task_end,
            insert_task=lambda c: insert_task(  # ②-1 chat_tasks 创建 — 归一: task_model 传 ModelRef, display_name 不再拼装落库(设计要求2) — 小欧 2026-08-22
                c, task_id=task_id, session_id=session_id, user_message_id=_user_msg_id,
                ai_message_id=None,  # agent_runner 分配后回填 — 小欧 2026-08-19
                user_input=user_input, context_link_mode=context_link_mode,
                context_root_task_id=_context_root_task_id,
                task_model=agent.llm_client.llm_model),
            update_task=lambda c, **kw: update_task(c, task_id=task_id, **kw),  # ②-1 chat_tasks 终态
            insert_token=lambda c, **kw: token_usage_insert(  # ②-3 共用 — 归一: task_model 传 ModelRef — 小欧 2026-08-22
                c, task_id=task_id, session_id=session_id,
                task_model=agent.llm_client.llm_model, **kw),
            update_task_accumulation=lambda c, **kw: update_task_accumulation(c, **kw),  # 11.1 任务级token累计(去闭包双重绑定, 由调用方经**kw传task_id)
            update_session_accumulation=lambda c, **kw: update_session_accumulation(c, **kw),  # 11.1 会话级token累计(去闭包双重绑定, 由调用方经**kw传session_id)
            query_task_acc=lambda c, **kw: query_task_accumulation(c, **kw),  # 12.2-Q3/C3: 终态快照从权威累计列派生 — 小欧 2026-08-21
            user_msg_id=_user_msg_id,  # v2.0 改动2: 供agent_runner回填chat_user_message — 小欧 2026-08-19
        )
        # ── 编排⑧注入 start 运行元数据(_start_meta, start_step 装配用) ———————— 小健 2026-08-17
        # S4/S5(10.1.1③/10.1.7④): start 运行元数据注入 agent — 取消 orchestrator 旁路(step_start),
        #   start 业务完整归 start_step 模块(chat 层仅 P4 捕获运行数据注入 agent._start_meta),
        #   react_cycle 经 assemble_start_step 从 _start_meta 读齐装配, 不再有 chat 层 start 构造逻辑 — 小健 2026-08-17
        #   只注入 agent 拿不到的 chat 运行数据: task_id(agent.task_id 已持有)、provider/model(agent.llm_client
        #   已持有)、user_input? 见下——next_step/session_id/链字段/warning 为必需 (react_cycle 无权威源)
        #   2026-08-17 小健 收敛真冗余: task_id 由 agent.task_id 权威持有(base_agent:59), 不重复注入; 余键保留
        agent._start_meta = {
            "user_input": user_input,
            "session_id": session_id,
            "context_link_mode": context_link_mode,
            "context_root_task_id": _context_root_task_id,
            "warning": _model_warning,
        }
        # ── 编排⑨落库任务行 + 建后台 agent 任务(asyncio.create_task 独立运行) ——— 小健 2026-08-17
        # ②-1 落点：建 agent 后、后台运行前 INSERT 任务行(provider/model 取 agent.llm_client) — 小欧 2026-08-16
        _ai_message_id = None
        try:
            # 目录前导常量局部导入(北京老陈 2026-08-24): files_dir 落库锚与物理目录唯一同源(DRY, 前缀定义于 file_persist)
            from app.file_persist import SESSION_DIR_PREFIX, TASK_DIR_PREFIX
            # ②-1 落库热路径 offload 出事件循环(后端卡死修复 小欧 2026-08-24):
            #   原 `with db.get_conn_with_retry` 在 loop 主线程同步写大 blob + time.sleep 锁重试,
            #   致 loop 被独占、/health 超时; 整段 DB 操作经 db.atxn 进子线程, conn 同线程闭环零跨线程。
            def _setup_task_db(conn):
                _db_ops.insert_task(conn)
                # v2.0 改动7: user 消息回填 task_id — 小欧 2026-08-19
                # 镜像写点 W6(UPDATE chat_messages SET task_id) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27
                # 12.2-C4: eager分配assistant行+创建时即写chat_tasks.ai_message_id —
                #   任务启动即分配(原首步惰性), 消除agent_runner finally legacy save_steps分支
                #   (步骤丢失/覆写旧消息双风险根除) — 小欧 2026-08-21
                _aid = allocate_and_insert_message(conn, session_id, task_id, user_message_id=_user_msg_id)
                conn.execute(
                    "UPDATE chat_tasks SET ai_message_id=? WHERE task_id=?",
                    (_aid, task_id),
                )
                # D7/#5(2026-08-23): 11.7.5-1 落库 $dir 引用(物理目录 = files/Sion_{session_id}/Task_{task_id}/,
                #   前导 2026-08-24 北京老陈裁定, 与 TaskFileWriter._dir 同源常量拼装),
                #   供排查定位(任务→files_dir→文件A 按 step/tool_no/retry_no 定位块→文件B); 不重复落库文件名 — 小欧 2026-08-23
                conn.execute(
                    "UPDATE chat_tasks SET files_dir=? WHERE task_id=?",
                    (f"files/{SESSION_DIR_PREFIX}{session_id}/{TASK_DIR_PREFIX}{task_id}/", task_id),
                )
                return _aid
            _ai_message_id = await db.atxn("chat", _setup_task_db)
            # 11.8-H1/D1: 文件A/B 创建(header)——assistant 分配即建(11.7.4-4); 创建后挂载
            #   agent.file_persist 供 agent 层钩子使用(telemetry 同模式, agent 零 chat 依赖) — 11.9 P5 — 小欧 2026-08-23
            #   非DB文件写, 移出DB事务块(后端卡死修复 offload 小欧 2026-08-24):
            #   成功路径等价; 失败路径更稳——writer 创建失败不再连坐回滚任务落库事务(仅告警),
            #   任务行/ai_message_id 已持久化, agent.file_persist 缺失由下游 getattr 守卫兜底
            from app.file_persist import create_task_writer
            from app.utils.time_utils import get_local_iso_timestamp  # 局部导入必需(#11: 顶层无该符号, 缺则 NameError 被吞降级无文件)
            _mr = getattr(getattr(agent, "llm_client", None), "llm_model", None)
            agent.file_persist = create_task_writer(
                session_id=session_id,
                task_id=task_id,
                ai_message_id=_ai_message_id,
                start_time_iso=get_local_iso_timestamp(),
                model=(_mr.model_dump(exclude_none=True) if hasattr(_mr, "model_dump") else None),
            )
        except Exception as _task_e:
            logger.warning(f"[chat] chat_tasks INSERT/eager分配失败(task={task_id}): {_task_e}")
        # 持有强引用，防 GC 回收导致任务被取消→打断 DB 保存(问题2修复) — 小欧 2026-07-13
        bg_task = asyncio.create_task(run_agent_in_background(
            agent, task_id, user_input, None, session_id, state, _task_start_time,
            db_ops=_db_ops, ai_message_id=_ai_message_id))
        _agent_tasks.add(bg_task)
        bg_task.add_done_callback(_agent_tasks.discard)

        # ── 编排⑩流式转发(消费后台 agent 产出的 SSE → 转前端) ————————————————— 小健 2026-08-17
        async for sse_chunk in _stream_with_control(buffer, task_id, session_id, execution_steps, state):
            yield sse_chunk
    # ── 编排⑪异常/收尾(断连静默/异常取消后台/reset ContextVar) ———— 小健 2026-08-17; 小沈 2026-08-29 bug#5: 去 finally 还原单例副作用
    except asyncio.CancelledError:
        # 客户端断开：静默返回，agent 后台继续运行 — 北京老陈 2026-07-12 小欧 2026-07-12
        logger.info(f"[chat_stream_orchestrator] 客户端断开(task={task_id})，agent 后台继续")
        return
    except Exception as e:
        logger.error(f"[chat_stream_orchestrator] Error: {e}", exc_info=True)
        # BUG-32修复(三堂会审 小沈 2026-08-13): orchestrator 异常时 cancel bg_task, 避免后台继续运行但前端收到错误的状态不一致;
        #   bg_task 已启动(若进入 try 块内), cancel 后 run_agent_in_background 的 finally 仍会执行 DB 保存(已产出结果不丢失)。
        try:
            if bg_task and not bg_task.done():
                bg_task.cancel()
                logger.info(f"[chat_stream_orchestrator] 已取消后台 agent 任务: {task_id}")
        except Exception as _ce:
            logger.warning(f"[chat_stream_orchestrator] 取消 bg_task 失败: {_ce}")
        yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
    finally:
        _current_task_id.reset(_task_token)


async def _stream_with_control(buffer, task_id: str, session_id: str,
                               execution_steps: list, state=None, after_seq: int = 0):
    """SSE 消费者包装：读缓冲 + 注入 pause/cancel 检查 — 自 openai.py 迁入 — 小欧 2026-08-13

    首次请求(after_seq=0)与重连请求(after_seq=N)共用本函数，DRY。
    客户端断开时 CancelledError 向上传播，由 orchestrator 捕获。
    2026-08-18 小欧 P2(§10.4.4): 删 next_step, task_pause/cancel_check 步号统一 _current_step(task_id)
    """
    async for sse_chunk in stream_reader(buffer, task_id, after_seq):
        async for pause_event in task_pause_check_and_yield(task_id):
            yield pause_event
        cancelled_sse = await task_cancel_check_and_yield(
            task_id, execution_steps)
        if cancelled_sse:
            yield cancelled_sse
            return
        yield sse_chunk


async def chat_stream_reconnect_orchestrator(
    task_id: str, session_id: Optional[str] = None, after_seq: int = 0
) -> AsyncGenerator[str, None]:
    """SSE 重连编排：读同一任务的流态缓冲，不启动新 agent — 自 openai.py 迁入 — 小欧 2026-08-13"""
    buffer = get_stream_buffer(task_id)
    if not buffer:
        yield create_error_response(error_type="not_found", error_message="任务不存在或已结束")
        return
    async for sse_chunk in _stream_with_control(
        buffer, task_id, session_id or "", [], None, after_seq
    ):
        yield sse_chunk