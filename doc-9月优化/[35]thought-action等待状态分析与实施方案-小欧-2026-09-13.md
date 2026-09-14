# [35] thought→action等待状态分析与实施方案

**编写人**：小欧
**编写时间**：2026-09-13 21:09:45
**版本**：v1.7

---

## 一、问题现象

前端在thought内容显示完毕后，到action步到达之间，有时出现一段空白等待期——后端LLM正在推理生成action，心跳正常发送（1~5个心跳回应），但前端没有任何等待状态指示，用户看到的是"干等着"。

## 二、现有等待状态分析

### 2.1 三个等待阶段

| 阶段 | 等待图标 | 颜色 | 触发条件 | 消失条件 |
|------|---------|------|---------|---------|
| 等thought内容 | 绿色270°弧线旋转 | #52c41a | `thought-start`事件到达 | 首个thinking chunk到达（`appendToLast`覆盖waiting segment） |
| **等action响应** | **无（缺失）** | **—** | **—** | **—** |
| 等action执行结果 | 橙色8臂loader旋转 | #fa8c16 | `action`步到达且`!hasResult` | `observation`到达（`hasResult=true`） |

### 2.2 缺失段定位

```
thought-start → [绿色圆圈] → thinking chunks → [???缺失???] → action步 → [橙色齿轮] → observation → 完成
                    ↑                           ↑                                        ↑
               绿色消失                    最后一个chunk                        齿轮出现
                                          到达此处
```

心跳在此期间正常发送（1~5个），证明后端存活，只是前端无指示。

## 三、根因分析

### 3.1 后端流程

`react_cycle.py` ReAct循环：

1. 发送 `thought-start` 事件（每轮LLM调用前）
2. 流式发送thinking chunks（`is_reasoning=true`）
3. **调用LLM生成action（耗时，无SSE事件发出）**
4. 发送 `action` 事件（工具调用信息）
5. 执行工具，发送 `observation` 事件
6. 回到步骤1（下一轮）

步骤3是LLM推理时间，可能较长（数秒到数十秒），期间无任何SSE事件。

### 3.2 前端渲染逻辑

`PipelineRenderer.tsx` `buildSegments()` 中：

- `thought-start` → 产生 `{ kind: 'waiting' }` segment → 渲染绿色圆圈
- `chunk(is_reasoning=true)` → `appendToLast('thinking', content)` → **覆盖waiting segment** → 绿色圆圈消失
- `action` → 产生 `{ kind: 'tool' }` segment → ToolCallLine渲染橙色齿轮

**问题**：绿色圆圈被thinking chunk覆盖后，到action步到达前，没有新的waiting segment产生。

### 3.3 `taskActive` 条件

```typescript
const taskActive =
  streaming ||
  !!highlightToolName ||
  badge === 'running' ||
  badge === 'paused';
```

心跳期间 `taskActive` 为true（badge='running'），但没有waiting segment渲染。

## 四、方案设计

### 4.1 方案选择：前端推断

**不改后端**。在 `buildSegments()` 中，检测到最后一步是thinking segment且taskActive为true时，自动追加一个蓝色等待segment。

选择理由：
- 符合项目现有架构（前端信号驱动，不依赖后端新事件）
- 改动量小（~38行），不碰后端/SSE解析/ToolCallLine
- 与绿色圆圈机制一致（`appendToLast`覆盖机制自然处理消失）

### 4.2 图标设计

| 属性 | 值 | 理由 |
|------|-----|------|
| 颜色 | `#1677ff`（蓝色） | 与绿色(思考)、橙色(执行)三色区分，蓝色=LLM决策中 |
| 形状 | 270°弧线（与绿色圆圈同款） | 保持视觉一致，降低认知成本 |
| 大小 | 1.4em × 1.4em | 与绿色圆圈同级 |
| 动画 | 复用 `waiting-spin`（1s逆时针旋转） | 不新增CSS动画 |
| aria-label | `"等待LLM决策"` | 语义区分 |

### 4.3 显示条件（同时满足）

1. `buildSegments()` 从 `executionSteps` 完整列表构建所有segment后，最后一个segment的 `kind === 'thinking'`（说明最后收到的是thinking chunk，action还没到）
2. `taskActive === true`（streaming/badge=running/badge=paused/highlightToolName 任一为真）
3. 此时 `buildSegments()` 在thinking segment后面追加一个 `action-waiting` segment

