# DCP策略风险分析与应对方法

**创建时间**: 2026-02-13 00:10:00
**版本**: v1.0
**存放位置**: D:\2bktest\MDview\

---

## 一、背景

### 1.1 什么是DCP

DCP（Dynamic Context Pruning，动态上下文剪枝）是OpenCode的一个插件，用于自动清理会话上下文中的冗余信息，节省token使用。

### 1.2 DCP的三个自动策略

| 策略 | 官方描述 | 默认状态 |
|------|---------|---------|
| deduplication | 识别并删除重复的工具调用 | 开启 |
| supersedeWrites | 删除被read覆盖的write调用 | 开启 |
| purgeErrors | 清除一定轮数后的错误信息 | 开启 |

### 1.3 问题由来

在使用DCP过程中，发现存在"Prune打劫"现象：工具输出被自动删除，导致重要信息丢失。经过详细分析，决定关闭所有自动策略，改为手动控制。

---

## 二、三个策略详解

### 2.1 deduplication（去重策略）

#### 2.1.1 官方定义

> Identifies repeated tool calls (e.g., reading the same file multiple times) and keeps only the most recent output.

#### 2.1.2 表面含义

相同工具 + 相同参数 = 保留最后一次调用

```
正确例子：
read test.go → read test.go → 只保留后一个（参数完全相同）

不正确例子：
read A → read B → read X → 不删除（A、B、X参数都不同）
```

#### 2.1.3 实际风险

##### 风险1：误删有用历史

```bash
# 场景：调试时需要对比多次分析结果
read test.go → 分析test.go，发现问题A
read test.go → 再次分析test.go，发现问题B
# 问题：第一次分析中可能包含用户需要的结论，被删除
```

##### 风险2：调试时需要对比

```bash
# 场景：对比前后两次读取的结果差异
read test.go → 版本1的代码分析
修改代码
read test.go → 版本2的代码分析
# 问题：想对比两个版本的差异，但第一次可能被删除
```

##### 风险3：推理链中断

```bash
# 场景：回顾之前的推理过程
read test.go → 我分析："这里可能有个bug"
修复bug
现在想回顾之前的分析："我当时是怎么发现这个bug的？"
# 问题：之前的分析记录已被删除，无法追溯
```

#### 2.1.4 总结

| 方面 | 说明 |
|------|------|
| 表面 | 删除重复调用，节省token |
| 实际 | 可能删除有用的历史记录 |
| 影响 | 调试困难、推理链中断 |

---

### 2.2 supersedeWrites（覆盖写入策略）

#### 2.2.1 官方定义

> Prunes write tool inputs for files that have subsequently been read. When a file is written and later read, the original write content becomes redundant since the current file state is captured in the read result.

#### 2.2.2 表面含义

先write后read同一文件 → 删除write，保留read

```bash
write test.go → read test.go
# 删除write，保留read（因为read已经包含文件的最新状态）
```

#### 2.2.3 实际风险

##### 风险1：丢失修改意图

```bash
# 场景：想知道"为什么要这样改"
write test.go  // 修改内容：修复登录bug
write test.go  // 修改内容：添加验证逻辑
read test.go   // 结果：显示修复后的代码
# 问题：删除write后，丢失了"为什么要这样改"的上下文
```

##### 风险2：丢失修改历史

```bash
# 场景：需要追溯修改历史
write test.go  // 第1次修改：添加登录功能
write test.go  // 第2次修改：添加验证逻辑
write test.go  // 第3次修改：添加错误处理
read test.go   // 结果：最终代码
# 问题：删除所有write，丢失了修改历史
```

##### 风险3：read结果不完整

```bash
# read test.go 的结果：
---
文件名：test.go
内容：[文件内容摘要]
---

# write工具的输出：
---
文件名：test.go
操作：写入
内容：[完整内容]
意图：修复登录验证bug
预期：用户登录成功
备注：修改了第15-20行的验证逻辑
---

# 问题：write包含的意图、预期、备注等信息，read结果里没有！
```

##### 风险4：调试时需要对比

```bash
# 场景：想知道"改了什么"
write test.go  // 修改前
read test.go   // 想对比：改了什么？
# 问题：如果删除write，不知道改了什么，只知道现在是什么
```

#### 2.2.4 总结

| 方面 | 说明 |
|------|------|
| 表面 | read已经包含最新状态，write冗余 |
| 实际 | 丢失意图、历史、修改原因 |
| 影响 | 无法追溯修改、调试困难 |

---

### 2.3 purgeErrors（清除错误策略）

#### 2.3.1 官方定义

> Prunes tool inputs for tools that returned errors after a configurable number of turns (default: 4).

#### 2.3.2 表面含义

工具调用出错后4轮（默认）→ 自动删除错误信息

```bash
第1轮：执行工具 → 出错 → 显示错误信息
第2轮：又出错 → 显示错误信息
第3轮：又出错 → 显示错误信息
第4轮：错误信息被删除！
```

#### 2.3.3 实际风险

##### 风险1：丢失调试线索

```bash
# 场景：想知道"当初是什么错误导致的"
第1轮：工具A出错了，显示"Connection refused"
第2轮：工具A又出错，显示同样的错误
第3轮：同样的错误
第4轮：错误信息被删除！

后来想问：当初是什么错误导致的？
→ 不知道了！
```

