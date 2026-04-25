/**
 * CopyFileView 测试用例
 * 
 * 【小资编写 2026-04-25】
 * 根据设计文档第3.1.1节要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-25
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import CopyFileView from "../../components/Chat/views/CopyFileView";

// ============================================================
// 测试数据
// ============================================================

// 成功数据 - 完整字段
const mockSuccessData = {
  source_path: "D:\\项目\\source\\file.txt",
  destination_path: "D:\\项目\\dest\\file.txt",
  success: true,
  file_size: 5090,
  elapsed_time: 0.523,
};

// 成功数据 - 无可选字段
const mockSuccessMinimal = {
  source_path: "D:\\test\\source.txt",
  destination_path: "D:\\test\\dest.txt",
  success: true,
};

// 失败数据
const mockFailedData = {
  source_path: "D:\\项目\\source\\file.txt",
  destination_path: "D:\\项目\\dest\\file.txt",
  success: false,
  error_message: "目标文件已存在",
};

// 空数据
const mockEmptyData = {};

// 超大文件数据
const mockLargeFileData = {
  source_path: "D:\\项目\\large\\movie.mp4",
  destination_path: "D:\\项目\\dest\\movie.mp4",
  success: true,
  file_size: 1024 * 1024 * 1024 * 5, // 5GB
  elapsed_time: 15.75,
};

// 小文件数据
const mockSmallFileData = {
  source_path: "D:\\项目\\small\\config.json",
  destination_path: "D:\\项目\\dest\\config.json",
  success: true,
  file_size: 512,
  elapsed_time: 0.012,
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 CopyFileView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockSuccessData,
    ...overrides,
  };
}

// ============================================================
// 基本渲染测试（对应设计文档3.1.1）
// ============================================================

describe("CopyFileView 基本渲染测试", () => {
  it("应该渲染成功状态标题", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    expect(screen.getByText("📋 文件复制成功")).toBeTruthy();
  });

  it("应该渲染源文件路径", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("D:\\项目\\source\\file.txt")
    )).toBeTruthy();
  });

  it("应该渲染目标文件路径", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("D:\\项目\\dest\\file.txt")
    )).toBeTruthy();
  });

  it("应该渲染文件大小", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    // 5090 bytes = 5.0 KB
    expect(screen.getByText((content) => content.includes("5.0"))).toBeTruthy();
  });

  it("应该渲染复制耗时", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    expect(screen.getByText((content) => content.includes("0.52"))).toBeTruthy();
  });
});

// ============================================================
// 成功状态测试（对应设计文档3.1.1 UI设计）
// ============================================================

describe("CopyFileView 成功状态测试", () => {
  it("应该显示成功的渐变背景", () => {
    const props = createProps();
    const { container } = render(<CopyFileView {...props} />);

    // 检查是否有绿色渐变背景
    const divs = container.querySelectorAll("div");
    let hasGradient = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("f6ffed")) hasGradient = true;
    });
    expect(hasGradient).toBe(true);
  });

  it("应该显示成功图标", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    // 成功时应该显示文件复制成功标题
    expect(screen.getByText("📋 文件复制成功")).toBeTruthy();
  });

  it("应该显示文件图标和路径标签", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    expect(screen.getByText("📄 源文件：")).toBeTruthy();
    expect(screen.getByText("📄 目标文件：")).toBeTruthy();
  });

  it("应该显示文件大小标签", () => {
    const props = createProps({ data: mockSuccessData });
    render(<CopyFileView {...props} />);

    expect(screen.getByText("📊 文件大小：")).toBeTruthy();
  });

  it("应该显示复制耗时标签", () => {
    const props = createProps({ data: mockSuccessData });
    render(<CopyFileView {...props} />);

    expect(screen.getByText("⏱️ 复制耗时：")).toBeTruthy();
  });
});

// ============================================================
// 失败状态测试（对应设计文档3.1.1 样式规范）
// ============================================================

describe("CopyFileView 失败状态测试", () => {
  it("应该显示失败状态标题", () => {
    const props = createProps({ data: mockFailedData });
    render(<CopyFileView {...props} />);

    expect(screen.getByText("❌ 文件复制失败")).toBeTruthy();
  });

  it("应该显示失败渐变背景", () => {
    const props = createProps({ data: mockFailedData });
    const { container } = render(<CopyFileView {...props} />);

    // 检查是否有红色渐变背景
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
    render(<CopyFileView {...props} />);

    expect(screen.getByText("目标文件已存在")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("错误信息："))).toBeTruthy();
  });

  it("失败时不应显示文件大小和耗时", () => {
    const props = createProps({ data: mockFailedData });
    render(<CopyFileView {...props} />);

    expect(screen.queryByText("📊 文件大小：")).toBeNull();
    expect(screen.queryByText("⏱️ 复制耗时：")).toBeNull();
  });
});

// ============================================================
// 文件大小格式化测试（对应设计文档格式规范）
// ============================================================

describe("CopyFileView 文件大小格式化测试", () => {
  it("应该正确格式化字节", () => {
    const props = createProps({ data: mockSmallFileData });
    render(<CopyFileView {...props} />);

    expect(screen.getByText("512 B")).toBeTruthy();
  });

  it("应该正确格式化KB", () => {
    const props = createProps();
    render(<CopyFileView {...props} />);

    expect(screen.getByText("5.0 KB")).toBeTruthy();
  });

  it("应该正确格式化MB", () => {
    const props = createProps({ 
      data: {
        ...mockSuccessData,
        file_size: 1024 * 1024 * 2.5, // 2.5 MB
      }
    });
    render(<CopyFileView {...props} />);

    expect(screen.getByText("2.5 MB")).toBeTruthy();
  });

  it("应该正确格式化GB", () => {
    const props = createProps({ data: mockLargeFileData });
    render(<CopyFileView {...props} />);

    expect(screen.getByText("5.0 GB")).toBeTruthy();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("CopyFileView 边界条件测试", () => {
  it("应该处理空数据", () => {
    const props = createProps({ data: mockEmptyData });
    render(<CopyFileView {...props} />);

    // 空数据时显示空路径
    const emptyPathElements = screen.getAllByText("");
    expect(emptyPathElements.length).toBeGreaterThan(0);
  });

  it("应该处理undefined的文件大小", () => {
    const props = createProps({
      data: {
        source_path: "D:\\test\\file.txt",
        destination_path: "D:\\test\\dest.txt",
        success: true,
        file_size: undefined,
      }
    });
    render(<CopyFileView {...props} />);

    // 不显示文件大小标签
    expect(screen.queryByText("📊 文件大小：")).toBeNull();
  });

  it("应该处理undefined的耗时", () => {
    const props = createProps({
      data: {
        source_path: "D:\\test\\file.txt",
        destination_path: "D:\\test\\dest.txt",
        success: true,
        elapsed_time: undefined,
      }
    });
    render(<CopyFileView {...props} />);

    // 不显示复制耗时标签
    expect(screen.queryByText("⏱️ 复制耗时：")).toBeNull();
  });

  it("应该处理超长路径", () => {
    const longPathData = {
      source_path: "D:\\非常深的目录\\非常深的子目录\\甚至更深的目录\\最终目录\\超长文件名.txt",
      destination_path: "D:\\另一个非常深的目录\\非常深的子目录\\甚至更深的目录\\最终目录\\复制文件.txt",
      success: true,
      file_size: 1024,
    };
    
    const props = createProps({ data: longPathData });
    render(<CopyFileView {...props} />);

    // 检查超长路径是否被渲染
    expect(screen.getByText((content) => 
      content.includes("超长文件名.txt")
    )).toBeTruthy();
  });

  it("应该处理极速复制（<0.01秒）", () => {
    const props = createProps({
      data: {
        ...mockSuccessData,
        elapsed_time: 0.003,
      }
    });
    render(<CopyFileView {...props} />);

    expect(screen.getByText((content) => content.includes("0.00"))).toBeTruthy();
  });
});

// ============================================================
// 样式一致性测试（对应设计文档3.1.1 视觉约束）
// ============================================================

describe("CopyFileView 样式一致性测试", () => {
  it("成功状态应该使用绿色边框", () => {
    const props = createProps();
    const { container } = render(<CopyFileView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasGreenBorder = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("b7eb8f")) hasGreenBorder = true;
    });
    expect(hasGreenBorder).toBe(true);
  });

  it("应该使用圆角���框", () => {
    const props = createProps();
    const { container } = render(<CopyFileView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasBorderRadius = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("borderRadius")) hasBorderRadius = true;
    });
    expect(hasBorderRadius).toBe(true);
  });

  it("应该使用正确的内边距", () => {
    const props = createProps();
    const { container } = render(<CopyFileView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasPadding = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("padding")) hasPadding = true;
    });
    expect(hasPadding).toBe(true);
  });
});

// ============================================================
// 向后兼容测试
// ============================================================

describe("CopyFileView 向后兼容测试", () => {
  it("应该兼容默认success为true", () => {
    const props = createProps({
      data: {
        source_path: "D:\\test\\file.txt",
        destination_path: "D:\\test\\dest.txt",
      }
    });
    render(<CopyFileView {...props} />);

    // 默认应该显示成功状态
    expect(screen.getByText("📋 文件复制成功")).toBeTruthy();
  });

  it("应该兼容混合字段顺序", () => {
    const mixedData = {
      success: true,
      file_size: 1024,
      source_path: "D:\\test.txt",
      destination_path: "D:\\test_copy.txt",
      elapsed_time: 0.1,
    };
    
    const props = createProps({ data: mixedData });
    render(<CopyFileView {...props} />);

    expect(screen.getByText("📋 文件复制成功")).toBeTruthy();
    expect(screen.getByText("1.0 KB")).toBeTruthy();
  });
});

console.log("CopyFileView 测试用例加载完成");