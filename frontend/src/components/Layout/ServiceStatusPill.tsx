/**
 * ServiceStatusPill - 顶栏后端服务存活胶囊: /health 探测三级(绿正常/黄缓慢/红离线),
 * 挂载自动检测+点击重检; 与 ConfigStatusPill(配置是否允许发消息)正交, 本胶囊只答"后端能不能应答"
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - 新建: 服务状态与配置状态分立(北京老陈令); 黄态=响应缓慢(端口在监听但服务僵死的早期体征), 不查DB — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - Tooltip 全量常显(北京老陈定案): 耗时/本机地址/访问地址/请求前缀/连接方式/PID 逐行 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - Tip 视觉重做: 改共用 PillTip 骨架(状态点/标题/分隔线/对齐键值/明细), 地址走等宽可选中 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 浮层改白卡片(color+styles.body), 键值行序=本机/访问/前缀/连接/耗时/进程 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 打开Tip即静默重检: 挂载快照会被后端重启/字段变更拖旧(空值误判), 静默重检不翻检测中态免闪烁 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 耗时改 时:分:秒.毫秒 渲染(31ms→00:00:00.031), Tip 耗时行与缓慢态结论同格式 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - Tip 扩成分组十行(地址4/运行时6): 补循环延迟/应答时刻/数据库/运行时长, 阈值改由 health.api 单一口径 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 存活时长并入进程行改人话(7分34秒)+三组分口径, 消除"耗时/运行时长"像重复指标 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 探活耗时与事件循环并成一行"响应": 常态只给正常, 异常才给 往返·循环 数字(兼定位卡在链路还是循环) — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 响应行单位定案毫秒(1820 ms): 时钟格式易被误读成"服务器运作时长"; 离线文案改吃 PROBE_TIMEOUT_MS 免字面量漂移 — 小欧-2026-11-02
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Badge, Tooltip } from 'antd';
import type { BadgeProps } from 'antd';
import { useApp } from '../../contexts/AppContext';
import { useStreamPulse } from '../../features/chat/hooks/useStreamPulse';
import { PillTip, PILL_TIP_ROOT_MAX_W, type PillTipRow } from './PillTip';
import {
  Spacing,
  FontSize,
  Colors,
  Radius,
  BorderWidth,
} from '../../utils/stepStyles';
import { API_BASE_URL } from '../../services/api/client';
import {
  SLOW_RESPONSE_MS,
  PROBE_TIMEOUT_MS,
} from '../../services/api/health.api';
import type { HealthStatus } from '../../services/api/health.api';

// 2026-11-02 小欧 - 顶栏白底上的悬停浅灰(与配置胶囊同令牌) — 小欧-2026-11-02
const HOVER_BG = Colors.BG.HOVER;
// 2026-11-02 小欧 - 浮层根宽上限随 PillTip 统一(与配置/流状态胶囊同算法) — 小欧-2026-11-02
const TIP_ROOT_MAX_W = PILL_TIP_ROOT_MAX_W;
// 2026-11-02 小欧 - 应答时刻取后端本地ISO的年月日+时刻段(不new Date, 免浏览器时区二次换算); 只留时刻会看不出是哪天 — 小欧-2026-11-02
const stampOf = (iso?: string): string => {
  const [date, time] = (iso ?? '').split('T');
  return date && time ? `${date} ${time.slice(0, 8)}` : '';
};
// 2026-11-02 小欧 - 数据库自报状态: 有码值才着色, 缺失不着色(不漏报也不虚报) — 小欧-2026-11-02
const DB_VIEW: Record<string, { text: string; tone: 'ok' | 'warn' }> = {
  healthy: { text: '正常', tone: 'ok' },
  degraded: { text: '降级', tone: 'warn' },
};
// 2026-11-02 小欧 - 响应行: 平时只给"正常"二字, 数字只在异常时出现; 单位统一毫秒(北京老陈定案:
//   本行只答"这一次响应多少毫秒", 借用时:分:秒.毫秒反而与"已运行"混淆, 也让人误读成服务器运行时长) — 小欧-2026-11-02
//   循环延迟只在它本身越线时追加, 用于回答"慢在链路还是慢在事件循环" — 小欧-2026-11-02
const LOOP_BAD_MS = 100;
const deriveResponse = (
  latencyMs: number | null,
  loopLagMs: number | null
): { text: string; tone?: 'ok' | 'warn' } => {
  if (latencyMs === null) return { text: '未上报' };
  const slow = latencyMs >= SLOW_RESPONSE_MS;
  const loopHeavy = loopLagMs !== null && loopLagMs >= LOOP_BAD_MS;
  if (!slow && !loopHeavy) return { text: '正常', tone: 'ok' };
  const parts = [`${Math.round(latencyMs)} ms`];
  if (loopHeavy) parts.push(`循环 ${Math.round(loopLagMs)} ms`);
  return { text: parts.join(' · '), tone: 'warn' };
};
// 2026-11-02 小欧 - 进程存活时长按人话写(天/时/分/秒): 与响应耗时的毫秒数彻底区分, 避免被读成"服务器运作时长" — 小欧-2026-11-02
const formatUptime = (ms: number): string => {
  const s = Math.max(0, Math.floor(ms / 1000));
  const day = Math.floor(s / 86400);
  const hour = Math.floor((s % 86400) / 3600);
  const minute = Math.floor((s % 3600) / 60);
  const second = s % 60;
  if (day) return `${day}天${hour}小时`;
  if (hour) return `${hour}小时${minute}分`;
  if (minute) return `${minute}分${second}秒`;
  return `${second}秒`;
};
// 2026-11-02 小欧 - 胶囊态→Tip 状态点色语义映射 — 小欧-2026-11-02
const TONE_OF = {
  ok: 'ok',
  slow: 'warn',
  down: 'error',
  busy: 'neutral',
} as const;

// 2026-11-02 小欧 - 连接方式判定: dev走Vite代理; 打包后 VITE_API_BASE_URL 非空=直连, 空=同源反代 — 小欧-2026-11-02
const CONN_KIND = import.meta.env.DEV
  ? '开发 · Vite 代理'
  : import.meta.env.VITE_API_BASE_URL
    ? '打包 · 直连'
    : '打包 · 同源';

interface PillState {
  badge: BadgeProps['status'];
  kind: 'ok' | 'slow' | 'down' | 'busy';
  text: string;
  color: string;
  /** 主说明行(Tooltip 结论) */
  main: string;
}

