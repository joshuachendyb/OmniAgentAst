# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 配置业务服务(方案4.7.3步骤3)。从 api/v1/model_routes.py 复制 update_config 业务编排,
#   复用 services/model/persistence.py 底层 I/O, 不重复迁移 read/write_yaml_config/save_config/_backup_config/
#   _auto_fix_and_validate(已在 persistence)。越层 app.safety.operation_backup.clear_backup_paths 依赖在业务服务层
#   调用(services→safety 合法方向), 消除 API→safety 越层(守护测试 api 规则可启用)。DTO 边界: 本服务不 import api/v1 DTO,
#   接收 API 层传入的 config_update 对象(鸭子类型访问字段/model_dump), 业务逻辑一字不改。
# 2026-08-13 - 小沈 - P3 CRUD全量下沉: 从 model_routes.py 复制12个CRUD业务逻辑迁入, 业务逻辑一字不改,
#   仅改归属与返回格式(返回plain dict, API层构造Pydantic响应模型)。model_routes 降为纯薄壳。
#   DTO边界: 本服务不import api/v1/model_schemas, 接收DTO对象(鸭子类型)或原始参数。
# 2026-08-13 - 小沈 - 三堂会审修复: validate_config 改只接收 provider。原签名接收(model) 但 API层
#   ConfigValidateRequest 无 model 字段, 迁移后 route 访问 request.model 在 service try 之外抛
#   AttributeError→500(原代码在 try 内被吞返回 valid=False)。get_service_config(provider, model) 的
#   model 参数实际未使用, 改传 "" 保持语义不变。校验接口第一次真正可用(原实现永远走假报错分支)。
# 2026-08-14 - 小欧 - 改名名实相符: model_routes.py→config_routes.py, persistence.py→config_helpers.py(import与docstring同步)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.6: 全文件 resolve_provider_model 拆包 → resolve_model_ref
#   (4处); get_system_config_data 返回 ai_model_ref=resolved_model、get_full_config 返回 current_model_ref=
#   resolved_model、update_config 返回 current_model_ref 结构(方案B 前端 api.ts 契约已同步改)
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P2): update_config 的 updated_fields 内嵌 ai_model_ref 的
#   api_base/display_name null 键剔除(模型转 dict 后过滤 None), 免前端/日志噪声
# 2026-09-21 - 小欧 - 关于页功能: 新增 read_version_file(读 get_code_root()/version.txt 全文返
#   {version_content})，供 GET /config/version-file；Path 顶层 import。
# 2026-09-21 - 小欧 - 修复 None 陷阱: .get('key', '') 在 key 存在但值为 None 时返回 None 非 ''，
#   导致 ProviderInfo(api_base=None) Pydantic 校验 500；全文件 .get() 统一修为 .get() or ''/[]/60/3
# 2026-09-21 - 小欧 - 三堂会审修复：timeout/max_retries 的 `or 60/3` 改为 `is not None` 判断，防止合法值0被吞
# 2026-09-21 - 小欧 - v4.20 死配置清理: get_system_config_data 默认 security 块删 contentFilterEnabled/contentFilterLevel/maxFileSize（全库无消费方）
# 2026-09-21 - 小欧 - v4.20 单源收敛: delete_provider/add_model 的当前模型读写由扁平 ai.provider/ai.model
#   改为 ai.model_ref（is_provider_metadata_field 过滤 provider 列表）；update_config 验证日志与返回
#   current_model_ref 改读 model_ref
# 2026-09-21 - 小欧 - [59]B-4 修复: _mask_api_key 复用公用 mask_secret_value（"****"+末4位，与 /settings /models
#   的 suffix 契约一致）——原"前3后2/≤6全*"与前端 slice(-4) 显示错位；传入 int/None 由 mask_secret_value 内部 str() 兜底
# 2026-09-21 - 小欧 - [59]B-5/B-6/B-7 修复: ①新增 _provider_conf（非 dict provider 归空统一守卫，三处复用，防畸形
#   YAML 下 provider 非 dict .get 崩溃）; ②api_key 接层 str() 化（数字/None 不再 .strip()/len() 崩溃）;
#   ③security 非 dict 统一回默认安全块（防 Pydantic ValidationError→500），默认块提模块级 DEFAULT_SECURITY（DRY）
# 2026-09-21 - 小欧 - [59]B-14 修复: read_config_file/read_version_file ①内容 lstrip("\ufeff") 剥离 BOM
#   （原样透传时与 main.get_version/settings_service.app_version 的显示不一致）; ②超过 512KB 拒读（size 上限防
#   f.read() 全量进 JSON 响应）
# 2026-09-21 - 小欧 - [59]B-15 修复: get_model_list 的 provider.models dict 老格式({model: {...}})归一为键列表——
#   原只认 list，老式/手写 YAML 整个 provider 静默缺列表，与 /models 展示不一致
# 2026-09-22 - 小欧 - 31候选修复 #9/#14: update_config 包 filelock(config.yaml.lock) 与 merge_region_patch/
#   get_config_snapshot 同一把锁串行化（并发读-改-写旧快照整文件覆盖丢更新、文件占用 PermissionError→500 根治）；
#   成功路径改 reload_ai_config(_load+reset) 与 merge 写链路行为对齐（原仅 reload 不 reset，运行态缓存不一致）
# 2026-09-24 - 小欧 - 禁止backward死代码清理: 删 delete_provider/delete_model/update_model/update_provider/
#   add_provider/add_model 6函数（仅被已删 /config/provider/* 路由调用, 前端零调用）；同步清孤儿 import — 小欧-2026-09-24
# 2026-09-26 - 小欧 - [72]第七章(7.3) 落地: 删死契约 _mask_api_key(第2套掩码, "****"+末4位 字符串形态),
#   /config/full 的 providers.{name}.api_key 改用第 1 套唯一权威 mask_secret_value → **形状变为对象**
#   {configured, prefix, suffix}。删除前已按 7.3 要求复核消费方: 前端 getFullConfig( 全项目零调用
#   (仅 config.api.ts:138 定义处); config.api.ts 的 ConfigValidateRequest/ProviderInfo 两 interface
#   仅文件内自引用、无组件消费 —— 故 [59]B-4 注释宣称的"前端 slice(-4) 兼容"确无对应代码, 死契约成立。
#   第3套 api_key_configured(bool, 回答"是否已配置"这一布尔问题) 保留, 语义区别已写入 config_schemas
#   的字段说明(避免后人误以为三套可互换取错形状) — 小欧 2026-09-26
# 2026-09-26 (三堂会审后修正) - 小欧 - 10 大规范 + 关联逻辑复核, 本文件 4 处已改:
#   ①[规范违规] `from app.logger import logger` 与 `from app.utils.response_utils import api_success`
#     被误放在**模块中部**（update_config 函数体之后、DEFAULT_SECORY 之前）。Python 允许 import
#     出现在模块任意层级(照样执行) → 不报错、测试也过, 但违反 PEP8 与项目 import 规范
#     (import 必须在文件头依赖区)。危害: 读者会误以为 logger 是 update_config 的局部导入、
#     模块执行顺序反直觉、lint 的 import/first 规则一旦启用即整片报错。已归位到文件头。
#   ②[YAGNI 死 import] `api_success` 经全仓 Select-String 确认**零引用** → 删（没引用就不留）。
#   ③[注释撒谎 · 事实错误] import 区原注释称"删 update_config 本体"、"FIELD_HANDLERS/
#     _restore_backup_if_needed 随本体删"。**update_config 本体并未被删**(仅内部收敛为只切模型),
#     且这两个符号在收敛后**仍被 update_config 使用**。照原注释再删一次 → 运行时 NameError。
#     已按事实重写注释并逐条标注保留理由。
#   ④[KISS-DIRECT 无意义中间层] `handler = FIELD_HANDLERS["ai_model_ref"]; handler(...)` 退化为
#     纯中转(7 项收敛为 1 项后，派发表不再有可扩展性价值)，改为直接调 _update_model_ref。
#   ⑤[可观测性倒退] 删备份的 `except Exception: pass` 静默吞异常 → 恢复 logger.warning。
#     删不掉的备份副本内含**明文 api_key**, 静默 pass 让密钥副本堆积无人知晓。
#   ※ 如实记录: 上述 ④ 改完后, FIELD_HANDLERS 在全仓已成**零消费方**(含 tests/e2etests 均无引用)。
#     本次**不删**它 —— [72]第十一章设计明文要求"FIELD_HANDLERS 收敛为只含 ai_model_ref 一项",
#     即保留该结构是设计决定而非疏漏。此事实记录在案, 是否进一步删除请北京老陈裁定。
"""
config_service — 配置业务服务(services/model)

职责: 配置CRUD业务编排。YAML底层I/O归属config_helpers.py, 本服务只做编排。
A7(小欧 2026-08-13): update_config 业务编排。
P3(小沈 2026-08-13): 全量CRUD下沉, model_routes 降为纯薄壳。
"""
import os
import subprocess
import copy
from pathlib import Path

