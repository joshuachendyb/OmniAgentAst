# 前端公用函数清单

**创建时间**: 2026-09-23 14:19:12
**编写人**: 小欧
**维护人**: 小欧
**最后更新时间**: 2026-11-19
**最近更新**: 2026-11-19 商量 新增 §4.2 notice 与 interact 两事件使用规范 + §4.1 登记 interact 事件

---

## 使用规则

1. **写代码前先查本清单**
2. **有公用函数必须使用，禁止重复实现**
3. **没有才创建新的（先查后建）**
4. **新函数必须添加到本清单（版本历史同步登记）**
5. **禁止向后兼容：不保留旧名称别名，不做新旧双轨**

### 前端控件规格铁律（2026-11-12 小欧 增补，强制）

与《开发人员戒律》第八章同源；本节为前端唯一执行清单。控件规格唯一真源：`frontend/src/theme/controlScale.ts`（登记见 §1.4），推导与验收线见 `doc-11月优化/[32]全站控件刻度统一与界面密度设计-小欧-2026-11-12.md`。

| 规则 | 说明 | 违反后果 |
|------|------|---------|
| **控件规格唯一定义点** | 控件高/圆角的**全部档位**只能在 `frontend/src/theme/controlScale.ts` 定义；其它任何文件不得写死控件高数值或另立刻度表 | 退回重做 |
| **禁沿用 UI 库缺省值** | 不得把 UI 库的缺省 token（如 antd 的 `controlHeight` 32 / `borderRadius` 6）当作项目标准；缺省值只作反例 | 退回重做 |
| **禁依赖库的派生公式** | 库按公式派生的档位（antd 的 `controlHeightSM` = base×0.75、`controlHeightLG` = base×1.25 等）必须**显式下发**后再用；放任派生会产出 21/35 这类非 4px 网格值 | 退回重做 |
| **密度只切档位** | 界面密度 = 「哪一档控件高生效」，不是「在某基线上减几 px」；密度**不得改字号** | 退回重做 |
| **字号恒 14** | 控件内字号恒 14px；**禁止用 antd `componentSize` 承载密度**（其 small 档会把 `Select`/`DatePicker` 字号切到 12） | 退回重做 |
| **流水线零变化** | 流水线（消息渲染区）控件在两档密度下必须像素不变；流水线内唯一 antd 控件走 small 档，故 small 档两档同值 | 退回重做 |
| **数字只在 TS 一处** | CSS 只消费 TS 解算出的变量，不得在 CSS 里写像素数字（与 [30] 排版单一真源同源纪律） | 退回重做 |

### 前端间距与行高铁律（2026-11-13 商量 增补，强制）

间距/行高唯一真源：`frontend/src/theme/spacing.ts`（登记见 §1.5）；数值刻度源：`utils/stepStyles.ts` 的 `Spacing`；控件内距源：`theme/controlScale.ts` 的 `CONTROL_PADDING`。

| 规则 | 说明 | 违反后果 |
|------|------|---------|
| **一个距离只归一处** | 兄弟元素之间的距离**只能**由父容器 `gap` 承担；严禁 `gap` 与子元素 `margin`/`marginBottom` 叠加表达同一段距离（父 8 + 子 4 = 12 的记账方式禁止） | 退回重做 |
| **padding 只做内容与容器边** | `padding` 用于控件内距、列表/面板内容区；**不得**用 padding 制造元素之间的间距 | 退回重做 |
| **margin 原则不用** | 仅两种例外且必须写注释：① 绝对定位/浮层贴边补偿（负 margin 抵消 padding）；② 行内文本流中无法用 gap 的场景 | 退回重做 |
| **间距只取语义档** | 一律用 `Gap.ROW/STACK/INLINE/SECTION/GROUP`，不直接引用 `Spacing` 数字；语义名承载「为什么是这个距离」 | 退回重做 |
| **行高必须显式下发** | 承载文字的容器必须显式 `lineHeight`，取值只能来自 `LineHeight.DENSE/BODY/LOOSE`；严禁继承 UI 库缺省行高 | 退回重做 |
| **禁自造留白数字** | 间距/行高/内距不得写裸数字；控件内距的例外值（文本框上下 2、徽标垂直 1）只在 `CONTROL_PADDING` 备案 | 退回重做 |

---

## 一、全局层（src/utils/ + src/theme/）

### 1.1 样式令牌（stepStyles.ts，全前端唯一视觉源）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `Colors` | 色板唯一源（TEXT 五档灰/BG/BORDER/PRIMARY/ERROR_BG 等）；禁硬编码色值 | — | 对象 |
| `Spacing` | 间距唯一源（XS=4/SM=6/MD=8/LG=12/XL=16）；禁裸数字间距 | — | 对象 |
| `FontSize` | 字号两档（PRIMARY=14/SECONDARY=12/SMALL=11）；禁 13 等中间档 | — | 对象 |
| `FontWeight` | 字重（BOLD/REGULAR 等） | — | 对象 |
| `Radius` | 圆角（SM=4/LG=8 等） | — | 对象 |
| `BorderWidth` | 边框宽度 | — | 对象 |
| `FontFamily` | 等宽字体族（MONO，代码/路径/技术文本；收敛目标，存量 5 处待统一）— 小欧 2026-10-05 | — | 对象 |
| `stepMargin` | 步骤间距（compact 区分） | compact: boolean | string |
| `isValidStepType` / `getAllStepTypes` | 步骤类型守卫/全量 | stepType | boolean / StepType[] |
| `getStepLabel` / `getStepPriority` / `getStepLayout` | 步骤标签/优先级/布局 | stepType | string / StepPriority / LayoutMode |
| `shouldBreakLine` / `hasExpandableDetails` | 是否换行/是否可展开 | stepType | boolean |
| `getStreamStyle` | 流式样式 | compact: boolean | CSSProperties |
| `TokenLayer` | token 三字段公用类型（替代各处私有 TokenTriple，DRY） | — | type |
| `formatTokenCompact` / `formatTokenFull` | token 紧凑/完整格式化 | TokenLayer | string |
| `formatTokenK` | taskinfo 行内 token 折 K/M 格式化（9200→"9.2K"，无值→"–"） | number \| null \| undefined | string |

