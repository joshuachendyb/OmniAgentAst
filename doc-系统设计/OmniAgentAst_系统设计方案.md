# OmniAgentAst. 系统设计方案

**【版本】v1.0 : 2026-02-15 10:37:26 : 创建文档**

---

## 1. 项目概述

## 1. 项目概述

### 1.1 项目背景

现有AI_OSShell_v2.py存在严重的安全和架构问题：
- 硬编码API密钥，存在泄露风险
- 任意命令执行，系统安全性极低
- 单用户架构，无法支持多用户
- 缺乏扩展性，工具难以动态添加

### 1.2 项目目标

构建一个企业级、安全、可扩展的AI Agent操作系统：

| 目标维度 | 现有版本 | 新版本目标 |
|---------|---------|-----------|
| **安全性** | 🔴 危险 | 🟢 企业级安全（沙箱、权限、审计） |
| **可扩展性** | 🔴 硬编码 | 🟢 插件化架构（动态加载工具） |
| **多用户** | 🔴 单用户 | 🟢 多租户（RBAC权限系统） |
| **多模型** | 🔴 仅Claude | 🟢 多模型智能路由 |
| **多模态** | 🔴 仅文本 | 🟢 图像+语音+文本 |
| **客户端** | 🔴 Web单端 | 🟢 Web+桌面+移动端 |
| **可观测性** | 🔴 print输出 | 🟢 完整监控+审计+告警 |

### 1.3 核心价值主张

**让AI Agent从"玩具"变成"生产工具"**

- **对企业**: 安全合规、权限可控、审计完备
- **对开发者**: 插件生态、API丰富、易于扩展
- **对终端用户**: 自然交互、多客户端、智能高效

---

## 2. 系统架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           接入层 (Access Layer)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Web App    │  │   桌面客户端  │  │  移动端App   │  │   API接口    │   │
│  │  (React/Vue) │  │  (Electron)  │  │  (Flutter)   │  │  (REST/WS)   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
└─────────┼────────────────┼────────────────┼────────────────┼─────────────┘
          │                │                │                │
          └────────────────┴────────────────┴────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        网关层 (Gateway Layer)                                │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         FastAPI Gateway                               │  │
│  │  ├─ 身份认证 (JWT + OAuth2)                                          │  │
│  │  ├─ 权限控制 (RBAC: 管理员/用户/访客)                                 │  │
│  │  ├─ 限流保护 (Rate Limiting: 100 req/min)                            │  │
│  │  ├─ 日志审计 (结构化日志输出)                                         │  │
│  │  └─ 请求路由 (动态路由到Agent服务)                                    │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       核心服务层 (Core Services)                              │
│                                                                             │
│  ┌─────────────────────────┐  ┌─────────────────────────┐                  │
│  │     Agent调度服务        │  │      任务队列服务        │                  │
│  │  ├─ 任务生命周期管理     │  │  ├─ Redis任务队列       │                  │
│  │  ├─ 多Agent负载均衡      │  │  ├─ Celery任务执行      │                  │
│  │  ├─ 资源隔离（容器化）    │  │  ├─ 任务状态追踪        │                  │
│  │  └─ 故障转移            │  │  └─ 死信队列处理        │                  │
│  └─────────────────────────┘  └─────────────────────────┘                  │
│                                                                             │
│  ┌─────────────────────────┐  ┌─────────────────────────┐                  │
│  │     ReAct引擎服务        │  │      模型路由服务        │                  │
│  │  ├─ 意图识别模块        │  │  ├─ 多模型支持          │                  │
│  │  ├─ 任务规划模块        │  │  ├─ 智能路由策略        │                  │
│  │  ├─ 执行监控模块        │  │  ├─ 失败自动切换        │                  │
│  │  ├─ 异常恢复模块        │  │  └─ 成本优化            │                  │
│  │  └─ 反思优化模块        │  │                         │                  │
│  └─────────────────────────┘  └─────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      工具层 (Tool Layer) - 插件化架构                          │
│                                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐               │
│  │   系统工具箱     │ │   应用工具箱     │ │   网络工具箱     │               │
│  │  ├─ file_ops    │ │  ├─ browser     │ │  ├─ search      │               │
│  │  ├─ process_mgr │ │  ├─ office      │ │  ├─ download    │               │
│  │  ├─ screenshot  │ │  ├─ ide         │ │  ├─ api_call    │               │
│  │  ├─ system_info │ │  ├─ media       │ │  └─ webhook     │               │
│  │  └─ registry    │ │  └─ database    │ │                 │               │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘               │
│                                                                             │
│  工具执行沙箱:                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Docker容器 / Firejail / Windows Sandbox                           │   │
│  │   - 文件系统隔离 (只暴露白名单目录)                                   │   │
│  │   - 网络隔离 (出站白名单模式)                                        │   │
│  │   - 资源限制 (CPU≤1核, 内存≤512MB)                                   │   │
│  │   - 时间限制 (单次执行≤60秒)                                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      数据层 (Data Layer)                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  PostgreSQL  │  │    Redis     │  │    MinIO     │  │ Elasticsearch│   │
│  │  (主数据库)   │  │  (缓存/队列)  │  │  (文件存储)   │  │   (搜索)      │   │
│  │  - 用户数据   │  │  - Session   │  │  - 截图      │  │  - 日志搜索   │   │
│  │  - 任务历史   │  │  - 任务队列  │  │  - 附件      │  │  - 全文检索   │   │
│  │  - 审计日志   │  │  - 缓存      │  │  - 备份      │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 服务拆分架构

