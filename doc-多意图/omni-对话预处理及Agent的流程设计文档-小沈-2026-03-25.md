# OmniAgent对话预处理及Agent的流程设计文档

**创建时间**: 2026-03-25 13:51:48
**更新时间**: 2026-03-26 15:47:58
**版本**: v2.80
**编写人**: 小沈

---

## 📚 参考文档

本设计文档参考以下文档：

| 参考文档 | 说明 |
|---------|------|
| `Agent分层重构设计方案-小沈-2026-03-25.md` | Agent分层架构设计原始方案，提供了BaseAgent与IntentReactAgent继承关系的详细设计 |
| `LLM调用prompt中间层设计方案-小沈-2026-03-24.md` | Prompt中间层设计，定义了Prompt构建和管理的架构 |
| `多意图系统与现有代码整合架构设计-2026-03-22.md` | 多意图系统与现有代码的整合架构 |
| `2.预处理与多意图代码目录说明-小沈-2026-03-22.md` | 预处理与多意图代码目录结构说明 |

---

## 版本历史

| 版本 | 时间 | 更新内容 |
|------|------|---------|
| v1.0 | 2026-03-25 13:51:48 | 初始版本：对话预处理流程设计 |
| v1.1 | 2026-03-25 14:03:14 | 修正架构：预处理调用chat2，不是chat2调用预处理 |
| v1.2 | 2026-03-25 14:14:04 | Session管理并入chat2，职责更清晰 |
| v1.3 | 2026-03-25 14:18:02 | 补充文件引用、history处理、实际参数核对 |
| v1.4 | 2026-03-25 14:22:49 | 补充agent创建、意图判断逻辑、函数引入路径 |
| v1.5 | 2026-03-25 15:33:27 | 新增1.1.1问题发现过程，详细记录问题发现步骤 |
| v2.0 | 2026-03-25 16:00:00 | 合并对话预处理流程设计 + Agent分层重构设计方案，成为完整设计文档 |
| v2.1 | 2026-03-25 17:10:00 | 添加参考文档章节 |
| v2.2 | 2026-03-25 17:30:00 | 优化章节布局：整合Agent分层设计到第四章，合并文件位置与职责划分到第六章，统一待实现清单到第七章 |
| v2.3 | 2026-03-25 17:40:00 | 第一章1.3节添加说明，整合自参考文档Agent分层重构设计方案 |
| v2.4 | 2026-03-25 17:45:00 | 第二章2.1节添加Agent说明，特指IntentReactAgent |
| v2.5 | 2026-03-25 17:50:00 | 第二章2.3节添加chat2与Agent关系详细说明 |
| v2.6 | 2026-03-25 17:55:00 | 第四章标题改为Agent分层架构设计与实现说明，删除4.6实施步骤移到第七章 |
| v2.7 | 2026-03-25 18:00:00 | 确认7.4节已包含Agent分层重构待实现项 |
| v2.8 | 2026-03-25 18:40:00 | 新增7.1本次代码重组原则 |
| v2.9 | 2026-03-25 18:50:00 | 修正7.2/7.3/7.4，严格按照2.1架构：预处理是独立模块在路由层调用，禁止在chat2内部调用预处理 |
| v2.10 | 2026-03-25 19:00:00 | 修正7.5 Agent分层重构，整合4.5.2未完成项，不是清空重写 |
| v2.11 | 2026-03-25 19:10:00 | 删除末尾重复Session内容，修正第四章标题层级，删除7.6回归验证移至附录 |
| v2.12 | 2026-03-25 19:15:00 | 修正2.7.1预处理代码示例：预处理不调用chat2，由路由层串联调用 |
| v2.13 | 2026-03-25 19:20:00 | 修正6.1文件位置（PreprocessingPipeline/IntentRegistry正确路径），修正6.2.1预处理职责（不调用chat2） |
| v2.14 | 2026-03-25 19:29:45 | 修正6.3 Session管理：补充两层Session管理（chat2.py任务管理 + session.py文件操作会话），删除不准确的Session生命周期描述，补充代码位置和实际状态值 |
| v2.15 | 2026-03-25 19:38:24 | 新增6.3.4节：添加6.3 Session管理与报告设计方案的逻辑关系图，说明两者是架构层与实现层的关系 |
| v2.16 | 2026-03-25 19:42:42 | 新增7.1.1核心教训：明确本次梳理的目的是"正确整合已有功能到主流程"，强调"单元重构完成≠重构目的达到" |
| v2.17 | 2026-03-25 19:46:12 | 新增7.3遗留问题修复：补充 `2.预处理与多意图代码目录说明-小沈-2026-03-22.md` 7.7节的遗留问题（agent.py:452应用preprocessed['corrected']替代原始task） |
| v2.18 | 2026-03-25 19:59:02 | 修正7.4路由改造：引用整合架构设计，新增chat_router.py设计，强调chat2不能作为路由层，废除detect_file_operation_intent |
| v2.19 | 2026-03-25 20:09:30 | 整合两个文档的2.1节：合并整合架构设计的chat_router.py架构图，替换OMNI的2.1节，明确chat_router/预处理/IntentReactAgent职责分工 |
| v2.20 | 2026-03-25 20:15:07 | 新增Agent命名规范（7.5节）：IntentReactAgent统一改名为intent-file-ReactAgent，避免与BaseAgent混淆 |
| v2.21 | 2026-03-25 20:19:07 | 全面替换文档中所有IntentReactAgent为intent-file-ReactAgent（1.3/2.1/2.3/2.7/3.3/4.2/4.3/4.5/5.1/6.1/6.2节） |
| v2.22 | 2026-03-25 21:18:40 | 新增附录2：ReAct架构层次说明，明确base.py是底层ReAct、agent.py是上层Intent-*-React、chat2是混合体 |
| v2.23 | 2026-03-25 21:31:13 | 整理附录2.3为清晰的三层架构：底层ReAct(base.py)→上层Intent-*-React(agent.py)→路由层(chat_router.py待创建) |
| v2.24 | 2026-03-25 22:09:19 | 替换附录2.4为四层架构：路由层→意图特定React→chat2流式包装→base.py通用ReAct；明确agent.py约等于intent-file-ReactAgent |
| v2.25 | 2026-03-25 22:12:52 | 删除冗余的附录2.3（中间状态），保留完整的附录2.3（四层架构最终版） |
| v2.26 | 2026-03-25 22:17:08 | 修正章节编号：附录2.4改为附录2.3，各子章节同步更新 |
| v2.27 | 2026-03-25 22:20:36 | 新增附录2.4：base.py改名base-react.py，理由和同步更新说明 |
| v2.28 | 2026-03-25 22:28:07 | 完成base.py→base_react.py改名，同步更新所有导入，测试通过20个 |
| v2.29 | 2026-03-25 22:36:38 | 新增附录2.5：chat_router.py架构决策（放置位置、意图检测方式、职责、与chat2.py关系澄清） |
| v2.30 | 2026-03-25 22:45:00 | 重组附录2.5-2.8：按四层架构重组（附录2.5路由层、2.6意图特定层、2.7流式包装层、2.8文件清单） |
| v2.31 | 2026-03-25 22:50:00 | 删除附录2.5.4：与chat2.py关系澄清（构建router时不会与chat2有任何牵涉） |
| v2.32 | 2026-03-25 23:05:00 | 废除detect_file_operation_intent()任务移至附录2.7（chat2.py改造），补充说明函数位置和引用情况 |
| v2.33 | 2026-03-25 23:12:00 | 附录2.7重命名为react_sse_wrapper.py，文件名和类名更新 |
| v2.34 | 2026-03-25 23:15:00 | 附录2.7.3改为"需要抽取的内容"：明确从chat2.py抽取SSE/中断/调用base_react的逻辑，废弃chat2.py |
| v2.35 | 2026-03-25 23:18:00 | 删除附录2.7.4中废除detect_file_operation_intent()任务（废弃chat2.py时自然废除，无需单独处理） |
| v2.36 | 2026-03-25 23:25:00 | 附录2.6更新：文件命名为file_react.py+FileReactAgent，明确逐步抽取+废弃原文件的改造思路 |
| v2.37 | 2026-03-25 23:35:00 | 附录2.6.3/2.6.4补充：从agent.py和chat2.py抽取的完整内容清单（基于代码深入分析） |
| v2.38 | 2026-03-25 23:50:00 | 附录2.3更新：四层架构图按2.6/2.7讨论更新（file_react.py/FileReactAgent/react_sse_wrapper.py） |
| v2.39 | 2026-03-26 00:10:00 | 小健检查修复：附录2.6.4移到2.7、更新2.7职责/抽取内容/待实现任务、修正2.3.4描述、更新2.8文件清单 |
| v2.40 | 2026-03-26 11:30:00 | 附录2.6.2改造思路优化：改"抽取法"为"复制+删除法"，补充SSE依赖模块说明，更新待实现任务清单 |
| v2.41 | 2026-03-26 11:50:00 | 附录2.6.5实施记录：file_react.py创建完成，删除intent-type分支，32个测试全部通过，commit e15abcbe |
| v2.42 | 2026-03-26 07:56:05 | 附录2.7分阶段实施方案标题改为附录2.8，原附录2.8文件清单改为附录2.9 |
| v2.43 | 2026-03-26 07:56:05 | 附录2.9文件清单更新：按四层架构重新排序，修正各文件对应层级 |
| v2.44 | 2026-03-26 07:58:00 | 附录2.7层级修正：第三层改为第二层（react_sse_wrapper） |
| v2.45 | 2026-03-26 07:58:00 | 附录2.5阶段1实施完成：chat_router.py创建完成，调用PreprocessingPipeline实现意图分发 |
| v2.46 | 2026-03-26 08:10:00 | 小健检查修复：删除未使用uuid导入，区分chat/其他意图提示，文档补充chat_stream_query已实现说明 |
| v2.47 | 2026-03-26 08:15:00 | 新增附录：TODO待处理清单，汇总2个TODO项 |
| v2.48 | 2026-03-26 08:20:00 | 附录2.7.4添加说明：任务为对照检查项，实际操作在2.7.5 |
| v2.49 | 2026-03-26 08:22:00 | 修复：附录2.7层级错误（新第三层改为第二层），附录2.9文件清单更新chat_router状态 |
| v2.50 | 2026-03-26 08:38:42 | 附录2.7阶段2实施完成：react_sse_wrapper.py创建完成，删除FastAPI代码，转换为服务层函数，语法验证通过 |
| v2.51 | 2026-03-26 08:53:33 | 补充阶段2当前实施状态说明：file_react.ver1_run_stream尚未删除，chat_router尚未集成react_sse_wrapper |
| v2.52 | 2026-03-26 08:57:53 | 阶段3采用复制+删除法：复制ver1_run_stream整体逻辑，删除run_stream调用，保留SSE格式化 |
| v2.53 | 2026-03-26 10:10:55 | 附录2.8阶段1后补充：启用chat_router的步骤说明（创建chat_router_api.py新端点） |
| v2.54 | 2026-03-26 10:25:00 | 附录2.5对照检查标注：文件位置✅、核心职责✅（部分）、意图检测✅、任务✅ |
| v2.55 | 2026-03-26 10:40:00 | 附录2.8阶段1补充：chat_router统一准备环境参数方案分析 |
| v2.56 | 2026-03-26 11:05:00 | 修正环境参数分析：让FileReactAgent增加参数与chat_stream_query保持一致 |
| v2.57 | 2026-03-26 11:15:00 | 新增start函数独立设计分析：start数据传递后续、创建独立start_step()函数 |
| v2.58 | 2026-03-26 11:30:00 | 整理阶段1补充参数分析格式+start函数独立设计格式 |
| v2.59 | 2026-03-26 11:29:40 | 小健检查修正：阶段4 start函数独立设计分析有误，修正为API层工具函数而非Agent内部函数，明确start数据是API层使用不是Agent使用 |
| v2.60 | 2026-03-26 11:44:06 | 老杨批评修正：start_step()位置错误，修正为Router服务层(chatrobotsy.py)而非API层，明确Router层职责：预处理→意图检测→安全检测→start步骤→调用Agent |
| v2.61 | 2026-03-26 11:50:57 | 老杨再次批评：Router服务层包含完整5步：预处理→意图检测→安全检测→start→分发Agent，修正架构图和流程说明 |
| v2.62 | 2026-03-26 12:00:00 | 整合阶段4.5架构图到第2.1章节，更新chat_router.py为5步完整流程 |
| v2.63 | 2026-03-26 12:10:00 | 修正职责分工错误：chat2改为具体Agent(FileReactAgent/NetworkReactAgent/chat_stream_query)，删除chat2废弃计划 |
| v2.64 | 2026-03-26 12:15:00 | 全文检查修正：修正路由层架构图(start在chat_router不在react_sse_wrapper)，修正6.1职责分工表 |
| v2.65 | 2026-03-26 12:20:00 | 修正架构：chat_router.py直接作为API端点，删除chat_router_api.py两层结构 |
| v2.66 | 2026-03-26 12:25:00 | 修正4.4流程为6步：步骤1初始化(	next_step/running_tasks/ai_service)，步骤2-6对应原5步 |
| v2.67 | 2026-03-26 12:30:00 | 调整6步顺序：步骤1预处理，步骤2意图检测，步骤3初始化，步骤4安全检测，步骤5 start，步骤6分发 |
| v2.68 | 2026-03-26 12:35:00 | 修正4.5架构图：删除chat_router_api.py，改为6步流程 |
| v2.69 | 2026-03-26 12:40:00 | 4.5节改为代码改造方案，包含6步流程完整代码 |
| v2.70 | 2026-03-26 14:00:00 | 补充6.1步骤6分发示例：添加chat/query、file、network、desktop四种Agent调用示例 |
| v2.71 | 2026-03-26 14:10:00 | 补充步骤6前提取llm_client代码：从ai_service.chat包装为llm_client函数 |
| v2.72 | 2026-03-26 14:20:00 | 补充chat_stream_query需要的11个参数准备代码：task_id/running_tasks_lock/llm_call_count等 |
| v2.73 | 2026-03-26 14:30:00 | 补全步骤6调用示例：chat_stream_query传15个参数，FileReactAgent等传llm_client |
| v2.74 | 2026-03-26 14:35:00 | 更新1661-1772节分析：修正为最终方案（chat_stream_query用ai_service，Agent用llm_client） |
| v2.75 | 2026-03-26 14:45:00 | 重新梳理1661-1762节：清晰展示两种调用方式的参数准备方案 |
| v2.76 | 2026-03-26 14:50:00 | 修复阶段5代码问题：删除重复代码，补全默认回退参数 |
| v2.77 | 2026-03-26 14:55:00 | 统一使用start_step()函数：更新阶段4函数设计和阶段5调用方式 |
| v2.78 | 2026-03-26 15:00:00 | 小健检查修复：调整task_id定义顺序到步骤5之前 |
| v2.79 | 2026-03-26 15:36:57 | 阶段5步骤3拆分为3.1基础初始化+3.2 Agent参数准备，删除重复代码 |
| v2.80 | 2026-03-26 15:47:58 | 全文中5步改为6步：步骤3增加初始化+参数准备，修正所有描述（小强检查） |
| v2.81 | 2026-03-26 16:00:00 | 修正架构图为四层：路由层→React SSE包装层→意图特定React→通用ReAct，明确react_sse_wrapper是第二层（小强修正） |

