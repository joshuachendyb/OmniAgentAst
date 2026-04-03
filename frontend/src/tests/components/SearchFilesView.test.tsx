/**
 * SearchFilesView 测试用例
 * 
 * 【小资编写 2026-03-31】
 * 根据设计文档第2章要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.2
 * @since 2026-03-31
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import SearchFilesView from "../../components/Chat/views/SearchFilesView";
import { transformSearchFilesData } from "../../utils/searchTransformers";

// ============================================================
// 测试数据
// ============================================================

// 后端返回的原始数据（符合设计文档2.1）
const mockRawData = {
  success: true,
  file_pattern: "*.txt",
  path: "D:\\项目",
  matches: [
    {
      name: "我的资料.txt",
      path: "D:\\项目\\我的资料.txt",
      size: 5090,
    },
    {
      name: "资料信息.txt",
      path: "D:\\项目\\资料信息.txt",
      size: 601,
    },
    {
      name: "项目文档.txt",
      path: "D:\\项目\\子目录\\项目文档.txt",
      size: 10240,
    },
  ],
  total: 3049,
  page: 1,
  total_pages: 16,
  page_size: 200,
  last_file: "D:\\项目\\子目录\\项目文档.txt",
  has_more: true,
};

// 转换后的数据
const mockTransformedData = transformSearchFilesData(mockRawData);

// 空数据
const mockEmptyData = {
  success: true,
  file_pattern: "*.xyz",
  path: "D:\\空目录",
  matches: [],
  total: 0,
  page: 1,
  total_pages: 1,
  page_size: 200,
  last_file: undefined,
  has_more: false,
};

// 分页数据（最后一页，无更多）
const mockLastPageData = {
  success: true,
  file_pattern: "*.txt",
  path: "D:\\项目",
  matches: [
    {
      name: "最后文件.txt",
      path: "D:\\项目\\最后文件.txt",
      size: 100,
    },
  ],
  total: 3049,
  page: 16,
  total_pages: 16,
  page_size: 200,
  last_file: "D:\\项目\\最后文件.txt",
  has_more: false,
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 SearchFilesView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockTransformedData,
    ...overrides,
  };
}

// ============================================================
// 转换函数测试（对应设计文档2.2）
// ============================================================

describe("transformSearchFilesData 转换函数测试", () => {
  it("应该正确转换后端数据到前端期望格式", () => {
    const result = transformSearchFilesData(mockRawData);

    // 后端返回 total=3049 (文件总数), matches=[3个文件]
    // 前端应该显示 files_matched=3049, total_matches=0 (文件搜索不显示匹配数)
    expect(result.files_matched).toBe(3049);  // 使用后端返回的 total
    expect(result.total_matches).toBe(0);     // 文件搜索没有"匹配数"概念
    expect(result.search_pattern).toBe("*.txt");
    expect(result.search_path).toBe("D:\\项目");
  });

  it("应该正确转换 matches 数组", () => {
    const result = transformSearchFilesData(mockRawData);

    expect(result.matches).toHaveLength(3);
    expect(result.matches[0].name).toBe("我的资料.txt");
    expect(result.matches[0].path).toBe("D:\\项目\\我的资料.txt");
    expect(result.matches[0].size).toBe(5090);
  });

  it("应该正确转换分页信息", () => {
    const result = transformSearchFilesData(mockRawData);

    expect(result.pagination.page).toBe(1);
    expect(result.pagination.total_pages).toBe(16);
    expect(result.pagination.page_size).toBe(200);
    expect(result.pagination.has_more).toBe(true);
    expect(result.pagination.last_file).toBe("D:\\项目\\子目录\\项目文档.txt");
  });

  it("应该处理空 matches 数组", () => {
    const result = transformSearchFilesData(mockEmptyData);

    expect(result.files_matched).toBe(0);
    expect(result.matches).toHaveLength(0);
    expect(result.pagination.has_more).toBe(false);
  });

  it("应该处理 null 和 undefined 值", () => {
    const result = transformSearchFilesData(null);

    expect(result.files_matched).toBe(0);
    expect(result.matches).toHaveLength(0);
    expect(result.search_pattern).toBe("");
  });
});

// ============================================================
// 基本渲染测试（对应设计文档2.4.3）
// ============================================================

describe("SearchFilesView 基本渲染测试", () => {
  it("应该渲染搜索模式标签", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    // 使用函数匹配器处理文本被拆分的情况
    expect(screen.getByText((content) => content.includes("搜索模式"))).toBeTruthy();
  });

  it("应该渲染文件数量统计", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("📁"))).toBeTruthy();
    expect(screen.getByText((content) => content.includes("个文件"))).toBeTruthy();
  });

  it("应该渲染匹配数量统计", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("🔎"))).toBeTruthy();
    expect(screen.getByText((content) => content.includes("处匹配"))).toBeTruthy();
  });

  it("应该渲染分页信息", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("📋"))).toBeTruthy();
  });

  it("应该渲染搜索路径", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("📂"))).toBeTruthy();
  });

  it("应该渲染文件列表（至少有一个文件）", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    // 使用 getAllByText 因为文件名可能出现在多个地方
    const fileElements = screen.getAllByText((content) => content.includes("我的资料.txt"));
    expect(fileElements.length).toBeGreaterThan(0);
  });

  it("应该渲染文件大小", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    // 使用 getAllByText 因为可能有多个文件
    const sizeElements = screen.getAllByText((content) => content.includes("KB"));
    expect(sizeElements.length).toBeGreaterThan(0);
  });
});

// ============================================================
// 空数据测试（对应设计文档2.5 错误处理）
// ============================================================

describe("SearchFilesView 空数据测试", () => {
  it("应该显示空数据提示", () => {
    const emptyTransformedData = transformSearchFilesData(mockEmptyData);
    const props = createProps({ data: emptyTransformedData });
    render(<SearchFilesView {...props} />);

    expect(screen.getByText("🔍 未找到匹配结果")).toBeTruthy();
  });
});

// ============================================================
// 分页功能测试（对应设计文档2.4.3）
// ============================================================

describe("SearchFilesView 分页功能测试", () => {
  it("当 has_more=true 且有 onLoadMore 回调时应该显示加载更多按钮", () => {
    const mockLoadMore = vi.fn();
    const props = createProps({ onLoadMore: mockLoadMore });
    render(<SearchFilesView {...props} />);

    // 按钮可能使用 span 或其他元素包裹文本
    expect(screen.getByText((content) => content.includes("加载更多"))).toBeTruthy();
  });

  it("当 has_more=false 时不应该显示加载更多按钮", () => {
    const lastPageTransformed = transformSearchFilesData(mockLastPageData);
    const props = createProps({ data: lastPageTransformed });
    render(<SearchFilesView {...props} />);

    expect(screen.queryByText((content) => content.includes("加载更多"))).toBeNull();
  });

  it("当 has_more=true 但没有 onLoadMore 回调时不应该显示按钮", () => {
    const props = createProps({ data: mockTransformedData, onLoadMore: undefined });
    render(<SearchFilesView {...props} />);

    expect(screen.queryByText((content) => content.includes("加载更多"))).toBeNull();
  });

  it("加载更多按钮应该显示加载状态", () => {
    const mockLoadMore = vi.fn();
    const props = createProps({ onLoadMore: mockLoadMore, isLoadingMore: true });
    render(<SearchFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("加载中"))).toBeTruthy();
  });
});

// ============================================================
// 虚拟滚动测试（对应设计文档2.6）
// ============================================================

describe("SearchFilesView 虚拟滚动测试", () => {
  it("超过100条数据应该显示虚拟滚动提示", () => {
    // 创建超过100条数据
    const largeData = {
      files_matched: 150,
      total_matches: 5000,
      matches: Array.from({ length: 150 }, (_, i) => ({
        name: `文件${i}.txt`,
        path: `D:\\项目\\文件${i}.txt`,
        size: 1000 * (i + 1),
      })),
      search_pattern: "*.txt",
      search_path: "D:\\项目",
      pagination: {
        page: 1,
        total_pages: 10,
        page_size: 200,
        has_more: true,
      },
    };

    const props = createProps({ data: largeData });
    render(<SearchFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("超过100条"))).toBeTruthy();
  });

  it("少于100条数据不应该显示虚拟滚动提示", () => {
    const props = createProps();
    render(<SearchFilesView {...props} />);

    expect(screen.queryByText((content) => content.includes("超过100条"))).toBeNull();
  });
});

// ============================================================
// 样式测试（对应设计文档2.8 视觉一致性）
// ============================================================

describe("SearchFilesView 样式测试", () => {
  it("应该使用蓝色系配色", () => {
    const container = document.createElement("div");
    const props = createProps();
    const { container: renderedContainer } = render(<SearchFilesView {...props} />, {
      container: document.body.appendChild(container),
    });

    // 检查是否有蓝色背景的Tag
    const tags = renderedContainer.querySelectorAll('[style*="e6f7ff"]');
    expect(tags.length).toBeGreaterThan(0);
  });
});

// ============================================================
// 向后兼容测试（对应设计文档2.4.2）
// ============================================================

describe("SearchFilesView 向后兼容测试", () => {
  it("应该兼容旧版 file_path 字段", () => {
    const legacyData = {
      files_matched: 1,
      total_matches: 1,
      matches: [
        {
          file_path: "D:\\旧项目\\文档.txt",
          line_number: 10,
          line_content: "这是旧版格式",
        },
      ],
      search_pattern: "*.txt",
    };

    const props = createProps({ data: legacyData });
    render(<SearchFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("旧项目"))).toBeTruthy();
  });

  it("应该处理混合数据类型（文件搜索+内容搜索）", () => {
    const mixedData = {
      files_matched: 2,
      total_matches: 5,
      matches: [
        // 文件搜索数据
        {
          name: "文件A.txt",
          path: "D:\\项目\\文件A.txt",
          size: 1024,
        },
        // 内容搜索数据
        {
          file_path: "D:\\项目\\文件B.txt",
          line_number: 5,
          line_content: "匹配的内容",
        },
      ],
      search_pattern: "*.txt",
    };

    const props = createProps({ data: mixedData });
    render(<SearchFilesView {...props} />);

    // 使用 getAllByText 因为文件名可能出现在多个地方
    const fileAElements = screen.getAllByText((content) => content.includes("文件A"));
    expect(fileAElements.length).toBeGreaterThan(0);
    expect(screen.getByText((content) => content.includes("文件B"))).toBeTruthy();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("SearchFilesView 边界条件测试", () => {
  it("应该处理超长文件路径", () => {
    const longPathData = {
      files_matched: 1,
      total_matches: 1,
      matches: [
        {
          name: "超长文件名.txt",
          path: "D:\\非常深的目录\\非常深的子目录\\甚至更深的目录\\最终目录\\超长文件名.txt",
          size: 1024,
        },
      ],
      search_pattern: "*.txt",
    };

    const props = createProps({ data: longPathData });
    const { container } = render(<SearchFilesView {...props} />);

    // 检查长路径是否被正确渲染
    const codeElement = container.querySelector("code");
    expect(codeElement).toBeTruthy();
  });

  it("应该处理超大文件大小", () => {
    const largeFileData = {
      files_matched: 1,
      total_matches: 1,
      matches: [
        {
          name: "大文件.zip",
          path: "D:\\项目\\大文件.zip",
          size: 1024 * 1024 * 1024 * 2, // 2GB
        },
      ],
      search_pattern: "*.zip",
    };

    const props = createProps({ data: largeFileData });
    render(<SearchFilesView {...props} />);

    // 组件超过1MB就显示MB（2GB = 2048.00 MB）
    expect(screen.getByText((content) => content.includes("MB"))).toBeTruthy();
  });

  it("应该处理文件大小为0的情况", () => {
    const zeroSizeData = {
      files_matched: 1,
      total_matches: 1,
      matches: [
        {
          name: "空文件.txt",
          path: "D:\\项目\\空文件.txt",
          size: 0,
        },
      ],
      search_pattern: "*.txt",
    };

    const props = createProps({ data: zeroSizeData });
    render(<SearchFilesView {...props} />);

    // 组件 size=0 时不显示大小标签（因为有 match.size > 0 条件）
    // 验证文件路径被正确渲染（文件名可能出现在多个地方）
    const fileElements = screen.getAllByText((content) => content.includes("空文件.txt"));
    expect(fileElements.length).toBeGreaterThan(0);
  });

  it("应该处理超多页码", () => {
    const manyPagesData = {
      ...mockRawData,
      page: 999,
      total_pages: 9999,
    };

    const transformed = transformSearchFilesData(manyPagesData);
    const props = createProps({ data: transformed });
    render(<SearchFilesView {...props} />);

    // 检查页码是否渲染
    expect(screen.getByText((content) => content.includes("999"))).toBeTruthy();
  });
});
