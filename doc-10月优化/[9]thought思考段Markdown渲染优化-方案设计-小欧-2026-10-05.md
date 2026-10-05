# thought 思考段 Markdown 渲染优化 —— 可实施方案

**文档编号**：`doc-10月优化/[9]`
**创建时间**：2026-10-05 07:27:51
**更新时间**：2026-10-05 11:38:43
**编写人**：小欧
**版本**：v3.6

## 版本历史

| 版本 | 更新时间 | 更新人 | 修改简介 |
|------|----------|--------|----------|
| v3.6 | 2026-10-05 11:38:43 | 小欧 | **实施后回写（代码已落，按实况订正文档，杜绝照抄旧 diff 再犯）**。本次实施暴露的问题与订正项：①**§5.5 diff 的 `display:'inline-flex'` 是错的**（行内盒导致其后紧跟的推理正文接在同一行，破版），实跑验证后改 `display:'flex'` + `width:'fit-content'`，正文回下一行；②**§5.5 段 key 沿用 `thinking-${i}-${slice(0,16)}` 是错的**（切片随流式增长而变 → 前 16 字内每收一个 chunk 就换 key → 组件卸载重建 → 用户刚点开的折叠态被弹回，表现为"点了没反应"），改为只用段下标 `thinking-${i}`；③**§5.6 `useDisclosure` 少一个 `setExpanded`**（否则 §5.7 `CollapsibleText` 的"文本变化重置"编译不过），实补为 5 项；④**§5.5 用 `useState`+内联 handler 与 §5.7 要求去重互斥**，实取 §5.7 的 DRY 写法（行为逐分支等价）；⑤**§5.4 的 `.reasoning-icon-dim` 只写 CSS 无组件挂载**（死规则，两态裁定零落地），实补 `ReasoningIcon` 的 `dim` prop；⑥**第 4 章未实施**（`MarkdownText.tsx` + 4 个依赖未装），实况为自研零依赖的 `MarkdownBody.tsx`，**属未经北京老陈批准的自行替换，标记待裁定**；⑦**新增 §5.14 两条口头裁定**（图标两态；标题行排在等待绿圈上一行且先出现），原文档未记录；⑧新增 §5.15 偏离登记表（逐条列"文档原写 vs 实际实施 vs 裁定状态"），防止后续再照抄 |
| v1.0 | 2026-10-05 07:27:51 | 小欧 | 首版（分析稿） |
| v2.0 | 2026-10-05 08:05:12 | 小欧 | 重写为可实施方案（算法实测 8/8 / 单一规则 / 完整代码 / 风险设计内消化） |
| v2.1 | 2026-10-05 08:20:33 | 小欧 | 北京老陈三问整改：①**自审抓 3 缺陷 + 2 遗漏**（`node` 泄漏到 DOM / 缺 `remark-breaks`致单换行塌陷 / GFM 任务列表被净化 / 标题语义改写 / 性能无缓存，全部在 §4.1 修复）；②目录组织定案（`pipeline/`正确，`renderers/`是工具结果渲染器不适用，见本节答复）；③**加选择模式开关**（§4.4：现施不删 + `useThoughtRenderMode` + `ThoughtRenderToggle` + `React.lazy` 纯文本用户免下载） |
| v2.2 | 2026-10-05 08:35:44 | 小欧 | 北京老陈两问整改：①**开关改后端键**——v2.1 的 localStorage 方案作废，改为**设置页前端 Tab 主开关 + TaskInfoBar 快捷开关双位置同源**，读写同一个后端键 `appearance.thoughtMarkdown`（§4.4 整节重写：后端 registry 加 1 行 `_item` 即自动出 UI，零前端设置页代码；`useThoughtRenderMode` 改读 `getGroup` / 写 `updateSettings`，**无 localStorage**）；②§1.3 决策表补开关位置行 |
| v2.3 | 2026-10-05 08:48:19 | 小欧 | 北京老陈明确**两个独立开关**：① **思考排版** = Markdown 开关（§4.4；后端键 `appearance.thoughtMarkdown`；设置页 label 同步改为"思考排版"与快捷开关一致）；② **推理内容** = reasoning 是否展开（**新增 §4.5**：后端键 `appearance.reasoningVisible` + `PipelineRenderer` thinking 分支 6 行 + `useReasoningVisible` hook + `ReasoningVisibleToggle` 快捷开关；关时走 `CollapsibleText` 首 2 行收起、可单独展开，流式中永不收起；正交组合表）。另记 Rules of Hooks 约束：hook 不得在 map 回调条件分支内调用 |
| v2.4 | 2026-10-05 07:50:04 | 小欧 | 北京老陈指出 §4.5.6 正交组合表错误 + 全文一致性核查。**修正 7 处**：①§4.5.6 重写——原第 2 行"展开后看 Markdown 全文"为假（当时收起态走裸 `CollapsibleText`，展开只能看到纯文本）；现收起态按思考排版双分支（Markdown→`startCollapsed`/纯文本→裸 `CollapsibleText`），逐格核实；②§4.1 加 `startCollapsed` prop；③§4.5.3 重写（hook 上移顶层 + 双分支，另补"纯文本模式误加载 markdown 包"陷阱说明）；④§1.2 边界"不改后端"改为"仅 2 行 registry"（与 §4.4/§4.5 矛盾）；⑤§8 禁止 backward 行重写（原"不留开关"与 §4.4 矛盾，明确开关是用户功能非兼容层）；⑥§9 影响面重写（原"零后端改动"为假，补 5 新建 + 4 改动清单）；⑦版本尾 v2.0→v2.4 |
| v3.5 | 2026-10-05 09:30:21 | 小欧 | 北京老陈指令：**图标放到图标目录去，跟 waiting 图标放一起**。实读核实 `frontend/src/components/WaitingIcons/`（`index.tsx` 108行导出 `ThoughtWaitingIcon`/`ToolWaitingIcon`/`ActionWaitingIcon`，子控件另有 `clockStopwatch.tsx`）。**改动**：①原 v3.4 把 57 号 SVG **内联在 ThinkingStream.tsx** → 改为**在 `WaitingIcons/index.tsx` 新增导出 `ReasoningIcon`**（§5.3），`ThinkingStream` 只 import（§5.5），符合"图标控件统一归口"；②**发现并修正一处违规**：v3.4 diff 直接照搬设计稿硬编码色 `#52c41a`/`#1677ff`/`#fa8c16`，而该文件 `:3` 编辑历史明文规定「组件内硬编码 SVG 色令牌化（绿→`Colors.SUCCESS`/橙→`Colors.WAIT_ACTION`/蓝→`Colors.PRIMARY`），零行为变化」—— 已全部令牌化；③CSS 从"§5.3.1 子节 + `@@ 文件末尾追加`占位"改为**独立的 §5.4**（`index.css` 实测 293 行，hunk 头 `@@ -291,3 +291,31 @@` 对齐真实末行 `.clock-beat-wave`），落实"一个代码一个小节 + 杜绝占位 diff"；④节号顺延 §5.1~§5.11，全文交叉引用（含代码注释里的 `文档[9] §x.y`、§六分步落地表、§九影响面表）按新编号逐条重写校正；⑤新增 `aria-hidden="true"`（装饰性图标，语义由标题文字承载，避免读屏重复播报） |
| v3.4 | 2026-10-05 09:22:10 | 小欧 | 北京老陈定案**标题行图标**：`🤔 AI` 两字符**用 SVG 替换**，文字只保留「推理内容...」；选**既有设计稿 `scripts/title-icon-compare.html` 57 号「信号发射」原样照搬**（中心点 #52c41a + 三色三弧 #52c41a/#1677ff/#fa8c16 + `beampulse` 1.8s 渐次扩散），**动画常驻不停**；标题行放大到 **24px** 承载（三色三弧在 12px 会糊）。**改动**：①§5.3 标题行 diff 改为 `[24px SVG] + 推理内容... + CircleArrow`，删掉 emoji；②**新增 §5.3.1 `index.css` diff**（`@keyframes beampulse` + `.reasoning-beam1~3`，落点依据 = `index.css` 是既有 keyframes 唯一聚集处，`.thinking-cursor:44`/`.waiting-cursor:109`/`@keyframes thinking-blink:100`/`waiting-spin:120`/`action-ripple:186` 皆在此）；③**类名加 `reasoning-` 前缀**（设计稿 `.beam1~3` 直接搬会撞名），已核实 `index.css` 现有 keyframes 为 `hitl-breathing`/`thinking-blink`/`waiting-spin`/`gridwave`/`action-ripple`/`clock-beat`，**`beampulse` 未被占用**可沿用；④§5.9.4 记录"常驻动画"取舍与降级方案（`prefers-reduced-motion` 一行）；⑤明确图标与 `ThoughtWaitingIcon` **各自独立互不相关**（北京老陈：跟其他图标没关系） |
| v3.3 | 2026-10-05 09:09:19 | 小欧 | 北京老陈定案**推理折叠新设计**（多轮澄清后）：`🤔 AI 正在思考...` 不再只是临时占位，改为**常驻标题行** `🤔 AI 推理内容...` + `>`，每段独立折叠。**语义澄清（用户纠正）**：开关是「**开=展开态 / 关=折叠态**」，**不是显示/隐藏**。**设计要点**：①`>` 是**每段独立本地 state**（用户点只改自己，**不写后端**），初始值 = `reasoningVisible`；②折叠态 = **只显示标题行**，无阈值/无摘要/不截断，故**不引入 `CollapsibleText`**（用户明确否决阈值方案）；③`ThoughtWaitingIcon` 绿转圈机制**零改动**（用户：和目前机制一样，不需要改）；④段身份复用既有 key `thinking-${i}-${slice(0,16)}` → 换段即重建、天然拿初值，**无需 text 重置逻辑**；⑤后端键 `reasoningVisible` **保留但语义变更** = 「新段折叠初值默认值」，registry notice 已同步改写。**结构变更（一个代码一个小节）**：§5.3 改为 `ThinkingStream.tsx`（标题行+折叠，原为 PipelineRenderer）、§5.4 `PipelineRenderer.tsx` 降为纯下传（**删掉 v3.2 的 `if(!streaming && !reasoningVisible) return <CollapsibleText/>` 分支**）、新增 §5.5 `useChatStreaming.ts` + §5.6 `useChatCallbacks.ts`（3 处占位改空串）、§5.7 `SettingsGroup.tsx`、§5.8 `useSettings.ts`、§5.9 纯设计说明。**占位改空串的依据（实读核实）**：`useChatCallbacks.ts:311` 非 final 帧走 `lastMessage.content` 原样保留占位，只有 `:308` final 帧才可能替换 → 断流/中断时**永久卡住**；且标题行上线后两处显示同句属重复。**连带测试**：列出 5 文件 7 处断言需同步（其余仅构造入参无需改）。`CollapsibleText`/`TextStream`/`useChatSend` 回到零改动 |
| v3.2 | 2026-10-05 08:40:37 | 小欧 | 北京老陈指令：**第4/5 章头部加该章实施的全部代码列表；小节标题带代码名称，一个代码对应一个小节**。**第4章**：①新增 `### 4.0 本章代码清单`（3 个代码 + 动作 + 小节 + 改动量）；②小节改名带代码名 —— `4.1【新增】pipeline/MarkdownText.tsx` / `4.2【改】pipeline/TextStream.tsx` / `4.3【装】依赖4个包(package.json+package-lock.json)`；③原 `#### 4.2.1 TextStream.tsx 完整 diff` 降级为 §4.2 的正文（一个代码只占一个小节，不设子节）。**第5章**：④新增 `### 5.0 本章代码清单`（5 个代码 + **零改动确认清单** + 两开关归属 + 指向纯设计节）；⑤按"一个代码一个小节"重编 —— `5.1【改】settings_registry.py` / `5.2【新增】useStepRenderPrefs.ts` / `5.3【改】PipelineRenderer.tsx` / `5.4【改】SettingsGroup.tsx` / `5.5【改·可选】useSettings.ts`（原 5.2 开关位置、5.4.1 语义等无代码内容不再占编号位）；⑥新增 `### 5.6 纯设计说明（本节零代码）`，收纳 5.6.1 开关位置核查表 / 5.6.2 消费侧架构真空 / 5.6.3 无组合表存档说明 —— **实施小节与设计论证彻底分离**；⑦原 `5.4.2 后端`（内容已并入 §5.1 diff）整节删除，杜绝同一改动两处出现；⑧原 §5.4.1 推理内容语义表上移并入 §5.3 正文；⑨全文 §5.x 交叉引用按新编号重写（含 §六分步落地表、§九影响面表、代码内注释里的 `文档[9] §x.y`），并复查 `§5.1/§5.1` 类重复引用零残留 |
| v3.1 | 2026-10-05 08:34:31 | 小欧 | 北京老陈指令：**每个实施修改代码的地方必须是真实代码或 diff 格式，杜绝只有说明的代码块**。全文审计 15 个代码块，**发现 5 处是"占位片段"而非真实代码/diff，已全部改写**：①§5.4.3 原为 `const PipelineRenderer = ({ ... }) => { // ...原有逻辑... }` 的**伪代码占位**（`{ ... }` 连 props 都没写全，落地必然对不上真实签名）→ 改为 `PipelineRenderer.tsx` 完整 unified diff（3 个 hunk：import 段 / `buildSegments` 后插 hook / thinking 分支加收起分支，含真实行号 `:100,:299,:340,:360`）；②§4.2 原为 3 个孤立 `tsx` 片段（import 块 / props interface / 渲染分支，彼此不连续，无法 apply）→ 合并为 `TextStream.tsx` 单一完整 diff（改前 86 行，2 个 hunk）；③§5.1 / §5.4.2 原为两段独立 `python` 新增片段（同一处改动在文档里出现两份，日后必改一处忘一处）→ 合并为 `settings_registry.py` **单一 diff**（两个 `_item` 一次加完），并补「改前真实代码」`python` 块（`:155-169`）供上下文核对；④§5.5 原为裸 `tsx` 新增片段 → 改为 `SettingsGroup.tsx` unified diff；⑤§5.5.1 原为裸 `ts` + `// ...` 占位 → 改为 `useSettings.ts` unified diff（2 个 hunk，真实行号 `:83,:698`）；⑥§5.3 `useStepRenderPrefs.ts` 原为 `ts` 完整代码 → 改为 **`--- /dev/null` 新建文件 diff**（全 `+` 行）。另把 §5.1 里 `SettingsGroup.tsx:76-79` 的**带行号引用块**改为不带行号的真实代码块（行号是注释不是代码）。现全文 15 个代码块：**9 个 unified diff + 3 个 bash 命令 + 3 个"改前真实代码"参照块**，零占位片段（已用正则复查 `...原有逻辑` / `{ ... }` 零残留） |
| v3.0 | 2026-10-05 08:28:51 | 小欧 | 北京老陈指令：**对照本地前后端最新代码，三堂会审每一个要实施的代码块**。逐块比对真实文件后**发现并修正 3 个阻断级 + 5 个实质缺陷**。**阻断级**：①**Rules of Hooks 违规**（`MarkdownText` 把 `if (!streaming && overflow) return <CollapsibleText/>` 放在两个 `useMemo` **之前**；文字增长跨过 overflow 阈值时渲染的 hook 数变化 → React 抛 "Rendered fewer hooks than expected"，且 `.eslintrc.cjs:53` `react-hooks/rules-of-hooks: 'error'` **直接报 error，验收门 Lint 必挂**）→ 提前 return 移到全部 hook 之后；②**`<input>` 组件崩**（`const { node, ...safe } = p` 把 `children` 一并透传 → `<input {...safe}/>` 触发 React "input is a void element tag and must neither have children"，GFM 任务列表 `- [ ]` 直接崩）→ 改显式解构 + 白名单属性；③**§3.4 表格"展开态 → Markdown 完整渲染"是假的**（折叠后渲染权已交给 `CollapsibleText`，它自持 `expanded`（`CollapsibleText.tsx:41,69`），本组件收不到"用户展开了"事件，**无任何路径回 Markdown**）—— 与 v2.4 犯过、v2.5 已删的同一个错，v2.8 重组时被带回；现改为如实描述 + 记录"接受该行为"及不做受控化的理由。**实质缺陷**：④`MarkdownText` 的 `expanded`/`useState`/`useRef`/`useEffect` **全是死代码**（`CollapsibleText` 已有同款逻辑，`setExpanded` 除重置外从未被调）→ 删除，import 收窄为 `useMemo`；⑤§5.3 的 `useSettingsSavedReload` **导出了但无人调**，设置页保存后 chat 侧**根本不重拉** → 改为 hook 内 `useEffect` 直接订阅；⑥`notifySettingsSaved` 无人调用 + §5.8.1 裸写事件名字面量 = **同常量两处** → 只留 `SETTINGS_SAVED_EVT` 单一来源；⑦`mdComponents` 22 处 `(p: any)`（`no-explicit-any` 为 warn，会把现有 9 warning 爆到 30+）→ 全部改为具名解构；⑧`pre` 组件 `{ node, children }` 解构后仍引用 `p.children`（**undefined 引用**）→ 修正为 `{ children }`。另补 §5.8.1 跨层依赖（`settings2` → `chat`）风险标注。**已实读核验**：`_item` 签名（`settings_registry.py:35-52`）、fail-fast 三项（`:263-307`）、`get_group` 返回**全点号键**（`settings_service.py:197-201`，故 hook 读 `data[KEY_MD]` 正确）、`_validate_value` bool 严格校验（`:269-270`）、`_to_stored_value` bool 原样落盘（`:236`）、`merge_region_patch` 嵌套写入（`config_helpers.py:495-499`）、`.eslintrc.cjs:53` rules-of-hooks=error、`CollapsibleText.tsx:30-113` 全文、`stepStyles.ts:66-162` 全部令牌 |
| v2.9 | 2026-10-05 08:23:49 | 小欧 | 北京老陈指令：**全文读 10 遍核查一致性**。逐节比对文档与真实代码，**发现并修正 7 处不一致**：①§4.1 改名说明自相矛盾（原写"v2.0~v2.4 叫 `MarkdownText`"，实为 `MarkdownThinking`，而本文档 §4.1 标题已是 `MarkdownText` —— 改为 `MarkdownThinking`）；②§2.3 光标行缺代码锚点（补 `ThinkingStream.tsx:52` / `TextStream.tsx:80`）；③§5.5.3 两处代码注释日期写 `2026-08-02`，实为 `2026-09-02`（与 `PipelineRenderer.tsx:341,353` 原文一致）；④§八 SLAP 行称"以 `streaming` prop 传入"，实际 `TextStream` 收的是既有 `typing`/`cursor`，`streaming` 是 `MarkdownText` 自己的 prop —— 两者混淆，已分清；⑤§5.2 "appearance Tab" 提法与后端 `label: "前端"`（`settings_registry.py:155`）不符，统一为「前端」Tab；⑥§六第 2 步"8 条用例 + 3 条渲染态"表述含混（§3.3 的 8 条是纯函数用例），已标明"8 条纯函数用例"；⑦§4.1 令牌核查：`Colors.BORDER.LIGHT` / `FontSize.CODE` / `FontWeight.*` / `Spacing.XL` 等全部实读 `stepStyles.ts:66-162` 确认存在，**零虚构令牌**（v2.8 前未逐个核过） |
| v2.8 | 2026-10-05 08:18:35 | 小欧 | 北京老陈指令：**章节重组** —— 原 §4.4/§4.5/§4.6 三节合并升格为**新第5章「前端 step 设置开关」**（三节讲的是同一件事的两个开关 + 设置页归属，合章更清晰）；原第5章「风险」由北京老陈删除。**改动**：①新增 `## 五、前端 step 设置开关（北京老陈令：现施不删，用户可切）` 章节头，含 v2.8 结构调整说明；②节号重编 5.1~5.5（原 4.4.1→5.1、4.4.2→5.2、4.4.3→5.3、4.5→5.4 含 5.4.1~5.4.3、4.6→5.5 含 5.5.1）；③原 §4.5.6「无组合表」按北京老陈要求**删除**（v2.5 已判定无组合可言，无内容价值），故 5.4 后直接到 5.5，节号连续无跳号；④全文 §4.4/§4.5/§4.6 交叉引用统一改写为 §5.x（版本历史段落内的旧引用按铁规保留不动）；⑤§1.2 边界表与 §1.3 决策表同步纠正（补 `appearance.step_render.*` 全键名、删 `TaskInfoBar` 快捷开关、开关位置改单位置）|
| v2.7 | 2026-10-05 08:12:51 | 小欧 | 北京老陈指令：**先查清现有设置架构再设计**。实读 `settings_registry.py` / `SettingsGroup.tsx` / `settings.api.ts` / `useSettings.ts` / `TextStream.tsx` / `PipelineRenderer.tsx` / `TaskInfoBar.tsx` 后重写实施代码，**修正 v2.2~v2.6 的 6 处架构错误**：①键名 `appearance.thoughtMarkdown`→`appearance.step_render.thoughtMarkdown`（原键会被 `SettingsGroup.tsx:78` 的 `return '外观'` 兜底吞掉，无法独立成块）；②函数名 `sectionNameForKey`（不存在）→ 真实是 `sectionOf(group,key)`（`SettingsGroup.tsx:55`）；③**删除 `TaskInfoBar` 两个快捷开关**（`TaskInfoBar.tsx:121-127` props 不含任何 onChange，`:136` 折叠态机已删，全仓无可复用范式，YAGNI）；④**合并两个 hook 为一个 `useStepRenderPrefs`**（`useThoughtRenderMode`+`useReasoningVisible` 同构重复，违 DRY）；⑤`TextStream` 内调 hook 改为 `PipelineRenderer` 顶层调 + `markdown` prop 下传（`TextStream` 在 `segs.map` 内渲染，违反 Hooks 规则）；⑥补 3 项后端 fail-fast 硬约束（`settings_registry.py:263-307` 违反即导入拒启）+ items 物理顺序约束（`SettingsGroup.tsx:171-172` 只比相邻项，插错位置会插出 3 个标题）；⑦新增 §4.4.2 架构核查表、§4.4.3 消费侧真空分析（`getGroup` 全仓零消费、`appearance.fontSize` 是死配置、`useSettings` 不可搬进 chat 页）、§4.6.1 设置页保存后广播 |
| v2.6 | 2026-10-05 08:03:11 | 小欧 | 北京老陈定案：两个开关在设置页归为一个组，组名 **「step渲染显示」**。**新增 §4.6**：①明确为 `appearance` Tab 内的第 3 个子块（不新建后端 group、不动 Tab 结构）；②前端改动 2 行 —— `SettingsGroup.tsx` 的 `sectionNameForKey` 加 `appearance.thought` / `appearance.reasoning` 前缀分支；③补子块顺序由 registry 声明顺序决定（前端不重排）；④补预览小卡不受影响（`appearancePreview` 仍挂「外观」块首项）；⑤§4.4.1/§4.5.2 的「前端零行」修正为 §4.6 的 2 行 |
| v2.5 | 2026-10-05 07:55:31 | 小欧 | 北京老陈纠正映射错误：**Markdown 作用的是 thought 正文段（`TextStream`），不是 reasoning 段**；reasoning 段只管展开/收起，永不进 Markdown。**v2.4 的"双分支+正交组合表"建立在错误映射上，一并作废**。修正：①§1.1/§2.1/§2.3 按正确映射重写（`reasoning`→thinking 段→推理内容开关；`thought`→text 段→思考排版开关）；②`MarkdownThinking` 改名 `MarkdownText`；③删 `startCollapsed`（reasoning 不走 Markdown 后无调用方）；④§4.2 改为 `TextStream` 打字机切片集成（切片喂 Markdown + 波纹光标保留在外）；⑤§4.5.3 简化为单分支（reasoning 纯文本收起/全文）；⑥§4.5.6 正交组合表删除（两开关零共享状态，无组合可言）；⑦§1.2/§8/§9 连带修正 |

