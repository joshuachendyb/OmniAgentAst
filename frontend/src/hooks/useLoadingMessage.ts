import { useRef, useCallback } from 'react';
import { message } from 'antd';

interface UseLoadingMessageOptions {
  duration?: number;
}

export const useLoadingMessage = (options: UseLoadingMessageOptions = {}) => {
  const { duration = 0 } = options;
  
  const loadingRef = useRef<(() => void) | null>(null);

  const show = useCallback((content: string, key: string = 'loading') => {
    if (loadingRef.current) {
      loadingRef.current();
      loadingRef.current = null;
    }
    
    const hide = message.loading({
      content,
      key,
      duration,
    });
    
    loadingRef.current = hide;
    return hide;
  }, [duration]);

  const hide = useCallback((key: string = 'loading') => {
    if (loadingRef.current) {
      loadingRef.current();
      loadingRef.current = null;
    }
    message.destroy(key);
  }, []);

  const hideAll = useCallback(() => {
    if (loadingRef.current) {
      loadingRef.current();
      loadingRef.current = null;
    }
    message.destroy();
  }, []);

  return { show, hide, hideAll };
};