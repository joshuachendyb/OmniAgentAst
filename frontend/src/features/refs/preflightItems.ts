// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段D D12 —— 引用 chips → 后端 preflight items 纯投影
//   (零识别/零质量判定, 分类与质量仍由 contract 唯一裁决);
//   preflightItemKey 与后端 preflight._item_key 同口径, 供按 key 回写逐项 quality — 小欧-2026-11-16

/**
 * preflightItems —— 引用条 → 输入预检 items 的纯投影(单一实现)
 *
 * 目的: D12 全量重算把"仅 URL 采集时预检"升级为"Composer 级重算"——把既有 chips
 *   投影成后端 items, 由后端 preflight 统一裁决逐项 quality/worst_quality/routing_advice。
 *   本模块不做识别、不做质量判定、不发请求。
 */
import type { ComposerRef } from './store';
import { refKeyOf } from './identity';

/** 投影为后端 PreflightIn.items 形态(字段与 contract.classify_ref 入参对齐) */
export const refsToPreflightItems = (
  refs: ComposerRef[]
): Array<Record<string, unknown>> =>
  refs.map((r) =>
    r.kind === 'url'
      ? { kind: 'url', url: r.url ?? r.path }
      : r.kind === 'attachment'
        ? {
            kind: 'attachment',
            attachment_id: r.attachment_id,
            path: r.path,
            mime: r.mime,
            size: r.size,
          }
        : { kind: r.kind, path: r.path, mime: r.mime, size: r.size }
  );

/** 条目去重键: 与后端 preflight._item_key 同口径(url→url; 其余 path/attachment_id/label) */
export const preflightItemKey = (r: ComposerRef): string =>
  r.kind === 'url'
    ? String(r.url ?? r.path ?? '')
    : String(r.path || r.attachment_id || r.label || '');

/** 重算触发签名: 归一 key 排序串(条目增删/替换即变, 逐项 quality 回写不触发) */
export const refsSignature = (refs: ComposerRef[]): string =>
  refs
    .map(refKeyOf)
    .sort()
    .join('\n');
