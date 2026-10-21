// 编辑历史: 2026-10-21 小杨 - 新建：可选导航（无 Router 上下文不抛） — 小杨-2026-10-21
/**
 * useOptionalNavigate —— "有 Router 就 SPA 跳，没有就整页跳"的可选导航
 *
 * 为什么需要：`useNavigate()` 在**无 Router 上下文**时抛
 *   "useNavigate() may be used only in the context of a <Router> component" → 整块渲染崩。
 *   本仓有两类渲染场景不在 Router 内：
 *   ① 单测直接渲染组件（TaskListPanel / MarkdownSlot / FileRefChip 的既有测试即如此）；
 *   ② markdown 渲染层可能被非路由容器使用。
 *
 * 为什么不用 `useNavigate` + try/catch：Hook 不能条件调用、也不能被 try 包住（Hook 顺序会乱）。
 *   故直接读 Router 的导航上下文（react-router 的 `UNSAFE_NavigationContext`，
 *   即 `useNavigate` 内部用的同一个 context），**有就用它的 navigator，没有就整页跳**。
 */
import { useContext } from 'react';
import { UNSAFE_NavigationContext } from 'react-router';

export type OptionalNavigate = (to: string) => void;

interface NavigationCtx {
  navigator?: { push?: (to: string) => void };
}

export const useOptionalNavigate = (): OptionalNavigate => {
  const ctx = useContext(UNSAFE_NavigationContext) as NavigationCtx | null;
  const navigator = ctx?.navigator;
  return (to: string) => {
    if (navigator?.push) {
      navigator.push(to);
      return;
    }
    // 无 Router 上下文（单测 / 非路由容器）→ 整页跳转兜底
    window.location.assign(to);
  };
};
