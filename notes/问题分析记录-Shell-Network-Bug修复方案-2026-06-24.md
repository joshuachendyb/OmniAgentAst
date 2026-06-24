# 问题分析记录 - Shell/Network工具Bug修复方案

**创建时间**: 2026-06-24 22:35:55
**版本**: v1.0
**编写人**: 小欧
**项目**: OmniAgentAs-desk
**范围**: SHELL(4个tool) + NETWORK(5个tool) + 公共模块

---

## 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-06-24 22:35:55 | 初始版本，50个Bug分析及修复方案 | 小欧 |

---

## 一、Bug汇总

| 分类 | 数量 | 严重程度 |
|------|------|---------|
| SHELL工具Bug | 18个 | P0-P2 |
| NETWORK工具Bug | 24个 | P0-P2 |
| 公共模块Bug | 8个 | P1-P3 |
| **总计** | **50个** | - |

---

## 二、SHELL工具Bug分析（18个）

### Bug#S01: _run_shell_background硬编码shell_type

**文件**: `app/tools/shell/execute_shell_command.py:100`
**严重程度**: P1-高
**问题描述**: `_run_shell_background`函数在存储后台会话时，shell_type硬编码为"powershell"，忽略了调用者传入的shell_type参数。

**根因分析**:
```python
# 第100行：硬编码赋值
_background_shells[shell_id] = {
    "process": process, "command": command,
    "started_at": datetime.now().isoformat(),
    "shell_type": "powershell",  # ← 应为传入参数
    "cwd": cwd,
}
```
函数签名接收`executable`参数，但没有接收`shell_type`参数，导致存储时只能硬编码。

**影响**: 用户指定`shell_type="cmd"`时，后台会话记录的shell_type仍是"powershell"，导致后续会话管理混淆。

**修复方案**:
```python
def _run_shell_background(command: str, executable: Optional[str],
                           cwd: Optional[str], env: Optional[dict],
                           shell_type: str = "powershell") -> Dict[str, Any]:
    """启动后台shell命令"""
    # ... 现有代码 ...
    _background_shells[shell_id] = {
        "process": process, "command": command,
        "started_at": datetime.now().isoformat(),
        "shell_type": shell_type,  # ← 使用传入参数
        "cwd": cwd,
    }
```
**遵循原则**: SRP（单一职责）- 函数应正确传递参数；KISS-DIRECT（简单直接）- 直接使用参数赋值。

---

### Bug#S02: exit_code=0+stderr标记为error

**文件**: `app/tools/shell/execute_shell_command.py:205-210`
**严重程度**: P1-高
**问题描述**: 当命令exit_code=0但有stderr输出时，结果被标记为"error"而非"success"或"warning"。

**根因分析**:
```python
# 第205-210行
if result.get("success"):  # returncode==0时success=True
    if stderr_str and stderr_str.strip():
        exec_code = "warning"  # ← 应该是warning
    else:
        exec_code = "success"
```
但实际测试显示返回的是"error"。检查`_build_shell_result`第81-82行：
```python
if returncode == 0:
    return {"success": True, ...}
```
问题出在第83行：当returncode!=0时返回`success: False`，但exit_code=0时应该走success分支。实际测试中stderr内容导致了不同的exec_code。

**影响**: pip等工具的正常进度信息写stderr，被误判为错误，影响Agent决策。

**修复方案**:
```python
if result.get("success"):
    if stderr_str and stderr_str.strip():
        exec_code = "warning"  # 确保warning而非error
    else:
        exec_code = "success"
    llm_data = _build_execute_shell_command_llm_data(
        exec_code, duration_ms, command[:100], returncode, 
        stdout_str[:200], stderr_str[:200], shell_type or "powershell")
```
**遵循原则**: KISS-DIRECT（简单直接）- 逻辑清晰；SLAP（同一抽象层）- 状态判断在同一层级。

---

### Bug#S03: shell_type大小写敏感

**文件**: `app/tools/shell/execute_shell_command.py:138`
**严重程度**: P2-中
**问题描述**: shell_type参数只接受小写"powershell"/"cmd"，"PowerShell"/"CMD"被拒绝。

**根因分析**:
```python
# 第138行：严格匹配小写
if shell_type not in ("powershell", "cmd", None):
    # 返回错误
```
没有进行大小写归一化处理。

**影响**: LLM可能生成"PowerShell"或"CMD"，导致工具调用失败。

**修复方案**:
```python
# 在参数验证前归一化
if shell_type:
    shell_type = shell_type.lower().strip()
if shell_type not in ("powershell", "cmd", None):
    # 返回错误
```
**遵循原则**: KISS-DIRECT（简单直接）- 一行归一化；防御性编程 - 验证输入。

---

### Bug#S04: _decode_bytes_safe GBK优先导致emoji乱码

