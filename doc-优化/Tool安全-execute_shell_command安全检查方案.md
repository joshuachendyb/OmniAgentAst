# execute_shell_command安全检查方案

**签名**: 北京老陈 2026-06-27
**变更**: 北京老陈 2026-06-27 复核修正（正则精度/MEDIUM处理/路由逻辑/缺失模式）
**设计复核**: 小欧 2026-06-27 发现别名/CMD顺序/check_fn跳过/换行续行等10项漏洞，修复于v1.1
**设计复核v2**: 小欧 2026-06-27 发现CMD路径前置绕过/MEDIUM消息丢失等3项漏洞，修复于v1.2
**复核修正v3**: 小欧 2026-06-27 14项漏洞逐条3轮复核，13项真问题保留，第6项为假问题（代码逻辑不受顺序影响），修正注释描述
**设计复核v3**: 小健 2026-06-27 6项问题3轮复核，1项真问题（cipher /w:遗漏→补入HIGH），1项语义修正（MEDIUM is_safe=True→False），4项降级为建议（补充说明）
**设计复核v4**: 小健 2026-06-27 对齐execute_code设计原则——检查逻辑从tool_safety_checker.py迁出到独立execute_shell_command_safety.py，SHELL_DANGEROUS_PATTERNS从tool_constants.py迁出到safety文件内聚
**设计复核v5**: 小健 2026-06-27 调用方式对齐execute_code——execute_shell_command.py内部直接调用check_shell_command_risk()，不走框架层（符合SRP+KISS-DIRECT原则）
**复核修正v5**: 小沈 2026-06-27 6项问题3轮复核全部确认：2项逻辑矛盾（is_safe/safety_level）、2项正则遗漏（shutdown -a/format /q D:）、1项死代码、1项代码冗余，已在文档中修正

---

## 1. 现状分析

### 1.1 当前实现

**文件**: `backend/app/tools/shell/execute_shell_command.py:224-229`

```python
safety_check = get_tool_safety_checker().check_before_execute(
    "execute_shell_command", {"command": command}
)
if safety_check.blocked:
    logger.warning(f"[Shell安全] 拦截: {safety_check.message}")
    # ... 拒绝执行
```

**安全检查逻辑**: `backend/app/services/safety/tool_safety_checker.py:127-139`

```python
shell_tools = set(tool_registry.get_categories().get(ToolCategory.SHELL, []))
if tool_name in shell_tools:
    from app.tools.tool_constants import DANGEROUS_PATTERNS
    code = params.get("command") or params.get("code") or ""
    for pattern_str, desc in DANGEROUS_PATTERNS:
        if re.search(pattern_str, code):
            return SafetyResult(is_safe=False, blocked=True, message=f"代码注入: {desc}")
```

**危险模式列表**: `backend/app/tools/tool_constants.py:166-180`

```python
DANGEROUS_PATTERNS = [
    (r"os\.system\s*\(", "系统调用(os.system)"),
    (r"subprocess\.(call|run|Popen|check_output)\s*\(", "子进程调用(subprocess)"),
    (r"shutil\.rmtree\s*\(", "递归删除目录(shutil.rmtree)"),
    (r"os\.remove\s*\(", "删除文件(os.remove)"),
    (r"os\.unlink\s*\(", "删除文件(os.unlink)"),
    (r"eval\s*\(", "动态执行(eval)"),
    (r"exec\s*\(", "动态执行(exec)"),
    (r"compile\s*\(", "动态编译(compile)"),
    (r"open\s*\(.*[\'\"]w[\'\"]", "写入文件操作"),
    (r"socket\s*\.", "网络Socket操作"),           # ❌ Python模式，不适用于Shell
    (r"requests\.(get|post|put|delete|patch)\s*\(", "HTTP请求(requests)"),  # ❌ Python模式
    (r"urllib\.request", "URL请求(urllib)"),      # ❌ Python模式
]
```

### 1.2 问题

**问题1**: DANGEROUS_PATTERNS（Python模式）被错误地用于Shell命令检查
- **原因**: `_check_known_risks` 对所有 SHELL 类别工具统一使用 `DANGEROUS_PATTERNS`
- **后果**: `os.system`、`subprocess`、`eval` 等Python模式对PowerShell/CMD命令毫无意义；Shell真正的危险命令（`Remove-Item -Recurse`、`del /s`）反而漏检

**问题2**: 安全检查过于粗糙——所有匹配一律 blocked=True
- **当前**: 无法区分"高风险操作"和"中风险操作"
- **例子**:
  - `Remove-Item -Recurse C:\temp` (高风险，应拒绝)
  - `Restart-Computer` (中风险，应允许但需用户确认)
  - `Get-Process` (安全，应直接执行)