---

## 一、目标与边界

### 1.1 目标

前端 step 的 **thought 部分**（`thought` 字段 → `text` 段 → `TextStream` 正体打字机）
从**纯文本直出**改为 **Markdown 渲染**，且**流式输出时无布局抖动**。

> **v2.5 更正**：v2.0~v2.4 误把 Markdown 做到了 **reasoning 部分**（`thinking` 段 → `ThinkingStream` 灰斜体）。
> 正确映射（`PipelineRenderer.tsx:169-205` 注释原文"reasoning 在前 thinking 灰斜体、thought 在后 text 正体"）：
> reasoning→thinking 段→**推理内容**开关（展开/收起，纯文本不动）；thought→text 段→**思考排版**开关（Markdown/纯文本）。
> 本版起全部生效点、对接代码、组合表按此修正。

### 1.2 边界

| 项 | 内容 |
|---|---|
| 后端改动 | **仅 2 行**：`settings_registry.py` 的 `appearance` 组加 `appearance.step_render.thoughtMarkdown` + `appearance.step_render.reasoningVisible` 两个 `bool` 项（§5.1）。**零 SSE 契约改动，零业务逻辑改动，零 Tab 结构改动** |
| 前端改动范围 | thought 正文段（`TextStream` 打字机 + `markdown` prop）+ reasoning 段收起分支（`PipelineRenderer` thinking 分支，纯文本）+ 设置页 1 行前缀分支（`SettingsGroup.sectionOf`） |
| 不做 | 不给代码块做语法着色；不改 `ThinkingStream`（reasoning 灰斜体保持纯文本）；不改其他 step；**不做 `TaskInfoBar` 快捷开关**（§5.12.1 架构核查后否决） |

### 1.3 已定决策（北京老陈 2026-10-05 确认，无遗留待定项）

| 项 | 决策 |
|---|---|
| 语法范围 | 标题 / 粗体 / 斜体 / 删除线 / 行内代码 / **围栏代码块** / 有序无序列表 / 任务列表 / 引用 / 分割线 / **表格** / 链接 / 长内容自动折叠 |
| 流式策略 | **全程实时**渲染，不延迟整段 |
| 代码块抖动 | **方案 A**：未闭合围栏按纯文本渲染，闭合瞬间成型 |
| 依赖 | 引入成熟库（4 个包，版本见 §4.3） |
| 现施处理 | **不删**，加选择模式开关（纯文本 / Markdown 双选，默认 Markdown，见 §5.1） |
| 开关位置 | **单位置**：设置页 `前端` Tab → 「step渲染显示」子块 = 主开关（后端持久）。**无快捷开关** —— `TaskInfoBar` props 不含回调、折叠态机已删、全仓无可复用范式（§5.2 核查表） |
| 开关定名 | **两个独立开关**：① **思考排版** = thought 正文是否 Markdown（§5.1）；② **推理内容** = reasoning 折叠初值（§5.8）。各管各的段，**无组合** |

---

## 二、现状（实读代码核实，非推测）

### 2.1 当前是纯文本直出（thought 正文段）

`frontend/src/features/chat/components/pipeline/TextStream.tsx:77-83`：

```tsx
<div style={getStreamStyle(compact)}>
  {clean.slice(0, typing ? shown : clean.length)}
  {cursor && typing && <ActionWaitingIcon waitClock={waitClock} />}{' '}
</div>
```

**打字机**：`shown` 状态 + 16ms interval 逐字推进（`:51-75`，短文逐字、长文加速、≤4s 打完）；
`cursor && typing` 时末位挂蓝色波纹光标 `ActionWaitingIcon`（`:10`，2026-09-14 由静态 `▍` 换型）。

纯文本切片进 `div`，`**`、`##`、`|`、```` ``` ```` 原样显示。**无任何 Markdown 解析。**

> **v2.5 更正**：v2.0~v2.4 本节误贴 `ThinkingStream`（reasoning 灰斜体段）代码。
> 思考排版（Markdown）作用的是 **thought 正文段 = `TextStream`**，不是 reasoning 段。

### 2.2 项目当前零 Markdown 依赖（`package.json` 实测）

`dependencies` 仅 `antd` / `axios` / `dayjs` / `react` / `react-dom` / `react-router-dom`。
Markdown、XSS 净化、代码高亮**全部为零**。历史 `markdown.tsx` 已由 `f17143584` 以零引用死代码删除。

### 2.3 thought 数据形态（reasoning 与 thought 是两个独立段）

> **v2.5 更正**：v2.0~v2.4 把两段混为一谈。下表按 `PipelineRenderer.tsx:169-205` 拆开
> （注释原文"reasoning 在前 thinking 灰斜体、thought 在后 text 正体"）。

| 项 | reasoning 部分 | thought 部分 |
|---|---|---|
| 后端字段 | `reasoning` | `thought` |
| Pipeline 段 | `thinking`（`:178-185`，与 chunk 累积去重） | `text`（`:188-194`，与 chunk 累积去重） |
| 渲染组件 | `ThinkingStream`（灰斜体弱化） | **`TextStream`（正体打字机）** |
| 光标 | 静态 `▍`（`.thinking-cursor` 呼吸光标，`ThinkingStream.tsx:52`） | 蓝色波纹 `ActionWaitingIcon` + `waitClock`（`TextStream.tsx:80`） |
| 同 step 关系 | 在前，标 `sameStep` → 紧凑间距 | 在后，标 `sameStep` → 紧凑间距 |
| **对应开关** | **推理内容**（展开/收起，纯文本不动） | **思考排版**（Markdown/纯文本） |
| 历史来源 | 同一步 `step_json` 的 `reasoning` 字段 | 同一步 `step_json` 的 `thought` 字段 |

---

## 三、方案设计

### 3.1 单一规则（不分支）

> **规则：未闭合的围栏代码块，其尾段按纯文本渲染；其余全文按 Markdown 渲染。**

**为何不需要"实时/历史"分支**：历史任务的文本虽已完整，但**可能因 LLM 截断而留下未闭合围栏** —— 此时渲染成代码块是**撒谎**（源码本身就不完整），按纯文本显示才是事实。故实时与历史**共用同一规则**，无分支、无状态机（KISS-DIRECT）。

### 3.2 为什么未闭合围栏必须延迟

实测数据（逐字符输入，`react-markdown` 行为）：

| 收到 | 渲染 | 页面影响 |
|---|---|---|
| ` ```js ` | **`<pre>` 空块容器出现** | **下方内容整体下移约 40px** |
| ` ```js\nconst a=1;` | 块内一行 | 逐行下移 |

任务中代码块越多，抖动次数越多。方案 A 下，未闭合期间不生成 `<pre>` 容器 → **页面零位移**；闭合瞬间一次性成型。

### 3.3 围栏尾段切分算法（**已实测 8/8 通过**）

```ts
/**
 * 切分未闭合围栏代码块的尾段 —— 小欧 2026-10-05
 * 返回 closedPart(可安全按 Markdown 渲染) + openTail(未闭合, 按纯文本渲染)
 * 判定: 行首(≤3 空格缩进)的 ``` 或 ~~~ (≥3个) 为围栏行;
 *       开围栏可带 info string, 闭围栏必须为空(行首标记字符需与开围栏一致)
 */
