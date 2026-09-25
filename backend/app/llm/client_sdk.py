
"""
LLM 客户端 SDK
Author: 小沈 - 2026-05-29

基础模块,被 BaseAIService 调用。
只支持 OpenAI 兼容格式的 API(/chat/completions 端点)。
SDK 只管发 HTTP 请求,不处理错误,异常原样抛出。

FC-only重构: 删除mode参数, tools不为None时始终注入 — 小沈 2026-06-11
编辑历史: 2026-07-16 小欧 request_stream 响应错误路径: >=400时记录响应体后raise_for_status(所有4xx/5xx可见错误原因)
编辑历史: 2026-07-16 小欧 M1 解决400错误根因不可见问题: 此前>=400仅把响应体写进服务器日志, 前端/用户只看到泛化文案"客户端错误:请求参数异常", 排障须翻数MB日志; 新增_extract_server_error_message解析OpenAI兼容错误信封{"error":{"message":...}}, >=400时抛HTTPStatusError并携带服务商真实错误文本(server_msg)。能力提升: 前端用户与错误记录可直接看到sensenova等真实错误原因(如参数被拒), 无需查日志即可定位根因
编辑历史: 2026-07-17 小欧 修复429/5xx限流日志污染: 可重试状态(429/5xx)由base_service L1重试处理, 降为WARNING; 仅不可重试客户端错误(400/401/403)记ERROR, 避免check_logs/测试误判FAIL
编辑历史: 2026-07-18 小欧 #33 fix: 兼容data:无空格格式
编辑历史: 2026-07-18 小欧 #37 fix: request新增request_timeout形参并传httpx.Timeout
编辑历史: 2026-07-28 小欧 BUG#1: 非流式请求必崩(AttributeError: _default_timeout undefined)。__init__ 漏存 self._default_timeout = read_timeout, request() 引用时崩溃。新增存储。
编辑历史: 2026-08-22 小欧 model结构化归一报告v1.25 6.4: LLMClient 构造 (provider, model) 分离入参 → llm_model: ModelRef
  单结构; base_url 取 llm_model.api_base(缺省回退 _default_base_url(llm_model.provider)); 请求体拼
  self.llm_model.model 属裸单值调API场景(设计要求4允许并注释)
编辑历史: 2026-08-23 小欧 三堂会审复核加固(P2): _base_url 回退链补 provider or "openai" 兜底——
  防空 provider 时 _DEFAULT_URLS.get("","") 返回空串致 httpx base_url 为空(防御性语义与归一前对齐, 不弱化)
编辑历史: 2026-09-20 小欧 P5+C-1: ①P5(13.6) LLM软配额信号量(_soft_pool_semaphore, asyncio.Semaphore 惰性初始化,
  排队超时保底放行, request_stream 入口自动获取/finally释放); ②C-1(RED-C-1) 新增 _current_response 追踪
  在飞流式HTTP响应(request_stream 进入置位/finally清空) + cancel() 方法 aclose 强关在飞流
  ——BaseAIService.cancel 优先委托此处直达HTTP层(原来 cancel 关闭的 _current_response 恒 None 假日志)
编辑历史: 2026-09-20 小欧 三堂会审BUG-04修复: cancel()中aclose后立即清_current_response引用, 防finally/__aexit__二次关闭(double-close)
编辑历史: 2026-09-22 小欧 - [61] constants.py 配置化迁移：import 改别名 + soft_pool_wait_timeout/max_connections/max_keepalive 改读 tuning 配置
编辑历史: 2026-09-23 小欧 - [64] LLM补充采样参数: _build_request_body/request/request_stream 签名加 top_p/frequency_penalty/presence_penalty 三参(仿 seed None透传写法)
编辑历史: 2026-09-23 小欧 - wiring假保存修复: __init__/request_stream 两处 httpx.Timeout 的 connect/write/pool 改读 tuning.llm_net.* 配置兜底常量（此前设置页可改实际不生效）
编辑历史: 2026-09-24 小欧 - [66]v3.6 流式主路径漏改修复+整段快照保底: ①request_stream 循环逐帧把 muse /responses 事件归一为 chat 形 choices[0].delta 行（增量优先、整段快照仅"全程无对应增量"时作保底唯一来源, 双布尔去重）, 供 BaseAIService 既有 chat 解析链一字不改读通——agent 全链(react_step→BaseAIService.request_stream)对 muse 不再空响应; ②collect 删 is_responses 分支回归纯 chat 消费(单通道单归一心智); ③_norm_responses_delta 新增 content_full 文本整段快照保底识别(output_text.done/content_part.done/output_item.done message/completed); ④删 _responses_stream_frame 薄壳(KISS-DIRECT, 决策内联循环)
编辑历史: 2026-09-23 小欧 - [66]v3.7 适配层接入: ①import get_provider_adapter + __init__ 注入 self._adapter/self._static_headers(shared_client 分支复用全局池头); ②headers= 改用 static_headers(默认仅 Authorization, 行为==现状); ③request/request_stream 发送点接 per_request_headers + force_stream 流式收集分支 + _request_via_stream_collect(非流式入口经 request_stream 收集返回, 覆盖 zen 门禁 stream:true); ④>=400 分支消费 adapter.error_message_map(zen 403/426 友好文案); ⑤gate body/端点路由/协议位经 _adapt_request 单点(muse- 前缀→/responses)
编辑历史: 2026-09-24 小欧 - [66]v3.7.1 模块化搬迁: ①八个 /responses 归一成员(_norm_responses_delta/_fold_emit_delta/_chat_frame/_DeltaFoldState/_responses_completed_eval 等)整体迁出至 responses_stream.py(零行为变更, 与 chat 直通通道物理隔离); ②request/request_stream 重复块函数化收敛: _acquire_soft_pool(软配额排队)/_adapt_request(gate+端点+动态头+协议判定单点)/_raise_http_error(4xx/5xx 日志分级+错误提取+error map); ③协议位 _is_responses 收敛 _adapt_request 唯一判定(消除 2 处 endswith 重复嗅探)
编辑历史: 2026-09-25 小欧 - [70] ConnectionScope连接池统一所有者(3.1): ①新增 inspect/threading 导入(池 close 判定可等待对象 + 池级线程锁); ②新增 _SharedClientPool/SharedClientLease 两类(引用计数 lease 核心: 归零关闭 close_on_zero/释放幂等/池级锁, 落户自[70]素材原样); ③acquire 增 client.is_closed 检查(底层被池外 aclose 后禁借, 偿还[69] 1.2.3⑥) + close 失败 warning 带池标识(多代并存可定位); ④LLMClient 新增 relinquish_ownership() 与 client property, close() 改三态收口(移交后 no-op/独占池 aclose/已关闭不抛), _owns_client 判据全部收敛回本类
编辑历史: 2026-09-25 小欧 - [70] v1.11 代码审查修正(YAGNI): _SharedClientPool.closing property 全仓零消费点(含测试)按 YAGNI 删除; _closing 实例标志保留(acquire/release 内部判据仍在用) — 小欧 2026-09-25
"""

