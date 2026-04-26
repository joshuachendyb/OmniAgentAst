# OmniAgentAs-desk 智能助手桌面版

**版本**: v0.10.17 (2026-04-26)  
**状态**: 生产就绪  
**最后更新**: 2026-04-26 10:00:00

---

## 一、项目概述

OmniAgentAs-desk 是一个基于 **ReAct (Reasoning + Acting)** 架构的智能助手桌面应用，具备以下核心能力：

| 能力 | 说明 |
|------|------|
| **智能文件操作** | 读取、写入、列表、搜索、删除、移动文件 |
| **时间工具** | 获取当前时间、格式化、时间差、定时器、时区转换、判断周末/假日 |
| **多AI提供商** | OpenCode、智谱AI、DeepSeek、Kimi等 |
| **流式响应** | SSE实时流式输出，思考过程即时可见 |
| **意图检测** | GLiClass零样本分类，自动识别用户意图 |
| **安全防护** | 路径白名单、操作审计、异常回滚 |
| **会话管理** | 历史记录、搜索、会话标题自动生成 |

---

## 二、技术架构

### 2.1 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.11+ / FastAPI / Uvicorn |
| **前端** | React 18 / TypeScript / Vite / Ant Design |
| **LLM集成** | 多Provider适配层（OpenAI兼容API） |
| **数据库** | SQLite (aiosqlite) |

### 2.2 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React + Vite)                     │
│  ┌─────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  Chat   │  │  Settings  │  │  Session   │  │  Mark   │ │
│  │   UI    │  │    UI      │  │    UI      │  │   down  │ │
│  └────┬────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘ │
│       │            │             │            │         │
│       └────────────┴─────────────┴────────────┘         │
│                         │                               │
│                    SSE 流式                             │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────┐
│                     后端 (FastAPI)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ ChatRouter  │  │Preprocessing│  │ ReAct Loop  │       │
│  │   路由层    │  │   预处理   │  │   执行层    │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │               │              │               │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐       │
│  │   LLM Core  │  │   Tools    │  │   Safety   │       │
│  │  LLM适配器  │  │  文件工具  │  │  安全检查  │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## 三、快速开始

### 3.1 环境要求

| 依赖 | 版本 |
|------|------|
| Python | ≥ 3.11 |
| Node.js | ≥ 18.x |
| pnpm | ≥ 8.0 (推荐) |

### 3.2 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd OmniAgentAs-desk

# 2. 后端安装
cd backend
pip install -r requirements.txt

# 3. 前端安装
cd ../frontend
pnpm install

# 4. 配置
cp config/config.yaml.example config/config.yaml
# 编辑 config.yaml 填入API密钥
```

### 3.3 运行

```bash
# 后端 (端口 8000)
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 前端 (端口 5173)
cd frontend
pnpm dev
```

访问 `http://localhost:5173` 开始使用。

---

## 四、核心功能

### 4.1 文件操作工具

| 工具 | 功能 |
|------|------|
| `read_file` | 读取文件内容 |
| `write_file` | 写入/创建文件 |
| `list_directory` | 列出目录内容 |
| `delete_file` | 删除文件/目录 |
| `move_file` | 移动/重命名文件 |
| `search_files` | 搜索文件 |
| `generate_report` | 生成操作报告 |

### 4.2 LLM Provider 支持

- **OpenCode** (默认)
- **智谱AI** (GLM-4)
- **DeepSeek**
- **Kimi**
- **通义千问**
- **其他 OpenAI 兼容API**

### 4.3 安全特性

- **路径验证**: 限制操作范围在工作目录内
- **操作审计**: 记录所有文件操作历史
- **异常回滚**: 支持撤销最近的操作
- **黑名单**: 禁止危险Shell命令

---

## 五、目录结构

```
OmniAgentAs-desk/
├── backend/
│   └── app/
│       ├── api/v1/           # API路由
│       ├── services/         # 业务逻辑
│       │   ├── agent/        # ReAct Agent
│       │   ├── preprocessing/# 预处理
│       │   ├── tools/        # 工具集
│       │   ├── safety/       # 安全检查
│       │   └── prompts/      # Prompt模板
│       └── utils/            # 工具函数
├── frontend/
│   └── src/
│       ├── components/       # React组件
│       ├── pages/            # 页面
│       ├── hooks/            # 自定义Hook
│       └── utils/            # 工具函数
├── config/                   # 配置文件
├── doc/                      # 设计文档
└── version.txt              # 版本历史
```

---

## 六、版本历史

### v0.9.8 (2026-04)

- LLM响应解析器重构优化
- ReAct Loop 统一解析器 (react_output_parser)
- 测试覆盖率提升至91个用例

### v0.9.5 (2026-04)

- 多意图预处理系统
- GLiClass 意图分类集成
- 文件安全检查增强

### v0.9.0 (2026-03)

- ReAct 架构正式上线
- SSE 流式响应
- 7个文件操作工具

完整版本历史见 `version.txt`

---

## 七、数据库

| 数据库 | 路径 |
|--------|------|
| 聊天历史 | `~/.omniagent/chat_history.db` |
| 操作记录 | `~/.omniagent/operations.db` |

---

## 八、测试

```bash
# 后端测试
cd backend
pytest tests/ -v

# 前端测试
cd frontend
pnpm test

# E2E测试
cd frontend
pnpm test:e2e
```

---

## 九、API文档

启动后端后访问：
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 十、故障排除

| 问题 | 解决方案 |
|------|---------|
| 后端启动失败 | 检查 Python ≥ 3.11，端口8000是否被占用 |
| 前端启动失败 | 检查 Node.js ≥ 18，清除 node_modules 后重装 |
| API连接失败 | 检查 config.yaml 中的 API 密钥是否有效 |

---

**作者**: 北京老陈、小沈、小强、小健、小资、老杨、小许  
**许可**: MIT License

---

**最后更新**: 2026-04-18 20:25:57  
**版本**: v0.9.8.5  
**状态**: ✅ 生产就绪