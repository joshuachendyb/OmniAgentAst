# 日常场景与 Function Call 对应关系分析

**创建时间**: 2026-04-05 07:30:00  
**编写人**: 小沈  
**版本**: v2.1  
**更新时间**: 2026-04-05 08:45:00  
**更新说明**: 重写15个核心场景，增加条件分支、错误处理、完整调用链；每个场景末尾增加工具编号对照表  
**存放位置**: D:\OmniAgentAs-desk\doc-functioncall

---

## 一、核心概念

本文档分析**普通用户的日常场景**与**Function Call（工具调用）**之间的对应关系。

用户说的是**日常用语（人话）**，系统执行的是**工具调用序列（机器指令）**。中间通过**意图翻译（Intent Translation）**机制进行转换。

---

## 二、从日常场景到 Function Call 的转换逻辑

```
【用户日常场景】：日常用语（非结构化）
      ↓
【意图翻译层】（中间处理机制）：
  1. 意图识别（用户想干嘛？）
  2. 步骤拆解（需要分几步做？）
  3. 参数提取（从话里抠出关键信息）
  4. 条件判断（是否有分支逻辑？）
  5. 异常处理（如果失败怎么办？）
      ↓
【Function Call 层】：生成执行计划（Plan）
  Step 1: 前置检查 → Tool A(参数)
  Step 2: 条件分支 → if/else 判断
  Step 3: 核心执行 → Tool B(参数)
  Step 4: 后置验证 → Tool C(参数)
  Step 5: 结果通知 → Tool D(参数)
```

---

## 三、典型日常场景与 Function Call 对应关系

> **说明**：本文档选取 15 个最典型的日常场景进行分析，每个场景展示**完整的、可执行的** Function Call 调用链，包含前置检查、条件分支、错误处理、后置验证和结果通知。每个场景末尾附工具编号对照表，标注每个工具在《Omni 系统工具定义说明书》中的编号和定义状态。

---

### 场景 1：找文件（跨类别组合，完整调用链）

*   **用户日常场景**："帮我找下上周下载的那个合同"
*   **意图翻译**：
    1.  **意图**：搜索文件，确认内容，通知用户结果。
    2.  **拆解**：获取当前时间 → 计算上周时间范围 → 搜索 Downloads 目录 → 按时间过滤 → 逐个确认内容 → 找到则通知用户，未找到则扩大搜索范围。
    3.  **参数**：目录=`Downloads`，关键词=`合同`，时间=`上周`。
    4.  **条件分支**：找到 0 个文件 → 扩大搜索到全磁盘；找到 1 个 → 直接确认；找到多个 → 逐个确认内容。
    5.  **异常处理**：搜索失败 → 检查目录是否存在；读取失败 → 跳过该文件继续。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `get_current_time()` → **【Tool 26】**获取当前时间，计算"上周"的起止日期
    2.  `check_path_exists(path="Downloads")` → **【Tool 36】**检查 Downloads 目录是否存在
        *   **if 不存在**: `execute_shell_command(command='echo "Downloads 目录不存在"')` → **【Tool 20】**通知用户目录不存在，结束
    3.  `search_files(search_dir="Downloads", pattern="*合同*")` → **【Tool 12】**搜索包含"合同"的文件
    4.  *(LLM 内部处理：判断搜索结果数量)*
        *   **if 找到 0 个文件**:
            5.  `search_files(search_dir="C:/", pattern="*合同*")` → **【Tool 12】**扩大搜索到全磁盘
            6.  *(LLM 内部处理：再次判断)*
                *   **if 仍然 0 个**: `send_notification(title="未找到文件", message="在整个电脑中未找到包含'合同'的文件，请确认文件名是否正确")` → **【Tool 107】**结束
    5.  `get_file_info(file_path="找到的文件 1")` → **【Tool 18】**获取文件修改时间
    6.  *(LLM 内部处理：判断文件修改时间是否在"上周"范围内)*
        *   **if 不在范围内**: 跳过该文件，处理下一个
    7.  `read_text_file(file_path="确认的文件")` → **【Tool 1】**读取文件内容确认是合同
        *   **if 读取失败（二进制文件）**: `get_file_info(file_path="确认的文件")` → **【Tool 18】**获取文件大小和类型，跳过内容确认
    8.  *(LLM 内部处理：确认内容包含合同相关关键词)*
    9.  `send_notification(title="找到文件", message="已找到上周下载的合同：xxx.pdf（修改时间：2026-03-29，大小：2.3MB）")` → **【Tool 107】**通知用户结果
    10. `get_file_info(file_path="确认的文件")` → **【Tool 18】**再次获取文件信息，准备后续操作
    11. *(LLM 内部处理：询问用户是否需要打开/复制/移动该文件)*

#### 场景 1 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `get_current_time` | Tool 26 | ✅ 已定义 | 5 类：时间/日期 |
| 2 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 3 | `execute_shell_command` | Tool 20 | ✅ 已定义 | 2 类：Shell 命令 |
| 4 | `search_files` | Tool 12 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `get_file_info` | Tool 18 | ✅ 已定义 | 1 类：文件操作 |
| 6 | `read_text_file` | Tool 1 | ✅ 已定义 | 1 类：文件操作 |
| 7 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 1 统计**：共 7 个不同工具，全部已定义 ✅

---

### 场景 2：改内容（跨类别组合，完整调用链）

