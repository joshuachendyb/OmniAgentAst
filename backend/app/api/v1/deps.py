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
      连带安全增强: 原实现把字面量 "localhost" 当回环放行，而 _client_ip 在 TRUST_PROXY_HEADERS=1
      时会采信 X-Forwarded-For —— 伪造 `X-Forwarded-For: localhost` 即可免口令进；
      新实现只认合法 IP 字面量，该伪造路径消失（功能不退化: 真实回环 127.0.0.0/8 与 ::1 仍全放行，
      且新增支持 ::ffff:127.0.0.1 等 IPv4-mapped 变体，原手写版本反而漏判）；
    ③首次设置豁免的两个端点路径提为 AUTH_TOKEN_PATH/AUTH_STATUS_PATH 常量 ——
      原为 verify_token 内联的 (…"/api/v1/auth/token", …"/api/v1/auth/status") 字面量元组，
      字面量与 router 定义（auth_routes 用 "/auth/token"，前缀由 main.py 挂载时给）分处两地，
      对不上时排查极难（豁免失效=死锁）。提为命名常量后，与本模块说明性 docstring 的
      AUTH_EXEMPT_PATHS 一眼可读。说明: auth_routes 侧**本就没有**同一字面量（它只写 "/auth/token"），
      故此处并非"消除重复实现"，而是把魔法字面量换成可追溯的命名常量；auth_routes 不反向引用
      本常量（其 router 路径不含 /api/v1 前缀，引用反而要再拼一次前缀，徒增绕弯=KISS-DIRECT 所忌）。
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
# 2026-09-26 - 小欧 - [72]第九章（DRY）: 首次设置豁免的两个端点路径在此定一份。
#   原先 deps.verify_token 内联字面量、auth_routes 又各写一次 router 前缀，同一事实两处硬编码，
#   改路径必漏一处（漏一处=死锁：没口令就永远设不了口令）。故提为常量单一来源。
AUTH_TOKEN_PATH = "/api/v1/auth/token"
AUTH_STATUS_PATH = "/api/v1/auth/status"
AUTH_EXEMPT_PATHS = (AUTH_TOKEN_PATH, AUTH_STATUS_PATH)
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
    """取来源 IP：优先 request.client.host；反向代理场景回落 X-Forwarded-For 最左段。

    [72]第九章 - 小欧 - 2026-09-26（北京老陈要求"本机和白名单豁免"）
    注意: X-Forwarded-For **可被客户端伪造**（非受信代理场景），故仅当显式设置
    TRUST_PROXY_HEADERS=1 时才采信 —— 否则攻击者伪造该头即可冒充白名单 IP 绕过鉴权。
    默认不采信（安全侧优先），仅信任 TCP 层来源地址。
    """
    try:
        ip = request.client.host if request.client else ""
    except Exception:
        ip = ""
    if (os.environ.get("TRUST_PROXY_HEADERS") or "").strip() in ("1", "true", "True"):
        xff = (request.headers.get("X-Forwarded-For") or "").strip()
        if xff:
            ip = xff.split(",")[0].strip()
    return ip


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

    **首次设置豁免**（2026-09-26 小欧 [72]第九章补）：未配置口令时，
    `POST /api/v1/auth/token` 与 `GET /api/v1/auth/status` 必须放行 ——
    否则死锁（没口令就永远设不了口令）。已配置口令后这两个端点**不再豁免**
    （`POST /auth/token` 需当前有效 token 才能改，防局域网内抢占设置权）。

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
    # 首次设置豁免：仅当"服务端尚未配置口令"时才对 auth 两个端点放行
    if not _resolve_configured_token() and request.url.path.rstrip("/").endswith(
        AUTH_EXEMPT_PATHS
    ):
        return
    expected = _resolve_configured_token()
    if not expected:
        # fail-closed：未配置 token 时拒绝一切受保护请求 —— 绝不放行
        raise HTTPException(
            status_code=401,
            detail=(
                f"未配置访问口令（{API_TOKEN_CONFIG_KEY} 或环境变量 {API_TOKEN_ENV}），"
                f"已拒绝请求。请在设置页填写访问口令或设置该环境变量后重启后端"
            ),
        )
    provided = extract_token(request)
    # 常量时间比较，避免计时侧信道
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="访问口令无效或缺失")
