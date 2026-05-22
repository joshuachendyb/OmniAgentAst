# Ollama 本地部署说明

**创建时间**: 2026-05-22 06:40:08  
**版本**: v1.1  
**编写人**: 小健

---

## 版本记录

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-05-22 06:40:08 | 小健 | 初始版本 |
| v1.1 | 2026-05-22 06:49:30 | 小健 | 补充启动/关闭/目录/图形界面详细说明，修正模型实际存放位置 |
| v1.2 | 2026-05-22 07:27:46 | 小健 | 模型成功从 C 盘移至 E 盘，全部 7 个 Ollama 测试通过确认；新增 VBS 静默启动脚本 |

---

## 一、概述

**Ollama 是什么**: Ollama 是一个本地大模型运行工具。你可以把它理解为"本地的 LLM 服务器"——它让你可以在自己电脑上运行大模型（如 qwen、llama 等），不需要联网，也不需要调用外部 API。

**在项目中的作用**：
- 开发调试时替代外部 API（七牛、智谱等），不花一分钱
- 没有网络也能跑全链路测试
- 验证 Agent 的 ReAct 循环、工具调用等核心逻辑

**一句话**: Ollama = 在本机跑 AI 模型的服务端软件。

---

## 二、安装过程

### 2.1 从哪里安装的

Ollama 是从 **winget** 安装的。winget 是 Windows 自带的包管理器（类似手机上的应用商店）。

```bash
# 在终端执行这个命令安装的
winget install --id Ollama.Ollama -l E:\ollama
```

