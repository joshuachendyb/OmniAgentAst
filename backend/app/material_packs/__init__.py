# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-04 小欧 新建: 素材包域包声明(不做 IO、不做再导出) — 小欧-2026-11-04

"""material_packs 域 —— 素材包：一组文件 + 名称 + 说明，跨会话复用。

只存清单，不复制文件：包是"引用清单"，文件留原位（含 attachments/）。
本 __init__ 不导入子模块，消费方显式 `from app.material_packs.material_pack_service import ...`。
"""
