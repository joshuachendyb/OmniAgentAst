# 会话页分割面板(SplitPane)Bug深度分析与修复方案

| 版本 | 时间 | 签名 | 修改简介 |
|------|------|------|---------|
| v1.0 | 2026-10-27 16:50 | 小欧 | 新建：深入分析SplitPane组件全部bug，按10大规范给出修复方案 |
| v1.1 | 2026-10-27 17:30 | 小欧 | 补充8个新发现Bug(Bug-8~Bug-18)，含startDrag闭包陷阱、fullLeft状态残留、测试不足细化、触摸/动画缺失等 |
| v1.2 | 2026-10-27 17:20 | 小欧 | 复核结论(3遍)：确认12个真实Bug、7个非Bug/可选；新增Bug-19(getInitialWidth containerW=0+stored返回0)；合并Bug-12→Bug-3 |
| v1.3 | 2026-10-27 17:31 | 小欧 | 修复双击语义(方案A)+Bug-19：双击改"设为新默认"写回localStorage不跳回；删除死代码clearStoredWidth；getInitialWidth containerW<=0返回偏好值；测试17/17通过 |
| v1.4 | 2026-10-27 17:47 | 小欧 | 默认值双向管理(设计文档[51])：双击=存储新默认，Shift+双击=返回出厂默认；重新引入clearStoredWidth；提示文案更新；测试19/19通过 |

编写人：小欧

---

## 一、分析范围

本次分析覆盖以下文件：
- `frontend/src/features/chat/components/layout/SplitPane.tsx` (307行)
- `frontend/src/features/chat/components/layout/SessionLayout.tsx` (208行)
- `frontend/src/constants/layout.ts` (25行)
- `frontend/src/tests/unit/SplitPane.test.tsx` (252行)
- 设计文档 `doc-10月优化/[49]会话页可拖动分割面板优化方案.md`

测试状态：**17/17 通过**（Bug-3 回归测试已添加，记录 maxW=0 问题）

---

## 二、Bug清单（按严重程度排序）

### Bug-1 [严重] 文档v1.1功能未实现：根据rightOpen调整默认宽度

**问题描述**：
设计文档 `[49]` 明确描述 v1.1 优化："根据 rightOpen 状态调整默认宽度（折叠 240px/展开 280px）"，并给出了带 `rightOpen` 参数的实现：

```typescript
// 文档中描述的 v1.1 实现
const getInitialWidth = (containerW: number, rightOpen: boolean): number => {
  if (containerW === 0) {
    return rightOpen ? 280 : 240;
  }
  if (rightOpen) {
    return Math.min(280, Math.round(containerW * 0.22));
  }
  return Math.min(240, Math.round(containerW * 0.18));
};
```

**实际代码**（`SplitPane.tsx:71-83`）：
```typescript
const getInitialWidth = (containerW: number): number => {
  const stored = readStoredWidth();
  if (stored !== null) {
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);
    return Math.min(stored, maxW);
  }
  if (containerW === 0) {
    return 300;  // ← 硬编码300，没有rightOpen参数
  }
  return Math.round(containerW * SPLIT_LEFT_DEFAULT_RATIO);  // ← 始终30%
};
```

**违反规范**：
- **YAGNI**：设计文档描述了用户需求（右侧折叠时左侧更窄），但未实现
- **关联检查**：SessionLayout 已传递 `fullLeft={!rightOpen}` 给 SplitPane，但 SplitPane 忽略了 rightOpen 对默认宽度的影响

**根因**：
v1.1 设计时考虑了 rightOpen 调整，但实现时改为固定30%，文档未同步更新。

**修复方案**：

方案A（推荐）：恢复 rightOpen 调整逻辑
```typescript
// SplitPane.tsx 接口扩展
interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  fullLeft?: boolean;
  // 新增：右侧展开状态，用于调整默认宽度
  rightOpen?: boolean;
}

// getInitialWidth 增加 rightOpen 参数
const getInitialWidth = (containerW: number, rightOpen: boolean): number => {
  const stored = readStoredWidth();
  if (stored !== null) {
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);
    return Math.min(stored, maxW);
  }
  if (containerW === 0) {
    // 容器未布局完成：折叠态240px，展开态280px
    return rightOpen ? 280 : 240;
  }
  // 展开态：22%容器宽，最大280px
  // 折叠态：18%容器宽，最大240px
  const ratio = rightOpen ? 0.22 : 0.18;
  const maxPX = rightOpen ? 280 : 240;
  return Math.min(maxPX, Math.round(containerW * ratio));
};

// SessionLayout.tsx 透传 rightOpen
<SplitPane
  left={renderSlot(panels, 'left')}
  fullLeft={!rightOpen}
  rightOpen={rightOpen}  // ← 新增
  right={...}
/>
```

方案B（保守）：保持固定30%，更新文档
- 删除文档中 v1.1 关于 rightOpen 的描述
- 在代码注释中说明"为何不根据 rightOpen 调整"

**选择方案A的理由**：
- 用户需求真实（左侧菜单栏在右侧折叠时需要更窄）
- 改动极小（仅增加一个prop和getInitialWidth参数）
- 符合 YAGNI（需求驱动，不预设未来）

---

### Bug-2 [中等] ResizeObserver比例计算分母不一致

**问题位置**：`SplitPane.tsx:140`

```typescript
const ratio = prev / (container.offsetWidth || 1);
```

**问题**：
- `newContainerW`（来自 `entry.contentRect.width`）是浏览器已计算的准确新尺寸
- `container.offsetWidth` 理论上也应已更新，但在 CSS transition 或某些边界场景下可能滞后
- 两者混用导致比例计算不一致

**违反规范**：
- **KISS-DIRECT**：逻辑绕弯，同一函数内用两个不同来源的尺寸值

**修复方案**：
```typescript
// 修复前
const ratio = prev / (container.offsetWidth || 1);

// 修复后：统一用 newContainerW 作为基准
// 但需要注意：ratio = prev / oldContainerW，我们需要旧容器宽度
// 解决方案：在ResizeObserver外缓存旧宽度
const containerWRef = useRef<number>(0);
// ...
const ratio = prev / (containerWRef.current || 1);
containerWRef.current = newContainerW;
```

