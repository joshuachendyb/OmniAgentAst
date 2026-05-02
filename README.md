# OmniAgentAs-desk

> AI智能体桌面应用 - 基于 ReAct 架构的全栈 Web 应用（React + FastAPI）

**版本**: v0.12.5 | **更新时间**: 2026-05-02 09:42:02 | **作者**: 北京老陈团队

---

## 一、项目概述

OmniAgentAs-desk 是一个基于 **ReAct (Reasoning + Acting)** 架构的智能助手桌面应用，具备以下核心能力：

| 能力 | 说明 |
|------|------|
| **112个工具函数** | 覆盖文件、系统、网络、Shell、数据库、GUI等14个分类 |
| **ReAct推理引擎** | thought → action → observation 循环推理 |
| **CRSS意图识别** | 基于风险评分的命令意图分类系统 |
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
│  │ ChatRouter  │  │Preprocessing│  │ ReAct Loop  │       │
│  │   路由层    │  │  意图识别   │  │   执行层    │       │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘       │
│         │               │              │               │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴──────┐       │
│  │   LLM Core  │  │   Tools    │  │   Safety   │       │
│  │  LLM适配器  │  │ 112个工具  │  │  安全检查  │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

---

## 三、工具体系（112个）

### 3.1 一级工具（35个）

| 分类 | 数量 | 工具列表 |
|------|------|---------|
| **文件操作** (file) | 27 | read_file, write_file, list_directory, delete_file, move_file, search_file_content, search_files, generate_report, copy_file, create_directory, get_file_info, compare_files, batch_rename, compress_files, file_monitor, file_statistics, file_checksum, read_text_file, read_media_file, read_batch_file, precise_replace_in_file, edit_file, rename_file, glob_files, grep_file_content, get_directory_tree, list_allowed_directories |
| **Shell命令** (shell) | 6 | execute_command, get_working_directory, change_directory, check_path_exists, get_shell_output, terminate_shell |
| **网络通信** (network) | 6 | http_request, download_file, fetch_webpage, search_web, ping, port_check |
| **时间日期** (time) | 9 | time_now, time_format, time_diff, timer_set, timer_clear, time_utc_to_local, time_local_to_utc, time_is_weekend, time_is_holiday |
| **环境变量** (env) | 3 | get_env, set_env, list_env |
| **系统信息** (system) | 21 | get_system_info, net_connections, event_log, list_processes, kill_process, log_message, get_logs, service_list, service_start, service_stop, task_list, task_create, task_delete, reg_read, reg_write, reg_delete, read_json, write_json, read_csv_basic, execute_python, execute_javascript |
| **数据库** (database) | 3 | query_sql, execute_sql, get_db_schema |
| **桌面功能** (desktop) | 3 | list_windows, get_window_info, set_window_state |

### 3.2 二级工具（77个）

| 分类 | 数量 | 工具列表 | 依赖库 |
|------|------|---------|--------|
| **数据分析** (data_analysis) | 3 | read_csv_dataframe, generate_chart, analyze_data | pandas, matplotlib |
| **文档读写** (document) | 3 | read_pdf, read_docx, read_xlsx | pdfplumber, python-docx, openpyxl |
| **环境检查** (env_check) | 9 | check_python_available, validate_code_safety, check_node_available, check_module_available, validate_csv_format, validate_chart_data, check_pdf_readable, check_docx_readable, check_xlsx_readable | — |
| **GUI操作** (gui) | 12 | click, move, scroll, type_text, shortcut, key_combo, screenshot, snapshot, screen_record, focus_window, resize_window, ocr | pyautogui, pywin32, pytesseract |
| **数据库辅助** (db_helper) | 7 | check_db_exists, get_table_schema, begin_transaction, commit_transaction, rollback_transaction, check_network_connectivity, validate_url | — |

### 3.3 工具注册架构

