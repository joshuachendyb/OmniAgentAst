// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离标题编辑回调至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-09 小欧 - B8/B9依赖收窄: chatState解构为字段级局部变量, 标题回调不再随chatState整体重建(仅字段变化触发) - 小欧-2026-09-09
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
  // 2026-09-09 小欧 B8/B9: 字段级解构, 消除依赖数组对chatState对象的整体引用 — 小欧-2026-09-09
  const {
    editingTitle,
    sessionId,
    sessionTitle,
    setTitleInput,
    setEditingTitle,
  } = chatState;

  const handleEditingStart = useCallback(() => {
    if (!editingTitle && sessionId) {
      setTitleInput(sessionTitle || '');
    }
    setEditingTitle(true);
  }, [editingTitle, sessionId, sessionTitle, setTitleInput, setEditingTitle]);

  const handleEditingCancel = useCallback(() => {
    setEditingTitle(false);
  }, [setEditingTitle]);

  return { handleEditingStart, handleEditingCancel };
}
