# Tool内部安全检查设计 — 复核修订版v3

**签名**: 北京老陈 2026-06-27（v3：并入path_validator分层设计）

---

## 0. 安全架构分层定义

### 系统级安全（tool外部，不属于本次设计范围）

| 层级 | 位置 | 作用 |
|------|------|------|
| 路径白名单/黑名单 | `path_validator.py` | 限制file工具可操作的路径范围 |
| 通用安全检查 | `tool_safety_checker.py` | 路径越权/写入保护/代码注入 |
| 操作记录+回滚 | `file_safety/` | 记录操作、支持回滚 |
| 用户确认 | `needs_confirmation` | 执行前需用户确认 |

> **注意**：Windows UAC/schtasks等OS权限保护属于操作系统层面，不在我们代码系统的安全架构内，不纳入分层设计。

### Tool内部安全（本次设计范围）

| 定义 | 说明 |
|------|------|
| 工具自身在执行前/执行中做的业务级安全检查 | 不依赖系统级安全 |
| 针对工具自身业务特点的风险检测 | 如SQL注入检测、Shell命令危险模式检测 |
| 在工具代码内部实现 | 不是在tool_safety_checker中实现 |

### 判断原则

**只看tool内部自身有没有做安全检查**，不看系统级的。

**只看**：工具自身代码里有没有针对自身业务特点的安全检查逻辑。

---

## 1. path_validator分层：系统级 vs Tool内部

### 1.1 现状问题

**path_validator只有1个函数`validate_path()`**，被两条链路调用：

```
链路1（系统级）: action_handler → tool_safety_checker._check_known_risks() → validate_path()
链路2（tool内部）: delete_file._validate_path() → validate_path()
                   write_text_file._validate_path() → validate_path()
                   ...（12个file工具全部透传）
```

**问题**：
1. **重复检查**：同一个检查做了两次
2. **没有差异化**：所有tool内部的`_validate_path()`都是一模一样的透传，没有任何tool特有的检查
3. **职责不清**：系统级检查"能不能访问这个路径"，tool内部也应该检查"能不能对这个路径做这个操作"，但目前两者做的是同一件事

### 1.2 分层设计

| 层级 | 函数 | 职责 | 例子 |
|------|------|------|------|
| **系统级** | `validate_path()` | 路径能不能访问（白名单+黑名单+路径穿越） | `C:\Windows\System32\config\SAM` → 禁止 |
| **tool内部** | `validate_path_for_write()`等 | 对这个路径能不能做这个操作（tool业务级检查） | 覆盖大文件WARNING、递归删除WARNING |

#### 1.2.1 系统级的validate_path（已有，不改）

```python
# path_validator.py — 系统级，所有tool共享
def validate_path(file_path, allowed_paths=None):
    """路径能不能访问"""
    # 1. 空路径拒绝
    # 2. 黑名单检查
    # 3. 路径穿越检查
    # 4. 白名单检查
```

#### 1.2.2 tool内部路径检查（新增，集中到一个文件）

**文件位置**：`backend/app/tools/validate/file_path_checker.py`

**为什么集中到一个文件**：
1. 5个tool的路径检查逻辑有关联性（write类共享、覆盖类共享）
2. 避免每个tool各写一份重复代码（DRY原则）
3. 一处修改，所有tool生效
4. 调用方只需`from app.tools.validate.file_path_checker import validate_path_for_write`

**函数清单**：

| 函数 | 适用tool | 检查内容 |
|------|---------|---------|
| `validate_path_for_write()` | write_text_file, edit_text_file | 覆盖大文件WARNING、追加到超大文件WARNING |
| `validate_path_for_delete()` | delete_file | 递归删除WARNING、永久删除WARNING |
| `validate_path_for_overwrite()` | move_file, copy_file | 覆盖目标文件WARNING |
| `validate_path_for_extract()` | extract_archive | 解压到系统目录WARNING |

**关键发现：write类检查可复用**：
- `write_text_file`和`edit_text_file`都是写入操作，共享`validate_path_for_write()`
- `move_file`和`copy_file`都是覆盖操作，共享`validate_path_for_overwrite()`

**函数实现**：

```python
# validate/file_path_checker.py — tool内部路径业务级检查（集中管理）

from pathlib import Path
from typing import Optional, Tuple


def validate_path_for_write(file_path: str, content: str = "", append: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    写入操作的路径业务级检查（适用于write_text_file、edit_text_file）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    path = Path(file_path)
    if path.exists() and path.is_file():
        if not append:
            old_size = path.stat().st_size
            if old_size > 1024 * 1024:
                return True, None, f"覆盖大文件({old_size}字节)，请确认"
        else:
            old_size = path.stat().st_size
            if old_size > 100 * 1024 * 1024:
                return True, None, f"追加到超大文件({old_size}字节)，请确认"
    return True, None, None


def validate_path_for_delete(file_path: str, recursive: bool = False, force: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    删除操作的路径业务级检查（适用于delete_file）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    if recursive and Path(file_path).is_dir():
        return True, None, "递归删除目录，请确认"
    if force:
        return True, None, "永久删除（绕过回收站），请确认"
    return True, None, None


def validate_path_for_overwrite(source: str, destination: str, overwrite: bool = False) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    覆盖操作的路径业务级检查（适用于move_file、copy_file）
    
    Returns: (is_valid, error_msg, warning_msg)
    注意：文件存在检查与实际操作之间存在时间窗口（TOCTOU），
    检查结果仅作为参考，不保证操作时的文件状态一致。
    """
    if overwrite and Path(destination).exists():
        return True, None, f"覆盖目标文件，请确认"
    return True, None, None


def validate_path_for_extract(output_dir: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    解压操作的路径业务级检查（适用于extract_archive）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    system_dirs = ["windows", "program files", "program files (x86)"]
    output_lower = output_dir.lower()
    for sd in system_dirs:
        if sd in output_lower:
            return True, None, f"解压到系统目录，请确认"
    return True, None, None
```

### 1.3 各tool内部路径检查需求（完整梳理）