```
backend/app/services/tools/
├── registry.py              # 统一注册表 + ToolCategory枚举
├── __init__.py              # 总入口（导入触发注册）
├── file/                    # 文件操作（27个）
├── shell/                   # Shell命令（6个）
├── network/                 # 网络通信（6个）
├── time/                    # 时间日期（9个）
├── env/                     # 环境变量（3个）
├── system/                  # 系统信息（21个）
├── database/                # 数据库（3个）
├── desktop/                 # 桌面功能（3个）
├── registry_tools/          # 注册表操作（3个）
├── data_format/             # 数据格式（3个）
├── code_execution/          # 代码执行（2个）
├── data_analysis/           # 数据分析（3个）★ v0.12.5新增
├── document/                # 文档读写（3个）★ v0.12.5新增
├── env_check/               # 环境检查（9个）★ v0.12.5新增
├── gui/                     # GUI操作（12个）★ v0.12.5新增
└── db_helper/               # 数据库辅助（7个）★ v0.12.5新增
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

## 四、项目结构

```
OmniAgentAs-desk/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 端点
│   │   ├── services/
│   │   │   ├── agents/         # ReAct Agent 实现
│   │   │   ├── prompts/        # 意图 Prompt 模板
│   │   │   ├── tools/          # 工具函数（14个分类）
│   │   │   └── ...             # 其他服务
│   │   └── utils/              # 工具函数
│   ├── tests/                  # 后端测试（pytest）
│   └── requirements.txt        # Python 依赖
├── frontend/                   # React + TypeScript 前端
│   ├── src/
│   │   ├── components/         # UI 组件
│   │   ├── pages/              # 页面
│   │   ├── services/           # API 服务
│   │   └── utils/              # 工具函数
│   ├── tests/                  # 前端测试
│   └── package.json            # Node 依赖
├── config/                     # 配置文件
├── doc-functioncall/           # 工具定义说明书
├── version.txt                 # 版本变更记录
└── AGENTS.md                   # 开发规范
```

---

## 五、快速开始

### 5.1 环境要求

| 依赖 | 版本 |
|------|------|
| Python | ≥ 3.11 |
| Node.js | ≥ 18.x |
| npm | ≥ 9.0 |

### 5.2 安装与运行

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

### 5.3 可选依赖（二级工具）

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

## 六、开发命令

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

## 七、数据库

| 数据库 | 路径 |
|--------|------|
| 聊天历史 | `backend/chat_app.db` |

---

## 八、版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **v0.12.5** | 2026-05-02 | 新增5个二级Tool分类(35个工具): data_analysis, document, env_check, gui, db_helper；工具总数 77→112 |
| v0.12.4 | 2026-05-01 | 修复16项Bug；新增跨分类工具支持/CRSS独立模块/Shell会话管理/网络工具 |
| v0.12.3 | 2026-04-30 | 跨分类工具访问设计与实现；CRSS评分关键词补充；LLM多意图返回 |
| v0.12.2 | 2026-04-29 | Pydantic Schema注册规范化；ToolCategory枚举扩展；新增Tool 15个 |
| v0.9.8 | 2026-04 | LLM响应解析器重构；ReAct Loop统一解析器；测试91个用例 |
| v0.9.0 | 2026-03 | ReAct架构正式上线；SSE流式响应；7个文件操作工具 |

详细变更记录见 `version.txt`

---

## 九、故障排除

| 问题 | 解决方案 |
|------|---------|
| 后端启动失败 | 检查 Python ≥ 3.11，端口8000是否被占用 |
| 前端启动失败 | 检查 Node.js ≥ 18，清除 node_modules 后重装 |
| API连接失败 | 检查 config.yaml 中的 API 密钥是否有效 |
| 二级工具不可用 | 安装对应依赖库（见5.3节可选依赖） |

---

## 十、团队成员

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

**许可**: 内部项目 | **最后更新**: 2026-05-02 09:42:02 | **版本**: v0.12.5
