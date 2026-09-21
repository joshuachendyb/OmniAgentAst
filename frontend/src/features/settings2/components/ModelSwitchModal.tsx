// 编辑历史: 2026-09-21 小欧 - 新建：更换模型独立弹框（通用区"更换模型 →"按钮触发）
import React, { useEffect, useState } from 'react';
import { Form, Modal, Select } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsModalWidth } from '@/theme/settingsTokens';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  open: boolean;
  providers: ProviderEntry[];
  currentProvider: string;
  currentModel: string;
  onOk: (provider: string, model: string) => void;
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

  useEffect(() => {
    if (open) {
      setSelProvider(currentProvider);
      setSelModel(currentModel);
    }
  }, [open, currentProvider, currentModel]);

  const providerModels = providers
    .find((p) => p.name === selProvider)
    ?.models ?? [];

  return (
    <Modal
      open={open}
      title={<span style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}>更换当前系统全局使用模型</span>}
      width={settingsModalWidth.form}
      onCancel={onCancel}
      onOk={() => onOk(selProvider, selModel)}
      okText="确认更换"
      cancelText="取消"
    >
      <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY, marginBottom: Spacing.LG }}>
        选择新的 Provider 和模型，确认后立即生效
      </div>
      <Form layout="vertical">
        <Form.Item label="Provider" required>
          <Select value={selProvider} onChange={(v) => { setSelProvider(v); setSelModel(''); }}>
            {providers.map((p) => (
              <Select.Option key={p.name} value={p.name}>
                {p.label || p.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        <Form.Item label="模型" required>
          <Select value={selModel || undefined} onChange={setSelModel}>
            {providerModels.map((m) => (
              <Select.Option key={m.name} value={m.name}>
                {m.label || m.name}
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
      </Form>
      <div style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}>
        当前生效：{currentProvider} / {currentModel}
      </div>
    </Modal>
  );
};
