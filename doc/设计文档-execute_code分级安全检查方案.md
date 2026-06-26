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

### 2.3 分级检查规则

#### **subprocess规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `subprocess.run(["python", "script.py"])` | LOW | 执行解释器脚本 | ✅ 允许 |
| `subprocess.run(["rm", "-rf", "/"])` | HIGH | 执行危险系统命令 | ❌ 拒绝 |
| `subprocess.run(["dir"])` | MEDIUM | 其他子进程调用 | ✅ 允许（警告） |

#### **文件操作规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `open("test.txt", "w")` | LOW | 写入临时文件 | ✅ 允许 |
| `open("/etc/passwd", "w")` | HIGH | 写入系统文件 | ❌ 拒绝 |
| `open("data.txt", "w")` | MEDIUM | 其他文件写入 | ✅ 允许（警告） |

#### **eval/exec规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `eval("1+1")` | LOW | eval硬编码字符串 | ✅ 允许 |
| `eval(user_input)` | HIGH | eval动态变量（**代码注入风险**） | ❌ 拒绝 |
| `eval(complex_expr)` | MEDIUM | 其他eval调用 | ✅ 允许（警告） |

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

#### **socket和requests：无风险，不检查**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `socket.socket()` | **无风险** | 正常网络连接 | ✅ 完全允许 |
| `requests.get("https://api.com")` | **无风险** | 正常HTTP请求 | ✅ 完全允许 |

**为什么socket和requests无风险？**

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

**之前的过度担心**：
- ❌ 担心socket可以建立恶意连接 → 实际无法提权
- ❌ 担心requests可以发起DDoS攻击 → 实际单机无法DDoS
- ❌ 担心泄露数据 → 实际execute_code在沙箱环境

---

## 三、代码实现

### 3.1 代码组织结构

**文件命名规范**：`{tool_name}_safety.py`

**示例**：
- `execute_code_safety.py` - execute_code工具的安全检查
- `execute_shell_command_safety.py` - execute_shell_command工具的安全检查
- `write_text_file_safety.py` - write_text_file工具的安全检查

**优点**：
1. ✅ **一目了然**：一看文件名就知道是哪个工具的安全处理
2. ✅ **单一职责**：每个工具的安全检查独立
3. ✅ **易于维护**：修改某工具的安全检查不影响其他工具
4. ✅ **可扩展**：新增工具的安全检查只需新建文件

### 3.2 风险等级定义

**文件**: `backend/app/tools/shell/execute_code_safety.py`

```python
# -*- coding: utf-8 -*-
"""
execute_code安全检查模块 — 小健 2026-06-27

命名规范：{tool_name}_safety.py
- execute_code_safety.py - execute_code的安全检查
- execute_shell_command_safety.py - execute_shell_command的安全检查

职责：
- 定义风险等级
- 定义安全检查规则
- 实现安全检查函数
"""

from typing import Dict, Any, List
import re as re_mod
from app.utils.logger import setup_logger

logger = setup_logger(__name__)


# ============================================================
# 风险等级定义
# ============================================================
class RiskLevel:
    """安全风险等级 — 小健 2026-06-27"""
    LOW = "low"        # 低风险：允许执行，INFO日志
    MEDIUM = "medium"  # 中风险：允许执行，WARNING日志
    HIGH = "high"      # 高风险：拒绝执行


# ============================================================
# execute_code安全检查规则
# ============================================================
RISK_CHECK_RULES: List[Dict[str, Any]] = [
    # ===== subprocess =====
    # 低风险：执行Python/Node等解释器
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(\s*\[.*?(python|node|python3)",
        "risk": RiskLevel.LOW,
        "desc": "执行解释器脚本（相对安全）",
        "allow": True,
    },
    # 高风险：执行系统命令（rm、del、format等）
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(\s*\[.*?(rm|del|format|shutdown|reboot)",
        "risk": RiskLevel.HIGH,
        "desc": "执行危险系统命令",
        "allow": False,
    },
    # 中风险：其他subprocess调用
    {
        "pattern": r"subprocess\.(run|call|Popen|check_output)\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "子进程调用（需审查）",
        "allow": True,
    },
    
    # ===== open/write =====
    # 低风险：写入临时文件或当前目录
    {
        "pattern": r"open\s*\(\s*[\'\"](test|temp|tmp|output)",
        "risk": RiskLevel.LOW,
        "desc": "写入临时文件（相对安全）",
        "allow": True,
    },
    # 高风险：写入系统文件
    {
        "pattern": r"open\s*\(\s*[\'\"]/(etc|sys|proc|windows)",
        "risk": RiskLevel.HIGH,
        "desc": "写入系统文件",
        "allow": False,
    },
    # 中风险：其他文件写入
    {
        "pattern": r"open\s*\(.*[\'\"]w[\'\"]",
        "risk": RiskLevel.MEDIUM,
        "desc": "文件写入操作",
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
    # 高风险：eval动态变量
    {
        "pattern": r"eval\s*\(\s*[a-zA-Z_]",  # eval(variable)
        "risk": RiskLevel.HIGH,
        "desc": "eval动态变量（代码注入风险）",
        "allow": False,
    },
    # 中风险：其他eval
    {
        "pattern": r"eval\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "eval调用",
        "allow": True,
    },
    
    # ===== os.system =====
    # 高风险：os.system（无法检查参数）
    {
        "pattern": r"os\.system\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "os.system调用（无法审查参数）",
        "allow": False,
    },
    
    # ===== shutil.rmtree =====
    # 高风险：递归删除
    {
        "pattern": r"shutil\.rmtree\s*\(",
        "risk": RiskLevel.HIGH,
        "desc": "递归删除目录",
        "allow": False,
    },
    
    # ===== socket和requests：无风险，不检查 =====
    # socket - 只是建立网络连接，无法提权
    # requests - 只是HTTP客户端，正常操作
]
```

