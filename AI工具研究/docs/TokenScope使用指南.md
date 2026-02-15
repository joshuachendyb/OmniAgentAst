# TokenScope 插件使用指南

**创建时间**: 2026-02-08  
**插件**: @ramtinj95/opencode-tokenscope v1.5.2

---

## 查看 Token 统计

### 方法1: 使用命令（推荐）
```bash
# 查看当前会话统计
/tokenscope show

# 查看总体统计
/tokenscope total

# 导出为 JSON
/tokenscope export
```

### 方法2: 查看日志文件
插件会自动记录到:
```
~/.local/share/opencode/tokenscope/
```

### 方法3: 查看详细报告
```bash
# 生成完整报告
/tokenscope report
```

---

## 核心功能

| 功能 | 命令 | 说明 |
|------|------|------|
| **实时统计** | `/tokenscope show` | 查看当前会话 Token 使用 |
| **分类分析** | `/tokenscope categories` | 按工具/操作分类统计 |
| **成本估算** | `/tokenscope cost` | 估算 API 费用 |
| **历史趋势** | `/tokenscope history` | 查看使用趋势 |
| **导出数据** | `/tokenscope export` | 导出 JSON/CSV |

---

## 安装状态

✅ **已配置**: `opencode.jsonc`  
✅ **已备份**: `opencode.jsonc.backup.tokenscope.xxx`  
⏳ **待重启**: 重启 OpenCode 后生效

---

## 下一步

1. **重启 OpenCode** - 插件会自动下载安装
2. **测试命令** - 输入 `/tokenscope show`
3. **查看统计** - 观察 Token 使用 breakdown
