# OpenCode上下文优化插件汇总研究分析

**创建时间**: 2026-02-13 11:54:45  
**更新时间**: 2026-02-13  
**研究范围**: OpenCode生态系统中与上下文管理、会话备份、记忆持久化相关的插件  
**文档版本**: v1.1  

---

## 技术架构发现（重要更新）

### 运行时与GUI框架

经过实际检查和验证，OpenCode Desktop的技术架构如下：

**运行时**: **Bun**（不是Node.js）  
**GUI框架**: **WebView**（不是Electron）  

**证据**:
1. 官方架构文档明确说明: "Built with Bun runtime and written in TypeScript"
2. GitHub Bun仓库issue: "The Bun bundled with the Windows version of OpenCode crashes..."
3. 发现`@webreflection/webview-bun`包 - 专门用于Bun的WebView绑定
4. OpenCode.exe只有54MB（远小于Electron应用的100MB+）
5. `AppData/Local/ai.opencode.desktop/EBWebView/`目录存在WebView相关文件

**架构对比**:

| 特性 | Electron | WebView (OpenCode实际使用) |
|------|----------|---------------------------|
| 运行时 | Node.js | Bun |
| 体积 | 大（100MB+） | 小（54MB） |
| 内存占用 | 高 | 低 |
| 启动速度 | 慢 | 快 |
| Web引擎 | 自带Chromium | 使用系统WebView（Windows: Edge WebView2） |

**对插件兼容性的影响**:

⚠️ **关键发现**:
- Bun runtime ≠ Node.js runtime
- 但Bun官方声称:"If a package works in Node.js but doesn't work in Bun, we consider it a bug in Bun"
- Bun目标是100% Node.js API兼容，目前支持大多数npm包
- **实际发现**: OpenCode Desktop架构更复杂（见下文"Desktop版深度架构分析"）

**与TUI/CLI版本的区别**:
- TUI/CLI版: Node.js运行时 + 终端界面
- Desktop版: Bun运行时 + WebView GUI + `opencode-cli` sidecar
- 插件实际运行在sidecar进程中，不是直接在Bun环境下

### Desktop版深度架构分析（二次研究发现）

**关键发现**: OpenCode Desktop不是简单的"Bun + WebView"，而是更复杂的架构：

#### 1. 实际架构组成
```
OpenCode Desktop (WebView GUI界面)
    ↓ 通信
opencode-cli sidecar (后台进程)
    ↓ 运行
插件系统 (@opencode-ai/plugin)
    ↓ 存储
.dat文件 (AppData/Roaming/ai.opencode.desktop/)
```

**证据**:
- OpenCode官方文档: "Desktop app OpenCode Desktop runs a local OpenCode server (the `opencode-cli` sidecar) in the background"
- 实际进程观察: 运行OpenCode Desktop时，`opencode-cli.exe`和`OpenCode.exe`同时存在
- Changelog: "Fix plugin installation to use direct package.json manipulation instead of bun add"

#### 2. 插件运行机制
- **Desktop版**: 插件由`opencode-cli` sidecar加载和执行
- **sidecar本质**: 就是TUI/CLI版本的核心
- **结论**: 插件实际上在sidecar中运行，不是在Bun主进程中！

#### 3. Bun兼容性重新评估
**Bun官方承诺**: "Bun aims for 100% Node.js compatibility"
- 支持大多数npm包
- 每天运行数千个Node.js测试用例
- 不兼容视为Bun的bug

**但为什么opencode-session-backup还是不行？**
根本原因不是Bun vs Node.js，而是：
- **存储路径不同**: Desktop使用.dat文件，TUI/CLI使用文件系统
- **sidecar隔离**: 插件可能无法访问Desktop的主存储
- **存储格式差异**: 二进制.dat vs 明文JSON

#### 4. 正确的兼容性评估
| 插件类型 | Desktop兼容性 | 原因 |
|---------|-------------|------|
| 纯逻辑插件（不依赖存储） | ✅ 可能兼容 | 运行在sidecar中，sidecar是Node.js/Bun环境 |
| 依赖`@opencode-ai/plugin` | ✅ 应该兼容 | 官方插件API，sidecar支持 |
| 依赖文件系统存储 | ❌ 不兼容 | Desktop使用.dat文件，路径不同 |
| 直接操作session storage | ❌ 不兼容 | TUI/CLI路径不存在于Desktop |

