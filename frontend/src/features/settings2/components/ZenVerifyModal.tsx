// ZenVerifyModal — ZenithFree 双路验证结果弹框（北京老陈 2026-10-10）
//
// 排版契约（北京老陈「不能犬牙交错」）：每个模型一块，上下用 Divider 隔开；
//   块内三段定宽——模型名(左) · 两路状态(中) · 端点 Tag(右，定宽不折行)；
//   失败原因独占一行小字，长文截断 + title 悬停看全文。
// 样式全部走 settingsTokens/settingsControl + Colors 令牌，与设置页同源。
//
// 编辑历史:
//   2026-10-10 小欧 - 新建。双路对比结果列表 + 历史报告查看 — 小欧-2026-10-10
//   2026-10-10 小欧 - 端点改为各挂各的路（北京老陈指令「失败就是两个 endpoint 都失败 对比」）：
//     原实现无条件显示 adapter 的端点，exo-free 两路都挂却看着像走通了。故端点挂到各自那一路
//     状态后面，失败端点标红；第3列腾出来显示「双端通过/双端失败/两路分歧」。失败原因由单行
//     省略号改为整段折行完整展示（北京老陈「不能省略」） — 小欧-2026-10-10

import React, { useEffect, useState } from 'react';
import { Button, Divider, Empty, Modal, Tag } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsModalWidth } from '@/theme/settingsTokens';
import { ErrorType, showMessage } from '@/services/error/handler';
import {
  modelApi,
  type ZenReportItem,
  type ZenVerifyItem,
  type ZenVerifyResponse,
  type ZenVerdict,
} from '@/services/api/model.api';

/** 端点徽章定宽：两路纵向对齐不跳动（chat 4 字符 / responses 9 字符取后者） */
const ENDPOINT_TAG_WIDTH = 108;
/** 2026-10-10 小欧 - 单路状态文字定宽：不定则「200 OK」与「410✗」字宽不同，
 *  后面挂的端点标签起始位置随之左右错位（北京老陈要求显示规整），定宽后两路标签成列。 */
const SIDE_TEXT_WIDTH = 48;
/** 模型名列宽：两路状态改同一行并排后总宽收紧，模型名列随之收窄，
 *  最长模型名 muse-spark-1.2-contributor-free 仍需放得下，超出走省略号。 */
const MODEL_COL_WIDTH = 196;
const VERDICT_COL_WIDTH = 68;

const VERDICT_META: Record<
  ZenVerdict,
  { text: string; color: string; bg: string }
> = {
  both_pass: { text: '一致通过', color: Colors.SUCCESS, bg: 'transparent' },
  both_fail: { text: '一致失败', color: Colors.TEXT.SECONDARY, bg: 'transparent' },
  diverge: { text: '分歧', color: Colors.WARNING, bg: Colors.BG.WARNING_LIGHT },
  zen_unavailable: {
    text: '未比对',
    color: Colors.TEXT.TERTIARY,
    bg: 'transparent',
  },
};

const VERDICT_ICON: Record<ZenVerdict, string> = {
  both_pass: '✅',
  both_fail: '❌',
  diverge: '⚠️',
  zen_unavailable: '—',
};

/** 2026-10-10 小欧 - 第3列结论文字：端点各挂各的路后，这列改显「双端通过/双端失败/两路分歧」。 */
const VERDICT_TEXT: Record<ZenVerdict, string> = {
  both_pass: '双端通过',
  both_fail: '双端失败',
  diverge: '两路分歧',
  zen_unavailable: '未比对',
};

/** 两路侧的结果文案：状态码 + 通过标记；失败才带原因（下方独占行已展示） */
function sideText(s: ZenVerifyItem['zen_gate']): string {
  if (s.status === -1 && s.error.startsWith('zen_gate 库不可用')) return '库不可用';
  return `${s.status} ${s.ok ? 'OK' : '✗'}`;
}

/**
 * 2026-10-10 小欧 - 端点徽章挂到各自那一路后面（北京老陈指令）：
 *   失败时该路端点标红（原实现无条件显示 adapter 端点，失败行看着像走通了）。
 *   走通的端点才配彩色，失败端点用红色 Tag 表示「此路失败」。
 *   两路端点归一化：zen_gate 库返回 'chat'、adapter 返回 '/chat/completions'，
 *   同一端点两种写法会让两行标签长短不一（北京老陈要求显示规整），统一补成完整路径。
 */
