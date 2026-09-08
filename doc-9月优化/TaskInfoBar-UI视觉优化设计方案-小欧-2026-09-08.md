# TaskInfoBar UI视觉优化设计方案

**编写人：小欧**
**编写时间：2026-09-08 19:57:56**
**版本：v1.0**

---

## 版本历史

| 版本 | 时间 | 修改简介 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-09-08 19:57:56 | 初版：基于全量源码精读，发现 18 项问题，分 P0/P1/P2 三级 | 小欧 |
| v2.0 | 2026-09-08 20:00:00 | 新增第二章"现状与改进对比（线框图）"：含 2.1 现状问题图 + 2.2 改进后设计稿（A-G 七图）；章节重排（原三~七章顺延为四~七章），优化设计基础前置 | 小欧 |

---

## 一、文档目的

本文档基于对 TaskInfoBar 及其关联组件（TrustPanel、useTaskInfo、SessionLayout、stepStyles.ts、sse.ts 等）的**全量源码精读**，系统性审查 UI 视觉呈现、交互体验、无障碍、代码规范四个维度，发现问题 18 项，并给出具体可落地的改进方案。

---

## 二、现状与改进对比（线框图）

### 2.1 现状问题图（改进前）

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  ● 执行中  耗时 12s  步骤 3 / 轮次 2  [🔁 正在重试] · 疑似卡死   │  ← 左组：emoji+组件图标混用
│                           ·                                         │  ← 中组：全灰，P/C藏tooltip
│  本轮 T1234 (P890/C344) · 任务累计 T5678 (P3456/C2222)             │  ← 同字同色难扫视
│                    上下文 2048tok 🔴                                │  ← 🔴与执行错误撞色
│                                                    信任(2) ▼       │  ← 右组：TrustPanel内嵌撑高
├─────────────────────────────────────────────────────────────────────┤
│ ▶️ 任务已开始 14:32:01                                              │  ← 过程事件：时间+文本同色
│ 🔁 正在重试 14:32:15                                                │     无 tabular-nums
│ ⏸️ 任务已暂停 14:32:20                                              │     key={i}
└─────────────────────────────────────────────────────────────────────┘
         ↑ 无折叠箭头/提示，整行cursor:pointer但用户不知道能点
         ↑ 无 role/tabIndex/aria，键盘用户完全无法操作
         ↑ TrustPanel撤销×无确认，误触即丢失
```

**现状核心问题汇总**：
- **图标混用**：Badge dot + emoji(🔁⛔⚠🔴▶️⏸️) + antd icon(CloseCircleFilled) 三套共存
- **信息平铺**：全 12px 同色，扫描 6 个元素才能找到重点
- **折叠不可发现**：无箭头/图标，仅靠 cursor:pointer 暗示
- **无障碍缺失**：外层折叠无 role/tabIndex/aria-expanded
- **生产残留**：console.log 调试探针未删除
- **TrustPanel 撤销无确认**：误触即丢失信任配置

---

### 2.2 改进后设计稿

#### A. 第一行：核心信息带（一行 6 组，优先级从左到右递减）

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  [▾] ● 执行中   12s   3步·2轮   ↻ 重试中           信任(2) [▸]   │
│                                                                      │
│  G0折叠  G1状态  G2耗时  G3进度    G4异常             G5操作         │
└──────────────────────────────────────────────────────────────────────┘
         ↑ 6组信息，优先级从左到右递减，每组有明确视觉层级
```

**各组设计规范**：

| 组 | 内容 | 字号 | 字重 | 色值 Token | 说明 |
|---|---|---|---|---|---|
| G0 折叠 | `▾` 箭头 | 10 | 400 | TERTIARY | 折叠 affordance，视觉锚点 |
| G1 状态 | Badge + 文字 | 12 | 500 | PRIMARY | antd Badge dot，加粗文字 |
| G2 耗时 | `12s` | 12 | 600 | PRIMARY | **tabular-nums** 等宽，加粗最醒目 |
| G3 进度 | `3步·2轮` | 12 | 400 | SECONDARY | 辅助信息，中灰 |
| G4 异常 | 图标+文字 | 12 | 500 | 见图标映射 | **统一 antd icon**，去掉 emoji |
| G5 操作 | 信任+折叠 | 12 | 400 | PRIMARY | TrustPanel 内嵌，绝对定位浮层 |

**G4 异常位图标统一方案**（去掉 emoji，全用 antd icon）：

| 场景 | 现状 | 改进 | antd icon | 理由 |
|------|------|------|-----------|------|
| 重试中 | `🔁` emoji | spin 动画 | `<SyncOutlined spin />` | 动画传达"进行中"，比静态 emoji 强 |
| 请求级错误 | `⛔` emoji | 灰色静态 | `<StopOutlined />` | 后端业务错误，非用户操作失败 |
| 执行级错误 | `<CloseCircleFilled/>` 红 | 不变 | `<CloseCircleFilled />` | 已是 antd icon，正确 |
| 截断警告 | `⚠` + `🔴` | 去🔴 | `<WarningOutlined />` | **去掉🔴**，与执行错误区分 |

**折叠 affordance（关键改动）**：

```
现状：整行 cursor:pointer，无任何视觉提示
改进：G0 区域加 [▾] 小三角（10px，TERTIARY色），点击响应折叠
      整行仍可点击（扩大热区），但三角是视觉锚点
      补 role="button" + aria-expanded + tabIndex + onKeyDown
```

