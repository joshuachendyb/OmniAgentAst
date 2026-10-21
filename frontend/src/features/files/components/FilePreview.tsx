// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.10 + 9.8 新建：预览区（文本/图片/选区/过期检测） — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28]§9.8(O1/O2)：refresh 单请求化（mtime 同源同拍）+ 体量分段提示（token 数） — 小杨-2026-10-21
/**
 * FilePreview —— 选中文件的预览区（只读）
 *
 * 能力：文本（保留换行缩进、可滚动、不做语法高亮）/ 图片（objectURL 自适应）/
 *   选区引用（F8）/ 过期提示（I9，措辞"可能已被修改"）/ 体量提示（O2，token 数 + 分级警示）。
 *
 * O1（单请求刷新）：`/files/read` 现在一次带回正文与 mtime（同源同拍），
 *   刷新时比对新旧 mtime 即可判"可能已被修改"，**不再绕道再拉一次 tree**。
 */
import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Empty } from 'antd';
import type { FileNode, ReadResponse } from '@/services/api/file.api';
import { fileApi, ImageUnchanged } from '@/services/api/file.api';
import { formatBytes } from '@/utils/format';
import { refCost } from '@/utils/refCost';
import { chatTokens } from '@/theme/tokens';
import { Colors, Spacing } from '@/utils/stepStyles';

export interface FilePreviewProps {
  node: FileNode | null;
  /** 深链行号（&line=start-end），打开时滚动并高亮 */
  lineRange?: { start: number; end: number } | null;
  /** 发送到输入框（F4） */
  onSendFile: (content: string, node: FileNode) => void;
  /** 引用选区（F8） */
  onSendSelection: (
    content: string,
    node: FileNode,
    lineRange: { start: number; end: number }
  ) => void;
  /** 暴露给父级的刷新句柄（O10 三同刷用） */
  refreshRef?: React.MutableRefObject<(() => void) | null>;
}

