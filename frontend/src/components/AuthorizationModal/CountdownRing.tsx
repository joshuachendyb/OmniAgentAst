// CountdownRing.tsx — countdown隔离的扁平纯文本显示
// 编辑历史: 2026-09-16 老杨 - 拆分CountdownRing子组件,React.memo隔离重渲染 - 老杨-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: React.FC+memo内联解构致react/prop-types误报2error, 对齐ErrorDetail.tsx惯例文件级disable - 小欧-2026-09-16
// 编辑历史: 2026-09-18 小欧 - 审核整改: "秒"字 #8c8c8c→#262626 去灰字, 与弹窗高亮规范一致 - 小欧-2026-09-18
// 编辑历史: 2026-09-18 小欧 - 审核整改(KISS-DIRECT): 去Progress circle复杂控件(饼环+双层格式化div嵌套), 改扁平纯文本大数字+秒;
//   删除confirmTimeout prop(环形进度已删, YAGNI), memo仅依赖countdown - 小欧-2026-09-18
/* eslint-disable react/prop-types */

import React from 'react';

interface CountdownRingProps {
  countdown: number;
}

const CountdownRing: React.FC<CountdownRingProps> = React.memo(
  ({ countdown }) => {
    const color = countdown <= 3 ? '#fa541c' : '#333';
    return (
      <div style={{ textAlign: 'center', marginBottom: 2 }}>
        <span
          style={{
            fontSize: 22,
            fontWeight: 600,
            color,
            animation:
              countdown <= 3 ? 'pulse 0.8s ease-in-out infinite' : 'none',
          }}
        >
          {countdown}
        </span>
        <span style={{ fontSize: 12, color: '#262626', marginLeft: 2 }}>
          秒
        </span>
      </div>
    );
  }
);

CountdownRing.displayName = 'CountdownRing';
export default CountdownRing;
