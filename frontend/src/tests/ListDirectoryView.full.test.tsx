/**
 * ListDirectoryView 完整树构建测试
 * 
 * 测试完整的 convertEntriesToTree 函数，包括树构建逻辑
 * 验证：没有重复节点，目录类型正确
 * 
 * @author 小强
 * @date 2026-03-30
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

/**
 * 将扁平的 entries 数组转换为树形结构（供 Tree 组件使用）
 * 这是从 ListDirectoryView.tsx 复制的完整函数
 */
function convertEntriesToTree(entries: Entry[], rootPath: string): TreeNode[] {
  if (!entries || entries.length === 0) {
    return [];
  }

  // 标准化 rootPath，移除末尾斜杠，统一使用正斜杠
  const normalizedRoot = rootPath.replace(/\\/g, "/").replace(/\/$/, "");

  // 第一步：标准化所有条目路径，并过滤相对路径
  const normalizedEntries: Entry[] = [];
  const relativeEntries: Entry[] = [];
  
  for (const entry of entries) {
    // 标准化路径：统一使用正斜杠
    const normalizedPath = entry.path.replace(/\\/g, "/");
    
    // 检查是否为绝对路径（以rootPath开头）
    if (normalizedPath.startsWith(normalizedRoot + "/")) {
      // 绝对路径条目：使用标准化路径
      normalizedEntries.push({
        ...entry,
        path: normalizedPath
      });
    } else if (normalizedPath === normalizedRoot) {
      // rootPath本身
      normalizedEntries.push({
        ...entry,
        path: normalizedPath
      });
    } else {
      // 相对路径条目
      relativeEntries.push({
        ...entry,
        path: normalizedPath
      });
    }
  }
  
  // 第二步：为没有对应绝对路径的相对路径条目创建虚拟条目
  const missingFromAbsolute = relativeEntries.filter(rel => {
    const relName = rel.name;
    return !normalizedEntries.some(abs => {
      // 检查是否有同名的第一级目录
      const pathAfterRoot = abs.path.substring(normalizedRoot.length + 1);
      if (!pathAfterRoot) return false;
      const firstPart = pathAfterRoot.split("/")[0];
      return firstPart === relName;
    });
  });
  
  // 创建虚拟条目
  const virtualEntries = missingFromAbsolute.map(rel => ({
    name: rel.name,
    path: normalizedRoot + "/" + rel.name,
    type: rel.type,
    size: rel.size
  }));
  
  // 合并所有条目
  const allEntries = [...normalizedEntries, ...virtualEntries];
  
  // 第三步：去重 - 按标准化路径去重
  const uniqueEntries: Entry[] = [];
  const seenPaths = new Set<string>();
  
  for (const entry of allEntries) {
    const normalizedPath = entry.path.replace(/\\/g, "/");
    if (!seenPaths.has(normalizedPath)) {
      seenPaths.add(normalizedPath);
      uniqueEntries.push({
        ...entry,
        path: normalizedPath
      });
    }
  }
  
  // 第四步：按路径排序，确保父目录在前
  uniqueEntries.sort((a, b) => {
    // 先按类型排序：目录在前
    if (a.type === "directory" && b.type === "file") return -1;
    if (a.type === "file" && b.type === "directory") return 1;
    // 然后按路径深度排序
    const aDepth = a.path.split("/").length;
    const bDepth = b.path.split("/").length;
    if (aDepth !== bDepth) return aDepth - bDepth;
    // 最后按名称排序
    return a.name.localeCompare(b.name);
  });
  
  // 第五步：构建树结构
  const pathToNode = new Map<string, TreeNode>();
  const rootNodes: TreeNode[] = [];
  
  // 创建所有节点
  for (const entry of uniqueEntries) {
    const node: TreeNode = {
      key: entry.path,
      title: entry.name,
      type: entry.type,
      path: entry.path,
      size: entry.size,
      children: entry.type === "directory" ? [] : undefined,
    };
    pathToNode.set(entry.path, node);
  }
  
  // 构建父子关系
  for (const entry of uniqueEntries) {
    const node = pathToNode.get(entry.path);
    if (!node) continue;
    
    // 计算相对路径
    const normalizedPath = entry.path;
    let relativePath: string;
    
    if (normalizedPath === normalizedRoot) {
      // rootPath本身，添加到根节点
      rootNodes.push(node);
      continue;
    } else if (normalizedPath.startsWith(normalizedRoot + "/")) {
      relativePath = normalizedPath.substring(normalizedRoot.length + 1);
    } else {
      // 虚拟条目，相对路径
      relativePath = normalizedPath;
    }
    
    const parts = relativePath.split("/").filter(Boolean);
    
    if (parts.length === 0) {
      // 这种情况不应该发生
      continue;
    }
    
    // 找到或创建父节点
    let parentPath = normalizedRoot;
    let parent = pathToNode.get(parentPath);
    
    // 如果没有父节点，创建虚拟父节点
    if (!parent) {
      // 创建根节点虚拟目录
      parent = {
        key: normalizedRoot,
        title: normalizedRoot.split("/").pop() || normalizedRoot,
        type: "directory",
        path: normalizedRoot,
        size: null,
        children: [],
      };
      pathToNode.set(normalizedRoot, parent);
      rootNodes.push(parent);
    }
    
    // 处理路径中的每一部分
    for (let i = 0; i < parts.length - 1; i++) {
      const part = parts[i];
      const childPath = parentPath + "/" + part;
      
      // 检查子节点是否存在
      if (!pathToNode.has(childPath)) {
        // 创建虚拟目录节点
        const virtualNode: TreeNode = {
          key: childPath,
          title: part,
          type: "directory",
          path: childPath,
          size: null,
          children: [],
        };
        pathToNode.set(childPath, virtualNode);
        
        // 添加到父节点
        if (parent?.children) {
          parent.children.push(virtualNode);
        }
      }
      
      parentPath = childPath;
      parent = pathToNode.get(childPath);
    }
    
    // 添加当前节点到其父节点
    if (parent?.children) {
      parent.children.push(node);
    } else {
      // 没有父节点，添加到根节点
      rootNodes.push(node);
    }
  }
  
  // 第六步：清理和排序
  const cleanAndSort = (nodes: TreeNode[]): TreeNode[] => {
    return nodes
      .map((node) => {
        if (node.type === "directory" && node.children) {
          node.children = cleanAndSort(node.children);
        }
        return node;
      })
      .sort((a, b) => {
        if (a.type === "directory" && b.type === "file") return -1;
        if (a.type === "file" && b.type === "directory") return 1;
        return a.title.localeCompare(b.title);
      });
  };
  
  // 第七步：去重根节点
  const seenRootKeys = new Set<string>();
  const dedupedRootNodes: TreeNode[] = [];
  
  for (const node of rootNodes) {
    if (!seenRootKeys.has(node.key)) {
      seenRootKeys.add(node.key);
      dedupedRootNodes.push(node);
    }
  }
  
  return cleanAndSort(dedupedRootNodes);
}

