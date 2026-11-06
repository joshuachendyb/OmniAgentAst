# 编辑历史:
# 2026-11-04 小欧 新建: 附件五分类 + 五张档案卡注入文本(纯函数, 零 DB) — 小欧-2026-11-04
# 2026-11-06 小欧 补 classify 文本分支: 文本扩展名(如 .txt/.md/.py)先于"任意后缀 → binary"判定,
#   否则文本文件落 binary, 文本档案卡用不上 — 小欧-2026-11-06

"""attachments.extract — 按类型把附件变成注入文本。

类型轴分层(每个阶段只替换一个函数, 分派结构不动):
  S0 全部     → 档案卡(本文件即完成; 任何类型上传后都能发送)
  S1 text     → _text_card 换成 _text_body(≤256KB 全文 / 超限档案头)
  S2 image    → 卡片只服务非视觉模型(视觉模型由 services/agent/vision.py 走 parts, 不经过本文件)
  S3 richdoc  → _richdoc_card 换成 _richdoc_body(复用 read_pdf / read_docx / read_xlsx)
  S4 video    → _video_card 增加 _video_meta(ffprobe; 缺失则降级, 不抛错)

零 DB、零状态: 入参是 attachments 表的一行(dict), 返回 str。
读盘复用 browse_service(唯一实现), 不另写文件读取。
"""
from pathlib import Path
from typing import Any

from app.file_browse import browse_service as browse

TEXT_INLINE_MAX = 256 * 1024      # 文本内联上限 256KB（超限走头尾摘录）
ARCHIVE_HEAD_LINES = 40           # 档案头预览行数

# 五分类后缀词典(唯一真源): service.py 据此组合上传白名单, 严禁另抄一份(DRY)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
RICH_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx"}
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".log", ".csv", ".tsv", ".json", ".jsonl", ".xml",
    ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties",
    ".html", ".htm", ".css", ".scss", ".less", ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx", ".vue", ".py", ".pyi", ".java", ".kt", ".go", ".rs", ".c",
    ".h", ".hpp", ".cpp", ".cc", ".cs", ".php", ".rb", ".swift", ".m", ".sh",
    ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".sql", ".r", ".lua", ".pl",
    ".scala", ".dart", ".gradle", ".dockerfile",
}


def classify(stored_path: Path, mime: str, size: int) -> str:
    """五分类(唯一实现): image / video / richdoc / text / binary。

    扩展名唯一真源优先(不可伪造); mime 仅当扩展名未知/为空时辅助判定,
    且不作为"可升级为图片/视频"的凭据 —— 避免客户端把 .txt 报成 image/png 混入图片通道。
    size 用于空文件判 binary(0 字节无内容, 不实探)。
    """
    sfx = stored_path.suffix.lower()
    if sfx in IMAGE_SUFFIXES:
        return "image"
    if sfx in VIDEO_SUFFIXES:
        return "video"
    if sfx in RICH_SUFFIXES:
        return "richdoc"
    if size <= 0:
        return "binary"
    # 文本扩展名: 命中即判 text（S1 起据此走 _text_body 读正文）。
    #   注意: 此分支须在"有扩展名但不在任何白名单 → binary"之前,
    #   否则 .txt/.py/.md 等文本会落 binary, 文本档卡永远用不上。
    if sfx in TEXT_SUFFIXES:
        return "text"
    # 有扩展名但不在白名单(如 .zip/.exe): 不靠 mime 翻案, 直接 binary
    if sfx:
        return "binary"
    # 无扩展名: 用 mime 辅助(仍以实探兜底), 客户端伪造代价与文本探测一致
    if (mime or "").startswith("image/") and browse._probe_text(stored_path) is not True:
        return "image"
    if (mime or "").startswith("video/"):
        return "video"
    if browse._probe_text(stored_path):      # 首 8KB 查 NUL, 与文件页同一判定
        return "text"
    return "binary"


def build_inject_text(att: dict[str, Any]) -> str:
    """注入文本唯一产生点。失败由调用方(resolver)折算成 attachment_failed。"""
    kind = att.get("kind") or "binary"
    if kind == "text":
        return _text_card(att)    # S1: 换成 _text_body(Path(att["stored_path"]), int(att.get("size") or 0))
    if kind == "image":
        return _image_card(att)
    if kind == "richdoc":
        return _richdoc_card(att)   # S3: 换成 _richdoc_body(att)
    if kind == "video":
        return _video_card(att)     # S4: 卡片前插入 _video_meta 元数据段
    return _binary_card(att)


def _head(att: dict[str, Any]) -> str:
    return (f"文件: {att.get('original_name') or Path(att['stored_path']).name}\n"
            f"路径: {att.get('path') or att['stored_path']}\n"
            f"类型: {att.get('mime') or '未知'}\n"
            f"大小: {int(att.get('size') or 0)} 字节")


def _text_card(att: dict[str, Any]) -> str:
    return (f"[附件档案卡·文本]\n{_head(att)}\n"
            f"说明: 已收到该文本文件。正文抽取未启用时，可用文件工具按上述路径读取。")


def _image_card(att: dict[str, Any]) -> str:
    return (f"[附件档案卡·图片]\n{_head(att)}\n"
            f"说明: 当前模型无视觉能力，无法查看图片内容。"
            f"如需识别图中信息，请用文字描述或改用可读的文本/表格文件。")


def _richdoc_card(att: dict[str, Any]) -> str:
    return (f"[附件档案卡·富格式文档]\n{_head(att)}\n"
            f"说明: 正文抽取未启用时，可用文件工具读取该路径，"
            f"或把内容另存为 txt/csv 后再引用。")


def _video_card(att: dict[str, Any]) -> str:
    return (f"[附件档案卡·视频]\n{_head(att)}\n"
            f"说明: 当前不支持视频内容理解；如需处理请用文件工具按需读取。")


def _binary_card(att: dict[str, Any]) -> str:
    return (f"[附件档案卡·二进制]\n{_head(att)}\n"
            f"说明: 非文本内容，无法注入正文；如需处理请用文件工具按需读取。")
