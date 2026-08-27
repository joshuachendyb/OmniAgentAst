import type React from 'react';
// 编辑历史: 2026-08-27 小欧 - 三堂会审去框-P1-1(B1): 抽工具视图外层容器token, 去22视图外框留内框(对齐"内容即容器")
/**
 * viewOuter - 工具结果视图外层容器去框化白名单（6.3.4 最小改动方案）
 * 外层透明无框，仅保留内层列表/代码块的 #fafafa / #1e1e1e 背景与 radius6。
 * @author 小欧
 * @date 2026-08-27
 */
export const viewOuter: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  borderRadius: 0,
  padding: '4px 0',
  marginTop: 4,
};
