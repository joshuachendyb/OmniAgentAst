# GSD 使用手册

**GSD** (Get Shit Done) 项目管理实践指南

**版本**: v1.3
**更新时间**: 2026-04-12 15:10:00
**作者**: 小资

---

## 一、GSD 是什么

GSD 是一套为 AI 辅助开发量身打造的项目管理方法论和工具链，专注于帮助独立开发者或小团队在 Claude Code 环境下进行高效、有组织的软件开发。

核心理念：
- **层次化规划**：将复杂项目拆分为可管理的阶段和波次
- **验证驱动**：每个交付物都有明确的验证标准
- **上下文传承**：完整的项目状态跟踪，支持会话恢复

---

## 二、核心命令详解

### 2.1 项目初始化

#### `/gsd-new-project`
**功能**：初始化新项目，包含完整的需求分析和路线图

**何时使用**：
- 全新的项目，从零开始
- 需要制定长期规划和里程碑

**交互流程**：
1. 深度提问，了解你要做什么
2. 可选：研究技术生态
3. 定义需求范围（v1/v2/不属于范围）
4. 创建路线图（阶段分解）

**示例**：
```
/gsd-new-project
# GSD 会提问：
# - 你要构建什么项目？
# - 核心功能有哪些？
# - 有什么技术偏好？
# - 预期里程碑是什么？
```

**生成文件**：`.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`

---

#### `/gsd-map-codebase`
**功能**：分析现有代码库，生成结构化文档

**何时使用**：
- 已有项目需要了解现状
- 存量项目（brownfield）
- 接手不熟悉的代码库

**示例**：
```
/gsd-map-codebase
# 分析现有代码库，生成 7 个文档
# STACK.md - 技术栈
# ARCHITECTURE.md - 架构
# STRUCTURE.md - 目录结构
# CONVENTIONS.md - 编码规范
# TESTING.md - 测试
# INTEGRATIONS.md - 外部集成
# CONCERNS.md - 技术债务
```

---

### 2.2 阶段规划

#### `/gsd-discuss-phase <num>`
**功能**：讨论并明确某个阶段的愿景和目标

**何时使用**：
- 开始规划前，需要理清思路
- 不确定某个阶段要做什么
- 需要与用户确认需求

**示例**：
```
/gsd-discuss-phase 1
# GSD 会问：
# - 这个阶段要实现什么？
# - 你期望的效果是什么？
# - 有什么边界情况？
# - 如何判断完成了？
```

---

#### `/gsd-research-phase <num>`
**功能**：研究特定领域的最佳实践和技术生态

**何时使用**：
- 涉及不熟悉的技术领域
- 需要了解行业标准做法
- 避免重复造轮子

**示例**：
```
/gsd-research-phase 2
# 研究第2阶段相关的技术
# 生成 RESEARCH.md
# 包含：标准做法、常见模式、注意事项
```

---

#### `/gsd-plan-phase <num>`
**功能**：创建详细的执行计划

**何时使用**：
- 需求已经明确
- 需要拆解成可执行的任务
- 准备开始执行

**示例**：
```
/gsd-plan-phase 1
# 生成 .planning/phases/01-xxx/01-01-PLAN.md
# 包含：
# - 具体任务列表
# - 任务依赖关系
# - 验证标准
# - 成功标准
```

**计划文件结构**：
```markdown
# Plan: 01-01-PLAN.md

## Tasks
- [ ] Task 1: 实现骨架屏
- [ ] Task 2: 添加加载状态

## Dependencies
- Task 2 依赖 Task 1 完成

## Verification
- 验证页面加载时间 < 1秒
```

---

#### `/gsd-list-phase-assumptions <num>`
**功能**：查看当前的规划假设（还没开始执行）

**何时使用**：
- 执行前想确认规划是否正确
- 想提前纠正误解

**示例**：
```
/gsd-list-phase-assumptions 2
# 显示第2阶段的规划假设
# 不修改任何文件，只做展示
```

---

### 2.3 执行

#### `/gsd-execute-phase <num>`
**功能**：执行指定阶段的所有计划

**何时使用**：
- 计划已经创建完成
- 准备开始动手实现

