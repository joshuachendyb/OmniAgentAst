// 编辑历史: 2026-08-27 小欧 - 修复ctx-1/ctx-2/ctx-4: 按key精确控制loading, 卸载清理, 不再message.destroy()误清全局队列
import { useRef, useCallback, useEffect } from 'react';
import { message } from 'antd';

interface UseLoadingMessageOptions {
  duration?: number;
}

export const useLoadingMessage = (options: UseLoadingMessageOptions = {}) => {
  const { duration = 0 } = options;

  // 2026-08-27 小欧 修复: 用 Map 记录每个 key 对应的 hide 函数, 支持按 key 精确隐藏
  const hideFns = useRef<Map<string, () => void>>(new Map());
  const activeKey = useRef<string | null>(null);

  const show = useCallback((content: string, key: string = 'loading') => {
    // 2026-08-27 小欧 修复ctx-2: 先隐藏上一条进行中的 loading(单loading语义), 再创建新的
    if (activeKey.current) {
      const prev = hideFns.current.get(activeKey.current);
      if (prev) prev();
      hideFns.current.delete(activeKey.current);
    }

    const hide = message.loading({
      content,
      key,
      duration,
    });

    hideFns.current.set(key, hide);
    activeKey.current = key;
    return hide;
  }, [duration]);

  const hide = useCallback((key: string = 'loading') => {
    // 2026-08-27 小欧 修复ctx-2: 仅当 key 与当前活动 loading 一致时才隐藏, 精确控制不误伤其它
    if (activeKey.current === key) {
      const fn = hideFns.current.get(key);
      if (fn) fn();
      activeKey.current = null;
      hideFns.current.delete(key);
    }
  }, []);

  const hideAll = useCallback(() => {
    // 2026-08-27 小欧 修复ctx-1: 只调用各 loading 自身的 hide, 不调用 message.destroy()(无参会清空全局队列, 误删业务 toast)
    if (activeKey.current) {
      const fn = hideFns.current.get(activeKey.current);
      if (fn) fn();
      activeKey.current = null;
    }
    hideFns.current.forEach((fn) => fn());
    hideFns.current.clear();
  }, []);

  // 2026-08-27 小欧 修复ctx-4: 组件卸载时清理进行中的全局 loading 消息, 防止泄漏
  useEffect(() => {
    return () => {
      if (activeKey.current) {
        const fn = hideFns.current.get(activeKey.current);
        if (fn) fn();
        activeKey.current = null;
      }
      hideFns.current.forEach((fn) => fn());
      hideFns.current.clear();
    };
  }, []);

  return { show, hide, hideAll };
};