或者更简洁的方式——直接用比例而非绝对宽度：
```typescript
// 存储比例而非绝对宽度（推荐）
const leftRatioRef = useRef<number>(SPLIT_LEFT_DEFAULT_RATIO);
// ...
setLeftW((prev) => {
  if (prev === null) return getInitialWidth(newContainerW, rightOpen);
  // prev 是像素值，转换为比例后再应用新容器宽度
  const ratio = prev / (containerWRef.current || 1);
  containerWRef.current = newContainerW;
  const maxW = Math.round(newContainerW * SPLIT_LEFT_MAX_RATIO);
  return Math.min(Math.max(SPLIT_LEFT_MIN_PX, Math.round(newContainerW * ratio)), maxW);
});
```

---

### Bug-3 [中等] maxW初始值为0导致首次键盘↑受限（已确认）

**问题位置**：`SplitPane.tsx:106`

```typescript
const [maxW, setMaxW] = useState<number>(0);
```

**问题**：
- `maxW` 初始值 0
- `useLayoutEffect` 同步执行后才设置正确值
- 极端情况下（如 SSR 或快速操作），用户可能在 maxW=0 时按 → 键
- `Math.min(0, w + 16) = 0`，宽度无法增大

**违反规范**：
- **KISS-DIRECT**：初始状态与预期状态不一致

**修复方案**：
```typescript
// 修复前
const [maxW, setMaxW] = useState<number>(0);

// 修复后：初始值设为合理默认
const [maxW, setMaxW] = useState<number>(() => {
  // 使用窗口宽度估算一个合理初始值
  return Math.round((window.innerWidth || 1024) * SPLIT_LEFT_MAX_RATIO);
});
```

**测试验证**：
- `SplitPane.test.tsx:118-131` 已记录此 bug（作为回归测试）
- 修复后需更新测试断言

**问题位置**：`SplitPane.tsx:106`

```typescript
const [maxW, setMaxW] = useState<number>(0);
```

**问题**：
- `maxW` 初始值 0
- `useLayoutEffect` 同步执行后才设置正确值
- 极端情况下（如 SSR 或快速操作），用户可能在 maxW=0 时按 → 键
- `Math.min(0, w + 16) = 0`，宽度无法增大

**违反规范**：
- **KISS-DIRECT**：初始状态与预期状态不一致

**修复方案**：
```typescript
// 修复前
const [maxW, setMaxW] = useState<number>(0);

// 修复后：初始值设为合理默认
const [maxW, setMaxW] = useState<number>(() => {
  // 使用窗口宽度估算一个合理初始值
  return Math.round((window.innerWidth || 1024) * SPLIT_LEFT_MAX_RATIO);
});
```

或更简单——直接给 useLayoutEffect 前的状态设一个安全默认值：
```typescript
const SAFE_MAX_W = Math.round(window.innerWidth * SPLIT_LEFT_MAX_RATIO);
const [maxW, setMaxW] = useState<number>(SAFE_MAX_W);
```

---

### Bug-4 [轻微] handleDoubleClick 缺少 fullLeft 防护

**问题位置**：`SplitPane.tsx:215-221`

```typescript
const handleDoubleClick = useCallback(() => {
  clearStoredWidth();
  const container = containerRef.current;
  if (container) {
    setLeftW(getInitialWidth(container.offsetWidth));
  }
}, []);
```

**问题**：
- 虽然分割线在 `fullLeft=true` 时不渲染（`!fullLeft && (...)`），双击事件不会触发
- 但如果通过其他方式调用（如测试、refs 直接调用），会在折叠态重置宽度
- 折叠态下 `setLeftW` 无意义（左列 flex 填满，不受 leftW 控制）

**违反规范**：
- **SRP**：handleDoubleClick 应只处理展开态的重置逻辑

**修复方案**：
```typescript
const handleDoubleClick = useCallback(() => {
  if (fullLeft) return;  // ← 新增防护
  clearStoredWidth();
  const container = containerRef.current;
  if (container) {
    setLeftW(getInitialWidth(container.offsetWidth, rightOpen));
  }
}, [fullLeft, rightOpen]);  // ← 补充依赖
```

---

### Bug-5 [轻微] containerW=0 时硬编码300无说明

**问题位置**：`SplitPane.tsx:78-80`

```typescript
if (containerW === 0) {
  return 300;  // ← 无注释说明300来源
}
```

**问题**：
- 300 是哪里来的？没有注释
- 与 SPLIT_LEFT_DEFAULT_RATIO=0.30 不一致（300px 对应 1000px 容器的 30%）
- 文档说 v1.1 改为 240/280，但代码仍是 300

**修复方案**：
```typescript
if (containerW === 0) {
  // 容器未布局完成时的安全默认值
  // 与 SPLIT_LEFT_DEFAULT_RATIO=0.30 对应（1000px容器→300px）
  // v1.1: 根据 rightOpen 调整为 240/280（见Bug-1）
  return rightOpen ? 280 : 240;
}
```

---

### Bug-6 [中等] 测试覆盖不充分

**问题位置**：`SplitPane.test.tsx`

**现状**：
| 测试用例 | 实际断言 | 问题 |
|---------|---------|------|
| 键盘←减小宽度 | `expect(separator).toBeInTheDocument()` | 只验证没崩，没验证宽度变化 |
| 键盘→增大宽度 | `expect(separator).toBeInTheDocument()` | 同上 |
| localStorage持久化 | `expect(item).not.toBeNull()` | 只验证key存在，没验证值正确 |
| 拖动测试 | **完全没有** | 核心功能无测试 |
| ResizeObserver | **完全没有** | 窗口缩放无测试 |
| 双击重置 | 只验证localStorage清除 | 没验证宽度重置 |
| fullLeft折叠态 | 5个用例 | 覆盖较好 |

**违反规范**：
- **关联检查**：测试是代码质量的最后一道防线，不充分测试埋下回归风险

