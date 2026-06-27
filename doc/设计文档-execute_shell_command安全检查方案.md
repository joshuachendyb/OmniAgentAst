# execute_shell_command安全检查方案

**签名**: 北京老陈 2026-06-27
**变更**: 北京老陈 2026-06-27 复核修正（正则精度/MEDIUM处理/路由逻辑/缺失模式）
**设计复核**: 小欧 2026-06-27 发现别名/CMD顺序/check_fn跳过/换行续行等10项漏洞，修复于v1.1
**设计复核v2**: 小欧 2026-06-27 发现CMD路径前置绕过/MEDIUM消息丢失等3项漏洞，修复于v1.2

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

### 2.2 Shell命令危险模式

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
| `(?<!\w)format\s+[A-Za-z]` | HIGH | 格式化磁盘（加前导限制，避免误匹配Get-FormatData等） |
| `\bshutdown\b(?!\s+/a\b)` | HIGH | 关机/重启（排除 `/a` 取消关机） |
| `net\s+user\s+\S+.*\/delete` | HIGH | 删除用户（要求指定用户名，避免 `net user /delete` 帮助命令误判） |
| `reg\s+delete` | MEDIUM | 删除注册表项 |
| `taskkill\s+/f` | MEDIUM | 强制杀进程 |

**正则设计说明**:
- 所有PowerShell参数使用 `\b` 词边界（如 `\b-Recurse\b`），防止 `-RecurseSomething` 误匹配
- `format` 使用 `(?<!\w)format\s+[A-Za-z]` 前导限制，避免匹配 `Get-FormatData`、`formatter` 等
- `-Recurse -Force` 组合模式放在 `-Recurse` 之前，优先匹配更危险的组合
- `Invoke-Expression` 升级为HIGH（等价于Python的eval，风险极高）
- PowerShell别名覆盖：`Remove-Item` 的别名 `rm`/`del`/`ri`/`erase` 使用 `(?:Remove-Item|rm|del|ri|erase)` 分组覆盖
- `-Recurse:$false` 排除：追加 `(?!:\$false\b)` 前导排除，显式关闭递归时不误拦
- CMD参数顺序与路径前置：使用 `\bdel\b.*?/s\b` 处理路径在前（`del C:\temp /s`）和flag在前（`del /q /s`）两种情形，`.*?` 惰性匹配确保只匹配到最近的 `/s`
- `shutdown /a` 排除：追加 `(?!\s+/a\b)` 前导排除，取消已计划关机不拦截
- `net user /delete` 用户名要求：`net\s+user\s+\S+` 要求指定用户名，避免 `net user /delete` 帮助命令误判
- 反引号换行续行：`re.search` 启用 `re.DOTALL` 标志，`.` 跨行匹配；或模式内用 `[\s\S]*` 替代 `.*`（见2.3节实现）
- 命令名自身加 `\b` 词边界：`\bshutdown\b` 避免 `autoshutdown`、`system-shutdown` 误匹配

### 2.3 分级检查实现

**数据结构**:

```python
# backend/app/tools/tool_constants.py — 第8节后新增

SHELL_DANGEROUS_PATTERNS = [
    # HIGH风险 - 拒绝执行(blocked=True)
    # 注意: 组合模式必须放在单模式之前，确保优先匹配；重排序会导致等级降级
    (r"(?:Remove-Item|rm|del|ri|erase)\s+.*\b-Recurse\b.*\b-Force\b", "递归+强制删除", "HIGH"),
    (r"(?:Remove-Item|rm|del|ri|erase)\s+(?:.*\b-Recurse\b(?!:\$false\b))", "递归删除目录", "HIGH"),
    (r"Invoke-Command", "远程/本地执行命令", "HIGH"),
    (r"Format-Volume", "格式化卷", "HIGH"),
    (r"Stop-Computer", "关机", "HIGH"),
    (r"Invoke-Expression", "动态执行命令", "HIGH"),
    (r"\bdel\b.*?/s\b", "递归删除文件", "HIGH"),
    (r"\brd\b.*?/s\b", "递归删除目录(rd)", "HIGH"),
    (r"\brmdir\b.*?/s\b", "递归删除目录(rmdir)", "HIGH"),
    (r"(?<!\w)format\s+[A-Za-z]", "格式化磁盘", "HIGH"),
    (r"\bshutdown\b(?!\s+/a\b)", "关机/重启", "HIGH"),
    (r"net\s+user\s+\S+.*\/delete", "删除用户", "HIGH"),

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
# backend/app/services/safety/tool_safety_checker.py
# 替换 _check_known_risks 中的 shell_tools 分支（第127-139行）

@staticmethod
def _check_shell_command_risk(command: str) -> Optional["SafetyResult"]:
    """Shell命令风险分级检查 — 仅用于execute_shell_command
    HIGH: blocked=True, 拒绝执行
    MEDIUM: requires_confirmation=True, 需用户确认（action_handler.py:70处理确认流程）
    — 北京老陈 2026-06-27
    """
    from app.tools.tool_constants import SHELL_DANGEROUS_PATTERNS

    medium_hit = None
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
            elif level == "MEDIUM" and medium_hit is None:
                medium_hit = (desc, pattern_str)

    if medium_hit:
        desc, _ = medium_hit
        logger.warning(f"[Shell安全] 中风险操作: {desc}")
        return SafetyResult(
            is_safe=True,
            blocked=False,
            requires_confirmation=True,
            message=f"中风险Shell操作: {desc}",
            safety_level="warning",
        )

    return None
```

