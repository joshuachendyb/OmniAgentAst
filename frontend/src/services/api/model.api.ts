// 编辑历史: 2026-09-20 小强 - 新建：模型管理 API（与 config.api.ts 同模式；current_model_ref 复用 SessionModelOverride）
// 编辑历史: 2026-09-21 小强 - deleteProvider 返回类型补齐 mtime(ModelMutationResult, 与 deleteModel 同构、后端同样返回 mtime)，消除表单 union 后 res.mtime 的 TS 报错 — 小强-2026-09-21
// 2026-09-21 小欧 - 实施：addProvider 参数扩 api_key
// 2026-09-21 小欧 - ProviderEntry 补 max_retries 字段（对齐后端 GET /models 返回 max_retries）
// 2026-09-22 小欧 - 实施 ModelEntry 补 param_options?: Record<string,string[]>（对齐后端 GET /models
//   返回的三层解析 param_options，前端读链第一站；缺此字段 useSettings 四通道无数据来源）
// 2026-09-22 小欧 - 实施：①addModel 入参补 param_options?: Record<string,string[]>（勾选即带入，
//   添加口模板区勾选项透传到 POST /models 落盘）；②updateModel Pick 补 'param_options'（3.2(7)，
//   ModelEntry 加该字段后 Pick 缺它 TS 拒收 param_options——后端已校验+落盘，前端类型须同步放开）
// 2026-09-22 小欧 - 实施：ProviderConfigPatch 补 max_retries/label、addProvider 入参补
//   timeout/max_retries（对齐后端 ProviderConfigUpdate/ProviderAddRequest DTO——前端实际发送的字段
//   须在 TS 类型有声明，否则类型保护失效；创建 Provider 弹窗可自定义超时/重试）
// 2026-09-22 小欧 - 实施：ProviderEntry 补 param_types 元数据（动态字段 schema 源）
// 2026-09-24 小欧 - updateModel data 扩 remove_params?: string[]（②参数行 × 删除键级通道，
//   PUT /models body 白名单字段，后端 update_model 先删后 merge）- 小欧-2026-09-24
// 2026-09-24 小欧 - 模型库：类型补 RemoteModelItem/RemoteModelsResponse/ReplaceModelsResult，
//   方法补 fetchRemoteModels（GET remote-models）/replaceModels（PUT models 替换写入）- 小欧-2026-09-24
// 2026-09-26 小欧 - 落地:
//   ①ProviderEntry.api_key 改三键恒定 {configured, prefix, suffix} —— 原类型 {configured, suffix} 撒谎
//     （后端未配置时只返 {configured:false}，无 suffix 键）；第七与十二两章改同一处，按设计合并一次实施
//   ②RemoteModelsResponse 补 status_code?/category? 两字段（设计文档错误分类，前端据此分两套文案）
//   ③新增 testConnection(provider, probeKey?) —— POST test-connection，body 传待测 key；
//     刻意不用 GET query（query 会进浏览器历史与服务器 access log，明文 key 留痕）— 小欧-2026-09-26
// 2026-09-29 小欧 - RemoteModelItem 补 6 字段：后端改为下发模型元数据(价格/上下文/能力/模态)，
//   前端原靠 id.includes('-free') 猜免费，实测 OpenRouter 460 个命中 0 — 小欧-2026-09-29
// 2026-10-03 小欧 - RemoteModelItem 补 free/stability（AMD 实测下发，此前被解析层丢弃）— 小欧 2026-10-03
// 2026-10-05 22:16:38 小欧 - RemoteModelItem 补 max_output_length/input_modalities/output_modalities/
//   supported_features（后端厂商适配新增并已归一）：类型须与后端 DTO 逐字段对齐，否则消费方读不到
//   实测值（SenseNova 顶层下发 modalities、OpenRouter 嵌 architecture，归一后统一读 input_modalities）
//   — 小欧 2026-10-05
// 编辑历史: 2026-10-10 小欧 - 文档[16] ModelModals 底部加模型: addProvider 入参补 models?: string[] 透传
//   （后端 ProviderAddRequest.models 原生支持，一次调用建完 Provider+模型，无半成功窗口）
// 2026-10-10 小欧 - 新增 ZenithFree 双路验证三接口（北京老陈 2026-10-10）：zenVerify 触发双路验证
//   （两套方法各跑一遍远端最新免费模型并对比），zenVerifyReports / zenVerifyReport 取历史报告。
//   zenVerify 耗时长（免费模型 20+ × 双路并发 5），故显式放宽超时到 600s；后两条为普通读接口，
//   不加超时。本板块行内注释已按规矩上提归并 — 小欧-2026-10-10
// 编辑历史: 2026-10-11 07:33:53 小欧 - 对齐后端 DTO publish_time: 增 publish_time?: string | null(真发布时间, created 全假不可用; 不下发则 undefined) — 小欧-2026-10-11
// 编辑历史: 2026-10-11 小欧 - 对齐后端 DTO effort_levels/effort_default: 增 effort_levels?: string[](推理强度档位)/effort_default?: string | null(默认值); 非 DeepSeek 不返回 → 空数组/undefined; 北京老陈令两个都加 — 小欧-2026-10-11
// 2026-10-26 18:45:00 - 小欧 - replaceModels 类型 Pick 增 max_output_length（对齐后端 DTO，保存时一并持久化输出上限）。
// ModelEntry 增 max_output_length（从 model_meta 读取，供 LLM 调用链设置 max_tokens 上限）— 小欧-2026-10-26
// 2026-11-01 小欧 - 键名统一（北京老陈指令：一个概念一个名字，不留别名）:
//   ①ModelEntry.default_params → model_params（与后端 yaml 真源同名）；
//   ②ModelEntry 补 context_length（后端本次才开始下发 model_meta 的厂商声明窗口）；
//   ③ProviderConfigPatch.base_url → api_base，删 retry_times（只留 max_retries）。— 小欧-2026-11-01
// 2026-11-08 小欧 - 能力字段拆双维度: ModelEntry/新增模型体 capabilities → input_modalities + output_modalities — 小欧-2026-11-08
// 2026-11-08 小欧 - 补 media 探测块(ModelEntry.media + probeMedia): 记录模型接受哪种媒体传输 — 小欧-2026-11-08
// 2026-11-09 小欧 - MediaProbe 补 url_err(厂商抓图失败≠地址为空没发)与 inline_ms/url_ms/inline_tokens/url_tokens(②验证tip按腿显示) — 小欧-2026-11-09
// 2026-11-09 小欧 - 生成验证([15]): MediaProbe 扩 generate.image/video 双腿 + probeOutput 接口(视频异步, 显式 1200s 超时) — 小欧-2026-11-09
import api from './client';
import type { SessionModelOverride } from '@/types/chat';

