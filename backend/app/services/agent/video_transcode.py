# -*- coding: utf-8 -*-
"""视频转码工具 — 把非 H264 视频转成 H264, 供只收标准编码的视频模型投递。

编辑历史: 2026-11-20 小欧 新建: 实测 nano-omni 只收 H264/HEVC/VP8/VP9, MJPG 等编码报 400;
  用 imageio-ffmpeg 自带 ffmpeg(本项目已有 imageio 依赖)转 H264, 转码结果按源文件路径缓存复用。
"""
import os
import subprocess
import tempfile
from typing import Optional

from app.logger import logger

# H264 的 FOURCC 取值(cv2 CAP_PROP_FOURCC 返回); 这些编码模型普遍能收, 不转
_H264_FOURCC = {"h264", "avc1", "H264", "AVC1", "x264", "X264"}
# 模型普遍也能收的其它标准编码(实测 nano-omni 报的错误里列出), 原样放行
_ACCEPTED_FOURCC = _H264_FOURCC | {"hevc", "hvc1", "vp80", "vp90", "av01"}

_ffmpeg_exe: Optional[str] = None


def _get_ffmpeg() -> str:
    """惰性取 ffmpeg 可执行文件路径(imageio-ffmpeg 自带, 无需系统安装)。"""
    global _ffmpeg_exe
    if _ffmpeg_exe is None:
        import imageio_ffmpeg  # 延迟导入: 仅转码路径需要
        _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    return _ffmpeg_exe


def _probe_codec(path: str) -> str:
    """读视频编码 FOURCC; 失败返回空串(空串按需转码处理, 保守)。"""
    import cv2  # 延迟导入: 仅探测路径需要
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return ""
    try:
        fc = int(cap.get(cv2.CAP_PROP_FOURCC))
        return "".join(chr((fc >> (8 * i)) & 0xFF) for i in range(4))
    finally:
        cap.release()


def needs_transcode(path: str) -> bool:
    """是否需要转 H264: 非公认标准编码(含 MJPG/MP4V 等)就转。"""
    codec = _probe_codec(path)
    return codec not in _ACCEPTED_FOURCC


def ensure_h264(path: str, cache_dir: Optional[str] = None) -> tuple:
    """确保视频是 H264; 是则原样返回, 否则转码到缓存文件并返回新路径。

    返回 (最终路径, 是否发生转码)。转码失败返回 (原路径, False) 由调用方继续尝试
    (失败投递会被上游错误分类降级), 不在此抛异常断轮。
    """
    if not needs_transcode(path):
        return path, False

    codec = _probe_codec(path)
    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    out_dir = cache_dir or os.path.join(tempfile.gettempdir(), "omniagent_video_h264")
    os.makedirs(out_dir, exist_ok=True)
    # 缓存键: 源文件名 + 大小 + mtime, 同文件复投不重转
    st = os.stat(path)
    key = f"{stem}_{st.st_size}_{int(st.st_mtime)}.mp4"
    out_path = os.path.join(out_dir, key)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path, True

    cmd = [
        _get_ffmpeg(), "-y", "-v", "error",
        "-i", path,
        "-vf", "scale='min(1280,iw)':-2",  # 长边上限 1280, 限体积
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-an",  # 视频投递不需要音轨, 去掉省体积
        out_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            logger.warning(f"[video_transcode] 转码失败 codec={codec} path={path} err={result.stderr[-300:]!r}")
            return path, False
        logger.info(f"[video_transcode] {codec}->h264 成功: {base} -> {os.path.getsize(out_path)} bytes")
        return out_path, True
    except Exception as e:  # noqa: BLE001 — 转码失败降级, 不打断对话
        logger.warning(f"[video_transcode] 转码异常 codec={codec} path={path} err={e}")
        return path, False