> **关键发现**：除了file类工具外，document、network、desktop、dataanalysis四类工具**完全没有路径检查**——既没有tool内部的，也没有系统级的（`tool_safety_checker`只覆盖`ToolCategory.FILE`）

#### 1.3.1 file类工具（13个）— ✅ 有系统级路径检查

| 工具 | 系统级检查 | tool内部需要额外检查的 | 使用的检查函数 |
|------|-----------|----------------------|---------------|
| read_text_file | ✅ | 无（只读） | ❌ |
| write_text_file | ✅ | 覆盖大文件WARNING | `validate_path_for_write` |
| edit_text_file | ✅ | 覆盖大文件WARNING | `validate_path_for_write` |
| delete_file | ✅ | 递归删除WARNING、永久删除WARNING | `validate_path_for_delete` |
| move_file | ✅ | 覆盖目标文件WARNING | `validate_path_for_overwrite` |
| copy_file | ✅ | 覆盖目标文件WARNING | `validate_path_for_overwrite` |
| compress_files | ✅ | 无 | ❌ |
| extract_archive | ✅ | 解压到系统目录WARNING | `validate_path_for_extract` |
| list_directory | ✅ | 无（只读） | ❌ |
| search_files | ✅ | 无（只读） | ❌ |
| grep_file_content | ✅ | 无（只读） | ❌ |
| read_media_file | ✅ | 无（只读） | ❌ |
| rename_file | ✅ | 无（内部调用move_file） | ❌ |

#### 1.3.2 document类工具（8个）— ❌ 完全没有路径检查

| 工具 | 路径参数 | 读/写 | 使用的检查函数 |
|------|---------|-------|---------------|
| read_docx | `file_name` | 读 | ❌ 只读，系统级应覆盖 |
| read_pdf | `file_name` | 读 | ❌ 只读，系统级应覆盖 |
| read_pptx | `file_name` | 读 | ❌ 只读，系统级应覆盖 |
| read_xlsx | `file_name` | 读 | ❌ 只读，系统级应覆盖 |
| **write_docx** | `file_name` | **写** | `validate_path_for_write` |
| **write_pdf** | `file_name` | **写** | `validate_path_for_write` |
| **write_pptx** | `file_name` | **写** | `validate_path_for_write` |
| **write_xlsx** | `file_name` | **写** | `validate_path_for_write` |

#### 1.3.3 dataanalysis类工具（6个）— ❌ 完全没有路径检查

| 工具 | 路径参数 | 读/写 | 使用的检查函数 |
|------|---------|-------|---------------|
| analyze_data | `file_path`（与data互斥） | 读 | ❌ 只读，系统级应覆盖 |
| filter_data | `file_path`（与data互斥） | 读 | ❌ 只读，系统级应覆盖 |
| **generate_chart** | `output_path` | **写** | `validate_path_for_write` |
| query_sql | `db_path` | 读 | ❌ 只读，系统级应覆盖 |
| **execute_sql** | `db_path` | **写** | ❌ 数据库记录写入，非文件写入，不适用file_path_checker |
| get_db_schema | `db_path` | 读 | ❌ 只读，系统级应覆盖 |

#### 1.3.4 network类工具（1个有路径）— ❌ 完全没有路径检查

| 工具 | 路径参数 | 读/写 | 使用的检查函数 |
|------|---------|-------|---------------|
| **download_file** | `destination_path` | **写** | `validate_path_for_write` |

> **说明**：download_file已有路径遍历检查（第139-143行），但没有系统级路径白名单/黑名单检查

#### 1.3.5 desktop类工具（1个有路径）— ❌ 完全没有路径检查

| 工具 | 路径参数 | 读/写 | 使用的检查函数 |
|------|---------|-------|---------------|
| **screen_capture** | `output_path` | **写** | `validate_path_for_write` |

> **说明**：screen_capture默认保存到temp目录，但用户可指定output_path写入任意位置

#### 1.3.6 其他类工具（无路径参数）

| 分类 | 工具 | 路径参数 | 说明 |
|------|------|---------|------|
| shell | execute_shell_command、execute_code、find_command、shell_session | 无文件路径 | 操作命令/代码，不操作文件路径 |
| system | event_log、create_task、delete_task、list_tasks | 无文件路径 | 操作系统服务，不操作文件路径 |
| win_registry | registry_read、registry_write、registry_delete | 注册表路径（非文件路径） | 注册表路径与文件路径不同，不适用file_path_checker |
| fundamental | get_system_info、time_add、time_diff、query_calendar | 无路径 | 系统信息/时间计算/日历查询 |
| timer | timer_set、timer_clear、timer_list | 无路径 | 定时器 |

### 1.4 汇总：需要路径检查的写入类工具

**所有有写入路径参数的工具**（共13个）：

| 工具 | 分类 | 写入路径参数 | 使用的检查函数 |
|------|------|-------------|---------------|
| write_text_file | file | `file_path` | `validate_path_for_write` |
| edit_text_file | file | `file_path` | `validate_path_for_write` |
| delete_file | file | `source` | `validate_path_for_delete` |
| move_file | file | `destination` | `validate_path_for_overwrite` |
| copy_file | file | `destination` | `validate_path_for_overwrite` |
| extract_archive | file | `destination` | `validate_path_for_extract` |
| write_docx | document | `file_name` | `validate_path_for_write` |
| write_pdf | document | `file_name` | `validate_path_for_write` |
| write_pptx | document | `file_name` | `validate_path_for_write` |
| write_xlsx | document | `file_name` | `validate_path_for_write` |
| generate_chart | dataanalysis | `output_path` | `validate_path_for_write` |
| download_file | network | `destination_path` | `validate_path_for_write` |
| screen_capture | desktop | `output_path` | `validate_path_for_write` |

> **注意**：execute_sql虽标注为"写"操作，但写入的是数据库记录而非文件，不适用file_path_checker，其安全检查由已有的`_check_sql_safety()`覆盖。

**`validate_path_for_write`被8个工具共享**，是复用率最高的检查函数。

