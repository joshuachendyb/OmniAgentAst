// 编辑历史: 2026-10-27 小欧 - 新建 SplitPane 组件：可拖动分割面板
//   职责：管理左右面板的宽度拖动逻辑（SRP）
//   设计：复用 Files 页的拖动模式（mousedown/mousemove/mouseup），符合 KISS-DIRECT
//   规范：DRY（拖动逻辑只写一次）、YAGNI（不引入第三方库）、禁止 backward
//   默认：左侧 30% 宽度，可拖动调整，键盘可访问（←/→）
// 编辑历史: 2026-10-27 小欧 - v1.1: 默认宽度固定为 30%（与右侧展开/折叠状态无关）
// 编辑历史: 2026-10-27 小欧 - v1.2: 加 localStorage 持久化 + 配置常量化 + 双击重置
//   ①拖动后的宽度写入 localStorage(SPLIT_PREFS_KEY), 下次打开沿用, 不再回退默认
//   ②默认宽度等 3 个数字上移到 constants/layout.ts(唯一定义点), 改默认只改配置
//   ③新增双击分割线彩蛋: 清除 localStorage 并重置为默认 30%(用户改坏了可一键回滚)
//   ④拖动过程中不写 localStorage(仅 mouseup 时写一次), 避免 mousemove 高频 IO
//   @author 小欧
//   @date 2026-10-27
import React, { useCallback, useRef, useState } from 'react';
import {
  SPLIT_LEFT_DEFAULT_RATIO,
  SPLIT_LEFT_MAX_RATIO,
  SPLIT_LEFT_MIN_PX,
  SPLIT_PREFS_KEY,
} from '@/constants/layout';

// 2026-10-27 小欧 - 读取 localStorage 中的用户偏好宽度; 失败/无值返回 null
//   为何 try/catch: 隐私模式下 localStorage 可能抛 SecurityError, 不能让组件崩
const readStoredWidth = (): number | null => {
  try {
    const raw = localStorage.getItem(SPLIT_PREFS_KEY);
    if (raw === null) return null;
    const n = Number(raw);
    // 校验: 必须是有限数且在合理范围内, 防止脏数据把面板撑爆
    if (!Number.isFinite(n) || n < SPLIT_LEFT_MIN_PX) return null;
    return n;
  } catch {
    return null;
  }
};

// 2026-10-27 小欧 - 写入 localStorage; 失败静默吞掉(偏好存储非阻断项)
const writeStoredWidth = (w: number): void => {
  try {
    localStorage.setItem(SPLIT_PREFS_KEY, String(Math.round(w)));
  } catch {
    // 隐私模式/配额满时静默失败, 不影响本次会话的拖动体验
  }
};

// 2026-10-27 小欧 - 清除 localStorage(双击重置用)
const clearStoredWidth = (): void => {
  try {
    localStorage.removeItem(SPLIT_PREFS_KEY);
  } catch {
    // 同上, 静默
  }
};

// 2026-10-27 小欧 - 计算初始宽度: 优先用 localStorage 的用户偏好, 没有才按容器比例
//   注意: containerW 为 0(初始渲染)时, 若 localStorage 有值仍返回该值(不依赖容器)
const getInitialWidth = (containerW: number): number => {
  const stored = readStoredWidth();
  if (stored !== null) return stored;
  if (containerW === 0) {
    // 容器未布局完成且无用户偏好: 返回一个合理的固定值, 避免 width:0 导致面板消失
    return 300;
  }
  return Math.min(
    Math.round(containerW * SPLIT_LEFT_MAX_RATIO),
    Math.round(containerW * SPLIT_LEFT_DEFAULT_RATIO)
  );
};

interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
}

