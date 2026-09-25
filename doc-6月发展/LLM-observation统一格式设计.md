# LLM Observation 统一输出格式设计

**创建时间**: 2026-06-20 10:50:29  
**更新时间**: 2026-06-20 11:15:00  
**版本**: v0.2  
**编写人**: 北京老陈 + 小健  
**适用范围**: OmniAgentAs-desk 所有工具给LLM的observation输出格式

---

## 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v0.1 | 2026-06-20 10:50:29 | 初始设计，定义三层输出格式 | 北京老陈 + 小健 |
| v0.2 | 2026-06-20 11:15:00 | 简化设计：删除llm_data，message承载关键信息，data格式化输出 | 北京老陈 + 小健 |

---

## 一、问题现状

### 1.1 当前各工具data格式混乱

每个工具返回的data结构完全不同：

| 工具 | data结构 | LLM看到的 |
|------|---------|----------|
| read_text_file | `{"operation_id":"xxx","file_path":"C:\\test.py","bytes_read":2380,"content":"..."}` | 要从5个字段里找content |
| query_sql | `{"sql":"SELECT...","affected_rows":5,"columns":["id","name"],"rows":[...]}` | 要从4个字段里找rows |
| get_system_info | `{"cpu":{"brand":"Intel","cores":12},"memory":{"total_gb":16}}` | 要解析嵌套JSON |
| get_db_schema | `{"tables":[...],"total":3,"markdown":"## 数据库结构..."}` | 要从3个字段里找markdown |
| list_files | `{"entries":[...],"total":156,"directory":"C:\\","truncated":false}` | 要从3个字段里找entries |

### 1.2 核心问题

1. **格式不统一** — 每个工具自己决定data结构，LLM每次都要重新解析
2. **信息密度低** — 原始JSON dump，LLM要自己从一堆字段里找有用信息
3. **重复冗余** — llm_data和data有重复字段（如file_path出现两次）
4. **message太短** — "读取文件成功"没有告诉LLM关键信息（几行、多大）

---

## 二、设计目标

### 2.1 核心原则

1. **每看全懂** — LLM看到observation就能准确理解工具执行结果
2. **格式统一** — 所有工具用同一种格式输出，LLM不用猜
3. **信息完整** — 关键事实都在，不丢失重要信息
4. **简洁高效** — 不废话，不冗余，token占用最小

### 2.2 设计约束

- 不修改工具的功能逻辑
- 只修改 `observation_formatter.py` 的输出格式
- 工具侧调整 `message` 和 `data` 的内容

---

## 三、字段重新定义

### 3.1 旧字段 → 新字段

| 旧字段 | 新字段 | 作用 |
|--------|--------|------|
| `message`（旧） | **删除** | 旧message只写"执行成功"，没信息量 |
| `llm_data` | **变成新 `message`** | 自然语言+关键信息，让LLM快速理解 |
| `data` | **格式化后输出** | 不是JSON dump，而是人能读懂的格式 |

### 3.2 新字段定义

| 字段 | 作用 | 示例 |
|------|------|------|
| `message` | 自然语言描述结果，包含关键数字 | `"读取 C:\test.py，156行，2380字节，UTF-8编码"` |
| `data` | 结构化数据，格式化为可读文本 | 文件内容、查询结果、系统信息等 |

### 3.3 为什么删除 llm_data

- `llm_data` 和 `message` 本质是同一件事：描述结果
- 合并成一个 `message`，减少冗余
- `message` 直接包含关键信息，不需要额外的摘要层

---

## 四、统一输出格式

### 4.1 格式定义

**所有工具的observation统一使用两层结构**：

```
观察: {status} - {action}
结果: {message}
详情:
{格式化的data}
```

### 4.2 两层说明

| 层级 | 来源 | 作用 |
|------|------|------|
| **结果** | `message`字段 | 自然语言描述，包含关键数字，LLM快速理解 |
| **详情** | `data`字段 | 格式化后的数据，LLM需要时引用 |

---

## 五、各工具类型格式规范

### 5.1 文件操作工具

**read_text_file 成功**：
```
观察: success - read_file
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情:
def hello():
    print('hi')
    return True
...
```

**write_text_file 成功**：
```
观察: success - write_file
结果: 写入 C:\output.txt，1024字节，UTF-8编码
详情:
写入成功，文件已更新
```

**copy_file 成功**：
```
观察: success - copy_file
结果: 复制 C:\a.txt → C:\b.txt，1024字节
详情:
复制完成
```

**list_files 成功**：
```
观察: success - list_files
结果: 列出 C:\project\，156个文件/目录
详情:
  src/ [目录]
  README.md [文件, 2048字节]
  package.json [文件, 1024字节]
  ...
```

### 5.2 数据库工具

