# Phase 3: P2级优化 - Bundle代码分割 + 初始化时序 - Context

**Gathered:** 2026-04-12
**Status:** Ready for planning

<domain>
## Phase Boundary

第三阶段：P2级优化（中期实施）
- Bundle代码分割：减少首屏bundle大小
- 初始化时序优化：协调应用初始化流程

**前置依赖**：第一阶段完成（骨架屏已实施）

</domain>

<decisions>
## Implementation Decisions

### Bundle分割策略
- **D-01:** 使用 manualChunks 配置手动分割
- **D-02:** `react-vendor`: react, react-dom, react-router-dom
- **D-03:** `antd-vendor`: antd
- **D-04:** `utils-vendor`: axios, dayjs
- **D-05:** cssCodeSplit: true
- **D-06:** chunkSizeWarningLimit: 500

### Lazy加载路由选择
- **D-07:** History页面 - lazy加载
- **D-08:** Settings页面 - lazy加载
- **D-09:** 使用 Suspense 包装，fallback 显示加载中

### 初始化时序Hook设计
- **D-10:** 创建 useInitializationProgress hook
- **D-11:** 返回状态：layoutReady, chatDataReady, isReady, phase
- **D-12:** phase枚举：initializing | loading-layout | loading-chat | ready
- **D-13:** 200ms 延迟后设置 layoutReady

### the agent's Discretion
- 具体CSS样式实现
- 竞态条件测试验证方法
- fallback loading 界面设计

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Vite配置
- `frontend/vite.config.ts` — Vite构建配置，需要添加rollupOptions

### App入口
- `frontend/src/App.tsx` — 主应用入口，需要添加Suspense和lazy

### Hook目录
- `frontend/src/hooks/` — 新建useInitializationProgress.ts

### 相关优化文档
- `doc-4月优化/版本V0.8.98前端性能问题分析与优化方案-小资-2026-0412.md` §5.5 — 第三阶段详细方案

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Ant Design Layout组件：已用于现有Layout
- React Suspense + lazy：React原生支持

### Established Patterns
- Vite项目：使用rollupOptions.output.manualChunks
- React Hooks：useState, useEffect模式

### Integration Points
- vite.config.ts: 添加build.rollupOptions
- App.tsx: Suspense包装Routes，lazy()导入组件
- Layout组件: 使用useInitializationProgress hook

</code_context>

<specifics>
## Specific Ideas

- Bundle目标：首屏减少50%
- 初始化时序：消除竞态条件，确保UI状态一致

</specifics>

<deferred>
## Deferred Ideas

- 问题2：标题编辑无反应 — 第二阶段已包含
- 问题3：消息显示慢 — 第二阶段已包含

</deferred>

---

*Phase: 03-p2-optimization*
*Context gathered: 2026-04-12*