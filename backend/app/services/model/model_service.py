# -*- coding: utf-8 -*-
"""
model_service — 模型编排器（位于 model 域，与 config_service/config_helpers/resolver 同域聚合）
读：解析 config.yaml 的 models[]/model_params/model_meta/provider_config 区域（动态遍历 provider，
禁止硬编码 provider 名，与旧页铁律一致）；写：校验 → config_helpers.merge_region_patch（单次落盘）→ config.yaml。
数据模型（v4.17）：models[] 保持字符串列表（旧链不变式）；模型参数写 ai.{provider}.model_params.{model}
（运行时 parse_model_params 消费）；label/range/capabilities 写 ai.{provider}.model_meta.{model}（UI 元数据）。
current_model_ref 单源为结构化 ai.model_ref（2026-09-21 小欧 v4.20 收敛：删旧扁平 ai.provider/ai.model 双写）；空值不写空键。

编辑历史:
  2026-09-20 - 小沈 - 新建：5.2 模型管理契约（合并返回/级联/switched_to/立即生效）
  2026-09-20 - 小沈 - 核查 B1/B2/A2：掩码改调 config_helpers.mask_secret_value；合并写改调
    config_helpers.merge_region_patch（消私有跨域）；delete_model 删光当前 provider 模型时跨
    provider 回退，不写空 model_ref
  2026-09-20 - 小欧 - v4.17：models[] 回字符串列表；模型参数/元数据分置 model_params/model_meta；
    delete_provider 单次落盘 + 禁删最后一个 Provider；_sync_current 空值保护
  2026-09-21 - 小欧 - 对齐设计文档 9.1.3：delete_provider switched_to 返回 provider 名称（target_p or None），撤销此前误改的模型名称版
  2026-09-21 - 小欧 - 修复 None 陷阱: .get('key','')/get('key',[])/get('key',{}) 在 key 存在但值为 None 时返回 None，
    统一修为 .get('key') or ''/[]/{}/60/3（config_service/config_helpers/model_service/resolver 共 12 处）
   2026-09-21 - 小欧 - 三堂会审第三轮 22 真实 bug 修复（模型域，对应 config_helpers 的
     merge_nested_patch 系列）——①add/update/delete_model 与 add/update/delete_provider 全部改走
     merge_nested_patch 嵌套树写(叶段字面名)：点号模型名 gpt-4.1 不再被拆成 model_params['gpt-4']['1']
     (错位+孤儿)；②add_provider 校验保留键 provider/model/model_ref 与空名；
     ③delete_model 未知 provider 前置 ValueError，不再写入空块污染；④add_model 空模型名拒绝；
     ⑤delete_provider 跳板扫第一个有可用模型的 provider，deelete_model/deelete_provider
     无可用回退时抛"禁止删除最后一个可用模型"守卫；⑥add_provider 接受 models 列表与
     max_retries(链路透传)；⑦env 接管双标准对齐：{NAME}_API_KEY 命中的 provider 读只读、
     AI_PROVIDER 命中时当前模型切换/删除只读；⑧update_provider_config 支持 label 更新、
     拒绝非法字段；⑨get_models 输出补 max_retries 对齐 ProviderInfo DTO
     2026-09-21 - 小欧 - 建议报告: update_model 对空 default_params 提交由"跳过+无有效配置项 500"改为
      显式清空（写空块 {}），配合 config_helpers._iter_nested_ops 空 dict 叶值修复根治"清空不落盘"
# 2026-09-21 - 小欧 - 三堂会审修复：timeout/max_retries 的 `or 60/3` 改为 `is not None` 判断，防止合法值0被吞
# 2026-09-21 - 小欧 - v4.20 单源收敛: get_current_ref 去扁平键 fallback 只读 ai.model_ref（签名去 providers 参数）；
#   _sync_current 只写 ai.model_ref（删扁平双写）——与 resolver/config_helpers 统一为单一真相源
# 2026-09-22 - 小欧 - param_options 读写链落地：①加 DEFAULT_PARAM_OPTIONS 全局兜底 +
#   _resolve_param_options 三层解析并集（模型级>provider级>全局）、_models_of 组装 param_options；
#   update_model 先合并本次新选项再校验（避免同批改选项+改值误杀）、unknown 白名单加 param_options、
#   落 model_meta；update_provider_config key_map 加 param_options（Provider级写入口）。
#   ②add_model 签名加 param_options + 选项表非空 string[]/值在表内（0拒）校验 + 落 model_meta
#   （不送 param_options 与现状兼容，tree 不写该键）。
# 2026-09-22 - 小欧 - get_models 显示层 timeout/max_retries 兜底改读 tuning
#   （timeout→tuning.llm_net.read_timeout 默认150、max_retries→tuning.llm.stream_max_retries 默认3），
#   import 补 from app.config import get_config——消除显示值60/3与运行时30/3 不一致（显示即真相）。
# 2026-09-22 - 小欧 - Provider 参数元数据：①常量区加 PROVIDER_PARAM_TYPES + KNOWN_PROVIDER_KEYS（元数据源头，
#   新增 Provider 参数只需加一行 + config.yaml 对字段，前端零改）；②get_models Provider 段加
#   param_types 元数据 + 动态标量值透传（KNOWN_PROVIDER_KEYS 之外标量平铺）；③update_provider_config
#   加 param_types 白名单（key_map + PROVIDER_PARAM_TYPES 之外拒，防任意键注入）+ 动态字段落盘
#   （param_types 内 key_map 外的标量直写 ai.{provider}.{k}，复用 merge_nested_patch 叶值链路）。
# 2026-09-24 - 小欧 - 参数键级删除：update_model 白名单加 remove_params——先从 model_params 拷贝删键、
#   同步清 model_meta.range/param_options 对应键，再 merge default_params（空 dp 仍=整块清空，与既有语义叠加：
#   remove 先算好 new_params，dp 非空则 update，dp 为空则置 {}）。前端①参数行 × 删除按钮通道 — 小欧-2026-09-24
# 2026-09-24 - 小欧 - 三堂会审修复（四条，逐条真伪鉴别后落码）：
#   ① remove 不再无条件 setdefault model_meta（原必建空块落 YAML model_meta.{model}:{} 污染），
#     range/param_options 清理仅实际命中才建块；
#   ② remove 的 meta 清理挪到 fields param_options 写入之后执行（原在前，293 行同批
#     param_options 全量覆盖使已删键选项复活）；清理跳过 default_params 重加键（keep 集合，
#     remove+dp 同批恢复值时其 meta 保留不误删）；
#   ③ remove_params 全为不存在键（model_params 均无命中且 meta 无命中、无 default_params、
#     无其它字段）= 幂等 no-op 成功返回不写盘（原仍全量 merge 空耗备份/原子重写/mtime 抖动）；
#   ④ range/param_options 双份近似清理收敛 for meta_key 单循环（DRY）— 小欧-2026-09-24
# 2026-09-24 - 小欧 - 模型库：新增 fetch_remote_models（GET 远程列表）与
#   replace_provider_models（PUT 替换写入 + 差集孤儿清理）— 小欧-2026-09-24
# 2026-09-24 23:55:00 - 小欧 - 模型库核查修复 2 处：①fetch_remote_models 组头
#   api_key 补读 {NAME}_API_KEY env 接管值（env 优先，YAML 兜底；原仅读 YAML，
#   env 接管时 YAML 可无 api_key 致 Bearer 空 key 远端 401）；②api_base 空的 400
# 2026-09-25 - 小欧 - 修复参数删除两处复发（守护测试 verify_bz_remove_params_guard 实证 temperature 残留）：
#   _iter_nested_ops 对非空 dict 无整块替换语义（递归展平为叶键写），update_model 落 new_params 整块
#   时删键意图丢失; 改 remove 命中时对残留键显式写 None（_set_nested_path 原生删键），
#   dp 恢复键原位保留不误删;(verify_cfg_weak_guard 10 passed) — 小欧-2026-09-25
#   文案补「该 Provider」前缀对齐设计 — 小欧-2026-09-24
# 2026-09-25 - 小健 - 模型列表全链路排序: _parse_remote_models_body 收集后按 id 字母序(不分大小写)单点排序,
#   远端返回即有序→模型库列表/分组组内/保存落盘 finalList/模型Tab下次保存后下拉全字母序(北京老陈确认全链路方案) — 小健-2026-09-25
# 2026-09-26 - 小欧 - api_key 三态/base_url 必填同一函数一次落地(铁律: 同函数禁止拆两次改):
#   (1)api_key 三态做实为后端唯一权威: key_map 循环内对 api_key 分流 - 空串/纯空白 continue 跳过(不写入=不修改),
#     非空先 str(v).strip() 再落盘; 字段不出现/None 由 v is not None 拦; clear=true 仍走下方显式写空串分支(唯一清空途径)。
#     修前缺陷: if k in key_map and v is not None 把空串判为合法, 任何非界面途径传空串即擦除密钥还返回 ok
#   (2)去空格与三态同一处收口(写入前 strip), 与 client_sdk 消费端兜底两侧对齐, 双通道 strip 不一致根因消除
#   (3)clear 与设置值互斥: clear is True 且 api_key 非空 -> 400, 不静默丢弃任何一方(修前无条件覆盖新 key)
#   (4)base_url 空即错误状态: base_url/api_base 传空或纯空白 -> 400 文案指向填写完整地址, 不再清空后照存
#   (5)三条校验均置于 tree/node 构造与 merge 之前, 失败时配置零改动(满足配置未被修改验收)
#   (6)ValueError 会被 handle_api_errors(=原handle_config_errors) 笼统转 500, 故显式抛 HTTPException(400);
#     不改公共装饰器, 避免波及全项目 24 处调用点(OCP/SRP)
# 2026-09-26 - 小欧 - add_provider 增加 api_base 必填校验(空/纯空白 -> 400, 文案"api_base 必填:
#   API 地址是 Provider 的必要配置"), 置于 _validate_new_provider_name 之后、构造 tree 之前, 失败时配置零改动;
#   前端 ModelModals.tsx 添加 Provider 弹窗同步加 required + 拒纯空白 validator, 前后端双闸。
#   不允许"先建后填" - api_key 才可后填(三态规则), base_url 是必要配置, 与之方向相反 - 小欧 2026-09-26
# 2026-09-26 - 小欧 - fetch_remote_models 错误分类落地: 增 probe_key 参数(测未保存的 key) + 错误分类
#   (1)新增 _classify_remote_result(status_code, network_err): ok / key_invalid(401,403) /
#      endpoint_unsupported(404,405,501) / network_error(超时与连接失败)。**404/405/501 刻意不判 key 无效** ——
#      部分 provider 无 /models 端点, 误判会让用户反复改 key 甚至把正确的 key 改坏(设计既定第3条)
#   (2)_fail 增 status_code / category 两字段, 成功返回亦补 status_code + category:"ok", 调用方据此分两套文案
#   (3)probe_key 仅存内存、只进本次探测的 header: 不落盘、不进日志、不回传响应(设计硬要求)。
#      优先级 probe_key > {NAME}_API_KEY env > YAML —— 用户输入框里新输的 key 才是待验证的那个
#   (4)安全前提已实测(要求先实测): httpx 异常字符串不回显 header、不含 key
#      (DNS 失败/连接拒绝/超时三种均验证), 故 _http_get_remote_models 现有 logger.error(f"拉取失败: {e}") 可保留
#   (5)未动 _http_get_remote_models 与 _parse_remote_models_body(职责单一, 分类在调用层做, 不污染下层) - 小欧 2026-09-26
# 2026-09-26 - 小欧 - 增"查看已保存密钥明文"的只读取数出口
#   审计日志与 env 接管拒绝逻辑在路由层(那里才有 request.client 可取来源 IP) — 小欧 2026-09-26
# 2026-09-26 (三堂会审后修正) - 小欧 - 10 大规范复核, 本文件 2 处已改:
#   ①[KISS-DIRECT + YAGNI] **删除** get_raw_ai_for_plain_read / provider_names_for_plain_read 两个函数。
#     原设计为"只读出口": 供 model_routes 的 GET /providers/{name}/api-key 取 ai 区域原始数据(不掩码)、
#     provider 名判定复用 _provider_names。但实现成了**纯透传壳**——函数体只有 `return _raw_ai()` /
#     `return _provider_names(ai)`, 无任何附加逻辑, 项目铁规明禁:
#     "无透传函数: def f(x): return g(x) 只调一个函数 → 内联, 直接调 g"。
#     原 docstring 自称"防两处口径分叉"并不成立 —— 透传壳取到的仍是底层同一权威, 与直接调完全等价,
#     只是一层无意义跳转(SLAP: API 层不必经 service 中转两次才拿到同一份数据)。真正的防分叉由
#     "两处都调 _raw_ai/_provider_names" 保证, 而非由壳函数保证。
#     调用方 model_routes 已同步改为直接调 svc._raw_ai() / svc._provider_names(ai)。
#   ②[复用优先] fetch_remote_models 的 probe_key 判空改调公用 is_blank_secret(), 删除内联的
#     `isinstance(probe_key, str) and probe_key.strip()`。同一判定写两遍必然漂移: 内联版只覆盖
#     "是字符串"一路, 非字符串类型靠短路侥幸兜住; 一旦 is_blank_secret 后续增补语义, 两处即分叉。
# 2026-09-26 (三堂会审后修正·二) - 小欧 - 上条 ① 的"直接调 svc._raw_ai() / svc._provider_names(ai)"
#   走偏了: 下划线前缀是模块私有约定, API 层直接调 service 私有函数 = 破坏封装/分层(SLAP)。
#   省一层壳却拆了层边界, 是拆东墙补西墙。正确解法不是"零函数", 而是"一个做实事的公开函数":
#   新增 get_provider_raw_entry(name) —— 读 ai 区 + 存在性校验(404)一次做完(含真实分支逻辑,
#   不是透传), 路由层只调它, 不再碰 _raw_ai/_provider_names。公开契约、防分叉、守边界三者兼得。
# 2026-09-26 (三堂会审后修正·三) - 小欧 - update_provider_config 字段落盘改单遍 if/elif 分流：
#   原为两遍遍历 fields + 第二遍 `k not in key_map` 排除重叠键(timeout/max_retries/label 同属
#   key_map 与 PROVIDER_PARAM_TYPES)，两循环互相耦合属隐式契约；单遍后该约束由结构天然承担。
#   行为经 20 万随机组合穷举验证等价(含 v=None/纯空白/非字符串真值/三键重叠)。
#   同时把该决策史由行内迁至本处：api_key 传空串="不修改" ⇒ node 空 ⇒ `if not node:
#   raise ValueError` ⇒ 级别纠正只在中央映射 response_utils.handle_api_errors 做(不在 service
#   层改异常类型, 否则推翻 TDD test_empty_api_key_not_overwrite 固化的"抛错+绝不落盘")。
# 2026-09-27 - 小欧 - 字符串落盘前 strip 补齐：①add_provider 落盘前 strip（api_key/label/api_base，
#   与 update_provider_config 的并行写入路径对齐；label 原未 strip、api_base 校验 strip 判空而落盘原样写，
#   均致 YAML 存脏值——消费端 get_models/resolver/client_sdk 均不 strip）；②update_provider_config
#   其余字符串字段同步 strip，与 api_key 同一口径（DRY：清洗只做一次）。留空仍为"未配置" — 小欧 2026-09-27
# 2026-09-29 - 小欧 - 远程模型元数据透传(北京老陈指令)：原只留 id/owned_by 丢弃远端 100+ 字段，
#   致前端靠 id.includes('-free') 猜免费(实测 OpenRouter 460 个命中 0)。现提升 8 字段并就地降级为
#   声明类型(路由已挂 response_model，错型会 500 整个模型库)；结构判别放宽为 dict/裸数组双路。
#   未动排序与写回契约(仍只落 ID 列表) — 小欧 2026-09-29
# 2026-10-03 - 小欧 - _parse_remote_models_body 增补 free/stability 透传(AMD 实测下发，此前静默丢弃) — 小欧 2026-10-03
# 2026-10-05 22:16:38 - 小欧 - 模型库厂商适配两处(SenseNova 实抓 9 模型 16 字段后改，北京老陈指令)：
#   ①_parse_remote_models_body 增 max_output_length/input_modalities/output_modalities/supported_features
#     并做厂商字段别名归一 —— 同义键层级不一(SenseNova 顶层 vs OpenRouter 嵌 architecture)用
#     {**architecture, **item} 合成单一查找视图(顶层优先)，命名不一走新公用 _first_alias 别名链；
#     逐字段仍就地降级为 DTO 声明类型(错型会 500 掉整个模型库)。既有 10 字段口径未动。
#   ②fetch_remote_models 三级取 key(probe_key→env→config)后，key 空白时 pop 掉 Authorization
#     (基类无条件造空 "Bearer " 畸形头，无鉴权自建端点会 400)；只在调用层摘该头、不动 adapter 基类，
#     避免波及 LLM 主链 7 个走默认基类的 provider — 小欧 2026-10-05
# 2026-10-10 小欧 - DEFAULT_PARAM_OPTIONS 的 reasoning_effort 加 minimal 档：与前端预设表
#   utils/modelUtils.PARAM_PRESETS 同步。本表是 update_model 校验 dp 值域的唯一依据（:_resolve_param_options
#   全局兜底亦取此），两边不同步则存 minimal 报"不支持的配置项值"。fre2e_08 自带列表，不受影响 — 小欧-2026-10-10
# 2026-10-10 小欧 - 中央别名表收敛厂商键名漂移：_KEY_ALIASES + _canon_item 入口归一，
#   _first_alias 退役删除（唯一调用点改直读）；longcat 两变体（context_window/max_output_tokens）首批入表，
#   新厂商只加表行不碰逻辑 — 小欧-2026-10-10
# 2026-10-11 - 小欧 - DeepSeek effort 透传：fetch_remote_models 输出字典补 effort_levels/effort_default
#   (取 item.effort.supported_levels/default_level, 仿 publish_time 同款先抽后填写法; 非 DeepSeek 不返回 → 空列表/None) — 小欧-2026-10-11
# 2026-10-11 - 小欧 - Moonshot 子键兼容：_KEY_ALIASES 加 effort 顶层别名(think_efforts/reasoning_efforts);
#   提取处兼容 valid_efforts/default_effort 子键(or 兜底, 与本文件 params_block.get(m) or {} 同款惯用法) — 小欧-2026-10-11
# 2026-10-11 - 小欧 - Moonshot supports_* 布尔组归并(表上能力/模态列全空)：_merge_supports_modalities
#   (image_in/video_in→input_modalities) + _merge_supports_features(reasoning/dynamic_tools→
#   supported_features 的 reasoning/tools)，与 _merge_capabilities 同模式(True 才追加，去重) — 小欧-2026-10-11
# 2026-10-24 - 小欧 - DEFAULT_PARAM_OPTIONS.reasoning_effort 移除 minimal: OpenAI 官方文档明确
#   "Not all reasoning models support every value"，minimal 是少数派值(agnes-2.5-flash 不认→HTTP 400)，
#   全局兜底只留 low/medium/high 三个所有推理模型都支持的核心值；少数派值走 per-model param_options — 小欧-2026-10-24
# 2026-10-26 18:45:00 - 小欧 - replace_provider_models 增 max_output_length 落 model_meta（与 context_length
#   同策略：isinstance(int) 且非 bool 才写，空值不覆盖已有值）。前端 replaceModels 同步扩展。
# _models_of 增 max_output_length（从 model_meta 读取，供 LLM 调用链设置 max_tokens 上限）— 小欧-2026-10-26
# 2026-10-31 - 小欧 - fetch_remote_models 删本地"空 key 摘 Authorization"实现, 收口到
#   ProviderAdapter.auth_headers 单点: 同一条规则写多处必然漂移, 且探测链与真对话链口径必须一致。 — 小欧 2026-10-31
# 2026-11-01 08:45 - 小欧 - update_model 删除清理失效修复：meta range/param_options 的删键改
#   与 model_params 同一个 None 意向机制（merge 内核 None 分支删叶键+回收空父级）。原裁剪
#   dict 整块回写在叶级归并合并器下只能写存活叶键、删不掉兄弟键（删 max_tokens 后
#   range.max_tokens 残留实证；仅单键清空走空 dict 整块替换侥幸全清），命中判定与 keep 语义
#   不变、仅实际命中才建块 — 小欧-2026-11-01
# 2026-11-01 09:15 - 小欧 - kilo.ai 输出上限提取补充：该厂商把单次输出上限放
#   top_provider.max_completion_tokens 嵌套层，原提取链（顶层键 + output_modalities[*].max_length）
#   两路都够不到此层致模型库「输出上限」列恒空。_extract_max_output_length 增第三优先级兜底：
#   前两路未命中才读 top_provider（对既有厂商零影响，命中顺序不变）— 小欧-2026-11-01
# 2026-11-01 13:25 - 小欧 - 键名全深度统一（北京老陈指令：一个概念一个名字，不允许别名长期存在）：
#   (1)_models_of 下发键 default_params → model_params（与 yaml 真源同名，消掉 API 层翻译）；
#      补下发 context_length（原只透 max_output_length，前端②参数区拿不到厂商声明窗口）；
#   (2)add_model 形参 default_params → model_params；update_model 出参键同名；
#   (3)update_provider_config 删 key_map 的 base_url 与 retry_times 别名（只留 api_base / max_retries），
#      空 URL 400 校验由双键循环收敛为 api_base 单键 — 小欧-2026-11-01
# 2026-11-08 小欧 - 迁移与别名收口: 新增 _migrate_legacy_capabilities(启动一次性迁移, 复用 config_helpers 读写);
#   _KEY_ALIASES 删 no-op 的 capabilities 行(_merge_capabilities 仅服务 zenmux reasoning 特征, 不是模态双读) — 小欧-2026-11-08
# 2026-11-08 小欧 - 模态词汇归一: normalize_modalities(MIME 级/脏值收敛 5 值), 远端解析与落盘同口, 启动迁移既有配置 — 小欧-2026-11-08
# 2026-11-08 小欧 - 媒体传输探测: probe_model_media 实测 image inline/url 并落 model_meta.media, _models_of 下发 — 小欧-2026-11-08
# 2026-11-08 小欧 - 探测结论分级: 只有 200 与 400/415/422 算确定结论, 鉴权/限流/5xx/网络不落库; 图像 token 字段缺失≠0 — 小欧-2026-11-08
# 2026-11-08 小欧 - 探测返回 message 改整句人话(_probe_hint 把取证串译成下一步动作), 状态码不再上界面 — 小欧-2026-11-08
# 2026-11-09 小欧 - 外链腿落库补 url_err(发了请求但厂商抓图失败): 与「地址为空没发」结构化区分, 界面提示不再含糊 — 小欧-2026-11-09
# 2026-11-09 小欧 - network_error 取证串补异常类型名(如 ConnectTimeout), 定位厂商侧120s无响应可读 — 小欧-2026-11-09
# 2026-11-09 小欧 - 探测两腿耗时(ms)+image_tokens 结构化落库(inline_ms/url_ms/inline_tokens/url_tokens), 界面tip按腿显示 — 小欧-2026-11-09
# 2026-11-09 小欧 - 生成验证腿: 新增 probe_model_output, 图腿 t2i/i2i 与视频腿 t2v/i2v 按输出声明实测,
#   分组落 media.generate.{image,video}(一组未取证不连坐另一组); 拒绝状态集上收 generation_client.REJECT_STATUS 单源 - 小欧-2026-11-09
# 2026-11-09 小欧 - 生成验证图源解耦: 图生/视频参考腿改用 generation_client.PROBE_IMAGE_URL,
#   不再借 media.probe_image_url(输入腿素材, 默认 8x8 内联 png 不能当外链图输入) - 小欧-2026-11-09
# 2026-11-09 小欧 - 视频腿改判: 任务 failed 只记未定(厂商侧失败不可归因模型), conclusive 改按「无未定腿」判定 - 小欧-2026-11-09
# 2026-11-09 小欧 - 图像 token 只查输入侧(prompt_tokens_details), 补纯文本基线差值判定:
#   kilo 网关在 completion_tokens_details.image_tokens 恒填 0, 原递归匹配会把能看图的模型判成不支持 - 小欧-2026-11-09
# 2026-11-09 小欧 - 验证回执常驻: 新增 model_meta.<model>.last_probe{media,output} 记上次验证的 at/ok/message,
#   未定结论不写能力但原因可常驻界面; 与 media 分键, 判定链不读它 - 小欧-2026-11-09
# 2026-11-09 小欧 - opencli 网关方言入表(模型库映射缺口, 网关侧零改动): _canon_item 降嵌套 metadata 子对象
#   (模态/上限等空位回填, 顶层优先); 别名表加 max_output 与 cost 行, _numeric_cost_to_pricing 转
#   数值 cost→{prompt,completion}(喂免费判据); effort 兼容 list 形状(reasoning_efforts 数组 +
#   default_reasoning_effort 标量); _merge_supports_features 加 tool_call→tools - 小欧-2026-11-09
# 2026-11-11 小欧 - 输入能力验证泛化三态: probe_model_media 增 kind(image/video/audio);
#   _probe_messages/_probe_once/_media_token_count/_ev_tokens 按 kind 分派 part 形状与 token 键,
#   视频腿=video_url 直传公网素材, 音频腿=下载素材 base64 内联 input_audio(协议无音频 URL part);
#   视频/音频结果落 media.{kind} 子块(深合并不触碰图片腿平铺字段), 素材地址 media.probe_{kind}_url
#   配置覆盖, 缺省用实测择优内置默认(w3school 788KB mp4 / runoob 29KB mp3); 图片腿行为零改动 - 小欧-2026-11-11
# 2026-11-11 小欧 - 勘误: 上条"w3school 788KB mp4"实为 test-videos.co.uk 991KB mp4(实测 w3school GET>30s 超时,
#   已改 test-videos.co.uk 全球 CDN 完整 GET≈3s; 音频 runoob 29KB 正确) — 小欧-2026-11-11
# 2026-11-11 小欧 - _models_of 下发 ref_capability_map 二维投影(contract 生成, DTO 只透传) — 小欧-2026-11-11
# 2026-11-14 小欧 - 投影改名 ref_quality_map: 状态模型正交化后下发 quality 四值(native/text_full/
#   meta_only/link_only), 与装配层 delivery 解耦, 前端按 quality 单表出文案 — 小欧-2026-11-14
  2026-11-14 - 商量 - 视频内联注记(_probe_messages 视频腿): 当前只探 video_url 直传; provider 声明
    支持视频内联(如 Gemini inline_data video/mp4)时补内联探测腿, 待视频功能实现时扩展
"""
import base64
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

