# -*- coding: utf-8 -*-
"""
deps — API 统一鉴权依赖（token）

服务绑 0.0.0.0（多机部署前提），此前 13 个 router 全部裸挂，局域网任意设备可直调任何接口
（读全部明文密钥、改密钥、越权读会话）。本模块提供唯一鉴权点，由 main.py 在 include_router
处一次性挂载（KISS：不逐个改 router 定义）。

设计要点：
  - token 存 security.api_token，支持环境变量覆盖（多机统一配置，不必逐台改 yaml）
  - 支持 Authorization: Bearer 与 X-API-Token 两种头
  - 未配置 token 时拒绝所有受保护请求（fail-closed），显式 OMNIAGENT_REQUIRE_AUTH=0 才放行
  - 失败返回 401 且文案统一，不区分"token 不对"与"未配置"（防探测）

编辑历史:
  2026-09-26 小欧 - 新建；_is_localhost 改用 ipaddress.is_loopback（消除与白名单解析的
    两套实现，顺带堵掉"伪造 X-Forwarded-For: localhost"免口令）；豁免路径提为命名常量
    （原为内联字面量，与 router 定义分处两地，对不上即死锁）。
  2026-09-26 小欧 - **删除**应用层 XFF 解析与 TRUST_PROXY_HEADERS：uvicorn 的
    ProxyHeadersMiddleware 已负责代理信任判定，远程客户端伪造 XFF 改不了 request.client.host，
    应用再自行解析属重复实现且易出判断分歧。
  2026-09-27 小欧 - 按北京老陈裁定重排判定顺序（设口令只能本机 / 白名单只是免口令登录 /
    其余一律要口令）；精简冗长注释（XFF 取值争论史与 _is_localhost 三堂会审说明压缩为结论）。
  2026-09-27 小欧 - 安全加固: 新增 _forwarded_allow_ips_all/_is_trusted_localhost。
    uvicorn 被配成 FORWARDED_ALLOW_IPS=* 时任何客户端可伪造 client.host 为 127.0.0.1，
    免口令进（可读全部明文密钥、可改口令）；应用层无法区分真回环与伪造，故此时
    **取消回环豁免、一律要口令**（fail-closed）。默认配置不受影响，本机开发照常免口令。
    同轮修 DRY: _resolve_ip_allowlist 里 join 时的 `if str(x).strip()` 是冗余（尾部
    split 后的 `if x.strip()` 已过滤第二次），删之。另修 security 出口不再整体透传。
"""
import hmac
import ipaddress
import os
from typing import Optional

from fastapi import HTTPException, Request

# 2026-09-26 - 小欧 - [72]第九章(9.6-1): token 配置键与环境变量名（集中在此，避免散落各处硬编码字符串）
API_TOKEN_CONFIG_KEY = "security.api_token"   # config.yaml 中的键
API_TOKEN_ENV = "OMNIAGENT_API_TOKEN"         # 环境变量名（优先于配置文件，便于多机统一配置）
# 显式关闭鉴权的环境变量（仅供本机开发/自动化测试显式声明；生产不得设置）
REQUIRE_AUTH_ENV = "OMNIAGENT_REQUIRE_AUTH"
# 首次设置豁免的端点路径单一来源。原为内联字面量、auth_routes 又各写一次前缀，
# 同一事实两处硬编码，改路径必漏一处（漏一处=没口令就永远设不了口令的死锁）。
# verify_token 只对 GET /auth/status 做豁免；AUTH_TOKEN_PATH 仅为写端点路径的权威定义。
AUTH_TOKEN_PATH = "/api/v1/auth/token"
AUTH_STATUS_PATH = "/api/v1/auth/status"
# 鉴权失败统一文案。严禁在此拆分"未配置"与"不匹配"两种措辞 —— 那会让攻击者从 401 body
# 就能探测服务端是否已启用口令。是否已配置由豁免的 GET /auth/status 告知前端。
AUTH_FAIL_MESSAGE = "访问口令无效或缺失"
# IP/CIDR 白名单（白名单内免口令），支持环境变量与配置文件两种来源。
# ⚠ 白名单内等于无鉴权（可读全部明文密钥），只应放可信网段。
IP_ALLOWLIST_CONFIG_KEY = "security.ip_allowlist"
IP_ALLOWLIST_ENV = "OMNIAGENT_IP_ALLOWLIST"


