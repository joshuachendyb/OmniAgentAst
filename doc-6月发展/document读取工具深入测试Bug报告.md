# document读取工具深入测试Bug报告 - 小健 2026-06-24

**测试时间**: 2026-06-24
**测试工具**: read_pdf, read_docx, read_pptx, read_xlsx
**测试用例数**: 19个
**通过**: 17个
**失败**: 2个
**发现Bug**: 2个

---

## Bug清单

### Bug #1: read_docx空段落处理不一致

**测试用例**: `test_bug1_empty_paragraphs`

**问题描述**:
- 输入: 包含空段落的Word文档（段落间有空段落）
- 预期: 文本中应该包含连续换行符 `\n\n`
- 实际: 只包含单个换行符 `\n`

**代码位置**: `read_docx.py:94-95`

**根本原因**:
```python
paragraphs = [para.text for para in doc.paragraphs]
text = "\n".join(paragraphs)
```
- 空段落的 `para.text` 为空字符串 `""`
- `"\n".join(["", "内容", ""])` 结果为 `"\n内容\n"`
- 但预期应该是保留空段落，即 `"\n\n内容\n\n"`

**影响**:
- 文档结构信息丢失
- 无法区分"空段落"和"段落间换行"

**建议修复**:
```python
# 方案1: 保留空段落（添加标记）
paragraphs = [para.text if para.text else "[空段落]" for para in doc.paragraphs]

# 方案2: 过滤空段落（当前行为）
paragraphs = [para.text for para in doc.paragraphs if para.text]

# 方案3: 保留空段落（双换行）
text = "\n\n".join(paragraphs)
```

**优先级**: P2（中）

---

### Bug #2: read_pptx表格内容未提取

**测试用例**: `test_bug1_table_not_extracted`

**问题描述**:
- 输入: 包含表格的PPT（表格内容：A, B, C, D）
- 预期: 读取时应该提取表格内容
- 实际: 只提取了标题，表格内容未提取

**代码位置**: `read_pptx.py:70-82`

**根本原因**:
```python
for shape in slide.shapes:
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            text = para.text.strip()
            if text:
                slide_text.append(text)
```
- 只检查 `shape.has_text_frame`
- 未检查 `shape.has_table`
- 表格内容被忽略

**影响**:
- 表格数据丢失
- 用户无法获取PPT中的表格信息

**建议修复**:
```python
for shape in slide.shapes:
    if shape.has_table:
        # 提取表格内容
        table = shape.table
        for row in table.rows:
            row_text = [cell.text.strip() for cell in row.cells]
            slide_text.append(" | ".join(row_text))
    elif shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            text = para.text.strip()
            if text:
                slide_text.append(text)
```

**优先级**: P1（高）

---

## 其他发现的问题（未触发但需关注）

### read_docx问题

| 问题编号 | 问题描述 | 优先级 |
|---------|---------|--------|
| Docx #1 | 合并单元格数据重复 | P2 |
| Docx #2 | 特殊格式信息丢失（颜色、字体等） | P3 |
| Docx #3 | 页眉页脚未提取 | P2 |
| Docx #4 | 图片未提取 | P2 |

### read_pptx问题

| 问题编号 | 问题描述 | 优先级 |
|---------|---------|--------|
| Pptx #1 | 图片未提取 | P2 |
| Pptx #2 | 母版内容未提取 | P3 |
| Pptx #3 | 隐藏幻灯片未处理 | P3 |

### read_xlsx问题

| 问题编号 | 问题描述 | 优先级 |
|---------|---------|--------|
| Xlsx #1 | 公式结果未计算（data_only=True需要先打开Excel） | P2 |
| Xlsx #2 | 多工作表只读取第一个 | P1 |
| Xlsx #3 | CSV不同分隔符未自动检测 | P2 |
| Xlsx #4 | CSV无表头时第一行被当作表头 | P2 |
| Xlsx #5 | 空行处理不明确 | P3 |

### read_pdf问题

| 问题编号 | 问题描述 | 优先级 |
|---------|---------|--------|
| Pdf #1 | 文本提取顺序可能不正确 | P2 |
| Pdf #2 | 表格提取准确性依赖pdfplumber | P2 |
| Pdf #3 | 图片提取信息有限 | P2 |
| Pdf #4 | 密码保护PDF未处理 | P2 |

---

## 测试覆盖度分析

| 工具 | 测试用例 | 通过 | 失败 | 覆盖度 |
|------|---------|------|------|--------|
| read_docx | 5 | 4 | 1 | 80% |
| read_pptx | 3 | 2 | 1 | 67% |
| read_xlsx | 5 | 5 | 0 | 100% |
| read_pdf | 3 | 3 | 0 | 100% |
| 对比测试 | 3 | 3 | 0 | 100% |
| **总计** | **19** | **17** | **2** | **89%** |

---

## 修复优先级

### P1（高优先级）

1. **Bug #2**: read_pptx表格内容未提取
2. **Xlsx #2**: 多工作表只读取第一个

### P2（中优先级）

3. **Bug #1**: read_docx空段落处理不一致
4. **Docx #1**: 合并单元格数据重复
5. **Docx #3**: 页眉页脚未提取
6. **Xlsx #3**: CSV不同分隔符未自动检测
7. **Xlsx #4**: CSV无表头处理

### P3（低优先级）

8. **Docx #2**: 特殊格式信息丢失
9. **Xlsx #5**: 空行处理不明确

---

## 建议改进

### 1. read_pptx增强

```python
# 提取表格
if shape.has_table:
    table = shape.table
    table_data = []
    for row in table.rows:
        row_data = [cell.text.strip() for cell in row.cells]
        table_data.append(row_data)
    slide_text.append(f"[表格: {len(table_data)}行 x {len(table_data[0])}列]")
    for row in table_data:
        slide_text.append(" | ".join(row))
```

### 2. read_xlsx增强

```python
# 支持多工作表
def read_xlsx(file_name, sheet_name=None):
    # 如果指定sheet_name，只读取该工作表
    # 否则返回所有工作表的数据
    pass

# CSV分隔符自动检测
def detect_delimiter(file_path):
    with open(file_path, 'r') as f:
        first_line = f.readline()
        for delimiter in [',', ';', '\t', '|']:
            if delimiter in first_line:
                return delimiter
    return ','
```

### 3. read_docx增强

```python
# 提取页眉页脚
def read_docx(file_name, include_headers_footers=False):
    if include_headers_footers:
        # 提取页眉页脚
        pass
```

---

## 测试文件位置

- 测试文件: `backend/tests/tools/param_combination/test_read_tools_deep_v2.py`

---

**创建时间**: 2026-06-24
**作者**: 小健
**用途**: document读取工具深入测试Bug报告