### 4.4 消失条件（任一满足）

1. **action步到达**：`buildSegments()` 产生 `tool` segment，排在 `thinking` 和 `action-waiting` 后面 → `action-waiting` 不再是最后一个segment → 蓝色圆圈消失，橙色齿轮出现
2. **任务结束**：`final`/`error` 到达 → `taskActive` 变false → 蓝色圆圈不渲染
3. **新一轮thought-start到达**：覆盖为新的等待thought的绿色圆圈（理论上可能，实际正常流程几乎不会发生，因为正常顺序是action→observation→thought-start，此时action-waiting已消失）

### 4.5 渲染位置

在pipeline最底部，紧跟最后一个thinking segment之后。与绿色圆圈位置相同，用户视线不需要移动。

### 4.6 风险与代码对策

| 风险 | 影响 | 代码对策 |
|------|------|---------|
| **误判：thinking后是text chunk（非action）** | 蓝色圆圈短暂闪烁 | text chunk到达后 `appendToLast('text', content)` 产生text segment，排在action-waiting后面 → action-waiting不再是最后一个 → 蓝色圆圈自动消失。代码层面无需额外处理，机制天然覆盖 |
| **误判：final紧跟thinking（无action）** | 蓝色圆圈短暂出现 | final到达后 `taskActive` 变false → 渲染条件不满足 → 蓝色圆圈不渲染。代码层面无需额外处理 |
| **性能：每轮多一个segment** | 几乎无影响 | segment是纯对象（{kind:'action-waiting'}），无DOM、无状态、无事件监听，内存开销可忽略 |
| **aria-label语义** | 屏幕阅读器读到"等待LLM决策" | 这是正确语义，不需要修改 |

### 4.7 代码改动清单

| 文件 | 改动内容 | 预估行数 |
|------|---------|---------|
| `PipelineRenderer.tsx` | `buildSegments()` 末尾追加 `action-waiting` segment逻辑 | ~10行 |
| `PipelineRenderer.tsx` | 新增 `ActionWaitingIcon` 组件（蓝色270°弧线） | ~15行 |
| `PipelineRenderer.tsx` | 渲染分支增加 `action-waiting` kind处理 | ~8行 |
| `index.css` | 新增 `.action-waiting-cursor` 样式（蓝色，复用 `waiting-spin` 动画） | ~5行 |

**总计：~38行改动，不碰后端，不碰SSE解析，不碰ToolCallLine。**

### 4.8 流程图

```
用户发送消息
  → thought-start到达 → buildSegments产生waiting → 绿色圆圈显示
  → thinking chunks到达 → appendToLast覆盖waiting → 绿色圆圈消失，thinking文字出现
  → 最后一个thinking chunk到达 → buildSegments构建完，最后一个是thinking + taskActive=true
    → 追加action-waiting segment → 蓝色圆圈显示 ← 新增
  → action步到达 → buildSegments产生tool segment（排在thinking和action-waiting后面）
    → action-waiting不再是最后一个segment → 蓝色圆圈消失，橙色齿轮显示
  → observation到达 → 橙色齿轮消失
  → final到达 → taskActive=false → 所有动画停止
```

### 4.9 segment数组变化示意

```
[thinking, thinking, thinking]                          ← thinking chunks到达后
[thinking, thinking, thinking, action-waiting]          ← 蓝色圆圈追加（末尾是thinking + taskActive）
[thinking, thinking, thinking, action-waiting, tool]    ← action到达，tool排在最后
```

## 五、代码实施（真实diff）

### 5.1 现状：三个等待图标处理方式

| 图标 | 当前位置 | 处理方式 | 问题 |
|------|---------|---------|------|
| ThoughtWaitingIcon（绿色弧线） | `PipelineRenderer.tsx:110-124` | 内联 `const WaitingIcon` 组件，私有不导出 | 其他文件无法复用 |
| ToolWaitingIcon（橙色loader） | `ToolCallLine.tsx:230-253` | 内联 `<svg>` 直接嵌JSX，无封装 | 无法复用，改一处漏另一处 |
| ActionWaitingIcon（蓝色波纹扩散） | 不存在 | — | 需新建 |