**示例**：
```
/gsd-execute-phase 1
# 执行第1阶段的所有任务
# 按波次（wave）顺序执行
# 完成后生成 SUMMARY.md
# 更新 ROADMAP.md 状态
```

**执行流程**：
1. 按 wave 顺序执行
2. 每个任务用子代理并行执行
3. 验证任务完成度
4. 生成执行总结

---

### 2.4 快速任务

#### `/gsd-quick [--flags]`
**功能**：快速执行临时小任务，跳过完整流程

**何时使用**：
- 临时性的需求
- 小范围优化
- 紧急修复

**Flags（可组合）**：
| Flag | 说明 |
|------|------|
| 无 | 基本快速任务 |
| `--discuss` | 轻量讨论 |
| `--research` | 包含研究 |
| `--full` | 完整验证（检查+验证）|

**示例**：
```
/gsd-quick                          # 最简单的任务
/gsd-quick --research               # 带研究
/gsd-quick --full                 # 完整流程
/gsd-quick --discuss --research     # 组合使用
```

---

#### `/gsd-do <描述>`
**功能**：智能路由，把自然语言转成合适的 GSD 命令

**何时使用**：
- 不确定该用哪个命令
- 只想说需求，不想选命令

**示例**：
```
/gsd-do 修复登录按钮不工作
# GSD 自动判断：
# - 这是一个 bug
# - 建议用 /gsd-debug
# 或 /gsd-quick "修复登录按钮"

/gsd-do 添加用户管理功能
# GSD 判断：
# - 这需要规划
# - 建议用 /gsd-plan-phase
```

---

### 2.5 路线图管理

#### `/gsd-add-phase <描述>`
**功能**：在路线图末尾添加新阶段

**示例**：
```
/gsd-add-phase "用户权限管理"
# 在 ROADMAP.md 末尾添加
# 阶段编号自动递增
```

---

#### `/gsd-insert-phase <��置> <描述>`
**功能**：在现有阶段之间插入新阶段

**示例**：
```
/gsd-insert-phase 3 "安全修复"
# 在阶段3和4之间插入
# 新阶段编号：3.1
```

---

#### `/gsd-remove-phase <num>`
**功能**：删除未开始的阶段

**示例**：
```
/gsd-remove-phase 5
# 删除第5阶段
# 后续阶段自动重新编号
```

---

### 2.6 里程碑

#### `/gsd-new-milestone <名称>`
**功能**：创建新的里程碑（版本发布）

**示例**：
```
/gsd-new-milestone "v2.0 功能"
# 类似 new-project
# 重新定义需求和路线图
```

---

#### `/gsd-complete-milestone <版本>`
**功能**：完成里程碑，创建归档

**示例**：
```
/gsd-complete-milestone 1.0.0
# 创建归档
# 生成 git tag
# 准备下一版本
```

---

### 2.7 进度追踪

#### `/gsd-progress`
**功能**：查看当前项目进度

**示例**：
```
/gsd-progress
# 显示：
# - 进度条
# - 完成百分比
# - 当前阶段
# - 下一步建议
```

---

#### `/gsd-resume-work`
**功能**：恢复之前的工作会话

**何时使用**：
- 重新打开项目
- 继续之前的开发

---

#### `/gsd-pause-work`
**功能**：暂停工作，保存上下文

**何时使用**：
- 需要中断工作
- 临时切换任务

---

### 2.8 调试

#### `/gsd-debug <问题描述>`
**功能**：系统化调试会话

**何时使用**：
- 遇到 bug
- 不清楚问题原因

**示例**：
```
/gsd-debug "登录按钮点击没反应"
# 科学方法调试
# 创建 .planning/debug/ 记录
# 不惧 context 重置
```

---

### 2.9 笔记和待办

#### `/gsd-note <文本>`
**功能**：快速记录想法

**示例**：
```
/gsd-note 重构 message 组件        # 记录想法
/gsd-note list                 # 查看所有笔记
/gsd-note promote 3            # 将第3条转为待办
```

---

#### `/gsd-add-todo <描述>`
**功能**：创建待办事项

