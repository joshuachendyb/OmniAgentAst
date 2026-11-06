// 编辑历史: 2026-11-06 小欧 - 新建: ⑤ 素材包面板(搜索/分组/投喂/存包/改名/删除) — 小欧-2026-11-06
// 编辑历史: 2026-11-06 小欧 - 三堂会审(SRP): 存包表单抽成独立组件 MaterialPackSaveForm, 本组件只留
//   列表/搜索/分组/投喂/改名/删除(原 376 行, 存包表单态+提交占 4 状态+1 函数) — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧 - F-07 修复: 投喂按条目身份分流 —— 附件按 id 查表恢复附件语义
//   (attachmentApi.get + enqueue 唯一入队口), 其余走 quoteFile — 小欧-2026-11-07
/**
 * MaterialPackPanel —— 素材包（⑤）唯一 UI 入口。
 *
 * 边界：
 * - 只存清单、不复制文件：「存当前」直接取引用区条目的 path/label 上行；
 * - 投喂走 quoteFile（唯一引用入口）：存在的正常入队，失效的逐个计数后统一提示；
 * - 409/400 由后端裁决、全局错误处理器提示，本组件不解析中文文案；
 * - 分组是自由文本（`group_name`），宽高固定 432px —— 面板要能并排放下三列内容。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Empty,
  Input,
  Popconfirm,
  Popover,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import { FolderAddOutlined, ImportOutlined } from '@ant-design/icons';

import {
  materialPackApi,
  type MaterialPack,
} from '@/services/api/materialPack.api';
import { quoteFile } from '@/features/refs/quote';
import type { ComposerRef } from '@/features/refs/store';
// 2026-11-07 小欧 F-07: 附件条目投喂按 id 查表恢复附件语义, 复用 enqueue 唯一入队口
import { attachmentApi } from '@/services/api/attachment.api';
import { enqueue } from '@/features/refs/uploadAttachment';
import { showMessage, showSuccess, ErrorType } from '@/services/error/handler';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
// 2026-11-06 小欧 三堂会审(SRP): 存包表单独立成组件 — 小欧-2026-11-06
import { MaterialPackSaveForm } from './MaterialPackSaveForm';

const PANEL_W = 432;

interface MaterialPackPanelProps {
  /** 当前引用区条目（「存当前」的数据源） */
  refs: ComposerRef[];
  /** 当前会话 ID（F-07: 附件条目投喂按 id 查表需会话归属校验, B-03） */
  sessionId?: string | null;
}

