# 错误日志分析报告

**分析时间**: 2026-02-26 19:35:21
**分析文件数**: 6

## 摘要统计

- **总错误数**: 488
- **总警告数**: 0

## 按错误类型分类

| 错误类型 | 数量 |
|----------|------|
| HTTP错误 | 180 |
| 文件错误 | 180 |
| 其他错误 | 112 |
| 验证错误 | 16 |

## 每日错误统计

| 日期 | 错误数 |
|------|--------|
| 2026-02-20 | 134 |
| 2026-02-21 | 74 |
| 2026-02-22 | 76 |
| 2026-02-23 | 69 |
| 2026-02-25 | 79 |
| 2026-02-26 | 56 |

## 日志级别统计

| 级别 | 数量 |
|------|------|
| ERROR | 488 |
| INFO | 4954 |
| WARNING | 617 |

## 最近的错误（最新文件）

1. **2026-02-26 19:21:02,356** - Operation not found for rollback: test-op-id
2. **2026-02-26 19:21:02,394** - Validation Error: [{'loc': ('query', 'session_id'), 'msg': 'field required', 'type': 'value_error.missing'}]
3. **2026-02-26 19:21:02,400** - Validation Error: [{'loc': ('query', 'format'), 'msg': "unexpected value; permitted: 'txt', 'json', 'html', 'mmd'", 'type': 'value_error.const', 'ctx': {'given': 'invalid', 'permitted': ('txt', 'json', 'html', 'mmd')}}]
4. **2026-02-26 19:21:02,725** - Validation Error: [{'loc': ('body', 'version'), 'msg': 'field required', 'type': 'value_error.missing'}]
5. **2026-02-26 19:21:02,764** - HTTP Exception: 400 - 会话ID列表不能为空
6. **2026-02-26 19:21:02,769** - HTTP Exception: 400 - 最多一次查询100个会话
7. **2026-02-26 19:21:02,779** - Validation Error: [{'loc': ('body', 'version'), 'msg': 'field required', 'type': 'value_error.missing'}]
8. **2026-02-26 19:21:02,798** - Validation Error: [{'loc': ('body', 'version'), 'msg': 'field required', 'type': 'value_error.missing'}]
9. **2026-02-26 19:21:02,842** - Validation Error: [{'loc': ('body', 'version'), 'msg': 'field required', 'type': 'value_error.missing'}]
10. **2026-02-26 19:21:03,725** - Session not found: test-session
