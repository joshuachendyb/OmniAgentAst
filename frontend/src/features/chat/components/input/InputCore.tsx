// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 输入框本体多行, 高度3-5行, 超5行内部滚动(4.3.6)
// 编辑历史: 2026-08-28 小欧 - ①D/d1: 边框收敛至 Colors.BORDER.LIGHT #f0f0f0, 令牌化
// 编辑历史: 2026-09-09 小欧 - 定案 B: 顶部分隔线归属 input 区上沿(紧贴 TaskInfoBar 下沿) — 小欧-2026-09-09
// 编辑历史: 2026-10-13 13:45 小欧 - 新增可选 onKeyDown 上抛, 供 ChatInput 做历史翻动判定
//   (IME 组字期不劫持 + 光标在首/末行才劫持 ↑↓); 可选 prop, 既有调用方零影响 — 小欧-2026-10-13
// 编辑历史: 2026-10-13 14:20 小欧 - 新增可选 focusKey: 自增即把焦点拉回输入框。全仓原本无"发送后归还焦点"的
//   逻辑, 点「发送」后焦点停在按钮、↑↓ 到不了 textarea; focusKey 是不穿透组件边界的触发口, 且不改 disabled 语义
/**
 * InputCore - 输入框本体（多行）
 *
 * 【小欧 2026-08-26 8.12】4.3.6 整体高度默认 3 行、最高 5 行(含底部功能按钮行)：
 * 输入框 autoSize minRows=3 / maxRows=4，加 SubmitBar 1 行 = 整体 ≤5；
 * 超 5 行输入框内部滚动（滚动非截断）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useRef } from 'react';
import { Input } from 'antd';
import { Colors, Radius } from '@/utils/stepStyles';

const { TextArea } = Input;

interface InputCoreProps {
  value: string;
  onChange: (v: string) => void;
  onPressEnter: () => void;
  /** 上抛键盘事件给 ChatInput(IME 组字期放行 + 仅首/末行才劫持 ↑↓ 翻历史); 可选, 既有调用方零影响 */
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  /** 自增即把焦点拉回输入框; 不传则不做任何聚焦(既有调用方行为不变) */
  focusKey?: number;
  disabled?: boolean;
}

const InputCore: React.FC<InputCoreProps> = ({
  value,
  onChange,
  onPressEnter,
  onKeyDown,
  focusKey,
  disabled,
}) => {
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  // 2026-10-13 14:20 小欧: focusKey 自增 → 聚焦。disabled 期间 focus() 是空操作,
  //   故 ChatInput 需在输入框解除禁用后再自增一次(见其 sendBlocked 迁移 effect)
  useEffect(() => {
    if (focusKey === undefined) return;
    taRef.current?.focus();
  }, [focusKey]);

  return (
    <TextArea
      ref={taRef}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      onPressEnter={(e) => {
        if (!e.shiftKey) {
          e.preventDefault();
          onPressEnter();
        }
      }}
      placeholder="输入消息，Shift+Enter 换行"
      autoSize={{ minRows: 3, maxRows: 4 }}
      disabled={disabled}
      style={{
        borderColor: Colors.BORDER.LIGHT,
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`, // 定案 B: 顶部分隔线归属 input 区上沿
        borderRadius: Radius.SM,
      }}
    />
  );
};

export { InputCore };