---

#### B. Token 数值行：分层显示（现状最大问题）

**现状**（信息平铺，无层级）：
```
本轮 T1234 (P890/C344) · 任务累计 T5678 (P3456/C2222) · 上下文 2048tok 🔴
↑ ↑ ↑ ↑ ↑ ↑ 全12px全灰，扫描6个元素才能找到重点
```

**改进后**（主次分明，标签+数值两段式）：
```
本轮   T 1,234   累计   T 5,678
标签  数值      标签  数值
────  ────      ────  ────
灰    加粗      灰    加粗
↑ 3个层级：标签(灰)→数值(加粗)→P/C分项(中灰)，扫一眼抓到数值
```
> 「上下文」不在此行定义，独立成单元格见 2.2-H「上下文段」——因上下文后续将单独优化，故提前独立预留。

**Token 数值行规范**（本轮/累计）：

| 元素 | 字号 | 字重 | 色值 | 说明 |
|------|------|------|------|------|
| 标签"本轮/累计" | 11 | 400 | TERTIARY | 小字灰色，不抢 |
| 数值 T 总数 | 12 | 600 | PRIMARY | 加粗，最醒目，核心监控值 |
| P/C 数值 | 12 | 500 | SECONDARY | 中灰，辅助信息 |
| 分隔符 `·` | 12 | 400 | BORDER | 极淡，不抢 |

---

#### C. 信任详情：Drawer 侧滑面板 + 撤销按钮首列

**现状**（展开列表撑高第一行）：
```
第一行行高被撑大：
┌────────────────────────────────────────────────────┐
│ ... 信任(2) ▼                                       │  ← 行高被撑到 ~100px
│   shell_exec › /tmp/任意                             │     左/中组视觉跳动
│   read_file › /data/                [×] [×]          │
└────────────────────────────────────────────────────┘
```

**改进**（Drawer 右侧滑出面板，第一行固定高度；撤销按钮放首列）：
```
第一行固定高度 28px：
┌────────────────────────────────────────────────────┐
│ ... 信任(2) [▸]      ← 点击信任计数弹出右侧 Drawer  │
└────────────────────────────────────────────────────┘

  ┌──────────────────────────Drawer──────────────────────────┐
  │                                                         │
  │  会话信任清单                              [关闭 ×]     │
  │                                                         │
  │  首列=撤销   │   对象=tool+path                         │
  │ ┌──────────┬──────────────────────────────────────┐    │
  │ │ [×撤销]  │ shell_exec › /tmp/任意               │    │
  │ ├──────────┼──────────────────────────────────────┤    │
  │ │ [×撤销]  │ read_file › /data/                   │    │
  │ └──────────┴──────────────────────────────────────┘    │
  │                                                         │
  │  空态：暂无信任工具                                      │
  └─────────────────────────────────────────────────────────┘
   ← 撤销按钮在每行首列，后跟「工具名 › 目录」，操作在前、对象在后
```

**改动要点**：
1. **形态**：从"第一行内嵌展开"改为 `Drawer`（右侧滑出），第一行固定高度，无左右组跳动
2. **撤销按钮位置**：移入**每行首列**（最左侧），后跟 `工具名 › 目录`，符合"操作在前、对象在后"的排布
3. 撤销走 `Modal.confirm` 二次确认（杜绝误触，呼应 P0-4）
4. Tab 顺序 = 视觉顺序（先见撤销操作、后见操作对象），无障碍友好

---

#### D. 过程事件行：时间轴 + 分段带（体现时序与关系）

**现状**（平铺行，时间/文本/图标同色，无时序关系）：
```
▶️ 任务已开始 14:32:01      ← emoji + 文本 + 时间，全同色
🔁 正在重试 14:32:15        ← 看不出事件先后、间隔
⏸️ 任务已暂停 14:32:20      ← 无 tabular-nums
```

**改进**（垂直时间线 + 事件分段带，事件从上到下按时间排列）：
```
  事件带(右列)                        时间线(中列)      时间(左列)

  ▶ 任务已开始              │ ●                 14:32:01
                            │ │
  ↻ 正在重试                │ │ ●               14:32:15
                            │ │ │
  ⏸ 任务已暂停              │ │ ●               14:32:20
                            └─┴─┴
                              ↑ 竖线段长≈时间间隔，一眼看出疏密
```

**三列布局规范**：

| 列 | 内容 | 字号 | 字重 | 色值 | 说明 |
|----|------|------|------|------|------|
| 左列 | 时间 `14:32:01` | 11 | 400 | SECONDARY | **tabular-nums** 等宽，右侧对齐 |
| 中列 | 时间线：`│` 竖线 + `●` 节点 | 10 | 400 | BORDER | 节点按时间顺序，竖线段长≈间隔 |
| 右列 | 事件图标 + 文本 | 12 | 400 | TERTIARY | 图标 `▶ ⏸ ↻`（去 emoji）|

**时序与关系表达**：
1. **从上到下**按时间顺序排列（最新在顶，遵循现状 reversed）
2. **时间线竖线**把各事件串起来──竖线段物理长度与时间间隔成正比，间隔大则段长、间隔小则段短，肉眼可读疏密
3. 每个事件都有**节点圆点**闭环，强化"这是一条连续的时间序列"
4. `role="log"` + `aria-live="polite"`，新事件实时播报

---

#### E. 信息密度对比（改进前后）

