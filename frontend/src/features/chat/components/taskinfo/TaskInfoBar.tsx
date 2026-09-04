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
import type { ExecutionStep } from '../../../../types/execution';
import type { TaskMetaFrames } from '@/types/sse';
import type { TaskDetail } from '../../../../services/api/task.api';
import { Colors } from '@/utils/stepStyles'; // 2026-09-03 小欧: 移除FontSize/Spacing(信任区已移入TrustPanel, 不再使用) — 小欧-2026-09-03
import { useTaskInfo } from '../../hooks/useTaskInfo';
import { TrustPanel } from '../config/TrustPanel'; // 2026-09-03 小欧: 复用TrustPanel, 删TaskInfoBar内联信任实现(DRY) — 小欧-2026-09-03

interface TaskInfoBarProps {
  steps: ExecutionStep[];
  frames: TaskMetaFrames; // 统计类元信息帧（8.4.14）
  receiving: boolean;
  detail?: TaskDetail | null; // 【A3】选中历史任务时由其详情派生动态信息
  sessionId?: string | null; // 13.14 TrustPanel第一行尾部需会话ID
  liveErrorText?: string | null; // 小欧 2026-09-02: 位4 error 实时源(useChatPanels 透传)
}

const BADGE_MAP = {
  idle: { status: 'default' as const, text: '待命' },
  running: { status: 'processing' as const, text: '执行中' },
  paused: { status: 'warning' as const, text: '已暂停' },
  completed: { status: 'success' as const, text: '已完成' },
  failed: { status: 'error' as const, text: '失败' },
  cancelled: { status: 'default' as const, text: '已取消' },
};

const TaskInfoBar: React.FC<TaskInfoBarProps> = ({
  steps,
  frames,
  receiving,
  detail,
  sessionId,
  liveErrorText,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const info = useTaskInfo(steps, frames, receiving, detail, liveErrorText);
  const b = BADGE_MAP[info.badge];
  // 【2026-09-03 小欧 复用TrustPanel】信任查询/刷新/撤销/折叠逻辑已移入 TrustPanel 组件(TaskInfoBar 删除内联重复, DRY)

  // 【小欧 2026-08-26 修复 B2】执行中实时计时：当前任务(receiving+running)按 start 时刻走表，
  // 历史任务(detail)用后端 duration，不计时。
  const [liveElapsed, setLiveElapsed] = useState(0);
  const startRef = useRef<number | null>(null); // 2026-08-27 小欧 三堂会审: 仅首次锚定start, 防计时抖动
  useEffect(() => {
    if (receiving && info.badge === 'running' && !detail) {
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
  }, [receiving, info.badge, detail]); // 2026-08-27 小欧 三堂会审: 去frames.startTimestamp防抖动
  const shownElapsed = detail
    ? info.elapsedSec
    : receiving && info.badge === 'running'
      ? liveElapsed
      : info.elapsedSec;

  return (
    <div
      style={{
        background: 'transparent',
        border: 'none',
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
        padding: '8px 0 0',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        textAlign: 'left',
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          cursor: 'pointer',
          flexWrap: 'nowrap',
        }}
        onClick={() => setCollapsed((v) => !v)}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
          }}
        >
          <Badge status={b.status} text={b.text} />
          <span
            style={{
              fontSize: 12,
              color: Colors.TEXT.PRIMARY,
              fontWeight: 500,
            }}
          >
            耗时 {Math.round(shownElapsed)}s
          </span>
          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
            步骤 {info.stepCount} / 轮次 {info.llmCallCount}
          </span>
          {/* 小欧 2026-09-02: 第一行位4(位置固定, 新覆盖旧; 只收 retrying/error/truncated 无优先级; 去旧"重试N"累计与截断独立段) - 北京老陈拍板 */}
          {info.liveMeta && (
            <span
              style={{ fontSize: 12, color: Colors.WARNING, marginLeft: 2 }}
            >
              [
              {{
                retrying: '🔁',
                error: '🛑',
                truncated: '⚠',
              }[info.liveMeta.kind] ?? '🔔'}{' '}
              {info.liveMeta.text}]
            </span>
          )}
          {info.stuckWarning && (
            <span style={{ fontSize: 12, color: Colors.WARNING }}>
              · 疑似卡死
            </span>
          )}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flex: 1,
            minWidth: 0,
            justifyContent: 'center',
          }}
        >
          <Tooltip
            title={`本轮 P ${info.roundUsage?.prompt ?? 0} / C ${info.roundUsage?.completion ?? 0} / T ${info.roundUsage?.total ?? 0}`}
          >
            <span
              style={{
                fontSize: 12,
                color: Colors.TEXT.PRIMARY,
                fontWeight: 500,
              }}
            >
              本轮 T{info.roundUsage?.total ?? 0} (P
              {info.roundUsage?.prompt ?? 0}/C
              {info.roundUsage?.completion ?? 0})
            </span>
          </Tooltip>
          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>·</span>
          <Tooltip
            title={`任务累计 P ${info.taskAccumulated?.prompt_tokens ?? info.usage.prompt} / C ${info.taskAccumulated?.completion_tokens ?? info.usage.completion} / T ${info.taskAccumulated?.total_tokens ?? info.usage.total}`}
          >
            <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
              本任务累计 T
              {info.taskAccumulated?.total_tokens ?? info.usage.total} (P
              {info.taskAccumulated?.prompt_tokens ?? info.usage.prompt}/C
              {info.taskAccumulated?.completion_tokens ?? info.usage.completion}
              )
            </span>
          </Tooltip>
          <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>·</span>
          {typeof info.overview === 'string' ? (
            <Tooltip title={info.overview}>
              <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
                上下文摘要
              </span>
            </Tooltip>
          ) : info.overview ? (
            <Tooltip
              title={`${info.overview.summary}\n消息数 ${info.overview.message_count ?? '-'} · 估算 ${info.overview.estimated_tokens ?? '-'} tok`}
            >
              <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
                上下文 {info.overview.estimated_tokens ?? '-'}tok
                {info.overview.truncated && ' 🔴'}
              </span>
            </Tooltip>
          ) : frames.contextSummary ? (
            <Tooltip title={frames.contextSummary}>
              <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
                上下文摘要
              </span>
            </Tooltip>
          ) : (
            <span style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
              上下文 {0}tok
            </span>
          )}
        </div>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            flexShrink: 0,
            marginLeft: 'auto',
          }}
        >
          {/* 2026-09-03 小欧 复用TrustPanel(信任查询/刷新/撤销/折叠/Tooltip/stopPropagation全部组件内承载), 替换原内联折叠三角 */}
          <TrustPanel sessionId={sessionId} />
        </div>
      </div>

      {!collapsed && info.processEvents.length > 0 && (
        <div
          style={{
            maxHeight: 72,
            overflowY: 'auto',
            scrollbarWidth: 'thin',
            borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
            paddingTop: 8,
            marginTop: 0,
          }}
        >
          {info.processEvents.map((e, i) => (
            <div key={i} style={{ fontSize: 12, color: Colors.TEXT.TERTIARY }}>
              {e.kind === 'started' && '▶️ '}
              {e.kind === 'paused' && '⏸️ '}
              {e.kind === 'resumed' && '▶️ '}
              {e.kind === 'retrying' && '🔁 '}
              {e.text} {new Date(e.time).toLocaleTimeString()}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { TaskInfoBar };
