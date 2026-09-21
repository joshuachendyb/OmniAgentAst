# -*- coding: utf-8 -*-
"""
settings_registry — 设置页唯一 Schema 源（3.2 铁律1）
key/类型/默认值/值域/存储/生效/来源规则只定一次；key 全局唯一，加载自检重复直接拒启。

编辑历史:
  2026-09-20 - 小沈 - 新建：v4.19 Phase 2 从文档54 9.1.1 逐字落盘
  2026-09-21 - 小欧 - 安全组补 2 项 HITL 参数（auto_confirm_delay, hitl_timeout）+ 新增沙箱组 8 项 + GROUP_ORDER 加 sandbox + app.language 从通用移到外观（UI语言属外观属性，与主题/字号同类）+ 系统参数5项（debug/max_context_tokens/max_history_length/max_rounds/max_steps）从系统组移到通用组 + ai.model_ref 标签改为"当前系统全局使用模型"对齐UI
  2026-09-21 - 小欧 - 删除无意义白/黑名单4项（whitelistEnabled/commandWhitelist/blacklistEnabled/commandBlacklist）：全库无消费方、仅透传保存不生效（北京老陈裁定删除；命令安全由 path_safe_check/tools/security 代码内实现，路径校验才是关键）
  2026-09-21 - 小欧 - v4.20 死配置全清+键名按域收敛（北京老陈裁定）:
    ①删除死配置10项: app.max_context_tokens/app.max_history_length/security.strict_mode/security.contentFilterEnabled/
      security.contentFilterLevel/security.maxFileSize/chat.temperature/chat.top_p/chat.max_tokens/chat.auto_title/
      chat.history_limit/chat.stream(实为12项, 其中chat组6项整体删除) + appearance.density(无消费方)
    ②键名按域收敛: app.project_root→workspace.project_root/app.allowed_dirs→workspace.allowed_dirs/
      app.max_rounds→agent.max_rounds/app.max_steps→agent.max_steps/app.debug→logging.debug
    ③保留: app.language/app.theme(外观域待二期深色) + appearance.fontSize(设置页预览有消费)
"""
from typing import Any, Dict, List, Optional


def _item(key: str, type_: str, label: str, default: Any = None,
          options: Optional[List[Any]] = None, range_: Optional[List[float]] = None,
          step: Optional[float] = None, restart: bool = False, secret: bool = False,
          readonly: bool = False, notice: str = "",
          env_key: Optional[str] = None) -> Dict[str, Any]:
    """单项构造：storage 统一 YAML（4.0/v3.0 单存储），env_key 指定环境变量名时来源判定看 os.environ 是否设了该键。"""
    return {"key": key, "type": type_, "label": label, "default": default,
            "options": options, "range": range_, "step": step, "storage": "YAML",
            "restart": restart, "secret": secret, "readonly": readonly, "notice": notice,
            "env_key": env_key}