*   **用户日常场景**："把这个文档里的旧地址改成新地址"
*   **意图翻译**：
    1.  **意图**：修改文件内容，确保安全（备份），验证修改结果。
    2.  **拆解**：检查文件 → 备份原文件 → 读取内容 → 查找旧内容 → 替换 → 验证修改 → 通知用户。
    3.  **参数**：文件=`当前文档`，旧内容=`旧地址`，新内容=`新地址`。
    4.  **条件分支**：旧内容不存在 → 提示用户；替换失败 → 恢复备份。
    5.  **异常处理**：文件只读 → 提示用户；替换后验证失败 → 恢复备份。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `check_path_exists(path="当前文档")` → **【Tool 36】**检查文件是否存在
        *   **if 不存在**: `send_notification(title="文件不存在", message="找不到指定的文档，请确认文件路径")` → **【Tool 107】**结束
    2.  `get_file_info(file_path="当前文档")` → **【Tool 18】**获取文件信息（大小、权限、类型）
        *   **if 文件为只读**: `send_notification(title="文件只读", message="该文档为只读状态，无法修改")` → **【Tool 107】**结束
    3.  `backup_file(file_path="当前文档")` → **【Tool 42】**修改前自动备份
    4.  `read_text_file(file_path="当前文档")` → **【Tool 1】**读取文件全文内容
    5.  *(LLM 内部处理：检查旧内容是否存在于文件中)*
        *   **if 未找到旧内容**:
            6.  `send_notification(title="未找到旧内容", message="在文档中未找到'旧地址'，请确认内容是否正确")` → **【Tool 107】**结束
    6.  `precise_replace_in_file(file_path="当前文档", old_string="旧地址", new_string="新地址")` → **【Tool 6】**精确替换内容
    7.  `read_text_file(file_path="当前文档")` → **【Tool 1】**重新读取文件，验证修改结果
    8.  *(LLM 内部处理：验证新内容已存在，旧内容已不存在)*
        *   **if 验证失败**:
            9.  `restore_backup(file_path="当前文档")` → **【❌ 未定义，需新增】**从备份恢复文件（可用 `copy_file` Tool 8 替代实现）
            10. `send_notification(title="修改失败", message="内容替换后验证失败，已恢复原文件")` → **【Tool 107】**结束
    9.  `get_file_info(file_path="当前文档")` → **【Tool 18】**获取修改后文件大小，确认有变化
    10. `send_notification(title="修改完成", message="已将文档中的'旧地址'改为'新地址'，共替换 X 处。原文件已备份。")` → **【Tool 107】**通知用户结果

#### 场景 2 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 2 | `get_file_info` | Tool 18 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `backup_file` | Tool 42 | ✅ 已定义 | 附录：配套保障 |
| 4 | `read_text_file` | Tool 1 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `precise_replace_in_file` | Tool 6 | ✅ 已定义 | 1 类：文件操作 |
| 6 | `restore_backup` | ❌ 未定义 | ⚠️ 需新增 | 附录：配套保障 |
| 7 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 2 统计**：共 7 个不同工具，6 个已定义 ✅，1 个未定义 ⚠️（`restore_backup`，建议新增或用 `copy_file` 替代）

---

### 场景 3：整理文件（跨类别组合，完整调用链）

*   **用户日常场景**："帮我把桌面上的照片整理到一个文件夹里"
*   **意图翻译**：
    1.  **意图**：识别照片文件，创建目标文件夹，移动照片，通知结果。
    2.  **拆解**：查看桌面 → 识别照片（jpg/png/gif）→ 创建日期命名文件夹 → 逐个移动 → 验证移动结果 → 通知用户。
    3.  **参数**：源=`Desktop`，目标=`照片整理_日期`，类型=`jpg/png/gif`。
    4.  **条件分支**：桌面没有照片 → 提示用户；目标文件夹已存在 → 直接使用。
    5.  **异常处理**：移动失败（文件被占用）→ 跳过并记录；权限不足 → 提示用户。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `list_directory(dir_path="Desktop")` → **【Tool 19】**查看桌面所有文件
    2.  *(LLM 内部处理：筛选出照片文件：.jpg, .jpeg, .png, .gif, .bmp)*
        *   **if 没有照片文件**: `send_notification(title="未找到照片", message="桌面上没有找到照片文件")` → **【Tool 107】**结束
    3.  `get_current_time(format="YYYYMMDD")` → **【Tool 26】**获取当前日期用于命名
    4.  `check_path_exists(path="Desktop/照片整理_20260405")` → **【Tool 36】**检查目标文件夹是否已存在
        *   **if 不存在**: `create_directory(dir_path="Desktop/照片整理_20260405")` → **【Tool 15】**创建文件夹
    5.  `get_file_info(file_path="Desktop/照片1.jpg")` → **【Tool 18】**获取第一张照片信息
    6.  `move_file(source="Desktop/照片1.jpg", destination="Desktop/照片整理_20260405/照片1.jpg")` → **【Tool 9】**移动第一张照片
        *   **if 移动失败**: 记录失败文件，继续处理下一张
    7.  *(循环执行步骤 5-6，处理所有照片)*
    8.  `list_directory(dir_path="Desktop/照片整理_20260405")` → **【Tool 19】**验证目标文件夹内容
    9.  *(LLM 内部处理：对比移动前后文件数量，确认全部移动成功)*
    10. `send_notification(title="整理完成", message="已将桌面 X 张照片整理到'照片整理_20260405'文件夹。失败 Y 张（文件被占用）。")` → **【Tool 107】**通知用户结果

#### 场景 3 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `list_directory` | Tool 19 | ✅ 已定义 | 1 类：文件操作 |
| 2 | `get_current_time` | Tool 26 | ✅ 已定义 | 5 类：时间/日期 |
| 3 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 4 | `create_directory` | Tool 15 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `get_file_info` | Tool 18 | ✅ 已定义 | 1 类：文件操作 |
| 6 | `move_file` | Tool 9 | ✅ 已定义 | 1 类：文件操作 |
| 7 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 3 统计**：共 7 个不同工具，全部已定义 ✅

---

### 场景 4：看文档（跨类别组合，完整调用链）

