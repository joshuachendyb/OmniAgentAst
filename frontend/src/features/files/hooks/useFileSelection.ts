// 编辑历史: 2026-10-22 小欧 - 新建：文件选中状态（纯选中域）— 小欧-2026-10-22
//   文档[43] R7：从 pages/Files 抽出选中相关状态，页面退化为布局壳。
//   收编：selected / multiFiles / lineRange / narrowTab。
import { useState } from 'react';
import type { FileNode } from '@/services/api/file.api';

export function useFileSelection() {
  const [selected, setSelected] = useState<FileNode | null>(null);
  const [multiFiles, setMultiFiles] = useState<FileNode[]>([]);
  const [lineRange, setLineRange] = useState<{
    start: number;
    end: number;
  } | null>(null);
  const [narrowTab, setNarrowTab] = useState<'tree' | 'preview'>('tree');

  return {
    selected,
    setSelected,
    multiFiles,
    setMultiFiles,
    lineRange,
    setLineRange,
    narrowTab,
    setNarrowTab,
  };
}
