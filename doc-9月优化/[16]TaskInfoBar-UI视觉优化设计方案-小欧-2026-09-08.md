# TaskInfoBar UI视觉优化设计方案

**编写人：小欧**
**编写时间：2026-09-08 19:57:56**
**版本：v3.6**

---

## 版本历史

| 版本 | 时间 | 修改简介 | 作者 |
|------|------|----------|------|
| v1.0 | 2026-09-08 19:57:56 | 初版：基于全量源码精读，发现 18 项问题，分 P0/P1/P2 三级 | 小欧 |
| v2.0 | 2026-09-08 20:00:00 | 新增第二章"现状与改进对比（线框图）"：含 2.1 现状问题图 + 2.2 改进后设计稿（A-G 七图）；章节重排（原三~七章顺延为四~七章），优化设计基础前置 | 小欧 |
| v3.0 | 2026-09-08 20:36:06 | 全链有机整合北京老陈三点建议：(1) 上下文标签/数值拆分，并**独立成番号 P1-8 / 设计稿 2.2.8 / 5.3**，为后续单独优化预留挂载点；(2) 信任详情改 **Drawer 侧滑面板** + 撤销按钮移入每行首列 + Modal.confirm 二次确认（D2 定案）；(3) 过程事件改**时间轴+分段带**（体现时序与疏密）。线框图 B/C/D/H、问题清单 P1-7/P1-8/P1-10、设计稿 5.2/5.3、决策表 D2/D5、优先级表全链同步 | 小欧 |
| v3.1 | 2026-09-08 20:50:00 | 第一行信息位**独立番号 G0~G7**：G0折叠/G1状态/G2耗时/G3进度/G4异常/**G5 Token数值/G6 上下文/G7 信任**，弃用"左/中/右组"合并分组；A 图、5.1、5.8 全链同步 G0~G7 番号 | 小欧 |
| v3.2 | 2026-09-08 22:04:21 | 全文章节号重排：第二章 2.2 子节由字母 A~H 重排为数字 **2.2.1~2.2.8**（2.2.1 第一行 / 2.2.2 Token / 2.2.3 Drawer / 2.2.4 时间轴 / 2.2.5 信息密度 / 2.2.6 颜色 / 2.2.7 无障碍 / 2.2.8 上下文），全文交叉引用同步；G7 信任可点击样式统一为"文字样式（深色加粗/框线/下划线）"，去除箭头与盾图标（[▸]/[盾]/RightOutlined）并同步 2.2.3/5.1/5.7/5.8/8.1；5.8 断点表列名改"G1-G4（状态/耗时/进度/异常）" | 小欧 |
| v3.3 | 2026-09-08 22:10:23 | G0 折叠改为 **G8 折叠**：番号体系 G0~G7 重组为 **G1~G8**（G1状态/G2耗时/G3进度/G4异常/G5 Token/G6上下文/G7信任/G8折叠），番号=渲染顺序，删除"番号≠渲染顺序"特殊说明；2.2.1、5.1、5.8、P0-2、2.2.1-八 全链同步 | 小欧 |
| v3.4 | 2026-09-08 22:15:20 | 图标渲染格式选型：全行图标统一为**单一格式 = @ant-design/icons 内联 SVG 组件**（fontSize 矢量缩放调大小 / currentColor 随文变色 / 跨平台一致 / 动画内建），否决 emoji、Unicode 纯文本符号、iconfont 字体图标、外链图、纯 CSS；**过程事件行由"纯文本符号 ▶ ⏸ ↻"升级为 antd SVG 图标**（PlayCircle/PauseCircle/ReloadOutlined），同步 2.2.4、P1-5、P2-13、5.4、5.9 | 小欧 |
| v3.5 | 2026-09-08 22:20:48 | 全文熟读核查一致性（修 4 处：v3.3 行"2.2.1-A 八"笔误、5.7"（原 P1-10）"冗余、5.9 emoji 检查补齐文本符号、2.2.1-七 表头列名统一"内联 SVG"）；**新增第十章"代码复用与模块划分（10 大规范核查）"**：依 DRY 抽 MetricItem/EllipsisTip/infoMaps 三文件，依 YAGNI 留 confirmRevoke/G7 样式在组件内，明确先查后建与判定规则 | 小欧 |
| v3.6 | 2026-09-08 22:35:08 | **新增第十一章"实施计划与步骤（TDD 模式）"**：判定 TDD 可行（主体 TDD + 视觉类后置验证混合）；分 6 阶段实施（底座→复用层→P0→P1→P2→回归），每步红→绿→重构；新增测试用例 27 项（纯函数 8 / 组件交互 11 / E2E 3 条链路），程序段前已核查前端无既有测试文件故无修改既有用例；DoD 验收 6 条 | 小欧 |

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

#### 2.2.1 第一行：核心信息带整体设计（信息位 G1~G8）

**一、设计原则（先定原则，再定布局）**

第一行是"任务实时状态条"，承载三类信息，按**主次**排布：

| 层级 | 类型 | 信息位 | 定位 |
|------|------|--------|------|
| **主信息**（运行态） | 被动展示 | G1 状态 · G2 耗时 · G3 进度 · G4 异常 | 用户最关心的"任务此刻怎样"，放最前 |
| **次信息**（资源态） | 被动展示 | G5 Token数值 · G6 上下文 | 辅助监控"消耗了多少"，居中 |
| **操作项**（交互） | 主动交互 | G7 信任 · G8 折叠 | 低频辅助操作，放最右不抢眼 |

```
四条铁律：
① 主次清楚 —— 主信息靠前，辅助操作靠右，绝不轻重倒置
② 番号独立 —— 每个信息位一个番号 G1~G8，互不合并、不依附
③ 可点必示 —— 凡可点击处必带"可点击样式"（字体样式/框线/下划线），不让用户猜
④ 层级统一 —— 全行统一"标签灰+数值加粗"两段式规范（见 5.5 颜色规范）
```

**二、整体线框图（渲染顺序）**

```
┌──────────────────────────────────────────────────────────────────────────┐
│ G1●执行中  G2 12s  G3 3步·2轮  G4↻重试中   G5 本轮T1,234/累计  G6上下文 │
│                                                                          │
│ 上下文 2,048tok           G7 信任(2)   G8 [▾] 收起                   │
│ ── 主信息(运行态) ──       ── 次信息(资源态) ──   ── 操作项 ──        │
└──────────────────────────────────────────────────────────────────────────┘
     渲染序：G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8（从左到右）
```

**三、番号体系与渲染顺序（关键结论）**

- **番号**（标识，逻辑分组）：G1 状态 · G2 耗时 · G3 进度 · G4 异常 · G5 Token数值 · G6 上下文 · G7 信任 · G8 折叠
- **渲染顺序**（物理，从左到右）：**G1 → G2 → G3 → G4 → G5 → G6 → G7 → G8**
- **番号 = 渲染顺序**：折叠是最次要辅助操作，排最右端（G8），主信息 G1 状态打头——番号与渲染从左到右完全一致
- G6「上下文」独立成番号（2.2.8 / P1-8 / 5.3 / D5），为后续单独优化预留挂载点

**四、各信息位设计规范**

| 番号 | 渲染序 | 类型 | 内容 | 字号 | 字重 | 色值 Token | 说明 |
|---|---|---|---|---|---|---|---|
| G1 状态 | 1 | 主 | Badge + 文字 | 12 | 500 | PRIMARY | antd Badge dot，**重要信息打头** |
| G2 耗时 | 2 | 主 | `12s` | 12 | 600 | PRIMARY | **tabular-nums** 等宽，加粗最醒目 |
| G3 进度 | 3 | 主 | `3步·2轮` | 12 | 400 | SECONDARY | 辅助信息，中灰 |
| G4 异常 | 4 | 主 | 图标+文字 | 12 | 500 | 见图标映射 | **统一 antd icon**，去掉 emoji |
| G5 Token数值 | 5 | 次 | 本轮 T / 累计 T | 见 2.2.2 | — | — | **本轮/累计 T 加粗、P/C 中灰** |
| G6 上下文 | 6 | 次 | 上下文段 | 见 2.2.8 | — | — | **标签+数值两段式，独立番号** |
| G7 信任 | 7 | 操作 | `信任(2)` | 12 | 500 | PRIMARY | **可点击文字样式**，Drawer 侧滑面板 |
| G8 折叠 | 8 | 操作 | `[▾] 收起` | 10 | 400 | TERTIARY | **辅助操作放最右**，不抢首位 |

**五、操作项的可点击样式（不让用户猜"能不能点"）**

两个操作位表达可点击，**方式不同、各取所长**：

| 操作位 | 可点击表达 | 说明 |
|--------|-----------|------|
| **G7 信任** | **文字样式**：PRIMARY 深色 + 加粗（或加圆角方框/下划线） | 靠**字体样式**提示可点，无需箭头图标 |
| **G8 折叠** | `[▾]` 箭头 | 纯图标，箭头方向=展开语义 |

> **设计取舍**：信任是"一段可点文字"，用**文字样式**（加粗/深色/框线/下划线）表达可点击，简洁直接；
> 折叠是"一个纯图标按钮"，用 `[▾]` 箭头表达。两操作位不需要一对方向箭头。

**G7 信任可点击样式方案**（三选一，统一即可）：

| 方案 | 实现 | 说明 |
|------|------|------|
| 方案 A：字体样式 | `信任(2)` 用 `colors: PRIMARY` + `fontWeight: 500` + hover 变色 | 最简洁，靠颜色+字重暗示可点 |
| 方案 B：方框 | `信任(2)` 套 `border-radius + padding 2px 6px + 浅底 #fafafa`（hover 加深）| 类似 Tag/按钮，一眼可点 |
| 方案 C：下划线 | `信任(2)` 文字加 `text-decoration: underline` | 经典链接语义，明确可点 |
| 交互反馈（通用） | hover 变 PRIMARY 深色 + `cursor: pointer`；focus-visible 2px outline | 任何方案都要带 |
| 无障碍 | `role="button"` + `aria-expanded={drawerOpen}` + `aria-controls` | 屏读播报"信任清单，已展开" |

> 推荐 **方案 A（字体样式）**：与第一行其他文字同位同构，不额外引入框/线元素，视觉最干净。

**六、关键改动汇总**

```
① 折叠排最右：G8 折叠位不抢首位，主信息 G1 状态打头
② 信任可点击：G7 用文字样式（加粗/深色/框线/下划线）表达可点击，不靠箭头图标
③ 上下文独立：G6 从 token 行拆出，独立番号（2.2.8）
④ 折叠无障碍：G8 补 role="button" + aria-expanded + tabIndex + onKeyDown
```

**七、G4 异常位图标统一方案**（去掉 emoji，全用 antd icon）：

| 场景 | 现状 | 改进 | antd icon（内联 SVG） | 理由 |
|------|------|------|-----------|------|
| 重试中 | `🔁` emoji | spin 动画 | `<SyncOutlined spin />` | 动画传达"进行中"，比静态 emoji 强 |
| 请求级错误 | `⛔` emoji | 灰色静态 | `<StopOutlined />` | 后端业务错误，非用户操作失败 |
| 执行级错误 | `<CloseCircleFilled/>` 红 | 不变 | `<CloseCircleFilled />` | 已是 antd icon，正确 |
| 截断警告 | `⚠` + `🔴` | 去🔴 | `<WarningOutlined />` | **去掉🔴**，与执行错误区分 |

**八、折叠 affordance（G8 无障碍落地）**

```
现状：整行 cursor:pointer，无任何视觉提示
改进：G8 区域加 [▾] 小三角（10px，TERTIARY色），点击响应折叠
      整行仍可点击（扩大热区），但三角是视觉锚点
      补 role="button" + aria-expanded + tabIndex + onKeyDown
```

---

#### 2.2.2 Token 数值行：分层显示（现状最大问题）

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
> 「上下文」不在此行定义，独立成单元格见 2.2.8「上下文段」——因上下文后续将单独优化，故提前独立预留。

**Token 数值行规范**（本轮/累计）：

| 元素 | 字号 | 字重 | 色值 | 说明 |
|------|------|------|------|------|
| 标签"本轮/累计" | 11 | 400 | TERTIARY | 小字灰色，不抢 |
| 数值 T 总数 | 12 | 600 | PRIMARY | 加粗，最醒目，核心监控值 |
| P/C 数值 | 12 | 500 | SECONDARY | 中灰，辅助信息 |
| 分隔符 `·` | 12 | 400 | BORDER | 极淡，不抢 |

---

#### 2.2.3 信任详情：Drawer 侧滑面板 + 撤销按钮首列

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
│ ... 信任(2)              ← 点击信任打开右侧 Drawer      │
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

#### 2.2.4 过程事件行：时间轴 + 分段带（体现时序与关系）

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
| 右列 | 事件图标 + 文本 | 12 | 400 | TERTIARY | antd SVG icon：PlayCircle/PauseCircle/ReloadOutlined |

**时序与关系表达**：
1. **从上到下**按时间顺序排列（最新在顶，遵循现状 reversed）
2. **时间线竖线**把各事件串起来──竖线段物理长度与时间间隔成正比，间隔大则段长、间隔小则段短，肉眼可读疏密
3. 每个事件都有**节点圆点**闭环，强化"这是一条连续的时间序列"
4. `role="log"` + `aria-live="polite"`，新事件实时播报

---

#### 2.2.5 信息密度对比（改进前后）

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

#### 2.2.6 颜色规范总结（改进后全局一张表）

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

#### 2.2.7 无障碍补全清单

| 位置 | 现状 | 改进 |
|------|------|------|
| 整行折叠 | 无 role/tabIndex/aria | `role="button"` + `aria-expanded` + `tabIndex={0}` + `onKeyDown` |
| 折叠热区 | 整行 onClick（与文本选中冲突） | 三角区域 onClick + stopPropagation，整行保留但不响应文本区 |
| TrustPanel 折叠 | ✅ 已有 role/aria/keyboard | 不变 |
| TrustPanel 撤销按钮 | 纯 span × | 改 antd Button + aria-label |
| 过程事件列表 | 无 role | `role="log"` + `aria-live="polite"` |

---

#### 2.2.8 上下文段（独立单元，为后续优化预留）

> **独立原则**：上下文段不再依附于 Token 数值行（2.2.2），单独成一格，赋予独立序号。
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

**上下文段交互行为**（hover/点击）：
| 交互 | 触发 | 响应 |
|------|------|------|
| 悬停（有数据） | pointer hover `<上下文 2,048 tok>` | Tooltip 显示 overview 摘要前 N 字 |
| 悬停（截断） | pointer hover 带 WarningOutlined | Tooltip 说明"上下文被截断，可能影响回答质量" |
| 悬停（无数据） | pointer hover `上下文 –` | Tooltip"上下文缺失，检查 frames 数据链路" |
| 点击（预留） | 单击整段 | 预留：展开上下文详情 Drawer（未来优化挂载点） |

**上下文段 `aria` 语义**：
| 属性 | 值 | 说明 |
|------|-----|------|
| `role` | `status` | 状态信息，非交互控件 |
| `aria-live` | `polite` | token 数变化时温和播报 |
| `aria-label` | `上下文 {n} tok{截断?'，已截断':''}` | 屏读完整语义，不吃 label 缩写 |
| `data-state` | `ok / summary-only / truncated / empty` | 供测试与样式钩子 |

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
2. G8 区域（折叠位）加一个小三角 `[▾]`（10px，TERTIARY 色）作为折叠视觉锚点
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
| 过程事件 | `▶️` `⏸️` `🔁` | antd SVG 图标 | `<PlayCircleOutlined/>` `<PauseCircleOutlined/>` `<ReloadOutlined/>` |

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

> 「上下文」段已独立成番号 P1-8（设计见第二章 2.2.8），不再于此定义，为后续单独优化预留。

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
4. emoji 改 antd SVG 图标 `<PlayCircleOutlined/>` `<PauseCircleOutlined/>` `<ReloadOutlined/>`

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

### 5.1 第一行布局（改进后，信息位 G1~G8 独立番号）

```
┌──────────────────────────────────────────────────────────────────────┐
│ G1●执行中  G2 12s  G3 3步·2轮  G4↻重试中  G5 本轮T1,234/累计 G6上下文│
│ 上下文 2,048tok          G7 信任(2)           G8 [▾] 收起              │
└──────────────────────────────────────────────────────────────────────┘
         ↑ 渲染序 G1→G2→G3→G4→G5→G6→G7→G8：折叠(辅助操作)放最右不抢眼
         ↑ G7 信任以文字样式提示可点：深色加粗/框线/下划线，无需箭头图标
```

| 番号 | 渲染序 | 内容 | 字号 | 字重 | 色值 Token | 说明 |
|---|---|---|---|---|---|---|
| G1 状态 | 1 | Badge + 文字 | 12 | 500 | PRIMARY | antd Badge dot，重要信息打头 |
| G2 耗时 | 2 | `12s` | 12 | 600 | PRIMARY | **tabular-nums**，等宽 |
| G3 进度 | 3 | `3步·2轮` | 12 | 400 | SECONDARY | 辅助信息 |
| G4 异常 | 4 | 图标+文字 | 12 | 500 | 见图标映射 | 统一 antd icon |
| G5 Token数值 | 5 | 本轮 T / 累计 T | 见 5.2 | — | — | **本轮/累计 T 加粗、P/C 中灰** |
| G6 上下文 | 6 | 上下文段 | 见 5.3 | — | — | **标签+数值两段式，独立番号** |
| G7 信任 | 7 | `信任(N)` | 12 | 500 | PRIMARY | **可点击文字样式**：深色加粗/框线/下划线 |
| G8 折叠 | 8 | `▾` 收起 | 10 | 400 | TERTIARY | **辅助操作排最右**，不占首位 |

> 番号 G1~G8 是信息位标识；渲染按 G1→G8 顺序，折叠(最次要辅助操作)放最右端，轻重有序。
> **G7 信任可点击样式**（详见 5.7）：以文字样式（PRIMARY 深色加粗/框线/下划线）+ hover 变色 + focus 描边表达可点击，无需箭头图标。

---

### 5.2 Token 数值行（G5 信息位，改进后）

```
本轮  T 1,234  P 890 / C 344   │  累计  T 5,678
 ── 标签灰 ── 加粗 ── 中灰 ──      ── 标签灰 ── 加粗
```
> 「上下文」已独立成 5.3 小节（信息位 G6），故 5.2 仅承载"本轮/累计"两段（信息位 G5）。

| 元素 | 字号 | 字重 | 色值 Token | 说明 |
|---|---|---|---|---|
| 标签"本轮/累计" | 11 | 400 | TERTIARY | 小字灰色 |
| T 总数 | 12 | 600 | PRIMARY | 加粗，最醒目 |
| P/C 数值 | 12 | 500 | SECONDARY | 中灰，辅助 |
| 分隔符 `·` | 12 | 400 | BORDER | 极淡，不抢 |

---

### 5.3 上下文段（G6 信息位，独立番号，为后续优化预留）

> **独立原则**：上下文段自成一格、独立番号（信息位 **G6**，对应问题 P1-8、设计稿 2.2.8）。
> 原因：上下文位置后续将单独优化，现在独立为将来扩展预留明确挂载点。

**改进后**（标签+数值两段式）：
```
上下文   2,048 tok
标签    数值
────    ────
灰      加粗(截断时 WARNING + WarningOutlined)
```

**上下文标签/数值独立定义**：

| 元素 | 字号 | 字重 | 色值 Token | 说明 |
|------|------|------|-----------|------|
| 标签"上下文" | 11 | 400 | TERTIARY | 小字灰色，独立定义 |
| 数值 `{n} tok` | 12 | 600 | PRIMARY | 加粗；截断时 WARNING |
| 截断标记 | 12 | 500 | WARNING | `<WarningOutlined />` 非"出错" |

**状态机**（4种→统一两段式）：

| 状态 | 标签 | 数值 | 色值 Token | 图标 |
|------|------|------|-----------|------|
| 有 overview + 有 token 数 | `上下文` | `{n} tok` | PRIMARY | 无 |
| 有 overview + 无 token 数 | `上下文` | `有摘要` | TERTIARY | 无 |
| 截断 | `上下文` | `{n} tok` | WARNING | WarningOutlined |
| 无数据 | `上下文` | `–` | TERTIARY | 无 |

**未来优化预留位**：
- 上下文摘要（summary 全文/展开）
- 注入比例 injected_ratio
- 消息数 message_count
- 截断策略/预警分级

---

### 5.4 图标统一方案

| 场景 | 现状 | 改进 | antd icon（内联 SVG） |
|------|------|------|------------------|
| 重试中 | `🔁` emoji | spin 动画 | `<SyncOutlined spin />` |
| 请求级错误 | `⛔` emoji | 灰色静态 | `<StopOutlined />` |
| 执行级错误 | `<CloseCircleFilled/>` | 不变 | `<CloseCircleFilled />` |
| 截断警告 | `⚠` + `🔴` | 去🔴 | `<WarningOutlined />` |
| 过程-开始 | `▶️` | SVG 图标 | `<PlayCircleOutlined />` |
| 过程-暂停 | `⏸️` | SVG 图标 | `<PauseCircleOutlined />` |
| 过程-恢复 | `▶️` | SVG 图标 | `<PlayCircleOutlined />` |
| 过程-重试 | `🔁` | SVG 图标 | `<ReloadOutlined />` |

**图标渲染格式选型（单一格式，方便调大小/颜色）**

第一行与过程事件行的图标，现状实际混用 4 种渲染格式（"乱七八糟"的根源）：

| 格式 | 现状出现 | 问题 |
|------|----------|------|
| Unicode emoji | 🔁 ⛔ ⚠ 🔴 ▶️ ⏸️ | 操作系统字体渲染，跨平台不一致、彩色、12px 基线漂移、U+FE0F 宽度不稳 |
| Unicode 纯文本符号 | ▶ ⏸ ↻ | 文本字形，仅能改颜色，能力弱、随字体变化 |
| antd 组件图标 | SyncOutlined、CloseCircleFilled、WarningOutlined 等 | = 内联 SVG 组件，fontSize/color 均可控 |
| CSS 状态点 | Badge dot | antd 自带状态圆点，非图标（保留正确） |

**统一结论：全行图标只保留一种格式 = @ant-design/icons 内联 SVG 组件**：

| SVG 优势 | 说明 |
|----------|------|
| 矢量缩放 | `fontSize` → SVG width/height，任意尺寸无失真，**调大小最方便** |
| 随文变色 | `color` → currentColor，与文字色联动，**调颜色最方便** |
| 描边可控 | stroke 继承 color，粗细统一 |
| 跨平台一致 | 不依赖操作系统字体，12px 不糊不漂 |
| 动画内建 | `<SyncOutlined spin />` 旋转加载 |
| 无障碍 | 组件级默认 aria-hidden，屏读不读乱码 |

**其他候选为何不用**：

| 候选 | 否决理由 |
|------|----------|
| iconfont 字体图标 | 单色单字重、依赖 web-font 加载、需加依赖，antd 生态已含 SVG |
| 外链 `<img>` / 背景图 | 不能继承 currentColor 变色、多一次请求 |
| 纯 CSS 绘制 | 复杂图形开销大、难维护 |
| emoji / Unicode 文本符号 | 跨平台渲染不一致、仅能改色，样式能力差 |

**过程事件行图标（重点修正）**：原方案"纯文本符号 ▶ ⏸ ↻"仍是 Unicode 文本、非 SVG，一并升级为 antd SVG 图标：

| 事件 | 图标（内联 SVG） |
|------|------------------|
| 开始 started | `<PlayCircleOutlined />` |
| 暂停 paused | `<PauseCircleOutlined />` |
| 恢复 resumed | `<PlayCircleOutlined />` |
| 重试 retrying | `<ReloadOutlined />` |

统一 `fontSize: 12` + `color: Colors.TEXT.TERTIARY`，与全行其他信息位图标同构同规格。

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

### 5.7 Drawer 信任面板实现要点（定案落地）

> 对应问题 P1-10、决策 D2、设计稿 2.2.3。撤销按钮移入每行首列。

**组件结构调整**（TrustPanel.tsx 重构方向）：
```typescript
// 第一行：仅保留计数徽标 + 展开按钮（不再内嵌列表）
<div role="button" aria-expanded={drawerOpen} tabIndex={0} onClick={openDrawer}>
  <ToolOutlined /> 信任({trustCount})                      // 点击打开 Drawer
</div>

// Drawer（右侧滑出），列表抽离为独立渲染
<Drawer
  placement="right"
  open={drawerOpen}
  onClose={closeDrawer}
  title="会话信任清单"
  width={360}
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

**撤销二次确认**（呼应 P0-4）：
```typescript
const confirmRevoke = (t: TrustItem) => {
  Modal.confirm({
    title: '确认撤销信任？',
    content: `撤销后将重新弹框确认「${t.toolName} › ${t.path ?? '全局'}」。`,
    okText: '确认撤销',
    cancelText: '取消',
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
| 持久化 | Drawer 开合状态不持久化（轻量瞬态），仅折叠态持久化（P0-3） |

---

### 5.8 第一行响应式断点策略（P1-9 落地）

| 断点 | 行为 |
|------|------|
| ≥ 1280px | 全部 8 个信息位展示（G1 状态 / G2 耗时 / G3 进度 / G4 异常 / G5 Token / G6 上下文 / G7 信任 / G8 折叠） |
| 1280 ~ 960px | G3 进度（`3步·2轮`）折叠进 Tooltip，仅留数字 |
| 960 ~ 768px | G4 异常文本省略（maxWidth 200 + ellipsis + Tooltip 全文） |
| < 768px | G2 耗时 + G3 进度合并，G5 Token 行（5.2）换行到第二行 |

```css
/* 外层容器允许换行，G5 Token 区最小宽度不为 0 */
.taskinfo-bar { display: flex; flex-wrap: wrap; row-gap: 4px; }
.taskinfo-token { min-width: 0; min-height: 20px; }
.taskinfo-token-inner {
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
```

| 断点 | G5（Token 数值） | G6（上下文） | G1-G4（状态/耗时/进度/异常） | G7（信任） |
|------|------------------|--------------|----------------|------------|
| ≥ 1280px | 完整（本轮/累计并排） | 完整（两段式） | 完整 | 完整 |
| < 1280px | 累计段可能收窄 | 独立段（5.3）可能换行 | 完整 | 完整 |
| < 960px | 累计段收进 Tooltip | 收进 Tooltip | 耗时 tabular-nums | 仅计数徽标 |

---

### 5.9 图标统一迁移检查清单（P1-5 落地）

> 原则：全组件统一 antd icon，禁用 emoji 文本图标。

| # | 检查点 | 来源代码 | 动作 |
|---|--------|----------|------|
| 1 | Badge dot（status）| :152 | 保留（已是 antd Badge） |
| 2 | `🔁` 重试 emoji | :171 | 改 `<SyncOutlined spin />` |
| 3 | `⛔` 请求错误 emoji | :183 | 改 `<StopOutlined />` |
| 4 | `⚠` 截断文本字符 | 截断分支 | 改 `<WarningOutlined />` |
| 5 | `🔴` 截断红点 | :243 | 删除，语义并入 WarningOutlined |
| 6 | `▶️⏸️🔁` 事件 emoji | :285-288 | 改 antd SVG 图标 `<PlayCircleOutlined/>` `<PauseCircleOutlined/>` `<ReloadOutlined/>` |
| 7 | 全局搜 `\p{Extended_Pictographic}` | 全文件 | 确保无遗留 emoji 图标 |

```powershell
# 全局检查是否残留 emoji 图标（Windows PowerShell）
Select-String -Path "frontend\src\features\chat\components\taskinfo\TaskInfoBar.tsx" -Pattern "🔁|⛔|⚠|🔴|▶️|⏸️|▶|⏸|↻|◀"
```

---

### 5.10 无障碍键盘导航流程（P0-2 / P2-18 落地）

**折叠行键盘操作**：
| 按键 | 行为 |
|------|------|
| `Tab` | 聚焦第一行（`role="button"` + `tabIndex={0}`） |
| `Enter` / `Space` | 切换 collapsed 折叠态 |
| `Shift+Tab` | 向后导航到 Token 行（`role="status"`） |

**信任 Drawer 键盘操作**：
| 按键 | 行为 |
|------|------|
| `Enter` | 触发信任按钮，打开 Drawer |
| `Esc` | 关闭 Drawer，焦点回到触发按钮 |
| `Tab` | 首列撤销 → 对象 → 下一行撤销（视觉/焦点顺序一致） |
| `Enter` / `Space`（撤销聚焦时） | 触发 Modal.confirm 二次确认 |

**焦点可见性**：折叠行与撤销按钮 `:focus-visible` 显式 outline（2px PRIMARY 蓝），无鼠标纯键盘可操作。

---

## 六、需确认的设计决策

| # | 问题 | 选项 A | 选项 B | 我的建议 |
|---|------|--------|--------|----------|
| D1 | Token 数值 P/C 露出来还是 hover 看？ | 露出来（占空间） | hover 看（紧凑） | **A：露出来**，核心监控信息 |
| D2 | TrustPanel 展开用浮层还是固定在第二行？ | absolute 浮层 | 固定第二行 | **已定案：Drawer 侧滑面板**，第一行固定高度，撤销按钮移入每行首列，走 Modal.confirm 二次确认 |
| D3 | 过程事件时间用绝对还是相对？ | `14:32:01` | `12秒前` | **A：绝对时间**，无需定时刷新 |
| D4 | collapsed 持久化方案？ | localStorage | 上提 state | **A：localStorage**，简单直接 |
| D5 | 上下文段是否独立成番号？ | 独立（P1-8 / 2.2.8） | 依附 token 行 | **A：独立成番号**，为后续单独优化（摘要/注入比例/截断策略）预留挂载点 |

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
| 第二阶段 | P1-7 Token 数值层级 | 20 min | 字重/色值调整（本轮/累计） |
| 第二阶段 | P1-8 上下文独立段 | 20 min | 独立番号：4 种文案→1 种两段式 + 截断 WarningOutlined |
| 第二阶段 | P1-9 窄屏溢出 | 15 min | flexWrap + min-width |
| 第二阶段 | P1-10 TrustPanel Drawer | 40 min | absolute 定位 → Drawer 侧滑 + 撤销首列 + Modal.confirm |
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

## 八、风险与降级策略

> 本方案涉及交互形态变更（Drawer、时间轴、上下文独立段），需明确迁移风险与降级路径，
> 确保任一改动在实测不理想时可平滑回退且不影响既有功能。

### 8.1 Drawer 信任面板风险

| 风险 | 等级 | 影响 | 缓解/降级 |
|------|------|------|-----------|
| Drawer 在窄屏/移动端占满宽度 | 中 | 遮住正文聊天区 | `width` 按视口 `min(360px, 80vw)`；`closable` + `Esc` 关闭 |
| 撤销二次确认（Modal.confirm）增加操作成本 | 低 | 用户撤销变慢 | 仅在"确认撤销"一步确认；取消无害；提示文案含工具名降低误确认 |
| Drawer 打开/关闭动画与 SSE 高频重渲染冲突 | 低 | 偶发闪烁 | Drawer 使用 `motion` 默认；列表数据变化仅触发内部刷新 |
| 第一行按钮可发现性降低（列表隐藏进抽屉） | 中 | 用户找不到信任项 | 保留计数徽标与可点击文字样式提示；hover 提示"查看信任清单" |

### 8.2 时间轴+分段带风险

| 风险 | 等级 | 影响 | 缓解/降级 |
|------|------|------|-----------|
| 事件间隔过大导致竖线过长占高 | 中 | 列表过高挤压布局 | 竖线最大高度封顶（如 24px），超过部分不变长 |
| 单一事件无间隔，时间轴退化为点列 | 低 | 视觉单调 | 无间隔时节点紧凑排列，仍保留时间列区分先后 |
| tabular-nums 字体在部分浏览器缺字符 | 低 | 数字宽度仍抖动 | 回退为 `font-variant-numeric: tabular-nums` + 等宽 `monospace` 兜底 |

### 8.3 上下文独立段风险

| 风险 | 等级 | 影响 | 缓解/降级 |
|------|------|------|-----------|
| 独立成番号后与 token 行视觉割裂 | 低 | 阅读连贯性 | 使用与"本轮/累计"完全一致的两段式结构，保持视觉同构 |
| 截断 WARNING 色被误判为错误 | 中 | 用户恐慌 | 采用 `<WarningOutlined/>`（非红圆）+ Tooltip 释明"被截断"语义 |
| 未来预留字段（injected_ratio 等）当前无数据 | 低 | 空字段 | 无数据默认隐藏，`data-state` 驱动，不占位冗余 |

### 8.4 整体回退策略

| 维度 | 策略 |
|------|------|
| 纯样式（色值/字重/图标） | 可即时回退，不影响逻辑，风险最低 |
| 结构（Drawer / 时间轴 / 上下文独立段） | 保留原功能调用链，仅替换渲染层；若实测不理想，还原渲染分支即可 |
| 无障碍 | 新增 role/aria 为纯增量，无降级负担 |
| 持久化（P0-3） | localStorage 键新设 `session_panel_collapsed:taskinfo.bar`，旧状态不冲突 |

---

## 九、设计令牌与术语索引

### 9.1 依赖的设计令牌（复用优先）

| 令牌 | 值 | 用途 |
|------|-----|------|
| `Colors.TEXT.PRIMARY` | `#595959` | 核心数值、耗时、加粗 |
| `Colors.TEXT.SECONDARY` | `#8c8c8c` | 辅助数值、时间、P/C |
| `Colors.TEXT.TERTIARY` | `#999` | 标签、事件文本 |
| `Colors.PRIMARY` | `#1677ff` | Badge running、焦点 outline |
| `Colors.ERROR` | `#ff4d4f` | 执行级错误红圆 |
| `Colors.WARNING` | `#faad14` | 重试/截断警告 |
| `Colors.BORDER.LIGHT` | `#f0f0f0` | 分隔线 |
| `FontSize.SECONDARY` | 12 | 主体数值 |
| `FontSize.CAPTION` | 11 | 标签/时间 |
| `Spacing.XS` | 4 | 紧凑间距 |

### 9.2 术语表

| 术语 | 含义 |
|------|------|
| **本轮 / 累计** | 单轮 ReAct 循环 token 数 / 会话累计 token 数 |
| **T / P / C** | Total / Prompt / Completion token 分项 |
| **上下文（Context）** | LLM 上下文注入段，独立成番号 P1-8 / 2.2.8 |
| **tabular-nums** | 等宽数字，避免倒计时数字抖动 |
| **Drawer** | antd 侧滑面板，用于信任清单 |
| **Modal.confirm** | antd 二次确认弹窗（撤销信任） |
| **`role="log"`** | WAI-ARIA 日志容器，配合 `aria-live` |
| **`aria-live="polite"`** | 屏读温和播报区域变更 |
| **时间轴+分段带** | 过程事件垂直时间线，竖线长≈时间间隔 |
| **标签+数值两段式** | `标签(灰) + 数值(加粗)` 信息排布范式 |

---

## 十、代码复用与模块划分（10 大规范核查）

> 以全行改进后设计为依据，按 10 大编码规范（日常 6 条：SRP / DRY / KISS-DIRECT / SLAP / YAGNI / 禁止 backward；重构 4 条：OCP / LSP / ISP / 复用优先）核查"可重用的逻辑实现"，明确**抽单独函数还是抽单独文件**。

### 10.1 可复用逻辑清单（先查后建，禁止重复造轮子）

| 可复用逻辑 | 设计稿中重复出现处 | 违反规范 | 结论：抽取粒度 |
|------------|--------------------|----------|----------------|
| **标签+数值两段式**结构 | 2.2.2 / 2.2.8 / 5.2 / 5.3 / 5.1 各表，同构定义 ≥4 处 | DRY（重复定义 4 次） | **抽独立组件 `MetricItem.tsx`** |
| **省略文本 + Tooltip** | G4 长错误（5.1）、G5 收窄进 Tooltip（5.8）、G6 上下文 hover（2.2.8）、折叠提示，共 ≥4 处 | DRY | **抽独立组件 `EllipsisTip.tsx`** |
| **状态 → 文案/色值/图标**映射 | BADGE_MAP、上下文段状态机（4 状态）、事件图标映射（started/paused/resumed/retrying） | DRY + SRP（状态语义散落） | **抽独立常量文件 `infoMaps.ts`** + 纯函数 `mapStatus()` |
| **等宽数字**规范 | 耗时数字（G2）、事件时间（2.2.4）、token 数（5.2/5.3）都用 tabular-nums | DRY | 共享 style 常量（复用现有 stepStyles 令牌），不新建文件 |
| **时间格式化** | `toLocaleTimeString()` 多处 | DRY/复用优先 | **先查** `src/utils/` 已有工具；无则加纯函数 `formatTime()` |
| **Drawer + Modal.confirm 撤销** | 仅信任清单 1 处 | YAGNI | **不抽文件**，留在 TrustPanel.tsx 内部函数（单处使用） |
| **G7 信任可点击文字样式** | 仅 1 处 | YAGNI | **不抽组件**，留在 TaskInfoBar.tsx |
| **信息位 G1~G8 渲染分发** | 8 个信息位 | KISS-DIRECT / SLAP / 禁 backward | **禁止工厂/注册表**，直接 if/elif 或 map 数组渲染 |

### 10.2 抽取决策（单函数 or 单文件判定）

| 单元 | 粒度 | 抽文件理由 | 不抽理由 |
|------|------|-----------|----------|
| `MetricItem`（标签+数值+可选图标） | 独立组件/文件 | 4 处重复、props 稳定（label/text/tone/icon），改一处全行同构 | — |
| `EllipsisTip`（文本 + maxWidth ellipsis + Tooltip 全文） | 独立组件/文件 | 4 处 hover/省略场景，行为一致 | — |
| `infoMaps.ts`（状态映射常量 + `mapStatus` 纯函数） | 独立常量模块 | 状态语义集中管理，新增状态仅加映射（OCP 扩展） | — |
| `formatTime()` | 独立函数 | 跨 G1~G8 多处时间展示 | 若 `src/utils/` 已有则**直接复用**，禁止重复写 |
| `confirmRevoke()` | 组件内函数 | — | 单处使用，抽文件违反 YAGNI |
| G7 可点击样式 | 组件内样式 | — | 单处使用，禁止过早抽象 |

**判定规则**：组件/纯函数且**复用处 ≥ 2** → 独立文件；**单处使用** → 留在所在组件，宁简勿繁（KISS-DIRECT + YAGNI）。

### 10.3 新建文件清单（全前端）

| 文件 | 职责 | 存放位置 |
|------|------|----------|
| `MetricItem.tsx` | 标签（灰 11px）+ 数值（加粗 12px）+ 可选 SVG 图标，支持 tone/截断态（G5/G6/P1 同构） | `frontend/src/features/chat/components/taskinfo/` |
| `EllipsisTip.tsx` | 省略文本 + Tooltip 全文的封装 | 同上 |
| `infoMaps.ts` | BADGE_MAP / CONTEXT_STATE_MAP(4 态) / EVENT_ICON_MAP + `mapStatus()` 纯函数 | 同上 |

### 10.4 复用优先核查纪律（实现前必查）

1. **先查后建**：写代码前先查 `frontend/src/utils/`、`src/theme/tokens.ts`、现有 taskinfo/ 组件，有则复用，无则新建并入库
2. **令牌复用**：颜色/字号/间距一律引用 `stepStyles.ts`（Colors/FontSize/Spacing），禁止硬码（呼应 P2-12）
3. **图标复用**：全部走 antd icon（内联 SVG），禁止 emoji/纯文本符号（呼应 5.4 选型）
4. **禁止局部重造**：时间格式化若 `src/utils/` 已存在 `formatTime` 则直接调用，不新写功能重复的函数
5. **不提前抽象**：确认撤销、信任可点击样式等单处逻辑留在组件内，等出现第二次重复再抽（YAGNI 优先）

---

## 十一、实施计划与步骤（TDD 模式）

### 11.1 TDD 可行性判定

**结论：可以 TDD，采用"主体 TDD + 视觉类后置验证"混合模式。**

| 测试对象 | 属性 | TDD 适配度 | 处理方式 |
|----------|------|-----------|----------|
| 纯函数与映射：`mapStatus` / `EVENT_ICON_MAP` / `BADGE_MAP` / `formatToken` / `formatTime` | 逻辑纯化 | ✅ 完全适配 | 红→绿→重构（最快循环） |
| 组件渲染与 aria：折叠按钮（P0-2）、上下文 4 态（P1-8）、MetricItem、EllipsisTip、Token 两段式（P1-7） | DOM 可断言 | ✅ 适配 | 红→绿→重构 |
| 交互链路：撤销 Modal.confirm（P0-4）、Drawer 开合与焦点（P1-10）、G8 折叠 toggle | DOM 事件 | ✅ 适配 | 红→绿→重构 |
| 视觉样式：tabular-nums 对齐（P2-16）、对比度（P1-6）、断点切换（P1-9）、Drawer 动画 | 视觉弱断言 | ⚠️ 收益低 | 实现后 E2E/视觉验证锁定，不做红绿循环 |

> 前端现状核查：`frontend/` 已配 Vitest + Playwright，但**无既有测试文件**（`tests/` 仅测量脚本）→ 本轮全部为**新增用例**，无修改既有用例。

### 11.2 分阶段实施步骤（顺序合理，每阶段 = 红→绿→重构）

| 阶段 | 步骤 | 内容（TDD 循环） | 对应设计稿 | 依赖 |
|------|------|------------------|-----------|------|
| 0 底座 | 0.1 | 建 `src/test/setup.ts`（jsdom + jest-dom）、建 `tests/unit/`、`tests/e2e/` 目录，`npm run test` 空套件跑通 | — | — |
| 1 复用层 | 1.1 | `infoMaps.ts`：先写 5 组映射测试（BADGE_MAP 含 cancelled 区分 / CONTEXT_STATE_MAP 4 态 / EVENT_ICON_MAP 4 事件）→ **红** → 建常量+`mapStatus()` → **绿**→重构 | 2.2.1 / 2.2.4 / 2.2.8 / 10.3 | 0.1 |
| | 1.2 | `formatToken`（千分位 T 1,234）、`formatTime`（HH:MM:SS）：先写断言 → **红** → 建纯函数 → **绿**（先查 `src/utils/`，有则直接复用） | 5.2 / 5.3 / 10.3 | 0.1 |
| | 1.3 | `MetricItem`：先写 props 渲染 / tone / 截断态 aria 测试 → **红** → 建组件 → **绿** | 2.2.2 / 2.2.8 / 5.2 / 5.3 | 0.1 |
| | 1.4 | `EllipsisTip`：先写省略 + Tooltip 全文测试 → **红** → 建组件 → **绿** | 5.1(G4) / 5.8 / 2.2.8 | 0.1 |
| 2 P0 优先级 | 2.1 | P0-1 探针删除：直接删（零逻辑，不写测试，回归验证） | P0-1 | — |
| | 2.2 | P0-2 折叠 a11y：先写 `role="button"` / `aria-expanded` / `tabIndex` / Enter+Space 触发测试 → **红** → 改折叠实现 → **绿** | 2.2.1-八 / 5.10 | 1.4 |
| | 2.3 | P0-4 撤销确认：先写点"撤销"触发 `Modal.confirm`、取消不删、确认才删测试 → **红** → 实现 → **绿** | 2.2.3 / 5.7 | 0.1 |
| | 2.4 | P0-3 collapsed 持久化：先写 localStorage 键 `session_panel_collapsed:taskinfo.bar` 存取/挂载恢复测试 → **红** → 实现 → **绿** | 5.7 | 0.1 |
| 3 P1 视觉/结构 | 3.1 | P1-5 图标统一：先写"过程事件无 emoji/无纯文本符号、渲染 antd SVG"测试 → **红** → 替换 → **绿** | 2.2.4 / 5.4 / 5.9 | 1.1 |
| | 3.2 | P1-8 上下文 4 态：先写 4 态 `data-state` / 标签 / aria-label 测试 → **红** → 接 `CONTEXT_STATE_MAP` + MetricItem → **绿** | 2.2.8 / 5.3 | 1.1+1.3 |
| | 3.3 | P1-7 Token 两段式：先写"本轮/累计分离、千分位、P/C 中灰"测试 → **红** → 接 MetricItem → **绿** | 2.2.2 / 5.2 | 1.1+1.2 |
| | 3.4 | P1-10 信任 Drawer：先写`role="button"` + hover/focus 样式 + 打开 Drawer + 焦点移入面板测试 → **红** → 实现 → **绿** | 2.2.3 / 5.7 | 1.4 |
| | 3.5 | P1-6/P1-11（直接实现）：对比度调色、分隔线归属，不走红绿，E2E/视觉锁定 | P1-6 / P1-11 | — |
| 4 P2 打磨 | 4.1 | P2-15 badge：先写 cancelled 与 idle 文案/色断言 → **红** → 改 `BADGE_MAP` → **绿** | 2.2.1 / 5.1 | 1.1 |
| | 4.2 | P2-16 耗时：先写 tabular-nums 类断言 → **红** → 加样式令牌 → **绿** | 2.2.1 / 5.1 | 0.1 |
| | 4.3 | P2-13 过程事件：先写"唯一 key + 时间 HH:MM:SS + SVG 图标"测试 → **红** → 实现（key=`${e.time}-${e.kind}`）→ **绿** | 2.2.4 / 5.5 | 1.1 |
| | 4.4 | P2-12 令牌 / P2-14 timestamp / P2-17 高度 / P2-18 撤销按钮：直接实现（Token 引用/语义化小改），回归验证 | P2-12/14/17/18 | — |
| 5 回归 | 5.1 | `npm run test` 全绿、`npm run check` 零告警 | — | 全 |
| | 5.2 | Playwright 3 条关键链路（11.3-C）通过（真实后端） | — | 5.1 |

### 11.3 新增测试用例清单

**A. 纯函数/映射（Vitest，最快红绿）**

| 用例 | 断言要点（红） | 对应设计稿 |
|------|----------------|-----------|
| `mapStatus — ok`（有 overview 与 token） | 返回"正常"标签/数值/BLUE/对应 data-state | 2.2.8 |
| `mapStatus — summary-only`（仅总结令牌） | 返回收窄数值/SEGMENT 灰 | 2.2.8 |
| `mapStatus — truncated` | 返回截断态 + WarningOutlined + 色值 | 2.2.8 |
| `mapStatus — empty` | 返回"待注入"SURFACE 灰 | 2.2.8 |
| `EVENT_ICON_MAP` | started→PlayCircle / paused→PauseCircle / resumed→PlayCircle / retrying→Reload | 2.2.4 |
| `BADGE_MAP` | idle→default+待命、cancelled→error/muted 区分（P2-15） | 2.2.1 |
| `formatToken` | 1234→"T 1,234"、无值→"—" | 5.2 |
| `formatTime` | 时间→"HH:MM:SS" 固定格式 | 2.2.4 |

**B. 组件与交互（Vitest + RTL）**

| 用例 | 断言要点（红） | 对应设计稿 |
|------|----------------|-----------|
| 折叠按钮（G8） | `role`/`aria-expanded`/`tabIndex`/Enter/Space 触发 toggle（P0-2） | 2.2.1-八 / 5.10 |
| 折叠轨道三角 | `stopPropagation` 点击不冒泡到底行（5.1 注） | 5.1 |
| 上下文段 4 态 | `data-state` + 标签/数值/aria 文案（P1-8） | 2.2.8 |
| MetricItem | label/value/tone/截断态 + aria-label | 2.2.2 |
| EllipsisTip | 文本省略 + Tooltip 全文 + aria | 5.1(G4) |
| Token 两段式 | 本轮/累计分离渲染、千分位、P/C 中灰（P1-7） | 2.2.2 / 5.2 |
| 过程事件行 | 每行唯一 key、时间 HH:MM:SS、SVG 图标、无 emoji（P2-13） | 2.2.4 |
| 信任（G7） | `role="button"` + 打开 Drawer + 焦点移入面板（P1-10） | 2.2.3 / 5.7 |
| 撤销按钮 + Modal.confirm | 点击弹确认、取消不删、确认走 `revoke`（P0-4/P2-18） | 5.7 |
| 耗时数字 | tabular-nums 类、位数不抖动（P2-16） | 5.1 |
| collapsed 持久化 | localStorage 写入/挂载恢复（P0-3） | 5.7 |

**C. E2E（Playwright，真实后端 + 真实 LLM 会话）**

| 用例 | 链路 |
|------|------|
| 会话渲染 | 新建会话 → 第一行 8 信息位渲染（G1 状态 / G2 耗时 / G3 进度 / G4 异常 / G5 Token / G6 上下文 / G7 信任 / G8 折叠） |
| 折叠 + 持久化 | 点击 G8 收起 → 宽度收窄 → 刷新后保持收起（P0-3） |
| 信任 Drawer + 撤销 | 打开 G7 → Drawer 侧滑 → 撤销 → Modal.confirm 确认 → 真实撤销语义（P0-4/P1-10/P2-18） |

> E2E 铁律照旧：一次只跑一个 case、真实后端、subprocess.Popen 落盘、禁 Mock（见 AGENTS.md E2E 手册）。

### 11.4 既有测试用例处理

已核查 `frontend/`：**无既有单测/E2E 断言文件**（`tests/` 仅 measurement 脚本，不涉 UI 断言）→ 本轮**无修改既有用例**，全部新增。若实现阶段联动改动 Step 渲染既有业务组件，其断言按"先测后改"迁移（先红后绿），禁止先改断言再实现。

### 11.5 测试命令

| 场景 | 命令（workdir=`frontend/`） |
|------|------------------------------|
| 全量单测 | `npm run test` |
| 跑单个用例 | `npm run test -- --run <name>` |
| TDD 迭代 | `npm run test:watch` |
| 覆盖率 | `npm run test:coverage` |
| E2E | `npm run test:e2e` |
| 提交前检查 | `npm run check` |

### 11.6 验收标准（Definition of Done）

1. 阶段 1~4 新增用例全部转绿，无 `skip/skip-suite`
2. 阶段 5.2 三条 E2E 链路通过（真实后端）
3. `npm run check` 零告警
4. 第十章 10.3 复用清单落地：无重复实现，时间函数先查 `src/utils/` 后建
5. 5.9 图标残留检查通过：emoji / 纯文本符号（▶ ⏸ ↻）清零
6. 行数不退化、不做 backward 兼容（新旧状态机不并存）

---

**编写人：小欧**
**编写时间：2026-09-08 22:35:08**
**文档版本：v3.6**
