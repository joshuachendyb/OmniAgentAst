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

import React, { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  Layout,
  Menu,
  Typography,
  Avatar,
  Badge,
  Tooltip,
  Drawer,
  Button,
  Grid,
  Tag,
  Select,
  message,
  Modal,
  Alert,
} from "antd";
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
} from "@ant-design/icons";
import { configApi } from "../../services/api";
import type { ValidateResponse } from "../../services/api";
import type { MenuProps } from "antd";
const { Option } = Select;
import ShortcutPanel from "../ShortcutPanel";
import { useApp } from "../../contexts/AppContext";

const { useBreakpoint } = Grid;

const { Sider, Content, Header } = Layout;
const { Title } = Typography;

type MenuItem = Required<MenuProps>["items"][number];

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
const AppLayout: React.FC<LayoutProps> = ({ children, activeKey = "/" }) => {
  // 路由导航
  const navigate = useNavigate();
  // 未读消息数（实际应从全局状态获取）
  const [unreadCount] = useState(0);
  // 导航折叠状态
  const [collapsed, setCollapsed] = useState(false);
  // 移动端抽屉显示状态
  const [drawerVisible, setDrawerVisible] = useState(false);
  // 快捷指令面板显示状态
  const [shortcutPanelVisible, setShortcutPanelVisible] = useState(false);
  // 响应式断点
  const screens = useBreakpoint();
  const isMobile = !screens.md; // md 以下认为是移动端

  // ⭐ 使用AppContext缓存API数据，避免重复调用
  const {
    sessionCount,
    serviceStatus,
    modelList,
    validationResult,
    initializeApp,
    refreshAll,
    refreshAfterModelChange,
    isInitialized,
  } = useApp();

  // 同步sessionCount到本地state（因为其他地方可能依赖sessionCount变量）
  const [_sessionCount, setSessionCount] = useState(0);
  useEffect(() => {
    setSessionCount(sessionCount);
  }, [sessionCount]);

  // 【修复问题1】检查服务状态 - 使用AppContext
  // 监听初始化状态，在初始化过程中显示loading
  const [checkingStatus, setCheckingStatus] = useState(false);
  // 【新增】手动刷新标志，避免自动重置
  const [isManualRefreshing, setIsManualRefreshing] = useState(false);
  // 【新增】验证错误弹框状态
  const [validationErrorModal, setValidationErrorModal] = useState<{
    visible: boolean;
    message: string;
    attemptedModel?: string; // 用户尝试切换的模型名称
  }>({ visible: false, message: "" });
  
  // 【新增】当前尝试切换的模型
  const [attemptedModel, setAttemptedModel] = useState<{
    provider: string;
    model: string;
    display_name: string;
  } | null>(null);

  // 初始化时同步设置checkingStatus
  useEffect(() => {
    // 【修复】只有在非手动刷新时才自动重置
    if (!isManualRefreshing) {
      if (!isInitialized) {
        setCheckingStatus(true);
      } else {
        setCheckingStatus(false);
      }
    }
  }, [isInitialized, isManualRefreshing]);

  // 【修复问题2】当前选中的模型ID（格式: provider-modelname）
  // 优先从 serviceStatus 获取（验证后的当前模型），如果没有则从 modelList 获取 current_model === true 的模型
  // 这样页面加载时也能正确显示当前配置的模型
  const currentProvider = (() => {
    // 如果有验证后的 serviceStatus，使用它
    if (serviceStatus?.provider && serviceStatus?.model) {
      return `${serviceStatus.provider}-${serviceStatus.model}`;
    }
    // 否则从 modelList 中找 current_model === true 的模型
    const currentModel = modelList.find(m => m.current_model === true);
    if (currentModel) {
      return `${currentModel.provider}-${currentModel.model}`;
    }
    // 如果都没有，返回空字符串
    return "";
  })();

  // 【新增】监听 serviceStatus 变化，当验证失败时显示弹框
  const lastServiceStatusRef = useRef<ValidateResponse | null>(null);
  
  useEffect(() => {
    // 检查 serviceStatus 是否发生变化
    const statusChanged = lastServiceStatusRef.current !== serviceStatus;
    lastServiceStatusRef.current = serviceStatus;
    
    // 只有当 serviceStatus 发生变化且验证失败时才显示弹框
    if (statusChanged && serviceStatus && !serviceStatus.success && serviceStatus.message) {
      // 显示验证错误弹框，包含尝试切换的新模型信息
      setValidationErrorModal({
        visible: true,
        message: serviceStatus.message,
        attemptedModel: attemptedModel ? `${attemptedModel.provider} (${attemptedModel.model})` : undefined,
      });
      // 2秒后自动关闭弹框
      const timer = setTimeout(() => {
        setValidationErrorModal({ visible: false, message: "" });
        setAttemptedModel(null); // 清除尝试切换的模型
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, [serviceStatus, attemptedModel]);

  // 切换模型后刷新serviceStatus
  const handleModelChange = async (value: string) => {
    try {
      const selectedModel = modelList.find(
        (m) => `${m.provider}-${m.model}` === value
      );
      if (!selectedModel) {
        message.error("未找到对应的模型");
        return;
      }
      console.log("[切换模型] 开始切换:", selectedModel.provider, selectedModel.model);
      // 【新增】记录尝试切换的模型
      setAttemptedModel({
        provider: selectedModel.provider,
        model: selectedModel.model,
        display_name: selectedModel.display_name,
      });
      
      const result = await configApi.updateConfig({
        ai_provider: selectedModel.provider,
        ai_model: selectedModel.model,
      });
      console.log("[切换模型] API返回:", result);
      if (!result.success) {
        message.error(result.message || "切换失败");
        return;
      }
      message.success(`已切换到 ${selectedModel.display_name}`);
      console.log("[切换模型] 开始刷新模型列表...");
      // 只刷新模型列表，不调用验证（验证由用户手动点击"检查服务"按钮）
      await refreshModelList();
      await refreshSessionCount();
      console.log("[切换模型] 刷新完成, serviceStatus:", serviceStatus);
    } catch (error: any) {
      console.error("[切换模型] 失败:", error);
      message.error(error?.response?.data?.detail || error?.message || "切换模型失败");
    }
  };

  // 【新增】验证详情弹框
  const [validationModalVisible, setValidationModalVisible] = useState(false);

  // 【修复】刷新模型列表 - 使用AppContext的refreshAll
  const refreshModelList = async () => {
    await refreshAll();
  };

  // 手动检查服务 - 使用AppContext刷新数据
  const handleCheckService = async () => {
    setCheckingStatus(true);
    setIsManualRefreshing(true);  // 设置手动刷新标志
    try {
      await refreshAll();
    } finally {
      setCheckingStatus(false);
      setIsManualRefreshing(false);  // 重置手动刷新标志
    }
  };

  // 页面加载时初始化 - 使用AppContext
  useEffect(() => {
    initializeApp();
  }, []);

  /**
   * 导航菜单配置
   *
   * 注意：disabled项表示功能预留，待后续开发
   */
  const menuItems: MenuItem[] = [
    {
      key: "/",
      icon: <MessageOutlined />,
      label: (
        <Badge count={unreadCount} size="small" offset={[6, -4]}>
          <span>对话任务</span>
        </Badge>
      ),
    },
    {
      key: "/files",
      icon: <FolderOutlined />,
      label: "文件管理",
      disabled: true,
    },
    {
      key: "/knowledge",
      icon: <BookOutlined />,
      label: (
        <Tooltip title="即将上线" placement="right">
          <span style={{ opacity: 0.6 }}>知识库</span>
        </Tooltip>
      ),
      disabled: true,
    },
    { type: "divider" },
    {
      key: "/history",
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
      key: "/shortcuts",
      icon: <ThunderboltOutlined />,
      label: "快捷指令",
    },
    { type: "divider" },
    {
      key: "/settings",
      icon: <SettingOutlined />,
      label: "系统设置",
    },
  ];

  /**
   * 菜单点击处理
   *
   * 功能：使用React Router进行页面导航
   *
   * @author 小新
   */
  const handleMenuClick: MenuProps["onClick"] = (e) => {
    const key = e.key;
    // 快捷指令特殊处理
    if (key === "/shortcuts") {
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
      case "/clear":
        // 清空当前对话
        console.log("清空对话");
        break;
      case "/help":
        // 显示帮助
        console.log("显示帮助");
        break;
      case "/history":
        // 跳转到历史记录
        navigate("/history");
        break;
      case "/settings":
        // 跳转到设置
        navigate("/settings");
        break;
      default:
        console.log("执行快捷指令:", command);
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
          display: "flex",
          alignItems: "center",
          justifyContent: isMobile || collapsed ? "center" : "flex-start",
          padding: isMobile || collapsed ? 0 : "0 16px",
          borderBottom: "1px solid #f0f0f0",
        }}
      >
        <Avatar
          size={40}
          icon={<DesktopOutlined />}
          style={{ background: "#1890ff", flexShrink: 0 }}
        />
        {!isMobile && !collapsed && (
          <Title
            level={5}
            style={{
              margin: "0 0 0 12px",
              fontSize: 16,
              fontWeight: 600,
              color: "#1890ff",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
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
          paddingTop: 12,
          paddingBottom: 12,
        }}
      />

      {/* 底部信息 - 前端小新代修改 VIS-L04: 优化底部信息, UX-L04: 添加点击查看版本详情 */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          padding: "16px 20px",
          borderTop: "1px solid #e8e8e8",
          fontSize: 13,
          color: "#666",
          background: "#fafafa",
          textAlign: isMobile || collapsed ? "center" : "left",
          cursor: "pointer",
          transition: "background 0.3s ease",
        }}
        onClick={() => message.info("OmniAgentAst v2.1.0 - 桌面版AI助手")}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "#f0f0f0";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "#fafafa";
        }}
      >
        {isMobile || collapsed ? "v2.1" : "版本 v2.1.0"}
      </div>
    </>
  );

  return (
    <Layout style={{ minHeight: "100vh" }}>
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
          styles={{ body: { padding: 0 } }}
        >
          {renderNavContent()}
        </Drawer>
      ) : (
        /* 桌面端：左侧导航栏 - 前端小新代修改 VIS-L02: 220px→180px */
        <Sider
          width={180}
          theme="light"
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          style={{
            boxShadow: "2px 0 8px rgba(0,0,0,0.05)",
            zIndex: 100,
          }}
        >
          {renderNavContent()}
        </Sider>
      )}

      {/* 右侧内容区 */}
      <Layout>
        {/* 顶部Header - 前端小新代修改 VIS-L03: 固定Header高度64px */}
        <Header
          style={{
            height: 43,
            background: "#fff",
            boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
            padding: isMobile ? "0 16px" : "0 20px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            zIndex: 99,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
            {/* 移动端菜单按钮 - 前端小新代修改 UX-L02: 增大按钮尺寸，添加tooltip */}
            {isMobile && (
              <Tooltip title="打开导航菜单">
                <Button
                  type="text"
                  icon={<MenuOutlined />}
                  onClick={() => setDrawerVisible(true)}
                  style={{ fontSize: 20, padding: "8px 12px" }}
                />
              </Tooltip>
            )}
            <Title
              level={4}
              style={{
                margin: 0,
                fontWeight: 500,
                fontSize: isMobile ? 16 : 18,
              }}
            >
              对话与任务
            </Title>
            {/* 服务状态显示 - 根据检查结果显示不同颜色 - 前端小新代修改 UX-L03: 可点击重试 */}
            {checkingStatus ? (
              <span style={{ color: "#999" }}>检查中...</span>
            ) : serviceStatus?.success ? (
              // ✅ 成功 或 🚨 警告（暂时可用）
              <Tag color={serviceStatus.status === "warning" ? "warning" : "success"}>
                <CheckCircleOutlined /> {serviceStatus.provider}{" "}
                {serviceStatus.model && `(${serviceStatus.model})`}
                {serviceStatus.status === "warning" && <span style={{ marginLeft: 4, fontSize: 11 }}>⚠️</span>}
              </Tag>
            ) : serviceStatus && !serviceStatus.success ? (
              // ❌ 失败时，显示配置文件中的模型名称（错误信息通过弹框显示）
              <Tag
                color="error"
                onClick={handleCheckService}
                style={{ cursor: "pointer" }}
              >
                <CheckCircleOutlined /> {serviceStatus.provider}{" "}
                {serviceStatus.model && `(${serviceStatus.model})`}
                <span style={{ marginLeft: 8, fontSize: 12 }}>(已失效)</span>
              </Tag>
            ) : (
              // serviceStatus为null时，显示配置文件中的当前模型（未验证状态）
              (() => {
                const currentModel = modelList.find(m => m.current_model === true);
                if (currentModel) {
                  return (
                    <Tag
                      color="default"
                      onClick={handleCheckService}
                      style={{ cursor: "pointer" }}
                    >
                      <CheckCircleOutlined /> {currentModel.provider}{" "}
                      ({currentModel.model})
                      <span style={{ marginLeft: 8, fontSize: 12 }}>(未验证)</span>
                    </Tag>
                  );
                }
                return (
                  <Tag
                    color="error"
                    onClick={handleCheckService}
                    style={{ cursor: "pointer" }}
                  >
                    未配置 (点击检查)
                  </Tag>
                );
              })()
            )}
            {/* 【新增】配置验证警告 - 当validationResult有错误或警告时显示 */}
            {validationResult &&
              (!validationResult.success ||
                (validationResult.warnings &&
                  validationResult.warnings.length > 0)) && (
                <Tag
                  color="warning"
                  style={{ cursor: "pointer" }}
                  onClick={() => setValidationModalVisible(true)}
                >
                  ⚠️ 配置验证
                </Tag>
              )}
          </div>

          {/* 右侧操作区 */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            {/* 模型选择下拉框 */}
            {modelList.length > 0 ? (
              <Select
                value={currentProvider}
                style={{ minWidth: 350 }}
                styles={{ popup: { root: { minWidth: 350 } } }}
                size="small"
                // 【新增】打开下拉框时刷新模型列表，获取最新配置
                onOpenChange={async (open: boolean) => {
                  if (open) {
                    await refreshModelList();
                  }
                }}
onChange={handleModelChange}
              >
                {modelList.map((model) => (
                  <Option
                    key={model.id}
                    value={`${model.provider}-${model.model}`}
                  >
                    {model.current_model === true ? "★ " : ""}
                    {model.display_name}
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
            <span style={{ color: "#666", fontSize: 14 }}>用户</span>
          </div>
        </Header>

        {/* 主内容区 - 只有这层有留白 - 前端小新代修改 VIS-L01: 留白优化, VIS-G02: 背景色优化 */}
        {/* 
          📝 留白调整说明（修改这里调整 Card 组件与外边框的间距）：
          padding: "上 右 下 左"
          - 上：Card 与顶部标题栏的间距（当前值：6px）
          - 右：Card 与右侧边框的间距（当前值：6px）
          - 下：Card 与底部边框的间距（当前值：10px）
          - 左：Card 与左侧菜单的间距（当前值：6px）
        */}
        <Content
          style={{
            margin: 0,
            padding: "6px 6px 10px 6px",
            background: "#f8fafc",
            borderRadius: 12,
            minHeight: 400,
            overflow: "auto",
          }}
        >
          {children}
        </Content>
      </Layout>

      {/* 【新增】配置验证详情弹框 */}
      <Modal
        title="配置验证详情"
        open={validationModalVisible}
        onCancel={() => setValidationModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setValidationModalVisible(false)}>
            关闭
          </Button>,
          <Button
            key="settings"
            type="primary"
            onClick={() => {
              setValidationModalVisible(false);
              navigate("/settings");
            }}
          >
            去设置
          </Button>,
        ]}
        width={600}
      >
        {validationResult && (
          <div>
            <Alert
              message={validationResult.message}
              type={validationResult.success ? "success" : "error"}
              showIcon
              style={{ marginBottom: 16 }}
            />

            {validationResult.errors && validationResult.errors.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ color: "#ff4d4f" }}>
                  错误 ({validationResult.errors.length})
                </h4>
                <ul style={{ paddingLeft: 20, color: "#ff4d4f" }}>
                  {validationResult.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {validationResult.warnings &&
              validationResult.warnings.length > 0 && (
                <div>
                  <h4 style={{ color: "#faad14" }}>
                    警告 ({validationResult.warnings.length})
                  </h4>
                  <ul style={{ paddingLeft: 20, color: "#faad14" }}>
                    {validationResult.warnings.map((warn, idx) => (
                      <li key={idx}>{warn}</li>
                    ))}
                  </ul>
                </div>
              )}
          </div>
        )}
      </Modal>

      {/* 【新增】验证错误弹框 - 2秒后自动关闭 */}
      <Modal
        title="模型验证失败"
        open={validationErrorModal.visible}
        onCancel={() => setValidationErrorModal({ visible: false, message: "" })}
        footer={[
          <Button
            key="close"
            type="primary"
            onClick={() => setValidationErrorModal({ visible: false, message: "" })}
          >
            关闭
          </Button>,
        ]}
        width={500}
      >
        <Alert
          message={validationErrorModal.attemptedModel 
            ? `尝试切换到 ${validationErrorModal.attemptedModel} 失败` 
            : "模型验证失败"}
          description={validationErrorModal.message}
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
        <p>配置文件中的模型可能无法正常工作，请检查配置或稍后重试。</p>
        <p style={{ marginTop: 8, color: '#666' }}>
          注意：系统已自动回退到配置文件中的可用模型。
        </p>
      </Modal>
    </Layout>
  );
};

export default AppLayout;
