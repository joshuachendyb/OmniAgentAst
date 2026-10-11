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
// 编辑历史: 2026-10-10 小欧 - 点按钮即后台重取: 弹框用存量秒开(手感不变), 新文案到了自动刷新;
//   取失败只走左上 Alert 原有位, 不挡弹框。 — 小欧-2026-10-10 11:00:40
// 2026-10-10 22:15 小欧 - 两个说明弹框归一到 SettingsModal 标准壳（此前是裸 antd Modal，归一批次漏掉）。
//   行为零变更：壳默认 discard 关闭语义 + destroyOnHidden，与原裸 Modal 的默认值完全一致；
//   宽度仍走 settingsModalWidth.display 令牌，footer={null}（只读说明，无操作键）保持。
// 编辑历史: 2026-10-11 10:37:22 小欧 - 北京老陈令「按人类设计师设计优化」: 说明入口由通用 Button 改文档卡片(图标 FileText/Branches + 标题 + 描述, POPUPS 同源派生, hover 边框+阴影反馈); Modal 标题同步加图标; 弹框内容包 .doc-body 作用域容器(样式见 index.css, 只依赖 markdown 结构标签, 后端文案改动不失效) — 小欧-2026-10-11
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Alert, Spin } from 'antd';
import { BranchesOutlined, FileTextOutlined } from '@ant-design/icons';
import { MarkdownSlot } from '@/components/markdown/MarkdownSlot';
import { SettingsModal } from '@/theme/SettingsModal';
import {
  settingsApi,
  type SecurityDocsResponse,
} from '@/services/api/settings.api';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';

/**
 * 两个弹框的单源定义: key 即后端返回键, 按钮与 Modal 全由它派生。
 * 2026-10-11 小欧 北京老陈令「按人类设计师设计优化」: 入口由通用 Button 改为
 *   **文档卡片**(图标 + 标题 + 描述) —— 两篇文档类型不同(规则文档 vs 判定流程),
 *   通用按钮无法区分内容类型, 用户须读标题猜; 卡片给视觉锚点 + 一句话描述,
 *   扫一眼即知点开是什么。图标/描述与标题同源派生, 后端加文档无需改本文件。
 */
const POPUPS = [
  {
    key: 'policy',
    title: '安全策略说明',
    desc: '了解目录访问的安全规则与分类标准',
    icon: <FileTextOutlined />,
  },
  {
    key: 'flow',
    title: '读写判定流程',
    desc: '查看文件读写操作的判定逻辑与流程',
    icon: <BranchesOutlined />,
  },
] as const;

type PopupKey = (typeof POPUPS)[number]['key'];

export function DirectoryAccessNote() {
  const [docs, setDocs] = useState<SecurityDocsResponse | null>(null);
  const [error, setError] = useState('');
  const [openKey, setOpenKey] = useState<PopupKey | null>(null);
  // 2026-10-11 小欧 - 文档卡片 hover 态(单值, 两卡互斥高亮)
  const [hovered, setHovered] = useState<PopupKey | null>(null);
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
  // 2026-10-10 小欧 - 点任一按钮即后台重取两份文案: 弹框用存量秒开, 新文案到了自动刷新;
  //   两个按钮同走 POPUPS.map, 改这一处即全覆盖。
  const open = useCallback(
    (k: PopupKey) => {
      setOpenKey(k);
      void load();
    },
    [load]
  );
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

      {/* 两个说明弹框入口: 文档卡片(北京老陈令「按人类设计师设计优化」)。
          恒在(文案加载失败也要让用户知道有这两个说明); 整卡可点, hover 有边框+阴影反馈。 */}
      <div style={{ display: 'flex', gap: Spacing.MD }}>
        {POPUPS.map((p) => {
          const _hover = hovered === p.key;
          return (
            <div
              key={p.key}
              role="button"
              tabIndex={0}
              onClick={() => open(p.key)}
              onMouseEnter={() => setHovered(p.key)}
              onMouseLeave={() => setHovered(null)}
              style={{
                flex: 1,
                minWidth: 0,
                display: 'flex',
                alignItems: 'center',
                gap: Spacing.MD,
                padding: '12px 14px',
                borderRadius: 6,
                border: `1px solid ${_hover ? Colors.BORDER.ACCENT : Colors.BORDER.LIGHT}`,
                backgroundColor: _hover
                  ? Colors.BG.SECONDARY
                  : Colors.BG.PRIMARY,
                cursor: docs ? 'pointer' : 'not-allowed',
                opacity: docs ? 1 : 0.55,
                transition:
                  'border-color 0.2s, background-color 0.2s, box-shadow 0.2s',
                boxShadow: _hover ? '0 2px 8px rgba(0,0,0,0.08)' : 'none',
              }}
            >
              <span
                style={{
                  fontSize: 20,
                  lineHeight: '20px',
                  color: _hover ? Colors.BORDER.ACCENT : Colors.TEXT.SECONDARY,
                  flexShrink: 0,
                }}
              >
                {p.icon}
              </span>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 2,
                  minWidth: 0,
                }}
              >
                <span
                  style={{
                    fontSize: FontSize.PRIMARY,
                    fontWeight: FontWeight.BOLD,
                    color: Colors.TEXT.PRIMARY,
                    lineHeight: '18px',
                  }}
                >
                  {p.title}
                </span>
                <span
                  style={{
                    fontSize: FontSize.SECONDARY,
                    color: Colors.TEXT.SECONDARY,
                    lineHeight: '16px',
                  }}
                >
                  {p.desc}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <SettingsModal
        open={openKey !== null}
        title={
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: Spacing.SM,
            }}
          >
            <span style={{ color: Colors.BORDER.ACCENT, fontSize: 16 }}>
              {current.icon}
            </span>
            {current.title}
          </span>
        }
        width="display"
        onCancel={close}
        footer={null}
        bodyMaxHeight="78vh"
      >
        {docs && (
          // 2026-10-11 小欧 北京老陈令「按人类设计师设计优化」: .doc-body 作用域样式
          //   (index.css) 只作用于本弹框的 markdown 渲染结果, 不影响全局 MarkdownText。
          //   样式只依赖结构标签(h2/ol/ul/code/p/strong), 后端文案改动不会失效。
          <div className="doc-body">
            <MarkdownSlot text={docs[current.key]} markdown />
          </div>
        )}
      </SettingsModal>
    </div>
  );
}

export default DirectoryAccessNote;
