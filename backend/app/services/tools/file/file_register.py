# -*- coding: utf-8 -*-
"""
File Register - 文件工具注册点

【架构规范】2026-04-26 小沈（更新2026-04-29）
- file_register.py 作为文件工具的注册点
- 实际工具实现在 file_tools.py 的 FileTools 类中
- 使用 registry.py 的 tool_registry.register() 显式注册

【2026-04-29 小沈更新】
- 按文档设计，使用 Pydantic 模型注册
- 使用 input_model 参数，自动生成 OpenAI Schema

【工具列表】（共24个）
1. write_text_file - 写入文本文件 - 小健 2026-05-02 新增
2. list_directory - 列出目录
3. delete_file - 删除文件
5. move_file - 移动文件
6. search_files_by_name - 按名称搜索文件
7. generate_report - 生成报告
8. copy_file - 复制文件
9. create_directory - 创建目录
10. get_file_info - 获取文件信息
11. compress_files - 压缩文件
12. compare_files - 比较文件
13. batch_rename - 批量重命名
14. file_checksum - 文件校验
15. file_statistics - 文件统计
16. file_monitor - 文件监控
17. read_text_file - 读取文本文件
18. read_media_file - 读取媒体文件
19. read_batch_file - 批量读取文件
20. precise_replace_in_file - 精确替换文件内容
21. edit_text_file - 编辑文本文件
22. rename_file - 重命名文件/目录
23. grep_file_content - 搜索文件内容
24. get_directory_tree - 获取目录树
25. list_allowed_directories - 列出允许访问的目录

【注册说明】
- file_tools.py 的旧 _TOOL_REGISTRY 已移除（2026-04-26）
- 使用 registry.py 的 tool_registry 统一注册
- 导入 file_register 时自动触发注册

创建时间: 2026-04-26
更新时间: 2026-04-29
"""

# ============================================================
# 文件工具注册 - 使用 Pydantic 模型（按文档设计）
# ============================================================
import logging
from typing import Optional
from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

# 导入 Pydantic 模型（按文档5.1设计）
# 【小健 2026-04-29】强制规范：新增工具必须从file_schema导入对应Pydantic模型，禁止手动编写input_schema字典
# 【小健 2026-04-29】后续新增tool类型（time/shell/network等）也必须按此要求，从对应schema文件导入模型注册
from app.services.tools.file.file_schema import (
    WriteTextFileInput,
    ListDirectoryInput,
    DeleteFileInput,
    MoveFileInput,
    SearchFilesInput,
    GenerateReportInput,
    CopyFileInput,
    CreateDirectoryInput,
    GetFileInfoInput,
    CompareFilesInput,
    BatchRenameInput,
    CompressFilesInput,
    FileMonitorInput,
    FileStatisticsInput,
    FileChecksumInput,
    ReadTextFileInput,
    ReadMediaFileInput,
    ReadBatchFileInput,
    PreciseReplaceInFileInput,
    EditTextFileInput,
    RenameFileInput,
    GrepFileContentInput,
    GetDirectoryTreeInput,
    ListAllowedDirectoriesInput,
)

# 导入工具类
from app.services.tools.file.file_tools import FileTools, get_file_tools

