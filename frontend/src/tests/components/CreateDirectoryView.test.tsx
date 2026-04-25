/**
 * CreateDirectoryView 测试用例
 * 
 * 【小资编写 2026-04-25】
 * 根据设计文档第3.1.2节要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-25
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import CreateDirectoryView from "../../components/Chat/views/CreateDirectoryView";

// ============================================================
// 测试数据
// ============================================================

// 成功数据 - 完整字段
const mockSuccessData = {
  directory_path: "D:\\项目\\new_folder",
  success: true,
  permissions: "755",
  created_at: "2026-04-25 10:30:00",
};

// 成功数据 - 无可选字段
const mockSuccessMinimal = {
  directory_path: "D:\\test\\new_folder",
  success: true,
};

// 失败数据
const mockFailedData = {
  directory_path: "D:\\项目\\new_folder",
  success: false,
  error_message: "权限不足，无法创建目录",
};

// 空数据
const mockEmptyData = {};

// 特殊权限数据
const mockSpecialPermissionsData = {
  directory_path: "D:\\test\\secure_folder",
  success: true,
  permissions: "700",
  created_at: "2026-04-25 15:45:30",
};

// 嵌套目录数据
const mockNestedData = {
  directory_path: "D:\\项目\\a\\b\\c\\deep\\nested\\folder",
  success: true,
  permissions: "755",
  created_at: "2026-04-25 09:00:00",
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 CreateDirectoryView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockSuccessData,
    ...overrides,
  };
}

// ============================================================
// 基本渲染测试（对应设计文档3.1.2）
// ============================================================

describe("CreateDirectoryView 基本渲染测试", () => {
  it("应该渲染成功状态标题", () => {
    const props = createProps();
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("📁 目录创建成功")).toBeTruthy();
  });

  it("应该渲染目录路径", () => {
    const props = createProps();
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("D:\\项目\\new_folder")
    )).toBeTruthy();
  });

  it("应该渲染权限信息", () => {
    const props = createProps();
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("📊 权限：")).toBeTruthy();
    expect(screen.getByText("755")).toBeTruthy();
  });

  it("应该渲染创建时间", () => {
    const props = createProps();
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("📅 创建时间：")).toBeTruthy();
    expect(screen.getByText("2026-04-25 10:30:00")).toBeTruthy();
  });
});

// ============================================================
// 成功状态测试（对应设计文档3.1.2 UI设计）
// ============================================================

describe("CreateDirectoryView 成功状态测试", () => {
  it("应该显示成功的渐变背景", () => {
    const props = createProps();
    const { container } = render(<CreateDirectoryView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasBlueGradient = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("e6f7ff")) hasBlueGradient = true;
    });
    expect(hasBlueGradient).toBe(true);
  });

  it("应该显示目录图标", () => {
    const props = createProps();
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("📂 目录路径：")).toBeTruthy();
  });

  it("应该正确显示权限值", () => {
    const props = createProps();
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("755")).toBeTruthy();
  });

  it("应该显示文件夹图标", () => {
    const props = createProps();
    render(<CreateDirectoryView {...props} />);

    // 应该有橙色文件夹图标
    const folderIcon = screen.getAllByText((content) => 
      content.includes("📂")
    );
    expect(folderIcon.length).toBeGreaterThan(0);
  });
});

// ============================================================
// 失败状态测试（对应设计文档3.1.2 样式规范）
// ============================================================

describe("CreateDirectoryView 失败状态测试", () => {
  it("应该显示失败状态标题", () => {
    const props = createProps({ data: mockFailedData });
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("❌ 目录创建失败")).toBeTruthy();
  });

  it("应该显示失败渐变背景", () => {
    const props = createProps({ data: mockFailedData });
    const { container } = render(<CreateDirectoryView {...props} />);

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
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("权限不足，无法创建目录")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("错误信息："))).toBeTruthy();
  });

  it("失败时不应显示创建时间和权限", () => {
    const props = createProps({ data: mockFailedData });
    render(<CreateDirectoryView {...props} />);

    expect(screen.queryByText("📊 权限：")).toBeNull();
    expect(screen.queryByText("📅 创建时间：")).toBeNull();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("CreateDirectoryView 边界条件测试", () => {
  it("应该处理空数据", () => {
    const props = createProps({ data: mockEmptyData });
    render(<CreateDirectoryView {...props} />);

    // 空数据时显示空路径
    expect(screen.getByText("📂 目录路径：")).toBeTruthy();
  });

  it("应该处理undefined的权限", () => {
    const props = createProps({
      data: {
        directory_path: "D:\\test\\folder",
        success: true,
        permissions: undefined,
      }
    });
    render(<CreateDirectoryView {...props} />);

    // 使用默认值755
    expect(screen.getByText("755")).toBeTruthy();
  });

  it("应该处理undefined的创建时间", () => {
    const props = createProps({
      data: {
        directory_path: "D:\\test\\folder",
        success: true,
        created_at: undefined,
      }
    });
    render(<CreateDirectoryView {...props} />);

    expect(screen.queryByText("📅 创建时间：")).toBeNull();
  });

  it("应��处理超长路径", () => {
    const longPathData = {
      directory_path: "D:\\非常深的目录\\非常深的子目录\\甚至更深的目录\\最终目录\\嵌套文件夹",
      success: true,
      permissions: "755",
    };
    
    const props = createProps({ data: longPathData });
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("嵌套文件夹")
    )).toBeTruthy();
  });

  it("应该处理根目录路径", () => {
    const rootPathData = {
      directory_path: "D:\\root_folder",
      success: true,
      permissions: "755",
    };
    
    const props = createProps({ data: rootPathData });
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("D:\\root_folder")
    )).toBeTruthy();
  });

  it("应该处理特殊权限值", () => {
    const props = createProps({ data: mockSpecialPermissionsData });
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("700")).toBeTruthy();
  });

  it("应该处理嵌套目录", () => {
    const props = createProps({ data: mockNestedData });
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText((content) => 
      content.includes("deep")
    )).toBeTruthy();
  });
});

// ============================================================
// 样式一致性测试（对应设计文档3.1.2 视觉约束）
// ============================================================

describe("CreateDirectoryView 样式一致性测试", () => {
  it("成功状态应该使用蓝色边框", () => {
    const props = createProps();
    const { container } = render(<CreateDirectoryView {...props} />);

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
    const { container } = render(<CreateDirectoryView {...props} />);

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
    const { container } = render(<CreateDirectoryView {...props} />);

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

describe("CreateDirectoryView 向后兼容测试", () => {
  it("应该兼容默认success为true", () => {
    const props = createProps({
      data: {
        directory_path: "D:\\test\\folder",
      }
    });
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("📁 目录创建成功")).toBeTruthy();
  });

  it("应该兼容混合字段顺序", () => {
    const mixedData = {
      success: true,
      created_at: "2026-04-25 12:00:00",
      directory_path: "D:\\mixed\\folder",
      permissions: "644",
    };
    
    const props = createProps({ data: mixedData });
    render(<CreateDirectoryView {...props} />);

    expect(screen.getByText("📁 目录创建成功")).toBeTruthy();
    expect(screen.getByText("644")).toBeTruthy();
  });
});

console.log("CreateDirectoryView 测试用例加载完成");