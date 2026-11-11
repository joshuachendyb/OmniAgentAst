# 编辑历史:
# 2026-11-04 小欧 新建: 附件五分类 + 五张档案卡注入文本(纯函数, 零 DB) — 小欧-2026-11-04
# 2026-11-06 小欧 补 classify 文本分支: 文本扩展名(如 .txt/.md/.py)先于"任意后缀 → binary"判定,
#   否则文本文件落 binary, 文本档案卡用不上 — 小欧-2026-11-06
# 2026-11-06 小欧 S1: text 分支从 _text_card 换成 _text_body(≤256KB 全文 / >256KB 档案头) — 小欧-2026-11-06
# 2026-11-07 小欧 - 修复: _read_head_and_count 补 latin-1 兜底(与 _read_text_full 编码能力对齐),
#   消除同文件 ≤/≥256KB 两侧解码不一致致的档案头乱码 — 小欧-2026-11-07
# 2026-11-09 小欧 S3/S4: richdoc 真抽取(复用工具层四读取器) + video ffprobe 元数据(缺失降级) — 小欧-2026-11-09
# 2026-11-10 小欧 ffprobe 子进程补 CREATE_NO_WINDOW: 无控制台部署(打包版/服务态)跑视频元数据防闪黑窗 — 小欧-2026-11-10
# 2026-11-11 小欧 附件能力域升级: 音频分类/URL 七类识别/链接文本出口/统一截断尾注/字节入口;
#   build_inject_text 改契约查表分派; 视频与音频共用 ffprobe 探测实现 — 小欧-2026-11-11

