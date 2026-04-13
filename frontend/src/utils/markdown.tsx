import React from "react";
// import katex from "katex";
// import "katex/dist/katex.min.css";  // 【小强删除 2026-04-13】未使用katex

/**
 * 渲染包含 Markdown 和 LaTeX 的内容
 * 【临时禁用LaTeX解析，只显示原始文本】
 */
export function renderContent(content: string): React.ReactNode[] {
  if (!content) return [];

  // 【临时禁用LaTeX解析，直接返回原始文本】
  return [<span key="content">{content}</span>];
}

export default { renderContent };