```
现状（信息平铺，无层级）：
  本轮 T1234 (P890/C344) · 任务累计 T5678 (P3456/C2222) · 上下文 2048tok 🔴
  ↑ ↑ ↑ ↑ ↑ ↑ 全12px全灰，扫描6个元素才能找到重点

改进后（主次分明）：
  本轮  T 1,234  P 890/C 344   │  累计  T 5,678   │  上下文  2,048 tok
  ──── 灰 ──── 加粗 ─── 中灰 ──   ──── 灰 ─── 加粗 ──   ──── 灰 ──── 中灰 ──
  ↑ 3个层级：标签→总数→分项，扫一眼抓到 T 值
```

---

#### F. 颜色规范总结（改进后全局一张表）

| 用途 | 色值 Token | 字重 | 用在哪 |
|------|-----------|------|--------|
| 核心数值 | `Colors.TEXT.PRIMARY #595959` | 600 | T 总数、耗时数字、徽标文字 |
| 辅助数值 | `Colors.TEXT.SECONDARY #8c8c8c` | 500 | P/C 值、步骤轮次、时间 |
| 标签/辅助文字 | `Colors.TEXT.TERTIARY #999` | 400 | 标签、事件文本 |
| 正常进行中 | `Colors.PRIMARY #1677ff` | - | Badge running dot |
| 错误（执行级） | `Colors.ERROR #ff4d4f` | - | CloseCircleFilled 红圆 |
| 警告（重试/截断） | `Colors.WARNING #faad14` | 500 | SyncOutlined / WarningOutlined |
| 业务错误（请求级） | `Colors.TEXT.SECONDARY #8c8c8c` | - | StopOutlined 灰色 |
| 分隔线 | `Colors.BORDER.LIGHT #f0f0f0` | - | 顶部分隔 |

---

#### G. 无障碍补全清单

| 位置 | 现状 | 改进 |
|------|------|------|
| 整行折叠 | 无 role/tabIndex/aria | `role="button"` + `aria-expanded` + `tabIndex={0}` + `onKeyDown` |
| 折叠热区 | 整行 onClick（与文本选中冲突） | 三角区域 onClick + stopPropagation，整行保留但不响应文本区 |
| TrustPanel 折叠 | ✅ 已有 role/aria/keyboard | 不变 |
| TrustPanel 撤销按钮 | 纯 span × | 改 antd Button + aria-label |
| 过程事件列表 | 无 role | `role="log"` + `aria-live="polite"` |

---

#### H. 上下文段（独立单元，为后续优化预留）

> **独立原则**：上下文段不再依附于 Token 数值行（B），单独成一格，赋予独立序号。
> 原因：上下文这个位置**后续还会单独优化**（如上下文摘要、注入比例、截断策略等扩展），
> 现在彻底独立，为将来新增优化项预留明确挂载点，避免届时在 token 行里叠床架屋。

**现状**（标签与数值混成一串，且与执行错误撞色）：
```
上下文 2048tok 🔴      ← "上下文"像句子不像标签；🔴与执行级错误撞色
```

**改进后**（标签+数值两段式，与 token 行同构但独立定义）：
```
上下文   2,048 tok
标签    数值
────    ────
灰      加粗(截断时 WARNING + WarningOutlined)
```

**上下文标签/数值独立定义**：

| 元素 | 字号 | 字重 | 色值 | 说明 |
|------|------|------|------|------|
| 标签"上下文" | 11 | 400 | TERTIARY | 小字灰色，与"本轮/累计"同级但独立定义 |
| 数值 `{n} tok` | 12 | 600 | PRIMARY | 加粗；截断时改 WARNING |
| 截断标记 | 12 | 500 | WARNING | `<WarningOutlined />` 表示"被截断"非"出错" |

**上下文段文案状态机**（4种→统一两段式）：

| 状态 | 标签 | 数值 | 数值色值 | 图标 |
|------|------|------|-----------|------|
| 有 overview + 有 token 数 | `上下文` | `{n} tok` | PRIMARY | 无 |
| 有 overview + 无 token 数 | `上下文` | `有摘要` | TERTIARY | 无 |
| 截断 | `上下文` | `{n} tok` | WARNING | WarningOutlined |
| 无数据 | `上下文` | `–` | TERTIARY | 无 |

**未来优化预留位**（本单元格扩展挂载点，待定案后填充）：
- 上下文摘要（summary 全文/展开）
- 注入比例 injected_ratio
- 消息数 message_count
- 截断策略/预警分级

---

## 三、审查范围

| 文件 | 行数 | 审查重点 |
|------|------|----------|
| `src/features/chat/components/taskinfo/TaskInfoBar.tsx` | 298 | 组件结构、样式、交互、渲染逻辑 |
| `src/features/chat/components/config/TrustPanel.tsx` | 183 | 信任面板、折叠、无障碍 |
| `src/features/chat/hooks/useTaskInfo.ts` | 304 | 数据派生逻辑、useMemo 依赖 |
| `src/utils/stepStyles.ts` | 230 | 设计令牌（Colors/FontSize/Spacing） |
| `src/theme/tokens.ts` | 29 | 会话页 UI token |
| `src/types/sse.ts` | 195 | SSE 类型定义、LiveError |
| `src/features/chat/components/layout/SessionLayout.tsx` | 162 | 布局骨架、gap/分隔 |
| `src/features/chat/components/layout/SessionPanelRegistry.ts` | 43 | 面板注册、持久化机制 |
| `src/features/chat/hooks/useChatPanels.tsx` | 340 | Props 透传链路 |
| `src/types/execution.ts` | 167 | ExecutionStep 类型 |

