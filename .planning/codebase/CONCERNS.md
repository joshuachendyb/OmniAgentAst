# CONCERNS.md - Technical Debt & Concerns

## Known Performance Issues

### Frontend Performance

1. **启动加载慢** - 页面空白问题
   - 位置: `frontend/src/components/Layout/index.tsx`
   - 状态: 优化中 (2026-04)

2. **标题编辑无反应** - 交互延迟
   - 位置: NewChatContainer 或 MessageItem
   - 状态: 待优化

3. **消息显示慢** - 渲染性能
   - 位置: MessageItem 组件
   - 状态: 待优化

## Technical Debt

### Code Quality

- 部分组件代码可以进一步优化
- 缺少部分单元测试覆盖率

### Architecture

- 可以进一步解耦模块依赖
- 预处理流程可以更灵活

## Security Considerations

- Shell 命令执行有安全限制
- 文件操作有安全检查
- API 有认证机制

## Performance Notes

- SSE 流式传输用于实时消息
- SQLite 数据库用于本地存储版
- 前端使用 Vite 快速构建

---

**Created**: 2026-04-12
**Focus**: concerns