/**
 * Layout组件 - 应用主布局（响应式版）
 * 
 * 功能：左右分栏布局，左侧导航栏，右侧内容区，支持移动端响应式
 * 
 * @author 小新
 * @version 1.1.0
 * @since 2026-02-17
 * @update 2026-02-18 添加移动端响应式支持
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Menu, Typography, Avatar, Badge, Tooltip, Drawer, Button, Grid, Tag } from 'antd';
import {
  MessageOutlined,
  FolderOutlined,
  BookOutlined,
  SettingOutlined,
  HistoryOutlined,
  ThunderboltOutlined,
  DesktopOutlined,
  MenuOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { configApi, chatApi } from '../../services/api';
import type { MenuProps } from 'antd';

const { useBreakpoint } = Grid;

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
 * - 集成React Router导航
 * 
 * @param children - 子组件（页面内容）
 * @param activeKey - 当前激活的菜单项
 * 
 * @author 小新
 * @version 1.2.0
 * @since 2026-02-17
 * @update 2026-02-18 集成React Router导航 - by 小新
 */
const AppLayout: React.FC<LayoutProps> = ({ children, activeKey = '/' }) => {
  // 路由导航
  const navigate = useNavigate();
  // 未读消息数（实际应从全局状态获取）
  const [unreadCount] = useState(0);
  // 会话数量
  const [sessionCount] = useState(5);
  // 导航折叠状态
  const [collapsed, setCollapsed] = useState(false);
  // 移动端抽屉显示状态
  const [drawerVisible, setDrawerVisible] = useState(false);
  // 响应式断点
  const screens = useBreakpoint();
  const isMobile = !screens.md; // md以下认为是移动端
  
  // 【新增】服务状态
  const [serviceStatus, setServiceStatus] = useState<{success: boolean; message: string; provider: string; model: string} | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  const [currentProvider, setCurrentProvider] = useState('opencode');
  
  // 【新增】检查服务状态
  useEffect(() => {
    const checkService = async () => {
      setCheckingStatus(true);
      try {
        // 先获取配置
        const config = await configApi.getConfig();
        if (config.ai_provider) {
          setCurrentProvider(config.ai_provider);
        }
        // 再检查服务
        const status = await chatApi.validateService();
        setServiceStatus(status);
      } catch (error) {
        console.warn('服务检查失败:', error);
      } finally {
        setCheckingStatus(false);
      }
    };
    checkService();
  }, []);

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
          <span>对话与下任务</span>
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
   * 功能：使用React Router进行页面导航
   * 
   * @author 小新
   */
  const handleMenuClick: MenuProps['onClick'] = (e) => {
    const key = e.key;
    // 使用React Router导航到对应页面
    navigate(key);
    // 移动端点击后关闭抽屉
    if (isMobile) {
      setDrawerVisible(false);
    }
  };

  /**
   * 渲染导航内容
   */
  const renderNavContent = () => (
    <>
      {/* Logo区域 */}
      <div
        style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: isMobile || collapsed ? 'center' : 'flex-start',
          padding: isMobile || collapsed ? 0 : '0 16px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        <Avatar
          size={40}
          icon={<DesktopOutlined />}
          style={{ background: '#1890ff', flexShrink: 0 }}
        />
        {!isMobile && !collapsed && (
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
          textAlign: isMobile || collapsed ? 'center' : 'left',
        }}
      >
        {isMobile || collapsed ? 'v2.1' : '版本 v2.1.0'}
      </div>
    </>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {/* 移动端：抽屉式导航 */}
      {isMobile ? (
        <Drawer
          placement="left"
          closable={false}
          onClose={() => setDrawerVisible(false)}
          open={drawerVisible}
          width={220}
          bodyStyle={{ padding: 0 }}
        >
          {renderNavContent()}
        </Drawer>
      ) : (
        /* 桌面端：左侧导航栏 */
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
          {renderNavContent()}
        </Sider>
      )}

      {/* 右侧内容区 */}
      <Layout>
        {/* 顶部Header */}
        <Header
          style={{
            background: '#fff',
            boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
            padding: isMobile ? '0 16px' : '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            zIndex: 99,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            {/* 移动端菜单按钮 */}
            {isMobile && (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setDrawerVisible(true)}
                style={{ fontSize: 18 }}
              />
            )}
            <Title level={4} style={{ margin: 0, fontWeight: 500, fontSize: isMobile ? 16 : 18 }}>
              对话与任务
            </Title>
            {/* 【新增】服务状态显示 */}
            <Tag color={serviceStatus?.success ? 'success' : checkingStatus ? 'processing' : 'warning'}>
              {checkingStatus ? (
                '检查中...'
              ) : serviceStatus?.success ? (
                <><CheckCircleOutlined /> {serviceStatus.message}</>
              ) : (
                serviceStatus?.message || '未就绪'
              )}
            </Tag>
          </div>
          
          {/* 右侧操作区 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Avatar size="small" icon={<DesktopOutlined />} />
            <span style={{ color: '#666', fontSize: 14 }}>用户</span>
          </div>
        </Header>

        {/* 主内容区 */}
        <Content
          style={{
            margin: isMobile ? 12 : 24,
            padding: isMobile ? 16 : 24,
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
