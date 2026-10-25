// 编辑历史: 2026-08-26 小欧 - 8.12 实施: 输入框本体多行, 高度3-5行, 超5行内部滚动(4.3.6)
// 编辑历史: 2026-08-28 小欧 - ①D/d1: 边框收敛至 Colors.BORDER.LIGHT #f0f0f0, 令牌化
// 编辑历史: 2026-09-09 小欧 - 定案 B: 顶部分隔线归属 input 区上沿(紧贴 TaskInfoBar 下沿) — 小欧-2026-09-09
// 编辑历史: 2026-10-13 13:45 小欧 - 新增可选 onKeyDown 上抛, 供 ChatInput 做历史翻动判定
//   (IME 组字期不劫持 + 光标在首/末行才劫持 ↑↓); 可选 prop, 既有调用方零影响 — 小欧-2026-10-13
// 编辑历史: 2026-10-13 14:20 小欧 - 新增可选 focusKey: 自增即把焦点拉回输入框。全仓原本无"发送后归还焦点"的
//   逻辑, 点「发送」后焦点停在按钮、↑↓ 到不了 textarea; focusKey 是不穿透组件边界的触发口
// 编辑历史: 2026-10-13 18:40 小欧 - 文档[30] §2.5: 删 disabled prop(已成死参, 输入框恒可编辑);
//   onPressEnter 改收事件, 由调用方按"能否发送"决定发 or 换行(原先无条件 preventDefault 致执行中打不了多行)
// 编辑历史: 2026-10-20 小欧 - 新增可选 actions 插槽: 动作按钮组(发送/停止/暂停)移入框内右下角(北京老陈指令);
//   textarea 补 paddingBottom 预留按钮区防文字被遮, 预留高随 SubmitActions 钮规格联动 — 小欧-2026-10-20
// 编辑历史: 2026-10-20 小欧 - minRows 3→1(北京老陈拍板): 按钮区 46px 纯新增叠加在原 3 行上致空态 118px
//   (比改造前 68px 多约 2.3 行视觉), 框外左侧控件行未省; 文字区起步压回 1 行使空态总高与改造前持平
//   (1行22+按钮区46+边框≈68px), maxRows=4 打字空间不变 — 小欧-2026-10-20
// 2026-10-25 小欧 - 删 actions 插槽(北京老陈指令): 动作按钮组回迁 SubmitBar 行右端, 框内不再需要
//   actions 挂点/paddingBottom/relative 容器, 连带删 ACTION_RESERVE 与 Spacing import; minRows 1→3 复原
//   (按钮区不再叠加框内, 原压行理由消失, 空态总高回归改造前 68px) — 小欧-2026-10-25
/**
 * InputCore - 输入框本体（多行）
 *
 * 【小欧 2026-08-26 8.12】4.3.6 整体高度默认 3 行、最高 5 行(含底部功能按钮行)：
 * 输入框 autoSize minRows=3 / maxRows=4,加 SubmitBar 1 行 = 整体 ≤5;
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
  /**
   * 上抛回车事件, 由调用方决定是否发送。
   * 2026-10-13 18:40 小欧 - 文档[30] §2.5: 原先本组件无条件 `if(!shiftKey) preventDefault()` 后发送,
   *   导致「执行中不可发送」时按回车既不换行也不发送 —— 用户打不了多行消息(功能退化)。
   *   改为把事件交回调用方: 不可发送时不 preventDefault, 回车自然换行。
   */
  onPressEnter: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  /** 上抛键盘事件给 ChatInput(IME 组字期放行 + 仅首/末行才劫持 ↑↓ 翻历史); 可选, 既有调用方零影响 */
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void;
  /** 自增即把焦点拉回输入框; 不传则不做任何聚焦(既有调用方行为不变) */
  focusKey?: number;
  /**
   * 2026-10-21 小杨 - 外抛 textarea ref（供 @ 补全取**真实光标位置**）。
   *   体验审计发现：@ 补全原先用 `value.length` 当光标 → 光标不在末尾时误触发/漏触发。
   *   不传则行为不变（既有调用方零影响）。
   */
  inputRef?: React.MutableRefObject<HTMLTextAreaElement | null>;
}

const InputCore: React.FC<InputCoreProps> = ({
  value,
  onChange,
  onPressEnter,
  onKeyDown,
  focusKey,
  inputRef,
}) => {
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  // 2026-10-21 小杨 - 外部 ref 同步（@ 补全取真实光标位置用）
  useEffect(() => {
    if (!inputRef) return;
    inputRef.current = taRef.current;
  }, [inputRef]);
  // 2026-10-13 14:20 小欧: focusKey 自增 → 聚焦
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
      onPressEnter={onPressEnter}
      placeholder="输入消息，Shift+Enter 换行"
      autoSize={{ minRows: 3, maxRows: 4 }}
      style={{
        borderColor: Colors.BORDER.LIGHT,
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`, // 定案 B: 顶部分隔线归属 input 区上沿
        borderRadius: Radius.SM,
      }}
    />
  );
};

export { InputCore };
