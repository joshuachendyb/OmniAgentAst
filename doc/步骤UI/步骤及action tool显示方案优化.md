# 步骤及 action_tool 显示方案优化

**创建时间**: 2026-03-23 16:07:56  
**编写人**: 小沈  
**适用范围**: 前端 MessageItem.tsx 步骤显示字段修正

---

## 一、问题背景

前端显示步骤时使用了错误的字段名，需要修正为正确的后端字段。

### 1.1 问题分类

| 步骤类型 | 问题数量 | 主要问题 |
|---------|---------|---------|
| thought | 1个 | 字段名错误 |
| action_tool | 0个 | 已正确 |
| observation | 5个 | 字段名错误 + 前缀处理问题 |

### 1.2 待修复清单

| 文件 | 位置 | 问题 | 优先级 |
|------|------|------|---------|
| MessageItem.tsx | 第589行 | 导出使用 `obs_` 前缀 | P1 |
| MessageItem.tsx | 第312行 | 显示 `step.thought` | P1 |
| MessageItem.tsx | 第344行 | 使用 `step.observation?.result` | P1 |
| MessageItem.tsx | 第410行 | 使用 `step.thinking_prompt` | P2 |

---

## 二、thought 字段问题

### 2.1 后端字段（实际数据结构）

```
type, step, timestamp, content, reasoning, action_tool, params
```

### 2.2 前端字段使用问题（Line 410）

**问题代码**：
```tsx
💭 {step.thinking_prompt || step.content || ""}
```

**问题**：
- 后端 thought **没有** `thinking_prompt` 字段
- 后端有 `content` 和 `reasoning` 字段

**修正**：
```tsx
💭 {step.content || step.reasoning || ""}
```

### 2.3 thought 字段对照表

| 前端显示内容 | 正确字段 |
|-------------|---------|
| 思考内容 | `step.content` 或 `step.reasoning` |

---

## 三、observation 字段问题

### 3.1 后端字段（实际数据结构）

```
type, step, timestamp, obs_execution_status, obs_summary, obs_raw_data, 
content, obs_reasoning, obs_action_tool, obs_params, is_finished
```

### 3.2 字段接收解析问题（核心问题）

#### 3.2.1 问题描述

前端 SSE 解析 observation 步骤时，对字段前缀处理不一致：

**后端返回字段（带 obs_ 前缀）**：
```
obs_execution_status, obs_summary, obs_raw_data, obs_reasoning, obs_action_tool, obs_params
```

**前端 sse.ts 解析后保存的字段（去掉 obs_ 前缀）**：
```
execution_status, summary, raw_data, reasoning, action_tool, params
```

#### 3.2.2 根因分析

sse.ts 第823行（代码从826行开始）解析 observation 时，把 `obs_` 前缀去掉了：
```typescript
case "observation": {
  step.raw_data = rawData.obs_raw_data ?? null;        // obs_raw_data → raw_data
  step.execution_status = rawData.obs_execution_status ?? 'success';
  step.summary = rawData.obs_summary ?? '';
  step.reasoning = rawData.obs_reasoning ?? '';
  step.action_tool = rawData.obs_action_tool ?? '';
  step.params = rawData.obs_params ?? {};
}
```

#### 3.2.3 导出代码读取问题

MessageItem.tsx 第589行导出时使用了 `obs_` 前缀读取：
```typescript
case 'observation':
  return { 
    obs_execution_status: (step as any).obs_execution_status,  // ❌ 应该是 execution_status
    obs_summary: (step as any).obs_summary,                    // ❌ 应该是 summary
    obs_raw_data: (step as any).obs_raw_data,                  // ❌ 应该是 raw_data
  };
```

**问题**：导出代码读取 `obs_execution_status`，但 sse.ts 保存的是 `execution_status`，导致数据为 undefined！

#### 3.2.4 修复方案

修改导出代码，使用正确字段名：
```typescript
case 'observation':
  return { 
    ...baseExport, 
    step: step.step, 
    execution_status: step.execution_status,    // ✅ 正确
    summary: step.summary,                        // ✅ 正确
    raw_data: step.raw_data,                    // ✅ 正确
    content: step.content,                       // ✅ 正确
    reasoning: step.reasoning,                  // ✅ 正确
    action_tool: step.action_tool,              // ✅ 正确
    params: step.params,                         // ✅ 正确
    is_finished: step.is_finished 
  };
```

