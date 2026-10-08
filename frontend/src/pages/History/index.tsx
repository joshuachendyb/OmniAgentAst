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
// 编辑历史: 2026-08-30 小欧 - 修复: handleDelete 单删后 setTotalSessions 加 !currentKeyword 守卫 — 过滤态下 list_sessions 返回的 total 为命中数而非真实总数，
//           与 loadSessions 守卫对齐，防过滤态单删污染 totalSessions 致清空守卫误判"没有会话可清空"、总会话 Badge 显示错误数
// 编辑历史: 2026-09-09 小欧 - 会话页console日志治理(北京老陈指示「该清理的清理」): handleResume 删「✅ 跳转成功」打点——
//   navigate 未抛异常即成功, 成功打点与「🔄 准备跳转」冗余; 保留准备/失败打点(追踪价值) — 小欧-2026-09-09
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.19 删除会话后清理 Store(4.6.2 语义, destroySession 见 5.4):
//   ①单删 handleDelete 后端确认成功即 destroySession; ②批量删改先取 targets 快照, 再按
//   allSettled 结果**只清理 fulfilled 者**(失败者保留以便重试, 不误清可重试会话);
//   ③清空全部同口径(按 allSessions 下标对齐 deleteResults) —— 后端已删而 Store 残留会导致
//   快照/草稿泄漏, 重进页重放已删会话内容 — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-10-05 22:16:38 小欧 - 新增在跑任务指示(北京老陈指令, SIG-A+B):
//   ①顶部一览条(Alert)列「当前 N 个会话在跑」+每个会话 Tag 可点直达(仅提醒, 用户主动点击才进入, 不抢占当前页面);
//   ②卡片角标 Tag(状态=运行中/已暂停/重连中)。数据源复用 chatStreamStore.getSnapshot(session_id).status
//   与新增的 getActiveSessionStatusList(), 零新接口。活性刷新: 用 chatStreamStore.subscribe 对当前在跑会话订阅,
//   终态转变时 tick 重渲染; 列表每次增删改查也会重跑 loadSessions 从而换绑订阅(不可见的已暂停→恢复→终态翻转仍可见) — 小欧-2026-10-05
// 编辑历史: 2026-10-08 小欧 - 文档[19] 遗留缺口修复 + 历史卡片版式定案(北京老陈逐条定案):
//   病根: 卡片标题只作展示, 能进会话的入口只有"继续"小图标与顶部 Alert 里的 Tag —— 点标题(最自然的
//   入口)毫无反应, 观感即"历史会话进不去"。
//   定案(全部零新增状态变量, 一律复用既有 handleResume 与 is_valid 语义):
//   ① 标题可点进入会话: 置于卡片左上角(与右上角勾选框同一行)、左对齐; 无效会话标题 not-allowed 且不跳,
//      与"继续"按钮 disabled 语义一致; is_valid 判定提为 renderItem 内局部常量 invalid 供四处复用(DRY)。
//   ② 跳转入口收敛为「继续」按钮 + 「标题」两处(实测点卡片正文/底栏空白不再跳转), 避免"看卡片就跳走"。
//   ③ 中间区域保留消息数 + 原卡片状态角标(运行中/已暂停/重连中, 北京老陈确认保留; 中间不再新增其他信息)。
//   ④ 更新时间与创建时间合并为同一行。
//   ⑤ 不再给 Card 挂整卡 onClick —— 实测该做法会把"点勾选框"也带进会话(click 先于 change 冒泡,
//      靠 onChange 里的 stopPropagation 拦不住), 故从根上不加整卡点击, 只保留上述两个显式入口。
//   治法与文档[19] 减锁同源: 修根因(入口缺失/入口过多)而非在调用点打补丁 — 小欧-2026-10-08

