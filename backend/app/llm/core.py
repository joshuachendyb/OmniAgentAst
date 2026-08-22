# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 #34 fix: StreamChunk新增truncated字段
# 2026-07-19 小欧 StreamChunk新增finish_reason字段(OpenAI兼容API终结原因:stop/length/tool_calls/content_filter)
"""
LLM核心数据类与辅助函数 — SRP拆分自llm_core.py — 小健 2026-05-27

职责:定义LLM层的响应数据类(ChatResponse、StreamChunk)、异常解析(_resolve_exception)。

LLM 响应 → type 分类链（知识备忘 — 小欧 2026-07-15）:
1. LLM 原生输出（OpenAI /chat/completions SSE 格式）：
   data: {"choices":[{"delta":{"content":"文本"}}]}     ← 纯文本
   data: {"choices":[{"delta":{"tool_calls":[...]}}]}   ← 工具调用
   data: [DONE]
   LLM 自身 不 输出 type 字段。

2. agent 事后分类（llm_stream.py call_llm_stream 末尾）：
   流结束后 agent 检查累积结果决定 type：
   - LLM 产 tool_calls → type="action"     → 执行工具，继续循环
   - LLM 仅文本        → type="answer"     → FinalStep，结束循环
   - 流异常/出错       → type="error"      → 任务失败

3. type 共 3 种：action | answer | error

4. content / thought / reasoning 字段映射：
   - content: LLM 非推理文本块累加（is_reasoning=False）
   - reasoning: LLM 推理文本块累加（is_reasoning=True）
   - thought:
     type="action" 时: = full_content（调工具时的附带文本）
     type="answer" 时: = parsed.get("thought", content)（回退为 content）

编辑历史:
# 格式规范: {日期} {署名} {修改内容}
   2026-07-15 小欧 FCFormatError.__init__加self.message=message,补缺失的实例属性(写测试挖出的预存bug)
   2026-07-17 小沈 FCFormatError→LLMResponseError(FC概念改名,对应用户LLM响应数据错误语义)
   2026-08-14 小欧 llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
   2026-08-22 小欧 model结构化归一报告v1.25 6.4: ChatResponse(model/provider分离→chat_model:ModelRef)、
     StreamChunk(单字段model形态④→chunk_model:ModelRef补provider)、create_cancelled_chunk/create_error_chunk
     入参归一 chunk_model:ModelRef — F8 不留兼容别名, 消费点随改

拆分原则:数据/辅助定义与BaseAIService主服务类分离,遵循SRP。
对外透明:本模块由 app/llm/__init__.py 对外导出(ChatResponse/StreamChunk/create_cancelled_chunk等),外部import路径不变。 — 小欧 2026-08-14 更正(原"llm_core.py重新导出"失效,该文件已合并入 llm; 2026-08-14 llm 已独立为 app 顶层目录, 路径由 app/services/llm 改 app/llm)
"""

from typing import List, Dict, Optional
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.llm.error_classifier import SystemErrorClassifier


class LLMResponseError(Exception):
    """LLM响应数据错误 — LLM返回空/无效/格式错误的响应 — 小沈 2026-07-17"""
    def __init__(self, *, message: str, details: dict = None):
        super().__init__(message)
        self.message = message  # 小欧 2026-07-15: 补缺失实例属性,防_format_response_error访问e.message时AttributeError
        self.details = details or {}


def _resolve_exception(e: Exception) -> tuple:
    """解析异常→(用户消息, 错误类型) — 委托至SystemErrorClassifier统一分类 — 小沈 2026-05-28"""
    info = SystemErrorClassifier.get_error_info(e)
    msg = info["message"]
    err_type = info["code"]
    return msg, err_type


class ChatResponse:
    """聊天响应类 - 非流式响应
    2026-08-22 小欧 归一报告v1.25 6.4: model/provider 分离 → chat_model: ModelRef 结构承载
    (F8 禁 backward, 不留 self.model/self.provider 兼容别名)"""
    def __init__(self, content: str, chat_model: "ModelRef", error: Optional[str] = None,
                 reasoning: Optional[str] = None, tool_calls: Optional[List[Dict]] = None):
        self.content = content
        self.chat_model = chat_model   # 前导+model 命名铁律(设计要求4)
        self.error = error
        self.success = error is None
        self.reasoning = reasoning or ""
        self.tool_calls = tool_calls or []


class StreamChunk:
    """流式响应片段 — FC-only: tool_calls原生传递,不走JSON roundtrip — 小沈 2026-06-12; 小健 2026-06-17 新增usage
    2026-08-22 小欧 归一报告v1.25 6.4: 单字段 model(形态④缺provider) → chunk_model: ModelRef(补 provider)"""
    def __init__(self, content: str, chunk_model: "ModelRef", is_done: bool = False,
                 stream_error: Optional[str] = None, stream_error_type: Optional[str] = None,
                 reasoning: Optional[str] = None, is_reasoning: bool = False,
                 tool_calls: Optional[List[Dict]] = None,
                 raw_data: str = "",
                 usage: Optional[Dict] = None,
                 truncated: bool = False,  # #34 fix: 超时截断标记 — 小欧 2026-07-18
                 finish_reason: Optional[str] = None):  # 2026-07-19 小欧 新增: API最后chunk的finish_reason(stop/length/tool_calls)
        self.content = content
        self.chunk_model = chunk_model   # 前导+model; 补 provider(F8 不留 self.model 兼容别名)
        self.is_done = is_done
        self.stream_error = stream_error
        self.stream_error_type = stream_error_type
        self.reasoning = reasoning
        self.is_reasoning = is_reasoning
        self.tool_calls = tool_calls or []
        self.raw_data = raw_data
        self.usage = usage
        self.truncated = truncated
        self.finish_reason = finish_reason  # 2026-07-19 小欧


def create_cancelled_chunk(chunk_model: "ModelRef") -> StreamChunk:
    """创建取消响应片段 — 小健 2026-05-27; 2026-08-22 小欧 归一: 入参 model:str → chunk_model: ModelRef"""
    return StreamChunk(content="", chunk_model=chunk_model, is_done=True,
                       stream_error="Request cancelled",
                       stream_error_type="cancelled")


def create_error_chunk(chunk_model: "ModelRef", error: str, error_type: str = "http_error") -> StreamChunk:
    """创建错误响应片段 — 小健 2026-05-27; 2026-08-22 小欧 归一: 入参归一"""
    return StreamChunk(content="", chunk_model=chunk_model, is_done=True,
                       stream_error=error,
                       stream_error_type=error_type)


__all__ = [
    "ChatResponse",
    "StreamChunk",
    "LLMResponseError",
    "_resolve_exception",
    "create_cancelled_chunk",
    "create_error_chunk",
]
