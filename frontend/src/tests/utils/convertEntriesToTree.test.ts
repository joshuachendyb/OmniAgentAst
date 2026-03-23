/**
 * convertEntriesToTree 函数测试
 * 【小强实现 2026-03-23】阶段4任务3：非递归模式虚拟列表
 */

import { describe, it, expect } from 'vitest';

interface TreeNode {
  key: string;
  title: string;
  type: 'directory' | 'file';
  children?: TreeNode[];
  path: string;
  size: number | null;
}

interface Entry {
  name: string;
  path: string;
  type: 'directory' | 'file';
  size: number | null;
}

function convertEntriesToTree(entries: Entry[], rootPath: string): TreeNode[] {
  if (!entries || entries.length === 0) {
    return [];
  }

  const pathToNode = new Map<string, TreeNode>();
  const rootNodes: TreeNode[] = [];

  // 标准化 rootPath，移除末尾斜杠
  const normalizedRoot = rootPath.replace(/\\/g, '/').replace(/\/$/, '');

  // 按 type 排序：目录在前，文件在后
  const sortedEntries = [...entries].sort((a, b) => {
    if (a.type === 'directory' && b.type === 'file') return -1;
    if (a.type === 'file' && b.type === 'directory') return 1;
    return a.name.localeCompare(b.name);
  });

  // 第一遍：创建所有节点
  for (const entry of sortedEntries) {
    const node: TreeNode = {
      key: entry.path,
      title: entry.name,
      type: entry.type,
      path: entry.path,
      size: entry.size,
      children: entry.type === 'directory' ? [] : undefined,
    };
    pathToNode.set(entry.path, node);
  }

  // 第二遍：构建父子关系
  for (const entry of sortedEntries) {
    const node = pathToNode.get(entry.path);
    if (!node) continue;

    // 标准化当前路径
    const normalizedPath = entry.path.replace(/\\/g, '/');

    // 计算相对路径：从 rootPath 之后的部分
    let relativePath: string;
    if (normalizedPath.startsWith(normalizedRoot + '/')) {
      relativePath = normalizedPath.substring(normalizedRoot.length + 1);
    } else if (normalizedPath.startsWith(normalizedRoot)) {
      relativePath = normalizedPath.substring(normalizedRoot.length);
    } else {
      // 相对路径情况
      relativePath = normalizedPath;
    }

    const parts = relativePath.split('/').filter(Boolean);

    if (parts.length === 0) {
      // 根路径本身就是节点
      rootNodes.push(node);
      continue;
    }

    if (parts.length === 1) {
      // 直接子项，父级是 rootPath
      const parentNode = pathToNode.get(normalizedRoot);
      if (parentNode?.children) {
        parentNode.children.push(node);
      } else {
        rootNodes.push(node);
      }
      continue;
    }

    // 多层嵌套：构建虚拟目录链
    let currentParentPath = normalizedRoot;

    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      const fullPath = currentParentPath + '/' + part;

      if (!pathToNode.has(fullPath)) {
        // 创建虚拟目录
        const virtualNode: TreeNode = {
          key: fullPath,
          title: part,
          type: 'directory',
          path: fullPath,
          size: null,
          children: [],
        };
        pathToNode.set(fullPath, virtualNode);

        // 链接到父级
        const parentNode = pathToNode.get(currentParentPath);
        if (parentNode?.children) {
          parentNode.children.push(virtualNode);
        } else if (currentParentPath === normalizedRoot) {
          // 第一层虚拟目录
          rootNodes.push(virtualNode);
        }
      }

      currentParentPath = fullPath;
    }

    // 最后一项添加到其父级
    const finalParentNode = pathToNode.get(currentParentPath);
    if (finalParentNode?.children) {
      finalParentNode.children.push(node);
    } else {
      rootNodes.push(node);
    }
  }

  // 清理空目录的 children
  const cleanEmptyChildren = (nodes: TreeNode[]): TreeNode[] => {
    return nodes.map(node => {
      if (node.type === 'directory' && node.children) {
        node.children = cleanEmptyChildren(node.children);
      }
      return node;
    }).sort((a, b) => {
      if (a.type === 'directory' && b.type === 'file') return -1;
      if (a.type === 'file' && b.type === 'directory') return 1;
      return a.title.localeCompare(b.title);
    });
  };

  return cleanEmptyChildren(rootNodes);
}

