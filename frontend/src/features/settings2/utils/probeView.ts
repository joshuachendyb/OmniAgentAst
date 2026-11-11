// 编辑历史: 2026-11-09 小欧 - 新建：实测行视图模型纯函数（自 SettingsPage 内联派生逻辑移出，逻辑零改动）— 小欧-2026-11-09
// 2026-11-11 小欧 - 图片/视频/音频三行 view 归一为 inputProbeView 唯一分派（原 mediaProbeView/modalityProbeView 吸收合并，
//   行名/方法tip/徽标tip/按钮tip 全量文案随迁，组件层零 kind 分支）— 小欧-2026-11-11
// 2026-11-11 小欧 - 注释勘误: 输入行 methodLines/JSDoc "输出能力正常"→"输入能力正常"(输入验证行结论词为输入) — 小欧-2026-11-11
import type {
  MediaProbe,
  ModalityProbeRec,
  OutputProbeRec,
} from '@/services/api/model.api';
import { Colors } from '@/utils/stepStyles';
import {
  acceptMain,
  acceptVerdict,
  probeMsText,
  urlErrOf,
  urlTestedOf,
} from '../mediaProbeText';

export type LegState = 'pass' | 'fail' | 'warn' | 'skip' | 'unknown' | 'na';

/** 徽标与结论词统一配色：未知/不适用=弱文字，不显红叉 */
export const legColor = (st: LegState): string =>
  st === 'pass'
    ? Colors.SUCCESS
    : st === 'fail'
      ? Colors.ERROR
      : st === 'warn'
        ? Colors.WARNING
        : Colors.TEXT.WEAK;

export type InputProbeKind = 'image' | 'video' | 'audio';

export interface InputProbeLeg {
  label: string;
  state: LegState;
}

export interface InputProbeDetail {
  text: string;
  /** 弱化展示（原 opacity 0.85 的取证时间/素材地址行） */
  weak?: boolean;
  breakAll?: boolean;
}

/** 输入能力验证行统一视图：图片(双腿)/视频/音频(单腿)共用，差异全以数据表达 */
export interface InputProbeView {
  rowLabel: string;
  /** 行名 tip 整句替换（图片行 chat 腿不适用时）；null = 走常规「验证方法说明」 */
  methodText: string | null;
  methodLines: string[];
  legs: InputProbeLeg[];
  verdictWord: string | null;
  verdictState: LegState;
  verdictLine: string;
  detailLines: InputProbeDetail[];
  buttonVisible: boolean;
  buttonBlocked: boolean;
  buttonBlockedTip: string;
  buttonGoLines: string[];
  memoVisible: boolean;
}

const inlineLegText = (media?: MediaProbe): string =>
  media?.inline_ms != null
    ? `响应 ${probeMsText(media.inline_ms)}${
        media?.inline_tokens != null
          ? `，图片 token ${media.inline_tokens}`
          : '，无 token 记录'
      }`
    : '未记录';

const urlLegText = (media: MediaProbe | undefined, urlErr: boolean): string => {
  const urlTested = urlTestedOf(media);
  if (!urlTested && !urlErr) return '未发起（Image_URL 为空）';
  const cost = media?.url_ms != null ? probeMsText(media.url_ms) : '—';
  const token = urlErr
    ? '抓图失败（未取证）'
    : media?.url_tokens != null
      ? `图片 token ${media.url_tokens}`
      : '未返回 token';
  return `响应 ${cost}，${token}`;
};