采用微服务架构，核心服务：

```
ai-agent-os/
├── services/
│   ├── gateway/              # API网关服务
│   │   ├── main.py
│   │   ├── auth/            # 认证模块
│   │   ├── middleware/      # 中间件（限流、日志）
│   │   └── routes/          # 路由配置
│   │
│   ├── agent-core/          # Agent核心服务
│   │   ├── react_engine/    # ReAct引擎
│   │   ├── planner/         # 任务规划器
│   │   ├── executor/        # 执行器
│   │   └── recovery/        # 故障恢复
│   │
│   ├── tool-service/        # 工具服务
│   │   ├── sandbox/         # 沙箱管理
│   │   ├── plugins/         # 插件目录
│   │   └── registry.py      # 插件注册表
│   │
│   ├── model-router/        # 模型路由服务
│   │   ├── router.py        # 路由逻辑
│   │   ├── providers/       # 各模型提供商
│   │   └── fallback.py      # 故障转移
│   │
│   └── task-scheduler/      # 任务调度服务
│       ├── queue/           # 队列管理
│       ├── worker.py        # Celery工作进程
│       └── monitor.py       # 任务监控
│
├── clients/
│   ├── web/                 # Web前端（React）
│   ├── desktop/             # 桌面端（Electron）
│   └── mobile/              # 移动端（Flutter）
│
└── shared/
    ├── models/              # 数据模型
    ├── schemas/             # Pydantic模型
    ├── constants/           # 常量定义
    └── utils/               # 工具函数
```

---

## 3. 详细技术方案

### 3.1 后端技术栈

| 组件 | 技术选型 | 版本 | 选型理由 |
|------|---------|------|----------|
| **Web框架** | FastAPI | ≥0.104 | 异步支持、自动生成OpenAPI文档、类型提示完善 |
| **数据库** | PostgreSQL | 15+ | ACID事务、JSONB支持、全文检索 |
| **ORM** | SQLAlchemy 2.0 | ≥2.0 | 类型安全、异步支持、成熟稳定 |
| **缓存** | Redis | 7+ | 高性能、Pub/Sub、分布式锁 |
| **任务队列** | Celery + Redis | 5.3+ | 成熟稳定、支持定时任务、监控完善 |
| **消息队列** | RabbitMQ | 3.12+ | 可靠消息传递、死信队列 |
| **认证** | JWT + OAuth2 | - | 无状态、标准化、支持第三方登录 |
| **文件存储** | MinIO | 2024+ | S3兼容、高性能、私有化部署 |
| **监控** | Prometheus + Grafana | - | 云原生标准、可视化强大 |
| **日志** | ELK Stack | 8.x+ | 集中式日志管理、全文检索 |
| **容器** | Docker + Docker Compose | 24+ | 标准化部署、环境隔离 |

### 3.2 前端技术栈

| 客户端 | 技术栈 | 选型理由 |
|--------|--------|----------|
| **Web** | React 18 + TypeScript + Ant Design | 生态丰富、类型安全、企业级UI |
| **桌面** | Electron + React | 跨平台、Web技术栈复用 |
| **移动端** | Flutter | 跨平台、性能接近原生、UI一致 |

### 3.3 AI模型层设计

#### 3.3.1 多模型路由策略

```python
# model_router/config.py
MODEL_CONFIG = {
    "claude-sonnet-4-20250514": {
        "provider": "anthropic",
        "api_key_env": "CLAUDE_API_KEY",
        "max_tokens": 4096,
        "temperature": 0.7,
        "strengths": ["工具调用", "复杂推理", "长上下文"],
        "cost_per_1k_tokens": {"input": 0.003, "output": 0.015},
        "priority": 1
    },
    "gpt-4-turbo": {
        "provider": "openai",
        "api_key_env": "OPENAI_API_KEY",
        "max_tokens": 4096,
        "temperature": 0.7,
        "strengths": ["代码生成", "知识问答"],
        "cost_per_1k_tokens": {"input": 0.01, "output": 0.03},
        "priority": 2
    },
    "gemini-1.5-pro": {
        "provider": "google",
        "api_key_env": "GEMINI_API_KEY",
        "max_tokens": 8192,
        "temperature": 0.7,
        "strengths": ["多模态", "超长上下文", "低成本"],
        "cost_per_1k_tokens": {"input": 0.0005, "output": 0.0015},
        "priority": 3
    },
    "llama3-70b-local": {
        "provider": "local",
        "endpoint": "http://localhost:11434",
        "max_tokens": 4096,
        "temperature": 0.7,
        "strengths": ["隐私保护", "离线使用", "无成本"],
        "cost_per_1k_tokens": {"input": 0, "output": 0},
        "priority": 4
    }
}

class SmartModelRouter:
    """智能模型路由器"""
    
    def __init__(self):
        self.models = self._load_models()
        self.health_status = {}
    
    async def route(self, task: Task) -> ModelConfig:
        """根据任务特征选择最佳模型"""
        
        # 1. 基于任务特征匹配
        if task.has_image_input:
            return self._select_by_capability("多模态")
        
        if task.requires_tool_calls:
            return self._select_by_capability("工具调用")
        
        if task.is_code_related:
            return self._select_by_capability("代码生成")
        
        if task.is_sensitive:
            return self._select_local_model()  # 敏感数据用本地模型
        
        # 2. 基于成本优化（如果用户设置成本限制）
        if task.user.cost_sensitive:
            return self._select_by_cost()
        
        # 3. 默认：优先级最高的可用模型
        return self._select_by_priority()
    
    async def _select_by_capability(self, capability: str) -> ModelConfig:
        """根据能力选择模型"""
        candidates = [
            m for m in self.models 
            if capability in m.strengths and self._is_healthy(m)
        ]
        return sorted(candidates, key=lambda x: x.priority)[0]
```

