"""ai_config 包内部公用函数 — YAML读写/配置修复/验证/备份/装饰器

迁入: services/config/persistence.py — 小欧 2026-07-10
原分散文件: _ordered_dict.py, _write_yaml_with_order.py, _backup_config.py,
_restore_backup_if_needed.py, _fix_config_common_issues.py, _auto_fix_and_validate.py,
_validate_config_integrity.py, _decorators.py
F10合并: 小欧 - 2026-06-08
"""
# 编辑历史:
# 2026-08-14 - 小欧 - 改名名实相符: persistence.py → config_helpers.py("persistence"只盖住持久化一面, 实为配置域公用杂集: I/O+修复+验证+备份+装饰器)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.6 方案B: ①_update_provider/_update_model 两 handler 合一为
#   _update_model_ref(provider+model+api_base 成对原子写入, 消除对 FIELD_HANDLERS 迭代顺序的耦合);
#   FIELD_HANDLERS 键 "ai_provider"/"ai_model" → "ai_model_ref"; ②_auto_fix_and_validate 的 fail_result
#   current_provider/current_model → current_model_ref 结构
# 2026-09-20 - 小沈 - v4.19 Phase 1/2: 新增公共工具函数 _get_dotted/_config_mtime/mask_secret_value/merge_region_patch/_set_nested;
#   write_yaml_config 改调 atomic_write 原子落盘; _write_system_yaml 改为返回 ordered data（不再直写文件）
# 2026-09-20 - 小沈 - v4.19 Phase 2: 新增 _validate_config_integrity 校验（merge_region_patch 安全网）
# 2026-09-21 小欧 - 依据设计文档 9.3.3 重写 merge_region_patch: 补 filelock 并发锁/备份/完整性校验/
#   写后逐键验证/失败回滚/reload 全链路；_set_dotted 替代 _set_nested；_validate_config_integrity
#   恢复读扁平键。
# 2026-09-21 小欧 - 新增 merge_nested_patch/_merge_region_core/_iter_nested_ops/_set_nested_path/
#   _get_path: 叶段按字面名写入（模型名含点号如 gpt-4.1 不再被当路径拆开，修点号模型名 params/meta
#   错位与删除残留孤儿）；_set_dotted/_get_dotted 复用同一核心。另: 空 patch 直接跳过不备份不写盘；
#   env 接管 provider 放行 api_base/api_key 缺失约束；短 secret 不再整体暴露。
# 2026-09-21 小欧 - _iter_nested_ops 对空 dict 叶值显式 yield 空块（原当内部节点无限展开导致零 ops，
#   "清空模型参数"永远写不落盘）；.get() 的 None 陷阱统一 `or ''/[]`；删无调用方的 _write_system_yaml。
# 2026-09-21 小欧 - v4.20 键名按域收敛与单源收敛: app.max_steps → agent.max_steps；ai.model_ref 统一
#   （provider/model → model_ref 读写校验全部对齐），防写出死键"保存成功永不生效"。
# 2026-09-21 小欧 - 修复: read_yaml_config 坏 YAML 显式抛 500（不静默）、顶层非 dict 归一空 dict；
#   新增 get_config_snapshot 原子快照（同把 .lock），消除"先读数据再 stat"导致前端误判外部更新。
# 2026-09-22 小欧 - _update_model_ref 加 AI_PROVIDER env 接管守卫（否则写入被 env 读回覆盖=假成功）；
#   _update_project_root 改写 workspace.project_root（原写 app.project_root 死键）。
# 2026-09-25 小欧 - 删 _update_model_ref 写盘前错位 reset()（换代正确位置在 reload_ai_config，
#   错位会致"保存模型换两次代"）；reload_ai_config 记 INFO 日志，补齐换代链入口可观测性。
# 2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}（北京老陈裁定，后端一次生成最终串）:
#   mask_secret_value 是全项目 secret 掩码唯一权威（/settings、/models、/config 共用），三档规则:
#     len > 8     → s[:4] + "****" + s[-4:]
#     4 < len <= 8 → "****" + s[-4:]
#     len <= 4    → "****"（真实内容零泄漏）
#     空/纯空白   → {configured: False, masked: ""}
#   收敛动机：旧三键 {configured,prefix,suffix} 让"档位判定+星号拼接"在前后端各实现一遍（违反 DRY），
#   且已漂移出真实 bug —— 前端靠 `prefix === '****'` 猜档位，遇到真实 key 前 4 位恰为 `****` 时拼错；
#   旧两档还有 len<=4 全量回显、len==8 拼回全量明文两处泄漏，本三档一并消除。
#   另: key 一律先去掉全部空白再判空与分档；非字符串按 str() 兜底。
# 2026-09-27 小欧 - 精简冗长注释（09-21~09-25 流水账压缩为按主题归并，只留决策不留过程）；
#   删掉"注释位置错了"这类关于注释的元讨论。
# 2026-09-27 小欧 - 修 B4: _validate_config_integrity 缺 isinstance 守卫，provider 值为 None
#   （yaml `myprov:` 空值）时下方 `'api_base' not in provider_config` 抛 TypeError。本函数被
#   _merge_region_core 每次写调用 → 改任何设置全 500。