/** 图片行视图：双腿（内联/外链）+ 输入能力结论词；chat 腿不适用时收腿只留定论 */
const imageInputView = (
  media: MediaProbe | undefined,
  opts: { checked: boolean; chatLegMuted: boolean }
): InputProbeView => {
  const { checked, chatLegMuted } = opts;
  const accept = media?.accept?.image;
  const urlTested = urlTestedOf(media);
  const urlErr = urlErrOf(media);
  const imageVerdict = acceptVerdict(accept, urlTested, urlErr);
  const inlineState: LegState = chatLegMuted
    ? 'na'
    : !accept
      ? 'unknown'
      : accept === 'none'
        ? 'fail'
        : 'pass';
  const urlState: LegState = chatLegMuted
    ? 'na'
    : accept === 'both'
      ? 'pass'
      : accept === 'inline' && urlTested
        ? 'fail'
        : urlErr
          ? 'warn'
          : 'unknown';
  return {
    rowLabel: '输入图片能力验证',
    methodText: chatLegMuted
      ? '生成模型：图片输入/输出走生成专用端点（如 /v1/images/generations），chat 腿 400 为预期；图片能力请点「生成验证」实测'
      : null,
    methodLines: [
      '真实调用 LLM 发送一张内置测试图，HTTP 200 且返回图像 token>0（厂商不报图像 token 时按「带图输入 token 明显高于纯文本」）才算「输入能力」正常',
      '内联＝图片数据直接随请求体发送（base64）',
      '外链＝只发图片地址，由厂商接口自行抓取',
      urlTested
        ? '外链已取证——测试图片地址由厂商接口实际抓取成功，图片地址可随请求转发'
        : urlErr
          ? '外链未取证——外链腿已请求，厂商侧抓图失败（网络超时或不可达），不判对错；可再点「验证」重试'
          : '外链未取证——本次验证时上方「Image_URL」为空，外链腿未发起请求；填好地址再点「验证」即出对/错',
    ],
    legs: chatLegMuted
      ? []
      : [
          { label: '内联', state: inlineState },
          { label: '外链', state: urlState },
        ],
    verdictWord: chatLegMuted
      ? '不适用'
      : checked || !!accept
        ? acceptMain(accept)
        : null,
    verdictState: inlineState,
    verdictLine: chatLegMuted
      ? '生成模型：图片输入/输出走生成专用端点，chat 腿 400 为预期现象'
      : checked
        ? imageVerdict
        : `${imageVerdict}（当前未勾选「图片」，不发图）`,
    detailLines: media?.probed_at
      ? [
          {
            text: '图片 token＝厂商把图片折算的输入 token，>0＝图真进了上下文',
          },
          { text: `内联腿：${inlineLegText(media)}` },
          { text: `外链腿：${urlLegText(media, urlErr)}` },
          { text: `验证时间 ${media.probed_at.replace('T', ' ')}`, weak: true },
        ]
      : [],
    buttonVisible: !chatLegMuted,
    buttonBlocked: !checked,
    buttonBlockedTip: '未勾选「图片」输入模态，当前不发图，无从验证',
    buttonGoLines: [
      '真实发送一张内置测试图，结论写回本行',
      '外链取证：先在上方「Image_URL」填公网图片地址，再点「验证」',
    ],
    memoVisible: !accept,
  };
};

export interface GenLegView {
  label: string;
  rec?: OutputProbeRec;
  state: LegState;
  tip: string;
}

export interface GenProbeView {
  legs: GenLegView[];
  hasRecord: boolean;
  wordState: LegState;
  verdictWord: string;
  verdict: string;
  probedAt: string;
}

const genLegState = (rec?: OutputProbeRec): LegState =>
  !rec
    ? 'unknown'
    : rec.state === 'skipped'
      ? 'skip'
      : rec.state === 'ok'
        ? 'pass'
        : rec.state === 'none'
          ? 'fail'
          : 'warn';

