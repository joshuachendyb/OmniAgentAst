# LLM调用Prompt中间层设计方案

**创建时间**: 2026-03-24 15:59:58  
**更新时间**: 2026-03-24 18:20:00  
**版本**: v2.1  
**编写人**: 小沈  
**文档类型**: 技术方案

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-03-24 15:59:58 | 小沈 | 初始版本：Prompt中间层设计方案 |
| v2.0 | 2026-03-24 17:15:00 | 小沈 | 优化：整理章节顺序，实施计划移到最后 |
| v2.1 | 2026-03-24 18:20:00 | 小沈 | 补充：客户端信息仅保存数据库，不用于Prompt |

---

## 一、背景分析

### 1.1 问题来源

在分析两个文档的关系时发现信息断层：

| 文档 | 输出的信息 | 状态 |
|------|-----------|------|
| React-field调用-Structured-Outputs-自适应方案 | LLM能力、当前系统、路径格式、命令格式 | ✅ 已设计 |
| ReAct-File调用Prompt验证分析 | 参数命名规则、工具description | ✅ 已实现 |
| **Gap** | 系统信息没有传导到工具Prompt中 | ❌ **缺失** |

### 1.2 问题影响

如果LLM不知道当前是Windows，可能返回：
- 路径格式：`/home/user/file.txt`（Linux格式，Windows无法执行）
- 命令格式：`ls -la`（Linux命令，Windows无法执行）

即使参数名正确（dir_path），路径和命令也无法正确执行。

### 1.3 关键澄清：检测谁的系统？

**重要说明**（小强意见修正）：
- 文件操作是在**服务器**上执行的
- 所以LLM需要知道的是**服务器的OS**，用来决定路径格式和命令
- 客户端OS只作为辅助上下文（告知LLM用户用什么设备访问），不是必需

**正确逻辑**：
```
服务器OS → 决定路径格式(C:\ vs /home/)和命令(dir vs ls)
客户端OS → 仅作为上下文（如："用户在手机上访问"→回复更简洁）
```

---

## 二、方案设计

### 2.1 核心理念

**分层设计**：将系统自适应信息抽取为独立的中间层，各意图的Prompt引用该中间层。

```
┌─────────────────────────────────────────────────────────────┐
│  【Prompt中间层】- 自适应信息层                               │
│  - 服务器OS信息（OS/路径格式/命令格式）← 核心：服务器OS决定    │
│  - 客户端OS信息（可选）← 辅助上下文                           │
│  - 各意图的系统信息配置                                        │
│  - 精细化调试修改的集中点                                     │
└─────────────────────────┬───────────────────────────────────┘
                          ↓ 嵌入
┌─────────────────────────────────────────────────────────────┐
│  【通用Tool Prompt】- 公用层                                 │
│  - 参数命名规则                                             │
│  - input_examples                                            │
│  - 工具description                                           │
│  - 可被file、网络、search、桌面助手等共用                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 方案优点

| 优点 | 说明 |
|------|------|
| **解耦** | 系统信息与工具定义分离 |
| **复用** | 通用Prompt被多种意图共用 |
| **可维护** | 修改系统信息只改中间层 |
| **扩展性** | 后续加桌面助手、网络搜索等只需扩展中间层 |
| **精细化** | 中间层是调试修改的集中点 |

---

## 三、系统信息获取方案

### 3.1 核心原则

**一句话说明**：
- **服务器OS**（必须）：文件操作在服务器上执行，需要服务器OS决定路径格式和命令
- **客户端OS**（可选）：仅作为辅助上下文

### 3.2 实施优先级

| 优先级 | 任务 | 说明 | 用途 |
|--------|------|------|------|
| **P0 必须** | 服务器OS信息传递给LLM | 核心功能，决定路径格式和命令 | **用于Prompt** |
| **P1 可选** | 客户端OS作为辅助上下文 | 锦上添花，告知LLM用户访问设备 | **仅保存数据库** |

**重要说明**：
- **服务器OS** → 用于Prompt（决定路径格式如C:\ vs /home/，命令如dir vs ls）
- **客户端OS** → 只保存在数据库，不用于Prompt（留着以后可能有用）

### 3.3 P0实施：服务器OS获取

**最简单方式：后端自己获取，不需要前端传递**

```python
import platform

