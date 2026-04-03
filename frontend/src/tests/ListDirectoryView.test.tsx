/**
 * ListDirectoryView 测试用例
 * 
 * 测试 convertEntriesToTree 函数的预处理逻辑
 * 验证：过滤掉有对应绝对路径的相对路径条目，为没有绝对路径的目录创建虚拟条目
 * 
 * @author 小资
 * @date 2026-03-29
 */

import { describe, it, expect } from 'vitest';

// 模拟 Entry 类型
interface Entry {
  name: string;
  path: string;
  type: 'directory' | 'file';
  size: number | null;
}

// 模拟 TreeNode 类型
interface TreeNode {
  key: string;
  title: string;
  type: 'directory' | 'file';
  children?: TreeNode[];
  path: string;
  size: number | null;
}

// 模拟 convertEntriesToTree 函数的预处理逻辑
function preprocessEntries(entries: Entry[], rootPath: string): Entry[] {
  const normalizedRoot = rootPath.replace(/\\/g, "/").replace(/\/$/, "");

  // 分离相对路径和绝对路径条目
  const relativeEntries: Entry[] = [];
  const absoluteEntries: Entry[] = [];
  
  for (const entry of entries) {
    const normalizedPath = entry.path.replace(/\\/g, "/");
    if (normalizedPath.startsWith(normalizedRoot + "/")) {
      // 绝对路径条目
      absoluteEntries.push(entry);
    } else {
      // 相对路径条目
      relativeEntries.push(entry);
    }
  }
  
  // 找出没有对应绝对路径的相对路径条目
  const missingFromAbsolute = relativeEntries.filter(rel => {
    const relName = rel.name;
    return !absoluteEntries.some(abs => {
      const normalizedPath = abs.path.replace(/\\/g, "/");
      if (!normalizedPath.startsWith(normalizedRoot + "/")) return false;
      const firstPart = normalizedPath.substring(normalizedRoot.length + 1).split("/")[0];
      return firstPart === relName;
    });
  });
  
  // 为这些条目创建绝对路径条目
  const createdEntries = missingFromAbsolute.map(rel => ({
    name: rel.name,
    path: normalizedRoot + "/" + rel.name,
    type: rel.type,
    size: rel.size
  }));
  
  return [...absoluteEntries, ...createdEntries];
}

describe('convertEntriesToTree 预处理逻辑 - 实际数据测试', () => {
  it('应该过滤掉有对应绝对路径的相对路径条目', () => {
    // 实际数据：相对路径条目和绝对路径条目共存
    const entries: Entry[] = [
      // 相对路径条目（会被过滤）
      { name: '11.联想GRX', path: '11.联想GRX', type: 'directory', size: null },
      { name: '12.跨网项目', path: '12.跨网项目', type: 'directory', size: null },
      // 绝对路径条目（会保留）
      { name: '16 正样-配置项测试', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试', type: 'directory', size: null },
      { name: '17-正样-合格性测试', path: 'D:\\10-旧项目库\\11.联想GRX\\17-正样-合格性测试', type: 'directory', size: null },
      { name: '0.项目合同', path: 'D:\\10-旧项目库\\12.跨网项目\\0.项目合同', type: 'directory', size: null },
    ];

    const result = preprocessEntries(entries, 'D:\\10-旧项目库');
    
    // 应该只有绝对路径条目，相对路径条目被过滤
    expect(result).toHaveLength(3);
    expect(result.every(e => e.path.includes('\\10-旧项目库\\'))).toBe(true);
  });

  it('应该为没有绝对路径的目录创建虚拟条目', () => {
    // 实际数据：6.沈阳资管项目只有相对路径，没有绝对路径
    const entries: Entry[] = [
      { name: '6.沈阳资管项目', path: '6.沈阳资管项目', type: 'directory', size: null },
      { name: '11.联想GRX', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试', type: 'directory', size: null },
    ];

    const result = preprocessEntries(entries, 'D:\\10-旧项目库');
    
    // 应该有 2 个条目：1 个绝对路径 + 1 个创建的
    expect(result).toHaveLength(2);
    
    // 检查创建的条目
    const createdEntry = result.find(e => e.name === '6.沈阳资管项目');
    expect(createdEntry).toBeDefined();
    expect(createdEntry!.path).toBe('D:/10-旧项目库/6.沈阳资管项目');
  });

  it('应该正确处理嵌套目录，不产生重复', () => {
    // 实际数据：深层目录
    const entries: Entry[] = [
      // 相对路径条目（会被过滤）
      { name: '11.联想GRX', path: '11.联想GRX', type: 'directory', size: null },
      // 绝对路径条目（会保留）
      { name: '16 正样-配置项测试', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试', type: 'directory', size: null },
      { name: '1安全拍照-正样', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试\\1安全拍照-正样', type: 'directory', size: null },
    ];

    const result = preprocessEntries(entries, 'D:\\10-旧项目库');
    
    // 应该只有绝对路径条目，没有相对路径条目
    expect(result).toHaveLength(2);
    expect(result[0].name).toBe('16 正样-配置项测试');
    expect(result[1].name).toBe('1安全拍照-正样');
  });

  it('应该正确处理 Windows 路径和 Linux 路径', () => {
    const entries: Entry[] = [
      // Windows 路径
      { name: '16 正样-配置项测试', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试', type: 'directory', size: null },
      // Linux 路径
      { name: '17-正样-合格性测试', path: 'D:/10-旧项目库/11.联想GRX/17-正样-合格性测试', type: 'directory', size: null },
    ];

    const result = preprocessEntries(entries, 'D:\\10-旧项目库');
    
    // 两种路径格式都应该被识别为绝对路径
    expect(result).toHaveLength(2);
  });

  it('应该正确处理空数组', () => {
    const entries: Entry[] = [];
    const result = preprocessEntries(entries, 'D:\\10-旧项目库');
    
    expect(result).toHaveLength(0);
  });

  it('应该正确处理只有一级目录的情况', () => {
    const entries: Entry[] = [
      { name: '6.沈阳资管项目', path: '6.沈阳资管项目', type: 'directory', size: null },
    ];

    const result = preprocessEntries(entries, 'D:\\10-旧项目库');
    
    // 应该创建虚拟条目
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('6.沈阳资管项目');
    expect(result[0].path).toBe('D:/10-旧项目库/6.沈阳资管项目');
  });
});
