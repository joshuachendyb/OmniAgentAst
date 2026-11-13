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
// 2026-10-25 小欧 - minRows 3→1 回调(北京老陈令): 三行空态在仅 1 行文字时空出两行, 与 SubmitBar 间
//   留白叠加致"输入框底线到按钮组"视觉距离过大; 回调 1 行起步恢复 2026-10-20 空态高度, maxRows=4 不变 — 小欧-2026-10-25
// 2026-10-25 小欧 - minRows 1→2 定案(北京老陈令): 1 行起步过扁, 2 行起步留一行输入余量更显舒展, 仍远低于 3 行的框内空白 — 小欧-2026-10-25
// 2026-10-25 小欧 - 新增 executingHint 可选 prop(北京老陈令): 执行中且输入框为空时, placeholder 区追加橘红色提示
//   (overlay 绝对定位, 隐藏原生 placeholder, 灰+橘红双层渲染); 不传/非空态行为不变 — 小欧-2026-10-25
// 2026-10-26 小欧 - overlay 内层 div 加 data-testid="receiving-hint"(保 H3/H9/H10 e2e 定位);
//   加在内层而非外层 wrapper —— 外层含 placeholder 灰字+橘红提示两行, toHaveText 会取全文导致 H3 断言不匹配 — 小欧-2026-10-26
// 2026-10-28 小欧 - ① maxRows 4→3(北京老陈令: 输入框最高 3 行, 整体含 SubmitBar ≤4);
//   ② minRows/maxRows 字面量改用 layout.ts INPUT_MIN_ROWS/INPUT_MAX_ROWS(消除内部字面量, 唯一定义点);
//   ③ 字面量令牌化: borderTop 1px→BorderWidth.THIN, overlay top 6→Spacing.SM,
//   fontSize 14→FontSize.PRIMARY / 12→FontSize.SECONDARY;
//   ④ 新增局部常量 HINT_LEFT_PX(=11, 对齐 AntD TextArea 水平 padding)/HINT_LINE_HEIGHT(=1.4, 普通文本行高)
// 2026-11-08 小欧 - placeholder 补"可直接贴公网图片链接"一句(只给格式示范, 完整外链规则在设置页「媒体」Tab) — 小欧-2026-11-08
// 2026-11-10 小欧 - placeholder 升级为编号化静态清单: 空态常驻显示 6 条输入方式([1]普通输入 [2]图片链接
//   [3]↑↓翻历史/历史输入 [4]@引用 [5]附件抽屉 [6]拖拽/粘贴), 抽 INPUT_HINTS 常量 + showHints 分支;
//   动态提示(插话/提交中, executingHint)保持原逻辑不编号; 原生 placeholder 置空由 overlay 统一承载 — 小欧-2026-11-10
// 2026-11-13 商量 - 撤销编号化清单(输入框只留核心 placeholder[1]): 6 条常驻清单随输入方式增加会塞满输入框,
//   且打字即消失、占位却不提供即时价值。原 [2]~[6] 迁入 ShortcutHelp 的「输入技巧」浮层(分组归类、可扩展),
//   输入框恢复单行原生 placeholder; 仅保留 executingHint 的橘红 overlay(真正的动态情境提示) — 商量-2026-11-13
// 2026-11-13 商量 - ① 能力提示并入 placeholder 尾段(PLACEHOLDER_HINTS: @ 引用 · 拖入文件 · 粘贴图片):
//   空态自带说明, minRows=2 已预留两行 → 零额外高度, 打字即隐不干扰;
//   ② 显式下发上下留白 4→2(TEXTAREA_PAD_Y, 取视觉下限非 1px: 圆角下首行贴边过紧),
//   overlay top 同源改用该常量, 水平 11 与 HINT_LEFT_PX 一致 — 商量-2026-11-13

// 2026-11-13 商量 - textarea 显式行高 HINT_LINE_HEIGHT(1.4), 与 overlay 提示同源:
//   原走 AntD 缺省 1.5714 致两者基线差约 1px、折行位置不一致; 统一后空态高度同步压缩 — 商量-2026-11-13