**示例**：
```
/gsd-add-todo                  # 从对话内容提取
/gsd-add-todo 优化加载速度     # 明确描述
```

---

#### `/gsd-check-todos`
**功能**：查看和选择待办

**示例**：
```
/gsd-check-todos               # 查看所有
/gsd-check-todos frontend     # 按领域筛选
```

---

### 2.10 验证和交付

#### `/gsd-verify-work [阶段]`
**功能**：用户验收测试

**何时使用**：
- 阶段完成
- 需要用户确认

**示例**：
```
/gsd-verify-work 1
# 逐项展示交付物
# 用户逐项确认：是/否
# 失败自动创建修复计划
```

---

#### `/gsd-ship [阶段]`
**功能**：创建 PR 并交付

**何时使用**：
- 验收通过
- 准备交付

**示例**：
```
/gsd-ship 1                     # 创建 PR
/gsd-ship 1 --draft          # 草稿PR
```

---

### 2.11 审计

#### `/gsd-audit-milestone [版本]`
**功能**：审计里程碑完成度

**示例**：
```
/gsd-audit-milestone
# 检查所有阶段
# 生成审计报告
```

---

#### `/gsd-plan-milestone-gaps`
**功能**：根据审计结果创建弥补计划

---

### 2.12 工具

#### `/gsd-settings`
**功能**：配置工作流设置

**示例**：
```
/gsd-settings
# 交互式配置
# - 开关 researcher
# - 开关 verifier
# - 选择模型配置
```

---

#### `/gsd-set-profile <配置>`
**功能**：切换模型配置

**示例**：
```
/gsd-set-profile quality      # 全部 Opus
/gsd-set-profile balanced  # 规划用 Opus
/gsd-set-profile budget   # 用 Haiku
```

---

#### `/gsd-cleanup`
**功能**：清理归档旧阶段

---

#### `/gsd-update`
**功能**：更新 GSD 工具

---

## 三、文件结构

```
.planning/
├── PROJECT.md              # 项目愿景
├── ROADMAP.md              # 阶段路线图
├── STATE.md                # 项目状态和上下文
├── RETROSPECTIVE.md         # 回顾总结
├── config.json             # 工作流配置
├── todos/                 # 待办事项
│   ├── pending/           # 待处理
│   └── done/             # 已完成
├── debug/                 # 调试会话
│   └── resolved/         # 已解决的问题
├── milestones/           # 里程碑归档
│   └── v1.0-phases/     # 各版本阶段
├── codebase/             # 代码库映射（ brownfield 项目）
│   ├── STACK.md
│   ├── ARCHITECTURE.md
│   ├── STRUCTURE.md
│   ├── CONVENTIONS.md
│   ├── TESTING.md
│   ├── INTEGRATIONS.md
│   └── CONCERNS.md
└── phases/               # 阶段目录
    ├── 01-foundation/
    │   ├── 01-01-PLAN.md
    │   └── 01-01-SUMMARY.md
    └── 02-core-features/
        ├── 02-01-PLAN.md
        └── 02-01-SUMMARY.md
```

---

## 四、工作流程

### 4.1 新项目开发

```
/gsd-new-project        # 初始化：提问 → 研究 → 需求 → 路线图
/clear
/gsd-plan-phase 1       # 创建第一阶段的计划
/clear
/gsd-execute-phase 1    # 执行第一阶段
```

### 4.2 存量项目（现有代码库）

适用于已有项目需要进行规范化管理或功能扩展：

```
/gsd-map-codebase    # 第1步：分析现有代码库
# 阅读 .planning/codebase/ 下的文档了解项目现状
/gsd-plan-phase 1  # 第2步：创建第一个阶段的计划
/gsd-execute-phase 1 # 第3步：执行计划
```

**映射代码库会生成**：
- `STACK.md` - 技术栈、框架、依赖
- `ARCHITECTURE.md` - 架构模式、数据流
- `STRUCTURE.md` - 目录结构、关键文件
- `CONVENTIONS.md` - 编码规范、命名约定
- `TESTING.md` - 测试设置、模式
- `INTEGRATIONS.md` - 外部服务、API
- `CONCERNS.md` - 技术债务、已知问题

