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



【工具列表】（共25个） 小沈-2026-05-05

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

# 导入 Pydantic 模型（按文档5.1设计）
# 【小健 2026-04-29】强制规范：新增工具必须从file_schema导入对应Pydantic模型，禁止手动编写input_schema字典
# 【小健 2026-04-29】后续新增tool类型（time/shell/network等）也必须按此要求，从对应schema文件导入模型注册
from app.services.tools.file.file_schema import (
    BatchRenameInput,
    CompareFilesInput,
    CompressFilesInput,
    CopyFileInput,
    CreateDirectoryInput,
    DeleteFileInput,
    EditTextFileInput,
    FileChecksumInput,
    FileMonitorInput,
    FileStatisticsInput,
    GenerateReportInput,
    GetDirectoryTreeInput,
    GetFileInfoInput,
    GrepFileContentInput,
    ListAllowedDirectoriesInput,
    ListDirectoryInput,
    MoveFileInput,
    PreciseReplaceInFileInput,
    ReadBatchFileInput,
    ReadMediaFileInput,
    ReadTextFileInput,
    RenameFileInput,
    SearchFilesInput,
    WriteTextFileInput,
    ExtractArchiveInput,
    GetFileHashInput,
)

# 导入工具类
from app.services.tools.file.file_tools import FileTools, get_file_tools
from app.services.tools.registry import ToolCategory, register_tool, tool_registry
from app.utils.logger import logger

# 工具描述（用于注册）

