// 编辑历史:
// 2026-11-15 小欧 新建: URL 采集层 —— 粘贴/拖拽文本交后端 preflight 扫描
//   (识别/去重/校验真源全在后端, 本层不写识别/去重/校验), 按逐项 ok/reason
//   产出 URL chip 与"加入时即拒"名单; 上限裁决在本层收口(调用方传入剩余配额) — 小欧-2026-11-15
// 2026-11-15 小欧 三堂会审整改: 删 isUrlOnlyText(前端自写 URL 正则属第二套识别口径,
//   且接管判据改由 ChatInput 以"原生粘贴落位+命中后撤出"实现, 识别单一真源在后端);
//   上限裁决移入本层(room 入参), 调用方不再自行切片 — 小欧-2026-11-15
// 2026-11-16 小欧 [23]阶段B: accepted chip 落存 preflight 逐项 quality(徽标双源之 URL 源,
//   只读不派生); outcome 透传 routing_advice(推荐切换提示数据源) — 小欧-2026-11-16
// 2026-11-16 小欧 [23]阶段D: 增 opts(modelId/mode) 透传 preflight, 使 routing_advice 参与判定 — 小欧-2026-11-16

// 2026-11-16 小欧 修正: 投影/签名跳过 pending 占位项(未落定条目不上送, 落定后签名变化触发重算);
//   routingAdvice 复用 types/chat 的 RoutingAdvice 类型


import { preflightInput } from '@/services/api/inputs.api';
import { newRefId, type ComposerRef, type RefQualityValue } from './store';
import type { RoutingAdvice, RoutingMode } from '@/types/chat';

export interface RejectedUrl {
  url: string;
  reason: string;
}

export interface UrlCaptureOutcome {
  accepted: ComposerRef[];
  rejected: RejectedUrl[];
  /** 配额不够被拦下的条数(0=无溢出) */
  overflow: number;
  /** 后端判定: 正文去掉扫描到的 URL 后只剩空白(纯 URL 内容才接管撤出正文) */
  urlOnly: boolean;
  /** preflight routing_advice 原值透传(推荐切换提示数据源, 零翻译) — 2026-11-16 小欧 */
  routingAdvice: RoutingAdvice;
}

export interface UrlCaptureOpts {
  /** 当前生效模型(provider/model 或 model); 缺省不路由(后端画像无从判定) */
  modelId?: string;
  /** 会话级路由模式, 缺省 suggest */
  mode?: RoutingMode;
}

/**
 * 采集: 整段文本交后端预检扫描 → URL 逐项分流。
 * ok → URL chip(一等引用); !ok → 即拒名单(调用方 toast 点名 reason);
 * duplicate_of 非空 → 后端已点名重复, 跳过不入队(去重裁决在后端, 本层只消费);
 * room = 引用剩余配额, 超出部分计入 overflow 由调用方一并点名;
 * urlOnly = 后端接管判据(识别真源在后端, 本层零识别)。
 */
export const captureUrlsFromText = async (
  text: string,
  room: number,
  opts: UrlCaptureOpts = {}
): Promise<UrlCaptureOutcome> => {
  const result = await preflightInput({
    text,
    model_id: opts.modelId,
    mode: opts.mode,
  });
  const accepted: ComposerRef[] = [];
  const rejected: RejectedUrl[] = [];
  for (const it of result.items) {
    if (it.source_kind !== 'url') continue;
    if (!it.ok) {
      rejected.push({ url: it.url, reason: it.reason });
      continue;
    }
    if (it.duplicate_of) continue;
    accepted.push({
      id: newRefId(),
      kind: 'url',
      label: it.url,
      path: it.url, // refKeyOf 按 path 归一 → 同 URL 天然同 key 原位替换
      url: it.url,
      source_kind: it.source_kind,
      must_native: it.must_native,
      // 阶段B: preflight 逐项 quality 原值落存(徽标只读, 前端零派生) — 2026-11-16 小欧
      quality: it.quality as RefQualityValue,
    });
  }
  const overflow = Math.max(0, accepted.length - Math.max(0, room));
  return {
    accepted: accepted.slice(0, Math.max(0, room)),
    rejected,
    overflow,
    urlOnly: result.text_url_only,
    routingAdvice: result.routing_advice,
  };
};
