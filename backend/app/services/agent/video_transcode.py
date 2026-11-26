# -*- coding: utf-8 -*-
"""视频转码工具 — 把非 H264 视频转成 H264, 供只收标准编码的视频模型投递。

编辑历史: 2026-11-20 小欧 新建: 实测 nano-omni 只收 H264/HEVC/VP8/VP9, MJPG 等编码报 400;
  用 imageio-ffmpeg 自带 ffmpeg(本项目已有 imageio 依赖)转 H264, 转码结果按源文件路径缓存复用。
编辑历史: 2026-11-20 小欧 三堂会审整改: 空路径/文件缺失防御(不崩轮); 半成品写临时名成功后原子替换(防缓存投毒);
  进程内锁防同文件并发重复转码; 编码只探一次; 魔法数提常量; 类型注解 Tuple 化。
  临时文件后缀修复: 原用 .partial 致 ffmpeg 无法识别 muxer 报 Invalid argument, 改 .tmp_<key>(保留 .mp4 后缀)后转码成功。
编辑历史: 2026-11-20 小欧 三堂会审命名整改: _get_ffmpeg 返回的是路径却名作 ffmpeg, 改 _get_ffmpeg_path; 局部变量 fc→fourcc_int、
  tmp_path→partial_path(保留 mp4 后缀的中间产物, 非泛临时物); 引用常量 VIDEO_ACCEPTED_FOURCCS/VIDEO_TRANSCODE_LOCK_TABLE_MAX
  (见 media_constants 同名整改); 纯改名零行为变更。
编辑历史: 2026-11-21 小欧 缓存目录单源 + 保留期清理: 目录拼装收口 default_cache_dir(), 新增 sweep_cache(days)
  按 mtime 删超期 .mp4/.tmp_(保留期同日志 logging.retention_days), 原缓存只增不减 — 小欧-2026-11-21
编辑历史: 2026-11-26 小欧 阶段六接入进程宿主: 转码 subprocess.run 改 proc_io.run(内部走宿主, 主进程零
  CreateProcessW); CompletedProcess/TimeoutExpired 契约一致, 超时由宿主 Job 杀整树(原只杀 ffmpeg 本体,
  孙进程残留风险消除); 删除模块级 import subprocess(已无调用方)。方案见 [65] 7.5.1。
"""

import os
import tempfile
import threading
import time
from typing import Dict, Optional, Tuple

from app.logger import logger
from app.proc.proc_io import (
    run as proc_run,  # 阶段六: 转码走进程宿主, 主进程零 CreateProcessW — 小欧-2026-11-26
)
from app.services.agent.media_constants import (
    VIDEO_ACCEPTED_FOURCCS,
    VIDEO_TRANSCODE_CRF,
    VIDEO_TRANSCODE_LOCK_TABLE_MAX,
    VIDEO_TRANSCODE_MAX_EDGE,
    VIDEO_TRANSCODE_TIMEOUT_SEC,
)  # 转码常量集中管理(三堂会审归位) — 小欧-2026-11-20

_TRANSCODE_STDERR_TAIL = 300  # 转码失败日志里截取的 stderr 尾部字符数(本模块日志细节)

# 以下为进程内运行时状态(非配置常量), 随用方留本模块
_transcode_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

_ffmpeg_exe: Optional[str] = None


def _get_ffmpeg_path() -> str:
    """惰性取 ffmpeg 可执行文件路径(imageio-ffmpeg 自带, 无需系统安装) — 小欧-2026-11-20 命名整改。"""
    global _ffmpeg_exe
    if _ffmpeg_exe is None:
        import imageio_ffmpeg  # 延迟导入: 仅转码路径需要
        _ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    return _ffmpeg_exe


def default_cache_dir() -> str:
    """转码缓存默认目录: %TEMP%/omniagent_video_h264 — 小欧-2026-11-21 单源(转码与清理共用)"""
    return os.path.join(tempfile.gettempdir(), "omniagent_video_h264")


