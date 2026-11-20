# 媒体生成/输入链路架构索引

**目的**：一图看懂媒体相关的三条链路与扩展点，避免散落代码难读。维护人：小欧 2026-11-20

---

## 1. 三条互不相交的链路

媒体相关的代码分属三条**独立**链路，最易误读成"一个统一媒体底座"，实则职责完全不同：

### 链路 A — 生成链路（用户生图/生视频）
```
工具层 tools/media/generate_image.py、generate_video.py
  ↓ get_current_generate_callback()（tools/context.py 注入的回调）
编排层 services/agent/media_generate.py::invoke_generate
  ├─ _provider_credentials：按模型名定位 provider/api_base/key
  ├─ get_provider_adapter(provider)：取厂商适配器
  ├─ 素材公网化 public_image.upload_image（i2v 本地图）/ _resolve_image_source（i2i data URI）
  └─ 调 services/generation/generation_client.py
HTTP 出口 services/generation/generation_client.py
  ├─ adapter.prepare_image_body / prepare_video_body：请求方言
  ├─ httpx POST /images/generations（生图同步）/ /videos + 轮询（生视频异步）
  └─ adapter.parse_image_result / parse_video_*：响应方言
产物：公网 URL 直出，或 b64 经 media_generate 落盘为会话附件
```

### 链路 B — 输入 part 构造（模型"看懂"图片/视频/音频/文档）
```
config model_meta.input_modalities
  → services/agent/capability.py::profile_of（判定 native + transport 门控）
  → services/agent/media_payload.py::build_logical_part / to_wire_part
      （逻辑 part → 方言 part：image_url / input_audio / file / video_url）
  → 注入 LLM 请求
与链路 A 无共享代码。video_url 是多厂商共同支持的通用投递形状。
```

### 链路 C — 探测腿（验证模型生成能力）
```
services/model/model_service.py::probe_model_output
  → 复用链路 A 的 generation_client HTTP 出口（不传 adapter，走通用基类）
  → 只取 settled/evidence，不写产物
```

---

## 2. 扩展点：加新厂商要改什么

**核心原则**：协议通用就零定制；有差异就只加一个 adapter，引擎与工具层零改动（OCP）。

| 场景 | 做法 |
|---|---|
| 协议通用 | config 登记 model 即可，直接走通用引擎 |
| 请求方言不同（size 档位/字段名/输出格式位置） | adapter 覆写 `prepare_image_body` / `prepare_video_body` |
| 响应方言不同（产物/状态提取） | adapter 覆写 `parse_image_result` / `parse_video_status` / `parse_video_reason` / `parse_video_url` |
| 输入 part 形状不同（如 Gemini inline_data） | 才考虑输入侧方言钩子（当前无实测需求，不预先抽象） |

现有范例：`agnes.py`（生图档位+ratio）、`sensenova.py`（生图 WIDTHxHEIGHT）。覆写方法返回 `None` 即回退引擎通用启发式，只覆写有差异的钩子。

**通用能力边界**：生图=同步单请求，生视频=异步提交+轮询。若某厂商生图也异步（如通义），需扩展引擎任务分支，非仅覆写钩子可涵盖——当前未接入，YAGNI。

---

## 3. 分层依赖

```
llm/adapters（provider 差异钩子集合：鉴权/端点/门禁 + 生成请求响应方言）
    ↑ 依赖
services/generation（生成 HTTP 出口，协议无关）
    ↑ 依赖
services/agent（编排 media_generate / 输入构造 media_payload / capability）
    ↑ 回调注入（tools/context.py，避免 tools→services 反向依赖）
tools/media（工具层，零 services import）
```

无循环依赖；模态词归一下沉 `utils/modality.py` 供 model_service 与 capability 单向共用。
