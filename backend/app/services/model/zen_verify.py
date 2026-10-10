# -*- coding: utf-8 -*-
"""zen_verify — ZenithFree 双路验证服务（北京老陈 2026-10-10）

职责(SRP): 只做「两套验证方法各跑一遍远端免费模型 → 双路结果对比 → 落盘 txt」。
  两路方法**故意不复用**: zen_gate 是外部独立验证库(某些模型的验证配方先在那里更新)，
  opencodeZenAdapter 是系统现役配方; 共用任一实现就不是"对比"了(DRY 在此让位于验证目的)。

对外三个函数:
  - verify_provider_zen(): 拉免费模型 → 双路并发验证 → 落盘 → 返回对比结果
  - list_reports():         列历史报告(时间倒序)
  - read_report(name):      读指定报告内容

编辑历史:
  2026-10-10 小欧 - 新建。双路对比(zen_gate 外部库 vs opencodeZenAdapter) + Semaphore 限并发
    + 结果落 files/zen_verify/*.txt(复用 file_persist._files_root 目录分流, DRY) — 小欧-2026-10-10
  2026-10-10 小欧 - 三堂会审修正 4 项: ①zen_gate 路改用其自带 tools_chat/tools_flat(is_responses_model
    决定端点), 不再自造第二套配方——外部库就是"最新配方"的权威源, 自造等于没对比; ②verdict 增
    zen_unavailable 态: 库缺失时 adapter 通过不应被误判成"分歧"(那会让用户去改 adapter);
    ③去掉 _adapter_tools 透传函数(接收 adapter 参数却不用, 违反 KISS-DIRECT), 工具定义并入调用处;
    ④报告文件名时间戳用文件系统安全格式(Windows 禁 ':'), 与 file_persist 同款替换 — 小欧-2026-10-10
  2026-10-10 小欧 - 归并行内注释到本板块: zen_gate 外部库路径(项目外独立迭代, 不可复制进项目,
    否则失去"先在外部更新配方"的意义) 与 Authorization 空 key 时去掉畸形 Bearer 头 — 小欧-2026-10-10
"""
import asyncio
import importlib.util
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.file_persist import _files_root
from app.llm.adapters import get_provider_adapter
from app.logger import logger
from app.services.model import model_service as svc

_ZEN_GATE_FILE = Path(r"F:\agenttool\ZenFree-Test-20260923\zen_gate.py")
# 并发上限: 免费模型 20+, 串行每模型 60s 超时要等 20 分钟; 5 并发整体 2-3 分钟。
#   两路共用同一信号量 —— 同一 provider 的对端, 不因开两路就把压力翻倍。
_CONCURRENCY = 5
_REQUEST_TIMEOUT = 60.0
# 免费层识别口径(与 zen_gate.is_free 同源): -free 后缀或 big-pickle
_FREE_SUFFIX = "-free"
_FREE_SPECIAL = ("big-pickle",)

_REPORT_DIRNAME = "zen_verify"
_LINE = "=" * 78

_ZEN_UNAVAILABLE = "zen_gate 库不可用(未找到 zen_gate.py)"


def _is_free(model_id: str) -> bool:
    """免费层识别 — 与 zen_gate.is_free 同一口径"""
    return model_id.endswith(_FREE_SUFFIX) or model_id in _FREE_SPECIAL


def _load_zen_gate():
    """动态 import 外部 zen_gate 库; 不可用返回 None(那一路标记 unavailable, 另一路照常)"""
    if not _ZEN_GATE_FILE.is_file():
        return None
    try:
        # 按路径加载而非 sys.path: 免污染全局模块搜索路径, 且同名库并存不打架
        spec = importlib.util.spec_from_file_location("zen_gate_ext", _ZEN_GATE_FILE)
        if spec is None or spec.loader is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        logger.warning("[zen_verify] zen_gate 库加载失败, 该路标记不可用: %s", e)
        return None


def _pick_error(resp: httpx.Response) -> str:
    """从失败响应提取可读原因(优先远端 error.message, 退回原始文本首行)"""
    try:
        body = resp.json()
        if isinstance(body, dict):
            err = body.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])[:200]
            if body.get("message"):
                return str(body["message"])[:200]
    except Exception:
        pass
    return (resp.text or "")[:200].replace("\n", " ").strip()


def _tool_stub(name: str, desc: str, prop: str) -> Dict[str, Any]:
    """单条 bash/read 工具定义(双层 function 包装; 门禁只认名字精确 bash/read)"""
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": {prop: {"type": "string"}},
                       "required": [prop]}}}