from fastapi import HTTPException

# 2026-09-26 - 小欧 - [72]第十一章(11.5 第1步) 孤儿 import 清理（逐条核实零引用后删）:
#   删 import yaml（唯一使用点原在 update_config 内的写后 yaml.load，本轮随该校验一并移除）
#   删 _make_safe_loader（同上；故**本行连注释一起重写**——原文案声称"随 update_config 本体删除"，
#     而 update_config 本体**并未被删**（仅内部收敛为只切模型），原注释在撒谎）
#   删 clear_backup_paths（唯一使用点原在 update_config 末尾。**注**：该调用删除无实际副作用 ——
#     其读侧 get_backup_paths / 写侧 set_backup_paths 经全仓 Select-String 确认同样零调用，
#     即它操作的是一组无人读取的全局变量。故此项不算功能退化，只算去掉一次无意义调用）
#   保留 FIELD_HANDLERS 与 _restore_backup_if_needed —— 二者在**收敛后仍被 update_config 使用**
#     （前者派发 ai_model_ref，后者用于两个 except 分支的回滚）。原注释称二者"已随本体删"属**事实错误**，
#     若照该注释再删一次，update_config 会在运行时 NameError。
# 2026-09-26 - 小欧 - [72]三堂会审后修正(import 归位 + 死 import): 原先
#   `from app.logger import logger` 与 `from app.utils.response_utils import api_success`
#   被放在**模块中部**（update_config 函数体之后、DEFAULT_SECURITY 之前），是本轮误插。
#   Python 允许 import 出现在模块任意层级（照样执行），所以**不报错、测试也过**，但违反 PEP8
#   与项目 import 规范: import 必须在文件头依赖区。危害: ①读者会误以为 logger 是 update_config 的
#   局部导入；②模块执行顺序反直觉；③lint 的 import/first 类规则一旦启用即整片报错。
#   同批删除: `api_success` **全仓零引用**（Select-String 全量确认，除自身定义外无调用），
#   属第十一章收敛后残留死 import，YAGNI 清除（没引用就不留，不"以防万一"）。
from app.logger import logger
# 2026-09-26 小欧 - [72]第十一章(11.5): _make_safe_loader 已删（随 update_config 内的写后校验移除），
#   同行保留 get_config_instance —— get_system_config_data / fix_config 仍在用。
from app.config import get_config as get_config_instance
from app.services.model.resolver import get_ai_config_resolver
from app.services.model.config_helpers import (
    # 2026-09-26 - 小欧 - [72]三堂会审后修正·二: 删本行的 `FIELD_HANDLERS` 导入 ——
    #   update_config 已改为直调 `_update_model_ref`（去无意义中间层），本文件内再无第二处引用，
    #   留着即死 import（F401 类）。注意与"保留 FIELD_HANDLERS 表本身"不矛盾：
    #   表的定义（config_helpers 内）按 [72]第十一章设计保留，删的只是本文件用不上的导入名。
    #   其余 6 项(provider_api_keys/theme/language/max_steps/security/project_root)随本次整改删除:
    #   provider_api_keys 是[72]第三章认定的"第二个能擦除密钥的入口"; 其余 5 项功能已迁移至 settings
    #   registry 对应项(文档 11.2 表), 且 theme 早已是 registry 只读项(暗色入口已移除)——不再有第二条写路径。
    _update_model_ref,  # [72]十一章: 唯一保留的 handler（直调，不经 FIELD_HANDLERS 中转）
    _auto_fix_and_validate,
    _backup_config,
    _fix_config_common_issues,
    _restore_backup_if_needed,  # [72]十一章: 收敛后 update_config 的 except 分支仍需回滚备份
    _validate_config_integrity,
    get_config_path,
    is_provider_metadata_field,
    mask_secret_value,
    read_yaml_config,
    reload_ai_config,
    write_yaml_config,
)


