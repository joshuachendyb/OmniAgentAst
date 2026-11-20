# -*- coding: utf-8 -*-
# 模块说明: provider 适配基类 — 默认行为==通用(general), 承载各 provider 相对通用的差异钩子。
#
# 【基类提供的通用能力(未覆写即采用)】
#   ① 鉴权/HTTP 接缝: Bearer 头(auth_headers/static_headers)、每请求头、chat 端点(/chat/completions)、
#      门禁 body 原样、非流式、error 码走全局分类器。
#   ② 输入模态: 基类不构造 chat 输入 part —— 图片/音频/文档用 OpenAI 标准
#      (image_url/input_audio/file), 视频用多厂商共同支持的 video_url, 均在 media_payload 统一构造;
#      传输策略(内联/外链)由 capability 的 transport 门控。基类只提供 responses 端点 body 转换(to_responses_body)。
#   ③ 输出模态(生成): 通用生图 prepare_image_body(size/image/response_format顶层) +
#      通用生视频 prepare_video_body(first/last_frame/images/audios/videos/seconds/size/aspect_ratio/seed 同名直传)。
#   ④ 纯文本任务调用约定: callTextForTask 默认不接管。
#
# 【何时必须建 adapter】规则: 某 provider 的方法/能力与上面基类通用实现不同 → 新建 adapter 文件继承本类,
#   只覆写有差异的钩子(如 sensenova 生图 size 用 WIDTHxHEIGHT、agnes 用档位+ratio+return_base64),
#   并在 adapters/__init__.py 的 _ADAPTERS 注册; 未覆写的钩子仍走基类通用实现(OCP)。
#   反例: 若只是调 general_gen_image/general_gen_video 的通用参数, 无需建 adapter。
#
# 归属依据(北京老陈核查): 承载 provider 的请求适配与调用约定差异 ——
#   前者指 HTTP 接缝差异与门禁 body/端点路由, 后者指纯文本任务的调用约定(callTextForTask)。
#   schema/reasoning/工具别名(#3/4/5)为全局层, 绝不 provider 化。
# 编辑历史: 2026-09-23 小欧 新建
# 编辑历史: 2026-10-09 小欧 加 callTextForTask 钩子(纯文本任务定制调用, 默认不接管) — 小欧-2026-10-09
# 编辑历史: 2026-10-31 小欧 新增 auth_headers(空 api_key 不携带 Authorization), static_headers 改为复用 — 小欧-2026-10-31

from typing import Dict, Optional

from app.utils.secret_utils import is_blank_secret  # 空密钥判定唯一权威 — 小欧 2026-10-31


