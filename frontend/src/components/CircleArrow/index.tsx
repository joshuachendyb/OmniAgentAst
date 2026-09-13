// 编辑历史: 2026-09-13 小欧 - CircleArrow 简洁版：圆形+实心三角+折叠旋转 — 小欧-2026-09-13
import React from 'react';

interface CircleArrowProps {
  /** 圆形直径，默认28 */
  size?: number;
  /** 三角颜色，默认#4096ff */
  color?: string;
  /** 展开时三角颜色，默认#ff4d94 */
  expandedColor?: string;
  /** 是否展开态（旋转180°），默认false */
  expanded?: boolean;
  /** 是否启用发光动画，默认false */
  glow?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const CircleArrow: React.FC<CircleArrowProps> = ({
  size = 28,
  color = '#4096ff',
  expandedColor = '#ff4d94',
  expanded = false,
  glow = false,
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
        background: '#f0f0f0',
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
          transition: 'transform 0.2s',
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
