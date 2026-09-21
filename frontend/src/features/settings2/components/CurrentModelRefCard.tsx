// 编辑历史: 2026-09-21 小欧 - 新建：当前生效模型高占位状态卡（三态：正常/兜底推荐/无可用）（[58] 第五章 5.3~5.5）
// 2026-09-21 小欧 - 核查修复：硬编码琥珀色→Colors.BG.WARNING_LIGHT/Colors.WARNING 令牌（[58] v1.11 Step5.1）
// 2026-09-21 小欧 - 全文逐章核查(第五章5.4/5.5)：补 capabilities tags、"使用中"徽标、S2/S3 文案对齐、来源徽标点击说明（[58] v1.12）
// 2026-09-21 小欧 - 更换模型独立弹框：按钮改为打开 ModelSwitchModal，不再跳转模型Tab
// 2026-09-21 小强 - 补 success 检查对齐顶栏：后端校验失败回 HTTP200+success:false，不查则假成功 toast（北京老陈定）
// 2026-09-21 小欧 - 标题改为"当前系统全局使用模型"并移到卡片边框上方；删未使用的 Popover 导入
import React, { useState } from 'react';
import { Button, Tag } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsRadius } from '@/theme/settingsTokens';
import { configApi } from '@/services/api/config.api';
import {
  handleApiError,
  handleError,
  showSuccess,
  ErrorType,
} from '@/services/error/handler';
import { ModelSwitchModal } from './ModelSwitchModal';
import type { SessionModelOverride } from '@/types/chat';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  currentRef: SessionModelOverride | null;
  providers: ProviderEntry[];
  onModelSwitched: () => void;
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
  onModelSwitched,
  onAddProvider,
}) => {
  const [switchOpen, setSwitchOpen] = useState(false);
  const status = resolveStatus(currentRef, providers);
  const providerName = currentRef?.provider ?? '';
  const modelName = currentRef?.model ?? '';
  // 5.4：capabilities tags 复用选中模型数据，无则隐藏整行
  const modelEntry = providers
    .find((p) => p.name === providerName)
    ?.models.find((m) => m.name === modelName);
  const capabilities = modelEntry?.capabilities ?? [];

  const bgColor =
    status === 'normal'
      ? Colors.BG.PRIMARY
      : status === 'fallback'
        ? Colors.BG.WARNING_LIGHT
        : Colors.BG.TERTIARY;
  const borderColor =
    status === 'normal'
      ? Colors.PRIMARY
      : status === 'fallback'
        ? Colors.WARNING
        : Colors.ERROR;
  const icon =
    status === 'normal' ? (
      <CheckCircleOutlined style={{ color: Colors.PRIMARY }} />
    ) : status === 'fallback' ? (
      <WarningOutlined style={{ color: Colors.WARNING }} />
    ) : (
      <CloseCircleOutlined style={{ color: Colors.ERROR }} />
    );

  return (
    <div>
      <div
        style={{
          fontSize: FontSize.PRIMARY,
          fontWeight: FontWeight.BOLD,
          marginBottom: Spacing.SM,
        }}
      >
        当前系统全局使用模型
      </div>
      <div
        style={{
          padding: `${Spacing.MD}px ${Spacing.LG}px`,
          marginBottom: Spacing.LG,
          background: bgColor,
          border: `1px solid ${borderColor}`,
          borderRadius: settingsRadius.DEFAULT,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: Spacing.SM,
            marginBottom: Spacing.SM,
          }}
        >
          {icon}
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {status === 'normal' &&
              `当前系统全局使用模型：${providerName} / ${modelName} —— 全局默认生效`}
            {status === 'fallback' &&
              `配置文件中 ai 块缺失或模型不可用，系统已自动使用推荐模型：${providerName} / ${modelName}。请确认或更换。`}
            {status === 'no_available' &&
              '未配置任何可用模型，所有会话将无法调用 LLM。请先添加 Provider。'}
          </span>
          {status === 'normal' && (
            <Tag color="blue" style={{ fontSize: FontSize.SECONDARY }}>
              使用中
            </Tag>
          )}
        </div>
        <div
          style={{
            fontSize: FontSize.PRIMARY,
            fontWeight: FontWeight.BOLD,
            marginBottom: capabilities.length ? Spacing.SM : Spacing.MD,
          }}
        >
          {providerName && modelName
            ? `${providerName} / ${modelName}`
            : '（无）'}
        </div>
        {capabilities.length > 0 && (
          <div style={{ marginBottom: Spacing.MD }}>
            {capabilities.map((c) => (
              <Tag
                key={c}
                style={{
                  fontSize: FontSize.SECONDARY,
                  marginRight: Spacing.SM,
                }}
              >
                {c}
              </Tag>
            ))}
          </div>
        )}
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginBottom: Spacing.MD,
          }}
        >
          全局默认：所有会话默认使用此模型；单个会话可另行覆盖（L2）
        </div>
        <div>
          {status === 'normal' && (
            <Button size="small" onClick={() => setSwitchOpen(true)}>
              更换模型 →
            </Button>
          )}
          {status === 'fallback' && (
            <Button
              size="small"
              type="primary"
              onClick={() => setSwitchOpen(true)}
            >
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
      <ModelSwitchModal
        open={switchOpen}
        providers={providers}
        currentProvider={providerName}
        currentModel={modelName}
        onOk={async (p, m) => {
          try {
            // 2026-09-21 小强 - 补 success 检查（对齐顶栏 handleModelChange）：后端校验失败回 HTTP200+success:false，
            //   不查就弹"模型已切换"假成功；失败弹错、不关框（后端未落盘，当前展示仍有效）
            const r = await configApi.updateConfig({
              ai_model_ref: { provider: p, model: m },
            });
            if (!r.success) {
              handleError({
                message: r.message || '切换失败',
                error_type: ErrorType.SWITCH_MODEL_FAILED,
              });
              return;
            }
            showSuccess('模型已切换');
            setSwitchOpen(false);
            onModelSwitched();
          } catch (e) {
            handleApiError(e);
          }
        }}
        onCancel={() => setSwitchOpen(false)}
      />
    </div>
  );
};