**修复方案**：
```typescript
// 新增：拖动测试
it('拖动后宽度正确更新', () => {
  const { container } = render(<SplitPane left={<div>左</div>} right={<div>右</div>} />);
  const separator = screen.getByRole('separator');
  
  // 模拟mousedown + mousemove + mouseup
  const mockContainer = { offsetWidth: 1000 };
  Object.defineProperty(container, 'offsetWidth', { value: 1000, writable: true });
  
  fireEvent.mouseDown(separator, { clientX: 300 });
  fireEvent.mouseMove(window, { clientX: 400 });
  fireEvent.mouseUp(window);
  
  // 验证：宽度从300变为400
  const leftPanel = container.querySelector('div:first-child');
  expect(leftPanel).toHaveStyle({ width: '400px' });
});

// 新增：键盘宽度变化测试
it('键盘→键增大左侧宽度', () => {
  const { container } = render(<SplitPane left={<div>左</div>} right={<div>右</div>} />);
  const separator = screen.getByRole('separator');
  
  fireEvent.keyDown(separator, { key: 'ArrowRight' });
  
  const leftPanel = container.querySelector('div:first-child');
  // 初始300 + 16 = 316
  expect(leftPanel).toHaveStyle({ width: '316px' });
});

// 新增：ResizeObserver测试
it('容器缩放时按比例重算宽度', () => {
  const { container } = render(<SplitPane left={<div>左</div>} right={<div>右</div>} />);
  
  // 模拟容器从1000px缩放到800px
  Object.defineProperty(container, 'offsetWidth', { value: 800, writable: true });
  
  // 触发ResizeObserver回调
  const entry = { contentRect: { width: 800 } };
  // ... 模拟ResizeObserver触发
  
  // 验证：宽度从300px按比例变为240px
  const leftPanel = container.querySelector('div:first-child');
  expect(leftPanel).toHaveStyle({ width: '240px' });
});
```

---

### Bug-8 [中等] startDrag闭包陷阱：leftW变化时旧监听器可能残留

**问题位置**：`SplitPane.tsx:158-190`

```typescript
const startDrag = useCallback((e: React.MouseEvent) => {
  e.preventDefault();
  const x0 = e.clientX;
  const w0 = leftW ?? 0;  // ← 闭包捕获当前leftW
  lastWidthRef.current = w0;
  const container = containerRef.current;
  if (!container) return;

  const containerW = container.offsetWidth;
  const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);  // ← 闭包捕获当前容器宽

  const move = (ev: MouseEvent) => {
    const newW = Math.min(maxW, Math.max(SPLIT_LEFT_MIN_PX, w0 + ev.clientX - x0));
    // ...
  };
  // ...
}, [leftW]);  // ← 依赖leftW，每次leftW变化都重建
```

**问题**：
- `startDrag` 依赖 `[leftW]`，当 `leftW` 变化时（如 ResizeObserver 触发、键盘调整），会重新创建函数
- 如果在拖动过程中 `leftW` 被其他操作改变（理论上不可能，但存在竞态风险），旧的 mousemove/mouseup 监听器引用的是旧的 `w0` 和 `maxW`
- 更关键的是：当 `fullLeft` 从 false 变为 true 时，`useLayoutEffect` 直接 `return`，不会清理可能存在的拖动状态

**违反规范**：
- **KISS-DIRECT**：闭包依赖导致状态不一致，逻辑绕弯
- **关联检查**：`startDrag` 的创建时机与 `leftW` 变化不同步

**修复方案**：
```typescript
// 方案A：移除leftW依赖，改用ref追踪
const leftWRef = useRef<number>(0);
leftWRef.current = leftW;

const startDrag = useCallback((e: React.MouseEvent) => {
  e.preventDefault();
  const x0 = e.clientX;
  const w0 = leftWRef.current;  // ← 读ref而非闭包
  lastWidthRef.current = w0;
  const container = containerRef.current;
  if (!container) return;

  const containerW = container.offsetWidth;
  const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);

  const move = (ev: MouseEvent) => {
    const newW = Math.min(maxW, Math.max(SPLIT_LEFT_MIN_PX, w0 + ev.clientX - x0));
    lastWidthRef.current = newW;
    setLeftW(newW);
  };

  const up = () => {
    window.removeEventListener('mousemove', move);
    window.removeEventListener('mouseup', up);
    document.body.style.userSelect = '';
    document.body.style.cursor = '';
    cleanupRef.current = null;
    writeStoredWidth(lastWidthRef.current);
  };

  cleanupRef.current = up;
  document.body.style.userSelect = 'none';
  document.body.style.cursor = 'col-resize';
  window.addEventListener('mousemove', move);
  window.addEventListener('mouseup', up);
}, []);  // ← 无依赖，稳定引用
```

---

### Bug-9 [中等] fullLeft切换时leftW/maxW状态未重置

**问题位置**：`SplitPane.tsx:114-122`

```typescript
useLayoutEffect(() => {
  if (fullLeft) return; // ← 直接return，不清理状态
  const container = containerRef.current;
  if (container) {
    const totalW = container.offsetWidth;
    setLeftW(getInitialWidth(totalW));
    setMaxW(Math.round(totalW * SPLIT_LEFT_MAX_RATIO));
  }
}, [fullLeft]);
```

**问题**：
- 当 `fullLeft` 从 `false` 变为 `true`（右侧折叠）时，`useLayoutEffect` 直接 `return`
- `leftW` 和 `maxW` 保留了展开时的值
- 当用户再次展开右侧（`fullLeft` 变回 `false`），会重新计算宽度，但如果 localStorage 有值，会使用存储的旧值而非根据 `rightOpen` 调整

**实际影响**：
- 用户折叠右侧后，再展开，左侧宽度可能不符合设计文档 v1.1 的预期（240px/280px）
- 这是 Bug-1 的连锁反应

**修复方案**：
```typescript
useLayoutEffect(() => {
  if (fullLeft) {
    // 折叠态：清空leftW/maxW，让flex布局接管
    setLeftW(null);
    setMaxW(0);
    return;
  }
  const container = containerRef.current;
  if (container) {
    const totalW = container.offsetWidth;
    setLeftW(getInitialWidth(totalW, rightOpen));  // ← 传入rightOpen
    setMaxW(Math.round(totalW * SPLIT_LEFT_MAX_RATIO));
  }
}, [fullLeft, rightOpen]);  // ← 增加rightOpen依赖
```