import os
import shutil
import yaml
from collections import OrderedDict

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.config import get_config as get_config_instance, _make_safe_loader
from app.utils.file_utils import backup_file  # P5b: 从 utils 导入 — 小沈 2026-08-13

from app.config import get_config_path as _get_config_path
from app.services.lifecycle.lifecycle import reset
from app.logger import logger
from app.utils.response_utils import handle_api_errors as handle_config_errors
from fastapi import HTTPException

# ====================================================================
# 装饰器
# ====================================================================

# __all__ 不包含 import 来的符号 — t-04 小欧 2026-07-10

# ====================================================================
# YAML 有序写入（配置专用）
# ====================================================================

def _repr_ordered_dict(dumper, data):
    return dumper.represent_dict(data.items())


yaml.add_representer(OrderedDict, _repr_ordered_dict)  # 模块 import 时注册一次（文档 9.3.3）
# 文档 9.3.3 merge_region_patch 字面用 yaml.safe_dump（SafeDumper）；add_representer 默认只注册 Dumper，
# 不补注册 SafeDumper 会让 safe_dump 对 OrderedDict 抛 RepresenterError（实测），故补一行 — 小欧 2026-09-21
yaml.SafeDumper.add_representer(OrderedDict, _repr_ordered_dict)


def _order_for_dump(d: Any) -> Any:
    """系统配置专用 YAML 有序化 — 小欧 2026-06-23; 小沈 2026-09-20 v4.19 由 _write_system_yaml 内嵌 _order 上提
    - model/provider 排 ai 块最前面
    - provider 名字保留原始顺序（不字母序重排）
    """
    if not isinstance(d, dict):
        return d
    result = OrderedDict()
    if 'ai' in d:
        ai_data = d['ai']
        ai_ordered = OrderedDict()
        if 'model_ref' in ai_data:
            ai_ordered['model_ref'] = ai_data['model_ref']
        for k in ai_data:
            if k != 'model_ref':
                ai_ordered[k] = _order_for_dump(ai_data[k]) if isinstance(ai_data[k], dict) else ai_data[k]
        result['ai'] = ai_ordered
    for k in d:
        if k != 'ai':
            result[k] = _order_for_dump(d[k]) if isinstance(d[k], dict) else d[k]
    return result

# ====================================================================
# 配置路径 / 读写
# ====================================================================

def get_config_path() -> Path:
    """获取配置文件路径(缓存式调用)"""
    return Path(_get_config_path())