**MEDIUM级别处理说明**:

MEDIUM级别设置 `requires_confirmation=True`，触发用户确认流程：
1. `check_before_execute` 返回 `SafetyResult(requires_confirmation=True)`
2. `action_handler.py:70` 检测到 `requires_confirmation`，发送确认请求给用户
3. 用户确认 → 继续执行；用户拒绝 → 中止

**注意**: MEDIUM结果必须从 `_check_known_risks` 返回给 `check_before_execute`，由 `check_before_execute` 的第88行统一处理 `requires_confirmation`。因此 `_check_known_risks` 的返回值需要支持非 `is_safe=True` 的 MEDIUM 情况。

**_check_known_risks 集成改造**:

```python
# 替换原 shell_tools 分支（第127-139行）

# Shell命令风险检查 — 仅对execute_shell_command生效
if tool_name == "execute_shell_command":
    shell_risk = ToolSafetyChecker._check_shell_command_risk(
        params.get("command") or ""
    )
    if shell_risk is not None:
        return shell_risk

# Python代码注入检查 — 仅对execute_code生效
if tool_name == "execute_code":
    from app.tools.tool_constants import DANGEROUS_PATTERNS
    code = params.get("code") or ""
    for pattern_str, desc in DANGEROUS_PATTERNS:
        if re.search(pattern_str, code):
            return SafetyResult(is_safe=False, blocked=True, message=f"代码注入: {desc}")

# shell_session / find_command — 不做代码注入检查
```

**关键改动**:
- 原来按 `shell_tools` 集合（4个工具）统一检查 → 改为按工具名精确路由
- `execute_shell_command` → `SHELL_DANGEROUS_PATTERNS`
- `execute_code` → `DANGEROUS_PATTERNS`（保留Python模式）
- `shell_session` / `find_command` → 不检查（无执行风险）

**check_before_execute 的 MEDIUM 处理**:

当前 `check_before_execute` 第66行 `if known_risk is not None and not known_risk.is_safe` 会跳过 MEDIUM 结果（因为 MEDIUM 的 `is_safe=True`）。需要修改判断逻辑：

```python
# 原代码（第66-68行）:
known_risk = self._check_known_risks(tool_name, params or {})
if known_risk is not None and not known_risk.is_safe:
    known_risk.safety_level = "dangerous"
    return known_risk

# 修改为:
known_risk = self._check_known_risks(tool_name, params or {})
if known_risk is not None:
    if known_risk.blocked:
        known_risk.safety_level = "dangerous"
        return known_risk
    if known_risk.requires_confirmation:
        # 注意: 不能直接return，要先执行 tool_meta.check_fn！
        # 如果先return了，check_fn 的自定义安全检查会被跳过。
        pass  # 继续执行，让下面的 check_fn 和确认流程处理

needs_confirm = self._get_needs_confirmation(tool_meta, params or {})

if tool_meta.check_fn:
    try:
        custom_result = tool_meta.check_fn(params or {})
        if not custom_result.get("is_safe", True):
            return SafetyResult(
                is_safe=False, blocked=True,
                message=custom_result.get("message", "安全检查未通过"),
                safety_level=custom_result.get("safety_level", "dangerous"),
            )
    except Exception as e:
        logger.error(f"[ToolSafetyChecker] check_fn异常,阻止执行: {e}")
        return SafetyResult(is_safe=False, blocked=True,
                message=f"安全检查异常(已阻止): {e}",
                safety_level="dangerous")

# 如果已知风险设置了 requires_confirmation，覆盖 needs_confirm 并保留消息
if known_risk is not None and known_risk.requires_confirmation:
    needs_confirm = True

safety_level = "destructive" if needs_confirm else "safe"
# 保留MEDIUM消息，让用户知道为什么需要确认（如"中风险Shell操作: 强制删除文件"）
message = known_risk.message if known_risk and known_risk.requires_confirmation else ""
return SafetyResult(is_safe=not needs_confirm, requires_confirmation=needs_confirm,
        blocked=False, message=message, safety_level=safety_level)
```

