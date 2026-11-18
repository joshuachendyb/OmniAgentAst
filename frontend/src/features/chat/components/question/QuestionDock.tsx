// 2026-11-18 商量 - question 卡片式底部停靠面板(对齐系统既有 antd + 设计 token 范式, 非 Modal)
// 2026-11-18 商量 - 三堂会审整改: 提交按钮在无任何作答时禁用(与 canSubmit 守卫同源)
import {
  CheckOutlined,
  CloseOutlined,
  LeftOutlined,
  MinusOutlined,
  PlusOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Button, Tag, Typography } from 'antd';

import type { QuestionDockController } from '@/features/chat/hooks/useQuestionDock';
import { CONTROL_HEIGHT, CONTROL_RADIUS } from '@/theme/controlScale';
import { Gap, LineHeight } from '@/theme/spacing';
import {
  Colors,
  FontSize,
  FontWeight,
  Radius,
  Spacing,
} from '@/utils/stepStyles';
import { QuestionCustomInput } from './QuestionCustomInput';
import { QuestionOption } from './QuestionOption';

const { Text } = Typography;

interface QuestionDockProps {
  controller: QuestionDockController;
}

export function QuestionDock({ controller }: QuestionDockProps) {
  const {
    request,
    total,
    tab,
    current,
    selected,
    custom,
    minimized,
    selectOption,
    toggleCustom,
    setCustomText,
    goTab,
    next,
    prev,
    cancel,
    toggleMinimize,
    handleKeyDown,
    canSubmit,
  } = controller;

  if (!request) return null;

  const header = (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: Gap.GROUP,
        padding: `${Spacing.MD}px ${Spacing.LG}px`,
        borderBottom: `1px solid ${Colors.BORDER.LIGHT}`,
      }}
    >
      <Text
        strong
        style={{ fontSize: FontSize.PRIMARY, color: Colors.TEXT.STRONG }}
      >
        需要你回答
      </Text>
      <Tag style={{ margin: 0, fontSize: FontSize.CAPTION }}>
        第 {tab + 1}/{total} 题
      </Tag>
      <span style={{ marginLeft: 'auto', display: 'flex', gap: Gap.INLINE }}>
        <Button
          type="text"
          size="small"
          aria-label={minimized ? '展开问询' : '最小化问询'}
          data-testid="question-minimize"
          icon={minimized ? <PlusOutlined /> : <MinusOutlined />}
          onClick={toggleMinimize}
          style={{ height: CONTROL_HEIGHT.comfortable.small }}
        />
        <Button
          type="text"
          size="small"
          danger
          aria-label="关闭问询"
          data-testid="question-close"
          icon={<CloseOutlined />}
          onClick={cancel}
          style={{ height: CONTROL_HEIGHT.comfortable.small }}
        />
      </span>
    </div>
  );

  if (minimized) {
    return (
      <div
        data-testid="question-dock"
        style={{
          display: 'flex',
          flexDirection: 'column',
          borderRadius: CONTROL_RADIUS.lg,
          border: `1px solid ${Colors.BORDER.LIGHT}`,
          background: Colors.BG.PRIMARY,
          boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
          overflow: 'hidden',
        }}
      >
        {header}
      </div>
    );
  }

  return (
    <div
      data-testid="question-dock"
      tabIndex={0}
      onKeyDown={handleKeyDown}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: Gap.SECTION,
        padding: `${Spacing.MD}px ${Spacing.LG}px`,
        borderRadius: CONTROL_RADIUS.lg,
        border: `1px solid ${Colors.BORDER.LIGHT}`,
        background: Colors.BG.PRIMARY,
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
        maxHeight: 360,
        overflowY: 'auto',
        textAlign: 'left',
        outlineColor: Colors.BORDER.ACCENT,
      }}
    >
      {header}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: Gap.STACK,
          lineHeight: LineHeight.BODY,
        }}
      >
        <Text
          style={{
            fontSize: FontSize.PRIMARY,
            fontWeight: FontWeight.MEDIUM,
            color: Colors.TEXT.STRONG,
          }}
        >
          {current?.question ?? ''}
        </Text>
        {request.content ? (
          <Text
            style={{
              fontSize: FontSize.SECONDARY,
              color: Colors.TEXT.SECONDARY,
            }}
          >
            {request.content}
          </Text>
        ) : null}
        {total > 1 ? (
          <div style={{ display: 'flex', gap: Gap.INLINE }}>
            {request.questions.map((q, i) => (
              <Button
                key={`${request.questionId}-${i}`}
                type={i === tab ? 'primary' : 'default'}
                size="small"
                aria-label={`第${i + 1}题`}
                data-testid={`question-tab-${i + 1}`}
                onClick={() => goTab(i)}
                style={{ height: CONTROL_HEIGHT.comfortable.small }}
              >
                {i + 1}
              </Button>
            ))}
          </div>
        ) : null}
        <div
          style={{ display: 'flex', flexDirection: 'column', gap: Gap.INLINE }}
        >
          {(current?.options ?? []).map((opt, i) => (
            <QuestionOption
              key={`${request.questionId}-${tab}-${i}`}
              index={i}
              label={opt.label}
              description={opt.description}
              multiple={Boolean(current?.multiple)}
              selected={selected.includes(opt.label)}
              onSelect={selectOption}
            />
          ))}
        </div>
        <QuestionCustomInput
          on={custom.on}
          text={custom.text}
          onToggle={toggleCustom}
          onChange={setCustomText}
        />
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Gap.INLINE,
          borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
          paddingTop: Spacing.MD,
        }}
      >
        <Button
          size="small"
          data-testid="question-dismiss"
          onClick={cancel}
          style={{ height: CONTROL_HEIGHT.comfortable.normal }}
        >
          取消
        </Button>
        <Button
          size="small"
          data-testid="question-prev"
          icon={<LeftOutlined />}
          disabled={tab === 0}
          onClick={prev}
          style={{ height: CONTROL_HEIGHT.comfortable.normal }}
        >
          上一题
        </Button>
        <Button
          type="primary"
          size="small"
          data-testid="question-next"
          icon={tab === total - 1 ? <CheckOutlined /> : <RightOutlined />}
          onClick={next}
          disabled={tab === total - 1 && !canSubmit}
          style={{
            height: CONTROL_HEIGHT.comfortable.normal,
            marginLeft: 'auto',
            borderRadius: Radius.DEFAULT,
          }}
        >
          {tab === total - 1 ? '提交' : '下一题'}
        </Button>
      </div>
    </div>
  );
}