FILE_TOOL_DESCRIPTIONS = {
    "write_text_file": '写入或追加文本文件内容，支持中文内容写入、编码自动检测、追加模式。仅支持文本文件，禁止写入二进制文件。\n\n使用场景：\n- 当用户需要创建新文件并写入内容时使用\n- 当用户需要在已有文件末尾追加内容时使用\n- 当用户需要保存文本内容到文件时使用\n- 当用户需要写入配置文件、日志内容时使用\n 转为真实换行），默认为true\n\n【重要】本工具仅支持文本文件，禁止写入二进制文件。禁止的后缀：.png/.jpg/.jpeg/.gif/.zip/.exe/.dll/.docx/.xlsx/.pptx/.pdf/.mp3/.mp4/.wav/.avi/.mkv等。文件不存在时会自动创建。\n\n使用示例：\n- 创建新文件：{"file_path": "D:/OmniAgentAs-desk/output/result.txt", "text": "Hello World"}\n- 追加到日志：{"file_path": "D:/OmniAgentAs-desk/logs/app.log", "text": "[2026-04-04] Task completed", "append": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - file_path: 写入的文件路径（成功时有值）\n  - bytes_written: 写入字节数（成功时有值）\n  - error: 错误信息（失败时有值）',
    "list_directory": '列出目录内容，包含文件大小、修改时间，支持递归、分页、排序、隐藏文件过滤。\n\n使用场景：\n- 当用户需要查看目录内容及文件大小时使用\n- 当用户想要了解文件夹中哪些文件占用空间较大时使用\n- 当用户需要递归查看子目录时使用\n- 当用户需要分页查看大型目录时使用\n- 当用户需要按名称或大小排序时使用\n- 当用户需要显示隐藏文件时使用\n\n【重要】返回目录中每个文件/目录的名称、路径、类型、大小、修改时间，以及分页信息\n\n使用示例：\n- 基础使用：{"dir_path": "D:/OmniAgentAs-desk"}\n- 递归查看：{"dir_path": "D:/OmniAgentAs-desk", "recursive": true}\n- 按大小排序：{"dir_path": "D:/OmniAgentAs-desk", "sortBy": "size"}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - entries: 条目列表，每项含name/path/type/size/mtime\n  - total: 总条目数\n  - directory: 目录路径\n  - statistics: 统计信息（total_size/dir_count/file_count/sort_by）\n  - truncated: 是否被截断（大目录时为true）\n  - next_page_token: 下一页令牌（分页时有值）\n  - error: 错误信息（失败时有值）',
    "delete_file": '删除文件或目录，默认放入回收站更安全（force=False）。设force=True则永久删除不可恢复。\n\n使用场景：\n- 当用户需要删除文件或目录时使用\n- 当用户需要清理临时文件时使用\n- 当用户确认文件不需要后进行删除时使用\n\n【重要】默认放入回收站更安全，force=True永久删除不可恢复。请谨慎使用force=True\n\n使用示例：\n- 删除文件（进回收站）：{"file_path": "D:/OmniAgentAs-desk/temp/cache.txt"}\n- 永久删除目录：{"file_path": "D:/OmniAgentAs-desk/temp", "recursive": true, "force": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - deleted_path: 已删除的路径（成功时有值）\n  - message: 操作说明（如"文件已放入回收站"或"文件已永久删除"）\n  - error: 错误信息（失败时有值）',
    "move_file": '移动或重命名文件。\n\n使用场景：\n- 当用户需要将文件移动到另一个目录时使用\n- 当用户想要重命名文件时使用\n- 当用户需要整理文件结构时使用\n\n【重要】如果目标位置已存在同名文件且overwrite为false，操作会失败\n\n使用示例：\n- 移动文件：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf"}\n- 覆盖移动：{"source_path": "D:/downloads/report.pdf", "destination_path": "D:/documents/reports/report.pdf", "overwrite": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - source: 源路径（成功时有值）\n  - destination: 目标路径（成功时有值）\n  - message: 操作说明（成功时有值）\n  - error: 错误信息（失败时有值）',
    "search_files": '递归搜索匹配或排除模式的文件/目录，返回完整路径，支持中文文件名搜索。\n\n使用场景：\n- 当用户需要在目录中搜索特定名称的文件时使用\n- 当用户想要查找符合条件的文件时使用\n- 当用户需要对文件进行批量操作前需要找到目标文件时使用\n\n【重要】递归搜索所有子目录，返回所有匹配的文件完整路径\n\n使用示例：\n- 搜索所有 Python 文件：{"search_dir": "D:/OmniAgentAs-desk", "pattern": "**/*.py"}\n- 搜索并排除 node_modules：{"search_dir": "D:/OmniAgentAs-desk", "pattern": "**/*.js", "excludePatterns": ["node_modules"]}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - pattern: 搜索模式\n  - search_dir: 搜索目录\n  - matches: 匹配结果列表，每项含name/path/type/size/mtime\n  - total: 匹配总数\n  - page: 当前页码\n  - total_pages: 总页数\n  - page_size: 每页大小\n  - next_page_token: 下一页令牌（分页时有值）\n  - has_more: 是否有更多结果\n  - error: 错误信息（失败时有值）',
    "generate_report": '生成文件操作报告，记录所有操作历史。\n\n使用场景：\n- 当用户需要回顾文件操作历史时使用\n- 当用户需要生成操作日志报告时使用\n- 当用户需要审计文件操作时使用\n\n\n【重要】返回包含所有文件操作的时间、路径、操作类型的完整报告\n\n使用示例：\n- 生成报告：{"output_dir": "D:/OmniAgentAs-desk/操作报告.txt"}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - task_id: 任务ID（成功时有值）\n  - reports: 报告路径字典（报告类型→文件路径）\n  - error: 错误信息（失败时有值）',
    "copy_file": '复制文件或目录到指定位置。\n\n使用场景：\n- 当用户需要复制文件到另一个位置时使用\n- 当用户想要备份文件时使用\n- 当用户需要创建文件的副本时使用\n\n【重要】如果目标路径已存在文件且 overwrite 为 false，操作会失败\n\n使用示例：\n- 复制文件：{"source_path": "D:/OmniAgentAs-desk/config.yaml", "destination_path": "D:/backup/config.yaml"}\n- 复制目录：{"source_path": "D:/OmniAgentAs-desk/src", "destination_path": "D:/backup/src", "recursive": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - source: 源路径（成功时有值）\n  - destination: 目标路径（成功时有值）\n  - message: 操作说明（成功时有值）\n  - error: 错误信息（失败时有值）',
    "create_directory": '创建新目录，如需要会创建父目录，目录已存在则静默成功。\n\n使用场景：\n- 当用户需要创建新目录时使用\n- 当用户需要创建多级目录时使用\n- 当用户需要在指定位置创建文件夹时使用\n\n【重要】默认情况下会自动创建父目录，且已存在目录不会报错，确保操作幂等性\n\n使用示例：\n- 创建单级目录：{"dir_path": "D:/OmniAgentAs-desk/new_folder"}\n- 创建多级目录：{"dir_path": "D:/OmniAgentAs-desk/output/reports/2026"}\n- 不创建父目录（父目录必须存在）：{"dir_path": "D:/existing_folder/new_folder", "parents": false}\n- 目录已存在时报错：{"dir_path": "D:/existing_folder", "exist_ok": false}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - directory: 创建的目录路径（成功时有值）\n  - message: 操作说明（成功时有值）\n  - error: 错误信息（失败时有值）',
    "get_file_info": '获取文件/目录的详细元数据，包括大小、创建/修改/访问时间、类型、权限。\n\n使用场景：\n- 当用户需要获取文件的详细信息时使用\n- 当用户想要了解文件的大小、修改时间等元数据时使用\n- 当用户需要检查文件类型和权限时使用\n\n【重要】返回文件的完整元数据信息，包括：文件大小（字节）、创建时间、修改时间、访问时间、文件类型、权限标志\n\n使用示例：\n- 获取文件信息：{"file_path": "D:/OmniAgentAs-desk/version.txt"}\n- 不跟随软链接：{"file_path": "D:/OmniAgentAs-desk/shortcut.lnk", "follow_symlinks": false}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - info: 文件信息对象，含path/name/type/size/created_time/modified_time/accessed_time/is_readable/is_writable/is_executable/is_symlink；文件时还有extension/parent_directory；目录时还有file_count/dir_count\n  - error: 错误信息（失败时有值）',
    "compare_files": '比较两个文件的内容/大小/修改时间差异，支持分块比较大文件。\n\n使用场景：\n- 当用户需要比较两个文件是否相同时使用\n- 当用户需要检查文件是否被修改时使用\n- 当用户需要查找两个文件的差异时使用\n\n【重要】支持分块比较，适合大文件。返回比较结果包含差异位置和行数\n\n使用示例：\n- 比较两个文件：{"file_path1": "D:/a.txt", "file_path2": "D:/b.txt"}\n- 分块比较：{"file_path1": "D:/large1.txt", "file_path2": "D:/large2.txt", "chunk_size": 4096}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - comparison: 比较结果对象，含file1/file2/size1/size2/size_match/mtime1/mtime2/mtime_match/identical/algorithm/content_match/comparison_time\n  - error: 错误信息（失败时有值）',
    "batch_rename": '批量重命名文件（正则匹配），支持预览、冲突处理。\n\n使用场景：\n- 当用户需要批量重命名文件时使用\n- 当用户需要按规则统一修改文件名时使用\n- 当用户需要重命名多个文件时使用\n\n【重要】首次执行建议preview=true先预览，确认无误后再执行\n\n使用示例：\n- 预览模式：{"directory": "D:/files", "pattern": "(.*)\\.txt", "replacement": "$1_backup.txt", "preview": true}\n- 执行重命名：{"directory": "D:/files", "pattern": "(.*)\\.txt", "replacement": "$1_backup.txt", "preview": false}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID\n  - directory/pattern/replacement/use_regex/recursive/preview_mode/conflict_strategy: 操作参数\n  - total_files: 总文件数\n  - renamed_files: 已重命名数\n  - skipped_files: 跳过数\n  - failed_files: 失败数\n  - operations: 操作详情列表，每项含file/original_name/new_name/status/reason/new_path/conflict_resolved\n  - error: 错误信息（失败时有值）',
    "compress_files": '压缩文件或目录为zip/tar.gz，支持加密（password）和分卷（split_size）。\n\n使用场景：\n- 当用户需要压缩文件或目录时使用\n- 当用户需要打包多个文件时使用\n- 当用户需要创建备份时使用\n\n【重要】支持任意类型文件，支持加密和分卷\n\n使用示例：\n- 压缩目录：{"source_path": "D:/docs", "output_path": "D:/backup/docs.zip"}\n- 加密压缩：{"source_path": "D:/docs", "output_path": "D:/backup/docs.zip", "password": "mypassword"}\n- 分卷压缩：{"source_path": "D:/large", "output_path": "D:/backup/large.zip", "split_size": "100m"}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - source_path/destination_path/format/compression_level/encrypted: 压缩参数\n  - original_size: 原始大小（字节）\n  - compressed_size: 压缩后大小（字节）\n  - compression_ratio: 压缩率\n  - compressed_files: 被压缩的文件列表\n  - file_count: 文件数量\n  - error: 错误信息（失败时有值）',
    "file_monitor": '监控目录文件变化（创建/修改/删除/重命名事件），支持递归监控、过滤条件、限时监控。\n\n使用场景：\n- 当用户需要监控目录文件变化时使用\n- 当用户需要监听文件创建/修改/删除事件时使用\n- 当用户需要实时了解目录变化时使用\n\n【重要】支持递归监控、多种事件类型过滤\n\n使用示例：\n- 监控目录：{"directory": "D:/watch", "duration": 60}\n- 监控修改事件：{"directory": "D:/watch", "event_types": ["modify"], "duration": 30}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - directory/event_types/recursive/filters/duration: 监控参数\n  - actual_duration: 实际监控时长\n  - events_count: 检测到的事件数\n  - events: 事件列表（最多100条），每项含event_type/file_path/timestamp/size/is_directory\n  - error: 错误信息（失败时有值）',
    "file_statistics": '统计目录的文件数量、总大小、类型分布，支持递归统计、过滤条件、多种输出格式。\n\n使用场景：\n- 当用户需要统计目录文件数量时使用\n- 当用户需要了解目录大小分布时使用\n- 当用户需要按文件类型统计存储空间时使用\n\n【重要】返回目录的文件数量、总大小、类型分布\n\n使用示例：\n- 统计目录：{"directory": "D:/docs"}\n- JSON格式输出：{"directory": "D:/docs", "output_format": "json"}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - directory: 统计目录\n  - total_files/total_directories/total_size/average_file_size: 统计汇总\n  - file_types: 文件类型分布字典\n  - size_distribution: 大小分布（0-1KB/1KB-1MB/1MB-10MB/10MB-100MB/100MB-1GB/1GB+）\n  - modification_time_distribution: 修改时间分布（today/this_week/this_month/this_year/older）\n  - depth_distribution: 深度分布\n  - files: 文件详情列表（最多1000条）\n  - scan_time: 扫描耗时\n  - output: 格式化输出字符串\n  - error: 错误信息（失败时有值）',
    "file_checksum": '计算文件的MD5/SHA1/SHA256/SHA512哈希值，用于校验文件完整性。\n\n使用场景：\n- 当用户需要计算文件哈希值时使用\n- 当用户需要校验文件完整性时使用\n- 当用户需要验证下载文件是否被篡改时使用\n\n【重要】支持分块计算大文件，返回哈希值可用于完整性校验\n\n使用示例：\n- 计算SHA256：{"file_path": "D:/downloads/file.zip"}\n- 验证完整性：{"file_path": "D:/downloads/file.zip", "algorithm": "sha256", "verify_hash": "abc123..."}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - operation_id: 操作ID（成功时有值）\n  - algorithm: 哈希算法\n  - checksum: 哈希值\n  - file_size: 文件大小\n  - verification_status: 验证状态（"passed"/"failed"/"not_verified"）\n  - message: 操作说明\n  - error: 错误信息（失败时有值）',
    "extract_archive": '解压zip、tar、gz压缩文件，支持密码解压、覆盖、权限保留。\n\n使用场景：\n- 当用户需要解压压缩文件时使用\n- 当用户需要提取压缩包中的文件时使用\n- 当用户需要访问zip/tar.gz压缩包内容时使用\n\n【重要】支持zip/tar/gz格式，支持加密压缩包\n\n使用示例：\n- 解压ZIP：{"archive_path": "D:/backup/docs.zip"}\n- 解压到指定目录：{"archive_path": "D:/backup/docs.zip", "output_dir": "D:/extract/docs"}\n- 覆盖解压：{"archive_path": "D:/backup/docs.zip", "overwrite": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - output_dir: 解压输出目录（成功时有值）\n  - extracted_files: 已解压文件数（成功时有值）\n  - skipped_files: 跳过文件数（成功时有值）\n  - format: 压缩格式（zip/tar.gz/tar.bz2/tar）\n  - error: 错误信息（失败时有值）',
    "get_file_hash": '计算文件的MD5/SHA1/SHA256/SHA512哈希值，支持大文件、哈希比对。\n\n使用场景：\n- 当用户需要计算文件哈希值时使用\n- 当用户需要校验文件完整性时使用\n- 当用户需要验证下载文件是否被篡改时使用\n- 当用户需要比对两个文件的哈希值时使用\n\n【重要】支持大文件分块计算，返回哈希值可用于完整性校验\n\n使用示例：\n- 计算SHA256：{"file_path": "D:/downloads/file.zip"}\n- 验证完整性：{"file_path": "D:/downloads/file.zip", "verify_against": "abc123..."}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - file_path: 文件路径（成功时有值）\n  - algorithm: 哈希算法\n  - hash: 哈希值（成功时有值）\n  - file_size: 文件大小（成功时有值）\n  - error: 错误信息（失败时有值）',
    "read_text_file": '读取文本文件的完整内容，始终以 UTF-8 编码处理文件，支持中文等多字节字符。仅支持文本文件，禁止读取二进制文件。\n\n使用场景：\n- 当用户需要查看文本文件的内容时使用\n- 当用户想要读取配置文件、日志文件、代码文件等文本内容时使用\n- 当用户需要获取文件的前几行或后几行时使用\n\n【重要】本工具仅支持文本文件，禁止读取二进制文件。禁止的后缀：.png/.jpg/.jpeg/.gif/.zip/.exe/.dll/.docx/.xlsx/.pptx/.pdf/.mp3/.mp4/.wav/.avi/.mkv等。若需读取媒体文件（图片/音频），请使用read_media_file工具。\n\n使用示例：\n- 读取全部内容：{"file_path": "D:/OmniAgentAs-desk/backend/app/main.py"}\n- 只读取前10行：{"file_path": "D:/OmniAgentAs-desk/backend/app/services/agent.py", "head": 10}\n- 只读取最后5行：{"file_path": "D:/OmniAgentAs-desk/logs/app.log", "tail": 5}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - content: 文件内容字符串（成功时有值）\n  - total_lines: 文件总行数\n  - line_count: 返回的行数\n  - encoding: 实际使用的编码\n  - file_size: 文件大小（字节）\n  - head/tail/offset/limit: 读取参数（按实际使用返回）\n  - error: 错误信息（失败时有值）',
    "read_media_file": '读取图片或音频文件，返回 Base64 编码的数据和对应的 MIME 类型。\n\n使用场景：\n- 当用户需要获取图片或音频文件的内容时使用\n- 当用户想要将媒体文件转换为 Base64 字符串以便传输或嵌入时使用\n- 当用户需要查看媒体文件的 MIME 类型时使用\n\n【重要】返回 Base64 编码的媒体数据和 MIME 类型，适用于图片（JPG、PNG、GIF等）和音频（MP3、WAV等）文件\n\n使用示例：\n- 读取图片：{"file_path": "D:/OmniAgentAs-desk/docs/screenshot.png"}\n- 读取音频：{"file_path": "D:/OmniAgentAs-desk/audio/notification.mp3"}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - data: Base64编码的媒体数据（成功时有值）\n  - mime_type: MIME类型（成功时有值）\n  - file_name: 文件名（成功时有值）\n  - file_size: 文件大小（字节，成功时有值）\n  - error: 错误信息（失败时有值）',
    "read_batch_file": '同时读取多个文件的内容，单个文件读取失败不会中断整个操作。仅支持文本文件，Agent会自动跳过二进制文件并提示。\n\n使用场景：\n- 当用户需要同时读取多个文件进行分析或对比时使用\n- 当用户想要批量获取多个配置文件内容时使用\n- 当用户需要快速了解多个相关文件的内容时使用\n\n【重要】本工具仅支持文本文件，禁止读取二进制文件。禁止的后缀：.png/.jpg/.jpeg/.gif/.zip/.exe/.dll/.docx/.xlsx/.pptx/.pdf/.mp3/.mp4/.wav等。Agent会自动检测文件类型，跳过二进制文件并返回提示信息。\n\n使用示例：\n- 读取2个文件：{"file_paths": ["D:/OmniAgentAs-desk/backend/app/main.py", "D:/OmniAgentAs-desk/backend/app/config.py"]}\n- 读取配置文件：{"file_paths": ["D:/OmniAgentAs-desk/config.yaml", "D:/OmniAgentAs-desk/.env"]}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool，至少一个文件成功即为true）\n  - results: 各文件结果列表，每项含file_path/success/content/encoding/file_size/error\n  - total: 总文件数\n  - success_count: 成功数\n  - failed_count: 失败数',
    "precise_replace_in_file": '执行精确的字符串替换，支持中文内容精确匹配和替换。仅支持文本文件，禁止编辑二进制文件。\n\n使用场景：\n- 当用户需要精确替换文件中特定的字符串时使用\n- 当用户需要对代码进行精确修改时使用\n- 当用户需要在文件中替换特定的文本内容时使用\n\n【重要】仅支持文本文件，二进制文件（.png/.jpg/.zip/.exe等）将被拒绝\n\n使用示例：\n- 替换单个：{"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "old_string": "def old_func():", "new_string": "def new_func():"}\n- 替换全部：{"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "old_string": "print(\\"debug\\")", "new_string": "# print(\\"debug\\")", "replace_all": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - replaced_count: 替换次数（成功时有值）\n  - encoding: 实际使用的编码（成功时有值）\n  - file_path: 文件路径（成功时有值）\n  - file_name: 文件名（成功时有值）\n  - operation_id: 操作ID（成功时有值）\n  - error: 错误信息（失败时有值）',
    "edit_text_file": '使用高级模式匹配进行选择性编辑，支持多同时编辑、缩进保留、dryRun 预览。仅支持文本文件，禁止编辑二进制文件（.png/.jpg/.zip/.exe等）。\n\n使用场景：\n- 当用户需要同时对文件进行多处编辑时使用\n- 当用户想要先预览修改效果再实际执行时使用\n- 当用户需要对代码文件进行批量修改时使用\n\n【重要】仅支持文本文件编辑，二进制文件（.png/.jpg/.zip/.exe/.docx/.xlsx/.pdf/.mp3等）将被拒绝并提示使用专业工具\n\n使用示例：\n- 单次编辑：{"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "def old():", "newText": "def new():"}]}\n- 多次编辑：{"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "import os", "newText": "import os\\nimport sys"}, {"oldText": "def foo():", "newText": "def bar():"}]}\n- 预览模式：{"file_path": "D:/OmniAgentAs-desk/backend/app/main.py", "edits": [{"oldText": "old", "newText": "new"}], "dryRun": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - applied_edits: 成功应用的编辑数（成功时有值）\n  - total_edits: 总编辑数（成功时有值）\n  - results: 各编辑结果列表，每项含index/success/old_text/new_text/error\n  - preview: 预览内容（dryRun=true时有值）\n  - dry_run: 是否预览模式\n  - encoding: 实际使用的编码\n  - operation_id: 操作ID（成功时有值）\n  - error: 错误信息（失败时有值）',
    "rename_file": '重命名文件或目录，不改变所在目录。\n\n使用场景：\n- 当用户需要重命名文件时使用\n- 当用户想要重命名目录时使用\n- 当用户需要修改文件名但保持文件位置不变时使用\n\n【重要】只改变名称，不改变所在目录。如果新名称与同目录已有文件重名，操作会失败\n\n使用示例：\n- 重命名文件：{"file_path": "D:/documents/report_old.txt", "new_name": "report_final.txt"}\n- 重命名目录：{"file_path": "D:/projects/old_folder", "new_name": "new_folder"}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - new_path: 新路径（成功时有值）\n  - old_path: 原路径（成功时有值）\n  - old_name: 原名称（成功时有值）\n  - new_name: 新名称（成功时有值）\n  - operation_id: 操作ID（成功时有值）\n  - error: 错误信息（失败时有值）',
    "grep_file_content": '基于 ripgrep 的强大内容搜索，支持正则表达式和多选项，支持 Unicode 中文字符搜索。\n\n使用场景：\n- 当用户需要在文件中搜索特定内容时使用\n- 当用户想要查找包含特定关键词的代码行时使用\n- 当用户需要对多个文件进行内容搜索时使用\n\n【重要】支持强大的正则表达式搜索，可以精确定位代码中的内容\n\n使用示例：\n- 简单搜索：{"pattern": "def read_file", "search_dir": "D:/OmniAgentAs-desk/backend"}\n- 搜索TS文件中的class：{"pattern": "class.*Component", "search_dir": "D:/OmniAgentAs-desk/frontend", "glob": "*.tsx", "ignore_case": true}\n- 带上下文搜索：{"pattern": "async def.*tool", "search_dir": "D:/OmniAgentAs-desk/backend", "context_lines": 3, "show_line_no": true}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - matches: 匹配结果列表，每项含file/matches/match_count（content模式）或file/count（count模式）或file（files_with_matches模式）\n  - total_files: 匹配文件总数\n  - total_matches: 匹配总行数\n  - pattern: 搜索模式\n  - search_dir: 搜索目录\n  - output_mode: 输出模式\n  - has_more: 是否有更多结果\n  - next_page_token: 下一页令牌（分页时有值）\n  - error: 错误信息（失败时有值）',
    "get_directory_tree": '获取目录的递归 JSON 树结构，每个条目包含 name、type（file/directory）、children。\n\n使用场景：\n- 当用户需要查看完整目录树结构时使用\n- 当用户想要了解项目的整体文件结构时使用\n- 当用户需要生成目录树视图时使用\n\n【重要】返回 JSON 格式的目录树结构，包含每个文件/目录的名称、类型、子目录（仅目录有 children 字段）\n\n使用示例：\n- 获取完整树：{"dir_path": "D:/OmniAgentAs-desk"}\n- 排除 node_modules：{"dir_path": "D:/OmniAgentAs-desk", "excludePatterns": ["node_modules", "__pycache__"]}\n\n返回数据说明：\n- status: 执行状态（"success"/"error"）\n- summary: 操作摘要描述\n- data: 结果数据对象\n  - success: 是否成功（bool）\n  - tree: 目录树对象，递归结构，每项含name/type；目录有children字段\n  - root: 根目录路径（成功时有值）\n  - error: 错误信息（失败时有值）',
    "list_allowed_directories": """列出服务器允许访问的所有目录。

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要确认可以访问哪些目录时使用
- 当用户想要了解系统允许的文件操作范围时使用
- 当用户需要检查是否有权限访问特定目录时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"path": "D:/xxx"}  # 不要传任何参数！

返回数据说明：
- status: 执行状态（"success"/"error"）
- summary: 操作摘要描述
- data: 结果数据对象
  - success: 是否成功（bool）
  - directories: 目录列表，每项含path/exists/type
  - total: 目录总数
  - error: 错误信息（失败时有值）""",
}


