# Phase 1: LLM响应解析器更新实施

**创建时间**: 2026-04-14 06:21:51
**版本**: v1.0
**编写人**: 小沈

---

## 一、测试方案设计

### 1.1 测试用例汇总（基于设计文档3.1-3.5示例）

#### TC001: 正常JSON+文本解析
- **输入**: `好的，用户需要检查E盘的目录数量。之前调用list_directory时没有提供dir_path参数导致错误。现在需要补上正确的路径参数。\n\n{"thought": "用户需要检查E盘根目录下的文件夹和文件情况。", "tool_name": "list_directory", "tool_params": {"dir_path": "E:/"}}`
- **预期输出**:
  - content = "好的，用户需要检查E盘的目录数量。之前调用list_directory时没有提供dir_path参数导致错误。现在需要补上正确的路径参数。"
  - thought = "用户需要检查E盘根目录下的文件夹和文件情况。"
  - tool_name = "list_directory"
  - tool_params = {"dir_path": "E:/"}
- **测试目的**: 验证JSON前面的纯文本被正确分离

#### TC002: 嵌套JSON解析
- **输入**: `我来执行操作。\n\n{"tool_name": "list_directory", "tool_params": {"dir_path": "E:/", "recursive": true}}`
- **预期输出**:
  - tool_name = "list_directory"
  - tool_params = {"dir_path": "E:/", "recursive": true}
- **测试目的**: 验证嵌套JSON正确解析

#### TC003: 截断的JSON解析
- **输入**: `调用list_directory\n\n{"tool_name": "list_directory", "params": {"dir_path": "E:/"`
- **预期输出**:
  - content = "调用list_directory"
  - tool_name = "list_directory"
  - tool_params = {"dir_path": "E:/"}
- **测试目的**: 验证截断JSON能正确解析

#### TC004: Markdown包裹JSON解析
- **输入**: `我来调用list_directory。\n\n```json\n{"tool_name": "list_directory", "tool_params": {"dir_path": "E:/"}}\n```\n`
- **预期输出**:
  - content = "我来调用list_directory。"
  - tool_name = "list_directory"
  - tool_params = {"dir_path": "E:/"}
- **测试目的**: 验证Markdown代码块被正确去除

#### TC005: 总结性文本finish判断
- **输入**: `任务已完成，E盘共有28个目录。\n\n{"thought": "任务完成", "tool_name": "finish", "tool_params": {}}`
- **预期输出**:
  - content = "任务已完成，E盘共有28个目录。"
  - tool_name = "finish"
- **测试目的**: 验证行首总结词正确判断finish

#### TC006: 空content情况
- **输入**: `{"tool_name": "list_directory", "tool_params": {"dir_path": "E:/"}}`
- **预期输出**:
  - content = ""
  - tool_name = "list_directory"
- **测试目的**: 验证无JSON前文本时content为空

#### TC007: thought字段单独提取
- **输入**: `分析任务...\n{"thought": "需要读取文件", "tool_name": "read_file", "tool_params": {"file_path": "/a.txt"}}`
- **预期输出**:
  - content = "分析任务..."
  - thought = "需要读取文件"
  - tool_name = "read_file"
- **测试目的**: 验证thought和content分开

#### TC008: 多工具名字段兼容
- **输入**: `{"action": "read_file", "action_input": {"file_path": "/a.txt"}}`
- **预期输出**:
  - tool_name = "read_file"
- **测试目的**: 验证action字段兼容