### 4.3 实际案例：前端性能优化 - 问题1（启动加载慢）

#### 问题背景

**项目**：OmniAgentAs-desk 前端应用  
**问题**：启动加载慢 → 页面空白  
**影响**：用户体验差，首屏等待时间长  
**优先级**：P0

#### 问题分析流程

根据代码库分析，问题在于：
1. 页面结构：`frontend/src/components/Layout/index.tsx`
2. 渲染流程：先加载布局，再加载内容
3. 空白原因：内容区渲染前没有占位

#### 优化方案：骨架屏方案

**方案A**：Layout 骨架屏（阶段1-4）
- Header 骨架：模拟导航栏
- Sider 骨架：模拟侧边栏
- Content 骨架：模拟主内容区

**方案B**：消息列表骨架屏（阶段5）
- 模拟真实消息结构显示

#### GSD 执行流程

**第1步：讨论问题（明确需求）**

```
/gsd-discuss-phase 1
# GSD 提问：
# 1. 首屏加载具体是哪里慢？布局还是内容？
# 2. 期望骨架屏显示在哪些位置？
# 3. 骨架屏样式要求和现有设计一致吗？
# 4. 完成后如何验证？
```

**回答示例**：
- 布局加载后内容区空白
- Header、Sider、Content 都需要骨架屏
- UI要和现有 Layout 保持一致
- 首屏加载时间 < 1秒

**第2步：创建计划**

```
/gsd-plan-phase 1
# 生成计划文件：
# .planning/phases/01-foundation/01-01-PLAN.md
```

**计划内容示例**：
```markdown
# Plan: 01-01-PLAN.md - 骨架屏优化

## 问题
- 首页加载后内容区空白
- 等待AI响应时没有视觉反馈

## 方案
1. 创建 LayoutSkeleton 组件
2. 创建消息列表骨架屏
3. 更新 Layout 和 NewChatContainer

## 任务列表
- [ ] Task 1: 分析现有 Layout UI 参数
- [ ] Task 2: 创建 LayoutSkeleton.tsx
- [ ] Task 3: 创建 LayoutSkeleton.module.css
- [ ] Task 4: 创建 MessageListSkeleton.tsx
- [ ] Task 5: 新增 Skeleton 组件导出
- [ ] Task 6: 修改 Layout/index.tsx 引入骨架屏
- [ ] Task 7: 修改 NewChatContainer.tsx

## 依赖关系
- Task 2 依赖 Task 1
- Task 3 依赖 Task 1
- Task 4 独立
- Task 5 依赖 Task 2, 3, 4
- Task 6 依赖 Task 5
- Task 7 依赖 Task 5

## 验证标准
1. 首页加载立即显示骨架屏
2. 骨架屏UI与 Layout 一致
3. 消息列表有骨架占位

## 成功标准
- 首屏骨架屏加载时间 < 500ms
- 用户等待时可见视觉反馈
```

**第3步：执行计划**

```
/gsd-execute-phase 1
# GSD 会：
# 1. 按任务顺序执行
# 2. 每个任务创建分支
# 3. 自动验证
# 4. 生成 SUMMARY.md
```

**第4步：验证**

```
/gsd-verify-work 1
# 逐项展示：
# 1. 骨架屏是否显示？ → 是/否
# 2. UI 是否一致？ → 是/否
# 3. 首屏时间？ → XXX ms
# 如有问题 → 自动创建修复计划
```

**第5步：交付**

```
/gsd-ship 1
# 创建 PR
# 更新版本号
```

---

### 4.4 实际案例：前端性能优化 - 问题2（标题编辑无反应）

#### 问题背景

**问题**：标题编辑时点击无反应  
**位置**：NewChatContainer 或 MessageItem  
**优先级**：待优化

#### GSD 执行流程

```
# 需求已明确，跳过讨论阶段
/gsd-plan-phase 2   # 创建第2阶段计划
/gsd-execute-phase 2 # 执行
/gsd-verify-work 2  # 验证
/gsd-ship 2         # 交付
```

---

