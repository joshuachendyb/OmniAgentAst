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
export function transformSearchFilesData(rawData: unknown): SearchFilesData {
  const data = rawData as Record<string, unknown>;
  return {
    files_matched: data?.total as number || 0,
    total_matches: 0,
    matches: ((data?.matches || []) as unknown[]).map((match: unknown) => {
      const m = match as Record<string, unknown>;
      return {
        name: (m?.name as string) || "",
        path: (m?.path as string) || "",
        size: (m?.size as number) || 0,
      };
    }),
    search_pattern: (data?.file_pattern as string) || "",
    search_path: (data?.path as string) || "",
    pagination: {
      page: (data?.page as number) || 1,
      total_pages: (data?.total_pages as number) || 1,
      page_size: (data?.page_size as number) || 200,
      has_more: (data?.has_more as boolean) || false,
      last_file: data?.last_file as string | undefined,
    },
  };
}

/**
 * search_file_content（文件内容搜索）转换函数
 * 将后端返回的文件内容搜索数据转换为前端组件期望的格式
 */
export function transformSearchFileContentData(rawData: unknown): SearchFileContentData {
  const data = rawData as Record<string, unknown>;
  return {
    success: data?.success as boolean,
    pattern: (data?.pattern as string) || "",
    path: (data?.path as string) || "",
    file_pattern: (data?.file_pattern as string) || "",
    matches: (data?.matches as SearchFileContentData['matches']) || [],
    total: (data?.total as number) || 0,
    total_matches: (data?.total_matches as number) || 0,
    pagination: {
      page: (data?.page as number) || 1,
      total_pages: (data?.total_pages as number) || 1,
      page_size: (data?.page_size as number) || 200,
      has_more: (data?.has_more as boolean) || false,
      last_file: data?.last_file as string | undefined,
    },
  };
}