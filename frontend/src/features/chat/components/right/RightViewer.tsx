// 编辑历史: 2026-08-26 小欧 - 8.5 实施: 右侧查看区, 当前任务禁REST走liveSteps, 业务步骤分流(7.10/R1-B4/B9)
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
/**
 * RightViewer - 右侧查看区（right slot，当前锚定任务流水线 + 静态统计块）
 *
 * 【小欧 2026-08-26 8.5 / R1 修正】
 * - B4：执行中的当前任务(isCurrentLive)禁拉 REST，纯走 liveSteps 回放同一 PipelineRenderer；
 * - B9：渲染入口 splitSteps().business 分流（meta 不进查看区，7.10）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Spin, Empty, Typography } from 'antd';
import type { ExecutionStep } from '../../../../types/execution';
import { Colors } from '@/utils/stepStyles';
import { sessionApi } from '../../../../services/api/session.api';
import {
  executionApi,
  type TaskDetail,
} from '../../../../services/api/task.api';
import { PipelineRenderer } from '../pipeline';
import { splitSteps } from '../pipeline/stepFilter';
import { StaticStatsBlock } from './StaticStatsBlock';
import { useTaskInfo } from '../../hooks/useTaskInfo'; // 2026-09-02 小欧: badge 权威派生(running/paused=任务进行), 撑 waiting 三处丢失窗口
import type { TaskMetaFrames } from '@/types/sse';
import { emptyMetaFrames } from '@/types/sse';

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
  receiving: boolean;
  liveSteps: ExecutionStep[];
  highlightToolName: string | null;
  frames: TaskMetaFrames; // 2026-09-02 小欧: useTaskInfo badge 派生输入(startInfo 判定 running)
  onSettledRefresh?: () => void; // 结束沿通知外层刷新任务列表
}

const RightViewer: React.FC<RightViewerProps> = ({
  activeTaskId,
  sessionId,
  serverTaskId,
  receiving,
  liveSteps,
  highlightToolName,
  frames,
  onSettledRefresh,
}) => {
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [historySteps, setHistorySteps] = useState<ExecutionStep[]>([]);
  const [loading, setLoading] = useState(false);
  const prevReceivingRef = useRef(false);

  const isCurrentLive =
    activeTaskId != null && activeTaskId === serverTaskId && receiving;
  // 2026-09-02 小欧: badge 权威派生——live 任务才取, 非live历史回放不传(不显示等待圈)
  const { badge: liveBadge } = useTaskInfo(
    liveSteps,
    frames ?? emptyMetaFrames(),
    receiving
  );

  // 2026-09-02 小欧 三堂会审定稿: 滚动开关改"用户是否主动上翻>120px"事件驱动(语义同useChatScroll.ts:57-61),
  //   弃 isNearBottom 瞬态判定(首屏scrollTop=0内容超一屏即false永不滚) 与 双RAF/force(HIT确认暴力滚)
  // 2026-09-02 小欧 task005会审P3(北京老陈定案): 弃 closest('[style*="overflow"]') 字符串选择器(仅匹配内联样式, 改CSS类即静默失效),
  //   改 getComputedStyle 沿祖先上溯找 overflowY:auto/scroll 滚动容器; 行为语义等价, 更稳健 — 小欧 2026-09-02
  const pipelineEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  // 用户在滚动中距底>120px视为主动上翻; 上翻后自动滚失效, 滚回底部自动恢复; 首屏从未滚动→false→内容增长即滚底
  const userScrolledUpRef = useRef(false);
  const findScrollContainer = useCallback(() => {
    if (scrollContainerRef.current) return scrollContainerRef.current;
    let el: HTMLElement | null = pipelineEndRef.current;
    while (el) {
      const style = window.getComputedStyle(el);
      if (
        style.overflowY === 'auto' ||
        style.overflowY === 'scroll' ||
        style.overflow === 'auto' ||
        style.overflow === 'scroll'
      ) {
        scrollContainerRef.current = el;
        return el;
      }
      el = el.parentElement;
    }
    return null;
  }, []);
  useEffect(() => {
    if (!isCurrentLive || liveSteps.length === 0) return;
    const container = findScrollContainer();
    const pipeline = pipelineEndRef.current;
    if (!container || !pipeline) return;
    const threshold = 120;
    // 2026-09-02 小欧 三堂会审: scroll 事件维护上翻标志(仅用户真实滚动触发; scrollTop 程序赋值滚到底时远距<120→false 不误判)
    const handleScroll = () => {
      userScrolledUpRef.current =
        container.scrollHeight - container.scrollTop - container.clientHeight >
        threshold;
    };
    container.addEventListener('scroll', handleScroll, { passive: true });
    // 内容高度变化驱动(覆盖新增step与打字机段逐字增长) + 首帧立即滚底(弃RAF双帧延迟)
    const stickToBottom = () => {
      if (!userScrolledUpRef.current) {
        container.scrollTop = container.scrollHeight;
      }
    };
    const ro = new ResizeObserver(stickToBottom);
    ro.observe(pipeline);
    stickToBottom(); // 首帧/新内容到达: 用户未上翻即滚动到底 — 小欧 2026-09-02
    return () => {
      ro.disconnect();
      container.removeEventListener('scroll', handleScroll);
    };
  }, [isCurrentLive, liveSteps.length, findScrollContainer]);

  // 拉取历史任务：C1+C2 并行；C2 空则 C3 按 message 降级（静态块降级为空，契约无通道）
  useEffect(() => {
    if (!activeTaskId || isCurrentLive) {
      // 2026-08-27 小欧 修复#45: 切到实时任务时清空历史detail, 避免StaticStatsBlock残留旧任务统计
      setDetail(null);
      return; // B4：执行中不拉 REST
    }
    let cancelled = false;
    if (!detail && !isCurrentLive) setLoading(true); // 小欧 2026-08-30: 加!isCurrentLive守卫, live模式不触发spinner
    (async () => {
      try {
        const [d, s] = await Promise.all([
          executionApi.getTaskDetail(activeTaskId),
          executionApi.getTaskSteps(activeTaskId),
        ]);
        if (cancelled) return;
        setDetail(d);
        if (s.steps.length > 0) {
          // 2026-08-27 小欧 修复#46: 拒绝裸断言, steps 缺失时回落空数组, 避免下游读step字段得undefined
          setHistorySteps(toExecutionSteps(s.steps)); // 2026-08-27 小欧 三堂会审: 收窄unknown[]→ExecutionStep[]
        } else if (sessionId) {
          const msgResp = await sessionApi.getSessionMessages(sessionId);
          if (cancelled) return;
          const fallback: ExecutionStep[] = [];
          for (const m of msgResp.messages) {
            for (const st of m.execution_steps ?? []) fallback.push(st);
          }
          setHistorySteps(fallback);
        } else {
          setHistorySteps([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeTaskId, sessionId, isCurrentLive]);

  // B16：锚定的当前任务结束沿 -> 补取 C1 终态详情并刷新外层列表
  useEffect(() => {
    if (
      prevReceivingRef.current &&
      !receiving &&
      activeTaskId === serverTaskId &&
      activeTaskId
    ) {
      // 2026-08-27 小欧 修复#44: 移除冗余getTaskDetail(上方effect在isCurrentLive变false时已补取), 避免双发REST
      onSettledRefresh?.();
    }
    prevReceivingRef.current = receiving;
  }, [receiving, activeTaskId, serverTaskId, onSettledRefresh]);

  const displaySteps = isCurrentLive ? liveSteps : historySteps;
  const hasSteps = displaySteps.length > 0;

  return (
    <Spin spinning={loading && !isCurrentLive}>
      {!loading && !hasSteps ? (
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
        <div ref={pipelineEndRef}>
          <PipelineRenderer
            steps={splitSteps(displaySteps).business}
            streaming={isCurrentLive}
            highlightToolName={highlightToolName}
            badge={isCurrentLive ? liveBadge : undefined} // 2026-09-02 小欧: live才传badge, 历史回放不显示等待圈
          />
        </div>
      )}
      {!isCurrentLive && (
        <StaticStatsBlock detail={detail} chainSteps={historySteps} />
      )}
    </Spin>
  );
};

export { RightViewer };
