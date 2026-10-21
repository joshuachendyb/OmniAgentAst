// 编辑历史: 2026-10-21 小杨 - 新建预览区：文本（行号/高亮/折行/选区引用）、图片（objectURL 自适应 + 像素尺寸）、
//   体量分级提示（token 数）、刷新单请求化（正文与 mtime 同源同拍）— 小杨-2026-10-21
//   2026-10-21 小杨 - 修复：刷新改为"重载+提示"（旧过期横幅与自动重载自相矛盾）、
//     图片补工具栏与本轮字节数、空文件 0 行、行号列横向滚动时粘左、引用体量统一为字节 — 小杨-2026-10-21
//   2026-10-21 小欧 - 「暂不支持预览」文案去掉"设为会话工作目录"：该入口已下线（工具条与右键
//     菜单都已摘除），继续引导用户去一个不存在的功能 = 制造死路 — 小欧-2026-10-21
//   2026-10-21 小欧 - 行号去"幽灵行"：split('\n') 末段空串不算一行（编辑器口径），
//     否则行号多 1（指到不存在的空行）且与后端 total_lines 不一致 — 小欧-2026-10-21
// 2026-10-22 小杨 - 深链行号按区间整段高亮（原只高亮首行），行号越界在工具条如实提示，
//     不再静默不定位 — 小杨-2026-10-22
/**
 * FilePreview —— 选中文件的预览区（只读）
 *
 * 能力：文本（保留换行缩进、可滚动、代码高亮）/ 图片（objectURL 自适应）/
 *   选区引用 / 过期提示 / 体量提示（token 数 + 分级警示）。
 *
 * 单请求刷新：`/files/read` 一次带回正文与 mtime（同源同拍），
 *   刷新时比对新旧 mtime 即可判文件是否已变，**不再绕道再拉一次 tree**。
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
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
import {
  showMessage,
  showSuccess,
  ErrorType,
  extractErrorMessage,
} from '@/services/error/handler';
import { refCost } from '@/utils/refCost';
import { chatTokens } from '@/theme/tokens';
import { Colors, Spacing } from '@/utils/stepStyles';
// 2026-10-21 小杨 - md 双模与代码高亮：md 复用系统唯一 markdown 渲染入口
//   （聊天/设置页同源 MarkdownSlot）；代码高亮走同目录 highlight 单点（prismjs）
import { MarkdownSlot } from '@/components/markdown/MarkdownSlot';
import { highlightLine, langOf } from './highlight';

/** 预览工具栏（文本/图片共用，避免两套头部样式漂移） */
const TOOLBAR_STYLE: React.CSSProperties = {
  marginBottom: Spacing.MD,
  flexShrink: 0,
  color: Colors.TEXT.SECONDARY,
  display: 'flex',
  alignItems: 'center',
  gap: Spacing.SM,
  flexWrap: 'wrap',
};