---

## 四、问题清单（18项，P0/P1/P2 分级）

### 4.1 P0 级问题（必须改，影响功能/生产安全）

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

**问题**：
1. 注释自称"临时"、"真机复现确认后删除"，但至今未删
2. 每次挂载/toggle 都刷控制台，污染开发环境日志
3. `Math.random().toString(36).slice(2)` 的 pid 语义无意义
4. `eslint-disable-next-line` 旁路了 hooks 规则检查

**影响**：生产包体积浪费；控制台噪音干扰调试；eslint 规则被旁路

**改进**：整段删除（含 useEffect 挂针 + onClick console.log + 编辑历史行 24-25）

---

#### P0-2：整行折叠零可发现性 + 无障碍缺失

**位置**：`TaskInfoBar.tsx:125-143`

**现状代码**：
```typescript
<div
  style={{
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    cursor: 'pointer',   // ← 仅靠 cursor 暗示
    flexWrap: 'nowrap',
  }}
  onClick={(e) => {
    // ... console.log ...
    setCollapsed((v) => !v);  // ← 整行点击 toggle
  }}
>
```

**问题**：
1. **无折叠 affordance**：无箭头/图标/"收起"文字，用户无法发现此行可点击
2. **无无障碍支持**：无 `role="button"`、无 `tabIndex`、无 `aria-expanded`、无 `onKeyDown(Enter/Space)`
3. **与 TrustPanel 双标**：TrustPanel（:92-106）有完整的 role/aria-expanded/tabIndex/onKeyDown，而外层折叠行无任何无障碍
4. **文本选中冲突**：点击选中的 token 数字会触发折叠

**对比 TrustPanel 的无障碍实现**（TrustPanel.tsx:92-106）：
```typescript
<div
  role="button"
  aria-expanded={expanded}
  tabIndex={0}
  onClick={(e) => { e.stopPropagation(); setExpanded((v) => !v); }}
  onKeyDown={(e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      e.stopPropagation();
      setExpanded((v) => !v);
    }
  }}
>
```

**改进**：
1. 外层 div 补 `role="button"` + `aria-expanded={collapsed}` + `tabIndex={0}` + `onKeyDown`
2. G5 区域（右组）加一个小三角 `[▾]`（10px，TERTIARY 色）作为折叠视觉锚点
3. 整行保留 onClick（扩大热区），但三角区域 stopPropagation

---

#### P0-3：collapsed 状态挂载即重置

**位置**：`TaskInfoBar.tsx:73`

**现状代码**：
```typescript
const [collapsed, setCollapsed] = useState(false);  // ← 挂载即 false（展开）
```

**问题**：
1. 组件重挂载（会话切换/panels 重组）即强制展开，用户收起的面板被重置
2. 与 `SessionPanelRegistry` 的 `persistVisible` 机制不一致——该机制支持 localStorage 持久化面板可见性，但 TaskInfoBar 的折叠状态未接入

**改进**：
- 方案 A（推荐）：collapsed 状态接入 `localStorage`，key = `session_panel_collapsed:taskinfo.bar`
- 方案 B：collapsed 状态上提到 `useChatPanels`，通过 props 传入

---

#### P0-4：撤销信任操作无确认提示

**位置**：`TrustPanel.tsx:74-82`

**现状代码**：
```typescript
const revoke = async (toolName: string, path: string | null) => {
  if (!sessionId) return;
  try {
    await trustApi.revokeTrust(sessionId, toolName, path);
    await load();
  } catch {
    /* 捕获异常防unhandledrejection上浮 */
  }
};
```

**问题**：点击 `×` 直接撤销信任，无任何确认。用户误触即丢失信任配置，且无法撤销（信任写入需 HITL 弹窗确认，撤销却一键生效）。

**改进**：revoke 前加 `window.confirm('确认撤销信任？撤销后该工具将重新弹框确认。')` 或 antd `Modal.confirm`

---

### 4.2 P1 级问题（视觉层级/布局/一致性）

#### P1-5：图标语言三套混用

**位置**：`TaskInfoBar.tsx:152,166-186,243,283-289`

**现状**：同一组件内混用三种图标体系：

| 位置 | 图标类型 | 示例 |
|------|----------|------|
| :152 | antd Badge dot | `<Badge status="processing" text="执行中" />` |
| :171-183 | emoji 文本 | `🔁` `⛔` `⚠` |
| :179 | antd 组件图标 | `<CloseCircleFilled style={{ fontSize: 12, color: Colors.ERROR }} />` |
| :243 | emoji 红圆 | `🔴` |
| :285-288 | emoji 事件图标 | `▶️` `⏸️` `▶️` `🔁` |

**问题**：
1. emoji 随平台/浏览器字体渲染不一致，基线在 12px 行内漂移
2. `🔴`（上下文截断，:243）与 `CloseCircleFilled` 红圆（执行错误，:179）语义撞色
3. 同一行内 Badge dot + emoji + antd icon 三套视觉语言，不统一

**改进**：统一用 antd icon：

| 场景 | 现状 | 改进 | antd icon |
|------|------|------|-----------|
| 重试中 | `🔁` | spin 动画 | `<SyncOutlined spin />` |
| 请求级错误 | `⛔` | 灰色静态 | `<StopOutlined />` |
| 执行级错误 | `<CloseCircleFilled/>` | 不变 | `<CloseCircleFilled />` |
| 截断警告 | `⚠` + `🔴` | 去🔴 | `<WarningOutlined />` |
| 过程事件 | `▶️` `⏸️` `🔁` | 灰色小图标 | `▶` `⏸` `▶` `↻`（纯文本符号） |