#### 3.3.2 故障转移机制

```python
class ModelFallback:
    """模型故障转移处理"""
    
    async def call_with_fallback(
        self, 
        task: Task, 
        primary_model: str,
        max_retries: int = 3
    ) -> ModelResponse:
        """带故障转移的模型调用"""
        
        models_to_try = self._get_fallback_chain(primary_model)
        
        for model in models_to_try:
            for attempt in range(max_retries):
                try:
                    response = await self._call_model(model, task)
                    return response
                except RateLimitError:
                    # 速率限制，切换到备用模型
                    logger.warning(f"{model} rate limited, trying fallback")
                    break
                except ModelUnavailableError:
                    # 模型不可用，标记并继续
                    await self._mark_unhealthy(model)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)  # 指数退避
        
        raise AllModelsFailed("所有模型均不可用")
```

---

## 4. 安全架构设计

### 4.1 零信任安全模型

```
原则：永不信任，始终验证

┌─────────────────────────────────────────────────────────────────┐
│                         零信任架构                               │
├─────────────────────────────────────────────────────────────────┤
│  1. 身份验证层 (Identity)                                        │
│     ├─ 多因素认证 (MFA)                                          │
│     ├─ 单点登录 (SSO)                                            │
│     └─ 会话管理 (短有效期Token)                                   │
│                                                                  │
│  2. 权限控制层 (Authorization)                                   │
│     ├─ RBAC (基于角色的访问控制)                                 │
│     ├─ ABAC (基于属性的访问控制)                                 │
│     └─ 最小权限原则                                              │
│                                                                  │
│  3. 执行隔离层 (Isolation)                                       │
│     ├─ 沙箱执行环境                                              │
│     ├─ 资源限制 (CPU/内存/IO)                                    │
│     └─ 网络隔离                                                  │
│                                                                  │
│  4. 审计监控层 (Audit)                                           │
│     ├─ 全量操作日志                                              │
│     ├─ 实时异常检测                                              │
│     └─ 合规报告                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 身份认证体系

```python
# auth/models.py
from enum import Enum

class UserRole(Enum):
    SUPER_ADMIN = "super_admin"      # 系统管理员
    ADMIN = "admin"                   # 租户管理员
    POWER_USER = "power_user"         # 高级用户
    USER = "user"                     # 普通用户
    GUEST = "guest"                   # 访客

class Permission(Enum):
    # 系统级权限
    SYSTEM_EXECUTE = "system:execute"       # 执行系统命令
    SYSTEM_ADMIN = "system:admin"           # 系统管理
    
    # 文件级权限
    FILE_READ = "file:read"                 # 读取文件
    FILE_WRITE = "file:write"               # 写入文件
    FILE_DELETE = "file:delete"             # 删除文件
    FILE_EXECUTE = "file:execute"           # 执行文件
    
    # 网络级权限
    NETWORK_HTTP = "network:http"           # HTTP请求
    NETWORK_HTTPS = "network:https"         # HTTPS请求
    NETWORK_DOWNLOAD = "network:download"   # 下载文件
    
    # 应用级权限
    APP_BROWSER = "app:browser"             # 浏览器控制
    APP_OFFICE = "app:office"               # Office控制
    APP_IDE = "app:ide"                     # IDE控制
    
    # 工具级权限
    TOOL_SANDBOX_BYPASS = "tool:sandbox_bypass"  # 绕过沙箱

# 角色权限映射
ROLE_PERMISSIONS = {
    UserRole.SUPER_ADMIN: [p for p in Permission],  # 全部权限
    
    UserRole.ADMIN: [
        Permission.SYSTEM_EXECUTE,
        Permission.FILE_READ, Permission.FILE_WRITE, Permission.FILE_DELETE,
        Permission.NETWORK_HTTP, Permission.NETWORK_HTTPS, Permission.NETWORK_DOWNLOAD,
        Permission.APP_BROWSER, Permission.APP_OFFICE, Permission.APP_IDE,
    ],
    
    UserRole.POWER_USER: [
        Permission.FILE_READ, Permission.FILE_WRITE,
        Permission.NETWORK_HTTP, Permission.NETWORK_HTTPS,
        Permission.APP_BROWSER, Permission.APP_OFFICE,
    ],
    
    UserRole.USER: [
        Permission.FILE_READ,
        Permission.NETWORK_HTTP, Permission.NETWORK_HTTPS,
        Permission.APP_BROWSER,
    ],
    
    UserRole.GUEST: [
        Permission.FILE_READ,
        Permission.NETWORK_HTTPS,
    ],
}
```

### 4.3 沙箱执行环境

#### 4.3.1 Docker沙箱配置

```dockerfile
# sandbox/Dockerfile.sandbox
FROM python:3.11-slim

