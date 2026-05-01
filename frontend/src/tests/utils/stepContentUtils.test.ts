/**
 * 步骤内容文本处理工具测试
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-05-01
 */

import { describe, it, expect } from 'vitest';
import { formatStepContent, formatReasoningContent } from '../../utils/stepContentUtils';

describe('formatStepContent', () => {
  it('应该将字面\\n转为真换行符', () => {
    const result = formatStepContent('第一行\\n第二行');
    expect(result).toBe('第一行\n第二行');
  });

  it('应该处理多个字面\\n', () => {
    const result = formatStepContent('1\\n2\\n3');
    expect(result).toBe('1\n2\n3');
  });

  it('应该处理连续\\n', () => {
    const result = formatStepContent('段落1\\n\\n段落2');
    expect(result).toBe('段落1\n\n段落2');
  });

  it('应该返回空字符串当输入为undefined', () => {
    expect(formatStepContent(undefined)).toBe('');
  });

  it('应该返回空字符串当输入为null', () => {
    expect(formatStepContent(null)).toBe('');
  });

  it('应该返回空字符串当输入为空字符串', () => {
    expect(formatStepContent('')).toBe('');
  });

  it('不应影响已含真换行符的文本', () => {
    const result = formatStepContent('第一行\n第二行');
    expect(result).toBe('第一行\n第二行');
  });

  it('应处理混合真换行和字面\\n', () => {
    const result = formatStepContent('a\nb\\nc');
    expect(result).toBe('a\nb\nc');
  });

  it('应处理不含\\n的普通文本', () => {
    expect(formatStepContent('普通文本')).toBe('普通文本');
  });
});

describe('formatReasoningContent', () => {
  it('应该将字面\\n转为真换行符', () => {
    const result = formatReasoningContent('推理1\\n推理2');
    expect(result).toBe('推理1\n推理2');
  });

  it('应该返回空字符串当输入为undefined', () => {
    expect(formatReasoningContent(undefined)).toBe('');
  });

  it('应该返回空字符串当输入为null', () => {
    expect(formatReasoningContent(null)).toBe('');
  });

  it('应处理不含\\n的普通文本', () => {
    expect(formatReasoningContent('普通推理')).toBe('普通推理');
  });
});
