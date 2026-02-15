# OpenCode CLI/TUI 安装情况调查报告

**创建时间**: 2026-02-11 19:44:07
**调查目的**: 查明本机所有OpenCode CLI/TUI的安装位置、版本、大小和安装时间

---

## 一、调查结论摘要

| 序号 | 安装方式/来源 | 是否安装 | 版本 | 大小 | 安装时间 |
|------|--------------|---------|------|------|---------|
| 1 | npm全局安装 | ✅ 是 | 1.1.53 | ~数MB | 2026-02-07 06:44 |
| 2 | bun全局安装 | ❌ 否 | - | - | - |
| 3 | pnpm全局安装 | ❌ 否 | - | - | - |
| 4 | yarn全局安装 | ❌ 否 | - | - | - |
| 5 | Chocolatey | ❌ 否 | - | - | - |
| 6 | Scoop | ❌ 否 | - | - | - |
| 7 | Mise | ❌ 否 | - | - | - |
| 8 | Docker镜像 | ❌ 否 | - | - | - |
| 9 | curl脚本 | ❌ 否 | - | - | - |
| 10 | Antigravity扩展 | ✅ 是 | 0.0.0-ide-plugin-202602081308 | 158MB | 2026-02-09 13:03 |
| 11 | VSCode扩展 | ✅ 是 | 0.0.0-ide-plugin-202602081308 | 158MB | 2026-02-09 13:43 |
| 12 | Cursor扩展 | ✅ 是 | 0.0.0-ide-plugin-202602081308 | 158MB | 2026-02-09 14:07 |

**总计重复安装**: 474MB（3个IDE扩展各158MB）

---

## 二、安装工具调查详情

### 2.1 npm全局安装 ✅

| 项目 | 值 |
|-----|-----|
| **安装状态** | 已安装 |
| **版本** | 1.1.53 |
| **命令位置** | `C:\Users\40968\AppData\Roaming\npm\opencode.cmd` |
| **模块目录** | `C:\Users\40968\AppData\Roaming\npm\node_modules\opencode\` |
| **安装时间** | 2026-02-07 06:44 |
| **大小** | 数MB（npm包，非完整二进制） |

**相关文件**:
```
C:\Users\40968\AppData\Roaming\npm\
├── opencode       (417 bytes, 2026-02-07 06:44)
├── opencode.cmd   (339 bytes, 2026-02-07 06:44)
└── opencode.ps1   (861 bytes, 2026-02-07 06:44)
```

**常用命令**:
```bash
# 查看已安装版本
npm list -g opencode-ai

# 查看全局node_modules路径
npm root -g

# 查看命令位置
where opencode

# 更新到最新版本
npm update -g opencode-ai

