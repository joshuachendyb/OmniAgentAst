import React from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

/**
 * 渲染包含 Markdown 和 LaTeX 的内容
 * 使用简单的字符串查找方式，比正则更可靠
 */
export function renderContent(content: string): React.ReactNode[] {
  if (!content) return [];

  const elements: React.ReactNode[] = [];
  let remaining = content;
  let key = 0;

  while (remaining.length > 0) {
    // 查找下一个 $$ 块公式
    const blockStart = remaining.indexOf("$$");
    
    // 如果没有块公式，直接渲染剩余文本
    if (blockStart === -1) {
      if (remaining) {
        elements.push(renderTextBasic(remaining, key));
      }
      break;
    }

    // 添加 $$ 之前的文本
    if (blockStart > 0) {
      const textBefore = remaining.slice(0, blockStart);
      elements.push(renderTextBasic(textBefore, key));
      key += 10;
    }

    // 查找结束 $$
    const blockEnd = remaining.indexOf("$$", blockStart + 2);
    
    if (blockEnd === -1) {
      // 没有结束的 $$，把剩余的都当作文本
      elements.push(renderTextBasic(remaining.slice(blockStart), key));
      break;
    }

    // 提取公式内容
    const formula = remaining.slice(blockStart + 2, blockEnd).trim();
    
    // 渲染公式
    try {
      elements.push(
        <div key={`formula-${key++}`} style={{ margin: "8px 0", overflowX: "auto" }}>
          <span dangerouslySetInnerHTML={{ __html: katex.renderToString(formula, { displayMode: true, throwOnError: false }) }} />
        </div>
      );
    } catch {
      elements.push(<code key={`formula-error-${key++}`}>{`$$${formula}$$`}</code>);
    }

    // 继续处理剩余内容
    remaining = remaining.slice(blockEnd + 2);
  }

  return elements;
}

/**
 * 简单的文本渲染，支持基本Markdown
 */
function renderTextBasic(text: string, startKey: number): React.ReactNode {
  if (!text) return null;

  // 处理换行
  const lines = text.split("\n");
  
  return (
    <span key={startKey}>
      {lines.map((line, lineIndex) => {
        // 处理粗体
        const boldProcessed = processBold(line);
        
        // 处理行内公式 $...$
        const formulaProcessed = processInlineFormula(boldProcessed);
        
        return (
          <React.Fragment key={`line-${lineIndex}-${startKey}`}>
            {formulaProcessed}
            {lineIndex < lines.length - 1 && <br />}
          </React.Fragment>
        );
      })}
    </span>
  );
}

/**
 * 处理粗体 **text**
 */
function processBold(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  let remaining = text;
  let key = 0;

  while (remaining.length > 0) {
    const boldMatch = remaining.match(/^\*\*(.+?)\*\*/);
    
    if (boldMatch) {
      if (boldMatch.index! > 0) {
        parts.push(remaining.slice(0, boldMatch.index));
      }
      parts.push(<strong key={`bold-${key++}`}>{boldMatch[1]}</strong>);
      remaining = remaining.slice(boldMatch.index! + boldMatch[0].length);
    } else {
      parts.push(remaining);
      break;
    }
  }

  return parts.length > 0 ? parts : [text];
}

/**
 * 处理行内公式 $...$
 */
function processInlineFormula(parts: React.ReactNode[]): React.ReactNode[] {
  const result: React.ReactNode[] = [];
  
  parts.forEach((part) => {
    if (typeof part === "string") {
      // 在字符串中查找 $...$
      let remaining = part;
      let key = 0;
      
      while (remaining.length > 0) {
        const inlineStart = remaining.indexOf("$");
        
        if (inlineStart === -1) {
          result.push(remaining);
          break;
        }
        
        if (inlineStart > 0) {
          result.push(remaining.slice(0, inlineStart));
        }
        
        const inlineEnd = remaining.indexOf("$", inlineStart + 1);
        
        if (inlineEnd === -1) {
          result.push(remaining.slice(inlineStart));
          break;
        }
        
        const formula = remaining.slice(inlineStart + 1, inlineEnd);
        
        try {
          result.push(
            <span key={`inline-${key++}`} style={{ margin: "0 2px" }}>
              <span dangerouslySetInnerHTML={{ __html: katex.renderToString(formula, { displayMode: false, throwOnError: false }) }} />
            </span>
          );
        } catch {
          result.push(`$${formula}$`);
        }
        
        remaining = remaining.slice(inlineEnd + 1);
      }
    } else {
      result.push(part);
    }
  });
  
  return result;
}

export default { renderContent };