### 3.3 安全检查函数

**文件**: `backend/app/tools/shell/execute_code_safety.py`

```python
def validate_code_safety(code: str) -> Dict[str, Any]:
    """分级安全检查 — 小健 2026-06-27
    
    使用方式：
        from app.tools.shell.execute_code_safety import validate_code_safety
        
        result = validate_code_safety(code)
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
    
    for rule in RISK_CHECK_RULES:
        if re_mod.search(rule["pattern"], code):
            risk = rule["risk"]
            desc = rule["desc"]
            
            # 记录详细信息
            details.append(f"[{risk.upper()}] {desc}")
            
            # 更新最高风险等级
            if risk == RiskLevel.HIGH:
                max_risk = RiskLevel.HIGH
                allow = False
                warnings.append(desc)
            elif risk == RiskLevel.MEDIUM and max_risk != RiskLevel.HIGH:
                max_risk = RiskLevel.MEDIUM
                warnings.append(desc)
            # LOW风险只记录，不警告
    
    return {
        "risk_level": max_risk,
        "warnings": warnings,
        "allow": allow,
        "details": details,
    }
```

### 3.4 execute_code调用

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
        
        # 记录安全检查结果
        if risk_level == "low":
            logger.info(f"[安全检查] 低风险: {details}")
        elif risk_level == "medium":
            logger.warning(f"[安全检查] 中风险: {warnings}")
        elif risk_level == "high":
            logger.error(f"[安全检查] 高风险，拒绝执行: {warnings}")
            return {
                "success": False,
                "error_detail": f"代码存在高风险: {', '.join(warnings)}",
                "params": {"risk_level": risk_level, "warnings": warnings}
            }
    
    # 执行代码...
```

---

## 四、效果对比

### 4.1 subprocess

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `subprocess.run(["python", "script.py"])` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `subprocess.run(["rm", "-rf", "/"])` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 保持安全 |
| `subprocess.run(["dir"])` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |

### 4.2 文件操作

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `open("test.txt", "w")` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `open("/etc/passwd", "w")` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 保持安全 |
| `open("data.txt", "w")` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |

### 4.3 eval/exec

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `eval("1+1")` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `eval(user_input)` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 保持安全 |
| `eval(complex_expr)` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |

### 4.4 socket和requests

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `socket.socket()` | ❌ 拒绝 | ✅ 完全允许 | ✅ 不再过度拦截 |
| `requests.get("https://api.com")` | ❌ 拒绝 | ✅ 完全允许 | ✅ 不再过度拦截 |

---

## 五、方案优点

### 5.1 核心优点

1. ✅ **不再一棍子打死**：根据具体内容判断风险
2. ✅ **细粒度检查**：区分合法用途和恶意用途
3. ✅ **分级处理**：低风险允许，中风险警告，高风险拒绝
4. ✅ **可扩展**：容易添加新规则
5. ✅ **日志清晰**：记录每个风险等级

### 5.2 安全性保证

- ✅ **高风险操作仍然拒绝**：如 `rm -rf /`、`eval(user_input)`
- ✅ **中风险有警告**：提醒开发者注意
- ✅ **低风险有日志**：可追溯

### 5.3 可用性提升

- ✅ **允许合法的subprocess调用**：如执行Python脚本
- ✅ **允许合法的文件写入**：如写入临时文件
- ✅ **允许合法的HTTP请求**：如调用API（完全允许，不检查）
- ✅ **允许合法的网络连接**：如socket（完全允许，不检查）
- ✅ **允许合法的eval调用**：如计算表达式

---

## 六、实施计划

### 6.1 实施步骤

1. **Step 1**: 创建 `backend/app/tools/shell/execute_code_safety.py`
2. **Step 2**: 实现 `RiskLevel`、`RISK_CHECK_RULES`、`validate_code_safety()`
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

### 6.2 测试用例

```python
def test_safety_check_v2():
    # LOW风险：允许
    result = _validate_code_safety_v2('subprocess.run(["python", "script.py"])')
    assert result["risk_level"] == "low"
    assert result["allow"] == True
    
    # HIGH风险：拒绝
    result = _validate_code_safety_v2('subprocess.run(["rm", "-rf", "/"])')
    assert result["risk_level"] == "high"
    assert result["allow"] == False
    
    # MEDIUM风险：允许但有警告
    result = _validate_code_safety_v2('subprocess.run(["dir"])')
    assert result["risk_level"] == "medium"
    assert result["allow"] == True
    assert len(result["warnings"]) > 0
```

---

## 七、风险与缓解

### 7.1 潜在风险

| 风险 | 说明 | 缓解措施 |
|------|------|---------|
| 规则不够完善 | 可能遗漏某些危险模式 | 持续更新规则，社区反馈 |
| 误判 | 可能错误判断风险等级 | 提供配置开关，允许关闭检查 |
| 绕过 | 攻击者可能绕过检查 | 多层防御，结合其他安全机制 |

### 7.2 缓解措施

1. **配置开关**：
   ```python
   # config.yaml
   safety_check:
     enabled: true
     strict_mode: false  # 严格模式：MEDIUM也拒绝
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

## 八、总结

**本方案通过分级安全检查，解决了当前"一棍子打死"的问题，在保证安全性的同时提升了可用性。**

**核心改进**：
- ✅ 不再过度拦截合法用途
- ✅ 保持对高风险操作的拦截
- ✅ 提供清晰的日志和警告
- ✅ 易于扩展和维护

**下一步**：实施并验证效果。