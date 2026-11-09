// 编辑历史: 2026-11-09 小欧 - 新建：② 生成能力验证行（逐腿徽标/结论词/汇总句/生成验证按钮）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import { Button, Tooltip } from 'antd';
import { Spacing } from '@/utils/stepStyles';
import { settingsRowStyle, settingsControl } from '@/theme/settingsTokens';
import type { MediaProbe, ProbeLastRec } from '@/services/api/model.api';
import { genProbeView } from '../utils/probeView';
import { HelpLabel, TipContent } from './Hint';
import { BadgeRow, LegBadge, VerdictBadge } from './LegBadge';
import { LastProbeMemo } from './ProbeMemo';

interface Props {
  media?: MediaProbe;
  lastProbe?: ProbeLastRec;
  outputModalities: string[];
  saving: boolean;
  probing: boolean;
  genProbing: boolean;
  onProbe: () => void;
}

export const ModelTabGenProbe: React.FC<Props> = ({
  media,
  lastProbe,
  outputModalities,
  saving,
  probing,
  genProbing,
  onProbe,
}) => {
  const view = genProbeView(media, outputModalities);

  return (
    <div style={settingsRowStyle}>
      <HelpLabel
        title={
          <TipContent title="验证方法说明">
            <div>
              真实调用厂商生成端点：文生＝只发一段提示词；图生＝附一张公网图作输入；返回产物地址才算通过
            </div>
            <div>
              图片腿走 /images/generations（秒级）；视频腿走 /videos
              异步任务，提交后轮询取产物，排队时长取决于厂商，超时只记「未完成」不下能力结论
            </div>
            <div>
              按模型声明的输出模态出现对应腿：image → 文生图／图生图，video →
              文生视频／图生视频
            </div>
          </TipContent>
        }
      >
        生成能力验证
      </HelpLabel>
      <Tooltip
        title={
          <TipContent>
            <div>{view.verdict}</div>
            {view.hasRecord && (
              <>
                {view.legs
                  .filter((l) => l.tip)
                  .map((l) => (
                    <div key={l.label}>{l.tip}</div>
                  ))}
                {view.probedAt && (
                  <div style={{ opacity: 0.85 }}>
                    验证时间 {view.probedAt.replace('T', ' ')}
                  </div>
                )}
              </>
            )}
          </TipContent>
        }
      >
        <BadgeRow>
          {view.legs.map((l) => (
            <LegBadge key={l.label} label={l.label} state={l.state} />
          ))}
          <VerdictBadge
            caption="生成能力"
            word={view.verdictWord}
            state={view.wordState}
          />
        </BadgeRow>
      </Tooltip>
      <span style={{ marginLeft: Spacing.SM, display: 'inline-flex' }}>
        <Button
          style={{ width: settingsControl.actionBtnWidth }}
          loading={genProbing}
          disabled={saving || probing}
          onClick={onProbe}
        >
          生成验证
        </Button>
      </span>
      {/* 有未定/被拒腿时，上次原因贴按钮右侧（排队满/需登录/超时） */}
      {lastProbe?.ok === false && <LastProbeMemo rec={lastProbe} />}
    </div>
  );
};
