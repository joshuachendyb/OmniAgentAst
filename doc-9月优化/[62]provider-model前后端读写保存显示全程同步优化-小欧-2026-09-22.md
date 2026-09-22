# [62]provider/model前后端读写保存显示全程同步优化

**创建时间**: 2026-09-22 12:40:51
**更新时间**: 2026-09-22 15:12:36（小欧）
**编写人**: 小欧
**版本历史**（按时间正序，旧条原文保留）:
- v1.0 2026-09-22 12:40:51 小欧 新建：reasoning_effort显示为数字0的病根分析与后端SSOT根治设计
- v1.1 2026-09-22 12:43:19 小欧 修正：v1.0中PARAM_ENUMS写死全局表不可扩展，改为按模型可配三层解析（model_meta > provider级 > 全局默认），不同模型3/4/5个选项无需改代码
- v1.2 2026-09-22 12:47:00 小欧 补充：2.2下加2.2.1配置文件示例，明确现状模型零迁移、新模型按例加model_meta.param_options即可
- v1.3 2026-09-22 12:50:57 小欧 澄清：2.2.1中“3个的、4个的同理”含糊，展开为3/4/5个三模型各自独立配置示例
- v1.4 2026-09-22 12:52:09 小欧 落实：2.2.1写法已在backend/config.yaml.example（zhipuai段）完整体现，文档以该文件为准
- v1.5 2026-09-22 12:53:13 小欧 补说明：第二章开头先声明配置写法以backend/config.yaml.example为准，文档示例与该文件保持同构
- v1.6 2026-09-22 12:58:14 小欧 一致性核查整改：修7处（update_model/add_model放行param_options、ModelParams.options改为可选、resolve取并集、只读/可写统一、新旧选项合并校验、setParam非法提示、示例统一用zhipuai与example逐行对应）
- v1.7 2026-09-22 13:00:00 小欧 一致性二轮核查：补Select字符串强绑定、fixture仅sensenova全补、后端unknown/add_model同步说明、setParam提示文案与越界一致
- v1.8 2026-09-22 13:01:02 小欧 三轮核查完毕：文档与example、DTO、service、hooks、components逻辑链一致性自检通过
- v1.9 2026-09-22 13:02:34 小欧 明确：2.2.1补“需要改动的文件/行”——backend/config.yaml.example zhipuai段实际要增model_params+model_meta及注释，示例明确应加哪些行，并列出零迁移/按需两种情况
- v2.0 2026-09-22 13:02:50 小欧 建议：按实际模型列表明确哪些模型要加。基于config.yaml当前sensenova四模型均有reasoning_effort但无model_meta，零迁移不加；zhipuai.glm-4.7-flash先按3选项示例加，其他provider中有reasoning_effort默认值的模型按需各自加model_meta.param_options，不同模型不同，不强制全加
- v2.1 2026-09-22 13:04:17 小欧 细化2.2.1：列明需要改动的文件/行（backend/config.yaml.example zhipuai段）、明确零迁移模型清单（sensenova四个不加）、按需模型清单及是否加的原则，示例与example文件逐行对应
- v2.2 2026-09-22 13:12:38 小欧 补添加口设计：三、3.3加“添加模型”全链（弹窗模板勾选区、透传、落盘、校验、回显），三、3.4补添加口测试，添加口与参数区同源SSOT（注：该条原文写“三、3.4/3.3”，经v2.6章节重编号后为3.3/3.4）
- v2.3 2026-09-22 13:15:21 小欧 通用参数通路：2.3新增未知类型全覆盖（枚举/数值/布尔/对象/字符串五分支），`isDirty`对象深比较，添加→保存→读出→修改全链同规则（注：新增时编号为2.4，v2.6重编号为2.3）
- v2.4 2026-09-22 13:17:01 小欧 补齐三处缺的diff：3.2(5)补布尔/对象分支代码，3.2新增(6)isDirty深比较diff，3.3补添加弹窗模板区与提交透传关键diff（注：该条的“3.3”指现3.3添加口节）
- v2.5 2026-09-22 13:17:57 小欧 落齐三块diff正文：3.2(5)五分支完整diff、3.2(6)isDirty深比较diff、3.3添加弹窗模板区与提交透传diff（含SettingsPage透传range/capabilities/param_options）（注：“3.3”指现3.3添加口节）
- v2.6 2026-09-22 13:20:37 小欧 一致性8+完整性3整改：版本历史按时间正序；章节重编号（2.4→2.3通用通路、原2.3→2.4，3.4→3.3添加口、3.5→3.4测试）；3.3(2)类型补range/capabilities；Provider级选项写入口（update_provider_config key_map）补齐；2.2示例措辞/对象分支行为/校验范围统一；补齐缺失签名
- v2.7 2026-09-22 13:23:47 小欧 逻辑重排+标题平行：第二章动机前移（2.1原则→2.2动机→2.3契约→2.4配置→2.5类型全覆盖扩展），游离说明并入2.1第4条，3.3改“添加口修改”与兄弟标题平行（旧号映射：原2.2→2.3、原2.2.1→2.4、原2.3→2.5、原2.4→2.2）
- v2.8 2026-09-22 13:27:15 小欧 补2.6修改要点总表：7处断档（API/State类型、hooks四通道、SettingsPage传参、ModelParams可选属性、弹窗模板规则、回显、测试）一行一要点对上3.x diff
- v2.9 2026-09-22 13:30:00 小欧 立核心原则：2.1加第5条完整性铁律（配置有体现→后端读写正常→前端显示修改正常→新增适配多模型→API落盘不错位不丢失不破坏），2.6总表加第16行完整性验收
- v3.0 2026-09-22 13:32:18 小欧 揪出全部代码点：一、1.4新增审计结论24处（3错21缺，逐条文件行号+违哪段原则+对应diff），写路径复用项验明（list叶值直写/None删叶/空dict落空块/锁+备份回滚，无需改）
- v3.1 2026-09-22 13:34:37 小欧 补齐第三章缺的diff：3.1(2)补unknown白名单+落盘hunk、新增3.1(5)add_model完整diff（签名+校验+落盘），3.2(1)(2)(4)补类型diff块，3.2(3)补四通道+setParam完整diff，3.3(1)补模板区diff，3.4(1)补夹具diff
- v3.2 2026-09-22 13:46:00 小欧 二轮十遍核查补漏：新增3.3(5)前端updateModel签名补param_options+3.1(6)POST路由add_model调用透req.param_options，共2处diff缺失补齐；PUT路由model_dump(exclude_none=True)随DTO自动含param_options无需改
- v3.3 2026-09-22 14:02:56 小欧 新增第四章Provider参数问题（除URL/KEY外6处）：timeout兜底不一致（lifecycle/service.py用30，其他用60）、max_retries运行时不消费（base_service.py硬编码3，DTO/TS类型缺字段）、addProvider前端缺timeout/max_retries输入
- v3.4 2026-09-22 14:14:11 小欧 4.1补四种断链说明表：timeout兜底打架（保存✓生效✗三处默认值不一致）、max_retries完全不消费（保存✓运行时硬编码3）、label改不了（保存✓前端无编辑入口）、models创建时丢失（没传✓弹窗无输入框）
- v3.5 2026-09-22 14:18:37 小欧 核查发现现有diff不遵守三层回落原则：4.3(1)create_service_instance写死默认60跳过tuning配置，4.3(2)max_retries无回落链。修正：create_service_instance传None（Provider没设时不传默认值），base_service.py timeout用is not None判断（0是合法值），max_retries加三层回落（Provider > tuning.max_retries > 常量3）
- v3.6 2026-09-22 14:26:43 小欧 补label/models两处diff：4.3(6)label编辑入口（types/useSettings/SettingsPage/ProviderConfig四文件）+4.3(7)addProvider弹窗补timeout/max_retries输入框+models注释说明（创建后通过模型管理UI添加）
- v3.7 2026-09-22 14:47:25 小欧 补两个"后来添加参数"场景UI设计：4.3(8)模型param_options编辑UI（管理选项弹窗，修改允许值列表）+4.3(9)Provider动态参数发现（GET /models返回param_types元数据，ProviderConfig动态渲染）
- v3.8 2026-09-22 14:55:36 小欧 修3处冲突：①4.3(2)中间层key正名tuning.llm.stream_max_retries（registry:157既有，llm_net.max_retries不存在）；②4.3(2)补snapshot()透传max_retries=self.max_retries（跨provider快照否则丢定制值）；③4.3(1)补get_models显示层走同三层+tuning对齐（否则显示60实际150），SettingsPage fallback改150
- v3.9 2026-09-22 14:58:18 小欧 文档改名：reasoning_effort类型错乱根因分析与SSOT根治方案→provider/model前后端读写保存显示全程同步优化（内容覆盖已超单点bug，改名贴合全貌；标题H1同步）
- v4.0 2026-09-22 15:06:24 小欧 补全三缺口：①4.3(9)动态参数读-写-存-显闭环（值随GET /models下发+types/useSettings透传+doSave收集+DTO extra='allow'+param_types白名单防注入）；②4.3(8)删选项致默认值悬空处理（同批回提default_params重置为首项，复用3.1(2)同批合并校验）；③4.4补第8/9条model级运行时消费验证（parse_model_params单测+真实LLM请求体）
- v5.0 2026-09-22 15:12:36 小欧 新增第五章TDD实施流程：5.1铁律+5.2要点↔Case覆盖矩阵（2.6十八行+4.x全映射）+5.3 Case清单（9新4改2回归2E2E）+5.4分九阶段实施计划（第2/3/4章diff台账一个不漏，红→绿→验证门）+5.5手工清单+5.6失败处理

---

## 一、问题现象与病根分析（小欧）

### 1.1 现象（小欧）

配置页面模型参数`reasoning_effort`显示为数字`0`，范围显示“不限”，默认`medium`。用户已修改仍错，期望为字符串`low/medium/high`，默认`medium`。

### 1.2 数据链取证（小欧，只读本地，不断链）

1. 后端值是对的：`frontend/src/tests/fixtures/live-models.json:74-79`中`sensenova/deepseek-v4-flash`为`"default_params": {"reasoning_effort": "medium", "context_limit": 900000}`，字符串类型正确；`"range": {}`为空，`"capabilities": []`为空，无任何`options/enum`字段。
2. 通用设置的`options`与模型参数无关：`frontend/src/tests/fixtures/live-schema.json:188-202,311-320,494-510`中有`options`的仅为`sandbox.backend: ["job_object"]`、`logging.level: ["DEBUG","INFO","WARNING","ERROR"]`、`app.language: ["zh-CN","en-US"]`，`model`组仅`ai.model_ref`且`options:null`。
3. 后端组装出口缺选项：`backend/app/services/model/model_service.py:70-90` `_models_of()`仅从`config.yaml`的`ai.{provider}.model_params`取`params`、从`ai.{provider}.model_meta`取`range/capabilities`，透传组装，不产生`param_options`；`backend/app/api/v1/model_routes.py:32-45` `ModelCreate/UpdateRequest`仅含`label/range/capabilities/default_params`，无选项字段。
4. 前端通道断裂：`frontend/src/features/settings2/hooks/useSettings.ts:173-240（load）、608-650（selectProvider）、655-691（selectModel）、734-783（refreshModels）`仅透`ranges`，无`paramOptions`通道；`frontend/src/features/settings2/components/SettingsPage.tsx:265-271`仅传`params/defaults/ranges/envOverride/onChange`给`ModelParams`。
5. 控件用错为直接病根：`frontend/src/features/settings2/components/ModelParams.tsx:37`为`const value = (params[key] ?? defaults[key]) as number`，`:79-85`为无`range`一律`<InputNumber value={value}/>`。`reasoning_effort`无`range`，字符串`"medium"`被强制断言为`number`塞入`InputNumber`，`Number("medium")=NaN`，回显坍缩为`0`/空白，提交即变数字。

### 1.3 病根结论（小欧）

病根分两层：

- 直接病根：`ModelParams`不区分参数类型，全当数字处理，用错控件。
- 设计病根：`GET /models`从未下发模型参数的合法枚举（SSOT缺失），前端拿不到`["low","medium","high"]`，只能硬编码或误用`InputNumber`。光改前端为`Select`硬编码，下个枚举值、换个`provider`照样翻车。

### 1.4 代码审计结论：26处（3错23缺，小欧）

按2.1第5条完整性铁律逐条揪出，现状代码（未改）核对，`错`=行为错误须改，`缺`=原则要求但代码没有须补：