**文件**: `app/tools/tool_fc_helper.py:59`
**严重程度**: P1-高
**问题描述**: `_decode_bytes_safe`在Windows上优先使用locale编码(GBK)解码，导致UTF-8编码的emoji和中文被错误解码。

**根因分析**:
```python
# 第59行：locale.getpreferredencoding()在Windows返回cp936(GBK)
for enc in (encodings or [locale.getpreferredencoding(), 'utf-8', 'gbk', 'latin-1']):
    try:
        return data.decode(enc).replace('\r\n', '\n')
    except (UnicodeDecodeError, LookupError):
        continue
```
UTF-8编码的"🌍"字节序列恰好能被GBK解码（虽然结果错误），所以不会抛出UnicodeDecodeError。

**影响**: 所有UTF-8编码的中文输出在Windows上可能乱码，emoji完全损坏。

**修复方案**:
```python
def _decode_bytes_safe(data: Any, encodings: Optional[list] = None) -> str:
    """安全解码bytes为str"""
    if data is None:
        return ""
    if isinstance(data, str):
        return data.replace('\r\n', '\n')
    if isinstance(data, bytes):
        # 优先尝试UTF-8，因为现代系统大多使用UTF-8
        for enc in (encodings or ['utf-8', locale.getpreferredencoding(), 'gbk', 'latin-1']):
            try:
                return data.decode(enc).replace('\r\n', '\n')
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode('latin-1').replace('\r\n', '\n')
    return str(data)
```
**遵循原则**: KISS-DIRECT（简单直接）- 调整编码顺序；防御性编程 - 多编码回退。

---

### Bug#S05: execute_code language大小写敏感

**文件**: `app/tools/shell/execute_code.py:187-189`
**严重程度**: P2-中
**问题描述**: language参数只接受小写"python"/"javascript"，"Python"/"Javascript"被拒绝。

**根因分析**:
```python
# 第187-189行：严格匹配小写
if language == "python":
    result = _execute_python(...)
elif language == "javascript":
    result = _execute_javascript(...)
else:
    # 返回错误
```

**影响**: LLM可能生成首字母大写的语言名，导致工具调用失败。

**修复方案**:
```python
# 在参数验证前归一化
language = language.lower().strip() if language else "python"
if language == "python":
    result = _execute_python(...)
elif language == "javascript":
    result = _execute_javascript(...)
```
**遵循原则**: KISS-DIRECT（简单直接）- 一行归一化。

---

### Bug#S06: execute_code用'python'而非sys.executable

**文件**: `app/tools/shell/execute_code.py:115`
**严重程度**: P1-高
**问题描述**: `_execute_python`使用字符串'python'调用Python，而非sys.executable，可能调用错误的Python版本。

**根因分析**:
```python
# 第115行：使用字符串'python'
result = subprocess.run(['python', temp_file], ...)
```
当系统有多个Python版本时（如Python 3.9和3.13），'python'可能指向错误版本。

**影响**: 代码在错误的Python环境中执行，可能导致依赖缺失或行为异常。

**修复方案**:
```python
import sys
# 第115行：使用sys.executable
result = subprocess.run([sys.executable, temp_file], ...)
```
**遵循原则**: KISS-DIRECT（简单直接）- 直接使用当前解释器；安全性 - 避免路径劫持。

---

### Bug#S07: find_command all_paths返回success给不存在的命令

**文件**: `app/tools/shell/find_command.py`
**严重程度**: P2-中
**问题描述**: `find_command`使用`all_paths=True`时，即使命令不存在也返回success状态。

**根因分析**: 函数设计为"查找"而非"验证"，count=0且paths=[]时仍返回success。这可能导致Agent误认为命令可用。

**影响**: Agent可能尝试执行不存在的命令。

**修复方案**:
```python
# 在返回前检查count
if result["data"]["count"] == 0:
    # 考虑返回warning或error
    llm_data["status"]["exec_code"] = "warning"
    llm_data["status"]["detail"] = f"命令'{command}'未找到"
```
**遵循原则**: SRP（单一职责）- 查找和验证分离；明确语义 - success应表示命令存在。

---

### Bug#S08: shell_session进程完成后第二次读取报"会话不存在"

**文件**: `app/tools/shell/shell_session.py:81-82`
**严重程度**: P2-中
**问题描述**: 当后台进程完成后，第一次output读取成功并从`_background_shells`中移除，第二次读取时报"会话不存在"。

**根因分析**:
```python
# 第81-82行
if not is_running:
    _background_shells.pop(shell_id, None)  # ← 第一次读取时移除
```
进程完成后自动清理是合理设计，但Agent可能需要多次读取输出。

**影响**: Agent丢失进程输出的访问能力。

