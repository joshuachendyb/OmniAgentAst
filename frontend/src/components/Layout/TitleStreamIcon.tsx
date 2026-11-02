/**
 * TitleStreamIcon - 顶栏品牌圈圈联动流状态: 只表达"节奏"(停/快/慢)。
 * 文字、颜色、秒数仍归 StreamStatusPill, 一处一个通道, 不重复。
 *
 * @author 小欧
 * @date 2026-11-03
 */
// 编辑历史: 2026-11-03 06:40:41 小欧 - 新建: 订阅 useStreamPulse(与流状态胶囊同一真源), phase 直挂 CSS 类 spin-<phase>;
//   8 档转速是视觉值留在 index.css, 本文件零秒数零颜色, 只做 phase→类名 — 小欧-2026-11-03
import React from 'react';

import { useStreamPulse } from '../../features/chat/hooks/useStreamPulse';
import { TitleSpinIcon } from '../AnimatedIcons';

export const TitleStreamIcon: React.FC = () => {
  // 2026-11-03 小欧 - 订阅放在本层而非 AppLayout: view 的秒数每秒换引用,
  //   放壳层会让整个顶栏 1Hz 重渲, 放这里重渲范围只有 20px 图标 — 小欧-2026-11-03
  const view = useStreamPulse();
  return <TitleSpinIcon className={`spin-${view.phase}`} />;
};
