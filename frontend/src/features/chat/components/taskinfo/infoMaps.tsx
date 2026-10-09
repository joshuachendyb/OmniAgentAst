// 编辑历史: 2026-09-08 小欧 - 六章6.5: 自 TaskInfoBar 抽取状态映射常量+纯函数(DRY/SRP/OCP, 禁止backward 不兼容旧写法)
// 职责: BADGE_MAP(cancelled 区分) / CONTEXT_STATE_MAP(4态状态机) / EVENT_ICON_MAP(9事件+新增)
// / mapStatus(纯函数) / formatTokenK(K/M 折算 3.2) — 小欧-2026-09-08
// 编辑历史: 2026-09-17 小欧 - 新增5个事件图标: error/rejected/cancelled/heartbeat/final - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 会审V3(#2): 删除 heartbeat 事件图标——后端心跳是 SSE 协议层 ":ping"(stream_orchestrator)，
// 永不被前端解析成 ProcessEvent, EVENT_ICON_MAP 中 heartbeat 为死代码(YAGNI 清理); 事件清单实为8类 — 小欧-2026-09-17
// 编辑历史: 2026-09-19 小欧: 恢复 heartbeat 事件图标(SyncOutlined)——心跳记录到事件列表(后端":ping" → ExecutionStep.heartbeat → processEvents) — 北京老陈驱动
// 编辑历史: 2026-10-04 小欧 - 文档[6]: ContextState 增 historical 态(4态→5态), mapStatus 依 isLiveContext
// 区分「历史任务无实时帧(设计如此)」与「真缺失」, empty 提示文案去内部变量名 frames — 小欧 2026-10-04
// 编辑历史: 2026-10-04 小欧 - token 显示序改 P→C→T, 行内折 K/M; formatToken 去 "T " 前缀后无调用方已删(YAGNI)
// 同日回退: historical 态与 mapStatus 的 isLiveContext 判据已撤, 改由卡片 isLiveContext 决定是否挂弹框
// 编辑历史: 2026-10-04 小欧 - EVENT_ICON_MAP 新增 context_trimmed(历史对话裁剪, 北京老陈令), 复用 WarningOutlined

// 编辑历史: 2026-10-07 小欧 - ContextSource 删 contextSummary: 上下文数据只认 history_context 帧(overview);
// 原 fallback 到 start.content(contextSummary) 会让未压缩/未注入的任务显示错误上下文
// 编辑历史: 2026-10-09 小欧[20] - ContextSource 复用帧类型; mapStatus 判据改 content; EVENT_ICON_MAP 加 context_compressed
// 编辑历史: 2026-10-10 小欧[20] - 删 summary-only 态(4态→3态): 历史任务无 conv_context,
// 单分组判据必然落进"有内容无计数", 自造的"摘要·无计数"漏进 UI。mapStatus 改双分组真值性

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
// 2026-10-09 小欧[20]: ContextSource 改复用帧类型(DRY, 不手写平铺形状)
import type { ContextOverviewFrame } from '@/types/sse';
// 2026-10-10 小欧[20] 帧读侧真源挪 utils/contextFrame(services 层也要用, 不许 UI 反向被依赖)
import { pickConv, pickInject } from '@/utils/contextFrame';

// ---------- BADGE_MAP（cancelled 与 idle 区分） ----------
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

// ---------- CONTEXT_STATE_MAP（3 态文案状态机） ----------
export type ContextState = 'ok' | 'truncated' | 'empty';
export interface ContextStateEntry {
  text: string; // 数值区文案（ok 态由调用方传入 token，此处留空）
  tone: 'primary' | 'secondary' | 'warning' | 'tertiary';
  icon?: ReactNode;
  tooltip: string;
}
export const CONTEXT_STATE_MAP: Record<ContextState, ContextStateEntry> = {
  ok: { text: '', tone: 'primary', tooltip: '上下文正常' },
  truncated: {
    text: '',
    tone: 'warning',
    icon: <WarningOutlined />,
    tooltip: '上下文被截断，可能影响回答质量',
  },
  empty: {
    text: '–',
    tone: 'tertiary',
    tooltip: '未收到上下文信息',
  },
};

