# [29] Step页面Observation工具参数区UI布局视觉优化-设计方案-小欧-2026-10-13

创建时间：2026-10-13 08:26:25
更新时间：2026-10-13 09:58:45
版本：v2.3
编写人：小欧

**版本历史**

| 版本 | 时间 | 编写人 | 修改说明 |
|---|---|---|---|
| v1.0 | 2026-10-13 08:26:25 | 小欧 | 新建（北京老陈令：分析 Step 页面 observation 工具结果展开区参数区UI渲染缺点，出布局视觉优化方案）。三章结构：问题分析 / 优化问题解决方案 / 实施代码详细设计说明 |
| v1.1 | 2026-10-13 08:50:40 | 小欧 | 三项裁定落地并重写第二三章：①**浮层定位由"取代展开区"改为"与展开区并存"**——展开区保留并改 **戊·JSON树** 渲染，浮层另挂在结果区之后由按钮触发；②浮层双视图定案 **乙·分组卡片（默认）+ 甲·规格表（可切换）**，面板头 Segmented 切换、localStorage 记忆；③浮层内不再二次折叠，打开即全量、超长内部滚动。补充 v1.0 未覆盖的历史沿革（参数区显示数量的两代决策）与内联区高度量化 |
| v1.2 | 2026-10-13 08:57:21 | 小欧 | 全文 10 遍一致性核查，订正 13 处不一致 + 落 D1 裁定。①**行高口径统一为 16px**（项目规则「字号+4」），量化全改：`write` 5400px→**112px**（降 97.9%）、`find` 414→384px；②**删 3 个与既有令牌同值的新增令牌**（`PARAM_VALUE`/`BG.PARAM_PANEL`/`BORDER.PARAM_PANEL`），改直接复用，§3.4.3 留核查结论表；③删 `LineHeight` 新组，按既有内联模式；④**D1 裁定为乙**：浮层触发按钮**固定在工具行内**，不随展开态移动；⑤验收标准编号改前缀 `T1-T17`（避与 §2.5 视觉清单 `V1-V8` 同号）；⑥删 §3.5.1 残留面板底栏；⑦修 §3.4.1 标量键折叠表述矛盾、§3.8 指代错误、"顺带解决"漏列、展开区/浮层口径差异未说明、60 字符估算偏差、并行量化误用 write 专属值 |
| v1.3 | 2026-10-13 09:01:09 | 小欧 | 北京老陈追问"收起行三个部分"时自查出**第 15 处不一致**（§3.6 文字写「参数按钮在箭头之前」、§3.9 示意图画「在箭头之后」）。**D2 裁定为乙**：收起态一行顺序定稿 `内容信息 │ ▸折叠箭头 │ ⚙参数按钮`，§3.6 代码块注释 + 新增"收起态一行三部分与顺序"结构图、§2.2/§3.9 示意图、§3.10 留档全部同步；并补定**参数按钮不带自带箭头**，开合以底色标识（关 `TEXT.SECONDARY` / 开 `PRIMARY`），避免与折叠箭头混淆成两级折叠 |
| v1.4 | 2026-10-13 09:01:09 | 小欧 | **D3 裁定**：浮层触发按钮文案由 `参数` 改为 **`浮层参数`**。理由：`参数` 二字已被「就地展开区（JSON 树）」占用，同名会让用户误认二者为同一物。§2.2 示意、§3.6 代码块注释 + 三部分结构图 + 图标规格、§3.9 两处示意、T18/T19 验收项、§3.10 留档全部同步；新增 T21 验收项（按钮文案不得退化为裸标签 `参数`） |
| v1.5 | 2026-10-13 09:07:05 | 小欧 | 北京老陈指令「①决策是否记录到第2章 ②§2.2 内加设计决策表 ③再读10遍查一致性」。①**新增 §2.2.1 设计决策汇总表**（DC-01~DC-18 全量裁定，声明"正文与本表冲突以本表为准"）与 **§2.2.2 被否决方案留档**（11 项，防重复讨论）——此前决策散落各节、无汇总，是本章最大缺口；二轮 10 遍核查查出并订正 **11 处**：③"四组"与 5 行分组表自相矛盾（4 处）→ 统一为**五类**并补 §2.3.2 判定优先级链 + 路径特征细则；④分组判定优先级未定义（长路径可能被误分）→ 定优先级链"正文载荷→开关→路径→编码→其他"，命中即止；⑤`Size.*` 命名与既有 `BorderWidth`/`FontSize` 风格脱节 → 补命名说明并新增 `MIN_W`；⑥`HUGE_VALUE_CHARS` 混入设计令牌 → 降为组件模块级 const（YAGNI）；⑦浮层容器选型未定且 props 冗余 `anchorRect` → 定案 antd `Popover`，改 `anchorEl`，并补**窄屏口径**与**与 HITL 模态框的层级关系**；⑧JSON 树内长值是否截断未定义 → 定"折叠态单行省略、展开态不截断"，并声明与浮层 200 字阈值**是两套口径**；⑨§3.4.1 示例只列 2 键无说明，易误读为只渲染 2 键 → 加注；⑩§3.5.5 与 §2.3.3 重复且未标关系 → 加交叉引用注；⑪T13 未指明在哪个载体验证 → 明确"展开区与浮层均" |
| v1.6 | 2026-10-13 09:11:58 | 小欧 | 落 U1/U2/U3 三项未决裁定，并**由此带出一个新设计点**（展开区 JSON 树原设计无复制按钮）。**DC-15 嵌套深度不设上限**——北京老陈：「为什么要限制」，深度失控由每层展开体限高 240px 控制而非层级裁剪；**DC-18 两态互不牵连**——北京老陈：「两个各自独立 不互相牵连」，§3.2 补两态独立性对照表；**DC-16 浮层复制 = `key=value` 逐行**、**DC-17 展开区树复制 = 格式化 JSON**（DC-17 新增树头 `⧉` 按钮）——两者语义分立互补。同步 §2.1 关键约定 +2 条、§2.4 S5/S7、§2.7 I4 拆为 I4a/I4b 并新增 I7、§3.1 文件清单第 1 行、§3.4 补树头结构图、§3.5.5、验收新增 T22~T25。**文尾落款时间同步为 09:11:58**（v1.5/v1.6 曾漏同步，一并订正） |
| v1.7 | 2026-10-13 09:28:03 | 小欧 | 北京老陈令「UI视觉一致性检查与系统整体风格一致」。三堂会审挖出 11 处视觉不一致——**不新增章节，全部改写进设计原位**：①**复用 `CopyButton.tsx`**（删自造 `⧉`）；②**删 `Colors.JSON.*` 三语法色**（改 `TEXT.SECONDARY`/`TEXT.STRONG` 两档，`MarkdownText` 代码块观感对齐）；③**壳改 `FloatingEntry`**（删自建浮层与 a11y，白拿焦点管理）；④**分类色条全改 `BORDER.*` 中性灰阶**（语义色保留给状态）；⑤**折叠切换对齐 `CircleArrow(14,PRIMARY)`+「展开/收起」**；⑥**窄屏接系统断点矩阵**；⑦**图标改 antd `CodeOutlined`**（`GearIcon` 语义=等待中）；⑧**热区复用 `.taskinfo-entry`**；新增 DC-19~DC-22、否决清单 +6、验收 T26~T32 |
| v1.8 | 2026-10-13 09:36:18 | 小欧 | 三轮 10 遍全节通读核查，查出 **6 组 13 处**全部订正（致命 2 组）：①**`ParamsPanel` 传了已删除的 `open` prop**（§3.5 已删而 §3.6 还传，编译不过）→ §3.6 改写开合归属说明，新增 T33 编译零错验收；②「JSON 语法着色」残留 2 处（§2.2 顺带解决 + §2.5 V1）→ 改双色阶；③自造 `⧉` 残留 6 处（S5/I4b/DC-17/T14/T23/U3/示意）→ 全部改为复用 `CopyButton`；④DC-12「底色」vs §3.6/T20「文字色」→ 统一文字色；⑤`role="dialog"` 归属未同步（§2.3.1/I6 自建）→ 改 `FloatingEntry` 提供；⑥**`CopyButton` 是 `position:absolute`**（放面板头会压住标题）→ 加 `inline?: boolean` 可选 prop（默认 false 既有调用零变化，面板头传 `inline`）。验收新增 T33/T34 |
| v1.9 | 2026-10-13 09:36:18 | 小欧 | 四轮逐节 10 遍核查，**6 处**（实质 2 处）：①**树头 `CopyButton` 未写明用默认形态还是 inline**（默认 `position:absolute` 放错地方会压住树头）→ §3.4 明确"树头用默认形态，面板头才传 `inline`"；②**DC-10/DC-12 仍含裸字符与病句**（`▸折叠箭头` 与 T29「无裸字符」自相矛盾、"不带自带箭头"病句）→ 改写为文字描述；③DC-17"新增"二字易误读为新建组件 → 改"增设（复用）"；④**约定 4「不再二次折叠」与 §2.3.3「巨型值折叠」字面打架** → 改写为「不按项数二次折叠，巨型单值的体量处理不属此列」，DC-06/S6 同步；⑤**T25 与 §3.4.3 窄屏口径两处都写算式/策略** → §3.4.3 加"具体落法见 T25"；⑥§2.8 与 §2.2.2 否决清单重复且 §2.8 未收录视觉 6 项 → §2.8 加注声明 + 补收录一行 |
| v2.0 | 2026-10-13 09:36:18 | 小欧 | 五轮逐节 10 遍核查，查出 **4 处**，**其中 1 处是 v1.9 自己改坏的（已还原）**：①**§2.8 引用的「§2.2.2 视觉一致性 6 项」在 v1.9 被误删**（当时以为去重，实为误删，导致行数 840→835、§2.8 指向空）→ **全部还原**，并补 2 条此前从未入册的（凭空定面板宽、自造浮层热区），§2.2.2 现共 19 项，§2.8 改为引用式；②T18 用裸字符 `▸折叠箭头`，与 T29「全文无裸字符」自相矛盾 → 改文字描述；③T24「点 `▸`」同上 → 改「点折叠箭头」；④§3.6/§3.10/T20 三处「无**自带**箭头」病句（v1.9 只改了 DC-12 一处）→ 全部改「无箭头」。**行数回 844，§2.2.2 否决项由 6 增至 19** |
| v2.1 | 2026-10-13 09:36:18 | 小欧 | 北京老陈令「基于前三章编写第4章详细设计实施代码」。**新增 §4 实施代码章**（§4.0 差异登记 / §4.1 代码列表 / §4.2~§4.7 逐文件全量代码 / §五 验证清单），§4.0 声明「冲突以本章为准」。落地时按 KISS/DRY 收敛 **6 处与前三章的差异**：D-1 **参数区移出 `role="button"`**（结构性根治 B1，替代 I1 的 stopPropagation 补丁——补丁方案下用户无法在展开态选中文字）；D-2 删 `ParamsTreeProps.onNodeClick` 死接口；D-3 `ParamsPanelProps` 由 `{toolName,params,children}` 改 `{toolName,params,onClose}`（T15 要求 ✕ 可关；`children` 无消费方 YAGNI）；D-4 增尺寸令牌 `PARAMS_PANEL_BODY_MAX_H`；D-5 断点矩阵改**纯 CSS 响应式三件套**（免 resize 监听与重渲染）；D-6 确认 `FloatingEntry` 自带 `stopPropagation` 故可安全置于工具行 flex 内。`ToolCallLine.tsx` 净 **−55 行**、净减 1 个 state、渲染期 `JSON.stringify` 归零 |
| v2.2 | 2026-10-13 09:36:18 | 小欧 | 六轮逐节 10 遍核查第 4 章代码，查出 **5 处**（其中 **3 处直接导致编译/校验失败**）：①**§4.6.1 多导入未使用的 `Radius`**（§4.6 全文未用）→ ESLint `no-unused-vars` error，**已删**；②**§4.5 `VIEW_OPTIONS` 加了 `as const`** → 产出 readonly tuple，而 antd `Segmented.options` 类型是可变数组 `(string｜number｜SegmentedOption)[]`，**tsc 报 TS2322**，**已去掉 `as const`** 并注明理由；③**§4.4 树根标签写成「树根(恒展开)」** → 把实现注释泄漏到 UI，且与 §3.4.1 结构图 `▾ {` 不一致，**改为只写 `{`**；④§3.8 **T33 的 props 清单与 §4.0 D-3 不符**（仍写 `children`）→ **同步为 `{toolName, params, onClose}`**；⑤**§4.6.6 删除块用 `... paramsFoldable 分支 + paramRows.map ...` 占位**，不可直接实施 → **已展开为原文件 `:361-437` 逐行完整原文** |
| v2.3 | 2026-10-13 09:58:45 | 小欧 | 七轮倒推核查（从 §4 实施代码反推 §1/§2/§3 依据），查出 **4 处**：①**§4.5 引用的 `paramsCardStyle` 小写与 §4.6.2 定义的 `PARAMS_CARD_STYLE` 大写不一致** → 统一大写；②**`<FloatingEntry>` 置于工具行 flex 内会被压缩**（其根是无类名 block div，Props 无 trigger 样式入口，窄屏时按钮被挤没）→ **外裹一层 `flexShrink: 0` 的 span**（注释写明根因）；③**§4.4 树根容器用 `BORDER.LIGHT(#f0f0f0)`，与 §3.4.3 复用表规定的 `BORDER.DEFAULT(#d9d9d9)` 冲突**（同为"代码容器"边框一深一浅）→ 改 `DEFAULT`；④**§五第 5 步命令在无测试文件的机器上跑不动**（§4.7 按铁规不提交）→ 加注"仅本地有测试文件时执行，否则跳过" |

---

## 一、问题分析

### 1.1 分析对象与定位

分析对象：Step 页面（右栏 RightViewer）中，工具调用行展开后、工具结果区（`ToolResultRenderer`）之上的**参数区**。

| 位置 | 代码落点 |
|---|---|
| 参数区渲染 | `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx:363-437` |
| 结果区渲染 | `frontend/src/features/chat/components/ToolResultRenderer/index.tsx` |
| 流水线容器 | `frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx:361-370` |
| 右栏滚动容器 | `frontend/src/features/chat/components/layout/SessionLayout.tsx:121-129` |
| 右栏自动滚底 | `frontend/src/features/chat/components/right/RightViewer.tsx:346-397` |
| 样式令牌 | `frontend/src/utils/stepStyles.ts` |

当前参数区实际结构（`ToolCallLine.tsx:363-437`）：

```tsx
{isOpen && (
  <div style={{
    marginTop: Spacing.XS,          // 4
    paddingLeft: Spacing.LG,        // 12
    fontSize: FontSize.SECONDARY,   // 12
    color: Colors.TEXT.SECONDARY,   // #8c8c8c
  }}>
    {paramsFoldable ? /* 一行 "▸ 参数（N 项）" */ : null}
    {paramRows.map(r => (
      <div key={r.k} style={{
        fontFamily: 'Consolas, Monaco, "Courier New", monospace',
        wordBreak: 'break-all',
      }}>{r.k}: {r.v}</div>
    ))}
  </div>
)}
```

### 1.2 历史沿革：参数区"显示数量"的两代决策（v1.1 补充）

经 `git log -S` 逐版本核对，参数区的显示数量决策历史上有两代，**当前为第二代**：

**第一代（2026-08-27 ~ 2026-10-04）——单行 60 字符硬截**

```tsx
const tParamText = JSON.stringify(t.params ?? {});
...
参数：{tParamText.slice(0, 60)}     // 只露前 60 字符（约 1~2 个参数）
```

