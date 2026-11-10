// 编辑历史: 2026-11-06 小欧: (SRP) 自 MaterialPackPanel 抽出 —— 存包表单独立成组件,
//   父组件只留列表/搜索/分组/投喂/改名/删除 — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧: 存包条目带 kind/attachment_id(附件身份不降格),
//   投喂时按 id 恢复附件语义(原只存 path/label, resolver 走文件读分支) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 存当前→新建合集 / 素材包→合集 / 引用区→本轮文件 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 表单由内联 Space 改 Modal(抽屉左栏仅 172px, 内联表单挤不下);
//   名字自动填 + 回车即存, 本轮为空时按钮置灰 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 注释清理: 去除修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
// 编辑历史: 2026-11-10 小欧 重构: 限额改由父组件注入(消本地 MAX_ITEMS 双真源), 新增「用途」备注;
//   默认名改空并按用途强引导(取代「合集-日期」无意义批量名), 达上限时入口置灰并提示 — 小欧-2026-11-10
/**
 * MaterialPackSaveForm - 「新建合集」表单
 *
 * 独立组件(SRP): 负责合集表单态(name/note/group/open)与提交。
 * 只存清单、不复制文件; 限额由父组件从后端 get_limits 下发(单一真源)。
 * 409 由全局错误处理器提示, 本组件不解析中文文案。
 */
import React, { useState } from 'react';
import { Button, Input, Modal, Space, Tooltip, Typography } from 'antd';
import { FolderAddOutlined } from '@ant-design/icons';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import {
  materialPackApi,
  type MaterialPackLimits,
} from '@/services/api/materialPack.api';
import type { ComposerRef } from '@/features/refs/store';
import { FontSize, Spacing } from '@/utils/stepStyles';

interface MaterialPackSaveFormProps {
  /** 本轮文件条目（「新建合集」的数据源） */
  refs: ComposerRef[];
  /** 保存成功后刷新父组件清单 */
  onSaved: () => Promise<void>;
  /** 后端限额（null=尚未加载，不做前端预判，后端仍会校验） */
  limits: MaterialPackLimits | null;
  /** 合集数量已达上限 */
  atLimit: boolean;
}

const MaterialPackSaveForm: React.FC<MaterialPackSaveFormProps> = ({
  refs,
  onSaved,
  limits,
  atLimit,
}) => {
  const [formOpen, setFormOpen] = useState(false);
  const [formName, setFormName] = useState('');
  const [formNote, setFormNote] = useState('');
  const [formGroup, setFormGroup] = useState('');

  const openForm = (): void => {
    setFormName('');
    setFormNote('');
    setFormGroup('');
    setFormOpen(true);
  };

  const saveCurrent = async (): Promise<void> => {
    const name = formName.trim();
    if (!name) {
      showMessage(ErrorType.WARNING, '请填写合集名称（建议按用途命名）');
      return;
    }
    if (refs.length === 0) {
      showMessage(ErrorType.WARNING, '本轮文件为空，先添加文件再新建合集');
      return;
    }
    if (limits && refs.length > limits.max_items) {
      showMessage(
        ErrorType.WARNING,
        `单个合集最多 ${limits.max_items} 个文件，本轮有 ${refs.length} 个`
      );
      return;
    }
    try {
      await materialPackApi.create({
        name,
        note: formNote.trim(),
        group_name: formGroup.trim(),
        // 条目保留引用身份 —— 附件带 kind/attachment_id, 投喂时按 id 恢复附件语义
        items: refs.map((r) => ({
          path: r.path,
          label: r.label,
          kind: r.kind,
          attachment_id: r.attachment_id,
        })),
      });
      showSuccess(`已新建合集「${name}」`);
      setFormOpen(false);
      await onSaved();
    } catch {
      /* 重名 409 / 超限 400 的后端文案由全局处理器给出 */
    }
  };

  const empty = refs.length === 0;
  const reason = atLimit
    ? `合集已达上限${limits ? `（${limits.max_packs} 个）` : ''}，请先删除旧合集`
    : empty
      ? '先把文件加入本轮'
      : '';
  return (
    <>
      <Tooltip title={reason}>
        <span style={{ display: 'block' }}>
          <Button
            block
            icon={<FolderAddOutlined />}
            disabled={empty || atLimit}
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
            placeholder="合集名称（必填，如：周报素材）"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            onPressEnter={() => void saveCurrent()}
          />
          <Input
            placeholder="用途说明（可选，如：给周报引用的三份数据）"
            value={formNote}
            onChange={(e) => setFormNote(e.target.value)}
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
            {`将把本轮 ${refs.length} 个文件存成一组（只存清单，不复制文件）`}
            {limits ? `，单组合集最多 ${limits.max_items} 个` : ''}
          </Typography.Text>
        </Space>
      </Modal>
    </>
  );
};

export { MaterialPackSaveForm };