**错3处（违④⑤）：**

| # | 代码点 | 违原则段 | 对应diff |
|---|---|---|---|
| E1 | `ModelParams.tsx:37 as number` + `:79-85`无`range`一律`InputNumber`，字符串`"medium"`变`0` | ④显示 | 三、3.2(5) |
| E2 | `modelUtils.ts:9-19 isDirty`用`!==`，对象参数恒脏 | ④修改 | 三、3.2(6) |
| E3 | `ModelModals.tsx:63-80 handleAddModel`丢掉已声明的`default_params`，只送3个基本项 | ⑤新增 | 三、3.3(2) |

**缺23处：**

| # | 代码点 | 违原则段 | 对应diff |
|---|---|---|---|
| B1 | `_resolve_param_options`函数不存在 | ②读 | 三、3.1(1) |
| B2 | `_models_of（70-90）`不组装`param_options` | ②读 | 三、3.1(1) |
| B3 | `ModelCreateRequest（model_routes.py:32-38）`无`param_options` | ②③ | 三、3.1(3) |
| B4 | `ModelUpdateRequest`无`param_options` | ②③ | 三、3.1(3) |
| B5 | `add_model（133-136）`签名无`param_options` | ③⑤ | 三、3.1(5) |
| B6 | `unknown`白名单（169）无`param_options` | ③ | 三、3.1(2) |
| B7 | `add_model`无枚举校验 | ③ | 三、3.1(5) |
| B8 | `update_model`无枚举校验 | ③ | 三、3.1(2) |
| B9 | `update_provider_config key_map（264-266）`无`param_options` | ②写 | 三、3.1(4) |
| F1 | `ModelEntry（model.api.ts:8-14）`无`param_options` | ④读 | 三、3.2(1) |
| F2 | `ModelState（types.ts:24-31）`无`paramOptions` | ④ | 三、3.2(2) |
| F3 | `initialModel（useSettings.ts:62-77）`无`paramOptions` | ④ | 三、3.2(3) |
| F4 | `load（173-245）`无通道 | ④ | 三、3.2(3) |
| F5 | `selectProvider（608-653）`无通道 | ④ | 三、3.2(3) |
| F6 | `selectModel（655-694）`无通道 | ④ | 三、3.2(3) |
| F7 | `refreshModels(select)（734-790）`无通道 | ④⑤ | 三、3.2(3)/3.3(4) |
| F8 | `setParam（698-728）`无枚举拦截 | ④ | 三、3.2(3) |
| F9 | `SettingsPage.tsx:265-271`未传`options` | ④ | 三、3.2(4) |
| F10 | `ModelModals.tsx:123-143`无参数模板区 | ⑤ | 三、3.3(1) |
| F11 | `SettingsPage.tsx:360-367`+`model.api.ts:59-69`未透`range/capabilities/param_options` | ⑤③ | 三、3.3(2) |
| T1 | `live-models.json`无`param_options`夹具 | ④验 | 三、3.4(1) |
| B10 | `model_routes.py:66-67` POST路由`add_model`调用不透`req.param_options` | ③⑤ | 三、3.1(6) |
| F12 | `model.api.ts:71-83` `updateModel`的`Pick`不含`param_options` | ③⑤ | 三、3.2(7) |

**验明复用、无需改（违③写安全，已有实现）：**`config_helpers.py:460-527`落盘链路——`merge_nested_patch`叶段字面名写（点号模型名不拆散）、`None`删叶并回收空父级、空dict落`{}`空块（P8）、`list`按叶值直写（`param_options`数组天然适配）、`filelock`并发锁+备份+完整性校验+原子写+失败回滚。`param_options`读写复用此链路，只需三、3.1的字段透传与校验，不动落盘核心。

---

## 二、SSOT根治设计（小欧）

### 2.1 设计原则（小欧）

1. 后端为枚举唯一来源（SSOT），前端只渲染不定义。
2. 全链只用字符串`value`，禁止`indexOf/[idx]/as number`等位置代表值的映射。
3. 前后兼容：老前端忽略新字段，新后端默认值兜底。
4. 文档约定：本章配置写法以`backend/config.yaml.example`（zhipuai段）为准，文档2.4示例与该文件同构；先看example文件，再看设计。
5. 完整性铁律（核心原则）：`model`参数设置五段必须闭环——①配置文件有体现（`model_params`存值+`model_meta.param_options`存选项）；②后端读正常（三层解析进`GET /models`）；③后端写正常（`merge_nested_patch`叶级写，不错位、不丢兄弟键、不破坏文件，写前校验、写后带`mtime`）；④前端显示修改正常（五分支渲染+深比较脏态）；⑤新增适配多模型（弹窗模板候选=同Provider并集，提交经API校验落盘）。任一段断即整体不合格。

### 2.2 为什么必须先补后端（小欧）

前端`if (key === 'reasoning_effort')`白名单是补丁：新增`xhigh`、某模型仅`low/high`、第三方调用传`0`时全部失效。只有后端下发`param_options`，前端`options[key]`才有真相源，`Select value === option.value`字符串精确匹配，回显不可能出`0`。

### 2.3 契约设计（v1.1修正：按模型可配，小欧）

`GET /models`每个`model`新增字段，按该模型实际允许值下发，不同模型可3/4/5个不同（读：`GET`回显消费；写：`POST/PUT`允许写`model_meta.param_options`，新模型建选项用；老前端忽略，不报错）：

```json
"param_options": {"reasoning_effort": ["low", "medium", "high"]}
```

- 类型固定`Record<string, string[]>`，`value`与`default_params`同类型（字符串）。
- 有该`key`前端走`Select`，无则走老分支（`range`→`Slider+InputNumber`，`number`→`InputNumber`，`string`→`Input`）。
- 选项来源三层解析（优先级从高到低），v1.0写死`PARAM_ENUMS`全局表作废：
  1. 模型级：`config.yaml`中`ai.{provider}.model_meta.{model}.param_options.{param}`，如某新模型配5个，与走兜底得3个的`sensenova/deepseek-v4-flash`互不干扰。
  2. Provider级（可选）：`ai.{provider}.param_options.{param}`，同`provider`下未单独配置的模型共用；写入口为`PUT /providers/{name}`（`update_provider_config`的`key_map`加`param_options`，见三、3.1(4)），不写则该层缺省。
  3. 全局默认（代码兜底）：`DEFAULT_PARAM_OPTIONS = {"reasoning_effort": ["low", "medium", "high"]}`，`config`两层都缺时兜底，保证现网`sensenova`四模型（`config.yaml:26-38`仅有`model_params`无`model_meta`）零迁移即有正确下拉。
- `update_model`按该模型解析出的`options`做值校验：本次提交的`default_params`值不在`options`内直接400，不落盘，避免脏值入库（已落盘旧值不追溯）。

### 2.4 配置文件要加什么（小欧）

结论：现状模型零迁移，只有选项特殊的模型才加。

```yaml
# config.yaml现状（config.yaml:26-38）：sensenova四模型（deepseek-v4-flash/glm-5.2/sensenova-6.8-flash-lite/deepseek-v4-pro）均有model_params.reasoning_effort但无model_meta.param_options
# 结论：sensenova四模型零迁移，不加model_meta；zhipuai.glm-4.7-flash如需固定选项范围，按示例加model_meta.param_options；其他provider中有reasoning_effort的模型按需各自加，不强制全加。
sensenova:
  model_params:
    deepseek-v4-flash: {reasoning_effort: medium, context_limit: 900000}
    # 其余三个同上，无需加model_meta

# 需要改动的文件/行（backend/config.yaml.example）：zhipuai段补model_params.glm-4.7-flash.reasoning_effort: medium + model_meta.glm-4.7-flash.param_options三选项（或按需3/4/5个）。示例如下：
zhipuai:
  model_params:
    glm-4.7-flash: {reasoning_effort: medium}
  model_meta:
    glm-4.7-flash: # 3个选项（生效示例；该模型需要限定范围时才加）
      param_options:
        reasoning_effort: [low, medium, high]
    # model-4opt: # 4个选项（按需照抄，仅当模型支持4个时加）
    #   param_options:
    #     reasoning_effort: [low, medium, high, xhigh]
    # model-5opt: # 5个选项（按需照抄，仅当模型支持5个时加）
    #   param_options:
    #     reasoning_effort: [low, medium, high, xhigh, ultra]
```

说明：零迁移模型（sensenova四个）不加；需要限定`reasoning_effort`可选范围的模型才在其`model_meta.{model}.param_options`加行。`deepseek-v4-flash`（`config.yaml:26-38`）不写，走兜底得3个。

注意：光加YAML不够，后端`model_service.py:70-90`必须先支持三层解析并透到`GET /models`，否则加了前端也收不到（见三、3.1）。

标准写法以`backend/config.yaml.example`（zhipuai段，2026-09-22 小欧）为准：`model_params`放当前值，`model_meta.{model}.param_options`放该模型选项单子，3/4/5个各写各的，不写`model_meta`的走兜底。

### 2.5 类型全覆盖扩展（小欧，未知类型全覆盖）

已知仅2种（`reasoning_effort`枚举 + `context_limit`整数，`config.yaml:26-60`实测），但`parse_model_params（service.py:87-97）`把`context_limit`弹出后余量整体透传`extra_body`，`model_params`是开放字典（如`enable_thinking`、`thinking_budget`、`chat_template_kwargs`），以后厂商加什么都可能。通路规则（新增→保存→读出→修改全链同规则）：

1. 有`param_options[key]`→`Select`字符串直绑（枚举型）。
2. 有`range[key]`→`Slider+InputNumber`（数值范围型）。
3. 值为`number`→`InputNumber`；为`boolean`→`Switch`；为对象→`textarea(JSON)`+解析失败不写`state`（`blur`回退默认值，见三、3.2(5)diff；对象型如`chat_template_kwargs`，禁`String(obj)`/`Number(obj)`）。
4. 其余字符串→`Input`。
5. `isDirty`对对象用`JSON.stringify`深比较（`modelUtils.ts:9-19`现`!==`对对象恒脏）。
6. `add_model`/`update_model`校验：枚举值必须在该模型`param_options`内，`0`直接400；非枚举只判类型不判值。

### 2.6 修改要点总表（小欧）

一行一要点，每个要点都能在第三章找到对应diff，文件行号以现状为准：

| # | 要点 | 对应diff | 文件 |
|---|---|---|---|
| 1 | 后端组装出口派生`param_options`（三层解析，并集） | 三、3.1(1) | `model_service.py:49-90` |
| 2 | `update_model`按模型合并校验+白名单放行 | 三、3.1(2) | `model_service.py:164-184` |
| 3 | DTO透传`param_options` | 三、3.1(3) | `model_routes.py:32-45` |
| 4 | Provider级写入口`key_map`加`param_options` | 三、3.1(4) | `model_service.py:259-277` |
| 5 | `ModelEntry`加`param_options?` | 三、3.2(1) | `model.api.ts:8-14` |
| 6 | `ModelState`加`paramOptions` | 三、3.2(2) | `types.ts:24-31` |
| 7 | 四处通道补`paramOptions`+`setParam`非法提示 | 三、3.2(3) | `useSettings.ts:228-243/631-641/676-680/764-771/698-728` |
| 8 | 参数区传入`options` | 三、3.2(4) | `SettingsPage.tsx:265-271` |
| 9 | 五分支渲染+`options?`可选+`onReset?` | 三、3.2(5) | `ModelParams.tsx:17-85` |
| 10 | `isDirty`对象深比较 | 三、3.2(6) | `modelUtils.ts:9-19` |
| 11 | 弹窗模板区（候选并集/默认值/切Provider重置） | 三、3.3(1) | `ModelModals.tsx:123-143` |
| 12 | 提交透传`default_params/range/capabilities/param_options` | 三、3.3(2) | `ModelModals.tsx:63-80`、`SettingsPage.tsx:360-367`、`model.api.ts:59-69` |
| 13 | `add_model`落盘`param_options`+同规则校验 | 三、3.1(5) | `model_service.py:133-161` |
| 14 | 建完回显补`paramOptions` | 三、3.3(4) | `useSettings.ts:734-783` |
| 15 | 夹具/单测/后端测试/手工/添加口验证 | 三、3.4(1)-(5) | 见3.4 |
| 16 | 完整性验收（核心原则第5条）：配置有值有选项→读写正常→显示修改正常→新增多模型适配→API落盘不错位不丢失 | 三、3.4(4)(5)+2.1(5) | `config.yaml`+全链 |
| 17 | POST路由`add_model`调用透`param_options` | 三、3.1(6) | `model_routes.py:63-68` |
| 18 | `updateModel`签名Pick补`param_options` | 三、3.2(7) | `model.api.ts:71-83` |

