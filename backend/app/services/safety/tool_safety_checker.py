# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 #14 fix: 删known_risk.requires_confirmation死分支
# 2026-07-18 小欧 #15/#50 fix: 删SafetyResult.is_safe死字段
# 2026-07-30 - 小欧 - auto_confirm+绕过时仍查needs_confirmation
# 2026-07-31 - 小欧 - 撤销auto_confirm: 恢复security.enabled=false原绕过路径, 删auto_confirm字段
# 2026-08-04 - 小欧 - 开关false仍拒绝已知风险: bypass只跳过确认询问不跳过危险防护, _check_known_risks(路径越权/写入保护/代码注入)检测到即blocked拒绝执行; 普通needs_confirmation仍auto_confirm放行 — 北京老陈驱动
# 2026-08-04 - 小欧 - 重构DRY: _check_known_risks提到两分支共同入口(无条件防线), 未注册check前置统一; 开关只分流"确认策略", 危险防护与开关解耦 — 三堂会审驱动(合规SRP/DRY/KISS最优)
# 2026-08-04 - 小欧 - delete专属安全(双轨接入): check_before_execute 一次性计算 delete_risk; R1/R2 仍由 known_risks(_is_forbidden_path) 覆盖, R6 入 _check_known_risks 无条件拦截, R3-R5 入 _get_needs_confirmation 确认分流; 惰性导入 delete_safety 避免循环依赖 — 北京老陈驱动(设计文档 v1.15)
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


from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from app.logger import logger
from app.config import get_config
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.services.safety.path_safe_check import validate_tool_path as _validate_tool_path

_WRITE_RISK_TOOL = "writetext"



@dataclass
class SafetyResult:
    """安全检查结果 — 替代raw dict — 小欧 2026-06-25
    #15 #50 fix: 删 is_safe 死字段(无人消费) — 小欧 2026-07-18"""
    blocked: bool = False
    requires_confirmation: bool = False
    message: str = ""
    safety_level: str = "safe"
    auto_confirm: bool = False


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
            return SafetyResult(blocked=True,
                    message=f"工具{tool_name}未注册",
                    safety_level="dangerous")

        # ① delete 专属判定一次性计算, 供②③两处消费(DRY) — 小欧 2026-08-04
        delete_risk = None
        if tool_name == "delete":
            from app.services.safety.delete_safety import check_delete_risk  # 惰性导入避免与delete_safety循环依赖 — 小欧 2026-08-04
            delete_risk = check_delete_risk(params or {})

        # ② 已知风险检测: 无条件防线(开关无关) — 路径越权(R1/R2)/delete R6/写入大小保护/代码注入即使开关false也拒绝 — 小欧 2026-08-04
        known_risk = self._check_known_risks(tool_name, params or {}, delete_risk=delete_risk)
        if known_risk is not None:
            # #14 fix: 已知风险只拦截, 不触发确认(确认由 needs_confirm 路径驱动) — 小欧 2026-07-18
            known_risk.safety_level = "dangerous"
            return known_risk

        # ③ 确认策略分流: 开关只影响"是否询问确认", 不影响危险防护
        if _is_skip_safety():
            if self._get_needs_confirmation(tool_meta, params or {}, delete_risk=delete_risk):
                return SafetyResult(requires_confirmation=True, auto_confirm=True,
                        blocked=False, message="安全开关已绕过(提示照出)",
                        safety_level="destructive")
            return SafetyResult(requires_confirmation=False,
                    blocked=False, message="安全开关已绕过",
                    safety_level="safe")

        if tool_meta.check_fn:
            try:
                custom_result = tool_meta.check_fn(params or {})
                if not custom_result.get("is_safe", True):
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
        小欧 2026-08-04: 增 delete_risk 入参, R6(项目根外递归) 在此无条件拦截"""
        is_valid, msg = _validate_tool_path(tool_name, params)
        if not is_valid:
            return SafetyResult(blocked=True, message=f"路径越权: {msg}")

        if delete_risk is not None and delete_risk.blocked:
            return delete_risk                                # R6 项目根外递归 — 小欧 2026-08-04

        if tool_name == _WRITE_RISK_TOOL:
            try:
                # 【#29修复】写入大小保护应优先用path参数（与路径检查一致），file_path兜底 — chendyg 2026-06-26
                file_path = params.get("path") or params.get("file_path", "")
                content = params.get("content", "")
                p = Path(file_path)
                old_size = p.stat().st_size if p.exists() and p.is_file() else 0
                new_size = len(content.encode("utf-8")) if content else 0
                if old_size > 1024 and new_size > 0 and new_size < old_size * 0.20:
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
