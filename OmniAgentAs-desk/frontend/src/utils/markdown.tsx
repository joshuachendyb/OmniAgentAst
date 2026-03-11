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
    // 查找下一个块公式：$$ 或 \[
    const blockStartDollar = remaining.indexOf("$$");
    const blockStartBracket = remaining.indexOf("\\[");
    
    // 选择最早出现的块公式
    let blockStart = -1;
    let blockType: "dollar" | "bracket" = "dollar";
    
    if (blockStartDollar !== -1 && blockStartBracket !== -1) {
      blockStart = Math.min(blockStartDollar, blockStartBracket);
      blockType = blockStartDollar < blockStartBracket ? "dollar" : "bracket";
    } else if (blockStartDollar !== -1) {
      blockStart = blockStartDollar;
      blockType = "dollar";
    } else if (blockStartBracket !== -1) {
      blockStart = blockStartBracket;
      blockType = "bracket";
    }
    
    // 如果没有块公式，直接渲染剩余文本
    if (blockStart === -1) {
      if (remaining) {
        elements.push(renderTextBasic(remaining, key));
      }
      break;
    }

    // 添加块公式之前的文本
    if (blockStart > 0) {
      const textBefore = remaining.slice(0, blockStart);
      elements.push(renderTextBasic(textBefore, key));
      key += 10;
    }

    // 查找结束标记
    const blockEndMarker = blockType === "dollar" ? "$$" : "\\]";
    const blockEnd = remaining.indexOf(blockEndMarker, blockStart + (blockType === "dollar" ? 2 : 2));
    
    if (blockEnd === -1) {
      // 没有结束标记，把剩余的都当作文本
      elements.push(renderTextBasic(remaining.slice(blockStart), key));
      break;
    }

    // 提取公式内容，并处理转义字符
    const formulaStart = blockStart + (blockType === "dollar" ? 2 : 2);
    let formula = remaining.slice(formulaStart, blockEnd).trim();
    
    // 处理转义：\\ -> \ (JSON 序列化导致的双重转义)
    formula = formula.replace(/\\\\/g, "\\");
    
    // 渲染公式
    try {
      elements.push(
        <div key={`formula-${key++}`} style={{ margin: "8px 0", overflowX: "auto" }}>
          <span dangerouslySetInnerHTML={{ __html: katex.renderToString(formula, { displayMode: true, throwOnError: false }) }} />
        </div>
      );
    } catch (e: any) {
      elements.push(<code key={`formula-error-${key++}`}>{remaining.slice(blockStart, blockEnd + 2)}</code>);
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