async def _verify_by_adapter(model: str, api_base: str, api_key: str,
                             sem: asyncio.Semaphore) -> Dict[str, Any]:
    """adapter 路: 走 opencodeZenAdapter 的四条件(UA/session/stream/tools)"""
    adapter = get_provider_adapter("opencodeZen")
    endpoint_rel = adapter.endpoint_for(model)        # /chat/completions 或 /responses
    out: Dict[str, Any] = {"ok": False, "endpoint": endpoint_rel, "status": -1, "error": ""}
    tools = [_tool_stub("bash", "Executes a given command.", "command"),
             _tool_stub("read", "Read a file.", "filePath")]
    body = {"model": model, "messages": [{"role": "user", "content": "Say OK"}],
            "max_tokens": 64, "tools": tools}
    if endpoint_rel == "/responses":
        body = adapter.to_responses_body(body, model)
    body = adapter.ensure_gate_body(body)             # 强制 stream:true
    headers = dict(adapter.static_headers(api_key))
    headers.update(adapter.per_request_headers())
    # 空 key 摘掉 Authorization: 基类无条件造 "Bearer " 畸形头, httpx 发请求前就抛
    # IllegalProtocolError(adapter 路一个模型都验不到)。与 fetch_remote_models 同口径 ——
    # 免费层靠 UA 身份而非 key 通过, 无 key 是正常场景不是配置错误。
    if not api_key.strip():
        headers.pop("Authorization", None)
    headers["Content-Type"] = "application/json"
    async with sem:
        try:
            async with httpx.AsyncClient(trust_env=False, timeout=_REQUEST_TIMEOUT) as client:
                resp = await client.post(
                    f"{api_base.rstrip('/')}{endpoint_rel}", headers=headers,
                    content=json.dumps(body, ensure_ascii=False).encode("utf-8"))
            out["status"] = resp.status_code
            out["ok"] = resp.status_code == 200
            if not out["ok"]:
                out["error"] = _pick_error(resp)
        except Exception as e:
            out["error"] = f"ERR {type(e).__name__}: {e}"[:200]
    return out


async def _verify_by_zen_gate(model: str, sem: asyncio.Semaphore,
                             zg) -> Dict[str, Any]:
    """zen_gate 路: 外部库的同步调用, to_thread 包起来与 adapter 路并发。

    tools 传 None 让 zen_gate 自选(它按 is_responses_model 决定用 tools_flat 还是 tools_chat)——
    这正是"外部库持有最新配方"的要点, 自造工具反而使对比失去意义。
    """
    out: Dict[str, Any] = {"ok": False, "endpoint": "", "status": -1, "error": ""}
    if zg is None:
        out["error"] = _ZEN_UNAVAILABLE
        return out
    async with sem:
        try:
            r = await asyncio.to_thread(zg.call, model, "Say OK", int(_REQUEST_TIMEOUT), None, None)
            out["ok"] = bool(r.get("ok"))
            out["endpoint"] = str(r.get("endpoint") or "")
            out["status"] = int(r.get("status", -1))
            if not out["ok"]:
                out["error"] = str(r.get("error") or "")[:200]
        except Exception as e:
            out["error"] = f"ERR {type(e).__name__}: {e}"[:200]
    return out


def _verdict(zen: Dict[str, Any], ada: Dict[str, Any], zen_available: bool) -> str:
    """一致性判定。

    zen_unavailable 是独立态而非分歧: 库缺失时 adapter 通过只说明"没比成",
    误判成分歧会把用户引去改 adapter —— 那是对不存在的问题下药。
    """
    if not zen_available:
        return "zen_unavailable"
    if zen["ok"] and ada["ok"]:
        return "both_pass"
    if not zen["ok"] and not ada["ok"]:
        return "both_fail"
    return "diverge"


async def _free_model_ids(provider: str, provider_cfg: Dict[str, Any]) -> tuple:
    """拉远端最新免费模型; 拉不到才回落已配置模型。返回 (ids, 来源)"""
    remote = await svc.fetch_remote_models(provider)
    ids = [m["id"] for m in (remote.get("models") or [])] if remote.get("ok") else []
    if ids:
        return ids, "remote"
    configured = [m for m in (provider_cfg.get("models") or []) if isinstance(m, str)]
    return configured, "configured"