---

#### P1-6：位4 liveMeta 警告色对比度不足

**位置**：`TaskInfoBar.tsx:167-168`

**现状代码**：
```typescript
<span style={{ fontSize: 12, color: Colors.WARNING, marginLeft: 2 }}>
```

**问题**：
- `Colors.WARNING = #faad14`，12px 文本落透明背景，白底对比度约 2.1:1
- WCAG AA 标准要求 4.5:1（小文本），当前远不达标
- 长错误文本（如 `info.liveMeta.text`）无 `maxWidth/ellipsis`，会把左组撑宽

**改进**：
1. error 场景改 `Colors.ERROR (#ff4d4f)`（对比度 4.6:1，达标）
2. retrying/truncated 保留 WARNING 但加粗 `fontWeight: 500`
3. 文本加 `maxWidth: 200px` + `overflow: hidden` + `textOverflow: ellipsis` + Tooltip 全文

---

#### P1-7：Token 数值行同字同色、层级缺失（本轮/累计）

**位置**：`TaskInfoBar.tsx:193-257`

**现状**：
```
本轮 T1234 (P890/C344) · 任务累计 T5678 (P3456/C2222) · 上下文 2048tok
```

**问题**：
1. 全部 `fontSize: 12` + 同色（本轮 PRIMARY，累计/上下文 TERTIARY），扫描 6 个元素才能找到重点
2. P/C 数值藏在 Tooltip 内，最有用的分项信息反而要点开才见
3. `·` 分隔符与 TERTIARY 同色，视觉分隔弱

**改进**：本轮/累计两段统一"标签+数值"两段式，主次分明

```
本轮   T 1,234   累计   T 5,678
标签  数值      标签  数值
灰    加粗      灰    加粗(截断时WARNING+WarningOutlined)
```

| 元素 | 字号 | 字重 | 色值 |
|------|------|------|------|
| 标签"本轮/累计" | 11 | 400 | TERTIARY |
| 数值 T 总数 | 12 | 600 | PRIMARY |
| P/C 数值 | 12 | 500 | SECONDARY |
| 分隔符 `·` | 12 | 400 | BORDER |

> 「上下文」段已独立成番号 P1-8（设计见第二章 2.2-H），不再于此定义，为后续单独优化预留。

---

#### P1-8：上下文段（独立位置番号）：四种文案格式 + 标签/数值拆分

**独立原则**：上下文段不再依附于 Token 数值行（P1-7），独立占番号 P1-8。
原因：上下文这个位置**后续还会单独优化**（如上下文摘要、注入比例、截断策略等扩展），
现在彻底独立，为将来新增优化项预留明确挂载点，避免届时在 token 行里叠床架屋。

**位置**：`TaskInfoBar.tsx:231-256`

**现状**：四种分支产生四种不同文案：
```typescript
// 分支1: typeof overview === 'string'
"上下文摘要"

// 分支2: overview 对象
"上下文 {estimated_tokens}tok{truncated ? ' 🔴' : ''}"

// 分支3: frames.contextSummary 存在
"上下文摘要"

// 分支4: fallback
"上下文 {0}tok"
```

**问题**：
1. 同一位置四种长相，用户无法形成稳定预期
2. `"上下文 0tok"` 像坏数据而非空态（0tok 是真实的，但显示方式让人怀疑是 bug）
3. `"上下文摘要"` 无信息量（token 数？是否截断？）
4. **上下文段标签与数值混成一串**（"上下文 2048tok"），与"本轮/累计"的"标签+数值"结构不一致，扫视时"上下文"像句子而非标签
5. `🔴` 与执行级错误（CloseCircleFilled 红圆）语义撞色

**改进**：统一为一种"标签+数值"两段式格式，标签与数值独立

```
上下文   2,048 tok
标签    数值
────    ────
灰      加粗(截断时 WARNING + WarningOutlined)
```

**上下文标签/数值独立定义**：

| 元素 | 字号 | 字重 | 色值 | 说明 |
|------|------|------|------|------|
| 标签"上下文" | 11 | 400 | TERTIARY | 小字灰色，与"本轮/累计"同级但独立定义 |
| 数值 `{n} tok` | 12 | 600 | PRIMARY | 加粗；截断时改 WARNING |
| 截断标记 | 12 | 500 | WARNING | `<WarningOutlined />` 表示"被截断"非"出错" |

**上下文段文案状态机**（4种→统一两段式）：

| 状态 | 标签 | 数值 | 数值色值 | 图标 |
|------|------|------|-----------|------|
| 有 overview + 有 token 数 | `上下文` | `{n} tok` | PRIMARY | 无 |
| 有 overview + 无 token 数 | `上下文` | `有摘要` | TERTIARY | 无 |
| 截断 | `上下文` | `{n} tok` | WARNING | WarningOutlined |
| 无数据 | `上下文` | `–` | TERTIARY | 无 |

**未来优化预留位**（本单元格扩展挂载点，待定案后填充）：
- 上下文摘要（summary 全文/展开）
- 注入比例 injected_ratio
- 消息数 message_count
- 截断策略/预警分级

---

#### P1-9：窄屏必溢出

