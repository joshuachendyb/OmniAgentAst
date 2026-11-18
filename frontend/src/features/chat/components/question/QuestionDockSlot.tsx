// 2026-11-18 商量 - question dock 面板槽包装: hook 内聚在组件里, useChatPanels 只注册组件不订阅 store
import { useQuestionDock } from '@/features/chat/hooks/useQuestionDock';
import { QuestionDock } from './QuestionDock';

interface QuestionDockSlotProps {
  sessionId: string | null;
}

export function QuestionDockSlot({ sessionId }: QuestionDockSlotProps) {
  const controller = useQuestionDock(sessionId);
  return <QuestionDock controller={controller} />;
}
