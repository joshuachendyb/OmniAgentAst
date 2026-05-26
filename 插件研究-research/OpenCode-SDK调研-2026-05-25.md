# OpenCode JS/TS SDK 调研

**创建时间**: 2026-05-25 10:18:38  
**数据来源**: https://opencode.ai/docs/sdk  
**SDK 包名**: `@opencode-ai/sdk`  
**版本**: v1.0  
**编写人**: 小欧

---

## 1 概述

OpenCode JS/TS SDK 是一个**类型安全的客户端**，用于以编程方式控制 OpenCode 服务器。你可以通过 SDK 构建集成工具，程序化地操控 OpenCode。

---

## 2 安装

```bash
npm install @opencode-ai/sdk
```

---

## 3 两种使用模式

### 3.1 一体化模式（自动启动服务器+客户端）

```typescript
import { createOpencode } from "@opencode-ai/sdk"
const { client } = await createOpencode()
```

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| hostname | string | 服务器主机 | 127.0.0.1 |
| port | number | 服务器端口 | 4096 |
| signal | AbortSignal | 取消信号 | undefined |
| timeout | number | 超时(ms) | 5000 |
| config | Config | 配置对象 | {} |

### 3.2 纯客户端模式（连接到已有服务器）

```typescript
import { createOpencodeClient } from "@opencode-ai/sdk"
const client = createOpencodeClient({ baseUrl: "http://localhost:4096" })
```

---

## 4 API 总览

### 4.1 全局

| 方法 | 说明 | 返回 |
|------|------|------|
| `client.global.health()` | 检查服务器健康状态 | `{ healthy, version }` |

### 4.2 应用

| 方法 | 说明 |
|------|------|
| `client.app.log()` | 写入日志 |
| `client.app.agents()` | 列出所有可用 Agent |

### 4.3 项目

| 方法 | 说明 |
|------|------|
| `client.project.list()` | 列出所有项目 |
| `client.project.current()` | 获取当前项目 |

### 4.4 路径

| 方法 | 说明 |
|------|------|
| `client.path.get()` | 获取当前路径信息 |

### 4.5 配置

| 方法 | 说明 |
|------|------|
| `client.config.get()` | 获取配置信息 |
| `client.config.providers()` | 列出所有 Provider 和默认模型 |

### 4.6 会话 (Sessions) — 核心 API

| 方法 | 说明 |
|------|------|
| `client.session.list()` | 列出会话 |
| `client.session.get()` | 获取单个会话 |
| `client.session.children()` | 获取子会话列表 |
| `client.session.create()` | 创建会话 |
| `client.session.delete()` | 删除会话 |
| `client.session.update()` | 更新会话属性 |
| `client.session.init()` | 分析项目并创建 AGENTS.md |
| `client.session.abort()` | 中止运行中的会话 |
| `client.session.share()` | 分享会话（生成链接） |
| `client.session.unshare()` | 取消分享 |
| `client.session.summarize()` | 总结会话 |
| `client.session.messages()` | 列出会话消息 |
| `client.session.message()` | 获取单条消息详情 |
| **`client.session.prompt()`** | **发送提示消息**（核心） |
| `client.session.command()` | 发送命令到会话 |
| `client.session.shell()` | 执行 Shell 命令 |
| `client.session.revert()` | 撤销消息 |
| `client.session.unrevert()` | 恢复已撤销消息 |

### 4.7 文件操作

| 方法 | 说明 |
|------|------|
| `client.find.text()` | 在文件中搜索文本 |
| `client.find.files()` | 按名称查找文件/目录 |
| `client.find.symbols()` | 查找符号 |
| `client.file.read()` | 读取文件内容 |
| `client.file.status()` | 获取文件状态 |

### 4.8 TUI 控制

| 方法 | 说明 |
|------|------|
| `client.tui.appendPrompt()` | 追加文本到提示框 |
| `client.tui.openHelp()` | 打开帮助 |
| `client.tui.openSessions()` | 打开会话选择器 |
| `client.tui.openThemes()` | 打开主题选择器 |
| `client.tui.openModels()` | 打开模型选择器 |
| `client.tui.submitPrompt()` | 提交当前提示 |
| `client.tui.clearPrompt()` | 清空提示 |
| `client.tui.executeCommand()` | 执行命令 |
| `client.tui.showToast()` | 显示 Toast 通知 |

### 4.9 认证

| 方法 | 说明 |
|------|------|
| `client.auth.set()` | 设置认证凭据 |

### 4.10 事件 (SSE)

| 方法 | 说明 |
|------|------|
| `client.event.subscribe()` | 订阅实时事件流 (SSE) |

---

## 5 结构化输出 (Structured Output)

支持 JSON Schema 格式的结构化输出：

```typescript
const result = await client.session.prompt({
  path: { id: sessionId },
  body: {
    parts: [{ type: "text", text: "查询公司信息" }],
    format: {
      type: "json_schema",
      schema: {
        type: "object",
        properties: {
          company: { type: "string" },
          founded: { type: "number" },
          products: { type: "array", items: { type: "string" } },
        },
        required: ["company", "founded"],
      },
    },
  },
})
```

---

## 6 类型定义

```typescript
import type { Session, Message, Part } from "@opencode-ai/sdk"
```

所有类型定义从 OpenAPI spec 自动生成，位于:  
https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts

---

## 7 应用场景

| 场景 | 使用方式 |
|------|---------|
| **构建 IDE 插件** | 用 `session.prompt()` 和 `find.*` API 实现代码辅助 |
| **自动化工作流** | 用 `session.create()` + `session.prompt()` 实现批处理 |
| ** CI/CD 集成** | 用 `session.shell()` 执行命令并检查结果 |
| **实时监控** | 用 `event.subscribe()` 订阅 Agent 运行状态 |
| **自定义 UI** | 用 TUI API 控制 OpenCode 界面 |

---

## 版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-05-25 10:18:38 | 初始版本，SDK 功能总览 | 小欧 |