### 3.3 前端显示问题

#### 3.3.1 问题1（Line 312）

**问题代码**：
```tsx
{step.thought && (
  <div>💭 {step.thought}</div>
)}
```

**问题**：后端没有 `thought` 字段

**修正**：
```tsx
{step.reasoning && (
  <div>💭 {step.reasoning}</div>
)}
```

#### 3.3.2 问题2（Line 344）

**问题代码**：
```tsx
const obsResult = step.observation?.result;
const hasEntries = obsResult?.entries && Array.isArray(obsResult.entries);
```

**问题**：后端没有 `observation.result` 字段

**修正**：
```tsx
const obsRawData = step.raw_data;
const hasEntries = obsRawData?.entries && Array.isArray(obsRawData.entries);
```

### 3.4 observation 字段对照表

| 后端字段（原始） | 前端保存后 | 前端显示使用 |
|-----------------|-----------|-------------|
| `obs_execution_status` | `execution_status` | `step.execution_status` |
| `obs_summary` | `summary` | `step.summary` |
| `obs_raw_data` | `raw_data` | `step.raw_data` |
| `content` | `content` | `step.content` |
| `obs_reasoning` | `reasoning` | `step.reasoning` |
| `obs_action_tool` | `action_tool` | `step.action_tool` |
| `obs_params` | `params` | `step.params` |
| `is_finished` | `is_finished` | `step.is_finished` |

---

## 四、字段对照表（汇总）

### 4.1 thought 步骤字段表

| 字段名 | 类型 | 说明 | 前端使用 |
|--------|------|------|---------|
| type | string | 固定为 "thought" | - |
| step | number | 步骤编号 | - |
| timestamp | string | 时间戳 | - |
| content | string | 思考内容 | ✅ `step.content` |
| reasoning | string | 推理过程 | ✅ `step.reasoning` |
| action_tool | string | 下一步动作 | - |
| params | object | 动作参数 | - |

### 4.2 action_tool 步骤字段表

| 字段名 | 类型 | 说明 | 前端使用 |
|--------|------|------|---------|
| type | string | 固定为 "action_tool" | - |
| step | number | 步骤编号 | - |
| timestamp | string | 时间戳 | - |
| tool_name | string | 工具名称 | ✅ `step.tool_name` |
| tool_params | object | 工具参数 | ✅ `step.tool_params` |
| execution_status | string | 执行状态 | ✅ `step.execution_status` |
| summary | string | 执行摘要 | ✅ `step.summary` |
| raw_data | object | 原始数据 | ✅ `step.raw_data` |
| action_retry_count | number | 重试次数 | - |

**raw_data.data 关键字段对照表**：

| 工具 | data 关键字段 | 类型 | 说明 |
|------|-------------|------|------|
| list_directory | entries | array | 条目数组 |
| | total | number | 总数 |
| | has_more | boolean | 是否还有更多 |
| read_file | content | string | 带行号内容 |
| | total_lines | number | 总行数 |
| | has_more | boolean | 是否还有更多 |
| write_file | file_path | string | 文件路径 |
| | bytes_written | number | 写入字节数 |
| delete_file | deleted_path | string | 删除路径 |
| | message | string | 提示信息 |
| move_file | source | string | 源路径 |
| | destination | string | 目标路径 |
| search_files | files_matched | number | 匹配文件数 |
| | total_matches | number | 总匹配数 |
| | matches | array | 匹配详情数组 |
| generate_report | reports | object | 报告字典 |

### 4.3 observation 步骤字段表

| 字段名 | 类型 | 说明 | 前端保存后 | 前端使用 |
|--------|------|------|-----------|---------|
| type | string | 固定为 "observation" | - | - |
| step | number | 步骤编号 | - | - |
| timestamp | string | 时间戳 | - | - |
| obs_execution_status | string | 执行状态 | execution_status | step.execution_status |
| obs_summary | string | 执行摘要 | summary | step.summary |
| obs_raw_data | object | 原始数据 | raw_data | step.raw_data |
| content | string | 内容 | content | step.content |
| obs_reasoning | string | 推理过程 | reasoning | step.reasoning |
| obs_action_tool | string | 下一步动作 | action_tool | step.action_tool |
| obs_params | object | 动作参数 | params | step.params |
| is_finished | boolean | 是否完成 | is_finished | step.is_finished |

