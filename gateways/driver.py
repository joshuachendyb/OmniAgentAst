# -*- coding: utf-8 -*-
r"""driver.py — Driver 接口与装载器（通用层; 3.5 SPI 的代码化, 1.8 D25）。

编写人: 小欧    创建时间: 2026-11-05 09:10:00
通用层只认本文件定义的名字; 换下游只换 vendor\<名>\driver.py 的实现。
"""
from __future__ import annotations

import importlib
import re
from typing import Protocol


class Driver(Protocol):
    """驱动接口。每个挂钩的规格出处见 9.1.5 的挂钩-出处表。"""

    name: str                      # 驱动名 == config["driver"] == vendor\<名>\（如 "opencode"）
    provider_id: str               # OpenAI owned_by 用的 id（4.2）
    version_re: re.Pattern         # 从 --version stdout 捕版本（6.3.4 第①②关）

    # --- 定位与环境（6.3.3 / 6.3.6 / 8.4） ---
    def cli_candidates(self, config): ...
    #   → [{"path", "level", "probe"}]：5 级候选; PATH 级（4 级）标 probe=False
    def env_overrides(self, tag): ...
    #   → {"XDG_CONFIG_HOME": path, ...}：按子代理实例 tag 隔离; 目录由驱动负责创建

    # --- 进程（7.1.2 / D17 / 8.4 / 8.6） ---
    def spawn_args(self, exe, port): ...
    #   → 子命令列表; 只允许服务型子命令（8.4: 裸 CLI 会挂用户后台服务）
    def credential(self, line): ...
    #   → stdout 一行 → (脱敏后行, 密码或 "")；密码行必须脱敏（8.6）
    def auth(self, password): ...
    #   → httpx auth 元组（opencode 为 Basic ("opencode", pw), 6.3.4 实测）
    def ready(self, port, auth): ...
    #   → 就绪单次检查 bool（7.1.3 硬判定的落点）; 轮询超时由通用层承担

    # --- 会话与报文（7.3 / 6.3.7 / 8.2） ---
    def session_body(self, model, permissions): ...
    def prompt_body(self, text, files): ...
    def path_create(self): ...
    def path_prompt(self, sid): ...
    def path_wait(self, sid): ...          # → (path, {ok, status, set})，阻塞式等待
    def path_messages(self, sid): ...      # → (path, params)：定向查询（7.3）
    def path_interrupt(self, sid): ...
    def path_delete(self, sid): ...
    def path_models(self): ...             # → 模型发现端点（4.2）
    def path_events(self): ...             # → 事件订阅端点（7.4）

    # --- 事件与取数（4.5 / 7.4 / 4.6 / 4.8.2） ---
    def event_session(self, payload): ...
    #   → 该事件的会话 ID（无则 None）；通用层用它过滤并发串流（7.4）
    def event_class(self, payload): ...
    #   → {"kind": "content|reasoning|idle|error|ignore", "text": str, "error": obj}
    def assistant_content(self, message): ...
    def token_counts(self, message): ...
    #   → {"input","written","cached","output","reasoning"} 或 None（4.6 算式入参）
    def finish_reason(self, message): ...  # → "stop" | "length" | ...

    # --- 发现与错误（4.2 / 4.7） ---
    def models_from(self, resp_json): ...
    #   → (OpenAI items, skipped)：方言字段 → 4.2 映射表，缺 id 项计数
    def map_error(self, error): ...
    #   → {"status","type","message","detail","internal_cooldown_ms"}（4.7 判读规则）


_LOADED = {}


def get_driver(config):
    r"""按 config["driver"] 装载 vendor\<名>\driver.py; 全进程共享一枚实例。"""
    name = str(config.get("driver") or "opencode").strip()
    if not re.match(r"^[A-Za-z0-9_-]+$", name):       # 目录穿越天然不可能
        raise RuntimeError("拒绝启动: driver 名含非法字符（9.1.6 preflight）")
    if name not in _LOADED:
        module = importlib.import_module("vendor.%s.driver" % name)
        _LOADED[name] = module.Driver()               # Driver 不给 name → 报错早失败
        if _LOADED[name].name != name:
            raise RuntimeError("拒绝启动: 驱动自报名≠config.driver")
    return _LOADED[name]
