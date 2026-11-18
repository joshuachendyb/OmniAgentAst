// 2026-11-18 商量 - question 自定义输入框(antd Checkbox + Input.TextArea, 恒开与 opencode custom:true 一致)
import { Checkbox, Input } from 'antd';

import { CONTROL_PADDING, CONTROL_RADIUS } from '@/theme/controlScale';
import { Gap } from '@/theme/spacing';
import { Colors, FontSize } from '@/utils/stepStyles';

interface QuestionCustomInputProps {
  on: boolean;
  text: string;
  onToggle: () => void;
  onChange: (text: string) => void;
}

export function QuestionCustomInput({
  on,
  text,
  onToggle,
  onChange,
}: QuestionCustomInputProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: Gap.STACK }}>
      <Checkbox
        data-testid="question-custom-toggle"
        checked={on}
        onChange={onToggle}
      >
        <span
          style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.MUTED }}
        >
          输入自己的答案
        </span>
      </Checkbox>
      {on ? (
        <Input.TextArea
          data-testid="question-custom-input"
          value={text}
          onChange={(e) => onChange(e.target.value)}
          rows={2}
          aria-label="自定义答案"
          style={{
            padding: `${CONTROL_PADDING.TEXT_INPUT_Y_TIGHT}px ${CONTROL_PADDING.TEXT_INPUT_X}px`,
            borderRadius: CONTROL_RADIUS.normal,
            borderColor: Colors.BORDER.DEFAULT,
            fontSize: FontSize.PRIMARY,
            resize: 'none',
          }}
        />
      ) : null}
    </div>
  );
}
