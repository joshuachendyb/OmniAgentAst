// 编辑历史: 2026-09-13 小欧 - PillBadge 简洁版：胶囊药丸标签+竖线扫光动画 — 小欧-2026-09-13
// 编辑历史: 2026-09-15 小欧 - 扫光keyframes迁 AnimatedIcons/animations.ts 统一承载(北京老陈令):
//   删本地injectShine重复注入逻辑, 改调 injectKeyframes('pillShine') 单例注入(DRY) — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - [40]第一阶段S3/S4: 默认色引 Colors.SUCCESS 去硬编码 + 字号 FontSize.SECONDARY 收敛 — 小欧-2026-09-15
import React from 'react';
// 2026-09-15 小欧 - 动画keyframes统一承载(AnimatedIcons) — 小欧-2026-09-15
import { injectKeyframes } from '../AnimatedIcons/animations';
import { Colors, FontSize } from '@/utils/stepStyles';

interface PillBadgeProps {
  /** 标签文本 */
  text: string;
  /** 背景色，默认Colors.SUCCESS(#52c41a) */
  color?: string;
  /** 启用竖线扫光动画，默认false */
  shine?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const PillBadge: React.FC<PillBadgeProps> = ({
  text,
  color = Colors.SUCCESS,
  shine = false,
  className,
  style,
}) => {
  // 2026-09-15 小欧 - 扫光动画keyframes注入(AnimatedIcons单例承载), 仅在启用时注入 — 小欧-2026-09-15
  if (shine) injectKeyframes('pillShine');

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: 80,
        height: 22,
        borderRadius: 11,
        color: '#fff',
        fontSize: FontSize.SECONDARY,
        fontWeight: 500,
        padding: '0 10px',
        ...(shine
          ? {
              backgroundSize: '200% 200%',
              backgroundImage: `linear-gradient(180deg, ${color} 0%, ${color} 35%, rgba(255,255,255,0.6) 50%, ${color} 65%, ${color} 100%)`,
              animation: 'pillShine 2.5s ease-in-out infinite',
            }
          : { background: color }),
        ...style,
      }}
    >
      {text}
    </span>
  );
};

export { PillBadge };
export type { PillBadgeProps };