// ---------- mapStatus（纯函数：输入数据源 → 3 态，供测试直接断言 data-state） ----------
// 输入形态: overview 字符串 / overview 对象(来自 history_context 帧)
export interface ContextSource {
  overview?: string | ContextOverviewFrame | null;
}
export const mapStatus = (src: ContextSource): ContextState => {
  const o = src.overview;
  // 2026-10-07 小欧: 上下文数据只认 history_context 帧(overview), 不再回退 start.content
  const mode = typeof o === 'string' ? o : (o?.content ?? '');
  const convCtx = pickConv(o);
  const injectCtx = pickInject(o);
  if (convCtx?.truncated === true) return 'truncated';
  const hasTokens =
    typeof convCtx?.estimated_tokens === 'number' ||
    typeof injectCtx?.injected_estimated_tokens === 'number';
  // content 有值即 ok(后端只给了状态文字), 不再编第四个态 —— 后端给什么显什么
  return hasTokens || mode ? 'ok' : 'empty';
};

// ---------- EVENT_ICON_MAP（过程事件统一 antd SVG，禁 emoji） ----------
// 2026-09-17 小欧 会审V3(#2): 8类事件——heartbeat 非事件(后端心跳=SSE 协议层 ":ping" 服务器注释帧,
// 对 JS EventSource 不可见, 永不解析为 ProcessEvent; 变更流不打 event 行, 已核实 stream_orchestrator) — 小欧-2026-09-17
export const EVENT_ICON_MAP: Record<ProcessEvent['kind'], ReactNode> = {
  started: <PlayCircleOutlined />, // 现状 ▶️ → SVG（3.4 定案）
  paused: <PauseCircleOutlined />, // 现状 ⏸️ → SVG
  resumed: <PlayCircleOutlined />, // 现状 ▶️ → SVG
  retrying: <ReloadOutlined />, // 现状 🔁 → SVG
  error: <WarningOutlined />, // 2026-09-17 小欧: 错误事件 - 小欧-2026-09-17
  rejected: <StopOutlined />, // 2026-09-17 小欧: 拒绝事件 - 小欧-2026-09-17
  cancelled: <CloseCircleOutlined />, // 2026-09-17 小欧: 取消事件 - 小欧-2026-09-17
  final: <CheckCircleOutlined />, // 2026-09-17 小欧: 任务完成/失败 - 小欧-2026-09-17
  heartbeat: <SyncOutlined />, // 2026-09-19 小欧: 心跳事件 — 北京老陈驱动
  // 2026-10-04 小欧: 历史对话裁剪事件(北京老陈令改名 context_trimmed, 与输出截断 truncated 区分), 复用警示图标
  context_trimmed: <WarningOutlined />,
  // 2026-10-09 北京老陈令[20]: 压缩事件图标, 与裁剪同级(压缩改变历史原貌, 值得警示)
  context_compressed: <WarningOutlined />, // 需与 useTaskInfo ProcessEvent kind 同步
};

// ---------- token 格式化（3.2：行内折 K/M；tooltip 用原始值） ----------
// 先查后建: src/utils/ 无折算工具, 新建; 2026-10-04 小欧 由 ContextOverviewCard 私有 fmtApproxTokens 提升共用(DRY),
// 原 formatToken(千分位) 因行内折 K、tooltip 用原始值而无调用方, 已删(YAGNI)
export const formatTokenK = (n: number | null | undefined): string => {
  if (n == null || Number.isNaN(n) || !Number.isFinite(n)) return '–';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
};

// ---------- 等宽数字共享样式（耗时、事件时间均用） ----------
export const TABULAR_NUMS: CSSProperties = {
  fontVariantNumeric: 'tabular-nums',
};
