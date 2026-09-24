# [68] 设置页「模型库」Tab — 获取 Provider 模型列表并写入配置设计方案

**版本**: v1.4
**创建时间**: 2026-09-24 20:34:12
**更新时间**: 2026-09-24 21:27:36
**编写人**: 小欧
**更新人**: 小欧
**状态**: 评审通过（北京老陈 2026-09-24 定案四项决策 + 整体方案通过；未落码）

---

## 版本历史

| 版本 | 时间 | 更新人 | 修改简介 |
|------|------|--------|---------|
| v1.0 | 2026-09-24 20:34:12 | 小欧 | 初版：现状调研 + 四项决策定案 + 后端/前端完整设计 + 边界风险 + 验收与实施清单 |
| v1.1 | 2026-09-24 21:08:59 | 小欧 | 补 Provider 增删反应闭环（北京老陈问询「增加/删除 provider 是否都支持」）：①§5.2 新增第 7 条——三种变更来源（设置页增删/外部改 yaml/拉取后保存前被删）的反应机制 + 本地 selectedProvider 失效守卫 useEffect；②§六 边界表补第 11 行外部改 yaml 场景；状态改评审通过 |
| v1.2 | 2026-09-24 21:10:44 | 小欧 | 补 §5.4 UI 布局与视觉风格规范（北京老陈指令「必须参考本地最新代码风格，不能搞的奇奇怪怪的」）：基于 settingsTokens/stepStyles/SettingsPage 现行代码提炼——令牌强制表（间距/字号/颜色/控件宽/弹窗宽，禁裸数字禁 hex）、区块骨架对齐 SectionTitle/ModelSelector/settingsRowStyle、控件选型 antd5 同款、提示走 errorHandler、六条禁止清单；§5.2 图注补「结构示意以 §5.4 为准」 |
| v1.3 | 2026-09-24 21:13:56 | 小欧 | 删除原第六章「边界与风险」整章（北京老陈指令：能解决的在方案里解决，不能解决的删掉，不留此章）：11 条全部为可解决问题且正文已覆盖或本次并入——①§4.2-5 补非数组响应显式 ok:false + 路径参数 enc() 编码；②测试表补 T11 非标准结构容错锁定该解法；③原七/八章号重排为六/七（含 7.1/7.2→6.1/6.2），全文章节连续 |
| v1.4 | 2026-09-24 21:27:36 | 小欧 | 全文十遍通读整体化修订（北京老陈指令：查逻辑一致性，正文不许版本补丁注释）：①消除悬空摇摆——失败路径定死「本地校验 400/404、远端失败 200+ok:false」，DTO 定死 model_routes 内联，service 定死 model_service.py，删读而不用的 timeout 步骤；②修硬伤——§4.2 重复步骤号 6、§5.1 改动数量 5+1→4+1、实施清单 10 case→11 case、§2.3 删用不上的 mask 行、D4/§5.2 过滤用词统一；③路径参数编码移 §4.4 路由层；④清除正文全部版本补丁标记与历史备注（v1.x 补/已证/禁回潮/19 组件等），融为整体行文 |

---

## 一、需求说明

### 1.1 用户需求（北京老陈 2026-09-24）

在配置页面（设置页）新增一个 **Tab 功能**：

1. 获取某个 Provider 的**远程模型列表**（该 Provider 服务端真实存在的模型）；
2. 用户**勾选**需要的模型；
3. 把勾选结果**写入配置文件**（config.yaml 的 `ai.{provider}.models` 列表）。

### 1.2 四项决策定案（北京老陈 2026-09-24 拍板）

| # | 决策点 | 定案 |
|---|--------|------|
| D1 | Tab 位置 | **顶层 Tab，倒数第二个位置**：通用 → 模型 → 安全 → 沙箱 → 调优 → 系统 → **模型库（新）** → 外观 |
| D2 | 写入语义 | **替换式**：勾选集合 = 最终 `models` 列表；取消勾选 = 从配置移除 |
| D3 | 全局模型 | **不带**「设为当前全局模型」，本 Tab 只管挑模型进配置；切全局模型仍走既有入口 |
| D4 | 列表过滤 | **三个都要**：①关键词搜索 ②已配置/未配置分组 ③免费模型过滤（如 `-free`） |

