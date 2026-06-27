# execute_code分级安全检查方案设计

**作者**: 小健  
**日期**: 2026-06-27  
**状态**: 设计完成，待实现

---

## 一、问题分析

### 1.1 当前方案的问题

当前execute_code使用"一棍子打死"的安全检查策略，存在过度拦截问题：

| 模式 | 当前处理 | 问题 |
|------|---------|------|
| `subprocess.run(["python", "script.py"])` | ❌ 拒绝 | **过度拦截**，这是合法用途 |
| `subprocess.run(["rm", "-rf", "/"])` | ❌ 拒绝 | ✅ 正确拦截 |
| `open("test.txt", "w")` | ❌ 拒绝 | **过度拦截**，execute_code在临时目录执行 |
| `open("/etc/passwd", "w")` | ❌ 拒绝 | ⚠️ 可能危险 |
| `requests.get("https://api.com")` | ❌ 拒绝 | **过度拦截**，合法的HTTP请求 |
| `eval("1+1")` | ❌ 拒绝 | **过度拦截**，这是合法计算 |
| `eval(user_input)` | ❌ 拒绝 | ✅ 正确拦截（但无法区分）|

### 1.2 根本原因

**当前方案**：基于模式匹配，只要匹配到就拒绝

**问题**：
- 无法区分合法用途和恶意用途
- 无法根据具体内容判断风险等级
- 一刀切，影响正常使用

### 1.3 当前方案代码

**当前安全检查函数**: `backend/app/tools/tool_fc_helper.py:82-88`

```python
def _validate_code_safety(code: str) -> List[str]:
    """验证代码安全性 — 小沈 2026-05-17"""
    warnings = []
    for pattern, desc in DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            warnings.append(desc)
    return warnings
```

**当前危险模式列表**: `backend/app/tools/tool_constants.py:166-180`

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
# 共12条，其中 socket、requests、urllib 共计3条属于过度拦截
```

---

## 二、方案设计

### 2.1 核心思想

**分级安全检查**：不是"一刀切"，而是"分级检查"

- **低风险（LOW）**：允许执行，记录INFO日志
- **中风险（MEDIUM）**：允许执行，记录WARNING日志
- **高风险（HIGH）**：拒绝执行

### 2.2 风险等级定义

```python
class RiskLevel:
    LOW = "low"        # 低风险：允许执行，INFO日志
    MEDIUM = "medium"  # 中风险：允许执行，WARNING日志
    HIGH = "high"      # 高风险：拒绝执行
