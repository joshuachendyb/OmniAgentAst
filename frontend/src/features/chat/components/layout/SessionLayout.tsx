// 编辑历史: 2026-08-26 小欧 - 8.3 实施: 会话插槽化骨架, panels prop注入消除首帧闪屏(4.2.1/R1-B25)
// 编辑历史: 2026-08-27 小欧 - 三堂会审P0-6: 根gap4→8主节奏; 左列overflow hidden→auto(防贴边); 右侧滚动区加minHeight0+padding0 12px 8px防代码块贴边
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

const LEFT_WIDTH = 'clamp(200px, 18vw, 280px)'; // 2026-08-28 小欧 v1.3(P2-H5): 定宽240→响应式区间, 防窄屏挤压

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
          width: LEFT_WIDTH,
          flexShrink: 0,
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
            flex: 1,
            minWidth: 0,
            display: 'flex',
            justifyContent: 'flex-end',
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
