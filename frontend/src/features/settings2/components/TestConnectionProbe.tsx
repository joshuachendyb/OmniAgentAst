/**
 * TestConnectionProbe — key 连通性探测按钮 + 分档结果文案（设计文档 10.3）
 *
 * 编辑历史:
 *   2026-09-26 - 小欧 - 新建。从 ProviderConfig.tsx 原样迁出（拆分只改归属，
 *     不改业务逻辑——符合项目"能复制就复制、不重写"纪律）。
 *     迁出原因（SRP）：ProviderConfig 同时承担"配置表单 / 明文查看 / 连通性探测"三件事，
 *     组件膨胀到 500 行。故把本职责独立成组件。
 *
 * 本组件只做一件事：探测 Provider 的 key + 地址组合是否可用。两条要点：
 *   ①按后端返回的 category 给**不同**文案（设计 10.5 明写"不得统一显示失败"）——
 *      endpoint_unsupported(404/405/501) 不得说 key 无效（部分 provider 就没有 /models 端点）；
 *      network_error 不得说 key 有问题（那是地址写错或网络不通）。
 *   ②传输入框里**未保存**的 key 实现"保存前验证"（后端仅用于本次请求 header，不落盘不进日志）。
 *
 *   2026-09-26 (三堂会审后修正) - 小欧 - 首版误用原生 <button>，与全项目 AntD Button 体系不一致
 *     （按钮高度/圆角/hover/loading 全不同，且 loading 态需自己手写）。已改回 AntD Button，
 *     样式一律走既有令牌（Spacing / Colors / FontSize），不新造样式。
 */
import React, { useState } from 'react';
import { Button } from 'antd';
import { modelApi } from '@/services/api/model.api';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

/**
 * 分类 → 文案映射。放模块级而非函数体内：原写法每次点击重建同内容对象，
 * 且文案埋在业务逻辑里不便与后端 category 一一对账（DRY）。
 */
const CATEGORY_TEXT: Record<string, string> = {
  ok: '连接成功，key 有效',
  key_invalid: 'key 无效或无权限（HTTP 401/403），请检查该 key 是否正确、是否已过期',
  endpoint_unsupported:
    '该 Provider 不支持模型列表检测（无 /models 端点），key 未验证 —— 不代表 key 无效',
  network_error:
    '无法连接，请检查 base_url 是否填写正确、网络是否可达（与 key 无关）',
};

/** 未知 category 的兜底文案（后端新增分类 / 分类拼错时不会显示 undefined）。 */
const FALLBACK_TEXT = CATEGORY_TEXT.network_error;

export interface TestConnectionProbeProps {
  /** provider 名 */
  providerName: string;
  /** 输入框里的 key（可为空 —— 为空则后端回落到已保存值 / env） */
  probeKey: string;
  /** base_url 是否已填（空则按钮禁用：地址不通测了无意义） */
  baseUrlReady: boolean;
  /** 按钮左间距（由调用方传既有令牌值，避免本组件硬编码间距） */
  marginLeft: number | string;
}

export const TestConnectionProbe: React.FC<TestConnectionProbeProps> = ({
  providerName,
  probeKey,
  baseUrlReady,
  marginLeft,
}) => {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(
    null
  );

  const run = async () => {
    setTesting(true);
    setResult(null);
    try {
      const r = await modelApi.testConnection(providerName, probeKey);
      setResult({
        ok: r.ok,
        text: r.ok
          ? CATEGORY_TEXT.ok
          : `${CATEGORY_TEXT[r.category ?? ''] ?? FALLBACK_TEXT}${
              r.message ? `（后端信息：${r.message}）` : ''
            }`,
      });
    } catch (e) {
      setResult({
        ok: false,
        text: `测试请求未能完成：${
          e instanceof Error ? e.message : String(e)
        }（属请求层问题，与 key 有效性无关）`,
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <>
      <Button
        onClick={() => void run()}
        loading={testing}
        disabled={!baseUrlReady}
        style={{ marginLeft }}
      >
        测试连接
      </Button>
      {result && (
        <div
          style={{
            marginLeft: Spacing.LG,
            fontSize: FontSize.SECONDARY,
            color: result.ok ? Colors.SUCCESS : Colors.ERROR,
            paddingTop: Spacing.XS,
          }}
        >
          {result.ok ? '✅' : '❌'} {result.text}
        </div>
      )}
    </>
  );
};