---

## 二、现状调研（证据链）

### 2.1 配置页 Tab 架构

- 前端：`frontend/src/features/settings2/`，Tab 列表由后端 `settings_registry.GROUPS` / `GROUP_ORDER` 驱动（现 7 组）；`model` / `general` 两组为特殊渲染分支（`SettingsPage.tsx:607-621`），其余走 `SettingsGroup` schema 行渲染。
- Tab 标题唯一源 = 后端注册表 label（`SettingsPage.tsx:596` `state.schema[g]?.label`）；`TabKey` 类型（`types.ts:24-31`）与 `SettingIcon`（`icons.tsx:27-35`）需与后端组名一一对应。

### 2.2 配置文件结构

`config/config.yaml`（模板 `backend/config.yaml.example:27-55`）：

```yaml
ai:
  model_ref: {provider: opencode, model: kimi-k2.5-free}   # 全局当前模型（唯一源）
  opencode:
    api_base: https://opencode.ai/zen/v1
    api_key: sk_xxx...
    models:            # ← 本功能写入目标：纯字符串列表
      - minimax-m2.5-free
      - kimi-k2.5-free
    model_params: {...}   # 按模型的运行参数
    model_meta: {...}     # 按模型的 UI 元数据（label/range/capabilities/param_options）
```

### 2.3 已有后端能力（复用面）

| 能力 | 位置 | 复用方式 |
|------|------|---------|
| Provider/模型 CRUD | `model_routes.py`（/models /providers 全套） | 新端点并列同风格薄壳 |
| 原子写盘（锁+备份+完整性校验+写后验证+回滚+reload） | `config_helpers.merge_nested_patch` | 替换 models 列表直接走它 |
| env 接管守卫 | `model_service._raise_if_env_takeover` | 保存端点复用 |
| Provider 请求头适配 | `get_provider_adapter(name).static_headers(api_key)`（`llm/adapters/`） | 拉取端点组头复用（opencode zen 的 UA/session 头自动带上，DRY） |
| 服务商错误体提取 | `client_sdk._extract_server_error_message` 思路 | 拉取失败透出真实错误 |
| mtime 返回 | `_config_mtime` | 替换端点返回 mtime，前端 `syncMtime` 对齐现有响应契约 |

### 2.4 拉取远程模型：现状为零

- **无任何**「拉取远程模型列表」后端 API（全库 grep 仅 `scripts/models_verify-2026-09-23.py` 手工脚本演示过 `GET {api_base}/models` → 解析 `data[].id`）。
- **浏览器直连 provider /models 否决**：各家 provider API 基本无 CORS 头，浏览器必拦 → **必须后端代理拉取**。

---

## 三、总体架构

```
前端新 Tab「模型库」(倒数第二)
  ├─ GET  /api/v1/providers/{name}/remote-models   ← 后端代理拉取远程模型列表
  └─ PUT  /api/v1/providers/{name}/models          ← 替换式写入 ai.{provider}.models

数据流：
  点击「获取」→ 后端 httpx GET {api_base}/models（适配层头）
             → 解析 data[].id → 返回前端列表
  勾选 + 保存 → PUT {models:[...]} → 守卫校验 → merge_nested_patch 原子落盘
             → 返回 mtime → 前端 refreshModels() → 模型 Tab 同步可见
```

### 3.1 策略选择

| 方案 | 说明 | 结论 |
|------|------|------|
| A. 浏览器直连 /models | 前端直接 fetch provider | **否决**：CORS 拦截，不可行 |
| **B. 后端代理拉取 + 后端原子写** | 新增 2 端点，前端只做交互 | **选定**：绕 CORS、复用守卫与写盘链路 |
| C. 手抄模型名 | 用户手动输入模型名进配置 | 现状痛点，本需求正是要消灭它 |

---

## 四、后端设计（4 处改动）

### 4.1 settings_registry 注册新组

文件：`backend/app/services/settings/settings_registry.py`