#### TC009: 截断Markdown代码块
- **输入**: `调用工具\n\n```json\n{"tool_name": "list_directory"`
- **预期输出**:
  - content = "调用工具"
  - tool_name = "list_directory"
- **测试目的**: 验证截断的代码块能正确处理

#### TC010: 字符串中的花括号不误判
- **输入**: `{"reasoning": "调用list_directory，参数是{dir_path: 'E:/'}", "tool_name": "finish", "tool_params": {}}`
- **预期输出**:
  - tool_name = "finish"
- **测试目的**: 验证字符串内花括号不干扰解析

---

### 1.2 回归测试用例（基于现有test_tool_parser.py）

| 用例ID | 测试内容 | 预期结果 |
|--------|---------|---------|
| TC029 | 标准JSON格式响应 | 解析正确 |
| TC030 | Markdown JSON代码块 | 解析正确 |
| TC031 | 无json标签代码块 | 解析正确 |
| TC032 | 缺少thought字段 | 使用空字符串 |
| TC033 | 缺少action字段 | 默认finish |
| TC034 | 缺少action_input字段 | 空字典 |
| TC035 | camelCase的actionInput | 正确解析 |
| TC036 | 包含额外字段 | 忽略额外字段 |
| TC037 | 非结构化文本响应 | 解析正确 |
| TC038 | 格式错误的JSON | 回退处理 |
| TC039 | 空响应 | 抛出异常 |
| TC040 | 完全无效JSON | 抛出异常 |
| TC041 | 部分JSON | 默认finish |
| TC046 | Unicode内容 | 正确解析 |
| TC047 | 嵌套JSON对象 | 正确解析 |
| TC049 | 特殊字符 | 正确解析 |
| TC050 | action_input包含数组 | 正确解析 |

---

## 二、实施步骤详细说明

### 步骤1: 备份文件
```bash
# 创建备份目录
mkdir backup/v1.0_before_parser_update_20260414_062200
# 复制tool_parser.py到备份目录
```

### 步骤2: 新增_extract_json_with_balanced_braces方法（设计文档5.5 Step 3）

**位置**: 在parse_response()方法之前（约第22行）新增静态方法

**代码**:
```python
@staticmethod
def _extract_json_with_balanced_braces(text: str) -> tuple:
    """
    Stage 1: 使用平衡括号匹配找到JSON，提取JSON前面的纯文本
    
    返回：(json_text, content_before_json)
    - json_text: 找到的JSON文本（可能截断）
    - content_before_json: JSON前面的纯文本
    """
    start = -1
    brace_count = 0
    in_string = False
    escape_next = False
    
    for i, char in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            continue
        
        if char == '"' and not escape_next:
            in_string = not in_string
            continue
        
        if in_string:
            continue
        
        if char == '{':
            if start == -1:
                start = i
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0 and start != -1:
                # 找到完整的JSON
                json_text = text[start:i+1]
                content_before = text[:start].strip()
                return json_text, content_before
    
    # 如果JSON被截断，返回不完整JSON
    if start != -1 and brace_count > 0:
        return text[start:], text[:start].strip()
    
    # 没有找到JSON
    return None, text.strip()
```

### 步骤3: 修改parse_response方法调用新方法（设计文档5.5 Step 3调用处）

**位置**: 第36-45行

**当前代码**:
```python
json_match = re.search(
    r'```(?:json)?\s*\n?(.*?)\n?```',
    response,
    re.DOTALL | re.IGNORECASE
)

if json_match:
    json_str = json_match.group(1).strip()
else:
    json_str = response.strip()
```

**修改为**:
```python
# Step 1: 去除Markdown代码块
json_match = re.search(
    r'```(?:json)?\s*\n?(.*?)\n?```',
    response,
    re.DOTALL | re.IGNORECASE
)

if json_match:
    # 去除```后，提取JSON前面的纯文本
    json_str = json_match.group(1).strip()
    json_without_backticks = json_str
else:
    json_without_backticks = response.strip()

# Step 2: 用平衡括号提取JSON和纯文本
json_text, content_before = ToolParser._extract_json_with_balanced_braces(json_without_backticks)
if json_text:
    json_str = json_text
else:
    json_str = json_without_backticks
    content_before = ""
```

### 步骤4: 分开提取content和thought（设计文档5.5 Step 5）

**位置**: 第54-78行

**当前代码**:
```python
content = parsed.get("content", parsed.get("thought", ""))
```

**修改为**:
```python
# JSON前面的纯文本作为content（用于显示）
content = content_before
# JSON里的thought单独提取
thought = parsed.get("thought", parsed.get("thinking", ""))
```

**最终return修改为**:
```python
return {
    "content": content,          # JSON前面的纯文本
    "thought": thought,          # JSON里的thought
    "tool_name": tool_name,
    "tool_params": tool_params,
    "reasoning": reasoning,
}
```

### 步骤5: 修复summarize_patterns（设计文档5.5 Step 2）

**位置**: 第140-154行

**当前代码**:
```python
summarize_patterns = [
    # 英文总结
    r'(?:summarize|summary|I have found|I will)',
    # 中文总结
    r'(?:总结|已完成|任务完成|结束了)',
    r'(?:根据.*?结果|基于.*?内容|以上)',  # BUG: 这行误判
    # 磁盘目录描述
    r'(?:D盘|E盘|C盘).*?(?:如下|目录|文件|内容|列表)',
]
```

**修改为**:
```python
# 【修复 2026-04-13】改进的finish判断
# 只匹配行首/句首的总结词，不匹配中间的内容
summarize_patterns = [
    # 英文总结 - 必须行首/句首
    r'^(?:summarize|summary|I have found|I will)',
    # 中文总结 - 必须行首/句首
    r'^(?:总结|已完成|任务完成|结束了)',
]
```

### 步骤6: 删除返回时的旧字段（设计文档5.5 Step 1）

**位置**: 第76-77行

**当前代码**:
```python
# 保持向后兼容
"action_tool": tool_name,
"params": tool_params
```

**修改**: 直接删除这两行

---

## 三、检查清单

### 3.1 修改前检查

- [ ] 确认tool_parser.py文件存在
- [ ] 确认当前版本备份完成
- [ ] 确认bug位置：
  - 第145行: `r'(?:根据.*?结果|基于.*?内容|以上)'`
  - 第54行: 只取content字段
  - 第36-45行: 未分离content和thought

### 3.2 修改中检查

- [ ] 步骤2: 新增_extract_json_with_balanced_braces方法（约第22行）
- [ ] 步骤3: 修改第36-52行调用新方法
- [ ] 步骤4: 修改第54行分开提取content和thought
- [ ] 步骤4: 修改return结构，添加thought字段
- [ ] 步骤5: 修复summarize_patterns（第140-154行）
  - 删除第145行 `r'(?:根据.*?结果|基于.*?内容|以上)'`
  - 删除第147行 `r'(?:D盘|E盘|C盘).*?(?:如下|目录|文件|内容|列表)'`
  - 在英文和中文pattern前加`^`
- [ ] 步骤6: 删除第76-77行的旧字段

### 3.3 修改后检查

- [ ] 运行单元测试: `pytest tests/test_tool_parser.py -v`
- [ ] 验证TC001-TC010新测试用例
- [ ] 验证TC029-TC050回归测试用例
- [ ] 检查content字段：JSON前面的纯文本
- [ ] 检查thought字段：JSON里的thought单独提取
- [ ] 检查summarize_patterns：不再误判"根据...结果"

---

## 四、版本历史

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-04-14 06:21:51 | 初始测试计划和实施步骤 | 小沈 |

---

## 五、参考设计文档

- 文档: `D:\OmniAgentAs-desk\doc-4月优化\LLM响应解析器最终设计方案-小沈-2026-04-13-v3.md`
- 相关章节:
  - 1.1 常见格式汇总
  - 1.2 网上学习的边界情况
  - 2.2 完整代码
  - 3.1-3.5 示例验证
  - 5.1 现有代码解析层次分析
  - 5.2 各层的问题定位
  - 5.3 各层的更新实施方法
  - 5.5 更新的检查清单
  - 5.6 代码更新实施方法