---

### Bug-10 [中等] 测试断言过弱，无法发现实际Bug

**问题位置**：`SplitPane.test.tsx:75-98`

**现状**：
```typescript
it('键盘 ← 键减小左侧宽度', () => {
  render(<SplitPane left={<div>左</div>} right={<div>右</div>} />);
  const separator = screen.getByRole('separator');
  fireEvent.keyDown(separator, { key: 'ArrowLeft' });
  // 验证事件被处理（实际宽度变化需要更复杂的测试）← 注释暴露问题
  expect(separator).toBeInTheDocument();  // ← 只验证没崩
});

it('键盘 → 键增大左侧宽度', () => {
  render(<SplitPane left={<div>左</div>} right={<div>右</div>} />);
  const separator = screen.getByRole('separator');
  fireEvent.keyDown(separator, { key: 'ArrowRight' });
  expect(separator).toBeInTheDocument();  // ← 同上
});
```

**问题**：
- 测试只验证"事件被处理"，没有断言实际宽度变化
- 如果 `handleKeyDown` 完全无效，测试仍然通过
- 注释"实际宽度变化需要更复杂的测试"表明测试作者知道覆盖不足

**违反规范**：
- **关联检查**：测试是代码质量的最后一道防线，弱断言等于没有防线

**修复方案**：
```typescript
it('键盘 ← 键减小左侧宽度', () => {
  const { container } = render(
    <SplitPane left={<div>左</div>} right={<div>右</div>} />
  );
  const separator = screen.getByRole('separator');
  
  // 模拟容器宽度
  Object.defineProperty(container, 'offsetWidth', { value: 1000, writable: true });
  act(() => {});
  
  const initialLeftW = container.querySelector('div:first-child')?.style.width;
  
  fireEvent.keyDown(separator, { key: 'ArrowLeft' });
  act(() => {});
  
  const finalLeftW = container.querySelector('div:first-child')?.style.width;
  // 断言宽度确实减少了
  expect(Number(finalLeftW?.replace('px', ''))).toBeLessThan(Number(initialLeftW?.replace('px', '')));
});

it('键盘 → 键增大左侧宽度', () => {
  const { container } = render(
    <SplitPane left={<div>左</div>} right={<div>右</div>} />
  );
  const separator = screen.getByRole('separator');
  
  Object.defineProperty(container, 'offsetWidth', { value: 1000, writable: true });
  act(() => {});
  
  const initialLeftW = container.querySelector('div:first-child')?.style.width;
  
  fireEvent.keyDown(separator, { key: 'ArrowRight' });
  act(() => {});
  
  const finalLeftW = container.querySelector('div:first-child')?.style.width;
  expect(Number(finalLeftW?.replace('px', ''))).toBeGreaterThan(Number(initialLeftW?.replace('px', '')));
});
```

---

### Bug-11 [轻微] SPLIT_LEFT_MAX_RATIO=0.80设计过于激进

**问题位置**：`constants/layout.ts:21`

```typescript
export const SPLIT_LEFT_MAX_RATIO = 0.80;
```

**问题**：
- 左侧最大占 80%，右侧仅剩 20%
- 右侧面板包含 Step 详情、工具调用结果、文件预览等多层内容
- 当右侧内容需要较大空间时（如查看长代码、文件预览），20% 宽度不够用

**实际影响**：
- 用户在 1440px 屏幕上最多可将左侧拖到 1152px，右侧仅剩 288px
- 右侧 Step 内容在 288px 内显示拥挤

**修复方案**：
```typescript
// 方案A：降低最大值
export const SPLIT_LEFT_MAX_RATIO = 0.70;  // 左侧最多70%，右侧保留30%

// 方案B：增加配置项，允许右侧最小宽度
export const SPLIT_RIGHT_MIN_PX = 300;  // 右侧最小300px
```

---

### Bug-12 [轻微] handleKeyDown在maxW=0时的边界竞态

**问题位置**：`SplitPane.tsx:202-210`

```typescript
} else if (e.key === 'ArrowRight') {
  e.preventDefault();
  setLeftW((w) => {
    const next = Math.min(maxW, (w ?? 0) + 16);  // ← maxW初始为0
    writeStoredWidth(next);
    return next;
  });
}
```

**问题**：
- `maxW` 初始值为 0（`useState<number>(0)`）
- `useLayoutEffect` 在首次渲染后才会设置正确的 maxW
- 极端情况下（如 SSR 或快速操作），用户可能在 maxW=0 时按 → 键
- `Math.min(0, w + 16) = 0`，宽度无法增大

**违反规范**：
- **KISS-DIRECT**：初始状态与预期状态不一致

**修复方案**：
```typescript
// 方案A：给maxW设置合理初始值
const SAFE_MAX_W = Math.round((typeof window !== 'undefined' ? window.innerWidth : 1024) * SPLIT_LEFT_MAX_RATIO);
const [maxW, setMaxW] = useState<number>(SAFE_MAX_W);

// 方案B：在handleKeyDown中加防护
} else if (e.key === 'ArrowRight') {
  e.preventDefault();
  setLeftW((w) => {
    const currentMaxW = maxW > 0 ? maxW : SAFE_MAX_W;
    const next = Math.min(currentMaxW, (w ?? 0) + 16);
    writeStoredWidth(next);
    return next;
  });
}
```

---

### Bug-13 [轻微] 折叠态左面板仍保留borderRight视觉分隔

**问题位置**：`SplitPane.tsx:235-248`

```typescript
<div
  style={{
    width: fullLeft ? undefined : leftW ?? undefined,
    flex: fullLeft ? '1 1 0' : undefined,
    minWidth: SPLIT_LEFT_MIN_PX,
    overflow: 'auto',
    overflowX: 'hidden',
    borderRight: `1px solid ${Colors.BORDER.LIGHT}`,  // ← 折叠态仍保留
  }}
>
```

**问题**：
- 当 `fullLeft=true` 时，左面板 flex 填满整个容器
- 但 `borderRight` 仍然保留，在左面板右侧显示一条分隔线
- 此时右面板仅按钮条，分隔线没有意义，反而造成视觉干扰

