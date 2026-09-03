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
import { Tooltip } from 'antd';
import { trustApi, type TrustedTool } from '../../../../services/api/task.api'; // v1.5: TrustedTool 带 path — 小欧 2026-09-02
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

interface TrustPanelProps {
  sessionId?: string | null; // 2026-09-03 小欧: 改可选, 兼容TaskInfoBar透传的 `string|null|undefined` (undefined→组件内 if(!sessionId) 已处理)
}

const TrustPanel: React.FC<TrustPanelProps> = ({ sessionId }) => {
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

  // 2026-09-03 小欧: 撤销带try/catch防unhandledrejection上浮(对齐TaskInfoBar原TB-02), 撤销成功重载清单 — 小欧-2026-09-03
  const revoke = async (toolName: string, path: string | null) => {
    if (!sessionId) return;
    try {
      await trustApi.revokeTrust(sessionId, toolName, path);
      await load();
    } catch {
      /* 2026-09-02 小欧 TB-02: 捕获异常防unhandledrejection上浮 */
    }
  };

  const [expanded, setExpanded] = useState(false);
  const hasTools = tools.length > 0;
  // 2026-09-03 小欧: 计数配色——有信任 PRIMARY / 无 TERTIARY(对齐TaskInfoBar原实现) — 小欧-2026-09-03
  const countColor = hasTools ? Colors.TEXT.PRIMARY : Colors.TEXT.TERTIARY;
  return (
    <div style={{ padding: 0 }}>
      {/* 折叠规范(小欧 2026-09-01): 三角统一▲▼、大小14(PRIMARY)、颜色PRIMARY#595959、位置数量后、方法role=button/aria-expanded/tabIndex/onKeyDown - 北京老陈定案，全页统一 */}
      {/* 2026-09-03 小欧: stopPropagation——信任三角不冒泡触发TaskInfoBar整行折叠面板(对齐原内联实现), Tooltip保留 — 小欧-2026-09-03 */}
      <div
        role="button"
        aria-expanded={expanded}
        tabIndex={0}
        onClick={(e) => {
          e.stopPropagation();
          setExpanded((v) => !v);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.stopPropagation();
            setExpanded((v) => !v);
          }
        }}
        style={{
          cursor: 'pointer',
          lineHeight: `${FontSize.SECONDARY + Spacing.XS}px`,
          display: 'inline-flex',
          alignItems: 'center',
        }}
      >
        <Tooltip title="会话级 tool+path 免审白名单：勾信任后同会话同工具、目标路径及其子目录免弹框，危险操作仍拦截，可×撤销">
          <span
            style={{
              fontSize: FontSize.SECONDARY,
              color: countColor,
            }}
          >
            信任({tools.length})
          </span>
        </Tooltip>
        <span
          style={{
            fontSize: FontSize.PRIMARY,
            color: countColor,
            marginLeft: 4,
          }}
        >
          {expanded ? '▲' : '▼'}
        </span>
      </div>
      {expanded && hasTools && (
        <div
          role="list"
          style={{ maxHeight: 70, overflow: 'auto', paddingTop: Spacing.XS }}
        >
          {tools.map((t) => (
            <div
              key={`${t.toolName}:${t.path ?? ''}`}
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
                {t.toolName} › {t.path ?? '任意'}
              </span>
              <span
                onClick={(e) => {
                  e.stopPropagation();
                  void revoke(t.toolName, t.path);
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