```python
# 编辑历史: 2026-09-24 小欧 - [68] 新增模型库组（items 空：本 Tab 不走 schema 行渲染，
#   特殊渲染分支同 model/general；Tab 位置=倒数第二）- 小欧-2026-09-24
GROUPS["model_library"] = {"label": "模型库", "items": []}
GROUP_ORDER = ["general", "model", "security", "sandbox", "tuning",
               "system", "model_library", "appearance"]   # 倒数第二（D1）
```

- `items=[]`：schema 无行，`GET /settings/schema` 正常返回空组，前端不走 `SettingsGroup`。
- 加载自检（`_build_index` 重复 key 拒启）不受空组影响。

### 4.2 新端点：GET /api/v1/providers/{name}/remote-models

文件：`backend/app/api/v1/model_routes.py`（薄壳）+ `backend/app/services/model/model_service.py`（service 与本地 Provider/模型读写同域，`_raw_ai` 等基础设施直接复用）

**行为**：

1. 读 `ai.{name}` 的 `api_base` / `api_key`（含 `{NAME}_API_KEY` env 接管值）；provider 不存在 → 404。
2. `api_base` 为空 → 400「该 Provider 未配置 api_base，请先到模型 Tab → ③ Provider 配置填写」。
3. 组请求头：`get_provider_adapter(name).static_headers(api_key)`（opencode zen 的 `User-Agent`/`x-opencode-session` 自动带；默认 provider 为 `Authorization: Bearer {key}`）。
4. `httpx.AsyncClient` GET `{api_base}/models`，超时固定 30s（拉列表是短操作，独立于会话用的 provider timeout）。
5. 解析 OpenAI 兼容响应：`{"data": [{"id": "...", "owned_by": "...", "created": ...}]}`；非标准结构容错——`id` 缺失时尝试 `model` 字段，`data` 非数组直接 `ok:false` + message 明示（不猜不崩）。
6. 返回：

```json
{
  "ok": true,
  "provider": "opencode",
  "models": [ {"id": "kimi-k2.5-free", "owned_by": "moonshotai"}, ... ],
  "count": 10,
  "configured": ["kimi-k2.5-free", "minimax-m2.5-free"],
  "current_model": "kimi-k2.5-free"
}
```

- `configured`：该 provider 现有 `models` 列表（前端预勾选数据源，一次请求拿全，少一次往返）。
- `current_model`：若该 provider 是 `ai.model_ref.provider`，返回当前模型名（前端禁用其勾选框；非当前 provider 返回 null）。
7. **失败路径定死（无二义）**：
   - **本地参数错误**（provider 不存在 / api_base 未配置）→ 直接 404 / 400（前端可预判，按钮已 disabled 防住）；
   - **远端拉取失败**（服务商 HTTP >=400、网络异常、30s 超时）→ 捕获并提取服务商真实错误体，**端点统一返回 200 + `ok:false` + `message`**（前端按钮下方 Alert 展示，不弹全屏）。

**DTO**（与现有 CRUD DTO 同风格，内联在 `model_routes.py`）：

```python
class RemoteModelItem(BaseModel):
    id: str
    owned_by: Optional[str] = None

class RemoteModelsResponse(BaseModel):
    ok: bool
    provider: str
    models: List[RemoteModelItem]
    count: int
    configured: List[str]
    current_model: Optional[str] = None
    message: Optional[str] = None   # ok=false 时的错误文案
```

### 4.3 新端点：PUT /api/v1/providers/{name}/models（替换式写入）

文件：同上（model_routes 薄壳 + service 编排）

**入参**：

```python
class ProviderModelsReplaceRequest(BaseModel):
    models: List[str]
```

**守卫与校验链（顺序固定）**：

| # | 校验 | 失败处理 |
|---|------|---------|
| 1 | provider 存在 | 404 |
| 2 | `_raise_if_env_takeover(name)` | 400「由环境变量接管，只读」 |
| 3 | 列表去空串、去重、保持入参顺序 | 静默归一（重复项只留首个） |
| 4 | 归一后列表非空 | 400「模型列表不能为空」 |
| 5 | 若该 provider = `ai.model_ref.provider`：`model_ref.model` 必须在新列表中 | 400「不能移除当前全局模型 {m}，请先切换全局模型」（替换式写入与配置完整性校验在此拦截，防止落盘校验失败回滚） |

