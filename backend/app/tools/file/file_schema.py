
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - RenameInput新增overwrite字段(默认False): 配合rename工具支持覆盖, 对齐move/copy/compress/extract(根因: rename原硬编码overwrite=False且不暴露该参数, 目标已存在时LLM无法用overwrite=True纠正); 按铁规禁止向后兼容, 此处为新增可选参数(默认False保持原行为), 非兼容旧接口
# 2026-07-15 - 小欧 - 常量归一化治理: WritetextInput.content 入参校验上限改引用 tool_constants.WRITE_TEXT_MAX_CHARS(原 max_length=10000), 功能零退化
# 2026-07-20 - 小欧 - GrepInput 类 docstring 改为仅写工具级默认能力(不重复字段描述);为 CompressInput/ExtractInput/MoveInput 补工具级默认能力 docstring(目录默认递归压缩/解压/移动)
# 2026-07-20 - 小欧 - WritetextInput.content 删 max_length=WRITE_TEXT_MAX_CHARS 入参长度校验(依3.6去除多余叠加限制; 写结果预览由 Tool 层 _build_content_preview 文首50+文末50 生成, 不新增 OBS_WRITETEXT_*; 常量 WRITE_TEXT_MAX_CHARS 作废删除)
# 2026-07-20 - 小欧 - 门限复查: FindInput docstring 去除"每页最多500条/仅返回offset后500条"误导(与治理后返回全部匹配、OBS_FIND显示域行×列收口冲突, LLM会误判工具能力上限); 改为"返回全部匹配, 显示域按行×列收口, offset仅跳过"
# 2026-07-21 - 小欧 - ReadtextInput.limit/ReadDocxInput.limit/top_n description 引用tool_constants常量(非硬编码200), 加"建议不超过{MAX}"说明
# 2026-07-21 - 小欧 - 入参即信任: ReadtextInput.limit le=1000000→1000, 支撑用户指定1000以内行数
# 2026-07-25 - 小欧 - description去冗余: 27处必填/可选/默认/范围重复移除
# 2026-07-25 - 小欧 - description去冗余+内部细节清理: encoding自动尝试/检测, AES-256, content LLM截断原因, context冗余; typo修: 盖覆→覆盖
# 2026-07-25 - 小欧 - description肯定表述+ReadmediaInput docstring正面格式说明+注释修正
# 2026-07-25 - 小欧 - 删content长度限制虚数建议,改为"超过建议分多次写入"
# 2026-07-25 - 小欧 - MoveInput.overwrite 说明增强: 提示默认False不覆盖+目标存在时报错
# 2026-07-28 - 小欧 - description精确化: writetext.content 去冗余精简至1行+点明"必填"; edittext.old_string 强调"必须精确匹配(含缩进)"; edittext.new_string 精简为"替换后的新文本"; EdittextInput docstring 开头加匹配提示
# 2026-07-28 - 小欧 - 修复Bug-4: edittext.new_string description 恢复"替换/插入的新文本"(上次精简丢弃了插入/删除语义)
# 2026-07-29 - 小欧 - 锚点重叠约束加schema desc: EdittextInput/old_string/new_string加说明, before/after模式new_string不能包含old_string整行
# 2026-08-05 - 小欧 - BUG-2.5修复: CompressInput.timeout 补 ge=5/le=1800 (description写5-1800但Field缺约束,clamp失效;配合compress internal timeout-2 deadline,ge=5使internal≥3s安全,防LLM传≤2导致deadline过去拿不到信息)
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
from app.tools.tool_constants import OBS_READTEXT_MAX_ROWS

# ============================================================
# F1: readtext — 读取文本文件
# ============================================================

