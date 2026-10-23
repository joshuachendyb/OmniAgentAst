// 编辑历史: 2026-10-21 小杨 - 新建：JSON 内嵌路径链接，覆盖嵌套对象/数组 — 小杨-2026-10-21
// 2026-10-22 小杨 - 数组元素继承父键判定（paths/files 下的元素本身即路径）；
//   标量按 JSON 语义输出（NaN/Infinity 与 JSON 一致为 null）— 小杨-2026-10-22
// 2026-10-23 小欧 - 透传 isDirHint（工具语义声明目录，顶层入口算一次全链路透传，
//   嵌套 path 同样按目录渲染）— 小欧-2026-10-23
/**
 * PathAwareJson —— 保持 JSON 形态，把 path 字段的值渲染成 PathLink。
 *
 * 为什么不用 JSON.stringify：字符串化后无法在中间插入 React 组件；本组件递归渲染，
 *   只替换路径值，键、标量、分隔符仍按 JSON 语法输出。
 */
import React from 'react';
import { isPathParam } from './paramCategories';
import { PathLink } from './PathLink';

export interface PathAwareJsonProps {
  value: unknown;
  projectRoot?: string;
  /** 2026-10-23 小欧 - 工具语义声明该路径必为目录（顶层入口算一次，递归透传） */
  isDirHint?: boolean;
}

const JsonNode: React.FC<PathAwareJsonProps & { keyHint?: string }> = ({
  value,
  projectRoot,
  isDirHint,
  keyHint,
}) => {
  if (typeof value === 'string') {
    if (keyHint !== undefined && isPathParam(keyHint, value)) {
      return (
        <>
          &quot;
          <PathLink
            value={value}
            projectRoot={projectRoot}
            isDirHint={isDirHint}
          />
          &quot;
        </>
      );
    }
    return <>{JSON.stringify(value)}</>;
  }
  if (value === undefined) return <>null</>;
  if (value === null || typeof value !== 'object') {
    // 数字/布尔按 JSON 语义输出（NaN/Infinity 在 JSON 里是 null）
    return <>{JSON.stringify(value) ?? 'null'}</>;
  }
  if (Array.isArray(value)) {
    return (
      <>
        [
        {value.map((item, i) => (
          <React.Fragment key={i}>
            {i > 0 && ', '}
            {/* keyHint 向下传：paths/files 这类键下的数组元素本身也是路径 */}
            <JsonNode
              value={item}
              projectRoot={projectRoot}
              isDirHint={isDirHint}
              keyHint={keyHint}
            />
          </React.Fragment>
        ))}
        ]
      </>
    );
  }
  const entries = Object.entries(value as Record<string, unknown>);
  return (
    <>
      {'{'}
      {entries.map(([k, v], i) => (
        <React.Fragment key={k}>
          {i > 0 && ', '}
          {JSON.stringify(k)}:{' '}
          <JsonNode
            value={v}
            projectRoot={projectRoot}
            isDirHint={isDirHint}
            keyHint={k}
          />
        </React.Fragment>
      ))}
      {'}'}
    </>
  );
};

export const PathAwareJson: React.FC<PathAwareJsonProps> = ({
  value,
  projectRoot,
  isDirHint,
}) => (
  <JsonNode value={value} projectRoot={projectRoot} isDirHint={isDirHint} />
);
