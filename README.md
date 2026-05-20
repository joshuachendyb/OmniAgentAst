# OmniAgentAs-desk

> AI智能体桌面应用 - 基于 ReAct 架构的全栈 Web 应用（React + FastAPI）

**版本**: v0.13.0 | **更新时间**: 2026-05-20 20:57:24 | **作者**: 北京老陈团队

---

## 一、项目概述

OmniAgentAs-desk 是一个基于 **ReAct (Reasoning + Acting)** 架构的智能助手桌面应用，具备以下核心能力：

| 能力 | 说明 |
|------|------|
| **135个工具函数** | 覆盖文件、系统、网络、Shell、文档、桌面等12个分类 |
| **ReAct推理引擎** | thought → action → observation 循环推理 |
| **Agent注册表** | AgentRegistry统一管理意图→Agent映射，配置化驱动 |
| **通用Agent** | GenericReactAgent替代7个同质Agent，Profile配置化 |
| **多AI Provider** | OpenCode、智谱AI、DeepSeek、Kimi等 OpenAI兼容API |
| **流式响应** | SSE实时推送，推理过程即时可见 |
| **会话管理** | 历史记录、搜索、标题自动生成、跨会话切换 |
| **安全防护** | OOM防护、符号链接防护、代码安全验证、数据保护、路径白名单 |

---

## 二、技术架构

### 2.1 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **后端** | Python / FastAPI / Uvicorn | 3.13 / 0.109.0 / 0.27.0 |
| **前端** | React / TypeScript / Vite / Ant Design | 18 / 5 / — / 5 |
| **LLM集成** | 多Provider适配层（OpenAI兼容API） | — |
| **数据库** | SQLite (aiosqlite + SQLAlchemy) | — |
| **测试** | pytest / Vitest / Playwright | — |

### 2.2 架构图

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
│  │ ChatRouter  │  │Semantic     │  │ ReAct Loop  │       │
│  │   路由层    │  │Router(规划中)│  │   执行层    │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │               │              │               │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐       │
│  │AgentRegistry│  │   Tools    │  │  Safety    │       │
│  │ Agent注册表 │  │ 135个工具  │  │ 安全检查层 │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## 三、工具体系（135个）

### 3.1 工具分类

| 分类 | 数量 | 说明 |
|------|------|------|
| **文件操作** (file) | ~27 | 读写、搜索、编辑、归档、压缩等 |
| **Shell命令** (shell) | ~5 | 命令执行、Python/JS代码执行 |
| **网络通信** (network) | ~10 | HTTP请求、下载、网页抓取、网络诊断 |
| **桌面操作** (desktop) | ~15 | 窗口管理、截屏、OCR、剪贴板 |
| **系统信息** (system) | ~15 | 系统查询、进程管理、服务控制、环境变量 |
| **文档处理** (document) | ~25 | PDF/Word/Excel读取、格式转换、SQL查询 |
| **元工具** (meta) | ~10 | 工具帮助、时间日期、定时器 |
| **数据分析** (data_analysis) | 3 | 数据读取、图表生成、数据分析 |
| **环境检查** (env_check) | 9 | 安全验证、格式校验、可用性检查 |
| **GUI操作** (gui) | 12 | 鼠标键盘控制、截图、录屏 |
| **数据库辅助** (db_helper) | 7 | 事务管理、表结构查询、连接验证 |
| **数据格式** (data_format) | 3 | JSON/CSV读写 |

### 3.2 工具注册架构

```
backend/app/services/tools/
├── registry.py              # 统一注册表 + ToolCategory枚举
├── safety.py                # 工具安全等级定义（规划中）
├── __init__.py              # 总入口（导入触发注册）
├── file/                    # 文件操作
├── shell/                   # Shell命令
├── network/                 # 网络通信
├── desktop/                 # 桌面操作
├── system/                  # 系统信息
├── document/                # 文档处理
├── meta/                    # 元工具
├── data_analysis/           # 数据分析
├── env_check/               # 环境检查
├── gui/                     # GUI操作
├── db_helper/               # 数据库辅助
└── data_format/             # 数据格式
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

### 4.1 当前架构

```
BaseAgent(ABC)                 ← ReAct循环核心
ReactAgentMixin                ← 公用逻辑混入
        ↓ MRO