# 【小沈 2026-04-29】补充 examples 参数 - 17个工具的使用示例

FILE_TOOL_EXAMPLES = {
    "write_text_file": [
        {"file_path": "C:/Users/用户名/Documents/test.txt", "text": "Hello World"},
        {
            "file_path": "D:/项目代码/config.json",
            "text": '{"key": "value"}',
            "encoding": "utf-8",
        },
        {
            "file_path": "D:/项目代码/logs/app.log",
            "text": "新增日志行\\n",
            "append": True,
        },
    ],
    "list_directory": [
        {"dir_path": "C:/Users/用户名/Documents"},
        {"dir_path": "D:/项目代码", "recursive": True, "max_depth": 3},
    ],
    "delete_file": [
        {"file_path": "C:/Users/用户名/Documents/temp.txt"},
        {"file_path": "D:/项目代码/logs/app.log"},
    ],
    "move_file": [
        {
            "source_path": "C:/Users/用户名/Desktop/old.txt",
            "destination_path": "C:/Users/用户名/Documents/new.txt",
        },
        {"source_path": "D:/项目代码/a.txt", "destination_path": "D:/项目代码/b.txt"},
    ],
    "search_files": [
        {"pattern": "*.py", "search_dir": "D:/项目代码"},
        {"pattern": "config*", "search_dir": "C:/Users/用户名/Documents"},
    ],
    "generate_report": [
        {"output_dir": "D:/项目代码"},
        {"output_dir": "C:/Users/用户名/Documents"},
    ],
    "copy_file": [
        {
            "source_path": "C:/Users/用户名/Documents/source.txt",
            "destination_path": "C:/Users/用户名/Documents/dest.txt",
        },
        {"source_path": "D:/项目代码/a.py", "destination_path": "D:/项目代码/b.py"},
    ],
    "create_directory": [
        {"dir_path": "C:/Users/用户名/Documents/新文件夹"},
        {"dir_path": "D:/项目代码/src/components"},
    ],
    "get_file_info": [
        {"file_path": "C:/Users/用户名/Documents/config.json"},
        {"file_path": "D:/项目代码/main.py"},
    ],
    "compare_files": [
        {
            "file_path1": "C:/Users/用户名/Documents/a.txt",
            "file_path2": "C:/Users/用户名/Documents/b.txt",
        },
        {
            "file_path1": "D:/项目代码/v1.py",
            "file_path2": "D:/项目代码/v2.py",
            "algorithm": "content",
        },
    ],
    "batch_rename": [
        {
            "directory": "C:/Users/用户名/Documents",
            "pattern": "*.txt",
            "replacement": "新文件_",
        },
        {"directory": "D:/项目代码", "pattern": "old_", "replacement": "new_"},
    ],
    "compress_files": [
        {
            "source_path": "C:/Users/用户名/Documents/a.txt",
            "output_path": "C:/Users/用户名/Documents/archive.zip",
        },
        {
            "source_path": "D:/项目代码/src",
            "output_path": "D:/项目代码/code.zip",
            "format": "zip",
            "compression_level": 6,
        },
        {
            "source_path": "D:/项目代码",
            "output_path": "D:/backup/bak.tar.gz",
            "format": "tar.gz",
            "exclude_patterns": ["node_modules", "__pycache__"],
            "overwrite": False,
        },
    ],
    "file_monitor": [
        {
            "directory": "C:/Users/用户名/Documents",
            "event_types": ["created", "modified"],
        },
        {"directory": "D:/项目代码", "event_types": ["deleted"]},
    ],
    "file_statistics": [
        {"directory": "C:/Users/用户名/Documents"},
        {"directory": "D:/项目代码", "filters": {"file_type": ["*.py", "*.js"]}},
    ],
    "file_checksum": [
        {"file_path": "C:/Users/用户名/Documents/data.zip", "algorithm": "md5"},
        {
            "file_path": "D:/项目代码/main.py",
            "algorithm": "sha256",
            "verify_hash": "abc123...",
        },
    ],
    "extract_archive": [
        {"archive_path": "C:/Users/用户名/Documents/archive.zip"},
        {"archive_path": "D:/backup/docs.zip", "output_dir": "D:/extract/docs"},
        {"archive_path": "D:/backup/docs.zip", "overwrite": True, "password": "mypassword"},
    ],
    "get_file_hash": [
        {"file_path": "C:/Users/用户名/Documents/data.zip", "algorithm": "md5"},
        {
            "file_path": "D:/项目代码/main.py",
            "algorithm": "sha256",
            "verify_against": "abc123...",
        },
    ],
    "read_text_file": [
        {"file_path": "D:/OmniAgentAs-desk/backend/app/main.py"},
        {"file_path": "D:/OmniAgentAs-desk/backend/app/services/agent.py", "head": 10},
        {"file_path": "D:/OmniAgentAs-desk/logs/app.log", "tail": 5},
    ],
    "read_media_file": [
        {"file_path": "D:/OmniAgentAs-desk/docs/screenshot.png"},
        {"file_path": "D:/OmniAgentAs-desk/audio/notification.mp3"},
    ],
    "read_batch_file": [
        {
            "file_paths": [
                "D:/OmniAgentAs-desk/backend/app/main.py",
                "D:/OmniAgentAs-desk/backend/app/config.py",
            ]
        },
        {"file_paths": ["D:/OmniAgentAs-desk/config.yaml", "D:/OmniAgentAs-desk/.env"]},
    ],
    "precise_replace_in_file": [
        {
            "file_path": "D:/OmniAgentAs-desk/backend/app/main.py",
            "old_string": "def old_func():",
            "new_string": "def new_func():",
        },
        {
            "file_path": "D:/OmniAgentAs-desk/backend/app/main.py",
            "old_string": 'print("debug")',
            "new_string": '# print("debug")',
            "replace_all": True,
        },
    ],
    "edit_text_file": [
        {
            "file_path": "D:/OmniAgentAs-desk/backend/app/main.py",
            "edits": [{"oldText": "def old():", "newText": "def new():"}],
        },
        {
            "file_path": "D:/OmniAgentAs-desk/backend/app/main.py",
            "edits": [{"oldText": "import os", "newText": "import os\nimport sys"}],
            "dryRun": True,
        },
    ],
    "rename_file": [
        {"file_path": "D:/documents/report_old.txt", "new_name": "report_final.txt"},
        {"file_path": "D:/projects/old_folder", "new_name": "new_folder"},
    ],
    "grep_file_content": [
        {"pattern": "def read_file", "search_dir": "D:/OmniAgentAs-desk/backend"},
        {
            "pattern": "class.*Component",
            "search_dir": "D:/OmniAgentAs-desk/frontend",
            "glob": "*.tsx",
            "ignore_case": True,
        },
    ],
    "get_directory_tree": [
        {"dir_path": "D:/OmniAgentAs-desk"},
        {
            "dir_path": "D:/OmniAgentAs-desk",
            "excludePatterns": ["node_modules", "__pycache__"],
        },
    ],
    "list_allowed_directories": [{}],
}


