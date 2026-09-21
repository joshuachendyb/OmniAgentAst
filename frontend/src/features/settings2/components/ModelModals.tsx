// 编辑历史: 2026-09-20 小强 - 新建：模型管理弹窗（添加模型/Provider + 删除确认含级联警告）
// 编辑历史: 2026-09-21 小强 - onSubmitAddModel 类型补齐 default_params?(Record<string, unknown>)——SettingsPage 提交处按参考扩展该字段，缺此声明 tsc 报错 — 小强-2026-09-21
// 编辑历史: 2026-09-21 小强 - 修复 BUG-A：mProvider 仅 useState 初始化一次，父级 selectedProvider 变化后弹窗仍指向旧 Provider（陈旧状态）；加 useEffect 联动
import React, { useEffect, useState } from 'react';
import { Form, Input, Modal, Select } from 'antd';
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
  }) => void;
  onSubmitAddProvider: (data: {
    name: string;
    label: string;
    api_base: string;
  }) => void;
  onConfirmDelete: () => void;
}

export const ModelModals: React.FC<Props> = (props) => {
  const { providers, addModelOpen, addProviderOpen, deleteOpen, deleteTarget } =
    props;
  const [mForm] = Form.useForm();
  const [pForm] = Form.useForm();
  const [mProvider, setMProvider] = useState(props.selectedProvider);
  // 2026-09-21 BUG-A 修复：父级切换所选 Provider 时联动弹窗内 Provider 下拉，防陈旧值
  useEffect(() => {
    setMProvider(props.selectedProvider);
  }, [props.selectedProvider]);
  return (
    <>
      <Modal
        open={addModelOpen}
        title="添加模型"
        onCancel={props.onCloseAddModel}
        onOk={() =>
          mForm.validateFields().then((v) => {
            props.onSubmitAddModel({
              provider: mProvider,
              model: v.model,
              label: v.label ?? v.model,
            });
            mForm.resetFields();
          })
        }
        okText="保存"
        cancelText="取消"
      >
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
        title="添加 Provider"
        onCancel={props.onCloseAddProvider}
        onOk={() =>
          pForm.validateFields().then((v) => {
            props.onSubmitAddProvider(v);
            pForm.resetFields();
          })
        }
        okText="保存"
        cancelText="取消"
      >
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
        </Form>
      </Modal>
      <Modal
        open={deleteOpen}
        title={`确定要删除 "${deleteTarget ?? ''}"？`}
        onCancel={props.onCloseDelete}
        onOk={props.onConfirmDelete}
        okText="删除"
        okButtonProps={{ danger: true }}
        cancelText="取消"
      >
        警告：如果这是当前使用的模型，将自动切换为默认模型；删除 Provider
        将级联删除其下所有模型！
      </Modal>
    </>
  );
};
