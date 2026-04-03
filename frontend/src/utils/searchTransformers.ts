/**
 * searchTransformers.ts - 搜索工具数据转换函数
 *
 * 功能：将后端搜索工具返回的数据转换为前端组件期望的格式
 * 包含：search_files（文件搜索）和 search_file_content（文件内容搜索）的转换
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-31
 */

// 类型定义
export interface SearchFilesData {
  files_matched: number;
  total_matches: number;
  matches: Array<{
    name: string;
    path: string;
    size: number;
  }>;
  search_pattern: string;
  search_path: string;
  pagination: {
    page: number;
    total_pages: number;
    page_size: number;
    has_more: boolean;
    last_file?: string; // 用于分页标记的最后一个文件路径
  };
}

export interface SearchFileContentData {
  success: boolean;
  pattern: string;
  path: string;
  file_pattern: string;
  matches: Array<{
    file: string;
    matches: Array<{
      start: number;
      end: number;
      matched: string;
      context: string;
    }>;
    match_count: number;
  }>;
  total: number;
  total_matches: number;
  pagination: {
    page: number;
    total_pages: number;
    page_size: number;
    has_more: boolean;
    last_file?: string; // 用于分页标记的最后一个文件路径
  };
}

/**
 * search_files（文件搜索）转换函数
 * 将后端返回的文件搜索数据转换为前端组件期望的格式
 * 
 * 后端返回: total=3023 (文件数量), matches=[...]
 * 前端期望: files_matched=3023, total_matches=0 (不使用)
 */
export function transformSearchFilesData(rawData: any): SearchFilesData {
  return {
    files_matched: rawData?.total || 0,  // 后端返回total=文件数量
    total_matches: 0,  // search_files是文件搜索，不应该有"匹配数"概念
    matches: (rawData?.matches || []).map((match: any) => ({
      name: match.name || "",
      path: match.path || "",
      size: match.size || 0,
    })),
    search_pattern: rawData?.file_pattern || "",
    search_path: rawData?.path || "",
    pagination: {
      page: rawData?.page || 1,
      total_pages: rawData?.total_pages || 1,
      page_size: rawData?.page_size || 200,
      has_more: rawData?.has_more || false,
      last_file: rawData?.last_file, // 最后一个文件的路径，用于分页标记
    },
  };
}

/**
 * search_file_content（文件内容搜索）转换函数
 * 将后端返回的文件内容搜索数据转换为前端组件期望的格式
 */
export function transformSearchFileContentData(rawData: any): SearchFileContentData {
  return {
    success: rawData?.success,
    pattern: rawData?.pattern || "",
    path: rawData?.path || "",
    file_pattern: rawData?.file_pattern || "",
    matches: rawData?.matches || [],
    total: rawData?.total || 0,
    total_matches: rawData?.total_matches || 0,
    pagination: {
      page: rawData?.page || 1,
      total_pages: rawData?.total_pages || 1,
      page_size: rawData?.page_size || 200,
      has_more: rawData?.has_more || false,
      last_file: rawData?.last_file, // 最后一个文件的路径，用于分页标记
    },
  };
}