**问题3**: shell_tools路由未区分工具
- **现状**: `execute_shell_command`、`execute_code`、`shell_session`、`find_command` 全部走同一套 DANGEROUS_PATTERNS
- **实际**: `execute_code` 有自己的安全检查（`_validate_code_safety` + `_js_safety_check`），不应再被 DANGEROUS_PATTERNS 重复拦截
- **实际**: `shell_session` 只管理已启动的后台会话（output/terminate），不执行新命令，不需要危险模式检查
- **实际**: `find_command` 只查找命令路径，不执行命令，不需要危险模式检查

---

## 2. 设计方案

### 2.1 核心原则

**原则1**: execute_shell_command执行的是Shell命令，不是Python代码
- DANGEROUS_PATTERNS中的Python模式（`os.system`、`subprocess`等）不适用于Shell命令
- 应使用Shell命令的危险模式（`Remove-Item -Recurse`、`del /s`等）

**原则2**: 分级检查，而非"一棍子打死"
- **HIGH**: 拒绝执行（blocked=True），记录ERROR日志
- **MEDIUM**: 允许执行但需用户确认（requires_confirmation=True），记录WARNING日志
- 不设LOW级别（无实际使用场景，避免过度设计——YAGNI原则）

**原则3**: 安全检查应针对Shell命令语法
- PowerShell危险命令: `Remove-Item -Recurse`、`Format-Volume`、`Stop-Computer`
- CMD危险命令: `del /s`、`rd /s`、`format`

**原则4**: 路由分流——不同工具用不同检查策略
- `execute_shell_command` → `SHELL_DANGEROUS_PATTERNS`（Shell命令危险模式）
- `execute_code` → `DANGEROUS_PATTERNS`（Python代码注入风险，已有独立检查，不走此分支）
- `shell_session` / `find_command` → 不做代码注入检查

### 2.2 风险等级定义

**与 execute_code 的区别**：execute_code 有 LOW/MEDIUM/HIGH 三级（需区分 `eval("1+1")` 和 `eval(user_input)`），Shell命令无需此区分——命令本身即表达完整语义，不存在"硬编码字符串 vs 变量"的歧义，因此只设两级。

```python
# 以下定义仅用于文档说明，代码中直接使用字符串 "HIGH"/"MEDIUM"
class ShellRiskLevel:
    HIGH = "high"      # 高风险：拒绝执行(blocked=True)，记录ERROR日志
    MEDIUM = "medium"  # 中风险：需用户确认(requires_confirmation=True)，记录WARNING日志
    # 不设LOW级别——Shell命令无"低风险但需记录"的场景（YAGNI原则）
```

| 风险等级 | 处理方式 | 日志级别 | 示例 |
|---------|---------|---------|------|
| **HIGH** | `blocked=True`，拒绝执行 | ERROR | `Remove-Item -Recurse`、`format D:`、`Stop-Computer` |
| **MEDIUM** | `requires_confirmation=True`，需用户确认 | WARNING | `Restart-Computer`、`taskkill /f`、`Start-Process` |

**为什么不设LOW？**

| execute_code 需要 LOW | execute_shell_command 不需要 LOW |
|----------------------|-------------------------------|
| `eval("1+1")` 硬编码字符串 vs `eval(var)` 变量——语义不同 | Shell命令本身即完整语义，无此歧义 |
| `subprocess.run(["python", "script.py"])` 是合法用途 | 安全命令（`dir`、`Get-Process`）直接放行，无需记录 |
| 需要区分"合法但有风险模式"和"完全安全" | 安全命令 = 不匹配任何模式 = 返回 None = 直接放行 |

### 2.3 Shell命令危险模式

**PowerShell危险模式**:
（注意：PowerShell中 `rm`/`del`/`ri`/`erase` 均为 `Remove-Item` 的别名，以下"Remove-Item"模式同时覆盖其别名模式）

| 模式 | 风险等级 | 说明 |
|------|---------|------|
| `(?:Remove-Item|rm|del|ri|erase)\s+.*\b-Recurse\b.*\b-Force\b` | HIGH | 递归+强制删除（组合比单独-Recurse更危险，优先匹配） |
| `(?:Remove-Item|rm|del|ri|erase)\s+(?:.*\b-Recurse\b(?!:\$false\b))` | HIGH | 递归删除目录（排除 `-Recurse:$false` 显式关闭递归的情况） |
| `Invoke-Command` | HIGH | 远程/本地执行任意命令（等价于代码注入） |
| `Format-Volume` | HIGH | 格式化卷 |
| `Stop-Computer` | HIGH | 关机 |
| `Invoke-Expression` | HIGH | 动态执行命令（等价于eval，应HIGH） |
| `(?:Remove-Item|rm|del|ri|erase)\s+.*\b-Force\b` | MEDIUM | 强制删除文件（不含-Recurse的情形） |
| `Restart-Computer` | MEDIUM | 重启 |
| `Set-ExecutionPolicy` | MEDIUM | 修改执行策略 |
| `Stop-Process\s+.*\b-Force\b` | MEDIUM | 强制停止进程 |
| `Start-Process` | MEDIUM | 启动任意进程/可执行文件 |