async def verify_provider_zen(name: str) -> Dict[str, Any]:
    """拉远端最新免费模型 → 双路并发验证 → 落盘 txt → 返回对比结果"""
    provider_cfg = svc.get_provider_raw_entry(name)
    api_base = str(provider_cfg.get("api_base") or "").strip()
    if not api_base:
        raise ValueError("该 Provider 未配置 api_base，请先到模型 Tab → ③ Provider 配置填写")
    api_key = str(provider_cfg.get("api_key") or "")

    ids, source = await _free_model_ids(name, provider_cfg)
    models = [m for m in ids if _is_free(m)]
    if not models:
        return {"ok": False, "provider": name, "message": "未获取到免费层模型",
                "results": [], "report_path": "", "summary": {}}

    zg = _load_zen_gate()
    zen_available = zg is not None
    sem = asyncio.Semaphore(_CONCURRENCY)
    flat = await asyncio.gather(*[
        t for m in models
        for t in (_verify_by_zen_gate(m, sem, zg), _verify_by_adapter(m, api_base, api_key, sem))
    ])

    results = [{
        "model": m,
        "zen_gate": flat[2 * i],
        "adapter": flat[2 * i + 1],
        "verdict": _verdict(flat[2 * i], flat[2 * i + 1], zen_available),
    } for i, m in enumerate(models)]
    results.sort(key=lambda r: r["model"].lower())

    summary = {
        "total": len(results),
        "both_pass": sum(1 for r in results if r["verdict"] == "both_pass"),
        "both_fail": sum(1 for r in results if r["verdict"] == "both_fail"),
        "diverge": sum(1 for r in results if r["verdict"] == "diverge"),
        "zen_unavailable": sum(1 for r in results if r["verdict"] == "zen_unavailable"),
        "source": source,
        "zen_gate_available": zen_available,
    }
    return {"ok": True, "provider": name, "results": results,
            "report_path": _write_report(name, results, summary), "summary": summary}


def _report_dir() -> Path:
    """报告目录: 复用 file_persist._files_root 的目录分流(debug→backend/files, 正式→~/.omniagent/files)"""
    d = _files_root() / _REPORT_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp() -> str:
    """文件名时间戳(Windows 禁 ':' 作文件名, 与 file_persist 同款替换)"""
    return datetime.now().strftime("%Y%m%d-%H%M%S")


_VERDICT_CN = {"both_pass": "一致通过", "both_fail": "一致失败",
               "diverge": "分歧", "zen_unavailable": "未比对"}


def _write_report(provider: str, results: List[Dict[str, Any]],
                  summary: Dict[str, Any]) -> str:
    """落盘纯文本报告, 返回文件绝对路径"""
    path = _report_dir() / f"zen_verify-{_stamp()}.txt"
    lines = [
        "ZenithFree 双路验证报告",
        "时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        f"Provider: {provider}",
        f"模型来源: {summary['source']}   "
        f"zen_gate 库: {'可用' if summary['zen_gate_available'] else '不可用'}",
        f"模型数: {summary['total']}",
        _LINE,
        "%-30s %-12s %-12s %-10s %s" % ("模型", "zen_gate", "adapter", "一致性", "原因"),
    ]
    for r in results:
        zen, ada = r["zen_gate"], r["adapter"]
        z_s = "%s %s" % (zen["status"], "OK" if zen["ok"] else "X")
        a_s = "%s %s" % (ada["status"], "OK" if ada["ok"] else "X")
        reason = zen.get("error") or ada.get("error") or ""
        lines.append("%-30s %-12s %-12s %-10s %s"
                     % (r["model"], z_s, a_s, _VERDICT_CN[r["verdict"]], reason[:70]))
    lines.append(_LINE)
    lines.append("汇总: 一致通过 %d / 一致失败 %d / 分歧 %d / 未比对 %d / 总计 %d"
                 % (summary["both_pass"], summary["both_fail"],
                    summary["diverge"], summary["zen_unavailable"], summary["total"]))
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def list_reports() -> Dict[str, Any]:
    """列历史报告(时间倒序)"""
    try:
        d = _report_dir()
        files = sorted((p for p in d.glob("zen_verify-*.txt") if p.is_file()),
                       key=lambda p: p.name, reverse=True)
    except Exception as e:
        return {"ok": False, "message": str(e), "reports": []}
    return {"ok": True, "reports": [
        {"name": p.name, "mtime": p.stat().st_mtime, "size": p.stat().st_size}
        for p in files]}


def read_report(name: str) -> Dict[str, Any]:
    """读指定报告内容(只允许 zen_verify-*.txt, Path.name 挡目录穿越)"""
    safe = Path(name).name
    if not (safe.startswith("zen_verify-") and safe.endswith(".txt")):
        return {"ok": False, "message": "非法报告名", "content": ""}
    try:
        p = _report_dir() / safe
    except Exception as e:
        return {"ok": False, "message": str(e), "content": ""}
    if not p.is_file():
        return {"ok": False, "message": "报告不存在", "content": ""}
    return {"ok": True, "content": p.read_text(encoding="utf-8")}


__all__ = ["verify_provider_zen", "list_reports", "read_report"]