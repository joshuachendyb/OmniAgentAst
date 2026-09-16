// CountdownRing.tsx — countdown/progress隔离,防每秒扩散到工具卡/参数卡/按钮
// 编辑历史: 2026-09-16 老杨 - 拆分CountdownRing子组件,React.memo隔离重渲染 - 老杨-2026-09-16

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
                    countdown <= 3
                      ? 'pulse 0.8s ease-in-out infinite'
                      : 'none',
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
