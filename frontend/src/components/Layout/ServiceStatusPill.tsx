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
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Badge, Tooltip } from 'antd';
import type { BadgeProps } from 'antd';
import { useApp } from '../../contexts/AppContext';
import { PillTip, PILL_TIP_MAX_W, type PillTipRow } from './PillTip';
import {
  Spacing,
  FontSize,
  Colors,
  Radius,
  BorderWidth,
} from '../../utils/stepStyles';
import { API_BASE_URL } from '../../services/api/client';
import type { HealthStatus } from '../../services/api/health.api';

// 2026-11-02 小欧 - 顶栏白底上的悬停浅灰(与配置胶囊同令牌) — 小欧-2026-11-02
const HOVER_BG = Colors.BG.HOVER;
// 2026-11-02 小欧 - 浮层根宽上限: 内容宽+左右padding+描边, 破 antd 根节点默认250px提前折行 — 小欧-2026-11-02
const TIP_ROOT_MAX_W = PILL_TIP_MAX_W + Spacing.LG * 2 + BorderWidth.THIN * 2;
// 2026-11-02 小欧 - 本机探活正常在10ms级, 超1.5s说明事件循环已被占死(见AGENTS.md卡死取证) — 小欧-2026-11-02
const SLOW_MS = 1500;
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
          main: '后端无响应: 连接被拒或超过 5 秒未返回',
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
  if (latencyMs !== null && latencyMs >= SLOW_MS) {
    return {
      badge: 'warning',
      kind: 'slow',
      text: '服务缓慢',
      color: Colors.WARNING,
      main: `后端响应耗时 ${latencyMs}ms，事件循环可能被占死`,
    };
  }
  if (health.status !== 'healthy') {
    return {
      badge: 'warning',
      kind: 'slow',
      text: '服务降级',
      color: Colors.WARNING,
      main: '后端应答正常但自报降级，部分功能可能受限',
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
  const handleCheck = useCallback(async () => {
    if (checkingRef.current) return;
    checkingRef.current = true;
    setChecking(true);
    setLatencyMs(null);
    const startedAt = performance.now();
    try {
      const health = await refreshHealth();
      setLatencyMs(
        health === null ? null : Math.round(performance.now() - startedAt)
      );
      setHasChecked(true);
    } finally {
      checkingRef.current = false;
      setChecking(false);
    }
  }, [refreshHealth]);

  // 挂载即自动检测(一次只读探活, 无定时器), 点击胶囊=重新检测
  useEffect(() => {
    void handleCheck();
  }, [handleCheck]);

  const state = deriveState(checking, hasChecked, healthStatus, latencyMs);

  // 2026-11-02 小欧 - 本机地址: 后端自报局域网IP + 访问地址里的端口(反代80/443时无端口, 不硬凑) — 小欧-2026-11-02
  const host = healthStatus?.host ?? '';
  const portInHost = /:(\d+)$/.exec(host)?.[1];
  const lanAddr = healthStatus?.server_ip
    ? `${healthStatus.server_ip}${portInHost ? `:${portInHost}` : ''}`
    : '';

  // 2026-11-02 小欧 - 键值行固定六行(全量常显): 缺值标"—/未上报", 绝不因数据缺失而整行消失 — 小欧-2026-11-02
  const rows: PillTipRow[] = [
    { label: '本机', value: lanAddr || '未上报', mono: true },
    { label: '访问', value: host || '未上报', mono: true },
    { label: '前缀', value: API_BASE_URL, mono: true },
    { label: '连接', value: CONN_KIND },
    { label: '耗时', value: latencyMs !== null ? `${latencyMs}ms` : '—' },
    {
      label: '进程',
      value: healthStatus?.pid ? String(healthStatus.pid) : '—',
    },
  ];

  return (
    <Tooltip
      color={Colors.BG.PRIMARY}
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
        onClick={handleCheck}
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