### 4.5 实际案例：前端性能优化 - 问题3（消息显示慢）

#### 问题背景

**问题**：消息列表渲染慢  
**位置**：MessageItem 组件  
**优先级**：待优化

#### GSD 执行流程

```
/gsd-plan-phase 3   # 创建第3阶段计划
/gsd-execute-phase 3 # 执行
/gsd-verify-work 3  # 验证
/gsd-ship 3         # 交付
```

---

### 4.6 快速流程（需求已明确）

如果已经清楚需求，可以跳过讨论：

```
/gsd-quick "优化首屏加载，加骨架屏"
/gsd-quick --research
```

---

### 4.4 继续之前的工作

```
/gsd-progress  # 查看进度并继续
```

### 4.3 紧急插入工作

```
/gsd-insert-phase 5 "关键安全修复"
/gsd-plan-phase 5.1
/gsd-execute-phase 5.1
```

### 4.4 完成里程碑

```
/gsd-complete-milestone 1.0.0
/clear
/gsd-new-milestone  # 开启下一阶段
```

---

## 五、配置说明

### 5.1 工作模式

**交互模式 (Interactive)**:
- 确认每个重大决策
- 在检查点暂停等待批准
- 全程更多指导

**YOLO 模式**:
- 自动批准大多数决策
- 执行计划无需确认
- 只在关键检查点停止

切换方式：编辑 `.planning/config.json`

### 5.2 模型配置

| 配置 | 说明 |
|------|------|
| `quality` | 全部使用 Opus 模型 |
| `balanced` | 规划用 Opus，执行用 Sonnet（默认）|
| `budget` | 写作用 Sonnet，研究和验证用 Haiku |
| `inherit` | 使用当前会话的模型 |

---

## 六、实战技巧

### 6.1 快速任务

临时小任务使用快速模式：

```
/gsd-quick                          # 基本快速任务
/gsd-quick --research --full        # 带研究和完整验证
```

### 6.2 调试会话

遇到 bug 时启动调试：

```
/gsd-debug "登录按钮不工作"
# ... 调查过程 ...
/clear
/gsd-debug                        # 从中断处继续
```

### 6.3 记录想法

工作中随时记录想法：

```
/gsd-note 重构钩子系统           # 记录想法
/gsd-note list                   # 查看所有笔记
/gsd-note promote 3              # 将笔记转为待办
```

### 6.4 用户验收

功能开发完成后进行验收测试：

```
/gsd-verify-work 3
```

---

## 七、验证与交付

### 7.1 验证流程

每个阶段执行完成后：
1. 运行 `/gsd-verify-work [阶段]`
2. 逐项验证功能是否满足要求
3. 如有问题，自动创建修复计划

### 7.2 交付流程

验证通过后交付：

```
/gsd-ship 4              # 创建 PR
/gsd-ship 4 --draft     # 创建草稿 PR
```

---

## 八、常见问题

### Q1: 如何知道当前进度？

使用 `/gsd-progress` 查看项目状态和下一步操作。

### Q2: 如何恢复之前的工作？

使用 `/gsd-resume-work` 恢复会话上下文。

### Q3: 如何添加紧急任务？

使用 `/gsd-insert-phase` 在现有阶段之间插入新工作。

### Q4: 如何更新 GSD 工具？

运行 `/gsd-update` 查看更新并确认安装。

---

## 九、附录

### 9.1 命令速查表

| 场景 | 命令 |
|------|------|
| 初始化项目 | `/gsd-new-project` |
| 规划阶段 | `/gsd-plan-phase <num>` |
| 执行阶段 | `/gsd-execute-phase <num>` |
| 查看进度 | `/gsd-progress` |
| 记录想法 | `/gsd-note <text>` |
| 添加待办 | `/gsd-add-todo` |
| 调试问题 | `/gsd-debug <描述>` |
| 验收功能 | `/gsd-verify-work` |
| 交付代码 | `/gsd-ship` |

### 9.2 更新 GSD

```bash
npx get-shit-done-cc@latest
```

或使用：

```
/gsd-update
```

---

**更新时间**: 2026-04-12 15:10:00
**版本**: v1.3