版本证据（逐版核对一致）：

| 提交 | 日期 | 形态 |
|---|---|---|
| `fd8b6d7d1` | 08-28 | `参数：{paramText.slice(0, 60)}` |
| `e8347e312` | 09-01 | `参数：{tParamText.slice(0, 60)}` |
| `f5bb51048` | 09-01 | 同款 |
| `88ce411d9` | 09-03 | 同款 |
| `0b3bb250c` | 09-15 | 同款 |

**第二代（`29b0ba2c3`，2026-10-04 至今）——每键一行 + >5 项折叠**

依据设计文档 `[8]observation工具结果显示问题-深度分析与优化方案-小欧-2026-10-04.md` §5.4：

- **乙案**：参数改「每键一行」，值直接取原值不二次序列化（避免路径 `\` 双重转义）
- **丙案**：项数 `> 5` 才折叠为一行 `▸ 参数（N 项）`，点开仍为**全量**

**结论**：当前无"只显示几个关键参数"的机制，第二代为**全量展示**。旧代 60 字符截断已于 2026-10-04 下线，且未留下"为何改全量"的记录。

**排除项（v1.0 曾误判，已订正）**：后端 `observation_content.py` 的 `DROP_KEYS`（30 键丢弃）、`PARAM_ORDER`（主次排序）、`PARAM_VALUE_MAX_CHARS=35`（截断），以及 `target_utils.py:15-18` 的 `_TARGET_PARAM_PRIORITY`（单参数优先）——**四套决策全部作用于摘要句**（`content_items[]` → 水滴右侧那行摘要），与参数区**无任何耦合**。v1.0 曾据其推断"参数区复用取舍口径"，属误判，本版删除该推断。

### 1.3 全页面结构与高度链路（全局分析）

从外到内的容器链与滚动归属：

| 层级 | 代码 | 高度行为 |
|---|---|---|
| ① 根布局 | `Layout/index.tsx:608` | `height:100vh; overflow:hidden` — 锁死视口 |
| ② 内容区 | `Layout/index.tsx:759-769` | `flex:1; overflow:auto` |
| ③ 页面根 | `ChatPage.tsx:271-281` | `height:100%; overflow:hidden` |
| ④ 会话骨架 | `SessionLayout.tsx:66-76` | `flex:1; minHeight:0; overflow:hidden` |
| ⑤ 中部 | `SessionLayout.tsx:91` | `flex:1; display:flex; minHeight:0` |
| ⑥ 右栏（75%） | `SessionLayout.tsx:106-131` | `flex:1; minHeight:0; overflowY:auto` — **唯一实际滚动容器** |
| ⑦ 流水线根 | `PipelineRenderer.tsx:362-369` | `borderLeft:2px; paddingLeft:12` — 无高度约束 |
| ⑧ 工具行 | `ToolCallLine.tsx:190-209` | `minHeight:32` — 含 `margin: stepMargin(false)` = 6px 上下 |
| ⑨ 工具子行 | `ToolCallLine.tsx:303-307` | `marginTop:4` |
| ⑩ 参数区 | `ToolCallLine.tsx:363-370` | **无 maxHeight、无滚动、无高度上限** |
| ⑪ 结果区 | `ToolCallLine.tsx:440-459` | `marginTop:2`（魔法数 `Spacing.XS-2`） |

**全局高度结论**：①~⑤ 全部锁高并 `overflow:hidden`，页面总高不会失控；真正的滚动容器只有 ⑥（右栏）。因此"全页面高度失控"实际表现为 **右栏滚动内容无上限增长**——用户感知为"页面被撑爆/滚不到底"。

行高实测链：

- ⑧ 根容器 `lineHeight = FontSize.PRIMARY(14) + Spacing.XS(4) = 18px`（`ToolCallLine.tsx:195`）
- ⑩ 参数区只改 `fontSize:12`，**未改 lineHeight**，行高仍继承 18px
- 故每个参数行实高 = 18px

### 1.4 缺陷清单

#### A. 视觉与可读性

| 编号 | 缺陷 | 代码落点 | 事实依据 |
|---|---|---|---|
| A1 | key 与 value 完全无视觉区分 | `:416` `{r.k}: {r.v}` 纯文本 | key、冒号、value 同字号同颜色同字体，扫读抓不到值 |
| A2 | 颜色弱化过度，不达 WCAG AA | `:369` `color: #8c8c8c` | 白底对比度 **3.09:1**，正文要求 4.5:1。参数是排查最需看清的内容，反而最看不清——层级倒挂 |
| A3 | 层级倒挂：参数缩进比结果更深 | 参数 `paddingLeft:LG(12)`（`:367`）vs 结果 `paddingLeft:SM(6)`（`:444`） | 参数是"输入"属次要，结果是"输出"更重要，却缩进更浅，缩进表达了错误语义 |
| A4 | 参数区与结果区无分隔 | 参数容器结束即接结果区，仅 `marginTop:2`（`:443`，且为魔法数 `Spacing.XS-2`） | 视觉糊成一块，分不清输入/输出 |
| A5 | `break-all` 粗暴断行 | `:413`、`:428` `wordBreak:'break-all'` | 在任意字符处切断；中文被切碎、长路径不从 `/` `.` 处断，长 JSON 完全不可读 |
| A6 | 对象/数组值单行 stringify | `:275-282` 非字符串一律 `JSON.stringify(v)` | 嵌套对象变超长单行，正好撞上 A5 被切碎 |
| A7 | 空值渲染为空白，无法与"参数不存在"区分 | `JSON.stringify(undefined)` 返回 `undefined`，React 渲染为空 | 显示成 `key: `，语义丢失 |
| A8 | 字体硬编码且与项目令牌不一致 | `:411`、`:427` 各写一遍 `'Consolas, Monaco, "Courier New", monospace'` | `stepStyles.ts:88` 已有 `FontFamily.MONO = 'Consolas, Menlo, monospace'`；DRY 违背且两种字形并存（`stepStyles.ts:20-23` 注释已记录此欠账） |
| A9 | 行高与字号不匹配 | 参数区 `fontSize:12` 继承 `lineHeight:18px` | 12px 字配 18px 行高，密集参数松散拖沓 |
| A10 | 无任何结构分组，全量参数平铺 | `:407-434` `paramRows.map` 等权渲染 | 路径、开关、编码、长正文载荷混排，23 项时无层次可循 |

#### B. 交互缺陷

| 编号 | 缺陷 | 代码落点 | 事实依据 |
|---|---|---|---|
| B1 | **点参数行会误折叠整个工具**（最严重） | 参数区整块位于父级 `role="button"`（`:308-320`）内 | 仅折叠箭头做了 `stopPropagation`（`:378`、`:391`），`paramRows` 展示区（`:407-419`）未做。点参数行 = 触发父级 `toggleTool`，整条工具行折叠，用户无法选中/复制长路径 |
| B2 | 展开参数触发整页自动滚底 | `RightViewer.tsx:386` ResizeObserver 观察锚点 → `scrollToBottomNow`（`:340-345`） | 展开参数后高度突增 → 页面被拽到底部，刚展开的参数内容立即滚出视口 |
| B3 | 参数区无任何交互反馈 | `:363-437` 全段 | 无 hover、无 focus 态，不可辨识为可交互区域 |

#### C. 全页面高度（全局性）

| 编号 | 缺陷 | 量化依据 |
|---|---|---|
| C1 | **参数区无任何高度上限**（全局核心问题） | ⑩ 无 `maxHeight`、无 `overflow`、无内部滚动。每行 18px，高度 = 参数行数 × 18 |
| C2 | **巨型参数无特殊处理**（最严重具体来源） | `write`/`edit` 的 `content` 参数是整段文件内容，数千行纯文本直接淹没右栏，且与 ⑥ 右栏主滚动容器抢滚动 |
| C3 | 折叠阈值按"项数"固定值定，不看内容体量 | `PARAMS_FOLD_THRESHOLD = 5`（`:124`）。5 项以内全量展开——若其中 1 项是 3000 字代码，阈值形同虚设 |
| C4 | 并行多工具高度**线性叠加** | 每工具子行独立展开（`expanded[]` 数组，`:288`），并行 5 个工具全展开 = 右栏内容 5 倍 |

高度量化表（按每行 18px）：

| 场景 | 参数行数 | 叠加高度 |
|---|---|---|
| `read`（file_path/offset/limit/encoding） | 4 | 72px |
| `write`（含 content，content 为 300 行代码） | 6 | **5400px+** |
| `find`（pattern/replace/glob… 23 项） | 23 | 414px |
| 并行 5 工具全展开 | — | **N 倍线性叠加** |

---

## 二、优化问题解决方案

### 2.1 总体路线：双载体并存（展开区 JSON 树 + 浮层双视图）

**北京老陈 2026-10-13 裁定**：现有展开区**保留**，浮层是**新增**载体，二者并存互补。

| 载体 | 定位 | 渲染形态 | 高度行为 |
|---|---|---|---|
| **现有展开区** | 就地一眼扫读，不离开流水线语境 | **戊 · JSON 树**（顶层键默认折叠） | **恒定 N 行**，与参数值体量无关 |
| **浮层**（工具行内固定按钮触发） | 细看、复制、宽屏读长内容 | **乙 · 分组卡片**（默认）/ **甲 · 规格表**（切换） | 不进入右栏滚动流，**高度增长 0** |

**关键约定**

1. 并行 N 个工具**仍是 N 条独立子行**，每条独立可点（现状 `expanded[]` 数组机制不变）
2. 浮层**单例互斥**：点新的自动关旧的，任意时刻最多一个面板亮着
3. 浮层触发按钮**固定在工具行内**（跟在结果摘要右侧），**位置不随展开态移动**（D1 裁定，§3.10）
4. 浮层**不按项数二次折叠**：打开即展示全部参数键（与旧 `>5 项折成一行` 彻底告别）；**巨型值自身的「共 N 行 · 展开」不属二次折叠**（见 §2.3.3，那是单值的体量处理，不是整块折叠）
5. **两态互不牵连**（DC-18）：工具行折开收起与浮层开合各自独立，任一方动作不影响另一方
6. **嵌套深度不设上限**（DC-15）：由数据自身决定，深度失控由限高 240px 控制而非层级裁剪
7. **两处复制语义不同**（DC-16/DC-17）：浮层复制 `key=value` 逐行；展开区 JSON 树复制格式化 JSON

### 2.2 现有展开区改造：戊 · JSON 树

```
● write成功:从第1-200行  ▾   </> 浮层参数   ← 按钮固定在工具行行尾（D1 裁定乙 + D2 裁定顺序）
  ▾ {
      ▸ "file_path"    : "F:\...\backend\app\main.py"
      ▸ "encoding"     : "utf-8"
      ▸ "shell_type"   : "powershell"
      ▸ "append"       : false
      ▸ "timeout"      : 30
      ▸ "content"      : "共 312 行"
    }
  成功:从第1-200行
```

**高度收益（本方案核心）**：顶层键**默认折叠**，每个参数恒占 1 行。

**行高口径**：新组件行高取 `FontSize.SECONDARY(12) + Spacing.XS(4) = 16px`，符合项目既定规则「行高 = 字号 + 4」（`stepStyles.ts:13`）。现状的 18px 是**继承**自 14px 根容器、并非按 12px 字号算出（属缺陷 A9），故下表"改造后"一律按 16px 计。

| 场景 | 改造前（行高 18px） | 改造后（行高 16px） |
|---|---|---|
| `write`（content 300 行） | 5400px+ | **7 行 × 16px = 112px 恒定** |
| `find`（23 项） | 414px | 24 行 × 16px = 384px（1 行树根 + 23 键） |
| 并行 5 工具全展开 | N 倍叠加（write 为例 5400px） | N × 112px |

**展开节点规则**：`▸ "content"` 展开后显示多行内容，但**内部限高 240px 滚动**，故单节点展开也不撑页。

**顺带解决（结构层面）**：A1（key/value 由**双色阶**区分——键 `TEXT.SECONDARY` / 值 `TEXT.STRONG`）、A5/A6（节点缩进结构替代 `break-all` 粗暴断行）、A10（按节点分列浏览）。其余 A2/A7/A9 由 §2.5 的 V1/V5/V7 令牌级改造解决，非结构本身带来。

**与浮层的口径差异**：展开区**不分组**——JSON 树的「树结构本身即分组」，按键原序纵览；浮层**按语义分组**（路径/开关/编码/正文载荷/其他），供快速定位。两者定位不同（就地纵览 vs 定向细看），故刻意采用不同组织方式。

#### 2.2.1 设计决策汇总表（**唯一真源，实施须逐条对照，防设计与讨论结果走样**）

> 本表汇总 2026-10-13 全程讨论产生的全部裁定。**凡本文正文与本表冲突，以本表为准**，并视为文档缺陷须订正。

| 编号 | 决策项 | 裁定结果 | 性质 | 正文落点 |
|---|---|---|---|---|
| DC-01 | 文档章节结构 | 三章：问题分析 / 优化问题解决方案 / 实施代码详细设计说明 | 北京老陈裁定 | 全文 |
| DC-02 | 总体路线 | 采用**浮层承载**（在方案一/二对比中选定方案一） | 北京老陈裁定 | §2.1 |
| DC-03 | 展开区存废 | **保留**现有展开区，浮层为**新增**载体，二者并存 | 北京老陈裁定 | §2.1 §2.6 |
| DC-04 | 展开区渲染形态 | **戊 · JSON 树**（顶层键默认折叠） | 北京老陈裁定 | §2.2 §3.4 |
| DC-05 | 浮层视图 | **乙 · 分组卡片（默认）** + **甲 · 规格表（可切换）**，antd `Segmented` + localStorage 记忆 | 北京老陈裁定 | §2.3.1 §3.5.4 |
| DC-06 | 浮层内是否按项数折叠 | **不折叠**：打开即展示全部参数键；巨型单值的「共 N 行 · 展开」不属此列（见 §2.3.3） | 北京老陈裁定 | §2.1 §2.4 S6 |
| DC-07 | 并行工具的浮层行为 | 并行 N 工具仍是 **N 条独立子行**（现状不变）；浮层**单例互斥**，任意时刻最多一个面板亮着 | 北京老陈确认 | §2.1 §3.2 |
| DC-08 | 参数显示范围 | **全量展示**，不做"只显几个关键参数"的取舍 | 北京老陈确认（现状即全量） | §1.2 §3.3 |
| DC-09 | 浮层按钮纵向位置 | **固定在工具行内**（位置不随展开态移动） | 北京老陈裁定 **D1 乙** | §2.1 §3.6 |
| DC-10 | 行内排列顺序 | `内容信息 │ 折叠箭头 │ 浮层参数按钮`（按钮在行尾；折叠箭头为 `CircleArrow` 组件，非裸字符） | 北京老陈裁定 **D2 乙** | §3.6 |
| DC-11 | 浮层按钮文案 | **`浮层参数`**（不是 `参数`，避免与展开区撞名） | 北京老陈裁定 **D3** | §3.6 §3.9 |
| DC-12 | 浮层按钮是否带箭头 | **不带箭头**，开合以**按钮文字色**标识（关 `TEXT.SECONDARY` / 开 `PRIMARY`） | 小欧补充设计（避免与折叠箭头混淆成两级折叠） | §3.6 |
| DC-13 | 行高口径 | **16px**（`FontSize.SECONDARY(12) + Spacing.XS(4)`，项目既定规则「字号+4」） | 小欧依既有规则推导 | §2.2 §3.4.3 |
| DC-14 | 令牌新增策略 | **禁造同值别名**：3 个与既有同值的拟新增令牌一律删除，直接复用 | 小欧三堂会审查 | §3.4.3 |
| DC-15 | JSON 树嵌套深度 | **不设上限**，任意深度均可逐层展开；深度风险由每层展开体限高 240px 控制，不做层级裁剪 | 北京老陈裁定 **U1** | §3.4.1 |
| DC-16 | 浮层复制内容 | **`key=value` 逐行**（非 JSON），面向人工核对/贴工单 | 北京老陈裁定 **U3** | §3.5.5 |
| DC-17 | 展开区 JSON 树复制 | **`JSON.stringify(params, null, 2)` 格式化 JSON**（树头增设复制按钮，复用 `CopyButton`），面向粘代码/交 LLM | 北京老陈裁定 **U3** | §3.4.1 |
| DC-18 | 工具行展开态与浮层开合 | **各自独立，互不牵连**（折叠不关浮层，关浮层不折叠）；仅切任务时同时清理 | 北京老陈裁定 **U2** | §3.2 |
| DC-19 | **视觉一致性铁律** | **禁新增颜色令牌**：键 `TEXT.SECONDARY`、值 `TEXT.STRONG`、面板 `BG.SECONDARY`+`BORDER.DEFAULT`+`Radius.SM`、等宽 `FontFamily.MONO`+`FontSize.CODE`，全部取自既有令牌；JSON 树**不做语法着色** | 北京老陈指令「UI视觉一致性检查与系统整体风格一致」 | §3.4.3 §3.5.1 |
| DC-20 | **复用既有资产，不造轮** | 复制按钮复用 `CopyButton.tsx`；浮层壳复用 `FloatingEntry.tsx`（含焦点管理与 a11y）；折叠箭头复用 `CircleArrow`；省略+全文复用 `EllipsisTip`；热区复用 `.taskinfo-entry` | 北京老陈指令「与系统整体风格一致」 | §3.1 §3.4 §3.5 |
| DC-21 | **分类色不得占用语义色** | 参数分类色条只用 `Colors.BORDER.*` 中性灰阶；`WARNING`/`ACCENT_ORANGE`/`SUCCESS`/`ERROR` 保留给状态语义 | 北京老陈指令「与系统整体风格一致」 | §3.5.2 |
| DC-22 | 浮层触发按钮图标 | 用 **antd `CodeOutlined`**，不用 `GearIcon`（后者语义为"工具执行等待"） | 北京老陈指令「与系统整体风格一致」 | §3.6 |

