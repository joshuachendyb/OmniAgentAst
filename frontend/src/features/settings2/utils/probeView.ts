// 编辑历史: 2026-11-09 小欧 - 新建：实测行视图模型纯函数（自 SettingsPage 内联派生逻辑移出，逻辑零改动）— 小欧-2026-11-09
import type { MediaProbe, OutputProbeRec } from '@/services/api/model.api';
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

export interface MediaProbeView {
  accept?: string;
  urlTested: boolean;
  urlErr: boolean;
  inlineState: LegState;
  urlState: LegState;
  verdictWord: string | null;
  verdictLine: string;
  inlineLeg: string;
  urlLeg: string;
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

/** 图片输入实测行：三态徽标（内联/外链）+ 输出能力结论词 + 定论句 + 逐腿耗时/token */
export const mediaProbeView = (
  media: MediaProbe | undefined,
  opts: { imageChecked: boolean; chatLegMuted: boolean }
): MediaProbeView => {
  const { imageChecked, chatLegMuted } = opts;
  const accept = media?.accept?.image;
  const urlTested = urlTestedOf(media);
  const urlErr = urlErrOf(media);
  const imageVerdict = acceptVerdict(accept, urlTested, urlErr);
  return {
    accept,
    urlTested,
    urlErr,
    inlineState: chatLegMuted
      ? 'na'
      : !accept
        ? 'unknown'
        : accept === 'none'
          ? 'fail'
          : 'pass',
    urlState: chatLegMuted
      ? 'na'
      : accept === 'both'
        ? 'pass'
        : accept === 'inline' && urlTested
          ? 'fail'
          : urlErr
            ? 'warn'
            : 'unknown',
    verdictWord: chatLegMuted
      ? '不适用'
      : imageChecked || !!accept
        ? acceptMain(accept)
        : null,
    verdictLine: chatLegMuted
      ? '生成模型：图片输入/输出走生成专用端点，chat 腿 400 为预期现象'
      : imageChecked
        ? imageVerdict
        : `${imageVerdict}（当前未勾选「图片」，不发图）`,
    inlineLeg: inlineLegText(media),
    urlLeg: urlLegText(media, urlErr),
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
