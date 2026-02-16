# OMO子智能体的模型决策

**创建时间**: 2026-02-13 14:41:49

---

## 一、各子代理功能说明

### 1.1 Sisyphus（西西弗斯）

**定位**：主编排代理（Default Orchestrator）

**功能**：
- 规划、委派和执行复杂任务
- 使用专门的子代理进行积极的并行执行
- Todo驱动的工作流
- 扩展思维（32k budget）

**工具权限**：完全权限（读写、bash、webfetch等）

**推荐模型**：`anthropic/claude-opus-4-5`（原配置）
**当前使用**：`opencode/glm-4.7-free`

---

### 1.2 librarian（图书管理员）

**定位**：代码库研究者

**功能**：
- 多仓库分析
- 文档查询
- OSS实现示例查找
- 深度代码库理解，基于证据的回答

**工具权限**：只读（不能写入、编辑或委派）

**推荐模型**：`opencode/big-pickle`（原配置）
**当前使用**：`opencode/kimi-k2.5-free`

---

### 1.3 explore（探索者）

**定位**：快速代码库探索者

**功能**：
- 快速代码库探索
- 上下文grep
- 代码模式搜索
- 使用Glob、Grep等工具

**工具权限**：只读（不能写入、编辑或委派）

**推荐模型**：`opencode/gpt-5-nano`（原配置）
**当前使用**：`opencode/gpt-5-nano`

**触发时机**：
- 使用Gemini 3 Flash（Antigravity配置时）
- 使用Haiku（Claude max20配置时）
- 否则使用Grok

---

### 1.4 oracle（预言者/顾问）

**定位**：架构与调试顾问

**功能**：
- 架构决策
- 代码审查
- 调试支持
- 只读咨询

**能力**：
- 出色的逻辑推理
- 深入分析
- Read-only consultation
- 灵感来源：AmpCode

**工具权限**：只读（不能写入、编辑或委派）

**推荐模型**：`openai/gpt-5.2`（原配置）
**当前使用**：`opencode/big-pickle`

---

### 1.5 frontend-ui-ux-engineer（前端UI/UX工程师）

**定位**：前端设计与开发专家

**功能**：
- UI设计
- 视觉变化
- 样式处理
- 设计师转开发，打造令人惊艳的界面

**能力**：
- 设计流程：Purpose, Tone, Constraints, Differentiation
- 美学方向：极端风格（brutalist, maximalist, retro-futuristic, luxury, playful）
- 排版：独特的字体，避免通用字体
- 配色：连贯的调色板，避免AI风格的紫色+白色
- 动效：高影响力的交错揭示、滚动触发、令人惊喜的hover状态

**推荐模型**：`google/gemini-3-pro`（原配置）
**当前使用**：`opencode/kimi-k2.5-free`

---

### 1.6 document-writer（文档编写者）

**定位**：技术文档编写专家

**功能**：
- 技术文档编写
- 清晰、结构化的文档生成
- API文档、用户手册、开发者指南

**推荐模型**：配置中指定
**当前使用**：`opencode/minimax-m2.5-free`

---

### 1.7 multimodal-looker（多模态查看者）

**定位**：视觉内容专家

**功能**：
- 分析PDF、图片、图表
- 提取视觉文件中的信息
- 让另一个代理处理媒体内容以节省token

**工具权限**：白名单 only（read, glob, grep）

**推荐模型**：`google/gemini-3-flash`（原配置）
**当前使用**：`opencode/kimi-k2.5-free`

---

## 二、OpenCode Zen免费模型能力对比

### 2.1 模型规格对比表

| 模型 | 上下文 | 最大输出 | 输入价格 | 输出价格 | 核心能力 | SWE-Bench分数 |
|------|--------|----------|----------|----------|----------|--------------|
| **Big Pickle** | 200K | 128K | Free | Free | 高级推理、函数调用、文本生成 | 隐身模型 |
| **MiniMax M2.5 Free** | 198K | - | Free | Free | 编码、多语言支持、Agent流程 | **80.2%** |
| **Kimi K2.5 Free** | 256K | - | Free | Free | 原生多模态、视觉-代码集成、Agent Swarm | 76.8% |
| **GPT 5 Nano** | - | - | Free | Free | 轻量级、快速 | - |