# 2026-11-09 小欧 - 生成端点单点（探测腿与 Phase B 真业务共用唯一 HTTP 出口）— 小欧-2026-11-09
# 2026-11-11 小欧: 附件能力二维投影下发(前端徽标只读索引, DTO 只透传)
from app.attachments.contract import ref_quality_map
from app.config import (
    get_config,  # get_models 显示层读 tuning 三层回落 — 小欧 2026-09-22（config_helpers 同层已引，无循环）
)
from app.llm.adapters import get_provider_adapter
from app.logger import logger
from app.services.agent.capability import profile_of
from app.services.generation import generation_client
from app.services.model.config_helpers import (
    _config_mtime,
    get_config_path,
    mask_secret_value,
    merge_nested_patch,
    read_yaml_config,
    write_yaml_config,
)

# 2026-09-26 - 小欧 - 三堂会审后修正(复用优先): 引公用"密钥空白判定"唯一权威
#   app/utils/secret_utils.is_blank_secret —— 本文件内联重写过一版(probe_key 判空)，已改为复用。
from app.utils.secret_utils import is_blank_secret

RESERVED_AI_KEYS = {"provider", "model", "model_ref"}

# v1.1：仅全局兜底默认，不同模型3/4/5个选项走config覆盖，不写死（小欧 2026-09-22）
# 全局兜底只放所有推理模型都支持的核心值；少数派值(none/minimal/xhigh/max)各模型支持不同，
#   放全局会导致切模型时HTTP 400（2026-10-24 实测：agnes-3.0-flash认minimal，agnes-2.5-flash不认）。
#   模型私有值走 per-model param_options 配置 — 小欧-2026-10-24
DEFAULT_PARAM_OPTIONS: Dict[str, List[str]] = {
    "reasoning_effort": ["low", "medium", "high"],
}

