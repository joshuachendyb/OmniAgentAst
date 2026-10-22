#!/usr/bin/env node
// 编辑历史: 2026-10-22 小欧 - 新建：前端架构审计（分层/单一真源守卫）— 小欧-2026-10-22
/**
 * arch-check —— 前端架构审计（文档[43] 的可执行守卫）
 *
 * 定位：**报告**工具，不是测试用例。
 *   - 不在 `src/tests/` 下，不被 vitest 收集（AGENTS：严禁 commit 测试 case 代码，本脚本是工具不是 case）；
 *   - 默认**只报告不失败**（当前基线仍有存量违规，改完代码前不能让它挡住构建）；
 *   - 加 `--strict` 时有违规即退出码 1（重构收口后接入门禁）。
 *
 * 用法：
 *   node scripts/arch-check.mjs            # 报告（含基线对照）
 *   node scripts/arch-check.mjs --strict   # 有违规即 exit 1（重构完成后启用）
 *
 * 审计规则（对齐文档[43] §2.7 / §3.2）：
 *   G1 域间零互引      features/chat ⇄ features/files 不得互相 import
 *   G2 引用入口唯一    composerRefStore.push 只允许出现在 features/refs/ 内
 *   G3 深链拼装唯一    '?path=' 只允许出现在 utils/fileDeepLink.ts 内
 *   G4 路径判据唯一    绝对→相对的自写实现只允许出现在 utils/projectPath.ts 内
 */