**写盘编排（service 层单函数）**：

1. 读旧 `models` 列表，算 `removed = 旧 - 新`。
2. 构造嵌套 patch 一次落盘（`merge_nested_patch`，锁+备份+校验+原子写+reload 全链路现成）：
   ```python
   tree = {"ai": {name: {"models": new_list}}}
   # 孤儿清理：removed 中每个 m，置 None 删键（_set_nested_path None 删+回收空父级）
   for m in removed:
       tree 叶路径 ai.{name}.model_params.{m} = None
       tree 叶路径 ai.{name}.model_meta.{m} = None
   ```
   - 模型名含点号（gpt-4.1）安全：`merge_nested_patch` 叶段按字面名写入，不按点号拆路径。
   - 只在 `model_params`/`model_meta` 里存在对应块才生成 None 叶（不存在则跳过，避免造空块再删）。
3. 返回 `{ok: true, mtime, added: [...], removed: [...]}`（前端提示「新增 X 个、移除 Y 个」）。

**不做**（D3）：不写 `ai.model_ref`，不动全局当前模型。

### 4.4 路由注册核对

- `model_router` 已在 `main.py:14` 注册，新端点挂同 router 零额外注册。
- 两个新端点的路径参数 `{name}` 一律 `encodeURIComponent` 编码后传入（防 provider 名含特殊字符，与现有 `enc()` 惯例一致）。

---

## 五、前端设计（4 处改动 + 1 新组件）

### 5.1 改动清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `settings2/types.ts` | `TabKey` 联合加 `'model_library'` |
| 2 | `settings2/components/icons.tsx` | `SettingIcon` 加 `model_library: <CloudDownloadOutlined style={TAB_ICON_STYLE} />` |
| 3 | `services/api/model.api.ts` | 加 `fetchRemoteModels(provider)` / `replaceModels(provider, models)` 两方法 + 响应类型 |
| 4 | `SettingsPage.tsx` | 渲染分支加 `state.activeTab === 'model_library' ? renderModelLibraryTab()`（与 model/general 同模式） |
| 5 | 新组件 `settings2/components/ModelLibraryTab.tsx` | 核心交互（组件一文件，settings2 既有惯例） |

**说明**：`GROUP_ORDER` 由 `useSettings` 从 `state.schema` 键序动态派生，后端注册组后 Tab 自动出现，前端无需维护分组常量。

### 5.2 ModelLibraryTab 交互设计

> 下图为**结构示意**（非像素稿）；间距/字号/颜色/控件宽一律按 §5.4 令牌规范落码，不照图写死尺寸。

```
┌─ 模型库 ──────────────────────────────────────────────┐
│ Provider: [ opencode ▼ ]   [ 获取模型列表 ]           │
│ （api_base 空 → 获取按钮 disabled + 灰字提示先去配置）  │
├──────────────────────────────────────────────────────┤
│ [🔍 关键词搜索...]   [✓] 仅看免费（名称含 -free）      │
│ 共 10 个模型，已配置 2 个，已勾选 3 个                 │
├──────────────────────────────────────────────────────┤
│ ▼ 已配置（2）                                          │
│   [✓] kimi-k2.5-free          [当前] Tag              │
│   [✓] minimax-m2.5-free                               │
│ ▼ 未配置 · 待挑选（8）                                 │
│   [✓] mimo-v2.6-flash-free     ← 本轮新勾选           │
│   [ ] nemotron-3-ultra-free                            │
│   ...                                                  │
├──────────────────────────────────────────────────────┤
│                    [ 保存所选（3） ]                    │
└──────────────────────────────────────────────────────┘
```

**交互流**：