# 动态参数元数据表（小欧 2026-09-22）
# 新增 Provider 参数：在此加一行 + config.yaml 对应 provider 加字段，前后端自动适配，不再改前端代码
# （rate_limit 作闭环演示实例保留启用——测试以它验证读-写-存-显四段）
PROVIDER_PARAM_TYPES: Dict[str, Dict[str, Any]] = {
    "timeout":     {"type": "number", "label": "超时(秒)", "min": 1, "default": 60},
    "max_retries": {"type": "number", "label": "重试次数", "min": 0, "default": 3},
    "label":       {"type": "string", "label": "显示名"},
    "rate_limit":  {"type": "number", "label": "速率限制", "min": 0, "default": 0},
}
KNOWN_PROVIDER_KEYS = {"name", "api_base", "api_key", "env", "models", "param_types"}


def _resolve_param_options(ai: Dict[str, Any], provider: str, model: str,
                           params: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, List[str]]:
    """三层解析 param_options（模型级 > provider级 > 全局兜底）并取并集（小欧 2026-09-22）。

    params=该模型 model_params 当前值，meta=该模型 model_meta；并集保证"有选项无默认值"
    时值不丢（config 已配置该项但 meta 未列选项 → 用 server/provider 级选项承接）。
    """
    out: Dict[str, List[str]] = {}
    meta_opts = meta.get("param_options") or {}
    for k in list(params) + [k for k in meta_opts if k not in params]:
        mo = meta_opts.get(k)  # 1.模型级最高
        po = ((ai.get(provider) or {}).get("param_options") or {}).get(k)  # 2.provider级
        go = DEFAULT_PARAM_OPTIONS.get(k)  # 3.全局兜底
        v = mo if mo is not None else (po if po is not None else go)
        if isinstance(v, list) and v:
            out[k] = list(v)
    return out


def _raw_ai() -> Dict[str, Any]:
    raw = read_yaml_config(Path(get_config_path())) or {}
    ai = raw.get("ai", {})
    return ai if isinstance(ai, dict) else {}


def _provider_names(ai: Dict[str, Any]) -> List[str]:
    return [k for k, v in ai.items() if isinstance(v, dict) and k not in RESERVED_AI_KEYS]


def get_current_ref(ai: Dict[str, Any]) -> Dict[str, str]:
    """读当前模型 — 2026-09-21 小欧 v4.20 单源收敛：只读结构化 ai.model_ref（删扁平键 fallback）"""
    ref = ai.get("model_ref")
    if isinstance(ref, dict) and ref.get("provider") and ref.get("model"):
        return {"provider": str(ref["provider"]), "model": str(ref["model"])}
    return {"provider": "", "model": ""}


def _models_of(ai: Dict[str, Any], provider: str) -> List[Dict[str, Any]]:
    p = ai.get(provider, {})
    raw_models = p.get("models") or [] if isinstance(p, dict) else []
    params_block = (p.get("model_params", {}) or {}) if isinstance(p, dict) else {}
    meta_block = (p.get("model_meta", {}) or {}) if isinstance(p, dict) else {}
    out: List[Dict[str, Any]] = []
    for m in raw_models:
        if not isinstance(m, str):
            m = str(m.get("name") or "") if isinstance(m, dict) else str(m)
        if not m or m in [o["name"] for o in out]:
            continue
        meta = (meta_block.get(m) or {}) if isinstance(meta_block, dict) else {}
        params = (params_block.get(m) or {}) if isinstance(params_block, dict) else {}
        out.append({
            "name": m,
            "label": str(meta.get("label") or m),
            # 2026-11-01 小欧 - 键名统一: 下发键 default_params → model_params, 与 yaml 真源同名(消翻译层)
            "model_params": params,
            "range": meta.get("range") or {},
            # 断链修正：capabilities 拆为 input_modalities + output_modalities，各自只读真源
            "input_modalities": meta.get("input_modalities") or [],
            "output_modalities": meta.get("output_modalities") or [],
            "param_options": _resolve_param_options(ai, provider, m, params, meta),
            # 2026-11-01 小欧 - 补下发模型声明窗口: 原只透 max_output_length, 前端②参数区拿不到声明值
            #   (问题2/问题3: 库保存的 context_length 既不下发也无编辑面)
            "context_length": meta.get("context_length"),
            "max_output_length": meta.get("max_output_length"),  # 模型最大输出长度，供 LLM 调用链设置 max_tokens 上限
            "media": meta.get("media") or {},  # 媒体传输探测结果(实测), 供模型库展示 — 小欧-2026-11-08
            # 附件/文件引用质量二维投影(source_kind → content_kind → quality 四值), 前端只读索引 — 小欧-2026-11-14
            "ref_quality_map": ref_quality_map(profile_of(provider, m)),
            # 上次验证回执(含未定结论的原因), 只给界面常驻显示, 不参与能力判定 — 小欧-2026-11-09
            "last_probe": meta.get("last_probe") or {},
        })
    return out


def get_models() -> Dict[str, Any]:
    ai = _raw_ai()
    providers = []
    for name in _provider_names(ai):
        p = ai[name]
        is_env = bool(os.environ.get(f"{name.upper()}_API_KEY"))
        providers.append({"name": name, "label": str(p.get("label") or name),
                          "api_base": str(p.get("api_base") or ""),
                          "api_key": mask_secret_value(p.get("api_key") or ""),
                          "env": is_env,
                          "timeout": p.get('timeout') if p.get('timeout') is not None else get_config().get("tuning.llm_net.read_timeout", 150),  # 显示值=运行时三层回落值（原兜底60≠运行30，显示即真相被打破）
                          "max_retries": p.get('max_retries') if p.get('max_retries') is not None else get_config().get("tuning.llm.stream_max_retries", 3),  # 与 __init__ 三层回落同源
                          "param_types": PROVIDER_PARAM_TYPES,  # 元数据表下发（前端只渲染不定义）
                          **{k: v for k, v in p.items()
                             if k not in KNOWN_PROVIDER_KEYS and isinstance(v, (str, int, float, bool))},  # 动态标量值透传（rate_limit 等新参数零改前端）
                          "models": _models_of(ai, name)})
    return {"providers": providers,
            "current_model_ref": get_current_ref(ai)}


def get_providers() -> List[Dict[str, Any]]:
    return get_models()["providers"]


def _raise_if_env_takeover(name: str) -> None:
    """env 接管守卫：设 {NAME}_API_KEY 的 provider 整行只读（与 settings 页 env 语义对齐，双标准）。"""
    if os.environ.get(f"{name.upper()}_API_KEY"):
        raise ValueError(f"Provider '{name}' 由环境变量 {name.upper()}_API_KEY 接管，只读")


def _raise_if_current_ref_env() -> None:
    """当前模型 env 接管守卫：AI_PROVIDER 命中时切换/删除当前模型只读（settings 页同源语义）。"""
    if os.environ.get("AI_PROVIDER"):
        raise ValueError("当前模型由环境变量 AI_PROVIDER 接管，切换/删除当前模型只读")


def _sync_current(tree: Dict[str, Any], provider: str, model: str) -> None:
    """更新嵌套树（merge_nested_patch）中的当前模型 — 2026-09-21 小欧 v4.20 单源收敛：只写 ai.model_ref（删扁平双写）。"""
    ai = tree.setdefault("ai", {})
    if provider and model:
        ai["model_ref"] = {"provider": provider, "model": model}


def add_model(provider: str, model: str, label: str = "",
              model_params: Optional[Dict[str, Any]] = None,
              range_: Optional[Dict[str, Any]] = None,
              input_modalities: Optional[List[str]] = None,
              output_modalities: Optional[List[str]] = None,
              param_options: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
    # 2026-11-01 小欧 - 形参键名统一 default_params → model_params(与前端口径/POST DTO 同名) - 小欧-2026-11-01
    ai = _raw_ai()
    if provider not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {provider}")
    _raise_if_env_takeover(provider)
    if not model:
        raise ValueError("模型名不能为空")
    if any(m["name"] == model for m in _models_of(ai, provider)):
        raise ValueError("同名模型已存在")
    # 与 update_model 同规则：选项表须为非空 string[]，值须在表内，0 直接 400（小欧 2026-09-22）
    allowed = dict(param_options or {})
    for k, vs in allowed.items():
        if not isinstance(vs, list) or not vs or not all(isinstance(x, str) for x in vs):
            raise ValueError(f"不支持的选项表: {k}须为非空string[]")
    for k, v in (model_params or {}).items():
        allow = allowed.get(k, DEFAULT_PARAM_OPTIONS.get(k))
        if allow is not None and v not in allow:
            raise ValueError(f"不支持的配置项值: {k}={v!r}，允许{allow}")
    models = list(ai[provider].get("models", []) or [])
    if not all(isinstance(m, str) for m in models):
        models = [_m["name"] for _m in _models_of(ai, provider)]
    models.append(model)
    tree: Dict[str, Any] = {
        "ai": {provider: {
            "models": models,
            "model_params": {model: model_params or {}},
            "model_meta": {model: {
                "label": label or model,
                "range": range_ or {},
                # 断链修正：capabilities 拆为 input/output 双维度
                "input_modalities": input_modalities or [],
                "output_modalities": output_modalities or [],
                **({"param_options": param_options} if param_options else {}),
            }},
        }}
    }
    merge_nested_patch(tree, scope="model")
    return {**get_models(), "ok": True, "mtime": _config_mtime()}


def update_model(provider: str, model: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    ai = _raw_ai()
    if not any(m["name"] == model for m in _models_of(ai, provider)):
        raise ValueError(f"模型不存在: {provider}/{model}")
    _raise_if_env_takeover(provider)
    # 白名单放行+落model_meta（小欧 2026-09-22：加 param_options，否则送了即报不支持的配置项）
    # 2026-09-24 小欧：加 remove_params（键级删除，与 model_params merge 叠加）— 小欧-2026-09-24
    # 2026-11-01 小欧 - 键名统一: default_params → model_params(与 yaml 真源同名) - 小欧-2026-11-01
    # 2026-11-08 小欧: 模态字段 capabilities → input_modalities + output_modalities
    unknown = set(fields) - {"label", "range", "input_modalities", "output_modalities", "model_params", "param_options", "remove_params"}
    if unknown:
        raise ValueError(f"不支持的配置项: {sorted(unknown)}")
    tree: Dict[str, Any] = {"ai": {provider: {}}}
    node = tree["ai"][provider]
    for k in ("label", "range", "input_modalities", "output_modalities"):
        if fields.get(k) is not None:
            node.setdefault("model_meta", {}).setdefault(model, {})[k] = fields[k]
    mp = fields.get("model_params")
    # v1.6：先合并本次新选项再校验，避免同批改选项+改值时用旧单子误杀（小欧 2026-09-22）
    cur = next((x for x in _models_of(ai, provider) if x["name"] == model), None) or {}
    allowed = dict(cur.get("param_options") or {})
    if isinstance(fields.get("param_options"), dict):
        for k, v in fields["param_options"].items():
            if isinstance(v, list) and v:
                allowed[k] = list(v)
    if isinstance(mp, dict):
        for k, v in mp.items():
            if k in allowed and v not in allowed[k]:
                raise ValueError(f"不支持的配置项值: {k}={v!r}，允许{allowed[k]}")
    # 2026-09-24 小欧：remove_params 键级删除——拷贝当前 model_params 删键得 new_params；
    #   三堂会审修复：①移除本段原无条件 setdefault model_meta（原 remove
    #   必建空块、YAML 落 model_meta.{model}:{} 污染）；②range/param_options 清理挪到下方
    #   fields 写入完成之后统一做（remove 删除意图最终生效，防同批 param_options 覆盖复活；
    #   且跳过 default_params 重加键 keep——remove+dp 同批恢复值时其 meta 保留）；③双份
    #   range/options 清理收敛 for meta_key 循环（DRY）；④remove 全为不存在键且 meta 无命中时
    #   不再空写盘（幂等 no-op 成功返回）— 小欧-2026-09-24
    removed = fields.get("remove_params")
    orig_params = ai[provider].get("model_params", {}).get(model, {}) or {}
    new_params: Optional[Dict[str, Any]] = None
    removed_hit = False
    if isinstance(removed, list) and removed:
        removed_hit = any(k in orig_params for k in removed)
        new_params = dict(orig_params)
        for k in removed:
            new_params.pop(k, None)
    if isinstance(mp, dict):
        if mp:
            if new_params is None:
                new_params = dict(orig_params)
            new_params.update(mp)
        else:
            # 2026-09-21 小欧 修复：空 model_params 提交 = 显式清空模型参数块（原实现走
            # isinstance 且为空跳过 → node 空 → "无有效配置项" 500）。merge_nested_patch
            # 支持空 dict 叶值直接落 YAML 空块，validate 侧 parseInt 兼容。
            new_params = {}
    # 仅 remove 真命中或 model_params 有变更才写 model_params（全 miss 不空写）
    # 2026-09-25 小欧 修复删除意图丢失复发（守护测试 verify_bz_remove_params_guard 实证）：
    #   _iter_nested_ops 把非空 dict 递归展平为叶键写（无整块替换语义），直接落 new_params 块会丢删键意图
    #   → temperature 残留。改显式 None 删键意向（_set_nested_path 原生删键），保留 mp/keep 语义。
    if new_params is not None and (removed_hit or isinstance(mp, dict)):
        pn = node.setdefault("model_params", {})
        pn[model] = new_params
        if removed_hit:
            for k in removed:
                if k not in new_params:
                    pn[model][k] = None  # None=删键（被 dp 恢复的键已原位保留）
    # 选项表落 model_meta（小欧 2026-09-22）
    if isinstance(fields.get("param_options"), dict):
        node.setdefault("model_meta", {}).setdefault(model, {})["param_options"] = fields["param_options"]
    # remove 同步清 range/param_options——在 fields 写入之后执行（删除意图最终
    #   生效，防 293 行同批 param_options 覆盖复活）；删键改用与 model_params 同一个 None
    #   意向机制（merge 内核 None 分支：删叶键+回收空父级）。原裁剪 dict 整块回写在本合并器
    #   叶级归并语义下只能写存活叶键、删不掉兄弟键（删 max_tokens 后 range.max_tokens 残留实证；
    #   仅单键清空走空 dict 整块替换侥幸全清）；跳过 model_params 重加键（keep）；
    #   仅实际命中才 setdefault 建 model_meta 块（防空块污染）—— 小欧-2026-11-01
    if isinstance(removed, list) and removed:
        keep = set(mp) if isinstance(mp, dict) else set()
        base_meta = (ai[provider].get("model_meta", {}) or {}).get(model, {}) or {}
        node_meta = node.get("model_meta", {}).get(model)
        for meta_key in ("range", "param_options"):
            meta_src = dict((node_meta or {}).get(meta_key) or base_meta.get(meta_key) or {})
            for k in removed:
                if k in keep or k not in meta_src:
                    continue
                meta_write = node.setdefault("model_meta", {}).setdefault(model, {})
                meta_write.setdefault(meta_key, {})[k] = None  # None=删键意图
    if not node:
        # remove_params 全为不存在键 = 幂等 no-op，成功返回不写盘（原仍全量 merge，
        #   空耗备份/原子重写/mtime 抖动）；其余无有效配置项仍拒
        if isinstance(removed, list) and removed:
            return {"ok": True, "model": model, "mtime": _config_mtime()}
        raise ValueError("无有效配置项")
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "model": model, "mtime": _config_mtime()}


def delete_model(provider: str, model: str) -> Dict[str, Any]:
    ai = _raw_ai()
    if provider not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {provider}")
    _raise_if_env_takeover(provider)
    models = [m for m in (ai.get(provider, {}).get("models") or [])
              if (m if isinstance(m, str) else m.get("name")) != model]
    tree: Dict[str, Any] = {
        "ai": {provider: {
            "models": models,
            "model_params": {model: None},
            "model_meta": {model: None},
        }}
    }
    switched_to = None
    cur = get_current_ref(ai)
    if cur["provider"] == provider and cur["model"] == model:
        _raise_if_current_ref_env()
        names = [m for m in models if isinstance(m, str)] or \
                [(_m["name"]) for _m in _models_of(ai, provider) if _m["name"] in models]
        if names:
            _sync_current(tree, provider, names[0])
            switched_to = names[0]
        else:
            rest = [n for n in _provider_names(ai) if n != provider]
            target_p, target_m = "", ""
            for n in rest:
                ms = _models_of(ai, n)
                if ms:
                    target_p, target_m = n, ms[0]["name"]
                    break
            if not target_p:
                raise ValueError("禁止删除最后一个可用模型（无其它 Provider 可回退）")
            _sync_current(tree, target_p, target_m)
            switched_to = target_m or None
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "switched_to": switched_to, "mtime": _config_mtime()}


