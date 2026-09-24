// 编辑历史: 2026-02-17 小新 - 创建Layout组件(左右分栏+响应式)
// 编辑历史: 2026-02-18 小新 - 添加移动端响应式支持
// 编辑历史: 2026-08-22 小欧 - model结构化归一: updateConfig改传ai_model_ref结构; serviceStatus的provider/model读取点改经status.model_ref派生
// 编辑历史: 2026-08-27 小欧 - 修复#31: serviceStatus.success→valid字段名对齐后端返回
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: 删_sessionCount死状态/refreshModelList透传/unreadCount死值; 精简console.log; Option上移; 更正Header高度注释
// 2026-08-27 小欧 - 三堂会审: #1890ff→#1677ff(头像背景/标题); 删5处console.log调试语句
// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复注释行尾多余空白, 防止格式再次出错
// 编辑历史: 2026-09-08 小欧 - 删顶部模型状态指示Tag(北京老陈令): 右侧已有独立模型Select+检查按钮, 左侧Tag功能完全冗余, 删除更简洁 — 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 删左侧Logo区Avatar(北京老陈令): 顶部仅保留文字标识"OmniAgentAst.", 更简洁 — 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 标题图标化(北京老陈令): 顶部"对话与任务"文字换D三色弧段loader(蓝绿橙, 与 title-icon-compare.html 的D三色版一致),
//   复用 waiting-spin 逆时针1s常转, Tooltip 保留原标题; Title 组件仍被 Logo 区使用, import 保留 — 小欧-2026-09-08
// 编辑历史: 2026-09-20 小强 - 侧边"系统设置"菜单/快捷跳转由 /settings 切换为 /settings2(设置2版: 6Tab+模型管理) — 小强-2026-09-20
// 2026-09-21 小欧 - 旧设置页整体退休: 配置验证弹窗"去设置"跳转由 /settings 改 /settings2(旧页路由已移除)
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-A类: 去refreshAll解构; isManualRefreshing改[,setIsManualRefreshing]
//   (保留setter调用防死状态:131注释, 仅弃读值) — 小欧-2026-09-09
// 编辑历史: 2026-09-15 小欧 - 左侧Logo图形化+品牌文字移位(北京老陈令): ①删左侧Logo区文字Title,
//   换嗅title-icon-compare 70号斜向波浪3x3九色点阵(SVG36x36, gridwave动画); ②"OmniAgentAst."文字移右侧顶栏
//   动画圈圈(title-spin-icon)之后(brand-title-text); ③Title组件随Logo区文字删除不再使用, 保留import防他处引用破坏 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 10大规范自查整改: ①删Typography/Title死import(禁止backward); ②9个rect抽
//   LOGO_GRID_CELLS常量数组+map迭代渲染(DRY); ③行内width/height冗余删除由CSS定义(DRY) — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 动画图标抽离(北京老陈令): 左侧Logo点阵+右侧顶栏圈圈两段内联SVG统一移入
//   新建 AnimatedIcons/index.tsx(LogoGridIcon/TitleSpinIcon, 数据+渲染随组件走), Layout改import引用, LOGO_GRID_CELLS随组件移走 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 折叠后Logo不显示修复+菜单栏优化落地(北京老陈令): ①折叠态Logo渲染条件去!collapsed(容器居中展示);
//   ②[38]4.1 Logo区高度64→43与Topbar Header对齐; ③[38]4.2 Logo包Tooltip"OmniAgentAst"(折叠态可识别);
//   ④[38]4.3 disabled项统一为"即将上线"预留样式(文件管理与知识库一致, opacity0.6+Tooltip);
//   ⑤[38]4.4 展开态Logo左缘对齐菜单图象标中心(padding 5px); ⑥菜单栏默认折叠(useState true, 北京老陈令) — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 折叠态Tooltip黑框无字修复(北京老陈反馈): 折叠时AntD自动Tooltip取label文本,
//   label为JSX(Badge/Tooltip包裹)取不到字符串→黑框无字, 所有菜单项显式加title字符串兜底 — 小欧-2026-09-15
// 编辑历史: 2026-09-21 小强 - 顶栏Header优化: ①删写-only死状态isManualRefreshing(值从未被读, 收尾09-09半删YAGNI);
//   ②配置验证Tag emoji改WarningOutlined(7.9.4禁emoji); ③#fff/fontSize14/gap12→Colors.BG.PRIMARY/FontSize.PRIMARY/Spacing.LG令牌零视觉差 — 小强-2026-09-21
// 编辑历史: 2026-09-21 小强 - DRY收口: handleModelChange改经configApi.switchCurrentModel共用切全局模型唯一写链(去本地装配ai_model_ref) — 小强-2026-09-21
// 编辑历史: 2026-09-24 19:15:07 小欧 - DRY收口: handleModelChange改经AppContext.switchAndRefreshModel(API+刷新收口), 删configApi直调与手动refreshAfterModelChange — 小欧-2026-09-24
/**
 * Layout组件 - 应用主布局（响应式版）
 *
 * 功能：左右分栏布局，左侧导航栏，右侧内容区，支持移动端响应式
 *
 * @author 小新
 * @version 1.1.0
 * @since 2026-02-17
 * @update 2026-02-18 添加移动端响应式支持
 * @update 2026-08-22 小欧 - model结构化归一报告v1.25/v1.26 6.6 方案B(前端随后端修改): updateConfig 改传 ai_model_ref 结构; serviceStatus 的 provider/model 读取点(4处)改经 status.model_ref 派生
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layout,
  Menu,
  Avatar,
  Badge,
  Tooltip,
  Drawer,
  Button,
  Grid,
  Tag,
  Select,
  Modal,
  Alert,
} from 'antd';
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
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { ValidateResponse } from '../../services/api/chat.api';
import type { MenuProps } from 'antd';
import ShortcutPanel from '../ShortcutPanel';
import { LogoGridIcon, TitleSpinIcon } from '../AnimatedIcons';
import { useApp } from '../../contexts/AppContext';
import { LayoutSkeleton } from '../Skeleton';
import { Colors, FontSize, Spacing } from '../../utils/stepStyles';
import {
  handleError,
  showSuccess,
  showMessage,
  ErrorType,
} from '@/services/error/handler';
// import useInitializationProgress from "../../hooks/useInitializationProgress"; // 步骤9预留

const { useBreakpoint } = Grid;

const { Option } = Select;
const { Sider, Content, Header } = Layout;

// 2026-08-27 小欧 三堂会审B32: 版本号统一定义(DRY), 避免硬编码散落多处
const APP_VERSION = 'v2.1.0';

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
  // 导航折叠状态
  // 2026-09-15 小欧 - 默认折叠(北京老陈令): useState初始true, 用户可手动展开 — 小欧-2026-09-15
  const [collapsed, setCollapsed] = useState(true);
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
    refreshServiceStatus,
    switchAndRefreshModel,
    refreshModelList: appRefreshModelList, // 获取AppContext的refreshModelList
    isInitialized,
    initError,
  } = useApp();

  // 2026-09-21 小强 - 删写-only死状态isManualRefreshing（值从未被读，只剩两次空转setState；YAGNI收尾09-09半删）
  // 【修复问题1】检查服务状态 - 使用AppContext
  // 监听初始化状态，在初始化过程中显示loading
  const [checkingStatus, setCheckingStatus] = useState(false);
  // 【新增】是否为首次初始化（首次不显示弹框）
  const isInitialLoadRef = useRef(true);
  // 【修改】验证错误弹框状态 - 支持三种状态
  const [validationErrorModal, setValidationErrorModal] = useState<{
    visible: boolean;
    message: string;
    attemptedModel?: string; // 用户尝试切换的模型名称
    status?: 'success' | 'failed' | 'warning'; // 验证状态
    modelInfo?: string; // 模型信息 provider (model)
  }>({ visible: false, message: '' });

  // 【新增】骨架屏显示状态
  const [skeletonState, setSkeletonState] = useState<{
    visible: boolean;
    error?: string;
  }>({ visible: true });

  // 【新增】当前尝试切换的模型
  const [attemptedModel, setAttemptedModel] = useState<{
    provider: string;
    model: string;
    display_name: string;
  } | null>(null);

  // 初始化时同步设置checkingStatus
  useEffect(() => {
    if (!isInitialized) {
      setCheckingStatus(true);
    } else {
      setCheckingStatus(false);
    }
  }, [isInitialized]);

  // 【修正】骨架屏切换：监听isInitialized完成后延迟100ms切换
  // 或监听initError使用errorHandler统一处理错误
  useEffect(() => {
    // 初始化成功，延迟切换到实际内容
    if (isInitialized && skeletonState.visible && !initError) {
      const timer = setTimeout(() => {
        setSkeletonState({ visible: false });
      }, 100);
      return () => clearTimeout(timer);
    }

    // 初始化失败，使用errorHandler统一处理错误
    if (initError && skeletonState.visible) {
      // 使用errorHandler统一错误处理中心显示错误提示+重试按钮
      handleError(
        {
          message: initError,
          error_type: ErrorType.LOAD_FAILED,
        },
        {
          source: 'manual',
          onRetry: () => handleSkeletonRetry(),
        }
      );
      // 不在骨架屏显示错误，由errorHandler统一处理
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInitialized, skeletonState.visible, initError]);

  // 【新增】骨架屏重试函数 - 用于加载失败时重试
  const handleSkeletonRetry = useCallback(async () => {
    setSkeletonState({ visible: true, error: undefined });
    await initializeApp();
  }, [initializeApp]);

  // 【修复问题2】当前选中的模型ID（格式: provider-modelname）
  // 【2026-04-07修复】切换模型后不再调用refreshServiceStatus，所以必须优先从modelList获取
  const currentProvider = (() => {
    // 优先从 modelList 中找 current_model === true 的模型（切换模型后这里会更新）
    const currentModel = modelList.find((m) => m.current_model === true);
    if (currentModel) {
      return `${currentModel.provider}-${currentModel.model}`;
    }
    // 其次从 serviceStatus 获取（验证后的当前模型）— 归一: model_ref 结构派生(方案B 前端随后端) — 小欧 2026-08-22
    if (serviceStatus?.model_ref?.provider && serviceStatus?.model_ref?.model) {
      return `${serviceStatus.model_ref.provider}-${serviceStatus.model_ref.model}`;
    }
    // 如果都没有，返回空字符串
    return '';
  })();

  // 【修改】监听 serviceStatus 变化，显示三种状态的弹框说明
  const lastServiceStatusRef = useRef<ValidateResponse | null>(null);

  useEffect(() => {
    // 【修复】首次初始化时不显示弹框（避免初始化和手动刷新重复弹框）
    if (isInitialLoadRef.current) {
      isInitialLoadRef.current = false;
      return;
    }

    // 检查 serviceStatus 是否发生变化（比较关键字段避免引用不等导致重复弹窗）
    // 编辑历史: 2026-08-28 老杨 - [26] 引用比较改为深比较关键字段valid/status，避免每次新对象即true
    const statusChanged =
      lastServiceStatusRef.current?.valid !== serviceStatus?.valid ||
      lastServiceStatusRef.current?.status !== serviceStatus?.status ||
      lastServiceStatusRef.current?.message !== serviceStatus?.message;
    lastServiceStatusRef.current = serviceStatus;

    // 只有当 serviceStatus 发生变化且有消息时才显示弹框
    if (statusChanged && serviceStatus && serviceStatus.message) {
      // 获取模型信息 — 归一: model_ref 结构派生 — 小欧 2026-08-22
      const modelInfo = serviceStatus.model_ref
        ? `${serviceStatus.model_ref.provider} (${serviceStatus.model_ref.model})`
        : '';

      // 根据状态类型显示不同的弹框内容
      if (serviceStatus.status === 'warning') {
        // 🚨 警告状态
        setValidationErrorModal({
          visible: true,
          message: serviceStatus.message,
          attemptedModel: undefined,
          status: 'warning',
          modelInfo: modelInfo,
        });
      } else if (!serviceStatus.valid) {
        // 2026-08-27 小欧 修复#31: ValidateResponse.valid(后端返回valid)
        // ❌ 失败状态
        setValidationErrorModal({
          visible: true,
          message: serviceStatus.message,
          attemptedModel: attemptedModel
            ? `${attemptedModel.provider} (${attemptedModel.model})`
            : undefined,
          status: 'failed',
          modelInfo: modelInfo,
        });
      } else if (serviceStatus.valid && serviceStatus.status === 'success') {
        // ✅ 成功状态 - 也显示弹框说明
        setValidationErrorModal({
          visible: true,
          message: serviceStatus.message,
          attemptedModel: undefined,
          status: 'success',
          modelInfo: modelInfo,
        });
      }

      // 2秒后自动关闭弹框（成功状态1.5秒）
      const timer = setTimeout(
        () => {
          setValidationErrorModal({ visible: false, message: '' });
          setAttemptedModel(null); // 清除尝试切换的模型
        },
        serviceStatus.status === 'success' ? 1500 : 2000
      );
      return () => clearTimeout(timer);
    }
  }, [serviceStatus, attemptedModel]);

  // 切换模型后刷新serviceStatus
  // 【小强修复 2026-03-31】修复setServiceStatus未定义错误，改用AppContext的action函数
  const handleModelChange = async (value: string) => {
    try {
      const selectedModel = modelList.find(
        (m) => `${m.provider}-${m.model}` === value
      );
      if (!selectedModel) {
        handleError({
          message: '未找到对应的模型',
          error_type: ErrorType.LOAD_FAILED,
        });
        return;
      }
      // 【新增】记录尝试切换的模型
      setAttemptedModel({
        provider: selectedModel.provider,
        model: selectedModel.model,
        display_name: selectedModel.display_name,
      });

      // 归一(小欧 2026-08-22 报告v1.25 6.6 方案B): ai_provider/ai_model → ai_model_ref 结构
      // 2026-09-24 小欧 - DRY收口: 改经switchAndRefreshModel(API+成功/失败刷新收口), 不再直调configApi+手动refreshAfterModelChange
      const result = await switchAndRefreshModel(
        selectedModel.provider,
        selectedModel.model
      );
      if (!result.success) {
        handleError({
          message: result.message || '切换失败',
          error_type: ErrorType.SWITCH_MODEL_FAILED,
        });
        // 切换失败时switchAndRefreshModel内部已刷新模型列表(后端回滚后状态), 此处只管展示
        return;
      }
      showSuccess(`已切换到 ${selectedModel.display_name}`);
    } catch (error: unknown) {
      const err = error as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      console.error('[切换模型] 失败:', error);
      handleError({
        message: err?.response?.data?.detail || err?.message || '切换模型失败',
        error_type: ErrorType.SWITCH_MODEL_FAILED,
      });
    }
  };

  // 【新增】验证详情弹框
  const [validationModalVisible, setValidationModalVisible] = useState(false);

  // 手动检查服务
  const handleCheckService = async () => {
    setCheckingStatus(true);
    try {
      const status = await refreshServiceStatus();
      // 归一: model_ref 结构派生 — 小欧 2026-08-22
      if (status && status.valid) {
        showMessage(
          ErrorType.INFO,
          `${status.model_ref?.provider || '未知'} (${status.model_ref?.model || '未知'}) 服务连接正常`
        );
      } else {
        showMessage(
          ErrorType.WARNING,
          `${status?.model_ref?.provider || '未知'} (${status?.model_ref?.model || '未知'}) 验证失败: ${status?.message || '请检查配置'}`
        );
      }
    } catch {
      showMessage(ErrorType.WARNING, '服务验证失败，请检查网络连接');
    } finally {
      setCheckingStatus(false);
    }
  };

  // 页面加载时初始化 - 使用AppContext
  // 【2026-04-08修复】页面加载不调用服务检查，与会话加载无关
  useEffect(() => {
    initializeApp();
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
      // 2026-09-15 小欧 - 折叠态Tooltip文字修复: label为JSX(Badge包裹)AntD取不到字符串→黑框无字,
      //   显式title兜底(折叠自动tooltip用title文本) — 小欧-2026-09-15
      title: '对话任务',
      label: (
        <Badge size="small" offset={[6, -4]}>
          <span>对话任务</span>
        </Badge>
      ),
    },
    {
      key: '/files',
      icon: <FolderOutlined />,
      title: '文件管理',
      // 2026-09-15 小欧 - [38]4.3 disabled项统一预留样式(与知识库一致): opacity0.6+Tooltip"即将上线" — 小欧-2026-09-15
      label: (
        <Tooltip title="即将上线" placement="right">
          <span style={{ opacity: 0.6 }}>文件管理</span>
        </Tooltip>
      ),
      disabled: true,
    },
    {
      key: '/knowledge',
      icon: <BookOutlined />,
      title: '知识库',
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
      title: '历史会话',
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
      title: '快捷指令',
      label: '快捷指令',
    },
    { type: 'divider' },
    {
      key: '/settings2',
      icon: <SettingOutlined />,
      title: '设置2版',
      label: '设置2版',
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
        break;
      case '/help':
        // 显示帮助
        break;
      case '/history':
        // 跳转到历史记录
        navigate('/history');
        break;
      case '/settings2':
        // 跳转到设置2版 — 小强 2026-09-20
        navigate('/settings2');
        break;
      default:
      // 执行快捷指令
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
          // 2026-09-15 小欧 - [38]4.1 高度64→43: 与顶栏Header(43px)纵向对齐, 三态统一 — 小欧-2026-09-15
          height: 43,
          display: 'flex',
          alignItems: 'center',
          justifyContent: isMobile || collapsed ? 'center' : 'flex-start',
          // 2026-09-15 小欧 - [38]4.4 展开态左缘5px(16px-11px): 使36px点阵中心对齐菜单项图标中心(图标14px距左16px),
          //   消除视觉偏左重心; 折叠/移动端仍居中 — 小欧-2026-09-15
          padding: isMobile || collapsed ? 0 : '0 5px',
          borderBottom: '1px solid #f0f0f0',
        }}
      >
        {!isMobile && (
          // 2026-09-15 小欧 - 左侧Logo图形化(北京老陈令选 title-icon-compare 70号斜向波浪):
          //   原文字"OmniAgentAst."移右侧顶栏动画圈圈之后, 此处放 AnimatedIcons/LogoGridIcon(3x3九色点阵, 组件内数据+渲染)
          //   2026-09-15 小欧 - 修复折叠后顶部Logo不显示: 原条件 !collapsed 使折叠态整块不渲染,
          //   容器折叠态 justify-content:center 正好居中展示点阵 — 小欧-2026-09-15
          // 2026-09-15 小欧 - [38]4.2 Logo包Tooltip"OmniAgentAst": 折叠态窄栏可识别品牌 — 小欧-2026-09-15
          <Tooltip title="OmniAgentAst" placement="right">
            <LogoGridIcon />
          </Tooltip>
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
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          padding: '16px 20px',
          borderTop: '1px solid #e8e8e8',
          fontSize: 13,
          color: '#666',
          background: '#fafafa',
          textAlign: isMobile || collapsed ? 'center' : 'left',
          cursor: 'pointer',
          transition: 'background 0.3s ease',
        }}
        onClick={() =>
          showMessage(
            ErrorType.INFO,
            `OmniAgentAst ${APP_VERSION} - 桌面版AI助手`
          )
        }
        onMouseEnter={(e) => {
          e.currentTarget.style.background = '#f0f0f0';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = '#fafafa';
        }}
      >
        {isMobile || collapsed ? APP_VERSION : `版本 ${APP_VERSION}`}
      </div>
    </>
  );

  return (
    <Layout style={{ height: '100vh', overflow: 'hidden' }}>
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
            boxShadow: '2px 0 8px rgba(0,0,0,0.05)',
            zIndex: 100,
          }}
        >
          {renderNavContent()}
        </Sider>
      )}

      {/* 右侧内容区 */}
      <Layout>
        {/* 顶部Header - 固定Header高度43px（与LayoutSkeleton一致） */}
        <Header
          style={{
            height: 43,
            // 2026-09-21 小强 - 令牌零视觉差：#fff=Colors.BG.PRIMARY
            background: Colors.BG.PRIMARY,
            boxShadow: '0 2px 8px rgba(0,0,0,0.05)',
            padding: isMobile ? '0 16px' : '0 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            zIndex: 99,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
            {/* 移动端菜单按钮 - 前端小新代修改 UX-L02: 增大按钮尺寸，添加tooltip */}
            {isMobile && (
              <Tooltip title="打开导航菜单">
                <Button
                  type="text"
                  icon={<MenuOutlined />}
                  onClick={() => setDrawerVisible(true)}
                  style={{ fontSize: 20, padding: '8px 12px' }}
                />
              </Tooltip>
            )}
            {/* 2026-09-08 小欧 - 标题图标化(北京老陈令): "对话与任务"文字换D三色弧段loader(蓝绿橙),
                与对比页 title-icon-compare.html 的 D 三色版一致, 1s逆时针常转; Tooltip 保留原标题, 无障碍 — 小欧-2026-09-08
                2026-09-15 小欧 - 内联SVG抽离至 AnimatedIcons/TitleSpinIcon — 小欧-2026-09-15 */}
            <Tooltip title="对话与任务" placement="bottom">
              <TitleSpinIcon />
            </Tooltip>
            {/* 2026-09-15 小欧 - 品牌文字移此(北京老陈令): 左侧文字Logo挪到动画圈圈之后, 字号/粗细/色与左侧一致 — 小欧-2026-09-15 */}
            <span className="brand-title-text" aria-label="OmniAgentAst">
              OmniAgentAst.
            </span>
            {/* 【新增】配置验证警告 - 当validationResult有错误或警告时显示 */}
            {/* 2026-09-21 小强 - emoji禁令(7.9.4)：⚠️改WarningOutlined图标 */}
            {validationResult &&
              (!validationResult.success ||
                (validationResult.warnings &&
                  validationResult.warnings.length > 0)) && (
                <Tag
                  color="warning"
                  icon={<WarningOutlined />}
                  style={{ cursor: 'pointer' }}
                  onClick={() => setValidationModalVisible(true)}
                >
                  配置验证
                </Tag>
              )}
          </div>

          {/* 右侧操作区 */}
          {/* 2026-09-21 小强 - 令牌零视觉差：gap 12=Spacing.LG */}
          <div
            style={{ display: 'flex', alignItems: 'center', gap: Spacing.LG }}
          >
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
                    await appRefreshModelList();
                  }
                }}
                onChange={handleModelChange}
              >
                {modelList.map((model) => (
                  <Option
                    key={model.id}
                    value={`${model.provider}-${model.model}`}
                  >
                    {model.current_model === true ? '★ ' : ''}
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
              disabled={checkingStatus}
              size="small"
            >
              检查服务
            </Button>
            <Avatar size="small" icon={<DesktopOutlined />} />
            {/* 2026-09-21 小强 - 令牌零视觉差：fontSize 14=FontSize.PRIMARY */}
            <span style={{ color: '#666', fontSize: FontSize.PRIMARY }}>
              用户
            </span>
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
            padding: '6px 6px 10px 6px',
            background: '#f8fafc',
            borderRadius: 12,
            minHeight: 0,
            flex: 1,
            overflow: 'auto',
          }}
        >
          {/* 【新增】骨架屏/实际内容切换 */}
          {skeletonState.visible ? <LayoutSkeleton /> : children}
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
              navigate('/settings2');
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
              type={validationResult.success ? 'success' : 'error'}
              showIcon
              style={{ marginBottom: 16 }}
            />

            {validationResult.errors && validationResult.errors.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <h4 style={{ color: '#ff4d4f' }}>
                  错误 ({validationResult.errors.length})
                </h4>
                <ul style={{ paddingLeft: 20, color: '#ff4d4f' }}>
                  {validationResult.errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {validationResult.warnings &&
              validationResult.warnings.length > 0 && (
                <div>
                  <h4 style={{ color: '#faad14' }}>
                    警告 ({validationResult.warnings.length})
                  </h4>
                  <ul style={{ paddingLeft: 20, color: '#faad14' }}>
                    {validationResult.warnings.map((warn, idx) => (
                      <li key={idx}>{warn}</li>
                    ))}
                  </ul>
                </div>
              )}
          </div>
        )}
      </Modal>

      {/* 【修改】验证结果弹框 - 显示三种状态的说明 */}
      <Modal
        title={
          <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {validationErrorModal.status === 'success' ? (
              <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 18 }} />
            ) : validationErrorModal.status === 'warning' ? (
              <ExclamationCircleOutlined
                style={{ color: '#faad14', fontSize: 18 }}
              />
            ) : (
              <CloseCircleOutlined style={{ color: '#ff4d4f', fontSize: 18 }} />
            )}
            {validationErrorModal.status === 'success'
              ? '模型验证成功'
              : validationErrorModal.status === 'warning'
                ? '模型验证警告'
                : '模型验证失败'}
          </span>
        }
        open={validationErrorModal.visible}
        onCancel={() =>
          setValidationErrorModal({ visible: false, message: '' })
        }
        footer={[
          <Button
            key="close"
            type="primary"
            onClick={() =>
              setValidationErrorModal({ visible: false, message: '' })
            }
          >
            关闭
          </Button>,
        ]}
        width={500}
      >
        {/* 根据状态显示不同的内容 */}
        {validationErrorModal.status === 'success' && (
          // ✅ 成功状态
          <div>
            <Alert
              message={`${validationErrorModal.modelInfo || '当前模型'} 验证通过`}
              description={validationErrorModal.message}
              type="success"
              showIcon
              style={{ marginBottom: 16 }}
            />
            <p style={{ color: '#52c41a' }}>✓ 模型配置正确，可以正常使用。</p>
          </div>
        )}

        {validationErrorModal.status === 'warning' && (
          // 🚨 警告状态
          <div>
            <Alert
              message={`${validationErrorModal.modelInfo || '当前模型'} 验证警告`}
              description={validationErrorModal.message}
              type="warning"
              showIcon
              style={{ marginBottom: 16 }}
            />
            <p>模型配置存在暂时性问题，可能影响使用。</p>
            <p style={{ marginTop: 8, color: '#666' }}>
              建议：稍后重试或检查账户状态。
            </p>
          </div>
        )}

        {validationErrorModal.status === 'failed' && (
          // ❌ 失败状态
          <div>
            <Alert
              message={
                validationErrorModal.attemptedModel
                  ? `尝试切换到 ${validationErrorModal.attemptedModel} 失败`
                  : `${validationErrorModal.modelInfo || '当前模型'} 验证失败`
              }
              description={validationErrorModal.message}
              type="error"
              showIcon
              style={{ marginBottom: 16 }}
            />
            <p>配置文件中的模型无法正常工作，请检查配置或稍后重试。</p>
            <p style={{ marginTop: 8, color: '#666' }}>
              注意：系统已自动回退到配置文件中的可用模型。
            </p>
          </div>
        )}
      </Modal>
    </Layout>
  );
};

export default AppLayout;