---

## 三、精确修改diff与验证（小欧）

### 3.1 后端修改（小欧）

（1）`backend/app/services/model/model_service.py:49-90`：全局默认仅兜底，选项按模型解析（小欧 v1.1）。

```diff
 RESERVED_AI_KEYS = {"provider", "model", "model_ref"}
+# v1.1：仅全局兜底默认，不同模型3/4/5个选项走config覆盖，不写死（小欧 2026-09-22）
+DEFAULT_PARAM_OPTIONS: Dict[str, List[str]] = {
+    "reasoning_effort": ["low", "medium", "high"],
+}
+def _resolve_param_options(ai, provider, model, params, meta) -> Dict[str, List[str]]:
+    out: Dict[str, List[str]] = {}
+    # 并集：params已有值 ∪ meta已配选项，避免有选项无默认值时下发丢失（小欧 2026-09-22）
+    for k in list(params) + [k for k in (meta.get("param_options") or {}) if k not in params]:
+        mo = (meta.get("param_options") or {}).get(k)  # 1.模型级最高
+        po = ((ai.get(provider) or {}).get("param_options") or {}).get(k)  # 2.provider级
+        go = DEFAULT_PARAM_OPTIONS.get(k)  # 3.全局兜底
+        v = mo if mo is not None else (po if po is not None else go)
+        if isinstance(v, list) and v:
+            out[k] = list(v)
+    return out
-            "capabilities": meta.get("capabilities") or [],
+            "capabilities": meta.get("capabilities") or [],
+            "param_options": _resolve_param_options(ai, provider, m, params, meta),
```

原因：`_models_of`仍为唯一组装出口；`config.yaml:26-38`现无`model_meta`，靠全局兜底零迁移；要给某模型配4/5个选项时，只在`ai.{provider}.model_meta.{model}.param_options`加YAML即可，不改代码。`add_model`签名加`param_options`形参并写`model_meta`，`update_model`白名单`unknown`加`param_options`并写`model_meta`（否则送了即报“不支持的配置项”，见(2)(3)）。

（2）`backend/app/services/model/model_service.py:164-184` `update_model`按该模型选项校验。

```diff
     dp = fields.get("default_params")
     if isinstance(dp, dict):
+        # v1.6：先合并本次新选项再校验，避免同批改选项+改值时用旧单子误杀（小欧 2026-09-22）
+        cur = next((x for x in _models_of(ai, provider) if x["name"] == model), None) or {}
+        allowed = dict(cur.get("param_options") or {})
+        if isinstance(fields.get("param_options"), dict):
+            for k, v in fields["param_options"].items():
+                if isinstance(v, list) and v:
+                    allowed[k] = list(v)
+        for k, v in dp.items():
+            if k in allowed and v not in allowed[k]:
+                raise ValueError(f"不支持的配置项值: {k}={v!r}，允许{allowed[k]}")
+    # 白名单放行+落model_meta（小欧；unknown/loop为现状上下文行，仅首行改动）
+    unknown = set(fields) - {"label", "range", "capabilities", "default_params", "param_options"}  # 改：+param_options
     for k in ("label", "range", "capabilities"):  # 现状行
         if fields.get(k) is not None:  # 现状行
             node.setdefault("model_meta", {}).setdefault(model, {})[k] = fields[k]  # 现状行
+    if isinstance(fields.get("param_options"), dict):  # 增：选项表落model_meta
+        node.setdefault("model_meta", {}).setdefault(model, {})["param_options"] = fields["param_options"]
```

原因：不同模型允许值不同，全局表会误杀；按模型校验，`0`照样拦住，5选项模型传第5个合法值可放行。同时`unknown`白名单必须加`param_options`，`add_model`签名同步加形参，否则(3)的DTO字段接不住（见(5)）。

（3）`backend/app/api/v1/model_routes.py:32-45` DTO透传。

```diff
 class ModelCreateRequest(BaseModel):
     capabilities: List[str] = ...
+    param_options: Optional[Dict[str, List[str]]] = None
 class ModelUpdateRequest(BaseModel):
     ...
+    param_options: Optional[Dict[str, List[str]]] = None
```

原因：Pydantic不声明即丢字段；声明后老前端不送也不报错。

（4）`backend/app/services/model/model_service.py:259-277` Provider级选项写入口（小欧 v2.6，三层第2层无写即空谈）：

```diff
     key_map = {"api_key": "api_key", "base_url": "api_base", "api_base": "api_base",
                "timeout": "timeout", "retry_times": "max_retries", "max_retries": "max_retries",
-               "label": "label"}
+               "label": "label", "param_options": "param_options"}
```

原因：`update_provider_config`白名单不加，`ai.{provider}.param_options`只能手改YAML；加后`PUT /providers/{name} {param_options: {...}}`可写，与模型级同校验规则（值必须为非空`string[]`）。

（5）`backend/app/services/model/model_service.py:133-161 add_model`完整diff（小欧 v3.1，签名+校验+落盘三件齐）：

```diff
-def add_model(provider: str, model: str, label: str = "",
-              default_params: Optional[Dict[str, Any]] = None,
-              range_: Optional[Dict[str, Any]] = None,
-              capabilities: Optional[List[str]] = None) -> Dict[str, Any]:
+def add_model(provider: str, model: str, label: str = "",
+              default_params: Optional[Dict[str, Any]] = None,
+              range_: Optional[Dict[str, Any]] = None,
+              capabilities: Optional[List[str]] = None,
+              param_options: Optional[Dict[str, List[str]]] = None) -> Dict[str, Any]:
     ...
+    # 与update_model同规则：选项表须为非空string[]，值须在表内，0直接400（小欧）
+    allowed = dict(param_options or {})
+    for k, vs in allowed.items():
+        if not isinstance(vs, list) or not vs or not all(isinstance(x, str) for x in vs):
+            raise ValueError(f"不支持的选项表: {k}须为非空string[]")
+    for k, v in (default_params or {}).items():
+        allow = allowed.get(k, DEFAULT_PARAM_OPTIONS.get(k))
+        if allow is not None and v not in allow:
+            raise ValueError(f"不支持的配置项值: {k}={v!r}，允许{allow}")
     tree: Dict[str, Any] = {
         "ai": {provider: {
             "models": models,
             "model_params": {model: default_params or {}},
             "model_meta": {model: {
                 "label": label or model,
                 "range": range_ or {},
                 "capabilities": capabilities or [],
+                **({"param_options": param_options} if param_options else {}),
             }},
         }}
     }
```

原因：新建即带选项+值，入口与修改口同规则；不送`param_options`与现状`{}`兼容。

（6）`backend/app/api/v1/model_routes.py:63-68` POST路由`add_model`调用透`param_options`（小欧 v3.2）：

```diff
 @router.post("/models")
 @handle_config_errors("添加模型")
 async def add_model(req: ModelCreateRequest):
     return svc.add_model(req.provider, req.model, req.label,
-                         req.default_params, req.range, req.capabilities)
+                         req.default_params, req.range, req.capabilities,
+                         req.param_options)
```

原因：DTO（3.1(3)）声明了`param_options`字段，但POST路由调用`svc.add_model`时 positional args不传该值，`param_options`形参永远拿到`None`，落盘静默丢。与(5)签名改动联动——(5)签名末尾加了`param_options`，路由必须同步传。

注：PUT路由无需改——`model_routes.py:75`用`req.model_dump(exclude_none=True)`构建`fields`字典，`ModelUpdateRequest`加`param_options`后`model_dump`自动包含，`update_model`的`fields`自然有该key，经(2)的`unknown`白名单放行+校验+落盘，链路闭合。

### 3.2 前端修改（小欧）

（1）`frontend/src/services/api/model.api.ts:8-14`：

```diff
 export interface ModelEntry {
   name: string;
   label: string;
   default_params: Record<string, unknown>;
   range: Record<string, { min: number; max: number }>;
   capabilities: string[];
+  param_options?: Record<string, string[]>;
 }
```

（2）`frontend/src/features/settings2/types.ts:24-31`：

```diff
 export interface ModelState {
   providers: ProviderEntry[];
   selectedProvider: string;
   selectedModel: string;
   params: Record<string, unknown>;
   defaults: Record<string, unknown>;
   ranges: Record<string, { min: number; max: number }>;
+  paramOptions: Record<string, string[]>;
   envOverride: Record<string, boolean>;
   ...
```

（3）`frontend/src/features/settings2/hooks/useSettings.ts`：`initialModel`加`paramOptions: {}`；`load:228-243`、`selectProvider:631-641`、`selectModel:676-680`、`refreshModels:764-771`四处同构补`paramOptions: {...((current?.param_options ?? {}) as Record<string,string[]>) }`；`setParam:698-728`加`const opts = state.model.paramOptions[key]; if (opts && !opts.includes(value as string)) { showMessage(ErrorType.WARNING, ...); return; }`

原因：当前仅透`ranges`为断点，不补通道后端下了也到不了UI；`setParam`拦截保证非法枚举不写`state`，且与同函数越界`showMessage`一致，禁止静默return。

```diff
 const initialModel = () => ({
   ...
   ranges: {},
+  paramOptions: {},
   envOverride: {},
   ...
 // load:228-243（selectProvider:631-641、selectModel:676-680、refreshModels:764-771同构，源换first/entry/m）
               ranges: {
                 ...((current?.range ?? {}) as Record<string, { min: number; max: number }>),
               },
+              paramOptions: {
+                ...((current?.param_options ?? {}) as Record<string, string[]>),
+              },
 // setParam:698-728（依赖数组同步加state.model.paramOptions）
       if (state.model.envOverride[key]) return;
+      const opts = state.model.paramOptions[key];
+      if (opts && !opts.includes(value as string)) {
+        showMessage(ErrorType.WARNING, `参数 ${key} 为非法选项，允许：${opts.join('/')}`);
+        return;
+      }
       const range = state.model.ranges[key];
```

附：`selectModel`先取`const nextOptions = { ...(entry.param_options ?? {}) }`再`paramOptions: nextOptions`。

（4）`frontend/src/features/settings2/components/SettingsPage.tsx:265-271`：

```diff
       <ModelParams
         params={state.model.params}
         defaults={state.model.defaults}
         ranges={state.model.ranges}
+        options={state.model.paramOptions}
         envOverride={state.model.envOverride}
         onChange={s.setParam}
       />
```

（5）`frontend/src/features/settings2/components/ModelParams.tsx:17-85`五分支完整diff（小欧 v2.5，枚举/数值/布尔/对象/字符串，未知类型全覆盖）：

```diff
-import { InputNumber, Slider } from 'antd';
+import { Input, InputNumber, Select, Slider, Switch } from 'antd';
 interface Props {
   params: Record<string, unknown>;
   defaults: Record<string, unknown>;
   ranges: Record<string, { min: number; max: number }>;
+  options?: Record<string, string[]>;
   envOverride: Record<string, boolean>;
   onChange: (key: string, value: unknown) => void;
+  onReset?: (key: string) => void;
 }
-        const value = (params[key] ?? defaults[key]) as number;
+        const rawValue = params[key] ?? defaults[key];
+        const enumOpts = (options ?? {})[key];
+        const numValue = typeof rawValue === 'number' ? rawValue : Number(rawValue);
-            {range ? (
+            {range ? ( // 数值范围型：Slider+InputNumber，字符串安全转数字
-                   value={value}
+                   value={isNaN(numValue) ? range.min : numValue}
-            ) : (
-              <InputNumber value={value} disabled={envKey} onChange={(v) => onChange(key, v)} />
-            )}
+            ) : enumOpts ? ( // 枚举型：Select字符串直绑，禁indexOf/[idx]
+              <Select options={enumOpts.map((v) => ({ label: v, value: v }))}
+                value={typeof rawValue === 'string' ? rawValue : String(rawValue ?? '')}
+                disabled={envKey} style={{ minWidth: 120 }} onChange={(v) => onChange(key, v)} />
+            ) : typeof rawValue === 'number' ? ( // 数值型
+              <InputNumber value={rawValue} disabled={envKey} onChange={(v) => onChange(key, v)} />
+            ) : typeof rawValue === 'boolean' ? ( // 布尔型
+              <Switch checked={rawValue} disabled={envKey} onChange={(v) => onChange(key, v)} />
+            ) : rawValue !== null && typeof rawValue === 'object' ? ( // 对象型：textarea(JSON)，禁String(obj)
+              <Input.TextArea value={JSON.stringify(rawValue ?? null)}
+                disabled={envKey} autoSize
+                onChange={(e) => { try { onChange(key, JSON.parse(e.target.value)); } catch { /* 输入中，blur时提示 */ } }}
+                onBlur={(e) => { try { JSON.parse(e.target.value); } catch { onChange(key, defaults[key]); } }} />
+            ) : ( // 字符串型
+              <Input value={String(rawValue ?? '')} disabled={envKey} onChange={(e) => onChange(key, e.target.value)} />
+            )}
```

