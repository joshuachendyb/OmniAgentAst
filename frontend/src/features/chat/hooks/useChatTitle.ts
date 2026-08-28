// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离标题编辑回调至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useCallback } from 'react';
import type { UseChatFacadeReturn } from './useChatFacade';

/**
 * 标题编辑 hook：ChatHeader 编辑开始/取消回调
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatTitle(chatState: UseChatFacadeReturn['chatState']): {
  handleEditingStart: () => void;
  handleEditingCancel: () => void;
} {
  const handleEditingStart = useCallback(() => {
    if (!chatState.editingTitle && chatState.sessionId) {
      chatState.setTitleInput(chatState.sessionTitle || '');
    }
    chatState.setEditingTitle(true);
  }, [
    chatState.editingTitle,
    chatState.sessionId,
    chatState.sessionTitle,
    chatState.setTitleInput,
    chatState.setEditingTitle,
  ]);

  const handleEditingCancel = useCallback(() => {
    chatState.setEditingTitle(false);
  }, [chatState.setEditingTitle]);

  return { handleEditingStart, handleEditingCancel };
}