/**
 * InputCore - 输入框本体（多行）
 *
 * 【小欧 2026-08-26 8.12】4.3.6 整体高度最高 4 行(含底部功能按钮行)：
 * 输入框 autoSize minRows=2 / maxRows=3(2 行起步, 文字多自动增行),加 SubmitBar 1 行 = 整体 ≤4;
 * 超 3 行输入框内部滚动（滚动非截断）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useEffect, useRef } from 'react';
import { Input } from 'antd';
import { Colors, Radius, BorderWidth, FontSize } from '@/utils/stepStyles';
import { INPUT_MIN_ROWS, INPUT_MAX_ROWS } from '@/constants/layout';

const { TextArea } = Input;

// 2026-10-28 小欧 - placeholder 提示 overlay 定位/行高(仅本组件使用, 局部常量):
//   left=11 为框内文字左缘(AntD TextArea 水平 padding 缺省值), 现由本组件显式下发保证同源;
//   lineHeight=1.4 为普通文本行高(非等宽, 不引 MonoLineHeight)。
const HINT_LEFT_PX = 11;
const HINT_LINE_HEIGHT = 1.4;

// 2026-11-13 商量 - 输入框上下留白收口到视觉下限: 4(库缺省)→2。
//   2px 是下限而非 1px: 圆角 4px 下 1px 会让首行文字视觉贴上描边, 且与全站单行控件
//   "行盒20+留白3" 的舒展度反差过大; 2px 配合 22px 行盒仍留出约半个字身的呼吸。
//   本组件显式下发, 不依赖库缺省(与控件规格不一味沿用库默认值同源)。
const TEXTAREA_PAD_Y = 2;

// 输入框核心占位: 只保留提交语义(唯一必须一眼可见的信息)。
//   其余输入方式(翻历史/@引用/附件/拖拽/图片)的完整说明归 ShortcutHelp 浮层(「输入技巧」入口)。
const PLACEHOLDER_TEXT = '输入文本消息，Shift+Enter 换行，Enter 提交';
// 能力提示尾段(2026-11-13 商量): 极简符号 + 短词, 只在空态露出; minRows=2 已预留两行,
//   长文案也不额外增高(打字即隐), 是"零成本的能力发现位"。
const PLACEHOLDER_HINTS = '@ 引用 · 拖入文件 · 粘贴图片';
// 测试定位锚点 testid(原生 placeholder 交还给 textarea)
const HINT_TESTID = 'chat-input-textarea';

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
  /**
   * 执行中追加提示（输入框为空时以橘红色 overlay 显示，替代原生 placeholder）。
   *   不传/传 undefined 时行为不变；传入时输入框为空 → 隐藏原生 placeholder、
   *   仅显示橘红 overlay；输入框非空 → overlay 自动消失。
   */
  executingHint?: string;
}

const InputCore: React.FC<InputCoreProps> = ({
  value,
  onChange,
  onPressEnter,
  onKeyDown,
  focusKey,
  inputRef,
  executingHint,
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

  // 动态提示(执行中插话/提交中): 输入为空时以橘红 overlay 显示, 同时隐藏原生 placeholder 避免重复
  const empty = value.trim() === '';
  const showExecutingHint = !!executingHint && empty;

  return (
    <div style={{ position: 'relative' }}>
      <TextArea
        ref={taRef}
        data-testid={HINT_TESTID}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
        onPressEnter={onPressEnter}
        placeholder={
          showExecutingHint ? '' : `${PLACEHOLDER_TEXT} · ${PLACEHOLDER_HINTS}`
        }
        autoSize={{ minRows: INPUT_MIN_ROWS, maxRows: INPUT_MAX_ROWS }}
        style={{
          borderColor: Colors.BORDER.LIGHT,
          borderTop: `${BorderWidth.THIN}px solid ${Colors.BORDER.LIGHT}`, // 定案 B: 顶部分隔线归属 input 区上沿
          borderRadius: Radius.SM,
          // 显式下发上下留白(4→2), 水平与 overlay 左缘同源为 11
          padding: `${TEXTAREA_PAD_Y}px ${HINT_LEFT_PX}px`,
          // 2026-11-13 商量 - 行高与 overlay 提示同源为 HINT_LINE_HEIGHT: 原 textarea 走 AntD 缺省 1.5714,
          //   与 overlay 的 1.4 相差约 1px, 灰字/橘红提示基线错位且折行位置不同; 统一后同时压缩空态高度
          lineHeight: HINT_LINE_HEIGHT,
        }}
      />
      {showExecutingHint && (
        <div
          style={{
            position: 'absolute',
            top: TEXTAREA_PAD_Y,
            left: HINT_LEFT_PX,
            pointerEvents: 'none',
            userSelect: 'none',
            lineHeight: HINT_LINE_HEIGHT,
          }}
        >
          {/* testid 保既有 e2e 定位(overlay 是动态提示的唯一挂载点) */}
          <div
            data-testid="receiving-hint"
            style={{ color: Colors.ORANGE_RED, fontSize: FontSize.SECONDARY }}
          >
            {executingHint}
          </div>
        </div>
      )}
    </div>
  );
};

export { InputCore };
