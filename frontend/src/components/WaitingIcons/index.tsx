// 编辑历史: 2026-09-13 小欧 - 新建等待图标控件组: ThoughtWaitingIcon/ToolWaitingIcon/ActionWaitingIcon从PipelineRenderer/ToolCallLine内联提取, 统一导出, DRY复用 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - ActionWaitingIcon换型(北京老陈令选title-icon-compare G波纹扩散): 蓝色270°弧线旋转改蓝核心圆+双层扩散波纹(SVG36x36, .action-ripple-1/.action-ripple-2, 1.8s不旋转) — 小欧-2026-09-13
// 编辑历史: 2026-09-14 小欧 - 漏洞2修复: 组件内5处硬编码SVG色令牌化(绿#52c41a→Colors.SUCCESS / 橙#fa8c16→Colors.WAIT_ACTION / 蓝#1677ff→Colors.PRIMARY), 零行为变化 — 小欧-2026-09-14
import React from 'react';
import { Colors } from '@/utils/stepStyles';

/**
 * ThoughtWaitingIcon — 绿色270°弧线旋转
 * 用途：thought-start到达后、首个thinking chunk到达前的等待状态
 * 原位置：PipelineRenderer.tsx 内联 const WaitingIcon（私有）
 */
export const ThoughtWaitingIcon: React.FC = () => (
  <span className="waiting-cursor" aria-label="等待思考输出">
    <svg
      width="1.4em"
      height="1.4em"
      viewBox="0 0 24 24"
      fill="none"
      stroke={Colors.SUCCESS}
      strokeWidth={2}
      strokeLinecap="round"
    >
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  </span>
);

/**
 * ToolWaitingIcon — 橙色8臂loader旋转
 * 用途：action步到达后、observation到达前的工具执行等待状态
 * 原位置：ToolCallLine.tsx 内联 <svg>（直接嵌JSX无封装）
 */
export const ToolWaitingIcon: React.FC = () => (
  <span className="tool-waiting-cursor" aria-label="等待工具完成">
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke={Colors.WAIT_ACTION}
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 2v4" />
      <path d="M12 18v4" />
      <path d="M4.93 4.93l2.83 2.83" />
      <path d="M16.24 16.24l2.83 2.83" />
      <path d="M2 12h4" />
      <path d="M18 12h4" />
      <path d="M4.93 19.07l2.83-2.83" />
      <path d="M16.24 7.76l2.83-2.83" />
    </svg>
  </span>
);

/**
 * ActionWaitingIcon — 蓝色波纹扩散（G: 波纹扩散样式）
 * 用途：thinking内容显示完毕后、action步到达前的LLM决策等待状态
 * 新增位置：全新组件
 * 动画：蓝核心圆 + 两层扩散波纹，scale 0.5→1.4 + opacity 1→0，1.8s周期，不旋转
 */
export const ActionWaitingIcon: React.FC = () => (
  <span className="action-waiting-cursor" aria-label="等待action到达">
    <svg
      viewBox="0 0 36 36"
      width="1.4em"
      height="1.4em"
      fill="none"
      strokeWidth={2}
    >
      <circle cx="18" cy="18" r="6" stroke={Colors.PRIMARY} />
      <circle
        cx="18"
        cy="18"
        r="10"
        opacity="0.6"
        className="action-ripple-1"
        stroke={Colors.PRIMARY}
      />
      <circle
        cx="18"
        cy="18"
        r="10"
        opacity="0.6"
        className="action-ripple-2"
        stroke={Colors.PRIMARY}
      />
    </svg>
  </span>
);
