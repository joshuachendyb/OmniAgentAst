/**
 * SearchFileContentView - grep_file_content 工具结果渲染组件
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-31
 * @update 2026-05-10 小健-重写：修复图标嵌套bug，精简UI
 */

import React from "react";
import { Tag, Collapse, Button } from "antd";
import {
  FileTextOutlined,
  SearchOutlined,
  FolderOpenOutlined,
} from "@ant-design/icons";

const { Panel } = Collapse;

interface ContentMatch {
  start: number;
  end: number;
  matched: string;
  context: string;
}

interface FileContentMatch {
  file: string;
  matches: ContentMatch[];
  match_count: number;
}

interface Pagination {
  page: number;
  total_pages: number;
  has_more: boolean;
}

interface SearchFileContentViewProps {
  data: {
    success?: boolean;
    pattern: string;
    path: string;
    file_pattern: string;
    matches: FileContentMatch[];
    total: number;
    total_matches: number;
    pagination?: Pagination;
  };
  onLoadMore?: () => void;
  isLoadingMore?: boolean;
}

const SearchFileContentView: React.FC<SearchFileContentViewProps> = ({
  data,
  onLoadMore,
  isLoadingMore,
}) => {
  const {
    success,
    pattern = "",
    path = "",
    file_pattern = "",
    matches = [],
    total = 0,
    total_matches = 0,
    pagination,
  } = data;

  if (!success || (matches.length === 0 && total === 0)) {
    return <div style={{ color: "#999", padding: "8px 12px" }}>未找到匹配结果</div>;
  }

  return (
    <div style={{ fontSize: 13 }}>
      {/* 搜索统计 */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, alignItems: "center", marginBottom: 8 }}>
        <SearchOutlined style={{ color: "#1890ff" }} />
        <span style={{ fontWeight: 500, color: "#1890ff" }}>{pattern}</span>
        <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>
          <FolderOpenOutlined style={{ marginRight: 4 }} />{path}
        </Tag>
        {file_pattern && file_pattern !== "*" && (
          <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>{file_pattern}</Tag>
        )}
        <span style={{ color: "#595959" }}>{total}个文件 · {total_matches}处匹配</span>
      </div>

      {/* 文件匹配列表 */}
      {matches.length > 0 && (
        <div style={{ background: "#fafafa", borderRadius: 4, padding: "4px 8px", maxHeight: 400, overflow: "auto" }}>
          <Collapse ghost defaultActiveKey={[]} expandIconPosition="end">
            {matches.map((fm, fi) => (
              <Panel
                key={`f${fi}`}
                header={
                  <div style={{ display: "flex", alignItems: "center", gap: 6, width: "100%" }}>
                    <FileTextOutlined style={{ color: "#1890ff" }} />
                    <span style={{ flex: 1, fontFamily: "Consolas, Monaco, monospace", fontSize: 12, color: "#003a8c", wordBreak: "break-all" }}>
                      {fm.file}
                    </span>
                    <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>{fm.match_count}处</Tag>
                  </div>
                }
              >
                <div style={{ paddingLeft: 8 }}>
                  {fm.matches?.map((m, mi) => (
                    <div key={`m${mi}`} style={{ padding: "4px 0", borderBottom: mi < fm.matches.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                      <div style={{ fontSize: 11, color: "#8c8c8c", marginBottom: 2 }}>#{mi + 1} 位置 {m.start}-{m.end}</div>
                      {m.matched && (
                        <div style={{ fontFamily: "Consolas, Monaco, monospace", fontSize: 12, marginBottom: 2 }}>
                          <span style={{ background: "#fff7e6", padding: "1px 4px", borderRadius: 2, color: "#ad4e00" }}>{m.matched}</span>
                        </div>
                      )}
                      {m.context && (
                        <div style={{ background: "#1e1e1e", padding: "4px 8px", borderRadius: 3, color: "#d4d4d4", fontFamily: "Consolas, Monaco, monospace", fontSize: 11, whiteSpace: "pre-wrap", lineHeight: 1.4 }}>
                          {m.context}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Panel>
            ))}
          </Collapse>

          {pagination?.has_more && onLoadMore && (
            <div style={{ textAlign: "center", padding: "8px 0" }}>
              <Button type="link" size="small" loading={isLoadingMore} onClick={onLoadMore}>
                {isLoadingMore ? "加载中..." : "加载更多"}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchFileContentView;