import asyncio  # 2026-09-20 小欧 P5: 软配额信号量 — 小欧-2026-09-20
import httpx
import inspect  # [70] SharedClientPool.close 判定可等待对象 — 小欧-2026-09-25
import json
import threading  # [70] SharedClientPool 池级线程锁(多线程 acquire/release) — 小欧-2026-09-25
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.constants import (
    DEFAULT_CONNECT_TIMEOUT as _D_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT as _D_READ_TIMEOUT,
    DEFAULT_WRITE_TIMEOUT as _D_WRITE_TIMEOUT,
    DEFAULT_POOL_TIMEOUT as _D_POOL_TIMEOUT,
    LLM_MAX_CONNECTIONS as _D_MAX_CONNECTIONS,
    LLM_MAX_KEEPALIVE as _D_MAX_KEEPALIVE,
)
from app.config import get_config
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.logger import logger
from app.llm.adapters import get_provider_adapter   # 适配层查询 — 小欧 2026-09-23
from app.llm.reasoning import extract_reasoning_from_chunk   # diff五 流式收集复用三字段链 — 小欧 2026-09-23
from app.llm.responses_stream import (   # v3.7.1 模块化: /responses 协议归一独立模块, 与 chat 直通通道隔离 — 小欧 2026-09-24
    _chat_frame, _DeltaFoldState, _fold_emit_delta,
    _norm_responses_delta, _responses_completed_eval,
)