---

## 一、背景说明

### 1.1 问题描述

#### 1.1.1 问题发现过程

**时间**: 2026-03-25 13:00-15:30

| 步骤 | 发现内容 | 关键人物 |
|------|---------|---------|
| ① | 北京老陈要求深度代码检查，对比v0.7.92与v0.7.90差异 | 老陈 |
| ② | 发现主干流程（chat2 → ver1_run_stream → run_stream）缺失 preprocessor 和 intent_registry | 小沈 |
| ③ | 发现支流流程（chat_non_stream → run → _run_with_session）反而有完整的预处理功能 | 小沈 |
| ④ | 老陈点醒："chat-non-stream是废弃的支流，chat2才是主干，主干反而缺功能，跑到支杆上去了" | 老陈 |
| ⑤ | 小沈写错架构方向：以为是 chat2 调用预处理 | 小沈 |
| ⑥ | 老陈纠正："预处理调用chat2，职责不能混淆，chat2只做流式输出" | 老陈 |
| ⑦ | 老陈建议：Session管理并入chat2，预处理只做预处理+意图识别 | 老陈 |
| ⑧ | 小沈重新梳理调用关系、参数传递，完善文档 | 小沈 |
| ⑨ | 小健两轮代码审查，发现遗漏细节，小沈补充完善 | 小健/小沈 |

#### 1.1.2 问题根因

**上一次 Agent 重构时**（2026-03-22~25），把预处理 + 意图识别 + Session管理全部放到了支流代码 `_run_with_session()` 方法中，而主干流程 `run_stream()`（base.py）直接用的原始版本，没有这些功能。

**结果**：
- 主干（chat2 → run_stream）：缺失预处理 ❌
- 支流（chat_non_stream → _run_with_session）：有完整预处理 ✅
- 支流是废弃代码，主干才是生产代码，**功能放反了**

### 1.2 现状对比

| 流程 | 代码路径 | preprocessor | intent_registry | Session管理 |
|------|----------|-------------|-----------------|-------------|
| **主干**（流式） | chat2 → ver1_run_stream → run_stream | ❌ 缺失 | ❌ 缺失 | ✅ 有 |
| **支流**（非流式） | chat_non_stream → run → _run_with_session | ✅ 有 | ✅ 有 | ✅ 有 |

### 1.3 Agent内部架构问题

> **📝 说明**：本节整合自参考文档 `Agent分层重构设计方案-小沈-2026-03-25.md` 第一章

#### 1.3.1 问题描述

```
BaseAgent (base.py) - 定义了一套循环逻辑
intent-file-ReactAgent (agent.py) - 完全重写了另一套循环逻辑 ← 问题！
```

- agent.py 没有继承/调用 base.py 的核心逻辑
- 测试和生产代码不一致
- 维护困难

#### 1.3.2 正确设计

```
BaseAgent (base.py) 
    ↓ 定义核心逻辑（base = 基础）
intent-file-ReactAgent (agent.py)
    ↓ 继承并调用 base 的方法
chat2.py
```

- base.py 是核心基准
- agent.py 继承 base.py，调用其方法
- 测试和生产用同样的核心逻辑

#### 1.3.3 当前问题总结

| 问题类型 | 具体问题 | 影响 |
|---------|---------|------|
| **外部流程问题** | 预处理功能放在废弃的支流代码中 | 主干流程缺失预处理功能 |
| **内部架构问题** | agent.py 重写循环逻辑，没有继承 base.py | 代码重复，维护困难 |
| **可扩展性问题** | base.py 的 run_stream 没有拆分成可扩展的子方法 | 子类无法针对特定阶段进行定制 |

---

## 二、整体架构设计

### 2.1 外部调用架构

> **📝 说明**：整合自 `多意图系统与现有代码整合架构设计-2026-03-22.md` 2.1节
>
> **核心原则**：
> - chat_router.py **独立作为路由入口**
> - 预处理模块**独立**，不在chat2内部
> - chat2.py **只负责流式loop**，不包含路由/预处理/意图识别
> - **Agent** 特指 `intent-file-ReactAgent`（agent.py），基于 ReAct 循环实现

```
前端请求
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  chat_router.py (API端点 + 6步完整流程)                          │
│                                                                 │
│  1. 预处理 (PreprocessingPipeline)                              │
│  2. 意图检测 (IntentRegistry)                                  │
│  3. 初始化 + 参数准备                                           │
│  4. 安全检测 (security_check)                                   │
│  5. start步骤 (start_step)                                     │
│  6. 分发到Agent (根据intent_type)                              │
│                                                                 │
│  输出：intent, start_data, agent_events                         │
└─────────────────────────────────────────────────────────────────┘
               │
          ┌─────┼─────┐
          │     │     │
          ▼     ▼     ▼
      intent= intent= intent=
      file   network query
           │     │     │
           ▼     ▼     ▼
       ┌─────────────┐ ┌─────────────────┐ ┌────────────┐
       │intent-file- │ │intent-network- │ │chat_       │
       │ReactAgent    │ │ReactAgent      │ │stream_     │
       │(ReAct)       │ │(ReAct)         │ │query.py    │
       │              │ │                │ │(简单对话)  │
       └─────────────┘ └─────────────────┘ └────────────┘
       
       start → thought → action → observation → final
       
      ┌──────────────┐
      │error_handler │ ← 统一的错误处理
      │.py           │
      └──────────────┘
      ┌──────────────┐
      │incident_han- │ ← 统一的中断/暂停处理
      │dler.py       │
      └──────────────┘
```

**chat_router.py (Router服务层) 6步流程**：

| 步骤 | 功能 | 说明 |
|------|------|------|
| 1 | 预处理 | PreprocessingPipeline 语句校对 |
| 2 | 意图检测 | IntentRegistry 识别意图类型 |
| 3 | 初始化 + 参数准备 | ai_service/next_step/task_id等 |
| 4 | 安全检测 | security_check 安全检查 |
| 5 | start步骤 | start_step 发送start事件 |
| 6 | 分发Agent | 根据intent_type调用不同Agent |

**流程说明**：

| 阶段 | 文件 | 说明 |
|------|------|------|
| **入口** | chat_router.py | API端点，接收请求 |
| **路由** | chat_router.py | 6步完整流程 |
| **预处理** | preprocessing/pipeline.py | 语句校对 + 意图识别 |
| **ReAct流程** | intent-*-ReactAgent (agent.py) | start → thought → action → observation → final |
| **简单对话** | chat_stream_query.py | start → chunk → final |
| **错误处理** | error_handler.py | 统一的错误响应 |
| **中断处理** | incident_handler.py | 统一的中断/暂停响应 |

**chat_router.py (API端点) 与 具体Agent的职责分工**：

| 文件 | 职责 | 不做 |
|------|------|------|
| **chat_router.py** | API端点 + 6步流程：预处理→意图检测→初始化→安全检测→start→分发Agent | 具体执行 |
| **FileReactAgent** | ReAct循环：thought→action→observation→final | 路由、预处理 |
| **NetworkReactAgent** | ReAct循环：thought→action→observation→final | 路由、预处理 |
| **chat_stream_query** | 简单对话流：chunk→final | 路由、预处理 |

> **📝 说明**：chat2.py 逐步废弃，其功能整合到 chat_router.py (API端点)

### 2.2 预处理模块职责

预处理模块（`preprocessing.py`）是**入口**，负责：

| 步骤 | 功能 | 输出 |
|------|------|------|
| 1 | preprocessor.process() | 意图类型、置信度、处理后的文本 |
| 2 | intent_registry.get() | 意图定义（name, description） |
| 3 | 返回决策数据 | intent_type + intent_def + task |

### 2.3 具体Agent职责

> **📝 说明**：chat2.py 逐步废弃，其功能整合到 chat_router.py

**具体Agent职责**：

| Agent | 职责 | 说明 |
|-------|------|------|
| **FileReactAgent** | 文件操作ReAct循环 | thought→action→observation→final |
| **NetworkReactAgent** | 网络操作ReAct循环 | thought→action→observation→final |
| **chat_stream_query** | 简单对话流 | chunk→final |

### 2.4 文件引用关系

| 模块/函数 | 引用路径 |
|-----------|---------|
| PreprocessingPipeline | `from app.services.preprocessing import PreprocessingPipeline` |
| IntentRegistry | `from app.services.intent import IntentRegistry, Intent` |
| intent-file-ReactAgent | `from app.services.agent import intent_file_ReactAgent` |
| AIServiceFactory | `from app.services import AIServiceFactory` |
| cache_display_name | `from app.utils.display_name_cache import cache_display_name` |
| check_command_safety | `from app.services.shell_security import check_command_safety` |

### 2.5 历史消息处理

| 消息类型 | 处理方式 |
|----------|---------|
| 最后一条用户消息 | 经过 preprocessor.process() 处理后传入 chat2 |
| 历史消息（messages[:-1]） | 直接传给 chat2，由 chat2 传给 chat_stream_query |

### 2.6 意图判断逻辑

预处理返回的 intent_type 可能有以下值：

| intent_type | 处理方式 |
|-------------|---------|
| file_operation | 有动作 → ReAct 循环 |
| network_operation | 有动作 → ReAct 循环 |
| chat / unknown / 其他 | 无动作 → 普通对话 |

### 2.7 函数调用关系

#### 2.7.1 preprocessing.py（预处理入口）

