# -*- coding: utf-8 -*-
"""
deps — API 统一鉴权依赖（token）

服务绑 0.0.0.0（多机部署前提），此前 13 个 router 全部裸挂，局域网任意设备可直调任何接口
（读全部明文密钥、改密钥、越权读会话）。本模块提供唯一鉴权点，由 main.py 在 include_router
处一次性挂载（KISS：不逐个改 router 定义）。

设计要点：
  - token 存 security.access_token，支持环境变量覆盖（多机统一配置，不必逐台改 yaml）
  - 支持 Authorization: Bearer 与 X-API-Token 两种头
  - 未配置 token 时拒绝所有受保护请求（fail-closed），显式 OMNIAGENT_REQUIRE_AUTH=0 才放行
  - 失败返回 401 且文案统一，不区分"token 不对"与"未配置"（防探测）

编辑历史:
  2026-09-26 小欧 - 新建；_is_localhost 改用 ipaddress.is_loopback；豁免路径提为命名常量。
  2026-09-26 小欧 - 删应用层 XFF 解析（uvicorn ProxyHeadersMiddleware 已判定代理信任）。
  2026-09-27 小欧 - 按裁定重排判定顺序；新增 _forwarded_allow_ips_all/_is_trusted_localhost（*=信任任意
    XFF 时取消回环豁免，fail-closed）。
  2026-09-27 小欧 - /auth/status 豁免条件由"未配置口令"改为"未带口令"（带口令时仍需验真）；
    新增 current_client_requires_auth。
  2026-09-27 小欧 - 提 SET_TOKEN_LOCAL_ONLY_MESSAGE 消除 403 文案两处重复；
    current_client_requires_auth 增 configured 入参（同源一次读取）；_auth_required 改 lower() 比较；
    新增 warn_startup_checks（未注入 forwarded_allow_ips / 白名单全网通配时告警）。判定逻辑未变。
  2026-09-27 小欧 - 增设口令被拒原因 set_token_blocked_reason（not_local / proxy_untrusted）
    与 SET_TOKEN_BLOCKED_MESSAGES 文案表：FORWARDED_ALLOW_IPS=* 时本机也无法确认身份，
    原文案仍称"只能在服务端本机进行"，与真实原因不符且指引会撞同一 403。
  2026-09-27 小欧 - 白名单解析改调 app/utils/allowlist（normalize/matches），
    与设置页落盘校验共用一套语法规则，两侧不再各写一份。
"""
import hmac
import ipaddress
import os
from typing import Optional

from fastapi import HTTPException, Request

# 白名单语法单一权威（写侧落盘校验与本模块读侧匹配同源）
from app.utils.allowlist import matches as matches_allowlist
from app.utils.allowlist import normalize as normalize_allowlist

# 2026-09-26 - 小欧 - 访问令牌的配置键与环境变量名（集中在此，避免散落各处硬编码字符串）
# 2026-09-27 小欧 - 改名 api_token → access_token：原名与各家 LLM 服务商的密钥混淆
#   （本项目 `ai.*.api_key` / `{PROVIDER}_API_KEY` 遍地都是）。access_token 专指"访问本服务
#   所需的令牌"，看名字即知是鉴权而非模型密钥。配置键与环境变量同步改，不留旧名（禁止 backward）。
ACCESS_TOKEN_CONFIG_KEY = "security.access_token"   # config.yaml 中的键
ACCESS_TOKEN_ENV = "OMNIAGENT_ACCESS_TOKEN"          # 环境变量名（优先于配置文件，便于多机统一配置）
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
# 设口令被拒有两个原因，文案必须分开。FORWARDED_ALLOW_IPS=* 时用户确实在本机，
# 却收到"只能在服务端本机进行"，且登录页指引会再撞同一 403。
SET_TOKEN_LOCAL_ONLY_MESSAGE = (
    "设置或更换访问口令只能在服务端本机进行"
    "（白名单设备只是免口令登录，不能改口令）"
)
SET_TOKEN_PROXY_UNTRUSTED_MESSAGE = (
    "当前 uvicorn 配成信任任意来源的转发头（FORWARDED_ALLOW_IPS=*），"
    "无法确认你是不是本机，故不放开设口令入口（否则任何人都能冒充本机改口令）。"
    "请改为只信任反代所在机器的 IP，或改用环境变量 OMNIAGENT_ACCESS_TOKEN 配置后重启"
)
# 拒绝原因 → 文案。deps 与 auth_routes 共用，防同一文案两处硬编码改一处即漂移。
SET_TOKEN_BLOCKED_MESSAGES = {
    "not_local": SET_TOKEN_LOCAL_ONLY_MESSAGE,
    "proxy_untrusted": SET_TOKEN_PROXY_UNTRUSTED_MESSAGE,
}
# 免口令白名单（IP/CIDR），支持环境变量与配置文件两种来源。
# 2026-09-27 小欧 - 改名 ip_allowlist → access_token_allowlist：原名像通用防火墙白名单，
#   看不出与访问令牌有关。同步改配置键与环境变量。
# ⚠ 白名单内等于无鉴权（可读全部明文密钥），只应放可信网段。
ACCESS_TOKEN_ALLOWLIST_CONFIG_KEY = "security.access_token_allowlist"
ACCESS_TOKEN_ALLOWLIST_ENV = "OMNIAGENT_ACCESS_TOKEN_ALLOWLIST"


