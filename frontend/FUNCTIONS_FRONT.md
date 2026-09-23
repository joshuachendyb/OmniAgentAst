# 前端公用函数清单

**创建时间**: 2026-09-23 14:19:12
**编写人**: 小欧
**维护人**: 小欧
**最后更新时间**: 2026-09-23 14:19:12
**最近更新**: 2026-09-23 14:19:12 小欧 v1.0 初始版本：登记全局层（utils/theme）、服务层（api/error）、通用组件层、通用 Hooks 层、settings2 特征层；同步登记 [65] 十遍会审新抽公用（settingsControl.actionBtnWidth、KNOWN_CAPABILITY_VALUES、isCapsDirty 排序比）

---

## 使用规则

1. **写代码前先查本清单**
2. **有公用函数必须使用，禁止重复实现**
3. **没有才创建新的（先查后建）**
4. **新函数必须添加到本清单（版本历史同步登记）**
5. **禁止向后兼容：不保留旧名称别名，不做新旧双轨**

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
| `stepMargin` | 步骤间距（compact 区分） | compact: boolean | string |
| `isValidStepType` / `getAllStepTypes` | 步骤类型守卫/全量 | stepType | boolean / StepType[] |
| `getStepLabel` / `getStepPriority` / `getStepLayout` | 步骤标签/优先级/布局 | stepType | string / StepPriority / LayoutMode |
| `shouldBreakLine` / `hasExpandableDetails` | 是否换行/是否可展开 | stepType | boolean |
| `getStreamStyle` | 流式样式 | compact: boolean | CSSProperties |
| `TokenLayer` | token 三字段公用类型（替代各处私有 TokenTriple，DRY） | — | type |
| `formatTokenCompact` / `formatTokenFull` | token 紧凑/完整格式化 | TokenLayer | string |

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

### 1.4 时间处理（time.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `parseTimeSafe` | 安全解析时间为 Date，非法返回 null | Date/string/number | Date\|null |
| `formatTimestamp` / `formatSafeTimestamp` | 时间戳格式化（安全版空值兜底） | number/string/Date | string |
| `formatTime` / `formatTimeHMS` / `formatDate` | 时间/时分秒/日期格式化 | Date/string/number | string |
| `formatRelativeTime` | 相对时间（x 分钟前） | Date/string/number | string |
| `formatDurationHMS` | 秒数转时分秒时长 | sec: number | string |
| `formatDebugTime` | 调试时间戳（sseParser 等复用） | 无 | string |

### 1.5 文本规约（textNormalize.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `normalizeBlankLines` | 空行规约：连续空行折叠为一个，段首尾 trim，幂等；与后端 `normalize_blank_lines` 同一张规则表（见 backend/FUNCTIONS.md 1.7） | text: string | string |

### 1.6 视图派生（viewState.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `computeTaskActive` | 任务活跃判定提纯（streaming/highlight/badge 统一入口） | 状态入参 | boolean |
| `computeIsCurrentLive` | 是否当前直播任务判定提纯 | ComputeIsCurrentLiveArgs | boolean |

### 1.7 剪贴板/网络/客户端（clipboard.ts / network.ts / clientInfo.ts）

| 函数名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `copyTextToClipboard` | 剪贴板复制（异常兜底） | text: string | Promise<void> |
| `checkNetworkConnection` | 网络连通检查 | — | Promise<boolean> |
| `getClientInfo` / `getClientOS` / `isMobile` | 客户端信息/系统/移动端判定 | 无 | ClientInfo/string/boolean |

### 1.8 日志样式（logStyles.ts，console 调试日志统一出口）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `LOG_STYLES` | 日志样式常量（debug 等） | — | 对象 |
| `logHeader` / `logFooter` / `logDivider` | 日志头/尾/分隔线 | title, style | void |
| `logContent` | 日志内容行 | label, data?, style? | void |
| `logAIComplete` / `logAIError` / `logUserSend` / `logHistoryLoad` | AI 完成/失败/用户发送/历史加载日志 | 各字段 | void |
| `logDebug` / `logError` | 通用调试/错误日志 | label, data/error | void |

### 1.9 内容变换与历史（markdown.tsx / searchTransformers.ts / stepContentUtils.ts / chatHistory.ts / sessionStorage.ts / chatMessages.ts）

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

---

## 二、服务层（src/services/）

### 2.1 API 客户端（client.ts）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `API_BASE_URL` | API 基址（VITE_API_BASE_URL 或 /api/v1） | — | string |
| `getApiBaseUrl` | API 基址解析（环境变量→window→127.0.0.1:8000 兜底） | 无 | string |
| `getAccessToken` | 访问 token 读取 | 无 | string\|null |

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

---

## 四、通用 Hooks 层（src/hooks/）

| 导出名 | 功能 | 参数 | 返回值 |
|--------|------|------|--------|
| `useStateWithRef` | state+ref 同步（闭包读最新值） | initial | [state, set, ref] |
| `useBeforeUnload` | 离开守卫（脏态拦截刷新/关闭） | BeforeUnloadOptions | void |
| `useLoadingMessage` | 加载提示 | options | 加载态 |
| `useInitializationProgress` | 初始化进度 | 入参 | InitializationProgress |
| `useSSE` | SSE 流式连接（断线重连+任务轮询兜底+idle 监视；复用 sessionTaskApi.listTasks） | 会话/任务入参 | 连接态+数据 |

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