*   **用户日常场景**："帮我看看这个 PDF 合同写了什么，重点看金额"
*   **意图翻译**：
    1.  **意图**：读取 PDF 内容，提取关键信息（金额），生成摘要，保存并通知用户。
    2.  **拆解**：检查文件 → 读取 PDF → 提取文本 → LLM 分析提取金额 → 保存摘要 → 通知用户。
    3.  **参数**：文件=`合同.pdf`，关注点=`金额`。
    4.  **条件分支**：PDF 加密 → 提示用户需要密码；PDF 为扫描件 → 尝试 OCR。
    5.  **异常处理**：文件损坏 → 提示用户；提取失败 → 尝试其他方式。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `check_path_exists(path="合同.pdf")` → **【Tool 36】**检查文件是否存在
        *   **if 不存在**: `send_notification(title="文件不存在", message="找不到指定的 PDF 文件")` → **【Tool 107】**结束
    2.  `get_file_info(file_path="合同.pdf")` → **【Tool 18】**获取文件大小，确认不是空文件
        *   **if 文件大小为 0**: `send_notification(title="文件为空", message="该 PDF 文件大小为 0，无法读取")` → **【Tool 107】**结束
    3.  `read_pdf(file_path="合同.pdf")` → **【Tool 80】**读取 PDF 文本内容
        *   **if 读取失败（加密）**: `send_notification(title="PDF 加密", message="该 PDF 文件已加密，需要提供密码才能读取")` → **【Tool 107】**结束
        *   **if 读取失败（扫描件）**: `send_notification(title="扫描件", message="该 PDF 为扫描图片，无法直接提取文字，需要 OCR 处理")` → **【Tool 107】**结束
    4.  *(LLM 内部处理：分析文本，提取金额、日期、签约方等关键信息)*
    5.  `get_current_time()` → **【Tool 26】**获取当前时间，用于摘要文件名
    6.  `write_append_file(file_path="合同摘要_20260405.txt", text="合同金额：XXX 元\n签约方：XXX\n日期：XXX", append=false)` → **【Tool 5】**保存摘要到文件
    7.  `check_path_exists(path="合同摘要_20260405.txt")` → **【Tool 36】**验证摘要文件已创建
    8.  `send_notification(title="文档分析完成", message="合同金额：XXX 元\n签约方：XXX\n签约日期：XXX\n详细摘要已保存到'合同摘要_20260405.txt'")` → **【Tool 107】**通知用户结果

#### 场景 4 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 2 | `get_file_info` | Tool 18 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `read_pdf` | Tool 80 | ✅ 已定义 | 21 类：文档处理 |
| 4 | `get_current_time` | Tool 26 | ✅ 已定义 | 5 类：时间/日期 |
| 5 | `write_append_file` | Tool 5 | ✅ 已定义 | 1 类：文件操作 |
| 6 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 4 统计**：共 6 个不同工具，全部已定义 ✅

---

### 场景 5：查信息（跨类别组合，完整调用链）

*   **用户日常场景**："现在几点了？30 天后是几号？那天是星期几？"
*   **意图翻译**：
    1.  **意图**：获取当前时间，计算偏移日期，查询星期几，通知用户。
    2.  **拆解**：查当前时间 → 算 30 天后日期 → 算星期几 → 通知用户。
    3.  **参数**：偏移=`+30 天`。
    4.  **条件分支**：无。
    5.  **异常处理**：无。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `get_current_time(format="YYYY-MM-DD HH:mm:ss")` → **【Tool 26】**获取当前精确时间
    2.  `get_current_time(format="YYYY-MM-DD")` → **【Tool 26】**获取当前日期
    3.  `calculate_date(date="2026-04-05", days=30)` → **【Tool 27】**计算 30 天后的日期
    4.  `calculate_date(date="2026-04-05", days=30, format="weekday")` → **【Tool 27】**计算那天是星期几
    5.  `send_notification(title="时间查询", message="现在时间：2026-04-05 14:30:00\n30 天后：2026-05-05（星期二）")` → **【Tool 107】**通知用户结果

#### 场景 5 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `get_current_time` | Tool 26 | ✅ 已定义 | 5 类：时间/日期 |
| 2 | `calculate_date` | Tool 27 | ✅ 已定义 | 5 类：时间/日期 |
| 3 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 5 统计**：共 3 个不同工具，全部已定义 ✅

---

### 场景 6：网络诊断（跨类别组合，完整调用链）

*   **用户日常场景**："帮我看看网络通不通，能不能上百度"
*   **意图翻译**：
    1.  **意图**：测试网络连通性，如果异常则进一步诊断，通知用户结果。
    2.  **拆解**：Ping 百度 → 判断结果 → 正常则通知；异常则执行 DNS 测试、IP 配置检查 → 汇总诊断结果 → 通知用户。
    3.  **参数**：目标=`www.baidu.com`。
    4.  **条件分支**：Ping 成功 → 直接通知；Ping 失败 → 深入诊断（DNS、IP 配置、网关）。
    5.  **异常处理**：命令执行失败 → 记录错误信息。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `ping(host="www.baidu.com", count=4)` → **【Tool 66】**测试百度连通性
    2.  *(LLM 内部处理：判断 Ping 结果)*
        *   **if Ping 成功（丢包率 0%）**:
            3.  `send_notification(title="网络诊断", message="网络连通性正常\n目标：www.baidu.com\n延迟：XX ms\n丢包率：0%")` → **【Tool 107】**通知用户，结束
        *   **if Ping 失败（丢包率 100%）**:
            3.  `ping(host="8.8.8.8", count=4)` → **【Tool 66】**测试 DNS 服务器连通性（判断是 DNS 问题还是网络问题）
            4.  *(LLM 内部处理：判断 8.8.8.8 的 Ping 结果)*
                *   **if 8.8.8.8 通但百度不通**: `send_notification(title="DNS 问题", message="网络本身正常，但 DNS 解析可能有问题。建议：1. 刷新 DNS 缓存 2. 更换 DNS 服务器")` → **【Tool 107】**结束
                *   **if 8.8.8.8 也不通**:
                    5.  `execute_shell_command(command="ipconfig")` → **【Tool 20】**获取本机 IP 配置
                    6.  `execute_shell_command(command="ipconfig /all")` → **【Tool 20】**获取详细网络配置
                    7.  *(LLM 内部处理：分析 IP 配置，判断是否获取到有效 IP)*
                    8.  `send_notification(title="网络异常", message="网络不通，诊断结果：\n1. 无法连接外网\n2. 本机 IP：XXX\n3. 建议：检查网线/WiFi 连接，联系网络管理员")` → **【Tool 107】**通知用户诊断结果