FileReactAgent                 ← 有实质差异（session/rollback/alias）
TimeReactAgent                 ← 有实质差异（noop rollback）
GenericReactAgent              ← 通用Agent（替代7个同质Agent）
```

### 4.2 Agent注册表

```python
AgentRegistry
├── register(profile, agent_class)   # 注册意图→Agent映射
├── get_profile(intent_type)         # 获取Agent配置
├── create_agent(intent_type, ...)   # 创建Agent实例
└── _compat_map                      # 旧意图名兼容映射
```

### 4.3 规划中架构（方案C）

| 模块 | 状态 | 说明 |
|------|------|------|
| SemanticRouter | 规划中 | LLM语义路由，推荐工具子集 |
| ToolSafetyLayer | 规划中 | 工具声明式安全分级（READ_ONLY/SAFE/DESTRUCTIVE/DANGEROUS） |
| ToolObserver | 规划中 | 全量审计日志 + 异常检测 |
| HITL | 规划中 | DANGEROUS工具人机协同确认 |

详见 `doc-5月优化/Agent融合架构重构方案-方案C-小沈-2026-05-20.md`

---

## 五、项目结构

```
OmniAgentAs-desk/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 端点
│   │   ├── services/
│   │   │   ├── agent/          # Agent体系（base_react, generic_react, mixins/）
│   │   │   ├── tools/          # 工具函数（12个分类，135个工具）
│   │   │   ├── preprocessing/  # 意图分类
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
├── doc-5月优化/                # 架构重构设计文档
├── doc/                        # 系统设计文档
├── notes/                      # 调试笔记
├── version.txt                 # 版本变更记录
└── AGENTS.md                   # 开发规范
```

---

## 六、快速开始

### 6.1 环境要求

| 依赖 | 版本 |
|------|------|
| Python | ≥ 3.11 |
| Node.js | ≥ 18.x |
| npm | ≥ 9.0 |

### 6.2 安装与运行

```bash
# 1. 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 2. 前端
cd frontend
npm install
npm run dev
```

后端: `http://127.0.0.1:8000` | API文档: `http://127.0.0.1:8000/docs` | 前端: `http://localhost:5173`

### 6.3 可选依赖（二级工具）

```bash
# 数据分析
pip install pandas matplotlib

# 文档读写
pip install pdfplumber python-docx openpyxl

# GUI操作
pip install pyautogui pywin32 pytesseract Pillow

# 屏幕录制
pip install mss imageio imageio-ffmpeg numpy
```

---

## 七、开发命令

### 后端

| 命令 | 说明 |
|------|------|
| `python -m uvicorn app.main:app --reload` | 启动开发服务器 |
| `pytest` | 运行全部测试 |
| `pytest tests/test_xxx.py -v` | 运行指定测试文件 |
| `pytest -k test_name -v` | 按名称匹配运行测试 |
| `pytest --cov=app` | 测试并生成覆盖率 |

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
| 聊天历史 | `backend/chat_app.db` |

---

## 九、版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **v0.13.0** | 2026-05-20 | Agent体系重构：AgentRegistry/GenericReactAgent；新增方案C融合架构设计；工具总数112→135 |
| **v0.12.5** | 2026-05-02 | 新增5个二级Tool分类(35个工具): data_analysis, document, env_check, gui, db_helper |
| v0.12.4 | 2026-05-01 | 修复16项Bug；新增跨分类工具支持/CRSS独立模块/Shell会话管理/网络工具 |
| v0.12.3 | 2026-04-30 | 跨分类工具访问设计与实现；CRSS评分关键词补充；LLM多意图返回 |
| v0.12.2 | 2026-04-29 | Pydantic Schema注册规范化；ToolCategory枚举扩展；新增Tool 15个 |
| v0.9.8 | 2026-04 | LLM响应解析器重构；ReAct Loop统一解析器；测试91个用例 |
| v0.9.0 | 2026-03 | ReAct架构正式上线；SSE流式响应；7个文件操作工具 |

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

**许可**: 内部项目 | **最后更新**: 2026-05-20 20:57:24 | **版本**: v0.13.0