import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  Tooltip,
  Pagination,
  Checkbox,
  Alert,
} from 'antd';
import {
  HistoryOutlined,
  SearchOutlined,
  DeleteOutlined,
  MessageOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  CommentOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { sessionApi, type Session } from '../../services/api/session.api';
// [63] 5.19 v1.30：删除会话确认后清理 Store（4.6.2 语义，destroySession 见 5.4）
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import { getActiveSessionStatusList } from '@/features/chat/streams/chatStreamStore';
import { Spacing } from '@/utils/stepStyles';
import { useNavigate } from 'react-router-dom';
import { handleError, showSuccess, ErrorType } from '@/services/error/handler';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/zh-cn';
import { formatDate } from '@/utils/time'; // 2026-08-28 小欧 合并time模块: formatTime统一至utils/time.ts

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

  // 2026-10-05 22:16:38 小欧 - 在跑任务指示(SIG-A+B)：tick 只驱动重渲染，真源在 chatStreamStore。
  //   非订阅时历史列表不刷新；此处对当前在跑会话各自 subscribe，终态翻转时 tick 一次即驱动角标/条隐藏 —
  //   列表每次 loadSessions 也会换绑订阅(增/删/改后重新读 getActiveSessionStatusList)。
  const [, setRunTick] = useState(0);
  useEffect(() => {
    const active = getActiveSessionStatusList();
    const unsubs = active.map(({ sessionId }) =>
      chatStreamStore.subscribe(sessionId, () => setRunTick((n) => n + 1))
    );
    return () => unsubs.forEach((u) => u());
  }, [sessions]);

  // 渲染期一次性读取「会话→在跑状态」表，角标与顶部条共用，不拆两次扫描（DRY）
  const activeStatusById = new Map<string, string>(
    getActiveSessionStatusList().map((a) => [a.sessionId, a.status])
  );
  const activeCount = activeStatusById.size;

  useEffect(() => {
    keywordRef.current = keyword;
  }, [keyword]);
  useEffect(() => {
    paginationRef.current = pagination;
  }, [pagination]);

  /**
   * 加载会话列表
   */
  const loadSessions = useCallback(
    async (page: number = 1, searchKeyword?: string) => {
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
        handleError(new Error('加载会话列表失败'));
        console.error('加载会话列表失败:', error);
        return false;
      } finally {
        setLoading(false);
      }
    },
    [pagination.pageSize]
  );

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
    const ok = await loadSessions(
      paginationRef.current.current,
      keywordRef.current
    );
    if (ok) {
      showSuccess('列表已刷新');
    }
  };

  /**
   * 删除会话
   */
  const handleDelete = async (sessionId: string) => {
    try {
      await sessionApi.deleteSession(sessionId);
      // [63] 5.19 v1.30：后端确认删除后清理 Store+快照+草稿（4.6.2，语义见 5.4）
      chatStreamStore.destroySession(sessionId);
      showSuccess('会话已删除');
      // 2026-08-27 小欧 修复: 删除后从选中集合移除该 id，避免批量删除计数残留(脏选中)
      setSelectedSessions((prev) => {
        if (!prev.has(sessionId)) return prev;
        const next = new Set(prev);
        next.delete(sessionId);
        return next;
      });
      const currentPage = paginationRef.current.current;
      const currentKeyword = keywordRef.current;
      const response = await sessionApi.listSessions(
        currentPage,
        pagination.pageSize,
        currentKeyword,
        undefined
      );
      if (response.sessions.length === 0 && currentPage > 1) {
        loadSessions(currentPage - 1, currentKeyword);
      } else {
        setSessions(response.sessions);
        setPagination((prev) => ({
          ...prev,
          current: currentPage,
          total: response.total,
        }));
        // 编辑历史: 2026-08-28 老杨 - 单删后同步更新totalSessions，与批量删/清空逻辑一致
        // 2026-08-30 小欧 修复: 过滤态下 response.total 为命中数，仅非过滤时才是真实总数(与 loadSessions L110 守卫对齐)，
        //                     避免单删后 totalSessions 被过滤命中数污染，致清空守卫误判、总会话数显示错误
        if (!currentKeyword) {
          setTotalSessions(response.total);
        }
      }
    } catch (error) {
      handleError('删除会话失败');
      console.error('删除会话失败:', error);
    }
  };

  /**
   * 批量删除会话 - 前端小新代修改 UX-H03: 批量删除
   */
  const handleBatchDelete = async () => {
    if (selectedSessions.size === 0) {
      handleError({
        message: '请先选择要删除的会话',
        error_type: ErrorType.WARNING,
      });
      return;
    }
    try {
      const targets = Array.from(selectedSessions);
      const results = await Promise.allSettled(
        targets.map((sessionId) => sessionApi.deleteSession(sessionId))
      );
      // [63] 5.19 v1.30：成功者逐个清理 Store，失败者保留可重试（4.6.2）
      results.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          chatStreamStore.destroySession(targets[i]);
        }
      });
      const successCount = results.filter(
        (r) => r.status === 'fulfilled'
      ).length;
      const failCount = results.filter((r) => r.status === 'rejected').length;
      if (failCount === 0) {
        showSuccess(`已删除 ${successCount} 个会话`);
      } else {
        handleError({
          message: `删除完成：${successCount} 成功，${failCount} 失败`,
          error_type: ErrorType.WARNING,
        });
      }
      setSelectedSessions(new Set());
      loadSessions(paginationRef.current.current, keywordRef.current);
    } catch (error) {
      handleError('批量删除会话失败');
      console.error('批量删除会话失败:', error);
    }
  };

  /**
   * 清空所有会话 - 从小新代修改：从 Settings 页面迁移过来
   */
  const handleClearAllSessions = async () => {
    try {
      // 2026-08-27 小欧 修复: 守卫应基于真实总会话数(totalSessions)，而非过滤后的 pagination.total，避免过滤为空时真实会话未被清空
      if (totalSessions === 0) {
        handleError({
          message: '当前没有会话可清空',
          error_type: ErrorType.WARNING,
        });
        return;
      }

      // 清空会话时分页获取所有会话（包括有效和无效）
      const allSessions: Session[] = [];
      let page = 1;
      const pageSize = 100;
      let hasMore = true;
      while (hasMore) {
        const response = await sessionApi.listSessions(
          page,
          pageSize,
          undefined,
          undefined
        );
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
        handleError({
          message: '没有会话需要清空',
          error_type: ErrorType.WARNING,
        });
        return;
      }

      // 批量删除所有会话（并行执行，忽略失败）
      const deleteResults = await Promise.allSettled(
        allSessions.map((session) =>
          sessionApi.deleteSession(session.session_id)
        )
      );
      // [63] 5.19 v1.30：清空全部的成功者逐个清理 Store，口径同批量删（4.6.2）
      deleteResults.forEach((r, i) => {
        if (r.status === 'fulfilled') {
          chatStreamStore.destroySession(allSessions[i].session_id);
        }
      });

      // 统计成功数量
      const successCount = deleteResults.filter(
        (r) => r.status === 'fulfilled'
      ).length;
      showSuccess(`已清空 ${successCount} 个会话`);
      setSelectedSessions(new Set());
      setKeyword('');
      // 编辑历史: 2026-08-28 老杨 - setPagination使用函数式更新避免闭包陈旧
      // 刷新列表（直接重置状态，不需要等待 API）
      setSessions([]);
      setPagination((prev) => ({ ...prev, current: 1, total: 0 }));
      setTotalSessions(0); // 2026-08-27 小欧 修复: 同步重置真实总会话数
      // 重新加载列表确保数据一致性
      await loadSessions(1, '');
    } catch (error) {
      handleError('清空会话失败');
      console.error('清空会话失败:', error);
      // 编辑历史: 2026-08-28 老杨 - catch中使用ref.current避免闭包陈旧值
      // 失败后刷新列表以恢复正确状态
      await loadSessions(paginationRef.current.current, keywordRef.current);
    }
  };

  /**
   * 恢复对话 - 前端小新代修改 UX-H02: 添加 loading 状态
   */
  // 2026-08-27 小欧 修复: loading 在跳转完成前持续，移除 finally 中同步清零(clearTimeout)导致的 loading 永不展示
  const handleResume = async (sessionId: string) => {
    console.log('🔄 准备跳转到会话:', sessionId);
    setLoadingSessionId(sessionId);
    try {
      navigate(`/?session_id=${sessionId}`, { replace: true });
    } catch (error) {
      console.error('❌ 跳转失败:', error);
      handleError('跳转失败');
      setLoadingSessionId(null);
    }
  };

  return (
    // 前端小新代修改 VIS-H01: 历史记录页面内部留白
    // 原因: index.css 中 .ant-card-body { padding: 0 !important; } 会覆盖 Card 组件的 bodyStyle 属性
    // 解决方案: 通过外层 div 的 padding 来控制页面内部留白，padding 值为 25px（上下左右统一）
    <div
      className="history-page"
      style={{ padding: '25px', background: '#fff' }}
    >
      <Card bordered={false}>
        <Space
          direction="vertical"
          style={{ width: '100%', padding: '0 5px' }}
          size="large"
        >
          {/* 标题栏 */}
          <Space style={{ justifyContent: 'space-between', width: '100%' }}>
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
                总会话 (
                <span className="history-total-count">{totalSessions}</span>)
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
            onChange={(e) => {
              if (!e.target.value) handleSearch('');
            }}
            loading={loading}
          />

          {/* 2026-10-05 22:16:38 小欧 - 顶部一览条(方案B)：有活跃会话时显示「当前 N 个会话在跑」，
              每个 Tag 点击直达（用户主动导航，不抢占当前页面）；空状态直接不渲染，避免占位 */}
          {activeCount > 0 && (
            <Alert
              type="info"
              showIcon
              icon={<LoadingOutlined spin />}
              style={{ marginTop: Spacing.MD, marginBottom: Spacing.MD }}
              message={
                <Space wrap size={Spacing.SM}>
                  <Text strong>当前 {activeCount} 个会话在跑：</Text>
                  {getActiveSessionStatusList()
                    .slice(0, 3)
                    .map((a) => {
                      const s = sessions.find(
                        (x) => x.session_id === a.sessionId
                      );
                      return (
                        <Tag
                          key={a.sessionId}
                          style={{ cursor: 'pointer' }}
                          color={
                            a.status === 'paused' ? 'warning' : 'processing'
                          }
                          onClick={() => handleResume(a.sessionId)}
                        >
                          {s?.title || '未命名会话'}
                        </Tag>
                      );
                    })}
                  {activeCount > 3 && (
                    <Text type="secondary">另 {activeCount - 3} 条</Text>
                  )}
                </Space>
              }
            />
          )}

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
              renderItem={(session) => {
                // 2026-10-08 小欧 - 无效会话不可继续的单一判定, 供 style/Tooltip/disabled/标题点击四处复用(DRY)
                const invalid = session.is_valid === false;
                return (
                  <List.Item>
                    <Card
                      hoverable
                      size="small"
                      style={{
                        height: '100%',
                        opacity: invalid ? 0.5 : 1,
                        backgroundColor: invalid ? '#f5f5f5' : '#fff',
                        transition: 'all 0.3s ease',
                      }}
                      // 2026-10-08 小欧(北京老陈定案) - 卡片四行全部自排版, 不用 antd 的 extra/actions:
                      //   ① extra 渲染在 Card 的 head 行, 与 body 里的 Card.Meta 标题不同行, 会多出一条
                      //      "只有勾选框的空带"(截图实证); ② styles.actions 只压得住容器 padding, 压不动
                      //      actions>li 自身 padding, 操作行仍过高。改为 body 内自排版后两问题同时消失,
                      //      且不新增 CSS 文件、不用全局选择器。
                      styles={{ body: { padding: '10px 12px' } }}
                    >
                      <Space
                        direction="vertical"
                        size={6}
                        style={{ width: '100%' }}
                      >
                        {/* 第1行(卡片左上角): 标题(左, 可点进入会话) + 勾选框(右);
                          行下加一条分割线, 把标题区与其下的信息区分开(北京老陈定案) */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: 8,
                            borderBottom: '1px solid #f0f0f0',
                            paddingBottom: 6,
                          }}
                        >
                          <Tooltip title={session.title || '未命名会话'}>
                            <Text
                              strong
                              ellipsis
                              style={{
                                flex: 1,
                                minWidth: 0,
                                textAlign: 'left',
                                cursor: invalid ? 'not-allowed' : 'pointer',
                              }}
                              onClick={() => {
                                if (invalid) return;
                                handleResume(session.session_id);
                              }}
                            >
                              {session.title || '未命名会话'}
                            </Text>
                          </Tooltip>
                          <Checkbox
                            checked={selectedSessions.has(session.session_id)}
                            onChange={(e) => {
                              const newSelected = new Set(selectedSessions);
                              if (e.target.checked) {
                                newSelected.add(session.session_id);
                              } else {
                                newSelected.delete(session.session_id);
                              }
                              setSelectedSessions(newSelected);
                            }}
                          />
                        </div>

                        {/* 第2行(中间): 消息数 + 卡片状态角标(运行中/已暂停/重连中);
                        后者由 activeStatusById 驱动, 北京老陈确认保留(此前误删, 已恢复原位置) */}
                        <div>
                          <Space size={6} wrap>
                            <Tag icon={<CommentOutlined />} color="blue">
                              {session.message_count} 条消息
                            </Tag>
                            {/* 2026-10-05 22:16:38 小欧 - 卡片角标(方案A)：在跑/已暂停/重连中才渲染，终态或
                            idle 不吵用户视线；状态 → 颜色与文案由同一张表驱动（DRY，改一处全卡联动） */}
                            {(() => {
                              const st = activeStatusById.get(
                                session.session_id
                              );
                              if (!st) return null;
                              const TAG: Record<
                                string,
                                { color: string; text: string }
                              > = {
                                active: { color: 'processing', text: '运行中' },
                                paused: { color: 'warning', text: '已暂停' },
                                recovering: { color: 'blue', text: '重连中' },
                                // 2026-10-08 小欧(北京老陈定案) - 补 retrying: StreamStatus 活跃态共 4 个
                                //   (active/paused/recovering/retrying), 原 TAG 表漏了它, t 为 undefined
                                //   直接返回 null → 重试中的会话卡片不显示任何角标(静默丢失)。独立显示「重试中」。
                                retrying: { color: 'gold', text: '重试中' },
                              };
                              const t = TAG[st];
                              return t ? (
                                <Tag
                                  color={t.color}
                                  icon={<LoadingOutlined spin />}
                                >
                                  {t.text}
                                </Tag>
                              ) : null;
                            })()}
                          </Space>
                        </div>

                        {/* 第3行: 更新时间靠左、创建时间靠右(同一行, 北京老陈定案) */}
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                          }}
                        >
                          <ClockCircleOutlined style={{ color: '#999' }} />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            更新于 {formatDate(session.updated_at)}
                          </Text>
                          <span style={{ flex: 1 }} />
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            创建于{' '}
                            {dayjs(session.created_at).format(
                              'YYYY-MM-DD HH:mm'
                            )}
                          </Text>
                        </div>

                        {/* 第4行: 继续 / 删除(自排版, 高度可控) */}
                        <div
                          style={{
                            display: 'flex',
                            gap: 4,
                            borderTop: '1px solid #f0f0f0',
                            paddingTop: 4,
                          }}
                        >
                          <Button
                            type="link"
                            size="small"
                            icon={<MessageOutlined />}
                            onClick={() => handleResume(session.session_id)}
                            loading={loadingSessionId === session.session_id}
                            disabled={invalid}
                            style={{ padding: '0 4px', height: 22 }}
                          >
                            {/* 2026-08-27 小欧 修复: 将 loading 类同步到文本节点，保证 getByText('继续') 可断言 loading 状态持续展示 */}
                            <span
                              className={
                                loadingSessionId === session.session_id
                                  ? 'ant-btn-loading'
                                  : undefined
                              }
                            >
                              继续
                            </span>
                          </Button>
                          <Popconfirm
                            title="删除会话"
                            description={`确定要删除"${
                              session.title || '未命名会话'
                            }"吗？此操作不可恢复。`}
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
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                style={{ padding: '0 4px', height: 22 }}
                              >
                                删除
                              </Button>
                            </Tooltip>
                          </Popconfirm>
                        </div>
                      </Space>
                    </Card>
                  </List.Item>
                );
              }}
            />
          </Spin>

          {/* 分页 - 前端小新代修改 VIS-H03: 改用Antd Pagination组件 */}
          {pagination.total > 0 && (
            <div style={{ textAlign: 'center', marginTop: 24 }}>
              <Pagination
                current={pagination.current}
                total={pagination.total}
                pageSize={pagination.pageSize}
                onChange={(page) => loadSessions(page, keyword)}
                showSizeChanger={false}
                showQuickJumper
                showTotal={(total) =>
                  keyword ? `共 ${total} 条结果` : `共 ${total} 条`
                }
              />
            </div>
          )}
        </Space>
      </Card>
    </div>
  );
};

export default HistoryPage;
