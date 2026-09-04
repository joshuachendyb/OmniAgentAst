# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 第3阶段拆分: 从 action_handler 完整复制 execute_tools
#   [背景] execute_tools 是工具三分支(单/并行分组串行/顺序)执行调度, 应属工具执行层, 非 action 编排本身
#   [改法] 先复制后修改: 本文件保留原名完整复制(逻辑零改动), 仅迁移存放位置
#   [效果] action_handler 920→~596行纯编排调度层; 本文件与 tool_executor 同层(工具执行调度), 是 execute_tool 的上一层
import asyncio
import time
from typing import Dict, List, Any

from app.logger import logger, log_and_print
from app.constants import ACTION_LOG_RESULT_MAX_CHARS
from app.services.agent.tool_executor import execute_tool
from app.tools.file_tool_utils import _auto_correct_file_tool
from app.tools.conflict_detector import _has_conflict, _partition_calls


async def execute_tools(agent, all_calls: List[Dict], is_parallel: bool,
                        tool_name: str, tool_params: Dict,
                        on_retry_started=None, on_attempt_recorded=None) -> List[Any]:
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
            # #18(2026-08-23): 文件A 每次尝试回调按【全局序号】取号 — 小欧 2026-08-23
            _cb = on_attempt_recorded(1) if on_attempt_recorded else None
            result = await execute_tool(agent, tool_name, tool_params, agent._retry_engine,
                                        on_retry_started=on_retry_started, on_attempt_recorded=_cb)
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
                    # #18(2026-08-23): 工厂实参=全局序号(indices[0]+1), 禁用组内局部下标 — 小欧 2026-08-23
                    _cb = on_attempt_recorded(indices[0] + 1) if on_attempt_recorded else None
                    _res = [await execute_tool(agent, _cn(group[0]), _cp(group[0]), agent._retry_engine,
                                               on_retry_started=on_retry_started, on_attempt_recorded=_cb)]
                    _gmode = "单工具"
                elif not conflicted:  # 组内无冲突→并行(try_once), 语义同原B
                    # #18(2026-08-23): zip(indices, group) 对齐全局下标取号 — 小欧 2026-08-23
                    tasks = [execute_tool(agent, _cn(c), _cp(c), agent._retry_engine, parallel=True,
                                          on_attempt_recorded=(on_attempt_recorded(_gi + 1) if on_attempt_recorded else None))
                             for _gi, c in zip(indices, group)]
                    _res = await asyncio.gather(*tasks, return_exceptions=True)
                    _gmode = "并行"
                else:  # 组内冲突→串行(带重试), 语义同原C
                    _res = []
                    for _gi, call in zip(indices, group):
                        try:
                            _cb = on_attempt_recorded(_gi + 1) if on_attempt_recorded else None
                            _res.append(await execute_tool(agent, _cn(call), _cp(call), agent._retry_engine,
                                                           on_retry_started=on_retry_started, on_attempt_recorded=_cb))
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
            for _gi, call in enumerate(all_calls, 1):
                try:
                    # #18(2026-08-23): 顺序分支按全局序号取号 — 小欧 2026-08-23
                    _cb = on_attempt_recorded(_gi) if on_attempt_recorded else None
                    result = await execute_tool(agent, _cn(call), _cp(call), agent._retry_engine,
                                                on_retry_started=on_retry_started, on_attempt_recorded=_cb)
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

        # 11.2-C 工具遥测回调（P0-2 修复：on_tool_call 未调用 → tool_execution_seconds 恒 0）— 小欧 2026-08-20; 2026-09-04 小健 第2阶段拆分: 批量聚合下沉 agent_telemetry.collect_and_report
        _tele = getattr(agent, "telemetry", None)
        if _tele is not None:
            _tele.collect_and_report(all_calls, results)

        return results
