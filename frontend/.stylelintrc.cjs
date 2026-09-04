// stylelint 配置 — 会话页视觉令牌门禁（v1.3 三堂会审落地）
// 2026-08-30 小欧 根治prettier解析失败: 原JSDoc块注释/* */内含glob "src/**/*.tsx"的"**/"序列会提前终止块注释,
//   剩余代码成为裸文本致SyntaxError(9:28); 改行注释后glob可安全书写, 内容零丢失 - 小欧-2026-08-30
//
// 目的：强制所有颜色/部分尺寸走 stepStyles 令牌，杜绝硬编码十六进制回潮。
// 规则依据：会话页整体UI审计-小欧-2026-08-28.md v1.3 之 P3 门禁。
//
// 启用方式（当前依赖未装，仅作契约）：
//   npm i -D stylelint
//   npx stylelint "src/**/*.tsx" --fix
// 并在 CI / pre-commit 中调用，使 H1/H3 类硬码零拦截成为常态。
//
// @author 小欧
// @date 2026-08-28

module.exports = {
  // 仅用内置规则，不依赖插件，避免未装依赖报错
  rules: {
    // 禁直写任何十六进制色值（强制 Colors.* 令牌）。true=开启
    'color-no-hex': true,
    // 十六进制强制小写（即使误写也被统一格式，配合上方规则拦截）
    'color-hex-case': 'lower',
  },
  // 令牌源 stepStyles.ts 本身以十六进制定义语义色, 必须排除, 否则 color-no-hex 自伤令牌
  ignoreFiles: [
    '**/node_modules/**',
    '**/dist/**',
    '**/*.test.tsx',
    '**/stepStyles.ts',
  ],
};
