# execute_shell_command安全检查方案

**签名**: 北京老陈 2026-06-27

---

## 1. 现状分析

### 1.1 当前实现

**文件**: `backend/app/tools/shell/execute_shell_command.py:219-224`

```python
safety_check = get_tool_safety_checker().check_before_execute(
    "execute_shell_command", {"command": command}
)
if safety_check.blocked:
    logger.warning(f"[Shell安全] 拦截: {safety_check.message}")
    # ... 拒绝执行
```

**安全检查逻辑**: `backend/app/services/safety/tool_safety_checker.py:145-156`

```python
shell_tools = set(all_categories.get(ToolCategory.SHELL, []))
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
    (r"socket\s*\.", "网络Socket操作"),           # ❌ 过度拦截
    (r"requests\.(get|post|put|delete|patch)\s*\(", "HTTP请求(requests)"),  # ❌ 过度拦截
    (r"urllib\.request", "URL请求(urllib)"),      # ❌ 过度拦截
]
```

### 1.2 问题

**问题1**: socket/requests/urllib被过度拦截
- **原因**: 这些模式匹配的是Python代码，但execute_shell_command执行的是PowerShell/CMD命令
- **后果**: 正常的PowerShell命令（如`Invoke-WebRequest`）不会被误判，但逻辑上不清晰

**问题2**: 安全检查过于粗糙
- **当前**: 所有匹配模式直接blocked=True（拒绝执行）
- **问题**: 无法区分"高风险操作"和"中风险操作"
- **例子**: 
  - `Remove-Item -Recurse C:\temp` (高风险，应拒绝)
  - `Get-Process | Where-Object {$_.CPU -gt 100}` (低风险，应允许)

---

## 2. 设计方案

### 2.1 核心原则

**原则1**: execute_shell_command执行的是Shell命令，不是Python代码
- DANGEROUS_PATTERNS中的Python模式（`os.system`、`subprocess`等）不适用于Shell命令
- 应使用Shell命令的危险模式（`rm -rf`、`del /s`等）

**原则2**: 分级检查，而非"一棍子打死"
- **LOW**: 允许执行，记录INFO日志
- **MEDIUM**: 允许执行，记录WARNING日志，提示用户注意
- **HIGH**: 拒绝执行，记录ERROR日志

**原则3**: 安全检查应针对Shell命令语法
- PowerShell危险命令: `Remove-Item -Recurse`、`Format-Volume`、`Stop-Computer`
- CMD危险命令: `del /s`、`format`、`shutdown`

### 2.2 Shell命令危险模式

**PowerShell危险模式**:

| 模式 | 风险等级 | 说明 |
|------|---------|------|
| `Remove-Item\s+.*-Recurse` | HIGH | 递归删除目录 |
| `Remove-Item\s+.*-Force` | MEDIUM | 强制删除文件 |
| `Format-Volume` | HIGH | 格式化卷 |
| `Stop-Computer` | HIGH | 关机 |
| `Restart-Computer` | MEDIUM | 重启 |
| `Set-ExecutionPolicy` | MEDIUM | 修改执行策略 |
| `Invoke-Expression` | MEDIUM | 动态执行命令 |

**CMD危险模式**:

| 模式 | 风险等级 | 说明 |
|------|---------|------|
| `del\s+/s` | HIGH | 递归删除文件 |
| `rd\s+/s` | HIGH | 递归删除目录 |
| `format\s+` | HIGH | 格式化磁盘 |
| `shutdown` | HIGH | 关机/重启 |
| `reg\s+delete` | MEDIUM | 删除注册表项 |

### 2.3 分级检查实现

**数据结构**:

```python
# backend/app/tools/tool_constants.py

SHELL_DANGEROUS_PATTERNS = [
    # HIGH风险 - 拒绝执行
    (r"Remove-Item\s+.*-Recurse", "递归删除目录", "HIGH"),
    (r"Format-Volume", "格式化卷", "HIGH"),
    (r"Stop-Computer", "关机", "HIGH"),
    (r"del\s+/s", "递归删除文件", "HIGH"),
    (r"rd\s+/s", "递归删除目录", "HIGH"),
    (r"format\s+", "格式化磁盘", "HIGH"),
    
    # MEDIUM风险 - 允许执行+WARNING
    (r"Remove-Item\s+.*-Force", "强制删除文件", "MEDIUM"),
    (r"Restart-Computer", "重启", "MEDIUM"),
    (r"Set-ExecutionPolicy", "修改执行策略", "MEDIUM"),
    (r"reg\s+delete", "删除注册表项", "MEDIUM"),
]
```

**安全检查逻辑**:

```python
# backend/app/services/safety/tool_safety_checker.py

def _check_shell_command_risk(self, command: str) -> SafetyResult:
    """Shell命令风险检查 — 分级检查"""
    from app.tools.tool_constants import SHELL_DANGEROUS_PATTERNS
    
    for pattern_str, desc, level in SHELL_DANGEROUS_PATTERNS:
        if re.search(pattern_str, command, re.IGNORECASE):
            if level == "HIGH":
                return SafetyResult(
                    is_safe=False, 
                    blocked=True,
                    message=f"高风险操作: {desc}",
                    safety_level="dangerous"
                )
            elif level == "MEDIUM":
                logger.warning(f"[Shell安全] 中风险操作: {desc}")
                # 允许执行，但记录WARNING
    
    return SafetyResult(is_safe=True, blocked=False)
```

---

## 3. 实施计划

### 3.1 修改文件

1. **tool_constants.py**: 新增`SHELL_DANGEROUS_PATTERNS`
2. **tool_safety_checker.py**: 修改`_check_known_risks`，对shell工具使用Shell模式检查
3. **DANGEROUS_PATTERNS**: 移除socket/requests/urllib（这些是Python模式，不适用于Shell）

### 3.2 测试用例

| 命令 | 预期结果 |
|------|---------|
| `Remove-Item -Recurse C:\temp` | blocked=True (HIGH) |
| `Remove-Item -Force C:\temp\file.txt` | blocked=False + WARNING (MEDIUM) |
| `Get-Process` | blocked=False (安全) |
| `del /s C:\temp` | blocked=True (HIGH) |
| `dir` | blocked=False (安全) |

---

## 4. 与execute_code的区别

| 工具 | 执行内容 | 安全检查重点 |
|------|---------|-------------|
| execute_shell_command | PowerShell/CMD命令 | Shell命令危险模式 |
| execute_code | Python代码 | Python代码注入风险 |

**关键区别**:
- execute_code需要检查`eval(user_input)`、`subprocess.call(user_cmd)`等Python代码注入
- execute_shell_command需要检查`Remove-Item -Recurse`、`del /s`等Shell命令风险

---

## 5. 总结

**核心改进**:
1. 区分Shell命令和Python代码的危险模式
2. 分级检查（HIGH/MEDIUM/LOW），而非"一棍子打死"
3. 移除不适用的Python模式（socket/requests/urllib）

**预期效果**:
- 高风险操作（递归删除、格式化）被拒绝
- 中风险操作（强制删除、重启）允许执行但记录WARNING
- 正常命令不受影响