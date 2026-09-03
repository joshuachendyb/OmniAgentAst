// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复对象属性/JSX属性行超80字符换行、import重排, 防止格式再次出错
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①AM-01 request变化重置trustSession防跨请求残留②AM-02 Modal加maskClosable=false+keyboard=false防幽灵关闭死锁 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 - v1.5.4 弹窗渲染完善: 环形进度Progress+大数字倒计时+最后5s转橙3s微脉动+bypass标题补全+countdown到0自动代发/拒绝 — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 - 三堂会审问题1方案A+问题3优化: ①handleConfirm强制bypass下trustSession=false(防bypass勾选偷偷落库转正为长期信任, 堵5.4防污染漏洞); ②countdown interval依赖数组移除countdown(函数式更新, 只在弹窗开/新请求建一次) — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 Bug修复(24项): ⑪countdown lazy初值跟随request防首渲染0误触发 ⑬/⑲autoHandledRef按confirmId一次性guard防倒计时到0 effect重入双发 ⑰submitting互斥态防连点意图翻转(按钮loading/disabled+勾选disabled) ⑳后端兜底文案5→60与实际一致 ㉑首tick 100ms即-1节奏对齐 ㉘trustPath缺失文案改"未指定路径，仅本次"防"任意整工具"误导 — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 UI优化(v1.1方案): 降高100px(420→288): Modal padding24→12+图标48→32+Title level4→5+Tag margin16→4+Progress size88→60+双卡合一(maxHeight200→150)+Checkbox margin24→12+Space→flex gap12+段距16→8 — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 UI优化第四章实施: 边框2px→1.5px+boxShadow+Title Tag同行flex+动效pulse0.8s/opacity0.7+信任行缩写"信任此操作（本次会话）"+Tooltip展开路径+去Space导入加Tooltip — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 P1修复: handleConfirm中autoHandledRef先设再调onConfirm, 堵countdown到0+用户同帧点击双发onConfirm时序缺口; P3: @keyframes pulse移至组件外避免重复注入 — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧/北京老陈: countdown就绪守卫 — 跨弹窗countdown残留0致新弹窗首帧即触发自动代发, 加countdownReadyRef守卫, 未就绪禁止代发
// 编辑历史: 2026-09-03 小欧/北京老陈 根因修复: onConfirm接口加confirmId参数, auto-confirm不依赖pendingRef读confirmId(改前ref时序竞态致旧弹窗auto-confirm发旧ID到后端, 新ID从未被confirm→S1超时弹窗不消失) — 小欧/北京老陈-2026-09-03
/**
 * AuthorizationModal - HITL人工确认弹窗
 *
 * 功能：显示工具执行授权请求，用户可选择允许/拒绝/本会话信任
 *
 * 设计规范（参考DangerConfirmModal）：
 * - 宽度: 480px
 * - 边框: 1.5px solid #faad14 (橙色) / 1.5px dashed #1677ff (bypass) + boxShadow
 * - 图标: WarningOutlined (橙色, 32px)
 * - 按钮: "允许执行"（橙色）、"拒绝执行"（danger ghost）/ bypass时保留按钮可点击
 * - 居中对齐
 *
 * 【v3.4实施 2026-06-09 小沈】
 * - SRP: 只负责显示授权弹窗和回传用户选择
 * - KISS: 简单Modal + 3个按钮，不搞复杂状态
 * - DRY: 复用Ant Design Modal组件
 */

import React from 'react';
import {
  Modal,
  Button,
  Typography,
  Tag,
  Checkbox,
  Progress,
  Tooltip,
} from 'antd';
import {
  WarningOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
} from '@ant-design/icons';

const { Text, Title } = Typography;

export interface AuthorizationRequest {
  confirmId: string;
  toolName: string;
  params: Record<string, unknown>;
  safetyLevel: string;
  trustPath?: string | null;
  autoConfirm?: boolean;
  confirmTimeout?: number;
  backendTimeout?: number;
}

interface AuthorizationModalProps {
  visible: boolean;
  request: AuthorizationRequest | null;
  onConfirm: (confirmed: boolean, trustSession: boolean, confirmId?: string) => void;
}

const SAFETY_LEVEL_CONFIG: Record<
  string,
  { color: string; label: string; icon: React.ReactNode }
> = {
  read_only: { color: 'green', label: '只读', icon: null },
  safe: { color: 'blue', label: '安全', icon: null },
  destructive: { color: 'orange', label: '破坏性', icon: <WarningOutlined /> },
  dangerous_sandbox: {
    color: 'volcano',
    label: '沙箱危险',
    icon: <ExclamationCircleOutlined />,
  },
  dangerous: { color: 'red', label: '系统危险', icon: <StopOutlined /> },
};

