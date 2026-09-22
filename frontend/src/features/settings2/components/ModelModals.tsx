// 编辑历史: 2026-09-20 小强 - 新建：模型管理弹窗（添加模型/Provider + 删除确认含级联警告）
// 编辑历史: 2026-09-21 小强 - onSubmitAddModel 类型补齐 default_params?(Record<string, unknown>)——SettingsPage 提交处按参考扩展该字段，缺此声明 tsc 报错 — 小强-2026-09-21
// 编辑历史: 2026-09-21 小强 - 修复 BUG-A：mProvider 仅 useState 初始化一次，父级 selectedProvider 变化后弹窗仍指向旧 Provider（陈旧状态）；加 useEffect 联动
// 2026-09-21 小欧 - P0-9：添加 Provider 弹窗增 api_key 输入框（[58] P0-9）
// 2026-09-21 小欧 - 第六章①②③：弹窗视觉优化——描述行/danger/⚠/后果说明（[58] 第六章 6.2）
// 2026-09-21 小欧 - 全文逐章核查：①②表单弹窗显式 form 宽、③确认弹窗宽散落 480 → settingsModalWidth.form/confirm 令牌收口（[58] v1.12 第六章 6.1 规范一）
// 2026-09-21 小欧 - 全文逐章核查：规范二落地——①②③弹窗标题显式 fontSize:PRIMARY(14)+fontWeight:BOLD，弃用 antd 默认16px；描述行 marginBottom:12 → Spacing.LG（[58] v1.12 第六章 6.1 规范二）
// 2026-09-21 小强 - 设置页17问题复核修复：删除标题剥离 model:/provider: 内部前缀；添加弹窗 busy+confirmLoading 防连点双发、
//   失败不关窗不 reset（父级 rethrow）；onSubmitAddModel/Provider 类型改 Promise<void>（[设置页UI审计] 问题3/9）
// 2026-09-22 小欧 - [62]P5 3.3(1)+3.3(2)：添加模型弹窗加「参数模板」区——候选=所选Provider兄弟模型
//   default_params∪param_options key 并集；勾选即带入默认值（兄弟default_params，reasoning_effort→medium兜底），
//   控件按 opts→Select/数字→InputNumber/其他→Input；切Provider重算清空；成功重置。
//   Props onSubmitAddModel 加 range?/capabilities?/param_options?；handleAddModel 透传 collected.{params,options}
// 2026-09-22 小欧 - [62]P5 E2E-01 抓真bug修复：勾选行有兄弟 param_options 时, 仅写 collected.params 而 options 恒空
//   → handleAddModel 的 param_options 永远空 → 新模型 model_meta 不落 options → 回显无下拉。
//   修复：勾选时若 opts 存在同步带 options[key]=opts, 取消则删（POST 体含 param_options + config.yaml 落盘 + 回显下拉验证通过）
// 2026-09-22 小欧 - [62]P6 4.3(5)：onSubmitAddProvider Props 加 timeout?/max_retries?；添加 Provider
//   弹窗表单 api_key 后新增 timeout(秒) min1 默认60占位、max_retries min0 默认3占位两个 InputNumber
//   （配合 model.api.ts addProvider 入参补两字段，创建时即可自定义超时/重试）
import React, { useEffect, useState } from 'react';
import { Checkbox, Form, Input, InputNumber, Modal, Select } from 'antd';
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
    range?: Record<string, { min: number; max: number }>;
    capabilities?: string[];
    param_options?: Record<string, string[]>;
  }) => Promise<void>;
  onSubmitAddProvider: (data: {
    name: string;
    label: string;
    api_base: string;
    api_key?: string;
    timeout?: number;
    max_retries?: number;
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

  // [62]P5 3.3(1) 模板区：候选 = 所选 Provider 已有模型 default_params ∪ param_options key 并集
  const sibModels = providers.find((p) => p.name === mProvider)?.models ?? [];
  const candKeys = Array.from(
    new Set(
      sibModels.flatMap((m) => [
        ...Object.keys(m.default_params ?? {}),
        ...Object.keys(m.param_options ?? {}),
      ])
    )
  );
  // 勾选状态 + 值收集（勾中才送后端，未勾不送该 key——与现状 {} 兼容）
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [collected, setCollected] = useState<{
    params: Record<string, unknown>;
    options: Record<string, string[]>;
  }>({ params: {}, options: {} });
  // 切 Provider 重算候选并清空已勾（与 BUG-A 的 mProvider 联动放一处）
  useEffect(() => {
    setChecked({});
    setCollected({ params: {}, options: {} });
  }, [mProvider]);

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
      // [62]P5 3.3(2)-b：模板区勾选项由 collected.{params,options} 供给——勾了才送，未勾不送该 key
      await props.onSubmitAddModel({
        provider: mProvider,
        model: v.model,
        label: v.label ?? v.model,
        ...(Object.keys(collected.params).length
          ? { default_params: collected.params }
          : {}),
        ...(Object.keys(collected.options).length
          ? { param_options: collected.options }
          : {}),
      });
      mForm.resetFields();
      // [62]P5 3.3(1) 成功重置模板区勾选/收集
      setChecked({});
      setCollected({ params: {}, options: {} });
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
          {/* [62]P5 3.3(1) 参数模板：勾选即带入，候选=兄弟模型 default_params ∪ param_options key 并集 */}
          {candKeys.length > 0 && (
            <div
              style={{
                borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
                paddingTop: Spacing.MD,
                marginTop: Spacing.MD,
              }}
            >
              <div
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.SECONDARY,
                  marginBottom: Spacing.MD,
                }}
              >
                参数模板（勾选即带入新模型）
              </div>
              {candKeys.map((key) => {
                const opts = sibModels[0]?.param_options?.[key];
                const siblingValue = sibModels[0]?.default_params?.[key];
                const defaultVal =
                  collected.params[key] ??
                  siblingValue ??
                  (key === 'reasoning_effort' ? 'medium' : undefined);
                return (
                  <div
                    key={key}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: Spacing.MD,
                      marginBottom: Spacing.SM,
                    }}
                  >
                    <Checkbox
                      checked={!!checked[key]}
                      onChange={(e) => {
                        const next = { ...checked, [key]: e.target.checked };
                        setChecked(next);
                        const params = { ...collected.params };
                        const options = { ...collected.options };
                        if (e.target.checked) {
                          // 勾选即带入当前默认值（不含则保持未送）
                          if (defaultVal !== undefined)
                            params[key] = defaultVal;
                          // 兄弟有枚举则一并带入新模型（回显下拉）
                          if (opts) options[key] = opts;
                        } else {
                          delete params[key];
                          delete options[key];
                        }
                        setCollected({ ...collected, params, options });
                      }}
                    >
                      {key}
                    </Checkbox>
                    {opts ? (
                      <Select
                        value={
                          typeof defaultVal === 'string'
                            ? defaultVal
                            : String(defaultVal ?? '')
                        }
                        options={opts.map((v) => ({ label: v, value: v }))}
                        style={{ minWidth: 160 }}
                        onChange={(v) =>
                          checked[key] &&
                          setCollected({
                            ...collected,
                            params: { ...collected.params, [key]: v },
                          })
                        }
                      />
                    ) : typeof defaultVal === 'number' ? (
                      <InputNumber
                        value={defaultVal as number}
                        style={{ minWidth: 160 }}
                        onChange={(v) =>
                          checked[key] &&
                          setCollected({
                            ...collected,
                            params: { ...collected.params, [key]: v },
                          })
                        }
                      />
                    ) : (
                      <Input
                        value={
                          defaultVal !== undefined ? String(defaultVal) : ''
                        }
                        style={{ maxWidth: 240 }}
                        onChange={(e) =>
                          checked[key] &&
                          setCollected({
                            ...collected,
                            params: {
                              ...collected.params,
                              [key]: e.target.value,
                            },
                          })
                        }
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}
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
          {/* [62]P6 4.3(5) 创建 Provider 可自定义 timeout/max_retries（后端 DTO 默认 60/3，留空走默认） */}
          <Form.Item label="timeout(秒)" name="timeout">
            <InputNumber min={1} placeholder="默认60" />
          </Form.Item>
          <Form.Item label="max_retries" name="max_retries">
            <InputNumber min={0} placeholder="默认3" />
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