```python
from app.services.preprocessing import PreprocessingPipeline
from app.services.intent import IntentRegistry, Intent

# 全局实例
_preprocessor = PreprocessingPipeline()
_intent_registry = IntentRegistry()

async def execute_preprocessing(request: ChatRequest) -> dict:
    """
    预处理入口函数
    职责：预处理 → 意图识别 → 返回预处理结果
    注意：不调用chat2，由路由层决定后续调用
    """
    # 1. 预处理
    task = request.messages[-1].content
    intent_names = _intent_registry.get_all_names()
    preprocessed = _preprocessor.process(task, intent_names, session_id=None)
    
    # 2. 意图识别
    intent_type = preprocessed.get("intent", "unknown")
    intent_def = _intent_registry.get(intent_type)
    
    # 3. 历史消息（不经过预处理）
    history = request.messages[:-1]
    
    # 4. 返回预处理结果（由路由层决定后续调用）
    return {
        "corrected": preprocessed["corrected"],
        "intent_type": intent_type,
        "intent_def": intent_def,
        "history": history,
    }
```

> **📝 说明**：预处理模块只返回预处理结果，不直接调用chat2。由路由层（7.4节）负责串联调用。

#### 2.7.2 chat2.py（入口+执行）

```python
from app.services.agent import intent_file_ReactAgent  # 文件操作专用Agent
from app.services import AIServiceFactory

async def handle_stream(
    last_message: str,        # 预处理后的用户消息
    intent_type: str,         # 意图类型
    intent_def,               # 意图定义
    history: List[Message],   # 历史消息（不经过预处理）
    request: ChatRequest,     # 原始请求
):
    """
    chat2.py 入口+执行函数
    
    职责：
    1. Session 创建/管理
    2. 根据 intent_type 决定分支
    3. 流式输出具体工作
    """
    # ========== 1. 初始化（Session、AI服务、计数器） ==========
    session_id = request.session_id or create_session(...)
    ai_service = AIServiceFactory.get_service_for_model(request.provider, request.model)
    
    # 步骤计数器
    step_counter = 0
    def next_step():
        nonlocal step_counter
        step_counter += 1
        return step_counter
    
    # ========== 2. 根据 intent_type 决定分支 ==========
    if intent_type in ["file_operation", "network_operation"]:
        # 有动作 → 走 ReAct 循环
        
        # 创建 LLM 客户端适配器
        async def llm_client(message, history=None):
            response = await ai_service.chat(message, history)
            return type('obj', (object,), {'content': response.content})()
        
        # 创建 Agent 实例
        agent = FileOperationAgent(
            llm_client=llm_client,
            session_id=session_id
        )
        
        async for event in agent.ver1_run_stream(
            task=last_message,
            model=ai_service.model,
            provider=ai_service.provider,
            context={"session_id": session_id, "intent_def": intent_def},
            get_next_step=next_step,
        ):
            yield event
    else:
        # 无动作 → 走普通对话
        async for event in chat_stream_query(
            request=request,
            ai_service=ai_service,
            last_message=last_message,
            history=history,
            ...
        ):
            yield event
```

---

## 三、参数传递设计

### 3.1 预处理 → chat2

| 参数 | 说明 | 来源 |
|------|------|------|
| last_message | 预处理后的用户消息 | preprocessor.process() 返回的 corrected |
| intent_type | 意图类型 | preprocessor.process() 返回的 intent |
| intent_def | 意图定义 | intent_registry.get() 返回 |
| history | 历史消息（不含最后一条） | request.messages[:-1] |
| request | 原始请求对象 | API 传入 |

### 3.2 chat2 内部准备

| 参数 | 说明 | 准备方式 |
|------|------|---------|
| session_id | Session ID | request.session_id 或创建新 session |
| ai_service | AI 服务实例 | AIServiceFactory.get_service_for_model() |
| step_counter | 步骤计数器 | 局部变量 |
| next_step | 计数函数 | chat2 内定义的局部函数 |

### 3.3 chat2 → intent-file-ReactAgent.ver1_run_stream()

**实际参数（已核对代码）**：

```python
agent = intent_file_ReactAgent(
    llm_client=llm_client,
    session_id=session_id
)

agent.ver1_run_stream(
    task=last_message,                    # 预处理后的用户消息
    model=ai_service.model,                # 模型名称
    provider=ai_service.provider,           # Provider 名称
    context={"session_id": session_id, "intent_def": intent_def},  # 上下文（含意图定义）
    system_prompt=None,                    # 可选自定义 prompt
    max_steps=100,                         # 最大迭代次数
    get_next_step=next_step,               # step 计数函数
)
```

### 3.4 chat2 → chat_stream_query()

**实际参数（已核对代码）**：

```python
chat_stream_query(
    request=request,                       # 原始请求
    ai_service=ai_service,                  # AI 服务实例
    task_id=task_id,                       # 任务 ID
    llm_call_count=llm_call_count,         # LLM 计数器
    current_execution_steps=[],            # 执行步骤列表
    current_content="",                    # 当前累积内容
    last_is_reasoning=None,                # 上一个 reasoning 状态
    last_message=last_message,              # 预处理后的用户消息
    running_tasks=running_tasks,            # 运行任务字典
    running_tasks_lock=running_tasks_lock, # 锁
    next_step=next_step,                   # step 计数函数
    display_name=display_name,             # 显示名称
    session_id=session_id,                 # Session ID
    save_execution_steps_to_db=save_fn,   # 保存函数
    add_step_and_save=add_step_fn,         # 添加步骤函数
)
```

---

## 四、Agent分层架构设计与实现说明

> **📝 说明**：本节整合自参考文档 `Agent分层重构设计方案-小沈-2026-03-25.md`，以实际代码为参考标注实现状态。

### 4.1 设计原则

| 原则 | 说明 |
|------|------|
| **生产代码是基准** | 以 agent.py 的 run_stream 为准 |
| **base.py 向生产代码看齐** | 用正确的逻辑更新 base.py |
| **agent.py 继承 base.py** | 而不是重写 |

### 4.2 继承架构图

```
┌─────────────────────────────────────────┐
│     intent-file-ReactAgent (agent.py) (扩展层) │
│  - 继承 BaseAgent                       │
│  - 添加扩展功能:                        │
│    • session 管理                        │
│    • prompt 日志                        │
│    • preprocessor                       │
│    • intent_registry                    │
│  - 调用父类核心方法                     │
└─────────────────────────────────────────┘
                    ↓ 继承
┌─────────────────────────────────────────┐
│     BaseAgent (base.py) (核心层)       │
│  - 定义 ReAct 循环核心逻辑               │
│  - 提供抽象方法供子类实现                │
│  - 不包含任何具体实现细节                │
└─────────────────────────────────────────┘
```

### 4.3 调用关系

```
chat2.ver1_run_stream()
    ↓ 调用
agent.ver1_run_stream() ← intent-file-ReactAgent
    ↓ 调用
run_stream() ← 父类 BaseAgent
    ↓
    ├── _step_thought() ← 可扩展
    ├── _step_action() ← 可扩展  
    └── _step_observation() ← 核心逻辑在父类
            ↓
            内部调用:
            ├── _get_llm_response() ← 子类实现
            ├── _execute_tool() ← 子类实现
            └── _add_observation_to_history() ← 父类实现
```

### 4.4 BaseAgent 抽象方法定义（参考文档）

```python
class BaseAgent(ABC):
    """Agent 核心基类"""
    
    # ===== 抽象方法（子类必须实现）=====
    
    @abstractmethod
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应"""
        pass
    
    @abstractmethod
    async def _execute_tool(self, action: str, params: Dict) -> Dict:
        """执行工具"""
        pass
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """获取系统 Prompt"""
        pass
    
    @abstractmethod
    def _get_task_prompt(self, task: str, context: Optional[Dict]) -> str:
        """获取任务 Prompt"""
        pass
    
    # ===== 核心方法（子类调用）=====
    
    async def run_stream(self, task: str, context: Optional[Dict] = None, max_steps: int = 100):
        """ReAct 核心循环"""
        self._init_session(task, context)
        step_count = 0
        while step_count < max_steps:
            step_count += 1
            yield await self._step_thought()
            yield await self._step_action()
            yield await self._step_observation()
    
    # ===== 可扩展方法（子类可覆盖）=====
    
    def _init_session(self, task: str, context: Optional[Dict]):
        pass
    
    async def _step_thought(self) -> Dict:
        pass
    
    async def _step_action(self) -> Dict:
        pass
    
    async def _step_observation(self) -> Dict:
        pass
```

### 4.5 当前实现状态

**检查时间**: 2026-03-25 15:30:20  
**检查人**: 小沈

#### 4.5.1 已完成项目 ✅

| 项目 | 说明 | 代码位置 |
|------|------|---------|
| agent.py 继承 BaseAgent | 继承关系已建立 | agent.py:41 `class intent-file-ReactAgent(BaseAgent)` |
| 实现4个抽象方法 | 子类必须实现的方法 | agent.py:197/299/313/320 |
| ver1_run_stream 调用 run_stream | 调用父类核心方法 | agent.py:657 `async for event in self.run_stream(...)` |
| base.py 核心循环逻辑 | 完整的 ReAct 循环 | base.py:108-270 |
| observation 包含实际数据 | 2026-03-25 修复 | base.py:206-212 raw_data 传递给 LLM |

#### 4.5.2 未完成项目 ❌

| 序号 | 未完成项 | 当前状态 |
|------|---------|---------|
| 1 | **_step_thought 可扩展方法** | base.py 未实现拆分 |
| 2 | **_step_action 可扩展方法** | base.py 未实现拆分 |
| 3 | **_step_observation 可扩展方法** | base.py 未实现拆分 |
| 4 | **_init_session Hook** | base.py 有 _on_session_init，但不是 _init_session |
| 5 | **_on_before_loop Hook** | base.py 有调用但没有实现 |

#### 4.5.3 差距分析

**文档设计**：base.py 应该有可扩展的 `_step_thought()`、`_step_action()`、`_step_observation()` 方法，run_stream 调用这些方法，子类可以覆盖。

**实际情况**：base.py 的 run_stream 是一个完整的函数，所有逻辑都在里面，没有拆分成可扩展的子方法。

**影响**：当前架构可扩展性不足，子类无法针对特定阶段进行定制。

---

## 五、事件类型定义

### 5.1 ReAct 循环事件（intent-file-ReactAgent）

| 事件类型 | 说明 | 包含字段 |
|----------|------|---------|
| start | 会话开始 | task, session_id |
| thought | LLM 思考过程 | step, content, reasoning, action_tool, params |
| action_tool | 工具执行 | step, action_tool, params |
| observation | 执行结果 | step, result |
| final | 最终回复 | content |
| error | 错误信息 | code, message |

### 5.2 普通对话事件（chat_stream_query）

| 事件类型 | 说明 | 包含字段 |
|----------|------|---------|
| start | 会话开始 | task |
| chunk | 流式输出 | content |
| final | 完成信号 | content |

---

## 六、文件位置与职责划分

### 6.1 文件位置

| 文件 | 说明 |
|------|------|
| `backend/app/api/v1/chat2.py` | 路由层/chat2入口（含预处理调用） |
| `backend/app/services/agent/agent.py` | intent-file-ReactAgent (ver1_run_stream) |
| `backend/app/services/agent/base.py` | BaseAgent 基类（需补充可扩展方法） |
| `backend/app/services/preprocessing/pipeline.py` | PreprocessingPipeline（已存在） |
| `backend/app/services/intent/registry.py` | IntentRegistry（已存在） |
| `backend/app/chat_stream/chat_stream_query.py` | 普通对话流式输出 |

### 6.2 职责划分原则

#### 6.2.1 外部流程职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **chat_router.py** | 6步：预处理→意图检测→初始化→安全检测→start→分发Agent | 具体执行 |
| **具体Agent** | ReAct循环或简单对话流 | 路由、预处理 |

> **📝 说明**：预处理不调用chat2，由路由层负责串联调用（见2.1架构）

#### 6.2.2 Agent内部职责

| 模块 | 职责 | 不做 |
|------|------|------|
| **BaseAgent (base.py)** | 定义ReAct循环核心逻辑，提供抽象方法，定义可扩展方法 | 包含具体实现细节 |
| **intent-file-ReactAgent (agent.py)** | 继承BaseAgent，实现抽象方法，添加扩展功能（session、prompt等） | 重写循环逻辑 |

### 6.3 Session 管理

> **📝 说明**：代码中存在**两层Session管理**，职责不同：

#### 6.3.1 两层Session管理

