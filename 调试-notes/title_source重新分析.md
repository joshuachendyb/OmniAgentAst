## title_source 问题重新分析

**执行时间**: 2026-03-02

---

## 问题发现

### 1. 后端 `update_session` 响应不包含 `title_locked`

**位置**：`backend/app/api/v1/sessions.py` 第848-852行

```python
return {
    "success": True,
    "title": update_data.title,
    "version": new_version
    # ❌ 缺少 title_locked 字段
}
```

### 2. 前端在用户修改标题后只更新了 `titleSource`，没有更新 `titleLocked`

**位置**：`frontend/src/components/Chat/NewChatContainer.tsx` 第1460-1461行

```typescript
setSessionTitle(titleInput.trim());
setTitleSource("user"); // ⭐ 标记为用户修改
// ❌ 缺少：setTitleLocked(true)
```

### 3. 导致的问题

- 用户修改标题后，`titleSource` 被设置为 `"user"`
- 但 `titleLocked` 没有被更新
- 后端在 `getSessionMessages` 中返回 `title_source = 'user' if title_locked else 'auto'`
- 如果 `titleLocked` 不是 `true`，`title_source` 会被计算为 `"auto"`
- 导致 UI 显示不一致

---

## 修复方案

### 方案A：删除 `titleSource` 状态，直接使用 `titleLocked`

**优点**：
- 不需要维护两套状态
- 简单直接

**缺点**：
- 需要修改多处代码

**具体修改**：
1. 删除 `titleSource` 状态定义（第108行）
2. 删除所有 `setTitleSource` 调用（第592、852、962、1051、1468行）
3. 修改 UI 显示逻辑（第1497-1504行）

### 方案B：保留 `titleSource` 状态，但在用户修改标题时同时更新 `titleLocked`

**优点**：
- 不需要大幅修改 UI 显示逻辑
- 两套状态更清晰

**缺点**：
- 需要维护两套状态的同步

**具体修改**：
1. 在第1461行添加 `setTitleLocked(true)`
2. 其他保持不变

---

## 方案选择

**选择**：方案A（删除 `titleSource` 状态）

**原因**：
1. `title_source` 本质上是 `title_locked` 的派生状态
2. 维护两套状态容易导致不一致
3. 删除后代码更简洁

---

## 执行修复

### 步骤1：删除状态定义

```typescript
// 删除第108行
// const [titleSource, setTitleSource] = useState<"user" | "auto">("auto");
```

### 步骤2：删除所有 `setTitleSource` 调用

- 第592-593行：删除
- 第852-853行：删除
- 第961-962行：删除
- 第1050-1051行：删除
- 第1468行：删除

### 步骤3：修改 UI 显示逻辑

```typescript
// 第1497-1504行
<span
  style={{
    cursor: "pointer",
    color: titleLocked ? "#000" : "#666",  // 使用 titleLocked 替代 titleSource
    fontSize: titleLocked ? "16px" : "14px",
    fontWeight: titleLocked ? "bold" : "normal",
  }}
  onClick={() => setEditingTitle(true)}
>
  {sessionTitle || "未命名会话"}
  {!titleLocked && (  // 使用 titleLocked 替代 titleSource
    <Tooltip title="AI自动生成的标题">
      <InfoCircleOutlined
        style={{ fontSize: 12, marginLeft: 4, color: "#999" }}
      />
    </Tooltip>
  )}
```

---

## 风险评估

**风险**：低

**原因**：
1. `title_source` 是后端动态计算的，不是从数据库读取的
2. 删除前端的 `titleSource` 状态不会影响后端逻辑
3. UI 显示逻辑只是从 `titleSource` 改为 `titleLocked`，逻辑完全一致

---

## 验证方法

修复后验证：
1. 新建会话，发送第一条消息 → 标题应该自动生成，显示灰色小字体，显示 InfoCircleOutlined 图标
2. 用户修改标题 → 标题应该显示黑色大字体，显示 LockOutlined 图标
3. 加载历史会话 → 标题应该根据 `title_locked` 正确显示

---

**结论**：方案A（删除 `titleSource` 状态）是正确的修复方案。