**决定**：三个图标统一拆成独立控件文件，放在 `frontend/src/components/WaitingIcons/` 目录，DRY复用。

### 5.2 新建 `WaitingIcons/index.tsx`（三个图标统一出口）

路径：`frontend/src/components/WaitingIcons/index.tsx`

```tsx
// 编辑历史: 2026-09-13 小欧 - 新建等待图标控件组: ThoughtWaitingIcon/ToolWaitingIcon/ActionWaitingIcon从PipelineRenderer/ToolCallLine内联提取, 统一导出, DRY复用 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - ActionWaitingIcon换型(北京老陈令选title-icon-compare G波纹扩散): 蓝色270°弧线旋转改蓝核心圆+双层扩散波纹(SVG36x36, .action-ripple-1/.action-ripple-2, 1.8s不旋转) — 小欧-2026-09-13
import React from 'react';

/**
 * ThoughtWaitingIcon — 绿色270°弧线旋转
 * 用途：thought-start到达后、首个thinking chunk到达前的等待状态
 * 原位置：PipelineRenderer.tsx 内联 const WaitingIcon（私有）
 */
export const ThoughtWaitingIcon: React.FC = () => (
  <span className="waiting-cursor" aria-label="等待思考输出">
    <svg
      width="1.4em"
      height="1.4em"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#52c41a"
      strokeWidth={2}
      strokeLinecap="round"
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  </span>
);

/**
 * ToolWaitingIcon — 橙色8臂loader旋转
 * 用途：action步到达后、observation到达前的工具执行等待状态
 * 原位置：ToolCallLine.tsx 内联 <svg>（直接嵌JSX无封装）
 */
export const ToolWaitingIcon: React.FC = () => (
  <span className="tool-waiting-cursor" aria-label="等待工具完成">
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="#fa8c16"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2v4" />
      <path d="M12 18v4" />
      <path d="M4.93 4.93l2.83 2.83" />
      <path d="M16.24 16.24l2.83 2.83" />
      <path d="M2 12h4" />
      <path d="M18 12h4" />
      <path d="M4.93 19.07l2.83-2.83" />
      <path d="M16.24 7.76l2.83-2.83" />
    </svg>
  </span>
);

/**
 * ActionWaitingIcon — 蓝色波纹扩散（G: 波纹扩散样式）
 * 用途：thinking内容显示完毕后、action步到达前的LLM决策等待状态
 * 新增位置：全新组件
 * 动画：蓝核心圆 + 两层扩散波纹，scale 0.5→1.4 + opacity 1→0，1.8s周期，不旋转
 */
export const ActionWaitingIcon: React.FC = () => (
  <span className="action-waiting-cursor" aria-label="等待action到达">
    <svg
      viewBox="0 0 36 36"
      width="1.4em"
      height="1.4em"
      fill="none"
      strokeWidth={2}
    >
      <circle cx="18" cy="18" r="6" stroke="#1677ff" />
      <circle
        cx="18"
        cy="18"
        r="10"
        opacity="0.6"
        className="action-ripple-1"
        stroke="#1677ff"
      />
      <circle
        cx="18"
        cy="18"
        r="10"
        opacity="0.6"
        className="action-ripple-2"
        stroke="#1677ff"
      />
    </svg>
  </span>
);
```

### 5.3 `index.css` 新增 `.action-waiting-cursor` 样式（波纹扩散动画）

```diff
--- a/frontend/src/index.css
+++ b/frontend/src/index.css
@@ -134,4 +134,26 @@
+/* 2026-09-13 小欧 - action等待图标: 蓝色波纹扩散(G样式), scale 0.5→1.4 + opacity 1→0, 1.8s周期, 不旋转 — 小欧-2026-09-13 */
+@keyframes action-ripple {
+  0% {
+    transform: scale(0.5);
+    opacity: 1;
+  }
+  100% {
+    transform: scale(1.4);
+    opacity: 0;
+  }
+}
+.action-waiting-cursor {
+  display: inline-block;
+  vertical-align: baseline;
+}
+.action-waiting-cursor svg {
+  display: block;
+}
+.action-ripple-1 {
+  transform-origin: center;
+  transform-box: fill-box;
+  animation: action-ripple 1.8s ease-out infinite;
+}
+.action-ripple-2 {
+  transform-origin: center;
+  transform-box: fill-box;
+  animation: action-ripple 1.8s ease-out infinite;
+  animation-delay: 0.9s;
+}
```