/** 生成验证单腿记录（图腿 t2i/i2i 或视频腿 t2v/i2v），state 语义见后端 media.generate  - 小欧-2026-11-09 */
export interface OutputProbeRec {
  state: 'ok' | 'none' | 'unverified' | 'skipped';
  ms?: number;
  evidence?: string;
  at?: string;
}

/** 图片接收实测结果。accept.image 由探测写入，只有 'both' | 'inline' | 'none' 三值
 *  （'url' 单独出现无意义：外链通了必然也通内联，探测也不会产出该值）。 */
export interface MediaProbe {
  accept?: Record<string, string>;
  probed_at?: string;
  /** 外链那条腿是否拿到确定结论；由后端落库，前端不再解析 evidence 文本。 */
  url_tested?: boolean;
  /** 外链腿已发请求但厂商抓图失败(network_error 类，非确定结论)；false = 没发(地址空)或已取证 — 小欧-2026-11-09 */
  url_err?: boolean;
  /** 两腿请求往返耗时(ms，客户端掐表)；url_ms 为 null/缺省 = 外链腿未发起 — 小欧-2026-11-09 */
  inline_ms?: number | null;
  url_ms?: number | null;
  inline_tokens?: number | null;
  url_tokens?: number | null;
  evidence?: string;
  /** 生成验证（[15]）：图腿 t2i/i2i、视频腿 t2v/i2v；未点过「生成验证」= undefined  - 小欧-2026-11-09 */
  generate?: {
    image?: { t2i?: OutputProbeRec; i2i?: OutputProbeRec };
    video?: { t2v?: OutputProbeRec; i2v?: OutputProbeRec };
  };
}

