# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-04 - 小欧 - 新建: delete 工具专属差异安全判定(R3-R6), 设计文档 6.2(v1.15) — 北京老陈驱动
# 2026-08-10 - 小欧 - ⑫多授权域(步骤1实施, 北京老陈驱动): 新增_get_allowed_roots=[项目根]+授权目录get_allowed_dirs()/_is_inside_any; R3-R6判定从单项目根扩展为多授权根, 授权目录内递归降级R4确认不再误拦R6
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1盲点二/四: SafetyResult 与 _get_project_root_safety 均迁 app/tools/security, import 同步更新 — 小欧 2026-08-12
# 2026-08-13 - 小欧 - 三堂会审修复#25: _get_allowed_roots 读取授权目录的 except pass 静默吞→logger.warning 留痕
#   (授权目录读取失败致删除判定根集缺失无任何日志, 排查无迹)
# 2026-09-18 小欧 - safety_level→severity: SafetyResult字段重命名同步更新 — 小欧-2026-09-18
# 2026-09-18 - 小欧 - 落地: R6硬拦截文案"禁止删除项目根/授权目录外目录(递归)"→"禁止删除工作区外目录"(人话化, 逻辑不变) — 小欧-2026-09-18
# 2026-10-14 - 小欧 - SA4标注: 本文件=权限信任框架SA4(delete专属分支check_delete_risk R3-R6,执行第4步,由SA3总闸内调,R1/R2回SA5路径层覆盖) — 小欧-2026-10-14
# 2026-10-14 - 小欧 - 文档[33] 4.11-D: SafetyResult import 由 app.tools.security.safety_result 改 app.tools.tool_types(契约归工具层单源)
# 2026-10-14 - 小欧 - 文档[33] 4.1连带表: :30 _get_project_root_safety 改同包 app.safety.path_safe_check 导入
# 2026-10-15 北京老陈裁定(10规范: DRY/YAGNI/SRP/fail-closed/越层) - 四项修正:
#   ① DRY 删 _get_allowed_roots(与 path_safe_check 白名单构建、本仓 _get_protected_roots 三处同义), 改调 path_utils.get_allowed_roots 单源;
#   ② YAGNI/SRP __all__ 由 5 符号收为 ["check_delete_risk"](另 4 个零外部调用且均为 _ 私有命名, 属 backward 再导出);
#   ③ fail-closed: 路径归一化异常原 return _PASS(注"工具层validate会拦"=依赖下一道防线, 违 AGENTS 硬底线原则) → 改 blocked;
#      根集读取异常新增兜底 blocked(否则 inside 恒 False → 全路径误判区外, R5/R6 语义翻转);
#   ④ 越层: 删函数内 from app.config / get_ws_snapshot 延迟导入(safety→config / safety→tools.context), 收敛到单源一处且有注释说明。
#   ⑤ 内联(YAGNI): _as_bool / _PASS 再内联进 check_delete_risk, 删死 import typing.Any; 全文件现零模块级私有符号, __all__ 与实际导出完全一致。
# 2026-10-16 - 小欧 - 老陈裁定 severity destructive→risk(纯改名): 沙箱判定已同步, 行为不变。
"""
delete_safety — delete 工具专属安全检查(差异层)

职责: check_delete_risk 只判 R3-R6(项目根边界+递归差异), 恒返回 SafetyResult(R3→_PASS, 不用 None 表示放行)。
R1(系统盘/系统目录) 与 R2(磁盘根递归) 由 _check_known_risks → 三线 validate → classify_forbidden_path 无条件覆盖,
此处不重复实现(DRY/SRP, 三堂会审)。

调用方: tool_safety_checker.check_before_execute 对 delete 工具一次性计算 delete_risk, 双轨消费:
        R6 blocked 入 _check_known_risks 无条件拦截, R3-R5 入 _get_needs_confirmation 确认分流。

小欧 2026-08-04
"""
import os
from pathlib import Path

from app.tools.tool_types import SafetyResult  # 2026-10-14 小欧 - 文档[33] 4.11-D: 类型迁 tool_types
from app.session_workspace import session_workspace_paths  # 2026-10-15 北京老陈裁定(分层): 快照组迁中立层, 解 safety→tools 越层
from app.utils.path_utils import get_allowed_roots  # 2026-10-15 北京老陈裁定: 允许根单源(DRY), 本文件不再自持一份
from app.logger import logger  # #25: 授权目录失败需 warning