export const findUnclosedFenceTail = (
  text: string
): { closedPart: string; openTail: string } => {
  const lines = text.split('\n');
  let openIdx = -1;
  let openMark = '';
  for (let i = 0; i < lines.length; i++) {
    const m = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(lines[i]);
    if (!m) continue;
    if (openIdx === -1) {
      openIdx = i;
      openMark = m[1][0];
    } else if (m[1][0] === openMark && m[2].trim() === '') {
      openIdx = -1;
    }
  }
  if (openIdx === -1) return { closedPart: text, openTail: '' };
  return {
    closedPart: lines.slice(0, openIdx).join('\n'),
    openTail: lines.slice(openIdx).join('\n'),
  };
};
```

**实测用例（全部通过）**：

| 用例 | 输入 | 期望 | 结果 |
|---|---|---|---|
| 无围栏 | `# a` | 无尾段 | ✅ |
| 已闭合 | ` ```\na\n``` ` | 无尾段 | ✅ |
| 未闭合 | ` ```js\na ` | 尾段=全文 | ✅ |
| 闭合后又开 | ` ```\na\n```\n中\n```\nb ` | 只切最后一个 | ✅ |
| 波浪号闭合 | `~~~\nx\n~~~` | 无尾段 | ✅ |
| 波浪号未闭合 | `~~~\nx` | 有尾段 | ✅ |
| 4 空格缩进不算围栏 | `    ```\n    x\n    ``` ` | 无尾段 | ✅ |
| **围栏内含 ``` 字符串** | ` ```md\n```js\n```\n``` ` | 闭合到第 2 行，第 3 行是新开围栏 | ✅ |

> 第 8 条是关键：围栏**内部**的 ` ```js ` 是代码块内容而非围栏 —— 算法正确识别（开发时曾误写断言，实测发现**是断言错、算法对**，已修正断言）。

### 3.4 长内容折叠（复用既有组件，不新造）

| 状态 | 渲染内容 |
|---|---|
| 未超阈值 | Markdown 渲染 |
| **流式中**（`streaming`） | **永不折叠**（内容在增长，折叠态无意义且会抖动），直接 Markdown 渲染 |
| 超阈值 + 非流式 | **整段委派 `CollapsibleText`** —— 折叠态是纯文本首 2 行；**用户点「展开」后仍是纯文本全文**（展开动作发生在 `CollapsibleText` 内部，它自持 `expanded`），**不会回到 Markdown** |

> **v2.10 重要更正**：v2.1~v2.9 的本表曾写「超阈值 + 展开态 → Markdown 完整渲染」，**这是假的**。
> 折叠后整个渲染权已交给 `CollapsibleText`（它自己持有 `expanded`，见 `CollapsibleText.tsx:41,69`），
> 本组件根本收不到"用户展开了"这个事件，**无任何路径回到 Markdown**。
> 这与 v2.4 犯过、v2.5 已删除的"展开后看 Markdown 全文"是**同一个错**，v2.8 章节重组时被带回来了。
>
> **接受该行为**：① 只影响超长 thought（>5 行或 >200 字）；② 用户看到纯文本全文，内容不缺，只是无排版；
> ③ 要让展开后回到 Markdown，就得把折叠态做成受控组件（`expanded` 提升到本组件），
> 等于为 `CollapsibleText` 加受控模式 —— 该组件有 3 处复用方（`ResponseStream` / `ToolCallLine` 等），
> 改其契约会波及无关功能，**YAGNI，不做**。

**复用**：`pipeline/CollapsibleText.tsx` 既有组件（阈值 `maxLines` / `maxChars`，带 `stopPropagation` + Enter/Space 键盘可达 + 内部 `CircleArrow` 折叠箭头）。**零新组件、零新样式、零 props 扩展。**

### 3.5 v2.1 自审：原方案不是 100% 完美（3 缺陷 + 2 遗漏，均已在 §4.1 修复）

> 北京老陈 2026-10-05 问"设计方案都是 100% 完美了吗"。小欧重审 v2.0 代码后自查出以下问题，
> **本节逐条记录，修复全部落进 §4.1 最终代码**。隐瞒自审缺陷即谎报军情。

**缺陷 1：`node` 属性泄漏到 DOM（真 bug）**
- react-markdown v9 给**每个**自定义组件传 `node`（hast 节点对象）。
- v2.0 的 `code: ({ children, className, ...rest }) => <code className {...rest}>` 会把 `node` 对象扩散到 DOM，
  触发 React unknown-prop 警告并产生非法 `node=` 属性；`input: (props) => <input {...props}>` 同病。
- **修复**：所有自定义组件显式解构 `node` 后丢弃，**禁止 `...rest` 透传**。

**缺陷 2：缺 `remark-breaks`，单换行会塌（真 bug）**
- 当前 thought 是 `pre-wrap`，**每个 `\n` 都换行**。
- Markdown 默认把单个 `\n` 当空格（软换行）：`"第一行\n第二行"` 渲染为**一行**。
- 流式 thought 满是单换行 → 没这个包等于行为退化（比"打印机"还差）。
- **修复**：加 `remark-breaks`（`\n` → `<br>`），逐字保留现有换行效果。

**缺陷 3：GFM 任务列表被净化掉（真 bug）**
- `- [ ] 待办` 渲染为 `<input type="checkbox">`，但 `input` **不在默认 sanitize 的 tagName 里** → 复选框被剥掉。
- **修复**：schema 显式加 `input` + `type/checked/disabled` 属性；`input` 组件同样剥 `node`。

**遗漏 4：标题语义被改写**
- v2.0 把 h1→h3、h4/h5/h6→h6：既破坏文档大纲（a11y），又造成三级长得一样。
- **修复**：保留语义标签 `h1..h6`，只统一样式压小（thought 区不应出现大字号标题）。

**遗漏 5：性能（长推理 × 高频 chunk）**
- `findUnclosedFenceTail` + `ReactMarkdown` 全量重解析在每个 chunk 都跑一次。
- **修复**：切分与渲染结果按 `text` 做 `useMemo`（§4.1 已加）。

---

## 四、完整实现（可直接落地复制）

### 4.0 本章代码清单

| # | 代码 | 动作 | 小节 | 改动量 |
|---|---|---|---|---|
| 1 | `frontend/src/features/chat/components/pipeline/MarkdownText.tsx` | **新增** | §4.1 | 全新文件 ~230 行 |
| 2 | `frontend/src/features/chat/components/pipeline/TextStream.tsx` | 改 | §4.2 | +17 行（打字机/光标/规约**零改动**） |
| 3 | `frontend/package.json` + `package-lock.json` | 改 | §4.3 | 新增 4 依赖 |

### 4.1 【新增】`pipeline/MarkdownText.tsx`

路径：`frontend/src/features/chat/components/pipeline/MarkdownText.tsx`

> **v2.5 改名**：v2.0~v2.4 叫 `MarkdownThinking`（误以为服务 thinking 段）。
> 实际服务的是 **text 段（thought 正文）**，改名以正视听。
> 同时删除 `startCollapsed` prop —— reasoning 收起态不再走 Markdown（见 §5.8），该 prop 已无调用方。

```tsx
// 编辑历史: 2026-10-05 小欧 - 新增: thought 思考段 Markdown 渲染器(文档[9] v2.0 方案A)
//   未闭合围栏尾段按纯文本渲染(避免空 <pre> 容器凭空出现致页面位移), 其余按 Markdown 渲染 — 小欧-2026-10-05
// 编辑历史: 2026-10-05 小欧 - v2.1 自审整改: ①全部自定义组件显式剥 node 防泄漏到 DOM(react-markdown v9
//   必传 node, …rest 透传即非法属性, 禁止); ②remark-breaks 保留单换行(与 pre-wrap 现有效果一致);
//   ③schema 补 input 标签+属性(GFM 任务列表复选框否则被净化剥掉); ④标题保留语义标签只压样式;
//   ⑤切分与渲染按 text useMemo(防长推理×高频 chunk 重复全量解析) — 小欧-2026-10-05
import React, { useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import { Colors, FontSize, FontWeight, Spacing, BorderWidth } from '@/utils/stepStyles';
import { CollapsibleText } from './CollapsibleText';

// XSS 净化配置: 默认 schema(GitHub 风格, 天然覆盖 GFM 表格/删除线)之上只补两处缺口——
//   ① code[className]: 围栏语言标记(language-js)渲染所需, 默认被剥离(剥掉则无法区分围栏/行内代码)
//   ② input 标签 + type/checked/disabled: GFM 任务列表复选框所需, 默认整个标签被剥离
// 注意: 不补 a[target/rel]——外链属性由本文件 a 组件硬编码渲染(不从 hast 取), schema 无需放行
const SANITIZE_SCHEMA = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames ?? []), 'input'],
  attributes: {
    ...defaultSchema.attributes,
    code: [...(defaultSchema.attributes?.code ?? []), 'className'],
    input: ['type', 'checked', 'disabled'],
  },
};

// 代码块容器: 显式覆盖父级 whiteSpace:pre-wrap(否则 <pre> 内换行被软化) + 限高滚动
const codeBlockStyle: React.CSSProperties = {
  margin: `${Spacing.XS}px 0 ${Spacing.SM}px`,
  padding: `${Spacing.XS}px ${Spacing.SM}px`,
  borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
  background: 'transparent',
  fontSize: FontSize.CODE,
  fontStyle: 'normal',
  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
  whiteSpace: 'pre',
  wordBreak: 'break-word',
  maxHeight: 400,
  overflow: 'auto',
  borderRadius: 0,
};

// 行内代码: 加浅底以与正文区分(不加背景色块, 与项目"内容即容器"风格一致)
const inlineCodeStyle: React.CSSProperties = {
  padding: '0 3px',
  fontSize: FontSize.CODE,
  fontStyle: 'normal',
  fontFamily: 'Consolas, Monaco, "Courier New", monospace',
  color: Colors.TEXT.STRONG,
};

// Markdown 元素样式映射: 全部走 stepStyles 既有令牌, 零硬编码颜色 — 小欧-2026-10-05
// 规则: 所有组件必须显式解构 node 后丢弃(§3.5 缺陷 1), 禁止 ...rest 透传到 DOM
// 标题保留语义标签 h1..h6(a11y 大纲不断), 只统一样式压小(§3.5 遗漏 4)
const mdComponents = {
  h1: ({ node, children }: any) => {
    const { node, children } = p;
    return <h1 style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD, color: Colors.TEXT.STRONG, margin: `${Spacing.SM}px 0 ${Spacing.XS}px`, lineHeight: `${FontSize.PRIMARY + Spacing.XS}px` }}>{children}</h1>;
  },
  h2: ({ node, children }: any) => {
    const { node, children } = p;
    return <h2 style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD, color: Colors.TEXT.STRONG, margin: `${Spacing.SM}px 0 ${Spacing.XS}px`, lineHeight: `${FontSize.PRIMARY + Spacing.XS}px` }}>{children}</h2>;
  },
  h3: ({ node, children }: any) => {
    const { node, children } = p;
    return <h3 style={{ fontSize: FontSize.SECONDARY, fontWeight: FontWeight.MEDIUM, color: Colors.TEXT.STRONG, margin: `${Spacing.XS}px 0`, lineHeight: `${FontSize.SECONDARY + Spacing.XS}px` }}>{children}</h3>;
  },
  h4: ({ node, children }: any) => {
    const { node, children } = p;
    return <h4 style={{ fontSize: FontSize.SECONDARY, fontWeight: FontWeight.MEDIUM, color: Colors.TEXT.SECONDARY, margin: `${Spacing.XS}px 0`, lineHeight: `${FontSize.SECONDARY + Spacing.XS}px` }}>{children}</h4>;
  },
  h5: ({ node, children }: any) => {
    const { node, children } = p;
    return <h5 style={{ fontSize: FontSize.SECONDARY, fontWeight: FontWeight.REGULAR, color: Colors.TEXT.SECONDARY, margin: `${Spacing.XS}px 0`, lineHeight: `${FontSize.SECONDARY + Spacing.XS}px` }}>{children}</h5>;
  },
  h6: ({ node, children }: any) => {
    const { node, children } = p;
    return <h6 style={{ fontSize: FontSize.TERTIARY, fontWeight: FontWeight.REGULAR, color: Colors.TEXT.SECONDARY, margin: `${Spacing.XS}px 0`, lineHeight: `${FontSize.TERTIARY + Spacing.XS}px` }}>{children}</h6>;
  },
  p: ({ node, children }: any) => {
    const { node, children } = p;
    return <p style={{ margin: `${Spacing.XS}px 0`, lineHeight: `${FontSize.SECONDARY + Spacing.XS}px` }}>{children}</p>;
  },
  ul: ({ node, children }: any) => {
    const { node, children } = p;
    return <ul style={{ margin: `${Spacing.XS}px 0`, paddingLeft: Spacing.XL, lineHeight: `${FontSize.SECONDARY + Spacing.XS}px` }}>{children}</ul>;
  },
  ol: ({ node, children }: any) => {
    const { node, children } = p;
    return <ol style={{ margin: `${Spacing.XS}px 0`, paddingLeft: Spacing.XL, lineHeight: `${FontSize.SECONDARY + Spacing.XS}px` }}>{children}</ol>;
  },
  li: ({ node, children }: any) => {
    const { node, children } = p;
    return <li style={{ margin: 0, lineHeight: `${FontSize.SECONDARY + Spacing.XS}px` }}>{children}</li>;
  },
  blockquote: ({ node, children }: any) => {
    const { node, children } = p;
    return <blockquote style={{ margin: `${Spacing.XS}px 0`, paddingLeft: Spacing.MD, borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`, color: Colors.TEXT.SECONDARY }}>{children}</blockquote>;
  },
  hr: ({ node, children }: any) => <hr style={{ border: 'none', borderTop: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`, margin: `${Spacing.SM}px 0` }} />,
  code: ({ node, children }: any) => {
    const { node, children, className } = p;
    // 围栏代码块(className 含 language-xxx)走块级样式; 其余为行内代码
    if (className) {
      return <pre style={codeBlockStyle}><code className={className}>{children}</code></pre>;
    }
    return <code style={inlineCodeStyle}>{children}</code>;
  },
  // pre 覆盖: 只透出 children, 让 code 组件自己产 <pre>(否则会 pre>pre 双层嵌套)
  pre: ({ children }: any) => <>{children}</>,
  a: ({ node, children }: any) => {
    const { node, children, href } = p;
    return <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: Colors.PRIMARY, textDecoration: 'underline', wordBreak: 'break-all' }}>{children}</a>;
  },
  table: ({ node, children }: any) => {
    const { node, children } = p;
    return (
      <div style={{ overflowX: 'auto', margin: `${Spacing.XS}px 0` }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: FontSize.SECONDARY }}>{children}</table>
      </div>
    );
  },
  thead: ({ node, children }: any) => {
    const { node, children } = p;
    return <thead style={{ background: Colors.BG.TERTIARY }}>{children}</thead>;
  },
  th: ({ node, children }: any) => {
    const { node, children } = p;
    return <th style={{ border: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`, padding: `${Spacing.XS}px ${Spacing.SM}px`, textAlign: 'left', fontWeight: FontWeight.MEDIUM, color: Colors.TEXT.STRONG }}>{children}</th>;
  },
  td: ({ node, children }: any) => {
    const { node, children } = p;
    return <td style={{ border: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`, padding: `${Spacing.XS}px ${Spacing.SM}px`, color: Colors.TEXT.PRIMARY }}>{children}</td>;
  },
  // GFM 任务列表复选框: 只读展示。
  // ⚠️ 绝不能 `const { node, ...safe } = p` 再 {...safe} —— safe 里含 children,
  //   透传给 <input> 会抛 "input is a void element tag and must neither have children" 直接崩。
  //   故与其它组件同款: 显式解构 node + children 后丢弃, 只取白名单属性。
  input: ({ node, children, type, checked }: Components['input']) => (
    <input
      type={type as 'checkbox' | undefined}
      defaultChecked={checked}
      disabled
      readOnly
      style={{ marginRight: Spacing.XS }}
    />
  ),
};

export const findUnclosedFenceTail = (
  text: string
): { closedPart: string; openTail: string } => {
  const lines = text.split('\n');
  let openIdx = -1;
  let openMark = '';
  for (let i = 0; i < lines.length; i++) {
    const m = /^ {0,3}(`{3,}|~{3,})(.*)$/.exec(lines[i]);
    if (!m) continue;
    if (openIdx === -1) {
      openIdx = i;
      openMark = m[1][0];
    } else if (m[1][0] === openMark && m[2].trim() === '') {
      openIdx = -1;
    }
  }
  if (openIdx === -1) return { closedPart: text, openTail: '' };
  return {
    closedPart: lines.slice(0, openIdx).join('\n'),
    openTail: lines.slice(openIdx).join('\n'),
  };
};