const genLegTip = (label: string, leg?: OutputProbeRec): string => {
  if (!leg) return '';
  if (leg.state === 'skipped')
    return `${label}：— 未执行（前置腿被拒或未取证，未发起第二枪）`;
  if (leg.state === 'ok') return `${label}：✓ ${probeMsText(leg.ms)}`;
  if (leg.state === 'none') return `${label}：✗ 厂商拒绝`;
  const ev = leg.evidence ?? '';
  const reason = ev.startsWith('source_unreachable')
    ? '？ 厂商抓不到探测素材'
    : ev.startsWith('task_failed')
      ? '？ 厂商侧生成失败，稍后重试'
      : ev.startsWith('queue_full')
        ? '？ 厂商队列已满'
        : ev.startsWith('poll_timeout')
          ? '？ 等出片超时'
          : '？ 未完成（鉴权／限流／协议漂移）';
  return `${label}：${reason}`;
};

const pickLegs = (
  media: MediaProbe | undefined,
  outputModalities: string[]
): GenLegView[] => {
  const image = media?.generate?.image;
  const video = media?.generate?.video;
  const raw = [
    ...(outputModalities.includes('image')
      ? [
          { label: '文生图', rec: image?.t2i },
          { label: '图生图', rec: image?.i2i },
        ]
      : []),
    ...(outputModalities.includes('video')
      ? [
          { label: '文生视频', rec: video?.t2v },
          { label: '图生视频', rec: video?.i2v },
        ]
      : []),
  ];
  return raw.map((l) => ({
    ...l,
    state: genLegState(l.rec),
    tip: genLegTip(l.label, l.rec),
  }));
};

/** 生成能力实测行：逐腿徽标 + 结论词 + 汇总句；腿由输出声明决定 */
export const genProbeView = (
  media: MediaProbe | undefined,
  outputModalities: string[]
): GenProbeView => {
  const legs = pickLegs(media, outputModalities);
  const states = legs.map((l) => l.state);
  const allPass = states.length > 0 && states.every((st) => st === 'pass');
  const anyPass = states.includes('pass');
  const anyFail = states.includes('fail');
  const wordState: LegState = states.every(
    (st) => st === 'unknown' || st === 'skip'
  )
    ? 'unknown'
    : allPass
      ? 'pass'
      : anyPass
        ? 'warn'
        : anyFail
          ? 'fail'
          : 'warn';
  const passLabels = legs.filter((l) => l.state === 'pass').map((l) => l.label);
  const failLabels = legs.filter((l) => l.state === 'fail').map((l) => l.label);
  const pendLabels = legs.filter((l) => l.state === 'warn').map((l) => l.label);
  const skipLabels = legs.filter((l) => l.state === 'skip').map((l) => l.label);
  const atList = legs.map((l) => l.rec?.at).filter(Boolean) as string[];
  return {
    legs,
    hasRecord: legs.some((l) => l.rec),
    wordState,
    verdictWord:
      wordState === 'unknown'
        ? '未验证'
        : wordState === 'pass'
          ? '可用'
          : wordState === 'fail'
            ? '不可用'
            : anyPass
              ? '部分可用'
              : '未完成',
    verdict:
      wordState === 'unknown'
        ? '尚未做过生成验证——点右侧「生成验证」实测'
        : allPass
          ? `${legs.map((l) => l.label).join('与')}均通过`
          : [
              passLabels.length ? `可${passLabels.join('、')}` : '',
              failLabels.length ? `${failLabels.join('、')}被厂商拒绝` : '',
              pendLabels.length ? `${pendLabels.join('、')}未完成` : '',
              skipLabels.length ? `${skipLabels.join('、')}未执行` : '',
            ]
              .filter(Boolean)
              .join('；'),
    probedAt: atList.length ? atList[atList.length - 1] : '',
  };
};

/** Image_URL 落库键（后端 registry hidden 项，全名扁平提交） */
export const PROBE_IMAGE_URL_KEY = 'media.probe_image_url';

/** Image_URL 当前已存值：values 组内键为全名 key，与 saveKeys 读取口径一致 */
export const probeImageUrlOf = (
  values: Record<string, Record<string, unknown>>
): string =>
  (values['media']?.[PROBE_IMAGE_URL_KEY] as string | undefined) ?? '';

