# [62]reasoning_effort类型错乱根因分析与SSOT根治方案

**创建时间**: 2026-09-22 12:40:51
**更新时间**: 2026-09-22 14:02:56（小欧）
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

按2.1第5条完整性铁律逐条核对现状代码（未改），6处问题：

| # | 代码点 | 问题 | 违原则段 |
|---|---|---|---|
| P1 | `lifecycle/service.py:113` timeout兜底`30` | `get_models()`对外返回`60`，实际运行时用`30`，显示值≠实际值 | ②读③写 |
| P2 | `base_service.py:98-109` `__init__`无`max_retries`参数 | 运行时完全不消费Provider级`max_retries`，前端可编辑但改了没用 | ③写 |
| P3 | `base_service.py:300` `max_retries`硬编码`_D_STREAM_MAX_RETRIES`（常量3） | 用户在前端改`max_retries=5`，实际重试仍是3 | ③写 |
| P4 | `model_routes.py:48-54` `ProviderConfigUpdate` DTO缺`max_retries`字段 | DTO只有`retry_times`，前端发`max_retries`靠key_map别名绕过，类型不一致 | ②③ |
| P5 | `model.api.ts:43-49` `ProviderConfigPatch` TS类型缺`max_retries` | 接口只有`retry_times`，前端`ProviderConfig.tsx:52-53`实际发送`max_retries`，TS类型保护失效 | ④ |
| P6 | `model.api.ts:98-103` `addProvider`签名缺`timeout`/`max_retries` | 创建Provider时不传这两个值，全走后端默认值（60/3），前端无法在创建时自定义 | ⑤ |

注：P4的DTO虽然缺`max_retries`字段，但`model_dump(exclude_none=True)`把前端传的`max_retries`原样透传到`update_provider_config`的`fields`，key_map有`max_retries→max_retries`映射，所以**写入链路碰巧能工作**——但这是绕过类型系统的隐式行为，不是正确设计。

### 4.2 设计原则（小欧）

1. **兜底值统一**：Provider参数在所有读写点使用同一默认值，杜绝显示值≠运行时值。
2. **运行时必须消费配置值**：前端可编辑的参数，后端运行时必须真正使用，禁止硬编码常量。
3. **DTO与TS类型对齐**：前后端类型定义必须覆盖实际发送的所有字段。
4. **创建时可设**：Provider创建弹窗和API签名必须包含所有可配置参数。

### 4.3 精确修改diff（小欧）

（1）`backend/app/services/lifecycle/service.py:113` timeout兜底统一为60：

```diff
-        timeout=provider_config.get("timeout", 30),
+        timeout=provider_config.get("timeout", 60),
```

原因：`get_models()`（model_service.py:103）兜底60，`add_provider()`（model_service.py:244）默认60，`ProviderAddRequest`（config_schemas.py:117）默认60，SettingsPage.tsx:281前端fallback 60。唯独`lifecycle/service.py`用30，导致YAML未配timeout的Provider对外显示60但实际用30。统一为60。

（2）`backend/app/llm/base_service.py` `max_retries`从硬编码改为配置驱动：

```diff
     def __init__(
         self,
         api_key: str,
         llm_model: ModelRef,
         timeout: int = _D_READ_TIMEOUT,
+        max_retries: int = _D_STREAM_MAX_RETRIES,
         max_tokens: Optional[int] = None,
         ...
     ):
         ...
         self.timeout = int(timeout_value)
+        self.max_retries = max_retries
```

```diff
     # request_stream():300
-        max_retries = _D_STREAM_MAX_RETRIES
+        max_retries = self.max_retries
```

```diff
 # lifecycle/service.py:106-119 create_service_instance():
     return BaseAIService(
         api_key=...,
         llm_model=...,
         timeout=provider_config.get("timeout", 60),
+        max_retries=provider_config.get("max_retries", 3),
         ...
     )
```

原因：现状`base_service.py:300`硬编码`_D_STREAM_MAX_RETRIES=3`，用户在前端改`max_retries`后保存成功但运行时无任何效果，是虚假可配置。修复后`BaseAIService`持有`self.max_retries`，`request_stream()`使用配置值，`lifecycle/service.py`从`provider_config`读取并透传。`get_models()`（model_service.py:104）已正确返回`max_retries`值（兜底3），无需改。

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

### 4.4 测试与验证（小欧）

1. **timeout一致性**：`config.yaml`给某Provider设`timeout: 45`，`GET /models`返回45，运行时httpx read timeout为45；不设timeout的Provider，`GET /models`返回60，运行时也为60（不再出现显示60实际30）。
2. **max_retries消费**：前端改`max_retries=5`保存，触发请求模拟失败，观察日志重试次数为5次（不再固定3次）；不设max_retries的Provider，运行时用3（与常量一致）。
3. **DTO类型对齐**：`PUT /providers/{name} {max_retries: 5}`直接调API，落盘成功（不再依赖retry_times别名）。
4. **创建可设**：添加Provider弹窗填写timeout=30/max_retries=5，保存后`config.yaml`落盘对应值，`GET /models`返回所填值。
