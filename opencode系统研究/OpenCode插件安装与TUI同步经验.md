# OpenCode插件安装与TUI同步经验

**创建时间**: 2026-02-12 11:48:44
**更新时间**: 2026-02-12 11:48:44
**版本**: v1.0

---

## 一、核心概念理解

### 1.1 OpenCode的两种使用形态

| 形态 | 运行时 | 使用场景 | 配置文件位置 |
|------|--------|---------|-------------|
| **Desktop版本** | Bun | 日常使用，GUI界面 | `C:\Users\40968\.config\opencode\opencode.jsonc` |
| **TUI/CLI版本** | Node.js | 命令行操作，脚本集成 | 同上 |

### 1.2 关键差异

| 差异点 | Desktop (Bun) | TUI (Node.js) |
|--------|---------------|---------------|
| 插件自动安装 | ✅ 自动安装到`.cache`目录 | ❌ 需要手动复制 |
| JSON配置支持 | ❌ 部分不支持 | ✅ 支持 |
| 环境变量 | ✅ 完美支持 | ✅ 支持 |
| 插件目录 | `~/.cache/opencode/node_modules/` | `~/.config/opencode/plugins/` |

---

## 二、插件存储位置详解

### 2.1 Desktop版本插件位置

**路径**: `C:\Users\40968\.cache\opencode\node_modules\`

```
C:\Users\40968\.cache\opencode\node_modules\
├── @tarquinen\opencode-dcp\              # DCP插件 v2.0.2
├── @ramtinj95\opencode-tokenscope\       # TokenScope插件 v1.5.2
└── opencode-session-backup\              # SessionBackup插件 v1.3.0
```

**特点**:
- 使用Bun包管理器自动安装
- 属于缓存目录，可能被清理（但会自动重新安装）
- 这是Desktop版本实际运行时加载的目录

### 2.2 TUI版本插件位置

**路径**: `C:\Users\40968\.config\opencode\plugins\`

```
C:\Users\40968\.config\opencode\plugins\
├── @tarquinen\opencode-dcp\
├── @ramtinj95\opencode-tokenscope\
└── opencode-session-backup\
```

**特点**:
- TUI版本的标准插件目录
- 需要手动复制Desktop安装的插件
- 或者手动从此目录安装插件

### 2.3 配置文件位置

**路径**: `C:\Users\40968\.config\opencode\opencode.jsonc`

**正确的插件配置格式**:
```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [...],
  
  "plugin": [
    "@tarquinen/opencode-dcp@latest",
    "@ramtinj95/opencode-tokenscope@latest",
    "opencode-session-backup@latest",
    "@tarquinen/opencode-smart-title@latest",
    "opencode-antigravity-auth@1.4.6"
  ]
}
```

**重要提醒**:
- 配置项名称是 **`plugin`**（单数形式），不是 `plugins`
- 使用 `plugins` 会导致启动失败并报错: `Unrecognized key: "plugins"`

---

## 三、插件安装与同步流程

### 3.1 标准流程：先Desktop后TUI

**步骤1**: 在Desktop版本中安装插件

**操作**:
- 在 `opencode.jsonc` 中添加 `"plugin"` 配置项
- 重启Desktop版本
- Bun自动下载并安装插件到 `.cache/opencode/node_modules/`

**示例配置**:
```json
"plugin": [
  "@tarquinen/opencode-dcp@latest"
]
```

**步骤2**: 复制插件到TUI目录

**操作**:
```powershell
# 从Desktop目录复制到TUI目录
cp -r "C:\Users\40968\.cache\opencode\node_modules\@tarquinen\opencode-dcp" \
      "C:\Users\40968\.config\opencode\plugins\"

cp -r "C:\Users\40968\.cache\opencode\node_modules\@ramtinj95\opencode-tokenscope" \
      "C:\Users\40968\.config\opencode\plugins\"

cp -r "C:\Users\40968\.cache\opencode\node_modules\opencode-session-backup" \
      "C:\Users\40968\.config\opencode\plugins\"
```

**原因**: TUI版本不会自动从`.cache`目录加载插件，需要手动复制到`.config/opencode/plugins/`

### 3.2 反向流程：先TUI后Desktop

**问题**: 如果先在TUI中安装插件，如何同步到Desktop？

**操作**:
```powershell
# 从TUI目录复制到Desktop目录
cp -r "C:\Users\40968\.config\opencode\plugins\@tarquinen\opencode-dcp" \
      "C:\Users\40968\.cache\opencode\node_modules\"

cp -r "C:\Users\40968\.config\opencode\plugins\@ramtinj95\opencode-tokenscope" \
      "C:\Users\40968\.cache\opencode\node_modules\"