def get_server_os() -> str:
    """获取服务器操作系统"""
    system = platform.system()  # Windows / Linux / Darwin
    return system
```

后端通过 `platform.system()` 就能知道自己在什么系统上运行，然后把这个信息嵌入Prompt即可。

### 3.4 P1可选：客户端信息传递

如果需要客户端辅助信息，前端可以获取并传递：

**前端获取方法**（渐进增强）：

```javascript
function getClientInfo() {
    // 1. 获取操作系统
    let client_os = "Unknown";
    if (navigator.userAgentData) {
        client_os = navigator.userAgentData.platform;
    } else {
        const ua = navigator.userAgent;
        if (ua.includes("Windows")) client_os = "Windows";
        else if (ua.includes("Mac")) client_os = "macOS";
        else if (ua.includes("Linux")) client_os = "Linux";
        else if (ua.includes("iPhone")) client_os = "iPhone";
        else if (ua.includes("iPad")) client_os = "iPad";
        else if (ua.includes("Android")) client_os = "Android";
        else client_os = navigator.platform || "Unknown";
    }
    
    // 2. 获取浏览器信息
    const ua = navigator.userAgent;
    let browser = "Unknown";
    if (ua.includes("Chrome")) browser = "Chrome";
    else if (ua.includes("Firefox")) browser = "Firefox";
    else if (ua.includes("Safari")) browser = "Safari";
    else if (ua.includes("Edge")) browser = "Edge";
    
    // 3. 获取设备类型
    const device = navigator.maxTouchPoints > 1 ? "mobile" : "desktop";
    
    return {
        client_os: client_os,
        browser: browser,
        device: device
    };
}
```

**传递方式**：

| 方式 | 说明 |
|------|------|
| **方式一：消息体携带（推荐）** | 保存用户消息时在请求体中携带 client_os |
| **方式二：HTTP请求头** | 每次请求带 `X-Client-OS` 头 |

### 3.5 后端处理

```python
import platform

class SessionService:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}
    
    def save_message(self, session_id: str, message: dict):
        # P0：后端自动获取服务器OS（核心）
        server_os = platform.system()
        
        # P1：可选，前端传递的客户端信息
        client_os = message.get("client_os")
        
        # 存储到session中
        if session_id not in self.sessions:
            self.sessions[session_id] = {}
        
        # 服务器OS必须，客户端OS可选
        client_info = self.sessions[session_id].get("client_info", {})
        if not client_info:
            self.sessions[session_id]["client_info"] = {
                "server_os": server_os,  # P0：必须
                "client_os": client_os   # P1：可选
            }
    
    def get_system_for_prompt(self) -> str:
        """获取系统信息用于Prompt"""
        # 优先使用服务器OS
        return platform.system()
```

### 3.6 兼容方案

如果未来需要区分客户端和服务器（分部署场景）：

```python
def get_system_for_prompt(self, session_id: str = None) -> str:
    """获取系统信息用于Prompt"""
    # P0：始终使用服务器OS（核心）
    return platform.system()

def get_client_info(self, session_id: str) -> dict:
    """获取客户端辅助信息"""
    return self.sessions[session_id].get("client_info", {})
```

---

## 四、架构设计

### 4.1 目录结构

```
backend/app/services/prompts/
├── middle/                          # 【新增】Prompt中间层
│   ├── __init__.py                  # 导出接口
│   ├── system_adapter.py           # 系统信息适配器
│   └── intent_context.py           # 意图上下文（后续扩展）
├── file/                            # file意图专用
│   └── file_prompts.py             # 嵌入中间层 + 专用内容
├── network/                         # 【预留】network意图
├── search/                          # 【预留】search意图
└── desktop/                         # 【预留】桌面助手意图
```

### 4.2 system_adapter.py 输出格式

```python
# 输出示例
{
    "system": "Windows",           # 当前系统（来自客户端）
    "path_format": "C:\\Users\\xxx\\file.txt",
    "commands": {
        "list": "dir",
        "copy": "copy", 
        "delete": "del",
        "read": "type"
    }
}
```

### 4.3 生成的Prompt字符串

```
【当前系统】
Windows