function endpointTag(endpoint: string, ok: boolean) {
  if (!endpoint) return null;
  /** zen_gate 库用 chat/responses 简称，adapter 用完整路径，统一到完整路径 */
const ENDPOINT_ALIAS: Record<string, string> = {
  chat: '/chat/completions',
  responses: '/responses',
};
const path = endpoint.startsWith('/')
  ? endpoint
  : (ENDPOINT_ALIAS[endpoint] ?? endpoint);
  return (
    <Tag
      color={ok ? (path === '/responses' ? 'purple' : 'blue') : 'red'}
      style={{
        display: 'inline-block',
        width: ENDPOINT_TAG_WIDTH,
        margin: 0,
        marginLeft: Spacing.XS,
        textAlign: 'center',
        fontFamily: 'monospace',
        whiteSpace: 'nowrap',
      }}
    >
      {path}
    </Tag>
  );
}

const ZenVerifyModal: React.FC<{
  open: boolean;
  provider: string;
  result: ZenVerifyResponse | null;
  onClose: () => void;
}> = ({ open, provider, result, onClose }) => {
  const [reports, setReports] = useState<ZenReportItem[]>([]);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyName, setHistoryName] = useState('');
  const [historyText, setHistoryText] = useState('');

  // 打开时拉历史报告清单（当前结果由父组件点击时已拿到）
  useEffect(() => {
    if (!open) return;
    void modelApi.zenVerifyReports().then((r) => {
      if (r.ok) setReports(r.reports);
    });
  }, [open]);

  const openHistory = async (name: string) => {
    const r = await modelApi.zenVerifyReport(name);
    if (!r.ok || !r.content) {
      showMessage(ErrorType.WARNING, r.message || '读取报告失败');
      return;
    }
    setHistoryName(name);
    setHistoryText(r.content);
  };

  return (
    <>
      <Modal
        open={open}
        onCancel={onClose}
        footer={
          <>
            <Button key="history" onClick={() => setHistoryOpen(true)}>
              查看历史
            </Button>
            <Button key="close" type="primary" onClick={onClose}>
              关闭
            </Button>
          </>
        }
        width={settingsModalWidth.display}
        title={
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            ZenithFree 双路验证 — {provider}
          </span>
        }
      >
        {/* 空态：本次无结果（接口失败时父组件不传 result） */}
        {!result || result.results.length === 0 ? (
          <Empty description={result?.message || '本次无验证结果'} />
        ) : (
          <div style={{ fontSize: FontSize.SECONDARY }}>
            {result.results.map((r, idx) => {
              const meta = VERDICT_META[r.verdict];
              const reason = r.zen_gate.error || r.adapter.error || '';
              const isDiverged = r.verdict === 'diverge';
              return (
                <div key={r.model}>
                  {idx > 0 && <Divider style={{ margin: `${Spacing.SM}px 0` }} />}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: Spacing.SM,
                    }}
                  >
                    {/* 段1 模型名 */}
                    <span
                      style={{
                        width: MODEL_COL_WIDTH,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        color: Colors.TEXT.PRIMARY,
                      }}
                    >
                      {VERDICT_ICON[r.verdict]} {r.model}
                    </span>
                    {/* 段2 两路状态 + 各挂各的端点徽章（2026-10-10 小欧·北京老陈指令）
                        失败行原来无条件挂 adapter 的端点，exo-free 两路都挂却看着像走通了 ——
                        该端点应挂在它自己的那一路后面，失败即该路端点标红，两路成败一眼可比。
                        两路改为同一行左右并排（北京老陈指令「两个显示在一行上」），
                        标签统一按各自固定宽度对齐，不再上下堆叠占两倍行高 */}
                    <span
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: Spacing.SM,
                        color: Colors.TEXT.SECONDARY,
                      }}
                    >
                      <span style={{ whiteSpace: 'nowrap' }}>
                        zen_gate{' '}
                        <span
                          style={{
                            display: 'inline-block',
                            width: SIDE_TEXT_WIDTH,
                          }}
                        >
                          {sideText(r.zen_gate)}
                        </span>
                      </span>
                      {endpointTag(r.zen_gate.endpoint, r.zen_gate.ok)}
                      <span style={{ whiteSpace: 'nowrap' }}>
                        adapter{' '}
                        <span
                          style={{
                            display: 'inline-block',
                            width: SIDE_TEXT_WIDTH,
                          }}
                        >
                          {sideText(r.adapter)}
                        </span>
                      </span>
                      {endpointTag(r.adapter.endpoint, r.adapter.ok)}
                    </span>
                    {/* 段3 结果结论（定宽，不用裸字） */}
                    <span
                      style={{
                        width: VERDICT_COL_WIDTH,
                        marginLeft: 'auto',
                        textAlign: 'right',
                      }}
                    >
                      {VERDICT_TEXT[r.verdict]}
                    </span>
                  </div>
                  {/* 原因独占一行（小字次要色），完整折行不省略 */}
                  {reason && (
                    <div
                      style={{
                        marginTop: Spacing.XS,
                        paddingLeft: MODEL_COL_WIDTH + Spacing.SM,
                        color: Colors.TEXT.TERTIARY,
                        // 2026-10-10 小欧 - 原因完整折行显示（北京老陈指令「不能省略」）：
                        //   原 nowrap+ellipsis 压成一行须悬停才看全，现按容器宽度整段换行展示，
                        //   不做行数截断（行数上限仍靠后端 200 字符截断控制，不会撑爆弹框）
                        whiteSpace: 'normal',
                        wordBreak: 'break-all',
                      }}
                    >
                      原因 {reason}
                    </div>
                  )}
                  {isDiverged && (
                    <div
                      style={{
                        marginTop: Spacing.XS,
                        paddingLeft: MODEL_COL_WIDTH + Spacing.SM,
                        padding: `${Spacing.XS}px ${Spacing.SM}px`,
                        color: meta.color,
                        background: meta.bg,
                        borderRadius: 4,
                      }}
                    >
                      两路结果不一致 —— 可能是 zen_gate 已更新配方而 adapter 未跟上
                    </div>
                  )}
                </div>
              );
            })}
            {/* 汇总条 */}
            <Divider style={{ margin: `${Spacing.SM}px 0` }} />
            <div style={{ color: Colors.TEXT.SECONDARY }}>
              {VERDICT_ICON.both_pass} 一致通过 {result.summary.both_pass} ·{' '}
              {VERDICT_ICON.both_fail} 一致失败 {result.summary.both_fail} ·{' '}
              {VERDICT_ICON.diverge} 分歧 {result.summary.diverge}
              {result.summary.zen_unavailable > 0 &&
                ` · 未比对 ${result.summary.zen_unavailable}`}
              {result.summary.source === 'configured' && (
                <span style={{ color: Colors.WARNING }}>
                  {' '}
                  （远端拉取失败，已回落已配置模型）
                </span>
              )}
            </div>
            {result.report_path && (
              <div
                title={result.report_path}
                style={{
                  marginTop: Spacing.XS,
                  color: Colors.TEXT.TERTIARY,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                报告已保存 {result.report_path}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* 历史报告列表 + 内容 */}
      <Modal
        open={historyOpen}
        onCancel={() => setHistoryOpen(false)}
        footer={null}
        width={settingsModalWidth.form}
        title={
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            历史验证报告
          </span>
        }
      >
        <div style={{ maxHeight: 360, overflow: 'auto' }}>
          {reports.length === 0 ? (
            <Empty description="暂无历史报告" />
          ) : (
            reports.map((f) => (
              <div
                key={f.name}
                onClick={() => void openHistory(f.name)}
                title={f.name}
                style={{
                  padding: `${Spacing.XS}px ${Spacing.SM}px`,
                  cursor: 'pointer',
                  borderRadius: 4,
                  color:
                    f.name === historyName
                      ? Colors.PRIMARY
                      : Colors.TEXT.PRIMARY,
                  background:
                    f.name === historyName ? Colors.BG.SECONDARY : 'transparent',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {f.name}
              </div>
            ))
          )}
        </div>
        {historyText && (
          <>
            <Divider style={{ margin: `${Spacing.SM}px 0` }} />
            <pre
              style={{
                margin: 0,
                maxHeight: 260,
                overflow: 'auto',
                fontSize: FontSize.CODE,
                color: Colors.TEXT.SECONDARY,
                whiteSpace: 'pre',
              }}
            >
              {historyText}
            </pre>
          </>
        )}
      </Modal>
    </>
  );
};

export default ZenVerifyModal;