要点：删`as number`类型谎言；`Select`的`value/options[].value/onChange`全程字符串；对象分支`JSON.parse`失败不写`state`（`blur`回退默认值），`Number("medium")`链路彻底删除。

（6）`frontend/src/features/settings2/utils/modelUtils.ts:9-19`深比较diff（小欧 v2.5，对象参数`!==`恒脏必修）：

```diff
+function sameValue(a: unknown, b: unknown): boolean {
+  if (Object.is(a, b)) return true;
+  if (a !== null && b !== null && typeof a === 'object' && typeof b === 'object') {
+    try { return JSON.stringify(a) === JSON.stringify(b); } catch { return false; }
+  }
+  return false;
+}
-    out[key] = !env[key] && params[key] !== defaults[key];
+    out[key] = !env[key] && !sameValue(params[key], defaults[key]);
```

（7）`frontend/src/services/api/model.api.ts:71-83` `updateModel`签名补`param_options`（小欧 v3.2）：

```diff
   updateModel: async (
     provider: string,
     model: string,
     data: Partial<
-      Pick<ModelEntry, 'label' | 'default_params' | 'range' | 'capabilities'>
+      Pick<ModelEntry, 'label' | 'default_params' | 'range' | 'capabilities' | 'param_options'>
     >
   ): Promise<ModelMutationResult> => {
```

原因：`ModelEntry`加了`param_options?`（3.2(1)），但`updateModel`的`Pick`不含它，TS类型不接受`param_options`字段，前端修改模型选项时传了也编译不过。与3.1(3) DTO + 3.1(2) `update_model`校验联动——后端已接收+校验+落盘，前端API层必须同步放开类型。

注：`model.api.ts:59-69`的`addModel`入参已为内联类型字面量（非`Pick`），3.3(2)的diff直接加了`param_options?`字段，无此问题。

### 3.3 添加口修改：添加模型时特定参数在哪处理（小欧）

现状断点：`ModelModals.tsx:123-143`表单仅`Provider/模型名/显示名`，`handleAddModel:63-80`丢掉`default_params`；`SettingsPage.tsx:360-367`仅透`default_params`；`model.api.ts:59-69`与`model_routes.py:32-38 ModelCreateRequest`、`model_service.py:133-161 add_model`均无`param_options`；`refreshModels(select):734-783`回显不补`paramOptions`。新模型建出即`default_params={}`且无选项，必回参数区返工。

设计（与参数区同源SSOT，不硬编码）：

（1）弹窗加“参数模板（勾选即带入）”（`ModelModals.tsx:123-143`后新增区块）：候选项=所选Provider下已有模型`default_params ∪ param_options` key并集（如切sensenova自动列`reasoning_effort/context_limit`）；每行`Checkbox`+值控件，有`param_options`走`Select`字符串直绑，纯数字走`InputNumber`，其他走`Input`；默认值取同Provider兄弟模型`default_params`，无则取全局兜底（`reasoning_effort→medium`）；切换Provider重算候选并清空已勾。

```diff
 // ModelModals.tsx：模板区state（与mForm/mProvider同级，Checkbox勾选+值收集）
+  const sibModels = (providers.find((p) => p.name === mProvider)?.models ?? []);
+  const candKeys = Array.from(new Set(sibModels.flatMap((m) => [
+    ...Object.keys(m.default_params ?? {}), ...Object.keys(m.param_options ?? {}),
+  ])));
+  const [checked, setChecked] = useState<Record<string, boolean>>({});
+  const [collected, setCollected] = useState<{ params: Record<string, unknown>; options: Record<string, string[]> }>({ params: {}, options: {} });
+  // 切Provider重算并清空已勾（与BUG-A的mProvider联动放一处）
+  useEffect(() => { setChecked({}); setCollected({ params: {}, options: {} }); }, [mProvider]);
 // 模板区每行：<Checkbox checked onChange=toggle> + 值控件（opts=兄弟模型param_options[k]；有则Select/数字InputNumber/其他Input；默认值取兄弟default_params[k]，无则reasoning_effort→medium）
 // handleAddModel成功后同mForm.resetFields一起：setChecked({}); setCollected({ params: {}, options: {} });
```

（2）提交透传（`ModelModals.tsx:63-80` + `SettingsPage.tsx:360-367` + `model.api.ts:59-69`）关键diff（小欧 v2.5）：

```diff
 // ModelModals.tsx:26-31 Props（range/capabilities与SettingsPage透传对齐，否则d.range必TS报错）
   onSubmitAddModel: (data: {
     provider: string;
     model: string;
     label: string;
     default_params?: Record<string, unknown>;
+    range?: Record<string, { min: number; max: number }>;
+    capabilities?: string[];
     param_options?: Record<string, string[]>;
   }) => Promise<void>;
 // ModelModals.tsx:63-80 handleAddModel（模板区勾选项由新增state collected:{params,options}供给）
-      await props.onSubmitAddModel({ provider: mProvider, model: v.model, label: v.label ?? v.model });
+      await props.onSubmitAddModel({
+        provider: mProvider, model: v.model, label: v.label ?? v.model,
+        ...(Object.keys(collected.params).length ? { default_params: collected.params } : {}),
+        ...(Object.keys(collected.options).length ? { param_options: collected.options } : {}),
+      });
 // SettingsPage.tsx:360-367（range/capabilities/param_options一并透传，不再只透default_params）
-            const res = await modelApi.addModel({ provider: d.provider, model: d.model, label: d.label,
-              ...(d.default_params ? { default_params: d.default_params } : {}) });
+            const res = await modelApi.addModel({ provider: d.provider, model: d.model, label: d.label,
+              ...(d.default_params ? { default_params: d.default_params } : {}),
+              ...(d.range ? { range: d.range } : {}),
+              ...(d.capabilities ? { capabilities: d.capabilities } : {}),
+              ...(d.param_options ? { param_options: d.param_options } : {}) });
 // model.api.ts:59-69 addModel入参加param_options?: Record<string, string[]>
```

模板区规则：候选=所选Provider已有模型`default_params ∪ param_options` key并集；有选项走`Select`、数字走`InputNumber`、其他走`Input`；默认值取兄弟模型`default_params`、无则`reasoning_effort→medium`兜底；切Provider重算并清空已勾；不勾=不送该key（与现状`{}`兼容）。

（3）后端落盘（`model_routes.py:32-38` + `model_service.py:133-161`）：`ModelCreateRequest`加`param_options`字段；`add_model`签名加`param_options`形参并写`ai.{provider}.model_meta.{model}.param_options`，与`update_model`同写位；`add_model`加与`update_model`同规则的按模型枚举校验（`default_params`值必须在本次`param_options ∪ 解析后options`内，`0`直接400，弹窗不关）。

（4）建完回显（`useSettings.ts:734-783 refreshModels(select)`）：按`m.param_options`补`paramOptions`，与`load/selectProvider/selectModel`同构，切到新模型参数区即有下拉，不再`InputNumber`吃字符串。

### 3.4 测试与验证（小欧）

1. `frontend/src/tests/fixtures/live-models.json`给`sensenova`四个模型（`deepseek-v4-flash/glm-5.2/sensenova-6.8-flash-lite/deepseek-v4-pro`）全补`"param_options": {"reasoning_effort": ["low","medium","high"]}`，缺一个即切到该模型无下拉。其他provider的模型若无枚举不加。

```diff
           "default_params": {
             "reasoning_effort": "medium",
             "context_limit": 900000
           },
+          "param_options": {"reasoning_effort": ["low", "medium", "high"]},
           "range": {},
           "capabilities": []
```

（注：四个`sensenova`模型同理共四处；`agnes`等无枚举模型不加。）
2. `settings2-live-scenarios.test.tsx:91-110` BUG-E保留，加断言：`options`来自`fixture`，`Select`显示`medium`，`setParam('reasoning_effort','x')`被拒。
3. 后端加`test_model_param_options`：`get_models`含`param_options`，`update_model default_params:{reasoning_effort:0}`报400。
4. 手工：切`sensenova/deepseek-v4-flash`下拉显示`medium`非`0`；改`high`保存Network为字符串`"high"`；刷新仍`high`；`config.yaml`落盘字符串。
5. 添加口：sensenova下新建模型，勾选`reasoning_effort=high`+`context_limit=900000`保存，`POST /models`体含字符串`"high"`；非法值（如`0`）后端400弹窗不关；建完自动切新模型，参数区即有下拉且值为所勾值；`config.yaml`中新模型`model_params`与`model_meta.param_options`同时落盘。

---

## 四、Provider特殊参数问题与修复（小欧，除URL/KEY外）

第三章解决了model级参数的SSOT问题。本章解决Provider级参数（除`api_base`/`api_key`外）的遗留问题。

### 4.1 问题清单（小欧）

按2.1第5条完整性铁律逐条核对现状代码（未改），8处问题：

| # | 代码点 | 问题 | 违原则段 |
|---|---|---|---|
| P1 | `lifecycle/service.py:113` timeout兜底`30` | `get_models()`对外返回`60`，实际运行时用`30`，显示值≠实际值；且`create_service_instance`写死默认值跳过tuning配置层 | ②读③写 |
| P2 | `base_service.py:98-109` `__init__`无`max_retries`参数 | 运行时完全不消费Provider级`max_retries`，前端可编辑但改了没用；且`create_service_instance`不传max_retries给BaseAIService | ③写 |
| P3 | `base_service.py:300` `max_retries`硬编码`_D_STREAM_MAX_RETRIES`（常量3） | 用户在前端改`max_retries=5`，实际重试仍是3；无三层回落链（Provider > tuning > 常量） | ③写 |
| P4 | `model_routes.py:48-54` `ProviderConfigUpdate` DTO缺`max_retries`字段 | DTO只有`retry_times`，前端发`max_retries`靠key_map别名绕过，类型不一致 | ②③ |
| P5 | `model.api.ts:43-49` `ProviderConfigPatch` TS类型缺`max_retries` | 接口只有`retry_times`，前端`ProviderConfig.tsx:52-53`实际发送`max_retries`，TS类型保护失效 | ④ |
| P6 | `model.api.ts:98-103` `addProvider`签名缺`timeout`/`max_retries` | 创建Provider时不传这两个值，全走后端默认值（60/3），前端无法在创建时自定义 | ⑤ |
| P7 | `types.ts:32-41` + `ProviderConfig.tsx`无label编辑入口 | providerConfig state无label字段，ProviderConfig无label输入框，创建后无法通过UI修改显示名 | ②③ |
| P8 | `model.api.ts:98-103` + `ModelModals.tsx:170-187` addProvider弹窗缺timeout/max_retries | 创建Provider时无法自定义这两个值，全走后端默认值 | ⑤ |

注：P4的DTO虽然缺`max_retries`字段，但`model_dump(exclude_none=True)`把前端传的`max_retries`原样透传到`update_provider_config`的`fields`，key_map有`max_retries→max_retries`映射，所以**写入链路碰巧能工作**——但这是绕过类型系统的隐式行为，不是正确设计。

**四种断链类型总结：**

| 问题 | 保存到config.yaml | 运行时生效 | 断链类型 | 根因 |
|------|:-:|:-:|:-:|------|
| timeout | ✓ | **兜底值打架** | 保存✓生效✗ | `lifecycle/service.py:113`兜底30，`get_models()`兜底60，`base_service.__init__`兜底150，三处三个数字；用户改了timeout的Provider没问题（链路完整），**没改的才出问题**（显示60实际30） |
| max_retries | ✓ | **完全不消费** | 保存✓运行时忽略 | config.yaml写了`max_retries:5`，但`create_service_instance()`不传给BaseAIService，`base_service.py:300`硬编码用常量3；用户改了白改 |
| label | ✓ | **改不了** | 保存✓前端无入口 | 后端`key_map`有`label→label`支持修改，但`ProviderConfig.tsx`没有label输入框，创建后无法通过UI编辑 |
| models | **没传** | **创建时丢失** | 弹窗缺字段 | 后端`ProviderAddRequest` DTO支持`models`字段，但`ModelModals.tsx`弹窗无models输入框，创建时只能传name/label/api_base/api_key，models走默认空列表 |