**CMD危险模式**:
（CMD参数顺序可变，如 `del /q /s`，模式需要处理参数在任意位置的情形）

| 模式 | 风险等级 | 说明 |
|------|---------|------|
| `\bdel\b.*?/s\b` | HIGH | 递归删除文件（路径可前可后：`del /s C:\temp` 或 `del C:\temp /s`） |
| `\brd\b.*?/s\b` | HIGH | 递归删除目录 |
| `\brmdir\b.*?/s\b` | HIGH | 递归删除目录（rmdir的完整形式） |
| `(?<!\w)format\b.*?[A-Za-z]:` | HIGH | 格式化磁盘（`.*?` 处理中间参数如 `format /q D:`） |
| `\bshutdown\b(?!\s+[/-]a\b)` | HIGH | 关机/重启（排除 `/a` 和 `-a` 取消关机） |
| `net\s+user\s+\S+.*\/delete` | HIGH | 删除用户（要求指定用户名，避免 `net user /delete` 帮助命令误判） |
| `reg\s+delete` | MEDIUM | 删除注册表项 |
| `taskkill\s+/f` | MEDIUM | 强制杀进程 |

**正则设计说明**:
- 所有PowerShell参数使用 `\b` 词边界（如 `\b-Recurse\b`），防止 `-RecurseSomething` 误匹配
- `format` 使用 `(?<!\w)format\b.*?[A-Za-z]:` 前导限制避免匹配 `Get-FormatData`、`formatter` 等，`.*?` 惰性匹配处理中间参数如 `format /q D:`，要求冒号结尾避免 `format D`（无盘符冒号，不合法）
- `-Recurse -Force` 组合模式放在 `-Recurse` 之前，优先匹配更危险的组合
- `Invoke-Expression` 升级为HIGH（等价于Python的eval，风险极高）
- PowerShell别名覆盖：`Remove-Item` 的别名 `rm`/`del`/`ri`/`erase` 使用 `(?:Remove-Item|rm|del|ri|erase)` 分组覆盖
- `del` 跨shell说明：`del` 在 PowerShell 中是 `Remove-Item` 的别名（支持 `-Recurse`/`-Force`），在 CMD 中是独立命令（支持 `/s`/`/f`）。PowerShell 别名模式中的 `del -Recurse` 仅在 PowerShell 上下文有效；CMD 的 `del /s` 由独立的 CMD 模式 `\bdel\b.*?/s\b` 覆盖，两者不冲突。若 CMD 用户误输入 `del -Recurse`，该命令在 CMD 中本就执行失败，误拦截无害
- `-Recurse:$false` 排除：追加 `(?!:\$false\b)` 前导排除，显式关闭递归时不误拦
- CMD参数顺序与路径前置：使用 `\bdel\b.*?/s\b` 处理路径在前（`del C:\temp /s`）和flag在前（`del /q /s`）两种情形，`.*?` 惰性匹配确保只匹配到最近的 `/s`
- `shutdown /a` 和 `-a` 排除：追加 `(?!\s+[/-]a\b)` 前导排除，Windows 的 shutdown 同时支持 `/` 和 `-` 参数前缀，取消已计划关机不拦截
- `net user /delete` 用户名要求：`net\s+user\s+\S+` 要求指定用户名，避免 `net user /delete` 帮助命令误判
- `Remove-ItemProperty` 未覆盖说明：PowerShell 的 `Remove-ItemProperty`（删除单个注册表值）风险低于删除整个键，且 `execute_shell_command` 默认 `needs_confirmation=True` 兜底，LLM 极少使用此命令，暂不覆盖
- 反引号换行续行：`re.search` 启用 `re.DOTALL` 标志，`.` 跨行匹配；或模式内用 `[\s\S]*` 替代 `.*`（见2.3节实现）
- 命令名自身加 `\b` 词边界：`\bshutdown\b` 避免 `autoshutdown`、`system-shutdown` 误匹配

### 2.4 分级检查实现

**设计原则对齐**（与 `execute_code分级安全检查方案` 2.3节一致）：

| 情况 | 组织方式 | 本方案 |
|------|---------|--------|
| 规则数量 > 5条 | 单独 `{tool_name}_safety.py` | ✅ 20条规则 → `execute_shell_command_safety.py` |
| 规则复杂（多级判断） | 单独文件 | ✅ HIGH/MEDIUM分级 → 单独文件 |
| 规则特殊（非通用场景） | 单独文件 | ✅ Shell命令审查 → 单独文件 |

