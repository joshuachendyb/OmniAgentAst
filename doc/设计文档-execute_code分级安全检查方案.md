# execute_code分级安全检查方案

**签名**: 北京老陈 2026-06-27

---

## 1. 现状分析

### 1.1 当前实现

**文件**: `backend/app/tools/shell/execute_code.py:106-110`

```python
if safety_check:
    from app.tools.tool_fc_helper import _validate_code_safety
    warnings = _validate_code_safety(code)
    if warnings:
        return {"success": False, "error_detail": f"代码存在安全风险: {', '.join(warnings)}"}
```

**安全检查函数**: `backend/app/tools/tool_fc_helper.py:82-88`

```python
def _validate_code_safety(code: str) -> List[str]:
    """验证代码安全性 — 小沈 2026-05-17"""
    warnings = []
    for pattern, desc in DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            warnings.append(desc)
    return warnings
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
- **原因**: 这些是正常网络库，无代码注入风险
- **后果**: LLM无法使用requests获取数据、无法使用socket进行网络编程

**问题2**: eval/exec检查过于粗糙
- **当前**: 所有eval/exec都被拦截
- **问题**: 无法区分`eval(user_input)`（危险）和`eval("1+1")`（安全）
- **例子**:
  - `eval(input())` - 危险（用户输入注入）
  - `eval("1+1")` - 安全（硬编码表达式）
  - `eval(f"{x}+{y}")` - 中等风险（变量拼接）

**问题3**: subprocess检查过于粗糙
- **当前**: 所有subprocess都被拦截
- **问题**: 无法区分`subprocess.call(user_cmd)`（危险）和`subprocess.call(["git", "status"])`（安全）
- **例子**:
  - `subprocess.call(user_input, shell=True)` - 危险（命令注入）
  - `subprocess.run(["python", "--version"])` - 安全（硬编码命令）

---

## 2. 设计方案

### 2.1 核心原则

**原则1**: 区分"库本身"和"使用方式"
- `socket`、`requests`、`urllib`本身无风险，风险在于用户输入注入
- 应检查是否使用了用户输入，而非禁止整个库

**原则2**: 分级检查，而非"一棍子打死"
- **HIGH**: 拒绝执行（代码注入风险）
- **MEDIUM**: 允许执行+WARNING（潜在风险）
- **LOW**: 允许执行（安全）

**原则3**: 静态分析优先，运行时检查兜底
- 静态分析：检查代码中是否有用户输入变量（如`input()`、`sys.argv`）
- 运行时检查：无法静态判断时，记录WARNING

### 2.2 风险分级

**HIGH风险（拒绝执行）**:

| 模式 | 说明 | 原因 |
|------|------|------|
| `eval\s*\(\s*(input|sys\.argv|os\.getenv)` | eval用户输入 | 代码注入 |
| `exec\s*\(\s*(input|sys\.argv|os\.getenv)` | exec用户输入 | 代码注入 |
| `subprocess\..*\(\s*(input|sys\.argv).*shell\s*=\s*True` | subprocess用户输入+shell=True | 命令注入 |
| `os\.system\s*\(\s*(input|sys\.argv)` | os.system用户输入 | 命令注入 |

**MEDIUM风险（允许执行+WARNING）**:

| 模式 | 说明 | 原因 |
|------|------|------|
| `eval\s*\(` | eval使用（未检测到用户输入） | 潜在代码注入 |
| `exec\s*\(` | exec使用（未检测到用户输入） | 潜在代码注入 |
| `subprocess\..*\(\s*.*shell\s*=\s*True` | subprocess+shell=True | 潜在命令注入 |
| `shutil\.rmtree\s*\(` | 递归删除目录 | 数据破坏风险 |
| `os\.remove\s*\(` | 删除文件 | 数据破坏风险 |

**LOW风险（允许执行）**:

| 模式 | 说明 | 原因 |
|------|------|------|
| `socket\s*\.` | socket使用 | 无代码注入风险 |
| `requests\.` | requests使用 | 无代码注入风险 |
| `urllib\.request` | urllib使用 | 无代码注入风险 |
| `open\s*\(.*[\'\"]w[\'\"]` | 写入文件 | 正常文件操作 |

### 2.3 实现策略

**策略1**: 用户输入变量检测

```python
USER_INPUT_PATTERNS = [
    r"input\s*\(",          # input()
    r"sys\.argv",           # sys.argv
    r"os\.getenv\s*\(",     # os.getenv()
    r"os\.environ",         # os.environ
]
```

**策略2**: 风险模式分级

```python
CODE_RISK_PATTERNS = [
    # HIGH风险 - 拒绝执行
    (r"eval\s*\(\s*(input|sys\.argv|os\.getenv|os\.environ)", "eval用户输入", "HIGH"),
    (r"exec\s*\(\s*(input|sys\.argv|os\.getenv|os\.environ)", "exec用户输入", "HIGH"),
    (r"subprocess\.(call|run|Popen)\s*\([^)]*(input|sys\.argv)[^)]*shell\s*=\s*True", "subprocess用户输入+shell=True", "HIGH"),
    
    # MEDIUM风险 - 允许执行+WARNING
    (r"eval\s*\(", "eval使用", "MEDIUM"),
    (r"exec\s*\(", "exec使用", "MEDIUM"),
    (r"subprocess\.(call|run|Popen)\s*\([^)]*shell\s*=\s*True", "subprocess+shell=True", "MEDIUM"),
    (r"shutil\.rmtree\s*\(", "递归删除目录", "MEDIUM"),
    (r"os\.remove\s*\(", "删除文件", "MEDIUM"),
    (r"os\.unlink\s*\(", "删除文件", "MEDIUM"),
    
    # LOW风险 - 允许执行（不记录日志）
    (r"socket\s*\.", "socket使用", "LOW"),
    (r"requests\.(get|post|put|delete|patch)\s*\(", "requests使用", "LOW"),
    (r"urllib\.request", "urllib使用", "LOW"),
]
```

**策略3**: 分级检查函数

```python
def _validate_code_safety_v2(code: str) -> Tuple[List[str], List[str]]:
    """
    分级代码安全检查
    
    Returns:
        (errors, warnings)
        - errors: HIGH风险，应拒绝执行
        - warnings: MEDIUM风险，允许执行但需警告
    """
    errors = []
    warnings = []
    
    for pattern, desc, level in CODE_RISK_PATTERNS:
        if re.search(pattern, code):
            if level == "HIGH":
                errors.append(desc)
            elif level == "MEDIUM":
                warnings.append(desc)
            # LOW级别不记录
    
    return errors, warnings
```

---

## 3. 实施计划

### 3.1 修改文件

1. **tool_constants.py**: 新增`CODE_RISK_PATTERNS`（替代`DANGEROUS_PATTERNS`）
2. **tool_fc_helper.py**: 新增`_validate_code_safety_v2`（分级检查）
3. **execute_code.py**: 使用新的分级检查函数
4. **tool_safety_checker.py**: 移除execute_code的通用检查（execute_code有自己的检查）

### 3.2 测试用例

| 代码 | 预期结果 |
|------|---------|
| `eval(input())` | errors=["eval用户输入"] (HIGH) |
| `eval("1+1")` | warnings=["eval使用"] (MEDIUM) |
| `subprocess.call(user_cmd, shell=True)` | warnings=["subprocess+shell=True"] (MEDIUM) |
| `subprocess.run(["python", "--version"])` | 无错误无警告 (LOW) |
| `requests.get("https://api.example.com")` | 无错误无警告 (LOW) |
| `socket.socket()` | 无错误无警告 (LOW) |

---

## 4. 与execute_shell_command的区别

| 工具 | 执行内容 | 安全检查重点 |
|------|---------|-------------|
| execute_code | Python/JavaScript代码 | 代码注入风险（eval用户输入、subprocess+shell=True） |
| execute_shell_command | PowerShell/CMD命令 | Shell命令风险（递归删除、格式化） |

**关键区别**:
- execute_code需要检查Python/JavaScript代码中的动态执行和用户输入
- execute_shell_command需要检查Shell命令的危险操作

---

## 5. 总结

**核心改进**:
1. 移除socket/requests/urllib的拦截（LOW风险）
2. 区分eval/exec的用户输入使用（HIGH）和硬编码使用（MEDIUM）
3. 区分subprocess的用户输入+shell=True（HIGH）和硬编码命令（MEDIUM/LOW）
4. 分级检查（HIGH拒绝、MEDIUM警告、LOW允许）

**预期效果**:
- 高风险代码（eval用户输入）被拒绝
- 中风险代码（eval硬编码）允许执行但记录WARNING
- 正常网络编程（socket/requests）不受影响