def read_yaml_config(config_path: Path) -> dict:
    """读取 YAML 配置文件,文件不存在时返回空 dict

    2026-09-21 小欧: ①YAMLError 显式抛 500（坏 YAML 必须被看见，禁静默吞）;
    ②顶层非 dict 归一空 dict（str/list 顶层不再对 .get 崩溃，模型/设置读统一空配置语义）
    """
    if not config_path.exists():
        return {}
    with open(config_path, 'r', encoding='utf-8') as f:
        text = f.read()
    try:
        data = yaml.load(text, Loader=_make_safe_loader())
    except yaml.YAMLError as e:
        logger.error(f"配置文件解析失败: {config_path}: {e}")
        raise HTTPException(status_code=500, detail=f"配置文件解析失败: {e}")
    return data if isinstance(data, dict) else {}

def write_yaml_config(config_path: str, data: dict) -> None:
    """使用有序 Key 写入 YAML 配置文件 — 2026-09-20 小沈: 经 atomic_write 原子落盘(9.3.3)"""
    ordered = _order_for_dump(data)
    from app.utils.file_utils import atomic_write
    atomic_write(config_path, yaml.dump(ordered, allow_unicode=True, default_flow_style=False, indent=2))

def reload_ai_config() -> None:
    """重新加载 AI 配置并重置缓存"""
    config_obj = get_config_instance()
    try:
        config_obj._load_config()
    except Exception:
        # 2026-09-25 小欧 - 补失败留痕: 坏配置若只靠异常上抛, 从换代链看就是"改了配置没生效",
        #   无从区分是"写盘失败"还是"重载失败"。此处明确记"未换代, 旧配置继续生效"。
        logger.error("[config] 配置热重载失败(未换代, 旧配置继续生效)", exc_info=True)
        raise
    # 2026-09-25 小欧 - 入口日志补**生效模型**(换代链可独立自证, 不必再去翻 config 写入那套日志):
    #   原日志只写"重新加载 config.yaml 并换代"不带模型, 于是"无在役旧代"的重载完全看不出切成了什么。
    #   实测: 连切 3 次模型(ling-3.0-flash-fin-free → big-pickle → sensenova-6.8-flash-lite),
    #   换代链里只有 1 次带模型名, 另 2 次因那一刻无在役代而丢失目标信息, 排障时只能靠另一套日志反推。
    #   模型须在 _load_config() 之后读, 此刻配置单例已是新值; 与 service 侧"换代触发(退休旧代)"相邻成对,
    #   构成"退的是哪一代 → 切成哪个模型"的完整事实。
    _ai = config_obj.get("ai") or {}
    _new_ref = _ai.get("model_ref") or {}
    logger.info(
        f"[config] 配置热重载触发: 已重载 config.yaml, 生效模型="
        f"{_new_ref.get('provider') or '-'}/{_new_ref.get('model') or '-'}, 即将换代"
    )
    reset()

def is_provider_metadata_field(field_name: str) -> bool:
    """检查字段是否是provider元数据字段（provider/model/model_ref），用于遍历ai配置时跳过 — 小欧 2026-06-18
    2026-09-21 小欧 v4.20 单源收敛：补 model_ref（唯一源），防其被当作 provider 遍历"""
    return field_name in ('provider', 'model', 'model_ref')

def load_config() -> tuple:
    """加载配置的公共函数 — 小欧 2026-06-18
    返回: (config_path, config)
    """
    config_path = get_config_path()
    config = read_yaml_config(config_path)
    return config_path, config

def save_config(config_path: str, config: dict) -> None:
    """保存配置的公共函数 — 小欧 2026-06-18
    """
    write_yaml_config(config_path, config)
    reload_ai_config()

# ====================================================================
# 备份 / 恢复
# ====================================================================

def _backup_config(config_path: Path) -> Path:
    """备份配置文件"""
    result = backup_file(str(config_path), suffix=".backup")
    bp = Path(result["backup_path"])
    logger.info(f"配置文件已备份: {bp}")
    return bp

