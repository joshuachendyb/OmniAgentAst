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
// 编辑历史: 2026-10-27 小欧 - v1.4(用户实测反馈): 双击语义修复(方案A)
//   原实现: 双击清除 localStorage → 跳回 30% 出厂默认(与用户期望"把当前位置设为默认"相反)
//   修复: 双击把当前宽度写入 localStorage 作为新默认, 保持当前宽度不跳回
//   同步: title/aria-label 文案"双击重置为默认"→"双击设为默认宽度", 依赖 [leftW]
// 编辑历史: 2026-10-27 小欧 - v1.5(设计文档[51]): 默认值双向管理
//   ①双击: 存储新默认(当前宽度写入 localStorage, 不跳回) —— 保持 v1.4 行为
//   ②Shift+双击: 返回出厂默认(清除自定义默认 + 重置为 30%)
//   ③重新引入 clearStoredWidth(v1.4 删除, 现 Shift+双击需要)
//   ④提示文案: title/aria-label 增加"Shift+双击返回出厂默认"
// 编辑历史: 2026-10-27 小欧 - v1.6(8个真实Bug修复): 按10大规范(尤其KISS)修复全部8个真实Bug
//   ①Bug-2: ResizeObserver比例计算分母统一用 containerWRef 缓存旧宽度(原混用 offsetWidth 导致比例重算失效)
//   ②Bug-3: maxW 初始值设为安全默认(window.innerWidth*MAX_RATIO), 且 offsetWidth=0 时不覆盖(防键盘→首帧受限)
//   ③Bug-5: containerW=0 硬编码300 补注释说明来源(对应30%的1000px容器)
//   ④Bug-8: startDrag 用 leftWRef 读取当前宽度, 依赖改 [] 消除闭包陷阱(稳定引用)
//   ⑤Bug-15: 拖动 move 实时读 containerWRef 计算 maxW, 拖动中窗口resize用最新值
//   ⑥Bug-13: borderRight 条件化——fullLeft 折叠态不显示视觉分隔线
//   ⑦Bug-6/Bug-10: 测试增强——补拖动/ResizeObserver用例, 键盘→断言改为 >300(修复Bug-3后)
// 编辑历史: 2026-10-28 小欧 - 左面板补 scrollbarGutter:'stable': 防 fail/cancel 时 taskinfo-bar 换行撑高
//   → 中部行压矮 → 左栏纵向滚动条出现/消失 → 内容宽度跳变(CLS弹动); 与右栏 SessionLayout.tsx:153 同款根治 — 小欧-2026-10-28
// 编辑历史: 2026-10-28 小欧 - 修复横向溢出失控(实证: 容器 ResizeObserver 突变52次/scrollWidth 超 clientWidth +307px):
//   根因: 根容器与右面板两级 flex item 均未设 min-width, 取默认 automatic minimum size(min-width:auto),
//     被 step 长行/左栏长文本的 min-content 横向撑破, 且 overflow:visible 不裁剪 → 容器撑破视口;
//     ResizeObserver 见容器变宽按比例放大 leftW, 形成正反馈(左框宽度弹动/折叠按钮移出视口/横向溢出)。
//   修复: 根容器补 minWidth:0+overflow:hidden、右面板补 minWidth:0(允许收缩至 flex 分配宽度, 解除 auto 最小尺寸)。
//   容器宽度自此只随视口缩放, 不随内容/拖动变化。功能逻辑(拖动/双击默认/持久化)零改动。

//   @author 小欧
//   @date 2026-10-27
import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
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

// 2026-10-27 小欧 - v1.4 删除 clearStoredWidth: 双击语义改为"设为新默认"后无调用点, 按 YAGNI 删除
//   (原实现"双击清除 localStorage → 跳回30%"已废弃, 见头部编辑历史 v1.4)
// 2026-10-27 小欧 - v1.5 重新引入: Shift+双击"返回出厂默认"需要清除自定义默认值
//   设计见 doc-10月优化/[51]分割线默认值管理设计
const clearStoredWidth = (): void => {
  try {
    localStorage.removeItem(SPLIT_PREFS_KEY);
  } catch {
    // 隐私模式/配额满时静默失败, 不影响本次会话
  }
};

