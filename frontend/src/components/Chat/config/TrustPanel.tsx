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

import React, { useCallback, useEffect, useState } from 'react';
import { Button, Collapse, List, Typography } from 'antd';
import { DeleteOutlined } from '@ant-design/icons';
import { trustApi } from '../../../services/api';

interface TrustPanelProps {
  sessionId: string | null;
}

const TrustPanel: React.FC<TrustPanelProps> = ({ sessionId }) => {
  const [tools, setTools] = useState<string[]>([]);

  const load = useCallback(async () => {
    if (!sessionId) return;
    // trustApi.getTrust 已适配为 string[]（8.C-②），直接入列
    const tools = await trustApi.getTrust(sessionId);
    setTools(tools);
  }, [sessionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const revoke = async (toolName: string) => {
    if (!sessionId) return;
    await trustApi.revokeTrust(sessionId, toolName);
    await load(); // 撤销后刷新清单
  };

  return (
    <Collapse
      ghost
      items={[
        {
          key: 'trust',
          label: (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              本会话信任的操作（{tools.length}）
            </Typography.Text>
          ),
          children: (
            <List
              size="small"
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
