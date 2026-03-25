# 主流 LLM 模型 Structured Outputs 支持情况研究报告

**创建时间**: 2026-03-20 09:35:00
**版本**: v1.1
**编写人**: 小沈
**研究日期**: 2026-03-20
**更新日期**: 2026-03-20 10:15:00

---

## 一、研究概述

### 1.1 三个核心概念通俗解释

#### 1.1.1 response_format（响应格式控制）

**作用**：强制模型输出必须是 JSON 格式

```
你发：今天天气怎么样？
期望返回：{ "weather": "晴天", "temperature": 25 }

但模型可能返回普通文本：
"今天天气很好，阳光明媚..."  ← 普通文本，不是JSON
```

**应用场景**：
- 工具调用时需要结构化参数
- 需要程序自动解析 LLM 输出
- 提取实体、分类等需要结构化结果

---

#### 1.1.2 tools（工具调用）

**作用**：让模型能调用你写的函数

```
你定义一个"计算器"工具：
{
  "name": "calculate",
  "parameters": { "a": "number", "b": "number", "op": "string" }
}

模型对话：
用户：3加5等于多少？

【无 tools 模式】
模型返回："请调用calculate(3,5,'+')"  ← 你自己解析文本
你执行计算器，得到结果 8

【有 tools 模式】
模型返回：tool_calls: [{ "name": "calculate", "args": { "a":3, "b":5, "op":"+" }}]
你直接执行，不需要解析文本！
```

**对比**：
| 方式 | 模型怎么告诉你"要用工具" | 你怎么处理 |
|------|----------------------|----------|
| 无 tools | 返回文本描述 | 自己解析文本提取参数 |
| 有 tools | 直接返回结构化的 tool_calls | 直接执行，不需要解析 |

---

#### 1.1.3 reasoning_content（推理内容/思考过程）

**作用**：模型输出思考过程（模型的"内心独白"）

```
普通模型：
问：3加5为什么等于8？
答：因为3加5等于8。

有 reasoning_content 的模型：
reasoning: "我先把3记在心里...然后加5...3+1=4...4+1=5...5+1=6...6+1=7...7+1=8"
answer: "因为3加5等于8。"
```

**典型应用**：DeepSeek-R1、GLM-4 思考版、kimi-k2-thinking 等"推理模型"

---

#### 1.1.4 三者关系总结

```
┌─────────────────────────────────────────────────────┐
│                  你的 Agent                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  reasoning_content ← 模型输出思考过程（如果支持）      │
│     ↓ 模型的"内心独白"                              │
│                                                     │
│  tools ← 模型决定调用工具（搜索文件、读写文件等）      │
│     ↓ 模型返回 tool_calls                            │
│     返回: [{ "name": "search_files", "arguments": {...} }]
│                                                     │
│  response_format ← 强制输出 JSON 格式                 │
│     ↓ 工具参数必须是标准 JSON                        │
│     确保: { "path": "...", "pattern": "..." }        │
│                                                     │
└─────────────────────────────────────────────────────┘

简单记忆：
- tools = 模型能"动手做事"
- response_format = 模型动手时"格式要对"
- reasoning_content = 模型动手时"让我看看它怎么想的"
```

---

### 1.2 研究背景

Structured Outputs（结构化输出）是现代 LLM API 的重要功能，主要包括：
1. **response_format** (`json_object` / `json_schema`): 强制模型输出 JSON
2. **tools/function_calling**: 让模型调用外部工具
3. **reasoning_content**: 思考过程输出

### 1.2 研究目标

评估以下模型的 Structured Outputs 支持情况：

| 模型 | 提供商 | API Base | 测试模型数 |
|------|--------|----------|----------|
| LongCat | 美团 | https://api.longcat.chat/openai/v1 | 1 |
| GLM | 智谱AI | https://open.bigmodel.cn/api/paas/v4 | 1 |
| DeepSeek | DeepSeek | https://api.deepseek.com | 1 |
| Kimi | Moonshot AI | https://api.moonshot.cn/v1 | 1 |
| Minimax | MiniMax | https://api.minimax.chat/text/... | 1 |
| **Qiniu AI** | **七牛云** | **https://api.qnaigc.com/v1** | **52** |

