// 2026-11-18 商量 - question 单选项(antd Radio/Checkbox + 数字快捷键提示), 视觉取设计 token
// 2026-11-19 小欧 - multiple→single 语义反转: single 默认true=单选; role/控件与传参同步 — 小欧-2026-11-19
import { Checkbox, Radio } from 'antd';

import { Gap } from '@/theme/spacing';
import { Colors, FontSize, Radius, Spacing } from '@/utils/stepStyles';

interface QuestionOptionProps {
  label: string;
  description?: string;
  index: number;
  single: boolean;
  selected: boolean;
  onSelect: (label: string) => void;
}

export function QuestionOption({
  label,
  description,
  index,
  single,
  selected,
  onSelect,
}: QuestionOptionProps) {
  return (
    <div
      data-testid={`question-option-${index + 1}`}
      role={single ? 'radio' : 'checkbox'}
      aria-checked={selected}
      tabIndex={0}
      onClick={() => onSelect(label)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(label);
        }
      }}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: Gap.INLINE,
        padding: `${Spacing.SM}px ${Spacing.MD}px`,
        borderRadius: Radius.DEFAULT,
        border: `1px solid ${selected ? Colors.BORDER.ACCENT : Colors.BORDER.LIGHT}`,
        background: selected ? Colors.BG.SELECTED : Colors.BG.PRIMARY,
        cursor: 'pointer',
        lineHeight: 1.5,
      }}
    >
      {/* 选中唯一入口 = 容器 onClick/onKeyDown; 内层控件只做视觉, onChange 空实现避免与容器冒泡双触发 */}
      {single ? (
        <Radio checked={selected} onChange={() => undefined} />
      ) : (
        <Checkbox checked={selected} onChange={() => undefined} />
      )}
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={{ fontSize: FontSize.PRIMARY, color: Colors.TEXT.STRONG }}>
          <span
            style={{ color: Colors.TEXT.TERTIARY, marginRight: Spacing.XS }}
          >
            {index + 1}.
          </span>
          {label}
        </span>
        {description ? (
          <span
            style={{
              display: 'block',
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {description}
          </span>
        ) : null}
      </span>
    </div>
  );
}
