// 编辑历史: 2026-09-08 小欧 - 六章6.5: 自 TaskInfoBar 抽取状态映射常量+纯函数(DRY/SRP/OCP, 禁止backward 不兼容旧写法)
//   职责: BADGE_MAP(P2-15 cancelled 区分) / CONTEXT_STATE_MAP(4态 P1-8) / EVENT_ICON_MAP(9事件 P1-5+新增)
//   / mapStatus(纯函数) / formatToken(千分位 3.2) — 小欧-2026-09-08
// 编辑历史: 2026-09-17 小欧 - 新增5个事件图标: error/rejected/cancelled/heartbeat/final - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 会审V3(#2): 删除 heartbeat 事件图标——后端心跳是 SSE 协议层 ":ping"(stream_orchestrator)，
//   永不被前端解析成 ProcessEvent, EVENT_ICON_MAP 中 heartbeat 为死代码(YAGNI 清理); 事件清单实为8类 — 小欧-2026-09-17
// 编辑历史: 2026-09-19 小欧: 恢复 heartbeat 事件图标(SyncOutlined)——心跳记录到事件列表(后端":ping" → ExecutionStep.heartbeat → processEvents) — 北京老陈驱动
import type { CSSProperties, ReactNode } from 'react';
import {
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  WarningOutlined,
  StopOutlined,
  CloseCircleOutlined,
  CheckCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import type { ProcessEvent, TaskBadge } from '../../hooks/useTaskInfo';

// ---------- BADGE_MAP（P2-15：cancelled 与 idle 区分） ----------
export interface BadgeEntry {
  status: 'default' | 'processing' | 'warning' | 'success' | 'error';
  text: string;
}
export const BADGE_MAP: Record<TaskBadge, BadgeEntry> = {
  idle: { status: 'default', text: '待命' }, // 灰点灰字，语义"空闲等待"
  running: { status: 'processing', text: '执行中' },
  paused: { status: 'warning', text: '已暂停' },
  completed: { status: 'success', text: '已完成' },
  failed: { status: 'error', text: '失败' },
  cancelled: { status: 'error', text: '已取消' }, // 定案: 红点红字，区分 idle 灰
};

// ---------- CONTEXT_STATE_MAP（P1-8：4 态文案状态机） ----------
export type ContextState = 'ok' | 'summary-only' | 'truncated' | 'empty';
export interface ContextStateEntry {
  text: string; // 数值区文案（ok 态由调用方传入 token，此处留空）
  tone: 'primary' | 'secondary' | 'warning' | 'tertiary';
  icon?: ReactNode;
  tooltip: string;
}
export const CONTEXT_STATE_MAP: Record<ContextState, ContextStateEntry> = {
  ok: { text: '', tone: 'primary', tooltip: '上下文正常' },
  // 3.3 状态机: summary-only/empty 数值色 TERTIARY(标签级弱文字), 非 SECONDARY(3.3 表/7.3 用例一致)
  'summary-only': {
    text: '摘要·无计数',
    tone: 'tertiary',
    tooltip: '上下文概览尚无 token 计数',
  },
  truncated: {
    text: '',
    tone: 'warning',
    icon: <WarningOutlined />,
    tooltip: '上下文被截断，可能影响回答质量',
  },
  empty: {
    text: '–',
    tone: 'tertiary',
    tooltip: '上下文缺失，检查 frames 数据链路',
  },
};

// ---------- mapStatus（纯函数：输入数据源 → 4 态，供测试直接断言 data-state） ----------
// 输入形态对齐现状三数据源: overview 字符串 / overview 对象{summary,estimated_tokens,truncated} / frames.contextSummary
export interface ContextSource {
  overview?:
    | string
    | {
        summary?: string;
        estimated_tokens?: number | null;
        truncated?: boolean;
      }
    | null;
  contextSummary?: string | null;
}
export const mapStatus = (src: ContextSource): ContextState => {
  const o = src.overview;
  const summary =
    typeof o === 'string' ? o : (o?.summary ?? src.contextSummary ?? null);
  const truncated =
    typeof o === 'object' && o !== null ? o.truncated === true : false;
  const hasTokens =
    typeof o === 'object' && o !== null && o.estimated_tokens != null;
  if (truncated) return 'truncated';
  if (summary) return hasTokens ? 'ok' : 'summary-only';
  return 'empty';
};

// ---------- EVENT_ICON_MAP（3.4/P1-5：过程事件统一 antd SVG，禁 emoji） ----------
// 2026-09-17 小欧 会审V3(#2): 8类事件——heartbeat 非事件(后端心跳=SSE 协议层 ":ping" 服务器注释帧,
//   对 JS EventSource 不可见, 永不解析为 ProcessEvent; 变更流不打 event 行, 已核实 stream_orchestrator) — 小欧-2026-09-17
export const EVENT_ICON_MAP: Record<ProcessEvent['kind'], ReactNode> = {
  started: <PlayCircleOutlined />, // 现状 ▶️   → SVG（3.4 定案）
  paused: <PauseCircleOutlined />, // 现状 ⏸️   → SVG
  resumed: <PlayCircleOutlined />, // 现状 ▶️   → SVG
  retrying: <ReloadOutlined />, // 现状 🔁   → SVG
  error: <WarningOutlined />, // 2026-09-17 小欧: 错误事件 - 小欧-2026-09-17
  rejected: <StopOutlined />, // 2026-09-17 小欧: 拒绝事件 - 小欧-2026-09-17
  cancelled: <CloseCircleOutlined />, // 2026-09-17 小欧: 取消事件 - 小欧-2026-09-17
  final: <CheckCircleOutlined />, // 2026-09-17 小欧: 任务完成/失败 - 小欧-2026-09-17
  heartbeat: <SyncOutlined />, // 2026-09-19 小欧: 心跳事件 — 北京老陈驱动
};

// ---------- formatToken（3.2：T 千分位，1234 → "T 1,234"；无值 → "–"） ----------
// 先查后建结论: src/utils/ 无千分位工具(en-US toLocaleString 全库无命中), 新建
export const formatToken = (n: number | null | undefined): string => {
  if (n == null || Number.isNaN(n)) return '–';
  return `T ${n.toLocaleString('en-US')}`;
};

// ---------- 等宽数字共享样式（P2-16/3.6：耗时、事件时间均用） ----------
export const TABULAR_NUMS: CSSProperties = {
  fontVariantNumeric: 'tabular-nums',
};