### 5.4 `PipelineRenderer.tsx` 改动

#### 5.4.1 import 改动：删除内联WaitingIcon，引入新组件

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
+++ b/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ -80,6 +80,7 @@
 import { TextStream } from './TextStream'; // 13.8 正文打字机 — 小欧 2026-08-30
+import { ThoughtWaitingIcon, ActionWaitingIcon } from '@/components/WaitingIcons'; // 2026-09-13 小欧: ThoughtWaitingIcon/ActionWaitingIcon从内联提取为独立控件 — 小欧-2026-09-13
 import {
```

#### 5.4.2 删除内联 WaitingIcon 组件（原110-124行）

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
+++ b/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ -107,22 +107,6 @@
-// 4.4.2(2026-09-07 小欧, 10大规范-复用优先/DRY): 等待图标唯一 SVG 定义 —
-//   waiting 段渲染分支专用(旧 showGreenCircle 兜底已删除, 见编辑历史 2026-09-07 去留) — 小欧-2026-09-07
-const WaitingIcon: React.FC = () => (
-  <span className="waiting-cursor" aria-label="等待下一个思考内容">
-    <svg
-      width="1.4em"
-      height="1.4em"
-      viewBox="0 0 24 24"
-      fill="none"
-      stroke="#52c41a"
-      strokeWidth={2}
-      strokeLinecap="round"
-    >
-      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
-    </svg>
-  </span>
-);
```

#### 5.4.3 组件体内追加 action-waiting 逻辑（buildSegments调用之后）

**注意**：buildSegments 是纯函数，只接收 `steps` 参数，不能访问 `streaming`/`badge` 等组件 props。action-waiting 逻辑必须放在 buildSegments 调用之后的组件体内。

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
+++ b/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ -275,6 +275,15 @@
   const segs = buildSegments(steps);
+  // 2026-09-13 小欧 - ActionWaitingIcon segment追加: 末段是thinking + taskActive=true时,
+  //   追加ActionWaitingIcon; action到达后tool segment排在它后面自然消失; taskActive=false时不显示
+  const lastSeg = segs[segs.length - 1];
+  if (lastSeg && lastSeg.kind === 'thinking' && taskActive) {
+    segs.push({ kind: 'action-waiting' });
+  }
   // 2026-09-04 小欧 - observation 去重
```

其中 `taskActive` 在 action-waiting 判定之前已声明（原位置不变，仅提前了注释块）：

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
+++ b/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ -275,6 +275,11 @@
   const segs = buildSegments(steps);
+  const taskActive =
+    streaming ||
+    !!highlightToolName ||
+    badge === 'running' ||
+    badge === 'paused';
   // 2026-09-04 小欧 - observation 去重
```

#### 5.4.4 PipelineSegment union 新增 action-waiting 类型

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
+++ b/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ -101,6 +101,7 @@
   | { kind: 'obs'; step: ExecutionStep }
   | { kind: 'error'; step: ExecutionStep }
-  | { kind: 'waiting'; step?: number }; // 4.4.2(2026-09-07 小欧): thought-start 落段, 可被首个内容覆盖接管
+  | { kind: 'waiting'; step?: number } // 4.4.2(2026-09-07 小欧): thought-start 落段, 可被首个内容覆盖接管
+  | { kind: 'action-waiting' }; // 2026-09-13 小欧: thinking末段+taskActive时追加ActionWaitingIcon(LLM推理action中)
```

#### 5.4.5 渲染分支：waiting段用ThoughtWaitingIcon替换WaitingIcon + 新增action-waiting渲染

```diff
--- a/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
+++ b/frontend/src/features/chat/components/pipeline/PipelineRenderer.tsx
@@ -329,7 +329,7 @@
           if (i !== segs.length - 1 || !taskActive) return null;
           return (
             <div key={`waiting-${i}`} style={{ margin: stepMargin(false) }}>
-              <WaitingIcon />
+              <ThoughtWaitingIcon />
             </div>
           );
         }
