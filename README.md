# OmniAgentAs-desk

> AI智能体桌面应用 - 基于 ReAct 架构的全栈 Web 应用（React + FastAPI）

**版本**: v4.0.0 | **更新时间**: 2026-05-26 09:13:45 | **作者**: 北京老陈团队

---

## 一、项目概述

OmniAgentAs-desk 是一个基于 **ReAct (Reasoning + Acting)** 架构的智能助手桌面应用，具备以下核心能力：

| 能力 | 说明 |
|------|------|
| **58个工具函数** | 覆盖文件、Shell、网络、系统、桌面、文档、元工具等7个分类 |
| **ReAct推理引擎** | thought → action → observation 循环推理 |
| **AgentFactory分发** | 按意图类型分发到UniversalReactAgent / DesktopReactAgent |
| **多AI Provider** | OpenCode、智谱AI、DeepSeek、Kimi等 OpenAI兼容API |
| **流式响应** | SSE实时推送，推理过程即时可见 |
| **会话管理** | 历史记录、搜索、标题自动生成、跨会话切换 |
| **安全防护** | OOM防护、符号链接防护、代码安全验证、数据保护、路径白名单 |

---

## 二、技术架构

### 2.1 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **后端** | Python / FastAPI / Uvicorn | 3.13 / ≥0.109.0 / ≥0.27.0 |
| **前端** | React / TypeScript / Vite / Ant Design | 18 / 5 / — / 5 |
| **LLM集成** | 多Provider适配层（OpenAI兼容API） | — |
| **数据库** | SQLite (aiosqlite + SQLAlchemy) | — |
| **测试** | pytest / Vitest / Playwright | — |

### 2.2 当前架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + Vite)                     │
│  ┌─────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  Chat   │  │  Settings  │  │  Session   │  │  Mark   │ │
│  │   UI    │  │    UI      │  │    UI      │  │   down  │ │
│  └────┬────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘ │
│       └────────────┴─────────────┴────────────┘         │
│                         │ SSE 流式                        │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────┐
│                     后端 (FastAPI)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ ChatRouter  │  │ 意图识别    │  │ ReAct Loop  │       │
│  │   路由层    │  │CRSS+LLM兜底 │  │   执行层    │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │               │              │               │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐       │
│  │AgentFactory │  │   Tools    │  │  Safety    │       │
│  │ 2个Agent类  │  │  58个工具  │  │ 安全检查   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## 三、工具体系（58个）

### 3.1 工具分类（7个ToolCategory）

| 分类 | 数量 | 说明 |
|------|------|------|
| **FILE** | 11 | 文件读写、搜索、编辑、归档等 |
| **SHELL** | 4 | 注册到SYSTEM分类，Shell命令执行、Python/JS代码执行 |
| **NETWORK** | 5 | HTTP请求、下载、网页抓取、网络诊断 |
| **SYSTEM** | 10 | 系统信息查询、进程管理、服务控制、环境变量 |
| **DESKTOP** | 9 | 窗口管理、截屏、OCR、剪贴板、通知 |
| **DOCUMENT** | 9 | PDF/Word/Excel读写、SQL查询、图表生成 |
| **META** | 10 | 注册到SYSTEM分类，工具帮助、时间日期、定时器 |
| **合计** | **58** | |

> **注**：SHELL工具注册到SYSTEM分类，META工具注册到SYSTEM分类，其余分类一对一注册。

### 3.2 工具注册架构

```
backend/app/services/tools/
├── registry.py              # 统一注册表 + ToolCategory枚举（7分类）
├── __init__.py              # 总入口（导入触发注册）
├── tool_aliases.py          # 工具别名映射
├── tool_config.py           # 工具配置
├── tool_meta.py             # 工具元数据
├── tool_result_utils.py     # 工具结果工具函数
├── toolhelper/              # 工具辅助
├── file/                    # 文件操作
├── shell/                   # Shell命令
├── network/                 # 网络通信
├── desktop/                 # 桌面操作
├── system/                  # 系统信息
├── document/                # 文档处理
└── meta/                    # 元工具
```

每个分类目录结构：
```
{category}/
├── __init__.py              # 导入触发注册
├── {category}_schema.py     # Pydantic 参数模型
├── {category}_register.py   # 注册点
└── {category}_tools.py      # 具体实现
```

---

## 四、Agent体系

### 4.1 当前架构（2个Agent实现类）

```
BaseAgent(ABC)                 ← ReAct循环核心
ReactAgentMixin                ← 公用逻辑混入
RollbackMixin                  ← rollback能力（仅UniversalReactAgent使用）
ToolStepMixin                  ← 工具步骤管理
         ↓ MRO
UniversalReactAgent            ← ToolStep + ReactAgentMixin + Rollback + BaseAgent
DesktopReactAgent              ← ToolStep + ReactAgentMixin + BaseAgent
```

