# DCP插件问题调查笔记

**创建时间**: 2026-02-10 06:25:32  
**更新时间**: 2026-02-10 06:29:53  
**调查人员**: AI助手小欧  
**文档状态**: 已更新（修正重要发现）  
**存放位置**: D:\2bktest\MDview\doc\

---

## 重要更新

**⚠️ 2026-02-10 更新说明**

经过查看 tarquinen npm 包 v2.0.2 的实际源代码（`dist/index.js`），**修正了之前的重要错误发现**：

- **之前错误**: 认为存在"版本混乱"，GitHub版和npm版工具名称不同
- **实际真相**: npm包v2.0.2实际提供的工具就是 `prune`, `distill`, `compress`，与GitHub文档一致
- **之前看到 npm 页面显示 `discard` 和 `extract` 是错误的**（可能是旧版本文档或查看错误）

**结论**: 没有版本混乱问题！工具名称是一致的。

---

## 一、问题背景

**调查起因**: 用户反馈 prune 操作频繁，影响正常工作，需要调查 DCP 插件的工作机制和配置问题。

**涉及插件**: @tarquinen/opencode-dcp v2.0.2  
**安装时间**: 2026-02-08  
**配置文件**: ~/.config/opencode/dcp.jsonc

---

## 二、核心发现

### 2.1 插件实际提供的工具

**源代码证据**（`dist/index.js` 第4行和第31-58行）：

```javascript
import { createPruneTool, createDistillTool, createCompressTool } from "./lib/strategies";

tool: {
  distill: createDistillTool({...}),  // ✅ distill 工具
  compress: createCompressTool({...}),  // ✅ compress 工具
  prune: createPruneTool({...}),  // ✅ prune 工具
},
```

**实际提供的三个工具**：

| 工具 | 功能 | 权限配置 | 说明 |
|------|------|---------|------|
| **prune** | 删除工具输出 | `tools.prune.permission` | 删除已完成的工具内容 |
| **distill** | 提炼摘要 | `tools.distill.permission` | 将重要内容提炼为摘要 |
| **compress** | 压缩对话 | `tools.compress.permission` | 压缩大段对话为单个摘要 |

### 2.2 配置与实际行为不匹配

**当前配置**:
```json
{
  "$schema": "https://raw.githubusercontent.com/Opencode-DCP/opencode-dynamic-context-pruning/master/dcp.schema.json"
}
```

**问题**:
- 配置仅包含 schema 引用，没有其他配置项
- DCP 完全使用默认配置运行
- 默认配置包含激进的自动清理策略

### 2.3 默认策略过于激进

**DCP 自动策略** (默认开启):

| 策略 | 说明 | 默认状态 | 问题 |
|------|------|---------|------|
| **Deduplication** | 去重，保留最新工具调用 | 开启 ✅ | 合理，建议保留 |
| **Supersede Writes** | 文件写入后被读取就删除原写入 | 开启 ✅ | 可能导致写入记录丢失 |
| **Purge Errors** | 错误信息在N轮后删除 | 开启 ✅ (4轮) | 调试时可能需要回看错误 |

**导致的实际问题**:
- 刚读取的文件内容可能很快被清理
- 调试时需要参考历史信息但已被删除
- 频繁的 prune 操作打断工作流

### 2.4 工具权限默认值

**根据源代码分析**（`dist/index.js` 第32-58行）：

```javascript
// 只有当 permission !== "deny" 时才启用工具
...(config.tools.distill.permission !== "deny" && { distill: ... }),
...(config.tools.compress.permission !== "deny" && { compress: ... }),
...(config.tools.prune.permission !== "deny" && { prune: ... }),
```

**默认权限**: 未配置时，三个工具都**默认启用**（相当于 permission = "allow"）

---

## 三、问题影响

### 3.1 用户体验问题
- prune 操作频繁，感觉被打断
- 想回看之前的搜索结果但已被清理
- 文件操作记录丢失，难以追溯

### 3.2 调试困难
- 错误信息被快速清理（4轮后）
- 无法对比历史操作结果
- 上下文丢失导致重复工作

### 3.3 配置设计问题
- 默认配置过于激进，无用户确认
- 缺乏配置示例和说明
- 用户不清楚哪些配置项有效

---

## 四、根因分析

### 4.1 默认配置过于激进
- 自动策略全部默认开启
- 清理周期短（错误4轮就删）
- 无用户确认机制

### 4.2 缺乏配置指导
- 用户配置仅包含 schema 引用
- 不知道有哪些配置项可调整
- 没有最佳实践文档

### 4.3 工具权限默认全开
- prune/distill/compress 都默认启用
- AI可以在任何时候调用
- 用户无法控制清理时机

---

## 五、解决方案建议

### 方案1: 保守配置 (推荐)

**目标**: 减少自动清理，保留更多上下文

```json
{
  "$schema": "https://raw.githubusercontent.com/Opencode-DCP/opencode-dynamic-context-pruning/master/dcp.schema.json",
  "enabled": true,
  "pruneNotification": "detailed",
  "tools": {
    "settings": {
      "nudgeEnabled": true,
      "nudgeFrequency": 20,
      "contextLimit": 150000
    },
    "prune": {
      "permission": "ask"
    },
    "distill": {
      "permission": "allow"
    },
    "compress": {
      "permission": "deny"
    }
  },
  "strategies": {
    "deduplication": {
      "enabled": true
    },
    "supersedeWrites": {
      "enabled": false
    },
    "purgeErrors": {
      "enabled": true,
      "turns": 15
    }
  }
}
```