#### 2.2.2 被否决方案（留档，防重复讨论）

| 方案 | 否决理由 | 否决时点 |
|---|---|---|
| 浮层**取代**展开区（DC-02 初版） | 北京老陈：「现在的展开区留着」→ 改为并存（DC-03） | 2026-10-13 |
| 浮层**不取代**但**改用内联限高**（原方案二） | 只能封顶不能消除，并行 N 工具仍叠加；且用户要求"展开区留着" | 2026-10-13 |
| 浮层内**二次折叠**（>5 项折成一行） | 浮层已是"点开才看"，再套折叠是多一次点击 | 2026-10-13 |
| 展开区**限高 3 行 + 跳转按钮** | 用户直接选定「戊 · JSON 树」，该中间方案未采用 | 2026-10-13 |
| 恢复旧代 **60 字符截断** | 2026-10-04 已下线；截断丢失排查信息，JSON 树已解决高度 | 2026-10-13 |
| 参数区复用后端 `DROP_KEYS`/`PARAM_ORDER` 分组 | 二者作用于摘要句，与参数区零耦合（§1.2 已订正） | 2026-10-13 |
| 浮层按钮**接受位置随展开态移动**（D1 甲） | 位置跳动体验差 → 改乙 | 2026-10-13 |
| 浮层按钮**收起态不显示**（D1 丙） | 收起时少一个快捷入口 | 2026-10-13 |
| 浮层视觉：**丙 紧凑清单 / 丁 双栏宽表 / 己 主从双栏** | 用户选乙（分组）+ 甲（规格表）双视图 | 2026-10-13 |
| 浮层视觉：**戊 JSON 树** | 用户将该形态指派给**展开区**，浮层改用乙/甲 | 2026-10-13 |
| JSON 树**嵌套深度限 2 层** | 北京老陈：「为什么要限制 不需要限制」 | 2026-10-13 |
| **JSON 语法高亮配色**（绿/蓝/橘三色） | 系统无代码语法色系，`MarkdownText` 代码块是纯 `TEXT.STRONG` 单色；引入会与页面其它代码块观感割裂（DC-19） | 2026-10-13 |
| **自造浮层壳 + 自建 a11y** | 系统已有 `FloatingEntry` 封装（含焦点入卡、Esc 焦点回入口），自建必漏无障碍细节（DC-20） | 2026-10-13 |
| **自造复制按钮** | 系统已有 `CopyButton.tsx`（1.5s「已复制」回退 + `aria-label` + 令牌化样式）（DC-20） | 2026-10-13 |
| **分类色条用 `WARNING`/`ACCENT_ORANGE` 等语义色** | 分类是结构、状态是语义，混用会让用户误读为"有警告/异常"（DC-21） | 2026-10-13 |
| **浮层按钮用 `GearIcon`** | 该图标系统语义为「工具执行等待」转圈齿轮，复用会误导为"加载中"（DC-22） | 2026-10-13 |
| **裸 `▸`/`▾` 字符做折叠切换** | 系统折叠一律 `CircleArrow(14, PRIMARY)` + 「展开/收起」（`CollapsibleText.tsx:109-115`）（DC-20） | 2026-10-13 |
| **浮层宽度凭空定值**（无断点依据） | 须接系统断点矩阵（`TaskInfoBar.tsx:26`）与 `EllipsisTip` 降级原则（DC-19） | 2026-10-13 |
| **浮层入口自造热区** | 系统 `.taskinfo-entry` 已定义 hover/focus 规格（`index.css:253-274`）（DC-20） | 2026-10-13 |

### 2.3 浮层改造：乙（默认）+ 甲（切换）

```
┌────────────────────────────────────────────────────────────┐
│ </> write · 参数 6 项     [分组│规格表]            [复制]   ✕ │
├────────────────────────────────────────────────────────────┤
│ 【默认·分组视图】                                           │
│ ▌ 路径                                                     │
│    file_path      F:\...\backend\app\main.py               │
│ ▌ 开关                                                     │
│    append         关闭                                      │
│    shell_type     powershell                               │
│ ▌ 编码                                                     │
│    encoding       utf-8                                    │
│ ▌ 正文载荷                                                 │
│    content        共 312 行                     ▸ 展开      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  1  from fastapi import FastAPI                  │   │
│  └──────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────┤
│ 【规格表视图】                                              │
│ file_path      F:\OmniAgentAs-repair\backend\app\main.py  │
│ ────────────────────────────────────────────────────────│
│ encoding       utf-8                                      │
│ ────────────────────────────────────────────────────────│
│ content · 312 行 ────────────────────────────────────────│
│  1 │ from fastapi import FastAPI                         │
│  2 │ app = FastAPI()                                     │
└────────────────────────────────────────────────────────────┘
```

#### 2.3.1 切换器定案

| 项 | 定案 |
|---|---|
| 位置 | 面板头右侧，复制按钮 与 `✕` 左边 |
| 控件 | antd `Segmented`，两段：`分组` / `规格表` |
| 默认 | **分组**（层次清楚，为主视图） |
| 记忆 | 写入 `localStorage`，下次打开沿用上次选择 |
| 数据源 | 两视图共用同一份 `t.params`，零重复取数，切换零延迟 |
| 无障碍 | 由 `FloatingEntry` 提供 `role="dialog"` + `aria-haspopup/expanded/controls/label`（`FloatingEntry.tsx:73-92`），**不自建**；`Segmented` 自带键盘可达 |

#### 2.3.2 分组规则（乙视图）

按参数语义自动分**五类**（四类具名 + 一类兜底「其他」），**不硬编码工具名单**，按 key 形态与值形态判定。

**判定优先级链（严格自上而下，命中即止，防一个参数落进两组）**：

```
1. 正文载荷  ← 值含换行 / 值为 list|dict / 值.length > HUGE_VALUE_CHARS
2. 开关      ← 值为 boolean
3. 路径      ← key ∈ PATH_KEYS 或 值匹配路径特征
4. 编码      ← key ∈ {encoding, charset}
5. 其他      ← 以上皆非（兜底）
```

> **正文载荷置于最高优先级**的原因：`content`/`body` 之类的值往往极长，若先按"路径特征"或"编码"匹配，会被误分到语义更轻的组里；而它们恰恰是用户最需要一眼定位的参数，故优先占位。

| 类 | 判定规则 | 示例 |
|---|---|---|
| 路径 | key ∈ `PATH_KEYS`（`path`/`dir_path`/`file_path`/`source_path`/`dest`/`output_path`）**或** 值匹配路径特征（含分隔符且有扩展名） | `file_path`、`dest` |
| 开关 | 值为 boolean | `append`、`overwrite`、`recursive` |
| 编码 | key ∉ `PATH_KEYS` 且 key ∈ `{encoding, charset}` | `encoding` |
| 正文载荷 | 值含换行，或为 list/dict 对象，或字符串长度 > `HUGE_VALUE_CHARS`(200) | `content`、`body`、`data` |
| 其他 | 以上皆非（兜底） | `timeout`、`limit` |

> 「路径特征」判定细则：**同时**满足含 `/` 或 `\` **且**末段存在扩展名（`\.` + 1~8 位字母数字）。单独含分隔符但无扩展名（如 `a/b/c`）不判为路径，归「其他」，避免误伤 SQL 片段与代码片段。

#### 2.3.3 巨型值处理（两视图共用）

| 条件 | 呈现 |
|---|---|
| 含换行 / 超 `HUGE_VALUE_CHARS`(200) | 折叠为 `共 N 行 · 展开`；展开后限高 240px 内部滚动 |
| list/dict 对象 | `JSON.stringify(v, null, 2)` 多行缩进，按上行同样限高；嵌套深度不限（DC-15） |

> 展开区 JSON 树**不用**本表口径（只看是否含换行，不设字符阈值），理由见 §3.4.1。

### 2.4 交互改造清单

| # | 改造项 | 解决缺陷 |
|---|---|---|
| S1 | 展开区改 JSON 树（顶层默认折叠 + 节点限高滚动） | C1 C2 C3 A1 A5 A6 A10 |
| S2 | 浮层按钮**固定挂于工具行内**（结果摘要右侧），位置不随展开态移动；展开区保留不动 | 定位澄清（并存 + D1 裁定乙） |
| S3 | 浮层双视图（乙默认 / 甲切换）+ localStorage 记忆 | A10 层次 |
| S4 | 浮层单例互斥：`openPanelIndex` state，点新关旧 | C4 叠加 |
| S5 | 面板头 `工具名 · 参数（N 项）` + 复制按钮（key=value 逐行）+ `✕`；树头另置复制按钮（格式化 JSON）。**两处均复用 `CopyButton`**（面板头传 `inline`），不自造 | 可用性 + DC-16/DC-17 + DC-20 |
| S6 | 浮层不按项数折叠（打开即展示全部参数键）；巨型单值的折叠见 §2.3.3 | 简化两层点击 |
| S7 | 工具行展开态与浮层开合**互不牵连**，嵌套深度不限，两处复制语义分立 | DC-18 DC-15 DC-16 DC-17 |

### 2.5 视觉改造清单（两载体共用令牌）

| # | 改造项 | 解决缺陷 |
|---|---|---|
| V1 | key / value **分色**：key 用 `TEXT.SECONDARY`，value 用 `TEXT.PRIMARY`（对比度 7:1 达标）；JSON 树内值用 `TEXT.STRONG`。**不做语法着色**（无 `Colors.JSON.*`，见 DC-19） | A1 A2 |
| V2 | 字体改用 `FontFamily.MONO` 令牌，删两处硬编码 | A8 |
| V3 | `break-all` → `break-word`；长值截断 + `title` 全文（复用 `EllipsisTip`） | A5 |
| V4 | 对象值多行缩进 JSON（树节点内天然支持） | A6 |
| V5 | 空值渲染 `(空)` 占位 | A7 |
| V6 | 层级重定义：靠**浅底/边框/缩进结构**表达输入输出之分，**不用缩进表达重要次要** | A3 A4 |
| V7 | 参数区显式 `lineHeight = FontSize.CODE(12) + Spacing.XS(4) = 16px`，与字号匹配 | A9 |
| V8 | 节点/按钮加 hover / focus-visible 反馈；按钮热区复用 `.taskinfo-entry` | B3 |

### 2.6 保留不动项（防功能退化）

| 保留项 | 代码落点 | 理由 |
|---|---|---|
| 每工具独立展开状态 | `:288` `expanded[]` | 现状能力不减 |
| 展开区整体挂在工具行内（就地展开手感） | `:363` | 北京老陈裁定"现有展开区留着" |
| 工具名 / 状态水滴 / 结果摘要单行省略 | `:330-352` | 现状观感已定案；收起行三部分顺序仅**追加**参数按钮，不改前三者（D2） |
| `ToolResultRenderer` 结论区 | 独立组件 | 不在本次范围 |
| 参数按数组下标配对 `results[idx]` | `:160-162` | 并行同名工具防串味（2026-10-04 已修） |

### 2.7 必做的交互修复

| # | 修复 | 说明 |
|---|---|---|
| I1 | **浮层按钮与树节点区加 `stopPropagation`** | 解决 B1：点参数节点不再折叠整个工具行 |
| I2 | 树节点/浮层展开的限高 | 解决 C1 C2：单节点展开不撑页 |
| I3 | 浮层内容不进入右栏滚动流 | 解决 B2：浮层展开不触发 `RightViewer` 全页滚底 |
| I4a | **浮层复制**：`key=value` 逐行（DC-16） | 一键复制逐行参数，人工核对/贴工单用 |
| I4b | **展开区 JSON 树复制**：`JSON.stringify(params, null, 2)` 格式化 JSON（DC-17），树头复用 `CopyButton` | 一键复制可直接粘进代码或交 LLM |
| I5 | `Escape` 关闭 + 点击面板外关闭 + `✕` 按钮——全部由 `FloatingEntry` 提供 | 与项目现有浮层行为一致 |
| I6 | 焦点可达：触发按钮 `tabIndex=0` + `aria-haspopup/expanded/controls/label`，面板 `role="dialog"`——**全部由 `FloatingEntry` 提供**（`FloatingEntry.tsx:73-92`），不自建 | 无障碍 |
| I7 | **两态互不牵连**（DC-18）：`toggleTool` 只改 `expanded[]`，`togglePanel` 只改 `openPanelIndex` | 收起工具行**不关**浮层；关浮层**不收**工具行 |

### 2.8 被否决的备选（留档，防重复讨论）

> 完整否决清单见 §2.2.2（含视觉一致性否决项，共 20 条）。本节仅列与"渲染形态"直接相关者。

| 备选 | 否决理由 |
|---|---|
| 浮层取代展开区 | 北京老陈裁定"现有展开区留着"，改为并存 |
| 浮层内二次折叠 | 浮层已是"点开才看"，再套折叠是多一次点击 |
| 恢复旧代"60 字符截断" | 2026-10-04 已下线，截断丢失排查信息，JSON 树已解决高度问题 |
| 浮层复用后端 `DROP_KEYS`/`PARAM_ORDER` 分组 | 二者作用于摘要句，与参数区无耦合（§1.2 已订正） |
| 其余 16 项（含视觉一致性否决项、按钮位置甲/丙案、各视觉方案） | 完整条目见 §2.2.2 |

---

## 三、实施代码详细设计说明

### 3.1 改动文件清单

| # | 文件 | 改动 |
|---|---|---|
| 1 | `frontend/src/features/chat/components/pipeline/ParamsTree.tsx`（新建） | 展开区 JSON 树组件（可折叠节点、限高滚动、键值分色、树头复用 `CopyButton`） |
| 2 | `frontend/src/features/chat/components/pipeline/ParamsPanel.tsx`（新建） | 浮层面板（乙分组视图 + 甲规格表视图 + `Segmented` 切换 + 复制） |
| 3 | `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx` | 展开区改挂 `ParamsTree`；工具行内加浮层触发按钮与 `ParamsPanel`（D1 裁定乙，位置固定） |
| 4 | `frontend/src/utils/stepStyles.ts` | 新增**面板尺寸**令牌（`Size.*`）；**不新增颜色令牌**，全部复用既有 `Colors.*` |
| 5 | `frontend/src/features/chat/components/pipeline/ParamsTree.test.tsx`（新建） | 展开区行为回归测试 |

**复用优先（不新建已有资产）**

| 复用 | 路径 | 替代了什么 |
|---|---|---|
| `CopyButton` | `frontend/src/components/markdown/CopyButton.tsx` | 自造的复制按钮（含 1.5s「已复制」回退、a11y、令牌化样式）。**须加一个可选 prop `inline?: boolean`（默认 `false` 保持既有 5 处调用零变化），面板头传 `inline` 取消绝对定位**——理由见下 |
| `FloatingEntry` | `frontend/src/features/chat/components/taskinfo/FloatingEntry.tsx` | 自建浮层壳与 a11y（含焦点入卡、Esc 后焦点回入口） |
| `CircleArrow` | `frontend/src/components/CircleArrow.tsx` | 自造折叠箭头（14px/PRIMARY 规格） |
| `EllipsisTip` | `frontend/src/features/chat/components/taskinfo/EllipsisTip.tsx` | 自造「省略+悬停全文」 |
| `.taskinfo-entry` | `frontend/src/index.css:253-274` | 自造浮层入口热区 |

### 3.2 状态设计（ToolCallLine.tsx 组件体）

```tsx
// 现状保留：每工具独立展开状态（不动）
const [expanded, setExpanded] = useState<boolean[]>([]);