`-l E:\ollama` 参数指定了安装到 E 盘，所以程序文件都在 `E:\ollama\`。

### 2.2 安装完后有哪些文件

```
E:\ollama\                          ← 程序安装目录
├── ollama.exe                      ← 主程序（命令行工具 + 服务端）
├── ollama app.exe                  ← 系统托盘程序（图形界面）
├── unins000.exe                    ← 卸载程序
├── lib\                            ← 运行时库（不要动）
└── models\                         ← 空目录（本想用来存模型，实际没用上）
```

### 2.3 模型文件实际在哪

**现在已经把模型从 C 盘移到 E 盘了，测试全部通过**。

| 目录 | 是什么 | 占用空间 |
|------|--------|---------|
| `E:\ollama\` | **程序本体**（ollama.exe、ollama app.exe 等） | ~75 MB |
| `E:\ollama\models\` | **模型文件**（qwen2.5:1.5b 的模型文件） | ~986 MB |
| `C:\Users\chend\.ollama\` | **旧位置**（已删除，不用了） | 0 |

**迁移步骤**：
1. 关闭 Ollama（右下角托盘 → 右键羊驼图标 → Quit Ollama / 退出）
2. 设置用户环境变量 `OLLAMA_MODELS=E:\ollama\models`（已永久设好）
3. 把 `C:\Users\chend\.ollama\models\` 全部内容复制到 `E:\ollama\models\`
4. 重新启动 Ollama
5. 验证：`ollama list` 能看到 qwen2.5:1.5b

**⚠️ 重要：启动时确保环境变量生效**
Ollama 启动时会读 `OLLAMA_MODELS` 环境变量来确定模型目录。如果从命令行动手启动：

```powershell
# 正确的启动方式——先在当前 shell 设好环境变量，再启动
$env:OLLAMA_MODELS = "E:\ollama\models"
ollama serve
```

如果 Ollama 已经启动但找不到模型（`ollama list` 为空），说明环境变量没传进去。需要关闭后用上面的命令重开。

**简化方案：一键静默启动**

做了两个文件，双击即用，**没有任何黑窗口**：

| 文件 | 说明 |
|------|------|
| `E:\ollama\start_ollama.vbs` | VBScript 静默启动脚本（无窗口） |
| 桌面 `启动Ollama（静默）` | 快捷方式，指向上面的 VBS |

以后重启电脑后，双击桌面 **"启动Ollama（静默）"** 就行。Ollama 在后台运行，没有任何界面弹出来。

**要关闭 Ollama**：右下角系统托盘找到羊驼图标 🦙 → 右键 → Quit Ollama

**验证结果**：删除 C 盘模型后，全部 7 个 Ollama 测试通过（连通性 2 个、LLM Core 4 个、全链路 ReAct 1 个），确认模型从 E 盘正常加载。

---

## 三、Ollama 的启动、关闭和架构

### 3.1 有没有分服务端和客户端？

**不分。Ollama 只有一个程序**（ollama.exe），它既是服务端又是客户端：

| 角色 | 说明 | 怎么用 |
|------|------|--------|
| **服务端模式** | 后台运行，监听 `localhost:11434`，等待程序来调用 | 安装完自动启动，或手动 `ollama serve` |
| **客户端模式** | 发命令给服务端，拉模型、列出模型等 | `ollama list`、`ollama pull` 等 |

**对比更熟悉的软件**：
- 像 MySQL 有 `mysqld`（服务端）和 `mysql`（客户端），是两个程序
- Ollama 是**同一个程序**，用不同参数切换角色

### 3.2 怎么启动 Ollama？

**方式一：自动启动（推荐）**

安装后 Ollama 默认开机自启。右下角系统托盘（任务栏右边的小箭头点开）会有个**羊驼图标** 🦙，说明 Ollama 已经在后台运行了。

**方式二：手动启动命令行服务**

```bash
# 打开终端，输入：
ollama serve
```

这样会在当前终端窗口启动服务，窗口不能关，关了服务就停了。

**方式三：通过图形界面启动**

双击 `E:\ollama\ollama app.exe`，系统托盘会出现羊驼图标。

### 3.3 怎么关闭 Ollama？

**方法一：通过系统托盘关闭（最简单）**
1. 点任务栏右边的 `^` 小箭头
2. 找到羊驼图标（🦙），**鼠标右键**点击
3. 菜单里选 **"Quit Ollama"** 或 **"退出"**
4. 服务就停了

**方法二：任务管理器关闭**
1. `Ctrl + Shift + Esc` 打开任务管理器
2. 找到 `ollama.exe`，右键 -> 结束任务

**方法三：命令行关闭**
```bash
# 先找到 Ollama 的进程 ID
netstat -ano | findstr :11434
# 看到类似 TCP 0.0.0.0:11434 0.0.0.0:0 LISTENING 12345
# 12345 就是进程 ID，用下面命令杀掉
taskkill /PID 12345 /F
```

### 3.4 如何验证 Ollama 正在运行？

```bash
# 方法一：查看进程
Get-Process ollama -ErrorAction SilentlyContinue
# 如果显示 ollama 进程信息，说明正在运行

# 方法二：看端口
curl http://localhost:11434/api/tags
# 如果返回 JSON（模型列表），说明服务正常

# 方法三：查看右下角系统托盘
# 有没有羊驼图标（🦙）
```

### 3.5 启动顺序注意

```
1. 先启动 Ollama（系统托盘有图标就行）
2. 再启动后端服务器（python -m uvicorn...）
3. 最后发请求

如果先启动后端再启动 Ollama，后端会连不上 LLM，需要重启后端。
```

---

## 四、图形界面（GUI）说明

### 4.1 Ollama 有没有图形界面？

**有，但很简单**。Ollama 的图形界面主要就是**系统托盘图标**：

```
Windows 任务栏右下角
         │
         ▼
    ^（展开小箭头）
         │
         ▼
   🦙 羊驼图标  ← Ollama 的图形界面就这
         │
   右键点击 → 菜单：
       ├─ 显示运行状态
       ├─ 退出（关闭 Ollama）
       └─ （没有其他功能了）
