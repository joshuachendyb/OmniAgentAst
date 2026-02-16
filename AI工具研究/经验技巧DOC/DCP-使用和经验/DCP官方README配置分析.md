# DCP官方README配置建议与版本情况

## GitHub官方README最新情况

### 版本信息
- **GitHub版本**: 2.0.0 (package.json)
- **你安装的版本**: 2.0.2 (npm版)
- **结论**: 你用的是更新的版本

### 官方工具说明
DCP确实提供三个工具：
- **Distill** - 提炼上下文为摘要
- **Compress** - 压缩大段对话为摘要  
- **Prune** - 删除已完成/噪声的工具内容

### 自动策略说明
**三个策略都是自动运行的（零LLM成本）**：

1. **Deduplication（去重）**
   - 识别重复的工具调用（如多次读取同一文件）
   - 只保留最新输出
   - **自动运行，每轮都执行**

2. **Supersede Writes（替代写入）**
   - 删除已被后续读取的文件写入内容
   - 理由：文件被读取后，原始写入变得冗余
   - **自动运行，每轮都执行**

3. **Purge Errors（清理错误）**
   - 清理错误工具输出
   - **自动运行，但README未说明具体轮次**

---

## 官方配置建议

### 默认行为
- README没有提供具体的配置模板
- 暗示所有策略都是**默认开启的**
- 没有提到如何调整权限

### 安装方式
```jsonc
{
  "plugin": ["@tarquinen/opencode-dcp@latest"]
}
```

---

## 发现的版本差异

### GitHub vs npm
- **GitHub**: 显示为 2.0.0
- **npm包**: 你安装的是 2.0.2
- **你用的是更新的版本**

### 工具名确认
- README确认三个工具名：distill, compress, prune
- **与我们源码看到的完全一致**
- **证实了：不存在版本混乱，之前是信息混淆**

---

## 基于README的配置建议

### 问题分析
1. **默认策略太激进**
   - Deduplication每轮运行，可能删除有用信息
   - Supersede Writes自动删除写入内容，导致调试困难
   - 没有说明如何控制这些策略

2. **缺乏配置文档**
   - README只说明工具和策略，但没有配置示例
   - 缺乏具体的dcp.jsonc配置方法

### 建议配置（基于README分析）

```json
{
  "$schema": "https://raw.githubusercontent.com/Opencode-DCP/opencode-dynamic-context-pruning/master/dcp.schema.json",
  "tools": {
    "prune": {
      "permission": "ask"    // 避免自动频繁清理
    },
    "distill": {
      "permission": "allow"   // 保留自动摘要
    },
    "compress": {
      "permission": "deny"    // 关闭压缩工具
    }
  },
  "strategies": {
    "deduplication": {
      "enabled": false      // 关闭自动去重
    },
    "supersedeWrites": {
      "enabled": false      // 关闭替代写入
    },
    "purgeErrors": {
      "enabled": true,
      "turns": 10         // 延长错误清理轮次
    }
  }
}
```

---

## 下一步执行

### 立即行动
1. **查看实际schema文件**
   - 获取官方配置选项定义
   - 确认上述配置字段是否正确

2. **更新dcp.jsonc**
   - 应用建议配置
   - 测试prune行为是否收敛

### 长期措施
1. **监控策略效果**
   - 观察去重和替代写入的影响
   - 根据实际需要调整

2. **建立配置文档**
   - 为团队提供可复制的配置模板
   - 记录每种策略的影响

---

**结论**：
- 不存在版本混乱，你用的是更新的2.0.2版本
- 问题确实是默认策略过于激进
- 需要通过配置来控制自动清理行为

---

**分析时间**: 2026-02-10 11:50:00  
**状态**: 准备执行配置优化