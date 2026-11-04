// CountdownRing.tsx — countdown/progress隔离,防每秒扩散到工具卡/参数卡/按钮
// 编辑历史: 2026-09-16 老杨 - 拆分CountdownRing子组件,React.memo隔离重渲染 - 老杨-2026-09-16
// 编辑历史: 2026-09-16 小欧 - 修复: React.FC+memo内联解构致react/prop-types误报2error, 对齐ErrorDetail.tsx惯例文件级disable - 小欧-2026-09-16
// 编辑历史: 2026-09-18 小欧 - 恢复圆圈倒计时(北京老陈令): 回退a59aaff8e的扁平纯文本, 恢复Progress circle饼环+双层格式化div嵌套, 恢复confirmTimeout prop - 小欧-2026-09-18
// 编辑历史: 2026-10-11 00:55:20 小欧 - 直径可调(北京老陈「计时钟不能删除但可以改变位置」配套): 新增 size prop(默认 60), 数字随环缩放, 供标题行右侧 44px 调用(见 index.tsx 同批) — 小欧-2026-10-11
/* eslint-disable react/prop-types */

import React from 'react';
import { Progress } from 'antd';

interface CountdownRingProps {
  countdown: number;
  confirmTimeout: number;
  /**
   * 2026-10-11 00:20 小欧 - 直径可调（北京老陈："弹框中的计时钟不能删除，但是可以改变位置"）。
   * 原为写死 60px 独占一整行居中，倒计时这个**辅助信息**占了确认弹框最大的视觉权重——
   * 用户该先看"要我确认什么"，其次才是"还有多久自动放行"。改为可传入更小直径，
   * 挪到标题行右侧（视线终点）后缩到 44，与次级信息同一量级。
   */
  size?: number;
}

const CountdownRing: React.FC<CountdownRingProps> = React.memo(
  ({ countdown, confirmTimeout, size = 60 }) => {
    const progressPercent =
      confirmTimeout > 0 ? Math.round((countdown / confirmTimeout) * 100) : 0;
    const strokeColor =
      countdown <= 3 ? '#fa541c' : countdown <= 5 ? '#faad14' : '#1677ff';
    // 数字随环一起缩，避免 60→44 后数字撑破圆环
    const numFont = Math.round(size * 0.36);

    return (
      <div style={{ textAlign: 'center', marginBottom: 4 }}>
        <Progress
          type="circle"
          size={size}
          percent={progressPercent}
          strokeColor={strokeColor}
          strokeWidth={size > 50 ? 5 : 4}
          format={() => (
            <div style={{ textAlign: 'center', lineHeight: 1.2 }}>
              <div
                style={{
                  fontSize: numFont,
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