### 1.2 设置页令牌（theme/settingsTokens.ts，派生自 stepStyles+chatTokens，不建大表）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `settingsSpacing` | 设置页间距（复用 Spacing + pagePadding=16/rowHeight=44/labelWidth=180） | — | 对象 |
| `settingsRadius` | 设置页圆角（复用 Radius） | — | 对象 |
| `settingsControl` | 控件宽度族（inputWidth 等统一 180；apiKeyWidth/baseUrlWidth=360；actionBtnWidth=120[65]） | — | 对象 |
| `settingsModalWidth` | 弹窗宽度三档（confirm=480/form=520/display=800） | — | 对象 |
| `settingsRowStyle` | 行容器样式单点（SettingRow/ProviderConfig/ModelParams/AddParamForm 四处复用） | — | CSSProperties |
| `settingsLabelStyle` | 行 label 样式单点（宽 180/14 号/常规字重） | — | CSSProperties |
| `settingsRowLayout` | 行布局常量（display/align/minHeight/labelWidth） | — | 对象 |
| `settingsShadow` | 保存条阴影 | — | string |

### 1.3 聊天令牌（theme/tokens.ts）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `chatTokens` | 聊天域令牌（settingsTokens 派生源之一） | — | 对象 |


### 1.4 控件刻度（theme/controlScale.ts，全站控件规格唯一真源）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `CONTROL_HEIGHT` | 控件高三档 × 两档密度（舒适 24/28/32、紧凑 24/24/28）——控件规格唯一定义点，禁沿用 UI 库缺省值/派生值 | — | 对象 |
| `CONTROL_RADIUS` | 全局圆角三档（sm4/normal6/lg8，取自 stepStyles 的 Radius 阶梯） | — | 对象 |
| `PAGE_RADIUS_FLAT` | 页面级圆角全档 4（设置页/文件页/事项工作区面板逐页审计结论） | — | 对象 |
| `CONTROL_HEIGHT_SM` | 小档控件高 24（两档密度同值，贴「文字不被压」22px 底线；流水线零变化锚点） | — | number |
| `CONTROL_PADDING` | 控件内距标准（`TEXT_INPUT_X` 12=4px 网格标准档、`TEXT_INPUT_Y_TIGHT` 2=视觉下限），禁沿用 UI 库的 4/11 缺省 | — | 对象 |
| `FOCUS_RING_WIDTH` / `FOCUS_RING_OFFSET` | 焦点环线宽 2 / 环到控件边缘间距 2，本项目自定义、与库 outline 缺省无关 | — | number |
| `controlHeightByDensity` | 取某密度下的控件高三档 | density | `{small, normal, large}` |
| `controlScaleTokens` | 根 ConfigProvider 的控件规格 token 组（控件高 3 档 + 圆角 3 档，全部显式下发） | density | 对象 |
| `pageControlTokens` | 页面级控件规格 token 组（normal 随密度、small 与 normal 齐平、圆角全档 4） | density | 对象 |

### 1.5 间距与行高（theme/spacing.ts，全站空白维度唯一真源）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `Gap` | 间距语义档（`ROW` 4 行内容补足 / `STACK` 6 同列兄弟 / `INLINE` 6 同行相邻 / `SECTION` 8 组内分组 / `GROUP` 12 大分组），数值派生自 `Spacing` 刻度 | — | 对象 |
| `LineHeight` | 行高三档（`DENSE` 1.4 密集区 / `BODY` 1.5 正文 / `LOOSE` 1.5714 需呼吸行），显式下发，禁继承 UI 库缺省 | — | 对象 |

**间距铁律（强制）**：①一个距离只能有一处归属——兄弟间距一律由父容器 `gap` 承担，严禁 `gap` 与 `margin` 叠加同一段距离；②`padding` 只做「内容与容器边」的留白，不制造元素间距；③`margin` 原则不用，仅两种例外且须注释：绝对定位贴边补偿、行内文本流无法用 gap 的场景；④间距数值只从 `Spacing` 刻度取，行高只从 `LineHeight` 三档取。

### 1.6 时间处理（time.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `parseTimeSafe` | 安全解析时间为 Date，非法返回 null | Date/string/number | Date\|null |
| `formatTimestamp` / `formatSafeTimestamp` | 时间戳格式化（安全版空值兜底） | number/string/Date | string |
| `formatTimestampSec` | 秒精度时间戳（`YYYY-MM-DD HH:MM:SS`，去小数秒；后端 ISO 微秒串直显时用） | number/string/undefined | string |
| `formatTime` / `formatTimeHMS` / `formatDate` | 时间/时分秒/日期格式化 | Date/string/number | string |
| `formatRelativeTime` | 相对时间（x 分钟前） | Date/string/number | string |
| `formatDurationHMS` | 秒数转时分秒时长 | sec: number | string |
| `formatDebugTime` | 调试时间戳（sseParser 等复用） | 无 | string |
| `probeMsText`（settings2/mediaProbeText.ts） | 探测腿毫秒转人话（485ms→"485 ms"，33200→"33.2 s"，null→""）；②图片能力验证 tip 复用 | number \| null \| undefined | 2026-11-09 |

### 1.7 文本规约（textNormalize.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `normalizeBlankLines` | 空行规约：连续空行折叠为一个，段首尾 trim，幂等；与后端 `normalize_blank_lines` 同一张规则表（见 backend/FUNCTIONS.md 1.7） | text: string | string |

### 1.8 视图派生（viewState.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `computeTaskActive` | 任务活跃判定提纯（streaming/highlight/badge 统一入口） | 状态入参 | boolean |
| `computeIsCurrentLive` | 是否当前直播任务判定提纯 | ComputeIsCurrentLiveArgs | boolean |

### 1.9 剪贴板/客户端（clipboard.ts / clientInfo.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `copyTextToClipboard` | 剪贴板复制（异常兜底） | text: string | Promise<void> |
| `getClientInfo` / `getClientOS` / `isMobile` | 客户端信息/系统/移动端判定 | 无 | ClientInfo/string/boolean |

### 1.10 日志样式（logStyles.ts，console 调试日志统一出口）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `LOG_STYLES` | 日志样式常量（debug 等） | — | 对象 |
| `logHeader` / `logFooter` / `logDivider` | 日志头/尾/分隔线 | title, style | void |
| `logContent` | 日志内容行 | label, data?, style? | void |
| `logAIComplete` / `logAIError` / `logUserSend` / `logHistoryLoad` | AI 完成/失败/用户发送/历史加载日志 | 各字段 | void |
| `logDebug` / `logError` | 通用调试/错误日志 | label, data/error | void |


