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
import type { ExecutionStep } from '../../../utils/sse';

interface StatusLineProps {
  step: ExecutionStep; // type=error
}

const StatusLine: React.FC<StatusLineProps> = ({ step }) => {
  if (step.type !== 'error') return null;
  return (
    <div style={{ color: '#cf1322', fontSize: 13, margin: '6px 0' }}>
      ⚠️ {step.error_message || step.details || step.content || '执行出错'}
    </div>
  );
};

export { StatusLine };
