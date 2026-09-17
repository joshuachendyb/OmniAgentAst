// 编辑历史: 2026-08-26 小欧 - 8.4.12 实施: 状态行仅error渲染红字, 其余状态归任务信息条(4.9.1⑤)
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距-P0-1: 段距margin6px0→8px0统一流水线节奏
// 编辑历史: 2026-08-30 小欧 - 第十三章13.10.3.1(设计文档[2]13.12.7, 北京老陈 2026-08-30 批准): 段距落 Spacing.MD 常量(数值不变8px, 去魔法数字) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 段距改走 stepMargin(false)=(MD-2)=6, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-09-15 小欧 - 历史补记(工作区已落地改动核查补齐): 错误态去⚠️emoji前缀改纯文本, 样式令牌化增强——
//   padding(XS,SM)/background Colors.ERROR_BG/border Colors.ERROR_BORDER/borderRadius Radius.SM/lineHeight=字号+Spacing.XS — 小欧-2026-09-15
/**
 * StatusLine - 状态行（仅 error 渲染）
 *
 * 【小欧 2026-08-26 8.4.12】4.9.1⑤ 状态行仅当 error 步骤渲染：红色小字错误信息；
 * 其余状态(start/paused/resumed/retrying/usage/stats/truncated 等)均不在此渲染，
 * 归任务信息条(8.6)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import type { ExecutionStep } from '@/types/execution';
import {
  Colors,
  FontSize,
  Spacing,
  Radius,
  stepMargin,
} from '@/utils/stepStyles';

interface StatusLineProps {
  step: ExecutionStep; // type=error
}

const StatusLine: React.FC<StatusLineProps> = ({ step }) => {
  if (step.type !== 'error') return null;
  return (
    <div
      style={{
        color: Colors.ERROR,
        fontSize: FontSize.TERTIARY,
        lineHeight: `${FontSize.TERTIARY + Spacing.XS}px`,
        margin: stepMargin(false),
        padding: `${Spacing.XS}px ${Spacing.SM}px`,
        background: Colors.ERROR_BG,
        border: `1px solid ${Colors.ERROR_BORDER}`,
        borderRadius: Radius.SM,
      }}
    >
      {step.error_message || step.details || step.content || '执行出错'}
    </div>
  );
};

export { StatusLine };
