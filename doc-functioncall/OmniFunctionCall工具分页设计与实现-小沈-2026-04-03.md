# OmniFunctionCall 工具设计与实现文档（最新分页方案）

**创建时间**: 2026-04-03 14:26:22  
**版本**: v2.0  
**编写人**: 小沈  
**更新人**: 小沈  
**更新时间**: 2026-04-03 15:00:00

---

## 一、核心设计理念（2026-04-03 更新）

**后端原则**：必须返回全部真实数据，不能丢失任何数据！
**前端控制**：前端自己决定如何显示（分页/滚动），不依赖后端分页

### 新旧方案对比

| 方案 | 后端 | 前端 | 说明 |
|------|------|------|------|
| **旧方案（已废弃）** | 限制每页数量，返回部分数据 | 点击"加载更多"调用nextPage | ❌ 后端丢失数据 |
| **新方案** | 返回全部数据 | 自己控制分页/滚动显示 | ✅ 数据不丢失 |

---

## 二、支持分页的工具列表

本文档涵盖以下工具（数据全部返回，前端自行处理显示）：

| 工具名称 | 功能描述 | 返回数据 |
|----------|----------|----------|
| **list_directory** | 列出目录内容 | 全部目录条目 |
| **read_file** | 读取文件内容 | 全部文件内容（或指定范围） |
| **search_files** | 搜索文件名 | 全部匹配文件 |
| **search_file_content** | 搜索文件内容 | 全部匹配结果 |

---

## 二、当前实现方式

### 2.1 后端返回全部数据（除 read_file 外）

**2026-04-03 更新**：后端设置 `DEFAULT_PAGE_SIZE = 999999999`，保证返回全部数据

```python
# backend/app/services/tools/file/file_tools.py
# 【分页方案更新】2026-04-03 小沈

# read_file 特殊处理：默认限制500行（因为大文件不能一次性读取到内存）
READ_FILE_DEFAULT_LIMIT = 500

# 其他工具返回全部数据
DEFAULT_PAGE_SIZE = 999999999  # 远超实际数据量，保证返回全部
```

### 2.2 read_file 特殊说明

**read_file 是特殊 case**：
- 大文件不能一次性读取全部内容到内存
- 需要保留 limit 参数，默认 500 行
- 前端可以指定 offset 读取不同部分

### 2.3 前端控制显示

前端收到全部数据后，可以选择：

**方案A：前端分页**
```typescript
// 前端自己实现分页
const pageSize = 100;  // 前端自己决定每页显示多少
const currentPage = 1;
const displayData = allData.slice((currentPage - 1) * pageSize, currentPage * pageSize);
```

**方案B：滚动加载**
```typescript
// 类似微信聊天，滚动加载
const visibleItems = allData.slice(0, 100);  // 先显示100条
// 滚动到底部时增加
const moreItems = allData.slice(0, visibleItems.length + 100);
```

### 2.4 next-page 接口（保留但不使用）

next-page 接口仍然存在，但**不再需要使用**，因为后端已经返回全部数据。

---

## 三、工具返回字段说明

### 3.1 list_directory

```python
{
    "success": True,
    "entries": [...],  # 全部目录条目
    "total": 1000,    # 总数量
    "has_more": False # 永远是false（因为返回全部）
}
```

### 4.2 read_file

```python
{
    "success": True,
    "content": "...",     # 全部内容
    "total_lines": 5000,   # 总行数
    "start_line": 1,
    "end_line": 5000,      # 默认返回全部
    "has_more": False      # 永远是false（因为返回全部）
}
```

### 4.3 search_files / search_file_content

```python
{
    "success": True,
    "matches": [...],  # 全部匹配结果
    "total": 800,      # 总匹配数
    "has_more": False  # 永远是false（因为返回全部）
}
```

---

## 四、前端实现建议

### 4.1 前端分页实现

```typescript
// 收到全部数据后，前端自己控制
function handleToolResponse(rawData) {
    const allData = rawData.matches || rawData.entries || [];
    
    // 分页显示
    const [page, setPage] = useState(1);
    const pageSize = 100;  // 前端自己决定每页数量
    
    const displayData = allData.slice((page - 1) * pageSize, page * pageSize);
    
    // 渲染
    return (
        <div>
            {displayData.map(item => <Item key={item.name} data={item} />)}
            {page * pageSize < allData.length && (
                <button onClick={() => setPage(p => p + 1)}>加载更多</button>
            )}
        </div>
    );
}
```

### 4.2 滚动加载实现（推荐）

```typescript
// 类似微信聊天，滚动加载更多
function handleToolResponse(rawData) {
    const allData = rawData.matches || rawData.entries || [];
    const [visibleCount, setVisibleCount] = useState(100);
    
    return (
        <div style={{ height: '500px', overflow: 'auto' }} 
             onScroll={(e) => {
                 // 滚动到底部时加载更多
                 const { scrollTop, scrollHeight, clientHeight } = e.target;
                 if (scrollTop + clientHeight >= scrollHeight - 50) {
                     setVisibleCount(c => Math.min(c + 100, allData.length));
                 }
             }}>
            {allData.slice(0, visibleCount).map(item => <Item data={item} />)}
        </div>
    );
}
```

---

## 六、版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-04-03 14:26:22 | 初始版本（旧方案） | 小沈 |
| v1.1 | 2026-04-03 14:40:00 | 更新分页大小为500，补充read_file特殊分页机制说明 | 小沈 |
| v2.0 | 2026-04-03 15:00:00 | 废弃后端分页，改为后端返回全部数据，前端自行控制显示 | 小沈 |

---

## 七、总结

**核心改变**：
1. ✅ 后端不再限制返回数量，返回全部数据
2. ✅ 前端自己决定如何显示（分页/滚动）
3. ✅ 不再依赖 next-page 接口
4. ✅ 数据不丢失，用户看到完整结果