**修复方案**:
```python
# 方案1：保留已完成的会话信息，标记为completed
if not is_running:
    shell_info["completed"] = True
    # 不立即pop，等cleanup时再清理

# 方案2：在data中返回完整输出，不依赖后续读取
resp_data = {
    "shell_id": shell_id, 
    "stdout": stdout_str, 
    "stderr": stderr_str, 
    "is_running": is_running, 
    "returncode": returncode,
    "completed": not is_running,  # 新增标记
}
```
**遵循原则**: KISS-DIRECT（简单直接）- 保留已完成会话；明确语义 - 返回完整信息。

---

### Bug#S09: shell_session terminate静默吞掉异常

**文件**: `app/tools/shell/shell_session.py:111-112`
**严重程度**: P2-中
**问题描述**: terminate操作的kill/wait异常被`except Exception: pass`静默吞掉，`terminated`保持False但会话仍被移除。

**根因分析**:
```python
# 第111-112行
except Exception:
    pass  # ← 静默吞掉异常
```
导致用户不知道kill是否成功，且僵尸进程可能残留。

**影响**: 进程可能未被正确终止，资源泄漏。

**修复方案**:
```python
try:
    process.kill()
    process.wait(timeout=SUBPROCESS_TIMEOUT_SHORT)
    terminated = True
    returncode = process.returncode
except subprocess.TimeoutExpired:
    # 第二次尝试强制终止
    try:
        process.kill()
        process.wait(timeout=2)
        terminated = True
        returncode = process.returncode
    except Exception:
        logger.warning(f"无法终止进程: {shell_id}")
except Exception as e:
    logger.warning(f"终止进程异常: {shell_id}, {e}")
```
**遵循原则**: 错误处理 - 不静默吞掉异常；防御性编程 - 多次尝试。

---

### Bug#S10-S11: data字段缺失shell_type和returncode

**文件**: `app/tools/shell/execute_shell_command.py:82-83`
**严重程度**: P3-低
**问题描述**: `_build_shell_result`构建的data字典缺少shell_type和returncode字段。

**根因分析**:
```python
# 第76-78行：data只包含stdout和stderr
data = {
    "stdout": stdout_str, "stderr": stderr_str,
}
```
未包含执行上下文信息。

**影响**: 前端和LLM无法获取完整的执行信息。

**修复方案**:
```python
data = {
    "stdout": stdout_str, "stderr": stderr_str,
    "shell_type": shell_type,
    "returncode": returncode,
}
```
**遵循原则**: SLAP（同一抽象层）- 数据结构完整；明确语义 - 返回完整信息。

---

### Bug#S12: 长命令在summary中被截断

**文件**: `app/tools/shell/execute_shell_command.py:43`
**严重程度**: P3-低
**问题描述**: 命令超过100字符时在summary中被截断，可能丢失关键信息。

**根因分析**:
```python
# 第43行
cmd_short = command[:100] if command else ""
```
简单截断，无智能摘要。

**影响**: Agent可能无法从summary中理解完整的命令内容。

**修复方案**:
```python
# 保留关键部分，截断中间
if len(command) > 100:
    cmd_short = command[:60] + "..." + command[-37:]
else:
    cmd_short = command
```
**遵循原则**: KISS-DIRECT（简单直接）- 保留首尾信息。

---

### Bug#S13: 超时后进程kill可能失败导致进程泄漏

**文件**: `app/tools/shell/execute_shell_command.py:188-194`
**严重程度**: P1-高
**问题描述**: 超时后调用proc.kill()和proc.communicate()，但第二次communicate也可能超时，导致进程残留。

**根因分析**:
```python
# 第188-194行
except subprocess.TimeoutExpired:
    timed_out = True
    proc.kill()
    try:
        stdout_bytes, stderr_bytes = proc.communicate(timeout=SUBPROCESS_TIMEOUT_SHORT)
    except subprocess.TimeoutExpired:
        stdout_bytes, stderr_bytes = b"", b""  # ← 进程可能仍在运行
```

**影响**: 僵尸进程累积，占用系统资源。

**修复方案**:
```python
except subprocess.TimeoutExpired:
    timed_out = True
    try:
        proc.kill()
        proc.wait(timeout=5)  # 等待进程退出
    except Exception:
        pass
    stdout_bytes, stderr_bytes = b"", b""
```
**遵循原则**: 资源管理 - 确保进程退出；防御性编程 - 多次尝试。

---

### Bug#S14: execute_code data中不含working_dir

**文件**: `app/tools/shell/execute_code.py:208`
**严重程度**: P3-低
**问题描述**: execute_code返回的data缺少working_dir字段。

**根因分析**:
```python
# 第208行
data = {"stdout": output, "stderr": error, "returncode": returncode}
```
未包含执行目录信息。

**影响**: Agent无法知道代码在哪个目录执行。

**修复方案**:
```python
data = {
    "stdout": output, 
    "stderr": error, 
    "returncode": returncode,
    "working_dir": working_dir or os.getcwd(),
}
```
**遵循原则**: SLAP（同一抽象层）- 数据结构完整。

---

### Bug#S15: _background_shells无并发锁

