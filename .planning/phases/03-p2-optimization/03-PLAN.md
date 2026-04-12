# Phase 3: P2级优化 - Bundle代码分割 + 初始化时序 - PLAN

**Phase:** 03-p2-optimization  
**Created:** 2026-04-12  
**Status:** Ready for execution

## Objective

实现P2级优化：Bundle代码分割减少首屏大小 + 初始化时序优化协调应用启动流程

## Context

详见 `03-CONTEXT.md`

## Implementation Tasks

### Task 1: 配置 Vite Bundle 代码分割

**Objective:** 修改 vite.config.ts 添加 manualChunks 配置

**Files to modify:**
- `frontend/vite.config.ts`

**Read first:**
- `frontend/vite.config.ts` - 现有配置

**Action:**
1. 在 `build` 对象中添加 `rollupOptions`
2. 配置 `manualChunks` 分割策略：
   - `react-vendor`: ['react', 'react-dom', 'react-router-dom']
   - `antd-vendor`: ['antd']
   - `utils-vendor`: ['axios', 'dayjs']
3. 设置 `cssCodeSplit: true`
4. 设置 `chunkSizeWarningLimit: 500`

**Acceptance Criteria:**
- [ ] vite.config.ts 包含 rollupOptions 配置
- [ ] manualChunks 包含三个vendor chunk
- [ ] cssCodeSplit: true 已设置

---

### Task 2: App.tsx 添加 Lazy 加载

**Objective:** 修改 App.tsx 使用 Suspense + lazy 加载路由

**Files to modify:**
- `frontend/src/App.tsx`

**Read first:**
- `frontend/src/App.tsx` - 现有路由配置

**Action:**
1. 导入 `Suspense`, `lazy` from React
2. 将 History 和 Settings 改为 lazy 导入：
   ```typescript
   const HistoryPage = lazy(() => import('./pages/History'));
   const Settings = lazy(() => import('./pages/Settings'));
   ```
3. 使用 Suspense 包装 Routes：
   ```typescript
   <Suspense fallback={<div>加载中...</div>}>
     <Routes>...</Routes>
   </Suspense>
   ```

**Acceptance Criteria:**
- [ ] History 页面使用 lazy 导入
- [ ] Settings 页面使用 lazy 导入
- [ ] Suspense fallback 显示加载状态

---

### Task 3: 创建 useInitializationProgress Hook

**Objective:** 创建初始化时序管理 hook

**Files to create:**
- `frontend/src/hooks/useInitializationProgress.ts`

**Action:**
1. 创建接口定义：
   ```typescript
   interface InitializationProgress {
     layoutReady: boolean;
     chatDataReady: boolean;
     isReady: boolean;
     phase: 'initializing' | 'loading-layout' | 'loading-chat' | 'ready';
   }
   ```
2. 实现 hook：
   - 接收 `appInitialized`, `sessionLoaded` 参数
   - 200ms 延迟后设置 layoutReady
   - sessionLoaded 后设置 chatDataReady
   - 返回完整状态对象

**Acceptance Criteria:**
- [ ] hook 文件创建成功
- [ ] 返回 layoutReady, chatDataReady, isReady, phase 四个状态
- [ ] phase 枚举包含四个状态

---

### Task 4: Layout 组件集成 useInitializationProgress

**Objective:** 在 Layout 中使用初始化时序 hook

**Files to modify:**
- `frontend/src/components/Layout/index.tsx`

**Read first:**
- `frontend/src/components/Layout/index.tsx`

**Action:**
1. 导入 useInitializationProgress hook
2. 从 AppContext 获取 appInitialized, sessionLoaded 状态
3. 使用 hook 获取初始化进度
4. 根据 phase 状态显示不同 UI

**Acceptance Criteria:**
- [ ] Layout 导入并使用 hook
- [ ] 根据 phase 显示不同加载状态
- [ ] 验证无竞态条件

---

### Task 5: 验证 Bundle 分割效果

**Objective:** 验证配置正确性和分割效果

**Verification:**
1. 运行 `npm run build` 查看分割结果
2. 检查输出文件：
   - `react-vendor-*.js`
   - `antd-vendor-*.js`
   - `utils-vendor-*.js`
3. 测量首屏bundle大小减少比例

**Acceptance Criteria:**
- [ ] 构建成功，无报错
- [ ] 生成了分割的chunk文件
- [ ] 首屏bundle减少约50%

---

### Task 6: 验证初始化时序

**Objective:** 验证初始化hook工作正常，无竞态条件

**Verification:**
1. 启动应用，观察初始化流程
2. 验证 phase 状态正确转换：
   - initializing → loading-layout → loading-chat → ready
3. 200ms后 layoutReady 变为 true
4. sessionLoaded 后 chatDataReady 变为 true

**Acceptance Criteria:**
- [ ] 无竞态条件
- [ ] 状态转换正确
- [ ] UI显示与状态同步

---

## Dependencies

- React 18 (lazy, Suspense, useState, useEffect)
- Vite (rollupOptions, manualChunks)
- Ant Design 5

## Notes

- Bundle分割目标：首屏减少50%
- 初始化时序：消除竞态条件，确保UI状态一致
- 前置依赖：Phase 1 骨架屏已完成