**关键发现**：
- rename_file内部调用`_move_file_impl()`，因此`validate_path_for_overwrite`必须实现在`_move_file_impl()`内部（而非`move_file()`外层），rename_file才能继承此检查
- write_text_file和edit_text_file共享`validate_path_for_write`
- move_file和copy_file共享`validate_path_for_overwrite`
- 只读类工具（read_text_file、list_directory、search_files、grep_file_content、read_media_file）不需要tool内部检查

### 1.5 实施方案

1. **系统级检查不变**：`validate_path()`保持原样，tool_safety_checker继续调用
2. **系统级检查扩展**：`tool_safety_checker._check_known_risks()`应扩展路径检查覆盖`ToolCategory.DATAANALYSIS`、`ToolCategory.DOCUMENT`、`ToolCategory.NETWORK`、`ToolCategory.DESKTOP`（当前只覆盖`ToolCategory.FILE`），确保所有有路径参数的工具都有系统级路径保护
3. **新建集中文件**：`backend/app/tools/validate/file_path_checker.py`，包含4个检查函数
4. **去掉透传**：不需要差异化检查的8个file工具，去掉tool内部的`_validate_path()`透传（系统级已覆盖，重复调用无意义）
5. **13个写入类工具调用集中文件**：按1.4节汇总表，从`app.tools.validate.file_path_checker`导入对应的检查函数
6. **返回值扩展**：tool内部检查返回`(is_valid, error_msg, warning_msg)`，支持WARNING
7. **调用集成模式**：检查函数在tool主函数最开头手动调用
8. **warning处理规则**：
   - `error_msg`非空 → 阻断执行，返回错误给用户
   - `warning_msg`非空且`is_valid=True` → **不阻断执行**，记录WARNING日志，warning信息返回给调用方
   - 当前**不触发**系统级`needs_confirmation`流程（warning仅为提示，非强制阻断）

## 2. delete_file — ✅ 需要tool内部路径检查

### tool内部现有安全检查

**无**。delete_file内部没有针对"删除"操作的业务级安全检查。

### tool内部需要什么

delete_file的业务是"删除文件"，有业务级风险：
- 递归删除目录 → WARNING
- 永久删除（force=True）→ WARNING

### 最终方案

**需要tool内部路径检查**: ✅ 是（`_validate_path_for_delete`）

详见第1.2.2节。

---

## 3. registry_write — ❌ 不需要独立safety代码

### tool内部现有安全检查

**无**。registry_write内部没有针对"注册表写入"的业务级安全检查。

### 为什么不需要

registry_write的业务是"写入注册表键值"，没有"危险写入模式"和"安全写入模式"之分。写入就是写入。

### 最终方案

**需要独立safety代码**: ❌ 否

**原因**: registry_write的业务逻辑简单（写入键值），没有需要tool内部检测的"危险模式"。

---

## 4. registry_delete — ❌ 不需要额外safety代码

### tool内部现有安全检查

**有**。非空键检查（需要recursive=True）——这是tool内部的业务级安全检查。

### 最终方案

**需要独立safety代码**: ❌ 否

**原因**: 已有非空键检查，没有额外的业务级安全逻辑需要做。

---

## 5. create_task — ❌ 不需要独立safety代码

### tool内部现有安全检查

**无**。create_task内部没有针对"创建任务"的业务级安全检查。

### 为什么不需要

create_task的业务是"创建计划任务"，没有"危险任务模式"和"安全任务模式"之分。创建任务就是创建任务。

### 最终方案

**需要独立safety代码**: ❌ 否

**原因**: create_task的业务逻辑简单（创建任务），没有需要tool内部检测的"危险模式"。

---

## 6. delete_task — ❌ 不需要额外safety代码

### tool内部现有安全检查

**有**。任务存在检查（schtasks /query）——这是tool内部的业务级安全检查。

### 最终方案

**需要独立safety代码**: ❌ 否

**原因**: 已有任务存在检查，没有额外的业务级安全逻辑需要做。

---

## 7. execute_sql — ❌ 不需要额外safety代码

### tool内部现有安全检查

**有**。`_check_sql_safety()`——这是tool内部的业务级安全检查：

```python
# execute_sql.py:21-36
def _check_sql_safety(sql: str, dry_run: bool) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """
    统一危险模式检测 + 无WHERE检测 + 拦截决策 — 小沈 2026-05-25
    Returns: (has_danger, warning_msg, dangerous_list)
        has_danger=True  → 命中危险模式，warning_msg非空，dangerous_list含匹配项
        has_danger=False → 无危险模式，warning_msg=None，dangerous_list=None
    """
    sql_upper = sql.strip().upper()
    DANGEROUS_PATTERN = re.compile(r'\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', re.IGNORECASE)
    dangerous_matches = DANGEROUS_PATTERN.findall(sql)
    if re.match(r'\s*(DELETE|UPDATE)\s', sql_upper) and 'WHERE' not in sql_upper:
        dangerous_matches.append('NO_WHERE')
    if dangerous_matches:
        warnings = []
        dangerous_to_show = [d for d in dangerous_matches if d != 'NO_WHERE']
        if dangerous_to_show:
            warnings.append(f"危险操作: {dangerous_to_show}")
        if 'NO_WHERE' in dangerous_matches:
            warnings.append("缺少 WHERE 条件")
        return True, f"警告:检测到危险操作 {'+'.join(warnings)},已拦截执行。可使用dry_run=true预演", dangerous_matches
    return False, None, None
```

**其他检查**（在`_check_sql_safety`之上，由主函数`execute_sql`控制）：

**语义差异**：`_check_sql_safety`返回`has_danger=True`=命中危险（与`_validate_path_for_*`的`is_valid=True`=检查通过含义相反），实现时注意区分：
| 函数 | 含义 | True表示 |
|------|------|---------|
| `_validate_path_for_*` | `(is_valid, error_msg, warning_msg)` | ✅ 检查通过，可以继续 |
| `_check_sql_safety` | `(has_danger, warning_msg, dangerous_list)` | 🔴 检测到危险，应拦截 |