def _restore_backup_if_needed(
    backup_path: Optional[Path], config_path: Optional[Path],
    restored_flag: List[bool],
) -> bool:
    """恢复备份配置(仅一次)"""
    if restored_flag[0]:
        return False
    if not backup_path or not config_path or not backup_path.exists():
        return False
    try:
        shutil.copy2(str(backup_path), str(config_path))
        restored_flag[0] = True
        logger.warning(f"已从备份恢复配置: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"备份恢复失败: {e}")
        return False

# ====================================================================
# 配置修复
# ====================================================================

def _fix_config_common_issues(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """自动修复常见的配置问题(删除provider下废弃的model字段)"""
    ai_config = config_data.get('ai', {})
    # 2026-09-21 小欧 v4.20 单源收敛: 删除 ai 顶层遗留扁平键 provider/model（唯一源=ai.model_ref）
    for _legacy in ('provider', 'model'):
        if _legacy in ai_config:
            del ai_config[_legacy]
            logger.info(f"已删除 ai 顶层废弃扁平键 '{_legacy}'（唯一源=ai.model_ref）")
    for provider_name in ai_config.keys():
        if is_provider_metadata_field(provider_name):
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            del provider_data['model']
            logger.info(f"已删除 provider '{provider_name}' 下废弃的 model 字段")
    return config_data

# ====================================================================
# 配置验证
# ====================================================================

def _validate_config_integrity(config_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """完整验证配置文件完整性: (是否通过, 错误列表, 警告列表)
    v4.20 单源收敛（2026-09-21 小欧）：改读结构化 ai.model_ref，删扁平 ai.provider/ai.model
    （运行时 resolver._extract_provider_model 与 model_service.get_current_ref 均已改读 model_ref）。"""
    errors = []
    warnings = []
    ai_config = config_data.get('ai', {})

    model_ref = ai_config.get('model_ref')
    if not isinstance(model_ref, dict) or not model_ref.get('provider') or not model_ref.get('model'):
        errors.append("缺少 ai.model_ref.provider/model 字段")
        return False, errors, warnings

    selected_provider = model_ref['provider']
    selected_model = model_ref['model']

    if selected_provider not in ai_config:
        errors.append(f"provider '{selected_provider}' 不存在")
        return False, errors, warnings

    provider_config = ai_config[selected_provider]
    if not isinstance(provider_config, dict):
        errors.append(f"provider '{selected_provider}' 配置格式错误（应为映射）")
        return False, errors, warnings

    # 2026-09-21 小欧 修 S1：env 接管 provider（设 {NAME}_API_KEY）在 YAML 里可无 api_base/api_key，
    # 硬性要求会让「环境变量接管的配置」任意 settings 写都被校验打回；env 存在时放行这两项约束。
    env_managed = bool(os.environ.get(f"{selected_provider.upper()}_API_KEY"))
    if 'api_base' not in provider_config and not env_managed:
        errors.append(f"provider '{selected_provider}' 缺少 api_base 字段")
    # 只判"字段缺失"，不判"空串"：界面明确允许未配置状态（显示"留空=保持原值"），
    # 判空串会让未配置 key 的 provider 连其它配置都存不了（功能退化）。切勿加"空串即错误"。
    # key 三态（空=不改 / 非空=设置 / clear=清空）由 model_service.update_provider_config 唯一承担。
    if 'api_key' not in provider_config and not env_managed:
        errors.append(f"provider '{selected_provider}' 缺少 api_key 字段")
    if errors:
        return False, errors, warnings

    if 'models' not in provider_config:
        errors.append(f"provider '{selected_provider}' 缺少 models 列表")
        return False, errors, warnings

    models_list = provider_config['models']

    if selected_model not in models_list:
        errors.append(f"model '{selected_model}' 不在 provider '{selected_provider}' 的 models 列表中")
        return False, errors, warnings

    for provider_name in ai_config.keys():
        if is_provider_metadata_field(provider_name):
            continue
        provider_data = ai_config.get(provider_name, {})
        if isinstance(provider_data, dict) and 'model' in provider_data:
            warnings.append(f"provider '{provider_name}' 下有废弃的 model 字段,建议删除")

    return True, errors, warnings

# ====================================================================
# 自动修复 + 验证
# ====================================================================

def _auto_fix_and_validate(
    config_data: dict, config_path: Path, backup_path: Optional[Path],
    original_config_data: dict,
) -> Tuple[bool, List[str], List[str], Optional[Dict[str, Any]]]:
    """自动修复+验证,失败则恢复备份"""
    config_data = _fix_config_common_issues(config_data)
    is_valid, errors, warnings = _validate_config_integrity(config_data)
    if not is_valid:
        _restore_backup_if_needed(backup_path, config_path, [False])
        get_config_instance().reload()
        if backup_path and backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
        original_ai = original_config_data.get('ai', {})
        fail_result = {
            "success": False, "message": "配置验证失败", "errors": errors, "warnings": warnings,
            "backup_path": str(backup_path) if backup_path else None,
            # 归一(小欧 2026-08-22 报告v1.25 6.6): current_provider/current_model → current_model_ref 结构
            "current_model_ref": {
                "provider": str((original_ai.get('model_ref') or {}).get('provider') or 'unknown'),
                "model": str((original_ai.get('model_ref') or {}).get('model') or ''),
            },
        }
        return False, errors, warnings, fail_result
    return True, [], warnings, None

# ====================================================================
# 来自 _validators.py
# ====================================================================

def ensure_provider_exists(config: dict, provider_name: str) -> None:
    """确保 Provider 存在于配置中,否则抛 HTTPException(404)"""
    if provider_name not in config.get('ai', {}):
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_name} 不存在"
        )

def ensure_provider_not_duplicate(config: dict, provider_name: str) -> None:
    """确保 Provider 名不重复,否则抛 HTTPException(400)"""
    if provider_name in config.get('ai', {}):
        raise HTTPException(
            status_code=400,
            detail=f"Provider {provider_name} 已存在"
        )

def ensure_model_exists(config: dict, provider_name: str, model_name: str) -> None:
    """确保模型在指定 Provider 中存在,否则抛 HTTPException(404)"""
    providers = config.get('ai', {})
    if provider_name not in providers:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider_name} 不存在"
        )
    models = providers[provider_name].get('models') or []
    if model_name and model_name not in models:
        raise HTTPException(
            status_code=404,
            detail=f"模型 {model_name} 在 Provider {provider_name} 中不存在"
        )