# 可重试 HTTP 状态: 429限流 / 5xx服务端瞬时错误, 由 base_service L1 重试处理 — 小欧 2026-07-17
_RETRYABLE_STATUS = (429, 500, 502, 503, 504)

# ============================================================
# [70] 共享连接池 lease 核心(引用计数) — 落户自 doc-9月优化/[70]素材-lease核心 原样吸收
# 归零关闭(close_on_zero)/释放幂等(lease._released)/池级线程锁 — 小欧 2026-09-25
# ============================================================

class _SharedClientPool:
    def __init__(self, client: Any, close_on_zero: bool = True) -> None:
        self.client = client
        self.close_on_zero = close_on_zero
        self._ref_count = 1
        self._closing = False
        self._lock = threading.Lock()

    def acquire(self) -> "SharedClientLease":
        with self._lock:
            if self._closing:
                raise RuntimeError("共享 httpx 客户端已关闭，不能继续获取 lease")
            if getattr(self.client, "is_closed", False):
                # [70] v1.4 审核新增: 底层被池外 aclose 后禁借, 防借出即炸(偿还 [69] 1.2.3⑥/2.2 池约束④) — 小欧-2026-09-25
                raise RuntimeError("共享 httpx 客户端已被外部关闭，不能继续获取 lease")
            self._ref_count += 1
        return SharedClientLease._from_pool(self)

    def release(self) -> bool:
        with self._lock:
            if self._closing or self._ref_count <= 0:
                return False
            self._ref_count -= 1
            if self._ref_count != 0 or not self.close_on_zero:
                return False
            self._closing = True
            return True

    @property
    def ref_count(self) -> int:
        with self._lock:
            return self._ref_count

    async def close(self) -> None:
        if getattr(self.client, "is_closed", False) is True:
            return
        try:
            result = self.client.aclose()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.warning(f"[LLM] 共享 httpx 客户端关闭失败(pool={id(self):#x}): {exc}")  # [70] v1.4 审核新增: warning 带池标识, 多代并存时可定位(2.7④) — 小欧-2026-09-25


class SharedClientLease:
    """共享连接池的一次引用；释放幂等，最后一个引用负责关闭。"""

    def __init__(self, client: Any, close_on_zero: bool = True) -> None:
        self._pool = _SharedClientPool(client, close_on_zero=close_on_zero)
        self._released = False

    @classmethod
    def _from_pool(cls, pool: _SharedClientPool) -> "SharedClientLease":
        lease = cls.__new__(cls)
        lease._pool = pool
        lease._released = False
        return lease

    @property
    def client(self) -> Any:
        return self._pool.client

    @property
    def ref_count(self) -> int:
        return self._pool.ref_count

    @property
    def is_released(self) -> bool:
        return self._released

    def acquire(self) -> "SharedClientLease":
        if self._released:
            raise RuntimeError("已释放的 lease 不能继续获取引用")
        return self._pool.acquire()

    async def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._pool.release():
            await self._pool.close()


def _build_request_body(
    messages: List[Dict],
    model: str,
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,  # 新增 — 小欧 2026-09-23
    frequency_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
    presence_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
    seed: Optional[int] = None,
    tools: Optional[List[Dict]] = None,
    tool_choice: Optional[str] = None,
    stream: bool = False,
    parallel_tool_calls: Optional[bool] = None,
    stream_options: Optional[Dict] = None,
    extra_body: Optional[Dict] = None,
) -> Dict:
    """统一构建 LLM 请求体 — FC-only: 无mode参数 — 小沈 2026-06-11; 小沈 2026-06-17 新增parallel_tool_calls; 小健 2026-06-17 新增stream_options; 小欧 2026-07-09 新增extra_body"""
    body = {"model": model, "messages": messages}
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    if seed is not None:
        body["seed"] = seed
    # ✅ 仿 seed 现写法：None 即不拼（旁路），有值才拼 — 小欧 2026-09-23
    if top_p is not None:
        body["top_p"] = top_p
    if frequency_penalty is not None:
        body["frequency_penalty"] = frequency_penalty
    if presence_penalty is not None:
        body["presence_penalty"] = presence_penalty
    if stream:
        body["stream"] = True
        if stream_options is not None:
            body["stream_options"] = stream_options
    if tools:
        body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice
        
        if parallel_tool_calls is None:
            parallel_tool_calls = True  # 执行层(action_handler)的_has_conflict控制并发安全 — 北京老陈 2026-07-04
        
        body["parallel_tool_calls"] = parallel_tool_calls
    
    if extra_body:
        body.update(extra_body)
    
    return body