### 最终方案

**需要独立safety代码**: ❌ 否

**原因**: 已有完善的tool内部安全检查（带危险模式检测 + 无WHERE检测 + 行数限制 + dry_run）。

---

## 8. compress_files — ❌ 不需要独立safety代码

### tool内部现有安全检查

**无**。compress_files内部没有针对"压缩"操作的业务级安全检查。

### 为什么不需要

compress_files的业务是"压缩文件"，没有"危险压缩模式"和"安全压缩模式"之分。压缩就是压缩。

### 最终方案

**需要独立safety代码**: ❌ 否

**原因**: compress_files的业务逻辑简单（压缩文件），没有需要tool内部检测的"危险模式"。

---

## 9. extract_archive — ✅ 需要tool内部路径检查

### tool内部现有安全检查

**有**。`_is_safe_path()`——路径遍历检查（Zip Slip防护）。

### tool内部还需要什么

解压到系统目录 → WARNING

### 最终方案

**需要tool内部路径检查**: ✅ 是（`_validate_path_for_extract`）

详见第1.2.2节。

---

## 10. write_text_file — ✅ 需要tool内部路径检查

### tool内部现有安全检查

**无**（系统级有写入大小保护，但那是系统级的）。

### tool内部需要什么

覆盖大文件 → WARNING

### 最终方案

**需要tool内部路径检查**: ✅ 是（`_validate_path_for_write`）

详见第1.2.2节。

---

## 11. move_file — ✅ 需要tool内部路径检查

### tool内部需要什么

覆盖目标文件 → WARNING

### 最终方案

**需要tool内部路径检查**: ✅ 是（`validate_path_for_overwrite`）

详见第1.2.2节。

---
## 12. copy_file — ✅ 需要tool内部路径检查

### tool内部需要什么

覆盖目标文件 → WARNING

### 最终方案

**需要tool内部路径检查**: ✅ 是（`validate_path_for_overwrite`）

详见第1.2.2节。


## 总结

### 需要tool内部安全代码的工具（6个file类 + 7个其他类，共13个）

| 工具 | 安全类型 | 具体内容 |
|------|---------|---------|
| **delete_file** | tool内部业务级检查 | `validate_path_for_delete`（递归删除WARNING、永久删除WARNING） |
| **write_text_file** | tool内部业务级检查 | `validate_path_for_write`（覆盖大文件WARNING） |
| **edit_text_file** | tool内部业务级检查 | `validate_path_for_write`（覆盖大文件WARNING） |
| **move_file** | tool内部业务级检查 | `validate_path_for_overwrite`（覆盖目标文件WARNING） |
| **copy_file** | tool内部业务级检查 | `validate_path_for_overwrite`（覆盖目标文件WARNING） |
| **extract_archive** | tool内部业务级检查 | `validate_path_for_extract`（解压到系统目录WARNING） |
| **write_docx** | tool内部业务级检查 | `validate_path_for_write`（覆盖大文件WARNING） |
| **write_pdf** | tool内部业务级检查 | `validate_path_for_write`（覆盖大文件WARNING） |
| **write_pptx** | tool内部业务级检查 | `validate_path_for_write`（覆盖大文件WARNING） |
| **write_xlsx** | tool内部业务级检查 | `validate_path_for_write`（覆盖大文件WARNING） |
| **generate_chart** | tool内部业务级检查 | `validate_path_for_write`（覆盖输出文件WARNING） |
| **download_file** | tool内部业务级检查 | `validate_path_for_write`（覆盖目标文件WARNING） |
| **screen_capture** | tool内部业务级检查 | `validate_path_for_write`（覆盖输出文件WARNING） |

### 不需要额外安全代码的工具（6个）

| 工具 | 原因 |
|------|------|
| registry_write | 业务逻辑简单，无危险模式 |
| registry_delete | 已有非空键检查 |
| create_task | 业务逻辑简单，无危险模式 |
| delete_task | 已有任务存在检查 |
| execute_sql | 已有完善的_check_sql_safety（数据库写入，不适用file_path_checker） |
| compress_files | 业务逻辑简单，无危险模式 |

### 需要去掉_validate_path透传的8个file工具

read_text_file、edit_text_file、list_directory、search_files、grep_file_content、read_media_file、rename_file、compress_files

> **rename_file 特别说明**：rename_file 自身不直接调用 `_validate_path` 透传，而是通过 `_move_file_impl()` 间接使用。因此去掉透传对它无直接影响。但设计上要注意：`validate_path_for_overwrite` 必须实现在 `_move_file_impl()` 内部才能被 rename_file 继承使用。

---

## 13. URL统一检查 — validate/url_validator.py

**签名**: 小沈 2026-06-27 10:56:50

### 13.1 问题背景

除了文件路径（file_path）外，**URL是另一类跨工具出现的资源定位参数**，具有类似的安全风险：

| 风险 | 类比文件路径 | 影响 |
|------|------------|------|
| SSRF（服务端请求伪造） | 路径遍历 | 攻击内网服务、云metadata端点 |
| 恶意端点访问 | 黑名单路径 | 下载恶意软件、访问钓鱼网站 |
| 内网服务探测 | 访问系统目录 | 扫描内部端口、探测内网拓扑 |
| proxy滥用 | 无类比 | 通过proxy跳板攻击第三方 |

**当前状态**：HTTP请求类工具**完全没有URL安全检查**（既无系统级，也无tool内部）。

### 13.2 涉及工具

| 工具 | 类别 | URL参数 | proxy参数 | 风险等级 |
|------|------|---------|-----------|---------|
| **http_request** | network | `url` | `proxy`（可选） | 🔴 SSRF + 内网探测 |
| **download_file** | network | `url` | `proxy`（可选） | 🔴 SSRF + 恶意文件下载 |
| **fetch_webpage** | network | `url` | `proxy`（可选） | 🔴 SSRF + 内网内容获取 |
| **search_web** | network | 无URL参数 | `proxy`（可选） | 🟡 proxy滥用 |