+        if (seg.kind === 'action-waiting') {
+          // 2026-09-13 小欧: ActionWaitingIcon, 仅末段+taskActive显示, action到达后tool段排在后面自然消失
+          if (i !== segs.length - 1 || !taskActive) return null;
+          return (
+            <div key={`action-waiting-${i}`} style={{ margin: stepMargin(false) }}>
+              <ActionWaitingIcon />
+            </div>
+          );
+        }
```

### 5.5 `ToolCallLine.tsx` 改动：内联SVG替换为ToolWaitingIcon组件

```diff
--- a/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
+++ b/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
@@ -1,3 +1,4 @@
+import { ToolWaitingIcon } from '@/components/WaitingIcons'; // 2026-09-13 小欧: ToolWaitingIcon从内联提取为独立控件 — 小欧-2026-09-13
 // ... 其他imports保持不变 ...
```

```diff
--- a/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
+++ b/frontend/src/features/chat/components/pipeline/ToolCallLine.tsx
@@ -230,24 +230,7 @@
           {!hasResult && tools.length > 0 && !interrupted && !replay && (
-            <span className="tool-waiting-cursor" aria-label="工具执行中">
-              {/* 2026-09-08 小欧 - 图标换型(北京老陈令:齿轮旋转不明显): 齿轮(settings)换Feather loader弧段,
-                  三段弧非对称旋转时位置变化幅度大, 视觉感知明显; stroke线框橙#fa8c16/1s逆时针不变,
-                  尺寸由index.css统一控 1.1em(≈15px) — 小欧-2026-09-08 */}
-              <svg
-                viewBox="0 0 24 24"
-                fill="none"
-                stroke="#fa8c16"
-                strokeWidth={2}
-                strokeLinecap="round"
-                strokeLinejoin="round"
-              >
-                <path d="M12 2v4" />
-                <path d="M12 18v4" />
-                <path d="M4.93 4.93l2.83 2.83" />
-                <path d="M16.24 16.24l2.83 2.83" />
-                <path d="M2 12h4" />
-                <path d="M18 12h4" />
-                <path d="M4.93 19.07l2.83-2.83" />
-                <path d="M16.24 7.76l2.83-2.83" />
-              </svg>
-            </span>
+            <ToolWaitingIcon />
           )}
```

### 5.6 改动文件清单

| 文件 | 操作 | 改动内容 | 预估行数 |
|------|------|---------|---------|
| `frontend/src/components/WaitingIcons/index.tsx` | **新建** | ThoughtWaitingIcon + ToolWaitingIcon + ActionWaitingIcon 三个控件（ActionWaitingIcon 为 G 波纹扩散） | ~88行 |
| `frontend/src/index.css` | 追加 | `@keyframes action-ripple` + `.action-ripple-1/.action-ripple-2` 波纹扩散动画 + `.action-waiting-cursor` 容器 | ~22行 |
| `PipelineRenderer.tsx` | 编辑 | import新组件 + 删内联WaitingIcon + union加action-waiting + 组件体内追加逻辑 + 渲染分支 | ~30行增删 |
| `ToolCallLine.tsx` | 编辑 | import新组件 + 删内联SVG | ~18行删除 |

**总计：~158行改动，不碰后端，不碰SSE解析，不碰useTaskInfo。**

---

## 六、等待图标代码梳理（小欧 2026-09-14）

### 6.1 三种等待图标定义

| 图标 | 组件名 | 颜色 | 色值 | 动画 | 定义位置 |
|------|--------|------|------|------|---------|
| 绿色弧线旋转 | `ThoughtWaitingIcon` | SUCCESS | `#52c41a` | `waiting-spin` 1s逆时针旋转 | `components/WaitingIcons/index.tsx:12-26` |
| 蓝色波纹扩散 | `ActionWaitingIcon` | PRIMARY | `#1677ff` | `action-ripple` 1.8s scale 0.5→1.4 + opacity 1→0，双层交替 | `components/WaitingIcons/index.tsx:61-89` |
| 橙色齿轮旋转 | `ToolWaitingIcon` | WAIT_ACTION | `#fa8c16` | `waiting-spin` 1s逆时针旋转 | `components/WaitingIcons/index.tsx:33-53` |

**颜色令牌**：定义在 `utils/stepStyles.ts:110-143`，`Colors.PRIMARY` / `Colors.SUCCESS` / `Colors.WAIT_ACTION`。

