// 编辑历史: 2026-08-26 小欧 - 8.3 实施: 会话插槽化骨架, panels prop注入消除首帧闪屏(4.2.1/R1-B25)
// 编辑历史: 2026-08-27 小欧 - 三堂会审P0-6: 根gap4→8主节奏; 左列overflow hidden→auto(防贴边); 右侧滚动区加minHeight0+padding0 12px 8px防代码块贴边
// 编辑历史: 2026-08-30 小欧 - v1.100实施: 左列flex:'1 1 0'自适应+min/max守卫(LEFTBAR_MINW=200/MAXW=560), 右栏收起分支flex:'0 0 auto'+marginLeft:auto仅按钮宽条(4.2.1/4.3.2/4.5.1/第十一章11.1-11.3) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - v1.100三堂会审P1修复: 左列flex '1 1 0'→'1 1 25%'(实测201px仅14%不达验收"约1/4", 改后25%/74.5%精确吻合4.2.1/11.0/11.5; 依据真实Chrome测量, 同步文档11.2/11.5) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - v1.100设计语义澄清修正: 收起态左列填满不设maxWidth(max560仅约束展开态), 展开态左列flex'1 1 25%'+max560; 实测收起态左≈1351px@容器1424 - 小欧-2026-08-30
/**
 * SessionLayout - 会话页插槽化骨架（纯展示组件）
 *
 * 【小欧 2026-08-26 8.3】panels 改为 prop 注入（R1-B25 修正：不再读单例，
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

interface SessionLayoutProps {
  panels: SessionPanel[];
  rightOpen: boolean;
  onToggleRight: () => void;
}

const LEFTBAR_MINW = 200; // 2026-08-30 小欧 v1.100: 左列宽度随右栏折叠 flex 自适应填充(见 4.3.2), min 全域生效防过窄
const LEFTBAR_MAXW = 560; // max 防左列过宽——仅右栏展开态生效(防挤占右侧查看区); 右栏收起态左列填满不设 max(11.0 要求③)

const renderSlot = (panels: SessionPanel[], slot: SlotName) =>
  panels
    .filter((p) => p.slot === slot)
    .filter((p) =>
      readPanelVisible(
        p.key,
        p.defaultVisible ?? true,
        p.persistVisible ?? false
      )
    )
    .map((p) => <React.Fragment key={p.key}>{p.component}</React.Fragment>);

// 2026-08-28 小欧 v1.3(P2-M3): 判空槽, 空则不渲染外层div, 避免空div占gap8致间距翻倍
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

    {/* ② 中部：左列 + 右侧查看区（中间无主列；窄屏可收缩 R1-B24） */}
    <div style={{ flex: 1, display: 'flex', minHeight: 0, gap: 8 }}>
      <div
        style={{
          flex: rightOpen ? '1 1 25%' : '1 1 0',
          minWidth: LEFTBAR_MINW,
          ...(rightOpen ? { maxWidth: LEFTBAR_MAXW } : {}),
          borderRight: `1px solid ${Colors.BORDER.LIGHT}`,
          overflowY: 'auto',
          overflowX: 'hidden',
        }}
      >
        {renderSlot(panels, 'left')}
      </div>

      {rightOpen ? (
        <div
          style={{
            flex: '1 1 75%',
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <Button
            size="small"
            type="text"
            icon={<DoubleRightOutlined />}
            onClick={onToggleRight}
            style={{ alignSelf: 'flex-end' }}
          />
          <div
            style={{
              flex: 1,
              minHeight: 0,
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: '0 12px 8px',
            }}
          >
            {renderSlot(panels, 'right')}
          </div>
        </div>
      ) : (
        <div
          style={{
            flex: '0 0 auto',
            marginLeft: 'auto',
          }}
        >
          <Button
            size="small"
            type="text"
            icon={<DoubleLeftOutlined />}
            onClick={onToggleRight}
          />
        </div>
      )}
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
