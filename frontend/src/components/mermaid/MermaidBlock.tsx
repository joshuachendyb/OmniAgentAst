// 编辑历史: 2026-10-06 小欧 - 新建：Markdown 中的 mermaid 围栏渲染为流程图（security Tab 弹框2 用）
// 编辑历史: 2026-10-06 小欧 - 配色改用项目 Colors/FontSize 令牌(原先 fontSize:12 与 mermaid 自带
//   蓝紫默认主题都是硬编码/脱离令牌); 线色取 TEXT.SECONDARY —— 用 BORDER.VERTICAL 实测渲成
//   #e8e8e8, 比节点填充 #f5f5f5 还浅, 线几乎不可见; flowchart 加 wrappingWidth 放宽节点标签折行。
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
import { Colors, FontSize } from '@/utils/stepStyles';

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
      // 2026-10-06 小欧(三堂会审): 配色改用项目 Colors 体系, 不再用 mermaid 自带蓝紫默认主题
      //   (默认主题色与 settings2 的浅灰底/中灰字完全脱节, 深浅色模式下也不会跟着变)。
      //   ⚠️ 复测: 线色不能用 BORDER.VERTICAL —— 实测渲成 #e8e8e8, 比节点填充 #f5f5f5 还浅,
      //   线几乎不可见。故线与箭头统一取 TEXT.SECONDARY(#8c8c8c), 与节点填充拉得开。
      theme: 'base',
      themeVariables: {
        background: Colors.BG.PRIMARY,
        primaryColor: Colors.BG.TERTIARY,
        primaryBorderColor: Colors.TEXT.SECONDARY,
        primaryTextColor: Colors.TEXT.PRIMARY,
        lineColor: Colors.TEXT.SECONDARY,
        textColor: Colors.TEXT.PRIMARY,
        fontSize: `${FontSize.SECONDARY}px`,
      },
      // 2026-10-06 小欧: 节点标签折行才是图高的主因(实测节点被压到 68px 宽、文字挤成 5 行,
      //   整图 1566px 高 vs 弹框 634px)。故用 wrappingWidth 放宽单节点可用宽度, 让标签少折行。
      flowchart: {
        wrappingWidth: 220,
        nodeSpacing: 40,
        rankSpacing: 40,
        padding: 8,
      },
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
          fontSize: FontSize.CODE,
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