import { readdir, readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SRC = path.join(ROOT, 'src');
const STRICT = process.argv.includes('--strict');

/**
 * 页面 → 域 的归属映射（用于判定"页面依赖他域私有实现"）
 * ⚠ 例外是显式登记的，不是通配豁免 —— 新增页面若跨域依赖，须在此登记理由。
 */
const PAGE_DOMAIN = {
  'pages/chatpage.tsx': 'chat',
  'pages/history/index.tsx': 'chat', // 历史会话页属会话域（用 chatStreamStore 读任务态）
  'pages/files/index.tsx': 'files',
};
/** 归属查表统一走小写（Windows 大小写不敏感，路径登记不应因大小写失配） */
const ownDomainOf = (rel) => PAGE_DOMAIN[rel.toLowerCase()] ?? null;

const RULES = [
  {
    id: 'G1a',
    name: '跨 feature 零互引（features/A 不得 import features/B）',
    test: (line, rel) => {
      const m = line.match(/from\s+['"]([^'"]+)['"]/);
      if (!m) return null;
      const spec = m[1];
      const inFeature = rel.match(/^features\/([^/]+)\//);
      const target = spec.match(/features\/([^/]+)\//);
      if (!inFeature || !target) return null;
      if (inFeature[1] === target[1]) return null;
      // 2026-10-22 小欧 - features/refs 是共享域（文档[43] §3.2），chat 与 files 都可依赖它
      if (target[1] === 'refs') return null;
      return `跨 feature 引用：${spec}（${inFeature[1]} → ${target[1]}）`;
    },
    exempt: () => false,
  },
  {
    id: 'G1b',
    name: '共享层不得依赖域（utils/ hooks/ components/ 不得 import features/**）',
    test: (line, rel) => {
      if (!/^(utils|hooks|components)\//.test(rel)) return null;
      // ⚠ 类型导入（import type）在编译期即被擦除，**不构成运行期依赖** → 豁免
      //   （否则 utils/viewState.ts 的 `import type { TaskBadge }` 会被误判为违规）
      if (/^\s*import\s+type\b/.test(line)) return null;
      const m = line.match(/from\s+['"]([^'"]+)['"]/);
      if (!m) return null;
      if (!/features\/[^/]+\//.test(m[1])) return null;
      return `共享层依赖域：${m[1]}（${rel} 属共享层，不得依赖具体域）`;
    },
    exempt: () => false,
  },
  {
    id: 'G1c',
    name: '页面不得依赖他域私有实现（pages/X → features/Y/streams/**，Y≠X）',
    test: (line, rel) => {
      if (!rel.startsWith('pages/')) return null;
      const own = ownDomainOf(rel);
      const m = line.match(/from\s+['"]([^'"]+)['"]/);
      if (!m) return null;
      const spec = m[1];
      const target = spec.match(/features\/([^/]+)\//);
      if (!target) return null;
      if (!/features\/[^/]+\/(streams|services)\//.test(spec)) return null; // 私有实现目录
      if (target[1] === own) return null; // 本域页面用本域实现，合法
      return `页面跨域依赖私有实现：${spec}（${own ?? '未登记域'} → ${target[1]}）`;
    },
    exempt: () => false,
  },
  {
    id: 'G2',
    name: '引用入口唯一（composerRefStore.push 只在 features/refs/）',
    test: (line) =>
      line.includes('composerRefStore.push')
        ? '域外直接 push 引用（应走 features/refs 的 quote*/enqueueRef）'
        : null,
    exempt: (rel) => rel.startsWith('features/refs/'),
  },
  {
    id: 'G3',
    name: '文件页深链拼装唯一（/files?path= 只在 utils/fileDeepLink.ts）',
    // ⚠ 精确匹配 /files?path= —— 不误伤后端 URL（/files/raw?path=）与 markdown 通道（/file-ref?path=）
    test: (line) =>
      /\/files\?path=/.test(line)
        ? '文件页深链在此手工拼装（应走 buildFileDeepLink）'
        : null,
    exempt: (rel) => rel === 'utils/fileDeepLink.ts',
  },
  {
    id: 'G3b',
    name: 'markdown 引用链接拼装唯一（/file-ref?path= 只在 components/markdown/FileRefChip.tsx）',
    test: (line) =>
      /\/file-ref\?path=/.test(line) && !/^\s*(\*|\/\/)/.test(line)
        ? 'markdown 引用链接在此手工拼装（应走 FileRefChip 的 toFileRefMarkdown）'
        : null,
    exempt: (rel) => rel === 'components/markdown/FileRefChip.tsx',
  },
  {
    id: 'G4',
    name: '路径判据唯一（绝对→相对自写实现只在 utils/projectPath.ts）',
    test: (line) => {
      if (/relative_to\(/.test(line)) return '自写相对化实现 relative_to()';
      if (/startsWith\(\s*root/i.test(line))
        return '自写相对化实现 startsWith(root…)';
      if (/slice\(\s*root\.length/.test(line))
        return '自写相对化实现 slice(root.length)';
      if (/const\s+normalizeRelPath\b/.test(line))
        return '自写 normalizeRelPath';
      return null;
    },
    exempt: (rel) => rel === 'utils/projectPath.ts',
  },
];

/** 递归收集源码文件 */
async function collect(dir, out = []) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') continue;
      await collect(full, out);
    } else if (/\.(ts|tsx)$/.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

const SKIP_DIR = ['node_modules', 'dist', '.vite'];

async function walk(dir, out = []) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    if (SKIP_DIR.includes(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) await walk(full, out);
    else if (/\.(ts|tsx)$/.test(entry.name)) out.push(full);
  }
  return out;
}

async function main() {
  if (!existsSync(SRC)) {
    console.error('[arch-check] 找不到 src 目录：', SRC);
    process.exit(2);
  }
  const files = await walk(SRC);
  const findings = [];

  for (const file of files) {
    const rel = path.relative(SRC, file).split(path.sep).join('/');
    if (rel.startsWith('tests/')) continue; // 测试目录不参与架构审计
    const text = await readFile(file, 'utf8');
    const lines = text.split(/\r?\n/);
    for (const rule of RULES) {
      if (rule.exempt(rel)) continue;
      for (let i = 0; i < lines.length; i += 1) {
        const msg = rule.test(lines[i], rel);
        if (msg)
          findings.push({
            rule: rule.id,
            name: rule.name,
            file: rel,
            line: i + 1,
            msg,
          });
      }
    }
  }

  const byRule = new Map();
  for (const f of findings) {
    if (!byRule.has(f.rule)) byRule.set(f.rule, []);
    byRule.get(f.rule).push(f);
  }

  console.log('════════ 前端架构审计（文档[43] 守卫）════════');
  console.log(
    `扫描目录：${path.relative(ROOT, SRC)}   文件数：${files.length}`
  );
  console.log(
    `模式：${STRICT ? '严格（有违规即失败）' : '报告（只报告不失败）'}`
  );
  console.log('');

  for (const rule of RULES) {
    const list = byRule.get(rule.id) ?? [];
    const status = list.length === 0 ? '✅' : '❌';
    console.log(`${status} ${rule.id} ${rule.name} —— ${list.length} 处`);
    for (const f of list.slice(0, 40)) {
      console.log(`     ${f.file}:${f.line}  ${f.msg}`);
    }
    if (list.length > 40)
      console.log(`     …（其余 ${list.length - 40} 处省略）`);
  }

  const total = findings.length;
  console.log('');
  console.log(`合计违规：${total} 处`);
  if (total === 0) {
    console.log('架构守卫生效：分层与单一真源均已守住。');
  } else {
    console.log(
      '整改顺序见 doc-10月优化/[43]前端架构优化-文件域引用域-KISS化重构设计-小欧-2026-10-22.md（R1~R8）。'
    );
  }

  process.exit(STRICT && total > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error('[arch-check] 执行失败：', e);
  process.exit(2);
});
