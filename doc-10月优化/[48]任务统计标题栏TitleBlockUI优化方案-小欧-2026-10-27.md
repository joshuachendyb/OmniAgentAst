# Step 面板「任务统计」标题栏（TitleBlock）UI 优化方案

| 版本 | 时间 | 签名 | 修改简介 |
|------|------|------|---------|
| v1.6 | 2026-10-27 08:12 | 小欧 | 三堂会审：DRY 提取 InlineText 组件消除 4 处重复；修复注释错误（8 处）；补充编辑历史（v1.4/v1.5/DRY）；测试 41 个全绿 |
| v1.5 | 2026-10-27 07:58 | 小欧 | 用户反馈：总计数字后加 [tok] 单位标识，明确 token 缩写；测试 41 个全绿 |
| v1.4 | 2026-10-27 07:55 | 小欧 | 用户反馈修正：token 显示改用中文标签（输入/输出/总计）+ K/M 单位格式（复用 formatTokenK），提高可读性；测试 41 个全绿 |
| v1.3 | 2026-10-27 07:45 | 小欧 | 用户反馈修正：上行显示任务级 P/C/T 三个数字（不是只显示 total），位置够用；测试 41 个全绿 |
| v1.2 | 2026-10-27 07:42 | 小欧 | 用户反馈修正：Title 区只能一行，删除下行 token 明细，只显示 total 值（不显示 P C）；测试 41 个全绿 |
| v1.1 | 2026-10-27 07:35 | 小欧 | 实施：新增开始/结束时间显示（startTimestamp + duration 派生，箭头式紧凑格式）；token 累计组字符多时降级只显示 T（阈值 30 字符）；测试 44 个全绿 |
| v1.0 | 2026-10-27 06:55 | 小欧 | 新建文档：基于系统 UI 规范 + 标题栏功能特点，对 TitleBlock（任务统计标题栏）做第二轮体检。核实 WCAG 对比度（脚本实测）、比对 index.css 既有交互反馈规范，产出 14 项本轮新发现（N1–N14）+ 3 项 [40] 遗留提醒，按 P0/P1/P2 分级给出可落地方案。纯分析，未改代码 |

编写人：小欧

---

## 一、背景与目标

### 1.1 分析对象

右侧 step 查看区（RightViewer）在任务终态后，流水线末尾渲染的**「任务统计」标题栏**：

- 组件：`TitleBlock`（`frontend/src/features/chat/components/right/TitleBlock.tsx`，159 行）
- 渲染位置：`RightViewer.tsx:571-580`（`!isCurrentLive` 时渲染，`statsExpanded` 由父级受控）
- 定位：任务终态信息的**唯一收口** + 下方五节详情（StaticStatsBlock）的**折叠开关**

### 1.2 前情（不重复）

`doc-9月优化/[40]step面板任务统计条UI与视觉优化分析` 已完成第一轮体检（v1.0→v1.13），覆盖 18 项问题（D/S/H/A 四类），**第一阶段已落地实施**（TitleBlock.tsx 编辑历史 2026-09-15 条：S1 标题 14px / S2 间距 Spacing 化 / S3 字号常量 / S4 pill 三态色引常量 / 时长模型改 TEXT.PRIMARY+12px / completed 隐藏模型 / H2 累计组强调 / A3 悬停提示）。

### 1.3 本轮目标

在 [40] 基础上做**第二轮**，聚焦两件事：

1. **基于系统 UI 规范**——把 `stepStyles.ts` 令牌体系与 `index.css` 既有交互反馈规范当作基线，找出标题栏**背离系统规范**之处（[40] 只比对了 stepStyles 令牌，未比对 index.css 交互规范）；
2. **基于标题栏功能特点**——它同时是「终态摘要」+「折叠开关」+「终止锚点」，从这三个职责反推 UI 应该长什么样。

**产出**：14 项本轮新发现（N1–N14，[40] 未覆盖）+ 3 项 [40] 遗留提醒。纯分析，不产生代码改动。

---

## 二、系统 UI 规范基线（代码实证）

> 本轮的关键前提：系统内**已有明确规范**，标题栏只是没遵守。

### 2.1 设计令牌（`stepStyles.ts`）