**文件结构**：
```
backend/app/tools/shell/
├── execute_shell_command.py              # 主工具
├── execute_shell_command_safety.py       # 安全检查模块（新增）
├── execute_code.py                       # 主工具
└── execute_code_safety.py                # 安全检查模块（已存在）
```

**数据结构**:

```python
# backend/app/tools/shell/execute_shell_command_safety.py — 新增文件

SHELL_DANGEROUS_PATTERNS = [
    # HIGH风险 - 拒绝执行(blocked=True)
    # 组合模式放在单模式之前，便于阅读和维护（MEDIUM仅记录不return，不会降级；HIGH匹配后立即return）
    (r"(?:Remove-Item|rm|del|ri|erase)\s+.*\b-Recurse\b.*\b-Force\b", "递归+强制删除", "HIGH"),
    (r"(?:Remove-Item|rm|del|ri|erase)\s+(?:.*\b-Recurse\b(?!:\$false\b))", "递归删除目录", "HIGH"),
    (r"Invoke-Command", "远程/本地执行命令", "HIGH"),
    (r"Format-Volume", "格式化卷", "HIGH"),
    (r"Stop-Computer", "关机", "HIGH"),
    (r"Invoke-Expression", "动态执行命令", "HIGH"),
    (r"\bdel\b.*?/s\b", "递归删除文件", "HIGH"),
    (r"\brd\b.*?/s\b", "递归删除目录(rd)", "HIGH"),
    (r"\brmdir\b.*?/s\b", "递归删除目录(rmdir)", "HIGH"),
    (r"(?<!\w)format\b.*?[A-Za-z]:", "格式化磁盘", "HIGH"),
    (r"\bshutdown\b(?!\s+[/-]a\b)", "关机/重启", "HIGH"),
    (r"net\s+user\s+\S+.*\/delete", "删除用户", "HIGH"),
    (r"\bcipher\b\s+/w:", "永久数据销毁(cipher /w)", "HIGH"),

    # MEDIUM风险 - 需用户确认(requires_confirmation=True)
    (r"(?:Remove-Item|rm|del|ri|erase)\s+.*\b-Force\b", "强制删除文件", "MEDIUM"),
    (r"Restart-Computer", "重启", "MEDIUM"),
    (r"Set-ExecutionPolicy", "修改执行策略", "MEDIUM"),
    (r"Stop-Process\s+.*\b-Force\b", "强制停止进程", "MEDIUM"),
    (r"Start-Process", "启动任意进程", "MEDIUM"),
    (r"reg\s+delete", "删除注册表项", "MEDIUM"),
    (r"taskkill\s+/f", "强制杀进程", "MEDIUM"),
]
```

**安全检查逻辑**:

```python
# backend/app/tools/shell/execute_shell_command_safety.py — 新增文件

import re
from typing import Optional, Tuple, List

from app.services.safety.tool_safety_checker import SafetyResult
from app.utils.logger import logger


def check_shell_command_risk(command: str) -> Optional[SafetyResult]:
    """Shell命令风险分级检查 — 仅用于execute_shell_command
    HIGH: blocked=True, 拒绝执行
    MEDIUM: requires_confirmation=True, 需用户确认（action_handler.py:70处理确认流程）
    — 北京老陈 2026-06-27
    — 小健 2026-06-27 迁出到独立safety文件（对齐execute_code_safety.py设计原则）
    """
    medium_hit_desc = None

    for pattern_str, desc, level in SHELL_DANGEROUS_PATTERNS:
        # 使用 DOTALL 标志，确保 `.*` 能跨反引号续行的换行匹配
        if re.search(pattern_str, command, re.IGNORECASE | re.DOTALL):
            if level == "HIGH":
                return SafetyResult(
                    is_safe=False,
                    blocked=True,
                    message=f"高风险Shell操作: {desc}",
                    safety_level="dangerous",
                )
            elif level == "MEDIUM" and medium_hit_desc is None:
                medium_hit_desc = desc

    if medium_hit_desc:
        logger.warning(f"[Shell安全] 中风险操作: {medium_hit_desc}")
        return SafetyResult(
            is_safe=False,
            blocked=False,
            requires_confirmation=True,
            message=f"中风险Shell操作: {medium_hit_desc}",
            safety_level="destructive",
        )

    return None
```

**MEDIUM级别处理说明**:

MEDIUM级别设置 `is_safe=False` + `requires_confirmation=True`，触发用户确认流程：
1. `check_before_execute` 返回 `SafetyResult(requires_confirmation=True)`
2. `action_handler.py:70` 检测到 `requires_confirmation`，发送确认请求给用户
3. 用户确认 → 继续执行；用户拒绝 → 中止

