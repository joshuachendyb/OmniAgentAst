// 编辑历史: 2026-10-06 小欧 - 新建：Markdown 中的 mermaid 围栏渲染为流程图（security Tab 弹框2 用）
//
// 为什么单独一个组件:
//   mermaid 体积不小且只在少数场景用到, 故动态 import 懒加载, 不进主包。
//   securityLevel='strict': 图里的文字/HTML 一律不执行, 只画图。
//
// 为什么失败要降级而不是抛错:
//   流程图画不出来不该让整个说明弹框打不开——降级成 <pre> 原文, 用户仍能读到图的内容。
//
// initialize 只做一次(2026-10-06 三堂会审 #7):
//   mermaid 是**全局单例**, initialize 会改它的全局配置。原实现每次 effect 都调,
//   多个图/重渲染时互相覆盖且重复初始化。现用模块级 Promise 缓存, 首次并发调用也只初始化一次。
import { useEffect, useId, useRef, useState } from 'react';

interface MermaidBlockProps {
  /** mermaid 源码(已从 ```mermaid 围栏中剥出) */
  chart: string;
}

/** mermaid 初始化单例: 首次调用真正 initialize, 之后复用同一 Promise */
let initOnce: Promise<typeof import('mermaid').default> | null = null;
function loadMermaid(): Promise<typeof import('mermaid').default> {
  initOnce ??= import('mermaid').then((m) => {
    m.default.initialize({
      startOnLoad: false,
      securityLevel: 'strict',
      theme: 'default',
      // 2026-10-06 小欧: 判定流程有 15+ 节点, 默认字号/间距在弹框里过高、需大量滚动。
      // 收紧后整图更紧凑, 仍由 CSS max-width 兜底不溢出。
      fontSize: 12,
      flowchart: { nodeSpacing: 30, rankSpacing: 34, padding: 6 },
    });
    return m.default;
  });
  return initOnce;
}

type State =
  | { kind: 'loading' }
  | { kind: 'done'; svg: string }
  | { kind: 'failed' };

export function MermaidBlock({ chart }: MermaidBlockProps) {
  // mermaid 的 id 必须全文档唯一, 否则第二张图会串到第一张上
  const reactId = useId();
  const graphId = 'mmd-' + reactId.replace(/[^a-zA-Z0-9]/g, '');
  // 2026-10-06 三堂会审 #4: 初值 loading(旧实现初值空串→首帧渲染 null→弹框里闪一下空白);
  //   #6: chart 变化时 effect 会重置为 loading, 不会在图渲染完成前停留在上一张图
  const [state, setState] = useState<State>({ kind: 'loading' });
  // mermaid.render 同 id 重复渲染会拿到旧结果, 每次调用递增后缀
  const renderSeq = useRef(0);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: 'loading' });
    void (async () => {
      try {
        const mermaid = await loadMermaid();
        const seq = ++renderSeq.current;
        const { svg } = await mermaid.render(`${graphId}-${seq}`, chart);
        if (!cancelled) setState({ kind: 'done', svg });
      } catch {
        // 语法错 / 依赖缺失都走这里
        if (!cancelled) setState({ kind: 'failed' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [chart, graphId]);

  if (state.kind === 'failed') {
    return (
      <pre
        style={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          fontFamily: 'monospace',
          fontSize: 12,
          lineHeight: 1.5,
        }}
      >
        {chart}
      </pre>
    );
  }

  // loading 时给固定高度占位, 避免图出现时把下方内容顶下去(页面位移)
  if (state.kind === 'loading') {
    return <div className="mermaid-block" style={{ minHeight: 120 }} />;
  }

  // mermaid 产出的是它自己生成的 svg 串, 用 dangerouslySetInnerHTML 上屏
  return (
    <div
      className="mermaid-block"
      dangerouslySetInnerHTML={{ __html: state.svg }}
    />
  );
}
