// 编辑历史: 2026-08-26 小欧 - 8.3 实施: 会话插槽化骨架, panels prop注入消除首帧闪屏(4.2.1)
// 编辑历史: 2026-08-27 小欧 - 修复: 根gap4→8主节奏; 左列overflow hidden→auto(防贴边); 右侧滚动区加minHeight0+padding0 12px 8px防代码块贴边
// 编辑历史: 2026-08-30 小欧 - v1.100实施: 左列flex:'1 1 0'自适应+min/max守卫(LEFTBAR_MINW=200/MAXW=560), 右栏收起分支flex:'0 0 auto'+marginLeft:auto仅按钮宽条 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - v1.100修复: 左列flex '1 1 0'→'1 1 25%'(实测201px仅14%不达验收"约1/4", 改后25%/74.5%精确吻合设计; 依据真实Chrome测量, 同步设计文档) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - v1.100设计语义澄清修正: 收起态左列填满不设maxWidth(max560仅约束展开态), 展开态左列flex'1 1 25%'+max560; 实测收起态左≈1351px@容器1424 - 小欧-2026-08-30
// 编辑历史: 2026-10-20 小欧 - 展开态»折叠钮去独占行(北京老陈令): 原钮独占一行致step窗口顶部空出24px空行, 改absolute悬浮右上角(容器position:relative, 钮白底zIndex10防内容文字穿透) — 小欧-2026-10-20
// 编辑历史: 2026-10-27 小欧 - v1.7: 改用 SplitPane 组件，支持拖动分割线调整左右面板宽度，默认左侧 1/3；删除 LEFTBAR_MINW/MAXW 常量（SplitPane 内部管理） — 小欧-2026-10-27
// 编辑历史: 2026-10-28 小欧 - 根治「展开任务统计→右栏宽度突变+晃动」(CLS): 右栏滚动容器
//   加 scrollbar-gutter:stable 防滚动条出现致内容宽跳变 — 小欧-2026-10-28
// 编辑历史: 2026-10-28 小欧 - 修复横向溢出: 中部行未设 min-width/overflow → 默认 min-width:auto,
//   被 SplitPane 内容横向撑破, 右面板(含 absolute 折叠按钮/滚动条)随之移出视口;
//   补 minWidth:0+overflow:hidden, 右边缘约束在屏幕内(与 SplitPane.tsx 根容器/右面板同款修复) — 小欧-2026-10-28
/**
 * SessionLayout - 会话页插槽化骨架（纯展示组件）
 *
 * 【小欧 2026-08-26 8.3】panels 改为 prop 注入（修正：不再读单例，
 * 消除首帧空面板闪屏与闭包过期；注册表只承担组装期"加新功能=注册新面板"）。
 * 4.2.1：顶栏全宽；中部=左列+右侧查看区（收起=仅按钮宽度条/展开≈3/4），中间无主列；
 * 下部依次=任务信息条(taskinfo)/信任操作面板(config，默认收起)/输入区(input)。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Button } from 'antd';
import { DoubleLeftOutlined, DoubleRightOutlined } from '@ant-design/icons';
import {
  readPanelVisible,
  type SessionPanel,
  type SlotName,
} from './SessionPanelRegistry';
import { Colors } from '@/utils/stepStyles';
import { SplitPane } from './SplitPane';

interface SessionLayoutProps {
  panels: SessionPanel[];
  rightOpen: boolean;
  onToggleRight: () => void;
}

// 2026-10-27 小欧 - 删除 LEFTBAR_MINW/MAXW 常量，改用 SplitPane 组件内部管理
//   原常量用于固定 flex 布局，现在 SplitPane 组件内部定义了 MIN_LEFT_W/MAX_LEFT_W

/**
 * 2026-10-21 小杨 - 体验审计（版面决策，替代"同 slot 多面板 → Tabs"）：
 *   次要面板不再与主面板并列成 tab（主次同权、切换即失去主内容视野），
 *   改为注册到 `rightBottom` slot —— 右栏下方**可折叠区**，常驻可见且不抢主位。
 */
const renderSlot = (panels: SessionPanel[], slot: SlotName) => {
  const visible = panels
    .filter((p) => p.slot === slot)
    .filter((p) =>
      readPanelVisible(
        p.key,
        p.defaultVisible ?? true,
        p.persistVisible ?? false
      )
    );
  if (visible.length === 0) return null;
  return (
    <>
      {visible.map((p) => (
        <React.Fragment key={p.key}>{p.component}</React.Fragment>
      ))}
    </>
  );
};

// 2026-08-28 小欧 v1.3: 判空槽, 空则不渲染外层div, 避免空div占gap8致间距翻倍
const hasVisibleSlot = (panels: SessionPanel[], slot: SlotName): boolean =>
  panels.some(
    (p) =>
      p.slot === slot &&
      readPanelVisible(
        p.key,
        p.defaultVisible ?? true,
        p.persistVisible ?? false
      )
  );

