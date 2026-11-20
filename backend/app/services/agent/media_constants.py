# -*- coding: utf-8 -*-
"""app.services.agent.media_constants — 媒体生成/投递域常量集中管理 — 小欧 2026-11-20 三堂会审

职责(单一职责): 承载生图/生视频/视频转码/图源解析业务域的共享常量, 供 media_generate、
  video_transcode 等 agent 层模块引用, 消除常量散落在业务模块。与 app/constants.py(系统层)、
  tool_constants.py(工具层)分层, 本文件只属 agent/媒体域。
编辑历史: 2026-11-20 小欧 新建(三堂会审常量归位): 视频转码 6 常量(video_transcode.py 迁入)、
  图源 mime 映射(media_generate.py 迁入)集中至此, 原模块改 import, 取值零变更。
"""

# 视频编码 FOURCC(cv2 CAP_PROP_FOURCC 返回值, 4 字符)
VIDEO_H264_FOURCC = frozenset({"h264", "avc1", "H264", "AVC1", "x264", "X264"})
# 模型普遍可收的标准编码, 原样放行不转码(实测 nano-omni 报错列出的白名单)
VIDEO_ACCEPTED_FOURCC = VIDEO_H264_FOURCC | {"hevc", "hvc1", "vp80", "vp90", "av01"}
# 转码参数: 长边上限(px)、CRF 质量、ffmpeg 子进程超时(秒)
VIDEO_TRANSCODE_MAX_EDGE = 1280
VIDEO_TRANSCODE_CRF = 26
VIDEO_TRANSCODE_TIMEOUT_SEC = 300
# 同文件并发锁表上限: 长跑服务防无界增长, 超限清未持有的锁(转码期锁必被持有, 清不掉)
VIDEO_TRANSCODE_LOCK_MAX = 1024
# 本地路径→mime 映射(后缀白名单, 默认 png); 图源归一 i2i/i2v 共用
IMAGE_MIME_BY_EXT = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                     "webp": "image/webp", "gif": "image/gif"}
