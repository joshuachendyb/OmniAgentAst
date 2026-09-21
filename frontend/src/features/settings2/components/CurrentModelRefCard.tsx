// 编辑历史: 2026-09-21 小欧 - 新建：当前生效模型高占位状态卡（三态：正常/兜底推荐/无可用）（[58] 第五章 5.3~5.5）
// 2026-09-21 小欧 - 核查修复：硬编码琥珀色→Colors.BG.WARNING_LIGHT/Colors.WARNING 令牌（[58] v1.11 Step5.1）
import React from 'react';
import { Button, Tag } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsRadius } from '@/theme/settingsTokens';
import type { SessionModelOverride } from '@/types/chat';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  currentRef: SessionModelOverride | null;
  providers: ProviderEntry[];
  onSelectModel: () => void;
  onAddProvider: () => void;
}

type Status = 'normal' | 'fallback' | 'no_available';

function resolveStatus(
  currentRef: SessionModelOverride | null,
  providers: ProviderEntry[]
): Status {
  if (!providers.length) return 'no_available';
  if (!currentRef) return 'no_available';
  const provider = providers.find((p) => p.name === currentRef.provider);
  if (!provider) return 'fallback';
  const model = provider.models.find((m) => m.name === currentRef.model);
  if (!model) return 'fallback';
  return 'normal';
}

export const CurrentModelRefCard: React.FC<Props> = ({
  currentRef,
  providers,
  onSelectModel,
  onAddProvider,
}) => {
  const status = resolveStatus(currentRef, providers);
  const providerName = currentRef?.provider ?? '';
  const modelName = currentRef?.model ?? '';

  const bgColor = status === 'normal'
    ? Colors.BG.PRIMARY
    : status === 'fallback'
      ? Colors.BG.WARNING_LIGHT
      : Colors.BG.TERTIARY;
  const borderColor = status === 'normal'
    ? Colors.PRIMARY
    : status === 'fallback'
      ? Colors.WARNING
      : Colors.ERROR;
  const icon = status === 'normal'
    ? <CheckCircleOutlined style={{ color: Colors.PRIMARY }} />
    : status === 'fallback'
      ? <WarningOutlined style={{ color: Colors.WARNING }} />
      : <CloseCircleOutlined style={{ color: Colors.ERROR }} />;

  return (
    <div
      style={{
        padding: `${Spacing.MD}px ${Spacing.LG}px`,
        marginBottom: Spacing.LG,
        background: bgColor,
        border: `1px solid ${borderColor}`,
        borderRadius: settingsRadius.DEFAULT,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.SM }}>
        <span style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}>
          当前生效模型
        </span>
        <Tag color="default" style={{ fontSize: FontSize.SECONDARY }}>
          YAML 顶层 ai 块 · 全局默认
        </Tag>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.SM, marginBottom: Spacing.SM }}>
        {icon}
        <span style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}>
          {status === 'normal' && '正常使用中'}
          {status === 'fallback' && '⚠ 配置文件中 ai 块缺失或模型不可用，系统已自动使用推荐模型'}
          {status === 'no_available' && '未配置任何可用模型，所有会话将无法调用 LLM'}
        </span>
      </div>
      <div style={{ fontSize: FontSize.PRIMARY, marginBottom: Spacing.SM }}>
        {providerName && modelName
          ? `${providerName} / ${modelName}`
          : '（无）'}
      </div>
      <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY, marginBottom: Spacing.MD }}>
        全局默认：所有会话默认使用此模型；单个会话可另行覆盖（L2）
      </div>
      <div>
        {status === 'normal' && (
          <Button size="small" onClick={onSelectModel}>
            更换模型 →
          </Button>
        )}
        {status === 'fallback' && (
          <Button size="small" type="primary" onClick={onSelectModel}>
            去选择
          </Button>
        )}
        {status === 'no_available' && (
          <Button size="small" type="primary" danger onClick={onAddProvider}>
            添加 Provider
          </Button>
        )}
      </div>
    </div>
  );
};