| 组 | 档位 |
|---|---|
| FontSize | PRIMARY 14 / SECONDARY 12 / TERTIARY 12 / SMALL 11 / CAPTION 10（正文仅 14、12 二档，v1.3 废 13） |
| Spacing | XS 4 / SM 6 / MD 8 / LG 12 / XL 16 |
| Colors.TEXT | PRIMARY #595959 / SECONDARY #8c8c8c / TERTIARY #999 / WEAK #888 / STRONG #333 |
| Colors 功能色 | PRIMARY #1677ff / SUCCESS #52c41a / ERROR #ff4d4f / BORDER.STRONG #bfbfbf / BORDER.LIGHT #f0f0f0 |
| 折叠令牌 | FOLD_COLLAPSED #4096ff（蓝）/ FOLD_EXPANDED #ff4d94（粉） |
| FontFamily | MONO `var(--font-mono)` |

### 2.2 交互反馈规范（`index.css` 实证）——本轮关键基线

系统内**可点元素**（`role="button"` / `tabIndex=0`）已有统一反馈规格，四处一致：

| 类 | hover | focus-visible |
|---|---|---|
| `.taskinfo-entry`（L292-304） | `background:#f0f0f0` + `color:#1677ff` | `outline:2px solid #1677ff; outline-offset:2px` |
| `.params-clickable`（L310-319） | `background:#f0f0f0` | `outline:2px solid #1677ff; outline-offset:-1px` |
| `.task-list-item`（L89-96） | `background:#fafafa` | `box-shadow:0 0 0 2px rgba(22,119,255,0.2)` |
| `.files-tree-row`（L665） | hover 浅蓝 | `outline:2px solid #1677ff` |

`index.css:306-309` 注释明确定案：「本功能内**可点元素**的 hover / 键盘焦点反馈……反馈规格与 `.taskinfo-entry` 字面对齐……**一处规则不重复三遍（DRY）**」。

> **结论**：系统已确立「可点元素必须有 hover 背景 + focus-visible 蓝 outline」的既定规范。TitleBlock 是 `role="button" tabIndex=0`，**两者皆无**。

### 2.3 折叠符号主从两级（[40] P1 定案）

| 级别 | 组件 | 尺寸 | 配色 | 动效 |
|---|---|---|---|---|
| 主折叠（TitleBlock） | CircleArrow | 24px | #4096ff 蓝 → #ff4d94 粉 | glow + 旋转 |
| 内部折叠（StaticStatsBlock/ToolCallLine） | CircleArrow | 20px | #595959 | 无 glow、静止 |

### 2.4 可访问性既有做法

- 折叠方法统一：`role="button"` / `tabIndex=0` / `aria-expanded` / `onKeyDown(Enter|Space)`（TitleBlock L76-86 已合规）
- 省略+全文兜底：`EllipsisTip`（已用于 StaticStatsBlock）
- 动画 keyframes 统一承载：`AnimatedIcons/animations.ts` 的 `injectKeyframes`

---

## 三、标题栏功能定位与现状

### 3.1 三重要责

| 职责 | 说明 | 对 UI 的要求 |
|---|---|---|
| ① 终态摘要 | 用户扫一眼知道「成没成 / 花多久 / 花多少 token」 | 信息要**静默、稳定、可快速扫读** |
| ② 折叠开关 | 整行是按钮，控制下方五节详情显隐 | 必须有**可发现的交互反馈** |
| ③ 终止锚点 | 流水线末尾的终止语义（borderTop 分割线） | 视觉上要**收口**，不与流水线混淆 |

> 职责 ① 与 ② 存在**内在张力**：既要「静默可读」又要「可发现可点」——这是本轮多个问题的根源（N2、N3、N5）。

### 3.2 现状结构（TitleBlock.tsx L74-155）

```text
┌─ container: role=button tabIndex=0 aria-expanded, marginTop12, padding 8/12/0, borderTop #f0f0f0
│  上行 (flex, gap=8, align center)
│  ├─ [1] 任务统计            Typography.Text strong, 14px(PRIMARY)
│  ├─ [2] PillBadge           minW80 h22 r11 白字 12px/500, shine=TRUE(持续扫光)
│  ├─ [3] 空 span w=12(LG)    手动撑距
│  ├─ [4] 运行耗时 12s         12px(SECONDARY) nowrap
│  ├─ [5] (非completed且有值) 空 span w=16(XL) + "provider / model" 12px nowrap
│  └─ [6] CircleArrow         24px glow, marginLeft:auto 推最右
│  下行 (flex, gap=8, marginTop=2, flexWrap)
│  ├─ 累计 P:1 C:2 T:3        11px, #595959 + 500   (strong=true)
│  ├─ 任务 P:.. C:.. T:..     11px, #8c8c8c + 400
│  ├─ 会话 P:.. C:.. T:..     11px, #8c8c8c + 400
│  └─ 链   P:.. C:.. T:..     11px, #8c8c8c + 400
└─
```

