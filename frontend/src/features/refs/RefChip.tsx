// 编辑历史:
// 2026-11-16 小欧 新建: [23]阶段B —— 引用 chip 统一组件(附件/文件/URL/选区同一渲染体),
//   自 ChatInput refs.map 内联 span 原样抽出(样式/点击/回执态零改动, 不退化功能);
//   徽标双源: URL 逐项只读 preflight items[].quality(采集层落存), 附件/文件只读
//   ref_quality_map(调用方经 useRefQualityMap 投影), 同源 quality_of, 前端零派生 — 小欧-2026-11-16

/**
 * RefChip —— 引用 chip 统一组件（四类引用唯一渲染体）
 *
 * 职责(SRP): 单条引用的展示 + 回执态着色 + 点击跳转 + 移除按钮。
 * 状态裁决在 notice.chipStateOf(5 态唯一映射), 配色只查色表, 本组件零状态推导。
 */
import React from 'react';
import { FileOutlined } from '@ant-design/icons';
import {
  chipStateOf,
  chipStateText,
  chipToneOf,
  noticeOf,
  noticeDetailText,
  type ChipTone,
  type NoticeMap,
} from './notice';
import { resolveChipUrlFresh } from '@/hooks/useProjectRoot';
import { useOptionalNavigate } from '@/hooks/useOptionalNavigate';
import { QualityBadge } from '@/features/chat/components/input/QualityBadge';
import { Colors, FontSize } from '@/utils/stepStyles';
import { chatTokens } from '@/theme/tokens';
import { Gap, LineHeight } from '@/theme/spacing';
import { CONTROL_PADDING } from '@/theme/controlScale';
import type { ComposerRef, RefQualityValue } from './store';

/** chip 色调 → 具体色值(组件侧唯一色表, 状态→色调的裁决在 notice.chipToneOf) */
const CHIP_TONE_STYLE: Record<ChipTone, { bg: string; border: string }> = {
  danger: { bg: Colors.ERROR_BG, border: Colors.ERROR_BORDER },
  warn: { bg: Colors.WARNING_BG, border: Colors.WARNING },
  normal: { bg: chatTokens.colorPrimaryBg, border: chatTokens.colorBorder },
};

interface RefChipProps {
  r: ComposerRef;
  /** 回执态 map(refNoticeStore 快照, 经 useComposerRefs 透传) */
  notices: NoticeMap;
  /** 能力徽标: URL=逐项 preflight quality / 附件文件=ref_quality_map 投影; 查不到不显示 */
  quality?: RefQualityValue;
  onRemove: (id: string) => void;
}

export const RefChip: React.FC<RefChipProps> = ({ r, notices, quality, onRemove }) => {
  const state = chipStateOf(r, notices);
  const notice = noticeOf(r, notices);
  const tone = CHIP_TONE_STYLE[chipToneOf(state)];
  const detail = noticeDetailText(notice);
  // 点击跳转的唯一口（有 Router 走 SPA，无 Router 整页跳）
  const nav = useOptionalNavigate();
  return (
    <span
      title={`${r.path ?? ''}${
        r.lineRange
          ? `（第 ${r.lineRange.start}-${r.lineRange.end} 行）`
          : ''
      }${detail ? `｜${detail}` : ''}`}
      style={{
        /* 失效引用红底（与正常蓝底一眼区分） */
        background: tone.bg,
        color: Colors.TEXT.STRONG,
        border: `1px solid ${tone.border}`,
        borderRadius: chatTokens.radius,
        padding: `${CONTROL_PADDING.CHIP_Y}px ${CONTROL_PADDING.CHIP_X}px`,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        gap: Gap.ROW,
        // chip 文字行高取全站行高标准 LOOSE, 配合 chip 上下内距 1px 得 24px 行盒
        lineHeight: LineHeight.LOOSE,
      }}
      onClick={() => {
        // 上下文包无单一路径（path=''）→ 不跳文件页（否则点开一个空 path 的死链），仅作展示
        if (!r.path) return;
        // URL chip: path 载的是外链, 直接新开, 不走文件路径解析(否则外链被当项目内路径, 文件页必报找不到)
        if (r.kind === 'url') {
          window.open(r.url ?? r.path, '_blank', 'noopener');
          return;
        }
        // 走唯一路径解析（点击实时取根），根外路径不生成无 ext=1 的内部深链;
        // 跳转口径与 PathLink 一致（SPA 导航 + internal 标记）
        void resolveChipUrlFresh(r.path, r.lineRange ?? null).then((url) => {
          if (url) nav(url, { state: { internal: true } });
        });
      }}
    >
      <FileOutlined style={{ color: chatTokens.colorPrimary }} />
      {r.label}
      {/* 引用质量徽标: 双源只读(见头注), 前端零派生 */}
      {quality && <QualityBadge quality={quality} />}
      {chipStateText(state, notice)}
      {/* 删除按钮放大到可点面积 + 键盘可达（原来是裸 × 字符） */}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove(r.id);
        }}
        aria-label={`删除引用 ${r.label}`}
        title="移除该引用"
        style={{
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          padding: `0 ${CONTROL_PADDING.CHIP_X}px`,
          // 删除按钮与 chip 文字同字号同行高(不再单写 16px), 靠颜色区分主次
          fontSize: FontSize.PRIMARY,
          lineHeight: LineHeight.LOOSE,
          color: Colors.TEXT.SECONDARY,
        }}
      >
        ×
      </button>
    </span>
  );
};
