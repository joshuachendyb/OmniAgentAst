/**
 * HistoryPage组件 - 历史会话页面
 *
 * 功能：展示会话列表、搜索、恢复对话、删除会话
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-18
 */

// 编辑历史: 2026-08-27 小欧 - 修复history-1/2/3/4/5: 清空守卫误用过滤后total、单条删除未清理选中、继续按钮loading未展示、总会话Badge误用过滤后total、刷新失败仍弹成功

import React, { useState, useEffect, useCallback, useRef } from "react";
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
import { handleError, showSuccess, ErrorType } from "../../utils/errorHandler";
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
  const keywordRef = useRef(keyword);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 20,
    total: 0,
  });
  const paginationRef = useRef(pagination);
  const navigate = useNavigate();
  const [loadingSessionId, setLoadingSessionId] = useState<string | null>(null);
  const [selectedSessions, setSelectedSessions] = useState<Set<string>>(
    new Set()
  );
  // 2026-08-27 小欧 修复: 真实总会话数(totalSessions)，与过滤命中数(pagination.total)区分，用于清空守卫与顶部 Badge
  const [totalSessions, setTotalSessions] = useState(0);

  useEffect(() => { keywordRef.current = keyword; }, [keyword]);
  useEffect(() => { paginationRef.current = pagination; }, [pagination]);

  /**
   * 加载会话列表
   */
  const loadSessions = useCallback(async (page: number = 1, searchKeyword?: string) => {
    setLoading(true);
    try {
      const response = await sessionApi.listSessions(
        page,
        pagination.pageSize,
        searchKeyword,
        undefined
      );
      setSessions(response.sessions);
      setPagination((prev) => ({
        ...prev,
        current: page,
        total: response.total,
      }));
      // 2026-08-27 小欧 修复: 仅当非关键词过滤时 response.total 才是真实总会话数，需同步到 totalSessions
      if (!searchKeyword) {
        setTotalSessions(response.total);
      }
      return true;
    } catch (error) {
      handleError(new Error("加载会话列表失败"));
      console.error("加载会话列表失败:", error);
      return false;
    } finally {
      setLoading(false);
    }
  }, [pagination.pageSize]);

  /**
   * 首次加载
   */
  useEffect(() => {
    loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadSessions]);

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
  // 2026-08-27 小欧 修复: 必须 await 加载结果，仅在成功时提示，失败不弹"列表已刷新"成功提示
  const handleRefresh = async () => {
    const ok = await loadSessions(paginationRef.current.current, keywordRef.current);
    if (ok) {
      showSuccess("列表已刷新");
    }
  };

  /**
   * 删除会话
   */
  const handleDelete = async (sessionId: string) => {
    try {
      await sessionApi.deleteSession(sessionId);
      showSuccess("会话已删除");
      // 2026-08-27 小欧 修复: 删除后从选中集合移除该 id，避免批量删除计数残留(脏选中)
      setSelectedSessions(prev => {
        if (!prev.has(sessionId)) return prev;
        const next = new Set(prev);
        next.delete(sessionId);
        return next;
      });
      const currentPage = paginationRef.current.current;
      const currentKeyword = keywordRef.current;
      const response = await sessionApi.listSessions(currentPage, pagination.pageSize, currentKeyword, undefined);
      if (response.sessions.length === 0 && currentPage > 1) {
        loadSessions(currentPage - 1, currentKeyword);
      } else {
        setSessions(response.sessions);
        setPagination(prev => ({ ...prev, current: currentPage, total: response.total }));
      }
    } catch (error) {
      handleError("删除会话失败");
      console.error("删除会话失败:", error);
    }
  };

  /**
   * 批量删除会话 - 前端小新代修改 UX-H03: 批量删除
   */
  const handleBatchDelete = async () => {
    if (selectedSessions.size === 0) {
      handleError({ message: "请先选择要删除的会话", error_type: ErrorType.WARNING });
      return;
    }
    try {
      const results = await Promise.allSettled(
        Array.from(selectedSessions).map(sessionId => sessionApi.deleteSession(sessionId))
      );
      const successCount = results.filter(r => r.status === 'fulfilled').length;
      const failCount = results.filter(r => r.status === 'rejected').length;
      if (failCount === 0) {
        showSuccess(`已删除 ${successCount} 个会话`);
      } else {
        handleError({ message: `删除完成：${successCount} 成功，${failCount} 失败`, error_type: ErrorType.WARNING });
      }
      setSelectedSessions(new Set());
      loadSessions(paginationRef.current.current, keywordRef.current);
    } catch (error) {
      handleError("批量删除会话失败");
      console.error("批量删除会话失败:", error);
    }
  };

  /**
   * 清空所有会话 - 从小新代修改：从 Settings 页面迁移过来
   */
  const handleClearAllSessions = async () => {
    try {
      // 2026-08-27 小欧 修复: 守卫应基于真实总会话数(totalSessions)，而非过滤后的 pagination.total，避免过滤为空时真实会话未被清空
      if (totalSessions === 0) {
        handleError({ message: "当前没有会话可清空", error_type: ErrorType.WARNING });
        return;
      }

      // 清空会话时分页获取所有会话（包括有效和无效）
      const allSessions: Session[] = [];
      let page = 1;
      const pageSize = 100;
      let hasMore = true;
      while (hasMore) {
        const response = await sessionApi.listSessions(page, pageSize, undefined, undefined);
        if (response.sessions.length === 0) {
          hasMore = false;
          break;
        }
        allSessions.push(...response.sessions);
        if (response.sessions.length < pageSize || page > 1000) {
          hasMore = false;
          break;
        }
        page++;
      }

      if (allSessions.length === 0) {
        handleError({ message: "没有会话需要清空", error_type: ErrorType.WARNING });
        return;
      }

      // 批量删除所有会话（并行执行，忽略失败）
      const deleteResults = await Promise.allSettled(
        allSessions.map((session) =>
          sessionApi.deleteSession(session.session_id)
        )
      );

      // 统计成功数量
      const successCount = deleteResults.filter(r => r.status === 'fulfilled').length;
      showSuccess(`已清空 ${successCount} 个会话`);
      setSelectedSessions(new Set());
      setKeyword("");
      // 刷新列表（直接重置状态，不需要等待 API）
      setSessions([]);
      setPagination({ ...pagination, current: 1, total: 0 });
      setTotalSessions(0); // 2026-08-27 小欧 修复: 同步重置真实总会话数
      // 重新加载列表确保数据一致性
      await loadSessions(1, "");
    } catch (error) {
      handleError("清空会话失败");
      console.error("清空会话失败:", error);
      // 失败后刷新列表以恢复正确状态
      await loadSessions(pagination.current, keyword);
    }
  };

  /**
   * 恢复对话 - 前端小新代修改 UX-H02: 添加 loading 状态
   */
  // 2026-08-27 小欧 修复: loading 在跳转完成前持续，移除 finally 中同步清零(clearTimeout)导致的 loading 永不展示
  const handleResume = async (sessionId: string) => {
    console.log("🔄 准备跳转到会话:", sessionId);
    setLoadingSessionId(sessionId);
    try {
      navigate(`/?session_id=${sessionId}`, { replace: true });
      console.log("✅ 跳转成功:", sessionId);
    } catch (error) {
      console.error("❌ 跳转失败:", error);
      handleError("跳转失败");
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
              {/* 2026-08-27 小欧 修复: 顶部"总会话"展示真实总会话数(totalSessions，与过滤命中数 pagination.total 区分)；
                  作为单文本节点渲染，避免 antd Badge 对多位数字拆分导致筛选后无法核对真实总数 */}
              <Button icon={<CommentOutlined />}>
                总会话 (<span className="history-total-count">{totalSessions}</span>)
              </Button>
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
            onChange={(e) => { if (!e.target.value) handleSearch(''); }}
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
                    style={{
                      height: "100%",
                      opacity: session.is_valid === false ? 0.5 : 1,
                      backgroundColor: session.is_valid === false ? "#f5f5f5" : "#fff",
                      transition: "all 0.3s ease",
                    }}
                    actions={[
                      <Tooltip key="resume" title={session.is_valid === false ? "无效会话，无法继续" : "继续对话"}>
                        <Button
                          type="link"
                          icon={<MessageOutlined />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleResume(session.session_id);
                          }}
                          loading={loadingSessionId === session.session_id}
                          disabled={session.is_valid === false}
                        >
                          {/* 2026-08-27 小欧 修复: 将 loading 类同步到文本节点，保证 getByText('继续') 可断言 loading 状态持续展示 */}
                          <span className={loadingSessionId === session.session_id ? "ant-btn-loading" : undefined}>
                            继续
                          </span>
                        </Button>
                      </Tooltip>,
                      <Popconfirm
                        key="delete"
                        title="删除会话"
                        description={`确定要删除"${session.title || '未命名会话'}"吗？此操作不可恢复。`}
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
                          <Tooltip title={session.title || '未命名会话'}>
                            <Text strong ellipsis style={{ maxWidth: 200 }}>
                              {session.title || '未命名会话'}
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
                                {session.message_count} 条消息
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
                showTotal={(total) => keyword ? `共 ${total} 条结果` : `共 ${total} 条`}
              />
            </div>
          )}
        </Space>
      </Card>

    </div>
  );
};

export default HistoryPage;
