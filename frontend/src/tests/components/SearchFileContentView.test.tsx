/**
 * SearchFileContentView 测试用例
 * 
 * 【小资编写 2026-03-31】
 * 根据设计文档第3章要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-03-31
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import SearchFileContentView from "../../components/Chat/views/SearchFileContentView";
import { transformSearchFileContentData } from "../../utils/searchTransformers";

// ============================================================
// 测试数据
// ============================================================

// 后端返回的原始数据（符合设计文档3.1）
const mockRawData = {
  success: true,
  pattern: "安全",
  path: "D:\\1WTCB",
  file_pattern: "*",
  matches: [
    {
      file: "0个律云系统\\00-原始需求\\应用CB开发构建技术说明书V1.2.md",
      matches: [
        {
          start: 1312,
          end: 1314,
          matched: "安全",
          context: "...一些文本内容...",
        },
        {
          start: 2500,
          end: 2502,
          matched: "安全",
          context: "...另一个匹配上下文...",
        },
      ],
      match_count: 5,
    },
    {
      file: "另一个文件\\测试.txt",
      matches: [
        {
          start: 100,
          end: 102,
          matched: "安全",
          context: "...第三个匹配上下文...",
        },
      ],
      match_count: 1,
    },
  ],
  total: 91,
  total_matches: 668,
  page: 1,
  total_pages: 3,
  page_size: 200,
  last_file: "RuleTool\\工具\\Graphviz-14.1.1-win64\\bin\\brotlicommon.dll",
  has_more: true,
};

// 转换后的数据
const mockTransformedData = transformSearchFileContentData(mockRawData);

// 空数据
const mockEmptyData = {
  success: true,
  pattern: "不存在的关键词",
  path: "D:\\空目录",
  file_pattern: "*.xyz",
  matches: [],
  total: 0,
  total_matches: 0,
  page: 1,
  total_pages: 1,
  page_size: 200,
  has_more: false,
};

// 最后一页数据（无更多）
const mockLastPageData = {
  success: true,
  pattern: "测试",
  path: "D:\\项目",
  file_pattern: "*.txt",
  matches: [
    {
      file: "D:\\项目\\最后文件.txt",
      matches: [
        {
          start: 10,
          end: 12,
          matched: "测试",
          context: "...最后文件的匹配上下文...",
        },
      ],
      match_count: 1,
    },
  ],
  total: 1,
  total_matches: 1,
  page: 1,
  total_pages: 1,
  page_size: 200,
  has_more: false,
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 SearchFileContentView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockTransformedData,
    ...overrides,
  };
}

// ============================================================
// 转换函数测试（对应设计文档3.2）
// ============================================================

describe("transformSearchFileContentData 转换函数测试", () => {
  it("应该正确转换后端数据到前端期望格式", () => {
    const result = transformSearchFileContentData(mockRawData);

    expect(result.success).toBe(true);
    expect(result.pattern).toBe("安全");
    expect(result.path).toBe("D:\\1WTCB");
    expect(result.file_pattern).toBe("*");
  });

  it("应该正确转换嵌套的 matches 数组", () => {
    const result = transformSearchFileContentData(mockRawData);

    expect(result.matches).toHaveLength(2);
    expect(result.matches[0].file).toBe("0个律云系统\\00-原始需求\\应用CB开发构建技术说明书V1.2.md");
    expect(result.matches[0].match_count).toBe(5);
    expect(result.matches[0].matches).toHaveLength(2);
  });

  it("应该正确转换分页信息", () => {
    const result = transformSearchFileContentData(mockRawData);

    expect(result.pagination.page).toBe(1);
    expect(result.pagination.total_pages).toBe(3);
    expect(result.pagination.page_size).toBe(200);
    expect(result.pagination.has_more).toBe(true);
    expect(result.pagination.last_file).toBe("RuleTool\\工具\\Graphviz-14.1.1-win64\\bin\\brotlicommon.dll");
  });

  it("应该处理空 matches 数组", () => {
    const result = transformSearchFileContentData(mockEmptyData);

    expect(result.matches).toHaveLength(0);
    expect(result.total).toBe(0);
    expect(result.total_matches).toBe(0);
  });

  it("应该处理 null 和 undefined 值", () => {
    const result = transformSearchFileContentData(null);

    expect(result.pattern).toBe("");
    expect(result.path).toBe("");
    expect(result.matches).toHaveLength(0);
  });
});

// ============================================================
// 基本渲染测试（对应设计文档3.3.2）
// ============================================================

describe("SearchFileContentView 基本渲染测试", () => {
  it("应该渲染搜索关键词", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("关键词"))).toBeTruthy();
    expect(screen.getByText((content) => content.includes("安全"))).toBeTruthy();
  });

  it("应该渲染搜索路径", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("📂"))).toBeTruthy();
  });

  it("应该渲染文件模式", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("📁"))).toBeTruthy();
  });

  it("应该渲染匹配文件数统计", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    const fileElements = screen.getAllByText((content) => content.includes("个文件"));
    expect(fileElements.length).toBeGreaterThan(0);
  });

  it("应该渲染内容匹配数统计", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    const matchElements = screen.getAllByText((content) => content.includes("处匹配"));
    expect(matchElements.length).toBeGreaterThan(0);
  });

  it("应该渲染分页信息", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("📋"))).toBeTruthy();
    expect(screen.getByText((content) => content.includes("1/3"))).toBeTruthy();
  });

  it("应该渲染文件列表（至少有一个文件）", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    const fileElements = screen.getAllByText((content) => 
      content.includes("应用CB开发构建技术说明书V1.2.md")
    );
    expect(fileElements.length).toBeGreaterThan(0);
  });

  it("应该渲染匹配数量标签", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    // 匹配数量可能在多个地方出现
    const matchCountElements = screen.getAllByText((content) => 
      content.includes("处匹配")
    );
    expect(matchCountElements.length).toBeGreaterThan(0);
  });
});

// ============================================================
// 空数据测试（对应设计文档3.4）
// ============================================================

describe("SearchFileContentView 空数据测试", () => {
  it("应该显示空数据提示", () => {
    const emptyTransformedData = transformSearchFileContentData(mockEmptyData);
    const props = createProps({ data: emptyTransformedData });
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText("🔍 未找到匹配结果")).toBeTruthy();
  });

  it("应该处理 success=false 的情况", () => {
    const failData = {
      ...mockTransformedData,
      success: false,
    };
    const props = createProps({ data: failData });
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText("🔍 未找到匹配结果")).toBeTruthy();
  });
});

// ============================================================
// 分页功能测试（对应设计文档3.5）
// ============================================================

describe("SearchFileContentView 分页功能测试", () => {
  it("当 has_more=true 且有 onLoadMore 回调时应该显示加载更多按钮", () => {
    const mockLoadMore = vi.fn();
    const props = createProps({ onLoadMore: mockLoadMore });
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("加载更多"))).toBeTruthy();
  });

  it("当 has_more=false 时不应该显示加载更多按钮", () => {
    const lastPageTransformed = transformSearchFileContentData(mockLastPageData);
    const props = createProps({ data: lastPageTransformed });
    render(<SearchFileContentView {...props} />);

    expect(screen.queryByText((content) => content.includes("加载更多"))).toBeNull();
  });

  it("当 has_more=true 但没有 onLoadMore 回调时不应该显示按钮", () => {
    const props = createProps({ data: mockTransformedData, onLoadMore: undefined });
    render(<SearchFileContentView {...props} />);

    expect(screen.queryByText((content) => content.includes("加载更多"))).toBeNull();
  });

  it("加载更多按钮应该显示加载状态", () => {
    const mockLoadMore = vi.fn();
    const props = createProps({ onLoadMore: mockLoadMore, isLoadingMore: true });
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("加载中"))).toBeTruthy();
  });
});

// ============================================================
// 虚拟滚动提示测试（对应设计文档3.6）
// ============================================================

describe("SearchFileContentView 虚拟滚动测试", () => {
  it("应该渲染文件数量提示", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("个文件显示"))).toBeTruthy();
  });

  it("当有更多结果时应该显示提示", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    expect(screen.getByText((content) => content.includes("更多结果请加载"))).toBeTruthy();
  });
});

// ============================================================
// 样式测试（对应设计文档3.3.2 视觉一致性）
// ============================================================

describe("SearchFileContentView 样式测试", () => {
  it("应该使用蓝色系配色", () => {
    const container = document.createElement("div");
    const props = createProps();
    const { container: renderedContainer } = render(<SearchFileContentView {...props} />, {
      container: document.body.appendChild(container),
    });

    // 检查是否有蓝色背景的Tag
    const tags = renderedContainer.querySelectorAll('[style*="e6f7ff"]');
    expect(tags.length).toBeGreaterThan(0);
  });
});

// ============================================================
// 匹配详情测试（对应设计文档3.3.2）
// 注意：匹配详情在折叠的Collapse Panel里，默认不展开
// ============================================================

describe("SearchFileContentView 匹配详情测试", () => {
  it("Collapse默认应该折叠（不显示匹配详情）", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    // 匹配上下文在折叠的Panel里，默认不应该可见
    // 这验证了Collapse组件的默认行为
    expect(screen.queryByText((content) => content.includes("一些文本内容"))).toBeNull();
  });

  it("应该渲染Collapse组件", () => {
    const props = createProps();
    render(<SearchFileContentView {...props} />);

    // 检查是否有Collapse组件
    const collapseElement = document.querySelector(".ant-collapse");
    expect(collapseElement).toBeTruthy();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("SearchFileContentView 边界条件测试", () => {
  it("应该处理超长文件路径", () => {
    const longPathData = {
      success: true,
      pattern: "测试",
      path: "D:\\项目",
      file_pattern: "*",
      matches: [
        {
          file: "D:\\非常深的目录\\非常深的子目录\\甚至更深的目录\\最终目录\\超长文件名.md",
          matches: [
            {
              start: 100,
              end: 102,
              matched: "测试",
              context: "...上下文内容...",
            },
          ],
          match_count: 1,
        },
      ],
      total: 1,
      total_matches: 1,
      pagination: {
        page: 1,
        total_pages: 1,
        page_size: 200,
        has_more: false,
      },
    };

    const props = createProps({ data: longPathData });
    render(<SearchFileContentView {...props} />);

    // 检查长路径是否被正确渲染（使用span而非code标签）
    const fileElements = screen.getAllByText((content) => 
      content.includes("超长文件名.md")
    );
    expect(fileElements.length).toBeGreaterThan(0);
  });

  it("应该处理无匹配详情的文件", () => {
    const noMatchDetailData = {
      success: true,
      pattern: "测试",
      path: "D:\\项目",
      file_pattern: "*",
      matches: [
        {
          file: "D:\\项目\\无匹配.txt",
          matches: [],
          match_count: 0,
        },
      ],
      total: 1,
      total_matches: 0,
      pagination: {
        page: 1,
        total_pages: 1,
        page_size: 200,
        has_more: false,
      },
    };

    const props = createProps({ data: noMatchDetailData });
    render(<SearchFileContentView {...props} />);

    // 文件路径应该被渲染
    expect(screen.getByText((content) => content.includes("无匹配.txt"))).toBeTruthy();
  });

  it("应该处理超多文件数量", () => {
    const manyFilesData = {
      success: true,
      pattern: "测试",
      path: "D:\\项目",
      file_pattern: "*",
      matches: Array.from({ length: 150 }, (_, i) => ({
        file: `D:\\项目\\文件${i}.txt`,
        matches: [
          {
            start: 100 * i,
            end: 100 * i + 2,
            matched: "测试",
            context: `...第${i}个文件的上下文...`,
          },
        ],
        match_count: 1,
      })),
      total: 150,
      total_matches: 150,
      pagination: {
        page: 1,
        total_pages: 1,
        page_size: 200,
        has_more: false,
      },
    };

    const props = createProps({ data: manyFilesData });
    render(<SearchFileContentView {...props} />);

    // 虚拟滚动提示应该显示
    expect(screen.getByText((content) => content.includes("个文件显示"))).toBeTruthy();
  });

  it("应该处理超多页码", () => {
    const manyPagesData = {
      ...mockRawData,
      page: 999,
      total_pages: 9999,
    };

    const transformed = transformSearchFileContentData(manyPagesData);
    const props = createProps({ data: transformed });
    render(<SearchFileContentView {...props} />);

    // 检查页码是否渲染
    expect(screen.getByText((content) => content.includes("999"))).toBeTruthy();
  });

  it("应该处理超大文件中的大量匹配", () => {
    const largeMatchData = {
      success: true,
      pattern: "函数",
      path: "D:\\项目",
      file_pattern: "*.py",
      matches: [
        {
          file: "D:\\项目\\大文件.py",
          matches: Array.from({ length: 50 }, (_, i) => ({
            start: i * 100,
            end: i * 100 + 2,
            matched: "函数",
            context: `...第${i}个匹配的上下文内容...`,
          })),
          match_count: 50,
        },
      ],
      total: 1,
      total_matches: 50,
      pagination: {
        page: 1,
        total_pages: 1,
        page_size: 200,
        has_more: false,
      },
    };

    const props = createProps({ data: largeMatchData });
    render(<SearchFileContentView {...props} />);

    // 应该显示多个匹配
    const matchedElements = screen.getAllByText((content) => content.includes("函数"));
    expect(matchedElements.length).toBeGreaterThan(0);
  });
});