1. **Provider 下拉**：数据源 `state.model.providers`；切换 Provider → 清空列表与搜索词，重置勾选为新 Provider 的已配置集。
2. **获取按钮**：`fetchRemoteModels` loading 态；成功 → 勾选集初始化为 `configured`；失败 → 按钮下方 `Alert` 展示 message（不弹全屏 Modal）。
3. **三项过滤（D4，叠加生效）**：
   - 关键词：对 `id`/`owned_by` 大小写不敏感包含匹配；
   - 仅看免费：名称含 `-free`（如 kimi-k2.5-free）或等于 `big-pickle`（对齐 scripts 过滤规则）；开关带 Tooltip 说明规则；
   - 分组展示：`configured` 命中 → 「已配置」组；未命中 → 「未配置 · 待挑选」组。
4. **勾选状态**：本地 `Set<string>` state；已配置预勾选；`current_model` 命中项 `checkbox disabled + Tag「当前」`（对应 §4.3 校验第 5 条，落实 D2）。
5. **保存**：`Modal.confirm`「将**替换**该 Provider 的模型列表为已勾选的 N 个（移除 M 个）」→ `replaceModels` → `showSuccess` → `s.refreshModels()`（模型 Tab / 参数区同步）→ 成功后按新列表重算分组。
6. **脏态边界**：勾选态是组件本地 state，**不进** settings 脏计数/SaveBar 体系（KISS：本 Tab 有自己的保存按钮，切 Tab 未保存勾选静默丢弃，不污染全局「保存本组」语义）。
7. **Provider 增删反应**——三种变更来源全闭环：

   | 来源 | 反应机制 | 覆盖 |
   |------|---------|------|
   | 设置页增/删 provider（模型 Tab 操作） | 现有 `onSubmitAddProvider → refreshModels()` / `onConfirmDelete → load()` 更新 `state.model.providers`（本组件下拉唯一数据源）→ 下拉自动增减；且切 Tab 组件卸载重挂，本地态按新 providers 重新初始化；后端禁删最后一个 provider，列表永不空 | ✅ |
   | 拉取后、保存前 provider 被删 | PUT 返回 404 → 前端错误透出，不写错对象 | ✅ |
   | **外部直接改 config.yaml 删 provider**（不走设置页） | `checkMtime` 刷新 `state.model.providers` → 下拉更新；组件 `useEffect` 监听 providers 变化，本地 `selectedProvider` 不在列表中 → 重置为第一个 provider 并清空已拉取列表/勾选态（防本地态悬空指着已删 provider） | ✅ |

### 5.3 model.api.ts 契约

```ts
export interface RemoteModelsResponse {
  ok: boolean;
  provider: string;
  models: Array<{ id: string; owned_by?: string }>;
  count: number;
  configured: string[];
  current_model?: string | null;
  message?: string;
}

fetchRemoteModels: (provider: string) => Promise<RemoteModelsResponse>   // GET  /providers/{enc(provider)}/remote-models
replaceModels: (provider: string, models: string[]) => Promise<{ ok: boolean; mtime: number; added: string[]; removed: string[] }>  // PUT /providers/{enc(provider)}/models
```

### 5.4 UI 布局与视觉风格规范

> 唯一基准 = 本地 `settings2` 现行代码的令牌体系（历次视觉收敛成果）。本节是落码与评审的硬约束；不引入任何新 UI 库、新样式方案、第二套 token。

#### 5.4.1 令牌强制表（禁裸数字、禁硬编码色）

| 类别 | 必须用 | 取值/出处 | 禁止 |
|------|--------|----------|------|
| 间距 | `Spacing.XS/SM/MD/LG/XL` | 4/6/8/12/16，`@/utils/stepStyles` | 裸 `margin/padding/gap: 数字` |
| 字号 | `FontSize.PRIMARY` / `SECONDARY` | 14 / 12（全链仅二档） | 13px、15px 等游离档 |
| 字重 | `FontWeight.BOLD` / `REGULAR` | 600 / 400 | 裸 `fontWeight: 'bold'` |
| 文字色 | `Colors.TEXT.PRIMARY/SECONDARY/WEAK` | #595959/#8c8c8c/#888 | 裸 hex（#333/#999…） |
| 背景/边框 | `Colors.BG.PRIMARY`、`Colors.BORDER.LIGHT` | stepStyles 语义色 | 裸 hex 背景/描边 |
| 圆角 | `settingsRadius.SM`（=Radius.SM 4） | settingsTokens | 裸 `borderRadius: 4/8` |
| 控件宽度 | `settingsControl.*` | modelSelectWidth 180 / searchWidth 260 / actionBtnWidth 120 / modelNameWidth 240 / baseUrlWidth 360 | 裸 `width: 200` 等散落数字 |
| 弹窗宽度 | `settingsModalWidth.confirm/form/display` | 480 / 520 / 800 | 裸 `width: 480`（禁散落弹窗宽） |
| 行容器/行 label | `settingsRowStyle` / `settingsLabelStyle` | settingsTokens 单点收口（SettingRow/ProviderConfig/ModelParams 三处复用） | 组件内私自行样式（第四套行样式漂移） |