const MaterialPackPanel: React.FC<MaterialPackPanelProps> = ({ refs, sessionId }) => {
  const [open, setOpen] = useState(false);
  const [packs, setPacks] = useState<MaterialPack[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState('');
  const [keyword, setKeyword] = useState('');
  const [group, setGroup] = useState('');
  const [editing, setEditing] = useState<MaterialPack | null>(null);
  const [editName, setEditName] = useState('');
  const [editGroup, setEditGroup] = useState('');

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      setPacks(await materialPackApi.list());
    } catch {
      /* 全局错误处理器已提示，不重复弹 */
    } finally {
      setLoading(false);
    }
  }, []);

  // 打开才拉：素材包是低频数据，不该在对话页初始化时占用一次请求
  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  const groups = useMemo(
    () => Array.from(new Set(packs.map((p) => p.group_name || '未分组'))),
    [packs]
  );

  const shown = useMemo(() => {
    const k = keyword.trim().toLowerCase();
    return packs.filter((p) => {
      if (group && (p.group_name || '未分组') !== group) return false;
      if (!k) return true;
      return (
        p.name.toLowerCase().includes(k) || p.note.toLowerCase().includes(k)
      );
    });
  }, [packs, group, keyword]);

  /** 投喂：按条目身份分流(F-07) —— 附件按 id 查表恢复附件语义(enqueue 唯一入队口),
   *  其余走 quoteFile(唯一引用入口); 失效的计数后一次提示 */
  const feed = async (pack: MaterialPack): Promise<void> => {
    setBusyId(pack.id);
    let failed = 0;
    try {
      for (const it of pack.items) {
        // 2026-11-07 小欧 F-07: 附件条目按 id 恢复附件语义 —— 原一律 quoteFile(path),
        //   附件降格为普通文件引用, resolver 走文件读分支(路径在根外时直接失效)
        if (it.kind === 'attachment' && it.attachment_id) {
          try {
            const rec = await attachmentApi.get(it.attachment_id, sessionId ?? '');
            if (!enqueue(rec)) failed += 1;
          } catch {
            failed += 1;
          }
          continue;
        }
        const r = await quoteFile(it.path, { label: it.label });
        if (!r.ok) failed += 1;
      }
      if (failed === 0) {
        showSuccess(`已引用「${pack.name}」的 ${pack.items.length} 个文件`);
      } else {
        showMessage(
          ErrorType.WARNING,
          `「${pack.name}」有 ${failed} 个文件已失效，其余已加入引用区`
        );
      }
    } finally {
      setBusyId('');
    }
  };

  const rename = async (pack: MaterialPack): Promise<void> => {
    const name = editName.trim();
    if (!name) {
      showMessage(ErrorType.WARNING, '名称不能为空');
      return;
    }
    try {
      await materialPackApi.update(pack.id, {
        name,
        group_name: editGroup.trim(),
      });
      showSuccess('已更新素材包');
      setEditing(null);
      await load();
    } catch {
      /* 409 同上 */
    }
  };

  const remove = async (pack: MaterialPack): Promise<void> => {
    try {
      await materialPackApi.remove(pack.id);
      showSuccess(`已删除素材包「${pack.name}」（磁盘文件不受影响）`);
      await load();
    } catch {
      /* 同上 */
    }
  };

  const body = (
    <div style={{ width: PANEL_W }}>
      <Space.Compact style={{ width: '100%' }}>
        <Input
          allowClear
          placeholder="搜索名称或说明"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <MaterialPackSaveForm refs={refs} onSaved={load} />
      </Space.Compact>

      {groups.length > 1 && (
        <Space size={4} wrap style={{ marginTop: Spacing.SM }}>
          <Tag.CheckableTag
            checked={group === ''}
            onChange={() => setGroup('')}
          >
            全部
          </Tag.CheckableTag>
          {groups.map((g) => (
            <Tag.CheckableTag
              key={g}
              checked={group === g}
              onChange={() => setGroup(g)}
            >
              {g}
            </Tag.CheckableTag>
          ))}
        </Space>
      )}

      <Spin spinning={loading}>
        <div
          style={{ maxHeight: 360, overflowY: 'auto', marginTop: Spacing.SM }}
        >
          {shown.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无素材包"
            />
          ) : (
            shown.map((p) => (
              <div
                key={p.id}
                style={{
                  padding: `${Spacing.XS}px 0`,
                  borderBottom: `1px solid ${Colors.BORDER.LIGHT}`,
                }}
              >
                {editing?.id === p.id ? (
                  <Space
                    direction="vertical"
                    size={Spacing.XS}
                    style={{ width: '100%' }}
                  >
                    <Input
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                    />
                    <Input
                      placeholder="分组（可留空）"
                      value={editGroup}
                      onChange={(e) => setEditGroup(e.target.value)}
                    />
                    <Space>
                      <Button
                        type="primary"
                        size="small"
                        onClick={() => void rename(p)}
                      >
                        保存
                      </Button>
                      <Button size="small" onClick={() => setEditing(null)}>
                        取消
                      </Button>
                    </Space>
                  </Space>
                ) : (
                  <>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: Spacing.XS,
                      }}
                    >
                      <Typography.Text strong ellipsis style={{ flex: 1 }}>
                        {p.name}
                      </Typography.Text>
                      <Typography.Text
                        type="secondary"
                        style={{ fontSize: FontSize.CAPTION }}
                      >
                        {p.group_name || '未分组'} · {p.items.length} 个
                      </Typography.Text>
                    </div>
                    {p.note && (
                      <Typography.Text
                        type="secondary"
                        style={{ fontSize: FontSize.CAPTION }}
                      >
                        {p.note}
                      </Typography.Text>
                    )}
                    <Space size={4} style={{ marginTop: 2 }}>
                      <Button
                        size="small"
                        icon={<ImportOutlined />}
                        loading={busyId === p.id}
                        disabled={p.items.length === 0}
                        onClick={() => void feed(p)}
                      >
                        投喂
                      </Button>
                      <Button
                        size="small"
                        onClick={() => {
                          setEditing(p);
                          setEditName(p.name);
                          setEditGroup(p.group_name);
                        }}
                      >
                        改名
                      </Button>
                      <Popconfirm
                        title={`删除素材包「${p.name}」？`}
                        description="只删清单，磁盘文件不受影响"
                        onConfirm={() => void remove(p)}
                      >
                        <Button size="small" danger>
                          删除
                        </Button>
                      </Popconfirm>
                    </Space>
                  </>
                )}
              </div>
            ))
          )}
        </div>
      </Spin>
    </div>
  );

  return (
    <Popover
      trigger="click"
      open={open}
      onOpenChange={setOpen}
      placement="topRight"
      title="素材包"
      content={body}
    >
      <Button size="small" icon={<FolderAddOutlined />}>
        素材包
      </Button>
    </Popover>
  );
};

export { MaterialPackPanel };
