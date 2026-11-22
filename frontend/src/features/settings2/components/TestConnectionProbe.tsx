/**
 * TestConnectionProbe — key 连通性探测按钮 + 分档结果提示（设计文档 10.3）
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
 *
 *   2026-11-22 - 商量 - 结果提示 UI 重构（用户令「高级设计师水平，失败/正常提示要在一行显示、
 *     不折行、不撑爆」）：
 *     ①提示改为「语义图标 + 短标题」与探测按钮**同一行**（父 flex 行内），`whiteSpace: nowrap`
 *       不折行；短标题（如「连接成功」「key 无效」）一行放得下，不再横向撑爆按钮行。
 *     ②完整详情（含后端 message）放 AntD Tooltip 悬停显示——主信息一行可见，次信息不占行。
 *     ③语义色分档：成功=绿(PILL_SUCCESS) / key无效=红(ERROR_TEXT) / 网络=橙(ORANGE_RED) /
 *       不支持=蓝(INFO)，各自达 AA 对比度；图标用 AntD 语义图标（Check/Close/Exclamation/Info）。
 *     ④分类→(tone,title,detail) 结构化映射放模块级，与后端 category 一一对账（DRY）。
 */
import React, { useState } from 'react';
import { Button, Tooltip } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons';
import { modelApi } from '@/services/api/model.api';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';

/** 语义档位：成功/错误/警告(网络)/信息(不支持) 四档，各自独立色与图标。 */
type ProbeTone = 'success' | 'error' | 'warning' | 'info';

/** 分类 → 语义档 + 短标题 + 详情。放模块级而非函数体内：原写法每次点击重建同内容对象，
 *  且文案埋在业务逻辑里不便与后端 category 一一对账（DRY）。 */
const CATEGORY_META: Record<
  string,
  { tone: ProbeTone; title: string; detail: string }
> = {
  ok: { tone: 'success', title: '连接成功', detail: 'key 有效，可正常使用' },
  key_invalid: {
    tone: 'error',
    title: 'key 无效',
    detail: '请检查 key 是否正确或已过期（401/403）',
  },
  endpoint_unsupported: {
    tone: 'info',
    title: '不支持检测',
    detail: '该 Provider 无 /models 端点，key 未验证',
  },
  network_error: {
    tone: 'warning',
    title: '无法连接',
    detail: '请检查 api_base 地址或网络（与 key 无关）',
  },
};

/** 未知 category 的兜底（后端新增分类 / 分类拼错不会显示 undefined）。 */
const FALLBACK_META = CATEGORY_META.network_error;

const TONE_COLOR: Record<ProbeTone, string> = {
  success: Colors.PILL_SUCCESS,
  error: Colors.ERROR_TEXT,
  warning: Colors.ORANGE_RED,
  info: Colors.INFO,
};

const TONE_ICON: Record<ProbeTone, React.ReactNode> = {
  success: <CheckCircleOutlined />,
  error: <CloseCircleOutlined />,
  warning: <ExclamationCircleOutlined />,
  info: <InfoCircleOutlined />,
};

export interface TestConnectionProbeProps {
  /** provider 名 */
  providerName: string;
  /** 输入框里的 key（可为空 —— 为空则后端回落到已保存值 / env） */
  probeKey: string;
  /** api_base 是否已填（空则按钮禁用：地址不通测了无意义） */
  baseUrlReady: boolean;
  /** 按钮左间距（由调用方传既有令牌值；flex gap 容器内传 0 或省略） */
  marginLeft?: number | string;
}

export const TestConnectionProbe: React.FC<TestConnectionProbeProps> = ({
  providerName,
  probeKey,
  baseUrlReady,
  marginLeft = 0,
}) => {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<{
    tone: ProbeTone;
    title: string;
    tooltip: string;
  } | null>(null);

  const run = async () => {
    setTesting(true);
    setResult(null);
    try {
      const r = await modelApi.testConnection(providerName, probeKey);
      const meta = r.ok
        ? CATEGORY_META.ok
        : (CATEGORY_META[r.category ?? ''] ?? FALLBACK_META);
      setResult({
        tone: meta.tone,
        title: meta.title,
        tooltip: r.ok
          ? meta.detail
          : `${meta.detail}${r.message ? `（后端：${r.message}）` : ''}`,
      });
    } catch (e) {
      setResult({
        tone: 'error',
        title: '测试请求未完成',
        tooltip: `${
          e instanceof Error ? e.message : String(e)
        }（请求层问题，与 key 无关）`,
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
        配置联通测试
      </Button>
      {result && (
        <Tooltip title={result.tooltip} placement="topLeft">
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: Spacing.XS,
              whiteSpace: 'nowrap',
              fontSize: FontSize.SECONDARY,
              color: TONE_COLOR[result.tone],
            }}
          >
            {TONE_ICON[result.tone]}
            <span>{result.title}</span>
          </span>
        </Tooltip>
      )}
    </>
  );
};
