// 编辑历史:
// 2026-08-27 小欧 - 去框-P1-1: 外层容器去框透明(viewOuter), 内层列表/标题保留成功失败语义样式; 主色 #1890ff→#1677ff 收敛
/**
 * SearchFileContentView - grep 工具结果渲染组件
 *
 * 【北京老陈 2026-07-13 小欧】按后端契约重建：
 *   三种模式由 mode 区分（content / count / only_files）。
 *   content: 每个命中展示 file:line + 匹配内容+上下文
 *   count / only_files: 仅展示汇总与文件列表
 *   不读不存在的 success/ pattern/ path/ pagination 等字段。
 *
 * @author 小强
 * @version 3.0.0
 * @since 2026-03-31
 * @update 2026-07-13 小欧-按后端契约重建
 */

import React from "react";
import { viewOuter } from './viewTokens';
import { CheckCircleOutlined, CloseCircleOutlined, FileTextOutlined } from "@ant-design/icons";

interface ContentMatch {
  file?: string;
  line?: number;
  matched?: string[];
  content?: string;
  before?: string;
  after?: string;
}

interface OnlyFileMatch {
  file?: string;
  lines?: number[];
}

interface SearchFileContentViewProps {
  data: {
    mode: "content" | "count" | "only_files";
    matches: (ContentMatch | OnlyFileMatch)[];
    total_matches: number;
    total_files: number;
    skipped_binary_files?: string[];
    skipped_binary_count?: number;
  };
  summary?: string;
  success: boolean;
}

const containerStyle = (_success: boolean): React.CSSProperties => ({ ...viewOuter });

const titleStyle = (success: boolean): React.CSSProperties => ({
  display: "flex",
  alignItems: "center",
  marginBottom: 12,
  fontSize: 14,
  fontWeight: 500,
  color: success ? "#52c41a" : "#ff4d4f",
});

const SearchFileContentView: React.FC<SearchFileContentViewProps> = ({ data, summary, success }) => {
  const { mode, matches, total_matches, total_files, skipped_binary_count } = data;

  return (
    <div style={containerStyle(success)}>
      {/* 标题 */}
      <div style={titleStyle(success)}>
        {success ? <CheckCircleOutlined style={{ marginRight: 8 }} /> : <CloseCircleOutlined style={{ marginRight: 8 }} />}
        搜索文件内容{success ? "成功" : "失败"}
      </div>

      {/* 命中汇总 */}
      <div style={{ fontSize: 12, color: "#595959", marginBottom: matches.length > 0 ? 8 : 0 }}>
        共 {total_files} 个文件 · {total_matches} 处匹配
        {skipped_binary_count !== undefined && skipped_binary_count > 0 && (
          <span style={{ color: "#faad14", marginLeft: 8 }}>（跳过 {skipped_binary_count} 个二进制文件）</span>
        )}
      </div>

      {/* content 模式：逐命中展示 */}
      {mode === "content" && matches.length > 0 && (
        <div style={{ background: "#fafafa", borderRadius: 6, padding: "6px 10px", maxHeight: 400, overflow: "auto" }}>
          {matches.map((m, idx) => {
            const cm = m as ContentMatch;
            const file = cm.file || "";
            return (
              <div
                key={`c-${idx}`}
                style={{
                  padding: "6px 0",
                  borderBottom: idx < matches.length - 1 ? "1px solid #f0f0f0" : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <FileTextOutlined style={{ color: "#1677ff" }} />
                  <span style={{ flex: 1, fontFamily: "Consolas, Monaco, monospace", fontSize: 12, color: "#003a8c", wordBreak: "break-all" }}>
                    {file}
                    {cm.line !== undefined && <span style={{ color: "#8c8c8c" }}> : {cm.line}</span>}
                  </span>
                </div>
                {cm.matched && cm.matched.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    {cm.matched.map((mk, mi) => (
                      <span
                        key={mi}
                        style={{ background: "#fff7e6", padding: "1px 4px", borderRadius: 2, color: "#ad4e00", fontFamily: "Consolas, Monaco, monospace", fontSize: 12, marginRight: 4 }}
                      >
                        {mk}
                      </span>
                    ))}
                  </div>
                )}
                {cm.content && (
                  <div
                    style={{
                      marginTop: 4,
                      background: "#1e1e1e",
                      padding: "4px 8px",
                      borderRadius: 3,
                      color: "#d4d4d4",
                      fontFamily: "Consolas, Monaco, monospace",
                      fontSize: 11,
                      whiteSpace: "pre-wrap",
                      lineHeight: 1.4,
                    }}
                  >
                    {cm.before ? `${cm.before}\n` : ""}
                    {cm.content}
                    {cm.after ? `\n${cm.after}` : ""}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* only_files 模式：文件 + 命中行号列表 */}
      {mode === "only_files" && matches.length > 0 && (
        <div style={{ background: "#fafafa", borderRadius: 6, padding: "6px 10px", maxHeight: 400, overflow: "auto" }}>
          {matches.map((m, idx) => {
            const fm = m as OnlyFileMatch;
            return (
              <div
                key={`f-${idx}`}
                style={{
                  padding: "5px 0",
                  borderBottom: idx < matches.length - 1 ? "1px solid #f0f0f0" : "none",
                  fontSize: 13,
                }}
              >
                <FileTextOutlined style={{ color: "#1677ff", marginRight: 6 }} />
                <span style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 12, color: "#003a8c", wordBreak: "break-all" }}>
                  {fm.file}
                </span>
                {fm.lines && fm.lines.length > 0 && (
                  <span style={{ color: "#8c8c8c", fontSize: 12, marginLeft: 8 }}>
                    行号：{fm.lines.join(", ")}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* count 模式：无命中明细，仅汇总已展示 */}

      {/* 后端摘要 */}
      {summary && (
        <div style={{ color: "#595959", whiteSpace: "pre-wrap", marginTop: matches.length > 0 ? 8 : 4 }}>{summary}</div>
      )}
    </div>
  );
};

export default React.memo(SearchFileContentView);