### 6.2 CSS 动画定义

| 动画 | 文件位置 | 关键参数 |
|------|---------|---------|
| `@keyframes waiting-spin` | `index.css:116-123` | 0→360deg逆时针，1s linear infinite，被绿色弧线/橙色齿轮/title图标复用 |
| `@keyframes action-ripple` | `index.css:148-158` | scale(0.5)→scale(1.4) + opacity(1)→opacity(0)，1.8s ease-out infinite |
| `.action-ripple-1` | `index.css:166-170` | transform-origin:center, transform-box:fill-box, animation: action-ripple 1.8s |
| `.action-ripple-2` | `index.css:171-176` | 同上 + animation-delay: 0.9s（与 ripple-1 交替扩散） |

### 6.3 触发与消失逻辑

**PipelineRenderer** (`pipeline/PipelineRenderer.tsx`)：

```
buildSegments(steps) → PipelineSegment[]
         ↓
taskActive = computeTaskActive(highlightToolName, badge)   ← viewState.ts:13-18
         ↓
末段 kind === 'thinking' + taskActive === true
         ↓
追加 { kind: 'action-waiting' } segment                    ← :291-293
         ↓
渲染: action-waiting 段 → <ActionWaitingIcon />              ← :332-342
```

**消失触发**（任一满足）：
1. action 步到达 → `buildSegments` 产生 `tool` 段 → action-waiting 不再是末段 → 自动消失
2. taskActive=false（final/error/badge=completed）→ 不渲染
3. 新 thought-start 覆盖为绿色等待圈

### 6.4 状态管理链路

| 状态 | 管理方式 | 位置 |
|------|---------|------|
| `taskActive` | 纯函数 `computeTaskActive()` | `utils/viewState.ts:13-18` |
| `isCurrentLive` | 纯函数 `computeIsCurrentLive()` | `utils/viewState.ts:39-51` |
| `badge` | `useMemo` 派生（从 steps/frames/detail 计算） | `hooks/useTaskInfo.ts` |
| `loading` | `useState(false)` REST 历史加载 | `components/right/RightViewer.tsx:173` |

**taskActive 判定逻辑**：
```typescript
!!highlightToolName || badge === 'running' || badge === 'paused'
```

### 6.5 组件调用链路

```
ChatPage → useChatPanels → useChatState (loading/isPaused)
                    ↓
         ┌── ChatInput → SubmitBar (loading→发送/停止切换)
         │
         └── RightViewer
                │
                ├── Spin spinning={loading && !isCurrentLive}    ← AntD spinner
                │
                └── PipelineRenderer
                       │
                       ├── buildSegments(steps) → PipelineSegment[]
                       │     ├── 'waiting'段 → ThoughtWaitingIcon (绿色)
                       │     ├── 'action-waiting'段 → ActionWaitingIcon (蓝色)
                       │     └── 'tool'段 → ToolCallLine → ToolWaitingIcon (橙色)
                       │
                       ├── ThinkingStream (thinking-cursor ▍光标闪烁)
                       └── computeTaskActive(highlightToolName, badge)
```

### 6.6 文件清单

| 文件 | 角色 |
|------|------|
| `components/WaitingIcons/index.tsx` | 三个等待图标组件定义 |
| `index.css:106-176` | 所有等待动画 CSS（waiting-spin + action-ripple） |
| `utils/viewState.ts` | `computeTaskActive` / `computeIsCurrentLive` 纯函数 |
| `utils/stepStyles.ts:110-143` | Colors 令牌定义 |
| `pipeline/PipelineRenderer.tsx` | 流水线渲染，构建 segment 并消费等待图标 |
| `pipeline/ThinkingStream.tsx:48` | thinking-cursor ▍光标 |
| `hooks/useTaskInfo.ts` | badge 状态派生（idle/running/paused/completed/failed） |
| `components/right/RightViewer.tsx:458` | Spin spinner + isCurrentLive 判定 |

---

**更新时间**：2026-09-14 12:15:00
**版本**：v1.8
**更新内容**：第六章6.5图已恢复（含ToolCallLine/ThinkingStream），6.6文件清单仅保留蓝色圈圈相关文件，小欧编写