#### 场景 6 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `ping` | Tool 66 | ✅ 已定义 | 18 类：网络诊断 |
| 2 | `execute_shell_command` | Tool 20 | ✅ 已定义 | 2 类：Shell 命令 |
| 3 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 6 统计**：共 3 个不同工具，全部已定义 ✅

---

### 场景 7：打包文件（跨类别组合，完整调用链）

*   **用户日常场景**："帮我把这些文件打包，我要发邮件"
*   **意图翻译**：
    1.  **意图**：将多个文件压缩为 zip 包，验证压缩包完整性，通知用户。
    2.  **拆解**：检查源文件 → 检查输出目录 → 压缩 → 验证压缩包 → 获取大小 → 通知用户。
    3.  **参数**：源=`这些文件`，输出=`压缩包.zip`。
    4.  **条件分支**：源文件不存在 → 提示用户；输出文件已存在 → 询问是否覆盖。
    5.  **异常处理**：压缩失败 → 提示用户；压缩包验证失败 → 删除损坏文件。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `check_path_exists(path="文件 1")` → **【Tool 36】**检查第一个源文件
    2.  `check_path_exists(path="文件 2")` → **【Tool 36】**检查第二个源文件
        *   **if 任一文件不存在**: `send_notification(title="文件不存在", message="部分源文件不存在，请检查文件路径")` → **【Tool 107】**结束
    3.  `check_path_exists(path="压缩包.zip")` → **【Tool 36】**检查输出文件是否已存在
        *   **if 已存在**: `delete_file(file_path="压缩包.zip")` → **【Tool 11】**删除旧压缩包
    4.  `compress_archive(source_path="文件 1,文件 2", output_path="压缩包.zip", format="zip")` → **【Tool 33】**执行压缩
    5.  `check_path_exists(path="压缩包.zip")` → **【Tool 36】**验证压缩包已创建
        *   **if 不存在**: `send_notification(title="压缩失败", message="文件打包失败，请检查文件是否被占用")` → **【Tool 107】**结束
    6.  `get_file_info(file_path="压缩包.zip")` → **【Tool 18】**获取压缩包大小
    7.  `test_archive(file_path="压缩包.zip")` → **【❌ 未定义，需新增】**验证压缩包完整性（可用 `execute_shell_command` 执行 `tar -tzf` 或 `unzip -t` 替代）
        *   **if 验证失败**: `delete_file(file_path="压缩包.zip")` → **【Tool 11】**删除损坏的压缩包 → 通知用户重新打包
    8.  `send_notification(title="打包完成", message="文件已打包为'压缩包.zip'\n大小：XX MB\n包含文件：X 个\n压缩包已验证完整")` → **【Tool 107】**通知用户结果

#### 场景 7 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 2 | `delete_file` | Tool 11 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `compress_archive` | Tool 33 | ✅ 已定义 | 9 类：压缩/解压 |
| 4 | `get_file_info` | Tool 18 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `test_archive` | ❌ 未定义 | ⚠️ 需新增 | 9 类：压缩/解压 |
| 6 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 7 统计**：共 6 个不同工具，5 个已定义 ✅，1 个未定义 ⚠️（`test_archive`，建议新增或用 `execute_shell_command` 替代）

---

### 场景 8：Excel 数据分析（办公自动化类，跨类别组合，完整调用链）

*   **用户日常场景**："帮我看看这个 Excel 表里销售额最高的是哪个月"
*   **意图翻译**：
    1.  **意图**：读取 Excel 数据，分析销售额，找出最高月份，生成图表，保存结果。
    2.  **拆解**：检查文件 → 读取 Excel → 分析数据 → 生成图表 → 保存结果 → 通知用户。
    3.  **参数**：文件=`销售数据.xlsx`，关注列=`销售额`。
    4.  **条件分支**：文件不存在 → 提示；无销售额列 → 提示用户；数据为空 → 提示。
    5.  **异常处理**：文件格式错误 → 提示；分析失败 → 尝试其他方式。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `check_path_exists(path="销售数据.xlsx")` → **【Tool 36】**检查文件是否存在
        *   **if 不存在**: `send_notification(title="文件不存在", message="找不到'销售数据.xlsx'，请确认文件路径")` → **【Tool 107】**结束
    2.  `get_file_info(file_path="销售数据.xlsx")` → **【Tool 18】**获取文件大小
        *   **if 文件大小为 0**: `send_notification(title="文件为空", message="该 Excel 文件大小为 0")` → **【Tool 107】**结束
    3.  `read_xlsx(file_path="销售数据.xlsx", sheet_name="Sheet1")` → **【Tool 82】**读取 Excel 数据
    4.  *(LLM 内部处理：解析数据，找到"销售额"列，计算每月总和)*
        *   **if 无销售额列**: `send_notification(title="数据格式问题", message="Excel 中未找到'销售额'列，请确认列名")` → **【Tool 107】**结束
        *   **if 数据为空**: `send_notification(title="数据为空", message="Excel 中没有数据行")` → **【Tool 107】**结束
    5.  `read_csv_dataframe(file_path="销售数据.csv")` → **【Tool 77】**如已导出为 CSV，进行深度分析
    6.  *(LLM 内部处理：找出销售额最高的月份，计算具体数值)*
    7.  `generate_chart(data={"labels": ["1月", "2月", "3月", ...], "values": [100, 200, 150, ...]}, chart_type="bar", title="月度销售额对比")` → **【Tool 78】**生成柱状图
    8.  `write_append_file(file_path="销售分析结果.txt", text="销售额最高月份：X 月\n销售额：XXX 万元\n详细数据见图表", append=false)` → **【Tool 5】**保存分析结果
    9.  `send_notification(title="分析完成", message="销售额最高的是 X 月，销售额 XXX 万元\n图表和分析结果已保存")` → **【Tool 107】**通知用户结果

#### 场景 8 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 2 | `get_file_info` | Tool 18 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `read_xlsx` | Tool 82 | ✅ 已定义 | 21 类：文档处理 |
| 4 | `read_csv_dataframe` | Tool 77 | ✅ 已定义 | 20 类：数据分析 |
| 5 | `generate_chart` | Tool 78 | ✅ 已定义 | 20 类：数据分析 |
| 6 | `write_append_file` | Tool 5 | ✅ 已定义 | 1 类：文件操作 |
| 7 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 8 统计**：共 7 个不同工具，全部已定义 ✅