**注意**: MEDIUM结果必须从 `_check_known_risks` 返回给 `check_before_execute`，由 `check_before_execute` 的第88行统一处理 `requires_confirmation`。MEDIUM 的 `is_safe=False` + `blocked=False` + `requires_confirmation=True` 三者组合明确表达"不安全但不直接拒绝，需用户确认"的语义，避免 `is_safe=True` 与 `requires_confirmation=True` 的语义矛盾。

**_check_known_risks 集成改造**:

```python
# 替换原 shell_tools 分支（第127-139行）

# Shell命令风险检查 — 仅对execute_shell_command生效
if tool_name == "execute_shell_command":
    from app.tools.shell.execute_shell_command_safety import check_shell_command_risk
    shell_risk = check_shell_command_risk(
        params.get("command") or ""
    )
    if shell_risk is not None:
        return shell_risk

# execute_code — 由execute_code_safety自行管理（见execute_code分级安全检查方案），不在此处检查
# shell_session / find_command — 不做代码注入检查
```

**关键改动**:
- `execute_shell_command` 在工具内部调用 `check_shell_command_risk()`（与 `execute_code` 方式对齐，符合SRP+KISS-DIRECT原则）
- `execute_code` / `shell_session` / `find_command` → 不走 shell 安全检查
- `SHELL_DANGEROUS_PATTERNS` 存放在 `execute_shell_command_safety.py` 内（规则与检查逻辑内聚）

**execute_shell_command 调用方式**（与 execute_code 对齐）:

```python
# backend/app/tools/shell/execute_shell_command.py

from app.tools.shell.execute_shell_command_safety import check_shell_command_risk

def execute_shell_command(command: str, ...):
    # ... 参数校验 ...

    # 安全检查 — 工具内部直接调用，不绕到框架层
    safety_result = check_shell_command_risk(command)
    if safety_result is not None and safety_result.blocked:
        logger.warning(f"[Shell安全] 拦截: {safety_result.message}")
        return build_error(data={"error_detail": safety_result.message}, ...)

    # ... 执行命令 ...
```

**注意**: MEDIUM 级别的 `requires_confirmation=True` 由 `execute_shell_command` 的默认 `needs_confirmation=True` 兜底（工具注册时设置），用户确认流程由 `action_handler.py:70` 统一处理。

---

## 3. 实施计划

### 3.1 实施步骤

| 步骤 | 操作 | 说明 |
|------|------|------|
| **Step 1** | 新建 `execute_shell_command_safety.py` | 独立safety模块，含 `SHELL_DANGEROUS_PATTERNS` + `check_shell_command_risk()` |
| **Step 2** | `execute_shell_command.py` 调用安全检查 | 在执行前调用 `check_shell_command_risk()`，拦截 `blocked=True` 的命令 |
| **Step 3** | 编写单元测试 | 验证所有模式匹配正确性 |
| **Step 4** | 运行回归测试 | 确认不破坏现有功能 |

### 3.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `execute_shell_command_safety.py`（新建） | 1. `SHELL_DANGEROUS_PATTERNS`（20条规则，13 HIGH + 7 MEDIUM） |
| | 2. `check_shell_command_risk()` 分级检查函数 |
| `execute_shell_command.py` | 在执行前调用 `check_shell_command_risk()`，拦截 `blocked=True` 的命令（与 `execute_code` 方式对齐） |

### 3.3 不修改的文件

| 文件 | 原因 |
|------|------|
| `execute_code.py` | 已有独立安全检查（`execute_code_safety`），不受影响 |
| `shell_session.py` | 只管理后台会话，不执行新命令，无需检查 |
| `tool_constants.py` | `SHELL_DANGEROUS_PATTERNS` 存放在 `execute_shell_command_safety.py` 内（规则与检查逻辑内聚），不放在全局常量文件 |
| `tool_safety_checker.py` | 安全检查由 `execute_shell_command.py` 内部直接调用 `check_shell_command_risk()`，不走框架层（与 `execute_code` 方式对齐，符合SRP+KISS-DIRECT原则） |
| `DANGEROUS_PATTERNS` | 🔴 待删除——当前仍有 `tool_fc_helper` 引用，待execute_code迁移后整段删除 |

### 3.4 测试文件与测试要点

**测试文件位置**：`backend/tests/tools/test_shell_command_safety.py`

**测试框架**：pytest

**执行命令**：
```bash
cd backend
pytest tests/tools/test_shell_command_safety.py -v
```

**测试要点分类**：