```
### 2.3 设计原则

**原则：根据复杂度选择组织方式**

| 情况 | 组织方式 | 示例 |
|------|---------|------|
| **特殊、量大、非常规** | 单独 `{tool_name}_safety.py` 文件 | `execute_code_safety.py` |
| **普通、常规、量小** | 直接在tool代码内检查 | `read_text_file` 的路径检查 |

**判断标准**：
1. ✅ **规则数量 > 5条** → 单独文件
2. ✅ **规则复杂（需要多级判断）** → 单独文件
3. ✅ **规则特殊（非通用场景）** → 单独文件
4. ❌ **规则数量 ≤ 5条** → 工具内检查
5. ❌ **规则简单（单级判断）** → 工具内检查
6. ❌ **规则通用（常规场景）** → 工具内检查

**示例对比**：

| 工具 | 规则数量 | 复杂度 | 组织方式 |
|------|---------|--------|---------|
| `execute_code` | 15+ | 高（多级判断） | ✅ 单独 `execute_code_safety.py` |
| `execute_shell_command` | 10+ | 高（命令审查） | ✅ 单独 `execute_shell_command_safety.py` |
| `read_text_file` | 2 | 低（路径检查） | ❌ 工具内检查 |
| `write_text_file` | 3 | 低（路径+类型检查） | ❌ 工具内检查 |

### 2.4 代码组织结构

**文件命名规范**：`{tool_name}_safety.py`（仅复杂工具）

**示例**：
- `execute_code_safety.py` - execute_code工具的安全检查（复杂，15+规则）
- `execute_shell_command_safety.py` - execute_shell_command工具的安全检查（复杂，10+规则）
- `write_text_file` - 直接在工具内检查（简单，3条规则）

**优点**：
1. ✅ **一目了然**：一看文件名就知道是哪个工具的安全处理
2. ✅ **单一职责**：每个工具的安全检查独立
3. ✅ **易于维护**：修改某工具的安全检查不影响其他工具
4. ✅ **可扩展**：新增工具的安全检查只需新建文件
5. ✅ **避免过度设计**：简单工具不需要单独文件

**避免过度设计**：
- ❌ 不要为每个工具都创建safety文件
- ❌ 简单检查（≤5条规则）直接写在工具内
- ❌ 常规检查（路径、类型等）不需要单独文件

## 三、execute-code代码实现 概要

### 3.1 分级检查规则

#### **subprocess规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `subprocess.run(["python", "script.py"])` | LOW | 执行解释器脚本 | ✅ 允许 |
| `subprocess.run(["rm", "-rf", "/"])` | HIGH | 执行危险系统命令 | ❌ 拒绝 |
| `subprocess.run(["dir"])` | MEDIUM | 其他子进程调用 | ✅ 允许（警告） |

#### **文件操作规则**

> **核心原则**：open()本身安全，关键是write模式。只读模式（r/rb）不检查，写入模式（w/wb/a/ab等）才需要检查。

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `open("file.txt", "r")` | **不检查** | 只读，完全安全 | ✅ 允许 |
| `open("file.txt", "rb")` | **不检查** | 只读二进制，完全安全 | ✅ 允许 |
| `open("file.txt", "w")` | MEDIUM | 写入文件 | ✅ 允许（警告） |
| `open("file.txt", "wb")` | MEDIUM | 写入二进制文件 | ✅ 允许（警告） |
| `open("file.txt", "a")` | MEDIUM | 追加写入文件 | ✅ 允许（警告） |

> **说明**：写入系统文件路径保护——tool内部可调用系统级`path_validator`检查目标路径是否为系统敏感路径，若为系统敏感路径则升级为HIGH拒绝。

#### **eval/exec规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `eval("1+1")` | LOW | eval硬编码字符串 | ✅ 允许 |
| `eval(user_input)` | MEDIUM | eval变量（正则无法区分user_input与complex_expr） | ✅ 允许（警告） |
| `eval(complex_expr)` | MEDIUM | 其他eval调用 | ✅ 允许（警告） |
| `exec("import os; os.system('ls')")` | LOW | exec硬编码字符串 | ✅ 允许 |
| `exec(user_input)` | MEDIUM | exec变量（代码注入风险） | ✅ 允许（警告） |
| `exec(sys.argv[1])` | HIGH | exec用户输入（代码注入风险） | ❌ 拒绝 |
| `compile("1+1","","eval")` | LOW | compile硬编码字符串 | ✅ 允许 |
| `compile(source,"","exec")` | MEDIUM | compile变量（潜在代码注入） | ✅ 允许（警告） |

**eval()是什么？**

`eval()` 是Python内置函数，用于**执行字符串形式的Python代码**：

```python
# 正常用法
eval("1+1")  # 返回 2
eval("2*3")  # 返回 6
```

**为什么eval(user_input)危险？**

**代码注入攻击**：

```python
# 假设user_input来自用户输入
user_input = "__import__('os').system('rm -rf /')"
eval(user_input)  # ❌ 会执行删除命令！