### 4.2 AgentFactory 意图分发

```python
AgentFactory.create(intent_type, llm_client, task_id, ...)
├── "file"      → UniversalReactAgent
├── "system"    → UniversalReactAgent  (含 shell / meta / time / code_execution 等别名)
├── "network"   → UniversalReactAgent
├── "document"  → UniversalReactAgent  (含 database 别名)
└── "desktop"   → DesktopReactAgent
```

共有 **5个意图类型**、含别名 **12个入口**，后路由到 2 个实现类。

### 4.3 Agent 2.0（规划中）

| 模块 | 状态 | 说明 |
|------|------|------|
| SemanticRouter | 设计中 | LLM语义路由，替代CRSS正则匹配 |
| ToolSafetyLayer | 设计中 | 工具声明式安全分级 |
| ToolObserver | 设计中 | 全量审计日志 + 异常检测 |
| HITL | 设计中 | DANGEROUS工具人机协同确认 |

> 统一Agent（GenericReactAgent → UniversalReactAgent）已在 v4.0.0 完成，详见 `doc-agent2.0/`。

---

## 五、项目结构

```
OmniAgentAs-desk/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 端点
│   │   ├── services/
│   │   │   ├── agent/          # Agent体系（base_react, 2个实现类, mixins/）
│   │   │   ├── tools/          # 工具函数（7个分类目录，58个工具）
│   │   │   ├── preprocessing/  # 意图分类
│   │   │   ├── intents/        # 意图定义
│   │   │   ├── safety/         # 安全检查
│   │   │   └── llm_core.py     # LLM客户端
│   │   └── utils/
│   ├── tests/                  # 后端测试（pytest）
│   ├── tools/                  # 测试与调试脚本
│   └── requirements.txt
├── frontend/                   # React + TypeScript 前端
│   ├── src/
│   │   ├── components/         # UI 组件
│   │   ├── pages/              # 页面
│   │   ├── services/           # API 服务
│   │   └── utils/              # 工具函数
│   ├── tests/                  # 前端测试
│   └── package.json
├── config/                     # 配置文件
├── doc-agent2.0/               # Agent 2.0架构重构设计文档
├── doc/                        # 系统设计文档
├── notes/                      # 调试笔记
├── version.txt                 # 版本变更记录
└── AGENTS.md                   # 开发规范
```

---

## 六、快速开始

### 6.1 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 测试用 3.13 |
| Node.js | ≥ 18.x | — |
| npm | ≥ 9.0 | — |

> **虚拟环境说明**：Python 后端强烈建议使用虚拟环境，原因：
> 1. **隔离依赖** — 不同项目用不同版本的包，互不冲突（如项目A用pydantic 2.5、项目B用pydantic 2.13）
> 2. **干净卸载** — 不要了直接删 `.venv` 目录，不影响全局 Python
> 3. **环境可复现** — `requirements.txt` 一键装完，新同事 clone 下来就能跑

### 6.2 初次安装（新人从零开始）

> **前提**：已下载项目代码，打开命令行（PowerShell / cmd），`cd` 到项目文件夹（如 `cd D:\OmniAgentAs-desk`）。

后端和前端需要**同时运行**，所以要开**两个命令行窗口**。

---

#### 窗口 1 — 后端（选一种方式）

先进入后端目录：

```bash
cd backend
```

**方式 A（推荐）：虚拟环境**

```bash
# ① 创建虚拟环境（仅第一次需要）
python -m venv .venv

# ② 安装依赖（仅第一次需要）
.venv\Scripts\pip install -r requirements.txt

# ③ 启动后端服务
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

> 启动 uvicorn 后这个窗口**不要关闭**，它要一直运行。

**方式 B：全局 Python（不用虚拟环境）**

```bash
# ① 安装依赖（仅第一次需要）
pip install -r requirements.txt

# ② 启动后端服务
python -m uvicorn app.main:app --reload --port 8000
```

> 方式 B 的包装到全局，不同项目依赖版本不同时可能冲突。
> 启动后这个窗口**同样不要关闭**。

---

#### 窗口 2 — 前端（两种方式一样）

再开一个命令行窗口，同样先 `cd` 到项目文件夹，然后：

```bash
cd frontend

# ① 安装依赖（仅第一次需要）
npm install

