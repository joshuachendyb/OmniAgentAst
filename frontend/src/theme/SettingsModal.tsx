// 编辑历史: 2026-10-10 小欧 - 文档[16] 设置页弹窗统一化审计后新建：设置页弹窗标准壳（SettingsModal）
//   归一化四件事（原先 11 个弹窗各写各的，行为不一致）：宽度令牌 / 关闭语义 / 销毁语义 / 提交防连发
//   定制项留给各弹窗自己传（title 样式/footer/内容），壳不吞业务
// 2026-10-10 22:15 小欧 - 视觉优化二轮（8 弹窗实拍取证后）：壳再补三能力，消 18 条问题里的 8 条
//   ① ModalSection —— 语义分区块（弱容器+小标题+可选右槽）。解决「各弹窗语义块裸奔」：
//      添加Provider 的 身份/连接/性能/批量模型四块、添加模型的参数模板区，全部靠它分区。
//   ② CodeChip —— 机器键名（provider::model / sandbox.enabled）专用等宽 chip。
//      解决「结构化键名与中文标题同权重、辨识不出是标识符」。
//   ③ bodyMaxHeight —— 壳级高度上限 + 滚动。解决「添加模型 641px / AboutFiles 602px 在
//      720p 屏把 footer 顶到边甚至裁切」。壳管上限，各弹窗不再各写 maxHeight。
import type { CSSProperties, ReactNode } from 'react';
import { Modal } from 'antd';
import type { ButtonProps } from 'antd';
import { settingsModalWidth } from './settingsTokens';
import { Colors, FontSize, FontWeight, Radius, Spacing } from '@/utils/stepStyles';

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
  /**
   * 正文最大高度：超出则正文滚动、footer 永不被挤（壳级默认 62vh）。
   * 传null 关闭上限（内容极短的确认类弹窗可不设）。
   */
  bodyMaxHeight?: string | null;
  children?: ReactNode;
}

/** 等宽字体栈：与 AboutFiles 代码区同源（DRY：全设置页机器字只有这一份） */
const MONO_FONT = 'Consolas, Menlo, monospace';

/**
 * CodeChip - 机器键名专用渲染（provider::model / sandbox.enabled 这类结构化标识符）
 *
 * 为什么不用普通文本：这类键名既不是标题也不是正文，混排时用户读不出"这是标识符"。
 * 等宽 + 浅底 + 与正文拉开一档字重，一眼可辨，且长键名不与中文标题抢行。
 */
export function CodeChip({
  children,
  tone = 'default',
  style,
}: {
  children: ReactNode;
  /** danger=破坏性操作涉及的键；default=普通标识符 */
  tone?: 'default' | 'danger';
  style?: CSSProperties;
}) {
  return (
    <code
      style={{
        fontFamily: MONO_FONT,
        fontSize: FontSize.CODE,
        lineHeight: '20px',
        padding: '1px 6px',
        borderRadius: Radius.SM,
        border: `1px solid ${Colors.BORDER.LIGHT}`,
        background: tone === 'danger' ? '#fff1f0' : Colors.BG.TERTIARY,
        color: tone === 'danger' ? '#cf1322' : Colors.TEXT.STRONG,
        wordBreak: 'break-all',
        ...style,
      }}
    >
      {children}
    </code>
  );
}

/**
 * ModalSection - 弹窗内语义分区块
 *
 * 设计依据（8 弹窗实拍取证）：弹窗表单一旦超过 3 个字段，字段就开始"平铺"，
 * 用户读不出哪些字段是一件事。加浅底+ 边框的弱容器与小标题后，块层级立刻成立。
 * 刻意不做成卡片（无阴影、圆角小），避免和弹窗卡片本身抢层级。
 */
export function ModalSection({
  title,
  hint,
  extra,
  children,
  style,
}: {
  /** 块标题；不传则只渲染内容（纯分隔用） */
  title?: ReactNode;
  /** 标题右侧的补充说明（如"勾选即带入新模型"） */
  hint?: ReactNode;
  /** 标题行右端的操作位（如"全选"） */
  extra?: ReactNode;
  children?: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <section
      style={{
        background: Colors.BG.LIGHT,
        border: `1px solid ${Colors.BORDER.LIGHT}`,
        borderRadius: Radius.DEFAULT,
        // 2026-10-10 22:35 小欧 - 竖向内距 12→10：四块分区时上下内距×4 是纯开销，
        //   实测把「批量模型」块顶出可视区。横向留 12 保可点区舒适度。
        padding: '10px 12px',
        ...style,
      }}
    >
      {(title || hint || extra) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: Spacing.MD,
            marginBottom: Spacing.MD,
          }}
        >
          {title && (
            <span
              style={{
                fontSize: FontSize.PRIMARY,
                fontWeight: FontWeight.BOLD,
                color: Colors.TEXT.PRIMARY,
                flexShrink: 0,
              }}
            >
              {title}
            </span>
          )}
          {hint && (
            <span
              style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}
            >
              {hint}
            </span>
          )}
          {extra && <span style={{ marginLeft: 'auto' }}>{extra}</span>}
        </div>
      )}
      {children}
    </section>
  );
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
  bodyMaxHeight = '62vh',
  children,
}: SettingsModalProps) {
  // 2026-10-10 22:15 小欧 - 壳级高度上限：内容再长也只滚正文，footer 常驻可见
  // 22:35 追加：Windows/Linux 默认 overlay 滚动条静止时不可见，正文被截断时用户
  //   完全看不出"下面还有"（实测「批量模型」整块被切在可视区外，像坏掉了）。
  //   显式给 scrollbar 宽度+滑块色，滚动条常驻可见，作为溢出信号。
  const bodyOverflowStyle: CSSProperties | undefined =
    bodyMaxHeight === null
      ? undefined
      : {
          maxHeight: bodyMaxHeight,
          overflowY: 'auto',
          scrollbarWidth: 'thin',
          scrollbarColor: '#d9d9d9 transparent',
        };

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
      styles={{ body: bodyOverflowStyle }}
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
