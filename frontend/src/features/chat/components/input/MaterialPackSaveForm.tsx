// 编辑历史: 2026-11-06 小欧 - 三堂会审(SRP): 自 MaterialPackPanel 抽出 —— 存包表单独立成组件,
//   父组件只留列表/搜索/分组/投喂/改名/删除 — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧 - F-08 修复: 存包条目带 kind/attachment_id(附件身份不降格),
//   投喂时按 id 恢复附件语义(原只存 path/label, resolver 走文件读分支) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - P0 正名: 存当前→新建合集 / 素材包→合集 / 引用区→本轮文件 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - P1 合门: 表单由内联 Space 改 Modal(抽屉左栏仅 172px, 内联表单挤不下);
//   名字自动填 + 回车即存, 本轮为空时按钮置灰 — 小欧-2026-11-07
/**
 * MaterialPackSaveForm - 「新建合集」表单
 *
 * 独立组件(SRP): 负责合集表单态(formName/formGroup/formOpen)与提交(saveCurrent)。
 * 只存清单、不复制文件; 409 由全局错误处理器提示, 本组件不解析中文文案。
 */
import React, { useState } from 'react';
import { Button, Input, Modal, Space, Tooltip, Typography } from 'antd';
import { FolderAddOutlined } from '@ant-design/icons';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { materialPackApi } from '@/services/api/materialPack.api';
import type { ComposerRef } from '@/features/refs/store';
import { FontSize, Spacing } from '@/utils/stepStyles';

const MAX_ITEMS = 10;

interface MaterialPackSaveFormProps {
  /** 本轮文件条目（「新建合集」的数据源） */
  refs: ComposerRef[];
  /** 保存成功后刷新父组件清单 */
  onSaved: () => Promise<void>;
}

const MaterialPackSaveForm: React.FC<MaterialPackSaveFormProps> = ({
  refs,
  onSaved,
}) => {
  const [formOpen, setFormOpen] = useState(false);
  const [formName, setFormName] = useState('');
  const [formGroup, setFormGroup] = useState('');

  const openForm = (): void => {
    setFormName(`合集-${new Date().toISOString().slice(0, 10)}`);
    setFormOpen(true);
  };

  const saveCurrent = async (): Promise<void> => {
    const name = formName.trim();
    if (!name) {
      showMessage(ErrorType.WARNING, '请填写合集名称');
      return;
    }
    if (refs.length === 0) {
      showMessage(ErrorType.WARNING, '本轮文件为空，先添加文件再新建合集');
      return;
    }
    if (refs.length > MAX_ITEMS) {
      showMessage(ErrorType.WARNING, `单个合集最多 ${MAX_ITEMS} 个文件`);
      return;
    }
    try {
      await materialPackApi.create({
        name,
        group_name: formGroup.trim(),
        // F-08: 条目保留引用身份 —— 附件带 kind/attachment_id, 投喂时按 id 恢复附件语义
        items: refs.map((r) => ({
          path: r.path,
          label: r.label,
          kind: r.kind,
          attachment_id: r.attachment_id,
        })),
      });
      showSuccess(`已新建合集「${name}」`);
      setFormOpen(false);
      setFormName('');
      await onSaved();
    } catch {
      /* 重名 409 的后端文案由全局处理器给出 */
    }
  };

  const empty = refs.length === 0;
  return (
    <>
      <Tooltip title={empty ? '先把文件加入本轮' : ''}>
        <span style={{ display: 'block' }}>
          <Button
            block
            icon={<FolderAddOutlined />}
            disabled={empty}
            onClick={openForm}
          >
            新建合集
          </Button>
        </span>
      </Tooltip>
      <Modal
        open={formOpen}
        title="新建合集"
        okText="保存"
        cancelText="取消"
        onOk={() => void saveCurrent()}
        onCancel={() => setFormOpen(false)}
      >
        <Space direction="vertical" size={Spacing.XS} style={{ width: '100%' }}>
          <Input
            autoFocus
            placeholder="合集名称（必填）"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            onPressEnter={() => void saveCurrent()}
          />
          <Input
            placeholder="分组（可留空）"
            value={formGroup}
            onChange={(e) => setFormGroup(e.target.value)}
            onPressEnter={() => void saveCurrent()}
          />
          <Typography.Text
            type="secondary"
            style={{ fontSize: FontSize.CAPTION }}
          >
            将把本轮文件的 {refs.length} 个文件存成一组（只存清单，不复制文件）
          </Typography.Text>
        </Space>
      </Modal>
    </>
  );
};

export { MaterialPackSaveForm };
