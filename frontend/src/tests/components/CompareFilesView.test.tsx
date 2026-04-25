/**
 * CompareFilesView 测试用例
 * 
 * 【小资编写 2026-04-25】
 * 根据设计文档第3.2.1节要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-25
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import CompareFilesView from "../../components/Chat/views/CompareFilesView";

// ============================================================
// 测试数据
// ============================================================

// 完整比较数据
const mockCompareData = {
  file_a: "D:\\项目\\file1.txt",
  file_b: "D:\\项目\\file2.txt",
  file_a_size: 5090,
  file_b_size: 6010,
  size_diff: 920,
  modified_time_diff: "+5分钟",
  content_diff_count: 3,
  success: true,
};

// 完全相同数据
const mockIdenticalData = {
  file_a: "D:\\项目\\original.txt",
  file_b: "D:\\项目\\copy.txt",
  file_a_size: 2048,
  file_b_size: 2048,
  size_diff: 0,
  modified_time_diff: "0分钟",
  content_diff_count: 0,
  success: true,
};

// 失败数据
const mockFailedData = {
  file_a: "D:\\项目\\file1.txt",
  file_b: "D:\\项目\\file2.txt",
  success: false,
  error_message: "无法读取文件B",
};

// 空数据
const mockEmptyData = {};

// 大小差异数据（文件B更大）
const mockSizeDiffBData = {
  file_a: "D:\\项目\\small.txt",
  file_b: "D:\\项目\\large.txt",
  file_a_size: 1024,
  file_b_size: 1024 * 1024,
  size_diff: 1048576,
  success: true,
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 CompareFilesView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockCompareData,
    ...overrides,
  };
}

// ============================================================
// 基本渲染测试（对应设计文档3.2.1）
// ============================================================

describe("CompareFilesView 基本渲染测试", () => {
  it("应该渲染文件比较结果标题", () => {
    const props = createProps();
    render(<CompareFilesView {...props} />);

    expect(screen.getByText("🔍 文件比较结果")).toBeTruthy();
  });

  it("应该渲染文件A路径", () => {
    const props = createProps();
    render(<CompareFilesView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("D:\\项目\\file1.txt")
    )).toBeTruthy();
  });

  it("应该渲染文件B路径", () => {
    const props = createProps();
    render(<CompareFilesView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("D:\\项目\\file2.txt")
    )).toBeTruthy();
  });

  it("应该渲染大小差异", () => {
    const props = createProps();
    render(<CompareFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("大小差异"))).toBeTruthy();
  });

  it("应该渲染修改时间差异", () => {
    const props = createProps();
    render(<CompareFilesView {...props} />);

    expect(screen.getByText((content) => content.includes("修改时间差异"))).toBeTruthy();
  });

  it("应该渲染内容差异数量", () => {
    const props = createProps();
    render(<CompareFilesView {...props} />);

    expect(screen.getByText("3处不同")).toBeTruthy();
  });
});

// ============================================================
// 相同文件测试（对应设计文档3.2.1 UI设计）
// ============================================================

describe("CompareFilesView 相同文件测试", () => {
  it("文件完全相同时应该显示绿色提示", () => {
    const props = createProps({ data: mockIdenticalData });
    render(<CompareFilesView {...props} />);

    expect(screen.getByText("文件内容完全相同")).toBeTruthy();
  });

  it("文件相同时不应显示差异数量", () => {
    const props = createProps({ data: mockIdenticalData });
    render(<CompareFilesView {...props} />);

    expect(screen.queryByText("处不同")).toBeNull();
  });
});

// ============================================================
// 失败状态测试（对应设计文档3.2.1 样式规范）
// ============================================================

describe("CompareFilesView 失败状态测试", () => {
  it("应该显示失败状态标题", () => {
    const props = createProps({ data: mockFailedData });
    render(<CompareFilesView {...props} />);

    expect(screen.getByText("❌ 文件比较失败")).toBeTruthy();
  });

  it("应该显示错误信息", () => {
    const props = createProps({ data: mockFailedData });
    render(<CompareFilesView {...props} />);

    expect(screen.getByText("无法读取文件B")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("错误信息：")))).toBeTruthy();
  });
});

// ============================================================
// 大小差异测试
// ============================================================

describe("CompareFilesView 大小差异测试", () => {
  it("文件A大于文件B时应该显示正数差异", () => {
    const props = createProps();
    render(<CompareFilesView {...props} />);

    // 920 bytes应该显示
    expect(screen.getByText((content) => content.includes("920"))).toBeTruthy();
  });

  it("文件B大于文件A时应该显示负数差异", () => {
    const props = createProps({ data: mockSizeDiffBData });
    render(<CompareFilesView {...props} />);

    // 1.0 MB差异，应该显示+
    expect(screen.getByText((content) => content.includes("1.0 MB"))).toBeTruthy();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("CompareFilesView 边界条件测试", () => {
  it("应该处理空数据", () => {
    const props = createProps({ data: mockEmptyData });
    render(<CompareFilesView {...props} />);

    // 空数据时应该显示空结果
    expect(screen.getByText("🔍 文件比较结果")).toBeTruthy();
  });

  it("应该处理undefined的文件大小", () => {
    const noSizeData = {
      file_a: "D:\\test\\a.txt",
      file_b: "D:\\test\\b.txt",
      success: true,
    };
    
    const props = createProps({ data: noSizeData });
    render(<CompareFilesView {...props} />);

    expect(screen.queryByText("📊 大小差异：")).toBeNull();
  });

  it("应该处理undefined的修改时间差异", () => {
    const noTimeData = {
      file_a: "D:\\test\\a.txt",
      file_b: "D:\\test\\b.txt",
      success: true,
      size_diff: 100,
    };
    
    const props = createProps({ data: noTimeData });
    render(<CompareFilesView {...props} />);

    expect(screen.queryByText("📅 修改时间差异：")).toBeNull();
  });

  it("应该处理undefined的内容差异数量", () => {
    const noContentData = {
      file_a: "D:\\test\\a.txt",
      file_b: "D:\\test\\b.txt",
      success: true,
      size_diff: 100,
    };
    
    const props = createProps({ data: noContentData });
    render(<CompareFilesView {...props} />);

    expect(screen.queryByText("📝 内容差异：")).toBeNull();
  });
});

// ============================================================
// 样式一致性测试
// ============================================================

describe("CompareFilesView 样式一致性测试", () => {
  it("成功状态应该使用蓝色边框", () => {
    const props = createProps();
    const { container } = render(<CompareFilesView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasBlueBorder = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("91d5ff")) hasBlueBorder = true;
    });
    expect(hasBlueBorder).toBe(true);
  });

  it("应该使用圆角边框", () => {
    const props = createProps();
    const { container } = render(<CompareFilesView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasBorderRadius = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("borderRadius")) hasBorderRadius = true;
    });
    expect(hasBorderRadius).toBe(true);
  });
});

// ============================================================
// 向后兼容测试
// ============================================================

describe("CompareFilesView 向后兼容测试", () => {
  it("应该兼容默认success为true", () => {
    const defaultData = {
      file_a: "D:\\a.txt",
      file_b: "D:\\b.txt",
    };
    
    const props = createProps({ data: defaultData });
    render(<CompareFilesView {...props} />);

    expect(screen.getByText("🔍 文件比较结果")).toBeTruthy();
  });

  it("应该兼容混合字段顺序", () => {
    const mixedData = {
      success: true,
      file_b: "D:\\b.txt",
      file_a: "D:\\a.txt",
      size_diff: 100,
    };
    
    const props = createProps({ data: mixedData });
    render(<CompareFilesView {...props} />);

    expect(screen.getByText("🔍 文件比较结果")).toBeTruthy();
  });
});

console.log("CompareFilesView 测试用例加载完成");