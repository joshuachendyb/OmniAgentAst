// 编辑历史: 2026-11-20 小欧 - 新建: 生成图像/视频工具的产物专用卡片。
//   文字参数信息(工具名/浮层参数/状态/耗时/结果摘要)全部走现有 ToolCallLine, 本组件只做差异部分——
//   把产物渲染成缩略图/播放器 + 查看/下载入口; 公网 URL 直接 img/video, 本地落盘路径走 PathLink(不用 markdown ![], 会 401);
//   视频按后缀分流 <video controls>(与 MarkdownText.img 同口径); 不落地大 base64。 — 小欧-2026-11-20
// 编辑历史: 2026-11-20 小欧 - 按 Tool 编写规范整改: 产物只取 tool_result[i].raw_data(=后端 data,
//   {url,type}/{file_path,type}), 取到什么就是什么, 不做兜底; 组件入参统一为产物对象;
//   卡片从展开区移到工具子行默认可见位, 不再藏在 isOpen 里 — 小欧-2026-11-20
// 编辑历史: 2026-11-21 小欧 - 三堂会审整改: 入参由数组改为单个产物对象 —— 父级每渲染一次都新建数组,
//   React.memo 的浅比较恒不相等, 记忆化实际失效; 改具名导出(组件禁默认导出, 与全项目一致) — 小欧-2026-11-21
// 编辑历史: 2026-11-22 小欧 - 本地产物改用附件 raw blob 内嵌预览(与浮层 GeneratedMediaView 同口径):
//   data.attachment_id 经带 token 的 raw 接口取字节转 objectURL 直接显图, 无 id 的兜底保留 PathLink;
//   三堂会审整改: blob 取流/懒加载/revoke 收敛到公用 useAttachmentBlob, 本组件只留渲染 — 小欧-2026-11-22
// 编辑历史: 2026-11-22 小欧 - 消除 sessionId 全局隐式依赖: 后端产物 data 自带 session_id,
//   本组件从 artifact 读, 不再依赖 useForegroundSession, 跨会话回看不取错附件 — 小欧-2026-11-22
/**
 * GenerationResultCard - 生图/生视频产物专用卡片
 *
 * 只负责"产物呈现"这一差异点。产物数据只取 tool_result[i].raw_data（后端 data =
 * 本次执行的真实产物 payload，{url,type} / {file_path,attachment_id,type}），取到什么就是什么，不做兜底。
 * 公网 URL 渲染缩略图/播放器；本地附件有 attachment_id 时经 raw 接口取 blob 内嵌预览，
 * 无 attachment_id 时渲染 PathLink 深链。文字信息不在此重复——由父级 ToolCallLine 统一呈现。
 *
 * @author 小欧
 * @date 2026-11-20
 */
import React from 'react';
import { PathLink } from '@/components/PathLink';
import { useAttachmentBlob } from '@/features/chat/hooks/useAttachmentBlob';
import { Colors, FontSize, Spacing, Radius } from '@/utils/stepStyles';

/** 产物对象: 与后端 data 同形(url 或 file_path+attachment_id+session_id) */
export interface GenerationArtifact {
  url?: string; // 公网产物 URL
  file_path?: string; // 本地落盘路径
  attachment_id?: string; // 本地产物附件 id(走 raw 接口取 blob 内嵌预览)
  session_id?: string; // 产物所属会话(后端给, 取附件的鉴权范围; 不依赖全局前台会话)
  type?: string;
}

interface GenerationResultCardProps {
  artifact?: GenerationArtifact;
}

const isRemote = (path: string): boolean => /^https?:\/\//i.test(path);
const isVideo = (path: string, type?: string): boolean =>
  type === 'video' || /\.(mp4|webm|mov|ogg)(\?|$)/i.test(path);

/** 从产物对象取可见路径与标签: 只认 data 的 url/file_path, 不做任何兜底 */
const resolveItem = (a: GenerationArtifact) => {
  const path = a.url || a.file_path || '';
  const video = isVideo(path, a.type);
  const label = video ? '生成的视频' : '生成的图片';
  return { path, video, label };
};

export const GenerationResultCard = React.memo(function GenerationResultCard({
  artifact,
}: GenerationResultCardProps) {
  const item = artifact ? resolveItem(artifact) : undefined;
  const remote = item ? isRemote(item.path) : false;
  // 本地产物且带 attachment_id → 走 raw 接口取 blob; 无 id 的兜底行只能 PathLink
  const localId =
    item && !remote && artifact?.attachment_id ? artifact.attachment_id : '';
  // 会话取自产物自身(后端权威), 跨会话回看也不会用错 session 取附件
  const ownerSessionId = artifact?.session_id || '';
  // 聊天流长列表: 进入视口才取流, 避免大图 blob 常驻占内存
  const { blobUrl, error, containerRef } = useAttachmentBlob(
    localId,
    ownerSessionId,
    { lazy: true }
  );

  if (!item || !item.path) return null;

  const src = remote ? item.path : blobUrl;
  const canEmbed = remote || !!blobUrl;
  return (
    <div
      ref={containerRef}
      style={{
        marginTop: Spacing.XS,
        padding: Spacing.SM,
        border: `1px solid ${Colors.BORDER.VERTICAL}`,
        borderRadius: Radius.SM,
        maxWidth: 360,
      }}
    >
      {canEmbed ? (
        item.video ? (
          <video
            src={src}
            controls
            preload="metadata"
            style={{ width: '100%', borderRadius: Radius.SM }}
          />
        ) : (
          <img
            src={src}
            alt={item.label}
            loading="lazy"
            style={{
              display: 'block',
              width: '100%',
              borderRadius: Radius.SM,
            }}
          />
        )
      ) : (
        <PathLink rawPath={item.path} variant="inline" mono tooltip fileHint />
      )}
      <div
        style={{
          marginTop: Spacing.XS,
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.SM,
          flexWrap: 'wrap',
        }}
      >
        <span
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
          }}
        >
          {item.label}
        </span>
        {remote && (
          <a
            href={item.path}
            target="_blank"
            rel="noreferrer"
            style={{ fontSize: FontSize.SECONDARY, color: Colors.PRIMARY }}
          >
            查看 / 下载
          </a>
        )}
        {!remote && blobUrl && (
          <a
            href={blobUrl}
            download={item.path.split(/[\\/]/).pop()}
            style={{ fontSize: FontSize.SECONDARY, color: Colors.PRIMARY }}
          >
            下载
          </a>
        )}
        {error && (
          <span style={{ fontSize: FontSize.SECONDARY, color: Colors.ERROR }}>
            {error}
          </span>
        )}
      </div>
    </div>
  );
});
