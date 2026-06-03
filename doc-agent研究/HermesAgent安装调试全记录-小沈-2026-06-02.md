# Hermes Agent 安装调试全记录

**创建时间**: 2026-06-02 07:57:41  
**编写人**: 小沈  
**版本**: v1.1  

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-02 07:57:41 | 小沈 | 初始版本，完整记录Hermes Agent安装调试全过程 |
| v1.1 | 2026-06-03 05:00:00 | 小沈 | 第五章新增 5.4-5.7 子节：通用 Provider 新增/调整方法（以 agnes 为实例） |

---

## 目录

- [快速启动](#快速启动)
- [一、目标与背景](#一目标与背景)
- [二、环境准备](#二环境准备)
- [三、安装Hermes依赖](#三安装hermes依赖)
- [四、配置DeepSeek API](#四配置deepseek-api)
- [五、Provider插件配置](#五provider插件配置)
- [六、调试过程与问题记录](#六调试过程与问题记录)
- [七、验证结果](#七验证结果)
- [八、运行方式](#八运行方式)
- [九、心得体会](#九心得体会)
- [十、补充记录（2026-06-02 第二会话）](#十补充记录2026-06-02-第二会话)

---

## 快速启动

**前提**: WSL2 + Ubuntu 已安装，Hermes 代码已克隆到 `F:\agenttool\hermes`

### 方式一：分步操作（推荐）

**第一步**：进入 Hermes 目录并激活环境

```powershell
# 在 Windows PowerShell/CMD 中运行
wsl -d Ubuntu
cd /mnt/f/agenttool/hermes
source venv/bin/activate
```

**第二步**：启动 CLI

```bash
python cli.py
```

**完整一条命令**（一步到位）：

```powershell
wsl -d Ubuntu bash -c "cd /mnt/f/agenttool/hermes && source venv/bin/activate && python cli.py"
```

> **注意**: `-d` 和 `Ubuntu` 之间必须有空格！

### 方式二：一步到位（启动时指定模型）

```powershell
wsl -d Ubuntu bash -c "cd /mnt/f/agenttool/hermes && source venv/bin/activate && python cli.py --model deepseek/deepseek-chat"
```

### 配置 API Key

WSL 终端下编辑 `~/.hermes/.env` 文件：

```bash
# ~/.hermes/.env (WSL2: /home/admin/.hermes/.env)
# 或在 Windows 路径下: \\wsl.localhost\Ubuntu\home\admin\.hermes\.env

# Hermes Agent - DeepSeek config
DEEPSEEK_API_KEY=sk-f5c...efac
```

---

### 快速启动 — 支持网关的微信通信

```bash
cd /mnt/f/agenttool/hermes
source venv/bin/activate
nohup python3 -m gateway.run > /dev/null 2>&1 &
```

---

#### 完整的启动流程和命令

**WSL 终端里执行：**

```bash
# 1. 进入 WSL（在 Windows PowerShell/CMD 中运行）
wsl

# 2. 切到 Hermes 项目根目录
cd /mnt/f/agenttool/hermes

# 3. 激活虚拟环境（必须是项目根目录，相对路径才能解析）
source venv/bin/activate

# 4. 后台启动微信网关
nohup python3 -m gateway.run > /dev/null 2>&1 &
```

**注意事项（按顺序）：**

1. `wsl` 是在 Windows PowerShell/CMD 里执行，进入 Ubuntu 发行版
2. `cd` 必须成功，激活 venv 用的是相对路径，目录不对会报"找不到 venv/bin/activate"
3. `source`（不是 `.`）激活 venv，激活后命令行前缀会出现 `(venv)` 字样
4. `nohup ... &` 把进程挂到后台，关掉 WSL 窗口也不会被杀；`> /dev/null 2>&1` 把所有输出丢掉
5. 首次启动需要先在 `~/.hermes/config.yaml` 配置微信（weixin / ilink）平台凭证，否则网关启动了也连不上微信

**配置文件路径**：

```
\\wsl.localhost\Ubuntu\home\admin\.hermes\config.yaml
```

---

#### 推荐：用 hermes CLI 替代裸命令

```bash
# 启动网关（前台，能看到日志）
hermes gateway

# 或后台启动（CLI 自带 daemon 管理，会写 PID 文件）
hermes gateway start

# 查看状态
hermes gateway status

# 停止
hermes gateway stop

# 看日志
hermes logs --follow --level INFO
```

> `hermes` 命令是 venv 里的 wrapper，封装了 `python3 -m gateway.run` + 配置文件加载 + 日志管理 + PID 管理，比手动 `nohup` 健壮（重启不会重复起进程、崩溃有日志可查）。

**验证启动成功：**

```bash
# 看进程
ps aux | grep gateway.run | grep -v grep

# 看日志（推荐路径）
tail -f ~/.hermes/logs/gateway.log
```

---

#### 停止网关

**第 2 种启动方式（hermes CLI，推荐）：**

```bash
wsl -d Ubuntu bash -c "cd /mnt/f/agenttool/hermes && source venv/bin/activate && hermes gateway stop"
```

**其他相关命令：**

```bash
hermes gateway status    # 看运行状态
hermes gateway restart   # 重启
```

**第 1 种启动方式（nohup 裸启动）：**

```bash
# 找进程
wsl -d Ubuntu bash -c "ps aux | grep gateway.run | grep -v grep"

# 找到 PID 后 kill（比如 PID 是 12345）
wsl -d Ubuntu bash -c "kill 12345"

# 或者一键杀掉所有 gateway.run 进程
wsl -d Ubuntu bash -c "pkill -f gateway.run"
```

**杀不掉的兜底：**

```bash
# 强制杀
wsl -d Ubuntu bash -c "pkill -9 -f gateway.run"
```

杀之前建议先看状态：

```bash
# 看进程是否存在
wsl -d Ubuntu bash -c "ps aux | grep gateway.run | grep -v grep"
```

---

## 一、目标与背景

**目标**: 在本地 WSL2 (Ubuntu) 环境中安装 Nous Research 的 [Hermes Agent](https://github.com/NousResearch/hermes-agent) v0.15.1，并配置 DeepSeek V4 模型 (`deepseek-v4-flash` / `deepseek-v4-pro`)，最终能在 CLI TUI 中交互使用。

**源码位置**: `F:\agenttool\hermes`（通过 githubfast.com 镜像克隆）  
**系统环境**: Windows 11 + WSL2 (Ubuntu) + Python 3.11.15  
**包管理器**: uv 0.11.14  

---

## 二、环境准备

### 2.1 WSL 状态检查

| 项目 | 值 |
|------|-----|
| WSL 版本 | WSL2 |
| Linux 发行版 | Ubuntu |
| 状态 | 初始为 Stopped，启动后运行正常 |

### 2.2 Python 与 uv

Hermes 要求 Python >= 3.11。WSL Ubuntu 自带的 Python 版本为 3.14.4，但 Hermes 的 `pyproject.toml` 只要求 >=3.11，所以两版本均可。实际我们使用了 `uv` 创建的 venv（Python 3.11.15）。

| 工具 | 路径 | 版本 |
|------|------|------|
| Python (venv) | `/mnt/f/agenttool/hermes/venv/bin/python` | 3.11.15 |
| uv | `/home/admin/.local/bin/uv` | 0.11.14 |

---

## 三、安装 Hermes 依赖

### 3.1 创建虚拟环境

```bash
cd /mnt/f/agenttool/hermes
uv venv venv
```

输出：`Using CPython 3.11.15, Creating virtual environment at: venv`

### 3.2 安装全部依赖

```bash
uv pip install -e ".[all,dev]"
```

安装结果：
- 解析 101 个包，耗时 2.29s
- 下载/构建/安装 70 个包，总耗时约 95s
- 核心依赖包括：`openai==2.24.0`, `httpx==0.28.1`, `pydantic==2.13.4`, `prompt_toolkit==3.0.52` 等

---

## 四、配置 DeepSeek API

### 4.1 创建 .env 文件

在 Hermes 项目根目录创建 `.env`（该文件已被 `.gitignore` 排除，不会提交到仓库）：

```bash
cat > /mnt/f/agenttool/hermes/.env << 'EOF'
# Hermes Agent - DeepSeek config
DEEPSEEK_API_KEY=sk-f5c...efac
EOF
```

**关键**: Hermes 的 DeepSeek provider 使用环境变量 `DEEPSEEK_API_KEY`，而不是 `OPENAI_API_KEY`。

### 4.2 DeepSeek 端点信息

| 端点 | 用途 |
|------|------|
| `https://api.deepseek.com/v1` | OpenAI 兼容的 Chat Completions 端点 |
| `https://api.deepseek.com` | 基础 API 端点 |
| `https://api.deepseek.com/anthropic` | Anthropic 兼容端点 |
| `https://api.deepseek.com/v1/models` | 模型列表查询 |

### 4.3 可用模型

通过 API 查询到 2 个模型：

| 模型名 | 类型 |
|--------|------|
| `deepseek-v4-flash` | V4 思考模型（快速） |
| `deepseek-v4-pro` | V4 思考模型（专业） |

---

## 五、Provider 插件配置

### 5.1 内置 DeepSeek 插件

Hermes 已经自带了 DeepSeek provider 插件，位于：

```
F:\agenttool\hermes\plugins\model-providers\deepseek/
├── __init__.py    # DeepSeekProfile 定义
└── plugin.yaml    # 插件清单
```

**插件核心配置**：

| 字段 | 值 |
|------|-----|
| name | `deepseek` |
| aliases | `deepseek-chat` |
| env_vars | `DEEPSEEK_API_KEY` |
| base_url | `https://api.deepseek.com/v1` |
| api_mode | `chat_completions` |
| default_aux_model | `deepseek-chat` |

### 5.2 特殊处理：V4 思考模型

`DeepSeekProfile` 类重写了 `build_api_kwargs_extras()` 方法，专门处理 V4 思考模型的特殊性：

1. `extra_body.thinking.type` = `enabled|disabled` — 控制思考模式开关
2. `reasoning_effort` = `low|medium|high|max` — 控制思考深度
3. V3 模型（`deepseek-chat`）不受影响，保持原始行为

### 5.3 补充 fallback_models

原始 fallback_models 只有 `deepseek-chat` 和 `deepseek-reasoner`，缺少 V4 模型。已补充：

```python
# 修改前
fallback_models=("deepseek-chat", "deepseek-reasoner")

# 修改后
fallback_models=("deepseek-chat", "deepseek-reasoner",
                 "deepseek-v4-flash", "deepseek-v4-pro")
```

这样当 `/model` 选择器无法在线获取模型列表时，仍能显示 V4 模型。

### 5.4 通用方法：新增/调整 Provider

5.1-5.3 是 DeepSeek 的特例。**新接入任何 OpenAI 兼容的 API** 都按本节流程操作。**核心原则：尽量复用现有 provider，能不写新类就不写新类**。

#### 5.4.1 适用场景

| 场景 | 例子 |
|------|------|
| 新接入一个 OpenAI 兼容的 API | 接入 agnes-ai、自建中转、其他厂商 |
| 给已有 provider 增加新模型 | 在 fallback_models 中追加 |
| provider 临时调整 | 改 base_url、修改 env_vars 名等 |

#### 5.4.2 准备工作清单

动手前先确认这 5 项：

| # | 项目 | 示例（agnes） |
|---|------|---------------|
| 1 | API Key | `sk-0QG...wpDy` |
| 2 | Base URL | `https://apihub.agnes-ai.com/v1` |
| 3 | 模型清单 | agnes-1.5-flash / agnes-2.0-flash / agnes-image-2.0-flash / agnes-image-2.1-flash / agnes-video-v2.0 |
| 4 | env var 命名（**首字母大写、下划线分隔**） | `AGNES_API_KEY` |
| 5 | 是否有 thinking / 特殊模式？ | 无（普通 chat） |

#### 5.4.3 步骤详解（以 agnes 为例）

**步骤 1：选择模板**

在 `plugins/model-providers/` 下选一个**最相似的现有 provider** 作为模板：

| 目标 provider 行为 | 参考模板 |
|------------------|---------|
| 普通 OpenAI 兼容 chat（**最常见**） | `xiaomi/__init__.py` — 14 行，最简版 |
| 需要 thinking / reasoning 特殊处理 | `deepseek/__init__.py` — 重写 `build_api_kwargs_extras` |
| OAuth 设备码授权 | 看 anthropic 或 copilot |
| 多 backend relay | 看 openrouter |

**agnes 是普通 chat** → 用 `xiaomi` 模板。

**步骤 2：创建目录和 `__init__.py`**

路径：`F:\agenttool\hermes\plugins\model-providers\agnes\__init__.py`

```python
"""Agnes AI provider profile.

Generic OpenAI-compatible relay at https://apihub.agnes-ai.com/v1.
Exposes text, image, and video models behind one API key.
"""

from __future__ import annotations

from providers import register_provider
from providers.base import ProviderProfile


agnes = ProviderProfile(
    name="agnes",
    aliases=("agnes-ai",),
    env_vars=("AGNES_API_KEY",),
    display_name="Agnes AI",
    description="Agnes AI — multi-model relay (text/image/video)",
    signup_url="https://apihub.agnes-ai.com/",
    base_url="https://apihub.agnes-ai.com/v1",
    default_aux_model="agnes-1.5-flash",
    fallback_models=(
        "agnes-1.5-flash",
        "agnes-2.0-flash",
        "agnes-image-2.0-flash",
        "agnes-image-2.1-flash",
        "agnes-video-v2.0",
    ),
)

register_provider(agnes)
```

**关键字段说明**：

| 字段 | 作用 | 必填 |
|------|------|------|
| `name` | provider 唯一标识，`/model` 用 `name/model` 选择 | ✅ |
| `aliases` | 备选名称，可写多个；用户输入别名也能识别 | ❌ |
| `env_vars` | 启动时从环境变量读 key 的名字（**首字母大写**） | ✅ |
| `base_url` | OpenAI 兼容端点 | ✅ |
| `display_name` | picker 里显示的友好名 | ❌ |
| `description` | picker 副标题 | ❌ |
| `signup_url` | setup 流程里显示给用户的注册链接 | ❌ |
| `fallback_models` | 在线拉不到模型列表时显示的备选；`/model` picker 也用它 | ✅ |
| `default_aux_model` | 后台小任务（压缩、视觉）默认用的便宜模型 | ❌ |
| `supports_health_check` | `False` → doctor 跳过 `/models` 探活 | ❌ |

**步骤 3：创建 `plugin.yaml`**

路径：`F:\agenttool\hermes\plugins\model-providers\agnes\plugin.yaml`

```yaml
name: agnes-provider
kind: model-provider
version: 1.0.0
description: Agnes AI (text/image/video relay)
author: Nous Research
```

> **注意**：`name` 字段用 `{provider}-provider` 格式（如 `agnes-provider`），与 `__init__.py` 里的 `name` 区分开。

**步骤 4：在 `.env` 中追加 API Key**

路径：`F:\agenttool\hermes\.env`，在已有内容后追加：

```bash
# Hermes Agent - Agnes AI config
AGNES_API_KEY=sk-0QG...wpDy
```

**关键**：环境变量名**必须**和 `env_vars` 元组里的字符串**一字不差**。`AGNES_API_KEY` ≠ `AGNES_KEY` ≠ `agnEs_api_key`。

**步骤 5：验证（用 WSL 执行 Python 脚本）**

> ⚠️ **避坑**：PowerShell 调用 WSL 时**不要用 `bash -c` 嵌套双引号**（参见第六章 6.1）。把 Python 脚本写到文件里，再 `wsl -d Ubuntu bash -c "cd /path && source venv/bin/activate && python script.py"`。

**5a. 验证 provider 注册成功**：

```python
# verify_agnes.py
import sys
sys.path.insert(0, "plugins")
from providers import list_providers
p = next(p for p in list_providers() if p.name == "agnes")
print(f"name             : {p.name}")
print(f"env_vars         : {p.env_vars}")
print(f"base_url         : {p.base_url}")
print(f"fallback_models  : {p.fallback_models}")
```

**预期输出**：
```
name             : agnes
env_vars         : ('AGNES_API_KEY',)
base_url         : https://apihub.agnes-ai.com/v1
fallback_models  : ('agnes-1.5-flash', 'agnes-2.0-flash', ...)
```

**5b. 验证 API 连通**：

```python
# test_agnes_api.py
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")
client = OpenAI(base_url="https://apihub.agnes-ai.com/v1",
                api_key=os.environ["AGNES_API_KEY"])

# 列模型
r = client.models.list()
print([m.id for m in r.data])

# 聊一句
r = client.chat.completions.create(
    model="agnes-1.5-flash",
    messages=[{"role": "user", "content": "Reply: pong"}],
    max_tokens=20,
)
print(r.choices[0].message.content)
```

**预期输出**：
```
['agnes-1.5-flash', 'agnes-2.0-flash', 'agnes-image-2.0-flash', ...]
pong
```

**5c. 验证完清理临时文件**（**禁止在项目目录留临时测试文件**）：

```bash
rm verify_agnes.py test_agnes_api.py
rm -rf plugins/model-providers/agnes/__pycache__/
```

**步骤 6：CLI 中切换模型**

启动 CLI 后：
```
/model agnes/agnes-1.5-flash
/model                                  # 不带参：查看 picker，输入 "agnes" 过滤
```

### 5.5 调整已有 Provider（不新建文件）

有些改动**不需要新建 provider 目录**，直接改 `__init__.py` 即可：

| 需求 | 改哪里 | 例子 |
|------|--------|------|
| 增加 fallback_models 中的模型 | `__init__.py` 的 `fallback_models` 元组 | 5.3 给 deepseek 加 V4 模型 |
| 改 base_url | `__init__.py` 的 `base_url` | 中转地址变更 |
| 改 env_vars 名字 | `__init__.py` 的 `env_vars` 元组 + `.env` | 重命名 key |
| 调整 thinking 行为 | `__init__.py` 重写 `build_api_kwargs_extras` | 5.2 deepseek 的特殊处理 |

**改完一定要重启 CLI**，env var 改动后要 `source venv/bin/activate` 重新加载。

### 5.6 常见失败原因速查

| 现象 | 根因 | 修复 |
|------|------|------|
| `/model` 里看不到新 provider | provider 没注册或导入失败 | 看 CLI 启动日志；用 5.4.3 步骤 5a 脚本验证 |
| 选完模型报错 `Authentication failed` | `env_vars` 名字和 `.env` 不一致 | 大小写、下划线、字母一字不差 |
| `404 Not Found` | `base_url` 拼错，缺 `/v1` 后缀 | 对照厂商文档 |
| `model_not_found` | `fallback_models` 拼错，或厂商根本没这模型 | 先用 5.4.3 步骤 5b 脚本列模型对照 |
| 5b 脚本读不到 key | `.env` 不在当前目录，或 `load_dotenv()` 没调用 | 显式 `load_dotenv("/path/.env")` |
| WSL `python: command not found` | 非交互 shell PATH 不全 | 用 venv 完整路径 `/mnt/f/agenttool/hermes/venv/bin/python` |

### 5.7 关键经验

1. **选对模板是核心** — 普通 chat 用 `xiaomi`（14 行），需要特殊处理才继承重写。不要一上来就抄 deepseek，那有 100 行。
2. **provider 目录命名 = URL hostname 主体** — `https://apihub.agnes-ai.com` → `agnes`（去 `-ai` 和前缀）。
3. **env var 命名约定**：`<PROVIDER>_API_KEY`，全大写，下划线。
4. **fallback_models 不能空** — picker 在网络拉不到时靠这个显示，且只有**支持 tool calling 的 agentic 模型**才能放进去。image/video 模型放进去虽然会显示但不能跑 agent，**用之前要清楚**。
5. **测试文件用完必删** — 含 API Key 的临时脚本禁止留在项目根目录（参见第六章 6.5）。
6. **每次改动都更新文档** — provider 加完同步在本文档对应章节补充。

---

## 六、调试过程与问题记录

### 6.1 问题1：PowerShell 与 WSL 的引号冲突

**现象**: 

```powershell
wsl -d Ubuntu bash -c 'python -c "import run_agent; print(42)"'
```

报 SyntaxError，`import` 出现在 Python 错误信息第一行。

**根因**: PowerShell 处理外部命令时，双引号 `"` 被消耗，bash 收到的 Python 代码被拦腰截断成多行。

**解决**: 避开 `bash -c` 嵌套引号，直接用：

```powershell
wsl -d Ubuntu /path/to/venv/bin/python -c "simple code"
```

如果必须用 `bash -c`，则用单引号包裹 bash 命令，内部用双引号。

**教训**: 在 PowerShell 中调用 WSL 执行内联 Python 代码时，`wsl -d Ubuntu <command>` 直接模式是最可靠的。避免 `bash -c` 嵌套双引号。

---

### 6.2 问题2：WSL 非交互 Shell 的 PATH 不完整

**现象**: 

```powershell
wsl -d Ubuntu -e bash -c 'python --version'
```

返回 `python: command not found`

**根因**: WSL 的非交互 shell 不会加载 `~/.bashrc` 或 `~/.profile`，默认 PATH 不包含 `~/.local/bin`。

**解决**: 使用 Hermes venv 的完整 Python 路径：

```powershell
wsl -d Ubuntu /mnt/f/agenttool/hermes/venv/bin/python -c "..."
```

**教训**: 在 WSL 非交互模式下，涉及 Python/uv 的命令必须使用完整路径，不能依赖 PATH。

---

### 6.3 问题3：DeepSeek V4 思考模型的 content 为空

**现象**:

```python
r = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "Say hi"}],
    max_tokens=30
)
print(repr(r.choices[0].message.content))  # 输出: ''
print(r.usage.completion_tokens_details.reasoning_tokens)  # 输出: 30
```

**根因**: DeepSeek V4 是思考模型，会先输出 `reasoning_content`（思考过程），再输出 `content`（最终答案）。`max_tokens=30` 太小，全部 30 个 token 都花在 reasoning 上，没轮到输出 content。

**解决**: 
1. 增加 `max_tokens` 到 100 以上，留足给 content 的空间
2. DeepSeek V4 非流式调用时，content 可能在 finish_reason=stop 时才返回
3. 流式调用时，先收到 `reasoning_content` delta，后收到 `content` delta

**验证**（`max_tokens=100` 通过）:

```python
# streaming test: reasoning="We need to answer...", content="Hello there!"
# agent test:     final_response="Hello there!"
```

**教训**: 思考模型需要更大的 token 预算。测试时必须考虑 reasoning_tokens 的消耗，不能按普通模型的习惯设 max_tokens。

---

### 6.4 问题4：CLI TUI 不支持管道输入

**现象**: 

```bash
echo "/exit" | python cli.py
```

进程超时，没有退出。

**根因**: `cli.py` 使用 `prompt_toolkit` 库实现 TUI，它直接操作终端（读取键盘事件），不读取 stdin 管道数据。

**解决**: 用户必须亲自在终端中交互。验证是否能正常启动的方法是用一个短 timeout：

```bash
timeout 5 python cli.py
```

能显示欢迎界面和提示符就算启动成功。

**教训**: TUI 应用不能像 CLI 工具那样用管道测试，需要真人操作。

---

### 6.5 问题5：.env 文件不能直接用 exec 读取

**现象**:

```python
exec(open(".env").read())  # NameError: name 'sk' is not defined
```

**根因**: `.env` 文件是 shell 格式（`KEY=value`），不是 Python 格式。`exec` 把 `sk-xxx` 当成 Python 变量名解析。

**解决**:

```python
# 方法1: 使用 python-dotenv
from dotenv import load_dotenv
load_dotenv("/path/to/.env")

# 方法2: 手动解析
with open(".env") as f:
    for line in f:
        if line.startswith("KEY="):
            value = line.strip().split("=", 1)[1]
```

---

### 6.6 问题6：wsl 参数拼写错误

**现象**:

```powershell
wsl -dUbuntu bash -c "..."
# 报：无效的命令行参数：-dUbuntu
```

**根因**: `-d` 和分发版名称之间空格是必需的。`-dUbuntu` 被解析成一个整体参数。

**解决**: 

```powershell
# 正确
wsl -d Ubuntu bash -c "..."
# 错误
wsl -dUbuntu bash -c "..."
```

---

## 七、验证结果

### 7.1 验证清单

| # | 检查项 | 结果 |
|---|--------|------|
| 1 | `.env` 文件存在且包含 DEEPSEEK_API_KEY | ✅ |
| 2 | DeepSeek provider 插件定义正确 | ✅ |
| 3 | fallback_models 包含 V4 模型 | ✅（已补充） |
| 4 | `run_agent` 模块可正常导入 | ✅ |
| 5 | `hermes_cli.main` 模块可正常导入 | ✅ |
| 6 | DeepSeek API `/v1/models` 返回 200 | ✅ |
| 7 | `deepseek-v4-flash` 在模型列表中 | ✅ |
| 8 | `deepseek-v4-pro` 在模型列表中 | ✅ |
| 9 | 流式 Chat 返回 reasoning_content + content | ✅ |
| 10 | AIAgent 完整对话（含工具循环） | ✅（输出: "Hello there!"、"4"） |
| 11 | CLI TUI 启动到欢迎界面 | ✅ |
| 12 | 测试临时文件全部清理 | ✅ |

### 7.2 测试用例结果

```python
# 1. 直接 API 调用（非流式）
model="deepseek-v4-flash", max_tokens=100
→ status=200, content="Hello there!", finish_reason="stop"

# 2. 流式调用
model="deepseek-v4-flash", max_tokens=50
→ reasoning_content="We need to answer...", content="four"

# 3. Hermes AIAgent 完整对话
model="deepseek-v4-flash", max_iterations=1
→ final_response="Hello there!", turn_exit_reason="text_response(finish_reason=stop)", failed=False
```

---

## 八、运行方式

### 8.1 CLI TUI 交互模式（推荐）

```bash
wsl -d Ubuntu bash -c "cd /mnt/f/agenttool/hermes && source venv/bin/activate && python cli.py"
```

进入后常用斜杠命令：

| 命令 | 功能 |
|------|------|
| `/model deepseek/deepseek-v4-flash` | 切换模型 |
| `/model deepseek/deepseek-v4-pro` | 切换模型 |
| `/tools` | 查看/配置工具集 |
| `/new` 或 `/reset` | 开始新对话 |
| `/compress` | 压缩上下文 |
| `/help` | 查看全部命令 |
| `Ctrl+C` | 中断当前输出 |
| `Ctrl+D` | 退出 CLI |

### 8.2 Python 库模式

```python
from run_agent import AIAgent

agent = AIAgent(
    base_url="https://api.deepseek.com/v1",
    model="deepseek-v4-flash",
    api_key="sk-xxx",
    provider="deepseek",
    max_iterations=1,
)
result = agent.run_conversation("你的问题")
print(result["final_response"])
```

### 8.3 消息网关模式（需额外配置）

```bash
source venv/bin/activate
hermes gateway start
```

支持平台：Telegram、Discord、Slack、WhatsApp、Signal 等。

---

## 九、心得体会

### 9.1 安装总结

| 阶段 | 耗时 | 难度 |
|------|------|------|
| 环境检查 | 5分钟 | 低 |
| 依赖安装 | 2分钟 | 低 |
| 配置 API Key | 1分钟 | 低 |
| Provider 调整 | 5分钟 | 低 |
| 调试引号冲突 | 20分钟 | 中 |
| 调试 V4 思考模型 | 15分钟 | 中 |
| 验证 | 10分钟 | 低 |

**总计约 1 小时**，其中引号冲突和思考模型调试占了大部分时间。

### 9.2 关键经验

1. **WSL + PowerShell 引号**是最耗时的坑。推荐用 `wsl -d Ubuntu <command>` 直接模式，避免嵌套引号
2. **思考模型（V4）** 的行为与普通模型不同：先 reasoning 后 content，max_tokens 需要多留余量
3. **Hermes 代码质量很高** — provider 插件体系完善，DeepSeek 的思考模型特殊处理已经内置，只需配 API Key 即可使用
4. **不要在项目目录留含 API Key 的临时文件** — 每次都清理干净

---

## 十、补充记录（2026-06-02 第二会话）

### 10.1 DeepSeek V4 Thinking 模型行为确认

**V4 双字段输出机制**:
- `reasoning_content` — 思考过程（CoT 链）
- `content` — 最终回答
- streaming 时 `reasoning_content` 先到达（delta accumulates），然后 `content` 开始到达
- 需设置 `max_tokens > 100` 为 content 留空间（否则 content 被截断甚至为空）

**fallback_models 更新**:
在 `plugins/model-providers/deepseek/__init__.py` 中添加：
```python
"deepseek-v4-flash",
"deepseek-v4-pro",
```
使 V4 模型进入 fallback 路径，兼容 thinking mode。

### 10.2 调试教训汇总

| 问题 | 根因 | 解决方法 |
|------|------|---------|
| PowerShell ↔ WSL 引号冲突 | 嵌套双引号被 WSL 截断 | `wsl -d Ubuntu` 直接执行，避免 `bash -c` |
| PATH 不完全 | WSL 非交互 shell 不加载 ~/.bashrc | 使用完整路径 `/mnt/f/agenttool/hermes/venv/bin/python` |
| `wsl -d Ubuntu` 写法错误 | `-dUbuntu` 不识别 | 必须空格：`wsl -d Ubuntu` |
| `.env` 读取失败 | 用 `exec(open().read())` 不支持 export | 改为 `load_dotenv()` |
| CLI TUI 不接受 | stdin pipe 不工作 | 使用 `prompt_toolkit` 终端交互 |

### 10.3 Weixin 网关配置详解（iLink Bot 个人微信）

#### 10.3.1 配置现状（已配置）

Hermes 的 Weixin 网关**之前已经配置完成**，配置信息位于 `~/.hermes/.env`：

```ini
# ~/.hermes/.env  (WSL2: /home/admin/.hermes/.env)
WEIXIN_ACCOUNT_ID=4fa3c61028dc@im.bot
WEIXIN_TOKEN=4fa3c61028dc@im.bot:060000932a0b4c373d00a5434c6dd0b65b987e
WEIXIN_BASE_URL=https://ilinkai.weixin.qq.com
WEIXIN_DM_POLICY=open
```

账号文件位于 `~/.hermes/weixin/accounts/`：

| 文件 | 内容 |
|------|------|
| `4fa3c61028dc@im.bot.json` | token + base_url + user_id (o9cq807v0Ivf...) |
| `4fa3c61028dc@im.bot.context-tokens.json` | 会话上下文 token（恢复用） |
| `4fa3c61028dc@im.bot.sync.json` | get_updates 同步状态 |

#### 10.3.2 配置方式一：交互式扫码登录（推荐）

```bash
# 进入 Hermes 目录
cd /mnt/f/agenttool/hermes

# 运行交互式设置（venv 环境下）
./venv/bin/python -m hermes setup
```

**扫码登录流程**：

1. 在终端菜单中选择 **Weixin** 平台
2. Hermes 调用 iLink Bot API（`ilinkai.weixin.qq.com`）获取二维码
3. 终端显示 ASCII 二维码（使用 `qrcode` 库渲染）
4. **微信扫码**（个人微信 App → 扫一扫）
5. 在手机上确认登录
6. Hermes 轮询扫码结果（最长等待约 8 分钟）
7. 确认后自动保存：
   - `account_id` → `~/.hermes/.env` 的 `WEIXIN_ACCOUNT_ID`
   - `token` → `~/.hermes/.env` 的 `WEIXIN_TOKEN`
   - `base_url` → `~/.hermes/.env` 的 `WEIXIN_BASE_URL`
   - 账号信息 → `~/.hermes/weixin/accounts/{id}.json`

**注意**：
- 依赖 `aiohttp` 和 `cryptography` 包（Hermes 安装时已包含）
- 需要终端支持 Unicode 显示二维码
- 二维码有效期有限，过期需重新获取

#### 10.3.3 配置方式二：手动配置 .env

如果已有 iLink Bot 的 token 和 account_id，可以直接写 `.env`：

```bash
# WSL2 中编辑
echo 'WEIXIN_ACCOUNT_ID=your_account_id' >> ~/.hermes/.env
echo 'WEIXIN_TOKEN=your_ilink_bot_token' >> ~/.hermes/.env
echo 'WEIXIN_BASE_URL=https://ilinkai.weixin.qq.com' >> ~/.hermes/.env
echo 'WEIXIN_DM_POLICY=open' >> ~/.hermes/.env
```

**配置自动启用的条件**：设了 `WEIXIN_ACCOUNT_ID` 或 `WEIXIN_TOKEN` 任一变量，`load_gateway_config()` 的 `_apply_env_overrides()` 会自动将 `Platform.WEIXIN` 加入 `cfg.platforms` 并 `enabled=True`。

#### 10.3.4 配置验证

验证配置是否正确加载：

```python
# 测试脚本
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path.home() / ".hermes" / ".env")

from gateway.config import load_gateway_config, Platform
cfg = load_gateway_config()
print(f"Has WEIXIN: {Platform.WEIXIN in cfg.platforms}")
if Platform.WEIXIN in cfg.platforms:
    p = cfg.platforms[Platform.WEIXIN]
    print(f"enabled: {p.enabled}")
    print(f"token: {p.token[:30]}...")
    print(f"extra: {p.extra}")
```

**本机验证结果**（2026-06-02）:
```
Has WEIXIN: True
enabled: True
token: 4fa3c61028dc@im.bot:060000932a...
extra: {'account_id': '4fa3c61028dc@im.bot', 'base_url': 'https://ilinkai.weixin.qq.com', 'dm_policy': 'open'}
```

**关键注意点**：
- `load_gateway_config()` 必须在 `dotenv.load_dotenv()` 之后调用，否则 env var 未加载会导致 Weixin 不出现
- Hermes 正式入口（`hermes gateway run`）会自动处理 dotenv 加载，不用人工干预

#### 10.3.5 启动网关

```bash
cd /mnt/f/agenttool/hermes
./venv/bin/python -m hermes gateway run
```

网关启动后 WeixinAdapter 会：
1. 检查 `aiohttp` 和 `cryptography` 是否已安装
2. 检查 `token` 和 `account_id` 非空
3. 获取 token 锁（"weixin-bot-token"）
4. 创建 `aiohttp.ClientSession`
5. 从磁盘恢复 context tokens
6. 启动 `_poll_loop()` 异步轮询任务

#### 10.3.6 wecom.py — 企业微信（WeCom AI Bot WebSocket）

配置方法类似，但使用不同的 API：

```bash
# ~/.hermes/.env
WECOM_BOT_ID=your_bot_id
WECOM_SECRET=your_secret
WECOM_TOKEN=your_token           # 回调验证用（可选）
WECOM_ENCODING_AES_KEY=your_key # 回调验证用（可选）
WECOM_DM_POLICY=open
WECOM_GROUP_POLICY=open
```

wecom 使用 WebSocket 连接（非 HTTP 轮询），同样通过 `_apply_env_overrides()` 检测 `WECOM_BOT_ID` + `WECOM_SECRET` 自动启用。

**其他网关**: 飞书（feishu.py）、钉钉（dingtalk.py）、QQ（qqbot/）— 配置模式相同，各自检测对应环境变量。

### 10.4 最终验证状态

| 验证项 | 状态 |
|--------|------|
| CLI 正常启动 | ✅ |
| DeepSeek V4 Flash 流式对话 | ✅ |
| DeepSeek V4 Pro 流式对话 | ✅ |
| Agent 正常响应 | ✅ |
| 17 toolsets 注册 | ✅ |
| 临时测试文件清理 | ✅ |
| 文档更新（快速开始 + v4） | ✅ |
| 安装文档完成 | ✅ |

---

**文档完成时间**: 2026-06-02 07:57:41  
**最后更新**: 2026-06-03 05:00:00  
**编写人**: 小沈  
**最后验证结果**: 全部验证通过
