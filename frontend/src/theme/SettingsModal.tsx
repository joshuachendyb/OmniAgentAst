// 编辑历史: 2026-10-10 小欧 - 文档[16] 设置页弹窗统一化审计后新建：设置页弹窗标准壳（SettingsModal）
//   归一化四件事（原先 11 个弹窗各写各的，行为不一致）：宽度令牌 / 关闭语义 / 销毁语义 / 提交防连发
//   定制项留给各弹窗自己传（title 样式/footer/内容），壳不吞业务
import type { ReactNode } from 'react';
import { Modal } from 'antd';
import type { ButtonProps } from 'antd';
import { settingsModalWidth } from './settingsTokens';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';

export type SettingsModalWidth = keyof typeof settingsModalWidth;

interface SettingsModalProps {
  open: boolean;
  /** 标题：传字符串走标准样式；传 ReactNode 则原样渲染（各弹窗自定义标题时用） */
  title: ReactNode;
  onCancel: () => void;
  /** 宽度档位：display=800 大表单 / form=520 中表单 / confirm=480 确认类 */
  width?: SettingsModalWidth;
  /**
   * 关闭语义（归一化关键项）：
   *   'discard' 表单类 —— 点遮罩/ESC/取消即放弃（内部状态随 destroyOnHidden 销毁）
   *   'ignore'  只读类 —— 点遮罩无反应，只有点 × 或取消按钮能关
   */
  closeBehavior?: 'discard' | 'ignore';
  /** 关闭并销毁内部状态：默认 true（防重开看到上次脏数据） */
  destroyOnHidden?: boolean;
  /** 确定按钮回调；传了才渲染确定按钮 */
  onOk?: () => void;
  okText?: string;
  cancelText?: string;
  /** 提交进行中：确定按钮 loading 且防连发 */
  confirmLoading?: boolean;
  okButtonProps?: ButtonProps;
  /** 取消键属性（如单按钮提示窗传 {style:{display:'none'}}） */
  cancelButtonProps?: ButtonProps;
  /** 危险操作（删除/清空）—— 确定键转 danger 红 */
  danger?: boolean;
  /** 标题下方的说明行（如"创建后可在③区修改"） */
  description?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
}

/**
 * SettingsModal - 设置页弹窗标准壳
 *
 * 为什么有壳（DRY/KISS-DIRECT）：审计 11 个弹窗发现同一批毛病分散在 10 个文件
 * —— 宽度硬编码、maskClosable 语义不明、缺 destroyOnHidden、3 处无提交防连发、
 * 4 处删除确认缺 danger。壳把这四类收敛成默认值，各弹窗只声明"我是什么档位、
 * 关闭是丢弃还是忽略"，不再各写一遍（改动一处，全页生效）。
 *
 * 各弹窗的专属优化（内容排版/留白/图表等）仍在自己文件里做，壳不越界。
 */
export function SettingsModal({
  open,
  title,
  onCancel,
  width = 'form',
  closeBehavior = 'discard',
  destroyOnHidden = true,
  onOk,
  okText = '确定',
  cancelText = '取消',
  confirmLoading = false,
  okButtonProps,
  cancelButtonProps,
  danger = false,
  description,
  footer,
  children,
}: SettingsModalProps) {
  return (
    <Modal
      open={open}
      width={settingsModalWidth[width]}
      title={
        typeof title === 'string' ? (
          <span
            style={{ fontSize: FontSize.PRIMARY, fontWeight: FontWeight.BOLD }}
          >
            {title}
          </span>
        ) : (
          title
        )
      }
      // 关闭语义归一：表单类允许误触遮罩(=放弃)，只读类屏蔽误触
      maskClosable={closeBehavior === 'discard'}
      keyboard={closeBehavior === 'discard'}
      destroyOnHidden={destroyOnHidden}
      onCancel={onCancel}
      {...(onOk ? { onOk, okText, cancelText, confirmLoading } : {})}
      {...(footer !== undefined ? { footer } : {})}
      okButtonProps={{
        ...(danger ? { danger: true } : {}),
        ...okButtonProps,
      }}
      {...(cancelButtonProps ? { cancelButtonProps } : {})}
    >
      {description && (
        <div
          style={{
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.SECONDARY,
            marginBottom: Spacing.LG,
          }}
        >
          {description}
        </div>
      )}
      {children}
    </Modal>
  );
}

export default SettingsModal;

/**
 * confirmDanger - 危险操作统一确认（删除/清空/查看密钥）
 *
 * 审计发现 4 处删除类确认没走 danger，误点与"取消"视觉等价，危险度错配。
 * 统一收口：okButtonProps.danger + okText 说清动作，杜绝各处自拼。
 */
export function confirmDanger(opts: {
  title: string;
  content: ReactNode;
  okText?: string;
  onOk: () => void | Promise<void>;
}) {
  Modal.confirm({
    ...opts,
    okText: opts.okText ?? '删除',
    cancelText: '取消',
    okButtonProps: { danger: true },
  });
}
