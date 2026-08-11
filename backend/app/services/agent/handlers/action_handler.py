
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 小欧 add_tool_result异常日志带类型与repr
# 2026-07-16 小欧 op_id双表贯通修复
# 2026-07-17 小欧 handle_action执行工具后重置_consecutive_reasoning_only(空转检测: 本步LLM发起工具调用=非reasoning-only空转, 归零)
# 2026-07-17 小欧 计数器修正: handle_action-tool_name空early-return处补归零(空转检测非reasoning-only出口完备, 不变量严格成立)
# 2026-07-18 小欧 #4 fix: _file_tool_names从模块函数名改为注册名(delete/copy/move/edittext/writetext/compress),op_id双表贯通恢复
# 2026-07-18 小欧 #11 fix: wait_for_confirmation_result超时返回expired=True;超时/拒绝分流
# 2026-07-18 小欧 #12 fix: check_safety_and_confirm拒绝不再return终止整批,收集_denied后继续,最终只执行通过的call
# 2026-07-18 小欧 FinalStep多态自包含终态重构:
#   【病根】原FinalStep无outcome字段, 终态语义隐含在type中,
#          action_handler中return_direct提前返回的FinalStep缺少显式终态声明,
#          与answer_handler/agent_runner的终态产出不一致。
#   【改法】在return_direct分支的FinalStep中显式添加outcome="completed",
#          使所有终态产出点均有显式outcome声明, 与FinalStep多态设计契约一致。
#   [原来] for循环内对每个call查file_operations「最新」op_id写task_operations
#   [问题] ①非文件工具(searchtool等)误关联文件op_id ②同轮多文件工具抢同一op_id撞UNIQUE(constraint failed)
#   [根因] action_handler在"所有工具返回后统一处理"循环中, 查"最新"在多工具同轮时顺序错乱/抢占
#   [改法] 循环外预取file_operations「未写入task_operations」的op_id候选队列, 循环内仅文件类工具(白名单6个)按call顺序pop(0)取用, 非文件工具op_id=None自生成
#   [原理] ①文件工具call顺序==file_operations写入顺序(同轮顺序执行), 升序候选队列+顺序pop精确一一对应
#          ②用"FO未写入TO的op_id"做差集, 天然排除已消耗项, 杜绝UNIQUE冲突
#          ③白名单隔离非文件工具使其不参与贯通(op_id=None自生成), 消除误关联
#          ④纯内部取id(不读result/LLM字段), 符合"operation_id是agent内部字段严禁进LLM返回结构"铁律
# 2026-07-18 小欧 #4 fix: _file_tool_names 白名单值从模块函数名(delete_file等)改为注册名(delete等); 因 call["tool_name"] 是注册名, 原白名单恒 False 致 op_id 双表贯通完全失效
# 2026-07-18 小欧 #11+#12 fix: check_safety_and_confirm 重构 — 超时与拒绝分流(expired标记); 拒绝不return终止整批, 收
#   集_denied后continue, 最终只执行通过的call(通过_out参数回传过滤后列表); 调用方对应改_exec_calls
# 2026-07-19 小欧 build_observation/_add_denial_feedback新增reasoning参数传递
# 2026-07-21 小欧 - #4 自动纠正: 新增 _auto_correct_file_tool + _EXT_TO_READ/WRITE_TOOL 映射, execute_tools 入口扩展名预检自动切换 tool_name, 结果中 llm_data.summary 追加"(工具自动纠正自:{原始名})"
# 2026-07-23 小欧 - log_and_print统一: 删局部_log_and_print函数, 改为import from app.logger.log_and_print; execute_tools中3处logger.info()+print()替换为log_and_print()
# 2026-07-23 小欧 - 局部常量迁移: 删 _MAX_LOG_RESULT_CHARS=5000,
#            改为 from app.constants import ACTION_LOG_RESULT_MAX_CHARS
# 2026-07-25 - 小欧 - 修复readmedia被自动纠错为readtext: _auto_correct_file_tool fallback硬编码"readtext"→tool_name, 无专用映射时不篡改原工具
# 2026-07-25 小欧 - 三分类映射表重构: _EXT_TO_READ/WRITE_TOOL换用file_type_checker常量(TEXT_EXTENSIONS/MEDIA_EXTENSIONS)构建, 删fallback; _auto_correct_file_tool简化: None短路+!=判断; 文本→readtext/文档→专用工具/多媒体→readmedia 三分类全覆盖
# 2026-07-25 小欧 - task006-issue1: operation_id候选查询加task_id类型守卫(isinstance str/int); 非str/int提前短路并降WARNING为DEBUG, 消除测试环境MagicMock刷52次WARNING噪声
# 2026-07-25 小欧 - 回退上述类型守卫: 根因在测试fixture缺task_id而非生产代码(生产代码generate_task_id()永远返回str), 改为测试fixture源头修复; 生产代码恢复原始try-except
# 2026-07-25 小欧 - 欧阳报告缺陷修复:
# 2026-07-28 - 小欧 - BUG#3: _exec_calls原写法_safe_calls or call_result.all_calls, 当_safe_calls为空列表(所有调用均被安全拒绝)时回退到all_calls(含被拒绝调用), 完全绕过安全检查。改为_safe_calls if _safe_calls else [], 拒绝后执行空列表。
#   缺陷1: 删_build_call_list中tool_name空检查的重复日志(DRY, handle_action已兜底ErrorStep+return)
#   缺陷2: build_observation统一call字典访问为.get()防KeyError(与同函数内.get()混用修一致)
#   缺陷3: _correction_map改用enumerate索引替代id(call)(更直观,符合KISS-DIRECT)
#   缺陷4: check_safety_and_confirm拒绝反馈改为循环所有_denied(原只给第一个)
#   缺陷5: _has_conflict跳过无别名工具时补path兜底冲突检测(漏报文件路径竞态)
# 2026-07-30 - 小沈 - ContextVar注入: 导入set_current_task_id; handle_action入口加set_current_task_id(agent.task_id)
# 2026-07-30 - 小沈 - except:pass补日志: add_tool_result双层catch失败改为logger.debug记录
# 2026-07-30 - 小欧 - auto_confirm校验: SafetyResult.auto_confirm=True时不等确认直接通过, 提示照出但SUSPENDED不挂起 — 北京老陈驱动三堂会审
# 2026-07-31 - 小欧 - 撤销auto_confirm: action_handler删auto_confirm判断块, 恢复wait_for_confirmation_result等待逻辑
# 2026-08-03 - 小沈 - P0-01 E2E修复: 重加auto_confirm消费块(07-30加→07-31撤→重加缺失一半, 仅残留checker返回+字段)
#           与tool_safety_checker.py:84返回的auto_confirm=True配对, 实现DB场景表#1(安全绕过时MetaStep照出但立即resolve不过SUSPENDED)
# 2026-08-07 - 小欧 - import同步: param_alias_mapper.py→tools_alias_mapper.py 重命名(名实相符), PARAM_ALIASES引用处同步更新
# 2026-08-07 - 小欧 - P07修复(北京老陈驱动 task001): _EXT_TO_READ_TOOL 从TEXT_EXTENSIONS排除.csv(双域: 文本+表格), 使 read_xlsx(csv)/readtext(csv) 均不被_auto_correct_file_tool自动改写 — 小欧 2026-08-07
# 2026-08-09 - 小欧 - edittext并发竞态修复(北京老陈驱动, 方案二分组调度版):
#   [BUG] 旧_has_conflict用set存工具名不计数, 3×edittext同文件被去重漏检→误走并行→read-modify-write竞态致内容丢失(after模式插入位置异常, log step=11)
#   [改法] ①新增_parse_paths(从旧_has_conflict路径解析循环提取, DRY) ②_has_conflict改为计数版(count>=2且含写操作即冲突)
#         ③新增_partition_calls(并查集连通分量分组) ④分支B改分组调度B': 冲突组内串行+无冲突组并行+组间失败隔离(results保序)
#         ⑤C分支_reason死代码清理(进入B'后C分支仅is_parallel=False触发, "文件路径冲突"永假)
#   [验证] verify_refactor_consistency 14/14一致 + verify_partition_v13 分组/执行/隔离10项全PASS + pytest全量回归
# 2026-08-09 - 小欧 - B'分支DRY优化(规范6, 见doc-8月优化修复代码三堂会审报告): 每组冲突判定 _has_conflict 只算一次
#   存入 _gconf 列表, 监控(_gmode拼接)与执行(_run_group冲突分支判定)共用该结果, 消除二次冗余调用;
#   _has_conflict为确定性纯函数(同参数必同果), 判定一次监控与实际执行必然一致(无失真); _run_group加conflicted参数。
#   验证: ast语法✓ + 三分支(单/并行/串行)语义逐字保留无退化
# 2026-08-09 - 小欧 - B'分组调度监控日志(北京老陈驱动: 需监控时间运行情况):
#   [目的] 原B'仅"分组并行执行"开头日志+总耗时, 无法观察每组是并行/串行及各组实际耗时
#   [改法] ①进入B'后打印分组明细(每组工具+模式: 单工具/并行/串行) ②_run_group内计时,
#          每组执行完打印"分组执行完成: tools=..., 模式=..., 耗时=x.xxs" ③执行逻辑零改动(仅return改为赋值_res后return)
#   [验证] py_compile + verify_prod_smoke(生产代码直接import) + handlers/edittext测试
# 2026-08-10 - 小欧 - BUG-E修复(补A"操作结束即清除"落地): handle_action 工具批执行结束后 finally 调 clear_temp_auth(),
#   清空本请求作用域 ContextVar 临时授权, 杜绝"一次一申请"授权跨工具跨步骤残留复用;
#   try/finally 保证执行异常时也清除(不残留授权) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - H1-H2 实施(第二次代码更新): H1 finally 清零移除(清零点迁移到 task 级 R1 react_cycle.run_react_cycle finally);
#   H2 复用现有 HITL 模式: create_confirmation + wait_for_confirmation_result(前端零改动) — 小欧 2026-08-10
# 2026-08-11 - 小欧 - task002 三堂会审修复A(北京老陈驱动, 问题A窗口并行竞态):
#   [BUG] window_focus/window_resize/set_window_state 作用于同一窗口时状态变更非幂等, 同批并行调度产生竞态;
#         实测 P2: set_window_state(restore)+window_resize 同批并行, resize 0.00s 返回 ERR_WINDOW_RESIZE
#   [改法] ①新增 WINDOW_TARGET_TOOLS 常量 ②_parse_paths 新增窗口分支(返回 "window:{window_title}" 冲突键,
#         缺 title 返回空集——工具参数校验必失败, 不会操作任何窗口, 无竞态风险)
#         ③_has_conflict 遍历与判定条件纳入窗口工具(同标题≥2次调用即冲突→降级串行)
#   [效果] 同批同标题窗口工具自动并入同组串行(_partition_calls 并查集本体零改动), 不同标题窗口仍可跨组并行
#   [验证] py_compile + verify_partition_v13 + verify_refactor_consistency + pytest 回归 — 小欧 2026-08-11
"""
action_handler — action类型处理（SRP拆分，模块级函数）

3个职责单一的函数:
- check_safety_and_confirm: 安全检查+HITL确认(async generator,IncidentStep先yield再等确认)
- execute_tools: 工具执行 → 返回results
- build_observation: 构建observation → 返回events

小沈 2026-06-09
小沈 2026-06-10 合并check_safety+wait_confirmation,消除重复check_before_execute调用
小沈 2026-06-10 修复HITL bug: check_safety_and_confirm改为async generator,IncidentStep先yield再等确认
小沈 2026-06-13 移除ActionHandler类,改为模块级函数
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set

from app.logger import logger, log_and_print
from app.constants import ACTION_LOG_RESULT_MAX_CHARS
from app.logger.prompt_logger import get_prompt_logger
from app.services.agent.steps import ThoughtStep, ActionStep, ObservationStep, ErrorStep, MetaStep, FinalStep  # 小欧 2026-07-13: 移除 ChunkStep（工具重试隐蔽，不再 emit）
from app.services.agent.status_table import AgentStatus, set_status
from app.services.agent.observation_formatter import build_observation_text
from app.constants import HITL_TIMEOUT
from app.services.agent.tool_executor import execute_tool
from app.services.task.task_context import set_current_task_id
from app.db.models.operation_models import OperationStatus
from app.db import db

from app.tools.tool_constants import SENSITIVE_FIELDS as _SENSITIVE_FIELDS, FILE_OPERATION_TOOLS
from app.tools.tools_alias_mapper import PARAM_ALIASES
from app.tools.validate.file_type_checker import TEXT_EXTENSIONS, MEDIA_EXTENSIONS


# 【修复P2-5】封装observation构建上下文 — 北京老陈 2026-06-13
@dataclass
class ObservationContext:
    """构建observation所需的上下文 — 遵守ISP原则"""
    agent: Any
    all_calls: List[Dict]
    results: List[Any]
    step: int
    tool_name: str
    tool_params: Dict
    is_parallel: bool
    pending_calls: List
    fc_context: Dict = None


# 工具文件写操作集合（冲突检测用）— 北京老陈 2026-07-04
_WRITE_OPS = FILE_OPERATION_TOOLS - {"readtext"}

# 窗口类目标工具集合（冲突检测用）— 小欧 2026-08-11 task002 三堂会审修复A
# 窗口状态变更(restore/resize/focus)作用于同一窗口时非幂等, 同批并行会产生竞态
# (实测 P2: set_window_state(restore)+window_resize 同批并行, resize 0.00s 莫名失败),
# 需与文件工具同机制: 同键(同 window_title)互斥 → 并入同组串行。
# 不含 window_info(只读枚举, 不改变窗口状态, 无竞态)。
WINDOW_TARGET_TOOLS = {"window_focus", "window_resize", "set_window_state"}

# #4 自动纠正: 文件扩展名→tool_name 映射（三分类: 文本→readtext, 文档→专用工具, 多媒体→readmedia）
# P07修复: .csv 是双域(文本+表格), 从读取映射移除, 使 read_xlsx/readtext 均不被自动改写 — 小欧 2026-08-07
_EXT_TO_READ_TOOL = {ext: "readtext" for ext in TEXT_EXTENSIONS if ext != ".csv"}
_EXT_TO_READ_TOOL.update({ext: "readmedia" for ext in MEDIA_EXTENSIONS})
_EXT_TO_READ_TOOL.update({
    ".docx": "read_docx",
    ".xlsx": "read_xlsx",
    ".pdf": "read_pdf",
    ".pptx": "read_pptx",
})
_EXT_TO_WRITE_TOOL = {ext: "writetext" for ext in TEXT_EXTENSIONS}
_EXT_TO_WRITE_TOOL.update({
    ".docx": "write_docx",
    ".xlsx": "write_xlsx",
    ".pdf": "write_pdf",
    ".pptx": "write_pptx",
})


def _auto_correct_file_tool(tool_name: str, tool_params: dict) -> tuple:
    """文件扩展名预检自动纠正tool_name — 返回 (纠正后名, 原始名或None)
    三分类映射: 文本→readtext, 文档→专用工具, 多媒体→readmedia — 小欧 2026-07-25"""
    _path = tool_params.get("path", "") if isinstance(tool_params, dict) else ""
    if not _path or not isinstance(_path, str):
        return tool_name, None
    _ext = _path[_path.rfind("."):].lower() if "." in _path else ""
    if not _ext:
        return tool_name, None
    if tool_name.startswith("read"):
        _mapping = _EXT_TO_READ_TOOL
    elif tool_name.startswith("write"):
        _mapping = _EXT_TO_WRITE_TOOL
    else:
        return tool_name, None
    if _ext in _mapping and tool_name != _mapping[_ext]:
        return _mapping[_ext], tool_name
    return tool_name, None


async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int, fc_context: Dict = None, _out: list = None):
        """安全检查+HITL确认 — async generator: MetaStep先yield给前端,再等确认 — 小沈 2026-06-10

        拒绝/拦截是可恢复的(符合人类认知: 拒绝≠失败), 不置终态FAILED:
        - 把"工具被拒绝/拦截"作为 observation 写进LLM历史(_add_denial_feedback), 让LLM换方案;
        - 循环回 THINKING 由主循环 EXECUTING→THINKING 处理;
        - 仅当同类拒绝累计>=3次才由 _dispatch_handler 置 FAILED。 — 小欧 2026-07-13
        # 2026-07-18 小欧 #11+#12 fix: 超时/拒绝分流; 拒绝不终止整批, 收集_denied后继续检查剩余工具,
        #   最终只执行通过的call(通过_out返回过滤后的call列表)
        """
        from app.services.safety.tool_safety_checker import get_tool_safety_checker
        from app.services.task.hitl_confirmation import create_confirmation, wait_for_confirmation_result, resolve_confirmation
        safety_checker = get_tool_safety_checker()

        _denied = []
        for call in all_calls:
            _cn = call.get("tool_name", "?")
            _cp = call.get("tool_params", {})
            safety_result = safety_checker.check_before_execute(_cn, _cp)

            if safety_result.blocked:
                yield agent._step_emitter.emit(ErrorStep(
                    step=step,
                    error_type="blocked",
                    error_message=safety_result.message
                ))
                _denied.append((_cn, f"被安全策略拦截: {safety_result.message}"))
                continue  # was: return  — 小欧 2026-07-18 #12 fix

            if safety_result.requires_confirmation:
                desensitized_params = {k: v for k, v in _cp.items()
                                       if k not in _SENSITIVE_FIELDS}

                confirm_id = await create_confirmation(agent.task_id)

                yield agent._step_emitter.emit(MetaStep(
                    step=step,
                    type="paused",
                    content=f"需要用户确认工具执行: {_cn}",
                    confirm_id=confirm_id,
                    tool_name=_cn,
                    params=desensitized_params,
                    safety_level=safety_result.safety_level,
                ))

                if safety_result.auto_confirm:
                    # P0-01修复: 安全绕过(security.enabled=false)时MetaStep照出但自动确认立即通过, 不挂起不等wait
                    #   与tool_safety_checker.py bypass路径返回的auto_confirm=True配对 — 小沈 2026-08-03
                    # 2026-08-11 小欧(P2-5): bypass模式(auto_confirm=True)下continue跳过下方grant_temp_auth —
                    #   安全开关关闭时每次工具调用均auto_confirm直接放行, 无需累积临时授权, 跳过是正确语义
                    resolve_confirmation(confirm_id, confirmed=True, trust_session=True)
                    set_status(agent, AgentStatus.EXECUTING, "安全策略自动确认工具执行")
                    continue

                set_status(agent, AgentStatus.SUSPENDED, f"等待用户确认工具执行: {_cn}")
                auth = await wait_for_confirmation_result(confirm_id, timeout=HITL_TIMEOUT)

                if not auth.get("confirmed"):
                    if auth.get("expired"):
                        # #11 fix: 超时与拒绝分流 — 小欧 2026-07-18
                        yield agent._step_emitter.emit(ErrorStep(
                            step=step,
                            error_type="timeout",
                            error_message=f"工具确认超时未响应: {_cn}"
                        ))
                        _denied.append((_cn, "确认超时未响应"))
                    else:
                        yield agent._step_emitter.emit(ErrorStep(
                            step=step,
                            error_type="user_rejected",
                            error_message=f"用户拒绝执行工具: {_cn}"
                        ))
                        _denied.append((_cn, "被用户拒绝执行"))
                    set_status(agent, AgentStatus.EXECUTING, "用户拒绝/超时，恢复执行态")
                    continue  # was: return  — 小欧 2026-07-18 #12 fix

                # 用户已确认：恢复执行态继续工具执行（SUSPENDED→EXECUTING 合法）— 小欧 2026-07-12
                # ⑮ 白名单外临时授权: 确认后授予本次操作权限(一次一申请, 支持递归, per-request) — 小欧 2026-08-10
                if getattr(safety_result, "auth_path", None):
                    from app.services.safety.temp_auth import grant_temp_auth
                    grant_temp_auth(safety_result.auth_path, recursive=True)
                    yield agent._step_emitter.emit(MetaStep(
                        step=step,
                        type="resumed",
                        content=f"已临时授权白名单外路径: {safety_result.auth_path}"
                    ))
                set_status(agent, AgentStatus.EXECUTING, "用户已确认工具执行")

        if _denied:
            for _cn, _reason in _denied:
                _add_denial_feedback(agent, all_calls, fc_context, _cn, _reason)
        # 回传未被拒的call索引给调用方 — 小欧 2026-07-18 #12 fix
        if _out is not None:
            _denied_cns = {d[0] for d in _denied}
            _out[:] = [c for c in all_calls if c.get("tool_name", "") not in _denied_cns]


def _add_denial_feedback(agent, all_calls: List[Dict], fc_context: Dict, denied_tool: str, reason: str):
    """HITL拒绝/拦截→把反馈写入LLM历史, 让LLM换方案(符合人类认知: 拒绝≠失败) — 小欧 2026-07-13

    不置终态, 仅补充 observation:
    1. 补 assistant(tool_calls) 使 tool result 能配对;
    2. 被拒/被拦截的工具: 用 reason 说明原因;
    3. 同批其他工具: 标记"未执行"(它们并非被拒, 不能错标)。
    缺此反馈 LLM 会傻乎乎重复请求同一工具陷入死循环(受 max_steps 兜底)。
    """
    _fc = fc_context or {}
    _tc = _fc.get("tool_calls", [])
    if _tc:
        agent.message_builder.add_assistant_tool_call(_tc, content=_fc.get("llm_content", "") or None, reasoning=_fc.get("llm_reasoning", "") or None)  # 2026-07-19 小欧 reasoning传递
    for call in all_calls:
        _tid = call.get("_tool_call_id", "")
        _cn = call.get("tool_name", "")
        if _cn == denied_tool:
            _obs = f"[Observation] 工具 {_cn} {reason}. 请改用其他工具或方式完成用户任务。"
        else:
            _obs = f"[Observation] 工具 {_cn} 未执行(同批工具 {denied_tool} 未通过安全检查)。"
        try:
            agent.message_builder.add_tool_result(_tid, _obs)
        except Exception as e:
            logger.debug(f"add_tool_result(_tid={_tid})失败, 尝试空ID: {e}")
            try:
                agent.message_builder.add_tool_result("", _obs)
            except Exception as e2:
                logger.debug(f"add_tool_result(空ID)也失败: {e2}")


def _parse_paths(name: str, params: Dict) -> Set[str]:
    """解析一个调用的路径/窗口冲突键集合(复用 PARAM_ALIASES 别名→规范名) — 小欧 2026-08-09 — 小欧 2026-08-11 窗口分支
    文件工具: 解析 path 集合(与 _has_conflict/_partition_calls 共用, DRY)。
    窗口工具: 以 "window:{window_title}" 为冲突键, 同标题窗口工具并入同组串行(状态变更非幂等);
              缺 window_title 返回空集——窗口工具参数校验必失败, 不会操作任何窗口, 无竞态风险, 不参与分组。
    """
    if name in WINDOW_TARGET_TOOLS:
        title = params.get("window_title", "")
        if title and isinstance(title, str):
            return {f"window:{title}"}
        return set()
    if name not in FILE_OPERATION_TOOLS:
        return set()
    aliases = PARAM_ALIASES.get(name, {})
    if not aliases:
        p = params.get("path", "")
        return {p} if p and isinstance(p, str) else set()
    resolved = {}
    for key, value in params.items():
        canon = aliases.get(key, key)
        if canon not in resolved:
            resolved[canon] = value
    out = set()
    for pname in set(aliases.values()):
        pval = resolved.get(pname)
        if pval and isinstance(pval, str):
            out.add(pval)
    return out


def _has_conflict(all_calls: List[Dict]) -> bool:
    """检测路径/窗口冲突 — 北京老陈 2026-07-04 初版; 小欧 2026-08-09 计数版; 小欧 2026-08-11 窗口工具纳入
    冲突：同一键(文件路径/窗口标题)被>=2次调用访问, 且(至少一个文件写操作 或 含窗口工具)
    有冲突→顺序执行, 无冲突→并行
    [2026-08-09 小欧] BUG修复: 旧实现用 set 存工具名不计数, 同名工具多次写
    同一路径漏检(3×edittext 同文件)→误走并行→read-modify-write 竞态致内容丢失。
    改为 path→(调用次数, 工具名set), 复用 _parse_paths 解析(与 _partition_calls 一致, DRY)。
    [2026-08-11 小欧] 扩展: 窗口工具(window_focus/window_resize/set_window_state)同标题即冲突,
    消除 task002 实测 P2(restore+resize 同批并行→resize 0.00s 莫名失败)的并行竞态。
    注: 文件路径键与 "window:" 键空间不重叠, 同一 entry 的 tools 不会混合文件与窗口工具。
    """
    path_ops: Dict[str, Dict[str, Any]] = {}

    def _record(_path: str, _name: str) -> None:
        entry = path_ops.setdefault(_path, {"count": 0, "tools": set()})
        entry["count"] += 1
        entry["tools"].add(_name)

    for c in all_calls:
        name = c.get("tool_name", "")
        if name not in FILE_OPERATION_TOOLS and name not in WINDOW_TARGET_TOOLS:
            continue
        for _path in _parse_paths(name, c.get("tool_params", {})):
            _record(_path, name)

    for path, entry in path_ops.items():
        tools = entry["tools"]
        if entry["count"] >= 2 and (any(t in _WRITE_OPS for t in tools) or any(t in WINDOW_TARGET_TOOLS for t in tools)):
            logger.info(f"[_has_conflict] 操作冲突(路径/窗口): {path}, tools={tools}, 调用数={entry['count']}, 降级顺序执行")
            return True
    return False


def _partition_calls(all_calls: List[Dict]) -> List[List[int]]:
    """按路径/窗口相关性分组(并查集连通分量): 共享路径或同标题窗口的调用归一组, 组间无共享→可并行
    返回: 组列表, 每组是 all_calls 的索引列表 — 小欧 2026-08-09 — 小欧 2026-08-11 窗口工具自动纳入
    (窗口工具经 _parse_paths 返回 "window:标题" 冲突键, 同标题自动并组串行, 分组本体逻辑零改动)
    """
    n = len(all_calls)
    parent = list(range(n))

    def _find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    path_to_calls = {}
    for i, c in enumerate(all_calls):
        for p in _parse_paths(c.get("tool_name", ""), c.get("tool_params", {})):
            path_to_calls.setdefault(p, []).append(i)
    for _p, idxs in path_to_calls.items():
        base = idxs[0]
        for i in idxs[1:]:
            _union(base, i)

    groups = {}
    for i in range(n):
        groups.setdefault(_find(i), []).append(i)
    return list(groups.values())


async def execute_tools(agent, all_calls: List[Dict], is_parallel: bool,
                        tool_name: str, tool_params: Dict,
                        on_retry_started=None) -> List[Any]:
        """工具执行调度 — 三分支策略（遵守SLAP：本层只做决策不分派执行细节）
         
        三分支说明：
          A: 单工具（len==1）→ execute_tool(on_retry_started=...)
             单个工具执行，注入重试回调。引擎层自动处理重试+通知。
          B: 多工具无冲突 → execute_tool(parallel=True, 无on_retry_started)
             各工具并行执行，用try_once一次执行不重试。
             设计理由（YAGNI）：并行工具的瞬态失败概率低，不需要引擎自动重试。
             LLM从observation看到失败后可自行决定重试。同时避免asyncio.gather内
             多重试的复杂性。
          C: 多工具有冲突/非并行模式 → 顺序执行，每个调execute_tool(on_retry_started=...)
             文件路径冲突（一写多读）→降级顺序避免并发竞态。
             非并行模式→依次执行不并发。
         
        参数变化历史：
        北京老陈 2026-07-04: 初版，三分支+文件冲突检测
        小欧 2026-07-09: 
          - 并行分支B改用parallel=True（→try_once），删除手动重试循环（解决SRP/DRY违规）
          - 新增on_retry_started参数，透传给单工具/顺序分支（解决重试无前端通知问题）
        """
        start_time = time.time()

        # #4 自动纠正: 文件工具扩展名预检 — 小欧 2026-07-21
        _correction_map = {}
        for i, c in enumerate(all_calls):
            _orig = c.get("tool_name", "")
            _corrected, _raw = _auto_correct_file_tool(_orig, c.get("tool_params", {}))
            if _raw:
                logger.info(f"[action_handler] 自动纠正: {_raw}→{_corrected}")
                c["tool_name"] = _corrected
                _correction_map[i] = _raw
        _corrected_tn, _raw_tn = _auto_correct_file_tool(tool_name, tool_params)
        if _raw_tn:
            tool_name = _corrected_tn
            if all_calls:
                _correction_map[0] = _raw_tn

        def _cn(c):
            return c.get("tool_name", "") if isinstance(c, dict) else ""
        def _cp(c):
            return c.get("tool_params", {}) if isinstance(c, dict) else {}

        if len(all_calls) == 1:
            # A: 单工具
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 单工具执行: tool={tool_name}")
            result = await execute_tool(agent, tool_name, tool_params, on_retry_started=on_retry_started)
            results = [result]

        elif is_parallel:
            # B': 并行分组调度 — 冲突组内串行, 无冲突组并行("该并行就并行") — 小欧 2026-08-09
            _names = [_cn(c) for c in all_calls]
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 分组并行执行: tools={_names}")
            groups = _partition_calls(all_calls)
            # DRY(规范6): 每组冲突判定只算一次, 监控(_gmode)与执行(_run_group)共用,
            # 消除二次 _has_conflict 冗余调用; 纯函数确定性保证监控与实际执行必然一致(无失真) — 小欧 2026-08-09
            _gd = []
            _gconf = []  # 每组冲突判定结果, 按 groups 顺序对齐
            for _g in groups:
                _gt = [_cn(all_calls[i]) for i in _g]
                _conflicted = len(_g) > 1 and _has_conflict([all_calls[i] for i in _g])
                _gconf.append(_conflicted)
                _gmode = "单工具" if len(_g) == 1 else ("并行" if not _conflicted else "串行")
                _gd.append(f"[{'/'.join(_gt)}:{_gmode}]")
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 分组明细({len(groups)}组): {' '.join(_gd)}")

            async def _run_group(indices: List[int], conflicted: bool):
                group = [all_calls[i] for i in indices]
                _g_start = time.time()  # 监控: 每组执行耗时起点 — 小欧 2026-08-09
                if len(group) == 1:  # 单工具, 语义同原A
                    _res = [await execute_tool(agent, _cn(group[0]), _cp(group[0]),
                                               on_retry_started=on_retry_started)]
                    _gmode = "单工具"
                elif not conflicted:  # 组内无冲突→并行(try_once), 语义同原B
                    tasks = [execute_tool(agent, _cn(c), _cp(c), parallel=True) for c in group]
                    _res = await asyncio.gather(*tasks, return_exceptions=True)
                    _gmode = "并行"
                else:  # 组内冲突→串行(带重试), 语义同原C
                    _res = []
                    for call in group:
                        try:
                            _res.append(await execute_tool(agent, _cn(call), _cp(call),
                                                           on_retry_started=on_retry_started))
                        except Exception as e:
                            logger.warning(f"[action_handler] 工具{_cn(call)}组内顺序执行失败: {e}")
                            _res.append(e)
                    _gmode = "串行"
                logger.info(f"[action_handler] 分组执行完成: tools={[_cn(c) for c in group]}, 模式={_gmode}, 耗时={time.time()-_g_start:.2f}s")
                return _res

            _grouped = await asyncio.gather(*[_run_group(g, _gconf[i]) for i, g in enumerate(groups)],
                                            return_exceptions=True)  # 组间失败隔离: 单组异常不取消其他组
            results = [None] * len(all_calls)  # 结果按原顺序填回
            for _indices, _res in zip(groups, _grouped):
                if isinstance(_res, Exception):  # 整组失败: 组内全部标记为该异常(与原C分支单工具异常append语义一致)
                    for _i in _indices:
                        results[_i] = _res
                    continue
                for _i, _r in zip(_indices, _res):
                    results[_i] = _r
        else:
            # C: 非并行模式 → 顺序执行（一个不丢）
            _names = [_cn(c) for c in all_calls]
            _reason = "非并行模式"
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 顺序执行({_reason}): tools={_names}")
            results = []
            for call in all_calls:
                try:
                    result = await execute_tool(agent, _cn(call), _cp(call), on_retry_started=on_retry_started)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"[action_handler] 工具{_cn(call)}顺序执行失败: {e}")
                    results.append(e)

        elapsed = time.time() - start_time
        tool_names = [_cn(c) for c in all_calls]
        logger.info(f"[action_handler] 工具执行完成: tools={tool_names}, 耗时={elapsed:.2f}s")

        for i, (call, result) in enumerate(zip(all_calls, results)):
            if isinstance(result, Exception):
                logger.info(f"[action_handler] 工具原始结果: tool={_cn(call)}, params={_cp(call)}, result=ERROR({result})")
            else:
                _r_str = str(result)
                if len(_r_str) > ACTION_LOG_RESULT_MAX_CHARS:
                    _r_str = _r_str[:ACTION_LOG_RESULT_MAX_CHARS] + f"...(截断{len(_r_str)}字符)"
                logger.info(f"[action_handler] 工具原始结果: tool={_cn(call)}, params={_cp(call)}, result={_r_str}")
            _orig_tool = _correction_map.get(i)
            if _orig_tool and isinstance(result, dict):
                _llm = result.get("llm_data")
                if isinstance(_llm, dict) and isinstance(_llm.get("summary"), str):
                    _llm["summary"] += f"（工具自动纠正自:{_orig_tool}）"

        return results


def _merge_llm_data(all_llm_data: List[Dict]) -> Dict:
    """并行场景llm_data合并 — 小健 2026-06-22"""
    if not all_llm_data:
        return {}
    # 过滤非dict条目，防止崩溃 — 小欧 2026-06-22
    all_llm_data = [d for d in all_llm_data if isinstance(d, dict)]
    if not all_llm_data:
        return {}
    if len(all_llm_data) == 1:
        return all_llm_data[0]

    severity_order = {"error": 3, "warning": 2, "success": 1}

    def _severity_key(d):
        status = d.get("status")
        if not isinstance(status, dict):
            return 0
        exec_code = status.get("exec_code", "success")
        return severity_order.get(exec_code, 0)

    sorted_data = sorted(all_llm_data, key=_severity_key, reverse=True)

    most_severe = sorted_data[0]

    merged_metrics = {}
    for llm_d in all_llm_data:
        action = llm_d.get("action") if isinstance(llm_d.get("action"), dict) else {}
        tool_name = action.get("tool", "unknown")
        metrics = llm_d.get("metrics") if isinstance(llm_d.get("metrics"), dict) else {}
        for k, v in metrics.items():
            merged_metrics[f"{tool_name}.{k}"] = v

    def _safe_str(val):
        if val is None:
            return ""
        return str(val) if not isinstance(val, str) else val

    return {
        "summary": "\n\n".join([_safe_str(d.get("summary", "")) for d in all_llm_data]),
        "action": most_severe.get("action") if isinstance(most_severe.get("action"), dict) else {},
        "status": most_severe.get("status") if isinstance(most_severe.get("status"), dict) else {},
        "duration_ms": max([d.get("duration_ms", 0) for d in all_llm_data]),
        "metrics": merged_metrics,
    }


def _merge_other_data(all_other_data: List[Dict]) -> Dict:
    """并行场景other_data合并 — 小健 2026-06-22; 小欧 2026-06-22 过滤None条目"""
    valid = [od for od in all_other_data if od is not None]
    if not valid:
        return {}

    merged: Dict[str, Any] = {}
    warnings = []
    attachments = []
    return_direct = False

    for od in valid:
        w = od.get("warning")
        if w:
            warnings.append(str(w) if not isinstance(w, str) else w)
        if od.get("attachment") is not None:
            attachments.append(od["attachment"])
        if od.get("return_direct"):
            return_direct = True
        if "retry_count" not in merged and od.get("retry_count") is not None:
            merged["retry_count"] = od["retry_count"]

    if warnings:
        merged["warning"] = "\n\n".join(warnings)
    if attachments:
        merged["attachment"] = attachments if len(attachments) > 1 else attachments[0]
    if return_direct:
        merged["return_direct"] = True
    return merged


async def build_observation(ctx: ObservationContext, merged_other: Optional[Dict] = None) -> List:
    """构建observation — FC-only: 传递fc_context,删除add_assistant — 小沈 2026-06-11
    【修复P2-5】使用ObservationContext封装参数 — 北京老陈 2026-06-13"""
    events = []

    for call, result in zip(ctx.all_calls, ctx.results):
        if isinstance(result, Exception):
            _ec = "error"
        elif isinstance(result, dict):
            _llm_data = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            _ec = _llm_data.get("status", {}).get("exec_code", "") if _llm_data else "error"
        else:
            _ec = "error"
        action_step = ActionStep(
            step=ctx.step,
            tool_name=call.get("tool_name", ""),
            tool_params=call.get("tool_params", {}),
            execution_result=result,
            execution_status=_ec if _ec else "",
        )
        events.append(ctx.agent._step_emitter.emit(action_step))

    obs_parts = []

    # 【Bug A修复】循环前：建1条assistant带所有tool_calls — 小沈 2026-07-06
    # assistant+tool 配对规则:
    #   1条assistant(带本轮N个tool_calls) + N条tool(每个tool_call_id对应1条)
    #   历史结构: ...→assistant(tool_calls=[id1,id2])→tool(id1)→tool(id2)→...
    #   注: 同一assistant的所有tool_calls是一次性发给LLM的"并行"请求
    # — 小欧 2026-07-12
    _fc = ctx.fc_context or {}
    _shared_tc = _fc.get("tool_calls", [])
    if _shared_tc:
        ctx.agent.message_builder.add_assistant_tool_call(
            _shared_tc, content=_fc.get("llm_content", "") or None,
            reasoning=_fc.get("llm_reasoning", "") or None  # 2026-07-19 小欧 reasoning传递
        )

    # ==========================================================================
    # op_id 双表贯通（纯内部逻辑，与 LLM 返回结构零耦合） — 小欧 2026-07-16
    # 目标：让同一文件操作在 file_operations 与 task_operations 两表共享同一
    #       operation_id（双表同号），实现"一个文件操作、两个维度"的精确关联。
    # 为什么需要 _file_tool_names 白名单（硬编码 6 个文件工具名）？
    #   - 只有这 6 个文件工具会在内部调用 record_operation 写入 file_operations；
    #   - 非文件工具（searchtool/sysinfo/timer/sql…）不写 file_operations，
    #     若也去取 op_id 会"误关联"文件操作的 op_id；
    #   - 白名单用于判定"当前 call 是否参与贯通"，把贯通精准限定在文件类工具维度。
    #   - 硬编码而非查 registry：action_handler 只有 tool_name 字符串，查 category
    #     需额外引入/遍历；硬编码最直接(KISS/YAGNI)。代价：新增文件工具需同步此集合。
    # 解决的两个真实 bug（unit-02 暴露）：
    #   1) 非文件工具误关联：原实现每个 call 都查 file_operations「最新」op_id，
    #      导致 searchtool 抢走 write_docx 的 op_id 写进 task_operations（错误关联）；
    #   2) 多文件工具同轮撞 UNIQUE：同轮多个文件工具抢同一 op_id →
    #      "UNIQUE constraint failed: task_operations.operation_id"。
    # 处理逻辑（三步）：
    #   [预取] 取本 task 在 file_operations 中「尚未写入 task_operations」的 op_id，
    #          按 created_at/rowid 升序排成候选队列 _pending_op_ids；
    #   [分配] 循环内：仅文件类工具(call 在白名单)按 call 顺序 pop(0) 取一个候选，
    #          非文件类工具 op_id=None 由 record_operation 内部自生成；
    #   [写入] 用取出的 op_id 调 record_operation 写 task_operations，实现双表同号。
    #   文件工具 call 顺序 == file_operations 写入顺序，故 pop 精确一一对应，不撞车。
    # ==========================================================================
    _file_tool_names = {
        "delete", "copy", "move", "edittext",
        "writetext", "compress",
    }
    _pending_op_ids = []
    try:
        with db.get_conn("operations") as _cf:
            _fo = _cf.execute(
                "SELECT operation_id FROM file_operations WHERE task_id = ? "
                "ORDER BY created_at ASC, rowid ASC",
                (ctx.agent.task_id,),
            ).fetchall()
        with db.get_conn("task_tracker") as _ct:
            _used = set(r[0] for r in _ct.execute(
                "SELECT operation_id FROM task_operations WHERE task_id = ?",
                (ctx.agent.task_id,),
            ).fetchall())
        _pending_op_ids = [r[0] for r in _fo if r[0] not in _used]
    except Exception as _e:
        logger.warning(f"[action_handler] 查询 operation_id 候选失败: {_e}")
        _pending_op_ids = []

    for idx, (call, result) in enumerate(zip(ctx.all_calls, ctx.results)):
        if isinstance(result, Exception):
            obs_text = f"Observation: 工具{call.get('tool_name', '?')}执行异常: {result}"
            _ec = "error"
            _is_failed = True
        else:
            obs_text = build_observation_text(result, call.get("tool_name", ""), call.get("tool_params", {}))
            _llm_data = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            _ec = _llm_data.get("status", {}).get("exec_code", "") if _llm_data else "error"
            _is_failed = _ec == "error"

        get_prompt_logger().log_observation(
            step_name=f"步骤{ctx.step}: 工具执行结果",
            observation_content=obs_text,
            tool_name=call.get("tool_name", ""),
            tool_params=call.get("tool_params", {}),
            round_number=ctx.step,
            raw_data=result,
        )
        # 取 op_id：文件类工具(白名单内)从候选队列按 call 顺序 pop(0) 取一个 → 双表同号；
        #          非文件类工具为 None → record_operation 内部自生成。绝不读取工具返回值/LLM 字段(纯内部) — 小欧 2026-07-16
        _tool = call.get("tool_name", "?")
        _op_id = None
        if _tool in _file_tool_names and _pending_op_ids:
            _op_id = _pending_op_ids.pop(0)
        ctx.agent.record_operation(
            _tool,
            status=OperationStatus.FAILED.value if _is_failed else OperationStatus.SUCCESS.value,
            error=str(result) if _is_failed else None,
            operation_id=_op_id,
        )

        repair_warning = call.get("_repair_warning", "")
        if repair_warning:
            obs_text = f"Observation: {repair_warning}\n{obs_text}"
            print(f"{time.strftime('%H:%M:%S')} [Warning] step={ctx.step}, {call.get('tool_name', '?')} 参数截断修复")
            logger.warning(f"[action_handler] step={ctx.step}, {call.get('tool_name', '?')} 参数截断修复: {repair_warning}")
        obs_parts.append(obs_text)

        try:
            tc_id = call.get("_tool_call_id", "")
            ctx.agent.message_builder.add_tool_result(tc_id, obs_text)
        except Exception as e:
            logger.warning(f"[action_handler] add_tool_result异常: {type(e).__name__}: {e!r}")  # — 小欧 2026-07-13
            try:
                ctx.agent.message_builder.add_tool_result("", obs_text)
            except Exception as e2:
                logger.warning(f"[action_handler] add_tool_result最终异常: {type(e2).__name__}: {e2!r}")  # — 小欧 2026-07-13

    if not obs_parts:
        obs_parts = ["Observation: 无结果"]

    merged_obs = "\n\n".join(obs_parts) if len(obs_parts) > 1 else obs_parts[0]

    _all_llm_data = []
    _all_tool_results = []
    _all_other_data = []
    _parallel_results = []
    is_parallel = len(ctx.all_calls) > 1
    for call, result in zip(ctx.all_calls, ctx.results):
        if isinstance(result, dict):
            _all_llm_data.append(result.get("llm_data", {}))
            _all_tool_results.append(result.get("data"))
            _all_other_data.append(result.get("other_data", {}))
        else:
            _all_tool_results.append(result)
        if is_parallel:
            _parallel_results.append({
                "tool_name": call["tool_name"],
                "tool_params": call.get("tool_params", {}),
                "llm_data": result.get("llm_data", {}) if isinstance(result, dict) else {},
                "tool_result": result.get("data") if isinstance(result, dict) else result,
                "other_data": result.get("other_data", {}) if isinstance(result, dict) else {},
            })

    # 直接列表传递，不merge（各是各的，与parallel_results索引1:1）— 北京老陈 2026-07-08
    llm_data_list = _all_llm_data if _all_llm_data else None

    if llm_data_list:
        for i, ld in enumerate(llm_data_list):
            _st = ld.get("status", {}) if isinstance(ld, dict) else {}
            _ac = ld.get("action", {}) if isinstance(ld, dict) else {}
            _sm = (ld.get("summary", "") if isinstance(ld, dict) else "")[:120]
            logger.info(f"[Observation] step={ctx.step}[{i}], tool={_ac.get('tool','')}, code={_st.get('exec_code','?')}, summary={_sm}")

    if merged_other is None:
        merged_other = _all_other_data[0] if _all_other_data else None
        if len(_all_other_data) > 1:
            merged_other = _merge_other_data(_all_other_data)

    events.append(ctx.agent._step_emitter.emit(ObservationStep(
        step=ctx.step,
        llm_data=llm_data_list,
        tool_result=_all_tool_results[0] if len(_all_tool_results) == 1 else _all_tool_results,
        other_data=merged_other,
        parallel_results=_parallel_results or None,
    )))

    return events


@dataclass
class BuildCallListResult:
    """_build_call_list 返回值 — M-03 6元组→dataclass — 小欧 2026-07-10"""
    tool_name: str
    tool_params: Dict
    fc_context: Dict
    pending_calls: List
    all_calls: List[Dict]
    is_parallel: bool


def _build_call_list(parsed: Dict) -> BuildCallListResult:
    """构建工具调用列表 — 小欧 2026-06-18 从handle_action提取
    chendyg 2026-06-26 P1-10/11修复: 防御tool_name为空和pending_calls缺字段"""
    tool_name = parsed.get("tool_name", "")
    tool_params = parsed.get("tool_params") or {}
    fc_context = parsed.get("fc_context") or {}
    pending_calls = parsed.get("_pending_calls", [])

    # 【P1-10修复】tool_name为空时直接FAILED — chendyg 2026-06-26
    # handle_action已兜底空检查(ErrorStep+return), 此处删除重复日志 — 小欧 2026-07-25

    all_calls = [{
        "tool_name": tool_name, "tool_params": tool_params,
        "_tool_call_id": fc_context.get("tool_call_id", "") if fc_context else "",
        "_repair_warning": parsed.get("_repair_warning", ""),
    }]
    # 【P1-11修复】pending_calls条目缺tool_name时跳过 — chendyg 2026-06-26
    for pc in pending_calls:
        pc_name = pc.get("tool_name", "")
        if not pc_name:
            logger.warning(f"[_build_call_list] pending_call缺tool_name,跳过: {pc}")
            continue
        all_calls.append({
            "tool_name": pc_name, "tool_params": pc.get("tool_params") or {},
            "_tool_call_id": pc.get("_tool_call_id", ""),
            "_repair_warning": pc.get("_repair_warning", ""),
        })

    return BuildCallListResult(
        tool_name=tool_name, tool_params=tool_params, fc_context=fc_context,
        pending_calls=pending_calls, all_calls=all_calls,
        is_parallel=len(all_calls) > 1,
    )



async def handle_action(agent, parsed: Dict):
    """完整action处理流程 — FC-only: 提取fc_context传递
     
    处理管线（遵守SLAP，逐层递进）：
    1. _build_call_list → 解析parsed为all_calls
    2. emit ThoughtStep → LLM推理内容
    3. check_safety_and_confirm → 安全检查+HITL（async generator）
    4. build retry notification callback → 收集重试通知
    5. execute_tools → 三分支执行（单/并行/顺序）
    6. 工具重试由 tool_retry_engine 内部执行（隐蔽，前端不可见）— 小欧 2026-07-13
    7. build ObservationContext → 收集执行结果
    8. build_observation → yield ActionStep + ObservationStep
    9. return_direct检查 → 需要时yield FinalStep提前结束
     
    小沈 2026-06-11
    小欧 2026-07-09: 新增重试通知注入（步骤4-6）
    """
    set_current_task_id(agent.task_id)
    call_result = _build_call_list(parsed)
    step = agent.llm_call_count

    if not call_result.tool_name:
        logger.warning(f"[handle_action] tool_name为空, parsed={parsed}")
        agent._consecutive_reasoning_only = 0  # 2026-07-17 - 小欧 - action空名异常非reasoning-only, 归零防残留
        # chendyg 2026-07-01: 删set_failed，_dispatch_handler从ErrorStep推断状态
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="invalid_action",
            error_message="LLM返回的action中tool_name为空",
        ))
        return

    params_str = str(call_result.tool_params); params_short = (params_str[:180] + '..') if len(params_str) > 180 else params_str  # 小欧 2026-07-01 控制台截断 — 小沈 2026-07-05 50→100
    print(f"{time.strftime('%H:%M:%S')} [Action]step={step} ={call_result.tool_name}, pars:{params_short}")  # 小欧 2026-07-01 控制台 — 小沈 2026-07-05 =→:

    # thought 步骤 — content=LLM推理内容, reasoning=内部思维过程 — 小欧 2026-07-01
    yield agent._step_emitter.emit(ThoughtStep(
        step=step,
        content=parsed.get("thought", ""),
        tool_name=call_result.tool_name, tool_params=call_result.tool_params,
        reasoning=parsed.get("reasoning", ""),
    ))

    # #11+#12 fix: 传_out收集通过安全检查的call, 拒绝不终止整批 — 小欧 2026-07-18
    _safe_calls = []
    async for event in check_safety_and_confirm(agent, call_result.all_calls, step,
                                                call_result.fc_context, _out=_safe_calls):
        yield event
    _exec_calls = _safe_calls if _safe_calls else []

    # ── 工具重试（隐蔽，前端不可见）── 小欧 2026-07-13
    # 工具重试由 tool_retry_engine 内部执行, 不向前端 emit 任何 step(北京老陈要求: tool 重试隐蔽)。
    # 重试回调不再收集/上报, 仅后端内部重试。
    # H1 (v1.43): 移除工具批 finally 的 clear_temp_auth() — 清零点迁移到 task 级(R1, react_cycle.run_react_cycle finally)
    try:
        results = await execute_tools(agent, _exec_calls, call_result.is_parallel,
                                      call_result.tool_name, call_result.tool_params)
    except Exception as e:
        logger.error(f"[action_handler] execute_tools 异常: {e}")
        raise

    agent._consecutive_reasoning_only = 0  # 2026-07-17 - 小欧 - 本步LLM发起工具调用(非reasoning-only空转), 归零空转计数

    ctx = ObservationContext(
        agent=agent, all_calls=_exec_calls, results=results, step=step,
        tool_name=call_result.tool_name, tool_params=call_result.tool_params,
        is_parallel=call_result.is_parallel, pending_calls=call_result.pending_calls,
        fc_context=call_result.fc_context,
    )
    merged_other = _merge_other_data([r.get("other_data", {}) for r in results if isinstance(r, dict)]) if results else {}
    for event in await build_observation(ctx, merged_other=merged_other):
        yield event
    if merged_other.get("return_direct"):
        merged_llm = _merge_llm_data([r.get("llm_data", {}) for r in results if isinstance(r, dict)]) if results else {}
        _status = merged_llm.get("status", {}) if isinstance(merged_llm, dict) else {}
        yield agent._step_emitter.emit(FinalStep(
            step=step, response=_status.get("message", ""),
            thought=parsed.get("thought", ""),
            outcome="completed",  # 小欧 2026-07-18: 显式终态声明, 与FinalStep多态契约一致
        ))
        # chendyg 2026-07-01: 删set_completed，_dispatch_handler从FinalStep推断状态

