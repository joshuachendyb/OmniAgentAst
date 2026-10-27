// 编辑历史: 2026-10-27 小欧 - 新建 SplitPane 组件：可拖动分割面板
//   职责：管理左右面板的宽度拖动逻辑（SRP）
//   设计：复用 Files 页的拖动模式（mousedown/mousemove/mouseup），符合 KISS-DIRECT
//   规范：DRY（拖动逻辑只写一次）、YAGNI（不引入第三方库）、禁止 backward
//   默认：左侧 1/3 宽度，可拖动调整，键盘可访问（←/→）
// 编辑历史: 2026-10-27 小欧 - v1.1: 根据 rightOpen 状态调整默认宽度和边界
//   右侧折叠时：左侧更窄（240px），因为右侧不需要空间
//   右侧展开时：左侧稍宽（280px），给右侧更多空间
//   @author 小欧
//   @date 2026-10-27
import React, { useCallback, useRef, useState } from 'react';

const MIN_LEFT_W = 180; // 最小宽度，防止内容挤压（原 200，减小给右侧更多空间）
const MAX_LEFT_W = 500; // 最大宽度，防止挤压右侧（原 800，减小给右侧更多空间）

// 2026-10-27 小欧 - 根据 rightOpen 状态计算默认宽度
//   右侧折叠时：左侧 240px（约 18%），更窄
//   右侧展开时：左侧 280px（约 22%），稍宽但给右侧更多空间
//   注意：当 containerW 为 0（初始渲染）时，返回固定值而非比例计算
const getInitialWidth = (containerW: number, rightOpen: boolean): number => {
  if (containerW === 0) {
    // 初始渲染时容器宽度为 0，返回固定默认值
    return rightOpen ? 280 : 240;
  }
  if (rightOpen) {
    return Math.min(280, Math.round(containerW * 0.22));
  }
  return Math.min(240, Math.round(containerW * 0.18));
};

interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  initialRatio?: number; // 初始比例，默认 1/3（已废弃，改用 rightOpen）
  rightOpen?: boolean; // 右侧是否展开，影响默认宽度
}

const SplitPane: React.FC<SplitPaneProps> = ({
  left,
  right,
  rightOpen = true,
}) => {
  // 2026-10-27 小欧 - 使用 useState 管理左侧宽度，初始值在 useEffect 中根据容器宽度计算
  const [leftW, setLeftW] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // 2026-10-27 小欧 - 初始化宽度：根据 rightOpen 状态计算默认宽度
  //   右侧折叠时：左侧 240px（约 18%），更窄
  //   右侧展开时：左侧 280px（约 22%），稍宽但给右侧更多空间
  //   使用 useEffect 确保容器已渲染，获取真实宽度
  React.useEffect(() => {
    const container = containerRef.current;
    if (container) {
      const totalW = container.offsetWidth;
      setLeftW(getInitialWidth(totalW, rightOpen));
    }
  }, [rightOpen]);

  // 2026-10-27 小欧 - 组件卸载时清理事件监听器
  React.useEffect(() => () => cleanupRef.current?.(), []);

  // 2026-10-27 小欧 - 拖动开始：记录初始位置和宽度，监听 mousemove/mouseup
  //   符合 KISS-DIRECT：直接使用鼠标事件，不引入复杂抽象
  const startDrag = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const x0 = e.clientX;
    const w0 = leftW ?? 0;
    const container = containerRef.current;
    if (!container) return;

    const containerW = container.offsetWidth;
    const maxW = Math.round(containerW * 0.8); // 最大 80%，保留右侧最小空间

    const move = (ev: MouseEvent) => {
      const newW = Math.min(maxW, Math.max(MIN_LEFT_W, w0 + ev.clientX - x0));
      setLeftW(newW);
    };

    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      cleanupRef.current = null;
    };

    cleanupRef.current = up;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  }, [leftW]);

  // 2026-10-27 小欧 - 键盘可访问：←/→ 调整宽度（符合 WCAG 2.1）
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setLeftW((w) => Math.max(MIN_LEFT_W, (w ?? 0) - 16));
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      setLeftW((w) => Math.min(MAX_LEFT_W, (w ?? 0) + 16));
    }
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        gap: 0,
        alignItems: 'stretch',
        flex: 1,
        minHeight: 0,
      }}
    >
      {/* 左侧面板 */}
      <div
        style={{
          width: leftW ?? undefined,
          minWidth: MIN_LEFT_W,
          overflow: 'auto',
          overflowX: 'hidden',
        }}
      >
        {left}
      </div>

      {/* 分割线 - 可拖动 */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="调整面板宽度"
        aria-valuenow={leftW ?? 0}
        aria-valuemin={MIN_LEFT_W}
        aria-valuemax={MAX_LEFT_W}
        tabIndex={0}
        onMouseDown={startDrag}
        onKeyDown={handleKeyDown}
        style={{
          width: 6,
          cursor: 'col-resize',
          flexShrink: 0,
          borderRadius: 3,
          background: 'transparent',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = 'rgba(22, 119, 255, 0.1)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
        }}
      />

      {/* 右侧面板 */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto',
        }}
      >
        {right}
      </div>
    </div>
  );
};

export { SplitPane };