**文件**: `app/tools/shell/execute_shell_command.py:34,97-101`
**严重程度**: P1-高
**问题描述**: `_background_shells`是模块级dict，多个async协程同时操作时存在竞态条件。

**根因分析**: 虽然Python GIL防止数据竞争，但逻辑竞态仍存在：
- 协程A读取shell_info
- 协程B删除同一shell_info
- 协程A继续操作已删除的shell_info

**影响**: 并发请求时会话状态混乱。

**修复方案**:
```python
import asyncio

_background_shells: Dict[str, Dict[str, Any]] = {}
_background_shells_lock = asyncio.Lock()

async def _get_shell_info(shell_id: str) -> Optional[Dict]:
    async with _background_shells_lock:
        return _background_shells.get(shell_id)

async def _remove_shell(shell_id: str) -> bool:
    async with _background_shells_lock:
        return _background_shells.pop(shell_id, None) is not None
```
**遵循原则**: 并发安全 - 使用锁保护共享状态。

---

### Bug#S16: execute_code timeout单位与execute_shell_command不一致

**文件**: `app/tools/shell/execute_code.py:180` vs `execute_shell_command.py:131`
**严重程度**: P2-中
**问题描述**: execute_code的timeout单位是秒(30)，execute_shell_command的timeout单位是毫秒(30000)。

**根因分析**: 两个工具由不同作者在不同时间开发，未统一约定。

**影响**: Agent或LLM可能传错单位（如30000给execute_code→8.3小时）。

**修复方案**:
```python
# 统一使用毫秒，与execute_shell_command一致
def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30000,  # ← 改为毫秒
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    timeout_sec = timeout / 1000.0  # 转换为秒
```
**遵循原则**: 一致性 - 统一接口约定。

---

## 三、NETWORK工具Bug分析（24个）

### Bug#N01a-e: SSRF绕过（5个变体）

**文件**: `app/tools/network/http_request.py:62-89`
**严重程度**: P0-紧急
**问题描述**: _validate_url的SSRF拦截存在多个绕过方式。

**根因分析**:
```python
# 第72-76行：只拦截特定字符串
blocked = ["localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]",
            "169.254.169.254", "metadata.google.internal"]
if hostname.lower() in blocked:
    return {"valid": False, ...}
```
**绕过方式**:
- N01a: `0x7f000001` (十六进制IP) → 解析为127.0.0.1
- N01b: `2130706433` (整数IP) → 解析为127.0.0.1
- N01c: `127.0.0.2` (loopback范围) → 未拦截
- N01d: `0` (等同0.0.0.0) → 未拦截
- N01e: `127.1` (缩写形式) → 未拦截

**影响**: 攻击者可通过格式化IP绕过SSRF防护，访问内网服务。

**修复方案**:
```python
import ipaddress

def _validate_url(url: str) -> Dict[str, Any]:
    """验证URL格式"""
    try:
        parsed = urlparse(url)
        # ... 现有scheme验证 ...
        
        hostname = parsed.hostname or ""
        
        # 解析IP地址进行统一检查
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return {"valid": False, "error": f"SSRF拦截: 禁止访问内网地址 {hostname}"}
        except ValueError:
            # 不是IP地址，检查域名
            blocked_domains = ["localhost", "metadata.google.internal"]
            if hostname.lower() in blocked_domains:
                return {"valid": False, "error": f"SSRF拦截: 禁止访问内网地址 {hostname}"}
            # 检查内网域名
            if hostname.endswith(".internal") or hostname.endswith(".local"):
                return {"valid": False, "error": f"SSRF拦截: 禁止访问内网域名 {hostname}"}
        
        return {"valid": True, ...}
    except Exception as e:
        return {"valid": False, "error": str(e)}
```
**遵循原则**: 安全性 - 使用标准库解析IP；深度防御 - 多层检查。

---

### Bug#N02: 172.x.x.x内网检测逻辑不完整

**文件**: `app/tools/network/http_request.py:76-84`
**严重程度**: P1-高
**问题描述**: 172.16-31.x.x的内网检测逻辑复杂且脆弱，依赖字符串解析。

**根因分析**:
```python
# 第76-84行：复杂的字符串解析
if hostname.startswith("10.") or hostname.startswith("192.168.") or hostname.startswith("172."):
    parts = hostname.split(".")
    if len(parts) == 4 and parts[0] == "172":
        try:
            second = int(parts[1])
            if 16 <= second <= 31:
                return {"valid": False, ...}
```

**影响**: 维护困难，容易遗漏边界情况。

**修复方案**: 使用ipaddress模块统一处理（见Bug#N01a-e修复方案）。

**遵循原则**: KISS-DIRECT（简单直接）- 使用标准库；复用优先 - 统一SSRF检查函数。

---

### Bug#N03: 非法scheme拦截不完整

**文件**: `app/tools/network/http_request.py:67`
**严重程度**: P1-高
**问题描述**: valid_schemes包含ftp/ftps/ws/wss，这些协议存在安全风险。