user_input = "open('/etc/passwd', 'r').read()"
eval(user_input)  # ❌ 会读取敏感文件！
```

**问题**：eval会把字符串当Python代码执行，如果字符串来自用户输入，可以执行任意代码！

#### **subprocess shell=True规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `subprocess.run("ls", shell=True)` | MEDIUM | shell=True字符串参数 | ✅ 允许（警告） |
| `subprocess.Popen(cmd, shell=True)` | MEDIUM | shell=True变量参数 | ✅ 允许（警告） |
| `os.popen("ls")` | MEDIUM | os.popen执行命令 | ✅ 允许（警告） |

> **说明**：shell=True本身风险在于参数来源，不在于shell=True本身。已有"用户输入+shell=True"的HIGH规则覆盖真正危险的情况（见用户输入变量检测），因此shell=True统一为MEDIUM。

#### **文件删除规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `os.remove("temp.txt")` | MEDIUM | 删除单个文件 | ✅ 允许（警告） |
| `os.unlink("temp.txt")` | MEDIUM | 删除单个文件 | ✅ 允许（警告） |
| `Path("temp.txt").unlink()` | MEDIUM | pathlib删除文件 | ✅ 允许（警告） |

#### **动态导入规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `__import__('os').system('cmd')` | HIGH | 动态导入+命令执行 | ❌ 拒绝 |
| `importlib.import_module('os')` | MEDIUM | 动态导入模块 | ✅ 允许（警告） |

#### **序列化/原生代码规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `pickle.load(data)` | HIGH | pickle反序列化（RCE风险） | ❌ 拒绝 |
| `pickle.loads(data)` | HIGH | pickle反序列化（RCE风险） | ❌ 拒绝 |
| `ctypes.CDLL("lib.so")` | HIGH | 加载原生共享库 | ❌ 拒绝 |
| `ctypes.cdll.LoadLibrary(...)` | HIGH | 加载原生库（代码执行） | ❌ 拒绝 |

#### **用户输入变量检测**

当 eval/exec/subprocess/os.system 等危险函数**与用户输入变量结合使用**时，风险升级为 HIGH：

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `eval(input())` | HIGH | eval用户输入（**代码注入风险**） | ❌ 拒绝 |
| `exec(sys.argv[1])` | HIGH | exec用户输入（**代码注入风险**） | ❌ 拒绝 |
| `subprocess.run(cmd, shell=True)` + `cmd=input()` | HIGH | subprocess用户输入+shell=True（**命令注入**） | ❌ 拒绝 |
| `os.system(os.getenv("cmd"))` | HIGH | os.system用户输入（**命令注入**） | ❌ 拒绝 |

**用户输入变量来源**：`input()`、`sys.argv`、`os.getenv()`、`os.environ`

```python
# 用户输入变量检测
USER_INPUT_PATTERNS = [
    r"\binput\s*\(",           # input()
    r"\bsys\.argv",            # sys.argv
    r"\bos\.getenv\s*\(",      # os.getenv()
    r"\bos\.environ",          # os.environ
]
```

**检测逻辑**：代码中同时出现危险函数和用户输入变量时，即使内容正则判断为 MEDIUM，也升级为 HIGH 拒绝执行。无用户输入变量的 eval/exec/subprocess 调用保持原分级。

#### **socket、requests、urllib：无风险，不检查**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `socket.socket()` | **无风险** | 正常网络连接 | ✅ 完全允许 |
| `requests.get("https://api.com")` | **无风险** | 正常HTTP请求 | ✅ 完全允许 |
| `urllib.request.urlopen("https://api.com")` | **无风险** | 正常URL请求 | ✅ 完全允许 |

**为什么socket、requests、urllib无风险？**

1. **socket**：
   - 只是建立网络连接
   - execute_code在临时目录执行，没有特殊权限
   - 无法访问敏感资源
   - **不应该被拦截**

2. **requests**：
   - 只是发起HTTP请求
   - 正常的网络操作
   - 无法访问本地敏感文件
   - **不应该被拦截**

3. **urllib**：
   - 标准的URL请求库
   - 与requests同级，同样无代码注入风险
   - **不应该被拦截**

**之前的过度担心**：
- ❌ 担心socket可以建立恶意连接 → 实际无法提权
- ❌ 担心requests可以发起DDoS攻击 → 实际单机无法DDoS
- ❌ 担心urllib可以访问本地文件 → 实际受沙箱限制
- ❌ 担心泄露数据 → 实际execute_code在沙箱环境

---


### 3.2 安全检查规则

**文件**: `backend/app/tools/shell/execute_code_safety.py`

```python
# ============================================================
# execute_code安全检查规则
# ============================================================
RISK_CHECK_RULES: List[Dict[str, Any]] = [
    # ===== subprocess =====
    # 低风险：执行Python/Node等解释器
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(\s*\[[^\]]*?(python|node|python3)",
        "risk": RiskLevel.LOW,
        "desc": "执行解释器脚本（相对安全）",
        "allow": True,
    },
    # 高风险：执行系统命令（rm、del、format等）
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(\s*\[[^\]]*?(rm|del|format|shutdown|reboot)",
        "risk": RiskLevel.HIGH,
        "desc": "执行危险系统命令",
        "allow": False,
    },
    # 中风险：其他subprocess调用（负向前瞻排除LOW匹配的解释器脚本）
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\((?!\s*\[[^\]]*?(?:python|node|python3))",
        "risk": RiskLevel.MEDIUM,
        "desc": "子进程调用（需审查）",
        "allow": True,
    },
    
    # ===== open/write =====
    # 中风险：文件写入操作（只检查write/append模式，只读模式不检查）
    # 正则说明：匹配 open(..., "w"/"wb"/"a"/"ab" 等写入模式
    {
        "pattern": r"open\s*\(.*[\'\"]w[b+]?[\'\"]",
        "risk": RiskLevel.MEDIUM,
        "desc": "文件写入操作（write模式）",
        "allow": True,
    },
    {
        "pattern": r"open\s*\(.*[\'\"]a[b+]?[\'\"]",
        "risk": RiskLevel.MEDIUM,
        "desc": "文件追加操作（append模式）",
        "allow": True,
    },
    
    # ===== eval/exec =====
    # 低风险：eval硬编码字符串
    {
        "pattern": r"eval\s*\(\s*[\'\"]",
        "risk": RiskLevel.LOW,
        "desc": "eval硬编码字符串（相对安全）",
        "allow": True,
    },
    # 中风险：其他eval（负向前瞻排除LOW的字符串字面量）
    # 注：正则无法区分 eval(var) 与 eval(expr)，统一按MEDIUM处理
    {
        "pattern": r"eval\s*\((?!\s*[\'\"])",
        "risk": RiskLevel.MEDIUM,
        "desc": "eval调用（非字面量，需审查）",
        "allow": True,
    },
    
    # ===== exec =====
    # 低风险：exec硬编码字符串
    {
        "pattern": r"exec\s*\(\s*[\'\"]",
        "risk": RiskLevel.LOW,
        "desc": "exec硬编码字符串（相对安全）",
        "allow": True,
    },
    # 中风险：其他exec（负向前瞻排除LOW的字符串字面量）
    {
        "pattern": r"exec\s*\((?!\s*[\'\"])",
        "risk": RiskLevel.MEDIUM,
        "desc": "exec调用（非字面量，需审查）",
        "allow": True,
    },
    
    # ===== compile =====
    # 低风险：compile硬编码字符串
    {
        "pattern": r"compile\s*\(\s*[\'\"]",
        "risk": RiskLevel.LOW,
        "desc": "compile硬编码字符串（相对安全）",
        "allow": True,
    },
    # 中风险：compile动态编译（负向前瞻排除LOW的字符串字面量）
    {
        "pattern": r"compile\s*\((?!\s*[\'\"])",
        "risk": RiskLevel.MEDIUM,
        "desc": "compile动态编译（非字面量，潜在代码注入）",
        "allow": True,
    },
    
    # ===== 用户输入变量 + 危险函数组合 =====
    # 高风险：当 input()/sys.argv/os.getenv/os.environ 与危险函数结合使用
    # 即使内容正则判为 MEDIUM，也升级为 HIGH 拒绝执行
    {
        "pattern": r"eval\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)",
        "risk": RiskLevel.HIGH,
        "desc": "eval用户输入（代码注入风险）",
        "allow": False,
    },
    {
        "pattern": r"exec\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)",
        "risk": RiskLevel.HIGH,
        "desc": "exec用户输入（代码注入风险）",
        "allow": False,
    },
    {
        "pattern": r"subprocess\.(?:run|call|Popen|check_output)\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)[^)]*?shell\s*=\s*True",
        "risk": RiskLevel.HIGH,
        "desc": "subprocess用户输入+shell=True（命令注入风险）",
        "allow": False,
    },
    {
        "pattern": r"os\.system\s*\([^)]*?(?:input|sys\.argv|os\.getenv|os\.environ)",
        "risk": RiskLevel.HIGH,
        "desc": "os.system用户输入（命令注入风险）",
        "allow": False,
    },
    
    # ===== os.system / os.popen =====
    # 中风险：os.system调用（LLM经常使用，不拒绝；用户输入组合已在上面覆盖HIGH）
    {
        "pattern": r"os\.system\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "os.system调用",
        "allow": True,
    },
    {
        "pattern": r"os\.popen\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "os.popen调用",
        "allow": True,
    },
    
    # ===== shutil.rmtree =====
    # 中风险：递归删除（LLM经常需要清理目录，不拒绝）
    {
        "pattern": r"shutil\.rmtree\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "递归删除目录",
        "allow": True,
    },
    
    # ===== subprocess shell=True =====
    # 中风险：shell=True（用户输入组合已在上面覆盖HIGH，此处只处理非用户输入的情况）
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\([^)]*?shell\s*=\s*True",
        "risk": RiskLevel.MEDIUM,
        "desc": "subprocess shell=True",
        "allow": True,
    },
    
    # ===== os.remove / os.unlink =====
    # 中风险：文件删除，可能是合法操作
    {
        "pattern": r"os\.(remove|unlink)\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "os.remove/os.unlink 删除文件",
        "allow": True,
    },
    
    # ===== pathlib.Path.unlink =====
    # 中风险：pathlib 方式删除文件
    {
        "pattern": r"Path\s*\(.*\)\.unlink\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "pathlib 删除文件",
        "allow": True,
    },
    
    # ===== __import__ 动态导入 =====
    # 高风险：动态导入 os 后执行命令
    {
        "pattern": r"__import__\s*\(\s*[\'\"]os[\'\"]\)",
        "risk": RiskLevel.HIGH,
        "desc": "__import__ 动态导入 os（可执行命令）",
        "allow": False,
    },
    
    # ===== importlib 动态导入 =====
    # 中风险：动态导入模块，需审查用途
    {
        "pattern": r"importlib\.import_module\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "importlib 动态导入（需审查）",
        "allow": True,
    },
    
    # ===== pickle 反序列化 =====
    # 高风险：pickle.load/loads 可触发任意代码执行
    {
        "pattern": r"pickle\.(load|loads)\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "pickle 反序列化（RCE 风险）",
        "allow": False,
    },
    
    # ===== ctypes 原生库加载 =====
    # 高风险：加载原生共享库可执行任意代码
    {
        "pattern": r"ctypes\.(CDLL|cdll|windll|oledll)\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "ctypes 加载原生库（代码执行风险）",
        "allow": False,
    },
    
    # ===== socket和requests：无风险，不检查 =====
    # socket - 只是建立网络连接，无法提权
    # requests - 只是HTTP客户端，正常操作
]
```

### 3.3 AST导入别名检测（第二层防御）

#### 问题背景

正则规则通过 `subprocess.`、`open(`、`os.system` 等函数名前缀匹配。攻击者可用 Python 导入别名完全绕过：

```python
import subprocess as sp
sp.run(["rm", "-rf", "/"])      # 不匹配 subprocess. 任何规则

import requests as req
req.get("file:///etc/passwd")   # 不匹配 requests. 任何规则

from os import system as cmd
cmd("rm -rf /")                 # 不匹配 os.system 规则
```

#### 方案：AST解析 + 别名还原

在正则检查前增加一层 AST 解析，专门处理导入别名：

```python
import ast

def _resolve_import_aliases(code: str) -> Dict[str, str]:
    """AST解析代码，返回别名→真实模块名映射
    
    例： import subprocess as sp  →  {"sp": "subprocess"}
         from os import system   →  {} (无别名时不记录)
         from os import system as cmd  →  {"cmd": "os.system"}
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:  # import X as Y 形式
                    aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname:  # from X import Y as Z 形式
                    aliases[alias.asname] = f"{node.module}.{alias.name}" if node.module else alias.name
    return aliases
```

**检查逻辑**：`validate_code_safety` 先调用 `_resolve_import_aliases()` 获取别名映射。对于每个别名，生成与之对应的正则检测，追加到规则检查中。

#### 覆盖的别名组合

| 原始模块 | 别名示例 | 检测到的规则 |
|---------|---------|-------------|
| `subprocess` | `sp.run(...)` | subprocess.run 三档规则 |
| `os` | `o.system(...)` | os.system / os.popen / os.remove |
| `shutil` | `sh.rmtree(...)` | shutil.rmtree |
| `pickle` | `pk.load(...)` | pickle.load/loads |
| `ctypes` | `ct.CDLL(...)` | ctypes.CDLL/cdll/windll/oledll |

### 3.4 安全检查函数

**文件**: `backend/app/tools/shell/execute_code_safety.py`

```python
import re as re_mod
import ast
from typing import List, Dict, Any, Optional

# ... RiskLevel 定义、RISK_CHECK_RULES ...

def _resolve_import_aliases(code: str) -> Dict[str, str]:
    """AST解析，返回别名→真实模块名映射 — 小欧 2026-06-27"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = f"{node.module}.{alias.name}" if node.module else alias.name
    return aliases


def _validate_code_safety_v2(code: str) -> Dict[str, Any]:
    """分级安全检查（三层防御） — 小欧 2026-06-27
     
     第一层：正则规则匹配（RISK_CHECK_RULES，含用户输入组合检测）
     第二层：AST别名检测（_resolve_import_aliases）
     第三层：用户输入变量与危险函数组合升级（嵌入在第一层内，§用户输入变量检测）
    
    使用方式：
        from app.tools.shell.execute_code_safety import _validate_code_safety_v2
        
        result = _validate_code_safety_v2(code)
        if not result["allow"]:
            # 拒绝执行
    
    返回:
    {
        "risk_level": "low/medium/high",
        "warnings": ["警告信息"],
        "allow": True/False,
        "details": ["详细信息"]
    }
    """
    warnings = []
    details = []
    max_risk = RiskLevel.LOW
    allow = True
    
    # ── 第一层：正则规则匹配 ──
    for rule in RISK_CHECK_RULES:
        if re_mod.search(rule["pattern"], code):
            risk = rule["risk"]
            desc = rule["desc"]
            details.append(f"[{risk.upper()}] {desc}")
            if risk == RiskLevel.HIGH:
                max_risk = RiskLevel.HIGH
                allow = False
                warnings.append(desc)
            elif risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                max_risk = RiskLevel.MEDIUM
                warnings.append(desc)
    
    # ── 第二层：AST别名检测 ──
    alias_map = _resolve_import_aliases(code)
    
    # 为常用危险模块预置别名的正则检测
    # 只要代码中出现 alias.dangerous_func(...) 即告警
    ALIAS_PATTERNS = {
        "subprocess": [
            (r"{{}}\.(run|call|Popen|check_output)\s*\(", RiskLevel.MEDIUM,
             "通过别名调用subprocess执行子进程"),
            (r"{{}}\.(run|call|Popen|check_output)\s*\([^)]*?shell\s*=\s*True", RiskLevel.HIGH,
             "通过别名调用subprocess且shell=True（命令注入风险）"),
            (r"{{}}\.(run|call|Popen|check_output)\s*\(\s*\[[^\]]*?(rm|del|format|shutdown|reboot)", RiskLevel.HIGH,
             "通过别名调用subprocess执行危险系统命令"),
        ],
        "os": [
            (r"{{}}\.(system|popen)\s*\(", RiskLevel.HIGH,
             "通过别名调用os执行系统命令"),
            (r"{{}}\.(remove|unlink)\s*\(", RiskLevel.MEDIUM,
             "通过别名调用os删除文件"),
        ],
        "shutil": [
            (r"{{}}\.rmtree\s*\(", RiskLevel.HIGH,
             "通过别名调用shutil递归删除"),
        ],
        "pickle": [
            (r"{{}}\.(load|loads)\s*\(", RiskLevel.HIGH,
              "通过别名调用pickle反序列化（RCE风险）"),
        ],
        "ctypes": [
            (r"{{}}\.(CDLL|cdll|windll|oledll)\s*\(", RiskLevel.HIGH,
             "通过别名调用ctypes加载原生库"),
        ],
    }
    
    for alias, real_module in alias_map.items():
        top_module = real_module.split(".")[0]
        if top_module not in ALIAS_PATTERNS:
            continue
        for pattern_tmpl, risk, desc in ALIAS_PATTERNS[top_module]:
            pattern = pattern_tmpl.format(re_mod.escape(alias))
            if re_mod.search(pattern, code):
                desc_full = f"{desc}（{real_module}→{alias}）"
                details.append(f"[{risk.upper()}] {desc_full}")
                if risk == RiskLevel.HIGH:
                    max_risk = RiskLevel.HIGH
                    allow = False
                    warnings.append(desc_full)
                elif risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                    max_risk = RiskLevel.MEDIUM
                    warnings.append(desc_full)
    
    return {
        "risk_level": max_risk,
        "warnings": warnings,
        "allow": allow,
        "details": details,
    }


# 对外暴露统一入口
validate_code_safety = _validate_code_safety_v2
```

### 3.5 execute_code调用

**文件**: `backend/app/tools/shell/execute_code.py`

```python
from app.tools.shell.execute_code_safety import validate_code_safety

def _execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None, safety_check: bool = True) -> Dict[str, Any]:
    """执行Python代码 — 小健 2026-06-27 使用execute_code_safety模块"""
    if not code or not code.strip():
        return {"success": False, "error_detail": "code参数不能为空"}
    
        if safety_check:
            safety_result = validate_code_safety(code)
            
            risk_level = safety_result["risk_level"]
            warnings = safety_result["warnings"]
            allow = safety_result["allow"]
            details = safety_result["details"]
            
            # strict_mode 配置：MEDIUM 也拒绝
            if risk_level == "medium" and config.safety_check.strict_mode:
                logger.error(f"[安全检查] 严格模式({config.safety_check.strict_mode})中风险也拒绝: {'; '.join(warnings)}")
                return {
                    "success": False,
                    "error_detail": f"严格模式下代码存在中风险: {'; '.join(warnings)}",
                    "params": {"risk_level": risk_level, "warnings": warnings, "details": details}
                }
            
            # 记录安全检查结果
            if risk_level == "low":
                logger.info(f"[安全检查] 低风险: {'; '.join(details)}")
            elif risk_level == "medium":
                logger.warning(f"[安全检查] 中风险: {'; '.join(warnings)}")
            elif risk_level == "high":
                logger.error(f"[安全检查] 高风险，拒绝执行: {', '.join(warnings)}")
                return {
                    "success": False,
                    "error_detail": f"代码存在高风险: {', '.join(warnings)}",
                    "params": {"risk_level": risk_level, "warnings": warnings, "details": details}
                }
    
    # 执行代码...
