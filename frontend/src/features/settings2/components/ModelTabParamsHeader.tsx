// 编辑历史: 2026-11-09 小欧 - 新建：② 参数区标题行与三按钮（添加参数/管理推理深度/放弃修改）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import { Button, Modal, Tooltip } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { settingsControl, settingsModalWidth } from '@/theme/settingsTokens';
import { SectionTitle } from './SectionTitle';

interface Props {
  saving: boolean;
  envManaged: boolean;
  hasManagementOptions: boolean;
  hasProviderDraft: boolean;
  isDirty: boolean;
  onAddParam: () => void;
  onManageOptions: () => void;
  onDiscard: () => void;
}

export const ModelTabParamsHeader: React.FC<Props> = ({
  saving,
  envManaged,
  hasManagementOptions,
  hasProviderDraft,
  isDirty,
  onAddParam,
  onManageOptions,
  onDiscard,
}) => (
  <div
    style={{
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 1fr',
      alignItems: 'center',
    }}
  >
    <SectionTitle title="── ② 选中模型参数 ──" />
    {/* 三按钮组：同款默认 Button + actionBtnWidth 等长 + gap SM 紧挨，整组居中 */}
    <div style={{ display: 'flex', gap: Spacing.SM, justifySelf: 'start' }}>
      <Button
        icon={<PlusOutlined />}
        style={{ width: settingsControl.actionBtnWidth }}
        // env 接管禁添加（后端拒保存）+ 保存中禁（防保存期间改 state）
        disabled={saving || envManaged}
        onClick={onAddParam}
      >
        添加模型参数
      </Button>
      {/* 两颗灰钮不藏，常显——位置恒定不跳位；Tip 只解释「为什么灰」 */}
      <Tooltip
        title={
          !hasManagementOptions
            ? '还没有可管理的参数选项——添加模型勾选「参数选项」后这里才可用'
            : undefined
        }
      >
        <span style={{ display: 'inline-flex' }}>
          <Button
            style={{ width: settingsControl.actionBtnWidth }}
            disabled={saving || envManaged || !hasManagementOptions}
            onClick={onManageOptions}
          >
            管理推理深度
          </Button>
        </span>
      </Tooltip>
      <Tooltip
        title={
          !isDirty && !hasProviderDraft
            ? '还没改过任何参数，不用放弃'
            : undefined
        }
      >
        <span style={{ display: 'inline-flex' }}>
          <Button
            style={{ width: settingsControl.actionBtnWidth }}
            disabled={(!isDirty && !hasProviderDraft) || saving}
            onClick={() => {
              Modal.confirm({
                title: (
                  <span
                    style={{
                      fontSize: FontSize.PRIMARY,
                      fontWeight: FontWeight.BOLD,
                    }}
                  >
                    ⚠ 放弃修改
                  </span>
                ),
                content: (
                  <div style={{ color: Colors.TEXT.SECONDARY, lineHeight: 2 }}>
                    <div>将放弃该页全部未保存修改：</div>
                    <div>①参数值还原为已保存值</div>
                    <div>②×删除的参数恢复回列表</div>
                    <div>③能力勾选还原为已保存勾选</div>
                    <div>
                      ④Provider
                      配置（地址/显示名/超时/重试/速率限制）还原为已保存值
                    </div>
                    <div style={{ marginTop: Spacing.SM }}>
                      已保存的配置不受影响，此操作只撤内存草稿、不改动后端。
                    </div>
                  </div>
                ),
                okText: '确认放弃',
                okButtonProps: { danger: true },
                cancelText: '取消',
                width: settingsModalWidth.confirm,
                onOk: () => {
                  // 保存进行中确认放弃的竞态守卫（防放弃覆写保存中快照）
                  if (saving) return;
                  onDiscard();
                },
              });
            }}
          >
            放弃修改
          </Button>
        </span>
      </Tooltip>
    </div>
  </div>
);
