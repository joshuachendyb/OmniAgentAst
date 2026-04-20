import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorDetail from "../../components/Chat/ErrorDetail";

describe("ErrorDetail Component Tests", () => {
  describe("ERROR_COLORS_MAP color mapping", () => {
    it("should render security_error colors", () => {
      render(<ErrorDetail errorType="security_error" errorMessage="test" />);
      expect(screen.getByText("⚠️")).toBeInTheDocument();
      expect(screen.getByText("待确认")).toBeInTheDocument();
    });

    it("should render agent colors", () => {
      render(<ErrorDetail errorType="agent" errorMessage="test" />);
      expect(screen.getByText("🤖")).toBeInTheDocument();
      expect(screen.getByText("Agent错误")).toBeInTheDocument();
    });

    it("should render network colors", () => {
      render(<ErrorDetail errorType="network" errorMessage="test" />);
      expect(screen.getByText("🌐")).toBeInTheDocument();
      expect(screen.getByText("网络错误")).toBeInTheDocument();
    });

    it("should render default colors", () => {
      render(<ErrorDetail errorMessage="test" />);
      expect(screen.getByText("❌")).toBeInTheDocument();
      expect(screen.getByText("错误详情")).toBeInTheDocument();
    });
  });

  describe("ERROR_TYPE_LABELS mapping", () => {
    it("should render empty_response label", () => {
      render(<ErrorDetail errorType="empty_response" errorMessage="test" />);
      expect(screen.getByText("空响应")).toBeInTheDocument();
    });

    it("should render timeout label", () => {
      render(<ErrorDetail errorType="timeout" errorMessage="test" />);
      expect(screen.getByText("请求超时")).toBeInTheDocument();
    });

    it("should render unknown type", () => {
      render(<ErrorDetail errorType="custom_error" errorMessage="test" />);
      expect(screen.getByText("custom_error")).toBeInTheDocument();
    });
  });

  describe("11 fields display", () => {
    it("should display errorType field", () => {
      render(<ErrorDetail errorType="network" errorMessage="test" />);
      expect(screen.getByText("类型:")).toBeInTheDocument();
    });

    it("should display errorMessage field", () => {
      render(<ErrorDetail errorType="network" errorMessage="error message" />);
      expect(screen.getByText("error message")).toBeInTheDocument();
    });

    it("should display errorTimestamp field", () => {
      render(
        <ErrorDetail
          errorType="network"
          errorMessage="test"
          errorTimestamp="2026-04-20T10:00:00Z"
        />
      );
      expect(screen.getByText(/2026/)).toBeInTheDocument();
    });

    it("should display errorDetails field", () => {
      render(
        <ErrorDetail errorType="network" errorMessage="test" errorDetails="details content" />
      );
      expect(screen.getByText("详情:")).toBeInTheDocument();
    });

    it("should display errorStack field", () => {
      render(
        <ErrorDetail
          errorType="network"
          errorMessage="test"
          errorStack="Error at line 1"
        />
      );
      expect(screen.getByText("查看堆栈信息")).toBeInTheDocument();
    });

    it("should display errorRetryAfter field", () => {
      render(
        <ErrorDetail
          errorType="network"
          errorMessage="test"
          errorRecoverable={true}
          errorRetryAfter={30}
        />
      );
      expect(screen.getByText(/30秒后/)).toBeInTheDocument();
    });

    it("should display model and provider", () => {
      render(
        <ErrorDetail
          errorType="network"
          errorMessage="test"
          model="gpt-4"
          provider="OpenAI"
        />
      );
      expect(screen.getByText(/OpenAI/)).toBeInTheDocument();
    });

    it("should display errorRecoverable field", () => {
      render(
        <ErrorDetail errorType="network" errorMessage="test" errorRecoverable={true} />
      );
      expect(screen.getByText("可恢复:")).toBeInTheDocument();
      expect(screen.getByText("是")).toBeInTheDocument();
    });

    it("should display errorContext field", () => {
      render(
        <ErrorDetail
          errorType="network"
          errorMessage="test"
          errorContext={{ step: 1, model: "gpt-4" }}
        />
      );
      expect(screen.getByText("上下文:")).toBeInTheDocument();
      expect(screen.getByText("步骤: 1")).toBeInTheDocument();
    });
  });

  describe("React.memo optimization", () => {
    it("should re-render when props change", () => {
      const { rerender } = render(
        <ErrorDetail errorType="network" errorMessage="test" />
      );
      expect(screen.getByText("网络错误")).toBeInTheDocument();
      rerender(<ErrorDetail errorType="agent" errorMessage="test" />);
      expect(screen.getByText("Agent错误")).toBeInTheDocument();
    });
  });

  describe("edge cases", () => {
    it("should handle undefined props", () => {
      render(<ErrorDetail />);
      expect(screen.getByText("错误详情")).toBeInTheDocument();
    });

    it("should handle empty strings", () => {
      render(<ErrorDetail errorType="" errorMessage="" />);
      expect(screen.getByText("错误详情")).toBeInTheDocument();
    });
  });
});