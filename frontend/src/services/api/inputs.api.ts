// 编辑历史:
// 2026-11-15 小欧 新建: 输入预检 API 封装(同 attachment.api 范式)。
//   契约真源 = backend/app/api/v1/inputs.py + app/services/inputs/preflight.py。
//   预检是建议性预览: 响应不含 limits/accepted, 前端不做任何能力/上限裁决 — 小欧-2026-11-15
// 2026-11-15 小欧 三堂会审整改: 补 text_url_only(正文纯 URL 判据真源在后端,
//   前端删自写 URL 正则, 接管判据消费此字段) — 小欧-2026-11-15

import api from './client';

/** 预检逐项结果(与后端 PreflightItem 字段一一对应, 零翻译) */
export interface PreflightItemDTO {
  key: string;
  source_kind: string;
  content_kind: string;
  ok: boolean;
  reason: string;
  quality: string;
  delivery: string;
  must_native: boolean;
  duplicate_of: string;
  url: string;
}

/** 预检响应(建议性: 无 limits/accepted) */
export interface PreflightResultDTO {
  items: PreflightItemDTO[];
  worst_quality: 'native' | 'degraded';
  /** 正文去掉扫描到的 URL 后只剩空白(纯 URL 粘贴/拖拽的接管判据, 识别真源在后端) */
  text_url_only: boolean;
  routing_advice: { action: string; reason: string };
}

export interface PreflightPayload {
  session_id?: string;
  model_id?: string;
  text?: string;
  items?: Array<Record<string, unknown>>;
}

/** 输入预检(永不阻断): 识别无条件执行, 能力判定读模型画像 */
export const preflightInput = async (
  payload: PreflightPayload
): Promise<PreflightResultDTO> => {
  const res = await api.post<PreflightResultDTO>('/inputs/preflight', payload);
  return res.data;
};