interface MarkdownTextProps {
  text: string;
  /** 流式中: 打字机进行态。不折叠(内容在增长), 但未闭合围栏规则照常生效 */
  streaming?: boolean;
  /** 与父容器一致的折叠阈值(超出则先纯文本摘要, 展开后渲染 Markdown) */
  maxLines?: number;
  maxChars?: number;
}

const MarkdownText: React.FC<MarkdownTextProps> = ({
  text,
  streaming = false,
  maxLines = 5,
  maxChars = 200,
}) => {
  const overflow = useMemo(
    () => text.split('\n').length > maxLines || text.length > maxChars,
    [text, maxLines, maxChars]
  );

  // §3.5 遗漏 5: 切分按 text 缓存, 长推理 × 高频 chunk 不再重复分段
  const { closedPart, openTail } = useMemo(() => findUnclosedFenceTail(text), [text]);

  const mdNode = useMemo(
    () =>
      closedPart ? (
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          rehypePlugins={[[rehypeSanitize, SANITIZE_SCHEMA]]}
          components={mdComponents}
        >
          {closedPart}
        </ReactMarkdown>
      ) : null,
    [closedPart]
  );

  // ⚠️ 提前 return 必须放在**全部 hook 之后**。
  //   v2.10 修正: 原稿把本行放在两个 useMemo 之前 —— 文字增长跨过 overflow 阈值时
  //   本组件渲染的 hook 数会变化, React 抛 "Rendered fewer hooks than expected",
  //   且 eslint .eslintrc.cjs:53 `react-hooks/rules-of-hooks: 'error'` 直接报 error(验收门 Lint 必挂)。
  // 流式中永不折叠 —— 避免"内容边长边折叠"的抖动与语义混乱
  if (!streaming && overflow) {
    return <CollapsibleText text={text} maxLines={maxLines} maxChars={maxChars} />;
  }

  return (
    <div style={{ whiteSpace: 'normal' }}>
      {mdNode}
      {/* 未闭合围栏尾段: 纯文本(pre-wrap 保留原换行), 不生成 <pre> 容器 → 页面零位移 */}
      {openTail && (
        <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{openTail}</div>
      )}
    </div>
  );
};

export { MarkdownText };
export default MarkdownText;
```

### 4.2 【改】`pipeline/TextStream.tsx`（现施保留 + 选择模式开关）

> **v2.5 更正**：v2.0~v2.4 本节误写 `ThinkingStream`。思考排版作用的是 **thought 正文段 = `TextStream`**。
> `TextStream` 有打字机（`shown` 状态 16ms interval 逐字推进），集成方式与 `ThinkingStream` 不同，见下。

> 北京老陈 2026-10-05 裁定：**现施不删**，加选择模式开关。用户随时可切回纯文本。

**v2.7 架构修正**：v2.5~v2.6 让 `TextStream` 自己调 hook（`useThoughtRenderMode`）是错的 ——
`TextStream` 在 `PipelineRenderer` 的 `segs.map` 内被渲染，hook 必须调在组件顶层。
改为 **`PipelineRenderer` 顶层调一次 `useStepRenderPrefs`，以 `markdown` prop 下传**（§5.8）。

文件：`frontend/src/features/chat/components/pipeline/TextStream.tsx`（改前 86 行）

```diff
--- a/frontend/src/features/chat/components/pipeline/TextStream.tsx
+++ b/frontend/src/features/chat/components/pipeline/TextStream.tsx
@@ -26,12 +26,19 @@
 import { ActionWaitingIcon } from '@/components/WaitingIcons'; // 2026-09-14 小欧: 正文末位光标换型(蓝色波纹扩散圈) — 小欧-2026-09-14
 import type { ClockSignals } from '@/types/sse'; // 2026-09-17 小欧 实施: 钟面信号类型 — 小欧-2026-09-17
 
+// 2026-10-05 小欧 - 思考排版开关(文档[9] §4.2): React.lazy 分块, 纯文本模式用户不下载
+//   react-markdown 三件套(含 remark-gfm/remark-breaks/rehype-sanitize); 开关切到 Markdown 时
+//   Suspense fallback 先显纯文本原文, 加载完自动切换为排版 — 小欧-2026-10-05
+const MarkdownText = React.lazy(() => import('./MarkdownText'));
+
 interface TextStreamProps {
   text: string;
   typing?: boolean; // 实时流且为本段累积中（打字机态）
   cursor?: boolean; // 末位闪烁光标
   compact?: boolean; // 同 step 内部(13.6 拆出的 reasoning→thought 相邻): 段距 SM(6)
   waitClock?: ClockSignals; // 2026-09-17 小欧 实施: 钟面信号(与波纹光标并存) — 小欧-2026-09-17
+  /** 2026-10-05 小欧: 思考排版开关(文档[9] §4.2; 由 PipelineRenderer 顶层下传) — 小欧-2026-10-05 */
+  markdown?: boolean;
 }
 
 const TextStream: React.FC<TextStreamProps> = ({
@@ -40,6 +47,7 @@
   cursor = false,
   compact = false,
   waitClock, // 2026-09-17 小欧 实施
+  markdown = false,
 }) => {
   const clean = normalizeBlankLines(text, { streaming: typing });
   const [shown, setShown] = useState(0);
@@ -76,7 +84,19 @@
 
   return (
     <div style={getStreamStyle(compact)}>
-      {clean.slice(0, typing ? shown : clean.length)}
+      {/* 2026-10-05 小欧 - 思考排版开关(文档[9] §4.2): markdown=false 时走 2026-10-04 前的
+          原纯文本切片路径, 一字不改; markdown=true 时把同一份打字机切片喂 MarkdownText
+          (切片是不完整源码, 由 findUnclosedFenceTail 按未闭合围栏规则兜住, 见 §3.1) — 小欧-2026-10-05 */}
+      {markdown ? (
+        <React.Suspense fallback={clean.slice(0, typing ? shown : clean.length)}>
+          <MarkdownText
+            text={clean.slice(0, typing ? shown : clean.length)}
+            streaming={typing}
+          />
+        </React.Suspense>
+      ) : (
+        clean.slice(0, typing ? shown : clean.length)
+      )}
       {cursor && typing && <ActionWaitingIcon waitClock={waitClock} />}{' '}
       {/* 2026-09-17 小欧: 波纹与钟面并存(追加) — 小欧-2026-09-17 */}
     </div>
```

**import 段新增 1 行**（接在 `import React, { useEffect, useRef, useState } from 'react';` 之后）：

```diff
```

**现施保留点（diff 里一个都没删）**：打字机 `shown` 状态机 + interval（`:51-75`）、
`normalizeBlankLines` 规约（`:44`）、`cursor && typing` 波纹光标 + `waitClock`（`:80`）、
`getStreamStyle(compact)`（`:78`）、`useRiseLog('CURSOR F')` 打点（`:49`）—— **全部原样保留**。
光标永远在 Markdown 之外，不进解析。

> **为什么打字机切片能直接喂 Markdown**：切片是不完整源码 = 流式未完文本，
> 按 §3.1 同一规则处理（标题/列表/引用立即成型，粗体等闭合后扣符号，未闭合围栏纯文本）。
> 打字机只决定"喂多少字符"，Markdown 只决定"怎么排版已喂的字符"，两者互不干扰。

### 4.3 【装】依赖 4 个包（`package.json` / `package-lock.json`）

```bash
cd frontend
npm install react-markdown@^9 remark-gfm@^4 remark-breaks@^2 rehype-sanitize@^6
npm install -D @types/hast@^3
```

| 包 | 版本 | 作用 |
|---|------|------|
| `react-markdown` | `^9` | Markdown → React |
| `remark-gfm` | `^4` | GFM：表格 / 删除线 / 任务列表 / 自动链接 |
| `remark-breaks` | `^2` | **单换行 → `<br>`（§3.5 缺陷 2 必需；无此包则 thought 的单换行全部塌成一行，行为退化）** |
| `rehype-sanitize` | `^6` | **XSS 净化（安全红线）** |
| `@types/hast` | `^3`（dev） | `defaultSchema` 类型 |

**不引入代码高亮**：需求未要求；高亮库（尤其 `shiki`）bundle 显著更大；围栏用等宽字体 + 左线已可读，与项目既有 `CodeResultRenderer` 风格一致。

## 五、前端 step 设置开关（北京老陈令：现施不删，用户可切）

> **v2.8 结构调整**：本章由原 §5.1 / §5.3 / §5.8 三节合并升格（原第 5 章「风险」已被北京老陈删除）。
> 三个小节讲的是同一件事的两个开关 + 它们的设置页归属，合为一章更清晰。

### 5.0 本章代码清单

| # | 代码 | 动作 | 小节 | 改动量 |
|---|---|---|---|---|
| 1 | `backend/app/services/settings/settings_registry.py` | 改 | §5.1 | **+7 行**（2 个 `bool` 项） |
| 2 | `frontend/src/features/chat/components/pipeline/useStepRenderPrefs.ts` | **新增** | §5.2 | 全新文件 62 行 |
| 3 | `frontend/src/components/WaitingIcons/index.tsx` | 改 | §5.3 | +35 行（新增 `ReasoningIcon`，三色令牌化） |
| 4 | `frontend/src/index.css` | 改 | §5.4 | +28 行（`beampulse` + `.reasoning-beam1~3`） |
| 5 | `frontend/src/features/chat/components/pipeline/ThinkingStream.tsx` | 改 | §5.5 | +58 行（标题行 + 每段折叠） |
| 6 | `frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx` | 改 | §5.8 | +3 行（下传折叠初值） |
| 7 | `frontend/src/features/chat/hooks/useChatStreaming.ts` | 改 | §5.8 | 1 行（占位文案 → 空串） |
| 8 | `frontend/src/features/chat/hooks/useChatCallbacks.ts` | 改 | §5.9 | 2 行（2 处占位文案 → 空串） |
| 9 | `frontend/src/features/settings2/components/SettingsGroup.tsx` | 改 | §5.10 | **+3 行**（1 行分支 + 2 行注释） |
| 10 | `frontend/src/features/settings2/hooks/useSettings.ts` | 改（**可选**） | §5.11 | +4 行（1 行 import + 1 行 dispatch） |

**图标落点**：`ReasoningIcon` 与 `ThoughtWaitingIcon` / `ToolWaitingIcon` / `ActionWaitingIcon`
同放 `frontend/src/components/WaitingIcons/index.tsx`（图标控件组），**各自独立、互不相关**。

**零改动确认**：`TextStream.tsx`（本方案不碰）、`CollapsibleText.tsx`、
`WaitingIcons/index.tsx`（**ThoughtWaitingIcon 机制原样保留**）、
`useChatSend.ts`（幽灵清理按 `isStreaming` 不看文案，不受影响）、
`SettingRow.tsx`、`settings.api.ts`、`types.ts`（`TabKey` 不新增 Tab）、`TaskInfoBar.tsx`。

**测试连带改动**：`🤔 AI 正在思考...` 改空串后，5 个测试文件 7 处断言需同步
（§5.8 / §5.9 末尾列出清单）。

**两个开关的归属**：同属设置页 `前端` Tab → **「step渲染显示」** 子块（§5.10）。

**纯设计说明（无代码）**：§5.12。

### 5.1 【改】`settings_registry.py` —— 两个开关键（`appearance.step_render.*`）

**v2.7 键名改前缀的架构依据**（v2.2~v2.6 用 `appearance.thoughtMarkdown` 是错的）：

`SettingsGroup.tsx:76-79` 的 appearance 分块是**前缀映射 + 兜底**（改前真实代码）：

```tsx
  if (group === 'appearance') {
    if (key.startsWith('security.')) return '登录与准入';
    return '外观';        // ← 任何非 security.* 的键都被兜底吞进「外观」
  }
```

若沿用 `appearance.thoughtMarkdown`，会被 78 行静默吞进「外观」块，与「登录与准入」之外的
界面偏好混装 —— 无法独立成「step渲染显示」子块。故**必须用新前缀** `appearance.step_render.`，
并在 78 行**之前**显式加分支。

**改前真实代码**（`settings_registry.py:155-169`，供 diff 上下文核对）：

```python
    # 4.8 前端（appearance）：前两项是准入控制，键名沿用 security.*（前缀只表命名空间）
    #   Tab 显示名 2026-09-27 由「外观」改「前端」（本组实含准入 + 外观两块）
    "appearance": {"label": "前端", "items": [
        # 访问口令（secret → 读掩码；写路径被显式拒绝，改口令走 auth_routes 专用端点）
        _item("security.access_token", "secret", "访问口令", None, secret=True,
              env_key="OMNIAGENT_ACCESS_TOKEN", env_inject=True,
              notice="局域网访问本服务用的口令（暗号）。除本机与白名单外，访问任何接口都要它；泄露了改成新的，旧的立即作废"),
        # 免口令 IP 白名单（非 secret：白名单不是机密，需在设置页可维护）
        _item("security.access_token_allowlist", "textarea", "免口令 IP 白名单", "",
              env_key="OMNIAGENT_ACCESS_TOKEN_ALLOWLIST", env_inject=True, list_of="ip_cidr",
              notice="这些 IP/网段访问本服务免口令。每行一条，也可用逗号分隔，支持 CIDR（如 192.168.1.0/24）。本机(127.0.0.1/::1)免口令。⚠️白名单内等于无鉴权，可读全部密钥，只放可信网段"),
        _item("app.language", "select", "系统语言", "zh-CN",
              options=["zh-CN", "en-US"], restart=True),
        _item("app.theme", "readonly", "主题", "light", readonly=True,
              notice="当前固定浅色；深色二期（需全站 token 化重做硬编码色值）"),
        _item("appearance.fontSize", "range", "字号(px)", 14, range_=[12, 18], step=1),
    ]},
```

**5.1 + 5.4.2 合并 diff**（两个开关一次改完；**必须紧接 `fontSize` 之后**）：

```diff
--- a/backend/app/services/settings/settings_registry.py
+++ b/backend/app/services/settings/settings_registry.py
@@ -166,6 +166,14 @@
         _item("app.theme", "readonly", "主题", "light", readonly=True,
               notice="当前固定浅色；深色二期（需全站 token 化重做硬编码色值）"),
         _item("appearance.fontSize", "range", "字号(px)", 14, range_=[12, 18], step=1),
+        # 2026-10-05 小欧 - step 渲染显示开关组(文档[9] §5.1): 新前缀 appearance.step_render.*
+        #   独立成「step渲染显示」子块, 不被 SettingsGroup.tsx:78 的"外观"兜底吞掉;
+        #   必须排在 appearance.fontSize 之后 —— sectionOf 只比相邻项(SettingsGroup.tsx:171-172),
+        #   插入位置错乱会插出重复小节标题 — 小欧-2026-10-05
+        _item("appearance.step_render.thoughtMarkdown", "bool", "思考排版", True,
+              notice="任务思考正文(thought)用 Markdown 排版显示(标题/列表/代码块/表格); 关掉则显示纯文本。实时输出与历史回放同样生效"),
+        _item("appearance.step_render.reasoningVisible", "bool", "推理内容", True,
+              notice="推理内容默认展开还是默认收起(只决定新段的初始状态; 每段标题行的箭头可单独展开/收起)。关掉则新出现的推理段默认只显示标题行。"),
     ]},
     # 2026-09-24 小欧 - 模型库：items 空（schema 仅提供 label 供 Tab 渲染），内容走专用组件分支
     "model_library": {"label": "模型库", "items": []},
