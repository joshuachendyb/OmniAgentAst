/**
 * PillTip - 顶栏胶囊的 Tooltip 内容骨架(配置胶囊/服务胶囊共用)
 * 视觉结构: 状态点+标题 / 副说明 / 分隔线 / 键值行(标签列对齐) / 明细条目 / 动作出路
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - 新建: 两胶囊 Tip 统一骨架(北京老陈令: 按高级设计师水准重做视觉), 全令牌零硬编码色值 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 版式定稿: 白色卡片浮层(浅底文字令牌), 字号收14/12两档, 键值行改栅格40px对齐 — 小欧-2026-11-02
import React, { type CSSProperties } from 'react';
import {
  Spacing,
  FontSize,
  FontWeight,
  Colors,
  BorderWidth,
  FontFamily,
} from '../../utils/stepStyles';

type Tone = 'ok' | 'warn' | 'error' | 'neutral';

// 2026-11-02 小欧 - 浮层版式常量: 宽度区间/标签列宽(两字12px=24+留白)/状态点径/行高比 — 小欧-2026-11-02
const TIP_MIN_W = 240;
/** 内容最大宽, 胶囊侧据此算浮层根宽上限(antd 根节点默认 250px 会提前折行) — 2026-11-02 小欧 */
export const PILL_TIP_MAX_W = 320;
const LABEL_COL_W = 40;
const DOT_SIZE = 8;
const LINE_HEIGHT = 1.6;

const TONE_COLOR: Record<Tone, string> = {
  ok: Colors.SUCCESS,
  warn: Colors.WARNING,
  error: Colors.ERROR,
  neutral: Colors.TEXT.TERTIARY,
};

export interface PillTipRow {
  label: string;
  value: string;
  /** 地址/ID 等机器可读值走等宽字体并可选中复制 */
  mono?: boolean;
}

export interface PillTipItem {
  text: string;
  tone: 'warn' | 'error';
}

export interface PillTipAction {
  label: string;
  onAction: () => void;
}

interface PillTipProps {
  tone: Tone;
  title: string;
  subtitle?: string;
  rows?: PillTipRow[];
  items?: PillTipItem[];
  action?: PillTipAction;
}

const RULE_STYLE: CSSProperties = {
  height: BorderWidth.THIN,
  background: Colors.BORDER.LIGHT,
  margin: `${Spacing.SM}px 0`,
};

// 2026-11-02 小欧 - 白底浮层小字对比度: 标签用 MUTED(#666, 5.7:1)、副说明用 PRIMARY(#595959, 7:1), 均达 AA — 小欧-2026-11-02
const LABEL_STYLE: CSSProperties = {
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.MUTED,
};

export const PillTip: React.FC<PillTipProps> = ({
  tone,
  title,
  subtitle,
  rows,
  items,
  action,
}) => (
  <div style={{ minWidth: TIP_MIN_W, maxWidth: PILL_TIP_MAX_W }}>
    {/* 标题行: 状态点与文案同一基线, 点色即状态语义 */}
    <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.SM }}>
      <span
        style={{
          width: DOT_SIZE,
          height: DOT_SIZE,
          borderRadius: '50%',
          background: TONE_COLOR[tone],
          flex: '0 0 auto',
        }}
      />
      <span
        style={{
          fontSize: FontSize.PRIMARY,
          fontWeight: FontWeight.BOLD,
          color: Colors.TEXT.STRONG,
          letterSpacing: 0.2,
        }}
      >
        {title}
      </span>
    </div>

    {subtitle && (
      <div
        style={{
          marginTop: Spacing.XS,
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.PRIMARY,
          lineHeight: LINE_HEIGHT,
        }}
      >
        {subtitle}
      </div>
    )}

    {!!rows?.length && (
      <>
        <div style={RULE_STYLE} />
        {rows.map((row) => (
          <div
            key={row.label}
            style={{
              display: 'grid',
              gridTemplateColumns: `${LABEL_COL_W}px 1fr`,
              alignItems: 'baseline',
              lineHeight: LINE_HEIGHT,
            }}
          >
            <span style={LABEL_STYLE}>{row.label}</span>
            <span
              style={{
                fontSize: row.mono ? FontSize.CODE : FontSize.SECONDARY,
                fontFamily: row.mono ? FontFamily.MONO : undefined,
                color: Colors.TEXT.STRONG,
                fontVariantNumeric: 'tabular-nums',
                overflowWrap: 'anywhere',
                userSelect: 'text',
              }}
            >
              {row.value}
            </span>
          </div>
        ))}
      </>
    )}

    {!!items?.length && (
      <>
        <div style={RULE_STYLE} />
        {items.map((item, idx) => (
          <div
            key={idx}
            style={{
              display: 'flex',
              gap: Spacing.SM,
              lineHeight: LINE_HEIGHT,
            }}
          >
            <span style={{ color: TONE_COLOR[item.tone] }}>•</span>
            <span
              style={{
                fontSize: FontSize.SECONDARY,
                color: Colors.TEXT.PRIMARY,
              }}
            >
              {item.text}
            </span>
          </div>
        ))}
      </>
    )}

    {action && (
      <>
        <div style={RULE_STYLE} />
        <span
          role="button"
          tabIndex={0}
          aria-label={action.label}
          onClick={(e) => {
            e.stopPropagation();
            action.onAction();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              action.onAction();
            }
          }}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: Spacing.XS,
            fontSize: FontSize.SECONDARY,
            fontWeight: FontWeight.MEDIUM,
            // 2026-11-02 小欧 - 动作链接用 INFO(#096dd9, 白底5.05:1达AA), PRIMARY(#1677ff)仅4.10:1不达 — 小欧-2026-11-02
            color: Colors.INFO,
            cursor: 'pointer',
          }}
        >
          {action.label}
          <span aria-hidden>→</span>
        </span>
      </>
    )}
  </div>
);
