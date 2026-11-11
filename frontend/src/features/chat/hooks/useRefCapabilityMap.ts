// 编辑历史: 2026-11-11 小欧 新建: 生效模型(L2 会话覆盖 ?? L1 全局)的附件能力二维投影 hook,
//   chip/文件行徽标唯一数据源(只读索引, 不在前端推导能力) — 小欧-2026-11-11

/**
 * useRefCapabilityMap —— 当前生效模型的 ref_capability_map 只读索引。
 *
 * 数据链: sessionApi.getSession(L2) ?? configApi.getFullConfig(L1) → modelApi.getModels()
 *   → ModelEntry.ref_capability_map(后端 contract.ref_capability_map 生成)。
 * chipCapState: 按 chip 的 kind/path/mime 投影出 (source_kind, content_kind) 查表。
 */
import { useEffect, useState } from 'react';

import { configApi } from '@/services/api/config.api';
import { modelApi } from '@/services/api/model.api';
import { sessionApi } from '@/services/api/session.api';
import type { CapabilityState } from '@/features/chat/components/input/CapabilityBadge';
import type { ComposerRef } from '@/features/refs/store';

export type RefCapabilityMap = Record<
  string,
  Record<string, 'native' | 'degraded' | 'opaque'>
>;

const _SUFFIX_RES: Array<[RegExp, string]> = [
  [/\.(png|jpe?g|gif|webp|bmp)$/i, 'image'],
  [/\.(mp4|mov|mkv|webm|avi|m4v)$/i, 'video'],
  [/\.(mp3|wav|m4a|aac|flac|ogg|opus|wma)$/i, 'audio'],
  [/\.(pdf|docx|xlsx|pptx)$/i, 'richdoc'],
  [
    /\.(txt|md|markdown|log|csv|tsv|json|jsonl|xml|ya?ml|toml|ini|cfg|conf|env|properties|html?|css|s[ca]ss|less|jsx?|mjs|cjs|tsx?|vue|py|pyi|java|kt|go|rs|c|h|hpp|cpp|cc|cs|php|rb|swift|m|sh|bash|zsh|ps1|bat|cmd|sql|r|lua|pl|scala|dart|gradle|dockerfile)$/i,
    'text',
  ],
];

export function contentKindOf(path: string, mime?: string): string {
  for (const [re, kind] of _SUFFIX_RES) {
    if (re.test(path)) return kind;
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