### 1.11 Markdown 排版解算与外观偏好（utils/markdownStyles.ts / constants/appearancePrefs.ts / hooks/useAppearancePrefs.ts）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `mdStyles` | Markdown 排版唯一解算点：按场景×正文档位×密度解出 CSS 变量与场景 class（文档[30]） | scene, base?, density? | `{vars, rootClass, codeLineHeight, decorations}` |
| `DENSITY_PAD` | 密度→阅读区间距系数（comfortable 1 / compact 0.75）——**全仓唯一定义点** | — | 对象 |
| `codeBlockStyle` | 代码块行为样式（P3 横向滚动：whiteSpace/wordBreak/overflow/maxHeight）——唯一真源，CSS 侧不重复声明 | — | 对象 |
| `codeFenceLineHeight` | 围栏行高判定（含框线字符的取 1.1，其余取场景值） | content, fallback | number |
| `isNumericCell` | 表格数字列判定（走 tabular-nums 等宽数字） | 单元格文本 | boolean |
| `APPEARANCE_FONT_SIZES` / `APPEARANCE_DENSITIES` | 外观偏好合法档位（字号 12/14/16、密度 comfortable/compact）——**密度词表唯一真源** | — | 数组 |
| `AppearanceDensity` | 密度档位类型（由 `APPEARANCE_DENSITIES` 派生，不另写字面量联合） | — | 类型 |
| `clampFontSize` / `clampDensity` | 偏好值钳制：字号夹紧后向下吸附到合法档；密度非法值回落默认 | unknown | number / AppearanceDensity |
| `useAppearancePrefs` | 读取外观偏好并订阅变更（同标签页事件 + 设置保存广播 + 跨标签页 storage 事件） | — | `{fontSize, density}` |

### 1.12 内容变换与历史（markdown.tsx / searchTransformers.ts / stepContentUtils.ts / chatHistory.ts / sessionStorage.ts / chatMessages.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `renderContent` | markdown 内容渲染为 React 节点数组 | content: string | ReactNode[] |
| `transformSearchFilesData` | 搜索文件结果适配（unknown→SearchFilesData） | rawData: unknown | SearchFilesData |
| `transformSearchFileContentData` | 搜索文件内容适配 | rawData: unknown | SearchFileContentData |
| `formatStepContent` | 步骤内容格式化（空/undefined 兜底） | text | string |
| `debounce` | 通用防抖 | fn | debounced fn |
| `parseMessage` | 历史消息解析（unknown→Message） | rawMessage: unknown | Message |
| `loadHistoryMessages` / `loadLatestHistoryMessages` | 历史消息加载/最近加载 | 会话入参 | Promise<Message[]> |
| `saveSessionToCache` / `clearSessionCache` | 会话缓存写/清（STORAGE_KEY='chat_session_state'，5 分钟过期） | session 入参 | void |
| `saveChatState` | 聊天状态本地存 | state: unknown | void |
| `show*` 消息提示族 | 会话消息提示统一入口：保存/加载/冲突/网络（showSaveSuccess/showSaveError/showLoadError/showNetworkError/showConflictError 等）、任务（showTaskControlMessage/showTaskResultMessage 等）、会话新建（showNewSessionSuccess/showNewSessionError 等）、标题（showTitleSaved/showTitleUpdated 等）、通用（showError/showWarning/showInfo/showSuccess 系） | content/结果入参 | void（部分返回 boolean，如 handleConflictError） |

### 1.13 路径处理（utils/projectPath.ts，路径形态与深链唯一真源）

同文件另有项目根 ⇄ 相对路径转换（`toRelativePath`/`toAbsolutePath`）、路径形态判据（`isDriveAbsPath`/`isExternalAbsPath`/`isUnderRoot`/`isAbsDirLikePath`/`isDirLikePath`）、深链拼装（`buildFileDeepLink`/`resolvePathTarget`）与分隔符归一（`norm`），均属该模块既有职责，改动前先看本文件头注。

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `shortenPath` | 路径**展示**收敛：超长时丢弃中间段，保留盘符 + 末 `tail` 段（`E:\test_dir\report\a-task` → `E:\…\report\a-task`）；短路径原样返回。按段裁剪而非纯 CSS 省略号——同一机器前缀几乎相同，右端省略会把最有区分度的末段先吃掉。调用方仍须把完整值挂 `title` 供核对 — 商量 2026-11-18 | p: string, max?: number（默认 40）, tail?: number（默认 2） | string |

---

## 二、服务层（src/services/）

### 2.1 API 客户端（client.ts）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `AUTH_STORAGE_KEY` | 访问口令的 localStorage 键名（`omniagent_auth`） | — | string |
| `API_BASE_URL` | API 基址（`VITE_API_BASE_URL` 或相对路径 `/api/v1`），供 ChatPage 的 SSE fetch 使用 | — | string |
| `getApiBaseUrl` | API 基址解析：`VITE_API_BASE_URL` 或空串（同源相对路径，由 Vite proxy / Nginx 反代转发） | 无 | string |
| `getAccessToken` | 访问口令读取（认 `{state:{accessToken}}` 与裸 `{accessToken}`） | 无 | string\|null |
| `setAccessToken` | 访问口令写入（保留 persist 包络其余字段）；**写失败抛错**，调用方须处理 | string\|null | void |
| `ApiRequestConfig` | 请求级开关：`_skip401`（本请求 401 不清 token 不跳登录）、`_skipAuth`（本请求不附带 Authorization） | — | 接口 |

### 2.2 设置 API 簿（settings.api.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `settingsApi.getSchema` | 设置页 schema（6 分组） | 无 | SettingsSchema |
| `settingsApi.getMtime` | 配置 mtime（外部变更守卫） | 无 | number |
| `settingsApi.getAll` | 6 组全量值（data+sources+mtime） | 无 | SettingsAll |
| `settingsApi.getGroup` | 单组刷新 | group | 组数据 |
| `settingsApi.updateSettings` | PUT /settings 批量写 | patch | SettingsUpdateResult |

### 2.3 模型 API 簿（model.api.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `modelApi.getModels` | providers/models 层级 + current_model_ref | 无 | ModelsResponse |
| `modelApi.addModel` | 建模型（default_params/range/capabilities/param_options 同批） | data | ModelsResponse |
| `modelApi.updateModel` | 改模型（label/range/capabilities→model_meta；default_params 逐键 merge；`{}`=显式清空） | provider, model, data | ModelMutationResult |
| `modelApi.deleteModel` | 删模型（清参数/meta 块；删当前自动切换） | provider, model | ModelMutationResult |
| `modelApi.getProviders` | provider 列表 | 无 | ProviderEntry[] |
| `modelApi.addProvider` | 建 provider | data | ModelMutationResult |
| `modelApi.updateProvider` | 改 provider（clear=true 清空 api_key） | name, data | ModelMutationResult |
| `modelApi.deleteProvider` | 删 provider（级联；禁删最后一个） | name | ModelMutationResult |
| `modelApi.probeOutput` | 生成验证（按输出模态跑图腿 t2i/i2i 与视频腿 t2v/i2v；视频为异步任务，显式 30 分钟超时） — [15] 小欧-2026-11-09 | provider, model | `{ok, generate:{image?,video?}, conclusive, persisted, message}` |

