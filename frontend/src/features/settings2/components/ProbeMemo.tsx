// 编辑历史: 2026-11-09 小欧 - 新建：未出定论的上次验证回执常驻短语（两条实测腿共用） — 小欧-2026-11-09
import React from 'react';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import type { ProbeLastRec } from '@/services/api/model.api';

/** 贴在「验证」按钮右侧的行内短语：谁失败、什么时候、后端原句，不另起一行 */
export const LastProbeMemo: React.FC<{ rec?: ProbeLastRec }> = ({ rec }) =>
  rec?.message ? (
    <span
      style={{
        flex: 1,
        minWidth: 0,
        marginLeft: Spacing.SM,
        fontSize: FontSize.SECONDARY,
        lineHeight: 1.6,
        color: rec.ok ? Colors.TEXT.SECONDARY : Colors.WARNING,
      }}
    >
      上次验证 {rec.at ? rec.at.replace('T', ' ') : '—'}：{rec.message}
    </span>
  ) : null;
