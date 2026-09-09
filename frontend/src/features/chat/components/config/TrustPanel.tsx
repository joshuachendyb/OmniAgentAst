// 编辑历史: 2026-08-26 小欧 - 8.7 实施: 信任操作面板, 查询/撤销信任, HITL confirm写入(4.3.5/4.7)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 新增omni-trust-changed事件监听, HITL信任写入后自动刷新面板
// 编辑历史: 2026-08-28 小欧 - ①B/b1: 空态不占位(tools0→null), ghost对齐padding4 0, 文案色#595959统一
// 编辑历史: 2026-08-30 小欧 - 13.14 纯div重构: 去Collapse/List/Typography/Button, 收起16px/展开90px(4×16+3×2+4), 零默认留白 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复×不显眼: DeleteOutlined→文本×、色#8c8c8c→#595959、字号12→14加粗 - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - task005会审P2无障碍修复(北京老陈定案): 纯div折叠回归→折叠区补 role="button"/aria-expanded/tabIndex/onKeyDown(Enter/Space)、列表补 role="list"/"listitem"; 不引 aria-controls(列表条件渲染, id可能不存在成无效引用) - 小欧-2026-09-02
// 编辑历史: 2026-09-01 小欧 - 规范折叠符号位置统一：三角移至“(*)”后，与工具调用链同位，保持全页单一折叠方法 - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 会话信任功能修复 v1.5⑤⑥(北京老陈定案"tool+path才是准确对象", 后端§5.5): 面板升级 tool+path 精确信任——
//   tools行类型带path、行键 `${toolName}:${path}`、显示 {toolName} › {path ?? '任意'}(空=工具级通配)、revoke签名带path精确撤销 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - TaskInfoBar复用(北京老陈定案方向1, 零退化铁律): TrustPanel原为config孤儿(2026-08-30迁移TaskInfoBar时被内联复制成孤儿),
//   现把TaskInfoBar内联信任实现(查询/刷新/撤销/折叠/无障碍/空态/计数配色 + Tooltip + stopPropagation + 撤销try/catch)全部合并回TrustPanel,
//   TaskInfoBar改import复用删除内联重复(DRY); 以TaskInfoBar现有样式为准(紧凑"信任(N)"+Tooltip+计数配色+stopPropagation), 功能零丢失零退化 - 小欧-2026-09-03
// 编辑历史: 2026-09-09 小欧 - [16]v4.x P1-10/P0-4/P2-18: 展开列表改 Drawer 侧滑面板(第一行高度恒定不跳动); 撤销移入每行首列 + Modal.confirm 二次确认(文案含工具名);
//   触发按钮文字样式(PRIMARY+500)提示可点; 关闭后焦点回触发按钮; load/omni-trust-changed监听/trustReqIdRef竞态守卫原样不动 — 小欧-2026-09-09
/**
 * TrustPanel - 信任操作面板（集成于 TaskInfoBar 第一行尾部，紧凑样式）
 *
 * 【小欧 2026-08-26 8.7】4.3.5/4.7：本会话信任的操作清单，按 tool_name(+path) 列出、
 * 可随时撤销；写入主通道 = HITL 弹窗 confirm(trust_session=True)（既有 F1），
 * 面板只做查询(D1)与撤销(D2)。REST 低频读写。
 * 【小欧 2026-09-03】原 config slot 定位废弃，现为 TaskInfoBar 第一行尾巴集成（13.14）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Button, Drawer, Empty, Modal, Table, Tooltip } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import { trustApi, type TrustedTool } from '../../../../services/api/task.api'; // v1.5: TrustedTool 带 path — 小欧 2026-09-02
import { Colors, FontSize, FontWeight } from '@/utils/stepStyles';

interface TrustPanelProps {
  sessionId?: string | null; // 2026-09-03 小欧: 改可选, 兼容TaskInfoBar透传的 `string|null|undefined` (undefined→组件内 if(!sessionId) 已处理)
  compact?: boolean; // 小欧 2026-09-09 3.9 修复#3: narrow/xsmall 仅计数(按钮只显 (N), Tooltip 保留)
}

const TrustPanel: React.FC<TrustPanelProps> = ({ sessionId, compact }) => {
  const [tools, setTools] = useState<TrustedTool[]>([]); // v1.5: tool+path 行 — 小欧 2026-09-02

  const trustReqIdRef = useRef(0); // 2026-08-27 小欧 修复#50: 防切会话竞态, 仅采纳最新请求响应

  const load = useCallback(async () => {
    if (!sessionId) return;
    const reqId = ++trustReqIdRef.current;
    try {
      // trustApi.getTrust 已适配为 string[]（8.C-②），直接入列
      const fetchedTools = await trustApi.getTrust(sessionId);
      if (reqId === trustReqIdRef.current) {
        setTools(fetchedTools); // 2026-08-27 小欧 修复#12: 局部变量tools遮蔽状态tools, 改名避免遮蔽
      }
    } catch (e) {
      // 2026-08-27 小欧 修复#49: load新增try/catch, 避免getTrust失败导致unhandled rejection
      console.error('[TrustPanel] 加载信任清单失败', e);
      if (reqId === trustReqIdRef.current) setTools([]);
    }
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  // 2026-08-27 小欧 三堂会审: 监听HITL confirm(trust_session=True)成功后派发的事件, 仅命中本会话时刷新信任清单
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

  // P0-4: 撤销前 Modal.confirm 二次确认（文案含工具名），确认才删
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

  const [drawerOpen, setDrawerOpen] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const drawerPanelRef = useRef<HTMLDivElement>(null); // 小欧 2026-09-09 #4: 打开后焦点移入靶点
  const openDrawer = () => setDrawerOpen(true);
  const closeDrawer = () => {
    setDrawerOpen(false);
    triggerRef.current?.focus(); // 3.5: 关闭后焦点回到触发按钮
  };
  // 小欧 2026-09-09 #4: Drawer 打开后焦点移入面板(3.5/P1-10 键盘无障碍)；
  //   open 置 true 时内容已渲染, 直接聚焦(不依赖 antd 动画 afterOpenChange, 测试可判定)
  useEffect(() => {
    if (drawerOpen) drawerPanelRef.current?.focus();
  }, [drawerOpen]);
  // 3.1.3 方案A: 文字样式(PRIMARY + 500)提示可点
  return (
    <div style={{ padding: 0 }}>
      <div
        ref={triggerRef}
        role="button"
        aria-expanded={drawerOpen}
        aria-label="会话信任清单"
        tabIndex={0}
        onClick={openDrawer}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            openDrawer();
          }
        }}
        style={{
          cursor: 'pointer',
          color: Colors.TEXT.PRIMARY,
          fontWeight: FontWeight.MEDIUM,
          fontSize: FontSize.SECONDARY,
        }}
      >
        <Tooltip title="会话级 tool+path 免审白名单：勾信任后同会话同工具、目标路径及其子目录免弹框，危险操作仍拦截，可×撤销">
          <span>
            {compact ? `(${tools.length})` : `信任(${tools.length})`}{' '}
            {/* 3.9 修复#3: narrow/xsmall 仅计数, Tooltip 全文保留 */}
          </span>
        </Tooltip>
      </div>
      {/* Drawer 侧滑面板: 第一行高度恒 28px 不跳动(P1-10) */}
      <Drawer
        placement="right"
        open={drawerOpen}
        onClose={closeDrawer}
        title="会话信任清单"
        width="min(360px, 80vw)" // v3.7 定案
      >
        <div ref={drawerPanelRef} tabIndex={-1}>
          {' '}
          {/* 小欧 2026-09-09 #4: 焦点靶点(可聚焦但不出 Tab 序) */}
          {tools.length === 0 ? (
            <Empty description="暂无信任工具" />
          ) : (
            <Table
              dataSource={tools}
              size="small"
              rowKey={(t) => `${t.toolName}|${t.path}`}
              pagination={false}
            >
              <Table.Column
                title="撤销" // 操作在前、对象在后(3.5, Tab 顺序=视觉顺序)
                width={64}
                render={(_, t: TrustedTool) => (
                  <Button
                    type="text"
                    size="small"
                    icon={<CloseOutlined />}
                    aria-label={`撤销信任 ${t.toolName}`}
                    onClick={(e) => {
                      e.stopPropagation(); // 小欧 2026-09-09 #7(6.5.4.2): 行内撤销防冒泡
                      confirmRevoke(t);
                    }}
                  />
                )}
              />
              <Table.Column
                title="对象"
                render={(_, t: TrustedTool) =>
                  `${t.toolName} › ${t.path ?? '全局'}`
                }
              />
            </Table>
          )}
        </div>
      </Drawer>
    </div>
  );
};

export { TrustPanel };