# 创建非root用户
RUN useradd -m -s /bin/bash sandboxuser

# 安装必要工具（最小化）
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /workspace

# 复制受限Python环境
COPY sandbox/python-restricted /usr/local/bin/python-restricted

# 切换用户
USER sandboxuser

# 资源限制通过docker run参数控制
# --memory=512m --cpus=1.0 --pids-limit=100
```

```python
# sandbox/docker_manager.py
import docker
from dataclasses import dataclass

@dataclass
class SandboxConfig:
    memory_limit: str = "512m"          # 内存限制
    cpu_quota: int = 100000             # CPU限制（100% = 1核）
    cpu_period: int = 100000
    pids_limit: int = 100               # 进程数限制
    timeout: int = 60                   # 执行超时（秒）
    network_mode: str = "none"          # 默认无网络
    read_only: bool = True              # 只读根文件系统
    
    # 允许挂载的目录（白名单）
    allowed_mounts: List[str] = None

class DockerSandbox:
    """Docker沙箱管理器"""
    
    def __init__(self):
        self.client = docker.from_env()
        self.image = "ai-agent-sandbox:latest"
    
    async def execute(
        self, 
        command: str, 
        config: SandboxConfig = None,
        user_id: str = None
    ) -> SandboxResult:
        """在沙箱中执行命令"""
        
        config = config or SandboxConfig()
        
        # 生成唯一的容器名
        container_name = f"sandbox-{user_id}-{uuid.uuid4().hex[:8]}"
        
        try:
            container = self.client.containers.run(
                image=self.image,
                command=command,
                name=container_name,
                detach=True,
                mem_limit=config.memory_limit,
                cpu_quota=config.cpu_quota,
                cpu_period=config.cpu_period,
                pids_limit=config.pids_limit,
                network_mode=config.network_mode,
                read_only=config.read_only,
                volumes=self._prepare_volumes(config.allowed_mounts),
                security_opt=["no-new-privileges:true"],  # 禁止提权
                cap_drop=["ALL"],  # 丢弃所有Capability
                cap_add=["CHOWN", "SETUID", "SETGID"],  # 最小权限
            )
            
            # 等待执行完成或超时
            result = container.wait(timeout=config.timeout)
            
            # 获取输出
            stdout = container.logs(stdout=True, stderr=False).decode('utf-8')
            stderr = container.logs(stdout=False, stderr=True).decode('utf-8')
            
            return SandboxResult(
                exit_code=result['StatusCode'],
                stdout=stdout,
                stderr=stderr,
                duration=result.get('Running', 0)
            )
            
        except docker.errors.ContainerError as e:
            return SandboxResult(
                exit_code=e.exit_status,
                stderr=str(e),
                error="Container execution failed"
            )
        except Exception as e:
            return SandboxResult(
                exit_code=-1,
                error=str(e)
            )
        finally:
            # 清理容器
            try:
                container = self.client.containers.get(container_name)
                container.remove(force=True)
            except:
                pass
```

#### 4.3.2 命令白名单与过滤

```python
# security/command_filter.py
import re
from typing import List, Tuple

class CommandFilter:
    """命令过滤器"""
    
    # 绝对禁止的危险命令（黑名单）
    DANGEROUS_PATTERNS = [
        r"\brm\s+-rf\s+/",
        r"\bmkfs\.",
        r"\bdd\s+if=",
        r"\b:(){ :|:& };:",  # Fork炸弹
        r"\bformat\s+",
        r"\bdel\s+/f\s+/s\s+/q\s+c:\\",
        r"\breg\s+delete\s+hk",
        r"\bnet\s+user\s+.*\s+/add",
        r"\bpowershell\s+-enc",
        r"\bcmd\s+/c\s+.*\|\s*sh",
    ]
    
    # 允许的基础命令（白名单）
    ALLOWED_COMMANDS = [
        # 文件操作
        (r"^ls\s+(-[a-z]+\s+)?[^;&|]*$", "list_files"),
        (r"^dir(\s+[a-zA-Z]:)?$", "list_files_win"),
        (r"^cat\s+[\w\./\-]+$", "read_file"),
        (r"^type\s+[\w\\\-]+$", "read_file_win"),
        (r"^echo\s+.+$", "echo"),
        (r"^pwd$", "print_working_directory"),
        (r"^cd\s+[\w/\-]+$", "change_directory"),
        
        # 系统信息
        (r"^uname\s+-[a]$", "system_info"),
        (r"^whoami$", "current_user"),
        (r"^date$", "current_date"),
        
        # 网络（限制）
        (r"^curl\s+-I\s+https?://[\w\./-]+$", "check_url"),
        (r"^ping\s+-c\s+\d+\s+[\w\.]+$", "ping"),
        
        # 应用程序
        (r"^notepad(\s+\w+)?$", "open_notepad"),
        (r"^calc$", "open_calculator"),
        (r"^explorer(\s+\w:)?$", "open_explorer"),
    ]
    
    def __init__(self, user_role: UserRole):
        self.role = user_role
        self.allowed = self._get_allowed_commands()
    
    def validate(self, command: str) -> Tuple[bool, str]:
        """
        验证命令是否允许执行
        返回: (is_valid, reason)
        """
        command = command.strip()
        
        # 1. 黑名单检查
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return False, f"命令包含危险操作模式: {pattern}"
        
        # 2. 危险字符检查
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')']
        if any(char in command for char in dangerous_chars):
            return False, "命令包含危险字符（分号、管道等）"
        
        # 3. 白名单检查
        for pattern, cmd_type in self.allowed:
            if re.match(pattern, command):
                return True, f"允许执行: {cmd_type}"
        
        # 4. 不在白名单中
        return False, "命令不在白名单中，请联系管理员"
    
    async def validate_with_confirmation(
        self, 
        command: str, 
        user: User,
        require_admin: bool = False
    ) -> Tuple[bool, str]:
        """需要确认的验证（敏感操作）"""
        
        is_valid, reason = self.validate(command)
        if not is_valid:
            return False, reason
        
        # 检查是否需要管理员确认
        if require_admin and self.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            # 发送确认请求给管理员
            confirmation_id = await self._request_admin_confirmation(
                user=user,
                command=command,
                reason=reason
            )
            return False, f"需要管理员确认，请求ID: {confirmation_id}"
        
        return True, reason