### 2.2 Big Pickle（隐身模型）

**提供方**：OpenCode Zen

**核心特性**：
- 200K token上下文窗口
- 128K token最大输出
- 高级推理能力（Advanced Reasoning）
- 函数调用支持
- 文本生成能力
- 完全免费（长期）

**适用场景**：
- 需要深度推理的任务
- 复杂逻辑分析
- 架构设计
- 调试与问题诊断

**数据隐私**：免费期数据可能用于模型改进

**性能对比**：
- Context Window: 200K（vs Qwen3 Coder 262K）
- Pricing: Free（vs Qwen3 Coder $0.45/$1.80）
- Max Output: 128K（vs Qwen3 Coder 66K）

---

### 2.3 MiniMax M2.5 Free

**提供方**：MiniMax（OpenCode Zen）

**核心特性**：
- 198K context window
- SWE-Bench Verified: 80.2%（接近Claude Opus 4.6）
- 1/10th 成本（vs顶级竞争对手）
- 37% faster than M2.1
- 200K+ 训练环境（Forge RL Framework）
- 多语言支持：10+编程语言

**能力亮点**：
- 代码生成与审查
- 全栈Agentic AI（编码、web搜索、工具调用）
- Office工作（Word、Excel、PowerPoint）
- Agent原生训练（CISPO算法，40x训练加速）

**适用场景**：
- 编码任务
- 文档生成
- Agent工作流
- 多语言项目

**数据隐私**：免费期数据可能用于模型改进

---

### 2.4 Kimi K2.5 Free

**提供方**：Moonshot AI（OpenCode Zen）

**核心特性**：
- **256K context window**（最大）
- 原生多模态（文本、图片、视频）
- SWE-Bench: 76.8%
- Agent Swarm架构（可并行100个子代理）
- 视觉-代码集成

**独特能力**：
- **视频→代码**：从演示视频重建网站
- **图片→界面**：从设计稿生成交互式前端组件
- **视觉调试**：分析渲染输出并识别UI问题
- **前端开发**：从自然语言或视觉参考创建像素级布局和动画

**Agent Swarm能力**：
- 并行研究：同时执行多个搜索查询
- 批量处理：并发处理多个文件或文档
- 多步工作流：将复杂任务分解为协调的子任务（无需手动编排）

**适用场景**：
- 大规模代码库分析（256K上下文）
- 视觉-代码转换
- UI/UX设计与实现
- 图片/视频处理

**数据隐私**：免费期数据可能用于模型改进

---

### 2.5 GPT 5 Nano

**提供方**：OpenAI（OpenCode Zen）

**核心特性**：
- 轻量级模型
- 快速响应
- 完全免费（可能是长期）

**适用场景**：
- 简单任务
- 快速grep
- 代码库搜索
- 不需要复杂推理的场景

**限制**：
- 不适合复杂推理任务
- 不适合深度代码审查
- 不适合大规模上下文处理

---

## 三、模型选择决策过程

### 3.1 决策原则

根据用户明确要求：
1. ✅ **Sisyphus保持GLM-4.7-free**（不能改）
2. ✅ **GPT 5 Nano用于其他子代理**（不用在Sisyphus和oracle上）
3. ✅ **oracle不用GPT 5 Nano**
4. ✅ **Big Pickle用在需要推理的agent上**

### 3.2 代理-模型匹配分析

#### 3.2.1 Sisyphus（主编排器）

**原配置**：`opencode/glm-4.7-free`

**用户要求**：保持不变 ✅

**原因**：
- GLM-4.7-free是用户指定模型
- 主编排器需要统一的模型管理
- 不修改按用户要求

**最终决定**：`opencode/glm-4.7-free`

---

#### 3.2.2 librarian（图书管理员）

**原配置**：`opencode/glm-4.7-free`

**优化方案**：`opencode/kimi-k2.5-free`

**选择原因**：
1. **最大上下文需求**：librarian需要分析大型代码库和文档，Kimi K2.5的256K上下文窗口是免费的
2. **SWE-Bench分数**：76.8%足够处理代码库理解任务
3. **多仓库分析**：Kimi K2.5的Agent Swarm能力可以并行处理多个仓库

