# -*- coding: utf-8 -*-
"""
File Schema - 文件工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容

Author: 小沈 - 2026-03-21
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union


# ============================================================
# F1: readtext — 读取文本文件
# ============================================================

# ⚠️ Pydantic class docstring 会进入 JSON Schema 的 parameters.description 并发给 LLM
# 禁止在这里写文档字符串。工具描述写在 file_register.py 的 FILE_TOOL_DESCRIPTIONS 里。
class ReadtextInput(BaseModel):
    """
     不支持office类型.docx/.xlsx/.pptx/.PDF文件和媒体文件读取
    【四种模式】
    1. 读全文: 不传offset/limit/tail
    2. 前N行: 只传limit（如limit=100读前100行）
    3. 尾部N行: 只传tail（如tail=20读最后20行）
    4. 分页: offset+limit（如offset=10, limit=20读第10-29行）

    【互斥规则】
    - tail不能与offset/limit同时使用

    【示例】
    - 不传参数: 读全文
    - limit=100: 读前100行
    - tail=20: 读最后20行
    - offset=10, limit=20: 读第10-29行"""
    file_path: str = Field(
        description="要读取的文件路径(绝对路径)。支持文本文件:txt/md/py/js/ts/json/yaml/yml/xml/html/css/csv/log等"
    )
    offset: Optional[int] = Field(
        default=None,
        ge=1,
        description="""起始行号(1-indexed)，必须配合limit使用。

【示例】
- offset=1, limit=100: 读第1-100行
- offset=10, limit=20: 读第10-29行"""
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000000,
        description="""读取行数。

【三种模式】
1. 只传limit: 读前limit行（如limit=100读前100行）
2. offset+limit: 分页模式（如offset=10, limit=20读第10-29行）
3. tail: 读尾部N行（不能与offset/limit同时使用）"""
    )
    tail: Optional[int] = Field(
        default=None,
        ge=1,
        description="""读取尾部N行。

【重要】tail不能与offset/limit同时使用！

【示例】
- tail=20: 读最后20行
- tail=100: 读最后100行"""
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码,默认utf-8。读取失败时自动尝试gbk/gb2312/utf-8-sig"
    )



# ============================================================
# F2: writetext — 写文本文件
# ============================================================

class WritetextInput(BaseModel):
    """不支持office类型.docx/.xlsx/.pptx/.PDF文件和媒体文件写入"""
    file_path: str = Field(
        description="文件的完整路径(绝对路径,支持中文路径)。用于写入文本文件:txt/md/py/js/ts/json/yaml/yml/xml/html/css/csv/log等"
    )
    content: str = Field(
        description="""要写入文件的文本内容。

【格式要求】
- 类型: 必须是字符串(string)，不支持dict/list/object
- 换行: 使用\\n表示换行
- 特殊字符: 双引号用\\"表示，反斜杠用\\\\表示

【长度限制】
- 建议: 单次调用不超过2000字符(避免LLM输出截断)
- 超过2000字符: 建议分多次调用(第一次append=False，后续append=True)
- 最大: 10000字符

