/**
 * TopbarStats - 顶栏会话级聚合信息（任务数/会话累计 token/创建更新时间悬浮）
 *
 * 【小欧 2026-08-26 8.1】三分归位原则②：会话级信息展示只在顶栏（4.5.1）。
 * 生效模型徽标由 8.13 useModelLayer + 既有 ModelPicker 承载，不在本组件重复。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Tooltip, Typography } from 'antd';

interface TopbarStatsProps {
  taskCount: number;
  chainTokens: number | null;
  createdAt?: string;
  updatedAt?: string;
}

const TopbarStats: React.FC<TopbarStatsProps> = ({
  taskCount,
  chainTokens,
  createdAt,
  updatedAt,
}) => {
  const timeTip =
    createdAt || updatedAt
      ? `创建：${createdAt ?? '-'}\n更新：${updatedAt ?? '-'}`
      : '';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 12 }}>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        任务数 {taskCount}
      </Typography.Text>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        累计 token {chainTokens ?? '-'}
      </Typography.Text>
      {timeTip && (
        <Tooltip
          title={<span style={{ whiteSpace: 'pre-line' }}>{timeTip}</span>}
        >
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            ⓘ
          </Typography.Text>
        </Tooltip>
      )}
    </span>
  );
};

export { TopbarStats };
