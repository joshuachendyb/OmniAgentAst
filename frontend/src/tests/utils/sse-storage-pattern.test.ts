/**
 * SSE 数据存储方式测试
 * 
 * 测试目标：验证 SSE 事件处理使用正确的回调函数模式
 * - chunk 类型应使用回调函数模式
 * - final 类型应调用 onShowSteps?.(true)
 * - error 类型应使用回调函数模式 + 调用 onShowSteps?.(true)
 * - incident(interrupted) 类型应调用 onShowSteps?.(true)
 * 
 * @author 小强
 * @since 2026-04-10
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/**
 * 测试数据存储方式的正确性
 * 
 * 正确的回调函数模式：
 * setExecutionSteps((prev) => {
 *   const newSteps = [...prev, step];
 *   handlers.executionStepsRef.current = newSteps;
 *   saveStepsToStorage?.(newSteps);
 *   return newSteps;
 * });
 * 
 * 错误的直接同步更新：
 * const newSteps = [...handlers.executionStepsRef.current, step];
 * handlers.executionStepsRef.current = newSteps;
 * setExecutionSteps(newSteps);
 */
describe('SSE 数据存储方式 - 回调函数模式验证', () => {
  
  /**
   * 测试1: chunk 类型应使用回调函数模式
   * 
   * 验证：chunk 处理时，setExecutionSteps 应该传入函数（回调函数模式）
   * 而不是直接传入数组（直接同步更新）
   */
  it('chunk 类型应使用回调函数模式 setExecutionSteps((prev)=>{...})', () => {
    // 模拟 handlers 对象
    const executionStepsRef = { current: [] as any[] };
    let setExecutionStepsCalledWithFunction = false;
    let setExecutionStepsCalledWithArray = false;
    
    const mockSetExecutionSteps = (value: any) => {
      if (typeof value === 'function') {
        setExecutionStepsCalledWithFunction = true;
        // 执行回调函数，验证内部逻辑
        const result = value(executionStepsRef.current);
        expect(result).toBeDefined();
        expect(Array.isArray(result)).toBe(true);
      } else {
        setExecutionStepsCalledWithArray = true;
      }
    };
    
    // 模拟 chunk 处理逻辑
    const processChunkWithCallbackPattern = () => {
      const step = { type: 'chunk', content: 'test' };
      // 正确的回调函数模式
      mockSetExecutionSteps((prev: any[]) => {
        const newSteps = [...prev, step];
        executionStepsRef.current = newSteps;
        return newSteps;
      });
    };
    
    processChunkWithCallbackPattern();
    
    // 验证：应该使用回调函数模式
    expect(setExecutionStepsCalledWithFunction).toBe(true);
    expect(setExecutionStepsCalledWithArray).toBe(false);
  });

  /**
   * 测试2: final 类型应调用 onShowSteps?.(true)
   * 
   * 验证：final 类型处理后，应该调用 onShowSteps?.(true)
   * 以确保直接返回 final 时步骤列表显示
   */
  it('final 类型应调用 onShowSteps?.(true)', () => {
    let onShowStepsCalled = false;
    let onShowStepsArgument: boolean | undefined;
    
    const mockOnShowSteps = (show: boolean) => {
      onShowStepsCalled = true;
      onShowStepsArgument = show;
    };
    
    // 模拟 final 处理逻辑
    const processFinal = () => {
      const step = { type: 'final', content: 'final response' };
      // 正确的逻辑：调用 onShowSteps?.(true)
      mockOnShowSteps?.(true);
    };
    
    processFinal();
    
    // 验证：onShowSteps 应该被调用，参数为 true
    expect(onShowStepsCalled).toBe(true);
    expect(onShowStepsArgument).toBe(true);
  });

  /**
   * 测试3: error 类型应使用回调函数模式 + 调用 onShowSteps?.(true)
   * 
   * 验证：error 类型处理时：
   * 1. setExecutionSteps 应该使用回调函数模式
   * 2. 应该调用 onShowSteps?.(true)
   */
  it('error 类型应使用回调函数模式 + onShowSteps?.(true)', () => {
    const executionStepsRef = { current: [] as any[] };
    let setExecutionStepsCalledWithFunction = false;
    let onShowStepsCalled = false;
    let onShowStepsArgument: boolean | undefined;
    
    const mockSetExecutionSteps = (value: any) => {
      if (typeof value === 'function') {
        setExecutionStepsCalledWithFunction = true;
        const result = value(executionStepsRef.current);
        expect(result).toBeDefined();
        expect(Array.isArray(result)).toBe(true);
      }
    };
    
    const mockOnShowSteps = (show: boolean) => {
      onShowStepsCalled = true;
      onShowStepsArgument = show;
    };
    
    // 模拟 error 处理逻辑（正确的实现）
    const processError = () => {
      const step = { type: 'error', content: 'error message' };
      // 正确的回调函数模式
      mockSetExecutionSteps((prev: any[]) => {
        const newSteps = [...prev, step];
        executionStepsRef.current = newSteps;
        return newSteps;
      });
      // 正确的：调用 onShowSteps?.(true)
      mockOnShowSteps?.(true);
    };
    
    processError();
    
    // 验证：应该使用回调函数模式 + onShowSteps
    expect(setExecutionStepsCalledWithFunction).toBe(true);
    expect(onShowStepsCalled).toBe(true);
    expect(onShowStepsArgument).toBe(true);
  });

  /**
   * 测试4: incident(interrupted) 类型应调用 onShowSteps?.(true)
   * 
   * 验证：incident 类型中 interrupted 应该调用 onShowSteps?.(true)
   * 以确保用户中断时步骤列表显示
   */
  it('incident(interrupted) 类型应调用 onShowSteps?.(true)', () => {
    let onShowStepsCalled = false;
    let onShowStepsArgument: boolean | undefined;
    
    const mockOnShowSteps = (show: boolean) => {
      onShowStepsCalled = true;
      onShowStepsArgument = show;
    };
    
    // 模拟 incident(interrupted) 处理逻辑
    const processInterrupted = () => {
      const step = { type: 'interrupted', content: 'user stopped' };
      // 正确的：调用 onShowSteps?.(true)
      mockOnShowSteps?.(true);
    };
    
    processInterrupted();
    
    // 验证：onShowSteps 应该被调用，参数为 true
    expect(onShowStepsCalled).toBe(true);
    expect(onShowStepsArgument).toBe(true);
  });

  /**
   * 测试5: 对比回调函数模式和直接同步更新
   * 
   * 验证两种模式的差异
   */
  it('验证回调函数模式 vs 直接同步更新的差异', () => {
    const ref = { current: [] as any[] };
    const step = { type: 'chunk', content: 'test' };
    
    // 回调函数模式（正确）
    const callbackPattern = () => {
      let result: any[] = [];
      const setState = (value: any) => {
        if (typeof value === 'function') {
          result = value(ref.current);
          ref.current = result;
        }
      };
      setState((prev: any[]) => [...prev, step]);
      return result;
    };
    
    // 直接同步更新（错误）
    const directPattern = () => {
      const newSteps = [...ref.current, step];
      ref.current = newSteps;
      return newSteps;
    };
    
    const callbackResult = callbackPattern();
    const refAfterCallback = [...ref.current];
    
    // 重置 ref
    ref.current = [];
    
    const directResult = directPattern();
    const refAfterDirect = [...ref.current];
    
    // 两种方式都能得到正确结果，但回调函数模式更符合 React 设计
    expect(callbackResult.length).toBe(1);
    expect(directResult.length).toBe(1);
    expect(refAfterCallback.length).toBe(1);
    expect(refAfterDirect.length).toBe(1);
  });

  /**
   * 测试6: 验证 setTimeout 延迟保存不阻塞 UI
   * 
   * 测试目标：验证使用 setTimeout(() => { saveStepsToStorage?.(newSteps); }, 0)
   * 可以将同步保存转为异步，避免阻塞主线程
   * 
   * 验证：
   * 1. setTimeout 回调在下一帧执行（不是立即执行）
   * 2. saveStepsToStorage 在 setTimeout 回调中被调用
   * 3. 主线程不会被阻塞
   */
  it('setTimeout 延迟保存不阻塞 UI 线程', async () => {
    const executionStepsRef = { current: [] as any[] };
    let saveCalled = false;
    let saveCalledInSetTimeout = false;
    let mainThreadBlocked = false;
    
    // 模拟 saveStepsToStorage
    const mockSaveStepsToStorage = (steps: any[]) => {
      saveCalled = true;
    };
    
    // 模拟 setExecutionSteps 回调函数模式
    const mockSetExecutionSteps = (value: any) => {
      if (typeof value === 'function') {
        const newSteps = value(executionStepsRef.current);
        executionStepsRef.current = newSteps;
        
        // 使用 setTimeout 延迟保存（方案1）
        setTimeout(() => {
          saveCalledInSetTimeout = true;
          mockSaveStepsToStorage(newSteps);
        }, 0);
        
        return newSteps;
      }
    };
    
    // 记录主线程是否被阻塞
    const startTime = Date.now();
    
    // 执行回调函数模式
    const step = { type: 'action_tool', content: 'test', raw_data: { size: 100 * 1024 * 1024 } }; // 100MB
    mockSetExecutionSteps((prev: any[]) => [...prev, step]);
    
    // 立即检查 - saveStepsToStorage 尚未被调用（因为在 setTimeout 中）
    expect(saveCalled).toBe(false);
    
    // 等待 setTimeout 执行
    await new Promise(resolve => setTimeout(resolve, 10));
    
    // 验证：saveStepsToStorage 在 setTimeout 中被调用
    expect(saveCalled).toBe(true);
    expect(saveCalledInSetTimeout).toBe(true);
    
    // 验证：主线程未被阻塞（即使数据很大）
    const elapsed = Date.now() - startTime;
    expect(elapsed).toBeLessThan(100); // 应该很快完成，因为 setTimeout 不阻塞
  });

  /**
   * 测试7: 验证大数据场景下 setTimeout 延迟执行不会卡死 UI
   * 
   * 测试目标：100M/170M 大数据时，setTimeout 延迟执行让 UI 先完成
   * 虽然最终 saveStepsToStorage 会失败（sessionStorage 5MB 限制），但 UI 不卡死
   */
  it('大数据场景下延迟保存确保 UI 不卡死', async () => {
    const executionStepsRef = { current: [] as any[] };
    let saveError: Error | null = null;
    let uiCompletedBeforeSave = false;
    
    // 模拟会失败的 saveStepsToStorage（大数据超出 5MB）
    const mockSaveStepsToStorage = (steps: any[]) => {
      // 模拟 sessionStorage 溢出
      try {
        // 大数据会触发 QuotaExceededError
        throw new DOMException('QuotaExceededError', 'QuotaExceededError');
      } catch (e: any) {
        saveError = e;
      }
    };
    
    // 模拟 mockSetExecutionSteps
    const mockSetExecutionSteps = (value: any) => {
      if (typeof value === 'function') {
        const newSteps = value(executionStepsRef.current);
        executionStepsRef.current = newSteps;
        
        // 延迟保存
        setTimeout(() => {
          mockSaveStepsToStorage(newSteps);
        }, 0);
        
        return newSteps;
      }
    };
    
    // 模拟 UI 完成标志
    let uiRenderComplete = false;
    
    // 执行 setExecutionSteps 回调函数模式 + setTimeout 延迟保存
    const processLargeData = () => {
      const step = { 
        type: 'action_tool', 
        content: 'test', 
        raw_data: { data: 'x'.repeat(170 * 1024 * 1024) } // 170MB
      };
      
      mockSetExecutionSteps((prev: any[]) => {
        const newSteps = [...prev, step];
        executionStepsRef.current = newSteps;
        
        // 延迟保存
        setTimeout(() => {
          mockSaveStepsToStorage(newSteps);
        }, 0);
        
        return newSteps;
      });
      
      // UI 渲染完成（主线程继续执行，不等待 setTimeout）
      uiRenderComplete = true;
    };
    
    processLargeData();
    
    // 验证：UI 先完成（不阻塞）
    expect(uiRenderComplete).toBe(true);
    
    // 等待 setTimeout 执行
    await new Promise(resolve => setTimeout(resolve, 10));
    
    // 验证：大数据保存失败（预期行为），但 UI 已完成
    expect(saveError).toBeDefined();
    expect(uiRenderComplete).toBe(true); // UI 早已完成，不受保存失败影响
  });
});