// ── 输入能力验证行视图（图片/视频/音频归一, 2026-11-11）────────────────────────
const MODALITY_LABEL: Record<'video' | 'audio', string> = {
  video: '视频',
  audio: '音频',
};

/** 素材通道说明（行名 tip 内固定交代） */
const MODALITY_CHANNEL: Record<'video' | 'audio', string> = {
  video: '视频＝只发公网素材地址，由厂商接口自行抓取（video_url）',
  audio: '音频＝后端先下载素材，再 base64 内联随请求体发送（input_audio）',
};

/** 视频/音频行视图：单徽标（视频=URL 腿 / 音频=内联腿）+ 结论词 */
const modalityInputView = (
  kind: 'video' | 'audio',
  rec: ModalityProbeRec | undefined,
  opts: { checked: boolean }
): InputProbeView => {
  const label = MODALITY_LABEL[kind];
  const { checked } = opts;
  const state: LegState = !rec
    ? 'unknown'
    : rec.state === 'ok'
      ? 'pass'
      : rec.state === 'none'
        ? 'fail'
        : 'warn';
  const leg = rec
    ? `响应 ${probeMsText(rec.ms) || '—'}${
        rec.tokens != null
          ? `，${label} token ${rec.tokens}`
          : '，无 token 记录'
      }`
    : '未记录';
  const baseVerdict = !rec
    ? `未实测——暂不随请求发送${label}素材`
    : state === 'pass'
      ? `实测可用：${label}素材随请求发送后真进了模型上下文`
      : state === 'fail'
        ? `不收${label}：接口拒绝素材内容（HTTP 400/415/422），或返回 200 但${label} token 为 0`
        : `未完成：本次验证未拿到确定结论（鉴权/限流/超时），不判对错，可再点「验证」重试`;
  return {
    rowLabel: `输入${label}能力验证`,
    methodText: null,
    methodLines: [
      `真实调用 LLM 发送一段内置测试${label}素材，HTTP 200 且返回对应 token>0（厂商不报时按「带素材输入 token 明显高于纯文本」）才算「输入能力」正常`,
      MODALITY_CHANNEL[kind],
      `素材地址可在后端配置 media.probe_${kind}_url 中修改`,
    ],
    legs: [{ label, state }],
    verdictWord: checked || rec ? '输入' : null,
    verdictState: state,
    verdictLine: checked
      ? baseVerdict
      : `${baseVerdict}（当前未勾选「${label}」，不发送${label}素材）`,
    detailLines: rec
      ? [
          {
            text: `${label} token＝厂商把素材折算的输入 token，>0＝素材真进了上下文`,
          },
          { text: `${label}腿：${leg}` },
          ...(rec.source
            ? [{ text: `素材 ${rec.source}`, weak: true, breakAll: true }]
            : []),
          ...(rec.at
            ? [{ text: `验证时间 ${rec.at.replace('T', ' ')}`, weak: true }]
            : []),
        ]
      : [],
    buttonVisible: true,
    buttonBlocked: !checked,
    buttonBlockedTip: `未勾选「${label}」输入模态，当前不发送${label}素材，无从验证`,
    buttonGoLines: [
      `真实发送一段测试${label}素材，结论写回本行`,
      `素材地址由后端配置提供（media.probe_${kind}_url）`,
    ],
    memoVisible: !rec,
  };
};

/** 输入能力验证行唯一分派点：图片走平铺 media，视频/音频走 media[kind] 子记录 */
export const inputProbeView = (
  kind: InputProbeKind,
  media: MediaProbe | undefined,
  opts: { checked: boolean; chatLegMuted?: boolean }
): InputProbeView =>
  kind === 'image'
    ? imageInputView(media, {
        checked: opts.checked,
        chatLegMuted: opts.chatLegMuted ?? false,
      })
    : modalityInputView(kind, media?.[kind], { checked: opts.checked });
