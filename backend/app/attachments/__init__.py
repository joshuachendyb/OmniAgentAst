# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 小欧 新建: 附件域包声明(不做 IO、不做再导出) — 小欧-2026-11-04

"""attachments 域 —— 附件落盘与注入文本生成。

分层: attachment_service.py(落盘 + DB, 唯一写盘点) / extract.py(纯抽取, 零 DB)。
本 __init__ **不导入任何子模块**: attachment_service 依赖 extract, 若在包初始化期再导出,
会形成"包初始化 → service → 包内 extract"的导入顺序耦合, 平白多一处循环导入面。
消费方一律 `from app.attachments.attachment_service import ...` 显式取子模块。
"""