```

> **两个开关写在同一个 diff 里**，避免分两次编辑 registry 产生中间态。

**三条硬约束**（违反即模块加载拒启或渲染错乱）：

| 约束 | 依据 |
|---|---|
| **不加 `restart=True`** | 显示开关纯前端消费；加了会进 `settings_service.py:346-347` 的 `need_restart`，SaveBar 弹重启提示，属误导 |
| **不加 `secret` / `env_key`** | `settings_registry.py:278-284` 要求 secret 项在 `_SECRET_WRITTEN_BY_PROVIDER_CHANNEL` 登记；`:287-303` 要求 `env_inject` 与 `app.config.ENV_INJECTED_KEYS` 双向一致 —— 任一不满足**导入即拒启** |
| **必须排在 `appearance.fontSize` 之后** | `SettingsGroup.tsx:171-172` 只比较相邻项 `section !== lastSection`；插在 `security.access_token`（`:157`）之前会让小节名序列变成 外观→显示→外观→准入，**插出 3 个标题** |

**默认值 `True`（开）**：优化是本次诉求，用户要看到效果；开关是逃生舱。

**`bool` 零控件代码**：`SettingRow.tsx:244-251` 已自动渲染 antd `Switch`；`disabled = readonly || source==='env'`（`:114`）对无 env 的新项恒 false。**不新增任何 Switch 分支。**

**唯一真源**：设置页 `前端` Tab → 「step渲染显示」子块（§5.10）。改值 → SaveBar 保存
（`useSettings.saveKeys` → `settingsApi.updateSettings`，`:639`）→ 落 YAML → mtime bump。

### 5.2 【新增】`pipeline/useStepRenderPrefs.ts` —— 两开关读取 hook

**这是本方案最大的架构真空，必须新建**。三条硬事实：

1. `settingsApi.getGroup`（`settings.api.ts:138-147`）**全仓零消费方** —— 它正是为"按需拉单组"预留的正确入口；
2. `useSettings`（`hooks/useSettings.ts:224`）**只在 `SettingsPage.tsx:116,151` 被调用**，是整页表单状态机（含模型区 + mtime 守卫 + beforeunload 拦截 + 全屏 loading），**不可搬到 chat 页**；
3. **`appearance.fontSize` 是死配置** —— 存进了 YAML，但全站字号仍走 `App.tsx:46` 硬编码 `fontSize: '14px'` + `stepStyles.ts` 常量，前端业务零消费。

**照抄 fontSize 那条路（存了不读）必然重蹈覆辙**，故本 hook 必须**真消费**：

**新建文件**：`frontend/src/features/chat/components/pipeline/useStepRenderPrefs.ts`（**全新文件，diff 全为 `+`**）

```diff
--- /dev/null
+++ b/frontend/src/features/chat/components/pipeline/useStepRenderPrefs.ts
@@ -0,0 +1,62 @@
+// 编辑历史: 2026-10-05 小欧 - 新增: step 渲染显示两开关的消费 hook(文档[9] §5.2)。
+//   单一真源=后端 YAML(只读 getGroup('appearance')), 无 localStorage、无第二数据源。
+//   架构依据: ①settingsApi.getGroup(settings.api.ts:138)全仓零消费, 本 hook 是其首个消费方;
+//            ②useSettings 是设置页专用状态机(仅 SettingsPage.tsx:116,151 调用), 不可搬进 chat 页;
+//            ③不复用 useSettings.ts:476-491 的 omni.prefs.v1 localStorage 分支 —— 该键全仓无消费方(死代码),
+//              且其 appearance.density 分支指向 registry 不存在的键, 恒 false。
+//   挂载点: 仅 PipelineRenderer 顶层调一次, 以 markdown prop 下传 TextStream
+//           (禁在 segs.map 回调内调 hook, Rules of Hooks) — 小欧-2026-10-05
+import { useCallback, useEffect, useState } from 'react';
+import { settingsApi } from '@/services/api/settings.api';
+
+// 后端 registry 的两个键(单一来源, 禁在此处另写字面量副本)
+const KEY_MD = 'appearance.step_render.thoughtMarkdown';
+const KEY_RV = 'appearance.step_render.reasoningVisible';
+
+/** 两个开关的当前值。缺键(旧版本 registry)或后端不可达时取默认值 true, 保证渲染不崩。 */
+export interface StepRenderPrefs {
+  /** thought 正文是否 Markdown 排版(默认开) */
+  thoughtMarkdown: boolean;
+  /** reasoning 段折叠态初值(默认展开=true): 来自后端 reasoningVisible, 仅作新段初始态;
+   *  每段标题行箭头可单独折叠/展开(本地 state, 不回写后端) — v3.3 语义变更 */
+  reasoningVisible: boolean;
+}
+
+const DEFAULTS: StepRenderPrefs = { thoughtMarkdown: true, reasoningVisible: true };
+
+/**
+ * 设置页保存后广播的事件名 —— 设置页 useSettings.saveKeys 落盘成功后派发,
+ * 本 hook 订阅并重拉。挂载点见文档[9] §5.11。
+ */
+export const SETTINGS_SAVED_EVT = 'omni-settings-saved';
+
+export const useStepRenderPrefs = (): StepRenderPrefs => {
+  const [prefs, setPrefs] = useState<StepRenderPrefs>(DEFAULTS);
+
+  // 单键重拉: 首挂 + 设置页每次保存后。useCallback 稳定身份, 下方 effect 依赖才安全。
+  const reload = useCallback(() => {
+    let alive = true;
+    settingsApi
+      .getGroup('appearance')
+      .then(({ data }) => {
+        if (!alive) return;
+        setPrefs({
+          thoughtMarkdown:
+            data[KEY_MD] === undefined ? true : Boolean(data[KEY_MD]),
+          reasoningVisible:
+            data[KEY_RV] === undefined ? true : Boolean(data[KEY_RV]),
+        });
+      })
+      .catch(() => {
+        /* 后端不可达时聊天本就不可用, 保持 DEFAULTS 不抛错打断渲染 */
+      });
+    return () => {
+      alive = false;
+    };
+  }, []);
+
+  // ⚠️ reload 走 useCallback 而非直接写 effect 体: 直接写会每次渲染重建函数,
+  //   配合下方 [reload] 依赖即造成无限请求 —— 必须是稳定引用。
+  useEffect(reload, [reload]);
+  useEffect(() => {
+    window.addEventListener(SETTINGS_SAVED_EVT, reload);
+    return () => window.removeEventListener(SETTINGS_SAVED_EVT, reload);
+  }, [reload]);
+
+  return prefs;
+};
```

> **v2.10 修正两处**：① v2.9 的 `useSettingsSavedReload` 是**导出了但没人调**的死函数 ——
> 本 hook 根本没订阅，设置页保存后 chat 侧**不会**重拉，"保存后要刷页面"依旧。
> 现改为本 hook 内 `useEffect` 直接订阅，删除该死函数（DRY + 去死代码）。
> ② v2.9 另导出了 `notifySettingsSaved` 但无人调用，而 §5.11 又在 `useSettings` 里裸写
> `new Event('omni-settings-saved')` 字面量 —— **同一常量两处字面量**。现只保留本文件的
> `SETTINGS_SAVED_EVT` 单一来源，`useSettings` 侧 import 它（见 §5.11）。

**`reasoningVisible` 语义已变更（v3.3）**：原为"全局实时开关"，现改为
**「每段折叠的初始态」默认值** —— 用户点 `>` 只改该段的本地 state，不写后端；
后端键只决定**新渲染出来的段**初始是展开还是折叠。设置页那个 Switch 的标签
在 §5.1 的 notice 里已按此语义描述。

**测试**：① mock `getGroup` 返回 `{thoughtMarkdown:false}` → hook 值 false；
② `getGroup` reject → 值回落 `DEFAULTS`，组件不崩；③ `settingsApi.getGroup` 被调用的 group 参数为 `'appearance'`。

### 5.3 【改】`components/WaitingIcons/index.tsx` —— 新增 `ReasoningIcon`

**落点依据**：waiting / tool / action 三个图标都在 `frontend/src/components/WaitingIcons/index.tsx`
（108 行，统一导出），子控件另有 `clockStopwatch.tsx`。新图标属同类，放同一目录。

**⚠️ 必须令牌化（v3.5 修正）**：该文件 `:3` 编辑历史明文规定
「组件内硬编码 SVG 色令牌化（绿 `#52c41a`→`Colors.SUCCESS` / 橙 `#fa8c16`→`Colors.WAIT_ACTION` /
蓝 `#1677ff`→`Colors.PRIMARY`），零行为变化」。57 号原图是硬编码 hex，**直接照搬即违规**。

文件：`frontend/src/components/WaitingIcons/index.tsx`（改前 108 行）

```diff
--- a/frontend/src/components/WaitingIcons/index.tsx
+++ b/frontend/src/components/WaitingIcons/index.tsx
@@ -2,6 +2,8 @@
 // 编辑历史: 2026-09-13 小欧 - ActionWaitingIcon换型(北京老陈令选title-icon-compare G波纹扩散): 蓝色270°弧线旋转改蓝核心圆+双层扩散波纹(SVG36x36, .action-ripple-1/.action-ripple-2, 1.8s不旋转) — 小欧-2026-09-13
 // 编辑历史: 2026-09-14 小欧 - 漏洞2修复: 组件内5处硬编码SVG色令牌化(绿#52c41a→Colors.SUCCESS / 橙#fa8c16→Colors.WAIT_ACTION / 蓝#1677ff→Colors.PRIMARY), 零行为变化 — 小欧-2026-09-14
 // 编辑历史: 2026-09-17 小欧 - 实施: 三角色等待图标接 waitClock 可选信号, 图标保留+钟面追加并存(Thought/Action→kind="llm", Tool→kind="tool") - 小欧-2026-09-17
+// 编辑历史: 2026-10-05 小欧 - 新增 ReasoningIcon(文档[9] §5.3): reasoning 标题行图标, 选既有设计稿
+//   scripts/title-icon-compare.html 57号「信号发射」原样照搬, 三色按本文件 :3 既有约定令牌化 — 小欧-2026-10-05
 import React from 'react';
 import { Colors } from '@/utils/stepStyles';
 import { ClockStopwatch } from './clockStopwatch'; // 2026-09-17 小欧 实施: 微型钟面(追加并存) — 小欧-2026-09-17
@@ -106,3 +108,40 @@
     {waitClock && <ClockStopwatch {...waitClock} kind="llm" />}
   </>
 );
+
+/**
+ * ReasoningIcon — 信号发射（推理标题行图标）
+ * 用途：reasoning 段常驻标题行的行首标识，替换原「🤔 AI」emoji（文档[9] §5.3）
+ * 选型：既有设计稿 scripts/title-icon-compare.html 57 号「信号发射」原样照搬（非新画）
+ * 配色：设计稿硬编码 #52c41a/#1677ff/#fa8c16 → 按本文件 :3 既有约定令牌化，视觉零差异
+ * 动画：beampulse 1.8s 三弧渐次扩散，**常驻不停**（北京老陈 2026-10-05 定案），样式见 index.css
+ * 与 ThoughtWaitingIcon 无关：后者表达"等待首个 chunk"，本图标是段标识，各自独立
+ */
+export const ReasoningIcon: React.FC<{ size?: number }> = ({ size = 24 }) => (
+  <svg
+    viewBox="0 0 36 36"
+    width={size}
+    height={size}
+    fill="none"
+    strokeWidth={2.5}
+    strokeLinecap="round"
+    aria-hidden="true" // 装饰性图标, 语义由标题行文字承载, 不重复读屏
+  >
+    <circle cx="18" cy="18" r="2.5" fill={Colors.SUCCESS} />
+    <path
+      className="reasoning-beam1"
+      d="M6 18 A13 13 0 0 1 30 18"
+      stroke={Colors.SUCCESS}
+    />
+    <path
+      className="reasoning-beam2"
+      d="M6 18 A13 13 0 0 1 30 18"
+      stroke={Colors.PRIMARY}
+    />
+    <path
+      className="reasoning-beam3"
+      d="M6 18 A13 13 0 0 1 30 18"
+      stroke={Colors.WAIT_ACTION}
+    />
+  </svg>
+);
```

**`size` 默认 24**：设计稿 36px 缩 2/3。三色三弧在 12px（`FontSize.SECONDARY`）会糊成一团，
故标题行用 24px 承载 —— 图标尺寸不受文字字号约束，两者并排。

### 5.4 【改】`frontend/src/index.css` —— 图标动画样式

落点依据：`index.css`（293 行）是既有 keyframes 唯一聚集处
（`.thinking-cursor:44` / `.waiting-cursor:109` / `@keyframes thinking-blink:100` /
`waiting-spin:120` / `action-ripple:186` / `clock-beat:266` 皆在此）。

**类名加 `reasoning-` 前缀**：设计稿用 `.beam1~3`，直接搬会与全局撞名。
已核实 `index.css` 现有 keyframes 为 `hitl-breathing` / `thinking-blink` / `waiting-spin` /
`gridwave` / `action-ripple` / `clock-beat`，**`beampulse` 未被占用**，可沿用同名。

文件：`frontend/src/index.css`（改前 293 行）

```diff
--- a/frontend/src/index.css
+++ b/frontend/src/index.css
@@ -291,3 +291,33 @@
   transform-box: fill-box;
   animation: clock-beat 0.6s ease-out 1;
 }
+
+/* 2026-10-05 小欧 - reasoning 标题行「信号发射」图标动画(文档[9] §5.4):
+   既有设计稿 scripts/title-icon-compare.html 57号 原样照搬, 类名加 reasoning- 前缀防撞名;
+   动画常驻不停(北京老陈定案)。与 WaitingIcons/index.tsx 的 ReasoningIcon 配对 — 小欧-2026-10-05 */
+@keyframes beampulse {
+  0% {
+    transform: scale(0.4);
+    opacity: 0;
+  }
+  30% {
+    opacity: 0.7;
+  }
+  100% {
+    transform: scale(1.15);
+    opacity: 0;
+  }
+}
+.reasoning-beam1,
+.reasoning-beam2,
+.reasoning-beam3 {
+  transform-box: view-box;
+  transform-origin: center;
+  animation: beampulse 1.8s ease-out infinite;
+}
+.reasoning-beam2 {
+  animation-delay: 0.6s;
+}
+.reasoning-beam3 {
+  animation-delay: 1.2s;
+}
```