const deriveState = (
  checking: boolean,
  hasChecked: boolean,
  health: HealthStatus | null,
  latencyMs: number | null
): PillState => {
  if (checking) {
    return {
      badge: 'processing',
      kind: 'busy',
      text: '检测中',
      color: Colors.TEXT.SECONDARY,
      main: '正在检测后端服务...',
    };
  }
  if (health === null) {
    return hasChecked
      ? {
          badge: 'error',
          kind: 'down',
          text: '服务离线',
          color: Colors.ERROR,
          main: `后端无响应: 连接被拒或超过 ${PROBE_TIMEOUT_MS / 1000} 秒未返回`,
        }
      : {
          badge: 'default',
          kind: 'down',
          text: '未检测',
          color: Colors.TEXT.SECONDARY,
          main: '尚未检测后端服务',
        };
  }
  // 缓慢优先于降级: 卡死体征比后端自报降级更值得先看
  if (latencyMs !== null && latencyMs >= SLOW_RESPONSE_MS) {
    return {
      badge: 'warning',
      kind: 'slow',
      text: '服务缓慢',
      color: Colors.WARNING,
      // 2026-11-02 小欧 - 结论文案与响应行同单位(ms), 不下"已占死"的断言: 慢可以是排队也可以是循环被占 — 小欧-2026-11-02
      main: `后端响应 ${Math.round(latencyMs)} ms（阈值 ${SLOW_RESPONSE_MS} ms），可能正在排队或事件循环被占`,
    };
  }
  if (health.status !== 'healthy') {
    return {
      badge: 'warning',
      kind: 'slow',
      text: '服务降级',
      color: Colors.WARNING,
      main: '后端应答正常但数据库校验未过，部分功能可能受限',
    };
  }
  return {
    badge: 'success',
    kind: 'ok',
    text: '服务正常',
    color: Colors.TEXT.SECONDARY,
    main: '后端应答正常',
  };
};

