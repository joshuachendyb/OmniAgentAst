// 编辑历史: 2026-11-14 小欧 重构: 徽标只按 quality 四值出文案(不再按 content_kind 二次翻译),
//   颜色/图标/文案单表; 与后端 contract.QUALITIES 同源, 前端零派生 — 小欧-2026-11-14
import { Tag, Tooltip } from 'antd';

import type { RefQuality } from '@/services/api/model.api';

/** 档位元数据: 颜色/图标/档位名/白话解释的唯一展示真源 */
export const QUALITY_META: Record<RefQuality, { color: string; icon: string; label: string; tip: string }> = {
  native:      { color: 'green',   icon: '✓', label: '原生投递', tip: '按原生形态直接交给模型' },
  text_full:   { color: 'blue',    icon: '≣', label: '全文注入', tip: '正文完整进入请求体' },
  meta_only:   { color: 'cyan',    icon: '▤', label: '元信息注入', tip: '仅注入抽取正文或文件元信息' },
  link_only:   { color: 'default', icon: '—', label: '仅链接',     tip: '只收到链接地址, 未取内容' },
};

export function QualityBadge(props: { quality: RefQuality }) {
  const meta = QUALITY_META[props.quality];
  return (
    <Tooltip title={meta.tip}>
      <Tag color={meta.color} style={{ marginInlineEnd: 0 }}>{meta.icon} {meta.label}</Tag>
    </Tooltip>
  );
}
