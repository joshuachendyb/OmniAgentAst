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
// 编辑历史: 2026-09-02 小欧 - 等待图标残留丢失根治(北京老陈驱动三堂会审): waiting守卫补 error 终态(exclude error与final同为终态, 防止error后转圈); 场景穷举12种, 残留主因为纯网络空闲断连isCurrentLive瞬false, 由RightViewer isCurrentLive改 (receiving||badge running/paused) 共担
// 编辑历史: 2026-09-03 小欧 - Bug-9: waiting 判定排除 tool 段 — 末段为工具段时不再叠加底部绿色缺口圆弧(双动画), 工具等待由 ToolCallLine 橙齿轮+扳手唯一承载
// 编辑历史: 2026-09-03 小欧 D2-07: waiting补排除obs孤儿观察（与final/error同终态），防绿圈残留
// 编辑历史: 2026-09-03 小欧 P3/P4/P5修复: buildSegments action段按step去重, 防重复seq致双实例(空obs走超时+有obs走子行并存)
// 编辑历史: 2026-09-03 小欧 P2修复: waiting判定tool段改为有obs时排除/无obs时保留, 恢复每轮thought前绿圈复现语义
// 编辑历史: 2026-09-03 小沈 P3/P4/P5修复修正: buildSegments action去重改不可变更新(原existingTool.action=s原地突变违反BUG-18不可变原则)
// 编辑历史: 2026-09-03 小沈 thought/action等待图标修复: 修正小欧P2(第29行)/D2-07(第27行)方向反转——
//   tool有obs(工具完成等待LLM下一轮thought)应保留绿圈(observations.length>0), tool无obs(action执行中由ToolCallLine齿轮承载)应排除;
//   obs孤儿观察段(结果已到等待LLM下一轮)应保留绿圈(去掉obs排除); 场景穷举6种: 无段✅thinking/text✅tool无obs✅tool有obs✅obs✅final/error✅ - 小沈-2026-09-03
// 编辑历史: 2026-09-03 小欧/北京老陈 v5.1 observation统一存obs段, 不挂tool
// 编辑历史: 2026-09-03 小欧/北京老陈 v5.1 showGreenCircle正向判断替代6条件否定式
// 编辑历史: 2026-09-03 小欧/北京老陈 v5.1 ToolCallLine从segments数组按step找obs传入(修复obs独立后扳手一直转)
// 编辑历史: 2026-09-03 小欧/北京老陈 v5.1 waiting变量改名showGreenCircle语义更清晰
// 编辑历史: 2026-09-04 小欧 - 修复 observation 重复显示(单/多工具并行时孤儿与 ToolCallLine 重复): toolStepSet 抑制已消费孤儿渲染 - 小欧-2026-09-04
// 编辑历史: 2026-09-06 小欧 - B2时序(北京老陈定案: action先于弹窗发): blocked 工具也进 action.tools(无 obs), toolDenied 判定纳入 blocked 停齿轮防空转 - 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2三思三省修订(北京老陈驱动): interrupted 由"任一error存在"改"整批计数判定"——未执行工具数(blocked/user_rejected/timeout)>=tools总数才停齿轮; 修"1拒+1执行中"短暂误灰字缝隙 - 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(北京老陈裁定): 拒绝独立type="user_rejected"事件+error blocked/timeout两路实时聚合deniedSteps(Map step→计数),
//   interrupted 整批计数判定数据源从"error段"换deniedSteps(erro事件不入liveSteps=原计数永远0=死代码); ToolCallLine传replay=!streaming(回放免齿轮) - 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2(J1缝隙修复, 北京老陈核验): tool段新增candidateCount(预览全量候选数), buildSegments去重时预览先到
//   canonical后覆盖, candidateCount取预览候选总数并保留; allDenied分母由seg.action.tools(被canonical覆盖后缩为执行集)改为
//   candidateCount —— 原代码2工具1拒+1执行中: denied=1>=执行集长度1 误判全拒停齿轮(违"1拒+1执行中→齿轮保持"裁定), 改后1<2齿轮保持 — 小欧-2026-09-06
// 编辑历史: 2026-09-07 小欧 - 4.4.2 thought-start→waiting 段(时序根治 前端消息分类处理分析及设计-小欧-2026-09-06.md 4.4.2):
//   ①union 新增 {kind:'waiting', step?} 段——thought-start 由"break 丢弃"改为落段(信号真正驱动图标, 取代条件推断);
//   ②appendToLast 就地覆盖 waiting——首个内容(chunk/thought)到达, waiting 段原位变 thinking/text, 图标位变文字(内容覆盖制);
//   ③渲染分支门控: waiting 仅"末段+taskActive"亮圈(非末段/历史回放 taskActive=false 自动灭, 杜绝常驻);
//   UI 观感机制不变(该亮照亮、内容到即消失), showGreenCircle 保留(空容器/obs 窗口), waiting 为末段时其条件不成立无双圈 — 小欧-2026-09-07
// 编辑历史: 2026-09-07 小欧 - 4.4.2 DRY 重构(北京老陈审查, 10大规范): 等待图标 SVG markup 两处重复
//   (waiting 段渲染分支 + showGreenCircle 兜底) → 抽唯一 WaitingIcon 组件共用; 行为零变化(测试全绿前提下, 设计3.4原则七) — 小欧-2026-09-07
// 编辑历史: 2026-09-07 小欧 - 4.4.2 旧逻辑清理(北京老陈定案, 设计3.4原则七"showGreenCircle 去留"):
//   删除 showGreenCircle 双条件推断(!lastSeg || lastSeg.kind==='obs')整段 —— 等待图标改由 thought-start 信号唯一驱动
//   (每可见轮 LLM 请求前必发, 产 waiting 段, 内容覆盖制); 空容器首圈由首信号到达即亮, obs 后等待由紧邻 thought-start
//   (waiting 段)承接, 同批 SSE 无缝隙, 不再双机制并行; 相关旧注释块一并清除 — 小欧-2026-09-07
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定 被拒工具 UI 灰字): 新增 deniedEntries prop, tool 段按 step
//   取出被拒工具点名条传入 ToolCallLine(部分拒/全拒对被拒工具显橘红灰字点名单) — 小欧-2026-09-06
// 编辑历史: 2026-09-09 小欧 - A2修复(跨任务 step 号回绕互踩): buildSegments tool 段去重升级——同 step 仅允许
//   preview+canonical 各一次合一(保持 UI 一行契约, candidateCount 以预览全量为准), 第三次起的同 step action
//   (跨任务/异常残留)独立追加不覆盖历史段, 杜绝"旧任务工具行被新任务同 step 覆盖篡改" — 小欧-2026-09-09
// 编辑历史: 2026-09-11 小欧 - 修复reasoning/thought重复: thought步骤的reasoning字段与chunk步骤(is_reasoning=true)内容重叠时去重, 防appendToLast拼接致双倍文本 - 小欧-2026-09-11
// 编辑历史: 2026-09-13 小欧 - Prettier 格式统一(前端源码格式专项, 纯格式零逻辑): 对齐项目 prettier 排版规范 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - [35]thought-action等待状态实施: 内联WaitingIcon拆为WaitingIcons控件ThoughtWaitingIcon; 新增action-waiting段
//   (thinking末段+taskActive时组件体内追加ActionWaitingIcon段, 北京老陈令选G波纹扩散样式, action到达/任务结束自动消失);
//   union加action-waiting类型, 渲染分支加ActionWaitingIcon; 注释统一用组件名(ThoughtWaitingIcon/ToolWaitingIcon/ActionWaitingIcon) — 小欧-2026-09-13
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
  ThoughtWaitingIcon,
  ActionWaitingIcon,
} from '@/components/WaitingIcons'; // 2026-09-13 小欧: ThoughtWaitingIcon/ActionWaitingIcon 从内联提取为独立控件 — 小欧-2026-09-13
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
  | {
      kind: 'tool';
      action: ExecutionStep;
      observations: ExecutionStep[];
      candidateCount: number; // 2026-09-06 小欧 B2(J1修复): 该step候选工具总数(预览全量), 供allDenied整批判定 —— canonical覆盖后action.tools缩为执行集, 不得作分母(1拒+1执行中会误停齿轮) — 小欧-2026-09-06
    }
  | { kind: 'obs'; step: ExecutionStep }
  | { kind: 'error'; step: ExecutionStep }
  | { kind: 'waiting'; step?: number } // 4.4.2(2026-09-07 小欧): thought-start 落段, 可被首个内容覆盖接管
  | { kind: 'action-waiting' }; // 2026-09-13 小欧: thinking末段+taskActive时追加ActionWaitingIcon(LLM推理action中)

