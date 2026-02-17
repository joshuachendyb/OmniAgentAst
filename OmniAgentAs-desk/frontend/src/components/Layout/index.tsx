/**
 * Layout组件 - 应用主布局
 * 
 * 功能：左右分栏布局，左侧导航栏，右侧内容区
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import React, { useState } from 'react';
import { Layout, Menu, Typography, Avatar, Badge, Tooltip } from 'antd';
import {
  MessageOutlined,
  FolderOutlined,
  BookOutlined,
  SettingOutlined,
  HistoryOutlined,
  ThunderboltOutlined,
  DesktopOutlined,
} from '@ant-design/icons';
import type { MenuProps } from 'antd';

const { Sider, Content, Header } = Layout;
const { Title } = Typography;

type MenuItem = Required<MenuProps>['items'][number];

interface LayoutProps {
  children: React.ReactNode;
  activeKey?: string;
}

/**
 * 主布局组件
 * 
 * 设计要点：
 * - 左侧固定宽度220px导航栏
 * - 右侧自适应内容区
 * - 响应式：移动端变为抽屉
 * - 导航项带图标和徽标
 * 
 * @param children - 子组件（页面内容）
 * @param activeKey - 当前激活的菜单项
 */
const AppLayout: React.FC<LayoutProps> = ({ children, activeKey = '/' }) => {
  // 未读消息数（实际应从全局状态获取）
  const [unreadCount] = useState(0);
  // 会话数量
  const [sessionCount] = useState(5);
  // 导航折叠状态
  const [collapsed, setCollapsed] = useState(false);

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
        <Badge count={unreadCount} size="small" offset={[10, 0]}>
          <span>对话</span>
        </Badge>
      ),
    },
    {
      key: '/files',
      icon: <FolderOutlined />,
      label: '文件管理',
      disabled: true,
    },
    {
      key: '/knowledge',
      icon: <BookOutlined />,
      label: (
        <Tooltip title="即将上线" placement="right">
          <span style={{ opacity: 0.6 }}>知识库</span>
        </Tooltip>
      ),
      disabled: true,
    },
    { type: 'divider' },
    {
      key: '/history',
      icon: <HistoryOutlined />,
      label: (
        <Badge count={sessionCount} size="small" offset={[10, 0]} showZero={false}>
          <span>历史记录</span>
        </Badge>
      ),
    },
    {
      key: '/shortcuts',
      icon: <ThunderboltOutlined />,
      label: '快捷指令',
      disabled: true,
    },
    { type: 'divider' },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '设置',
    },
  ];

  /**
   * 菜单点击处理
   * 
   * TODO: 接入react-router进行页面跳转
   */
  const handleMenuClick: MenuProps['onClick'] = (e) => {
    console.log('导航到:', e.key);
    // 实际项目中使用: navigate(e.key)
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 左侧导航栏 */}
      <Sider
        width={220}
        theme="light"
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        style={{
          boxShadow: '2px 0 8px rgba(0,0,0,0.05)',
          zIndex: 100,
        }}
      >
        {/* Logo区域 */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? 0 : '0 16px',
            borderBottom: '1px solid #f0f0f0',
          }}
        >
          <Avatar
            size={40}
            icon={<DesktopOutlined />}
            style={{ background: '#1890ff', flexShrink: 0 }}
          />
          {!collapsed && (
            <Title
              level={5}
              style={{
                margin: '0 0 0 12px',
                fontSize: 16,
                fontWeight: 600,
                color: '#1890ff',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
            >
              OmniAgentAst.
            </Title>
          )}
        </div>

        {/* 导航菜单 */}
        <Menu
          mode="inline"
          selectedKeys={[activeKey]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            borderRight: 0,
            paddingTop: 8,
          }}
        />

        {/* 底部信息 */}
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            padding: '12px 16px',
            borderTop: '1px solid #f0f0f0',
            fontSize: 12,
            color: '#999',
            textAlign: collapsed ? 'center' : 'left',
          }}
        >
          {collapsed ? 'v2.1' : '版本 v2.1.0'}
        </div>
      </Sider>

      {/* 右侧内容区 */}
      <Layout>
        {/* 顶部Header */}
        <Header
          style={{
            background: '#fff',
            boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            zIndex: 99,
          }}
        >
          <Title level={4} style={{ margin: 0, fontWeight: 500 }}>
            AI 对话助手
          </Title>
          
          {/* 右侧操作区 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Avatar size="small" icon={<DesktopOutlined />} />
            <span style={{ color: '#666', fontSize: 14 }}>用户</span>
          </div>
        </Header>

        {/* 主内容区 */}
        <Content
          style={{
            margin: 24,
            padding: 24,
            background: '#f5f5f5',
            borderRadius: 8,
            minHeight: 280,
            overflow: 'auto',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
