// 编辑历史: 2026-08-26 小欧 - 8.7 实施: 信任操作面板, 查询/撤销信任, HITL confirm写入(4.3.5/4.7)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 新增omni-trust-changed事件监听, HITL信任写入后自动刷新面板
// 编辑历史: 2026-08-28 小欧 - ①B/b1: 空态不占位(tools0→null), ghost对齐padding4 0, 文案色#595959统一
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
import { Button, Collapse, List, Typography } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { trustApi } from '../../../../services/api/task.api';
import { Colors } from '@/utils/stepStyles';

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

  if (tools.length === 0) return null;
  return (
    <Collapse
      ghost
      defaultActiveKey={[]}
      style={{ padding: '4px 0' }}
      items={[
        {
          key: 'trust',
          label: (
            <Typography.Text
              type="secondary"
              style={{ fontSize: 12, color: Colors.TEXT.PRIMARY }}
            >
              本会话信任的操作（{tools.length}）
            </Typography.Text>
          ),
          children: (
            <List
              size="small"
              style={{ paddingLeft: 8 }}
              dataSource={tools}
              locale={{
                emptyText: '暂无信任项（HITL 弹窗勾选"本次会话信任"后出现）',
              }}
              renderItem={(tool) => (
                <List.Item
                  actions={[
                    <Button
                      key="revoke"
                      size="small"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => void revoke(tool)}
                    >
                      撤销
                    </Button>,
                  ]}
                >
                  <Typography.Text style={{ fontSize: 12 }}>
                    {tool}
                  </Typography.Text>
                </List.Item>
              )}
            />
          ),
        },
      ]}
    />
  );
};

export { TrustPanel };
