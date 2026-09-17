// 编辑历史: 2026-09-15 小欧 - 新建动画图标组件组(北京老陈令): LogoGridIcon(左侧品牌logo 3x3九色点阵,
//   原Layout内联提取, 含LOGO_GRID_CELLS数据) / TitleSpinIcon(右侧顶栏D三色弧段loader, 原Layout内联提取),
//   统一集中管理动画图标, DRY复用 — 小欧-2026-09-15
import React from 'react';

// 2026-09-15 小欧 - 品牌logo九色点阵数据(title-icon-compare 70号斜向波浪):
//   9宫格坐标/颜色/动画延迟单数组, 组件内map渲染, DRY — 小欧-2026-09-15
const LOGO_GRID_CELLS = [
  { x: 4, y: 4, fill: '#1677ff', delay: '0s' },
  { x: 13, y: 4, fill: '#52c41a', delay: '0.35s' },
  { x: 22, y: 4, fill: '#faad14', delay: '0.7s' },
  { x: 4, y: 13, fill: '#fa8c16', delay: '0.35s' },
  { x: 13, y: 13, fill: '#ff4d4f', delay: '0.7s' },
  { x: 22, y: 13, fill: '#eb2f96', delay: '1.05s' },
  { x: 4, y: 22, fill: '#722ed1', delay: '0.7s' },
  { x: 13, y: 22, fill: '#13c2c2', delay: '1.05s' },
  { x: 22, y: 22, fill: '#2f54eb', delay: '1.4s' },
];

/**
 * LogoGridIcon — 左侧顶部品牌logo(3x3九色点阵斜向波浪)
 * 用途：侧栏Logo区品牌标识, 九格 gridwave 2s 斜向波动
 * 原位置：Layout/index.tsx 内联 SVG(北京老陈令选 title-icon-compare 70号)
 */
export const LogoGridIcon: React.FC = () => (
  <span
    className="logo-gridwave-icon"
    aria-label="OmniAgentAst"
    title="OmniAgentAst"
  >
    <svg viewBox="0 0 36 36">
      {LOGO_GRID_CELLS.map((cell) => (
        <rect
          key={`${cell.x}-${cell.y}`}
          className="gridwave"
          x={cell.x}
          y={cell.y}
          width="8"
          height="8"
          rx="2"
          fill={cell.fill}
          style={{ animationDelay: cell.delay }}
        />
      ))}
    </svg>
  </span>
);

/**
 * TitleSpinIcon — 右侧顶栏标题动画圈圈(D三色弧段loader)
 * 用途：顶栏"对话与任务"标识, 三角色弧段复用waiting-spin逆时针1s常转
 * 原位置：Layout/index.tsx 内联 SVG(Tooltip 内嵌, 2026-09-08 标题图标化)
 */
export const TitleSpinIcon: React.FC = () => (
  <span className="title-spin-icon" aria-label="对话与任务">
    <svg
      viewBox="0 0 24 24"
      fill="none"
      strokeWidth={2.5}
      strokeLinecap="round"
    >
      <path d="M12 2v4" stroke="#1677ff" />
      <path d="M16.24 7.76l2.83-2.83" stroke="#1677ff" />
      <path d="M18 12h4" stroke="#1677ff" />
      <path d="M16.24 16.24l2.83 2.83" stroke="#52c41a" />
      <path d="M12 18v4" stroke="#52c41a" />
      <path d="M4.93 19.07l2.83-2.83" stroke="#52c41a" />
      <path d="M2 12h4" stroke="#fa8c16" />
      <path d="M4.93 4.93l2.83 2.83" stroke="#fa8c16" />
    </svg>
  </span>
);
