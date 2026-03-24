# LLM调用Prompt中间层设计方案

**创建时间**: 2026-03-24 15:59:58  
**更新时间**: 2026-03-24 17:10:00  
**版本**: v1.7  
**编写人**: 小沈  
**文档类型**: 技术方案

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-03-24 15:59:58 | 小沈 | 初始版本：Prompt中间层设计方案 |
| v1.1 | 2026-03-24 16:15:00 | 小沈 | 新增：客户端系统信息获取方案 |
| v1.2 | 2026-03-24 16:20:00 | 小沈 | 优化：客户端发消息时一起传递系统信息 |
| v1.3 | 2026-03-24 16:30:00 | 小沈 | 研究：浏览器获取OS方法，渐进增强方案 |
| v1.4 | 2026-03-24 16:40:00 | 小沈 | 修复：代码示例使用getClientInfo()，补充移动端映射 |
| v1.5 | 2026-03-24 16:50:00 | 小沈 | 新增：分工说明和实施顺序 |
| v1.6 | 2026-03-24 17:00:00 | 小沈 | 新增：服务器OS信息+浏览器+设备+网络信息，数据库字段 |
| v1.7 | 2026-03-24 17:10:00 | 小沈 | 修复：统一函数名getClientInfo() |

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

**重要说明**：
- **Prompt是给客户端用的**，系统信息应该是**客户端的系统**，不是服务器的系统
- 当前 server 和 client 在一台机器上是偶然情况
- 未来 server 和 client 分开部署是必然要支持的

---

## 二、方案设计

### 2.1 核心理念

**分层设计**：将系统自适应信息抽取为独立的中间层，各意图的Prompt引用该中间层。

```
┌─────────────────────────────────────────────────────────────┐
│  【Prompt中间层】- 自适应信息层                               │
│  - 目标运行系统信息（OS/路径格式/命令格式）                   │
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

## 三、客户端系统信息获取方案

### 3.1 信息来源

**核心原则**：系统信息来自**客户端**，不是服务器。

### 3.2 前端需要获取并传递的客户端信息

用户消息保存时，需要传递以下客户端信息：

| 信息 | 字段名 | 说明 | 状态 |
|------|--------|------|------|
| 客户端操作系统 | client_os | Windows/macOS/Linux/iPhone/iPad/Android | ❌ 需新增 |
| 服务器操作系统 | server_os | 后端运行系统的Windows/Linux/Darwin | ❌ 需新增 |
| 浏览器信息 | browser | 浏览器类型和版本 | ❌ 需新增 |
| 设备信息 | device | 设备类型（桌面/平板/手机） | ❌ 需新增 |
| 网络信息 | network | 网络类型（WIFI/4G/5G） | ❌ 需新增 |
| 显示名称 | display_name | 模型显示名称 | ✅ 已有 |

### 3.3 前端获取客户端系统信息

**浏览器环境获取OS信息的方法**：

| 方法 | 状态 | 浏览器支持 | 返回值 |
|------|------|-----------|--------|
| `navigator.userAgentData` | 🆕 实验性 | 仅Chrome/Edge/Opera | Windows / macOS / Linux |
| `navigator.userAgent` | ✅ 正常 | 全部 | 需解析字符串 |
| `navigator.platform` | ⚠️ 已废弃但仍可用 | 全部 | Win32 / Linux x86_64 / MacIntel |

**推荐实现（渐进增强）**：

```javascript
// 前端获取客户端完整信息
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
    
    // 4. 获取网络类型（如果支持）
    let network = "Unknown";
    if (navigator.connection) {
        network = navigator.connection.effectiveType || "Unknown";
    }
    
    return {
        client_os: client_os,
        browser: browser,
        device: device,
        network: network
    };
}