export const FilePreview: React.FC<FilePreviewProps> = ({
  node,
  lineRange,
  onSendFile,
  onSendSelection,
  refreshRef,
}) => {
  const [text, setText] = useState<ReadResponse | null>(null);
  const [imgUrl, setImgUrl] = useState<string | null>(null);
  const [stale, setStale] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<{ start: number; end: number } | null>(null);
  const preRef = useRef<HTMLPreElement | null>(null);
  /** 打开时的 mtime（用于"可能已被修改"判定） */
  const openedMtime = useRef<string | null>(null);
  /** 竞态防护（I7）：只认最后一次请求的结果 */
  const reqSeq = useRef(0);

  const load = async (target: FileNode) => {
    const seq = ++reqSeq.current;
    setErr(null);
    try {
      if (target.preview === 'text') {
        const r = await fileApi.readFile(target.key);
        if (seq !== reqSeq.current) return; // 已被更新的请求取代
        setText(r);
        releaseImage(); // 2026-10-21 小杨 - 审计修复：切走时**必须 revoke**（原 setImgUrl(null) 直接丢 URL 字符串 → 泄漏）
        openedMtime.current = r.mtime;
        setStale(false);
      } else if (target.preview === 'image') {
        const blob = await fileApi.loadImageBlob(target.key);
        if (seq !== reqSeq.current) return;
        setImgUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return URL.createObjectURL(blob);
        });
        setText(null);
        setStale(false);
      } else {
        setText(null);
        releaseImage();
      }
    } catch (e) {
      if (seq !== reqSeq.current) return;
      if (e instanceof ImageUnchanged) {
        setStale(false); // 图片未变化（304）不算失败，保留旧图
      } else {
        setErr(e instanceof Error ? e.message : '加载失败');
      }
    }
  };

  /**
   * 释放当前图片的 objectURL（2026-10-21 小杨 - 审计修复：原实现 setImgUrl(null) 只是丢掉 URL 字符串，
   * blob 内存不释放 → 反复切图 / 离开页面都会泄漏）。
   */
  const releaseImage = () => {
    setImgUrl((old) => {
      if (old) URL.revokeObjectURL(old);
      return null;
    });
  };

  // 卸载时释放（组件消失不留 blob）
  useEffect(() => {
    return () => {
      setImgUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });
    };
  }, []);

  useEffect(() => {
    if (!node) {
      setText(null);
      releaseImage();
      setStale(false);
      setErr(null);
      return;
    }
    void load(node);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node?.key]);

  /** O1：refresh 单请求化 —— 一次 /files/read 同时拿到"新鲜度判定 + 内容重载"
   *  2026-10-21 小杨 - 审计修复：refresh 也要走 reqSeq 守卫
   *   （原文 refresh 无守卫 → 刷新 A 的请求晚于切到 B 的请求返回 → 头部显示 B、正文却是 A） */
  const refresh = async () => {
    if (!node) return;
    const seq = ++reqSeq.current;
    try {
      if (node.preview === 'text') {
        const r = await fileApi.readFile(node.key);
        if (seq !== reqSeq.current) return; // 已被更新的请求取代
        if (r.mtime && r.mtime !== openedMtime.current) setStale(true);
        else setStale(false);
        if (r.mtime) openedMtime.current = r.mtime;
        setText(r);
      } else {
        const blob = await fileApi.loadImageBlob(node.key);
        if (seq !== reqSeq.current) return;
        setImgUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return URL.createObjectURL(blob);
        });
        setStale(false);
      }
    } catch (e) {
      if (seq !== reqSeq.current) return;
      if (e instanceof ImageUnchanged) setStale(false);
      else setErr(e instanceof Error ? e.message : '刷新失败');
    }
  };

  // 父级「↻刷新」三同刷用（O10）
  useEffect(() => {
    if (!refreshRef) return;
    refreshRef.current = () => {
      void refresh();
    };
    return () => {
      refreshRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node?.key, refreshRef]);

  /** 深链行号：打开后滚动并高亮（T1） */
  useEffect(() => {
    if (!lineRange || !preRef.current) return;
    const el = preRef.current.querySelector(
      `[data-ln="${lineRange.start}"]`
    ) as HTMLElement | null;
    if (el) {
      el.scrollIntoView({ block: 'center' });
      el.classList.add('file-ref-hit');
    }
  }, [lineRange, text]);

  if (!node) {
    return <Empty description="从左侧选择一个文件" />;
  }
  if (err) {
    return <Alert type="error" message={err} showIcon />;
  }
  if (node.preview === 'image') {
    return imgUrl ? (
      <div style={{ textAlign: 'center' }}>
        <img src={imgUrl} style={{ maxWidth: '100%' }} alt={node.name} />
      </div>
    ) : (
      <Alert type="info" message="图片加载中…" />
    );
  }
  if (!text) return <Alert type="info" message="文本加载中…" />;

  const cost = refCost(text.content.length);

  /** 选区取行号：按 pre 内的 [data-ln] 行元素反查起止行 */
  const takeSelection = () => {
    const pre = preRef.current;
    if (!pre) return;
    const selRange = window.getSelection();
    if (!selRange || selRange.isCollapsed) return;
    const lines = Array.from(
      pre.querySelectorAll('[data-ln]')
    ) as HTMLElement[];
    const startEl = lines.find((l) => selRange.containsNode(l, true)) as
      | HTMLElement
      | undefined;
    const endEl = [...lines]
      .reverse()
      .find((l) => selRange.containsNode(l, true)) as HTMLElement | undefined;
    if (!startEl || !endEl) return;
    const s = Number(startEl.dataset.ln);
    const e = Number(endEl.dataset.ln);
    if (Number.isNaN(s) || Number.isNaN(e)) return;
    setSel({ start: Math.min(s, e), end: Math.max(s, e) });
  };

  const selText = sel
    ? text.content
        .split('\n')
        .slice(sel.start - 1, sel.end)
        .join('\n')
    : '';

  return (
    <div>
      <div
        style={{
          marginBottom: Spacing.MD,
          color: Colors.TEXT.SECONDARY,
        }}
      >
        {node.name} · {formatBytes(node.size)} · {text.total_lines} 行 ·{' '}
        {text.mtime}
        <Button
          size="small"
          onClick={() => void refresh()}
          style={{ marginLeft: Spacing.MD }}
        >
          ↻刷新
        </Button>
      </div>
      {stale && (
        <Alert
          type="warning"
          message="文件可能已被修改，是否刷新？"
          action={
            <Button size="small" onClick={() => void refresh()}>
              刷新
            </Button>
          }
        />
      )}
      <pre
        ref={preRef}
        onMouseUp={takeSelection}
        style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
      >
        {text.content.split('\n').map((ln, i) => (
          <span key={i} data-ln={i + 1}>
            {ln}
            {'\n'}
          </span>
        ))}
      </pre>
      {sel && selText && (
        <div style={{ marginTop: Spacing.SM }}>
          <Button
            size="small"
            onClick={() => onSendSelection(selText, node, sel)}
          >
            引用选区 L{sel.start}-{sel.end}
          </Button>
        </div>
      )}
      <div style={{ marginTop: Spacing.MD }}>
        <Button
          onClick={() => onSendFile(text.content, node)}
          style={
            cost.level !== 'ok'
              ? { color: Colors.WARNING, borderColor: Colors.WARNING }
              : undefined
          }
        >
          发送到输入框 · 约
          {cost.tokens >= 1024
            ? `${(cost.tokens / 1024).toFixed(1)}K`
            : `${cost.tokens}`}{' '}
          token
        </Button>
        {cost.level === 'warn' && (
          <div
            style={{
              color: Colors.WARNING,
              fontSize: chatTokens.fontSM,
              marginTop: 2,
            }}
          >
            正文本轮发送后会持续占用后续对话的上下文（不会自动清理）
          </div>
        )}
        {cost.level === 'suggest' && (
          <div
            style={{
              color: Colors.INFO,
              fontSize: chatTokens.fontSM,
              marginTop: 2,
            }}
          >
            体量很大，建议只引用行号范围的选区（框选后点「引用选区」）
          </div>
        )}
      </div>
    </div>
  );
};