```

### 4.4 审计与合规

```python
# audit/models.py
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
import uuid

class AuditEvent(BaseModel):
    """审计事件模型"""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # 用户信息
    user_id: str
    user_name: str
    user_role: UserRole
    session_id: str
    ip_address: str
    user_agent: str
    
    # 操作信息
    action_type: str           # 操作类型
    action_details: Dict[str, Any]  # 操作详情
    resource_type: str         # 资源类型（文件/命令/窗口等）
    resource_id: Optional[str] # 资源标识
    
    # 执行信息
    tool_name: Optional[str]   # 使用的工具
    command: Optional[str]     # 执行的命令
    parameters: Optional[Dict] # 参数
    
    # 结果信息
    status: str                # success / failure / blocked
    result_summary: str        # 结果摘要
    error_message: Optional[str]
    
    # 安全信息
    risk_score: int = Field(ge=0, le=100)  # 风险评分
    security_flags: List[str] = []         # 安全标记
    
    # 证据留存
    screenshot_url: Optional[str]     # 操作截图
    recording_url: Optional[str]      # 录屏文件
    command_output: Optional[str]     # 命令输出
    
    class Config:
        indexes = [
            [("timestamp", -1)],           # 时间倒序索引
            [("user_id", 1), ("timestamp", -1)],  # 用户时间索引
            [("action_type", 1)],          # 操作类型索引
            [("risk_score", -1)],          # 风险评分索引
        ]

class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, db: Database, storage: FileStorage):
        self.db = db
        self.storage = storage
        self.alert_threshold = 70  # 风险评分阈值
    
    async def log_event(self, event: AuditEvent):
        """记录审计事件"""
        
        # 1. 保存到数据库
        await self.db.audit_events.insert_one(event.dict())
        
        # 2. 高风险操作实时告警
        if event.risk_score >= self.alert_threshold:
            await self._send_security_alert(event)
        
        # 3. 发送到日志系统（ELK）
        await self._send_to_elk(event)
        
        # 4. 更新用户行为画像
        await self._update_user_profile(event)
    
    async def _send_security_alert(self, event: AuditEvent):
        """发送安全告警"""
        alert = {
            "level": "HIGH" if event.risk_score >= 90 else "MEDIUM",
            "title": f"高风险操作告警: {event.action_type}",
            "description": f"用户 {event.user_name} 执行了高风险操作",
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "details": event.dict()
        }
        
        # 发送邮件/短信/钉钉
        await notification_service.send_alert(alert)
    
    async def generate_compliance_report(
        self, 
        start_date: datetime, 
        end_date: datetime,
        user_id: Optional[str] = None
    ) -> ComplianceReport:
        """生成合规报告"""
        
        query = {
            "timestamp": {"$gte": start_date, "$lte": end_date}
        }
        if user_id:
            query["user_id"] = user_id
        
        events = await self.db.audit_events.find(query).to_list(None)
        
        return ComplianceReport(
            period=(start_date, end_date),
            total_events=len(events),
            high_risk_events=len([e for e in events if e.risk_score >= 70]),
            failed_events=len([e for e in events if e.status == "failure"]),
            top_users=self._get_top_active_users(events),
            top_actions=self._get_top_actions(events),
            security_incidents=self._identify_security_incidents(events),
            generated_at=datetime.utcnow()
        )