### 2.4 其他 API 簿（config/chat/session/task/health.api.ts）

| 对象 | 方法 | 功能 |
|------|------|------|
| `configApi` | getConfig/updateConfig/switchCurrentModel/validateConfig/getModelList/getFullConfig/deleteProvider/updateModel/deleteModel/updateProvider/addModel/addProvider/fixConfig/getConfigPath/openConfigFolder/readConfigFile/readVersionFile | 全量配置读写与校验修复（旧链路；模型域已迁 model.api） |
| `chatApi` | validateService | 聊天服务校验 |
| `sessionApi` | createSession/listSessions/getSessionMessages/saveMessage/saveExecutionSteps/deleteSession/updateSession/getSession/getSessionTitlesBatch | 会话 CRUD 与消息落库 |
| `taskControlApi` | cancel/pause/resume/confirm | 任务控制 |
| `sessionTaskApi` | listTasks | 会话任务列表（useSSE 断线兜底复用） |
| `executionApi` | getTaskDetail/getTaskSteps | 任务详情/步骤 |
| `trustApi` | getTrust/revokeTrust | 信任查询/撤销 |
| `tokenUsageApi` | getChainTokens | 上下文链 token |
| `healthApi` | checkHealth/echo | 健康检查/回显 |
| `probeAlive` / `PROBE_TIMEOUT_MS` / `SLOW_RESPONSE_MS` | 后端存活判据与阈值（探活唯一出处：发送前预检/超时归因/顶栏胶囊共用；原 utils/network.ts 的 fetch+3s 已删） | 无 | Promise<boolean> / number |

### 2.5 错误处理（error/handler.ts，提示语唯一出口）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `ErrorType` | 错误类型枚举（WARNING/MODEL_CONFIG_ERROR/INFO 等；P1-3 对齐唯一提示规范） | — | enum |
| `showMessage` | 按类型统一提示（settings2 内 save/校验提示唯一入口） | ErrorType, msg | void |
| `showSuccess` | 成功提示（默认'操作成功'） | msg | void |
| `handleError` / `handleApiError` | 错误/ API 错误统一处理（含 ok:false 假成功识别） | error/context | void |
| `classifyError` | 错误分类 | error: unknown | ErrorType |
| `handleSSEError` | SSE 错误处理 | SSEErrorContext | void |
| `shouldShowError` / `isSilentError` / `clearExpiredErrors` | 去重展示/静默判定/过期清理 | key/error | boolean/void |
| `handleDangerousOperation` / `handleSecurityServiceDown` / `handleUserMessageSaveFailed` / `handleDuplicateClick` / `handleQuotaExceeded` | 场景化错误处理（危险操作/安全服务/消息落库/重复点击/配额） | — | ActionResult |

---

## 三、通用组件层（src/components/）

| 导出名 | 功能 | 位置 |
|--------|------|------|
| `CircleArrow` | 折叠箭头组件（消▲▼字符，三级折叠复用） | CircleArrow/ |
| `DropletIcon` | 水滴状态图标（success/error/warning） | DropletIcon/ |
| `GearIcon` | 齿轮图标 | GearIcon/ |
| `ThoughtWaitingIcon` / `ToolWaitingIcon` / `ActionWaitingIcon` | 等待图标组（内联提取统一导出，DRY） | WaitingIcons/ |
| `LogoGridIcon` / `TitleSpinIcon` | 品牌点阵/标题旋转图标 | AnimatedIcons/ |
| `PillBadge` | 徽标胶囊 | PillBadge/ |
| `ErrorBoundary` | 错误边界 | ErrorBoundary/ |
| `ShortcutPanel` | 快捷指令面板 | ShortcutPanel/ |
| `Layout` | 布局壳 | Layout/ |
| `HealthCheck` | 健康检查 | HealthCheck/ |
| `AuthorizationModal` | 授权弹窗 | AuthorizationModal/ |
| `CountdownRing` | 倒计时环（自绘 SVG：`<circle>` + strokeDasharray 算弧长，中心数字+「秒」绝对定位压在环心）。直径/环宽/字色/字重全取本项目令牌，不用 UI 库的 `size/strokeWidth/format` 派生；环色三档 主色→将到点橙→临近红（≤3s 数字同步脉冲）；盒子尺寸即直径，行内不需贴边补偿。HITL 授权弹窗（44）与 question 问询浮层（40）共用，只按直径分叉 — 商量 2026-11-18 | CountdownRing/ |
| `PanelCard` / `PanelChip` / `PanelRow` / `PanelEmpty` / `PanelIconButton` | 浮层卡片视觉壳族（计划/信任/问询三块浮层共用一套卡片语言）：`PanelCard` 壳（头部 title/meta/actions + 可选 subheader + 内容区 + 脚注，`raised` 自绘边框投影、`plain` 挂在 Popover 内不叠框）+ `PanelChip` 计数胶囊（`tone` 取 `ChipTone` 四档 `primary`/`warning`/`danger`/`default`，底色与字色由档位映射本项目语义色，不接受色名或色值）+ `PanelRow` 列表行（传 `onClick` 才是可点行，`hoverable` 给「行不可点但行内有悬停操作」的浅档底色；**行距唯一归属**是它自己的上下内距，调用方不得再叠 gap）+ `PanelEmpty` 空态文案 + `PanelIconButton` 纯图标按钮（自绘 `<button>`+`forwardRef`，盒高取控件小档 24，悬停底/焦点环走本项目色值，不用 UI 库按钮的缺省派生）。只收敛**视觉**，业务由调用方注入 — 商量 2026-11-18 | PanelCard/ |

---

## 四、通用 Hooks 层（src/hooks/）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `useStateWithRef` | state+ref 同步（闭包读最新值） | initial | [state, set, ref] |
| `useBeforeUnload` | 离开守卫（脏态拦截刷新/关闭） | BeforeUnloadOptions | void |
| `useLoadingMessage` | 加载提示 | options | 加载态 |
| `useInitializationProgress` | 初始化进度 | 入参 | InitializationProgress |
| `useSSE` | SSE 流式连接（断线重连+任务轮询兜底+idle 监视；复用 sessionTaskApi.listTasks） | 会话/任务入参 | 连接态+数据 |
| `useCountdown` | 倒计时唯一实现（纯展示）：开窗时按 `total` 算出截止时刻，之后逐秒采样「真实剩余秒数」而非自减（原自减在 0.1s/1.0s 各触发一次 → 第 1 秒掉 2 格，展示窗口比后端真实窗口短 1 秒）；到点恒为 0，换窗口靠 `resetKey` 重建截止时刻。授权弹窗与问询面板共用 — 商量 2026-11-18 | total: number, resetKey?: string \| null | number |

