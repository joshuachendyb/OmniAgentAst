// 编辑历史: 2026-11-22 小欧 - 新建: 附件 raw blob 内嵌预览的取流/生命周期唯一实现。
//   收敛"带 token 取字节 → objectURL → 卸载/切换 revoke → 超时 abort → 错误态"四步,
//   供生成产物卡片(视口懒加载)与浮层 TOOL结果(打开即加载)共用, 消除两处重复的 effect。
//   复用 attachmentApi.loadRawBlob(与附件预览同一取流口), 不新写请求。 — 小欧-2026-11-22
/**
 * useAttachmentBlob — 把 attachment_id 变成可塞给 <img>/<video> 的 blob URL
 *
 * 本地附件在后端磁盘上, 浏览器裸 src 带不了 Authorization 头(必 401),
 * 故统一走 attachmentApi.loadRawBlob 带 token 取字节, 再 createObjectURL。
 * objectURL 在依赖变化/组件卸载时由 effect 清理函数 revoke, 不泄漏内存。
 */
import { useEffect, useRef, useState, type RefObject } from 'react';

import { attachmentApi } from '@/services/api/attachment.api';

/** 本地产物取流超时: 视频可达数十 MB, 30s 会误杀大文件 */
const LOAD_TIMEOUT_MS = 60_000;

export interface UseAttachmentBlobOptions {
  /** true=进入视口才取流(聊天流长列表懒加载); false=挂载即取流(浮层)。默认 false */
  lazy?: boolean;
  /** 视口提前触发距离, 仅 lazy=true 生效 */
  rootMargin?: string;
}

export interface UseAttachmentBlobResult {
  blobUrl: string;
  error: string;
  /** 挂到被观察的容器元素(lazy=true 时用于 IntersectionObserver) */
  containerRef: RefObject<HTMLDivElement>;
}

export function useAttachmentBlob(
  attachmentId: string,
  sessionId: string | null,
  options: UseAttachmentBlobOptions = {}
): UseAttachmentBlobResult {
  const { lazy = false, rootMargin = '200px' } = options;
  const [blobUrl, setBlobUrl] = useState('');
  const [error, setError] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const loadedRef = useRef(false); // lazy 下进入视口只取一次

  useEffect(() => {
    setBlobUrl('');
    setError('');
    loadedRef.current = false;
    if (!attachmentId || !sessionId) return;
    if (lazy && !containerRef.current) return;
    let alive = true;
    let objUrl = '';
    let ctrl: AbortController | null = null;
    let timer = 0;
    const startLoad = () => {
      if (loadedRef.current || !alive) return;
      loadedRef.current = true;
      ctrl = new AbortController();
      timer = window.setTimeout(() => ctrl?.abort(), LOAD_TIMEOUT_MS);
      attachmentApi
        .loadRawBlob(attachmentId, sessionId, ctrl.signal)
        .then((b) => {
          if (!alive) return;
          objUrl = URL.createObjectURL(b);
          setBlobUrl(objUrl);
        })
        .catch((e: unknown) => {
          if (!alive) return;
          setError(
            e instanceof DOMException && e.name === 'AbortError'
              ? '产物加载超时，请稍后重试'
              : '产物加载失败，文件可能已被移动'
          );
        })
        .finally(() => window.clearTimeout(timer));
    };
    let observer: IntersectionObserver | null = null;
    if (lazy && containerRef.current) {
      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((en) => en.isIntersecting)) {
            startLoad();
            observer?.disconnect();
          }
        },
        { rootMargin }
      );
      observer.observe(containerRef.current);
    } else {
      startLoad();
    }
    return () => {
      alive = false;
      observer?.disconnect();
      window.clearTimeout(timer);
      ctrl?.abort();
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [attachmentId, sessionId, lazy, rootMargin]);

  return { blobUrl, error, containerRef };
}
