# 所有Tool Schema文件类型说明审核报告

**审核时间**: 2026-06-24  
**审核人**: 小健  
**范围**: 所有tool分类中涉及文件操作的schema

---

## 一、File分类（15个工具）

### ✅ 合理的说明

| 工具 | 参数 | 说明 | 评价 |
|------|------|------|------|
| read_text_file | file_path | "要读取的文件路径(绝对路径)" | ✅ 简洁清晰 |
| write_text_file | file_path | "文件的完整路径(必须是绝对路径,支持中文路径)" | ✅ 清晰 |
| edit_text_file | file_path | "目标文件的绝对路径(仅支持文本文件,二进制文件将被拒绝)" | ✅ **明确说明文件类型限制** |
| read_media_file | file_path | "媒体文件的完整路径。支持图片(JPG/PNG/GIF/BMP/WebP/SVG/ICO/TIFF)、音频(MP3/WAV/OGG/M4A/FLAC/AAC)、视频(MP4/AVI/MOV/MKV)。返回Base64编码数据" | ✅ **详细列出支持的格式** |
| read_config_file | file_path | "文件路径(必须是绝对路径)" | ⚠️ 未说明支持的配置格式 |
| write_config_file | file_path | "文件路径(必须是绝对路径)" | ⚠️ 未说明支持的配置格式 |

### ❌ 需要改进的说明

#### 1. read_text_file

**当前**:
```python
file_path: str = Field(description="要读取的文件路径(绝对路径)")
```

**问题**: 未说明支持的文件类型

**建议**:
```python
file_path: str = Field(
    description="要读取的文本文件路径(绝对路径)。支持所有文本格式(.txt/.py/.js/.json/.yaml/.md等)，二进制文件(.png/.pdf/.exe等)将被拒绝并提示使用正确工具"
)
```

#### 2. write_text_file

**当前**:
```python
file_path: str = Field(description="文件的完整路径(必须是绝对路径,支持中文路径)")
```

**问题**: 未说明是文本文件，未说明二进制文件会被拒绝

**建议**:
```python
file_path: str = Field(
    description="文本文件的完整路径(绝对路径,支持中文路径)。支持所有文本格式，二进制文件路径(.png/.pdf等)将被拒绝。文件不存在时自动创建，父目录不存在时自动创建"
)
```

#### 3. read_config_file

**当前**:
```python
file_path: str = Field(description="文件路径(必须是绝对路径)")
format: Optional[Literal["json", "yaml", "toml", "ini", "xml", "properties"]] = Field(
    default=None,
    description="强制指定格式:json/yaml/toml/ini/xml/properties。不填则根据文件扩展名自动检测"
)
```

**问题**: file_path未说明支持的格式

**建议**:
```python
file_path: str = Field(
    description="配置文件路径(绝对路径)。支持JSON/YAML/TOML/INI/XML/Properties格式，其他格式将被拒绝"
)
```

#### 4. write_config_file

**当前**:
```python
file_path: str = Field(description="文件路径(必须是绝对路径)")
format: Optional[Literal["json", "yaml", "toml"]] = Field(
    default=None,
    description="强制指定格式:json/yaml/toml。不填则根据文件扩展名自动检测"
)
```

**问题**: file_path未说明支持的格式

**建议**:
```python
file_path: str = Field(
    description="配置文件路径(绝对路径)。支持JSON/YAML/TOML格式，INI/XML/Properties暂不支持写入。文件不存在时自动创建"
)
```

---

## 二、Document分类（8个工具）

### ✅ 合理的说明

| 工具 | 参数 | 说明 | 评价 |
|------|------|------|------|
| read_pdf | file_name | "文件名+路径(.pdf)" | ✅ 明确格式 |
| read_docx | file_name | "文件名+路径(.docx/.doc)" | ✅ 明确格式 |
| read_pptx | file_name | "文件名+路径(.pptx)" | ✅ 明确格式 |
| read_xlsx | file_name | "文件名+路径(.xlsx/.csv/.xls)" | ✅ 明确格式 |
| write_docx | file_name | "文件名+路径(.docx)" | ✅ 明确格式 |
| write_xlsx | file_name | "文件名+路径(.xlsx)" | ✅ 明确格式 |
| write_pdf | file_name | "文件名+路径(.pdf)" | ✅ 明确格式 |
| write_pptx | file_name | "文件名+路径(.pptx)" | ✅ 明确格式 |

**评价**: Document分类schema说明清晰，明确标注了文件格式，无需改进。

---

## 三、DataAnalysis分类（6个工具）

### ⚠️ 需要改进的说明

#### 1. analyze_data

**当前**:
```python
data: str = Field(..., description="要分析的数据。可以是CSV/XLSX/XLS文件路径或JSON字符串")
```

**问题**: 未说明文件路径必须是绝对路径

**建议**:
```python
data: str = Field(
    ..., 
    description="要分析的数据。可以是CSV/XLSX/XLS文件的绝对路径或JSON字符串。文件路径必须是绝对路径"
)
```

#### 2. filter_data

**当前**:
```python
data: str = Field(..., description="要筛选的数据。可以是CSV/Excel文件路径或JSON字符串")
```

