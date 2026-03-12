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

import React, { useState, useEffect } from "react";
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
import { configApi, chatApi, sessionApi } from "../../services/api";
import type { MenuProps } from "antd";
const { Option } = Select;
import ShortcutPanel from "../ShortcutPanel";

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
  // ⭐ 修复：会话数量 - 从后端获取真实值
  const [sessionCount, setSessionCount] = useState(0);
  // 导航折叠状态
  const [collapsed, setCollapsed] = useState(false);
  // 移动端抽屉显示状态
  const [drawerVisible, setDrawerVisible] = useState(false);
  // 快捷指令面板显示状态
  const [shortcutPanelVisible, setShortcutPanelVisible] = useState(false);
  // 响应式断点
  const screens = useBreakpoint();
  const isMobile = !screens.md; // md 以下认为是移动端

  // ⭐ 新增：加载会话数量（用于菜单角标显示）
  useEffect(() => {
    const loadSessionCount = async () => {
      try {
        console.log("🔍 开始加载会话数量...");
        const response = await sessionApi.listSessions(1, 1, undefined, true); // ⭐ 只加载有效会话
        console.log("📊 会话数量响应:", response);
        setSessionCount(response.total);
        console.log("✅ 会话数量设置为:", response.total);
      } catch (error) {
        console.error("❌ 加载会话数量失败:", error);
        // 失败时显示 0，避免误导
        setSessionCount(0);
      }
    };

    loadSessionCount();
  }, []);

  // 【新增】检查服务状态
  const [serviceStatus, setServiceStatus] = useState<{
    success: boolean;
    message: string;
    provider: string;
    model: string;
  } | null>(null);
  const [checkingStatus, setCheckingStatus] = useState(false);
  // 【修改】当前选中的模型ID（格式: provider-modelname）
  const [_currentProvider, setCurrentProvider] = useState<string>(
    "opencode-minimax-m2.5-free"
  );
  // 【修改】模型列表 - 类型匹配后端返回（id, provider, model, display_name, current_model）
  const [modelList, setModelList] = useState<
    {
      id: number;
      provider: string;
      model: string;
      display_name: string;
      current_model: boolean;
    }[]
  >([]);

  // 【新增】完整配置验证结果
  const [validationResult, setValidationResult] = useState<{
    success: boolean;
    provider: string;
    model: string;
    message: string;
    errors: string[];
    warnings: string[];
  } | null>(null);
  // 【新增】验证详情弹框
  const [validationModalVisible, setValidationModalVisible] = useState(false);

  // 【修复】刷新模型列表 - 同时刷新验证状态
  const refreshModelList = async () => {
    try {
      // 同时刷新验证状态
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (err) {
        console.warn("刷新验证状态失败:", err);
      }

      const modelData = await configApi.getModelList();
      if (modelData.models) {
        setModelList(modelData.models);
      }
    } catch (error) {
      console.warn("刷新模型列表失败:", error);
    }
  };

  // 手动检查服务
  const handleCheckService = async () => {
    setCheckingStatus(true);
    try {
      // 【修复】同时刷新验证状态和模型列表
      try {
        const validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (err) {
        console.warn("刷新验证状态失败:", err);
      }

      const modelData = await configApi.getModelList();

      // 更新模型列表
      if (modelData.models) {
        setModelList(modelData.models);
      }

      // 更新当前选中的模型 - 直接使用后端返回的current_model字段
      if (modelData.models && modelData.models.length > 0) {
        const currentModel = modelData.models.find(
          (m) => m.current_model === true
        );
        if (currentModel) {
          // 使用id（数字类型），转为字符串保持一致
          setCurrentProvider(`${currentModel.provider}-${currentModel.model}`); // 2b50 4fee590dFf1a4f7f7528 provider-model 683c5f0f
        }
      }

      // 检查服务状态
      const status = await chatApi.validateService();
      setServiceStatus(status);
    } catch (error) {
      console.warn("服务检查失败:", error);
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
        // 【修复】先调用完整配置验证，获取所有配置项的验证结果
        let validation = null;
        try {
          validation = await configApi.validateFullConfig();
          setValidationResult(validation);
        } catch (err) {
          console.warn("配置验证失败:", err);
          // 验证失败时设置空结果，补全所有字段
          const errorResult = {
            success: false,
            provider: "",
            model: "",
            message: "配置验证接口调用失败",
            errors: ["配置验证接口调用失败"],
            warnings: [] as string[],
          };
          setValidationResult(errorResult);
          validation = errorResult;
        }

        // 【修复】根据验证结果决定是否获取模型列表
        // 设计文档要求：验证失败时不获取列表或显示空列表
        if (!validation || !validation.success) {
          setModelList([]);
          setCheckingStatus(false);
          return;
        }

        // 验证成功才获取模型列表
        const modelData = await configApi.getModelList();

         // 设置模型列表
         if (modelData.models && modelData.models.length > 0) {
           setModelList(modelData.models);

          // 设置当前选中的模型 - 直接使用后端返回的 current_model 字段
          const currentModel = modelData.models.find(
            (m) => m.current_model === true
          );
          if (currentModel) {
            setCurrentProvider(
              `${currentModel.provider}-${currentModel.model}`
            ); // 2b50 4fee590dFf1a4f7f7528 provider-model 683c5f0f
          }
        }

        // 检查服务状态
        const status = await chatApi.validateService();
        setServiceStatus(status);
      } catch (error) {
        console.warn("初始化失败:", error);
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
              <Tag color="success">
                <CheckCircleOutlined /> {serviceStatus.provider}{" "}
                {serviceStatus.model && `(${serviceStatus.model})`}
              </Tag>
            ) : serviceStatus?.message ? (
              // 有错误信息显示红色/黄色（根据错误类型），可点击重试
              <Tag
                color={
                  serviceStatus.message.includes("限速") ||
                  serviceStatus.message.includes("欠费") ||
                  serviceStatus.message.includes("额度")
                    ? "warning"
                    : "error"
                }
                onClick={handleCheckService}
                style={{ cursor: "pointer" }}
              >
                {serviceStatus.provider}{" "}
                {serviceStatus.model && `(${serviceStatus.model})`} -{" "}
                {serviceStatus.message} (点击重试)
              </Tag>
            ) : (
              // 未配置或初始状态，可点击检查
              <Tag
                color="error"
                onClick={handleCheckService}
                style={{ cursor: "pointer" }}
              >
                未配置 (点击检查)
              </Tag>
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
                value={_currentProvider}
                style={{ minWidth: 350 }}
                styles={{ popup: { root: { minWidth: 350 } } }}
                size="small"
                // 【新增】打开下拉框时刷新模型列表，获取最新配置
                onOpenChange={async (open: boolean) => {
                  if (open) {
                    await refreshModelList();
                  }
                }}
                onChange={async (value: string) => {
                  try {
                    // 从modelList中找到对应的模型，获取完整的provider和model
                    const selectedModel = modelList.find(
                      (m) => `${m.provider}-${m.model}` === value
                    );
                    if (!selectedModel) {
                      message.error("未找到对应的模型");
                      return;
                    }

                    // ⭐⭐⭐ 重要：provider 和 model 必须成对使用！⭐⭐⭐
                    // 从 selectedModel 中同时获取 provider 和 model
                    // 原因：同一个 model 名称可能属于多个 provider
                    // 只有 provider+model 组合才能唯一确定一个模型
                    const modelName = selectedModel.model; // 直接使用 selectedModel.model

                    // 调用API切换provider和model
                    await configApi.updateConfig({
                      ai_provider: selectedModel.provider, // ⭐ 删除类型断言，使用字符串
                      ai_model: modelName,
                    });
                    message.success(`已切换到 ${selectedModel.display_name}`);

                    // 切换后更新当前选中的模型ID
                    setCurrentProvider(value);

                    // 切换后自动检查服务
                    handleCheckService();
                  } catch (error) {
                    message.error("切换失败");
                  }
                }}
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
    </Layout>
  );
};

export default AppLayout;
