// 编辑历史: 2026-10-06 小欧 - MarkdownSlot 上移中立层后改指 @/components/markdown/MarkdownSlot(原 ../pipeline/MarkdownSlot), 内容未改。 — 小欧-2026-10-06
// 编辑历史: 2026-08-30 小欧 - 13.8 实施: 正文 text 段真逐字打字机(打字机效果+末位光标), 回放/终态整段静态(13.8.5);
//   集成 13.10 step 间段距与 13.11 空行规约(normalizeBlankLines 尾随守卫);
//   2026-08-30 北京老陈定案纠正(step间8/内部6/折叠4): 主段12px(LG)废止 → margin 默认 MD(8)=step 间段距, compact=SM(6)=同 step 内部 - 小欧-2026-08-30
//   2026-08-30 北京老陈新定案(step间6/内部4/折叠2=常量-2派生): 段距走 stepMargin → 默认=(MD)-2=6, compact=(SM)-2=4, 数值不写死 - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: TS-01 interval达终态即clear防CPU空转(原clear仅在unmount, 打完后仍空转) — 小欧-2026-09-02
// 编辑历史: 2026-09-14 小欧 - 思考光标不显示问题修复(北京老陈驱动): 光标条件删 shown<clean.length
//   打字机进度门槛(打字机追平即灭→光标大部分时间消失病根), 改 bind 末段+流式进行中恒亮; CURSOR F 打点下放本组件
//   反转检测(false→true 才打, ref 去重 StrictMode 双渲染) — 小欧-2026-09-14
//   2026-09-14 小欧 - DRY: 反转检测打点抽取公用 hook useRiseLog(与 ThinkingStream 同款逻辑去重) — 小欧-2026-09-14
// 编辑历史: 2026-09-14 小欧 - 正文末位光标换型(北京老陈驱动): 静态<span>▍</span>(无动画)→复用 WaitingIcons/ActionWaitingIcon(蓝#1677ff核心圆+双层波纹扩散, 复用既有CSS零新增, 清理后首次启用) — 小欧-2026-09-14
// 编辑历史: 2026-09-17 小欧 - 实施: 新增 waitClock prop, 打字机末位波纹光标 ActionWaitingIcon 挂钟面并存 - 小欧-2026-09-17
// 编辑历史: 2026-10-05 小欧 - 新增 markdown prop 接「思考排版」开关(文档[9] §5.8): 开=按Markdown 渲染本段, 关=原样纯文本(旧行为不变); 打字机切片在前、渲染在后, 两层不干涉 — 小欧-2026-10-05
/**
 * TextStream - 正文打字机（真逐字 + 末位光标）
 *
 * 【小欧 2026-08-30 13.8】13.8.4 方案1 落地：streaming 实时按"已累积文本"逐字微延迟流出、
 * 末位等待圈（复用 ActionWaitingIcon 蓝色波纹扩散）；streaming 结束/历史回放整段静态呈现。
 * 内置 normalizeBlankLines（13.11）：流式走尾随守卫(防打字机回缩)、终态统一 trim。
 *
 * @author 小欧
 * @date 2026-08-30
 */
import React, { useEffect, useRef, useState } from 'react';
import { getStreamStyle } from '@/utils/stepStyles';
import { normalizeBlankLines } from '@/utils/textNormalize';
import { useRiseLog } from '@/features/chat/hooks/useRiseLog'; // 2026-09-14 小欧: CURSOR F 翻转打点(抽公用 hook) — 小欧-2026-09-14
import { ActionWaitingIcon } from '@/components/WaitingIcons'; // 2026-09-14 小欧: 正文末位光标换型(蓝色波纹扩散圈) — 小欧-2026-09-14
import type { ClockSignals } from '@/types/sse'; // 2026-09-17 小欧 实施: 钟面信号类型 — 小欧-2026-09-17
// 2026-10-05 小欧 v3.9: lazy + Suspense + 纯文本 fallback 三件事已抽到 MarkdownSlot(唯一入口),
//   思考内容段与最终答复段共用同一开关同一逻辑, 此处不再重复一遍 —— 小欧-2026-10-05
import { MarkdownSlot } from '@/components/markdown/MarkdownSlot';

interface TextStreamProps {
  text: string;
  typing?: boolean; // 实时流且为本段累积中（打字机态）
  cursor?: boolean; // 末位闪烁光标
  compact?: boolean; // 同 step 内部(13.6 拆出的 reasoning→thought 相邻): 段距 SM(6)
  waitClock?: ClockSignals; // 2026-09-17 小欧 实施: 钟面信号(与波纹光标并存) — 小欧-2026-09-17
  /**
   * 2026-10-05 小欧 - 思考排版开关(文档[9] 方案设计 §5.8 / 北京老陈裁定「两个独立开关」):
   *   本段(thought 段)正文是否按 Markdown 语法渲染。与 reasoning 段的折叠初值开关
   *   (reasoningVisible → ThinkingStream)是两个独立开关, 互不干涉。
   *   默认 false=按纯文本(与本组件 2026-08-30 以来行为完全一致, 不退化) — 小欧-2026-10-05
   */
  markdown?: boolean;
}

const TextStream: React.FC<TextStreamProps> = ({
  text,
  typing = false,
  cursor = false,
  compact = false,
  waitClock, // 2026-09-17 小欧 实施
  markdown = false, // 2026-10-05 小欧: 思考排版(默认关=纯文本旧行为) — 小欧-2026-10-05
}) => {
  const clean = normalizeBlankLines(text, { streaming: typing });
  const [shown, setShown] = useState(0);
  const timerRef = useRef<number | null>(null);
  // 2026-09-14 小欧: 光标真实显示条件(修复后=末段+流式中, 已去 shown<clean.length 打字机进度门槛) + 翻转打点
  const showing = cursor && typing;
  useRiseLog('CURSOR F', showing);

  useEffect(() => {
    if (!typing) {
      setShown(clean.length); // 终态/回放: 整段静态
      return;
    }
    // 打字机: 已显示进度回续(单调递增不回缩), 步进按长度自适应(短文逐字、长文加速, ≤4s 打完)
    const step = Math.max(1, Math.ceil(clean.length / 240));
    timerRef.current = window.setInterval(() => {
      setShown((prev) => {
        if (prev >= clean.length) {
          if (timerRef.current) window.clearInterval(timerRef.current);
          return prev;
        }
        const next = prev + step;
        if (next >= clean.length) {
          if (timerRef.current) window.clearInterval(timerRef.current);
          return clean.length;
        }
        return next;
      });
    }, 16);
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
  }, [clean, typing]);

  return (
    <div style={getStreamStyle(compact)}>
      {/* 2026-10-05 小欧 - 「思考排版」开关(文档[9] §4.2/§5.8): markdown=false 时走 2026-10-04 前的
          原纯文本切片路径, 一字不改; markdown=true 时把同一份打字机切片喂 MarkdownText
          (切片是不完整源码, 由 findUnclosedFenceTail 按未闭合围栏规则兜住, 见 §3.1)。
          光标永远在 Markdown 之外, 不进解析器。lazy/Suspense/fallback 已抽到 MarkdownSlot。 */}
      <MarkdownSlot
        text={clean.slice(0, typing ? shown : clean.length)}
        markdown={markdown}
      />
      {cursor && typing && <ActionWaitingIcon waitClock={waitClock} />}{' '}
      {/* 2026-09-17 小欧: 波纹与钟面并存(追加) — 小欧-2026-09-17 */}
    </div>
  );
};

export { TextStream };
