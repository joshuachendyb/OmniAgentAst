// 编辑历史: 2026-10-05 小欧 - 新建: thought 块正文 Markdown 渲染(文档[9] 方案设计 §5.8 消费端)
//   动因: 设置项 appearance.step_render.thoughtMarkdown(设置页标签「思考排版」)只管 thought 块
//   (TextStream)正文的显示方式, 与「推理内容」(reasoningVisible → reasoning 块 ThinkingStream 折叠初值)
//   是两个独立开关, 各自独立互不干涉(北京老陈裁定)
//   为何自带极简渲染而不引 react-markdown: 不新增依赖(react-markdown/remark-*/rehype-* 共4包)且
//     不开 XSS 面 —— 全程不用 dangerouslySetInnerHTML, 一律走 React 文本节点, 标签与属性无法注入
//   支持子集(首版, 够用即止 YAGNI): 围栏代码块 ``` / 行内代码 ` / 粗体 ** __ / 斜体 * _ /
//     标题 # ## ### / 无序列表 - * ; 其余(含表格/链接/图片/引用/任务列表)按纯文本原样显示
//   与打字机的分层: 打字机负责"显示到第几个字"(切片在前), 本组件负责"这些字怎么画"(渲染在后)
//   编辑历史: 2026-10-05 小欧 - 三堂会审修复: ①斜体/粗体合并分支用 slice(2,-2) 剥标记,
//     而单星号定界符只有 1 对, '*强调*' 被切成空串(内容静默丢失, 三堂会审实测复现);
//     改为按实际定界符长度剥(粗体2/斜体1) ②行级容器补 whiteSpace:pre-wrap, 否则行首缩进
//     被 HTML 折叠(LLM 输出的 JSON/树/伪代码不可读, 相对旧纯文本属渲染退化)
//     ③切分改 split(/\r?\n/) 剥 CRLF 的 \r(否则 Windows 来源文本每行尾部留不可见字符,
//     且会污染标题正则的 $ 锚点) ④等宽字体改走 FontFamily.MONO 令牌(DRY) — 小欧-2026-10-05
import React from 'react';
import {
  BorderWidth,
  Colors,
  FontFamily,
  FontSize,
  FontWeight,
  Radius,
  Spacing,
} from '@/utils/stepStyles';

/**
 * 行内标记: 代码 > 粗体 > 斜体, 按优先级单趟切分(不递归, 免嵌套自匹配)。
 * 2026-10-05 小欧 三堂会审修复: 单星号/单下划线加**词边界**断言, 否则会吃掉普通文本的字符 ——
 *   `snake_case_name`(丢两个下划线且中间变斜体)、`2*3*4`(丢两颗星号)。判据: 定界符前后都不是词内字符。
 *   注意: 断言写在捕获组**内部**(零宽, 不改变组的起止), 不可另立捕获组 —— String.split 会把每个
 *   捕获组都作为独立片段返回, 多一个组就会把标记内容重复渲染一遍。
 *   依赖: lookbehind 需 ES2018 运行时(Chrome/Edge/modern Node 均支持, 本项目 antd 桌面端满足)。
 */