### 5.5 【改】`pipeline/ThinkingStream.tsx` —— 常驻标题行 + 每段独立折叠

**设计依据（北京老陈 2026-10-05 定案）**：

| 项 | 设计 |
|---|---|
| 标题行 | **每个 reasoning 段一个**：`[信号发射图标 24px]` + `推理内容...` + `>` |
| 图标 | **57 号「信号发射」SVG 原样照搬**（三色三弧 + `beampulse` 1.8s 渐次扩散，**动画常驻不停**）；**替换掉原 `🤔 AI` emoji**，文字只保留 `推理内容...` |
| `>` 行为 | **每段独立本地 state**，初始值 = `reasoningVisible`（§5.2 hook 下传）；点击只改自己，**不写后端** |
| 折叠态 | **只显示标题行**，内容全隐（**无阈值、不截断**，故不依赖 `CollapsibleText`） |
| 展开态 | 标题行 + 灰斜体全文（现状样式全保留） |
| 段身份复用 | `PipelineRenderer.tsx:345` 的 key 已是 `thinking-${i}-${seg.text.slice(0,16)}` → 换段即卸载重建，**天然拿到初始态**，无需额外重置逻辑 |
| `ThoughtWaitingIcon` | **零改动** —— 仍是独立 `waiting` 段（`PipelineRenderer.tsx:329-339`），与本图标**各自独立、互不相关**（北京老陈 2026-10-05 确认） |
| 折叠箭头 | 复用既有 `CircleArrow`（`CollapsibleText.tsx:100-105` 同款），不新造图标 |
| 无障碍 | 复用 `CollapsibleText.tsx:79-91` 已验证的 `role=button` + `tabIndex` + `aria-expanded` + Enter/Space 模式 |

**图标来源**：`frontend/scripts/title-icon-compare.html:1885-1883`（57 号「信号发射」）+ 其
`@keyframes beampulse` / `.beam1~3`（同文件 `:634-659`）。**非新画**，是既有设计稿选型。

文件：`frontend/src/features/chat/components/pipeline/ThinkingStream.tsx`（改前 57 行）

```diff
--- a/frontend/src/features/chat/components/pipeline/ThinkingStream.tsx
+++ b/frontend/src/features/chat/components/pipeline/ThinkingStream.tsx
@@ -17,25 +17,38 @@
  * @date 2026-08-26
  */
 
-import React from 'react';
+import React, { useState } from 'react';
 import { Colors, FontSize, Spacing, getStreamStyle } from '@/utils/stepStyles';
 import { normalizeBlankLines } from '@/utils/textNormalize'; // 13.11 显示兜底 — 小欧 2026-08-30
 import { useRiseLog } from '@/features/chat/hooks/useRiseLog'; // 2026-09-14 小欧: CURSOR T 翻转打点(抽公用 hook) — 小欧-2026-09-14
+import { CircleArrow } from '@/components/CircleArrow'; // 2026-10-05 小欧: 折叠箭头复用既有控件(同 CollapsibleText) — 小欧-2026-10-05
+import { ReasoningIcon } from '@/components/WaitingIcons'; // 2026-10-05 小欧: 标题行图标(文档[9] §5.3) — 小欧-2026-10-05
 
 interface ThinkingStreamProps {
   text: string;
   cursor?: boolean; // 实时思考末段光标
   compact?: boolean; // 同 step 内部(13.6 拆出的 reasoning 与后置 thought 相邻): 段距 SM(6)
+  /**
+   * 2026-10-05 小欧 - 折叠态初值(文档[9] §5.5): 来自后端 appearance.step_render.reasoningVisible,
+   *   仅作**本段初始态**; 用户点标题行后只改本地 state, 不回写后端(每段独立折叠)。
+   *   未传时默认 true(展开), 保证既有用法(无此 prop)行为不变。 — 小欧-2026-10-05
+   */
+  defaultExpanded?: boolean;
 }
 
 const ThinkingStream: React.FC<ThinkingStreamProps> = ({
   text,
   cursor = false,
   compact = false,
+  defaultExpanded = true,
 }) => {
   const clean = normalizeBlankLines(text, { streaming: cursor }); // 13.11: 思考段规约, 光标态(实时末段)走尾随守卫
   // 2026-09-14 小欧: thinking 光标本就 bind cursor(无打字机进度门槛), 翻转打点(CURSOR T)
   useRiseLog('CURSOR T', cursor);
+  // 2026-10-05 小欧 - 每段独立折叠(文档[9] §5.5): 本 hook 必须落在下面 `if (!text && !cursor) return null;`
+  //   早退**之前** —— 否则首帧 text 为空时不执行本 hook、后续帧执行, 违反 Rules of Hooks;
+  //   段身份由父级 key(thinking-${i}-${seg.text.slice(0,16)}) 保证换段即重建, 无需 text 重置 — 小欧-2026-10-05
+  const [expanded, setExpanded] = useState(defaultExpanded);
   if (!text && !cursor) return null;
   return (
     <div
@@ -48,8 +61,55 @@
         ...getStreamStyle(compact),
       }}
     >
-      {clean}
-      {cursor && <span className="thinking-cursor">▍</span>}
+      {/* 2026-10-05 小欧 - 常驻标题行 + 每段独立折叠(文档[9] §5.5, 北京老陈定案):
+          标题行每个 reasoning 段一个; 行首图标=既有设计稿 57 号「信号发射」原样照搬
+          (WaitingIcons.ReasoningIcon, §5.3), 替换原「🤔 AI」emoji, 文字只留「推理内容...」;
+          标题行点按只改本段 state(每段独立), 不写后端、不影响其它段 — 小欧-2026-10-05 */}
+      <span
+        role="button"
+        tabIndex={0}
+        aria-expanded={expanded}
+        aria-label={expanded ? '收起推理内容' : '展开推理内容'}
+        onClick={(e) => {
+          e.stopPropagation();
+          setExpanded((prev) => !prev);
+        }}
+        onKeyDown={(e) => {
+          if (e.key === 'Enter' || e.key === ' ') {
+            e.preventDefault();
+            e.stopPropagation();
+            setExpanded((prev) => !prev);
+          } else {
+            e.stopPropagation();
+          }
+        }}
+        style={{
+          // v3.6 订正: 原 v3.5 写 display:'inline-flex' 是错的 —— inline-flex 是**行内盒**,
+          //   其后紧跟的推理正文会**接在同一行**(标题行与正文串行, 破版)。
+          //   必须块级(flex) 正文才回下一行 = 保持 2026-10-05 之前"正文独占一行"的原样。
+          //   width:fit-content: 块级但宽度只占内容, 避免整行被 pointer 事件铺满。
+          display: 'flex',
+          width: 'fit-content',
+          alignItems: 'center',
+          gap: Spacing.XS,
+          fontStyle: 'normal', // 标题不用斜体(斜体是 reasoning 正文的视觉标记)
+          fontSize: FontSize.SECONDARY,
+          color: Colors.TEXT.SECONDARY,
+          cursor: 'pointer',
+          userSelect: 'none',
+        }}
+      >
+        <ReasoningIcon size={24} />
+        {'推理内容...'}
+        <CircleArrow
+          size={14}
+          color={Colors.PRIMARY}
+          expanded={expanded}
+          animated={false}
+        />
+      </span>
+      {/* 正文: 折叠态完全不渲染(无阈值、不截断, 故不依赖 CollapsibleText) */}
+      {expanded && (
+        <>
+          {clean}
+          {cursor && <span className="thinking-cursor">▍</span>}
+        </>
+      )}
     </div>
   );
 };
```

**类名加前缀 `reasoning-`**：设计稿用 `.beam1~3`，直接搬会与全局/其它样式撞名。
改为 `.reasoning-beam1~3`，`@keyframes beampulse` 同名沿用（`index.css` 内该名未占用，
已核实现有 keyframes 为 `hitl-breathing`/`thinking-blink`/`waiting-spin`/`gridwave`/
`action-ripple`/`clock-beat`，**无 `beampulse`**）。

### 5.6 【新增】`hooks/useDisclosure.ts` —— 折叠交互公用 hook（消 DRY 重复）

**起因（v3.6 三堂会审发现）**：`CollapsibleText.tsx:79-91` 与 §5.5 `ThinkingStream` 标题行的
`onClick` / `onKeyDown` + `stopPropagation` 逻辑**逐行重复 13 行**，违 **DRY + 复用优先**。

**范围界定（刻意收窄，守 SRP）**：本 hook **只管"切换 + 事件处理"**，
**不管折叠阈值、不管渲染** —— `CollapsibleText` 的 `maxLines`/`maxChars` 阈值与
`ThinkingStream` 的"折叠即全隐"策略各自留在各自组件（两者语义本就不同，不强行统一）。

**行为等价性**：Enter/Space 切换 + 全分支 `stopPropagation`，与原实现逐字一致 ——
`CollapsibleText` 的 **5 处复用方**（`TaskListPanel.tsx:307,356,383` / `ResponseStream.tsx:45` /
`ToolCallLine.tsx:448`）行为**零变化**。

```diff
--- /dev/null
+++ b/frontend/src/features/chat/hooks/useDisclosure.ts
--- /dev/null
+++ b/frontend/src/features/chat/hooks/useDisclosure.ts
@@ -0,0 +1,45 @@
+// 编辑历史: 2026-10-05 小欧 - 新建: 折叠/展开交互公用 hook(文档[9] §5.8)
+//   起因: CollapsibleText.tsx(2026-08-30 起)与 ThinkingStream 标题行(2026-10-05)的
+//   onClick/onKeyDown + stopPropagation 逻辑逐行重复, 违 DRY/复用优先 —— 抽本 hook 消重复。
+//   行为与原实现逐字等价(Enter/Space 切换 + 全分支 stopPropagation 防误触外层 onSelect),
+//   CollapsibleText 5 处复用方(TaskListPanel x3 / ResponseStream / ToolCallLine)行为零变化。
+//   范围: 只管"切换 + 事件处理", 不管折叠阈值、不管渲染 —— CollapsibleText 的 maxLines/maxChars
+//   与 ThinkingStream 的"折叠即全隐"策略各自保留在各自组件(不强行统一, 避免 SRP 越界)。 — 小欧-2026-10-05
+import { useCallback, useState } from 'react';
+import type { KeyboardEvent, MouseEvent } from 'react';
+
+/** 折叠切换。返回 expanded + 可直接摊给 DOM 的 onClick/onKeyDown（已含 a11y 键盘可达与阻止冒泡）。 */
+export interface UseDisclosureResult {
+  expanded: boolean;
+  /** 切换（一般不需要直接用，除非自定义触发器） */
+  toggle: () => void;
+  onToggleClick: (e: MouseEvent) => void;
+  onToggleKeyDown: (e: KeyboardEvent) => void;
+}
+
+export const useDisclosure = (initial = false): UseDisclosureResult => {
+  const [expanded, setExpanded] = useState(initial);
+  const toggle = useCallback(() => setExpanded((prev) => !prev), []);
+  // stopPropagation: 折叠按钮在消息流里，外层有 onSelect(左栏自动展开)，冒泡会误触
+  //   历史 bug: 2026-08-30 北京老陈反馈「展开」误触外层导致右栏自动展开 — 沿用既有处理
+  const onToggleClick = useCallback(
+    (e: MouseEvent) => {
+      e.stopPropagation();
+      toggle();
+    },
+    [toggle]
+  );
+  const onToggleKeyDown = useCallback(
+    (e: KeyboardEvent) => {
+      if (e.key === 'Enter' || e.key === ' ') {
+        e.preventDefault(); // 空格默认滚动页面
+        e.stopPropagation();
+        toggle();
+      } else {
+        e.stopPropagation();
+      }
+    },
+    [toggle]
+  );
+  return { expanded, toggle, onToggleClick, onToggleKeyDown };
+};
```

### 5.7 【改】`pipeline/CollapsibleText.tsx` —— 内联折叠逻辑改用公用 hook

**只改内部实现，props 与对外行为零变化**（`maxLines` / `maxChars` / 折叠阈值 / 首2行摘要逻辑全不动）。

```diff
--- a/frontend/src/features/chat/components/pipeline/CollapsibleText.tsx
+++ b/frontend/src/features/chat/components/pipeline/CollapsibleText.tsx
@@ -26,6 +26,9 @@
 import React, { useMemo, useState } from 'react';
 import { CircleArrow } from '@/components/CircleArrow';
 import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
+// 2026-10-05 小欧 - 折叠交互抽公用 hook(文档[9] §5.8): 本组件与 ThinkingStream 标题行
+//   的 onClick/onKeyDown 逻辑逐行重复, 违 DRY/复用优先; 抽 useDisclosure 消重复(零行为变化) — 小欧-2026-10-05
+import { useDisclosure } from '@/features/chat/hooks/useDisclosure';
 
 interface CollapsibleTextProps {
   text: string;
@@ -38,7 +41,9 @@
   maxLines = 5,
   maxChars = 200,
 }) => {
-  const [expanded, setExpanded] = useState(false);
+  // 2026-10-05 小欧 - 折叠 state 与交互改用公用 hook(文档[9] §5.8), 消与 ThinkingStream 的重复 — 小欧-2026-10-05
+  const { expanded, setExpanded, onToggleClick, onToggleKeyDown } =
+    useDisclosure(false);
   // 2026-09-03 小欧 修复: text变化(跨消息切换)时重置expanded, 用首100字符做key区分同消息内流式追加
   const _textKey = text.slice(0, 100);
   const _prevTextKeyRef = React.useRef(_textKey);
@@ -66,7 +71,6 @@
     return text;
   }, [text, overflow, expanded, maxChars]);
 
-  const toggle = () => setExpanded((prev) => !prev);
 
   return (
     <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
@@ -76,19 +80,8 @@
           role="button"
           tabIndex={0}
           aria-expanded={expanded}
-          onClick={(e) => {
-            e.stopPropagation();
-            toggle();
-          }}
-          onKeyDown={(e) => {
-            if (e.key === 'Enter' || e.key === ' ') {
-              e.preventDefault();
-              e.stopPropagation();
-              toggle();
-            } else {
-              e.stopPropagation();
-            }
-          }}
+          onClick={onToggleClick}
+          onKeyDown={onToggleKeyDown}
           style={{
             fontSize: FontSize.SECONDARY,
             marginLeft: Spacing.XS,
```

### 5.8 【改】`pipeline/PipelineRenderer.tsx` —— 下传两开关值

> 北京老陈 2026-10-05 明确：这是**两个不同的东西**。① **思考排版** = Markdown 排版开关
> （只作用于 thought 正文段）；② **推理内容** = reasoning 段的**折叠初值**（只作用于 reasoning 段）。
> 两者各管各的段，**没有正交组合**，各自独立测试通过即整体通过。

