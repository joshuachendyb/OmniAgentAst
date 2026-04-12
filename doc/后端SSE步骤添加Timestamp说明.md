# 后端 SSE 步骤 Timestamp 添加说明

**创建时间**: 2026-03-18 10:00:00  
**编写人**: 小沈  
**适用**: 前端开发 - 小强

---

## 一、修改背景

后端给所有 SSE 步骤都添加了统一的 `timestamp` 字段，格式为**毫秒时间戳**（如 `1773742493000`）。

前端不再需要自己添加 timestamp，直接使用后端返回的值即可。

---

## 二、后端 timestamp 字段添加位置

| 步骤类型 | 字段名 | 格式 | 示例 |
|----------|--------|------|------|
| start | timestamp | 毫秒 | 1773742493000 |
| thought | timestamp | 毫秒 | 1773742493000 |
| action_tool | timestamp | 毫秒 | 1773742493000 |
| observation | timestamp | 毫秒 | 1773742493000 |
| chunk | timestamp | 毫秒 | 1773742493000 |
| final | timestamp | 毫秒 | 1773742493000 |
| error | timestamp | 毫秒 | 1773742493000 |
| incident | timestamp | 毫秒 | 1773742493000 |

---

## 三、前端需要修改的地方

### 3.1 MessageItem.tsx

**文件**: `frontend/src/pages/chat/components/MessageItem.tsx`

**修改**: 直接使用后端的 `timestamp` 字段，不要自己生成。

找到类似这样的代码：
```typescript
// 之前（删除）
timestamp: formatTimestamp(...)
```

改为：
```typescript
// 之后（直接使用后端的timestamp）
timestamp: formatTimestamp(step.timestamp)  // step.timestamp 已经是后端返回的毫秒时间戳
```

### 3.2 导出逻辑检查

**文件**: `frontend/src/services/chatService.ts` 或相关导出模块

**检查**: 确认导出时使用后端的 `timestamp` 字段。

---

## 四、时间戳格式说明

| 项目 | 值 |
|------|-----|
| 格式 | 毫秒时间戳 |
| 示例 | `1773742493000` |
| 转换 | 前端 `formatTimestamp()` 可以直接处理 |

前端 `formatTimestamp` 支持：
- 数字：`1773742493000` → 自动转换
- 字符串：`"1773742493000"` → 自动转换

---

## 五、验证方法

1. 发起新对话
2. 检查 network 中后端返回的 SSE 数据是否包含 `timestamp` 字段
3. 检查前端显示的时间戳是否正确

---

**更新时间**: 2026-03-18 10:00:00
