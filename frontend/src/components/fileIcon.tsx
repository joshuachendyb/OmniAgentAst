// 编辑历史: 2026-10-21 小杨 - 文档[28]§7.0.5(v5.12) 新建：文件类型图标映射**单一真源** — 小杨-2026-10-21
/**
 * fileIcon —— 文件类型图标映射（单一真源）
 *
 * 为什么放全局 `src/components/`：树（features/files）、足迹面板（features/chat）、
 *   预览区（features/files）、引用 chip（components/markdown）**三域共用**，
 *   放任一 feature 都会产生跨 feature 引用（features/chat → features/files），
 *   故归全局共享展示组件目录（与 components/markdown 同级）。
 *
 * 分型口径（7.0.5 v5.12 路线甲）：
 * - 后端 `preview` 唯一真源 = `_preview_of()`：`TEXT_EXTS = {".txt", ".md"}`
 *   → `preview === 'text'` **只可能是 txt/md**；代码文件恒为 'none'（不可预览）
 * - 故只保留两型：md → FileMarkdownOutlined，txt → FileTextOutlined
 * - 亮/暗双通道：可预览 = PRIMARY 亮色；不可预览 = TEXT.WEAK + opacity 0.4
 */
import React from 'react';
import {
  FileMarkdownOutlined,
  FileOutlined,
  FileTextOutlined,
  FolderOutlined,
  PictureOutlined,
} from '@ant-design/icons';
import { Colors } from '@/utils/stepStyles';

export interface FileIconInput {
  type: 'dir' | 'file';
  preview?: 'text' | 'image' | 'none' | string;
  key: string;
}

export const fileIcon = (n: FileIconInput): React.ReactElement => {
  if (n.type === 'dir')
    return <FolderOutlined style={{ color: Colors.PRIMARY }} />;
  if (n.preview === 'text') {
    const ext = n.key.slice(n.key.lastIndexOf('.') + 1).toLowerCase();
    const Ico =
      ext === 'md' || ext === 'markdown'
        ? FileMarkdownOutlined
        : FileTextOutlined;
    return <Ico style={{ color: Colors.PRIMARY }} />; // 可预览 = 主蓝（亮）
  }
  if (n.preview === 'image')
    return <PictureOutlined style={{ color: Colors.PRIMARY }} />;
  return (
    <span title="该类型不支持预览（可复制路径或作 J3 工作目录）">
      {/* 不可预览 = 弱灰 + 半透明（暗）；原生 title 不叠 Tooltip（M16：Tooltip 只包文字 span） */}
      <FileOutlined style={{ color: Colors.TEXT.WEAK, opacity: 0.4 }} />
    </span>
  );
};
