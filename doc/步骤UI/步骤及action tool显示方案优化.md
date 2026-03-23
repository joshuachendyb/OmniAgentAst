# 步骤及 action_tool 显示方案优化

**创建时间**: 2026-03-23 16:07:56  
**编写人**: 小沈  
**适用范围**: 前端 MessageItem.tsx 步骤显示字段修正

---

## 一、问题背景

前端显示步骤时使用了错误的字段名，需要修正为正确的后端字段。

---

## 二、后端字段（实际数据结构）

### 2.1 thought 步骤

```
字段: type, step, timestamp, content, reasoning, action_tool, params
```

### 2.2 action_tool 步骤

```
字段: type, step, timestamp, tool_name, tool_params, execution_status, summary, raw_data, action_retry_count
```

### 2.3 observation 步骤

```
字段: type, step, timestamp, obs_execution_status, obs_summary, obs_raw_data, content, obs_reasoning, obs_action_tool, obs_params, is_finished
```

---

## 三、前端字段使用问题及修正

### 3.1 thought 步骤问题（Line 410）

**前端代码**：
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

---

### 3.2 observation 字段接收、解析、保存问题

**发现时间**: 2026-03-23 19:15:00
**发现人**: 小沈

#### 3.2.1 问题描述

前端 SSE 解析和保存 observation 步骤时，字段处理方式存在不一致：

**后端返回字段（带 obs_ 前缀）**：
```
obs_execution_status, obs_summary, obs_raw_data, obs_reasoning, obs_action_tool, obs_params
```

**前端 sse.ts 解析后保存的字段（去掉 obs_ 前缀）**：
```
execution_status, summary, raw_data, reasoning, action_tool, params
```

#### 3.2.2 问题根因

sse.ts 第826-832行解析 observation 时，把 `obs_` 前缀去掉了：
```typescript
case "observation": {
  step.is_finished = rawData.is_finished ?? false;
  step.raw_data = rawData.obs_raw_data ?? null;        // obs_raw_data → raw_data
  step.execution_status = rawData.obs_execution_status ?? 'success';  // obs_ 前缀去掉
  step.summary = rawData.obs_summary ?? '';              // obs_summary → summary
  // ...
}
```

#### 3.2.3 导出代码读取问题

MessageItem.tsx 第589行导出时使用了 `obs_` 前缀读取：
```typescript
case 'observation':
  return { 
    ...baseExport, 
    step: step.step, 
    obs_execution_status: (step as any).obs_execution_status,  // ❌ 应该是 execution_status
    obs_summary: (step as any).obs_summary,                    // ❌ 应该是 summary
    obs_raw_data: (step as any).obs_raw_data,                  // ❌ 应该是 raw_data
    is_finished: step.is_finished 
  };
```

**问题**：导出代码读取 `obs_execution_status`，但 sse.ts 保存的是 `execution_status`，导致数据为 undefined！

#### 3.2.4 修复方案

**方案1**：修改导出代码，使用正确字段名（推荐）
```typescript
case 'observation':
  return { 
    ...baseExport, 
    step: step.step, 
    execution_status: step.execution_status,    // ✅ 正确
    summary: step.summary,                      // ✅ 正确
    raw_data: step.raw_data,                   // ✅ 正确
    content: step.content,                     // ✅ 正确
    reasoning: step.reasoning,                 // ✅ 正确
    action_tool: step.action_tool,              // ✅ 正确
    params: step.params,                       // ✅ 正确
    is_finished: step.is_finished 
  };
```

**方案2**：修改 sse.ts，保留 `obs_` 前缀（不推荐，需要同时修改显示代码）

---

### 3.3 observation 步骤前端显示问题

#### 3.3.1 问题描述（Line 320）

**前端代码**：
```tsx
{step.thought && (
  <div>💭 {step.thought}</div>
)}
```

**问题**：
- 后端 observation **没有** `thought` 字段
- 后端有 `obs_reasoning` 字段（解析后变成 `reasoning`）

**修正**：
```tsx
{step.reasoning && (
  <div>💭 {step.reasoning}</div>
)}
```

#### 3.3.2 问题描述（Line 344）

**前端代码**：
```tsx
const obsResult = step.observation?.result;
const hasEntries = obsResult?.entries && Array.isArray(obsResult.entries);
const entryCount = hasEntries ? obsResult.entries.length : 0;
```

**问题**：
- 后端 observation **没有** `observation.result` 字段
- 后端有 `obs_raw_data` 字段（解析后变成 `raw_data`）

**修正**：
```tsx
const obsRawData = step.raw_data;
const hasEntries = obsRawData?.entries && Array.isArray(obsRawData.entries);
const entryCount = hasEntries ? obsRawData.entries.length : 0;
```

#### 3.3.3 observation 字段完整对照表