| 测试类型 | 覆盖范围 | 用例数 |
|---------|---------|--------|
| **HIGH模式匹配** | PowerShell递归删除/强制删除/格式化/关机/动态执行/数据销毁 + CMD递归删除/格式化/关机/删除用户/中间参数 | 17+ |
| **MEDIUM模式匹配** | PowerShell强制删除/重启/停止进程/启动进程 + CMD删除注册表/强制杀进程 | 7+ |
| **安全命令不拦截** | Get-Process/dir等日常命令 | 3+ |
| **误拦截排除** | shutdown /a/net user帮助/-Recurse:$false/Get-FormatData/autoshutdown | 5+ |
| **别名绕过** | rm/del/ri/erase作为Remove-Item别名 | 4+ |
| **CMD参数顺序绕过** | del/rd/rmdir + 中间参数(/q /f) + 路径前置 | 8+ |
| **边界条件** | 反引号换行续行/Invoke-Command/Start-Process | 3+ |

**测试通过标准**：
- `pytest` 返回：X passed, 0 failed, 0 error
- 不存在任何🔴被测代码问题
- 所有🟡测试代码问题首轮修复

### 3.5 测试用例

| 命令 | 预期结果 | 说明 |
|------|---------|------|
| `Remove-Item -Recurse C:\temp` | blocked=True (HIGH) | 递归删除 |
| `Remove-Item -Recurse C:\temp -Force` | blocked=True (HIGH) | 组合模式优先匹配 |
| `Remove-Item -Force C:\temp\file.txt` | requires_confirmation=True (MEDIUM) | 强制删除 |
| `Invoke-Expression "cmd"` | blocked=True (HIGH) | 动态执行=eval |
| `Stop-Computer` | blocked=True (HIGH) | 关机（PowerShell） |
| `Format-Volume` | blocked=True (HIGH) | 格式化卷 |
| `Get-Process` | blocked=False, requires_confirmation=False | 安全命令 |
| `del /s C:\temp` | blocked=True (HIGH) | CMD递归删除 |
| `rmdir /s C:\temp` | blocked=True (HIGH) | CMD递归删除 |
| `format D:` | blocked=True (HIGH) | 格式化磁盘 |
| `format /q D:` | blocked=True (HIGH) | 中间参数/q在盘符前 |
| `Get-FormatData` | blocked=False | format前导限制+词边界，不误判 |
| `shutdown /s` | blocked=True (HIGH) | 关机 |
| `shutdown -a` | blocked=False | 取消关机（减号形式） |
| `Restart-Computer` | requires_confirmation=True (MEDIUM) | 重启 |
| `Set-ExecutionPolicy` | requires_confirmation=True (MEDIUM) | 修改执行策略 |
| `Stop-Process -Force` | requires_confirmation=True (MEDIUM) | 强制停止进程 |
| `reg delete HKCU\Software\Test` | requires_confirmation=True (MEDIUM) | 删除注册表 |
| `taskkill /f /im notepad.exe` | requires_confirmation=True (MEDIUM) | 强制杀进程 |
| `net user test /delete` | blocked=True (HIGH) | 删除用户 |
| `dir` | blocked=False, requires_confirmation=False | 安全命令 |
| **——以下为绕过场景测试——** | | |
| `rm -Recurse C:\temp` | blocked=True (HIGH) | 别名绕过：rm |
| `del -Recurse C:\temp` | blocked=True (HIGH) | 别名绕过：del（PowerShell别名） |
| `ri -Recurse C:\temp` | blocked=True (HIGH) | 别名绕过：ri |
| `erase -Recurse C:\temp` | blocked=True (HIGH) | 别名绕过：erase |
| `del /q /s C:\temp` | blocked=True (HIGH) | CMD参数顺序绕过：/q /s |
| `del /f /s C:\temp` | blocked=True (HIGH) | CMD参数顺序绕过：/f /s |
| `del C:\temp /s` | blocked=True (HIGH) | CMD路径前置绕过：path在前/s在后 |
| `rd /q /s C:\temp` | blocked=True (HIGH) | CMD参数顺序绕过：rd /q /s |
| `rd C:\temp /s` | blocked=True (HIGH) | CMD路径前置绕过：rd path在前 |
| `rmdir /q /s C:\temp` | blocked=True (HIGH) | CMD参数顺序绕过：rmdir /q /s |
| `rmdir C:\temp /s` | blocked=True (HIGH) | CMD路径前置绕过：rmdir path在前 |
| `Remove-Item -Recurse:$false C:\temp` | blocked=False | -Recurse:$false 显式关闭递归 |
| `shutdown /a` | blocked=False | 取消关机，不应拦截 |
| `net user /delete` | blocked=False | 无用户名，仅显示帮助 |
| ``Remove-Item `\n  -Recurse `\n  C:\temp`` | blocked=True (HIGH) | 反引号续行绕过（需 DOTALL） |
| `Invoke-Command -ScriptBlock {Remove-Item -Recurse C:\temp}` | blocked=True (HIGH) | Invoke-Command远程执行 |
| `Invoke-Command -ComputerName SRV01 -ScriptBlock {dir}` | blocked=True (HIGH) | Invoke-Command仅命令本身即HIGH |
| `Start-Process -FilePath "malware.exe"` | requires_confirmation=True (MEDIUM) | Start-Process启动任意进程 |
| `autoshutdown` | blocked=False | shutdown词边界，不误判 |
| `cipher /w:C:\temp` | blocked=True (HIGH) | 永久数据销毁 |
| `Remove-ItemProperty -Path HKLM:\Software\Test -Name MyValue` | blocked=False, requires_confirmation=True | 删除单个注册表值（默认确认兜底） |

