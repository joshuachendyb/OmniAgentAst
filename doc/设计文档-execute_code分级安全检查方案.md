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

#### **HTTP请求规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `requests.get("https://api.com")` | LOW | HTTPS请求 | ✅ 允许 |
| `requests.get("file://...")` | HIGH | file://协议 | ❌ 拒绝 |
| `requests.get("http://...")` | MEDIUM | HTTP请求 | ✅ 允许（警告） |

#### **eval/exec规则**

| 模式 | 风险等级 | 说明 | 是否允许 |
|------|---------|------|---------|
| `eval("1+1")` | LOW | eval硬编码字符串 | ✅ 允许 |
| `eval(user_input)` | HIGH | eval动态变量 | ❌ 拒绝 |
| `eval(complex_expr)` | MEDIUM | 其他eval调用 | ✅ 允许（警告） |

---

## 三、代码实现

### 3.1 风险等级定义

**文件**: `backend/app/tools/tool_constants.py`

```python
# ============================================================
# 安全风险等级 — 小健 2026-06-27
# ============================================================
class RiskLevel:
    LOW = "low"        # 低风险：允许执行，INFO日志
    MEDIUM = "medium"  # 中风险：允许执行，WARNING日志
    HIGH = "high"      # 高风险：拒绝执行
```

### 3.2 分级检查规则

**文件**: `backend/app/tools/tool_constants.py`

```python
# ============================================================
# 分级安全检查规则 — 小健 2026-06-27
# ============================================================
RISK_CHECK_RULES = [
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
    
    # ===== requests/HTTP =====
    # 低风险：HTTPS请求
    {
        "pattern": r"requests\.(get|post|put|delete|patch)\s*\(\s*[\'\"]https://",
        "risk": RiskLevel.LOW,
        "desc": "HTTPS请求（相对安全）",
        "allow": True,
    },
    # 高风险：file:// 协议
    {
        "pattern": r"requests\.(get|post|put|delete|patch)\s*\(\s*[\'\"]file://",
        "risk": RiskLevel.HIGH,
        "desc": "file://协议请求",
        "allow": False,
    },
    # 中风险：HTTP请求
    {
        "pattern": r"requests\.(get|post|put|delete|patch)\s*\(",
        "risk": RiskLevel.MEDIUM,
        "desc": "HTTP请求",
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
    
    # ===== socket =====
    # 中风险：网络Socket
    {
        "pattern": r"socket\s*\.",
        "risk": RiskLevel.MEDIUM,
        "desc": "网络Socket操作",
        "allow": True,
    },
]
```

### 3.3 安全检查函数

**文件**: `backend/app/tools/tool_fc_helper.py`

```python
def _validate_code_safety_v2(code: str) -> Dict[str, Any]:
    """分级安全检查 — 小健 2026-06-27
    
    返回:
    {
        "risk_level": "low/medium/high",
        "warnings": ["警告信息"],
        "allow": True/False,
        "details": ["详细信息"]
    }
    """
    from app.tools.tool_constants import RISK_CHECK_RULES, RiskLevel
    
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

### 3.4 execute_code修改

**文件**: `backend/app/tools/shell/execute_code.py`

```python
def _execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None, safety_check: bool = True) -> Dict[str, Any]:
    """执行Python代码 — 小健 2026-06-27 改用分级安全检查"""
    if not code or not code.strip():
        return {"success": False, "error_detail": "code参数不能为空"}
    
    if safety_check:
        from app.tools.tool_fc_helper import _validate_code_safety_v2
        safety_result = _validate_code_safety_v2(code)
        
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

### 4.3 HTTP请求

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `requests.get("https://api.com")` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `requests.get("file://...")` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 保持安全 |
| `requests.get("http://...")` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |

### 4.4 eval/exec

| 代码 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| `eval("1+1")` | ❌ 拒绝 | ✅ 允许（LOW） | ✅ 不再过度拦截 |
| `eval(user_input)` | ❌ 拒绝 | ❌ 拒绝（HIGH） | ✅ 保持安全 |
| `eval(complex_expr)` | ❌ 拒绝 | ✅ 允许（MEDIUM） | ✅ 允许但有警告 |

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
- ✅ **允许合法的HTTP请求**：如调用API
- ✅ **允许合法的eval调用**：如计算表达式

---

## 六、实施计划

### 6.1 实施步骤

1. **Step 1**: 在 `tool_constants.py` 中添加 `RiskLevel` 和 `RISK_CHECK_RULES`
2. **Step 2**: 在 `tool_fc_helper.py` 中实现 `_validate_code_safety_v2`
3. **Step 3**: 修改 `execute_code.py` 使用新的安全检查
4. **Step 4**: 编写单元测试验证效果
5. **Step 5**: 更新文档

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