const INLINE_RE =
  /(`[^`\n]+`)|(\*\*[^*\n]+\*\*)|(__[^_\n]+__)|((?<![*\w`])\*[^*\n]+\*(?![*\w*`]))|((?<![_\w`])_[^_\n]+_(?![_\w`]))/g;

/** 行级容器统一样式: pre-wrap 保留源文本缩进与连续空格(LLM 输出大量缩进结构) */
const LINE_STYLE: React.CSSProperties = { whiteSpace: 'pre-wrap' };

const renderInline = (text: string, keyBase: string): React.ReactNode[] =>
  text
    .split(INLINE_RE)
    .filter((s) => s !== '' && s !== undefined)
    .map((seg, i) => {
      const key = `${keyBase}-i${i}`;
      if (seg.startsWith('`') && seg.endsWith('`') && seg.length > 2) {
        return (
          <code
            key={key}
            style={{
              fontFamily: FontFamily.MONO,
              fontSize: FontSize.CODE,
              background: Colors.BG.SECONDARY,
              padding: `0 ${Spacing.XS}px`,
              borderRadius: Radius.SM,
              ...LINE_STYLE,
            }}
          >
            {seg.slice(1, -1)}
          </code>
        );
      }
      // 2026-10-05 小欧 - 定界符长度决定剥几层: 粗体 ** __ 是 2 字符对, 斜体 * _ 是 1 字符对,
      //   统一 slice(2,-2) 会把单星号内容整段吃掉(三堂会审实测 '*强调*' => '') — 小欧-2026-10-05
      const boldMark = seg.startsWith('**') || seg.startsWith('__') ? 2 : 0;
      const italicMark = boldMark === 0 && /^(\*|_)/.test(seg) ? 1 : 0;
      if (boldMark || italicMark) {
        const n = boldMark || italicMark;
        return (
          <span
            key={key}
            style={{
              fontWeight: boldMark ? FontWeight.BOLD : FontWeight.REGULAR,
              fontStyle: italicMark ? 'italic' : undefined,
            }}
          >
            {seg.slice(n, -n)}
          </span>
        );
      }
      return <React.Fragment key={key}>{seg}</React.Fragment>;
    });

interface MarkdownBodyProps {
  text: string;
}

/** 块级解析: 仅 fenced 代码块与标题/列表为块, 其余逐行走行内解析 */
const MarkdownBody: React.FC<MarkdownBodyProps> = ({ text }) => {
  const blocks = text.split(/\r?\n/);
  const out: React.ReactNode[] = [];
  let i = 0;
  while (i < blocks.length) {
    const line = blocks[i];
    const fence = /^```/.test(line.trim());
    if (fence) {
      // 2026-10-05 小欧 三堂会审修复: key 必须用围栏**起始**下标 —— 原先用自增后的 i,
      //   与紧随其后那一块(=同一个 i)的 key 同值, 触发 React 重复 key 并复用错节点。
      const start = i;
      const buf: string[] = [];
      i += 1;
      while (i < blocks.length && !/^```/.test(blocks[i].trim())) {
        buf.push(blocks[i]);
        i += 1;
      }
      i += 1; // 跳过收尾围栏(缺收尾时 i 已越界, 自然终止)
      out.push(
        <pre
          key={`b${start}`}
          style={{
            fontFamily: FontFamily.MONO,
            fontSize: FontSize.CODE,
            background: Colors.BG.SECONDARY,
            border: `${BorderWidth.DEFAULT}px solid ${Colors.BORDER.DEFAULT}`,
            borderRadius: Radius.SM,
            padding: Spacing.SM,
            margin: `${Spacing.XS}px 0`,
            overflowX: 'auto',
            whiteSpace: 'pre',
          }}
        >
          {buf.join('\n')}
        </pre>
      );
      continue;
    }
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length; // 1~3 级
      out.push(
        <div
          key={`b${i}`}
          style={{
            fontWeight: FontWeight.BOLD,
            fontSize: level === 1 ? FontSize.PRIMARY : FontSize.SECONDARY,
            marginTop: Spacing.XS,
            ...LINE_STYLE,
          }}
        >
          {renderInline(heading[2], `b${i}`)}
        </div>
      );
      i += 1;
      continue;
    }
    const item = /^[-*]\s+(.*)$/.exec(line);
    if (item) {
      out.push(
        <div key={`b${i}`} style={{ display: 'flex', gap: Spacing.XS }}>
          <span aria-hidden="true">·</span>
          <span>{renderInline(item[1], `b${i}`)}</span>
        </div>
      );
      i += 1;
      continue;
    }
    if (line.trim() === '') {
      out.push(<div key={`b${i}`} style={{ height: Spacing.XS }} />);
      i += 1;
      continue;
    }
    out.push(
      <div key={`b${i}`} style={LINE_STYLE}>
        {renderInline(line, `b${i}`)}
      </div>
    );
    i += 1;
  }
  return <>{out}</>;
};

export { MarkdownBody };
