// 编辑历史: 2026-11-09 小欧 - 新建：② 参数表单与参数行容器（AddParamForm + ModelParams）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import { AddParamForm } from './AddParamForm';
import { ModelParams } from './ModelParams';

interface Props {
  params: Record<string, unknown>;
  baseline: Record<string, unknown>;
  ranges: Record<string, { min: number; max: number }>;
  options: Record<string, string[]>;
  envOverride: Record<string, boolean>;
  disabled: boolean;
  addFormOpen: boolean;
  onAdd: (
    key: string,
    value: unknown,
    meta?: { range?: { min: number; max: number }; options?: string[] }
  ) => void;
  onCancelAdd: () => void;
  onChange: (key: string, value: unknown) => void;
  onDelete: (key: string) => void;
}

export const ModelTabParams: React.FC<Props> = ({
  params,
  baseline,
  ranges,
  options,
  envOverride,
  disabled,
  addFormOpen,
  onAdd,
  onCancelAdd,
  onChange,
  onDelete,
}) => (
  <>
    {/* 「+ 添加参数」内联表单（勾选多个循环 onAdd，批量完调 onCancelAdd 统一关） */}
    {addFormOpen && (
      <AddParamForm
        existingKeys={Object.keys(params)}
        onAdd={onAdd}
        onCancel={onCancelAdd}
        // 保存中禁用表单确认，防保存 await 期间注入新键致快照错位
        disabled={disabled}
      />
    )}
    <ModelParams
      params={params}
      baseline={baseline}
      ranges={ranges}
      options={options}
      envOverride={envOverride}
      onChange={onChange}
      onDelete={onDelete}
      // 保存中锁定参数区全部控件+×按钮，防闭包快照错位
      disabled={disabled}
    />
  </>
);
