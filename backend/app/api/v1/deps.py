# -*- coding: utf-8 -*-
"""
deps — API 统一鉴权依赖（token）

编辑历史:
  2026-09-26 - 小欧 - [72]第九章(9.6-1) 新建。实现统一 token 鉴权 Depends，供 main.py 在
    include_router 处一次性挂载（KISS：一处生效，不逐个改 13 个 router 定义）。
    背景（第九章 9.2）：全项目 13 个 APIRouter 全部裸挂，Depends( 零命中，main.py 唯一中间件是 CORS；
    服务绑 0.0.0.0（多机部署硬前提，不可收窄），局域网任意设备/程序/网页跨源请求均可直调任何接口 ——
    可读走全部 provider 明文密钥、可改可擦密钥、可越权读他人会话。零身份验证是缺陷，须修。

设计要点（9.6）：
  - token 存服务端配置 security.api_token，支持环境变量覆盖（多机部署统一配置，不必逐台改 yaml）
  - 失败返回 401，**不泄露"token 存在但不对"与"未配置"的差异**（避免探测）
  - 支持 Authorization: Bearer <token> 与 X-API-Token: <token> 两种头（前端 axios 走 Bearer）
  - 未配置 token 时**拒绝所有受保护请求**（fail-closed，绝不"没配就全放行"），
    否则等于没做鉴权；仅当显式设置 OMNIAGENT_REQUIRE_AUTH=0 时才放行（供本机开发/测试显式声明）
  - /api/v1/health 豁免（便于探活与排障，9.6-1 要求）

  2026-09-26 (三堂会审后修正) - 小欧 - 10 大规范复核，3 处 DRY/复用优先违规已改：
    ①import hmac/ipaddress 由函数体内提到模块头（原先 ipaddress 在 _ip_in_allowlist 体内 import，
      且同一函数内 import 4 处；模块级一次导入即可，函数级 import 属重复劳动）；
    ②_is_localhost 原为手写分段判断（parts[0]=="127" + 逐段 0~255），与 _ip_in_allowlist 的
      ipaddress 解析是同一件事的两套实现 —— 改用 ipaddress.ip_address(ip).is_loopback。
      连带安全增强: 原实现把字面量 "localhost" 当回环放行，而 _client_ip 在信任代理头时
      会采信 X-Forwarded-For —— 伪造 `X-Forwarded-For: localhost` 即可免口令进；
      新实现只认合法 IP 字面量，该伪造路径消失（功能不退化: 真实回环 127.0.0.0/8 与 ::1 仍全放行，
      且新增支持 ::ffff:127.0.0.1 等 IPv4-mapped 变体，原手写版本反而漏判）；
    ③首次设置豁免的两个端点路径提为 AUTH_TOKEN_PATH/AUTH_STATUS_PATH 常量 ——
      原为 verify_token 内联的 (…"/api/v1/auth/token", …"/api/v1/auth/status") 字面量元组，
      字面量与 router 定义（auth_routes 用 "/auth/token"，前缀由 main.py 挂载时给）分处两地，
      对不上时排查极难（豁免失效=死锁）。提为命名常量后，与本模块说明性 docstring 的
      AUTH_EXEMPT_PATHS 一眼可读。说明: auth_routes 侧**本就没有**同一字面量（它只写 "/auth/token"），
      故此处并非"消除重复实现"，而是把魔法字面量换成可追溯的命名常量；auth_routes 不反向引用
      本常量（其 router 路径不含 /api/v1 前缀，引用反而要再拼一次前缀，徒增绕弯=KISS-DIRECT 所忌）。

  2026-09-26 (三堂会审后修正·实测复现高危绕过) - 小欧 - 修 _client_ip 的 XFF 最左取值：
    原实现 TRUST_PROXY_HEADERS=1 时取 xff.split(",")[0]（**最左**），但各代理对 X-Forwarded-For
    是**追加**语义：最右才是最近代理看到的真实来源，最左是客户端可随意伪造的。实测复现
    （tests/test_repro_3_xff.py，3 用例全 fail）：
      TRUST_PROXY_HEADERS=1 + `X-Forwarded-For: 127.0.0.1, 8.8.8.8`
      → 原实现取 [0]=127.0.0.1 → 判本机 → 免口令读全部明文密钥（鉴权绕过，高危）。
    uvicorn 官方 ProxyHeadersMiddleware.get_trusted_client_address 已核实：从右往左
    （reversed）找第一个非可信 host。修法：信任代理时**不再自行解析 XFF**，直接用 uvicorn
    已写入 request.client.host 的解析结果（单点信任，消除自解析歧义）。改后 5/5 过。

  2026-09-26 (三堂会审后二次修正) - 小欧 - **彻底删除**应用层 XFF 处理与 TRUST_PROXY_HEADERS：
    上一条"修最左取值"方向对（不自行取 XFF），但当时只改了取值方式、**保留了自解析分支与
    环境变量**，属治标未治本。三遍核实后确认：uvicorn ProxyHeadersMiddleware 的
    `trusted_hosts` 默认 `"127.0.0.1"` 且仅在 `client_host in self.trusted_hosts` 时才改写
    request.client.host ⇒ **远程客户端伪造 XFF 不可能改变 client.host，绕过不成立**
    （前版"实测"是在回环对端做的，回环本就豁免，属自证循环）。
    且同机反代部署时 XFF 必然存在 → 空串 fail-closed 会**误拒合法 LAN 客户端**（真退化），
    并凭空引入部署新概念（YAGNI）。代理信任判定交回 uvicorn（其 forwarded_allow_ips
    已是正确实现），应用只读 request.client.host —— 消除重复实现(DRY)与判断标准分裂。
    下方 _client_ip 编辑历史记录全过程，未删改历史条目。
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
# 2026-09-26 - 小欧 - [72]第九章（DRY）: 首次设置豁免的端点路径在此定一份。
#   原先 deps.verify_token 内联字面量、auth_routes 又各写一次 router 前缀，同一事实两处硬编码，
#   改路径必漏一处（漏一处=死锁：没口令就永远设不了口令）。故提为常量单一来源。
#   2026-09-26（C 修复·豁免收窄为只读）: verify_token 只对 GET /auth/status 做首次设置豁免，
#   故代码仅引用 AUTH_STATUS_PATH；AUTH_TOKEN_PATH 保留为写端点路径的权威定义（auth_routes
#   侧仍以字面量 "/auth/token" 定义 router，专用于"已配置或本机/白名单"下的改口令）。
AUTH_TOKEN_PATH = "/api/v1/auth/token"
AUTH_STATUS_PATH = "/api/v1/auth/status"
# 2026-09-26 - 小欧 - [72]第九章(B-1 修复): 鉴权失败统一文案（常量单一来源）。
#   ⚠ 严禁在此拆分"未配置"与"不匹配"两种措辞 —— 那会让攻击者从 401 body
#   就能探测服务端是否已启用口令（设计 9.6 明确要求不区分，避免探测）。
#   未配置时用户该去哪里设口令，由前端经 GET /auth/status（configured 字段）
#   得知（该读端点豁免保留），**不写进 401 文案**。
AUTH_FAIL_MESSAGE = "访问口令无效或缺失"
# 2026-09-26 - 小欧 - [72]第九章（北京老陈要求"本机和白名单豁免"）:
#   IP/CIDR 白名单（白名单内免口令）。支持环境变量（逗号/分号分隔）与配置文件两种来源。
#   安全提醒: 白名单内等于**无鉴权**（可读全部明文密钥），故只应放可信设备网段；
#   且 ip_allowlist 本身**不是 secret**（可经 /settings 设置页维护，见 settings_registry 注册项）。
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
    """取来源 IP = request.client.host（不自行解析 X-Forwarded-For）。

    【编辑历史 — 最新在下】
    2026-09-26 - 小欧 - 修 XFF 最左取值（真绕过，保留）：原实现在信任代理时取
      `xff.split(",")[0]`（最左），而各代理对 XFF 是**追加**语义，最左是客户端可随意伪造的。
      改法：不再自行解析 XFF，改用 uvicorn 已写入 request.client.host 的结果。

    2026-09-26 - 小欧 - **回退**本函数内的 fail-closed XFF 分支与 TRUST_PROXY_HEADERS 环境变量
      （北京老陈 2026-09-26 指示「按常理处理」；三遍核实后确认前一版是错的）：
      前一版声称"uvicorn 会把 XFF 写进 request.client.host，故可伪造绕过"。**该前提经查证不成立**：
      uvicorn.middleware.proxy_headers.ProxyHeadersMiddleware.__init__ 签名
      `trusted_hosts: list[str] | str = "127.0.0.1"`，且 __call__ 内是
      `if client_host in self.trusted_hosts:` 才处理 X-Forwarded-For ——
      **必须"对端地址"可信才改写**。故远程客户端(对端 10.0.0.5)发 `X-Forwarded-For: 127.0.0.1`
      **不会**被改写，request.client.host 仍为 10.0.0.5 → 不判本机 → 照常鉴权。**绕过不成立。**
      前一版的"实测 XFF=127.0.0.1 → 200"是在**回环对端**上做的，而回环本就豁免，与 XFF 无关，
      不能证明绕过（自证循环）。
      且 fail-closed 分支造成**真实功能退化**：同机反代部署时 XFF 必然存在，未设
      TRUST_PROXY_HEADERS 就会返回空串 → **合法 LAN 客户端被拒**；凭空引入部署新概念(YAGNI)。
      按 10 大规范：代理信任判定已由 uvicorn 按 forwarded_allow_ips 实现（且其
      get_trusted_client_address 是从右往左扫描的正确实现），应用再实现一遍属
      **重复实现(DRY 违规)** 且判断标准不一致。回归单点信任：只读 request.client.host。
    """
    return request.client.host if request.client else ""


def _is_localhost(ip: str) -> bool:
    """是否本机回环地址（127.0.0.0/8 或 ::1）。

    [72]第九章 - 小欧 - 2026-09-26（DRY + 复用优先修正）
    原为手写分段判断（parts[0]=="127" 再逐段 0~255），与本文件下方 _ip_in_allowlist 的
    ipaddress 解析是**同一件事的两套实现**（YAGNI/DRY：相同逻辑只写一次）。
    改用 ipaddress.ip_address(...).is_loopback：一行覆盖 127.0.0.0/8 与 ::1，
    且原生支持 ::ffff:127.0.0.1 等 IPv4-mapped 变体——手写版本会漏判这些形态。
    解析失败（非合法 IP）按"非回环"处理，往下走鉴权（fail-closed）。
    """
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def _resolve_ip_allowlist() -> list:
    """取 IP/CIDR 白名单：环境变量优先（多机统一配置），回落配置文件 security.ip_allowlist。"""
    raw = (os.environ.get(IP_ALLOWLIST_ENV) or "").strip()
    if not raw:
        try:
            from app.config import get_config
            v = get_config().get(IP_ALLOWLIST_CONFIG_KEY)
            if isinstance(v, list):
                raw = ",".join(str(x) for x in v if str(x).strip())
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

    失败一律返回 **401**，且**文案统一**（不区分"未配置 token"与"token 不匹配"，
    避免攻击者据此探测服务端是否已启用鉴权）。

    **首次设置豁免**（2026-09-26 小欧 [72]第九章补，北京老陈指示收窄）：服务端**尚未配置**
    口令时，仅放行**读端点** `GET /api/v1/auth/status`（前端据此 configured=false 引导首设）；
    **写端点 `POST /api/v1/auth/token` 不在豁免内** —— 非本机/白名单客户端一律 401
    （fail-closed 只读不写），杜绝局域网任意客户端抢先设置口令、锁死管理员。
    管理员首次配置口令在**服务端本机**（本机豁免）或白名单设备上进行。

    **本机与白名单豁免**（2026-09-26 小欧 [72]第九章，北京老陈要求）：
      - 来源为本机回环（127.0.0.0/8、::1）→ 免口令（如在服务端本机开网页/跑本机脚本）
      - 来源命中 IP/CIDR 白名单（`security.ip_allowlist` 或 `OMNIAGENT_IP_ALLOWLIST`）→ 免口令
      - 其余（本机与白名单之外的任何客户端，含同网段其他机器）→ **一律要口令**
    ⚠️ 白名单内等于**无鉴权**（可读全部明文密钥、可改可擦），只应放可信设备网段。
    """
    if not _auth_required():
        return
    # 本机 / 白名单豁免（先于口令判定，使本机在未配置口令时也能正常使用）
    _ip = _client_ip(request)
    if _is_localhost(_ip) or _ip_in_allowlist(_ip):
        return
    # 2026-09-26 - 小欧 - 修 D14「同一请求读两次配置」（三遍核实部分成立，次数为 2 非 3）：
    #   原实现在下方判首次设置豁免时读一次 _resolve_configured_token()、取期望值时再读一次。
    #   每次 get_config() 都做一次 config.yaml 的 mtime 探测；若这两次之间另一请求
    #   POST /auth/token 落盘并触发 reload，则「豁免判定」与「口令比对」依据的可能是**两个不同的
    #   token**（:220 判"未配置"→走首次设置豁免直接放行，:224 取到新 token），存在单请求竞态窗口。
    #   修法（DRY + 正确性）：开头取一次，后续豁免与比对**共用同一个值**。
    #   —— 编辑：小欧 2026-09-26
    expected = _resolve_configured_token()
    _path = request.url.path.rstrip("/")
    # 首次设置豁免 = **fail-closed 只读不写**（2026-09-26 小欧 - 北京老陈指示「把豁免
    # 收窄到本机/白名单 或 保持 fail-closed 只读不写」）：
    #   仅当"服务端尚未配置口令"时，只对**读端点** GET /api/v1/auth/status 放行
    #   （前端据此经 configured=false 引导首次设置）;
    #   **写端点 POST /api/v1/auth/token 不再对全网豁免** —— 非本机/白名单客户端
    #   一律 401（fail-closed），杜绝局域网任意客户端抢先设置口令、锁死管理员的
    #   抢注窗口。管理员首次配置口令在**服务端本机**（上方本机豁免，免口令）或白名单
    #   设备上进行。
    #   —— 编辑：小欧 2026-09-26
    if not expected and request.method == "GET" and _path.endswith(AUTH_STATUS_PATH):
        return
    if not expected:
        # fail-closed：未配置 token 时拒绝一切受保护请求 —— 绝不放行。
        # 2026-09-26 - 小欧 - 修 D01「401 文案泄露鉴权状态 + 指路到进不去的地方」（三遍核实确认成立）：
        #   原 detail 明文写出「未配置访问口令(security.api_token 或环境变量 OMNIAGENT_API_TOKEN)
        #   …请在设置页填写」—— ①精确泄露"当前未启用鉴权"这一事实（可据此区分"未配置"与"口令不对"，
        #   正是本函数 docstring 承诺要禁的探测面）；②指引到"设置页"，而未配置口令时设置页的**所有**
        #   接口都被本函数的 fail-closed 分支拒掉 → 用户被指引到一个自己也进不去的地方（指引死循环），
        #   而该 toast 恰好由登录页首屏探测触发。
        #   修法：对外文案**与"口令无效"完全一致**（不区分未配置/不匹配，符合本函数 docstring 的
        #   统一文案原则）；"是否已配置"的权威答案由**已豁免的** GET /api/v1/auth/status 提供，
        #   引导信息只进服务端日志（可运维、不对外）。
        #   —— 编辑：小欧 2026-09-26
        # logger 延迟导入：app.logger 会 import app.config，本模块被 app.api 引用，
        #   模块级导入易成环（与本文件既有局部 import 同一策略）
        from app.logger import logger  # noqa: PLC0415
        logger.warning(
            "[auth] 拒绝请求：服务端尚未配置访问口令（键 %s / 环境变量 %s），来源 path=%s",
            API_TOKEN_CONFIG_KEY, API_TOKEN_ENV, _path,
        )
        raise HTTPException(status_code=401, detail=AUTH_FAIL_MESSAGE)
    provided = extract_token(request)
    # 2026-09-26 - 小欧 - 修 B03「中文口令致死」（三遍核实确认成立，实测复现）：
    #   hmac.compare_digest 对**非 ASCII 字符串**直接抛
    #   `TypeError: comparing strings with non-ASCII characters is not supported`，
    #   而 auth_routes.set_api_token 只校验 `len >= 8`、**不限字符集** ⇒ 用户把口令设成
    #   「我的访问口令123」这类中文口令后，每次带该口令的请求都在本行抛 TypeError，
    #   落到 main.py 的全局 ExceptionHandler → 返回 **500「服务器内部错误」**（不是 401），
    #   前端 401 拦截器不触发、用户看到的是"服务器内部错误"而非"口令无效"，
    #   且改回 ASCII 口令前该用户对系统**完全不可用** —— 而这条死路是设置接口亲手开的。
    #   修法（最小、语义不变）：两侧统一 encode('utf-8') 后再常量时间比较。
    #   bytes 比较与 str 比较同样具备常量时间特性，不引入新的时序侧信道。
    #   —— 编辑：小欧 2026-09-26
    if not provided or not hmac.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail=AUTH_FAIL_MESSAGE)