// 获取客户端完整信息
const clientInfo = getClientInfo();
// { client_os: "Windows", browser: "Chrome", device: "desktop", network: "4g" }
```

**返回值映射**：

| getClientInfo() 返回值 | 含义 |
|---------------------|------|
| Windows | Windows系统 |
| macOS | Apple Mac系统 |
| Linux | Linux系统 |
| Win32 | Windows（fallback） |
| MacIntel | macOS（fallback） |
| Linux x86_64 | Linux（fallback） |
| iPhone | iPhone手机（扩展预留） |
| iPad | iPad平板（扩展预留） |
| Android | 安卓手机（扩展预留） |

### 3.3 传递方式

**推荐方案：在客户端保存用户消息时同时传递系统信息**

```javascript
// 前端保存用户消息时（传递完整客户端信息）
const clientInfo = getClientInfo();
const userMessage = {
    content: userInput,
    timestamp: Date.now(),
    client_os: clientInfo.client_os,
    browser: clientInfo.browser,
    device: clientInfo.device,
    network: clientInfo.network
};
```

**传递方式**：

| 方式 | 说明 |
|------|------|
| **方式一：SSE连接传递** | 建立SSE时传递：`EventSource('/api/v1/chat/stream?client_os=' + navigator.platform)` |
| **方式二：HTTP请求头** | 每次请求带 `X-Client-OS` 头 |
| **方式三：消息体携带（推荐）** | 保存用户消息时在请求体中携带 client_os |

**方式三示例**：
```javascript
// 前端调用保存消息API
fetch('/api/v1/sessions/{id}/messages', {
    method: 'POST',
    body: JSON.stringify({
        content: userInput,
        client_os: getClientInfo()  // 使用 getClientOS 函数获取
    })
});
```

### 3.4 后端接收处理

**在客户端保存用户消息时接收并存储客户端信息**：

**后端自动获取服务器操作系统**：
```python
import platform

def get_server_os() -> str:
    """获取服务器操作系统"""
    system = platform.system()
    # Windows -> Windows, Linux -> Linux, Darwin -> macOS
    return system
```

**数据库存储**：需要在 chat_messages 表新增以下列：
- client_os: 客户端操作系统
- server_os: 服务器操作系统  
- browser: 浏览器信息
- device: 设备类型
- network: 网络类型

**后端接收用户消息时**：
```python
import platform

class SessionService:
    def __init__(self):
        self.sessions: Dict[str, dict] = {}
    
    def save_message(self, session_id: str, message: dict):
        # 从消息体中提取客户端信息
        client_os = message.get("client_os")
        browser = message.get("browser")
        device = message.get("device")
        network = message.get("network")
        
        # 后端自动获取服务器操作系统
        server_os = platform.system()
        
        # 存储到session中
        if session_id not in self.sessions:
            self.sessions[session_id] = {}
        
        # 只在首次设置，后续保持不变
        client_info = self.sessions[session_id].get("client_info", {})
        if not client_info:
            self.sessions[session_id]["client_info"] = {
                "client_os": client_os,
                "server_os": server_os,
                "browser": browser,
                "device": device,
                "network": network
            }
    
    def get_client_info(self, session_id: str) -> dict:
        return self.sessions[session_id].get("client_info", {})
```

### 3.5 兼容方案

如果客户端未传递系统信息，fallback到服务器系统：

```python
import platform

def get_system_for_prompt(self, session_id: str = None) -> str:
    # 优先使用客户端系统信息
    client_info = self.session_service.get_client_info(session_id)
    client_os = client_info.get("client_os") if client_info else None
    
    if client_os:
        return client_os
    
    # Fallback到服务器系统
    return platform.system()
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

## 五、实施计划

### 5.1 实施步骤

| 阶段 | 任务 | 状态 | 预计工时 |
|------|------|------|----------|
| 1 | 前端：实现 getClientInfo() 函数并传递给后端 | ⏳ 待实施 | 30分钟 |
| 2 | 后端：接收并存储客户端系统信息到session | ⏳ 待实施 | 30分钟 |
| 3 | 创建 middle/ 目录和 system_adapter.py | ⏳ 待实施 | 1小时 |
| 4 | 修改 file_prompts.py 嵌入中间层 | ⏳ 待实施 | 30分钟 |
| 5 | 验证Prompt输出包含正确的系统信息 | ⏳ 待实施 | 30分钟 |
| 6 | 扩展network/search等意图 | 📋 后续 | - |

