/**
 * HistoryPage组件 - 历史会话页面
 *
 * 功能：展示会话列表、搜索、恢复对话、删除会话
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-18
 */

import React, { useState, useEffect } from "react";
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
  Pagination,
  Checkbox,
} from "antd";
import {
  HistoryOutlined,
  SearchOutlined,
  DeleteOutlined,
  MessageOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  CommentOutlined,
} from "@ant-design/icons";
import { sessionApi, Session } from "../../services/api";
import { useNavigate } from "react-router-dom";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";

// 配置dayjs
dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

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
  const [keyword, setKeyword] = useState("");
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const navigate = useNavigate();
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null);
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(
    new Set()
  ); // 前端小新代修改 UX-H03: 批量删除功能

  /**
   * 加载会话列表
   */
  const loadSessions = async (page: number = 1, searchKeyword?: string) => {
    setLoading(true);
    try {
      const response = await sessionApi.listSessions(
        page,
        pagination.pageSize,
        searchKeyword,
        undefined  // ⭐ 显示所有会话（包括有效和无效）
      );
      setSessions(response.sessions);
      setPagination({
        ...pagination,
        current: page,
        total: response.total,
      });
    } catch (error) {
      message.error("加载会话列表失败");
      console.error("加载会话列表失败:", error);
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
    message.success("列表已刷新");
  };

  /**
   * 强制刷新列表 - 清除可能的缓存
   */
  const handleForceRefresh = async () => {
    setLoading(true);
    try {
      // 添加时间戳参数强制刷新，防止缓存
      const response = await sessionApi.listSessions(
        pagination.current,
        pagination.pageSize,
        keyword,
        undefined  // ⭐ 显示所有会话（包括有效和无效）
      );
      setSessions(response.sessions);
      setPagination({
        ...pagination,
        current: pagination.current,
        total: response.total,
      });
      message.success("列表已强制刷新");
    } catch (error) {
      message.error("刷新失败");
      console.error("强制刷新失败:", error);
    } finally {
      setLoading(false);
    }
  };

  /**
   * 删除会话
   */
  const handleDelete = async (sessionId: string) => {
    try {
      await sessionApi.deleteSession(sessionId);
      message.success("会话已删除");
      // 刷新列表
      loadSessions(pagination.current, keyword);
    } catch (error) {
      message.error("删除会话失败");
      console.error("删除会话失败:", error);
    }
  };

  /**
   * 批量删除会话 - 前端小新代修改 UX-H03: 批量删除
   */
  const handleBatchDelete = async () => {
    if (selectedSessions.size === 0) {
      message.warning("请先选择要删除的会话");
      return;
    }
    try {
      for (const sessionId of selectedSessions) {
        await sessionApi.deleteSession(sessionId);
      }
      message.success(`已删除 ${selectedSessions.size} 个会话`);
      setSelectedSessions(new Set());
      // 刷新列表
      loadSessions(pagination.current, keyword);
    } catch (error) {
      message.error("批量删除会话失败");
      console.error("批量删除会话失败:", error);
    }
  };

  /**
   * 清空所有会话 - 从小新代修改：从 Settings 页面迁移过来
   */
  const handleClearAllSessions = async () => {
    try {
      // 检查是否有会话
      if (pagination.total === 0) {
        message.warning("当前没有会话可清空");
        return;
      }

      // ⭐ 修复：获取所有会话（不分页），确保删除全部
      // 清空会话时应该删除所有会话（包括有效和无效），不传isValid参数
      const allSessionsResponse = await sessionApi.listSessions(
        1,
        pagination.total,
        undefined,
        undefined  // 不限制有效/无效，删除全部会话
      );
      const allSessions = allSessionsResponse.sessions;

      if (allSessions.length === 0) {
        message.warning("没有会话需要清空");
        return;
      }

      // 批量删除所有会话（并行执行）
      const deletePromises = allSessions.map((session) =>
        sessionApi.deleteSession(session.session_id)
      );

      await Promise.all(deletePromises);
      message.success(`已清空 ${allSessions.length} 个会话`);
      setSelectedSessions(new Set());
      setKeyword("");
      // 刷新列表（直接重置状态，不需要等待 API）
      setSessions([]);
      setPagination({ ...pagination, current: 1, total: 0 });
      // 重新加载列表确保数据一致性
      await loadSessions(1, "");
    } catch (error) {
      message.error("清空会话失败");
      console.error("清空会话失败:", error);
      // 失败后刷新列表以恢复正确状态
      await loadSessions(pagination.current, keyword);
    }
  };

  /**
   * 恢复对话 - 前端小新代修改 UX-H02: 添加 loading 状态
   */
  const handleResume = async (sessionId: string) => {
    console.log("🔄 准备跳转到会话:", sessionId);
    setLoadingSessionId(sessionId);
    try {
      // 跳转到聊天页面，带上 session_id 参数（使用 React Router，不刷新页面）
      // ⭐ 修复：使用 replace 避免浏览器历史记录堆积
      navigate(`/?session_id=${sessionId}`, { replace: true });
      console.log("✅ 跳转成功:", sessionId);
    } catch (error) {
      console.error("❌ 跳转失败:", error);
      message.error("跳转失败");
    } finally {
      setLoadingSessionId(null);
    }
  };

  /**
   * 格式化时间显示
   */
  const formatTime = (time: string) => {
    return dayjs(time).fromNow();
  };

  return (
    // 前端小新代修改 VIS-H01: 历史记录页面内部留白
    // 原因: index.css 中 .ant-card-body { padding: 0 !important; } 会覆盖 Card 组件的 bodyStyle 属性
    // 解决方案: 通过外层 div 的 padding 来控制页面内部留白，padding 值为 25px（上下左右统一）
    <div
      className="history-page"
      style={{ padding: "25px", background: "#fff" }}
    >
      <Card bordered={false}>
        <Space
          direction="vertical"
          style={{ width: "100%", padding: "0 5px" }}
          size="large"
        >
          {/* 标题栏 */}
          <Space style={{ justifyContent: "space-between", width: "100%" }}>
            <Title level={3} style={{ margin: 0 }}>
              <HistoryOutlined /> 历史会话
            </Title>
            <Space>
              {/* 清空所有会话按钮 - 从小新代修改：从 Settings 页面迁移 */}
              <Popconfirm
                title="确定要清空所有会话吗？"
                description="此操作不可恢复"
                onConfirm={handleClearAllSessions}
                okText="确定"
                cancelText="取消"
                okButtonProps={{ danger: true }}
              >
                <Button danger icon={<DeleteOutlined />}>
                  清空所有会话
                </Button>
              </Popconfirm>
              {/* 前端小新代修改 UX-H03: 批量删除按钮 */}
              {selectedSessions.size > 0 && (
                <Popconfirm
                  title={`确定要删除选中的 ${selectedSessions.size} 个会话吗？`}
                  description="此操作不可恢复"
                  onConfirm={handleBatchDelete}
                  okText="确定"
                  cancelText="取消"
                  okButtonProps={{ danger: true }}
                >
                  <Button danger icon={<DeleteOutlined />}>
                    批量删除 ({selectedSessions.size})
                  </Button>
                </Popconfirm>
              )}
              <Button
                icon={<ReloadOutlined />}
                onClick={handleRefresh}
                loading={loading}
              >
                刷新
              </Button>
              <Button
                icon={<ReloadOutlined />}
                onClick={handleForceRefresh}
                loading={loading}
              >
                强刷
              </Button>
              <Badge count={pagination.total} showZero>
                <Button icon={<CommentOutlined />}>总会话</Button>
              </Badge>
            </Space>
          </Space>

          {/* 搜索栏 */}
          <Search
            placeholder="搜索会话标题..."
            allowClear
            enterButton={
              <>
                <SearchOutlined /> 搜索
              </>
            }
            size="large"
            onSearch={handleSearch}
            loading={loading}
          />

          {/* 会话列表 */}
          <Spin spinning={loading}>
            <List
              grid={{
                gutter: [24, 24],
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
                    className="session-card"
                    style={{ 
                      height: "100%",
                      opacity: session.is_valid ? 1 : 0.5,  // ⭐ 无效会话灰色显示
                      backgroundColor: session.is_valid ? "#fff" : "#f5f5f5"  // ⭐ 灰色背景
                    }}
                    actions={[
                      <Tooltip key="resume" title="继续对话">
                        <Button
                          type="link"
                          icon={<MessageOutlined />}
                          onClick={(e) => {
                            e.stopPropagation(); // 防止事件冒泡
                            handleResume(session.session_id);
                          }}
                          loading={loadingSessionId === session.session_id}
                        >
                          继续
                        </Button>
                      </Tooltip>,
                      <Popconfirm
                        key="delete"
                        title="删除会话"
                        description={`确定要删除"${session.title}"吗？此操作不可恢复。`}
                        onConfirm={() => {
                          handleDelete(session.session_id);
                        }}
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <Tooltip title="删除会话">
                          <Button
                            type="link"
                            danger
                            icon={<DeleteOutlined />}
                            onClick={(e) => e.stopPropagation()} // 防止事件冒泡
                          >
                            删除
                          </Button>
                        </Tooltip>
                      </Popconfirm>,
                    ]}
                    extra={
                      <Checkbox
                        checked={selectedSessions.has(session.session_id)}
                        onChange={(e) => {
                          e.stopPropagation(); // 防止事件冒泡
                          const newSelected = new Set(selectedSessions);
                          if (e.target.checked) {
                            newSelected.add(session.session_id);
                          } else {
                            newSelected.delete(session.session_id);
                          }
                          setSelectedSessions(newSelected);
                        }}
                      />
                    }
                  >
                    {/* 前端小新代修改 VIS-H02: 会话方块内部文字左侧留白 */}
                    <div style={{ padding: "0 10px" }}>
                      <Card.Meta
                        title={
                          <Tooltip title={session.title}>
                            <Text strong ellipsis style={{ maxWidth: 200 }}>
                              {session.title}
                            </Text>
                          </Tooltip>
                        }
                        description={
                          <Space
                            direction="vertical"
                            size="small"
                            style={{ width: "100%" }}
                          >
                            <Space>
                              <Tag icon={<CommentOutlined />} color="blue">
                                {session.message_count ?? 0} 条消息
                              </Tag>
                            </Space>
                            <Space>
                              <ClockCircleOutlined style={{ color: "#999" }} />
                              <Text type="secondary" style={{ fontSize: 12 }}>
                                更新于 {formatTime(session.updated_at)}
                              </Text>
                            </Space>
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              创建于{" "}
                              {dayjs(session.created_at).format(
                                "YYYY-MM-DD HH:mm"
                              )}
                            </Text>
                          </Space>
                        }
                      />
                    </div>
                  </Card>
                </List.Item>
              )}
            />
          </Spin>

          {/* 分页 - 前端小新代修改 VIS-H03: 改用Antd Pagination组件 */}
          {pagination.total > 0 && (
            <div style={{ textAlign: "center", marginTop: 24 }}>
              <Pagination
                current={pagination.current}
                total={pagination.total}
                pageSize={pagination.pageSize}
                onChange={(page) => loadSessions(page, keyword)}
                showSizeChanger={false}
                showQuickJumper
                showTotal={(total) => `共 ${total} 条`}
              />
            </div>
          )}
        </Space>
      </Card>

      {/* 自定义CSS - 卡片hover效果 */}
      <style>{`
         .session-card {
           transition: all 0.3s ease;
         }
         .session-card:hover {
           transform: translateY(-4px);
           box-shadow: 0 8px 24px rgba(0,0,0,0.12);
         }
       `}</style>
    </div>
  );
};

export default HistoryPage;