---

### 场景 9：批量重命名（办公自动化类，跨类别组合，完整调用链）

*   **用户日常场景**："帮我把这些照片按日期重命名"
*   **意图翻译**：
    1.  **意图**：获取照片创建日期，按"日期_序号"格式批量重命名，验证结果。
    2.  **拆解**：查看目录 → 获取每张照片创建时间 → 生成新文件名 → 逐个重命名 → 验证结果 → 通知用户。
    3.  **参数**：目录=`照片`，格式=`YYYYMMDD_序号`。
    4.  **条件分支**：目录为空 → 提示；文件名冲突 → 自动添加序号。
    5.  **异常处理**：重命名失败（文件被占用）→ 跳过并记录。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `list_directory(dir_path="照片")` → **【Tool 19】**查看目录中所有文件
    2.  *(LLM 内部处理：筛选出照片文件：.jpg, .jpeg, .png)*
        *   **if 没有照片**: `send_notification(title="未找到照片", message="该目录中没有照片文件")` → **【Tool 107】**结束
    3.  `get_file_info(file_path="照片/IMG001.jpg")` → **【Tool 18】**获取第一张照片的创建时间
    4.  *(LLM 内部处理：按创建时间排序，生成新文件名：20260405_001.jpg, 20260405_002.jpg...)*
    5.  `check_path_exists(path="照片/20260405_001.jpg")` → **【Tool 36】**检查新文件名是否已存在
        *   **if 已存在**: 自动添加序号避免冲突（如 20260405_001_1.jpg）
    6.  `rename_file(file_path="照片/IMG001.jpg", new_name="20260405_001.jpg")` → **【Tool 10】**重命名第一张
        *   **if 重命名失败**: 记录失败文件，继续处理下一张
    7.  *(循环执行步骤 3-6，处理所有照片)*
    8.  `list_directory(dir_path="照片")` → **【Tool 19】**验证重命名结果
    9.  `send_notification(title="重命名完成", message="已将 X 张照片按日期重命名\n格式：YYYYMMDD_序号\n失败：Y 张（文件被占用）")` → **【Tool 107】**通知用户结果

#### 场景 9 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `list_directory` | Tool 19 | ✅ 已定义 | 1 类：文件操作 |
| 2 | `get_file_info` | Tool 18 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 4 | `rename_file` | Tool 10 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 9 统计**：共 5 个不同工具，全部已定义 ✅

---

### 场景 10：清理磁盘（系统维护类，跨类别组合，完整调用链）

*   **用户日常场景**："帮我看看 C 盘哪些文件夹占的空间最大"
*   **意图翻译**：
    1.  **意图**：分析 C 盘空间使用情况，按大小排序，生成报告，通知用户。
    2.  **拆解**：获取磁盘总空间 → 查看一级目录大小 → 排序 → 深入分析大目录 → 生成报告 → 通知用户。
    3.  **参数**：目录=`C:/`。
    4.  **条件分支**：权限不足 → 跳过系统目录；目录过大 → 限制深度。
    5.  **异常处理**：访问被拒 → 记录并跳过。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `get_disk_usage(drive="C:")` → **【❌ 未定义，需新增】**获取 C 盘总空间和已用空间（可用 `execute_shell_command` 执行 `wmic logicaldisk` 替代）
    2.  `list_directory_with_sizes(dir_path="C:/", sortBy="size")` → **【Tool 16】**查看一级目录并按大小排序
    3.  *(LLM 内部处理：识别占用最大的前 5 个目录)*
    4.  `get_directory_tree(dir_path="C:/Users", max_depth=2, sortBy="size")` → **【Tool 17】**深入分析 Users 目录
    5.  `get_directory_tree(dir_path="C:/Program Files", max_depth=2, sortBy="size")` → **【Tool 17】**深入分析 Program Files 目录
    6.  `get_directory_tree(dir_path="C:/Windows", max_depth=1, sortBy="size")` → **【Tool 17】**查看 Windows 目录（仅一级，避免权限问题）
    7.  *(LLM 内部处理：汇总分析结果，生成空间使用报告)*
    8.  `write_append_file(file_path="C 盘空间分析报告.txt", text="C 盘总空间：XXX GB\n已用：XXX GB\n可用：XXX GB\n\n占用最大的文件夹：\n1. Users/XXX: XX GB\n2. Program Files/XXX: XX GB\n...", append=false)` → **【Tool 5】**保存分析报告
    9.  `send_notification(title="磁盘分析报告", message="C 盘总空间：XXX GB，已用 XX%\n\n占用最大的文件夹：\n1. Users/XXX: XX GB\n2. Program Files/XXX: XX GB\n\n详细报告已保存")` → **【Tool 107】**通知用户结果

#### 场景 10 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `get_disk_usage` | ❌ 未定义 | ⚠️ 需新增 | 7 类：系统信息 |
| 2 | `list_directory_with_sizes` | Tool 16 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `get_directory_tree` | Tool 17 | ✅ 已定义 | 1 类：文件操作 |
| 4 | `write_append_file` | Tool 5 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 10 统计**：共 5 个不同工具，4 个已定义 ✅，1 个未定义 ⚠️（`get_disk_usage`，建议新增或用 `execute_shell_command` 替代）

---

### 场景 11：搜索网络（信息获取类，跨类别组合，完整调用链）

