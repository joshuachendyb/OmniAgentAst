/**
 * HistoryPage组件 - 历史会话页面
 * 
 * 功能：展示会话列表、搜索、恢复对话、删除会话
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-18
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  List,
  Input,
  Button,
  Space,
  Tag,
  Typography,
  Popconfirm,
  Empty,
  message,
  Spin,
  Badge,
  Tooltip,
} from 'antd';
import {
  HistoryOutlined,
  SearchOutlined,
  DeleteOutlined,
  MessageOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  CommentOutlined,
} from '@ant-design/icons';
import { sessionApi, Session } from '../../services/api';
import { useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';

// 配置dayjs
 dayjs.extend(relativeTime);
dayjs.locale('zh-cn');

const { Title, Text } = Typography;
const { Search } = Input;

/**
 * 历史会话页面组件
 * 
 * 功能特性：
 * - 会话列表展示（带分页）
 * - 关键词搜索
 * - 恢复对话（跳转到聊天页）
 * - 删除会话（软删除）
 * - 相对时间显示
 */
const HistoryPage: React.FC = () => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const navigate = useNavigate();

  /**
   * 加载会话列表
   */
  const loadSessions = async (page: number = 1, searchKeyword?: string) => {
    setLoading(true);
    try {
      const response = await sessionApi.listSessions(
        page,
        pagination.pageSize,
        searchKeyword
      );
      setSessions(response.sessions);
      setPagination({
        ...pagination,
        current: page,
        total: response.total,
      });
    } catch (error) {
      message.error('加载会话列表失败');
      console.error('加载会话列表失败:', error);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 首次加载
   */
  useEffect(() => {
    loadSessions();
  }, []);

  /**
   * 搜索会话
   */
  const handleSearch = (value: string) => {
    setKeyword(value);
    loadSessions(1, value);
  };

  /**
   * 刷新列表
   */
  const handleRefresh = () => {
    loadSessions(pagination.current, keyword);
    message.success('列表已刷新');
  };

  /**
   * 删除会话
   */
  const handleDelete = async (sessionId: string) => {
    try {
      await sessionApi.deleteSession(sessionId);
      message.success('会话已删除');
      // 刷新列表
      loadSessions(pagination.current, keyword);
    } catch (error) {
      message.error('删除会话失败');
      console.error('删除会话失败:', error);
    }
  };

  /**
   * 恢复对话
   */
  const handleResume = (sessionId: string) => {
    // 跳转到聊天页面，带上session_id参数（使用React Router，不刷新页面）
    navigate(`/?session_id=${sessionId}`);
  };

  /**
   * 格式化时间显示
   */
  const formatTime = (time: string) => {
    return dayjs(time).fromNow();
  };

  return (
    <div style={{ padding: 0, margin: 0 }}>
      <Card bordered={false}>
        <Space direction="vertical" style={{ width: '100%' }} size="large">
          {/* 标题栏 */}
          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
            <Title level={3} style={{ margin: 0 }}>
              <HistoryOutlined /> 历史会话
            </Title>
            <Space>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={loading}
              >
                刷新
              </Button>
              <Badge count={pagination.total} showZero>
                <Button icon={<CommentOutlined />}>
                  总会话
                </Button>
              </Badge>
            </Space>
          </Space>

          {/* 搜索栏 */}
          <Search
            placeholder="搜索会话标题..."
            allowClear
            enterButton={<><SearchOutlined /> 搜索</>}
            size="large"
            onSearch={handleSearch}
            loading={loading}
          />

          {/* 会话列表 */}
          <Spin spinning={loading}>
            <List
              grid={{
                gutter: 16,
                xs: 1,
                sm: 1,
                md: 2,
                lg: 2,
                xl: 3,
                xxl: 3,
              }}
              dataSource={sessions}
              locale={{
                emptyText: (
                  <Empty
                    image={Empty.PRESENTED_IMAGE_SIMPLE}
                    description={
                      <Space direction="vertical">
                        <Text type="secondary">暂无历史会话</Text>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          开始与AI助手对话，会话将自动保存
                        </Text>
                      </Space>
                    }
                  />
                ),
              }}
              renderItem={(session) => (
                <List.Item>
                  <Card
                    hoverable
                    size="small"
                    style={{ height: '100%' }}
                    actions={[
                      <Tooltip title="继续对话">
                        <Button
                          type="link"
                          icon={<MessageOutlined />}
                          onClick={() => handleResume(session.session_id)}
                        >
                          继续
                        </Button>
                      </Tooltip>,
                      <Popconfirm
                        title="删除会话"
                        description={`确定要删除"${session.title}"吗？此操作不可恢复。`}
                        onConfirm={() => handleDelete(session.session_id)}
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <Tooltip title="删除会话">
                          <Button type="link" danger icon={<DeleteOutlined />}>
                            删除
                          </Button>
                        </Tooltip>
                      </Popconfirm>,
                    ]}
                  >
                    <Card.Meta
                      title={
                        <Tooltip title={session.title}>
                          <Text strong ellipsis style={{ maxWidth: 200 }}>
                            {session.title}
                          </Text>
                        </Tooltip>
                      }
                      description={
                        <Space direction="vertical" size="small" style={{ width: '100%' }}>
                          <Space>
                            <Tag icon={<CommentOutlined />} color="blue">
                              {session.message_count} 条消息
                            </Tag>
                          </Space>
                          <Space>
                            <ClockCircleOutlined style={{ color: '#999' }} />
                            <Text type="secondary" style={{ fontSize: 12 }}>
                              更新于 {formatTime(session.updated_at)}
                            </Text>
                          </Space>
                          <Text type="secondary" style={{ fontSize: 11 }}>
                            创建于 {dayjs(session.created_at).format('YYYY-MM-DD HH:mm')}
                          </Text>
                        </Space>
                      }
                    />
                  </Card>
                </List.Item>
              )}
            />
          </Spin>

          {/* 分页 */}
          {pagination.total > pagination.pageSize && (
            <div style={{ textAlign: 'center', marginTop: 24 }}>
              <Space>
                <Button
                  disabled={pagination.current === 1}
                  onClick={() => loadSessions(pagination.current - 1, keyword)}
                >
                  上一页
                </Button>
                <Text>
                  第 {pagination.current} 页，共 {Math.ceil(pagination.total / pagination.pageSize)} 页
                </Text>
                <Button
                  disabled={pagination.current >= Math.ceil(pagination.total / pagination.pageSize)}
                  onClick={() => loadSessions(pagination.current + 1, keyword)}
                >
                  下一页
                </Button>
              </Space>
            </div>
          )}
        </Space>
      </Card>
    </div>
  );
};

export default HistoryPage;
