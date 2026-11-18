// 2026-11-18 商量 - 新建: 倒计时唯一实现(按截止时刻采样, 不是逐秒自减)
//   WHY: 授权弹窗与 question 面板此前各写一份「首 tick 100ms + 1s interval 自减」,
//   自减在 0.1s 与 1.0s 各触发一次 → 第 1 秒掉 2 格, 展示窗口比后端真实窗口短 1 秒;
//   改为先算 deadline 再按秒采样, 展示值与真实剩余秒数对齐(单真源, 两处共用)。
import { useEffect, useState } from 'react';

/** 首个采样点(ms): 与既有视觉节奏一致(开窗后 0.1s 内即出数字), 不改变观感 */
const FIRST_SAMPLE_MS = 120;

/**
 * 倒计时剩余秒数(纯展示, 到点后恒为 0)。
 *
 * @param total   窗口总秒数(<=0 视为无倒计时, 恒返 0)
 * @param resetKey 窗口身份(新窗口必须传入新值, 否则沿用上一窗口的截止时刻)
 */
export function useCountdown(total: number, resetKey?: string | null): number {
  const [countdown, setCountdown] = useState(total);

  useEffect(() => {
    if (!total || total <= 0) {
      setCountdown(0);
      return;
    }
    const deadline = Date.now() + total * 1000;
    const sample = () =>
      setCountdown(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
    setCountdown(total);
    const interval = window.setInterval(sample, 1000);
    const first = window.setTimeout(sample, FIRST_SAMPLE_MS);
    return () => {
      window.clearInterval(interval);
      window.clearTimeout(first);
    };
    // resetKey 只承担"换窗口即重建截止时刻", 不参与计算
  }, [total, resetKey]);

  return countdown;
}