---

## 五、action_tool 显示问题

### 5.1 分页问题（已修复）

之前 list_directory 使用 `page_size=100` 导致数据丢失：
- 1000条数据只返回前100条
- 递归查询3118条数据也只返回100条

**修复**：2026-03-23 修改了 `page_size` 默认值为 `None`，现在返回所有数据。

### 5.2 显示问题（已修复）

用户反馈：action_tool 步骤只显示工具名称和参数，没有显示工具执行结果（文件列表）。

**修复**：添加了文件列表折叠显示功能。

### 5.3 代码分析（详细）

**文件**: `frontend/src/components/Chat/MessageItem.tsx` 第 305-380 行

#### 5.3.1 observation 步骤渲染逻辑

```tsx
{step.type === "observation" && (
  <>
    {/* 显示 step.thought */}
    {step.thought && (
      <div>💭 {step.thought}</div>
    )}
    
    {/* 显示 step.content */}
    {step.content && typeof step.content === "string" && (
      <div>📋 {step.content}</div>
    )}
    
    {/* 显示 step.observation?.result?.entries - 只有当没有 content 时才显示 */}
    {!step.content && (
      <div>
        {obsResult?.entries && (
          // 文件列表显示
          {obsResult.entries.map(...)}
        )}
      </div>
    )}
  </>
)}
```

**结论**：
- ✅ observation **有**显示 `step.content`
- ✅ observation **有**显示 `step.observation?.result?.entries`
- 两者互斥：有 content 时只显示 content，没有 content 时才显示 entries

#### 5.3.2 action_tool 步骤渲染逻辑

**文件**: `frontend/src/components/Chat/MessageItem.tsx` 第 216-304 行

```tsx
{step.type === "action_tool" && (
  <>
    {/* 显示工具名称 */}
    {step.action_description || step.tool_name || "执行中..."}
    
    {/* 显示工具参数 */}
    {step.tool_params && (
      <div>
        参数：{JSON.stringify(step.tool_params, null, 2)}
      </div>
    )}
    
    {/* 显示分页信息 */}
    {step.raw_data && (
      <div>
        {step.raw_data.total && (
          <span>📊 共 {step.raw_data.total} 个项目</span>
        )}
        {hasMore && <span>📄 加载更多</span>}
      </div>
    )}
  </>
)}
```

**结论**：
- ✅ action_tool **有**显示 `step.tool_name`（工具名称）
- ✅ action_tool **有**显示 `step.tool_params`（工具参数）
- ✅ action_tool **有**显示 `step.raw_data.total`（总数）和分页信息
- ❌ action_tool **没有**显示 `step.raw_data.entries`（文件列表）← **这就是问题所在！**

#### 5.3.3 对比总结

| 字段 | observation | action_tool |
|------|-------------|-------------|
| content | ✅ 有显示 | ❌ 无（不需要） |
| entries | ❌ 无（observation 只有 obs_raw_data 字段，无 entries） | ❌ 无（应该通过 raw_data.entries 显示） |
| total | - | ✅ 有显示 |
| 分页 | - | ✅ 有显示 |

**注**：文档之前记录有误，observation 步骤没有 result.entries 字段。

### 5.4 根因

action_tool 步骤的渲染代码只显示了：
- 工具名称
- 工具参数
- 总数和分页信息

**缺少显示 `step.raw_data.entries`（文件列表）**，这是用户需要查看的内容。

### 5.5 修复方案

#### 5.5.1 实现功能

在 action_tool 和 observation 步骤中添加文件列表折叠功能：
- 默认展开
- 点击"▶ 展开/▼ 收起 文件列表 (N个)"按钮可以切换
- 使用 getFileListBackground() 样式显示文件列表

#### 5.5.2 代码修改

**文件**: `frontend/src/components/Chat/MessageItem.tsx`

**修改1**: 添加Map状态（支持多步骤独立折叠）
```tsx
const [expandedSteps, setExpandedSteps] = useState<Map<number, boolean>>(
  new Map([[0, true]]) // 默认第0步展开
);

// 切换展开状态
const toggleExpand = (stepIndex: number) => {
  setExpandedSteps(prev => {
    const newMap = new Map(prev);
    newMap.set(stepIndex, !newMap.get(stepIndex));
    return newMap;
  });
};
```