| 层级 | 文件 | 职责 | Session ID |
|------|------|------|------------|
| **第一层** | chat2.py | task_id任务管理、中断/暂停控制 | task_id（路由参数） |
| **第二层** | session.py | 文件操作会话记录、统计 | session_id（业务参数） |

#### 6.3.2 chat2.py中的任务管理

**文件位置**：`backend/app/api/v1/chat2.py`

**数据结构**：
```python
# task_id → 任务信息
running_tasks: dict[str, dict] = {
    "task-uuid": {
        "status": "running",    # running/cancelled/paused
        "cancelled": False,
        "paused": False,
        "created_at": datetime,
        "ai_service": ai_service
    }
}

# session_id → 中断时间（防止5分钟内重连）
interrupted_sessions: dict[str, datetime] = {}
```

**Session生命周期**：
```
request.session_id 或生成新 session_id
    ↓
running_tasks[task_id] = {status: "running", ...}
    ↓
根据 intent_type 分支（有动作/无动作）
    ↓
finally: del running_tasks[task_id]
```

#### 6.3.3 FileOperationSessionService（文件操作会话）

**文件位置**：`backend/app/services/agent/session.py`

**数据库表**：`file_operation_sessions`

**状态**：`pending` / `active` / `completed` / `paused` / `failed`

**主要方法**：
- `create_session(agent_id, task_description)` → session_id
- `complete_session(session_id, success)`
- `get_session(session_id)` → SessionRecord

> **⚠️ 注意**：两层Session的ID可能不同：
> - chat2用的是task_id（路由级别）
> - session.py用的是session_id（业务级别）
> - 需要在Agent内部统一为session_id

#### 6.3.4 与报告设计方案的逻辑关系

> **📝 说明**：本节描述架构现状，报告设计方案（`LLM-文件操作历史过程报告设计方案V2版-小沈-20260325.md`）是基于本节架构的**具体实现方案**。

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    6.3 Session管理（架构层）                              │
│                                                                         │
│  chat2.py                           session.py                          │
│  ┌─────────────────┐               ┌─────────────────┐                  │
│  │ task_id 任务管理 │               │ file_operation  │                  │
│  │ + session_id    │               │ _sessions 表    │                  │
│  └────────┬────────┘               └────────┬────────┘                  │
│           │                                 │                            │
│           │ 统一使用 request.session_id      │                            │
│           └───────────────┬─────────────────┘                            │
│                           ↓                                              │
│                  file_operations 表                                       │
│                  (session_id 关联操作记录)                                │
└─────────────────────────────────────────────────────────────────────────┘
                           │
                           ↓ 具体实现
┌─────────────────────────────────────────────────────────────────────────┐
│           报告设计方案（实现层）- 已实现 ✅                                │
│                                                                         │
│  chat2.py:456                                                           │
│  session_id = request.session_id or str(uuid.uuid4())  ← 统一session_id  │
│                           ↓                                              │
│  file_operations.session_id = request.session_id  ← 可被报告生成找到     │
│                           ↓                                              │
│  generate_report API (带 task_description 参数)  ← 报告正确生成        │
└─────────────────────────────────────────────────────────────────────────┘
```

**逻辑关系**：
1. **6.3 Session管理** = 描述架构现状（有哪些Session、职责是什么）
2. **报告设计方案** = 基于架构的具体实现方案（解决Session ID不统一导致报告找不到数据的问题）
3. **关系**：报告设计方案是6.3架构的**落地实现**

---

## 七、待实现清单

### 7.1 本次代码重组原则

> **📝 说明**：本次代码重组的核心指导思想，所有待实现任务都应遵循以下原则。

| 序号 | 原则 | 说明 |
|------|------|------|
| 1 | **基础版本** | 改造的代码基础版本是 **v0.7.92** |
| 2 | **重构范围** | 本次重构的是系统**主流程**的不合理和错乱的部分代码 |
| 3 | **实现目标** | 通过部分代码的重构，和部分函数/代码文件的逻辑关系重组，实现**合理的OMNI系统运行逻辑**（流程图参考 2.1 节） |
| 4 | **改造对象** | 改造的函数、代码文件的**错乱功能** |
| 5 | **关联调用** | 重组把已经实现的功能正确的函数和代码，按照OMNI系统的流程进行**正确的关联和调用** |
| 6 | **复用原则** | 重组的代码要**尽可能使用基础版本已有功能**，可以将已有功能**函数化/文件化**，被引用 |
| 7 | **核心原则** | 引用基础版本的**各个小功能模块**的代码和功能，**不能丢失/破坏**已有的功能和小逻辑 |

#### 7.1.1 核心教训（本次梳理的目的）

> **⚠️ 教训来源**：上次 Agent 重构时，preprocessor、intent_registry、Session管理等单元功能都实现了，单元测试通过，但整合到主流程时失败——功能放到了废弃的支流代码中，主干流程反而没有这些功能。

**核心问题**：
- 单元重构完成 ≠ 重构目的达到
- 功能实现 ≠ 功能被主流程调用
- 单元测试通过 ≠ 主流程能工作

**本次梳理的目的**：
- 不是重新实现功能
- 而是**正确地把已有功能整合到主流程**
- 确保：preprocessor、intent_registry 等 → 被 chat2.py 主流程调用

**每次修改必须思考**：
```
这个修改能不能整合到主流程？
如果不能，怎么改才能整合？
```

---

#### 7.1.2 关于基础版本 v0.7.92
- 所有改造以 v0.7.92 为基准
- 不能脱离这个版本进行"全新设计"
- 只能在原有基础上进行调整和优化

**关于主流程重构**：
- 问题：预处理功能在废弃的支流代码中，主干流程缺失
- 目标：让主干流程具备完整的预处理功能
- 方法：参考 2.1 节的流程图，将预处理功能正确关联到主流程

**关于复用已有功能**：
- v0.7.92 中已有许多小功能模块（preprocessor, intent_registry, session管理等）
- 本次重组不是重新发明轮子
- 而是**正确地调用**这些已有模块

**关于不破坏已有功能**：
- 重组时不能影响那些已经正常工作的功能
- 只能修复错乱的部分
- 保持其他功能不受影响

### 7.2 预处理模块（独立入口）

> **📝 说明**：根据2.1架构要求，预处理是**独立模块**，在路由层调用，不是放在chat2内部
> 
> **详细实现**：见附录 **阶段5：Router的更新**（第1943行起）

**2.1架构要求**（必须遵守）：
```
用户请求
    ↓
chat_router.py (API端点) - 6步完整流程
    1. 预处理 (PreprocessingPipeline)
    2. 意图检测 (IntentRegistry)
    3. 初始化 + 参数准备
    4. 安全检测 (security_check)
    5. start步骤 (start_step)
    6. 分发到Agent
    ↓
Agent (FileReactAgent / chat_stream_query)
```

**关键约束**：
- **禁止在chat2内部调用预处理**（违反2.1架构）
- chat_router.py 包含完整6步流程
- chat2只接收Agent执行结果

### 7.3 chat2.py 废弃计划

> **📝 说明**：chat2.py 逐步废弃，其功能整合到 chat_router.py 的6步流程中

**chat2废弃原因**：
- 混合了路由和流式loop职责
- 包含预处理调用（违反2.1架构）
- 职责不清

**遗留问题修复**（来自 `2.预处理与多意图代码目录说明-小沈-2026-03-22.md` 7.7节）：
> **问题**：agent.py:452 使用原始 `task` 而不是 `preprocessed['corrected']`
> 
> **应改为**：
> ```python
> task_prompt = self.prompts.get_task_prompt(preprocessed['corrected'], context)  # 用修正后的 ✅
> ```

### 7.4 路由改造（创建 chat_router.py）

> **📝 设计依据**：`多意图系统与现有代码整合架构设计-2026-03-22.md` 3.1节
> 
> **核心原则**：chat2 **不能作为路由层**，chat2只负责流式loop

**问题**：当前 chat2.py 混合了路由和流式loop职责，职责不清

**目标**：创建独立的 chat_router.py 作为路由入口

**chat_router.py (API端点) 职责**（6步完整流程）：
```
chat_router.py（API端点）
    1. 预处理 (PreprocessingPipeline)
    2. 意图检测 (IntentRegistry)
    3. 初始化 + 参数准备
    4. 安全检测 (security_check)
    5. start步骤 (start_step)
    6. 分发到Agent (根据intent_type)
```

**架构**（参考整合架构设计2.1节）：
```
chat_router.py（API端点）
    ├── intent=file → FileReactAgent (file_react.py) - ReAct流式loop
    ├── intent=network → NetworkReactAgent (network_react.py) - ReAct流式loop
    └── intent=query → chat_stream_query.py (简单对话流式)
```

**过渡策略**：旧代码逐步取代，不能完全删除
- 当前：api/chat2.py → agent.py → base.py
- 目标：chat_router.py → react_sse_wrapper.py → FileReactAgent (file_react.py) → base_react.py
- 方式：直接修改 chat_router.py 作为新入口，验证通过后逐步替换旧调用链
- chat2.py 暂时保留，待新架构稳定后再废弃

> **📝 详细代码实现**：见附录 **阶段5：Router的更新**（第1943行起）

---

### 7.5 Agent分层重构

> **📝 说明**：基于4.5.2的未完成项，补充base.py的可扩展方法。

**4.5.1已完成** ✅：继承关系、调用run_stream、核心循环逻辑

**4.5.2待实现** ❌：可扩展方法拆分

**Agent命名规范**（必须遵守）：
> **⚠️ 命名原则**：IntentReactAgent 是**文件操作专用**的Agent，应统一命名为 `intent-file-ReactAgent`
>
> | 当前命名 | 应改为 | 说明 |
> |---------|--------|------|
> | IntentReactAgent | intent-file-ReactAgent | 文件操作专用 |
> | IntentReactAgent (network) | intent-network-ReactAgent | 网络操作专用（未来） |
>
> **原因**：避免与 BaseAgent 混淆，明确每个Agent的职责范围

**改造要点**：
- [ ] 将 `IntentReactAgent` 重命名为 `intent-file-ReactAgent`
- [ ] base.py 拆分 `_step_thought()` 可扩展方法
- [ ] base.py 拆分 `_step_action()` 可扩展方法
- [ ] base.py 拆分 `_step_observation()` 可扩展方法
- [ ] base.py 实现 `_init_session()` Hook（替代 `_on_session_init`）
- [ ] base.py 实现 `_on_before_loop()` Hook
- [ ] 验证（生产功能正常 + 测试通过）

---

## 八、关键实现细节（代码示例）

### 8.1 next_step 函数定义

```python
# 必须在使用前定义
step_counter = 0

def next_step():
    nonlocal step_counter
    step_counter += 1
    return step_counter
```

### 8.2 LLM 客户端适配器

```python
async def llm_client(message, history=None):
    response = await ai_service.chat(message, history)
    return type('obj', (object,), {'content': response.content})()
```

### 8.3 Agent 实例创建

```python
agent = FileOperationAgent(
    llm_client=llm_client,
    session_id=session_id
)
```

---

## 附录2：ReAct架构层次说明

> **📝 说明**：整理ReAct架构的层次关系，明确各层职责
>
> **更新时间**: 2026-03-25 21:18:40
> **更新人**: 小沈

### 附录2.1 架构层次总览

```
┌─────────────────────────────────────────────────────────────────┐
│  第一层：路由层 (chat_router.py) - 6步完整流程                    │
│                                                                 │
│  1. 预处理 (PreprocessingPipeline)                             │
│  2. 意图检测 (IntentRegistry)                                  │
│  3. 初始化 + 参数准备                                           │
│  4. 安全检测 (security_check)                                  │
│  5. start步骤 (start_step)                                     │
│  6. 分发到Agent (根据intent_type)                               │
│                                                                 │
│  ✅ 路由入口，统一入口处理                                        │
└─────────────────────────────────────────────────────────────────┘
                            ↑
                            │ 调用
┌─────────────────────────────────────────────────────────────────┐
│  第二层：React SSE 包装层 (react_sse_wrapper.py)                 │
│                                                                 │
│  - SSE 框架搭建                                                 │
│  - 任务管理 (running_tasks)                                     │
│  - start 步骤发送                                               │
│  - 数据库保存 (save_execution_steps_to_db)                     │
│  - SSE 格式化转换 (dict → SSE 字符串)                           │
│  - 中断/暂停检查                                                 │
│                                                                 │
│  ✅ 流式输出包装，与具体意图无关                                  │
└─────────────────────────────────────────────────────────────────┘
                            ↑
                            │ 调用
