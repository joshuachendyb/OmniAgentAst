// 编辑历史: 2026-08-26 小欧 - 8.7 实施: 信任操作面板, 查询/撤销信任, HITL confirm写入(4.3.5/4.7)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 新增omni-trust-changed事件监听, HITL信任写入后自动刷新面板
// 编辑历史: 2026-08-28 小欧 - ①B/b1: 空态不占位(tools0→null), ghost对齐padding4 0, 文案色#595959统一
// 编辑历史: 2026-08-30 小欧 - 13.14 纯div重构: 去Collapse/List/Typography/Button, 收起16px/展开90px(4×16+3×2+4), 零默认留白 - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修复×不显眼: DeleteOutlined→文本×、色#8c8c8c→#595959、字号12→14加粗 - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - task005会审P2无障碍修复(北京老陈定案): 纯div折叠回归→折叠区补 role="button"/aria-expanded/tabIndex/onKeyDown(Enter/Space)、列表补 role="list"/"listitem"; 不引 aria-controls(列表条件渲染, id可能不存在成无效引用) - 小欧-2026-09-02
// 编辑历史: 2026-09-01 小欧 - 规范折叠符号位置统一：三角移至“(*)”后，与工具调用链同位，保持全页单一折叠方法 - 小欧-2026-09-01
/**
 * TrustPanel - 信任操作面板（config slot，默认收起）
 *
 * 【小欧 2026-08-26 8.7】4.3.5/4.7：本会话信任的操作清单，按 tool_name 列出、
 * 可随时撤销；写入主通道 = HITL 弹窗 confirm(trust_session=True)（既有 F1），
 * 面板只做查询(D1)与撤销(D2)。REST 低频读写。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { trustApi } from '../../../../services/api/task.api';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

interface TrustPanelProps {
  sessionId: string | null;
}

const TrustPanel: React.FC<TrustPanelProps> = ({ sessionId }) => {
  const [tools, setTools] = useState<string[]>([]);

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

  const revoke = async (toolName: string) => {
    if (!sessionId) return;
    await trustApi.revokeTrust(sessionId, toolName);
    await load(); // 撤销后刷新清单
  };

  const [expanded, setExpanded] = useState(false);
  if (tools.length === 0) return null;
  return (
    <div style={{ padding: 0 }}>
      <div
        role="button"
        aria-expanded={expanded}
        tabIndex={0}
        onClick={() => setExpanded((v) => !v)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setExpanded((v) => !v);
          }
        }}
        style={{
          cursor: 'pointer',
          lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
        }}
      >
        <span
          style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.PRIMARY }}
        >
          本会话信任的操作（{tools.length}） {expanded ? '▾' : '▸'}
        </span>
      </div>
      {expanded && (
        <div
          role="list"
          style={{ maxHeight: 70, overflow: 'auto', paddingTop: Spacing.XS }}
        >
          {tools.map((tool) => (
            <div
              key={tool}
              role="listitem"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: `${Spacing.XS - 2}px 0`,
              }}
            >
              <span
                style={{
                  fontSize: FontSize.SECONDARY,
                  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
                }}
              >
                {tool}
              </span>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  void revoke(tool);
                }}
                style={{
                  fontSize: 14,
                  color: Colors.TEXT.PRIMARY,
                  cursor: 'pointer',
                  lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
                  padding: '0 4px',
                  fontWeight: 500,
                }}
                title="撤销信任"
              >
                ×
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export { TrustPanel };
