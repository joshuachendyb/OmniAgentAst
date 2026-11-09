// 编辑历史: 2026-11-09 小欧 - 新建：② 输入图片能力验证行（三徽标/定论/逐腿 tip/验证按钮）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import { Button, Tooltip } from 'antd';
import { Spacing } from '@/utils/stepStyles';
import { settingsRowStyle, settingsControl } from '@/theme/settingsTokens';
import type { MediaProbe, ProbeLastRec } from '@/services/api/model.api';
import { mediaProbeView } from '../utils/probeView';
import { HelpLabel, TipContent } from './Hint';
import { BadgeRow, LegBadge, VerdictBadge } from './LegBadge';
import { LastProbeMemo } from './ProbeMemo';

interface Props {
  media?: MediaProbe;
  lastProbe?: ProbeLastRec;
  chatLegMuted: boolean;
  imageChecked: boolean;
  saving: boolean;
  probing: boolean;
  genProbing: boolean;
  onProbe: () => void;
}

export const ModelTabMediaProbe: React.FC<Props> = ({
  media,
  lastProbe,
  chatLegMuted,
  imageChecked,
  saving,
  probing,
  genProbing,
  onProbe,
}) => {
  const view = mediaProbeView(media, { imageChecked, chatLegMuted });

  return (
    <div style={settingsRowStyle}>
      {/* 行名 tip = 固定验证方法说明；徽标 tip 只留定论/耗时/取证，避免两处重复 */}
      <HelpLabel
        title={
          chatLegMuted ? (
            '生成模型：图片输入/输出走生成专用端点（如 /v1/images/generations），chat 腿 400 为预期；图片能力请点「生成验证」实测'
          ) : (
            <TipContent title="验证方法说明">
              <div>
                真实调用 LLM 发送一张内置测试图，HTTP 200 且返回图像
                token&gt;0（厂商不报图像 token 时按「带图输入 token
                明显高于纯文本」）才算「输出能力」正常
              </div>
              <div>内联＝图片数据直接随请求体发送（base64）</div>
              <div>外链＝只发图片地址，由厂商接口自行抓取</div>
              <div>
                {view.urlTested
                  ? '外链已取证——测试图片地址由厂商接口实际抓取成功，图片地址可随请求转发'
                  : view.urlErr
                    ? '外链未取证——外链腿已请求，厂商侧抓图失败（网络超时或不可达），不判对错；可再点「验证」重试'
                    : '外链未取证——本次验证时上方「Image_URL」为空，外链腿未发起请求；填好地址再点「验证」即出对/错'}
              </div>
            </TipContent>
          )
        }
      >
        输入图片能力验证
      </HelpLabel>
      <Tooltip
        title={
          <TipContent>
            <div>{view.verdictLine}</div>
            {media?.probed_at && (
              <>
                <div>
                  图片 token＝厂商把图片折算的输入 token，&gt;0＝图真进了上下文
                </div>
                <div>内联腿：{view.inlineLeg}</div>
                <div>外链腿：{view.urlLeg}</div>
                <div style={{ opacity: 0.85 }}>
                  验证时间 {media.probed_at.replace('T', ' ')}
                </div>
              </>
            )}
          </TipContent>
        }
      >
        <BadgeRow>
          {/* chat 腿不适用时整组不出，只留定论词，免得灰徽标被读成「未验证」 */}
          {!chatLegMuted && (
            <>
              <LegBadge label="内联" state={view.inlineState} />
              <LegBadge label="外链" state={view.urlState} />
            </>
          )}
          {view.verdictWord !== null && (
            <VerdictBadge
              caption="输出能力"
              word={view.verdictWord}
              state={view.inlineState}
            />
          )}
        </BadgeRow>
      </Tooltip>
      {/* 按钮紧跟结论；x 由结论区定宽锚定，四态文案长短不使按钮搬家 */}
      {!chatLegMuted && (
        <Tooltip
          title={
            !imageChecked ? (
              '未勾选「图片」输入模态，当前不发图，无从验证'
            ) : (
              <TipContent maxWidth={380}>
                <div>真实发送一张内置测试图，结论写回本行</div>
                <div>
                  外链取证：先在上方「Image_URL」填公网图片地址，再点「验证」
                </div>
              </TipContent>
            )
          }
        >
          <span style={{ marginLeft: Spacing.SM, display: 'inline-flex' }}>
            <Button
              style={{ width: settingsControl.actionBtnWidth }}
              loading={probing}
              disabled={saving || !imageChecked || genProbing}
              onClick={onProbe}
            >
              验证
            </Button>
          </span>
        </Tooltip>
      )}
      {/* 未出定论时把上次尝试原因贴在按钮右侧，刷新不丢 */}
      {!view.accept && <LastProbeMemo rec={lastProbe} />}
    </div>
  );
};
