# Phase 1: 前端性能优化 - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

优化前端性能，解决启动加载慢导致的首屏空白问题。包括 Layout 骨架屏和消息列表骨架屏的实现。

</domain>

<decisions>
## Implementation Decisions

### 覆盖范围
- **Layout骨架屏**：Header + Sider + Content 三个区域都需要骨架占位
- **消息列表骨架屏**：消息列表区域也需要骨架占位显示

### UI样式
- **与现有Layout完全一致**：严格复用Layout的UI参数
  - Sider宽度：180px
  - Header高度：43px
  - Header padding：0 20px
  - Logo区域高度：64px
  - Content margin：无（无间距）

### 动画效果
- **闪烁动画**：使用Ant Design默认的shimmer闪烁效果（Skeleton组件自带）

### Claude's Discretion
- 具体的CSS动画参数（时长、缓动函数）
- 骨架屏颜色微调
- 错误状态的处理方式

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Layout组件
- `frontend/src/components/Layout/index.tsx` — 主布局组件（843行），获取实际UI参数

### 创建的骨架屏组件
- `frontend/src/components/Skeleton/LayoutSkeleton.tsx` — Layout骨架屏组件
- `frontend/src/components/Skeleton/LayoutSkeleton.module.css` — Layout骨架屏样式
- `frontend/src/components/Skeleton/MessageListSkeleton.tsx` — 消息列表骨架屏
- `frontend/src/components/Skeleton/index.ts` — 组件导出

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Ant Design Skeleton 组件：已可用于骨架屏实现
- Layout组件：使用 Ant Design Layout 组件族

### Established Patterns
- Layout组件使用 Ant Design 5 的 Layout 组件
- CSS使用CSS Modules（.module.css）

### Integration Points
- Layout/index.tsx: 在内容区渲染前显示骨架屏
- NewChatContainer.tsx: 在消息列表区域显示骨架屏

</code_context>

<specifics>
## Specific Ideas

- 首屏加载时间目标：< 500ms 骨架屏显示
- UI必须与现有Layout完全一致，包括颜色、间距、圆角等
- 消息列表骨架屏使用"全像法"（模拟真实消息结构）

</specifics>

<deferred>
## Deferred Ideas

- 问题2：标题编辑无反应 —  Future phase
- 问题3：消息显示慢 — Future phase

</deferred>

---

*Phase: 01-performance*
*Context gathered: 2026-04-12*