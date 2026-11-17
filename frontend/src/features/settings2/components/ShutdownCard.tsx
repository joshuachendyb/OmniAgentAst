// 编辑历史: 2026-11-16 小欧 - 新建: 设置页「服务」卡, 提供前端关闭后端服务入口(优雅停机) — 小欧-2026-11-16
// 2026-11-16 小欧 - 版式优化: 标题「服务」→「后端服务」; 改高危操作警示卡版式(区块标题在框外、框内左说明右动作, 与 CurrentModelRefCard 区块标题对齐) — 小欧-2026-11-16
// 2026-11-16 小欧 - 停机动作下沉共享 hook(useShutdown), 本卡只负责展示, 与侧栏按钮复用同一套确认/调用逻辑(DRY) — 小欧-2026-11-16
// 2026-11-16 小欧 - 注释同步: 删除"仅设置页/避免误触"的过期表述, 改为设置页与侧栏双入口共用 useShutdown 的一致说明 — 小欧-2026-11-16
import React from 'react';
import { Button, Typography } from 'antd';
import { PoweroffOutlined } from '@ant-design/icons';

import { useShutdown } from '@/hooks/useShutdown';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsRadius } from '@/theme/settingsTokens';

/**
 * 后端服务卡 —— 设置页「常规」Tab 底部, 提供「关闭服务」按钮。
 *
 * 设置页入口负责"发现与理解": 展示后果说明, 适合低频操作前的确认;
 * 侧栏底部另设同功能快捷入口, 二者共用 useShutdown, 二次确认与提示一致。
 *
 * 版式: 区块标题在框外(与同页「当前系统全局使用模型」同一基准), 框内
 * 「危险图标 + 后果说明」居左、「关闭服务」危险按钮贴右 —— 动作贴着它作用的对象,
 * 浅红底/红框仅表达"不可逆高危"语义, 不喧宾夺主。
 */
export const ShutdownCard: React.FC = () => {
  const { loading, requestShutdown } = useShutdown();

  return (
    <div>
      <div
        style={{
          fontSize: FontSize.PRIMARY,
          fontWeight: FontWeight.BOLD,
          marginBottom: Spacing.SM,
        }}
      >
        后端服务
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.LG,
          padding: `${Spacing.MD}px ${Spacing.LG}px`,
          marginBottom: Spacing.LG,
          background: Colors.ERROR_BG,
          border: `1px solid ${Colors.ERROR_BORDER}`,
          borderRadius: settingsRadius.SM,
        }}
      >
        <PoweroffOutlined
          style={{ fontSize: FontSize.SUBHEAD, color: Colors.ERROR_TEXT }}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: FontSize.PRIMARY,
              fontWeight: FontWeight.MEDIUM,
              color: Colors.TEXT.STRONG,
            }}
          >
            关闭后端服务进程
          </div>
          <Typography.Paragraph
            type="secondary"
            style={{
              margin: `${Spacing.XS}px 0 0`,
              fontSize: FontSize.SECONDARY,
            }}
          >
            优雅退出: 先终止后台任务并释放数据库连接。
            关闭后前台页面将无法继续使用, 需重新启动程序。
          </Typography.Paragraph>
        </div>
        <Button danger loading={loading} onClick={requestShutdown}>
          关闭服务
        </Button>
      </div>
    </div>
  );
};

export default ShutdownCard;