**修复方案**：
```typescript
<div
  style={{
    width: fullLeft ? undefined : leftW ?? undefined,
    flex: fullLeft ? '1 1 0' : undefined,
    minWidth: SPLIT_LEFT_MIN_PX,
    overflow: 'auto',
    overflowX: 'hidden',
    // 折叠态不显示分隔线
    borderRight: fullLeft ? 'none' : `1px solid ${Colors.BORDER.LIGHT}`,
  }}
>
```

---

### Bug-14 [轻微] handleKeyDown缺少fullLeft防护

**问题位置**：`SplitPane.tsx:194-211`

```typescript
const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
  if (e.key === 'ArrowLeft') {
    // ...
  } else if (e.key === 'ArrowRight') {
    // ...
  }
}, [maxW]);
```

**问题**：
- 虽然分割线在 `fullLeft=true` 时不渲染，用户无法聚焦
- 但如果通过测试、refs 或直接调用，`handleKeyDown` 仍会执行
- 折叠态下 `setLeftW` 无意义（左列 flex 填满，不受 leftW 控制）

**违反规范**：
- **SRP**：handleKeyDown 应只处理展开态的调整逻辑

**修复方案**：
```typescript
const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
  if (fullLeft) return;  // ← 新增防护
  if (e.key === 'ArrowLeft') {
    e.preventDefault();
    setLeftW((w) => {
      const next = Math.max(SPLIT_LEFT_MIN_PX, (w ?? 0) - 16);
      writeStoredWidth(next);
      return next;
    });
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    setLeftW((w) => {
      const next = Math.min(maxW, (w ?? 0) + 16);
      writeStoredWidth(next);
      return next;
    });
  }
}, [fullLeft, maxW]);
```

---

### Bug-15 [轻微] 拖动时容器宽度变化导致计算错误

**问题位置**：`SplitPane.tsx:166-173`

```typescript
const containerW = container.offsetWidth;
const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);

const move = (ev: MouseEvent) => {
  const newW = Math.min(maxW, Math.max(SPLIT_LEFT_MIN_PX, w0 + ev.clientX - x0));
  // ...
};
```

**问题**：
- `maxW` 在 `mousedown` 时计算并捕获到闭包中
- 如果用户在拖动过程中调整浏览器窗口大小，`container.offsetWidth` 会变化
- 但 `move` 闭包中的 `maxW` 仍是旧值，导致计算错误
- 用户可能将面板拖出容器边界，或者无法拖到应有的最大宽度

**修复方案**：
```typescript
const move = (ev: MouseEvent) => {
  const currentContainerW = container.offsetWidth;  // ← 实时读取
  const currentMaxW = Math.round(currentContainerW * SPLIT_LEFT_MAX_RATIO);
  const newW = Math.min(currentMaxW, Math.max(SPLIT_LEFT_MIN_PX, w0 + ev.clientX - x0));
  lastWidthRef.current = newW;
  setLeftW(newW);
};
```

---

### Bug-16 [信息] 设计文档v1.1与实际代码脱节

**问题位置**：设计文档 `[49]` vs 实际代码 `SplitPane.tsx`

**文档描述**（`[49]` 第179-191行）：
```typescript
const getInitialWidth = (containerW: number, rightOpen: boolean): number => {
  if (containerW === 0) {
    return rightOpen ? 280 : 240;
  }
  if (rightOpen) {
    return Math.min(280, Math.round(containerW * 0.22));
  }
  return Math.min(240, Math.round(containerW * 0.18));
};
```

**实际代码**（`SplitPane.tsx:71-83`）：
```typescript
const getInitialWidth = (containerW: number): number => {
  const stored = readStoredWidth();
  if (stored !== null) {
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);
    return Math.min(stored, maxW);
  }
  if (containerW === 0) {
    return 300;  // ← 硬编码300，没有rightOpen参数
  }
  return Math.round(containerW * SPLIT_LEFT_DEFAULT_RATIO);  // ← 始终30%
};
```

**问题**：
- 文档明确描述 v1.1 实现了 rightOpen 调整，但代码实际没有
- 这是 Bug-1 的详细版本，但单独列出是因为文档本身也是问题源
- 文档中的代码示例与实际实现不一致，会误导后续维护者

**修复方案**：
- 方案A：实现文档描述的功能（推荐）
- 方案B：更新文档，说明实际行为是固定30%

---

### Bug-17 [低] 缺少触摸事件支持

**问题位置**：`SplitPane.tsx` 全局

**现状**：
- 代码只实现了 `mousedown/mousemove/mouseup` 事件
- 没有任何 `touchstart/touchmove/touchend` 处理

**违反规范**：
- **YAGNI**：设计文档"八、后续优化"明确列出"触摸支持"作为可选功能
- **关联检查**：现代 Web 应用应考虑移动端访问

**修复方案**：
```typescript
// 在 startDrag 中增加触摸支持
const startDrag = useCallback((e: React.MouseEvent | React.TouchEvent) => {
  e.preventDefault();
  const x0 = 'touches' in e ? e.touches[0].clientX : e.clientX;
  // ... 其余逻辑相同
}, [leftW]);

// 在 JSX 中添加 onTouchStart
<div
  role="separator"
  onMouseDown={startDrag}
  onTouchStart={startDrag}  // ← 新增
  // ...
/>
```

---

### Bug-18 [低] 缺少CSS过渡动画

**问题位置**：`SplitPane.tsx:235-248`

**现状**：
- 左面板宽度变化时无过渡动画
- 拖动时宽度即时变化，视觉上显得生硬

**违反规范**：
- **YAGNI**：设计文档"八、后续优化"明确列出"动画过渡"作为可选功能
- **用户体验**：无动画的宽度跳变可能让用户感到突兀

