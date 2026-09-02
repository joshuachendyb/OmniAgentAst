// 编辑历史: 2026-08-26 小欧 - 8.4.9 实施: 消息流水线渲染器, 按事件seq序产出段, 相邻同类合并, 实时与回放共用(4.4.2①/3.7.6)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 消除map自增副作用, 预计算lastThink判定光标(11)
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P1-2/P1-6: 流水线容器左线化(borderLeft2px#e8e8e8+paddingLeft12+marginTop4), 靠换行+缩进+左线替代卡片; 段距已统一8px0
// 编辑历史: 2026-08-28 小欧 - ④A/a1: 左线令牌化 Colors.BORDER.VERTICAL
// 编辑历史: 2026-08-30 小欧 - 第十三章13.10.3.1(设计文档[2]13.12.1, 北京老陈 2026-08-30 批准): 正文 text 段接入 TextStream 打字机(预计算 lastText 作实时累积段); 容器 paddingLeft→Spacing.LG、marginTop→Spacing.XS、obs 失孤行 margin→Spacing.MD 去魔法数字 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈 标注修正(step之间8/step内部文字6/观察折叠内4): text 段同 step 后续标记 sameStep(thought的reasoning+thought), 主段 step 间距收敛 MD(8), 同 step 内文字块走 compact(6) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): stepMargin(false)=(MD-2)=6 统一 step 段距(obs 孤儿行同步), 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 北京老陈最新定案(字体留白全0 + 行高=字号+4): 容器 line-height=字号+Spacing.XS(4)(行间距4), step 间 SM6/step 内文字 XS4 折不折同 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - final段修复: 流式不渲染(chunks已展示), 历史回放渲染reasoning+response两字段(此前仅response遗漏reasoning)
// 编辑历史: 2026-09-02 小欧 - 北京老陈定案(流水线等待光标UI设计 v1.6): 光标/打字机判定末段化(修复旧思考段光标常亮); 新增waiting判定, 末段非thinking/text且streaming时渲染SVG缺口圆弧等待符号(1.4em≈20px, #52c41a, stroke-width2, 逆时针1s转圈); 首chunk到达末段变content段waiting即消失, 内容从同一首列打字机接管, 等待符号禁止常驻
// 编辑历史: 2026-09-02 小欧 - 修复final段失败终态不显原因(北京老陈反馈: 失败任务右栏最后仅"任务执行失败"无原因):
//   final段历史回放渲染 outcome=failed 时补 error_type/error_message 红字行(⚠[llm_error] 具体原因, 对齐StatusLine红字小字样式);
//   数据链路本就贯通(sseParser:119-120 已解析outcome/error_type/error_message, FinalStep.to_dict输出:111-112原样透传),
//   此前仅渲染 response/reasoning 二字段漏了错误字段; second修订: outcome三态显式分支(completed正常/failed红字原因行/cancelled弱化"已取消") - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - HIT三处修复C: waiting判定加highlightToolName保活, HIT高亮时保持等待可见消确认后闪消 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 三堂会审定稿(北京老陈驱动, 根治等待圈三处丢失窗口): waiting判定由 streaming 单一依赖改
//   taskActive = streaming||highlight||badge(running/paused), badge 复用 useTaskInfo 权威派生(paused→running 回推已实现,
//   useTaskInfo.ts:109-170), 渲染器不重造业务判断; 覆盖: ①首屏 serverTaskId→activeTaskId 同步窗口 streaming=false 圈不亮
//   (startinfo 已到且 receiving → badge=running 撑圈) ②HIT挂起>60s 空闲超时重连 disconnect isReceiving=false 圈闪失
//   (badge 仍 paused/running 撑圈) ③HIT confirm 后 resumed 前 highlight 已清 null 圈闪失(badge 仍 paused 撑圈);
//   非 live 历史回放 badge=undefined, 不显示圈 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 三堂会审task005-BUG-005修复: ToolCallLine key由索引i改step序号(任务切换时卸载重建, 展开状态不残留)
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①buildSegments去原地突变last.text改不可变更新(防污染缓存)②ThinkingStream/TextStream key由i改稳定key(防索引复用串味)③waiting终态守卫lastSeg.kind !== 'final'防失败后转圈 — 小欧-2026-09-02
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
import type { ExecutionStep } from '../../../../types/execution';
import type { TaskBadge } from '../../hooks/useTaskInfo'; // 2026-09-02 小欧: waiting 取 badge 权威派生
import { ThinkingStream } from './ThinkingStream';
import { ResponseStream } from './ResponseStream';
import { ToolCallLine } from './ToolCallLine';
import { StatusLine } from './StatusLine';
import { TextStream } from './TextStream'; // 13.8 正文打字机 — 小欧 2026-08-30
import {
  Colors,
  BorderWidth,
  FontSize,
  Spacing,
  stepMargin,
} from '@/utils/stepStyles';

export type PipelineSegment =
  | { kind: 'thinking'; text: string; sameStep?: boolean } // sameStep: 同 step 内部(13.6 reasoning+thought)→compact SM(6)
  | { kind: 'text'; text: string; sameStep?: boolean }
  | { kind: 'final'; step: ExecutionStep }
  | { kind: 'tool'; action: ExecutionStep; observations: ExecutionStep[] }
  | { kind: 'obs'; step: ExecutionStep }
  | { kind: 'error'; step: ExecutionStep };

// 可承载 sameStep 的段(thinking/text) — 2026-08-30 小欧 三堂会审: union 含 sameStep 的仅两类, 抽取避免写包任一段
type TextishSegment = Extract<PipelineSegment, { kind: 'thinking' | 'text' }>;

/** 纯函数：业务步骤 -> 顺序段（可单测） */
export const buildSegments = (steps: ExecutionStep[]): PipelineSegment[] => {
  const segs: PipelineSegment[] = [];
  const appendToLast = (
    kind: 'thinking' | 'text',
    text: string
  ): TextishSegment => {
    const last = segs[segs.length - 1];
    if (last && last.kind === kind) {
      const updated = { ...last, text: last.text + text } as TextishSegment;
      segs[segs.length - 1] = updated;
      return updated;
    }
    const seg = { kind, text } as TextishSegment;
    segs.push(seg);
    return seg;
  };
  for (const s of steps) {
    switch (s.type) {
      case 'thought-start':
        break; // 光标信号由 streaming prop 承载，不产出内容
      case 'chunk':
        if (s.is_reasoning) appendToLast('thinking', s.content ?? '');
        else appendToLast('text', s.content ?? '');
        break;
      case 'thought': {
        // 13.6① 两字段契约：reasoning 在前(thinking 灰斜体)、thought 在后(text 正体)；s.content 永不下发不使用
        // 13.6 三堂会审(2026-08-30): 同 step reasoning+thought 两段标 sameStep→compact(6); 单段只按 step 间距 MD(8)
        const hasReasoning = !!s.reasoning && s.reasoning !== s.thought;
        const hasBoth = hasReasoning && !!s.thought;
        // reasoning 合并进旧段(跨 step 相邻 thinking)时非本 step 新建 → 不标 compact, 保持 step 间 MD(8)
        const prevThinkWasLast =
          segs.length > 0 && segs[segs.length - 1].kind === 'thinking';
        if (hasReasoning && s.reasoning) appendToLast('thinking', s.reasoning);
        const thoughtSeg = s.thought ? appendToLast('text', s.thought) : null;
        if (hasBoth && thoughtSeg) {
          thoughtSeg.sameStep = true;
          if (!prevThinkWasLast) {
            const thinkSeg = segs[segs.length - 2];
            if (thinkSeg && thinkSeg.kind === 'thinking') {
              thinkSeg.sameStep = true;
            }
          }
        }
        break;
      }
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
  badge?: TaskBadge; // 2026-09-02 小欧: 任务活跃徽标(running/paused=任务仍进行), 撑起三个 waiting 丢失窗口
}

const PipelineRenderer: React.FC<PipelineRendererProps> = ({
  steps,
  streaming = false,
  highlightToolName = null,
  headerNode,
  badge, // 2026-09-02 小欧: 非 live 历史回放不传 → undefined → 不显示圈
}) => {
  const segs = buildSegments(steps);
  // 2026-08-27 小欧 三堂会审: 预计算最后一个思考段索引, 消除map内自增副作用与额外filter
  const lastThink = segs.reduce(
    (a, s, i) => (s.kind === 'thinking' ? i : a),
    -1
  );
  // 13.8 打字机: 最后一个 text 段为实时累积段(打字), 前序已完成段静态呈现
  const lastText = segs.reduce((a, s, i) => (s.kind === 'text' ? i : a), -1);
  // 2026-09-02 小欧 · 北京老陈定案: 等待 thought——streaming 且末段无 content 段
  // (thinking/text)时, 说明处于 action 执行/新 thought 未到, 在流水线内容输出位置
  // (末段之下; 无任何段时即容器首列)渲染 ↻ 型 SVG 缺口圆弧; 首 chunk 到达,
  // 末段变 thinking/text, waiting 即消失, 内容从同一首列打字机输出——等待符号
  // 禁止常驻, 由内容覆盖接管
  // 2026-09-02 小欧 HIT三处修复C: HIT高亮时保持等待可见, 消确认后圈闪消
  // 2026-09-02 小欧 三堂会审定稿: streaming 单一依赖改 taskActive 三源(streaming/highlight/badge),
  //   根治①首屏任务ID同步窗口②HIT挂起>60s空闲超时重连③confirm-resumed间隙三处圈丢失
  const lastSeg = segs[segs.length - 1];
  const taskActive =
    streaming ||
    !!highlightToolName ||
    badge === 'running' ||
    badge === 'paused'; // 2026-09-02 小欧: badge 权威派生(running=连接中但内容空窗, paused=HIT/卡顿挂起)
  const waiting =
    taskActive &&
    (!lastSeg ||
      (lastSeg.kind !== 'thinking' &&
        lastSeg.kind !== 'text' &&
        lastSeg.kind !== 'final'));
  return (
    <div
      style={{
        fontSize: FontSize.PRIMARY,
        lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
        borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
        paddingLeft: Spacing.LG,
        marginTop: Spacing.XS,
      }}
    >
      {headerNode}
      {segs.map((seg, i) => {
        if (seg.kind === 'thinking') {
          // 2026-09-02 小欧 · 北京老陈定案: 光标仅亮在"最后一段"(打字机末段), 旧 thinking 段完成即灭
          const cursor = streaming && i === lastThink && i === segs.length - 1;
          return (
            <ThinkingStream
              key={`thinking-${i}-${seg.text.slice(0, 16)}`}
              text={seg.text}
              cursor={cursor}
              compact={seg.sameStep}
            />
          );
        }
        if (seg.kind === 'text') {
          // 2026-09-02 小欧: 限定末段, 与 thinking 光标同策略
          const isLive = streaming && i === lastText && i === segs.length - 1;
          return (
            <TextStream
              key={`text-${i}-${seg.text.slice(0, 16)}`}
              text={seg.text}
              typing={isLive}
              cursor={isLive}
              compact={seg.sameStep}
            />
          );
        }
        if (seg.kind === 'final') {
          // 小欧 2026-08-30: 流式chunks已展示thought/reasoning/response, final不重复;
          //   历史回放无chunks, final是唯一载体, 需渲染reasoning+response两个字段
          if (streaming) return null;
          const reasoning = seg.step.reasoning;
          // 小欧 2026-09-02: 终态三态显式分支（completed/failed/cancelled）——
          //   cancelled 弱化小字"已取消"、failed 红字原因行(error_type/error_message)、
          //   completed 正常 response；三者互斥走齐不留默认吞掉
          const isFailed = seg.step.outcome === 'failed';
          const isCancelled = seg.step.outcome === 'cancelled';
          return (
            <React.Fragment key={`final-${i}-${seg.step.step ?? i}`}>
              {reasoning && (
                <div
                  style={{
                    color: Colors.TEXT.SECONDARY,
                    fontStyle: 'italic',
                    fontSize: FontSize.TERTIARY,
                    lineHeight: `${FontSize.TERTIARY + Spacing.XS}px`,
                    margin: stepMargin(false),
                  }}
                >
                  {reasoning}
                </div>
              )}
              {isFailed ? (
                <React.Fragment>
                  <ResponseStream
                    text={seg.step.response || seg.step.content || ''}
                  />
                  {(seg.step.error_message || seg.step.error_type) && (
                    <div
                      style={{
                        color: Colors.ERROR,
                        fontSize: FontSize.TERTIARY,
                        lineHeight: `${FontSize.TERTIARY + Spacing.XS}px`,
                        margin: stepMargin(false),
                      }}
                    >
                      ⚠️ [{seg.step.error_type || 'error'}]{' '}
                      {seg.step.error_message}
                    </div>
                  )}
                </React.Fragment>
              ) : (
                <ResponseStream
                  text={seg.step.response || seg.step.content || ''}
                  cancelled={isCancelled}
                />
              )}
            </React.Fragment>
          );
        }
        if (seg.kind === 'tool') {
          return (
            <ToolCallLine
              key={seg.action.step ?? i}
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
              key={`obs-${i}-${seg.step.step ?? i}`}
              style={{
                color: Colors.SUCCESS,
                fontSize: FontSize.TERTIARY,
                lineHeight: `${FontSize.TERTIARY + Spacing.XS}px`,
                margin: stepMargin(false),
              }}
            >
              📋 {seg.step.summary || seg.step.content || ''}
            </div>
          );
        }
        return (
          <StatusLine
            key={`status-${i}-${seg.step.step ?? i}`}
            step={seg.step}
          />
        );
      })}
      {waiting && (
        <div
          style={{
            margin: stepMargin(false),
          }}
        >
          <span className="waiting-cursor" aria-label="等待下一个思考内容">
            <svg
              width="1.4em"
              height="1.4em"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#52c41a"
              strokeWidth={2}
              strokeLinecap="round"
            >
              <path d="M21 12a9 9 0 1 1-6.219-8.56" />
            </svg>
          </span>
        </div>
      )}
    </div>
  );
};

export { PipelineRenderer };