**修改2**: action_tool 显示逻辑
```tsx
{/* 显示文件列表 - 带折叠功能 */}
{step.raw_data?.entries && step.raw_data.entries.length > 0 && (
  <div>
    {/* 折叠按钮和文件计数 */}
    <div style={{ marginBottom: 6 }}>
      <span 
        onClick={() => toggleExpand(stepIndex)}
        style={{ cursor: "pointer", color: "#1890ff", fontSize: 12, fontWeight: 500 }}
      >
        {(expandedSteps.get(stepIndex) ?? false) ? "▼ 收起" : "▶ 展开"} 文件列表 ({step.raw_data.entries.length}个)
      </span>
    </div>
    {/* 文件列表内容 */}
    {(expandedSteps.get(stepIndex) ?? false) && step.raw_data?.entries && (
      <div style={getFileListBackground()}>
        {step.raw_data.entries.map((entry: any, idx: number) => (...))}
      </div>
    )}
  </div>
)}
```

**修改3**: observation 显示逻辑（同样添加折叠功能）

### 5.6 修复验证

- ✅ TypeScript 编译通过
- ✅ 生产构建成功
- ✅ action_tool 步骤显示文件列表（可折叠）
- ✅ observation 步骤显示文件列表（可折叠）
- ✅ 默认展开

---

## 六、根据 tool_name 分支处理

### 6.1 核心原则

**不同工具的 `raw_data.data` 结构完全不同，前端必须根据 `tool_name` 字段判断使用哪种解析方式。**

### 6.2 分支处理代码结构

```tsx
const renderToolResult = (step: any) => {
  const data = step.raw_data?.data;
  if (!data) return null;
  
  switch (step.tool_name) {
    case 'list_directory':
      return <ListDirectoryView data={data} />;
    case 'read_file':
      return <ReadFileView data={data} />;
    case 'write_file':
      return <WriteFileView data={data} />;
    case 'delete_file':
      return <DeleteFileView data={data} />;
    case 'move_file':
      return <MoveFileView data={data} />;
    case 'search_files':
      return <SearchFilesView data={data} />;
    case 'generate_report':
      return <GenerateReportView data={data} />;
    default:
      return <pre>{JSON.stringify(data, null, 2)}</pre>;
  }
};
```

---

## 七、显示方案

### 7.1 list_directory 数据结构分析

list_directory 工具支持两种模式：
1. **非递归模式**：列出目录的直接子项（数量较少）
2. **递归模式**：列出目录的递归子项（数量可达上千条）

#### 7.1.1 非递归模式返回数据

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

#### 7.1.2 递归模式返回数据

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

#### 7.1.3 数据字段说明

| 字段 | 说明 |
|------|------|
| name | 文件/文件夹名称 |
| path | 完整路径（根目录直接子项是相对路径，深层子项是绝对路径） |
| type | "directory" 或 "file" |
| size | 文件大小（文件夹为 null） |

**注意**：返回数据**不包含层级字段**，前端需要根据 path 字段解析出层级关系。

### 7.2 非递归模式显示方案（少量数据）

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

### 7.3 递归模式显示方案（大量数据）

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

### 7.4 方案对比

| 模式 | 推荐方案 | 备选方案 | 备注 |
|------|----------|----------|------|
| 非递归（少量） | 虚拟列表 | 懒加载 | 虚拟列表性能更好 |
| 递归（大量） | 树形结构 | 扁平化列表 | 树形结构更直观 |

### 7.5 两种显示模式

根据 `recursive` 参数分为两种模式：

| 模式 | recursive参数 | 数据量 | 显示方案 |
|------|--------------|--------|---------|
| 单列表模式 | `false` | 少量（直接子项） | 虚拟列表 |
| 递归模式 | `true` | 大量（所有子项） | 树形结构 |

**判断逻辑**：
```javascript
const isRecursive = step.tool_params?.recursive === true;

if (isRecursive) {
  // 递归模式 → 树形结构
} else {
  // 单列表模式 → 虚拟列表
}
```

**判断逻辑流程图**：
```
                开始
                  ↓
      recursive === true？
          ↓         ↓
         是         否
          ↓         ↓
    树形结构   虚拟列表
```

---

## 八、实施计划

### 8.1 list_directory 实施建议

#### 8.1.1 优先级

1. **优先实现**：单列表模式的虚拟列表（实现简单，提升明显）
2. **后续实现**：递归模式的树形结构（需要数据转换逻辑）