### 3.6 验证清单

实施完成后，按以下清单逐项验证：

| 序号 | 验证项 | 验证方法 | 预期结果 |
|------|--------|---------|---------|
| 1 | `SHELL_DANGEROUS_PATTERNS` 定义正确 | `python -c "from app.tools.shell.execute_shell_command_safety import SHELL_DANGEROUS_PATTERNS; print(len(SHELL_DANGEROUS_PATTERNS))"` | 输出模式数量 ≥ 20（13 HIGH + 7 MEDIUM） |
| 2 | `check_shell_command_risk` 可调用 | `python -c "from app.tools.shell.execute_shell_command_safety import check_shell_command_risk; print(check_shell_command_risk('dir'))"` | 返回 None（安全命令） |
| 3 | HIGH命令被拦截 | 同上，传入 `Remove-Item -Recurse C:\temp` | 返回 SafetyResult(blocked=True) |
| 4 | MEDIUM命令需确认 | 同上，传入 `Remove-Item -Force C:\temp` | 返回 SafetyResult(requires_confirmation=True) |
| 5 | `_check_known_risks` 路由正确 | `python -c "from app.services.safety.tool_safety_checker import ToolSafetyChecker; print(ToolSafetyChecker._check_known_risks('execute_shell_command', {'command': 'dir'}))"` | 返回 None |
| 6 | execute_code分支已删除 | 检查 `_check_known_risks` 源码 | 无 `DANGEROUS_PATTERNS` 引用 |
| 7 | 单元测试全量通过 | `pytest tests/tools/test_shell_command_safety.py -v` | X passed, 0 failed, 0 error |
| 8 | 全量回归测试通过 | `pytest` | 不破坏现有功能 |
| 9 | MEDIUM确认流程可用 | 手动触发MEDIUM命令（如 `taskkill /f /im notepad.exe`） | 弹出确认对话框，消息显示"中风险Shell操作: 强制杀进程" |

### 3.7 后续清理：DANGEROUS_PATTERNS迁移

**来源**：execute_code设计文档第7章要求 — shell工具改造后，DANGEROUS_PATTERNS最终删除。

**流程**：

```
Step 1: shell工具改造（本次）
  tool_safety_checker → 改用 execute_shell_command_safety.check_shell_command_risk()
  SHELL_DANGEROUS_PATTERNS → 存放在 execute_shell_command_safety.py（独立safety文件，对齐execute_code_safety设计原则）
  _check_known_risks中execute_code分支 → 删除（由execute_code_safety自行管理）

Step 2: execute_code迁移（execute_code设计文档方案）
  tool_fc_helper._validate_code_safety() → execute_code_safety.validate_code_safety()
  DANGEROUS_PATTERNS → RISK_CHECK_RULES

Step 3: 删除DANGEROUS_PATTERNS
  两个调用方都迁移后（shell端已在本方案中完成，execute_code端待迁移），
  DANGEROUS_PATTERNS无人引用 → 删除整个常量定义
```

**本方案负责**：Step 1（已完成）+ Step 3的前提条件（DANGEROUS_PATTERNS在shell端不再使用）

**边界**：Step 2（execute_code迁移）和Step 3（实际删除）不在本方案范围内，由execute_code设计文档负责。

---

## 4. 与execute_code的区别

| 工具 | 执行内容 | 安全检查机制 | 检查位置 |
|------|---------|-------------|---------|
| execute_shell_command | PowerShell/CMD命令 | `execute_shell_command_safety.check_shell_command_risk()`（SHELL_DANGEROUS_PATTERNS + HIGH/MEDIUM分级） | `execute_shell_command_safety.py` |
| execute_code | Python/JS代码 | `execute_code_safety.validate_code_safety()`（RISK_CHECK_RULES + AST别名解析）+ `_JS_DANGEROUS_PATTERNS`（JS注入） | `execute_code_safety.py` |
| shell_session | 后台会话管理 | 无需代码注入检查 | — |
| find_command | 查找命令路径 | 无需代码注入检查 | — |