**改动说明**:
- 关闭 Supersede Writes 策略
- 延长错误清理时间 (4轮→15轮)
- 增加上下文限制 (100k→150k)
- 减少清理提示频率 (10轮→20轮)
- **关键改动**: prune 改为 "ask" 权限，需要确认后才执行
- compress 禁用（不常用）

### 方案2: 最小干预配置

**目标**: 只保留必要的自动策略

```json
{
  "$schema": "https://raw.githubusercontent.com/Opencode-DCP/opencode-dynamic-context-pruning/master/dcp.schema.json",
  "enabled": true,
  "pruneNotification": "minimal",
  "tools": {
    "prune": { "permission": "ask" },
    "distill": { "permission": "allow" },
    "compress": { "permission": "deny" }
  },
  "strategies": {
    "deduplication": { "enabled": true },
    "supersedeWrites": { "enabled": false },
    "purgeErrors": { "enabled": true, "turns": 10 }
  }
}
```

### 方案3: 手动控制

**目标**: 完全由用户控制清理时机

```json
{
  "$schema": "https://raw.githubusercontent.com/Opencode-DCP/opencode-dynamic-context-pruning/master/dcp.schema.json",
  "enabled": true,
  "tools": {
    "prune": { "permission": "deny" },
    "distill": { "permission": "deny" },
    "compress": { "permission": "deny" }
  },
  "strategies": {
    "deduplication": { "enabled": false },
    "supersedeWrites": { "enabled": false },
    "purgeErrors": { "enabled": false }
  }
}
```

**说明**: 完全关闭自动策略和工具，只在必要时手动调用（通过命令行或其他方式）。

---

## 六、后续行动事项

### 6.1 立即行动
- [ ] 测试方案1的保守配置效果
- [ ] 监控 prune 频率是否降低
- [ ] 确认历史记录保留情况

### 6.2 短期行动
- [ ] 整理正确的配置文档
- [ ] 备份当前配置以便回滚
- [ ] 测试不同配置组合的效果

### 6.3 长期行动
- [ ] 关注 DCP 插件更新
- [ ] 评估是否需要更换其他上下文管理方案
- [ ] 建立 DCP 使用规范

---

## 七、参考资料

### 7.1 官方资源
- GitHub: https://github.com/Tarquinen/opencode-dynamic-context-pruning
- npm: https://www.npmjs.com/package/@tarquinen/opencode-dcp
- Schema: https://raw.githubusercontent.com/Opencode-DCP/opencode-dynamic-context-pruning/master/dcp.schema.json

### 7.2 本地路径
- 配置文件: `C:\Users\40968\.config\opencode\dcp.jsonc`
- 插件目录: `C:\Users\40968\.config\opencode\plugins\@tarquinen\opencode-dcp\`
- 包信息: `C:\Users\40968\.config\opencode\plugins\@tarquinen\opencode-dcp\package.json`
- 源代码: `C:\Users\40968\.config\opencode\plugins\@tarquinen\opencode-dcp\dist\index.js`

### 7.3 相关文档
- OpenCode Tools: https://opencode.ai/docs/tools/
- DCP Troubleshooting: https://github.com/Tarquinen/opencode-dynamic-context-pruning/blob/master/TROUBLESHOOTING.md

---

## 八、配置项完整说明

### 8.1 顶层配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | boolean | true | 是否启用 DCP |
| `debug` | boolean | false | 是否启用调试模式 |
| `pruneNotification` | string | "detailed" | 清理通知级别 (off/minimal/detailed) |
| `pruneNotificationType` | string | "chat" | 通知类型 |

### 8.2 Tools 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `tools.settings.nudgeEnabled` | boolean | true | 是否启用清理提示 |
| `tools.settings.nudgeFrequency` | number | 10 | 提示频率(轮数) |
| `tools.settings.contextLimit` | number | 100000 | 上下文限制(token) |
| `tools.prune.permission` | string | "allow" | prune工具权限 (allow/ask/deny) |
| `tools.distill.permission` | string | "allow" | distill工具权限 (allow/ask/deny) |
| `tools.compress.permission` | string | "allow" | compress工具权限 (allow/ask/deny) |

### 8.3 Strategies 配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `strategies.deduplication.enabled` | boolean | true | 是否启用去重策略 |
| `strategies.supersedeWrites.enabled` | boolean | true | 是否启用替代写入策略 |
| `strategies.purgeErrors.enabled` | boolean | true | 是否启用错误清理策略 |
| `strategies.purgeErrors.turns` | number | 4 | 错误保留轮数 |

---

**文档更新时间**: 2026-02-10 06:29:53  
**下次审查时间**: 2026-02-17

---

## 备注

本笔记记录了 DCP 插件 v2.0.2 的详细调查过程。

**核心发现修正**:
- ✅ 实际提供的工具: `prune`, `distill`, `compress`
- ✅ 工具名称与 GitHub 文档一致，无版本混乱
- ❌ 之前错误地认为存在 `discard` 和 `extract` 工具

**问题根因**: 默认配置过于激进，而非工具名称混乱。

**重要提醒**: 任何配置修改前请先备份当前配置！
