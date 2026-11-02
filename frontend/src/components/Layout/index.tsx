// 编辑历史: 2026-02-17 小新 - 创建Layout组件(左右分栏+响应式)
// 编辑历史: 2026-02-18 小新 - 添加移动端响应式支持
// 编辑历史: 2026-08-22 小欧 - model结构化归一: updateConfig改传ai_model_ref结构; serviceStatus的provider/model读取点改经status.model_ref派生
// 编辑历史: 2026-08-27 小欧 - serviceStatus.success→valid字段名对齐后端返回
// 编辑历史: 2026-08-27 小欧 - 删_sessionCount死状态/refreshModelList透传/unreadCount死值; 精简console.log; Option上移; 更正Header高度注释
// 编辑历史: 2026-08-27 小欧 - #1890ff→#1677ff(头像背景/标题); 删5处console.log调试语句
// 编辑历史: 2026-08-28 老杨 - 引用比较改为深比较关键字段valid/status，避免每次新对象即true
// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复注释行尾多余空白, 防止格式再次出错
// 编辑历史: 2026-09-08 小欧 - 删顶部模型状态指示Tag(北京老陈令): 右侧已有独立模型Select+检查按钮, 左侧Tag功能完全冗余, 删除更简洁 — 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 删左侧Logo区Avatar(北京老陈令): 顶部仅保留文字标识"OmniAgentAst.", 更简洁 — 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 标题图标化(北京老陈令): 顶部"对话与任务"文字换D三色弧段loader(蓝绿橙, 与 title-icon-compare.html 的D三色版一致),
//   复用 waiting-spin 逆时针1s常转, Tooltip 保留原标题; Title 组件仍被 Logo 区使用, import 保留 — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-A类: 去refreshAll解构; isManualRefreshing改[,setIsManualRefreshing]
//   (保留setter调用防死状态:131注释, 仅弃读值) — 小欧-2026-09-09
// 编辑历史: 2026-09-15 小欧 - 左侧Logo图形化+品牌文字移位(北京老陈令): ①删Logo区文字Title, 换斜向波浪3x3九色点阵SVG(gridwave动画);
//   ②"OmniAgentAst."移右侧顶栏圈圈(title-spin-icon)之后(brand-title-text); ③Title组件不再使用, 保留import防他处引用破坏 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 10大规范自查整改: ①删Typography/Title死import(禁止backward); ②9个rect抽
//   LOGO_GRID_CELLS常量数组+map迭代渲染(DRY); ③行内width/height冗余删除由CSS定义(DRY) — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 动画图标抽离(北京老陈令): 左侧Logo点阵+右侧顶栏圈圈两段内联SVG统一移入
//   新建 AnimatedIcons/index.tsx(LogoGridIcon/TitleSpinIcon, 数据+渲染随组件走), Layout改import引用, LOGO_GRID_CELLS随组件移走 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 折叠后Logo不显示修复+菜单栏优化(北京老陈令): ①折叠态Logo渲染条件去!collapsed; ②Logo区高度64→43对齐Header;
//   ③Logo包Tooltip"OmniAgentAst"; ④disabled项统一"即将上线"预留样式; ⑤展开态Logo对齐菜单图标中心; ⑥菜单栏默认折叠 — 小欧-2026-09-15
// 编辑历史: 2026-09-15 小欧 - 折叠态Tooltip黑框无字修复(北京老陈反馈): 折叠时AntD自动Tooltip取label文本,
//   label为JSX(Badge/Tooltip包裹)取不到字符串→黑框无字, 所有菜单项显式加title字符串兜底 — 小欧-2026-09-15
// 编辑历史: 2026-09-20 小强 - 侧边"系统设置"菜单/快捷跳转由 /settings 切换为 /settings2(设置2版: 6Tab+模型管理) — 小强-2026-09-20
// 编辑历史: 2026-09-21 小欧 - 旧设置页整体退休: 配置验证弹窗"去设置"跳转由 /settings 改 /settings2(旧页路由已移除)
// 编辑历史: 2026-09-21 小强 - 顶栏Header优化: ①删写-only死状态isManualRefreshing(值从未被读, 收尾09-09半删YAGNI);
//   ②配置验证Tag emoji改WarningOutlined(禁emoji); ③#fff/fontSize14/gap12→Colors.BG.PRIMARY/FontSize.PRIMARY/Spacing.LG令牌零视觉差 — 小强-2026-09-21
// 编辑历史: 2026-09-21 小强 - DRY收口: handleModelChange改经configApi.switchCurrentModel共用切全局模型唯一写链(去本地装配ai_model_ref) — 小强-2026-09-21
// 编辑历史: 2026-09-24 19:15:07 小欧 - DRY收口: handleModelChange改经AppContext.switchAndRefreshModel(API+刷新收口), 删configApi直调与手动refreshAfterModelChange — 小欧-2026-09-24
// 编辑历史: 2026-10-20 小欧 - Content底部留白10→4px(北京老陈令): 压缩聊天页输入区下方红框留白(上层ChatPage已8→2, 本层为全站通用底距) — 小欧-2026-10-20
// 编辑历史: 2026-10-21 小杨 - 文件管理菜单解禁(/files 去掉 disabled 与"即将上线" Tooltip) + 双 tooltip 收敛(只留原生 title) — 小杨-2026-10-21
// 编辑历史: 2026-10-25 小欧 - 修左侧菜单tooltip双重显示: 移除所有menu item的title属性(展开原生title+折叠antd自带=双重显示),
//   移除后展开无tooltip, 折叠由antd自动从label提取文本显示 — 小欧-2026-10-25
// 编辑历史: 2026-10-27 小欧 - 侧边栏宽度优化(北京老陈令): 宽/窄菜单切换(宽:180/80px, 窄:120/48px)+顶栏切换图标localStorage持久化;
//   窄模式文字截断修复: <style>移出Menu(AntD 5.x不渲染非菜单项children), padding改逻辑属性+补图标/正文margin覆盖 — 小欧-2026-10-27
// 编辑历史: 2026-11-02 小欧 - 顶栏模型选择框 minWidth:350 改定宽+popupMatchSelectWidth=false 弹层自适应全宽条(长名不再撑宽选中框,下拉完整显示provider (model)),端内HMR实测两框生效 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 顶栏模型框宽度归常量TOP_MODEL_SELECT_WIDTH=180(选中框+弹层minWidth两槽位共引,调宽只改一行),与底部ModelPicker各自持常量互不共享隔离 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 北京老陈令: 顶框选中框width回归minWidth下限语义(修手改minWidth::双冒号语法错),常量仅作下限 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 历史条目合规整改: 抹除各类序号类引用(15处), 超行条目压缩为2行, 乱序条目按日期归位; 条目未删, 技术含义不变 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - SRP拆分6件套迁出: useValidationFeedback/GlobalModelSelect/ServiceCheckButton/ValidationDetailModal/ValidationErrorModal/NavContent, 壳层只留组合编排 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 版本号真源化: APP_VERSION死字串删除, health.version(version.txt首行)入props走NavContent底条; 底条bottom抬到触发条上方治从未显示 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - SidebarModeSwitcher控件及宽窄模式常量/读写迁独立文件, 壳层回归组合编排单职责 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 魔法数字清零: 壳层高43/抽屉220/层级99,100/投影×2/pad16,20,24/字20/8,12/内容区6,6,4,6,12,100ms 共14处, 令牌或命名常量(零视觉差) - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 死链删除: ValidationDetailModal+顶栏死Tag+validationModalVisible+validationResult解构全删(AppContext validationResult仅被写null, Tag条件恒false永不可达), 零行为变化 - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 功能重设计: "检查服务"按钮+三态弹窗半死链(成功/警告分支死后端无status字段)+toast复读 → ConfigStatusPill配置状态胶囊(语义订正: 实查config.yaml四步校验) - 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 顶栏加ServiceStatusPill(服务存活与本胶囊分立); 版本号改为从AppContext的/health派生, 删壳层单独打health的useEffect与healthApi导入 - 小欧-2026-11-02
// 编辑历史: 2026-11-03 06:40:41 小欧 - 顶栏标题圈圈换 TitleStreamIcon(流状态联动): 壳层零逻辑, 仍是纯插槽 - 小欧-2026-11-03
/**
 * Layout组件 - 应用主布局（响应式版）
 *
 * 功能：左右分栏布局，左侧导航栏，右侧内容区，支持移动端响应式
 *
 * @author 小新
 * @version 1.1.0
 * @since 2026-02-17
 * @update 2026-02-18 添加移动端响应式支持
 * @update 2026-08-22 小欧 - model结构化归一(前端随后端修改): updateConfig 改传 ai_model_ref 结构; serviceStatus 的 provider/model 读取点(4处)改经 status.model_ref 派生
 */