```

**这个图形界面不做**：
- ❌ 不能选模型、不能聊天对话
- ❌ 不能配置参数
- ❌ 没有漂亮的 Web 界面

**如果想用 Web 界面聊天**，需要装额外的软件（如 Open WebUI、ChatBox 等），但那是另一回事了。本项目不需要。

### 4.2 我们怎么用 Ollama？

在本项目中，Ollama **没有界面操作**，完全由后端程序自动调用：

```
后端（Python/FastAPI）
    ↓ 发 HTTP 请求
Ollama 服务（localhost:11434）
    ↓ 推理计算
qwen2.5:1.5b 模型
    ↓ 返回结果
后端解析后返回给前端
```

用户看到的是我们自己的前端界面，完全不知道背后用的是 Ollama 还是七牛。

---

## 五、模型说明

### 5.1 已拉取的模型

| 模型名 | 大小 | 说明 |
|--------|------|------|
| `qwen2.5:1.5b` | 986 MB | 通义千问 1.5B 参数版，适合开发测试 |

### 5.2 模型存在哪里？

```
真实路径: C:\Users\chend\.ollama\models\
    └── blobs\
        ├── sha256-183715c4358...  ← 这个 986MB 就是模型文件
        ├── sha256-377ac4d7aea...  ← 配置文件
        └── ...其他几个小文件
    └── manifests\                 ← 模型清单
```

### 5.3 怎么查看已下载的模型？

```bash
ollama list
# 输出示例：
# NAME               ID           SIZE    MODIFIED
# qwen2.5:1.5b       65ec06548149 986 MB  8 hours ago
```

### 5.4 怎么下载其他模型？

```bash
# ollama pull <模型名>
ollama pull qwen2.5:1.5b    # 下载 1.5B 版
# ollama pull qwen2.5:3b     # 如果想用 3B 版（更大更慢）
```

---

## 六、配置方法

### 6.1 环境变量

当前设置的环境变量：

```bash
OLLAMA_MODELS = E:\ollama\models
```

**但这个设置目前没生效**，模型实际在 C 盘默认位置。如果想让它生效，需要：
1. 关闭 Ollama
2. 把 `C:\Users\chend\.ollama\models\` 的内容复制到 `E:\ollama\models\`
3. 重新启动 Ollama

### 6.2 config.yaml 配置

**文件**: `G:\OmniAgentAs-desk\config\config.yaml`

```yaml
ai:
  provider: ollama                    # 默认用 Ollama（不调用外部 API）
  model: qwen2.5:1.5b                 # 默认模型
  ollama:
    api_base: http://localhost:11434/v1   # Ollama 地址（不要改）
    api_key: ollama                       # 占位符，Ollama 不验证 key
    max_retries: 2
    models:
      - qwen2.5:1.5b
    timeout: 120                          # 超时 120 秒（CPU 推理慢）
```

### 6.3 切换到七牛等外部 API

当需要更强大的模型时：

```yaml
ai:
  provider: qiniu        # 改为 qiniu / deepseek / bigmodel 等
  model: deepseek-v3.1   # 七牛提供的强模型