### 4.2 设计原则（小欧）

1. **兜底值统一**：Provider参数在所有读写点使用同一默认值，杜绝显示值≠运行时值。
2. **运行时必须消费配置值**：前端可编辑的参数，后端运行时必须真正使用，禁止硬编码常量。
3. **DTO与TS类型对齐**：前后端类型定义必须覆盖实际发送的所有字段。
4. **创建时可设**：Provider创建弹窗和API签名必须包含所有可配置参数。
5. **Provider级优先三级回落**（与model参数三层解析同思路）：`Provider设了 → 用Provider的值`；`Provider没设 → 回落到系统级配置（tuning）`；`系统级也没设 → 回落到代码常量`。禁止在`create_service_instance`写死默认值跳过tuning配置层。

### 4.3 精确修改diff（小欧）

（1）`backend/app/services/lifecycle/service.py:106-119` timeout传None（不传默认值，让BaseAIService走三层回落）：

```diff
     return BaseAIService(
         api_key=...,
         llm_model=...,
-        timeout=provider_config.get("timeout", 30),
+        timeout=provider_config.get("timeout"),  # None=未设，BaseAIService回落到tuning>常量
```

```diff
 # base_service.py:131-135 __init__ timeout回落链：
         try:
-            timeout_value = float(timeout) if timeout else float(get_config().get("tuning.llm_net.read_timeout", _D_READ_TIMEOUT))
+            timeout_value = float(timeout) if timeout is not None else float(get_config().get("tuning.llm_net.read_timeout", _D_READ_TIMEOUT))
         except (ValueError, TypeError):
             timeout_value = float(get_config().get("tuning.llm_net.read_timeout", _D_READ_TIMEOUT))
         self.timeout = int(timeout_value)
```

原因：原来`if timeout`用truthiness判断，`timeout=0`是合法值（极短超时）但被当falsy跳到tuning层。改`is not None`后：Provider设了任意值（含0）→直接用；Provider没设（None）→读tuning配置→没配→常量150。三层回落链完整。

```diff
 # model_service.py:93-105 get_models()显示值走同三层（小欧 v3.8：否则显示60实际150，第3章"显示即真相"被打破）
+from app.config import get_config  # config_helpers同层已引，无循环
-                           "timeout": p.get('timeout') if p.get('timeout') is not None else 60,
-                           "max_retries": p.get('max_retries') if p.get('max_retries') is not None else 3,
+                           "timeout": p.get('timeout') if p.get('timeout') is not None else get_config().get("tuning.llm_net.read_timeout", 150),
+                           "max_retries": p.get('max_retries') if p.get('max_retries') is not None else get_config().get("tuning.llm.stream_max_retries", 3),
```

```diff
 # SettingsPage.tsx:278-284 fallback对齐tuning默认（小欧 v3.8：缺省条目才触发，平时走API值）
               api_key: { configured: false, suffix: '' },
               base_url: '',
-              timeout: 60,
+              timeout: 150,
               max_retries: 3,
               env: false,
```

（2）`backend/app/llm/base_service.py` + `lifecycle/service.py` max_retries三层回落：

```diff
 # base_service.py:98-109 __init__
     def __init__(
         self,
         api_key: str,
         llm_model: ModelRef,
         timeout: int = _D_READ_TIMEOUT,
+        max_retries: Optional[int] = None,  # None=未设，回落到tuning>常量
         ...
     ):
         ...
         self.timeout = int(timeout_value)
+        # max_retries三层回落：Provider值 > tuning配置 > 常量（小欧 2026-09-22）
+        if max_retries is not None:
+            self.max_retries = max_retries
+        else:
+            self.max_retries = int(get_config().get("tuning.llm.stream_max_retries", _D_STREAM_MAX_RETRIES))
```

```diff
 # base_service.py:299-300 request_stream()
-        max_retries = _D_STREAM_MAX_RETRIES
+        max_retries = self.max_retries
```

```diff
 # base_service.py:173-184 snapshot()透传（小欧 v3.8：快照常切跨provider模型，不传则丢provider定制值）
         snap = BaseAIService(
             api_key=api_key or self.api_key,
             llm_model=model_ref if model_ref is not None else self.llm_model,
             timeout=self.timeout,
+            max_retries=self.max_retries,
             max_tokens=self.max_tokens,
             ...
```

```diff
 # lifecycle/service.py:106-119 create_service_instance()
     return BaseAIService(
         api_key=...,
         llm_model=...,
         timeout=provider_config.get("timeout"),
+        max_retries=provider_config.get("max_retries"),  # None=未设，BaseAIService回落到tuning>常量3
         ...
     )
```

原因：原来`create_service_instance`不传max_retries，`base_service.py:300`硬编码用常量3。修复后Provider设了→用Provider的；Provider没设→读`tuning.llm.stream_max_retries`（系统级可配）；tuning也没配→常量3。三层回落完整，与timeout同构。中间层用既有键`tuning.llm.stream_max_retries`（registry:157，默认3）——`tuning.llm_net.max_retries`不存在，误引则中间层永死。`snapshot()`同步透传，否则跨provider快照丢定制值。

（3）`backend/app/api/v1/model_routes.py:48-54` `ProviderConfigUpdate` DTO补`max_retries`：

```diff
 class ProviderConfigUpdate(BaseModel):
     label: Optional[str] = Field(default=None, description="Provider 显示名")
     api_key: Optional[str] = Field(default=None)
     base_url: Optional[str] = Field(default=None)
     timeout: Optional[int] = Field(default=None)
     retry_times: Optional[int] = Field(default=None)
+    max_retries: Optional[int] = Field(default=None)
     clear: Optional[bool] = Field(default=None, description="clear=true 显式清空 api_key")
```

原因：前端`ProviderConfig.tsx:52-53`发送`max_retries`，但DTO只有`retry_times`。靠`model_dump(exclude_none=True)`透传碰巧能工作，但类型不一致。补字段后前端发`max_retries`直连key_map，不再依赖隐式绕过。

（4）`frontend/src/services/api/model.api.ts:43-49` `ProviderConfigPatch` TS类型补`max_retries`：

```diff
 export interface ProviderConfigPatch {
   api_key?: string;
   base_url?: string;
   timeout?: number;
   retry_times?: number;
+  max_retries?: number;
   clear?: boolean;
 }
```

原因：`ProviderConfig.tsx:52-53`实际发送`max_retries`但TS类型无此字段，类型保护失效。补后与实际行为一致。

（5）`frontend/src/services/api/model.api.ts:98-103` + `ModelModals.tsx:32-37` + `ModelModals.tsx:170-187` `addProvider`补`timeout`/`max_retries`：

```diff
 // model.api.ts:98-103 addProvider签名
   addProvider: async (data: {
     name: string;
     label?: string;
     api_base?: string;
     api_key?: string;
+    timeout?: number;
+    max_retries?: number;
   }): Promise<ModelMutationResult> => {

 // ModelModals.tsx:32-37 Props.onSubmitAddProvider类型
   onSubmitAddProvider: (data: {
     name: string;
     label: string;
     api_base: string;
     api_key?: string;
+    timeout?: number;
+    max_retries?: number;
   }) => Promise<void>;

 // ModelModals.tsx:170-187 弹窗表单区块（在api_key输入框后新增两项）
+      <Form.Item label="timeout(秒)" name="timeout">
+        <InputNumber min={1} placeholder="默认60" />
+      </Form.Item>
+      <Form.Item label="max_retries" name="max_retries">
+        <InputNumber min={0} placeholder="默认3" />
+      </Form.Item>
```

原因：创建Provider时无法自定义timeout/max_retries，全走后端默认值。补后创建弹窗可设，API签名可传，与后端`ProviderAddRequest` DTO（config_schemas.py:117-118，已有timeout=60/max_retries=3默认值）对齐。

（6）label编辑入口（`types.ts` + `useSettings.ts` + `SettingsPage.tsx` + `ProviderConfig.tsx`，四文件联动）：

```diff
 # types.ts:32-41 providerConfig类型
   providerConfig: Record<
     string,
     {
       api_key: { configured: boolean; suffix: string };
       base_url: string;
+      label: string;
       timeout: number;
       max_retries: number;
       env: boolean;
     }
   >;
```

```diff
 # useSettings.ts:178-189 load()构建providerConfig
   const providerConfig = Object.fromEntries(
     models.providers.map((p) => [
       p.name,
       {
         api_key: p.api_key,
         base_url: p.api_base,
+        label: p.label,
         timeout: p.timeout,
         max_retries: p.max_retries,
         env: p.env,
       },
     ])
   );
```

```diff
 # SettingsPage.tsx:278-284 ProviderConfig fallback
   state.model.providerConfig[state.model.selectedProvider] ?? {
     api_key: { configured: false, suffix: '' },
     base_url: '',
+    label: '',
     timeout: 60,
     max_retries: 3,
     env: false,
   }
```

```diff
 # ProviderConfig.tsx:18-36 Props定义
   interface Props {
     name: string;
     config: {
       api_key: { configured: boolean; suffix: string };
       base_url: string;
+      label: string;
       timeout: number;
       max_retries: number;
       retry_times?: number;
       env: boolean;
     };
     onSave: (patch: {
       api_key?: string;
       base_url?: string;
+      label?: string;
       timeout?: number;
       retry_times?: number;
       max_retries?: number;
       clear?: boolean;
     }) => Promise<void>;
   }
```

```diff
 # ProviderConfig.tsx:42-64 doSave构建patch
   const doSave = async () => {
     const values = await form.validateFields();
     const patch: Record<string, unknown> = {};
     if (values.api_key !== undefined && String(values.api_key).trim() !== '')
       patch.api_key = values.api_key;
     if (values.base_url !== undefined)
       patch.base_url = String(values.base_url).trim();
+    if (values.label !== undefined && String(values.label).trim() !== '')
+      patch.label = String(values.label).trim();
     if (values.timeout !== undefined) patch.timeout = values.timeout;
     if (values.max_retries !== undefined)
       patch.max_retries = values.max_retries;
```

```diff
 # ProviderConfig.tsx:78-119 表单区块（在base_url后新增label输入框）
   <Form.Item label="base_url" name="base_url" extra="留空=清空地址（恢复默认直连）">
     <Input />
   </Form.Item>
+  <Form.Item label="显示名" name="label" extra="Provider显示名称，留空=保持原值">
+    <Input />
+  </Form.Item>
   <Form.Item label="timeout" name="timeout">
```

原因：后端`key_map`有`label→label`支持修改，`ProviderConfigUpdate` DTO有`label`字段，但前端无编辑入口。补后可在Provider配置区修改显示名，与后端写链路闭合。

（7）`models`创建时处理说明：后端`ProviderAddRequest` DTO（config_schemas.py:116）已有`models: list[str]`字段，`add_provider()`（model_service.py:249-251）已支持models列表写入config.yaml。前端创建弹窗不加models输入框——模型列表通过②模型管理区的"添加模型"按钮逐个添加（已有完整UI），创建Provider时通常还不知道要挂哪些模型。如需批量设置，可直接编辑config.yaml的`ai.{provider}.models`列表。

（8）模型param_options编辑UI——"管理选项"弹窗（小欧 v3.7，场景：模型升级后修改允许值列表）：

**场景**：模型创建时配了`reasoning_effort: [low, medium, high]`，后来模型升级支持`xhigh`，需加第4个选项。

**UI位置**：模型Tab → ②参数区 → 标题行右侧，与"重置为默认"同排。仅当当前模型有`param_options`时显示"管理选项"链接。

**弹窗设计**：