┌─────────────────────────────────────────────────────────────────┐
│  第三层：意图特定React层 (file_react.py / network_react.py)      │
│                                                                 │
│  - 继承 BaseReActAgent                                          │
│  - 调用 self.run_stream()（返回 event dict）                    │
│  - 意图特定逻辑（工具/prompt/LLM策略）                          │
│                                                                 │
│  ✅ 与具体意图相关（file/network/desktop）                       │
└─────────────────────────────────────────────────────────────────┘
                            ↑
                            │ 调用
┌─────────────────────────────────────────────────────────────────┐
│  第四层：通用ReAct层 (base_react.py)                            │
│                                                                 │
│  实现标准的 ReAct 循环：                                        │
│     Thought → Action → Observation → (循环直到 finish)          │
│                                                                 │
│  返回通用 dict 事件：                                           │
│     {"type": "thought", "content": ...}                        │
│     {"type": "action_tool", "tool_name": ...}                   │
│     {"type": "observation", "obs_summary": ...}                 │
│                                                                 │
│  ✅ 与意图无关，是通用的                                         │
└─────────────────────────────────────────────────────────────────┘
```

### 附录2.2 各层职责说明

| 层次 | 文件 | 职责 | 特点 |
|------|------|------|------|
| **路由层** | chat_router.py | 6步完整流程：预处理→意图检测→初始化→安全检测→start→分发Agent | 路由入口 |
| **React SSE 包装层** | react_sse_wrapper.py | SSE流式输出+任务管理+数据库保存+中断暂停检查 | 流式输出包装 |
| **意图特定React** | file_react.py / network_react.py | run_stream返回event dict + 意图相关逻辑 | 与具体意图相关 |
| **通用ReAct** | base_react.py | 标准ReAct循环 | 与意图无关，通用 |

### 附录2.3 四层架构与意图分发

> **整理时间**: 2026-03-25 21:50:00
> **整理人**: 小沈
>
> **更新时间**: 2026-03-26
> **更新说明**: 补充第二层React SSE包装层，明确调用关系

#### 附录2.3.1 四层架构

```
┌─────────────────────────────────────────────────────────────────┐
│  第一层：路由层 (chat_router.py) - 6步完整流程                    │
│                                                                 │
│  1. 预处理 (PreprocessingPipeline)                             │
│  2. 意图检测 (IntentRegistry)                                  │
│  3. 初始化 + 参数准备                                           │
│  4. 安全检测 (security_check)                                  │
│  5. start步骤 (start_step)                                     │
│  6. 分发到Agent (根据intent_type)                               │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  第二层：React SSE 包装层 (react_sse_wrapper.py)                 │
│                                                                 │
│  - SSE 框架搭建                                                 │
│  - 任务管理 (running_tasks)                                     │
│  - start 步骤发送                                               │
│  - 数据库保存 (save_execution_steps_to_db)                     │
│  - SSE 格式化转换 (dict → SSE 字符串)                           │
│  - 中断/暂停检查                                                 │
│                                                                 │
│  ✅ 流式输出包装，与具体意图无关                                  │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  第三层：意图特定React层                                         │
│                                                                 │
│  ├── FileReactAgent (file_react.py)                            │
│  │   ├── 文件操作工具 (FileTools)                               │
│  │   ├── Prompt 模板 (FileOperationPrompts)                    │
│  │   └── run_stream() → 返回 event dict                        │
│  │                                                             │
│  ├── NetworkReactAgent (network_react.py) ← 待实现             │
│  │                                                             │
│  └── DesktopReactAgent (desktop_react.py) ← 待实现            │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  第四层：通用ReAct层 (base_react.py)                            │
│                                                                 │
│  实现标准的 ReAct 循环：                                        │
│     Thought → Action → Observation → (循环直到 finish)          │
│                                                                 │
│  返回通用 dict 事件：                                           │
│     {"type": "thought", "content": ...}                        │
│     {"type": "action_tool", "tool_name": ...}                   │
│     {"type": "observation", "obs_summary": ...}                 │
│                                                                 │
│  ✅ 与意图无关，是通用的                                         │
└─────────────────────────────────────────────────────────────────┘
```

#### 附录2.3.2 调用链说明

```
chat_router → react_sse_wrapper.generate_sse_stream() → file_react.run_stream() → base_react.run_stream()
     ↓                      ↓                              ↓                        ↓
   第一层                第二层                        第三层                    第四层
```

#### 附录2.3.3 改造前后对应关系

| 改造前 | 改造后 | 状态 |
|--------|---------|------|
| agent.py | file_react.py (FileReactAgent) | ✅ 已完成 |
| agent.py (intent_type=network) | network_react.py (NetworkReactAgent) | 待实现 |
| agent.py (intent_type=desktop) | desktop_react.py (DesktopReactAgent) | 待实现 |
| chat2.py | react_sse_wrapper.py | ✅ 已完成 |
| 无 | chat_router.py | ✅ 已完成 |

#### 附录2.3.4 各层职责总结

| 层 | 文件 | 职责 | 特点 |
|---|------|------|------|
| **路由层** | chat_router.py | 6步完整流程：预处理→意图检测→初始化→安全检测→start→分发Agent | 新增 |
| **React SSE 包装层** | react_sse_wrapper.py | SSE流式输出+任务管理+数据库保存+中断暂停检查 | 从chat2.py抽取 |
| **意图特定React** | file_react.py / network_react.py / desktop_react.py | 意图相关逻辑（工具/prompt/LLM策略/run_stream） | 拆分自 agent.py |
| **通用ReAct** | base_react.py | 标准 ReAct 循环 | 与意图无关 |

#### 附录2.3.5 关键理解

1. **agent.py = FileReactAgent 的前身**
   - 当前 agent.py 有 intent_type 参数，但只完整实现了 file
   - file_react.py 拆分自 agent.py

2. **react_sse_wrapper 是 SSE 包装层**
   - 从 chat2.py 抽取的 SSE 框架代码
   - 负责将 event dict 转换为 SSE 字符串
   - 管理 running_tasks、数据库保存、中断/暂停

3. **意图特定 React 层调用 base_react.py**
   - FileReactAgent.run_stream() 返回 event dict
   - 由 react_sse_wrapper 转换为 SSE 字符串

4. **不再需要现有的 agent.py 作为独立文件**
   - 其逻辑拆分到 file_react.py / network_react.py / desktop_react.py
   - SSE 包装整合到 react_sse_wrapper.py
   - chat_router 负责路由分发

### 附录2.4 base.py更名base_react.py规范

> **整理时间**: 2026-03-25 22:20:00
> **整理人**: 小沈
>
> **更新时间**: 2026-03-25 22:25:00
> **更新说明**: 已完成改名，文件位置和实际命名为 base_react.py

#### 附录2.4.1 底层ReAct文件命名

| 原文件名 | 新文件名 | 文件位置 | 说明 |
|---------|---------|---------|------|
| base.py | **base_react.py** | `backend/app/services/agent/base_react.py` | 明确表示"底层ReAct"职责 |

**改名理由**：
- `base.py` 含义模糊
- `base_react.py` 明确表达是"底层ReAct循环"
- 与四层架构名称对齐

**注意**：Python模块名必须使用下划线，不能用连字符

#### 附录2.4.2 改名后同步更新 ✅ 已完成

| 文件 | 更新内容 |
|------|---------|
| `backend/app/services/agent/base_react.py` | 重命名文件 |
| `backend/app/services/agent/agent.py` | 更新导入：`from app.services.agent.base_react import BaseAgent` |
| `backend/app/services/agent/__init__.py` | 更新导入 |
| `backend/tests/test_agent.py` | 更新导入 |
| `backend/tests/test_multi_intent_architecture.py` | 更新导入 |

#### 附录2.4.3 改名影响范围

```
引用 base.py 的文件：
├── agent.py
├── test_agent.py
└── test_multi_intent_architecture.py

