# -*- coding: utf-8 -*-
"""
settings_service — 设置页 6 组服务（3.1 前门：读独立+写复用旧链，YAML I/O 复用 config_helpers 同一套）
读：经 read_yaml_config/get_config（与后端业务同源同批）→ {groups:{data,sources,mtime}} + env 标注 + secret 掩码
写：全部 key 一次 merge_region_patch 单次落盘（v4.19：不再分旧/新键两次写，防部分成功）；
    merge_region_patch 内部先 _validate_config_integrity 校验再原子写（安全网与 update_config 持平）。
只读项 config_path/version 由本服务组装。
注：v4.19 起 settings_service 不再直接调 update_config_service——旧链仅剩 ai.model_ref 一个映射键，
    且其写语义（结构+扁平双写）已由 update_settings 内联等价实现（P0-2），避免两阶段写的半程失败风险；
    写旧业务键（语言/项目根目录）与安全/新键同路径经 region 合并，字段语义由 registry schema 承接。

编辑历史:
  2026-09-20 - 小沈 - 新建：3.1 前门实现 + 5.2 env/secret 契约 + 5.3 get_setting
  2026-09-20 - 小沈 - 核查 B1/B2/B5：掩码改调 config_helpers.mask_secret_value（消与 model_service 重复）；
    通用合并上提 config_helpers.merge_region_patch（消私有跨域）；_app_version 公开为 app_version
  2026-09-20 - 小欧 - v4.17：security 逐键走通用合并（去 SECURITY_KNOWN 整块写，防覆盖丢键）；
    update_config 返回 fail_result 透传 errors（防假成功）；PUT 响应带 mtime
  2026-09-20 - 小沈 - v4.19：update_settings 改单次落盘（弃 update_config 两阶段），ai.model_ref 内联双写
  2026-09-21 - 小欧 - 对齐文档54 9.1.2：update_settings 成功返回不含 errors 字段（文档如此），撤销此前误加的空 errors
   2026-09-21 - 小欧 - 三堂会审第三轮 22 真实 bug 修复（settings 域 S2/S3/S4，其余模型域见 model_service）——
     ①S2 merge_region_patch 对非法 model_ref 目标（provider 不存在/模型不在列表）抛 RuntimeError 未捕获→500，
     改在 update_settings 内捕获转 {ok:False, errors}，杜绝裸异常；②S3 校验对 None 一律放行→_set_dotted(None)
     直接删 YAML 键（select/bool/range 字段被"清空消失"），改为仅当该 key 默认值本身为 None 时允 null
     （如 chat.max_tokens 留空=跟随模型），否则拒绝；③S4 os.environ.get(env_key) is not None 把空字符串
     环境变量误判为 env 接管（AI_PROVIDER='' 导致模型永不可改），改 bool(...) 非空才判定接管
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import get_config, get_code_root
from app.db.models.chat_models import ModelRef
from app.logger import logger
from app.services.model.config_helpers import (
    get_config_path,
    mask_secret_value,
    merge_region_patch,
    read_yaml_config,
    _get_dotted,
    _config_mtime,
)
from app.services.settings.settings_registry import (
    GROUPS, GROUP_ORDER, get_item,
)


def _raw_config() -> Dict[str, Any]:
    return read_yaml_config(Path(get_config_path()))


def _resolved(key: str, default: Any = None) -> Any:
    return get_config().get(key, default)


def app_version() -> str:
    try:
        vf = Path(get_code_root()) / "version.txt"
        if vf.exists():
            with open(vf, "r", encoding="utf-8") as f:
                for line in f:
                    v = line.strip().lstrip("\ufeff")
                    if v:
                        return v
    except Exception as e:
        logger.warning(f"读取 version 失败: {e}")
    return "0.0.0"


def _item_data(key: str, item: Dict[str, Any], raw: Dict[str, Any]) -> Tuple[Any, str]:
    if key == "config_path":
        return str(get_config_path()), "ro"
    if key == "version":
        return app_version(), "ro"
    raw_val = _get_dotted(raw, key, item["default"])
    eff_val = _resolved(key, item["default"])
    is_env = bool(item.get("env_key") and os.environ.get(item["env_key"]))
    if item.get("secret"):
        return mask_secret_value(eff_val), ("env" if is_env else "yaml")
    if is_env:
        return eff_val, "env"
    return raw_val if raw_val is not None else item["default"], "yaml"


def get_all_groups() -> Dict[str, Any]:
    raw = _raw_config()
    groups: Dict[str, Any] = {}
    for gname in GROUP_ORDER:
        data: Dict[str, Any] = {}
        sources: Dict[str, str] = {}
        for item in GROUPS[gname]["items"]:
            val, src = _item_data(item["key"], item, raw)
            data[item["key"]] = val
            sources[item["key"]] = src
        groups[gname] = {"data": data, "sources": sources}
    return {"groups": groups, "version": app_version(), "mtime": _config_mtime()}


def get_group(group: str) -> Dict[str, Any]:
    if group not in GROUPS:
        raise ValueError(f"未知分组: {group}")
    raw = _raw_config()
    data: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    for item in GROUPS[group]["items"]:
        val, src = _item_data(item["key"], item, raw)
        data[item["key"]] = val
        sources[item["key"]] = src
    return {"data": data, "sources": sources, "mtime": _config_mtime()}


def get_schema() -> Dict[str, Any]:
    return {"groups": {g: {"label": GROUPS[g]["label"], "items": GROUPS[g]["items"]}
                        for g in GROUP_ORDER}}


def get_mtime() -> Dict[str, float]:
    return {"mtime": _config_mtime()}


def get_setting(key: str, default: Any = None) -> Any:
    item = get_item(key)
    return _resolved(key, item["default"] if item else default)


def _validate_value(item: Dict[str, Any], value: Any) -> Optional[str]:
    if item.get("readonly"):
        return f"{item['key']} 为只读项"
    t = item["type"]
    # 2026-09-21 小欧 修 S3：None 仅当该 key 默认值本身为 None（如 chat.max_tokens 留空=跟随模型）时放行；
    # 否则拒绝——旧实现一律放行，_set_dotted(None) 直接删 YAML 键，select/bool/range 字段被"清空消失"。
    if value is None:
        if item["default"] is None:
            return None
        return f"{item['key']} 值不能为 null"
    if t == "bool" and not isinstance(value, bool):
        return f"{item['key']} 应为 bool"
    if t == "int" and not isinstance(value, int):
        return f"{item['key']} 应为整数"
    if t in ("float", "range") and not isinstance(value, (int, float)):
        return f"{item['key']} 应为数字"
    if item.get("range"):
        lo, hi = item["range"]
        if not (lo <= float(value) <= hi):
            return f"{item['key']} 超出范围 [{lo}, {hi}]"
    if item.get("options") and value not in item["options"]:
        return f"{item['key']} 非法选项"
    if t == "model_ref" and not (isinstance(value, dict) and value.get("provider") and value.get("model")):
        return "ai.model_ref 应为 {provider, model} 结构"
    return None


def update_settings(patch: Dict[str, Any]) -> Dict[str, Any]:
    raw = _raw_config()
    updated: List[Dict[str, str]] = []
    need_restart: List[str] = []
    warnings: List[str] = []
    errors: List[str] = []
    region: Dict[str, Any] = {}

    for key, value in patch.items():
        item = get_item(key)
        if item is None:
            errors.append(f"未知 key: {key}")
            continue
        err = _validate_value(item, value)
        if err:
            errors.append(err)
            continue
        _, src = _item_data(key, item, raw)
        if src == "env":
            warnings.append(f"{key} 被环境变量接管，已跳过")
            continue
        if item.get("restart") and _get_dotted(raw, key, item["default"]) != value:
            need_restart.append(key)
        if key == "ai.model_ref":
            ref = ModelRef(**value)
            region["ai.model_ref"] = ref.model_dump()
            if ref.provider and ref.model:
                region["ai.provider"] = ref.provider
                region["ai.model"] = ref.model
        else:
            region[key] = value
        updated.append({"key": key, "source": "yaml"})

    if errors:
        return {"ok": False, "updated": [], "need_restart": [], "warnings": warnings,
                "errors": errors, "mtime": _config_mtime()}
    if region:
        try:
            merge_region_patch(region, scope="settings")
        except RuntimeError as e:
            # 2026-09-21 小欧 修 S2：model_ref 目标非法（provider 不存在/模型不在列表）被 merge 校验
            # RuntimeError 抛穿→500；捕获转可读 errors（配置未变更，rollback 由 merge 内部完成）。
            logger.warning(f"[settings] 合并写入被校验拒绝: {e}")
            return {"ok": False, "updated": [], "need_restart": [], "warnings": warnings,
                    "errors": [str(e)], "mtime": _config_mtime()}
    return {"ok": True, "updated": updated, "need_restart": need_restart,
            "warnings": warnings, "mtime": _config_mtime()}
