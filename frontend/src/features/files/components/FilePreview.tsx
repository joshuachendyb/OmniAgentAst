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
import {
  Alert,
  Button,
  Checkbox,
  Empty,
  Segmented,
  Skeleton,
  Spin,
} from 'antd';
import { CopyOutlined, ReloadOutlined } from '@ant-design/icons';
import type { FileNode, ReadResponse } from '@/services/api/file.api';
import { fileApi, ImageUnchanged } from '@/services/api/file.api';
import { formatBytes } from '@/utils/format';
import { copyTextToClipboard } from '@/utils/clipboard';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { refCost } from '@/utils/refCost';
import { chatTokens } from '@/theme/tokens';
import { Colors, Spacing } from '@/utils/stepStyles';
// 2026-10-21 小杨 - md 双模与代码高亮（北京老陈拍板）：md 复用系统唯一 markdown 渲染入口
//   （聊天/设置页同源 MarkdownSlot）；代码高亮走同目录 highlight 单点（prismjs）
import { MarkdownSlot } from '@/components/markdown/MarkdownSlot';
import { highlightLine, langOf } from './highlight';

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
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);
  /** 长行是否折行（默认关＝横向滚动，保住代码/路径的 token 结构；偏好持久化） */
  const [wrap, setWrap] = useState(
    () => localStorage.getItem('file_preview_wrap') === '1'
  );
  const onWrapChange = (v: boolean) => {
    setWrap(v);
    localStorage.setItem('file_preview_wrap', v ? '1' : '0');
  };
  /** 2026-10-21 小杨 - md 双模（北京老陈拍板）：md 默认**美显**，头部右侧可切「文本」看源码 */
  const [mdBeauty, setMdBeauty] = useState(true);
  // 切文件复位到美显（用户的源码态应只对当前这份文件生效）
  useEffect(() => {
    setMdBeauty(true);
  }, [node?.key]);
  const preRef = useRef<HTMLPreElement | null>(null);
  /** 上一次高亮的行元素（切换定位/刷新时先清掉，防"旧行永久黄底"） */
  const highlightedRef = useRef<HTMLElement | null>(null);
  /** 打开时的 mtime（用于"可能已被修改"判定） */
  const openedMtime = useRef<string | null>(null);
  /** 竞态防护（I7）：只认最后一次请求的结果 */
  const reqSeq = useRef(0);

  const load = async (target: FileNode) => {
    const seq = ++reqSeq.current;
    setErr(null);
    // 2026-10-21 小杨 - 体验审计：切文件必须**重置派生态**
    //   （原实现只换内容：上一张图的像素尺寸会残留到新图加载前；上一份的选区也带着走）
    setSel(null);
    setImgSize(null);
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

  /** 深链行号：打开后滚动 + 高亮 + **聚焦**（T1）
   *  2026-10-21 小杨 - 体验审计：
   *   ① 高亮原来靠 `file-ref-hit` class，而全仓**无该 CSS** → 高亮静默失效（用户定位到了却看不出哪行）
   *      → 改为**内联样式**（不依赖外部 CSS 文件，天然生效）；
   *   ② 定位后**焦点不移动** → 键盘/读屏用户失去位置感 → 目标行可聚焦并 focus。
   */
  useEffect(() => {
    if (!lineRange || !preRef.current) return;
    // 清掉上一次的高亮（DOM 元素会被 React 复用，直接写的 style 不会被回收）
    if (highlightedRef.current) {
      highlightedRef.current.style.background = '';
      highlightedRef.current = null;
    }
    const el = preRef.current.querySelector(
      `[data-ln="${lineRange.start}"]`
    ) as HTMLElement | null;
    if (!el) return;
    el.scrollIntoView({ block: 'center' });
    el.style.background = Colors.WARNING_BG; // 令牌化（原为裸色 #fffbe6）
    el.style.borderRadius = '2px';
    el.setAttribute('tabindex', '-1');
    el.focus({ preventScroll: true });
    highlightedRef.current = el;
    // 2026-10-21 小杨 - 体验审计：高亮**有时效**（4s 后淡出）
    //   常驻高亮会让用户误以为"这行有某种持久状态"，而它只是一次性定位提示。
    const timer = window.setTimeout(() => {
      el.style.background = '';
      if (highlightedRef.current === el) highlightedRef.current = null;
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [lineRange, text]);

  if (!node) {
    return <Empty description="从左侧选择一个文件" />;
  }
  if (err) {
    return (
      <Alert
        type="error"
        showIcon
        message={err}
        action={
          <Button size="small" onClick={() => void load(node)}>
            重试
          </Button>
        }
      />
    );
  }
  if (node.preview === 'image') {
    return imgUrl ? (
      <div style={{ textAlign: 'center' }}>
        <img
          src={imgUrl}
          /* 2026-10-21 小杨 - 体验审计（#5）：高图撑爆预览区 → 限高 + contain */
          style={{
            maxWidth: '100%',
            maxHeight: '70vh',
            objectFit: 'contain',
          }}
          alt={node.name}
          onLoad={(e) =>
            setImgSize({
              w: e.currentTarget.naturalWidth,
              h: e.currentTarget.naturalHeight,
            })
          }
        />
        {/* 2026-10-21 小杨 - 体验审计：补**像素尺寸**（设计稿 2.4.3 要求，原实现缺失） */}
        {imgSize && (
          <div
            style={{
              color: Colors.TEXT.SECONDARY,
              fontSize: chatTokens.fontSM,
              marginTop: 4,
            }}
          >
            {imgSize.w} × {imgSize.h} px · {formatBytes(node.size)}
          </div>
        )}
      </div>
    ) : (
      /* 2026-10-21 小杨 - 体验审计：图片加载用 Spin（Alert 语义是"需要你注意的问题"，不是"等待"） */
      <div style={{ textAlign: 'center', padding: Spacing.LG }}>
        <Spin tip="图片加载中…" />
      </div>
    );
  }
  if (node.preview === 'none') {
    /* 2026-10-21 小杨 - 体验审计（阻断级体验缺陷）：
       原实现把"不可预览"落到 `!text` 分支 → 显示**"文本加载中…"并永远转圈**（死状态，
       用户反复点击、以为是网络问题）。现在给出明确说明 + 可执行的替代动作。 */
    return (
      <Alert
        type="info"
        showIcon
        message={`「${node.name}」暂不支持预览`}
        description="该类型不在可预览范围（当前支持 .txt / .md 与常见图片）。你可以复制路径，或把它设为会话工作目录后再处理。"
        action={
          <Button
            size="small"
            onClick={() => {
              void copyTextToClipboard(node.key).then((r) => {
                if (r.ok) showSuccess('路径已复制');
                else showMessage(ErrorType.COPY_FAILED, '复制失败，请手动复制');
              });
            }}
          >
            复制路径
          </Button>
        }
      />
    );
  }
  if (!text)
    // 2026-10-21 小杨 - 体验审计：文本加载用**骨架屏**（原 Alert「文本加载中…」=
    //   把正常等待渲染成"提醒框"，长文件加载时用户会以为出错了）
    return <Skeleton active paragraph={{ rows: 10 }} title={false} />;

  const cost = refCost(text.content.length);
  // 2026-10-21 小杨 - md 美显判定 + 代码语言判定（未知后缀 = null 落纯文本）
  const isMd = /\.(md|markdown)$/i.test(node.name);
  const lang = langOf(node.name);
  const lines = text.content.split('\n');
  const showMd = isMd && mdBeauty;

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
    <>
      {/* 2026-10-21 小杨 - 冗余层砍除（北京老陈拍板）：根 div 的 flex column 是无谓包裹
          （内容本就是 block 纵排，sticky footer 自带 flex:none），改为 Fragment 砍一层 */}
      <div
        style={{
          marginBottom: Spacing.MD,
          flexShrink: 0, // 2026-10-21 小杨 - flex 链：头部工具行不参与压缩
          color: Colors.TEXT.SECONDARY,
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          flexWrap: 'wrap',
        }}
      >
        {/* 2026-10-21 小杨 - 北京老陈拍板：**按钮在前、行数+时间垫后**（弱信息灰字，不按钮化） */}
        <Button
          size="small"
          onClick={() => onSendFile(text.content, node)}
          title="引用整文件到对话（发送前可再编辑）"
          /* 2026-10-21 小杨 - 北京老陈拍板：引用=主动作，浅蓝底（antd blue-1/blue-3）；警示态保警示色 */
          style={
            cost.level !== 'ok'
              ? { color: Colors.WARNING, borderColor: Colors.WARNING }
              : { background: '#e6f4ff', borderColor: '#91caff' }
          }
        >
          引用{' '}
          {cost.tokens >= 1024
            ? `${(cost.tokens / 1024).toFixed(1)}K`
            : `${cost.tokens}`}{' '}
          tok
        </Button>
        <Button
          size="small"
          icon={<CopyOutlined />}
          onClick={() => {
            void copyTextToClipboard(node.key).then((r) => {
              if (r.ok) showSuccess('路径已复制');
              else showMessage(ErrorType.COPY_FAILED, '复制失败，请手动复制');
            });
          }}
        >
          复制路径
        </Button>
        <span style={{ color: Colors.TEXT.TERTIARY }}>
          {text.total_lines} 行 · {(text.mtime ?? '').replace('T', ' ')}
        </span>
        <span style={{ flex: 1 }} />
        {/* 2026-10-21 小杨 - md 双模切换（北京老陈拍板：头部右侧「文本/美显」，md 默认美显）
            代码/纯文本无此开关 —— 高亮/行号即默认形态 */}
        {isMd && (
          <Segmented
            size="small"
            value={mdBeauty ? 'beauty' : 'text'}
            options={[
              { label: '美显', value: 'beauty' },
              { label: '文本', value: 'text' },
            ]}
            onChange={(v) => setMdBeauty(v === 'beauty')}
          />
        )}
        {/* 折行开关（md 美显模式下隐藏 —— 渲染流自动折行，无横向滚动概念） */}
        {!(isMd && mdBeauty) && (
          <Checkbox
            checked={wrap}
            onChange={(e) => onWrapChange(e.target.checked)}
            style={{ fontSize: chatTokens.fontSM }}
          >
            折行
          </Checkbox>
        )}
        {/* 图标化（原为文本字形「↻刷新」，与全局图标系统不一致） */}
        <Button
          size="small"
          icon={<ReloadOutlined />}
          onClick={() => void refresh()}
        >
          刷新
        </Button>
      </div>
      {stale && (
        <Alert
          type="warning"
          message="文件可能已被修改，是否刷新？"
          style={{ marginBottom: Spacing.SM }}
          action={
            <Button size="small" onClick={() => void refresh()}>
              刷新
            </Button>
          }
        />
      )}
      {showMd ? (
        // 2026-10-21 小杨 - md 美显（北京老陈拍板）：复用系统唯一 markdown 渲染入口
        //   （聊天/设置页同源 MarkdownSlot），J5 文件引用链接 / 表格 / 代码块全吃到；
        //   容器与文本模式同一"纸面"框（同底/同框/同圆角），高度链 flex:1 内滚不变
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowX: 'auto',
            overflowY: 'auto',
            background: Colors.BG.SECONDARY,
            border: `1px solid ${Colors.BORDER.LIGHT}`,
            borderRadius: 4,
            padding: Spacing.MD,
          }}
        >
          <MarkdownSlot text={text.content} markdown />
        </div>
      ) : (
        /* 文本/代码模式：逐行 flex 行（行号列 + 正文），代码走 prism 高亮 */
        <pre
          ref={preRef}
          onMouseUp={takeSelection}
          style={{
            margin: 0,
            fontFamily:
              'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace',
            fontSize: 13,
            lineHeight: 1.6,
            tabSize: 4,
            overflowX: 'auto',
            overflowY: 'auto',
            // 2026-10-21 小杨 - 底部大空白（北京老陈痛骂）：撤拍脑袋 calc(100vh-320px) 限高，
            //   pre 改 flex:1 填满右栏剩余高度（右栏已改 flex column），滚动留在 pre 内部
            flex: 1,
            minHeight: 0,
            background: Colors.BG.SECONDARY,
            border: `1px solid ${Colors.BORDER.LIGHT}`,
            borderRadius: 4,
            padding: Spacing.MD,
          }}
        >
          {lines.map((ln, i) => (
            <div
              key={i}
              data-ln={i + 1}
              style={{
                display: 'flex',
                // 空行也有完整行高（行容器无文字时塌 0；em 与全表 1.6 行高同源）
                minHeight: '1.6em',
              }}
            >
              {/* 2026-10-21 小杨 - 行号列（北京老陈拍板）：数字灰弱右对齐 + 禁复制
                  （选区复制只取正文不含号）；列宽按行数位数自适应（ch 单位），
                  万行/十万行不挤不换行 */}
              <span
                style={{
                  flexShrink: 0,
                  width: `${String(text.total_lines).length + 1}ch`,
                  textAlign: 'right',
                  paddingRight: `${Math.max(2, String(text.total_lines).length / 2)}ch`,
                  color: Colors.TEXT.TERTIARY,
                  userSelect: 'none',
                }}
              >
                {i + 1}
              </span>
              {/* 正文：代码后缀走 prism 高亮（输出已转义），未知后缀原样 */}
              <span
                style={{
                  flex: 1,
                  minWidth: 0,
                  // 折行语义从 pre 容器移到行内正文 span（行号列不受折行影响）
                  whiteSpace: wrap ? 'pre-wrap' : 'pre',
                  wordBreak: wrap ? 'break-word' : 'normal',
                }}
                dangerouslySetInnerHTML={
                  lang
                    ? { __html: ln ? highlightLine(ln, lang) : '' }
                    : undefined
                }
              >
                {lang ? undefined : ln}
              </span>
            </div>
          ))}
        </pre>
      )}
      {/*
        2026-10-21 小杨 - 体验审计（主操作可达性）：
          原实现的主 CTA 在**文件正文之后**——长文件要滚到最底才能引用（本页唯一目的却最难达）。
          现在改为 **sticky 底部操作条**：滚动时始终可见；主键 primary 表达主次。
      */}
      <div
        style={{
          position: 'sticky',
          bottom: 0,
          zIndex: 2,
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          flexWrap: 'wrap',
          marginTop: Spacing.MD,
          padding: `${Spacing.SM}px 0`,
          background: Colors.BG.PRIMARY,
          borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
        }}
      >
        {sel && selText && (
          <Button
            type="primary"
            size="small"
            onClick={() => onSendSelection(selText, node, sel)}
          >
            引用选区 L{sel.start}-{sel.end} 到对话
          </Button>
        )}
        {/* 2026-10-21 小杨 - 北京老陈拍板：引用整文件/复制路径**均已上移顶部**，底部去除 */}
        <span
          style={{
            color: Colors.TEXT.SECONDARY,
            fontSize: chatTokens.fontSM,
            marginLeft: 'auto',
          }}
        >
          {sel && selText ? `已选中第 ${sel.start}-${sel.end} 行` : ''}
        </span>
        {/* 2026-10-21 小杨 - 体验审计（#7）：警示并入 sticky 条（flex 换行第二行）
            原实现警示在条外 → 滚到中部时"按钮可见、警示不可见" */}
        {cost.level === 'warn' && (
          <span
            style={{
              flexBasis: '100%',
              color: Colors.WARNING,
              fontSize: chatTokens.fontSM,
            }}
          >
            正文本轮发送后会持续占用后续对话的上下文（不会自动清理）
          </span>
        )}
        {cost.level === 'suggest' && (
          <span
            style={{
              flexBasis: '100%',
              color: Colors.INFO,
              fontSize: chatTokens.fontSM,
            }}
          >
            体量很大，建议只引用行号范围的选区（框选后点「引用选区」）
          </span>
        )}
      </div>
    </>
  );
};
