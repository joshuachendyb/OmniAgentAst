// 编辑历史: 2026-08-26 小欧 - 8.7 实施: 信任操作面板, 查询/撤销信任, HITL confirm写入(4.3.5/4.7)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 新增omni-trust-changed事件监听, HITL信任写入后自动刷新面板
// 编辑历史: 2026-09-02 小欧 - 会话信任功能修复 v1.5: tool+path 精确信任(行键 toolName:path, 撤销带 path)
// 编辑历史: 2026-09-03 小欧 - TaskInfoBar 复用(北京老陈定案方向1, 零退化): 内联实现合并回本组件(DRY)
// 编辑历史: 2026-09-09 小欧 - 展开列表改 Drawer 侧滑面板 + 撤销移入行首列 Modal.confirm 二次确认
// 编辑历史: 2026-11-18 商量 - UI 重做: Drawer+Table → FloatingEntry 浮层卡片(与「上下文/事件」同一套浮层语言);
//   病根是 Table 那套表格语言在密集浮层里过重(表头/列宽/留白与本页其余卡片完全两套) — 商量-2026-11-18
// 编辑历史: 2026-11-18 商量 - 卡片排版重做(人写版面的读法):
//   ① 按工具归并 —— 同一工具常有多个信任范围, 平铺会把工具名重复 N 遍, 把"这工具信任了哪几处"拆散;
//      组内每个范围行尾各自 ✕(撤销粒度不变, 仍是 (工具,范围) 对);
//   ② 范围行用 12px 等宽 + 三级灰 + 缩进一级, 长路径先段级裁剪(shortenPath)再省略号兜底, 全文挂 title;
//   ③ 撤销改「悬停该行才现身」, 常驻一排 ✕ 会让只读清单第一眼就是删除按钮墙(触屏无 hover, 一律常显);
//   ④ 计数胶囊仅在有内容时给(0 项是噪声), 脚注压成一句人话(原句把实现细节当说明);
//   ⑤ 内容区限高滚动(Size.PANEL_LIST_MAX_H + .panel-scroll 细滚动条), 长清单不把浮层顶出视口 — 商量-2026-11-18
/**
 * TrustPanel - 会话信任清单入口(集成于 TaskInfoBar 右组)
 *
 * 【小欧 2026-08-26 8.7】4.3.5/4.7：本会话信任的操作清单，按 tool_name(+path) 列出、
 * 可随时撤销；写入主通道 = HITL 弹窗 confirm(trust_session=True)，
 * 面板只做查询与撤销。REST 低频读写。
 * 【商量 2026-11-18】浮层形态改与 taskinfo 其余入口一致（向上弹、Esc 回焦、点外关闭），
 * 卡片壳/列表行/空态统一取 components/PanelCard。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Modal, Tooltip } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import {
  PanelCard,
  PanelChip,
  PanelEmpty,
  PanelRow,
} from '@/components/PanelCard';
import { trustApi, type TrustedTool } from '../../../../services/api/task.api'; // v1.5: TrustedTool 带 path — 小欧 2026-09-02
import {
  Colors,
  FontFamily,
  FontSize,
  FontWeight,
  Size,
  Spacing,
} from '@/utils/stepStyles';
import { Gap, LineHeight } from '@/theme/spacing';
import { shortenPath } from '@/utils/projectPath';
import { FloatingEntry } from '../taskinfo/FloatingEntry';

const CARD_W = 32 * FontSize.SECONDARY; // 32 汉字宽 ≈ 384px

/** 路径展示上限(字符): 384px 卡片内 12px 等宽约容 46 字, 取 44 —— 超长的提前做段级裁剪, 短的原样 */
const PATH_MAX = 44;

interface TrustGroup {
  toolName: string;
  rows: TrustedTool[];
}

/**
 * 按工具名归并信任项(顺序沿用接口给的先后, 新的在前)。
 * Map 天然保插入序, 不必再排一次 —— 撤销只针对单个 (工具, 范围), 归并只改"怎么读", 不改操作粒度。
 */
