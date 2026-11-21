// 编辑历史: 2026-11-21 小欧 - 新建: 生成图像/视频的工具结果在「TOOL结果」标签内的媒体渲染。
//   公网 {url,type} 直接当 src(浏览器可直连厂商 CDN); 本地 {file_path,attachment_id,type} 经
//   attachmentApi.loadRawBlob 带 token 取 blob → objectURL(复用附件预览同一取流口, 不新写请求);
//   type 决定 <img> 或 <video controls>; 未登记附件的兜底行无可取字节, 只能显文字。
//   2026-11-21 小欧 - 媒体下方补一行产物指针纯文字(url / file_path): 看得见图也能复制地址 — 小欧-2026-11-21
/**
 * GeneratedMediaView —— 生成类工具结果的媒体渲染器
 *
 * 只负责"把产物指针变成可见媒体"这一件事:
 *   - 公网 URL: 浏览器直连厂商 CDN, 不需要 token, 不存在本地跨机问题;
 *   - 本地落盘: file_path 在后端机器磁盘上, 浏览器无权访问且裸 src 带不了
 *     Authorization 头(必 401), 故必须走附件 raw 接口取回字节再转 objectURL。
 *
 * 尺寸受内容区约束(maxWidth 100% + maxHeight), 不按原始分辨率撑破浮层;
 * objectURL 在卸载/切换工具行时由 effect 清理函数回收, 不泄漏视频内存。
 */
import React, { useEffect, useState } from 'react';

import { attachmentApi } from '@/services/api/attachment.api';
import { useForegroundSession } from '@/features/chat/services/foregroundSessionStore';
import {
  Colors,
  FontFamily,
  FontSize,
  Radius,
  Spacing,
} from '@/utils/stepStyles';

/** 浮层内媒体最大高度: 面板已限 maxHeight(100vh-58), 视频按原始高度会顶掉头部 */
const MEDIA_MAX_H = 360;
/** 本地产物取流超时: 视频可达数十 MB, 取 60s(短于附件预览的 30s 会误杀大文件) */
const LOAD_TIMEOUT_MS = 60_000;

const REMOTE_RE = /^https?:\/\//i;

const nonEmpty = (v: unknown): v is string =>
  typeof v === 'string' && v.trim() !== '';

/**
 * 媒体结果的形状判据(供 pickResultView 派发):
 *   必须带 type=image|video, 且**有可用产物指针**(公网 url 或本地 file_path)。
 *   只认这两个键 —— 其他工具即便有 url 字段(如 http_get)也不接管,
 *   避免把普通结果误判成媒体而丢文字信息。
 */
export const isMediaResult = (data: Record<string, unknown>): boolean =>
  (data.type === 'image' || data.type === 'video') &&
  ((nonEmpty(data.url) && REMOTE_RE.test(data.url)) ||
    nonEmpty(data.file_path));

const mono: React.CSSProperties = {
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.CODE,
  lineHeight: `${FontSize.CODE + Spacing.XS}px`,
  color: Colors.TEXT.TERTIARY,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
};

/** 产物指针(URL / file_path)纯文字: 可选中复制, 不参与点击跳转 */
const pointerStyle: React.CSSProperties = {
  fontFamily: FontFamily.MONO,
  fontSize: FontSize.SECONDARY,
  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
  color: Colors.TEXT.TERTIARY,
  wordBreak: 'break-all',
  userSelect: 'text',
};

const mediaStyle: React.CSSProperties = {
  display: 'block',
  maxWidth: '100%',
  maxHeight: MEDIA_MAX_H,
  borderRadius: Radius.SM,
};

interface GeneratedMediaViewProps {
  /** 后端 data 原样: {url,type} 或 {file_path,attachment_id,type} */
  data: Record<string, unknown>;
}

export const GeneratedMediaView: React.FC<GeneratedMediaViewProps> = ({
  data,
}) => {
  const isVideo = data.type === 'video';
  const remoteUrl =
    nonEmpty(data.url) && REMOTE_RE.test(data.url) ? data.url : '';
  const filePath = nonEmpty(data.file_path) ? data.file_path : '';
  const attachmentId =
    !remoteUrl && nonEmpty(data.attachment_id) ? data.attachment_id : '';
  const { sessionId } = useForegroundSession();
  const [blobUrl, setBlobUrl] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    setBlobUrl('');
    setError('');
    if (!attachmentId) return;
    if (!sessionId) {
      setError('会话未就绪，无法读取本地产物');
      return;
    }
    let alive = true;
    let objUrl = '';
    const ctrl = new AbortController();
    const timer = window.setTimeout(() => ctrl.abort(), LOAD_TIMEOUT_MS);
    attachmentApi
      .loadRawBlob(attachmentId, sessionId, ctrl.signal)
      .then((b) => {
        if (!alive) return;
        objUrl = URL.createObjectURL(b);
        setBlobUrl(objUrl);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setError(
          e instanceof DOMException && e.name === 'AbortError'
            ? '产物加载超时，请稍后重试'
            : '产物加载失败，文件可能已被移动'
        );
      })
      .finally(() => window.clearTimeout(timer));
    return () => {
      alive = false;
      window.clearTimeout(timer);
      ctrl.abort();
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [attachmentId, sessionId]);

  const label = isVideo ? '生成的视频' : '生成的图片';
  const pointer = remoteUrl || filePath;
  const src = remoteUrl || blobUrl;

  if (!src) {
    if (attachmentId && !error) {
      return <div style={mono}>正在读取产物…</div>;
    }
    // 无可用媒体源: 未登记附件的本地产物(兜底行)、非 http 的 url、或取流失败
    return (
      <div style={mono}>
        {error ||
          (pointer
            ? `产物无法内嵌预览，仅地址：${pointer}`
            : '本次执行无可用产物')}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: Spacing.XS }}>
      {isVideo ? (
        <video src={src} controls preload="metadata" style={mediaStyle} />
      ) : (
        <img src={src} alt={label} loading="lazy" style={mediaStyle} />
      )}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          flexWrap: 'wrap',
          fontSize: FontSize.SECONDARY,
          color: Colors.TEXT.SECONDARY,
        }}
      >
        <span>{label}</span>
        {remoteUrl ? (
          <a
            href={remoteUrl}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: FontSize.SECONDARY, color: Colors.PRIMARY }}
          >
            查看 / 下载
          </a>
        ) : (
          <a
            href={blobUrl}
            download={filePath.split(/[\\/]/).pop()}
            style={{ fontSize: FontSize.SECONDARY, color: Colors.PRIMARY }}
          >
            下载
          </a>
        )}
      </div>
      {/* 2026-11-21 小欧 - 媒体下面附一行产物指针纯文字: 图能看, 地址也要能看见/复制 — 小欧-2026-11-21 */}
      {pointer && <span style={pointerStyle}>{pointer}</span>}
    </div>
  );
};
