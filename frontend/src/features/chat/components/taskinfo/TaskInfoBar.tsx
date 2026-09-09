// 编辑历史: 2026-08-26 小欧 - 修复A3(接受detail派生历史任务动态信息/7.6+4.5.1)+B2(执行中实时计时/7.6②)+C2(上下文截断文字/7.9)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.4 useRef仅首次锚定start, 去frames.startTimestamp防抖动, 切换复位
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P0-2/边距-P0-2: 去整框留淡底(border→none,background#fafafa,radius6,padding8px); 内层过程区加滚动细线borderTop#f5f5f5+scrollbarWidth; 外层gap2→8主节奏
// 编辑历史: 2026-08-28 小欧 - ①C/c1: 去胶囊改透明+borderTop#f0f0f0, gap12→8, 数值加粗#595959 500, Tag→Text轻量化
// 编辑历史: 2026-08-30 小欧 - 13.14 8处Typography.Text→span+双组token本轮/任务累计(P/C/T后端直发) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 13.14 TrustPanel移至TaskInfoBar第一行尾部集成（第一行尾巴） - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复×不显眼: DeleteOutlined→文本×、色#999→#595959、字号12→14加粗 - 小欧-2026-08-30
// 编辑历史: 2026-09-01 小欧 - TaskInfoBar一线三组最佳重排: 左主节奏(状态/耗时/步轮·重试) 中Token合一T(P/C) 右信任/收起 gap12/8 减半宽 - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 去尾部"收起/展开"文字按钮(北京老陈驱动: 冒泡至整行onClick致setCollapsed两次切换抵消=点了没反应; 且与整行点击重复): 面板折叠仅保留整行点击(:139), 信任独立三角stopPropagation - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 设计文档v1.21§5.7-B落码(工具结果显示与taskinfo显示分析与设计-小欧-2026-09-01.md): Props六参补
//   liveErrorText(位4 error 实时源) + 组件解构同步 + useTaskInfo 五参调用 + 第一行去掉旧"· 重试N"累计(:163-168,
//   来源stats.retry_count, 无内容看不懂——北京老陈质疑)与截断独立段(:174-178, 并入位4) + 位4渲染段(🔁/🛑/⚠
//   图标映射, 置于 步骤/轮次 之后、·疑似卡死 之前; 新覆盖旧无优先级) - 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: TB-02 revokeTrust加try/catch防unhandledrejection上浮 — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 会话信任功能修复 v1.5⑤⑥(北京老陈定案"tool+path才是准确对象", 后端§5.5): TrustedTool带path升级一行一变——
//   trustTools行键改 `${toolName}:${path}`、显示 {toolName} › {path ?? '任意'}(空=工具级通配)、revokeTrust签名带path精确撤销、Tooltip文案改"会话级 tool+path 免审白名单"(目标路径及其子目录免弹框) — 小欧-2026-09-02
// 编辑历史: 2026-09-06 小欧 - R1秒表与徽标解耦(B1实证修复, 见 doc-9月优化/错误弹窗与TaskInfoBar计时器干扰问题-验证分析与解决方案): 秒表interval运行条件去badge依赖改为
//   receiving&&!detail(实时流在就走表, 错误信号不再清零停表/业务恢复不再回跳); shownElapsed实时态一律liveElapsed, 非实时/历史回退elapsedSec;
//   else分支原样保留(归零+startRef复位, 保终态duration显示与新任务归零) — 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 六章6.3.4(北京老陈定案): prop 第7位 liveErrorText✗ string 改 liveError?: LiveError|null
//   (P3数据源对象形态, useChatPanels 透传) + 位4 图标分层——执行级 error 用 CloseCircleFilled(红圆底白×,
//   替原🛑, ·/着色 Colors.ERROR) + 请求级 error 用 ⛔(后端业务错误如"消息列表为空"); retrying🔁/truncated⚠ 不变 — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - [16]v4.1+v4.2: P0-1探针删除/P0-3折叠态机删除(信息带恒定1行)/P1-5图标全antd SVG/P1-6对比度分级/P1-7 Token两段式MetricItem/P1-8上下文4态/P1-9换行/P1-11分隔线归属input/P2-12令牌化/P2-13事件时间轴/P2-15徽标迁infoMaps/P2-16耗时等宽/G6上下文+G8事件双浮层经FloatingEntry复用(G8双写修复) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - [16]v4.4 修复#3: 3.9 断点矩阵落地(useInfoBreakpoint 1280/960/768)——G2/G3 xsmall 合并(G3 含耗时段)、
//   G3 mid/narrow 收窄(仅数字+Tooltip 展开全文本)、G4 narrow/xsmall 省略(maxWidth200+ellipsis+Tooltip 全文)、G5 累计段收窄(明细进 MetricItem Tooltip 轻浮层)、
//   G7 narrow/xsmall 仅计数(TrustPanel compact)、G6/G8 恒完整(FloatingEntry 基础行数字+▸+明细进浮层① 已满足矩阵) — 小欧-2026-09-09
/**
 * TaskInfoBar - 输入框上方任务信息条（taskinfo slot，当前任务动态实时唯一位置）
 *
 * 【小欧 2026-08-26 8.6】7 项信息点（7.6 目标）：①状态徽标(startinfo)②耗时③轮次
 * ④token实时累计(usage)⑤上下文概况(context_overview)⑥过程状态条(start已开始/
 * paused/resumed/retrying)+取消终态⑦truncated提示。可折叠；纯 SSE 收流。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useState, useRef } from 'react';
import { Badge, Tooltip } from 'antd';
import {
  CloseCircleFilled,
  DownOutlined,
  StopOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons'; // 3.4: G4/G8 全 antd SVG (P1-5)
import type { ExecutionStep } from '../../../../types/execution';
import type { TaskMetaFrames, LiveError } from '@/types/sse';
import type { TaskDetail } from '../../../../services/api/task.api';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles'; // P2-12: 硬码数字全令牌化
import { formatTimeHMS } from '@/utils/time'; // 3.6 时间轴 HH:MM:SS
import { useTaskInfo, type LiveMeta } from '../../hooks/useTaskInfo';
import { useInfoBreakpoint } from '../../hooks/useInfoBreakpoint'; // 3.9 断点矩阵(见 v4.4 修复#3)
import { TrustPanel } from '../config/TrustPanel';
import { EllipsisTip } from './EllipsisTip';
import { MetricItem } from './MetricItem';
import { FloatingEntry } from './FloatingEntry'; // v4.2: G6/G8 双浮层入口公共壳(见 6.5.2.4)
import {
  BADGE_MAP,
  CONTEXT_STATE_MAP,
  EVENT_ICON_MAP,
  TABULAR_NUMS,
  formatToken,
  mapStatus,
} from './infoMaps';

// BADGE_MAP 由 6.5.2.1 infoMaps.ts 定义，本文件经 import 使用（6.5.3.2），不再内联定义

interface TaskInfoBarProps {
  steps: ExecutionStep[];
  frames: TaskMetaFrames; // 统计类元信息帧（8.4.14）
  receiving: boolean;
  detail?: TaskDetail | null; // 【A3】选中历史任务时由其详情派生动态信息
  sessionId?: string | null; // 13.14 TrustPanel第一行尾部需会话ID
  liveError?: LiveError | null; // 小欧 2026-09-02+09-08: 位4 error 实时源(LiveError 对象, useChatPanels 透传) — 小欧-2026-09-08
}

const TaskInfoBar: React.FC<TaskInfoBarProps> = ({
  steps,
  frames,
  receiving,
  detail,
  sessionId,
  liveError,
}) => {
  // v4.1: 取消整行折叠(P0-3), collapsed 状态机/localStorage 键已删除
  // 新增: eventsOpen、ctxOpen 各 useState(false)(见 6.5.3.4 / 6.5.3.8), 随组件轻量瞬态, 不持久化
  const [eventsOpen, setEventsOpen] = useState(false);
  const [ctxOpen, setCtxOpen] = useState(false);
  const info = useTaskInfo(steps, frames, receiving, detail, liveError);
  const b = BADGE_MAP[info.badge];
  // 3.9 断点矩阵（v4.4 修复#3）：wide≥1280 / mid 1280~960 / narrow 960~768 / xsmall<768
  const bp = useInfoBreakpoint();
  const isNarrow = bp === 'narrow' || bp === 'xsmall';
  const isXSmall = bp === 'xsmall';
  const isMid = bp === 'mid';
  // 【2026-09-03 小欧 复用TrustPanel】信任查询/刷新/撤销/折叠逻辑已移入 TrustPanel 组件(TaskInfoBar 删除内联重复, DRY)

  // 【小欧 2026-08-26 修复 B2】实时计时：实时流(receiving)期间按 start 时刻走表
  // （2026-09-06 R1: 不再挂靠徽标 running, 错误/失败态下秒表继续走不零不回跳），
  // 历史任务(detail)用后端 duration，不计时。
  const [liveElapsed, setLiveElapsed] = useState(0);
  const startRef = useRef<number | null>(null); // 2026-08-27 小欧 三堂会审: 仅首次锚定start, 防计时抖动
  useEffect(() => {
    if (receiving && !detail) {
      // 2026-09-06 小欧 R1: 去 info.badge==='running' 依赖 — 小欧-2026-09-06
      if (startRef.current == null) {
        startRef.current = frames.startTimestamp || Date.now(); // 2026-08-27 小欧 三堂会审: 首次锚定
      }
      const start = startRef.current;
      const t = setInterval(
        () =>
          setLiveElapsed(Math.max(0, Math.round((Date.now() - start) / 1000))),
        1000
      );
      return () => clearInterval(t);
    }
    setLiveElapsed(0);
    startRef.current = null; // 2026-08-27 小欧 三堂会审: 任务切换复位startRef
    return undefined;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- frames.startTimestamp有意不入deps: R1定时器防每帧重置(去抖动, 变更记录见R1注释) — 小欧-2026-09-09
  }, [receiving, detail]); // 2026-09-06 小欧 R1: deps去info.badge; 其余保持(去frames.startTimestamp防抖动) — 小欧-2026-09-06
  const shownElapsed = detail
    ? info.elapsedSec
    : receiving // 2026-09-06 小欧 R1: 实时态一律走 liveElapsed(错误态继续走表); 非实时回退 elapsedSec(终态 duration) — 小欧-2026-09-06
      ? liveElapsed
      : info.elapsedSec;

  // eventsTimeline(v4.1, v4.2 经 FloatingEntry 注入): 渲染于 G8 卡片 content(6.5.3.4), 无折叠态条件
  const eventsTimeline =
    info.processEvents.length > 0 ? (
      <div
        role="log"
        aria-live="polite" // 3.6: 新事件实时播报
        style={{
          maxHeight: '40vh', // v4.1/P2-17: 浮层卡片内滚, 不撑 TaskInfoBar 高度
          overflowY: 'auto',
          scrollbarWidth: 'thin',
        }}
      >
        {info.processEvents.map((e) => (
          <div
            key={`${e.time}-${e.kind}`} // P2-13: 唯一 key, 弃索引 {i}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: Spacing.MD,
              fontSize: FontSize.SECONDARY,
              lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
            }}
          >
            {/* 左列: 时间 HH:MM:SS + 均长竖线(3.6 定案, 不编码间隔) */}
            <span
              style={{
                fontSize: FontSize.SMALL, // 11px
                color: Colors.TEXT.SECONDARY,
                ...TABULAR_NUMS, // P2-13: 等宽防抖动
                width: 56,
                textAlign: 'right',
                flexShrink: 0,
              }}
            >
              {formatTimeHMS(e.time)}
            </span>
            <span style={{ color: Colors.BORDER.LIGHT }}>│</span>
            {/* 右列: antd SVG 图标 + 文本(P1-5); 图标即 3.6 "● 节点", 不另加 ● 文本符 */}
            <span style={{ color: Colors.TEXT.TERTIARY, minWidth: 0 }}>
              {EVENT_ICON_MAP[e.kind]}
              <span style={{ marginLeft: Spacing.XS }}>{e.text}</span>
            </span>
          </div>
        ))}
      </div>
    ) : null;

  // renderLiveMeta(3.9 重用: wide/mid 完整 + narrow/xsmall 经 EllipsisTip 省略 均同源) — v4.4 修复#3
  const renderLiveMeta = (m: LiveMeta) => (
    <span
      style={{
        fontSize: FontSize.SECONDARY,
        fontWeight: FontWeight.MEDIUM, // P1-6: 加 500
        color:
          m.kind === 'error'
            ? m.requestLevel
              ? Colors.TEXT.SECONDARY // 请求级: StopOutlined 灰
              : Colors.ERROR // 执行级: CloseCircleFilled 红
            : Colors.WARNING, // retrying/truncated: #AD6800 (对比度≥4.5:1)
        marginLeft: Spacing.XS,
      }}
    >
      {m.kind === 'retrying' ? (
        <SyncOutlined spin /> // P1-5: 🔁 → SyncOutlined spin
      ) : m.kind === 'error' ? (
        m.requestLevel ? (
          <StopOutlined /> // P1-5: ⛔ → StopOutlined
        ) : (
          <CloseCircleFilled
            style={{ fontSize: FontSize.SECONDARY, color: Colors.ERROR }}
          />
        )
      ) : (
        <WarningOutlined /> // P1-5: ⚠ → WarningOutlined
      )}{' '}
      {m.text}
    </span>
  );

  // 3.1.3 方案A: 文字样式(PRIMARY + 500)提示可点
  return (
    <div
      style={{
        background: 'transparent',
        border: 'none',
        borderTop: 'none', // P1-11 定案 B: 分隔线归属 input 区上沿(见 6.5.3.9), 本条不带上边框
        padding: `${Spacing.MD}px 0 0`, // P2-12: 8px → Spacing.MD
        display: 'flex',
        flexDirection: 'column',
        gap: Spacing.MD,
        textAlign: 'left',
      }}
    >
      {/* v4.1: 信息带恒定 1 行, 整行折叠态机已删除(P0-3 随删); G1~G6 渲染其中, 无整行点击 */}
      {/* 编辑历史: 2026-09-09 小欧 - [16]v4.4 修复#2: 接线 .taskinfo-bar(G5 可换行, 消死 CSS) — 小欧-2026-09-09 */}
      <div
        className="taskinfo-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.LG,
          cursor: 'default',
          flexWrap: 'wrap',
          userSelect: 'text', // 3.9: 文本可选中, 点击不触发任何折叠
        }}
      >
        <div
          className="taskinfo-token"
          style={{
            display: 'flex',
            alignItems: 'center',
            // 编辑历史: 2026-09-09 小欧 - [16]v4.4 修复#5(P2-12): gap:8 硬码 → Spacing.MD — 小欧-2026-09-09
            gap: Spacing.MD,
            flexShrink: 0,
          }}
        >
          <Badge status={b.status} text={b.text} />
          {/* 3.9 断点矩阵: xsmall(<768) G2 合并进 G3; 其余档 G2 完整独立 */}
          {!isXSmall && (
            <span
              style={{
                fontSize: FontSize.SECONDARY,
                color: Colors.TEXT.PRIMARY,
                fontWeight: FontWeight.BOLD, // 3.1.2: G2 耗时 600
                ...TABULAR_NUMS, // P2-16: 等宽数字, 位数不抖动
              }}
            >
              耗时 {Math.round(shownElapsed)}s
            </span>
          )}
          {/* 3.9 断点矩阵: 完整档(G3 全文本) / mid·narrow 收窄(仅留数字, Tooltip 展开全文本) / xsmall 合并(含耗时) */}
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {isXSmall ? (
              <>
                {'耗时 '}
                {Math.round(shownElapsed)}s·{info.stepCount}步·
                {info.llmCallCount}轮
              </>
            ) : isNarrow || isMid ? (
              <Tooltip title={`${info.stepCount}步·${info.llmCallCount}轮`}>
                <span style={TABULAR_NUMS}>
                  {info.stepCount}/{info.llmCallCount}
                </span>
              </Tooltip>
            ) : (
              <>
                {info.stepCount}步·{info.llmCallCount}轮
              </>
            )}
          </span>
          {/* 小欧 2026-09-02: 第一行位4(位置固定, 新覆盖旧; 只收 retrying/error/truncated 无优先级; 去旧"重试N"累计与截断独立段) - 北京老陈拍板 */}
          {/* 3.9 断点矩阵: wide/mid 完整显示, narrow/xsmall 省略(maxWidth 200 + ellipsis + Tooltip 全文) — v4.4 修复#3 */}
          {info.liveMeta &&
            (isNarrow ? (
              <EllipsisTip
                text={info.liveMeta.text}
                tooltip={info.liveMeta.text}
                maxWidth={200}
              >
                {renderLiveMeta(info.liveMeta)}
              </EllipsisTip>
            ) : (
              renderLiveMeta(info.liveMeta)
            ))}
          {info.stuckWarning && (
            <span
              style={{ fontSize: FontSize.SECONDARY, color: Colors.WARNING }}
            >
              · 疑似卡死
            </span>
          )}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: Spacing.MD,
            flex: 1,
            minWidth: 0,
            justifyContent: 'center',
            flexWrap: 'wrap',
          }}
        >
          {/* G5 本轮: 标签灰 + T 加粗 + P/C 中灰(P1-7 两段对称) */}
          {/* 3.9 断点矩阵: narrow 累计段进浮层(累计 detail 收进 tooltip)、xsmall 明细全部进浮层(两段 detail 全收, 基础行恒 label+value) — v4.4 修复#3 */}
          <MetricItem
            label="本轮"
            value={formatToken(info.roundUsage?.total ?? 0)}
            detail={
              isXSmall
                ? undefined
                : `P ${info.roundUsage?.prompt ?? 0} / C ${info.roundUsage?.completion ?? 0}`
            }
            tooltip={`本轮 P ${info.roundUsage?.prompt ?? 0} / C ${info.roundUsage?.completion ?? 0} / T ${info.roundUsage?.total ?? 0}`}
          />
          <span
            style={{ fontSize: FontSize.SECONDARY, color: Colors.BORDER.LIGHT }}
          >
            ·
          </span>
          <MetricItem
            label="累计"
            value={formatToken(
              info.taskAccumulated?.total_tokens ?? info.usage.total
            )}
            detail={
              isNarrow
                ? undefined
                : `P ${info.taskAccumulated?.prompt_tokens ?? info.usage.prompt} / C ${info.taskAccumulated?.completion_tokens ?? info.usage.completion}`
            }
            tooltip="任务累计 P/C/T"
          />
          {/* G6 上下文(v4.1): 基础行 MetricItem 为浮层① 入口锚点, data-state 供测试 */}
          {(() => {
            const ctxState = mapStatus({
              overview: info.overview,
              contextSummary: frames.contextSummary,
            });
            const ctx = CONTEXT_STATE_MAP[ctxState];
            const tokens =
              typeof info.overview === 'object' && info.overview
                ? info.overview.estimated_tokens
                : null;
            const summary =
              typeof info.overview === 'string'
                ? info.overview
                : (info.overview?.summary ?? frames.contextSummary ?? '');
            // 3.3 状态机: ok/truncated 均显 "{n} tok"(truncated 警告色+图标); summary-only/empty 用态文案
            const showTokens = ctxState === 'ok' || ctxState === 'truncated';
            // v4.2: G6 入口经 FloatingEntry 实现(见 6.5.2.4), onClick 保持仅 stopPropagation(与 G8 对齐后单真源)
            return (
              <FloatingEntry
                open={ctxOpen}
                onOpenChange={setCtxOpen}
                placement="bottomLeft" // v4.1: 左缘对齐 G6; 窄屏右贴安全边距(v4.1 定案)(antd 真值, 见 FloatingEntry)
                cardId="taskinfo-context-card"
                ariaLabel="上下文详情"
                cardStyle={{
                  width: 320,
                  maxWidth: '90vw',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: Spacing.SM,
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.SECONDARY,
                }}
                content={
                  <>
                    <div
                      style={{
                        fontWeight: FontWeight.BOLD,
                        color: Colors.TEXT.PRIMARY,
                      }}
                    >
                      上下文详情
                    </div>
                    <div>
                      摘要: {summary.slice(0, 60)}
                      {summary.length > 60 ? '…' : ''}
                    </div>
                    <div>
                      估算 token:{' '}
                      {showTokens
                        ? `${(tokens ?? 0).toLocaleString('en-US')} tok`
                        : '—'}
                    </div>
                    <div
                      style={{
                        color:
                          ctx.tone === 'warning'
                            ? Colors.WARNING
                            : Colors.TEXT.TERTIARY,
                      }}
                    >
                      {ctxState === 'ok' ? '正常' : ctx.tooltip}
                    </div>
                  </>
                }
              >
                <MetricItem
                  label="上下文"
                  value={
                    showTokens
                      ? `${(tokens ?? 0).toLocaleString('en-US')} tok`
                      : ctx.text
                  }
                  tone={ctx.tone}
                  icon={ctx.icon}
                  dataState={ctxState}
                />
              </FloatingEntry>
            );
          })()}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: Spacing.MD,
            flexShrink: 0,
            marginLeft: 'auto',
          }}
        >
          {/* G7 信任: 内为 TrustPanel 触发按钮(6.5.4.3 改 Drawer 打开), 不承担折叠; 3.9 窄档仅计数 */}
          <TrustPanel sessionId={sessionId} compact={isNarrow} />
          {/* G8 事件入口(v4.1/P0-2/P2-12, v4.2 经 FloatingEntry 实现): 浮层② 事件卡片, 热区 32×32, hover 规格 2, 3.8 键盘 */}
          {/* v4.2 双写修复: 删 onClick 手动 setEventsOpen toggle(与 antd trigger click 双重写入), 开合唯一真源为 trigger + onOpenChange, 与 G6 对齐 */}
          <FloatingEntry
            open={eventsOpen}
            onOpenChange={setEventsOpen}
            placement="bottomRight" // v4.1: 右缘对齐 G8, 向左展开(3.9)(antd 真值, 见 FloatingEntry)
            cardId="taskinfo-events-card"
            ariaLabel="事件序列"
            cardStyle={{ width: 520, maxWidth: '90vw' }}
            content={eventsTimeline} // 6.5.3.10 移入: role="log" + aria-live + maxHeight 40vh 内滚
          >
            <span style={{ fontSize: FontSize.CAPTION }}>
              <DownOutlined style={{ fontSize: FontSize.CAPTION }} />{' '}
              {/* P1-5 + v4.1: 方向=弹出语义 */}
              事件
            </span>
          </FloatingEntry>
        </div>
      </div>
    </div>
  );
};

export { TaskInfoBar };
