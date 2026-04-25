/**
 * GetFileInfoView 测试用例
 * 
 * 【小资编写 2026-04-25】
 * 根据设计文档第3.1.3节要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-25
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import GetFileInfoView from "../../components/Chat/views/GetFileInfoView";

// ============================================================
// 测试数据
// ============================================================

// 完整文件数据
const mockFileData = {
  name: "document.txt",
  path: "D:\\项目\\文档\\document.txt",
  size: 5090,
  created_at: "2026-04-01 10:00:00",
  modified_at: "2026-04-25 14:30:00",
  permissions: "644",
  type: "txt",
  is_directory: false,
};

// 目录数据
const mockDirectoryData = {
  name: "项目文件夹",
  path: "D:\\项目\\文档",
  size: 0,
  created_at: "2026-04-01 09:00:00",
  modified_at: "2026-04-25 12:00:00",
  permissions: "755",
  type: "",
  is_directory: true,
};

// 错误数据
const mockErrorData = {
  name: "missing.txt",
  path: "D:\\项目\\missing.txt",
  error_message: "文件不存在",
};

// 空数据
const mockEmptyData = {};

// 无扩展名数据
const mockNoExtensionData = {
  name: "README",
  path: "D:\\项目\\README",
  size: 2048,
  created_at: "2026-04-20 08:00:00",
  modified_at: "2026-04-25 16:00:00",
  permissions: "600",
  type: "",
  is_directory: false,
};

// 大文件数据
const mockLargeFileData = {
  name: "movie.mp4",
  path: "D:\\项目\\movie.mp4",
  size: 1024 * 1024 * 1024 * 2, // 2GB
  created_at: "2026-04-01 10:00:00",
  modified_at: "2026-04-25 14:30:00",
  permissions: "644",
  type: "mp4",
  is_directory: false,
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 GetFileInfoView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockFileData,
    ...overrides,
  };
}

// ============================================================
// 基本渲染测试（对应设计文档3.1.3）
// ============================================================

describe("GetFileInfoView 基本渲染测试", () => {
  it("应该渲染文件信息标题", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("📄 文件信息")).toBeTruthy();
  });

  it("应该渲染文件名", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("document.txt")).toBeTruthy();
  });

  it("应该渲染文件路径", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("D:\\项目\\文档\\document.txt")
    )).toBeTruthy();
  });

  it("应该渲染文件大小", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    // 5090 bytes = 5.0 KB
    expect(screen.getByText((content) => content.includes("5.0"))).toBeTruthy();
  });

  it("应该渲染文件类型", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText((content) => content.includes(".txt"))).toBeTruthy();
  });

  it("应该渲染权限", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("644")).toBeTruthy();
  });
});

// ============================================================
// 目录显示测试（对应设计文档3.1.3 UI设计）
// ============================================================

describe("GetFileInfoView 目录显示测试", () => {
  it("应该显示目录图标", () => {
    const props = createProps({ data: mockDirectoryData });
    render(<GetFileInfoView {...props} />);

    // 目录应该显示目录图标和类型
    expect(screen.getByText("📂 文件信息")).toBeTruthy();
    expect(screen.getByText("目录")).toBeTruthy();
  });

  it("目录不应该显示文件类型扩展名", () => {
    const props = createProps({ data: mockDirectoryData });
    render(<GetFileInfoView {...props} />);
    const content = screen.queryByText((content) => content.includes("("));
    expect(content).toBeNull();
  });

  it("目录应该显示为0字节", () => {
    const props = createProps({ data: mockDirectoryData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("0 B")).toBeTruthy();
  });
});

// ============================================================
// 创建/修改时间测试
// ============================================================

describe("GetFileInfoView 时间信息测试", () => {
  it("应该渲染创建时间", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("📝 名称：")).toBeTruthy();
    expect(screen.getByText("2026-04-01 10:00:00")).toBeTruthy();
  });

  it("应该渲染修改时间", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("📂 路径：")).toBeTruthy();
    expect(screen.getByText("2026-04-25 14:30:00")).toBeTruthy();
  });
});

// ============================================================
// 错误状态测试（对应设计文档3.1.3 样式规范）
// ============================================================

describe("GetFileInfoView 错误状态测试", () => {
  it("应该显示错误状态标题", () => {
    const props = createProps({ data: mockErrorData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("📄 文件信息")).toBeTruthy();
  });

  it("应该显示错误信息", () => {
    const props = createProps({ data: mockErrorData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("文件不存在")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("错误信息："))).toBeTruthy();
  });

  it("错误状态应该使用红色边框", () => {
    const props = createProps({ data: mockErrorData });
    const { container } = render(<GetFileInfoView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasRedBorder = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("ffa39e")) hasRedBorder = true;
    });
    expect(hasRedBorder).toBe(true);
  });
});

// ============================================================
// 文件大小格式化测试
// ============================================================

describe("GetFileInfoView 文件大小格式化测试", () => {
  it("应该正确格式化字节", () => {
    const smallData = { ...mockFileData, size: 512 };
    const props = createProps({ data: smallData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("512 B")).toBeTruthy();
  });

  it("应��正确格式化KB", () => {
    const props = createProps();
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("5.0 KB")).toBeTruthy();
  });

  it("应该正确格式化MB", () => {
    const mbData = { ...mockFileData, size: 1024 * 1024 * 2.5 };
    const props = createProps({ data: mbData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("2.5 MB")).toBeTruthy();
  });

  it("应该正确格式化GB", () => {
    const props = createProps({ data: mockLargeFileData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("2.0 GB")).toBeTruthy();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("GetFileInfoView 边界条件测试", () => {
  it("应该处理空数据", () => {
    const props = createProps({ data: mockEmptyData });
    render(<GetFileInfoView {...props} />);

    // 空数据时基本元素应显示
    expect(screen.getByText("📄 文件信息")).toBeTruthy();
  });

  it("应该处理undefined的大小", () => {
    const noSizeData = { ...mockFileData, size: undefined };
    const props = createProps({ data: noSizeData });
    render(<GetFileInfoView {...props} />);

    expect(screen.queryByText("📊 大小：")).toBeNull();
  });

  it("应该处理无扩展名文件", () => {
    const props = createProps({ data: mockNoExtensionData });
    render(<GetFileInfoView {...props} />);

    // 无扩展名时只显示"文件"类型
    expect(screen.getByText("文件")).toBeTruthy();
    expect(screen.queryByText(".txt")).toBeNull();
  });

  it("应该处理超长路径", () => {
    const longPathData = {
      name: "file.txt",
      path: "D:\\非常深的目录\\非常深的子目录\\甚至更深的目录\\最终目录\\超长文件名.txt",
      size: 1024,
    };
    
    const props = createProps({ data: longPathData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("超长文件名.txt")
    )).toBeTruthy();
  });
});

// ============================================================
// 网格布局测试（对应设计文档3.1.3 样式规范）
// ============================================================

describe("GetFileInfoView 网格布局测试", () => {
  it("应该使用两列网格布局", () => {
    const props = createProps();
    const { container } = render(<GetFileInfoView {...props} />);

    // 检查是否有网格样式
    const divs = container.querySelectorAll("div");
    let hasGrid = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("grid")) hasGrid = true;
    });
    expect(hasGrid).toBe(true);
  });
});

// ============================================================
// 向后兼容测试
// ============================================================

describe("GetFileInfoView 向后兼容测试", () => {
  it("应该兼容默认is_directory为false", () => {
    const noDirData = {
      name: "file.txt",
      path: "D:\\test\\file.txt",
      size: 1024,
    };
    
    const props = createProps({ data: noDirData });
    render(<GetFileInfoView {...props} />);

    // 默认应显示文件图标
    expect(screen.getByText("📄 文件信息")).toBeTruthy();
  });

  it("应该兼容混合字段顺序", () => {
    const mixedData = {
      path: "D:\\test\\file.txt",
      name: "file.txt",
      size: 2048,
      modified_at: "2026-04-25",
      created_at: "2026-04-01",
      permissions: "600",
      type: "txt",
      is_directory: false,
    };
    
    const props = createProps({ data: mixedData });
    render(<GetFileInfoView {...props} />);

    expect(screen.getByText("📄 文件信息")).toBeTruthy();
  });
});

console.log("GetFileInfoView 测试用例加载完成");