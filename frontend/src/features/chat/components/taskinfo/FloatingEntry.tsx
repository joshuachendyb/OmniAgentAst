// 编辑历史: 2026-09-09 小欧 - v4.2: 抽 G6/G8 双浮层入口公共壳(DRY, 17 行×2 处重复收敛)
//   Popover 配置 + taskinfo-entry 热区 a11y + Enter/Space/Esc 键盘 + 单真源开合 + 焦点管理(3.8/7.3); 卡片内容/样式调用方注入 — 小欧-2026-09-09
// 编辑历史: 2026-10-10 小欧[20] 三堂会审 10 规范审计 B5 - hover 打开的浮层点击不得反向关闭: trigger
//   ['hover','click'] 共享受控 open, 鼠标未移出时无 mouseenter 纠正 → 卡在关闭态"点一下反而关掉"。记来源后
//   hover 态点击只确保打开; 键盘路径同步清标记, 不影响既有"点开再点关"契约
// 编辑历史: 2026-10-13 小欧 - 文档[29]D-7: 新增可选 prop trigger?: Array<'hover'|'click'>(默认 ['hover','click'],
//   G6/G8 两处既有调用零变化, OCP 扩展不改既有签名) 并由 Popover 透传; 同时把 B5 补偿逻辑**按 trigger 门控**
//   (hoverTriggered = trigger.includes('hover')): onMouseEnter 仅 hover 模式置位、onClick 仅 hover 模式消费。
//   原因: onMouseEnter 原是无条件置位, 若只把 trigger 透传而不门控, 纯点击模式下会出现
//   「鼠标移入→点开→再点一次关不掉」(open && hoverOpenedRef 吃掉关闭意图), T36 必挂 — 小欧-2026-10-13
import React, { useEffect, useRef } from 'react';
import { Popover } from 'antd';

export interface FloatingEntryProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  placement: 'bottomLeft' | 'bottomRight'; // antd 真值: bottomLeft=G6 左缘对齐向右展开 / bottomRight=G8 右缘对齐向左展开(3.9)
  /**
   * 2026-10-13 小欧 - 文档[29]§3.5/D-7: 触发方式。默认 ['hover','click'] 保持 G6/G8 既有行为**零变化**;
   *   参数区浮层传 ['click'] 去掉悬停弹出与 B5「首击被吃掉」(本文件 :97-105)。
   */
  trigger?: Array<'hover' | 'click'>;
  cardId: string; // 卡片 id（= 入口 aria-controls，关系内聚于组件内）
  ariaLabel: string; // 入口 + 卡片共用 aria-label
  cardStyle?: React.CSSProperties; // 卡片容器样式（宽/布局，调用方注入）
  content: React.ReactNode; // 卡片内容（调用方注入，内部 a11y 如 role="log" 自带）
  children: React.ReactNode; // 入口热区内容（G6: MetricItem / G8: DownOutlined + "事件"）
}

export const FloatingEntry: React.FC<FloatingEntryProps> = ({
  open,
  onOpenChange,
  placement,
  trigger = ['hover', 'click'],
  cardId,
  ariaLabel,
  cardStyle,
  content,
  children,
}) => {
  const entryRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(open);
  // 2026-10-10 小欧[20] 审计 B5: hover 打开的浮层, 点击不得反向关闭。
  //   病根: trigger=['hover','click'] 共享受控 open —— 鼠标已悬停打开时点击置 false,
  //   而鼠标未移出不会再有 mouseenter 纠正 → 卡在关闭态, 用户观感"点了一下反而关掉, 再点打不开"。
  //   修法(KISS-DIRECT): 记来源, hover 态的点击只"确保打开"不关闭; 再点一次才关(测试契约仍成立)。
  const hoverOpenedRef = useRef(false);
  // 2026-10-13 小欧 - 文档[29]D-7 闭环: B5 补偿**只服务于 hover 触发**。
  //   无 hover 触发时(本功能传 ['click'])若仍置位/消费 hoverOpenedRef, 会出现纯点击下"点开后再点关不掉"
  //   (mouseenter 无条件置 true → onClick 见 open=true 便吃掉关闭意图)。故整条 B5 逻辑按 trigger 门控。
  const hoverTriggered = trigger.includes('hover');
  // 打开后焦点入卡(3.8/7.3)：仅当入口持有焦点时跟进（hover 打开不抢焦点）
  useEffect(() => {
    if (
      open &&
      !wasOpen.current &&
      document.activeElement === entryRef.current
    ) {
      cardRef.current?.focus();
    }
    wasOpen.current = open;
  }, [open]);
  // 卡片内 Esc（portal 内容经 React 树冒泡至外层 div）：关闭 + 焦点回入口(3.8/7.3)
  const closeToEntry = () => {
    onOpenChange(false);
    entryRef.current?.focus();
  };
  return (
    <div
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          closeToEntry();
        }
      }}
    >
      <Popover
        open={open}
        onOpenChange={onOpenChange}
        trigger={trigger}
        placement={placement}
        mouseEnterDelay={0.15}
        mouseLeaveDelay={0.3}
        arrow={{ pointAtCenter: true }}
        content={
          <div
            ref={cardRef}
            tabIndex={-1}
            id={cardId}
            role="dialog"
            aria-label={ariaLabel}
            style={cardStyle}
          >
            {content}
          </div>
        }
      >
        <div
          ref={entryRef}
          className={`taskinfo-entry${open ? ' taskinfo-entry-open' : ''}`}
          data-open={open}
          role="button"
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-label={ariaLabel}
          aria-controls={cardId}
          tabIndex={0}
          onMouseEnter={() => {
            if (hoverTriggered) hoverOpenedRef.current = true;
          }}
          onClick={(e) => {
            e.stopPropagation(); // 仅止冒泡；开合交还 antd trigger（v4.2 双写修复：删手动 toggle）
            // 审计 B5: hover 打开的态, 点击改为"确保打开"(吃掉这次关闭意图), 避免无 mouseenter 纠正
            //   2026-10-13 小欧: 门控 hoverTriggered —— 纯 click 触发时无 hover 打开的态, 不得吃点击(T36)
            if (open && hoverTriggered && hoverOpenedRef.current) {
              hoverOpenedRef.current = false;
              return;
            }
            hoverOpenedRef.current = false;
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              hoverOpenedRef.current = false;
              onOpenChange(!open);
            }
          }}
        >
          {children}
        </div>
      </Popover>
    </div>
  );
};
