/**
 * SidebarModeSwitcher - 侧边栏宽/窄菜单切换控件(顶栏用)
 *
 * 功能：
 * - 宽/窄两套模式常量与 localStorage 持久化 read/write(SIDEBAR_MODE_KEY)
 * - 图标按钮点击切换并派发 sidebar-mode-change CustomEvent, AppLayout 监听后更新宽度
 * - 逻辑自 Layout/index.tsx 原样迁入(仅移动未改业务)
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - SRP拆分新建: SIDEBAR_MODES/readSidebarMode/writeSidebarMode/getSidebarWidths/SidebarModeSwitcher自index.tsx 104~208原样迁入, 逻辑零改动 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 三堂会审收口: svg盒16=Icon.BOX, pad4/8=Spacing.XS/MD, 圆角4=Radius.SM, 字12=FontSize.SECONDARY, hover底rgba留组件常量(零视差) - 小欧-2026-11-02
import React, { useState } from 'react';
import { Button } from 'antd';
import {
  Colors,
  Spacing,
  Radius,
  Icon,
  FontSize,
} from '../../utils/stepStyles';

// 2026-11-02 小欧 - hover底rgba(22,119,255,0.1)无同值令牌, stepStyles硬规定不新增颜色令牌, 留组件常量 — 小欧-2026-11-02
const HOVER_BG_SOFT = 'rgba(22, 119, 255, 0.1)'; // 主蓝10%透明hover底

// 2026-10-27 小欧 - 侧边栏宽度优化: 定义两套参数(宽菜单/窄菜单), 支持设置页切换
//   宽菜单: 展开=180px, 折叠=80px (适合大屏, 显示更多内容)
//   窄菜单: 展开=120px, 折叠=48px (适合小屏, 节省空间)
//   localStorage 键: omni.sidebar.mode (值: 'wide' | 'narrow')
const SIDEBAR_MODES = {
  wide: { expanded: 180, collapsed: 80 },
  narrow: { expanded: 120, collapsed: 48 },
} as const;

const SIDEBAR_MODE_KEY = 'omni.sidebar.mode';

// 2026-10-27 小欧 - 读取用户选择的侧边栏模式(默认宽菜单)
export const readSidebarMode = (): 'wide' | 'narrow' => {
  try {
    const mode = localStorage.getItem(SIDEBAR_MODE_KEY);
    if (mode === 'wide' || mode === 'narrow') return mode;
  } catch {
    // 隐私模式静默失败
  }
  return 'wide'; // 默认宽菜单
};

// 2026-10-27 小欧 - 写入用户选择的侧边栏模式
const writeSidebarMode = (mode: 'wide' | 'narrow'): void => {
  try {
    localStorage.setItem(SIDEBAR_MODE_KEY, mode);
  } catch {
    // 隐私模式静默失败
  }
};

// 2026-10-27 小欧 - 获取当前模式对应的宽度参数
export const getSidebarWidths = (mode: 'wide' | 'narrow') =>
  SIDEBAR_MODES[mode];

// 2026-10-27 小欧 - 菜单宽度切换组件(顶栏用, 漂亮的视觉设计)
// 设计: 简洁的图标按钮, 宽菜单显示三竖条, 窄菜单显示单竖条, 点击切换
export const SidebarModeSwitcher: React.FC = () => {
  const [mode, setMode] = useState<'wide' | 'narrow'>(readSidebarMode);

  const handleModeChange = () => {
    const newMode = mode === 'wide' ? 'narrow' : 'wide';
    setMode(newMode);
    writeSidebarMode(newMode);
    // 触发自定义事件, 让 Layout 组件感知模式变化
    window.dispatchEvent(
      new CustomEvent('sidebar-mode-change', { detail: { mode: newMode } })
    );
  };

  // 2026-10-27 小欧 - 宽菜单图标(三个竖条, 宽度较大); 2026-11-02 三堂会审收口: 盒边16=Icon.BOX — 小欧-2026-10-27
  const renderWideIcon = () => (
    <svg
      width={Icon.BOX}
      height={Icon.BOX}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="2" y="3" width="3" height="10" rx="1" fill="currentColor" />
      <rect x="6.5" y="3" width="3" height="10" rx="1" fill="currentColor" />
      <rect x="11" y="3" width="3" height="10" rx="1" fill="currentColor" />
    </svg>
  );

  // 2026-10-27 小欧 - 窄菜单图标(一个竖条, 宽度较小)
  const renderNarrowIcon = () => (
    <svg
      width={Icon.BOX}
      height={Icon.BOX}
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect x="6" y="3" width="4" height="10" rx="1" fill="currentColor" />
    </svg>
  );

  return (
    <Button
      type="text"
      size="small"
      icon={mode === 'wide' ? renderWideIcon() : renderNarrowIcon()}
      onClick={handleModeChange}
      title={mode === 'wide' ? '切换到窄菜单' : '切换到宽菜单'}
      style={{
        color: Colors.TEXT.MUTED,
        // 2026-11-02 小欧 - 三堂会审收口: 4=Spacing.XS, 8=Spacing.MD, 圆角4=Radius.SM(零视差) — 小欧-2026-11-02
        padding: `${Spacing.XS}px ${Spacing.MD}px`,
        borderRadius: Radius.SM,
        transition: 'all 0.2s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.color = Colors.PRIMARY;
        e.currentTarget.style.background = HOVER_BG_SOFT;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.color = Colors.TEXT.MUTED;
        e.currentTarget.style.background = 'transparent';
      }}
    >
      <span style={{ fontSize: FontSize.SECONDARY, marginLeft: Spacing.XS }}>
        {mode === 'wide' ? '宽' : '窄'}
      </span>
    </Button>
  );
};
