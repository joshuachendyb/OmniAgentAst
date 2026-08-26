// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 任务类型勾选(续聊/新任务), 发送后复位新任务(4.6.1)
/**
 * TaskTypeToggle - 任务类型勾选（续聊 linked / 新任务 independent，默认 independent）
 *
 * 【小欧 2026-08-26 8.12】4.6.1：发送后本次勾选状态复位为"新任务"（复位逻辑在
 * ChatInput 组合根的 handleSend 中执行 setChecked(false)）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Checkbox } from 'antd';

interface TaskTypeToggleProps {
  checked: boolean; // true = 续聊 linked
  onChange: (checked: boolean) => void;
}

const TaskTypeToggle: React.FC<TaskTypeToggleProps> = ({
  checked,
  onChange,
}) => (
  <Checkbox checked={checked} onChange={(e) => onChange(e.target.checked)}>
    续聊任务
  </Checkbox>
);

export { TaskTypeToggle };
