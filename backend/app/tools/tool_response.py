# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 - 小健 - 三堂会审 修复(同源): is_success/is_warning/is_error 的 llm_data.status 可能为 str, 防御 AttributeError; 抽 _exec_code 统一取值, 保留 is_error 畸形结果(无llm_data)视为错误语义不退化
# 2026-08-21 - 小欧 - 11.6.1: 新增 extract_ext/with_artifacts/with_artifact_file 三个公共helper（DRY+KISS，产出型工具声明artifacts统一入口）
# 2026-10-19 - 小欧 - 新增 build_missing_dep_error: 缺库统一错误体(原先各工具各写一份"xxx未安装/请安装xxx",
#   文案不统一且只说没装不说怎么装, LLM 拿不到可执行动作)。文案分三级: 系统自动装失败→LLM 用 bash 自装
#   →转管理员; 锁定依赖(httpx/httpcore)不给自装指示, 直指按锁定版本由管理员装; 收尾统一给"改用其他
#   工具继续任务"的出路, ReAct loop 不停。错误码落 llm_data.status.code, 随全项目错误体约定。
"""
统一工具返回结构定义 — 小健 2026-05-21

【Phase 1 v6.0 重构 — 小欧 2026-06-21】
result 统一为 3 字段: data + llm_data + other_data
build_success/error/warning 签名重写，函数名即语义，无需 exec_code 参数
删除旧格式代码: _REQUIRED_FIELDS/_OPTIONAL_FIELDS/_add_optionals/register_builder/_default_builder/_BUILDERS/build_result

两层职责边界:
  tool_response.py (构建层) ← 本文件
    → 提供 build_success / build_error / build_warning（纯组装 result）
    → 提供 is_success / is_error（从 llm_data.status.exec_code 判断）
    → 工具函数、helper函数、Agent编排层 统一使用这些函数

  observation_formatter.py (格式化层)
    → LLM observation / 前端SSE / extract_status 格式化
    → 禁止构建结果,只消费和格式化
"""
import os
import sys
from typing import Any, Dict, List, Optional

from app.tools.tool_constants import ERR_MISSING_DEPENDENCY  # 2026-10-19 小欧 - 缺库错误码

_RESERVED_TOP_KEYS: set = {"data", "llm_data", "other_data"}