def _validate_new_provider_name(name: str, ai: Dict[str, Any]) -> None:
    """新 Provider 名校验：非空、非保留键（provider/model/model_ref，撞车会覆盖 ai 元数据损坏）、不重名。"""
    if not name:
        raise ValueError("Provider 名不能为空")
    if name in RESERVED_AI_KEYS:
        raise ValueError(f"Provider 名 '{name}' 为保留键(provider/model/model_ref)，不可用作 Provider 名")
    if name in _provider_names(ai):
        raise ValueError("同名 Provider 已存在")


def add_provider(name: str, label: str = "", api_base: str = "",
                 api_key: str = "", model: str = "", timeout: int = 60,
                 models: Optional[List[str]] = None,
                 max_retries: int = 3) -> Dict[str, Any]:
    ai = _raw_ai()
    _validate_new_provider_name(name, ai)
    # api_base 必填校验 - 小欧 - 2026-09-26: 空/纯空白 → 400。
    # URL 是 Provider 的必要配置，无地址即无法调用；不允许"先建后填"（与 api_key 的"留空=保持原值"方向相反）。
    if not str(api_base or "").strip():
        raise HTTPException(status_code=400, detail="api_base 必填：API 地址是 Provider 的必要配置")
    ms = list(models or [])
    if model and model not in ms:
        ms.append(model)
    # 2026-09-27 - 小欧 - 第二条写入路径补 strip：api_key 落盘前 strip。
    #   add_provider 与 update_provider_config 是**两条并行的 api_key 落盘路径**，另一条已覆盖
    #   （`cleaned = str(v).strip()`），本函数原样落盘 ⇒ 界面新建 Provider 粘贴带空格的 key
    #   会把脏值写进 YAML。危害不在"当下调用失败"（消费端 service.py:220 / client_sdk:288 /
    #   model_routes:248 各有一道 strip 兜底），而在**脏值长期潜伏**：YAML 里存的是带空格的 key，
    #   任何新增消费端漏 strip 即 401，且界面无从提示病因（用户会反复重输同一串正确 key）。
    #   留空仍为"未配置"（str 化同时兜住 None/数字等非字符串，与 :458 的 api_base 校验同款）。
    tree: Dict[str, Any] = {"ai": {name: {
        "name": name,
        "label": str(label or name).strip(),
        # 2026-09-27 - 小欧 - api_base 与 label 一并 strip（与 update_provider_config 同一口径）：
        #   校验时用 .strip() 判非空，落盘却原样写，两者不一致 ⇒ YAML 存脏值。
        #   消费端 get_models(:232) / resolver(:274) / client_sdk(:296) 均不 strip，
        #   带空格的 api_base 会让 httpx 拿到 " https://x/v1 " 而真实请求失败。
        "api_base": str(api_base).strip(),
        "api_key": str(api_key or "").strip(),
        "timeout": timeout, "max_retries": max_retries, "models": ms}}}
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "provider": name, "mtime": _config_mtime()}


def update_provider_config(name: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    ai = _raw_ai()
    if name not in _provider_names(ai):
        raise ValueError(f"Provider 不存在: {name}")
    _raise_if_env_takeover(name)
    # 2026-11-01 小欧 - 键名统一: 删 base_url 别名(统一 api_base) 与 retry_times 别名(统一 max_retries)
    #   项目铁律禁止 backward 兼容层, 别名长期存在=每次保存都要翻译一遍, 且两侧 strip 口径漂移过(2026-09-27)
    key_map = {"api_key": "api_key", "api_base": "api_base",
               "timeout": "timeout", "max_retries": "max_retries",
               "label": "label", "param_options": "param_options"}
    # 字段白名单：仅 key_map + PROVIDER_PARAM_TYPES + clear（清空标记）内字段可落盘，其余拒（防任意键注入）
    if isinstance(fields, dict):
        unknown_key = next(
            (k for k in fields if k not in set(key_map) and k not in PROVIDER_PARAM_TYPES
             and k != "clear"), None
        )
        if unknown_key:
            raise ValueError(f"不支持的Provider配置项: {unknown_key}")
    # 三条契约在本函数一次落地（同函数禁止拆两次改）：
    #   api_key 三态：字段不出现/None/空串/纯空白 = 不修改（跳过不写）；非空 strip 后写入
    #   clear 与设置值互斥：clear=true 且 api_key 非空 → 400，不静默丢弃任何一方
    #   api_base 空即错误状态：空/纯空白 → 400，不再"清空后照存"
    # ValueError 会被 handle_api_errors(=原handle_config_errors) 笼统转 500，故此处显式抛 400 HTTPException
    if fields.get("clear") is True and str(fields.get("api_key") or "").strip():
        raise HTTPException(status_code=400,
                            detail="clear=true 与 api_key 设置值不能同时提交：请只提交其中一项")
    # 2026-11-01 小欧 - 单键判定(原双键 base_url/api_base 循环): 别名已删, 只校验 api_base
    if "api_base" in fields and fields.get("api_base") is not None \
            and not str(fields.get("api_base")).strip():
        raise HTTPException(
            status_code=400,
            detail="api_base 为空：URL 是 Provider 的必要配置，无法调用，请填写完整地址")
    tree: Dict[str, Any] = {"ai": {name: {}}}
    node = tree["ai"][name]
    # 2026-09-26 - 小欧 - 单遍 if/elif 分流（原两遍遍历+`k not in key_map` 排除重叠三键），
    #   行为经 20 万组合验证等价。None 短路须在 `k in key_map` 内层：否则 label=None 会落入
    #   动态参数分支被写入（原语义是不写）。详见文件头「三堂会审后修正·三」
    for k, v in fields.items():
        if k in key_map:
            if v is not None:
                if k == "api_key":
                    # api_key 三态：空/纯空白视为"不修改"跳过；非空 strip 后落盘
                    cleaned = str(v).strip()
                    if cleaned:
                        node["api_key"] = cleaned
                else:
                    # 2026-09-27 - 小欧 - 其余字符串字段（label / api_base）同样 strip 后落盘，
                    # 与 api_key 同一口径（DRY：清洗只做一次，不靠调用方自觉）
                    node[key_map[k]] = v.strip() if isinstance(v, str) else v
        elif k in PROVIDER_PARAM_TYPES:
            node[k] = v   # 动态参数直写 ai.{provider}.{k}（到此处必不在 key_map）
    if fields.get("clear") is True:
        node["api_key"] = ""
    # api_key 传空串="不修改" ⇒ 上面全部跳过 ⇒ node 空。保持 ValueError 不在本层改类型
    # （TDD test_empty_api_key_not_overwrite 固化"抛错+绝不落盘"），级别纠正由中央映射统一做。
    if not node:
        raise ValueError("没有有效字段")
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "provider": name, "mtime": _config_mtime()}


def delete_provider(name: str) -> Dict[str, Any]:
    ai = _raw_ai()
    names = _provider_names(ai)
    if name not in names:
        raise ValueError(f"Provider 不存在: {name}")
    if len(names) <= 1:
        raise ValueError("禁止删除最后一个 Provider（需至少保留一个可用模型）")
    _raise_if_env_takeover(name)
    tree: Dict[str, Any] = {"ai": {name: None}}
    switched_to = None
    cur = get_current_ref(ai)
    if cur["provider"] == name:
        _raise_if_current_ref_env()
        rest = [n for n in names if n != name]
        target_p, target_m = "", ""
        for n in rest:  # 2026-09-21 小欧 修 M10/M11：扫第一个有可用模型的 provider，不止取 rest[0]
            ms = _models_of(ai, n)
            if ms:
                target_p, target_m = n, ms[0]["name"]
                break
        if not target_p:
            raise ValueError("禁止删除最后一个 Provider（其余 Provider 均无可用模型）")
        _sync_current(tree, target_p, target_m)
        switched_to = target_p or None
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "switched_to": switched_to, "mtime": _config_mtime()}


