// DirectoryAccessNote.tsx — 安全 Tab 块2：分类表(页面直出) + 两个说明弹框
// 编辑历史: 2026-10-06 小欧 - 新建
//   文案源全在后端 app/datafile/*.md(已插值真实路径), 前端只取一次数 + MarkdownSlot 渲染, 零字符串逻辑。
//   两个弹框保持独立(决策41): 按钮1=策略说明, 按钮2=读写判定, 各挂各的 md。
//   POPUPS 单源派生: 按钮与 Modal 由同一份配置生成, 杜绝两处各写一遍再漂移。
// 编辑历史: 2026-10-06 小欧(三堂会审)修 4 项:
//   #2 加载失败原本走三选一只剩一条 Alert → 分类表和两个按钮全消失, 降级成了"功能没了"。
//      改为: 按钮恒在, 只有分类表区域按 docs 有无切换 提示/表格。
//   #3 关闭弹框时 {current && <Modal>} 直接卸载 → 丢失退出动画(body overflow 也会闪一下)。
//      改为 Modal 常驻, open 由 openKey 决定; 文案用 lastKey 兜住关闭动画那一帧。
//   #8 POPUPS 里 mdKey 与 key 同值冗余 → 删掉, 直接用 key。
//   #9 外层 div 的 color/fontSize 被 MarkdownText 内部每个元素的样式覆盖, 是死代码 → 删掉。 — 小欧-2026-10-06
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Button, Modal, Spin } from 'antd';
import { MarkdownSlot } from '@/components/markdown/MarkdownSlot';
import { settingsModalWidth } from '@/theme/settingsTokens';
import {
  settingsApi,
  type SecurityDocsResponse,
} from '@/services/api/settings.api';
import { Spacing } from '@/utils/stepStyles';

/** 两个弹框的单源定义: key 即后端返回键, 按钮与 Modal 全由它派生 */
const POPUPS = [
  { key: 'policy', title: '安全策略说明' },
  { key: 'flow', title: '读写判定流程' },
] as const;

type PopupKey = (typeof POPUPS)[number]['key'];

export function DirectoryAccessNote() {
  const [docs, setDocs] = useState<SecurityDocsResponse | null>(null);
  const [error, setError] = useState('');
  const [openKey, setOpenKey] = useState<PopupKey | null>(null);
  // 关闭动画期间 openKey 已置 null, 但 Modal 仍要显示最后一帧内容, 故留住上一次的 key
  const lastKey = useRef<PopupKey>('policy');
  if (openKey) lastKey.current = openKey;

  const load = useCallback(async () => {
    try {
      setDocs(await settingsApi.getSecurityDocs());
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const close = useCallback(() => setOpenKey(null), []);
  // 关闭动画那一帧 openKey 已是 null, 用 lastKey 兜住; POPUPS 是非空字面量数组, 末位兜底
  const current =
    POPUPS.find((p) => p.key === openKey) ??
    POPUPS.find((p) => p.key === lastKey.current) ??
    POPUPS[POPUPS.length - 1];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: Spacing.MD }}>
      {/* 分类表区域: 加载中转圈 / 失败给提示 / 成功直出表格 */}
      {error ? (
        <Alert
          type="error"
          showIcon
          message="安全策略说明加载失败，请检查服务是否正常"
        />
      ) : !docs ? (
        <Spin />
      ) : (
        <MarkdownSlot text={docs.classification} markdown fixedTable />
      )}

      {/* 两个说明弹框入口: 恒在(文案加载失败也要让用户知道有这两个说明) */}
      <div style={{ display: 'flex', gap: Spacing.SM }}>
        {POPUPS.map((p) => (
          <Button
            key={p.key}
            onClick={() => setOpenKey(p.key)}
            disabled={!docs}
          >
            {p.title}
          </Button>
        ))}
      </div>

      <Modal
        open={openKey !== null}
        title={current.title}
        width={settingsModalWidth.display}
        onCancel={close}
        footer={null}
        destroyOnHidden
        styles={{ body: { maxHeight: '78vh', overflow: 'auto' } }}
      >
        {docs && <MarkdownSlot text={docs[current.key]} markdown />}
      </Modal>
    </div>
  );
}

export default DirectoryAccessNote;