```

---

## 5. 数据库设计

### 5.1 ER图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              数据库实体关系图                                 │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
    │    users     │         │   sessions   │         │    tasks     │
    ├──────────────┤         ├──────────────┤         ├──────────────┤
    │ id (PK)      │◄────────│ user_id (FK) │         │ id (PK)      │
    │ username     │         │ id (PK)      │         │ user_id (FK) │
    │ email        │         │ token        │         │ session_id   │
    │ password_hash│         │ created_at   │         │ status       │
    │ role         │         │ expires_at   │         │ goal         │
    │ created_at   │         │ ip_address   │         │ result       │
    │ is_active    │         └──────────────┘         │ started_at   │
    └──────────────┘                                  │ completed_at │
           │                                          │ logs (JSON)  │
           │                                          └──────┬───────┘
           │                                                 │
           │         ┌──────────────┐         ┌──────────────▼───────────┐
           │         │  audit_logs  │         │      task_steps          │
           │         ├──────────────┤         ├──────────────────────────┤
           └────────►│ user_id (FK) │         │ id (PK)                  │
                     │ id (PK)      │         │ task_id (FK)             │
                     │ action       │         │ step_number              │
                     │ resource     │         │ tool_name                │
                     │ result       │         │ parameters (JSON)        │
                     │ risk_score   │         │ result (JSON)            │
                     │ timestamp    │         │ duration_ms              │
                     └──────────────┘         │ created_at               │
                                              └──────────────────────────┘

    ┌──────────────┐         ┌──────────────┐         ┌──────────────┐
    │   plugins    │         │ plugin_hooks │         │  file_refs   │
    ├──────────────┤         ├──────────────┤         ├──────────────┤
    │ id (PK)      │◄────────│ plugin_id    │         │ id (PK)      │
    │ name         │         │ id (PK)      │         │ task_id (FK) │
    │ version      │         │ event_type   │         │ file_path    │
    │ author       │         │ handler_code │         │ file_hash    │
    │ code         │         │ is_active    │         │ created_at   │
    │ is_enabled   │         └──────────────┘         └──────────────┘
    │ created_at   │
    └──────────────┘
```

### 5.2 表结构定义

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_login_at TIMESTAMP,
    mfa_enabled BOOLEAN NOT NULL DEFAULT false,
    mfa_secret VARCHAR(255),
    
    CONSTRAINT valid_role CHECK (role IN ('super_admin', 'admin', 'power_user', 'user', 'guest'))
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- 会话表
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(512) UNIQUE NOT NULL,
    refresh_token VARCHAR(512) UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    ip_address INET,
    user_agent TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    
    CONSTRAINT valid_expiry CHECK (expires_at > created_at)
);

CREATE INDEX idx_sessions_token ON sessions(token);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);

-- 任务表
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    goal TEXT NOT NULL,
    result TEXT,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    priority INTEGER NOT NULL DEFAULT 5,
    max_steps INTEGER NOT NULL DEFAULT 10,
    timeout_seconds INTEGER NOT NULL DEFAULT 300,
    cost_cents INTEGER,  -- 成本（美分）
    
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout')),
    CONSTRAINT valid_priority CHECK (priority BETWEEN 1 AND 10)
);

CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);

-- 任务步骤表（记录每一步执行）
CREATE TABLE task_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    tool_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    screenshot_url TEXT,
    
    UNIQUE(task_id, step_number)
);

CREATE INDEX idx_task_steps_task_id ON task_steps(task_id);

-- 审计日志表（分区表，按月分区）
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    user_name VARCHAR(50),
    user_role VARCHAR(20),
    session_id UUID,
    ip_address INET,
    user_agent TEXT,
    action_type VARCHAR(50) NOT NULL,
    action_details JSONB NOT NULL DEFAULT '{}',
    resource_type VARCHAR(50),
    resource_id VARCHAR(255),
    tool_name VARCHAR(100),
    command TEXT,
    parameters JSONB,
    status VARCHAR(20) NOT NULL,
    result_summary TEXT,
    error_message TEXT,
    risk_score INTEGER NOT NULL DEFAULT 0,
    security_flags TEXT[] DEFAULT '{}',
    screenshot_url TEXT,
    recording_url TEXT,
    command_output TEXT
) PARTITION BY RANGE (timestamp);

-- 创建分区（按月）
CREATE TABLE audit_logs_2024_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
CREATE TABLE audit_logs_2024_02 PARTITION OF audit_logs
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
-- ... 依此类推

CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action_type);
CREATE INDEX idx_audit_logs_risk ON audit_logs(risk_score DESC) WHERE risk_score >= 70;

-- 插件表
CREATE TABLE plugins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) UNIQUE NOT NULL,
    version VARCHAR(20) NOT NULL,
    description TEXT,
    author VARCHAR(100),
    code TEXT NOT NULL,  -- 插件代码
    schema JSONB NOT NULL,  -- 工具定义JSON Schema
    is_enabled BOOLEAN NOT NULL DEFAULT false,
    is_official BOOLEAN NOT NULL DEFAULT false,
    permissions TEXT[] DEFAULT '{}',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    installed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    
    CONSTRAINT valid_permissions CHECK (
        permissions <@ ARRAY['file:read', 'file:write', 'network:http', 'system:execute', 'app:control']
    )
);

-- 文件引用表（任务关联的文件）
CREATE TABLE file_refs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id) ON DELETE CASCADE,
    file_path TEXT NOT NULL,
    file_hash VARCHAR(64),  -- SHA-256
    file_size BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- 自动清理时间
    
    CONSTRAINT valid_expiry CHECK (expires_at > created_at)
);

CREATE INDEX idx_file_refs_task_id ON file_refs(task_id);
CREATE INDEX idx_file_refs_expires ON file_refs(expires_at) WHERE expires_at IS NOT NULL;
```

---

## 6. API设计

### 6.1 RESTful API规范

```yaml
openapi: 3.0.0
info:
  title: AI Agent OS API
  version: 2.0.0
  description: 企业级AI Agent操作系统API

