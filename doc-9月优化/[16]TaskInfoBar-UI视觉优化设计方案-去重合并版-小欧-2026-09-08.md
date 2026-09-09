# TaskInfoBar UI视觉优化设计方案（去重合并版 v4.3）

**编写人：小欧**
**编写时间：2026-09-08 19:57:56**
**去重合并人：小欧**
**去重合并时间：2026-09-08 23:47:47**
**v4.1 更新时间：2026-09-09 09:01:58**
**v4.2 更新时间：2026-09-09 09:32:53**
**v4.3 更新时间：2026-09-09 10:44:31**
**文档版本：v4.3**

---

## 版本历史

| 版本 | 时间 | 修改简介 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-09-08 19:57:56 | 初版：基于全量源码精读，发现 18 项问题，分 P0/P1/P2 三级 | 小欧 |
| v2.0 | 2026-09-08 20:00:00 | 新增第二章"现状与改进对比（线框图）"：含 2.1 现状问题图 + 2.2 改进后设计稿（A-G 七图）；章节重排（原三~七章顺延为四~七章），优化设计基础前置 | 小欧 |
| v3.0 | 2026-09-08 20:36:06 | 全链有机整合北京老陈三点建议：(1) 上下文标签/数值拆分，并**独立成番号 P1-8 / 2.2.8 / 5.3**，为后续单独优化预留挂载点；(2) 信任详情改 **Drawer 侧滑面板** + 撤销按钮移入每行首列 + Modal.confirm 二次确认（D2 定案）；(3) 过程事件改**时间轴+分段带**（体现时序与疏密）。线框图 B/C/D/H、问题清单 P1-7/P1-8/P1-10、设计稿 5.2/5.3、决策表 D2/D5、优先级表全链同步 | 小欧 |
| v3.1 | 2026-09-08 20:50:00 | 第一行信息位**独立番号 G0~G7**：G0折叠/G1状态/G2耗时/G3进度/G4异常/**G5 Token数值/G6 上下文/G7 信任**，弃用"左/中/右组"合并分组；A 图、5.1、5.8 全链同步 G0~G7 番号 | 小欧 |
| v3.2 | 2026-09-08 22:04:21 | 全文章节号重排：2.2 子节由字母 A~H 重排为数字 **2.2.1~2.2.8**，全文交叉引用同步；G7 信任可点击样式统一为"文字样式（深色加粗/框线/下划线）"，去除箭头与盾图标（[▸]/[盾]/RightOutlined）并同步 2.2.3/5.1/5.7/5.8/8.1；5.8 断点表列名改"G1-G4（状态/耗时/进度/异常）" | 小欧 |
| v3.3 | 2026-09-08 22:10:23 | G0 折叠改为 **G8 折叠**：番号体系 G0~G7 重组为 **G1~G8**（G1状态/G2耗时/G3进度/G4异常/G5 Token/G6上下文/G7信任/G8折叠），番号=渲染顺序；2.2.1、5.1、5.8、P0-2、2.2.1-八 全链同步 | 小欧 |
| v3.4 | 2026-09-08 22:15:20 | 图标渲染格式选型：全行图标统一为**单一格式 = @ant-design/icons 内联 SVG 组件**；**过程事件行升级为 antd SVG 图标**（PlayCircle/PauseCircle/ReloadOutlined），同步 2.2.4、P1-5、P2-13、5.4、5.9 | 小欧 |
| v3.5 | 2026-09-08 22:20:48 | 一致性修正 4 处（v3.3 行"2.2.1-A 八"笔误、5.7"（原 P1-10）"冗余、5.9 emoji 检查补齐文本符号、2.2.1-七 表头列名统一"内联 SVG"）；**新增第十章"代码复用与模块划分（10 大规范核查）"** | 小欧 |
| v3.6 | 2026-09-08 22:35:08 | **新增第十一章"实施计划与步骤（TDD 模式）"**：主体 TDD + 视觉类后置验证混合；6 阶段实施；新增测试用例 27 项；DoD 验收 6 条 | 小欧 |
| v3.7 | 2026-09-08 23:29:10 | 核查报告 10 处落定：G8 `▾`→`<DownOutlined/>`；2.2.4 时序矛盾定案"最新在顶"+三列改两列；8.2 改均长线；P/C 两段对称+T 空格 `T 1,234`；PRIMARY 全称化 `TEXT.PRIMARY`；WARNING `#faad14`→`#AD6800`；G7 定案 A；5.7 删 ToolOutlined；5.8 两表合并热区 32px；Drawer `min(360px,80vw)`；P1-11 定案 B；上下文 `有摘要`→`摘要·无计数`；破折号 en-dash；11.3 令牌名改 9.1 已定义 | 小欧 |
| **v4.0** | **2026-09-08 23:47:47** | **全量去重合并重写**：删除 2.2.x 与 5.x 双份规范（每份只留一处）、问题清单只留"问题+改法指针"；删单列审查范围（并入文档目的）、风险章节、与 v3.7 定案矛盾的术语表；保留 18 项问题、全部规范、D1~D5、优先级、令牌、复用、TDD 实施、27 项测试用例、DoD；重新排章节号 | 小欧 |
| v4.1 | 2026-09-09 09:01:58 | 折叠交互定案变更：**取消整行折叠（信息带恒定 1 行），拆为两块独立 Popover 浮层**（上下文卡片锚 G6 + 事件卡片锚 G8）；G8 语义由"折叠任务面板"改为"事件序列入口"；位置"锚点右缘对齐向左展开"、窄屏右贴边；hover 规格 2（32×32 热区背景淡入+图标 PRIMARY+展开态 rotate 180°）；6.5.3.4/6.5.3.8/6.5.3.10 真实代码、7.3 测试用例全链同步 | 小欧 |
| v4.2 | 2026-09-09 09:32:53 | 第二轮源码级核查落定：**G6/G8 双浮层入口抽公共组件 `FloatingEntry.tsx`**（Popover 壳 + 热区 a11y + Enter/Space/Esc 键盘 + 焦点管理，卡片内容留调用方；DRY，17 行×2 处重复收敛；3.8/7.3 Esc+焦点断言补实现归属）；**G8 `onClick` 删除手动 toggle 双重写入**（开合交还 antd trigger 单一真源，与 G6 对齐）；3.9 热区 CSS 落盘 `src/index.css`；6.1/6.2/6.3 复用清单、6.5.2.4 新建文件规约、6.5.3.2/6.5.3.4/6.5.3.8 调用、7.1/7.2 阶段 1.5、7.3 断言全链同步 | 小欧 |
| v4.3 | 2026-09-09 10:44:31 | **实施落盘校正（7 处偏离字面，以实码为准）**：(1)`infoMaps.ts`→`infoMaps.tsx`（含 JSX，`.ts` 编译失败）；(2)删 `infoMaps` 未用 `Colors` 导入；(3)精简 `TaskInfoBar` 未用 `Tooltip`/过程图标导入（迁 `infoMaps`）；(4)删 `TrustPanel` 未用 `Spacing`；(5)placement `bottom-start/bottom-end`→`bottomLeft/bottomRight`（antd 真值）；(6)6.5.5 P2-14 顺序 `末条步骤‖帧started‖Date.now()` + candidates 新信号前置（防旧时间遮新 G4 信号 + 0 穿透）；(7)7.4"无既有测试"失实→实有 765 项，3 文件按先红后绿迁移；全文 806 绿零失败、tsc/lint 零 error，行为等价 | 小欧 |

---

## 一、文档目的

基于对 TaskInfoBar 及其关联组件（TrustPanel、useTaskInfo、SessionLayout、stepStyles.ts、sse.ts、useChatPanels、execution.ts 等）的**全量源码精读**，系统性审查 UI 视觉呈现、交互体验、无障碍、代码规范四个维度，发现问题 18 项，并在第三章给出唯一权威的改进方案，第四章明确设计决策，第七~八章落地复用与 TDD 实施。

---

## 二、问题清单（18项，P0/P1/P2 分级）

> 每项只列「位置 + 现状问题 + 改法」，**详细规范见第三章对应小节**，不做二次完整定义。

### 2.1 P0 级问题（必须改，影响功能/生产安全）

#### P0-1：生产环境残留调试探针

**位置**：`TaskInfoBar.tsx:24-25,76-80,133-142`

**现状代码**：
```typescript
// 编辑历史: 2026-09-08 小欧 - [HITL排查探针·临时]: ...
useEffect(() => {
  console.log('[TaskInfoBar探针] mount', { sessionId, receiving, pid: Math.random().toString(36).slice(2) });
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, []);

// onClick 内：
console.log('[TaskInfoBar探针] toggle 触发', {
  collapsedBefore: collapsed,
  target: (e.target as HTMLElement)?.tagName,
  targetText: (e.target as HTMLElement)?.textContent?.slice(0, 20),
  isTrusted: e.nativeEvent?.isTrusted,
});
```

**问题**：注释自称"临时"却至今未删；每次挂载/toggle 刷控制台；pid 语义无意义；`eslint-disable-next-line` 旁路 hooks 检查。

**改法**：整段删除（含 useEffect 挂针 + onClick console.log + 编辑历史行 24-25）。纯删除，零逻辑。

---

#### P0-2：整行折叠零可发现性 + 无障碍缺失

**位置**：`TaskInfoBar.tsx:125-143`

**现状代码**：
```typescript
<div
  style={{
    display: 'flex', alignItems: 'center', gap: 12,
    cursor: 'pointer',   // ← 仅靠 cursor 暗示
    flexWrap: 'nowrap',
  }}
  onClick={(e) => {
    setCollapsed((v) => !v);  // ← 整行点击 toggle
  }}
>
```

**问题**：
1. **无折叠 affordance**：无箭头/图标/"收起"文字，用户无法发现此行可点击
2. **无无障碍支持**：无 `role="button"`、`tabIndex`、`aria-expanded`、`onKeyDown`
3. **与 TrustPanel 双标**：TrustPanel（:92-106）有完整 role/aria，外层折叠行却啥都没有
4. **文本选中冲突**：点击选中的 token 数字会触发折叠

**改法**：见 [3.1 G6/G8 入口](#31-第一行整体设计信息位-g1g8)、[3.8 无障碍](#38-无障碍与键盘导航)、[3.9 断点与热区](#39-响应式断点与浮层热区p1-9-落地v41-双浮层定案)（v4.1 定案）：**取消整行折叠**——信息带恒定 1 行不再收起；触发收敛到两个独立浮层入口：G6 上下文入口（`role="button"` + `aria-haspopup="dialog"` + `aria-expanded` + `tabIndex` + `onKeyDown`）、G8 事件入口（同规格，`<DownOutlined/>` 视觉锚点）；热区与 hover 见 3.9。

---

#### P0-3：collapsed 状态挂载即重置

**位置**：`TaskInfoBar.tsx:73`

**现状**：`const [collapsed, setCollapsed] = useState(false);` 组件重挂载（会话切换/panels 重组）即强制展开。

**问题**：用户收起的面板被重置；与 `SessionPanelRegistry.persistVisible` 持久化机制不一致。

**改法**（v4.1 定案）：取消整行折叠态机——信息带恒定 1 行，`collapsed` 状态与 `session_panel_collapsed:taskinfo.bar` 持久化随设计变更一并删除（折叠动作不复存在），不再有"收起面板被重置"问题。

---

#### P0-4：撤销信任操作无确认提示

**位置**：`TrustPanel.tsx:74-82`

**现状**：点击 `×` 直接 `revoke()`，无任何确认。误触即丢失信任配置，且不可恢复（信任写入有 HITL 弹窗确认，撤销却一键生效）。

**改法**：revoke 前加 antd `Modal.confirm`，二次确认文案含工具名（见 [3.5 信任 Drawer](#35-信任-drawerg7p1-10p0-4p2-18-落地)）。

---

### 2.2 P1 级问题（视觉层级/布局/一致性）

#### P1-5：图标语言三套混用

**位置**：`TaskInfoBar.tsx:152,166-186,243,283-289`

**现状**：同一组件混用 antd Badge dot + emoji（`🔁⛔⚠🔴▶️⏸️`）+ antd 组件图标三套视觉语言。

**问题**：emoji 跨平台渲染不一致、12px 行内漂移；`🔴` 与 CloseCircleFilled 红圆语义撞色；三套不统一。

**改法**：全行图标统一为 @ant-design/icons 内联 SVG 组件，一对一替换清单见 [3.4 图标统一方案](#34-图标统一方案g4--过程事件)，含迁移检查清单。

---

#### P1-6：G4 liveMeta 警告色对比度不足

**位置**：`TaskInfoBar.tsx:167-168`

**现状**：`<span style={{ fontSize: 12, color: Colors.WARNING, marginLeft: 2 }}>`

**问题**：`Colors.WARNING = #faad14` 白底对比度约 2.1:1（WCAG AA 要求 4.5:1）；长错误文本无 `maxWidth/ellipsis` 会把左组撑宽。

**改法**：
1. WARNING 色值 `#faad14` → `#AD6800`（白底对比度≥4.5:1 达标）
2. retrying/truncated 保留 WARNING + `fontWeight: 500`
3. 文本加 `maxWidth: 200px` + `overflow: hidden` + `textOverflow: ellipsis` + Tooltip 全文

---

#### P1-7：Token 数值行同字同色、层级缺失（本轮/累计）

**位置**：`TaskInfoBar.tsx:193-257`

**现状**：`本轮 T1234 (P890/C344) · 任务累计 T5678 (P3456/C2222) · 上下文 2048tok` 全 12px 同色，扫描 6 个元素找不到重点；P/C 藏在 Tooltip；`·` 与 TERTIARY 同色分隔弱。

**改法**：本轮/累计两段统一"标签+数值"两段式，**两段对称、P/C 均可见**（见 [3.2 Token 数值行](#32-g5-token-数值行)）。

---

#### P1-8：上下文段四种文案 + 标签/数值未拆分

**位置**：`TaskInfoBar.tsx:231-256`

**现状**：四种分支四种文案（`"上下文摘要"` / `"上下文 {n}tok🔴"` / `"上下文摘要"` / `"上下文 0tok"`），同一位置长相不稳定；`0tok` 像坏数据；`"上下文摘要"` 无信息量；标签数值混成一串；`🔴` 撞色。

**改法**：统一"标签+数值"两段式 + 4 态状态机 + 独立番号（见 [3.3 上下文段](#33-g6-上下文段)）。

---

#### P1-9：窄屏必溢出

**位置**：`TaskInfoBar.tsx:125-131`

**现状**：`flexWrap: nowrap` + 左组 `flexShrink: 0`（:149）= 窗口收窄时中组被压缩成 0 宽度。

**改法**：基础行 `flexWrap: 'wrap'` 允许换行；明细内容 v4.1 全部移入浮层，不再挤占基础行；断点行为见 [3.9 响应式断点](#39-响应式断点与浮层热区p1-9-落地v41-双浮层定案)。

---

#### P1-10：TrustPanel 展开撑高第一行

**位置**：`TrustPanel.tsx:134-138`

**现状**：展开列表渲染在第一行右组内，`maxHeight: 70` 撑高行高，左/中组视觉跳动。

**改法（定案：Drawer 侧滑面板）**：见 [3.5 信任 Drawer](#35-信任-drawerg7p1-10p0-4p2-18-落地)。

---

#### P1-11：与 input 区分隔缺失

**位置**：`TaskInfoBar.tsx:117`

**现状**：本条只顶部 `borderTop`，底部靠 `gap: 8` 悬空，input 区无顶部 border，两块间视觉界限模糊。

**改法（定案 B）**：本条去掉 `borderTop`，input 区顶部统一加 `borderTop`，分隔线归属"输入区上沿"；本条靠 `gap` 与 input 区分隔。

---

### 2.3 P2 级问题（细节打磨）

#### P2-12：设计令牌旁路

**位置**：`TaskInfoBar.tsx:43`

**现状**：只 import `Colors`，字号/间距/圆角全硬码（`fontSize: 12`×9、`fontWeight: 500`×2、`gap: 12/8`、`padding: '8px 0 0'`、`maxHeight: 72`、`marginLeft: 2`）。

**改法**：补 import `FontSize, Spacing, Radius`，硬码数字替换为令牌引用（令牌见 [六、设计令牌索引](#六设计令牌索引)）。

---

#### P2-13：过程事件行可读性差

**位置**：`TaskInfoBar.tsx:283-291`

**现状**：时间与文本同色 TERTIARY；`toLocaleTimeString()` 无 tabular-nums 数字抖动；`key={i}` 索引 key 列表重排错复用；emoji `▶️` 含 U+FE0F 宽度不稳。

**改法**：时间改 `fontSize: 11` + `color: SECONDARY` + `fontVariantNumeric: 'tabular-nums'`；事件文本保持 TERTIARY；key 改 `` `${e.time}-${e.kind}` ``；emoji 改 antd SVG（见 [3.6 过程事件时间轴](#36-过程事件时间轴g2-时间列--事件列)）。

---

#### P2-14：useTaskInfo useMemo 内 Date.now()

**位置**：`useTaskInfo.ts:254`

**现状**：`Date.now()` 在 useMemo 内，依赖变化即产生新时间戳；排序在 `time === now` 时退化为插入顺序；仅用于排序不影响显示，语义不清晰。

**改法**：`now` 改从 `frames.startTimestamp` 或 `steps[steps.length-1].timestamp` 取，不依赖 `Date.now()`。

---

#### P2-15：Badge idle 态视觉过弱

**位置**：`TaskInfoBar.tsx:56-63`

**现状**：`BADGE_MAP.idle = { status: 'default' }` 灰圆点灰字，与 `cancelled` 相同，无法区分"空闲等待"和"已取消"。

**改法**：idle 保持 `default` + `待命`；cancelled 改 `status: 'error'` + 文字 `已取消`（或自定义 dot 色区分）。

---

#### P2-16：耗时显示无单位对齐

**位置**：`TaskInfoBar.tsx:160`

**现状**：`Math.round(shownElapsed)s` 动态宽度数字，文字随位数跳动。

**改法**：数字 `fontVariantNumeric: 'tabular-nums'` 等宽；或固定 `minWidth: 32px` + `textAlign: right`。

---

#### P2-17：过程事件区 maxHeight 固定

**位置**：`TaskInfoBar.tsx:275`

**现状**：`maxHeight: 72` 固定（3-4 行），滚动条在 Windows 占 ~8px 实际可视更小。

**改法**：`maxHeight` 改 `80px`（4 行整含底部 padding）；或"最新 3 条 + 展开全部"。

---

#### P2-18：TrustPanel 撤销按钮无障碍

**位置**：`TrustPanel.tsx:158-174`

**现状**：`<span onClick>×</span>` 文本符号、无 role/tabIndex/keydown、无 aria-label（title 不替代）、撤销不可逆无确认。

**改法**：改 `<Button type="text" size="small" icon={<CloseOutlined />} />`（antd 自带 role/keyboard/aria）+ `aria-label="撤销信任 {toolName}"` + Modal.confirm 二次确认（见 [3.5](#35-信任-drawerg7p1-10p0-4p2-18-落地)）。

---

## 三、改进方案（唯一权威规范）

> 本版已合并 v3.7 的 2.2.x 与 5.x 全部重复定义，每份规范只保留一处，实现时以此为准。

### 3.1 第一行整体设计（信息位 G1~G8）

**设计原则（四条铁律）**：

```
① 主次清楚 —— 主信息靠前，辅助操作靠右，绝不轻重倒置
② 番号独立 —— 每个信息位一个番号 G1~G8，互不合并、不依附
③ 可点必示 —— 凡可点击处必带"可点击样式"（字体样式/框线/下划线），不让用户猜
④ 层级统一 —— 全行统一"标签灰+数值加粗"两段式规范（见 3.7 颜色规范）
```

#### 3.1.1 整体线框图

```
┌──────────────────────────────────────────────────────────────────────────┐
│ G1●执行中  G2 12s  G3 3步·2轮  G4[SyncOutlined]重试中  G5 本轮 T 1,234/累计  │
│ G6[上下文 2,048tok▸]   G7 信任(2)   G8[<DownOutlined/> 事件▸]             │
│ ── 主信息(运行态) ──       ── 次信息(资源态) ──   ── 操作项(浮层入口) ──  │
└──────────────────────────────────────────────────────────────────────────┘
     渲染序：G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8（从左到右）

 浮层① 上下文卡片（v4.1 定案，锚定 G6，hover 预览/click 钉住）
   ┌──────────────┐
   │ 上下文摘要 summary 前 N 字 │
   │ 估算 token · 状态 · 截断说明 │
   └──────────────┘
 浮层② 事件卡片（锚定 G8，maxHeight 40vh 内滚）
   ┌──────────────────────────────┐
   │ 09:01:58 │[PlayCircle] 事件已开始  │
   │ 09:02:10 │[Reload] 重试中…          │
   └──────────────────────────────┘
```

**番号体系**：番号（逻辑分组）= 渲染顺序（物理从左到右）= G1 状态 · G2 耗时 · G3 进度 · G4 异常 · G5 Token数值 · G6 上下文 · G7 信任 · G8 事件入口。主信息 G1 打头，操作项排最右；信息带**恒定 1 行**（v4.1 取消整行折叠），明细内容全部进独立浮层，永不推挤会话流。

#### 3.1.2 各信息位设计规范表

| 番号 | 渲染序 | 类型 | 内容 | 字号 | 字重 | 色值 Token | 说明 |
|---|---|---|---|---|---|---|---|
| G1 状态 | 1 | 主 | Badge + 文字 | 12 | 500 | TEXT.PRIMARY | antd Badge dot，重要信息打头 |
| G2 耗时 | 2 | 主 | `12s` | 12 | 600 | TEXT.PRIMARY | **tabular-nums** 等宽，加粗最醒目 |
| G3 进度 | 3 | 主 | `3步·2轮` | 12 | 400 | TEXT.SECONDARY | 辅助信息，中灰 |
| G4 异常 | 4 | 主 | 图标+文字 | 12 | 500 | 见图标映射 | **统一 antd icon**，去掉 emoji |
| G5 Token数值 | 5 | 次 | 本轮 T / 累计 T（P/C 均可见） | 见 3.2 | — | — | **本轮/累计 T 加粗、P/C 中灰，两段对称** |
| G6 上下文 | 6 | 次 | 上下文段 | 见 3.3 | — | — | **标签+数值两段式，独立番号；整段为浮层①入口**（hover 预览/click 钉住，见 3.3） |
| G7 信任 | 7 | 操作 | `信任(2)` | 12 | 500 | TEXT.PRIMARY | **可点击文字样式（方案A定案）**：加粗+hover 变色，Drawer 侧滑 |
| G8 事件入口 | 8 | 操作 | `[<DownOutlined/>] 事件` | 10 | 400 | TERTIARY | **浮层②入口**：事件序列时间轴（hover 预览/click 钉住），排最右；热区 32×32 + hover 规格 2（见 3.9） |

#### 3.1.3 操作项可点击样式（G6/G7/G8，方案A定案）

| 操作位 | 可点击表达 | 说明 |
|--------|-----------|------|
| **G7 信任** | **文字样式（方案A）**：`color: Colors.TEXT.PRIMARY` + `fontWeight: 500`，hover 变 `Colors.PRIMARY` 蓝 + `cursor: pointer`，focus-visible 2px outline | 靠字体样式提示可点，无图标/框线/下划线 |
| **G6 上下文入口** | 整段（标签+数值+▸）为浮层①入口：hover 背景淡入 + 数值变 `Colors.PRIMARY` + `cursor: pointer`；热区 ≥ 32×32 | popover 箭头指示符隐藏在 MetricItem 后，hover/click 均触发（见 3.3） |
| **G8 事件入口** | `[<DownOutlined/>] 事件` antd SVG 图标，fontSize 10，TERTIARY 色；**hover 规格 2**：32×32 热区圆角 8，背景 `#fafafa→#f0f0f0` 淡入，图标变 PRIMARY，展开态 `rotate(180deg)`，`transition 0.2s ease`，`cursor: pointer` | 内联 SVG，箭头方向=弹出语义 |

> 方案B（方框）/方案C（下划线）已否决：B 引入 Tag 元素增加视觉噪音，C 与浏览器原生链接语义混淆。

**装置无障碍**：G6/G8 浮层入口均 `role="button"` + `aria-haspopup="dialog"` + `aria-expanded` + `aria-label` + `aria-controls`，屏读播报"上下文详情，已展开 / 事件序列，已展开"等完整语义；`:focus-visible` 显式 outline（2px PRIMARY 蓝）。

---

### 3.2 G5 Token 数值行

```
本轮   T 1,234  P 890/C 344   │  累计   T 5,678  P 3,456/C 2,222
标签   数值    分项            标签    数值      分项
灰     加粗    中灰            灰      加粗      中灰
```

| 元素 | 字号 | 字重 | 色值 | 说明 |
|------|------|------|------|------|
| 标签"本轮/累计" | 11 | 400 | TERTIARY | 小字灰色，不抢 |
| 数值 T 总数 | 12 | 600 | TEXT.PRIMARY | 加粗，最醒目，核心监控值 |
| P/C 数值 | 12 | 500 | TEXT.SECONDARY | 中灰，辅助信息 |
| 分隔符 `·` | 12 | 400 | BORDER | 极淡，不抢 |

> 「上下文」段不在此行定义，独立见 [3.3 上下文段](#33-g6-上下文段)。本轮/累计两段对称展示 P/C（D1 定案 A）。

---

### 3.3 G6 上下文段

> **独立原则**：上下文段不再依附 Token 数值行，单独成番号 G6（对应 P1-8 / 原 2.2.8）。原因：该位置后续还会单独优化（摘要/注入比例/截断策略），现在独立为将来预留明确挂载点。

```
上下文   2,048 tok
标签    数值
灰      加粗(截断时 WARNING + WarningOutlined)
```

| 元素 | 字号 | 字重 | 色值 | 说明 |
|------|------|------|------|------|
| 标签"上下文" | 11 | 400 | TERTIARY | 小字灰色，独立定义 |
| 数值 `{n} tok` | 12 | 600 | TEXT.PRIMARY | 加粗；截断时 WARNING |
| 截断标记 | 12 | 500 | WARNING | `<WarningOutlined />` 表示"被截断"非"出错" |

**文案状态机（4态 → 统一两段式）**：

| 状态 | 标签 | 数值 | 数值色值 | 图标 |
|------|------|------|-----------|------|
| 有 overview + 有 token 数 | `上下文` | `{n} tok` | TEXT.PRIMARY | 无 |
| 有 overview + 无 token 数 | `上下文` | `摘要·无计数` | TERTIARY | 无（Tooltip 显示 overview 前 N 字） |
| 截断 | `上下文` | `{n} tok` | WARNING | WarningOutlined |
| 无数据 | `上下文` | `–` | TERTIARY | 无 |

**交互行为**（v4.1：整段为**浮层① 上下文卡片**入口，锚定 G6，独立于事件区）：

| 交互 | 触发 | 响应 |
|------|------|------|
| hover 预览 | hover `<上下文 2,048 tok>` | 150ms 后浮出**上下文卡片**（快速瞄一眼），鼠标移开 300ms 自动消失 |
| click 钉住 | 单击整段 | 卡片钉住（Pin），`Esc`/点卡片外关闭；hover 与 click 用 delay 防抖互斥 |
| hover（截断） | hover 带 WarningOutlined | 卡片内状态区高亮警告"上下文被截断，可能影响回答质量" |
| hover（无数据） | hover `上下文 –` | 卡片内显示"上下文缺失，检查 frames 数据链路" |
| 位置 | 卡片锚定 G6（`placement="bottomLeft"` antd 真值，语义 `bottom-start` 左缘对齐、向右展开）；窄屏右贴安全边距 | 与事件卡片（G8）互不干扰，各自独立开合 |

**浮层①卡片内容**（上下文卡片，宽约 320px，v4.1 独立块）：

```
┌ 上下文详情 ─────────────┐
│ 摘要: {overview.summary 前 N 字} │
│ 估算 token: {n} tok           │
│ 状态: 正常 / 已截断 / 无计数 / 缺失 │
└────────────────────────┘
```

**aria 语义**：入口 `role="button"` + `aria-haspopup="dialog"` + `aria-expanded` + `aria-controls` + `aria-label="上下文 {n} tok{截断?'，已截断':''}"`；数值区（基础行保持）`role="status"` + `aria-live="polite"` + `data-state="ok / summary-only / truncated / empty"`（测试与样式钩子）。

**未来优化预留位**：上下文摘要（summary 全文/展开）、注入比例 injected_ratio、消息数 message_count、截断策略/预警分级。

---

### 3.4 图标统一方案（G4 + 过程事件）

**原则**：全行图标统一为**单一格式 = @ant-design/icons 内联 SVG 组件**。

| 场景 | 现状 | 改进 | antd icon（内联 SVG） |
|------|------|------|-----------|
| 重试中 | `🔁` emoji | spin 动画 | `<SyncOutlined spin />` |
| 请求级错误 | `⛔` emoji | 灰色静态 | `<StopOutlined />` |
| 执行级错误 | `<CloseCircleFilled/>` | 不变 | `<CloseCircleFilled />` |
| 截断警告 | `⚠` + `🔴` | 去🔴 | `<WarningOutlined />` |
| 过程-开始 | `▶️` | SVG 图标 | `<PlayCircleOutlined />` |
| 过程-暂停 | `⏸️` | SVG 图标 | `<PauseCircleOutlined />` |
| 过程-恢复 | `▶️` | SVG 图标 | `<PlayCircleOutlined />` |
| 过程-重试 | `🔁` | SVG 图标 | `<ReloadOutlined />` |

统一 `fontSize: 12` + `color: Colors.TEXT.TERTIARY`，与全行其他信息位图标同构同规格。

**为什么用 SVG（选型结论）**：矢量缩放（fontSize→SVG 任意尺寸无失真）、随文变色（color→currentColor）、描边可控、跨平台一致（12px 不糊不漂）、动画内建（`<SyncOutlined spin />`）、组件级默认 aria-hidden。

**否决的候选**：iconfont 字体图标（单色依赖 web-font）、外链 `<img>`/背景图（不能变色多请求）、纯 CSS 绘制（复杂图形开销大）、emoji/Unicode 文本符号（跨平台不一致仅能改色）。

**迁移检查清单（验收归口：7.6 DoD 第 5 条）**：

| # | 检查点 | 来源代码 | 动作 |
|---|--------|----------|------|
| 1 | Badge dot（status） | :152 | 保留（已是 antd Badge） |
| 2 | `🔁` 重试 emoji | :171 | 改 `<SyncOutlined spin />` |
| 3 | `⛔` 请求错误 emoji | :183 | 改 `<StopOutlined />` |
| 4 | `⚠` 截断文本字符 | 截断分支 | 改 `<WarningOutlined />` |
| 5 | `🔴` 截断红点 | :243 | 删除，语义并入 WarningOutlined |
| 6 | `▶️⏸️🔁` 事件 emoji | :285-288 | 改 antd SVG（上表后 4 行） |
| 7 | 全局搜 `\p{Extended_Pictographic}` | 全文件 | 确保无遗留 emoji 图标 |

```powershell
# 全局检查是否残留 emoji 图标（Windows PowerShell）
Select-String -Path "frontend\src\features\chat\components\taskinfo\TaskInfoBar.tsx" -Pattern "🔁|⛔|⚠|🔴|▶️|⏸️|▶|⏸|↻|◀"
```

---

### 3.5 信任 Drawer（G7，P1-10/P0-4/P2-18 落地）

**形态**：从"第一行内嵌展开"改为 `Drawer`（右侧滑出），第一行固定高度 28px，无左右组跳动。撤销按钮移入每行首列（操作在前、对象在后），走 Modal.confirm 二次确认。

```typescript
// 编辑历史: 2026-09-08 小欧
// 第一行：仅保留计数徽标 + 展开按钮（不再内嵌列表）
<div role="button" aria-expanded={drawerOpen} tabIndex={0} onClick={openDrawer}
  style={{ color: Colors.TEXT.PRIMARY, fontWeight: 500, cursor: 'pointer' }}>
  信任({trustCount})                                      // 点击打开 Drawer
</div>

// Drawer（右侧滑出），列表抽离为独立渲染
<Drawer
  placement="right"
  open={drawerOpen}
  onClose={closeDrawer}
  title="会话信任清单"
  width="min(360px, 80vw)"
>
  {tools.length === 0 ? (
    <Empty description="暂无信任工具" />
  ) : (
    <Table dataSource={tools} size="small" rowKey={(t) => `${t.toolName}|${t.path}`}>
      <Table.Column title="撤销" dataIndex="toolName"
        render={(_, t) => (
          <Button size="small" type="text" icon={<CloseOutlined />}
            aria-label={`撤销信任 ${t.toolName}`}
            onClick={() => confirmRevoke(t)} />
        )} />
      <Table.Column title="对象" render={(_, t) => `${t.toolName} › ${t.path ?? '(全局)'}`} />
    </Table>
  )}
</Drawer>
```

**撤销二次确认（P0-4）**：
```typescript
// 编辑历史: 2026-09-08 小欧
const confirmRevoke = (t: TrustItem) => {
  Modal.confirm({
    title: '确认撤销信任？',
    content: `撤销后将重新弹框确认「${t.toolName} › ${t.path ?? '全局'}」。`,
    okText: '确认撤销', cancelText: '取消',
    onOk: async () => {
      await trustApi.revokeTrust(sessionId, t.toolName, t.path);
      await load();
    },
  });
};
```

| 要点 | 说明 |
|------|------|
| 第一行高度 | 固定不变，列表在 Drawer 内横向滑出，G1~G8 信息位不跳动 |
| 撤销按钮 | 每行首列，`操作在前、对象在后`，Tab 顺序=视觉顺序 |
| 焦点管理 | Drawer 打开后焦点移入面板，关闭后回到触发按钮 |
| 空态 | Drawer 内 `Empty` 组件"暂无信任工具" |
| 持久化 | Drawer 开合不持久化（轻量瞬态）；浮层卡片开合同理（v4.1 已无折叠态） |

---

### 3.6 过程事件时间轴（G2 时间列 + 事件列）

```
  时间线+时间(左列)              事件(右列)

  14:32:20 ── [<PauseCircleOutlined/>] 任务已暂停
      │
  14:32:15 ── [<ReloadOutlined/>] 正在重试
      │
  14:32:01 ── [<PlayCircleOutlined/>] 任务已开始
```

> **最新在顶**（遵循现状 reversed），**均长竖线只保留先后关系，不编码时间间隔**（v3.7 定案：删"线长≈间隔"承诺）。

| 列 | 内容 | 字号 | 字重 | 色值 | 说明 |
|----|------|------|------|------|------|
| 左列 | 时间 `14:32:01` + 时间线 `│` 竖线 + `●` 节点 | 11 | 400 | TEXT.SECONDARY | **tabular-nums** 等宽，竖线均长不编码间隔 |
| 右列 | 事件 antd SVG 图标 + 文本 | 12 | 400 | TEXT.TERTIARY | `<PlayCircleOutlined/>` `<PauseCircleOutlined/>` `<ReloadOutlined/>` |

**时序与关系表达**：
1. 从上到下按时间倒序（最新在顶，遵循现状 reversed）
2. 均长竖线串起各事件──只保留先后顺序，不编码间隔长短
3. 每个事件节点圆点闭环，强化"连续时间序列"
4. `role="log"` + `aria-live="polite"`，新事件实时播报

**key 与格式化**：每行 key = `` `${e.time}-${e.kind}` ``（唯一，P2-13）；时间 `HH:MM:SS` 固定 tabular-nums；间隔疏密靠时间数字区分，竖线不做比例编码。

---

### 3.7 颜色规范超总表

| 用途 | 色值 Token | 字重 | 用在哪 |
|------|-----------|------|--------|
| 核心数值 | `Colors.TEXT.PRIMARY #595959` | 600 | T 总数、耗时数字、徽标文字 |
| 辅助数值 | `Colors.TEXT.SECONDARY #8c8c8c` | 500 | P/C 值、步骤轮次、时间 |
| 标签/辅助文字 | `Colors.TEXT.TERTIARY #999` | 400 | 标签、事件文本 |
| 正常进行中 | `Colors.PRIMARY #1677ff` | - | Badge running dot |
| 错误（执行级） | `Colors.ERROR #ff4d4f` | - | CloseCircleFilled 红圆 |
| 警告（重试/截断） | `Colors.WARNING #AD6800` | 500 | SyncOutlined / WarningOutlined（对比度≥4.5:1） |
| 业务错误（请求级） | `Colors.TEXT.SECONDARY #8c8c8c` | - | StopOutlined 灰色 |
| 分隔线 | `Colors.BORDER.LIGHT #f0f0f0` | - | 顶部分隔 |

> WARNING 全链统一 `#AD6800`（P1-6 定案）；P/C、Token 等不再出现裸 PRIMARY/SECONDARY，全用 `TEXT.PRIMARY`/`TEXT.SECONDARY` 全称。

---

### 3.8 无障碍与键盘导航

**补全清单**：

| 位置 | 现状 | 改进 |
|------|------|------|
| G6 上下文入口 | 无 role/tabIndex/aria | `role="button"` + `aria-haspopup="dialog"` + `aria-expanded` + `tabIndex={0}` + `onKeyDown`（v4.2 经 `FloatingEntry` 实现，见 6.5.2.4；调用见 6.5.3.8） |
| G8 事件入口 | 无 role/tabIndex/aria | `role="button"` + `aria-haspopup="dialog"` + `aria-expanded` + `tabIndex={0}` + `onKeyDown`（v4.2 经 `FloatingEntry` 实现，见 6.5.2.4；调用见 6.5.3.4） |
| 浮层卡片 | 无（新增） | 卡片容器 `role="dialog"` + `aria-label="上下文详情/事件序列"`，焦点移入、Esc 关闭回入口 |
| TrustPanel 折叠 | ✅ 已有 role/aria/keyboard | 不变 |
| TrustPanel 撤销按钮 | 纯 span × | 改 antd Button + aria-label |
| 过程事件列表 | 无 role | 卡片内 `role="log"` + `aria-live="polite"` |

**浮层入口键盘操作**（G6 上下文 / G8 事件共用）：

| 按键 | 行为 |
|------|------|
| `Tab` | 依次聚焦 G6 → G8 入口（`role="button"` + `tabIndex={0}`） |
| `Enter` / `Space` | 打开对应浮层卡片（钉住） |
| `Shift+Tab` | 向后导航到 Token 行（`role="status"`） |
| 卡片内 `Esc` | 关闭卡片，焦点回到触发入口 |

**信任 Drawer 键盘操作**：

| 按键 | 行为 |
|------|------|
| `Enter` | 触发信任按钮，打开 Drawer |
| `Esc` | 关闭 Drawer，焦点回到触发按钮 |
| `Tab` | 首列撤销 → 对象 → 下一行撤销（视觉/焦点顺序一致） |
| `Enter` / `Space`（撤销聚焦时） | 触发 Modal.confirm 二次确认 |

**焦点可见性**：G6/G8 浮层入口与撤销按钮 `:focus-visible` 显式 outline（2px PRIMARY 蓝），无鼠标纯键盘可操作。

---

### 3.9 响应式断点与浮层热区（P1-9 落地，v4.1 双浮层定案）

**G1~G8 断点行为矩阵**：

| 断点 | G1 状态 | G2 耗时 | G3 进度 | G4 异常 | G5 Token | G6 上下文入口 | G7 信任 | G8 事件入口 |
|------|---------|---------|---------|---------|----------|-----------|---------|---------|
| ≥ 1280px | 完整 | 完整 | 完整（`3步·2轮`） | 完整 | 完整（本轮/累计并排） | 完整（两段式） | 完整 | 完整 |
| 1280~960px | 完整 | 完整 | 收窄（仅留数字，Tooltip 展开） | 完整 | 累计段收窄 | 收窄（数字+▸，明细进浮层①） | 完整 | 完整 |
| 960~768px | 完整 | 完整 | 收窄 | 省略（maxWidth 200 + ellipsis + Tooltip 全文） | 累计段进浮层 | 收窄（明细进浮层①） | 仅计数 | 完整 |
| < 768px | 完整 | 合并进 G3 | 合并 | 省略 | 基础行恒定，**明细全部进浮层** | 条目浓缩进浮层① | 仅计数 | 完整 |

**浮层热区定案**（G6/G8 双入口，hover 规格 2）：

- **G8 事件入口**：主热区 `32px × 32px` 圆角 8（click 触发开卡片，键盘鼠标均可点；v4.2 开合唯一真源为 antd trigger + `onOpenChange`，入口无手动 toggle）；hover 背景 `#fafafa→#f0f0f0` 淡入、图标 TERTIARY→PRIMARY、展开态 `rotate(180deg)`、`transition 0.2s ease`、`cursor: pointer`
- **G6 上下文入口**：整段（标签+数值+▸）热区 ≥ 32px，同规格背景/色变 hover；内嵌箭头指示符
- 入口 `user-select: text`、信息位子元素（G1~G5 各 span）不参与触发，避免与文本选中冲突（v4.1：整行已不再折叠，热区只归各自入口）
- 浮层位置：G8 事件卡片 `placement="bottomRight"`（antd 真值，语义 `bottom-end`）锚定入口**右缘、向左展开**（窄屏右贴安全边距不顶出视口）；G6 上下文卡片 `placement="bottomLeft"`（语义 `bottom-start`）锚定**左缘、向右展开**；双卡均 `mouseEnterDelay=0.15` / `mouseLeaveDelay=0.3` 防抖（v4.3 实码校正）

```css
/* 外层容器允许换行，G5 Token 区最小宽度不为 0 */
.taskinfo-bar { display: flex; flex-wrap: wrap; row-gap: 4px; }
.taskinfo-token { min-width: 0; min-height: 20px; }
.taskinfo-token-inner {
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
/* 浮层入口热区（hover 规格 2；已展开态 rotate 180°） */
.taskinfo-entry {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 32px; min-height: 32px; border-radius: 8px;
  cursor: pointer; color: Colors.TEXT.TERTIARY;
  transition: background 0.2s ease, color 0.2s ease, transform 0.2s ease;
}
.taskinfo-entry:hover { background: #f0f0f0; color: Colors.PRIMARY; }
.taskinfo-entry[data-open="true"] svg { transform: rotate(180deg); }
/* 键盘焦点可见性（3.8：无鼠标纯键盘可操作，2px PRIMARY 蓝 outline） */
.taskinfo-entry:focus-visible { outline: 2px solid Colors.PRIMARY; outline-offset: 2px; }
```

> 落盘：本段 CSS 追加至 `frontend/src/index.css` 尾部（全局样式，带编辑历史署名+日期；见 6.5.1）。

---

## 四、设计决策（D1~D5）

| # | 问题 | 选项 A | 选项 B | 定案 |
|---|------|--------|--------|------|
| D1 | Token P/C 露出来还是 hover？ | 露出来（占空间） | hover 看（紧凑） | **A：露出来**，核心监控信息 |
| D2 | TrustPanel 展开用浮层还是固定在第二行？ | absolute 浮层 | 固定第二行 | **Drawer 侧滑面板**，撤销移入每行首列 + Modal.confirm |
| D3 | 过程事件时间用绝对还是相对？ | `14:32:01` | `12秒前` | **A：绝对时间**，无需定时刷新 |
| D4 | collapsed 持久化方案？ | localStorage | 上提 state | ~~A：localStorage~~ **v4.1 取消折叠态机，D4 失效** |
| D5 | 上下文段是否独立成番号？ | 独立（G6） | 依附 token 行 | **A：独立**，为后续优化预留挂载点 |

## 五、设计令牌索引

| 令牌 | 值 | 用途 |
|------|-----|------|
| `Colors.TEXT.PRIMARY` | `#595959` | 核心数值、耗时、加粗 |
| `Colors.TEXT.SECONDARY` | `#8c8c8c` | 辅助数值、时间、P/C |
| `Colors.TEXT.TERTIARY` | `#999` | 标签、事件文本 |
| `Colors.PRIMARY` | `#1677ff` | Badge running、焦点 outline |
| `Colors.ERROR` | `#ff4d4f` | 执行级错误红圆 |
| `Colors.WARNING` | `#AD6800` | 重试/截断警告（对比度≥4.5:1） |
| `Colors.BORDER.LIGHT` | `#f0f0f0` | 分隔线 |
| `FontSize.SECONDARY` | 12 | 主体数值 |
| `FontSize.SMALL` | 11 | 标签（上下文/时间） |
| `FontSize.CAPTION` | 10 | G8 事件入口、极小注释 |
| `Spacing.XS` | 4 | 紧凑间距 |

---

## 六、代码复用与模块划分（10 大规范核查）

> 以第三章改进设计为依据，按 10 大编码规范（日常 6 条：SRP / DRY / KISS-DIRECT / SLAP / YAGNI / 禁止 backward；重构 4 条：OCP / LSP / ISP / 复用优先）核查可复用逻辑，明确抽独立文件还是留在组件内。

### 6.1 可复用逻辑清单（先查后建，禁止重复造轮子）

| 可复用逻辑 | 设计中重复出现处 | 违反规范 | 结论：抽取粒度 |
|------------|--------------------|----------|----------------|
| **标签+数值两段式**结构 | G5/G6/各信息位同构定义 ≥4 处 | DRY | **抽独立组件 `MetricItem.tsx`** |
| **省略文本 + Tooltip** | G4 长错误、G5 收窄、浮层摘要 ≥4 处 | DRY | **抽独立组件 `EllipsisTip.tsx`** |
| **状态 → 文案/色值/图标**映射 | BADGE_MAP、上下文 4 态、事件图标映射 | DRY + SRP | **抽独立常量文件 `infoMaps.ts`** + 纯函数 `mapStatus()` |
| **浮层入口（Popover 壳 + 热区 a11y + 键盘）** | G6 上下文入口 / G8 事件入口同构（Popover 6 props + 入口 a11y 9 属性 + Enter/Space 处理，约 17 行×2 处）+ Esc/焦点管理（3.8/7.3 有测无实现） | DRY | **抽独立组件 `FloatingEntry.tsx`**（v4.2；卡片内容/样式留调用方注入） |
| **等宽数字**规范 | 耗时、事件时间、token 数都用 tabular-nums | DRY | 共享 style 常量（复用 stepStyles 令牌），不新建文件 |
| **时间格式化** | `toLocaleTimeString()` 多处 | DRY/复用优先 | **先查** `src/utils/` 已有工具；无则纯函数 `formatTime()` |
| **Drawer + Modal.confirm 撤销** | 仅信任清单 1 处 | YAGNI | **不抽文件**，留 TrustPanel.tsx 内部函数 |
| **G7 信任可点击文字样式** | 仅 1 处 | YAGNI | **不抽组件**，留 TaskInfoBar.tsx |
| **信息位 G1~G8 渲染分发** | 8 个信息位 | KISS-DIRECT / SLAP | **禁止工厂/注册表**，直接 if/elif 或 map 数组渲染 |

### 6.2 抽取决策（单函数 or 单文件判定）

| 单元 | 粒度 | 抽文件理由 | 不抽理由 |
|------|------|-----------|----------|
| `MetricItem`（标签+数值+可选图标） | 独立组件/文件 | 4 处重复、props 稳定（label/text/tone/icon），改一处全行同构 | — |
| `EllipsisTip`（文本 + maxWidth ellipsis + Tooltip 全文） | 独立组件/文件 | 4 处 hover/省略场景，行为一致 | — |
| `infoMaps.ts`（状态映射常量 + `mapStatus` 纯函数） | 独立常量模块 | 状态语义集中管理，新增状态仅加映射（OCP 扩展） | — |
| `FloatingEntry`（Popover 壳 + 热区 a11y + 键盘） | 独立组件/文件 | G6/G8 双入口同构（约 17 行×2 处），props 稳定（open/onOpenChange/placement/cardId/ariaLabel/content/children）；抽后 G8 双重写入类漂移可防；Esc/焦点内聚（3.8/7.3 断言有实现归属） | — |
| `formatTime()` | 独立函数 | 跨 G1~G8 多处时间展示 | 若 `src/utils/` 已有则**直接复用** |
| `confirmRevoke()` | 组件内函数 | — | 单处使用，抽文件违反 YAGNI |
| G7 可点击样式 | 组件内样式 | — | 单处使用，禁止过早抽象 |

**判定规则**：组件/纯函数且**复用处 ≥ 2** → 独立文件；**单处使用** → 留在所在组件，宁简勿繁（KISS-DIRECT + YAGNI）。

### 6.3 新建文件清单（全前端）

| 文件 | 职责 | 存放位置 |
|------|------|----------|
| `MetricItem.tsx` | 标签（灰 11px）+ 数值（加粗 12px）+ 可选 SVG 图标，支持 tone/截断态 | `frontend/src/features/chat/components/taskinfo/` |
| `EllipsisTip.tsx` | 省略文本 + Tooltip 全文的封装 | 同上 |
| `infoMaps.tsx` | BADGE_MAP / CONTEXT_STATE_MAP(4 态) / EVENT_ICON_MAP + `mapStatus()` 纯函数（v4.3：含 JSX 改 `.tsx`，无扩名 import 零影响） | 同上 |
| `FloatingEntry.tsx` | G6/G8 双浮层入口公共壳：Popover 配置（hover/click 双触发、0.15/0.3s 延时、arrow）+ `taskinfo-entry` 热区 a11y + Enter/Space/Esc 键盘 + 单真源开合 + 焦点管理（v4.2，DRY；v4.3 placement `bottomLeft/bottomRight`） | 同上 |

### 6.4 复用优先核查纪律（实现前必查）

1. **先查后建**：写代码前先查 `src/utils/`、`src/theme/tokens.ts`、现有 taskinfo/ 组件，有则复用，无则新建并入库
2. **令牌复用**：颜色/字号/间距一律引用 `stepStyles.ts`（Colors/FontSize/Spacing），禁止硬码（P2-12）
3. **图标复用**：全部 antd icon（内联 SVG），禁 emoji/纯文本符号（3.4 选型）
4. **禁止局部重造**：时间格式化若已有 `formatTime` 直接调用，不新写重复
5. **不提前抽象**：撤销确认、信任可点击样式等单处逻辑留组件内，出现第二次重复再抽（YAGNI）

---

### 6.5 真实代码与改进差分（全量，一份不落）

> 以 TaskInfoBar / TrustPanel / useTaskInfo / stepStyles / time / InputCore 六份真实源码为基准逐项落地。diff 统一 `-` 为现状、`+` 为改进，行号均按改造前文件。本节省略"编辑历史"注释块中被替换的旧行，新增行必带署名+日期。
>
> 编制人：小欧 · 编制时间：2026-09-09 00:05:00

#### 6.5.1 改动总览与工作量

| 文件 | 涉及项 | 新增 | 删除 | 净变 |
|------|--------|-----:|-----:|-----:|
| 新建 `infoMaps.ts` | P1-8 / P2-15 / P2-14 辅助 | 约 90 行 | 0 | +90 |
| 新建 `MetricItem.tsx` | P1-7 / P1-8 / 6.x 复用 | 约 55 行 | 0 | +55 |
| 新建 `EllipsisTip.tsx` | P1-6 / 6.x 复用 | 约 35 行 | 0 | +35 |
| 新建 `FloatingEntry.tsx` | v4.2 G6/G8 双浮层入口公共壳（含 Esc/焦点管理） | 约 85 行 | 0 | +85 |
| 修改 `TaskInfoBar.tsx` | P0-1/2/3、P1-5/6/7/8/9/11、P2-12/13/16/17、v4.1 双浮层、v4.2 FloatingEntry 调用 + G8 双写修复 | 约 150 行 | 约 70 行 | +80 |
| 修改 `TrustPanel.tsx` | P0-4、P1-10、P2-18 | 约 85 行 | 约 55 行 | +30 |
| 修改 `useTaskInfo.ts` | P2-14 | 1 行 | 1 行 | 0 |
| 修改 `stepStyles.ts` | P1-6（WARNING 色值） | 1 行 | 1 行 | 0 |
| 修改 `src/utils/time.ts` | 3.6（formatTimeHMS） | 约 9 行 | 0 | +9 |
| 修改 `InputCore.tsx` | P1-11（分隔线归属） | 1 行 | 0 | +1 |
| 修改 `src/index.css` | 3.9 热区样式落盘（`.taskinfo-entry` + `:focus-visible`，全局样式，带编辑历史署名） | 约 20 行 | 0 | +20 |

**工作量结论**：共 11 个文件、23 项改动（含 v4.1 双浮层重构、v4.2 FloatingEntry 抽取 + G8 双写修复 + Esc/焦点 + 热区 CSS 落盘）；新增约 530 行、删除约 126 行。四份新建文件为纯展示层，无业务逻辑；修改文件全部为样式/交互重构，`useTaskInfo.ts` 仅 1 处时间源替换，零行为变化。

> ⚠️ `Colors.WARNING` 改 `#AD6800` 牵动 6 处既有引用（ToolCallLine/WarningBox/StatusIcon/shapeRenderers×5/Notification 系列）——均为警告图标/边框/文字色，由浅橙变深琥珀后白底对比度全面提升，**视觉增强非退化**；`WARNING_BG: #fffbe6` 或 `Colors.BORDER.*` 不受影响。三堂会审：合规（令牌化）/合理（全链统一）/关联（无白字衬浅橙的反例）均通过。

---

#### 6.5.2 新建文件（4 个，全量真实代码）

##### 6.5.2.1 `infoMaps.tsx`（新建，v4.3 含 JSX 改 `.tsx`）

位置：`frontend/src/features/chat/components/taskinfo/infoMaps.tsx`（v4.3：含 `<WarningOutlined/>` JSX，`.ts` 下 esbuild 报错 `Expected ">" but found "/"`，故改 `.tsx`；无扩名 `from './infoMaps'` 零影响）

```typescript
// 编辑历史: 2026-09-08 小欧 - 六章6.5: 自 TaskInfoBar 抽取状态映射常量+纯函数(DRY/SRP/OCP, 禁止backward 不兼容旧写法)
//   职责: BADGE_MAP(P2-15 cancelled 区分) / CONTEXT_STATE_MAP(4态 P1-8) / EVENT_ICON_MAP(4事件 P1-5)
//   / mapStatus(纯函数) / formatToken(千分位 3.2) — 小欧-2026-09-08
import type { CSSProperties, ReactNode } from 'react';
import {
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ProcessEvent, TaskBadge } from '../../hooks/useTaskInfo';
// v4.3 实码删未用 `Colors`（本文件仅用 tone 字符串，`Colors.WARNING` 由调用方按 tone 取色；留导入 lint 挂）

// ---------- BADGE_MAP（P2-15：cancelled 与 idle 区分） ----------
export interface BadgeEntry {
  status: 'default' | 'processing' | 'warning' | 'success' | 'error';
  text: string;
}
export const BADGE_MAP: Record<TaskBadge, BadgeEntry> = {
  idle: { status: 'default', text: '待命' }, // 灰点灰字，语义"空闲等待"
  running: { status: 'processing', text: '执行中' },
  paused: { status: 'warning', text: '已暂停' },
  completed: { status: 'success', text: '已完成' },
  failed: { status: 'error', text: '失败' },
  cancelled: { status: 'error', text: '已取消' }, // 定案: 红点红字，区分 idle 灰
};

// ---------- CONTEXT_STATE_MAP（P1-8：4 态文案状态机） ----------
export type ContextState = 'ok' | 'summary-only' | 'truncated' | 'empty';
export interface ContextStateEntry {
  text: string; // 数值区文案（ok 态由调用方传入 token，此处留空）
  tone: 'primary' | 'secondary' | 'warning' | 'tertiary';
  icon?: ReactNode;
  tooltip: string;
}
export const CONTEXT_STATE_MAP: Record<ContextState, ContextStateEntry> = {
  'ok': { text: '', tone: 'primary', tooltip: '上下文正常', },
  // 3.3 状态机: summary-only/empty 数值色 TERTIARY(标签级弱文字), 非 SECONDARY(3.3 表/7.3 用例一致)
  'summary-only': { text: '摘要·无计数', tone: 'tertiary', tooltip: '上下文概览尚无 token 计数', },
  'truncated': { text: '', tone: 'warning', icon: <WarningOutlined />, tooltip: '上下文被截断，可能影响回答质量', },
  'empty': { text: '–', tone: 'tertiary', tooltip: '上下文缺失，检查 frames 数据链路', },
};

// ---------- mapStatus（纯函数：输入数据源 → 4 态，供测试直接断言 data-state） ----------
// 输入形态对齐现状三数据源: overview 字符串 / overview 对象{summary,estimated_tokens,truncated} / frames.contextSummary
export interface ContextSource {
  overview?:
    | string
    | { summary?: string; estimated_tokens?: number | null; truncated?: boolean }
    | null;
  contextSummary?: string | null;
}
export const mapStatus = (src: ContextSource): ContextState => {
  const o = src.overview;
  const summary =
    typeof o === 'string' ? o : (o?.summary ?? src.contextSummary ?? null);
  const truncated = typeof o === 'object' && o !== null ? o.truncated === true : false;
  const hasTokens = typeof o === 'object' && o !== null && o.estimated_tokens != null;
  if (truncated) return 'truncated';
  if (summary) return hasTokens ? 'ok' : 'summary-only';
  return 'empty';
};

// ---------- EVENT_ICON_MAP（3.4/P1-5：过程事件统一 antd SVG，禁 emoji） ----------
export const EVENT_ICON_MAP: Record<ProcessEvent['kind'], ReactNode> = {
  started: <PlayCircleOutlined />, // 现状 ▶️   → SVG（3.4 定案）
  paused: <PauseCircleOutlined />, // 现状 ⏸️   → SVG
  resumed: <PlayCircleOutlined />, // 现状 ▶️   → SVG
  retrying: <ReloadOutlined />, // 现状 🔁   → SVG
};

// ---------- formatToken（3.2：T 千分位，1234 → "T 1,234"；无值 → "–"） ----------
// 先查后建结论: src/utils/ 无千分位工具(en-US toLocaleString 全库无命中), 新建
export const formatToken = (n: number | null | undefined): string => {
  if (n == null || Number.isNaN(n)) return '–';
  return `T ${n.toLocaleString('en-US')}`;
};

// ---------- 等宽数字共享样式（P2-16/3.6：耗时、事件时间均用） ----------
export const TABULAR_NUMS: CSSProperties = { fontVariantNumeric: 'tabular-nums' };
```

##### 6.5.2.2 `MetricItem.tsx`（新建）

位置：`frontend/src/features/chat/components/taskinfo/MetricItem.tsx`

```typescript
// 编辑历史: 2026-09-08 小欧 - 六章6.5: 抽"标签灰 + 数值加粗 + 可选分项/图标"两段式通用组件(DRY, G5/G6 ≥4 处复用)
//   支持 detail(P/C 中灰)、tone、icon、maxWidth 截断态、tooltip、data-state(测试钩子) — 小欧-2026-09-08
import React from 'react';
import { Tooltip } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { EllipsisTip } from './EllipsisTip';

export type MetricTone = 'primary' | 'secondary' | 'warning' | 'tertiary';

export interface MetricItemProps {
  label: string; // 标签（灰 11px）
  value: string; // 数值（加粗 12px 或 warning）
  detail?: string; // 可选分项（P/C 等，中灰 12px 500）
  tone?: MetricTone;
  icon?: React.ReactNode;
  maxWidth?: number; // >0 时数值区 ellipsis + Tooltip 全文
  tooltip?: string;
  dataState?: string; // aria/data 钩子（P1-8 测试断言）
}

const TONE_COLOR: Record<MetricTone, string> = {
  primary: Colors.TEXT.PRIMARY,
  secondary: Colors.TEXT.SECONDARY,
  tertiary: Colors.TEXT.TERTIARY, // 3.3: summary-only/empty 标签级弱文字
  warning: Colors.WARNING,
};

export const MetricItem: React.FC<MetricItemProps> = ({
  label,
  value,
  detail,
  tone = 'primary',
  icon,
  maxWidth,
  tooltip,
  dataState,
}) => {
  const body = (
    <React.Fragment>
      {icon && <span style={{ color: TONE_COLOR[tone] }}>{icon}</span>}
      <span
        style={{
          fontSize: FontSize.SECONDARY,
          fontWeight: FontWeight.BOLD,
          color: TONE_COLOR[tone],
        }}
      >
        {value}
      </span>
      {detail && (
        <span
          style={{
            fontSize: FontSize.SECONDARY,
            fontWeight: FontWeight.MEDIUM,
            color: Colors.TEXT.SECONDARY,
          }}
        >
          {detail}
        </span>
      )}
    </React.Fragment>
  );
  const wrapped = maxWidth ? (
    <EllipsisTip text={value} tooltip={tooltip} maxWidth={maxWidth}>
      {body}
    </EllipsisTip>
  ) : tooltip ? (
    <Tooltip title={tooltip}>{body}</Tooltip>
  ) : (
    body
  );
  return (
    <span
      role="status"
      aria-live="polite"
      data-state={dataState}
      title={tooltip}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Spacing.XS,
        fontSize: FontSize.SMALL,
        color: Colors.TEXT.TERTIARY,
      }}
    >
      <span style={{ fontSize: FontSize.SMALL, color: Colors.TEXT.TERTIARY }}>
        {label}
      </span>
      {wrapped}
    </span>
  );
};
```

##### 6.5.2.3 `EllipsisTip.tsx`（新建）

位置：`frontend/src/features/chat/components/taskinfo/EllipsisTip.tsx`

```typescript
// 编辑历史: 2026-09-08 小欧 - 六章6.5: 抽"省略 + Tooltip 全文"封装(DRY, G4 长错误/G5 收窄/G6 hover ≥4 处) — 小欧-2026-09-08
import React from 'react';
import { Tooltip } from 'antd';

export interface EllipsisTipProps {
  text: string;
  tooltip?: string;
  maxWidth: number;
  children?: React.ReactNode;
}

export const EllipsisTip: React.FC<EllipsisTipProps> = ({
  text,
  tooltip,
  maxWidth,
  children,
}) => {
  const inner = (
    <span
      style={{
        display: 'inline-block',
        maxWidth,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        verticalAlign: 'bottom',
      }}
    >
      {children ?? text}
    </span>
  );
  return tooltip ? <Tooltip title={tooltip}>{inner}</Tooltip> : inner;
};
```

##### 6.5.2.4 `FloatingEntry.tsx`（新建，v4.2）

位置：`frontend/src/features/chat/components/taskinfo/FloatingEntry.tsx`

> v4.2 第二轮核查落定：G6/G8 双浮层入口同构（Popover 6 props + 入口 a11y 9 属性 + Enter/Space 键盘，约 17 行×2 处），按 6.2 判定（复用处 ≥ 2 → 独立文件）抽公共壳；卡片内容与卡片样式留调用方注入（SRP：壳只管开合与 a11y，不管卡片语义）。G8 `onClick` 手动 toggle 随抽取一并删除——开合唯一真源为 antd trigger + `onOpenChange`，键盘经 `onOpenChange(!open)` 同路写入，单源无双写。**Esc 关闭 + 焦点管理（3.8/7.3 有测无实现，收敛入壳）**：卡片 `tabIndex={-1}`，入口持有焦点时打开跟进焦点（hover 打开不抢焦点），卡片内 Esc 经 portal 冒泡关闭回入口。

```typescript
// 编辑历史: 2026-09-09 小欧 - v4.2: 抽 G6/G8 双浮层入口公共壳(DRY, 17 行×2 处重复收敛)
//   Popover 配置 + taskinfo-entry 热区 a11y + Enter/Space/Esc 键盘 + 单真源开合 + 焦点管理(3.8/7.3); 卡片内容/样式调用方注入 — 小欧-2026-09-09
import React, { useEffect, useRef } from 'react';
import { Popover } from 'antd';

export interface FloatingEntryProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  placement: 'bottomLeft' | 'bottomRight'; // v4.3 antd 真值：G6 `bottomLeft` 左缘对齐向右展开 / G8 `bottomRight` 右缘对齐向左展开（语义同 3.9 的 bottom-start/end）
  cardId: string; // 卡片 id（= 入口 aria-controls，关系内聚于组件内）
  ariaLabel: string; // 入口 + 卡片共用 aria-label
  cardStyle?: React.CSSProperties; // 卡片容器样式（宽/布局，调用方注入）
  content: React.ReactNode; // 卡片内容（调用方注入，内部 a11y 如 role="log" 自带）
  children: React.ReactNode; // 入口热区内容（G6: MetricItem / G8: DownOutlined + "事件"）
}

export const FloatingEntry: React.FC<FloatingEntryProps> = ({
  open,
  onOpenChange,
  placement,
  cardId,
  ariaLabel,
  cardStyle,
  content,
  children,
}) => {
  const entryRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(open);
  // 打开后焦点入卡(3.8/7.3)：仅当入口持有焦点时跟进（hover 打开不抢焦点）
  useEffect(() => {
    if (open && !wasOpen.current && document.activeElement === entryRef.current) {
      cardRef.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);
  // 卡片内 Esc（portal 内容经 React 树冒泡至外层 div）：关闭 + 焦点回入口(3.8/7.3)
  const closeToEntry = () => {
    onOpenChange(false);
    entryRef.current?.focus();
  };
  return (
    <div
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          closeToEntry();
        }
      }}
    >
      <Popover
        open={open}
        onOpenChange={onOpenChange}
        trigger={['hover', 'click']}
        placement={placement}
        mouseEnterDelay={0.15}
        mouseLeaveDelay={0.3}
        arrow={{ pointAtCenter: true }}
        content={
          <div ref={cardRef} tabIndex={-1} id={cardId} role="dialog" aria-label={ariaLabel} style={cardStyle}>
            {content}
          </div>
        }
      >
        <div
          ref={entryRef}
          className={`taskinfo-entry${open ? ' taskinfo-entry-open' : ''}`}
          data-open={open}
          role="button"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-label={ariaLabel}
          aria-controls={cardId}
          tabIndex={0}
          onClick={(e) => e.stopPropagation()} // 仅止冒泡；开合交还 antd trigger（v4.2 双写修复：删手动 toggle）
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              onOpenChange(!open);
            }
          }}
        >
          {children}
        </div>
      </Popover>
    </div>
  );
};
```

---

#### 6.5.3 TaskInfoBar.tsx 真实差分

##### 6.5.3.1 P0-1 探针删除（3 处全删，零逻辑）

`TaskInfoBar.tsx:24-25`（编辑历史行）、`:76-80`（挂载探针 useEffect）、`:133-142`（onClick 内 console.log）：

```diff
-taskInfoBar.tsx:24-25 删除 2 行编辑历史（[HITL排查探针·临时] 注记）:
- // 编辑历史: 2026-09-08 小欧 - [HITL排查探针·临时]: 第一行onClick加console.log...
- //   定位..."事件区自动展开"是否真触发toggle(...)或组件重挂载; 真机复现确认后删除 — 小欧-2026-09-08

-:76-80 删除挂载探针:
-  // 【HITL排查探针·临时 2026-09-08 小欧】挂载/重挂载日志——...
-  useEffect(() => {
-    console.log('[TaskInfoBar探针] mount', { sessionId, receiving, pid: ... });
-    // eslint-disable-next-line react-hooks/exhaustive-deps
-  }, []);

-:135-140 删除 onClick 内 console.log 块（保留 :141 setCollapsed）:
-    // 【HITL排查探针·临时 2026-09-08 小欧】打印触发toggle的真实事件源——...
-    console.log('[TaskInfoBar探针] toggle 触发', {
-      collapsedBefore: collapsed, target: ..., targetText: ..., isTrusted: ...,
-    });
```

##### 6.5.3.2 文件头（import 区，P1-5/P1-6/P1-8/P2-12 + v4.2）

```diff
  import { Badge } from 'antd'; // v4.2: PopoverTooltip 随 G6/G8 迁入 FloatingEntry/EllipsisTip, 本文件不再直引（v4.3 实码 lint 去未用 Tooltip）
+import {
+  CloseCircleFilled,
+  DownOutlined,
+  StopOutlined,
+  SyncOutlined,
+  WarningOutlined,
+} from '@ant-design/icons'; // 3.4: G4/G8 全 antd SVG（v4.3：过程图标 Pause/Play/Reload 随 EVENT_ICON_MAP 迁 infoMaps，本文件不再直引）
 import type { ExecutionStep } from '../../../../types/execution';
 import type { TaskMetaFrames, LiveError } from '@/types/sse';
 import type { TaskDetail } from '../../../../services/api/task.api';
-import { Colors } from '@/utils/stepStyles'; // 仅 Colors
+import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles'; // P2-12: 硬码数字全令牌化
+import { formatTimeHMS } from '@/utils/time'; // 3.6 时间轴 HH:MM:SS
 import { useTaskInfo } from '../../hooks/useTaskInfo';
 import { TrustPanel } from '../config/TrustPanel';
+import { EllipsisTip } from './EllipsisTip';
+import { MetricItem } from './MetricItem';
+import { FloatingEntry } from './FloatingEntry'; // v4.2: G6/G8 双浮层入口公共壳(见 6.5.2.4)
+import { BADGE_MAP, CONTEXT_STATE_MAP, EVENT_ICON_MAP, TABULAR_NUMS, formatToken, mapStatus } from './infoMaps'; // v4.3 实为 './infoMaps.tsx'，无扩名 import 零影响

-const BADGE_MAP = { idle:...cancelled:... }; // 整块迁入 infoMaps.tsx（P2-15，v4.3 含 JSX 改扩展名）
```

##### 6.5.3.3 P0-3 collapsed 状态机删除 + P2-12 令牌（`:73` 附近）

```diff
 -const [collapsed, setCollapsed] = useState(false);
 -export const COLLAPSE_KEY = 'session_panel_collapsed:taskinfo.bar';
 -const getCollapsed = (): boolean =>
 -  typeof window !== 'undefined' && localStorage.getItem(COLLAPSE_KEY) === '1';
 -const [collapsed, setCollapsed] = useState<boolean>(getCollapsed);
 -const toggleCollapsed = () =>
 -  setCollapsed((v) => {
 -    localStorage.setItem(COLLAPSE_KEY, v ? '0' : '1');
 -    return !v;
 -  });
 +// v4.1: 取消整行折叠(P0-3), 上述状态机/localStorage 键/全部 collapsed 引用整体删除
 +// 新增: eventsOpen、ctxOpen 各 useState(false)(见 6.5.3.4 / 6.5.3.8), 随组件轻量瞬态, 不持久化
```

##### 6.5.3.4 P0-2 + P1-9 + P1-11 + v4.1 G8 事件入口 + v4.2 FloatingEntry 复用/G8 双写修复（`:112-143`，外层结构与浮层热区）

```diff
   <div
     style={{
       background: 'transparent',
       border: 'none',
 -      borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
 -      padding: '8px 0 0',
 +      borderTop: 'none', // P1-11 定案 B: 分隔线归属 input 区上沿(见 6.5.3.9), 本条不带上边框
 +      padding: `${Spacing.MD}px 0 0`, // P2-12: 8px → Spacing.MD
       display: 'flex',
       flexDirection: 'column',
 -      gap: 8,
 +      gap: Spacing.MD,
       textAlign: 'left',
     }}
   >
+   {/* v4.1: 信息带恒定 1 行, 整行折叠态机已删除(P0-3 随删); G1~G6 渲染其中, 无整行点击 */}
     <div
       style={{
         display: 'flex',
         alignItems: 'center',
 -        gap: 12,
 -        cursor: 'pointer',
 -        flexWrap: 'nowrap',
 +        gap: Spacing.LG,
 +        cursor: 'default',
 +        flexWrap: 'wrap',
 +        userSelect: 'text', // 3.9: 文本可选中, 点击不触发任何折叠
       }}
-      onClick={(e) => {
-        // 【HITL排查探针·临时...】console.log(...)  ← P0-1 删除 6.5.3.1
-        setCollapsed((v) => !v); // v4.1: 整行折叠取消, collapsed 随 P0-3 删除
-      }}
     >
```

**右组（G7 信任 + G8 事件入口）真实实现**（v4.1：G8 承载事件卡片；v4.2：壳层 a11y/热区/键盘收敛入 `FloatingEntry` 见 6.5.2.4——满足 3.8 G8 入口键表与 3.1.3 hover 规格 2）：

```typescript
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.MD,
          flexShrink: 0,
          marginLeft: 'auto',
        }}
      >
        {/* G7 信任: 内为 TrustPanel 触发按钮(6.5.4.3 改 Drawer 打开), 不承担折叠 */}
        <TrustPanel sessionId={sessionId} />
        {/* G8 事件入口(v4.1/P0-2/P2-12, v4.2 经 FloatingEntry 实现): 浮层② 事件卡片, 热区 32×32, hover 规格 2, 3.8 键盘 */}
        {/* v4.2 双写修复: 删 onClick 手动 setEventsOpen toggle(与 antd trigger click 双重写入), 开合唯一真源为 trigger + onOpenChange, 与 G6 对齐 */}
        <FloatingEntry
          open={eventsOpen}
          onOpenChange={setEventsOpen}
          placement="bottomRight" // v4.1: 右缘对齐 G8, 向左展开(3.9)（v4.3 antd 真值，语义 bottom-end）
          cardId="taskinfo-events-card"
          ariaLabel="事件序列"
          cardStyle={{ width: 520, maxWidth: '90vw' }}
          content={eventsTimeline} // 6.5.3.10 移入: role="log" + aria-live + maxHeight 40vh 内滚
        >
          <span style={{ fontSize: FontSize.CAPTION }}>
            <DownOutlined style={{ fontSize: FontSize.CAPTION }} /> {/* P1-5 + v4.1: 方向=弹出语义 */}
            事件
          </span>
        </FloatingEntry>
      </div>
```

> v4.1 落地说明：整行折叠取消（P0-3 状态机删除），事件序列由 G8 独立浮层承载；热区/hover 全部收敛在 `taskinfo-entry`（3.9 CSS：hover 背景淡入 + 图标 PRIMARY + `data-open` 时 rotate 180°），满足 3.8 G8 键表与 3.9 热区定案。`eventsOpen` 以 `useState(false)` 声明。

```diff
      </div>
```

##### 6.5.3.5 P1-5 + P1-6 G4 异常（`:166-186`）

```diff
-          {info.liveMeta && (
-            <span style={{ fontSize: 12, color: Colors.WARNING, marginLeft: 2 }}>
-              [{info.liveMeta.kind === 'retrying' ? '🔁' : info.liveMeta.kind === 'error'
-                ? (info.liveMeta.requestLevel ? '⛔' : <CloseCircleFilled .../>)
-                : '⚠'} {info.liveMeta.text}]
-            </span>
-          )}
+          {info.liveMeta && (
+            <EllipsisTip text={info.liveMeta.text} tooltip={info.liveMeta.text} maxWidth={200}>
+              <span
+                style={{
+                  fontSize: FontSize.SECONDARY,
+                  fontWeight: FontWeight.MEDIUM, // P1-6: 加 500
+                  color: // P1-6: 分级着色
+                    info.liveMeta.kind === 'error'
+                      ? info.liveMeta.requestLevel
+                        ? Colors.TEXT.SECONDARY // 请求级: StopOutlined 灰
+                        : Colors.ERROR // 执行级: CloseCircleFilled 红
+                      : Colors.WARNING, // retrying/truncated: #AD6800 (对比度≥4.5:1)
+                  marginLeft: Spacing.XS,
+                }}
+              >
+                {info.liveMeta.kind === 'retrying' ? (
+                  <SyncOutlined spin /> // P1-5: 🔁 → SyncOutlined spin
+                ) : info.liveMeta.kind === 'error' ? (
+                  info.liveMeta.requestLevel ? (
+                    <StopOutlined /> // P1-5: ⛔ → StopOutlined
+                  ) : (
+                    <CloseCircleFilled style={{ fontSize: 12, color: Colors.ERROR }} />
+                  )
+                ) : (
+                  <WarningOutlined /> // P1-5: ⚠ → WarningOutlined
+                )}{' '}
+                {info.liveMeta.text}
+              </span>
+            </EllipsisTip>
+          )}
```

##### 6.5.3.6 P2-16 耗时 + G3 进度 + P2-12 令牌（`:158-164`）

```diff
           <span
             style={{
 -              fontSize: 12,
 +              fontSize: FontSize.SECONDARY,
               color: Colors.TEXT.PRIMARY,
 -              fontWeight: 500,
 +              fontWeight: FontWeight.BOLD, // 3.1.2: G2 耗时 600
 +              ...TABULAR_NUMS, // P2-16: 等宽数字, 位数不抖动
             }}
           >
 -            耗时 {Math.round(shownElapsed)}s
 +            耗时 {Math.round(shownElapsed)}s
           </span>
```

```diff
<!-- G3 进度（:162-164）：3.1.2 表 G3 = `3步·2轮`/12px/400/SECONDARY -->
-          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
-            步骤 {info.stepCount} / 轮次 {info.llmCallCount}
-          </span>
+          <span style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}>
+            {info.stepCount}步·{info.llmCallCount}轮
+          </span>
```

##### 6.5.3.7 P2-15 徽标（`BADGE_MAP` 迁入 `infoMaps.ts` 6.5.2.1）

`:56-63` 原 `BADGE_MAP` 整块删除，`:75` `const b = BADGE_MAP[info.badge];` 改为：

```diff
 -const BADGE_MAP = { idle:...running:...cancelled:... }; // 已迁 infoMaps.ts
 -const b = BADGE_MAP[info.badge];
 +const b = BADGE_MAP[info.badge]; // 同 import, cancelled = {status:'error', text:'已取消'}(P2-15)
```

> G1 字重（3.1.2 表 G1：12px/500/PRIMARY）：如需 500 字重，`<Badge status={b.status} text={b.text} style={{ fontWeight: 500 }} />`；现状 antd Badge 默认 normal，此项为增量可选，不阻塞（Badge status 色已达标）。

##### 6.5.3.8 P1-7 + P1-8 + v4.1 G5 Token / G6 上下文入口重构 + v4.2 FloatingEntry 复用（`:193-257` 整块替换）

> P1-8 现状块含 `:243 {' 🔴'}` 截断红点（3.4 表行 5），随整块替换一并删除——truncated 态改由 WarningOutlined 承担（3.3 状态机）。

```diff
         <div style={{ display:'flex', alignItems:'center', gap:Spacing.MD, flex:1,
-                      minWidth:0, justifyContent:'center' }}>
-          <Tooltip title={...本轮 P/C/T...}>
-            <span ...>本轮 T{info.roundUsage?.total ?? 0} (P{...}/C{...})</span>
-          </Tooltip>
-          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>·</span>
-          <Tooltip title={...任务累计...}>
-            <span ...>本任务累计 T{...} (P{...}/C{...})</span>
-          </Tooltip>
-          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>·</span>
-          {contextOverview 4 分支 现状 :231-256}
+        minWidth:0, justifyContent:'center', flexWrap:'wrap' }}>
+          {/* G5 本轮: 标签灰 + T 加粗 + P/C 中灰(P1-7 两段对称) */}
+          <MetricItem
+            label="本轮"
+            value={formatToken(info.roundUsage?.total ?? 0)}
+            detail={`P ${info.roundUsage?.prompt ?? 0} / C ${info.roundUsage?.completion ?? 0}`}
+            tooltip={`本轮 P ${info.roundUsage?.prompt ?? 0} / C ${info.roundUsage?.completion ?? 0} / T ${info.roundUsage?.total ?? 0}`}
+          />
+          <span style={{ fontSize: FontSize.SECONDARY, color: Colors.BORDER.LIGHT }}>·</span>
+          <MetricItem
+            label="累计"
+            value={formatToken(info.taskAccumulated?.total_tokens ?? info.usage.total)}
+            detail={`P ${info.taskAccumulated?.prompt_tokens ?? info.usage.prompt} / C ${info.taskAccumulated?.completion_tokens ?? info.usage.completion}`}
+            tooltip="任务累计 P/C/T"
+          />
+          {/* G6 上下文(v4.1): 基础行 MetricItem 为浮层① 入口锚点, data-state 供测试 */}
+          {(() => {
+            const ctxState = mapStatus({
+              overview: info.overview,
+              contextSummary: frames.contextSummary,
+            });
+            const ctx = CONTEXT_STATE_MAP[ctxState];
+            const tokens =
+              typeof info.overview === 'object' && info.overview
+                ? info.overview.estimated_tokens
+                : null;
+            const summary =
+              typeof info.overview === 'string'
+                ? info.overview
+                : info.overview?.summary ?? frames.contextSummary ?? '';
+            // 3.3 状态机: ok/truncated 均显 "{n} tok"(truncated 警告色+图标); summary-only/empty 用态文案
+            const showTokens = ctxState === 'ok' || ctxState === 'truncated';
+            // v4.2: G6 入口经 FloatingEntry 实现(见 6.5.2.4), onClick 保持仅 stopPropagation(与 G8 对齐后单真源)
+            return (
+              <FloatingEntry
+                open={ctxOpen}
+                onOpenChange={setCtxOpen}
+                placement="bottomLeft" // v4.1: 左缘对齐 G6; 窄屏右贴安全边距(v4.1 定案)（v4.3 antd 真值，语义 bottom-start）
+                cardId="taskinfo-context-card"
+                ariaLabel="上下文详情"
+                cardStyle={{
+                  width: 320,
+                  maxWidth: '90vw',
+                  display: 'flex',
+                  flexDirection: 'column',
+                  gap: Spacing.SM,
+                  fontSize: FontSize.SECONDARY,
+                  color: Colors.TEXT.SECONDARY,
+                }}
+                content={
+                  <>
+                    <div style={{ fontWeight: FontWeight.BOLD, color: Colors.TEXT.PRIMARY }}>上下文详情</div>
+                    <div>摘要: {summary.slice(0, 60)}{summary.length > 60 ? '…' : ''}</div>
+                    <div>估算 token: {showTokens ? `${(tokens ?? 0).toLocaleString('en-US')} tok` : '—'}</div>
+                    <div style={{ color: ctx.tone === 'warning' ? Colors.WARNING : Colors.TEXT.TERTIARY }}>
+                      {ctxState === 'ok' ? '正常' : ctx.tooltip}
+                    </div>
+                  </>
+                }
+              >
+                <MetricItem
+                  label="上下文"
+                  value={
+                    showTokens
+                      ? `${(tokens ?? 0).toLocaleString('en-US')} tok`
+                      : ctx.text
+                  }
+                  tone={ctx.tone}
+                    icon={ctx.icon}
+                    dataState={ctxState}
+                  />
+              </FloatingEntry>
+            );
+          })()}
         </div>
```

##### 6.5.3.9 P1-11 分隔线归属（定案 B，双文件）

`TaskInfoBar.tsx:117`：本条 `borderTop` 已删（6.5.3.4）；分隔线上移至 input 区——`InputCore.tsx:45`（注：若 input 区另有顶层容器，borderTop 应上移至该容器顶部、紧贴 TaskInfoBar 下沿，语义最准；TextArea 同色覆盖仅作代码归属落点）：

```diff
   <TextArea
     ... // 不变
-    style={{ borderColor: Colors.BORDER.LIGHT, borderRadius: Radius.SM }}
+    style={{
+      borderColor: Colors.BORDER.LIGHT,
+      borderTop: `1px solid ${Colors.BORDER.LIGHT}`, // P1-11 定案 B: 顶部分隔线归属 input 区上沿
+      borderRadius: Radius.SM,
+    }}
   />
```

##### 6.5.3.10 P2-13 + P2-17 过程事件时间轴 → v4.1 事件卡片内容（`:272-293` 移入 G8 FloatingEntry content，v4.2）

`eventsTimeline`（6.5.3.4 引用）＝本块渲染结果；`{!collapsed && ...}` 条件删除（v4.1 无折叠态）：

```diff
-      {!collapsed && info.processEvents.length > 0 && (
-        <div
-          style={{ maxHeight: 72, overflowY: 'auto', scrollbarWidth: 'thin',
-                   borderTop: `1px solid ${Colors.BORDER.LIGHT}`, paddingTop: 8, marginTop: 0 }}
-        >
-          {info.processEvents.map((e, i) => (
-            <div key={i} style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
-              {e.kind === 'started' && '▶️ '}
-              {e.kind === 'paused' && '⏸️ '}
-              {e.kind === 'resumed' && '▶️ '}
-              {e.kind === 'retrying' && '🔁 '}
-              {e.text} {new Date(e.time).toLocaleTimeString()}
-            </div>
-          ))}
-        </div>
-      )}
+      {/* eventsTimeline(v4.1, v4.2 经 FloatingEntry 注入): 渲染于 G8 卡片 content(6.5.3.4), 无折叠态条件 */}
+      {info.processEvents.length > 0 && (
+        <div
+          role="log"
+          aria-live="polite" // 3.6: 新事件实时播报
+          style={{ maxHeight: '40vh', // v4.1/P2-17: 浮层卡片内滚, 不撑 TaskInfoBar 高度
+                   overflowY: 'auto', scrollbarWidth: 'thin' }}
+        >
+          {info.processEvents.map((e) => (
+            <div
+              key={`${e.time}-${e.kind}`} // P2-13: 唯一 key, 弃索引 {i}
+              style={{
+                display: 'flex',
+                alignItems: 'center',
+                gap: Spacing.MD,
+                fontSize: FontSize.SECONDARY,
+                lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
+              }}
+            >
+              {/* 左列: 时间 HH:MM:SS + 均长竖线(3.6 定案, 不编码间隔) */}
+              <span
+                style={{
+                  fontSize: FontSize.SMALL, // 11px
+                  color: Colors.TEXT.SECONDARY,
+                  ...TABULAR_NUMS, // P2-13: 等宽防抖动
+                  width: 56,
+                  textAlign: 'right',
+                  flexShrink: 0,
+                }}
+              >
+                {formatTimeHMS(e.time)}
+              </span>
+              <span style={{ color: Colors.BORDER.LIGHT }}>│</span>
+              {/* 右列: antd SVG 图标 + 文本(P1-5); 图标即 3.6 "● 节点", 不另加 ● 文本符 */}
+              <span style={{ color: Colors.TEXT.TERTIARY, minWidth: 0 }}>
+                {EVENT_ICON_MAP[e.kind]}
+                <span style={{ marginLeft: Spacing.XS }}>{e.text}</span>
+              </span>
+            </div>
+          ))}
+        </div>
+      )}
```

> 时间轴接线说明：`info.processEvents` 已在 `useTaskInfo` 尾部 `reverse()`（最新在顶，现状已如此），渲染顺序即时间倒序，故不再二次排序。事件卡片宽 520px（6.5.3.4），`role="log"` + `aria-live` 随卡片进入 G8 FloatingEntry（v4.2，3.8 浮层卡片行）。

---

#### 6.5.4 TrustPanel.tsx 真实差分（P0-4/P1-10/P2-18）

##### 6.5.4.1 import 区

```diff
 import React, { useCallback, useEffect, useRef, useState } from 'react';
-import { Tooltip } from 'antd';
+import { Button, Drawer, Empty, Modal, Table, Tooltip } from 'antd';
+import { CloseOutlined } from '@ant-design/icons';
 import { trustApi, type TrustedTool } from '../../../../services/api/task.api';
-import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
+import { Colors, FontSize, FontWeight } from '@/utils/stepStyles'; // v4.3 实码 lint 去未用 Spacing
```

##### 6.5.4.2 P0-4 + P2-18 撤销：Button + Modal.confirm（`:74-82` + `:158-174`）

```diff
-  const revoke = async (toolName: string, path: string | null) => {
-    if (!sessionId) return;
-    try {
-      await trustApi.revokeTrust(sessionId, toolName, path);
-      await load();
-    } catch { /* TB-02: 防 unhandledrejection */ }
-  };
+  // P0-4: 撤销前 Modal.confirm 二次确认（文案含工具名），确认才删
+  const confirmRevoke = (t: TrustedTool) => {
+    if (!sessionId) return;
+    Modal.confirm({
+      title: '确认撤销信任？',
+      content: `撤销后将重新弹框确认「${t.toolName} › ${t.path ?? '全局'}」。`,
+      okText: '确认撤销',
+      cancelText: '取消',
+      onOk: async () => {
+        try {
+          await trustApi.revokeTrust(sessionId, t.toolName, t.path);
+          await load();
+        } catch {
+          /* 撤销失败保持清单不变 */
+        }
+      },
+    });
+  };
```

`:158-174` 撤销渲染（在 Drawer 内，见 6.5.4.3）：

```diff
-              <span onClick={...revoke...} title="撤销信任">×</span>
+              <Button
+                type="text"
+                size="small"
+                icon={<CloseOutlined />}
+                aria-label={`撤销信任 ${t.toolName}`} // P2-18: 屏读语义
+                onClick={(e) => {
+                  e.stopPropagation();
+                  confirmRevoke(t); // P0-4: 弹确认
+                }}
+              />
```

##### 6.5.4.3 P1-10 信任 Drawer（`:84-178` 展开列表 → Drawer 侧滑）

```diff
-  const [expanded, setExpanded] = useState(false);
-  const hasTools = tools.length > 0;
-  const countColor = hasTools ? Colors.TEXT.PRIMARY : Colors.TEXT.TERTIARY;
+  const [drawerOpen, setDrawerOpen] = useState(false);
+  const triggerRef = useRef<HTMLDivElement>(null);
+  const openDrawer = () => setDrawerOpen(true);
+  const closeDrawer = () => {
+    setDrawerOpen(false);
+    triggerRef.current?.focus(); // 3.5: 关闭后焦点回到触发按钮
+  };
+  // 3.1.3 方案A: 文字样式(PRIMARY + 500)提示可点
   return (
-    <div style={{ padding: 0 }}>
-      {/* 折叠三角 ▲▼ */}
-      <div role="button" aria-expanded={expanded} tabIndex={0} onClick={...} onKeyDown={...}>
-        <Tooltip title="会话级 tool+path 免审白名单...">
-          <span ...>信任({tools.length})</span>
-        </Tooltip>
-        <span ...>{expanded ? '▲' : '▼'}</span>
-      </div>
-      {expanded && hasTools && (
-        <div role="list" style={{ maxHeight: 70, overflow: 'auto', paddingTop: Spacing.XS }}>
-          {tools.map((t) => (
-            <div key={`${t.toolName}:${t.path ?? ''}`} role="listitem" ...>
-              <span>{t.toolName} › {t.path ?? '任意'}</span>
-              <span onClick={...}>×</span>
-            </div>
-          ))}
-        </div>
-      )}
-    </div>
+    <div style={{ padding: 0 }}>
+      <div
+        ref={triggerRef}
+        role="button"
+        aria-expanded={drawerOpen}
+        aria-label="会话信任清单"
+        tabIndex={0}
+        onClick={openDrawer}
+        onKeyDown={(e) => {
+          if (e.key === 'Enter' || e.key === ' ') {
+            e.preventDefault();
+            openDrawer();
+          }
+        }}
+        style={{
+          cursor: 'pointer',
+          color: Colors.TEXT.PRIMARY,
+          fontWeight: FontWeight.MEDIUM,
+          fontSize: FontSize.SECONDARY,
+        }}
+      >
+        <Tooltip title="会话级 tool+path 免审白名单：勾信任后同会话同工具、目标路径及其子目录免弹框，危险操作仍拦截，可×撤销">
+          <span>信任({tools.length})</span>
+        </Tooltip>
+      </div>
+      {/* Drawer 侧滑面板: 第一行高度恒 28px 不跳动(P1-10) */}
+      <Drawer
+        placement="right"
+        open={drawerOpen}
+        onClose={closeDrawer}
+        title="会话信任清单"
+        width="min(360px, 80vw)" // v3.7 定案
+      >
+        {tools.length === 0 ? (
+          <Empty description="暂无信任工具" />
+        ) : (
+          <Table
+            dataSource={tools}
+            size="small"
+            rowKey={(t) => `${t.toolName}|${t.path}`}
+            pagination={false}
+          >
+            <Table.Column
+              title="撤销" // 操作在前、对象在后(3.5, Tab 顺序=视觉顺序)
+              width={64}
+              render={(_, t: TrustedTool) => (
+                <Button
+                  type="text"
+                  size="small"
+                  icon={<CloseOutlined />}
+                  aria-label={`撤销信任 ${t.toolName}`}
+                  onClick={() => confirmRevoke(t)}
+                />
+              )}
+            />
+            <Table.Column
+              title="对象"
+              render={(_, t: TrustedTool) => `${t.toolName} › ${t.path ?? '全局'}`}
+            />
+          </Table>
+        )}
+      </Drawer>
+    </div>
   );
```

> 保留项：`load` / `omni-trust-changed` 监听 / `trustReqIdRef` 竞态守卫原样不动（零行为变化）；`stopPropagation` 无再需（展开列表已入 Drawer，触发按钮是独立控件）。

---

#### 6.5.5 useTaskInfo.ts 真实差分（P2-14）

`:254`（实时分支 liveMeta 合成处）：

```diff
-    const now = Date.now();
+    // P2-14: 时间源改从末条步骤/帧取(useMemo 幂等), 不再依赖 Date.now()
+    //   顺序: 末条业务 step 时间 → 帧 started 时间; 均无时回退 Date.now()(与现状等价)
+    //   注: 不取"帧 started 时间优先"(文档字面)——旧时间会令新到的 error/truncated 在排序中输给近期过程事件,
+    //   G4 新信号被遮(退化); 且 startTimestamp 为 0 时 `??` 不穿透。末条步骤时间恒 ≥ latestProcessEvent 时间,
+    //   新信号 candidates 前置保序, 与现状 winner 等价 — 小欧-2026-09-09
+    const now =
+      steps[steps.length - 1]?.timestamp || frames.startTimestamp || Date.now();
+    const candidates: LiveMeta[] = [
+      // v4.3 实码校正：新信号 liveError/truncated 前置（与旧排序 winner 等价）
+      ...(liveError ? [{ kind: 'error' as const, text: liveError.text, time: now, requestLevel: liveError.requestLevel }] : []),
+      ...(frames.truncated?.content ? [{ kind: 'truncated' as const, text: frames.truncated.content, time: now, requestLevel: false }] : []),
+      ...(latestProcessEvent ? [latestProcessEvent] : []),
+    ];
```

> 行为验证：`末条步骤时间 || 帧 started 时间 || Date.now()` 以 `||` 穿透 0 值；`latestProcessEvent.time` 取自末条 retrying 步骤，末条时间恒 ≥ 其时间，故新信号前置与旧排序 winner 等价。排序 `candidates.sort(b.time-a.time)` 语义不变；`||` 防 0 陷阱。

---

#### 6.5.6 stepStyles.ts 真实差分（P1-6 WARNING 色值）+ 关联核查

`:134`：

```diff
-  WARNING: '#faad14', // 警告/思考状态 - 橙色(AntD5默认警告色, 收敛)
+  WARNING: '#AD6800', // 警告/思考状态 - 深琥珀(白底对比度约 4.7:1, P1-6 定案 3.7)
```

编辑历史行（追加在 `:2` 之后，不删旧历史）：

```typescript
// 编辑历史: 2026-09-08 小欧 - P1-6: WARNING #faad14→#AD6800(白底对比度≥4.5:1), 全链统一(6 处引用同步增强) — 小欧-2026-09-08
```

**关联影响核查（6 处引用逐条判定，均增强非退化）**：

| 引用文件:行 | 用途 | 改后影响 |
|------------|------|----------|
| `ToolCallLine.tsx:172,190,192` | 警告边框/高亮 | 边框色更深清晰，`WARNING_BG` 不动 |
| `WarningBox.tsx:25,33` | 警告框左边线+文字 | 对比度提升，可读性增强 |
| `StatusIcon.tsx:31` | WarningOutlined 着色 | 深琥珀更醒目 |
| `shapeRenderers.tsx:146,220,306,345,477` | 文件夹/警告提示 | 图标色加深，白底更可见 |
| `TaskInfoBar.tsx:168,188` | G4 警告 + 疑似卡死 | 正文 6.5.3.5 |
| `StaticStatsBlock.tsx` 等 BORDER 引用 | 分隔线 | `BORDER.LIGHT` 不变，无影响 |

> 无白底浅橙反例（改前 `#faad14` 正是对比度不达标项），`Colors.WARNING_BG` 独立不受牵连。

---

#### 6.5.7 `src/utils/time.ts` 增补（formatTimeHMS）与"先查后建"结论

**先查后建结论**：`src/utils/time.ts` 已有 `formatTime`，但输出为「月/日 时:分」（`02/08 14:32`，`:23-33`），**无秒、非固定 HH:MM:SS**，不满足 3.6 时间轴 `HH:MM:SS` 规范 → **在既有模块增补 `formatTimeHMS`**，不新发文件、不覆盖旧契约（禁止 backward）。

`time.ts` 末尾追加：

```typescript
// 编辑历史: 2026-09-08 小欧 - 六章6.5(P2-13/3.6): 新增 formatTimeHMS(固定 HH:MM:SS, 时间轴左列用),
//   复用 parseTimeSafe, 不覆盖 formatTime(既有契约"月/日 时:分") — 小欧-2026-09-08
export const formatTimeHMS = (date: Date | string | number): string => {
  const d = parseTimeSafe(date);
  if (!d) return '-';
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`;
};
```

#### 6.5.8 令牌修订说明（6.5.1 引出，文中一致）

| 文档处 | 原文 | 实码 stepStyles.ts | 定案 |
|--------|------|--------------------|------|
| 设计令牌索引 | `FontSize.CAPTION` = 11 | `CAPTION: 10` | 文档改为 10（3.1.2 G8 字号 10 已一致） |
| 设计令牌索引 | — | `FontSize.SMALL` = 11（新引用） | 3.3/3.5 上下文段标签 11px 引用 `FontSize.SMALL` |

> 实现阶段一切令牌值以 `stepStyles.ts` 实码为准；上述修订纳入 6.5 章节本文，不回改历史版本。

---

## 七、实施计划与步骤（TDD 模式）

### 7.1 TDD 可行性判定

**结论：可以 TDD，采用"主体 TDD + 视觉类后置验证"混合模式。**

| 测试对象 | 属性 | TDD 适配度 | 处理方式 |
|----------|------|-----------|----------|
| 纯函数与映射：`mapStatus` / `EVENT_ICON_MAP` / `BADGE_MAP` / `formatToken` / `formatTimeHMS` | 逻辑纯化 | ✅ 完全适配 | 红→绿→重构（最快循环） |
| 组件渲染与 aria：G6/G8 浮层入口（P0-2/v4.1，v4.2 经 `FloatingEntry` 实现）、上下文 4 态（P1-8）、MetricItem、EllipsisTip、Token 两段式（P1-7） | DOM 可断言 | ✅ 适配 | 红→绿→重构 |
| 交互链路：撤销 Modal.confirm（P0-4）、信任 Drawer 开合与焦点（P1-10）、G6/G8 浮层开合与键盘（v4.1/v4.2 双写修复） | DOM 事件 | ✅ 适配 | 红→绿→重构 |
| 视觉样式：tabular-nums 对齐（P2-16）、对比度（P1-6）、断点切换（P1-9）、Drawer 动画 | 视觉弱断言 | ⚠️ 收益低 | 实现后 E2E/视觉验证锁定，不做红绿循环 |

> 前端现状核查：`frontend/` 已配 Vitest + Playwright，但**无既有测试文件**（`tests/` 仅测量脚本）→ 本轮全部为**新增用例**，无修改既有用例。

### 7.2 分阶段实施步骤（每阶段 = 红→绿→重构）

| 阶段 | 步骤 | 内容（TDD 循环） | 对应设计稿 | 依赖 |
|------|------|------------------|-----------|------|
| 0 底座 | 0.1 | 建 `src/test/setup.ts`（jsdom + jest-dom）、建 `tests/unit/`、`tests/e2e/` 目录，`npm run test` 空套件跑通 | — | — |
| 1 复用层 | 1.1 | `infoMaps.ts`：先写 5 组映射测试（BADGE_MAP 含 cancelled 区分 / CONTEXT_STATE_MAP 4 态 / EVENT_ICON_MAP 4 事件）→ **红** → 建常量+`mapStatus()` → **绿**→重构 | 3.1/3.3/3.4 | 0.1 |
| | 1.2 | `formatToken`（千分位 T 1,234）、`formatTimeHMS`（HH:MM:SS 新增，见 6.5.7）：先写断言 → **红** → 建纯函数 → **绿**（先查 `src/utils/time.ts`） | 3.2/3.3 | 0.1 |
| | 1.3 | `MetricItem`：先写 props 渲染 / tone / 截断态 aria 测试 → **红** → 建组件 → **绿** | 3.2/3.3 | 0.1 |
| | 1.4 | `EllipsisTip`：先写省略 + Tooltip 全文测试 → **红** → 建组件 → **绿** | 3.1(G4)/3.9/3.3 | 0.1 |
| | 1.5 | `FloatingEntry`（v4.2）：先写热区 a11y（role/aria-haspopup/aria-expanded/tabIndex）+ Enter/Space 开合 + click 单次开合（G8 双写修复）+ Esc 关闭/焦点回入口测试 → **红** → 建组件 → **绿** | 3.8/3.9 | 0.1 |
| 2 P0 | 2.1 | P0-1 探针删除：直接删（零逻辑，回归验证） | P0-1 | — |
| | 2.2 | P0-2/v4.1 浮层入口 a11y：先写 G6/G8 `role="button"` / `aria-haspopup="dialog"` / `aria-expanded` / `tabIndex` / Enter+Space 开合测试 → **红** → `FloatingEntry` 实现（v4.2，G6/G8 共用） → **绿** | 3.1/3.8 | 1.4+1.5 |
| | 2.3 | P0-4 撤销确认：点撤销触发 `Modal.confirm`、取消不删、确认才删 → **红** → 实现 → **绿** | 3.5 | 0.1 |
| 3 P1 | 3.1 | P1-5 图标统一：先写"过程事件无 emoji/无纯文本符号、渲染 antd SVG" → **红** → 替换 → **绿** | 3.4 | 1.1 |
| | 3.2 | P1-8/v4.1 上下文入口：先写 4 态 `data-state` + G6 入口 `role="button"`/`aria-haspopup` + 浮层① 开合（hover/click/Esc） → **红** → 接 `CONTEXT_STATE_MAP` + MetricItem + `FloatingEntry`（v4.2） → **绿** | 3.3 | 1.1+1.3+1.5 |
| | 3.3 | P1-7 Token 两段式：先写"本轮/累计分离、千分位、P/C 中灰" → **红** → 接 MetricItem → **绿** | 3.2 | 1.1+1.2 |
| | 3.4 | P1-10 信任 Drawer：先写 `role="button"` + 打开 Drawer + 焦点移入面板 → **红** → 实现 → **绿** | 3.5 | 1.4 |
| | 3.5 | P1-6/P1-11（直接实现）：对比度调色、分隔线归属，不走红绿，E2E/视觉锁定 | P1-6/P1-11 | — |
| 4 P2 | 4.1 | P2-15 badge：先写 cancelled 与 idle 文案/色断言 → **红** → 改 `BADGE_MAP` → **绿** | 3.1 | 1.1 |
| | 4.2 | P2-16 耗时：先写 tabular-nums 类断言 → **红** → 加样式令牌 → **绿** | 3.1 | 0.1 |
| | 4.3 | P2-13 过程事件：先写"唯一 key + 时间 HH:MM:SS + SVG 图标" → **红** → 实现（key=`${e.time}-${e.kind}`）→ **绿** | 3.6/3.7 | 1.1 |
| | 4.4 | P2-12 令牌 / P2-14 timestamp / P2-17 高度 / P2-18 撤销按钮：直接实现（回归验证） | P2-12/14/17/18 | — |
| 5 回归 | 5.1 | `npm run test` 全绿、`npm run check` 零告警 | — | 全 |
| | 5.2 | Playwright 3 条关键链路通过（真实后端） | — | 5.1 |

### 7.3 新增测试用例清单

**A. 纯函数/映射（Vitest，最快红绿）**

| 用例 | 断言要点（红） | 对应设计稿 |
|------|----------------|-----------|
| `mapStatus — ok`（有 overview 与 token） | 返回"正常"标签/数值/`TEXT.PRIMARY`/`data-state="ok"` | 3.3 |
| `mapStatus — summary-only`（仅总结令牌） | 返回收窄数值/`TEXT.TERTIARY`/`data-state="summary-only"` | 3.3 |
| `mapStatus — truncated` | 返回截断态 + WarningOutlined + `Colors.WARNING`/`data-state="truncated"` | 3.3 |
| `mapStatus — empty` | 返回"–"/`TEXT.TERTIARY`/`data-state="empty"` | 3.3 |
| `EVENT_ICON_MAP` | started→PlayCircle / paused→PauseCircle / resumed→PlayCircle / retrying→Reload | 3.4 |
| `BADGE_MAP` | idle→default+待命、cancelled→error/muted 区分（P2-15） | 3.1 |
| `formatToken` | 1234→"T 1,234"、无值→"–" | 3.2 |
| `formatTimeHMS` | 时间→"HH:MM:SS" 固定格式（新增函数，见 6.5.7） | 3.6 |

**B. 组件与交互（Vitest + RTL）**

| 用例 | 断言要点（红） | 对应设计稿 |
|------|----------------|-----------|
| G8 事件入口（v4.1/v4.2） | `role="button"`/`aria-haspopup`/`aria-expanded`/`tabIndex`/Enter+Space 开合事件卡片（P0-2/v4.1，v4.2 经 `FloatingEntry` 实现） | 3.1/3.8 |
| G6 上下文入口（v4.1/v4.2） | `role="button"`/`aria-haspopup`/开合浮层① + `data-state` 4 态（P1-8/v4.1，v4.2 经 `FloatingEntry` 实现） | 3.3/3.8 |
| 浮层卡片 | 打开后焦点入卡、`Esc` 关闭回入口、`stopPropagation` 不冒泡、G8 click 单次开合（v4.2 双写修复，v4.1/3.9） | 3.8/3.9 |
| MetricItem | label/value/tone/截断态 + aria-label | 3.2 |
| EllipsisTip | 文本省略 + Tooltip 全文 + aria | 3.1(G4) |
| Token 两段式 | 本轮/累计分离渲染、千分位、P/C 中灰（P1-7） | 3.2 |
| 过程事件行 | 每行唯一 key、时间 HH:MM:SS、SVG 图标、无 emoji（P2-13） | 3.6 |
| 信任（G7） | `role="button"` + 打开 Drawer + 焦点移入面板（P1-10） | 3.5 |
| 撤销按钮 + Modal.confirm | 点击弹确认、取消不删、确认走 `revoke`（P0-4/P2-18） | 3.5 |
| 耗时数字 | tabular-nums 类、位数不抖动（P2-16） | 3.1 |

**C. E2E（Playwright，真实后端 + 真实 LLM 会话）**

| 用例 | 链路 |
|------|------|
| 会话渲染 | 新建会话 → 基础行 8 信息位渲染（G1 状态 / G2 耗时 / G3 进度 / G4 异常 / G5 Token / G6 上下文入口 / G7 信任 / G8 事件入口） |
| 浮层开合 | hover G6/G8 出卡片、click 钉住、Esc 关闭焦点回入口（v4.1） |
| 信任 Drawer + 撤销 | 打开 G7 → Drawer 侧滑 → 撤销 → Modal.confirm 确认 → 真实撤销语义 |

> E2E 铁律照旧：一次只跑一个 case、真实后端、subprocess.Popen 落盘、禁 Mock（见 AGENTS.md E2E 手册）。

### 7.4 既有测试用例处理（v4.3 实测校正）

实测 `frontend/src/tests/`：**既有 765 项单测（77 文件）**（`src/tests/unit/` + `integration/` + `reality/`；仅 `tests/` 目录为 measurement 脚本）。本轮**新增 41 项，新迁 3 文件**：`taskinfo-error-icon-level.test.tsx`（N15 `⛔`→`StopOutlined`）、`pipeline-audit.test.tsx`（高亮 `#faad14`→`#AD6800`）、`trust-panel.test.tsx`（折叠→Drawer + 撤销×→首列 Button + Modal.confirm 二次确认，新增"取消不删"、Esc 回焦点）——均按"先测后改"迁移（先红→后绿），禁止先改断言再实现。`frontend/src/tests/` 处于 `.gitignore`，新增测试本地运行不入库（与既有 77 文件同规）。

### 7.5 测试命令

| 场景 | 命令（workdir=`frontend/`） |
|------|------------------------------|
| 全量单测 | `npm run test` |
| 跑单个用例 | `npm run test -- --run <name>` |
| TDD 迭代 | `npm run test:watch` |
| 覆盖率 | `npm run test:coverage` |
| E2E | `npm run test:e2e` |
| 提交前检查 | `npm run check` |

### 7.6 验收标准（Definition of Done）

1. 阶段 1~4 新增用例全部转绿，无 `skip/skip-suite`
2. 阶段 5.2 三条 E2E 链路通过（真实后端）
3. `npm run check` 零告警
4. 第六章 6.5 复用清单落地（真实差分全量一份不落）：无重复实现，时间函数先查 `src/utils/` 后建
5. 3.4 图标残留检查通过：emoji / 纯文本符号（▶ ⏸ ↻）清零
6. 行数不退化、不做 backward 兼容（新旧状态机不并存）

---

**编写人：小欧**
**编写时间：2026-09-08 19:57:56**
**去重合并人：小欧**
**去重合并时间：2026-09-08 23:47:47**
**v4.1 更新时间：2026-09-09 09:01:58**
**v4.2 更新时间：2026-09-09 09:32:53**
**v4.3 更新时间：2026-09-09 10:44:31**
**文档版本：v4.3**