# 工具描述（用于注册）
FILE_TOOL_DESCRIPTIONS = {
    "write_text_file": "写入或追加文本文件内容，支持中文内容写入、编码自动检测、追加模式。仅支持文本文件，禁止写入二进制文件。\n\n使用场景：\n- 当用户需要创建新文件并写入内容时使用\n- 当用户需要在已有文件末尾追加内容时使用\n- 当用户需要保存文本内容到文件时使用\n- 当用户需要写入配置文件、日志内容时使用\n\n参数说明：\n- file_path：文件路径，必须是绝对路径\n- text：写入的文本内容，支持中文\n- encoding：文件编码，默认null（自动检测；新建默认utf-8）\n- append：是否追加写入，默认为false。设置为true时在文件末尾追加\n- create_parents：是否自动创建父目录，默认为true\n- unescape：是否自动反转义转义字符（如 \\n 转为真实换行），默认为true\n\n【重要】本工具仅支持文本文件，禁止写入二进制文件。禁止的后缀：.png/.jpg/.jpeg/.gif/.zip/.exe/.dll/.docx/.xlsx/.pptx/.pdf/.mp3/.mp4/.wav/.avi/.mkv等。文件不存在时会自动创建。\n\n使用示例：\n- 创建新文件：{\"file_path\": \"D:/OmniAgentAs-desk/output/result.txt\", \"text\": \"Hello World\"}\n- 追加到日志：{\"file_path\": \"D:/OmniAgentAs-desk/logs/app.log\", \"text\": \"[2026-04-04] Task completed\", \"append\": true}",
    "list_directory": "列出目录内容，包含文件大小、修改时间，支持递归、分页、排序、隐藏文件过滤。\n\n使用场景：\n- 当用户需要查看目录内容及文件大小时使用\n- 当用户想要了解文件夹中哪些文件占用空间较大时使用\n- 当用户需要递归查看子目录时使用\n- 当用户需要分页查看大型目录时使用\n- 当用户需要按名称或大小排序时使用\n- 当用户需要显示隐藏文件时使用\n\n参数说明：\n- dir_path：目录的完整路径（必须是绝对路径）\n- recursive：是否递归列出所有子目录，默认为False\n- max_depth：最大递归深度，仅当 recursive=True 时有效，默认10层保护系统性能\n- page_token：分页令牌，用于获取后续页面结果\n- sortBy：排序方式，可选name（按名称）或size（按大小）\n- include_hidden：是否显示隐藏文件，默认为False\n\n【重要】返回目录中每个文件/目录的名称、路径、类型、大小、修改时间，以及分页信息\n\n使用示例：\n- 基础使用：{\"dir_path\": \"D:/OmniAgentAs-desk\"}\n- 递归查看：{\"dir_path\": \"D:/OmniAgentAs-desk\", \"recursive\": true}\n- 按大小排序：{\"dir_path\": \"D:/OmniAgentAs-desk\", \"sortBy\": \"size\"}",
    "delete_file": "删除文件或目录，默认放入回收站更安全（force=False）。设force=True则永久删除不可恢复。\n\n使用场景：\n- 当用户需要删除文件或目录时使用\n- 当用户需要清理临时文件时使用\n- 当用户确认文件不需要后进行删除时使用\n\n参数说明：\n- file_path：要删除的文件或目录路径\n- recursive：是否递归删除目录，目录非空时需要设为 true\n- force：是否强制永久删除（不放入回收站），默认为false放入回收站更安全；设为true则永久删除不可恢复\n\n【重要】默认放入回收站更安全，force=True永久删除不可恢复。请谨慎使用force=True\n\n使用示例：\n- 删除文件（进回收站）：{\"file_path\": \"D:/OmniAgentAs-desk/temp/cache.txt\"}\n- 永久删除目录：{\"file_path\": \"D:/OmniAgentAs-desk/temp\", \"recursive\": true, \"force\": true}",
    "move_file": "移动或重命名文件。\n\n使用场景：\n- 当用户需要将文件移动到另一个目录时使用\n- 当用户想要重命名文件时使用\n- 当用户需要整理文件结构时使用\n\n参数说明：\n- source_path：源文件路径，即要移动的文件当前路径\n- destination_path：目标文件路径，即文件移动后的新路径\n\n【重要】如果目标位置已存在同名文件，操作会失败\n\n使用示例：\n- 移动文件：{\"source_path\": \"D:/downloads/report.pdf\", \"destination_path\": \"D:/documents/reports/report.pdf\"}\n- 重命名文件：{\"source_path\": \"D:/documents/old_name.txt\", \"destination_path\": \"D:/documents/new_name.txt\"}",
    "search_files": "递归搜索匹配或排除模式的文件/目录，返回完整路径，支持中文文件名搜索。\n\n使用场景：\n- 当用户需要在目录中搜索特定名称的文件时使用\n- 当用户想要查找符合条件的文件时使用\n- 当用户需要对文件进行批量操作前需要找到目标文件时使用\n\n参数说明：\n- search_dir：搜索的起始目录，支持中文目录名\n- pattern：搜索模式，支持 glob 风格通配符。支持中文搜索\n- excludePatterns：排除模式数组\n- recursive：是否递归搜索子目录，默认为True\n- max_depth：最大递归深度\n- ignore_case：是否忽略大小写匹配，默认为True\n- type：搜索类型，可选file/directory\n- sortBy：排序方式，可选name/size/mtime\n\n【重要】递归搜索所有子目录，返回所有匹配的文件完整路径\n\n使用示例：\n- 搜索所有 Python 文件：{\"search_dir\": \"D:/OmniAgentAs-desk\", \"pattern\": \"**/*.py\"}\n- 搜索并排除 node_modules：{\"search_dir\": \"D:/OmniAgentAs-desk\", \"pattern\": \"**/*.js\", \"excludePatterns\": [\"node_modules\"]}",
    "generate_report": "生成文件操作报告，记录所有操作历史。\n\n使用场景：\n- 当用户需要回顾文件操作历史时使用\n- 当用户需要生成操作日志报告时使用\n- 当用户需要审计文件操作时使用\n\n参数说明：\n- output_path：报告输出路径（可选，默认生成在当前目录）\n- format：报告格式，可选text/json/html\n\n【重要】返回包含所有文件操作的时间、路径、操作类型的完整报告\n\n使用示例：\n- 生成报告：{\"output_path\": \"D:/OmniAgentAs-desk/操作报告.txt\"}",
    "copy_file": "复制文件或目录到指定位置。\n\n使用场景：\n- 当用户需要复制文件到另一个位置时使用\n- 当用户想要备份文件时使用\n- 当用户需要创建文件的副本时使用\n\n参数说明：\n- source_path：源文件或目录路径\n- destination_path：目标路径\n- recursive：是否递归复制目录，仅当源路径是目录时有效\n- overwrite：目标已存在时是否覆盖\n- preserve_metadata：是否保留文件元数据（修改时间等），默认true\n\n【重要】如果目标路径已存在文件且 overwrite 为 false，操作会失败\n\n使用示例：\n- 复制文件：{\"source_path\": \"D:/OmniAgentAs-desk/config.yaml\", \"destination_path\": \"D:/backup/config.yaml\"}\n- 复制目录：{\"source_path\": \"D:/OmniAgentAs-desk/src\", \"destination_path\": \"D:/backup/src\", \"recursive\": true}",
    "create_directory": "创建新目录，如需要会创建父目录，目录已存在则静默成功。\n\n使用场景：\n- 当用户需要创建新目录时使用\n- 当用户需要创建多级目录时使用\n- 当用户需要在指定位置创建文件夹时使用\n\n参数说明：\n- dir_path：要创建的目录的完整路径（必须是绝对路径）\n- parents：是否创建父目录，默认为True（如果父目录不存在则创建）\n- exist_ok：如果目录已存在是否报错，默认为True（不报错，静默成功）\n\n【重要】默认情况下会自动创建父目录，且已存在目录不会报错，确保操作幂等性\n\n使用示例：\n- 创建单级目录：{\"dir_path\": \"D:/OmniAgentAs-desk/new_folder\"}\n- 创建多级目录：{\"dir_path\": \"D:/OmniAgentAs-desk/output/reports/2026\"}\n- 不创建父目录（父目录必须存在）：{\"dir_path\": \"D:/existing_folder/new_folder\", \"parents\": false}\n- 目录已存在时报错：{\"dir_path\": \"D:/existing_folder\", \"exist_ok\": false}",
    "get_file_info": "获取文件/目录的详细元数据，包括大小、创建/修改/访问时间、类型、权限。\n\n使用场景：\n- 当用户需要获取文件的详细信息时使用\n- 当用户想要了解文件的大小、修改时间等元数据时使用\n- 当用户需要检查文件类型和权限时使用\n\n参数说明：\n- file_path：文件或目录路径\n- follow_symlinks：是否跟随软链接。设置为 true 时获取链接指向的真实文件信息，设置为 false 时获取链接文件本身信息\n\n【重要】返回文件的完整元数据信息，包括：文件大小（字节）、创建时间、修改时间、访问时间、文件类型、权限标志\n\n使用示例：\n- 获取文件信息：{\"file_path\": \"D:/OmniAgentAs-desk/version.txt\"}\n- 不跟随软链接：{\"file_path\": \"D:/OmniAgentAs-desk/shortcut.lnk\", \"follow_symlinks\": false}",
    "compare_files": "比较两个文件的内容/大小/修改时间差异，支持分块比较大文件。\n\n使用场景：\n- 当用户需要比较两个文件是否相同时使用\n- 当用户需要检查文件是否被修改时使用\n- 当用户需要查找两个文件的差异时使用\n\n参数说明：\n- file_path1：第一个文件路径\n- file_path2：第二个文件路径\n- mode：比较模式，可选content/size/mtime/all\n- chunk_size：分块大小，用于大文件分块比较\n\n【重要】支持分块比较，适合大文件。返回比较结果包含差异位置和行数\n\n使用示例：\n- 比较两个文件：{\"file_path1\": \"D:/a.txt\", \"file_path2\": \"D:/b.txt\"}\n- 分块比较：{\"file_path1\": \"D:/large1.txt\", \"file_path2\": \"D:/large2.txt\", \"chunk_size\": 4096}",
    "batch_rename": "批量重命名文件（正则匹配），支持预览、冲突处理。\n\n使用场景：\n- 当用户需要批量重命名文件时使用\n- 当用户需要按规则统一修改文件名时使用\n- 当用户需要重命名多个文件时使用\n\n参数说明：\n- dir_path：目录路径\n- pattern：正则匹配模式\n- replacement：替换内容\n- recursive：是否递归子目录\n- preview：是否预览模式（不执行仅显示结果）\n- conflict：冲突处理方式skip/overwrite/rename\n\n【重要】首次执行建议preview=true先预览，确认无误后再执行\n\n使用示例：\n- 预览模式：{\"dir_path\": \"D:/files\", \"pattern\": \"(.*)\\.txt\", \"replacement\": \"$1_backup.txt\", \"preview\": true}\n- 执行重命名：{\"dir_path\": \"D:/files\", \"pattern\": \"(.*)\\.txt\", \"replacement\": \"$1_backup.txt\", \"preview\": false}",
    "compress_files": "压缩文件或目录为zip/tar.gz，支持加密（password）和分卷（split_size）。\n\n使用场景：\n- 当用户需要压缩文件或目录时使用\n- 当用户需要打包多个文件时使用\n- 当用户需要创建备份时使用\n\n参数说明：\n- source_path：要压缩的文件或目录路径\n- output_path：压缩包输出路径\n- format：压缩格式，可选zip/tar.gz\n- password：加密密码（可选）\n- split_size：分卷大小，如10m、100m\n\n【重要】支持任意类型文件，支持加密和分卷\n\n使用示例：\n- 压缩目录：{\"source_path\": \"D:/docs\", \"output_path\": \"D:/backup/docs.zip\"}\n- 加密压缩：{\"source_path\": \"D:/docs\", \"output_path\": \"D:/backup/docs.zip\", \"password\": \"mypassword\"}\n- 分卷压缩：{\"source_path\": \"D:/large\", \"output_path\": \"D:/backup/large.zip\", \"split_size\": \"100m\"}",
    "file_monitor": "监控目录文件变化（创建/修改/删除/重命名事件），支持递归监控、过滤条件、限时监控。\n\n使用场景：\n- 当用户需要监控目录文件变化时使用\n- 当用户需要监听文件创建/修改/删除事件时使用\n- 当用户需要实时了解目录变化时使用\n\n参数说明：\n- dir_path：监控的目录路径\n- recursive：是否递归监控子目录\n- events：监控事件类型create/modify/delete/rename\n- excludePatterns：排除模式\n- timeout：监控超时时间（秒）\n\n【重要】支持递归监控、多种事件类型过滤\n\n使用示例：\n- 监控目录：{\"dir_path\": \"D:/watch\", \"timeout\": 60}\n- 监控修改事件：{\"dir_path\": \"D:/watch\", \"events\": [\"modify\"], \"timeout\": 30}",
    "file_statistics": "统计目录的文件数量、总大小、类型分布，支持递归统计、过滤条件、多种输出格式。\n\n使用场景：\n- 当用户需要统计目录文件数量时使用\n- 当用户需要了解目录大小分布时使用\n- 当用户需要按文件类型统计存储空间时使用\n\n参数说明：\n- dir_path：统计的目录路径\n- recursive：是否递归统计子目录\n- output_format：输出格式json/csv/text\n- excludePatterns：排除模式\n\n【重要】返回目录的文件数量、总大小、类型分布\n\n使用示例：\n- 统计目录：{\"dir_path\": \"D:/docs\"}\n- JSON格式输出：{\"dir_path\": \"D:/docs\", \"output_format\": \"json\"}",
    "file_checksum": "计算文件的MD5/SHA1/SHA256/SHA512哈希值，用于校验文件完整性。\n\n使用场景：\n- 当用户需要计算文件哈希值时使用\n- 当用户需要校验文件完整性时使用\n- 当用户需要验证下载文件是否被篡改时使用\n\n参数说明：\n- file_path：文件路径\n- algorithm：哈希算法，可选md5/sha1/sha256/sha512，默认sha256\n- verify：验证哈希值（与给定的hash比较）\n\n【重要】支持分块计算大文件，返回哈希值可用于完整性校验\n\n使用示例：\n- 计算SHA256：{\"file_path\": \"D:/downloads/file.zip\"}\n- 验证完整性：{\"file_path\": \"D:/downloads/file.zip\", \"algorithm\": \"sha256\", \"verify\": \"abc123...\"}",
    "read_text_file": "读取文本文件的完整内容，始终以 UTF-8 编码处理文件，支持中文等多字节字符。仅支持文本文件，禁止读取二进制文件。\n\n使用场景：\n- 当用户需要查看文本文件的内容时使用\n- 当用户想要读取配置文件、日志文件、代码文件等文本内容时使用\n- 当用户需要获取文件的前几行或后几行时使用\n\n参数说明：\n- file_path：文件的完整路径，必须是绝对路径，支持中文路径（如 D:/文档/测试.txt）\n- head：读取文件的前 N 行，不能与 tail 参数同时使用\n- tail：读取文件的后 N 行，不能与 head 参数同时使用\n- offset：起始行号（从1开始），不能与 head/tail 参数同时使用，用于分页读取\n- limit：最大读取行数，配合 offset 使用进行分页读取\n\n【重要】本工具仅支持文本文件，禁止读取二进制文件。禁止的后缀：.png/.jpg/.jpeg/.gif/.zip/.exe/.dll/.docx/.xlsx/.pptx/.pdf/.mp3/.mp4/.wav/.avi/.mkv等。若需读取媒体文件（图片/音频），请使用read_media_file工具。\n\n使用示例：\n- 读取全部内容：{\"file_path\": \"D:/OmniAgentAs-desk/backend/app/main.py\"}\n- 只读取前10行：{\"file_path\": \"D:/OmniAgentAs-desk/backend/app/services/agent.py\", \"head\": 10}\n- 只读取最后5行：{\"file_path\": \"D:/OmniAgentAs-desk/logs/app.log\", \"tail\": 5}",
    "read_media_file": "读取图片或音频文件，返回 Base64 编码的数据和对应的 MIME 类型。\n\n使用场景：\n- 当用户需要获取图片或音频文件的内容时使用\n- 当用户想要将媒体文件转换为 Base64 字符串以便传输或嵌入时使用\n- 当用户需要查看媒体文件的 MIME 类型时使用\n\n参数说明：\n- file_path：媒体文件的完整路径，必须是绝对路径\n\n【重要】返回 Base64 编码的媒体数据和 MIME 类型，适用于图片（JPG、PNG、GIF等）和音频（MP3、WAV等）文件\n\n使用示例：\n- 读取图片：{\"file_path\": \"D:/OmniAgentAs-desk/docs/screenshot.png\"}\n- 读取音频：{\"file_path\": \"D:/OmniAgentAs-desk/audio/notification.mp3\"}",
    "read_batch_file": "同时读取多个文件的内容，单个文件读取失败不会中断整个操作。仅支持文本文件，Agent会自动跳过二进制文件并提示。\n\n使用场景：\n- 当用户需要同时读取多个文件进行分析或对比时使用\n- 当用户想要批量获取多个配置文件内容时使用\n- 当用户需要快速了解多个相关文件的内容时使用\n\n参数说明：\n- file_paths：文件路径数组，每个元素必须是文件的完整绝对路径\n\n【重要】本工具仅支持文本文件，禁止读取二进制文件。禁止的后缀：.png/.jpg/.jpeg/.gif/.zip/.exe/.dll/.docx/.xlsx/.pptx/.pdf/.mp3/.mp4/.wav等。Agent会自动检测文件类型，跳过二进制文件并返回提示信息。\n\n使用示例：\n- 读取2个文件：{\"file_paths\": [\"D:/OmniAgentAs-desk/backend/app/main.py\", \"D:/OmniAgentAs-desk/backend/app/config.py\"]}\n- 读取配置文件：{\"file_paths\": [\"D:/OmniAgentAs-desk/config.yaml\", \"D:/OmniAgentAs-desk/.env\"]}",
    "precise_replace_in_file": "执行精确的字符串替换，支持中文内容精确匹配和替换。仅支持文本文件，禁止编辑二进制文件。\n\n使用场景：\n- 当用户需要精确替换文件中特定的字符串时使用\n- 当用户需要对代码进行精确修改时使用\n- 当用户需要在文件中替换特定的文本内容时使用\n\n参数说明：\n- file_path：文件的绝对路径，支持中文路径（必须是文本文件）\n- old_string：要替换的精确文本，支持中文。必须是文件中确实存在的文本\n- new_string：替换后的文本，支持中文\n- replace_all：是否替换所有匹配项，默认为 false。设置为 true 时替换所有匹配项，设置为 false 时只替换第一个匹配项\n\n【重要】仅支持文本文件，二进制文件（.png/.jpg/.zip/.exe等）将被拒绝\n\n使用示例：\n- 替换单个：{\"file_path\": \"D:/OmniAgentAs-desk/backend/app/main.py\", \"old_string\": \"def old_func():\", \"new_string\": \"def new_func():\"}\n- 替换全部：{\"file_path\": \"D:/OmniAgentAs-desk/backend/app/main.py\", \"old_string\": \"print(\\\"debug\\\")\", \"new_string\": \"# print(\\\"debug\\\")\", \"replace_all\": true}",
    "edit_text_file": "使用高级模式匹配进行选择性编辑，支持多同时编辑、缩进保留、dryRun 预览。仅支持文本文件，禁止编辑二进制文件（.png/.jpg/.zip/.exe等）。\n\n使用场景：\n- 当用户需要同时对文件进行多处编辑时使用\n- 当用户想要先预览修改效果再实际执行时使用\n- 当用户需要对代码文件进行批量修改时使用\n\n参数说明：\n- file_path：要编辑的文件路径（必须是文本文件）\n- edits：编辑操作数组，每个元素包含 oldText（要替换的文本）和 newText（替换后的文本），支持同时执行多个编辑操作\n- dryRun：预览模式，设置为 true 时不实际修改文件，只返回修改后的内容预览。默认值为 false\n\n【重要】仅支持文本文件编辑，二进制文件（.png/.jpg/.zip/.exe/.docx/.xlsx/.pdf/.mp3等）将被拒绝并提示使用专业工具\n\n使用示例：\n- 单次编辑：{\"file_path\": \"D:/OmniAgentAs-desk/backend/app/main.py\", \"edits\": [{\"oldText\": \"def old():\", \"newText\": \"def new():\"}]}\n- 多次编辑：{\"file_path\": \"D:/OmniAgentAs-desk/backend/app/main.py\", \"edits\": [{\"oldText\": \"import os\", \"newText\": \"import os\\nimport sys\"}, {\"oldText\": \"def foo():\", \"newText\": \"def bar():\"}]}\n- 预览模式：{\"file_path\": \"D:/OmniAgentAs-desk/backend/app/main.py\", \"edits\": [{\"oldText\": \"old\", \"newText\": \"new\"}], \"dryRun\": true}",
    "rename_file": "重命名文件或目录，不改变所在目录。\n\n使用场景：\n- 当用户需要重命名文件时使用\n- 当用户想要重命名目录时使用\n- 当用户需要修改文件名但保持文件位置不变时使用\n\n参数说明：\n- file_path：当前文件或目录的路径\n- new_name：新的文件名或目录名\n\n【重要】只改变名称，不改变所在目录。如果新名称与同目录已有文件重名，操作会失败\n\n使用示例：\n- 重命名文件：{\"file_path\": \"D:/documents/report_old.txt\", \"new_name\": \"report_final.txt\"}\n- 重命名目录：{\"file_path\": \"D:/projects/old_folder\", \"new_name\": \"new_folder\"}",
    "grep_file_content": "基于 ripgrep 的强大内容搜索，支持正则表达式和多选项，支持 Unicode 中文字符搜索。\n\n使用场景：\n- 当用户需要在文件中搜索特定内容时使用\n- 当用户想要查找包含特定关键词的代码行时使用\n- 当用户需要对多个文件进行内容搜索时使用\n\n参数说明：\n- pattern：正则表达式搜索模式，支持中文（如搜索\"函数定义\"或\"class.*方法\"）\n- search_dir：搜索路径，默认为当前目录\n- output_mode：输出模式。content-显示匹配行的内容；files_with_matches-只显示包含匹配的文件名；count-显示每个文件的匹配数量\n- glob：文件类型过滤，使用 glob 通配符（如 \"*.ts\" 或 \"*.{js,py}\"）\n- type：语言类型，简化 glob 匹配（如 js, py, rust, html, json）\n- after_lines：匹配行之后额外显示的行数，用于查看后续上下文\n- before_lines：匹配行之前额外显示的行数，用于查看前面上下文\n- context_lines：匹配行前后各显示的行数，同时设置 before 和 after\n- ignore_case：搜索时忽略大小写，例如 \"test\" 会匹配 \"Test\" 和 \"TEST\"\n- show_line_no：是否在输出中显示行号，便于定位\n- multiline：启用多行匹配模式，允许正则表达式中的 . 匹配换行符\n- head_limit：限制返回的匹配结果数量，用于大文件搜索避免输出过多\n\n【重要】支持强大的正则表达式搜索，可以精确定位代码中的内容\n\n使用示例：\n- 简单搜索：{\"pattern\": \"def read_file\", \"search_dir\": \"D:/OmniAgentAs-desk/backend\"}\n- 搜索TS文件中的class：{\"pattern\": \"class.*Component\", \"search_dir\": \"D:/OmniAgentAs-desk/frontend\", \"glob\": \"*.tsx\", \"ignore_case\": true}\n- 带上下文搜索：{\"pattern\": \"async def.*tool\", \"search_dir\": \"D:/OmniAgentAs-desk/backend\", \"context_lines\": 3, \"show_line_no\": true}",
    "get_directory_tree": "获取目录的递归 JSON 树结构，每个条目包含 name、type（file/directory）、children。\n\n使用场景：\n- 当用户需要查看完整目录树结构时使用\n- 当用户想要了解项目的整体文件结构时使用\n- 当用户需要生成目录树视图时使用\n\n参数说明：\n- dir_path：起始目录\n- excludePatterns：排除模式数组，符合排除模式的目录不会包含在结果中（glob 格式）\n- max_depth：最大递归深度（可选），由 Agent 根据系统资源动态设置\n\n【重要】返回 JSON 格式的目录树结构，包含每个文件/目录的名称、类型、子目录（仅目录有 children 字段）\n\n使用示例：\n- 获取完整树：{\"dir_path\": \"D:/OmniAgentAs-desk\"}\n- 排除 node_modules：{\"dir_path\": \"D:/OmniAgentAs-desk\", \"excludePatterns\": [\"node_modules\", \"__pycache__\"]}",
    "list_allowed_directories": "列出服务器允许访问的所有目录。\n\n使用场景：\n- 当用户需要确认可以访问哪些目录时使用\n- 当用户想要了解系统允许的文件操作范围时使用\n- 当用户需要检查是否有权限访问特定目录时使用\n\n参数说明：\n- 无参数\n\n【重要】返回服务器配置中允许访问的目录列表，用于确定文件操作的边界\n\n使用示例：\n- 查询允许访问的目录：{}",
}

