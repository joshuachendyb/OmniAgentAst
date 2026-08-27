// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
/**
 * FileOperationView - readmedia/extract/edittext/rename 通用结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   按 tool_name 分支渲染真实字段：
 *     - readmedia: file_name + <img src=data:mime;base64,...>
 *     - extract:   output_dir + 解压/跳过文件数 + 文件列表(前若干)
 *     - edittext/rename: 成功徽标 + llm_data.summary（如「替换成功: N/M 处」）+ diff
 *   不读不存在的 message/ success 字段。
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-05-10
 */

import React from "react";
import { viewOuter } from './viewTokens';
import { CheckCircleOutlined, CloseCircleOutlined, FileImageOutlined, FileZipOutlined, DiffOutlined } from "@ant-design/icons";

interface FileOperationViewProps {
  tool_name: string;
  data: Record<string, unknown>;
  summary?: string;
  success: boolean;
}

const containerStyle = (_success: boolean): React.CSSProperties => ({ ...viewOuter, fontSize: 13, lineHeight: 1.8 });

const titleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 8,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const infoItemStyle: React.CSSProperties = { display: "flex", alignItems: "center", marginBottom: 8, fontSize: 13, color: "#595959" };
const labelStyle: React.CSSProperties = { minWidth: 84, color: "#8c8c8c", marginRight: 8 };

const FileOperationView: React.FC<FileOperationViewProps> = ({ tool_name, data, summary, success }) => {
  // ===== readmedia：图片展示 =====
  if (tool_name === "readmedia") {
    const file_name = (data.file_name as string) || "";
    const mime_type = (data.mime_type as string) || "image/png";
    const base64_data = (data.base64_data as string) || "";
    return (
      <div style={containerStyle(success)}>
        <div style={titleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          <FileImageOutlined style={{ marginRight: 6 }} />
          读取媒体文件{success ? "成功" : "失败"}
        </div>
        {file_name && (
          <div style={{ ...infoItemStyle, marginBottom: 8 }}>
            <span style={labelStyle}>文件名：</span>
            <span>{file_name}</span>
          </div>
        )}
        {base64_data && (
          <img
            src={`data:${mime_type};base64,${base64_data}`}
            alt={file_name}
            style={{ maxWidth: "100%", maxHeight: 360, borderRadius: 6, border: "1px solid #d9d9d9", marginTop: 4 }}
          />
        )}
        {summary && <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>}
      </div>
    );
  }

  // ===== extract：解压展示 =====
  if (tool_name === "extract") {
    const output_dir = (data.output_dir as string) || "";
    const extracted_files = (data.extracted_files as number) ?? 0;
    const skipped_files = (data.skipped_files as number) ?? 0;
    const format = (data.format as string) || "";
    const file_list = (data.file_list as string[]) || [];
    return (
      <div style={containerStyle(success)}>
        <div style={titleStyle(success)}>
          {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
          <FileZipOutlined style={{ marginRight: 6 }} />
          解压文件{success ? "成功" : "失败"}
        </div>
        {output_dir && (
          <div style={infoItemStyle}>
            <span style={labelStyle}>输出目录：</span>
            <code style={{ background: "#f5f5f5", padding: "2px 6px", borderRadius: 4, fontFamily: "Consolas, Monaco, monospace", fontSize: 12 }}>{output_dir}</code>
          </div>
        )}
        <div style={infoItemStyle}>
          <span style={labelStyle}>解压文件：</span>
          <span>{extracted_files} 个{skipped_files > 0 ? `（跳过 ${skipped_files} 个）` : ""}</span>
          {format && <span style={{ marginLeft: 12, color: "#8c8c8c" }}>格式：{format}</span>}
        </div>
        {file_list.length > 0 && (
          <div style={{ background: "#fafafa", borderRadius: 6, padding: "6px 10px", maxHeight: 200, overflow: "auto" }}>
            {file_list.slice(0, 30).map((f, idx) => (
              <div key={idx} style={{ fontSize: 12, fontFamily: "Consolas, Monaco, monospace", color: "#595959", padding: "2px 0" }}>{f}</div>
            ))}
            {file_list.length > 30 && <div style={{ color: "#8c8c8c", fontSize: 12 }}>...还有 {file_list.length - 30} 个</div>}
          </div>
        )}
        {summary && <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: 4 }}>{summary}</div>}
      </div>
    );
  }

  // ===== edittext / rename：徽标 + 摘要 + diff =====
  const diff = (data.diff as string) || "";
  return (
    <div style={containerStyle(success)}>
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        <DiffOutlined style={{ marginRight: 6 }} />
        {tool_name === "rename" ? "重命名" : "文本编辑"}{success ? "成功" : "失败"}
      </div>
      {summary && <div style={{ color: "#595959", whiteSpace: "pre-wrap" }}>{summary}</div>}
      {diff && (
        <pre
          style={{
            background: "#1e1e1e",
            color: "#d4d4d4",
            padding: "8px 12px",
            borderRadius: 6,
            fontSize: 12,
            fontFamily: "Consolas, Monaco, monospace",
            whiteSpace: "pre-wrap",
            wordBreak: "break-all",
            maxHeight: 300,
            overflow: "auto",
            marginTop: 8,
          }}
        >
          {diff}
        </pre>
      )}
    </div>
  );
};

export default React.memo(FileOperationView);
