# -*- coding: utf-8 -*-
"""
N5: ping_port — 网络连通性诊断(ping+端口检测)

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _ping / _port_check / _build_ping_cmd / _parse_ping_output 等辅助函数
注意: _build_ping_llm_data和_build_port_check_llm_data是内部函数的builder,
     不是注册tool的builder。注册tool的builder只有_build_network_diagnose_llm_data。
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import platform
import re
import socket
import subprocess
import time as _time_mod
from typing import Any, Dict, List, Literal, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.validate.url_validator import _is_private_or_loopback_ip
from app.tools.validate.timeout_validator import validate_timeout
from app.tools.validate.tools_file_path_checker import validate_str_param

from app.utils.logger import logger
from app.tools.tool_constants import ERR_MISSING_PARAM
from app.tools.tool_constants import (
    ERR_INVALID_MODE,
    ERR_NETWORK_CONNECTION_ERROR,
    ERR_NETWORK_DNS_ERROR,
    ERR_NETWORK_INVALID_HOST,
    ERR_NETWORK_INVALID_PORT,
    ERR_NETWORK_TIMEOUT,
    ERR_NET_UNKNOWN,
    ERR_SHELL_COMMAND_NOT_FOUND,
)


well_known_ports = {
    20: "FTP-Data", 21: "FTP-Control", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS",
    465: "SMTPS", 587: "SMTP-MSA", 993: "IMAPS", 995: "POP3S",
    1433: "MSSQL", 1521: "Oracle", 3306: "MySQL", 3389: "RDP",
    5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-Proxy",
    8443: "HTTPS-Alt", 27017: "MongoDB",
}


def _build_network_diagnose_llm_data(
    exec_code: str, duration_ms: int, host: str = "", mode: str = "ping",
    err_code: str = "", detail: str = "", hint: str = "",
    port: Optional[int] = None, count: int = 4, timeout: int = 5,
) -> Dict[str, Any]:
    """network_diagnose的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 过滤None值"""
    _act_params = {"mode": mode, "host": host, "count": count, "timeout": timeout}
    if port is not None:
        _act_params["port"] = port
    if exec_code == "error":
        return {
            "summary": f"网络诊断失败: {host}",
            "action": {"tool": "ping_port", "tool_zh": "网络诊断", "target": host, "params": _act_params},
            "status": {"exec_code": "error", "message": "网络诊断失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查主机地址和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"网络诊断成功: {host}",
        "action": {"tool": "ping_port", "tool_zh": "网络诊断", "target": host, "params": _act_params},
        "status": {"exec_code": "success", "message": "网络诊断成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def _build_ping_llm_data(exec_code: str, duration_ms: int, host: str = "", is_reachable: bool = False,
                          packets_sent: int = 0, packets_received: int = 0, loss_rate: float = 0.0,
                          avg_latency=None, min_latency=None, max_latency=None,
                          err_code: str = "", detail: str = "", hint: str = "",
                          count: int = 4, timeout: int = 5) -> Dict[str, Any]:
    """ping内部函数的llm_data构建 — 小欧 2026-06-22"""
    _act_params = {"mode": "ping", "host": host, "count": count, "timeout": timeout}
    if exec_code == "error":
        return {
            "summary": f"Ping测试失败: {host}",
            "action": {"tool": "ping_port", "tool_zh": "网络诊断", "target": host, "params": _act_params},
            "status": {"exec_code": "error", "message": "Ping测试失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查主机地址和网络连接"},
            "duration_ms": duration_ms, "metrics": {},
        }
    status_text = "可达" if is_reachable else "不可达"
    metrics = {}
    if is_reachable:
        metrics["loss_rate"] = {"value": loss_rate, "text": f"{loss_rate}%"}
        if avg_latency is not None:
            metrics["avg_latency"] = {"value": avg_latency, "text": f"{avg_latency}ms"}
    return {
        "summary": f"Ping测试{'成功' if is_reachable else '失败'}:{host} {status_text}",
        "action": {"tool": "ping_port", "tool_zh": "网络诊断", "target": host, "params": _act_params},
        "status": {"exec_code": "success" if is_reachable else "error", "message": f"Ping {status_text}", "code": "" if is_reachable else ERR_NETWORK_TIMEOUT, "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": metrics,
    }


def _build_port_check_llm_data(exec_code: str, duration_ms: int, host: str = "", port: int = 0,
                                is_open: bool = False, service: str = "",
                                err_code: str = "", detail: str = "", hint: str = "",
                                timeout: int = 3) -> Dict[str, Any]:
    """port_check内部函数的llm_data构建 — 小欧 2026-06-22"""
    _act_params = {"mode": "port", "host": host, "port": port, "timeout": timeout}
    if exec_code == "error":
        return {
            "summary": f"端口检查失败: {host}:{port}",
            "action": {"tool": "ping_port", "tool_zh": "网络诊断", "target": f"{host}:{port}", "params": _act_params},
            "status": {"exec_code": "error", "message": "端口检查失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查主机地址和网络连接"},
            "duration_ms": duration_ms, "metrics": {},
        }
    status_text = "开放" if is_open else "关闭"
    return {
        "summary": f"端口 {port} ({service}) {status_text}: {host}:{port}",
        "action": {"tool": "ping_port", "tool_zh": "网络诊断", "target": f"{host}:{port}", "params": _act_params},
        "status": {"exec_code": "success", "message": f"端口{status_text}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms, "metrics": {},
    }


def _build_ping_cmd(host: str, count: int, timeout: int) -> List[str]:
    """根据平台构建ping命令 — 小欧 2026-06-22"""
    system = platform.system().lower()
    if system == "windows":
        return ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    return ["ping", "-c", str(count), "-W", str(timeout), host]


def _parse_ping_output(raw_output: str, system: str) -> dict:
    """解析ping输出 — 小欧 2026-06-22"""
    result = {"packets_sent": 0, "packets_received": 0, "packets_lost": 0, "loss_rate": 0.0,
              "min_latency": None, "avg_latency": None, "max_latency": None, "is_reachable": False}
    if system == "windows":
        loss = re.search(r"(?:已发送|Sent\s*=\s*)(\d+).*?(?:已接收|Received\s*=\s*)(\d+).*?(?:丢失|Lost\s*=\s*)(\d+).*?(\d+)%", raw_output, re.DOTALL | re.IGNORECASE)
        if loss:
            result.update(packets_sent=int(loss.group(1)), packets_received=int(loss.group(2)),
                          packets_lost=int(loss.group(3)), loss_rate=float(loss.group(4)))
        latency = re.search(r"(?:最短|Minimum)\s*[=:]\s*([\d.]+).*?(?:最长|Maximum)\s*[=:]\s*([\d.]+).*?(?:平均|Average)\s*[=:]\s*([\d.]+)", raw_output, re.DOTALL | re.IGNORECASE)
        if latency:
            result.update(min_latency=float(latency.group(1)), max_latency=float(latency.group(2)),
                          avg_latency=float(latency.group(3)))
        if "TTL=" in raw_output.upper() or (loss and int(loss.group(2)) > 0):
            result["is_reachable"] = True
    else:
        loss = re.search(r"(\d+)\s+packets transmitted.*?(\d+)\s+received.*?(\d+)%\s+packet loss", raw_output, re.DOTALL)
        if loss:
            sent, recv, rate = int(loss.group(1)), int(loss.group(2)), float(loss.group(3))
            result.update(packets_sent=sent, packets_received=recv, packets_lost=sent-recv, loss_rate=rate)
        latency = re.search(r"rtt min/avg/max/mdev\s*=\s*([\d.]+)/([\d.]+)/([\d.]+)", raw_output)
        if latency:
            result.update(min_latency=float(latency.group(1)), avg_latency=float(latency.group(2)),
                          max_latency=float(latency.group(3)))
        if result["packets_received"] > 0:
            result["is_reachable"] = True
    return result


async def _ping(host: str, count: int = 4, timeout: int = 5) -> Dict[str, Any]:
    """Ping测试(内部函数) — 只返回raw dict — 小欧 2026-06-22 — 小健 2026-06-22 修复铁规违反 — 小欧 2026-06-28 改用to_thread避免Python 3.13+ EventLoop NotImplementedError"""
    if not host or not host.strip():
        return {"success": False, "error_detail": "目标主机地址不能为空", "err_code": ERR_NETWORK_INVALID_HOST, "params": {"host": host}}
    host = host.strip()
    cmd = _build_ping_cmd(host, count, timeout)
    try:
        result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=count * timeout + 10)
        raw_output = result.stdout
    except subprocess.TimeoutExpired:
        return {"success": False, "error_detail": f"Ping超时({count * timeout + 10}秒)", "err_code": ERR_NETWORK_TIMEOUT, "params": {"host": host}}
    except FileNotFoundError:
        return {"success": False, "error_detail": "系统ping命令不可用", "err_code": ERR_SHELL_COMMAND_NOT_FOUND, "params": {"host": host}}

    parsed = _parse_ping_output(raw_output, platform.system().lower())
    reachable = parsed["is_reachable"]
    data = {**parsed}
    if not reachable:
        data.update(packets_received=0, packets_lost=parsed["packets_sent"],
                     loss_rate=100.0, min_latency=None, avg_latency=None, max_latency=None)
    return {"success": True, "data": data, "is_reachable": reachable, "parsed": parsed}


async def _port_check(host: str, port: int, timeout: int = 3) -> Dict[str, Any]:
    """检查端口是否开放(内部函数) — 只返回raw dict — 小欧 2026-06-22 — 小健 2026-06-22 修复铁规违反"""
    if not host or not host.strip():
        return {"success": False, "error_detail": "目标主机地址不能为空", "err_code": ERR_NETWORK_INVALID_HOST, "params": {"host": host, "port": port}}
    if port < 1 or port > 65535:
        return {"success": False, "error_detail": f"端口号无效: {port}", "err_code": ERR_NETWORK_INVALID_PORT, "params": {"port": port}}
    host = host.strip()
    if _is_private_or_loopback_ip(host):
        return {"success": False, "error_detail": f"禁止访问内网地址: {host}", "err_code": ERR_NETWORK_INVALID_HOST, "params": {"host": host, "port": port}}
    try:
        addrs = await asyncio.to_thread(socket.getaddrinfo, host, None)
        for addr in addrs:
            ip = addr[4][0]
            if _is_private_or_loopback_ip(ip):
                return {"success": False, "error_detail": f"DNS解析到内网地址: {ip}", "err_code": ERR_NETWORK_INVALID_HOST, "params": {"host": host, "port": port}}
    except socket.gaierror:
        return {"success": False, "error_detail": f"DNS解析失败: {host}", "err_code": ERR_NETWORK_DNS_ERROR, "params": {"host": host, "port": port}}
    service = well_known_ports.get(port, "Unknown")

    def _do_check():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            return sock.connect_ex((host, port)) == 0
        finally:
            sock.close()

    is_open = await asyncio.to_thread(_do_check)

    data = {"is_open": is_open, "service": service}
    return {"success": True, "data": data, "is_open": is_open, "service": service}


async def ping_port(
    host: str,
    mode: Literal["ping", "port"] = "ping",
    port: Optional[int] = None,
    count: int = 4,
    timeout: int = 5,
) -> Dict[str, Any]:
    """网络连通性诊断(ping+端口检测) — 小健 2026-06-21 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 修复铁规违反 — 小欧 2026-06-30 更名为ping_port"""
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "ping_port")
    if not timeout_valid:
        llm_data = _build_network_diagnose_llm_data("error", 0, host, mode, ERR_NETWORK_INVALID_HOST, timeout_err, hint="请检查超时设置", port=port, count=count, timeout=timeout)
        return build_error(data={"error_detail": timeout_err, "params": {"host": host, "mode": mode}}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    err = validate_str_param(host, "host")
    if err:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_network_diagnose_llm_data("error", duration_ms, host, mode, ERR_NETWORK_INVALID_HOST, err, hint="请检查主机地址", port=port, count=count, timeout=timeout)
        return build_error(data={"error_detail": err, "params": {"host": host, "mode": mode}}, llm_data=llm_data)
    if _is_private_or_loopback_ip(host):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_network_diagnose_llm_data("error", duration_ms, host, mode, ERR_NETWORK_INVALID_HOST, f"禁止访问内网地址: {host}", hint="请使用公网地址", port=port, count=count, timeout=timeout)
        return build_error(data={"error_detail": f"禁止访问内网地址: {host}", "params": {"host": host, "mode": mode}}, llm_data=llm_data)

    # SSRF防护：DNS解析后校验解析IP是否为内网（防hostname绕过）
    try:
        addrs = await asyncio.to_thread(socket.getaddrinfo, host, None)
        for addr in addrs:
            ip = addr[4][0]
            if _is_private_or_loopback_ip(ip):
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_network_diagnose_llm_data("error", duration_ms, host, mode, ERR_NETWORK_INVALID_HOST, f"DNS解析到内网地址: {ip}", hint="请使用公网地址", port=port, count=count, timeout=timeout)
                return build_error(data={"error_detail": f"DNS解析到内网地址: {ip}", "params": {"host": host, "mode": mode}}, llm_data=llm_data)
    except socket.gaierror:
        pass
    if mode == "ping":
        result = await _ping(host=host, count=count, timeout=timeout)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if result.get("success"):
            parsed = result.get("parsed", {})
            llm_data = _build_ping_llm_data("success", duration_ms, host, result.get("is_reachable", False),
                                            parsed.get("packets_sent", 0), parsed.get("packets_received", 0),
                                            parsed.get("loss_rate", 0.0), parsed.get("avg_latency"),
                                            parsed.get("min_latency"), parsed.get("max_latency"),
                                            count=count, timeout=timeout)
            # ---- observation_formatter route -------------------------------------------
            # branch: #21 fallback (key:val) — ping mode
            # trigger: 无上述20条分支匹配 — data 含 host/is_reachable/packets_sent 等
            # handler: _format_scalar_data(data) — key | value 单行列表
            # file:    observation_formatter.py:214
            # ------------------------------------------------------------------------------
            return build_success(data=result.get("data", {}), llm_data=llm_data)
        else:
            llm_data = _build_ping_llm_data("error", duration_ms, host, err_code=result.get("err_code", ERR_NET_UNKNOWN), detail=result.get("error_detail", ""), hint="请检查主机地址和网络连接", count=count, timeout=timeout)
            return build_error(data={"error_detail": result.get("error_detail", ""), "params": result.get("params", {})}, llm_data=llm_data)
    elif mode == "port":
        if port is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_network_diagnose_llm_data("error", duration_ms, host, mode, ERR_MISSING_PARAM, "缺少port参数", hint="端口模式需要提供port参数", port=port, count=count, timeout=timeout)
            return build_error(data={"error_detail": "mode='port'时port参数必填", "params": {"host": host, "mode": mode}}, llm_data=llm_data)
        try:
            result = await _port_check(host=host, port=port, timeout=timeout)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if result.get("success"):
                llm_data = _build_port_check_llm_data("success", duration_ms, host, port, result.get("is_open", False), result.get("service", ""), timeout=timeout)
                # ---- observation_formatter route -------------------------------------------
                # branch: #21 fallback (key:val) — port mode
                # trigger: 无上述20条分支匹配 — data 含 host/port/is_open/service
                # handler: _format_scalar_data(data) — key | value 单行列表
                # file:    observation_formatter.py:214
                # ------------------------------------------------------------------------------
                return build_success(data=result.get("data", {}), llm_data=llm_data)
            else:
                llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=result.get("err_code", ERR_NET_UNKNOWN), detail=result.get("error_detail", ""), hint="请检查主机地址和端口", timeout=timeout)
                return build_error(data={"error_detail": result.get("error_detail", ""), "params": result.get("params", {})}, llm_data=llm_data)
        except socket.gaierror:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NETWORK_DNS_ERROR, detail=f"DNS解析失败: {host}", hint="请检查主机地址", timeout=timeout)
            return build_error(data={"error_detail": f"DNS解析失败: {host}", "params": {"host": host, "port": port}}, llm_data=llm_data)
        except socket.timeout:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NETWORK_TIMEOUT, detail=f"端口 {port} 连接超时", hint="请检查主机和端口是否可达", timeout=timeout)
            return build_error(data={"error_detail": f"端口 {port} 连接超时", "params": {"host": host, "port": port}}, llm_data=llm_data)
        except OSError as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NETWORK_CONNECTION_ERROR, detail=str(e), hint="请检查主机和端口", timeout=timeout)
            return build_error(data={"error_detail": str(e), "params": {"host": host, "port": port}}, llm_data=llm_data)
        except Exception as e:
            logger.error(f"[port_check] 未知错误: {e}")
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_port_check_llm_data("error", duration_ms, host, port, err_code=ERR_NET_UNKNOWN, detail=str(e), hint="请检查主机地址和网络连接", timeout=timeout)
            return build_error(data={"error_detail": str(e), "params": {"host": host, "port": port}}, llm_data=llm_data)
    else:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_network_diagnose_llm_data("error", duration_ms, host, mode, ERR_INVALID_MODE, f"无效的诊断模式: {mode}", hint="请使用ping或port模式", port=port, count=count, timeout=timeout)
        return build_error(data={"error_detail": f"无效的诊断模式: {mode}", "params": {"host": host, "mode": mode}}, llm_data=llm_data)