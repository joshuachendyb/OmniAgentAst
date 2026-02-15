# OpenCode插件Desktop版兼容性验证报告

**验证时间**: 2026-02-13  
**验证插件**: 
1. Roampal
2. opencode-mem

---

## 一、验证方法

### 1.1 信息来源
- 官方网站文档
- GitHub仓库README
- NPM包信息
- 源码分析（如有）

### 1.2 兼容性判断标准
- **完全兼容(✅)**: 官方明确支持Desktop版，或实现方式不依赖特定存储路径
- **可能兼容(⚠️)**: 实现方式理论上支持，但未官方确认
- **不兼容(❌)**: 官方明确不支持，或依赖TUI/CLI特定路径
- **待验证(❓)**: 需要实际安装测试才能确定

---

## 二、Roampal 兼容性验证

### 2.1 产品形态分析

Roampal提供**两个版本**:

#### A. roampal-core（免费开源）
- **GitHub**: https://github.com/roampal-ai/roampal-core
- **支持工具**: Claude Code & OpenCode
- **集成方式**: 
  - Claude Code: hooks（自动注入）
  - OpenCode: plugin（自动注入）
- **存储**: 本地ChromaDB向量数据库
- **安装**: `pip install roampal`

#### B. Roampal Desktop（$9.99一次性购买）
- **官网**: https://roampal.ai/
- **性质**: 独立的GUI应用程序
- **支持工具**: 任何MCP兼容的AI工具（Claude Code, OpenCode, Cline等）
- **集成方式**: MCP（Model Context Protocol）
- **存储**: 本地ChromaDB + 本地LLM（Ollama/LM Studio）
- **功能差异**:
  - Desktop: 需要手动提示AI使用记忆工具（无自动注入）
  - Core: 自动注入和评分

### 2.2 Desktop版兼容性结论

**❓ 待验证 / ⚠️ 可能部分兼容**

**原因分析**:

1. **版本混淆**: Roampal官网区分了"Core"和"Desktop"两个产品：
   - "Core"支持OpenCode（应该指TUI/CLI版）
   - "Desktop"是独立应用，通过MCP连接其他工具

2. **OpenCode Desktop vs Roampal Desktop**:
   - 如果用户使用**Roampal Core** + **OpenCode Desktop**: 兼容性不确定
   - 如果用户使用**Roampal Desktop**（独立应用）: 可以工作，但这是替换OpenCode Desktop，不是插件

3. **集成方式差异**:
   - roampal-core使用OpenCode plugin API
   - 但OpenCode Desktop的插件系统可能与TUI版不同

**官方说明**: 官网未明确说明是否支持OpenCode Desktop版，只说支持"OpenCode"

**建议**: 需要实际安装测试才能确定

---

## 三、opencode-mem 兼容性验证

### 3.1 技术架构分析

**NPM包**: opencode-mem@2.7.5

**依赖分析**:
```
@opencode-ai/plugin: ^1.0.162     ← OpenCode插件API
@xenova/transformers: ^2.17.2    ← 本地嵌入模型（Transformers.js）
sqlite-vec: ^0.1.7-alpha.2       ← SQLite向量数据库
franc-min: ^6.2.0                ← 语言检测
iso-639-3: ^3.0.1                ← 语言代码
```

**存储方式**:
- **数据存储**: SQLite本地文件（`~/.opencode-mem/data`）
- **不依赖**: OpenCode的session storage路径
- **插件API**: 使用标准的`@opencode-ai/plugin`

**工作原理**:
1. 通过OpenCode插件API注册`memory`工具
2. 将记忆存储在独立的SQLite数据库中
3. 提供Web UI管理界面（http://127.0.0.1:4747）
4. 不读取或修改OpenCode的会话存储

### 3.2 Desktop版兼容性结论

**⚠️ 可能兼容 / ❓ 需要实际测试**

**支持理由**:

