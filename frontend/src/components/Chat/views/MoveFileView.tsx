// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
/**
 * MoveFileView - move 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   data 为空，直接展示 llm_data.summary（如「移动成功: A -> B」）。
 *   不读不存在的 source/ destination/ message 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { viewOuter } from './viewTokens';
import { CheckCircleOutlined, CloseCircleOutlined, SendOutlined } from "@ant-design/icons";

interface MoveFileViewProps {
  summary?: string;
  success: boolean;
}

const moveContainerStyle = (_success: boolean): React.CSSProperties => ({ ...viewOuter, fontSize: 13, lineHeight: 1.8 });

const moveTitleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 8,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const MoveFileView: React.FC<MoveFileViewProps> = ({ summary, success }) => {
  return (
    <div style={moveContainerStyle(success)}>
      <div style={moveTitleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <SendOutlined style={{ marginRight: 6 }} />
        移动文件{success ? "成功" : "失败"}
      </div>

      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap" }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(MoveFileView);