def ensure_model_not_duplicate(config: dict, provider_name: str, model_name: str) -> None:
    """确保模型名不重复,否则抛 HTTPException(400)"""
    providers = config.get('ai', {})
    if provider_name not in providers:
        return
    models = providers[provider_name].get('models') or []
    if model_name and model_name in models:
        raise HTTPException(
            status_code=400,
            detail=f"模型 {model_name} 已存在"
        )

__all__ = [
    "ensure_provider_exists",
    "ensure_provider_not_duplicate",
    "ensure_model_exists",
    "ensure_model_not_duplicate",
]


# ====================================================================
# 模型切换 handler（六个旧 handler 已删, 只留切模型必需的这一个）
# ====================================================================
def _update_model_ref(config_data: dict, update) -> None:
    """provider+model(+api_base) 成对原子写入 — 单一权威入口
    2026-08-22 小欧 归一报告v1.25 6.6 方案B: 原 _update_provider/_update_model 两 handler 依赖
    FIELD_HANDLERS 迭代顺序先后生效, 合并为单一 handler 消除该耦合(DRY/原子性 KISS-DIRECT)
    2026-09-22 小欧 修 S10: AI_PROVIDER env 接管时切换只读(防假成功)——
      原无守卫, 切换写入 yaml 后被 _apply_env_overrides 读回覆盖, 前端"更换成功"实为无效"""
    ai_config = config_data.get('ai', {})
    # 2026-09-22 小欧 修 S10: 与 settings_service env_key=AI_PROVIDER / model_service _raise_if_current_ref_env 同语义
    from app.config import env_nonempty  # 局部 import 防顶层循环
    if env_nonempty('AI_PROVIDER'):
        raise HTTPException(status_code=400, detail="当前模型由环境变量 AI_PROVIDER 接管，切换/删除当前模型只读")
    if update.ai_model_ref.provider not in ai_config:
        raise HTTPException(status_code=400, detail=f"不支持的提供商: {update.ai_model_ref.provider}")
    config_data['ai']['model_ref'] = {
        "provider": update.ai_model_ref.provider,
        "model": update.ai_model_ref.model,
    }
    if update.ai_model_ref.api_base:
        config_data['ai'][update.ai_model_ref.provider]['api_base'] = update.ai_model_ref.api_base
    logger.info(f"更新AI模型: provider={update.ai_model_ref.provider}, model={update.ai_model_ref.model}")