def update_config(config_update):
    """[72]第十一章(11.5 第1步) 收敛后的配置更新业务编排 — **只切模型**。
    原实现（已删）经 FIELD_HANDLERS 派发 7 个 handler：ai_model_ref / provider_api_keys / theme /
    language / max_steps / security / project_root。本次整改后本函数**只保留 ai_model_ref 一条能力**：
      - provider_api_keys：能空串擦除密钥（[72]第三章认定第二个入口），字段已从 ConfigUpdate 删除，漏洞消失
      - theme/language/max_steps/security/project_root：功能已迁移至 PUT /settings 对应 registry 项，
        旧字段与旧 handler 一并删除，不留第二条写路径（避免同一配置两个写入口产生分叉）
    保留原因：configApi.switchCurrentModel（AppContext.tsx:266，顶栏与设置页「切换全局模型」唯一写链）
    仍调 PUT /config；删端点会导致该功能 404 失效（功能退化，违反"只能增强不能退化"红线）。
    事务语义不变：整段读-改-写包 filelock(config.yaml.lock)，异常路径回滚备份。
    """
    import filelock  # 局部 import：filelock 为可选依赖，抑制启动失败面（与 merge_region_patch 同策略）
    config_path = get_config_path()
    with filelock.SoftFileLock(str(config_path) + ".lock", timeout=10):
        config_data = read_yaml_config(Path(config_path)) or {}
        original_config_data = copy.deepcopy(config_data)
        restored = [False]
        backup_path = _backup_config(config_path)
        try:
            # 2026-09-26 - 小欧 - [72]三堂会审后修正(KISS-DIRECT · 去掉无意义间接层):
            #   原为 `handler = FIELD_HANDLERS["ai_model_ref"]; handler(config_data, config_update)`。
            #   FIELD_HANDLERS 经第十一章收敛后**只剩这一项**，于是这层字典查表 + 间接调用
            #   已退化为纯粹的中间层 —— 项目铁规明禁: "无中间层: 3 层函数每层只调下一层 → 合并为 1 层"、
            #   "KISS-DIRECT: 逻辑直线，不提前引入抽象"。7 项变 1 项后保留派发表，是"为不再存在的
            #   可扩展性付费"（YAGNI）。改为直接调用已 import 的 _update_model_ref，链路 A→B 两跳到底。
            _update_model_ref(config_data, config_update)
            is_valid, errors, warnings, fail_result = _auto_fix_and_validate(
                config_data, config_path, backup_path, original_config_data)
            if not is_valid:
                return fail_result

            write_yaml_config(str(config_path), config_data)
            reload_ai_config()

            if backup_path and backup_path.exists():
                try:
                    backup_path.unlink()
                    logger.info(f"[update_config] 验证成功, 已删除备份文件: {backup_path}")
                except Exception as e:
                    # 2026-09-26 - 小欧 - [72]三堂会审后修正: 原为 `except Exception: pass`（静默吞掉）。
                    #   备份文件删不掉是**要留痕**的运维事实：残留副本持续堆积、且副本内含**明文 api_key**。
                    #   静默 pass 等于让"密钥副本堆积"无人知晓 —— 可观测性倒退（配置已生效，行为不回滚）。
                    logger.warning(f"[update_config] 删除备份文件失败（可能残留含明文密钥的副本）: {e}")
            return {
                "success": True, "message": "配置更新成功，已校验并生效",
                "updated_fields": {"ai_model_ref": getattr(config_update, "ai_model_ref", None)},
                "warnings": warnings,
                "backup_path": str(backup_path) if backup_path else None,
                "current_model_ref": {
                    "provider": (config_data.get('ai', {}).get('model_ref') or {}).get('provider') or '',
                    "model": (config_data.get('ai', {}).get('model_ref') or {}).get('model') or '',
                },
            }

        except HTTPException:
            _restore_backup_if_needed(backup_path, config_path, restored)
            if backup_path:
                backup_path.unlink(missing_ok=True)
            raise
        except Exception as e:
            _restore_backup_if_needed(backup_path, config_path, restored)
            if backup_path:
                backup_path.unlink(missing_ok=True)
            logger.error(f"配置更新失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="配置更新失败，请稍后重试")


DEFAULT_SECURITY = {
    "enabled": False,
    "confirmDangerousOps": True,
    "auto_confirm_delay": 10,
    "hitl_timeout": 120,
}


def _provider_conf(ai_config: dict, provider: str) -> dict:
    """取 provider 配置；非 dict 一律归空 — 2026-09-21 小欧 [59]B-5 统一守卫
    （畸形 YAML 写 provider 为 str/list 时避免 .get 崩溃；get_system_config_data/get_model_list/get_full_config 复用）"""
    p = ai_config.get(provider)
    return p if isinstance(p, dict) else {}


def get_system_config_data() -> dict:
    """获取系统配置数据 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-08-22 小欧 归一报告v1.25 6.6: ai_provider/ai_model → ai_model_ref: ModelRef 结构"""
    config = get_config_instance()
    resolved_model = get_ai_config_resolver().resolve_model_ref()
    ai_config = config.get('ai', {})
    provider_config = _provider_conf(ai_config, resolved_model.provider)
    api_key = str(provider_config.get('api_key') or '')
    api_key_configured = bool(api_key.strip() != '')
    theme = config.get('app.theme', 'light')
    language = config.get('app.language', 'zh-CN')
    security_config = config.get('security', {})
    if not isinstance(security_config, dict) or not security_config:
        security_config = dict(DEFAULT_SECURITY)
    logger.info(f"获取配置成功: provider={resolved_model.provider}, model={resolved_model.model}")
    return {
        "ai_model_ref": resolved_model,
        "api_key_configured": api_key_configured,
        "theme": theme,
        "language": language,
        "security": security_config,
        "max_steps": config.get_max_steps(),
        "project_root": config.get_project_root()
    }


def validate_config(provider: str) -> dict:
    """配置校验 — 自 model_routes.py 迁入; 三堂会审修复: 只收provider(get_service_config的model参数未使用) — 小沈 2026-08-13
    2026-08-22 小欧 归一: resolve_provider_model 拆包 → resolve_model_ref"""
    try:
        resolver = get_ai_config_resolver()
        try:
            resolver.get_service_config(provider, "")
        except ValueError as e:
            return {"valid": False, "message": str(e), "model": None}
        resolved_model = resolver.resolve_model_ref()
        logger.info(f"配置校验通过: provider={resolved_model.provider}, model={resolved_model.model}")
        return {
            "valid": True,
            "message": f"配置校验通过(未保存),将在首次使用时验证 {resolved_model.provider} ({resolved_model.model})",
            "model": resolved_model.model
        }
    except Exception as e:
        logger.error(f"配置验证异常: {e}")
        return {"valid": False, "message": f"验证过程出错: {str(e)}", "model": None}


def get_model_list() -> dict:
    """获取模型列表 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-08-22 小欧 归一: resolve_model_ref 属性访问"""
    try:
        resolver = get_ai_config_resolver()
        ai_config = resolver.get_ai_config()
        resolved_model = resolver.resolve_model_ref()
        models = []
        model_id = 1
        for provider_name in ai_config.keys():
            if is_provider_metadata_field(provider_name):
                continue
            provider_data = _provider_conf(ai_config, provider_name)
            if not provider_data:
                continue
            provider_models = provider_data.get('models') or []
            # 2026-09-21 小欧 [59]B-15: dict 老格式 models({name: {...}}) 归一为键列表——
            # 原只认 list，老式/手写 YAML 整个 provider 静默不出现在 /config/models，与 /models 列表不一致
            if isinstance(provider_models, dict):
                provider_models = list(provider_models.keys())
            if isinstance(provider_models, list) and provider_models:
                for model_name in provider_models:
                    display_name = f"{provider_name} ({model_name})"
                    is_current = (resolved_model.provider == provider_name and resolved_model.model == model_name)
                    models.append({
                        "id": model_id,
                        "provider": provider_name,
                        "model": model_name,
                        "display_name": display_name,
                        "current_model": is_current
                    })
                    model_id += 1
        logger.info(f"获取模型列表成功: {len(models)}个模型")
        return {"models": models, "default_provider": resolved_model.provider}
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return {"models": [], "default_provider": ''}


def get_full_config() -> dict:
    """获取完整配置 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-08-22 小欧 归一报告v1.25 6.6: current_provider/current_model → current_model_ref 结构"""
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()
    resolved_model = resolver.resolve_model_ref()
    providers = {}
    for provider_name in ai_config.keys():
        if is_provider_metadata_field(provider_name):
            continue
        provider_data = _provider_conf(ai_config, provider_name)
        if not provider_data:
            continue
        api_key = str(provider_data.get('api_key') or '')
        providers[provider_name] = {
            "name": provider_name,
            "api_base": provider_data.get('api_base') or '',
            # [72]第七章(7.3) - 小欧 - 2026-09-26: 删死契约 _mask_api_key（"****"+末4位 字符串形态），
            # /config/full 改用第 1 套唯一权威 mask_secret_value → **形状变为对象** {configured, prefix, suffix}。
            # 删除前已按 7.3 要求复核消费方: 前端 getFullConfig( 全项目零调用（仅 config.api.ts:138 定义处），
            # config.api.ts 的 ConfigValidateRequest/ProviderInfo 两个 interface 仅文件内自引用、无组件消费，
            # 故原注释宣称的"前端 slice(-4) 兼容"确无对应代码 —— 死契约成立。
            "api_key": mask_secret_value(api_key),
            "model": '',
            "models": provider_data.get('models') or [],
            "timeout": provider_data.get('timeout') if provider_data.get('timeout') is not None else 60,
            "max_retries": provider_data.get('max_retries') if provider_data.get('max_retries') is not None else 3,
        }
    return {
        "providers": providers,
        "current_model_ref": resolved_model
    }


def fix_config() -> dict:
    """配置修复 — 自 model_routes.py 迁入 — 小沈 2026-08-13"""
    config_path = get_config_path()
    backup_path = _backup_config(config_path)
    config_data = read_yaml_config(config_path)
    config_data = _fix_config_common_issues(config_data)
    fixed_issues = [f"删除 provider 下废弃的 model 字段"]
    is_valid, errors, warnings = _validate_config_integrity(config_data)
    if not is_valid:
        return {
            "success": False,
            "fixed_issues": fixed_issues,
            "warnings": warnings + errors,
            "backup_path": str(backup_path)
        }
    write_yaml_config(str(config_path), config_data)
    config = get_config_instance()
    config.reload()
    logger.info(f"配置修复成功: 修复了 {len(fixed_issues)} 个问题")
    return {
        "success": True,
        "fixed_issues": fixed_issues,
        "warnings": warnings,
        "backup_path": str(backup_path)
    }


_MAX_READ_FILE_BYTES = 512 * 1024


def read_config_file() -> dict:
    """读取配置文件 — 自 model_routes.py 迁入 — 小沈 2026-08-13
    2026-09-21 小欧 P2-9：返回体扩 path/size/lines/mtime（[58] P2-9）
    2026-09-21 小欧 [59]B-14：BOM 剥离 + 大小上限"""
    config_path = get_config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
    size = config_path.stat().st_size
    if size > _MAX_READ_FILE_BYTES:
        raise HTTPException(status_code=400, detail=f"配置文件过大({size} 字节)，拒绝读取")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read().lstrip("\ufeff")
    stat = config_path.stat()
    return {
        "config_content": content,
        "path": str(config_path),
        "size": stat.st_size,
        "lines": content.count('\n') + 1,
        "mtime": int(stat.st_mtime),
    }


def read_version_file() -> dict:
    """读取 version.txt 全文 — 2026-09-21 小欧 关于页"查看版本文件全文"。
    路径与 main.get_version / settings_service.app_version 一致（get_code_root()/version.txt，DRY）。
    2026-09-21 小欧 P2-9：返回体扩 path/size/lines/mtime（[58] P2-9）
    2026-09-21 小欧 [59]B-14：BOM 剥离 + 大小上限"""
    from app.config import get_code_root  # 局部 import：避免顶层循环依赖
    version_path = Path(get_code_root()) / "version.txt"
    if not version_path.exists():
        raise HTTPException(status_code=404, detail=f"version 文件不存在: {version_path}")
    size = version_path.stat().st_size
    if size > _MAX_READ_FILE_BYTES:
        raise HTTPException(status_code=400, detail=f"version 文件过大({size} 字节)，拒绝读取")
    with open(version_path, "r", encoding="utf-8") as f:
        content = f.read().lstrip("\ufeff")
    stat = version_path.stat()
    return {
        "version_content": content,
        "path": str(version_path),
        "size": stat.st_size,
        "lines": content.count('\n') + 1,
        "mtime": int(stat.st_mtime),
    }


def open_config_folder() -> dict:
    """打开配置目录 — 自 model_routes.py 迁入 — 小沈 2026-08-13"""
    config_path = get_config_path()
    config_dir = str(config_path.parent)
    if not os.path.exists(config_dir):
        raise HTTPException(status_code=404, detail=f"配置目录不存在: {config_dir}")
    subprocess.Popen(
        ["explorer", "/e,", config_dir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info(f"已打开配置目录: {config_dir}")
    return api_success(path=config_dir)