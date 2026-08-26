/**
 * InputCore - 输入框本体（多行）
 *
 * 【小欧 2026-08-26 8.12】4.3.6 整体高度默认 3 行、最高 5 行(含底部功能按钮行)：
 * 输入框 autoSize minRows=3 / maxRows=4，加 SubmitBar 1 行 = 整体 ≤5；
 * 超 5 行输入框内部滚动（滚动非截断）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Input } from 'antd';

const { TextArea } = Input;

interface InputCoreProps {
  value: string;
  onChange: (v: string) => void;
  onPressEnter: () => void;
  disabled?: boolean;
}

const InputCore: React.FC<InputCoreProps> = ({
  value,
  onChange,
  onPressEnter,
  disabled,
}) => (
  <TextArea
    value={value}
    onChange={(e) => onChange(e.target.value)}
    onPressEnter={(e) => {
      if (!e.shiftKey) {
        e.preventDefault();
        onPressEnter();
      }
    }}
    placeholder="输入消息，Shift+Enter 换行"
    autoSize={{ minRows: 3, maxRows: 4 }}
    disabled={disabled}
  />
);

export { InputCore };