#### 5.4.2 区块骨架（逐段对齐现有组件同款）

| 本页元素 | 对齐参照（本地代码） | 写法要点 |
|---------|---------------------|---------|
| 区块分隔标题 | `SectionTitle`（`── ① … ──` 中文破折号样式） | 直接复用组件；区块编号续接中文序号习惯（①获取/②过滤/③列表），与模型 Tab ①②③④ 同气质 |
| Provider 选择 + 获取按钮行 | `ModelSelector.tsx:35` | `display:flex; gap:Spacing.MD; alignItems:center`；Provider 下拉宽 `settingsControl.modelSelectWidth` |
| 按钮 | 「添加模型」同款（ModelSelector.tsx:58） | **默认 Button + 图标**（`CloudDownloadOutlined`/`SearchOutlined`），禁 `type="link"` 异款、禁手打加号字符；图标来自 `@ant-design/icons` |
| 关键词搜索框 | `SearchBox.tsx` `Input.Search` | 宽 `settingsControl.searchWidth`；过滤式用受控 `onChange` 即时过滤（不抄它的回车跳转语义） |
| 免费过滤开关 | 能力多选行（SettingsPage Checkbox.Group 行）同排气质 | `Checkbox`（或 antd `Switch`）+ `FontSize.SECONDARY` 说明字 + Tooltip；行上下留白用 Spacing |
| 统计行（共 N/已配置 M/已勾选 K） | 现有次级小字惯例 | `FontSize.SECONDARY` + `Colors.TEXT.SECONDARY` |
| 分组标题（已配置/未配置） | `SectionTitle` 或 `FontWeight.BOLD + FontSize.PRIMARY` | 与页内其它小节头一致，不新造 Collapse 花样 |
| 模型勾选行 | `settingsRowStyle` | 行高≥44、下边框 `Colors.BORDER.LIGHT`；模型名 `FontSize.PRIMARY`、`owned_by` 用 `Colors.TEXT.SECONDARY`；Checkbox 左、Tag 右 |
| 「当前」标注 | capabilities 的 antd `Tag` 用法（SettingsPage.tsx:371） | 默认 `Tag`，不自绘徽章 |
| 空态/无命中 | antd `Empty` 或灰字 `Colors.TEXT.WEAK` | 不自绘插画 |
| 加载态 | 按钮 `loading` prop；列表区 `Skeleton active`（SettingsPage 首屏同款） | 禁自造 spinner |
| 错误提示 | 按钮下方 antd `Alert`（§5.2-2 定案） | 不弹全屏 Modal；**禁直接 `message.*`**（eslint `no-restricted-syntax` 强制走 `showSuccess/showMessage/handleApiError`） |
| 保存确认弹窗 | `Modal.confirm` + `width: settingsModalWidth.confirm` | 与「重置为默认」确认同款（SettingsPage.tsx:304-326）：title 加粗 `FontSize.PRIMARY`、content `Colors.TEXT.SECONDARY` |
| 保存按钮 | 页面主操作默认 Button | 成功提示 `showSuccess`；失败 `handleApiError`；成功后 `s.refreshModels()` |

#### 5.4.3 组件与代码风格（settings2 惯例）