### 13.3 文件位置

`backend/app/tools/validate/url_validator.py`

**统一放在validate目录下**：URL检查与file_path检查、timeout检查、registry检查同属参数验证范畴，统一放在`tools/validate/`便于管理。调用方只需`from app.tools.validate.url_validator import validate_url`。

### 13.4 函数设计

#### 13.4.1 核心验证函数

```python
# validate/url_validator.py — URL业务级安全检查（集中管理）

from urllib.parse import urlparse
from typing import Optional, Tuple

# 协议白名单：仅允许安全的协议
ALLOWED_PROTOCOLS = {"https"}

# 内网IP段（用于DNS解析后检查）
# 注意：仅覆盖IPv4内网段。IPv6内网（fd00::/8）暂未覆盖，
# 因为当前URL场景几乎不会出现IPv6地址，且validate_url需兼容IPv6需额外处理。
PRIVATE_IP_PREFIXES = (
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.",
)

# 回环地址/本地地址
LOOPBACK = ("127.", "0.", "::1", "localhost")


def validate_url(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    URL业务级安全检查（适用于http_request、download_file、fetch_webpage）
    
    检查内容：
    1. URL格式是否合法
    2. 协议是否在白名单内（仅允许https）
    3. 主机名是否为内网/回环地址（SSRF防护）
    4. 是否为裸IP+端口（绕过SSRF常见手法）
    
    Returns: (is_valid, error_msg, warning_msg)
        is_valid=True  → 检查通过，可以继续请求
        is_valid=False → 检查未通过，error_msg非空（阻断执行）
        warning_msg非空 → 有安全提示但不阻断
    """
    if not url or not isinstance(url, str):
        return False, "URL不能为空", None
    
    try:
        parsed = urlparse(url)
    except Exception:
        return False, f"URL格式解析失败: {url}", None
    
    # 检查1: 协议白名单
    if parsed.scheme not in ALLOWED_PROTOCOLS:
        return False, f"不允许的协议: {parsed.scheme}（仅允许https）", None
    
    # 检查2: 主机名是否为空
    hostname = parsed.hostname
    if not hostname:
        return False, f"URL缺少主机名: {url}", None
    
    # 检查3: 回环地址
    host_lower = hostname.lower()
    if host_lower in LOOPBACK or host_lower.startswith(LOOPBACK):
        return False, f"不允许访问回环地址: {hostname}", None
    
    # 检查4: 内网IP地址（包括DNS解析后检查）
    if _is_private_ip(hostname):
        return False, f"不允许访问内网地址: {hostname}", None
    
    # 检查5: DNS二次校验（防DNS rebinding攻击）
    # TODO: 实现DNS解析后二次校验 resolved_ip 是否在内网段
    # resolved_ips = socket.getaddrinfo(hostname, 80)
    # for ip in resolved_ips: if _is_private_ip(ip): return False, ...
    
    # 检查6: 裸IP + 端口（SSRF绕过常见手法）
    if _is_literal_ip(host_lower):
        return True, None, f"目标为IP地址而非域名，请确认"
    
    return True, None, None


def validate_proxy(proxy: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    proxy地址安全检查（适用于所有HTTP类工具）
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    if not proxy:
        return True, None, None
    
    try:
        parsed = urlparse(proxy)
    except Exception:
        return False, f"proxy地址格式解析失败: {proxy}", None
    
    hostname = parsed.hostname
    if not hostname:
        return False, f"proxy地址缺少主机名: {proxy}", None
    
    host_lower = hostname.lower()
    if host_lower in LOOPBACK or host_lower.startswith(LOOPBACK):
        return False, f"不允许使用localhost作为proxy", None
    
    if _is_private_ip(hostname):
        return False, f"不允许使用内网地址作为proxy", None
    
    return True, None, None


def _is_private_ip(hostname: str) -> bool:
    """检查主机名是否为内网IP"""
    host_lower = hostname.lower()
    for prefix in PRIVATE_IP_PREFIXES:
        if host_lower.startswith(prefix):
            return True
    return False


def _is_literal_ip(hostname: str) -> bool:
    """检查主机名是否为IP地址（而非域名）
    
    注意：正则仅做格式校验（形如x.x.x.x），不验证各段数值范围（0-255）。
    非法IP（如999.999.999.999）不会被DNS解析，后续请求会因DNS失败而阻断，
    因此此处格式校验足够安全。
    """
    import re
    if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', hostname):
        return True
    if ':' in hostname:
        return True
    return False
```

#### 13.4.2 集成调用模式

**各tool入口处调用**：

```python
# 示例：http_request._execute() 最开头
from app.tools.validate.url_validator import validate_url, validate_proxy

def _execute(self, url, method="GET", headers=None, body=None, 
             timeout=30, proxy=None, retry=1):
    # 第1步：URL安全检查
    is_valid, error_msg, warning_msg = validate_url(url)
    if not is_valid:
        return {"code": "PARAM_ERROR", "data": None, "message": error_msg}
    if warning_msg:
        logger.warning(f"[URL安全提示] {warning_msg}")
        # warning不阻断，继续执行
    
    # 第2步：proxy安全检查
    is_valid, error_msg, warning_msg = validate_proxy(proxy)
    if not is_valid:
        return {"code": "PARAM_ERROR", "data": None, "message": error_msg}
    
    # 第3步：原始逻辑继续...
```

**同样的模式适用于 download_file 和 fetch_webpage**。

### 13.5 工具集成对照表

| 工具 | 调用的检查函数 | 检查位置 |
|------|--------------|---------|
| http_request | `validate_url(url)` + `validate_proxy(proxy)` | `_execute()` 第一行 |
| download_file | `validate_url(url)` + `validate_proxy(proxy)` | `_execute()` 第一行 |
| fetch_webpage | `validate_url(url)` + `validate_proxy(proxy)` | `_execute()` 第一行 |
| search_web | `validate_proxy(proxy)` | `_execute()` 第一行 |

### 13.6 实施步骤