// v1.1 删除：paramsOpen / PARAMS_FOLD_THRESHOLD（:122-124）
// 理由：展开区改 JSON 树后，节点级折叠由 ParamsTree 内部自治；
//       顶层"参数（N 项）"折叠已被"顶层键默认折叠"取代，不再需要

// 新增：浮层单例互斥（任意时刻最多一个面板）
// DC-18 互不牵连：toggleTool 只动 expanded，togglePanel 只动 openPanelIndex，二者互不调用
const [openPanelIndex, setOpenPanelIndex] = useState<number | null>(null);

const togglePanel = (i: number) =>
  setOpenPanelIndex((prev) => (prev === i ? null : i));  // 点新的关旧的
```

**两态独立性（DC-18）**：

| 操作 | 影响 `expanded[]`（工具行） | 影响 `openPanelIndex`（浮层） |
|---|---|---|
| 点 `▸` 折叠箭头 | ✅ 变 | ❌ 不变（浮层保持打开） |
| 点 `浮层参数` 按钮 | ❌ 不变（工具行保持原状） | ✅ 变 |
| 点 `✕` / 点外面 / `Escape` | ❌ 不变 | ✅ 关 |

唯一同时清空二者的是**切任务**（`useEffect(..., [action])`，`:125-128`）——旧任务的面板与展开态都不该泄漏到新任务，属清理而非联动。

### 3.3 数据源单一化

现状 `:268-283` 的 `paramRows` 计算（含渲染期 `JSON.stringify`）删除，改为向两个子组件传**原始入参**：

```tsx
const paramEntries = Object.entries((t.params ?? {}) as Record<string, unknown>);
// ParamsTree   收 paramEntries
// ParamsPanel  收 t.params（按视图需要自行分组）
```

理由：序列化与格式化下沉到组件内部（SLAP），消除渲染期开销；两视图共用同一份数据，切换零延迟（§2.3.1）。

### 3.4 `ParamsTree.tsx` 设计（展开区 · 戊 JSON 树）

```tsx
interface ParamsTreeProps {
  entries: Array<[string, unknown]>;
  maxNodeBodyHeight?: number;  // 默认 240（每一层展开体各自承担）
  onNodeClick?: (e: React.MouseEvent) => void;  // 外层接 stopPropagation
}
```

**树头（§3.4.1 结构图首行 `▾ {` 右侧）**

```
▾ {                          [复制]    ← 树头：折叠箭头 + CopyButton（复用，非自造）
    ▸ "file_path"  : "F:\...\main.py"
    ▸ "content"    : "共 312 行"
  }
```

复制内容为 `JSON.stringify(Object.fromEntries(entries), null, 2)`（格式化 JSON）。按钮**直接复用 `frontend/src/components/markdown/CopyButton.tsx`**（`fontSize:11` + `BORDER.DEFAULT` 细框 + `Radius.SM` + 白底灰字 + 点击 1.5s 回「已复制」），**不自造图标按钮**——自造会与系统代码块右上角的复制按钮观感割裂（无「已复制」反馈、无 `aria-label`）。**树头用 `CopyButton` 默认形态（`position:absolute`）**——树头容器是相对定位块，默认绝对定位正落在树头右上角，与代码块内的用法完全一致；面板头才传 `inline`。

#### 3.4.1 结构与默认态

> 示例仅列 2 键以便对齐阅读；完整结构与 §2.2 示意图（6 键）一致。

```
▾ {                      ← 树根常展
    ▸ "file_path"  : "F:\...\main.py"     ← 顶层节点默认折叠
    ▸ "content"    : "共 312 行"           ← 长值折叠为摘要
  }
```

| 节点类型 | 默认态 | 展开后 |
|---|---|---|
| 顶层标量键（string/数字/布尔） | 恒为单行 `key : 值`，**无折叠态**（本就一行，箭头不出现） | 无（不存在展开） |
| 顶层长字符串 / 含换行 | 折叠，显示 `共 N 行` | `<pre>` 限高 240px 内部滚动 |
| 顶层 list / dict 对象 | 折叠，显示 `{…} N 项` | 子节点树，嵌套限高 240px |
| **嵌套节点（任意深度）** | 随父节点展开态 | **不限嵌套层数**（DC-15），逐层独立折叠；限高 240px 由**每个展开体各自**承担 |

**嵌套深度不设上限（DC-15）**：嵌套层数由数据自身决定，是数据的客观结构，前端不应替后端做裁剪。深度失控的风险由**限高 240px**而非层级上限来控制——任意深度的内容展开后都只在 240px 内滚动，不会撑破展开区。故上表「嵌套限高 240px」指**每一层展开体各自限高**，非全局总高。

**长值在树内的截断口径**：折叠态单行恒显示，**不因长度换行、不截断**（单行 + 溢出省略）；展开态 `<pre>` 限高滚动，**不做字符级截断**——内容完整可读、可选中复制。这与浮层"巨型值超 200 字折叠"是**两套口径**（树内无字符阈值、只看是否含换行），刻意区分：展开区已天然限高，无需再按字符折叠。

**展开区复制（DC-17）**：见上文树头结构图，复制内容为 `JSON.stringify(params, null, 2)` 格式化 JSON（与浮层的 `key=value` 逐行**语义不同**，见 DC-16）——树形态是 JSON，复制自然也该是 JSON，便于直接粘进代码或交给 LLM。

#### 3.4.2 交互

| 项 | 规格 |
|---|---|
| 折叠箭头 | 复用既有 `CircleArrow`（同 `CollapsibleText`/`ThinkingStream`，保证图标列对齐，见 `stepStyles.ts:128-138` `Icon.BOX`） |
| 点击节点 | 切换该节点展开态，`onClick` 内 `e.stopPropagation()`（解决 I1/B1） |
| 键盘 | `Enter` / `Space` 切换，`tabIndex=0`，`aria-expanded` |
| 折叠动画 | 无（避免流式下抖动，与 `ThinkingStream` 折叠策略一致） |

#### 3.4.3 样式令牌（stepStyles.ts 新增）

**本功能不新增任何颜色令牌，全部复用既有 `Colors.*`。** 仅新增面板尺寸令牌：

```ts
// 唯一新增项——尺寸令牌（既有结构无对应者）
Size.PARAMS_PANEL_MAX_H    = 240         // 巨型值/节点展开限高
Size.PARAMS_PANEL_MAX_W    = 640         // 浮层最大宽（甲规格表需宽）
Size.PARAMS_PANEL_MIN_W    = 320         // 浮层最小宽（窄屏下限，见下方窄屏口径）
```

**视觉一致性：直接复用既有令牌，禁新增颜色**

| 用途 | 复用既有令牌 | 出处 |
|---|---|---|
| JSON 键名 | `Colors.TEXT.SECONDARY` `#8c8c8c` | `stepStyles.ts:145` |
| JSON 值（字符串/数字/布尔**统一**） | `Colors.TEXT.STRONG` `#333333` | `stepStyles.ts:148` |
| 参数值（浮层内普通值） | `Colors.TEXT.PRIMARY` `#595959` | `stepStyles.ts:144` |
| 面板/代码块底 | `Colors.BG.SECONDARY` `#fafafa` | `stepStyles.ts:154` |
| 面板/代码块边框 | `Colors.BORDER.DEFAULT` `#d9d9d9` + `BorderWidth.DEFAULT` | `MarkdownText.tsx:90` |
| 圆角 | `Radius.SM` 4 | `MarkdownText.tsx:91` |
| 等宽字体 | `FontFamily.MONO` | `stepStyles.ts:88` |
| 代码块字号 | `FontSize.CODE` 12 | `MarkdownText.tsx:93` |

**已删除的拟新增项（三处，视觉不一致根因）**

| 拟新增 | 值 | 删除理由 |
|---|---|---|
| `Colors.JSON.STRING` | `#389e0d` 绿 | 系统**无代码语法高亮色系**，代码块（`MarkdownText`）是纯 `TEXT.STRONG` 单色。引入五色语法会让 JSON 树在页面里与其它代码块**观感割裂**，破坏"全链仅 14/12 二档灰阶"的既定原则 |
| `Colors.JSON.NUMBER` | `#1677ff` 蓝 | 同上 |
| `Colors.JSON.BOOLEAN` | `#d46b08` 橘 | 同上 |

> JSON 树的类型区分**靠等宽字体 + 缩进结构 + `▸` 箭头**，不靠颜色——与系统 `MarkdownText` 代码块观感对齐。

**行高写法统一**：新组件内按既有模式内联 `${FontSize.CODE + Spacing.XS}px`（同 `ToolResultRenderer.tsx:109` 的 `FontSize.SMALL + Spacing.XS` 写法），**不新增 `LineHeight` 令牌组**，避免与仓内 6+ 处既有内联写法不一致。

**`HUGE_VALUE_CHARS`(200) 不进 stepStyles**：它是**判定阈值**而非视觉令牌，落 `ParamsPanel.tsx` 模块级 `const HUGE_VALUE_CHARS = 200`（与 `PARAMS_FOLD_THRESHOLD` 现状同范式），避免为单一消费方开设计令牌（YAGNI）。

**`Size` 命名说明**：既有组为 `BorderWidth`/`FontSize`/`Radius`/`Spacing`（"名 + 量纲"风格），故新组用 `Size.*` 承接面板尺寸，不新建 `PanelSize` 之类第四种风格。

**窄屏口径**：面板宽接系统断点矩阵（`TaskInfoBar.tsx:26` 记载的 wide/mid/narrow/xsmall）——宽档用 `Size.PARAMS_PANEL_MAX_W`(640)，窄档降到 `Size.PARAMS_PANEL_MIN_W`(320)；最低不小于 320，窄于 320 的视口按 320 铺满并允许面板内滚动，**不产生横向滚动条**（与 `EllipsisTip`「超宽不横滚、靠折叠/Tooltip 降级」原则一致）。**具体落法见 T25**（`min(视口-32px, 640)`）。

### 3.5 `ParamsPanel.tsx` 设计（浮层 · 乙/甲双视图）

```tsx
interface ParamsPanelProps {
  toolName: string;
  params: Record<string, unknown>;
  children: React.ReactNode;   // FloatingEntry 的 content（GroupView / SpecView）
}
```

> 浮层开合、锚点、a11y、焦点管理**全部由 `FloatingEntry` 承担**，本组件只负责"渲染什么内容"与"面板内样式"（SRP）。

**容器选型定案**：用**系统既有浮层统一壳 `FloatingEntry`**（`frontend/src/features/chat/components/taskinfo/FloatingEntry.tsx`）包裹 antd `Popover`，不自建浮层与 a11y。理由：

| 项 | 说明 |
|---|---|
| 复用壳而非裸 Popover | `FloatingEntry` 已封装 `role="dialog"` + `aria-haspopup/expanded/controls/label`（`:73-77, 88-92`），且处理了两个自建必漏的坑：**打开后焦点入卡**（`:39-48`）、**Esc 关闭后焦点回入口**（`:50-53`）。漏焦点管理 = 键盘用户 Tab 进不去面板内容、关闭后焦点丢失（无障碍缺陷） |
| 入口热区 | `FloatingEntry` 的 `.taskinfo-entry` 已定义 hover 底 `#f0f0f0` + focus 2px 蓝 outline（`index.css:253-274`），本功能触发按钮复用同一规格，不另造热区 |
| 定位 | 由 `FloatingEntry` 的 `placement` 参数控制（`bottomLeft`/`bottomRight`），本功能取 **`bottomRight`**（贴工具行右缘向左展开，与摘要右侧的按钮位置呼应） |
| 卡片样式 | 经 `cardStyle` 注入宽/限高；内容经 `content` 注入 GroupView / SpecView（内容自持 a11y 如 `role="log"`） |
| 与 HITL 模态框 | `AuthorizationModal` 为模态（`z-index` 更高 + 遮罩），**命中安全确认期间浮层不自动关闭**（Popover 不响应遮罩点击），确认后恢复；两者不同时操作，无冲突 |
| 单例互斥 | 仍由 `openPanelIndex` 单一真源控制（DC-07），壳只负责呈现 |

#### 3.5.1 面板结构

```
┌────────────────────────────────────────────────────────┐
│ </> write · 参数 6 项    [分组│规格表]      [复制]   ✕    │  ← 面板头
├────────────────────────────────────────────────────────┤ ← 1px BORDER.DEFAULT
│                                                        │
│              {view === 'group' ? <GroupView/>         │
│                                 : <SpecView/>}         │
│                                                        │
└────────────────────────────────────────────────────────┘
   外壳 = FloatingEntry（内含 antd Popover + role="dialog"）
   卡片底 = BG.SECONDARY + BORDER.DEFAULT 1px + Radius.SM 4
```

> 面板头复制按钮与树头复制按钮**均为 `CopyButton`**（DC-20），差别仅定位方式：树头沿用默认绝对定位，面板头传 `inline` 取消绝对定位（`CopyButton` 现为 `position:absolute` 直接放进面板头会脱离文档流、压住标题）。
>
> **`CopyButton` 唯一改动**：新增可选 prop `inline?: boolean`（默认 `false`）。既有 5 处调用（markdown 代码块）行为**零变化**，不违反"禁 backward"。两处复制内容格式不同（见 §3.5.5），实施时勿混用。

#### 3.5.2 GroupView（乙 · 分组卡片 · 默认）

按 §2.3.2 判定优先级链分**五类**，每类：左侧 2px 色条 + 类名小字标题，类内键值行。**空类不渲染**（如无 boolean 参数则不显「开关」条）。

**色条用中性阶，不占用语义色**

| 类 | 色条色 | 说明 |
|---|---|---|
| 路径 | `Colors.BORDER.STRONG` `#bfbfbf` | 中性灰最深 |
| 开关 | `Colors.BORDER.DEFAULT` `#d9d9d9` | 中性灰中 |
| 编码 | `Colors.BORDER.DEFAULT` `#d9d9d9` | 中性灰中 |
| 正文载荷 | `Colors.BORDER.VERTICAL` `#e8e8e8` | 中性灰最浅 |
| 其他 | `Colors.BORDER.LIGHT` `#f0f0f0` | 中性灰最浅 |

> **为何不用语义色**：系统的 `Colors.WARNING(#AD6800)` / `ACCENT_ORANGE(#d4380d)` / `SUCCESS` / `ERROR` 承载**状态语义**（警告、事件计数、成功、失败）。拿它们当"参数分类色标"，用户会误读为"这个参数有警告/异常"。分类是**结构**，状态是**语义**，两者必须用不同视觉通道。故分类只用中性灰阶，类名靠**文字**区分。

#### 3.5.3 SpecView（甲 · 规格表）

固定两列：key 列宽 140px 右对齐灰字（`TEXT.SECONDARY`），value 列左对齐深字（`TEXT.PRIMARY`）；行间 1px `Colors.BORDER.LIGHT` 分割线；巨型值整宽跨行成代码块（`BG.SECONDARY` + `BORDER.DEFAULT` + `Radius.SM` + `FontFamily.MONO` + `FontSize.CODE`，与 `MarkdownText` 代码块同款）。

**巨型值折叠切换规格（复用系统惯例）**：一律用 **`CircleArrow`(size=14, color=`Colors.PRIMARY`) + 文案「展开」/「收起」**（同 `CollapsibleText.tsx:109-115`），**不用 `▸`/`▾` 裸字符**——裸字符是本方案 v1.0 的旧写法，与系统既有折叠观感不一致。

#### 3.5.4 视图切换

```tsx
// 模块级持久常量（防每次渲染重建，同 REJECT_LABEL_MAP 范式）
export const PARAMS_VIEW_MAP = { group: '分组', spec: '规格表' } as const;
export type ParamsView = keyof typeof PARAMS_VIEW_MAP;
const VIEW_LS_KEY = 'step.params.view';
```

| 项 | 规格 |
|---|---|
| 控件 | antd `Segmented` |
| 默认 | `group`（分组） |
| 持久化 | `localStorage[VIEW_LS_KEY]`，读取失败回落 `group`（fail-safe） |
| 切换行为 | 仅换视图，数据与滚动位置**不重置** |

#### 3.5.5 巨型值与复制（两视图共用）

> 方案层口径见 §2.3.3；本节为其实现口径，二者一致，改动须同步。

| 条件 | 呈现 |
|---|---|
| 含换行 或 长度 > `HUGE_VALUE_CHARS`(200) | 折叠 `共 N 行 · 展开`；展开后限高 `Size.PARAMS_PANEL_MAX_H` 内部滚动 |
| list / dict | `JSON.stringify(v, null, 2)` 多行缩进，同上限高；**嵌套深度不限**（DC-15） |
| `undefined` / `null` | `(空)` 占位（解决 A7） |

> **与展开区 JSON 树的口径差异**：浮层按**字符数**（200）判定巨型值并折叠；展开区 JSON 树**只按是否含换行**判定，不设字符阈值（§3.4.1 已说明理由）。两处均为限高滚动，方向一致。

**浮层复制（DC-16）**：面板头复制按钮复制 **`key=value` 逐行**格式（非 JSON）——

```
file_path = F:\OmniAgentAs-repair\backend\app\main.py
encoding = utf-8
shell_type = powershell
append = false
timeout = 30
content = 共 312 行
```

选择逐行而非 JSON 的理由：浮层面向**人工核对与逐项比对**（甲规格表本就是两列对照），`key=value` 一行一项可直接读、直接贴进工单；JSON 格式由展开区复制承担（DC-17），两者互补不重复。

### 3.6 挂载位置（ToolCallLine.tsx）

浮层按钮**固定在工具行内**（D1 裁定乙），展开区**原位保留**：

```tsx
<div key={...} style={{ marginTop: Spacing.XS }}>
  {/* ① 工具行（flex 容器, gap: Spacing.SM），D2 裁定顺序：droplet + 工具名 + 结果摘要 + 折叠箭头 + </>浮层参数按钮 */}
  {/*    </>浮层参数按钮 = FloatingEntry 的 children，插在 <CircleArrow/> 之后（行尾）；其 onClick 内 e.stopPropagation() */}
  <div role="button" onClick={toggleTool}>...</div>

  {/* ② 展开区：改 JSON 树（原位保留，仅随 isOpen 出现/消失） */}
  {isOpen && <ParamsTree entries={paramEntries} />}

  {/* ③ 结果区（不变） */}
  {isOpen && <ToolResultRenderer step={singleStep} />}

  {/* ④ 浮层本体：外壳 FloatingEntry 的 children 即①中的浮层参数按钮；content 为 ParamsPanel */}
  <ParamsPanel toolName={t.tool} params={t.params ?? {}}>
    {openPanelIndex === i && <GroupSpecSwitcher />}
  </ParamsPanel>
</div>
```

> **注意**：`ParamsPanel` 的 props **不含 `open`**（见 §3.5）——开合由 `FloatingEntry` 的 `open`/`onOpenChange` 承担，`openPanelIndex` 只负责"哪个工具的面板开着"这一单例互斥语义（DC-07），由外层把它映射成 `FloatingEntry` 的 `open` 布尔值。

**收起态一行的三部分与顺序（D2 裁定）**

```
💧 read成功:从第1-50行   ▸   </> 浮层参数
 └ ① 内容信息            └②      └ ③
   水滴(状态)+工具名
   +结果摘要(单行省略)
                          ② 折叠箭头：切换本行展开/收起（展开区+结果区）
                          ③ </>浮层参数按钮：开关浮层面板，与 ② 互不相干
```

**③ 按钮文案定稿（D3 裁定）**：标签文字为 **`浮层参数`**，不是 `参数`——"参数"二字在流水线语境里已被"展开区（JSON 树）"占用，同名会让用户误以为两者是同一个东西。`浮层参数` 一眼区分「就地展开的那块」与「弹出来的面板」。

**门控口径**：③ 按钮在工具行内，与 `isOpen` **无关**——折开收起恒在原位，故展开区与结果区的出现/消失不影响按钮位置（D1 裁定乙的核心目的）。

**按钮交互**：③ 虽在 `role="button"` 容器内，但 `onClick` 内 `e.stopPropagation()`，故点浮层参数按钮**不会**触发工具行折叠（解决 I1/B1）；反之点 ② 之外的其他区域仍照常折叠整行。

**图标规格**：③ 用 **antd `CodeOutlined` + 文字 `浮层参数`**（D3 定稿），**不用 `GearIcon`**——`GearIcon` 在系统里的语义是「工具执行等待」转圈齿轮（`ToolCallLine.tsx:248` `ToolWaitingIcon`），复用会让用户误以为参数区正在加载。antd SVG 图标是项目既定规范（见 `ToolCallLine.tsx:96-109` `REJECT_ICON_MAP` 全量用 antd 禁 emoji）。

**按钮无箭头**：面板开合以按钮**文字色**标识（关=`Colors.TEXT.SECONDARY`，开=`Colors.PRIMARY`），避免与 ② 的折叠箭头混淆成"两级折叠"。

**按钮热区复用 `.taskinfo-entry`**：③ 用 `FloatingEntry` 作外壳后，热区自动继承 `index.css:253-274` 的既有规格（`min-width:32` / `min-height:20` / `border-radius:8` / hover 底 `#f0f0f0` / focus-visible 2px 蓝 outline），**不另造热区样式**。

### 3.7 高度链路验证（全局）

| 层级 | 改造前 | 改造后 |
|---|---|---|
| ⑧ 工具行 | `minHeight:32` + 展开后随参数区暴涨 | 不变 |
| ⑩ 展开区参数 | 无上限，参数行数 × 18（含巨型值铺满） | **顶层键默认折叠，恒 (键数+1) × 16** |
| ⑩-b 树节点展开体 | — | **限高 240px 内部滚动**（每层各自承担，DC-15 不限深度） |
| ⑪ 结果区 | 不变 | 不变 |
| 浮层 | — | **移出流内**，高度增长 0 |
| ⑥ 右栏内容高度 | 参数全部累加，N 工具 N 倍叠加 | 仅按**键数**累加，与参数值体量无关 |

`write`（content 300 行）单例：改造前 5400px+ → 改造后 112px，**降 97.9%**。

### 3.8 验收标准

> 编号前缀 `T`（Test），与 §2.5 视觉改造清单的 `V`（Visual）区分，避免同号歧义。

| # | 验收项 |
|---|---|
| T1 | `write` 工具（content 300 行）展开后，**该工具展开区**高度 ≤ 120px（DevTools 量展开区容器，非右栏总高） |
| T2 | 并行 5 个工具全部点开，右栏内容高度按**键数**累加，不按值体量累加 |
| T3 | 点树节点任意位置，**不触发**工具行折叠（B1 修复） |
| T4 | 展开巨型节点不触发整页自动滚底（B2 修复） |
| T5 | 浮层打开时，右栏滚动位置不变；浮层展开/切换视图不引起右栏高度变化 |
| T6 | 任意时刻最多一个浮层；点另一工具的浮层参数按钮，旧浮层自动关闭 |
| T7 | 参数值对比度 ≥ 4.5:1（浮层 `Colors.TEXT.PRIMARY` 生效；JSON 树值 `TEXT.STRONG` 对比度更高） |
| T8 | 展开区 JSON 树顶层键默认折叠；`content` 显示 `共 N 行` |
| T9 | 树节点展开体限高 240px，超出内部滚动，不撑破展开区 |
| T10 | 浮层默认「分组」视图，五类（路径/开关/编码/正文载荷/其他）按 §2.3.2 优先级链判定且不重复落组、空类不渲染、色条正确；切「规格表」后视图正确、滚动位置不重置 |
| T11 | 视图选择写入 localStorage，刷新页面后沿用 |
| T12 | 对象参数以多行缩进 JSON 显示；空值显示 `(空)` |
| T13 | 长路径在展开区与浮层均不断词中间（`break-word`，非 `break-all`）；字体为 `FontFamily.MONO` |
| T14 | 面板头复制与树头复制均能复制，产出格式符合 T23 |
| T15 | `Escape` / 点外面 / `✕` 三种方式均可关闭浮层 |
| T16 | 现有功能无退化：每工具独立展开、结果区渲染、并行同名工具不串味、展开区仍在原位 |
| T17 | `npm run check:full` 通过（typecheck + typecheck:e2e + lint + lint:e2e + format:check） |
| T18 | 收起态一行渲染顺序为 `水滴+工具名+摘要 │ 折叠箭头(CircleArrow) │ </>浮层参数`；展开态顺序不变（D2） |
| T19 | 点 `浮层参数` 不触发工具行折叠；点该行其他区域仍照常折叠（T3 的补充分支） |
| T20 | 浮层参数按钮无箭头；面板打开时按钮文字色为 `PRIMARY`，关闭时为 `TEXT.SECONDARY` |
| T21 | 按钮文案为 `浮层参数`，全仓不出现裸标签 `参数` 作该按钮文案（D3，避免与展开区混淆） |
| T22 | JSON 树嵌套对象**不限层数**，逐层可独立折叠；每层展开体各自限高 240px 不破版（DC-15） |
| T23 | 面板头复制产出 `key=value` 逐行文本；树头复制产出格式化 JSON，两者不同（DC-16/DC-17） |
| T24 | 点折叠箭头收起工具行时**浮层仍打开**；点 `✕` 关浮层时**工具行仍保持展开**；切任务时二者同时清理（DC-18） |
| T25 | 窄屏（视口 < 640px）面板宽 = `min(视口-32px, 640)`，不低于 320，无横向滚动条；与 HITL 模态框同屏时浮层不误关 |
| T26 | **视觉一致性**：面板与 JSON 树**不引入任何新颜色**，全部取自既有 `Colors.*`；无 `Colors.JSON.*` 语法色（VC7） |
| T27 | 浮层外壳为 `FloatingEntry`，打开后焦点入卡、Esc 关闭后焦点回入口——与系统其它浮层行为完全一致（VC3） |
| T28 | 两处复制按钮均为 `CopyButton` 组件（1.5s「已复制」回退 + `aria-label`）；面板头传 `inline` 取消绝对定位；markdown 代码块既有 5 处调用行为零变化（DC-20） |
| T29 | 折叠切换一律 `CircleArrow(14, PRIMARY)` + 「展开/收起」，全文无 `▸`/`▾` 裸字符切换（VC5） |
| T30 | 分类色条全部取自 `Colors.BORDER.*` 中性灰阶，无 `WARNING`/`ACCENT_ORANGE`/`SUCCESS`/`ERROR` 等语义色（VC4） |
| T31 | 浮层参数按钮图标为 antd `CodeOutlined`（非 `GearIcon`，后者语义为"工具执行等待"）；热区继承 `.taskinfo-entry` 规格（VC8/VC9） |
| T32 | 参数区与页面既有代码块并排时观感一致：同 `BG.SECONDARY` + `BORDER.DEFAULT` + `Radius.SM` + `FontFamily.MONO` + `FontSize.CODE`（VC2/VC10/VC11） |
| T33 | `ParamsPanel` 的 props **只有** `toolName`/`params`/`onClose`（见 §4.0 D-3）；开合由 `FloatingEntry` 承担，编译通过（`npm run typecheck` 零错误） |
| T34 | 全文无「JSON 语法着色」残留、无自造复制按钮残留（DC-19/DC-20 已落地，代码与文档同步） |

### 3.9 改造前后对比示意

**改造前**（平铺全量，撑页）：

```
● 并行 2 个工具 [write, read]
  💧 write成功:从第1-200行   ▾
      file_path: F:\...\main.py
      encoding: utf-8
      content: def main():
      content: import os
      content: ...（300 行 → 右栏内容 5400px）
      shell_type: powershell
      append: false
      成功:从第1-200行
  💧 read成功:从第1-50行  ▸
    ...（再点开 → 高度继续叠加）
```

**改造后**（展开区 JSON 树恒高 + 浮层双视图）：

```
● 并行 2 个工具 [write, read]
  💧 write成功:从第1-200行  ▾   </> 浮层参数   ← 按钮固定在工具行行尾
      ▾ {                          [复制]        ← 树头复制（复用 CopyButton，格式化 JSON）
          ▸ "file_path"    : "F:\...\backend\app\main.py"
          ▸ "encoding"     : "utf-8"
          ▸ "shell_type"   : "powershell"
          ▸ "append"       : false
          ▸ "timeout"      : 30
          ▸ "content"      : "共 312 行"
        }                              （7 行 × 16 = 112px 恒定）
      成功:从第1-200行
  💧 read成功:从第1-50行  ▸   </> 浮层参数   ← 收起态按钮位置不变

点 write 的「浮层参数」→ write 行附近浮出（外壳 FloatingEntry + antd Popover）：
┌────────────────────────────────────────────────────────┐
│ </> write · 参数 6 项    [分组│规格表]      [复制]   ✕    │
├────────────────────────────────────────────────────────┤
│ ▌ 路径                                                     │
│    file_path      F:\...\backend\app\main.py               │
│ ▌ 开关                                                     │
│    append         关闭                                      │
│    shell_type     powershell                               │
│ ▌ 编码                                                     │
│    encoding       utf-8                                    │
│ ▌ 正文载荷                                                 │
│    content        共 312 行                     ▸ 展开      │
│  ┌──────────────────────────────────────────────────┐   │
│  │  1  from fastapi import FastAPI                  │   │
│  └──────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────┘
  高度增长 0；切「规格表」→ 同一份数据的另一种排布
  面板头复制 → key=value 逐行（与树头复制的格式化 JSON 不同）
```

### 3.10 已裁定事项（留档）

| # | 事项 | 裁定 | 结果 |
|---|---|---|---|
| D1 | 浮层触发按钮的纵向位置是否随展开态移动 | **北京老陈 2026-10-13 裁定「乙」**：按钮固定在工具行内，跟在结果摘要右侧 | 位置恒定，展开区/结果区出现消失均不影响按钮；§2.1/§2.2/§2.4 S2/§3.6/§3.9 已全部同步 |
| D2 | 收起态一行三部分（内容信息 / 折叠箭头 / 参数按钮）的排列顺序 | **北京老陈 2026-10-13 裁定「乙」**：内容 │ 折叠箭头 │ 参数按钮（参数按钮在行尾） | §3.6 代码块与"收起态一行三部分与顺序"图已按此定稿；浮层参数按钮**无箭头**，开合以**文字色**标识，避免与折叠箭头混淆成两级折叠 |
| D3 | 浮层触发按钮的文案标签 | **北京老陈 2026-10-13 裁定**：文案由 `参数` 改为 **`浮层参数`** | 理由：`参数` 二字已被「就地展开区（JSON 树）」占用，同名会让用户误认两者是同一个东西。§2.2/§3.6/§3.9 示意图、T18/T19/T21 全部同步 |
| U1 | JSON 树嵌套深度是否限制 | **北京老陈裁定「不限制」** | DC-15；深度失控由每层展开体限高 240px 控制 |
| U2 | 浮层打开时收起工具行，是否连带关浮层 | **北京老陈裁定「各自独立 不互相牵连」** | DC-18；§3.2 两态独立性对照表 |
| U3 | 两处复制的内容格式 | **浮层 = `key=value` 逐行；展开区 JSON 树 = 格式化 JSON** | DC-16/DC-17；并**在树头增设复制按钮**（原设计展开区无复制入口；按钮复用 `CopyButton`，见 DC-20） |

## 第4章   详细设计实施代码

### 4.0 本章与前三章的差异登记（**最终口径，冲突以此为准**）

> 实施前先读本表。前三章为设计推演，本章为落地时按 KISS/DRY 收敛后的**最终可实施口径**。

| # | 前三章写法 | 本章落地写法 | 变更理由 |
|---|---|---|---|
| D-1 | §2.7 I1「浮层按钮与树节点区加 `stopPropagation`」 | **结构性修复**：`ParamsTree` 移出 `role="button"` 容器外层 | 加 `stopPropagation` 只是补丁：用户在展开态点选/复制长文本时，`stopPropagation` 拦住了父级，但**节点自身**的 `onClick` 仍会切换折叠态 → 选不中文字。移出按钮容器后两者都不需要，是 KISS 根治 |
| D-2 | §3.4 `ParamsTreeProps` 含 `onNodeClick?`（外层接 stopPropagation） | **删除该 prop** | D-1 的结构性修复后无处可接，属死接口（YAGNI） |
| D-3 | §3.5 `ParamsPanelProps = { toolName, params, children }` | **`{ toolName, params, onClose }`** | T15 要求 `✕` 可关闭，而 `✕` 在面板内 → 必须有 `onClose`；`children` 无消费方（内容就是分组/规格表两视图），YAGNI 删除 |
| D-4 | §3.4.3 尺寸令牌 3 个 | **4 个**，增 `PARAMS_PANEL_BODY_MAX_H: 480` | 面板整体需有高度上限，否则 23 项参数的面板会超出视口；`PARAMS_PANEL_MAX_H` 只管**单个值**展开体 |
| D-5 | §3.5 「面板宽度接系统断点矩阵」 | **纯 CSS 响应式**：`width:640 + minWidth:320 + maxWidth:calc(100vw - 32px)` | 断点矩阵需 JS 监听 resize（重渲染+状态），纯 CSS 三行解决且零重渲染。T25 的落法因此得以自然满足 |
| D-6 | §3.6 「浮层按钮 = FloatingEntry 的 children，插在 CircleArrow 之后」 | **确认可行**：`FloatingEntry` 触发器自带 `e.stopPropagation()`（`FloatingEntry.tsx:98`），置于工具行 flex 内安全 | 原设计担心冒泡，实读源码已解决，无需额外包装 |

### 4.1 代码列表

| # | 文件 | 类型 | 行数变化 | 对应设计 |
|---|---|---|---|---|
| 1 | `frontend/src/utils/stepStyles.ts` | 改 | +8 | §3.4.3 |
| 2 | `frontend/src/components/markdown/CopyButton.tsx` | 改 | +6 −0 | §3.5.1 |
| 3 | `frontend/src/features/chat/components/pipeline/ParamsTree.tsx` | **新建** | +约 150 | §3.4 |
| 4 | `frontend/src/features/chat/components/pipeline/ParamsPanel.tsx` | **新建** | +约 200 | §3.5 |
| 5 | `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx` | 改 | +约 40 −约 95 | §3.2 §3.6 |
| 6 | `frontend/src/features/chat/components/pipeline/ParamsTree.test.tsx` | 新建 | +约 90 | §3.1 第 5 项 |

**实施顺序**：1 → 2 → 3 → 4 → 5（`3/4` 依赖 `1/2` 的令牌与组件）。**第 6 项按 AGENTS 铁规不提交**，本地保留。

**全局高度链路复核**（改前 → 改后，见 §3.7）：

| 层 | 改前 | 改后 | 代码位置 |
|---|---|---|---|
| ⑧ 工具行 | `minHeight:32`，不变 | 不变 | `ToolCallLine.tsx:190-209` 未动 |
| ⑩ 展开区 | 无上限，参数行数 × 18px | **恒 (键数+1) 行 × 16px**，节点展开体各自限高 240px 内部滚动 | `ParamsTree` 顶层键默认折叠 + `maxBodyHeight` |
| ⑪ 结果区 | `marginTop:2` | 不变 | `ToolCallLine.tsx:440-459` 未动 |
| 浮层 | — | **移出流内**，高度增长 0 | `FloatingEntry` + antd `Popover`（portal） |

---

### 4.2 `frontend/src/utils/stepStyles.ts` —— 新增 `Size` 令牌

**改动位置**：文件末尾 `Colors` 常量之后、`getStepLabel` 等函数之前。

```ts
// 2026-10-13 小欧 - 文档[29]§3.4.3/DC-19: 新增**尺寸**令牌组; 严禁新增颜色令牌(全部复用既有 Colors.*)
export const Size = {
  PARAMS_PANEL_MAX_H: 240, // 巨型值 / JSON 树节点展开体限高（每层各自承担，DC-15）
  PARAMS_PANEL_MAX_W: 640, // 浮层面板最大宽（甲规格表两列对照需宽）
  PARAMS_PANEL_MIN_W: 320, // 浮层面板最小宽（窄屏下限，见 §4.5 响应式三件套）
  PARAMS_PANEL_BODY_MAX_H: 480, // 2026-10-13 小欧 - 面板内容区总限高(D-4): 防止 23 项参数的面板超出视口
} as const;
```

**规范判定**：SRP（只管尺寸不管颜色）✅ ｜ KISS-DIRECT（4 个常量，无逻辑）✅ ｜ 无魔法数字 ✅ ｜ 命名沿用既有「名 + 量纲」风格（`BorderWidth`/`FontSize`）✅

---

### 4.3 `frontend/src/components/markdown/CopyButton.tsx` —— 新增 `inline` 变体

**改动 1**：接口加可选 prop

```diff
 interface CopyButtonProps {
   /** 点击复制的原文(必须由调用方保证不含按钮自身的文本) */
   text: string;
+  /**
+   * 2026-10-13 小欧 - 文档[29]§3.5.1: 行内模式(浮层面板头)。默认 false 保持绝对定位
+   * (代码块右上角用法); true 时取消绝对定位, 用于面板头等常规流内位置。
+   * 既有 5 处调用零变化(禁 backward)。
+   */
+  inline?: boolean;
 }
```

**改动 2**：组件签名 + 样式分支

```diff
-const CopyButton: React.FC<CopyButtonProps> = ({ text }) => {
+const CopyButton: React.FC<CopyButtonProps> = ({ text, inline = false }) => {
   const [copied, setCopied] = useState(false);
   ...
   return (
     <button
       type="button"
       onClick={onCopy}
       aria-label={copied ? '已复制' : '复制代码'}
       style={{
-        position: 'absolute',
-        top: Spacing.XS - 2,
-        right: Spacing.XS,
+        // 2026-10-13 小欧 - 文档[29]§3.5.1: 定位按 inline 分支, 避免面板头内脱离文档流压住标题
+        ...(inline
+          ? {}
+          : {
+              position: 'absolute' as const,
+              top: Spacing.XS - 2,
+              right: Spacing.XS,
+            }),
         fontSize: 11,
         lineHeight: '14px',
         padding: '2px 6px',
```

**规范判定**：OCP（加可选 prop 扩展，既有调用零变化）✅ ｜ DRY（不新建按钮组件）✅ ｜ 默认值兜底 fail-safe ✅

---

### 4.4 `frontend/src/features/chat/components/pipeline/ParamsTree.tsx` —— 新建

**全文**（展开区 JSON 树，戊方案）：

```tsx
// 编辑历史: 2026-10-13 小欧 - 新建: Step 页参数区 JSON 树(文档[29] §3.4/DC-04/DC-15/DC-17/DC-19/DC-20)
//   顶层键默认折叠 · 每层展开体限高滚动 · 嵌套不限深度 · 树头复制(格式化 JSON) — 小欧 2026-10-13
import React, { useCallback, useMemo, useState } from 'react';
import { CircleArrow } from '@/components/CircleArrow';
import { CopyButton } from '@/components/markdown/CopyButton';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  Icon,
  Radius,
  Size,
  Spacing,
} from '@/utils/stepStyles';

/** 节点三态: 标量(恒单行无箭头) / 长文本(折叠为"共N行") / 分支(list|dict) */
type NodeKind = 'scalar' | 'body' | 'branch';

/**
 * 2026-10-13 小欧 - 树内口径(§3.4.1「长值在树内的截断口径」):
 *   只看是否含换行, **不设字符阈值**——与浮层的 200 字阈值是两套口径, 刻意区分。
 *   树内已天然限高(每层 240px), 无需再按字符折叠。
 */
const classify = (v: unknown): NodeKind => {
  if (typeof v === 'string') return v.includes('\n') ? 'body' : 'scalar';
  if (typeof v === 'object' && v !== null) return 'branch';
  return 'scalar';
};

const displayScalar = (v: unknown): string =>
  v === undefined || v === null ? '(空)' : String(v);

const branchEntries = (v: unknown): Array<[string, unknown]> =>
  typeof v === 'object' && v !== null
    ? Object.entries(v as Record<string, unknown>)
    : [];

const branchSummary = (v: unknown): string =>
  `{…} ${branchEntries(v).length} 项`;

// ==================== 单节点 ====================

interface ParamNodeProps {
  nodeKey: string;
  label: string;
  value: unknown;
  depth: number;
  isExpanded: (key: string) => boolean;
  onToggle: (key: string) => void;
  maxBodyHeight: number;
}

/** 2026-10-13 小欧 - 递归自渲染(DC-15 不限嵌套深度): 深度由数据自身决定 */
const ParamNode: React.FC<ParamNodeProps> = ({
  nodeKey,
  label,
  value,
  depth,
  isExpanded,
  onToggle,
  maxBodyHeight,
}) => {
  const kind = classify(value);
  const foldable = kind !== 'scalar';
  const open = foldable && isExpanded(nodeKey);
  const summary =
    kind === 'body'
      ? `共 ${String(value).split('\n').length} 行`
      : kind === 'branch'
        ? branchSummary(value)
        : displayScalar(value);

  const toggle = () => onToggle(nodeKey);
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggle();
    }
  };

  return (
    <div style={{ marginLeft: depth * Icon.BOX }}>
      <div
        role={foldable ? 'button' : undefined}
        tabIndex={foldable ? 0 : undefined}
        aria-expanded={foldable ? open : undefined}
        onClick={foldable ? toggle : undefined}
        onKeyDown={foldable ? onKeyDown : undefined}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          fontFamily: FontFamily.MONO,
          fontSize: FontSize.CODE,
          lineHeight: `${FontSize.CODE + Spacing.XS}px`,
          color: Colors.TEXT.SECONDARY,
          cursor: foldable ? 'pointer' : 'default',
        }}
      >
        {foldable && (
          <CircleArrow
            size={14}
            color={Colors.PRIMARY}
            expanded={open}
            animated={false}
          />
        )}
        <span style={{ color: Colors.TEXT.SECONDARY }}>{label}</span>
        <span style={{ color: Colors.TEXT.STRONG }}>: {summary}</span>
      </div>
      {/* 分支子树: 深度 +1, 由每个展开体各自限高(DC-15) */}
      {open && kind === 'branch' && (
        <div style={{ marginTop: Spacing.XS - 2 }}>
          {branchEntries(value).map(([k, v], idx) => {
            const childKey = `${nodeKey}/${k}/${idx}`;
            return (
              <ParamNode
                key={childKey}
                nodeKey={childKey}
                label={k}
                value={v}
                depth={depth + 1}
                isExpanded={isExpanded}
                onToggle={onToggle}
                maxBodyHeight={maxBodyHeight}
              />
            );
          })}
        </div>
      )}
      {/* 长文本: <pre> 限高内部滚动, 不做字符级截断(内容完整可复制) */}
      {open && kind === 'body' && (
        <div
          style={{
            marginLeft: Icon.BOX,
            marginTop: Spacing.XS - 2,
            maxHeight: maxBodyHeight,
            overflowY: 'auto',
          }}
        >
          <pre
            style={{
              margin: 0,
              padding: Spacing.SM,
              background: Colors.BG.SECONDARY,
              border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
              borderRadius: Radius.SM,
              fontFamily: FontFamily.MONO,
              fontSize: FontSize.CODE,
              lineHeight: `${FontSize.CODE + Spacing.XS}px`,
              color: Colors.TEXT.STRONG,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {String(value)}
          </pre>
        </div>
      )}
    </div>
  );
};

// ==================== 树根 ====================

interface ParamsTreeProps {
  entries: Array<[string, unknown]>;
  /** 每层展开体限高, 默认 Size.PARAMS_PANEL_MAX_H(240) */
  maxNodeBodyHeight?: number;
}

/**
 * ParamsTree - 展开区 JSON 树(戊方案)
 *
 * 2026-10-13 小欧: 顶层键**默认折叠**(全折叠), 故展开区高度 = (键数+1) 行 × 16px,
 * 与参数值体量无关 —— 这是 §1.4 C1/C2 的根治点。
 *
 * @author 小欧
 * @since 2026-10-13
 */
const ParamsTree: React.FC<ParamsTreeProps> = ({
  entries,
  maxNodeBodyHeight = Size.PARAMS_PANEL_MAX_H,
}) => {
  const [expandedKeys, setExpandedKeys] = useState<ReadonlySet<string>>(
    () => new Set()
  );
  // 2026-10-13 小欧 - 用 Set 承载展开态而非布尔数组: key 是路径字符串, 新增/删除无需考虑下标对齐,
  // 且嵌套深度不定(DC-15)时布尔数组不可用
  const isExpanded = useCallback(
    (key: string) => expandedKeys.has(key),
    [expandedKeys]
  );
  const onToggle = useCallback((key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);
  const copyText = useMemo(
    () => JSON.stringify(Object.fromEntries(entries), null, 2),
    [entries]
  );

  return (
    // position:relative 是 CopyButton 绝对定位的包含块(DC-17 树头复制)
    <div
      style={{
        position: 'relative',
        marginTop: Spacing.XS,
        padding: Spacing.XS,
        background: Colors.BG.SECONDARY,
        // 2026-10-13 小欧 - R3 根治(第七轮倒推核查): 与 §3.4.3 复用表对齐, 用 BORDER.DEFAULT。
        //   初稿用的 BORDER.LIGHT(#f0f0f0) 与同为"代码容器"的巨型值 <pre> 块(BORDER.DEFAULT #d9d9d9)
        //   不一致, 两块并排时边框一深一浅
        border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
        borderRadius: Radius.SM,
        fontFamily: FontFamily.MONO,
        fontSize: FontSize.CODE,
        lineHeight: `${FontSize.CODE + Spacing.XS}px`,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          color: Colors.TEXT.STRONG,
        }}
      >
        <CircleArrow
          size={14}
          color={Colors.PRIMARY}
          expanded
          animated={false}
        />
        {/* 2026-10-13 小欧 - 核查订正: 树根标签只写 `{`, 与 §3.4.1 结构图一致。
            初稿写「树根(恒展开)」是把注释写进了 UI, 属实现细节泄漏到用户界面 */}
        <span>{'{'}</span>
        <CopyButton text={copyText} />
      </div>
      {entries.map(([k, v], idx) => {
        const nodeKey = `${k}/${idx}`;
        return (
          <ParamNode
            key={nodeKey}
            nodeKey={nodeKey}
            label={k}
            value={v}
            depth={0}
            isExpanded={isExpanded}
            onToggle={onToggle}
            maxBodyHeight={maxNodeBodyHeight}
          />
        );
      })}
    </div>
  );
};

export { ParamsTree };
export default ParamsTree;
```

**规范判定**：

| 规范 | 判定 |
|---|---|
| SRP | `ParamsTree` 只管"树的展开态与渲染"；`ParamNode` 只管"单节点"；值格式化是 3 个纯函数 ✅ |
| KISS-DIRECT | 展开态用 `Set<string>` + 两个 `useCallback`，无 useMemo/useRef/forwardRef 冗余 ✅ |
| DRY | `key: value` 渲染只有一处（`ParamNode`），子树与长文本分支不重复 ✅ |
| OCP | 新增组件不改动任何既有组件签名 ✅ |
| 禁 backward | 全新文件，无旧逻辑兼容 ✅ |
| 无魔法数字 | 行高/字号全走 `FontSize.CODE + Spacing.XS`，缩进走 `Icon.BOX` ✅ |

---

### 4.5 `frontend/src/features/chat/components/pipeline/ParamsPanel.tsx` —— 新建

**全文**（浮层面板，乙默认 / 甲可切）：

```tsx
// 编辑历史: 2026-10-13 小欧 - 新建: 工具参数浮层面板(文档[29] §3.5/DC-05/DC-06/DC-16/DC-19/DC-21/DC-22)
//   乙·分组卡片(默认) / 甲·规格表 可切 · 五类语义分组 · 巨型值折叠限高 · 复制为 key=value 逐行 — 小欧 2026-10-13
import React, { useMemo, useState } from 'react';
import { Segmented } from 'antd';
import { CloseOutlined, CodeOutlined } from '@ant-design/icons';
import { CircleArrow } from '@/components/CircleArrow';
import { CopyButton } from '@/components/markdown/CopyButton';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  Radius,
  Size,
  Spacing,
} from '@/utils/stepStyles';

// ==================== 模块级常量(防每次渲染重建, 同 REJECT_LABEL_MAP 范式) ====================

/** 巨型值字符阈值(判定阈值非视觉令牌, 故不入 stepStyles — §3.4.3) */
const HUGE_VALUE_CHARS = 200;

const PATH_KEYS: ReadonlySet<string> = new Set([
  'path',
  'dir_path',
  'file_path',
  'source_path',
  'dest',
  'output_path',
]);
const ENCODING_KEYS: ReadonlySet<string> = new Set(['encoding', 'charset']);

export const PARAMS_VIEW_MAP = { group: '分组', spec: '规格表' } as const;
export type ParamsView = keyof typeof PARAMS_VIEW_MAP;
/**
 * 2026-10-13 小欧 - 核查订正: 此数组**不可加 `as const`**。
 *   `as const` 会产出 readonly tuple, 而 antd `Segmented.options` 的类型是
 *   `(string | number | SegmentedOption)[]`(可变数组) → readonly 不可赋值, tsc 报 TS2322。
 *   故去掉 `as const`, 让元素结构按推断走(仍能提供 label/value 字面量类型)。
 */
const VIEW_OPTIONS = [
  { label: PARAMS_VIEW_MAP.group, value: 'group' },
  { label: PARAMS_VIEW_MAP.spec, value: 'spec' },
];
const VIEW_LS_KEY = 'step.params.view';

/** 2026-10-13 小欧 - DC-21: 分类色只用 BORDER 中性灰阶, 语义色(警告/错误/成功)保留给状态 */
type Category = 'payload' | 'switch' | 'path' | 'encoding' | 'other';
const CATEGORY_META: ReadonlyArray<{
  id: Category;
  label: string;
  color: string;
}> = [
  { id: 'payload', label: '正文载荷', color: Colors.BORDER.VERTICAL },
  { id: 'switch', label: '开关', color: Colors.BORDER.DEFAULT },
  { id: 'path', label: '路径', color: Colors.BORDER.STRONG },
  { id: 'encoding', label: '编码', color: Colors.BORDER.DEFAULT },
  { id: 'other', label: '其他', color: Colors.BORDER.LIGHT },
];

// ==================== 值格式化(纯函数, 可单测) ====================

/** 「路径特征」: 同时含分隔符 **且** 末段有扩展名(§2.3.2 细则, 防误伤 SQL/代码片段) */
const isPathLike = (v: string): boolean => {
  if (!/[\\/]/.test(v)) return false;
  const last = v.split(/[\\/]/).pop() ?? '';
  return /\.[A-Za-z0-9]{1,8}$/.test(last);
};

/** §2.3.2 判定优先级链: 严格自上而下, 命中即止, 防一个参数落进两组 */
const categorize = (k: string, v: unknown): Category => {
  if (typeof v === 'object' && v !== null) return 'payload';
  if (typeof v === 'string' && (v.includes('\n') || v.length > HUGE_VALUE_CHARS))
    return 'payload';
  if (typeof v === 'boolean') return 'switch';
  if (PATH_KEYS.has(k) || (typeof v === 'string' && isPathLike(v)))
    return 'path';
  if (ENCODING_KEYS.has(k)) return 'encoding';
  return 'other';
};

const needFold = (v: unknown): boolean => {
  if (typeof v === 'object' && v !== null) return true;
  if (typeof v === 'string')
    return v.includes('\n') || v.length > HUGE_VALUE_CHARS;
  return false;
};

const summaryOf = (v: unknown): string => {
  if (v === undefined || v === null) return '(空)';
  if (typeof v === 'object')
    return `{…} ${Object.keys(v as object).length} 项`;
  if (typeof v === 'string' && needFold(v))
    return `共 ${v.split('\n').length} 行`;
  return String(v);
};

const fullTextOf = (v: unknown): string => {
  if (v === undefined || v === null) return '(空)';
  if (typeof v === 'object') return JSON.stringify(v, null, 2);
  return String(v);
};

/** DC-16: 浮层复制为 key=value 逐行(非 JSON), 面向人工核对/贴工单 */
const toKeyValueText = (params: Record<string, unknown>): string =>
  Object.entries(params)
    .map(([k, v]) => `${k} = ${summaryOf(v)}`)
    .join('\n');

const readView = (): ParamsView => {
  try {
    return window.localStorage.getItem(VIEW_LS_KEY) === 'spec'
      ? 'spec'
      : 'group';
  } catch {
    return 'group';
  }
};

// ==================== 巨型值(两视图共用) ====================

/** 折叠切换规格: CircleArrow(14,PRIMARY) + 「展开/收起」, 不用裸 ▸/▾(T29) */
const ParamValue: React.FC<{ value: unknown }> = ({ value }) => {
  const [open, setOpen] = useState(false);
  const foldable = needFold(value);
  const toggle = () => setOpen((p) => !p);
  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggle();
    }
  };

  if (!foldable) {
    return <span style={{ color: Colors.TEXT.PRIMARY }}>{summaryOf(value)}</span>;
  }
  return (
    <div>
      <span
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={toggle}
        onKeyDown={onKeyDown}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: Spacing.SM,
          cursor: 'pointer',
          color: Colors.PRIMARY,
          fontSize: FontSize.CODE,
          fontFamily: FontFamily.MONO,
        }}
      >
        <CircleArrow
          size={14}
          color={Colors.PRIMARY}
          expanded={open}
          animated={false}
        />
        {open ? '收起' : `${summaryOf(value)} · 展开`}
      </span>
      {open && (
        <pre
          style={{
            margin: `${Spacing.XS}px 0 0`,
            padding: Spacing.SM,
            maxHeight: Size.PARAMS_PANEL_MAX_H,
            overflowY: 'auto',
            background: Colors.BG.SECONDARY,
            border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
            borderRadius: Radius.SM,
            fontFamily: FontFamily.MONO,
            fontSize: FontSize.CODE,
            lineHeight: `${FontSize.CODE + Spacing.XS}px`,
            color: Colors.TEXT.STRONG,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
          }}
        >
          {fullTextOf(value)}
        </pre>
      )}
    </div>
  );
};

// ==================== 乙 · 分组卡片(默认) ====================

const GroupView: React.FC<{ params: Record<string, unknown> }> = ({
  params,
}) => {
  const buckets = useMemo(() => {
    const map = new Map<Category, Array<[string, unknown]>>();
    CATEGORY_META.forEach((c) => map.set(c.id, []));
    Object.entries(params).forEach(([k, v]) => {
      const bucket = map.get(categorize(k, v));
      if (bucket) bucket.push([k, v]);
    });
    return map;
  }, [params]);

  return (
    <div>
      {CATEGORY_META.map((c) => {
        const rows = buckets.get(c.id) ?? [];
        if (rows.length === 0) return null; // 空类不渲染(§3.5.2)
        return (
          <div key={c.id} style={{ marginTop: Spacing.SM }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: Spacing.SM,
              }}
            >
              <span
                style={{
                  width: 2,
                  height: 10,
                  borderRadius: 1,
                  background: c.color,
                }}
              />
              <span
                style={{
                  fontSize: FontSize.CODE,
                  color: Colors.TEXT.SECONDARY,
                }}
              >
                {c.label}
              </span>
            </div>
            <div style={{ marginLeft: Spacing.SM, marginTop: Spacing.XS }}>
              {rows.map(([k, v]) => (
                <div
                  key={k}
                  style={{
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: Spacing.SM,
                    marginTop: Spacing.XS - 2,
                  }}
                >
                  <span
                    style={{
                      width: 96,
                      flexShrink: 0,
                      fontFamily: FontFamily.MONO,
                      fontSize: FontSize.CODE,
                      color: Colors.TEXT.SECONDARY,
                      wordBreak: 'break-all',
                    }}
                  >
                    {k}
                  </span>
                  <span
                    style={{
                      flex: 1,
                      minWidth: 0,
                      fontFamily: FontFamily.MONO,
                      fontSize: FontSize.CODE,
                      wordBreak: 'break-word',
                    }}
                  >
                    <ParamValue value={v} />
                  </span>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

// ==================== 甲 · 规格表 ====================

const SpecView: React.FC<{ params: Record<string, unknown> }> = ({
  params,
}) => (
  <div>
    {Object.entries(params).map(([k, v]) => (
      <div
        key={k}
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: Spacing.SM,
          paddingTop: Spacing.XS,
          paddingBottom: Spacing.XS,
          borderBottom: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`,
        }}
      >
        <span
          style={{
            width: 140,
            flexShrink: 0,
            textAlign: 'right',
            fontFamily: FontFamily.MONO,
            fontSize: FontSize.CODE,
            color: Colors.TEXT.SECONDARY,
            wordBreak: 'break-all',
          }}
        >
          {k}
        </span>
        <span
          style={{
            flex: 1,
            minWidth: 0,
            fontFamily: FontFamily.MONO,
            fontSize: FontSize.CODE,
            wordBreak: 'break-word',
          }}
        >
          <ParamValue value={v} />
        </span>
      </div>
    ))}
  </div>
);

