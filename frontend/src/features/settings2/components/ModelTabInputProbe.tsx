// 编辑历史: 2026-11-11 小欧 - 新建：输入能力验证行统一渲染（图片/视频/音频三行合并，自 ModelTabMediaProbe
//   + ModelTabModalityProbe 吸收归一；差异全部由 inputProbeView 以数据表达，本组件零 kind 分支）— 小欧-2026-11-11
// 2026-11-11 小欧 - 注释勘误: VerdictBadge caption "输出能力"→"输入能力"(输入验证行结论词) — 小欧-2026-11-11
import React from 'react';
import { Button, Tooltip } from 'antd';
import { Spacing } from '@/utils/stepStyles';
import { settingsRowStyle, settingsControl } from '@/theme/settingsTokens';
import type { MediaProbe, ProbeLastRec } from '@/services/api/model.api';
import { inputProbeView, type InputProbeKind } from '../utils/probeView';
import { HelpLabel, TipContent } from './Hint';
import { BadgeRow, LegBadge, VerdictBadge } from './LegBadge';
import { LastProbeMemo } from './ProbeMemo';

interface Props {
  kind: InputProbeKind;
  /** 图片=平铺字段（accept/inline_ms/url_ms…），视频/音频=media[kind] 单腿记录 */
  media?: MediaProbe;
  lastProbe?: ProbeLastRec;
  checked: boolean;
  /** 仅图片行：生成模型未声明图片输入时 chat 腿不适用（收腿/收按钮） */
  chatLegMuted?: boolean;
  saving: boolean;
  probing: boolean;
  genProbing: boolean;
  onProbe: () => void;
}

export const ModelTabInputProbe: React.FC<Props> = ({
  kind,
  media,
  lastProbe,
  checked,
  chatLegMuted,
  saving,
  probing,
  genProbing,
  onProbe,
}) => {
  const view = inputProbeView(kind, media, {
    checked,
    chatLegMuted: chatLegMuted ?? false,
  });

  return (
    <div style={settingsRowStyle}>
      {/* 行名 tip = 固定验证方法说明；徽标 tip 只留定论/耗时/取证，避免两处重复 */}
      <HelpLabel
        title={
          view.methodText ?? (
            <TipContent title="验证方法说明">
              {view.methodLines.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </TipContent>
          )
        }
      >
        {view.rowLabel}
      </HelpLabel>
      <Tooltip
        title={
          <TipContent>
            <div>{view.verdictLine}</div>
            {view.detailLines.map((d, i) => (
              <div
                key={i}
                style={{
                  opacity: d.weak ? 0.85 : undefined,
                  wordBreak: d.breakAll ? 'break-all' : undefined,
                }}
              >
                {d.text}
              </div>
            ))}
          </TipContent>
        }
      >
        <BadgeRow>
          {/* 腿空数组（图片行 chat 腿不适用）时整组不出，只留定论词，免得灰徽标被读成「未验证」 */}
          {view.legs.map((l) => (
            <LegBadge key={l.label} label={l.label} state={l.state} />
          ))}
          {view.verdictWord !== null && (
            <VerdictBadge
              caption="输入能力"
              word={view.verdictWord}
              state={view.verdictState}
            />
          )}
        </BadgeRow>
      </Tooltip>
      {/* 按钮紧跟结论；x 由结论区定宽锚定，四态文案长短不使按钮搬家 */}
      {view.buttonVisible && (
        <Tooltip
          title={
            view.buttonBlocked ? (
              view.buttonBlockedTip
            ) : (
              <TipContent maxWidth={380}>
                {view.buttonGoLines.map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
              </TipContent>
            )
          }
        >
          <span style={{ marginLeft: Spacing.SM, display: 'inline-flex' }}>
            <Button
              style={{ width: settingsControl.actionBtnWidth }}
              loading={probing}
              disabled={saving || view.buttonBlocked || genProbing}
              onClick={onProbe}
            >
              验证
            </Button>
          </span>
        </Tooltip>
      )}
      {/* 未出定论时把上次尝试原因贴在按钮右侧，刷新不丢 */}
      {view.memoVisible && <LastProbeMemo rec={lastProbe} />}
    </div>
  );
};