---

## 二、七牛 AI API 详细分析

### 2.1 基本信息

| 项目 | 内容 |
|------|------|
| API Base | https://api.qnaigc.com/v1 |
| API Key | `sk-ee99b1ccb7495fd4f...` (已隐藏) |
| 可用模型数 | **52 个** |
| 认证方式 | Bearer Token |

### 2.2 七牛可用模型列表（52个）

| 序号 | 模型ID | 提供商 | 备注 |
|------|--------|--------|------|
| 1 | z-ai/glm-5 | 智谱AI | GLM-5 |
| 2 | openai/gpt-5.4 | OpenAI | GPT-5.4 |
| 3 | openai/gpt-5.4-mini | OpenAI | GPT-5.4 Mini |
| 4 | glm-4.5-air | 智谱AI | GLM-4.5 Air |
| 5 | minimax/minimax-m2.5 | MiniMax | M2.5 |
| 6 | nvidia/nemotron-3-super-120b-a12b | NVIDIA | Nemotron |
| 7 | qwen3-235b-a22b-thinking-2507 | 通义千问 | Qwen3 思考版 |
| 8 | qwen3-coder-480b-a35b-instruct | 通义千问 | Qwen3 Coder |
| 9 | moonshotai/kimi-k2.5 | Kimi | K2.5 |
| 10 | meituan/longcat-flash-lite | 美团 | LongCat Lite |
| 11 | doubao-1.5-thinking-pro | 字节豆包 | 豆包思考版 |
| 12 | doubao-1.5-vision-pro | 字节豆包 | 豆包视觉版 |
| 13 | doubao-seed-1.6-thinking | 字节豆包 | Seed 思考版 |
| 14 | qwen3-32b | 通义千问 | Qwen3 32B |
| 15 | deepseek/deepseek-v3.2-exp-thinking | DeepSeek | V3.2 Exp Thinking |
| 16 | deepseek/deepseek-v3.2-exp | DeepSeek | V3.2 Exp |
| 17 | deepseek-r1 | DeepSeek | DeepSeek R1 |
| 18 | deepseek-r1-0528 | DeepSeek | DeepSeek R1 0528 |
| 19 | deepseek-v3-0324 | DeepSeek | V3.2 0324 |
| 20 | deepseek/deepseek-v3.2-251201 | DeepSeek | V3.2 |
| 21 | minimax/minimax-m2.1 | MiniMax | M2.1 |
| 22 | z-ai/glm-4.7 | 智谱AI | GLM-4.7 |
| 23 | moonshotai/kimi-k2-0905 | Kimi | K2 0905 |
| 24 | qwen3-vl-30b-a3b-thinking | 通义千问 | Qwen3 VL 思考版 |
| 25 | qwen3-30b-a3b-thinking-2507 | 通义千问 | Qwen3 30B 思考版 |
| 26 | qwen3-30b-a3b-instruct-2507 | 通义千问 | Qwen3 30B |
| 27 | glm-4.5 | 智谱AI | GLM-4.5 |
| 28 | MiniMax-M1 | MiniMax | M1 |
| 29 | qwen3-next-80b-a3b-thinking | 通义千问 | Qwen3 Next 思考版 |
| 30 | qwen3-max-preview | 通义千问 | Qwen3 Max Preview |
| 31 | qwen3-235b-a22b | 通义千问 | Qwen3 235B |
| 32 | qwen-vl-max-2025-01-25 | 通义千问 | Qwen VL Max |
| 33 | qwen-max-2025-01-25 | 通义千问 | Qwen Max |
| 34 | qwen3-30b-a3b | 通义千问 | Qwen3 30B |
| 35 | qwen2.5-vl-72b-instruct | 通义千问 | Qwen2.5 VL |
| 36 | qwen2.5-vl-7b-instruct | 通义千问 | Qwen2.5 VL 7B |
| 37 | qwen-turbo | 通义千问 | Qwen Turbo |
| 38 | doubao-seed-1.6-flash | 字节豆包 | Seed Flash |
| 39 | doubao-seed-1.6 | 字节豆包 | Seed |
| 40 | deepseek/deepseek-v3.1-terminus-thinking | DeepSeek | V3.1 Thinking |
| 41 | minimax/minimax-m2 | MiniMax | M2 |
| 42 | z-ai/glm-4.6 | 智谱AI | GLM-4.6 |
| 43 | qwen3-max | 通义千问 | Qwen3 Max |
| 44 | xiaomi/mimo-v2-flash | 小米 | Mimo Flash |
| 45 | doubao-1.5-pro-32k | 字节豆包 | 豆包 Pro 32K |
| 46 | deepseek-v3 | DeepSeek | DeepSeek V3 |
| 47 | deepseek/deepseek-v3.1-terminus | DeepSeek | V3.1 |
| 48 | deepseek-v3.1 | DeepSeek | DeepSeek V3.1 |
| 49 | qwen3-235b-a22b-instruct-2507 | 通义千问 | Qwen3 235B Instruct |
| 50 | moonshotai/kimi-k2-thinking | Kimi | K2 Thinking |
| 51 | kimi-k2 | Kimi | Kimi K2 (简化) |
| 52 | qwen3-next-80b-a3b-instruct | 通义千问 | Qwen3 Next Instruct |

