// 编辑历史: 2026-09-09 小欧 - v4.2: 抽「上下文概览 / 事件」双浮层入口公共壳(DRY, 17 行×2 处重复收敛)
//   Popover 配置 + taskinfo-entry 热区 a11y + Enter/Space/Esc 键盘 + 单真源开合 + 焦点管理(3.8/7.3); 卡片内容/样式调用方注入 — 小欧-2026-09-09
// 编辑历史: 2026-10-10 小欧[20] 三堂会审 10 规范审计 B5 - hover 打开的浮层点击不得反向关闭: trigger
//   ['hover','click'] 共享受控 open, 鼠标未移出时无 mouseenter 纠正 → 卡在关闭态"点一下反而关掉"。记来源后
//   hover 态点击只确保打开; 键盘路径同步清标记, 不影响既有"点开再点关"契约
// 编辑历史: 2026-10-13 小欧 - 文档[29]D-7: 新增可选 prop trigger?: Array<'hover'|'click'>(默认 ['hover','click'],
//   上下文概览 / 事件 两处既有调用零变化, OCP 扩展不改既有签名) 并由 Popover 透传; 同时把 B5 补偿逻辑**按 trigger 门控**
//   (hoverTriggered = trigger.includes('hover')): onMouseEnter 仅 hover 模式置位、onClick 仅 hover 模式消费。
//   原因: onMouseEnter 原是无条件置位, 若只把 trigger 透传而不门控, 纯点击模式下会出现
//   「鼠标移入→点开→再点一次关不掉」(open && hoverOpenedRef 吃掉关闭意图), T36 必挂 — 小欧-2026-10-13
// 编辑历史: 2026-10-13 18:20 小欧 - 修实测缺陷「点浮层 ✕ 连带展开工具行 JSON 树」: 门户内容的 React 冒泡
//   不经过 trigger 上的 stopPropagation, 直达宿主行 onClick; 改在**卡片根**统一拦截一处, 全调用方受益(DRY 单一真源),
//   不再由各调用方逐个按钮打补丁(上下文概览 / 事件 及后续注入可交互 content 的调用方同样受益)
import React, { useEffect, useRef } from 'react';
import { Popover } from 'antd';

export interface FloatingEntryProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  placement: 'bottomLeft' | 'bottomRight'; // antd 真值: bottomLeft=左缘对齐向右展开(上下文概览) / bottomRight=右缘对齐向左展开(事件、工具行参数)
  /**
   * 2026-10-13 小欧 - 文档[29]§3.5/D-7: 触发方式。默认 ['hover','click'] 保持「上下文概览 / 事件」既有行为**零变化**;
   *   参数区浮层传 ['click'] 去掉悬停弹出与 B5「首击被吃掉」(本文件 :97-105)。
   */
  trigger?: Array<'hover' | 'click'>;
  cardId: string; // 卡片 id（= 入口 aria-controls，关系内聚于组件内）
  ariaLabel: string; // 入口 + 卡片共用 aria-label
  /**
   * 2026-10-13 小欧 - 北京老陈裁定: 纵向居中(横向仍按 placement 贴按钮)。
   *   病根: 贴按钮长内容时底部顶出视口 → rc-trigger 被迫上移补偿且越移越多 = 严重漂移;
   *   居中后 top=(100vh-h)/2, h≤100vh 时**永不截断**, 位移变为绕中心对称扩张。
   *   OCP: 可选 prop, 默认 false —— 「事件」浮层不传, 零影响。
   * 2026-10-14 小欧 订正: 原写「视口居中(不贴按钮)」+ OCP 称「上下文概览 / 事件」零影响 —— 两处均已失效:
   *   ①语义收敛为**纵向**居中(横向交回 rc-trigger 按 placement 贴按钮, 见 index.css
   *   .popover-viewport-centered 注释); ②「上下文概览」已传 centered, 不再零影响 — 小欧-2026-10-14
   */
  centered?: boolean;
  cardStyle?: React.CSSProperties; // 卡片容器样式（宽/布局，调用方注入）
  content: React.ReactNode; // 卡片内容（调用方注入，内部 a11y 如 role="log" 自带）
  children: React.ReactNode; // 入口热区内容（上下文概览: MetricItem / 事件: DownOutlined + "事件"）
}

/**
 * 2026-10-13 小欧 - 纵向居中挂载类(定位规则在 index.css, 因需 !important 覆盖 rc-trigger 的内联坐标)。
 * 2026-10-14 小欧 订正: 原写「视口居中…覆盖 left/top」—— 现仅接管纵向(top), 横向不写 left/translateX,
 *   交回 rc-trigger 按 placement 横向锚定(见 index.css 该规则注释) — 小欧-2026-10-14
 */
const CENTERED_CLASS = 'popover-viewport-centered';

export const FloatingEntry: React.FC<FloatingEntryProps> = ({
  open,
  onOpenChange,
  placement,
  trigger = ['hover', 'click'],
  cardId,
  ariaLabel,
  centered = false,
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
        // 2026-10-13 小欧 - 居中三件套: 关箭头 + 关 zoom 动效(动效给 .ant-popover 加 transform,
        //   会与居中的 translate 打架, 且 transform 的祖先会成为 fixed 的包含块)
        //   + 挂定位类(!important 覆盖 rc-trigger 内联坐标)。
        // 2026-10-14 小欧 订正: 原关箭头理由「居中后箭头会指在屏幕中间无对象」已失效 —— 现横向仍贴按钮,
        //   箭头指向按钮正是正确的视觉指引。此处保留关箭头系沿袭 17a057b3c 完全居中设计的顺带残留;
        //   应否解耦为独立 prop 需另行裁定, 本次仅订正注释口径不改代码 — 小欧-2026-10-14
        arrow={centered ? false : { pointAtCenter: true }}
        transitionName={centered ? '' : undefined}
        rootClassName={centered ? CENTERED_CLASS : undefined}
        content={
          <div
            ref={cardRef}
            tabIndex={-1}
            id={cardId}
            role="dialog"
            aria-label={ariaLabel}
            style={cardStyle}
            // 2026-10-13 18:20 小欧 - 修实测缺陷「点浮层 ✕ 却把工具行的 JSON 树展开了」。
            //   病根: antd Popover 的 content 是 **portal 到 body** 的, 而 React 事件冒泡走
            //   **React 组件树**、非 DOM 树 —— portal 内容在 React 树里的位置是 trigger div 的
            //   **兄弟节点**, 故其冒泡路径**根本不经过**下面 trigger 上的那个 stopPropagation,
            //   直达宿主行(ToolCallLine:332 工具行 onClick={toggleTool}) → 连带展开 JSON 树
            //   (ToolCallLine:449 isOpen 才渲染 ParamsTree)。
            //   修法取「门户自守」而非各调用方逐个打补丁: 在**卡片根**统一拦截一处, 全调用方受益
            //   (DRY 单一真源, 下一个注入可交互 content 的调用方不会再踩同一个坑);
            //   若只在某个按钮上补, 同类缺陷会在「上下文概览 / 事件」及后续调用方重复发生。
            //   不影响卡内组件自身: React 事件在 target 阶段先执行, 卡内 Segmented/CopyButton/
            //   折叠箭头照常响应, 只是不再外泄到宿主行。Esc 走 keydown, 不受此处拦截影响。
            onClick={(e) => e.stopPropagation()}
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
