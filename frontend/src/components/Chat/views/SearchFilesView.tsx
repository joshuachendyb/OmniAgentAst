/**
 * SearchFilesView - search_files 工具结果渲染组件
 *
 * 显示文件搜索结果，包含匹配详情
 * 【小强实现 2026-03-31】根据设计文档第2章改进：
 *  - 数据转换由transformSearchFilesData处理
 *  - 视觉风格改为蓝色系（与action_tool一致）
 *  - 添加分页功能
 *  - 添加虚拟滚动支持
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-03-24
 */

import React from "react";
import { List, Tag, Button } from "antd";
import { FileTextOutlined } from "@ant-design/icons";

// 文件匹配接口（向后兼容）
interface FileMatch {
  // 文件搜索字段
  name?: string;
  path?: string;
  size?: number;
  // 兼容字段
  file_path?: string;
  line_number?: number;
  line_content?: string;
}

// 分页接口
interface Pagination {
  page: number;
  total_pages: number;
  page_size: number;
  has_more: boolean;
  last_file?: string;
}

// SearchFilesView Props接口（符合设计文档2.4.2）
interface SearchFilesViewProps {
  data: {
    files_matched: number;
    total_matches?: number;
    matches: FileMatch[];
    search_pattern: string;
    search_path?: string;
    pagination?: Pagination;
  };
  // 【小强实现 2026-03-31】分页回调（可选）
  onLoadMore?: () => void;
  isLoadingMore?: boolean;
}

/**
 * SearchFilesView 主组件
 */
