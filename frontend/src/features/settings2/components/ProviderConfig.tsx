// 编辑历史: 2026-09-20 小强 - 新建：Provider 配置区（统一表单；写走 PUT /providers 统一链 + mtime 同步，见 7.3.2/8.4.1）
// 编辑历史: 2026-09-20 小强 - v4.17 纠错：撤销内嵌 <ProviderSettings shouldLoad />——旧组件自带保存按钮直调旧 /config API，
//   内嵌会造成双真相源 + modelApi.updateProvider 死代码；改为读全局 providerConfig state、保存走 PUT /providers。
// 2026-09-21 小欧 - P2-6：isEnv 时渲染 EnvTag + 警示文案（[58] P2-6）
// 2026-09-21 小欧 - P2-7：清空 api_key 按钮改 danger + 间距分隔（[58] P2-7）
// 2026-09-21 小欧 - V-1：base_url 留空=保持原值，与 api_key 语义对齐（[58] V-1）
// 2026-09-21 小欧 - 重组区块：清空api_key移入操作区，保存按钮限宽（方案C）
// 2026-09-21 小欧 - 补 max_retries：config 类型+表单字段+doSave patch 全链路补齐（后端 update_provider_config 支持 max_retries 键）
// 2026-09-21 小强 - 切 provider 表单值不跟随修复：Form 加 key={name} 重挂刷新（initialValues 只在挂载生效；KISS-DIRECT 一行直解，不加 effect 链条，北京老陈定）
import React, { useState } from 'react';
import { Button, Input, InputNumber, Form } from 'antd';
import { Colors } from '@/utils/stepStyles';
import { EnvTag } from './icons';

interface Props {
  name: string;
  config: {
    api_key: { configured: boolean; suffix: string };
    base_url: string;
    timeout: number;
    max_retries: number;
    retry_times?: number;
    env: boolean;
  };
  onSave: (patch: {
    api_key?: string;
    base_url?: string;
    timeout?: number;
    retry_times?: number;
    max_retries?: number;
    clear?: boolean;
  }) => Promise<void>;
}

export const ProviderConfig: React.FC<Props> = ({ name, config, onSave }) => {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  const isEnv = config.env === true;
  const doSave = async () => {
    const values = await form.validateFields();
    const patch: Record<string, unknown> = {};
    if (values.api_key !== undefined && String(values.api_key).trim() !== '')
      patch.api_key = values.api_key;
    if (values.base_url !== undefined && String(values.base_url).trim() !== '')
      patch.base_url = values.base_url;
    if (values.timeout !== undefined) patch.timeout = values.timeout;
    if (values.max_retries !== undefined)
      patch.max_retries = values.max_retries;
    setSaving(true);
    try {
      await onSave(patch);
    } finally {
      setSaving(false);
    }
  };

  if (isEnv)
    return (
      <div>
        <EnvTag />
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          该 Provider 配置被 {name.toUpperCase()}_API_KEY
          环境变量接管，页面只读。
        </span>
      </div>
    );
  return (
    <Form
      key={name}
      form={form}
      layout="horizontal"
      initialValues={{ ...config, api_key: undefined }}
      onFinish={doSave}
    >
      <Form.Item
        label="api_key"
        name="api_key"
        extra={
          config.api_key.configured
            ? `已配置（末4位 ${config.api_key.suffix}），留空=保持原值`
            : '未配置，留空=保持原值'
        }
      >
        <Input.Password
          placeholder={
            config.api_key.configured ? '已配置，留空保持原值' : '未配置'
          }
          autoComplete="new-password"
        />
      </Form.Item>
      <Form.Item label="base_url" name="base_url">
        <Input />
      </Form.Item>
      <Form.Item label="timeout" name="timeout">
        <InputNumber min={1} />
      </Form.Item>
      <Form.Item label="max_retries" name="max_retries">
        <InputNumber min={0} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={saving}>
          保存 Provider 配置（立即生效）
        </Button>
      </Form.Item>
    </Form>
  );
};