影响：较小，只需更新导入语句
```

---

### 附录2.5 路由层 - chat_router.py

> **整理时间**: 2026-03-25 22:36:38
> **整理人**: 小沈
>
> **对应架构层**: 第一层：路由层

#### 附录2.5.1 文件位置 ✅

| 项目 | 说明 | 状态 |
|------|------|------|
| 文件路径 | `backend/app/services/chat_router.py` | ✅ 已实现 |
| 目录选择 | `app/services/` 而非 `app/api/v1/` | ✅ 符合 |

**理由**：API层应保持轻薄，业务路由逻辑放在服务层

#### 附录2.5.2 核心职责 ✅（部分）

| 设计要求 | 实际代码位置 | 状态 |
|---------|-------------|------|
| 接收用户消息 | 第44行 user_input 参数 | ✅ |
| 调用 PreprocessingPipeline 进行意图检测 | 第72行 `self.preprocessing.process()` | ✅ |
| 返回 intent_type 和参数 | 第78-79行 | ✅ |
| 分发到 file → FileReactAgent | 第87-100行 `_handle_file_operation()` | ✅ |
| 分发到 chat → chat_stream_query() | 第101-110行 | ⚠️ 暂返回提示信息 |
| 分发到 network → NetworkReactAgent | 第111-117行 | ❌ 返回"暂不支持"错误 |
| 分发到 desktop → DesktopReactAgent | 第111-117行 | ❌ 返回"暂不支持"错误 |
| 返回统一的 SSE 流 | yield sse_data | ✅ |

#### 附录2.5.3 意图检测方式 ✅

| 候选方式 | 结论 | 理由 |
|---------|------|------|
| `detect_file_operation_intent()` | ❌ 废除 | 简陋的字符串匹配 |
| `PreprocessingPipeline` | ✅ 必须使用 | 完整的预处理流程 |

**实际实现**：第25行导入 `PreprocessingPipeline`，第72行调用 `self.preprocessing.process()`

#### 附录2.5.4 待实现任务 ✅

| 序号 | 任务 | 状态 |
|------|------|------|
| 1 | 创建 `chat_router.py` | ✅ 已完成 |
| 2 | 调用 `PreprocessingPipeline` | ✅ 已完成 |
| 3 | 实现意图分发逻辑 | ✅ 已完成（file已实现，其他待后续） |

#### 附录2.5.5 实施记录

> **更新时间**: 2026-03-26 07:58:00
> **实施人**: 小沈

**阶段1实施完成**（2026-03-26）：
- ✅ 创建 `backend/app/services/chat_router.py`
- ✅ 实现 `ChatRouter` 类
- ✅ 调用 `PreprocessingPipeline.process()` 进行意图检测
- ✅ 实现意图分发：file → FileReactAgent.ver1_run_stream()
- ✅ 语法检查通过
- ✅ 32个测试全部通过

**实现细节**：
- 文件位置：`app/services/chat_router.py`（符合附录2.5.1）
- 意图检测：使用 `PreprocessingPipeline`（符合附录2.5.3）
- 分发逻辑：file 意图调用 FileReactAgent，其他意图返回错误

**待后续阶段处理**：
- chat 意图 → chat_stream_query()（阶段2/3）
- network 意图 → NetworkReactAgent（阶段2/3）
- desktop 意图 → DesktopReactAgent（阶段2/3）

> **TODO**：
> - chat_stream_query 已实现（`backend/app/chat_stream/chat_stream_query.py`），需传递 request、ai_service、running_tasks 等参数才能调用，第一阶段先返回提示信息，后续阶段实现真正调用

---

### 附录2.6 意图特定层 - file_react.py

> **整理时间**: 2026-03-25 22:36:38
> **整理人**: 小沈
>
> **对应架构层**: 第三层：意图特定 React

#### 附录2.6.1 文件命名

| 项目 | 说明 |
|------|------|
| 文件名 | `file_react.py` |
| 类名 | `FileReactAgent` |
| 位置 | `backend/app/services/agent/file_react.py` |

**命名理由**：
- 文件名 `file_react.py` 与 `base_react.py` 风格一致
- 类名 `FileReactAgent` 简洁明了

#### 附录2.6.2 改造思路

**复制 + 删除法**（2026-03-26 小沈优化）

**方法选择理由**：
| 方法 | 优点 | 缺点 |
|------|------|------|
| 抽取法 | 代码干净，无冗余 | 容易漏依赖，复杂易错 |
| **复制+删除法** | 保留完整依赖，简单可靠 | 可能有些冗余代码 |

**采用复制+删除法**：
- agent.py 只有 719 行，复制一份不大
- 只需要删除几处代码，依赖完整保留
- 简单可靠，不易出错

**具体步骤**：
```
1. cp agent.py file_react.py
2. 删除 intent-type 分支（第121-134行）
3. 重命名类 IntentReactAgent → FileReactAgent
4. 清理 docstring
5. 编译验证
```

**要删除的代码**：
| 删除项 | 代码位置 | 说明 |
|--------|---------|------|
| intent-type 分支 | 第121-134行 | desktop/network 分支，file_react.py 不需要 |
| 类名 | 第41行 | IntentReactAgent → FileReactAgent |
| docstring | 第2-16行 | 更新为文件专用描述 |

#### 附录2.6.3 从 agent.py 抽取的内容（完整清单）

| 抽取项 | 代码位置 | 说明 | 抽取目标 |
|--------|---------|------|----------|
| FileTools 初始化 | 第104行 | 文件操作工具 | file_react.py |
| ToolExecutor 初始化 | 第107-116行 | 工具执行器 | file_react.py |
| FileOperationPrompts | 第118行 | Prompt 模板 | file_react.py |
| IntentRegistry + _register_default_intents | 第138-191行 | 意图注册表 | file_react.py |
| LLM 调用策略 | 第145-161行 | TextStrategy/ToolsStrategy/LLMAdapter | file_react.py |
| ver1_run_stream | 第622-716行 | SSE 流式执行 | file_react.py |
| run / _run_with_session | 第371-559行 | 非流式执行 + Session 管理 | file_react.py |
| rollback | 第573-620行 | 回滚操作 | file_react.py |
| intent-type 分支（network/desktop） | 第121-134行 | 预留意图 | network_react.py / desktop_react.py |

**说明**：agent.py 中的 `ver1_run_stream()` 已经封装了完整的 ReAct 循环 + SSE 转换，被 chat2.py 调用。抽取时保留此函数。

#### 附录2.6.4 依赖的辅助模块

**ver1_run_stream() 依赖以下模块**（已存在，无需移动）：

| 依赖模块 | 说明 | 位置 |
|---------|------|------|
| `sse_formatter.py` | SSE 事件格式化 | `app/chat_stream/sse_formatter.py` |
| `chat_helpers.py` | final 响应和 timestamp | `app/chat_stream/chat_helpers.py` |
| `error_handler.py` | 错误响应 | `app/chat_stream/error_handler.py` |

#### 附录2.6.5 实施记录

| 序号 | 任务 | 状态 | 时间 | commit |
|------|------|------|------|--------|
| 1 | 复制 agent.py → file_react.py | ✅ 完成 | 2026-03-26 | e15abcbe |
| 2 | 删除 intent-type 分支 | ✅ 完成 | 2026-03-26 | e15abcbe |
| 3 | 重命名类 IntentReactAgent → FileReactAgent | ✅ 完成 | 2026-03-26 | e15abcbe |
| 4 | 清理 docstring | ✅ 完成 | 2026-03-26 | e15abcbe |
| 5 | 编译验证 | ✅ 完成 | 2026-03-26 | - |
| 6 | 单元测试 | ✅ 32个全部通过 | 2026-03-26 | - |
| 7 | 废弃 `agent.py` | 待废弃 | - | - |

> **TODO 待清理（小健检查发现 - 2026-03-26）**：
> - `intent_registry` 和 `preprocessor` 对象仍保留在代码中（第121-125行）
> - `run_stream` 方法中仍有意图识别调用（第389-404行）
> - FileReactAgent 是专用 Agent，这些逻辑应该在路由层（chat_router.py）处理
> - 后续应删除这些冗余代码

---

### 附录2.7 React SSE 包装层 - react_sse_wrapper.py

> **整理时间**: 2026-03-25 23:10:00
> **整理人**: 小沈
>
> **更新时间**: 2026-03-26
> **更新说明**: 确认第二层react_sse_wrapper.py价值，作为SSE流式输出包装层
>
> **对应架构层**: 第二层：从 chat2.py 抽取流式 SSE 包装函数

#### 附录2.7.1 文件命名

| 项目 | 说明 |
|------|------|
| 文件名 | `react_sse_wrapper.py` |
| 类名 | `SSEReactWrapper` |
| 位置 | `backend/app/services/react_sse_wrapper.py` |

**React_sse_wrapper 结构**（第二层）：
```
react_sse_wrapper (第二层)
├── running_tasks 管理 ← 从 chat2.py 抽
├── DB 保存 save_execution_steps_to_db ← 从 chat2.py 抽
├── SSE 转换 ← 从 file_react.py.ver1_run_stream 抽
└── 调用 Agent.run_stream() ← 只做 ReAct 循环
```

**来源**：从 chat2.py 抽取有价值内容后废弃

#### 附录2.7.2 职责

| 职责 | 说明 |
|------|------|
| SSE 框架搭建 | chat_stream() 是 SSE 框架 |
| 任务管理 | running_tasks / interrupted_sessions 注册和管理 |
| start 步骤发送 | 包含 security_check |
| 数据库保存 | save_execution_steps_to_db |
| **SSE 转换** | 从 file_react.py.ver1_run_stream 抽取的 SSE 格式化逻辑 |
| API 端点 | cancel/pause/resume 三个接口 |
| 中断/暂停检查 | check_and_yield_if_interrupted/paused |

#### 附录2.7.3 抽取内容

**从 chat2.py 抽取**：

| 抽取项 | 代码位置 | 说明 |
|--------|---------|------|
| running_tasks / interrupted_sessions / 超时常量 | 第246-255行 | 任务状态管理 |
| cleanup_expired_tasks() | 第257-268行 | 清理过期任务 |
| start 步骤发送（含 security_check） | 第362-382行 | 初始化步骤 |
| 数据库保存 (save_execution_steps_to_db) | 第385-386行 | 持久化 |
| 中断/暂停检查 | 第441-448行 | 状态检查 |
| cancel_stream_task() API | 第604-641行 | 取消任务 |
| pause_stream_task() API | 第647-666行 | 暂停任务 |
| resume_stream_task() API | 第669-688行 | 恢复任务 |

**从 file_react.py.ver1_run_stream 抽取**：

| 抽取项 | 说明 |
|--------|------|
| SSE 格式化逻辑 | format_thought_sse, format_action_tool_sse, format_observation_sse 等调用 |
| 事件转换 | 将 BaseAgent.run_stream() 的 event dict 转为 SSE 字符串 |

#### 附录2.7.4 待实现任务

> **📝 说明**：以下任务为对照检查项，实际操作过程详见 2.7.5 实施方法。

| 序号 | 任务 | 状态 |
|------|------|------|
| 1 | 抽取任务管理状态（running_tasks / interrupted_sessions） | ✅ 已完成 |
| 2 | 封装 start 步骤发送（含 security_check） | ✅ 已完成 |
| 3 | 封装数据库保存逻辑 | ✅ 已完成 |
| 4 | 封装 SSE 转换逻辑（从 ver1_run_stream 抽取） | ✅ 已完成 |
| 5 | 封装中断/暂停检查 | ✅ 已完成 |
| 6 | 实现 cancel/pause/resume API 端点 | ✅ 已完成（转为服务层函数） |
| 7 | 改造 FileReactAgent：删除 ver1_run_stream，保留 run_stream | 待实现 |
| 8 | 验证调用链完整 | 待验证 |

#### 附录2.7.5 实施方法（复制+删除法）

**采用与 file_react.py 相同的"复制+删除法"**：
- 复制 `chat2.py` → `react_sse_wrapper.py`
- 删除不应该在第三层的内容
- 保留通用职责

**chat2.py 当前结构**：
```
chat2.py (688行)
├── 路由判断（if is_file_op）❌ → 应该在 chat_router.py
├── 意图检测 ❌ → 应该在 chat_router.py
├── 任务管理 running_tasks ✅ → 保留
├── start 步骤发送（含 security_check）✅ → 保留
├── 数据库保存 ✅ → 保留
├── 中断/暂停检查 ✅ → 保留
├── 调用 agent.run_stream() → 返回 event dict
└── SSE 转换 → 自己实现（从 file_react.py.ver1_run_stream 抽取的 SSE 格式化逻辑）
```

**具体步骤**：
```
1. cp chat2.py react_sse_wrapper.py
2. 删除路由判断（if is_file_op）
3. 删除意图检测代码
4. 添加 SSE 转换逻辑（从 file_react.py.ver1_run_stream 抽取）
5. 修改调用：agent.ver1_run_stream() → agent.run_stream()
6. 重命名类：Chat2 → SSEReactWrapper
7. 清理 docstring
8. 编译验证
```

**file_react.py 同步改造**：
- 删除 ver1_run_stream 方法（SSE 转换逻辑已被抽走）
- 保留 run_stream 方法（返回 event dict，供 react_sse_wrapper 调用）

**react_sse_wrapper 调用 file_react.run_stream() 参数说明**：
```python
# react_sse_wrapper 调用 file_react
agent = FileReactAgent(llm_client=..., session_id=...)
async for event in agent.run_stream(
    task=task,          # 用户输入
    model=model,        # 模型名称
    provider=provider,   # 模型提供商
    ...
):
    # event 是 dict，转为 SSE 字符串
    yield format_sse(event)
```

**要删除的代码**：
| 删除项 | 代码位置 | 说明 |
|--------|---------|------|
| 路由判断 | 第300-330行 | is_file_op 判断，应在 chat_router.py |
| 意图检测 | 第350-360行 | 应在 chat_router.py |
| detect_file_operation_intent 调用 | - | 废除 |

**要修改的代码**：
| 修改项 | 说明 |
|--------|------|
| agent.ver1_run_stream() | 改为 agent.run_stream() |
| 类名 | Chat2 → SSEReactWrapper |

### 附录2.8 分阶段实施方案（推荐）

> **更新时间**: 2026-03-26 06:20:00
> **更新说明**: 新增分阶段实施方案，降低重构风险

```
阶段1：chat_router → FileReactAgent.ver1_run_stream()（直接调用）【参考附录2.5章节操作说明】
       ├── 实现 chat_router.py（第一层）
       └── 直接调用 file_react.ver1_run_stream()（现有方法）
       验证：路由 + 文件操作正常工作

**阶段1完成后：启用 chat_router**（2026-03-26 10:10:55 小沈补充，已修正）

> **修正说明**：chat_router.py 直接作为 API 端点，不需要单独的 chat_router_api.py

**启用步骤**：
1. 修改 `app/services/chat_router.py` 添加 FastAPI 路由装饰器
2. 在 `app/main.py` 中注册 chat_router
3. 验证新端点正常工作后，逐步迁移流量

**chat_router.py 作为API端点代码示例**：
```python
# app/services/chat_router.py
from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/chat/stream/v2")
async def chat_stream_v2(request: Request):
    """新版本流式API，使用 chat_router 进行意图路由"""
    # 从 request 中获取参数
    body = await request.json()
    user_input = body.get("messages", [{}])[-1].get("content", "")
    session_id = body.get("session_id")
    model = body.get("model")
    provider = body.get("provider")
    
    chat_router = ChatRouter()
    
    async def llm_client(message, history=None):
        # 实现 LLM 调用
        ...
    
    async def generate():
        async for sse_data in chat_router.route(
            user_input=user_input,
            model=model,
            provider=provider,
            llm_client=llm_client,
            session_id=session_id
        ):
            yield sse_data
    
    return StreamingResponse(generate(), media_type="text/event-stream")
```

**新端点与旧端点并行**：
- 旧端点：`/chat/stream` → chat2.py（待废除）
- 新端点：`/chat/stream/v2` → chat_router（阶段1启用）

**验证通过后**：将前端请求切换到新端点，旧端点废弃

**阶段1补充：chat_router 调用 Agent 的参数准备方案**（2026-03-26 10:40:00 小沈）

> 💡 **核心问题**：chat_router 需要调用两种不同的处理函数，需要分别准备不同的参数

---

#### 背景

chat_router 在步骤6需要根据 intent_type 分发到不同的处理函数：

| intent_type | 调用的函数 | LLM调用方式 |
|-------------|-----------|-------------|
| chat / confidence < 0.3 | chat_stream_query | 使用 `ai_service` |
| file / network / desktop | FileReactAgent 等 | 使用 `llm_client` |

---

#### 参数准备方案

##### 方案一：chat_stream_query 需要的参数（15个）

