// 编辑历史:
// 2026-11-15 小欧 新建: URL 采集层 —— 粘贴/拖拽文本交后端 preflight 扫描
//   (识别/去重/校验真源全在后端, 本层不写识别/去重/校验), 按逐项 ok/reason
//   产出 URL chip 与"加入时即拒"名单; 上限裁决在本层收口(调用方传入剩余配额) — 小欧-2026-11-15
// 2026-11-15 小欧 三堂会审整改: 删 isUrlOnlyText(前端自写 URL 正则属第二套识别口径,
//   且接管判据改由 ChatInput 以"原生粘贴落位+命中后撤出"实现, 识别单一真源在后端);
//   上限裁决移入本层(room 入参), 调用方不再自行切片 — 小欧-2026-11-15

import { preflightInput } from '@/services/api/inputs.api';
import { newRefId, type ComposerRef } from './store';

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
  room: number
): Promise<UrlCaptureOutcome> => {
  const result = await preflightInput({ text });
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
    });
  }
  const overflow = Math.max(0, accepted.length - Math.max(0, room));
  return {
    accepted: accepted.slice(0, Math.max(0, room)),
    rejected,
    overflow,
    urlOnly: result.text_url_only,
  };
};