export interface ModelEntry {
  name: string;
  label: string;
  // 2026-11-01 小欧 - 键名统一: default_params → model_params(与后端 yaml 真源同名) — 小欧-2026-11-01
  model_params: Record<string, unknown>;
  param_options?: Record<string, string[]>;
  range: Record<string, { min: number; max: number }>;
  // 2026-11-08 小欧: capabilities 拆为 input_modalities + output_modalities 双维度
  input_modalities: string[];
  output_modalities: string[];
  /**
   * 厂商声明的上下文窗口(token)。来源 model_meta.context_length。
   * 2026-11-01 小欧 - 后端原不下发该字段, ②参数区因此拿不到声明值(库保存的窗口既不可见也不可改) — 小欧-2026-11-01
   * undefined/null = 厂商未声明。**不得在此处造值**，上层按 model_params → meta → 全局默认逐级兜底。
   */
  context_length?: number | null;
  /** 模型最大输出 token 数。后端未下发 → undefined，由 LLM 调用链回退到全局默认值。 — 小欧-2026-10-26 */
  max_output_length?: number | null;
  /** 媒体传输探测结果(实测得出，非厂商声明)；未探测 → undefined。 — 小欧-2026-11-08 */
  media?: MediaProbe;
}

export interface ProviderEntry {
  name: string;
  label: string;
  api_base: string;
  // 2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}：masked 是后端 mask_secret_value
  //   一次生成好的最终可显示串（三档：len>8 前4+4星+后4 / 4<len<=8 ****+后4 / len<=4 ****），
  //   前端只回显，不再判断档位或拼星号。旧 {configured,prefix,suffix} 三键契约已作废。
  api_key: { configured: boolean; masked: string };
  env: boolean; // v4.19：该 provider 的 api_key 是否被 {NAME}_API_KEY 环境变量接管（config.py _apply_env_overrides 同源判定）
  timeout: number;
  max_retries: number;
  // 2026-09-22 小欧 - 实施：param_types 元数据（后端 PROVIDER_PARAM_TYPES 下发，
  //   前端动态字段渲染/收集的 schema 源——只渲染不定义）
  param_types?: Record<
    string,
    { type: string; label: string; min?: number; default?: unknown }
  >;
  models: ModelEntry[];
}

export interface ModelsResponse {
  providers: ProviderEntry[];
  current_model_ref: SessionModelOverride;
  ok?: boolean;
  switched_to?: string | null;
  mtime?: number;
}

export interface ModelMutationResult {
  ok: boolean;
  model?: string;
  provider?: string;
  switched_to?: string | null;
  mtime: number;
}

