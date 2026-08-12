# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 #14 fix: 删known_risk.requires_confirmation死分支
# 2026-07-18 小欧 #15/#50 fix: 删SafetyResult.is_safe死字段
# 2026-07-30 - 小欧 - auto_confirm+绕过时仍查needs_confirmation
# 2026-07-31 - 小欧 - 撤销auto_confirm: 恢复security.enabled=false原绕过路径, 删auto_confirm字段
# 2026-08-04 - 小欧 - 开关false仍拒绝已知风险: bypass只跳过确认询问不跳过危险防护, _check_known_risks(路径越权/写入保护/代码注入)检测到即blocked拒绝执行; 普通needs_confirmation仍auto_confirm放行 — 北京老陈驱动
# 2026-08-04 - 小欧 - 重构DRY: _check_known_risks提到两分支共同入口(无条件防线), 未注册check前置统一; 开关只分流"确认策略", 危险防护与开关解耦 — 三堂会审驱动(合规SRP/DRY/KISS最优)
# 2026-08-04 - 小欧 - delete专属安全(双轨接入): check_before_execute 一次性计算 delete_risk; R1/R2 仍由 known_risks(_is_forbidden_path) 覆盖, R6 入 _check_known_risks 无条件拦截, R3-R5 入 _get_needs_confirmation 确认分流; 惰性导入 delete_safety 避免循环依赖 — 北京老陈驱动(设计文档 v1.15)
# 2026-08-04 - 小欧 - fix: _check_known_risks 中 writetext 的 content 可能为 dict/list(LLM结构化传参), content.encode() 崩溃致误拦; 对齐工具层 check_content_safety 的 dict/list→json 转换 — E2E-P0-03a 回归发现
# 2026-08-04 - 小欧 - 三堂会审(YAGNI)撤销转换方案: 写保护只需量字节数, content为dict/list(非str)走 isinstance(str) 判typeskip(new_size=0), 不崩不误拦且无需把dict转json; 与工具层json转换职责解耦 — 北京老陈审出多余转换
# 2026-08-10 - 小欧 - 步骤1实施(⑮, 北京老陈驱动「项目根=tool工作区, 代码库根=tool禁区」): SafetyResult新增auth_path字段; _check_known_risks白名单外路径(非禁区/系统目录)转为临时授权请求(requires_confirmation+auth_path), 由action_handler HITL确认后grant_temp_auth放行
# 2026-08-10 - 小欧 - BUG-A修复: delete R6(项目根/授权目录外递归)外层先于 _check_known_risks 判定(if delete_risk.blocked: return), 杜绝R6被白名单临时授权绕过
# 2026-08-10 - 小欧 - BUG-D修复: _check_known_risks 白名单外授权请求的 auth_path 改用 validate_tool_path 返回的 failed_path(真正越权参数的真实路径),
#   不再固定 params.get("path") or params.get("dest")(多路径参数工具 copy/move/compress/extract 越权在dest时原逻辑授权对象错误, 取到合法path) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - T1-T3 实施(第二次代码更新, 基于第3章设计框架): _check_known_risks 接收 validate_tool_path 4元组(is_valid, msg, failed_path, category);
#   T2 按 category+mode 显式分流(替代 L167 msg 字符串特征判断): category=="system"写删硬拦永不授权 / category=="non_system"写→任务级授权请求(删在validate_path删除规则已硬拦到达不到) / category==None→白名单外临时授权 / category=="system"/"non_system"且读→放行(validate_path读mode已处理)
# 2026-08-10 - 小欧 - T2 缺陷修复(三堂会审关联逻辑复核发现): category=="non_system" 分支未区分写/删——validate_path 删mode返回
#   (False, msg, "non_system") 时, 原代码一律返回 requires_confirmation(可授权), 违反 3.2.10/表五「非系统禁区删❌硬拦永不授权」;
#   修复: 按 normalize_tool_name 判断 delete 操作 → 硬拦 blocked; 写操作保持任务级授权请求(3.2.13)
# 2026-08-10 - 小欧 - 三堂会审 BUG-2 修复(v1.45): _check_known_risks 写保护判定原 `tool_name == _WRITE_RISK_TOOL("writetext")`
#   用 LLM 原始名, 别名(write_text/writefile等) normalize 前不等于 writetext → 写入大小保护被绕过;
#   统一走 normalize_tool_name 再判(P2 防别名漏检补齐, 与 T2 delete 判定同模式) — 小欧 2026-08-10
# 2026-08-11 - 小欧 - P0-02回归修复: security.enabled=false(bypass)时 _check_known_risks 白名单外临时授权请求
#   (requires_confirmation+auth_path) 未设 auto_confirm, 仍挂起HITL等确认; E2E自动化无人在线确认→确认超时→任务failed。
#   修复: 白名单外授权请求在 _is_skip_safety()=true 时设 auto_confirm=True 直放(与普通确认bypass语义一致) — 北京老陈驱动E2E
# 2026-08-11 - 小欧 - 全分支补日志留痕(北京老陈驱动): bypass自动放行+各硬拦截统一用log_and_print(日志+控制台双输出),
#   覆盖 工具未注册/delete R6/授权请求bypass直放/已知风险拦截/普通确认bypass/check_fn拦截/系统禁区删拦/写入大小保护
# 2026-08-11 - 小欧 - bypass自动放行(无需确认) 改为仅 logger.info 留痕不上控制台(北京老陈驱动: 高频路径刷屏, 只log不print)
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1盲点二/四迁移: validate_tool_path 迁 app/tools/security/path_safe_check(import 同步),
#   SafetyResult dataclass 迁 app/tools/security/safety_result(本文件删除本地定义改 import, __all__ 保留导出) — 小欧 2026-08-12
"""
工具安全检查器 — 执行前安全检查（Safety层入口）

Safety层（本文件 + path_safe_check.py）：
  - 路径黑名单/白名单校验（_is_forbidden_path → validate_path）
  - 路径穿越(..)拒绝
  - 写入大小保护
  - 二元安全确认(needs_confirmation)
  - 已知风险检测(路径越权/写入污染)

工具层（validate/file_safety_checker.py + validate/file_path_checker.py + validate/file_type_checker.py）独立运行、互不调用：
  - check_content_safety: 内容安全检查（None/空/null字节/类型/append冲突）
  - validate_path: 非空/保留字符/保留名/系统目录硬阻断/存在性+类型/业务警告
  - check_file_type: 文件类型检查（文本/媒体/文档/压缩）
  - check_tool_module: 依赖库安装检查
  - check_office_file: 路径+类型+模块安全三位一体

Layer 2: 二元安全确认(needs_confirmation)
Layer 3: 已知风险检测(路径越权/写入污染/代码注入)

2026-06-16 小沈 删除5级枚举，改用二元安全+check_fn
2026-06-17 小沈 删除record_operation/execute_with_safety委托(打破tools→safety循环依赖)，
             路径校验改用path_safe_check(打破safety→tools循环依赖)
2026-07-04 小欧 补充两层架构说明注释
2026-07-09 北京老陈 补充validate层完整函数清单
"""