**修复方案**：
```typescript
// 方案A：添加过渡（拖动时禁用，避免卡顿）
<div
  style={{
    width: fullLeft ? undefined : leftW ?? undefined,
    flex: fullLeft ? '1 1 0' : undefined,
    minWidth: SPLIT_LEFT_MIN_PX,
    overflow: 'auto',
    overflowX: 'hidden',
    borderRight: fullLeft ? 'none' : `1px solid ${Colors.BORDER.LIGHT}`,
    transition: isDragging ? 'none' : 'width 0.2s ease',  // ← 新增
  }}
>

// 方案B：仅在非拖动时添加过渡
// 通过 isDragging state 控制
```

---

### Bug-7 [轻微] localStorage跨屏clamp后不写回

**问题位置**：`SplitPane.tsx:71-77`

```typescript
const getInitialWidth = (containerW: number): number => {
  const stored = readStoredWidth();
  if (stored !== null) {
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);
    return Math.min(stored, maxW);  // ← clamp但没有写回localStorage
  }
  // ...
};
```

**问题**：
- 用户在大屏拖到 800px，换小屏后 clamp 到 480px
- localStorage 仍存 800
- 下次打开还是 clamp 到 480
- 行为正确，但 localStorage 值与实际显示不一致

**是否需要修复**：
- 这实际上是**正确行为**——用户换回大屏后应该恢复 800px
- 如果写回 clamp 后的值，换回大屏后会丢失用户偏好
- **结论**：不修复，这是设计如此

**但需要添加注释说明**：
```typescript
// 注意：clamp后不写回localStorage——用户换回大屏时应恢复原偏好宽度
```

---

## 三、无Bug项确认

以下功能经分析确认**无bug**：

| 功能 | 验证结果 |
|------|---------|
| localStorage读写try/catch容错 | ✅ 隐私模式/配额满时静默失败 |
| 拖动mouse move防抖 | ✅ 仅mouseup时写一次，避免高频IO |
| lastWidthRef避免异步旧值 | ✅ ref同步更新，mouseup时读ref正确 |
| fullLeft折叠态布局 | ✅ flex:'1 1 0'填满，分割线不渲染 |
| 键盘←/→边界约束 | ✅ MIN_PX和maxW双重约束 |
| ResizeObserver清理 | ✅ useEffect return 中 disconnect |
| aria属性动态更新 | ✅ maxW用state管理，随resize更新 |
| 配置常量化 | ✅ constants/layout.ts 唯一定义点 |

---

## 四、修复优先级

| 优先级 | Bug | 影响 | 修复难度 |
|--------|-----|------|---------|
| P0 | Bug-1 文档功能未实现 | 用户需求未满足 | 低 |
| P1 | Bug-2 ResizeObserver比例计算 | 窗口缩放精度 | 中 |
| P1 | Bug-3 maxW初始值0 | 极端竞态 | 低 |
| P2 | Bug-4 handleDoubleClick防护 | 代码健壮性 | 低 |
| P2 | Bug-5 硬编码300无说明 | 可维护性 | 低 |
| P1 | Bug-6 测试不充分 | 回归风险 | 中 |
| P3 | Bug-7 localStorage跨屏 | 设计如此 | 无 |

---

## 五、修复代码（汇总）

### 5.1 SplitPane.tsx 修复

```typescript
// ===== 修复1: getInitialWidth增加rightOpen参数 (Bug-1, Bug-5) =====
const getInitialWidth = (containerW: number, rightOpen: boolean = true): number => {
  const stored = readStoredWidth();
  if (stored !== null) {
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);
    return Math.min(stored, maxW);
  }
  if (containerW === 0) {
    // 容器未布局完成：折叠态240px，展开态280px
    return rightOpen ? 280 : 240;
  }
  const ratio = rightOpen ? 0.22 : 0.18;
  const maxPX = rightOpen ? 280 : 240;
  return Math.min(maxPX, Math.round(containerW * ratio));
};

// ===== 修复2: maxW初始值 (Bug-3) =====
const SAFE_MAX_W = Math.round((typeof window !== 'undefined' ? window.innerWidth : 1024) * SPLIT_LEFT_MAX_RATIO);
const [maxW, setMaxW] = useState<number>(SAFE_MAX_W);

// ===== 修复3: ResizeObserver比例计算 (Bug-2) =====
const containerWRef = useRef<number>(0);
useEffect(() => {
  if (fullLeft) return;
  const container = containerRef.current;
  if (!container) return;
  const ro = new ResizeObserver((entries) => {
    const entry = entries[0];
    if (!entry) return;
    const newContainerW = entry.contentRect.width;
    if (newContainerW <= 0) return;
    setMaxW(Math.round(newContainerW * SPLIT_LEFT_MAX_RATIO));
    setLeftW((prev) => {
      if (prev === null) return getInitialWidth(newContainerW, rightOpen);
      const ratio = prev / (containerWRef.current || 1);
      containerWRef.current = newContainerW;
      const maxW = Math.round(newContainerW * SPLIT_LEFT_MAX_RATIO);
      return Math.min(Math.max(SPLIT_LEFT_MIN_PX, Math.round(newContainerW * ratio)), maxW);
    });
  });
  ro.observe(container);
  return () => ro.disconnect();
}, [fullLeft, rightOpen]);

// ===== 修复4: handleDoubleClick防护 (Bug-4) =====
const handleDoubleClick = useCallback(() => {
  if (fullLeft) return;
  clearStoredWidth();
  const container = containerRef.current;
  if (container) {
    setLeftW(getInitialWidth(container.offsetWidth, rightOpen));
  }
}, [fullLeft, rightOpen]);

// ===== 修复5: 接口扩展 (Bug-1) =====
interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  fullLeft?: boolean;
  rightOpen?: boolean;  // 新增
}
```

### 5.2 SessionLayout.tsx 修复

```typescript
// ===== 修复: 透传rightOpen (Bug-1) =====
<SplitPane
  left={renderSlot(panels, 'left')}
  fullLeft={!rightOpen}
  rightOpen={rightOpen}  // 新增
  right={...}
/>
```

### 5.3 测试补充（Bug-6）

见 Bug-6 修复方案中的测试代码。

---

## 六、规范符合性检查