// 2026-09-03 小欧 P3修复: @keyframes pulse移至组件外, 避免每次渲染重复注入<style>标签 — 小欧-2026-09-03
const AUTH_MODAL_STYLE = `
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.7; }
  }
`;

const AuthorizationModal: React.FC<AuthorizationModalProps> = ({
  visible,
  request,
  onConfirm,
}) => {
  // 2026-09-03 小欧 Bug-11: countdown 用 lazy 初值(跟随新 request), 避免默认 0 触发首渲染自动代发/拒绝
  const [trustSession, setTrustSession] = React.useState(false);
  const [countdown, setCountdown] = React.useState(
    () => request?.confirmTimeout ?? 0
  );
  const onConfirmRef = React.useRef(onConfirm);
  // 2026-09-03 小欧 Bug-13/29: autoHandledRef 按 confirmId 一次性 guard, 防倒计时到 0 后 effect 重入双发
  const autoHandledRef = React.useRef<string | null>(null);
  // 2026-09-03 小欧/北京老陈: countdown就绪守卫 — 倒计时状态跨弹窗残留0, 新弹窗未重置前禁止自动代发
  const countdownReadyRef = React.useRef<string | null>(null);
  // 2026-09-03 小欧 Bug-17: submitting 互斥态, 提交中禁用按钮/勾选, 防连点意图翻转
  const [submitting, setSubmitting] = React.useState(false);
  const isBypass = Boolean(request?.autoConfirm);
  onConfirmRef.current = onConfirm;

  React.useEffect(() => {
    setTrustSession(false);
    setSubmitting(false);
    if (request?.confirmId) {
      setCountdown(request.confirmTimeout ?? 0);
      autoHandledRef.current = null;
      countdownReadyRef.current = request.confirmId;
    }
  }, [request?.confirmId, request?.confirmTimeout]);

  React.useEffect(() => {
    // 2026-09-03 小欧 Bug-21: 首 tick 100ms 内即刻 -1(节奏对齐), 再走 1s interval; 依赖无 countdown(函数式更新)
    if (!visible || !request) return;
    const tick = () => setCountdown((v) => Math.max(0, v - 1));
    const t = setInterval(tick, 1000);
    const first = setTimeout(tick, 100);
    return () => {
      clearInterval(t);
      clearTimeout(first);
    };
  }, [visible, request]);

  React.useEffect(() => {
    if (!visible || countdown !== 0 || !request) return;
    // 2026-09-03 小欧/北京老陈: 就绪守卫 — countdown跨弹窗残留0时新弹窗未重置前禁止代发
    if (countdownReadyRef.current !== request.confirmId) return;
    // 2026-09-03 小欧 Bug-13/29: 同 confirmId 只代发一次, 防止 effect 因 deps 变化重入双发
    if (autoHandledRef.current === request.confirmId) return;
    autoHandledRef.current = request.confirmId;
    setSubmitting(true);
    // 2026-09-03 小欧/北京老陈: 传confirmId参数, 不依赖pendingRef时序(根因修复)
    if (isBypass) {
      onConfirmRef.current(true, false, request.confirmId);
    } else {
      onConfirmRef.current(false, false, request.confirmId);
    }
  }, [visible, countdown, isBypass, request]);

  if (!request) {
    return null;
  }

  const safetyConfig = SAFETY_LEVEL_CONFIG[request.safetyLevel] || {
    color: 'default',
    label: request.safetyLevel,
    icon: null,
  };

  const confirmTimeout = request.confirmTimeout ?? 60;
  const progressPercent =
    confirmTimeout > 0 ? Math.round((countdown / confirmTimeout) * 100) : 0;
  const strokeColor =
    countdown <= 3 ? '#fa541c' : countdown <= 5 ? '#faad14' : '#1677ff';

  // 小欧 2026-09-03 三堂会审问题1方案A: bypass(安全开关绕开)模式下即使勾选"信任此操作"也不产生信任,
  //   强制 trustSession=false(防绕过5.4防污染: bypass期间勾出的信任切回enabled:true后转正为长期豁免)
  const handleConfirm = (confirmed: boolean) => {
    if (submitting) return;
    // 2026-09-03 小欧 P1修复: 先设 guard 再调 onConfirm——堵 countdown effect 同帧双发(时序缺口: submitting state异步生效, countdown effect同帧看到 submitting=false 也能通过guard)
    autoHandledRef.current = request.confirmId;
    setSubmitting(true);
    // 2026-09-03 小欧/北京老陈: 传confirmId参数, 不依赖pendingRef时序(根因修复)
    onConfirm(confirmed, isBypass ? false : trustSession, request.confirmId);
    setTrustSession(false);
  };

  return (
    <Modal
      open={visible}
      title={null}
      footer={null}
      closable={false}
      maskClosable={false}
      keyboard={false}
      width={480}
      style={{
        border: isBypass ? '1.5px dashed #1677ff' : '1.5px solid #faad14',
        borderRadius: '8px',
        overflow: 'hidden',
        boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
      }}
      styles={{
        body: {
          padding: '12px',
        },
      }}
    >
      <div style={{ textAlign: 'center' }}>
        <WarningOutlined
          style={{
            fontSize: 32,
            color: isBypass ? '#1677ff' : '#faad14',
            marginBottom: 8,
          }}
        />

        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: 4,
          }}
        >
          <Title level={5} style={{ marginBottom: 0 }}>
            {isBypass ? '将自动确认（安全开关已绕开）' : '安全确认请求'}
          </Title>
          <Tag
            color={safetyConfig.color}
            style={{ marginBottom: 0, fontSize: 14 }}
          >
            {safetyConfig.label}
          </Tag>
        </div>

        <div style={{ textAlign: 'center', marginBottom: 4 }}>
          <Progress
            type="circle"
            size={60}
            percent={progressPercent}
            strokeColor={strokeColor}
            strokeWidth={5}
            format={() => (
              <div style={{ textAlign: 'center', lineHeight: 1.2 }}>
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 600,
                    color: countdown <= 3 ? '#fa541c' : '#333',
                    animation:
                      countdown <= 3
                        ? 'pulse 0.8s ease-in-out infinite'
                        : 'none',
                  }}
                >
                  {countdown}
                </div>
                <div style={{ fontSize: 11, color: '#8c8c8c' }}>秒</div>
              </div>
            )}
          />
        </div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: '#8c8c8c',
            marginBottom: 4,
          }}
        >
          {/* 2026-09-03 小欧 Bug-20: 后端兜底原文案 5s 与实际 60s 不符(useAuthorization 兜底即 60), 统一为 60 防文案欺骗 */}
          {isBypass
            ? `将在 ${countdown}s 后自动确认（后端 ${request.backendTimeout ?? 60}s 兜底）`
            : `未响应将在 ${countdown}s 后自动拒绝`}
        </div>

        <div
          style={{
            backgroundColor: '#fafafa',
            border: '1px solid #f0f0f0',
            borderRadius: 4,
            padding: 8,
            marginBottom: 8,
            textAlign: 'left',
            maxHeight: 150,
            overflow: 'auto',
          }}
        >
          <div style={{ marginBottom: 4 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              工具名称：
            </Text>
            <br />
            <Text
              strong
              style={{ display: 'block', marginTop: 4, fontSize: 14 }}
            >
              {request.toolName}
            </Text>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 12 }}>
              执行参数：
            </Text>
            <br />
            <Text
              code
              style={{
                display: 'block',
                marginTop: 4,
                fontSize: 12,
                wordBreak: 'break-all',
              }}
            >
              {JSON.stringify(request.params, null, 2)}
            </Text>
          </div>
        </div>

        <div style={{ marginBottom: 12 }}>
          <Checkbox
            checked={trustSession}
            disabled={submitting}
            onChange={(e) => setTrustSession(e.target.checked)}
          >
            {request.trustPath ? (
              <Tooltip
                title={`${request.toolName} › ${request.trustPath}，含子目录`}
              >
                <span>信任此操作（本次会话）</span>
              </Tooltip>
            ) : (
              '信任此操作（本次会话）'
            )}
          </Checkbox>
        </div>

        <div style={{ display: 'flex', gap: 12, width: '100%' }}>
          <Button
            onClick={() => handleConfirm(false)}
            size="large"
            disabled={submitting}
            danger
            ghost
            style={{ flex: 1 }}
          >
            拒绝执行
          </Button>
          <Button
            type="primary"
            onClick={() => handleConfirm(true)}
            size="large"
            loading={submitting}
            disabled={submitting}
            style={{
              backgroundColor: '#faad14',
              borderColor: '#faad14',
              color: '#fff',
              flex: 1,
            }}
          >
            允许执行
          </Button>
        </div>
      </div>
      <style>{AUTH_MODAL_STYLE}</style>
    </Modal>
  );
};

export default AuthorizationModal;