# ⚠️ Pydantic class docstring 会进入 JSON Schema 的 parameters.description 并发给 LLM
# 工具描述写在 file_register.py 的 FILE_TOOL_DESCRIPTIONS 里。
#禁止在docstring 里面行 非工具信息文字
class ReadtextInput(BaseModel):
    """
     不支持office类型.docx/.xlsx/.pptx/.PDF文件和媒体文件读取和编辑
    【四种模式】
    1. 读全文: 不传offset/limit/tail
    2. 前N行: 只传limit（如limit=100读前100行）。建议limit不超过{}行，超出需用offset+limit分页
    3. 尾部N行: 只传tail（如tail=20读最后20行）
    4. 分页: offset+limit（如offset=10, limit=20读第10-29行）

    【互斥规则】
    - tail不能与offset/limit同时使用

    【示例】
    - 不传参数: 读全文
    - limit=100: 读前100行
    - tail=20: 读最后20行
    - offset=10, limit=20: 读第10-29行"""
    __doc__ = __doc__.format(OBS_READTEXT_MAX_ROWS)
    path: str = Field(
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
        le=1000,
        description=f"""读取行数。建议不超过{OBS_READTEXT_MAX_ROWS}行，超限需再次用offset+limit分页读取。

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
        description="文件编码,默认utf-8。非utf-8编码文件需指定gbk/gb2312等"
    )



# ============================================================
# F2: writetext — 写文本文件
# ============================================================

class WritetextInput(BaseModel):
    """不支持office类型.docx/.xlsx/.pptx/.PDF文件和媒体文件写入"""
    path: str = Field(
        description="文件的完整路径(绝对路径,支持中文路径)。用于写入文本文件:txt/md/py/js/ts/json/yaml/yml/xml/html/css/csv/log等"
    )
    content: str = Field(
        description="要写入文件的正文,必填。换行用\\n表示。大文件建议分多次写入(首次append=False,后续append=True)",
    )
    encoding: Optional[str] = Field(
        default=None,
        description="文件编码。追加时沿用已有编码,新建时默认utf-8。也可指定gbk/gb2312等"
    )
    append: bool = Field(
        default=False,
        description="是否追加写入。True=追加,False=覆盖"
    )


# ============================================================
# F3: readmedia — 读媒体文件
# ============================================================

class ReadmediaInput(BaseModel):
    """支持本地图片(JPG/PNG/GIF/BMP/WebP/SVG/ICO/TIFF)、音频(MP3/WAV/OGG/M4A/FLAC/AAC)、视频(MP4/AVI/MOV/MKV)。返回Base64编码数据。不支持PDF文件和URL——网页中的图片/PDF请用fetchpage获取"""
    path: str = Field(
        description="本地媒体文件的完整路径(不支持URL)"
    )


# ============================================================
# F4: edittext — 编辑文本文件
# ============================================================

class EdittextInput(BaseModel):
    """old_string必须精确匹配(含缩进)。
    mode说明:
    once   -- 只替换第一个匹配
    all    -- 替换全部匹配
    before -- 在唯一锚点前插入(new_string不要包含old_string整行,否则重复)
    after  -- 在唯一锚点后插入(new_string不要包含old_string整行,否则重复)"""
    path: str = Field(
        description="目标文件的绝对路径(仅支持文本文件)"
    )
    old_string: str = Field(
        description="待替换/定位的旧文本,必填且必须精确匹配(含缩进和空格)。before/after模式下old_string是锚点定位行,new_string不要包含此行"
    )
    new_string: str = Field(
        default="",
        description="替换/插入的新文本。传空串''表示删除匹配的old_string。before/after模式下new_string不能包含与old_string相同的整行(否则插入后锚点行会重复),只填新内容即可"
    )
    mode: str = Field(
        default="once",
        description="操作模式: once(只替换第一个), all(替换全部), before(在锚点前插入), after(在锚点后插入)"
    )
    ignore_case: bool = Field(
        default=False,
        description="是否忽略大小写"
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
    path: str = Field(
        description="目录路径(绝对路径)"
    )
    sort_by: Literal["name", "size", "mtime"] = Field(
        default="name",
        description="排序方式:name/size/mtime"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件(以.开头的文件)"
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
    path: str = Field(
        description="目录路径(绝对路径)"
    )
    include_hidden: bool = Field(
        default=False,
        description="是否显示隐藏文件(以.开头的文件)"
    )
    max_depth: int = Field(
        default=5,
        ge=1, le=20,
        description="树的最大深度"
    )
    sort_by: Literal["name", "mtime"] = Field(
        default="name",
        description="排序方式:name/mtime(不支持size排序)"
    )


# ============================================================
# F6: search_files — 搜索文件名
# ============================================================

class FindInput(BaseModel):
    """支持offset参数跳过前N条结果;工具返回显示域按行×列收口,offset仅用于跳过"""
    pattern: str = Field(
        description="文件名匹配模式,支持glob通配符(* ? **)和中文文件名。如 \"*.py\""
    )
    path: str = Field(
        description="搜索的起始目录(绝对路径)。如 D:/项目代码"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写"
    )
    type: Optional[Literal["file", "directory"]] = Field(
        default=None,
        description="搜索类型过滤:file=只返回文件,directory=只返回目录,不设则全部返回"
    )
    offset: int = Field(
        default=0,
        description="分页偏移量,用于跳过前N条结果;offset仅跳过不限制总数"
    )


# ============================================================
# F7: grep_file_content — 搜索文件内容
# ============================================================

class GrepInput(BaseModel):
    """默认返回匹配行的完整内容(含文件名与行号);结果按文件修改时间降序排列,最新修改的文件在最前。
只查文件名列表或只计匹配数量等需求,由 LLM 基于返回的带文件路径内容自行去重或计数,无需额外参数。
(各参数能力见对应字段 description)"""
    pattern: str = Field(
        description="正则表达式搜索模式(Python re 语法),支持中文内容搜索。如 \"def read_file\";含 . ( ) [ ] * + ? $ 等特殊字符的纯文本请自行转义(如 foo\\.bar)"
    )
    path: str = Field(
        description="搜索文件或目录路径(绝对路径,必填);传文件则只搜该文件,传目录则递归搜索子目录"
    )
    glob: Optional[str] = Field(
        default=None,
        description="文件名过滤(glob通配符),如 \"*.py\",仅对目录递归搜索生效"
    )
    ignore_case: bool = Field(
        default=True,
        description="是否忽略大小写(等价于 pattern 前加 (?i))"
    )
    context: int = Field(
        default=0, ge=0,
        description="匹配行前后各N行上下文"
    )





# ============================================================
# F8: compress_files — 压缩文件
# ============================================================

class CompressInput(BaseModel):
    """可压缩单文件、目录或通配符批量打包;压缩目录时默认递归包含子目录。默认 zip 格式,默认不覆盖已存在压缩包(需 overwrite=True),仅 ZIP 支持加密。"""
    path: str = Field(description="文件/目录路径(绝对路径),支持通配符如*.txt")
    dest: str = Field(description="输出压缩包路径(绝对路径)")
    format: Literal["zip", "tar", "tar.gz", "tar.bz2"] = Field(
        default="zip", description="压缩格式:zip/tar/tar.gz/tar.bz2"
    )

    password: Optional[str] = Field(default=None, description="ZIP加密密码,设置后创建加密ZIP,仅ZIP格式支持")
    overwrite: bool = Field(default=False, description="是否覆盖已存在文件")
    exclude_patterns: Optional[List[str]] = Field(
        default=None, description="排除的文件/目录模式列表,如 ['node_modules', '__pycache__']"
    )
    timeout: int = Field(
        default=300, ge=5, le=1800,
        description="超时秒数(5-1800秒),大目录/大文件压缩建议适当增大,默认300秒;LLM传入≤4时clamp到5,防compress内部timeout-2 deadline副本过期拿不到进度提示 — 小欧 2026-08-05 BUG-2.5"
    )


# ============================================================
# F8b: extract_archive — 解压文件
# ============================================================

class ExtractInput(BaseModel):
    """解压 zip/tar/tar.gz/tar.bz2 到目标目录,默认递归展开所有层级并保留原目录结构。dest 默认自动创建同名目录,默认不覆盖(需 overwrite=True),ZIP 加密包需 password。"""
    path: str = Field(description="压缩包路径(绝对路径)。支持格式:zip/tar/tar.gz/tar.bz2")
    dest: Optional[str] = Field(
        default=None, description="解压目标目录(绝对路径,默认自动创建同名目录)"
    )
    password: Optional[str] = Field(default=None, description="解密密码(仅ZIP格式支持)")
    overwrite: bool = Field(default=False, description="是否覆盖已存在文件")


# ============================================================
# F9a: move_file — 移动文件
# ============================================================

class MoveInput(BaseModel):
    """移动文件或目录到新位置;移动目录时默认递归。默认不覆盖已存在目标(需 overwrite=True)。"""
    path: str = Field(description="源文件路径(绝对路径)")
    dest: str = Field(description="目标路径(绝对路径)")
    overwrite: bool = Field(default=False, description="是否覆盖目标文件(不覆盖时目标存在则报错)")


# ============================================================
# F9b: copy_file — 复制文件
# ============================================================

class CopyInput(BaseModel):
    path: str = Field(description="源文件路径(绝对路径)")
    dest: str = Field(description="目标路径(绝对路径)")
    recursive: bool = Field(default=False, description="复制目录时需True")
    overwrite: bool = Field(default=False, description="是否覆盖目标文件")
    preserve_metadata: bool = Field(default=True, description="是否保留文件元数据")



# ============================================================
# F9c: delete_file — 删除文件
# ============================================================

class DeleteInput(BaseModel):
    path: str = Field(description="文件/目录路径(绝对路径)")
    recursive: bool = Field(default=False, description="删除非空目录时需True")
    force: bool = Field(default=False, description="True=跳过回收站永久删除,False=放入回收站")


# ============================================================
# F9d: rename_file — 重命名文件
# ============================================================

class RenameInput(BaseModel):
    path: str = Field(min_length=1, description="原文件/目录路径(绝对路径)")
    dest: str = Field(min_length=1, description="新名称(仅文件名,不含目录路径)")
    overwrite: bool = Field(default=False, description="是否覆盖目标文件")


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