import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Layout, Avatar, Drawer, Button, Grid } from 'antd';
import { DesktopOutlined, MenuOutlined } from '@ant-design/icons';
import NavContent from './NavContent';
import {
  SidebarModeSwitcher,
  getSidebarWidths,
  readSidebarMode,
} from './SidebarModeSwitcher';
import { GlobalModelSelect } from './GlobalModelSelect';
import { ConfigStatusPill } from './ConfigStatusPill';
import { ServiceStatusPill } from './ServiceStatusPill';
import { StreamStatusPill } from './StreamStatusPill';
import { TitleStreamIcon } from './TitleStreamIcon';
import ShortcutPanel from '../ShortcutPanel';
import { useApp } from '../../contexts/AppContext';
import { LayoutSkeleton } from '../Skeleton';
import {
  Colors,
  FontSize,
  Spacing,
  Size,
  Radius,
} from '../../utils/stepStyles';
import { handleError, ErrorType } from '@/services/error/handler';
// import useInitializationProgress from "../../hooks/useInitializationProgress"; // 步骤9预留

const { useBreakpoint } = Grid;

const { Sider, Content, Header } = Layout;

// 2026-11-02 小欧 - 魔法数字收口: 壳层专属值命名常量化, 步长/尺寸有令牌处直接用令牌; 色值无同值令牌按stepStyles硬规定留组件常量不进库 — 小欧-2026-11-02
const MOBILE_DRAWER_WIDTH = 220; // 移动端抽屉宽
const HEADER_GAP = 24; // 顶栏左组元素间距
const HEADER_SHADOW = '0 2px 8px rgba(0,0,0,0.05)'; // 顶栏投影
const SIDER_SHADOW = '2px 0 8px rgba(0,0,0,0.05)'; // 侧栏投影(向右)
const HEADER_Z_INDEX = 99; // 顶栏层级
const SIDER_Z_INDEX = 100; // 侧栏层级
const MENU_BUTTON_FONT_SIZE = 20; // 移动端菜单按钮图标字号
const SKELETON_SWITCH_DELAY_MS = 100; // 初始化完成→骨架屏收起延迟
// 2026-11-02 小欧 - #f8fafc无同值令牌(BG.SECONDARY=#fafafa不混用), 硬规定不新增颜色令牌, 留此处常量 — 小欧-2026-11-02
const CONTENT_BG = '#f8fafc'; // 内容区底色

