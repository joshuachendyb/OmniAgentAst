/**
 * TitleStreamIcon - 顶栏品牌圈圈联动流状态: 只表达"节奏"(停/快/慢), 文字/颜色/秒数仍归 StreamStatusPill。 @author 小欧 @date 2026-11-03
 */
// 编辑历史: 2026-11-03 06:40:41 小欧 - 新建: 订阅 useStreamPulse(与流状态胶囊同一真源), phase 直挂 CSS 类 spin-<phase>;
//   8 档转速是视觉值留在 index.css, 本文件零秒数零颜色, 只做 phase→类名 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 12:58:00 小欧 - 增 foregroundSessionId 入参: 圈圈只表达当前会话的节奏,
//   并行会话不上镜(与胶囊/钟面同源同主语), 由 AppLayout 透传 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 14:30:00 小欧 - 入参改名 subject(PulseSubject): 非会话页为主语 LATEST_RUNNING — 小欧-2026-11-03
import React from 'react';

import { useStreamPulse } from '../../features/chat/hooks/useStreamPulse';
import type { PulseSubject } from '../../features/chat/streams/chatStreamStore';
import { TitleSpinIcon } from '../AnimatedIcons';

interface TitleStreamIconProps {
  /** 顶栏主语: 会话页=页面发布的会话 id(可为 null → 圈圈停); 非会话页=LATEST_RUNNING */
  subject: PulseSubject;
}

export const TitleStreamIcon: React.FC<TitleStreamIconProps> = ({
  subject,
}) => {
  // 2026-11-03 小欧 - 订阅放在本层而非 AppLayout: view 的秒数每秒换引用,
  //   放壳层会让整个顶栏 1Hz 重渲, 放这里重渲范围只有 20px 图标 — 小欧-2026-11-03
  const view = useStreamPulse(subject);
  return <TitleSpinIcon className={`spin-${view.phase}`} />;
};
