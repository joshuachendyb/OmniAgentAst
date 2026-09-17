// 编辑历史: 2026-09-14 小欧 - [37]光标问题修复链路: TextStream/ThinkingStream 两处相同的 CURSOR 翻转检测打点
//   (prevRef + useEffect + false→true 才 log) 抽取为公共 hook(DRY), label 由调用方传入 — 小欧-2026-09-14
import { useEffect, useRef } from 'react';
import { formatDebugTime } from '@/utils/time'; // 2026-09-14 小欧 [37]: 时间戳复用 — 小欧-2026-09-14

/**
 * useRiseLog - 状态上升沿(false→true)打点一条调试日志
 *
 * 【小欧 2026-09-14 [37]】光标点亮瞬间打点, ref 去重 StrictMode 双渲染; 格式 [HH:MM:SS.mmm] LABEL 与旧 pipe 一致
 *
 * @param label 日志标签(如 'CURSOR T' / 'CURSOR F')
 * @param showing 目标状态(点亮条件)
 */
export const useRiseLog = (label: string, showing: boolean): void => {
  const prevShowingRef = useRef(false);
  useEffect(() => {
    if (showing && !prevShowingRef.current) {
      console.log(`${formatDebugTime()} ${label}`); // 2026-09-14 小欧 [37]: 点亮瞬间打点(翻转去重) — 小欧-2026-09-14
    }
    prevShowingRef.current = showing;
  }, [showing, label]);
};