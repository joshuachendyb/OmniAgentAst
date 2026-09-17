// 编辑历史: 2026-08-26 小欧 - 8.5 实施: 右侧查看区, 当前任务禁REST走liveSteps, 业务步骤分流(7.10/B4/B9)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.1 抽toExecutionSteps收窄unknown[]→ExecutionStep[]替换裸as断言
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审P1-5/边距: 补空/错误三态(Empty暂无执行记录/Skeleton由Spin承载/Alert错误margin8px0#fff2f0隔离); 错误红字与统计块加间距防误读
// 编辑历史: 2026-08-30 小欧 - 修复两个问题: ①auto-scroll: liveSteps变化时滚到底部(仅用户已在底部120px内触发, 防打断手动上翻); ②StaticStatsBlock仅非live时显示(消除执行中提前显示统计块的竞态)
// 编辑历史: 2026-08-30 小欧 - 修复spinner: Spin spinning加!isCurrentLive守卫+setLoading加!isCurrentLive守卫, live模式不触发loading/spinner
// 编辑历史: 2026-09-02 小欧 - task005会审P3修复(北京老陈定案): findScrollContainer 弃字符串选择器 closest('[style*="overflow"]')
//   (仅匹配内联样式, 改CSS类即失效且不报错)→改 getComputedStyle 沿祖先上溯找 overflowY auto/scroll, 稳健且语义等价 — 小欧-2026-09-02
// 编辑历史: 2026-09-01 小欧 - 任务统计增强v0.8: StaticStatsBlock透传chainSteps=historySteps，复用C2步骤数据作工具调用链源 - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 设计文档v1.21§5.7-D落码(工具结果显示与taskinfo显示分析与设计-小欧-2026-09-01.md):
//   error 实时显示唯一位置收口=TaskInfoBar 位4(北京老陈定案): 删 Props :49 liveErrorText 声明 + 解构 :60 +
//   空态条件去 !liveErrorText :172 + 删 error Alert 段 :194-207(其后 :208 StaticStatsBlock 原样保留) + 收回
//   useChatPanels :222 传参(已随 §5.7-C 同提交) + 同步删 import Alert(未用即 ESLint 报错); 防 error 双显示(右栏+位4) — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 修复实时auto-scroll滚动慢/最新被盖住(北京老陈反馈):
//   ①弃 scrollIntoView(smooth)——流式逐chunk增长下smooth动画反复被打断重起追赶不及, 改 scrollTop=scrollHeight 即时到底;
//   ②驱动由 liveSteps.length 改 ResizeObserver 监听流水线内容高度——打字机段逐字增长length不变旧逻辑不触发, 内容增高即滚底;
//   ③沿用"用户已在底部120px内才滚"防打断手动上翻(行为不进反退) - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - HIT三处修复A/B: ①首帧requestAnimationFrame补发消ResizeObserver断档漏触发 ②HIT确认highlightToolName由值→null时无条件滚底防阈值误拦 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 三堂会审定稿(北京老陈驱动, 根治三处不自动上滚): 滚动开关弃 isNearBottom(距底<120px瞬态判定,
//   首屏scrollTop=0内容超一屏即false永不滚) 改 userScrolledUpRef 事件驱动(语义同useChatScroll.ts:57-61, 消息区已验证):
//   ①container scroll监听维护"用户是否主动上翻>120px"标志 ②仅 !userScrolledUpRef 才 scrollTop=scrollHeight 即时滚底
//   (弃 requestAnimationFrame 双帧延迟) ③弃 prevHighlightRef/force(首屏从未滚动→标志false→首帧即滚, HIT确认新内容到达即滚,
//   用户真上翻读历史绝不打断) — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 修复路由切回实时任务不自动滚边界: isCurrentLive从false→true时重置userScrolledUpRef为false,
//   确保实时任务恢复自动滚(用户在历史任务中上翻→切回实时任务→ref保持true→不滚, 属于非预期行为) — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 修复findScrollContainer类型错误(HTMLElement→HTMLDivElement显式as断言, tsc TS2741)
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①RV-02/03去scrollContainerRef缓存与as强转(缓存永不失效+类型谎言)②RV-05 fallback加toExecutionSteps过滤防dirty污染③RV-06 Empty加liveBadge守卫(首chunk前waiting绕过)④RV-01去liveSteps.length驱动防误重置 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 修复auto-scroll完全失效(北京老陈反馈实时任务不自动滚): useEffect依赖加liveSteps.length,
//   原仅isCurrentLive变化时执行, 实时任务开始时liveSteps.length=0→pipelineEndRef=null→effect return, 后续liveSteps增长不触发effect
// 编辑历史: 2026-09-02 小欧 - 修复findScrollContainer永不生效(useCallback依赖[]→liveSteps.length): 组件挂载时pipelineEndRef为null→返回null,
//   liveSteps增长后pipelineEndRef有值但findScrollContainer闭包捕获旧null→仍返回null, ResizeObserver永远不执行
// 编辑历史: 2026-09-02 小欧 - auto-scroll双修复(北京老陈驱动三堂会审):
//   ①渲染条件简化: 实时任务时始终渲染pipelineEndRef(!isCurrentLive&&!loading&&!hasSteps才Empty),
//     原liveBadge条件(startinfo延迟→badge=idle→Empty→pipelineEndRef=null)致auto-scroll完全失效;
//   ②程序滚动标志: isProgramScrollingRef防止stickToBottom设置scrollTop触发scroll事件被误判为用户上翻,
//     microtask重置保证下一个scroll事件正常判断用户真实滚动
// 编辑历史: 2026-09-02 小欧 - 等待图标残留丢失根治(北京老陈驱动三堂会审): isCurrentLive由 receiving 单条件改 (receiving||liveBadge running/paused),
//   根治纯网络空闲断连(无paused)60s重连间隙badge=idle致waiting消失的第4窗口; displaySteps与badge透传不再因SSE瞬断切历史, waiting由badge撑住; PipelineRenderer waiting补 error 终态守卫
// 编辑历史: 2026-09-03 小欧 12.6修复: isCurrentLive增_hasFinal守卫, final已到即转历史拉取, 防receiving=false+running badge永久卡live
// 编辑历史: 2026-09-03 小沈 BUG-01/04修复修正: effect依赖liveSteps.length改hasLiveSteps(0→1触发一次, 后续chunk不重跑), 消scroll监听每chunk重挂载
// 编辑历史: 2026-09-06 小欧 RG-1/RG-2(北京老陈定案直接改码, 文档: 前端问题统一分析-HITL弹窗顺序与后台滚动失效-小欧-2026-09-06):
//   ①新增visibilitychange兜底——浏览器后台节流后切回可见立即重滚到底(对称左栏useChatScroll.ts:93-103);
//   ②主滚动effect守卫由"仅live"放宽为"live或历史数据就绪"——后台任务final切历史(hasHistorySteps 0→1)后首帧滚底, 防右栏停半空;
//   ③抽scrollToBottomNow统一滚底实现(RO/首帧/切历史/visibilitychange共用, DRY) — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定): deniedEntries prop 接收/透传 PipelineRenderer,
//   承被拒工具点名条(橘红灰字)数据链路 — 小欧-2026-09-06
// 编辑历史: 2026-09-09 小欧 - A3修复(final→历史切换竞态): REST拉取对"刚结束的实时任务自身"加 300ms 缓冲——
//   SSE final 先发、DB 落库稍后, 立即拉会拿到 executing 旧态覆盖 failed/completed 结果; 历史回放即时拉不变;
//   effect 依赖补 _hasFinal/serverTaskId — 小欧-2026-09-09
// 编辑历史: 2026-09-15 小欧 - 北京老陈定案([33]第七章): 左侧回复区只用 final.step.response 渲染——
//   ①props: onSettledRefresh → updateTaskResponse(历史任务拉 steps 后写 final.response 到左侧任务列表)
//   ②删除 B16 DB 刷新覆盖 effect(hasFinalStats→onSettledRefresh refreshTasks 从 chat_tasks.response 拉 chunk 累积内容违反铁令)
//   ③主 REST effect 三处(主来源/等长校验回退/C3降级)加载 steps 后取 type=final 的 response 写左侧
//   ④task.response(chat_tasks.response) 不再作为左侧显示来源 — 小欧-2026-09-15
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-B1: 主REST effect的detail有意不入依赖数组(setDetail后自激循环REST, 见:266注释),
//   eslint-disable移至依赖数组行上方使生效+写明理由 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 北京老陈 - 任务1/任务2 UI冻结根治: isCurrentLive 增 hasBusinessSteps 铁证兜底——
//   liveSteps 含任一业务步骤(thought/action/observation/chunk)即证执行中, 不受 receiving/badge 时序竞态影响,
//   根治 HITL暂停/工具执行空窗/SSE断连重连 三类窗口下 isCurrentLive 翻 false 致 displaySteps 切历史空态、
//   action/observation 静默压栈、恢复后整批回放 ——与 useTaskInfo badge fix(2026-09-08) 双保险 — 北京老陈-2026-09-09
// 编辑历史: 2026-09-10 小欧 - S13 live→终态单一真源平滑交接(根治Q13丢尾):
//   S13.1 新增 settledSteps/settledRef + useEffect(final到达时快照executionStepsRef全量);
//   S13.2 displaySteps 非live时优先用 settledSteps(兜底), REST成功且更长时再替换;
//   S13.3 去掉300ms猜测缓冲(settleTimer), 立即拉REST;
//   S13.4 REST结果与settledSteps等长校验(短则弃,保留settledSteps兜底);
//   新增 executionStepsRef prop(从useChatPanels透传) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段三S13门禁实施落地(v2.17): S13.1条件原为 `_hasFinal && isCurrentLive`, 但
//   isCurrentLive 定义自身含 !_hasFinal, 两者恒互斥→快照effect永不触发, settledRef恒空,S13防丢尾整体失效;
//   改 _hasFinal 驱动, 不加 settledRef 长度守卫(多任务切换时 settledRef 残留旧值, 守卫会阻止新任务快照覆盖
//   旧值, 引入任务切换残留), final 到达即固化 executionStepsRef 全量(幂等, 多次同值不触发重渲染)。
//   【纠正上条误记 2026-09-10 小欧】: 原版本误写"+settledRef.length守卫", 三堂会审裁定不放守卫, 以代码为准 — 小欧-2026-09-10
// 编辑历史: 2026-09-11 小欧 - 契约化(method2, 北京老陈 2026-09-11 定案): thought=仅历史回显事件(DB
//   executionSteps), 实时 SSE 永不发(后端 _SSE_EXCLUDE_TYPES 过滤)。hasBusinessSteps 判定剔除 thought
//   (thought-start/action/observation/chunk 仍实时兜住 isCurrentLive 铁证, 语义不变) — 小欧-2026-09-11
// 编辑历史: 2026-09-11 小欧 - 第七章 M1/M2/M3a: hasFinalStats 派生(DB落库信号统一) + effect1 显式守卫 +
//   B16 删 prevReceivingRef 死码 + import TitleBlock + statsExpanded 折叠状态提升 + finalStep 派生 + 渲染块拆分 — 小欧-2026-09-11
// 编辑历史: 2026-09-11 小欧 - 三堂会审修复: P1-4 props复用TokenLayer(与StaticStatsBlock必选/可选形状对齐, TS2322归零, DRY), import TokenLayer — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - P1-9三堂会审修复: _businessTypes 组件体每次渲染重建 Set 提升模块级常量 BUSINESS_TYPES(性能+DRY) — 小欧-2026-09-12
// 编辑历史: 2026-09-13 小欧 - 新建会话右栏残留根治(北京老陈三思三省定位): REST历史effect的 !activeTaskId 早退分支补清
//   settledSteps/settledRef/historySteps——原早退仅setDetail(null), 会话切换首帧旧activeTaskId跨会话拉旧任务步骤回填后,
//   activeTaskId归空时不清steps→右栏永久残留; 补清保证"无活动任务必空态", 与useTaskSelection渲染期复位双钳制 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - DRY收敛(北京老陈质疑"多余改动"驱动三轮会审): 两处三行清零(settledSteps/settledRef/historySteps)
//   抽 resetSettledAndHistory 唯一入口, sessionId切换effect与REST早退共用; 函数职责=RightViewer展示态清理, 与useSSE.clearSteps正交 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 北京老陈复测: 切会话折叠区(统计区)复位为折叠——新会话默认折叠, 防展开旧统计残留; statsExpanded声明上移供effect复位 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 回归修复(北京老陈实证: 实时任务完成后点击左侧旧任务, 右侧不切换仍显实时任务step, 刷新后正常):
//   settledSteps/settledRef 是"当前任务"终态快照, 同会话内切换历史任务(activeTaskId!==serverTaskId)时残留且恒非空,
//   ①displaySteps三选一原 settledSteps.length>0 永远优先于 historySteps→右侧显示旧任务快照不切换;
//   ②REST等长校验用 settledRef 残留当基准, 旧任务步骤更少时误判丢尾→用快照覆盖historySteps二次污染;
//   修: 两处均加 activeTaskId===serverTaskId 守卫, 快照仅庇当前任务回放, 历史任务切换一律走historySteps;
//   与"刷新后正常"(重挂载置空)语义一致, S13快照机制语义不改 — 小欧-2026-09-13
// 编辑历史: 2026-09-13 小欧 - 三思三省真根治(北京老陈否决守卫治标方案, 责令重写): 守卫只改了选择源, 数据未绑定任务——
//   切旧任务当帧 historySteps 仍是上一任务REST结果会闪现旧内容; 根治=展示态(detail/settledSteps/historySteps)
//   生命周期绑定 activeTaskId: ①渲染期复位(prevActiveTaskIdRef 哨兵, 与 useTaskSelection 同范式)切走即清,
//   切换帧即空无残留无闪现; ②快照 effect 加 activeTaskId===serverTaskId 条件+deps 补 activeTaskId/serverTaskId,
//   切回当前final任务时用 executionStepsRef 重新固化(切回即回), 非当前任务永不固化; ③两处守卫纯冗余删除
//   (渲染期复位已保证 settledRef 非空即当前任务语境); ④废弃为测而抽的 pickDisplaySteps 纯函数与自测case,
//   改组件级真场景回归(切任务后 must 显示新任务数据非残留快照) — 小欧-2026-09-13
// 编辑历史: 2026-09-15 小欧 - 三思三省根治"实时任务完成后点历史任务右侧仍显实时step"反复复发(北京老陈驱动):
//   根因复盘=第二次修复(d4af1d99c)删掉了第一次修复(fe88d378d)的pickDisplaySteps的currentTaskMatch守卫,
//   displaySteps三选一settledSteps.length>0无条件优先→同会话切历史任务时settledSteps(A快照)残留且恒非空,
//   右侧永远显示A的step; 渲染期复位setState在当前帧未生效→settledSteps仍是旧值→守卫是计算层面唯一可靠防线;
//   恢复activeTaskId===serverTaskId守卫(displaySteps+REST等长校验两处), 保留渲染期复位防historySteps闪现;
//   用户锁(userLockRef)经实测与本bug无关(activeTaskId未被effect①抢走)已全部撤销 — 小欧-2026-09-15
// 编辑历史: 2026-09-14 小欧 [36]删 receiving(方案A, 北京老陈批准): ①props接口/解构删 receiving ②useTaskInfo 调用
//   改四参签名 ③isCurrentLive 判定提纯复用 computeIsCurrentLive(改动点③, 删 receiving 条件)
//   ④DBG-1 日志去 recv 槽位(5.5.3-(二) 只留 live/match/final/biz 前缀四字段) ⑤import viewState — 小欧-2026-09-14
// 编辑历史: 2026-09-17 小欧 - 统一拒绝事件 type="rejected": RightViewerProps deniedEntries 类型新增 reject_type 字段 - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 - [46]第五章实施: 新增 waitClock prop(类型导入 ClockSignals/接口声明/解构/透传 PipelineRenderer) - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 会审V3修复(复核三遍): Prettier 格式对齐——deniedEntries 内联类型超长行展开为多行(项目 prettier 排版规范, 纯格式零逻辑) — 小欧-2026-09-17
/**
 * RightViewer - 右侧查看区（right slot，当前锚定任务流水线 + 静态统计块）
 *
 * 【小欧 2026-08-26 8.5 / 修正】
 * - B4：执行中的当前任务(isCurrentLive)禁拉 REST，纯走 liveSteps 回放同一 PipelineRenderer；
 * - B9：渲染入口 splitSteps().business 分流（meta 不进查看区，7.10）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Spin, Empty, Typography } from 'antd';
import type { ExecutionStep } from '../../../../types/execution';
import { Colors, type TokenLayer } from '@/utils/stepStyles'; // 2026-09-11 小欧 三堂会审P1-4: 复用公用 TokenLayer 消重复定义 — 小欧-2026-09-11
import { sessionApi } from '../../../../services/api/session.api';
import {
  executionApi,
  type TaskDetail,
} from '../../../../services/api/task.api';
import { PipelineRenderer } from '../pipeline';
import { splitSteps } from '../pipeline/stepFilter';
import { StaticStatsBlock } from './StaticStatsBlock';
import { TitleBlock } from './TitleBlock'; // 2026-09-11 小欧 第七章 M3a(TitleBlock拆分): title 段独立组件 — 小欧-2026-09-11
import { useTaskInfo } from '../../hooks/useTaskInfo'; // 2026-09-02 小欧: badge 权威派生(running/paused=任务进行), 撑 waiting 三处丢失窗口
import { computeIsCurrentLive } from '@/utils/viewState'; // 2026-09-14 小欧 [36]改动点③(方案A): isCurrentLive 判定提纯复用 — 小欧-2026-09-14
import type { TaskMetaFrames, ClockSignals } from '@/types/sse'; // 2026-09-17 小欧 [46]第五章: 钟面信号类型 — 小欧-2026-09-17
import { emptyMetaFrames } from '@/types/sse';

// 2026-09-12 小欧 P1-9: 业务步骤类型集合提升模块级, 消组件体每次渲染重建 Set(性能+DRY) — 小欧-2026-09-12
const BUSINESS_TYPES = new Set<ExecutionStep['type']>([
  'action',
  'observation',
  'chunk',
]);

// 2026-08-27 小欧 三堂会审: 收窄 unknown[]→ExecutionStep[], 形状不符回落空数组
const toExecutionSteps = (raw: unknown): ExecutionStep[] => {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (s): s is ExecutionStep =>
      typeof s === 'object' && s !== null && 'type' in s
  );
};

interface RightViewerProps {
  activeTaskId: string | null;
  sessionId: string | null;
  serverTaskId: string | null;
  liveSteps: ExecutionStep[];
  executionStepsRef?: React.MutableRefObject<ExecutionStep[]>; // 小欧 2026-09-10 S13: 同步 ref，final 到达时快照用
  highlightToolName: string | null;
  frames: TaskMetaFrames; // 2026-09-02 小欧: useTaskInfo badge 派生输入(startInfo 判定 running)
  deniedSteps: ReadonlyMap<number, number>; // 2026-09-06 小欧 B2(方案C): 拒绝/拦截/超时执行轮聚合(step→denied计数), 透传 PipelineRenderer 停齿轮 — 小欧-2026-09-06
  deniedEntries: ReadonlyMap<
    number,
    Array<{ tool: string; reason: string; reject_type?: string }>
  >; // 2026-09-06 小欧 B2(6.4): 被拒工具点名条(step→[{tool,reason}]), 透传 ToolCallLine 灰字 — 小欧-2026-09-06
  waitClock?: ClockSignals; // 2026-09-17 小欧 [46]第五章: 钟面信号, 透传 PipelineRenderer — 小欧-2026-09-17
  // 2026-09-11 小欧 三堂会审P1-4: 复用公用 TokenLayer——原 {prompt_tokens?: number;...} | null 与 StaticStatsBlock 必选字段形状不匹配(TS2322), 统一后 DRY — 小欧-2026-09-11
  sessionTokens?: TokenLayer;
  chainTokens?: TokenLayer;
  // 2026-09-15 小欧 [33]第七章(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
  //   历史任务加载 steps 后写 final.response 到左侧任务列表(实时任务由 ChatPage R3 effect 写) — 小欧-2026-09-15
  updateTaskResponse?: (taskId: string, response: string) => void;
}

const RightViewer: React.FC<RightViewerProps> = ({
  activeTaskId,
  sessionId,
  serverTaskId,
  liveSteps,
  executionStepsRef, // 小欧 2026-09-10 S13: 同步 ref
  highlightToolName,
  frames,
  deniedSteps,
  deniedEntries, // 2026-09-06 小欧 B2(6.4)
  waitClock, // 2026-09-17 小欧 [46]第五章: 钟面信号
  sessionTokens, // 2026-09-11 小欧 三堂会审P1-4: 复用 TokenLayer(类型统一) — 小欧-2026-09-11
  chainTokens,
  updateTaskResponse, // 2026-09-15 小欧 [33]第七章: 历史任务 final.response 写入左侧唯一入口 — 小欧-2026-09-15
}) => {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [historySteps, setHistorySteps] = useState<ExecutionStep[]>([]);
  const [loading, setLoading] = useState(false);
  const prevIsCurrentLiveRef = useRef(false); // [DEBUG-1] 2026-09-09 北京老陈
  // 小欧 2026-09-10 S13: live→终态快照 — final 到达时固化 executionStepsRef 全量
  const [settledSteps, setSettledSteps] = useState<ExecutionStep[]>([]);
  const settledRef = useRef<ExecutionStep[]>([]);
  // 小欧 2026-09-11 第七章 M3a(TitleBlock拆分): 统计区折叠状态提升到父级——TitleBlock(title 段)持折叠箭头,
  //   StaticStatsBlock(折叠区)受控显隐, 两次独立渲染事件互不干扰 — 小欧-2026-09-11
  // 2026-09-13 小欧 北京老陈 新建会话右栏彻底清态: statsExpanded 声明上移, 供切会话effect复位折叠 — 小欧-2026-09-13
  const [statsExpanded, setStatsExpanded] = useState(false);

  // 2026-09-13 小欧 DRY收敛(三轮会审): 终态快照/历史步骤清理唯一入口——sessionId切换effect与REST早退共用,
  //   消除两处三行重复清零; 与useSSE.clearSteps/serverTaskId语义正交, 仅管RightViewer内部展示态 — 小欧-2026-09-13
  const resetSettledAndHistory = useCallback(() => {
    setSettledSteps([]);
    settledRef.current = [];
    setHistorySteps([]);
  }, []);

  // 2026-09-13 小欧 三思三省真根治(北京老陈否决守卫治标方案): 右栏展示态(detail/settledSteps/historySteps)
  //   必须与所属任务绑定——activeTaskId 切换时渲染期同步复位(prevActiveTaskIdRef 哨兵, 与 useTaskSelection 同范式):
  //   否则同会话内点旧任务时 settledSteps/historySteps 仍是上一个任务的数据, 渲染层无论怎么选源都会闪现旧内容;
  //   渲染期复位保证切换帧即空, 新任务数据由REST(historySteps)按需填充, 无任何跨任务残留 — 小欧-2026-09-13
  const prevActiveTaskIdRef = useRef(activeTaskId);
  if (prevActiveTaskIdRef.current !== activeTaskId) {
    prevActiveTaskIdRef.current = activeTaskId;
    setDetail(null);
    resetSettledAndHistory();
  }

  // 2026-09-13 小欧 北京老陈 新建会话右侧残留修复: 会话切换时清零settledSteps/historySteps,
  //   防旧会话的终态快照/历史拉取残留导致displaySteps渲染旧步骤 — 小欧-2026-09-13
  // 2026-09-13 小欧 北京老陈 复测: 折叠区(统计区)随切会话复位为折叠(新会话默认折叠, 防展开旧统计残留) — 小欧-2026-09-13
  useEffect(() => {
    resetSettledAndHistory();
    setStatsExpanded(false);
  }, [sessionId, resetSettledAndHistory]);

  // 2026-09-02 小欧: badge 权威派生——live 任务才取, 非live历史回放不传(不显示等待圈)
  // 2026-09-14 小欧 [36]改动点①(方案A, 北京老陈批准): 签名删 receiving, 断连窗由 startinfo 门承接 — 小欧-2026-09-14
  const { badge: liveBadge } = useTaskInfo(
    liveSteps,
    frames ?? emptyMetaFrames()
  );
  // 2026-09-03 小欧 12.6修复: 若liveSteps已含final终态, 不再判live(及时切历史拉取), 防final丢失前永久卡live
  const _hasFinal = liveSteps.some((s) => s.type === 'final');
  // 2026-09-03 小沈 BUG-01/04修复修正: hasLiveSteps仅0→1变化时触发effect重跑(首帧pipelineEndRef挂载), 后续chunk增长由ResizeObserver驱动不重挂载
  const hasLiveSteps = liveSteps.length > 0;
  // 2026-09-06 小欧 RG-2: 历史数据是否已就绪(0→1驱动主滚动effect重跑, 后台final切历史后滚底兜底) — 小欧-2026-09-06
  const hasHistorySteps = historySteps.length > 0;
  // 小欧 2026-09-11 第七章 M1/M2(DB落库信号): hasFinalStats = frames.finalStats 非空 = final_stats 到达 =
  //   DB 已落库信号(t3', v1.9 方案 A)——折叠区 DB 读(effect1)与任务列表刷新(B16)以此统一信号读 DB — 小欧-2026-09-11
  const hasFinalStats = !!frames?.finalStats;
  // 2026-09-09 北京老陈 铁证兜底: liveSteps含任一业务步骤即证执行中(不可翻false)
  // 2026-09-11 小欧 契约化(method2): thought=仅历史回显(实时再也不来), 信号移出 thought
  //   (action/observation/chunk 已足够; thought-start 由 pipeline 消费) — 小欧-2026-09-11
  // 2026-09-12 小欧 P1-9: 提升模块级 BUSINESS_TYPES — 小欧-2026-09-12
  const hasBusinessSteps = liveSteps.some((s) => BUSINESS_TYPES.has(s.type));
  // 2026-09-14 小欧 [36]改动点③(方案A, 北京老陈批准): isCurrentLive 判定提纯为 computeIsCurrentLive
  //   纯函数(借力 startinfo 门无条件 running/业务 steps), 删 receiving 条件 — 小欧-2026-09-14
  const isCurrentLive = computeIsCurrentLive({
    activeTaskId,
    serverTaskId,
    hasFinal: _hasFinal,
    hasBusinessSteps,
    liveBadge,
  });
  // [DEBUG-1] 2026-09-09 北京老陈 冻结诊断：isCurrentLive 仅状态变化时打
  // 2026-09-14 小欧 [36]5.5.3-(二): DBG-1 日志去 recv 槽位(接收变量已删, 只留 live/match/final/biz 前缀四字段) — 小欧-2026-09-14
  if (isCurrentLive !== prevIsCurrentLiveRef.current) {
    prevIsCurrentLiveRef.current = isCurrentLive;
  }

  // 小欧 2026-09-10 S13.1: final 到达瞬时快照——用 ref（同步）而非 state（异步）
  // v2.17 修复(小欧 2026-09-10)：原条件 `_hasFinal && isCurrentLive` 恒假（isCurrentLive 定义含 !_hasFinal），
  //   快照 effect 永不触发，settledRef/settledSteps 恒空，S13 防丢尾整体失效——改 _hasFinal 驱动，
  //   不加 settledRef 守卫（多任务切换时 settledRef 会残留旧值，守卫会阻止新任务快照覆盖），
  //   final 到达即固化 executionStepsRef 全量（幂等，多次执行值相同，React 不重渲染）
  // 2026-09-13 小欧 三思三省根治(北京老陈否决守卫治标方案): 快照生命周期跟随"当前任务"——
  //   ①快照仅当 activeTaskId===serverTaskId 且 final 已到时固化(防A任务final后切B, effect因activeTaskId变重跑
  //   把A快照重新灌回B); ②deps补 activeTaskId/serverTaskId——切回当前final任务时(渲染期复位刚清空)立即用
  //   executionStepsRef 重新固化, 保证"切走即清、切回即回", RIGHT侧永无跨任务残留 — 小欧-2026-09-13
  useEffect(() => {
    if (_hasFinal && activeTaskId === serverTaskId) {
      const snapshot =
        executionStepsRef && executionStepsRef.current.length > 0
          ? [...executionStepsRef.current]
          : [...liveSteps];
      settledRef.current = snapshot;
      setSettledSteps(snapshot);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 不依赖 liveSteps（ref 已同步更新） — 小欧 2026-09-10
  }, [_hasFinal, isCurrentLive, activeTaskId, serverTaskId]);

  // 2026-09-02 小欧 三堂会审定稿: 滚动开关改"用户是否主动上翻>120px"事件驱动(语义同useChatScroll.ts:57-61),
  //   弃 isNearBottom 瞬态判定(首屏scrollTop=0内容超一屏即false永不滚) 与 双RAF/force(HIT确认暴力滚)
  // 2026-09-02 小欧 task005会审P3(北京老陈定案): 弃 closest('[style*="overflow"]') 字符串选择器(仅匹配内联样式, 改CSS类即静默失效),
  //   改 getComputedStyle 沿祖先上溯找 overflowY:auto/scroll 滚动容器; 行为语义等价, 更稳健 — 小欧 2026-09-02
  const pipelineEndRef = useRef<HTMLDivElement>(null);
  // 用户在滚动中距底>120px视为主动上翻; 上翻后自动滚失效, 滚回底部自动恢复; 首屏从未滚动→false→内容增长即滚底
  const userScrolledUpRef = useRef(false);
  // 2026-09-02 小欧: 程序滚动标志，防止stickToBottom设置scrollTop触发scroll事件被误判为用户上翻
  const isProgramScrollingRef = useRef(false);
  // 2026-09-03 小欧 BUG-01/BUG-04修复: findScrollContainer仅遍历DOM找overflow容器, 不依赖liveSteps, 改[]防每chunk重挂载
  const findScrollContainer = useCallback(() => {
    let el: HTMLElement | null = pipelineEndRef.current;
    while (el) {
      const style = window.getComputedStyle(el);
      if (
        style.overflowY === 'auto' ||
        style.overflowY === 'scroll' ||
        style.overflow === 'auto' ||
        style.overflow === 'scroll'
      ) {
        return el as unknown as HTMLDivElement;
      }
      el = el.parentElement;
    }
    return null;
  }, []);
  // 2026-09-06 小欧 RG-1/RG-2: 抽统一滚底(scrollToBottomNow)——主effect(RO/首帧/切历史)与visibilitychange兜底共用, DRY — 小欧-2026-09-06
  const scrollToBottomNow = useCallback(() => {
    if (userScrolledUpRef.current) return;
    const container = findScrollContainer();
    if (!container) return;
    isProgramScrollingRef.current = true;
    container.scrollTop = container.scrollHeight;
    // microtask重置标志，让下一个scroll事件正常判断
    Promise.resolve().then(() => {
      isProgramScrollingRef.current = false;
    });
  }, [findScrollContainer]);
  useEffect(() => {
    // RG-2: 守卫放宽——live 或 历史数据已就绪(后台任务final切历史后滚动兜底, 防右栏停半空) — 小欧-2026-09-06
    if (!isCurrentLive && !hasHistorySteps) return;
    const container = findScrollContainer();
    const pipeline = pipelineEndRef.current;
    if (!container || !pipeline) return;
    const threshold = 120;
    // 2026-09-02 小欧: scroll 事件维护上翻标志(仅用户真实滚动触发; 程序设置scrollTop时跳过判断)
    const handleScroll = () => {
      if (isProgramScrollingRef.current) return; // 程序滚动跳过
      userScrolledUpRef.current =
        container.scrollHeight - container.scrollTop - container.clientHeight >
        threshold;
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    // 内容高度变化驱动(覆盖新增step与打字机段逐字增长) + 首帧立即滚底(历史数据到达亦立即滚底)
    const ro = new ResizeObserver(scrollToBottomNow);
    ro.observe(pipeline);
    scrollToBottomNow(); // 首帧/新内容到达: 用户未上翻即滚动到底 — 小欧 2026-09-02/09-06
    return () => {
      ro.disconnect();
      container.removeEventListener('scroll', handleScroll);
    };
  }, [
    isCurrentLive,
    hasLiveSteps,
    hasHistorySteps,
    findScrollContainer,
    scrollToBottomNow,
  ]);
  // RG-1: 浏览器后台节流后切回可见——visibilitychange 兜底重滚(左栏 useChatScroll.ts:93-103 已有, 右栏补对称) — 小欧-2026-09-06
  useEffect(() => {
    if (!isCurrentLive && !hasHistorySteps) return;
    const handleVisibility = () => {
      if (!document.hidden) scrollToBottomNow();
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [isCurrentLive, hasHistorySteps, scrollToBottomNow]);

  // 拉取历史任务：C1+C2 并行；C2 空则 C3 按 message 降级（静态块降级为空，契约无通道）
  useEffect(() => {
    if (!activeTaskId || isCurrentLive) {
      // 2026-08-27 小欧 修复#45: 切到实时任务时清空历史detail, 避免StaticStatsBlock残留旧任务统计
      setDetail(null);
      // 2026-09-13 小欧 根治(北京老陈三思三省定位): 活跃任务为空时同步清终态快照/历史步骤——会话切换首帧
      //   旧activeTaskId跨会话拉旧任务REST回填historySteps后, activeTaskId归空早退仅清detail不清steps,
      //   右栏永久残留旧执行记录; 补清后"无活动任务必空态", 不依赖effect执行时序 — 小欧-2026-09-13
      if (!activeTaskId) {
        resetSettledAndHistory();
      }
      return; // B4：执行中不拉 REST
    }
    // 小欧 2026-09-11 第七章 M1(DB落库信号): 当前任务 final 已到但 final_stats(DB 就绪信号 t3')未到——
    //   此刻 update_task(任务级)尚未落库(final 先发后落, t0≪t3), 读必 stale executing/旧时长, 绝不读 DB;
    //   isCurrentLive 含 !_hasFinal, final 一到即翻 false 会强制本 effect 重跑——仅换依赖数组治不了本,
    //   须显式守卫挡住此路径; 历史任务选择(activeTaskId!==serverTaskId)DB 已稳定, 不受守卫
    if (activeTaskId === serverTaskId && !hasFinalStats) {
      setDetail(null);
      return;
    }
    let cancelled = false;

    const startFetch = () => {
      if (!detail && !isCurrentLive) setLoading(true); // 小欧 2026-08-30: 加!isCurrentLive守卫, live模式不触发spinner
      (async () => {
        try {
          const [d, s] = await Promise.all([
            executionApi.getTaskDetail(activeTaskId),
            executionApi.getTaskSteps(activeTaskId),
          ]);
          if (cancelled) return;
          setDetail(d);
          // 小欧 2026-09-15 [33]第七章(北京老陈定案): 左侧回复区只用 final.step.response 渲染——
          //   历史任务须从 chat_task_steps.step_json 的 type=final step 取 response 写左侧;
          //   严禁用 task.response(chat_tasks.response=chunk累积) 显示; 无 final.response 则留空 — 小欧-2026-09-15
          const writeFinalResponse = (stepsArray: unknown[]) => {
            const fs = toExecutionSteps(stepsArray).find(
              (s) => s.type === 'final'
            );
            const resp = fs?.response;
            if (resp && !cancelled) {
              updateTaskResponse?.(activeTaskId, resp);
            }
          };
          // 小欧 2026-09-10 S13.4: REST 结果与 settledSteps 等长校验——短则弃，保留 settledSteps 兜底
          // 2026-09-15 小欧 三思三省根治: 加回 activeTaskId===serverTaskId 守卫——防跨任务时 settledRef 残留旧快照,
          //   误判"丢尾"用旧快照覆盖新 historySteps, 与 displaySteps 守卫互补 — 小欧-2026-09-15
          if (
            activeTaskId === serverTaskId &&
            s.steps.length > 0 &&
            settledRef.current.length > 0 &&
            s.steps.length < settledRef.current.length
          ) {
            console.warn(
              `[RV] REST 步骤数(${s.steps.length}) < settledSteps(${settledRef.current.length})，弃用 REST`
            );
            setHistorySteps(toExecutionSteps(settledRef.current));
            writeFinalResponse(settledRef.current);
            return;
          }
          if (s.steps.length > 0) {
            // 2026-08-27 小欧 修复#46: 拒绝裸断言, steps 缺失时回落空数组, 避免下游读step字段得undefined
            setHistorySteps(toExecutionSteps(s.steps)); // 2026-08-27 小欧 三堂会审: 收窄unknown[]→ExecutionStep[]
            writeFinalResponse(s.steps);
          } else if (sessionId) {
            const msgResp = await sessionApi.getSessionMessages(sessionId);
            if (cancelled) return;
            const fallback: ExecutionStep[] = [];
            for (const m of msgResp.messages) {
              for (const st of m.execution_steps ?? [])
                fallback.push(st as ExecutionStep);
            }
            setHistorySteps(toExecutionSteps(fallback));
            writeFinalResponse(fallback);
          } else {
            setHistorySteps([]);
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
    };
    // 小欧 2026-09-10 S13.3: 立即拉 REST，结果与 settledSteps 等长校验（替代 300ms 猜测缓冲）
    startFetch();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- detail有意不入deps: setDetail后重Run会自激循环REST(loading窗口见#45修复) — 小欧-2026-09-09
  }, [activeTaskId, sessionId, isCurrentLive, hasFinalStats, serverTaskId]);

  // 小欧 2026-09-15 [33]第七章(北京老陈定案): 删除原 B16 hasFinalStats→onSettledRefresh(refreshTasks)
  //   effect——其从 DB 拉 chat_tasks.response(chunk累积) 覆盖左侧, 违反"左侧只用 final.step.response"铁命令 — 小欧-2026-09-15

  // 小欧 2026-09-10 S13.2: 结束瞬时先用 live 快照兜底，REST 成功且更长时再替换
  // 2026-09-15 小欧 三思三省根治: activeTaskId===serverTaskId 守卫——settledSteps 仅当前任务回放时优先,
  //   防同会话切历史任务时 settledSteps(A快照)残留且恒非空致右侧永远显示A的step; 渲染期复位清 historySteps
  //   防闪现, 两者互补不可缺一 — 小欧-2026-09-15
  const displaySteps = isCurrentLive
    ? liveSteps
    : activeTaskId === serverTaskId && settledSteps.length > 0
      ? settledSteps
      : historySteps;
  // 小欧 2026-09-11 第七章 M3a(title段数据源=final帧): title 段数据源=final 帧——实时=settledSteps 快照(final 已入 ref 快照),
  //   历史回放=historySteps 的 final step; final 到达即可渲染, 绝不读DB — 小欧-2026-09-11
  const finalStep = displaySteps.find((s) => s.type === 'final');
  const hasSteps = displaySteps.length > 0;
  // [DEBUG-2] 2026-09-09 北京老陈 displaySteps 切换侦测
  const _prevSrcRef = useRef<string>('live');
  const _src = isCurrentLive ? 'live' : 'hist';
  if (_src !== _prevSrcRef.current) {
    _prevSrcRef.current = _src;
  }

  return (
    <Spin spinning={loading && !isCurrentLive}>
      {!isCurrentLive && !loading && !hasSteps ? (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, color: Colors.TEXT.SECONDARY }}
            >
              暂无执行记录
            </Typography.Text>
          }
          style={{ padding: '24px 0' }}
        />
      ) : (
        // 编辑历史: 2026-09-14 小欧 - 容器加 right-viewer-body 类名: E2E唯一正文定位锚点(getFinalText整页innerText在多任务/切历史下尾串脆弱), 零UI影响 - 小欧-2026-09-14
        <div ref={pipelineEndRef} className="right-viewer-body">
          <PipelineRenderer
            steps={splitSteps(displaySteps).business}
            streaming={isCurrentLive}
            highlightToolName={highlightToolName}
            badge={isCurrentLive ? liveBadge : undefined} // 2026-09-02 小欧: live才传badge, 历史回放不显示等待圈
            deniedSteps={deniedSteps} // 2026-09-06 小欧 B2(方案C): 停齿轮判定 — 小欧-2026-09-06
            deniedEntries={deniedEntries} // 2026-09-06 小欧 B2(6.4): 被拒工具点名条 — 小欧-2026-09-06
            waitClock={waitClock} // 2026-09-17 小欧 [46]第五章: 钟面信号 — 小欧-2026-09-17
          />
        </div>
      )}
      {!isCurrentLive && (
        // 小欧 2026-09-11 第七章 M3a(统计区分段渲染): 统计区拆两段两次独立渲染——TitleBlock(title 段,
        //   final 帧驱动, 绝不读 DB)为每次渲染第二段; StaticStatsBlock(折叠区, final_stats 到达后
        //   effect1 已读 DB, finalStats 帧复合兜底)为第三次渲染, 各自独立互不影响 — 小欧-2026-09-11
        <>
          <TitleBlock
            finalStep={finalStep}
            expanded={statsExpanded}
            onToggle={() => setStatsExpanded((v) => !v)}
          />
          {statsExpanded && (
            <StaticStatsBlock
              detail={detail}
              chainSteps={historySteps}
              finalStats={frames.finalStats}
              sessionTokens={sessionTokens}
              chainTokens={chainTokens}
            />
          )}
        </>
      )}
    </Spin>
  );
};

export { RightViewer };