**为什么不选其他模型**：
- Big Pickle：虽然推理强，但librarian更需要上下文容量
- MiniMax M2.5 Free：SWE-Bench分数更高，但Kimi的256K上下文更适合
- GPT 5 Nano：上下文不足，只能处理简单grep任务

**最终决定**：`opencode/kimi-k2.5-free`

---

#### 3.2.3 explore（探索者）

**原配置**：`opencode/glm-4.7-free`

**优化方案**：`opencode/gpt-5-nano`

**选择原因**：
1. **任务性质**：explore主要用于快速grep和代码库搜索，不需要复杂推理
2. **成本考虑**：GPT 5 Nano完全免费，适合频繁调用的探索任务
3. **速度优势**：轻量级模型，响应更快
4. **原推荐模型**：官方推荐就是`opencode/gpt-5-nano`

**为什么不选其他模型**：
- Big Pickle：过度使用，浪费高级推理能力
- Kimi K2.5 Free：过度使用，浪费256K大上下文
- MiniMax M2.5 Free：过度使用，浪费80.2% SWE-Bench能力

**最终决定**：`opencode/gpt-5-nano`

---

#### 3.2.4 oracle（预言者/顾问）

**原配置**：`opencode/glm-4.7-free`

**优化方案**：`opencode/big-pickle`

**选择原因**：
1. **深度推理需求**：oracle需要高级推理能力用于架构审查和调试
2. **用户明确要求**：oracle不用GPT 5 Nano，Big Pickle适合深度推理
3. **Big Pickle优势**：200K上下文 + 高级推理 + 函数调用
4. **只读权限**：oracle是只读代理，不需要写入能力，专注于分析

**为什么不选其他模型**：
- GPT 5 Nano：用户明确要求不使用
- Kimi K2.5 Free：虽然上下文大，但Big Pickle的推理能力更适合oracle
- MiniMax M2.5 Free：编码能力强，但oracle更需要推理而不是编码

**最终决定**：`opencode/big-pickle`

---

#### 3.2.5 frontend-ui-ux-engineer（前端UI/UX工程师）

**原配置**：`opencode/glm-4.7-free`

**优化方案**：`opencode/kimi-k2.5-free`

**选择原因**：
1. **原生多模态能力** ⭐：Kimi K2.5的原生多模态（文本+图片+视频）是UI/UX设计的核心需求
2. **视觉-代码集成**：
   - 视频→网站：从演示视频重建完整网站
   - 图片→界面：从设计稿生成交互式组件
   - 视觉调试：分析渲染输出并修复UI问题
3. **Agent Swarm**：可以并行处理多个UI组件或页面
4. **256K上下文**：可以处理完整的UI设计规范和组件库

**为什么不选其他模型**：
- GPT 5 Nano：无多模态能力
- Big Pickle：无多模态能力
- MiniMax M2.5 Free：编码能力强但不是原生多模态

**最终决定**：`opencode/kimi-k2.5-free`

---

#### 3.2.6 document-writer（文档编写者）

**原配置**：`opencode/glm-4.7-free`

**优化方案**：`opencode/minimax-m2.5-free`

**选择原因**：
1. **SWE-Bench最高分**：80.2%，是最强的免费编码模型
2. **代码生成能力**：适合编写包含代码示例的技术文档
3. **Office文件集成**：MiniMax M2.5能创建Word、Excel、PowerPoint文件
4. **Agent原生训练**：经过200K+环境训练，适合结构化任务

**为什么不选其他模型**：
- GPT 5 Nano：不满足文档生成的质量要求
- Big Pickle：编码和文档生成能力不如MiniMax
- Kimi K2.5 Free：虽然多模态，但MiniMax的SWE-Bench分数更高，适合文档+代码

**最终决定**：`opencode/minimax-m2.5-free`

---

#### 3.2.7 multimodal-looker（多模态查看者）

**原配置**：`opencode/glm-4.7-free`

**优化方案**：`opencode/kimi-k2.5-free`

