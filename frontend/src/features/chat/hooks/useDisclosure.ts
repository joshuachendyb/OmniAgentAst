// 编辑历史: 2026-10-05 小欧 - 新建: 折叠/展开状态 hook(文档[9] 方案设计 §5.6)
//   动因: CollapsibleText.tsx(2026-08-30 起)与 ThinkingStream 思考行(2026-10-05)的
//   onClick/onKeyDown + stopPropagation 逻辑重复两处, 违 DRY/健壮性, 抽公用 hook 复写一次
//   行为: 与原实现零差异(Enter/Space 切换 + 全分支 stopPropagation 阻断冒泡),
//   CollapsibleText 5 处调用(TaskListPanel x3 / ResponseStream / ToolCallLine)行为不变
//   职责: 只管"切换状态 + 事件阻断", 不管阈值/折叠文案(那是 CollapsibleText 的 maxLines/maxChars,
//   ThinkingStream 的"推理内容..."标题行也别塞进来, 否则 SRP 越界) — 小欧-2026-10-05
import { useCallback, useState } from 'react';
import type {
  Dispatch,
  KeyboardEvent,
  MouseEvent,
  SetStateAction,
} from 'react';

/** 折叠切换返回值: expanded + 直接暴露 setExpanded(供"文本变化时重置"这类受控归零场景) + 两道 a11y 事件聚合 */
export interface UseDisclosureResult {
  expanded: boolean;
  /** 直接设置展开态(传初始值 / 受控归零); useState setter 引用恒稳定, 可安全进依赖数组 */
  setExpanded: Dispatch<SetStateAction<boolean>>;
  onToggleClick: (e: MouseEvent) => void;
  onToggleKeyDown: (e: KeyboardEvent) => void;
}

export const useDisclosure = (initial = false): UseDisclosureResult => {
  const [expanded, setExpanded] = useState(initial);
  const toggle = useCallback(() => setExpanded((prev) => !prev), []);
  // stopPropagation: 折叠钮嵌在信息流内, 外层有 onSelect(选中任务自动展开), 不阻断会连带选中
  //   历史 bug: 2026-08-30 左列点"展开全文"误触发外层自动展开 — 小欧-2026-08-30
  const onToggleClick = useCallback(
    (e: MouseEvent) => {
      e.stopPropagation();
      toggle();
    },
    [toggle]
  );
  const onToggleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault(); // 空格默认会滚页
        e.stopPropagation();
        toggle();
      } else {
        e.stopPropagation();
      }
    },
    [toggle]
  );
  // 2026-10-05 小欧: toggle 不导出(YAGNI: 全仓无外部取用者, 仅本 hook 内两个 handler 闭包调用) — 小欧-2026-10-05
  return { expanded, setExpanded, onToggleClick, onToggleKeyDown };
};