**位置**：`TaskInfoBar.tsx:125-131`

**现状代码**：
```typescript
<div
  style={{
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    cursor: 'pointer',
    flexWrap: 'nowrap',  // ← 禁止换行
  }}
>
```

**问题**：
1. `flexWrap: nowrap` + 左组 `flexShrink: 0`（:149）= 窗口收窄时中组被压缩
2. 中组无 `minWidth: 0`（:199 虽有但被 `justifyContent: center` 抵消）
3. 窄屏下左组状态+耗时+步骤+位4 强制占位，中组 token 数被挤成 0 宽度

**改进**：
1. 外层 `flexWrap: 'wrap'`（允许换行）
2. 中组加 `minWidth: 0` + `overflow: hidden` + `whiteSpace: nowrap` + `textOverflow: ellipsis`
3. `< 900px` 时累计段进 Tooltip 或隐藏

---

#### P1-10：TrustPanel 展开撑高第一行

**位置**：`TrustPanel.tsx:134-138`

**现状代码**：
```typescript
{expanded && hasTools && (
  <div
    role="list"
    style={{ maxHeight: 70, overflow: 'auto', paddingTop: Spacing.XS }}
  >
```

**问题**：展开列表渲染在第一行右组内，maxHeight 70px 撑高行高，左/中组视觉跳动。

**改进**（定案：Drawer 侧滑面板）：
- 展开列表改为 `Drawer`（右侧滑出），第一行固定高度，永不撑高
- 撤销按钮移入每行**首列**，后跟 `工具名 › 目录`（操作在前、对象在后）
- 撤销走 `Modal.confirm` 二次确认（呼应 P0-4）
- 空态在 Drawer 内显示"暂无信任工具"

---

#### P1-11：与 input 区分隔缺失

**位置**：`TaskInfoBar.tsx:117`

**现状代码**：
```typescript
borderTop: `1px solid ${Colors.BORDER.LIGHT}`,  // ← 仅顶部
padding: '8px 0 0',  // ← 无底部 padding
```

**问题**：本条只有顶部 `borderTop`，底部靠 `SessionLayout.tsx:72` 的 `gap: 8` 悬空，视觉上像"浮条"而非"状态栏"。input 区也没有顶部 border，两块之间靠 gap 分隔，视觉界限模糊。

**改进**：
- 方案 A：本条加 `borderBottom` + `paddingBottom: 8` 收口
- 方案 B（更干净）：本条去掉 `borderTop`，改为 input 区顶部统一加 `borderTop`，让分隔线归属"输入区上沿"

---

### 4.3 P2 级问题（细节打磨）

#### P2-12：设计令牌旁路

**位置**：`TaskInfoBar.tsx:43`

**现状代码**：
```typescript
import { Colors } from '@/utils/stepStyles';  // ← 只 import Colors
```

**问题**：TaskInfoBar 只用 `Colors`，字号/间距/圆角全硬码：
- `fontSize: 12` 出现 9 次（:155,162,168,188,207,222,233,241,253）
- `fontWeight: 500` 出现 2 次（:157,209）
- `gap: 12` / `gap: 8` 各 1 次（:129,148）
- `padding: '8px 0 0'`（:118）
- `maxHeight: 72`（:275）
- `marginLeft: 2`（:168）

而 TrustPanel 全用 `FontSize.SECONDARY` / `Spacing.XS` 等令牌。

**改进**：TaskInfoBar 补 import `FontSize, Spacing, Radius`，硬码数字替换为令牌引用

---

#### P2-13：过程事件行可读性差

**位置**：`TaskInfoBar.tsx:283-291`

**现状代码**：
```typescript
{info.processEvents.map((e, i) => (
  <div key={i} style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
    {e.kind === 'started' && '▶️ '}
    {e.kind === 'paused' && '⏸️ '}
    {e.kind === 'resumed' && '▶️ '}
    {e.kind === 'retrying' && '🔁 '}
    {e.text} {new Date(e.time).toLocaleTimeString()}
  </div>
))}
```

**问题**：
1. 时间与事件文本同色 TERTIARY，扫视难区分
2. `toLocaleTimeString()` 无 `tabular-nums`，秒表跳动时数字抖动
3. `key={i}` 索引 key，列表重排时 React 复用错误 DOM
4. emoji `▶️` 含变体选择器 U+FE0F，渲染宽度不稳定

**改进**：
1. 时间改 `fontSize: 11` + `color: SECONDARY` + `fontVariantNumeric: 'tabular-nums'`
2. 事件文本保持 TERTIARY
3. key 改为 `${e.time}-${e.kind}`（唯一性足够）
4. emoji 改纯文本符号 `▶` `⏸` `↻`

---

#### P2-14：useTaskInfo useMemo 内 Date.now()

**位置**：`useTaskInfo.ts:254`

**现状代码**：
```typescript
const now = Date.now();
const candidates: LiveMeta[] = [
  ...(liveError
    ? [{
        kind: 'error' as const,
        text: liveError.text,
        time: now,  // ← Date.now() 在 useMemo 内
      }]
    : []),
  ...(frames.truncated?.content
    ? [{
        kind: 'truncated' as const,
        text: frames.truncated.content,
        time: now,
      }]
    : []),
];
```

**问题**：
- `Date.now()` 在 useMemo 内，每次依赖变化（steps/frames/receiving/detail/liveError）都会产生新时间戳
- `candidates.sort((a, b) => b.time - a.time)[0]` 的排序在 `time === now` 时退化为插入顺序
- 但此时间戳仅用于"新覆盖旧"的排序，不影响显示——所以功能正确，只是语义不清晰

