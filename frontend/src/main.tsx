// 编辑历史: 2026-08-28 小欧 - 包裹antd<App>使message/notification消费ConfigProvider主题上下文, 根治toast显示异常/不可点击 - 小欧-2026-08-28
// 编辑历史: 2026-09-15 小欧 - 全站Tooltip白底浅卡片统一(北京老陈令, 效果最佳标准):
//   页面整体为白底浅色体系, AntD默认黑底黑块突兀且灰字对黑底对比度仅1.9:1不可读;
//   colorBgSpotlight=#fff+colorTextLightSolid=#595959后, 全站53处Tooltip与页面视觉同语言,
//   现有5档灰阶(Color TERTIARY#999等)灰底/白底自然可读;
//   【三堂会审修正】箭头背景由antd ::before + --antd-arrow-background-color变量自动继承colorBgSpotlight,
//   白底shadow/半径走antd自带boxShadowSecondary+tooltipBorderRadius, 无需index.css任何覆盖(YAGNI/DRY) — 小欧-2026-09-15
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.3: main.tsx 注入 setTransportConfig(baseURL)（render 前模块级一次）— 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-11-12 小欧 - **界面密度接线改写**(文档[31] §4.4/§5.7 初版 → 文档[32] 终版):
//   ①根 ConfigProvider 下发密度相关 token, 密度即刻全站生效;
//      **fontSize token 恒 14 不动** —— 阅读区 Markdown 显式设字号、不继承 antd, 故无脱节风险;
//      反过来若把 antd fontSize 也随设置项走, 会越界把整个界面都改了(违「字号只管阅读区」)。
//   ②控件高走**全站唯一刻度**(theme/controlScale.ts), 不再按「各上下文自身基线 − 偏移」:
//      原实现以 antd 缺省 32 作根基线, 既违「不许拿库默认值当标准」, 又使全站并存 32/28
//      两套控件高(同型于老陈在圆角上批过的「缺省结果的堆积」), 且页面级 ConfigProvider
//      写死基线会把根下发的密度值覆盖掉 → 密度对设置页/文件页/工作区面板无效。
//      现改为绝对刻度 24/28/32 三档 × 两档密度, 密度只切「哪一档生效」。
//   ③**弃用 componentSize 承载密度**: antd 的 size 上下文会连带把 Select/DatePicker 的
//      字号切到 fontSizeSM(=12), 违[31] §7.1 第 5 项(字号恒 14)与 §7.2 第 4 项(字号不变)。
//      密度只改控件高一个维度。
//   ④删 --density-pad CSS 变量: 全仓零消费方(阅读区间隔由 utils/markdownStyles.ts 在 TS 侧解算),
//      留着即死代码 + 双真源。规范见文档[32]。
// 编辑历史: 2026-11-13 小欧 - 三堂会审: Tooltip 色值归令牌(裸 '#ffffff'/'#595959' →
//   Colors.BG.PRIMARY/Colors.TEXT.PRIMARY, 同像素零视觉差)。 — 小欧-2026-11-13
import React, { useMemo } from 'react';
import ReactDOM from 'react-dom/client';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
// 【小强 2026-04-21】引入 antd v5 重置样式，统一浏览器默认样式差异
import 'antd/dist/reset.css';
import App from './App';
import './index.css';
// [63] 5.3：SSE 传输层连接参数模块级注入一次（替代 useSSE 的 React 入参；React render 前注入）。
//   口令不传——传输层 authHeaders() 每次请求现取 getAccessToken()，登录/改口令后即时生效
//   （原 useSSE config.token 全仓 0 处赋值 → Authorization 从不附带，2026-09-26 缺陷不复现）。
import { setTransportConfig } from './features/chat/streams/chatStreamTransport';
import { API_BASE_URL } from './services/api/client';
import { Colors } from './utils/stepStyles';
import { useAppearancePrefs } from './hooks/useAppearancePrefs';
// 控件规格唯一真源(文档[32]): 控件高三档 + 圆角三档全部显式下发,
// 不下发即等于让 antd 用 0.75×/1.25× 派生 21/35 这类非 4px 网格值。
import { controlScaleTokens } from './theme/controlScale';

setTransportConfig({ baseURL: API_BASE_URL });

/**
 * 根主题壳 —— 密度在此统一下发(控件高三档 + 圆角三档)。
 *   抽成组件而非在 main.tsx 顶层直读: 密度是**可变的运行时偏好**(改设置即时生效),
 *   顶层读取拿不到订阅, 改完设置不刷新就不生效。
 */
const RootTheme: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { density } = useAppearancePrefs();

  const theme = useMemo(
    () => ({
      token: controlScaleTokens(density),
    }),
    [density]
  );

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        ...theme,
        components: {
          Tooltip: {
            // 2026-11-13 小欧 - 色值归令牌(同像素零视觉差): 裸 '#ffffff'/'#595959' → Colors 阶梯
            colorBgSpotlight: Colors.BG.PRIMARY,
            colorTextLightSolid: Colors.TEXT.PRIMARY,
          },
        },
      }}
    >
      {children}
    </ConfigProvider>
  );
};

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <RootTheme>
        <AntdApp>
          <App />
        </AntdApp>
      </RootTheme>
    </React.StrictMode>
  );
}
