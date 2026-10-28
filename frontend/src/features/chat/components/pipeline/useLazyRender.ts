// 编辑历史: 2026-10-28 小欧 - 新建: P2 渐进式渲染 hook(历史回放分批加载, 与 useStepRenderPrefs 同范式)
//   职责单一: 只管"分批调度"(visibleCount state + IntersectionObserver + 渲染期同步重置),
//   消费方只拿 visibleItems/sentinelRef/hasMore 三件套, 渲染逻辑零侵入 — 小欧-2026-10-28
// 编辑历史: 2026-10-28 小欧 - 三堂会审复核新增修复:
//   ①visibleItems useMemo 包裹(防每次渲染 slice 新数组, 全量已加载完时直接返回 items 零拷贝);
//   ②enabled 从 false 变 true(实时流结束)时保持全量(防内容收缩到首批, 用户丢失底部位置) — 小欧-2026-10-28
/**
 * useLazyRender - 渐进式分批渲染 hook
 *
 * 【小欧 2026-10-28 P2】历史回放场景段数可达数千, 一次性挂载 DOM 冻结浏览器。
 * 本 hook 封装"首批渲染 N 段 → 哨兵进入视口预加载下一批"的分批调度逻辑,
 * 使消费方组件只关注"渲染哪些段", 不关心"怎么分批"。
 *
 * - enabled=true 时分批: 首批 initialBatch 段, IntersectionObserver 哨兵进入 rootMargin 预加载圈
 *   时加载下一批 loadBatch 段, setTimeout(0) 给浏览器喘息渲染;
 * - enabled=false 时全量: 直接返回 items(流式场景打字机/等待图标依赖末段位, 分批会丢失末段判定);
 * - items 引用变化(任务切换)时渲染期同步重置 visibleCount(prevItemsRef 哨兵, 与 RightViewer
 *   prevActiveTaskIdRef 同范式), 不用 effect(防一帧闪现: effect 在渲染后执行, 首帧仍用旧 visibleCount
 *   渲染过多段导致冻结一帧再收缩)。
 *
 * @author 小欧
 * @date 2026-10-28
 */
import { useState, useRef, useEffect, useMemo, type RefObject } from 'react';

const DEFAULT_INITIAL_BATCH = 80;
const DEFAULT_LOAD_BATCH = 80;
const DEFAULT_ROOT_MARGIN = '400px';

export interface LazyRenderResult<T> {
  /** 实际要渲染的段(enabled=false 时为全量, enabled=true 时为前 visibleCount 段) */
  visibleItems: T[];
  /** 哨兵 div 的 ref, 消费方在渲染列表末尾挂载 `{hasMore && <div ref={sentinelRef} />}` */
  sentinelRef: RefObject<HTMLDivElement>;
  /** 是否还有未渲染段(hasMore=true 时哨兵挂载, IntersectionObserver 观察其进入视口) */
  hasMore: boolean;
}

/**
 * @param items 全量段数组
 * @param enabled 是否启用懒加载(流式模式传 false → 全量渲染)
 * @param initialBatch 首批渲染段数(默认 80, 约 2~3 屏)
 * @param loadBatch 每次滚动加载段数(默认 80)
 * @param rootMargin IntersectionObserver 预加载距离(默认 400px, 哨兵进入视口前即触发)
 */
export const useLazyRender = <T>(
  items: T[],
  enabled: boolean,
  initialBatch: number = DEFAULT_INITIAL_BATCH,
  loadBatch: number = DEFAULT_LOAD_BATCH,
  rootMargin: string = DEFAULT_ROOT_MARGIN
): LazyRenderResult<T> => {
  const [visibleCount, setVisibleCount] = useState(initialBatch);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // 渲染期同步重置: items 引用变化(任务切换)或 enabled 变化(实时流结束)时更新 visibleCount。
  // 不用 useEffect(渲染后执行, 首帧仍用旧 visibleCount 渲染过多段 → 冻结一帧再收缩 → 用户可见闪现)。
  // 与 RightViewer prevActiveTaskIdRef 哨兵同范式(渲染期同步, 当前帧即生效)。
  // 2026-10-28 三堂会审复核新增: enabled 从 false 变 true(实时流结束)时保持全量——
  //   实时流期间用户已看到全量内容(全量渲染), 若重置为首批会内容收缩到 80 段, 用户丢失正在看的底部位置;
  //   保持全量(items.length)则 DOM 复用(React diff), 内容不变。刷新后重新打开历史会话(挂载时 enabled=true)
  //   不受影响(prevEnabledRef 挂载时初始化, 不触发), 仍分批加载。
  const prevItemsRef = useRef(items);
  const prevEnabledRef = useRef(enabled);
  const wasEnabled = prevEnabledRef.current;
  const itemsChanged = prevItemsRef.current !== items;
  const enabledChanged = prevEnabledRef.current !== enabled;
  if (itemsChanged || enabledChanged) {
    prevItemsRef.current = items;
    prevEnabledRef.current = enabled;
    // wasEnabled=false && enabled=true → 实时流结束, 保持全量防收缩; 否则(任务切换/数据更新) → 重置为首批
    setVisibleCount(!wasEnabled && enabled ? items.length : initialBatch);
  }

  const hasMore = enabled && visibleCount < items.length;

  // 哨兵进入视口预加载圈 → 加载下一批(setTimeout(0) 允许浏览器在批次间渲染, 防 IO 回调同步批量加载卡死)
  useEffect(() => {
    if (!hasMore) return;
    const sentinel = sentinelRef.current;
    if (!sentinel) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setTimeout(() => {
            setVisibleCount((prev) => Math.min(prev + loadBatch, items.length));
          }, 0);
        }
      },
      { rootMargin }
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, items.length, loadBatch, rootMargin]);

  // 2026-10-28 三堂会审复核新增: useMemo 包裹 visibleItems, 避免每次渲染重新 slice 分配新数组。
  //   enabled=false(流式) 或 全量已加载完(visibleCount>=items.length) → 直接返回 items(引用稳定, 零拷贝);
  //   enabled=true 且分批中 → 才 slice(仅 visibleCount 变化时才重新计算, 其他渲染复用缓存)。
  const visibleItems = useMemo(
    () =>
      enabled && visibleCount < items.length
        ? items.slice(0, visibleCount)
        : items,
    [enabled, items, visibleCount]
  );

  return { visibleItems, sentinelRef, hasMore };
};
