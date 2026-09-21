// 编辑历史: 2026-09-20 小强 - 新建：模型管理弹窗（添加模型/Provider + 删除确认含级联警告）
// 编辑历史: 2026-09-21 小强 - onSubmitAddModel 类型补齐 default_params?(Record<string, unknown>)——SettingsPage 提交处按参考扩展该字段，缺此声明 tsc 报错 — 小强-2026-09-21
// 编辑历史: 2026-09-21 小强 - 修复 BUG-A：mProvider 仅 useState 初始化一次，父级 selectedProvider 变化后弹窗仍指向旧 Provider（陈旧状态）；加 useEffect 联动
// 2026-09-21 小欧 - P0-9：添加 Provider 弹窗增 api_key 输入框（[58] P0-9）
// 2026-09-21 小欧 - 第六章①②③：弹窗视觉优化——描述行/danger/⚠/后果说明（[58] 第六章 6.2）
// 2026-09-21 小欧 - 全文逐章核查：①②表单弹窗显式 form 宽、③确认弹窗宽散落 480 → settingsModalWidth.form/confirm 令牌收口（[58] v1.12 第六章 6.1 规范一）
// 2026-09-21 小欧 - 全文逐章核查：规范二落地——①②③弹窗标题显式 fontSize:PRIMARY(14)+fontWeight:BOLD，弃用 antd 默认16px；描述行 marginBottom:12 → Spacing.LG（[58] v1.12 第六章 6.1 规范二）
// 2026-09-21 小强 - 设置页17问题复核修复：删除标题剥离 model:/provider: 内部前缀；添加弹窗 busy+confirmLoading 防连点双发、
//   失败不关窗不 reset（父级 rethrow）；onSubmitAddModel/Provider 类型改 Promise<void>（[设置页UI审计] 问题3/9）
import React, { useEffect, useState } from 'react';
import { Form, Input, Modal, Select } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsModalWidth } from '@/theme/settingsTokens';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  providers: ProviderEntry[];
  addModelOpen: boolean;
  addProviderOpen: boolean;
  deleteOpen: boolean;
  deleteTarget: string | null;
  selectedProvider: string;
  onCloseAddModel: () => void;
  onCloseAddProvider: () => void;
  onCloseDelete: () => void;
  onSubmitAddModel: (data: {
    provider: string;
    model: string;
    label: string;
    default_params?: Record<string, unknown>;
  }) => Promise<void>;
  onSubmitAddProvider: (data: {
    name: string;
    label: string;
    api_base: string;
    api_key?: string;
  }) => Promise<void>;
  onConfirmDelete: () => void;
}

export const ModelModals: React.FC<Props> = (props) => {
  const { providers, addModelOpen, addProviderOpen, deleteOpen, deleteTarget } =
    props;
  const [mForm] = Form.useForm();
  const [pForm] = Form.useForm();
  const [mProvider, setMProvider] = useState(props.selectedProvider);
  // 修正(2026-09-21 小强)：busy 态驱动 Modal confirmLoading 防连点双发（原 onOk 走 .then() 无 loading，
  // 双击触发两次提交）；失败父级 rethrow 不关窗，输入保留（[设置页UI审计] 问题9）
  const [busy, setBusy] = useState<'model' | 'provider' | null>(null);
  // 2026-09-21 BUG-A 修复：父级切换所选 Provider 时联动弹窗内 Provider 下拉，防陈旧值
  useEffect(() => {
    setMProvider(props.selectedProvider);
  }, [props.selectedProvider]);

  // 修正(2026-09-21 小强)：删除标题剥离 model:/provider: 内部前缀——原 deleteTarget 直接注入标题，
  // 显示 "model:openai::gpt-4o" 泄漏内部格式（[设置页UI审计] 问题3）
  const deleteLabel = (t: string | null): string => {
    if (!t) return '';
    const idx = t.indexOf(':');
    return idx > 0 ? t.slice(idx + 1) : t;
  };

  const handleAddModel = async () => {
    if (busy) return;
    const v = await mForm.validateFields().catch(() => null);
    if (!v) return;
    setBusy('model');
    try {
      await props.onSubmitAddModel({
        provider: mProvider,
        model: v.model,
        label: v.label ?? v.model,
      });
      mForm.resetFields();
    } catch {
      /* 保存失败：输入保留、弹窗不关（父级已弹错） */
    } finally {
      setBusy(null);
    }
  };

  const handleAddProvider = async () => {
    if (busy) return;
    const v = await pForm.validateFields().catch(() => null);
    if (!v) return;
    setBusy('provider');
    try {
      await props.onSubmitAddProvider(v);
      pForm.resetFields();
    } catch {
      /* 保存失败：输入保留、弹窗不关（父级已弹错） */
    } finally {
      setBusy(null);
    }
  };
  return (
    <>
      <Modal
        open={addModelOpen}
        title={
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            添加模型
          </span>
        }
        width={settingsModalWidth.form}
        confirmLoading={busy === 'model'}
        onCancel={props.onCloseAddModel}
        onOk={() => void handleAddModel()}
        okText="保存"
        cancelText="取消"
      >
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginBottom: Spacing.LG,
          }}
        >
          为指定 Provider 添加新模型，创建后可在①选择器中选用
        </div>
        <Form form={mForm} layout="vertical">
          <Form.Item label="Provider" required>
            <Select value={mProvider} onChange={setMProvider}>
              {providers.map((p) => (
                <Select.Option key={p.name} value={p.name}>
                  {p.label || p.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            name="model"
            label="模型名"
            rules={[{ required: true, message: '请输入模型名' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="label" label="显示名">
            <Input />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        open={addProviderOpen}
        title={
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            添加 Provider
          </span>
        }
        width={settingsModalWidth.form}
        confirmLoading={busy === 'provider'}
        onCancel={props.onCloseAddProvider}
        onOk={() => void handleAddProvider()}
        okText="保存"
        cancelText="取消"
      >
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginBottom: Spacing.LG,
          }}
        >
          创建后可在③Provider配置区修改 API Key / API 地址
        </div>
        <Form form={pForm} layout="vertical">
          <Form.Item
            name="name"
            label="名称"
            rules={[{ required: true, message: '请输入名称' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item name="label" label="显示名">
            <Input />
          </Form.Item>
          <Form.Item name="api_base" label="API 地址">
            <Input />
          </Form.Item>
          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="未配置则留空" />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        open={deleteOpen}
        title={
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >{`⚠ 确定要删除 "${deleteLabel(deleteTarget)}"？`}</span>
        }
        onCancel={props.onCloseDelete}
        onOk={() => void props.onConfirmDelete()}
        okText="删除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
        width={settingsModalWidth.confirm}
      >
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          警告：如果这是当前使用的模型，将自动切换为默认模型；删除 Provider
          将级联删除其下所有模型！
        </span>
      </Modal>
    </>
  );
};
