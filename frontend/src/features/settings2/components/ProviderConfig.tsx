// 2026-09-20 小强 - 新建：Provider 配置区（统一表单；写走 PUT /providers 统一链 + mtime 同步，见 7.3.2/8.4.1）
// 编辑历史: 2026-09-20 小强 - v4.17 纠错：撤销内嵌 <ProviderSettings shouldLoad />——旧组件自带保存按钮直调旧 /config API，
//   内嵌会造成双真相源 + modelApi.updateProvider 死代码；改为读全局 providerConfig state、保存走 PUT /providers。
// 2026-09-21 小欧 - P2-6：isEnv 时渲染 EnvTag + 警示文案（[58] P2-6）
// 2026-09-21 小欧 - P2-7：清空 api_key 按钮改 danger + 间距分隔（[58] P2-7）
// 2026-09-21 小欧 - V-1：base_url 留空=保持原值，与 api_key 语义对齐（[58] V-1）
// 2026-09-21 小欧 - 重组区块：清空api_key移入操作区，保存按钮限宽（方案C）
// 2026-09-21 小欧 - 补 max_retries：config 类型+表单字段+doSave patch 全链路补齐（后端 update_provider_config 支持 max_retries 键）
// 2026-09-21 小强 - 切 provider 表单值不跟随修复：Form 加 key={name} 重挂刷新（initialValues 只在挂载生效；KISS-DIRECT 一行直解，不加 effect 链条，北京老陈定）
// 2026-09-21 小强 - 修正：内层 key 证伪（rc-field-form 源码：setInitialValues merge(新值,旧仓库)旧赢+默认preserve不清仓，form 实例常驻则重挂无效）；key 上移调用方，删内层冗余 key（北京老陈定）
// 2026-09-21 小强 - 设置页17问题复核修复：base_url 留空=清空（后端支持空串落盘api_base=''）；保存成功复位 api_key
//   防明文残留二次重复提交（失败父级 rethrow 保留输入）；env 接管补解除指引（[设置页UI审计] 问题5/6/14）
// 2026-09-22 小欧 - [62]P6 4.3(6)：label 显示名编辑入口——Props.config 加 label、onSave patch 加 label?、
//   doSave 收集（非空 trim 留空=保持原值）、表单 base_url 后加「显示名」Input（后端 key_map/DTO 早已支持，
//   前端补入口即闭环）；types/useSettings/SettingsPage 三文件同批联动
// 2026-09-22 小欧 - [62]P8 4.3(9)-3-c：①Props.config 加 param_types + [key:string]:unknown 动态索引、
//   onSave patch 加动态索引；②doSave 动态收集循环（param_types 非静态 keys、values[k]!==undefined 送 patch）；
//   ③渲染区加动态字段（param_types 除已硬编码字段外，number→InputNumber/boolean→Switch/string→Input，
//   值回填走 initialValues 天然生效）——rate_limit 等新参数前端零改代码。
// 2026-09-22 小欧 - 控件宽度统一：api_key/base_url 使用 apiKeyWidth/baseUrlWidth(360px)令牌；显示名/timeout/max_retries 使用 inputWidth/inputNumberWidth(240px)令牌 - 小欧-2026-09-22
// 2026-09-22 小欧 - 布局对齐：Form labelCol 固定宽度对齐 SettingRow 的 labelWidth - 小欧-2026-09-22
import React, { useState } from 'react';
import { Button, Input, InputNumber, Form, Switch } from 'antd';
import { Colors } from '@/utils/stepStyles';
import { settingsControl, settingsSpacing } from '@/theme/settingsTokens';
import { EnvTag } from './icons';

// 2026-09-22 小欧 - [62]P8 4.3(9)-3-c：动态字段渲染 skip 已有硬编码字段（api_key/base_url/label/timeout/max_retries）
const EXISTING_KEYS = new Set([
  'api_key',
  'base_url',
  'label',
  'timeout',
  'max_retries',
]);
// 2026-09-22 小欧 - [62]P8 4.3(9)-3-c：doSave 动静态字段分界——静态字段（timeout/max_retries）已在
//  onSave patch 显式收集，动态循环跳过它们避免重复/类型偏差
const STATIC_KEYS = new Set([
  'api_key',
  'base_url',
  'label',
  'timeout',
  'max_retries',
]);