```python
async for event in chat_stream_query(
    request=request,                      # 获取history
    ai_service=ai_service,                # AI服务（使用 ai_service.chat_stream）
    task_id=task_id,                      # 任务ID（中断检查）
    llm_call_count=0,                     # LLM调用计数器
    current_execution_steps=[],            # 执行步骤列表
    current_content="",                    # 当前累积内容
    last_is_reasoning=None,                # 上一个is_reasoning状态
    last_message=user_input,               # 用户消息
    running_tasks={},                      # 运行中的任务
    running_tasks_lock=asyncio.Lock(),     # 任务锁
    next_step=next_step,                   # 获取步骤号函数
    display_name=display_name,             # 显示名称
    session_id=session_id,                # 会话ID
    save_execution_steps_to_db=wrapped_save_steps,   # 保存到DB函数
    add_step_and_save=wrapped_add_step     # 添加步骤并保存函数
):
```

##### 方案二：FileReactAgent 需要的参数（4个）

```python
agent = FileReactAgent(
    llm_client=llm_client,                # LLM客户端（从 ai_service.chat 包装）
    session_id=session_id,                # 会话ID
    intent_type=intent_type,              # 意图类型
    max_steps=100                         # 最大步数（默认100）
)
async for event in agent.run_stream(user_input):
```

---

#### chat_router 统一准备的公共参数

在步骤6之前（步骤1-5），需要准备以下公共参数：

| 参数 | 准备方式 | 说明 |
|------|---------|------|
| ai_service | AIServiceFactory.create() | AI服务实例 |
| llm_client | 从 ai_service.chat 包装 | LLM客户端函数 |
| task_id | request.task_id or uuid.uuid4() | 任务ID |
| running_tasks | {} | 任务字典 |
| running_tasks_lock | asyncio.Lock() | 任务锁 |
| next_step | 闭包函数 | 步骤计数器 |
| session_id | 已有 | 会话ID |
| wrapped_save_steps | 包装函数 | 保存到DB |
| wrapped_add_step | 包装函数 | 添加步骤并保存 |

---

#### 总结

| 函数 | LLM调用方式 | 需要准备的参数数量 |
|------|------------|------------------|
| chat_stream_query | ai_service | 15个（router准备13个 + 2个初始值） |
| FileReactAgent | llm_client | 4个（router准备） |


阶段2：创建 react_sse_wrapper.py（第二层）【参考附录2.7章节操作说明】
       ├── 从 chat2.py 复制为 react_sse_wrapper.py
       ├── 保留 SSE 转换逻辑（暂时不抽）
       └── 保留任务管理、DB保存等
       验证：原有功能不变

**阶段2当前实施状态（2026-03-26 08:40）**：
- ✅ react_sse_wrapper.py 已创建（354行）
- ✅ 删除 FastAPI 代码，转换为服务层函数
- ⚠️ file_react.ver1_run_stream 尚未删除（仍被 chat_router 调用）
- ⚠️ chat_router 尚未集成 react_sse_wrapper（直接调用 file_react.ver1_run_stream）
- **结论**：阶段2框架已创建，需要阶段3完成集成


阶段3：最终架构（chat_router → react_sse_wrapper → file_react）

> **更新时间**: 2026-03-26 16:10:00
> **更新说明**: 修正阶段3实施步骤，基于当前实际代码结构

**当前状态**（2026-03-26 16:10）：
- chat_router.py 已实现6步流程 ✅
- file_react.ver1_run_stream() 已包含 SSE 格式化逻辑（调用 sse_formatter.py）✅
- react_sse_wrapper.py 已创建但未被调用 ⚠️

---

#### 3.1 当前调用链 vs 目标调用链

```
【当前调用链】（简化版，3层）
chat_router.py (backend/app/services/chat_router.py)
  → FileReactAgent.ver1_run_stream()  [包含 SSE 格式化] (backend/app/services/agent/file_react.py)
  → BaseAgent.run_stream() [返回 event dict] (backend/app/services/agent/base_react.py)

【目标调用链】（完整版，4层）
chat_router.py (backend/app/services/chat_router.py)
  → react_sse_wrapper.generate_sse_stream()  [SSE 格式化] (backend/app/services/react_sse_wrapper.py)
  → FileReactAgent.ver1_run_stream()  [返回 event dict] (backend/app/services/agent/file_react.py)
  → BaseAgent.run_stream() (backend/app/services/agent/base_react.py)

【说明】
- BaseReAct 类在实际代码中不存在，已删除
- react_sse_wrapper.generate_sse_stream() 已创建但目前未被调用（待集成）
- FileReactAgent 冗余代码已清理完成（intent_registry 和 preprocessor 已删除）
```

---

#### 3.2 实施步骤（详细说明）

**第一步：修改 file_react.py**
- 删除 `ver1_run_stream()` 方法
- 保留 `run_stream()` 方法（返回 event dict）
- SSE 格式化逻辑移到 react_sse_wrapper

```python
# 删除 ver1_run_stream() 方法（约100行）
# 保留 run_stream() 方法（返回 event dict）
class FileReactAgent(BaseAgent):
    async def run_stream(self, task, context, max_steps):
        # 返回 event dict，不是 SSE 字符串
        yield {"type": "thought", "content": ...}
        yield {"type": "action_tool", "tool_name": ...}
        ...
```

**第二步：修改 react_sse_wrapper.py**
- 添加 SSE 格式化逻辑（从 file_react.ver1_run_stream 复制）
- 添加调用 file_react.run_stream() 的函数

```python
# react_sse_wrapper.py 新增
async def process_file_operation(
    user_input: str,
    model: str,
    provider: str,
    llm_client: Callable,
    session_id: str,
    next_step: Callable
):
    from app.services.agent.file_react import FileReactAgent
    
    agent = FileReactAgent(llm_client=llm_client, session_id=session_id)
    
    # 调用 run_stream()，获取 event dict
    async for event in agent.run_stream(task=user_input, context=None, max_steps=100):
        step = next_step()
        
        # SSE 格式化（从 ver1_run_stream 复制）
        if event.get("type") == "thought":
            yield format_thought_sse(step=step, content=event.get("content", ""))
        elif event.get("type") == "action_tool":
            yield format_action_tool_sse(...)
        elif event.get("type") == "observation":
            yield format_observation_sse(...)
        elif event.get("type") == "final":
            yield create_final_response(...)
        # ... 其他类型
```

**第三步：修改 chat_router.py**
- 将 `_handle_file_operation` 改为调用 `react_sse_wrapper.process_file_operation()`

```python
# chat_router.py 当前
async for event in agent.ver1_run_stream(...):
    yield event

# 改为
async for event in react_sse_wrapper.process_file_operation(...):
    yield event
```

**第四步：验证**
- 单元测试通过
- 端到端测试正常
- 前后功能一致

---

#### 3.3 为什么需要阶段3

| 原因 | 说明 |
|------|------|
| **架构一致性** | 统一使用 react_sse_wrapper 处理 SSE 格式化 |
| **代码复用** | 网络操作、桌面操作可以用相同的 SSE 格式化逻辑 |
| **职责分离** | Agent 负责执行，SSE 包装负责输出格式 |

---

#### 3.4 不实施阶段3也可以工作

> ⚠️ **说明**：当前实现（3层）已经可以正常工作，阶段3是**可选优化**。

**当前实现**：
- file_react.ver1_run_stream() 自己完成 SSE 格式化
- 优点：简单直接
- 缺点：每个 Agent 都要重复 SSE 格式化代码

**实施后的优点**：
- 统一 SSE 格式化逻辑
- 易于维护和扩展

**结论**：可以先不实施阶段3，等需要添加 network_react / desktop_react 时再考虑。

---

#### 阶段4：start 函数独立设计（2026-03-26 11:29:40 小沈）

> 💡 **问题修正**（感谢小健的分析）：原设计方案将 start 函数放在 Agent 内部调用，这是错误的。start 应该是 **API 层的工具函数**，不是 Agent 的职责。

---

##### 4.1 问题分析（原设计方案的错误）

**原设计方案的问题**：
```
原设计: Agent 内部调用 start_step()
  ↓
问题1: Agent 是普通异步函数，不是 generator，如何发送 SSE？
问题2: start_data 的数据（display_name/provider/model）来自 API 层，不是 Agent 应该关心的
问题3: 这些数据是 final/error 步骤使用，不是 Agent 执行过程使用
问题4: 参数来源复杂（AI服务、API配置），Agent 不应该依赖这些
```

**start 数据的真正使用者**：

| 数据 | 真正使用者 | 说明 |
|------|-----------|------|
| display_name | **API 层** - final 步骤 | Agent 执行完后发送 |
| provider/model | **API 层** - final/error 步骤 | Agent 执行完后发送 |
| task_id | **API 层** - 中断检查 | API 层管理 |
| security_check | **API 层** | 安全检查决定是否调用 Agent |

**核心发现**：start 数据全部是 **API 层** 使用，**Agent 执行过程不需要这些数据**！

---

##### 4.2 正确的架构层次

**Router 服务层 (chat_router.py) 的完整职责**：
```
┌─────────────────────────────────────────────────────────────────┐
│  chat_router.py (Router 服务层)                                  │
│  - 预处理 (PreprocessingPipeline)                               │
│  - 意图检测 (IntentRegistry)                                   │
│  - 安全检测 (security_check)                                    │
│  - start步骤 (start_step)                                      │
│  - 分发到Agent (根据intent_type调用不同Agent)                   │
└─────────────────────────────────────────────────────────────────┘
```

**start 函数的正确位置**：**Router 服务层 (chat_router.py)**

---

##### 4.3 start_step() 函数设计

**文件位置**：`app/chat_stream/start_step.py`

**函数签名**：
```python
async def send_start_step(
    ai_service,                    # AI 服务实例（用于获取 provider/model）
    task_id: str,                 # 任务ID
    next_step: Callable,           # 获取步骤号函数
    user_message: str,            # 用户消息（用于预览）
    security_check_result: dict,   # 安全检查结果
    current_execution_steps: List, # 执行步骤列表
    yield_func: Callable          # SSE发送回调函数
) -> Dict:
    """
    发送 start 步骤的独立函数（统一方法）
    
    职责：
    1. 构建 start_data
    2. 通过 SSE 发送 start 步骤
    3. 保存到 current_execution_steps
    4. 返回 start_data（供后续 final/error 步骤使用）
    
    返回：
    - start_data 字典（包含 display_name/provider/model 等）
    """
```

**函数实现要点**：
```python
async def send_start_step(
    ai_service,
    task_id,
    next_step,
    user_message,
    security_check_result,
    current_execution_steps,
    yield_func
):
    from app.chat_stream.utils import create_timestamp
    
    # 1. 构建 start_data
    start_data = {
        'type': 'start',
        'step': next_step(),
        'timestamp': create_timestamp(),
        'display_name': f"{ai_service.provider} ({ai_service.model})",
        'provider': ai_service.provider,
        'model': ai_service.model,
        'task_id': task_id,
        'user_message': user_message[:40] if user_message else "",
        'security_check': {
            'is_safe': security_check_result.get('is_safe', True),
            'risk_level': security_check_result.get('risk_level'),
            'risk': security_check_result.get('risk'),
            'blocked': security_check_result.get('blocked', False)
        }
    }
    
    # 2. 发送 SSE（通过回调函数）
    yield_func(start_data)
    
    # 3. 保存到 current_execution_steps
    current_execution_steps.append(start_data)
    
    # 4. 返回 start_data
    return start_data
```

---

##### 4.4 start函数独立的价值

| 价值 | 说明 |
|------|------|
| **职责清晰** | start 是 API 层职责，不是 Agent 职责 |
| **SSE 发送** | API 层负责发送 SSE，Agent 是纯逻辑 |
| **数据分离** | API 层管理 start_data，Agent 专注业务逻辑 |
| **接口简洁** | Agent 只需要 llm_client + session_id |
| **统一逻辑** | 避免在多个 API 文件中重复 start 发送逻辑 |

---

##### 4.5 分阶段实施

**阶段4.1**：创建 start_step.py
- 文件位置：`app/chat_stream/start_step.py`
- 定义函数签名和参数
- 实现基本功能

**阶段4.2**：修改 chat_router.py 调用 start_step
- 调用 start_step()
- 处理 security_check 逻辑

**阶段4.3**：修改 final/error 发送逻辑
- 从 start_data 获取 display_name/provider/model
- 统一发送方式

**分阶段优势**：
- 每阶段可独立验证，降低风险
- 不影响现有功能
- 逐步演进，最终达到目标架构

---

#### 阶段5：Router的更新（2026-03-26 小沈）

##### 5.1 Router的完整流程（6步）

