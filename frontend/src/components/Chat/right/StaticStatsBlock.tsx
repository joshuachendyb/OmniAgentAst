// 编辑历史: 2026-08-26 小欧 - 8.5 实施: 任务结束静态统计块7项+token终值, 历史C1/当前final_stats(4.5.1)
// 编辑历史: 2026-08-27 小欧 - 修复#8: 工具汇总空对象{}时显'-'而非空白(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.2 抽STATUS_COLOR_MAP查表替嵌套三元
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P0-3/边距-P0-3: 去卡片双框留上分割线(borderTop#f0f0f0,去#fafafa+radius+padding覆盖), marginTop8→12 paddingTop8→padding12, 仅留终止语义锚点
// 编辑历史: 2026-08-27 小欧 - 修复chat-H: accumulated_usage 空对象{}时 token 字段缺失显'-'而非 undefined
/**
 * StaticStatsBlock - 任务结束静态统计块（右侧查看区底部）
 *
 * 【小欧 2026-08-26 8.5】7 项：最终状态/总耗时/总步骤轮次/工具汇总/错误/重试/产出物
 * + 单任务 token 终值（4.5.1 行7/14）。历史=C1 TaskDetail；当前任务终态经
 * final_stats/FinalStep 下发后由外层把 ExecutionStep 映射为 TaskDetail 传入。
 * 动态/静态分工：本组件只在任务结束后出现，切换锚定任务随之切换（4.5.1 联动规则）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React from 'react';
import { Descriptions, Tag, Typography } from 'antd';
import type { TaskDetail } from '../../../services/api';

// 2026-08-27 小欧 三堂会审: 状态色查表替嵌套三元
const STATUS_COLOR_MAP: Record<string, string> = {
  completed: 'success',
  failed: 'error',
};

const StaticStatsBlock: React.FC<{ detail: TaskDetail | null }> = ({
  detail,
}) => {
  if (!detail) return null;
  // 2026-08-27 小欧 三堂会审: 状态色查表, 未知状态回落default
  const statusColor = STATUS_COLOR_MAP[detail.status] ?? 'default';
  return (
    <div
      style={{
        marginTop: 12,
        padding: 12,
        background: 'transparent',
        border: 'none',
        borderRadius: 0,
        borderTop: '1px solid #f0f0f0',
      }}
    >
      <Typography.Text strong style={{ fontSize: 13 }}>
        任务统计
      </Typography.Text>
      <Descriptions size="small" column={2} style={{ marginTop: 4 }}>
        <Descriptions.Item label="最终状态">
          <Tag color={statusColor}>{detail.status}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="总耗时">
          {detail.duration != null ? `${Math.round(detail.duration)}s` : '-'}
        </Descriptions.Item>
        <Descriptions.Item label="步骤/轮次">
          {detail.total_steps} / {detail.llm_call_count}
        </Descriptions.Item>
        <Descriptions.Item label="重试">{detail.retry_count}</Descriptions.Item>
        <Descriptions.Item label="工具汇总" span={2}>
          {detail.tool_stats && Object.keys(detail.tool_stats).length > 0
            ? Object.entries(detail.tool_stats)
                .map(([k, v]) => `${k}×${v}`)
                .join('、')
            : '-'}
        </Descriptions.Item>
        {detail.error_message && (
          <Descriptions.Item label="错误" span={2}>
            <Typography.Text type="danger" style={{ fontSize: 12 }}>
              [{detail.error_type}] {detail.error_message}
            </Typography.Text>
          </Descriptions.Item>
        )}
        <Descriptions.Item label="token 终值" span={2}>
          {/* 2026-08-27 小欧 修复: accumulated_usage 为空对象{}时 token 字段缺失, 显'-'而非 undefined(BUG-H) */}
          {(() => {
            const u = detail.accumulated_usage;
            const hasTokens =
              u != null &&
              (u.prompt_tokens != null ||
                u.completion_tokens != null ||
                u.total_tokens != null);
            return hasTokens
              ? `P ${u.prompt_tokens} / C ${u.completion_tokens} / T ${u.total_tokens}`
              : '-';
          })()}
        </Descriptions.Item>
        {detail.artifacts && detail.artifacts.length > 0 && (
          <Descriptions.Item label="产出物" span={2}>
            {detail.artifacts.map((a) => (
              <Tag key={a.path} color="blue" style={{ marginBottom: 2 }}>
                {a.name}({a.type})
              </Tag>
            ))}
          </Descriptions.Item>
        )}
      </Descriptions>
    </div>
  );
};

export { StaticStatsBlock };