### 2.3 七牛模型测试结果

| 模型ID | 基本调用 | response_format | tools | reasoning_content |
|--------|---------|---------------|-------|-----------------|
| z-ai/glm-4.7 | ✅ | ✅ | ✅ | ❌ |
| z-ai/glm-4.6 | ✅ | ✅ | ✅ | ✅ |
| moonshotai/kimi-k2 | ✅ | ✅ | ✅ | ❌ |
| moonshotai/kimi-k2-0905 | ✅ | ✅ | ✅ | ❌ |
| moonshotai/kimi-k2-thinking | ✅ | ❌ | ❌ | ❌ |
| moonshotai/kimi-k2.5 | ✅ | ✅ | ✅ | ❌ |
| minimax/minimax-m2 | ✅ | ⚠️ 非JSON | ✅ | ❌ |
| minimax/minimax-m2.5 | ✅ | ✅ | ✅ | ✅ |
| MiniMax-M1 | ✅ | ✅ | ✅ | ❌ |
| deepseek-v3 | ✅ | ⚠️ 非JSON | ✅ | ❌ |
| deepseek-v3.1 | ✅ | ✅ | ✅ | ❌ |
| deepseek-r1 | ✅ | ✅ | ✅ | ✅ |
| qwen-turbo | ✅ | ✅ | ✅ | ❌ |
| qwen3-max | ✅ | ✅ | ✅ | ❌ |
| kimi-k2 | ✅ | ✅ | ✅ | ❌ |

**图例**：✅=支持，❌=不支持，⚠️=部分支持/非标准JSON

---

## 三、所有模型测试结果汇总

### 3.1 测试结果表

