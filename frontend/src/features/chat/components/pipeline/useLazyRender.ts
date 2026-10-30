// 编辑历史: 2026-10-28 小欧 - 新建: P2 渐进式渲染 hook(历史回放分批加载, 与 useStepRenderPrefs 同范式)
//   职责单一: 只管"分批调度"(visibleCount state + IntersectionObserver + 渲染期同步重置),
//   消费方只拿 visibleItems/sentinelRef/hasMore 三件套, 渲染逻辑零侵入 — 小欧-2026-10-28
// 编辑历史: 2026-10-28 小欧 - 三堂会审复核新增修复:
//   ①visibleItems useMemo 包裹(防每次渲染 slice 新数组, 全量已加载完时直接返回 items 零拷贝);
//   ②enabled 从 false 变 true(实时流结束)时保持全量(防内容收缩到首批, 用户丢失底部位置) — 小欧-2026-10-28
// 编辑历史: 2026-10-30 小欧 - 重构为"尾部窗口"(根治完成瞬间尾部 response 段被裁的整类缺陷):
//   ①窗口锚定在列表尾部(渲染末尾 visibleCount 段), 向上滚动加载更早段。理由: 消费方(右栏)恒"自动滚到内容
//     末端", 原先"从头部开始分批 + 自动滚底"互相矛盾 —— 滚底使哨兵始终在视口内, 必然逐批把整表拉全(既没省
//     DOM 又卡顿); 尾部窗口与"看末端"语义一致, 打开历史会话直接看到结论, 上翻才加载更早记录;
//   ②重置判据由"数组引用"改为"任务身份"(resetKey): 原判据把"引用变化"当"任务切换", 而完成链路必然重物化
//     steps(终态快照 settledSteps、REST historySteps 回填都是同内容新数组) → 误判切任务 → 裁回首批 80,
//     尾部答复段(含 final)整段消失/延后出现。窗口大小属任务级视图状态, 只认调用方给的任务标识 — 小欧-2026-10-30
/**
 * useLazyRender - 渐进式分批渲染 hook(尾部窗口)
 *
 * 【小欧 2026-10-28 P2】历史回放场景段数可达数千, 一次性挂载 DOM 冻结浏览器。
 * 本 hook 封装"尾部 N 段先渲染 → 哨兵进入视口预加载更早一批"的分批调度逻辑,
 * 使消费方组件只关注"渲染哪些段", 不关心"怎么分批"。
 *
 * - enabled=true 时分批: 渲染**末尾** initialBatch 段; 顶部哨兵进入 rootMargin 预加载圈时
 *   向上扩一批 loadBatch 段(setTimeout(0) 给浏览器喘息渲染);
 * - enabled=false 时全量: 直接返回 items(流式场景打字机/等待图标依赖末段位, 分批会丢失末段判定);
 * - 复位判据 = resetKey(任务身份): 只有调用方给的任务标识变化才把窗口归零; items 引用变化
 *   (同内容重物化/追加)一律不改窗口 —— 完成链路必然重物化 steps, 用引用比对会把"完成"误判成"切任务"。
 *
 * @author 小欧
 * @date 2026-10-28
 */
import { useState, useRef, useEffect, useMemo, type RefObject } from 'react';

const DEFAULT_INITIAL_BATCH = 80;
const DEFAULT_LOAD_BATCH = 80;
const DEFAULT_ROOT_MARGIN = '400px';

export interface LazyRenderResult<T> {
  /** 实际要渲染的段(enabled=false 时为全量; enabled=true 时为末尾 visibleCount 段) */
  visibleItems: T[];
  /** 顶部哨兵 div 的 ref, 消费方在渲染列表开头挂载 `{hasMore && <div ref={sentinelRef} />}` */
  sentinelRef: RefObject<HTMLDivElement>;
  /** 前面是否还有未渲染段(hasMore=true 时哨兵挂载, IntersectionObserver 观察其进入视口) */
  hasMore: boolean;
  /** 本窗口首段在 items 中的绝对下标(消费方据此算"绝对段位", 保证 key 与段位判定跨批次稳定) */
  startIndex: number;
}

/**
 * @param items 全量段数组
 * @param enabled 是否启用分批(取尾部窗口); 实时/刚完成的任务传 false → 全量渲染
 * @param resetKey 任务身份标识(如 activeTaskId): 值变化才把窗口复位到首批, items 引用变化不复位
 * @param initialBatch 首批渲染段数(默认 80, 约 2~3 屏, 取末尾)
 * @param loadBatch 每次向上滚动加载段数(默认 80)
 * @param rootMargin IntersectionObserver 预加载距离(默认 400px, 哨兵进入视口前即触发)
 */
export const useLazyRender = <T>(
  items: T[],
  enabled: boolean,
  resetKey: string,
  initialBatch: number = DEFAULT_INITIAL_BATCH,
  loadBatch: number = DEFAULT_LOAD_BATCH,
  rootMargin: string = DEFAULT_ROOT_MARGIN
): LazyRenderResult<T> => {
  const [visibleCount, setVisibleCount] = useState(initialBatch);
  const sentinelRef = useRef<HTMLDivElement>(null);
  // 任务身份复位: 渲染期同步比较(React 官方"随 props 调整 state"范式), 切换任务的同一帧即换窗口,
  //   不产生"先渲染旧窗口再复位"的中间帧; 只在 resetKey 真变化时调用 setState, 不会成环 — 小欧-2026-10-30
  const prevResetKeyRef = useRef(resetKey);
  if (prevResetKeyRef.current !== resetKey) {
    prevResetKeyRef.current = resetKey;
    setVisibleCount(initialBatch);
  }

  // 尾部窗口: 首段下标 = 总长 - 窗口长度(enabled=false 时窗口=全量, 下标归零) — 小欧-2026-10-30
  const startIndex = enabled ? Math.max(0, items.length - visibleCount) : 0;
  const hasMore = enabled && startIndex > 0;

  // 头哨兵进入视口预加载圈 → 向上扩一批(setTimeout(0) 允许浏览器在批次间渲染, 防 IO 回调同步批量加载卡死)
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

  // useMemo 包裹 visibleItems: items/窗口不变时复用同一数组; 窗口=全量时直接返回 items(零拷贝) — 小欧-2026-10-30
  const visibleItems = useMemo(
    () => (startIndex > 0 ? items.slice(startIndex) : items),
    [items, startIndex]
  );

  return { visibleItems, sentinelRef, hasMore, startIndex };
};