# 重新安装最新版
npm install -g opencode-ai@latest
```

### 2.2 bun全局安装 ❌

| 项目 | 值 |
|-----|-----|
| **bun工具本身** | ✅ 已安装 (v1.3.6) |
| **bun安装位置** | `C:\Users\40968\.bun\` |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查路径** | `C:\Users\40968\.bun\install\global\node_modules\` |
| **检查结果** | 目录存在，但无opencode，仅有@tauri-apps/cli |

### 2.3 pnpm全局安装 ❌

| 项目 | 值 |
|-----|-----|
| **pnpm工具本身** | ❌ 未安装 |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查路径** | `C:\Users\40968\AppData\Local\pnpm\global\` |
| **检查结果** | 目录不存在 |

### 2.4 yarn全局安装 ❌

| 项目 | 值 |
|-----|-----|
| **yarn工具本身** | ❌ 未安装 |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查路径** | `C:\Users\40968\AppData\Local\Yarn\` |
| **检查结果** | 目录不存在 |

### 2.5 Chocolatey ❌

| 项目 | 值 |
|-----|-----|
| **Chocolatey工具本身** | ✅ 已安装 (v1.1.0) |
| **Chocolatey位置** | `C:\ProgramData\chocolatey\` |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查路径** | `C:\ProgramData\chocolatey\bin\opencode*` |
| **检查结果** | 目录不存在，未通过choco安装opencode |

### 2.6 Scoop ❌

| 项目 | 值 |
|-----|-----|
| **Scoop工具本身** | ✅ 已安装 |
| **Scoop位置** | `C:\Users\40968\scoop\` |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查路径** | `C:\Users\40968\scoop\apps\opencode*` |
| **检查结果** | 目录不存在，未通过scoop安装opencode |

### 2.7 Mise ❌

| 项目 | 值 |
|-----|-----|
| **Mise工具本身** | ❌ 未安装 |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查路径** | `C:\Users\40968\.local\share\mise\` |
| **检查结果** | 目录不存在 |

### 2.8 Docker镜像 ❌

| 项目 | 值 |
|-----|-----|
| **Docker工具本身** | ✅ 已安装 |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查命令** | `docker images` |
| **检查结果** | 无opencode相关镜像 |

### 2.9 curl脚本安装 ❌

| 项目 | 值 |
|-----|-----|
| **curl工具本身** | ✅ 系统自带 |
| **OpenCode安装状态** | ❌ 未安装 |
| **检查路径** | `C:\Users\40968\.opencode\` |
| **检查结果** | 目录不存在，未通过curl脚本安装opencode |

---

## 三、IDE扩展调查详情

### 3.1 Antigravity扩展 ✅

| 项目 | 值 |
|-----|-----|
| **扩展名称** | paviko.opencode-ux-plus-26.2.8-universal |
| **是否自带CLI** | 是 |
| **CLI版本** | 0.0.0-ide-plugin-202602081308 |
| **CLI位置** | `C:\Users\40968\.antigravity\extensions\paviko.opencode-ux-plus-26.2.8-universal\resources\bin\windows\amd64\opencode.exe` |
| **CLI大小** | 158MB (165,287,936 bytes) |
| **安装时间** | 2026-02-09 13:03 |

### 3.2 VSCode扩展 ✅

| 项目 | 值 |
|-----|-----|
| **扩展名称** | paviko.opencode-ux-plus-26.2.8 |
| **是否自带CLI** | 是 |
| **CLI版本** | 0.0.0-ide-plugin-202602081308 |
| **CLI位置** | `C:\Users\40968\.vscode\extensions\paviko.opencode-ux-plus-26.2.8\resources\bin\windows\amd64\opencode.exe` |
| **CLI大小** | 158MB (165,287,936 bytes) |
| **安装时间** | 2026-02-09 13:43 |

### 3.3 Cursor扩展 ✅

| 项目 | 值 |
|-----|-----|
| **扩展名称** | paviko.opencode-ux-plus-26.2.8-universal |
| **是否自带CLI** | 是 |
| **CLI版本** | 0.0.0-ide-plugin-202602081308 |
| **CLI位置** | `C:\Users\40968\.cursor\extensions\paviko.opencode-ux-plus-26.2.8-universal\resources\bin\windows\amd64\opencode.exe` |
| **CLI大小** | 158MB (165,287,936 bytes) |
| **安装时间** | 2026-02-09 14:07 |

---

## 四、版本对比分析

### 4.1 版本差异

| 来源 | 版本号 | 类型说明 |
|------|-------|---------|
| npm全局 | 1.1.53 | 官方正式版本 |
| IDE扩展 | 0.0.0-ide-plugin-202602081308 | IDE专用定制版本 |

**分析**：
- npm安装的是官方正式版本
- IDE扩展自带的是定制版本，版本号格式不同
- IDE定制版本可能包含特定功能适配

### 4.2 功能差异

| 来源 | TUI/CLI | 说明 |
|------|---------|------|
| npm全局 | 完整CLI/TUI | 通过npm包管理，轻量级 |
| IDE扩展 | 完整CLI/TUI | 内置完整二进制文件，体积大 |

---

## 五、重复安装统计

### 5.1 空间占用

| 来源 | 大小 | 占比 |
|------|------|------|
| npm全局 | ~数MB | ~1% |
| Antigravity扩展 | 158MB | 33% |
| VSCode扩展 | 158MB | 33% |
| Cursor扩展 | 158MB | 33% |
| **总计** | ~474MB | 100% |

### 5.2 重复情况

- **3个IDE扩展**各自内置了一套完整的opencode.exe
- 每套158MB，**总计474MB重复空间**
- 三个扩展版本号完全相同（0.0.0-ide-plugin-202602081308）
- 理论上可以共享同一份CLI

---

## 六、结论与建议

### 6.1 调查结论

1. **npm全局安装**：唯一使用的命令行安装工具，版本1.1.53
2. **其他安装工具**：Chocolatey、Scoop、curl脚本均未安装
3. **IDE扩展**：三个IDE各自内置了完整的opencode CLI/TUI
4. **重复问题**：474MB空间被重复的IDE专用CLI占用

### 6.2 建议

| 方案 | 优点 | 缺点 | 建议 |
|------|------|------|------|
| 保持现状 | 各IDE独立运行，互不干扰 | 浪费474MB空间 | 磁盘空间充足时可接受 |
| 删除IDE内置CLI | 节省474MB空间 | IDE可能无法正常调用CLI | 不推荐，可能影响IDE功能 |
| 符号链接共享 | 节省空间，保持功能 | 需要手动配置 | 可尝试，但有风险 |

---

## 七、附录

### 7.1 检查命令参考

```bash
# 检查npm安装
npm list -g opencode-ai

# 检查Chocolatey安装
choco list opencode --local-only

# 检查Scoop安装
scoop list opencode

# 检查系统PATH中的opencode
where opencode

# 检查IDE扩展
ls ~/.antigravity/extensions/
ls ~/.vscode/extensions/
ls ~/.cursor/extensions/
```

### 7.2 文件清单

```
# npm全局
C:\Users\40968\AppData\Roaming\npm\opencode
C:\Users\40968\AppData\Roaming\npm\opencode.cmd
C:\Users\40968\AppData\Roaming\npm\opencode.ps1
C:\Users\40968\AppData\Roaming\npm\node_modules\opencode\

# Antigravity扩展
C:\Users\40968\.antigravity\extensions\paviko.opencode-ux-plus-26.2.8-universal\
└── resources\bin\windows\amd64\opencode.exe (158MB)

# VSCode扩展
C:\Users\40968\.vscode\extensions\paviko.opencode-ux-plus-26.2.8\
└── resources\bin\windows\amd64\opencode.exe (158MB)

# Cursor扩展
C:\Users\40968\.cursor\extensions\paviko.opencode-ux-plus-26.2.8-universal\
└── resources\bin\windows\amd64\opencode.exe (158MB)
```

---

**报告完成时间**: 2026-02-11 19:44:07
**报告人**: AI助手小欧
