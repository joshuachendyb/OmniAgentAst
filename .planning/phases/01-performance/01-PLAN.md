# Phase 1: P0级优化-骨架屏 - PLAN

**Phase:** 01-performance  
**Created:** 2026-04-12  
**Status:** Ready for execution

## Objective

实现骨架屏(Skeleton Screen)替换空白屏幕，解决启动加载慢导致的首屏空白问题。

## Context

详见 `01-CONTEXT.md`

## Implementation Tasks

### Task 1: 创建骨架屏组件目录和基础结构

**Objective:** 创建 Skeleton 组件目录和导出文件

**Files to create:**
- `frontend/src/components/Skeleton/` - 骨架屏组件目录
- `frontend/src/components/Skeleton/index.ts` - 组件导出

**Action:**
1. 创建目录 `frontend/src/components/Skeleton/`
2. 创建 `index.ts` 导出文件

**Acceptance Criteria:**
- [ ] Skeleton 目录存在
- [ ] index.ts 导出 LayoutSkeleton 和 MessageListSkeleton

---

### Task 2: 实现 LayoutSkeleton 组件

**Objective:** 实现 Layout 骨架屏组件，复现 Layout 的 Header + Sider + Content 结构

**Files to create:**
- `frontend/src/components/Skeleton/LayoutSkeleton.tsx`
- `frontend/src/components/Skeleton/LayoutSkeleton.module.css`

**Read first:**
- `frontend/src/components/Layout/index.tsx` - 获取实际 UI 参数

**Action:**
1. 使用 Ant Design Skeleton 组件实现
2. Header 骨架：高度 43px，padding 0 20px
3. Sider 骨架：宽度 180px，Logo 区域 64px
4. Content 骨架：占满剩余空间
5. 动画：1s shimmer 闪烁效果（Ant Design 默认）

**UI Parameters (from CONTEXT.md):**
- Sider 宽度：180px
- Header 高度：43px
- Header padding：0 20px
- Logo 区域高度：64px
- Content margin：无（无间距）

**Acceptance Criteria:**
- [ ] LayoutSkeleton.tsx 存在并使用 Ant Design Skeleton
- [ ] LayoutSkeleton.module.css 样式与 Layout 一致
- [ ] 包含 Header、Sider、Content 三个骨架区域
- [ ] 闪烁动画时长 1s

---

### Task 3: 实现 MessageListSkeleton 组件

**Objective:** 实现消息列表骨架屏，使用"全像法"模拟真实消息结构

**Files to create:**
- `frontend/src/components/Skeleton/MessageListSkeleton.tsx`

**Action:**
1. 模拟真实消息结构（头像、用户名、时间、内容）
2. 显示 3-5 条消息占位符
3. 使用 Ant Design Skeleton 组件

**Acceptance Criteria:**
- [ ] MessageListSkeleton.tsx 存在
- [ ] 模拟 3-5 条消息结构
- [ ] 包含头像、用户名、时间、内容区域

---

### Task 4: 集成骨架屏到 Layout 组件

**Objective:** 在 Layout/index.tsx 中添加骨架屏显示逻辑

**Files to modify:**
- `frontend/src/components/Layout/index.tsx`

**Read first:**
- `frontend/src/components/Layout/index.tsx`

**Action:**
1. 在内容区渲染前显示骨架屏
2. 切换时机：200ms（AppContext 初始化完成后）
3. 失败处理：显示错误提示 + 重试按钮
4. 状态管理：loading / error / content

**Acceptance Criteria:**
- [ ] Layout 显示骨架屏等待状态
- [ ] 200ms 后切换到实际内容
- [ ] 加载失败时显示错误 + 重试按钮

---

### Task 5: 集成骨架屏到 NewChatContainer

**Objective:** 在 NewChatContainer.tsx 中添加消息列表骨架屏

**Files to modify:**
- `frontend/src/components/Chat/NewChatContainer.tsx`

**Read first:**
- `frontend/src/components/Chat/NewChatContainer.tsx`

**Action:**
1. 消息列表区域显示骨架屏
2. 加载完成后切换到实际消息

**Acceptance Criteria:**
- [ ] 消息列表区域显示骨架屏
- [ ] 数据加载后显示实际内容

---

### Task 6: 验证和测试

**Objective:** 验证骨架屏功能正常工作

**Verification:**
1. 启动应用，观察首屏是否显示骨架屏而非空白
2. 等待 200ms 后是否正常切换
3. 模拟加载失败，验证错误提示和重试按钮
4. 检查样式是否与现有 Layout 一致

## Dependencies

- Ant Design 5 Skeleton 组件
- React 18

## Notes

- UI 必须与现有 Layout 完全一致
- 切换时机：200ms
- 失败显示：错误提示 + 重试按钮
- 动画时长：1s