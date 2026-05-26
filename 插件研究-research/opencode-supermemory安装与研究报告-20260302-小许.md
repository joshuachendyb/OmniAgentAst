# opencode-supermemory 安装与研究报告

**创建时间**: 2026-03-02 18:23:04  
**分析人**: 小许（专家级需求分析师）  
**用户**: 北京老陈  
**来源**: https://github.com/supermemoryai/opencode-supermemory

---

## 一、项目概述

### 1.1 项目定位

**opencode-supermemory** 是一个为 **OpenCode** 提供持久化记忆功能的插件。

**核心理念**：让AI助手记住你告诉它的一切 —— **跨会话、跨项目**。

**项目统计**：
- ⭐ **Stars**: 717
- 🔀 **Forks**: 54
- 👨‍💻️ **Contributors**: 10
- 💻 **Languages**: TypeScript (76.3%), JavaScript (22.0%), Shell (1.7%)
- 📦 **License**: MIT

---

## 二、主要功能

### 2.1 上下文自动注入

**功能描述**：在每次对话开始时，自动向AI注入上下文信息（对用户不可见）。

**注入内容包括**：

#### 2.1.1 用户画像
- 跨项目偏好设置
- 技能专长（如：TypeScript专家）
- 编码风格偏好

#### 2.1.2 项目记忆
- 项目技术栈（如：100%使用Bun，不用Node.js）
- 构建命令（如：bun run build）
- 项目架构知识

#### 2.1.3 相关用户记忆（语义搜索）
- 通过语义搜索找到相关记忆
- 按相似度排序

**示例**（AI看到的上下文）：
```
[SUPERMEMORY]

User Profile:
- Prefers concise responses
- Expert in TypeScript

Project Knowledge:
- [100%] Uses Bun, not Node.js
- [100%] Build: bun run build

Relevant Memories:
- [82%] Build fails if .env.local missing
```

### 2.2 关键词检测

**功能描述**：检测用户输入中的关键词，自动保存到记忆。

**触发关键词**：
- "remember"
- "save this"
- "don't forget"
- "记住"
- "保存"

**示例**：
```
你: "Remember that this project uses bun"
AI: [自动保存到项目记忆]
```

**自定义关键词**：可通过 `keywordPatterns` 配置项添加自定义触发模式。

### 2.3 代码库索引

**功能描述**：探索并记忆代码库结构、模式和约定。

**触发命令**：`/supermemory-init`

**索引内容**：
- 代码库结构
- 编码模式
- 命名约定
- 依赖关系

### 2.4 预防性压缩

**功能描述**：当上下文使用率达到80%时，自动触发压缩机制。

**工作流程**：
1. 检测到上下文使用率达到80%
2. 触发OpenCode的上下文压缩
3. 将项目记忆注入到摘要上下文
4. 保存会话摘要作为记忆

**作用**：在上下文压缩时保留会话上下文。

---

## 三、可用工具

### 3.1 supermemory 工具

| 模式 | 参数 | 描述 |
|------|------|------|
| `add` | `content`, `type?`, `scope?` | 存储记忆 |
| `search` | `query`, `scope?` | 搜索记忆 |
| `profile` | `query?` | 查看用户画像 |
| `list` | `scope?`, `limit?` | 列出记忆 |
| `forget` | `memoryId`, `scope?` | 删除记忆 |

### 3.2 记忆作用域

| 作用域 | 标签 | 持久化范围 |
|--------|------|-----------|
| `user` | `opencode_user_{hash(git email)}` | 所有项目 |
| `project` | `opencode_project_{hash(directory)}` | 当前项目 |

### 3.3 记忆类型

| 类型 | 说明 |
|------|------|
| `project-config` | 项目配置 |
| `architecture` | 架构信息 |
| `error-solution` | 错误解决方案 |
| `preference` | 用户偏好 |
| `learned-pattern` | 学习到的模式 |
| `conversation` | 对话记忆 |

---

## 四、隐私保护

### 4.1 私有标签

**功能描述**：`<private>`标签中的内容永远不会被存储。

**示例**：
```
API key is <private>sk-abc123</private>
```

**结果**：只有`API key is `会被存储，`sk-abc123`不会被存储。

---

## 五、配置选项

### 5.1 配置文件

创建 `~/.config/opencode/supermemory.jsonc`：

```jsonc
{
  // API key（也可以使用 SUPERMEMORY_API_KEY 环境变量）
  "apiKey": "sm_...",

  // 记忆检索的最小相似度（0-1）
  "similarityThreshold": 0.6,

  // 每次请求注入的最大记忆数
  "maxMemories": 5,

  // 列出的最大项目记忆数
  "maxProjectMemories": 10,

  // 注入的最大用户画像项数
  "maxProfileItems": 5,

  // 是否在上下文中包含用户画像
  "injectProfile": true,

  // 容器标签前缀（默认：opencode）
  "containerTagPrefix": "opencode",

  // 可选：设置精确的用户容器标签（覆盖自动生成的标签）
  "userContainerTag": "my-custom-user-tag",

  // 可选：设置精确的项目容器标签（覆盖自动生成的标签）
  "projectContainerTag": "my-project-tag",

  // 额外的关键词检测模式（正则表达式）
  "keywordPatterns": ["log\\s+", "write\\s+down"],

// 触发压缩的上下文使用率（0-1）
  "compactionThreshold": 0.80
}
```

### 5.2 容器标签选择

**默认行为**：自动生成标签
- 用户标签：`{prefix}_user_{hash(git_email)}`
- 项目标签：`{prefix}_project_{hash(directory)}`

