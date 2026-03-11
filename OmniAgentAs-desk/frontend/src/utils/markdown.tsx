import katex from "katex";
import "katex/dist/katex.min.css";

/**
 * 渲染包含 Markdown 和 LaTeX 的内容
 * 支持：
 * - LaTeX 块公式: $$...$$
 * - LaTeX 行内公式: \(...\) 或 $...$
 * - 粗体: **text**
 * - 斜体: *text*
 * - 代码: `code`
 * - 换行: \n
 */
export function renderContent(content: string): React.ReactNode[] {
  if (!content) return [];

  const elements: React.ReactNode[] = [];
  const remaining = content;
  let key = 0;

  let lastIndex = 0;
  let match;

  // eslint-disable-next-line no-useless-escape
  const combinedRegex = /(\$\$[\s\S]*?\$\$)|(\\\([\s\S]*?\\\)|\$[^\$\n]+?\$)|(\*\*[^*]+\*\*)|(\*[^*]+\*)|(`[^`]+`)|(\n)/g;

  while ((match = combinedRegex.exec(remaining)) !== null) {
    // 添加匹配之前的普通文本
    if (match.index > lastIndex) {
      const text = remaining.slice(lastIndex, match.index);
      if (text) {
        elements.push(renderTextWithBasicMarkdown(text, key));
        key += 10;
      }
    }

    const fullMatch = match[0];

    // 块公式 $$...$$
    if (fullMatch.startsWith("$$")) {
      try {
        const formula = fullMatch.slice(2, -2).trim();
        elements.push(
          <div key={`formula-${key++}`} style={{ margin: "8px 0", overflowX: "auto" }}>
            <span dangerouslySetInnerHTML={{ __html: katex.renderToString(formula, { displayMode: true, throwOnError: false }) }} />
          </div>
        );
      } catch {
        elements.push(<code key={`formula-error-${key++}`}>{fullMatch}</code>);
      }
    }
    // 行内公式 \(...\) 或 $...$
    else if (fullMatch.startsWith("\\(") || fullMatch.startsWith("$")) {
      try {
        const formula = fullMatch.startsWith("\\(")
          ? fullMatch.slice(2, -2).trim()
          : fullMatch.slice(1, -1).trim();
        elements.push(
          <span key={`inline-formula-${key++}`} style={{ margin: "0 2px" }}>
            <span dangerouslySetInnerHTML={{ __html: katex.renderToString(formula, { displayMode: false, throwOnError: false }) }} />
          </span>
        );
      } catch {
        elements.push(<code key={`inline-formula-error-${key++}`}>{fullMatch}</code>);
      }
    }
    // 粗体 **text**
    else if (fullMatch.startsWith("**") && fullMatch.endsWith("**")) {
      const text = fullMatch.slice(2, -2);
      elements.push(<strong key={`bold-${key++}`}>{text}</strong>);
    }
    // 斜体 *text*
    else if (fullMatch.startsWith("*") && fullMatch.endsWith("*") && !fullMatch.startsWith("**")) {
      const text = fullMatch.slice(1, -1);
      elements.push(<em key={`italic-${key++}`}>{text}</em>);
    }
    // 代码 `code`
    else if (fullMatch.startsWith("`") && fullMatch.endsWith("`")) {
      const code = fullMatch.slice(1, -1);
      elements.push(<code key={`code-${key++}`} style={{ background: "#f5f5f5", padding: "2px 4px", borderRadius: "3px", fontSize: "0.9em" }}>{code}</code>);
    }
    // 换行 \n
    else if (fullMatch === "\n") {
      elements.push(<br key={`br-${key++}`} />);
    }
    // 其他情况
    else {
      elements.push(renderTextWithBasicMarkdown(fullMatch, key));
      key += 10;
    }

    lastIndex = match.index + fullMatch.length;
  }

  // 添加剩余文本
  if (lastIndex < remaining.length) {
    const text = remaining.slice(lastIndex);
    if (text) {
      elements.push(renderTextWithBasicMarkdown(text, key));
    }
  }

  return elements;
}

/**
 * 简单的文本渲染，支持基本Markdown
 */
function renderTextWithBasicMarkdown(text: string, startKey: number): React.ReactNode {
  // 如果没有特殊字符，直接返回文本
  if (!text.includes("*") && !text.includes("`") && !text.includes("\\")) {
    return text.split("\n").reduce((acc: React.ReactNode[], line, i, arr) => {
      acc.push(line);
      if (i < arr.length - 1) acc.push(<br key={`${startKey}-br-${i}`} />);
      return acc;
    }, []);
  }

  // 处理粗体
  const boldRegex = /\*\*([^*]+)\*\*/g;
  let processed = text.replace(boldRegex, (_, content) => `<strong>${content}</strong>`);

  // 处理斜体
  const italicRegex = /(?<!\*)\*([^*]+)\*(?!\*)/g;
  processed = processed.replace(italicRegex, (_, content) => `<em>${content}</em>`);

  // 处理代码
  const codeRegex = /`([^`]+)`/g;
  processed = processed.replace(codeRegex, (_, code) => `<code style="background:#f5f5f5;padding:2px 4px;border-radius:3px;font-size:0.9em">${code}</code>`);

  // 处理换行
  processed = processed.replace(/\n/g, "<br>");

  return <span key={startKey} dangerouslySetInnerHTML={{ __html: processed }} />;
}

export default { renderContent };