export interface RemoteModelItem {
  id: string;
  owned_by?: string | null;
  // 以下 6 项 2026-09-29 起由后端下发。此前只有 id/owned_by，前端靠 id.includes('-free')
  // 猜免费，实测在 OpenRouter 460 模型上命中 0 个(它用 :free 不是 -free) — 小欧 2026-09-29
  name?: string | null;
  description?: string | null;
  // 实测 OpenRouter 460 项全有值；agnes 等 provider 可能整个字段缺失
  context_length?: number | null;
  /** 单次请求最大输出 token。与 context_length 常差 8~16 倍（SenseNova 实测 glm-5.2
   *  输出 131072 / 上下文 1048576），缺此项会让人误判单次输出上限。
   *  该厂商不下发 → undefined，前端显示 –。 — 小欧 2026-10-05 */
  max_output_length?: number | null;
  /** 每 token 单价字符串。免费判据 prompt==="0" && completion==="0" */
  pricing?: Record<string, string>;
  /** 声明为 unknown：远端未声明元素类型，交消费方 Array.isArray 收窄 */
  architecture?: {
    input_modalities?: unknown;
    output_modalities?: unknown;
    modality?: unknown;
    instruct_type?: unknown;
    tokenizer?: unknown;
  };
  /** 输入模态。后端已把厂商两种层级归一：SenseNova 顶层下发 / OpenRouter 嵌在
   *  architecture.input_modalities，故此处只需读归一后的字段。 — 小欧 2026-10-05 */
  input_modalities?: string[];
  /** 输出模态。output 出现 image 即图像生成模型（SenseNova u1/u1.5），非对话模型。 */
  output_modalities?: string[];
  supported_parameters?: string[];
  /** 能力特性（tools/json_mode/reasoning），与上面的采样参数不同语义，故分列。
   *  厂商命名不统一（SenseNova 下发 supported_sampling_parameters），后端已按别名链合并。 */
  supported_features?: string[];
  /** 远端免费标记。是「是否落在每日免费额度内零计费」的记账标记，不等于"要花钱"。
   *  非 AMD provider 不返回 → undefined，由 isFreeModel 回退到名称尾巴/pricing 判据。 */
  free?: boolean | null;
  /** stable/beta/unstable/experimental。AMD 9 项实测全 experimental。现无消费方（已知 YAGNI）。 */
  stability?: string | null;
  /** 真发布时间（如 2026-09-03，zenmux 下发）。created 全假不可用；非 zenmux 不返回 → undefined。
   *  — 小欧 2026-10-10（对齐后端 DTO publish_time） */
  publish_time?: string | null;
  /** 推理强度档位（如 low/high/max，DeepSeek 下发）。非 DeepSeek 不返回 → 空数组。
   *  — 小欧 2026-10-11（对齐后端 DTO effort_levels，北京老陈令两个都加） */
  effort_levels?: string[];
  /** 推理强度默认值（如 high，DeepSeek 下发）。非 DeepSeek 不返回 → undefined。
   *  — 小欧 2026-10-11（对齐后端 DTO effort_default） */
  effort_default?: string | null;
}

export interface RemoteModelsResponse {
  ok: boolean;
  provider: string;
  models: RemoteModelItem[];
  count: number;
  configured: string[];
  current_model?: string | null;
  message?: string | null;
  // 小欧 - 2026-09-26: 错误分类与状态码随响应返回，前端据此分流
  // "地址问题"与"key 问题"两套文案（**不得统一显示"失败"**）。
  // **404/405/501 → endpoint_unsupported，刻意不判 key 无效**（部分 provider 无 /models 端点）。
  status_code?: number | null;
  category?: 'ok' | 'key_invalid' | 'endpoint_unsupported' | 'network_error';
}

export interface ReplaceModelsResult {
  ok: boolean;
  mtime: number;
  added: string[];
  removed: string[];
}

// 小欧 - 2026-09-26: 明文查看接口响应（api_key 为明文，仅内存持有不持久化）
export interface ApiKeyPlainResponse {
  provider: string;
  api_key: string;
  configured: boolean;
}

/** ZenithFree 双路验证（北京老陈 2026-10-10）：外部 zen_gate 库 vs 系统 opencodeZenAdapter */
export interface ZenVerifySide {
  ok: boolean;
  /** chat / responses；zen_gate 不可用时为空串 */
  endpoint: string;
  status: number;
  error: string;
}
/** 一致性判定。zen_unavailable 是独立态：外部库缺失只说明"没比成"，
 *  与 diverge 严格分开（否则会误导用户去改 adapter 修不存在的问题）。 */
export type ZenVerdict =
  | 'both_pass'
  | 'both_fail'
  | 'diverge'
  | 'zen_unavailable';

export interface ZenVerifyItem {
  model: string;
  zen_gate: ZenVerifySide;
  adapter: ZenVerifySide;
  verdict: ZenVerdict;
}

export interface ZenVerifyResponse {
  ok: boolean;
  provider: string;
  message?: string;
  results: ZenVerifyItem[];
  /** 报告绝对路径（后端 files/ 下），空串表示未生成 */
  report_path: string;
  summary: {
    total: number;
    both_pass: number;
    both_fail: number;
    diverge: number;
    zen_unavailable: number;
    /** remote = 远端最新；configured = 远端拉失败回落已配置 */
    source: string;
    zen_gate_available: boolean;
  };
}

export interface ZenVerifyReport {
  ok: boolean;
  message?: string;
  content?: string;
}

export interface ZenReportItem {
  name: string;
  mtime: number;
  size: number;
}

export interface ProviderConfigPatch {
  api_key?: string;
  api_base?: string;
  label?: string;
  timeout?: number;
  max_retries?: number;
  clear?: boolean;
}

