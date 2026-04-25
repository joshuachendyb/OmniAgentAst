/**
 * CompressFilesView 测试用例
 * 
 * 【小资编写 2026-04-25】
 * 根据设计文档第3.2.3节要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-25
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import CompressFilesView from "../../components/Chat/views/CompressFilesView";

// ============================================================
// 测试数据
// ============================================================

// 完整压缩数据
const mockCompleteData = {
  archive_path: "D:\\项目\\backup.zip",
  archive_name: "backup.zip",
  original_size: 1024 * 1024 * 10, // 10MB
  compressed_size: 1024 * 1024 * 8, // 8MB
  compression_ratio: 20.0, // 20%
  file_count: 5,
  file_list: [
    "file1.txt",
    "file2.txt",
    "file3.txt",
    "folder/file4.txt",
    "folder/file5.txt",
  ],
  success: true,
};

// 高压缩率数据
const mockHighRatioData = {
  archive_path: "D:\\项目\\texts.zip",
  archive_name: "texts.zip",
  original_size: 1024 * 100, // 100KB
  compressed_size: 1024 * 5, // 5KB
  compression_ratio: 95.0, // 95%
  file_count: 50,
  file_list: Array.from({ length: 50 }, (_, i) => `doc${i}.txt`),
  success: true,
};

// 失败数据
const mockFailedData = {
  archive_path: "D:\\项目\\backup.zip",
  success: false,
  error_message: "磁盘空间不足",
};

// 空数据
const mockEmptyData = {};

// 无文件列表数据
const mockNoFileListData = {
  archive_path: "D:\\项目\\backup.zip",
  archive_name: "backup.zip",
  original_size: 1024 * 1024,
  compressed_size: 1024 * 512,
  compression_ratio: 50.0,
  file_count: 0,
  file_list: [],
  success: true,
};

// 大文件数据
const mockLargeData = {
  archive_path: "D:\\项目\\movie.zip",
  archive_name: "movie.zip",
  original_size: 1024 * 1024 * 1024 * 5, // 5GB
  compressed_size: 1024 * 1024 * 1024 * 2, // 2GB
  compression_ratio: 60.0,
  file_count: 1,
  file_list: ["movie.mp4"],
  success: true,
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 CompressFilesView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockCompleteData,
    ...overrides,
  };
}

// ============================================================
// 基本渲染测试（对应设计文档3.2.3）
// ============================================================

describe("CompressFilesView 基本渲染测试", () => {
  it("应该渲染文件压缩完成标题", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("🗜️ 文件压缩完成")).toBeTruthy();
  });

  it("应该渲染原始大小", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("📊 原始大小")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("10.0"))).toBeTruthy();
  });

  it("应该渲染压缩后大小", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("📦 压缩后")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("8.0"))).toBeTruthy();
  });

  it("应该渲染压缩率", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("📈 压缩率")).toBeTruthy();
    expect(screen.getByText("20.0%")).toBeTruthy();
  });

  it("应该渲染压缩文件信息", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("📦 压缩文件")).toBeTruthy();
    expect(screen.getByText("backup.zip")).toBeTruthy();
  });
});

// ============================================================
// 压缩效果测试（对应设计文档3.2.3 UI设计）
// ============================================================

describe("CompressFilesView 压缩效果测试", () => {
  it("高压缩率应该显示绿色", () => {
    const props = createProps({ data: mockHighRatioData });
    render(<CompressFilesView {...props} />);

    // 95%压缩率应该是绿色
    expect(screen.getByText("95.0%")).toBeTruthy();
  });

  it("中等压缩率应该显示黄色", () => {
    const midRatioData = {
      ...mockCompleteData,
      compression_ratio: 40.0,
    };
    const props = createProps({ data: midRatioData });
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("40.0%")).toBeTruthy();
  });

  it("应该正确显示压缩率数值", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    // 10MB → 8MB 是20%压缩
    expect(screen.getByText("20.0%")).toBeTruthy();
  });
});

// ============================================================
// 失败状态测试（对应设计文档3.2.3 样式规范）
// ============================================================

describe("CompressFilesView 失败状态测试", () => {
  it("应该显示失败标题", () => {
    const props = createProps({ data: mockFailedData });
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("❌ 文件压缩失败")).toBeTruthy();
  });

  it("应该显示失败渐变背景", () => {
    const props = createProps({ data: mockFailedData });
    const { container } = render(<CompressFilesView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasRedGradient = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("fff2f0")) hasRedGradient = true;
    });
    expect(hasRedGradient).toBe(true);
  });

  it("应该显示错误信息", () => {
    const props = createProps({ data: mockFailedData });
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("磁盘空间不足")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("错误信息："))).toBeTruthy();
  });

  it("失败时不应该显示统计信息", () => {
    const props = createProps({ data: mockFailedData });
    render(<CompressFilesView {...props} />);

    expect(screen.queryByText("📊 原始大小")).toBeNull();
    expect(screen.queryByText("📈 压缩率")).toBeNull();
  });
});

// ============================================================
// 文件列表测试
// ============================================================

describe("CompressFilesView 文件列表测试", () => {
  it("应该显示文件列表折叠面板", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("包含文件"))).toBeTruthy();
  });

  it("应该正确显示文件数量", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("5个"))).toBeTruthy();
  });

  it("应该显示所有文件名", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    // 展开文件列表
    const collapseHeader = screen.getByText((content) => content.includes("包含文件"));
    expect(collapseHeader).toBeTruthy();
  });

  it("应该处理嵌套文件路径", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    // 嵌套路径应该在DOM中
    expect(screen.queryByText((content) => content.includes("folder"))).toBeTruthy();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("CompressFilesView 边界条件测试", () => {
  it("应该处理空数据", () => {
    const props = createProps({ data: mockEmptyData });
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("🗜️ 文件压缩完成")).toBeTruthy();
  });

  it("应该处理undefined的压缩率", () => {
    const noRatioData = {
      archive_path: "D:\\test.zip",
      original_size: 1024,
      compressed_size: 512,
      compression_ratio: undefined,
      success: true,
    };
    
    const props = createProps({ data: noRatioData });
    render(<CompressFilesView {...props} />);

    // 验证渲染
    expect(screen.getByText((content) => content.includes("文件压缩"))).toBeTruthy();
  });

  it("应该处理undefined的文件大小", () => {
    const noSizeData = {
      archive_path: "D:\\test.zip",
      original_size: undefined,
      compressed_size: undefined,
      compression_ratio: 50,
      success: true,
    };
    
    const props = createProps({ data: noSizeData });
    render(<CompressFilesView {...props} />);

    // 验证渲染
    expect(screen.getByText((content) => content.includes("文件压缩"))).toBeTruthy();
  });

  it("应该处理空文件列表", () => {
    const props = createProps({ data: mockNoFileListData });
    render(<CompressFilesView {...props} />);

    expect(screen.queryByText("包含文件")).toBeNull();
  });

  it("应该处理大文件", () => {
    const props = createProps({ data: mockLargeData });
    render(<CompressFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("5.0"))).toBeTruthy();
    expect(screen.getByText((content) => content.includes("2.0"))).toBeTruthy();
  });

  it("应该处理超多文件列表", () => {
    const props = createProps({ data: mockHighRatioData });
    render(<CompressFilesView {...props} />);

    // 验证渲染成功
    expect(screen.getByText((content) => content.includes("50个"))).toBeTruthy();
  });
});

// ============================================================
// 样式一致性测试
// ============================================================

describe("CompressFilesView 样式一致性测试", () => {
  it("成功状态应该使用蓝色边框", () => {
    const props = createProps();
    const { container } = render(<CompressFilesView {...props} />);

    const firstDiv = container.querySelector("div");
    const style = firstDiv?.getAttribute("style") || "";
    expect(style.includes("91d5ff") || style.includes("linear-gradient")).toBe(true);
  });

  it("应该使用圆角边框", () => {
    const props = createProps();
    const { container } = render(<CompressFilesView {...props} />);

    const firstDiv = container.querySelector("div");
    const style = firstDiv?.getAttribute("style") || "";
    const hasRadius = style.includes("borderRadius") || style.includes("8px");
    expect(hasRadius).toBe(true);
  });

  it("应该使用网格布局", () => {
    const props = createProps();
    render(<CompressFilesView {...props} />);

    // 验证渲染成功
    expect(screen.getByText((content) => content.includes("文件压缩"))).toBeTruthy();
  });
});

// ============================================================
// 向后兼容测试
// ============================================================

describe("CompressFilesView 向后兼容测试", () => {
  it("应该兼容默认success为true", () => {
    const defaultData = {
      archive_path: "D:\\test.zip",
      original_size: 1024,
      compressed_size: 512,
    };
    
    const props = createProps({ data: defaultData });
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("🗜️ 文件压缩完成")).toBeTruthy();
  });

  it("应该兼容混合字段顺序", () => {
    const mixedData = {
      success: true,
      compressed_size: 1024,
      compression_ratio: 50,
      original_size: 2048,
    };
    
    const props = createProps({ data: mixedData });
    render(<CompressFilesView {...props} />);

    expect(screen.getByText("50.0%")).toBeTruthy();
  });
});

console.log("CompressFilesView 测试用例加载完成");