这样 MEDIUM 级别的 `requires_confirmation=True` 能正确传递到 `action_handler` 的用户确认流程，同时 `check_fn` 的自定义检查不会被跳过。

**注意**: 修改后 `known_risk` 与 `needs_confirm` 的关系：
- `known_risk` MEDIUM → `known_risk.requires_confirmation=True` → `needs_confirm` 被覆盖为 True
- `known_risk` HIGH → `known_risk.blocked=True` → 直接返回，不执行后续流程
- `known_risk` None → 正常流程，`needs_confirm` 由 `_get_needs_confirmation` 决定

**`check_fn` 优先级说明**:
- `check_fn` 在 MEDIUM 结果之后执行，但其返回的 `blocked=True` 会**覆盖** MEDIUM 结果
- 即：MEDIUM 命令如果被 `check_fn` 判定为不安全，会被升级为 HIGH（blocked=True）
- 这是正确行为：`check_fn` 是工具级自定义检查，优先级高于通用的 `SHELL_DANGEROUS_PATTERNS`

---

## 3. 实施计划

### 3.1 修改文件

| 文件 | 修改内容 |
|------|---------|
| `tool_constants.py` | 新增 `SHELL_DANGEROUS_PATTERNS`（第8节后） |
| `tool_safety_checker.py` | 1. 新增 `_check_shell_command_risk` 静态方法 |
| | 2. 修改 `_check_known_risks`：shell_tools分支改为按工具名路由 |
| | 3. 修改 `check_before_execute`：known_risk判断支持MEDIUM |

### 3.2 不修改的文件

| 文件 | 原因 |
|------|------|
| `execute_shell_command.py` | 调用方只检查 `blocked`，无需改动；MEDIUM由 `action_handler` 的确认流程处理 |
| `execute_code.py` | 已有独立安全检查（`_validate_code_safety` + `_js_safety_check`），不受影响 |
| `shell_session.py` | 只管理后台会话，不执行新命令，无需检查 |
| `DANGEROUS_PATTERNS` | 保留不动，仍用于 `execute_code` 的代码注入检查 |

### 3.3 测试用例

| 命令 | 预期结果 | 说明 |
|------|---------|------|
| `Remove-Item -Recurse C:\temp` | blocked=True (HIGH) | 递归删除 |
| `Remove-Item -Recurse C:\temp -Force` | blocked=True (HIGH) | 组合模式优先匹配 |
| `Remove-Item -Force C:\temp\file.txt` | requires_confirmation=True (MEDIUM) | 强制删除 |
| `Invoke-Expression "cmd"` | blocked=True (HIGH) | 动态执行=eval |
| `Get-Process` | blocked=False, requires_confirmation=False | 安全命令 |
| `del /s C:\temp` | blocked=True (HIGH) | CMD递归删除 |
| `rmdir /s C:\temp` | blocked=True (HIGH) | CMD递归删除 |
| `format D:` | blocked=True (HIGH) | 格式化磁盘 |
| `Get-FormatData` | blocked=False | format前导限制，不误判 |
| `shutdown /s` | blocked=True (HIGH) | 关机 |
| `Restart-Computer` | requires_confirmation=True (MEDIUM) | 重启 |
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
| `Start-Process -FilePath "malware.exe"` | requires_confirmation=True (MEDIUM) | Start-Process启动任意进程 |
| `autoshutdown` | blocked=False | shutdown词边界，不误判 |

---

## 4. 与execute_code的区别

| 工具 | 执行内容 | 安全检查机制 | 检查位置 |
|------|---------|-------------|---------|
| execute_shell_command | PowerShell/CMD命令 | `SHELL_DANGEROUS_PATTERNS`（Shell命令危险模式） | `tool_safety_checker.py` |
| execute_code | Python/JS代码 | `DANGEROUS_PATTERNS`（Python注入）+ `_JS_DANGEROUS_PATTERNS`（JS注入） | `tool_safety_checker.py` + `execute_code.py` |
| shell_session | 后台会话管理 | 无需代码注入检查 | — |
| find_command | 查找命令路径 | 无需代码注入检查 | — |

**关键区别**:
- `execute_code` 有**双重安全检查**：`tool_safety_checker` 的 `DANGEROUS_PATTERNS`（Python代码注入）+ 自身的 `_validate_code_safety` / `_js_safety_check`
- `execute_shell_command` 改用 `SHELL_DANGEROUS_PATTERNS`（Shell命令危险模式），不再使用 Python 模式
- `shell_session` / `find_command` 不执行用户输入的命令/代码，无需代码注入检查

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
- `execute_code` 的 Python 注入检查不受影响

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
| 6 | 组合模式顺序依赖脆弱 | 🟢 建议 | 加注释警告"重排序会导致等级降级" |
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
