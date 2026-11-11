// 编辑历史: 2026-11-11 小欧 新建: 生效模型(L2 会话覆盖 ?? L1 全局)的附件能力二维投影 hook,
//   chip/文件行徽标唯一数据源(只读索引, 不在前端推导能力) — 小欧-2026-11-11
// 编辑历史: 2026-11-11 小欧 三堂会审整改: 删前端复制的后缀正则表(与后端 extract 词典双真源漂移),
//   改消费后端 capabilities.suffix_kind 词典(模块级一次拉取缓存); mime 兜底保留(HTTP 标准前缀, 非词典) — 小欧-2026-11-11

/**
 * useRefCapabilityMap —— 当前生效模型的 ref_capability_map 只读索引。
 *
 * 数据链: sessionApi.getSession(L2) ?? configApi.getFullConfig(L1) → modelApi.getModels()
 *   → ModelEntry.ref_capability_map(后端 contract.ref_capability_map 生成)。
 * chipCapState: 按 chip 的 kind/path/mime 投影出 (source_kind, content_kind) 查表。
 */
import { useEffect, useState } from 'react';

import { attachmentApi } from '@/services/api/attachment.api';
import { configApi } from '@/services/api/config.api';
import { modelApi } from '@/services/api/model.api';
import { sessionApi } from '@/services/api/session.api';
import type { CapabilityState } from '@/features/chat/components/input/CapabilityBadge';
import type { ComposerRef } from '@/features/refs/store';

export type RefCapabilityMap = Record<
  string,
  Record<string, 'native' | 'degraded' | 'opaque'>
>;

/** 后端 suffix_kind 词典模块缓存(一次拉取, 拉取失败降级为仅 mime 兜底) */
let _suffixKind: Record<string, string> | null = null;

/** 后端后缀→类型词典单源加载(幂等); 前端禁止再写死后缀表 — 小欧-2026-11-11 */
export async function ensureSuffixKind(): Promise<void> {
  if (_suffixKind) return;
  try {
    const caps = await attachmentApi.capabilities();
    _suffixKind = caps.suffix_kind ?? {};
  } catch {
    _suffixKind = {};
  }
}

export function contentKindOf(path: string, mime?: string): string {
  const p = (path || '').toLowerCase();
  for (const [sfx, kind] of Object.entries(_suffixKind ?? {})) {
    if (p.endsWith(sfx)) return kind;
  }
  if (mime?.startsWith('image/')) return 'image';
  if (mime?.startsWith('video/')) return 'video';
  if (mime?.startsWith('audio/')) return 'audio';
  if (mime === 'application/pdf') return 'richdoc';
  return 'binary';
}

/** chip → (source_kind, content_kind) 查表; map 缺该格返回 undefined(不显示徽标)。 */
export function chipCapState(
  map: RefCapabilityMap | null,
  r: Pick<ComposerRef, 'kind' | 'path' | 'mime'>
): CapabilityState | undefined {
  if (!map) return undefined;
  const source = r.kind === 'attachment' ? 'attachment' : 'file';
  const row = map[source];
  if (!row) return undefined;
  const state = row[contentKindOf(r.path ?? '', r.mime)];
  return (state as CapabilityState) || undefined;
}

export function useRefCapabilityMap(
  sessionId?: string | null
): RefCapabilityMap | null {
  const [map, setMap] = useState<RefCapabilityMap | null>(null);
  useEffect(() => {
    let alive = true;
    void (async () => {
      await ensureSuffixKind();
      let target: { provider?: string; model?: string } | null = null;
      if (sessionId) {
        try {
          const s = await sessionApi.getSession(sessionId);
          target = (s as { sessionModel?: { provider?: string; model?: string } | null })
            .sessionModel ?? null;
        } catch {
          target = null;
        }
      }
      if (!target?.provider || !target?.model) {
        try {
          const cfg = await configApi.getFullConfig();
          target = cfg.current_model_ref ?? null;
        } catch {
          target = null;
        }
      }
      if (!alive) return;
      if (!target?.provider || !target?.model) {
        setMap(null);
        return;
      }
      try {
        const resp = await modelApi.getModels();
        const prov = target.provider;
        const name = target.model;
        const entry = (resp.providers ?? [])
          .find((p) => p.name === prov)
          ?.models.find((m) => m.name === name);
        if (alive) setMap(entry?.ref_capability_map ?? null);
      } catch {
        if (alive) setMap(null);
      }
    })();
    return () => {
      alive = false;
    };
  }, [sessionId]);
  return map;
}
