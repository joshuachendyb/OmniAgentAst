// 编辑历史: 2026-09-10 小欧 - S14: 创建 useStateWithRef，封装 state/ref 双写同步（StrictMode 安全）
// 编辑历史: 2026-09-10 小欧 - S14修正: ref 改为同步赋值（setValue 调用即写 ref.current），而非在 setState updater 内赋值。
//   原因：updater 可能延迟执行（React 批处理/并发模式），导致 ref.current 在 updater 运行前仍是旧值，
//   异步回调（如 handleSSEError 读 serverTaskIdRef）拿到旧值致逻辑断裂。同步赋值保证 ref 即时可用。
//   StrictMode 安全：setValue 调用即写 ref.current + setState(next)，双执行时两次写同一值（幂等），无害。
import { useState, useRef, useCallback, type MutableRefObject } from 'react';

/**
 * useStateWithRef — state 驱动渲染 + ref 供异步回调读最新值
 *
 * 同步安全：setValue 调用即写 ref.current（不经 updater 延迟），
 * 保证异步回调（SSE error handler 等）能即时读到最新值。
 * StrictMode 安全：双执行时两次写同一值（幂等），无害。
 *
 * @returns [state, ref, setValue] — setValue 接受值或函数
 */
export function useStateWithRef<T>(
  initialValue: T
): [T, MutableRefObject<T>, (value: T | ((prev: T) => T)) => void] {
  const [state, setState] = useState<T>(initialValue);
  const ref = useRef<T>(initialValue);

  const setValue = useCallback((value: T | ((prev: T) => T)) => {
    const next = value instanceof Function ? value(ref.current) : value;
    ref.current = next;
    setState(next);
  }, []);

  return [state, ref, setValue];
}