const SplitPane: React.FC<SplitPaneProps> = ({
  left,
  right,
}) => {
  // 2026-10-27 小欧 - 使用 useState 管理左侧宽度, 初始值在 useEffect 中根据容器宽度计算
  const [leftW, setLeftW] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // 2026-10-27 小欧 - 初始化宽度: 优先 localStorage 用户偏好, 否则按容器 30%
  //   使用 useEffect 确保容器已渲染, 获取真实宽度
  React.useEffect(() => {
    const container = containerRef.current;
    if (container) {
      const totalW = container.offsetWidth;
      setLeftW(getInitialWidth(totalW));
    }
  }, []);

  // 2026-10-27 小欧 - 组件卸载时清理事件监听器
  React.useEffect(() => () => cleanupRef.current?.(), []);

  // 2026-10-27 小欧 - 拖动开始: 记录初始位置和宽度, 监听 mousemove/mouseup
  //   符合 KISS-DIRECT: 直接使用鼠标事件, 不引入复杂抽象
  //   v1.2: mouseup 时把最终宽度写入 localStorage(仅一次, 避免 mousemove 高频 IO)
  //   用 lastWidthRef 记录最新宽度, 避免 setLeftW 异步导致 up 时读到旧值
  const lastWidthRef = useRef<number>(0);

  const startDrag = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    const x0 = e.clientX;
    const w0 = leftW ?? 0;
    lastWidthRef.current = w0;
    const container = containerRef.current;
    if (!container) return;

    const containerW = container.offsetWidth;
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);

    const move = (ev: MouseEvent) => {
      const newW = Math.min(maxW, Math.max(SPLIT_LEFT_MIN_PX, w0 + ev.clientX - x0));
      lastWidthRef.current = newW;
      setLeftW(newW);
    };

    const up = () => {
      window.removeEventListener('mousemove', move);
      window.removeEventListener('mouseup', up);
      document.body.style.userSelect = '';
      document.body.style.cursor = '';
      cleanupRef.current = null;
      // 2026-10-27 小欧 - 拖动结束, 持久化最终宽度(读 ref 而非 state, 避免异步旧值)
      writeStoredWidth(lastWidthRef.current);
    };

    cleanupRef.current = up;
    document.body.style.userSelect = 'none';
    document.body.style.cursor = 'col-resize';
    window.addEventListener('mousemove', move);
    window.addEventListener('mouseup', up);
  }, [leftW]);

  // 2026-10-27 小欧 - 键盘可访问: ←/→ 调整宽度(符合 WCAG 2.1)
  //   v1.2: 每次按键后写入 localStorage(键盘事件频率低, 无需防抖)
  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      setLeftW((w) => {
        const next = Math.max(SPLIT_LEFT_MIN_PX, (w ?? 0) - 16);
        writeStoredWidth(next);
        return next;
      });
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      setLeftW((w) => {
        const next = Math.min(
          Math.round((containerRef.current?.offsetWidth ?? 0) * SPLIT_LEFT_MAX_RATIO),
          (w ?? 0) + 16
        );
        writeStoredWidth(next);
        return next;
      });
    }
  }, []);

  // 2026-10-27 小欧 - 双击分割线: 重置为默认 30%(清除 localStorage)
  //   用途: 用户拖坏了/想回到初始状态, 一键回滚, 不用清浏览器数据
  const handleDoubleClick = useCallback(() => {
    clearStoredWidth();
    const container = containerRef.current;
    if (container) {
      setLeftW(getInitialWidth(container.offsetWidth));
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
          minWidth: SPLIT_LEFT_MIN_PX,
          overflow: 'auto',
          overflowX: 'hidden',
        }}
      >
        {left}
      </div>

      {/* 分割线 - 可拖动; 双击重置为默认宽度 */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label="调整面板宽度(双击重置为默认)"
        aria-valuenow={leftW ?? 0}
        aria-valuemin={SPLIT_LEFT_MIN_PX}
        aria-valuemax={Math.round((containerRef.current?.offsetWidth ?? 0) * SPLIT_LEFT_MAX_RATIO)}
        tabIndex={0}
        onMouseDown={startDrag}
        onKeyDown={handleKeyDown}
        onDoubleClick={handleDoubleClick}
        title="拖动调整宽度; 双击重置为默认"
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