def _extract_server_error_message(body_text: str) -> str:
    """从LLM服务商错误响应体提取真实错误(OpenAI兼容信封 {"error":{"message":...}}) — 小欧 2026-07-16"""
    if not body_text:
        return ""
    try:
        data = json.loads(body_text)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            msg = err.get("message")
            if msg:
                return str(msg)[:500]
        if isinstance(err, str):
            return err[:500]
    except (ValueError, TypeError):
        pass
    return body_text[:500]


_soft_pool_semaphore = None  # 2026-09-20 小欧 P5: 延迟初始化, 绑定首次使用时的 event loop — 小欧-2026-09-20
_SOFT_POOL_WAIT_TIMEOUT = get_config().get("tuning.concurrency.soft_pool_wait_timeout", 30.0)  # 软配额排队等待上限(秒): 超时保底放行(不拒绝不降级) — 小欧-2026-09-20


def _get_soft_pool_semaphore():
    """惰性获取软配额信号量(避免模块级创建绑定错误 loop) — 小欧 2026-09-20"""
    global _soft_pool_semaphore
    if _soft_pool_semaphore is None:
        _soft_pool_semaphore = asyncio.Semaphore(get_config().get("tuning.llm_net.max_connections", _D_MAX_CONNECTIONS))
    return _soft_pool_semaphore


