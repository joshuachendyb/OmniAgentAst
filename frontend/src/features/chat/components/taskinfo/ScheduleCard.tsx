// 2026-11-18 商量 - 新建: taskinfo 的「执行计划」入口 + 浮层卡片
//   WHY: schedule 工具是纯回显(不落库/不发事件), 清单只存在于步骤流里, 需要一个人能主动点开的位置;
//   入口落 taskinfo 左组状态徽标之后 —— 徽标答「这一轮什么状态」, 计划答「进行到哪一步」, 同属一句状态;
//   右组留给耗时/token 等度量与信任/事件入口。
//   与 question 面板的分叉: question 的锚点是阻塞本身(必须弹出), 本入口的锚点是用户主动查(不打扰)。
// 2026-11-18 商量 - 三处纠偏:
//   ① 行由 alignItems:center 改回首行对齐 —— 多行条目时字形浮在整段中间, 与文字不在一个基线上;
//   ② 状态字形的 7px/1px 魔法数改令牌(Spacing.MD / BorderWidth.THIN), 刻度外数字不得出现在业务代码;
//   ③ 脚注「共 N 项，第 M 步更新」把内部步骤计数当说明写给人看, 改成人话(进行中/全部完成) — 商量-2026-11-18
import { CloseOutlined, CheckOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';

import {
  PanelCard,
  PanelChip,
  PanelIconButton,
  PanelRow,
} from '@/components/PanelCard';
import type {
  ScheduleSnapshot,
  ScheduleStatus,
} from '@/features/chat/hooks/useScheduleList';
import { LineHeight } from '@/theme/spacing';
import {
  BorderWidth,
  Colors,
  FontSize,
  FontWeight,
  Size,
  Spacing,
} from '@/utils/stepStyles';

import { FloatingEntry } from './FloatingEntry';

const CARD_W = 30 * FontSize.SECONDARY; // 30 汉字宽 ≈ 360px

interface ScheduleCardProps {
  /** 派生自步骤流的最新清单(TaskInfoBar 用同一份派生值决定分隔点与入口显隐, 故由此传入) */
  list: ScheduleSnapshot | null;
  compact?: boolean; // 窄档仅计数, 与 TrustPanel 的窄档口径一致
}

/** 状态视觉: 一个 12px 定宽字位 + 文字色, 三档"完成/进行中/待办"不靠图标数量堆叠 */
const STATUS_COLOR: Record<ScheduleStatus, string> = {
  completed: Colors.TEXT.TERTIARY,
  in_progress: Colors.TEXT.STRONG,
  pending: Colors.TEXT.SECONDARY,
  cancelled: Colors.TEXT.TERTIARY,
};

/**
 * 一行文字的行盒高(= 字号 × 密集行高)。
 * 字形按**首行行盒**垂直居中: 条目换行成两行时, 字形仍贴第一行, 而不是浮在整段中间。
 */
const FIRST_LINE_BOX = FontSize.PRIMARY * LineHeight.DENSE;

/** 状态字形: 已完成=勾, 进行中=实心点, 待开始=空心圈, 已取消=短横 */
function StatusGlyph({ status }: { status: ScheduleStatus }) {
  if (status === 'completed') {
    return (
      <CheckOutlined style={{ fontSize: FontSize.SMALL, lineHeight: 1 }} />
    );
  }
  if (status === 'in_progress') {
    return (
      <span
        style={{
          display: 'inline-block',
          width: Spacing.MD,
          height: Spacing.MD,
          borderRadius: '50%',
          background: Colors.PRIMARY,
        }}
      />
    );
  }
  if (status === 'cancelled') {
    return (
      <span
        style={{
          display: 'inline-block',
          width: Spacing.MD,
          height: BorderWidth.THIN,
          background: Colors.TEXT.TERTIARY,
        }}
      />
    );
  }
  return (
    <span
      style={{
        display: 'inline-block',
        width: Spacing.MD,
        height: Spacing.MD,
        borderRadius: '50%',
        border: `${BorderWidth.THIN}px solid ${Colors.BORDER.STRONG}`,
      }}
    />
  );
}

export function ScheduleCard({ list, compact }: ScheduleCardProps) {
  const [open, setOpen] = useState(false);

  // 清单消失(清空/换会话/换任务)时同步关闭浮层, 避免留下一个空浮层
  useEffect(() => {
    if (!list) setOpen(false);
  }, [list]);

  if (!list) return null;

  const { items } = list;
  const done = items.filter((it) => it.status === 'completed').length;
  const total = items.length;
  const active = items.find((it) => it.status === 'in_progress');

  const content = (
    <PanelCard
      title="执行计划"
      meta={
        <PanelChip tone={done === total ? 'success' : 'primary'}>
          {done} / {total} 已完成
        </PanelChip>
      }
      actions={
        <PanelIconButton
          ariaLabel="关闭执行计划"
          icon={<CloseOutlined />}
          onClick={() => setOpen(false)}
        />
      }
      gap={0}
      bodyStyle={{
        maxHeight: Size.PANEL_LIST_MAX_H,
        overflowY: 'auto',
      }}
      footer={
        // 脚注只说人话: 有进行中项就点名, 全做完就说全做完, 其余情况不占一行
        // (原「共 N 项，第 M 步更新」把内部步骤计数当说明, 读者既不知道"第 M 步"指什么, 也用不上)
        active
          ? `进行中：${active.content}`
          : done === total
            ? '全部完成'
            : undefined
      }
    >
      {items.map((it, i) => (
        <PanelRow
          key={`${i}-${it.content}`}
          // 计划是有序的, 按原顺序直显(按状态分组会打乱阅读顺序)
          style={{
            color: STATUS_COLOR[it.status],
            textDecoration:
              it.status === 'cancelled' ? 'line-through' : undefined,
            fontWeight:
              it.status === 'in_progress' ? FontWeight.MEDIUM : undefined,
          }}
        >
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: FontSize.SECONDARY,
              // 字形只对齐首行行盒: 条目换行时不会漂到整段中间
              height: FIRST_LINE_BOX,
              flexShrink: 0,
            }}
          >
            <StatusGlyph status={it.status} />
          </span>
          <span style={{ minWidth: 0, wordBreak: 'break-word' }}>
            {it.content}
          </span>
        </PanelRow>
      ))}
    </PanelCard>
  );

  return (
    <FloatingEntry
      open={open}
      onOpenChange={setOpen}
      // 入口在 taskinfo(视口底部), 必须向上弹: 向下展开只剩输入框高度, 长清单必被裁。
      // 与「事件」浮层同一决策(2026-11-18 小欧实测), 此处沿用 — 商量-2026-11-18
      // 2026-11-18 商量 - 水平方向改 topLeft: 入口已迁至左组(徽标之后), 贴视口左侧,
      //   若仍写 topRight, 卡片右缘对齐入口左缘会跑出视口左边界, 只能靠 rc-trigger 自动翻转兜底。
      //   声明真实方位, 不依赖翻转。
      placement="topLeft"
      cardId="taskinfo-schedule-card"
      ariaLabel="执行计划"
      cardStyle={{ width: CARD_W, maxWidth: '90vw' }}
      content={content}
    >
      <span
        data-testid="schedule-entry"
        style={{ fontSize: FontSize.SECONDARY }}
      >
        {/* 不叠 Tooltip: 本入口是 hover 即开浮层, 再挂一层悬浮提示会与浮层抢同一触发, 观感上是两个框同时冒出 */}
        <span
          style={{
            color: Colors.TEXT.PRIMARY,
            fontWeight: FontWeight.MEDIUM,
          }}
        >
          {compact ? `${done}/${total}` : `计划 ${done}/${total}`}
        </span>
      </span>
    </FloatingEntry>
  );
}
