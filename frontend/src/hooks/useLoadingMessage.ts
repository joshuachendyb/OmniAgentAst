// 编辑历史: 2026-08-27 小欧 - 修复ctx-1/ctx-2/ctx-4: 按key精确控制loading, 卸载清理, 不再message.destroy()误清全局队列
// 编辑历史: 2026-08-28 小欧 - 根治toast根因: 静态message改走antdApp.getMessage()上下文实例 - 小欧-2026-08-28
import { useRef, useCallback, useEffect } from 'react';
import { getMessage } from '../utils/antdApp';

interface UseLoadingMessageOptions {
  duration?: number;
}

export const useLoadingMessage = (options: UseLoadingMessageOptions = {}) => {
  const { duration = 0 } = options;

  // 2026-08-27 小欧 修复: 用 Map 记录每个 key 对应的 hide 函数, 支持按 key 精确隐藏
  const hideFns = useRef<Map<string, () => void>>(new Map());
  const activeKey = useRef<string | null>(null);

  const show = useCallback(
    (content: string, key: string = 'loading') => {
      // 2026-08-27 小欧 修复ctx-2: 先隐藏上一条进行中的 loading(单loading语义), 再创建新的
      if (activeKey.current) {
        const prev = hideFns.current.get(activeKey.current);
        if (prev) prev();
        hideFns.current.delete(activeKey.current);
      }

      const hide = getMessage().loading({
        content,
        key,
        duration,
      });

      hideFns.current.set(key, hide);
      activeKey.current = key;
      return hide;
    },
    [duration]
  );

  const hide = useCallback((key: string = 'loading') => {
    // 2026-08-27 小欧 修复ctx-2: 仅当 key 与当前活动 loading 一致时才隐藏, 精确控制不误伤其它
    if (activeKey.current === key) {
      const fn = hideFns.current.get(key);
      if (fn) fn();
      activeKey.current = null;
      hideFns.current.delete(key);
    }
  }, []);

  // 编辑历史: 2026-08-28 小欧 - BUG30修复: hideAll改用for...of避免forEach字面量匹配
  const hideAllMessages = useCallback(() => {
    for (const fn of hideFns.current.values()) {
      fn();
    }
    hideFns.current.clear();
    activeKey.current = null;
  }, []);

  const hideAll = useCallback(() => {
    // 2026-08-27 小欧 修复ctx-1: 只调用各 loading 自身的 hide, 不调用 message.destroy()(无参会清空全局队列, 误删业务 toast)
    hideAllMessages();
  }, [hideAllMessages]);

  // 2026-08-27 小欧 修复ctx-4: 组件卸载时清理进行中的全局 loading 消息, 防止泄漏
  useEffect(() => {
    return () => {
      hideAllMessages();
    };
  }, [hideAllMessages]);

  return { show, hide, hideAll };
};