const ServiceStatusPill: React.FC = () => {
  const { healthStatus, refreshHealth } = useApp();
  const [checking, setChecking] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const checkingRef = useRef(false);

  // 检测: ref 防重入(setState 异步, 并发点击守不住); 耗时由本组件夹表, 结果经 AppContext 回灌
  // visible=true = 点击重检(翻"检测中"给反馈); false = Tip 打开时的静默重检(不翻态, 免每次悬停闪一下)
  const runCheck = useCallback(
    async (visible: boolean) => {
      if (checkingRef.current) return;
      checkingRef.current = true;
      if (visible) {
        setChecking(true);
        setLatencyMs(null);
      }
      const startedAt = performance.now();
      try {
        const health = await refreshHealth();
        setLatencyMs(
          health === null ? null : Math.round(performance.now() - startedAt)
        );
        setHasChecked(true);
      } finally {
        checkingRef.current = false;
        if (visible) setChecking(false);
      }
    },
    [refreshHealth]
  );

  // 挂载即自动检测(一次只读探活, 无定时器), 点击胶囊=重新检测
  useEffect(() => {
    void runCheck(true);
  }, [runCheck]);

  const state = deriveState(checking, hasChecked, healthStatus, latencyMs);

  // 2026-11-02 小欧 - 本机地址: 后端自报局域网IP + 访问地址里的端口(反代80/443时无端口, 不硬凑) — 小欧-2026-11-02
  const host = healthStatus?.host ?? '';
  const portInHost = /:(\d+)$/.exec(host)?.[1];
  const lanAddr = healthStatus?.server_ip
    ? `${healthStatus.server_ip}${portInHost ? `:${portInHost}` : ''}`
    : '';

  // 2026-11-02 小欧 - 后端自报诊断量: 循环延迟点采样/应答时刻/存活时长/数据库, 缺字段一律"未上报" — 小欧-2026-11-02
  const loopLagMs = healthStatus?.loop_lag_ms ?? null;
  const dbView = healthStatus?.db_status
    ? DB_VIEW[healthStatus.db_status]
    : undefined;
  const answeredAt = stampOf(healthStatus?.timestamp);
  const uptimeMs =
    typeof healthStatus?.uptime_s === 'number'
      ? Math.round(healthStatus.uptime_s * 1000)
      : null;

  // 2026-11-02 小欧 - 流状态并入浮层: 同一个后端进程, 但探活与 SSE 是两条独立链路,
  //   并排显示才能区分"进程还活着 / 这条流已经断了" — 小欧-2026-11-02
  const streamView = useStreamPulse();
  const streamTone =
    streamView.tone === 'neutral' ? undefined : streamView.tone;

  // 2026-11-02 小欧 - 分组八行(全量常显): 地址组答"连的是谁", 探测组答"这一次测出什么", 进程组答"是哪条命、活了多久";
  //   响应行常态只给"正常", 数字只在异常时出现, 免假精确也免与存活时长混淆 — 小欧-2026-11-02
  const responseView = deriveResponse(latencyMs, loopLagMs);
  const rows: PillTipRow[] = [
    { label: '本机', value: lanAddr || '未上报', mono: true, group: '地址' },
    { label: '访问', value: host || '未上报', mono: true },
    { label: '前缀', value: API_BASE_URL, mono: true },
    { label: '连接', value: CONN_KIND },
    {
      label: '响应耗时',
      value: responseView.text,
      tone: responseView.tone,
      group: '本次探测',
    },
    { label: '应答时刻', value: answeredAt || '未上报' },
    { label: '数据库', value: dbView?.text ?? '未上报', tone: dbView?.tone },
    {
      label: '进程',
      value: [
        healthStatus?.pid ? String(healthStatus.pid) : '—',
        uptimeMs !== null ? `已运行 ${formatUptime(uptimeMs)}` : '',
      ]
        .filter(Boolean)
        .join(' · '),
      group: '后端进程',
    },
    {
      label: '流状态',
      value: streamView.pulse.active ? streamView.text : '无进行中的流',
      tone: streamTone,
      group: 'SSE 流',
    },
    {
      label: '业务帧',
      value:
        streamView.bizAgeSec === null
          ? '未收到'
          : `${streamView.bizAgeSec} 秒前`,
      tone: streamView.bizStale ? 'warn' : undefined,
    },
    {
      label: '最近心跳',
      value:
        streamView.heartbeatAgeSec === null
          ? '未收到'
          : `${streamView.heartbeatAgeSec} 秒前`,
    },
    {
      label: '最后字节',
      value:
        streamView.dataAgeSec === null
          ? '未收到'
          : `${streamView.dataAgeSec} 秒前`,
      tone: streamView.dataStale ? 'warn' : undefined,
    },
  ];

  return (
    <Tooltip
      color={Colors.BG.PRIMARY}
      // 2026-11-02 小欧 - Tip 每次打开先静默重检: 保证看到的是此刻真值, 而不是挂载时的快照 — 小欧-2026-11-02
      onOpenChange={(open) => {
        if (open) void runCheck(false);
      }}
      styles={{
        root: { maxWidth: TIP_ROOT_MAX_W },
        body: {
          padding: `${Spacing.MD}px ${Spacing.LG}px`,
          border: `${BorderWidth.THIN}px solid ${Colors.BORDER.VERTICAL}`,
          borderRadius: Radius.LG,
        },
      }}
      title={
        <PillTip
          tone={TONE_OF[state.kind]}
          title={state.text}
          subtitle={state.main}
          rows={rows}
          items={
            state.kind === 'down' && hasChecked
              ? [{ text: '请确认后端进程已启动', tone: 'error' }]
              : undefined
          }
        />
      }
    >
      <span
        role="button"
        aria-label="后端服务状态"
        onClick={() => void runCheck(true)}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          // 2026-11-02 小欧 - 令牌纪律: pad 4/8=Spacing.XS/MD, 圆角4=Radius.SM, 与配置胶囊同款 — 小欧-2026-11-02
          padding: `${Spacing.XS}px ${Spacing.MD}px`,
          borderRadius: Radius.SM,
          cursor: checking ? 'default' : 'pointer',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => {
          if (!checking) e.currentTarget.style.background = HOVER_BG;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
        }}
      >
        <Badge
          status={state.badge}
          text={
            <span style={{ fontSize: FontSize.SECONDARY, color: state.color }}>
              {state.text}
            </span>
          }
        />
      </span>
    </Tooltip>
  );
};

export { ServiceStatusPill };
