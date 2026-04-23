/**
 * MessageContent组件 - 消息内容渲染
 * 
 * 功能：
 * 1. 渲染chunk内容（AI流式输出片段）
 * 2. Content回退逻辑（无chunk时显示message.content）
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-21
 */

import React from "react";
import type { ExecutionStep } from "../../../utils/sse";

interface MessageContentProps {
  message: {
    content: string;
    isStreaming?: boolean;
    is_reasoning?: boolean;
    executionSteps?: ExecutionStep[];
  };
  isUser?: boolean;
  isSystem?: boolean;
}

/**
 * Chunk渲染组件
 */
const ChunkRenderer: React.FC<{ chunks: ExecutionStep[] }> = ({ chunks }) => {
  return (
    <>
      {chunks.map((chunk, index) => {
        const is_reasoning = !!chunk.is_reasoning;
        let content = (chunk.content || '').replace(/<\/?longcat_think>/g, '');

        if (index > 0) {
          const prevChunk = chunks[index - 1];
          const prevIsReasoning = !!prevChunk.is_reasoning;
          const prevContent = prevChunk.content || '';

          if (is_reasoning !== prevIsReasoning) {
            if (!prevContent.endsWith('\n')) {
              content = '\n' + content;
            }
          }
        }

        return (
          <span
            key={`chunk-${index}`}
            style={{
              color: is_reasoning ? '#888' : '#000',
              fontStyle: is_reasoning ? 'italic' : 'normal',
              fontSize: is_reasoning ? '0.95em' : '1em',
            }}
          >
            {content}
          </span>
        );
      })}
    </>
  );
};

/**
 * Content回退渲染
 * 当没有chunk时，显示message.content
 */
const ContentFallback: React.FC<{
  message: MessageContentProps['message'];
  _hasChunk: boolean;
}> = ({ message }) => {
  const executionSteps = message.executionSteps || [];

  let hasAction = 0;
  for (const step of executionSteps) {
    if (step.type === 'action_tool') {
      hasAction = 1;
      break;
    }
    if (step.type === 'chunk') {
      hasAction = 0;
    }
  }

  if (hasAction !== 1) {
    const chunks = executionSteps.filter(s => s.type === "chunk");
    const hasFalseReasoning = chunks.some(c => c.is_reasoning === false);

    const hasErrorStep = executionSteps.some(step => {
      const content = step.content || '';
      return step.type === 'error' ||
        content.includes('[错误]') ||
        content.includes('429') ||
        content.includes('限流');
    });

    if (hasErrorStep) {
      return null;
    }

    if (message.isStreaming) {
      if (message.content === "🤔 AI 正在思考...") {
        return null;
      }
      return chunks.length === 0 ? (
        <div
          style={{
            wordBreak: "break-word",
            overflowWrap: "break-word",
            paddingRight: 32,
          }}
        >
          {message.content && typeof message.content === 'string'
            ? message.content.replace(/\n\n/g, '\n')
            : String(message.content || '').replace(/\n\n/g, '\n')}
        </div>
      ) : null;
    }

    return !hasFalseReasoning ? (
      <div
        style={{
          wordBreak: "break-word",
          overflowWrap: "break-word",
          paddingRight: 32,
        }}
      >
        {message.content && typeof message.content === 'string'
          ? message.content.replace(/\n\n/g, '\n')
          : String(message.content || '').replace(/\n\n/g, '\n')}
      </div>
    ) : null;
  }

  return null;
};

/**
 * MessageContent组件
 */
const MessageContent: React.FC<MessageContentProps> = ({
  message,
}) => {
  const chunks = message.executionSteps?.filter(step => step.type === "chunk") || [];

  return (
    <>
      {/* Chunk渲染 */}
      {chunks.length > 0 && <ChunkRenderer chunks={chunks} />}

      {/* Content回退 */}
      <ContentFallback message={message} _hasChunk={chunks.length > 0} />
    </>
  );
};

export default React.memo(MessageContent);
