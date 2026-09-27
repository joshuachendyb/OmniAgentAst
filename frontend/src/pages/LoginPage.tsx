/**
 * 登录页 — 输入访问口令（token）
 *
 * 编辑历史:
 *   2026-09-26 小欧 - [72]第九章 新建
 *   2026-09-27 小欧 - [75]5.4 按 4.2.3 状态机重写：状态 1 个扩成 5 个、入口查询不带旧口令
 *     （_skipAuth）、/auth/status 兼作验真探针（替代 /models）、can_set=false 不给输入框、
 *     403 透传后端原话、首设失败专属文案
 *   2026-09-27 小欧 - [75]实施后十轮会审修 3 处：① handleSubmit 增并发守卫（回车不受 Button
 *     loading 约束，连按会重复提交）；② 口令输入框验证中 disabled（避免界面显示值与实际提交值
 *     不一致）；③ 首设提交前复查后端状态（进页结论可能已过期，直接 setToken 会静默覆盖他人刚设的口令）
 *
 * 背景：服务绑 0.0.0.0（多机部署硬前提不可收窄），鉴权前局域网任意设备可直调任何接口
 *   （读走全部 provider 明文密钥 / 改擦密钥 / 越权读会话）。本页是口令录入入口：
 *   输入后存 localStorage，之后由 client.ts 请求拦截器统一附带 `Authorization: Bearer <token>`。
 *
 * 设计约束：
 *   - 口令明文存 localStorage（与 getAccessToken 读取结构一致，不新造第二个存储键）
 *   - 输错只提示"口令无效"，不泄露服务端是否已启用鉴权
 *   - 口令变化即时生效：鉴权头每次请求现取，无需重新登录
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Input } from 'antd';
import { getAccessToken, setAccessToken } from '@/services/api/client';
// 2026-09-26 小欧 - [72]第九章: 统一提示规范（禁 message.*，走 error/handler）
import { ErrorType, showMessage } from '@/services/error/handler';
// 2026-09-26 小欧 - [72]第九章(9.5.3 第1步): 首次设置/查状态走 authApi
import { authApi } from '@/services/api/settings.api';

/** 2026-09-27 小欧 - [75]第5章 5.4：4.2.3 状态机的五个状态（按后端结论分流，前端不猜来源） */
type AuthView =
  | { kind: 'checking' } // 入口查询进行中（结论未到不显示输入框）
  | { kind: 'noAuthNeeded' } // requires_auth=false → 直接进主页
  | { kind: 'firstSetup' } // 未配置 + 可设 → 输入即设置
  | { kind: 'firstSetupElsewhere' } // 未配置 + 不可设 → 只给指引，不给输入框
  | { kind: 'login' }; // 已配置（或查状态失败兜底）→ 登录框，status 当探针验真