- **组件一文件**：新组件独立 `ModelLibraryTab.tsx`，PascalCase 文件名，**named export**（无 default export）。
- **antd 5** 原生组件（Button/Select/Checkbox/Input/Tag/Alert/Skeleton/Empty/Modal/Tooltip），图标一律 `@ant-design/icons` SVG，**禁 emoji**。
- **import 规矩**：`@/` 别名；同一模块 import 合并追加不重复；类型用 `import type`。
- **提示统一**：`showSuccess` / `showMessage` / `handleApiError`（`@/services/error/handler`），与设置页全页一致。
- **文件头编辑历史**：`// 编辑历史: YYYY-MM-DD 小欧 - … - 小欧-YYYY-MM-DD` 署名+日期。
- **脏态不外溢**：不给 SaveBar/DirtyBadge 造模型库脏点（§5.2-6 定案），避免视觉上出现来路不明的红点。

#### 5.4.4 禁止清单

1. 禁新 UI 库 / CSS-in-JS / 第二套 token / 全局样式文件；
2. 禁裸 hex 色、裸 px 间距、裸控件宽度（一律 §5.4.1 令牌）；
3. 禁 emoji 图标、禁 `type="link"` 异款操作按钮、禁自绘 Spinner/徽章/插画；
4. 禁 `message.success/error/warning/info` 直调（eslint error 级）；
5. 禁全屏错误 Modal、禁脱离 `settingsModalWidth` 的散落弹窗宽；
6. 禁照 §5.2 ASCII 示意图写死尺寸（那图只表达结构与层级）。

---

## 六、测试与验收

### 6.1 后端 pytest

| Case | 断言 |
|------|------|
| T1 拉取成功 | mock httpx 200 `{"data":[{"id":"a"}]}` → count=1、configured 对齐 yaml |
| T2 拉取 401/超时 | ok=false、message 含服务商真实错误 |
| T3 api_base 空 | 400 |
| T4 provider 不存在 | 404 |
| T5 替换写盘 | 落盘后 yaml models == 入参；mtime 变化 |
| T6 移除当前全局模型 | 400，yaml 不变 |
| T7 env 接管保存 | 400 只读 |
| T8 空列表 | 400 |
| T9 孤儿清理 | removed 模型的 model_params/model_meta 键消失 |
| T10 重复/空串入参 | 归一去重去空 |
| T11 非标准结构容错 | `data` 非数组 → ok:false；`id` 缺失回退 `model` 字段（§4.2 行为 5） |

### 6.2 前端

- `npm run check`（lint + format:check）+ `npx vitest` 相关用例。
- 手工 E2E（真实后端）：获取 → 三项过滤各自生效 → 勾选 → 保存确认 → 模型 Tab 出现新模型 → 取消勾选保存 → 模型消失且参数区无孤儿。

---

## 七、实施清单（落码顺序）

| Step | 内容 | 文件 |
|------|------|------|
| 1 | 注册组 + GROUP_ORDER | `settings_registry.py` |
| 2 | 拉取端点（DTO + service + 路由） | `model_routes.py` / `model_service.py` |
| 3 | 替换端点（守卫 + 差集孤儿清理 + 落盘） | 同上 |
| 4 | 后端 pytest 11 case | `backend/tests/...` |
| 5 | 前端类型/图标/API | `types.ts` / `icons.tsx` / `model.api.ts` |
| 6 | ModelLibraryTab 组件 + SettingsPage 分支 | 新 `ModelLibraryTab.tsx` / `SettingsPage.tsx` |
| 7 | UI 风格自查（逐条过 §5.4 禁止清单 + 令牌表：无裸 hex/裸数字/emoji/link 款按钮/message 直调） | 新组件 + SettingsPage 分支 |
| 8 | `npm run check` + vitest + 手工 E2E | frontend |
| 9 | 编辑历史/注释署名+日期逐文件补 | 全部改动文件 |

---

**编写人**: 小欧
**编写时间**: 2026-09-24 20:34:12
**更新人**: 小欧
**更新时间**: 2026-09-24 21:27:36（v1.4：全文十遍通读整体化修订——消除悬空定案、修数字/编号硬伤、清除正文版本补丁标记）