interface LayoutProps {
  children: React.ReactNode;
  activeKey?: string;
  // 2026-09-30 小欧 [63]7.x - 实施: 当前会话 id(由 App 壳解析: URL 优先/sessionStorage 回落),供「对话任务」显式回跳 — 小欧-2026-09-30
  currentSessionId?: string | null;
}

/**
 * 主布局组件
 *
 * 设计要点：
 * - 左侧导航栏(宽/窄两模式: 宽180/80px, 窄120/48px, localStorage持久化)
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
const AppLayout: React.FC<LayoutProps> = ({
  children,
  activeKey = '/',
  currentSessionId = null,
}) => {
  // 路由导航
  const navigate = useNavigate();
  // 导航折叠状态
  // 2026-09-15 小欧 - 默认折叠(北京老陈令): useState初始true, 用户可手动展开 — 小欧-2026-09-15
  const [collapsed, setCollapsed] = useState(true);
  // 2026-10-27 小欧 - 侧边栏模式(宽/窄菜单), 从 localStorage 读取
  const [sidebarMode, setSidebarMode] = useState<'wide' | 'narrow'>(
    readSidebarMode
  );
  // 2026-10-27 小欧 - 监听侧边栏模式变化事件(设置页切换时触发)
  useEffect(() => {
    const handler = (e: Event) => {
      const mode = (e as CustomEvent<{ mode: 'wide' | 'narrow' }>).detail.mode;
      setSidebarMode(mode);
    };
    window.addEventListener('sidebar-mode-change', handler);
    return () => window.removeEventListener('sidebar-mode-change', handler);
  }, []);
  // 2026-10-27 小欧 - 获取当前模式的宽度参数
  const sidebarWidths = getSidebarWidths(sidebarMode);
  // 移动端抽屉显示状态
  const [drawerVisible, setDrawerVisible] = useState(false);
  // 快捷指令面板显示状态
  const [shortcutPanelVisible, setShortcutPanelVisible] = useState(false);
  // 响应式断点
  const screens = useBreakpoint();
  const isMobile = !screens.md; // md 以下认为是移动端

  // ⭐ 使用AppContext缓存API数据，避免重复调用
  const { initializeApp, isInitialized, initError, appVersion } = useApp();

  // 2026-11-02 小欧 - 版本号真源化: 取后端 /health 的 version(version.txt 首行), 由 AppContext 存且只进不退;
  //   探活失败不再连带把底条版本清成"—"(旧实现直读 healthStatus?.version) — 小欧-2026-11-02

  // 【新增】骨架屏显示状态
  const [skeletonState, setSkeletonState] = useState<{
    visible: boolean;
    error?: string;
  }>({ visible: true });

  // 【修正】骨架屏切换：监听isInitialized完成后延迟100ms切换
  // 或监听initError使用errorHandler统一处理错误
  useEffect(() => {
    // 初始化成功，延迟切换到实际内容
    if (isInitialized && skeletonState.visible && !initError) {
      const timer = setTimeout(() => {
        setSkeletonState({ visible: false });
      }, SKELETON_SWITCH_DELAY_MS);
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

  // 页面加载时初始化 - 使用AppContext
  // 【2026-04-08修复】页面加载不调用服务检查，与会话加载无关
  useEffect(() => {
    initializeApp();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
          width={MOBILE_DRAWER_WIDTH}
          styles={{ body: { padding: 0 } }}
        >
          <NavContent
            activeKey={activeKey}
            collapsed={collapsed}
            isMobile={isMobile}
            sidebarMode={sidebarMode}
            currentSessionId={currentSessionId}
            onOpenShortcuts={() => setShortcutPanelVisible(true)}
            onCloseDrawer={() => setDrawerVisible(false)}
            appVersion={appVersion || '—'}
          />
        </Drawer>
      ) : (
        /* 桌面端：左侧导航栏 - 前端小新代修改: 220px→180px */
        /* 2026-10-27 小欧 - 侧边栏宽度优化: 支持宽/窄菜单切换, 从 localStorage 读取 */
        <Sider
          width={sidebarWidths.expanded}
          collapsedWidth={sidebarWidths.collapsed}
          theme="light"
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          style={{
            boxShadow: SIDER_SHADOW,
            zIndex: SIDER_Z_INDEX,
          }}
        >
          <NavContent
            activeKey={activeKey}
            collapsed={collapsed}
            isMobile={isMobile}
            sidebarMode={sidebarMode}
            currentSessionId={currentSessionId}
            onOpenShortcuts={() => setShortcutPanelVisible(true)}
            appVersion={appVersion || '—'}
          />
        </Sider>
      )}

      {/* 右侧内容区 */}
      <Layout>
        {/* 顶部Header - 固定Header高度43px（与LayoutSkeleton一致） */}
        <Header
          style={{
            height: Size.HEADER_HEIGHT,
            // 2026-09-21 小强 - 令牌零视觉差：#fff=Colors.BG.PRIMARY
            background: Colors.BG.PRIMARY,
            boxShadow: HEADER_SHADOW,
            // 2026-11-02 小欧 - 收口: 16=Spacing.XL, 20=Spacing.XXL(零视差) — 小欧-2026-11-02
            padding: isMobile ? `0 ${Spacing.XL}px` : `0 ${Spacing.XXL}px`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            zIndex: HEADER_Z_INDEX,
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: HEADER_GAP,
            }}
          >
            {/* 移动端菜单按钮 - 前端小新代修改: 增大按钮尺寸，添加tooltip */}
            {isMobile && (
              <Button
                type="text"
                icon={<MenuOutlined />}
                onClick={() => setDrawerVisible(true)}
                title="打开导航菜单"
                style={{
                  fontSize: MENU_BUTTON_FONT_SIZE,
                  // 2026-11-02 小欧 - 收口: 8=Spacing.MD, 12=Spacing.LG(零视差) — 小欧-2026-11-02
                  padding: `${Spacing.MD}px ${Spacing.LG}px`,
                }}
              />
            )}
            {/* 2026-09-08 小欧 - 标题图标化(北京老陈令): "对话与任务"文字换D三色弧段loader(蓝绿橙),
                与对比页 title-icon-compare.html 的 D 三色版一致, 1s逆时针常转; Tooltip 保留原标题, 无障碍 — 小欧-2026-09-08
                2026-09-15 小欧 - 内联SVG抽离至 AnimatedIcons/TitleSpinIcon — 小欧-2026-09-15
                2026-11-03 06:40:41 小欧 - 换 TitleStreamIcon 联动流状态: 转速=节奏(停/快/慢), 文案与颜色仍归流胶囊 — 小欧-2026-11-03 */}
            {/* 2026-10-21 小杨 - 双 tooltip 收敛：原生 title 即可 */}
            <span title="事项对话">
              <TitleStreamIcon />
            </span>
            {/* 2026-09-15 小欧 - 品牌文字移此(北京老陈令): 左侧文字Logo挪到动画圈圈之后, 字号/粗细/色与左侧一致 — 小欧-2026-09-15 */}
            <span className="brand-title-text" aria-label="OmniAgentAst">
              OmniAgentAst.
            </span>
          </div>

          {/* 右侧操作区 */}
          {/* 2026-09-21 小强 - 令牌零视觉差：gap 12=Spacing.LG */}
          <div
            style={{ display: 'flex', alignItems: 'center', gap: Spacing.LG }}
          >
            {/* 模型选择下拉框 - 2026-11-02 小欧 SRP拆分: 领域逻辑迁GlobalModelSelect, 壳层只留插槽 — 小欧-2026-11-02 */}
            <GlobalModelSelect />
            {/* 模型配置状态胶囊 - 2026-11-02 小欧 重设计: 五步校验三级分级(绿就绪/黄预警/红错误)语义=可发消息与否, 自动检测+点击重检(config.yaml完整性+凭证预警, 非LLM连通/非后端存活), 替代旧"检查服务"按钮+三态弹窗死链 — 小欧-2026-11-02 */}
            <ConfigStatusPill />
            {/* 后端服务状态胶囊 - 2026-11-02 小欧 新建(北京老陈令): 与配置胶囊分立, 只答"后端能不能应答"/health三态(绿正常/黄缓慢或降级/红离线), Tooltip全量常显地址/PID/耗时 — 小欧-2026-11-02 */}
            <ServiceStatusPill />
            {/* SSE 流状态小灯 - 2026-11-02 小欧 新建: 与服务胶囊正交, 只答"当前这条流活没活/心跳新不新", 只读 store 不发请求 — 小欧-2026-11-02 */}
            <StreamStatusPill />
            {/* 2026-10-27 小欧 - 菜单宽度切换(宽/窄菜单, 漂亮的视觉设计) */}
            <SidebarModeSwitcher />
            <Avatar size="small" icon={<DesktopOutlined />} />
            {/* 2026-09-21 小强 - 令牌零视觉差：fontSize 14=FontSize.PRIMARY；2026-11-02 小欧 #666→TEXT.MUTED令牌收口 — 小欧-2026-11-02 */}
            <span
              style={{ color: Colors.TEXT.MUTED, fontSize: FontSize.PRIMARY }}
            >
              用户
            </span>
          </div>
        </Header>

        {/* 主内容区 - 只有这层有留白 - 前端小新代修改: 留白优化, 背景色优化 */}
        {/* 
          📝 留白调整说明（修改这里调整 Card 组件与外边框的间距）：
          padding: "上 右 下 左"
          - 上：Card 与顶部标题栏的间距（当前值：6px）
          - 右：Card 与右侧边框的间距（当前值：6px）
          - 下：Card 与底部边框的间距（当前值：4px）
          - 左：Card 与左侧菜单的间距（当前值：6px）
        */}
        <Content
          style={{
            margin: 0,
            // 2026-10-20 小欧 - 底10→4(北京老陈令: 红框留白压缩), 其余三边不变; 2026-11-02 收口: 6=Spacing.SM, 4=Spacing.XS(零视差) — 小欧-2026-11-02
            padding: `${Spacing.SM}px ${Spacing.SM}px ${Spacing.XS}px ${Spacing.SM}px`,
            background: CONTENT_BG,
            borderRadius: Radius.CONTAINER,
            minHeight: 0,
            flex: 1,
            overflow: 'auto',
          }}
        >
          {/* 【新增】骨架屏/实际内容切换 */}
          {skeletonState.visible ? <LayoutSkeleton /> : children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