# ============================================================
# 工具名到 Pydantic 模型的映射（模块级别，供 __all__ 导出）
# ============================================================
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
    "extract_archive": ExtractArchiveInput,
    "get_file_hash": GetFileHashInput,
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
    # 【修复 2026-05-07 小沈】lambda必须接受**kwargs并转发给实际方法，否则执行器传参报错

    tool_methods = {
        "write_text_file": lambda **kw: _get_ft().write_text_file(**kw),
        "list_directory": lambda **kw: _get_ft().list_directory(**kw),
        "delete_file": lambda **kw: _get_ft().delete_file(**kw),
        "move_file": lambda **kw: _get_ft().move_file(**kw),
        "search_files": lambda **kw: _get_ft().search_files(**kw),
        "generate_report": lambda **kw: _get_ft().generate_report(**kw),
        "copy_file": lambda **kw: _get_ft().copy_file(**kw),
        "create_directory": lambda **kw: _get_ft().create_directory(**kw),
        "get_file_info": lambda **kw: _get_ft().get_file_info(**kw),
        "compare_files": lambda **kw: _get_ft().compare_files(**kw),
        "batch_rename": lambda **kw: _get_ft().batch_rename(**kw),
        "compress_files": lambda **kw: _get_ft().compress_files(**kw),
        "extract_archive": lambda **kw: _get_ft().extract_archive(**kw),
        "get_file_hash": lambda **kw: _get_ft().get_file_hash(**kw),
        "file_monitor": lambda **kw: _get_ft().file_monitor(**kw),
        "file_statistics": lambda **kw: _get_ft().file_statistics(**kw),
        "file_checksum": lambda **kw: _get_ft().file_checksum(**kw),
        "read_text_file": lambda **kw: _get_ft().read_text_file(**kw),
        "read_media_file": lambda **kw: _get_ft().read_media_file(**kw),
        "read_batch_file": lambda **kw: _get_ft().read_batch_file(**kw),
        "precise_replace_in_file": lambda **kw: _get_ft().precise_replace_in_file(**kw),
        "edit_text_file": lambda **kw: _get_ft().edit_file(**kw),
        "rename_file": lambda **kw: _get_ft().rename_file(**kw),
        "grep_file_content": lambda **kw: _get_ft().grep_file_content(**kw),
        "get_directory_tree": lambda **kw: _get_ft().get_directory_tree(**kw),
        "list_allowed_directories": lambda **kw: _get_ft().list_allowed_directories(**kw),
    }

    # 【2026-04-29 小沈新增】工具名到 Pydantic 模型的映射（按文档5.1设计）

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
            examples=examples,  # 【小沈 2026-04-29】补充 examples 参数
        )

        logger.info(
            f"[file_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个"
        )


# 触发注册

# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_file_tools"]


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