def _resolve_configured_token() -> str:
    """取配置中的 token：环境变量优先（多机统一配置），回落配置文件。空字符串表示未配置。"""
    env_val = (os.environ.get(ACCESS_TOKEN_ENV) or "").strip()
    if env_val:
        return env_val
    try:
        from app.config import get_config
        val = get_config().get(ACCESS_TOKEN_CONFIG_KEY)
        return str(val or "").strip()
    except Exception:
        # 配置读取失败一律按"未配置"处理（fail-closed，不因读不到配置就放行）
        return ""


def _auth_required() -> bool:
    """是否启用鉴权。默认启用；仅 OMNIAGENT_REQUIRE_AUTH=0 / false（大小写等价）时关闭。

    无法识别的值按"启用"处理（fail-closed）。
    """
    return (os.environ.get(REQUIRE_AUTH_ENV) or "1").strip().lower() not in ("0", "false")


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


# 2026-09-27 小欧 - 本模块不再自己读 FORWARDED_ALLOW_IPS 环境变量。
#   值由 run_server.py 启动时注入下面这个模块变量（与传给 uvicorn 的是同一份，见 5.2）。
#   原因：应用与 uvicorn 各读一次环境变量可能不一致（命令行启动时应用层读不到、只看到默认值），
#   改为同源注入后不可能分叉，并顺带修掉"命令行传 * 检测不到"的盲区。
#   未被 run_server 启动（如测试直接 import）时为 None → 按 uvicorn 默认 "127.0.0.1" 处理。
_forwarded_allow_ips: Optional[str] = None


def set_forwarded_allow_ips(value: str) -> None:
    """由启动脚本注入 uvicorn 的 forwarded_allow_ips 实参（唯一来源）。

    2026-09-27 小欧。run_server.py 在 uvicorn.run() 前调用一次。
    """
    global _forwarded_allow_ips
    _forwarded_allow_ips = value


def _forwarded_allow_ips_all() -> bool:
    """uvicorn 是否被配成"信任任意来源的 X-Forwarded-For"（值 = `*`）。

    2026-09-27 小欧 - 安全加固。uvicorn 默认 forwarded_allow_ips="127.0.0.1"，此时远程客户端
    伪造 XFF 改不了 request.client.host，回环判定可信。但一旦被配成 `*`（常见于"反代在内网、
    懒得列 IP"的部署），**任何客户端都能把 client.host 伪造成 127.0.0.1** → _is_localhost
    判真回环 → 免口令进，可读全部明文密钥、可改口令。

    此时应用层**无法区分**真回环与伪造（两者 client.host 都是 127.0.0.1），故 fail-closed：
    不再给回环豁免，一律要口令（见 _is_trusted_localhost）。
    """
    return (_forwarded_allow_ips or "127.0.0.1").strip() == "*"


def _is_trusted_localhost(ip: str) -> bool:
    """能否按"本机"豁免鉴权 = 回环 且 uvicorn 未配 FORWARDED_ALLOW_IPS=*。

    FORWARDED_ALLOW_IPS=* 时的两项后果：
      安全侧  回环不再免口令 —— 任何客户端可伪造 client.host 为 127.0.0.1，fail-closed。
      可用性侧 本机也无法设置/更换口令（同判据）→ 首次部署只能改用环境变量
                OMNIAGENT_ACCESS_TOKEN 或配置文件 security.access_token 后重启。
    _forwarded_allow_ips 仅由 run_server.py 注入；换 uvicorn 命令行等方式启动则注入不发生，
    此时无法得知实际是否配了 *，故 warn_startup_checks() 在启动时告警。
    """
    return _is_localhost(ip) and not _forwarded_allow_ips_all()


def warn_startup_checks() -> None:
    """启动自检：两处"配错即失守或死锁"的配置显式告警。只观测，不改判定。

    ① _forwarded_allow_ips 为 None = 未收到 run_server.py 注入，按"非 *"处理会低估风险。
    ② 白名单含 0.0.0.0/0、::/0 时任意来源免鉴权（白名单内可读全部明文密钥）；
       不拒绝（拒绝会改变既有部署行为），仅告警。
    """
    from app.logger import logger  # noqa: PLC0415

    if _forwarded_allow_ips is None:
        logger.warning(
            "[auth] 未收到 forwarded_allow_ips 注入：若 uvicorn 实际以 --forwarded-allow-ips '*' "
            "启动，伪造 X-Forwarded-For 即可冒充本机免口令。请改用 run_server.py 启动。"
        )
    for entry in _resolve_ip_allowlist():
        if entry.strip() in ("0.0.0.0/0", "::/0"):
            logger.warning(
                "[auth] 白名单含全网通配 %s：任意来源将免口令访问（可读全部明文密钥），"
                "请改为具体网段。", entry,
            )


