# DCP 插件安装及使用说明

**创建时间**: 2026-02-10 13:00:39  
**版本**: 1.1  
**适用范围**: OpenCode 用户，DCP 插件安装与配置  

---

## 一、插件概述

### 1.1 什么是 DCP 插件

**DCP**（Dynamic Context Pruning）是 OpenCode 的**动态上下文管理插件**，用于：

- **减少 token 使用量**（节省 30-50%）
- **清理无用的工具输出**
- **提炼关键信息为摘要**
- **压缩大段对话内容**

### 1.2 版本说明

| 版本来源 | 版本号 | 工具名称 | 特点 |
|---------|---------|---------|------|
| **npm 包**（推荐） | 2.0.2 | prune, distill, compress | 功能完整，支持详细配置 |
| **GitHub 官方** | 2.0.2 | prune, distill, compress | 与npm版本同步，功能一致 |

**推荐使用 npm 版**：功能更新更快，配置选项更丰富。

---

## 二、安装方法

### 2.1 前置条件

- OpenCode 已正确安装并配置
- 有 npm 环境访问权限
- 网络连接正常

### 2.2 安装命令

```bash
# 安装最新版本（推荐）
opencode plugin install @tarquinen/opencode-dcp@latest

# 或安装指定版本
opencode plugin install @tarquinen/opencode-dcp@2.0.2
```

### 2.3 验证安装

1. **检查插件文件**
   ```bash
   ls ~/.config/opencode/plugins/@tarquinen/opencode-dcp/
   ```

2. **查看版本信息**
   ```bash
   cat ~/.config/opencode/plugins/@tarquinen/opencode-dcp/package.json | grep version
   ```

3. **重启 OpenCode**
   安装完成后必须重启 OpenCode 以加载插件。

---

## 三、配置详解

### 3.1 配置文件位置

DCP 配置文件按优先级加载：

```
项目级配置（最高优先级）: .opencode/dcp.jsonc
全局配置: ~/.config/opencode/dcp.jsonc
默认配置（最低优先级）: 内置默认值
```

### 3.2 配置模板

#### 推荐配置（日常使用）
```json
{
  "$schema": "https://raw.githubusercontent.com/Opencode-DCP/opencode-dynamic-context-pruning/master/dcp.schema.json",
  "tools": {
    "prune": {
      "permission": "ask"  // 改为询问，避免自动清理
    },
    "distill": {
      "permission": "allow"  // 保留自动蒸馏
    },
    "compress": {
      "permission": "deny"  // 关闭压缩
    }
  },
  "strategies": {
    "deduplication": {
      "enabled": true  // 保留去重
    },
    "supersedeWrites": {
      "enabled": false  // 关闭替代写入
    },
    "purgeErrors": {
      "enabled": true,
      "turns": 10  // 延长到10轮
    }
  }
}
```

#### 调试配置（信息保留优先）
```json
{
  "tools": {
    "prune": { "permission": "deny" },      // 完全禁用
    "distill": { "permission": "ask" },      // 手动控制
    "compress": { "permission": "deny" }      // 完全禁用
  },
  "strategies": {
    "deduplication": { "enabled": false },     // 禁用所有自动策略
    "supersedeWrites": { "enabled": false },
    "purgeErrors": { "enabled": false }
  }
}
```

---

## 四、工具详解

### 4.1 工具权限说明

| 工具 | 作用 | 权限选项 | 推荐设置 |
|------|------|---------|---------|
| **prune** | 删除工具输出（无保留） | allow/ask/deny | ask |
| **distill** | 提炼摘要（保留精华） | allow/ask/deny | allow |
| **compress** | 压缩对话（大段摘要） | allow/ask/deny | deny |

### 4.2 策略说明

| 策略 | 作用 | 默认值 | 推荐设置 |
|------|------|---------|---------|
| **deduplication** | 去重，保留最新输出 | enabled | enabled |
| **supersedeWrites** | 替代写入，删除冗余 | enabled | disabled |
| **purgeErrors** | 清理错误，N轮后删除 | enabled:4 | enabled:10 |

---

## 五、使用指南

### 5.1 配置更新流程

1. **备份现有配置**
   ```bash
   cp ~/.config/opencode/dcp.jsonc ~/.config/opencode/dcp.jsonc.backup
   ```

2. **编辑配置文件**
   ```bash
   notepad ~/.config/opencode/dcp.jsonc
   ```

3. **验证配置语法**
   ```bash
   cat ~/.config/opencode/dcp.jsonc | jq .
   ```

4. **重启 OpenCode** 让配置生效

### 5.2 配置优先级

配置文件按优先级合并：`默认 < 全局 < 环境变量 < 项目`  
项目级配置（`.opencode/dcp.jsonc`）具有最高优先级。

### 5.3 故障排除

#### 配置不生效
- 检查文件位置是否正确
- 验证 JSON 语法是否正确
- 确认已重启 OpenCode
- 查看是否有 Toast 警告提示

#### 工具无法使用
- 检查 permission 设置是否正确
- 查看控制台是否有错误信息
- 验证插件版本是否支持该功能

#### 性能问题
- 检查 deduplication 是否导致误删
- 考虑关闭 compress 工具
- 调整 purgeErrors 的轮次设置

---

## 六、最佳实践

### 6.1 日常使用建议

1. **prune 设为 "ask"**：避免自动删除有用信息
2. **保留 distill 自动运行**：适度清理有用
3. **关闭 compress**：避免过度压缩丢失上下文
4. **supersedeWrites 关闭**：保留调试信息
5. **purgeErrors 设为 10**：延长错误保留时间

### 6.2 针对场景配置

| 场景 | prune | distill | compress | deduplication | supersedeWrites | purgeErrors |
|------|--------|---------|---------|-------------|----------------|-------------|
| **日常开发** | ask | allow | deny | true | false | 10 |
| **调试阶段** | deny | ask | deny | false | false | 15 |
| **token节省** | allow | allow | ask | true | true | 3 |
| **长期对话** | ask | allow | deny | true | false | 20 |

---

## 七、版本管理

### 7.1 版本更新

```bash
# 检查当前版本
npm view @tarquinen/opencode-dcp version

# 更新到最新版本
opencode plugin update @tarquinen/opencode-dcp@latest
```

### 7.2 版本兼容性

- **2.0.x 系列**：完全兼容，推荐使用
- **1.x 系列**：配置格式可能不同，建议升级

---

## 八、常见问题

### Q: 配置文件在哪里？
A: `~/.config/opencode/dcp.jsonc`（全局）或项目级 `.opencode/dcp.jsonc`

### Q: 为什么 prune 还是自动执行？
A: 检查 permission 是否设为 "ask"，并确保已重启 OpenCode

### Q: 如何彻底禁用自动策略？
A: 在 strategies 中将所有 enabled 设为 false

### Q: 配置不生效怎么办？
A: 1) 检查语法 2) 确认文件位置 3) 重启 OpenCode 4) 查看日志

---

## 九、参考资源

- **GitHub 仓库**: https://github.com/Opencode-DCP/opencode-dynamic-context-pruning
- **npm 包**: https://www.npmjs.com/package/@tarquinen/opencode-dcp
- **配置文档**: https://opencodedocs.com/Opencode-DCP/opencode-dynamic-context-pruning
- **故障排除**: https://opencodedocs.com/Opencode-DCP/opencode-dynamic-context-pruning/faq/troubleshooting/

---

**文档更新时间**: 2026-02-10 13:05:00  
**版本**: 1.1  
**维护人**: OpenCode DCP 用户社区