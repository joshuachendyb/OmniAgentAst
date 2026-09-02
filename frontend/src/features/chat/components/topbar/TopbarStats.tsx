// 编辑历史: 2026-08-26 小欧 - 8.1 实施: 顶栏会话级聚合(任务数/token/时间), 三分归位②(4.5.1)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.3 删冗余??'-'(formatTime已返'-')
// 编辑历史: 2026-08-27 小欧 - 三堂会审边距-P1: 顶栏聚合gap12→8对齐SessionLayout主节奏
// 编辑历史: 2026-09-01 小欧 - 顶栏token双口径(北京老陈定案): 前面会话累计(session)后面链累计(chain), 各为3字段P/C/T紧凑格式; chainTokens由number改TokenTriple
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: TB-03 taskCount加??0兜底防undefined闪烁 — 小欧-2026-09-02
/**
 * TopbarStats - 顶栏会话级聚合信息（任务数/会话累计token/链累计token/创建更新时间悬浮）
 *
 * 【小欧 2026-08-26 8.1】三分归位原则②：会话级信息展示只在顶栏（4.5.1）。
 * 生效模型徽标由 8.13 useModelLayer + 既有 ModelPicker 承载，不在本组件重复。
 * 2026-09-01 北京老陈定案：顶栏两个 token 都显示，前面 session 会话累计，后面 chain 链累计。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { formatDate } from '@/utils/time'; // 2026-08-28 小欧 合并time模块: formatTime统一至utils/time.ts
import { Tooltip, Typography } from 'antd';

// 2026-09-01 小欧: token 3 字段口径
interface TokenTriple {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

// 2026-09-01 小欧: 3字段紧凑格式(与StaticStatsBlock的P/C/T一致, 去/两侧空格省宽度), 无值显'-'
const formatTriple = (t: TokenTriple | null): string => {
  if (!t) return '-';
  const p = t.prompt_tokens ?? '-';
  const c = t.completion_tokens ?? '-';
  const v = t.total_tokens ?? '-';
  return `P${p}/C${c}/T${v}`;
};

interface TopbarStatsProps {
  taskCount: number;
  sessionTokens: TokenTriple | null; // 2026-09-01 小欧: 会话累计 token(前)
  chainTokens: TokenTriple | null; // 2026-09-01 小欧: 链累计 token(后, 由number改3字段)
  createdAt?: string;
  updatedAt?: string;
}

const TopbarStats: React.FC<TopbarStatsProps> = ({
  taskCount,
  sessionTokens,
  chainTokens,
  createdAt,
  updatedAt,
}) => {
  const timeTip =
    createdAt || updatedAt
      ? `创建：${formatDate(createdAt)}\n更新：${formatDate(updatedAt)}`
      : '';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        任务数 {taskCount ?? 0}
      </Typography.Text>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        会话累计 {formatTriple(sessionTokens)}
      </Typography.Text>
      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
        链累计 {formatTriple(chainTokens)}
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
export type { TokenTriple }; // 2026-09-01 小欧: 供外部复用类型