**自定义行为**：精确指定标签
```jsonc
{
  "userContainerTag": "my-team-workspace",
  "projectContainerTag": "my-awesome-project"
}
```

**用途**：
- 在团队成员间共享记忆（相同的 `userContainerTag`）
- 在不同机器间同步同一项目的记忆
- 使用自定义命名方案组织记忆

---

## 六、安装过程

### 6.1 环境检查

✅ **Bun 已安装**：版本 1.3.6  
✅ **OpenCode 配置文件存在**：`~/.config/opencode/opencode.jsonc`  
✅ **API Key 已提供**：`sm_Kkx8RHLYVkXsD3XvjhTfNx_cJMqDTvomzvyzlvLmhvaiiBAevqrmehGriTpEpqsWalfrJHsPjqzVbzoINwcjZpn`

### 6.2 插件安装

**安装命令**：
```bash
bunx opencode-supermemory@latest install --no-tui
```

**安装结果**：
```
✓ Added plugin to C:\Users\40968\.config\opencode\opencode.jsonc
✓ Created /supermemory-init command
✓ Created /supermemory-login command
```

### 6.3 API Key 配置

**配置文件**：`~/.config/opencode/supermemory.jsonc`

**配置内容**：
```jsonc
{
  "apiKey": "sm_Kkx8RHLYVkXsD3XvjhTfNx_cJMqDTvomzvyzlvLmhvaiiBAevqrmehGriTpEpqsWalfrJHsPjqzVbzoINwcjZpn"
}
```

---

## 七、验证结果

### 7.1 插件注册状态

✅ **插件已注册**：`opencode-supermemory@latest` 在 `opencode.jsonc` 中

### 7.2 命令创建状态

⚠️ **命令未找到**：`/supermemory-init` 和 `/supermemory-login` 命令在 `opencode --help` 中不可见

**可能原因**：
1. 命令可能需要重启 OpenCode 后才可用
2. 命令可能需要通过其他方式调用（如直接运行脚本）

### 7.3 配置文件状态

✅ **API Key 配置成功**：`~/.config/opencode/supermemory.jsonc` 文件已创建并包含正确的 API Key

---

## 八、兼容性说明

### 8.1 与 Oh My OpenCode 兼容

如果你使用的是 [Oh My OpenCode](https://github.com/code-yeongyu/oh-my-opencode)，需要禁用其内置的自动压缩钩子，让 supermemory 处理上下文压缩。

**配置方法**：
在 `~/.config/opencode/oh-my-opencode.json` 中添加：
```jsonc
{
  "disabled_hooks": ["anthropic-context-window-limit-recovery"]
}
```

---

## 九、使用示例

### 9.1 基本使用

**场景1：让AI记住项目信息**
```
你: "记住这个项目使用Bun而不是Node.js"
AI: [自动保存到项目记忆]
```

**场景2：查询记忆**
```
你: "这个项目使用什么运行时？"
AI: [检索项目记忆] -> "这个项目使用Bun作为运行时"
```

**场景3：跨项目记忆**
```
你: "我通常喜欢简洁的回答"
AI: [保存到用户画像]
```

### 9.2 初始化代码库记忆

**如果需要让 AI 学习代码库结构**：
```bash

/supermemory-init
```

---

## 十、下一步操作建议

### 10.1 重启 OpenCode

**建议**：重启 OpenCode 后，插件会完全激活

**验证方法**：
```bash
opencode --help
```

应该能看到 `supermemory-init` 和 `supermemory-login` 命令。

### 10.2 验证插件加载

**重启后运行**：
```bash
opencode -c
```

应该能看到 `supermemory` 工具在工具列表中。

### 10.3 初始化代码库记忆（可选）

**如果需要让 AI 学习代码库结构**：
```bash
/supermemory-init
```

---

## 十一、已知问题

### 11.1 命令未在 help 中显示

**现象**：`/supermemory-init` 和 `/supermemory-login` 命令在 `opencode --help` 中不可见

**可能原因**：
1. 插件可能需要在 OpenCode 完全启动后才能注册命令
2. 命令可能需要通过特定方式调用

**解决方案**：
- 重启 OpenCode 后再次检查
- 查看插件文档了解命令使用方式
- 检查日志文件：`~/.opencode-supermemory.log`

---

## 十二、总结与建议

### 12.1 核心价值

1. **跨会话记忆**：AI可以记住之前对话的内容
2. **跨项目记忆**：AI可以记住不同项目的共性和模式
3. **自动上下文注入**：无需手动提示，AI自动获取相关上下文
4. **代码库索引**：AI自动学习代码库结构和模式
5. **隐私保护**：支持`<private>`标签保护敏感信息

### 12.2 适用场景

- ✅ 长期项目开发（需要AI记住项目约定）
- ✅ 多项目并行开发（需要AI记住跨项目偏好）
- ✅ 频繁切换会话（需要AI记住上下文）
- ✅ 团队协作（共享项目记忆）

### 12.3 安装完成状态

**已完成**：
- ✅ Bun 环境检查通过
- ✅ opencode-supermemory 插件件安装成功
- ✅ 插件已注册到 OpenCode 配置
- ✅ API Key 配置成功
- ⚠️ 命令未在 help 中显示（可能需要重启 OpenCode）

**待完成**：
- ⏳ 重启 OpenCode 激活插件
- ⏳ 验证 `supermemory` 工具是否可用
- ⏳ 可选：运行 `/supermemory-init` 初始化代码库记忆

---

**报告完成时间**: 2026-03-02 18:23:04  
**分析人**: 小许（专家级需求分析师）  
**用户**: 北京老陈  
**建议**: 请重启 OpenCode 后验证插件是否完全激活
