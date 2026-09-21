// 编辑历史: 2026-09-20 小强 - 新建：模型参数区（跟随当前模型+范围+[已修改]+[重置为默认]确认内联）
import React from 'react';
import { Button, InputNumber, Modal, Slider } from 'antd';
import { isDirty } from '../utils/modelUtils';
import { DirtyDot } from './icons';

interface Props {
  params: Record<string, unknown>;
  defaults: Record<string, unknown>;
  ranges: Record<string, { min: number; max: number }>;
  envOverride: Record<string, boolean>;
  onChange: (key: string, value: unknown) => void;
  onReset: () => void;
}

export const ModelParams: React.FC<Props> = ({
  params,
  defaults,
  ranges,
  envOverride,
  onChange,
  onReset,
}) => {
  const dirty = isDirty(params, defaults, envOverride);
  const confirmReset = () => {
    Modal.confirm({
      title: '重置为默认',
      content: '按当前模型 schema.default 重置全部参数，脏态清空。继续吗？',
      okText: '重置',
      cancelText: '取消',
      onOk: onReset,
    });
  };
  return (
    <div>
      {Object.keys(defaults).map((key) => {
        const range = ranges[key];
        const value = (params[key] ?? defaults[key]) as number;
        return (
          <div
            key={key}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              minHeight: 44,
            }}
          >
            <span style={{ width: 132 }}>{key}</span>
            {range ? (
              <span
                style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}
              >
                <Slider
                  min={range.min}
                  max={range.max}
                  value={value}
                  style={{ width: 160 }}
                  onChange={(v) => onChange(key, v)}
                />
                <InputNumber
                  min={range.min}
                  max={range.max}
                  value={value}
                  onChange={(v) => onChange(key, v)}
                />
              </span>
            ) : (
              <InputNumber value={value} onChange={(v) => onChange(key, v)} />
            )}
            <span style={{ color: '#8c8c8c', fontSize: 12 }}>
              范围{range ? `${range.min}-${range.max}` : '不限'} 默认
              {String(defaults[key])}
            </span>
            {dirty[key] && <DirtyDot />}
          </div>
        );
      })}
      <Button onClick={confirmReset}>重置为默认</Button>
    </div>
  );
};
