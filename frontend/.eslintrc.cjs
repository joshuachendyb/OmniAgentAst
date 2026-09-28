module.exports = {
  root: true,
  env: { browser: true, es2020: true, node: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: [
    'dist',
    'node_modules',
    '*.config.*',
    '*.d.ts',
    // 2026-09-28 小欧 - 归档备份不参与 lint（同 tsconfig.e2e.json：历史快照非活代码）
    '**/*.备份-*.ts',
    'e2e_case/output',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
    // 2026-09-28 小欧 - 改为按目录双 tsconfig：src/ 与 E2E/测试支撑各自对应一个 project。
    //   原先只指 tsconfig.json（include 仅 ["src"]），而 e2e_case/、e2e_front_lib/、src/tests/
    //   全在其外 → 这些文件对类型感知规则直接报 parsing error，等于零检查。
    //   tsconfig.e2e.json 复用同一套 compilerOptions（extends），仅换 include 范围。
    project: ['./tsconfig.json', './tsconfig.e2e.json'],
  },
  plugins: ['react', 'react-hooks', '@typescript-eslint'],
  settings: {
    react: {
      version: 'detect',
    },
  },
  rules: {
    'react/jsx-uses-react': 'off',
    'react/react-in-jsx-scope': 'off',
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': [
      'warn',
      { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
    ],
    '@typescript-eslint/no-empty-function': 'warn',
    '@typescript-eslint/no-non-null-assertion': 'warn',
    'react-hooks/rules-of-hooks': 'error',
    'react-hooks/exhaustive-deps': 'warn',
    'react/jsx-key': 'error',
    'react/no-direct-mutation-state': 'error',
    'no-console': 'off', // TODO: 生产环境发布前需清除所有 console.log
    'no-debugger': 'warn',
    // 禁止直接调用 message.error/warning/success/info，应使用 errorHandler
    'no-restricted-syntax': [
      'error',
      {
        selector:
          'CallExpression[callee.object.name=message][callee.property.name=error]',
        message:
          '禁止直接调用 message.error，请使用 errorHandler.handleError() 或 handleApiError()',
      },
      {
        selector:
          'CallExpression[callee.object.name=message][callee.property.name=warning]',
        message:
          '禁止直接调用 message.warning，请使用 errorHandler.handleError() 或 handleApiError()',
      },
      {
        selector:
          'CallExpression[callee.object.name=message][callee.property.name=success]',
        message:
          '禁止直接调用 message.success，请使用 errorHandler.showSuccess()',
      },
      {
        selector:
          'CallExpression[callee.object.name=message][callee.property.name=info]',
        message: '禁止直接调用 message.info，请使用 errorHandler.showMessage()',
      },
    ],
  },
  overrides: [
    {
      // errorHandler.ts 是统一错误处理中心，允许内部调用 message
      files: ['src/utils/errorHandler.ts'],
      rules: {
        'no-restricted-syntax': 'off',
      },
    },
  ],
};