// 2026-10-27 小欧 - 计算初始宽度: 优先用 localStorage 的用户偏好, 没有才按容器比例
//   注意: containerW 为 0(初始渲染)时, 若 localStorage 有值仍返回该值(不依赖容器)
// 2026-10-27 小欧 修复(审计): ①删死代码——原 Math.min(W*0.8, W*0.3) 恒等于 W*0.3,
//   MAX_RATIO 在此处完全无效, 简化为直接乘 DEFAULT_RATIO;
//   ②补越界防护——localStorage 值 clamp 到容器 MAX_RATIO(防大屏拖宽换小屏时左列超出容器)
// 2026-10-27 小欧 - v1.4 修复(Bug-19): containerW<=0 且有 stored 时返回偏好值而非 0
//   原代码: Math.min(stored, 0*0.8)=0 → 首帧容器未布局(offsetWidth=0)时把左宽设为 0,
//   与无 stored 返回 300 不一致, 且双击"设为新默认"时写回 0 而非当前宽度
//   修复: containerW<=0 时无法 clamp, 直接返回 stored(注释已声明"不依赖容器", 实现补齐)
const getInitialWidth = (containerW: number): number => {
  const stored = readStoredWidth();
  if (stored !== null) {
    // 容器未布局完成(首帧 offsetWidth=0): 无法 clamp, 直接返回偏好值
    if (containerW <= 0) return stored;
    // 用户偏好: clamp 到容器最大宽度(跨屏换小屏时防越界)
    const maxW = Math.round(containerW * SPLIT_LEFT_MAX_RATIO);
    return Math.min(stored, maxW);
  }
  if (containerW === 0) {
    // 容器未布局完成且无用户偏好: 返回一个合理的固定值, 避免 width:0 导致面板消失
    // 来源: 对应 SPLIT_LEFT_DEFAULT_RATIO=0.30 的 1000px 容器(1000*0.30=300), 与默认比例语义一致
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
  // 2026-10-27 小欧 - v1.6 修复(Bug-3): maxW 初始值设为安全默认而非 0
  //   原 maxW=0: 首帧(SSR/offsetWidth=0)时键盘→ Math.min(0, w+16)=0, 宽度无法增大
  //   修复: 初始值用窗口宽度估算(1024*0.8≈819), useLayoutEffect 在 offsetWidth>0 时才覆盖
  const [maxW, setMaxW] = useState<number>(() =>
    Math.round(
      (typeof window !== 'undefined' ? window.innerWidth : 1024) *
        SPLIT_LEFT_MAX_RATIO
    )
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  // 2026-10-27 小欧 - v1.6 修复(Bug-8): leftWRef 同步最新 leftW, 供 startDrag 稳定引用(读 ref 而非闭包)
  const leftWRef = useRef<number>(0);
  leftWRef.current = leftW ?? 0;
  // 2026-10-27 小欧 - v1.6 修复(Bug-2): containerWRef 缓存最新容器宽度, 供 ResizeObserver/startDrag 统一读取
  //   原 ResizeObserver 混用 entry.contentRect.width(分子) 与 container.offsetWidth(分母),
  //   两者来源不同导致比例重算失效; 修复: 统一用 ref 缓存旧宽度做分母
  const containerWRef = useRef<number>(0);

  // 2026-10-27 小欧 - 初始化宽度: 优先 localStorage 用户偏好, 否则按容器 30%
  // 2026-10-27 小欧 修复(审计): useEffect → useLayoutEffect——消首帧闪烁
  //   原 useEffect 在绘制后设置宽度, 首帧 leftW=null → 宽度由内容决定, 第二帧跳 30%, 布局跳动
  //   useLayoutEffect 在绘制前同步设置, 首帧即正确宽度, 无跳动
  useLayoutEffect(() => {
    if (fullLeft) return; // 折叠态: 左列 flex 填满, 无需计算固定宽度
    const container = containerRef.current;
    if (container) {
      const totalW = container.offsetWidth;
      // leftW 始终初始化: getInitialWidth 内部处理 totalW<=0 的边界(返回偏好值或300)
      setLeftW(getInitialWidth(totalW));
      // v1.6 修复(Bug-3): maxW 只在有实际容器宽度时设置, 避免 offsetWidth=0 时覆盖安全初始值
      if (totalW > 0) {
        containerWRef.current = totalW;
        setMaxW(Math.round(totalW * SPLIT_LEFT_MAX_RATIO));
      }
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
      // v1.6 修复(Bug-2): 用 containerWRef 缓存旧宽度做分母, 统一尺寸来源
      //   原代码: ratio = prev / (container.offsetWidth || 1) —— 分母用 offsetWidth(可能滞后),
      //   分子用 entry.contentRect.width(准确), 两者混用导致比例重算失效
      //   修复: 先读缓存旧宽度, 再更新 ref 为新宽度, 分母/分子来源一致
      const oldContainerW = containerWRef.current || newContainerW;
      containerWRef.current = newContainerW;
      setMaxW(Math.round(newContainerW * SPLIT_LEFT_MAX_RATIO));
      // 按比例重算: 保持用户设定的比例, 不重置为默认 30%
      setLeftW((prev) => {
        if (prev === null) return getInitialWidth(newContainerW);
        const ratio = prev / (oldContainerW || 1);
        const maxW = Math.round(newContainerW * SPLIT_LEFT_MAX_RATIO);
        return Math.min(
          Math.max(SPLIT_LEFT_MIN_PX, Math.round(newContainerW * ratio)),
          maxW
        );
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
    // v1.6 修复(Bug-8): 读 leftWRef 而非闭包 leftW —— 依赖改 [] 后 startDrag 稳定引用,
    //   闭包不再捕获旧 leftW, 拖动中其他操作改 leftW 不产生竞态
    const w0 = leftWRef.current;
    lastWidthRef.current = w0;
    const container = containerRef.current;
    if (!container) return;

    const move = (ev: MouseEvent) => {
      // v1.6 修复(Bug-15): 实时读 containerWRef 计算 maxW, 拖动中窗口 resize 用最新值
      //   原代码: maxW 在 mousedown 时捕获到闭包, 拖动中容器宽度变化仍用旧值
      const currentMaxW = Math.round(
        (containerWRef.current || container.offsetWidth) * SPLIT_LEFT_MAX_RATIO
      );
      const newW = Math.min(
        currentMaxW,
        Math.max(SPLIT_LEFT_MIN_PX, w0 + ev.clientX - x0)
      );
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
  }, []);

  // 2026-10-27 小欧 - 键盘可访问: ←/→ 调整宽度(符合 WCAG 2.1)
  //   v1.2: 每次按键后写入 localStorage(键盘事件频率低, 无需防抖)
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
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
    },
    [maxW]
  );

  // 2026-10-27 小欧 - 双击分割线: 默认值双向管理(设计文档 [51])
  //   用户实测反馈(2026-10-27 17:25): 原实现"清除 localStorage → 跳回 30% 出厂默认",
  //   与用户期望"双击=把当前位置设为默认值"相反, 故按方案A修复:
  //   ①双击: 存储新默认——当前宽度写入 localStorage, 不跳回
  //   ②Shift+双击: 返回出厂默认——清除自定义默认 + 重置为 30%
  //   依赖: [leftW] —— 需要当前宽度做新默认值
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      const container = containerRef.current;
      if (!container) return;
      if (e.shiftKey) {
        // Shift+双击: 返回出厂默认(清除自定义默认 + 重置为 30%)
        clearStoredWidth();
        setLeftW(getInitialWidth(container.offsetWidth)); // 清除后 getInitialWidth 返回 30%
        return;
      }
      // 双击: 存储新默认(当前宽度写入 localStorage, 不跳回)
      const cur = leftW ?? getInitialWidth(container.offsetWidth);
      writeStoredWidth(cur); // ① 写回 localStorage 作为新的持久化默认
      setLeftW(cur); // ② 保持当前宽度, 不跳回 30%
    },
    [leftW]
  );

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        gap: 0,
        alignItems: 'stretch',
        flex: 1,
        minHeight: 0,
        // 2026-10-28 小欧 - 修复横向溢出失控(实证: 容器 ResizeObserver 突变52次/scrollWidth 超 clientWidth +307px):
        //   本容器是中部行的 flex item, 未设 min-width → 取默认 automatic minimum size(min-width:auto),
        //   内容(step 长行/左栏长文本)撑大其 min-content, 且 overflow:visible 不裁剪 → 容器被横向撑破;
        //   ResizeObserver 据此放大 leftW 形成正反馈。修复: minWidth:0(允许收缩至 flex 分配宽度, 解除 auto 最小尺寸),
        //   overflow:hidden(建立 BFC 裁剪溢出)。容器宽度自此只随视口缩放, 不随内容/拖动变化。
        minWidth: 0,
        overflow: 'hidden',
      }}
    >
      {/* 左侧面板 */}
      <div
        style={{
          width: fullLeft ? undefined : (leftW ?? undefined),
          flex: fullLeft ? '1 1 0' : undefined,
          minWidth: SPLIT_LEFT_MIN_PX,
          overflow: 'auto',
          overflowX: 'hidden',
          // 2026-10-28 小欧 - 防 fail/cancel 时左栏高度变化致纵向滚动条出现/消失→内容宽度跳变(CLS弹动), 与右栏 SessionLayout.tsx:153 同款根治 — 小欧-2026-10-28
          scrollbarGutter: 'stable',
          // 2026-10-27 小欧 修复(审计): 恢复 borderRight 视觉分隔——原布局左列有 borderRight,
          //   新 SplitPane 分割线默认透明(仅 hover 显示), 导致左列与右侧无可见分隔
          // 2026-10-27 小欧 - v1.6 修复(Bug-13): borderRight 条件化——fullLeft 折叠态不显示分隔线
          //   原代码: borderRight 始终渲染, 折叠态左面板右侧仍有一条分隔线(视觉干扰, 且与分割线隐藏逻辑不一致)
          //   修复: 折叠态 borderRight:'none', 展开态才显示
          borderRight: fullLeft ? 'none' : `1px solid ${Colors.BORDER.LIGHT}`,
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
          aria-label="调整面板宽度(双击设为默认宽度, Shift+双击返回出厂默认)"
          aria-valuenow={leftW ?? 0}
          aria-valuemin={SPLIT_LEFT_MIN_PX}
          aria-valuemax={maxW}
          tabIndex={0}
          onMouseDown={startDrag}
          onKeyDown={handleKeyDown}
          onDoubleClick={handleDoubleClick}
          title="拖动调整宽度; 双击设为默认宽度; Shift+双击返回出厂默认"
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
          // 2026-10-28 小欧 - 修复横向溢出: 右面板未设 min-width → 默认 min-width:auto, step 长行/长文本
          //   撑大其 min-content 致面板被顶出视口(absolute 定位的折叠按钮随其右边缘一同移出可视区);
          //   补 minWidth:0 允许收缩至 flex 分配宽度, 右边缘约束在容器内。
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          // 2026-10-27 小欧 修复(审计): overflow auto → hidden——消除意外滚动容器
          //   原 overflow:auto 在右栏容器缺 min-height:0 时成为实际滚动容器,
          //   导致文件足迹随 step 滚动(粘连)、任务统计展开不可见
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