def _require_provider_for_fetch(name: str, ai: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """拉取前置校验层：provider 存在性 + api_base 非空，返回 (p, api_base) — 小欧 2026-09-24"""
    if name not in _provider_names(ai):
        raise HTTPException(status_code=404, detail=f"Provider {name} 不存在")
    p = ai[name]  # _provider_names 已保证 isinstance(ai[name], dict)
    api_base = str(p.get("api_base") or "").strip()
    if not api_base:
        raise HTTPException(status_code=400, detail="该 Provider 未配置 api_base，请先到模型 Tab → ③ Provider 配置填写")
    return p, api_base


async def _http_get_remote_models(api_base: str, headers: Dict[str, str]) -> Tuple[Any, Optional[str]]:
    """HTTP 拉取层 → (resp, err)；网络异常统一 err 文案 — 小欧 2026-09-24"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{api_base.rstrip('/')}/models", headers=headers)
    except Exception as e:
        logger.error(f"拉取远程模型失败: {e}")
        return None, f"拉取失败: {e}"
    return resp, None


def _str_list(value: Any) -> List[str]:
    """把远端值收敛为 List[str]——非数组退空列表、非字符串成员丢弃（防错型打挂 DTO）— 小欧 2026-10-05

    抽成公用函数是为消 DRY 重复：supported_parameters 原有内联写法与新增的 modalities/features
    三处同一逻辑，且每处都必须同步 isinstance 双重校验，漏一处即在 response_model 上 500 掉整个模型库。
    """
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []


def _flatten_pricings(pricings: Any) -> Dict[str, str]:
    """zenmux 式 pricings（复数嵌套）拍平 → {prompt/completion/…: str} — 小欧 2026-10-10

    形状: {"prompt": [{"value": 0.1, "unit": "perMTokens", "currency": "USD"}], …}。
    只取 unit == perMTokens 的首项值转 str；perCount（如 web_search 按次）跳过——
    免费判据 prompt === "0" && completion === "0" 只认 token 计费，不许按次项污染。
    bool 需排除（isinstance(True, int) 为真）；非标形状退 {}。
    """
    flat: Dict[str, str] = {}
    if not isinstance(pricings, dict):
        return flat
    for k, v in pricings.items():
        if not isinstance(k, str) or not isinstance(v, list):
            continue
        for e in v:
            if (isinstance(e, dict) and e.get("unit") == "perMTokens"
                    and isinstance(e.get("value"), (int, float))
                    and not isinstance(e.get("value"), bool)):
                flat[k] = str(e["value"])
                break
    return flat


def _numeric_cost_to_pricing(pricing: Any) -> Dict[str, str]:
    """OpenCode 网关 cost{input,output:每百万token数值} → {prompt,completion}字符串 — 小欧 2026-11-09

    仅认数值型 input/output 双键（bool 排除）；其余形状退空 dict，调用方保留原值不动。
    转出后免费判据 prompt=completion="0" 对 opencli 免费模型自然生效。
    """
    if not isinstance(pricing, dict) or "prompt" in pricing:
        return {}
    ci, co = pricing.get("input"), pricing.get("output")
    if isinstance(ci, (int, float)) and not isinstance(ci, bool) \
            and isinstance(co, (int, float)) and not isinstance(co, bool):
        return {"prompt": str(ci), "completion": str(co)}
    return {}


def _merge_capabilities(feats: List[str], capabilities: Any) -> List[str]:
    """capabilities:{reasoning:bool} 对象并入 supported_features（去重）— 小欧 2026-10-10

    zenmux 把推理能力放在 capabilities.reasoning 布尔上，而非 supported_features 列表；
    不认则推理模型标不出来。True 才追加；其它键原样忽略（不猜语义）。
    """
    if isinstance(capabilities, dict) and capabilities.get("reasoning") is True \
            and "reasoning" not in feats:
        return [*feats, "reasoning"]
    return feats


def _merge_capabilities_into_modalities(modalities: List[str], capabilities: Any) -> List[str]:
    """老格式 capabilities 列表并入 input_modalities（迁移用, 一次性）

    agnes/ZenFree 老写法: capabilities:['text','image'] → 并进 input_modalities(去重)。
    仅作"把已判定为 input 的值补充进 input"的兜底, 不承载 input/output 方向判定
    (生图/生视频的方向由手工标注表定, 见 _migrate_legacy_capabilities)。
    """
    out = list(modalities)
    if isinstance(capabilities, list):
        for v in capabilities:
            if isinstance(v, str) and v not in out:
                out.append(v)
    return out


def _migrate_legacy_capabilities(config_path: Path) -> bool:
    """老 capabilities 一次性并入 input 维度、显式建 output 维度并删旧键；幂等，无残留时零改动 — 小欧-2026-11-08"""
    raw = read_yaml_config(config_path) or {}
    ai = raw.get("ai") or {}
    changed = False
    for p in (ai.values() if isinstance(ai, dict) else []):
        meta = p.get("model_meta") if isinstance(p, dict) else None
        if not isinstance(meta, dict):
            continue
        for m in meta.values():
            if not isinstance(m, dict) or "capabilities" not in m:
                continue
            legacy = m.pop("capabilities")
            m["input_modalities"] = _merge_capabilities_into_modalities(
                m.get("input_modalities") or [], legacy)
            m.setdefault("output_modalities", [])
            changed = True
    if changed:
        write_yaml_config(str(config_path), raw)
        logger.info(f"[model] 老 capabilities 已迁移为 input/output 双维度: {config_path}")
    return changed


def _normalize_config_modalities(config_path: Path) -> bool:
    """既有 model_meta 模态词汇一次性归一(幂等, 无脏值时零改动) — 小欧-2026-11-08"""
    raw = read_yaml_config(config_path) or {}
    ai = raw.get("ai") or {}
    changed = False
    for p in (ai.values() if isinstance(ai, dict) else []):
        meta = p.get("model_meta") if isinstance(p, dict) else None
        if not isinstance(meta, dict):
            continue
        for m in meta.values():
            if not isinstance(m, dict):
                continue
            for key in ("input_modalities", "output_modalities"):
                cur = m.get(key)
                if not isinstance(cur, list):
                    continue
                norm = normalize_modalities(cur)
                if norm != cur:
                    m[key] = norm
                    changed = True
    if changed:
        write_yaml_config(str(config_path), raw)
        logger.info(f"[model] 模态词汇已归一(image/*→image, pdf→file): {config_path}")
    return changed


def migrate_legacy_capabilities() -> bool:
    """startup 迁移入口(只迁真实配置): 老 capabilities 并维 + 模态词汇归一；模板文件运行期不写。"""
    path = Path(get_config_path())
    changed = _migrate_legacy_capabilities(path)
    vocab = _normalize_config_modalities(path)
    return changed or vocab


def _merge_supports_modalities(modalities: List[str], item: Any) -> List[str]:
    """Moonshot supports_image_in/video_in 布尔并入 input_modalities（去重）— 小欧 2026-10-11

    Moonshot 把输入模态放在顶层布尔上，而非 input_modalities 列表；
    不认则表上"输入模态"列与图片/视频筛选全空。True 才追加；其它键原样忽略（不猜语义）。
    """
    out = list(modalities)
    for flag, value in (("supports_image_in", "image"), ("supports_video_in", "video")):
        if isinstance(item, dict) and item.get(flag) is True and value not in out:
            out.append(value)
    return out


def _merge_supports_features(feats: List[str], item: Any) -> List[str]:
    """Moonshot supports_reasoning/dynamic_tools、OpenCode tool_call 布尔并入 supported_features（去重）— 小欧 2026-10-11

    reasoning→'reasoning'；dynamic_tools/tool_call→'tools'（动态工具调用即挂工具能力，
    与 supported_features 现有 'tools' 同语义，见 DTO 注释"直接决定能不能挂工具"）。
    True 才追加；其它键原样忽略。
    """
    out = list(feats)
    for flag, value in (("supports_reasoning", "reasoning"), ("supports_dynamic_tools", "tools"), ("tool_call", "tools")):
        if isinstance(item, dict) and item.get(flag) is True and value not in out:
            out.append(value)
    return out


# 远端模型键名中央别名表 — 小欧 2026-10-10：
#   OpenAI /models 无 schema 标准，各厂商同义键各叫各的名（name/display_name、
#   pricing/pricings、context_length/context_window、max_output_length/max_output_tokens、
#   supported_parameters/supported_sampling_parameters），散写 if 越补越多。
#   收敛：解析入口 _canon_item 先把键名归一，后面逻辑只认 canonical 键；
#   新厂商只加表行，不碰逻辑。顺序即优先级（同命中取首个非 None）。
_KEY_ALIASES = {
    "id": ["id", "model"],
    "owned_by": ["owned_by"],
    "name": ["name", "display_name", "title"],
    "description": ["description"],
    "context_length": ["context_length", "context_window"],
    "max_output_length": ["max_output_length", "max_output_tokens", "max_output"],
    "pricing": ["pricing", "pricings", "cost"],
    "architecture": ["architecture"],
    "input_modalities": ["input_modalities"],
    "output_modalities": ["output_modalities"],
    "supported_parameters": ["supported_parameters", "supported_sampling_parameters"],
    "supported_features": ["supported_features"],
    # 2026-11-08 小欧: 删 `capabilities` 行(identity 别名, 模态只认 input/output; zenmux reasoning 仍由 _merge_capabilities 直读原键)
  "free": ["free"],
  "stability": ["stability"],
  "publish_time": ["publish_time"],
  # 2026-10-11 小欧 - effort 顶层别名：DeepSeek 用 effort，Moonshot 用 think_efforts
  #   与 reasoning_efforts（k3 上两者并存且内容一致，先命中者胜）。
  #   子键差异（supported_levels/default_level vs valid_efforts/default_effort）
  #   在提取处兼容，见下 effort 透传注释 — 小欧-2026-10-11
  "effort": ["effort", "think_efforts", "reasoning_efforts"],
  }


def _canon_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """单条模型键名归一：别名落到 canonical 键，原键保留（merged 合成视图与下游直读不受影响）。"""
    out = dict(item)
    for canon, aliases in _KEY_ALIASES.items():
        for key in aliases:
            value = item.get(key)
            if value is not None:
                out[canon] = value
                break
    # metadata 子对象降嵌套(OpenCode 网关方言): 模态等仅存于 metadata, 顶层优先空位回填 — 小欧-2026-11-09
    meta = out.get("metadata")
    if isinstance(meta, dict):
        for k, v in meta.items():
            if out.get(k) is None:
                out[k] = v
    return out


# 模态词汇归一表: 远端存在 MIME 级值(image/jpeg、application/pdf)与历史脏值 pdf — 小欧-2026-11-08
_MODALITY_PREFIX = (("image/", "image"), ("audio/", "audio"), ("video/", "video"), ("text/", "text"))
_MODALITY_ALIAS = {"pdf": "file", "application/pdf": "file"}


def normalize_modalities(values: Any) -> List[str]:
    """模态词归一: MIME 级值与脏值收敛到 {text,image,audio,video,file}, 未知值保序保留不丢能力。"""
    out: List[str] = []
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, str):
            continue
        s = v.strip()
        if not s:
            continue
        low = s.lower()
        canon = _MODALITY_ALIAS.get(low)
        if canon is None:
            canon = next((c for pfx, c in _MODALITY_PREFIX if low.startswith(pfx)), s)
        if canon not in out:
            out.append(canon)
    return out


def _extract_modalities(modalities: Any) -> List[str]:
    """Intern InkStone 式嵌套模态拍平：[{'type':'text', ...}] → ['text']，并归一词汇。"""
    out: List[str] = []
    if not isinstance(modalities, list):
        return out
    for entry in modalities:
        if isinstance(entry, str):
            if entry not in out:
                out.append(entry)
        elif isinstance(entry, dict):
            t = entry.get("type")
            if isinstance(t, str) and t not in out:
                out.append(t)
    return normalize_modalities(out)


def _extract_context_length(item: Dict[str, Any]) -> Optional[int]:
    """Intern InkStone 上下文长度提取：优先顶层，其次 input_modalities[*].supported_inputs.max_context_length.value。"""
    ctx = item.get("context_length")
    if isinstance(ctx, int) and not isinstance(ctx, bool):
        return ctx
    for entry in item.get("input_modalities") or []:
        if not isinstance(entry, dict):
            continue
        supported = entry.get("supported_inputs")
        if not isinstance(supported, dict):
            continue
        node = supported.get("max_context_length")
        if isinstance(node, dict):
            val = node.get("value")
            if isinstance(val, int) and not isinstance(val, bool):
                return val
    return None


def _extract_max_output_length(item: Dict[str, Any]) -> Optional[int]:
    """Intern InkStone 输出上限提取：优先顶层，其次 output_modalities[*].max_length.value。"""
    max_out = item.get("max_output_length")
    if isinstance(max_out, int) and not isinstance(max_out, bool):
        return max_out
    for entry in item.get("output_modalities") or []:
        if not isinstance(entry, dict):
            continue
        node = entry.get("max_length")
        if isinstance(node, dict):
            val = node.get("value")
            if isinstance(val, int) and not isinstance(val, bool):
                return val
    # 2026-11-01 小欧 - kilo.ai 第三优先级兜底：该厂商把单次输出上限藏
    #   top_provider.max_completion_tokens，前两路都够不到 → 「输出上限」列恒空。
    #   前两路未命中才读此层，既有厂商（值在顶层或 output_modalities）命中顺序不变 — 小欧-2026-11-01
    _top = item.get("top_provider")
    if isinstance(_top, dict):
        _val = _top.get("max_completion_tokens")
        if isinstance(_val, int) and not isinstance(_val, bool):
            return _val
    return None


def _extract_supported_parameters(item: Dict[str, Any]) -> List[str]:
    """Intern InkStone 参数名提取：从 output_modalities[*].supported_parameters 的键名归一。"""
    out: List[str] = []
    for entry in item.get("output_modalities") or []:
        if not isinstance(entry, dict):
            continue
        params = entry.get("supported_parameters")
        if isinstance(params, dict):
            for key in params.keys():
                if isinstance(key, str) and key not in out:
                    out.append(key)
    return out


def _parse_remote_models_body(resp: Any) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """响应解析层 → (models, err)；HTTP>=400/非JSON/非数组 → err — 小欧 2026-09-24"""
    if resp.status_code >= 400:
        message = f"HTTP {resp.status_code}"
        try:
            body = resp.json()
            if isinstance(body, dict):
                err = body.get("error")
                if isinstance(err, dict) and err.get("message"):
                    message = str(err["message"])
                elif body.get("message"):
                    message = str(body["message"])
        except Exception:
            pass
        return None, message
    try:
        body = resp.json()
    except Exception as e:
        return None, f"响应解析失败: {e}"
    # 2026-09-29 小欧 - 兼容裸数组(防御性放宽, 本仓 provider 实测均为 dict+data 规范)
    if isinstance(body, dict):
        data = body.get("data")
        if not isinstance(data, list):
            return None, "远端返回结构异常（data 非数组）"
    elif isinstance(body, list):
        data = body
    else:
        return None, "远端返回结构异常"
    models: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # 2026-10-10 小欧 - 键名先归一（_canon_item）：id/model、name/display_name 等别名在此收敛，
        #   后面只认 canonical 键；_first_alias 别名链退役（唯一调用点已改直读，函数删除，见下方）。
        item = _canon_item(item)
        mid = item.get("id")
        if not mid:
            continue
        # 2026-09-29 小欧 - 元数据透传(北京老陈指令): 提升表格/筛选要用的 8 字段。
        #   7 字段就地降级为 DTO 声明类型: 路由已挂 response_model，错型会 500 掉整个模型库。
        #   非字符串不转 str(会产出 "{'x': 1}" 伪值)；bool 需排除(isinstance(True,int) 为真)。
        owned_by, name, desc = item.get("owned_by"), item.get("name"), item.get("description")
        pricing, architecture = item.get("pricing"), item.get("architecture")
        # 2026-10-10 小欧 - pricing 形状分流（键名已由 _canon_item 归一）：老厂商扁平 dict 原样用；
        #   zenmux 式复数嵌套才走 _flatten_pricings 拍平（只取 perMTokens，perCount 跳过）。
        if isinstance(pricing, dict) and any(isinstance(v, list) for v in pricing.values()):
            pricing = _flatten_pricings(pricing)
        else:
            # OpenCode 网关 cost 数值方言在此转换, 其余形状原样保留 — 小欧-2026-11-09
            pricing = _numeric_cost_to_pricing(pricing) or pricing
        free, stability = item.get("free"), item.get("stability")
        arch = architecture if isinstance(architecture, dict) else {}
        # 2026-10-05 22:16:38 - 小欧 - 厂商字段别名归一（SenseNova 实抓 9 模型 16 字段后补，丢弃 11 个）：
        #   ①层级不统一（SenseNova 顶层 input_modalities / OpenRouter 嵌 architecture）
        #     → {**arch, **item} 合成单一查找视图，顶层优先、嵌套兜底，替掉按厂商写if 分支（KISS-DIRECT）。
        #   ②命名不统一（同义键多名）→ 2026-10-10 起走入口 _canon_item 中央别名表（_first_alias 已退役删除）。
        merged = {**arch, **item}
        # Intern InkStone 嵌套结构：上下文/输出上限/参数名都藏在模态对象里，先归一再进 DTO。
        ctx = _extract_context_length(item)
        max_out = _extract_max_output_length(item)
        input_modalities = _merge_supports_modalities(_extract_modalities(merged.get("input_modalities")), item)
        output_modalities = _extract_modalities(merged.get("output_modalities"))
        supported_parameters = _extract_supported_parameters(item)
        if not supported_parameters:
            supported_parameters = _str_list(item.get("supported_parameters"))
        _pub = item.get("publish_time")
        _eff = item.get("effort")
        if isinstance(_eff, dict):  # DeepSeek/Moonshot dict 形状
            _eff_levels = _eff.get("supported_levels") or _eff.get("valid_efforts")
            _eff_d = _eff.get("default_level") or _eff.get("default_effort")
        else:  # OpenCode 网关 list 形状: reasoning_efforts 数组 + default_reasoning_effort 标量
            _eff_levels = _eff if isinstance(_eff, list) else []
            _eff_d = item.get("default_reasoning_effort")
        models.append({
            "id": str(mid),
            "owned_by": owned_by if isinstance(owned_by, str) else None,
            "name": name if isinstance(name, str) else None,
            "description": desc if isinstance(desc, str) else None,
            "context_length": ctx,
            "max_output_length": max_out,
            "pricing": pricing if isinstance(pricing, dict) else {},
            "architecture": arch,
            "input_modalities": input_modalities,
            "output_modalities": output_modalities,
            "supported_parameters": supported_parameters,
            "supported_features": _merge_supports_features(_merge_capabilities(_str_list(merged.get("supported_features")),
                                                      merged.get("capabilities")), item),
            "free": free if isinstance(free, bool) else None,
            "stability": stability if isinstance(stability, str) and stability.strip() else None,
            "publish_time": _pub if isinstance(_pub, str) and _pub.strip() else None,
            "effort_levels": _str_list(_eff_levels),
            "effort_default": _eff_d if isinstance(_eff_d, str) and _eff_d.strip() else None,
        })
    # 2026-09-25 04:38:28 小健 - 全链路单点排序: 远端列表按 id 字母序(不分大小写), 下游分组/落盘/下拉自动继承
    models.sort(key=lambda m: m["id"].lower())
    return models, None


def _classify_remote_result(status_code: Optional[int], network_err: bool) -> str:
    """远端探测结果分类，供前端给出"地址问题/key 问题"两套文案 - 小欧 - 2026-09-26。

    分类表（**404/405/501 不得判 key 无效** —— 部分 provider 没有 /models 端点，
    拿 404 判"key 无效"会给用户误报，用户会反复改 key 甚至把本来正确的 key 改坏）：
      ok                     2xx                     key 有效
      key_invalid            401 / 403               key 无效或无权限
      endpoint_unsupported   404 / 405 / 501         该 provider 无 /models 端点，key 未验证
      network_error          超时 / 连接失败          api_base 或网络问题，与 key 无关
    """
    if network_err:
        return "network_error"
    if status_code is None:
        return "network_error"
    if 200 <= status_code < 300:
        return "ok"
    if status_code in (401, 403):
        return "key_invalid"
    if status_code in (404, 405, 501):
        return "endpoint_unsupported"
    return "network_error"


def get_provider_raw_entry(name: str) -> Dict[str, Any]:
    """取指定 provider 的 ai 区原始条目（不掩码）—— 明文查看端点的 service 层唯一入口。

    2026-09-26 - 小欧 - 三堂会审后修正·二（见文件头）: 做"读 + 存在性校验"两件事，
    有真实分支逻辑，不是透传壳。路由层只调本函数，不直接碰 _raw_ai/_provider_names。
    """
    ai = _raw_ai()
    if name not in _provider_names(ai):
        raise HTTPException(status_code=404, detail=f"Provider {name} 不存在")
    return ai.get(name) or {}


async def fetch_remote_models(name: str, probe_key: Optional[str] = None) -> Dict[str, Any]:
    """拉取 Provider 远程模型列表 — 后端代理绕 CORS；远端失败统一 200+ok:false — 小欧 2026-09-24

    probe_key 支持"测未保存的 key"（保存前验证场景）- 小欧 - 2026-09-26。
    该 key **仅存内存、只用于本次探测的 header，不落盘、不进日志、不回传响应**（设计硬要求）。
    另：失败返回增 status_code + category 字段，供前端区分"地址问题"与"key 问题"两套文案。
    """
    ai = _raw_ai()
    p, api_base = _require_provider_for_fetch(name, ai)
    # 2026-09-24 23:55:00 - 小欧 - api_key 含 {NAME}_API_KEY env 接管值（env 优先，YAML 兜底）— 小欧-2026-09-24
    # probe_key 优先于 env/YAML（用户正在输入框里新输的 key 才是待验证的那个）- 小欧 - 2026-09-26
    # api_key 为空时传空串给远端、**不回落**到全局默认 provider 的 key（与 resolver 的 key 空白语义
    # 共同构成"key 空白即失败"的一致语义）。切勿在此加 `or 全局单例.api_key` 之类 fallback。
    api_key = (probe_key.strip() if not is_blank_secret(probe_key)
               else os.environ.get(f"{name.upper()}_API_KEY") or str(p.get("api_key") or ""))
    headers = get_provider_adapter(name).static_headers(api_key)
    # 2026-10-31 - 小欧 - 空 key 不携带 Authorization 已收口到 ProviderAdapter.auth_headers(基类与
    #   zen 覆写版共用同一实现)。本处原有 pop 兜底删除: 同一条规则写两处必然漂移, 且探测链与
    #   真实对话链口径必须一致(否则"测试连接通过、真对话 400")。
    configured = [m for m in (p.get("models") or []) if isinstance(m, str)]
    ref = get_current_ref(ai)
    current_model = ref["model"] if ref["provider"] == name else None

    def _fail(message: str, status_code: Optional[int] = None, network_err: bool = False) -> Dict[str, Any]:
        return {
            "ok": False,
            "provider": name,
            "models": [],
            "count": 0,
            "configured": configured,
            "current_model": current_model,
            "message": message,
            # 分类 + 状态码随失败一起返回，调用方才能程序化区分错误类型
            "status_code": status_code,
            "category": _classify_remote_result(status_code, network_err),
        }

    resp, err = await _http_get_remote_models(api_base, headers)
    if err:
        return _fail(err, network_err=True)
    models, err = _parse_remote_models_body(resp)
    if err:
        return _fail(err, status_code=resp.status_code)
    return {
        "ok": True,
        "provider": name,
        "models": models,
        "count": len(models),
        "configured": configured,
        "current_model": current_model,
        "status_code": resp.status_code,
        "category": "ok",
    }


# 探测素材: 8x8 纯色 PNG(74B)内联 data URI —— 程序生成, 不依赖外网图床 — 小欧-2026-11-08
_PROBE_IMAGE_URL = ("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAgAAAAICAIAAABLbSncAAAAEUlE"
                    "QVR4nGO4o6GBFTEMLQkAe3tLAfuiUfAAAAAASUVORK5CYII=")
# 2026-11-09 小欧 - 拒绝状态集单源: 由 generation_client.REJECT_STATUS 统一持有, 本文件不再复制 — 小欧-2026-11-09
# 2026-11-09 小欧 - 图像 token 差值判定: 厂商不回报 image_tokens 时改比同 prompt 纯文本基线 prompt_tokens,
#   差值≥_IMG_DELTA_MIN 即证明图进了上下文(sensenova 系只报 prompt/total) — 小欧-2026-11-09
# 2026-11-11 小欧 - 输入探测泛化三态(image/video/audio): 视频=video_url 直传公网素材,
#   音频=下载素材后 base64 内联 input_audio(OpenAI 兼容协议无音频 URL part); 素材地址可由
#   media.probe_video_url / media.probe_audio_url 配置覆盖, 缺省用下方实测选定的默认值 — 小欧-2026-11-11
_PROBE_TEXT = "图中是什么颜色? 只回答颜色。"
_PROBE_VIDEO_TEXT = "这段视频里主体在做什么? 只回答一句话。"
_PROBE_AUDIO_TEXT = "这段音频里是什么声音? 只回答一句话。"
# 默认素材(本机实测可达性/速度/体积择优): 视频取 test-videos.co.uk 全球 CDN 991KB≈3s 完整 GET
#   (w3school 中国 CDN HEAD 快但 GET 实测 >30s, kilo 抓取 60s 超时根因), 音频 runoob 29KB≈0.5s — 小欧-2026-11-11
_PROBE_VIDEO_URL_DEFAULT = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
_PROBE_AUDIO_URL_DEFAULT = "https://www.runoob.com/try/demo_source/horse.mp3"
_MEDIA_DELTA_MIN = 8
_PROBE_KIND_TEXT = {"image": _PROBE_TEXT, "video": _PROBE_VIDEO_TEXT, "audio": _PROBE_AUDIO_TEXT}
_PROBE_TOKEN_SUFFIX = {"image": "image_tokens", "video": "video_tokens", "audio": "audio_tokens"}
# 取证串 → 人话的模态名(_probe_hint 用)
_PROBE_HINT_LABEL = {"image": "图像", "video": "视频", "audio": "音频"}
# 音频素材后缀 → input_audio.format 合法值(OpenAI 兼容协议枚举)
_AUDIO_SUFFIX_FORMAT = {".mp3": "mp3", ".wav": "wav", ".m4a": "m4a", ".ogg": "ogg", ".flac": "flac", ".webm": "webm"}


def _audio_format(url: str) -> str:
    """素材 URL 后缀 → input_audio.format; 无法识别按 mp3(默认素材即 mp3) — 小欧-2026-11-11"""
    path = urlsplit(url).path.lower()
    for suf, fmt in _AUDIO_SUFFIX_FORMAT.items():
        if path.endswith(suf):
            return fmt
    return "mp3"


def _probe_messages(media: str, kind: str = "image",
                    audio_format: str = "mp3") -> List[Dict[str, Any]]:
    """探测请求 messages: kind 决定素材 part 形状(image_url / video_url / input_audio) — 小欧-2026-11-11"""
    if kind == "image":
        part: Dict[str, Any] = {"type": "image_url", "image_url": {"url": media}}
    elif kind == "video":
        # provider 定制点: 当前视频腿只探 URL 直传(方言通用); provider 声明支持视频内联
        #   (如 Gemini inline_data video/mp4)时在此补内联探测腿, 待视频功能实现时再扩展。
        part = {"type": "video_url", "video_url": {"url": media}}
    else:
        part = {"type": "input_audio", "input_audio": {"data": media, "format": audio_format}}
    return [{"role": "user", "content": [
        {"type": "text", "text": _PROBE_KIND_TEXT[kind]},
        part,
    ]}]


async def _probe_baseline_tokens(api_base: str, headers: Dict[str, str], model: str,
                                 text: str, timeout: float) -> Optional[int]:
    """纯文本基线 prompt_tokens(带素材请求同 prompt 去掉素材): 差值即素材占用 token — 小欧-2026-11-09"""
    body = {"model": model, "messages": [{"role": "user", "content": text}],
            "max_tokens": 16, "temperature": 0}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{api_base.rstrip('/')}/chat/completions",
                                     headers=headers, json=body)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    try:
        usage = resp.json().get("usage")
    except Exception:
        return None
    n = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    return n if isinstance(n, int) else None


def _media_token_count(usage: Any, kind: str) -> Optional[int]:
    """从 usage 的输入侧递归找指定模态 token 数: 各家键位不同, 只认 *{kind}_tokens 且为 int。

    返回 None = 输入侧根本没有该字段(厂商不报), 与"字段存在且为 0"必须区分:
    后者是网关静默丢素材, 前者什么也证明不了。
    **只查输入侧**: completion_tokens_details.* 是"输出 token"(生成模型用),
    kilo 等网关对纯文本模型也恒填 0, 误当输入计数会把能看素材的模型判成静默丢 — 小欧-2026-11-09
    2026-11-11 小欧 - 泛化 kind(image/video/audio), 键后缀单源 _PROBE_TOKEN_SUFFIX — 小欧-2026-11-11
    """
    if not isinstance(usage, dict):
        return None
    suffix = _PROBE_TOKEN_SUFFIX[kind]
    top = usage.get(suffix)
    if isinstance(top, int) and not isinstance(top, bool):
        return top
    return _scan_token_key(usage.get("prompt_tokens_details"), suffix)


def _scan_token_key(node: Any, suffix: str) -> Optional[int]:
    """在 prompt_tokens_details 子树内找以 suffix 结尾的 int 键 — 小欧-2026-11-09"""
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, int) and not isinstance(v, bool) and str(k).endswith(suffix):
                return v
            if isinstance(v, (dict, list)):
                hit = _scan_token_key(v, suffix)
                if hit is not None:
                    return hit
    elif isinstance(node, list):
        for v in node:
            hit = _scan_token_key(v, suffix)
            if hit is not None:
                return hit
    return None


async def _fetch_audio_b64(url: str, timeout: float) -> Tuple[Optional[str], str]:
    """下载音频素材并 base64 内联(音频探测唯一素材通道) — 小欧-2026-11-11

    失败返回 (None, 取证串): 属素材不可达, 不判模型能力(与图片外链腿同口径)。
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
    except Exception as e:
        return None, f"source_download_failed: {type(e).__name__}: {e}"[:160]
    if resp.status_code != 200:
        return None, f"source_download_failed: http_{resp.status_code}"
    return base64.b64encode(resp.content).decode("ascii"), ""


async def _probe_once(api_base: str, headers: Dict[str, str], model: str,
                      media: str, timeout: float, kind: str = "image",
                      audio_format: str = "mp3") -> Tuple[bool, str, bool]:
    """单次探测 → (是否真看到素材, 证据, 结论是否确定)。

    确定结论: 200 有对应模态 token(或基线差值≥阈值) / 200 该 token 为 0(或差值≤0) / 400·415·422 拒内容类型。
    鉴权失败、限流、超时、5xx、坏 JSON 都是环境问题, 不得写成模型能力 — 小欧-2026-11-08
    2026-11-11 小欧 - 泛化 kind(image/video/audio), 取证串按模态命名({kind}_tokens=…) — 小欧-2026-11-11
    """
    body = {"model": model, "messages": _probe_messages(media, kind, audio_format),
            "max_tokens": 16, "temperature": 0}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{api_base.rstrip('/')}/chat/completions", headers=headers, json=body)
    except Exception as e:
        return False, f"network_error: {type(e).__name__}: {e}", False
    if resp.status_code != 200:
        text = resp.text
        # 「需登录/付费账号」与「key 无效」是两件事, 提示要指到该做的动作 — 小欧-2026-11-09
        if resp.status_code in (401, 403) and "sign in" in text.lower():
            return False, f"paid_model_required: {text[:160]}", False
        return False, f"http_{resp.status_code}: {text[:160]}", resp.status_code in generation_client.REJECT_STATUS
    try:
        data = resp.json()
    except Exception:
        return False, "bad_json", False
    tokens = _media_token_count(data.get("usage"), kind)
    if tokens is not None and tokens > 0:
        return True, f"{kind}_tokens={tokens}", True
    # 输入侧没报(或恒报 0): 比纯文本基线差值, 素材真进了上下文即证明能读 — 小欧-2026-11-09
    usage = data.get("usage")
    used = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    base = await _probe_baseline_tokens(api_base, headers, model, _PROBE_KIND_TEXT[kind], timeout)
    if not isinstance(used, int) or base is None:
        return (False, f"no_{kind}_tokens", True) if tokens == 0 else (False, f"no_{kind}_token_field", False)
    delta = used - base
    if delta >= _MEDIA_DELTA_MIN:
        return True, f"{kind}_tokens={delta}", True
    if delta <= 0:
        return False, f"no_{kind}_tokens", True
    return False, f"{kind}_tokens_ambiguous={delta}", False


def _probe_hint(ev: str) -> str:
    """未测成的取证串 → 用户可据以行动的说明(技术词汇, 不打哑谜)。

    界面只在轻提示里显示这句, 故必须短且无嵌套括号; 原始取证(状态码/响应片段)留在 media.evidence 供排查 — 小欧-2026-11-08
    """
    if ev.startswith("network_error"):
        return "连不上厂商接口"
    if ev.startswith("source_unreachable"):
        return "厂商抓不到探测素材，换素材地址再测"
    if ev.startswith("source_download_failed"):
        return "下载探测素材失败，换素材地址再测"
    if ev.startswith("queue_full"):
        return "厂商视频队列已满，稍后重试"
    if ev.startswith("poll_timeout"):
        return "等视频出片超时，任务可能仍在排队"
    if ev.startswith("task_failed"):
        return "厂商侧生成失败，稍后重试"
    if ev.startswith("no_task_id"):
        return "厂商未返回任务号，检查接口地址"
    if ev.startswith("protocol_drift"):
        return "厂商改了视频参数校验（mode），需同步常量"
    if ev.startswith("no_output_field"):
        return "任务已完成但取不到视频地址，响应结构可能变了"
    if ev.startswith("poll_http_"):
        return "轮询查任务失败，稍后重试"
    if ev == "bad_json":
        return "返回不是 JSON，检查接口地址"
    if ev.startswith("paid_model_required"):
        return "该模型需登录付费账号，API Key 不足以调用"
    if ev == "no_image_token_field":
        return "厂商未回报图像 token，基线差值也取不到"
    if ev.startswith("image_tokens_ambiguous"):
        return "图像 token 增量过小，无法确认读到了图"
    # 2026-11-11 小欧 - 视频/音频取证串同款提示(键名即模态, 不再逐 kind 复制分支) — 小欧-2026-11-11
    m = re.match(r"no_(video|audio)_token_field$", ev)
    if m:
        return _PROBE_HINT_LABEL[m.group(1)] + " token 无回报，基线差值也取不到"
    m = re.match(r"(video|audio)_tokens_ambiguous", ev)
    if m:
        return _PROBE_HINT_LABEL[m.group(1)] + " token 增量过小，无法确认读到了素材"
    if ev == "no_output":
        return "厂商返回 200 但无产物地址"
    code = ev.split(":", 1)[0][5:] if ev.startswith("http_") else ""
    if code in ("401", "403"):
        return f"鉴权失败 {code}，检查 API Key"
    if code == "404":
        return "无此模型 404，检查模型名"
    if code == "408":
        return "厂商超时 408"
    if code == "429":
        return "厂商限流 429"
    if code.startswith("5"):
        return f"厂商服务端错误 {code}"
    return f"厂商拒绝 {code}" if code else "厂商拒绝该请求"


def _persist_media_probe(name: str, model: str, media: Dict[str, Any]) -> bool:
    """探测结果落 model_meta.<model>.media(嵌套整块写); 失败只记日志不影响探测结论。"""
    try:
        merge_nested_patch({"ai": {name: {"model_meta": {model: {"media": media}}}}}, scope="model")
    except Exception:
        logger.error(f"[probe] 媒体能力落库失败 provider={name} model={model}", exc_info=True)
        return False
    return True


def _persist_probe_last(name: str, model: str, kind: str, ok: bool, message: str) -> None:
    """记「上次验证回执」: 未定结论不写能力, 但要留原因给界面常驻显示, 不藏在一次性 toast 里。

    与 media 物理分离(不同键), 判定链永不读它; 写盘失败只记日志 — 小欧-2026-11-09
    """
    rec = {"at": datetime.now().isoformat(timespec="seconds"), "ok": ok, "message": message}
    try:
        merge_nested_patch(
            {"ai": {name: {"model_meta": {model: {"last_probe": {kind: rec}}}}}}, scope="model")
    except Exception:
        logger.error(f"[probe] 回执落库失败 provider={name} model={model} kind={kind}", exc_info=True)


def _ev_tokens(ev: str) -> Optional[int]:
    """从取证串抽 image_tokens 值(串样例 image_tokens=64, 无值返 None)，供界面按腿显示 — 小欧-2026-11-09"""
    m = re.search(r"image_tokens=(\d+)", ev or "")
    return int(m.group(1)) if m else None


def _ev_tokens(ev: str, kind: str = "image") -> Optional[int]:
    """从取证串抽 {kind}_tokens 值(串样例 image_tokens=64, 无值返 None)，供界面按腿显示 — 小欧-2026-11-09
    2026-11-11 小欧 - 泛化 kind(视频/音频腿取证串同款命名) — 小欧-2026-11-11"""
    m = re.search(rf"{kind}_tokens=(\d+)", ev or "")
    return int(m.group(1)) if m else None


async def probe_model_media(name: str, model: str, kind: str = "image") -> Dict[str, Any]:
    """探测模型接受哪种媒体输入并落库 — 小欧-2026-11-08

    kind=image: 内联(内置 8x8 PNG) + 外链(media.probe_image_url 配置时) 两腿, accept=both/inline/none;
    kind=video: 单腿 video_url 直传公网素材(内联 base64 体积过大且非通用协议), accept=url/none;
    kind=audio: 下载素材后 base64 内联 input_audio(OpenAI 兼容协议无音频 URL part), accept=inline/none。
    视频/音频素材地址由 media.probe_video_url / media.probe_audio_url 配置, 缺省用实测择优的内置默认值。
    只落确定结论(见 _probe_once): 一次 429/5xx/密钥错不得把模型能力写死成 none。
    返回的 message 是给人看的整句结论(界面原样显示, 不自行拼词) — 小欧-2026-11-08
    2026-11-11 小欧 - 泛化 kind(图片行为不变, 视频/音频落 media.{kind} 子块) — 小欧-2026-11-11
    """
    if kind not in _PROBE_KIND_TEXT:
        raise HTTPException(status_code=400, detail=f"未知探测类型 {kind}(合法: image/video/audio)")
    ai = _raw_ai()
    p, api_base = _require_provider_for_fetch(name, ai)
    configured = [m for m in (p.get("models") or []) if isinstance(m, str)]
    if model not in configured:
        raise HTTPException(status_code=404, detail=f"模型 {model} 不在 provider {name} 的 models 列表")
    api_key = os.environ.get(f"{name.upper()}_API_KEY") or str(p.get("api_key") or "")
    headers = get_provider_adapter(name).static_headers(api_key)
    timeout = float(p.get("timeout") or 60)
    cfg = get_config().get("media") or {}

    if kind in ("video", "audio"):
        return await _probe_media_single_leg(name, model, kind, api_base, headers, timeout, cfg)

    t0 = time.monotonic()
    inline_ok, inline_ev, inline_settled = await _probe_once(
        api_base, headers, model, _PROBE_IMAGE_URL, timeout)
    inline_ms = int((time.monotonic() - t0) * 1000)
    url_ok, url_ev, url_settled = False, "skipped", False
    probe_url = str(cfg.get("probe_image_url") or "").strip()
    url_ms: Optional[int] = None
    if inline_ok and probe_url:
        t0 = time.monotonic()
        url_ok, url_ev, url_settled = await _probe_once(api_base, headers, model, probe_url, timeout)
        url_ms = int((time.monotonic() - t0) * 1000)

    accept = "both" if (inline_ok and url_ok) else ("inline" if inline_ok else "none")
    # 外链腿已请求(内联通过且配置了地址)却未取证 = 厂商抓图失败(network_error 类), 与「地址为空没发」
    #   结构化区分, 前端提示不再一律归因「地址为空」 — 小欧-2026-11-09
    url_err = bool(inline_ok and probe_url and not url_ok and not url_settled)
    # 两腿耗时(ms, 请求往返)/token 结构化落库, 界面 tip 直读, 不再解析 evidence 串 — 小欧-2026-11-09
    media = {
        "accept": {"image": accept},
        "probed_at": datetime.now().isoformat(timespec="seconds"),
        "url_tested": url_settled,
        "url_err": url_err,
        "inline_ms": inline_ms,
        "url_ms": url_ms,
        "inline_tokens": _ev_tokens(inline_ev),
        "url_tokens": _ev_tokens(url_ev),
        "evidence": f"image:inline={inline_ev}; image:url={url_ev}",
    }
    persisted = _persist_media_probe(name, model, media) if inline_settled else False
    # 界面用轻提示(toast)展示, 必须短: 结论一句, 细节在列内 tooltip — 小欧-2026-11-08
    if not inline_settled:
        message = f"未测成：{_probe_hint(inline_ev)}；原有记录未改动"
    elif not inline_ok:
        message = "已记录：该模型收不到图片"
    elif url_ok:
        message = "已记录：内联＋外链"
    elif url_settled:
        message = "已记录：仅内联（外链被拒）"
    elif not probe_url:
        message = "已记录：仅内联（外链未测）"
    else:
        message = f"已记录：仅内联（外链未取证，{_probe_hint(url_ev)}）"
    # 回执常驻: 未定结论也能看到原因(需登录/超时/限流), 不随 toast 消失 — 小欧-2026-11-09
    _persist_probe_last(name, model, "media", inline_ok, message)
    return {
        "ok": inline_ok,
        "provider": name,
        "model": model,
        "kind": kind,
        "accept": accept,
        "url_tested": url_settled,
        "conclusive": inline_settled,
        "media": media,
        "persisted": persisted,
        "message": message,
    }


# 视频/音频探测共用骨架: 单腿(视频=URL 直传, 音频=下载内联), 结果落 media.{kind} 子块 — 小欧-2026-11-11
async def _probe_media_single_leg(
    name: str, model: str, kind: str, api_base: str,
    headers: Dict[str, str], timeout: float, cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """单腿探测编排(视频/音频): 取素材 → _probe_once → 落库/回执, 与图片腿同口径。"""
    label = _PROBE_HINT_LABEL[kind]
    src = str(cfg.get(f"probe_{kind}_url") or
              (_PROBE_VIDEO_URL_DEFAULT if kind == "video" else _PROBE_AUDIO_URL_DEFAULT)).strip()
    if not src:
        message = f"未测成：未配置{label}素材地址；原有记录未改动"
        _persist_probe_last(name, model, "media", False, message)
        return {"ok": False, "provider": name, "model": model, "kind": kind,
                "accept": None, "conclusive": False, "media": {}, "persisted": False, "message": message}

    if kind == "audio":
        b64, dl_err = await _fetch_audio_b64(src, timeout)
        if b64 is None:
            message = f"未测成：{_probe_hint(dl_err)}；原有记录未改动"
            _persist_probe_last(name, model, "media", False, message)
            return {"ok": False, "provider": name, "model": model, "kind": kind,
                    "accept": None, "conclusive": False, "media": {}, "persisted": False, "message": message}
        t0 = time.monotonic()
        ok, ev, settled = await _probe_once(
            api_base, headers, model, b64, timeout, kind="audio", audio_format=_audio_format(src))
    else:
        t0 = time.monotonic()
        ok, ev, settled = await _probe_once(api_base, headers, model, src, timeout, kind="video")
    ms = int((time.monotonic() - t0) * 1000)

    accept = ("url" if kind == "video" else "inline") if ok else "none"
    # 单腿记录落 media.{kind} 子块(深合并, 不触碰图片腿平铺字段); 顶层 probed_at 留给图片腿
    rec = {
        "state": "ok" if ok else ("none" if settled else "unverified"),
        "ms": ms,
        "tokens": _ev_tokens(ev, kind),
        "evidence": ev,
        "at": datetime.now().isoformat(timespec="seconds"),
        "source": src,
    }
    persisted = _persist_media_probe(name, model, {"accept": {kind: accept}, kind: rec}) if settled else False
    if not settled:
        message = f"未测成：{_probe_hint(ev)}；原有记录未改动"
    elif ok:
        message = f"已记录：{label}输入可用"
    else:
        message = f"已记录：该模型收不到{label}"
    _persist_probe_last(name, model, "media", ok, message)
    return {
        "ok": ok,
        "provider": name,
        "model": model,
        "kind": kind,
        "accept": accept,
        "conclusive": settled,
        "media": {"accept": {kind: accept}, kind: rec},
        "persisted": persisted,
        "message": message,
    }


# 2026-11-09 小欧 - 生成验证腿：图/视频各两枪(文生+图生)验输入与输出，落 media.generate.{image,video} — 小欧-2026-11-09
async def probe_model_output(name: str, model: str) -> Dict[str, Any]:
    """生成验证（[15]）：按声明的输出模态双腿实测，落 media.generate.{image,video}  - 小欧-2026-11-09

    复用三级取值链（env→config）/ adapter 静态头 / _persist_media_probe 深合并
    （merge_nested_patch 按叶子路径写盘，accept 等输入腿字段物理不可被触碰）；
    evidence 口径与 _probe_once 同源，message 复用 _probe_hint 短语。
    闸门：只在模型声明 image/video 输出时执行——与设置页按钮条件同口径。
    视频腿是异步任务（提交+轮询，单腿上限 VIDEO_POLL_TIMEOUT），超时/排队只记未完成。
    """
    ai = _raw_ai()
    p, api_base = _require_provider_for_fetch(name, ai)
    configured = [m for m in (p.get("models") or []) if isinstance(m, str)]
    if model not in configured:
        raise HTTPException(status_code=404, detail=f"模型 {model} 不在 provider {name} 的 models 列表")
    meta = p.get("model_meta") or {}
    outs = ((meta.get(model) or {}).get("output_modalities") or []) if isinstance(meta, dict) else []
    has_image = "image" in outs
    has_video = "video" in outs
    if not has_image and not has_video:
        raise HTTPException(status_code=400, detail=f"模型 {model} 未声明 image/video 输出，无生成验证腿")
    api_key = os.environ.get(f"{name.upper()}_API_KEY") or str(p.get("api_key") or "")
    headers = get_provider_adapter(name).static_headers(api_key)
    timeout = float(p.get("timeout") or 60)

    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    async def _probe_leg(coro: Any) -> Tuple[Dict[str, Any], bool]:
        t0 = time.monotonic()
        ok, ev, settled = await coro
        rec = {
            "state": "ok" if ok else ("none" if settled else "unverified"),
            "ms": int((time.monotonic() - t0) * 1000),
            "evidence": ev,
            "at": _now(),
        }
        return rec, settled

    def _image_leg(prompt: str, image: Optional[str] = None) -> Any:
        return generation_client.generate_image(
            api_base, headers, model, prompt, image=image, timeout=timeout
        )

    def _video_leg(prompt: str, mode: str, image: Optional[str] = None) -> Any:
        return generation_client.generate_video(
            api_base,
            headers,
            model,
            prompt,
            mode,
            images=[image] if image else None,
            timeout=timeout,
        )

    skipped = {"state": "skipped", "evidence": "", "at": _now()}
    generate: Dict[str, Any] = {}
    settled_groups: Dict[str, Any] = {}
    legs: List[Tuple[str, Dict[str, Any]]] = []
    if has_image:
        t2i, settled = await _probe_leg(_image_leg(generation_client.PROBE_PROMPT))
        # 图源=generation_client.PROBE_IMAGE_URL(生成腿专用公网位图, 与输入腿素材解耦); t2i 未取证或未成功不打第二枪
        if settled and t2i["state"] == "ok":
            i2i, _ = await _probe_leg(
                _image_leg(generation_client.PROBE_I2I_PROMPT, generation_client.PROBE_IMAGE_URL)
            )
        else:
            i2i = skipped
        generate["image"] = {"t2i": t2i, "i2i": i2i}
        if settled:
            settled_groups["image"] = generate["image"]
        legs += [("文生图", t2i), ("图生图", i2i)]
    if has_video:
        t2v, settled = await _probe_leg(
            _video_leg(generation_client.PROBE_VIDEO_PROMPT, generation_client.VIDEO_MODE_T2V)
        )
        if settled and t2v["state"] == "ok":
            i2v, _ = await _probe_leg(
                _video_leg(
                    generation_client.PROBE_VIDEO_I2V_PROMPT,
                    generation_client.VIDEO_MODE_I2V,
                    generation_client.PROBE_IMAGE_URL,
                )
            )
        else:
            i2v = skipped
        generate["video"] = {"t2v": t2v, "i2v": i2v}
        if settled:
            settled_groups["video"] = generate["video"]
        legs += [("文生视频", t2v), ("图生视频", i2v)]

    # 分组落库: 图腿已取证就存图腿, 视频腿排队超时不连坐(反之亦然) — 小欧-2026-11-09
    persisted = (
        _persist_media_probe(name, model, {"generate": settled_groups}) if settled_groups else False
    )
    ok_labels = [lb for lb, r in legs if r["state"] == "ok"]
    none_labels = [lb for lb, r in legs if r["state"] == "none"]
    pend_labels = [lb for lb, r in legs if r["state"] == "unverified"]
    skip_labels = [lb for lb, r in legs if r["state"] == "skipped"]
    pend_reasons = [
        (lb, _probe_hint(r["evidence"])) for lb, r in legs if r["state"] == "unverified"
    ]
    # 单腿未定时不再重复腿名(摘要已写「X未完成」), 多腿才带前缀区分 — 小欧-2026-11-09
    pend_hint = "；".join(
        h if len(pend_reasons) == 1 else f"{lb}：{h}" for lb, h in pend_reasons
    )
    if not settled_groups:
        message = f"未完成：{pend_hint}（原记录未改动）"
    elif not none_labels and not pend_labels and not skip_labels:
        # 生成腿自证输入(文生=文本、图生=公网图), 不再套输入腿「文本+URL图片」文案 — 小欧-2026-11-09
        message = f"已记录：{'、'.join(ok_labels)}均通过"
    else:
        parts = []
        if ok_labels:
            parts.append(f"可{'、'.join(ok_labels)}")
        if none_labels:
            parts.append(f"{'、'.join(none_labels)}被厂商拒绝")
        if pend_labels:
            parts.append(f"{'、'.join(pend_labels)}未完成")
        if skip_labels:
            parts.append(f"{'、'.join(skip_labels)}未执行")
        message = "已记录：" + "；".join(parts)
        if pend_hint:
            message += f"（{pend_hint}）"
    # 回执常驻: 生成腿未完成/被拒的原因同样要能留在界面上 — 小欧-2026-11-09
    _persist_probe_last(
        name, model, "output",
        all(r["state"] == "ok" for _, r in legs if r["state"] != "skipped"), message)
    return {
        "ok": all(r["state"] == "ok" for lb, r in legs if r["state"] != "skipped"),
        "provider": name,
        "model": model,
        "generate": generate,
        # 结论口径 = 无未定腿: 未定腿(skipped 除外)存在时调用方只提示、不落能力结论 — 小欧-2026-11-09
        "conclusive": all(r["state"] != "unverified" for _, r in legs),
        "persisted": persisted,
        "message": message,
    }


def _persist_model_meta(
    node: Dict[str, Any],
    meta_by_id: Dict[str, Dict[str, Any]],
    valid_ids: List[str],
) -> None:
    """把勾选模型的静态元数据持久化到 model_meta — 小欧 2026-10-26

    字段分两组（新增字段只需在对应元组加一行，不碰逻辑）：
      - INT_FIELDS：int 值（排除 bool），空值不写（防覆盖已有值）
      - LIST_FIELDS：list 值（过滤非 str 成员），空数组也写（显式声明"无"）

    仅对 valid_ids 中的模型写入，merge_nested_patch 负责与既有 model_meta 块合并。
    """
    # 2026-10-26 18:45:00 - 小欧 - 字段配置表（OCP：新增字段只加表行，不改逻辑）
    INT_FIELDS = ("context_length", "max_output_length")
    LIST_FIELDS = ("input_modalities", "output_modalities", "supported_parameters", "supported_features")
    valid_set = set(valid_ids)
    for mid, md in meta_by_id.items():
        if mid not in valid_set or not isinstance(md, dict):
            continue
        leaf: Dict[str, Any] = {}
        # int 字段组：isinstance(int) 且非 bool 才写，空值不覆盖已有值
        for key in INT_FIELDS:
            val = md.get(key)
            if isinstance(val, int) and not isinstance(val, bool):
                leaf[key] = val
        # list 字段组：isinstance(list) 就写，空数组也写（显式声明"无"）；模态两字段先归一词汇
        for key in LIST_FIELDS:
            val = md.get(key)
            if isinstance(val, list):
                strs = [v for v in val if isinstance(v, str)]
                leaf[key] = normalize_modalities(strs) if key.endswith("_modalities") else strs
        if leaf:
            node.setdefault("model_meta", {}).setdefault(mid, {}).update(leaf)


def replace_provider_models(name: str, models: List[Dict[str, Any]]) -> Dict[str, Any]:
    """替换式写入 ai.{provider}.models + 差集孤儿清理 — 小欧 2026-09-24

    models 元素契约 2026-10-05 22:16:38 扩：Dict{id: str, context_length?, input_modalities?}。
    旧 List[str] 等价于元素只含 id。保存时把每个勾选模型的「上下文/输入模态」静态元数据
    同步落 ai.{provider}.model_meta.{model}（北京老陈指令——它们是模型自身属性，此前只在页面展示、
    重新拉取即丢，现在持久化到配置，离线/重启后仍可见）。removed 模型的 model_params/model_meta 块
    仍按既有差集孤儿清理整块置 None。

    2026-10-26 18:45:00 - 小欧 - 三堂会审重构：
      - 提取 _persist_model_meta 独立函数（SRP：编排 vs 细节分离）
      - 用字段配置表 + 循环替代 6 个 if 块（DRY/KISS-DIRECT/OCP）
    """
    _migrate_legacy_capabilities(Path(get_config_path()))  # 落盘前迁移老 capabilities(幂等, 无残留零改动) — 小欧-2026-11-08
    ai = _raw_ai()
    if name not in _provider_names(ai):
        raise HTTPException(status_code=404, detail=f"Provider {name} 不存在")
    p = ai[name]  # _provider_names 已保证 isinstance(ai[name], dict)
    if os.environ.get(f"{name.upper()}_API_KEY"):
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{name}' 由环境变量 {name.upper()}_API_KEY 接管，只读",
        )
    new_list: List[str] = []
    meta_by_id: Dict[str, Dict[str, Any]] = {}
    seen = set()
    for m in models:
        s = str(m.get("id")).strip() if isinstance(m, dict) else str(m).strip()
        if s and s not in seen:
            seen.add(s)
            new_list.append(s)
            if isinstance(m, dict):
                meta_by_id[s] = m
    if not new_list:
        raise HTTPException(status_code=400, detail="模型列表不能为空")
    ref = get_current_ref(ai)
    if ref["provider"] == name and ref["model"] and ref["model"] not in new_list:
        raise HTTPException(
            status_code=400,
            detail=f"不能移除当前全局模型 {ref['model']}，请先切换全局模型",
        )
    old = [m for m in (p.get("models") or []) if isinstance(m, str)]
    removed = [m for m in old if m not in set(new_list)]
    added = [m for m in new_list if m not in set(old)]
    tree: Dict[str, Any] = {"ai": {name: {"models": new_list}}}
    node = tree["ai"][name]
    params_block = p.get("model_params") or {}
    meta_block = p.get("model_meta") or {}
    if isinstance(params_block, dict):
        orphans = {m: None for m in removed if m in params_block}
        if orphans:
            node["model_params"] = orphans
    if isinstance(meta_block, dict):
        orphans = {m: None for m in removed if m in meta_block}
        if orphans:
            node["model_meta"] = orphans
    # 2026-10-05 22:16:38 小欧 - 把勾选模型的「上下文/输入模态」静态元数据持久化到 model_meta
    _persist_model_meta(node, meta_by_id, new_list)
    merge_nested_patch(tree, scope="model")
    return {"ok": True, "mtime": _config_mtime(), "added": added, "removed": removed}