【路径格式】
- Windows: C:\Users\xxx\file.txt
- Linux/Mac: /home/xxx/file.txt

【命令格式】
- list: dir
- copy: copy
- delete: del
- read: type
```

### 4.4 嵌入位置

```
System Prompt 结构：
1. 【当前系统】← 中间层嵌入位置（第1行）
2. 【通用Tool规则】← 文档2的参数命名规则
3. 【任务指令】
```

---

## 五、与现有文档的关系

| 文档 | 角色 | 作用 |
|------|------|------|
| LLM调用-fileStructured-Outputs-自适应方案 | 底层能力检测 | 检测LLM能力和当前系统 |
| **Prompt中间层设计方案** | 中间层 | 统一管理系统信息（来自服务器） |
| LLM-File调用Prompt验证分析 | 上层实现 | 各工具的具体Prompt |

**信息流**：
```
后端 platform.system() → 获取服务器OS → 中间层 → 各意图Prompt → LLM
```

---

## 六、预期效果

| 效果 | 说明 |
|------|------|
| ✅ 服务器Windows | LLM返回 dir C:\xxx 格式 |
| ✅ 服务器Linux | LLM返回 ls /home/xxx 格式 |
| ✅ 服务器Mac | LLM返回 ls /Users/xxx 格式 |
| ✅ 参数名正确 | 继承文档2的设计 |
| ✅ 意图扩展 | 新增network/search/desktop只需引用中间层 |
| ✅ 分部署支持 | 支持server和client分开部署 |

---

## 七、总结

本方案通过引入Prompt中间层，解决系统信息无法传导到工具Prompt的问题。

**核心**：
- **服务器OS**是核心：文件操作在服务器上执行，需要服务器OS决定路径格式和命令
- **客户端OS**是可选：仅作为辅助上下文
- **关键**：服务器OS通过后端 `platform.system()` 获取，无需前端传递

**下一步**：开始实施P0阶段 - 后端通过 `platform.system()` 获取服务器OS并嵌入Prompt。

---

## 八、小强意见（已采纳）

**核心问题**：文件操作在服务器上执行，所以需要服务器OS，不是客户端OS。

| 修改前 | 修改后 |
|--------|--------|
| 客户端OS作为必需 | 服务器OS作为核心(P0)，客户端OS作为可选(P1) |

---

## 九、实施计划

### 9.1 实施步骤（按优先级）

| 优先级 | 任务 | 负责人 | 预计工时 |
|--------|------|--------|----------|
| **P0** | 后端：通过 `platform.system()` 获取服务器OS | 小沈 | 15分钟 |
| **P0** | 后端：创建 middle/ 目录和 system_adapter.py | 小沈 | 1小时 |
| **P0** | 后端：修改 file_prompts.py 嵌入中间层 | 小沈 | 30分钟 |
| **P0** | 验证：Prompt输出包含正确的服务器OS | 小健 | 30分钟 |
| **P1** | 前端：实现 getClientInfo()（可选） | 小强 | 30分钟 |
| **P1** | 前端：传递客户端OS作为辅助（可选） | 小强 | 30分钟 |

### 9.2 实施顺序

```
P0阶段（必须）- 小沈
  1. 后端通过 platform.system() 获取服务器OS
  2. 创建 middle/ 目录和 system_adapter.py
  3. 修改 file_prompts.py 嵌入中间层
  4. 验证Prompt包含正确的服务器OS（小健）

P1阶段（可选）- 小强
  5. 前端实现 getClientInfo()
  6. 传递客户端OS作为辅助
```

---

**文档结束**

**编写时间**: 2026-03-24 15:59:58  
**更新时间**: 2026-03-24 17:15:00  
**编写人**: 小沈  
**版本**: v2.0