| 后端字段（原始） | 前端 sse.ts 解析后 | 前端显示应使用 |
|-----------------|-------------------|---------------|
| `obs_execution_status` | `execution_status` | `step.execution_status` |
| `obs_summary` | `summary` | `step.summary` |
| `obs_raw_data` | `raw_data` | `step.raw_data` |
| `content` | `content` | `step.content` |
| `obs_reasoning` | `reasoning` | `step.reasoning` |
| `obs_action_tool` | `action_tool` | `step.action_tool` |
| `obs_params` | `params` | `step.params` |
| `is_finished` | `is_finished` | `step.is_finished` |

---

### 3.4 待小强修复的前端代码清单

| 文件 | 位置 | 问题 | 修复方式 |
|------|------|------|---------|
| MessageItem.tsx | 第589行 | 导出使用 `obs_execution_status` | 改为 `execution_status` |
| MessageItem.tsx | 第589行 | 导出使用 `obs_summary` | 改为 `summary` |
| MessageItem.tsx | 第589行 | 导出使用 `obs_raw_data` | 改为 `raw_data` |
| MessageItem.tsx | 第320行 | 显示 `step.thought` | 改为 `step.reasoning` |
| MessageItem.tsx | 第344行 | 使用 `step.observation?.result` | 改为 `step.raw_data` |

---

## 四、正确的字段对应表

| 前端想显示的内容 | 后端正确字段 |
|-----------------|-------------|
| thought 思考内容 | `step.content` 或 `step.reasoning` |
| observation 思考内容 | `step.obs_reasoning` |
| observation 结果数据 | `step.obs_raw_data` |
| action_tool 结果数据 | `step.raw_data` |
| action_tool 工具名称 | `step.tool_name` |
| action_tool 工具参数 | `step.tool_params` |
| action_tool 执行状态 | `step.execution_status` |
| action_tool 总数 | `step.raw_data.total` |
| action_tool 文件列表 | `step.raw_data.entries` |

---

## 五、action_tool 显示问题（后端已修复）

### 5.1 分页问题（已修复）

之前 list_directory 使用 `page_size=100` 导致数据丢失：
- 1000条数据只返回前100条
- 递归查询3118条数据也只返回100条

**修复**：2026-03-23 修改了 `page_size` 默认值为 `None`，现在返回所有数据。

### 5.2 显示问题（已修复）

用户反馈：action_tool 步骤只显示工具名称和参数，没有显示工具执行结果（文件列表）。

**修复**：添加了文件列表折叠显示功能。

---

## 六、前端：数据结构分析（list_directory）

前端通过 `action_tool` 步骤的 `tool_params` 字段判断：

```javascript
const isRecursive = step.tool_params?.recursive === true;
```


### 6.1 非递归模式

```json
{
  "tool_name": "list_directory",
  "tool_params": { "dir_path": "D:/" },
  "raw_data": {
    "entries": [
      {"name": "文件夹1", "path": "D:\\文件夹1", "type": "directory", "size": null},
      {"name": "文件1.txt", "path": "D:\\文件1.txt", "type": "file", "size": 1024}
    ],
    "total": 23,
    "directory": "D:\\"
  }
}
```

### 6.2 递归模式

```json
{
  "tool_name": "list_directory",
  "tool_params": { "dir_path": "D:/", "recursive": true, "max_depth": 3 },
  "raw_data": {
    "entries": [
      {"name": "$RECYCLE.BIN", "path": "$RECYCLE.BIN", "type": "directory", "size": null},
      {"name": ".agent", "path": "D:\\2bktest\\Ammreader\\.agent", "type": "directory", "size": null},
      {"name": ".git", "path": "D:\\1WTCB\\.git", "type": "directory", "size": null}
    ],
    "total": 3118,
    "directory": "D:\\"
  }
}
```

## 八、根据 tool_name 分支处理（本次重点）

### 8.1 核心原则

**不同工具的 `raw_data.data` 结构完全不同，前端必须根据 `tool_name` 字段判断使用哪种解析方式。**

```
action_tool 步骤数据结构：
{
  "type": "action_tool",
  "tool_name": "xxx",           // ← 用这个判断工具类型
  "tool_params": {...},
  "raw_data": {
    "data": {...}               // ← 这个结构因工具而异
  }
}
```

### 8.2 分支处理代码结构

