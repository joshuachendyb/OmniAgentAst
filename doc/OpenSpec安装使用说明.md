# OpenSpec 安装与使用说明文档

**创建时间**: 2026-04-02 08:04:24  
**版本**: v1.0  
**作者**: 小欧

---

## 一、OpenSpec 是什么

OpenSpec 是一个 **AI编程助手的规范驱动开发框架**（Spec-driven Development）。

**核心功能**：
- 帮助人类与 AI 在写代码之前先对齐"要构建什么"
- 通过规范（Spec）管理需求、设计、实现过程
- 支持 20+ AI 助手工具（Claude、Cursor、Windsurf 等）

**官方网站**：https://openspec.dev/

---

## 二、安装

### 2.1 前置条件

| 要求 | 说明 |
|------|------|
| Node.js | 20.19.0 或更高版本 |
| 检查命令 | `node --version` |

### 2.2 安装命令

**npm 安装（推荐）**：
```bash
npm install -g @studyzy/openspec-cn@latest
```

**其他包管理器**：
```bash
# pnpm
pnpm add -g @studyzy/openspec-cn@latest

# yarn
yarn global add @studyzy/openspec-cn@latest

# bun
bun add -g @studyzy/openspec-cn@latest
```

### 2.3 验证安装

```bash
openspec-cn --version
```

---

## 三、初始化项目

### 3.1 基本初始化

```bash
cd 你的项目目录
openspec-cn init
```

初始化后，项目目录结构如下：

```
openspec/
├── specs/              # 单一事实来源（系统当前行为规范）
│   └── <domain>/
│       └── spec.md
├── changes/            # 提议的变更（每个变更一个文件夹）
│   └── <change-name>/
│       ├── proposal.md
│       ├── design.md
│       ├── tasks.md
│       └── specs/      # 增量规范
└── config.yaml         # 项目配置（可选）
```

### 3.2 刷新代理指令

每次安装后运行一次，用于重新生成 AI 指引：

```bash
openspec-cn update
```

---

## 四、基本使用流程

### 4.1 工作流程图

```
┌────────────────────┐
│ 开始变更            │  /opsx:new
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 创建制品            │  /opsx:ff 或 /opsx:continue
│ (proposal, specs,  │
│  design, tasks)    │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 实施任务            │  /opsx:apply
│ (AI 编写代码)       │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ 归档并合并规范       │  /opsx:archive
└────────────────────┘
```

### 4.2 核心命令

| 命令 | 功能 | 说明 |
|------|------|------|
| `/opsx:new <名称>` | 开始新变更 | 创建变更文件夹 |
| `/opsx:ff` | 快进 | 一次性创建所有规划制品 |
| `/opsx:continue` | 继续 | 逐步创建制品 |
| `/opsx:apply` | 应用 | 开始实施任务 |
| `/opsx:archive` | 归档 | 合并规范并清理 |
| `/opsx:propose <需求>` | 提议 | 向 AI 提出需求 |

---

## 五、制品说明

每个变更文件夹包含以下制品：

| 制品 | 用途 |
|------|------|
| `proposal.md` | "为什么"和"做什么" - 捕获意图、范围和方法 |
| `specs/` | 增量规范，显示新增/修改/删除的需求 |
| `design.md` | "如何做" - 技术方法和架构决策 |
| `tasks.md` | 带复选框的实施清单 |

---

## 六、CLI 命令参考

### 6.1 常用命令

```bash
# 查看版本
openspec-cn --version

# 初始化项目
openspec-cn init

# 刷新代理指令
openspec-cn update

# 列出所有活动变更
openspec-cn list

# 查看变更详情
openspec-cn show <变更名称>

# 验证规范格式
openspec-cn validate <变更名称>

# 交互式仪表盘
openspec-cn view
```

### 6.2 配置命令

```bash
# 选择扩展工作流
openspec-cn config profile
```

---

## 七、使用示例

### 示例：添加深色模式功能

**1. 开始变更**
```
你：/opsx:new add-dark-mode

AI：已创建 openspec/changes/add-dark-mode/
     准备创建：proposal
```

**2. 创建制品**
```
你：/opsx:ff

AI：正在为 add-dark-mode 创建制品...
     ✓ proposal.md — 为什么要做，有什么变化
     ✓ specs/       — 需求和场景
     ✓ design.md   — 技术方法
     ✓ tasks.md    — 实施清单
     准备实施！
```

**3. 实施任务**
```
你：/opsx:apply

AI：正在处理任务...
     ✓ 1.1 创建了 ThemeContext
     ✓ 1.2 添加了 CSS 变量
     ...
     所有任务完成！
```

**4. 归档**
```
你：/opsx:archive

AI：正在归档 add-dark-mode...
     ✓ 已将规范合并到 specs/
     ✓ 已移动到 archive/
     完成！
```

---

## 八、注意事项

### 8.1 模型选择
OpenSpec 更适合高推理模型，推荐使用 **Claude Opus 4.5** 和 **GPT 5.2**。

### 8.2 上下文卫生
- 开始实现前清理上下文
- 保持良好的上下文卫生

### 8.3 退出遥测
如需禁用遥测：
```bash
export OPENSPEC_TELEMETRY=0
# 或
export DO_NOT_TRACK=1
```

---

## 九、相关链接

| 资源 | 地址 |
|------|------|
| GitHub 仓库 | https://github.com/studyzy/OpenSpec-cn |
| npm 包 | https://www.npmjs.com/package/@studyzy/openspec-cn |
| 官方网站 | https://openspec.dev/ |
| Discord 社区 | https://discord.gg/YctCnvvshC |

---

## 十、版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-04-02 08:04:24 | 小欧 | 初始版本：安装说明、基本使用、命令参考 |