// ==================== 面板 ====================

interface ParamsPanelProps {
  toolName: string;
  params: Record<string, unknown>;
  /** T15: ✕ / Esc / 点外面关闭; 关闭动作回交 FloatingEntry 的 onOpenChange */
  onClose: () => void;
}

/**
 * ParamsPanel - 工具参数浮层面板(浮层开合/锚点/a11y/焦点管理全部由 FloatingEntry 承担,
 * 本组件只负责"渲染什么内容"与面板内样式 — SRP, 见 §3.5)
 *
 * @author 小欧
 * @since 2026-10-13
 */
const ParamsPanel: React.FC<ParamsPanelProps> = ({
  toolName,
  params,
  onClose,
}) => {
  const [view, setView] = useState<ParamsView>(readView);
  const entries = useMemo(() => Object.entries(params), [params]);
  const onViewChange = (next: ParamsView) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_LS_KEY, next);
    } catch {
      /* 隐私模式/存储禁用: 仅本次会话生效, 不阻断 */
    }
  };
  const copyText = useMemo(() => toKeyValueText(params), [params]);
  const onCloseKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClose();
    }
  };

  return (
    <div
      style={{
        background: Colors.BG.SECONDARY,
        border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
        borderRadius: Radius.SM,
        fontFamily: FontFamily.MONO,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          padding: Spacing.SM,
          borderBottom: `${BorderWidth.THIN}px solid ${Colors.BORDER.DEFAULT}`,
        }}
      >
        <CodeOutlined
          style={{ color: Colors.PRIMARY, fontSize: FontSize.CODE }}
        />
        <span
          style={{
            fontSize: FontSize.CODE,
            color: Colors.TEXT.STRONG,
            whiteSpace: 'nowrap',
          }}
        >
          {toolName} · 参数 {entries.length} 项
        </span>
        <span style={{ flex: 1 }} />
        <Segmented
          size="small"
          options={VIEW_OPTIONS}
          value={view}
          onChange={(v) => onViewChange(v as ParamsView)}
        />
        {/* DC-20: 面板头用 inline 变体, 否则绝对定位会压住标题 */}
        <CopyButton text={copyText} inline />
        <span
          role="button"
          tabIndex={0}
          aria-label="关闭参数面板"
          onClick={onClose}
          onKeyDown={onCloseKeyDown}
          style={{
            display: 'inline-flex',
            cursor: 'pointer',
            color: Colors.TEXT.SECONDARY,
            fontSize: FontSize.CODE,
            lineHeight: `${FontSize.CODE + Spacing.XS}px`,
          }}
        >
          <CloseOutlined />
        </span>
      </div>
      <div
        style={{
          padding: Spacing.SM,
          maxHeight: Size.PARAMS_PANEL_BODY_MAX_H,
          overflowY: 'auto',
        }}
      >
        {view === 'group' ? (
          <GroupView params={params} />
        ) : (
          <SpecView params={params} />
        )}
      </div>
    </div>
  );
};

