// 编辑历史: 2026-08-26 小欧 - 8.3 实施: 面板注册表, 按slot注册, 加功能不动骨架(4.3.7)
/**
 * SessionPanelRegistry - 会话页面板注册表
 *
 * 【小欧 2026-08-26 8.3】4.3.7：按 slot 注册面板组件；加新功能 = 注册新面板，
 * 不动骨架。骨架(SessionLayout)只渲染各 slot，不感知面板内容。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import type { ReactNode } from 'react';

export type SlotName =
  'topbar' | 'left' | 'right' | 'taskinfo' | 'config' | 'input';

export interface SessionPanel {
  slot: SlotName;
  key: string; // 唯一标识，用于开关与持久化
  component: ReactNode;
  defaultVisible?: boolean;
  persistVisible?: boolean; // 开关状态是否随会话持久化(localStorage)
}

const PANEL_VISIBLE_PREFIX = 'session_panel_visible:';

export const readPanelVisible = (
  key: string,
  def = true,
  persist = false
): boolean => {
  if (!persist) return def; // 未声明持久化的面板不受存储影响
  const raw = localStorage.getItem(PANEL_VISIBLE_PREFIX + key);
  return raw === null ? def : raw === '1';
};

// 2026-08-27 小欧 修复#7: 删除死代码SessionPanelRegistry类+实例(PANEL_REGISTRY全仓无消费方,SessionLayout已改为panels prop注入)