servers:
  - url: https://api.ai-agent-os.local/v2
    description: 本地开发环境

security:
  - BearerAuth: []

paths:
  # 认证相关
  /auth/login:
    post:
      summary: 用户登录
      security: []  # 公开接口
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                username: { type: string }
                password: { type: string }
                mfa_code: { type: string }
      responses:
        200:
          description: 登录成功
          content:
            application/json:
              schema:
                type: object
                properties:
                  access_token: { type: string }
                  refresh_token: { type: string }
                  expires_in: { type: integer }
                  user: { $ref: '#/components/schemas/User' }

  /auth/refresh:
    post:
      summary: 刷新Token
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                refresh_token: { type: string }

  # 任务管理
  /tasks:
    get:
      summary: 获取任务列表
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [pending, running, completed, failed]
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
            maximum: 100
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
      responses:
        200:
          description: 任务列表
          content:
            application/json:
              schema:
                type: object
                properties:
                  total: { type: integer }
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/Task' }

    post:
      summary: 创建新任务
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [goal]
              properties:
                goal: { type: string, description: '用户目标' }
                priority: { type: integer, default: 5 }
                max_steps: { type: integer, default: 10 }
                timeout: { type: integer, default: 300 }
                context:
                  type: object
                  description: '额外上下文信息'
      responses:
        201:
          description: 任务创建成功
          content:
            application/json:
              schema: { $ref: '#/components/schemas/Task' }

  /tasks/{task_id}:
    get:
      summary: 获取任务详情
      parameters:
        - name: task_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: 任务详情
          content:
            application/json:
              schema: { $ref: '#/components/schemas/TaskDetail' }

    delete:
      summary: 取消/删除任务
      responses:
        204:
          description: 操作成功

  /tasks/{task_id}/steps:
    get:
      summary: 获取任务执行步骤
      parameters:
        - name: task_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: 步骤列表
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/TaskStep' }

  # WebSocket实时通信
  /ws/tasks:
    get:
      summary: WebSocket连接（实时任务状态）
      description: |
        建立WebSocket连接，实时接收任务状态更新。
        认证通过Query参数传递：?token=xxx
      responses:
        101:
          description: WebSocket连接已建立

  # 工具管理
  /tools:
    get:
      summary: 获取可用工具列表
      responses:
        200:
          description: 工具列表
          content:
            application/json:
              schema:
                type: array
                items: { $ref: '#/components/schemas/Tool' }

  /tools/{tool_name}/execute:
    post:
      summary: 直接执行工具（需要权限）
      parameters:
        - name: tool_name
          in: path
          required: true
          schema:
            type: string
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                parameters: { type: object }
                async: { type: boolean, default: false }
      responses:
        200:
          description: 执行结果

  # 插件管理
  /plugins:
    get:
      summary: 获取插件列表
      responses:
        200:
          description: 插件列表

    post:
      summary: 安装插件（管理员）
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                plugin_file:
                  type: string
                  format: binary
                metadata:
                  type: object

  /plugins/{plugin_id}/enable:
    post:
      summary: 启用插件

  /plugins/{plugin_id}/disable:
    post:
      summary: 禁用插件

  # 审计日志
  /audit/logs:
    get:
      summary: 查询审计日志（管理员）
      parameters:
        - name: start_date
          in: query
          schema:
            type: string
            format: date-time
        - name: end_date
          in: query
          schema:
            type: string
            format: date-time
        - name: user_id
          in: query
          schema:
            type: string
        - name: risk_min
          in: query
          description: 最小风险评分
          schema:
            type: integer
            minimum: 0
            maximum: 100
      responses:
        200:
          description: 审计日志列表
          content:
            application/json:
              schema:
                type: object
                properties:
                  total: { type: integer }
                  items:
                    type: array
                    items: { $ref: '#/components/schemas/AuditLog' }

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

  schemas:
    User:
      type: object
      properties:
        id: { type: string, format: uuid }
        username: { type: string }
        email: { type: string }
        role: { type: string }
        created_at: { type: string, format: date-time }

    Task:
      type: object
      properties:
        id: { type: string, format: uuid }
        status: { type: string }
        goal: { type: string }
        progress: { type: integer, minimum: 0, maximum: 100 }
        created_at: { type: string, format: date-time }
        started_at: { type: string, format: date-time }
        completed_at: { type: string, format: date-time }

    TaskDetail:
      allOf:
        - $ref: '#/components/schemas/Task'
        - type: object
          properties:
            result: { type: object }
            error_message: { type: string }
            steps_count: { type: integer }
            cost_cents: { type: integer }

    TaskStep:
      type: object
      properties:
        step_number: { type: integer }
        tool_name: { type: string }
        parameters: { type: object }
        status: { type: string }
        started_at: { type: string, format: date-time }
        completed_at: { type: string, format: date-time }

    Tool:
      type: object
      properties:
        name: { type: string }
        description: { type: string }
        parameters: { type: object }
        required_permissions: 
          type: array
          items: { type: string }

    AuditLog:
      type: object
      properties:
        id: { type: string, format: uuid }
        timestamp: { type: string, format: date-time }
        action_type: { type: string }
        status: { type: string }
        risk_score: { type: integer }
```

### 6.2 WebSocket协议

```typescript
// WebSocket消息类型定义
interface WebSocketMessage {
  type: 'task_update' | 'step_complete' | 'notification' | 'error';
  timestamp: string;
  payload: unknown;
}