| 规范 | 当前状态 | 说明 |
|------|---------|------|
| SRP | ✅ | SplitPane 只负责分割面板，不含业务逻辑 |
| DRY | ✅ | 拖动逻辑只写一次，复用 Files 页模式 |
| KISS-DIRECT | ⚠️ | Bug-2 修复后更直线 |
| SLAP | ✅ | UI层与业务层分离 |
| YAGNI | ⚠️ | Bug-1 修复后需求驱动 |
| 禁止backward | ✅ | 无向后兼容代码 |
| OCP | ✅ | 配置常量化支持扩展 |
| LSP | ✅ | 无继承体系 |
| ISP | ✅ | 接口职责单一 |
| 复用优先 | ✅ | 复用 constants/layout.ts |

---

## 七、后续行动

1. **P0**: 实现 Bug-1 修复（rightOpen 调整默认宽度）
2. **P1**: 实现 Bug-2 修复（ResizeObserver比例计算）
3. **P1**: 实现 Bug-3 修复（maxW初始值）+ 更新 Bug-10 测试断言
4. **P1**: 实现 Bug-8 修复（startDrag闭包陷阱）
5. **P1**: 实现 Bug-9 修复（fullLeft状态残留）
6. **P2**: 实现 Bug-4、Bug-5、Bug-11、Bug-12、Bug-13、Bug-14、Bug-15 修复
7. **P3**: 考虑实现 Bug-17、Bug-18（触摸支持、CSS动画）
8. **文档**: 更新 `[49]` 文档，同步代码实际行为

---

## 八、三遍复核结论（2026-10-27 17:20）

> 复核人：小欧 · 复核方法：①通读源码找bug ②对照测试断言验证 ③验证根因与严重性，共3遍独立复核。
> 测试验证：`npx vitest run SplitPane.test.tsx` → **17/17 通过**。

### 8.1 复核结果总表

| 编号 | 严重性 | 复核结论 | 关键证据（源码/测试/文档） |
|------|--------|---------|--------------------------|
| Bug-1 | **P0 严重** | ✅ **真实** | 文档[49]v1.1第181行有`getInitialWidth(containerW, rightOpen)`(240/280)，但`SplitPane.tsx:71-83`只有单参数返回固定30%/300；`SessionLayout.tsx:115`传`fullLeft={!rightOpen}`但**未传rightOpen** |
| Bug-16 | P1 | ✅ **真实** | 文档[49]v1.1描述rightOpen调整，代码无此参数——文档与代码脱节（Bug-1根因） |
| Bug-2 | P1 | ✅ **真实** | `SplitPane.tsx:140` ratio分母用`container.offsetWidth`，分子用`entry.contentRect.width`——两个不同来源尺寸混用，有border/滚动条时比例失真 |
| Bug-6 | P1 | ✅ **真实** | 测试`SplitPane.test.tsx`无拖动(mousedown/move/up)用例、无ResizeObserver用例；双击只验证localStorage清除(第206行)未验证宽度重置 |
| Bug-10 | P1 | ⚠️ **部分修复** | v1.4键盘断言已增强为验证localStorage写入(第97-102行)，但**仍未验证DOM实际宽度**；且键盘→测试写死`expect(finalVal).toBe(0)`(第133行)——Bug-3记录性测试，修复Bug-3后必失败 |
| Bug-3 | P2(降) | ✅ **真实但低概率** | `maxW=useState(0)`(第106行)；客户端useLayoutEffect首帧同步执行几乎不可触发，SSR/JSDOM触发。测试第126-133行确认 |
| Bug-5 | P2 | ✅ **真实** | `containerW=0`返回硬编码300(第80行)无注释；且与有stored时返回0不一致 |
| Bug-8 | P2(降) | ✅ **真实但低概率** | `startDrag`闭包捕获`w0/maxW`(第161-167行)，拖动中其他操作改leftW产生竞态；`fullLeft`切换不清理拖动状态——但正常拖动无害 |
| Bug-15 | P3 | ✅ **真实但低概率** | `move`闭包捕获mousedown时`maxW`(第167行)，拖动中窗口resize会用旧值 |
| Bug-13 | P3 | ✅ **真实(逻辑不一致)** | `fullLeft`时分割线隐藏(`!fullLeft`第252行)但`borderRight`始终渲染(第244行)——视觉逻辑不一致；测试第285行断言borderRight存在（与Bug-13建议矛盾） |
| Bug-11 | P3 | ⚠️ **设计权衡** | `MAX_RATIO=0.80`左侧最大80%；是否bug取决于产品对右侧最小空间的需求，非确定bug |
| Bug-19 | **新增** | ✅ **真实** | `getInitialWidth`: `containerW=0`且有stored时`Math.min(stored, 0)=0`(第75-76行)，而非偏好值——与无stored返回300不一致 |

### 8.2 非Bug / 设计如此 / 可选增强

| 编号 | 复核结论 | 理由 |
|------|---------|------|
| Bug-7 | ❌ **非Bug(设计如此)** | clamp后不写回localStorage是正确行为——用户换回大屏应恢复原偏好宽度 |
| Bug-9 | ❌ **降级为代码质量** | `fullLeft`时leftW/maxW残留但**不参与渲染**(width:undefined+flex填满)，切回false时useLayoutEffect重新计算，无用户可见影响 |
| Bug-12 | ❌ **= Bug-3 重复** | 与Bug-3根因相同(maxW=0)，应合并，不单独计 |
| Bug-4 | ⚠️ **防御性(低)** | `fullLeft`时不渲染分割线，用户无法触发onDoubleClick；仅测试/ref直接调用才触发 |
| Bug-14 | ⚠️ **防御性(低)** | 同Bug-4，`fullLeft`时分割线不渲染，键盘无法聚焦触发 |
| Bug-17 | ❌ **可选增强** | 文档[49]"八、后续优化"明确列为**可选**触摸支持 |
| Bug-18 | ❌ **可选增强** | 文档[49]"八、后续优化"明确列为**可选**动画过渡 |

### 8.3 复核后结论