```
┌─ Modal: 管理参数选项 ──────────────────────────────────┐
│  width: 480px                                           │
│  标题: "管理 {model} 的参数选项"                         │
│                                                         │
│  ┌─ 参数行: reasoning_effort ─────────────────────────┐ │
│  │  标签名: [low] [medium] [high] [×]                 │ │
│  │  添加: [输入新值...] [添加]                         │ │
│  │  说明: "保存后生效，已有参数值不做校验"              │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ 参数行: (其他有param_options的参数) ──────────────┐ │
│  │  同上结构                                          │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  按钮: [保存] [取消]                                    │
│  保存调用: update_model(provider, model,                │
│            {param_options: {reasoning_effort: [....]}}) │
│  保存后: 刷新state.paramOptions → ModelParams下拉联动   │
└─────────────────────────────────────────────────────────┘
```

**交互规则**：
- 候选参数 = `state.model.paramOptions`的所有key（即当前模型的param_options）
- 每个参数显示已有值为Tag，Tag可删除（×）
- 输入框+添加按钮：新值须为非空字符串，重复值禁止
- 保存前校验：每个参数至少保留1个值（空列表禁止）
- 保存后：`update_model`写入config.yaml的`model_meta.{model}.param_options`，刷新`state.model.paramOptions`，ModelParams的Select下拉立即联动

```diff
 # SettingsPage.tsx:②参数区标题行（约line 218-230）
   <SectionTitle
     title={`② 参数（${state.model.selectedModel}）`}
     extra={
       <>
+        {Object.keys(state.model.paramOptions).length > 0 && (
+          <Button type="link" size="small" onClick={() => setParamOptionsModalOpen(true)}>
+            管理选项
+          </Button>
+        )}
         {state.model.isDirty && (
           <Button type="link" size="small" danger onClick={handleResetParams}>
             重置为默认
           </Button>
         )}
       </>
     }
   />
```

```diff
 # types.ts ModelState 加弹窗控制
+  paramOptionsModalOpen: boolean;
```

```diff
 # ParamOptionsModal.tsx（新组件，约120行）
 // Props: {open, model, paramOptions, onClose, onSave}
 // onSave调用: modelApi.updateModel(provider, model, {param_options: newOptions})
 // 保存后回调: 刷新state.model.paramOptions
```

原因：param_options是模型元数据的一部分，修改允许值列表是管理员常见操作（模型升级、厂商调整参数范围）。放在参数区标题行右侧，与"重置为默认"同级，位置合理——用户在参数区发现选项不够时，视线自然扫到标题行的管理入口。

**悬空值处理（小欧 v4.0，删选项致当前默认值不再合法时）：**

场景：当前`defaults.reasoning_effort="high"`，管理员在管理选项里删掉`high`。若只提交`param_options`、不碰`default_params`，保存后Select的value=high不在新options内，下拉无高亮、回显悬空。

修复（复用3.1(2)同批合并能力，零后端改动）：管理选项弹窗`onSave`保存前交叉校验——对每个改了`param_options`的key，若`defaults[key]`存在且不在新列表内，弹`Modal.confirm`："默认值 {key}='{旧值}' 不在新选项内，是否重置为该参数第一选项 '{新列表[0]}'？"。确认→同批提交`{param_options: 新表, default_params: {..., [key]: 新列表[0]}}`；取消→不保存并停留在弹窗。

```diff
 # ParamOptionsModal.tsx onSave（保存前交叉校验，小欧 v4.0）
 -  onSave调用: modelApi.updateModel(provider, model, {param_options: newOptions})
 +  // 1. 排查每个改动过的key，defaults[key]是否仍在新列表内
 +  const dangling = toChangedKeys.find(
 +    (k) => defaults[k] !== undefined && !newOptions[k].includes(defaults[k])
 +  );
 +  if (dangling) {
 +    Modal.confirm({
 +      title: `默认值 ${dangling}='${defaults[dangling]}' 不在新选项内`,
 +      content: `将重置为 '{newOptions[dangling][0]}'，继续？`,
 +      onOk: async () => {
 +        await modelApi.updateModel(provider, model, {
 +          param_options: newOptions,
 +          default_params: { ...defaults, [dangling]: newOptions[dangling][0] },
 +        });
 +        onSaveDone(); // 刷新 paramOptions + defaults
 +      },
 +    });
 +    return;
 +  }
 +  // 2. 无悬空：仅提交param_options
 +  await modelApi.updateModel(provider, model, { param_options: newOptions });
```

关键点：`param_options`+`default_params`同批提交正好走3.1(2)的"先合并本次新选项再校验"逻辑（allow合并新表→`dangling`新值=首项必然在新列表内→校验通过），校验与落盘天然自洽，不需要后端额外分支。回显层（ModelParams Select）新选项内含该值，无悬空。

（9）Provider动态参数发现——完整读-写-存-显闭环（小欧 v3.7起，v4.0补全）：

**场景**：Provider以后可能新增参数（如`rate_limit`、`max_concurrent`），当前UI硬编码了timeout/max_retries/label，新参数无法被发现和编辑。

**设计原则**：元数据（参数名/类型/标签）由后端一处声明，前端只渲染不定义；新参数的值随`GET /models`正常下发、随`PUT /providers`正常落盘，前端不做任何硬编码。新增参数只需后端：①常量表加一行元数据 ②`config.yaml`加字段 ③零改前端。

**1. 元数据源头（后端常量表，不塞config避免配置膨胀）：**

```python
# model_service.py 模块常量区（小欧 v4.0）
PROVIDER_PARAM_TYPES: Dict[str, Dict[str, Any]] = {
    "timeout":     {"type": "number", "label": "超时(秒)", "min": 1, "default": 60},
    "max_retries": {"type": "number", "label": "重试次数", "min": 0, "default": 3},
    "label":       {"type": "string", "label": "显示名"},
    # 新增Provider参数：在此加一行 + config.yaml对应provider加字段，前后端自动适配，不再改前端代码
    # "rate_limit": {"type": "number", "label": "速率限制", "min": 0, "default": 0},
}
KNOWN_PROVIDER_KEYS = {"name", "api_base", "api_key", "env", "models", "param_types"}
```

**2. 读链（`GET /models`→config state→Form回填，v4.0补值通道）：**

```json
{
  "name": "sensenova",
  "timeout": 60, "max_retries": 3, "label": "商汤", "rate_limit": 10,
  "param_types": {
    "timeout": {"type": "number", "label": "超时(秒)", "min": 1, "default": 60},
    "max_retries": {"type": "number", "label": "重试次数", "min": 0, "default": 3},
    "label": {"type": "string", "label": "显示名"},
    "rate_limit": {"type": "number", "label": "速率限制", "min": 0, "default": 0}
  },
  "models": [ ... ]
}
```

```diff
 # model_service.py get_models() Provider段（v4.0：元数据 + 动态值一并下发）
         "max_retries": <三层解析值>,
+        "param_types": PROVIDER_PARAM_TYPES,
+        **{k: v for k, v in p.items()
+           if k not in KNOWN_PROVIDER_KEYS and isinstance(v, (str, int, float, bool))},  # 动态值透传
         "models": <models>,
```

```diff
 # model.api.ts ProviderEntry 加param_types
   export interface ProviderEntry {
     name: string;
     label: string;
     api_base: string;
     api_key: { configured: boolean; suffix: string };
     env: boolean;
     timeout: number;
     max_retries: number;
     models: ModelEntry[];
+    param_types?: Record<string, { type: string; label: string; min?: number; default?: unknown }>;
   }
```

```diff
 # types.ts providerConfig 每条加动态索引（v4.0：rate_limit等新参数类型收容）
       {
         api_key: { configured: boolean; suffix: string };
         base_url: string;
         label: string;
         timeout: number;
         max_retries: number;
         env: boolean;
+        [key: string]: unknown;  // 动态参数（param_types驱动）
       }
```

```diff
 # useSettings.ts load()构建providerConfig（v4.0：动态值从provider对象透传）
         {
           api_key: p.api_key,
           base_url: p.api_base,
           label: p.label,
           timeout: p.timeout,
           max_retries: p.max_retries,
           env: p.env,
+          // 动态参数值透传：跳过已具名+元数据+列表类，其余标量照抄
+          ...Object.fromEntries(
+            Object.entries(p as Record<string, unknown>).filter(([k]) =>
+              !['name', 'label', 'api_base', 'api_key', 'timeout',
+                'max_retries', 'env', 'models', 'param_types'].includes(k)
+            )
+          ),
         }
```

回填点：`ProviderConfig.tsx:82` `initialValues={{ ...config, api_key: undefined }}`已把整个config展开进Form——动态字段只要进了`config`即自动回填，无需额外代码。

**3. 写链（前端patch收集 → DTO放行 → 后端白名单落盘，v4.0补收集）：**

```diff
 # ProviderConfig.tsx doSave（v4.0：param_types驱动的新参数收集进patch）
     if (values.max_retries !== undefined)
       patch.max_retries = values.max_retries;
+    // 动态参数收集：已有静态字段skip，param_types里其余字段值非undefined送patch
+    for (const k of Object.keys(config.param_types ?? {})) {
+      if (STATIC_KEYS.has(k)) continue;
+      if (values[k] !== undefined) patch[k] = values[k];
+    }
```

```diff
 # ProviderConfig.tsx 动态渲染区（v3.7已有，值回填走initialValues天然生效）
   {/* 已有字段: api_key / base_url / label / timeout / max_retries（硬编码） */}
+  {/* 动态字段: param_types中除已有字段外的新参数 */}
+  {Object.entries(config.param_types ?? {}).map(([key, meta]) =>
+    EXISTING_KEYS.has(key) ? null : (
+      <Form.Item key={key} label={meta.label} name={key}>
+        {meta.type === 'number' ? (
+          <InputNumber min={meta.min} />
+        ) : meta.type === 'boolean' ? (
+          <Switch />
+        ) : (
+          <Input />
+        )}
+      </Form.Item>
+    )
+  )}
```

```diff
 # model_routes.py:17 import 补ConfigDict（v4.0：动态字段放行必须的pydantic配置）
-from pydantic import BaseModel, Field
+from pydantic import BaseModel, ConfigDict, Field
 # ProviderConfigUpdate 加 extra='allow'（v4.0：静态字段仍强类型，动态字段放行）
 class ProviderConfigUpdate(BaseModel):
+    model_config = ConfigDict(extra='allow')
     label: Optional[str] = Field(default=None)
     ...
```

```diff
 # model_service.py update_provider_config() 循环前加param_types白名单（v4.0：防任意键注入）+动态落盘
+    if isinstance(fields, dict):
+        unknown_key = next(
+            (k for k in fields if k not in set(key_map) and k not in PROVIDER_PARAM_TYPES), None
+        )
+        if unknown_key:
+            raise ValueError(f"不支持的Provider配置项: {unknown_key}")
     for k, v in fields.items():
         if k not in key_map: continue
         ...
+    # 动态参数落盘：key_map遍历后，param_types内的动态字段写 config.yaml 的 ai.{provider}.{k}
+    for k, v in fields.items():
+        if k in PROVIDER_PARAM_TYPES and k not in key_map:
+            node.setdefault("ai", {}).setdefault(provider, {})[k] = v
```

原因：动态字段在DTO声明会违背"前端零改代码"初衷（每个新参数都改DTO）。`extra='allow'`一行放行未知字段，静态字段（label/timeout/max_retries）仍强类型校验，两条合流。后端白名单以`PROVIDER_PARAM_TYPES`为界——不在元数据表的键拒绝落盘，杜绝注入。动态参数走`merge_nested_patch`叶值写入（复用1.4已验证链路），标量类型直写无拆散风险。

**4. 存（mtime+锁+备份回滚，复用已有链路）：** 第3步节点写复用`merge_nested_patch`叶级原子写（锁+备份+回滚，1.4验明），`mtime`校验并发。`onSave`成功后父级`refreshModels`（或重拉`GET /models`）刷新，动态值回显即最新。

**5. 测试（4.4第10条）：** 后端`config.yaml` sensenova加`rate_limit: 10`→`GET /models`该provider返回`rate_limit: 10`+`param_types.rate_limit`→前端ProviderConfig自动渲染InputNumber且值回填10→改20保存→`PUT /providers`体含`rate_limit: 20`→落盘`config.yaml`→重拉显示20（闭环）。

原因：v3.7只给了渲染骨架，"读"（值回填）和"写"（patch收集+落盘）都断。本次补全后动态参数也成为完整四段闭环：元数据常量表→值下发透传→表单回填→patch收集→DTO放行→白名单落盘→重拉回显。新增参数真正只需要动后端两处（常量表+config.yaml），前端零改。

### 4.4 测试与验证（小欧）