1. 新建 `backend/app/tools/validate/url_validator.py`，实现上述函数（注：该文件已存在并被 network_diagnose.py 导入使用，需对照§13.4设计逐函数验证完善）
2. 修改 http_request、download_file、fetch_webpage 的 `_execute()` 入口
3. 修改 search_web 的 `_execute()` 入口（仅proxy检查）
4. 编写单元测试（覆盖：合法URL、非法协议、内网IP、回环地址、proxy检查）

### 13.7 注意事项

- **SSRF防护不能仅靠IP黑名单**：攻击者可利用DNS rebinding绕过，增加DNS解析后二次检查
- **如果需要支持HTTP**（本地开发场景），应通过配置项开启：`config.allow_http_urls=True`
- **url_validator 只做业务级安全检查**，系统级安全（如URL黑名单）应在 tool_safety_checker 中实现

---

## 14. Timeout统一检查 — validate/timeout_validator.py

**签名**: 小沈 2026-06-27 10:56:50

### 14.1 问题背景

**timeout是跨工具出现次数最多的参数**（6个工具），但存在严重的**单位不一致**问题：

| 工具 | 参数名 | 当前单位 | LLM看到的默认值 | LLM理解误区 |
|------|-------|---------|----------------|-------------|
| http_request | `timeout` | **毫秒** | 30000（=30秒） | LLM可能传`timeout=30`期望30秒，实际只有30ms |
| download_file | `timeout` | **毫秒** | 60000（=60秒） | 同上 |
| fetch_webpage | `timeout` | **毫秒** | 30000（=30秒） | 同上 |
| network_diagnose | `timeout` | **秒** | 10（=10秒） | LLM可能传`timeout=10000`期望10秒，实际等2.7小时 |
| execute_shell_command | `timeout` | **毫秒** | 60000（=60秒） | 同前三个 |
| execute_code | `timeout` | **毫秒** | 30000（=30秒） | 同前三个 |

**根源**：参数名都是`timeout`但语义不同——LLM无法区分"这个timeout是毫秒，那个是秒"。

### 14.2 文件位置

`backend/app/tools/validate/timeout_validator.py`

**统一放在validate目录下**：timeout与file_path、URL、registry同属参数验证范畴，统一放在`tools/validate/`便于管理。调用方只需`from app.tools.validate.timeout_validator import validate_timeout`。

### 14.3 函数设计

#### 14.3.1 统一规范

**Schema给LLM用秒，工具内部直接传秒（无需转换）**：

| 层 | 参数名 | 单位 | 说明 |
|----|--------|------|------|
| **Schema（LLM看到的）** | `timeout` | **秒** | LLM传`timeout=30`表示30秒，人类直觉 |
| **集中验证器** | `timeout` | **秒** | 按秒验证min/max范围 |
| **工具内部** | `timeout` | **秒** | **直接传**给httpx/subprocess（底层API全要秒） |

**原因**：
- LLM是文本生成模型，人习惯说"30秒"不是"30000毫秒"
- 如果schema写`timeout_ms`，LLM很可能传30（以为是秒），实际变成30ms
- 底层API（httpx、subprocess.run、asyncio.wait_for）全部期望**秒**，传秒无需任何转换
- 唯一例外：fetch_webpage的Playwright路径要毫秒，内部自行 `timeout * 1000`

#### 14.3.2 集中验证函数

```python
# validate/timeout_validator.py — timeout参数统一验证（跨工具共享）

from typing import Optional, Tuple


# 各工具timeout范围（秒）
# 只验证合理性，不限制过死
TIMEOUT_RANGES_SECONDS = {
    "http_request":           (1,   300),     # 1秒 ~ 5分钟
    "download_file":          (5,  3600),     # 5秒 ~ 1小时
    "fetch_webpage":          (1,   120),     # 1秒 ~ 2分钟
    "network_diagnose":       (1,    30),     # 1秒 ~ 30秒
    "execute_shell_command":  (1,   600),     # 1秒 ~ 10分钟
    "execute_code":           (1,   300),     # 1秒 ~ 5分钟
}


def validate_timeout(timeout: int, tool_name: str) -> Tuple[bool, Optional[str], None]:
    """
    timeout参数验证（适用于所有有timeout的工具）
    
    参数：timeout — 秒（schema给LLM暴露的单位就是秒）
    
    检查内容：
    1. timeout必须为正整数
    2. timeout必须在工具对应的[min_seconds, max_seconds]范围内
    
    Returns: (is_valid, error_msg, None)
        is_valid=False → error_msg非空，阻断执行
        is_valid=True  → 检查通过
    """
    if not isinstance(timeout, int) or timeout <= 0:
        return False, f"timeout必须为正整数（秒），收到: {timeout}", None
    
    if tool_name not in TIMEOUT_RANGES_SECONDS:
        return True, None, None
    
    min_s, max_s = TIMEOUT_RANGES_SECONDS[tool_name]
    if timeout < min_s:
        return False, f"{tool_name}的timeout不能小于{min_s}秒", None
    if timeout > max_s:
        return False, f"{tool_name}的timeout不能大于{max_s}秒", None
    
    return True, None, None
```

#### 14.3.3 工具内部转换用法

```python
# 示例：http_request._execute() 入口处

def _execute(self, url, method="GET", headers=None, body=None, 
             timeout=30, proxy=None, retry=1):
    # timeout来自LLM（秒），例如 timeout=30 表示30秒
    
    # 第1步：验证timeout（秒）
    from app.tools.validate.timeout_validator import validate_timeout
    is_valid, error_msg, _ = validate_timeout(timeout, "http_request")
    if not is_valid:
        return {"code": "PARAM_ERROR", "data": None, "message": error_msg}
    
    # 第2步：直接传秒给底层API（httpx、subprocess等全要秒）
    # 注意：去掉当前代码中 timeout / 1000.0 的转换
    response = httpx.Client().get(url, timeout=timeout)
```