def _resolve_ip_allowlist() -> list:
    """取 IP/CIDR 白名单：环境变量优先（多机统一配置），回落配置文件。归一规则见 allowlist.normalize。"""
    raw = (os.environ.get(ACCESS_TOKEN_ALLOWLIST_ENV) or "").strip()
    if not raw:
        try:
            from app.config import get_config
            raw = get_config().get(ACCESS_TOKEN_ALLOWLIST_CONFIG_KEY)
        except Exception:
            raw = None
    return normalize_allowlist(raw)


def _ip_in_allowlist(ip: str) -> bool:
    """来源 IP 是否命中白名单。规则与设置页落盘校验同源（allowlist 模块），不会各写一套。"""
    return matches_allowlist(ip, _resolve_ip_allowlist())


def set_token_blocked_reason(request: Request) -> Optional[str]:
    """本来源为何不能设置/更换访问口令。None=可以设。

    两个原因必须分开：非本机 vs 无法确认是否本机（FORWARDED_ALLOW_IPS=*）。
    合并成一个判据会让文案说谎，用户照指引操作仍被拒。
    """
    if _is_trusted_localhost(_client_ip(request)):
        return None
    return "proxy_untrusted" if _forwarded_allow_ips_all() else "not_local"


def current_client_requires_auth(request: Request, configured: str) -> bool:
    """本来源本次访问是否需要口令。

    公式须含已设口令判定：白名单在未设口令时同样需要口令（判定链②），否则该来源得 false
    放行进主界面、随即被 403 挡回。configured 由调用方传入而非本函数自取，使同一响应内
    三个字段同源于一次读取（自取会与 access_token_configured 读到不同值）。
    """
    return not (
        _is_trusted_localhost(_client_ip(request))
        or (_ip_in_allowlist(_client_ip(request)) and configured)
    )


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

    判定顺序（2026-09-27 裁定，勿随意调整）：
      0. 未带口令时 `GET /auth/status` 对所有来源放行；带了口令照常往下验真
      1. `POST /auth/token` 非本机 → 403（放鉴权层而非只放业务层，否则远程请求先被通用 401
         拦掉，用户看不到"只能本机设置"这条提示）
      2. 白名单只是免口令登录：已配置 → 放行；未配置 → 403「请联系管理员设置」（无口令可免，
         静默放行等于防护就位前开全站敞口）
      3. 其余来源一律要口令；未配置口令时 fail-closed

    ⚠️ 白名单内等于无鉴权（可读全部明文密钥），只应放可信网段。
    ⚠️ `auth_routes.set_api_token` 的本机检查是纵深兜底（拦非 HTTP 调用），非重复；改任一处须同步。
    """
    if not _auth_required():
        return
    _ip = _client_ip(request)
    _local = _is_trusted_localhost(_ip)
    _allow = _ip_in_allowlist(_ip)
    # 只取一次 expected，避免同一请求读到两个 token 的竞态
    expected = _resolve_configured_token()
    _path = request.url.path.rstrip("/")

    # 豁免条件由"未配置口令"改为"未带口令"：带口令时继续走判定链验真（200/错 401），
    # 不得写成无条件放行。
    if (
        request.method == "GET"
        and _path.endswith(AUTH_STATUS_PATH)
        and not extract_token(request)
    ):
        return

    # 裁定①：设口令仅限可信本机。放鉴权层而非业务层，否则远程请求先被通用 401 拦掉，看不到准确提示。
    if request.method == "POST" and _path.endswith(AUTH_TOKEN_PATH):
        blocked = set_token_blocked_reason(request)
        if blocked:
            raise HTTPException(status_code=403, detail=SET_TOKEN_BLOCKED_MESSAGES[blocked])

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
            ACCESS_TOKEN_CONFIG_KEY, ACCESS_TOKEN_ENV, _path,
        )
        raise HTTPException(status_code=401, detail=AUTH_FAIL_MESSAGE)
    provided = extract_token(request)
    # 2026-09-26 小欧 - 修 B03：hmac.compare_digest 对非 ASCII 字符串抛 TypeError，
    #   中文口令会让每个带该口令的请求变 500（前端不触发 401 拦截）。改：统一 encode 再比较。
    if not provided or not hmac.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail=AUTH_FAIL_MESSAGE)
