/**
 * ChatInput组件 - 独立输入框组件
 *
 * 目的：将输入框逻辑从NewChatContainer中分离，避免每次按键触发整个2328行组件重渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-31
 */

import React, { useState, useCallback, useMemo } from "react";
import { Input, Button, Space, Tag } from "antd";
import {
  SendOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
} from "@ant-design/icons";
import PropTypes from "prop-types";

const { TextArea } = Input;

interface ChatInputProps {
  loading: boolean;
  isReceiving: boolean;
  isPaused: boolean;
  isRetrying: boolean;
  waitTime: number;
  useStream: boolean;
  checkingDanger: boolean;
  onSend: (value: string) => void;
  onInterrupt: () => void;
  onTogglePause: () => void;
}

/**
 * ChatInput - 独立的聊天输入组件
 *
 * 性能优化：
 * - 使用React.memo避免父组件重渲染时不必要的重渲染
 * - 内部维护inputValue状态，避免每次按键都通知父组件
 * - useMemo缓存style对象，避免每次渲染创建新对象
 */
const ChatInput: React.FC<ChatInputProps> = React.memo(({
  loading,
  isReceiving,
  isPaused,
  isRetrying,
  waitTime,
  useStream,
  checkingDanger,
  onSend,
  onInterrupt,
  onTogglePause,
}) => {
  const [inputValue, setInputValue] = useState("");

  const handleSend = useCallback(() => {
    if (!inputValue.trim() || loading) return;
    onSend(inputValue.trim());
    setInputValue("");
  }, [inputValue, loading, onSend]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (!e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  const hasText = useMemo(() => inputValue.trim().length > 0, [inputValue]);

  const buttonStyle = useMemo(() => ({
    backgroundColor: hasText ? "#0066cc" : "#e6e6e6",
    borderColor: hasText ? "#0066cc" : "#d0d0d0",
    color: hasText ? "#fff" : "rgba(0,0,0,0.4)",
    fontWeight: 500,
  }), [hasText]);

  const inputStyle = useMemo(() => ({
    borderColor: "#a8a8a8",
    boxShadow: "none",
  }), []);

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      {/* 等待时间显示 */}
      {loading && waitTime > 0 && (
        <div style={{ marginTop: 8, marginBottom: 4 }}>
          <Tag color={waitTime > 30 ? "error" : waitTime > 15 ? "warning" : "processing"}>
            {isRetrying ? "🔄 正在重试..." : `已等待 ${waitTime} 秒`}
          </Tag>
        </div>
      )}

      {/* 中断和暂停按钮 */}
      {loading && (
        <Space style={{ marginTop: 8, marginBottom: 8 }}>
          <Button
            danger
            icon={<CloseCircleOutlined />}
            onClick={onInterrupt}
          >
            中断
          </Button>
          <Button
            icon={isPaused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
            onClick={onTogglePause}
          >
            {isPaused ? "继续" : "暂停"}
          </Button>
        </Space>
      )}

      <TextArea
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        placeholder={
          useStream
            ? "输入消息... (流式模式可实时查看思考过程)"
            : "输入消息..."
        }
        autoSize={{ minRows: 2, maxRows: 4 }}
        onPressEnter={handleKeyPress}
        disabled={loading || isReceiving}
        style={inputStyle}
      />

      <Button
        type="primary"
        icon={<SendOutlined />}
        onClick={handleSend}
        loading={loading || isReceiving || checkingDanger}
        disabled={!hasText}
        block
        style={buttonStyle}
      >
        {isReceiving
          ? "接收中..."
          : checkingDanger
          ? "安全检查中..."
          : "发送消息"}
      </Button>
    </Space>
  );
});

ChatInput.displayName = "ChatInput";

ChatInput.propTypes = {
  loading: PropTypes.bool.isRequired,
  isReceiving: PropTypes.bool.isRequired,
  isPaused: PropTypes.bool.isRequired,
  isRetrying: PropTypes.bool.isRequired,
  waitTime: PropTypes.number.isRequired,
  useStream: PropTypes.bool.isRequired,
  checkingDanger: PropTypes.bool.isRequired,
  onSend: PropTypes.func.isRequired,
  onInterrupt: PropTypes.func.isRequired,
  onTogglePause: PropTypes.func.isRequired,
};

export default ChatInput;