```

**结论**: **是的**，如果需要在两个版本间同步使用插件，必须手动复制。

### 3.3 同步规则总结

| 安装顺序 | Desktop目录 | TUI目录 | 是否需要复制 |
|---------|-------------|---------|--------------|
| 先Desktop后TUI | `.cache/opencode/node_modules/` | `.config/opencode/plugins/` | ✅ 需要复制到TUI |
| 先TUI后Desktop | `.cache/opencode/node_modules/` | `.config/opencode/plugins/` | ✅ 需要复制到Desktop |

**核心原则**: 两个版本的插件目录是独立的，必须手动同步。

---

## 四、配置差异与兼容性问题

### 4.1 JSON配置支持差异

| 插件 | Desktop (Bun) | TUI (Node.js) | 推荐配置方式 |
|------|---------------|---------------|--------------|
| opencode-dcp | ✅ 支持 | ✅ 支持 | `"plugin"` 配置 |
| opencode-tokenscope | ✅ 支持 | ✅ 支持 | `"plugin"` 配置 |
| opencode-session-backup | ❌ 不支持JSON | ✅ 可能支持 | **环境变量** |
| opencode-smart-title | ✅ 支持 | ✅ 支持 | `"plugin"` 配置 |
| opencode-antigravity-auth | ✅ 支持 | ✅ 支持 | `"plugin"` + 具体版本号 |

### 4.2 session-backup配置问题

**问题现象**:
```json
// ❌ 错误的配置方式（Desktop版本不生效）
{
  "session-backup": {
    "backupPath": "D:/path/to/backup"
  }
}

// ✅ 正确的配置方式（环境变量）
{
  "plugin": [
    "opencode-session-backup@latest"
  ]
}
```

**配置方法**:
```powershell
# Windows PowerShell
$env:OPENCODE_BACKUP_PATH = "D:/2bktest/MDview/opencode-backups"
$env:OPENCODE_BACKUP_DEBUG = "true"
```

**原因分析**:
- Bun运行时可能不调用插件的`config`异步回调函数
- 环境变量是同步读取，立即生效

### 4.3 antigravity版本号问题

**错误写法**:
```json
// ❌ 使用@latest会失败
"plugin": [
  "opencode-antigravity-auth@latest"
]
```

**正确写法**:
```json
// ✅ 必须使用具体版本号
"plugin": [
  "opencode-antigravity-auth@1.4.6"
]
```

**错误信息**: `Invalid SemVer: latest`

---

## 五、完整安装流程示例

### 5.1 安装新插件的完整步骤

**假设安装新插件: example-plugin**

**步骤1**: 编辑配置文件

**文件**: `C:\Users\40968\.config\opencode\opencode.jsonc`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [...],
  
  "plugin": [
    "@tarquinen/opencode-dcp@latest",
    "@ramtinj95/opencode-tokenscope@latest",
    "opencode-session-backup@latest",
    "@tarquinen/opencode-smart-title@latest",
    "opencode-antigravity-auth@1.4.6",
    "example-plugin@1.0.0"  // 新增插件
  ]
}
```

**步骤2**: 重启Desktop版本

- 关闭OpenCode Desktop
- 重新打开
- 观察日志确认插件安装成功

**步骤3**: 验证Desktop安装成功

**日志位置**: `C:\Users\40968\.local\share\opencode\log\`

**成功标志**:
```
INFO  service=bun installed example-plugin@1.0.0
```

**步骤4**: 复制到TUI目录

```powershell
cp -r "C:\Users\40968\.cache\opencode\node_modules\example-plugin" \
      "C:\Users\40968\.config\opencode\plugins\"