def build_success(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建成功响应 — 小欧 2026-06-21，小欧 2026-06-27 修复默认llm_data一致性"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "success"}}
    # 2026-10-04 小欧 - data层与llm_data层可同名出现 action(同名不同层): data.action 是工具自带快照, llm_data.action 是LLM展示目标, 取值勿混
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result


def build_error(data: Any = None, llm_data: Optional[Dict] = None,
                other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建错误响应 — 小欧 2026-06-21，小欧 2026-06-27 修复默认llm_data一致性"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "error"}}
    # 2026-10-04 小欧 - data层与llm_data层可同名出现 action(同名不同层): data.action 是工具自带快照, llm_data.action 是LLM展示目标, 取值勿混
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result


def build_warning(data: Any = None, llm_data: Optional[Dict] = None,
                  other_data: Optional[Dict] = None, **extra) -> Dict[str, Any]:
    """构建警告响应 — 小欧 2026-06-21，小欧 2026-06-27 修复默认llm_data一致性"""
    if llm_data is None:
        llm_data = {"status": {"exec_code": "warning"}}
    # 2026-10-04 小欧 - data层与llm_data层可同名出现 action(同名不同层): data.action 是工具自带快照, llm_data.action 是LLM展示目标, 取值勿混
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result


def build_missing_dep_error(tool_name: str, missing: Optional[List[str]] = None,
                            agent_can_install: Optional[bool] = None) -> Dict[str, Any]:
    """缺库统一错误体 — 小欧 2026-10-19

    系统已自动装过仍缺时才走本函数(tool_executor._missing_dep_guard), 故文案按
    「系统装不上 → LLM 自己试 → 都不行才转管理员」三级给出, 且每一级都是 LLM 可执行的下一步:

    1. 系统自动安装已失败 —— 直说, 免得 LLM 以为再等等就会自己好;
    2. LLM 自己装 —— Agent 持有 bash 工具且对 LLM 可见(已实测), 故给出可直接执行的命令;
    3. 转管理员 —— 只作兜底, 不是终止信号: 明说"改用其他工具继续任务", ReAct loop 不停。

    **锁定依赖另走一套文案**(httpx/httpcore 等, 见 dependency.LOCKED_PACKAGES):
    它们的版本被顶升即破坏既有协议, 裸装 = 装最新版 = 顶锁。故对这类依赖不给"自己装"的
    指示, 直指"按锁定版本、由管理员安装"。不在 shell 层加拦截 —— 那是为一个不值得的
    场景去动安全层; 差别只体现在提示语上, 足够让 LLM 不去乱升级。

    冻结版(frozen)例外: exe 内 pip 装了进程也看不见, bash 同样无效, 故不提"自己装", 直指管理员。

    形状随全项目错误体约定(各工具 _build_*_llm_data 同一套): 错误码落 llm_data.status.code。
    """
    from app.utils.dependency import LOCKED_PACKAGES   # 局部导入: 只此一处用, 不进模块头

    specs = [m for m in (missing or []) if m]
    pkg_list = ", ".join(specs) if specs else "未知依赖"
    if agent_can_install is None:
        agent_can_install = not getattr(sys, "frozen", False)

    def _names(items):
        return sorted({s.split("==")[0] for s in items})

    locked = [s for s in specs if s.split("==")[0] in LOCKED_PACKAGES]
    normal = [s for s in specs if s not in locked]

    hints = []
    if locked:
        locked_names = ", ".join(_names(locked))
        versions = ", ".join(f"{n}=={LOCKED_PACKAGES[n]}" for n in _names(locked))
        hints.append(f"其中 [{locked_names}] 为锁定依赖, 不可自行安装或升级"
                     f"(须按锁定版本 {versions} 安装, 换版本会破坏既有协议), 请转交管理员处理")
    if normal:
        cmd = "pip install " + ", ".join(_names(normal))
        if agent_can_install:
            hints.append(f"你可以用 bash 工具执行 `{cmd}` 安装后重试本工具")
        else:
            hints.append("当前为打包版, 无法在运行时安装依赖, 请转交管理员处理")
    if not hints:                      # 无依赖信息(如 missing 传空)
        hints.append("请改用功能相近的其他工具继续完成本次任务")

    # 收尾统一给"继续走"出路: 三级提示都是"下一步做什么", 不是终止信号, ReAct loop 照常进下一轮
    hint = "; ".join(hints) + "。若仍无法使用, 请改用功能相近的其他工具继续完成本次任务。"
    return build_error(
        data={},
        llm_data={
            "summary": f"{tool_name}，失败：缺少依赖库 [{pkg_list}]",
            "action": {"tool": tool_name, "tool_zh": tool_name, "params": {}},
            "status": {
                "exec_code": "error",
                "message": "失败",
                "code": ERR_MISSING_DEPENDENCY,
                "detail": f"缺少依赖库 [{pkg_list}]，系统自动安装未成功",
                "hint": hint,
            },
            "duration_ms": 0,
            "metrics": {},
        },
    )


def _exec_code(result: Dict[str, Any]) -> str:
    """2026-08-18 小健 三堂会审 修复(同源): llm_data.status 可能为 str, 防御 .get AttributeError"""
    llm_data = result.get("llm_data")
    if not isinstance(llm_data, dict):
        return ""
    _st = llm_data.get("status")
    return _st.get("exec_code", "") if isinstance(_st, dict) else ""


def is_success(result: Dict[str, Any]) -> bool:
    """判断返回是否成功 — 从llm_data.status.exec_code判断 — 小欧 2026-06-21"""
    return _exec_code(result) in ("success", "warning")


def is_warning(result: Dict[str, Any]) -> bool:
    """判断返回是否为warning — 小健 2026-06-25"""
    return _exec_code(result) == "warning"


def is_error(result: Dict[str, Any]) -> bool:
    """判断返回是否失败 — 从llm_data.status.exec_code判断 — 小欧 2026-06-21 — 小欧 2026-06-24 畸形结果视为错误"""
    llm_data = result.get("llm_data") if isinstance(result, dict) else None
    if not isinstance(llm_data, dict):
        return True  # 畸形结果(无llm_data)视为错误
    return _exec_code(result) == "error"


def extract_ext(file_path: str) -> str:
    """提取文件扩展名（小写无点），无扩展名返回 'file' — 小欧 2026-08-21 DRY"""
    _base = os.path.basename(file_path)
    return _base.rsplit(".", 1)[-1].lower() if "." in _base else "file"


def with_artifacts(llm_data: Optional[Dict], items: List[Dict[str, str]]) -> Dict:
    """产出型工具成功时声明产出物 [{name, path, type}]，挂 llm_data.action.artifacts（无白名单、OCP）— 小欧 2026-08-20"""
    if not isinstance(llm_data, dict):
        llm_data = {}
    _act = llm_data.setdefault("action", {})
    if not isinstance(_act, dict):
        _act = {}
        llm_data["action"] = _act
    _act["artifacts"] = list(items or [])
    return llm_data


def with_artifact_file(llm_data: Optional[Dict], file_path: str) -> Dict:
    """便捷声明：从文件路径自动提取 name/path/type，挂 llm_data.action.artifacts — 小欧 2026-08-21 KISS"""
    return with_artifacts(llm_data, [{
        "name": os.path.basename(file_path),
        "path": file_path,
        "type": extract_ext(file_path),
    }])