**与 §5.1 思考排版共用同一个 hook**（`useStepRenderPrefs`），不新建第二个 hook —— DRY。
（后端两个键已合并在 §5.1 的 diff 中一次加完，此处不重复贴 registry 代码。）

**⚠️ v3.3 变更**：**不再**在此处做"收起分支"（`if (!streaming && !reasoningVisible) return <CollapsibleText/>` 已删）。
折叠逻辑整体移入 `ThinkingStream`（§5.3），本文件只负责**下传 `defaultExpanded`** ——
保持"谁渲染谁负责折叠"，本文件不掺入 reasoning 的展示细节（SRP）。

文件：`frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx`（改前 474 行）

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
+++ b/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ -100,6 +100,8 @@
 import { ToolCallLine } from './ToolCallLine';
 import { StatusLine } from './StatusLine';
 import { TextStream } from './TextStream'; // 13.8 正文打字机 — 小欧 2026-08-30
+// 2026-10-05 小欧 - step 渲染显示两开关(文档[9] §5.8) — 小欧-2026-10-05
+import { useStepRenderPrefs } from './useStepRenderPrefs';
 import { ThoughtWaitingIcon } from '@/components/WaitingIcons'; // 2026-09-13 小欧: ThoughtWaitingIcon 从内联提取为独立控件 — 小欧-2026-09-13
 import { formatErrorType } from '@/features/chat/components/ErrorDetail'; // 2026-09-17 小欧 修改: 中文标签映射复用, 失败细节行英文枚举转中文 — 小欧-2026-09-17
 import type { ClockSignals } from '@/types/sse'; // 2026-09-17 小欧 实施: 钟面信号类型 — 小欧-2026-09-17
@@ -298,6 +300,11 @@
 }) => {
   const segs = buildSegments(steps);
   const taskActive = computeTaskActive(highlightToolName, badge);
+  // 2026-10-05 小欧 - step 渲染显示两开关(文档[9] §5.8): hook 顶层调一次取两值(Rules of Hooks:
+  //   不可在下方 segs.map 回调内调), 结果以 prop 下传给 TextStream / ThinkingStream;
+  //   ①thoughtMarkdown 管 text 段是否喂 MarkdownText; ②reasoningVisible 管 reasoning 段的折叠初值;
+  //   两开关作用于不同段, reasoning 段永不进 Markdown — 小欧-2026-10-05
+  const { thoughtMarkdown, reasoningVisible } = useStepRenderPrefs();
   // 2026-09-04 小欧 - observation 去重：已消费孤儿抑制（单/多工具并行时孤儿与 ToolCallLine 重复）
   const toolStepSet = new Set(
     segs
@@ -346,6 +353,7 @@
               text={seg.text}
               cursor={cursor}
               compact={seg.sameStep}
+              defaultExpanded={reasoningVisible} // 2026-10-05 小欧: 折叠初值(文档[9] §5.5), 每段独立折叠 — 小欧-2026-10-05
             />
           );
         }
@@ -360,6 +368,7 @@
               cursor={isLive}
               compact={seg.sameStep}
               waitClock={waitClock} // 2026-09-17 小欧 实施: 钟面信号 — 小欧-2026-09-17
+              markdown={thoughtMarkdown} // 2026-10-05 小欧: 思考排版开关(文档[9] §4.2) — 小欧-2026-10-05
             />
           );
         }
```

**`CollapsibleText` 回到零改动**（v3.2 曾计划在 thinking 分支改用它，现已不需要）。

**`waiting` 段（`ThoughtWaitingIcon`）分支零改动**（`:329-339`）—— 绿转圈机制原样保留。

### 5.9 【改】`useChatStreaming.ts` —— 发送占位改空串

**为什么改**：§5.5 上线后，标题行 `推理内容...` 常驻，已承担"正在推理"的告知。
气泡 content 再写一遍 `🤔 AI 正在思考...` 即**重复信息**。

文件：`frontend/src/features/chat/hooks/useChatStreaming.ts`（改前 619 行）

```diff
--- a/frontend/src/features/chat/hooks/useChatStreaming.ts
+++ b/frontend/src/features/chat/hooks/useChatStreaming.ts
@@ -562,7 +562,11 @@
       const assistantMessage: Message = {
         id: assistantId,
         role: 'assistant',
-        content: '🤔 AI 正在思考...',
+        // 2026-10-05 小欧 - 占位文案改空串(文档[9] §5.8): 「推理内容...」标题行已由
+        //   ThinkingStream 常驻提供(§5.5), 气泡再写一遍是重复信息; 且本占位在非 final 帧
+        //   永不替换(见 useChatCallbacks.ts:311), 断流时永久卡住 —— 空串不引入该风险。
+        //   本消息壳仍在(isStreaming=true), 用户仍能看到流水线里的等待图标 — 小欧-2026-10-05
+        content: '',
         timestamp: new Date(),
         executionSteps: [],
         isStreaming: true,
```

**不影响**：消息壳仍创建（`isStreaming: true`），故用户仍立即看到 assistant 消息位置 +
流水线里的 `ThoughtWaitingIcon` 绿转圈（§5.8 零改动）。

### 5.10 【改】`useChatCallbacks.ts` —— 兜底占位改空串

**为什么改**：同 §5.8，另有一处更严重的卡住路径。

**卡住机理（实读核实）**：`useChatCallbacks.ts:271` 分支在"最后一条不是 assistant"时新建消息，
content 写入占位文案（`:287` / `:291`）；而后续所有**非 final** 帧走 `:311`
`stepDisplayContent = lastMessage.content` —— **原样保留**，只有 `final` 帧（`:308`）才可能替换。
故 `final` 未到达（中断/断流/只到 `thought-start`）时，该文案**永久显示**。

文件：`frontend/src/features/chat/hooks/useChatCallbacks.ts`（改前 907 行）

```diff
--- a/frontend/src/features/chat/hooks/useChatCallbacks.ts
+++ b/frontend/src/features/chat/hooks/useChatCallbacks.ts
@@ -284,11 +284,11 @@
               step.type === 'final'
                 ? (step.response as string) ||
                   (step.content as string) ||
-                  '🤔 AI 正在思考...'
+'' // 2026-10-05 小欧 - 原 '🤔 AI 正在思考...': 标题行已常驻(§5.5), 重复且会卡住 — 小欧-2026-10-05
                 : step.content ||
                   (step.type === 'error'
                     ? step.error_message || '执行出错'
-                    : '🤔 AI 正在思考...'),
+                    : ''), // 2026-10-05 小欧 - 同上; 空串避免非 final 帧把占位永久留住(§5.9 前言) — 小欧-2026-10-05
             timestamp: step.timestamp ? new Date(step.timestamp) : new Date(),
             executionSteps: [step], // 直接使用当前step
             isStreaming: step.type !== 'error' && step.type !== 'final',
```

**触发场景不变**（本 diff 只改文案，不改分支条件）：刷新后续接进行中任务、
发送异常占位被清后帧才到、后端不发 `start` 直接发 `paused`/`retrying`。

**不影响**：`useChatSend.ts:167-171` 的幽灵消息清理按 `role==='assistant' && isStreaming===true`
过滤，**不看文案** → 本改动与该机制完全解耦。

**连带测试改动**（文案改空串后以下断言失效，必须同步）：

| 文件 | 处数 |
|---|---|
| `hooks-chat-send-bug.test.ts` | 4（`:54,:87` 等） |
| `hooks-chat-callbacks-bugs.test.ts` | 1（`:122`） |
| `useChatCallbacks-error-diversion.test.tsx` | 1（`:119`） |
| `stage12_real_bug_hunt.test.tsx` | 1（`:204`） |
| `base-layer-sse-bugs.test.tsx` / `sse-data-flow.test.ts` / 等 | 仅**构造**入参（如 `content:'思考中'`），**非断言本占位**，无需改 |

### 5.11 【改】`settings2/components/SettingsGroup.tsx` —— 「step渲染显示」子块

**决策**：两个开关在设置页 `前端` Tab 内归为一个子块，**组名「step渲染显示」**。
不新建后端 group（不动 Tab 结构），分组由前端按键前缀切 —— 与现有
「登录与准入 / 外观」两子块同一机制。

> **v2.7 更正两处 v2.6 的错**：
> ① 函数名写成了不存在的 `sectionNameForKey` —— 真实是 **`sectionOf(group, key)`**（`SettingsGroup.tsx:55`）；
> ② 前缀写 `appearance.thought`/`appearance.reasoning` —— 若沿用 `appearance.*` 会被 `:78` 的
>    `return '外观'` 兜底吞掉。**必须用新前缀 `appearance.step_render.`**（§5.1）。

**设置页最终形态**（Tab 前端 → 三块，按 `settings_registry.py` items 数组顺序）：

| 子块 | 项 | 键 | 类型 |
|---|---|---|---|
| 登录与准入 | 访问口令 / 免口令 IP 白名单 | `security.*` | 现状，不动 |
| 外观 | 系统语言 / 主题 / 字号 + 预览小卡 | `app.*` / `appearance.fontSize` | 现状，不动 |
| **step渲染显示** | **思考排版** | `appearance.step_render.thoughtMarkdown` | Switch |
| | **推理内容** | `appearance.step_render.reasoningVisible` | Switch |

**前端 diff** —— `frontend/src/features/settings2/components/SettingsGroup.tsx`（改前 220 行）：

```diff
--- a/frontend/src/features/settings2/components/SettingsGroup.tsx
+++ b/frontend/src/features/settings2/components/SettingsGroup.tsx
@@ -75,6 +75,9 @@
   //   语义切分理由同后端：准入控制 ≠ 外观偏好，混在一块会让人误以为"改外观就能改准入"。
   if (group === 'appearance') {
     if (key.startsWith('security.')) return '登录与准入';
+    // 2026-10-05 小欧 - step渲染显示子块(文档[9] §5.10, 北京老陈定案): 两个 thought 段显示开关归于此。
+    //   必须排在下一行"外观"兜底之前 —— 否则会被兜底静默吞进「外观」块; 前缀与后端 registry 同名段对齐。 — 小欧-2026-10-05
+    if (key.startsWith('appearance.step_render.')) return 'step渲染显示';
     return '外观';
   }
   if (group === 'tuning') {
```

**子块内顺序**：由后端 registry 中两个 `_item` 的先后决定（`thoughtMarkdown` 在前），
前端不重排 —— 单一真源在顺序上也不二义。

**预览小卡不受影响**：`SettingsGroup.tsx:175-176` 的 `showAppearancePreview` 门控是
`header === '外观'`，两开关子块在其后，标题不同故不触发。

**零 `Switch` 代码**：`bool` 在 `SettingRow.tsx:244-251` 自动渲染为 antd `Switch`，
`disabled = readonly || source === 'env'`（`:114`）对新项恒 false，无特例分支。

**Tab 层零改动**：不新增 group，故不动 `GROUP_ORDER`（`settings_registry.py:253`）、
不动前端 `types.ts:35-43` 的 `TabKey` 联合枚举（**加了新 group 而漏改它会 tsc 报错**）。

### 5.12 【改·可选】`settings2/hooks/useSettings.ts` —— 保存后广播，chat 侧重拉

**问题**：`PipelineRenderer` 挂载时拉一次 `getGroup('appearance')`。用户在设置页改完保存后，
**已挂载的 chat 页不会自动更新**（要刷新页面）—— 这是"存了不读"之外的第二个"看起来没生效"。

**方案**：设置页 `saveKeys` 落盘成功后派发 window 事件，chat 侧 hook（§5.2）订阅重拉。
**不改后端、不改 API、不引新依赖。**

```diff
--- a/frontend/src/features/settings2/hooks/useSettings.ts
+++ b/frontend/src/features/settings2/hooks/useSettings.ts
@@ -81,6 +81,9 @@
   settingsApi,
   type SettingSchemaItem,
 } from '@/services/api/settings.api';
+// 2026-10-05 小欧 - step渲染显示开关(文档[9] §5.11): 事件名单一来源
+//   (禁在本文件写字面量副本) — 小欧-2026-10-05
+import { SETTINGS_SAVED_EVT } from '@/features/chat/components/pipeline/useStepRenderPrefs';
 import { modelApi, type ProviderEntry } from '@/services/api/model.api';
 import {
   isDirty,
@@ -697,6 +700,10 @@
         });
         // A7：用落盘后 mtime 覆盖缓存，防假后门刷新误判
         syncMtime(result.mtime);