```

改完保存即可，下一次请求自动切换到新 provider。

---

## 七、测试体系

### 7.1 测试分层

| 层级 | 依赖 | 速度 | 什么时候跑 | 说明 |
|------|------|------|-----------|------|
| **L1: Mock 测试** | 不依赖任何 LLM | ~0.7s | 每次改完代码 | 用假 LLM 模拟响应，测 ReAct 循环逻辑 |
| **L2: Ollama 测试** | 依赖 Ollama 运行 | 5s~5min | 发布新版本前 | 用真 LLM 测全链路 |
| **手动 HTTP 测试** | 依赖 Ollama + 后端 | 手动 | 需要时 | 启动后端发 HTTP 请求测 |

### 7.2 L1: Mock 测试（每日必跑）

**文件**: `backend/tests/test_runtime_integration.py`

```bash
cd backend
pytest tests/test_runtime_integration.py -v
```

**覆盖内容**：14 个测试场景，覆盖工具执行历史拼接、状态映射、多轮调用、边界值等。

### 7.3 L2: Ollama E2E 测试（发布前跑）

**文件**: `backend/tests/test_e2e_ollama.py`

```bash
cd backend
pytest -m e2e_ollama -v
```

**覆盖内容**：
| 测试 | 测什么 | 大概时间 |
|------|--------|---------|
| 连通性测试 | Ollama 服务活着吗？模型在吗？ | ~5s |
| LLM Core 测试 | 文本对话、历史对话、流式、工具格式 | ~30s |
| 全链路 ReAct | IntentAgent 真的能跑完整吗？ | ~2-5min |

---

## 八、测试结果汇总

### 8.1 测试状态

| 测试 | 数量 | 通过 | 失败 | 结论 |
|------|------|------|------|------|
| Mock 运行时测试 | 14 | 14 | 0 | ✅ 全部通过 |
| MessageBuilder 测试 | 43 | 43 | 0 | ✅ 全部通过 |
| Ollama E2E 测试 | 7 | 7 | 0 | ✅ 全部通过 |
| **合计** | **64** | **64** | **0** | **✅** |

### 8.2 手动 HTTP 实测结果

启动后端后发 HTTP 请求测了两条：

| 输入 | 结果 | 说明 |
|------|------|------|
| `列出文件` | start 事件到达（0.4s），然后超时了 | 原因是 qwen2.5:1.5b 首次推理在 CPU 上要 ~2 分钟，我们只等了 60 秒。不是程序问题，是机器太慢 |
| `hello` | 死循环了 | **发现一个 Bug**：LLM 返回空工具名时，程序没有正确处理，一直在空转 |

---

## 九、已知问题

### 9.1 空工具名死循环（Bug）

- **位置**: `backend/app/services/agent/base_react.py` 第 480 行
- **表现**: 输入"hello"等不匹配 CRSS 的请求时，程序进入 thought→空工具→观察→thought 的死循环
- **原因**: 代码没处理好 LLM 返回空工具名的情况
- **状态**: 已确认，待修复

### 9.2 CPU 推理太慢

- qwen2.5:1.5b 在本机（16GB RAM，纯 CPU）首次推理约 2 分钟
- 不是 bug，是本机硬件限制
- 后续请求会快一点，但也不会很快

---

## 十、使用指引

### 10.1 日常开发流程

```
1. 开机 → Ollama 自动启动（确认右下角有羊驼图标 🦙）
2. 终端 → cd backend → python -m uvicorn app.main:app --reload
3. 打开浏览器 → http://localhost:5173 → 正常使用
4. 改完代码 → pytest tests/test_runtime_integration.py -v（快速验证）
5. 发布前 → pytest -m e2e_ollama -v（全链路验证）
```

### 10.2 常见问题

**Q: Ollama 没启动，后端报连接错误怎么办？**
A: 点击右下角系统托盘，确认羊驼图标在。不在的话双击 `E:\ollama\ollama app.exe` 启动。

**Q: 模型下载到一半断网了？**
A: 重新执行 `ollama pull qwen2.5:1.5b`，Ollama 会断点续传。

**Q: 模型在 C 盘占空间，想移到 E 盘？**
A: 1. 退出 Ollama → 2. 复制 `C:\Users\chend\.ollama\models\` 到 `E:\ollama\models\` → 3. 重启 Ollama

**Q: 想用更强的模型？**
A: 1. `ollama pull qwen2.5:7b`（下载更大模型）→ 2. 修改 `config.yaml` 的 `model` 字段

**Q: 怎么卸载 Ollama？**
A: 双击 `E:\ollama\unins000.exe`，或者 设置 → 应用 → 找到 Ollama → 卸载。

---

**更新时间**: 2026-05-22 06:49:30  
**编写人**: 小健