**同样的模式适用于所有6个工具**：
- schema参数保持 `timeout: int`（秒）
- 入口调用 `validate_timeout(timeout, tool_name)`
- 内部直接传 `timeout`（秒），去除当前代码中的 `/ 1000.0` 转换
- 唯一例外：fetch_webpage的Playwright路径，内部 `timeout * 1000` 转毫秒

### 14.4 工具集成对照表

| 工具 | Schema参数 | 单位 | 验证范围 | 内部处理 |
|------|-----------|------|---------|---------|
| http_request | `timeout` | 秒 | 1 ~ 300秒 | 直接传秒 → httpx |
| download_file | `timeout` | 秒 | 5 ~ 3600秒 | 直接传秒 → httpx |
| fetch_webpage (httpx) | `timeout` | 秒 | 1 ~ 120秒 | 直接传秒 → httpx |
| fetch_webpage (Playwright) | `timeout` | 秒 | 1 ~ 120秒 | ×1000转毫秒 → playwright |
| network_diagnose | `timeout` | 秒 | 1 ~ 30秒 | 直接传秒 → ping/port |
| execute_shell_command | `timeout` | 秒 | 1 ~ 600秒 | 直接传秒 → subprocess |
| execute_code | `timeout` | 秒 | 1 ~ 300秒 | 直接传秒 → subprocess |

### 14.5 实施步骤（已完成 ✅）

| 步骤 | 状态 | 详情 |
|------|------|------|
| 1. 新建 `timeout_validator.py` | ⏳ 待做 | 集中验证函数 |
| 2. 改2个schema文件（6个tool） | ✅ **已做** | `backend/app/tools/network/network_schema.py` + `shell/shell_schema.py` |
| 3. 入口调用 `validate_timeout()` | ⏳ 待做 | 等 `timeout_validator.py` 实现后接入 |
| 4. 去掉内部 `/ 1000.0` 转换 | ✅ **已做** | 5个实现文件全部去掉，直接传秒 |
| 5. 修复下限1ms→1秒 | ✅ **已做** | `execute_shell_command` + `execute_code` |
| 6. 编写单元测试 | ⏳ 待做 | 等 `timeout_validator.py` 实现后补充 |

### 14.6 注意事项

- **network_diagnose无需修改**：schema已是秒，内部已是秒（Windows ping ×1000转毫秒、Linux -W用秒、端口检查用秒），是6个工具中最干净的
- **execute_shell_command/execute_code下限1ms修复**：当前下限太短（1ms不可能执行任何命令），改为1秒下限

---

## 15. Registry key_path检查 — validate/registry_path_checker.py

**签名**: 小沈 2026-06-27 10:56:50

### 15.1 问题背景

注册表路径（key_path）是**第三类跨工具出现的资源定位参数**，与文件路径类似但有不同的安全风险：

| 风险 | 类比 | 影响 |
|------|------|------|
| 系统级键路径修改 | 访问系统目录 | `HKLM\...` 可影响系统启动、服务配置 |
| 自启动持久化 | 文件写入 | `...\Run\...` 可设置开机自启 |
| 删除保护不足 | 递归删除 | 删掉整个键子树导致系统异常 |

**当前状态**：注册表3个工具**完全没有key_path格式验证和关键键保护**。

### 15.2 涉及工具

| 工具 | 类别 | key_path参数 | 操作 | 风险等级 |
|------|------|-------------|------|---------|
| **registry_read** | win_registry | `key_path` + `hive` | 读 | 🟢 只读，几乎无风险 |
| **registry_write** | win_registry | `key_path` + `value_name` + `value` + `hive` | **写** | 🔴 可写入Run等自启动键 |
| **registry_delete** | win_registry | `key_path` + `value_name` + `hive` + `recursive` | **删** | 🔴 可删除系统关键键 |

### 15.3 文件位置

`backend/app/tools/validate/registry_path_checker.py`

### 15.4 函数设计