##### 风险2：错误原因无法追溯

```bash
# 场景：复杂流程中的错误排查
1. 工具A出错 → "file not found"
2. 工具B出错 → "permission denied"
3. 工具C出错 → "timeout"
→ 这些错误信息被删除后
→ 完全不知道问题出在哪里
```

##### 风险3：对比错误的机会丢失

```bash
# 如果保留错误信息，可以：
- 对比多次错误的差异
- 分析错误模式
- 找到根本原因

# 删除后：
- 无法分析
- 只能瞎猜
```

#### 2.3.4 总结

| 方面 | 说明 |
|------|------|
| 表面 | 清理过期错误，减少噪音 |
| 实际 | 丢失调试线索、无法追溯 |
| 影响 | 调试困难、问题难定位 |

---

## 三、风险总结

### 3.1 三个策略对比

| 策略 | 表面含义 | 实际风险 | 影响场景 |
|------|---------|---------|---------|
| deduplication | 删除重复调用 | 误删有用历史 | 调试、对比分析 |
| supersedeWrites | read覆盖write | 丢失意图历史 | 追溯修改、代码评审 |
| purgeErrors | 清除过期错误 | 丢失错误线索 | 错误排查、问题定位 |

### 3.2 共同问题

1. **理论合理 ≠ 实际安全**
   - 开发者以为的去重 ≠ 用户需要的保留
   - 自动删除的可能是用户回头需要的信息

2. **自动策略的隐患**
   - 无法区分"冗余信息"和"有用信息"
   - 一刀切的删除策略必然误伤

3. **调试场景的致命伤**
   - 需要对比历史输出
   - 需要追溯修改意图
   - 需要保留错误线索
   - 自动删除会破坏这些需求

---

## 四、应对方法

### 4.1 关闭所有自动策略

#### 最终配置（dcp.jsonc）

```json
{
  "debug": false,
  "tools": {
    "prune": {
      "permission": "allow"
    },
    "distill": {
      "permission": "allow"
    },
    "compress": {
      "permission": "allow"
    }
  },
  "strategies": {
    "deduplication": {
      "enabled": false
    },
    "supersedeWrites": {
      "enabled": false
    },
    "purgeErrors": {
      "enabled": false
    }
  }
}
```

#### 配置说明

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `debug` | false | 关闭调试日志 |
| `tools.*.permission` | allow | 允许手动调用 |
| `strategies.*.enabled` | false | 关闭所有自动策略 |

---

### 4.2 手动控制方法

#### 4.2.1 prune（剪枝工具）

**作用**: 手动删除指定的工具输出

**使用场景**:
- 某次工具输出确定没用
- 对话中出现大量无关输出
- 需要精简无关内容

**使用方式**:
```bash
# 在OpenCode中调用
/prune <tool_call_id>
# 或选择要删除的工具调用
```

---

#### 4.2.2 distill（蒸馏工具）

**作用**: 将对话内容精简为摘要

**使用场景**:
- 上下文太长时
- 需要保留核心信息
- 减少token消耗

**使用方式**:
```bash
/distill
# AI会生成摘要，保留核心信息
```

---

#### 4.2.3 compress（压缩工具）

**作用**: 压缩上下文

**使用场景**:
- 需要节省token
- 对话历史太长
- 需要保留整体结构

**使用方式**:
```bash
/compress
# AI会压缩上下文，保留重要信息
```

---

### 4.3 用户控制流程

```
1. 我执行工具 → 输出显示在对话中
2. 你觉得需要精简 → 手动调用 prune/distill/compress
3. 上下文被精简 → 继续工作
4. 不会再自动被打劫 → 完全由你控制
```

---

### 4.4 什么时候需要手动精简

| 情况 | 建议 |
|------|------|
| 大量无关输出堆积 | 使用 prune |
| 上下文太长（>50轮） | 使用 distill 或 compress |
| Token快用完了 | 使用 compress |
| 需要保留所有信息 | 不需要调用任何工具 |

---

## 五、总结

### 5.1 决策

| 策略 | 状态 | 原因 |
|------|------|------|
| deduplication | 关闭 | 保留所有工具输出，避免丢失有用历史 |
| supersedeWrites | 关闭 | 保留write的意图和历史，便于追溯 |
| purgeErrors | 关闭 | 保留所有错误信息，便于调试 |
| prune/distill/compress | 手动调用 | 用户控制什么时候需要精简 |

### 5.2 优势

1. **100%安全**
   - 不会自动删除任何信息
   - 用户决定什么时候需要精简

2. **保留所有信息**
   - 调试时可以对比历史
   - 可以追溯修改意图
   - 可以分析错误模式

3. **完全控制**
   - 用户最清楚什么时候需要什么信息
   - 手动调用，完全可控

### 5.3 代价

- Token消耗可能增加
- 需要用户手动管理上下文
- 长时间会话可能达到token限制

### 5.4 建议

1. **短期会话**：不需要调用任何精简工具
2. **中期会话**：选择性调用 prune 删除无关输出
3. **长期会话**：使用 distill 或 compress 精简上下文
4. **调试场景**：保留所有信息，不调用任何工具

---

**更新时间**: 2026-02-13 00:10:00
**版本**: v1.0
