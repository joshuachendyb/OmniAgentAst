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

// 编辑历史: 2026-10-27 小欧 - v1.3: 审计修复(共 10 处)
//   ①getInitialWidth 删死代码(MAX_RATIO 恒被 MIN 短路无效) + 补越界防护(用户偏好 clamp 到容器 MAX_RATIO, 防跨屏换小屏越界)
//   ②新增 fullLeft 折叠态: 左列 flex:'1 1 0' 填满, 分割线隐藏, 右面板仅按钮条(恢复旧布局语义, 修复功能分支退化)
//   ③maxW 用 state 管理, 消除 aria-valuemax 渲染期读 ref 的反模式(首帧为 0 且不随 resize 更新)
//   ④useEffect → useLayoutEffect, 消首帧闪烁(绘制后设宽导致布局跳动)
//   ⑤ResizeObserver 监听容器尺寸, 窗口缩放按比例重算左列宽度(修复比例失真)
//   ⑥恢复 borderRight 视觉分隔; 折叠态右面板 flex:'0 0 auto'; overflow auto → hidden

//   @author 小欧
//   @date 2026-10-27
import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  SPLIT_LEFT_DEFAULT_RATIO,
  SPLIT_LEFT_MAX_RATIO,
  SPLIT_LEFT_MIN_PX,
  SPLIT_PREFS_KEY,
} from '@/constants/layout';
import { Colors } from '@/utils/stepStyles';

