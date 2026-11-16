/**
 * NavContent - 侧边导航内容(Logo区 + 导航菜单 + 窄模式CSS注入 + 底部版本/关闭服务区)
 *
 * 功能：
 * - 菜单items配置与点击分发(快捷指令开面板/对话任务回当前会话/其余navigate)
 * - 桌面Sider与移动端Drawer共用本组件(同一渲染源, 移动端点击后经onCloseDrawer关抽屉)
 * - 逻辑自 Layout/index.tsx 原样迁入(仅移动/道具化与色值令牌化未改业务)
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - SRP拆分新建: menuItems/handleMenuClick/renderNavContent(646~744)自index.tsx原样迁入 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 版本号真源化+防覆盖: appVersion改由后端health.version(version.txt首行)props下发(原手写死v2.1.0删除); 底条bottom抬到触发条上方治"桌面端从未显示" - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 魔法数字收口: 43=Size.HEADER_HEIGHT, 12=Spacing.LG, 16/8/20=Spacing.XL/MD/XXL, #e8e8e8=Colors.BORDER.VERTICAL; 13px字档无同值令牌零视差保留 — 小欧-2026-11-02
// 编辑历史: 2026-11-12 小欧 - 字号归位: 版本条 fontSize 13 → FontSize.SECONDARY(13px 档已废除, 原为无同值可替的妥协), import 同步补 FontSize — 小欧-2026-11-12
// 编辑历史: 2026-11-16 小欧 - 底部信息区重构: 版本标签下方、折叠触发条上方新增「关闭服务」按钮(高危低频, 灰字常驻/hover 显危险红), 与设置卡共用 useShutdown — 小欧-2026-11-16
import React from 'react';
import { Badge, Menu } from 'antd';
import type { MenuProps } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  BookOutlined,
  FolderOutlined,
  HistoryOutlined,
  MessageOutlined,
  PoweroffOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { LogoGridIcon } from '../AnimatedIcons';
import { useApp } from '../../contexts/AppContext';
import { showMessage, ErrorType } from '@/services/error/handler';
import { useShutdown } from '@/hooks/useShutdown';
import { CONTROL_HEIGHT_SM } from '@/theme/controlScale';
import {
  Colors,
  FontSize,
  FontWeight,
  Radius,
  Spacing,
  Size,
} from '../../utils/stepStyles';

type MenuItem = Required<MenuProps>['items'][number];

// 2026-11-02 小欧 - antd Sider默认折叠触发条高48px: 底部版本条bottom须抬到其上方, 否则被触发条整条覆盖(桌面端从未显示的根因) — 小欧-2026-11-02
const SIDER_TRIGGER_HEIGHT = 48;

const NavContent: React.FC<{
  activeKey: string;
  collapsed: boolean;
  isMobile: boolean;
  sidebarMode: 'wide' | 'narrow';
  currentSessionId: string | null;
  onOpenShortcuts: () => void;
  onCloseDrawer?: () => void;
  appVersion: string;
}> = ({
  activeKey,
  collapsed,
  isMobile,
  sidebarMode,
  currentSessionId,
  onOpenShortcuts,
  onCloseDrawer,
  appVersion,
}) => {
  const navigate = useNavigate();
  const { sessionCount } = useApp();
  const { loading: shuttingDown, requestShutdown } = useShutdown();
  // appVersion 由 Shell 取自后端真源(health.version=version.txt首行)经props下发, 本组件只渲染

  /**
   * 导航菜单配置
   *
   * 注意：disabled项表示功能预留，待后续开发
   */
  const menuItems: MenuItem[] = [
    {
      key: '/',
      icon: <MessageOutlined />,
      label: (
        <Badge size="small" offset={[6, -4]}>
          <span>对话任务</span>
        </Badge>
      ),
    },
    {
      key: '/files',
      icon: <FolderOutlined />,
      // 2026-10-21 小杨 - /files 解禁(页面已落地), 去disabled与Tooltip — 小杨-2026-10-21
      label: <span>文件管理</span>,
    },
    {
      key: '/knowledge',
      icon: <BookOutlined />,
      label: <span style={{ opacity: 0.6 }}>知识库</span>,
      disabled: true,
    },
    { type: 'divider' },
    {
      key: '/history',
      icon: <HistoryOutlined />,
      label: (
        <Badge
          count={sessionCount}
          size="small"
          offset={[6, -4]}
          showZero={false}
        >
          <span>历史会话</span>
        </Badge>
      ),
    },
    {
      key: '/shortcuts',
      icon: <ThunderboltOutlined />,
      label: '快捷指令',
    },
    { type: 'divider' },
    {
      key: '/settings2',
      icon: <SettingOutlined />,
      label: '设置页面',
    },
  ];

  /**
   * 菜单点击处理：React Router导航
   */
  const handleMenuClick: MenuProps['onClick'] = (e) => {
    const key = e.key;
    // 快捷指令特殊处理
    if (key === '/shortcuts') {
      onOpenShortcuts();
      if (isMobile) {
        onCloseDrawer?.();
      }
      return;
    }
    // 2026-09-30 小欧 - 「对话任务」显式回当前会话: 原navigate('/')不带session_id曾静默漂到最近会话,
    //   改带session_id确定性加载(无则保持原行为), 其它菜单原样navigate不附加无关参数 — 小欧-2026-09-30
    if (key === '/' && currentSessionId) {
      navigate(`/?session_id=${encodeURIComponent(currentSessionId)}`);
    } else {
      navigate(key);
    }
    // 移动端点击后关闭抽屉
    if (isMobile) {
      onCloseDrawer?.();
    }
  };

  return (
    <>
      {/* Logo区域 */}
      <div
        style={{
          // 2026-09-15 小欧 - 高度64→43: 与顶栏Header纵向对齐, 三态统一; 2026-11-02 收口43=Size.HEADER_HEIGHT — 小欧-2026-09-15
          height: Size.HEADER_HEIGHT,
          display: 'flex',
          alignItems: 'center',
          justifyContent: isMobile || collapsed ? 'center' : 'flex-start',
          // 2026-09-15 小欧 - 展开态左缘5px: 36px点阵中心对齐菜单项图标中心(图标14px距左16px) — 小欧-2026-09-15
          padding: isMobile || collapsed ? 0 : '0 5px',
          borderBottom: `1px solid ${Colors.BORDER.LIGHT}`,
        }}
      >
        {!isMobile && (
          // 2026-09-15 小欧 - 左侧Logo图形化: AnimatedIcons/LogoGridIcon(3x3九色点阵); 折叠态容器居中展示点阵 — 小欧-2026-09-15
          // 2026-10-21 小杨 - 双tooltip收敛: 只留原生方框title(antd剥离浮泡) — 小杨-2026-10-21
          <div title="OmniAgentAst">
            <LogoGridIcon />
          </div>
        )}
      </div>

      {/* 2026-10-27 小欧 - 窄菜单模式CSS注入: 必须放Menu外部(AntD5.x不渲染非菜单项children)且用逻辑属性 — 小欧-2026-10-27 */}
      {sidebarMode === 'narrow' && !collapsed && (
        <style>{`
          .ant-menu-inline .ant-menu-item,
          .ant-menu-inline .ant-menu-submenu-title {
            padding-inline-start: 8px !important;
            padding-inline-end: 8px !important;
            margin-inline-start: 0 !important;
            margin-inline-end: 0 !important;
          }
          .ant-menu-inline .ant-menu-item .ant-menu-item-icon,
          .ant-menu-inline .ant-menu-submenu-title .ant-menu-item-icon {
            margin-inline-end: 4px !important;
          }
          .ant-menu-inline .ant-menu-item .ant-menu-title-content,
          .ant-menu-inline .ant-menu-submenu-title .ant-menu-title-content {
            overflow: visible !important;
            white-space: nowrap !important;
          }
        `}</style>
      )}

      {/* 导航菜单 */}
      <Menu
        mode="inline"
        selectedKeys={[activeKey]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{
          borderRight: 0,
          // 2026-11-02 小欧 - 收口: 12=Spacing.LG(零视差) — 小欧-2026-11-02
          paddingTop: Spacing.LG,
          paddingBottom: Spacing.LG,
        }}
      />

      {/* 底部信息区：版本标签在上, 关闭服务按钮在下, 整体抬到折叠触发条上方 */}
      <div
        style={{
          position: 'absolute',
          // 2026-11-02 小欧 - 桌面端抬高到触发条上方(见SIDER_TRIGGER_HEIGHT), 移动端抽屉无触发条贴底 — 小欧-2026-11-02
          bottom: isMobile ? 0 : SIDER_TRIGGER_HEIGHT,
          left: 0,
          right: 0,
          background: Colors.BG.SECONDARY,
          // 2026-11-02 小欧 - 收口: #e8e8e8=Colors.BORDER.VERTICAL(同值零视差) — 小欧-2026-11-02
          borderTop: `1px solid ${Colors.BORDER.VERTICAL}`,
        }}
      >
        {/* 版本条：点击查看版本详情 */}
        <div
          style={{
            // 2026-10-27 小欧 - 窄菜单模式下减少左右padding, 防止文字被截断; 2026-11-02 收口: 16=Spacing.XL, 8=Spacing.MD, 20=Spacing.XXL — 小欧-2026-10-27
            padding:
              sidebarMode === 'narrow'
                ? `${Spacing.MD}px ${Spacing.MD}px`
                : `${Spacing.MD}px ${Spacing.XXL}px`,
            // 2026-11-12 小欧 - 归位 SECONDARY(12): 侧栏底部「关于/版本」触发条属低频次要信息,
            //   归次要正文档。原 13px 裸值是「当年只有 14/12 二档、无同值可替」的妥协, 随阶梯扩充而失效
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.MUTED,
            textAlign: isMobile || collapsed ? 'center' : 'left',
            cursor: 'pointer',
            transition: 'background 0.3s ease',
          }}
          onClick={() =>
            showMessage(
              ErrorType.INFO,
              `OmniAgentAst ${appVersion || '—'} - 事务工作助手`
            )
          }
          onMouseEnter={(e) => {
            e.currentTarget.style.background = Colors.BG.HOVER;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = Colors.BG.SECONDARY;
          }}
        >
          {isMobile || collapsed
            ? appVersion || '—'
            : `版本 ${appVersion || '—'}`}
        </div>

        {/* 关闭服务：高危低频动作, 常驻低强调(灰字), hover 才显危险红语义, 避免常亮红色喧宾夺主 */}
        <div
          style={{
            padding: collapsed
              ? `${Spacing.SM}px 0`
              : `${Spacing.SM}px ${
                  sidebarMode === 'narrow' ? Spacing.MD : Spacing.XXL
                }px`,
            borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
          }}
        >
          <button
            type="button"
            title={collapsed || isMobile ? '关闭后端服务' : undefined}
            disabled={shuttingDown}
            onClick={requestShutdown}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: collapsed ? 'center' : 'flex-start',
              gap: Spacing.SM,
              width: '100%',
              height: CONTROL_HEIGHT_SM,
              padding: collapsed ? 0 : `0 ${Spacing.MD}px`,
              border: 'none',
              borderRadius: Radius.SM,
              background: 'transparent',
              color: Colors.TEXT.MUTED,
              fontSize: FontSize.SECONDARY,
              fontWeight: FontWeight.MEDIUM,
              cursor: shuttingDown ? 'not-allowed' : 'pointer',
              opacity: shuttingDown ? 0.6 : 1,
              transition: 'background 0.2s ease, color 0.2s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = Colors.ERROR_BG;
              e.currentTarget.style.color = Colors.ERROR_TEXT;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent';
              e.currentTarget.style.color = Colors.TEXT.MUTED;
            }}
          >
            <PoweroffOutlined />
            {!collapsed && <span>关闭服务</span>}
          </button>
        </div>
      </div>
    </>
  );
};

export default NavContent;
