// 编辑历史: 2026-09-13 小欧 - PillBadge 简洁版：胶囊药丸标签+竖线扫光动画 — 小欧-2026-09-13
import React from 'react';

interface PillBadgeProps {
  /** 标签文本 */
  text: string;
  /** 背景色，默认#52c41a */
  color?: string;
  /** 启用竖线扫光动画，默认false */
  shine?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

// 扫光动画样式，只注入一次
let injected = false;
const injectShine = () => {
  if (injected) return;
  injected = true;
  const el = document.createElement('style');
  el.textContent = `@keyframes pillShine{0%{background-position:0 200%}100%{background-position:0 -100%}}`;
  document.head.appendChild(el);
};

const PillBadge: React.FC<PillBadgeProps> = ({
  text,
  color = '#52c41a',
  shine = false,
  className,
  style,
}) => {
  if (shine) injectShine();

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
        fontSize: 12,
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
