/**
 * SearchFileContentView - search_file_content 工具结果渲染组件
 *
 * 显示文件内容搜索结果，包含匹配详情
 * 【小强实现 2026-03-31】根据设计文档第3章新建：
 *  - 处理嵌套数据结构
 *  - 蓝色系视觉风格（与action_tool一致）
 *  - 分页功能
 *  - 可折叠的文件匹配列表
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-31
 */

import React from "react";
import { List, Tag, Button, Collapse, Empty } from "antd";
import { 
  FileTextOutlined, 
  SearchOutlined
} from "@ant-design/icons";

const { Panel } = Collapse;

// 内容匹配详情接口
interface ContentMatch {
  start: number;
  end: number;
  matched: string;
  context: string;
}

// 单个文件的匹配结果接口
interface FileContentMatch {
  file: string;
  matches: ContentMatch[];
  match_count: number;
}

// 分页接口
interface Pagination {
  page: number;
  total_pages: number;
  page_size: number;
  has_more: boolean;
  last_file?: string;
}

// SearchFileContentView Props接口
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
  // 分页回调（可选）
  onLoadMore?: () => void;
  isLoadingMore?: boolean;
}

/**
 * SearchFileContentView 主组件
 */
const SearchFileContentView: React.FC<SearchFileContentViewProps> = ({ 
  data, 
  onLoadMore, 
  isLoadingMore 
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

  // 判断是否显示加载更多按钮
  const canLoadMore = pagination?.has_more && onLoadMore;

  // 空数据检查
  if (!success || (matches.length === 0 && total === 0)) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        🔍 未找到匹配结果
      </div>
    );
  }

  // 渲染单个文件匹配项
  const renderFileMatch = (fileMatch: FileContentMatch, fileIndex: number) => {
    return (
      <Panel
        key={`file-${fileIndex}`}
        header={
          <div style={{ display: "flex", alignItems: "center", width: "100%" }}>
            <FileTextOutlined style={{ color: "#1890ff", marginRight: 8 }} />
            <span 
              style={{ 
                flex: 1, 
                fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                fontSize: 12,
                color: "#003a8c",
                wordBreak: "break-all",
              }}
            >
              {fileMatch.file}
            </span>
            <Tag 
              style={{ 
                marginLeft: 8, 
                background: "#e6f7ff", 
                border: "none", 
                color: "#003a8c" 
              }}
            >
              {fileMatch.match_count} 处匹配
            </Tag>
          </div>
        }
      >
        {/* 匹配详情列表 */}
        <div style={{ paddingLeft: 8 }}>
          {fileMatch.matches && fileMatch.matches.length > 0 ? (
            <List
              size="small"
              dataSource={fileMatch.matches}
              renderItem={(match: ContentMatch, matchIndex: number) => (
                <List.Item
                  key={`match-${fileIndex}-${matchIndex}`}
                  style={{
                    padding: "6px 8px",
                    borderBottom: matchIndex < fileMatch.matches.length - 1 
                      ? "1px solid #91d5ff" 
                      : "none",
                    background: matchIndex % 2 === 0 ? "rgba(230,247,255,0.3)" : "transparent",
                  }}
                >
                  <div style={{ width: "100%" }}>
                    {/* 匹配序号 */}
                    <div style={{ 
                      fontSize: 11, 
                      color: "#666", 
                      marginBottom: 4 
                    }}>
                      #{matchIndex + 1} 位置：{match.start}-{match.end}
                    </div>
                    
                    {/* 匹配的关键词（高亮） */}
                    {match.matched && (
                      <div style={{ 
                        marginBottom: 4,
                        fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                        fontSize: 12,
                        color: "#003a8c",
                      }}>
                        <SearchOutlined style={{ marginRight: 4 }} />
                        <span style={{ 
                          background: "#fff7e6", 
                          padding: "1px 4px",
                          borderRadius: 2,
                          color: "#ad4e00",
                        }}>
                          {match.matched}
                        </span>
                      </div>
                    )}
                    
                    {/* 上下文内容 */}
                    {match.context && (
                      <div
                        style={{
                          background: "#1e1e1e",
                          padding: "6px 10px",
                          borderRadius: 4,
                          color: "#d4d4d4",
                          fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                          fontSize: 11,
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-all",
                          lineHeight: 1.5,
                        }}
                      >
                        {match.context}
                      </div>
                    )}
                  </div>
                </List.Item>
              )}
            />
          ) : (
            <Empty description="无匹配详情" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          )}
        </div>
      </Panel>
    );
  };

  // 蓝色系搜索结果背景样式（与SearchFilesView一致）
  const searchResultStyle = {
    background: "linear-gradient(135deg, #e6f7ff 0%, #f0f5ff 100%)",
    border: "1px solid #69c0ff",
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: "0.9em",
    maxHeight: 400,
    overflow: "auto",
  };

  return (
    <div>
      {/* 搜索统计信息 - 统一蓝色系（符合设计文档3.3.2） */}
      <div
        style={{
          marginBottom: 8,
          fontSize: 12,
          display: "flex",
          flexWrap: "wrap",
          gap: 8,
          alignItems: "center",
        }}
      >
        {/* 搜索关键词 */}
        <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>
          🔍 关键词：{pattern}
        </Tag>
        
        {/* 搜索路径 */}
        <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>
          📂 {path}
        </Tag>
        
        {/* 文件模式 */}
        <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>
          📁 {file_pattern || "*"}
        </Tag>
        
        {/* 匹配文件数 */}
        <span
          style={{
            background: "#e6f7ff",
            padding: "2px 8px",
            borderRadius: 4,
            color: "#003a8c",
            fontWeight: 500,
          }}
        >
          📄 {total} 个文件
        </span>
        
        {/* 内容匹配数 */}
        <span
          style={{
            background: "#e6f7ff",
            padding: "2px 8px",
            borderRadius: 4,
            color: "#003a8c",
            fontWeight: 500,
          }}
        >
          🔎 {total_matches} 处匹配
        </span>
        
        {/* 分页信息 */}
        {pagination && (
          <span
            style={{
              background: "#e6f7ff",
              padding: "2px 8px",
              borderRadius: 4,
              color: "#003a8c",
              fontWeight: 500,
            }}
          >
            📋 第 {pagination.page}/{pagination.total_pages} 页
          </span>
        )}
      </div>

      {/* 文件匹配列表 */}
      {matches.length > 0 && (
        <div style={searchResultStyle}>
          <Collapse 
            ghost 
            defaultActiveKey={[]}
            expandIconPosition="end"
          >
            {matches.map((fileMatch, index) => 
              renderFileMatch(fileMatch, index)
            )}
          </Collapse>
          
          {/* 加载更多按钮 */}
          {canLoadMore && (
            <div style={{ textAlign: "center", marginTop: 16 }}>
              <Button 
                type="primary" 
                size="small"
                loading={isLoadingMore}
                onClick={onLoadMore}
                style={{ 
                  background: "#1890ff",
                  borderColor: "#1890ff",
                }}
              >
                {isLoadingMore ? "加载中..." : "加载更多"}
              </Button>
            </div>
          )}
          
          {/* 显示提示 */}
          {matches.length > 0 && (
            <div style={{ 
              textAlign: "center", 
              padding: "8px", 
              color: "#666",
              fontSize: 11,
              background: "rgba(230,247,255,0.5)",
              borderRadius: 4,
              marginTop: 8,
            }}>
              共 {matches.length} 个文件显示
              {pagination?.has_more && "（更多结果请加载）"}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SearchFileContentView;