export interface FilePreviewProps {
  node: FileNode | null;
  /** 深链行号（&line=start-end），打开时滚动并高亮 */
  lineRange?: { start: number; end: number } | null;
  /** 发送到输入框 —— size 为字节数（与 recent/tree 同口径） */
  onSendFile: (content: string, node: FileNode, size: number) => void;
  /** 引用选区 */
  onSendSelection: (
    content: string,
    node: FileNode,
    lineRange: { start: number; end: number },
    size: number
  ) => void;
  /** 暴露给父级的刷新句柄（父级工具条刷新复用） */
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
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<{ start: number; end: number } | null>(null);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);
  /** 2026-10-21 小杨 - 修复：图片体量取本轮 blob 的字节数（原用树节点 size，刷新后不更新） */
  const [imgBytes, setImgBytes] = useState<number | null>(null);
  /** 长行是否折行（默认关＝横向滚动，保住代码/路径的 token 结构；偏好持久化） */
  const [wrap, setWrap] = useState(
    () => localStorage.getItem('file_preview_wrap') === '1'
  );
  const onWrapChange = (v: boolean) => {
    setWrap(v);
    localStorage.setItem('file_preview_wrap', v ? '1' : '0');
  };
  /** 2026-10-21 小杨 - md 双模：md 默认**美显**，头部右侧可切「文本」看源码 */
  const [mdBeauty, setMdBeauty] = useState(true);
  // 2026-10-21 小杨 - 修复（md 深链定位断裂）：深链 @md:12 带行号
  //   打开必须落在**文本模式**（美显走 MarkdownSlot 无 preRef，行高亮静默失效）；
  //   无行号打开才复位美显。lineRange 每次打开动作都是新引用 → 重复深链同口径
  //   重新落位；用户手动切 Segmented 不动 lineRange，切换不受打扰。
  useEffect(() => {
    setMdBeauty(!lineRange);
  }, [node?.key, lineRange]);

  // 2026-10-21 小欧 - 换文件重置渲染行数；深链指定行若在可视行数之外 → 一次展开到该行
  useEffect(() => {
    setVisibleLines((v) =>
      lineRange && lineRange.end > v ? lineRange.end : 2000
    );
  }, [node?.key, lineRange]);
  // 2026-10-21 小杨 - 修复（逐行高亮无缓存）：原实现 hljs.highlight
  //   在 render 内对每行调，任何 state 变化（选区/折行/过期提示）都全文件重算，
  //   万行文件秒级卡。收敛到 useMemo：行数组与高亮 HTML 只随 (content, lang) 重算，
  //   render 只查表。
  const isMd = !!node && /\.(md|markdown)$/i.test(node.name);
  const lang = node ? langOf(node.name) : null;
  // 2026-10-21 小杨 - 修复：空文件 '' 曾 split 出 [''] → 头部写 0 行却渲染出 1 行行号
  const textContent = text?.content ?? '';
  const lines = useMemo(
    // 末尾换行不产生新行（编辑器口径）：split 出来的末段空串是"幽灵行"，
    // 留着会让行号多 1（行号指到不存在的空行），且与后端 total_lines 口径不一致。
    () => {
      if (textContent === '') return [];
      const arr = textContent.split('\n');
      if (arr.length > 1 && arr[arr.length - 1] === '') arr.pop();
      return arr;
    },
    [textContent]
  );
  const htmlLines = useMemo(
    () => (lang ? lines.map((l) => (l ? highlightLine(l, lang) : '')) : null),
    [lines, lang]
  );
  const preRef = useRef<HTMLPreElement | null>(null);
  /** 上一次高亮的行元素（切换定位/刷新时先清掉，防"旧行永久黄底"） */
  const highlightedRef = useRef<HTMLElement[]>([]);
  /** 2026-10-21 小杨 - 深链行号越界时如实告知（原来静默不定位，用户以为"点了没反应"）— 小杨-2026-10-21 */
  const [lineMiss, setLineMiss] = useState(false);
  /** 打开时的 mtime（判文件是否已被改写） */
  const openedMtime = useRef<string | null>(null);
  /** 竞态防护：只认最后一次请求的结果 */
  const reqSeq = useRef(0);
  /**
   * 2026-10-21 小欧 - 大文件渲染上限：2MB 文本 ≈ 2 万行，全量渲染会卡死页面。
   * 故首屏只渲染前 2000 行，点「显示更多」再追加（行号与 data-ln 仍是真实行号）。
   */
  const [visibleLines, setVisibleLines] = useState(2000);
  const shownLines = useMemo(
    () => lines.slice(0, visibleLines),
    [lines, visibleLines]
  );
  /**
   * 2026-10-21 小欧 - 大文件"加载后续内容"：默认只读到 2MB（后端截断），
   * 后面还有内容 → 按行区间向服务端要下一段（后端流式读，内存恒定），追加拼接。
   * 与「显示更多」（本地渲染上限 2000 行）是两件事，缺一不可。
   */
  const [moreLoading, setMoreLoading] = useState(false);
  const loadedLines = text?.returned_lines ?? 0;
  /** 美显模式的渲染文本：只取已渲染窗口内的行（与文本模式同一上限，避免 markdown 渲染 2MB 卡死） */
  const beautyText = useMemo(
    () => lines.slice(0, visibleLines).join('\n'),
    [lines, visibleLines]
  );
  const beautyTruncated = lines.length > visibleLines;
  const hasMoreInFile =
    !!text &&
    (text.truncated === true || loadedLines < (text.total_lines ?? 0));
  const loadMore = async () => {
    if (!node || !text) return;
    setMoreLoading(true);
    try {
      const next = await fileApi.readFile(node.key, {
        offset: loadedLines + 1,
        limit: 2000,
      });
      if (!next.content) {
        // 2026-10-22 小杨 - 到文件末尾时**如实告知**：此前静默 return，
        //   用户点了「加载后续内容」却毫无反馈（与"点了没反应"同一种病）— 小杨-2026-10-22
        showMessage(ErrorType.INFO, '已到文件末尾，没有更多内容');
        return;
      }
      setText((prev) => {
        if (!prev) return prev;
        // 追加前保证前段以换行结尾：上段可能被字节上限截在行中间 → 直接粘 '\n' 会把两行连成一行（行号错位）
        const head = prev.content.endsWith('\n')
          ? prev.content
          : prev.content + '\n';
        return {
          ...prev,
          content: head + next.content,
          returned_lines:
            (prev.returned_lines ?? 0) + (next.returned_lines ?? 0),
        };
      });
      // 渲染窗口同步推进：否则新内容进了已加载集合但视口仍停在前 2000 行 → 点了像没反应
      setVisibleLines((v) => v + (next.returned_lines ?? 0));
    } catch (e) {
      showMessage(
        ErrorType.FILE_READ,
        extractErrorMessage(e) ?? '加载后续内容失败'
      );
    } finally {
      setMoreLoading(false);
    }
  };

  const load = async (target: FileNode) => {
    const seq = ++reqSeq.current;
    setErr(null);
    // 2026-10-21 小杨 - 切文件必须**重置派生态**
    //   （原实现只换内容：上一张图的像素尺寸会残留到新图加载前；上一份的选区也带着走）
    setSel(null);
    setImgSize(null);
    setImgBytes(null);
    try {
      if (target.preview === 'text') {
        const r = await fileApi.readFile(target.key);
        if (seq !== reqSeq.current) return; // 已被更新的请求取代
        setText(r);
        releaseImage(); // 2026-10-21 小杨 - 修复：切走时**必须 revoke**（原 setImgUrl(null) 直接丢 URL 字符串 → 泄漏）
        openedMtime.current = r.mtime;
      } else if (target.preview === 'image') {
        const blob = await fileApi.loadImageBlob(target.key);
        if (seq !== reqSeq.current) return;
        setImgUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return URL.createObjectURL(blob);
        });
        setImgBytes(blob.size);
        setText(null);
      } else {
        setText(null);
        releaseImage();
      }
    } catch (e) {
      if (seq !== reqSeq.current) return;
      if (e instanceof ImageUnchanged) {
        // 图片未变化（304）不算失败，保留旧图
      } else {
        // 2026-10-21 小欧 - 显示后端业务文案（原来只有 axios 英文 "Request failed with status code 413"）
        setErr(extractErrorMessage(e) ?? '加载失败');
      }
    }
  };

  /**
   * 释放当前图片的 objectURL（2026-10-21 小杨 - 修复：原实现 setImgUrl(null) 只是丢掉 URL 字符串，
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
      setErr(null);
      setSel(null);
      return;
    }
    void load(node);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [node?.key]);

  /** refresh 单请求化 —— 一次 /files/read 同时拿到"新鲜度判定 + 内容重载"
   *  2026-10-21 小杨 - 修复：refresh 也要走 reqSeq 守卫
   *   （原实现 refresh 无守卫 → 刷新 A 的请求晚于切到 B 的请求返回 → 头部显示 B、正文却是 A） */
  const refresh = async () => {
    if (!node) return;
    const seq = ++reqSeq.current;
    try {
      if (node.preview === 'text') {
        const r = await fileApi.readFile(node.key);
        if (seq !== reqSeq.current) return; // 已被更新的请求取代
        // 2026-10-21 小杨 - 修复：内容既然已重载，就不再挂"可能已被修改"横幅
        //   （旧实现一边换正文一边让横幅永久停留，自相矛盾）。变化用一次性提示告知。
        const changed = !!r.mtime && r.mtime !== openedMtime.current;
        if (r.mtime) openedMtime.current = r.mtime;
        setText(r);
        setSel(null); // 行号可能已变，旧选区作废
        if (changed) showSuccess('文件已更新，已重新加载');
      } else if (node.preview === 'image') {
        const blob = await fileApi.loadImageBlob(node.key);
        if (seq !== reqSeq.current) return;
        setImgUrl((old) => {
          if (old) URL.revokeObjectURL(old);
          return URL.createObjectURL(blob);
        });
        setImgBytes(blob.size);
      }
    } catch (e) {
      if (seq !== reqSeq.current) return;
      if (!(e instanceof ImageUnchanged)) {
        setErr(extractErrorMessage(e) ?? '刷新失败');
      }
    }
  };

  // 父级工具条刷新复用
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

  /** 深链行号：打开后滚动 + 高亮 + **聚焦**
   *  2026-10-21 小杨 - 修复：
   *   ① 高亮原来靠 `file-ref-hit` class，而全仓**无该 CSS** → 高亮静默失效（用户定位到了却看不出哪行）
   *      → 改为**内联样式**（不依赖外部 CSS 文件，天然生效）；
   *   ② 定位后**焦点不移动** → 键盘/读屏用户失去位置感 → 目标行可聚焦并 focus。
   */
  useEffect(() => {
    if (!lineRange || !preRef.current) return;
    // 清掉上一次的高亮（DOM 元素会被 React 复用，直接写的 style 不会被回收）
    highlightedRef.current.forEach((node) => {
      node.style.background = '';
    });
    highlightedRef.current = [];

    const start = Math.max(1, Math.min(lineRange.start, lineRange.end));
    const end = Math.max(lineRange.start, lineRange.end);
    const nodes = Array.from(
      preRef.current.querySelectorAll<HTMLElement>('[data-ln]')
    ).filter((node) => {
      const n = Number(node.dataset.ln);
      return Number.isFinite(n) && n >= start && n <= end;
    });
    // 行号越界 / 文件为空：保持原文，不伪造高亮
    if (!nodes.length) {
      setLineMiss(true);
      return;
    }
    setLineMiss(false);

    nodes[0].scrollIntoView({ block: 'center' });
    nodes.forEach((node) => {
      node.style.background = Colors.WARNING_BG; // 令牌化（原为裸色 #fffbe6）
      node.style.borderRadius = '2px';
      node.setAttribute('tabindex', '-1');
    });
    nodes[0].focus({ preventScroll: true });
    highlightedRef.current = nodes;
    // 2026-10-21 小杨 - 高亮**有时效**（4s 后淡出）
    //   常驻高亮会让用户误以为"这行有某种持久状态"，而它只是一次性定位提示。
    const timer = window.setTimeout(() => {
      nodes.forEach((node) => {
        node.style.background = '';
      });
      if (highlightedRef.current === nodes) highlightedRef.current = [];
    }, 4000);
    return () => window.clearTimeout(timer);
  }, [lineRange, text]);

  /** 复制相对路径（三处复用：文本头 / 图片头 / 不可预览提示） */
  const copyPath = (target: FileNode) => {
    void copyTextToClipboard(target.key).then((r) => {
      if (r.ok) showSuccess('路径已复制');
      else showMessage(ErrorType.COPY_FAILED, '复制失败，请手动复制');
    });
  };

  if (!node) {
    return <Empty description="从左侧选择一个文件" />;
  }
  if (err) {
    return (
      <Alert
        type="error"
        showIcon
        message={`「${node.name}」${err}`}
        action={
          <Button size="small" onClick={() => void load(node)}>
            重试
          </Button>
        }
      />
    );
  }
  if (node.preview === 'image') {
    /* 2026-10-21 小杨 - 修复：图片原先没有工具栏（复制路径/刷新只能在文本下用），
       且体量用树节点旧 size；现与文本共用同一头部与刷新链路 */
    return (
      <>
        <div style={TOOLBAR_STYLE}>
          <Button
            size="small"
            icon={<CopyOutlined />}
            onClick={() => copyPath(node)}
          >
            复制路径
          </Button>
          <span style={{ color: Colors.TEXT.TERTIARY }}>
            {/* 图片拿不到"本次读取"的 mtime（blob 无该字段），不展示树里的旧值以免误导 */}
            {imgBytes != null ? formatBytes(imgBytes) : formatBytes(node.size)}
            {imgSize ? ` · ${imgSize.w} × ${imgSize.h} px` : ''}
          </span>
          <span style={{ flex: 1 }} />
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={() => void refresh()}
          >
            刷新
          </Button>
        </div>
        {imgUrl ? (
          <div style={{ textAlign: 'center' }}>
            <img
              src={imgUrl}
              /* 2026-10-21 小杨 - 高图撑爆预览区 → 限高 + contain */
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
          </div>
        ) : (
          /* 2026-10-21 小杨 - 图片加载用 Spin（Alert 语义是"需要你注意的问题"，不是"等待"） */
          <div style={{ textAlign: 'center', padding: Spacing.LG }}>
            {/* antd Spin 的 tip 仅在 nest/fullscreen 模式生效，裸用时警告且不显示文案；直接渲染说明 */}
            <Spin />
            <div style={{ marginTop: Spacing.SM }}>图片加载中…</div>
          </div>
        )}
      </>
    );
  }
  if (node.preview === 'none') {
    /* 2026-10-21 小杨 - 修复阻断级缺陷：
       原实现把"不可预览"落到 `!text` 分支 → 显示**"文本加载中…"并永远转圈**（死状态，
       用户反复点击、以为是网络问题）。现在给出明确说明 + 可执行的替代动作。
       2026-10-21 小欧 - 文案去掉"设为会话工作目录"：该入口已下线（工具条与右键菜单都已摘除），
       继续引导用户去一个不存在的功能 = 制造死路。替代动作只留"复制路径"。 */
    return (
      <Alert
        type="info"
        showIcon
        message={`「${node.name}」暂不支持预览`}
        description="该文件不是可预览的文本或图片（可能是二进制或无法读取）。你可以复制路径，或引用到对话中再处理。"
        action={
          <Button size="small" onClick={() => copyPath(node)}>
            复制路径
          </Button>
        }
      />
    );
  }
  if (!text)
    // 2026-10-21 小杨 - 文本加载用**骨架屏**（原 Alert「文本加载中…」=
    //   把正常等待渲染成"提醒框"，长文件加载时用户会以为出错了）
    return <Skeleton active paragraph={{ rows: 10 }} title={false} />;

  const cost = refCost(text.content.length);
  // 2026-10-21 小杨 - isMd/lang/lines 已上移到 hooks 区（useMemo 依赖），此处只定形态开关
  const showMd = isMd && mdBeauty;

  /** 选区取行号：按 pre 内的 [data-ln] 行元素反查起止行 */
  const takeSelection = () => {
    const pre = preRef.current;
    if (!pre) return;
    const selRange = window.getSelection();
    if (!selRange || selRange.isCollapsed) return;
    const lineEls = Array.from(
      pre.querySelectorAll('[data-ln]')
    ) as HTMLElement[];
    const startEl = lineEls.find((l) => selRange.containsNode(l, true)) as
      | HTMLElement
      | undefined;
    const endEl = [...lineEls]
      .reverse()
      .find((l) => selRange.containsNode(l, true)) as HTMLElement | undefined;
    if (!startEl || !endEl) return;
    const s = Number(startEl.dataset.ln);
    const e = Number(endEl.dataset.ln);
    if (Number.isNaN(s) || Number.isNaN(e)) return;
    setSel({ start: Math.min(s, e), end: Math.max(s, e) });
  };

  const selText = sel
    ? // 2026-10-21 小杨 - 修复（\r 残留）：read 侧 newline="" 保真让纸面
      //   行尾带 \r；**选区引用**只承载行内容语义，统一归一为 \n（整文件引用仍保真）
      lines
        .slice(sel.start - 1, sel.end)
        .join('\n')
        .replace(/\r\n/g, '\n')
    : '';

  return (
    <>
      {/* 2026-10-21 小杨 - 冗余层砍除：根 div 的 flex column 是无谓包裹
          （内容本就是 block 纵排，sticky footer 自带 flex:none），改为 Fragment 砍一层 */}
      <div style={TOOLBAR_STYLE}>
        {/* 2026-10-21 小杨 - **按钮在前、行数+时间垫后**（弱信息灰字，不按钮化） */}
        <Button
          size="small"
          onClick={() => onSendFile(text.content, node, text.size)}
          title="引用整文件到对话（发送前可再编辑）"
          /* 2026-10-21 小杨 - 引用=主动作，浅蓝底（antd blue-1/blue-3）；警示态保警示色 */
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
          onClick={() => copyPath(node)}
        >
          复制路径
        </Button>
        <span style={{ color: Colors.TEXT.TERTIARY }}>
          {text.total_lines} 行 · {text.mtime}
        </span>
        {/* 2026-10-21 小杨 - 行号越界如实告知，不静默吞掉深链定位请求 — 小杨-2026-10-21 */}
        {lineMiss && lineRange && (
          <span style={{ color: Colors.WARNING }}>
            未找到第 {lineRange.start}
            {lineRange.end !== lineRange.start ? `-${lineRange.end}` : ''} 行
          </span>
        )}
        {/* 2026-10-21 小欧 - 超大文件被截断时如实告知（后端不报错，改截断读取） */}
        {text.truncated && (
          <span style={{ color: Colors.WARNING }}>
            文件共 {formatBytes(text.total_size ?? text.size)}，已加载前{' '}
            {formatBytes(text.loaded_size ?? text.size)}
          </span>
        )}
        <span style={{ flex: 1 }} />
        {/* 2026-10-21 小杨 - md 双模切换（头部右侧「文本/美显」，md 默认美显）
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
      {showMd ? (
        // 2026-10-21 小杨 - md 美显：复用系统唯一 markdown 渲染入口
        //   （聊天/设置页同源 MarkdownSlot），文件引用链接 / 表格 / 代码块全吃到；
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
          {/* 美显模式同样限行：markdown 渲染 2MB 全文会卡死页面（文本模式已限 2000 行） */}
          <MarkdownSlot text={beautyText} markdown />
          {beautyTruncated && (
            <div style={{ color: Colors.WARNING, fontSize: chatTokens.fontSM }}>
              美显模式只渲染前 {visibleLines}{' '}
              行，切换「文本」模式可查看全部已加载内容。
            </div>
          )}
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
            // 2026-10-21 小杨 - 底部大空白修复：撤拍脑袋 calc(100vh-320px) 限高，
            //   pre 改 flex:1 填满右栏剩余高度（右栏已改 flex column），滚动留在 pre 内部
            flex: 1,
            minHeight: 0,
            background: Colors.BG.SECONDARY,
            border: `1px solid ${Colors.BORDER.LIGHT}`,
            borderRadius: 4,
            padding: Spacing.MD,
          }}
        >
          {shownLines.map((ln, i) => (
            <div
              key={i}
              data-ln={i + 1}
              style={{
                display: 'flex',
                // 空行也有完整行高（行容器无文字时塌 0；em 与全表 1.6 行高同源）
                minHeight: '1.6em',
              }}
            >
              {/* 2026-10-21 小杨 - 行号列：数字灰弱右对齐 + 禁复制
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
                  // 2026-10-21 小杨 - 修复：横向滚动时行号会跟着正文滑走，
                  //   图钉在 pre 左侧（pre 是最近滚动容器），背景与纸面同色避免透字
                  position: 'sticky',
                  left: 0,
                  zIndex: 1,
                  background: Colors.BG.SECONDARY,
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
                  lang ? { __html: htmlLines?.[i] ?? '' } : undefined
                }
              >
                {lang ? undefined : ln}
              </span>
            </div>
          ))}
          {/* 2026-10-21 小欧 - 还有未渲染的行 → 显式按钮继续加载（不做无限滚动，静默截断会骗人） */}
          {lines.length > shownLines.length && (
            <Button
              size="small"
              onClick={() =>
                setVisibleLines((v) => Math.min(v + 2000, lines.length))
              }
              style={{ marginTop: Spacing.SM }}
            >
              显示更多（还有 {lines.length - shownLines.length} 行）
            </Button>
          )}
          {/* 2026-10-21 小欧 - 内容没读完（后端 2MB 截断）→ 向服务端要下一段 */}
          {hasMoreInFile && (
            <Button
              size="small"
              loading={moreLoading}
              onClick={() => void loadMore()}
              style={{ marginTop: Spacing.SM }}
            >
              加载后续内容（已读 {loadedLines} 行）
            </Button>
          )}
        </pre>
      )}
      {/*
        2026-10-21 小杨 - 主操作可达性：
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
            onClick={() =>
              onSendSelection(
                selText,
                node,
                sel,
                new TextEncoder().encode(selText).length
              )
            }
          >
            引用选区 L{sel.start}-{sel.end} 到对话
          </Button>
        )}
        {/* 2026-10-21 小杨 - 引用整文件/复制路径**均已上移顶部**，底部去除 */}
        <span
          style={{
            color: Colors.TEXT.SECONDARY,
            fontSize: chatTokens.fontSM,
            marginLeft: 'auto',
          }}
        >
          {sel && selText ? `已选中第 ${sel.start}-${sel.end} 行` : ''}
        </span>
        {/* 2026-10-21 小杨 - 警示并入 sticky 条（flex 换行第二行）
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