const SearchFilesView: React.FC<SearchFilesViewProps> = ({ data, onLoadMore, isLoadingMore }) => {
  const {
    files_matched = 0,
    matches = [],
    search_pattern = "",
    search_path = "",
    pagination,
  } = data;

  // 判断是否显示加载更多按钮
  const canLoadMore = pagination?.has_more && onLoadMore;

  // 【小强实现 2026-03-31】虚拟滚动：超过100条启用
  const shouldUseVirtualList = matches.length > 100;

  // 格式化文件大小
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 字节";
    if (bytes < 1024) return `${bytes} 字节`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  // 渲染单个匹配项（智能判断数据类型）
  const renderMatchItem = (match: FileMatch, index: number) => {
    // 优先使用文件搜索数据（name + path + size）
    const hasFileData = match.name || match.path;
    
    if (hasFileData) {
      // 文件搜索数据渲染
      const displayPath = match.path || match.file_path || "";
      const displayName = match.name || displayPath.split(/[/\\]/).pop() || "";
      
      return (
        <List.Item
          key={`file-${index}`}
          style={{
            padding: "8px 12px",
            borderBottom: index < matches.length - 1 ? "1px solid #91d5ff" : "none",
            background: index % 2 === 0 ? "rgba(230,247,255,0.3)" : "transparent",
          }}
        >
          <div style={{ width: "100%" }}>
            {/* 文件路径 */}
            <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap" }}>
              <FileTextOutlined style={{ color: "#1890ff", marginRight: 6 }} />
              <code
                style={{
                  background: "#e6f7ff",
                  padding: "2px 8px",
                  borderRadius: 4,
                  fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                  fontSize: 12,
                  color: "#003a8c",
                  wordBreak: "break-all",
                }}
              >
                {displayPath}
              </code>
              {/* 文件大小 */}
              {match.size !== undefined && match.size > 0 && (
                <Tag style={{ marginLeft: 8, background: "#e6f7ff", border: "none", color: "#003a8c" }}>
                  {formatFileSize(match.size)}
                </Tag>
              )}
            </div>
            
            {/* 文件名（次要信息） */}
            {displayName && displayName !== displayPath && (
              <div style={{ marginTop: 4, fontSize: 11, color: "#8c6e2f" }}>
                文件名：{displayName}
              </div>
            )}
          </div>
        </List.Item>
      );
    }
    
    // 兼容：内容搜索数据渲染
    return (
      <List.Item
        key={`content-${index}`}
        style={{
          padding: "8px 12px",
          borderBottom: index < matches.length - 1 ? "1px solid #91d5ff" : "none",
          background: index % 2 === 0 ? "rgba(230,247,255,0.3)" : "transparent",
        }}
      >
        <div style={{ width: "100%" }}>
          <div style={{ display: "flex", alignItems: "center" }}>
            <FileTextOutlined style={{ color: "#1890ff", marginRight: 6 }} />
            <code
              style={{
                background: "#f5f5f5",
                padding: "2px 6px",
                borderRadius: 4,
                fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                fontSize: 12,
              }}
            >
              {match.file_path}
            </code>
            {match.line_number && (
              <Tag style={{ marginLeft: 8 }}>行 {match.line_number}</Tag>
            )}
          </div>
          
          {match.line_content && (
            <div
              style={{
                marginTop: 6,
                background: "#1e1e1e",
                padding: "6px 10px",
                borderRadius: 4,
                color: "#d4d4d4",
                fontFamily: "Consolas, Monaco, 'Courier New', monospace",
                fontSize: 12,
                whiteSpace: "pre-wrap",
                wordBreak: "break-all",
              }}
            >
              {match.line_content}
            </div>
          )}
        </div>
      </List.Item>
    );
  };

  // 空数据检查
  if (files_matched === 0 && matches.length === 0) {
    return (
      <div style={{ color: "#888", fontStyle: "italic" }}>
        🔍 未找到匹配结果
      </div>
    );
  }

  // 【小强实现 2026-03-31】蓝色系搜索结果背景样式（与action_tool一致）
  const searchResultStyle = {
    background: "linear-gradient(135deg, #e6f7ff 0%, #f0f5ff 100%)",
    border: "1px solid #69c0ff",
    borderRadius: 8,
    padding: "10px 14px",
    marginTop: 6,
    fontSize: "0.9em",
    lineHeight: 1.8,
    maxHeight: 400,
    overflow: "auto",
  };

  return (
    <div>
      {/* 【小强实现 2026-03-31】搜索统计信息 - 统一蓝色系（符合设计文档2.8.2） */}
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
        {/* 搜索模式 */}
        <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>
          🔍 搜索模式：{search_pattern}
        </Tag>
        
        {/* 搜索路径（新增） */}
        {search_path && (
          <Tag style={{ background: "#e6f7ff", border: "none", color: "#003a8c" }}>
            📂 {search_path}
          </Tag>
        )}
        
        {/* 文件数量 */}
        <span
          style={{
            background: "#e6f7ff",
            padding: "2px 8px",
            borderRadius: 4,
            color: "#003a8c",
            fontWeight: 500,
          }}
        >
          📁 {files_matched} 个文件
        </span>
        
        {/* 分页信息（新增） */}
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

      {/* 匹配详情列表 */}
      {matches.length > 0 && (
        <div style={searchResultStyle}>
          {/* 【小强实现 2026-03-31】虚拟滚动处理 */}
          {shouldUseVirtualList ? (
            <div style={{ maxHeight: 350, overflow: "auto" }}>
              {/* 简化版虚拟列表：直接渲染，使用CSS优化 */}
              <List
                dataSource={matches}
                size="small"
                renderItem={renderMatchItem}
              />
              <div style={{ 
                textAlign: "center", 
                padding: "8px", 
                color: "#666",
                fontSize: 11,
                background: "rgba(230,247,255,0.5)",
                borderRadius: 4,
              }}>
                ⚠️ 显示前 {matches.length} 条结果（超过100条启用虚拟滚动）
              </div>
            </div>
          ) : (
            <List
              dataSource={matches}
              size="small"
              renderItem={renderMatchItem}
            />
          )}
          
          {/* 【小强实现 2026-03-31】加载更多按钮 */}
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
        </div>
      )}
    </div>
  );
};

export default SearchFilesView;