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
  | 'topbar'
  | 'left'
  | 'right'
  | 'taskinfo'
  | 'config'
  | 'input';

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

export const writePanelVisible = (
  key: string,
  persist: boolean,
  visible: boolean
): void => {
  if (!persist) return; // 仅 persistVisible=true 才写存储
  localStorage.setItem(PANEL_VISIBLE_PREFIX + key, visible ? '1' : '0');
};

class SessionPanelRegistry {
  private panels: SessionPanel[] = [];

  register(panel: SessionPanel): void {
    this.unregister(panel.key);
    this.panels.push(panel);
  }

  unregister(key: string): void {
    this.panels = this.panels.filter((p) => p.key !== key);
  }

  getBySlot(slot: SlotName): SessionPanel[] {
    return this.panels
      .filter((p) => p.slot === slot)
      .sort((a, b) => a.key.localeCompare(b.key));
  }

  getAll(): SessionPanel[] {
    return [...this.panels];
  }
}

export const sessionPanelRegistry = new SessionPanelRegistry();