### 4.1 chat 特征层公用件（src/features/chat/，小欧 2026-10-05 新增）

| 导出名 | 位置 | 功能 | 参数 | 返回值 |
|--------|------|------|------|--------|
| `useDisclosure` | `hooks/useDisclosure.ts` | 折叠/展开状态 + 两道 a11y 事件聚合（Enter/Space 切换、全分支 stopPropagation）；只管切换与事件阻断，不管阈值/文案 | initial?: boolean | `{expanded, setExpanded, onToggleClick, onToggleKeyDown}` |
| `useStepRenderPrefs` | `components/pipeline/useStepRenderPrefs.ts` | 读后端 `appearance` 组的两个 step 渲染开关（「思考排版」「推理内容」）+ 订阅保存事件刷新；唯一真源=服务端 YAML | 无 | `StepRenderPrefs` |
| `SETTINGS_SAVED_EVT` | `src/constants/settingsEvents.ts` | 设置保存成功广播事件名（唯一定义点；生产侧仅 useSettings 派发，消费侧仅 useStepRenderPrefs 订阅）— 小欧 2026-10-05 | — | string |
| `MarkdownBody` | `components/pipeline/MarkdownBody.tsx` | thought 块正文 Markdown 渲染（围栏代码块/行内代码/粗体/斜体/1~3 级标题/无序列表子集；零新依赖，全程不用 dangerouslySetInnerHTML） | `{ text: string }` | JSX |
| `ReasoningIcon` | `components/WaitingIcons/index.tsx` | 推理折叠行前置图标（step 页面「推理内容...」左端）。`export const ReasoningIcon = SpinSquareIcon` 运行时代理别名（`ReasoningIcon = EyeIcon`），换图标只改该行取值；5 个备用图标 `EyeIcon`(眼睛) / `SignalBarsIcon`(43号) / `SunIcon`(58号) / `ApproachDotsIcon`(65号) / `SpinSquareIcon`(13号, 当前在用) 接口统一。`animating=true` 挂动画类(false 不挂即静止)，节奏唯一真源 `index.css`；`size` 默认 `Icon.BOX`(16px)，图形描边外缘正好填满盒子(与 `GearIcon` 同列齐整)。转/停由 `ThinkingStream` 的 `running` prop 按段序列派生传入 — 小欧 2026-10-07 | `{ size?: number; animating?: boolean }` | JSX |
| `EyeIcon` / `SignalBarsIcon` / `SunIcon` / `ApproachDotsIcon` / `SpinSquareIcon` | `components/WaitingIcons/index.tsx` | 推理折叠行图标组：当前在用 1 个（`SpinSquareIcon`）+ 备用 4 个（北京老陈令备用常驻，想用即改 `ReasoningIcon` 别名取值）。`viewBox` 统一收为图形外接框，缩放后填满 `Icon.BOX`、垂直居中；`animating` 条件挂动画类 | `{ size?: number; animating?: boolean }` | JSX |
| `Icon`（图标规格令牌） | `src/utils/stepStyles.ts` | step 行首图标统一规格：`BOX: 16`(盒子边长) + `STROKE: 2`(统一描边宽)。图标组件 `size` 默认取 `Icon.BOX`、`strokeWidth` 取 `Icon.STROKE`；图形需"填满盒子"时令描边外缘=viewBox 边界 — 小欧 2026-10-07 | — | `{ BOX: 16; STROKE: 2 }` |
| `ShortcutHelp` / `SHORTCUT_GROUPS` | `components/input/ShortcutHelp.tsx` | 输入帮助分层唯一落点：输入框内只保留核心 placeholder（提交语义 + 能力提示尾段 `@ 引用 · 拖入文件 · 粘贴图片`，见 `InputCore.PLACEHOLDER_HINTS`），原常驻编号清单的其余输入方式迁入「输入技巧」浮层（按 输入 / 文件与引用 / 图片 三组归类，可随新增扩展）；入口经 `SubmitBar.middleExtra` 落在底部按钮行中段（右对齐、与按钮同高，输入区零额外高度；打字后/受阻态 placeholder 隐藏时入口仍常驻）。**维护唯一入口**：增删改输入方式只改 `SHORTCUT_GROUPS`，浮层分组自动跟随 — 商量 2026-11-13 | — | `ShortcutGroup[]` / JSX |
| notice 信封（`type=notice`） | `services/sseParser.ts` + `hooks/useTaskInfo.ts` | 通知信封统一解析：`kind`(种类) + `phase`(start/done/failed) + `content`(文案) + 可选 `items`(结构化载荷) + 可选 `only_event`(呈现标记, 默认 false)。三态都 push 进 executionSteps（事件列表）；`phase=start/failed` 占位置2、`done` 清位置2，**例外**：`only_event=true`（schedule error）只进事件列表、不画卡片、不占位置2。`kind=schedule` 且 `!only_event` 且带 items → 投 `onScheduleUpdate` 写计划卡片。老 notice 无 `items`/`only_event` 字段按缺省处理，零退化 — 商量 2026-11-19 | — | `ExecutionStep{notice_kind,notice_phase,content,items?,only_event?}` |
| `ScheduleItem` / `scheduleList` | `streams/chatStreamTypes.ts` + `streams/chatStreamStore.ts` | 执行计划清单走 **notice 独立通道**（三态均发）：后端成功/可容忍发 `notice(kind=schedule, phase=done, items=[{content,status}])`，完全错误发 `notice(phase=failed, only_event=true)`；`sseParser` 按 `kind+phase+only_event` 分派，done 投 `onScheduleUpdate` → `chatStreamStore.setScheduleList` 写会话快照（刷新恢复），failed 只进事件列表、卡片保持上一份。清单类型 `ScheduleItem[] \| null` 从 `chatStreamTypes.ts`（backupTypes.ts 改名）单一真源导出，入 `SessionSnapshot`/`SNAPSHOT_KEYS`/`toBackupOf`/`restore`。后端仅 SSE 转发副本摘除 schedule 工具行（`sse_formatter`，判据 `tool_registry.visible_in_steps`），落库/喂 LLM/历史 conv 的 observation 原样保留（工具属性 `hide_from_steps` 声明）。完整设计见 [47] 文档 — 商量 2026-11-19 | — | `ScheduleItem[] \| null` |
| `ScheduleCard` | `components/taskinfo/ScheduleCard.tsx` | taskinfo 左组「执行计划」入口（紧跟状态徽标）+ 浮层卡片（`计划 N/M`，窄档只显示 `N/M`，无清单不渲染）：条目按 `completed/in_progress/pending/cancelled` 三档着色，脚注点出「进行中：xxx」；与问询面板的分工是**主动查 vs 阻塞弹出**。清单读 `store.scheduleList`（notice 唯一来源），经 `useChatStreamSession(sessionId)` 订阅；**入口只属于当前任务** —— 信息条转入历史详情（`detail` 非空，指标来自 DB）时不渲染，避免「A 任务的计划配 B 任务的耗时/步数」 — 商量 2026-11-19 | `{list: ScheduleItem[] \| null, compact?: boolean}` | JSX |
| interact 信封（`type=interact`） | `services/sseParser.ts` + `streams/chatStreamTransport.ts` | 通用双向交互事件统一解析与分派：`interaction_id` + `kind` + `event`(ask/answered/cancelled/expired) + `content` + 可选 `payload`。sseParser 只解析框架通用字段、push executionSteps 并投 `onInteract`（不认识 kind 语义）；transport 的 `interactHandlers` 按 kind 分派，`kind=question` 读写 `pendingQuestion`/`hitlWaitingKeys`（ask 开窗、answered/cancelled/expired 清窗，清窗只认后端收口帧）。载荷类型 `InteractPayload` 单一真源在 `chatStreamTypes.ts`。question 为首个使用者，新增交互 tool 只加一个 kind 分支，框架层零改 — 商量 2026-11-19 | — | `ExecutionStep{interaction_id,interact_kind,interact_event,content,interact_payload?}` |