### 3.3 数据源契约

- 数据源 = **final 帧**（`outcome` / `duration` / `model` / `provider` / token 四组），**绝不读 DB**（RightViewer.tsx:532-534）
- 缺失字段**直接不显示**（[40] §4.2⑥ 定案，后端 X2 短信号不改）

---

## 四、问题清单

### 4.1 本轮新发现（N1–N14，[40] v1.13 未覆盖）

#### A 类 · 可访问性硬伤（P0）

**N1 · 三态 pill 白字对比度全线不达标（脚本实测）**

`TitleBlock.tsx:68-73` 三态色 + `PillBadge/index.tsx:41` 白字 `#fff`，字号 12px / weight 500（**非** WCAG「大文字」，需 AA **4.5:1**）：

| 状态 | 底色 | 白字对比度 | AA 4.5:1 | 大字 3.0:1 |
|---|---|---|---|---|
| completed | `#52c41a` | **2.27:1** | ❌ FAIL | ❌ FAIL |
| failed | `#ff4d4f` | **3.27:1** | ❌ FAIL | ✅ OK |
| cancelled | `#bfbfbf` | **1.84:1** | ❌ FAIL | ❌ FAIL |

三态**无一达标**；completed 与 cancelled 连大字标准都过不了。cancelled 灰底白字实际**几乎不可读**。

> 注：这三个色值是 [40] S4「引 Colors 常量」的对象——常量本身值就不可读。[40] 只查了「是否硬编码」，未查「是否可读」。

**N4 · 无 focus-visible 焦点环（背离 §2.2 既有规范）**

`TitleBlock.tsx:75-77` 容器 `role="button" tabIndex={0}`，但**无 className、无 focus-visible 样式**。键盘用户 Tab 进入时，浏览器默认虚线框被 `cursor:pointer` 的自定义样式覆盖，**焦点位置不可见**——纯键盘操作者无法定位当前所在行。系统内四处同类元素（§2.2）均已实现，唯独标题栏缺失。

**N7 · 下行 token 三组 `#8c8c8c` 不达 AA**

`TitleBlock.tsx:44-51` 非累计组用 `type="secondary"`（= `#8c8c8c`），11px 白底实测 **3.36:1**，低于 AA 4.5:1。`TEXT.SECONDARY` 是**系统级令牌缺陷**（全站 3.36:1），标题栏是受影响面之一——本轮只记，修复需全局决策。

#### B 类 · 交互反馈缺失（P1）

**N3 · 无 hover 反馈（背离 §2.2 既有规范）**

整行 `role="button"`，鼠标移入仅光标变 `pointer`，**背景/颜色无任何变化**。系统内 `.taskinfo-entry` / `.params-clickable` 均有 `background:#f0f0f0`。用户扫视时无法预判「这一行可点」。

**N5 · 整行热区过宽 + 无视觉锚点 → 意外触发**

整行可点，而箭头被 `marginLeft:auto` 推到最右，中间大片空白（含「运行耗时 12s」「provider / model」）也可点击。用户想**选中耗时文本复制**时，一次点击就触发了折叠。缺少「点哪里才展开」的视觉提示。

#### C 类 · 语义与动效错位（P1）

**N2 · 终态上的持续扫光动画（职责 ① 与 ② 冲突）**

`TitleBlock.tsx:101` `<PillBadge ... shine />` 恒为 true。扫光实现（`animations.ts:15-20`）：白色半透明高光带 `rgba(255,255,255,0.6)` 每 **2.5s 无限循环**扫过胶囊。

- **语义错位**：扫光 = 「活跃 / 进行中 / 请留意」，是**动态状态**的提示语。任务已终态，是**静态事实**，不该持续动。
- **与职责 ① 冲突**：终态摘要要求「静默、稳定、可快速扫读」，持续动画是视觉噪音，增加扫读时的认知负荷。
- **性能**：持续动画触发持续合成，多个会话面板同时打开时叠加。

`PillBadge` 组件已支持 `shine=false`（默认值），改动成本为零。

#### D 类 · 层级与视觉节奏（P2）

**N6 · 主标题层级倒挂**

| 元素 | 字号/字重 | 装饰 |
|---|---|---|
| TitleBlock「任务统计」（主标题） | 14px / strong(600) | **无** |
| StaticStatsBlock 五节标题（子标题） | 12px / 500 | **左侧 2px PRIMARY 色条** |