**改进**：`now` 改为从 `frames.startTimestamp` 或 `steps[steps.length-1].timestamp` 取，不依赖 `Date.now()`

---

#### P2-15：Badge idle 态视觉过弱

**位置**：`TaskInfoBar.tsx:56-63`

**现状代码**：
```typescript
const BADGE_MAP = {
  idle: { status: 'default' as const, text: '待命' },
  // ...
};
```

**问题**：`status: 'default'` 在 antd Badge 中渲染为灰色圆点 + 灰色文字，与 `cancelled` 相同。用户无法区分"空闲等待"和"已取消"。

**改进**：
- idle 改 `status: 'default'` + 文字 `待命`（保持）
- cancelled 改 `status: 'error'` 灰色 + 文字 `已取消`（或用自定义 dot 颜色区分）

---

#### P2-16：耗时显示无单位对齐

**位置**：`TaskInfoBar.tsx:160`

**现状代码**：
```typescript
耗时 {Math.round(shownElapsed)}s
```

**问题**：`Math.round(shownElapsed)` 是动态宽度数字（1s / 12s / 120s / 3600s），导致"耗时"文字随数字宽度跳动。

**改进**：数字部分用 `fontVariantNumeric: 'tabular-nums'` 等宽数字，或固定宽度 `minWidth: 32px` + `textAlign: right`

---

#### P2-17：过程事件区 maxHeight 固定

**位置**：`TaskInfoBar.tsx:275`

**现状代码**：
```typescript
maxHeight: 72,  // ← 固定 72px（约 3-4 行事件）
```

**问题**：72px 约容纳 3-4 行事件（每行 ~18px），超过后滚动。但滚动条（`scrollbarWidth: thin`）在 Windows 下仍占 ~8px，实际可视区域更小。

**改进**：
1. `maxHeight` 改为 `80px`（4 行整，含底部 padding）
2. 或改为"最新 3 条 + 展开全部"模式

---

#### P2-18：TrustPanel 撤销按钮无障碍

**位置**：`TrustPanel.tsx:158-174`

**现状代码**：
```typescript
<span
  onClick={(e) => {
    e.stopPropagation();
    void revoke(t.toolName, t.path);
  }}
  style={{
    fontSize: 14,
    color: Colors.TEXT.PRIMARY,
    cursor: 'pointer',
    // ...
  }}
  title="撤销信任"
>
  ×
</span>
```

**问题**：
1. `×` 是文本符号，非语义化按钮
2. 无 `role="button"` / `tabIndex` / `onKeyDown`
3. 无 `aria-label`（`title` 不替代 aria-label）
4. 撤销操作不可逆，应有视觉/交互确认

**改进**：
1. 改为 `<Button type="text" size="small" icon={<CloseOutlined />} onClick={...} />`
2. antd Button 自带 role/keyboard/aria 支持
3. 加 `aria-label="撤销信任 {toolName}"`

---

## 五、改进设计稿（详细规范）

### 5.1 第一行布局（改进后）

```
┌──────────────────────────────────────────────────────────────────────┐
│  [▾] ● 执行中   12s   3步·2轮   ↻ 重试中           信任(2) [▸]   │
│                                                                      │
│  G0折叠  G1状态  G2耗时  G3进度    G4异常             G5操作         │
└──────────────────────────────────────────────────────────────────────┘
         ↑ 5组信息，优先级从左到右递减
```

| 组 | 内容 | 字号 | 字重 | 色值 Token | 说明 |
|---|---|---|---|---|---|
| G0 折叠 | `▾` 箭头 | 10 | 400 | TERTIARY | 折叠 affordance，可选 |
| G1 状态 | Badge + 文字 | 12 | 500 | PRIMARY | antd Badge dot |
| G2 耗时 | `12s` | 12 | 600 | PRIMARY | **tabular-nums**，等宽 |
| G3 进度 | `3步·2轮` | 12 | 400 | SECONDARY | 辅助信息 |
| G4 异常 | 图标+文字 | 12 | 500 | 见图标映射 | 统一 antd icon |
| G5 操作 | 信任+折叠 | 12 | 400 | PRIMARY | TrustPanel 内嵌 |

---

### 5.2 Token 数值行（改进后）

```
本轮  T 1,234  P 890 / C 344   │  累计  T 5,678   │  上下文  2,048 tok
 ── 标签灰 ── 加粗 ── 中灰 ──      ── 标签灰 ── 加粗      ── 标签灰 ── 中灰 ──
```

| 元素 | 字号 | 字重 | 色值 Token | 说明 |
|---|---|---|---|---|
| 标签"本轮/累计/上下文" | 11 | 400 | TERTIARY | 小字灰色 |
| T 总数 | 12 | 600 | PRIMARY | 加粗，最醒目 |
| P/C 数值 | 12 | 500 | SECONDARY | 中灰，辅助 |
| 分隔符 `·` | 12 | 400 | BORDER | 极淡，不抢 |

---

### 5.3 上下文段文案统一

| 状态 | 文案 | 色值 | 图标 |
|------|------|------|------|
| 有 overview + 有 token 数 | `{n} tok` | SECONDARY | 无 |
| 有 overview + 无 token 数 | `有摘要` | TERTIARY | 无 |
| 截断 | `{n} tok` | WARNING | WarningOutlined |
| 无数据 | `–` | TERTIARY | 无 |