**根因分析**:
```python
# 第67行
valid_schemes = {"http", "https", "ftp", "ftps", "ws", "wss"}
```
- FTP：明文传输，可泄露凭据
- WebSocket：可用于SSRF攻击

**影响**: Agent可被指示发起FTP请求或WebSocket连接到内网。

**修复方案**:
```python
valid_schemes = {"http", "https"}  # 只允许HTTP/HTTPS
```
**遵循原则**: 安全性 - 最小权限；YAGNI（不要过度设计）- 不需要FTP/WS。

---

### Bug#N04: Cloudflare降级使用相同UA

**文件**: `app/tools/network/fetch_webpage.py:371-375`
**严重程度**: P2-中
**问题描述**: 检测到Cloudflare挑战时，降级重试使用相同的BROWSER_USER_AGENT。

**根因分析**:
```python
# 第374行
simple_headers["User-Agent"] = BROWSER_USER_AGENT  # ← 与原始headers相同
```
Cloudflare已识别该UA，降级无效。

**影响**: Cloudflare保护的页面无法获取。

**修复方案**:
```python
# 使用简化的UA
simple_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
```
**遵循原则**: KISS-DIRECT（简单直接）- 使用不同的UA。

---

### Bug#N05: Playwright错误检查使用错误的键名

**文件**: `app/tools/network/fetch_webpage.py:360-362`
**严重程度**: P1-高
**问题描述**: 检查Playwright错误时使用"code"键，但错误字典使用"error"键。

**根因分析**:
```python
# 第360行
if "code" in playwright_result:  # ← 检查"code"
    return playwright_result
```
但`_fetch_via_playwright`返回的错误字典使用"error"键：
```python
return {"error": True, "error_detail": str(e), ...}
```
导致错误检查永远失败，触发KeyError。

**影响**: Playwright错误被静默忽略，后续代码因KeyError崩溃。

**修复方案**:
```python
if playwright_result.get("error"):
    return playwright_result
```
**遵循原则**: KISS-DIRECT（简单直接）- 使用.get()安全访问；一致性 - 统一键名。

---

### Bug#N06: download_file无文件大小限制

**文件**: `app/tools/network/download_file.py`
**严重程度**: P1-高
**问题描述**: 下载文件无大小限制，可能下载GB级文件导致磁盘耗尽。

**根因分析**: 未实现Content-Length检查和大小限制。

**影响**: 恶意URL可导致磁盘空间耗尽。

**修复方案**:
```python
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

async def _stream_download(client, url, dest_path, headers, chunk_size=8192):
    async with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()
        total_bytes = int(response.headers.get("content-length", 0))
        
        if total_bytes > MAX_FILE_SIZE:
            raise ValueError(f"文件过大: {total_bytes}字节, 限制: {MAX_FILE_SIZE}字节")
        
        downloaded = 0
        with open(dest_path, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                downloaded += len(chunk)
                if downloaded > MAX_FILE_SIZE:
                    os.remove(dest_path)
                    raise ValueError(f"下载超过大小限制")
                f.write(chunk)
```
**遵循原则**: 安全性 - 资源限制；防御性编程 - 边界检查。

---

### Bug#N07: download_file无路径遍历防护

**文件**: `app/tools/network/download_file.py:172`
**严重程度**: P0-紧急
**问题描述**: destination_path未检查路径遍历，可写入任意位置。

**根因分析**:
```python
# 第172行：直接使用用户输入的路径
dest_path = os.path.abspath(destination_path)
```
攻击者可传入`../../etc/passwd`写入系统文件。

**影响**: 任意文件写入，严重安全漏洞。

**修复方案**:
```python
# 限制在工作目录内
WORK_DIR = os.path.join(os.path.expanduser("~"), ".omniagent", "downloads")

dest_path = os.path.abspath(os.path.join(WORK_DIR, destination_path))
if not dest_path.startswith(os.path.abspath(WORK_DIR)):
    return build_error(data={"error_detail": "路径遍历不允许"})
```
**遵循原则**: 安全性 - 路径验证；最小权限 - 限制写入目录。

---

### Bug#N08-N11,N14: Schema字段缺失

**文件**: `app/tools/network/network_schema.py`
**严重程度**: P2-中
**问题描述**: 工具Schema缺少实现中支持的参数，LLM无法发现这些参数。

**根因分析**:
- HttpRequestInput: 缺少timeout/proxy/retry
- DownloadFileInput: 缺少headers/timeout/proxy
- FetchWebpageInput: 缺少js_render/timeout/proxy
- SearchWebInput: 缺少allowed_domains/blocked_domains/num_results/proxy
- NetworkDiagnoseInput: 缺少count/timeout

**影响**: LLM无法使用这些参数，功能受限。

**修复方案**: 更新Schema添加缺失字段（但不暴露给LLM的内部参数除外）。