1. **timeout三层回落**：Provider设timeout=45→运行时用45；Provider不设timeout+tuning设read_timeout=80→运行时用80；Provider不设+tuning也不设→运行时用150（常量）；三档下`GET /models`返回值与运行时一致（显示即真相）。
2. **max_retries三层回落**：Provider设max_retries=5→运行时重试5次；Provider不设+tuning.llm.stream_max_retries设8→运行时重试8次；Provider不设+tuning也不设→运行时重试3次（常量）；三档下`GET /models`返回值与运行时一致。
3. **timeout=0合法值**：Provider设timeout=0→不被跳过，直接传入BaseAIService（极短超时场景）。
4. **DTO类型对齐**：`PUT /providers/{name} {max_retries: 5}`直接调API，落盘成功（不再依赖retry_times别名）。
5. **创建可设**：添加Provider弹窗填写timeout=30/max_retries=5，保存后`config.yaml`落盘对应值，`GET /models`返回所填值。
6. **param_options编辑**：模型参数区点击"管理选项"→弹窗显示当前`[low,medium,high]`→添加`xhigh`→保存→`GET /models`返回4个选项→ModelParams的Select下拉立即出现`xhigh`。
7. **Provider动态参数**：后端config.yaml加`rate_limit: 10`→`GET /models`返回`param_types.rate_limit`→ProviderConfig自动渲染InputNumber→保存→落盘成功。
8. **model级运行时消费（v4.0补，第3章链路的运行时闭环）**：`parse_model_params`（lifecycle/service.py:87-97）单测——config.yaml `ai.{provider}.model_params.{m}.reasoning_effort="high"`（字符串）→ 返回`extra_body_params={"reasoning_effort": "high"}`（字符串，非数字）；`context_limit`弹出逻辑不伤余量；`create_service_instance`构造时`extra_body_params=该返回值`透传给BaseAIService（lifecycle/service.py:105/117）。
9. **model级端到端运行时（v4.0补）**：真实后端改`sensenova`某模型`reasoning_effort=high`保存→真实LLM调用（E2E幂等用例或手工+请求日志断言）请求体携带`reasoning_effort="high"`字符串；与第3章显示/落盘构成"配置→保存→显示→运行时消费"四段全通。
10. **Provider动态参数闭环（v4.0补，走通4.3(9)五步）**：config.yaml sensenova加`rate_limit: 10`→`GET /models`返回`rate_limit: 10`+`param_types`→ProviderConfig渲染InputNumber**且值回填10**→改20保存→落盘20→重拉显示20；另验白名单：`PUT /providers/sensenova {evil_key: 1}`→400（不在param_types拒绝）。

---

## 五、TDD实施流程（小欧）

### 5.1 TDD方法铁律（小欧）

1. **真实环境，禁止Mock**（AGENTS.md铁律）：后端单测可mock `config`对象内存态（`test_model_service_tdd.py`现有风格），但落盘、`GET /models`、`parse_model_params`、LLM请求体必须真实config/真实后端/真实LLM；E2E一律真实后端+真实SQLite（`~/.omniagent/chat_history.db`）。禁止为通过测试伪造数据通路。
2. **TDD三步循环**：①先写会失败的测试（红）→②改对应diff的最小代码→③测试变绿；红→绿一次一跳，严禁一次改多个diff不跑测试。
3. **一次只跑一个case**（AGENTS.md铁律），严禁批量；E2E用`subprocess.Popen`方式跑（bash工具会强杀长时进程），stdout/stderr落盘`tests/output/`，结果查junitxml；harness见`backend/e2etests/全链路E2E测试手册-小健-2026-05-23.md`（v2.8）。
4. **验证门**：每阶段绿后必过——①pytest/vitest该case绿②既有回归不破（RG-01/02）③`npm run check`（lint+format:check）④手工清单（5.5）抽检。任一门未过禁止进入下一阶段。
5. **提交规范**：每阶段绿且验证门过→提交，格式`<type>:<文件名> <description> - 小欧-<日期>`；禁提交测试代码；版本收尾统一走`version.txt`+打tag。
6. **失败处置**：红测试7天不绿/卡阶段→回退到上一绿基线重查该阶段diff与测试断言的匹配，**禁止`git checkout`/`git reset --hard`/`git revert`**（AGENTS.md禁止），用新增补丁修复。

### 5.2 要点↔Case覆盖矩阵（无遗漏证明，小欧）

每个设计要点都唯一映射到测试Case，双向覆盖；行来自第2.6修改要点总表（18行）+第4章各diff，列=Case编号（见5.3）。

| 要点（设计出处） | 对应diff | Case | 阶段 |
|---|---|---|---|
| 2.4 配置文件示例（model_params+model_meta） | config.yaml.example zhipuai段 | BY-01前置+RL-01 | P1 |
| 2.6-1 后端组装出口派生param_options三层并集 | 三、3.1(1) | BY-01 | P1 |
| 2.6-2 update_model合并校验+白名单放行 | 三、3.1(2) | BY-01 | P1 |
| 2.6-3 DTO透传param_options | 三、3.1(3) | BY-01 | P1 |
| 2.6-4 Provider级写入口key_map加param_options | 三、3.1(4) | BY-03 | P1 |
| 2.6-13 add_model落盘+同规则校验 | 三、3.1(5) | BY-02 | P2 |
| 2.6-17 POST路由透req.param_options | 三、3.1(6) | BY-02（含POST层） | P2 |
| 2.6-5 ModelEntry加param_options | 三、3.2(1) | FF-02 | P3 |
| 2.6-6 ModelState加paramOptions | 三、3.2(2) | FF-02 | P3 |
| 2.6-7 四处通道+setParam拦截 | 三、3.2(3) | FF-02 | P3 |
| 2.6-8 参数区传入options | 三、3.2(4) | FF-02 | P3 |
| 2.6-9 五分支渲染+options可选 | 三、3.2(5) | FF-02 | P4 |
| 2.6-10 isDirty对象深比较 | 三、3.2(6) | FF-02 | P4 |
| 2.6-18 updateModel签名Pick补param_options | 三、3.2(7) | FF-02 | P5 |
| 2.6-11 弹窗模板区 | 三、3.3(1) | E2E-01 | P5 |
| 2.6-12 提交透传default_params/range/capabilities/param_options | 三、3.3(2) | E2E-01 | P5 |
| 2.6-14 建完回显补paramOptions | 三、3.3(4) | E2E-01 | P5 |
| 2.6-15/16 夹具/完整性验收 | 三、3.4(1)-(5) | FF-01+RG+E2E-01 | P3/P10 |
| 4.2-1 兜底值统一（get_models三层对齐） | 四、4.3(1)c | BY-04+RG-03 | P7 |
| 4.2-2 运行时消费（timeout is not None） | 四、4.3(1)a/b | BY-04 | P7 |
| 4.2-3 DTO与TS对齐（max_retries） | 四、4.3(3)(4) | BY-06+RG-03 | P6 |
| 4.2-4 创建时可设（addProvider timeout/max_retries） | 四、4.3(5) | BY-07 | P6 |
| 4.2-5 三层回落（max_retries Provider>tuning>常量） | 四、4.3(2)a/b/d | BY-05 | P7 |
| 4.3(2)c snapshot透传max_retries | 四、4.3(2)c | BY-05 | P7 |
| 4.3(6) label编辑入口四文件 | 四、4.3(6) | BY-06+RG-03 | P6 |
| 4.3(7) models创建说明（无代码） | — | E2E-02 | P6 |
| 4.3(8) 管理选项弹窗+悬空值处理 | 四、4.3(8) | FF-03 | P8 |
| 4.3(9) 动态参数闭环（常量表/下发/透传/收集/白名单/落盘） | 四、4.3(9) | BY-09+FF-04+E2E-02 | P8 |
| 4.4-8/9 model级运行时消费 | — | BY-08+E2E-01 | P9 |
| 4.4-10 动态参数闭环+白名单 | — | BY-09+FF-04 | P8 |
| 完整性铁律2.1(5)（读写保存显示全闭合+落盘不错位） | 全部 | RG+E2E-01/02 | P10 |

### 5.3 Case清单：要修正/更新的case + 新建case（小欧）

**修正4个（现有case改动）：**

| 编号 | 文件 | 修正内容 | 依据 |
|---|---|---|---|
| FF-01 | `frontend/src/tests/fixtures/live-models.json` | 给`sensenova`四模型（deepseek-v4-flash/glm-5.2/sensenova-6.8-flash-lite/deepseek-v4-pro）各补`"param_options": {"reasoning_effort": ["low","medium","high"]}` | 三、3.4(1) |
| FF-02 | `frontend/src/tests/unit/settings2-live-scenarios.test.tsx:91-110` BUG-E | 保留原有"字符串被当number"断言（防回退），**新增**：`options`来自fixture的`param_options`；`Select`显示`medium`（非0）；`setParam('reasoning_effort','x')`被拒（非法选项拦截）；`setParam('reasoning_effort','high')`合法放行 | 三、3.4(2) |
| FF-03 | `backend/tests/test_model_service_tdd.py` 既有断言对齐 | timeout显示值从硬编码60→tuning对齐（若存在断言60处更新为150/80/实际值）；key_map新增`param_options`/`max_retries`映射后既有PUT用例参数表核对 | 四、4.3(1)c |
| FF-04 | 前端全量快照/断言（如有SettingsPage/ProviderConfig相关） | max_retries/label新增字段后，任何硬编码60、缺label的mock对象断言同步 | 四、4.3(5)(6) |

**新建9个case（红→绿）：**

| 编号 | 文件 | Case | 红条件（先写失败测什么） | 断言（绿）要点 |
|---|---|---|---|---|
| BY-01 | `backend/tests/test_model_service_tdd.py` | `test_model_param_options` | 现状`_models_of`不产`param_options`→断言空即红 | 三层解析：模型级`model_meta`覆盖provider级/全局；sensenova零迁移走`DEFAULT_PARAM_OPTIONS`得3选项；并集（params已有值∪meta选项）；`update_model default_params:{reasoning_effort:0}`→400；5选项模型传第5合法值放行 |
| BY-02 | 同上 | `test_add_model_param_options` | 现状`add_model`无param_options形参→签名缺失即红 | 带options新建→`model_meta.{model}.param_options`落盘；round-trip `GET /models`读回；非法选项表/`0`值→400弹窗不关；POST路由层透传 |
| BY-03 | 同上 | `test_param_options_provider_roundtrip` | `update_provider_config` key_map无param_options→PUT不落盘即红 | `PUT /providers/{name} {param_options:{...}}`→`ai.{provider}.param_options`落盘+读回；与模型级同校验 |
| BY-04 | 同上 | `test_timeout_three_tier` | 现状timeout=0被当falsy跳过、get_models兜底60≠150 | Provider设45→45；不设+tuning 80→80；不设+tuning无→150；timeout=0合法直传；三档`GET /models`显示值=运行时值 |
| BY-05 | 同上 | `test_max_retries_three_tier` | 现状base_service无max_retries参数→None即红 | Provider 5→`self.max_retries=5`；不设+tuning.llm.stream_max_retries 8→8；不设无→3；`snapshot()`结果max_retries一致；`request_stream`用self.max_retries |
| BY-06 | 同上 | `test_provider_config_dto_align` | DTO缺max_retries、label——直接PUT断言 | `PUT /providers/{name} {max_retries:5}`落盘（不再靠retry_times别名）；`{label:"新名"}`落盘并读回；`evil_key:1`→400白名单拒绝 |
| BY-07 | 同上 | `test_add_provider_fields` | addProvider DTO/服务无timeout/max_retries | 创建带timeout=30/max_retries=5→`config.yaml`落盘→`GET /models`读回30/5 |
| BY-08 | 同上 | `test_parse_model_params_runtime` | 无此单测 | `model_params.{m}.reasoning_effort="high"`→`extra_body_params`含字符串`"high"`（非数字）；context_limit弹出不伤余量；无model_params→`extra_body_params=None` |
| BY-09 | 同上 | `test_param_types_whitelist` | 无白名单概念→`evil_key`未拒绝 | `get_models` Provider段含`param_types`+动态标量值（rate_limit:10）；`PUT {evil_key:1}`→400；`{rate_limit:20}`→落盘读回20 |

**回归2个（全量门）：**

| 编号 | 命令 | 用途 |
|---|---|---|
| RG-01 | `pytest`（backend工作目录） | 后端全量回归，确认无既有用例被新diff破坏 |
| RG-02 | `npm run test`（frontend工作目录）+`npm run check` | 前端全量+lint+format:check，提交前必过 |