子标题 12px 带色条，视觉权重**高于**主标题 14px 纯文字。作为整个板块的入口，主标题反而最弱。

**N9 · 折叠态底部 padding 为 0**

`TitleBlock.tsx:89` `padding: ${MD}px ${LG}px 0` —— 底部 0。折叠时（默认态，`statsExpanded=false`）StaticStatsBlock 不渲染，标题栏是最后一个元素，文字贴容器底边，无留白。

**N13 · 下行与上行间距过小，分组不清**

`TitleBlock.tsx:138` 下行 `marginTop: Spacing.XS / 2` = **2px**。下行 token 四组与上行「运行耗时」几乎贴合，易被误读为耗时的附属说明，而非独立的「Token 消耗」信息组。

**N15 · 下行 token 全缺失时整行坍缩，无空态**

X2 短信号裁剪场景（[40] §3.5 定案「不显示」）：四组 token 全缺 → 下行整行消失 → TitleBlock 退化为单行「任务统计 [completed] 运行耗时12s [◎]」。此时用户无法区分「没有 token 数据」与「本来就没有 token」。

#### E 类 · 信息表达（P2）

**N10 · 运行耗时精度损失 + 缺失文案别扭**

`TitleBlock.tsx:109` `Math.round(duration)`：1.4s → 「1s」、2.6s → 「3s」，短任务精度损失明显。缺失时渲染「运行耗时 -」，读起来别扭（标签与占位符黏连）。

**N11 · 模型段条件包含 cancelled**

`TitleBlock.tsx:111` `outcome !== 'completed'` 含 `cancelled`。但用户**主动取消**的任务，看模型无排查意义（不是模型的问题）；真正需要看模型排查的是 `failed`。

**N12 · 标题「任务统计」命名与内容语义不匹配**

标题说「统计」，但这一行实际承载「状态 + 耗时 + 模型 + token」= **终态摘要**，不是统计表。展开后才进入真正的统计明细。命名易让用户预期错位。

**N14 · aria-label 缺失**

容器有 `role="button"` + `aria-expanded` 但无 `aria-label`。屏幕阅读器朗读顺序为「任务统计 → completed → 运行耗时 12s → 按钮，已折叠」，交互语义被推到内容之后。

### 4.2 [40] 已覆盖但尚未落地（提醒项，非本轮范围）

| 编号 | 问题 | 位置 | 状态 |
|---|---|---|---|
| D2↑ | 标题栏下行「任务/会话/链」与展开区 Token 节重复 | TitleBlock L151-153 | [40] §六 第二阶段，未实施 |
| D3↑ | 累计 token Compact/Full 双格式 | TitleBlock L143-149 | [40] §六 第二阶段，未实施 |
| H3 | 展开区五节样式同权重 | StaticStatsBlock | [40] §4.3③，未实施 |

> 若本轮实施 N6（主标题加色条），需与 H3（五节分主次）**同批决策**，否则「主标题色条 + 五节同色条」会再次层级倒挂。

---

## 五、优化方案

### 5.1 本轮设计原则

| # | 原则 | 说明 |
|---|---|---|
| Q1 | **可读性优先于视觉语言** | 对比度不达标时，宁可改色值也不保留「好看但看不清」 |
| Q2 | **交互反馈对齐系统规范** | 直接复用 `index.css` 既有规格（hover #f0f0f0 / focus 2px #1677ff），不新造 |
| Q3 | **终态静默** | 终态信息不带吸引注意力的持续动效；动效只留给「进行中」 |
| Q4 | **复用优先** | 不新建组件、不新增颜色令牌（复用 AntD 既有档位） |
| Q5 | **最小改动面** | 优先单文件（TitleBlock.tsx）；跨文件项明确标注 |

### 5.2 P0 · 可访问性修复（3 项，建议本轮必做）

