/**
 * JsonHighlight - JSON语法高亮组件
 * 
 * 功能：为工具参数提供语法高亮显示，不同类型值使用不同颜色
 * 
 * @author 老杨-2026-03-25
 * @version 1.0.0
 * @since 2026-03-25
 */

import React from "react";

interface JsonHighlightProps {
  data: any;
  isExpanded: boolean;
}

/**
 * JSON语法高亮组件
 * 
 * 颜色方案：
 * - null: 灰色(#8c8c8c)
 * - boolean: 橙色(#cf7301)
 * - number: 绿色(#389e0d)
 * - string: 蓝色(#0050b3)
 * - object key: 深蓝(#003a8c)
 * 
 * 展开/折叠：
 * - 折叠状态：数组显示[...]，对象显示{...}
 * - 展开状态：显示完整JSON，带缩进
 */
const JsonHighlight: React.FC<JsonHighlightProps> = ({ data, isExpanded }) => {
  // 递归渲染带颜色的JSON
  const renderValue = (value: any, depth: number = 0): React.ReactNode => {
    if (value === null) {
      return <span style={{ color: "#8c8c8c" }}>null</span>;
    }
    if (value === undefined) {
      return <span style={{ color: "#8c8c8c" }}>undefined</span>;
    }
    if (typeof value === "boolean") {
      return <span style={{ color: "#cf7301" }}>{String(value)}</span>;
    }
    if (typeof value === "number") {
      return <span style={{ color: "#389e0d" }}>{value}</span>;
    }
    if (typeof value === "string") {
      return <span style={{ color: "#0050b3" }}>&quot;{value}&quot;</span>;
    }
    if (Array.isArray(value)) {
      if (!isExpanded) {
        return <span style={{ color: "#595959" }}>[...]</span>;
      }
      return (
        <span>
          <span style={{ color: "#595959" }}>[</span>
          {value.map((item, i) => (
            <span key={i}>
              {i > 0 && <span style={{ color: "#595959" }}>, </span>}
              <span style={{ marginLeft: depth > 0 ? 0 : 0 }}>{renderValue(item, depth + 1)}</span>
            </span>
          ))}
          <span style={{ color: "#595959" }}>]</span>
        </span>
      );
    }
    if (typeof value === "object") {
      if (!isExpanded) {
        return <span style={{ color: "#595959" }}>{"{...}"}</span>;
      }
      const keys = Object.keys(value);
      return (
        <span>
          <span style={{ color: "#595959" }}>{"{"}</span>
          {keys.map((key, i) => (
            <span key={key}>
              {i > 0 && <span style={{ color: "#595959" }}>, </span>}
              <span style={{ color: "#003a8c" }}>&quot;{key}&quot;</span>
              <span style={{ color: "#595959" }}>: </span>
              {renderValue(value[key], depth + 1)}
            </span>
          ))}
          <span style={{ color: "#595959" }}>{"}"}</span>
        </span>
      );
    }
    return <span>{String(value)}</span>;
  };

  return (
    <span style={{ fontFamily: "Consolas, Monaco, 'Courier New', monospace" }}>
      参数：{renderValue(data)}
    </span>
  );
};

export default JsonHighlight;