**query_sql SELECT 成功**：
```
观察: success - query_sql
结果: 查询返回5行，列: id, name, email
详情:
id=1 | name=Alice | email=alice@test.com
id=2 | name=Bob | email=bob@test.com
id=3 | name=Charlie | email=charlie@test.com
id=4 | name=Dave | email=dave@test.com
id=5 | name=Eve | email=eve@test.com
```

**execute_sql DML 成功**：
```
观察: success - execute_sql
结果: SQL执行成功，影响5行
详情:
影响行数: 5
```

**get_db_schema 成功**：
```
观察: success - get_db_schema
结果: 获取到3个表的结构: users, orders, products
详情:
## users
|字段名|类型|可空|主键|
|id|INTEGER|否|是|
|name|TEXT|否|否|
|email|TEXT|否|否|

## orders
|字段名|类型|可空|主键|
|id|INTEGER|否|是|
|user_id|INTEGER|否|否|
|amount|REAL|否|否|
```

### 5.3 系统工具

**get_system_info 成功**：
```
观察: success - get_system_info
结果: 获取系统信息成功
详情:
CPU: Intel i7-12700K, 12核24线程
内存: 16GB DDR4, 已用8GB (50%)
磁盘: C: 500GB, 已用300GB (60%)
```

**event_log 成功**：
```
观察: success - event_log
结果: 获取事件日志，10条记录
详情:
  [1] 2026-06-20 10:30:00 | Error | Application Error
  [2] 2026-06-20 10:25:00 | Warning | .NET Runtime
  ...
```

### 5.4 桌面工具

**set_window_state 成功**：
```
观察: success - set_window_state
结果: 窗口最大化完成，匹配2个窗口
详情:
窗口标题: Chrome
操作: maximize
匹配数量: 2
```

**screen_record 成功**：
```
观察: success - screen_record
结果: 屏幕录制完成，保存到 C:\record.gif，10秒，15fps
详情:
输出路径: C:\record.gif
时长: 10秒
帧率: 15fps
```

### 5.5 网络工具

**fetch_webpage 成功**：
```
观察: success - fetch_webpage
结果: 获取网页成功，15000字符
详情:
<!DOCTYPE html>
<html>
<head><title>Example</title></head>
<body>...</body>
</html>
```

**download_file 成功**：
```
观察: success - download_file
结果: 下载完成，102400字节，保存到 C:\download\file.zip
详情:
文件路径: C:\download\file.zip
文件大小: 102400字节
```

### 5.6 Shell工具

**run_shell 成功**：
```
观察: success - run_shell
结果: 命令执行成功，退出码0
详情:
 Volume in drive C is Windows
 Directory of C:\
2026-06-20  10:00    <DIR>          Users
2026-06-20  10:00    <DIR>          Windows
...
```

**shell_session terminate 成功**：
```
观察: success - shell_session_terminate
结果: 会话 abc123 已终止，退出码0
详情:
会话ID: abc123
已终止: true
退出码: 0
```

### 5.7 注册表工具

**registry_read 成功**：
```
观察: success - registry_read
结果: 读取注册表值成功
详情:
键路径: HKCU\Software\MyApp
值名称: LastLogin
值类型: REG_SZ
值: 2026-06-20
```

**registry_write 成功**：
```
观察: success - registry_write
结果: 写入注册表值成功
详情:
键路径: HKCU\Software\MyApp
值名称: LastLogin
值: 2026-06-20
值类型: REG_SZ
```

### 5.8 定时器工具

**timer_set 成功**：
```
观察: success - timer_set
结果: 定时器设置成功，30秒后触发
详情:
定时器ID: timer_001
延迟: 30秒
触发时间: 2026-06-20 10:51:00
回调: on_timer_complete
```

**timer_clear 成功**：
```
观察: success - timer_clear
结果: 定时器 timer_001 已取消
详情:
定时器ID: timer_001
已取消: true
```

---

## 六、错误格式规范

### 6.1 错误输出格式

```
观察: error [{错误码}] - {错误描述}
结果: {人可读的错误原因}
详情:
{错误详情}
建议: {下一步操作}
```

### 6.2 错误示例

**文件不存在**：
```
观察: error [ERR_FILE_NOT_FOUND] - 文件不存在
结果: 文件 C:\notexist.txt 不存在
详情:
文件路径: C:\notexist.txt
建议: 请检查路径是否正确
```

**SQL执行失败**：
```
观察: error [ERR_SQL_EXEC] - SQL执行错误
结果: near "SELCT": syntax error
详情:
SQL: SELCT * FROM users
错误: near "SELCT": syntax error
建议: 请检查SQL语法
```

**依赖库未安装**：
```
观察: error [ERR_NO_PYAUTOGUI] - 依赖库未安装
结果: 需要安装 pyautogui 库
详情:
库名: pyautogui
安装命令: pip install pyautogui
建议: 请先执行安装命令
```

