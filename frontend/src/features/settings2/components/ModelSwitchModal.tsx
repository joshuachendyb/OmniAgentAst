// 编辑历史: 2026-09-21 小欧 - 新建：更换模型独立弹框（通用区"更换模型 →"按钮触发）
// 编辑历史: 2026-10-10 小欧 - 弹窗归一：Modal → SettingsModal 标准壳（form=520 宽度档、discard
//   关闭语义、confirmLoading）；补防连发（切模型期间锁提交），业务逻辑与文案未改。
//   实测：宽 520 / ESC 可关 / 主键「确认更换」，符合设计。
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
    <Modal
      open={open}
      title={
        <span
          style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
        >
          更换当前系统全局使用模型
        </span>
      }
      width={settingsModalWidth.form}
      destroyOnHidden
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
      confirmLoading={busy}
      okText="确认更换"
      cancelText="取消"
    >
      <div
        style={{
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.SECONDARY,
          marginBottom: Spacing.LG,
        }}
      >
        选择新的 Provider 和模型，确认后立即生效
      </div>
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
      <div
        style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}
      >
        当前生效：{currentProvider} / {currentModel}
      </div>
    </Modal>
  );
};