const SessionLayout: React.FC<SessionLayoutProps> = ({
  panels,
  rightOpen,
  onToggleRight,
}) => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      flex: 1,
      minHeight: 0,
      gap: 8,
      minWidth: 0,
      overflow: 'hidden', // 2026-09-15 小欧: 外层Layout已锁定height:100vh, 本层不再留paddingBottom, 输入条回正常文档流由flex底部钉住, 中部滚动区自行滚动
    }}
  >
    {/* ① 顶栏区 */}
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: 8,
      }}
    >
      {renderSlot(panels, 'topbar')}
    </div>

    {/* ② 中部：左列 + 右侧查看区（中间无主列；窄屏可收缩）
        2026-10-27 小欧 - 改用 SplitPane 组件，支持拖动分割线调整宽度
        2026-10-27 小欧 - v1.1: 默认宽度固定为 30%（与右侧展开/折叠状态无关） */}
    {/* 2026-10-28 小欧 - 修复横向溢出: 中部行未设 min-width/overflow → 默认 min-width:auto, 被 SplitPane
        内容横向撑破, 右面板(含 absolute 折叠按钮/滚动条)随之移出视口; 补 minWidth:0+overflow:hidden, 右边缘约束在屏幕内 */}
    <div
      style={{
        flex: 1,
        display: 'flex',
        minHeight: 0,
        minWidth: 0,
        overflow: 'hidden',
        gap: 8,
      }}
    >
      <SplitPane
        left={renderSlot(panels, 'left')}
        // 2026-10-27 小欧 修复(审计): 折叠态传 fullLeft——右栏收起时左列填满整个宽度
        //   旧布局折叠态: 左列 flex:'1 1 0'(填满≈95%), 右列仅按钮宽条
        //   原 SplitPane 折叠态: 左列固定 30%, 右侧 70% 空白(功能分支丢失)
        fullLeft={!rightOpen}
        right={
          rightOpen ? (
            <div
              style={{
                flex: 1,
                minWidth: 0,
                // 2026-10-27 小欧 修复(审计): 补 minHeight:0——消 flexbox min-height:auto 陷阱
                //   右栏容器在 SplitPane 右面板(flex 列容器)内缺 min-height:0,
                //   导致长到内容高度, 内层滚动 div 无溢出, Step 自动滚动失效
                minHeight: 0,
                display: 'flex',
                flexDirection: 'column',
                position: 'relative', // 2026-10-20 小欧: »钮悬浮定位锚点 — 小欧-2026-10-20
              }}
            >
              <Button
                size="small"
                type="text"
                icon={<DoubleRightOutlined />}
                onClick={onToggleRight}
                style={{
                  position: 'absolute', // 2026-10-20 小欧: 原常规流独占行致顶部24px空行, 改悬浮右上, 白底防内容文字穿透 — 小欧-2026-10-20
                  top: 0,
                  right: 0,
                  zIndex: 10,
                  background: Colors.BG.PRIMARY,
                }}
              />
              <div
                style={{
                  flex: 1,
                  minHeight: 0,
                  overflowY: 'auto',
                  overflowX: 'hidden',
                  // 2026-10-28 小欧 - 防展开「任务统计」滚动条出现致右栏宽度突变(CLS): 始终预留 gutter — 小欧-2026-10-28
                  scrollbarGutter: 'stable',
                  padding: '0 12px 8px',
                }}
              >
                {renderSlot(panels, 'right')}
              </div>
              {/* 2026-10-21 小杨 - 体验审计：右栏下方**折叠区**（次要面板的家）
                  —— 与主内容共用右栏、但有独立边界与高度上限，不挤占主内容。 */}
              {hasVisibleSlot(panels, 'rightBottom') && (
                <div
                  style={{
                    flex: '0 0 auto',
                    minHeight: 0,
                    maxHeight: '45%',
                    display: 'flex',
                    flexDirection: 'column',
                    borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
                    background: Colors.BG.SECONDARY,
                  }}
                >
                  {renderSlot(panels, 'rightBottom')}
                </div>
              )}
            </div>
          ) : (
            <div
              style={{
                flex: 1,
                marginLeft: 'auto',
                display: 'flex',
                alignItems: 'flex-start',
                padding: '0 8px',
              }}
            >
              <Button
                size="small"
                type="text"
                icon={<DoubleLeftOutlined />}
                onClick={onToggleRight}
              />
            </div>
          )
        }
      />
    </div>

    {/* ③④⑤ taskinfo / config / input */}
    {hasVisibleSlot(panels, 'taskinfo') && (
      <div>{renderSlot(panels, 'taskinfo')}</div>
    )}
    {hasVisibleSlot(panels, 'config') && (
      <div>{renderSlot(panels, 'config')}</div>
    )}
    {hasVisibleSlot(panels, 'input') && (
      <div>{renderSlot(panels, 'input')}</div>
    )}
  </div>
);

export { SessionLayout };
