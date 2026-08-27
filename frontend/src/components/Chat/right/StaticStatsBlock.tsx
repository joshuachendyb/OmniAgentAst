// 编辑历史: 2026-08-26 小欧 - 8.5 实施: 任务结束静态统计块7项+token终值, 历史C1/当前final_stats(4.5.1)
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
 * 2026-08-27 小欧 - 修复#8: 工具汇总空对象{}时显'-'而非空白(实测失败用例转绿)
 */

import React from 'react';
import { Descriptions, Tag, Typography } from 'antd';
import type { TaskDetail } from '../../../services/api';

const StaticStatsBlock: React.FC<{ detail: TaskDetail | null }> = ({
  detail,
}) => {
  if (!detail) return null;
  const statusColor =
    detail.status === 'completed'
      ? 'success'
      : detail.status === 'failed'
        ? 'error'
        : 'default';
  return (
    <div
      style={{
        borderTop: '1px solid #f0f0f0',
        marginTop: 8,
        paddingTop: 8,
        background: '#fafafa',
        borderRadius: 6,
        padding: 8,
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
          {detail.accumulated_usage
            ? `P ${detail.accumulated_usage.prompt_tokens} / C ${detail.accumulated_usage.completion_tokens} / T ${detail.accumulated_usage.total_tokens}`
            : '-'}
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
