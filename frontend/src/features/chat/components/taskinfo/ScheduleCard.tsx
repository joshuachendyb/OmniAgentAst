// 2026-11-18 商量 - 新建: taskinfo 的「执行计划」入口 + 浮层卡片
//   WHY: schedule 工具是纯回显(不落库/不发事件), 清单只存在于步骤流里, 需要一个人能主动点开的位置;
//   入口落 taskinfo 左组状态徽标之后 —— 徽标答「这一轮什么状态」, 计划答「进行到哪一步」, 同属一句状态;
//   右组留给耗时/token 等度量与信任/事件入口。
//   与 question 面板的分叉: question 的锚点是阻塞本身(必须弹出), 本入口的锚点是用户主动查(不打扰)。
// 2026-11-18 商量 - 三处纠偏:
//   ① 行由 alignItems:center 改回首行对齐 —— 多行条目时字形浮在整段中间, 与文字不在一个基线上;
//   ② 状态字形的 7px/1px 魔法数改令牌(Spacing.MD / BorderWidth.THIN), 刻度外数字不得出现在业务代码;
//   ③ 脚注「共 N 项，第 M 步更新」把内部步骤计数当说明写给人看, 改成人话(进行中/全部完成) — 商量-2026-11-18
// 2026-11-19 小欧 - list 入参由 ScheduleSnapshot(步骤流派生)改 ScheduleItem[](store.scheduleList, notice 写入);
//   类型 ScheduleItem/ScheduleStatus 改从 chatStreamTypes 导入(清单类型单一真源) — 小欧-2026-11-19
// 2026-11-19 小欧 - 状态渲染优化(高级设计): 字形加 aria-label/title 文字兜底(无障碍可学习); 完成项改绿勾+SECONDARY
//   文字(不再纯灰隐形); 四态形状各异: 完成绿勾✓/进行实心圆●/待开始空心方块□/取消叉✕(配删除线) — 小欧-2026-11-19
// 2026-11-22 商量 - 入口「计划 N/M」文字颜色改深琥珀 WARNING(#AD6800): 原 TEXT.PRIMARY 中灰 #595959
//   在 taskinfo 一线不明显(用户反馈); 深琥珀暖色调醒目, 保留文字入口轻量语言(不胶囊化);
//   与动态状态卡死预警同 WARNING 色带, 但计划是"进行到哪一步"状态短语, 暖色强调合理 — 商量-2026-11-22
// 2026-11-22 商量 - 入口颜色再改 WAIT_ACTION(#fa8c16 太阳橙): 用户要求改成天气图标小圆球(橙黄渐变太阳)
//   的主体色; 圆球主体约 #FF9800 明亮橙, 既有令牌最接近 WAIT_ACTION(复用不新增), 比 WARNING 更亮更近
//   图片鲜艳橙; ⚠ 白底对比度约 2.4:1 偏浅, 12px 小字可读性弱于深琥珀, 若觉浅可再调深 — 商量-2026-11-22
// 2026-11-22 商量 - 入口改用新 token WARNING_BRIGHT: 用户令新增 warning 语义亮警告色(不用 WAIT_ACTION 等
//   非 warning 名), 值 #fa8c16 太阳橙即图片圆球主体色; 深色 WARNING(#AD6800) 保留不变 — 商量-2026-11-22
import { CloseOutlined, CheckOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';

import {
  PanelCard,
  PanelChip,
  PanelIconButton,
  PanelRow,
} from '@/components/PanelCard';
import type {
  ScheduleItem,
  ScheduleStatus,
} from '@/features/chat/streams/chatStreamTypes';
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
  /** 2026-11-19 小欧: schedule notice 写入 store 的清单(TaskInfoBar 传 store.scheduleList) */
  list: ScheduleItem[] | null;
  compact?: boolean; // 窄档仅计数, 与 TrustPanel 的窄档口径一致
}

/**
 * 状态文字色: 字形(形状)为主通道, 文字色做辅助层次。
 * completed 用 SECONDARY(中等对比, 不再 TERTIARY 最弱隐形)配绿勾 —— 完成项仍可读("做完了什么"有价值);
 * in_progress 用 STRONG(最强焦点); pending 用 SECONDARY; cancelled 用 TERTIARY + 删除线(作废最弱) — 小欧 2026-11-19
 */