**E2E 2个case（真实全链路）：**

| 编号 | 场景 | 完整链路 |
|---|---|---|
| E2E-01 | 模型链（3.4手工5项转脚本） | 弹窗模板勾选`reasoning_effort=high`+`context_limit=900000`→POST体含字符串`"high"`→`config.yaml`落盘model_params+model_meta.param_options→切新模型参数区下拉+值=high→重启后端读回→真实LLM请求体断言`reasoning_effort="high"`（4.4-9） |
| E2E-02 | Provider链 | 创建provider带timeout=30/max_retries=5→落盘→GET /models读回→改label/动态rate_limit→保存→重拉回显→（无LLM诉求，纯配置链） |

### 5.4 实施计划：分九阶段，第2/3/4章diff台账一个不漏（小欧）

每阶段含：**先写红测试 → 改本阶段diff → 跑绿 → 验证门**。diff编号即本设计文档对应块，按P1→P9顺序执行，严禁越序。

**阶段P1 · 第2章配置+第3章后端读链（红：BY-01）**

| 步骤 | diff清单（一个不漏） |
|---|---|
| 改 | 第2.4 `backend/config.yaml.example` zhipuai段（`model_params.glm-4.7-flash.reasoning_effort: medium`+`model_meta.glm-4.7-flash.param_options`三选项） |
| 改 | 三、3.1(1) `model_service.py`：`DEFAULT_PARAM_OPTIONS`+`_resolve_param_options(ai,provider,model,params,meta)`+`_models_of`组装`param_options` |
| 改 | 三、3.1(2) `model_service.py update_model`：合并新options再校验（先合并→allowed→逐k校验）+`unknown`白名单加`param_options`+落`model_meta` |
| 改 | 三、3.1(3) `model_routes.py`：`ModelCreateRequest`/`ModelUpdateRequest`各加`param_options: Optional[Dict[str,List[str]]]=None` |
| 改 | 三、3.1(4) `model_service.py key_map`：加`"param_options": "param_options"` |
| 改 | 三、3.1(6) `model_routes.py` POST路由：`add_model(..., req.param_options)` |
| 验 | BY-01 绿 + RG-01 不破 + 手工：sensenova开关参数区有下拉 |

**阶段P2 · 第3章后端写链（红：BY-02）**

| 步骤 | diff清单 |
|---|---|
| 改 | 三、3.1(5) `add_model`签名加`param_options`+选项表校验（非空string[]/默认值在表内/0拒）+`tree`写`model_meta.{model}.param_options` |
| 验 | BY-02 绿（含POST路由层透传断言）+ RG-01 + 手工：POST /models带options落盘yaml可见 |

**阶段P3 · 第3章前端读链（红：FF-02，前置FF-01）**

| 步骤 | diff清单 |
|---|---|
| 改夹具 | 三、3.4(1) `live-models.json` sensenova四模型补`param_options`（FF-01，缺一个即切该模型无下拉） |
| 改 | 三、3.2(1) `model.api.ts ModelEntry` 加`param_options?` |
| 改 | 三、3.2(2) `types.ts ModelState` 加`paramOptions` |
| 改 | 三、3.2(3) `useSettings.ts`：`initialModel`加`paramOptions:{}`+`load/selectProvider/selectModel/refreshModels`四通道补`paramOptions`+`setParam`枚举拦截（`opts.includes(value)`不中→WARNING+return） |
| 改 | 三、3.2(4) `SettingsPage.tsx:265-271` 传`options={state.model.paramOptions}` |
| 验 | FF-02 绿 + RG-02 + 手工：切sensenova下拉显示medium |

**阶段P4 · 第3章前端渲染+脏态（红：FF-02新增断言）**

| 步骤 | diff清单 |
|---|---|
| 改 | 三、3.2(5) `ModelParams.tsx` 五分支：删`as number`；`enumOpts→Select(string直绑)`；`range→Slider+InputNumber(安全转数字)`；`number→InputNumber`；`boolean→Switch`；`object→TextArea(JSON)+blur回退`；`string→Input`；Props加`options?`/`onReset?` |
| 改 | 三、3.2(6) `modelUtils.ts` `sameValue`（`Object.is`+对象`JSON.stringify`）替换`!==` |
| 验 | FF-02 全绿（含对象compare恒脏修复）+ RG-02 |

**阶段P5 · 第3章添加口（红：E2E-01手工步骤先行红）**

| 步骤 | diff清单 |
|---|---|
| 改 | 三、3.2(7) `model.api.ts updateModel` Pick 加`'param_options'` |
| 改 | 三、3.3(1) `ModelModals.tsx` 模板区：`sibModels`/`candKeys`（default_params∪param_options &&）/`checked`/`collected` state/切Provider重算清空/勾选行控件（select/InputNumber/Input+默认值取兄弟）/成功后重置 |
| 改 | 三、3.3(2) `ModelModals.tsx` Props`onSubmitAddModel`加`range?/capabilities?/param_options?`+`handleAddModel`透传`collected.params/options`；`SettingsPage.tsx:360-367` addModel透传range/capabilities/param_options；`model.api.ts addModel`入参加`param_options?` |
| 改 | 三、3.3(4) `useSettings.ts refreshModels(select)` 补回显`paramOptions` |
| 验 | E2E-01 添加口径（表单→POST→落盘→回显下拉）+ RG-02 |

**阶段P6 · 第4章 provider读写（红：BY-06/BY-07）**

| 步骤 | diff清单 |
|---|---|
| 改 | 四、4.3(3) `model_routes.py ProviderConfigUpdate` 加`max_retries: Optional[int]=Field(default=None)` |
| 改 | 四、4.3(4) `model.api.ts ProviderConfigPatch` 加`max_retries?: number` |
| 改 | 四、4.3(5) `model.api.ts addProvider`加`timeout?/max_retries?`；`ModelModals.tsx` Props`onSubmitAddProvider`加两字段+弹窗表单两`InputNumber`（timeout min1默认60占位/max_retries min0默认3占位） |
| 改 | 四、4.3(6) 四文件联动label：`types.ts` providerConfig加`label:string`；`useSettings.ts` load构建加`label:p.label`；`SettingsPage.tsx:278-284` fallback加`label:''`；`ProviderConfig.tsx` Props/doSave/表单label输入框 |
| 改 | 四、4.3(7) 无代码（models创建走模型管理区UI） |
| 验 | BY-06/BY-07 绿 + RG-01 + 手工：改label保存→配置区即变+重拉仍新名 |

**阶段P7 · 第4章 provider运行时（红：BY-04/BY-05，含FF-03对齐）**

| 步骤 | diff清单 |
|---|---|
| 改 | 四、4.3(1)a `lifecycle/service.py` `timeout=provider_config.get("timeout")`（传None不传默认值） |
| 改 | 四、4.3(1)b `base_service.py:131-135` `timeout is not None`（0合法，不据truthiness） |
| 改 | 四、4.3(1)c `model_service.py get_models` 显示层读`tuning.llm_net.read_timeout`/`tuning.llm.stream_max_retries`（v3.8）+`from app.config import get_config` |
| 改 | 四、4.3(1)d `SettingsPage.tsx:278-284` fallback `timeout:150` |
| 改 | 四、4.3(2)a `base_service.py __init__` 加`max_retries:Optional[int]=None`+三层（Provider>[tuning.llm.stream_max_retries]>[常量3]）+`self.max_retries` |
| 改 | 四、4.3(2)b `request_stream:299-300` 用`self.max_retries`（删`_D_STREAM_MAX_RETRIES`读值） |
| 改 | 四、4.3(2)c `snapshot()` 加`max_retries=self.max_retries` |
| 改 | 四、4.3(2)d `lifecycle/service.py create_service_instance` 加`max_retries=provider_config.get("max_retries")` |
| 修 | FF-03：既有timeout=60断言改tuning对齐值 |
| 验 | BY-04/BY-05 绿 + RG-01 + 手工：改timeout=0保存→请求极短超时生效不跳tuning |

**阶段P8 · 第4章 高级：管理选项+动态参数（红：BY-09/FF-03/FF-04）**

| 步骤 | diff清单 |
|---|---|
| 改 | 四、4.3(8) `SettingsPage.tsx` 参数区标题行加"管理选项"链接（`paramOptions`非空才现）+`types.ts ModelState`加`paramOptionsModalOpen`+新建`ParamOptionsModal.tsx`（Tag展示/添加/删除/保存前校验非空/悬空值`Modal.confirm`同批回提`default_params`重置首项，复用3.1(2)同批合并） |
| 改 | 四、4.3(9)-1 `model_service.py` 常量区`PROVIDER_PARAM_TYPES`+`KNOWN_PROVIDER_KEYS` |
| 改 | 四、4.3(9)-2 `get_models` Provider段加`param_types`+动态标量值透传；`model.api.ts ProviderEntry`加`param_types?`；`types.ts providerConfig`加`[key:string]:unknown`；`useSettings.ts load`动态值照抄透传 |
| 改 | 四、4.3(9)-3 `ProviderConfig.tsx` doSave动态收集循环+渲染区（initialValues天然回填）；`model_routes.py:17` import补`ConfigDict`+`ProviderConfigUpdate`加`model_config=ConfigDict(extra='allow')`；`update_provider_config` param_types白名单+动态字段落盘 |
| 改 | 四、4.3(9)-4 落盘走`merge_nested_patch`（复用，无新增） |
| 验 | BY-09/FF-03/FF-04 绿 + RG + 手工：管理选项加xhigh→下拉即现；rate_limit改20→重拉20；evil_key 400 |

**阶段P9 · model级运行时验证（红：BY-08，E2E-01扩展LLM断言）**

| 步骤 | diff清单 |
|---|---|
| 改 | 无新代码（BY-08测现有`parse_model_params`；E2E-01补真实LLM请求体断言`reasoning_effort="high"`） |
| 验 | BY-08 绿 + E2E-01 全绿（配置→保存→显示→运行时四段全通） |

**阶段P10 · 全量回归与收尾（RG-01/RG-02/E2E-02）**

| 步骤 | 动作 |
|---|---|
| 回归 | 后端全量`pytest`（RG-01）+前端全量`npm run test`+`npm run check`（RG-02）+E2E-02（Provider全链） |
| 手工 | 5.5清单逐项 |
| 收尾 | 更新`version.txt`头部（本tag以来所有commit摘要）→打tag`v{major}.{minor}.{patch+1}`；commit标题带签名+日期；禁提交测试代码 |

### 5.5 手工验证清单（每阶段收尾抽检，小欧）

1. 切`sensenova/deepseek-v4-flash`参数区下拉显示`medium`非`0`；改`high`保存，Network观察`reasoning_effort`为字符串`"high"`。
2. 刷新页面重进设置页，值仍`high`；`config.yaml`对应模型落盘字符串。
3. 添加模型：sensenova下新建→勾选`reasoning_effort=high`+`context_limit=900000`→保存→`POST /models`体含字符串`"high"`→建完自动切新模型→参数区下拉出现且值为所勾值→`yaml`同时落`model_params`与`model_meta.param_options`。
4. Provider改`timeout=0`保存→请求按极短超时走（4.3(1)b验证`is not None`）；未设timeout的Provider显示值与运行时一致。
5. 管理选项删`high`且当前默认值=high→弹确认重置首项→保存后下拉无悬空值；新增`xhigh`→下拉出现。
6. 动态参数：config加`rate_limit:10`→ProviderConfig自动出现该InputNumber并回填10→改20保存→重拉20；`evil_key`保存被拒。
7. 重启后端，全部配置读回不变（落盘幂等性）。

### 5.6 失败处理（小欧）

- **红→绿未果**：单一case红7天不绿=该阶段diff与测试断言不匹配。按序核查：断言是否对准真实行为（非设计愿望）→工厂数据是否真实→diff是否遗漏相邻行。找到后补丁修正，禁改测试去迁就未实现行为。
- **回归破坏**：RG-01/02出现红=新diff与既有行为冲突。先隔离（该阶段最后一个提交回查），用增量补丁修复，禁`git checkout`/`reset --hard`/`revert`。
- **E2E超时/强杀**：一律走`subprocess.Popen`+`--timeout=2900`，严禁bash直跑pytest（agents.harness铁律）。
- **顺序纪律**：P1→P10严禁越序；前阶段验证门未全过，后阶段红测试不允许开工（防止diff堆叠掩盖断链）。
