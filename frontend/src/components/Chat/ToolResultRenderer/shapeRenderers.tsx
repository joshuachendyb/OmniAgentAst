// 编辑历史: 2026-08-27 小欧 - 重构: 形状渲染器(Tree/Code/Default), 移植自原views/*(复用优先), 删per-tool视图(禁backward/KISS)
// 编辑历史: 2026-08-27 小欧 - 修复chat-A: extractResult 合并 tool_result[].data_text 兜底, 新契约数据在 data_text 时树/码渲染不空
// 2026-08-27 小欧 - 三堂会审: tree列表/树容器统一边框 1px #f0f0f0(与行分割线一致), 半径保持6
// 编辑历史: 2026-08-28 小强 - 修复[18]: extractResult遍历tool_result数组合并data_text, 不再仅取首项 - 小强-2026-08-28
// 编辑历史: 2026-08-28 小欧 - ④B/b1: 去卡片填色改透明+左线, 令牌化, Code深色→浅底左线
/**
 * shapeRenderers - 按结果形状渲染(非 tool 名)
 *
 * 仅 3 类: tree(目录树/目录列表) / code(文件内容) / generic(其余全部)。
 * 逻辑移植自原 ListDirectoryView / GetDirectoryTreeView / ReadFileView / DefaultRenderer,
 * 统一从 step.execution_result 取数, 容器去框透明(契合"内容即容器"设计)。
 */
import React from 'react';
import { GenericResultRenderer } from '@/components/Chat/renderers';
import { Colors, BorderWidth, Spacing, Radius, FontSize } from '@/utils/stepStyles';
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
  const execData = (er.data || {}) as Record<string, unknown>;
  // 2026-08-27 小欧 修复: 新契约 tool_result[].data_text 常承载结构数据, 解析并与 execution_result.data 合并兜底(BUG-A 鲁棒, 不退化 data_text 场景)
  // 2026-08-28 小强 修复: 遍历tool_result数组合并所有data_text, 不再仅取首项(并行多工具结果保留)
  let textData: Record<string, unknown> = {};
  if (Array.isArray(step.tool_result)) {
    for (const item of step.tool_result) {
      if (item && typeof item === 'object') {
        const dt = (item as Record<string, unknown>).data_text;
        if (typeof dt === 'string') {
          try {
            const parsed = JSON.parse(dt) as Record<string, unknown>;
            textData = { ...textData, ...parsed };
          } catch {
            // 解析失败忽略
          }
        }
      }
    }
  }
  const data = { ...textData, ...execData } as Record<string, unknown>;
  const llmData = (er.llm_data || {}) as Record<string, unknown>;
  const status = (llmData.status || {}) as Record<string, unknown>;
  // 2026-08-27 小欧 修复: 指标来源归一 llm_data.metrics 与 data.metrics 合并(BUG-A 契约 metrics 在 data.metrics)
  const metrics = {
    ...(llmData.metrics || {}),
    ...(data.metrics || {}),
  } as Record<string, unknown>;
  const success = status.exec_code === 'success';
  const summary = (llmData.summary as string) || undefined;
  return { data, llmData, success, summary, metrics };
};