describe('convertEntriesToTree', () => {
  it('BUG修复: 嵌套目录 - App.tsx在src/components下', () => {
    const entries: Entry[] = [
      { name: 'App.tsx', path: 'D:/project/src/components/App.tsx', type: 'file', size: 1024 },
    ];
    const result = convertEntriesToTree(entries, 'D:/project');

    expect(result.length).toBe(1);
    expect(result[0].title).toBe('src');
    expect(result[0].type).toBe('directory');
    expect(result[0].children).toBeDefined();
    expect(result[0].children!.length).toBe(1);
    expect(result[0].children![0].title).toBe('components');
    expect(result[0].children![0].children![0].title).toBe('App.tsx');
  });

  it('多层嵌套目录', () => {
    const entries: Entry[] = [
      { name: 'index.ts', path: 'D:/project/src/lib/utils/helpers/index.ts', type: 'file', size: 512 },
    ];
    const result = convertEntriesToTree(entries, 'D:/project');

    expect(result.length).toBe(1);
    expect(result[0].title).toBe('src');
    expect(result[0].children![0].title).toBe('lib');
    expect(result[0].children![0].children![0].title).toBe('utils');
    expect(result[0].children![0].children![0].children![0].title).toBe('helpers');
    expect(result[0].children![0].children![0].children![0].children![0].title).toBe('index.ts');
  });

  it('直接子项 - 根目录下文件', () => {
    const entries: Entry[] = [
      { name: 'package.json', path: 'D:/project/package.json', type: 'file', size: 2048 },
    ];
    const result = convertEntriesToTree(entries, 'D:/project');

    expect(result.length).toBe(1);
    expect(result[0].title).toBe('package.json');
    expect(result[0].type).toBe('file');
  });

  it('多个文件在同一目录', () => {
    const entries: Entry[] = [
      { name: 'index.tsx', path: 'D:/project/src/index.tsx', type: 'file', size: 1024 },
      { name: 'App.tsx', path: 'D:/project/src/App.tsx', type: 'file', size: 2048 },
    ];
    const result = convertEntriesToTree(entries, 'D:/project');

    expect(result.length).toBe(1);
    expect(result[0].title).toBe('src');
    expect(result[0].children!.length).toBe(2);
    expect(result[0].children![0].title).toBe('App.tsx');
    expect(result[0].children![1].title).toBe('index.tsx');
  });

  it('混合场景 - 目录和文件', () => {
    const entries: Entry[] = [
      { name: 'config.json', path: 'D:/project/config.json', type: 'file', size: 256 },
      { name: 'App.tsx', path: 'D:/project/src/App.tsx', type: 'file', size: 1024 },
      { name: 'utils', path: 'D:/project/src/utils', type: 'directory', size: null },
    ];
    const result = convertEntriesToTree(entries, 'D:/project');

    expect(result.length).toBe(2);
    // config.json 直接在根目录
    const configNode = result.find(n => n.title === 'config.json');
    expect(configNode).toBeDefined();
    expect(configNode!.type).toBe('file');

    // src 目录
    const srcNode = result.find(n => n.title === 'src');
    expect(srcNode).toBeDefined();
    expect(srcNode!.type).toBe('directory');
    expect(srcNode!.children!.length).toBe(2);
  });

  it('Windows路径反斜杠处理', () => {
    const entries: Entry[] = [
      { name: 'App.tsx', path: 'D:\\project\\src\\components\\App.tsx', type: 'file', size: 1024 },
    ];
    const result = convertEntriesToTree(entries, 'D:\\project');

    expect(result.length).toBe(1);
    expect(result[0].title).toBe('src');
    expect(result[0].children![0].title).toBe('components');
    expect(result[0].children![0].children![0].title).toBe('App.tsx');
  });

  it('根路径带斜杠', () => {
    const entries: Entry[] = [
      { name: 'index.ts', path: 'D:/project/src/index.ts', type: 'file', size: 512 },
    ];
    const result = convertEntriesToTree(entries, 'D:/project/');

    expect(result.length).toBe(1);
    expect(result[0].title).toBe('src');
  });

  it('空数组输入', () => {
    const result = convertEntriesToTree([], 'D:/project');
    expect(result.length).toBe(0);
  });

  it('实际目录优先 - 真实目录在虚拟目录之前', () => {
    const entries: Entry[] = [
      { name: 'components', path: 'D:/project/src/components', type: 'directory', size: null },
      { name: 'App.tsx', path: 'D:/project/src/components/App.tsx', type: 'file', size: 1024 },
    ];
    const result = convertEntriesToTree(entries, 'D:/project');

    expect(result.length).toBe(1);
    expect(result[0].title).toBe('src');
    expect(result[0].children![0].title).toBe('components');
    expect(result[0].children![0].children![0].title).toBe('App.tsx');
  });
});
