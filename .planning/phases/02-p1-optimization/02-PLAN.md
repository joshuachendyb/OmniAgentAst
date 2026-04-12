# Phase 2: P1级优化 - React.memo + useMemo - PLAN

**Phase:** 02-p1-optimization  
**Created:** 2026-04-12  
**Status:** Ready for execution

## Objective

实现P1级优化：减少不必要重渲染，提升运行时性能
- MessageItem React.memo 优化
- 消息列表 useMemo 优化

## Context

详见 `02-CONTEXT.md`

## Implementation Tasks

### Task 1: MessageItem 添加 React.memo

**Objective:** 为 MessageItem 组件添加 memo 包装，减少不必要的重渲染

**Files to modify:**
- `frontend/src/components/Chat/MessageItem.tsx`

**Read first:**
- `frontend/src/components/Chat/MessageItem.tsx` - 现有组件实现

**Action:**
1. 导入 React.memo
2. 创建自定义比较函数 `areMessageItemPropsEqual`：
   ```typescript
   const areMessageItemPropsEqual = (prev: MessageItemProps, next: MessageItemProps) => {
     return (
       prev.content === next.content &&
       prev.role === next.role &&
       prev.timestamp === next.timestamp &&
       prev.showExecution === next.showExecution &&
       prev.sessionId === next.sessionId &&
       prev.sessionTitle === next.sessionTitle
     );
   };
   ```
3. 使用 memo 包装组件：
   ```typescript
   export const MessageItem = memo(({ ...props }: MessageItemProps) => {
     // ... component implementation
   }, areMessageItemPropsEqual);
   ```

**Acceptance Criteria:**
- [ ] MessageItem 使用 React.memo 包装
- [ ] 自定义比较函数正确比较关键属性
- [ ] 使用 memo 导出组件

---

### Task 2: NewChatContainer 消息列表 useMemo 优化

**Objective:** 使用 useMemo 缓存消息列表渲染，避免每次渲染都重新计算

**Files to modify:**
- `frontend/src/components/Chat/NewChatContainer.tsx`

**Read first:**
- `frontend/src/components/Chat/NewChatContainer.tsx` - 现有消息列表渲染逻辑

**Action:**
1. 找到消息列表渲染位置
2. 使用 useMemo 包装消息列表计算：
   ```typescript
   const messageList = useMemo(() => {
     return messages.map((msg, index) => (
       <MessageItem
         key={msg.id || index}
         content={msg.content}
         role={msg.role}
         timestamp={msg.timestamp}
         showExecution={msg.showExecution}
         sessionId={sessionId}
         sessionTitle={sessionTitle}
       />
     ));
   }, [messages, showExecution, sessionId, sessionTitle]);
   ```
3. 精确设置依赖数组：`[messages, showExecution, sessionId, sessionTitle]`

**Acceptance Criteria:**
- [ ] 消息列表使用 useMemo 包装
- [ ] 依赖数组正确包含所有必要依赖
- [ ] 组件能正确渲染消息列表

---

### Task 3: 性能验证 - React DevTools Profiler

**Objective:** 使用 React DevTools Profiler 验证优化效果

**Verification:**
1. 打开 React DevTools Profiler
2. 记录优化前的渲染次数
3. 执行优化后再次记录
4. 对比渲染次数变化

**Acceptance Criteria:**
- [ ] 能正常启动应用
- [ ] Profiler 能够连接
- [ ] 记录渲染次数对比

---

### Task 4: 回归测试

**Objective:** 确保优化没有破坏现有功能

**Verification:**
1. 消息发送功能正常
2. 消息显示正确
3. 会话切换正常
4. 标题显示正确

**Acceptance Criteria:**
- [ ] 所有消息相关功能正常工作
- [ ] 无新增警告或错误

---

## Dependencies

- React 18 (memo, useMemo)
- React DevTools (性能验证)

## Notes

- 优化目标：减少不必要的 Virtual DOM 对比
- Phase 1 骨架屏已就位，可以观察重渲染问题
- 比较函数要精确，避免遗漏关键属性导致显示错误