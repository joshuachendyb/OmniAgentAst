# -*- coding: utf-8 -*-
# 2026-10-04 小欧 - obs方案A: 删action.target(params承载目标)+document params file_path→path
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: 下载大小上限改引用 tool_constants.DOWNLOAD_MAX_BYTES(原 _MAX_FILE_SIZE=100MB), 功能零退化
# 2026-07-17 - 小欧 - HTTPStatusError hint 按状态码精化(4xx/5xx/429)
# 2026-07-20 - 小欧 - 常量依3.5改名: DOWNLOAD_MAX_BYTES→DOWNLOAD_INPUT_MAX_BYTES(私有内部常量前缀); 值依 v3.26 由100MB提升至1GB; 功能零退化
# 2026-07-25 - 小欧 - 新增非ASCII URL转码: download 支持中文域名/路径, 转码后走validate_url做DNS/SSRF检查
# 2026-08-06 - 小欧 - 核查8-05/8-06日志: url=None 在非ASCII转码块 url.encode 抛AttributeError落入catch-all记"意外错误"; 入口加url=None显式拦截(fetch_webpage/httpget同模式, 三网络工具统一), 返回ERR_INVALID_URL结构化错误, 不再落入catch-all
# 2026-08-10 - 小欧 - 注释更正: 下载目录未配置project_root时=用户主目录(不再是代码位置), 子目录download — 步骤1实施
# 2026-08-12 - 小欧 - 补漏: download 与 httpget 同病根(重定向到内网被SSRF防护拦截抛httpx.InvalidURL落入catch-all记ERROR);
#   用 http_client_sdk.is_ssrf_blocked_error 公用函数统一识别(httpget/fetch_webpage/download三工具一致), 返回ERR_INVALID_URL+warning
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
# 2026-08-13 - 小欧 - 修复修复: _stream_download抛的ValueError(文件过大/超过大小限制)落入catch-all归ERR_NET_UNKNOWN
#   【病根】L119-128大小超限抛ValueError, 外层仅except Exception归ERR_NET_UNKNOWN("未知网络错误"), 分类与成因不符, 重试引擎可能无谓重试
#   【改法】外层新增`except ValueError`分支, 归ERR_INVALID_PARAMS(输入/参数错误), hint给出"换用更小资源或分片"; 置于httpx异常分支后、Exception兜底前
# 2026-08-21 - 小欧 - 11.6.1: success分支调 with_artifact_file 声明产出物(下载文件)
# 2026-10-12 小欧 - tool_zh改短名词: 文件下载→下载
# 2026-10-16 - 小欧 - tool去检查化: 删 validate_path 合法性检查(dest 经 resolve 由派生检查覆盖), 仅留 for_write 警告。
# 2026-10-17 小欧 - 接入 path_utils.check_path_four_level 四级合法性总入口(下载目标用 WRITE; 未指定 dest 走默认目录)
# 2026-10-18 - 小欧 - WRITE 合法性检查改传 dest_path(绝对路径, 与 validate_path_for_write 口径一致),
#   原传 dest(裸名) 致相对路径被按 cwd 误判 —— 小欧-2026-10-18
# 2026-10-18 - 小欧 - dest 支持绝对路径: 绝对路径原样采用, 相对路径仍以下载目录为基准;
#   删去"必须落在下载目录内"的工具层硬拦, 落点是否获准交安全层判定(与其它写工具同口径), 仅保留 .. 拼写级防护 — 小欧-2026-10-18
# 2026-10-19 - 小欧 - dest 绝对化统一走公用 absolutize_path(value, base); get_download_dir 上移 app.utils.path_utils(单源, 安全入口同用)
# 2026-10-20 05:27 小欧 - 两处实测修复: Content-Length 非数字头(代理/异常服务器)int() 抛 ValueError
#   被误归类"文件超过下载大小限制", 改安全解析、非数字置0交流式累计口径; symlink 判定 realpath
#   与 abspath 对大小写还原口径不同(Windows 不区分大小写), 正常文件被判"路径被篡改"误报,
#   normcase 消除大小写差异后再比, 真 symlink/junction 仍可检出
"""
N2: download — 下载文件到本地

从network_tools.py拆分而来 — 小欧 2026-06-22
内聚: _stream_download / _map_network_error 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import os
import time as _time_mod
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import httpx

from app.tools.tool_response import build_success, build_error, with_artifact_file
from app.tools.network.http_client_sdk import create_http_client, HTTPClient, is_ssrf_blocked_error
from app.tools.network.network_register import check_network
from app.tools.validate.url_validator import validate_url, validate_proxy, transcode_url
from app.tools.validate.timeout_validator import validate_timeout
from app.utils.path_utils import OpCategory, check_path_four_level, validate_path_for_write, absolutize_path, get_download_dir  # 2026-10-17 小欧 - 路径四级合法性总入口; 仅业务警告, 合法性归路径安全层
# 2026-10-19 小欧 - dest 绝对化改调公用 absolutize_path(value, base)(基准=get_download_dir, 与安全入口同源); get_download_dir 上移 path_utils(单源)
from app.tools.toolhelper.error_hints import hint_for_write_error

from app.logger import logger

from app.tools.tool_constants import (
    ERR_INVALID_URL,
    DOWNLOAD_INPUT_MAX_BYTES,
    ERR_NETWORK_CREATE_DIR,
    ERR_NETWORK_DOWN,
    ERR_NETWORK_HTTP_ERROR,
    ERR_NETWORK_INVALID_PATH,
    ERR_NETWORK_REQUEST_ERROR,
    ERR_NETWORK_TIMEOUT,
    ERR_NETWORK_WRITE_FILE,
    ERR_INVALID_PARAMS,
    ERR_NET_UNKNOWN,
)


def _build_download_file_llm_data(
    exec_code: str, duration_ms: int, url: str = "", dest_path: str = "",
    file_size: int = 0, total_size: int = 0, content_type: str = "",
    err_code: str = "", detail: str = "", hint: str = "",
    timeout: int = 60, proxy: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """download_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 过滤None值"""
    _act_params = {"url": url, "dest": dest_path, "timeout": timeout}
    if proxy is not None:
        _act_params["proxy"] = proxy
    if headers is not None:
        _act_params["headers"] = headers
    if exec_code == "error":
        return {
            "summary": f"下载文件{url}，失败",
            "action": {"tool": "download", "tool_zh": "下载", "params": _act_params},
            "status": {"exec_code": "error", "message": "失败", "code": err_code, "detail": detail, "hint": hint if hint else "请检查URL和网络连接"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    size_str = f"{file_size}字节" if file_size else ""
    type_str = f", {content_type}" if content_type else ""
    # 2026-10-14 小欧 - summary 统一口径: 对象用 url(与失败分支一致), 结论=落盘路径+大小+类型(值全留, 去标签); status 原样不动 — 小欧-2026-10-14
    _result_parts = [dest_path]
    if size_str:
        _result_parts.append(size_str)
    if content_type:
        _result_parts.append(content_type)
    summary = f"下载文件{url}，成功：" + "，".join(_result_parts)
    return {
        "summary": summary,
        "action": {"tool": "download", "tool_zh": "下载", "params": _act_params},
        "status": {"exec_code": "success", "message": "成功" + (f":{size_str}{type_str}" if size_str or type_str else ""), "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"file_size": {"value": file_size, "text": size_str}, "content_type": {"value": content_type, "text": content_type}},
    }


_NET_ERROR_MAP = [
    (httpx.TimeoutException, ERR_NETWORK_TIMEOUT, "下载超时"),
    (httpx.HTTPStatusError, ERR_NETWORK_HTTP_ERROR, "下载失败"),
    (httpx.RequestError, ERR_NETWORK_REQUEST_ERROR, "网络请求失败"),
]


def _map_network_error(url: str, timeout: int, e: Exception, dest_path: str = "", duration_ms: int = 0) -> Dict[str, Any]:
    """将httpx异常映射为错误信息字典 — 小欧 2026-06-22"""
    for exc_type, code, prefix in _NET_ERROR_MAP:
        if isinstance(e, exc_type):
            detail = f"{prefix}({timeout}秒)：{url}"
            if isinstance(e, httpx.HTTPStatusError):
                detail = f"{prefix} (HTTP {e.response.status_code})：{url}"
            return {"error_detail": detail, "params": {"url": url, "dest": dest_path, "timeout": timeout}, "err_code": code, "detail": detail}
    logger.error(f"[download] 未知错误: {e}")
    return {"error_detail": str(e), "params": {"url": url, "dest": dest_path, "timeout": timeout}, "err_code": ERR_NET_UNKNOWN, "detail": str(e)}


async def _stream_download(client: HTTPClient, url: str, dest_path: str,
                           headers: dict, chunk_size: int = 8192) -> Tuple[int, str, int]:
    """流式下载文件到本地 — 小欧 2026-06-22 — 小欧 2026-06-24 增加大小限制+清理"""
    async with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        raw_total = response.headers.get("content-length")
        # 2026-10-20 小欧 - FIX: int(raw_total) 对非数字头(代理注入/异常服务器)抛 ValueError,
        #   落入外层 except ValueError 被误归类为"文件超过下载大小限制"; 非数字=无法预判,
        #   置 0 交流式累计口径(流内超限仍逐块拦截) — 小欧-2026-10-20
        try:
            total_bytes = int(raw_total) if raw_total else 0
        except ValueError:
            total_bytes = 0

        if raw_total and total_bytes > DOWNLOAD_INPUT_MAX_BYTES:
            raise ValueError(f"文件过大: {raw_total}字节, 限制: {DOWNLOAD_INPUT_MAX_BYTES}字节")

        downloaded = 0
        try:
            with open(dest_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    downloaded += len(chunk)
                    if downloaded > DOWNLOAD_INPUT_MAX_BYTES:
                        raise ValueError(f"下载超过大小限制({DOWNLOAD_INPUT_MAX_BYTES}字节)")
                    f.write(chunk)
        except Exception:
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception:
                logger.warning(f"[download] 清理失败: {dest_path}")
            raise
        return downloaded, content_type, total_bytes if raw_total else downloaded


async def download(
    url: str,
    dest: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    """从URL下载文件 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件"""
    if url is None:
        llm_data = _build_download_file_llm_data("error", 0, "", dest_path=dest or "", err_code=ERR_INVALID_URL, detail="URL不能为空", hint="请提供要下载的URL", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "download")
    if not timeout_valid:
        llm_data = _build_download_file_llm_data("error", 0, url, dest_path=dest or "", err_code=ERR_INVALID_URL, detail=timeout_err, hint="请检查超时设置", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)

    proxy_valid, proxy_err, _ = validate_proxy(proxy)
    if not proxy_valid:
        llm_data = _build_download_file_llm_data("error", 0, url, dest_path=dest or "", err_code=ERR_INVALID_URL, detail=proxy_err, hint="请检查代理配置", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)

    if dest is not None:
        if not isinstance(dest, str) or not dest.strip():
            llm_data = _build_download_file_llm_data("error", 0, url, dest_path="", err_code=ERR_NETWORK_INVALID_PATH, detail="dest不能为空", hint="请填写目标路径或留空自动命名", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        if any(p == ".." for p in dest.replace("\\", "/").split("/")):
            llm_data = _build_download_file_llm_data("error", 0, url, dest_path=dest, err_code=ERR_NETWORK_INVALID_PATH, detail="dest不允许路径遍历", hint="请使用合法文件名", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        dest_path = absolutize_path(dest, get_download_dir())
    else:
        filename = os.path.basename(urlparse(url).path) or f"download_{hash(url) & 0xFFFFFFFF}"
        dest_path = absolutize_path(filename, get_download_dir())
    # 2026-10-16 小欧 - tool去检查化: 合法性由路径安全层唯一检查(dest 经 resolve 得绝对路径), 此处仅业务警告
    _, _, path_warn = validate_path_for_write(dest_path)
    if path_warn:
        logger.warning(f"[download] {path_warn}")

    t0 = _time_mod.perf_counter()
    # 2026-10-17 小欧 - 路径检查走 check_path_four_level 四级合法性总入口(下载目标用 WRITE; 未指定 dest 交给默认目录)
    if dest:
        ok, err = check_path_four_level(dest_path, OpCategory.WRITE)
        if not ok:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest, detail=err, hint="请检查下载目标路径")
            return build_error(data={}, llm_data=llm_data)
    try:
        # 非ASCII URL转码(IDNA+percent-encoding) — 小欧 2026-07-25
        try:
            url.encode("ascii")
        except (UnicodeEncodeError, UnicodeDecodeError):
            url = transcode_url(url)

        is_valid, error_msg, warning_msg = validate_url(url)
        if not is_valid:
            detail = error_msg or "URL格式无效"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_INVALID_URL, detail=detail, hint="请检查URL格式", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        if warning_msg:
            logger.warning(f"[download] {warning_msg}")
        net_info = check_network()
        if not net_info["connected"]:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_NETWORK_DOWN, detail="网络不可用", hint="请检查网络连接", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)

        dest_dir = os.path.dirname(dest_path)
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_NETWORK_CREATE_DIR, detail=f"{type(e).__name__}: {str(e) or repr(e)}", hint=hint_for_write_error(e, dest_path), timeout=timeout, proxy=proxy, headers=headers)  # 2026-10-14 小欧 - 修片面: 建目录失败不止权限(父目录缺失/盘满皆可能), 按 errno 精确映射(复用 helper, 不编造) — 小欧-2026-10-14
            return build_error(data={}, llm_data=llm_data)

        req_headers = headers or {}

        # 2026-10-20 小欧 - FIX: realpath 与 abspath 对大小写还原口径不同(Windows 不区分大小写,
        #   传入大小写与磁盘真实拼写不一致时, 同一路径被判"路径被篡改(symlink)"误报);
        #   normcase 消除大小写差异后再比, 真 symlink/junction(指向变了)仍可检出 — 小欧-2026-10-20
        if os.path.exists(dest_path) and os.path.normcase(os.path.realpath(dest_path)) != os.path.normcase(os.path.abspath(dest_path)):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path=dest_path, err_code=ERR_NETWORK_INVALID_PATH, detail="路径被篡改(symlink)", hint="请检查目标路径", timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)

        async with create_http_client(timeout_sec=timeout, proxy=proxy) as client:
            downloaded, content_type, total_bytes = await _stream_download(client, url, dest_path, req_headers)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        # =============================================================================
        # 数据设计：file_path/total_size/content_type 全部通过 llm_data.summary 传入
        # summary 示例: "下载文件http://x/file.zip，成功：/path/file.zip，1024000字节，application/zip"
        # data = {}，无需额外字段 — 小欧 2026-07-06
        # =============================================================================
        llm_data = _build_download_file_llm_data("success", duration_ms, url, dest_path, downloaded, total_bytes, content_type, timeout=timeout, proxy=proxy, headers=headers)
        with_artifact_file(llm_data, dest_path)   # 11.6.1 产出物声明 — 小欧 2026-08-21
        # ---- observation_formatter route -------------------------------------------
        # branch: A- empty data — 无字段，输出"详情:\n" + 空
        # trigger: data == {}
        # handler: _format_scalar_data(data) — 空dict输出空字符串
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)
    except (PermissionError, OSError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=ERR_NETWORK_WRITE_FILE, detail=f"{type(e).__name__}: {str(e) or repr(e)}", hint=hint_for_write_error(e, dest_path), timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
    except httpx.InvalidURL as e:
        # httpx.InvalidURL: 重定向目标被SSRF防护拦截, 属预期防护, 返ERR_INVALID_URL+warning(不记ERROR) — 小欧 2026-08-12
        # 识别统一用 http_client_sdk.is_ssrf_blocked_error 公用函数(httpget/fetch_webpage/download三工具一致)
        _ssrf_info = is_ssrf_blocked_error(e)
        if _ssrf_info:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            logger.warning(f"[download] URL安全拦截(SSRF防护): {e}")
            llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=_ssrf_info["err_code"], detail=_ssrf_info["detail"], hint=_ssrf_info["hint"], timeout=timeout, proxy=proxy, headers=headers)
            return build_error(data={}, llm_data=llm_data)
        raise
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        error_info = _map_network_error(url, timeout, e, dest_path, duration_ms)
        if isinstance(e, httpx.HTTPStatusError):
            _sc = e.response.status_code
            if _sc == 429:
                _hint = "请求过于频繁(限流),请稍后重试或降低请求频率"
            elif 400 <= _sc < 500:
                # hint不重复具体状态码(detail已有"HTTP {_sc}"),仅给可行动建议 — 小欧 2026-07-17
                _hint = "客户端请求错误,请检查URL/请求方法与参数"
            elif 500 <= _sc < 600:
                _hint = "服务器暂时不可用,可稍后重试或换用其他地址"
            else:
                _hint = "请检查URL和网络连接"  # 兜底 — 小欧 2026-07-17
        else:
            _hint = "可增大timeout参数重试" if error_info["err_code"] == ERR_NETWORK_TIMEOUT else "请检查URL和网络连接"
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=error_info["err_code"], detail=error_info["detail"], hint=_hint, timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
    except ValueError as ve:
        # 文件超DOWNLOAD_INPUT_MAX_BYTES属输入/参数错误, 归ERR_INVALID_PARAMS而非ERR_NET_UNKNOWN, 避免重试引擎无谓重试/误导LLM — 小欧 2026-08-13 
        logger.error(f"[download] 下载大小超限: {ve}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=ERR_INVALID_PARAMS, detail=str(ve), hint="文件超过下载大小限制,请换用更小资源或分片", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        logger.error(f"[download] 未知错误: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_download_file_llm_data("error", duration_ms, url, dest_path, err_code=ERR_NET_UNKNOWN, detail=f"{type(e).__name__}: {str(e) or repr(e)}", hint="请检查URL和网络连接", timeout=timeout, proxy=proxy, headers=headers)
        return build_error(data={}, llm_data=llm_data)
