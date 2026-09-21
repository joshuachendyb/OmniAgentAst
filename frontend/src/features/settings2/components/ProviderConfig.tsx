// 编辑历史: 2026-09-20 小强 - 新建：Provider 配置区（统一表单；写走 PUT /providers 统一链 + mtime 同步，见 7.3.2/8.4.1）
// 编辑历史: 2026-09-20 小强 - v4.17 纠错：撤销内嵌 <ProviderSettings shouldLoad />——旧组件自带保存按钮直调旧 /config API，
//   内嵌会造成双真相源 + modelApi.updateProvider 死代码；改为读全局 providerConfig state、保存走 PUT /providers。
import React, { useState } from 'react';
import { Button, Input, InputNumber, Form } from 'antd';

interface Props {
  name: string;
  config: {
    api_key: { configured: boolean; suffix: string };
    base_url: string;
    timeout: number;
    retry_times?: number;
    env: boolean;
  };
  onSave: (patch: {
    api_key?: string;
    base_url?: string;
    timeout?: number;
    retry_times?: number;
    clear?: boolean;
  }) => Promise<void>;
}

export const ProviderConfig: React.FC<Props> = ({ name, config, onSave }) => {
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);
  // v4.19(P1-4/P1-5 修正)：isEnv 看 GET /models 下发的 config.env（与 config.py:99-102 _apply_env_overrides 同源判定），
  // 弃用旧 envOverride[name]（models[] 上无此标注，恒 false 的假死代码路径）
  const isEnv = config.env === true;
  const doSave = async () => {
    const values = await form.validateFields();
    const patch: Record<string, unknown> = {};
    // api_key 三态：留空/空白 = 保持原值（secret 契约，不提交覆盖）；填值 = 覆盖；clear=true = 显式清空
    if (values.api_key !== undefined && String(values.api_key).trim() !== '')
      patch.api_key = values.api_key;
    if (values.base_url !== undefined) patch.base_url = values.base_url;
    if (values.timeout !== undefined) patch.timeout = values.timeout;
    setSaving(true);
    try {
      await onSave(patch);
    } finally {
      setSaving(false);
    }
  };
  const doClear = async () => {
    setSaving(true);
    try {
      await onSave({ clear: true });
    } finally {
      setSaving(false);
    }
  };
  if (isEnv)
    return (
      <div>
        该 Provider 配置被 {name.toUpperCase()}_API_KEY 环境变量接管，页面只读。
      </div>
    );
  return (
    <Form
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
      {config.api_key.configured && (
        <Button type="link" disabled={saving} onClick={doClear}>
          清空 api_key
        </Button>
      )}
      <Button type="primary" htmlType="submit" loading={saving}>
        {'保存 Provider 配置（立即生效）'}
      </Button>
    </Form>
  );
};