---

### 5.4 图标统一方案

| 场景 | 现状 | 改进 | antd icon / 符号 |
|------|------|------|------------------|
| 重试中 | `🔁` emoji | spin 动画 | `<SyncOutlined spin />` |
| 请求级错误 | `⛔` emoji | 灰色静态 | `<StopOutlined />` |
| 执行级错误 | `<CloseCircleFilled/>` | 不变 | `<CloseCircleFilled />` |
| 截断警告 | `⚠` + `🔴` | 去🔴 | `<WarningOutlined />` |
| 过程-开始 | `▶️` | 纯文本 | `▶` |
| 过程-暂停 | `⏸️` | 纯文本 | `⏸` |
| 过程-恢复 | `▶️` | 纯文本 | `▶` |
| 过程-重试 | `🔁` | 纯文本 | `↻` |

---

### 5.5 颜色规范总结

| 用途 | 色值 Token | 字重 | 用在哪 |
|------|-----------|------|--------|
| 核心数值 | `Colors.TEXT.PRIMARY #595959` | 600 | T 总数、耗时数字、徽标文字 |
| 辅助数值 | `Colors.TEXT.SECONDARY #8c8c8c` | 500 | P/C 值、步骤轮次、时间 |
| 标签/辅助文字 | `Colors.TEXT.TERTIARY #999` | 400 | 标签、事件文本 |
| 正常进行中 | `Colors.PRIMARY #1677ff` | - | Badge running dot |
| 错误（执行级） | `Colors.ERROR #ff4d4f` | - | CloseCircleFilled 红圆 |
| 警告（重试/截断） | `Colors.WARNING #faad14` | 500 | SyncOutlined / WarningOutlined |
| 业务错误（请求级） | `Colors.TEXT.SECONDARY #8c8c8c` | - | StopOutlined 灰色 |
| 分隔线 | `Colors.BORDER.LIGHT #f0f0f0` | - | 顶部分隔 |

---

### 5.6 无障碍补全清单

| 位置 | 现状 | 改进 |
|------|------|------|
| 整行折叠 | 无 role/tabIndex/aria | `role="button"` + `aria-expanded` + `tabIndex={0}` + `onKeyDown` |
| 折叠热区 | 整行 onClick（与文本选中冲突） | 三角区域 onClick + stopPropagation，整行保留但不响应文本区 |
| TrustPanel 折叠 | ✅ 已有 role/aria/keyboard | 不变 |
| TrustPanel 撤销按钮 | 纯 span × | 改 antd Button + aria-label |
| 过程事件列表 | 无 role | `role="log"` + `aria-live="polite"` |

---

## 六、需确认的设计决策

| # | 问题 | 选项 A | 选项 B | 我的建议 |
|---|------|--------|--------|----------|
| D1 | Token 数值 P/C 露出来还是 hover 看？ | 露出来（占空间） | hover 看（紧凑） | **A：露出来**，核心监控信息 |
| D2 | TrustPanel 展开用浮层还是固定在第二行？ | absolute 浮层 | 固定第二行 | **A：浮层**，不撑高第一行 |
| D3 | 过程事件时间用绝对还是相对？ | `14:32:01` | `12秒前` | **A：绝对时间**，无需定时刷新 |
| D4 | collapsed 持久化方案？ | localStorage | 上提 state | **A：localStorage**，简单直接 |

---

## 七、改进优先级排序

| 阶段 | 问题 | 预估工作量 | 说明 |
|------|------|-----------|------|
| 第一阶段 | P0-1 探针删除 | 5 min | 纯删除，零风险 |
| 第一阶段 | P0-2 折叠 affordance + 无障碍 | 30 min | 核心交互修复 |
| 第一阶段 | P0-3 collapsed 持久化 | 15 min | localStorage 接入 |
| 第一阶段 | P0-4 撤销确认 | 5 min | 加 confirm |
| 第二阶段 | P1-5 图标统一 | 30 min | 替换 emoji → antd icon |
| 第二阶段 | P1-6 liveMeta 对比度 | 10 min | 色值调整 |
| 第二阶段 | P1-7 Token 数值层级 | 20 min | 字重/色值调整 |
| 第二阶段 | P1-8 上下文文案统一 | 15 min | 4 种→1 种 |
| 第二阶段 | P1-9 窄屏溢出 | 15 min | flexWrap + min-width |
| 第二阶段 | P1-10 TrustPanel 浮层 | 30 min | absolute 定位 |
| 第二阶段 | P1-11 分隔线归属 | 10 min | border 调整 |
| 第三阶段 | P2-12 令牌替换 | 15 min | 硬码→Tokens |
| 第三阶段 | P2-13 过程事件优化 | 15 min | 时间/图标/key |
| 第三阶段 | P2-14 Date.now() 语义 | 5 min | 改用 timestamp |
| 第三阶段 | P2-15 Badge idle 区分 | 5 min | cancelled 改色 |
| 第三阶段 | P2-16 耗时数字对齐 | 5 min | tabular-nums |
| 第三阶段 | P2-17 事件区高度 | 5 min | 72→80 |
| 第三阶段 | P2-18 撤销按钮无障碍 | 10 min | span→Button |

**总预估：~4 小时（P0 + P1 约 3h，P2 约 1h）**

---

**编写人：小欧**
**编写时间：2026-09-08 19:57:56**
**文档版本：v2.0**