*   **用户日常场景**："帮我搜一下今天有什么科技新闻"
*   **意图翻译**：
    1.  **意图**：搜索网络新闻，获取内容，总结摘要，通知用户。
    2.  **拆解**：搜索关键词 → 获取搜索结果 → 逐个获取网页内容 → 总结摘要 → 通知用户。
    3.  **参数**：关键词=`科技新闻`，时间=`今天`。
    4.  **条件分支**：搜索无结果 → 换关键词；网页无法访问 → 跳过。
    5.  **异常处理**：网络异常 → 提示用户；内容提取失败 → 跳过该网页。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `get_current_time(format="YYYY-MM-DD")` → **【Tool 26】**获取当前日期
    2.  `search_web(query="2026年4月5日 科技新闻")` → **【Tool 24】**搜索今日科技新闻
    3.  *(LLM 内部处理：分析搜索结果，选取前 3-5 个最相关的链接)*
    4.  `fetch_webpage(url="搜索结果 URL1")` → **【Tool 23】**获取第一个网页内容
        *   **if 获取失败**: 跳过，处理下一个链接
    5.  `fetch_webpage(url="搜索结果 URL2")` → **【Tool 23】**获取第二个网页内容
    6.  `fetch_webpage(url="搜索结果 URL3")` → **【Tool 23】**获取第三个网页内容
    7.  *(LLM 内部处理：提取各网页的新闻标题和摘要，去重，按重要性排序)*
    8.  `write_append_file(file_path="今日科技新闻摘要.txt", text="1. [标题1] 摘要...\n2. [标题2] 摘要...\n3. [标题3] 摘要...", append=false)` → **【Tool 5】**保存新闻摘要
    9.  `send_notification(title="今日科技新闻", message="为您找到以下科技新闻：\n1. [标题1]\n2. [标题2]\n3. [标题3]\n\n详细摘要已保存")` → **【Tool 107】**通知用户结果

#### 场景 11 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `get_current_time` | Tool 26 | ✅ 已定义 | 5 类：时间/日期 |
| 2 | `search_web` | Tool 24 | ✅ 已定义 | 4 类：网络通信 |
| 3 | `fetch_webpage` | Tool 23 | ✅ 已定义 | 4 类：网络通信 |
| 4 | `write_append_file` | Tool 5 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 11 统计**：共 5 个不同工具，全部已定义 ✅

---

### 场景 12：翻译内容（信息获取类，跨类别组合，完整调用链）

*   **用户日常场景**："帮我翻译这段英文，保存到文件里"
*   **意图翻译**：
    1.  **意图**：翻译文本，保存结果到文件，通知用户。
    2.  **拆解**：读取源文件 → 调用翻译 → 保存结果 → 验证 → 通知用户。
    3.  **参数**：文本=`Hello World`，目标语言=`中文`。
    4.  **条件分支**：源文件不存在 → 提示；翻译 API 失败 → 使用备用方式。
    5.  **异常处理**：网络异常 → 提示用户；保存失败 → 提示。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `check_path_exists(path="英文原文.txt")` → **【Tool 36】**检查源文件是否存在
        *   **if 不存在**: `send_notification(title="文件不存在", message="找不到'英文原文.txt'")` → **【Tool 107】**结束
    2.  `read_text_file(file_path="英文原文.txt")` → **【Tool 1】**读取英文原文
    3.  *(LLM 内部处理：调用翻译能力，将英文翻译为中文)*
    4.  `get_current_time(format="YYYYMMDD")` → **【Tool 26】**获取当前日期用于文件名
    5.  `write_append_file(file_path="中文翻译_20260405.txt", text="原文：Hello World\n翻译：你好世界", append=false)` → **【Tool 5】**保存翻译结果
    6.  `check_path_exists(path="中文翻译_20260405.txt")` → **【Tool 36】**验证翻译文件已创建
    7.  `send_notification(title="翻译完成", message="已将英文翻译为中文\n原文 X 字，译文 X 字\n结果已保存到'中文翻译_20260405.txt'")` → **【Tool 107】**通知用户结果

#### 场景 12 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `check_path_exists` | Tool 36 | ✅ 已定义 | 附录：配套保障 |
| 2 | `read_text_file` | Tool 1 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `get_current_time` | Tool 26 | ✅ 已定义 | 5 类：时间/日期 |
| 4 | `write_append_file` | Tool 5 | ✅ 已定义 | 1 类：文件操作 |
| 5 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 12 统计**：共 5 个不同工具，全部已定义 ✅

---

### 场景 13：查看系统信息（系统维护类，跨类别组合，完整调用链）

*   **用户日常场景**："我的电脑配置怎么样？内存够不够用？"
*   **意图翻译**：
    1.  **意图**：获取系统硬件信息，分析是否满足日常使用需求，给出建议。
    2.  **拆解**：获取系统信息 → 获取内存信息 → 获取磁盘信息 → 分析评估 → 生成报告 → 通知用户。
    3.  **参数**：无。
    4.  **条件分支**：无。
    5.  **异常处理**：信息获取失败 → 使用备用方法。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `get_system_info(info_type="cpu")` → **【Tool 30】**获取 CPU 信息
    2.  `get_system_info(info_type="memory")` → **【Tool 30】**获取内存信息
    3.  `get_system_info(info_type="disk")` → **【Tool 30】**获取磁盘信息
    4.  `get_system_info(info_type="os")` → **【Tool 30】**获取操作系统信息
    5.  `get_system_info(info_type="gpu")` → **【Tool 30】**获取显卡信息
    6.  *(LLM 内部处理：综合分析配置水平)*
        *   内存 < 8GB → "内存偏小，建议升级到 16GB"
        *   内存 8-16GB → "内存够用，日常办公足够"
        *   内存 > 16GB → "内存充足，可运行大型软件"
        *   磁盘剩余 < 10% → "磁盘空间紧张，建议清理"
    7.  `write_append_file(file_path="系统配置报告.txt", text="CPU: XXX\n内存：XX GB（评价：XXX）\n磁盘：XXX（剩余 XX%）\n显卡：XXX\n系统：XXX", append=false)` → **【Tool 5】**保存配置报告
    8.  `send_notification(title="系统配置分析", message="CPU: XXX\n内存：XX GB - 评价：XXX\n磁盘：XXX（剩余 XX%）\n显卡：XXX\n\n建议：XXX")` → **【Tool 107】**通知用户结果和建议

#### 场景 13 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `get_system_info` | Tool 30 | ✅ 已定义 | 7 类：系统信息 |
| 2 | `write_append_file` | Tool 5 | ✅ 已定义 | 1 类：文件操作 |
| 3 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 13 统计**：共 3 个不同工具，全部已定义 ✅

---