export { ParamsPanel };
export default ParamsPanel;
```

**响应式（替代 D-5 的断点矩阵）**：宽窄自适应由 §4.6 的 `PARAMS_CARD_STYLE` 纯 CSS 三件套承担，本组件无需 `window.innerWidth` 逻辑。

**规范判定**：

| 规范 | 判定 |
|---|---|
| SRP | `ParamsPanel` 管壳与切换、`GroupView`/`SpecView` 管各自视图、`ParamValue` 管单值；格式化全在 6 个纯函数 ✅ |
| KISS-DIRECT | 无 `useRef`/`forwardRef`/`useReducer`；`readView` 单表达式 + try/catch 兜底，无中间层 ✅ |
| DRY | `ParamValue` 被两个视图共用，折叠逻辑只写一次 ✅ |
| LSP/ISP | `ParamValue` 单 prop `value`，无接口膨胀 ✅ |
| 禁魔法数字 | 限高走 `Size.*`，行高走 `FontSize.CODE + Spacing.XS`，key 列宽 96/140 为**布局常量**已就地标注用途 ✅ |
| 无障碍 | 折叠/关闭均可 Tab 聚焦 + Enter/Space，`aria-expanded`/`aria-label` 齐 ✅ |

---

### 4.6 `frontend/src/features/chat/components/pipeline/ToolCallLine.tsx` —— 改动

#### 4.6.1 改动 1：import 补齐

```diff
 import { CollapsibleText } from './CollapsibleText';
 import ToolResultRenderer from '../ToolResultRenderer';
