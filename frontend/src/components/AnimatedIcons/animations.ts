// 编辑历史: 2026-09-15 小欧 - 新建动画资源模块(北京老陈令, AnimatedIcons统一承载内联动画):
//   keyframes常量(取自AuthorizationModal pulse/PillBadge pillShine) + 一次性注入守卫,
//   消除两组件各自重复的style注入逻辑(DRY), 后续新动画keyframes统一注册于此 — 小欧-2026-09-15

/** 动画keyframes注册表: 名称→CSS文本。组件按名注入, 重复要求同源(DRY) */
export const ICON_KEYFRAMES: Record<string, string> = {
  // 2026-09-15 小欧 - 迁自 AuthorizationModal AUTH_MODAL_STYLE: 倒计时≤3s数字呼吸脉动(透明度0.7↔1) — 小欧-2026-09-15
  pulse: `
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.7; }
    }
  `,
  // 2026-09-15 小欧 - 迁自 PillBadge injectShine: 胶囊竖线扫光(背景线性渐变200%上下移动) — 小欧-2026-09-15
  pillShine: `
    @keyframes pillShine {
      0% { background-position: 0 200%; }
      100% { background-position: 0 -100%; }
    }
  `,
};

/** 已注入标记: 同名keyframes每个进程只注入一次(YAGNI, 避免重复<style>标签) */
const injectedKeys = new Set<string>();

/**
 * 按名注入keyframes样式, 同名单例只注入一次
 * 用法: 组件渲染前置调用 injectKeyframes('pulse') → <style>自动挂载document.head
 */
export function injectKeyframes(name: string): void {
  if (injectedKeys.has(name)) return;
  const css = ICON_KEYFRAMES[name];
  if (!css) return;
  injectedKeys.add(name);
  const el = document.createElement('style');
  el.textContent = css;
  document.head.appendChild(el);
}
