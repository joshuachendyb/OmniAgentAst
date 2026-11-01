// 编辑历史: 2026-09-22 小欧 - 新建：管理选项弹窗——Tag 展示/添加/删除当前模型
//  param_options 选项列表；保存前交叉校验悬空默认值（baseline[key] 不在新列表 → Modal.confirm
//  同批回提 model_params 重置首项，复用后端 merge_nested_patch 同批合并零后端改动）。
// 2026-11-01 小欧 - 键名统一：props `defaults` → `baseline`，请求体 `default_params` → `model_params` - 小欧-2026-11-01
// 2026-09-22 小欧 - KISS+令牌收口：`dangling && dangling !== undefined` 冗余判断 → `dangling`（truthy 即非 undefined）；marginBottom:4/marginTop:4/fontSize:12 裸数字 → Spacing.XS/FontSize.SECONDARY - 小欧-2026-09-22
// 2026-09-24 22:56:21 小欧 - 闭环：加 disabled prop（保存中禁用「保存」提交+doSave 头部守卫）——
//   三堂会审发现外部 saveModelGroup saving 进行中弹窗仍可提交 param_options，与模型组保存并发写
//   同 YAML 不同字段（服务端非事务），快照错位同类风险；保存/取消关窗不改模型 state 不禁 - 小欧-2026-09-24
// 2026-09-25 06:17:07 小健 - 「添加」按钮改橘红底白字（Colors.ORANGE_RED 标准令牌 + inline style，
//   北京老陈指示）；同批撤销首版 12 行 antd color 对象与 stepStyles 派生色令牌（过度设计/YAGNI）— 小健-2026-09-25
// 2026-10-10 小欧 - 弹窗归一：主 Modal → SettingsModal 标准壳（form=520 宽度档、confirmLoading、
//   discard 关闭语义、destroyOnHidden）；warning/confirm 静态弹用仍走 antd Modal（无统一壳需求，不动）。
//   实测：宽 520 / ESC 可关，符合设计。
// 2026-11-01 小欧 - 悬空值回提只送变更键：原 `{...baseline, [dangling]: 首项}` 会就地展开整份基线，
//   把 useSettings 注入的「厂商声明 context_length」物化成用户参数落盘 —— 后端 update_model 的
//   model_params 是 merge 语义（dict(orig).update(patch)），只需送 `{ [dangling]: 首项 }`；
//   物化后会压住厂商后续上调的声明窗口 —— 小欧-2026-11-01
import React, { useState } from 'react';
import { Button, Input, Modal, Space, Tag } from 'antd'; // Modal 仍需：warning/confirm 静态弹用
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { SettingsModal } from '@/theme/SettingsModal'; // 2026-10-10 小欧: 归一到设置页弹窗壳
import { modelApi } from '@/services/api/model.api';

interface Props {
  open: boolean;
  provider: string;
  model: string;
  // 当前模型三层解析后的 param_options（{reasoning_effort: ['low','medium','high'], ...}）
  paramOptions: Record<string, string[]>;
  // 当前模型已保存参数基线（悬空值交叉校验数据源）
  baseline: Record<string, unknown>;
  onClose: () => void;
  // 保存成功后回调（父级刷新 paramOptions + baseline）
  onSaved: () => Promise<void> | void;
  // 2026-09-24 小欧 - 闭环：保存中(saving) 禁用提交，防与模型组保存并发写 YAML 致快照错位 — 小欧-2026-09-24
  disabled?: boolean;
}

export const ParamOptionsModal: React.FC<Props> = ({
  open,
  provider,
  model,
  paramOptions,
  baseline,
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
    // 2026-09-24 小欧 - 闭环：保存中禁止提交（防与 saveModelGroup 并发写同 YAML 快照错位）— 小欧-2026-09-24
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
    // 悬空值交叉校验：baseline[key] 不在新列表 → confirm 同批回提 model_params 重置首项
    const dangling = toChangedKeys().find(
      (k) =>
        baseline[k] !== undefined &&
        baseline[k] !== null &&
        !(draft[k] ?? []).includes(String(baseline[k]))
    );
    if (dangling) {
      Modal.confirm({
        title: `默认值 ${dangling}='${String(baseline[dangling])}' 不在新选项内`,
        content: `将重置为该参数第一选项 '${(draft[dangling] ?? [])[0] ?? ''}'，继续？`,
        okText: '确认重置',
        cancelText: '取消',
        // 2026-10-10 小欧 - 审计修复：会重写已存模型的默认值（不可逆），原 ok 键无 danger 标识
        okButtonProps: { danger: true },
        onOk: async () => {
          setSaving(true);
          try {
            await modelApi.updateModel(provider, model, {
              param_options: draft,
              // 2026-11-01 小欧 - 只送被重置的那一个键（后端 merge 语义），
              //   展开 baseline 会把基线注入行(厂商声明 context_length)一并物化落盘 — 小欧-2026-11-01
              model_params: { [dangling]: (draft[dangling] ?? [])[0] },
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
    <SettingsModal
      open={open}
      title={`管理 ${model} 的参数选项`}
      width="form"
      onCancel={onClose}
      onOk={doSave}
      okText="保存"
      cancelText="取消"
      confirmLoading={saving}
      // 2026-09-24 小欧 - 闭环：外部 saving 时禁用 OK 按钮（视觉与守卫双保险）— 小欧-2026-09-24
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
              {/* 2026-09-25 06:17:07 小健 - 「添加」按钮改橘红底白字（Colors.ORANGE_RED 标准令牌 + inline
                  style 3 行; 原 12 行 color 对象过度设计已撤, hover/active 沿用同色不派生新令牌,
                  YAGNI/KISS; 北京老陈指示) — 小健-2026-09-25 */}
              <Button
                style={{
                  background: Colors.ORANGE_RED,
                  borderColor: Colors.ORANGE_RED,
                  color: Colors.BG.PRIMARY,
                }}
                onClick={() => addValue(key)}
              >
                添加
              </Button>
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
    </SettingsModal>
  );
};