// 任务更新消息
interface TaskUpdateMessage extends WebSocketMessage {
  type: 'task_update';
  payload: {
    task_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
    current_step?: number;
    total_steps?: number;
    message?: string;
  };
}

// 步骤完成消息
interface StepCompleteMessage extends WebSocketMessage {
  type: 'step_complete';
  payload: {
    task_id: string;
    step_number: number;
    tool_name: string;
    result_preview: string;
    screenshot_url?: string;
  };
}
```

---

## 7. 实现路线图

### Phase 1: MVP核心框架（4周）

```
Week 1: 基础架构
├── Day 1-2: 项目脚手架搭建（FastAPI + SQLAlchemy + Docker）
├── Day 3-4: 数据库设计与迁移脚本
├── Day 5-7: 用户认证系统（JWT + 密码哈希）
└── 交付物: 可运行的基础服务

Week 2: ReAct引擎
├── Day 1-2: Claude API集成
├── Day 3-4: ReAct循环实现（基础版）
├── Day 5-6: 基础工具实现（file_ops, system_info）
└── Day 7: 简单Web界面

Week 3: 安全基础
├── Day 1-2: 命令白名单实现
├── Day 3-4: 基础审计日志
├── Day 5-6: Docker沙箱集成（简化版）
└── Day 7: 安全测试

Week 4: 集成测试
├── Day 1-3: 端到端测试
├── Day 4-5: 性能测试与优化
├── Day 6: 文档编写
└── Day 7: MVP发布

MVP功能清单:
✓ 用户注册/登录
✓ 基础任务执行（ReAct）
✓ 3个基础工具（文件、命令、窗口）
✓ 命令白名单保护
✓ 简单Web界面
✓ 基础审计日志
```

### Phase 2: 安全与扩展（4周）

```
Week 5-6: 安全增强
├── RBAC权限系统
├── Docker沙箱完善
├── 敏感操作确认机制
├── 审计日志完善（ELK集成）
└── 合规报告功能

Week 7-8: 插件系统
├── 插件架构设计
├── 插件加载器实现
├── 官方插件开发（browser, office, ide）
├── 插件市场（简化版）
└── 插件文档
```

### Phase 3: 多客户端（4周）

```
Week 9-10: Web客户端
├── React项目搭建
├── 组件库（Ant Design）
├── 任务管理界面
├── 实时监控面板
└── 移动端适配

Week 11-12: 桌面客户端
├── Electron项目搭建
├── 系统集成（全局快捷键、托盘）
├── 本地模型支持（Ollama集成）
└── 离线模式
```

### Phase 4: 生产就绪（4周）

```
Week 13-14: 运维与监控
├── Prometheus + Grafana监控
├── 日志聚合（ELK Stack）
├── 告警系统
├── 备份与恢复
└── 性能调优

Week 15-16: 高级功能
├── 多模型智能路由
├── 视觉感知（截图分析）
├── 语音交互
├── 知识库集成（RAG）
└── 性能优化
```

---

## 8. 风险评估与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| **沙箱绕过** | 中 | 极高 | 多层防护、安全审计、赏金计划 |
| **API密钥泄露** | 中 | 高 | 环境变量、密钥轮转、最小权限 |
| **模型幻觉导致误操作** | 高 | 中 | 人工确认、操作回放、撤销机制 |
| **性能瓶颈** | 中 | 中 | 负载测试、缓存优化、异步处理 |
| **合规问题** | 低 | 高 | 法律顾问、隐私设计、数据本地化 |

---

## 9. 总结

### 9.1 与原版对比

| 维度 | AI_OSShell_v2 | AI Agent OS 2.0 | 提升 |
|------|--------------|-----------------|------|
| **架构** | 单体脚本 | 微服务+插件化 | 10x可维护性 |
| **安全** | 🔴 危险 | 🟢 企业级 | 本质改进 |
| **扩展** | 硬编码 | 动态插件 | 生态能力 |
| **多用户** | 单用户 | 多租户RBAC | 商用能力 |
| **多模态** | 文本 | 图+文+音 | 交互能力 |

### 9.2 关键成功因素

1. **安全优先**: 沙箱、权限、审计是底线
2. **渐进交付**: MVP → 安全 → 客户端 → 高级功能
3. **用户体验**: 自然交互 + 多客户端覆盖
4. **生态建设**: 插件系统打造开发者社区

### 9.3 下一步行动

**立即可做（今天）:**
- [ ] 确认技术选型（团队技术栈匹配度）
- [ ] 准备开发环境（Docker、PostgreSQL、Redis）
- [ ] 创建Git仓库和项目结构

**本周完成:**
- [ ] Phase 1 Week 1 任务（基础架构）
- [ ] 团队技术分享（架构设计评审）

**资源需求:**
- 2-3名后端工程师（Python/FastAPI）
- 1-2名前端工程师（React/Electron）
- 1名DevOps工程师（Docker/K8s）
- 总计：4-6人，3-4个月全职开发

---

**文档结束**

*本设计方案详细规划了AI Agent OS 2.0的架构、技术、安全、数据库、API等各个方面，可作为开发团队的实施蓝图。*

---

**更新时间**: 2026-02-15 10:10:49