def sweep_cache(days: int = 0) -> int:
    """清理超过 days 天的转码缓存, 返回删除个数 — 小欧-2026-11-21

    缓存原先无任何清理策略(实测 %TEMP% 留残留 mp4); 保留期与日志同一口径(logging.retention_days)。
    目录是本模块专用的, 里面只有转码产物与半成品, 故按整目录清, 不设文件名匹配。
    """
    if days <= 0:
        from app.config import get_config
        days = int(get_config().get("logging.retention_days", 10) or 0)
    if days <= 0:
        return 0
    folder = default_cache_dir()
    if not os.path.isdir(folder):
        return 0
    cutoff = time.time() - days * 86400
    removed = 0
    for name in os.listdir(folder):
        target = os.path.join(folder, name)
        try:
            if os.path.isfile(target) and os.path.getmtime(target) < cutoff:
                os.remove(target)
                removed += 1
        except OSError as e:
            logger.warning(f"[video_transcode] 清理缓存失败: {target} err={e}")
    if removed:
        logger.info(f"[video_transcode] 清理超期转码缓存 {removed} 个(保留 {days} 天)")
    return removed


def _probe_codec(path: str) -> str:
    """读视频编码 FOURCC; 任何失败返回空串(空串→保守转码), 绝不抛异常断轮 — 小欧-2026-11-20。"""
    try:
        import cv2  # 延迟导入: 仅探测路径需要
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return ""
        try:
            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            return "".join(chr((fourcc_int >> (8 * i)) & 0xFF) for i in range(4))
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
            if len(_transcode_locks) >= VIDEO_TRANSCODE_LOCK_TABLE_MAX:
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
    if codec in VIDEO_ACCEPTED_FOURCCS:
        return path, False

    base = os.path.basename(path)
    stem, _ = os.path.splitext(base)
    out_dir = cache_dir or default_cache_dir()
    try:
        os.makedirs(out_dir, exist_ok=True)
        st = os.stat(path)
    except OSError as e:
        logger.warning(f"[video_transcode] 读源文件元数据失败, 跳转码: {path} err={e}")
        return path, False
    # 缓存键: 源文件名 + 大小 + mtime(纳秒, 避免同秒同大小覆盖文件命中旧产物), 同文件复投不重转
    key = f"{stem}_{st.st_size}_{st.st_mtime_ns}.mp4"
    out_path = os.path.join(out_dir, key)
    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        return out_path, True

    # 同文件并发串行化; 双重检查(上一线程可能已转完)
    with _lock_for(path):
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path, True
        # 写临时文件成功后原子替换 → 半成品永不成为缓存。
        # 临时名必须保留 .mp4 扩展名: ffmpeg 靠扩展名选 muxer, 用 .partial 会因无法识别封装格式而失败 — 小欧-2026-11-20
        partial_path = os.path.join(out_dir, f".tmp_{key}")  # key 已含 .mp4 后缀
        cmd = [
            _get_ffmpeg_path(), "-y", "-v", "error",
            "-i", path,
            "-vf", f"scale='min({VIDEO_TRANSCODE_MAX_EDGE},iw)':-2",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(VIDEO_TRANSCODE_CRF),
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            "-an",  # 视频投递不需要音轨, 去掉省体积
            partial_path,
        ]
        try:
            # 清理可能的旧半成品
            if os.path.exists(partial_path):
                os.remove(partial_path)
            result = proc_run(cmd, capture_output=True, timeout=VIDEO_TRANSCODE_TIMEOUT_SEC)
            if result.returncode != 0 or not os.path.exists(partial_path) or os.path.getsize(partial_path) == 0:
                logger.warning(f"[video_transcode] 转码失败 codec={codec} path={path} err={result.stderr[-_TRANSCODE_STDERR_TAIL:]!r}")
                _safe_remove(partial_path)
                return path, False
            os.replace(partial_path, out_path)  # 原子替换
            logger.info(f"[video_transcode] {codec}->h264 成功: {base} -> {os.path.getsize(out_path)} bytes")
            return out_path, True
        except Exception as e:  # noqa: BLE001 — 转码失败降级, 不打断对话
            logger.warning(f"[video_transcode] 转码异常 codec={codec} path={path} err={e}")
            _safe_remove(partial_path)
            return path, False


def _safe_remove(path: str) -> None:
    """尽力删除临时文件, 删除失败只告警不影响主流程 — 小欧-2026-11-20"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as e:
        logger.warning(f"[video_transcode] 清理临时文件失败 path={path} err={e}")
