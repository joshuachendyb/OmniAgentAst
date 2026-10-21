// 编辑历史: 2026-10-21 小杨 - 新建: 文件预览代码语法高亮单点(北京老陈拍板"代码要显示语法")
// 初版用 prismjs —— 页面实测**不亮**: prism 语言组件是裸全局脚本(`Prism.languages.x=...`),
//   走 vite bundler 的 global 注册链路时序不可靠, 读到空 grammar 全部退回纯文本。
//   2026-10-21 小杨 换 highlight.js: lib/core + 逐语言显式 registerLanguage(cjs 干净导出,
//   无全局裸引用, 确定性工作); **接口不变**(langOf/highlightLine), FilePreview 组件零改。
//   token 配色由组件层按 stepStyles 令牌定义(不载库自带主题 css, 全局视觉一致性);
//   聊天侧将来要高亮复用本单点(DRY 时机)
import hljs from 'highlight.js/lib/core';
import python from 'highlight.js/lib/languages/python';
import typescript from 'highlight.js/lib/languages/typescript';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import xml from 'highlight.js/lib/languages/xml';
import css from 'highlight.js/lib/languages/css';
import scss from 'highlight.js/lib/languages/scss';
import less from 'highlight.js/lib/languages/less';
import yaml from 'highlight.js/lib/languages/yaml';
import toml from 'highlight.js/lib/languages/toml';
import ini from 'highlight.js/lib/languages/ini';
import sql from 'highlight.js/lib/languages/sql';
import graphql from 'highlight.js/lib/languages/graphql';
import java from 'highlight.js/lib/languages/java';
import go from 'highlight.js/lib/languages/go';
import rust from 'highlight.js/lib/languages/rust';
import c from 'highlight.js/lib/languages/c';
import cpp from 'highlight.js/lib/languages/cpp';
import csharp from 'highlight.js/lib/languages/csharp';
import php from 'highlight.js/lib/languages/php';
import ruby from 'highlight.js/lib/languages/ruby';
import lua from 'highlight.js/lib/languages/lua';
import bash from 'highlight.js/lib/languages/bash';
import powershell from 'highlight.js/lib/languages/powershell';

const REGISTRY: Record<string, Parameters<typeof hljs.registerLanguage>[1]> = {
  python,
  typescript,
  javascript,
  json,
  xml,
  css,
  scss,
  less,
  yaml,
  toml,
  ini,
  sql,
  graphql,
  java,
  go,
  rust,
  c,
  cpp,
  csharp,
  php,
  ruby,
  lua,
  bash,
  powershell,
};
Object.entries(REGISTRY).forEach(([name, def]) =>
  hljs.registerLanguage(name, def)
);

/** 后缀 -> hljs 语言名(与后端 TEXT_EXTS 对齐; md 走 MarkdownText 渲染不进本表) */
const LANG_BY_EXT: Record<string, string> = {
  py: 'python',
  pyw: 'python',
  ts: 'typescript',
  tsx: 'typescript',
  js: 'javascript',
  jsx: 'javascript',
  mjs: 'javascript',
  cjs: 'javascript',
  json: 'json',
  jsonc: 'json',
  html: 'xml',
  htm: 'xml',
  xml: 'xml',
  css: 'css',
  scss: 'scss',
  less: 'less',
  yaml: 'yaml',
  yml: 'yaml',
  toml: 'toml',
  ini: 'ini',
  cfg: 'ini',
  conf: 'ini',
  env: 'ini',
  sql: 'sql',
  graphql: 'graphql',
  java: 'java',
  go: 'go',
  rs: 'rust',
  c: 'c',
  h: 'c',
  cpp: 'cpp',
  hpp: 'cpp',
  cc: 'cpp',
  cs: 'csharp',
  php: 'php',
  rb: 'ruby',
  sh: 'bash',
  bat: 'powershell',
  cmd: 'powershell',
  ps1: 'powershell',
  psm1: 'powershell',
  lua: 'lua',
};

/** 后缀 -> hljs 语言名; 未识别返回 null(逐行原样, 不含高亮) */
export const langOf = (name: string): string | null => {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return LANG_BY_EXT[ext] ?? null;
};

/** 单行高亮: 返回可直接塞 dangerouslySetInnerHTML 的 HTML(hljs 输出已转义正文) */
export const highlightLine = (line: string, lang: string): string => {
  if (!hljs.getLanguage(lang)) return line;
  try {
    return hljs.highlight(line, { language: lang, ignoreIllegals: true }).value;
  } catch {
    return line;
  }
};