```

**步骤5**: 验证TUI可用

```bash
# 在TUI版本中检查插件
opencode agent list
```

---

## 六、已安装插件汇总

### 6.1 当前配置的5个插件

| 序号 | 插件名称 | 版本 | 功能 | 安装方式 | TUI同步 |
|------|---------|------|------|---------|--------|
| 1 | @tarquinen/opencode-dcp | v2.0.2 | 动态上下文剪枝 | Desktop自动 | ✅ 需复制 |
| 2 | @ramtinj95/opencode-tokenscope | v1.5.2 | Token使用分析 | Desktop自动 | ✅ 需复制 |
| 3 | opencode-session-backup | v1.3.0 | 会话自动备份 | Desktop自动 | ✅ 需复制 |
| 4 | @tarquinen/opencode-smart-title | v0.1.7 | 自动生成标题 | Desktop自动 | ✅ 需复制 |
| 5 | opencode-antigravity-auth | v1.4.6 | 免费Claude/Gemini | Desktop自动 | ✅ 需复制 |

### 6.2 插件来源

| 来源 | 类型 |
|------|------|
| `@tarquinen/*` | NPM - DCP作者 |
| `@ramtinj95/*` | NPM - TokenScope作者 |
| `opencode-*` | NPM - OpenCode官方/社区 |
| `oh-my-opencode` | NPM - 已移除（曾遇到问题） |

---

## 七、问题排查指南

### 7.1 常见错误与解决方法

| 错误信息 | 原因 | 解决方法 |
|---------|------|---------|
| `Unrecognized key: "plugins"` | 配置项名称错误 | 改为 `plugin`（单数） |
| `Unrecognized key: "session-backup"` | 不支持JSON配置 | 使用环境变量 |
| `Invalid SemVer: latest` | antigravity版本号 | 使用具体版本号如 `1.4.6` |
| 插件不工作 | 未复制到TUI目录 | 手动复制插件到 `~/.config/opencode/plugins/` |

### 7.2 验证插件是否正确安装

**方法1**: 查看日志

```powershell
# 查看最新日志
Get-Content "C:\Users\40968\.local\share\opencode\log\*.log" -Tail 50

# 搜索插件加载信息
Select-String -Path "C:\Users\40968\.local\share\opencode\log\*.log" -Pattern "dcp|tokenscope|session"
```

**方法2**: 检查目录

```powershell
# Desktop插件目录
Test-Path "C:\Users\40968\.cache\opencode\node_modules\@tarquinen\opencode-dcp"

# TUI插件目录
Test-Path "C:\Users\40968\.config\opencode\plugins\@tarquinen\opencode-dcp"
```

**方法3**: 使用TUI命令

```bash
# 检查已安装的agent
opencode agent list

# 检查MCP servers
opencode mcp list
```

---

## 八、经验教训总结

### 8.1 重要教训

1. **配置项名称**
   - OpenCode使用 `plugin`（单数），不是 `plugins`（复数）
   - 教训：不要凭记忆配置，必须查阅官方文档

2. **版本号格式**
   - `antigravity-auth` 必须使用具体版本号，不能用 `@latest`
   - 其他插件通常可以使用 `@latest`

3. **配置方式**
   - 并非所有插件都支持JSON配置
   - `session-backup` 必须使用环境变量
   - 教训：安装前必须查阅每个插件的文档

4. **目录同步**
   - Desktop和TUI使用不同的插件目录
   - 必须在两个目录间手动复制插件
   - Desktop不会自动同步到TUI

### 8.2 最佳实践

| 场景 | 推荐做法 |
|------|---------|
| 日常安装插件 | 在Desktop中配置，重启后自动安装，然后复制到TUI |
| 配置插件 | 优先使用环境变量，兼容性最好 |
| 版本号 | 非antigravity插件可用 `@latest`，antigravity必须用具体版本 |
| 插件同步 | 安装后立即复制到TUI目录，避免忘记 |

---

## 九、相关文档链接

| 文档 | 位置 | 说明 |
|------|------|------|
| **OpenCode插件安装与TUI同步经验** | `D:\2bktest\MDview\OpenCode插件安装与TUI同步经验.md` | **本文档** |
| Skill-MCP-plugin安装日志 | `D:\50RuleTool\Skill-MCP-plugin安装日志.md` | 详细安装记录 |
| 工作日志-2026-02-08 | `D:\2bktest\MDview\工作日志-2026-02-08.md` | 问题排查记录 |
| OpenCode配置文件 | `C:\Users\40968\.config\opencode\opencode.jsonc` | 当前配置 |
| Desktop插件目录 | `C:\Users\40968\.cache\opencode\node_modules\` | Desktop插件 |
| TUI插件目录 | `C:\Users\40968\.config\opencode\plugins\` | TUI插件 |
| OpenCode日志 | `C:\Users\40968\.local\share\opencode\log\` | 运行日志 |

---

## 十、附录：常用命令速查

### 10.1 插件管理命令

| 命令 | 用途 | 运行环境 |
|------|------|---------|
| `opencode agent list` | 查看已安装agents | TUI |
| `opencode mcp list` | 查看MCP servers | TUI |
| `opencode config show` | 显示当前配置 | TUI/Desktop |
| `session_backup_status` | 查看备份状态 | TUI |
| `session_backup_sync force=true` | 强制同步备份 | TUI |

### 10.2 目录操作命令

```powershell
# 复制插件到TUI目录
cp -r "C:\Users\40968\.cache\opencode\node_modules\@tarquinen\opencode-dcp" \
      "C:\Users\40968\.config\opencode\plugins\"

# 检查插件是否存在
Test-Path "C:\Users\40968\.cache\opencode\node_modules\@tarquinen\opencode-dcp"
Test-Path "C:\Users\40968\.config\opencode\plugins\@tarquinen\opencode-dcp"

# 查看日志
Get-Content "C:\Users\40968\.local\share\opencode\log\*.log" -Tail 20
```

---

**更新时间**: 2026-02-12 11:48:44
**版本**: v1.0
**作者**: AI助手

---

## 关键结论

1. **Desktop和TUI的插件目录是独立的**
   - Desktop: `~/.cache/opencode/node_modules/`
   - TUI: `~/.config/opencode/plugins/`

2. **同步必须手动操作**
   - 在Desktop安装插件后，必须复制到TUI目录
   - 在TUI安装插件后，必须复制到Desktop目录

3. **配置项名称是 `plugin`（单数）**
   - 使用 `plugins` 会导致启动失败

4. **antigravity必须用具体版本号**
   - 不能使用 `@latest`

---

**文档结束**
