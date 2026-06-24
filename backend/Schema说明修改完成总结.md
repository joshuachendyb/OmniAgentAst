# Schema说明修改完成总结

**修改时间**: 2026-06-24 小欧

## 修改内容

### 1. 文件类型说明（file_schema.py）

#### read_text_file
- **修改前**: "要读取的文件路径(绝对路径)"
- **修改后**: "要读取的文件路径(绝对路径)。支持文本文件:txt/md/py/js/ts/json/yaml/yml/xml/html/css/csv/log等。二进制文件(图片/音频/视频/exe/dll等)将被拒绝,请使用read_media_file工具"

#### write_text_file
- **修改前**: "文件的完整路径(必须是绝对路径,支持中文路径)"
- **修改后**: "文件的完整路径(绝对路径,支持中文路径)。用于写入文本文件:txt/md/py/js/ts/json/yaml/yml/xml/html/css/csv/log等"

### 2. 绝对路径说明（7个参数）

#### dataanalysis_schema.py
1. **GenerateChartInput.output_path**
   - 修改前: "输出图片路径(可选)。不传则自动生成临时路径如<temp>/chart_<时间戳>.png"
   - 修改后: "输出图片路径(绝对路径,可选)。不传则自动生成临时路径如<temp>/chart_<时间戳>.png"

2. **AnalyzeDataInput.data**
   - 修改前: "要分析的数据。可以是CSV/XLSX/XLS文件路径或JSON字符串"
   - 修改后: "要分析的数据。可以是CSV/XLSX/XLS文件路径(绝对路径)或JSON字符串"

3. **FilterDataInput.data**
   - 修改前: "要筛选的数据。可以是CSV/Excel文件路径或JSON字符串"
   - 修改后: "要筛选的数据。可以是CSV/Excel文件路径(绝对路径)或JSON字符串"

#### desktop_schema.py
4. **ScreenCaptureInput.output_path**
   - 修改前: "输出文件路径(可选)。不传则保存到系统临时目录如<temp>/screenshot_<时间戳>.png"
   - 修改后: "输出文件路径(绝对路径,可选)。不传则保存到系统临时目录如<temp>/screenshot_<时间戳>.png"

#### network_schema.py
5. **DownloadFileInput.destination_path**
   - 修改前: "文件保存的完整路径,如 D:/Downloads/file.zip"
   - 修改后: "文件保存的完整路径(绝对路径),如 D:/Downloads/file.zip"

#### shell_schema.py
6. **ExecuteCodeInput.working_dir**
   - 修改前: "工作目录(可选)。默认为当前工作目录。目录不存在时自动创建"
   - 修改后: "工作目录(绝对路径,可选)。默认为当前工作目录。目录不存在时自动创建"

### 3. 未修改项

#### system_schema.py
- **CreateTaskInput.command**: 已包含"程序路径"说明，且实际场景可能包含命令行参数（如`python script.py`），保持不变

#### file_schema.py
- **read_config_file/write_config_file**: 已于2026-06-24删除，text工具已覆盖配置文件功能

## 修改原则

1. **文件类型说明**: 明确支持哪些文件类型，拒绝哪些文件类型，并给出替代工具建议
2. **绝对路径说明**: 在参数说明中明确标注"绝对路径"，避免LLM传入相对路径
3. **保持简洁**: 不冗余重复，只添加必要信息

## 验证方法

LLM调用工具时，Schema说明会出现在function calling的parameters.description中，帮助LLM：
1. 正确选择文件类型（避免对二进制文件使用文本工具）
2. 正确传入绝对路径（避免相对路径导致的文件找不到错误）

## 相关文档

- `backend/Schema文件类型说明审核报告.md` - 文件类型说明审核结果
- `backend/路径说明复核报告.md` - 路径说明复核结果