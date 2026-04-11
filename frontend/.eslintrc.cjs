module.exports = {
  root: true,
  env: { browser: true, es2020: true, node: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', 'node_modules', '*.config.*', '*.d.ts'],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    ecmaVersion: 2020,
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
    project: './tsconfig.json',
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
    'no-console': ['warn', { allow: ['warn', 'error'] }],
    'no-debugger': 'warn',
    // 禁止直接调用 message.error/warning/success/info，应使用 errorHandler
    'no-restricted-syntax': [
      'error',
      {
        selector: 'CallExpression[callee.object.name=message][callee.property.name=error]',
        message: '禁止直接调用 message.error，请使用 errorHandler.handleError() 或 handleApiError()',
      },
      {
        selector: 'CallExpression[callee.object.name=message][callee.property.name=warning]',
        message: '禁止直接调用 message.warning，请使用 errorHandler.handleError() 或 handleApiError()',
      },
      {
        selector: 'CallExpression[callee.object.name=message][callee.property.name=success]',
        message: '禁止直接调用 message.success，请使用 errorHandler.showSuccess()',
      },
      {
        selector: 'CallExpression[callee.object.name=message][callee.property.name=info]',
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