【示例】
- 单行: "Hello World"
- 多行: "第一行\\n第二行\\n第三行"
- JSON: "{\\"key\\": \\"value\\"}" """,
        max_length=10000
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。追加时检测已有文件编码,新建时默认utf-8。也可指定gbk/gb2312等"
    )
    append: bool = Field(
        default=False,
        description="是否追加写入。True=追加,False=覆盖"
    )


# ============================================================
# F3: readmedia — 读媒体文件
# ============================================================

class ReadmediaInput(BaseModel):
    """不支持PDF文件(请用read_pdf)"""
    file_path: str = Field(
        description="媒体文件的完整路径。支持图片(JPG/PNG/GIF/BMP/WebP/SVG/ICO/TIFF)、音频(MP3/WAV/OGG/M4A/FLAC/AAC)、视频(MP4/AVI/MOV/MKV)。返回Base64编码数据"
    )


# ============================================================
# F4: edittext — 编辑文本文件
# ============================================================

class EdittextInput(BaseModel):
    """edit工具的替换模式说明:
    mode="once"   -- 只替换第一个匹配的old_string
    mode="all"    -- 替换全部匹配的old_string
    mode="before" -- 在唯一锚点前插入
    mode="after"  -- 在唯一锚点后插入"""
    file_path: str = Field(
        description="目标文件的绝对路径(仅支持文本文件)"
    )
    old_string: str = Field(
        description="定位锚点字符串"
    )
    new_string: str = Field(
        default="",
        description="替换/插入的字符串。mode=once时传空字符串''表示删除匹配文本"
    )
    mode: str = Field(
        default="once",
        description="操作模式: once(只替换第一个), all(替换全部), before(在锚点前插入), after(在锚点后插入)"
    )
    ignore_case: bool = Field(
        default=False,
        description="是否忽略大小写,默认False"
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码,默认自动检测"
    )



# ============================================================
# F5a: listdir — 列出目录内容
# ============================================================

class ListdirInput(BaseModel):
    """支持offset参数分页遍历大目录(每页最多500项)"""
    dir_path: str = Field(
        description="目录路径(绝对路径,必填)。如 D:/项目代码"
    )
    sort_by: Literal["name", "size", "mtime"] = Field(
        default="name",
        description="排序方式:name/size/mtime,默认name"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件(以.开头的文件),默认False"
    )
    offset: int = Field(
        default=0,
        description="分页偏移量,用于跳过前N项。仅返回第offset项开始的500项,支持分页遍历大目录"
    )


# ============================================================
# F5b: tree — 列出目录树
# ============================================================

class TreeInput(BaseModel):
    """可设max_depth控制深度(默认5层,大目录如node_modules建议设3以下)"""
    dir_path: str = Field(
        description="目录路径(绝对路径,必填)。如 D:/项目代码"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件(以.开头的文件),默认False"
    )
    max_depth: int = Field(
        default=5,
        ge=1, le=20,
        description="树的最大深度(1~20),默认5层"
    )
    sort_by: Literal["name", "mtime"] = Field(
        default="name",
        description="排序方式:name/mtime(不支持size排序),默认name"
    )


# ============================================================
# F6: search_files — 搜索文件名
# ============================================================

class FindInput(BaseModel):
    """支持offset参数分页遍历大量搜索结果(每页最多500条)"""
    pattern: str = Field(
        description="文件名匹配模式,支持glob通配符(* ? **)和中文文件名。如 \"*.py\""
    )
    search_dir: str = Field(
        description="搜索的起始目录(绝对路径,必填)。如 D:/项目代码"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写,默认True"
    )
    type: Optional[Literal["file", "directory"]] = Field(
        default=None,
        description="搜索类型过滤:file=只返回文件,directory=只返回目录,不设则全部返回"
    )
    offset: int = Field(
        default=0,
        description="分页偏移量,用于跳过前N条结果。仅返回第offset条开始的500条,支持分页遍历大量搜索结果"
    )


# ============================================================
# F7: grep_file_content — 搜索文件内容
# ============================================================

class GrepInput(BaseModel):
    """使用技巧:
- pattern 支持正则如 \"def \\w+\" 匹配函数定义
- glob 可限制文件类型如 \"*.py\"
- output_mode=\"only_files\" 只返回文件名列表,节省token
- 结果按文件修改时间降序排列,最新修改的文件在最前"""
    pattern: str = Field(
        description="正则表达式搜索模式,支持中文内容搜索。如 \"def read_file\""
    )
    path: str = Field(
        description="搜索目录(绝对路径,必填)"
    )
    glob: Optional[str] = Field(
        default=None,
        description="文件过滤(glob通配符),如 \"*.py\""
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写,默认True"
    )
    literal: bool = Field(
        default=False,
        description="是否按纯文本精确搜索,默认False(正则模式)。搜索带正则特殊字符的字符串时设为True,如 \"foo.bar()\" \"arr[0]\" \"price$\",会自动转义 . ( ) [ ] * + ? $ 等字符"
    )
    context: int = Field(
        default=0, ge=0, le=10,
        description="返回匹配行前后各N行上下文,默认0,上限10。仅output_mode=content生效,其余模式忽略。用于查看匹配代码的上下文"
    )
    output_mode: Literal["content", "count", "only_files"] = Field(
        default="content",
        description="输出模式: content=返回匹配内容(默认), count=只返回匹配数量, only_files=只返回含匹配的文件名列表(节省token)"
    )



# ============================================================
# F8: compress_files — 压缩文件
# ============================================================

class CompressInput(BaseModel):
    source: str = Field(description="要压缩的文件/目录路径(绝对路径),支持通配符如*.txt")
    destination: str = Field(description="输出压缩包路径(绝对路径,必填)")
    format: Literal["zip", "tar", "tar.gz", "tar.bz2"] = Field(
        default="zip", description="压缩格式:zip/tar/tar.gz/tar.bz2,默认zip"
    )

    password: Optional[str] = Field(default=None, description="ZIP加密密码,设置后创建AES-256加密ZIP,仅ZIP格式支持,可选")
    overwrite: bool = Field(default=False, description="是否覆盖已存在文件,默认False")
    exclude_patterns: Optional[List[str]] = Field(
        default=None, description="排除的文件/目录模式列表,如 ['node_modules', '__pycache__']"
    )


# ============================================================
# F8b: extract_archive — 解压文件
# ============================================================

class ExtractInput(BaseModel):
    source: str = Field(description="压缩包路径(绝对路径,必填)。支持格式:zip/tar/tar.gz/tar.bz2")
    destination: Optional[str] = Field(
        default=None, description="解压目标目录(绝对路径,可选,默认自动创建同名目录)"
    )
    password: Optional[str] = Field(default=None, description="解密密码(仅ZIP格式支持),可选")
    overwrite: bool = Field(default=False, description="是否覆盖已存在文件,默认False")


# ============================================================
# F9a: move_file — 移动文件
# ============================================================

class MoveInput(BaseModel):
    source: str = Field(description="源文件路径(绝对路径)")
    destination: str = Field(description="目标路径(绝对路径)")
    overwrite: bool = Field(default=False, description="是否覆盖目标文件,默认False")


# ============================================================
# F9b: copy_file — 复制文件
# ============================================================

class CopyInput(BaseModel):
    source: str = Field(description="源文件路径(绝对路径)")
    destination: str = Field(description="目标路径(绝对路径)")
    recursive: bool = Field(default=False, description="复制目录时需True,默认False")
    overwrite: bool = Field(default=False, description="是否覆盖目标文件,默认False")
    preserve_metadata: bool = Field(default=True, description="是否保留文件元数据(修改时间等),默认True")



# ============================================================
# F9c: delete_file — 删除文件
# ============================================================

class DeleteInput(BaseModel):
    source: str = Field(description="要删除的文件/目录路径(绝对路径)")
    recursive: bool = Field(default=False, description="删除非空目录时需True,默认False")
    force: bool = Field(default=False, description="True=跳过回收站永久删除,False=放入回收站。默认False")


# ============================================================
# F9d: rename_file — 重命名文件
# ============================================================

class RenameInput(BaseModel):
    source: str = Field(min_length=1, description="原文件/目录路径(绝对路径)")
    destination: str = Field(min_length=1, description="新名称(仅文件名,不含目录路径)")


# ============================================================
# ============================================================
# __all__ — 13个工具的Schema导出
# ============================================================

__all__ = [
    "ReadtextInput",
    "WritetextInput",
    "ReadmediaInput",
    "EdittextInput",
    "ListdirInput",
    "TreeInput",
    "FindInput",
    "GrepInput",
    "CompressInput",
    "ExtractInput",
    "MoveInput",
    "CopyInput",
    "DeleteInput",
    "RenameInput",
]