// 2026-10-27 小欧 - 读取 localStorage 中的用户偏好宽度; 失败/无值返回 null
//   为何 try/catch: 隐私模式下 localStorage 可能抛 SecurityError, 不能让组件崩
//   只校验最小值(脏数据), 最大值由 getInitialWidth 根据容器宽度 clamp(防跨屏越界)
const readStoredWidth = (): number | null => {
  try {
    const raw = localStorage.getItem(SPLIT_PREFS_KEY);
    if (raw === null) return null;
    const n = Number(raw);
    // 校验: 必须是有限数且不小于最小值, 防止脏数据把面板撑爆
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
// 2026-10-27 小欧 修复(审计): ①删死代码——原 Math.min(W*0.8, W*0.3) 恒等于 W*0.3,
//   MAX_RATIO 在此处完全无效, 简化为直接乘 DEFAULT_RATIO;
//   ②补越界防护——localStorage 值 clamp 到容器 MAX_RATIO(防大屏拖宽换小屏时左列超出容器)
const getInitialWidth = (containerW: number): number => {
  const stored = readStoredWidth();
  if (stored !== null) {
    // 用户偏好: clamp 到容器最大宽度(跨屏换小屏时防越界)
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);
    return Math.min(stored, maxW);
  }
  if (containerW === 0) {
    // 容器未布局完成且无用户偏好: 返回一个合理的固定值, 避免 width:0 导致面板消失
    return 300;
  }
  return Math.round(containerW * SPLIT_LEFT_DEFAULT_RATIO);
};

interface SplitPaneProps {
  left: React.ReactNode;
  right: React.ReactNode;
  // 2026-10-27 小欧 修复(审计): 折叠态模式——右栏收起时左列填满整个宽度(恢复旧布局语义)
  //   旧布局: 折叠态左列 flex:'1 1 0'(填满≈95%), 右列仅按钮宽条
  //   新布局原设计: 折叠态左列仍固定 30%, 右侧 70% 空白(功能分支丢失)
  //   修复: fullLeft=true 时左列 flex:'1 1 0' 填满, 分割线隐藏, 右面板仅按钮条
  fullLeft?: boolean;
}

const SplitPane: React.FC<SplitPaneProps> = ({
  left,
  right,
  fullLeft = false,
}) => {
  // 2026-10-27 小欧 - 使用 useState 管理左侧宽度, 初始值在 useLayoutEffect 中根据容器宽度计算
  const [leftW, setLeftW] = useState<number | null>(null);
  // 2026-10-27 小欧 修复(审计): maxW 用 state 管理, 消除 aria-valuemax 渲染期读 ref 的反模式
  //   原代码: aria-valuemax={round((containerRef.current?.offsetWidth ?? 0) * MAX_RATIO)}
  //   首帧 containerRef.current=null → aria-valuemax=0(语义错误), 且不随容器 resize 更新
  //   修复: 用 state 存储最大宽度, 由 ResizeObserver 同步更新
  const [maxW, setMaxW] = useState<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // 2026-10-27 小欧 - 初始化宽度: 优先 localStorage 用户偏好, 否则按容器 30%
  // 2026-10-27 小欧 修复(审计): useEffect → useLayoutEffect——消首帧闪烁
  //   原 useEffect 在绘制后设置宽度, 首帧 leftW=null → 宽度由内容决定, 第二帧跳 30%, 布局跳动
  //   useLayoutEffect 在绘制前同步设置, 首帧即正确宽度, 无跳动
  useLayoutEffect(() => {
    if (fullLeft) return; // 折叠态: 左列 flex 填满, 无需计算固定宽度
    const container = containerRef.current;
    if (container) {
      const totalW = container.offsetWidth;
      setLeftW(getInitialWidth(totalW));
      setMaxW(Math.round(totalW * SPLIT_LEFT_MAX_RATIO));
    }
  }, [fullLeft]);

  // 2026-10-27 小欧 修复(审计): ResizeObserver 监听容器尺寸变化——窗口缩放按比例重算左列宽度
  //   原代码: leftW 存固定 px, 窗口缩放后比例失真(大屏 30% → 小屏 56%)
  //   修复: 容器宽度变化时按比例重算; fullLeft 模式左列 flex 填满, 无需计算
  useEffect(() => {
    if (fullLeft) return; // 折叠态: 左列 flex 填满, 无需监听
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const newContainerW = entry.contentRect.width;
      if (newContainerW <= 0) return;
      setMaxW(Math.round(newContainerW * SPLIT_LEFT_MAX_RATIO));
      // 按比例重算: 保持用户设定的比例, 不重置为默认 30%
      setLeftW((prev) => {
        if (prev === null) return getInitialWidth(newContainerW);
        const ratio = prev / (container.offsetWidth || 1);
        const maxW = Math.round(newContainerW * SPLIT_LEFT_MAX_RATIO);
        return Math.min(Math.max(SPLIT_LEFT_MIN_PX, Math.round(newContainerW * ratio)), maxW);
      });
    });
    ro.observe(container);
    return () => ro.disconnect();
  }, [fullLeft]);

  // 2026-10-27 小欧 - 组件卸载时清理事件监听器
  useEffect(() => () => cleanupRef.current?.(), []);

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
        // 2026-10-27 小欧 修复(审计): 用 maxW state 替代渲染期读 containerRef.current
        const next = Math.min(maxW, (w ?? 0) + 16);
        writeStoredWidth(next);
        return next;
      });
    }
  }, [maxW]);

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
          width: fullLeft ? undefined : leftW ?? undefined,
          flex: fullLeft ? '1 1 0' : undefined,
          minWidth: SPLIT_LEFT_MIN_PX,
          overflow: 'auto',
          overflowX: 'hidden',
          // 2026-10-27 小欧 修复(审计): 恢复 borderRight 视觉分隔——原布局左列有 borderRight,
          //   新 SplitPane 分割线默认透明(仅 hover 显示), 导致左列与右侧无可见分隔
          borderRight: `1px solid ${Colors.BORDER.LIGHT}`,
        }}
      >
        {left}
      </div>

      {/* 分割线 - 可拖动; 双击重置为默认宽度
          2026-10-27 小欧 修复(审计): fullLeft 模式(折叠态)不渲染分割线——折叠后拖动无意义 */}
      {!fullLeft && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="调整面板宽度(双击重置为默认)"
          aria-valuenow={leftW ?? 0}
          aria-valuemin={SPLIT_LEFT_MIN_PX}
          aria-valuemax={maxW}
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
      )}

      {/* 右侧面板 */}
      <div
        style={{
          // 2026-10-27 小欧 修复(审计): 折叠态 flex:'0 0 auto'——恢复旧布局语义
          //   旧布局折叠态右列: flex:'0 0 auto' + marginLeft:auto(仅按钮条宽度, 靠右)
          //   原 SplitPane 右面板: 始终 flex:1, 折叠态下与左面板(flex:'1 1 0')平分空间,
          //   导致左列只占一半, 右侧留白(功能分支退化)
          //   修复: fullLeft 时右面板 flex:'0 0 auto'(仅按钮条), 左面板填满剩余空间
          flex: fullLeft ? '0 0 auto' : 1,
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          // 2026-10-27 小欧 修复(审计): overflow auto → hidden——消除意外滚动容器
          //   原 overflow:auto 在右栏容器缺 min-height:0 时成为实际滚动容器,
          //   导致文件足迹随 step 滚动(粘连)、概览展开不可见
          //   修复: 右面板不滚动, 滚动由内层 div(overflowY:auto) 承担
          overflow: 'hidden',
        }}
      >
        {right}
      </div>
    </div>
  );
};

export { SplitPane };