# ② 启动前端开发服务器
npm run dev
```

> 这个窗口启动后**也不要关闭**。

---

#### 打开浏览器访问

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 前端页面 |
| http://127.0.0.1:8000 | 后端 API |
| http://127.0.0.1:8000/docs | API 交互式文档 |

---

### 6.2a 日常运行（第二次及以后）

不用再装依赖了，直接启动就行。同样开**两个命令行窗口**，先 `cd` 到项目文件夹。

#### 窗口 1 — 后端

```bash
cd backend
```

**虚拟环境方式：**

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

**全局 Python 方式：**

```bash
python -m uvicorn app.main:app --reload --port 8000
```

> 启动后窗口 1 不要关闭。

#### 窗口 2 — 前端

```bash
cd frontend
npm run dev
```

> 启动后窗口 2 不要关闭。

### 6.3 可选依赖（二级工具）

这些包大部分已包含在 `requirements.txt` 中。如需单独安装：

<details>
<summary><b>虚拟环境</b></summary>

```bash
cd backend
.venv\Scripts\pip install pandas matplotlib
.venv\Scripts\pip install pdfplumber python-docx openpyxl
.venv\Scripts\pip install pyautogui pywin32 pytesseract Pillow
.venv\Scripts\pip install mss imageio numpy
```
</details>

<details>
<summary><b>全局 Python</b></summary>

```bash
cd backend
pip install pandas matplotlib
pip install pdfplumber python-docx openpyxl
pip install pyautogui pywin32 pytesseract Pillow
pip install mss imageio numpy
```
</details>

---

## 七、开发命令

### 后端

<details>
<summary><b>虚拟环境（推荐）</b></summary>

激活后命令直接敲，无需前缀：

```bash
cd backend
.venv\Scripts\activate
```

| 命令 | 说明 |
|------|------|
| `uvicorn app.main:app --reload` | 启动开发服务器 |
| `pytest` | 运行全部测试 |
| `pytest tests/test_xxx.py -v` | 运行指定测试文件 |
| `pytest -k test_name -v` | 按名称匹配运行测试 |
| `pytest --cov=app` | 测试并生成覆盖率 |

不激活时，每条命令加 `.venv\Scripts\` 前缀：

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload
.venv\Scripts\pytest -k test_name -v
```
</details>

<details>
<summary><b>全局 Python</b></summary>

| 命令 | 说明 |
|------|------|
| `python -m uvicorn app.main:app --reload` | 启动开发服务器 |
| `pytest` | 运行全部测试 |
| `pytest tests/test_xxx.py -v` | 运行指定测试文件 |
| `pytest -k test_name -v` | 按名称匹配运行测试 |
| `pytest --cov=app` | 测试并生成覆盖率 |
</details>

### 前端

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 生产构建 |
| `npm run test` | 运行单元测试 |
| `npm run test:coverage` | 测试覆盖率 |
| `npm run lint` | ESLint 检查 |
| `npm run lint:fix` | 自动修复 ESLint 问题 |
| `npm run format` | Prettier 格式化 |
| `npm run test:e2e` | Playwright E2E 测试 |

---

## 八、数据库

| 数据库 | 路径 |
|--------|------|
| 聊天历史 | `~/.omniagent/chat_history.db` |

---

## 九、版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **v4.0.0** | 2026-05-25 | 全面import修复、测试文件修复、requirements.txt修复、文档目录整理、里程碑版本 |
| v0.13.46 | 2026-05-25 | feature/prompt-optimization 全量变更合并 |
| v0.13.11 | 2026-05-20 | Agent架构重构设计文档；README全面更新 |
| v0.13.0 | 2026-05-18 | ToolCategory从13类精简为7类 |
| v0.9.0 | 2026-03 | ReAct架构正式上线 |

详细变更记录见 `version.txt`

---

## 十、故障排除

| 问题 | 解决方案 |
|------|---------|
| 后端启动失败 | 检查 Python ≥ 3.11，端口8000是否被占用 |
| 前端启动失败 | 检查 Node.js ≥ 18，清除 node_modules 后重装 |
| API连接失败 | 检查 config.yaml 中的 API 密钥是否有效 |
| 二级工具不可用 | 安装对应依赖库（见6.3节可选依赖） |

---

## 十一、团队成员

| 角色 | 名称 | 职责 |
|------|------|------|
| 产品负责人 | 北京老陈 | 需求决策、质量把控 |
| 后端开发 | 小沈 | 架构设计、后端实现、工具开发 |
| 后端审查 | 小健 | 代码审查、测试、风险分析 |
| 前端开发 | 小强 | 前端实现、UI/UE设计 |
| 前端审查 | 小资 | 前端代码检查、测试 |
| 风险分析 | 老杨 | 安全审查、疑难诊断 |
| 需求分析 | 小许 | 需求文档、规格说明 |

---

**许可**: 内部项目 | **最后更新**: 2026-05-26 09:13:45 | **版本**: v4.0.0