def check_delete_risk(params: dict) -> SafetyResult:
    """delete 专属差异判定(R3-R6) — 小欧 2026-08-04, 2026-08-10 ⑫多授权域(项目根+授权目录)

    恒返回 SafetyResult(从不用 None), 使调用侧可用 `delete_risk is not None`
    区分"是delete工具", R3 直接内联构造放行产物(修 v1.9 R3=None 导致
    _get_needs_confirmation 落入原逻辑 needs_confirmation=True 的缺陷)。
    R1/R2 由 _check_known_risks(validate_tool_path) 覆盖, 此处不重复。
    补D: 递归删除走 os.walk 时各子路径逐项判定, 任一越权即 R6。
    [SA4] 权限信任框架第4步: 由SA3总闸内调, R1/R2回SA5路径层覆盖 — 小欧-2026-10-14
    """
    path = str(params.get("path") or "").strip()
    # 2026-10-15 北京老陈裁定(内联): 原 _as_bool() 单行函数已内联 ——
    #   isinstance 前置是冗余分支, isinstance(v,bool) 时 str(True).lower()=="true" 本就命中; 且全仓另有 3 处同义实现。
    _rv = params.get("recursive", False)
    recursive = (str(_rv).strip().lower() in ("1", "true", "yes", "on"))  # 防 LLM 传字符串 'false' 被 bool() 当真

    try:                                                        # 路径归一化
        p = Path(os.path.expanduser(path)).resolve()
    except Exception as e:
        # 2026-10-15 北京老陈裁定(修 fail-open): 原为 return _PASS 并注"工具层validate会拦",
        #   属依赖下一道防线(违 AGENTS「硬底线不依赖前面防线」)。归一化失败即判 blocked, 宁可拒不可放。
        logger.warning(f"[delete_safety] 路径归一化失败, 按拒绝处理: {path!r} ({e})")
        return SafetyResult(blocked=True, requires_confirmation=False,
                            message=f"删除路径非法: {path}", severity="dangerous")

    try:
        allowed_roots = get_allowed_roots(session_workspace_paths())  # 单源: 项目根+授权目录+会话目录(⑫)
    except Exception as e:
        # fail-closed: 根集读不出时若继续判, _is_inside_any 恒 False → 全部路径误判区外(R5/R6), 语义翻转
        logger.warning(f"[delete_safety] 允许根读取失败, 按拒绝处理: {e}")
        return SafetyResult(blocked=True, requires_confirmation=False,
                            message=f"删除安全判定不可用(根集读取失败): {e}", severity="dangerous")

    inside_proj = any(p == root or root in p.parents for root in allowed_roots)

    # --- R6 全部允许根外递归 → 拒 ---
    if (not inside_proj) and recursive:
        return SafetyResult(blocked=True, message=f"禁止删除工作区外目录: {path}", severity="dangerous")  # 7.3.3-C16: "项目根/授权目录外目录(递归)"→"工作区外" — 小欧-2026-09-18

    # --- R4 允许根内递归 → 确认 / R5 允许根外普通 → 确认 ---
    if (inside_proj and recursive) or (not inside_proj):
        return SafetyResult(requires_confirmation=True, blocked=False,
                            message=f"删除需确认: {path}", severity="risk")

    # --- R3 允许根内普通 → 放行(免确认), 恒非None ---
    # 2026-10-15 北京老陈裁定(内联): 原模块级常量 _PASS 已内联, 全文件零模块级可变单例, 免多对象共享之嫌。
    return SafetyResult(blocked=False, requires_confirmation=False,
                        message="", severity="safe")


# 2026-10-15 北京老陈裁定(YAGNI): __all__ 原导出 5 个符号, 其中 _as_bool/_PASS/
#   原 _get_allowed_roots/_is_inside_any 共 4 个【零外部调用】且均为 _ 私有命名 ——
#   属 backward 再导出(与 AGENTS 已批的 __all__ 死条目同型)。现只导出唯一消费方。
__all__ = ["check_delete_risk"]
