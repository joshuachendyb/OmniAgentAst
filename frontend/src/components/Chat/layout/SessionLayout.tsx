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

interface SessionLayoutProps {
  panels: SessionPanel[];
  rightOpen: boolean;
  onToggleRight: () => void;
}

const LEFT_WIDTH = 240;

const renderSlot = (panels: SessionPanel[], slot: SlotName) =>
  panels
    .filter((p) => p.slot === slot)
    .filter((p) =>
      readPanelVisible(p.key, p.defaultVisible ?? true, p.persistVisible ?? false)
    )
    .map((p) => <React.Fragment key={p.key}>{p.component}</React.Fragment>);

const SessionLayout: React.FC<SessionLayoutProps> = ({
  panels,
  rightOpen,
  onToggleRight,
}) => (
  <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 4, minWidth: 0 }}>
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
          borderRight: '1px solid #f0f0f0',
          overflow: 'hidden',
        }}
      >
        {renderSlot(panels, 'left')}
      </div>

      {rightOpen ? (
        <div style={{ flex: '1 1 75%', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <Button
            size="small"
            type="text"
            icon={<DoubleRightOutlined />}
            onClick={onToggleRight}
            style={{ alignSelf: 'flex-end' }}
          />
          <div style={{ flex: 1, minHeight: 0, overflowY: 'auto' }}>
            {renderSlot(panels, 'right')}
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, minWidth: 0, display: 'flex', justifyContent: 'flex-end' }}>
          <Button size="small" type="text" icon={<DoubleLeftOutlined />} onClick={onToggleRight} />
        </div>
      )}
    </div>

    {/* ③④⑤ taskinfo / config / input */}
    <div>{renderSlot(panels, 'taskinfo')}</div>
    <div>{renderSlot(panels, 'config')}</div>
    <div>{renderSlot(panels, 'input')}</div>
  </div>
);

export { SessionLayout };