def _resolve_configured_token() -> str:
    """取配置中的 token：环境变量优先（多机统一配置），回落配置文件。空字符串表示未配置。"""
    env_val = (os.environ.get(API_TOKEN_ENV) or "").strip()
    if env_val:
        return env_val
    try:
        from app.config import get_config
        val = get_config().get(API_TOKEN_CONFIG_KEY)
        return str(val or "").strip()
    except Exception:
        # 配置读取失败一律按"未配置"处理（fail-closed，不因读不到配置就放行）
        return ""


def _auth_required() -> bool:
    """是否启用鉴权。默认启用；仅显式 OMNIAGENT_REQUIRE_AUTH=0 时关闭（供本机开发/测试）。"""
    return (os.environ.get(REQUIRE_AUTH_ENV) or "1").strip() not in ("0", "false", "False")


def _client_ip(request: Request) -> str:
    """取来源 IP = request.client.host。

    不自行解析 X-Forwarded-For：代理信任判定已由 uvicorn 的 ProxyHeadersMiddleware 负责
    （只有对端可信时才改写 client.host），应用再解析一遍属重复实现且判断标准易分歧。
    """
    return request.client.host if request.client else ""


def _is_localhost(ip: str) -> bool:
    """是否本机回环地址（127.0.0.0/8 或 ::1）。解析失败按"非回环"处理，往下走鉴权。"""
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def _forwarded_allow_ips_all() -> bool:
    """uvicorn 是否被配成"信任任意来源的 X-Forwarded-For"（FORWARDED_ALLOW_IPS=*）。

    2026-09-27 小欧 - 安全加固。uvicorn 默认 forwarded_allow_ips="127.0.0.1"，此时远程客户端
    伪造 XFF 改不了 request.client.host，回环判定可信。但一旦被配成 `*`（常见于"反代在内网、
    懒得列 IP"的部署），**任何客户端都能把 client.host 伪造成 127.0.0.1** → _is_localhost
    判真回环 → 免口令进，可读全部明文密钥、可改口令。

    此时应用层**无法区分**真回环与伪造（两者 client.host 都是 127.0.0.1），故 fail-closed：
    不再给回环豁免，一律要口令（见 _is_trusted_localhost）。
    ⚠️ 本函数只认环境变量；用命令行 `--forwarded-allow-ips=*` 启动的检测不到 ——
    run_server.py 已改为显式传参并默认 127.0.0.1，从源头堵住该路径。
    """
    return (os.environ.get("FORWARDED_ALLOW_IPS") or "127.0.0.1").strip() == "*"


def _is_trusted_localhost(ip: str) -> bool:
    """能否按"本机"豁免鉴权 = 是回环 **且** uvicorn 未被配成信任任意 XFF。"""
    return _is_localhost(ip) and not _forwarded_allow_ips_all()


def _resolve_ip_allowlist() -> list:
    """取 IP/CIDR 白名单：环境变量优先（多机统一配置），回落配置文件 security.ip_allowlist。"""
    raw = (os.environ.get(IP_ALLOWLIST_ENV) or "").strip()
    if not raw:
        try:
            from app.config import get_config
            v = get_config().get(IP_ALLOWLIST_CONFIG_KEY)
            if isinstance(v, list):
                raw = ",".join(str(x) for x in v)   # 空项由下方 split 后的 if x.strip() 统一过滤
            elif v:
                raw = str(v)
        except Exception:
            raw = ""
    return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]


def _ip_in_allowlist(ip: str) -> bool:
    """来源 IP 是否命中白名单（支持单 IP 与 CIDR，如 192.168.1.0/24、10.0.0.5）。

    解析失败一律按"不命中"处理（fail-closed：写错的条目不放行，绝不因配置错误而全站失守或全站放行）。
    """
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in _resolve_ip_allowlist():
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif ipaddress.ip_address(entry) == addr:
                return True
        except ValueError:
            continue  # 写错的条目跳过（不放行）
    return False