### 场景 14：查看进程（系统维护类，跨类别组合，完整调用链）

*   **用户日常场景**："帮我看看有哪些程序在后台运行，有没有占 CPU 特别高的"
*   **意图翻译**：
    1.  **意图**：查看进程列表，找出 CPU/内存占用高的进程，通知用户。
    2.  **拆解**：获取进程列表 → 按 CPU 排序 → 按内存排序 → 识别异常进程 → 通知用户。
    3.  **参数**：无。
    4.  **条件分支**：发现异常高占用进程 → 询问是否结束；无异常 → 直接报告。
    5.  **异常处理**：权限不足 → 跳过系统进程。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `list_processes(limit=20, sort_by="cpu")` → **【Tool 58】**获取 CPU 占用最高的 20 个进程
    2.  `list_processes(limit=20, sort_by="memory")` → **【Tool 58】**获取内存占用最高的 20 个进程
    3.  *(LLM 内部处理：分析进程列表，识别异常)*
        *   单进程 CPU > 50% → 标记为"异常高占用"
        *   单进程内存 > 4GB → 标记为"内存占用大"
        *   未知进程名 → 标记为"可疑进程"
    4.  *(LLM 内部处理：判断是否有异常进程)*
        *   **if 发现异常高占用进程**:
            5.  `send_notification(title="进程分析", message="发现异常进程：\n1. XXX.exe - CPU 占用 XX%\n2. XXX.exe - 内存占用 XX MB\n\n是否需要结束这些进程？")` → **【Tool 107】**通知用户并询问操作
        *   **if 无异常**:
            5.  `send_notification(title="进程分析", message="当前进程运行正常\nCPU 最高：XXX（XX%）\n内存最高：XXX（XX MB）\n无异常进程")` → **【Tool 107】**通知用户

#### 场景 14 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `list_processes` | Tool 58 | ✅ 已定义 | 15 类：进程管理 |
| 2 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 14 统计**：共 2 个不同工具，全部已定义 ✅

---

### 场景 15：查看服务（系统维护类，跨类别组合，完整调用链）

*   **用户日常场景**："帮我看看 MySQL 服务有没有在运行，没运行的话帮我启动"
*   **意图翻译**：
    1.  **意图**：检查服务状态，如未运行则启动，验证启动结果，通知用户。
    2.  **拆解**：检查服务状态 → 判断是否运行 → 未运行则启动 → 验证启动结果 → 通知用户。
    3.  **参数**：服务名=`MySQL`。
    4.  **条件分支**：服务已运行 → 直接通知；服务不存在 → 提示用户；启动失败 → 提示错误。
    5.  **异常处理**：权限不足 → 提示需要管理员权限；启动超时 → 提示用户。
*   **对应 Function Call 序列（跨类别，完整链）**：
    1.  `service_list(name="MySQL")` → **【Tool 60】**查询 MySQL 服务状态
    2.  *(LLM 内部处理：判断服务状态)*
        *   **if 服务不存在**: `send_notification(title="服务不存在", message="系统中未找到 MySQL 服务，请确认是否已安装")` → **【Tool 107】**结束
        *   **if 服务运行中**:
            3.  `send_notification(title="服务状态", message="MySQL 服务：运行中\nPID: XXX\n启动时间：XXX")` → **【Tool 107】**通知用户，结束
        *   **if 服务已停止**:
            3.  `service_start(name="MySQL")` → **【Tool 61】**启动 MySQL 服务
            4.  `wait_for_condition(condition="MySQL 服务状态为运行中", timeout=30)` → **【❌ 未定义，需新增】**等待服务启动完成（可用 `execute_shell_command` 执行 `timeout` + `sc query` 循环替代）
            5.  `service_list(name="MySQL")` → **【Tool 60】**再次检查服务状态，验证启动成功
                *   **if 启动成功**: `send_notification(title="服务已启动", message="MySQL 服务已成功启动\nPID: XXX\n启动时间：XXX")` → **【Tool 107】**通知用户
                *   **if 启动失败**: `send_notification(title="启动失败", message="MySQL 服务启动失败，请检查：1. 配置文件 2. 端口占用 3. 管理员权限")` → **【Tool 107】**通知用户

#### 场景 15 使用工具对照表

| 序号 | 工具名称 | 说明书编号 | 状态 | 所属类别 |
|------|---------|-----------|------|---------|
| 1 | `service_list` | Tool 60 | ✅ 已定义 | 16 类：服务管理 |
| 2 | `service_start` | Tool 61 | ✅ 已定义 | 16 类：服务管理 |
| 3 | `wait_for_condition` | ❌ 未定义 | ⚠️ 需新增 | 附录：配套保障 |
| 4 | `send_notification` | Tool 107 | ✅ 已定义 | 28 类：通知 |

**场景 15 统计**：共 4 个不同工具，3 个已定义 ✅，1 个未定义 ⚠️（`wait_for_condition`，建议新增或用 `execute_shell_command` 替代）

---

## 四、意图翻译的五大核心能力

| 能力 | 说明 | 例子 |
|------|------|------|
| **1. 意图识别** | 听懂用户想干嘛 | "找下"=搜索，"改成"=编辑，"打包"=压缩 |
| **2. 步骤拆解** | 把一件事拆成几步 | 找文件 = 搜索 + 过滤 + 确认 |
| **3. 参数提取** | 从话里抠出关键信息 | "上周"=时间过滤，"合同"=关键词 |
| **4. 条件判断** | 识别分支逻辑 | "没运行就启动"=if/else 判断 |
| **5. 异常处理** | 预判失败情况 | "文件不存在怎么办"=错误处理分支 |

---

## 五、场景覆盖矩阵