interface Props {
  name: string;
  config: {
    api_key: { configured: boolean; suffix: string };
    base_url: string;
    label: string;
    timeout: number;
    max_retries: number;
    retry_times?: number;
    env: boolean;
    // 2026-09-22 小欧 - [62]P8 4.3(9)：param_types 元数据（动态字段 schema 源）——只渲染不定义
    param_types?: Record<
      string,
      { type: string; label: string; min?: number; default?: unknown }
    >;
    // 2026-09-22 小欧 - [62]P8 4.3(9)：动态参数值（rate_limit 等）——useSettings 透传后表单回填
    [key: string]: unknown;
  };
  onSave: (patch: {
    api_key?: string;
    base_url?: string;
    label?: string;
    timeout?: number;
    retry_times?: number;
    max_retries?: number;
    clear?: boolean;
    // 2026-09-22 小欧 - [62]P8 4.3(9)：动态字段收容（rate_limit 等 param_types 驱动）
    [key: string]: unknown;
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
    // 修正(2026-09-21 小强)：base_url 留空=清空——原空串被跳过导致地址无法删除回退默认（[设置页UI审计] 问题5）；
    // 后端 update_provider_config 对空串落盘 api_base=''，前端 model_dump(exclude_none=True) 不丢空串
    if (values.base_url !== undefined)
      patch.base_url = String(values.base_url).trim();
    // [62]P6 4.3(6) label：非空才送（留空=保持原值，与后端 update_provider_config label 语义一致）
    if (values.label !== undefined && String(values.label).trim() !== '')
      patch.label = String(values.label).trim();
    if (values.timeout !== undefined) patch.timeout = values.timeout;
    if (values.max_retries !== undefined)
      patch.max_retries = values.max_retries;
    // 2026-09-22 小欧 - [62]P8 4.3(9)-3-c：动态参数收集——现有静态字段 skip，param_types 里其余
    // 字段值非 undefined 送 patch（rate_limit 等新参数保存闭环；undefined=未填写不发送）
    for (const k of Object.keys(config.param_types ?? {})) {
      if (STATIC_KEYS.has(k)) continue;
      if (values[k] !== undefined) patch[k] = values[k];
    }
    setSaving(true);
    try {
      await onSave(patch);
      // 修正(2026-09-21 小强)：保存成功复位 api_key 输入——原明文残留 form store，
      // 二次保存会把上次明文 key 重复提交（[设置页UI审计] 问题6）；失败则保留输入
      form.resetFields(['api_key']);
    } catch {
      /* 保存失败：保留输入 */
    } finally {
      setSaving(false);
    }
  };

  if (isEnv)
    return (
      <div>
        <EnvTag />
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          {/* 修正(2026-09-21 小强)：补解除接管指引，原仅"页面只读"无任何方向（[设置页UI审计] 问题14） */}
          该 Provider 配置被 {name.toUpperCase()}_API_KEY
          环境变量接管，页面只读。如需解除，请删除该环境变量后重启后端。
        </span>
      </div>
    );
  return (
    <Form
      form={form}
      layout="horizontal"
      labelCol={{ style: { width: settingsSpacing.labelWidth } }}
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
          style={{ width: settingsControl.apiKeyWidth }}
        />
      </Form.Item>
      <Form.Item
        label="base_url"
        name="base_url"
        extra="留空=清空地址（恢复默认直连）"
      >
        <Input style={{ width: settingsControl.baseUrlWidth }} />
      </Form.Item>
      {/* [62]P6 4.3(6) label 显示名编辑入口（后端 key_map label→label + DTO label 字段早已支持，
          原来前端无入口，配置区改不了显示名；留空=保持原值） */}
      <Form.Item
        label="显示名"
        name="label"
        extra="Provider 显示名称，留空=保持原值"
      >
        <Input style={{ width: settingsControl.inputWidth }} />
      </Form.Item>
      <Form.Item label="timeout" name="timeout">
        <InputNumber min={1} style={{ width: settingsControl.inputNumberWidth }} />
      </Form.Item>
      <Form.Item label="max_retries" name="max_retries">
        <InputNumber min={0} style={{ width: settingsControl.inputNumberWidth }} />
      </Form.Item>
      {/* 2026-09-22 小欧 - [62]P8 4.3(9)-3-c：动态字段——param_types 中除已硬编码字段外的新参数
          （rate_limit 等元数据驱动，只渲染不定义；值回填走 initialValues 展开 config 天然生效） */}
      {Object.entries(config.param_types ?? {}).map(([key, meta]) =>
        EXISTING_KEYS.has(key) ? null : (
          <Form.Item key={key} label={meta.label} name={key}>
            {meta.type === 'number' ? (
              <InputNumber min={meta.min} style={{ width: settingsControl.inputNumberWidth }} />
            ) : meta.type === 'boolean' ? (
              <Switch />
            ) : (
              <Input style={{ width: settingsControl.inputWidth }} />
            )}
          </Form.Item>
        )
      )}
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={saving}>
          保存 Provider 配置（立即生效）
        </Button>
      </Form.Item>
    </Form>
  );
};