### 4.2 SSE 事件使用规范：notice 与 interact

前端只消费两类 SSE 事件信封（业务 tool 仍走 observation 步，不走这两类）：**notice 单向通知**与**interact 双向交互**。两者并列，不可混用。完整设计：notice 见 [47]，interact 见 [48]，设计说明见 [49]。

#### 4.2.1 选型（什么时候用哪个）

| 判断 | notice | interact |
|------|--------|----------|
| 方向 | 后端→前端单向告知，不需要用户响应 | 后端发起→用户响应→回传唤醒后端阻塞 |
| 典型 | 执行进度、摘要/安装提示、计划清单 | 问询（question）、确认（confirm）、选择 |
| 前端呈现 | 事件列表 + 可选卡片（任务信息条） | 专属浮层（QuestionDock / 授权弹窗） |
| 回传 API | 否 | 是（answer / confirm API 唤醒后端） |
| 生命周期字段 | `phase`: start/done/failed | `event`: ask/answered/cancelled/expired |

#### 4.2.2 字段契约（速查，完整定义见各规范文档）

| 事件 | type | 字段 |
|------|------|------|
| notice | `notice` | `kind` + `phase` + `content` + `items?` + `only_event?` |
| interact | `interact` | `interaction_id` + `kind` + `event` + `content` + `payload?` |

#### 4.2.3 前端处理规范

- **两层分派**：sseParser 只解析框架通用字段，不认识 kind 语义；分派层按 kind 路由——notice 走各 notice handler（如 `onScheduleUpdate`），interact 走 transport 的 `interactHandlers`。解析层不得写任何 tool 专属字段。
- **事件列表**：两类事件都 push 进 executionSteps，归 meta 不进业务流水线（否则查看区空白）。
- **呈现差异**：notice 用 `phase` 控制卡片占/清位置2（`only_event=true` 只进事件列表）；interact 用 `event=ask` 弹浮层、`answered/cancelled/expired` 清窗。
- **清窗权威**：interact 清窗只认后端收口帧，前端倒计时纯展示，不得自行清窗（双计时源会漂移）。
- **单一真源**：notice 清单读 `store.scheduleList`（notice 唯一来源）；interact 问询读 `store.pendingQuestion`（分派层唯一写入点）。
- **扩展新 kind**：notice 加 kind 走对应 handler；interact 加 `kind==='xxx'` 分支 + 专属 UI，框架层（sseParser / InteractStep / stepFilter）零改。

#### 4.2.4 不变量

1. 不混用：通知不弹阻塞浮层，交互不发 notice 卡片。
2. interact 的 ask 之后必有且仅有一个收口帧；前端清窗只认收口帧。
3. 两类事件均 SSE-only（不落库），工具行由 `hide_from_steps` 屏蔽，但落库/喂 LLM 照常。
4. 老帧缺可选字段（`items`/`only_event`/`payload`）按缺省处理，零退化。

---

## 五、settings2 特征层（src/features/settings2/）

### 5.1 纯函数（utils/modelUtils.ts，无 JSX，可单测）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `isDirty` | 模型 Tab 脏态（值≠默认且未被 env 接管；对象/数组经 sameValue 深比） | params, defaults, env | Record<string,boolean> |
| `clampToRange` | 超范围截断 | value, range? | unknown |
| `validate` | 保存前 schema 校验（首个错误定位；null/整数/step/范围/选项全规则，对齐后端 _validate_value） | items, values | {key,message}\|null |
| `isCapsDirty` | 能力脏判定（集合语义：排序后比，防手写 YAML 顺序假脏）[65] | caps, baseline | boolean |
| `CAPABILITY_OPTIONS` | 能力枚举单源词表（text/image/video/audio/pdf；渲染与合并共用）[65] | — | {label,value}[] |
| `KNOWN_CAPABILITY_VALUES` | 已知能力值集合单源（setCapabilities 未知值合并用）[65 十遍会审 F4] | — | ReadonlySet<string> |

### 5.2 图标行组件（components/icons.tsx，禁 emoji，全部 antd SVG）

| 导出名 | 功能 |
|--------|------|
| `SettingIcon` | Tab 图标唯一出口（Record<TabKey>，随选中态继承主色） |
| `DirtyDot` | 已修改角标（6px 圆点 + 12px 次文） |
| `EnvTag` | env 接管标注（橙色 Tag） |
| `DefaultTag` | 默认值未落盘标注（灰色 Tag） |
| `CopyIcon` | 只读复制按钮图标 |

### 5.3 设置 Hook 契约（hooks/useSettings.ts，全局单层 state）