| 场景编号 | 场景名称 | 工具总数 | 已定义 | 未定义 | 调用链长度 | 包含条件分支 | 包含异常处理 |
|---------|---------|---------|--------|--------|-----------|-------------|-------------|
| 1 | 找文件 | 7 | 7 | 0 | 11 步 | ✅ 是 | ✅ 是 |
| 2 | 改内容 | 7 | 6 | 1 | 10 步 | ✅ 是 | ✅ 是 |
| 3 | 整理文件 | 7 | 7 | 0 | 10 步 | ✅ 是 | ✅ 是 |
| 4 | 看文档 | 6 | 6 | 0 | 8 步 | ✅ 是 | ✅ 是 |
| 5 | 查信息 | 3 | 3 | 0 | 5 步 | ❌ 否 | ❌ 否 |
| 6 | 网络诊断 | 3 | 3 | 0 | 8 步 | ✅ 是 | ✅ 是 |
| 7 | 打包文件 | 6 | 5 | 1 | 8 步 | ✅ 是 | ✅ 是 |
| 8 | Excel 分析 | 7 | 7 | 0 | 9 步 | ✅ 是 | ✅ 是 |
| 9 | 批量重命名 | 5 | 5 | 0 | 9 步 | ✅ 是 | ✅ 是 |
| 10 | 清理磁盘 | 5 | 4 | 1 | 9 步 | ✅ 是 | ✅ 是 |
| 11 | 搜索网络 | 5 | 5 | 0 | 9 步 | ✅ 是 | ✅ 是 |
| 12 | 翻译内容 | 5 | 5 | 0 | 7 步 | ✅ 是 | ✅ 是 |
| 13 | 查看系统信息 | 3 | 3 | 0 | 8 步 | ✅ 是 | ✅ 是 |
| 14 | 查看进程 | 2 | 2 | 0 | 5 步 | ✅ 是 | ✅ 是 |
| 15 | 查看服务 | 4 | 3 | 1 | 5 步 | ✅ 是 | ✅ 是 |

---

## 六、场景工具汇总与缺口分析

### 6.1 全部场景使用工具汇总

| 工具名称 | 说明书编号 | 使用场景数 | 状态 |
|---------|-----------|-----------|------|
| `send_notification` | Tool 107 | 15 个场景 | ✅ 已定义 |
| `check_path_exists` | Tool 36 | 9 个场景 | ✅ 已定义 |
| `get_file_info` | Tool 18 | 8 个场景 | ✅ 已定义 |
| `get_current_time` | Tool 26 | 6 个场景 | ✅ 已定义 |
| `write_append_file` | Tool 5 | 6 个场景 | ✅ 已定义 |
| `list_directory` | Tool 19 | 3 个场景 | ✅ 已定义 |
| `read_text_file` | Tool 1 | 3 个场景 | ✅ 已定义 |
| `search_files` | Tool 12 | 1 个场景 | ✅ 已定义 |
| `execute_shell_command` | Tool 20 | 2 个场景 | ✅ 已定义 |
| `precise_replace_in_file` | Tool 6 | 1 个场景 | ✅ 已定义 |
| `backup_file` | Tool 42 | 1 个场景 | ✅ 已定义 |
| `create_directory` | Tool 15 | 1 个场景 | ✅ 已定义 |
| `move_file` | Tool 9 | 1 个场景 | ✅ 已定义 |
| `read_pdf` | Tool 80 | 1 个场景 | ✅ 已定义 |
| `calculate_date` | Tool 27 | 1 个场景 | ✅ 已定义 |
| `ping` | Tool 66 | 1 个场景 | ✅ 已定义 |
| `delete_file` | Tool 11 | 1 个场景 | ✅ 已定义 |
| `compress_archive` | Tool 33 | 1 个场景 | ✅ 已定义 |
| `read_xlsx` | Tool 82 | 1 个场景 | ✅ 已定义 |
| `read_csv_dataframe` | Tool 77 | 1 个场景 | ✅ 已定义 |
| `generate_chart` | Tool 78 | 1 个场景 | ✅ 已定义 |
| `rename_file` | Tool 10 | 1 个场景 | ✅ 已定义 |
| `list_directory_with_sizes` | Tool 16 | 1 个场景 | ✅ 已定义 |
| `get_directory_tree` | Tool 17 | 1 个场景 | ✅ 已定义 |
| `search_web` | Tool 24 | 1 个场景 | ✅ 已定义 |
| `fetch_webpage` | Tool 23 | 1 个场景 | ✅ 已定义 |
| `get_system_info` | Tool 30 | 1 个场景 | ✅ 已定义 |
| `list_processes` | Tool 58 | 1 个场景 | ✅ 已定义 |
| `service_list` | Tool 60 | 1 个场景 | ✅ 已定义 |
| `service_start` | Tool 61 | 1 个场景 | ✅ 已定义 |

### 6.2 未定义工具缺口清单（需新增）

| 序号 | 工具名称 | 使用场景 | 建议替代方案 | 建议新增类别 |
|------|---------|---------|-------------|-------------|
| 1 | `restore_backup` | 场景 2：改内容 | 用 `copy_file`（Tool 8）替代 | 附录：配套保障 |
| 2 | `test_archive` | 场景 7：打包文件 | 用 `execute_shell_command` 执行 `unzip -t` 替代 | 9 类：压缩/解压 |
| 3 | `get_disk_usage` | 场景 10：清理磁盘 | 用 `execute_shell_command` 执行 `wmic logicaldisk` 替代 | 7 类：系统信息 |
| 4 | `wait_for_condition` | 场景 15：查看服务 | 用 `execute_shell_command` 循环执行 `sc query` 替代 | 附录：配套保障 |

**缺口统计**：15 个场景共使用 34 个不同工具，其中 30 个已定义 ✅，4 个未定义 ⚠️

---

## 七、总结

**日常场景与 Function Call 的对应关系**：

*   **输入**：日常场景（一句话，人话）
*   **中间处理**：意图翻译（Intent Translation）- 包含意图识别、步骤拆解、参数提取、条件判断、异常处理
*   **输出**：Function Call 调用序列（机器指令列表）
*   **本质**：AI 的**规划能力（Planning）**，将非结构化需求转化为结构化工具调用。

**完整调用链的标准结构**：

```
1. 前置检查（文件/目录/权限是否存在）
2. 条件分支（根据不同情况走不同路径）
3. 核心执行（主要业务逻辑）
4. 后置验证（确认执行结果正确）
5. 结果通知（向用户报告结果）
```

---

**更新时间**: 2026-04-05 08:45:00
