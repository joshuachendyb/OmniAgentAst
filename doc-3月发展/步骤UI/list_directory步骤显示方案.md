# list_directory 步骤数据显示方案

**创建时间**: 2026-03-23 15:54:54  
**编写人**: 小沈  
**适用范围**: list_directory 工具返回数据的在前端的显示方式

---

## 一、背景

list_directory 工具支持两种模式：
1. **非递归模式**：列出目录的直接子项（数量较少）
2. **递归模式**：列出目录的递归子项（数量可达上千条）

修改记录：2026-03-23 修复了分页导致数据丢失问题，现在会返回完整数据。

---

## 二、数据结构分析

### 2.1 非递归模式返回数据

```json
{
  "entries": [
    {"name": "文件夹1", "path": "D:\\文件夹1", "type": "directory", "size": null},
    {"name": "文件1.txt", "path": "D:\\文件1.txt", "type": "file", "size": 1024}
  ],
  "total": 23,
  "directory": "D:\\"
}
```

### 2.2 递归模式返回数据

```json
{
  "entries": [
    {"name": "$RECYCLE.BIN", "path": "$RECYCLE.BIN", "type": "directory", "size": null},
    {"name": ".agent", "path": "D:\\2bktest\\Ammreader\\.agent", "type": "directory", "size": null},
    {"name": ".git", "path": "D:\\1WTCB\\.git", "type": "directory", "size": null},
    // ... 3118 条数据
  ],
  "total": 3118,
  "directory": "D:\\"
}
```

### 2.3 数据字段说明

| 字段 | 说明 |
|------|------|
| name | 文件/文件夹名称 |
| path | 完整路径（根目录直接子项是相对路径，深层子项是绝对路径） |
| type | "directory" 或 "file" |
| size | 文件大小（文件夹为 null） |

**注意**：返回数据**不包含层级字段**，前端需要根据 path 字段解析出层级关系。

---

## 三、显示方案

### 3.1 非递归模式（少量数据，推荐虚拟列表）

**推荐方案**：虚拟列表（Virtual Scrolling）

**原理**：只渲染可见区域的 DOM 节点，而非渲染所有节点。

**优点**：
- 性能好，渲染快
- 用户体验流畅，滚动无卡顿
- 不需要额外的分页请求

**实现**：
- 可使用 Ant Design 的 `List` 组件 + `virtual` 属性
- 或使用 `react-window`、`react-virtualized` 等库

**搜索功能**：
- 在列表顶部添加搜索框
- 用户输入关键词时，前端过滤显示匹配的结果
- 不需要额外请求，直接在前端数据中搜索

### 3.2 递归模式（大量数据，推荐树形结构）

**推荐方案**：树形结构展示（Tree 组件）

**原理**：按层级展示目录结构，展开/收起子目录。

**优点**：
- 直观展示目录层级关系
- 用户可以按需展开查看
- 适合大量数据的组织

**实现**：
- 使用 Ant Design 的 `Tree` 组件
- 需要前端将扁平数据转换为树形结构

**数据转换逻辑**：
```javascript
function convertToTree(entries) {
  // 1. 根据 path 解析层级
  // 2. 构建树形结构
  // 3. 返回树形数据给 Tree 组件
}
```

**备选方案**：

1. **扁平化列表**：所有条目放一起，用缩进表示层级
   - 实现简单
   - 但层级不明显，查找困难

2. **目录文件分离**：左边 Tree 显示目录，右边 List 显示文件
   - 适合目录层级较深的场景
   - 交互复杂

---

## 四、方案对比

| 模式 | 推荐方案 | 备选方案 | 备注 |
|------|----------|----------|------|
| 非递归（少量） | 虚拟列表 | 懒加载 | 虚拟列表性能更好 |
| 递归（大量） | 树形结构 | 扁平化列表 | 树形结构更直观 |

---

## 五、实施建议

### 5.1 优先级

1. **优先实现**：非递归模式的虚拟列表（实现简单，提升明显）
2. **后续实现**：递归模式的树形结构（需要数据转换逻辑）

### 5.2 注意事项

1. 递归数据需要前端自己解析层级，因为返回的 JSON 不包含层级字段
2. 非递归模式也可以考虑虚拟列表，以应对未来数据量增长

### 5.3 如何判断是否递归

前端可以通过 `action_tool` 步骤的 `tool_params` 字段判断：

```json
// 非递归
{
  "tool_name": "list_directory",
  "tool_params": {
    "dir_path": "D:/"
  }
}

// 递归
{
  "tool_name": "list_directory",
  "tool_params": {
    "dir_path": "D:/",
    "recursive": true,
    "max_depth": 3
  }
}
```

**判断逻辑**：
```javascript
const isRecursive = step.tool_params?.recursive === true;

// 显示方案
if (isRecursive) {
  // 使用树形结构显示（Tree组件）
} else {
  // 使用虚拟列表显示（Virtual List）
}
```

---

**更新时间**: 2026-03-23 15:54:54