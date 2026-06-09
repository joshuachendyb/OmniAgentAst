import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

const settingsDir = path.resolve(__dirname, '../../pages/Settings');

describe('Settings 拆分后的文件结构', () => {
  it('types.ts 存在且导出 ModelOption', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'types.ts'), 'utf-8');
    expect(content).toContain('interface ModelOption');
    expect(content).toContain('export');
  });

  it('components/ 目录下有 4 个子组件文件', () => {
    const files = fs.readdirSync(path.join(settingsDir, 'components'));
    expect(files).toContain('GlobalConfigArea.tsx');
    expect(files).toContain('ProviderList.tsx');
    expect(files).toContain('ProviderSettings.tsx');
    expect(files).toContain('SecuritySettings.tsx');
  });
});

describe('Settings 主组件', () => {
  it('使用 Tabs items 属性（非废弃的 TabPane）', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'index.tsx'), 'utf-8');
    expect(content).not.toContain('TabPane');
    expect(content).toContain('items={tabItems}');
  });

  it('子组件通过 import 引入', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'index.tsx'), 'utf-8');
    expect(content).toContain("from './components/ProviderSettings'");
    expect(content).toContain("from './components/SecuritySettings'");
  });

  it('export default 存在', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'index.tsx'), 'utf-8');
    expect(content).toContain('export default Settings');
  });
});

describe('ProviderSettings', () => {
  it('不含 validationResult 死代码', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'components/ProviderSettings.tsx'), 'utf-8');
    expect(content).not.toContain('validationResult');
  });

  it('getProviderDisplayName 为文件级函数', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'components/ProviderSettings.tsx'), 'utf-8');
    const funcMatch = content.match(/^(?:export )?(?:const|function) getProviderDisplayName/m);
    expect(funcMatch).not.toBeNull();
  });
});

describe('GlobalConfigArea', () => {
  it('包含查看配置和检测配置按钮', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'components/GlobalConfigArea.tsx'), 'utf-8');
    expect(content).toContain('查看配置');
    expect(content).toContain('检测配置');
  });

  it('使用 readConfigFile API', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'components/GlobalConfigArea.tsx'), 'utf-8');
    expect(content).toContain('readConfigFile');
  });
});

describe('ProviderList', () => {
  it('使用 ✓ 勾标记当前使用', () => {
    const content = fs.readFileSync(path.join(settingsDir, 'components/ProviderList.tsx'), 'utf-8');
    expect(content).toContain('✓');
  });
});