class LLMClient:
    """LLM 客户端实例 - 小沈 2026-06-09
    2026-08-22 小欧 归一报告v1.25 6.4: (provider, model) 分离入参 → llm_model: ModelRef 单结构
    (F8 不留 self.model/self.provider 兼容别名); 请求体拼 model 单值属裸单值场景(设计要求4允许)"""

    def __init__(
        self,
        llm_model: ModelRef,
        api_key: str,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        shared_client: Optional[httpx.AsyncClient] = None,  # 2026-09-20 小欧 C1: 共享连接池注入, 快照复用不 new — 小欧-2026-09-20
    ):
        self.llm_model = llm_model   # 前导+model 命名铁律 — 小欧 2026-08-22
        self._api_key = api_key
        # 三堂会审复核加固(小欧 2026-08-23): 保留原 provider or "openai" 兜底语义(防空 provider 时
        # _default_base_url 返回空串致 httpx base_url 为空; 当前可达路径虽恒非空, 防御不弱化)
        self._base_url = llm_model.api_base or self._default_base_url(llm_model.provider or "openai")

        read_timeout = float(timeout) if timeout else _D_READ_TIMEOUT
        self._default_timeout = read_timeout
        self._owns_client = shared_client is None   # 真连接池仅全局单例持有, 快照共享不重复建 — 小欧-2026-09-20
        self._current_response: Optional[httpx.Response] = None  # C-1(小欧 2026-09-20): 在飞流式HTTP响应, 供 cancel() 直达HTTP层强关 — 小欧-2026-09-20
        # 适配层消费: 按 provider 取适配实例(未注册=默认基类, 行为==现状); 静态头全生命周期算一次
        # shared_client 分支(同provider快照复用全局池)不重算头——全局池建池时已带 static_headers;
        # 跨provider 时 resolver 置 shared_client=None 走 else 新建, 头由 static_headers 注入 — 小欧 2026-09-23
        self._adapter = get_provider_adapter(llm_model.provider or "")
        self._static_headers = self._adapter.static_headers(api_key)
        if shared_client is not None:
            self._client = shared_client
        else:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=float(get_config().get("tuning.llm_net.connect_timeout", _D_CONNECT_TIMEOUT)),  # 小欧 2026-09-23 wiring假保存修复
                    read=read_timeout,
                    write=float(get_config().get("tuning.llm_net.write_timeout", _D_WRITE_TIMEOUT)),  # 小欧 2026-09-23 wiring假保存修复
                    pool=float(get_config().get("tuning.llm_net.pool_timeout", _D_POOL_TIMEOUT)),  # 小欧 2026-09-23 wiring假保存修复
                ),
                limits=httpx.Limits(
                    max_connections=get_config().get("tuning.llm_net.max_connections", _D_MAX_CONNECTIONS),
                    max_keepalive_connections=get_config().get("tuning.llm_net.max_keepalive", _D_MAX_KEEPALIVE),
                ),
                headers=self._static_headers,   # zen: UA/session 等静态头; 默认: 仅 Authorization — 小欧 2026-09-23
                base_url=self._base_url,
            )

    _DEFAULT_URLS = {
        "deepseek": "https://api.deepseek.com",
        "qwen": "https://dashscope.aliyuncs.com/compatible-mode",
        "ollama": "http://localhost:11434",
    }

    def _default_base_url(self, provider: str) -> str:
        """根据 provider 返回默认 API 地址 — 小健 2026-06-17 OCP: 优先配置,其次硬编码默认"""
        try:
            custom_urls = get_config().get("llm", {}).get("provider_urls", {})
            if provider in custom_urls:
                return custom_urls[provider]
        except Exception:
            logger.warning(f"[client_sdk] 读取自定义URL配置失败: provider={provider}")
        return self._DEFAULT_URLS.get(provider, "")

    async def _acquire_soft_pool(self, _sem: Optional[asyncio.Semaphore] = None) -> bool:
        """排队获取软配额信号量: 超时保底放行(不拒绝不降级, 防长时间卡等) — 小欧 2026-09-24 v3.7.1
        函数化(DRY: request/request_stream 两处完全相同的排队块收敛为单点)。"""
        sem = _sem or _get_soft_pool_semaphore()
        try:
            await asyncio.wait_for(sem.acquire(), timeout=_SOFT_POOL_WAIT_TIMEOUT)
            return True
        except asyncio.TimeoutError:
            logger.warning(f"[LLM] 软配额排队超{_SOFT_POOL_WAIT_TIMEOUT}s 保底放行")
            return False

    def _adapt_request(self, body: Dict) -> tuple:
        """gate 允许 + 端点分派 + 动态头 + 协议判定(非流式/流式共用) — 小欧 2026-09-24 v3.7.1; 模块化收敛协议判定单点 2026-09-24
        函数化(DRY: request/request_stream 两处 gate/端点/头组装重复); 返回含 _is_responses——
        v3.7.1 模块化后曾 2 处 endswith("/responses") 嗅探(请求侧转换 + 主循环分派), 收敛为本函数唯一判定点。"""
        body = self._adapter.ensure_gate_body(body)   # zen: 补 bash/read stub + stream:true; 默认原样 — 小欧 2026-09-23
        _endpoint = self._adapter.endpoint_for(self.llm_model.model)   # zen: muse- 前缀→/responses(+base=zen/v1→/zen/v1/responses); 默认/chat/completions
        _is_responses = _endpoint.endswith("/responses")   # 协议判定唯一来源 — 小欧 2026-09-24
        if _is_responses:
            body = self._adapter.to_responses_body(body, self.llm_model.model)   # messages→input, 双层tools→flat
        return _endpoint, body, self._adapter.per_request_headers(), _is_responses

    def _raise_http_error(self, response: httpx.Response, body_text: str) -> None:
        """>=400 错误响应体记录 + 服务商真实错误提取 + 抛错(request/request_stream 共用) — 小欧 2026-09-24 v3.7.1
        函数化(DRY: 两处 4xx/5xx 处理重复): 可重试状态(429限流/5xx服务端瞬时)记 WARNING 交 base_service L1 重试,
        仅不可重试客户端错误(400/401/403等)记 ERROR, 避免 check_logs/测试误判 FAIL。"""
        if response.status_code >= 400:
            if response.status_code in _RETRYABLE_STATUS:
                logger.warning(f"[LLM] HTTP {response.status_code} 响应体(可重试, base_service将重试): {body_text}")
            else:
                logger.error(f"[LLM] HTTP {response.status_code} 响应体: {body_text}")
            server_msg = _extract_server_error_message(body_text)
            # 适配层错误消息映射消费(zen 403/426 友好文案; 默认空 dict=不干预, 走全局分类) — 小欧 2026-09-17
            _adapter_msg = self._adapter.error_message_map().get(response.status_code)
            if _adapter_msg:
                server_msg = f"{_adapter_msg}（服务端: {server_msg}）" if server_msg else _adapter_msg
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code} 错误: {server_msg or '（服务商未返回错误详情）'}",
                request=response.request, response=response)

    async def request(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        frequency_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        presence_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        seed: Optional[int] = None,
        extra_body: Optional[Dict] = None,
        request_timeout: Optional[int] = None,  # #37 fix: per-request timeout — 小欧 2026-07-18
    ) -> Dict[str, Any]:
        """非流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11; 小欧 2026-07-09 新增extra_body; #37 新增request_timeout"""
        if self._adapter.force_stream():
            # zen True: 门禁强制 stream:true, 非流式语义改走流式收集(返回形态与 request 同构) — 小欧 2026-09-23
            # 默认 False: 直通现有非流式逻辑, 行为==现状
            return await self._request_via_stream_collect(
                messages=messages, tools=tools, tool_choice=tool_choice,
                max_tokens=max_tokens, temperature=temperature, top_p=top_p,
                frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
                seed=seed, extra_body=extra_body, request_timeout=request_timeout,
            )
        body = _build_request_body(
            messages=messages, model=self.llm_model.model,   # 裸单值调API(设计要求4允许) — 小欧 2026-08-22
            max_tokens=max_tokens, temperature=temperature, top_p=top_p,  # 新增 — 小欧 2026-09-23
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,  # 新增 — 小欧 2026-09-23
            seed=seed,
            tools=tools, tool_choice=tool_choice, stream=False,
            extra_body=extra_body,
        )
        _to = httpx.Timeout(request_timeout) if request_timeout else self._default_timeout
        # 软配额: 排队超时保底放行(非硬闸不 503 不降级, 防长时间卡等) — 小欧-2026-09-20
        _sem = _get_soft_pool_semaphore()
        _acquired = await self._acquire_soft_pool(_sem)
        try:
            _endpoint, body, _dyn_headers, _ = self._adapt_request(body)   # v3.7.1 函数化; 协议位非流式不消费 — 小欧 2026-09-24
            response = await self._client.post(_endpoint, json=body, timeout=_to,
                                               headers=_dyn_headers or None)
        finally:
            if _acquired:
                _sem.release()
        if response.status_code >= 400:
            self._raise_http_error(response, response.text)   # v3.7.1 函数化 — 小欧 2026-09-24
        return response.json()

    async def _request_via_stream_collect(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        seed: Optional[int] = None,
        extra_body: Optional[Dict] = None,
        request_timeout: Optional[int] = None,
    ) -> Dict[str, Any]:
        """force_stream 收集: 复用 request_stream 的 SSE, 累积为 request() 同构非流式响应 — 小欧 2026-09-23
        返回形态镜像 base_service.request 消费点: choices[0].message.{content,tool_calls,reasoning*}。
        端点分派(v3.3): muse 走 /responses(+base=zen/v1→/zen/v1/responses, SSE 事件形), 经 _norm_responses_delta 归一为 delta。"""
        content = ""
        reasoning = ""
        tool_acc: Dict[int, Dict[str, Any]] = {}   # 按 index 合并 — 镜像 base_service._extract_tool_calls 累加器
        finish_reason: Optional[str] = None
        async for raw in self.request_stream(
            messages=messages, tools=tools, tool_choice=tool_choice,
            max_tokens=max_tokens, temperature=temperature, top_p=top_p,
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
            seed=seed, stream_options=None, request_timeout=request_timeout, extra_body=extra_body,
        ):
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            # v3.6 小欧 2026-09-24: muse 事件已由 request_stream 循环内逐帧归一为 chat 形行,
            # 原 is_responses 分支删除, 此处纯 chat 消费(单通道单归一心智)
            choices = data.get("choices") or [{}]
            delta = choices[0].get("delta") or {}
            if delta.get("content"):
                content += delta["content"]
            rc = extract_reasoning_from_chunk(delta)   # 三字段链: reasoning_content/reasoning/thinking — 复用全局
            if rc:
                reasoning += rc
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                entry = tool_acc.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                if tc.get("id"):
                    entry["id"] = tc["id"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    entry["name"] = fn["name"]
                if fn.get("arguments"):
                    entry["arguments"] += fn["arguments"]
            fr = choices[0].get("finish_reason")
            if fr:
                finish_reason = fr
        # 幽灵过滤: 仅有 id 无 name 的残余 delta 丢弃 — 镜像 base_service._extract_tool_calls #38
        tool_calls_list = [
            {"id": acc.get("id"), "type": "function",
             "function": {"name": acc["name"], "arguments": acc["arguments"]}}
            for _, acc in sorted(tool_acc.items()) if acc.get("name")
        ]
        message: Dict[str, Any] = {"content": content}
        if reasoning:
            message["reasoning_content"] = reasoning
        if tool_calls_list:
            message["tool_calls"] = tool_calls_list
        if finish_reason is None:
            finish_reason = "tool_calls" if tool_calls_list else "stop"
        return {"choices": [{"index": 0, "message": message, "finish_reason": finish_reason}]}

    async def request_stream(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        frequency_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        presence_penalty: Optional[float] = None,  # 新增 — 小欧 2026-09-23
        seed: Optional[int] = None,
        stream_options: Optional[Dict] = None,
        request_timeout: Optional[int] = None,
        extra_body: Optional[Dict] = None,
    ) -> AsyncGenerator[str, None]:
        """流式请求 — FC-only: 无mode参数 — 小沈 2026-06-11; 小健 2026-06-17 新增stream_options; 小欧 2026-07-09 新增extra_body"""
        body = _build_request_body(
            messages=messages, model=self.llm_model.model,   # 裸单值调API(设计要求4允许) — 小欧 2026-08-22
            max_tokens=max_tokens, temperature=temperature, top_p=top_p,  # 新增 — 小欧 2026-09-23
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,  # 新增 — 小欧 2026-09-23
            seed=seed,
            tools=tools, tool_choice=tool_choice, stream=True,
            stream_options=stream_options,
            extra_body=extra_body,
        )
        # 结构化超时: request_timeout 仅作用于 read 阶段, connect/write/pool 读 tuning.llm_net.* 配置。
        # 避免浮点标量将四者全部拉长 (浮点标量 = 全阶段统一值, 会误将 connect 也拉长至 90+秒)。
        # request_timeout 由 base_service 传入 (provider.timeout + 重试递增),
        # 未显式传入时用 _D_READ_TIMEOUT 兜底 — 小欧 2026-07-13; connect/write/pool 改读配置 — 小欧 2026-09-23
        _timeout = httpx.Timeout(
            connect=float(get_config().get("tuning.llm_net.connect_timeout", _D_CONNECT_TIMEOUT)),
            read=float(request_timeout) if request_timeout is not None else _D_READ_TIMEOUT,
            write=float(get_config().get("tuning.llm_net.write_timeout", _D_WRITE_TIMEOUT)),
            pool=float(get_config().get("tuning.llm_net.pool_timeout", _D_POOL_TIMEOUT)),
        )
        _sem = _get_soft_pool_semaphore()
        _acquired = await self._acquire_soft_pool(_sem)   # v3.7.1 函数化(DRY) — 小欧 2026-09-24
        try:
            _endpoint, body, _dyn_headers, _is_responses = self._adapt_request(body)   # 协议判定单点(见 _adapt_request) — 小欧 2026-09-24
            async with self._client.stream("POST", _endpoint, json=body, timeout=_timeout,
                                           headers=_dyn_headers or None) as response:
                # C-1(小欧 2026-09-20): 记录在飞流式响应, BaseAIService 镜像后供 cancel() 直达HTTP层强关 — 小欧-2026-09-20
                self._current_response = response
                # 记录所有 4xx/5xx 错误响应体(>=400), 定位错误原因 — 小欧 2026-07-16
                if response.status_code >= 400:
                    response_body = await response.aread()   # 仅错误路径读 body(随后抛错终止, 不进流式读取) — 小欧 2026-07-16
                    self._raise_http_error(response, response_body.decode("utf-8", errors="replace"))   # v3.7.1 函数化 — 小欧 2026-09-24
                _state = _DeltaFoldState() if _is_responses else None   # 折叠状态仅 responses 协议需要(chat 通道不实例化) — 小欧 2026-09-24
                async for line in response.aiter_lines():
                    if line.startswith("data:"):  # #33 fix: 兼容无空格 data: — 小欧 2026-07-18
                        _body = line[len("data:"):].lstrip()
                        if _body.strip() == "[DONE]":
                            break
                        if not _is_responses:
                            yield _body
                            continue
                        # v3.6 responses 事件逐帧归一(小欧 2026-09-24): 产物为 chat 形 choices[0].delta 行,
                        # 供 base_service/_request_via_stream_collect 既有 chat 解析链一字不改读通;
                        # v3.7.1(小欧 2026-09-24) 循环只做解析+落底(_chat_frame): 普通事件决策全在
                        # _fold_emit_delta(文本/快照/推理/工具去重状态机), completed 走单遍分支(文本快照+信令同遍)。
                        try:
                            _ev = json.loads(_body)
                        except (ValueError, TypeError):
                            _ev = None
                        if not isinstance(_ev, dict):
                            yield _body   # 非 JSON 行原样透传(#7 防内容丢失)
                            continue
                        if _ev.get("type") == "response.completed":
                            # v3.7.1 终帧: 单遍扫描 output 得文本快照+finish_reason/usage, 与 chat 流末帧同构 — 小欧 2026-09-24
                            _cfull, _meta = _responses_completed_eval(_ev)
                            if _cfull and not _state.saw_text_delta:
                                yield _chat_frame({"content": _cfull})
                            yield _chat_frame({}, finish_reason=_meta["finish_reason"], usage=_meta.get("usage"))
                            continue
                        _emit = _fold_emit_delta(_norm_responses_delta(_ev), _state)
                        if _emit:
                            yield _chat_frame(_emit)
        finally:
            # C-1(小欧 2026-09-20): 流结束/异常清在飞响应(镜像随流清), 防悬挂旧HTTP响应 — 小欧-2026-09-20
            self._current_response = None
            if _acquired:
                _sem.release()

    async def cancel(self):
        """强制取消在飞流式请求 — C-1(小欧 2026-09-20): 直达HTTP层关闭流式响应, 供 BaseAIService.cancel 委托。
        RED-C-1 根因: 此前 cancel() 关闭的 _current_response 恒 None(从未赋值), 取消只能等 chunk 级轮询, 假日志。
        BUG-04修复(小欧 2026-09-20): aclose后立即清引用, 防finally/__aexit__二次关闭(double-close)。"""
        resp = self._current_response
        if resp is not None:
            self._current_response = None  # BUG-04: 立即清空, 阻止finally块重复关闭
            try:
                await resp.aclose()
                logger.info("[LLMClient.cancel] 流式HTTP响应已强制关闭")
            except Exception as e:
                logger.warning(f"[LLMClient.cancel] 关闭流式响应失败: {e}")

    def relinquish_ownership(self) -> None:
        """移交底层 httpx 客户端所有权(本实例不再关闭) — [70] ConnectionScope.ensure_pool 调用 — 小欧 2026-09-25
        幂等: 重复移交无害; 移交后 close() 对共享池变 no-op, 实例仍保留使用引用(不丢连接)。"""
        self._owns_client = False

    @property
    def client(self) -> httpx.AsyncClient:
        """公开底层 httpx 客户端 — [70] 替代跨层摸 _client 私有字段(欠账①) — 小欧 2026-09-25"""
        return self._client

    async def close(self):
        """关闭客户端,释放连接池 - 小沈 2026-06-09
        [70] 三态收口(小欧 2026-09-25): _owns_client=False(共享池/已移交) → no-op(池归 ConnectionScope
        引用计数管理); 独占池 → aclose(带 is_closed 双保险)。_owns_client 判据全部收敛回本类(欠账①)。"""
        if not self._owns_client:
            return
        if getattr(self._client, "is_closed", False):
            return
        await self._client.aclose()

    # 【P1-22修复】添加异步上下文管理器,防止AsyncClient连接池泄漏 — chendyg 2026-06-26
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


def create_llm_client(
    llm_model: ModelRef,
    api_key: str,
    base_url: Optional[str] = None,
    timeout: Optional[int] = None,
    shared_client: Optional[httpx.AsyncClient] = None,  # 2026-09-20 小欧 C1 透传 — 小欧-2026-09-20
) -> LLMClient:
    """创建 LLM 客户端 — 唯一入口 - 小沈 2026-06-09; 2026-08-22 小欧 归一: 入参 llm_model: ModelRef"""
    return LLMClient(llm_model=llm_model, api_key=api_key, base_url=base_url, timeout=timeout, shared_client=shared_client)

