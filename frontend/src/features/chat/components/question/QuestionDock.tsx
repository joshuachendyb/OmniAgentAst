// 2026-11-18 商量 - question 浮层问答面板(贴输入框上沿悬浮, 不参与布局流), 壳与计划/信任共用 PanelCard
// 2026-11-18 商量 - 三堂会审整改: 提交按钮在无任何作答时禁用(与 canSubmit 守卫同源)
// 2026-11-18 商量 - 头部增倒计时环(复用 HITL CountdownRing, 后端 backend_timeout 同源), 到 0 仅归零展示, 清窗仍由 question_resolved 收口
// 2026-11-18 商量 - 删头部重复文案: 后端 content 恒为「需要你回答 N 个问题」, 与标题逐字重复, 题量信息由「第 N/M 题」胶囊承担
import {
  CheckOutlined,
  CloseOutlined,
  LeftOutlined,
  MinusOutlined,
  PlusOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { Button } from 'antd';

import type { QuestionDockController } from '@/features/chat/hooks/useQuestionDock';
import CountdownRing from '@/components/AuthorizationModal/CountdownRing';
import { PanelCard, PanelChip } from '@/components/PanelCard';
import { CONTROL_HEIGHT } from '@/theme/controlScale';
import { Gap, LineHeight } from '@/theme/spacing';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { QuestionCustomInput } from './QuestionCustomInput';
import { QuestionOption } from './QuestionOption';

interface QuestionDockProps {
  controller: QuestionDockController;
}

/** 头部图标按钮统一规格(纯图标, 无文字, 热区按控件小档) */
const ICON_BTN = { height: CONTROL_HEIGHT.comfortable.small } as const;

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
    countdown,
  } = controller;

  if (!request) return null;

  /** 分段进度色: 当前题=主色, 已过题=浅主色, 未到题=浅边框色 */
  const segColor = (i: number) => {
    if (i === tab) return Colors.PRIMARY;
    if (i < tab) return Colors.BORDER.ACCENT;
    return Colors.BORDER.LIGHT;
  };

  const headerActions = (
    <>
      {/* 倒计时环(复用 HITL CountdownRing): 30s 窗口下剩余时间是本面板的主信号之一, 置于视线终点
          环自带 marginBottom:4 用于居中留白, 此处 flex 行内需抵掉, 否则整行被压偏 4px(贴边补偿) */}
      {countdown > 0 ? (
        <span style={{ display: 'inline-flex', marginBottom: -Spacing.XS }}>
          <CountdownRing
            countdown={countdown}
            confirmTimeout={request.backendTimeout ?? 0}
            size={40}
          />
        </span>
      ) : null}
      <Button
        type="text"
        size="small"
        aria-label={minimized ? '展开问询' : '最小化问询'}
        data-testid="question-minimize"
        icon={minimized ? <PlusOutlined /> : <MinusOutlined />}
        onClick={toggleMinimize}
        style={ICON_BTN}
      />
      <Button
        type="text"
        size="small"
        danger
        aria-label="关闭问询"
        data-testid="question-close"
        icon={<CloseOutlined />}
        onClick={cancel}
        style={ICON_BTN}
      />
    </>
  );

  const card = (
    <PanelCard
      variant="raised"
      title="需要你回答"
      meta={
        total > 1 ? (
          <PanelChip tone="primary">
            第 {tab + 1} / {total} 题
          </PanelChip>
        ) : null
      }
      actions={headerActions}
      /* 多题时头部下方压一条**分段**进度线: 每段可点即跳题(进度与导航合并成一条),
         比另起一排题号按钮省一整行高度, 也让"还剩几题/现在第几题"一眼可读 */
      subheader={
        total > 1 ? (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              padding: `${Spacing.XS}px ${Spacing.LG}px`,
              borderBottom: `1px solid ${Colors.BORDER.LIGHT}`,
            }}
          >
            {request.questions.map((_, i) => (
              <Button
                key={`${request.questionId}-${i}`}
                type="text"
                aria-label={`第${i + 1}题`}
                data-testid={`question-tab-${i + 1}`}
                aria-current={i === tab}
                onClick={() => goTab(i)}
                style={{
                  flex: 1,
                  minWidth: 0,
                  height: Spacing.MD,
                  padding: 0,
                  lineHeight: 0,
                }}
              >
                <span
                  style={{
                    display: 'block',
                    width: '100%',
                    height: 3,
                    borderRadius: 2,
                    background: segColor(i),
                  }}
                />
              </Button>
            ))}
          </div>
        ) : null
      }
      bodyStyle={{ maxHeight: 'min(360px, 50vh)', overflowY: 'auto' }}
      gap={Spacing.LG}
      footer={
        <>
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
            }}
          >
            {tab === total - 1 ? '提交' : '下一题'}
          </Button>
        </>
      }
    >
      {minimized ? undefined : (
        <>
          {/* 题干: 小标签(问题类别) + 正文。header 是 LLM 给的短标题, question 是完整问句,
              两者信息不重叠, 分层显示比压成一段更好扫读; 组内 4px, 与下方选项块走卡片 12px 主节奏 */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: Spacing.XS,
            }}
          >
            {current?.header ? (
              <span
                style={{
                  fontSize: FontSize.SMALL,
                  color: Colors.TEXT.TERTIARY,
                  letterSpacing: 0.2,
                }}
              >
                {current.header}
              </span>
            ) : null}
            <span
              style={{
                fontSize: FontSize.PRIMARY,
                fontWeight: FontWeight.MEDIUM,
                color: Colors.TEXT.STRONG,
                lineHeight: LineHeight.BODY,
              }}
            >
              {current?.question ?? ''}
            </span>
          </div>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: Gap.INLINE,
            }}
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
        </>
      )}
    </PanelCard>
  );

  return (
    <div
      data-testid="question-dock"
      className="question-dock"
      tabIndex={0}
      onKeyDown={minimized ? undefined : handleKeyDown}
    >
      {card}
    </div>
  );
}