| 返回项 | 功能 |
|--------|------|
| `state` / `saving` / `restartKeys` / `highlightKey` | 全局态/保存中/重启键/高亮键 |
| `dirtyCount` / `isGroupDirty` / `groupOfKey` / `GROUP_ORDER` | 脏计数（含能力脏 +1[65]）/组脏判定/键归属/Tab 顺序（后端 schema 键序唯一源） |
| `load` / `checkMtime` / `setValue` | 首载（S2 脏保留）/mtime 守卫/改控件（S6 回滚消脏） |
| `saveGroup` / `saveAll` / `saveModelGroup` | 存本组/存全部/存模型组（参数通道+能力通道双通道[65]；空变更早返防 `{}` 误清） |
| `selectProvider` / `selectModel` | 焦点切换（BUG-D 先存后切；四通道回填能力+基线[65]） |
| `setParam` / `addParam` / `setCapabilities` / `resetParams` | 改参（env 禁+枚举拦截+越界校正）/加参（判重+形态注入[65]）/改能力（Q1 未知合并[65]）/重置（只清参数脏，能力脏保留[65 十遍会审 F1]） |
| `refreshModels` / `syncMtime` / `patchModel` / `patchState` / `setActiveTab` | 模型列表刷新/mtime 同步/局部 patch/切 Tab |

---

## 六、使用示例

### 6.1 正确做法

```tsx
// 有公用，直接使用
import { Colors, Spacing, FontSize } from '@/utils/stepStyles';
import { settingsControl, settingsRowStyle } from '@/theme/settingsTokens';
import { isCapsDirty, CAPABILITY_OPTIONS } from '../utils/modelUtils';
import { showMessage, ErrorType } from '@/services/error/handler';

if (isCapsDirty(caps, baseline)) {
  showMessage(ErrorType.WARNING, '能力已修改');
}
```

### 6.2 错误做法

```tsx
// 错误：重复实现已有函数/硬编码令牌
const myIsCapsDirty = (a: string[], b: string[]) =>
  JSON.stringify(a) !== JSON.stringify(b); // 禁止！已有 isCapsDirty（且已做排序语义）
<div style={{ color: '#8c8c8c', marginLeft: 12, width: 120 }} /> // 禁止！用 Colors.TEXT.SECONDARY + Spacing.XL + settingsControl.actionBtnWidth
```

---

## 版本历史

