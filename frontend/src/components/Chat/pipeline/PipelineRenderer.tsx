// 编辑历史: 2026-08-26 小欧 - 8.4.9 实施: 消息流水线渲染器, 按事件seq序产出段, 相邻同类合并, 实时与回放共用(4.4.2①/3.7.6)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 消除map自增副作用, 预计算lastThink判定光标(11)
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P1-2/P1-6: 流水线容器左线化(borderLeft2px#e8e8e8+paddingLeft12+marginTop4), 靠换行+缩进+左线替代卡片; 段距已统一8px0
// 编辑历史: 2026-08-28 小欧 - ④A/a1: 左线令牌化 Colors.BORDER.VERTICAL
/**
 * PipelineRenderer - 消息流水线渲染器
 *
 * 【小欧 2026-08-26 8.4.9 / R1-B1 修正】按事件到达序产出"段"，相邻同类合并，
 * 不做分组重排（4.4.2① 流水线顺序=事件 seq 顺序）；实时与回放共用（3.7.6）。
 * 段类型：thinking / text / final / tool(含挂接 observations) / obs(孤儿观察) / error。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import type { ExecutionStep } from '../../../types/execution';
import { ThinkingStream } from './ThinkingStream';
import { ResponseStream } from './ResponseStream';
import { ToolCallLine } from './ToolCallLine';
import { StatusLine } from './StatusLine';
import { Colors, BorderWidth, FontSize } from '@/utils/stepStyles';

export type PipelineSegment =
  | { kind: 'thinking'; text: string }
  | { kind: 'text'; text: string }
  | { kind: 'final'; step: ExecutionStep }
  | { kind: 'tool'; action: ExecutionStep; observations: ExecutionStep[] }
  | { kind: 'obs'; step: ExecutionStep }
  | { kind: 'error'; step: ExecutionStep };

/** 纯函数：业务步骤 -> 顺序段（可单测） */
export const buildSegments = (steps: ExecutionStep[]): PipelineSegment[] => {
  const segs: PipelineSegment[] = [];
  const appendToLast = (kind: 'thinking' | 'text', text: string) => {
    const last = segs[segs.length - 1];
    if (last && last.kind === kind) last.text += text;
    else segs.push({ kind, text } as PipelineSegment);
  };
  for (const s of steps) {
    switch (s.type) {
      case 'thought-start':
        break; // 光标信号由 streaming prop 承载，不产出内容
      case 'chunk':
        if (s.is_reasoning) appendToLast('thinking', s.content ?? '');
        else appendToLast('text', s.content ?? '');
        break;
      case 'thought':
        // 回放重建思考流（stream_reader 只取 thought/reasoning）
        appendToLast('thinking', s.thought || s.content || '');
        break;
      case 'action':
        segs.push({ kind: 'tool', action: s, observations: [] });
        break;
      case 'observation': {
        const last = segs[segs.length - 1];
        if (last && last.kind === 'tool') last.observations.push(s);
        else segs.push({ kind: 'obs', step: s }); // 无前置 action 的孤儿观察，独立弱化行
        break;
      }
      case 'final':
        segs.push({ kind: 'final', step: s });
        break;
      case 'error':
        segs.push({ kind: 'error', step: s });
        break;
      default:
        break;
    }
  }
  return segs;
};

interface PipelineRendererProps {
  steps: ExecutionStep[];
  streaming?: boolean; // 实时流进行中（思考流尾随光标）
  highlightToolName?: string | null; // HITL 弹窗联动高亮（4.7）
  headerNode?: React.ReactNode; // 头部·模型标识
}

const PipelineRenderer: React.FC<PipelineRendererProps> = ({
  steps,
  streaming = false,
  highlightToolName = null,
  headerNode,
}) => {
  const segs = buildSegments(steps);
  // 2026-08-27 小欧 三堂会审: 预计算最后一个思考段索引, 消除map内自增副作用与额外filter
  const lastThink = segs.reduce((a, s, i) => (s.kind === 'thinking' ? i : a), -1);
  return (
    <div
      style={{
        fontSize: 14,
        lineHeight: 1.8,
        borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
        paddingLeft: 12,
        marginTop: 4,
      }}
    >
      {headerNode}
      {segs.map((seg, i) => {
        if (seg.kind === 'thinking') {
          const cursor = streaming && i === lastThink;
          return <ThinkingStream key={i} text={seg.text} cursor={cursor} />;
        }
        if (seg.kind === 'text') {
          return (
            <div
              key={i}
              style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
            >
              {seg.text}
            </div>
          );
        }
        if (seg.kind === 'final') {
          return (
            <ResponseStream
              key={i}
              text={seg.step.response || seg.step.content || ''}
              cancelled={seg.step.outcome === 'cancelled'}
            />
          );
        }
        if (seg.kind === 'tool') {
          return (
            <ToolCallLine
              key={i}
              action={seg.action}
              observations={seg.observations}
              highlight={
                highlightToolName != null &&
                !!seg.action.tools?.some((t) => t.tool === highlightToolName)
              }
            />
          );
        }
        if (seg.kind === 'obs') {
          // 孤儿观察：无前置 action，独立弱化行展示摘要
          return (
            <div
              key={i}
              style={{ color: Colors.SUCCESS, fontSize: FontSize.TERTIARY, margin: '8px 0' }}
            >
              📋 {seg.step.summary || seg.step.content || ''}
            </div>
          );
        }
        return <StatusLine key={i} step={seg.step} />;
      })}
    </div>
  );
};

export { PipelineRenderer };