const LoginPage: React.FC = () => {
  const [token, setToken] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [view, setView] = useState<AuthView>({ kind: 'checking' });
  const navigate = useNavigate();

  // 进页先取后端结论，按结论分流（前端不判断来源：本机/白名单/有无口令只有后端知道，
  // 浏览器 JS 拿不到自己的真实 IP，自行猜测必然文案与行为对不上）。
  // 入口查询传 _skipAuth（4.2.3 分工①）：拦截器默认附带 localStorage 里的旧口令，
  // 旧口令已作废时会把这次引导查询打成 401/403，导致问不到结论。
  React.useEffect(() => {
    let alive = true;
    void authApi
      .getTokenStatus({ _skipAuth: true })
      .then((st) => {
        if (!alive) return;
        if (!st.current_client_requires_auth) {
          setView({ kind: 'noAuthNeeded' });
          navigate('/', { replace: true });
          return;
        }
        setView(
          st.access_token_configured
            ? { kind: 'login' }
            : st.can_set_access_token
              ? { kind: 'firstSetup' }
              : { kind: 'firstSetupElsewhere' }
        );
      })
      .catch(() => {
        // 查状态失败兜底（4.2.3 要点五）：按"已配置"处理，只让用户输口令。
        // 绝不按"未配置"兜底 —— 那会引导用户去做一次本不该由他做的首设写操作。
        if (alive) setView({ kind: 'login' });
      });
    return () => {
      alive = false;
    };
  }, [navigate]);

  /**
   * 校验口令：用 GET /auth/status 本身当探针（4.2.3 分工②）。
   * 5.1 的豁免只对"不带口令"生效，故带上刚输入的口令去查即得真话：对 200 / 错 401，
   * 无需另设探针端点（早前用 GET /models 验口令，模型列表与鉴权语义无关）。
   * 入口查询已用 _skipAuth 不带旧口令，两次查询互不干扰。
   */
  const handleSubmit = async () => {
    // 并发守卫：回车（onPressEnter）不受 Button loading 约束，连按会并发提交多次
    // （首设场景=重复写口令；登录场景=重复探针 + 重复提示）。最外层拦截所有入口。
    if (verifying) return;
    const val = token.trim();
    if (!val) {
      showMessage(ErrorType.WARNING, '请输入访问口令');
      return;
    }
    setVerifying(true);
    const prev = getAccessToken();
    try {
      // 首次设置：后端尚无口令，直接写入即可（能否设置已由 can_set_access_token 判定）。
      // 不预写本地：POST /auth/token 在可信本机放行，成功后由 setToken 内部同步写入。
      if (view.kind === 'firstSetup') {
        // 提交前复查一次：结论是进页时取的，其间其他本机用户可能已设好口令。
        // 直接 setToken 会静默覆盖他人的设置（后端不校验"是否已存在"），故先确认再写。
        const st = await authApi.getTokenStatus({ _skipAuth: true });
        if (st.access_token_configured) {
          setView({ kind: 'login' });
          showMessage(ErrorType.WARNING, '访问口令已被设置，请直接输入该口令');
          return;
        }
        await authApi.setToken(val);
        navigate('/', { replace: true });
        return;
      }
      // 先写入以带上 Authorization。必须放在 try 之内：5.5 让写失败会抛错，
      // 留在 try 之前则异常没人接 → 按钮永久 loading。
      setAccessToken(val);
      // 验真探针：默认配置（带当前口令、_skip401）。200 → 口令有效；401 → 口令无效。
      await authApi.getTokenStatus();
      navigate('/', { replace: true });
    } catch (e) {
      if (view.kind === 'firstSetup') {
        // 首设失败要与"口令无效"区分开：后端拒（口令太短/env 接管/非本机 403）或本地
        // 存储写失败，都与"口令无效"无关，文案必须指向真实原因（4.4.2）。
        showMessage(
          isForbidden(e) ? ErrorType.AUTH_403 : ErrorType.AUTH_401,
          isForbidden(e)
            ? forbiddenDetail(e)
            : `设置访问口令失败：${messageOf(e)}`
        );
        return;
      }
      // 回滚用 try 包住：5.5 让 setAccessToken 写失败会抛错，回滚再抛会盖掉原错误
      try {
        setAccessToken(prev);
      } catch {
        /* 回滚失败不掩盖原错误 */
      }
      showMessage(
        // 403 是"你不能做这事"、401 是"口令不对"、其余多为网络/服务端异常 —— 三种必须
        // 分开，一律报"访问口令无效"会把用户引向反复重输的死路（错 4/错 6 同类病根）。
        isForbidden(e) ? ErrorType.AUTH_403 : ErrorType.AUTH_401,
        isForbidden(e)
          ? forbiddenDetail(e)
          : statusOf(e) === 401
            ? '访问口令无效'
            : `验证失败：${messageOf(e)}`
      );
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        gap: 16,
      }}
    >
      {view.kind === 'checking' && (
        <div style={{ fontSize: 13, color: '#8c8c8c' }}>
          正在检查访问口令状态…
        </div>
      )}

      {view.kind === 'firstSetupElsewhere' && (
        <div
          style={{
            maxWidth: 380,
            padding: 12,
            border: '1px solid #ffd591',
            background: '#fffbe6',
            borderRadius: 6,
            fontSize: 13,
            color: '#ad6800',
            textAlign: 'left',
            lineHeight: 1.7,
          }}
        >
          <strong>服务端尚未配置访问口令，且不能在当前这台机器上设置</strong>
          <br />
          设置或更换访问口令<strong>只能在服务端那台电脑上</strong>
          进行（安全设计）。
          <br />
          请到服务端本机打开「设置 → 前端 → 登录与准入 →
          访问口令」设置完成后，再回到本页访问。
        </div>
      )}

      {(view.kind === 'login' || view.kind === 'firstSetup') && (
        <>
          <div style={{ fontSize: 20, fontWeight: 600 }}>
            {view.kind === 'firstSetup'
              ? '首次使用，请设置访问口令'
              : '请输入访问口令'}
          </div>
          <div style={{ fontSize: 13, color: '#8c8c8c' }}>
            本服务部署在局域网内，需口令才能访问
          </div>
          {view.kind === 'firstSetup' && (
            <div
              style={{
                maxWidth: 380,
                padding: 12,
                border: '1px solid #ffd591',
                background: '#fffbe6',
                borderRadius: 6,
                fontSize: 13,
                color: '#ad6800',
                textAlign: 'left',
                lineHeight: 1.7,
              }}
            >
              <strong>服务端尚未配置访问口令</strong>
              <br />
              在下面输入一个口令（至少 8
              位）即可进入并保存；之后每次进入都用它。
              <br />
              {/* 路径为「设置 → 前端 → 登录与准入 → 访问口令」：access_token 属 appearance 组
                  （Tab 显示名已改「前端」），security 组只含 4 项操作安全项，照旧文案去 security 组找不到。 */}
              也可稍后在「设置 → 前端 → 登录与准入 → 访问口令」里修改。
            </div>
          )}
          <Input
            style={{ width: 320 }}
            value={token}
            placeholder="访问口令"
            type="password"
            autoComplete="current-password"
            disabled={verifying}
            onChange={(e) => setToken(e.target.value)}
            onPressEnter={() => void handleSubmit()}
          />
          <Button
            type="primary"
            loading={verifying}
            onClick={() => void handleSubmit()}
          >
            进入
          </Button>
        </>
      )}
    </div>
  );
};

export default LoginPage;

/** 2026-09-27 小欧 - [75]第5章 5.4：axios 错误对象里取 HTTP 状态码（axios 内部路径不稳定，不直接摸） */
function statusOf(e: unknown): number | undefined {
  return (e as { response?: { status?: number } } | null)?.response?.status;
}

function isForbidden(e: unknown): boolean {
  return statusOf(e) === 403;
}

/** 后端 detail 原话；没给（网络错误等）返回 undefined，由调用方决定回落文案 */
function detailOf(e: unknown): string | undefined {
  const d = (e as { response?: { data?: { detail?: string } } } | null)
    ?.response?.data?.detail;
  return typeof d === 'string' && d ? d : undefined;
}

/** 403 的 detail 是精确引导（如「只能在服务端本机进行」），优先原话，没给才用兜底串 */
function forbiddenDetail(e: unknown): string {
  return detailOf(e) ?? '此操作不被允许，请按提示处理';
}

/** 给用户看的错误文本：后端 detail 原话优先，其次错误对象自身 message（网络错误等） */
function messageOf(e: unknown): string {
  return detailOf(e) ?? (e instanceof Error ? e.message : String(e));
}
