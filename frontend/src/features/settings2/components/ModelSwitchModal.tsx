// 编辑历史: 2026-09-21 小欧 - 新建：更换模型独立弹框（通用区"更换模型 →"按钮触发）
// 编辑历史: 2026-10-10 小欧 - 弹窗归一 + 防连发：补 busy 态（切换模型要发 HTTP，原无防连发，
//   连点两下=发两次请求），失败不关窗（父级已弹错），成功由父级关。
// 2026-10-10 22:15 小欧 - 更正上一条不实记录并真正迁移：前次归一批次里，本文件被标为"已迁 SettingsModal"
//   并补了对应历史条目，但实际代码仍是裸 antd <Modal>（import { Modal }），归一未发生。
//   本次真正迁移到 SettingsModal，并落实视觉优化问题#17（见下）。
//   视觉优化#17：「当前生效 provider / model」是本次操作的影响预告（当前值 → 将变更），
//   原为裸灰字，与表单字段同权重，关键信息读不出来。改 ModalSection 容器 + CodeChip 键名。
import React, { useEffect, useState } from 'react';
import { Form, Select } from 'antd';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import { SettingsModal, ModalSection, CodeChip } from '@/theme/SettingsModal';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  open: boolean;
  providers: ProviderEntry[];
  currentProvider: string;
  currentModel: string;
  onOk: (provider: string, model: string) => void | Promise<void>;
  onCancel: () => void;
}

export const ModelSwitchModal: React.FC<Props> = ({
  open,
  providers,
  currentProvider,
  currentModel,
  onOk,
  onCancel,
}) => {
  const [selProvider, setSelProvider] = useState(currentProvider);
  const [selModel, setSelModel] = useState(currentModel);
  // 2026-10-10 小欧 - 审计修复：切换模型要发 HTTP，弹窗内原无防连发，
  //   连点两下=发两次请求。补 busy 态，失败不关窗（父级已弹错），成功由父级关。
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setSelProvider(currentProvider);
      setSelModel(currentModel);
    }
  }, [open, currentProvider, currentModel]);

  const providerModels =
    providers.find((p) => p.name === selProvider)?.models ?? [];

  return (
    <SettingsModal
      open={open}
      title="更换当前系统全局使用模型"
      description="选择新的 Provider 和模型，确认后立即生效"
      width="form"
      confirmLoading={busy}
      onCancel={onCancel}
      onOk={async () => {
        if (busy) return;
        setBusy(true);
        try {
          await onOk(selProvider, selModel);
        } finally {
          setBusy(false);
        }
      }}
      okText="确认更换"
      cancelText="取消"
    >
      <Form layout="vertical">
        <Form.Item label="Provider" required>
          <Select
            value={selProvider}
            onChange={(v) => {
              setSelProvider(v);
              setSelModel('');
            }}
          >
            {providers.map((p) => (
              <Select.Option key={p.name} value={p.name}>
                {p.label || p.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item label="模型" required style={{ marginBottom: 0 }}>
          <Select value={selModel || undefined} onChange={setSelModel}>
            {providerModels.map((m) => (
              <Select.Option key={m.name} value={m.name}>
                {m.label || m.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
      </Form>
      {/* 变更影响预告：容器化 + 键名等宽（问题#17） */}
      <ModalSection
        title="当前生效"
        hint="确认后将切换为"
        style={{ marginTop: Spacing.LG }}
      >
        <div style={{ display: 'flex', gap: Spacing.SM, flexWrap: 'wrap' }}>
          <CodeChip>{currentProvider}</CodeChip>
          <span style={{ color: Colors.TEXT.TERTIARY }}>/</span>
          <CodeChip>{currentModel}</CodeChip>
        </div>
      </ModalSection>
    </SettingsModal>
  );
};