```tsx
// 根据 tool_name 选择显示方式
const renderToolResult = (step: any) => {
  // 获取工具返回的数据
  const data = step.raw_data?.data;
  
  if (!data) return null;
  
  // 🔴 根据 tool_name 分支处理
  switch (step.tool_name) {
    
    case 'list_directory':
      // data.entries[] - 文件列表
      // data.total - 总数
      return (
        <div>
          <span>📁 文件列表 ({data.total}个)</span>
          <div className="file-list" style={getFileListBackground()}>
            {data.entries.map((entry: any, idx: number) => (
              <div key={idx} style={{ padding: "4px 0", borderBottom: "1px solid #e8e8e8" }}>
                {entry.type === 'directory' ? '📁' : '📄'} {entry.name}
                {entry.size && <span style={{ color: "#888" }}> ({formatSize(entry.size)})</span>}
              </div>
            ))}
          </div>
        </div>
      );
    
    case 'read_file':
      // data.content - 带行号内容
      // data.total_lines - 总行数
      return (
        <div>
          <span>📄 共 {data.total_lines} 行</span>
          <pre style={{ whiteSpace: "pre-wrap", maxHeight: 400, overflow: "auto" }}>
            {data.content}
          </pre>
        </div>
      );
    
    case 'write_file':
      // data.file_path - 文件路径
      // data.bytes_written - 字节数
      return (
        <div>
          <span>✅ 已写入 {data.file_path}</span>
          <span style={{ color: "#888" }}>（{data.bytes_written} 字节）</span>
        </div>
      );
    
    case 'delete_file':
      // data.deleted_path - 删除路径
      // data.message - 提示信息
      return (
        <div>
          <span>🗑️ 已删除 {data.deleted_path}</span>
          <span style={{ color: "#888" }}>{data.message}</span>
        </div>
      );
    
    case 'move_file':
      // data.source - 源路径
      // data.destination - 目标路径
      return (
        <div>
          <span>📦 {data.source}</span>
          <span> → </span>
          <span>{data.destination}</span>
        </div>
      );
    
    case 'search_files':
      // data.matches[] - 匹配数组
      // data.files_matched - 匹配文件数
      // data.total_matches - 总匹配数
      return (
        <div>
          <span>🔍 找到 {data.files_matched} 个文件，{data.total_matches} 处匹配</span>
          {data.matches.map((match: any, idx: number) => (
            <div key={idx} style={{ marginTop: 8 }}>
              <div>📄 {match.file} ({match.match_count}处)</div>
              {match.matches.slice(0, 3).map((m: any, i: number) => (
                <pre key={i} style={{ fontSize: 11, color: "#666", margin: "4px 0" }}>
                  ...{m.context}...
                </pre>
              ))}
            </div>
          ))}
        </div>
      );
    
    case 'generate_report':
      // data.reports{} - 报告字典
      return (
        <div>
          <span>📊 已生成 {Object.keys(data.reports).length} 个报告</span>
          {Object.entries(data.reports).map(([type, path]: [string, string]) => (
            <div key={type}>
              {type}: {path}
            </div>
          ))}
        </div>
      );
    
    default:
      // 未知工具，显示原始数据
      return <pre>{JSON.stringify(data, null, 2)}</pre>;
  }
};
```

### 8.3 raw_data.data 字段对照表

| 工具 | data 关键字段 | 类型 | 说明 |
|------|-------------|------|------|
| **list_directory** | entries | array | 条目数组 |
| | total | number | 总数 |
| | has_more | boolean | 是否还有更多 |
| **read_file** | content | string | 带行号内容 |
| | total_lines | number | 总行数 |
| | has_more | boolean | 是否还有更多 |
| **write_file** | file_path | string | 文件路径 |
| | bytes_written | number | 写入字节数 |
| **delete_file** | deleted_path | string | 删除路径 |
| | message | string | 提示信息 |
| **move_file** | source | string | 源路径 |
| | destination | string | 目标路径 |
| **search_files** | files_matched | number | 匹配文件数 |
| | total_matches | number | 总匹配数 |
| | matches | array | 匹配详情数组 |
| **generate_report** | reports | object | 报告字典 |

---

## 九、显示方案

### 9.1 非递归模式（少量数据）

**推荐方案**：虚拟列表（Virtual Scrolling）

**原理**：只渲染可见区域的 DOM 节点，而非渲染所有节点。

**优点**：
- 性能好，渲染快
- 用户体验流畅，滚动无卡顿

**实现**：Ant Design 的 `List` 组件 + `virtual` 属性

### 9.2 递归模式（大量数据）

**推荐方案**：树形结构展示（Tree 组件）

**原理**：按层级展示目录结构，展开/收起子目录。

**优点**：
- 直观展示目录层级关系
- 用户可以按需展开查看
- 适合大量数据的组织

**实现**：Ant Design 的 `Tree` 组件

**数据转换逻辑**：
```javascript
function convertToTree(entries) {
  // 根据 path 解析层级，构建树形结构
}
```

---

## 十、实施计划

### 10.1 优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P1 | **根据 tool_name 分支处理** | 本次重点实现 |
| P2 | 修正字段对应错误 | 待修正 |
| P3 | action_tool 显示 entries（可折叠） | 已实现 |
| P4 | 非递归模式虚拟列表 | 待实现 |
| P5 | 递归模式树形结构 | 待实现 |

### 10.2 待确认

- 虚拟列表是否使用 Ant Design List 组件？
- 树形结构数据转换逻辑如何实现？

---

**更新时间**: 2026-03-23 19:15:00
**版本**: v1.2
**更新内容**: 新增3.2-3.4节：observation字段接收解析保存问题、修复方案、待修复清单

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-03-23 16:07:56 | 小沈 | 初始版本：字段修正、list_directory数据结构分析 |
| v1.1 | 2026-03-23 16:30:00 | 小沈 | 新增根据 tool_name 分支处理结构（7个工具的显示方案） |
| v1.2 | 2026-03-23 19:15:00 | 小沈 | 新增3.2-3.4节：observation字段接收解析保存问题、修复方案、待修复清单 |