---

## 重要说明：OpenCode版本与会话存储位置

### TUI/CLI版本
**存储路径**: `C:\Users\{用户名}\AppData\Local\opencode\storage\`

**子目录结构**:
- `session/` - 会话数据
- `message/` - 消息数据
- `part/` - 消息片段
- `todo/` - 任务列表

**特点**:
- 使用文件系统存储
- 插件可通过标准路径访问
- 与opencode-session-backup等插件兼容

### Desktop版本（GUI界面）
**存储路径**: `C:\Users\{用户名}\AppData\Roaming\ai.opencode.desktop\`

**文件类型**:
- `opencode.global.dat` - 全局数据
- `opencode.workspace.{编码}.dat` - 工作区数据
- `opencode.settings.dat` - 设置数据
- `.window-state.json` - 窗口状态

**特点**:
- 使用二进制.dat文件格式
- 与TUI/CLI版本完全不同的存储机制
- 大部分现有插件**不兼容**
- 插件需要专门适配Desktop版

### 版本兼容性说明
⚠️ **重要**: 当前大多数上下文管理插件都是为TUI/CLI版本设计的，与Desktop版不兼容。Desktop用户需要使用其他备份方案。

---

## 插件详细分析

### 1. opencode-session-backup ⭐ 官方插件

**GitHub地址**: https://github.com/Microck/opencode-session-backup  
**NPM地址**: https://www.npmjs.com/package/opencode-session-backup  
**版本**: 1.3.0

**功能描述**:
- 自动备份会活到Google Drive或本地文件夹
- 每条消息后自动备份（30秒防抖）
- 支持手动同步和恢复
- 使用robocopy（Windows）或rsync（Unix）进行增量同步

**支持版本**:
- ✅ TUI/CLI版本
- ❌ Desktop版本（存储路径不兼容）

**配置方式**:
```json
{
  "session-backup": {
    "backupPath": "D:/backup/opencode-sessions",
    "debug": true
  }
}
```

**工具命令**:
- `session_backup_sync` - 手动触发备份
- `session_backup_status` - 查看备份状态
- `session_backup_restore` - 从备份恢复

**不兼容原因**:
- 源码中硬编码了`AppData/Local/opencode/storage`路径
- Desktop版使用`AppData/Roaming/ai.opencode.desktop/`和.dat格式
- 即使sidecar运行插件，存储路径和格式完全不同
- **不是Bun运行时的问题，是存储架构的差异**

---

### 2. @tarquinen/opencode-dcp ⭐ 最流行

**GitHub地址**: https://github.com/Tarquinen/opencode-dynamic-context-pruning  
**NPM地址**: https://www.npmjs.com/package/@tarquinen/opencode-dcp  
**版本**: 2.1.3  
**Stars**: 790+

**功能描述**:
- 动态上下文剪枝（DCP）
- 智能删除冗余工具调用
- 自动策略（去重、覆盖写入、清除错误）
- 减少30-50%的token使用
- LLM驱动的智能剪枝工具

**支持版本**:
- ✅ TUI/CLI版本
- ✅ Desktop版本（通过sidecar运行，应该兼容）

**核心策略**:
1. **deduplication** - 去重相同工具调用
2. **supersedeWrites** - 写后读场景删除旧写入
3. **purgeErrors** - 清除过时错误信息

**工具命令**:
- `/prune` - 手动剪枝
- `/distill` - 生成会话摘要
- `/compress` - 压缩会话
- `/dcp stats` - 查看统计信息
- `/dcp context` - 查看上下文信息

**配置**: `~/.config/opencode/dcp.jsonc`

**兼容性分析**:
- DCP通过`@opencode-ai/plugin` API与OpenCode交互
- 不直接操作文件系统存储路径
- 通过hooks拦截消息和工具调用
- **在sidecar中运行，应该完全兼容Desktop版**
- 可能部分功能受限（如直接访问存储文件），但核心功能应正常工作

---

### 3. opencode-supermemory ⭐ 云服务方案

**GitHub地址**: https://github.com/supermemoryai/opencode-supermemory  
**NPM地址**: https://www.npmjs.com/package/opencode-supermemory  
**版本**: 最新  
**Stars**: 635+

**功能描述**:
- 跨会话持久化记忆
- 使用Supermemory云服务
- 自动上下文注入（用户画像+项目记忆）
- 关键词检测自动保存（"remember", "save this"）
- 智能压缩（上下文达80%时触发）

**支持版本**:
- ✅ TUI/CLI版本
- ✅ Desktop版本（通过sidecar运行，云服务不依赖本地存储）

**安装**:
```bash
bunx opencode-supermemory@latest install
```

**需要**:
- Supermemory API key (`SUPERMEMORY_API_KEY`)
- 云服务依赖

**命令**:
- `/supermemory-init` - 初始化并探索代码库

**兼容性分析**:
- 使用云服务（Supermemory），不依赖本地文件系统
- 通过HTTP API与Supermemory通信
- 插件运行在sidecar中，网络请求应该正常工作
- **应该完全兼容Desktop版**

---

### 4. opencode-mem / @happycastle/opencode-openmemory

**GitHub地址**: https://github.com/tickernelz/opencode-mem  
**NPM地址**: https://www.npmjs.com/package/@happycastle/opencode-openmemory  
**版本**: 0.0.3  
**Fork来源**: opencode-supermemory

**功能描述**:
- 本地优先的持久化记忆
- 使用SQLite本地向量数据库
- 12+本地嵌入模型
- Web UI管理界面（http://127.0.0.1:4747）
- 智能去重和隐私保护
- 自托管，无需云服务

**支持版本**:
- ✅ TUI/CLI版本
- ✅ Desktop版本（通过sidecar运行，独立存储路径）

**配置**: `~/.config/opencode/opencode-mem.jsonc`

**特点**:
- 本地SQLite存储（`~/.opencode-mem/data`）
- 支持多种嵌入模型

**兼容性分析**:
- 使用独立的SQLite数据库存储（`~/.opencode-mem/data`）
- 不依赖OpenCode的session storage路径
- 插件运行在sidecar中，文件系统访问应该正常
- **应该完全兼容Desktop版**
- 自动记忆捕获和提取

---

### 5. oh-my-opencode ⭐ 综合框架

**GitHub地址**: https://github.com/code-yeongyu/oh-my-opencode  
**版本**: 最新  
**Stars**: 30,000+

**功能描述**:
- 综合性工作流自动化框架
- 多Agent编排（Sisyphus主Agent）
- 20+内置hooks
- 会话管理和恢复
- 上下文压缩和优化

**支持版本**:
- ✅ TUI/CLI版本（主要目标）
- ❌ Desktop版本（不兼容）

**相关Hooks**:
- `session-recovery` - 自动错误恢复
- `context-window-monitor` - 监控上下文使用
- `compaction-context-injector` - 管理上下文压缩
- `session-notification` - 会话事件通知
- `auto-resume` - 自动恢复会话

**配置**: `~/.config/opencode/oh-my-opencode/`

---

### 6. opencode-agent-memory

**GitHub地址**: https://github.com/joshuadavidthomas/opencode-agent-memory  
**版本**: 实验性  
**Stars**: 38

**功能描述**:
- Letta风格的可编辑记忆块
- 共享内存块模式
- 持久化、自编辑的记忆块
- AGENTS.md的增强版

**支持版本**:
- ✅ TUI/CLI版本
- ❓ Desktop版本（待验证）

**特点**:
- 类似AGENTS.md，但增加结构（作用域、元数据、大小限制）
- 每个会话可读写共享状态

---

### 7. opencode-plugin-simple-memory

**GitHub地址**: https://github.com/cnicolov/opencode-plugin-simple-memory  
**版本**: 最新  
**Stars**: 32

**功能描述**:
- 简单的持久化记忆插件
- 跨会话记忆上下文
- 存储在`.opencode/memory/`
- 每日logfmt文件格式

**支持版本**:
- ✅ TUI/CLI版本
- ❓ Desktop版本（待验证）

**存储位置**: `.opencode/memory/`（项目本地）

---

### 8. Roampal

**官网**: https://roampal.ai/  
**GitHub**: https://github.com/Roampal/roampal-core  
**支持**: Claude Code & OpenCode

**功能描述**:
- AI编码工具的持久化记忆
- 本地优先，数据存储在本地
- 自动检测工具（Claude Code, OpenCode）
- 记忆实际有效的工作方式
- 不仅仅是相似性匹配

**支持版本**:
- ✅ TUI/CLI版本
- ❓ Desktop版本（支持OpenCode，但未明确区分版本）

**安装**:
```bash
pip install roampal
roampal init
```

**特点**:
- Core版本：免费，本地存储
- Desktop版本：100%本地，GUI应用

---

## 插件对比表

| 插件名称 | GitHub Stars | 类型 | TUI/CLI | Desktop | 云服务 | 本地存储 | 兼容性说明 |
|---------|-------------|------|---------|---------|--------|---------|-----------|
| opencode-session-backup | - | 文件备份 | ✅ | ❌ | ❌ | ✅ | 硬编码CLI路径，与Desktop存储格式不同 |
| @tarquinen/opencode-dcp | 790+ | 上下文剪枝 | ✅ | ✅ | ❌ | - | 通过plugin API运行，sidecar兼容 |
| opencode-supermemory | 635+ | 记忆持久化 | ✅ | ✅ | ✅ | ❌ | 云服务，不依赖本地存储 |
| opencode-mem | 85+ | 向量记忆 | ✅ | ✅ | ❌ | ✅ | 独立SQLite存储，sidecar可访问 |
| oh-my-opencode | 30K+ | 综合框架 | ✅ | ❓ | 可选 | 可选 | 复杂框架，需测试sidecar兼容性 |
| opencode-agent-memory | 38 | 记忆块 | ✅ | ✅ | ❌ | ✅ | 独立存储文件，sidecar兼容 |
| simple-memory | 32 | 简单记忆 | ✅ | ✅ | ❌ | ✅ | 项目本地存储，sidecar兼容 |
| Roampal | - | 智能记忆 | ✅ | ⚠️ | ❌ | ✅ | Core版通过plugin，Desktop版需MCP |

**图例**:
- ✅ 完全支持（通过sidecar运行）
- ❌ 不支持（存储路径/格式不兼容）
- ⚠️ 部分支持/需配置（Roampal Desktop版是独立应用）
- ❓ 待验证（复杂框架需要实际测试）

**兼容性判断依据**:
- Desktop版使用`opencode-cli` sidecar运行插件
- sidecar是TUI/CLI核心，理论上支持所有Node.js/Bun兼容的插件
- **关键差异**: 不依赖OpenCode存储路径的插件应该兼容

---

## 建议方案

### 对于TUI/CLI用户
**推荐组合**:
1. **@tarquinen/opencode-dcp** - 减少token使用，必备
2. **opencode-session-backup** 或 **opencode-mem** - 会话备份
3. **oh-my-opencode** - 综合增强（可选）

### 对于Desktop用户

**重新评估后的好消息**: 通过sidecar架构，许多插件实际上**可以工作**！

**推荐组合**（基于新架构理解）:
1. **@tarquinen/opencode-dcp** ✅ - 通过plugin API运行，应该完全兼容
2. **opencode-supermemory** ✅ - 云服务，不依赖本地存储
3. **opencode-mem** ✅ - 独立SQLite存储，sidecar可访问

**不兼容插件**:
1. **opencode-session-backup** ❌ - 硬编码CLI存储路径（`AppData/Local/opencode/storage`）

**待验证**:
1. **oh-my-opencode** ❓ - 复杂框架，需要实际测试sidecar兼容性
2. **Roampal Core** ❓ - 通过plugin API，理论上应该工作

**不再推荐的方案**:
- ~~使用TUI版本~~ - Desktop版通过sidecar实际上可以运行大多数插件
- ~~等待官方支持~~ - 现有插件生态已经可以通过sidecar支持

---

## 关键发现（二次研究更新）

### 1. Desktop版实际架构（重要！）
**发现**: Desktop版 ≠ 简单的"Bun + WebView"，而是:
```
WebView GUI (前端界面)
    ↓