GROUPS: Dict[str, Dict[str, Any]] = {
    # 4.1 通用（general，5 项）
    "general": {"label": "通用", "items": [
        _item("workspace.project_root", "text", "项目根目录", "E:\\test_dir"),
        _item("workspace.allowed_dirs", "textarea", "授权目录", "",
              notice="项目根之外额外授权访问的工作目录，多个用换行分隔"),
        _item("logging.debug", "bool", "调试模式", True, restart=True),
        _item("agent.max_rounds", "int", "最大轮数", 100),
        _item("agent.max_steps", "int", "最大步数", 10000, range_=[1, 10000]),
    ]},
    # 4.2 模型（model，结构化语义；CRUD 由 model_service 承接，见 9.1.3）
    "model": {"label": "模型", "items": [
        _item("ai.model_ref", "model_ref", "当前系统全局使用模型", None,
              notice="与后端 DTO 同形的 {provider, model} 结构；env 接管时整行只读",
              env_key="AI_PROVIDER"),
    ]},
    # 4.3 安全（security，4 项，YAML，即时；命令安全由 path_safe_check/tools/security 代码内实现）
    "security": {"label": "安全", "items": [
        _item("security.enabled", "bool", "安全开关", False),
        _item("security.confirmDangerousOps", "bool", "危险操作确认", True,
              notice="保存二次确认 Modal（UX 层）；后端安全门禁独立生效"),
        _item("security.auto_confirm_delay", "int", "自动确认延迟(秒)", 10,
              notice="HITL 弹窗自动确认倒计时"),
        _item("security.hitl_timeout", "int", "人工确认超时(秒)", 120,
              notice="HITL 弹窗等待人工确认的最大时间"),
    ]},
    # 4.4 沙箱（sandbox，8 项，运行时参数）
    "sandbox": {"label": "沙箱", "items": [
        _item("sandbox.enabled", "bool", "沙箱开关", True, restart=True),
        _item("sandbox.backend", "select", "沙箱后端", "job_object",
              options=["job_object"], restart=True),
        _item("sandbox.max_concurrent_sandboxes", "int", "最大并发沙箱数", 3),
        _item("sandbox.max_workspace_mb", "int", "工作区上限(MB)", 500),
        _item("sandbox.max_shadow_mb", "int", "影子区上限(MB)", 100),
        _item("sandbox.process_memory_limit_mb", "int", "进程内存上限(MB)", 2048),
        _item("sandbox.default_timeout_sec", "int", "默认超时(秒)", 60),
        _item("sandbox.max_timeout_sec", "int", "最大超时(秒)", 300),
    ]},
    # 4.5 系统（system，5 项：3 运维日志 + 2 关于只读）
    "system": {"label": "系统", "items": [
        _item("logging.level", "select", "日志级别", "INFO",
              options=["DEBUG", "INFO", "WARNING", "ERROR"], restart=True),
        _item("logging.max_file_size", "int", "日志文件上限(字节)", 10485760, restart=True),
        _item("logging.backup_count", "int", "日志备份数", 5, restart=True),
        _item("config_path", "readonly", "配置文件路径", None, readonly=True),
        _item("version", "readonly", "当前版本", None, readonly=True),
    ]},
    # 4.6 外观（theme 只读，字号/语言 YAML 即时 + 本地预应用）
    "appearance": {"label": "外观", "items": [
        _item("app.language", "select", "系统语言", "zh-CN",
              options=["zh-CN", "en-US"], restart=True),
        _item("app.theme", "readonly", "主题", "light", readonly=True,
              notice="当前固定浅色；深色二期（需全站 token 化重做硬编码色值）"),
        _item("appearance.fontSize", "range", "字号(px)", 14, range_=[12, 18], step=1),
    ]},
}

GROUP_ORDER = ["general", "model", "security", "sandbox", "system", "appearance"]

# registry key → ConfigUpdate 字段映射（旧键走 config_service.update_config，语义不变；
# 未列出的键走通用 region 合并，见 config_helpers.merge_region_patch）
OLD_KEY_MAP: Dict[str, str] = {
    "app.language": "language",
    "workspace.project_root": "project_root",
    "ai.model_ref": "ai_model_ref",
}
# v4.17 修正：安全 10 项全部逐键走通用 region 合并（security.* 逐行 merge，防整块覆盖丢键）。
# 原 SECURITY_KNOWN 整块写 ConfigUpdate.security 的方案撤销——整块替换会覆盖未识别键造成丢数据。
# v4.18 修正：app.max_steps 从 OLD_KEY_MAP 移除，统一走 merge_region_patch（与 app.debug/max_context_tokens/max_history_length/max_rounds 同路径，消除系统参数写路径分裂）；范围校验由 registry range_=[1,10000] + _validate_value 承接。
# v4.20 修正：键名按域收敛后，app.max_steps→agent.max_steps、app.max_rounds→agent.max_rounds、app.debug→logging.debug、
#   app.project_root→workspace.project_root、app.allowed_dirs→workspace.allowed_dirs（OLD_KEY_MAP 同步改）；死配置已全清。
# v4.18 修正：app.theme 从 OLD_KEY_MAP 移除——该键 readonly=True，_validate_value 恒先拒，映射不可达死代码。


def _build_index() -> Dict[str, Dict[str, Any]]:
    """模块加载自检：key 全局唯一，重复直接拒启（3.2 铁律1）。"""
    index: Dict[str, Dict[str, Any]] = {}
    for gname, group in GROUPS.items():
        for item in group["items"]:
            key = item["key"]
            if key in index:
                raise RuntimeError(f"[settings_registry] 重复 key 拒启: {key}")
            index[key] = item
    return index


REGISTRY_INDEX = _build_index()


def get_item(key: str) -> Optional[Dict[str, Any]]:
    """按 key 取 schema 项。"""
    return REGISTRY_INDEX.get(key)


def group_items(group: str) -> List[Dict[str, Any]]:
    """取某组全部 schema 项。"""
    return GROUPS[group]["items"]