```python
# validate/registry_path_checker.py — 注册表路径业务级安全检查（集中管理）

from typing import Optional, Tuple

# Hive白名单：允许操作的hive
ALLOWED_HIVES = {"HKCU", "HKLM"}

# 关键键黑名单（写入/删除时需WARNING）
# 匹配规则：key_path中包含以下任一子串即触发警告
CRITICAL_KEY_PATTERNS = (
    # 自启动相关
    r"\Software\Microsoft\Windows\CurrentVersion\Run",
    r"\Software\Microsoft\Windows\CurrentVersion\RunOnce",
    r"\Software\Microsoft\Windows\CurrentVersion\RunServices",
    r"\Software\Microsoft\Windows\CurrentVersion\RunServicesOnce",
    # 安全配置
    r"\Software\Microsoft\Windows\CurrentVersion\Policies",
    r"\Software\Microsoft\Windows\CurrentVersion\Security",
    # 系统服务
    r"\System\CurrentControlSet\Services",
    r"\Software\Microsoft\Windows NT\CurrentVersion\Winlogon",
    # 浏览器配置
    r"\Software\Microsoft\Internet Explorer",
    r"\Software\Google\Chrome",
)


# Hive全名→简写映射（key_path中可能带全名前缀）
HIVE_FULL_TO_SHORT = {
    "HKEY_LOCAL_MACHINE": "HKLM",
    "HKEY_CURRENT_USER": "HKCU",
    "HKEY_CLASSES_ROOT": None,       # 不允许
    "HKEY_USERS": None,              # 不允许
    "HKEY_CURRENT_CONFIG": None,     # 不允许
}


def _normalize_key_path(key_path: str, hive: str) -> Tuple[str, str]:
    """
    规范化key_path：剥离key_path中可能带有的hive前缀，返回(key_path_clean, hive)。
    
    如果key_path以HKLM\或HKCU\或全名开头，剥离前缀并覆盖hive参数。
    """
    path_upper = key_path.upper()
    # 检查简写前缀
    for prefix in ALLOWED_HIVES:
        if path_upper.startswith(prefix + "\\") or path_upper.startswith(prefix + "/"):
            return key_path[len(prefix) + 1:], prefix
    # 检查全名前缀
    for full, short in HIVE_FULL_TO_SHORT.items():
        if path_upper.startswith(full + "\\") or path_upper.startswith(full + "/"):
            if short is None:
                return key_path, "INVALID"  # 不允许的hive
            return key_path[len(full) + 1:], short
    return key_path, hive


def validate_registry_key(key_path: str, hive: str, operation: str = "read") -> Tuple[bool, Optional[str], Optional[str]]:
    """
    注册表路径业务级安全检查（适用于registry_read、registry_write、registry_delete）
    
    检查内容：
    1. key_path不能为空
    2. key_path不能包含路径穿越（..）
    3. key_path不能以\结尾
    4. hive必须在白名单内（支持HKLM/HKCU简写和HKEY_*全名）
    5. HKLM hive需要WARNING（系统级影响）
    6. 写入/删除关键键需要WARNING
    
    Returns: (is_valid, error_msg, warning_msg)
        is_valid=False → error_msg非空，阻断执行
        is_valid=True  → 检查通过
        warning_msg非空 → 有安全提示但不阻断
    """
    # 检查1: key_path非空
    if not key_path or not isinstance(key_path, str):
        return False, "key_path不能为空", None
    
    # 规范化：处理key_path中可能含有的hive前缀
    clean_key_path, resolved_hive = _normalize_key_path(key_path, hive)
    key_path = clean_key_path
    hive = resolved_hive
    
    # 检查2: hive白名单（同时支持简写和全名）
    hive_upper = hive.upper() if hive else "HKCU"
    if hive_upper not in ALLOWED_HIVES:
        return False, f"不允许的hive: {hive_upper}（仅允许HKCU、HKLM）", None
    
    # 检查3: 路径穿越
    if ".." in key_path:
        return False, "key_path不能包含路径穿越符(..)", None
    
    # 检查4: 结尾反斜杠
    if key_path.endswith("\\") or key_path.endswith("/"):
        return False, "key_path不能以\\结尾", None
    
    # 检查5: HKLM → WARNING
    warnings = []
    if hive_upper == "HKLM":
        warnings.append("HKLM涉及系统级注册表，请确认")
    
    # 检查6: 关键键（写入/删除操作）
    if operation in ("write", "delete"):
        for pattern in CRITICAL_KEY_PATTERNS:
            if pattern.lower() in key_path.lower():
                _op = "写入" if operation == "write" else "删除"
                warnings.append(f"{_op}关键注册表键: {pattern}，请确认")
                break
    
    warning_msg = "；".join(warnings) if warnings else None
    return True, None, warning_msg


def validate_delete_safety(key_path: str, value_name: Optional[str], 
                           hive: str, recursive: bool) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    注册表删除操作的安全检查（适用于registry_delete）
    
    额外检查：
    1. 删除整个键（无value_name）且没传recursive → ERROR（必须确认）
    2. 删除HKLM键且无value_name → WARNING
    
    Returns: (is_valid, error_msg, warning_msg)
    """
    # 先执行基础检查
    is_valid, error_msg, warning_msg = validate_registry_key(
        key_path, hive, operation="delete"
    )
    if not is_valid:
        return is_valid, error_msg, warning_msg
    
    hive_upper = hive.upper() if hive else "HKCU"
    
    # 删除整个键（无value_name）且未指定recursive
    if value_name is None and not recursive:
        return False, "删除整个注册表键必须指定recursive=True", None
    
    # 删除HKLM整个键
    if hive_upper == "HKLM" and not value_name:
        return True, None, "删除HKLM下的整个键，请确认"
    
    return True, None, warning_msg
```

### 15.5 工具集成对照表

| 工具 | 调用的检查函数 | 检查位置 |
|------|--------------|---------|
| registry_read | `validate_registry_key(key_path, hive, "read")` | `_execute()` 第一行 |
| registry_write | `validate_registry_key(key_path, hive, "write")` | `_execute()` 第一行 |
| registry_delete | `validate_delete_safety(key_path, value_name, hive, recursive)` | `_execute()` 第一行 |

### 15.6 实施步骤

1. 新建 `backend/app/tools/validate/registry_path_checker.py`
2. 修改 registry_read、registry_write、registry_delete 的 `_execute()` 入口
3. `registry_delete` 使用 `validate_delete_safety`（含增强检查），其余两个使用 `validate_registry_key`
4. 编写单元测试（覆盖：空路径、hive非法、路径穿越、关键键警告、HKLM警告、删除保护）

### 15.7 注意事项

- **`validate_delete_safety` 是 `validate_registry_key` 的包装**：先执行基础检查，再增加删除特有的检查
- **registry_read 也做路径检查**：虽然"只读无风险"，但统一检查有以下好处：
  - 防止读取系统路径时误读敏感信息（如SAM文件虽受系统保护，但其他HKLM键可读）
  - 保持3个工具的安全行为一致，不因"只读"而忽略防御
- **CRITICAL_KEY_PATTERNS 使用子串匹配**：可以检测包含关键路径的所有子键

---

## 附：三类参数统一检查方案对比

| 维度 | file_path（已有） | URL（新增） | timeout（新增） | registry key_path（新增） |
|------|-----------------|------------|----------------|--------------------------|
| 代码文件 | `validate/file_path_checker.py` | `validate/url_validator.py` | `validate/timeout_validator.py` | `validate/registry_path_checker.py` |
| 涉及工具 | 13个 | 4个 | 6个 | 3个 |
| 风险等级 | 🔴 数据丢失 | 🔴 SSRF | 🟡 LLM混淆 | 🟢 需管理员权限 |
| 验证粒度 | WARNING级阻断 | 阻断+WARNING | 阻断（范围外） | 阻断+WARNING |
| 工作量估计 | ~160行 + 13个入口 | ~120行 + 4个入口 | ~80行 + 6个入口 | ~80行 + 3个入口 |
| **推荐优先级** | **1（已有方案）** | **2** | **3** | **4** |

---

**文档创建时间**: 2026-06-27（v3：并入path_validator分层 + 新增URL/timeout/registry三类参数统一检查方案）
**编写人**: 小沈 2026-06-27 10:56:50