| version | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-09-23 14:19:12 | 初始版本：登记全局层（utils 1.1–1.9/theme 令牌）、服务层（api 簿 2.1–2.4/error handler 2.5）、通用组件层、通用 Hooks 层、settings2 特征层（modelUtils/icons/useSettings 契约）；同步登记 [65] 十遍会审新抽公用（settingsControl.actionBtnWidth、KNOWN_CAPABILITY_VALUES、isCapsDirty 排序语义、resetParams 联合置脏） | 小欧 |
| v1.1 | 2026-11-02 | 探活口径收敛：删 utils/network.ts（checkNetworkConnection，名"网络检查"实为后端健康检查），改为 services/api/health.api.ts 的 probeAlive + PROBE_TIMEOUT_MS + SLOW_RESPONSE_MS 单一出处，1.7 与 2.4 同步登记 | 小欧 |
| v1.2 | 2026-11-10 | §4.1 chat 特征层新登记 `INPUT_HINTS`（`components/input/InputCore.tsx`）：输入框空态静态帮助清单（6 条输入方式），编号按数组下标自动生成；增删改输入方式只改数组、无需动 JSX；与动态提示 `executingHint`（执行中插话/正在提交）互斥且不编号 | 小欧 |
| v1.3 | 2026-11-12 | §1.4 新登记 `controlScale.ts`（`theme/controlScale.ts`）：**全站控件刻度唯一真源** —— 控件高三档（24/28/32，等差 4px）× 两档密度（紧凑档整档下移一档、小档 24 两档同值）+ 全局圆角三档（取自 stepStyles 的 Radius 阶梯）+ 页面级圆角全档 4 预设 + `controlScaleTokens`/`pageControlTokens` 两个 token 构造器。配套文档[32]；§1.4–§1.11 章节序号顺延（原 1.4–1.9 后移一位，无交叉引用需改） | 小欧 |
| v1.4 | 2026-11-12 | §1.10 新登记 `markdownStyles.ts` / `appearancePrefs.ts` / `useAppearancePrefs.ts`（补登上一轮遗漏）：Markdown 排版解算（`mdStyles` / `codeFenceLineHeight` / `isNumericCell` / `codeBlockStyle`，文档[30]）与外观偏好读取（`APPEARANCE_FONT_SIZES`/`APPEARANCE_DENSITIES` 密度词表唯一真源、`AppearanceDensity` 类型、`clampFontSize`/`clampDensity`、`useAppearancePrefs`）；`DENSITY_PAD` 登记为阅读区间距系数唯一真源 | 小欧 |
| v1.5 | 2026-11-12 | §使用规则 新增「前端控件规格铁律（强制）」七条：控件规格唯一定义点（`theme/controlScale.ts`）、禁沿用 UI 库缺省值、禁依赖库的派生公式、密度只切档位、字号恒 14（禁 `componentSize` 承载密度）、流水线零变化、数字只在 TS 一处；与《开发人员戒律》第八章同源，本清单为前端唯一执行位置；依据文档[32] | 小欧 |
| v1.6 | 2026-11-13 | §4.1 登记改为 `ShortcutHelp` / `SHORTCUT_GROUPS`（`components/input/ShortcutHelp.tsx`）：撤销 `INPUT_HINTS` 编号清单常驻输入框的做法，输入框仅保留核心 placeholder；其余输入方式按 输入/文件与引用/图片 三组归入「输入技巧」浮层（原名「全部技巧」）；能力提示尾段并入 placeholder（`@ 引用 · 拖入文件 · 粘贴图片`），入口置于按钮行中段；`InputCore` 显式下发上下留白 4→2；增删改输入方式只改 `SHORTCUT_GROUPS` | 商量 |
| v1.7 | 2026-11-13 | §1.4 新增 `CONTROL_PADDING`（`TEXT_INPUT_X` 12 / `TEXT_INPUT_Y_TIGHT` 2）与 `FOCUS_RING_WIDTH`/`FOCUS_RING_OFFSET`（2/2）：文本输入水平内距脱离库缺省 11px 改为 4px 网格标准档，焦点环规格集中定义；`InputCore` 删本地 `HINT_LEFT_PX`/`TEXTAREA_PAD_Y`，`ChatInput` 的 `outlineOffset`/`borderRadius` 改走令牌；`tokens.ts` 的 radius/gap 派生自 `Radius.DEFAULT`/`Spacing.MD`；`stepStyles.ts`/`tokens.ts`/`controlScale.ts` 顶部补「严禁使用 antd 默认规格属性」铁律横幅 | 商量 |
| v1.8 | 2026-11-13 | 新增 §1.5「间距与行高」（`theme/spacing.ts`，全站空白维度唯一真源）：`Gap`（ROW/STACK/INLINE/SECTION/GROUP 五档语义）+ `LineHeight`（DENSE/BODY/LOOSE 三档），并立间距铁律——一个距离只归一处（兄弟间距由父 gap 独占）、padding 只做内容与容器边的留白、margin 原则不用（仅绝对定位贴边与行内文本流两种例外且须注释）；§1.5–§1.11 顺延为 §1.6–§1.12。落地：ChatInput/InputCore/SubmitBar/ShortcutHelp/InputHistoryPanel/FileTrailPanel/SessionLayout/TaskInfoBar 的 gap 改用语义档，删多处 marginBottom/marginLeft 与 padding 叠加，行高改走 LineHeight | 商量 |
| v1.9 | 2026-11-18 | 三块浮层同一套卡片语言：§三 新登记 `PanelCard`/`PanelChip`/`PanelRow`/`PanelEmpty`（`components/PanelCard/`，只收敛视觉：壳 raised/plain 两形态 + 三原子；`PanelRow` 横向内距归零使行文字与标题同一条左轴线，`hoverable` 给「行不可点但行内有悬停操作」的浅档底色）；§四 新登记 `useCountdown`（`hooks/useCountdown.ts`，按截止时刻采样，修首秒双减，授权弹窗与问询面板共用）；§4.1 新登记 `useScheduleList` + `ScheduleCard`（执行计划清单派生自步骤流 + taskinfo 右组「计划 N/M」入口）；§1.13 新登记 `shortenPath`（`utils/projectPath.ts`，长路径展示收敛，信任清单用；同文件路径转换/判据/深链拼装一并说明）；`Size.PANEL_LIST_MAX_H`(360) 作为浮层列表限高唯一刻度 | 商量 |
| v1.10 | 2026-11-18 | 去 UI 库缺省派生两处：§三 新登记 `CountdownRing`（`components/AuthorizationModal/CountdownRing.tsx`，倒计时环改自绘 SVG，直径/环宽/字色全取本项目令牌，盒子尺寸即直径并去掉原来的假留白，HITL 弹窗与 question 浮层共用只按直径分叉）；§三 `PanelCard` 行补登 `PanelIconButton`（自绘图标按钮，盒高恒 24、悬停底与焦点环取本项目色值），并明确 `PanelRow` 是**行距唯一归属**（调用方不再叠 gap） | 商量 |
| v1.11 | 2026-11-18 | HITL 授权弹窗彻底脱离 UI 库缺省：§三 `PanelChip` 色调升级为 `ChipTone` 四档并新增 `danger`（危险类底/字取 `ERROR_BG`/`ERROR_TEXT`），原 antd 预设色名（red/orange/blue/volcano/geekblue）全部作废，严重度只留 删除/处置=danger、写入/命令=warning、读取/任务=primary 三级；`AuthorizationModal` 的裸色值清零改取 `Colors.*`，`Tag`/`Typography.Text` 换成本仓胶囊与自绘 `<span>`，纵向节奏收归根节点 `gap`（各块 `marginBottom` 删除），行高显式下发 `LineHeight` 三档、参数区高度由「行数 × 字号 × 行高」推导；`HITLModalShell` 边框/圆角/投影/内距收进 `styles.content` 并居中（原库默认 `top:100px` 与 `contentPadding 20/24` 叠加已消除） | 商量 |
| v1.12 | 2026-11-18 | §4.1 `ScheduleCard` 入口落位改述：由 taskinfo 右组迁至**左组状态徽标之后**（徽标答「这一轮什么状态」，计划答「进行到哪一步」，同属一句状态），TaskInfoBar 位置表由 11 位改 12 位。另 §三 补登 `PanelChip` 的 `danger` 色调后 `QuestionDock` 宽度口径：改 520 定宽（与 HITL 弹窗同宽，产品定宽不按字数推导）+ `90vw` 兜底，浮层不得通栏 | 商量 |
| v1.13 | 2026-11-18 | §4.1 `useScheduleList` 口径重写：清单改从观察步 `tool_result[i].llm_data`（后端归一后的 `items` + `exec_code`）派生，不再读 action 步的模型原文入参；三条口径入文 —— 任务边界即清单边界（越过 `start` 即无清单，新任务复位）、只认 `exec_code==='success'` 的落地结果（被拒/失败不显示假的「计划已生效」）、失败不改清单（跳过继续往前找，成功但空清单＝已清空就地收口）；同一步多次调用取后者。§4.1 `ScheduleCard` 补「入口只属于 `steps` 所在任务」：信息条展示历史详情时不渲染，避免两套事实混排 | 商量 |
| v1.14 | 2026-11-19 | `CountdownRing` 迁共享目录并具名导出，§三路径同步；question 事件归 meta；问询清窗加 id 守卫 | 商量 |
| v1.15 | 2026-11-19 | 执行计划清单改走 notice 通道：`tool_registry.visible_in_steps` 统一判据（工具属性 `hide_from_steps`）令 SSE 转发副本摘除 schedule 工具行（落库/喂 LLM 不动）；前端 `setScheduleList`→快照、`ScheduleCard` 读 store，删 `useScheduleList` | 商量 |
| v1.16 | 2026-11-19 | notice 三态化：三态均发 notice 且均返回 LLM+落库；error 发 `failed`+`only_event=true`（仅事件列表、不画卡片不占位置2），warning/success 发 `done`（事件列表+卡片）；新增 `only_event` 呈现标记（notice 可选字段，默认 false 零退化）；§三补 notice 信封登记；`backupTypes.ts` 改名 `chatStreamTypes.ts`（名副其实）；完整设计见 [47] 文档 | 商量 |
| v1.17 | 2026-11-19 | schedule 新增 `plan_stage` 必填参数(init/update/finish)：LLM 主动阶段决策, 与 items 宽松核对, 反馈进 `llm_data.plan_stage_note`; 阶段中文含义前置到 summary/notice content(`任务计划:初建/更新/结束;`); schema required 含两参数 | 商量 |
| v1.18 | 2026-11-19 | §4.1 登记 interact 信封(type=interact)：sseParser 只解析通用字段投 onInteract、transport interactHandlers 按 kind 分派；§4.2 新增 notice 与 interact 两事件使用规范(选型/字段契约/处理规范/不变量)；完整设计见 [47][48][49] | 商量 |