**选择原因**：
1. **原生多模态** ⭐：这是multimodal-looker的核心需求
   - 文本分析
   - 图片解析
   - 视频理解
2. **视觉专家**：Kimi K2.5专为视觉推理设计
3. **Agent Swarm**：可以并行处理多个视觉文件
4. **256K上下文**：可以处理长文档、长视频、大图片

**为什么不选其他模型**：
- GPT 5 Nano：无多模态能力
- Big Pickle：无多模态能力
- MiniMax M2.5 Free：虽然有图像输入，但Kimi的原生多模态更强大

**最终决定**：`opencode/kimi-k2.5-free`

---

## 四、最终配置方案

### 4.1 配置汇总表

| 代理 | 原模型 | 新模型 | 变更原因 |
|------|--------|--------|----------|
| Sisyphus | opencode/glm-4.7-free | **opencode/glm-4.7-free** | 用户要求保持不变 |
| librarian | opencode/glm-4.7-free | **opencode/kimi-k2.5-free** | 256K上下文适合代码库分析 |
| explore | opencode/glm-4.7-free | **opencode/gpt-5-nano** | GPT 5 Nano适合快速探索 |
| oracle | opencode/glm-4.7-free | **opencode/big-pickle** | Big Pickle高级推理适合架构审查 |
| frontend-ui-ux-engineer | opencode/glm-4.7-free | **opencode/kimi-k2.5-free** | Kimi原生多模态适合视觉-代码转换 |
| document-writer | opencode/glm-4.7-free | **opencode/minimax-m2.5-free** | MiniMax SWE-Bench 80.2%适合文档+代码 |
| multimodal-looker | opencode/glm-4.7-free | **opencode/kimi-k2.5-free** | Kimi原生多模态适合图片视频处理 |

### 4.2 配置文件内容

```json
{
  "$schema": "https://raw.githubusercontent.com/code-yeongyu/oh-my-opencode/master/assets/oh-my-opencode.schema.json",
  "agents": {
    "sisyphus": {
      "model": "opencode/glm-4.7-free"
    },
    "librarian": {
      "model": "opencode/kimi-k2.5-free"
    },
    "explore": {
      "model": "opencode/gpt-5-nano"
    },
    "oracle": {
      "model": "opencode/big-pickle"
    },
    "frontend-ui-ux-engineer": {
      "model": "opencode/kimi-k2.5-free"
    },
    "document-writer": {
      "model": "opencode/minimax-m2.5-free"
    },
    "multimodal-looker": {
      "model": "opencode/kimi-k2.5-free"
    }
  }
}
```

### 4.3 模型使用统计

| 模型 | 使用代理数 | 使用代理列表 |
|------|-----------|------------|
| opencode/glm-4.7-free | 1 | Sisyphus |
| opencode/kimi-k2.5-free | 3 | librarian, frontend-ui-ux-engineer, multimodal-looker |
| opencode/gpt-5-nano | 1 | explore |
| opencode/big-pickle | 1 | oracle |
| opencode/minimax-m2.5-free | 1 | document-writer |

---

## 五、注意事项

### 5.1 临时免费模型

以下模型标注为"临时免费"，可能会结束免费期：
- MiniMax M2.5 Free
- Kimi K2.5 Free
- Big Pickle（虽然标注为临时免费，但可能是长期）

### 5.2 数据隐私

免费期的数据可能被用于改进模型：
- Big Pickle: 临时free期间，收集的数据可能用于改进模型
- Kimi K2.5 Free: 临时free期间，收集的数据可能用于改进模型
- MiniMax M2.5 Free: 临时free期间，收集的数据可能用于改进模型

### 5.3 GLM-4.7-free状态

根据GitHub issue讨论：
- GLM-4.7在某些情况下是临时免费的
- 建议：如果有预算，考虑订阅稳定的提供商（如智谱AI官方、Novita AI等）

### 5.4 性能差异

- GPT 5 Nano是最基础的模型，只适合简单任务
- 不适合用于需要复杂推理、深度分析的代理
- oracle、文档编写等任务需要更强大的模型

---

**更新时间**: 2026-02-13 14:41:49
**版本**: v1.0
