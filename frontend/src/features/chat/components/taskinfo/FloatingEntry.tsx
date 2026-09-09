// 编辑历史: 2026-09-09 小欧 - v4.2: 抽 G6/G8 双浮层入口公共壳(DRY, 17 行×2 处重复收敛)
//   Popover 配置 + taskinfo-entry 热区 a11y + Enter/Space/Esc 键盘 + 单真源开合 + 焦点管理(3.8/7.3); 卡片内容/样式调用方注入 — 小欧-2026-09-09
import React, { useEffect, useRef } from 'react';
import { Popover } from 'antd';

export interface FloatingEntryProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  placement: 'bottomLeft' | 'bottomRight'; // antd 真值: bottomLeft=G6 左缘对齐向右展开 / bottomRight=G8 右缘对齐向左展开(3.9)
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
  cardId,
  ariaLabel,
  cardStyle,
  content,
  children,
}) => {
  const entryRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const wasOpen = useRef(open);
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
        trigger={['hover', 'click']}
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
          onClick={(e) => e.stopPropagation()} // 仅止冒泡；开合交还 antd trigger（v4.2 双写修复：删手动 toggle）
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
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