class ProviderAdapter:
    """provider 适配基类 — 小欧 2026-09-23"""

    @staticmethod
    def auth_headers(api_key: str) -> Dict[str, str]:
        """Bearer 鉴权头 — api_key 为空则返回空字典(不携带该头) — 小欧 2026-10-31

        `Authorization: Bearer `(值为空) 是畸形头, 严格校验的无鉴权端点(本机 Ollama/vLLM 之流)
        会直接 400/401。api_key 留空的正确含义是"不带鉴权头", 而不是"带一个只有 scheme 的头"。
        鉴权头构造只此一处(DRY): 覆写 static_headers 的适配器一律复用它, 不得自行拼字符串。
        """
        if is_blank_secret(api_key):
            return {}
        return {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def static_headers(api_key: str) -> Dict[str, str]:
        """客户端创建时的静态头 — 默认仅 Authorization"""
        return ProviderAdapter.auth_headers(api_key)

    @staticmethod
    def per_request_headers() -> Dict[str, str]:
        """每请求动态头 — 默认无(现状行为)"""
        return {}

    @staticmethod
    def ensure_gate_body(body: Dict) -> Dict:
        """发送前门禁 body 保障 — 默认原样返回(现状行为)"""
        return body

    @staticmethod
    def endpoint_for(model: str) -> str:
        """按模型选端点 — 默认 chat 端点(现状行为)"""
        return "/chat/completions"

    @staticmethod
    def force_stream() -> bool:
        """非流式是否改走流式收集 — 默认 False(现状行为)"""
        return False

    @staticmethod
    def to_responses_body(chat_body: Dict, model: str) -> Dict:
        """responses 端点 body 转换 — 默认原样(现状行为, 仅 endpoint_for 返回 /responses 的适配器会覆写)"""
        return chat_body

    @staticmethod
    def error_message_map() -> Dict[int, str]:
        """provider 特有错误码 → 用户友好消息 — 默认空(走全局 error_classifier)"""
        return {}

    @staticmethod
    async def callTextForTask(client, messages) -> Optional[str]:
        """纯文本任务的定制化调用钩子 — 默认不接管, 返回 None 由调用方走通用路径

        用途: 压缩摘要这类"不要工具、只要一段文本"的任务, 若某 provider 的调用约定与
        通用路径不同, 由其适配器覆写本钩子接管。默认不接管故对既有链路零影响。
        返回 None = 未接管, 调用方自行走通用路径; 本钩子绝不抛异常, 以免波及既有链路。
        """
        return None

    # ---- 生成端点方言钩子(生图/生视频) — 小欧 2026-11-20 ----
    # 【新厂商接入指南】
    #   ① 协议通用(字段同名) → 零定制: 不建 adapter, 直接调 general_gen_image/general_gen_video,
    #      基类提供通用生图(size/image/response_format顶层)与通用生视频(first/last_frame/images/audios/
    #      videos/seconds/size/aspect_ratio/seed 同名字段直传)两套实现。
    #   ② 有差异(如 sensenova size 用 WIDTHxHEIGHT) → 新建 adapter 文件, 只覆写下面对应钩子,
    #      并在 adapters/__init__.py 的 _ADAPTERS 注册; generation_client 与工具层零改动(OCP)。
    # 方言翻译归 provider adapter, generation_client 保持协议无关。

    @staticmethod
    def prepare_image_body(body: Dict, *, size: Optional[str] = None,
                           ratio: Optional[str] = None,
                           image_refs: Optional[list] = None,
                           return_base64: bool = False,
                           response_format: Optional[str] = None) -> Dict:
        """生图请求体方言 — 基类 = 纯 general(通用), 不含任何厂商特有字段。

        通用字段: size 原样、image 参考图(单串/多数组, 多数兼容厂商支持 generations 内传图)、
          response_format 顶层(OpenAI 标准)。厂商特有字段下沉各自 adapter:
          agnes(ratio/return_base64/extra_body.response_format)、sensenova(WIDTHxHEIGHT)。
        探测腿走基类 = 探通用协议兼容性 — 小欧 2026-11-20
        """
        if size:
            body["size"] = size
        if image_refs:
            body["image"] = image_refs[0] if len(image_refs) == 1 else image_refs
        if response_format:
            body["response_format"] = response_format  # OpenAI 标准: 顶层
        return body

    @staticmethod
    def prepare_video_body(body: Dict, *, first_frame: Optional[str] = None,
                           last_frame: Optional[str] = None,
                           images: Optional[list] = None,
                           audios: Optional[list] = None,
                           videos: Optional[list] = None,
                           seconds: Optional[str] = None,
                           size: Optional[str] = None,
                           aspect_ratio: Optional[str] = None,
                           seed: Optional[int] = None) -> Dict:
        """生视频请求体方言定制 — 默认 agnes/OpenAI Videos 风格(字段同名直传)。

        新增厂商若有字段差异, 覆写本钩子; generation_client 保持协议无关。
        """
        for key, val in (("first_frame", first_frame), ("last_frame", last_frame),
                         ("images", images), ("audios", audios), ("videos", videos),
                         ("seconds", seconds), ("size", size),
                         ("aspect_ratio", aspect_ratio), ("seed", seed)):
            if val is not None:
                body[key] = val
        return body
