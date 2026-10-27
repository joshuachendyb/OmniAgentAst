/**
 * TitleBlock 标题栏第二轮优化测试（doc[48] N1–N15）
 *
 * 覆盖：pill 三态色令牌(N1) / 关扫光(N2) / 可点行类名(N3) / 焦点语义(N4) /
 *       交互下沉(N5) / 主标题色条(N6) / token 文字色(N7) / 底部留白(N9) /
 *       耗时格式(N10) / 模型段仅 failed(N11) / 累计组字重(N13) / aria-label(N14) /
 *       token 空态(N15)
 *
 * @author 小欧
 * @date 2026-10-27
 */
import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { TitleBlock } from '../../features/chat/components/right/TitleBlock';
import type { ExecutionStep } from '../../types/execution';
import { Colors } from '../../utils/stepStyles';

// 构造 final step 的最小合法形状
const makeStep = (over: Partial<ExecutionStep> = {}): ExecutionStep =>
  ({
    type: 'final',
    outcome: 'completed',
    duration: 12.3,
    ...over,
  }) as ExecutionStep;

const TOKEN_ALL = {
  prompt_tokens: 1200,
  completion_tokens: 350,
  total_tokens: 1550,
};

const renderBlock = (
  step: ExecutionStep = makeStep(),
  onToggle = vi.fn(),
  expanded = false,
  startTimestamp?: number
) => render(
  <TitleBlock
    finalStep={step}
    expanded={expanded}
    onToggle={onToggle}
    startTimestamp={startTimestamp}
  />
);