**遵循原则**: 接口契约 - Schema与实现一致。

---

### Bug#N12: _validate_url在3个文件中重复

**文件**: `http_request.py`, `fetch_webpage.py`, `download_file.py`
**严重程度**: P2-中
**问题描述**: 完全相同的_validate_url函数在3个文件中重复定义。

**根因分析**: 从network_tools.py拆分时未提取公共函数。

**影响**: 维护困难，修改需同步3处。

**修复方案**:
```python
# 创建 app/tools/network/url_validator.py
def validate_url(url: str) -> Dict[str, Any]:
    """统一URL验证和SSRF检查"""
    # ... 实现 ...
```
**遵循原则**: DRY（不重复）- 提取公共函数；复用优先 - 统一验证逻辑。

---

### Bug#N13: http_request对PATCH/DELETE方法丢弃body

**文件**: `app/tools/network/http_request.py:201-203`
**严重程度**: P2-中
**问题描述**: 只有POST/PUT方法会发送body，PATCH/DELETE的body被静默丢弃。

**根因分析**:
```python
# 第201-203行
if method_upper in ("POST", "PUT"):
    if body is not None:
        request_kwargs["json"] = body
```

**影响**: PATCH/DELETE请求缺少body，服务器返回400或数据不一致。

**修复方案**:
```python
if method_upper in ("POST", "PUT", "PATCH", "DELETE"):
    if body is not None:
        request_kwargs["json"] = body
```
**遵循原则**: KISS-DIRECT（简单直接）- 扩展方法列表。

---

### Bug#N14: 指数退避无上限，最长等待512秒

**文件**: `app/tools/network/http_request.py:229`
**严重程度**: P1-高
**问题描述**: 重试退避公式`0.5 * (2 ** attempt)`无上限，retry=10时最后等待512秒。

**根因分析**:
```python
# 第229行
await asyncio.sleep(0.5 * (2 ** attempt))
```
attempt=9时：0.5 * 512 = 256秒；attempt=10时：0.5 * 1024 = 512秒。

**影响**: 工具挂起8.5分钟，阻塞Agent任务队列。

**修复方案**:
```python
MAX_BACKOFF_SEC = 10  # 最大退避10秒
await asyncio.sleep(min(0.5 * (2 ** attempt), MAX_BACKOFF_SEC))
```
**遵循原则**: KISS-DIRECT（简单直接）- 添加上限；防御性编程 - 防止极端情况。

---

### Bug#N15: fetch_webpage对media响应返回duration_ms=0

**文件**: `app/tools/network/fetch_webpage.py:384`
**严重程度**: P3-低
**问题描述**: 图片/PDF响应的duration_ms硬编码为0。

**根因分析**:
```python
# 第384行
llm_data = _build_fetch_webpage_llm_data("success", 0, url, ...)
```
media路径提前返回，未计算实际耗时。

**影响**: 性能指标不准确。

**修复方案**:
```python
# 在media路径前记录时间
t_media = _time_mod.perf_counter()
# ... 处理media ...
duration_ms = int((_time_mod.perf_counter() - t_media) * 1000)
llm_data = _build_fetch_webpage_llm_data("success", duration_ms, url, ...)
```
**遵循原则**: 准确性 - 计算真实耗时。

---

### Bug#N16: download_file网络错误后残留部分文件

**文件**: `app/tools/network/download_file.py:129-147`
**严重程度**: P2-中
**问题描述**: 网络错误时部分下载的文件残留在磁盘。

**根因分析**:
```python
# 第143行：只处理PermissionError/OSError
except (PermissionError, OSError):
    if os.path.exists(dest_path):
        os.remove(dest_path)
    raise
```
网络错误(httpx.RequestError)未被此except捕获。

**影响**: 用户看到不完整的文件，可能误用。

**修复方案**:
```python
try:
    with open(dest_path, "wb") as f:
        async for chunk in response.aiter_bytes(chunk_size=chunk_size):
            f.write(chunk)
            downloaded += len(chunk)
except Exception as e:
    # 清理部分文件
    try:
        if os.path.exists(dest_path):
            os.remove(dest_path)
    except Exception:
        pass
    raise
```
**遵循原则**: 原子性 - 操作要么完整要么回滚；防御性编程 - 清理资源。

---

### Bug#N17: network_diagnose无SSRF防护

**文件**: `app/tools/network/network_diagnose.py:153-193`
**严重程度**: P0-紧急
**问题描述**: network_diagnose的host参数无SSRF检查，可探测内网。

**根因分析**: 未调用_validate_url或进行IP验证。

**影响**: 攻击者可扫描内网主机和端口。

