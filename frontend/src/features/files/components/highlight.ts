// 编辑历史: 2026-10-21 小杨 - 新建: 文件预览代码语法高亮单点(北京老陈拍板"代码要显示语法")
//   prismjs 核心自带 markup/javascript/css/clike, 其余语言按需静态注册(仅 Files 路由 chunk 载入);
//   未知后缀落 plain 文本不硬造; **不载 prism 自带主题 css** —— token 颜色由组件层按
//   stepStyles 令牌定义(全局视觉一致性, 三堂会审口径); 聊天侧将来要高亮时复用本单点(DRY 时机)
import Prism from 'prismjs';
import 'prismjs/components/prism-markup-templating'; // php/powershell 的依赖, 须先于它们注册
import 'prismjs/components/prism-typescript'; // 依赖 javascript(core 已含)
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-powershell';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-toml';
import 'prismjs/components/prism-ini';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-graphql';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-go';
import 'prismjs/components/prism-rust';
import 'prismjs/components/prism-java';
import 'prismjs/components/prism-c'; // 依赖 clike(core 已含); cpp 依赖 c, 须在前
import 'prismjs/components/prism-cpp';
import 'prismjs/components/prism-csharp';
import 'prismjs/components/prism-php';
import 'prismjs/components/prism-ruby';
import 'prismjs/components/prism-lua';
import 'prismjs/components/prism-scss'; // 依赖 css(core 已含)
import 'prismjs/components/prism-less';

/** 后缀 -> prism 语言名(与后端 TEXT_EXTS 对齐; md 走 MarkdownText 渲染不进本表) */
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
  html: 'markup',
  htm: 'markup',
  xml: 'markup',
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
  proto: 'clike', // proto 暂置 clike 近似着色(不引 prism-proto, YAGNI)
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

/** 后缀 -> prism 语言名; 未识别返回 null(逐行原样, 不含高亮) */
export const langOf = (name: string): string | null => {
  const ext = name.split('.').pop()?.toLowerCase() ?? '';
  return LANG_BY_EXT[ext] ?? null;
};

/** 单行高亮: 返回可直接塞 dangerouslySetInnerHTML 的 HTML(prism 输出已转义正文) */
export const highlightLine = (line: string, lang: string): string =>
  Prism.languages[lang]
    ? Prism.highlight(line, Prism.languages[lang], lang)
    : line;