"""attachments.extract — 按类型把附件变成注入文本。

类型轴分层(每个阶段只替换一个函数, 分派结构不动):
  S0 全部     → 档案卡(本文件即完成; 任何类型上传后都能发送)
  S1 text     → _text_card 换成 _text_body(≤256KB 全文 / 超限档案头)
  S2 image    → 卡片只服务非视觉模型(视觉模型由 services/agent/vision.py 走 parts, 不经过本文件)
  S3 richdoc  → _richdoc_body(真抽取, 失败抛异常由 resolver 折算)
  S4 video    → _video_meta(ffprobe 元数据; 缺失则降级, 不抛错)

零 DB、零状态: 入参是 attachments 表的一行(dict), 返回 str。
读盘复用 browse_service(唯一实现), 不另写文件读取。
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlsplit

from app.constants import MAX_REMOTE_IMAGES
from app.file_browse import browse_service as browse

TEXT_INLINE_MAX = 256 * 1024      # 文本内联上限 256KB（超限走头尾摘录）
ARCHIVE_HEAD_LINES = 40           # 档案头预览行数
RICH_MAX_ROWS = 200               # 富格式单 sheet 注入行上限; 超出由模型用 read_xlsx 工具深读
FFPROBE_TIMEOUT = 8               # 视频元数据探测超时(秒); 网络盘/大文件也不至于挂住请求

_RICH_LABEL = {".pdf": "PDF", ".docx": "Word", ".xlsx": "Excel", ".pptx": "PowerPoint"}

# 六分类后缀词典(唯一真源): service.py 据此组合上传白名单, contract.py 只引用不复制(DRY)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
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

# URL 识别词典(自视觉通道迁入并泛化, 唯一真源): 七类 content_kind 全覆盖, 不读模型
_MD_URL_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
_BARE_URL_RE = re.compile(
    r"https?://[^\s()\[\]<>{}\"'|，。；：？！]+", re.IGNORECASE)


def classify_url(url: str, content_type: str = "") -> str:
    """URL → content_kind 七类(纯识别): 后缀词典唯一真源优先, content-type 仅无后缀兜底。"""
    sfx = Path(urlsplit(url).path).suffix.lower()
    if sfx in IMAGE_SUFFIXES:
        return "image"
    if sfx in VIDEO_SUFFIXES:
        return "video"
    if sfx in AUDIO_SUFFIXES:
        return "audio"
    if sfx in RICH_SUFFIXES:
        return "richdoc"
    if sfx in TEXT_SUFFIXES:
        return "text"
    if sfx:
        return "binary"          # 有后缀不在任何词典: 不靠 content-type 翻案
    ct = (content_type or "").lower()
    if ct.startswith("image/"):
        return "image"
    if ct.startswith("video/"):
        return "video"
    if ct.startswith("audio/"):
        return "audio"
    if ct.startswith("text/"):
        return "text"
    return "unknown"


def scan_text_urls(text: str) -> list[str]:
    """正文 URL 无条件扫描: markdown 图片语法 + 裸链接, 去重截断; 不读模型。"""
    found = [m.group(1) for m in _MD_URL_RE.finditer(text or "")]
    seen = set(found)
    found += [m.group(0) for m in _BARE_URL_RE.finditer(text or "")
              if m.group(0) not in seen]
    out: list[str] = []
    for url in found:
        if url not in out:
            out.append(url)
    return out[:MAX_REMOTE_IMAGES]


def _link_body(url: str) -> str:
    """URL 降级文本出口(fallback_quality='link'): 仅链接文本, 零内容。"""
    return f"[链接]\n地址: {url}\n说明: 当前模型仅收到链接文本, 未获取内容。"


def with_completeness(body: str, *, shown: int, total: int, unit: str, path: str) -> str:
    """截断统一尾注: 未截断原样返回; 截断时追加唯一格式说明。"""
    if shown >= total:
        return body
    return (f"{body}\n[已截断：仅呈现 {shown}/{total} {unit}；"
            f"完整内容请用文件工具读取 {path}]")


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
    if sfx in AUDIO_SUFFIXES:
        return "audio"
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
    from app.attachments.contract import KIND_CONTRACT   # 延迟导入防循环
    kind = att.get("kind") or "binary"
    route = KIND_CONTRACT.get(("attachment", kind)) or KIND_CONTRACT[("attachment", "binary")]
    return route.extractor(att)


def _head(att: dict[str, Any]) -> str:
    stored = str(att.get("stored_path") or att.get("path") or att.get("original_name") or "")
    return (f"文件: {att.get('original_name') or Path(stored).name}\n"
            f"路径: {att.get('path') or stored}\n"
            f"类型: {att.get('mime') or '未知'}\n"
            f"大小: {int(att.get('size') or 0)} 字节")


def _text_body(att: dict[str, Any]) -> str:
    """S1: 文本附件真读正文(path 入口; 字节入口见 _text_body_from_bytes)。"""
    return _text_body_from_bytes(att, None)


def _text_body_from_bytes(att: dict[str, Any], raw: Optional[bytes]) -> str:
    """raw=None 走读盘(附件); raw=bytes 走直抽(URL 下载后), 两入口同一实现。"""
    stored = Path(str(att.get("stored_path") or att.get("path") or att.get("original_name") or "attachment"))
    size = len(raw) if raw is not None else int(att.get("size") or 0)

    if size <= TEXT_INLINE_MAX:
        content = _decode_text_bytes(raw) if raw is not None else _read_text_full(stored)
        return f"[附件正文·文本]\n{_head(att)}\n正文:\n{content}"

    # > 256KB: 单遍扫描取前 N 行 + 总行数(不整篇入 prompt)
    if raw is not None:
        head_lines, total = _head_and_count_bytes(raw, ARCHIVE_HEAD_LINES)
    else:
        head_lines, total = _read_head_and_count(stored, ARCHIVE_HEAD_LINES)
    preview = "\n".join(head_lines)
    return with_completeness(
        f"[附件档案头]\n{_head(att)}\n预览(前{ARCHIVE_HEAD_LINES}行):\n{preview}\n总行数: {total}",
        shown=ARCHIVE_HEAD_LINES, total=total, unit="行", path=str(stored),
    )


def _decode_text_bytes(raw: bytes) -> str:
    """字节解码: utf-8 → gbk → latin-1 逐个试, 失败用 replace 兜底。"""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _head_and_count_bytes(raw: bytes, n: int) -> tuple[list[str], int]:
    """字节直抽的头 n 行 + 总行数(与 _read_head_and_count 同口径)。"""
    head: list[str] = []
    total = 0
    for line in raw.splitlines():
        total += 1
        if total <= n:
            head.append(_decode_text_bytes(line))
    return head, total


def _read_text_full(path: Path) -> str:
    """读全文: utf-8 → gbk → latin-1 逐个试, 失败用 replace 兜底。"""
    return _decode_text_bytes(path.read_bytes())


def _read_head_and_count(path: Path, n: int) -> tuple[list[str], int]:
    """单遍扫描: 取前 n 行(rstrip) + 总行数。不整篇入内存。"""
    head: list[str] = []
    total = 0
    with open(path, "rb") as f:
        for raw_line in f:
            total += 1
            if total <= n:
                try:
                    head.append(raw_line.decode("utf-8").rstrip("\r\n"))
                except UnicodeDecodeError:
                    try:
                        head.append(raw_line.decode("gbk").rstrip("\r\n"))
                    except UnicodeDecodeError:
                        # 2026-11-07 小欧 - 补 latin-1 兜底: 与 _read_text_full 编码能力对齐,
                        #   否则 >256KB 档案头分支缺 latin-1, 同文件的 ≤/≥256KB 两侧解码不一致,
                        #   超大 latin-1 文本档案头乱码(全文分支却正常)。
                        head.append(raw_line.decode("latin-1").rstrip("\r\n"))
    return head, total


def _image_card(att: dict[str, Any]) -> str:
    return (f"[附件档案卡·图片]\n{_head(att)}\n"
            f"说明: 当前模型无视觉能力，无法查看图片内容。"
            f"如需识别图中信息，请用文字描述或改用可读的文本/表格文件。")


def _richdoc_body(att: dict[str, Any]) -> str:
    """富格式正文(S3): 复用工具层四个读取实现(pdf/docx/xlsx/pptx), 不另写解析器(DRY)。

    失败一律抛异常 —— 由 resolver 折算成 attachment_failed 回执,
    不在本层吞掉(否则模型会收到半截内容却以为完整)。
    """
    stored = Path(att["stored_path"])
    return _richdoc_body_path(att, stored)


def _richdoc_body_from_bytes(att: dict[str, Any], raw: Optional[bytes],
                             filename: str = "") -> str:
    """字节入口(URL 下载后直抽): 按文件名后缀落临时文件, 复用 path 同一实现。"""
    suffix = Path(filename or str(att.get("original_name") or "")).suffix.lower()
    if not raw or suffix not in RICH_SUFFIXES:
        raise RuntimeError("无可用富文档字节或后缀未知")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as fh:
        fh.write(raw)
        tmp = Path(fh.name)
    try:
        return _richdoc_body_path(att, tmp, label_suffix=suffix)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _richdoc_body_path(att: dict[str, Any], stored: Path, label_suffix: str = "") -> str:
    suffix = label_suffix or stored.suffix.lower()
    text = _extract_richdoc(stored, suffix)
    label = _RICH_LABEL.get(suffix, "文档")
    return (f"[附件正文·{label}]\n{_head(att)}\n"
            f"抽取说明: 以下为自动抽取文本, 版式/图片可能丢失; "
            f"需要精确页码/整表请用文件工具读取上面的路径。\n"
            f"正文:\n{text}")


def _extract_richdoc(stored: Path, suffix: str) -> str:
    """调工具层读取器并取出纯数据段; 工具返回 error 时抛出。"""
    resp = _call_tool_reader(stored, suffix)
    status = (resp.get("llm_data") or {}).get("status") or {}
    if status.get("exec_code") == "error":
        raise RuntimeError(status.get("detail") or "抽取失败")
    data = resp.get("data") or {}
    if suffix == ".xlsx":
        return _sheet_text(data, str(stored))
    if suffix == ".pptx":
        return _pptx_text(data)
    text = str(data.get("text") or "").strip()
    if not text:
        raise RuntimeError("未抽取到文本（可能是扫描件或空文档）")
    return text


def _pptx_text(data: dict[str, Any]) -> str:
    """PPT 幻灯片 → 文本: 每页一段, 含页码与正文。"""
    slides = data.get("slides") or []
    if not slides:
        raise RuntimeError("演示文稿为空")
    blocks: list[str] = []
    for s in slides:
        num = s.get("slide_num") or "?"
        text = str(s.get("text") or "").strip()
        blocks.append(f"## 第 {num} 页\n{text}")
    return "\n\n".join(blocks)


def _call_tool_reader(stored: Path, suffix: str) -> dict[str, Any]:
    """延迟导入: 四个读取器各自带 pdfplumber/docx/openpyxl/pptx, 顶层导入会拖慢服务启动。"""
    if suffix == ".pdf":
        from app.tools.document.read_pdf import read_pdf
        return read_pdf(str(stored))
    if suffix == ".docx":
        from app.tools.document.read_docx import read_docx
        return read_docx(str(stored))
    if suffix == ".pptx":
        from app.tools.document.read_pptx import read_pptx
        return read_pptx(str(stored))
    from app.tools.document.read_xlsx import read_xlsx
    return read_xlsx(str(stored))


def _cell(v: Any) -> str:
    """单元格转义: 换行/竖线/控制符压平, 避免注入 Markdown 表结构错行。
    附件为不可信数据, 抽取文本一律视为文本而非结构, 不保留制表/换行等可控字符。"""
    if v is None:
        return ""
    s = str(v)
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    s = s.replace("|", "｜")
    return "".join(ch if ch >= " " else " " for ch in s)


def _sheet_text(data: dict[str, Any], path: str = "") -> str:
    """工作簿 → 文本表: 每 sheet 一段, 单 sheet 最多 RICH_MAX_ROWS 行。"""
    sheets = data.get("sheets") or ([data] if "rows" in data else [])
    blocks: list[str] = []
    for sh in sheets:
        name = sh.get("sheet_name") or "Sheet"
        headers = [_cell(h) for h in (sh.get("headers") or [])]
        all_rows = sh.get("rows") or []
        rows = all_rows[:RICH_MAX_ROWS]
        lines = [" | ".join(headers)] if headers else []
        lines += [" | ".join(_cell(v) for v in row)
                  for row in rows]
        body = f"## {name}（{len(all_rows)} 行）\n" + "\n".join(lines)
        blocks.append(with_completeness(
            body, shown=len(rows), total=len(all_rows), unit="行", path=path))
    if not blocks:
        raise RuntimeError("工作簿为空")
    return "\n\n".join(blocks)


def _ffprobe_meta(stored: Path, codec_type: str) -> dict[str, Any] | None:
    """ffprobe 读时长/编码(视频另含分辨率)。未安装或解析失败返回 None(降级, 不抛错)。"""
    exe = shutil.which("ffprobe")
    if not exe:
        return None
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(stored)],
            capture_output=True, timeout=FFPROBE_TIMEOUT, check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,  # 无控制台部署(打包版/服务态)防闪黑窗 — 小欧-2026-11-10
        )
        if out.returncode != 0:
            return None
        data = json.loads(out.stdout.decode("utf-8", "replace") or "{}")
        fmt = data.get("format") or {}
        stream = next((s for s in data.get("streams") or [] if s.get("codec_type") == codec_type), {})
        meta = {
            "duration": fmt.get("duration") or stream.get("duration"),
            "codec": stream.get("codec_name"),
            "bit_rate": fmt.get("bit_rate") or stream.get("bit_rate"),
        }
        if codec_type == "video":
            meta["width"] = stream.get("width")
            meta["height"] = stream.get("height")
        return meta
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _video_meta(stored: Path) -> dict[str, Any] | None:
    return _ffprobe_meta(stored, "video")


def _audio_meta(stored: Path) -> dict[str, Any] | None:
    return _ffprobe_meta(stored, "audio")


def _video_card(att: dict[str, Any]) -> str:
    meta = _video_meta(Path(att["stored_path"]))
    if meta:
        detail = (f"\n时长: {meta.get('duration') or '未知'} 秒"
                  f"\n分辨率: {meta.get('width') or '?'}x{meta.get('height') or '?'}"
                  f"\n编码: {meta.get('codec') or '未知'}")
    else:
        detail = "\n元数据: 未读取(本机无 ffprobe 或解析失败, 不影响其余功能)"
    return (f"[附件档案卡·视频]\n{_head(att)}{detail}\n"
            f"说明: 当前不支持视频内容理解；如需处理请用文件工具按需读取。")


def _audio_card(att: dict[str, Any]) -> str:
    """音频档案卡: ffprobe 元数据(仅元数据, 无内容理解), 失败降级为档案卡。"""
    meta = _audio_meta(Path(att["stored_path"]))
    if meta:
        detail = (f"\n时长: {meta.get('duration') or '未知'} 秒"
                  f"\n编码: {meta.get('codec') or '未知'}")
        bitrate = meta.get("bit_rate")
        if bitrate:
            try:
                detail += f"\n码率: {int(bitrate) // 1000} kbps"
            except (TypeError, ValueError):
                detail += f"\n码率: {bitrate}"
    else:
        detail = "\n元数据: 未读取(本机无 ffprobe 或解析失败, 不影响其余功能)"
    return (f"[附件档案卡·音频]\n{_head(att)}{detail}\n"
            f"说明: 仅注入元数据, 不包含音频内容；如需处理请用文件工具按需读取。")


def _binary_card(att: dict[str, Any]) -> str:
    return (f"[附件档案卡·二进制]\n{_head(att)}\n"
            f"说明: 非文本内容，无法注入正文；如需处理请用文件工具按需读取。")
