/**
 * BatchRenameView 测试用例
 * 
 * 【小资编写 2026-04-25】
 * 根据设计文档第3.2.2节要求构建测试用例
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-25
 */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import BatchRenameView from "../../components/Chat/views/BatchRenameView";

// ============================================================
// 测试数据
// ============================================================

// 完整数据
const mockCompleteData = {
  total_count: 10,
  success_count: 8,
  skip_count: 1,
  failed_count: 1,
  rename_list: [
    { old_name: "file1.txt", new_name: "document1.txt", success: true },
    { old_name: "file2.txt", new_name: "document2.txt", success: true },
    { old_name: "file3.txt", new_name: "document3.txt", success: false, error_message: "文件已存在" },
    { old_name: "file4.txt", new_name: "document4.txt", success: true },
    { old_name: "file5.txt", new_name: "document5.txt", success: true, error_message: undefined },
  ],
  success: true,
};

// 全部成功数据
const mockAllSuccessData = {
  total_count: 5,
  success_count: 5,
  skip_count: 0,
  failed_count: 0,
  rename_list: [
    { old_name: "a.txt", new_name: "b.txt", success: true },
    { old_name: "c.txt", new_name: "d.txt", success: true },
  ],
  success: true,
};

// 失败数据
const mockFailedData = {
  total_count: 10,
  success_count: 0,
  skip_count: 0,
  failed_count: 10,
  success: false,
  error_message: "权限不足",
};

// 空数据
const mockEmptyData = {};

// 大量数据
const mockManyData = {
  total_count: 100,
  success_count: 95,
  skip_count: 3,
  failed_count: 2,
  rename_list: Array.from({ length: 20 }, (_, i) => ({
    old_name: `file${i}.txt`,
    new_name: `doc${i}.txt`,
    success: i % 2 === 0,
    error_message: i % 2 === 0 ? undefined : "错误",
  }))),
  success: true,
};

// ============================================================
// 辅助函数
// ============================================================

/**
 * 创建 BatchRenameView Props
 */
function createProps(overrides = {}) {
  return {
    data: mockCompleteData,
    ...overrides,
  };
}

// ============================================================
// 基本渲染测试（对应设计文档3.2.2）
// ============================================================

describe("BatchRenameView 基本渲染测试", () => {
  it("应该渲染批量重命名完成标题", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("🔄 批量重命名完成")).toBeTruthy();
  });

  it("应该渲染处理文件总数", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("📊 处理文件：")).toBeTruthy();
    expect(screen.getByText("10个")).toBeTruthy();
  });

  it("应该渲染成功数量", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("成功：")).toBeTruthy();
    expect(screen.getByText("8个")).toBeTruthy();
  });

  it("应该渲染跳过数量", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("跳过：")).toBeTruthy();
    expect(screen.getByText("1个")).toBeTruthy();
  });

  it("应该渲染��败数量", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("失败：")).toBeTruthy();
    expect(screen.getByText("1个")).toBeTruthy();
  });
});

// ============================================================
// 全部成功测试（对应设计文档3.2.2 UI设计）
// ============================================================

describe("BatchRenameView 全部成功测试", () => {
  it("全部成功时应该显示渐变背景", () => {
    const props = createProps({ data: mockAllSuccessData });
    const { container } = render(<BatchRenameView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasGreenGradient = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("f6ffed")) hasGreenGradient = true;
    });
    expect(hasGreenGradient).toBe(true);
  });

  it("应该显示成功图标", () => {
    const props = createProps({ data: mockAllSuccessData });
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("🔄 批量重命名完成")).toBeTruthy();
  });

  it("不应该显示跳过和失败数量（都为0）", () => {
    const props = createProps({ data: mockAllSuccessData });
    render(<BatchRenameView {...props} />);

    expect(screen.queryByText("跳过：")).toBeNull();
    expect(screen.queryByText("失败：")).toBeNull();
  });
});

// ============================================================
// 失败状态测试（对应设计文档3.2.2 样式规范）
// ============================================================