- **确认真实Bug：12个**（Bug-1/2/3/5/6/8/10/13/15/16/19，其中Bug-11为设计权衡、Bug-10部分修复）
- **非Bug/可选：7个**（Bug-4/7/9/12/14/17/18，其中Bug-4/14为防御性、Bug-12合并入Bug-3）
- **新增遗漏：Bug-19**（getInitialWidth在containerW=0且有用户偏好时返回0，逻辑缺陷）
- **优先级调整**：Bug-3从P1降为P2（客户端首帧同步，用户几乎不可触发）；Bug-8从P1降为P2（正常拖动无害）；Bug-17/18维持"可选"不入修复队列

### 8.5 用户实测反馈：双击分割线语义与期望相反（2026-10-27 17:25 追加）

> 来源：用户实测反馈"双击后跳回到旧的默认值，不是设置新的位置为默认值"。

**问题现象**：
用户把分割线拖到某个位置（如 450px），双击分割线后，宽度**跳回 30% 出厂默认**（约 300px），而不是保持当前 450px 并把它设为新的默认值。

**当前实现**（`SplitPane.tsx:215-221`）：
```typescript
const handleDoubleClick = useCallback(() => {
  clearStoredWidth();               // ① 清除 localStorage
  const container = containerRef.current;
  if (container) {
    setLeftW(getInitialWidth(container.offsetWidth));  // ② stored=null → 返回 containerW*0.30 = 30%
  }
}, []);
```
双击后：`clearStoredWidth()` 清空偏好 → `getInitialWidth()` 读不到 stored → 走 `containerW * SPLIT_LEFT_DEFAULT_RATIO` 分支 → 返回 **30% 出厂默认** → `setLeftW(30%)` → 宽度跳回 30%。

**设计意图**（设计文档 [49] v1.2 第 247-252 行）：
- 双击 = "清除 localStorage + 重置为默认 30%"，用途"用户拖坏了/想回到初始状态，一键回滚"
- 即设计意图是**「重置为旧默认」**（回滚），不是「设置为新默认」

**用户期望**：
- 双击 = **保持当前宽度** + 把当前宽度**设为新的默认值**（以后打开/重置都回到这个宽度）

**结论：真实功能缺陷（语义相反）** ⚠️
- 当前实现与设计文档 [49] 一致（都是「重置为旧默认 30%」），**但与用户实际期望相反**
- 用户需要的是「设置为新默认」（把当前宽度固定为默认），代码却是「重置为旧默认」（跳回 30%）
- **根因**：设计文档 v1.2 把双击定义为"回滚重置"，而用户真实需求是"把当前设为默认"——**设计语义与用户需求脱节**

**修复方案（方案A，符合用户期望）**：
```typescript
const handleDoubleClick = useCallback(() => {
  // 改为: 把当前宽度设为新的默认值(持久化), 保持当前宽度不跳回
  const container = containerRef.current;
  if (container) {
    const cur = leftW ?? getInitialWidth(container.offsetWidth);  // 当前宽度(若未初始化则用初始值)
    writeStoredWidth(cur);   // ① 写回 localStorage 作为新的持久化默认
    setLeftW(cur);           // ② 保持当前宽度, 不跳回 30%
  }
}, [leftW]);
```
- 效果：双击后宽度**保持不变**，且该宽度被持久化为默认——符合"设置新的位置为默认值"
- 需要同步更新：title/aria-label 提示文案从"双击重置为默认"改为"双击设为默认宽度"；测试「双击清除 localStorage」断言需改为「双击写入 localStorage」

**备选方案B（保持设计，明确提示）**：
- 维持"重置为 30%"，但 title/aria 明确提示"双击重置为出厂默认 30%"，消除用户误解

**是否需要修复**：
- 若用户需求确为"设置新默认"→ 方案A（推荐）
- 若用户接受"重置为出厂默认"→ 方案B
- 需与用户确认期望后再定，但用户表述已明确倾向方案A

**修复状态：✅ 已按方案A实施（2026-10-27 17:31）**
- 用户确认采用方案A。已修改 `SplitPane.tsx`：
  - `handleDoubleClick`：改为 `writeStoredWidth(cur) + setLeftW(cur)`，双击后保持当前宽度并写入 localStorage 作为新默认（依赖 `[leftW]`）
  - title/aria-label 文案：`"双击重置为默认"` → `"双击设为默认宽度"`
  - 删除死代码 `clearStoredWidth`（无调用点，按 YAGNI）
  - **顺带修复 Bug-19**：`getInitialWidth` 在 `containerW<=0` 且有 stored 时返回偏好值而非 0（否则首帧 offsetWidth=0 时把左宽设 0，双击写回 0）
- 已更新 `SplitPane.test.tsx`（v1.5）：双击断言从"清除 localStorage"改为"写入 localStorage + aria-valuenow 保持 450"
- **测试验证：17/17 通过**

**✅ 扩展（2026-10-27 17:47）：默认值双向管理（设计文档 [51]）**
- 用户确认方案：**双击=存储新默认，Shift+双击=返回出厂默认**
- `handleDoubleClick` 增加 `e.shiftKey` 区分：
  - 双击：当前宽度写入 localStorage 作为新默认（保持 v1.4 行为）
  - Shift+双击：`clearStoredWidth()` + 重置为 30% 出厂默认
- 重新引入 `clearStoredWidth`（v1.4 删除，现 Shift+双击需要）
- title/aria-label 文案：增加"Shift+双击返回出厂默认"
- **测试验证：19/19 通过**（新增 2 个 Shift+双击用例）

### 8.4 后续行动更新

1. **P0**: 实现 Bug-1 修复（rightOpen 调整默认宽度）+ 同步 Bug-16 文档
2. **P1**: 实现 Bug-2 修复（ResizeObserver 比例计算统一来源）
3. **P1**: 实现 Bug-6/Bug-10 测试增强（补拖动/RO/双击宽度用例；Bug-3修复后更新键盘→断言为>300）
4. **P2**: 实现 Bug-3/Bug-5/Bug-8/Bug-13/Bug-15/Bug-19 修复（maxW安全默认、300常量化、容器宽实时读、borderRight条件化、containerW=0+stored返回偏好）
5. **P3**: Bug-11 设计权衡——与产品确认右侧最小空间需求后再定
6. **可选**: Bug-17/Bug-18（触摸/动画）作为后续增强，不入当前修复队列

---

*编写人：小欧 · 2026-10-27 17:05*