# 【小沈 2026-04-29】补充 examples 参数 - 17个工具的使用示例
FILE_TOOL_EXAMPLES = {
    "write_text_file": [
        {"file_path": "C:/Users/用户名/Documents/test.txt", "text": "Hello World"},
        {"file_path": "D:/项目代码/config.json", "text": "{\"key\": \"value\"}", "encoding": "utf-8"},
        {"file_path": "D:/项目代码/logs/app.log", "text": "新增日志行\\n", "append": True}
    ],
    "list_directory": [
        {"dir_path": "C:/Users/用户名/Documents"},
        {"dir_path": "D:/项目代码", "recursive": True, "max_depth": 3}
    ],
    "delete_file": [
        {"file_path": "C:/Users/用户名/Documents/temp.txt"},
        {"file_path": "D:/项目代码/logs/app.log"}
    ],
    "move_file": [
        {"source_path": "C:/Users/用户名/Desktop/old.txt", "destination_path": "C:/Users/用户名/Documents/new.txt"},
        {"source_path": "D:/项目代码/a.txt", "destination_path": "D:/项目代码/b.txt"}
    ],
    "search_files": [
        {"path": "D:/项目代码", "file_pattern": "*.py"},
        {"path": "C:/Users/用户名/Documents", "file_pattern": "config*"}
    ],
    "generate_report": [
        {"output_dir": "D:/项目代码"},
        {"output_dir": "C:/Users/用户名/Documents"}
    ],
    "copy_file": [
        {"source_path": "C:/Users/用户名/Documents/source.txt", "destination_path": "C:/Users/用户名/Documents/dest.txt"},
        {"source_path": "D:/项目代码/a.py", "destination_path": "D:/项目代码/b.py"}
    ],
    "create_directory": [
        {"dir_path": "C:/Users/用户名/Documents/新文件夹"},
        {"dir_path": "D:/项目代码/src/components"}
    ],
    "get_file_info": [
        {"file_path": "C:/Users/用户名/Documents/config.json"},
        {"file_path": "D:/项目代码/main.py"}
    ],
    "compare_files": [
        {"file_path1": "C:/Users/用户名/Documents/a.txt", "file_path2": "C:/Users/用户名/Documents/b.txt"},
        {"file_path1": "D:/项目代码/v1.py", "file_path2": "D:/项目代码/v2.py", "algorithm": "content"}
    ],
    "batch_rename": [
        {"dir_path": "C:/Users/用户名/Documents", "pattern": "*.txt", "replacement": "新文件_"},
        {"dir_path": "D:/项目代码", "pattern": "old_", "replacement": "new_"}
    ],
    "compress_files": [
        {"source_path": "C:/Users/用户名/Documents/a.txt", "output_path": "C:/Users/用户名/Documents/archive.zip"},
        {"source_path": "D:/项目代码/src", "output_path": "D:/项目代码/code.zip", "format": "zip", "compression_level": 6},
        {"source_path": "D:/项目代码", "output_path": "D:/backup/bak.tar.gz", "format": "tar.gz", "exclude_patterns": ["node_modules", "__pycache__"], "overwrite": False}
    ],
    "file_monitor": [
        {"directory": "C:/Users/用户名/Documents", "event_types": ["created", "modified"]},
        {"directory": "D:/项目代码", "event_types": ["deleted"]}
    ],
    "file_statistics": [
        {"directory": "C:/Users/用户名/Documents"},
        {"directory": "D:/项目代码", "filters": {"file_type": ["*.py", "*.js"]}}
    ],
    "file_checksum": [
        {"file_path": "C:/Users/用户名/Documents/data.zip", "algorithm": "md5"},
        {"file_path": "D:/项目代码/main.py", "algorithm": "sha256"}
    ],
    "read_text_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py"},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/services/agent.py", "head": 10},
        {"file_path": "D:/OmniAgentAs-desk/logs/app.log", "tail": 5}
    ],
    "read_media_file": [
        {"file_path": "D:/OmniAgentAs-desk/docs/screenshot.png"},
        {"file_path": "D:/OmniAgentAs-desk/audio/notification.mp3"}
    ],
    "read_batch_file": [
        {"file_paths": ["D:/OmniAgentAs-desk/backend/app/main.py", "D:/OmniAgentAs-desk/backend/app/config.py"]},
        {"file_paths": ["D:/OmniAgentAs-desk/config.yaml", "D:/OmniAgentAs-desk/.env"]}
    ],
    "precise_replace_in_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "old_string": "def old_func():", "new_string": "def new_func():"},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "old_string": "print(\"debug\")", "new_string": "# print(\"debug\")", "replace_all": True}
    ],
    "edit_text_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "def old():", "newText": "def new():"}]},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "import os", "newText": "import os\nimport sys"}], "dryRun": True}
    ],
    "rename_file": [
        {"file_path": "D:/documents/report_old.txt", "new_name": "report_final.txt"},
        {"file_path": "D:/projects/old_folder", "new_name": "new_folder"}
    ],
    "grep_file_content": [
        {"pattern": "def read_file", "search_dir": "D:/OmniAgentAs-desk/backend"},
        {"pattern": "class.*Component", "search_dir": "D:/OmniAgentAs-desk/frontend", "glob": "*.tsx", "ignore_case": True}
    ],
    "get_directory_tree": [
        {"dir_path": "D:/OmniAgentAs-desk"},
        {"dir_path": "D:/OmniAgentAs-desk", "excludePatterns": ["node_modules", "__pycache__"]}
    ],
    "list_allowed_directories": [
        {}
    ]
}