const enc = (s: string): string => encodeURIComponent(s);

export const modelApi = {
  getModels: async (): Promise<ModelsResponse> => {
    const response = await api.get<ModelsResponse>('/models');
    return response.data;
  },

  addModel: async (data: {
    provider: string;
    model: string;
    label?: string;
    model_params?: Record<string, unknown>;
    range?: Record<string, { min: number; max: number }>;
    // 2026-11-08 小欧: capabilities → input/output 双维度
    input_modalities?: string[];
    output_modalities?: string[];
    param_options?: Record<string, string[]>;
  }): Promise<ModelsResponse> => {
    const response = await api.post<ModelsResponse>('/models', data);
    return response.data;
  },

  updateModel: async (
    provider: string,
    model: string,
    data: Partial<
      Pick<
        ModelEntry,
        | 'label'
        | 'model_params'
        | 'range'
        | 'input_modalities'
        | 'output_modalities'
        | 'param_options'
      >
    > & {
      // 2026-09-24 小欧 - 键级删除名单（与 model_params merge 叠加，后端先删再 merge）- 小欧-2026-09-24
      remove_params?: string[];
    }
  ): Promise<ModelMutationResult> => {
    const response = await api.put(
      `/models/${enc(provider)}/${enc(model)}`,
      data
    );
    return response.data;
  },

  deleteModel: async (
    provider: string,
    model: string
  ): Promise<ModelMutationResult> => {
    const response = await api.delete(`/models/${enc(provider)}/${enc(model)}`);
    return response.data;
  },

  getProviders: async (): Promise<ProviderEntry[]> => {
    const response = await api.get<ProviderEntry[]>('/providers');
    return response.data;
  },

  // 2026-09-22 小欧 - 实施：addProvider 入参补 timeout/max_retries（添加弹窗可设，
  //   后端 ProviderAddRequest DTO 已有默认 timeout=60/max_retries=3，缺此声明前端弹窗没数据来源，
  //   创建 Provider 只能走后端默认值）
  addProvider: async (data: {
    name: string;
    label?: string;
    api_base?: string;
    api_key?: string;
    timeout?: number;
    max_retries?: number;
    // 2026-10-10 小欧 - 透传 models（后端 ProviderAddRequest.models 原生支持，
    //   建 Provider 时一并建模型，一次调用无半成功窗口；此前前端无此字段只能调 N 次）
    models?: string[];
  }): Promise<ModelMutationResult> => {
    const response = await api.post('/providers', data);
    return response.data;
  },

  updateProvider: async (
    name: string,
    data: ProviderConfigPatch
  ): Promise<ModelMutationResult> => {
    const response = await api.put(`/providers/${enc(name)}`, data);
    return response.data;
  },

  // 2026-09-21 小强 - 修复类型瑕疵：deleteProvider 补齐 mtime（与 deleteModel 同构、后端同样返回 mtime，缺此字段表单 union 后 res.mtime 报错）
  deleteProvider: async (name: string): Promise<ModelMutationResult> => {
    const response = await api.delete(`/providers/${enc(name)}`);
    return response.data;
  },

  // 2026-09-24 小欧 - 拉取远程模型列表 — 小欧-2026-09-24
  fetchRemoteModels: async (
    provider: string
  ): Promise<RemoteModelsResponse> => {
    const response = await api.get<RemoteModelsResponse>(
      `/providers/${enc(provider)}/remote-models`
    );
    return response.data;
  },

  // 小欧 - 2026-09-26: 取已保存的 api_key 明文（供"眼睛"切换查看）。
  // 后端会记审计日志（provider + 时间 + 来源 IP），env 接管时返回 400 拒绝（YAML 里不是生效值）。
  getApiKeyPlain: async (provider: string): Promise<ApiKeyPlainResponse> => {
    const response = await api.get<ApiKeyPlainResponse>(
      `/providers/${enc(provider)}/api-key`
    );
    return response.data;
  },

  // 小欧 - 2026-09-26: 测试连接（key 正确性检测）。
  // 用 POST 而非 GET query 传待测 key —— query 会进浏览器历史/服务器 access log，明文 key 会留痕。
  // 探测逻辑在后端复用 fetch_remote_models，此处只做转发（不新造第二套）。
  testConnection: async (
    provider: string,
    probeKey?: string
  ): Promise<RemoteModelsResponse> => {
    const response = await api.post<RemoteModelsResponse>(
      `/providers/${enc(provider)}/test-connection`,
      { api_key: probeKey && probeKey.trim() !== '' ? probeKey.trim() : null }
    );
    return response.data;
  },

  // 2026-09-24 小欧 - 替换式写入 models 列表 — 小欧-2026-09-24
  // 2026-10-05 22:16:38 小欧 - models 由 List[str] 扩为 List<{id, context_length?, input_modalities?}>，
  //   保存勾选模型时把「上下文/输入模态」静态元数据持久化（北京老陈指令）。保留 id-only 兼容：
  //   元素可直接是 {id} 对象，id 提升为模型名。
  replaceModels: async (
    provider: string,
    models: Array<
      Pick<
        RemoteModelItem,
        | 'id'
        | 'context_length'
        | 'max_output_length'
        | 'input_modalities'
        | 'output_modalities'
        | 'supported_parameters'
        | 'supported_features'
      >
    >
  ): Promise<ReplaceModelsResult> => {
    const response = await api.put<ReplaceModelsResult>(
      `/providers/${enc(provider)}/models`,
      { models }
    );
    return response.data;
  },

  /** 实测模型以哪种方式接收图片(HTTP 200 且图像 token>0 才算真收到)，结果由后端落 model_meta.media。
   *  message 是后端给的整句短结论，直接进轻提示，前端不再自行拼词。 */
  probeMedia: async (
    provider: string,
    model: string
  ): Promise<{
    ok: boolean;
    provider: string;
    model: string;
    accept: string;
    /** 本次外链探测是否拿到确定结论；false = 没测成(未配置探测地址/网络或限流失败)，不得当成"不支持外链"。 */
    url_tested: boolean;
    /** 本次探测是否拿到确定结论；false 时后端不落库，前端也不得把它当成实测结果展示。 */
    conclusive: boolean;
    persisted: boolean;
    message: string;
  }> => {
    const response = await api.post(
      `/providers/${enc(provider)}/models/${enc(model)}/probe-media`
    );
    return response.data;
  },

  /** 生成验证（图腿 t2i+i2i / 视频腿 t2v+i2v）：验证生成模型输入(文本/URL图)与输出(图片/视频)，
   *  落 model_meta.media.generate。message 为后端整句探测结论，直接进提示；前端不二次拼接。*/
  probeOutput: async (
    provider: string,
    model: string
  ): Promise<{
    ok: boolean;
    provider: string;
    model: string;
    generate: {
      image?: { t2i?: OutputProbeRec; i2i?: OutputProbeRec };
      video?: { t2v?: OutputProbeRec; i2v?: OutputProbeRec };
    };
    conclusive: boolean;
    persisted: boolean;
    message: string;
  }> => {
    const response = await api.post(
      `/providers/${enc(provider)}/models/${enc(model)}/probe-output`,
      null,
      // 生图单张实测 0.3~17s；生视频是异步任务(提交+轮询, 单腿上限 600s 且队列满重试 3×30s，
      //   两条腿串行最坏≈23 分钟)，axios 默认 60s 会先断而厂商侧任务仍在跑并计费 → 显式放宽到 30 分钟
      { timeout: 1_800_000 }
    );
    return response.data;
  },

  zenVerify: async (provider: string): Promise<ZenVerifyResponse> => {
    const response = await api.post<ZenVerifyResponse>(
      `/providers/${enc(provider)}/zen-verify`,
      null,
      { timeout: 600_000 }
    );
    return response.data;
  },

  zenVerifyReports: async (): Promise<{
    ok: boolean;
    reports: ZenReportItem[];
  }> => {
    const response = await api.get<{ ok: boolean; reports: ZenReportItem[] }>(
      '/zen-verify/reports'
    );
    return response.data;
  },

  zenVerifyReport: async (name: string): Promise<ZenVerifyReport> => {
    const response = await api.get<ZenVerifyReport>('/zen-verify/report', {
      params: { name },
    });
    return response.data;
  },
};