**问题**: 未说明文件路径必须是绝对路径

**建议**:
```python
data: str = Field(
    ..., 
    description="要筛选的数据。可以是CSV/XLSX/XLS文件的绝对路径或JSON字符串。文件路径必须是绝对路径"
)
```

#### 3. generate_chart

**当前**:
```python
output_path: Optional[str] = Field(
    default=None,
    description="输出图片路径(可选)。不传则自动生成临时路径如<temp>/chart_<时间戳>.png"
)
```

**问题**: 未说明必须是绝对路径

**建议**:
```python
output_path: Optional[str] = Field(
    default=None,
    description="输出图片的绝对路径(可选)。不传则自动生成临时路径如<temp>/chart_<时间戳>.png"
)
```

---

## 四、Network分类（4个工具）

### ⚠️ 需要改进的说明

#### download_file

**当前**:
```python
destination_path: str = Field(..., description="文件保存的完整路径,如 D:/Downloads/file.zip")
```

**问题**: 说明中有示例，但未明确要求绝对路径

**建议**:
```python
destination_path: str = Field(
    ..., 
    description="文件保存的绝对路径(必填)。必须是完整路径，如 D:/Downloads/file.zip"
)
```

---

## 五、Shell分类（4个工具）

### ⚠️ 需要改进的说明

#### execute_shell_command

**当前**:
```python
cwd: Optional[str] = Field(
    default=None, 
    description="命令执行的工作目录(绝对路径)。需要在特定目录下执行命令时设置,如 D:/project。不设置则使用当前目录"
)
```

**评价**: ✅ 已明确说明绝对路径，无需改进

#### execute_code

**当前**:
```python
working_dir: Optional[str] = Field(
    default=None, 
    description="工作目录(可选)。默认为当前工作目录。目录不存在时自动创建"
)
```

**问题**: 未明确要求绝对路径

**建议**:
```python
working_dir: Optional[str] = Field(
    default=None, 
    description="工作目录的绝对路径(可选)。默认为当前工作目录。目录不存在时自动创建"
)
```

---

## 六、其他分类

### Desktop分类
- 无文件路径参数，无需审核

### System分类
- 无文件路径参数，无需审核

### Timer分类
- 无文件路径参数，无需审核

### WinRegistry分类
- 无文件路径参数，无需审核

---

## 七、审核总结

### ✅ 说明合理的工具（13个）

| 分类 | 工具 | 评价 |
|------|------|------|
| File | edit_text_file | 明确说明"仅支持文本文件" |
| File | read_media_file | 详细列出所有支持的格式 |
| Document | read_pdf/docx/pptx/xlsx | 明确标注文件格式 |
| Document | write_docx/xlsx/pdf/pptx | 明确标注文件格式 |
| Shell | execute_shell_command | cwd明确说明绝对路径 |

### ⚠️ 需要改进的工具（9个）

| 分类 | 工具 | 问题 |
|------|------|------|
| File | read_text_file | 未说明支持的文件类型 |
| File | write_text_file | 未说明是文本文件 |
| File | read_config_file | 未说明支持的配置格式 |
| File | write_config_file | 未说明支持的配置格式 |
| DataAnalysis | analyze_data | 未说明绝对路径 |
| DataAnalysis | filter_data | 未说明绝对路径 |
| DataAnalysis | generate_chart | 未说明绝对路径 |
| Network | download_file | 未明确要求绝对路径 |
| Shell | execute_code | 未说明绝对路径 |

---

## 八、改进优先级

### 🔴 高优先级（影响LLM正确选择工具）

1. **read_text_file** - 未说明支持文本文件，LLM可能用来读二进制
2. **write_text_file** - 未说明是文本文件，LLM可能用来写二进制
3. **read_config_file** - 未说明支持的格式，LLM可能用错格式
4. **write_config_file** - 未说明支持的格式，LLM可能用错格式

### 🟡 中优先级（影响路径正确性）

5. **analyze_data** - 未说明绝对路径
6. **filter_data** - 未说明绝对路径
7. **generate_chart** - 未说明绝对路径
8. **download_file** - 未明确要求绝对路径
9. **execute_code** - 未说明绝对路径

---

## 九、改进建议

### 核心原则

1. **明确文件类型**: 说明支持的文件格式和类型限制
2. **明确路径要求**: 所有文件路径参数必须说明"绝对路径"
3. **明确拒绝行为**: 说明哪些类型会被拒绝，引导LLM使用正确工具
4. **参考edit_text_file**: 它的说明是最好的范例

### 改进模板

```python
# 读文件工具
file_path: str = Field(
    description="XXX文件的绝对路径。支持YYY格式，ZZZ格式将被拒绝并提示使用正确工具"
)

# 写文件工具
file_path: str = Field(
    description="XXX文件的绝对路径。支持YYY格式，ZZZ格式将被拒绝。文件不存在时自动创建，父目录不存在时自动创建"
)
```

---

**审核完成时间**: 2026-06-24 17:30  
**发现问题**: 9个工具需要改进  
**优先级**: 4个高优先级 + 5个中优先级