from pathlib import Path
from typing import Dict, Optional

from app.logger import logger, log_and_print
from app.config import get_config
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.tools.security.path_safe_check import validate_tool_path as _validate_tool_path
from app.tools.security.safety_result import SafetyResult  # A1盲点四: SafetyResult 迁 tools/security — 小欧 2026-08-12

_WRITE_RISK_TOOL = "writetext"


def _is_skip_safety() -> bool:
    """运行时检查安全开关 — 只读 config.yaml security.enabled"""
    try:
        return not get_config().get("security.enabled", True)
    except Exception:
        return False


class ToolSafetyChecker:
    """工具执行前安全检查 — 确认判定 + 已知风险检测"""

    def check_before_execute(self, tool_name: str, params: Optional[Dict] = None) -> SafetyResult:
        """
        执行前安全检查入口（Safety层）
        工具层的 validate_path() 先于本函数执行，已拦截空/保留字符/保留名/系统目录/不存在/类型不匹配
        本函数负责：路径黑名单/白名单/路径穿越/写入大小保护/二元确认

        安全开关: config.yaml security.enabled=false 时跳过所有检查
        2026-08-04 小欧: 已知风险(路径越权/写入保护/代码注入)无条件检测不管开关, 危险即拒绝执行(blocked);
            开关false仅bypass各"确认询问"(普通needs_confirmation), 开关true则正常询问 — 北京老陈驱动重构
        """
        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            log_and_print(f"[ToolSafetyChecker] 工具未注册,拒绝执行: {tool_name}")
            return SafetyResult(blocked=True,
                    message=f"工具{tool_name}未注册",
                    safety_level="dangerous")

        # ① delete 专属判定一次性计算, 供②③两处消费(DRY) — 小欧 2026-08-04
        delete_risk = None
        if tool_name == "delete":
            from app.safety.delete_safety import check_delete_risk  # 惰性导入避免与delete_safety循环依赖 — 小欧 2026-08-04
            delete_risk = check_delete_risk(params or {})

        # ② 已知风险检测: 无条件防线(开关无关) — 路径越权(R1/R2)/delete R6/写入大小保护/代码注入即使开关false也拒绝 — 小欧 2026-08-04
        # 先校验delete专属R6（项目根外递归删除），再校验白名单（临时授权）
        if delete_risk is not None and delete_risk.blocked:
            log_and_print(f"[ToolSafetyChecker] delete R6硬拦截(项目根外递归删除): {delete_risk.message}")
            return delete_risk
        known_risk = self._check_known_risks(tool_name, params or {}, delete_risk=delete_risk)
        if known_risk is not None:
            # ⑮ 白名单外临时授权请求(blocked=False, requires_confirmation=True, auth_path): 放行到确认流程 —
            #    action_handler 识别 requires_confirmation 走 HITL, 用户确认后 grant_temp_auth; 不在此拦截 — 小欧 2026-08-10
            if known_risk.requires_confirmation and not known_risk.blocked:
                # P0-02回归修复(安全开关false=bypass): 白名单外临时授权请求同样auto_confirm直放,
                #   与L129-131普通确认bypass语义一致; 否则E2E自动化无人在线确认, HITL超时致任务failed — 小欧 2026-08-11
                if _is_skip_safety():
                    known_risk.auto_confirm = True
                    log_and_print(f"[ToolSafetyChecker] bypass自动放行(白名单外临时授权请求): tool={tool_name}, auth_path={known_risk.auth_path}, {known_risk.message}")
                else:
                    log_and_print(f"[ToolSafetyChecker] 白名单外临时授权请求,转HITL确认: tool={tool_name}, auth_path={known_risk.auth_path}, {known_risk.message}")
                return known_risk
            # #14 fix: 已知风险只拦截, 不触发确认(确认由 needs_confirm 路径驱动) — 小欧 2026-07-18
            known_risk.safety_level = "dangerous"
            log_and_print(f"[ToolSafetyChecker] 已知风险拦截(危险拒绝执行): tool={tool_name}, {known_risk.message}")
            return known_risk

        # ③ 确认策略分流: 开关只影响"是否询问确认", 不影响危险防护
        if _is_skip_safety():
            if self._get_needs_confirmation(tool_meta, params or {}, delete_risk=delete_risk):
                log_and_print(f"[ToolSafetyChecker] bypass自动放行(需确认工具,提示照出): tool={tool_name}")
                return SafetyResult(requires_confirmation=True, auto_confirm=True,
                        blocked=False, message="安全开关已绕过(提示照出)",
                        safety_level="destructive")
            logger.info(f"[ToolSafetyChecker] bypass自动放行(无需确认): tool={tool_name}")
            return SafetyResult(requires_confirmation=False,
                    blocked=False, message="安全开关已绕过",
                    safety_level="safe")

        if tool_meta.check_fn:
            try:
                custom_result = tool_meta.check_fn(params or {})
                if not custom_result.get("is_safe", True):
                    log_and_print(f"[ToolSafetyChecker] check_fn拦截: tool={tool_name}, {custom_result.get('message')}")
                    return SafetyResult(
                        blocked=True,
                        message=custom_result.get("message", "安全检查未通过"),
                        safety_level=custom_result.get("safety_level", "dangerous"),
                    )
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] check_fn异常,阻止执行: {e}")
                return SafetyResult(blocked=True,
                        message=f"安全检查异常(已阻止): {e}",
                        safety_level="dangerous")

        needs_confirm = self._get_needs_confirmation(tool_meta, params or {}, delete_risk=delete_risk)
        safety_level = "destructive" if needs_confirm else "safe"
        return SafetyResult(requires_confirmation=needs_confirm,
                blocked=False, message="", safety_level=safety_level)

    @staticmethod
    def _get_needs_confirmation(tool_meta, params: Dict, delete_risk: Optional["SafetyResult"] = None) -> bool:
        """获取生效的确认策略：delete动态判定 > action级 > 工具级 — 小欧 2026-08-04"""
        if delete_risk is not None:                       # delete: 动态判定(R3免/R4/R5确认)
            return delete_risk.requires_confirmation      # R3→_PASS→False(免确认); R4/R5→True
        if tool_meta.action_confirmation and params.get("action"):
            return tool_meta.action_confirmation.get(
                params["action"], tool_meta.needs_confirmation
            )
        return tool_meta.needs_confirmation

    @staticmethod
    def _check_known_risks(tool_name: str, params: Dict, delete_risk: Optional["SafetyResult"] = None) -> Optional["SafetyResult"]:
        """已知风险检测：路径越权(R1/R2) / delete R6 / 写入大小保护 / 代码注入 — 小沈 2026-06-17
        小欧 2026-06-25: 返回SafetyResult替代raw dict
        小欧 2026-06-27: 路径检查委托validate_tool_path(path_safe_check统一处理)
        小欧 2026-06-28: 增 delete_risk 入参, R6(项目根外递归) 在此无条件拦截
        # T1 (v1.43): 传递 mode 给 validate_tool_path(自动推断), 接收 4元组 (is_valid, msg, failed_path, category)
        # T2 (v1.43): 按 category+mode 显式分流, 替代 msg 字符串特征匹配(L170):
        #   - category=="system" 且写/删 → blocked 硬拦(永不授权)
        #   - category=="non_system" 且删 → blocked 硬拦(永不授权)
        #   - category=="non_system" 且写 → requires_confirmation+auth_path(任务级临时授权, 复用 L238-240)
        #   - category==None 且白名单外msg → requires_confirmation+auth_path(现状已有)
        #   - category=="system"/"non_system" 且读 → 放行(validate_path 读 mode 已处理)
        """
        is_valid, msg, failed_path, category = _validate_tool_path(tool_name, params)
        if not is_valid:
            # T2: 显式 category+mode 分流(替代 msg 字符串特征)
            if category == "non_system":
                # 非系统禁区: 删→硬拦永不授权(3.2.10/表五), 写→任务级临时授权请求
                # (validate_tool_path 已按 tool_name 推断 mode, 此处按注册名归一判断删除操作)
                from app.tools.tools_alias_mapper import normalize_tool_name  # P2: 防别名漏判 — 小欧 2026-08-10
                if normalize_tool_name(tool_name) == "delete":
                    log_and_print(f"[ToolSafetyChecker] 路径越权硬拦(非系统禁区,禁止删除): tool={tool_name}, auth_path={failed_path}, {msg}")
                    return SafetyResult(blocked=True, message=f"路径越权(非系统禁区,禁止删除): {msg}",
                                        safety_level="dangerous", auth_path=failed_path)
                # BUG-D: auth_path 取真正越权参数的真实路径(failed_path), 不再固定 path-or-dest
                log_and_print(f"[ToolSafetyChecker] 路径越权转任务级授权请求: tool={tool_name}, auth_path={failed_path or (params.get('path') or params.get('dest'))}, {msg}")
                return SafetyResult(requires_confirmation=True, blocked=False,
                                    message=f"路径超出白名单,需任务级授权: {msg}",
                                    safety_level="destructive",
                                    auth_path=failed_path or (params.get("path") or params.get("dest")))
            if category == "system":
                # 系统禁区写/删 → 硬拦永不授权
                log_and_print(f"[ToolSafetyChecker] 路径越权硬拦(系统禁区): tool={tool_name}, auth_path={failed_path}, {msg}")
                return SafetyResult(blocked=True, message=f"路径越权(系统禁区): {msg}",
                                    safety_level="dangerous", auth_path=failed_path)
            # category == None: 白名单外非禁区 → 临时授权请求
            # BUG-D: auth_path 取真正越权参数的真实路径(failed_path), 不再固定 path-or-dest
            log_and_print(f"[ToolSafetyChecker] 路径越权转临时授权请求: tool={tool_name}, auth_path={failed_path or (params.get('path') or params.get('dest'))}, {msg}")
            return SafetyResult(requires_confirmation=True, blocked=False,
                                message=f"路径超出白名单,需临时授权: {msg}",
                                safety_level="destructive",
                                auth_path=failed_path or (params.get("path") or params.get("dest")))

        # BUG-2 (三堂会审复核发现, v1.45): 写保护判定用归一化名 —
        #   原代码 `tool_name == _WRITE_RISK_TOOL("writetext")` 用 LLM 原始名, 别名(write_text/writefile等)
        #   normalize 前不等于 writetext → 写入大小保护被绕过; 统一走 normalize_tool_name 再判(P2 补齐)
        from app.tools.tools_alias_mapper import normalize_tool_name as _norm_tool
        if _norm_tool(tool_name) == _WRITE_RISK_TOOL:
            try:
                # 【#29修复】写入大小保护应优先用path参数（与路径检查一致），file_path兜底 — chendyg 2026-06-26
                # 2026-08-04 小欧 fix: content 可能为 dict/list(LLM结构化传参), 用isinstance(str)判typeskip写保护, 不崩不误拦 — 北京老陈审出多余转换(YAGNI), 写保护只需量字节数无需转JSON
                file_path = params.get("path") or params.get("file_path", "")
                content = params.get("content", "")
                p = Path(file_path)
                old_size = p.stat().st_size if p.exists() and p.is_file() else 0
                new_size = len(content.encode("utf-8")) if isinstance(content, str) and content else 0
                if old_size > 1024 and new_size > 0 and new_size < old_size * 0.20:
                    log_and_print(f"[ToolSafetyChecker] 数据保护硬拦(新内容远小于原内容): tool={tool_name}, path={file_path}, new={new_size}, old={old_size}")
                    return SafetyResult(blocked=True,
                            message=f"数据保护:新内容({new_size}字节)远小于原始内容({old_size}字节)")
            except Exception as e:
                logger.error(f"[ToolSafetyChecker] 写入检查异常,阻止执行: {e}")
                return SafetyResult(blocked=True, message=f"安全检查异常(已阻止): {e}")


        return None


_checker: Optional[ToolSafetyChecker] = None


def get_tool_safety_checker() -> ToolSafetyChecker:
    global _checker
    if _checker is None:
        _checker = ToolSafetyChecker()
    return _checker


__all__ = ["SafetyResult", "ToolSafetyChecker", "get_tool_safety_checker"]