**关键区别**:
- `execute_shell_command` 有**独立安全检查模块**：`execute_shell_command_safety.check_shell_command_risk()`（SHELL_DANGEROUS_PATTERNS + HIGH/MEDIUM分级）
- `execute_code` 有**独立安全检查模块**：`execute_code_safety.validate_code_safety()`（RISK_CHECK_RULES + AST别名解析）+ `_js_safety_check`（JS注入）
- 两个工具均遵循同一设计原则：规则数量>5、规则复杂、规则特殊 → 单独 `{tool_name}_safety.py` 文件
- `shell_session` / `find_command` 不执行用户输入的命令/代码，无需代码注入检查
- 两个工具都迁移完毕后，`DANGEROUS_PATTERNS` 无人引用 → 删除（见3.7节）

---

## 5. 总结

**核心改进**:
1. 区分Shell命令和Python代码的危险模式——按工具名精确路由
2. 分级检查（HIGH拒绝/MEDIUM确认），而非"一棍子打死"
3. MEDIUM级别通过 `requires_confirmation=True` 触发用户确认流程（`action_handler.py:70`）
4. 正则精度提升：`\b` 词边界、`format` 前导限制、组合模式优先匹配
5. 补充缺失模式：`rmdir /s`、`taskkill /f`、`-Recurse -Force`组合、`net user /delete`、`Invoke-Expression`升级HIGH

**预期效果**:
- 高风险操作（递归删除、格式化、关机、动态执行）被拒绝
- 中风险操作（强制删除、重启、杀进程）需用户确认
- 正常命令不受影响
- `execute_code` 由自己的 `execute_code_safety` 模块独立管理安全检查
- DANGEROUS_PATTERNS 在两工具迁移完毕后删除（见3.7节）

### 5.2 v1.1 设计复核修复项

**复核人**: 小欧 2026-06-27
**复核方法**: 设计文档逐条审查 + 正则模拟推导 + 边界条件分析

| 编号 | 漏洞 | 严重程度 | 修复方式 |
|------|------|---------|---------|
| 1 | PowerShell别名（rm/del/ri/erase）绕过Remove-Item模式 | 🔴 严重 | 改为 `(?:Remove-Item\|rm\|del\|ri\|erase)` 分组覆盖 |
| 2 | CMD参数顺序（del /q /s）绕过del\s+/s | 🔴 严重 | 改为 `del\s+(?:/[a-zA-Z]\s+)*/s` 处理中间参数 |
| 3 | MEDIUM结果提前return跳过check_fn | 🟡 中 | 重构check_before_execute：MEDIUM不直接return，继续执行check_fn后再覆盖needs_confirm |
| 4 | shutdown /a（取消关机）被误拦截 | 🟡 中 | 追加 `(?!\s+/a\b)` 前导排除 |
| 5 | net user /delete（无用户名帮助命令）被误拦截 | 🟡 中 | 改为 `net\s+user\s+\S+` 要求指定用户名 |
| 6 | 组合模式顺序依赖脆弱 | 🟢 建议 | 加注释说明顺序关系（经3轮复核为假问题：MEDIUM仅记录不return，HIGH匹配后仍会覆盖） |
| 7 | 缺失Invoke-Command（远程/本地任意命令执行） | 🟢 建议 | 新增 `Invoke-Command` HIGH模式 |
| 8 | 缺失Start-Process（启动任意进程） | 🟢 建议 | 新增 `Start-Process` MEDIUM模式 |
| 9 | -Recurse:$false显式关闭递归仍被拦截 | 🟡 中 | 追加 `(?!:\$false\b)` 前导排除 |
| 10 | 反引号换行续行绕过.*不跨行 | 🟡 中 | re.search启用re.DOTALL标志 |
| 11 | 命令名无词边界（autoshutdown误匹配） | 🟢 建议 | `shutdown` 改为 `\bshutdown\b` |

### 5.3 v1.2 设计复核修复项

**复核人**: 小欧 2026-06-27
**复核方法**: 正则逐条模拟推导 + 路径前置边界测试 + 消息流追踪

| 编号 | 漏洞 | 严重程度 | 修复方式 |
|------|------|---------|---------|
| 12 | CMD路径前置绕过（`del C:\temp /s`合法CMD语法） | 🔴 严重 | CMD模式改为 `\bdel\b.*?/s\b`，`.*?` 惰性匹配处理路径在前或flag在前 |
| 13 | MEDIUM确认消息丢失（用户看到空消息弹窗） | 🟡 中 | `check_before_execute` 最终返回保留 `known_risk.message` |
| 14 | `check_fn` 优先级未文档化（可覆盖MEDIUM为HIGH） | 🟢 建议 | 在2.3节补充说明 `check_fn` 优先级高于 `SHELL_DANGEROUS_PATTERNS` |
