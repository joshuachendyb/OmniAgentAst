// 编辑历史: 2026-10-28 小欧 - 新建：chip 链接旁的「别针」引用按钮（FileRefChip / FilePathLink
//   共用单点），交互口径与文件足迹(FileTrailPanel)同款：点击 → quote* → toast — 小欧-2026-10-28
// 2026-10-28 小欧 - 三堂会审整改（YAGNI）：删无人使用的 name?: string 可选 prop（两个调用方
//   全走缺省分支），label 固定取路径末段（与足迹 f.name 同口径）；props 收敛为 path+lineRange
//   两项（ISP：接口只留真实使用的形状）。— 小欧-2026-10-28
// 2026-10-30 小欧 - 提示改调 quoteWithToast(成功/超限/读取失败三分支唯一实现), label 取 labelOf
//   (兼容 `\` 路径) — 小欧-2026-10-30
/**
 * QuoteButton —— 行内 chip / 链接旁的引用按钮（icon-only 别针）
 *
 * 为什么收口（DRY）：正文 chip（FileRefChip）与统计块链接（FilePathLink）都要引用入口，
 *   读盘/组装/入队已在 quote.ts 唯一实现（quoteFile/quoteSelection），本组件只做
 *   「调 quote* + 弹提示」这一件事；再开第二份提示文案就是分叉。
 *
 * 交互口径（与足迹面板完全一致）：
 * - 成功 toast `已引用「末段名」到对话`；失败按 reason 分支（2026-10-30 小欧 A7）：
 *   too_many → "一次最多引用 20 项"；其余 → "引用内容读取失败，请重试"。
 *   原实现把超限也报成"读取失败"，用户会去检查一个根本没坏的文件。
 * - 行区间语义：带 lineRange 走 quoteSelection 引选区（与足迹/任务卡口径一致）。
 * - 就地收集不导航：composerRefStore 由 ChatInput 订阅自动消费（同页无路由扰动）。
 * - stopPropagation：按钮与链接同处一个行内容器，防误触发外层 chip 跳转。
 * - 读盘分流（根内相对 readFile / 盘符绝对 readExternalFile）quote.ts 内部自理，
 *   本组件不做归一化（KISS）。
 */
import React from 'react';
import { PaperClipOutlined } from '@ant-design/icons';
import { quoteWithToast } from './quoteToast'; // 提示三分支唯一实现(成功/超限/读取失败)
import { labelOf } from './identity';
import { Colors } from '@/utils/stepStyles';

export interface QuoteButtonProps {
  /** 引用目标路径（原样传入；形态判界在调用方，读盘分流在 quote.ts） */
  path: string;
  /** 行区间（可选）；给定走 quoteSelection 引选区 */
  lineRange?: { start: number; end: number } | null;
}

const QuoteButton: React.FC<QuoteButtonProps> = ({
  path,
  lineRange = null,
}) => {
  const label = labelOf(path);
  const quote = async (): Promise<void> => {
    // 2026-10-30 小欧: 提示统一由 quoteWithToast 给出(此处节奏: 失败也是同一套文案, 不再各写一份)
    await quoteWithToast(path, lineRange, { label });
  };
  return (
    <button
      type="button"
      title="引用到对话"
      aria-label={`把 ${label} 引用到对话`}
      onClick={(e) => {
        e.stopPropagation(); // 别针≠链接：不触发外层 chip 的跳转
        void quote();
      }}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        border: 'none',
        background: 'transparent',
        cursor: 'pointer',
        color: Colors.PRIMARY,
        padding: '0 2px',
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      <PaperClipOutlined />
    </button>
  );
};

export { QuoteButton };