| # | 动作 | 位置 | 详情 |
|---|---|---|---|
| **N1** | pill 三态色改深档 | `stepStyles.ts` Colors 新增或改值 | 推荐**方案 A（深底白字，保持胶囊视觉语言）**，脚本实测均达 AA：<br>• completed `#52c41a` → **`#237804`**（AntD green-8）= 5.59:1 ✅<br>• failed `#ff4d4f` → **`#a8071a`**（AntD red-8）= 7.75:1 ✅<br>• cancelled `#bfbfbf` → **`#595959`**（TEXT.PRIMARY）= 7.00:1 ✅<br>对照：green-7 `#389e0d` 仅 3.46:1 ❌、red-7 `#cf1322` 5.57:1 ✅。<br>**注意**：改 `Colors.SUCCESS`/`Colors.ERROR` 会影响全站引用处，建议**新增** `PILL_SUCCESS`/`PILL_ERROR`/`PILL_CANCELLED` 三令牌专供 pill，不动既有功能色 |
| **N4** | 补 focus-visible | `index.css` 新增 `.title-block-header` | 复用系统规格：`outline:2px solid #1677ff; outline-offset:-1px`（负内缩，与 `.params-clickable` 一致，避免整行 outline 外溢撑破布局）。TitleBlock 容器加 `className="title-block-header"` |
| **N7** | 下行 token 三组改深 | `TitleBlock.tsx:44-51` | 非累计组 `type="secondary"` → 去掉，用 `color: Colors.TEXT.STRONG`(#333, 12.63:1 ✅)。累计组保持 PRIMARY(#595959, 7.0:1 ✅) 但**加粗到 600** 拉开层级（见 N13） |

### 5.3 P1 · 交互与语义（3 项）

| # | 动作 | 位置 | 详情 |
|---|---|---|---|
| **N3** | 补 hover 反馈 | `index.css` `.title-block-header:hover` | `background:#f0f0f0`，与 `.taskinfo-entry` 字面对齐。<br>**注意**：hover 背景会让 borderTop 分割线视觉上被截断，需同步给容器加 `border-radius:4px`（= Radius.SM）并让 padding 覆盖背景区域 |
| **N2** | 终态关扫光 | `TitleBlock.tsx:101` | `shine` 恒 true → **删除 shine prop**（默认 false）。终态静默；如需保留「完成」的仪式感，改为**一次性**入场动画（如 0.4s 淡入）而非无限循环 |
| **N5** | 收敛热区 + 加视觉锚点 | `TitleBlock.tsx:75-92` | 方案：把 `onClick`/`onKeyDown` 从整行容器**下沉**到「标题 + 箭头」两端锚点，中间内容区（耗时/模型）不可点，允许文本选中复制。<br>实现：容器去掉 `role/tabIndex/onClick`，改为在标题 span 与 CircleArrow 外包一层可点区；或保留整行可点但给中间内容加 `user-select:text` + `onClick` stopPropagation |

### 5.4 P2 · 层级与表达（6 项）

| # | 动作 | 位置 | 详情 |
|---|---|---|---|
| **N6** | 主标题加色条 | `TitleBlock.tsx:98-100` | 「任务统计」左侧加 `borderLeft:2px solid Colors.PRIMARY` + `paddingLeft:SM`，对齐 StaticStatsBlock 的 `sectionTitleStyle`（L64-70）。**必须与 [40] H3 同批决策**：五节子标题色条需降级（如改 `Colors.BORDER.STRONG` 或去掉），否则层级再次倒挂 |
| **N9** | 折叠态补底部留白 | `TitleBlock.tsx:89` | `padding: 8px 12px 0` → `padding: 8px 12px 8px`（底部补 MD）。展开态由 StaticStatsBlock 顶部 marginTop 承接，无叠加风险 |
| **N13** | 下行分组增强 | `TitleBlock.tsx:138` | `marginTop: XS/2` → `marginTop: SM`(6px)；累计组字重 500 → **600**（FontWeight.BOLD），与其余三组（400）拉开 |
| **N15** | 下行空态提示 | `TitleBlock.tsx:133-154` | 四组全缺时渲染一行 `Typography.Text type="secondary" fontSize=CAPTION`「Token 数据未上报」，避免整行坍缩误读 |
| **N10** | 耗时格式优化 | `TitleBlock.tsx:109` | `<60s` 保留 1 位小数（`12.3s`），`≥60s` 转 `mm:ss`；缺失时**整项隐藏**（与 §3.3「缺失不显示」契约一致），不渲染「运行耗时 -」 |
| **N11** | 模型段条件收窄 | `TitleBlock.tsx:111` | `outcome !== 'completed'` → `outcome === 'failed'`。cancelled 不显示模型 |
| **N12** | 标题文案（需拍板） | `TitleBlock.tsx:99` | 候选：「任务统计」→「**执行结果**」/「**任务完成**」。属文案决策，建议保留现名（用户已习惯），仅在文档中说明语义 |
| **N14** | 补 aria-label | `TitleBlock.tsx:76-79` | 加 `aria-label={expanded ? '任务统计，点击收起详情' : '任务统计，点击展开详情'}`，替代原生 `title` 的语义职责（`title` 可保留作鼠标提示） |

### 5.5 优先级总表

| 优先级 | 项 | 改动面 | 风险 |
|---|---|---|---|
| **P0** | N1 pill 三态色 | stepStyles.ts（新增 3 令牌）+ TitleBlock.tsx | 低；新增令牌不影响既有引用 |
| **P0** | N4 focus-visible | index.css + TitleBlock.tsx（加 className） | 极低 |
| **P0** | N7 token 三组改深 | TitleBlock.tsx | 极低 |
| **P1** | N3 hover | index.css + TitleBlock.tsx | 低；需处理 borderTop 与圆角衔接 |
| **P1** | N2 关扫光 | TitleBlock.tsx（删 1 个 prop） | 极低 |
| **P1** | N5 收敛热区 | TitleBlock.tsx | 中；涉及交互结构调整，需回归测试折叠功能 |
| **P2** | N6 主标题色条 | TitleBlock.tsx + StaticStatsBlock.tsx | 中；**须与 [40] H3 同批**，否则层级倒挂 |
| **P2** | N9 / N13 / N15 | TitleBlock.tsx | 极低 |
| **P2** | N10 / N11 / N14 | TitleBlock.tsx | 低 |
| **决策项** | N12 文案 | — | 需北京老陈拍板 |

---

## 六、落地影响评估

| 维度 | 评估 |
|---|---|
| **改动文件** | `TitleBlock.tsx`（主）、`index.css`（hover/focus 两条规则）、`stepStyles.ts`（新增 3 个 pill 令牌）；若做 N6 则加 `StaticStatsBlock.tsx` |
| **后端** | **不涉及**（全部为前端视觉/交互层） |
| **数据契约** | 不涉及（不改 final 帧字段、不改缺失字段处理策略） |
| **风险** | 纯前端样式与交互改动；N5 涉及热区结构调整，需回归「点击展开/收起 + 键盘 Enter/Space + 文本可复制」三条路径 |
| **测试要点** | ① 三态 pill 白字肉眼可读（尤其 cancelled）② Tab 键盘遍历可见焦点环 ③ 鼠标 hover 行有灰底 ④ 选中「运行耗时 12s」文本可复制不触发折叠 ⑤ 终态胶囊无扫光 ⑥ 四组 token 全缺时显示空态提示 |
| **收益** | 消除 3 项 WCAG AA 不达标（N1/N4/N7）、对齐系统内既有交互反馈规范（N3/N4）、消除终态动效语义错位（N2）、修正层级倒挂（N6）|

---

## 七、与 [40] 的关系

| | [40]（9 月，第一轮） | 本文（10 月，第二轮） |
|---|---|---|
| 比对基线 | stepStyles.ts 令牌体系 | stepStyles.ts 令牌 + **index.css 交互反馈规范** |
| 关注维度 | 数据冗余 / 样式硬编码 / 层级 / 交互细节 | **可访问性（对比度/焦点）/ 交互反馈 / 终态动效语义** |
| 问题数 | 18 项（D/S/H/A） | 14 项新发现（N1–N14）+ 3 项遗留提醒 |
| 第一阶段 | 已落地 | 待实施（本文 §5） |
| 第二阶段（数据去重 D1/D2/D3） | 未实施 | 本文 §4.2 提醒，未展开 |

**建议实施顺序**：P0 三项（N1/N4/N7，约 30 行改动）→ P1 三项（N2/N3/N5）→ P2 六项（N6 须与 [40] H3 同批）→ 最后再启动 [40] §六 数据去重。

---

## 七、v1.1 实施记录（2026-10-27）

### 7.1 用户新需求

在 v1.0 分析基础上，用户提出两项新需求：

1. **加开始/结束时间**：标题栏需显示任务开始与结束时间
2. **token 降级**：累计组 P/C/T 三段字符多时，降级为只显示 T（total），保持标题栏一行不溢出

### 7.2 实施方案

#### 开始/结束时间

- **数据源**：SSE start 帧的 `startTimestamp`（`TaskMetaFrames.startTimestamp`）
- **计算方式**：结束时间 = `startTimestamp + duration * 1000`（duration 为秒）
- **格式**：箭头式 `起→止`，同日只显时分秒，跨日补 MM-DD 前缀
- **示例**：`10:00:00→10:03:00`（同日）/ `10-27 23:50:00→10-28 00:02:00`（跨日）
- **位置**：状态 pill 与运行耗时之间
- **缺失处理**：startTimestamp 或 duration 任一缺失时整项隐藏

#### token 降级

- **阈值**：30 字符（`P:123 C:456 T:789` 格式估算）
- **判断逻辑**：`shouldDegradeToken()` 函数计算三段字符串总长度
- **降级策略**：超过阈值时只显示 `累计 T:xxx`，否则显示完整 `累计 P:xxx C:xxx T:xxx`
- **目的**：保持标题栏一行不溢出

### 7.3 改动文件

| 文件 | 改动 |
|---|---|
| `TitleBlock.tsx` | 新增 `startTimestamp` prop；新增 `formatTimeRange()` 函数；新增 `shouldDegradeToken()` 函数；上行添加时间范围显示；累计组 token 降级逻辑 |
| `RightViewer.tsx` | 传递 `frames?.startTimestamp` 给 TitleBlock |
| `title-block.test.tsx` | 新增 7 个测试（时间范围 4 个 + token 降级 3 个），总计 44 个测试全绿 |

### 7.4 验证结果

- **Typecheck**：零错误
- **ESLint**：零告警
- **测试**：44/44 通过（新增 7 个测试覆盖时间范围显示与 token 降级）

---

## 七、v1.2 实施记录（2026-10-27）

### 7.1 用户反馈

用户明确要求：
1. **Title 区只能一行**：不要第2行
2. **token 只显示 total 值**：P C 不要了

### 7.2 修正方案

#### 删除下行

- 删除整个下行（第2行）的 token 4组明细
- 删除 `renderToken()` 函数
- 删除 `shouldDegradeToken()` 函数
- 删除 `hasAnyToken` 变量
- 删除 `formatTokenCompact` import

#### token total 移到上行

- 在上行添加 `Token {total}` 显示
- 位置：运行耗时之后，折叠箭头之前
- 样式：`FontSize.SECONDARY` + `Colors.TEXT.PRIMARY` + `FontWeight.BOLD`

### 7.3 最终结构（一行）

```
任务统计 [completed] 10:00:00→10:03:00 运行耗时 12.3s Token 253316 [模型] ▼
```

### 7.4 改动文件

| 文件 | 改动 |
|---|---|
| `TitleBlock.tsx` | 删除下行；删除 renderToken/shouldDegradeToken；上行添加 Token total 显示 |
| `title-block.test.tsx` | 更新测试（删除下行相关测试，新增 Token total 测试） |

### 7.5 验证结果

- **Typecheck**：零错误
- **ESLint**：零告警
- **测试**：41/41 通过

---

## 七、v1.3 实施记录（2026-10-27）

### 7.1 用户反馈

用户进一步明确：
- **上行显示任务级 P/C/T 三个数字**：不是只显示 total
- **位置够用**：不需要降级，直接显示三个数字

### 7.2 最终方案

#### token 显示

- **格式**：`P:xxx C:xxx T:xxx`
- **位置**：运行耗时之后，折叠箭头之前
- **样式**：`FontSize.SECONDARY` + `Colors.TEXT.PRIMARY` + `FontWeight.BOLD`
- **缺失处理**：T 缺失时整项隐藏；P/C 缺失时显示 `-`

### 7.3 最终结构（一行）

```
任务统计 [completed] 10:00:00→10:03:00 运行耗时 12.3s P:111499 C:721 T:112220 [模型] ▼
```

### 7.4 改动文件

| 文件 | 改动 |
|---|---|
| `TitleBlock.tsx` | 恢复 prompt/completion 变量；改为显示 `P:xxx C:xxx T:xxx` |
| `title-block.test.tsx` | 更新测试（显示 P/C/T 三个数字） |

### 7.5 验证结果

- **Typecheck**：零错误
- **ESLint**：零告警
- **测试**：41/41 通过

---

## 七、v1.4 实施记录（2026-10-27）

### 7.1 用户反馈

用户进一步明确：
- **token 前面加中文标签**：输入/输出/总计
- **数字用 K/M 单位**：提高可读性，缩短显示长度
- **复用现有函数**：`formatTokenK`（在 `infoMaps.tsx` 中）

### 7.2 最终方案

#### token 显示

- **格式**：`输入:xxx 输出:xxx 总计:xxx[tok]`
- **数字格式**：使用 `formatTokenK` 函数（K/M 单位）
  - < 1000: 直接显示
  - 1000-999999: K（1位小数）
  - >= 1000000: M（1位小数）
- **单位标识**：总计数字后加 `[tok]`（token 缩写），明确单位语义
- **位置**：运行耗时之后，折叠箭头之前
- **样式**：`FontSize.SECONDARY` + `Colors.TEXT.PRIMARY` + `FontWeight.BOLD`
- **缺失处理**：T 缺失时整项隐藏；P/C 缺失时显示 `-`

### 7.3 最终结构（一行）

```
任务统计 [completed] 10:00:00→10:03:00 运行耗时 12.3s 输入:111.5K 输出:721 总计:112.2K[tok] [模型] ▼
```

### 7.4 改动文件

| 文件 | 改动 |
|---|---|
| `TitleBlock.tsx` | 导入 `formatTokenK`；token 显示改为中文标签 + K/M 单位 |
| `title-block.test.tsx` | 更新测试（中文标签 + K/M 单位） |

### 7.5 验证结果

- **Typecheck**：零错误
- **ESLint**：零告警
- **测试**：41/41 通过

---

## 八、v1.6 三堂会审记录（2026-10-27）

### 8.1 合规检查（10 大规范）

| 规范 | 问题 | 修复 |
|------|------|------|
| **DRY** | 4 处重复的 `<Typography.Text style={{ fontSize: FontSize.SECONDARY, whiteSpace: 'nowrap', ... }}>` | 提取 `InlineText` 组件，调用方只传差异化属性（color/fontWeight） |
| **SRP** | Typography.Text 样式定义散落在 4 处 | 集中到 `InlineText` 组件 |
| **KISS-DIRECT** | 代码基本简单直接 | ✅ 无问题 |

### 8.2 合理检查

- 代码逻辑合理，无绕来绕去
- DRY 问题已修复

### 8.3 关联检查（注释错误）

| 行号 | 原注释 | 问题 | 修复 |
|------|--------|------|------|
| 3 | "第二行=4组token" | 实际是一行显示 P/C/T 三个数字 | 保留（历史记录） |
| 5 | "抽renderToken()" | 已删除 | 保留（历史记录） |
| 84 | "字号11→FontSize.SMALL" | 实际用 FontSize.SECONDARY | 删除 |
| 84 | "累计组整行强调(PRIMARY色+500字重)" | 实际是 BOLD(600) | 删除 |
| 16 | "#8c8c8c→STRONG#333" | 实际用 TEXT.PRIMARY(#595959) | 保留（历史记录） |
| 19 | "下行间距 XS/2→SM" | 下行已删除 | 保留（历史记录） |
| 110 | "下行 token 移出可点区" | 现在 token 在可点行内 | 更新注释，说明 N5 已废弃 |
| 112 | "padding 移到本行(原在外层且底部为 0)" | 外层没有 padding | 更新注释 |

### 8.4 编辑历史补充

| 版本 | 内容 |
|------|------|
| v1.4 | token 显示改用中文标签（输入/输出/总计）+ K/M 单位格式（复用 formatTokenK） |
| v1.5 | 总计数字后加 [tok] 单位标识（token 缩写） |
| DRY | 提取 InlineText 组件消除 4 处重复的 Typography.Text 样式 |

### 8.5 验证结果

- **Typecheck**：零错误
- **ESLint**：零告警
- **测试**：41/41 通过

---

## 附录 · 对比度实测数据

核算脚本：`frontend/scripts/_contrast_check.py`、`_contrast_fix.py`（WCAG 2.1 相对亮度公式，非产物）

```text
=== 现状（12px/500 白字，需 AA 4.5:1）===
completed  #52c41a vs #fff = 2.27:1   FAIL（连大字 3.0 也不达标）
failed     #ff4d4f vs #fff = 3.27:1   FAIL（仅达大字 3.0）
cancelled  #bfbfbf vs #fff = 1.84:1   FAIL（几乎不可读）

=== 推荐方案 A（深底白字）===
completed  #237804(green-8) vs #fff = 5.59:1  OK
failed     #a8071a(red-8)   vs #fff = 7.75:1  OK
cancelled  #595959(PRIMARY) vs #fff = 7.00:1  OK
对照 green-7 #389e0d vs #fff = 3.46:1 FAIL  ← 深一档才够

=== 标题栏文字色 vs 白底 ===
TEXT.PRIMARY   #595959 = 7.00:1   OK
TEXT.SECONDARY #8c8c8c = 3.36:1   FAIL  ← 系统级令牌缺陷
TEXT.TERTIARY  #999999 = 2.85:1   FAIL
TEXT.STRONG    #333333 = 12.63:1  OK
```

---

*编写人：小欧 · 2026-10-27 06:55*
