/**
 * UserMessageBubble组件 - 用户消息气泡
 * 
 * 功能：
 * 1. 用户消息气泡样式（蓝色渐变）
 * 2. 角色名称 + 时间戳
 * 3. 消息内容渲染
 * 4. 复制/导出功能
 * 5. 发送失败图标（条件显示）
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-23
 */

/* eslint-disable react/prop-types */
import React, { memo, useState } from "react";
import { Tooltip, Button, message as antMessage } from "antd";
import {
  CopyOutlined,
  CheckOutlined,
  DownloadOutlined,
} from "@ant-design/icons";
import MessageContent from "../MessageContent";
import RoleNameDisplay from "./RoleNameDisplay";
import { formatTime, formatRelativeTime } from "../../../utils/timeFormatters";
import { exportMessage } from "../../../utils/messageExporter";
import type { MessageItemProps } from "../../../hooks/useMessageItemProps";

interface UserMessageBubbleProps {
  message: MessageItemProps["message"];
  sessionId?: string | null;
  sessionTitle?: string | null;
}

/**
 * 用户消息气泡样式
 */
const getUserBubbleStyle = (sendStatus?: string): React.CSSProperties => {
  const baseStyle: React.CSSProperties = {
    maxWidth: "100%",
    minWidth: "60px",
    width: "auto",
    paddingTop: 8,
    paddingBottom: 8,
    paddingLeft: 10,
    paddingRight: 30,
    borderRadius: "16px",
    position: "relative",
    transition: "all 0.3s ease",
    whiteSpace: "pre-wrap" as const,
    wordBreak: "normal" as const,
    overflowWrap: "break-word" as const,
  };

  // 【小沈修复2026-04-23】P0-1: 发送失败时显示红色边框
  if (sendStatus === "failed") {
    return {
      ...baseStyle,
      background: "linear-gradient(135deg, #fff1f0 0%, #ffccc7 100%)",
      color: "#cf1322",
      boxShadow: "0 4px 12px rgba(255, 77, 79, 0.15)",
      border: "1px solid #ffa39e",
    };
  }

  // 正常用户消息样式
  return {
    ...baseStyle,
    background: "linear-gradient(135deg, #f0f5ff 0%, #adc6ff 100%)",
    color: "#262626",
    boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
    border: "1px solid #d6e4ff",
  };
};

/**
 * UserMessageBubble组件
 */
const UserMessageBubble: React.FC<UserMessageBubbleProps> = memo(({
  message,
  sessionId,
  sessionTitle,
}) => {
  const [copied, setCopied] = useState(false);

  /**
   * 复制消息内容
   */
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      antMessage.success("已复制到剪贴板");
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      antMessage.error("复制失败");
    }
  };

  /**
   * 导出消息内容
   */
  const handleExport = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await exportMessage(message, { sessionId, sessionTitle });
    } catch (err) {
      antMessage.error("导出失败");
    }
  };

  const bubbleStyle = getUserBubbleStyle(message.sendStatus);

  return (
    <>
      {/* 角色名称和时间戳区域 */}
      <div
        style={{
          marginBottom: 4,
          fontSize: 12,
          color: "#1890ff",
          fontWeight: 500,
          opacity: 0.85,
          whiteSpace: "nowrap",
          display: "flex",
          alignItems: "center",
          gap: 0,
          flexDirection: "row-reverse",
        }}
      >
        <span style={{ whiteSpace: "nowrap" }}>
          <RoleNameDisplay
            role={message.role}
            sendStatus={message.sendStatus}
          />
        </span>
        <span
          style={{
            fontSize: 11,
            color: "#999999",
            whiteSpace: "nowrap",
          }}
        >
          <Tooltip title={formatTime(message.timestamp)}>
            <span>{formatRelativeTime(message.timestamp)}</span>
          </Tooltip>
        </span>
      </div>

      {/* 消息气泡 */}
      <div style={{ ...bubbleStyle, position: "relative" }}>
        {/* 复制按钮 */}
        <Tooltip title={copied ? "已复制" : "复制"}>
          <Button
            className="copy-button"
            type="text"
            size="small"
            icon={
              copied ? (
                <CheckOutlined style={{ color: "#52c41a" }} />
              ) : (
                <CopyOutlined style={{ color: "rgba(255,255,255,0.9)" }} />
              )
            }
            onClick={handleCopy}
            style={{
              position: "absolute",
              top: 4,
              right: 6,
              opacity: 0,
              transition: "opacity 0.2s ease",
              background: "transparent",
              border: "none",
              boxShadow: "none",
              padding: "0 4px",
              minHeight: "auto",
              height: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          />
        </Tooltip>

        {/* 导出按钮 */}
        <Tooltip title="导出">
          <Button
            className="copy-button"
            type="text"
            size="small"
            icon={<DownloadOutlined style={{ color: "rgba(255,255,255,0.9)" }} />}
            onClick={handleExport}
            style={{
              position: "absolute",
              top: 4,
              right: 30,
              opacity: 0,
              transition: "opacity 0.2s ease",
              background: "transparent",
              border: "none",
              boxShadow: "none",
              padding: "0 4px",
              minHeight: "auto",
              height: "20px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          />
        </Tooltip>

        {/* 消息内容 */}
        <MessageContent message={message} isUser={true} isSystem={false} />
      </div>
    </>
  );
});

UserMessageBubble.displayName = "UserMessageBubble";

export default UserMessageBubble;