**chat_router.py 完整流程（6步）**：
```
步骤1: 预处理 (PreprocessingPipeline)

步骤2: 意图检测 (IntentRegistry)

步骤3: 初始化 + 参数准备
        - ai_service创建 (AIServiceFactory)
        - next_step计数器
        - task_id、running_tasks、current_execution_steps
        - llm_client（Agent用）、running_tasks_lock（chat用）

步骤4: 安全检测 (security_check)
        - 使用 ai_service 的 provider/model

步骤5: start步骤 (start_step)
        - 使用 next_step 计数器
        - 使用 ai_service
        - 发送 SSE
        - 保存 current_execution_steps

步骤6: 分发到Agent
        - 根据 intent_type
        - 使用 running_tasks 管理Session
        - Agent执行完成后发送 final/error
```

---

##### 5.2 代码改造方案

**chat_router.py 当前流程（只有2步）**：
```python
# 步骤1: 意图检测 (已有)
intent_result = self.preprocessing.process(...)

# 步骤2: 分发到Agent (已有)
if intent_type == "file":
    ...
```

**改造为6步流程**：
```python
async def route(self, ...):
    
    # ===== 步骤1: 预处理 =====
    intent_result = self.preprocessing.process(
        user_input=user_input,
        intent_labels=INTENT_LABELS,
        session_id=session_id
    )
    
    # ===== 步骤2: 意图检测 =====
    intent_type = intent_result.get("intent", "chat")
    confidence = intent_result.get("confidence", 0.0)
    
    # ===== 步骤3: 初始化 + 参数准备 =====
    import uuid
    import asyncio
    from typing import Optional
    from app.services import AIServiceFactory
    from app.chat_stream.start_step import send_start_step
    from app.chat_stream.message_saver import save_execution_steps_to_db, add_step_and_save
    
    # ===== 步骤3.1: 基础初始化 =====
    # task_id: 任务ID（必须在步骤5之前定义）
    task_id = request.task_id if request.task_id else str(uuid.uuid4())
    
    # ai_service: AI服务实例
    ai_service = AIServiceFactory.create(
        provider=provider,
        model=model,
        session_id=session_id
    )
    
    # next_step: 步骤计数器
    step_counter = 0
    def next_step():
        nonlocal step_counter
        step_counter += 1
        return step_counter
    
    # running_tasks: 任务字典
    running_tasks: Dict[str, Any] = {}
    
    # current_execution_steps: 执行步骤列表
    current_execution_steps: List[Dict] = []
    
    # ===== 步骤3.2: Agent参数准备 =====
    # llm_client: 从ai_service.chat包装的LLM客户端函数
    async def llm_client(message, history=None):
        response = await ai_service.chat(message, history)
        return type('obj', (object,), {'content': response.content})()
    
    # running_tasks_lock: 任务锁（用于chat_stream_query）
    running_tasks_lock = asyncio.Lock()
    
    # llm_call_count: LLM调用计数器
    llm_call_count = 0
    
    # current_content: 当前累积内容（用于chat_stream_query）
    current_content = ""
    
    # last_is_reasoning: 上一个is_reasoning状态
    last_is_reasoning = None
    
    # last_message: 用户消息
    last_message = user_input
    
    # wrapped_save_steps: 包装的保存到DB函数
    async def wrapped_save_steps(execution_steps, content=None):
        await save_execution_steps_to_db(session_id, execution_steps, content)
    
    # wrapped_add_step: 包装的添加步骤并保存函数
    async def wrapped_add_step(step, content=None):
        await add_step_and_save(current_execution_steps, step, session_id, content)
    
    # ===== 步骤4: 安全检测 ===== 【新增】
    from app.services.shell_security import check_command_safety
    security_check_result = check_command_safety(user_input)
    
    # ===== 步骤5: start步骤 ===== 【新增】
    # 调用独立的 send_start_step() 函数（统一方法）
    start_data = await send_start_step(
        ai_service=ai_service,
        task_id=task_id,
        next_step=next_step,
        user_message=user_input,
        security_check_result=security_check_result,
        current_execution_steps=current_execution_steps,
        yield_func=lambda data: yield f"data: {json.dumps(data)}\n\n"
    )
    
    # ===== 步骤6: 分发到Agent ===== 【修改】
    
    # 6.1 简单对话 (chat/query)
    if intent_type == "chat" or confidence < 0.3:
        from app.services.chat_stream import chat_stream_query
        async for event in chat_stream_query(
            request=request,                    # 获取history
            ai_service=ai_service,              # AI服务
            task_id=task_id,                    # 任务ID（中断检查）
            llm_call_count=llm_call_count,      # LLM调用计数器
            current_execution_steps=current_execution_steps,  # 执行步骤列表
            current_content=current_content,    # 当前累积内容
            last_is_reasoning=last_is_reasoning,  # 上一个is_reasoning状态
            last_message=last_message,          # 用户消息
            running_tasks=running_tasks,        # 运行中的任务
            running_tasks_lock=running_tasks_lock,  # 任务锁
            next_step=next_step,                # 获取步骤号函数
            display_name=start_data['display_name'],  # 显示名称
            session_id=session_id,              # 会话ID
            save_execution_steps_to_db=wrapped_save_steps,  # 保存到DB函数
            add_step_and_save=wrapped_add_step  # 添加步骤并保存函数
        ):
            yield event
    
    # 6.2 文件操作 (FileReactAgent)
    elif intent_type == "file" and confidence >= 0.3:
        from app.services.agent.file_react import FileReactAgent
        agent = FileReactAgent(
            llm_client=llm_client,              # LLM客户端函数
            session_id=session_id,             # 会话ID
            intent_type=intent_type,           # 意图类型
            file_tools=None,                    # 可选，默认自动创建
            max_steps=100                       # 最大步数（默认100）
        )
        async for event in agent.run_stream(user_input):
            yield event
    
    # 6.3 网络操作 (NetworkReactAgent)
    elif intent_type == "network" and confidence >= 0.3:
        from app.services.agent.network_react import NetworkReactAgent
        agent = NetworkReactAgent(
            llm_client=llm_client,              # LLM客户端函数
            session_id=session_id,             # 会话ID
            intent_type=intent_type,           # 意图类型
            max_steps=100                       # 最大步数
        )
        async for event in agent.run_stream(user_input):
            yield event
    
    # 6.4 桌面操作 (DesktopReactAgent)
    elif intent_type == "desktop" and confidence >= 0.3:
        from app.services.agent.desktop_react import DesktopReactAgent
        agent = DesktopReactAgent(
            llm_client=llm_client,              # LLM客户端函数
            session_id=session_id,             # 会话ID
            intent_type=intent_type,           # 意图类型
            max_steps=100                       # 最大步数
        )
        async for event in agent.run_stream(user_input):
            yield event
    
    # 6.5 默认回退到 chat（使用 chat_stream_query）
    else:
        from app.services.chat_stream import chat_stream_query
        async for event in chat_stream_query(
            request=request,                      # 获取history
            ai_service=ai_service,                # AI服务
            task_id=task_id,                      # 任务ID（中断检查）
            llm_call_count=llm_call_count,        # LLM调用计数器
            current_execution_steps=current_execution_steps,  # 执行步骤列表
            current_content=current_content,       # 当前累积内容
            last_is_reasoning=last_is_reasoning,  # 上一个is_reasoning状态
            last_message=last_message,            # 用户消息
            running_tasks=running_tasks,          # 运行中的任务
            running_tasks_lock=running_tasks_lock,  # 任务锁
            next_step=next_step,                  # 获取步骤号函数
            display_name=start_data['display_name'],  # 显示名称
            session_id=session_id,                # 会话ID
            save_execution_steps_to_db=wrapped_save_steps,   # 保存到DB函数
            add_step_and_save=wrapped_add_step    # 添加步骤并保存函数
        ):
            yield event
```

---

##### 5.3 分阶段实施

**阶段5.1**：添加初始化+参数准备步骤3
- 步骤3.1 基础初始化：ai_service创建、next_step计数器、running_tasks、current_execution_steps
- 步骤3.2 Agent参数准备：llm_client、running_tasks_lock、llm_call_count、current_content、last_is_reasoning、last_message、wrapped_save_steps、wrapped_add_step

**阶段5.2**：添加安全检测步骤4
- 从chat2.py迁移security_check逻辑

**阶段5.3**：添加start步骤步骤5
- 调用start_step()函数
- 发送SSE

**阶段5.4**：修改分发逻辑步骤6
- 根据intent_type分发到不同Agent
- 使用running_tasks管理Session

---

### 附录2.9 待创建/改造文件清单

> **更新时间**: 2026-03-26 06:20:00
> **更新说明**: 确认第三层 react_sse_wrapper.py 价值，更新设计内容

| 序号 | 文件 | 操作 | 对应层 | 状态 |
|------|------|------|--------|------|
| 1 | `app/services/chat_router.py` | 创建 | 第一层 | ✅ 已完成 |
| 2 | `app/services/react_sse_wrapper.py` | 创建 | 第二层 | ✅ 已完成 |
| 3 | `app/services/agent/file_react.py` | 抽取 | 第三层 | ✅ 已完成 |
| 4 | `app/services/agent/network_react.py` | 创建 | 第三层 | 待实现 |
| 5 | `app/services/agent/desktop_react.py` | 创建 | 第三层 | 待实现 |
| 6 | `app/services/agent/base_react.py` | 已完成 | 第四层 | ✅ 已完成 |
| 7 | `app/services/agent/agent.py` | 废弃 | - | 待废弃 |
| 8 | `app/api/v1/chat2.py` | 改造 | - | 待改造（调用react_sse_wrapper） |

---

## 附录：TODO 待处理清单

> **📝 说明**：记录待完成的改进项，便于追踪和清理。

### 历史记录（已完成或已变更）

| 序号 | TODO | 位置 | 概要 | 状态 |
|------|------|------|------|------|
| 1 | chat_stream_query 调用 | 附录2.5.5（第1324行） | chat_stream_query 已实现，需传递 request/ai_service/running_tasks 等参数才能调用，第一阶段先返回提示信息 | ⏸️ 等待前端调用 |
| ~~2~~ | ~~file_react.py 清理~~ | ~~附录2.6（第1417行）~~ | ~~intent_registry/preprocessor 对象仍保留，run_stream 仍有意图识别调用~~ | ~~✅ 已完成~~ |

> **2026-03-26 更新**：TODO 2 已完成，已删除 file_react.py 中冗余的 intent_registry/preprocessor 代码。

### 当前待办

| 序号 | TODO | 概要 | 优先级 |
|------|------|------|--------|
| 3 | 前端调用新端点 | 修改前端 URL 从 `/chat/stream` 改为 `/chat/stream/v2`（见下方详细说明） | 高 |
| 4 | cancel/pause/resume 集成 | 任务控制功能仍用 chat2.py 旧端点，后续可集成到 react_sse_wrapper | 低 |
| 5 | react_sse_wrapper 集成 | 当前直接调用 file_react.ver1_run_stream，未经过 react_sse_wrapper 包装，可选优化 | 低 |

#### TODO 3 详细说明

**前端修改位置**：`frontend/src/utils/sse.ts` 第440行

```typescript
// 修改前
const url = `${config.baseURL}/chat/stream`;

// 修改后（选择以下之一）
// 方式A: 直接使用新端点
const url = `${config.baseURL}/chat/stream/v2`;

// 方式B: 保留旧端点（等后续任务控制也迁移后再改）
// const url = `${config.baseURL}/chat/stream`;
```

**API参数对比**：新旧 API 参数完全一致，前端只需修改 URL，无需修改请求体。

---

## 附录：回归验证检查清单

> **📝 说明**：以下检查清单用于待实现任务完成后的验证，确保功能正常。

| 序号 | 验证项 | 验证方法 |
|------|--------|---------|
| 1 | 流式对话正常 | 触发 chat 意图，检查 chunk/final 事件正确 |
| 2 | 文件操作正常 | 触发文件操作，检查 ReAct 循环事件正确 |
| 3 | 网络操作正常 | 触发网络操作，检查 ReAct 循环事件正确 |
| 4 | Session 管理正常 | 检查创建/传递/关闭流程 |
| 5 | 预处理识别意图 | 检查 intent_type 正确识别 |
| 6 | 历史消息传递 | 检查 history 不经过预处理 |
| 7 | 中断/暂停功能 | 触发中断，检查状态正确 |
| 8 | 数据库保存 | 检查 execution_steps 正确保存 |

---

**文档结束**