+// 2026-10-13 小欧 - 文档[29]§4.6: 新增两组件与浮层壳/尺寸令牌 — 小欧 2026-10-13
+import { ParamsTree } from './ParamsTree';
+import { ParamsPanel } from './ParamsPanel';
+import { FloatingEntry } from '../taskinfo/FloatingEntry';
 import { CircleArrow } from '@/components/CircleArrow';
 import { GearIcon } from '@/components/GearIcon';
 import { DropletIcon } from '@/components/DropletIcon';
 import {
   LockOutlined,
   ClockCircleOutlined,
   StopOutlined,
   SafetyCertificateOutlined,
+  CodeOutlined,
} from '@ant-design/icons';
  import {
    Colors,
    BorderWidth,
    FontSize,
    FontWeight,
    Spacing,
    stepMargin,
+  Size,
  } from '@/utils/stepStyles';
```

> **2026-10-13 核查订正**：初稿在 stepStyles 导入里加了 `Radius`，但 §4.6 全文**未使用**（浮层卡片的圆角/边框/底色全部在 `ParamsPanel` 内部承担）→ 保留会触发 ESLint `no-unused-vars` error，故删除。

#### 4.6.2 改动 2：模块级常量（浮层卡片响应式三件套，D-5）

```diff
 export const REJECT_DEFAULT_ICON = <StopOutlined />;
