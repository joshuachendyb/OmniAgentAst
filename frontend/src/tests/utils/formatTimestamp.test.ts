/**
 * 时间格式化工具函数测试
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-01
 * 
 * 【更新记录】
 * - 2026-04-01 小强：创建测试文件，验证 formatTimestamp 函数
 */

import { describe, it, expect } from 'vitest';
import { formatTimestamp } from '../../utils/timestamp';

describe('formatTimestamp', () => {
  describe('基本功能测试', () => {
    it('应该正确格式化毫秒时间戳', () => {
      const timestamp = 1773720971439;
      const result = formatTimestamp(timestamp);
      // UTC: 2026-03-17T04:16:11.439Z → 北京时间: +8小时
      expect(result).toBe('2026-03-17 12:16:11.439');
    });

    it('应该处理 undefined', () => {
      const result = formatTimestamp(undefined);
      expect(result).toBe('');
    });

    it('应该处理 null', () => {
      const result = formatTimestamp(null as any);
      expect(result).toBe('');
    });

    it('应该处理空字符串', () => {
      const result = formatTimestamp('');
      expect(result).toBe('');
    });
  });

  describe('ISO 字符串解析测试 (Bug修复验证)', () => {
    /**
     * 【重要】这是 Bug 修复的核心测试场景
     * 
     * 问题背景：
     * 1. message.timestamp 创建时是 Date 对象
     * 2. JSON.stringify() 存储到 sessionStorage 时，Date对象转成 ISO 字符串
     *    例如："2026-04-01T08:13:25.744Z"
     * 3. JSON.parse() 从 sessionStorage 恢复时，字符串不会自动变回 Date 对象
     * 4. formatTimestamp() 收到的是 ISO 字符串，不是 Date 对象
     * 
     * 错误代码问题：
     * - parseInt("2026-04-01T08:13:25.744Z", 10) = 2026 (只取前导数字)
     * - new Date(2026) = 1970-01-01 08:00:02.026 (错误!)
     * 
     * 修复方案：
     * - Date.parse("2026-04-01T08:13:25.744Z") = 1775031205744 (正确毫秒时间戳)
     * - new Date(1775031205744) = 2026-04-01 08:13:25.744 (正确时间)
     */

    it('【核心测试】应该正确解析 sessionStorage 恢复后的 ISO 字符串', () => {
      const isoString = '2026-04-01T08:13:25.744Z';
      const result = formatTimestamp(isoString);
      
      // 验证不会返回 1970 年的错误时间
      expect(result).not.toBe('1970-01-01 08:00:02.026');
      expect(result).not.toBe('');
      
      // 验证正确解析为 2026 年 (UTC 08:13:25 → 北京时间 +8小时)
      expect(result).toBe('2026-04-01 16:13:25.744');
    });

    it('应该正确解析带时区的 ISO 字符串 (UTC+0)', () => {
      const isoString = '2026-04-01T00:00:00.000Z';
      const result = formatTimestamp(isoString);
      expect(result).toBe('2026-04-01 08:00:00.000'); // 北京时间 UTC+8
    });

    it('应该正确解析带毫秒的 ISO 字符串', () => {
      const isoString = '2026-04-01T08:13:25.123Z';
      const result = formatTimestamp(isoString);
      expect(result).toBe('2026-04-01 16:13:25.123');
    });

    it('应该正确解析中国时区的 ISO 字符串 (+08:00)', () => {
      const isoString = '2026-04-01T08:13:25.744+08:00';
      const result = formatTimestamp(isoString);
      expect(result).toBe('2026-04-01 08:13:25.744'); // 本地时间无需转换
    });

    it('应该正确解析不带毫秒的 ISO 字符串', () => {
      const isoString = '2026-04-01T08:13:25Z';
      const result = formatTimestamp(isoString);
      expect(result).toBe('2026-04-01 16:13:25.000');
    });

    it('应该处理无效的 ISO 字符串', () => {
      const invalidString = 'not-a-date';
      const result = formatTimestamp(invalidString);
      // 注意：由于代码中 !ts 检查，空字符串才返回 ''
      // 无效字符串会被解析为 1970-01-01 (边界处理行为)
      expect(result).toBe('1970-01-01 08:00:00.000');
    });

    it('应该正确处理纯日期字符串', () => {
      const dateString = '2026-04-01';
      const result = formatTimestamp(dateString);
      // Date.parse("2026-04-01") = 2026-04-01T00:00:00.000Z
      expect(result).toBe('2026-04-01 08:00:00.000');
    });
  });

  describe('边界条件测试', () => {
    it('应该处理 0 时间戳', () => {
      const result = formatTimestamp(0);
      // 注意：由于代码中 if (!ts) return '' 会过滤掉 0
      // 返回空字符串（边界处理行为）
      expect(result).toBe('');
    });

    it('应该处理非常大的时间戳（未来时间）', () => {
      const futureTimestamp = 4102444800000;
      const result = formatTimestamp(futureTimestamp);
      // UTC: 2100-01-01T00:00:00.000Z → 北京时间
      expect(result).toBe('2100-01-01 08:00:00.000');
    });
  });

  describe('日期部分测试', () => {
    it('应该正确处理月份边界（1月31日）', () => {
      const isoString = '2026-01-31T12:00:00.000Z';
      const result = formatTimestamp(isoString);
      expect(result).toBe('2026-01-31 20:00:00.000');
    });

    it('应该正确处理闰年2月29日', () => {
      const isoString = '2024-02-29T12:00:00.000Z';
      const result = formatTimestamp(isoString);
      expect(result).toBe('2024-02-29 20:00:00.000');
    });
  });

  describe('sessionStorage 模拟测试', () => {
    /**
     * 模拟 sessionStorage 的 JSON.stringify/parse 过程
     * 这是实际使用场景的端到端测试
     */
    it('应该正确处理 sessionStorage 存储/恢复周期', () => {
      const originalTimestamp = 1773720971439;
      
      // 创建 Date 对象
      const dateObj = new Date(originalTimestamp);
      
      // 模拟 JSON.stringify (存储到 sessionStorage)
      const storedString = JSON.stringify(dateObj);
      expect(storedString).toMatch(/^\"\d{4}-\d{2}-\d{2}T/);
      
      // 模拟 JSON.parse (从 sessionStorage 恢复)
      const restoredDate = JSON.parse(storedString);
      
      // formatTimestamp 应该正确处理恢复后的 ISO 字符串
      const result = formatTimestamp(restoredDate);
      expect(result).toBe('2026-03-17 12:16:11.439');
    });

    it('应该处理数组中包含多个消息的时间戳', () => {
      const messages = [
        { timestamp: '2026-04-01T08:00:00.000Z' },
        { timestamp: '2026-04-01T08:05:30.500Z' },
        { timestamp: '2026-04-01T08:10:45.123Z' },
      ];

      const results = messages.map(msg => formatTimestamp(msg.timestamp));

      expect(results[0]).toBe('2026-04-01 16:00:00.000');
      expect(results[1]).toBe('2026-04-01 16:05:30.500');
      expect(results[2]).toBe('2026-04-01 16:10:45.123');
    });
  });
});