def _register_file_tools():
    """
    【2026-04-29 小沈更新】按文档5.1设计注册所有文件工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    【小健 2026-04-29】强制要求：此函数在新增工具时必须在TOOL_INPUT_MODELS中添加映射，并传入input_model参数
    【小健 2026-04-29】禁止后续新增工具使用旧的非规范注册方式（直接传input_schema字典）
    """
    # 【重要】延迟创建 FileTools 实例，避免循环导入
    # 工具方法的绑定在函数被调用时才创建，此时 agent已完成初始化
    ft = None
    
    def _get_ft():
        nonlocal ft
        if ft is None:
            from app.services.tools.file.file_tools import FileTools
            ft = FileTools()
        return ft
    
    # 【重要】使用 lambda 延迟绑定方法，避免在注册时立即访问 FileTools
    tool_methods = {
        "write_text_file": lambda: _get_ft().write_text_file,
        "list_directory": lambda: _get_ft().list_directory,
        "delete_file": lambda: _get_ft().delete_file,
        "move_file": lambda: _get_ft().move_file,
        "search_files": lambda: _get_ft().search_files,
        "generate_report": lambda: _get_ft().generate_report,
        "copy_file": lambda: _get_ft().copy_file,
        "create_directory": lambda: _get_ft().create_directory,
        "get_file_info": lambda: _get_ft().get_file_info,
        "compare_files": lambda: _get_ft().compare_files,
        "batch_rename": lambda: _get_ft().batch_rename,
        "compress_files": lambda: _get_ft().compress_files,
        "file_monitor": lambda: _get_ft().file_monitor,
        "file_statistics": lambda: _get_ft().file_statistics,
        "file_checksum": lambda: _get_ft().file_checksum,
        "read_text_file": lambda: _get_ft().read_text_file,
        "read_media_file": lambda: _get_ft().read_media_file,
        "read_batch_file": lambda: _get_ft().read_batch_file,
        "precise_replace_in_file": lambda: _get_ft().precise_replace_in_file,
        "edit_text_file": lambda: _get_ft().edit_file,
        "rename_file": lambda: _get_ft().rename_file,
        "grep_file_content": lambda: _get_ft().grep_file_content,
        "get_directory_tree": lambda: _get_ft().get_directory_tree,
        "list_allowed_directories": lambda: _get_ft().list_allowed_directories,
    }
    
    # 【2026-04-29 小沈新增】工具名到 Pydantic 模型的映射（按文档5.1设计）
    TOOL_INPUT_MODELS = {
        "write_text_file": WriteTextFileInput,
        "list_directory": ListDirectoryInput,
        "delete_file": DeleteFileInput,
        "move_file": MoveFileInput,
        "search_files": SearchFilesInput,
        "generate_report": GenerateReportInput,
        "copy_file": CopyFileInput,
        "create_directory": CreateDirectoryInput,
        "get_file_info": GetFileInfoInput,
        "compare_files": CompareFilesInput,
        "batch_rename": BatchRenameInput,
        "compress_files": CompressFilesInput,
        "file_monitor": FileMonitorInput,
        "file_statistics": FileStatisticsInput,
        "file_checksum": FileChecksumInput,
        "read_text_file": ReadTextFileInput,
        "read_media_file": ReadMediaFileInput,
        "read_batch_file": ReadBatchFileInput,
        "precise_replace_in_file": PreciseReplaceInFileInput,
        "edit_text_file": EditTextFileInput,
        "rename_file": RenameFileInput,
        "grep_file_content": GrepFileContentInput,
        "get_directory_tree": GetDirectoryTreeInput,
        "list_allowed_directories": ListAllowedDirectoriesInput,
    }
    
    # 【2026-04-29 小沈更新】使用 Pydantic 模型注册
    for name, method in tool_methods.items():
        desc = FILE_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)  # 获取对应的 Pydantic 模型
        examples = FILE_TOOL_EXAMPLES.get(name, [])  # 获取工具的使用示例
        
        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.FILE,
            implementation=method,
            version="1.0.0",
            input_model=input_model,  # 【小健 2026-04-29】强制要求：必须传入Pydantic模型，禁止传input_schema字典
            examples=examples  # 【小沈 2026-04-29】补充 examples 参数
        )
        logger.info(f"[file_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


# 触发注册
_register_file_tools()


# ============================================================
# 导出的工具类
# ============================================================
from app.services.tools.file.file_tools import FileTools, get_file_tools


__all__ = [
    "FileTools",
    "get_file_tools",
    "FILE_TOOL_DESCRIPTIONS",
    "TOOL_INPUT_MODELS",
    "FILE_TOOL_EXAMPLES",
    "get_all_file_tool_names",
    "get_tool_input_models",
]


def get_all_file_tool_names() -> list:
    """获取所有已注册的文件工具名 - 小健 2026-05-02"""
    return list(TOOL_INPUT_MODELS.keys())


def get_tool_input_models() -> dict:
    """获取所有工具的Pydantic输入模型映射 - 小健 2026-05-02"""
    return TOOL_INPUT_MODELS