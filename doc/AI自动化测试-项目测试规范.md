# AI自主自动化测试规范

**制定时间**: 2026-02-17 09:25:44  
**适用范围**: AI自动化测试 - 包括AI能够做的全部测试类型、测试分析、报告、总结的编写  
**核心原则**: 测试是为了暴露问题、解决问题、最终消灭问题  
**更新时间**: 2026-02-27  
**文档版本**: v2.0

---

## 📋 索引目录

### 第一部分：通用测试规范
1. [测试目的与范围](#一测试目的与范围)
   - 核心目标与考核标准
   - 测试覆盖范围
   - 明确不包括的测试类型

### 第二部分：系统测试工具架构
2. [系统现有测试工具汇总](#二系统现有测试工具汇总)
   - 单元测试工具
   - 端到端测试工具
   - 代码质量工具
   - 本地CI/CD工具

3. [测试工具配置文件说明](#三测试工具配置文件说明)
   - 单元测试配置 (vite.config.ts)
   - ESLint配置 (.eslintrc.cjs)
   - Playwright配置 (playwright.config.ts)

### 第三部分：项目具体测试说明
4. [项目测试执行规范](#四项目测试执行规范)
   - 本地CI/CD自动化脚本
   - 单元测试使用说明
   - 端到端测试使用说明
   - 代码质量检查

5. [项目测试执行检查清单](#五项目测试执行检查清单)

6. [惩罚机制](#六惩罚机制)

---

## 一、测试目的与范围

### 1.1 核心目标与考核标准

**测试的根本目的**:
1. **暴露问题** - 通过测试发现被测代码中的缺陷、错误、隐患
2. **解决问题** - 定位根因，实施修复
3. **消灭问题** - 验证修复，确保问题彻底解决，最终归零

**测试报告的价值**:
- 准确记录发现的问题
- 真实反映被测代码质量
- 追踪问题从发现到解决的全过程
- 最终目标：报告末尾不存在任何未解决的问题

**考核标准**（唯一标准）:
1. **问题归零** - 最终轮次必须达到: failed=0, error=0
2. **验收通过** - 用户验收时，报告中已解决的问题不能再被发现
3. **无遗留问题** - 报告结尾不得存在"建议下一步"、"待后续处理"等未解决问题的描述

**绝对禁止**:
- ❌ 掩盖或粉饰问题
- ❌ 验收时被用户发现报告中已解决的问题
- ❌ 报告末尾遗留未解决问题
- ❌ 添加"建议"、"评估"、"下一步"等无实质内容的章节

### 1.2 测试范围覆盖

本规范适用于**所有AI自主执行的自动化测试、测试分析、报告编写、总结编写**工作：

| 测试类型 | 说明 | 适用性 | 使用工具 |
|---------|------|--------|---------|
| **单元测试** | 函数/方法级别的最小单元测试 | ✅ 必须遵循 | Vitest + React Testing Library |
| **集成测试** | 模块间交互、接口联调测试 | ✅ 必须遵循 | Vitest + React Testing Library |
| **回归测试** | 修复后的重复验证测试 | ✅ 必须遵循 | Vitest + React Testing Library |
| **冒烟测试** | 核心功能快速验证测试 | ✅ 必须遵循 | Vitest + React Testing Library |
| **端到端测试(E2E)** | 完整业务流程自动化测试(Playwright/Selenium) | ✅ 必须遵循 | Playwright |
| **API测试** | 接口契约、参数、响应验证 | ✅ 必须遵循 | Vitest + axios |
| **性能测试** | 响应时间、吞吐量基准测试 | ✅ 必须遵循 | Vitest + @vitest/coverage-v8 |
| **压力测试** | 高负载、并发、极限条件测试 | ✅ 必须遵循 | Vitest + 压力测试工具 |
| **安全测试** | 自动化漏洞扫描、注入检测 | ✅ 必须遵循 | ESLint + 安全插件 |
| **契约测试** | API契约一致性验证 | ✅ 必须遵循 | Vitest + axios |
| **兼容性测试** | 多浏览器、多环境兼容验证 | ✅ 必须遵循 | Playwright |
| **代码质量测试** | 静态分析、Lint检查、规范验证 | ✅ 必须遵循 | ESLint + Prettier |
| **覆盖率测试** | 代码覆盖率统计与验证 | ✅ 必须遵循 | Vitest + @vitest/coverage-v8 |
| **依赖测试** | 第三方库版本兼容性测试 | ✅ 必须遵循 | npm audit + 依赖检查工具 |
| **配置测试** | 不同配置参数下的行为测试 | ✅ 必须遵循 | Vitest |

### 1.3 明确不包括的测试类型

**需要用户参与的测试**：
- ❌ **验收测试** - 由用户执行的功能验收
- ❌ **探索性测试** - 人工自由探索式测试
- ❌ **用户体验测试** - 需要人工判断的UI/UX测试
- ❌ **业务逻辑确认** - 需要业务专家确认的场景

---

## 二、系统现有测试工具汇总

### 2.1 单元测试工具

**通用说明**：用于函数/方法级别的最小单元测试，是测试的基础。

**项目使用的工具**：
- **Vitest**：^1.1.0 - 现代化测试框架，快速、Vite集成
- **React Testing Library**：^14.1.2 - React组件测试工具
- **@testing-library/user-event**：^14.5.2 - 模拟用户交互
- **@testing-library/jest-dom**：^6.2.0 - DOM匹配器扩展
- **@vitest/coverage-v8**：^1.1.0 - V8引擎覆盖率报告

**示例使用**：
```typescript
// 单元测试示例
import { render, screen, fireEvent } from '@testing-library/react'
import Button from './Button'

test('button renders correctly', () => {
  render(<Button>Click me</Button>)
  expect(screen.getByText('Click me')).toBeInTheDocument()
})
```

### 2.2 端到端测试工具

**通用说明**：用于完整业务流程的自动化测试，模拟真实用户操作。

**项目使用的工具**：
- **Playwright**：^1.40.0 - 现代化E2E测试工具，支持多浏览器
- **jsdom**：^23.0.1 - DOM环境模拟（用于Vitest）

**示例使用**：
```typescript
// Playwright E2E测试示例
import { test, expect } from '@playwright/test'

test('login functionality', async ({ page }) => {
  await page.goto('/login')
  await page.fill('#username', 'testuser')
  await page.fill('#password', 'password')
  await page.click('#login-button')
  
  await expect(page).toHaveURL('/dashboard')
})
```

### 2.3 代码质量工具

**通用说明**：用于静态分析、代码风格检查和规范验证。

**项目使用的工具**：
- **ESLint**：^8.57.0 - 代码检查工具
- **@typescript-eslint/eslint-plugin**：^7.18.0 - TypeScript规则
- **@typescript-eslint/parser**：^7.18.0 - TypeScript解析器
- **eslint-plugin-react**：^7.37.5 - React规则
- **eslint-plugin-react-hooks**：^4.6.2 - React Hooks规则
- **Prettier**：^3.8.1 - 代码格式化工具

**示例使用**：
```bash
# ESLint检查
npm run lint

# Prettier格式化
npm run format
```

### 2.4 本地CI/CD工具

**通用说明**：用于本地开发环境的自动化测试流程管理。

**项目使用的工具**：
- **本地CI/CD自动化脚本**：`frontend/scripts/local-ci.sh` - 完整的自动化测试流程

---

## 三、测试工具配置文件说明

### 3.1 单元测试配置

**文件位置**：`frontend/vite.config.ts` 和 `frontend/vitest.config.ts`

**通用配置说明**：
```typescript
// vite.config.ts 相关配置
test: {
  globals: true,              // 启用全局API
  environment: 'jsdom',       // 使用jsdom模拟浏览器环境
  setupFiles: './src/tests/setup.ts',  // 测试环境设置文件
  coverage: {
    reporter: ['text', 'json', 'html'],  // 覆盖率报告格式
    exclude: ['node_modules', 'src/tests']  // 排除文件
  }
}
```

**项目具体配置**：已配置上述参数，支持多种覆盖率报告格式。

### 3.2 ESLint配置

**文件位置**：`frontend/.eslintrc.cjs`

**通用配置说明**：
```javascript
// .eslintrc.cjs 相关配置
rules: {
  'react/jsx-key': 'error',               // 必须有key属性
  'react-hooks/rules-of-hooks': 'error',    // Hooks使用规则
  'react/no-direct-mutation-state': 'error', // 禁止直接修改state
  '@typescript-eslint/no-explicit-any': 'warn', // any类型警告
  '@typescript-eslint/no-unused-vars': 'warn', // 未使用变量警告
  'no-console': ['warn', { allow: ['warn', 'error'] }] // 控制台警告
}
```

**项目具体配置**：严格执行react/jsx-key和react-hooks规则，对其他规则给予警告。

### 3.3 Playwright配置

**文件位置**：`frontend/playwright.config.ts`

**通用配置说明**：
```typescript
// playwright.config.ts 相关配置
export default defineConfig({
  testDir: './tests/e2e',      // 测试文件目录
  fullyParallel: true,         // 文件级并行执行
  forbidOnly: !!process.env.CI, // CI环境禁止only标记
  retries: process.env.CI ? 2 : 0, // CI环境重试次数
  workers: process.env.CI ? 1 : undefined, // 工作进程数
  reporter: 'html',            // 报告格式
  use: {
    baseURL: 'http://localhost:5173',  // 测试基准URL
    trace: 'on-first-retry',           // 首次重试时收集trace
    screenshot: 'only-on-failure',    // 失败时截图
    video: 'on-first-retry',          // 首次重试时录像
  },
  projects: [
    {
      name: 'chromium',               // Chrome浏览器测试
      use: { ...devices['Desktop Chrome'] },
    }
  ]
});
```

**项目具体配置**：配置了Chrome浏览器测试，支持调试和失败分析。

---

## 四、项目测试执行规范

### 4.1 本地CI/CD自动化脚本

**文件位置**：`frontend/scripts/local-ci.sh`

**通用说明**：完整的本地自动化测试流程，包含所有测试阶段。

**项目具体使用说明**：

#### 4.1.1 基本使用方法

```bash
cd D:\2bktest\MDview\OmniAgentAs-desk\frontend
./scripts/local-ci.sh
```

#### 4.1.2 执行流程

脚本会依次执行：

```
检查Node.js版本 → 检查依赖 → ESLint检查 → 单元测试 → 生产构建
```

#### 4.1.3 执行示例

```
============================================
OmniAgentAs-desk 前端项目本地CI/CD自动化
============================================
执行时间: 2026-02-27 17:35:46

ℹ️  检查Node.js和npm版本...
ℹ️  Node.js: v24.13.0
ℹ️  npm: v11.6.2

ℹ️  开始执行本地CI/CD流程...
📦 安装项目依赖...
🔍 运行ESLint代码质量检查...
🧪 运行单元测试...
✅ 所有单元测试通过
🔨 执行生产环境构建...
✅ 项目构建成功
是否需要生成测试覆盖率报告? (y/N): 
```

#### 4.1.4 脚本特点

- **完整的错误处理**
- **彩色输出** - 使用ANSI颜色码
- **详细的日志信息** - 每个阶段都有说明
- **依赖检查** - 自动检查并安装依赖
- **版本验证** - 检查Node.js和npm版本
- **交互式选项** - 可选是否生成覆盖率报告
- **执行时间统计**

### 4.2 单元测试使用说明

**通用说明**：用于验证函数和组件的基本功能。

**项目具体使用说明**：

```bash
# 运行所有单元测试
npm run test

# 监听模式运行
npm run test:watch

# 生成覆盖率报告
npm run test:coverage
```

**项目测试覆盖情况**：
- 现有83个测试用例全部通过
- 代码覆盖率：19.8%（需要提高）

### 4.3 端到端测试使用说明

**通用说明**：用于验证完整的业务流程。

**项目具体使用说明**：

```bash
# 运行Playwright E2E测试
npm run test:e2e

# 可视化UI模式
npm run test:e2e:ui

# 调试模式
npm run test:e2e:debug
```

**项目E2E测试文件**：
- `tests/e2e/` 目录下有2个测试文件

### 4.4 代码质量检查

**通用说明**：用于确保代码符合ESLint规范。

**项目具体使用说明**：

```bash
# 运行ESLint检查
npm run lint

# 自动修复
npm run lint:fix

# 检查格式化
npm run format:check
```

---

## 五、项目测试执行检查清单

每次测试工作前自检：

- [ ] 是否获取了真实系统时间？
- [ ] 是否理解测试要暴露问题、解决问题、最终消灭问题？
- [ ] 是否准备好区分测试代码/被测代码问题？
- [ ] 是否知道测试代码问题要自行修复不报告？
- [ ] 是否清楚报告只能追加不能插入？
- [ ] 是否明白报告末尾不能存在未解决的问题？
- [ ] 是否了解本地CI/CD脚本的位置和功能？
- [ ] 是否知道如何执行本地CI/CD自动化脚本？
- [ ] 是否了解系统现有的测试工具配置？
- [ ] 是否知道各个测试工具的主要功能和使用场景？

---

## 六、惩罚机制

违反以下任意一条，接受惩罚：

| 违规行为 | 惩罚 |
|---------|------|
| 时间戳瞎估计 | 重新获取真实时间并修正 |
| 测试代码问题不立即修复 | 立即停止，修复后再继续 |
| 回归测试插入而非追加 | 删除插入内容，重新追加 |
| 报告添加自我吹嘘 | 删除相关内容 |
| 问题未归零就结束 | 继续测试直到归零 |
| 弄虚作假 | 重新执行完整测试流程 |

---

**规范生效时间**: 2026-02-17 09:25:44  
**适用范围**: AI自动化测试 - 包括AI能够做的全部测试类型、测试分析、报告、总结的编写  
**文档版本**: v2.0