describe('convertEntriesToTree 完整测试 - 模拟实际数据', () => {
  it('应该正确处理实际数据，无重复节点', () => {
    // 模拟实际数据：包含相对路径和绝对路径
    const entries: Entry[] = [
      // 相对路径条目（会被过滤）
      { name: '11.联想GRX', path: '11.联想GRX', type: 'directory', size: null },
      { name: '12.跨网项目', path: '12.跨网项目', type: 'directory', size: null },
      { name: '3.学习APP项目', path: '3.学习APP项目', type: 'directory', size: null },
      { name: '4.取证WJ项目', path: '4.取证WJ项目', type: 'directory', size: null },
      { name: '6.沈阳资管项目', path: '6.沈阳资管项目', type: 'directory', size: null },
      
      // 绝对路径条目（会保留）
      { name: '10-旧项目库', path: 'D:\\10-旧项目库', type: 'directory', size: null },
      { name: '15-1正样-合格性测试说明', path: 'D:\\10-旧项目库\\11.联想GRX\\15-1正样-合格性测试说明', type: 'directory', size: null },
      { name: '16 正样-配置项测试', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试', type: 'directory', size: null },
      { name: '17-正样-合格性测试', path: 'D:\\10-旧项目库\\11.联想GRX\\17-正样-合格性测试', type: 'directory', size: null },
      { name: '1安全拍照-正样', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试\\1安全拍照-正样', type: 'directory', size: null },
      { name: '1安全拍照-正样', path: 'D:\\10-旧项目库\\11.联想GRX\\17-正样-合格性测试\\1安全拍照-正样', type: 'directory', size: null },
    ];

    const tree = convertEntriesToTree(entries, 'D:\\10-旧项目库');
    
    // 检查根节点
    expect(tree).toBeDefined();
    expect(tree.length).toBeGreaterThan(0);
    
    // 收集所有节点的key，检查是否有重复
    const allKeys = new Set<string>();
    const collectKeys = (nodes: TreeNode[]) => {
      for (const node of nodes) {
        expect(allKeys.has(node.key)).toBe(false); // 确保没有重复的key
        allKeys.add(node.key);
        if (node.children) {
          collectKeys(node.children);
        }
      }
    };
    
    collectKeys(tree);
    
    // 检查特定节点是否存在
    const findNodeByKey = (nodes: TreeNode[], key: string): TreeNode | null => {
      for (const node of nodes) {
        if (node.key === key) return node;
        if (node.children) {
          const found = findNodeByKey(node.children, key);
          if (found) return found;
        }
      }
      return null;
    };
    
    // 检查11.联想GRX节点是否存在（应该是目录类型）
    const lianxiangNode = findNodeByKey(tree, 'D:/10-旧项目库/11.联想GRX');
    expect(lianxiangNode).toBeDefined();
    expect(lianxiangNode!.type).toBe('directory');
    expect(lianxiangNode!.title).toBe('11.联想GRX');
    
    // 检查子节点
    expect(lianxiangNode!.children).toBeDefined();
    expect(lianxiangNode!.children!.length).toBeGreaterThan(0);
  });

  it('应该正确处理多层嵌套目录', () => {
    const entries: Entry[] = [
      // 绝对路径条目
      { name: '10-旧项目库', path: 'D:\\10-旧项目库', type: 'directory', size: null },
      { name: '11.联想GRX', path: 'D:\\10-旧项目库\\11.联想GRX', type: 'directory', size: null },
      { name: '16 正样-配置项测试', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试', type: 'directory', size: null },
      { name: '1安全拍照-正样', path: 'D:\\10-旧项目库\\11.联想GRX\\16 正样-配置项测试\\1安全拍照-正样', type: 'directory', size: null },
    ];

    const tree = convertEntriesToTree(entries, 'D:\\10-旧项目库');
    
    // 调试信息
    console.log('树长度:', tree.length);
    console.log('根节点:', tree.map(n => n.title));
    
    // 检查树结构
    expect(tree.length).toBe(1); // 只有一个根节点：10-旧项目库
    
    const root = tree[0];
    expect(root.title).toBe('10-旧项目库');
    expect(root.type).toBe('directory');
    expect(root.children).toBeDefined();
    expect(root.children!.length).toBe(1); // 11.联想GRX
    
    const lianxiangNode = root.children![0];
    expect(lianxiangNode.title).toBe('11.联想GRX');
    expect(lianxiangNode.type).toBe('directory');
    expect(lianxiangNode.children).toBeDefined();
    expect(lianxiangNode.children!.length).toBe(1); // 16 正样-配置项测试
    
    const testNode = lianxiangNode.children![0];
    expect(testNode.title).toBe('16 正样-配置项测试');
    expect(testNode.type).toBe('directory');
    expect(testNode.children).toBeDefined();
    expect(testNode.children!.length).toBe(1); // 1安全拍照-正样
    
    const finalNode = testNode.children![0];
    expect(finalNode.title).toBe('1安全拍照-正样');
    expect(finalNode.type).toBe('directory');
  });

  it('应该为没有绝对路径的目录创建虚拟条目', () => {
    const entries: Entry[] = [
      // 只有相对路径，没有绝对路径
      { name: '6.沈阳资管项目', path: '6.沈阳资管项目', type: 'directory', size: null },
      { name: '10-旧项目库', path: 'D:\\10-旧项目库', type: 'directory', size: null },
    ];

    const tree = convertEntriesToTree(entries, 'D:\\10-旧项目库');
    
    // 应该有1个根节点：10-旧项目库
    expect(tree.length).toBe(1);
    
    // 检查虚拟条目是否被添加到根节点下
    const rootNode = tree[0];
    expect(rootNode.title).toBe('10-旧项目库');
    expect(rootNode.children).toBeDefined();
    expect(rootNode.children!.length).toBe(1); // 6.沈阳资管项目
    
    // 检查虚拟条目
    const shenyangNode = rootNode.children![0];
    expect(shenyangNode).toBeDefined();
    expect(shenyangNode.title).toBe('6.沈阳资管项目');
    expect(shenyangNode.type).toBe('directory');
    expect(shenyangNode.path).toBe('D:/10-旧项目库/6.沈阳资管项目');
  });

  it('应该正确处理文件类型', () => {
    const entries: Entry[] = [
      { name: '10-旧项目库', path: 'D:\\10-旧项目库', type: 'directory', size: null },
      { name: '11.联想GRX', path: 'D:\\10-旧项目库\\11.联想GRX', type: 'directory', size: null },
      { name: '文件1.txt', path: 'D:\\10-旧项目库\\11.联想GRX\\文件1.txt', type: 'file', size: 1024 },
    ];

    const tree = convertEntriesToTree(entries, 'D:\\10-旧项目库');
    
    const root = tree[0];
    expect(root.title).toBe('10-旧项目库');
    
    const lianxiangNode = root.children![0];
    expect(lianxiangNode.title).toBe('11.联想GRX');
    
    const fileNode = lianxiangNode.children![0];
    expect(fileNode.title).toBe('文件1.txt');
    expect(fileNode.type).toBe('file');
    expect(fileNode.size).toBe(1024);
  });
});