def extract_token(request: Request) -> Optional[str]:
    """从请求头取 token：Authorization: Bearer <token> 优先，其次 X-API-Token。"""
    auth = request.headers.get("Authorization") or ""
    if auth[:7].lower() == "bearer ":
        cand = auth[7:].strip()
        if cand:
            return cand
    return (request.headers.get("X-API-Token") or "").strip() or None


async def verify_token(request: Request) -> None:
    """统一 token 鉴权依赖（FastAPI Depends）。

    口令**校验**失败一律 401 且文案统一（不区分"未配置"与"口令不对"，防探测鉴权状态）；
    仅两类**准入**失败用 403：改口令非本机、白名单在未配置口令时访问。

    判定顺序（北京老陈 2026-09-27 裁定，勿随意调整）：
      0. 未配置口令时 `GET /auth/status` 对所有来源放行（前端据此显示状态）
      1. 设置口令只能本机：`POST /auth/token` 非本机 → 403（放这层而非只放业务层，
         否则远程请求会先被通用 401 拦掉，用户永远看不到"只能本机设置"这条提示）
      2. 白名单只是免口令登录：已配置口令 → 放行；未配置 → 403「请联系管理员设置」
         （此时无口令可免，静默放行等于防护就位前先开全站敞口）
      3. 其余来源一律要口令；未配置口令时 fail-closed

    ⚠️ 白名单内等于无鉴权（可读全部明文密钥），只应放可信网段。
    ⚠️ `auth_routes.set_api_token` 内的本机检查是纵深兜底（拦非 HTTP 调用），非重复；改任一处须同步。
    """
    if not _auth_required():
        return
    _ip = _client_ip(request)
    _local = _is_trusted_localhost(_ip)
    _allow = _ip_in_allowlist(_ip)
    # D14 修复（2026-09-26）：开头只取一次 expected，避免同一请求读到两个 token 的竞态
    expected = _resolve_configured_token()
    _path = request.url.path.rstrip("/")

    # 未配置口令时，状态查询对所有来源放行（前端据此显示"已配置/未配置"）
    if not expected and request.method == "GET" and _path.endswith(AUTH_STATUS_PATH):
        return

    # 裁定①：设口令仅限本机。放鉴权层而非只放业务层，否则远程请求会先被下面的通用 401 拦掉，
    # 用户就永远看不到"只能本机设置"这条准确提示。
    if request.method == "POST" and _path.endswith(AUTH_TOKEN_PATH) and not _local:
        raise HTTPException(
            status_code=403,
            detail="设置或更换访问口令只能在服务端本机进行"
                   "（白名单设备只是免口令登录，不能改口令）",
        )

    if _local:
        return

    # 裁定②：白名单只是免口令登录。未配置口令时无口令可免 → 403 提示找管理员，
    # 放行等于在防护就位前先开全站敞口。
    if _allow:
        if not expected:
            raise HTTPException(
                status_code=403,
                detail="服务端尚未配置访问口令，请联系管理员在服务端本机设置后再访问",
            )
        return

    # 裁定③：其余来源一律要口令。未配置口令时 fail-closed，文案与"口令不对"一致（防探测）。
    if not expected:
        # 2026-09-26 小欧 - 修 D01：原文案明文写出"未配置…请在设置页填写"，既泄露鉴权状态，
        #   又把用户指引到未配置口令时进不去的设置页（死循环）。改：统一文案，引导只进日志。
        from app.logger import logger  # noqa: PLC0415
        logger.warning(
            "[auth] 拒绝请求：服务端尚未配置访问口令（键 %s / 环境变量 %s），来源 path=%s",
            API_TOKEN_CONFIG_KEY, API_TOKEN_ENV, _path,
        )
        raise HTTPException(status_code=401, detail=AUTH_FAIL_MESSAGE)
    provided = extract_token(request)
    # 2026-09-26 小欧 - 修 B03：hmac.compare_digest 对非 ASCII 字符串抛 TypeError，
    #   中文口令会让每个带该口令的请求变 500（前端不触发 401 拦截）。改：统一 encode 再比较。
    if not provided or not hmac.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail=AUTH_FAIL_MESSAGE)