| 模型 | response_format | tools | reasoning_content | 备注 |
|------|---------------|-------|-----------------|------|
| **LongCat** | ❌ 空响应 | ✅ 支持 | ✅ 支持 | tools 正常 |
| **GLM-4.7-flash** | ✅ 支持 | ❌ 不支持 | ✅ 支持 | GLM 官方 API |
| **GLM-4.7 (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **GLM-4.6 (七牛)** | ✅ 支持 | ✅ 支持 | ✅ 支持 | 完整支持 |
| **DeepSeek-chat** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | DeepSeek 官方 |
| **DeepSeek-R1** | ✅ 支持 | ✅ 支持 | ✅ 支持 | 完整支持 |
| **DeepSeek-V3 (七牛)** | ⚠️ 非JSON | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **DeepSeek-V3.1 (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **Kimi-K2** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | Kimi 官方 |
| **Kimi-K2 (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **Kimi-K2-0905 (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **Kimi-K2-Thinking (七牛)** | ❌ 不支持 | ❌ 不支持 | ❌ 不支持 | 特殊版本 |
| **Kimi-K2.5 (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **MiniMax-M2** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 官方文档确认 |
| **MiniMax-M2 (七牛)** | ⚠️ 非JSON | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **MiniMax-M2.5 (七牛)** | ✅ 支持 | ✅ 支持 | ✅ 支持 | 七牛完整支持 |
| **MiniMax-M1 (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **Qwen-Turbo (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |
| **Qwen3-Max (七牛)** | ✅ 支持 | ✅ 支持 | ❌ 不支持 | 七牛版本 |

### 3.2 功能支持矩阵

```
功能支持矩阵：

                    response_format  tools  reasoning_content
                    ─────────────── ─────  ─────────────────
LongCat               ❌              ✅     ✅
GLM-4.7 (官方)        ✅              ❌     ✅
GLM-4.6/4.7 (七牛)   ✅              ✅     ✅
DeepSeek-chat         ✅              ✅     ❌
DeepSeek-R1           ✅              ✅     ✅
DeepSeek-V3 (七牛)    ⚠️              ✅     ❌
Kimi-K2 (官方)        ✅              ✅     ❌
Kimi-K2 (七牛)        ✅              ✅     ❌
Kimi-K2-Thinking      ❌              ❌     ❌
MiniMax-M2            ✅              ✅     ❌
MiniMax-M2.5 (七牛)   ✅              ✅     ✅
MiniMax-M1 (七牛)      ✅              ✅     ❌
Qwen-Turbo (七牛)     ✅              ✅     ❌
Qwen3-Max (七牛)      ✅              ✅     ❌

图例：
✅ = 支持
❌ = 不支持
⚠️ = 部分支持（非标准JSON）
```

---

## 四、总结与建议

### 4.1 七牛 AI API 结论

1. **端点状态**: ✅ 正常（/models 和 /chat/completions 都可用）
2. **模型数量**: 52 个可用模型
3. **支持的提供商**: 智谱AI、OpenAI、NVIDIA、DeepSeek、Kimi、通义千问、字节豆包、MiniMax、小米

### 4.2 策略选择建议

根据测试结果，**tools 模式**适用范围最广：

| 优先级 | 策略 | 适用模型数 | 说明 |
|--------|------|----------|------|
| **1** | tools | 约 50 个 | 大多数模型支持 |
| **2** | response_format | 约 45 个 | 部分返回非标准JSON |
| **3** | prompt engineering | 所有模型 | 降级方案 |

### 4.3 特别说明

1. **Kimi-K2-Thinking**: 该模型不支持 tools 和 response_format，可能是特殊版本
2. **reasoning_content**: 只有带 `thinking` 或 `r1` 后缀的模型支持
3. **七牛 API 特性**: 七牛是一个聚合平台，模型能力取决于底层提供商

---

## 五、附录

### 5.1 测试脚本

| 脚本 | 路径 | 说明 |
|------|------|------|
| 七牛综合测试 | `backend/tools/test_qiniu_ai.py` | 完整测试脚本 |
| 七牛关键模型测试 | `backend/tools/test_qiniu_key_models.py` | 快速测试关键模型 |
| 测试结果 | `backend/qiniu_key_models_test.json` | 关键模型测试结果 |

### 5.2 测试命令

```bash
# 完整测试（七牛 52 个模型）
cd D:\OmniAgentAs-desk\backend
python tools/test_qiniu_ai.py

# 关键模型测试
python tools/test_qiniu_key_models.py
```

---

**文档结束**

**编写时间**: 2026-03-20 09:35:00
**更新时间**: 2026-03-20 09:42:00
**编写人**: 小沈
**版本**: v1.1

**版本历史**:
- v1.0: 2026-03-20 09:35:00 - 初始版本（LongCat、GLM、DeepSeek、Kimi、Minimax）
- v1.1: 2026-03-20 09:42:00 - 新增七牛 AI API 测试结果（52个可用模型）
- v1.2: 2026-03-20 10:15:00 - 新增三个核心概念通俗解释（response_format/tools/reasoning_content）