#### 8.1.2 注意事项

1. 递归数据需要前端自己解析层级，因为返回的 JSON 不包含层级字段
2. 非递归模式也可以考虑虚拟列表，以应对未来数据量增长

#### 8.1.3 树形数据转换算法

递归模式下，返回的entries是**扁平数组**，需要前端转换为树形结构。

**后端返回格式（已确认）**：
- **直接子项**：相对路径（如 `"src/config.json"`）
- **深层子项**：绝对路径（如 `"D:/project/src/components/App.tsx"`）

**路径特点**：混合格式，前端需要处理

**算法思路**：
```javascript
interface TreeNode {
  key: string;
  title: string;
  type: 'directory' | 'file';
  children?: TreeNode[];
  path: string;
  size: number | null;
}

function convertEntriesToTree(entries: Entry[], rootPath: string): TreeNode[] {
  // 1. 构建 path -> node 的映射
  // 2. 遍历entries，根据path解析父子关系
  // 3. 返回根节点列表
}
```

**转换步骤**：
1. **按type排序**：目录在前，文件在后
2. **解析层级关系**：
   - 相对路径 → 直接作为根目录的子节点
   - 绝对路径 → 从rootPath开始解析层级
3. **构建树形结构**：用Map存储父子关系
4. **返回根节点**：包含所有顶级目录和文件

**关键处理**：
- 直接子项（无父级path）→ 根节点
- 深层子项（绝对路径）→ 需要从rootPath解析中间目录

#### 8.1.4 多步骤折叠状态管理

action_tool和observation步骤都可能显示文件列表，需要独立管理每个步骤的折叠状态。

**问题**：如果所有步骤共用一个状态，折叠一个会影响其他

**修复方案**：使用 Map 存储每个步骤的展开状态

```tsx
// 使用 Map 存储每个步骤的展开状态
const [expandedSteps, setExpandedSteps] = useState<Map<number, boolean>>(
  new Map([[0, true]]) // 默认第0步展开
);

// 切换展开状态
const toggleExpand = (stepIndex: number) => {
  setExpandedSteps(prev => {
    const newMap = new Map(prev);
    newMap.set(stepIndex, !newMap.get(stepIndex));
    return newMap;
  });
};

// 判断是否展开
const isExpanded = expandedSteps.get(stepIndex) ?? false;
```

| 优先级 | 功能 | 状态 |
|--------|------|------|
| P1 | 修复 observation 导出字段（3处 obs_ 前缀） | 待修复 |
| P1 | 修复 Line 312 使用 `step.thought` | 待修复 |
| P1 | 修复 Line 344 使用 `step.observation?.result` | 待修复 |
| P2 | 修复 Line 410 使用 `step.thinking_prompt` | 待修复 |
| P3 | 根据 tool_name 分支处理（7个工具） | 待实现 |
| P4 | 非递归模式虚拟列表 | 待实现 |
| P5 | 递归模式树形结构 | 待实现 |

---

**更新时间**: 2026-03-23 20:40:00
**版本**: v2.5
**更新内容**: 修正sse.ts行号描述；修正5.5.2节代码示例，统一使用Map方案

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-03-23 16:07:56 | 小沈 | 初始版本 |
| v1.1 | 2026-03-23 16:30:00 | 小沈 | 新增根据 tool_name 分支处理结构 |
| v1.2 | 2026-03-23 19:15:00 | 小沈 | 新增observation字段问题分析及修复方案 |
| v2.0 | 2026-03-23 19:25:00 | 小沈 | 重组文档结构：thought/observation各一章、字段对照表分3表 |
| v2.1 | 2026-03-23 19:46:15 | 小沈 | 补充第5章缺失内容；补充第7章缺失内容 |
| v2.2 | 2026-03-23 20:05:00 | 小沈 | 修正行号错误；新增7.5节区分数据量方法 |
| v2.3 | 2026-03-23 20:20:00 | 小沈 | 简化7.5节；新增8.1.3树形转换算法；新增8.1.4多步骤折叠状态管理 |
| v2.4 | 2026-03-23 20:30:00 | 小沈 | 确认后端path格式；简化7.5为两种模式；更新树形转换算法说明 |
| v2.5 | 2026-03-23 20:40:00 | 小沈 | 修正sse.ts行号；修正5.5.2节代码示例统一使用Map方案 |
