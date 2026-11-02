/**
 * ConfigStatusPill - 顶栏模型配置状态胶囊: 五步校验(配置完整性+凭证预警)三级可用分级(绿就绪/黄预警/红错误),
 * 挂载自动检测+点击重检; 红黄态Tooltip列明细+去设置页出路; 不查后端存活(/health)不查LLM联通(无网络请求)
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - 三级可用性重设计(北京老陈令): 绿/黄/红分级承接后端status字段实装,
//   挂载自动检测+Tooltip明细+去设置出路, 语义=可发消息而非文件校验通过 - 小欧-2026-11-02
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Badge, Tooltip } from 'antd';
import type { BadgeProps } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../contexts/AppContext';
import { Spacing, FontSize, Colors, Radius } from '../../utils/stepStyles';
import type { ValidateResponse } from '../../services/api/chat.api';

// 2026-11-02 小欧 - 顶栏白底上的悬停浅灰(与侧栏底条hover同令牌)
const HOVER_BG = Colors.BG.HOVER;
// 2026-11-02 小欧 - Tooltip 明细最大宽, 防单条长文案(凭证预警原文较长)撑爆悬浮层 - 小欧-2026-11-02
const TIP_MAX_WIDTH = 320;

interface PillState {
  badge: BadgeProps['status'];
  kind: 'ok' | 'warn' | 'fail' | 'busy' | 'netfail';
  text: string;
  color: string;
  /** 主说明行(明细列表之前的结论) */
  main: string;
}

const deriveState = (
  checking: boolean,
  hasChecked: boolean,
  status: ValidateResponse | null
): PillState => {
  if (checking) {
    return {
      badge: 'processing',
      kind: 'busy',
      text: '检测中',
      color: Colors.TEXT.SECONDARY,
      main: '正在校验模型配置...',
    };
  }
  if (status === null) {
    return hasChecked
      ? {
          badge: 'error',
          kind: 'netfail',
          text: '检测失败',
          color: Colors.ERROR,
          main: '网络或后端服务异常，配置状态未知',
        }
      : {
          badge: 'default',
          kind: 'fail',
          text: '未检测',
          color: Colors.TEXT.SECONDARY,
          main: '尚未校验模型配置',
        };
  }
  if (!status.valid || status.status === 'failed') {
    return {
      badge: 'error',
      kind: 'fail',
      text: '配置错误',
      color: Colors.ERROR,
      main: status.message,
    };
  }
  if (status.status === 'warning') {
    return {
      badge: 'warning',
      kind: 'warn',
      text: '配置预警',
      color: Colors.WARNING,
      main: status.message,
    };
  }
  return {
    badge: 'success',
    kind: 'ok',
    text: '配置就绪',
    color: Colors.TEXT.SECONDARY,
    main: status.message,
  };
};

const ConfigStatusPill: React.FC = () => {
  const { serviceStatus, refreshServiceStatus } = useApp();
  const navigate = useNavigate();
  const [checking, setChecking] = useState(false);
  const [hasChecked, setHasChecked] = useState(false);
  const checkingRef = useRef(false);

  // 检测: ref防重入(setState异步, 并发点击守不住); 结果经AppContext.serviceStatus回灌由视图派生
  const handleCheck = useCallback(async () => {
    if (checkingRef.current) return;
    checkingRef.current = true;
    setChecking(true);
    try {
      await refreshServiceStatus();
      setHasChecked(true);
    } finally {
      checkingRef.current = false;
      setChecking(false);
    }
  }, [refreshServiceStatus]);

  // 挂载即自动检测(零成本本地校验, 免费), 点击胶囊=重新检测
  useEffect(() => {
    void handleCheck();
  }, [handleCheck]);

  const state = deriveState(checking, hasChecked, serviceStatus);
  const modelInfo = serviceStatus?.model_ref
    ? `${serviceStatus.model_ref.provider} (${serviceStatus.model_ref.model})`
    : '';
  // 明细行: 红态列硬错误, 黄态列预警, 绿/检测中不列
  const detailItems: string[] =
    serviceStatus === null
      ? []
      : state.kind === 'fail'
        ? (serviceStatus.errors ?? [])
        : state.kind === 'warn'
          ? (serviceStatus.warnings ?? [])
          : [];

  return (
    <Tooltip
      title={
        <div style={{ maxWidth: TIP_MAX_WIDTH }}>
          <div>{state.main}</div>
          {modelInfo && `当前配置: ${modelInfo}`}
          {detailItems.map((item, idx) => (
            <div key={idx}>{`· ${item}`}</div>
          ))}
          {(state.kind === 'fail' || state.kind === 'warn') && (
            <span
              role="button"
              tabIndex={0}
              aria-label="去设置页修改配置"
              onClick={(e) => {
                e.stopPropagation();
                navigate('/settings2');
              }}
              style={{ color: Colors.PRIMARY, cursor: 'pointer' }}
            >
              去设置页修改 →
            </span>
          )}
        </div>
      }
    >
      <span
        role="button"
        aria-label="模型配置状态"
        aria-describedby="config-status-detail"
        onClick={handleCheck}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          // 2026-11-02 小欧 - 三堂会审令牌纪律: pad 4/8=Spacing.XS/MD, 圆角4=Radius.SM(例: SidebarModeSwitcher同款) — 小欧-2026-11-02
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

export { ConfigStatusPill };