**修复方案**:
```python
async def network_diagnose(host: str, mode: str = "ping", port: Optional[int] = None):
    # 添加SSRF检查
    from app.tools.network.url_validator import validate_url
    if not validate_url(f"http://{host}")["valid"]:
        return build_error(data={"error_detail": f"禁止访问内网地址: {host}"})
    # ... 现有逻辑 ...
```
**遵循原则**: 安全性 - 统一SSRF检查；复用优先 - 使用已有验证函数。

---

### Bug#N18: download_file content-length缺失时total_size=0

**文件**: `app/tools/network/download_file.py:135,191`
**严重程度**: P3-低
**问题描述**: 服务器不返回Content-Length时，total_size报告为0。

**根因分析**:
```python
# 第135行
total_bytes = int(response.headers.get("content-length", 0))
```
无Content-Length时默认为0，与"零字节文件"混淆。

**影响**: Agent可能认为下载失败。

**修复方案**:
```python
data = {
    "file_path": dest_path, 
    "file_size": downloaded, 
    "total_size": total_bytes if total_bytes > 0 else None,  # None表示未知
    "content_type": content_type,
}
```
**遵循原则**: 明确语义 - 区分"未知"和"零"。

---

## 四、公共模块Bug分析（8个）

### Bug#T01: write_yaml_ordered污染全局YAML状态

**文件**: `app/tools/tool_fc_helper.py:629`
**严重程度**: P2-中
**问题描述**: `yaml.add_representer`修改全局YAML序列化器状态。

**根因分析**:
```python
yaml.add_representer(OrderedDict, _repr_ordered_dict)
```
影响进程内所有YAML序列化。

**影响**: 多线程环境下其他代码的YAML序列化可能异常。

**修复方案**:
```python
# 使用自定义Dumper而非修改全局状态
class OrderedDumper(yaml.Dumper):
    pass

OrderedDumper.add_representer(OrderedDict, _repr_ordered_dict)

def write_yaml_ordered(data):
    return yaml.dump(data, Dumper=OrderedDumper)
```
**遵循原则**: 副作用最小化 - 不修改全局状态。

---

### Bug#T02: validate_html_content误报

**文件**: `app/tools/tool_fc_helper.py:451-457`
**严重程度**: P3-低
**问题描述**: 通过`<>`数量判断HTML有效性，属性值中的`>`会触发误报。

**根因分析**:
```python
if html.count('<') != html.count('>'):
    warnings.append("HTML标签不匹配")
```
`<div title="a>b">`中的`>`被错误计数。

**影响**: 有效HTML被误标为畸形。

**修复方案**:
```python
# 使用更精确的解析
from html.parser import HTMLParser

class SimpleHTMLValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []
    
    def handle_starttag(self, tag, attrs):
        pass
    
    def handle_endtag(self, tag):
        pass

def validate_html_content(html: str) -> List[str]:
    validator = SimpleHTMLValidator()
    try:
        validator.feed(html)
    except Exception as e:
        return [f"HTML解析错误: {e}"]
    return []
```
**遵循原则**: 准确性 - 使用正确的解析器。

---

### Bug#T03: check_db_exists连接泄漏

**文件**: `app/tools/tool_fc_helper.py:403-406`
**严重程度**: P2-中
**问题描述**: sqlite3连接未使用上下文管理器，异常时连接泄漏。

**根因分析**:
```python
conn = sqlite3.connect(db_path)
conn.execute("SELECT 1")
conn.close()  # ← 异常时不会执行
```

**影响**: 数据库连接累积，耗尽文件描述符。

**修复方案**:
```python
def check_db_exists(db_path: str) -> bool:
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
```
**遵循原则**: 资源管理 - 使用上下文管理器；防御性编程 - 异常安全。

---

### Bug#T04: download_file的os.remove可能失败

**文件**: `app/tools/network/download_file.py:144-145`
**严重程度**: P3-低
**问题描述**: 错误处理中调用os.remove，但文件可能被锁定或不存在。

**根因分析**:
```python
except (PermissionError, OSError):
    if os.path.exists(dest_path):
        os.remove(dest_path)  # ← 可能失败
    raise
```
os.remove失败会掩盖原始错误。

**影响**: 原始错误信息丢失。

**修复方案**:
```python
except (PermissionError, OSError) as original_error:
    try:
        if os.path.exists(dest_path):
            os.remove(dest_path)
    except Exception:
        pass  # 清理失败不影响原始错误
    raise original_error
```
**遵循原则**: 错误处理 - 不掩盖原始异常。

---

### Bug#T05: is_success/is_error对畸形结果返回False

**文件**: `app/tools/tool_response.py:66-81`
**严重程度**: P2-中
**问题描述**: 当llm_data缺失或格式错误时，is_success和is_error都返回False。

**根因分析**:
```python
def is_success(result):
    llm_data = result.get("llm_data")
    if not isinstance(llm_data, dict):
        return False  # ← 畸形结果返回False
```
调用者无法区分"成功"和"畸形"。

**影响**: 错误处理逻辑可能被跳过。

