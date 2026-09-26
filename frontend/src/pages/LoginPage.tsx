/**
 * 登录页 — 输入访问口令（token）
 *
 * 编辑历史:
 *   2026-09-26 - 小欧 - [72]第九章(9.5.3 / 9.6-2 / 9.6-4) 新建
 *
 * 背景（第九章）：服务绑 0.0.0.0（多机部署硬前提不可收窄），原先**零身份验证** ——
 *   局域网任意设备/程序/网页跨源请求都能直调任何接口（读走全部 provider 明文密钥 / 改擦密钥 / 越权读会话）。
 *   本页是"token 分发"的落地：用户在此输入暗号（token），存入 localStorage，
 *   之后所有请求由 client.ts 自动附带 `Authorization: Bearer <token>`。
 *
 * 四步操作（对应 9.5.3）：
 *   第1步 服务端在设置里填口令（security.api_token）或环境变量 OMNIAGENT_API_TOKEN
 *   第2步 打开本页输入口令 ← 本文件
 *   第3步 输对即记住（localStorage），以后不用再输；输错进不去
 *   第4步 口令泄露 → 在设置里改成新口令，旧口令立即作废
 *
 * 设计约束：
 *   - 口令**明文存 localStorage**（与既有 getAccessToken 读取结构 omniagent_auth 一致，不新造第二套存储键）
 *   - 输错不提示"口令错误"以外的信息（不泄露服务端是否已启用鉴权）
 *   - 口令变化即时生效：无需重新登录，前端每次请求都带当前值
 */
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Input } from 'antd';
import api, { getAccessToken, setAccessToken } from '@/services/api/client';
import type { ApiRequestConfig } from '@/services/api/client';
// 2026-09-26 小欧 - [72]第九章: 统一提示规范（禁 message.*，走 error/handler）
import { ErrorType, showMessage } from '@/services/error/handler';
// 2026-09-26 小欧 - [72]第九章(9.5.3 第1步): 首次设置/查状态走 authApi
import { authApi } from '@/services/api/settings.api';

const LoginPage: React.FC = () => {
  const [token, setToken] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);
  const navigate = useNavigate();

  // [72]第九章(9.5.3 第1步) - 小欧 - 2026-09-26: 进来先问服务端"是否已配置口令"。
  //   未配置时给出明确指引（首次设置走 /auth/token 端点，无需手改配置文件），
  //   避免用户被 401 跳到本页后一头雾水（不知道口令是什么、也不知道在哪设）。
  React.useEffect(() => {
    let alive = true;
    void authApi
      .getTokenStatus()
      .then((st) => {
        if (alive) setNotConfigured(!st.configured);
      })
      .catch(() => {
        /* 查询失败不阻断输入（可能已配置但网络异常） */
      });
    return () => {
      alive = false;
    };
  }, []);

  /** 校验口令：调一个轻量受保护接口验真，避免"存了错的 token 却进了主页" */
  const handleSubmit = async () => {
    const val = token.trim();
    if (!val) {
      showMessage(ErrorType.WARNING, '请输入访问口令');
      return;
    }
    setVerifying(true);
    const prev = getAccessToken();
    setAccessToken(val); // 先写入以带上 Authorization
    try {
      // 2026-09-26 小欧 - 修登录页 401 死循环：此处 401 表示"口令不对"，
      //   是本catch要处理的正常分支，绝不能被响应拦截器升级成 location.href='/login'
      //   （那会重载本页 → 再验一次 → 再 401 → 死循环，且下面的错误提示永远不显示）。
      // 2026-09-26 - 小沈(三遍复核): 走具名常量而非内联字面量 —— 内联对象会触发 axios 的
      //   excess-property 检查报错（_skip401 是本仓扩展字段，不在 axios 自带类型里），
      //   写成 ApiRequestConfig 具名常量则既过编译又保留字段名提示。
      const VERIFY_REQ: ApiRequestConfig = { _skip401: true };
      await api.get('/models', VERIFY_REQ);
      navigate('/', { replace: true });
    } catch {
      // [72]第九章(9.5.3 第1步): 服务端**未配置**口令时，任何口令都无法通过校验
      //   （fail-closed），故在此自动完成"首次设置"——把该口令写入服务端再进入，
      //   免得用户"输入了却进不去、且无处可设"（这正是补设置入口要解决的死锁）。
      if (notConfigured) {
        try {
          await authApi.setToken(val);
          navigate('/', { replace: true });
          return;
        } catch (e) {
          setAccessToken(prev);
          showMessage(
            ErrorType.AUTH_401,
            `设置访问口令失败：${e instanceof Error ? e.message : String(e)}`
          );
          return;
        }
      }
      setAccessToken(prev); // 校验失败则回滚，不留错误口令
      showMessage(ErrorType.AUTH_401, '访问口令无效');
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
      <div style={{ fontSize: 20, fontWeight: 600 }}>请输入访问口令</div>
      <div style={{ fontSize: 13, color: '#8c8c8c' }}>
        本服务部署在局域网内，需口令才能访问
      </div>
      {/* [72]第九章: 未配置口令时给出明确指引（首次设置入口 = 设置页「安全 → 访问口令」，
          或直接调 /auth/token 端点；无需手改配置文件） */}
      {notConfigured && (
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
          位）即可进入并自动保存；之后每次进入都用它。
          <br />
          {/* 2026-09-26 - 小欧 - [72]三堂会审后修正：原文案写「设置 → 安全 → 访问口令」，
              但 api_token 已移到外观组「登录与准入」（security 组只剩 4 项操作安全），
              照原文案去安全组根本找不到。已改为真实路径。 */}
          也可稍后在「设置 → 外观 → 登录与准入 → 访问口令」里修改。
        </div>
      )}
      <Input
        style={{ width: 320 }}
        value={token}
        placeholder="访问口令"
        type="password"
        autoComplete="current-password"
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
    </div>
  );
};

export default LoginPage;