1. **标准插件API**: 使用`@opencode-ai/plugin`，这是OpenCode官方插件接口
2. **独立存储**: 不依赖`AppData/Local/opencode/storage/`，使用自己的SQLite路径
3. **无文件系统依赖**: 不直接读取TUI/CLI特定的存储结构

**不确定因素**:

1. **OpenCode Desktop的插件系统**: 
   - Desktop版是否支持`@opencode-ai/plugin` API？
   - 插件加载机制是否与TUI版相同？

2. **权限问题**:
   - Desktop版（Electron应用）可能有不同的权限模型
   - 是否能访问`~/.opencode-mem/`路径？

3. **官方说明**: 未在文档中明确说明支持Desktop版

**源码位置**: 理论上如果Desktop版支持标准OpenCode插件API，opencode-mem应该可以工作

---

## 四、对比总结

| 插件 | TUI/CLI | Desktop | 云服务 | 本地存储 | 核心依赖 |
|------|---------|---------|--------|----------|----------|
| **Roampal Core** | ✅ 明确支持 | ❓ 待验证 | ❌ | ✅ ChromaDB | hooks/plugin |
| **Roampal Desktop** | N/A | ✅ 独立应用 | ❌ | ✅ ChromaDB | MCP |
| **opencode-mem** | ✅ 明确支持 | ⚠️ 可能兼容 | ❌ | ✅ SQLite | plugin API |

**关键区别**:
- Roampal Core通过OpenCode plugin API集成
- opencode-mem也通过OpenCode plugin API集成，但存储完全独立
- 两者都不直接操作OpenCode的session storage文件

---

## 五、测试建议

### 5.1 Roampal测试步骤

```bash
# 1. 安装Roampal Core
pip install roampal

# 2. 初始化
roampal init --opencode

# 3. 启动OpenCode Desktop
# 4. 观察是否有Roampal相关输出
# 5. 尝试对话，看是否有记忆功能
```

**预期结果**:
- 如果Desktop版支持标准plugin API：✅ 应该工作
- 如果不支持：❌ 会报错或无反应

### 5.2 opencode-mem测试步骤

```bash
# 1. 在OpenCode Desktop的config中添加插件
{
  "plugin": ["opencode-mem"]
}

# 2. 重启OpenCode Desktop
# 3. 观察控制台是否有插件加载信息
# 4. 尝试调用memory工具
# 5. 检查~/.opencode-mem/目录是否创建
```

**预期结果**:
- 如果Desktop版支持标准plugin API：✅ 应该工作
- 如果插件系统不兼容：❌ 会报错

---

## 六、当前建议

### 对于Desktop版用户

**短期方案**（确定可行）:
- 手动备份`C:/Users/{username}/AppData/Roaming/ai.opencode.desktop/`
- 使用Windows任务计划定期备份

**中期方案**（需要测试）:
1. 测试opencode-mem（推荐先测试这个，因为架构更简单）
2. 如果opencode-mem工作，再测试Roampal Core

**长期方案**:
- 向OpenCode官方反馈Desktop版插件支持需求
- 或考虑切换到TUI/CLI版本以获得完整插件生态

### 注意事项

⚠️ **Roampal Desktop ≠ OpenCode Desktop插件**:
- Roampal Desktop是一个独立的GUI应用
- 它可以通过MCP连接到OpenCode Desktop
- 但这是两个独立应用协同工作，不是OpenCode的插件

---

## 七、验证结论

| 插件 | Desktop兼容性 | 置信度 | 建议 |
|------|--------------|--------|------|
| **Roampal Core** | ❓ 待验证 | 中等 | 需要实际安装测试 |
| **opencode-mem** | ⚠️ 可能兼容 | 中等偏高 | 标准插件API，独立存储，建议优先测试 |

**关键不确定性**: OpenCode Desktop是否支持标准的`@opencode-ai/plugin` API

**下一步**: 建议在测试环境实际安装测试opencode-mem，确认Desktop版插件系统兼容性

---

**报告生成时间**: 2026-02-13  
**数据来源**: 官方文档、GitHub、NPM  
**验证状态**: 理论分析完成，待实际测试
