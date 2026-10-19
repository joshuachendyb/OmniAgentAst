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
/**
 * InputCore - 输入框本体（多行）
 *
 * 【小欧 2026-08-26 8.12】4.3.6 整体高度默认 3 行、最高 5 行(含底部功能按钮行)：
 * 输入框 autoSize minRows=1 / maxRows=4(2026-10-20 起步 1 行, 按钮区入框后空态总高原对齐)，加 SubmitBar 1 行 = 整体 ≤5；
 * 超 5 行输入框内部滚动（滚动非截断）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useRef } from 'react';
import { Input } from 'antd';
import { Colors, Radius, Spacing } from '@/utils/stepStyles';

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
  /** 2026-10-20 小欧 - 框内右下角动作插槽(发送/停止/暂停); 不传则不渲染挂点且不留 padding — 小欧-2026-10-20 */
  actions?: React.ReactNode;
}

// 按钮区预留高度: 钮高 34 + 底距 Spacing.MD(8) + 呼吸 Spacing.XS(4); 随 SubmitActions 的 BTN 联动
const ACTION_RESERVE = 34 + 8 + 4;

const InputCore: React.FC<InputCoreProps> = ({
  value,
  onChange,
  onPressEnter,
  onKeyDown,
  focusKey,
  actions,
}) => {
  const taRef = useRef<HTMLTextAreaElement | null>(null);
  // 2026-10-13 14:20 小欧: focusKey 自增 → 聚焦
  useEffect(() => {
    if (focusKey === undefined) return;
    taRef.current?.focus();
  }, [focusKey]);

  return (
    // 2026-10-20 小欧: relative 容器承载框内右下角动作挂点; 无 actions 时为透传 div 不改视觉
    <div style={{ position: 'relative' }}>
      <TextArea
        ref={taRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onPressEnter={onPressEnter}
        placeholder="输入消息，Shift+Enter 换行"
        // 2026-10-20 小欧 - minRows 1: 起步 1 行, 加 46px 按钮区后空态总高与改造前(3行无按钮区)持平; maxRows 4 不变
        autoSize={{ minRows: 1, maxRows: 4 }}
        style={{
          borderColor: Colors.BORDER.LIGHT,
          borderTop: `1px solid ${Colors.BORDER.LIGHT}`, // 定案 B: 顶部分隔线归属 input 区上沿
          borderRadius: Radius.SM,
          // 2026-10-20 小欧: 仅 actions 存在时预留, 防文字流到按钮底下
          ...(actions ? { paddingBottom: ACTION_RESERVE } : null),
        }}
      />
      {actions && (
        <div
          style={{
            position: 'absolute',
            right: Spacing.MD,
            bottom: Spacing.MD,
            display: 'flex',
            alignItems: 'center',
          }}
        >
          {actions}
        </div>
      )}
    </div>
  );
};

export { InputCore };