### 5.2 需要修改的文件

| 文件 | 修改内容 | 负责人 |
|------|---------|--------|
| `frontend/src/utils/clientOS.ts` | 新建：getClientInfo() 函数（获取OS/浏览器/设备/网络） | 小强 |
| `frontend/src/services/sse.ts` | 添加 client_os/browser/device/network 参数传递 | 小强 |
| `backend/app/api/v1/sessions.py` | MessageCreate类添加字段 + 数据库表新增列 | 小沈 |
| `backend/app/services/session.py` | 新增 client_info 字段存储 | 小沈 |
| `backend/app/services/prompts/middle/__init__.py` | 新建：导出接口 | 小沈 |
| `backend/app/services/prompts/middle/system_adapter.py` | 新建：系统信息适配器 | 小沈 |
| `backend/app/services/prompts/file/file_prompts.py` | 引入中间层 | 小沈 |

### 5.3 分工说明

| 角色 | 工作内容 |
|------|---------|
| **小强** | 前端工作：实现 getClientInfo() 函数、在保存消息时传递 client_os |
| **小沈** | 后端工作：存储 client_os、创建中间层、修改 file_prompts.py |
| **小健** | 审查工作：代码审查、测试验证 |
| **小资** | 审查工作：方案审查、测试验证 |

### 5.4 实施顺序

```
第一阶段：前端（30分钟）
  ↓ 小强
  1. 创建 frontend/src/utils/clientOS.ts
  2. 修改 sse.ts 传递 client_os

第二阶段：后端（2小时）
  ↓ 小沈  
  3. 修改 session.py 存储 client_os
  4. 创建 middle/ 目录和文件
  5. 修改 file_prompts.py 嵌入中间层

第三阶段：验证（30分钟）
  ↓ 小健 + 小资
  6. 测试验证Prompt输出正确
```

---

## 六、与现有文档的关系

| 文档 | 角色 | 作用 |
|------|------|------|
| React-field调用-Structured-Outputs-自适应方案 | 底层能力检测 | 检测LLM能力和当前系统 |
| **Prompt中间层设计方案** | 中间层 | 统一管理系统信息（来自客户端） |
| ReAct-File调用Prompt验证分析 | 上层实现 | 各工具的具体Prompt |

**信息流**：
```
前端用户发消息 → 消息体携带 client_os → 后端存储到session → 中间层读取 → 各意图Prompt → LLM
```

---

## 七、预期效果

### 7.1 短期效果

| 效果 | 说明 |
|------|------|
| ✅ 客户端Windows | LLM返回 dir C:\xxx 格式 |
| ✅ 客户端Linux | LLM返回 ls /home/xxx 格式 |
| ✅ 客户端Mac | LLM返回 ls /Users/xxx 格式 |
| ✅ 参数名正确 | 继承文档2的设计 |

### 7.2 长期价值

| 价值 | 说明 |
|------|------|
| ✅ 意图扩展 | 新增network/search/desktop只需引用中间层 |
| ✅ 统一调试 | 系统信息修改只在一处 |
| ✅ 精细控制 | 中间层可添加各意图的专用配置 |
| ✅ 分部署支持 | 支持server和client分开部署 |

---

## 八、总结

本方案通过引入Prompt中间层，解决系统信息无法传导到工具Prompt的问题。

- **中间层**：管理客户端系统信息（OS/路径/命令）
- **通用层**：各意图共用的工具定义Prompt
- **好处**：解耦、复用、可维护、扩展、分部署支持
- **关键**：系统信息来自客户端，通过前端传递

**下一步**：开始实施第一阶段，前端获取navigator.platform并传递给后端。

---

**文档结束**

**编写时间**: 2026-03-24 15:59:58  
**更新时间**: 2026-03-24 17:10:00  
**编写人**: 小沈  
**版本**: v1.7