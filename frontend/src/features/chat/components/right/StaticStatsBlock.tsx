// 编辑历史: 2026-08-26 小欧 - 8.5 实施: 任务结束静态统计块7项+token终值, 历史C1/当前final_stats(4.5.1)
// 编辑历史: 2026-08-27 小欧 - 修复#8: 工具汇总空对象{}时显'-'而非空白(实测失败用例转绿)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.4.2 抽STATUS_COLOR_MAP查表替嵌套三元
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P0-3/边距-P0-3: 去卡片双框留上分割线(borderTop#f0f0f0,去#fafafa+radius+padding覆盖), marginTop8→12 paddingTop8→padding12, 仅留终止语义锚点
// 编辑历史: 2026-08-27 小欧 - 修复chat-H: accumulated_usage 空对象{}时 token 字段缺失显'-'而非 undefined
// 编辑历史: 2026-08-28 小强 - 修复[23]: token字段缺失显undefined, 用?? '-'兜底 - 小强-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 修复工具汇总null×4: 工具汇总过滤tool_name为null的条目(根因: SQL取错key致全归null); 删除步骤/轮次行(TaskInfoBar已展示)
// 编辑历史: 2026-08-30 小欧 - 布局调整: column 2→3, 第一行放最终状态/总耗时/token终值, 第二行工具汇总横跨3列; 删除重试行(TaskInfoBar已展示)
// 编辑历史: 2026-09-01 小欧 - 修复token终值行折行: 加contentStyle whiteSpace:nowrap强制单行 + 格式紧凑化P/C/T去/两侧空格省宽度; 不折行不剪切(北京老陈要求) - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 任务统计增强 v0.8: 重构为极简六节(状态Tag同行/基本信息无框/Token行内/工具汇总+单折叠链/产出物极简列表/错误弱提示)，去重总耗时/tokenTag/产出Tag - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 修复工具调用链折叠三角移至(*步)后 - 小欧-2026-09-01
// 编辑历史: 2026-09-01 小欧 - 规范全页折叠方法与符号位置/大小统一：三角统一置于(*步)后、复用TrustPanel可访问方法与FontSize/Spacing/Colors常量，符号大小统一FontSize.SECONDARY - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 整个板块可折叠(北京老陈定案): 默认折叠只显标题行(任务统计+Tag+运行时间+▼), 点击展开显示完整统计内容; 与内层工具调用链折叠独立互不影响
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
import { Tag, Typography } from 'antd';
import type { TaskDetail } from '../../../../services/api/task.api';
import type { ExecutionStep } from '../../../../types/execution';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

const STATUS_COLOR_MAP: Record<string, string> = {
  completed: 'success',
  failed: 'error',
};

interface StaticStatsProps {
  detail: TaskDetail | null;
  chainSteps?: ExecutionStep[];
}

const StaticStatsBlock: React.FC<StaticStatsProps> = ({
  detail,
  chainSteps,
}) => {
  const [expanded, setExpanded] = React.useState(false); // 默认折叠
  const [chainOpen, setChainOpen] = React.useState(false);
  if (!detail) return null;
  const statusColor = STATUS_COLOR_MAP[detail.status] ?? 'default';
  const fmtTime = (v: string | null) =>
    v ? v.slice(0, 19).replace('T', ' ') : '-';
  const chain = (chainSteps ?? []).filter((s) => s.type === 'action');
  const chainSeq =
    chain.flatMap((s) => (s.tools ?? []).map((t) => t.tool)).join(' -> ') ||
    '-';
  return (
    <div
      style={{
        marginTop: 12,
        padding: 12,
        background: 'transparent',
        border: 'none',
        borderRadius: 0,
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
      }}
    >
      {/* 标题行：可折叠 */}
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={() => setExpanded(!expanded)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setExpanded(!expanded);
          }
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginTop: 8,
          cursor: 'pointer',
        }}
      >
        <Typography.Text strong style={{ fontSize: 13 }}>
          任务统计
        </Typography.Text>
        <Tag color={statusColor} style={{ margin: 0 }}>
          {detail.status}
        </Tag>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          运行{' '}
          {detail.duration != null ? `${Math.round(detail.duration)}s` : '-'}
        </Typography.Text>
        <span
          style={{
            fontSize: FontSize.PRIMARY,
            color: Colors.TEXT.PRIMARY,
            marginLeft: 'auto',
          }}
        >
          {expanded ? '▲' : '▼'}
        </span>
      </div>
      {/* 展开时显示完整统计内容 */}
      {expanded && (
        <>
          <div
            style={{
              marginTop: 10,
              borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
              paddingTop: 8,
            }}
          >
            <Typography.Text
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: '#595959',
                borderLeft: `2px solid ${Colors.PRIMARY}`,
                paddingLeft: 6,
              }}
            >
              基本信息
            </Typography.Text>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '72px 1fr 72px 1fr',
                columnGap: 12,
                rowGap: 4,
                marginTop: 6,
                fontSize: 12,
              }}
            >
              <span style={{ color: '#8c8c8c' }}>开始</span>
              <span style={{ color: '#262626', whiteSpace: 'nowrap' }}>
                {fmtTime(detail.created_at)}
              </span>
              <span style={{ color: '#8c8c8c' }}>结束</span>
              <span style={{ color: '#262626', whiteSpace: 'nowrap' }}>
                {fmtTime(detail.updated_at)}
              </span>
              <span style={{ color: '#8c8c8c' }}>事件</span>
              <span style={{ color: '#262626' }}>
                {detail.total_steps ?? '-'}
              </span>
              <span style={{ color: '#8c8c8c' }}>LLM</span>
              <span style={{ color: '#262626' }}>
                {detail.llm_call_count ?? '-'}
              </span>
              <span style={{ color: '#8c8c8c' }}>步数</span>
              <span style={{ color: '#262626' }}>
                {detail.total_steps ?? '-'}
              </span>
              <span style={{ color: '#8c8c8c' }}>模型</span>
              <span
                style={{
                  color: '#262626',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {detail.provider ?? '-'} / {detail.model ?? '-'}
              </span>
            </div>
          </div>
          <div
            style={{
              marginTop: 10,
              borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
              paddingTop: 8,
            }}
          >
            <Typography.Text
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: '#595959',
                borderLeft: `2px solid ${Colors.PRIMARY}`,
                paddingLeft: 6,
              }}
            >
              Token
            </Typography.Text>
            <Typography.Text
              style={{ fontSize: 12, display: 'block', marginTop: 4 }}
            >
              {(() => {
                const u = detail.accumulated_usage;
                return u
                  ? `prompt ${u.prompt_tokens ?? '-'} · completion ${u.completion_tokens ?? '-'} · total ${u.total_tokens ?? '-'}`
                  : '-';
              })()}
            </Typography.Text>
          </div>
          <div
            style={{
              marginTop: 10,
              borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
              paddingTop: 8,
            }}
          >
            <Typography.Text
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: '#595959',
                borderLeft: `2px solid ${Colors.PRIMARY}`,
                paddingLeft: 6,
              }}
            >
              工具汇总
            </Typography.Text>
            <Typography.Text
              style={{ fontSize: 12, display: 'block', marginTop: 4 }}
            >
              {detail.tool_stats && Object.keys(detail.tool_stats).length > 0
                ? Object.entries(detail.tool_stats)
                    .filter(([k]) => k !== 'null')
                    .map(([k, v]) => `${k}×${v}`)
                    .join(' · ')
                : '-'}
            </Typography.Text>
            {/* 折叠规范(小欧 2026-09-01): 三角统一▲▼、大小14(PRIMARY)、颜色PRIMARY#595959、位置数量后、方法role=button/aria-expanded/tabIndex/onKeyDown - 北京老陈定案，全页统一 */}
            <div
              role="button"
              tabIndex={0}
              aria-expanded={chainOpen}
              onClick={() => setChainOpen(!chainOpen)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  setChainOpen(!chainOpen);
                }
              }}
              style={{
                cursor: 'pointer',
                lineHeight: `${FontSize.PRIMARY + Spacing.XS}px`,
                marginTop: 4,
              }}
            >
              <span
                style={{
                  fontSize: FontSize.SECONDARY,
                  color: Colors.TEXT.PRIMARY,
                }}
              >
                工具调用链{chain.length ? ` (${chain.length}步)` : ''}
              </span>
              <span
                style={{
                  fontSize: FontSize.PRIMARY,
                  color: Colors.TEXT.PRIMARY,
                  marginLeft: 4,
                }}
              >
                {chainOpen ? '▲' : '▼'}
              </span>
            </div>
            {chainOpen && (
              <div style={{ marginTop: 4 }}>
                <Typography.Text style={{ fontSize: 12 }}>
                  {chainSeq}
                </Typography.Text>
                {chain.flatMap((s, sIdx) =>
                  (s.tools ?? []).map((t, tIdx) => (
                    <div
                      key={`${sIdx}-${tIdx}`}
                      style={{
                        fontSize: 12,
                        display: 'flex',
                        gap: 8,
                        marginTop: 2,
                      }}
                    >
                      <span style={{ color: '#8c8c8c', minWidth: 20 }}>
                        {sIdx + 1}.{tIdx + 1}
                      </span>
                      <span style={{ color: '#595959' }}>{t.tool}</span>
                      <span
                        style={{
                          color: '#8c8c8c',
                          fontFamily: 'monospace',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {JSON.stringify(t.params ?? {}).slice(0, 80)}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
          <div
            style={{
              marginTop: 10,
              borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
              paddingTop: 8,
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                marginTop: 4,
              }}
            >
              <Typography.Text
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: '#595959',
                  borderLeft: `2px solid ${Colors.PRIMARY}`,
                  paddingLeft: 6,
                }}
              >
                产出物
              </Typography.Text>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                {(detail.artifacts ?? []).length} 个
              </Typography.Text>
            </div>
            {(detail.artifacts ?? []).length > 0 ? (
              (detail.artifacts ?? []).map((a, i) => (
                <div
                  key={a.path}
                  style={{
                    display: 'flex',
                    gap: 8,
                    fontSize: 12,
                    lineHeight: '22px',
                  }}
                >
                  <span style={{ color: '#8c8c8c', minWidth: 16 }}>
                    {i + 1}
                  </span>
                  <span style={{ color: '#595959' }}>{a.tool_name || '-'}</span>
                  <span style={{ color: '#262626' }}>{a.name}</span>
                  <span style={{ color: '#8c8c8c', fontSize: 11 }}>
                    {a.type}
                  </span>
                  <span
                    style={{
                      color: '#595959',
                      fontFamily: 'monospace',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {a.path}
                  </span>
                </div>
              ))
            ) : (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                0 个 — 无产出物
              </Typography.Text>
            )}
          </div>
          {detail.error_message && (
            <div
              style={{
                marginTop: 10,
                borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
                paddingTop: 8,
              }}
            >
              <Typography.Text
                style={{
                  fontSize: 12,
                  background: '#fff1f0',
                  border: '1px solid #ffa39e',
                  borderRadius: 4,
                  padding: '2px 6px',
                  display: 'inline-block',
                }}
              >
                ⚠ [{detail.error_type}] {detail.error_message}
              </Typography.Text>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export { StaticStatsBlock };