const formatFileSize = (bytes?: number): string => {
  if (bytes === null || bytes === undefined || bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024)
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`;
};

const formatMtime = (mtime?: number | string): string => {
  if (mtime === undefined || mtime === null) return '';
  const d =
    typeof mtime === 'number' ? new Date(mtime * 1000) : new Date(mtime);
  if (isNaN(d.getTime())) return String(mtime);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

// 容器: 去框透明(内容即容器)
const containerStyle: React.CSSProperties = {
  background: 'transparent',
  marginTop: 4,
  padding: 0,
};
const titleStyle = (success: boolean): React.CSSProperties => ({
  display: 'flex',
  alignItems: 'center',
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? Colors.SUCCESS : Colors.ERROR,
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

const TreeDirItem: React.FC<{
  entry: DirEntry;
  idx: number;
  total: number;
}> = ({ entry, idx, total }) => {
  const isDir = entry.type === 'directory';
  const name = entry.name || (isDir ? '(目录)' : '(文件)');
  return (
    <div
      key={`${name}-${idx}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        padding: '3px 0',
        borderBottom: idx < total - 1 ? `1px solid ${Colors.BORDER.LIGHT}` : 'none',
        fontSize: 13,
      }}
    >
      {isDir ? (
        <FolderOutlined style={{ color: Colors.WARNING, marginRight: 8 }} />
      ) : (
        <FileOutlined style={{ color: Colors.PRIMARY, marginRight: 8 }} />
      )}
      <span style={{ flex: 1, color: '#333', wordBreak: 'break-all' }}>
        {name}
      </span>
      {entry.size !== undefined && entry.size !== null && (
        <span style={{ color: '#8c8c8c', fontSize: 12, marginRight: 12 }}>
          {formatFileSize(entry.size)}
        </span>
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

const TreeTreeNode: React.FC<{ node: TreeNode; depth: number }> = ({
  node,
  depth,
}) => {
  const isDirectory = node.type === 'directory';
  const hasChildren = isDirectory && node.children && node.children.length > 0;
  const [expanded, setExpanded] = React.useState(depth < 2);
  return (
    <div style={{ fontFamily: 'Consolas, Monaco, monospace', fontSize: 13 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '1px 0',
          cursor: hasChildren ? 'pointer' : 'default',
          borderRadius: 2,
        }}
        onClick={() => hasChildren && setExpanded(!expanded)}
      >
        <span style={{ width: depth * 16, display: 'inline-block' }} />
        {hasChildren ? (
          <span style={{ marginRight: 4, fontSize: 10, color: '#8c8c8c' }}>
            {expanded ? <DownOutlined /> : <RightOutlined />}
          </span>
        ) : (
          <span
            style={{ marginRight: 4, width: 10, display: 'inline-block' }}
          />
        )}
        {isDirectory ? (
          <FolderOutlined style={{ marginRight: 6, fontSize: 14, color: Colors.WARNING }} />
        ) : (
          <FileOutlined style={{ marginRight: 6, fontSize: 14, color: Colors.PRIMARY }} />
        )}
        <span
          style={{
            color: isDirectory ? '#333' : '#595959',
            fontWeight: isDirectory ? 500 : 400,
          }}
        >
          {node.name || '(未命名)'}
        </span>
      </div>
      {expanded && hasChildren && (
        <div>
          {(node.children as TreeNode[]).map((child, idx) => (
            <TreeTreeNode
              key={`${child.path || child.name}-${depth}-${idx}`}
              node={child}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export const TreeResultRenderer: React.FC<{ step: ExecutionStep }> = ({
  step,
}) => {
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
          {success ? (
            <CheckCircleOutlined style={{ marginRight: 8 }} />
          ) : (
            <CloseCircleOutlined style={{ marginRight: 8 }} />
          )}
          列出目录{success ? '成功' : '失败'}
        </div>
          <div
            style={{
              maxHeight: 360,
              overflow: 'auto',
              background: 'transparent',
              borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
              borderRadius: 0,
              padding: `6px ${Spacing.SM}px 6px ${Spacing.MD}px`,
            }}
          >
            {entries.map((entry, idx) => (
              <TreeDirItem
                key={`${entry.name || idx}-${idx}`}
                entry={entry}
                idx={idx}
                total={entries.length}
              />
            ))}
          </div>
        <div style={{ marginTop: 12, fontSize: 12, color: '#595959' }}>
          共 {total} 项（目录 {dirCount} / 文件 {fileCount}），总大小{' '}
          {formatFileSize(totalSize)}
        </div>
        {data.truncated === true && (
          <div style={{ color: '#faad14', fontSize: 12, marginTop: 4 }}>
            结果已截断，仅显示部分
          </div>
        )}
        {summary && (
          <div
            style={{ color: '#595959', whiteSpace: 'pre-wrap', marginTop: 4 }}
          >
            {summary}
          </div>
        )}
      </div>
    );
  }

  // 分支B: 递归目录树(tree)
  if (tree) {
    const statistics =
      (data.statistics as {
        file_count?: number;
        dir_count?: number;
        total_size?: number;
      }) || {};
    return (
      <div style={containerStyle}>
        <div style={titleStyle(success)}>
          {success ? (
            <CheckCircleOutlined style={{ marginRight: 8 }} />
          ) : (
            <CloseCircleOutlined style={{ marginRight: 8 }} />
          )}
          <FolderOutlined style={{ marginRight: 6, color: '#faad14' }} />
          目录树结构
        </div>
          <div
            style={{
              maxHeight: 400,
              overflow: 'auto',
              background: 'transparent',
              borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
              borderRadius: 0,
              padding: `8px ${Spacing.MD}px`,
            }}
          >
            <TreeTreeNode node={tree} depth={0} />
          </div>
        <div style={{ marginTop: 8, fontSize: 12, color: '#595959' }}>
          文件 {statistics.file_count ?? 0} / 目录 {statistics.dir_count ?? 0}
          ，总大小 {formatFileSize(statistics.total_size ?? 0)}
        </div>
        {summary && (
          <div
            style={{ color: '#595959', whiteSpace: 'pre-wrap', marginTop: 4 }}
          >
            {summary}
          </div>
        )}
      </div>
    );
  }

  // 空结果
  return (
    <div style={containerStyle}>
      <div style={titleStyle(success)}>
        {success ? (
          <CheckCircleOutlined style={{ marginRight: 8 }} />
        ) : (
          <CloseCircleOutlined style={{ marginRight: 8 }} />
        )}
        目录{success ? '成功' : '失败'}
      </div>
      <div style={{ color: '#888', fontStyle: 'italic' }}>目录为空</div>
    </div>
  );
};

// ===== Code: 文件内容(高亮/行数指标) =====
export const CodeResultRenderer: React.FC<{ step: ExecutionStep }> = ({
  step,
}) => {
  const { data, success, summary, metrics } = extractResult(step);
  const content = (data.content as string) || '';
  const truncatedLines = data.truncated_lines as number | undefined;
  const lines = (metrics.lines as number) || 0;
  const totalLines = (metrics.total_lines as number) || 0;
  const bytes = (metrics.bytes as number) || 0;

  const TitleBadge = (
    <div style={titleStyle(success)}>
      {success ? (
        <CheckCircleOutlined style={{ marginRight: 8 }} />
      ) : (
        <CloseCircleOutlined style={{ marginRight: 8 }} />
      )}
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
    background: Colors.BG.LIGHT,
    borderLeft: `${BorderWidth.THICK}px solid ${Colors.BORDER.VERTICAL}`,
    border: `none`,
    borderRadius: Radius.SM,
    padding: `${Spacing.XS}px ${Spacing.SM}px`,
    marginTop: 6,
    fontSize: FontSize.SECONDARY,
    lineHeight: 1.6,
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all',
    maxHeight: 400,
    overflow: 'auto',
    color: Colors.TEXT.PRIMARY,
    fontFamily: 'Consolas, Monaco, "Courier New", monospace',
  };

  return (
    <div style={containerStyle}>
      {TitleBadge}
      <pre style={contentBackground}>{content}</pre>
      <div
        style={{
          marginTop: 8,
          fontSize: 12,
          color: '#595959',
          display: 'flex',
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        {lines > 0 && (
          <span
            style={{
              background: '#e6f7ff',
              padding: '2px 8px',
              borderRadius: 4,
              color: '#1677ff',
              fontWeight: 500,
            }}
          >
            <BarChartOutlined style={{ marginRight: 4 }} /> 本次 {lines} 行 / 共{' '}
            {totalLines} 行
          </span>
        )}
        {bytes > 0 && <span style={{ color: '#8c8c8c' }}>{bytes} 字节</span>}
        {truncatedLines !== undefined && truncatedLines > 0 && (
          <span style={{ color: '#faad14' }}>已截断 {truncatedLines} 行</span>
        )}
      </div>
      {summary && (
        <div style={{ color: '#595959', whiteSpace: 'pre-wrap', marginTop: 4 }}>
          {summary}
        </div>
      )}
    </div>
  );
};

// ===== Generic: 通用(数组→列表/对象→键值表/代码串→代码块, 由 GenericResultRenderer 承担) =====
export const DefaultResultRenderer: React.FC<{ step: ExecutionStep }> = ({
  step,
}) => {
  // 优先 tool_result 数组, 其次 execution_result, 兜底 content(同源提取, DRY)
  // 2026-08-27 小欧 三堂会审C9: ExecutionStep已有tool_result/execution_result/content字段, 移除类型断言
  const raw = step.tool_result ?? step.execution_result ?? step.content;
  if (raw == null) return null;
  const data =
    (typeof raw === 'object' && raw !== null
      ? (raw as Record<string, unknown>).data
      : raw) ?? (raw as Record<string, unknown>);
  if (!data) return null;
  return <GenericResultRenderer data={data as Record<string, unknown>} />;
};