const groupByTool = (tools: TrustedTool[]): TrustGroup[] => {
  const groups = new Map<string, TrustedTool[]>();
  for (const t of tools) {
    const rows = groups.get(t.toolName);
    if (rows) rows.push(t);
    else groups.set(t.toolName, [t]);
  }
  return Array.from(groups, ([toolName, rows]) => ({ toolName, rows }));
};

interface TrustPanelProps {
  sessionId?: string | null;
  compact?: boolean; // 窄档仅计数(只显 (N)), 与相邻入口窄档口径一致
}

const TrustPanel: React.FC<TrustPanelProps> = ({ sessionId, compact }) => {
  const [tools, setTools] = useState<TrustedTool[]>([]);
  const [open, setOpen] = useState(false);
  const trustReqIdRef = useRef(0); // 2026-08-27 小欧 修复#50: 防切会话竞态, 仅采纳最新请求响应

  const load = useCallback(async () => {
    if (!sessionId) return;
    const reqId = ++trustReqIdRef.current;
    try {
      const fetchedTools = await trustApi.getTrust(sessionId);
      if (reqId === trustReqIdRef.current) setTools(fetchedTools);
    } catch (e) {
      // 2026-08-27 小欧 修复#49: load 补 try/catch, 避免 getTrust 失败导致 unhandled rejection
      console.error('[TrustPanel] 加载信任清单失败', e);
      if (reqId === trustReqIdRef.current) setTools([]);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  // 2026-08-27 小欧 三堂会审: 监听 HITL confirm(trust_session=True) 成功后派发的事件, 仅命中本会话时刷新
  useEffect(() => {
    const handler = (e: Event) => {
      const ce = e as CustomEvent<{ sessionId: string }>;
      if (ce.detail?.sessionId === sessionId) void load();
    };
    window.addEventListener('omni-trust-changed', handler as EventListener);
    return () =>
      window.removeEventListener(
        'omni-trust-changed',
        handler as EventListener
      );
  }, [sessionId, load]);

  // 撤销前 Modal.confirm 二次确认（文案含工具与路径），确认才删
  const confirmRevoke = (t: TrustedTool) => {
    if (!sessionId) return;
    Modal.confirm({
      title: '确认撤销信任？',
      content: `撤销后将重新弹框确认「${t.toolName} › ${t.path ?? '全局'}」。`,
      okText: '确认撤销',
      cancelText: '取消',
      onOk: async () => {
        try {
          await trustApi.revokeTrust(sessionId, t.toolName, t.path);
          await load();
        } catch {
          /* 撤销失败保持清单不变 */
        }
      },
    });
  };

  return (
    <FloatingEntry
      open={open}
      onOpenChange={setOpen}
      // 入口在 taskinfo(视口底部), 与「事件/计划」同样向上弹 — 商量-2026-11-18
      placement="topRight"
      cardId="taskinfo-trust-card"
      ariaLabel="会话信任清单"
      cardStyle={{ width: CARD_W, maxWidth: '90vw' }}
      content={
        <PanelCard
          title="会话信任"
          meta={
            // 0 项时不摆胶囊: 空清单已经由空态说明, 头上再挂一个「0 项」是重复且像占位符
            tools.length ? <PanelChip>{tools.length} 项</PanelChip> : undefined
          }
          actions={
            <Button
              type="text"
              size="small"
              aria-label="关闭信任清单"
              data-testid="trust-close"
              icon={<CloseOutlined />}
              onClick={() => setOpen(false)}
            />
          }
          // 组间距离由内容区 gap 统一负责(铁律: 兄弟间距只用 gap, 不用 margin)
          gap={Gap.SECTION}
          bodyStyle={{
            maxHeight: Size.PANEL_LIST_MAX_H,
            overflowY: 'auto',
          }}
          footer="信任仅免确认弹窗，危险操作仍会被拦截"
        >
          {tools.length === 0 ? (
            <PanelEmpty
              text="本会话还没有信任的操作"
              hint="在授权弹窗里勾选「本次会话信任」后收录于此"
            />
          ) : (
            // 按工具归并: 同一工具常有多个信任范围(本机 6 条信任里 bash 占 4 条),
            // 平铺会把工具名重复 4 遍、把"这个工具信任了哪几处"这件读者真正关心的事拆散。
            // 归并后每组 = 工具名一行 + 各范围一行, 撤销仍精确到单个范围(行尾 ✕)。
            // 组间用通栏细线分段(不只靠留白): 范围行本身不带工具名, 只靠 12px 缩进分不清
            // "这行属于上面那个工具"还是"自己一项"。
            groupByTool(tools).map((g, gi) => (
              <div
                key={g.toolName}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: Gap.ROW,
                  // 与上一组的距离 = 内容区 gap(上面) + 这里的 paddingTop(下面), 线居中
                  ...(gi > 0
                    ? {
                        paddingTop: Spacing.MD,
                        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
                      }
                    : {}),
                }}
              >
                <span
                  style={{
                    fontSize: FontSize.PRIMARY,
                    fontWeight: FontWeight.MEDIUM,
                    color: Colors.TEXT.STRONG,
                    lineHeight: LineHeight.DENSE,
                  }}
                >
                  {g.toolName}
                </span>
                {g.rows.map((t) => (
                  <PanelRow
                    key={`${t.toolName}|${t.path}`}
                    testId={`trust-row-${t.toolName}`}
                    hoverable
                    style={{
                      alignItems: 'center',
                      paddingTop: Spacing.XS,
                      paddingBottom: Spacing.XS,
                      // 缩进一级表示"从属于上面那个工具"; 撤销 ✕ 落在行尾, 与标题栏 ✕ 同一条右轴线
                      paddingLeft: Spacing.LG,
                    }}
                  >
                    <span
                      // 长路径先做段级裁剪, 仍过长时由尾部省略号兜底; 全文挂 title 供核对
                      title={t.path ?? undefined}
                      style={{
                        flex: 1,
                        minWidth: 0,
                        fontSize: FontSize.SECONDARY,
                        fontFamily: t.path ? FontFamily.MONO : undefined,
                        color: Colors.TEXT.TERTIARY,
                        lineHeight: LineHeight.DENSE,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {t.path ? shortenPath(t.path, PATH_MAX) : '全部路径'}
                    </span>
                    <Tooltip title="撤销信任">
                      <Button
                        // 悬停该行才现身的二次操作(样式在 index.css 的 .panel-del): 常驻 ✕ 会让
                        // 只读清单第一眼是删除按钮墙; 键盘仍可达, 聚焦时由 :focus-within 显形
                        className="panel-del"
                        type="text"
                        size="small"
                        aria-label={`撤销信任 ${t.toolName}${t.path ? ` ${t.path}` : ''}`}
                        icon={<CloseOutlined />}
                        onClick={(e) => {
                          e.stopPropagation(); // 6.5.4.2: 行内撤销防冒泡
                          confirmRevoke(t);
                        }}
                      />
                    </Tooltip>
                  </PanelRow>
                ))}
              </div>
            ))
          )}
        </PanelCard>
      }
    >
      <span data-testid="trust-entry" style={{ fontSize: FontSize.SECONDARY }}>
        {/* 不叠 Tooltip: 本入口 hover 即开浮层(与「计划/事件」同), 再挂悬浮提示会两个框同时冒出;
            信任口径说明已落到卡片脚注, 一次悬停只给一个面 */}
        <span
          style={{
            color: Colors.TEXT.PRIMARY,
            fontWeight: FontWeight.MEDIUM,
          }}
        >
          {compact ? `(${tools.length})` : `信任(${tools.length})`}
        </span>
      </span>
    </FloatingEntry>
  );
};

export { TrustPanel };
