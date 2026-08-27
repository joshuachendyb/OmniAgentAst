// 编辑历史: 2026-08-27 小欧 - 重构: 形状渲染器(Tree/Code/Default), 移植自原views/*(复用优先), 删per-tool视图(禁backward/KISS)
/**
 * shapeRenderers - 按结果形状渲染(非 tool 名)
 *
 * 仅 3 类: tree(目录树/目录列表) / code(文件内容) / generic(其余全部)。
 * 逻辑移植自原 ListDirectoryView / GetDirectoryTreeView / ReadFileView / DefaultRenderer,
 * 统一从 step.execution_result 取数, 容器去框透明(契合"内容即容器"设计)。
 */
import React from 'react';
import { GenericResultRenderer } from '@/components/Chat/renderers';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  FolderOutlined,
  FileOutlined,
  InboxOutlined,
  DownOutlined,
  RightOutlined,
  BarChartOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import type { ExecutionStep } from '../../../types/execution';

// ===== 通用取数(单一来源, DRY) =====
interface ResultData {
  data: Record<string, unknown>;
  llmData: Record<string, unknown>;
  success: boolean;
  summary?: string;
  metrics: Record<string, unknown>;
}

const extractResult = (step: ExecutionStep): ResultData => {
  const er = (step.execution_result || {}) as Record<string, unknown>;
  const data = (er.data || {}) as Record<string, unknown>;
  const llmData = (er.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;
  const metrics = (llmData.metrics || {}) as Record<string, unknown>;
  const success = status.exec_code === 'success';
  const summary = (llmData.summary as string) || undefined;
  return { data, llmData, success, summary, metrics };
};

const formatFileSize = (bytes?: number): string => {
  if (bytes === null || bytes === undefined || bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
};

const formatMtime = (mtime?: number | string): string => {
  if (mtime === undefined || mtime === null) return '';
  const d = typeof mtime === 'number' ? new Date(mtime * 1000) : new Date(mtime);
  if (isNaN(d.getTime())) return String(mtime);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

// 容器: 去框透明(内容即容器)
const containerStyle: React.CSSProperties = { background: 'transparent', marginTop: 4, padding: 0 };
const titleStyle = (success: boolean): React.CSSProperties => ({
  display: 'flex',
  alignItems: 'center',
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? '#52c41a' : '#ff4d4f',
});

// ===== Tree: 目录树 / 目录列表(二形合一, 按 data.entries / data.tree 判定) =====
interface DirEntry {
  name?: string;
  type?: 'file' | 'directory';
  mtime?: number | string;
  size?: number;
}
interface TreeNode {
  name?: string;
  path?: string;
  type?: 'file' | 'directory';
  children?: TreeNode[];
}

const TreeDirItem: React.FC<{ entry: DirEntry; idx: number; total: number }> = ({ entry, idx, total }) => {
  const isDir = entry.type === 'directory';
  const name = entry.name || (isDir ? '(目录)' : '(文件)');
  return (
    <div
      key={`${name}-${idx}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '3px 0',
        borderBottom: idx < total - 1 ? '1px solid #f0f0f0' : 'none',
        fontSize: 13,
      }}
    >
      {isDir ? (
        <FolderOutlined style={{ color: '#faad14', marginRight: 8 }} />
      ) : (
        <FileOutlined style={{ color: '#1677ff', marginRight: 8 }} />
      )}
      <span style={{ flex: 1, color: '#333', wordBreak: 'break-all' }}>{name}</span>
      {entry.size !== undefined && entry.size !== null && (
        <span style={{ color: '#8c8c8c', fontSize: 12, marginRight: 12 }}>{formatFileSize(entry.size)}</span>
      )}
      {entry.mtime !== undefined && entry.mtime !== null && (
        <span style={{ color: '#bfbfbf', fontSize: 12 }}>
          <InboxOutlined style={{ marginRight: 4, color: '#d9d9d9' }} />
          {formatMtime(entry.mtime)}
        </span>
      )}
    </div>
  );
};

const TreeTreeNode: React.FC<{ node: TreeNode; depth: number }> = ({ node, depth }) => {
  const isDirectory = node.type === 'directory';
  const hasChildren = isDirectory && node.children && node.children.length > 0;
  const [expanded, setExpanded] = React.useState(depth < 2);
  return (
    <div style={{ fontFamily: 'Consolas, Monaco, monospace', fontSize: 13 }}>
      <div
        style={{ display: 'flex', alignItems: 'center', padding: '1px 0', cursor: hasChildren ? 'pointer' : 'default', borderRadius: 2 }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        <span style={{ width: depth * 16, display: 'inline-block' }} />
        {hasChildren ? (
          <span style={{ marginRight: 4, fontSize: 10, color: '#8c8c8c' }}>{expanded ? <DownOutlined /> : <RightOutlined />}</span>
        ) : (
          <span style={{ marginRight: 4, width: 10, display: 'inline-block' }} />
        )}
        {isDirectory ? (
          <FolderOutlined style={{ marginRight: 6, fontSize: 14, color: '#faad14' }} />
        ) : (
          <FileOutlined style={{ marginRight: 6, fontSize: 14, color: '#1677ff' }} />
        )}
        <span style={{ color: isDirectory ? '#333' : '#595959', fontWeight: isDirectory ? 500 : 400 }}>{node.name || '(未命名)'}</span>
      </div>
      {expanded && hasChildren && (
        <div>
          {(node.children as TreeNode[]).map((child, idx) => (
            <TreeTreeNode key={`${child.path || child.name}-${depth}-${idx}`} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
};

export const TreeResultRenderer: React.FC<{ step: ExecutionStep }> = ({ step }) => {
  const { data, success, summary, metrics } = extractResult(step);
  const entries = (data.entries as DirEntry[] | undefined) || [];
  const tree = data.tree as TreeNode | null | undefined;

  // 分支A: 目录列表(entries)
  if (entries.length > 0) {
    const total = (metrics.total as number) || 0;
    const dirCount = (metrics.dir_count as number) || 0;
    const fileCount = (metrics.file_count as number) || 0;
    const totalSize = (metrics.total_size as number) || 0;
    return (
      <div style={containerStyle}>
        <div style={titleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          列出目录{success ? '成功' : '失败'}
        </div>
        <div style={{ maxHeight: 360, overflow: 'auto', background: '#fafafa', borderRadius: 6, padding: '6px 10px' }}>
          {entries.map((entry, idx) => (
            <TreeDirItem key={`${entry.name || idx}-${idx}`} entry={entry} idx={idx} total={entries.length} />
          ))}
        </div>
        <div style={{ marginTop: 12, fontSize: 12, color: '#595959' }}>
          共 {total} 项（目录 {dirCount} / 文件 {fileCount}），总大小 {formatFileSize(totalSize)}
        </div>
        {data.truncated === true && <div style={{ color: '#faad14', fontSize: 12, marginTop: 4 }}>结果已截断，仅显示部分</div>}
        {summary && <div style={{ color: '#595959', whiteSpace: 'pre-wrap', marginTop: 4 }}>{summary}</div>}
      </div>
    );
  }

  // 分支B: 递归目录树(tree)
  if (tree) {
    const statistics = (data.statistics as { file_count?: number; dir_count?: number; total_size?: number }) || {};
    return (
      <div style={containerStyle}>
        <div style={titleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          <FolderOutlined style={{ marginRight: 6, color: '#faad14' }} />
          目录树结构
        </div>
        <div style={{ maxHeight: 400, overflow: 'auto', background: '#fafafa', borderRadius: 6, padding: '8px 12px' }}>
          <TreeTreeNode node={tree} depth={0} />
        </div>
        <div style={{ marginTop: 8, fontSize: 12, color: '#595959' }}>
          文件 {statistics.file_count ?? 0} / 目录 {statistics.dir_count ?? 0}，总大小 {formatFileSize(statistics.total_size ?? 0)}
        </div>
        {summary && <div style={{ color: '#595959', whiteSpace: 'pre-wrap', marginTop: 4 }}>{summary}</div>}
      </div>
    );
  }

  // 空结果
  return (
    <div style={containerStyle}>
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        目录{success ? '成功' : '失败'}
      </div>
      <div style={{ color: '#888', fontStyle: 'italic' }}>目录为空</div>
    </div>
  );
};

// ===== Code: 文件内容(高亮/行数指标) =====
export const CodeResultRenderer: React.FC<{ step: ExecutionStep }> = ({ step }) => {
  const { data, success, summary, metrics } = extractResult(step);
  const content = (data.content as string) || '';
  const truncatedLines = data.truncated_lines as number | undefined;
  const lines = (metrics.lines as number) || 0;
  const totalLines = (metrics.total_lines as number) || 0;
  const bytes = (metrics.bytes as number) || 0;

  const TitleBadge = (
    <div style={titleStyle(success)}>
      {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
      读取文件{success ? '成功' : '失败'}
    </div>
  );

  if (!content) {
    return (
      <div style={containerStyle}>
        {TitleBadge}
        <div style={{ color: '#888', fontStyle: 'italic' }}>
          <FileTextOutlined style={{ marginRight: 8 }} />
          文件内容为空
        </div>
      </div>
    );
  }

  const contentBackground: React.CSSProperties = {
    background: '#1e1e1e',
    border: '1px solid #303030',
    borderRadius: 8,
    padding: '10px 14px',
    marginTop: 6,
    fontSize: '0.9em',
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    maxHeight: 400,
    overflow: 'auto',
    color: '#d4d4d4',
    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
  };

  return (
    <div style={containerStyle}>
      {TitleBadge}
      <pre style={contentBackground}>{content}</pre>
      <div style={{ marginTop: 8, fontSize: 12, color: '#595959', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        {lines > 0 && (
          <span style={{ background: '#e6f7ff', padding: '2px 8px', borderRadius: 4, color: '#1677ff', fontWeight: 500 }}>
            <BarChartOutlined style={{ marginRight: 4 }} /> 本次 {lines} 行 / 共 {totalLines} 行
          </span>
        )}
        {bytes > 0 && <span style={{ color: '#8c8c8c' }}>{bytes} 字节</span>}
        {truncatedLines !== undefined && truncatedLines > 0 && <span style={{ color: '#faad14' }}>已截断 {truncatedLines} 行</span>}
      </div>
      {summary && <div style={{ color: '#595959', whiteSpace: 'pre-wrap', marginTop: 4 }}>{summary}</div>}
    </div>
  );
};

// ===== Generic: 通用(数组→列表/对象→键值表/代码串→代码块, 由 GenericResultRenderer 承担) =====
export const DefaultResultRenderer: React.FC<{ step: ExecutionStep }> = ({ step }) => {
  // 优先 tool_result 数组, 其次 execution_result, 兜底 content(同源提取, DRY)
  const tr = (step as { tool_result?: unknown }).tool_result;
  const raw = tr != null ? tr : (step as { execution_result?: unknown }).execution_result != null ? (step as { execution_result?: unknown }).execution_result : (step as { content?: unknown }).content;
  if (raw == null) return null;
  const data = (typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>).data : raw) ?? (raw as Record<string, unknown>);
  if (!data) return null;
  return <GenericResultRenderer data={data as Record<string, unknown>} />;
};