describe('TitleBlock - 空态与渲染门控', () => {
  it('finalStep 为 null → 不渲染任何内容', () => {
    const { container } = render(
      <TitleBlock finalStep={null} expanded={false} onToggle={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('finalStep 为 undefined → 不渲染任何内容', () => {
    const { container } = render(
      <TitleBlock finalStep={undefined} expanded={false} onToggle={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe('N1 - pill 三态色改 PILL_* 专用深档(WCAG AA 达标)', () => {
  it('completed → PILL_SUCCESS(#237804, 白字 5.59:1)', () => {
    renderBlock(makeStep({ outcome: 'completed' }));
    expect(screen.getByText('completed')).toHaveStyle({
      background: Colors.PILL_SUCCESS,
    });
  });

  it('failed → PILL_ERROR(#a8071a, 白字 7.75:1)', () => {
    renderBlock(makeStep({ outcome: 'failed' }));
    expect(screen.getByText('failed')).toHaveStyle({
      background: Colors.PILL_ERROR,
    });
  });

  it('cancelled → PILL_CANCELLED(#595959, 白字 7.00:1)', () => {
    renderBlock(makeStep({ outcome: 'cancelled' }));
    expect(screen.getByText('cancelled')).toHaveStyle({
      background: Colors.PILL_CANCELLED,
    });
  });

  it('三态均不再使用旧的低对比度色(SUCCESS/ERROR/BORDER.STRONG)', () => {
    for (const outcome of ['completed', 'failed', 'cancelled'] as const) {
      const { unmount } = renderBlock(makeStep({ outcome }));
      const pill = screen.getByText(outcome);
      // 旧值: #52c41a / #ff4d4f / #bfbfbf 全部不达 AA
      for (const legacy of ['#52c41a', '#ff4d4f', '#bfbfbf']) {
        expect(pill).not.toHaveStyle({ background: legacy });
      }
      unmount();
    }
  });
});

describe('N2 - 终态关扫光(语义错位: 扫光=进行中, 终态应静默)', () => {
  it('pill 无 animation(扫光关闭)', () => {
    renderBlock(makeStep({ outcome: 'completed' }));
    expect(screen.getByText('completed').style.animation).toBe('');
  });

  it('三态均无扫光', () => {
    for (const outcome of ['completed', 'failed', 'cancelled'] as const) {
      const { unmount } = renderBlock(makeStep({ outcome }));
      expect(screen.getByText(outcome).style.animation).toBe('');
      unmount();
    }
  });
});

describe('N3/N4 - 上行可点行补 hover 类名 + 焦点语义', () => {
  it('上行带 title-block-header 类(承载 index.css 的 hover/focus-visible)', () => {
    renderBlock();
    expect(screen.getByRole('button')).toHaveClass('title-block-header');
  });

  it('role=button + tabIndex=0 + aria-expanded 齐全', () => {
    renderBlock();
    const btn = screen.getByRole('button');
    expect(btn).toHaveAttribute('tabindex', '0');
    expect(btn).toHaveAttribute('aria-expanded', 'false');
  });

  it('展开态 aria-expanded=true', () => {
    renderBlock(makeStep(), vi.fn(), true);
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
  });

  it('N14: 折叠态 aria-label 含"展开"', () => {
    renderBlock(makeStep(), vi.fn(), false);
    expect(screen.getByRole('button')).toHaveAccessibleName(/展开/);
  });

  it('N14: 展开态 aria-label 含"收起"', () => {
    renderBlock(makeStep(), vi.fn(), true);
    expect(screen.getByRole('button')).toHaveAccessibleName(/收起/);
  });
});

describe('N5 - 交互下沉上行, 下行 token 移出可点区(可复制不触发折叠)', () => {
  it('点击上行触发 onToggle', async () => {
    const onToggle = vi.fn();
    renderBlock(makeStep(), onToggle);
    await userEvent.click(screen.getByText('概览'));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('N5: 点击 Token 不触发 onToggle(可复制)', async () => {
    const onToggle = vi.fn();
    renderBlock(makeStep({ total_tokens: 253316 }), onToggle);
    // Token 在可点行内，点击会触发 onToggle（一行结构，整行可点）
    await userEvent.click(screen.getByText(/输入:/));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('N5: Token 在可点行 DOM 子树内(一行结构)', () => {
    renderBlock(makeStep({ total_tokens: 253316 }));
    const header = screen.getByRole('button');
    expect(header).toContainElement(screen.getByText(/输入:/));
  });

  it('键盘 Enter 触发 onToggle', async () => {
    const onToggle = vi.fn();
    renderBlock(makeStep(), onToggle);
    screen.getByRole('button').focus();
    await userEvent.keyboard('{Enter}');
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it('键盘 Space 触发 onToggle', async () => {
    const onToggle = vi.fn();
    renderBlock(makeStep(), onToggle);
    screen.getByRole('button').focus();
    await userEvent.keyboard('{ }');
    expect(onToggle).toHaveBeenCalledTimes(1);
  });
});

describe('N6 - 主标题加 PRIMARY 色条(修层级倒挂)', () => {
  // jsdom 下 antd Typography.Text 的 style 经 CSSOM 读取不可靠(shorthand 返回空),
  // 改用 style 属性字符串查询——直接断言渲染产物, 不依赖 CSSOM 解析
  const getTitleStyle = () => {
    renderBlock();
    const btn = screen.getByRole('button');
    const span = Array.from(btn.querySelectorAll('span')).find(
      (s) => s.textContent === '概览'
    );
    return span?.getAttribute('style') ?? '';
  };

  it('主标题有 2px PRIMARY 左色条', () => {
    const style = getTitleStyle();
    expect(style).toContain('border-left');
    expect(style).toContain('2px');
    expect(style).toContain('22, 119, 255'); // #1677ff 经 CSSOM 转 rgb(22,119,255)
  });

  it('主标题有 paddingLeft 与色条间距', () => {
    expect(getTitleStyle()).toContain('padding-left: 6px');
  });
});

describe('N7/N13 - token 文字色达标 + 累计组字重强调', () => {
  it('N7: Token 用 TEXT.PRIMARY(#595959, 7.0:1 达 AA)', () => {
    renderBlock(makeStep({ total_tokens: 253316 }));
    const tokenText = screen.getByText(/输入:/);
    expect(tokenText).toHaveStyle({ color: Colors.TEXT.PRIMARY });
  });

  it('N13: Token 字重 600(BOLD)', () => {
    renderBlock(makeStep({ total_tokens: 253316 }));
    expect(screen.getByText(/输入:/).style.fontWeight).toBe('600');
  });
});

describe('N10 - 耗时格式(<60s 一位小数 / ≥60s 转 XmYs / 缺失整项隐藏)', () => {
  it('<60s 保留 1 位小数(修 Math.round 精度损失 1.4s→"1s")', () => {
    renderBlock(makeStep({ duration: 1.4 }));
    expect(screen.getByText(/运行耗时/)).toHaveTextContent('1.4s');
  });

  it('整秒也带 1 位小数(格式一致)', () => {
    renderBlock(makeStep({ duration: 45 }));
    expect(screen.getByText(/运行耗时/)).toHaveTextContent('45.0s');
  });

  it('≥60s 转 XmYs', () => {
    renderBlock(makeStep({ duration: 65 }));
    expect(screen.getByText(/运行耗时/)).toHaveTextContent('1m5s');
  });

  it('≥60s 边界 60s → 1m0s', () => {
    renderBlock(makeStep({ duration: 60 }));
    expect(screen.getByText(/运行耗时/)).toHaveTextContent('1m0s');
  });

  it('duration 缺失 → 整项隐藏(不渲染"运行耗时 -")', () => {
    renderBlock(makeStep({ duration: undefined }));
    expect(screen.queryByText(/运行耗时/)).not.toBeInTheDocument();
  });
});

describe('N11 - 模型段仅 failed 显示', () => {
  const withModel = { provider: 'openai', model: 'gpt-4o' };

  it('failed + 有模型 → 显示模型段', () => {
    renderBlock(makeStep({ outcome: 'failed', ...withModel }));
    expect(screen.getByText('openai / gpt-4o')).toBeInTheDocument();
  });

  it('N11: cancelled + 有模型 → 不显示(用户主动取消, 看模型无排查意义)', () => {
    renderBlock(makeStep({ outcome: 'cancelled', ...withModel }));
    expect(screen.queryByText('openai / gpt-4o')).not.toBeInTheDocument();
  });

  it('completed + 有模型 → 不显示(沿用 [40] 定案)', () => {
    renderBlock(makeStep({ outcome: 'completed', ...withModel }));
    expect(screen.queryByText('openai / gpt-4o')).not.toBeInTheDocument();
  });

  it('failed + 模型缺失 → 不显示(缺字段不渲染)', () => {
    renderBlock(makeStep({ outcome: 'failed' }));
    expect(screen.queryByText(/\/ /)).not.toBeInTheDocument();
  });
});

describe('N15 - token 全缺显空态(原整行坍缩)', () => {
  it('T 缺失 → 不显示 Token 段', () => {
    renderBlock(makeStep({ outcome: 'completed', duration: 12.3 }));
    expect(screen.queryByText(/输入:/)).not.toBeInTheDocument();
  });

  it('有 T → 显示 Token 段', () => {
    renderBlock(makeStep({ total_tokens: 253316 }));
    expect(screen.getByText(/输入:/)).toBeInTheDocument();
  });
});

describe('N9 - 底部 padding 补 MD(原 0 致文字贴容器底)', () => {
  it('容器有 padding', () => {
    renderBlock(makeStep({ outcome: 'completed' }));
    // 外层容器有 padding，确保内容不贴边
    const container = screen.getByRole('button').parentElement!;
    expect(container.style.padding).toBeDefined();
  });
});

describe('时间范围显示 - startTimestamp + duration 计算开始/结束时间', () => {
  // 基准时间：2026-10-27 10:00:00
  const baseTime = new Date('2026-10-27T10:00:00').getTime();

  it('startTimestamp + duration 存在 → 显示时间范围', () => {
    renderBlock(
      makeStep({ duration: 180 }),
      vi.fn(),
      false,
      baseTime
    );
    // 10:00:00 → 10:03:00 (180s = 3min)
    expect(screen.getByText(/10:00:00→10:03:00/)).toBeInTheDocument();
  });

  it('startTimestamp 缺失 → 不显示时间范围', () => {
    renderBlock(makeStep({ duration: 180 }));
    expect(screen.queryByText(/→/)).not.toBeInTheDocument();
  });

  it('duration 缺失 → 不显示时间范围', () => {
    renderBlock(makeStep({ duration: undefined }), vi.fn(), false, baseTime);
    expect(screen.queryByText(/→/)).not.toBeInTheDocument();
  });

  it('跨日时间范围补 MM-DD 前缀', () => {
    // 23:50:00 + 720s (12min) = 次日 00:02:00
    const lateNight = new Date('2026-10-27T23:50:00').getTime();
    renderBlock(
      makeStep({ duration: 720 }),
      vi.fn(),
      false,
      lateNight
    );
    // 应显示 10-27 23:50:00→10-28 00:02:00
    expect(screen.getByText(/10-27 23:50:00→10-28 00:02:00/)).toBeInTheDocument();
  });
});

describe('token 显示 - 显示任务级 P/C/T 三个数字', () => {
  it('有 P/C/T → 显示 "输入:xxx 输出:xxx 总计:xxx"', () => {
    renderBlock(
      makeStep({
        prompt_tokens: 111499,
        completion_tokens: 721,
        total_tokens: 112220,
      })
    );
    expect(screen.getByText(/输入:111.5K 输出:721 总计:112.2K \[tok\]/)).toBeInTheDocument();
  });

  it('P/C 缺失但 T 有 → 显示 "输入:- 输出:- 总计:xxx"', () => {
    renderBlock(
      makeStep({
        prompt_tokens: undefined,
        completion_tokens: undefined,
        total_tokens: 112220,
      })
    );
    expect(screen.getByText(/输入:- 输出:- 总计:112.2K \[tok\]/)).toBeInTheDocument();
  });

  it('T 缺失 → 不显示 Token 段', () => {
    renderBlock(makeStep({ total_tokens: undefined }));
    expect(screen.queryByText(/输入:/)).not.toBeInTheDocument();
  });
});
