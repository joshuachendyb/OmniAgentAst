// 2026-11-18 商量 - question 浮层问答面板(贴输入框上沿悬浮, 不参与布局流), 壳与计划/信任共用 PanelCard
// 2026-11-18 商量 - 三堂会审整改: 提交按钮在无任何作答时禁用(与 canSubmit 守卫同源)
// 2026-11-18 商量 - 头部增倒计时环(复用 HITL CountdownRing, 后端 backend_timeout 同源), 到 0 仅归零展示, 清窗仍由 question_resolved 收口
// 2026-11-18 商量 - 删头部重复文案: 后端 content 恒为「需要你回答 N 个问题」, 与标题逐字重复, 题量信息由「第 N/M 题」胶囊承担
// 2026-11-18 商量 - 排版纠偏:
//   ① 分段进度条 gap 2 / 高 3 / 圆角 2 是刻度外数字, 改 Gap.ROW / Spacing.XS / Radius.SM 三档令牌;
//   ② 「上一题」在单题面板里永远是禁用态(死控件), 单题不渲染, 把宽度让给「提交」;
//   ③ 最小化只该剩一条标题栏(它的全部意义就是让位给会话区), 底部三按钮随之收起;
//   ④ 头部图标按钮改自绘 PanelIconButton(antd 按钮的高/内距/圆角/焦点环是库缺省派生, 见 controlScale 铁律) — 商量-2026-11-18
// 2026-11-18 商量 - 去通栏: 卡片宽度定为 520(与 HITL 授权弹窗同宽, 产品定宽), 窄视口 90vw 兜底;
//   卡片左缘贴锚点容器左缘(输入行左缘), 与聊天正文同一根左轴。
//   原实现随锚点容器 left:0/right:0 拉满会话列(实测 826 宽), 宽屏下成一条横幅, 选项行也失去节奏。 — 商量-2026-11-18
// 2026-11-18 商量 - 右上 × 走 cancel(中断问询), aria-label 改名符实; 倒计时环改从 components/CountdownRing 具名引入 — 商量-2026-11-18
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
// 2026-11-18 商量 - 共享件归位: 倒计时环迁至 components/CountdownRing(具名导出), 授权弹窗与本浮层同一份实现
import { CountdownRing } from '@/components/CountdownRing';
import { PanelCard, PanelChip, PanelIconButton } from '@/components/PanelCard';
import { CONTROL_HEIGHT } from '@/theme/controlScale';
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

/**
 * 浮层宽度 —— 与 HITL 授权弹窗同宽(520, 产品定宽, 不由字数推导): 问询与授权是同一族的
 * 「停下来问人一句」面板, 两张并排/先后出现时宽度一致, 不产生跳变。
 * 浮层不得通栏: 原实现跟着输入行 left:0/right:0 拉满整个会话列(实测 826), 宽屏下读成一条横幅,
 * 选项行被拉长后失去节奏; 窄视口由 90vw 兜底收缩。 — 商量 2026-11-18
 */
const CARD_W = 520;

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
      {/* 倒计时环(与 HITL 危险确认弹窗共用同一组件, 仅直径分叉): 30s 窗口下剩余时间是本面板的主信号之一,
          置于视线终点。环的盒子尺寸即直径本身, 行内不需任何贴边补偿 */}
      {countdown > 0 ? (
        <span style={{ display: 'inline-flex' }}>
          <CountdownRing
            countdown={countdown}
            confirmTimeout={request.backendTimeout ?? 0}
            size={40}
          />
        </span>
      ) : null}
      <PanelIconButton
        ariaLabel={minimized ? '展开问询' : '最小化问询'}
        testId="question-minimize"
        icon={minimized ? <PlusOutlined /> : <MinusOutlined />}
        onClick={toggleMinimize}
      />
      <PanelIconButton
        // 名副其实: 本按钮走 cancel(取消本次问询并让模型自行决策继续), 不是"收起/关闭"这类无副作用动作 — 商量-2026-11-18
        ariaLabel="取消问询(模型自行决策继续)"
        testId="question-close"
        tone="danger"
        icon={<CloseOutlined />}
        onClick={cancel}
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
              // 段与段之间的缝: 走刻度最小档(原 2px 属刻度外数字)
              gap: Gap.ROW,
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
                  // 可点条高 12 = 4px 进度条 + 上下各 4px 触区(原 8px 条过细, 鼠标容易点空)
                  height: Spacing.LG,
                  padding: 0,
                  lineHeight: 0,
                }}
              >
                <span
                  style={{
                    display: 'block',
                    width: '100%',
                    // 条高 4 / 圆角 4: 取刻度最小档, 4px 高的胶囊两端不会出现"半圆被压平"的假角
                    height: Spacing.XS,
                    borderRadius: Radius.SM,
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
        // 最小化只剩一条标题栏(它的意义就是让位给会话区), 底部动作一并收起;
        // 「上一题」单题时恒禁用(死控件), 单题不渲染, 宽度让给「提交」
        minimized ? undefined : (
          // 脚注容器本身是块级, 里面必须自成一行 flex: 否则 marginLeft:auto 在行内流里不生效,
          // 主按钮会紧贴「上一题」而不是落在右端
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: Gap.INLINE,
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
            {total > 1 ? (
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
            ) : null}
            <Button
              type="primary"
              size="small"
              data-testid="question-next"
              icon={tab === total - 1 ? <CheckOutlined /> : <RightOutlined />}
              onClick={next}
              disabled={tab === total - 1 && !canSubmit}
              style={{
                height: CONTROL_HEIGHT.comfortable.normal,
                // 主按钮贴右端: 贴边补偿是 margin 的正当用法(铁律三例外①), 不参与兄弟间距
                marginLeft: 'auto',
              }}
            >
              {tab === total - 1 ? '提交' : '下一题'}
            </Button>
          </div>
        )
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
      // 宽度只在本层收敛(锚点容器仍是整行), 卡片左缘与输入框左缘同一轴线
      style={{ width: CARD_W, maxWidth: '90vw' }}
      onKeyDown={minimized ? undefined : handleKeyDown}
    >
      {card}
    </div>
  );
}