# FIELD_HANDLERS 收敛为只含 "ai_model_ref" 一项。已删的 6 项:
#   provider_api_keys —— 曾被认定为"第二个能擦除密钥的入口"，删除即漏洞消失
#   theme/language   —— 已迁至 registry（theme 早已是只读项，旧写路径是死键回退）
#   max_steps/security/project_root —— 已全部迁至 PUT /settings 对应 registry 项
# 留 ai_model_ref: configApi.switchCurrentModel（顶栏与设置页"切换全局模型"唯一写链）仍走
# PUT /config，但**只写模型**，不再是第二条通用写路径。
#
# ⚠️ 本表当前无消费方（update_config 已直调 _update_model_ref），按原设计保留该结构。
#   是否进一步删除待北京老陈裁定，勿自行处置。
FIELD_HANDLERS: Dict[str, Any] = {
    "ai_model_ref": _update_model_ref,
}


def _get_path(data: Dict[str, Any], parts: Tuple[str, ...], default: Any = None) -> Any:
    """按路径段序列取值（_get_dotted/写后验证共用核心，叶段绝不分裂）。"""
    node: Any = data
    for part in parts:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return default
    return node


def _get_dotted(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """点号键取值。"""
    return _get_path(data, tuple(key.split(".")), default)


_MISSING = object()  # 存在性判定哨兵：与任何合法配置值都不相等（含 None/False/0/''）


def has_dotted(data: Dict[str, Any], key: str) -> bool:
    """点号键在 data 中是否存在。

    设置页 source 原用 `raw_val is not None` 判存在性，但 _get_dotted 对缺键返回
    registry default（非 None）→ 判据恒真 → 缺键也标 'yaml'。取值与存在性必须各用各的判据。
    """
    return _get_path(data, tuple(key.split(".")), _MISSING) is not _MISSING


def _set_nested_path(data: Dict[str, Any], parts: Tuple[str, ...], value: Any) -> None:
    """路径段序列写入嵌套 dict；value 为 None 时删除该叶键并回收空父级
    （merge_region_patch 的 _set_dotted 与 merge_nested_patch 共用核心）。"""
    node = data
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    if value is None:
        node.pop(parts[-1], None)
        for i in range(len(parts) - 1, 0, -1):
            parent = data
            for p in parts[:i]:
                parent = parent.get(p) if isinstance(parent, dict) else {}
            if isinstance(parent, dict) and not parent.get(parts[i]):
                parent.pop(parts[i], None)
            else:
                break
        return
    node[parts[-1]] = value


def _set_dotted(data: Dict[str, Any], key: str, value: Any) -> None:
    """点号键写入嵌套 dict；value 为 None 时删除该叶键并回收空父级
    （v4.17：delete_model 以 None 清 ai.{provider}.model_params.{model} 等块，
    不走 null 字面量——parse_model_params 对 dict(None) 会 TypeError）。"""
    _set_nested_path(data, tuple(key.split(".")), value)


def _iter_nested_ops(tree: Any, prefix: Tuple[str, ...] = ()) -> Iterator[Tuple[Tuple[str, ...], Any]]:
    """嵌套树扁平化为 (路径段, 值) 列表；叶段保持字面名，绝不按点号分裂
    （模型/Provider 名含点号时必须在模型域使用 merge_nested_patch）。
    2026-09-21 小欧 根治：空 dict 叶值显式 yield 空块 {}——原实现把 {} 当内部节点
    展开导致零 ops（"清空模型参数/空块"永远写不落盘，PUT default_params={} 静默无效果）。"""
    if not isinstance(tree, dict):
        yield prefix, tree
        return
    if not tree:
        yield prefix, {}
        return
    for k, v in tree.items():
        yield from _iter_nested_ops(v, prefix + (k,))


def merge_region_patch(region_updates: Dict[str, Any], scope: str) -> str:
    """通用 region 合并写（registry 已知的固定点号键：security.enabled 等）：
    registry 键不含叶段点号，安全按点号分裂。模型/Provider 名域请用 merge_nested_patch。"""
    ops = [(tuple(key.split(".")), value) for key, value in region_updates.items()]
    return _merge_region_core(ops, scope)


def merge_nested_patch(nested_tree: Dict[str, Any], scope: str) -> str:
    """通用嵌套树合并写：叶段按字面名写入（模型/Provider 名含 gpt-4.1 之类点号也不会被拆开）。
    与 merge_region_patch 同链路：备份→内存合并(_set_nested_path)→完整性校验→原子写→逐叶验证
    →失败回滚→reload，返回 backup_path。— 小欧 2026-09-21"""
    return _merge_region_core(list(_iter_nested_ops(nested_tree)), scope)


def _merge_region_core(ops: List[Tuple[Tuple[str, ...], Any]], scope: str) -> str:
    """region 合并写核心（merge_region_patch/merge_nested_patch 共用单条落盘链路）：
    备份 → 内存合并 → _validate_config_integrity 校验（v4.19 补：单写方案下校验
    由本函数统一承载，安全网与 update_config 持平，防绕过校验写坏配置）→
    _order_for_dump 保序 → atomic_write → 重读验证(reload_ai_config) → 异常回滚最近一个备份。返回 backup_path。
    落码：并发保护——进入即持 filelock.SoftFileLock(config.yaml.lock)，
    先写者完成后后写者基于最新文件重读合并，杜绝「读原→改→写」非原子下旧快照覆盖丢项。
    2026-09-21 小欧：空 ops 直接跳过（不备份不写盘，S6 备份膨胀）。"""
    import filelock  # 局部 import：filelock 为新增依赖，抑制启动失败面
    from app.utils.file_utils import atomic_write  # 局部 import：utils 不反向依赖 services

    if not ops:
        logger.info(f"[{scope}] region 合并写入: 空 patch，跳过（不备份不写盘）")
        return ""

    config_path = Path(get_config_path())
    lock = filelock.SoftFileLock(str(config_path.with_suffix(config_path.suffix + ".lock")), timeout=10)
    with lock:
        backup_path = _backup_config(config_path)
        restored = [False]
        try:
            config_data = read_yaml_config(config_path) or {}
            for parts, value in ops:
                _set_nested_path(config_data, parts, value)
            is_valid, verr, _w = _validate_config_integrity(config_data)
            if not is_valid:
                raise RuntimeError("配置完整性校验失败: " + "; ".join(verr))
            ordered = _order_for_dump(config_data)  # 保序：与 write_yaml_config 同一排序，不打乱键序
            atomic_write(str(config_path), yaml.safe_dump(ordered, allow_unicode=True,
                                                           default_flow_style=False, indent=2))
            verify = read_yaml_config(config_path)
            for parts, value in ops:
                if _get_path(verify, parts) != value:
                    raise RuntimeError(f"写入验证失败: {'.'.join(parts)}")
            reload_ai_config()
            logger.info(f"[{scope}] region 合并写入成功: {sorted('.'.join(p) for p, _ in ops)}")
            return str(backup_path)
        except Exception:
            _restore_backup_if_needed(backup_path, config_path, restored)
            # 设计文档 9.3.3 字面的 logger.error+裸 raise 在 except 块外会报
            # "No active exception to reraise"（Python 语义实测）；移入 except 块内
            # 保证「记日志 + 原样重抛」语义正确 — 小欧 2026-09-21
            logger.error(f"[{scope}] region 合并写入失败已回滚", exc_info=True)
            raise


def _config_mtime() -> float:
    """config.yaml mtime（公共函数，settings_service/model_service 共用，v4.18 DRY 修正）。"""
    try:
        return os.path.getmtime(get_config_path())
    except OSError:
        return 0.0


def get_config_snapshot() -> Dict[str, Any]:
    """配置数据 + mtime 原子快照 — 2026-09-21 小欧
    与 merge_region_patch 同一把 config.yaml.lock，读写互斥：读侧不再有
    "先 read_yaml_config 再单独 stat"的窗口（并发写落在两操作间 → 数据旧/mtime 新 → 前端误刷新）。
    锁超时 10s 与写侧一致；缺文件时 data={}、mtime=0.0（不抛错）。"""
    import filelock  # 局部 import：filelock 为新增依赖，抑制启动失败面（与 merge_region_patch 同策略）
    lock_path = Path(str(get_config_path()) + ".lock")
    with filelock.SoftFileLock(str(lock_path), timeout=10):
        data = read_yaml_config(Path(get_config_path()))
        try:
            mtime = os.path.getmtime(get_config_path())
        except OSError:
            mtime = 0.0
    return {"data": data, "mtime": mtime}


def mask_secret_value(value: Any) -> Dict[str, Any]:
    """secret 掩码公共函数（**唯一权威**）：永不返明文，只返 {configured, masked 可直接显示的串}。

    2026-09-27 北京老陈裁定 - 契约由 {configured, prefix, suffix} 三键改为两键：
      原三键把"怎么拼"交给前端（前端要自己判档位、点数星号），掩码规则在前后端各实现一遍（违反 DRY），
      且已漂移出真实 bug —— 真实 key 前 4 位恰为 `****` 时前端无法区分"真前缀是星号"与"短 key 档"。
      现后端一次生成最终可显示串，前端零掩码逻辑。三档规则见文件头编辑历史。
    """
    # 【编辑历史 — 最新在下】
    # 2026-09-26 - 小欧 - 落实北京老陈裁定，**收敛为两档**（原为 4 档: <4 / 4~7 / 8~11 / >=12）:
    #   裁定原话:「只是分大于=8还是小于8」+「>=8 按规矩来处理(前4+后4)」+「小于8的 显示后4位, 前面加4个*」。
    # 2026-09-27 - 北京老陈裁定改为**三档**，并定契约由后端一次生成最终串（星号一律 4 个）:
    #   ① len >  8      -> s[:4] + 4星 + s[-4:]      「按规矩: 前4 + 后4」
    #   ② 4 < len <= 8  -> **** + s[-4:]               「后面4个 + 前面4个*」
    #   ③ len <= 4      -> ****                       「只是显示 4 个*」= **不露真实内容**
    #   ④ 空(未配置)    -> configured=False, masked=""
    #   规则同时消除原两档的残留风险: len<=4 曾全量回显、len==8 曾拼回全量明文，③档后均不再发生。
    #   另: key 只做去空白(不校验内容), 非字符串按 str() 兜底走同一分档。
    s = "".join(str(value or "").split())   # 去全部空白(北京老陈: "只做 trim 前后中间空白")
    if not s:
        return {"configured": False, "masked": ""}
    if len(s) <= 4:
        return {"configured": True, "masked": "****"}
    if len(s) <= 8:
        return {"configured": True, "masked": "****" + s[-4:]}
    return {"configured": True, "masked": s[:4] + "*" * 4 + s[-4:]}