const STATUS_COLOR: Record<ScheduleStatus, string> = {
  completed: Colors.TEXT.SECONDARY,
  in_progress: Colors.TEXT.STRONG,
  pending: Colors.TEXT.SECONDARY,
  cancelled: Colors.TEXT.TERTIARY,
};

/**
 * 一行文字的行盒高(= 字号 × 密集行高)。
 * 字形按**首行行盒**垂直居中: 条目换行成两行时, 字形仍贴第一行, 而不是浮在整段中间。
 */
const FIRST_LINE_BOX = FontSize.PRIMARY * LineHeight.DENSE;

/** 四态中文标签(字形 aria-label/title + 无障碍, 高级设计: 图形编码配文字兜底) — 小欧 2026-11-19 */
const STATUS_LABEL: Record<ScheduleStatus, string> = {
  completed: '已完成',
  in_progress: '进行中',
  pending: '待开始',
  cancelled: '已取消',
};

/**
 * 状态字形(四态形状各异, 主通道靠形状不靠颜色) — 小欧 2026-11-19:
 *   已完成=绿勾 ✓ / 进行中=实心圆 ● / 待开始=空心方块 □ / 已取消=叉 ✕(配行级删除线)。
 * 每个字形带 role/aria-label/title, 图形编码 + 文字兜底(色觉障碍/新用户可学习)。
 */
function StatusGlyph({ status }: { status: ScheduleStatus }) {
  const label = STATUS_LABEL[status];
  if (status === 'completed') {
    return (
      <CheckOutlined
        role="img"
        aria-label={label}
        title={label}
        style={{
          fontSize: FontSize.SMALL,
          lineHeight: 1,
          color: Colors.PILL_SUCCESS,
        }}
      />
    );
  }
  if (status === 'in_progress') {
    return (
      <span
        role="img"
        aria-label={label}
        title={label}
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
    // 叉表达作废, 配行级删除线(文字色 TERTIARY 最弱)
    return (
      <CloseOutlined
        role="img"
        aria-label={label}
        title={label}
        style={{
          fontSize: FontSize.SMALL,
          lineHeight: 1,
          color: Colors.TEXT.TERTIARY,
        }}
      />
    );
  }
  // 待开始=空心方块(方形, 与实心圆的进行中区分明显; 小尺寸下比空心圈清晰)
  return (
    <span
      role="img"
      aria-label={label}
      title={label}
      style={{
        display: 'inline-block',
        width: Spacing.MD,
        height: Spacing.MD,
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

  const items = list;
  const done = items.filter((it) => it.status === 'completed').length;
  const total = items.length;
  const active = items.find((it) => it.status === 'in_progress');

  const content = (
    <PanelCard
      title="执行计划"
      // 2026-11-22 商量 - 标题行 meta 改当前进行状态(短词): 进度汇总移底部(用户令"两个位置反了"),
      //   标题行只留标题+当前状态; 具体进行中项由内容区实心圆+STRONG 标识(DRY), 避免长内容挤标题行
      meta={
        active ? (
          <PanelChip tone="primary">进行中</PanelChip>
        ) : done === total ? (
          <PanelChip tone="success">全部完成</PanelChip>
        ) : undefined
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
        // 2026-11-22 商量 - 底部脚注改进度汇总(4/6 已完成): 用户令"进度汇总应在底部而非标题行"("两个位置反了"),
        //   标题行只留标题+当前状态, 进度胶囊落底部脚注, 完成态转绿
        <PanelChip tone={done === total ? 'success' : 'primary'}>
          {done} / {total} 已完成
        </PanelChip>
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
            // 2026-11-22 商量 - 颜色改 WARNING_BRIGHT(#fa8c16 亮警告色): 用户要求改成天气图标小圆球
            //   (橙黄渐变太阳)的主体色, 并要求新增 warning 语义 token(不用 WAIT_ACTION 等非 warning 名);
            //   值 #fa8c16 太阳橙即图片圆球主体色。⚠ 白底对比度约 2.4:1 偏浅, 12px 小字可读性弱于深琥珀,
            //   若觉浅可回退深色 WARNING(#AD6800) 或调 ACCENT_ORANGE(#d4380d)。
            color: Colors.WARNING_BRIGHT,
            fontWeight: FontWeight.MEDIUM,
          }}
        >
          {compact ? `${done}/${total}` : `计划 ${done}/${total}`}
        </span>
      </span>
    </FloatingEntry>
  );
}