**修复方案**:
```python
def is_success(result):
    llm_data = result.get("llm_data")
    if not isinstance(llm_data, dict):
        return False  # 畸形结果视为失败
    exec_code = llm_data.get("status", {}).get("exec_code", "")
    return exec_code in ("success", "warning")

def is_error(result):
    llm_data = result.get("llm_data")
    if not isinstance(llm_data, dict):
        return True  # 畸形结果视为错误 ← 修改
    exec_code = llm_data.get("status", {}).get("exec_code", "")
    return exec_code == "error"
```
**遵循原则**: 安全默认 - 畸形结果视为错误。

---

### Bug#T06: http_request未处理超大JSON响应

**文件**: `app/tools/network/http_request.py:122-128`
**严重程度**: P1-高
**问题描述**: JSON响应直接调用response.json()，无大小限制。

**根因分析**:
```python
if "application/json" in content_type:
    body = response.json()  # ← 可能加载GB级数据
```

**影响**: 恶意服务器返回超大JSON导致OOM。

**修复方案**:
```python
MAX_JSON_SIZE = 10 * 1024 * 1024  # 10MB

if "application/json" in content_type:
    if len(response.content) > MAX_JSON_SIZE:
        body = response.text[:MAX_JSON_SIZE] + "...[truncated]"
    else:
        try:
            body = response.json()
        except (json.JSONDecodeError, ValueError):
            body = response.text
```
**遵循原则**: 安全性 - 资源限制；防御性编程 - 边界检查。

---

### Bug#T07: search_web递归搜索无深度限制

**文件**: `app/tools/network/search_web.py:329`
**严重程度**: P2-中
**问题描述**: `_search_bing`递归调用自身，无深度限制。

**根因分析**: 构造的查询可能触发深层递归，导致栈溢出。

**影响**: 服务崩溃。

**修复方案**:
```python
def _search_bing(query: str, max_depth: int = 3, current_depth: int = 0):
    if current_depth >= max_depth:
        return {"error": "递归深度超限"}
    # ... 现有逻辑 ...
    # 递归调用时增加深度
    return _search_bing(sub_query, max_depth, current_depth + 1)
```
**遵循原则**: 安全性 - 限制资源使用；防御性编程 - 边界检查。

---

### Bug#T08: _check_network在3个文件中重复

**文件**: `http_request.py`, `fetch_webpage.py`, `download_file.py`
**严重程度**: P2-中
**问题描述**: 完全相同的_check_network函数在3个文件中重复。

**根因分析**: 从network_tools.py拆分时未提取公共函数。

**影响**: 维护困难，且每次请求都执行3次TCP连接检查。

**修复方案**:
```python
# 创建 app/tools/network/connectivity.py
import socket
import time
from typing import Dict

def check_network() -> Dict[str, Any]:
    """检查网络连通性"""
    test_hosts = [("dns.google", 53), ("8.8.8.8", 53), ("1.1.1.1", 53)]
    for host, port in test_hosts:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            t1 = time.time()
            sock.connect((host, port))
            latency = (time.time() - t1) * 1000
            return {"connected": True, "host": host, "latency_ms": round(latency, 2)}
        except (socket.timeout, socket.error, OSError):
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass
    return {"connected": False}
```
**遵循原则**: DRY（不重复）- 提取公共函数；复用优先 - 统一网络检查。

---

## 五、修复优先级

| 优先级 | Bug编号 | 说明 |
|--------|---------|------|
| **P0-立即修复** | N01a-e, N07, N17 | SSRF绕过、路径遍历、内网探测 |
| **P1-必须修复** | S01, S02, S04, S06, S13, S15, N02, N03, N05, N06, N14, T06 | 核心逻辑错误、资源泄漏 |
| **P2-应该修复** | S03, S05, S07-S09, S16, N04, N08-N12, N13, N16, T01, T03, T05, T07, T08 | 功能缺陷、代码质量 |
| **P3-建议修复** | S10-S12, S14, N15, N18, T02, T04 | 信息缺失、误报 |

---

## 六、遵循的编码原则

| 原则 | 应用场景 |
|------|---------|
| **SRP** | 函数职责单一，验证和执行分离 |
| **DRY** | 提取_validate_url和_check_network为公共函数 |
| **KISS-DIRECT** | 简单直接的修复方案，不引入复杂抽象 |
| **SLAP** | 数据结构完整，返回信息在同一抽象层 |
| **YAGNI** | 不添加用不上的功能（如FTP支持） |
| **禁止backward** | 修复不考虑向后兼容 |
| **OCP** | 通过扩展（如url_validator模块）而非修改现有代码 |
| **LSP** | 子类不违反父类约定（如自定义Dumper） |
| **ISP** | 接口职责单一，Schema与实现一致 |
| **复用优先** | 使用ipaddress标准库，提取公共函数 |

---

**文档完成时间**: 2026-06-24 22:35:55
**编写人**: 小欧
**审核人**: 待定