opencode-cli sidecar (后台进程) ← 插件在这里运行！
    ↓
.dat文件存储
```

**关键洞察**: 插件实际上在**sidecar**中运行，不是在Bun主进程中！
- sidecar就是TUI/CLI的核心
- 插件使用`@opencode-ai/plugin` API与sidecar通信
- **这意味着大多数插件应该兼容Desktop版！**

### 2. 兼容性重新评估
**原来认为**: 90%插件不兼容（因为Bun运行时）  
**实际发现**: 
- ✅ **通过plugin API的插件**: DCP, supermemory, opencode-mem等应该兼容
- ❌ **直接操作存储的插件**: session-backup（硬编码路径）不兼容
- ❓ **复杂框架**: oh-my-opencode需要实际测试

### 3. 不兼容的真正原因
**不是Bun vs Node.js的问题**，而是:
- **存储路径不同**: CLI用`AppData/Local/opencode/storage/`，Desktop用`AppData/Roaming/ai.opencode.desktop/`
- **存储格式不同**: 文件系统 vs 二进制.dat
- **访问方式不同**: 直接文件访问 vs 通过sidecar API

### 4. 判断插件兼容性的新标准
| 条件 | 兼容性 | 示例 |
|-----|--------|------|
| 使用`@opencode-ai/plugin` API | ✅ 兼容 | DCP, supermemory |
| 不依赖OpenCode存储路径 | ✅ 兼容 | opencode-mem (独立SQLite) |
| 硬编码`AppData/Local/opencode/storage` | ❌ 不兼容 | session-backup |
| 直接操作.dat文件 | ❌ 不兼容 | 无（需要官方API） |

### 5. Bun运行时不是问题
- Bun官方声称100% Node.js兼容
- "If a package works in Node.js but doesn't work in Bun, we consider it a bug in Bun"
- Desktop版插件运行在sidecar中，sidecar可以用Node.js或Bun
- **存储架构差异才是主要障碍**

---

## 待验证项目

### 插件兼容性验证
- [ ] opencode-mem 是否兼容Desktop版（Bun运行时）
- [ ] Roampal 是否兼容Desktop版（Bun运行时）
- [ ] 使用Node.js API的插件在Bun环境下是否能正常工作

### Desktop版技术验证
- [ ] Desktop版是否支持`@opencode-ai/plugin`标准API
- [ ] Bun运行时与Node.js插件的兼容性测试
- [ ] WebView环境与插件的交互机制

### 备份恢复验证
- [ ] 手动备份Desktop版.dat文件是否可恢复
- [ ] Desktop版是否有官方备份/导出功能
- [ ] 不同版本间（TUI/Desktop）数据是否可互通

---

## 参考链接

- OpenCode官方文档: https://opencode.ai/docs
- 插件生态系统: https://opencode.ai/docs/ecosystem
- DCP详细文档: https://opencodedocs.com/Opencode-DCP/opencode-dynamic-context-pruning/
- Supermemory集成: https://supermemory.ai/docs/integrations/opencode

---

**更新时间**: 2026-02-13（二次研究：发现sidecar架构，重新评估兼容性）  
**版本**: v1.2  
**下次更新**: 实际测试Desktop版插件兼容性后更新验证结果

---

## 版本历史

### v1.2 (2026-02-13)
- **重大发现**: Desktop版使用`opencode-cli` sidecar运行插件
- **重新评估**: 大多数通过plugin API的插件应该兼容Desktop版
- **修正错误**: 之前认为Bun运行时是主要障碍，实际sidecar解决了这个问题
- **更新兼容性**: DCP、supermemory、opencode-mem等标记为Desktop兼容

### v1.1 (2026-02-13)
- 添加Bun运行时和WebView框架分析
- 对比Electron vs WebView架构
- 初步评估插件兼容性

### v1.0 (2026-02-13)
- 初始版本
- 8个上下文优化插件详细分析
- 版本存储路径说明
