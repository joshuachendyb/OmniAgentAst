// 编辑历史: 2026-11-06 小欧 - 三堂会审(SRP): 自 MaterialPackPanel 抽出 —— 存包表单独立成组件,
//   父组件只留列表/搜索/分组/投喂/改名/删除 — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧 - F-08 修复: 存包条目带 kind/attachment_id(附件身份不降格),
//   投喂时按 id 恢复附件语义(原只存 path/label, resolver 走文件读分支) — 小欧-2026-11-07
/**
 * MaterialPackSaveForm - 「存当前」表单(存包)
 *
 * 独立组件(SRP): 负责存包表单态(formName/formGroup/formOpen)与提交(saveCurrent)。
 * 只存清单、不复制文件; 409 由全局错误处理器提示, 本组件不解析中文文案。
 */
import React, { useState } from 'react';
import { Button, Input, Space, Typography } from 'antd';
import { FolderAddOutlined } from '@ant-design/icons';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { materialPackApi } from '@/services/api/materialPack.api';
import type { ComposerRef } from '@/features/refs/store';
import { FontSize, Spacing } from '@/utils/stepStyles';

const MAX_ITEMS = 10;

interface MaterialPackSaveFormProps {
  /** 当前引用区条目（「存当前」的数据源） */
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
    setFormName(`素材包-${new Date().toISOString().slice(0, 10)}`);
    setFormOpen(true);
  };

  const saveCurrent = async (): Promise<void> => {
    const name = formName.trim();
    if (!name) {
      showMessage(ErrorType.WARNING, '请填写素材包名称');
      return;
    }
    if (refs.length === 0) {
      showMessage(ErrorType.WARNING, '引用区为空，先添加文件再存为素材包');
      return;
    }
    if (refs.length > MAX_ITEMS) {
      showMessage(ErrorType.WARNING, `单个素材包最多 ${MAX_ITEMS} 个文件`);
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
      showSuccess(`已存为素材包「${name}」`);
      setFormOpen(false);
      setFormName('');
      await onSaved();
    } catch {
      /* 重名 409 的后端文案由全局处理器给出 */
    }
  };

  return (
    <>
      <Button type="primary" icon={<FolderAddOutlined />} onClick={openForm}>
        存当前
      </Button>
      {formOpen && (
        <Space
          direction="vertical"
          size={Spacing.XS}
          style={{ width: '100%', marginTop: Spacing.SM }}
        >
          <Input
            placeholder="素材包名称（必填）"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
          />
          <Input
            placeholder="分组（可留空）"
            value={formGroup}
            onChange={(e) => setFormGroup(e.target.value)}
          />
          <Typography.Text
            type="secondary"
            style={{ fontSize: FontSize.CAPTION }}
          >
            将保存引用区的 {refs.length} 个文件（只存清单，不复制文件）
          </Typography.Text>
          <Space>
            <Button
              type="primary"
              size="small"
              onClick={() => void saveCurrent()}
            >
              保存
            </Button>
            <Button size="small" onClick={() => setFormOpen(false)}>
              取消
            </Button>
          </Space>
        </Space>
      )}
    </>
  );
};

export { MaterialPackSaveForm };
