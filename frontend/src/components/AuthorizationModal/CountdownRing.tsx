// CountdownRing.tsx — countdown/progress隔离,防每秒扩散到工具卡/参数卡/按钮
// 编辑历史: 2026-09-16 老杨 - 拆分CountdownRing子组件,React.memo隔离重渲染 - 老杨-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: React.FC+memo内联解构致react/prop-types误报2error, 对齐ErrorDetail.tsx惯例文件级disable - 小欧-2026-09-16
// 编辑历史: 2026-09-18 小欧 - 恢复圆圈倒计时(北京老陈令): 回退a59aaff8e的扁平纯文本, 恢复Progress circle饼环+双层格式化div嵌套, 恢复confirmTimeout prop - 小欧-2026-09-18
/* eslint-disable react/prop-types */

import React from 'react';
import { Progress } from 'antd';

interface CountdownRingProps {
  countdown: number;
  confirmTimeout: number;
}

const CountdownRing: React.FC<CountdownRingProps> = React.memo(
  ({ countdown, confirmTimeout }) => {
    const progressPercent =
      confirmTimeout > 0 ? Math.round((countdown / confirmTimeout) * 100) : 0;
    const strokeColor =
      countdown <= 3 ? '#fa541c' : countdown <= 5 ? '#faad14' : '#1677ff';

    return (
      <div style={{ textAlign: 'center', marginBottom: 4 }}>
        <Progress
          type="circle"
          size={60}
          percent={progressPercent}
          strokeColor={strokeColor}
          strokeWidth={5}
          format={() => (
            <div style={{ textAlign: 'center', lineHeight: 1.2 }}>
              <div
                style={{
                  fontSize: 22,
                  fontWeight: 600,
                  color: countdown <= 3 ? '#fa541c' : '#333',
                  animation:
                    countdown <= 3 ? 'pulse 0.8s ease-in-out infinite' : 'none',
                }}
              >
                {countdown}
              </div>
              <div style={{ fontSize: 11, color: '#8c8c8c' }}>秒</div>
            </div>
          )}
        />
      </div>
    );
  }
);

CountdownRing.displayName = 'CountdownRing';
export default CountdownRing;
