# -*- coding: utf-8 -*-
"""视频转码工具 — 把非 H264 视频转成 H264, 供只收标准编码的视频模型投递。

编辑历史: 2026-11-20 小欧 新建: 实测 nano-omni 只收 H264/HEVC/VP8/VP9, MJPG 等编码报 400;
  用 imageio-ffmpeg 自带 ffmpeg(本项目已有 imageio 依赖)转 H264, 转码结果按源文件路径缓存复用。
编辑历史: 2026-11-20 小欧 三堂会审整改: 空路径/文件缺失防御(不崩轮); 半成品写临时名成功后原子替换(防缓存投毒);
  进程内锁防同文件并发重复转码; 编码只探一次; 魔法数提常量; 类型注解 Tuple 化。
  临时文件后缀修复: 原用 .partial 致 ffmpeg 无法识别 muxer 报 Invalid argument, 改 .tmp_<key>(保留 .mp4 后缀)后转码成功。
"""
import os
import subprocess
import tempfile
import threading
from typing import Dict, Optional, Tuple

from app.logger import logger

# H264 的 FOURCC 取值(cv2 CAP_PROP_FOURCC 返回); 这些编码模型普遍能收, 不转
_H264_FOURCC = {"h264", "avc1", "H264", "AVC1", "x264", "X264"}
# 模型普遍也能收的其它标准编码(实测 nano-omni 报的错误里列出), 原样放行
_ACCEPTED_FOURCC = _H264_FOURCC | {"hevc", "hvc1", "vp80", "vp90", "av01"}
# 转码参数(原散落的魔法数集中于此): 长边上限、CRF 质量、超时秒
_TRANSCODE_MAX_EDGE = 1280
_TRANSCODE_CRF = 26
_TRANSCODE_TIMEOUT_SEC = 300
# 同文件并发转码锁(进程内): 防止同时 -y 写同一路径产出截断文件
_TRANSCODE_LOCK_MAX = 1024  # 锁表上限: 长跑服务防无界增长, 超限清未持有的锁(转码期锁必被持有, 清不掉)
_transcode_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

_ffmpeg_exe: Optional[str] = None


def _get_ffmpeg() -> str:
    """惰性取 ffmpeg 可执行文件路径(imageio-ffmpeg 自带, 无需系统安装)。"""
    global _ffmpeg_exe
    if _ffmpeg_exe is None:
        import imageio_ffmpeg  # 延迟导入: 仅转码路径需要
        _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    return _ffmpeg_exe


def _probe_codec(path: str) -> str:
    """读视频编码 FOURCC; 任何失败返回空串(空串→保守转码), 绝不抛异常断轮 — 小欧-2026-11-20。"""
    try:
        import cv2  # 延迟导入: 仅探测路径需要
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return ""
        try:
            fc = int(cap.get(cv2.CAP_PROP_FOURCC))
            return "".join(chr((fc >> (8 * i)) & 0xFF) for i in range(4))
        finally:
            cap.release()
    except Exception as e:  # noqa: BLE001 — cv2 缺失/解码异常都降级为"未知编码"走转码
        logger.warning(f"[video_transcode] 编码探测失败, 按需转码 path={path} err={e}")
        return ""


def _lock_for(path: str) -> threading.Lock:
    """按规范化路径取进程内锁; 同文件并发转码串行化 — 小欧-2026-11-20"""
    key = os.path.normcase(os.path.abspath(path))
    with _locks_guard:
        lock = _transcode_locks.get(key)
        if lock is None:
            if len(_transcode_locks) >= _TRANSCODE_LOCK_MAX:
                # 清掉未被持有的锁(已转完的); 正被持有的不动, 防并发写同一缓存文件
                for k in [k for k, v in _transcode_locks.items() if not v.locked()]:
                    del _transcode_locks[k]
            lock = threading.Lock()
            _transcode_locks[key] = lock
        return lock


def ensure_h264(path: str, cache_dir: Optional[str] = None) -> Tuple[str, bool]:
    """确保视频是 H264; 是则原样返回, 否则转码到缓存文件并返回新路径。

    返回 (最终路径, 是否发生转码)。任何失败(空路径/文件缺失/转码异常/超时)都返回
    (原路径, False), 由调用方投递并交由上游错误分类降级, 绝在此抛异常断轮。
    """
    # 防御: 空路径/文件不存在 → 不转, 回原路径(交给上游降级), 不崩轮
    if not path:
        return path, False
    try:
        if not os.path.isfile(path):
            logger.warning(f"[video_transcode] 源文件不存在, 跳转码: {path}")
            return path, False
    except (OSError, ValueError):
        return path, False

    codec = _probe_codec(path)
    if codec in _ACCEPTED_FOURCC:
        return path, False

    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    out_dir = cache_dir or os.path.join(tempfile.gettempdir(), "omniagent_video_h264")
    try:
        os.makedirs(out_dir, exist_ok=True)
        st = os.stat(path)
    except OSError as e:
        logger.warning(f"[video_transcode] 读源文件元数据失败, 跳转码: {path} err={e}")
        return path, False
    # 缓存键: 源文件名 + 大小 + mtime, 同文件复投不重转
    key = f"{stem}_{st.st_size}_{int(st.st_mtime)}.mp4"
    out_path = os.path.join(out_dir, key)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path, True

    # 同文件并发串行化; 双重检查(上一线程可能已转完)
    with _lock_for(path):
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path, True
        # 写临时文件成功后原子替换 → 半成品永不成为缓存。
        # 临时名必须保留 .mp4 扩展名: ffmpeg 靠扩展名选 muxer, 用 .partial 会因无法识别封装格式而失败 — 小欧-2026-11-20
        tmp_path = os.path.join(out_dir, f".tmp_{key}")  # key 已含 .mp4 后缀
        cmd = [
            _get_ffmpeg(), "-y", "-v", "error",
            "-i", path,
            "-vf", f"scale='min({_TRANSCODE_MAX_EDGE},iw)':-2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(_TRANSCODE_CRF),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an",  # 视频投递不需要音轨, 去掉省体积
            tmp_path,
        ]
        try:
            # 清理可能的旧半成品
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            result = subprocess.run(cmd, capture_output=True, timeout=_TRANSCODE_TIMEOUT_SEC)
            if result.returncode != 0 or not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                logger.warning(f"[video_transcode] 转码失败 codec={codec} path={path} err={result.stderr[-300:]!r}")
                _safe_remove(tmp_path)
                return path, False
            os.replace(tmp_path, out_path)  # 原子替换
            logger.info(f"[video_transcode] {codec}->h264 成功: {base} -> {os.path.getsize(out_path)} bytes")
            return out_path, True
        except Exception as e:  # noqa: BLE001 — 转码失败降级, 不打断对话
            logger.warning(f"[video_transcode] 转码异常 codec={codec} path={path} err={e}")
            _safe_remove(tmp_path)
            return path, False


def _safe_remove(path: str) -> None:
    """尽力删除临时文件, 删除失败只告警不影响主流程 — 小欧-2026-11-20"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as e:
        logger.warning(f"[video_transcode] 清理临时文件失败 path={path} err={e}")