---

## 七、警告格式规范

### 7.1 警告输出格式

```
观察: warning [{警告码}] - {警告描述}
结果: {人可读的警告原因}
⚠ 警告: {具体警告内容}
详情:
{部分数据}
建议: {下一步操作}
```

### 7.2 警告示例

**数据量过大回滚**：
```
观察: warning [WARNING_DB_SAFETY] - 影响行数过大
结果: 影响行数 50000 > 10000，已自动回滚
⚠ 警告: 操作影响行数超过安全阈值，已自动回滚
详情:
影响行数: 50000
操作: rollback
建议: 请使用 WHERE 子句缩小影响范围
```

---

## 八、实现方案

### 8.1 修改范围

| 文件 | 修改内容 | 工作量 |
|------|---------|--------|
| `observation_formatter.py` | 重构输出格式：message+格式化data | 中 |
| 各 `*_tools.py` | 调整 `message` 内容，包含关键信息 | 小 |
| 各 `*_tools.py` | 调整 `data` 结构，格式化为可读文本 | 中 |
| 删除 `llm_data` | 从所有工具和formatter中移除 | 小 |

### 8.2 实现原则

1. **工具侧**：`message` 包含关键信息，`data` 格式化为可读文本
2. **格式化层**：按固定格式组装 `观察 + 结果 + 详情`
3. **不改功能逻辑**：只改输出格式

### 8.3 message 标准

**每个工具的 message 必须包含**：
- 操作类型（读取/写入/查询/...）
- 关键对象（文件路径/表名/命令/...）
- 关键数字（行数/字节数/影响行数/...）

```python
# 旧 message（没信息量）
message = "执行成功"
message = "读取文件成功"

# 新 message（包含关键信息）
message = "读取 C:\test.py，156行，2380字节，UTF-8编码"
message = "查询返回5行，列: id, name, email"
message = "SQL执行成功，影响5行"
```

### 8.4 data 标准

**每个工具的 data 必须格式化为可读文本**：

```python
# 旧 data（JSON dump）
data = {"operation_id":"abc","file_path":"C:\\test.py","bytes_read":2380,"content":"def hello():..."}

# 新 data（格式化文本）
data = "文件内容:\ndef hello():\n    print('hi')\n    return True\n..."
```

---

## 九、LLM对比效果

### 9.1 旧格式（当前）

```
Observation: success - 读取文件成功
【摘要】 action=read_file | file_path=C:\test.py | bytes_read=2380
【数据】 {"operation_id":"abc123","file_path":"C:\\test.py","bytes_read":2380,"encoding":"utf-8","line_count":156,"lines_read":156,"truncated":false,"content":"def hello():\n    print('hi')\n..."}
```

**LLM需要**：
1. 解析JSON找到 `line_count` → 156行
2. 解析JSON找到 `bytes_read` → 2380字节
3. 解析JSON找到 `content` → 文件内容
4. 跳过 `operation_id`、`truncated` 等无用字段

### 9.2 新格式（设计）

```
观察: success - read_file
结果: 读取 C:\test.py，156行，2380字节，UTF-8编码
详情:
def hello():
    print('hi')
    return True
...
```

**LLM直接看到**：
1. 第一行：成功读取了文件
2. 第二行：156行，2380字节
3. 第三行起：文件内容

**不需要解析任何JSON**。

---

## 十、执行计划

### 10.1 第一步：重构 observation_formatter.py

修改输出格式：`观察 + 结果(message) + 详情(格式化data)`

### 10.2 第二步：逐工具调整 message

按工具类型，逐个调整 `message` 的内容，包含关键信息。

### 10.3 第三步：逐工具格式化 data

按工具类型，逐个调整 `data` 的格式，从JSON dump改为可读文本。

### 10.4 第四步：删除 llm_data

从所有工具和formatter中移除 `llm_data` 字段。

### 10.5 第五步：测试验证

运行全部测试，确保格式正确、信息完整。

---

## 十一、总结

### 11.1 核心设计

```
观察: {status} - {action}     ← 发生了什么
结果: {message}               ← 关键信息（含数字）
详情:
{格式化的data}                ← 需要时查看
```

### 11.2 设计优势

| 优势 | 说明 |
|------|------|
| **每看全懂** | LLM不用解析JSON，直接读自然语言 |
| **格式统一** | 所有工具同一种格式，不用猜 |
| **信息完整** | 关键数字都在，不丢失信息 |
| **简洁高效** | 没有冗余字段，token占用最小 |
| **易于维护** | 工具只管提供message和data，格式化层统一输出 |

---

**文档更新时间**: 2026-06-20 11:15:00  
**版本**: v0.2  
**编写人**: 北京老陈 + 小健
