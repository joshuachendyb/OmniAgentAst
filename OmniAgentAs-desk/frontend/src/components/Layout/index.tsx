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
import { Layout, Menu, Typography, Avatar, Badge, Tooltip, Drawer, Button, Grid, Tag, Select, message } from 'antd';
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
  ReloadOutlined,
} from '@ant-design/icons';
import { configApi, chatApi } from '../../services/api';
import type { MenuProps } from 'antd';
const { Option } = Select;
import ShortcutPanel from '../ShortcutPanel';

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
  // 快捷指令面板显示状态
  const [shortcutPanelVisible, setShortcutPanelVisible] = useState(false);
  // 响应式断点
  const screens = useBreakpoint();
  const isMobile = !screens.md; // md以下认为是移动端
  
  // 【新增】检查服务状态
  const [serviceStatus, setServiceStatus] = useState<{success: boolean; message: string; provider: string; model: string} | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  // 【修改】当前选中的模型ID（格式: provider-modelname）
  const [_currentProvider, setCurrentProvider] = useState<string>('opencode-minimax-m2.5-free');
  // 【新增】模型列表
  const [modelList, setModelList] = useState<{id: string; name: string; provider: string}[]>([]);
  // 【新增】默认提供商
  const [defaultProvider, setDefaultProvider] = useState<string>('zhipuai');
  
  // 【新增】刷新模型列表 - 点击下拉框时调用，获取最新配置
  const refreshModelList = async () => {
    try {
      const modelData = await configApi.getModelList();
      if (modelData.models) {
        setModelList(modelData.models);
        setDefaultProvider(modelData.default_provider || 'zhipuai');
      }
    } catch (error) {
      console.warn('刷新模型列表失败:', error);
    }
  };
  
  // 手动检查服务
  const handleCheckService = async () => {
    setCheckingStatus(true);
    try {
      const [config, modelData] = await Promise.all([
        configApi.getConfig(),
        configApi.getModelList()
      ]);
      
      // 更新模型列表
      if (modelData.models) {
        setModelList(modelData.models);
      }
      
      // 更新当前选中的模型 - 使用config中的ai_model来匹配正确的模型
      if (config.ai_provider && config.ai_model && modelData.models) {
        const currentModel = modelData.models.find(
          m => m.provider === config.ai_provider && m.id.includes(config.ai_model)
        );
        if (currentModel) {
          setCurrentProvider(currentModel.id);
        }
      }
      
      const status = await chatApi.validateService();
      setServiceStatus(status);
    } catch (error) {
      console.warn('服务检查失败:', error);
    } finally {
      setCheckingStatus(false);
    }
  };
  
  // 页面加载时检查服务
  
  // 【新增】检查服务状态
  useEffect(() => {
    const initApp = async () => {
      setCheckingStatus(true);
      try {
        // 并行获取模型列表和配置
        const [modelData, config] = await Promise.all([
          configApi.getModelList(),
          configApi.getConfig()
        ]);
        
        // 设置模型列表
        if (modelData.models && modelData.models.length > 0) {
          setModelList(modelData.models);
          // 设置默认提供商
          setDefaultProvider(modelData.default_provider || 'zhipuai');
          
          // 设置当前选中的模型 - 使用ai_model匹配正确的模型
          if (config.ai_provider && config.ai_model) {
            const currentModel = modelData.models.find(
              m => m.provider === config.ai_provider && m.id.includes(config.ai_model)
            );
            if (currentModel) {
              setCurrentProvider(currentModel.id);
            }
          }
        }
        
        // 检查服务状态
        const status = await chatApi.validateService();
        setServiceStatus(status);
      } catch (error) {
        console.warn('初始化失败:', error);
      } finally {
        setCheckingStatus(false);
      }
    };
    initApp();
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
    // 快捷指令特殊处理
    if (key === '/shortcuts') {
      setShortcutPanelVisible(true);
      if (isMobile) {
        setDrawerVisible(false);
      }
      return;
    }
    // 使用React Router导航到对应页面
    navigate(key);
    // 移动端点击后关闭抽屉
    if (isMobile) {
      setDrawerVisible(false);
    }
  };

  /**
   * 快捷指令执行处理
   */
  const handleShortcutExecute = (command: string) => {
    // 根据快捷指令执行不同操作
    switch (command) {
      case '/clear':
        // 清空当前对话
        console.log('清空对话');
        break;
      case '/help':
        // 显示帮助
        console.log('显示帮助');
        break;
      case '/history':
        // 跳转到历史记录
        navigate('/history');
        break;
      case '/settings':
        // 跳转到设置
        navigate('/settings');
        break;
      default:
        console.log('执行快捷指令:', command);
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
      {/* 快捷指令弹窗 */}
      <ShortcutPanel
        visible={shortcutPanelVisible}
        onClose={() => setShortcutPanelVisible(false)}
        onExecute={handleShortcutExecute}
      />
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
            {/* 服务状态显示 - 根据检查结果显示不同颜色 */}
            {checkingStatus ? (
              <span style={{ color: '#999' }}>检查中...</span>
            ) : serviceStatus?.success ? (
              <Tag color="success">
                <CheckCircleOutlined /> {serviceStatus.provider} {serviceStatus.model && `(${serviceStatus.model})`}
              </Tag>
            ) : serviceStatus?.message ? (
              // 有错误信息显示红色/黄色（根据错误类型）
              <Tag color={serviceStatus.message.includes('限速') || serviceStatus.message.includes('欠费') || serviceStatus.message.includes('额度') ? 'warning' : 'error'}>
                {serviceStatus.provider} {serviceStatus.model && `(${serviceStatus.model})`} - {serviceStatus.message}
              </Tag>
            ) : (
              // 未配置或初始状态
              <Tag color="error">未配置</Tag>
            )}
          </div>
          
          {/* 右侧操作区 */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            {/* 模型选择下拉框 */}
            {modelList.length > 0 ? (
              <Select
                value={_currentProvider}
                style={{ width: 240 }}
                size="small"
                // 【新增】打开下拉框时刷新模型列表，获取最新配置
                onDropdownVisibleChange={async (open: boolean) => {
                  if (open) {
                    await refreshModelList();
                  }
                }}
                onChange={async (value: string) => {
                  try {
                    // 从modelList中找到对应的模型，获取完整的provider和model
                    const selectedModel = modelList.find(m => m.id === value);
                    if (!selectedModel) {
                      message.error('未找到对应的模型');
                      return;
                    }
                    
                    // 从model id中提取model名称 (格式: "provider-modelname")
                    const modelName = value.replace(`${selectedModel.provider}-`, '');
                    
                    // 调用API切换provider和model
                    await configApi.updateConfig({ 
                      ai_provider: selectedModel.provider as 'zhipuai' | 'opencode' | 'longcat',
                      ai_model: modelName
                    });
                    message.success(`已切换到 ${selectedModel.name}`);
                    
                    // 切换后更新当前选中的模型ID
                    setCurrentProvider(value);
                    
                    // 切换后自动检查服务
                    handleCheckService();
                  } catch (error) {
                    message.error('切换失败');
                  }
                }}
              >
                {modelList.map((model) => (
                  <Option key={model.id} value={model.id}>
                    {model.provider === defaultProvider ? '★ ' : ''}{model.name}
                  </Option>
                ))}
              </Select>
            ) : (
              <Tag color="warning">暂无模型</Tag>
            )}
            {/* 检查服务按钮 */}
            <Button
              icon={<ReloadOutlined />}
              onClick={handleCheckService}
              loading={checkingStatus}
              size="small"
            >
              检查服务
            </Button>
            <Avatar size="small" icon={<DesktopOutlined />} />
            <span style={{ color: '#666', fontSize: 14 }}>用户</span>
          </div>
        </Header>

        {/* 主内容区 - 只有这层有留白 */}
        <Content
          style={{
            margin: 8,
            padding: 8,
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
