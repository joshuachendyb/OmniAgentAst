# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-14 小欧 新建: wire 槽位正则与可视标签单一真源。只含字面量/正则, app 内零依赖;
#   供 ref_slots(计划/装配) 与 attachment_wire(展开) 共用, 消除各模块本地 re.compile 复制。
#   语义前缀(INLINE 层)按统一括号风格另批随 extract 一并归一, 本批不改变任何输出字节 — 小欧-2026-11-14
"""wire_prefix — wire 槽位正则与标签字面量的单一真源(零依赖)。"""

import re

# SLOT 层: 机器占位(ABI 冻结, 历史/持久化为字符串, 禁止改名)
# 命名组名 = SLOT_WRITERS 注册表键: 展开层按 m.lastgroup 派发, 新增来源
# 正则命名组与注册表键同名, 漏配展开器即 KeyError 响亮暴露, 不静默错位 — 小欧-2026-11-14
SLOT_ATTACHMENT_RE = re.compile(r"\[\[ATTACHMENT:(?P<attachment>[0-9a-f]{32})\]\]")
SLOT_URL_RE = re.compile(r"\[\[URL_ITEM:(?P<url>[A-Za-z0-9_\-=]+)\]\]")

SLOT_LABEL_ATTACHMENT = "附件"
SLOT_LABEL_URL = "链接"

# INLINE 层: 模型可见的可读标签(仅提示词语义, 无机器解析依赖)。
# 统一范式 [主体·形态(·第三段)], 主体∈{附件,链接}, 形态∈{正文,元信息,未发送,未转发,抽取失败};
# 禁止"档案头/档案卡/正文·文本"等同义异构词。产出点唯一, 各模块只引用本处常量 — 小欧-2026-11-15
INLINE_LINK = "[链接]"
INLINE_ATT_BODY = "[附件·正文]"
INLINE_ATT_BODY_KIND = "[附件·正文·{label}]"
INLINE_ATT_PREVIEW = "[附件·正文·预览]"
INLINE_ATT_META = "[附件·元信息·{kind}]"
INLINE_ATT_UNSENT = "[附件·未发送: {why}]"
INLINE_URL_UNSENT = "[链接·未转发: {why}]"
INLINE_EXTRACT_FAIL = "[附件·抽取失败({err})]"