// 可承载 sameStep 的段(thinking/text) — 2026-08-30 小欧 三堂会审: union 含 sameStep 的仅两类, 抽取避免写包任一段
type TextishSegment = Extract<PipelineSegment, { kind: 'thinking' | 'text' }>;

/** 纯函数：业务步骤 -> 顺序段（可单测） */
export const buildSegments = (steps: ExecutionStep[]): PipelineSegment[] => {
  const segs: PipelineSegment[] = [];
  // A2(2026-09-09 小欧): preview 槽位制——后端 B2 时序约定"每个 action 必先发 preview(tools=全量候选)、
  //   再发 canonical(tools=执行集, 落库)", 二者同 step 属同一轮双保险, 合一为单 tool 段:
  //   canonical 仅允许覆盖"最后一个未配对的 preview 段", 覆盖后槽位清空;
  //   无 preview 配对的 action(跨任务/回绕/异常残留)直接新增独立 tool 段, 兜底绝不让历史段被篡改 — 小欧-2026-09-09
  let pendingPreviewToolIdx = -1;
  const appendToLast = (
    kind: 'thinking' | 'text',
    text: string
  ): TextishSegment => {
    const last = segs[segs.length - 1];
    // 4.4.2(2026-09-07 小欧): 末段为 waiting(首列等待图标)时, 首个内容就地覆盖接管(图标位变文字)
    if (last && last.kind === 'waiting') {
      const updated = { kind, text } as TextishSegment;
      segs[segs.length - 1] = updated;
      return updated;
    }
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
        segs.push({ kind: 'waiting', step: s.step }); // 4.4.2(2026-09-07 小欧): 产 waiting 段, 首个内容到达被覆盖
        break;
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
        // 2026-09-11 小欧 去重: chunk(is_reasoning=true)已流式累积thinking段, thought.reasoning与之重叠时不再追加防双倍
        if (hasReasoning && s.reasoning) {
          const lastSeg = segs[segs.length - 1];
          const alreadyHas =
            lastSeg &&
            lastSeg.kind === 'thinking' &&
            lastSeg.text.endsWith(s.reasoning);
          if (!alreadyHas) appendToLast('thinking', s.reasoning);
        }
        // 2026-09-11 小欧 去重: chunk已流式累积text段, thought字段与之重叠时不再追加防双倍
        let thoughtSeg: TextishSegment | null = null;
        if (s.thought) {
          const lastTextSeg = segs[segs.length - 1];
          const textAlreadyHas =
            lastTextSeg &&
            lastTextSeg.kind === 'text' &&
            lastTextSeg.text.endsWith(s.thought);
          if (!textAlreadyHas) thoughtSeg = appendToLast('text', s.thought);
        }
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
      case 'action': {
        // 2026-09-03 小欧 P3/P4/P5修复: 同step的action段去重, 防重复seq致双实例(一个空obs走超时一个有obs走子行)
        // 2026-09-03 小沈 修正: 原地突变改不可变更新, 与BUG-18修复原则一致(防污染调用方缓存)
        // 2026-09-06 小欧 B2(J1修复): 预览action(tools=全量候选)先到, canonical(tools=执行集)后覆盖——
        //   candidateCount取以致小者优先的预览候选总数, canonical覆盖时保留, 供allDenied作分母(不得用执行集) — 小欧-2026-09-06
        // A2(2026-09-09 小欧): preview 槽位制——preview action 登记"待正式化槽位"并新增 tool 段;
        //   canonical action 仅当存在未配对 preview 槽位时覆盖之(合一为单 tool 段), 覆盖后槽位清空;
        //   无 preview 配对的 action(跨任务/回绕/异常残留)直接新增独立 tool 段, 历史 tool 段永不被篡改 — 小欧-2026-09-09
        if (s.preview) {
          // 登记槽位: 即将 push 的 tool 段索引
          pendingPreviewToolIdx = segs.length;
          segs.push({
            kind: 'tool',
            action: s,
            observations: [],
            // 候选总数以预览全量为准(canonical tools=执行集只减不增, 覆盖时保留预览值)
            candidateCount: s.tools?.length ?? 0,
          });
        } else if (pendingPreviewToolIdx >= 0) {
          const idx = pendingPreviewToolIdx;
          const existing = segs[idx] as Extract<
            PipelineSegment,
            { kind: 'tool' }
          >;
          pendingPreviewToolIdx = -1; // 槽位配对完成, 清空防后续 canonical 再覆盖
          segs[idx] = {
            kind: 'tool',
            action: s,
            observations: existing.observations ?? [],
            candidateCount: existing.candidateCount ?? s.tools?.length ?? 0,
          };
        } else {
          // 无 preview 配对(跨任务/回绕/异常残留): 独立新增, 绝不篡改历史段
          segs.push({
            kind: 'tool',
            action: s,
            observations: [],
            candidateCount: s.tools?.length ?? 0,
          });
        }
        break;
      }
      case 'observation': {
        segs.push({ kind: 'obs', step: s });
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

// 2026-09-11 小欧 复用优先(北京老陈): 终态细节行样式工厂——final段 reasoning/取消来源行/红字错误行
//   结构完全同式仅色异, 抽共用免三处内联重复, 颜色按态传(取消ORANGE_RED/失败ERROR/reasoning灰) — 小欧-2026-09-11
const terminalDetailStyle = (color: string): React.CSSProperties => ({
  color,
  fontSize: FontSize.TERTIARY,
  lineHeight: `${FontSize.TERTIARY + Spacing.XS}px`,
  margin: stepMargin(false),
});

interface PipelineRendererProps {
  steps: ExecutionStep[];
  streaming?: boolean; // 实时流进行中（思考流尾随光标）
  highlightToolName?: string | null; // HITL 弹窗联动高亮（4.7）
  headerNode?: React.ReactNode; // 头部·模型标识
  badge?: TaskBadge; // 2026-09-02 小欧: 任务活跃徽标(running/paused=任务仍进行), 撑起三个 waiting 丢失窗口
  deniedSteps?: ReadonlyMap<number, number>; // 2026-09-06 小欧 B2(方案C): 拒绝/拦截/超时执行轮聚合(step→denied计数), 供停齿轮判定 — 小欧-2026-09-06
  deniedEntries?: ReadonlyMap<number, Array<{ tool: string; reason: string }>>; // 2026-09-06 小欧 B2(6.4): 被拒工具点名条(step→[{tool,reason}]), 传 ToolCallLine 对被拒工具显橘红灰字 — 小欧-2026-09-06
}

const PipelineRenderer: React.FC<PipelineRendererProps> = ({
  steps,
  streaming = false,
  highlightToolName = null,
  headerNode,
  badge, // 2026-09-02 小欧: 非 live 历史回放不传 → undefined → 不显示圈
  deniedSteps, // 2026-09-06 小欧 B2(方案C)
  deniedEntries, // 2026-09-06 小欧 B2(6.4)
}) => {
  const segs = buildSegments(steps);
  // 2026-09-13 小欧 - ActionWaitingIcon segment追加(第4章方案): buildSegments是纯函数(只接收steps),
  //   此处用streaming/badge等组件props判定末段是否需要追加ActionWaitingIcon segment;
  //   末段是thinking + taskActive=true时追加, action到达后tool segment排在后面自然消失 — 小欧-2026-09-13
  const taskActive =
    streaming ||
    !!highlightToolName ||
    badge === 'running' ||
    badge === 'paused';
  // 2026-09-13 小欧 - ActionWaitingIcon segment追加: 末段是thinking + taskActive=true时,
  //   追加ActionWaitingIcon; action到达后tool segment排在它后面自然消失; taskActive=false时不显示
  const lastSeg = segs[segs.length - 1];
  if (lastSeg && lastSeg.kind === 'thinking' && taskActive) {
    segs.push({ kind: 'action-waiting' });
  }
  // 2026-09-04 小欧 - observation 去重：已消费孤儿抑制（单/多工具并行时孤儿与 ToolCallLine 重复）
  const toolStepSet = new Set(
    segs
      .filter(
        (s): s is Extract<PipelineSegment, { kind: 'tool' }> =>
          s.kind === 'tool'
      )
      .map((s) => s.action.step)
  );
  // 2026-08-27 小欧 三堂会审: 预计算最后一个思考段索引, 消除map内自增副作用与额外filter
  const lastThink = segs.reduce(
    (a, s, i) => (s.kind === 'thinking' ? i : a),
    -1
  );
  // 13.8 打字机: 最后一个 text 段为实时累积段(打字), 前序已完成段静态呈现
  const lastText = segs.reduce((a, s, i) => (s.kind === 'text' ? i : a), -1);
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
        if (seg.kind === 'waiting') {
          // 4.4.2(2026-09-07 小欧): thinking段首列亮ThoughtWaitingIcon; 仅"末段+taskActive"才显示,
          //   final/error/停止后非末段自动灭, 杜绝常驻
          if (i !== segs.length - 1 || !taskActive) return null;
          return (
            <div key={`waiting-${i}`} style={{ margin: stepMargin(false) }}>
              <ThoughtWaitingIcon />
            </div>
          );
        }
        if (seg.kind === 'action-waiting') {
          // 2026-09-13 小欧: ActionWaitingIcon, 仅末段+taskActive显示, action到达后tool段排在后面自然消失
          if (i !== segs.length - 1 || !taskActive) return null;
          return (
            <div
              key={`action-waiting-${i}`}
              style={{ margin: stepMargin(false) }}
            >
              <ActionWaitingIcon />
            </div>
          );
        }
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
          // 2026-09-11 小欧 北京老陈定案(最终): 终态三态平铺统一——首行 ResponseStream 共用(completed/failed/cancelled 全是response),
          //   细节行按态条件渲染: cancelled="! 取消来源: cancel_source"橘红(ORANGE_RED)、failed="⚠️ [error_type] error_message"红字,
          //   行样式共用 terminalDetailStyle 工厂, 不复用无中间态嵌套 — 小欧-2026-09-11
          const isFailed = seg.step.outcome === 'failed';
          const isCancelled = seg.step.outcome === 'cancelled';
          return (
            <React.Fragment key={`final-${i}-${seg.step.step ?? i}`}>
              {reasoning && (
                <div style={terminalDetailStyle(Colors.TEXT.SECONDARY)}>
                  {reasoning}
                </div>
              )}
              <ResponseStream
                text={seg.step.response || seg.step.content || ''}
              />
              {isCancelled && seg.step.cancel_source && (
                <div style={terminalDetailStyle(Colors.ORANGE_RED)}>
                  ! 取消来源: {seg.step.cancel_source}
                </div>
              )}
              {isFailed && (seg.step.error_message || seg.step.error_type) && (
                <div style={terminalDetailStyle(Colors.ERROR)}>
                  ⚠️ [{seg.step.error_type || 'error'}] {seg.step.error_message}
                </div>
              )}
            </React.Fragment>
          );
        }
        if (seg.kind === 'tool') {
          const toolObs = segs
            .filter(
              (s): s is Extract<PipelineSegment, { kind: 'obs' }> =>
                s.kind === 'obs' && s.step.step === seg.action.step
            )
            .map((s) => s.step);
          // 2026-09-06 小欧 B2(方案C, 北京老陈裁定): action 先于弹窗发→被拒/拦截/超时工具无 observation, 齿轮需停转;
          //   interrupted 由 deniedSteps 实时聚合判定(step→denied计数, 两路来源: 独立 user_rejected 事件 + error
          //   blocked/timeout), 整批计数语义与 09-06 三思三省修订一致——denied 计数 >= 候选工具总数才停齿轮防空转,
          //   部分拒+部分执行中 -> denied 数 < 候选总数 -> 齿轮保持(还有工具在跑), 有 obs 则真实执行不停转;
          //   分母用 tool 段保留的 candidateCount(预览全量候选数), 不用 seg.action.tools(预览被 canonical 覆盖后
          //   缩为执行集, 例 2工具1拒1执行中: denied=1>=执行集长度1 → 误判全拒停齿轮; candidateCount=2 → 1<2 齿轮保持)
          //   — 小欧-2026-09-06
          //   数据源从"error 段计数"(error 不入 liveSteps→恒空=死代码) 换为 deniedSteps 实时聚合 — 小欧-2026-09-06
          const toolDeniedCount =
            deniedSteps?.get(seg.action.step as number) ?? 0;
          const allDenied =
            toolDeniedCount >=
            (seg.candidateCount ?? seg.action.tools?.length ?? 0);
          return (
            <ToolCallLine
              key={seg.action.step ?? i}
              action={seg.action}
              observations={toolObs}
              interrupted={toolObs.length === 0 && allDenied}
              replay={!streaming} // 2026-09-06 小欧 B2(北京老陈裁定): 历史回放加了标志就自然不需要齿轮转动, 更简单 — 小欧-2026-09-06
              highlight={
                highlightToolName != null &&
                !!seg.action.tools?.some((t) => t.tool === highlightToolName)
              }
              deniedTools={// 2026-09-06 小欧 B2(6.4): 本执行轮被拒工具点名条(橘红灰字数据源, 按 step 取) — 小欧-2026-09-06
              deniedEntries?.get(seg.action.step as number)}
            />
          );
        }
        if (seg.kind === 'obs') {
          // 2026-09-04 小欧 - 已被 ToolCallLine 消费的 observation 不再渲孤儿，防重复
          if (toolStepSet.has(seg.step.step as number)) return null;
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
    </div>
  );
};

export { PipelineRenderer };
