// 编辑历史: 2026-09-22 小欧 - 新建：[62]P8 4.3(8) 管理选项弹窗——Tag 展示/添加/删除当前模型
//  param_options 选项列表；保存前交叉校验悬空默认值（defaults[key] 不在新列表 → Modal.confirm
//  同批回提 default_params 重置首项，复用后端 merge_nested_patch 同批合并零后端改动）。
// 2026-09-22 小欧 - KISS+令牌收口：`dangling && dangling !== undefined` 冗余判断 → `dangling`（truthy 即非 undefined）；marginBottom:4/marginTop:4/fontSize:12 裸数字 → Spacing.XS/FontSize.SECONDARY - 小欧-2026-09-22
// 2026-09-24 22:56:21 小欧 - BZ-5 闭环：加 disabled prop（保存中禁用「保存」提交+doSave 头部守卫）——
//   三堂会审发现外部 saveModelGroup saving 进行中弹窗仍可提交 param_options，与模型组保存并发写
//   同 YAML 不同字段（服务端非事务），快照错位同类风险；保存/取消关窗不改模型 state 不禁 - 小欧-2026-09-24
import React, { useState } from 'react';
import { Button, Input, Modal, Space, Tag } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsModalWidth } from '@/theme/settingsTokens';
import { modelApi } from '@/services/api/model.api';

interface Props {
  open: boolean;
  provider: string;
  model: string;
  // 当前模型三层解析后的 param_options（{reasoning_effort: ['low','medium','high'], ...}）
  paramOptions: Record<string, string[]>;
  // 当前模型 default_params（悬空值交叉校验数据源）
  defaults: Record<string, unknown>;
  onClose: () => void;
  // 保存成功后回调（父级刷新 paramOptions + defaults）
  onSaved: () => Promise<void> | void;
  // 2026-09-24 小欧 - BZ-5 闭环：保存中(saving) 禁用提交，防与模型组保存并发写 YAML 致快照错位 — 小欧-2026-09-24
  disabled?: boolean;
}

export const ParamOptionsModal: React.FC<Props> = ({
  open,
  provider,
  model,
  paramOptions,
  defaults,
  onClose,
  onSaved,
  disabled = false,
}) => {
  // 弹窗内工作副本（不直接改 state；确认/取消落定）
  const [draft, setDraft] = useState<Record<string, string[]>>({});
  // 每行添加输入框的值
  const [newValues, setNewValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  // open 变化时用最新 paramOptions 初始化 draft
  React.useEffect(() => {
    if (open) {
      setDraft(
        Object.fromEntries(
          Object.entries(paramOptions).map(([k, v]) => [k, [...v]])
        )
      );
      setNewValues({});
    }
  }, [open, paramOptions]);

  if (!open) return null;

  const addValue = (key: string) => {
    const v = (newValues[key] ?? '').trim();
    if (!v) return;
    if ((draft[key] ?? []).includes(v)) return; // 重复值禁止
    setDraft((d) => ({ ...d, [key]: [...(d[key] ?? []), v] }));
    setNewValues((n) => ({ ...n, [key]: '' }));
  };

  const removeValue = (key: string, val: string) => {
    setDraft((d) => ({ ...d, [key]: (d[key] ?? []).filter((x) => x !== val) }));
  };

  const toChangedKeys = (): string[] =>
    Object.keys(draft).filter(
      (k) => JSON.stringify(draft[k]) !== JSON.stringify(paramOptions[k] ?? [])
    );

  const doSave = async () => {
    // 2026-09-24 小欧 - BZ-5 闭环：保存中禁止提交（防与 saveModelGroup 并发写同 YAML 快照错位）— 小欧-2026-09-24
    if (disabled) return;
    // 保存前校验：每个参数至少保留 1 个值（空列表禁止）
    for (const k of Object.keys(draft)) {
      if (!draft[k] || draft[k].length === 0) {
        Modal.warning({
          title: `参数「${k}」不能为空`,
          content: '每个参数至少保留一个选项。',
        });
        return;
      }
    }
    // 悬空值交叉校验：defaults[key] 不在新列表 → confirm 同批回提 default_params 重置首项
    const dangling = toChangedKeys().find(
      (k) =>
        defaults[k] !== undefined &&
        defaults[k] !== null &&
        !(draft[k] ?? []).includes(String(defaults[k]))
    );
    if (dangling) {
      Modal.confirm({
        title: `默认值 ${dangling}='${String(defaults[dangling])}' 不在新选项内`,
        content: `将重置为该参数第一选项 '${(draft[dangling] ?? [])[0] ?? ''}'，继续？`,
        okText: '确认重置',
        cancelText: '取消',
        onOk: async () => {
          setSaving(true);
          try {
            await modelApi.updateModel(provider, model, {
              param_options: draft,
              default_params: {
                ...defaults,
                [dangling]: (draft[dangling] ?? [])[0],
              },
            });
            await onSaved();
            onClose();
          } finally {
            setSaving(false);
          }
        },
      });
      return;
    }
    // 无悬空：仅提交 param_options
    setSaving(true);
    try {
      await modelApi.updateModel(provider, model, { param_options: draft });
      await onSaved();
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      title={
        <span
          style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
        >
          管理 {model} 的参数选项
        </span>
      }
      width={settingsModalWidth.form}
      onCancel={onClose}
      onOk={doSave}
      okText="保存"
      cancelText="取消"
      confirmLoading={saving}
      // 2026-09-24 小欧 - BZ-5 闭环：外部 saving 时禁用 OK 按钮（视觉与守卫双保险）— 小欧-2026-09-24
      okButtonProps={{ disabled }}
    >
      {Object.keys(draft).length === 0 ? (
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          当前模型没有可管理的参数选项。
        </span>
      ) : (
        Object.entries(draft).map(([key, values]) => (
          <div key={key} style={{ marginBottom: Spacing.MD }}>
            <div
              style={{ fontWeight: FontWeight.BOLD, marginBottom: Spacing.XS }}
            >
              {key}
            </div>
            <Space wrap style={{ marginBottom: Spacing.XS }}>
              {(values ?? []).map((val) => (
                <Tag
                  key={val}
                  closable
                  onClose={(e) => {
                    e.preventDefault();
                    removeValue(key, val);
                  }}
                >
                  {val}
                </Tag>
              ))}
            </Space>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="输入新选项..."
                value={newValues[key] ?? ''}
                onChange={(e) =>
                  setNewValues((n) => ({ ...n, [key]: e.target.value }))
                }
                onPressEnter={() => addValue(key)}
              />
              <Button onClick={() => addValue(key)}>添加</Button>
            </Space.Compact>
            <div
              style={{
                color: Colors.TEXT.SECONDARY,
                fontSize: FontSize.SECONDARY,
                marginTop: Spacing.XS,
              }}
            >
              保存后生效，已有参数值不做校验。
            </div>
          </div>
        ))
      )}
    </Modal>
  );
};
