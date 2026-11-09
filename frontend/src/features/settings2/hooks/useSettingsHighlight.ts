// 编辑历史: 2026-11-09 小欧 - 新建：搜索命中高亮与 4s TTL 定时器（原 useSettings 内联逻辑原样搬迁）— 小欧-2026-11-09
import { useCallback, useRef, useState } from 'react';

// 高亮 TTL(4s) + 新跳转生效前清旧 timer：原 2s 且不清理 timer，连续搜索时旧 timer 会提前熄灭新高亮
const HIGHLIGHT_TTL = 4000;

export function useSettingsHighlight() {
  const [highlightKey, setHighlightKey] = useState<string | null>(null);
  const highlightTimer = useRef<number | null>(null);
  const setHighlightKeyTtl = useCallback((key: string | null) => {
    if (highlightTimer.current) window.clearTimeout(highlightTimer.current);
    setHighlightKey(key);
    if (key) {
      highlightTimer.current = window.setTimeout(
        () => setHighlightKey(null),
        HIGHLIGHT_TTL
      );
    }
  }, []);
  return { highlightKey, setHighlightKeyTtl };
}