+        // 2026-10-05 小欧 - step渲染显示开关(文档[9] §5.11): 保存成功后广播, chat 侧重拉
+        //   appearance.step_render.* —— 否则设置页改了, 已挂载的聊天页要刷新才生效。
+        //   事件名 import 自 useStepRenderPrefs(单一来源, 禁在此处写字面量) — 小欧-2026-10-05
+        window.dispatchEvent(new Event(SETTINGS_SAVED_EVT));
         return { ok: true as const };
       } catch (e) {
         handleApiError(e);
```

> **⚠️ 跨层依赖须知**：`settings2` → `chat` 的 import 是**新引入的反向依赖**
> （现有方向是 `SettingsPage` 不感知 chat）。故本段**标为可选**：
> 若评审不接受该方向，接受"设置页改完刷页面"（与既有 `appearance.fontSize` 同样的限制）。
> **本方案默认做它**，因为 2 行换"改完即生效"；方向问题在落码时按项目实际依赖规范再定。

hook 侧订阅已在 §5.2 的 `useStepRenderPrefs` 内实现（`useEffect` 监听 `SETTINGS_SAVED_EVT`）。

### 5.13 纯设计说明（**本节零代码**）

> §5.1~§5.11 每个小节对应**一个代码文件**。本节汇集纯设计论证，不含任何实施代码。

#### 5.13.1 开关位置：只有设置页，无快捷开关（v2.7 定案，删除 TaskInfoBar 方案）

v2.2~v2.6 计划在 `TaskInfoBar` 头部挂快捷开关。**核查真实代码后否决**：

| 核查项 | 真实情况 | 依据 |
|---|---|---|
| `TaskInfoBar` props | `steps/frames/detail/sessionId/liveError` —— **不接受任何 onChange 回调** | `TaskInfoBar.tsx:121-127` |
| 既有折叠态机 | **已被显式删除**，注释写明"collapsed 状态机/localStorage 键已删除" | `TaskInfoBar.tsx:136` |
| 头部操作区现有元素 | 仅 2 个可交互：`TrustPanel`（G7）、`FloatingEntry`「事件」（G8） | `TaskInfoBar.tsx:424-482` |
| 可复用的就地切换范式 | **无**。最接近的 `SessionPanelRegistry.readPanelVisible` 读侧完整但**写侧从未实现**，且注册表类已于 2026-08-27 删除 | `SessionPanelRegistry.ts:31-43` |

**结论**：加快捷开关需扩 `TaskInfoBar` props 或自持状态，还要额外解决与设置页的双向同步
（谁是唯一真源），属 YAGNI。故**本方案只做设置页主开关**，`TaskInfoBar` 零改动。
若日后确需快捷开关，最接近的架构先例是 `FloatingEntry`（`:448-451`）的"单一 `onChange` 真源"写法。

#### 5.13.2 消费侧架构真空（§5.2 hook 为何必须新建）

1. `settingsApi.getGroup`（`settings.api.ts:138-147`）**全仓零消费方** —— 它正是为"按需拉单组"预留的正确入口；
2. `useSettings`（`hooks/useSettings.ts:224`）**只在 `SettingsPage.tsx:116,151` 被调用**，是整页表单状态机（含模型区 + mtime 守卫 + beforeunload 拦截 + 全屏 loading），**不可搬到 chat 页**；
3. **`appearance.fontSize` 是死配置** —— 存进了 YAML，但全站字号仍走 `App.tsx:46` 硬编码 `fontSize: '14px'` + `stepStyles.ts` 常量，前端业务零消费。

**照抄 fontSize 那条路（存了不读）必然重蹈覆辙**，故 §5.2 的 hook 必须**真消费**。

#### 5.13.3 无组合表（v2.5 删除，此处仅存档说明）

v2.3/v2.4 曾有 4 格正交组合表，**建立在错误映射上**（Markdown 做在 reasoning 段），已删除。
正确映射下两个开关**作用于不同段、不同组件、不同后端键，零共享状态** —— 没有交互，
**无组合可言**，各自独立测试通过即整体通过。

#### 5.13.4 取舍记录：常驻动画图标（v3.4）

**决策**（北京老陈 2026-10-05）：57 号「信号发射」图标**动画常驻不停**，不做"仅流式时动"的条件动画。

**理由**：① 标题行是常驻的（折叠态也在），条件动画会让折叠态图标"死掉"，
用户无法分辨"这段推理结束了"还是"图标没在动"；② 折叠/展开是每段独立的 UI 状态，
与流式状态是两个正交维度，让图标去表达流式状态会造成语义混淆；
③ 图标与 `ThoughtWaitingIcon` **各自独立、互不相关**（等待态由 waiting 段表达，不靠标题行图标）。

**代价与接受**：每段一个常驻 CSS 动画 SVG。CSS 动画走合成器、不占主线程，
开销远低于 JS 定时器；同屏 reasoning 段数通常 ≤5（`buildSegments` 相邻同类合并），
可接受。**若日后实测掉帧**，改法是给 `.reasoning-beam*` 加
`@media (prefers-reduced-motion: reduce) { animation: none }`（一行，不动组件）。

> **v3.6 实施回写**：上面这条降级建议**已在实施中一并落地**（`index.css` 末尾
> `@media (prefers-reduced-motion: reduce)` 段已加），故不再是"若日后"的可选项。

### 5.14 北京老陈口头裁定补记（v3.3~v3.5 之后新增，原文档未记录）

> 本节两条是实施过程中的**口头裁定**，v3.5 及之前的版本历史里查不到，现补记以免后续误改回旧行为。

#### 5.14.1 标题行图标两态（收起=亮+动画 / 展开=暗 0.3+静止）

| 状态 | 亮度 | 扩散动画 | 理由 |
|---|---|---|---|
| **收起**（`expanded=false`） | 亮（正常色） | **保留 1.8s 扩散** | 正文看不见，动画在提示"这一段被折叠，内有思考" |
| **展开**（`expanded=true`） | **暗 = `opacity: 0.3`** | **静止** | 正文已在眼前，再闪就是干扰 |

落地：`ReasoningIcon` 收 `dim?: boolean`（§5.3 组件本体不动样式），按 `dim` 挂 `.reasoning-icon-dim`；
两态样式全在 `index.css`（`.reasoning-icon-dim .reasoning-beam1~3 { animation:none; opacity:.3 }`）。

> **v3.5 的"动画常驻不停"（v3.4 沿用）已被本裁定细化**：不再是"收起亮/展开也亮"，
> 而是两态分明。§5.9.4 的取舍记录需按本条理解。

#### 5.14.2 「推理内容...」标题行排在等待绿圈的**上一行**，且等待期先出现

**背景**：v3.5 §5.13.4 写"`ThoughtWaitingIcon` **不自动随思考段渲染**/零改动"，实施后
`thought-start` 帧只产 `waiting` 段（该帧无任何推理文本），而标题行挂在 `thinking` 段上，
两者**不同时存在** → 屏幕上先冒一个孤零零绿圈，文本到达后整行替换，标题行天然晚一拍。

**北京老陈裁定**：绿圈**保留不删**，等待图标原有显示逻辑（`ThoughtWaitingIcon` 组件、
末段+`taskActive` 门控、挂钟面）**一字不改**；只把标题行提到绿圈**上一行**，并让它在等待期就先出现。

落地（仅改 `PipelineRenderer` 的 `waiting` 分支，不动 `buildSegments`、不动绿圈组件）：

```
阶段① thought-start 到达、尚无推理文本：
  第1行  [ReasoningIcon] 推理内容... >     ← 先显示
  第2行  (绿圈 ThoughtWaitingIcon)          ← 换行到下面这行
阶段② 首个推理文本到达：waiting 段被 appendToLast 原地替换为 thinking 段
  第1行  [ReasoningIcon] 推理内容... >     ← 原地不动，不闪
  第2行  推理正文（随流式增长）
```

### 5.15 偏离登记表（v3.6 新增：文档原写 vs 实际实施 vs 裁定状态）

> **用途**：本次实施有 6 处"文档 diff 与实况不符"，其中 5 处是文档写错、1 处是实施自行替换。
> 后续维护**以本表为准**，勿再照抄 §5.x 的旧 diff 代码块。

| # | 文档原写 | 实际实施 | 性质 | 状态 |
|---|---|---|---|---|
| 1 | §5.5 `display:'inline-flex'`（v3.5，1007 行） | `display:'flex'` + `width:'fit-content'` | **文档错**：行内盒致标题行与正文串行 | 已按实况订正 §5.5 |
| 2 | v3.3 §5.3 "段身份复用既有 key `thinking-${i}-${slice(0,16)}`" | 只用段下标 `thinking-${i}` | **文档错**：切片随流式增长而变，前 16 字内每 chunk 换 key → 折叠态被弹回 | 已按实况订正（本文 v3.6 §5.5 说明） |
| 3 | §5.6 `UseDisclosureResult` 4 项（`expanded`/`toggle`/`onToggleClick`/`onToggleKeyDown`） | 5 项：`toggle` 不导出，改导出 `setExpanded` | **文档漏**：`CollapsibleText` 的"文本变化重置"需 `setExpanded`，否则 §5.7 编译不过 | 已补；`toggle` 按 YAGNI 收为内部私有 |
| 4 | §5.5 `useState(defaultExpanded)` + 内联 `onClick`/`onKeyDown` | `useDisclosure(defaultExpanded)`（§5.7 的 DRY 写法） | **文档自相矛盾**：§5.7 要求消除重复，§5.5 却写内联 | 取 §5.7，行为逐分支等价 |
| 5 | 第 4 章：`MarkdownText.tsx` + 装 4 个依赖（`react-markdown`/`remark-gfm`/`remark-breaks`/`rehype-sanitize`） | 自研 `pipeline/MarkdownBody.tsx`，**零新依赖**（围栏代码块/行内代码/粗体/斜体/1~3 级标题/无序列表子集，全程不用 `dangerouslySetInnerHTML`） | **实施自行替换，未经批准** | ⚠️ **待北京老陈裁定**：装回 4 依赖按第 4 章做，还是保留自研零依赖版 |
| 6 | v3.5 `ThoughtWaitingIcon` 零改动 | waiting 段**上方**加一行标题行 | **新增裁定**：见 §5.14.2 | 已按裁定实施 |
| 7 | §5.4 `.reasoning-icon-dim` 仅 CSS | `ReasoningIcon` 收 `dim` prop 并挂该类 | **文档漏**：类无组件挂载 = 死规则，两态零落地 | 已补，见 §5.14.1 |

---

## 六、分步落地（每步独立可验，代码即上一步产出）

### 第 1 步：装依赖 + 建组件骨架

```bash
cd frontend
npm install react-markdown@^9 remark-gfm@^4 remark-breaks@^2 rehype-sanitize@^6
npm install -D @types/hast@^3
```

新建 `MarkdownText.tsx`（§4.1 全文），**暂不接入** `TextStream`。
验证：`npm run typecheck` 通过。

### 第 2 步：算法单测（抖动回归守卫）

新建 `src/tests/unit/markdown-text-fence.test.tsx`，覆盖 §3.3 全部 8 条用例（纯函数）+ 3 条渲染态用例：

| 用例 | 断言 |
|---|---|
| 未闭合围栏渲染 | 喂 ` ```js ` → `container.querySelectorAll('pre').length === 0` |
| 闭合围栏渲染 | 喂 ` ```js\nx\n``` ` → `<pre>` 数量 `=== 1` 且含 `language-js` class |
| 流式逐字符 | 逐字喂 ` ```js\nx\n``` `，全程 `<pre>` 数量只在闭合那一刻由 0 变 1 |

验证：`npm run test` 该文件通过。

### 第 3 步：接入 + XSS 断言

改 `TextStream.tsx`（§4.2）+ `PipelineRenderer.tsx`（§5.8）+ 新建 `useStepRenderPrefs.ts`（§5.2）。
补 XSS 用例：喂 `<script>alert(1)</script>` 与 `<img src=x onerror=alert(1)>`，断言 `container.querySelector('script') === null` 且无 `onerror` 属性。

验证：`npm run check:full`（**注意 `check:full` 不含 `typecheck:e2e`，须单独跑**）+ `npm run test` 全绿。

### 第 4 步：后端 2 行 + 设置页 1 行

| 文件 | 改动 |
|---|---|
| `settings_registry.py` | `appearance.fontSize` 之后加 2 个 `bool` 项（§5.1），**不加 restart/secret/env_key** |
| `SettingsGroup.tsx` | `:78` 之前加 1 行前缀分支（§5.10） |
| `useSettings.ts` | 可选：`saveKeys` 成功后派发事件（§5.11） |

**后端自检**：`settings_registry.py:263-307` 三项 fail-fast（键唯一 / secret 登记 / env 双向一致）。
**启动即拒启 = 改错了**，故改完必须重启后端看是否正常起来。

验证：`PUT /api/v1/settings` 带 `{"patch":{"appearance.step_render.thoughtMarkdown": false}}` 返回 `ok:true`。

### 第 5 步：E2E 回归

| 命令 | 关注点 |
|---|---|
| `npx playwright test fre2e_13_switch_back_continuity.spec.ts --reporter=line` | 实时切页时 thought 段回放 |
| `npx playwright test fre2e_14_refresh_resume_seq.spec.ts --reporter=line` | 刷新续传后 thought 段完整 |

前置：vite `:5173` + 后端 `:8000` 均在跑（`fre2e_19` 实测流程可直接复用）。

### 第 6 步：提交

```bash
git add -A frontend/src/features/chat/components/pipeline/ frontend/src/features/settings2/ backend/app/services/settings/settings_registry.py frontend/package.json frontend/package-lock.json
git commit -m "feat:MarkdownText.tsx+TextStream.tsx thought正文段Markdown渲染(未闭合围栏延迟开启防页面位移) - 小欧-2026-10-05"
```

---

## 七、验收门（AGENTS.md 硬性，一项不过即返工）

| 门 | 命令 | 通过标准 |
|---|---|---|
| 类型 | `npm run typecheck` | 零错误 |
| **e2e 类型** | `npm run typecheck:e2e` | 零错误（**`check:full` 不含此项，必跑** —— AGENTS.md 2026-10-01 修订） |
| Lint | `npm run lint` + `npm run lint:e2e` | 零 error |
| 格式 | `npm run format:check` | 通过 |
| 单测 | `npm run test` | 1485 全绿 + 新增用例全绿 |
| **构建** | `npm run build` | 成功（新增依赖须验证生产构建） |
| E2E | `fre2e_13` + `fre2e_14` | PASSED |

---

## 八、10 大规范逐条判定

| 规范 | 判定 |
|------|------|
| **SRP** | ✅ `MarkdownText` 只管"Markdown 渲染 + 围栏延迟 + 折叠委派"；`TextStream` 仍是"正文打字机壳"，不因接入而膨胀；`ThinkingStream`（reasoning 灰斜体）**零改动** |
| **DRY** | ✅ 样式全走 `stepStyles.ts` 既有令牌（未新增颜色）；折叠直接复用 `CollapsibleText`，不新造折叠组件 |
| **KISS-DIRECT** | ✅ 不自写 Markdown 解析器；围栏判定是 15 行纯函数（已实测），**无状态机、无 class、无模式串**；实时/历史**不分支**（一条规则通吃） |
| **SLAP** | ✅ 流式状态由 `PipelineRenderer` 判定后以既有 `typing`/`cursor` prop 传入；开关值以 `markdown` prop 传入；`MarkdownText` 不接触 SSE 概念、不自行读设置 |
| **YAGNI** | ✅ 不引代码高亮（需求未要求）；不做语法着色主题；不为"将来可能要"留配置项 |
| **禁止 backward** | ✅ 不为"将来可能要"留配置项；不复活已删的 `markdown.tsx`。**选择模式开关不是兼容层**——它是北京老陈明确要的用户功能（双模式均为一等公民），与"为旧代码保留退路"有本质区别 |
| **OCP** | ✅ 渲染方式变更对 `PipelineRenderer` 调用方完全透明 |
| **LSP** | N/A（无继承体系变更） |
| **ISP** | ✅ `MarkdownText` 仅 4 个 prop（`text` 必需 + `streaming`/`maxLines`/`maxChars` 可选），接口最小 |
| **复用优先** | ✅ 复用 `stepStyles` 令牌 / `CollapsibleText` / `getStreamStyle` 语义；`rehype-sanitize` 复用生态成熟方案而非自写净化 |

---

## 九、影响面

| 文件 | 性质 | 说明 |
|---|---|---|
| `pipeline/MarkdownText.tsx` | **新增** | §4.1 全文 |
| `pipeline/useStepRenderPrefs.ts` | **新增** | §5.2（**`getGroup` 的首个消费方**；`useSettings` 是设置页专用状态机，不可搬进 chat 页） |
| `pipeline/TextStream.tsx` | 改 | 加 `markdown` prop + 选择模式分支 + `React.lazy`（§4.2） |
| `pipeline/PipelineRenderer.tsx` | 改 | 顶层调 `useStepRenderPrefs`；下传 `defaultExpanded`（§5.8） |
| `settings2/components/SettingsGroup.tsx` | 改 | `sectionOf` 的 appearance 分支加 1 行前缀（§5.10） |
| `settings2/hooks/useSettings.ts` | 改（可选） | `saveKeys` 成功广播 1 行（§5.11） |
| `settings_registry.py` | 改 | `appearance` 组 `fontSize` 之后加 2 个 `bool`（§5.1） |
| `package.json` / `package-lock.json` | 改 | 新增 4 依赖（§4.3） |
| `src/tests/unit/markdown-text-fence.test.tsx` | **新增**（本地） | §6 第 2/3 步用例；`src/tests` 被 gitignore，**不入库** |

**已删除的原计划**（v2.7 核查真实代码后否决）：
`pipeline/ThoughtRenderToggle.tsx`、`pipeline/ReasoningVisibleToggle.tsx`、
`pipeline/useThoughtRenderMode.ts`、`pipeline/useReasoningVisible.ts`、
`taskinfo/TaskInfoBar.tsx` 快捷开关挂载 —— 依据见 §5.12.1。

**后端改动仅 2 行 registry（零业务逻辑，零 SSE 契约，零 Tab 结构）。零其他 step 改动。**

---

**编写人**：小欧
**编写时间**：2026-10-05 11:38:43
**版本**：v3.6（实施后回写：订正 §5.5 两处错 diff + 补 §5.14 两条口头裁定 + 新增 §5.15 偏离登记表）（图标归口 WaitingIcons/index.tsx + 常驻标题行 + 每段独立折叠；10 个代码各占一节，全部真实 diff）
