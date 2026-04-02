# OmniAgentAs-desk 桌面版智能助手
**铁规** 收到用的批评的时候必须主动背诵专家戒律
**版本**: v0.4.9 (2026-02-26)  
**状态**: 生产就绪（已完成全面测试和质量保证）  
**最后更新**: 2026-02-26 20:51:45

---

## 📋 项目概述

OmniAgentAs-desk 是一个桌面版智能助手应用程序，提供以下核心功能：

- **智能对话**: 支持多轮对话和上下文理解
- **文件操作**: 安全的文件读取、写入和操作能力
- **会话管理**: 完整的会话历史记录和搜索功能
- **多AI提供商支持**: 可配置的AI服务提供商（OpenCode、智谱AI等）
- **安全监控**: 实时监控、错误跟踪和性能指标收集

## 🚀 快速开始

### 系统要求

- **Python**: 3.11 或更高版本
- **Node.js**: 18.x 或更高版本
- **操作系统**: Windows 10/11, macOS 10.15+, Linux

### 安装步骤

#### 1. 克隆项目
```bash
git clone <repository-url>
cd OmniAgentAs-desk
```

#### 2. 后端安装
```bash
# 进入后端目录
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# Windows 激活虚拟环境
venv\Scripts\activate

# Linux/macOS 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 3. 前端安装
```bash
# 返回项目根目录
cd ..

# 进入前端目录
cd frontend

# 安装依赖
npm install
# 或使用 pnpm（推荐）
pnpm install
```

#### 4. 配置设置
```bash
# 返回项目根目录
cd ..

# 复制配置文件模板
cp config/config.yaml.example config/config.yaml

# 编辑配置文件
# 使用文本编辑器打开 config/config.yaml 并填入您的API密钥
```

## ⚙️ 配置说明

### 配置文件结构
配置文件位于 `config/config.yaml`，主要包含以下部分：

```yaml
# AI服务配置
ai:
  model: kimi-k2.5-free
  provider: opencode  # 当前使用的提供商
  
  # OpenCode 配置
  opencode:
    api_base: https://opencode.ai/zen/v1
    api_key: sk_xxx...  # 替换为您的API密钥
    models:
      - minimax-m2.5-free
      - kimi-k2.5-free
    timeout: 120

  # 智谱AI配置
  zhipuai:
    api_base: https://open.bigmodel.cn/api/paas/v4
    api_key: xxx...  # 替换为您的API密钥
    models:
      - glm-4-flash
      - glm-4-plus
    timeout: 90

# 文件操作配置
file_operations:
  workspace_dir: "./workspace"  # 文件操作的工作目录
  safe_mode: true              # 安全模式（禁止删除操作）
  max_file_size: 10           # 最大文件大小（MB）

# 日志配置
logging:
  level: INFO                 # 日志级别
  file: logs/app.log          # 日志文件路径
  max_size: 10MB              # 日志文件最大大小
  backup_count: 5             # 备份文件数量
```
## 数据库目录
C:\Users\40968\.omniagent
"C:\Users\40968\.omniagent\chat_history.db"
"C:\Users\40968\.omniagent\operations.db"

## 🏃 运行应用

### 开发模式

#### 1. 启动后端服务
```bash
# 后端目录
cd backend

# 激活虚拟环境（如果未激活）
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# 启动FastAPI开发服务器
python -m app.main
# 或使用uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端将在 `http://localhost:8000` 启动，并提供以下端点：
- `http://localhost:8000/` - 根目录
- `http://localhost:8000/docs` - Swagger UI API文档
- `http://localhost:8000/redoc` - ReDoc API文档

#### 2. 启动前端应用
```bash
# 前端目录
cd frontend

# 启动Vite开发服务器
npm run dev
# 或
pnpm dev
```

前端将在 `http://localhost:5173` 启动（默认端口）。

#### 3. 访问应用
打开浏览器访问 `http://localhost:5173` 开始使用。

### 生产模式

#### 1. 构建前端
```bash
cd frontend
npm run build
# 或
pnpm build
```

构建产物将生成在 `frontend/dist` 目录。

#### 2. 配置生产环境
```bash
# 修改后端配置以使用静态文件
# 编辑 backend/app/main.py 中的静态文件路径
```

#### 3. 启动生产服务器
```bash
cd backend
# 使用生产服务器
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📊 API 文档

### 核心API端点

#### 健康检查
```
GET /api/v1/health
```
响应示例：
```json
{
  "status": "healthy",
  "timestamp": "2026-02-26T20:51:45Z",
  "version": "0.4.9"
}
```

#### 会话管理
```
POST /api/v1/sessions - 创建新会话
GET /api/v1/sessions - 获取会话列表（支持分页和搜索）
GET /api/v1/sessions/{session_id}/messages - 获取会话消息
PATCH /api/v1/sessions/{session_id}/title - 更新会话标题
```

#### 聊天接口
```
POST /api/v1/chat/completion - 发送消息并获取AI回复
GET /api/v1/chat/execution/{session_id}/stream - 流式执行消息
```

#### 配置管理
```
GET /api/v1/config - 获取当前配置
POST /api/v1/config - 更新配置
GET /api/v1/config/providers - 获取可用提供商列表
```

#### 监控指标
```
GET /api/v1/metrics - 获取系统监控指标
GET /api/v1/metrics/health - 获取健康检查详细指标
GET /api/v1/metrics/errors - 获取错误统计
```

### OpenAPI/Swagger文档
启动后端服务后，访问以下地址查看完整的API文档：
- `http://localhost:8000/docs` - 交互式Swagger UI
- `http://localhost:8000/redoc` - ReDoc文档