describe("BatchRenameView 失败状态测试", () => {
  it("应该显示失败标题", () => {
    const props = createProps({ data: mockFailedData });
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("❌ 批量重命名失败")).toBeTruthy();
  });

  it("应该显示失败渐变背景", () => {
    const props = createProps({ data: mockFailedData });
    const { container } = render(<BatchRenameView {...props} />);

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
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("权限不足")).toBeTruthy();
    expect(screen.getByText((content) => content.includes("错误信息：")))).toBeTruthy();
  });

  it("失败时不应该显示统计信息", () => {
    const props = createProps({ data: mockFailedData });
    render(<BatchRenameView {...props} />);

    expect(screen.queryByText("📊 处理文件：")).toBeNull();
  });
});

// ============================================================
// 重命名列表测试
// ============================================================

describe("BatchRenameView 重命名列表测试", () => {
  it("应该显示重命名列表折叠面板", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText((content) => content.includes("重命名列表"))).toBeTruthy();
  });

  it("应该显示旧名称到新名称的转换", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("file1.txt")).toBeTruthy();
    expect(screen.getByText("document1.txt")).toBeTruthy();
  });

  it("失败项应该显示错误信息", () => {
    const props = createProps();
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("文件已存在")).toBeTruthy();
  });
});

// ============================================================
// 边界条件测试
// ============================================================

describe("BatchRenameView 边界条件测试", () => {
  it("应该处理空数据", () => {
    const props = createProps({ data: mockEmptyData });
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("🔄 批量重命名完成")).toBeTruthy();
  });

  it("应该处理undefined的跳过数量", () => {
    const noSkipData = {
      total_count: 5,
      success_count: 5,
      failed_count: 0,
      skip_count: undefined,
      success: true,
    };
    
    const props = createProps({ data: noSkipData });
    render(<BatchRenameView {...props} />);

    expect(screen.queryByText("跳过：")).toBeNull();
  });

  it("应该处理undefined的失败数量", () => {
    const noFailData = {
      total_count: 5,
      success_count: 5,
      failed_count: undefined,
      success: true,
    };
    
    const props = createProps({ data: noFailData });
    render(<BatchRenameView {...props} />);

    expect(screen.queryByText("失败：")).toBeNull();
  });

  it("应该处理大量数据", () => {
    const props = createProps({ data: mockManyData });
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("100个")).toBeTruthy();
    expect(screen.getByText("95个")).toBeTruthy();
  });

  it("应该正确统计零值", () => {
    const zeroData = {
      total_count: 0,
      success_count: 0,
      skip_count: 0,
      failed_count: 0,
      success: true,
    };
    
    const props = createProps({ data: zeroData });
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("0个")).toBeTruthy();
  });
});

// ============================================================
// 样式一致性测试
// ============================================================

describe("BatchRenameView 样式一致性测试", () => {
  it("成功状态应该使用绿色边框", () => {
    const props = createProps();
    const { container } = render(<BatchRenameView {...props} />);

    const divs = container.querySelectorAll("div");
    let hasGreenBorder = false;
    divs.forEach((div) => {
      const style = div.getAttribute("style") || "";
      if (style.includes("b7eb8f")) hasGreenBorder = true;
    });
    expect(hasGreenBorder).toBe(true);
  });

  it("应该使用圆角边框", () => {
    const props = createProps();
    const { container } = render(<BatchRenameView {...props} />);

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

describe("BatchRenameView 向后兼容测试", () => {
  it("应该兼容默认success为true", () => {
    const defaultData = {
      total_count: 5,
      success_count: 5,
    };
    
    const props = createProps({ data: defaultData });
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("🔄 批量重命名完成")).toBeTruthy();
  });

  it("应该兼容混合字段顺序", () => {
    const mixedData = {
      success: true,
      failed_count: 1,
      success_count: 4,
      total_count: 5,
    };
    
    const props = createProps({ data: mixedData });
    render(<BatchRenameView {...props} />);

    expect(screen.getByText("5个")).toBeTruthy();
  });
});

console.log("BatchRenameView 测试用例加载完成");