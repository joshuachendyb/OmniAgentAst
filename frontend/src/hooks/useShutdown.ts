// 编辑历史: 2026-11-16 小欧 - 新建: 后端停机动作共享 hook(确认弹窗 + 调用 + 加载态), 供设置卡与侧栏按钮复用, 收敛重复逻辑(DRY) — 小欧-2026-11-16
import { useState } from 'react';
import { Modal } from 'antd';

import { systemApi } from '@/services/api/system.api';
import { handleApiError, showSuccess } from '@/services/error/handler';

export interface UseShutdown {
  /** 停机请求进行中(供按钮禁用/加载态) */
  loading: boolean;
  /** 弹出二次确认并执行优雅停机 */
  requestShutdown: () => void;
}

/**
 * 后端优雅停机动作共享 hook —— 2026-11-16 小欧
 *
 * 停机是低频不可逆高危动作, 所有入口(设置卡 / 侧栏按钮)必须走同一套
 * 「二次确认 + 成功/失败提示」, 故把动作收敛到这里, 避免多处复制(DRY)。
 */
export const useShutdown = (): UseShutdown => {
  const [loading, setLoading] = useState(false);

  const doShutdown = async () => {
    setLoading(true);
    try {
      await systemApi.shutdown();
      showSuccess('已请求关闭后端服务, 后端即将退出, 可关闭本页面');
    } catch (e) {
      handleApiError(e);
    } finally {
      setLoading(false);
    }
  };

  const requestShutdown = () => {
    Modal.confirm({
      title: '确认关闭后端服务?',
      content:
        '关闭后正在执行的任务会被中断, 且本页面将失去连接, 需重新启动程序才能继续使用。',
      okText: '确认关闭',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: doShutdown,
    });
  };

  return { loading, requestShutdown };
};
