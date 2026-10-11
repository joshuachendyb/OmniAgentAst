// 编辑历史: 2026-09-21 小欧 - 新建：当前生效模型高占位状态卡（三态：正常/兜底推荐/无可用）
// 2026-09-21 小欧 - 核查修复：硬编码琥珀色→Colors.BG.WARNING_LIGHT/Colors.WARNING 令牌（设计文档 v1.11）
// 2026-09-21 小欧 - 全文核查：补 capabilities tags、"使用中"徽标、S2/S3 文案对齐、来源徽标点击说明（设计文档 v1.12）
// 2026-09-21 小欧 - 更换模型独立弹框：按钮改为打开 ModelSwitchModal，不再跳转模型Tab
// 2026-09-21 小欧 - 标题改为"当前系统全局使用模型"并移到卡片边框上方；删未使用的 Popover 导入
// 2026-09-21 小强 - 补 success 检查对齐顶栏：后端校验失败回 HTTP200+success:false，不查则假成功 toast（北京老陈定）
// 2026-09-21 小强 - DRY收口：onOk改经configApi.switchCurrentModel调共用切全局模型唯一写链
// 2026-09-24 18:56:06 小欧 - 修顶栏下拉不刷新：切全局模型成功后补调 AppContext.refreshModelList()，使顶栏收起态带★即时更新（对齐顶栏 handleModelChange 路径）
// 2026-09-24 19:15:58 小欧 - DRY收口：onOk改经AppContext.switchAndRefreshModel(API+刷新收口), 删configApi直调与手动refreshAfterModelChange — 小欧-2026-09-24
// 编辑历史: 2026-10-11 00:18:37 小欧 - 设置页视觉密度统一之模型卡去重排: 模型名/标题/全局默认三组重复只留一处; 「更换模型」提至标题行右侧(动作贴对象); 能力/作用改 label:value 定宽对齐; 状态文字仅异常态出现; 「使用中」Tag 改小圆点+文字 — 小欧-2026-10-11
import React, { useState } from 'react';
import { Button, Tag } from 'antd';
import {
  CheckCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsRadius } from '@/theme/settingsTokens';
import {
  handleApiError,
  handleError,
  showSuccess,
  ErrorType,
} from '@/services/error/handler';
import { useApp } from '@/contexts/AppContext';
import { ModelSwitchModal } from './ModelSwitchModal';
import type { SessionModelOverride } from '@/types/chat';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  currentRef: SessionModelOverride | null;
  providers: ProviderEntry[];
  onModelSwitched: () => void;
  onAddProvider: () => void;
}

/** 2026-10-10 23:58 小欧 - label:value 行样式单点（能力/作用两行复用，DRY） */
const metaRowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'baseline',
  gap: Spacing.MD,
  marginTop: Spacing.SM,
};

/** 左标签定宽：中文标签（能力/作用）等宽，右侧内容起于同一 x，中英混排不参差 */
const metaLabelStyle: React.CSSProperties = {
  width: 28,
  flexShrink: 0,
  fontSize: FontSize.SECONDARY,
  color: Colors.TEXT.TERTIARY,
};

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
  const { switchAndRefreshModel } = useApp();
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
      {/* 2026-10-10 23:58 小欧 - 卡片重排（人类设计师单一信息源原则）。
          改前实测的冗余：normal 态下 `provider / model` 出现在 2 处（状态说明行 + 大标题行）、
          「当前系统全局使用模型」出现在 2 处（区块标题 + 状态说明行）、
          「全局默认」出现在 2 处（"—— 全局默认生效" + "全局默认：所有会话…"）。
          三组重复让一个只有 1 条事实的卡片占了 200px 高、读三遍才拼出完整信息。
          现改为：
            ① 模型名只出现一次（标题行，粗体，与状态图标同行）；
            ② 「更换模型」从卡片左下角提到区块标题行右侧——动作和它所作用的标题同处一行，
               符合"动作贴着对象"原则，也省掉一行垂直空间；
            ③ 能力/作用改 label:value 两行对齐，左标签固定宽，中文与英文混排时不参差；
            ④ 状态文字只在异常态出现（normal 态有"使用中"即可，再写一遍是废话）；
            ⑤ 「使用中」Tag 框 → 小圆点 + 文字，不为一个词占一个带边框的盒子。 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: Spacing.SM,
        }}
      >
        <span
          style={{
            fontSize: FontSize.PRIMARY,
            fontWeight: FontWeight.BOLD,
          }}
        >
          当前系统全局使用模型
        </span>
        {status === 'normal' && (
          <Button size="small" onClick={() => setSwitchOpen(true)}>
            更换模型
          </Button>
        )}
        {status === 'fallback' && (
          <Button size="small" type="primary" onClick={() => setSwitchOpen(true)}>
            去选择
          </Button>
        )}
        {status === 'no_available' && (
          <Button size="small" type="primary" danger onClick={onAddProvider}>
            添加 Provider
          </Button>
        )}
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
        {/* 主值行：图标 + 模型名（全卡唯一一次）+ 状态点 */}
        <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.MD }}>
          {icon}
          <span
            style={{
              fontSize: FontSize.PRIMARY,
              fontWeight: FontWeight.BOLD,
              color: Colors.TEXT.STRONG,
            }}
          >
            {providerName && modelName ? `${providerName} / ${modelName}` : '（无）'}
          </span>
          {status === 'normal' && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 4,
                fontSize: FontSize.SECONDARY,
                color: Colors.TEXT.SECONDARY,
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  background: Colors.PRIMARY,
                }}
              />
              使用中
            </span>
          )}
        </div>

        {/* 异常态专属说明：normal 态不需要（模型名 + 使用中 已说清），写在这里是重复表达 */}
        {(status === 'fallback' || status === 'no_available') && (
          <div
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
              marginTop: Spacing.SM,
            }}
          >
            {status === 'fallback'
              ? '配置文件中 ai 块缺失或模型不可用，系统已自动使用推荐模型。请确认或更换。'
              : '未配置任何可用模型，所有会话将无法调用 LLM。请先添加 Provider。'}
          </div>
        )}

        {/* label:value 两行：左标签定宽，右内容对齐，中英混排不参差 */}
        {capabilities.length > 0 && (
          <div style={{ ...metaRowStyle, marginTop: Spacing.MD }}>
            <span style={metaLabelStyle}>能力</span>
            <span>
              {capabilities.map((c) => (
                <Tag
                  key={c}
                  style={{ fontSize: FontSize.SECONDARY, marginRight: Spacing.SM }}
                >
                  {c}
                </Tag>
              ))}
            </span>
          </div>
        )}
        <div style={metaRowStyle}>
          <span style={metaLabelStyle}>作用</span>
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            所有会话默认使用此模型；单个会话可另行覆盖（L2）
          </span>
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
            // 2026-09-24 小欧 - DRY收口: 改经switchAndRefreshModel(API+成功/失败刷新收口), 不再直调configApi+手动refreshAfterModelChange
            const r = await switchAndRefreshModel(p, m);
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
