// 编辑历史: 2026-09-13 小欧 - CircleArrow 简洁版：圆形+实心三角+折叠旋转 — 小欧-2026-09-13
// 编辑历史: 2026-09-15 小欧 - [40]第一阶段: 默认色引 Colors 令牌(FOLD_COLLAPSED/FOLD_EXPANDED/BORDER.LIGHT)去硬编码(S5);
//   新增 animated prop(默认true)——内部折叠传 animated=false 保持静止, 主折叠保留旋转动画 — 小欧-2026-09-15
import React from 'react';
import { Colors } from '@/utils/stepStyles';

interface CircleArrowProps {
  /** 圆形直径，默认28 */
  size?: number;
  /** 三角颜色，默认Colors.FOLD_COLLAPSED(#4096ff) */
  color?: string;
  /** 展开时三角颜色，默认Colors.FOLD_EXPANDED(#ff4d94) */
  expandedColor?: string;
  /** 是否展开态（旋转180°），默认false */
  expanded?: boolean;
  /** 是否启用发光动画，默认false */
  glow?: boolean;
  /** 是否启用旋转动画，默认true；内部折叠传false保持静止 — 小欧-2026-09-15 */
  animated?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const CircleArrow: React.FC<CircleArrowProps> = ({
  size = 28,
  color = Colors.FOLD_COLLAPSED,
  expandedColor = Colors.FOLD_EXPANDED,
  expanded = false,
  glow = false,
  animated = true,
  className,
  style,
}) => {
  const triColor = expanded ? expandedColor : color;

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: size,
        height: size,
        borderRadius: '50%',
        background: Colors.BORDER.LIGHT,
        flexShrink: 0,
        boxShadow: glow ? `0 0 4px ${triColor}, 0 0 8px ${triColor}44` : undefined,
        transition: 'box-shadow 0.3s',
        ...style,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 28 28"
        fill="none"
        style={{
          transition: animated ? 'transform 0.2s' : undefined,
          transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
        }}
      >
        <path d="M6 11L14 19L22 11Z" fill={triColor} />
      </svg>
    </span>
  );
};

export { CircleArrow };
export type { CircleArrowProps };
