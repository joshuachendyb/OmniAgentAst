/**
 * ConfigStatusPill - 顶栏模型配置状态胶囊: 五步校验(配置完整性+凭证预警)三级可用分级(绿就绪/黄预警/红错误),
 * 挂载自动检测+点击重检; 红黄态Tooltip列明细+去设置页出路; 不查后端存活(/health)不查LLM联通(无网络请求)
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - 三级可用性重设计(北京老陈令): 绿/黄/红分级承接后端status字段实装,
//   挂载自动检测+Tooltip明细+去设置出路, 语义=可发消息而非文件校验通过 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - Tip 视觉重做: 改共用 PillTip 骨架(状态点/标题/分隔线/对齐键值/明细/动作), 删内联堆叠 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 浮层改白卡片(color+styles.body)并删指向不存在id的aria-describedby死属性 — 小欧-2026-11-02
// 编辑历史: 2026-11-03 小欧 - 收口: 浮层卡片/容器栅格/hover 交 PillShell, 删本文件 HOVER_BG 与根宽重算 — 小欧-2026-11-03
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Badge } from 'antd';
import type { BadgeProps } from 'antd';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../contexts/AppContext';
import { PillTip } from './PillTip';
import { PillShell } from './PillShell';
import { FontSize, Colors } from '../../utils/stepStyles';
import type { ValidateResponse } from '../../services/api/chat.api';

// 2026-11-02 小欧 - 胶囊态→Tip 状态点色语义映射 — 小欧-2026-11-02
const TONE_OF = {
  ok: 'ok',
  warn: 'warn',
  fail: 'error',
  netfail: 'error',
  busy: 'neutral',
} as const;

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
    <PillShell
      role="button"
      ariaLabel="模型配置状态"
      onClick={handleCheck}
      busy={checking}
      tooltip={
        <PillTip
          tone={TONE_OF[state.kind]}
          title={state.text}
          subtitle={state.main}
          rows={[{ label: '模型', value: modelInfo || '未确认', mono: true }]}
          items={detailItems.map((text) => ({
            text,
            tone: state.kind === 'warn' ? 'warn' : 'error',
          }))}
          action={
            state.kind === 'fail' || state.kind === 'warn'
              ? {
                  label: '去设置页修改',
                  onAction: () => navigate('/settings2'),
                }
              : undefined
          }
        />
      }
    >
      <Badge
        status={state.badge}
        text={
          <span style={{ fontSize: FontSize.SECONDARY, color: state.color }}>
            {state.text}
          </span>
        }
      />
    </PillShell>
  );
};

export { ConfigStatusPill };