+
+// 2026-10-13 小欧 - 文档[29]§4.6/§4.5: 浮层卡片纯 CSS 响应式三件套(替代断点矩阵 JS 方案 D-5)
+//   width 撑满上限 + maxWidth 随视口收 + minWidth 保底; 无 resize 监听、无重渲染 — 小欧 2026-10-13
+const PARAMS_CARD_STYLE: React.CSSProperties = {
+  width: Size.PARAMS_PANEL_MAX_W,
+  minWidth: Size.PARAMS_PANEL_MIN_W,
+  maxWidth: 'calc(100vw - 32px)',
+};
```

#### 4.6.3 改动 3：状态（删 `paramsOpen`，增 `openPanelIndex`）

```diff
   const [expanded, setExpanded] = useState<boolean[]>([]);
-  // 2026-10-04 小欧 文档[8]§5.4(丙案): 参数块独立折叠状态(每工具一份), 仅参数项数 >5 时才出现"展开" — 小欧 2026-10-04
-  const [paramsOpen, setParamsOpen] = useState<boolean[]>([]);
-  const PARAMS_FOLD_THRESHOLD = 5;
+  // 2026-10-13 小欧 - 文档[29]§3.2: 顶层"参数(N项)"折叠已被 ParamsTree 的"顶层键默认折叠"
+  //   取代(DC-04), paramsOpen/PARAMS_FOLD_THRESHOLD 一并删除(死状态 YAGNI);
+  //   新增 openPanelIndex 作浮层单例互斥(DC-07), 与 expanded 互不牵连(DC-18) — 小欧 2026-10-13
+  const [openPanelIndex, setOpenPanelIndex] = useState<number | null>(null);
   useEffect(() => {
     setExpanded([]);
-    setParamsOpen([]);
+    setOpenPanelIndex(null); // 切任务时二者同清(唯一同时清理的场景, §3.2)
   }, [action]);
```

#### 4.6.4 改动 4：`tools.map` 内删除 `paramRows` 派生

```diff
             tools.map((t, i) => {
-              // 2026-10-04 小欧 文档[8]§5.4 乙案: 参数改"每键一行"可读格式(不再一行压缩JSON,
-              //   值直接取原值不二次序列化 → 路径里的 \\ 不再双重转义); 丙案: 项数 >5 才折叠 — 小欧 2026-10-04
+              // 2026-10-13 小欧 - 文档[29]§3.3: 只传原始入参, 序列化/格式化下沉到子组件(SLAP) — 小欧 2026-10-13
               const paramEntries = Object.entries(
                 (t.params ?? {}) as Record<string, unknown>
               );
-              const paramRows = paramEntries.map(([k, v]) => ({
-                k,
-                v:
-                  typeof v === 'string'
-                    ? v
-                    : (() => {
-                        try {
-                          return JSON.stringify(v);
-                        } catch {
-                          return String(v);
-                        }
-                      })(),
-              }));
-              const paramsFoldable = paramRows.length > PARAMS_FOLD_THRESHOLD;
-              const paramsShown = !paramsFoldable || !!paramsOpen[i];
               const sum = getResultLine(i);
```

#### 4.6.5 改动 5：`toggleTool` 后补浮层开关（模块内纯函数化）

```diff
               const toggleTool = () => {
                 setExpanded((prev) => {
                   const next = [...prev];
                   next[i] = !prev[i];
                   return next;
                 });
               };
+              // 2026-10-13 小欧 - 浮层开合(DC-07 单例互斥 + DC-18 不牵连 expanded) — 小欧 2026-10-13
+              const onPanelOpenChange = (o: boolean) =>
+                setOpenPanelIndex(o ? i : null);
+              const closePanel = () => setOpenPanelIndex(null);
```

#### 4.6.6 改动 6：工具行内追加浮层按钮（D2 顺序：行尾），并删除内联参数区

**删除**（原 `:361-437`，整段位于 `role="button"` 内，是缺陷 B1 的病灶）：

```diff
-                    {/* 参数：子行展开后显示(乙案每键一行); 丙案项数>5 时先只显一行"参数(N项)"并可点开
-                        2026-10-04 小欧 文档[8]§5.4 乙/丙 — 小欧 2026-10-04 */}
-                    {isOpen && (
-                      <div
-                        style={{
-                          marginTop: Spacing.XS,
-                          paddingLeft: Spacing.LG,
-                          fontSize: FontSize.SECONDARY,
-                          color: Colors.TEXT.SECONDARY,
-                        }}
-                      >
-                        {paramsFoldable ? (
-                          <>
-                            <span
-                              role="button"
-                              tabIndex={0}
-                              onClick={(e) => {
-                                e.stopPropagation();
-                                setParamsOpen((prev) => {
-                                  const next = [...prev];
-                                  next[i] = !prev[i];
-                                  return next;
-                                });
-                              }}
-                              onKeyDown={(e) => {
-                                if (e.key === 'Enter' || e.key === ' ') {
-                                  e.preventDefault();
-                                  e.stopPropagation();
-                                  setParamsOpen((prev) => {
-                                    const next = [...prev];
-                                    next[i] = !prev[i];
-                                    return next;
-                                  });
-                                }
-                              }}
-                              style={{
-                                cursor: 'pointer',
-                                display: 'inline-block',
-                              }}
-                            >
-                              {paramsShown
-                                ? `▾ 参数（${paramRows.length} 项）`
-                                : `▸ 参数（${paramRows.length} 项）`}
-                            </span>
-                            {paramsShown && (
-                              <div style={{ marginTop: Spacing.XS }}>
-                                {paramRows.map((r) => (
-                                  <div
-                                    key={r.k}
-                                    style={{
-                                      fontFamily:
-                                        'Consolas, Monaco, "Courier New", monospace',
-                                      wordBreak: 'break-all',
-                                    }}
-                                  >
-                                    {r.k}: {r.v}
-                                  </div>
-                                ))}
-                              </div>
-                            )}
-                          </>
-                        ) : (
-                          paramRows.map((r) => (
-                            <div
-                              key={r.k}
-                              style={{
-                                fontFamily:
-                                  'Consolas, Monaco, "Courier New", monospace',
-                                wordBreak: 'break-all',
-                              }}
-                            >
-                              {r.k}: {r.v}
-                            </div>
-                          ))
-                        )}
-                      </div>
-                    )}
                   </div>
```

> **2026-10-13 核查订正**：初稿此处用 `... paramsFoldable 分支 + paramRows.map ...` 占位，不可直接实施。现已展开为**原文件 `:361-437` 的逐行完整原文**，可照单删除。

**在工具行 flex 内、`<CircleArrow>` 之后追加**（D2 定案：内容 │ 折叠箭头 │ 浮层参数）：

```diff
                       {/* 展开箭头 */}
                       <CircleArrow
                         size={16}
                         color={Colors.TEXT.PRIMARY}
                         expanded={isOpen}
                         animated={false}
                       />
+                      {/* 2026-10-13 小欧 - 文档[29]§3.6/D-6 + R2 根治(第七轮倒推核查):
+                          浮层参数按钮固定在工具行行尾(D2 乙), 外壳 FloatingEntry 自带 stopPropagation
+                          (FloatingEntry.tsx:98) 故置于此安全; FloatingEntry 根是无类名 block div,
+                          在工具行 flex 内会被压缩到 0 致按钮被挤没(其 Props 无 trigger 样式入口),
+                          故外裹一层 flexShrink:0(窄屏时按钮不被挤, 溢出由右栏 overflowX:hidden 兜);
+                          文案「浮层参数」避开与展开区撞名(D3), 图标用 CodeOutlined 不用 GearIcon(语义=等待中 DC-22) */}
+                      <span style={{ flexShrink: 0, display: 'inline-flex' }}>
+                      <FloatingEntry
+                        open={openPanelIndex === i}
+                        onOpenChange={onPanelOpenChange}
+                        placement="bottomRight"
+                        cardId={`params-panel-${t.tool ?? 'tool'}-${i}`}
+                        ariaLabel={`${t.tool} 参数`}
+                        cardStyle={PARAMS_CARD_STYLE}
+                        content={
+                          <ParamsPanel
+                            toolName={t.tool ?? 'tool'}
+                            params={(t.params ?? {}) as Record<string, unknown>}
+                            onClose={closePanel}
+                          />
+                        }
+                      >
+                        <span
+                          style={{
+                            display: 'inline-flex',
+                            alignItems: 'center',
+                            gap: Spacing.XS,
+                            fontSize: FontSize.SECONDARY,
+                          }}
+                        >
+                          <CodeOutlined />
+                          浮层参数
+                        </span>
+                      </FloatingEntry>
+                      </span>
                      </div>
```

#### 4.6.7 改动 7：展开区改挂 `ParamsTree`（B1 结构性根治，D-1）

**位置**：`role="button"` 容器**闭合之后**、原结果区 `<div>` 之前。

```diff
                   </div>
+                  {/* 2026-10-13 小欧 - 文档[29]§4.6.7/§2.7 I1 + D-1: 参数区**移出** role="button",
+                      点节点不再误折叠整行(B1 结构性根治), 故无需 stopPropagation 补丁;
+                      顶层键默认折叠 → 高度恒 (键数+1)×16px(C1/C2 根治) — 小欧 2026-10-13 */}
+                  {isOpen && <ParamsTree entries={paramEntries} />}
                   {/* 展开区：该工具完整 observation */}
                   {isOpen && (
```

#### 4.6.8 改动后净效果

| 项 | 前 | 后 |
|---|---|---|
| 文件行数 | 535 | **约 480**（删 95 / 增 40） |
| `ToolCallLine` 持有的参数相关状态 | `expanded` + `paramsOpen` + `PARAMS_FOLD_THRESHOLD` | 仅 `expanded` + `openPanelIndex` |
| 渲染期 `JSON.stringify` | 有（`paramRows` 每次渲染跑） | **零** |
| 参数区所在容器 | `role="button"` 内 | **容器外** |
| 点参数区 | 误折叠整行 | 仅切换节点 |

**规范判定**：KISS-DIRECT（净减 55 行、净减 1 个状态）✅ ｜ DRY（`stopPropagation` 补丁换结构修复，零重复逻辑）✅ ｜ SRP（`ToolCallLine` 只管编排，参数渲染全在 `ParamsTree`）✅ ｜ SLAP（`ParamsPanel` 不自管浮层开合）✅

---

### 4.7 回归测试文件（**按 AGENTS 铁规不提交**）

```tsx
// 2026-10-13 小欧 - 文档[29]§3.1 第 5 项: 展开区行为回归测试
//   ⚠️ AGENTS 铁规「严禁提交任何测试 case 代码」—— 本文件仅本地保留, git add 时勿纳入
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { ParamsTree } from './ParamsTree';

const entries: Array<[string, unknown]> = [
  ['file_path', 'F:\\a\\main.py'],
  ['encoding', 'utf-8'],
  ['append', false],
  ['content', 'line1\nline2\nline3'],
];

describe('ParamsTree(展开区 JSON 树)', () => {
  it('顶层键默认折叠: 长值只显行数摘要, 不铺内容', () => {
    render(<ParamsTree entries={entries} />);
    expect(screen.getByText(/共 3 行/)).toBeTruthy();
    expect(screen.queryByText('line1')).toBeNull();
  });

  it('标量键无折叠箭头, 恒单行', () => {
    render(<ParamsTree entries={entries} />);
    expect(screen.getByText('utf-8')).toBeTruthy();
  });

  it('点节点可展开长文本, 展开体限高由 maxNodeBodyHeight 控制', () => {
    render(<ParamsTree entries={entries} maxNodeBodyHeight={240} />);
    screen.getByText(/共 3 行/).click();
    expect(screen.getByText(/line1/)).toBeTruthy();
  });

  it('空值渲染 (空) 而非空白', () => {
    render(<ParamsTree entries={[[ 'x', undefined ]]} />);
    expect(screen.getByText(/\(空\)/)).toBeTruthy();
  });
});
```

---

## 五、实施完成后的验证清单（与 §3.8 验收合并执行）

| 顺序 | 步骤 | 命令 |
|---|---|---|
| 1 | 类型检查 | `npm run typecheck` |
| 2 | e2e 类型检查 | `npm run typecheck:e2e` |
| 3 | Lint | `npm run lint` |
| 4 | 格式检查 | `npm run format:check` |
| 5 | 关联回归 | `npm run test -- --run ParamsTree`（**仅本地有测试文件时执行**；§4.7 按 AGENTS 铁规不提交，CI/他机无此文件即跳过） |
| 6 | 手工核对 | 按 §3.8 的 T1~T34 逐条走查（重点 T1 高度、T3 误折叠、T26/T28/T30 视觉一致性） |

---

编写人：小欧
编写时间：2026-10-13 09:58:45