```

---

## 四、execute-code的安全检测功能的改进效果对比

### 4.1 subprocess

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `subprocess.run(["python", "script.py"])` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截（负向前瞻排除MEDIUM超集） |
| `subprocess.run(["rm", "-rf", "/"])` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 保持安全 |
| `subprocess.run(["dir"])` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |

### 4.2 文件操作

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `open("file.txt", "r")` | ✅ 允许 | ✅ 允许（不检查） | ✅ 只读不检查 |
| `open("file.txt", "w")` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 不再过度拦截 |
| `open("file.txt", "a")` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 不再过度拦截 |

### 4.3 eval/exec

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `eval("1+1")` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `eval(user_input)` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ⚠️ 纯内容判MEDIUM；若检测到 input() 等用户输入源头则升级至 HIGH |
| `eval(complex_expr)` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |
| `eval(input())` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 用户输入检测精确拦截 |
| `exec("import os; os.system('ls')")` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `exec(user_input)` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |
| `exec(input())` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 用户输入检测精确拦截 |
| `compile("1+1","","eval")` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `compile(source,"","exec")` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |

### 4.4 socket和requests

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `socket.socket()` | ❌ 拒绝 | ✅ 完全允许 | ✅ 不再过度拦截 |
| `requests.get("https://api.com")` | ❌ 拒绝 | ✅ 完全允许 | ✅ 不再过度拦截 |
| `urllib.request.urlopen("https://api.com")` | ❌ 拒绝 | ✅ 完全允许 | ✅ 不再过度拦截 |

### 4.5 subprocess shell=True

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `subprocess.run("ls", shell=True)` | ⚠️ 未检测（正则漏过） | ✅ 允许（MEDIUM） | ✅ 分级处理，不再一棍子打死 |
| `os.popen("ls")` | ⚠️ 未检测（函数未覆盖） | ✅ 允许（MEDIUM） | ✅ 分级处理 |
| `subprocess.run(sys.argv[1], shell=True)` | ⚠️ 未检测 | ❌ 拒绝（HIGH） | ✅ 用户输入+shell=True精确拦截 |

### 4.6 文件删除

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `os.remove("temp.txt")` | ⚠️ 未检测 | ✅ 允许（MEDIUM） | ✅ 分级处理 |

### 4.7 动态导入 / 反序列化 / 原生代码

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `__import__('os').system('cmd')` | ⚠️ 未检测 | ❌ 拒绝（HIGH） | ✅ 新增覆盖 |
| `pickle.load(data)` | ⚠️ 未检测 | ❌ 拒绝（HIGH） | ✅ 新增覆盖 |
| `ctypes.CDLL("lib.so")` | ⚠️ 未检测 | ❌ 拒绝（HIGH） | ✅ 新增覆盖 |

### 4.8 导入别名绕过

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `import subprocess as sp; sp.run(["rm","-rf","/"])` | ⚠️ 完全绕过 | ❌ 拒绝（HIGH） | ✅ AST检测覆盖 |
| `from os import system as cmd; cmd("rm -rf /")` | ⚠️ 完全绕过 | ❌ 拒绝（HIGH） | ✅ AST检测覆盖 |

---

## 五、与 execute_shell_command 的区别

| 工具 | 执行内容 | 安全检查重点 |
|------|---------|-------------|
| execute_code | Python/JavaScript代码 | 代码注入风险（eval用户输入、subprocess+shell=True、AST别名绕过） |
| execute_shell_command | PowerShell/CMD命令 | Shell命令风险（递归删除、格式化、系统命令） |

**关键区别**：
- execute_code 需要检查 Python/JavaScript 代码中的**动态执行**和**用户输入**，分级细（LOW/MEDIUM/HIGH），双层防御（正则+AST）
- execute_shell_command 需要检查 Shell 命令的**危险操作**，规则直接（HIGH/MEDIUM 两级）

---

## 六、方案优点

### 6.1 核心优点

1. ✅ **不再一棍子打死**：根据具体内容判断风险
2. ✅ **细粒度检查**：区分合法用途和恶意用途
3. ✅ **分级处理**：低风险允许，中风险警告，高风险拒绝
4. ✅ **可扩展**：容易添加新规则
5. ✅ **日志清晰**：记录每个风险等级

### 6.2 安全性保证

- ✅ **高风险操作仍然拒绝**：如 `rm -rf /`、`eval(user_input)`
- ✅ **中风险有警告**：提醒开发者注意
- ✅ **低风险有日志**：可追溯

### 6.3 可用性提升

- ✅ **允许合法的subprocess调用**：如执行Python脚本
- ✅ **允许合法的文件写入**：如写入临时文件
- ✅ **允许合法的HTTP请求**：如调用API（完全允许，不检查）
- ✅ **允许合法的网络连接**：如socket（完全允许，不检查）
- ✅ **允许合法的eval调用**：如计算表达式

---

## 七、实施计划

### 7.1 实施步骤

1. **Step 1**: 创建 `backend/app/tools/shell/execute_code_safety.py`
2. **Step 2**: 实现安全检查引擎 — 第一层 `RISK_CHECK_RULES`（正则规则，含用户输入组合检测）+ 第二层 `_resolve_import_aliases()`（AST别名解析，含shell=True和危险命令的HIGH检测）
3. **Step 3**: 修改 `execute_code.py` 调用 `execute_code_safety` 模块
4. **Step 4**: 编写单元测试 `test_execute_code_safety.py`
5. **Step 5**: 更新文档

**文件结构**：
```
backend/app/tools/shell/
├── execute_code.py              # 主工具
├── execute_code_safety.py       # 安全检查模块（新增）
├── execute_shell_command.py     # 主工具
└── execute_shell_command_safety.py  # 安全检查模块（未来）
```

### 7.2 测试用例

```python
def test_validate_code_safety():
    """测试分级安全检查 — 小健 2026-06-27"""
    from app.tools.shell.execute_code_safety import validate_code_safety
    
    # LOW风险：允许
    result = validate_code_safety('subprocess.run(["python", "script.py"])')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # HIGH风险：拒绝
    result = validate_code_safety('subprocess.run(["rm", "-rf", "/"])')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # MEDIUM风险：允许但有警告
    result = validate_code_safety('subprocess.run(["dir"])')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
    assert len(result["warnings"]) > 0

    # 别名绕过：import subprocess as sp → sp.run 应被拦截
    result = validate_code_safety('import subprocess as sp; sp.run(["rm", "-rf", "/"])')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # 别名绕过：from os import system as cmd → cmd() 应被拦截
    result = validate_code_safety('from os import system as cmd; cmd("rm -rf /")')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # 别名绕过：import pickle as pk → pk.load 应被拦截
    result = validate_code_safety('import pickle as pk; pk.load(data)')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # AST正确解析：无别名的正常调用不应被误判
    result = validate_code_safety('import subprocess; subprocess.run(["python", "script.py"])')
    assert result["risk_level"] == "low"  # 触发LOW规则
    assert result["allow"] == True
    
    # ===== 用户输入变量检测 =====
    # eval(input()) 应被拦截（用户输入+危险函数组合）
    result = validate_code_safety('eval(input())')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # eval("1+1") 应允许（纯字面量，无用户输入）
    result = validate_code_safety('eval("1+1")')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # subprocess + shell=True + sys.argv 应被拦截
    result = validate_code_safety('subprocess.run(sys.argv[1], shell=True)')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # ===== exec测试 =====
    # exec硬编码字符串（LOW）
    result = validate_code_safety('exec("import os; os.system(\'ls\')")')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # exec变量（MEDIUM）
    result = validate_code_safety('exec(user_input)')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
    
    # exec用户输入（HIGH）
    result = validate_code_safety('exec(sys.argv[1])')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # ===== compile测试 =====
    # compile硬编码字符串（LOW）
    result = validate_code_safety('compile("1+1", "", "eval")')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # compile变量（MEDIUM）
    result = validate_code_safety('compile(source, "", "exec")')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
    
    # ===== 负向测试：无风险操作不拦截 =====
    # socket不应被拦截
    result = validate_code_safety('s = socket.socket()')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # requests不应被拦截
    result = validate_code_safety('requests.get("https://api.com")')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # urllib不应被拦截
    result = validate_code_safety('urllib.request.urlopen("https://api.com")')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # ===== 多规则叠加测试 =====
    # subprocess执行Python解释器（LOW）+ 危险命令（HIGH）
    # 应判定为HIGH（取最高风险）
    result = validate_code_safety('subprocess.run(["python", "-c", "rm -rf /"])')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # Python解释器（LOW）+ 普通subprocess（MEDIUM）
    # 应判定为MEDIUM（但LOW规则匹配，MEDIUM被负向前瞻排除）
    result = validate_code_safety('subprocess.run(["python", "-c", "print(1)"])')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # ===== os.system / shutil.rmtree =====
    # os.system应为MEDIUM（不拒绝）
    result = validate_code_safety('os.system("dir")')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
    
    # shutil.rmtree应为MEDIUM（不拒绝）
    result = validate_code_safety('shutil.rmtree("build/")')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
    
    # ===== 文件写入统一MEDIUM =====
    # open写入统一MEDIUM，不区分文件名
    result = validate_code_safety('open("test.txt", "w")')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
    
    result = validate_code_safety('open("data.txt", "w")')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
```

---

## 八、风险与缓解

### 8.1 潜在风险

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| 规则不够完善 | 可能遗漏某些危险模式 | 持续更新规则，社区反馈 |
| 误判 | 可能错误判断风险等级 | 提供配置开关，允许关闭检查 |
| 绕过 | 攻击者可能绕过检查 | 多层防御，结合其他安全机制 |

### 8.2 缓解措施

1. **配置开关**：
   ```python
   # config.yaml
   safety_check:
     enabled: true
     strict_mode: false  # 严格模式：true=MEDIUM也拒绝（§3.5代码已处理）；false=MEDIUM允许但有警告
   ```

2. **多层防御**：
   - 代码静态检查（本方案）
   - 运行时沙箱隔离
   - 权限控制

3. **持续更新**：
   - 定期审查规则
   - 收集社区反馈
   - 跟踪新的攻击模式

---

## 九、总结

**本方案通过分级安全检查，解决了当前"一棍子打死"的问题，在保证安全性的同时提升了可用性。**

**核心改进**：
- ✅ 不再过度拦截合法用途
- ✅ 保持对高风险操作的拦截
- ✅ 提供清晰的日志和警告
- ✅ 易于扩展和维护

**下一步**：实施并验证效果。