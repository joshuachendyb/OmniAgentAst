# -*- coding: utf-8 -*-
r"""vendor\opencode\driver.py — opencode CLI 驱动（方言唯一集中点）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
换第二案 = 新增 vendor\<案>\driver.py, 实现 gateways\driver_api.py 的 DriverApi 钩子并导出 DRIVER_CLASS。

编辑历史:
  2026-11-05 实现 assistant_reasoning: content[] 里 reasoning 型段拼文 -- 小欧
  2026-11-05 实现类更名 OpenCodeDriver 并导出 DRIVER_CLASS; 报文构造改调 bodies.py 公有函数 -- 小欧
  2026-11-05 注释规范化: 压缩到两行内并统一署名日期 -- 小欧
  2026-11-05 400 分流: 仅 context 类归 context-too-long, 其余归 bad-request; released 非数值不再崩 -- 小欧
"""
from __future__ import annotations

import json
import os
import re

import httpx

try:                                  # vendor\opencode\ 为 namespace package — 小欧 2026-11-05
    from . import bodies as oc                   # 兼容器: 同目录直跑时回退顶层导入
except ImportError:
    import bodies as oc               # 打包为插件目录 copy 时两者皆可 — 小欧 2026-11-05

NAME = "opencode"
PROVIDER_ID = oc.PROVIDER_ID          # 单一来源: 报文构造与驱动自报名同此一处
VERSION_RE = re.compile(r"^opencode v?(\d+\.\d+\.\d+)")          # 实测: opencode v2.2.0
PASSWORD_RE = re.compile(r"server password (\S+)")               # 密码出自 stdout — 小欧 2026-11-05
PASSWORD_MASK = "server password ***"                            # 脱敏替身 — 小欧 2026-11-05

# 下游 CLI 是 agent 型程序, 默认 agent 自带工具并会自己跑多轮 ReAct; 网关只要一次纯文本补全。
# 故在隔离 XDG 配置里注册无工具单步 agent, 建会话时钉死使用它。— 小欧 2026-11-05
AGENT_NAME = "opencli-plain"
_AGENT_SPEC = {
    "description": "opencli gateway plain-text agent: no tools",
    "mode": "primary",
    "tools": {"*": False},
    "permission": {"*": "deny"},
}