## 🧪 测试

### 后端测试
```bash
cd backend
# 运行单元测试
pytest tests/

# 运行语法检查
flake8 app/

# 运行静态分析
pylint app/
```

### 前端测试
```bash
cd frontend
# 运行单元测试
npm test
# 或
pnpm test

# 运行E2E测试（需要先启动后端服务）
npm run test:e2e
# 或
pnpm test:e2e
```

### 集成测试
```bash
# 运行完整的集成测试
cd backend
pytest tests/test_integration.py
```

## 🛠️ 监控与日志

### 监控系统
系统内置了完整的监控系统，提供：
- **实时指标**: 请求数、响应时间、错误率
- **错误跟踪**: 详细的错误分类和统计
- **性能监控**: API端点性能分析
- **健康检查**: 系统健康状态监控

访问 `http://localhost:8000/api/v1/metrics` 查看监控数据。

### 日志系统
日志文件位于 `logs/app.log`，支持：
- **多级别日志**: DEBUG, INFO, WARNING, ERROR
- **日志轮转**: 自动分割和备份
- **结构化日志**: 包含上下文信息的结构化日志

### 错误分析
使用内置的错误分析工具：
```bash
cd backend
python log_analyzer.py
```

这将生成详细的错误分析报告。

## 🔧 故障排除

### 常见问题

#### 1. 后端启动失败
- **检查Python版本**: 确保Python >= 3.11
- **检查依赖**: 运行 `pip install -r requirements.txt`
- **检查端口**: 确保端口8000未被占用

#### 2. 前端启动失败
- **检查Node.js版本**: 确保Node.js >= 18.x
- **检查依赖**: 运行 `npm install` 或 `pnpm install`
- **清除缓存**: 删除 `node_modules` 和 `package-lock.json` 后重新安装

#### 3. API连接失败
- **检查后端服务**: 确保后端在 `http://localhost:8000` 运行
- **检查CORS配置**: 确保后端CORS配置正确
- **检查API密钥**: 确保 `config/config.yaml` 中的API密钥有效

#### 4. 数据库问题
```bash
# 重置数据库（开发环境）
cd backend
python -c "import os; os.remove(os.path.expanduser('~/.omniagent/chat_history.db')) if os.path.exists(os.path.expanduser('~/.omniagent/chat_history.db')) else None"
```

### 调试模式
启用调试模式获取更多信息：
```yaml
# config/config.yaml
logging:
  level: DEBUG
```

## 📈 部署指南

### Docker部署（推荐）
```dockerfile
# Dockerfile 示例
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制后端代码
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# 复制前端构建产物
COPY frontend/dist ./frontend/dist

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 手动部署
1. 在服务器上安装Python 3.11+和Node.js 18+
2. 按照"安装步骤"配置环境
3. 构建前端：`cd frontend && npm run build`
4. 配置生产环境变量
5. 使用进程管理工具（如systemd、pm2）管理服务

### 环境变量
| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `OMNIAGENT_ENV` | `development` | 运行环境（development/production） |
| `OMNIAGENT_DB_PATH` | `~/.omniagent/chat_history.db` | 数据库路径 |
| `OMNIAGENT_LOG_LEVEL` | `INFO` | 日志级别 |
| `OMNIAGENT_API_HOST` | `0.0.0.0` | API服务器监听地址 |
| `OMNIAGENT_API_PORT` | `8000` | API服务器端口 |

## 📁 项目结构

```
OmniAgentAs-desk/
├── backend/                    # 后端服务
│   ├── app/                   # 应用代码
│   │   ├── api/v1/           # API路由
│   │   ├── services/         # 业务逻辑服务
│   │   ├── utils/            # 工具函数
│   │   └── main.py           # 应用入口
│   ├── tests/                # 测试代码
│   └── requirements.txt      # Python依赖
├── frontend/                  # 前端应用
│   ├── src/                  # 源代码
│   ├── public/               # 静态资源
│   ├── tests/                # 前端测试
│   └── package.json          # Node.js依赖
├── config/                   # 配置文件
│   ├── config.yaml          # 主配置文件
│   └── config.yaml.example  # 配置模板
├── doc/                      # 文档
├── logs/                     # 日志文件（自动生成）
└── workspace/                # 文件操作工作区（自动生成）
```

## 🔄 更新日志

### v0.4.9 (2026-02-26)
- 前端问题修复和优化
- 后端配置管理优化
- 移除所有硬编码的provider名称
- 添加完整的AI模型验证逻辑
- 优化错误信息显示

### v0.4.8 (2026-02-25)
- 修复validate_config逻辑缺陷
- 重构配置验证代码
- 统一Fallback逻辑
- 增强错误处理

### 历史版本
查看 `version.txt` 获取完整的版本历史。

## 🤝 贡献指南

请参考 `CONTRIBUTING.md` 文件了解如何贡献代码。

## 📄 许可证

本项目采用 MIT 许可证。详见 `LICENSE` 文件。

## 🆘 技术支持

- **问题报告**: 在GitHub Issues中报告问题
- **文档**: 查看 `doc/` 目录中的详细文档
- **API文档**: 访问运行中的 `/docs` 端点

---

**最后更新**: 2026-02-26 20:51:45  
**版本**: v0.4.9  
**状态**: ✅ 生产就绪