class OpenCodeDriver:
    name = NAME
    provider_id = PROVIDER_ID
    version_re = VERSION_RE

    # --- 定位与环境（5 级解析 / XDG 隔离） ---

    def cli_candidates(self, config):
        """候选从 config 通用注记里取路径基点（runtime_dir/frozen 由 cli_manager 注入）。— 小欧 2026-11-05"""
        cli = config.get("cli") or {}
        frozen = bool(config.get("frozen"))
        allow_system = bool(cli.get("allow_system", True))
        if frozen and allow_system:
            config["system_probe_note"] = "disabled(packaged)"       # 打包版禁用系统探针 — 小欧 2026-11-05
            allow_system = False
        out = []
        if str(cli.get("executable") or "").strip():                # 1 级: 显式钉死
            out.append({"path": cli["executable"].strip(), "level": 1})
        out.append({"path": os.path.join(str(config.get("runtime_dir")), "runtime",
                                         "opencode-cli.exe"), "level": 2})   # 2 级: 自带优先
        shared = os.path.join(str(config.get("machine_root")), "bin", "opencode-cli.exe")
        out.append({"path": shared, "level": 3})                    # 3 级: 用户级共享
        if allow_system:                                            # 4 级: 仅开发版
            out.append({"path": "opencode-cli", "level": 4, "probe": False})
        return out

    def env_overrides(self, tag):
        """出生前隔离: XDG 四目录按 tag（i0/i1/probe）分目录, 不读用户全局配置。— 小欧 2026-11-05"""
        root = os.path.join(str(config_root()), "xdg")
        paths = {}
        for var, sub in (("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
                         ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state")):
            path = os.path.join(root, sub, tag)
            os.makedirs(path, exist_ok=True)
            paths[var] = path
        self._ensure_agent_config(paths["XDG_CONFIG_HOME"])
        return paths

    def _ensure_agent_config(self, config_home):
        """在隔离配置里注册无工具单步 agent（已存在则覆盖该项, 不动其他键）。— 小欧 2026-11-05"""
        cfg_dir = os.path.join(config_home, "opencode")
        os.makedirs(cfg_dir, exist_ok=True)
        path = os.path.join(cfg_dir, "opencode.json")
        data = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh) or {}
            except Exception:
                data = {}                                  # 坏配置不阻断启动, 重写
        agents = data.get("agent") or {}
        agents[AGENT_NAME] = dict(_AGENT_SPEC)
        data["agent"] = agents
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    # --- 进程（spawn / 密码捕获 / 就绪） ---

    def spawn_args(self, exe, port):
        """只允许 serve 子命令——裸 CLI 会挂用户后台服务。— 小欧 2026-11-05"""
        return ["serve", "--hostname", "127.0.0.1", "--port", str(port)]

    def credential(self, line):
        """stdout 行 → (脱敏行, 密码)。任何含密码的行都脱敏后再落盘。— 小欧 2026-11-05"""
        match = PASSWORD_RE.search(line)
        if not match:
            return line, ""
        return PASSWORD_MASK, match.group(1)

    def auth(self, password):
        return ("opencode", password)               # 用户名固定（实测）— 小欧 2026-11-05

    def ready(self, port, auth):
        """就绪硬判定: /api/model 200 且 data 为 list。— 小欧 2026-11-05"""
        try:
            resp = httpx.get("http://127.0.0.1:%d/api/model" % port, auth=auth,
                             timeout=3, trust_env=False)        # 不走系统代理 — 小欧 2026-11-05
            return resp.status_code == 200 and isinstance(resp.json().get("data"), list)
        except Exception:
            return False

    # --- 会话与报文（报文构造委托 vendor 纯函数） ---

    def session_body(self, model, permissions):
        return oc.session_body(model, title="ask-%s" % model,
                               agent=AGENT_NAME, permissions=permissions)

    def prompt_body(self, text, files):
        return oc.prompt_body(text, files=files or None)

    def path_create(self):
        return "/api/session"

    def path_prompt(self, sid):
        return "/api/session/%s/prompt" % sid

    def path_wait(self, sid):
        # 易错点: 阻塞式等待, 200/204 即执行结束, 无需轮询 — 小欧 2026-11-05
        return "/api/experimental/session/%s/wait" % sid, {200, 204}

    def path_messages(self, sid):
        # 定向查询: type=assistant + desc + limit=1, 只取末条, 报文更省 — 小欧 2026-11-05
        return "/api/session/%s/message" % sid, \
               {"type": "assistant", "order": "desc", "limit": 1}

    def path_interrupt(self, sid):
        return "/api/session/%s/interrupt" % sid

    def path_delete(self, sid):
        return "/api/session/%s" % sid

    def path_models(self):
        return "/api/model"

    def path_events(self):
        return "/api/event"

    # --- 事件与取数 ---

    def event_session(self, payload):
        data = payload.get("data") or {}
        return data.get("sessionID") or None        # 并发过滤键 — 小欧 2026-11-05

    def event_class(self, payload):
        """判别按内容形状; 事件名以实测 opencode v2.2.0 为准。
        增量在 session.text.delta, 收尾全文在 session.text.ended, 终止为 execution.*。— 小欧 2026-11-05"""
        data = payload.get("data") or {}
        kind = str(payload.get("type") or "")
        if data.get("error"):
            return {"kind": "error", "text": "", "error": data["error"]}
        if kind == "session.execution.failed":
            return {"kind": "error", "text": "",
                    "error": data or {"message": "下游执行失败"}}
        if kind in ("session.execution.succeeded", "session.idle", "idle"):
            return {"kind": "idle", "text": "", "error": None}
        if kind == "session.text.delta":
            return {"kind": "content", "text": data.get("delta") or "",
                    "ordinal": data.get("ordinal"), "error": None}
        if kind == "session.text.ended":
            # 收尾事件携带全文, 与 delta 流重复: 归一为 "final" 由通用层按 ordinal 去重。
            # 消息无 delta 时仍可收字。— 小欧 2026-11-05
            return {"kind": "final", "text": data.get("text") or "",
                    "ordinal": data.get("ordinal"), "error": None}
        if kind == "session.text.started":
            return {"kind": "ignore", "text": "", "error": None}
        if data.get("reasoning") is not None or kind.startswith("session.reasoning"):
            return {"kind": "reasoning",
                    "text": data.get("reasoning") or data.get("delta") or data.get("text") or "",
                    "error": None}
        if data.get("text"):
            return {"kind": "content", "text": data.get("text") or "", "error": None}
        return {"kind": "ignore", "text": "", "error": None}

    def assistant_content(self, message):
        return "\n".join((part.get("text") or "") for part in
                         (message.get("content") or []) if part.get("type") == "text")

    def assistant_reasoning(self, message):
        """思考段拼文（content[] 里 reasoning 型段; 下游混在文字段时用 reasoning 字段兜底）— 小欧 2026-11-05"""
        parts = []
        for part in (message.get("content") or []):
            ptype = str(part.get("type") or "")
            if ptype == "reasoning" or part.get("reasoning"):
                parts.append(part.get("reasoning") or part.get("text") or "")
        return "\n".join(s for s in parts if s)

    def token_counts(self, message):
        tokens = message.get("tokens")
        if not isinstance(tokens, dict) \
                or (tokens.get("input") is None and tokens.get("output") is None):
            return None                              # 缺计量 → None, 绝不填 0 — 小欧 2026-11-05
        cache = tokens.get("cache") or {}
        return {"input": int(tokens.get("input") or 0),
                "written": int(cache.get("write") or 0),
                "cached": int(cache.get("read") or 0),
                "output": int(tokens.get("output") or 0),
                "reasoning": int(tokens.get("reasoning") or 0)}

    def finish_reason(self, message):
        finish = str(message.get("finish") or message.get("rawFinish") or "").strip()
        return "length" if finish == "length" else "stop"       # 未知值按 stop 兜底 — 小欧 2026-11-05

    # --- 发现与错误 ---

    def models_from(self, resp_json):
        items, skipped = [], 0
        for item in (resp_json or {}).get("data") or []:
            mid = item.get("id") or item.get("modelID")          # id 回退 modelID — 小欧 2026-11-05
            if not mid:
                skipped += 1                                     # 缺 id 必须自己数出来 — 小欧 2026-11-05
                continue
            limit = item.get("limit") or {}
            caps = item.get("capabilities") or {}
            released = (item.get("time") or {}).get("released") or 0
            items.append({
                "id": mid,
                "object": "model",
                "created": int(released // 1000) if isinstance(released, (int, float)) and released else 0,
                "owned_by": self.provider_id,
                "name": item.get("name") or mid,
                "context_length": limit.get("context"),
                "max_output_length": limit.get("output"),
                "input_modalities": caps.get("input") or [],
                "output_modalities": caps.get("output") or [],
                "pricing": {"prompt": "0", "completion": "0"},
                "free": True,                       # 本网关只暴露免费层 — 小欧 2026-11-05
            })
        return items, skipped

    def map_error(self, error):
        """下游错误对象 → 统一分派 dict; 头值冷却只进 internal_cooldown_ms, 不写响应头。
        通用层只认返回的 dict 形状。— 小欧 2026-11-05"""
        error = error or {}
        etype = str(error.get("type") or "")
        msg = str(error.get("message") or "")
        status = int(error.get("status") or 0)
        cooldown = int(error.get("retryAfterMs") or 0)
        base = {"detail": (msg or "下游无错误详情")[:500],
                "internal_cooldown_ms": cooldown}

        if "free-limit" in etype or "FreeUsageLimit" in msg or "Free usage limit" in msg:
            return dict(base, status=429, type="free-limit",
                        message="免费额度受限（可能地区或频率），请稍后再试或更换出口")
        if status == 403 or "RegionError" in msg:
            return dict(base, status=403, type="region",
                        message="该地区不可用，请更换出口")
        if "no-route" in etype or status == 404:
            return dict(base, status=404, type="model-not-found",
                        message="模型不存在或未开放")
        if "context" in etype.lower() or "context" in msg.lower():
            return dict(base, status=400, type="context-too-long",
                        message="上下文过长")
        if status == 400:
            return dict(base, status=400, type="bad-request",
                        message="下游拒绝了该请求（参数或内容不被接受）")
        if status == 401 or "auth" in etype:
            # 下游 Basic 鉴权失败是网关内部问题, 包 502 而非透传 401 — 小欧 2026-11-05
            return dict(base, status=502, type="server",
                        message="网关内部错误（下游鉴权失败），请查看 logs 下 cli-out-i*.log")
        if "timeout" in etype or status == 504:
            return dict(base, status=504, type="timeout", message="模型响应超时")
        if "network" in etype or status in (502, 503):
            return dict(base, status=502, type="network", message="下游连接中断")
        return dict(base, status=502, type="server",
                    message="下游异常（debug 见 detail）")


# 装载器约定: 每个 vendor\<名>\driver.py 必须导出 DRIVER_CLASS — 小欧 2026-11-05
DRIVER_CLASS = OpenCodeDriver


def config_root():
    """机器级根目录（与通用层 machine_root 同值; 驱动不 import 通用层, 故就地实现）。— 小欧 2026-11-05"""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    return os.path.join(base, "opencli-gateway")
