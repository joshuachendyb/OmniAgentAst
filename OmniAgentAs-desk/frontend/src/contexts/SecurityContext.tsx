/**
 * 安全检测上下文 - SecurityContext.tsx
 * 
 * 功能：使用React Context API管理安全检测状态
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-19
 * @update 初始版本，基于阶段2.1危险等级设计文档
 */

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import type { SecurityCheckResponse, RiskLevelConfig } from '../types/security';
import { getRiskLevel } from '../types/security';
import { securityApi } from '../services/api';

/**
 * 安全检测状态类型
 */
interface SecurityState {
  lastCheckResult: SecurityCheckResponse | null;
  isChecking: boolean;
  error: string | null;
}

/**
 * 安全检测上下文类型
 */
interface SecurityContextType extends SecurityState {
  // Getters
  currentScore: number | null;
  currentRiskLevel: RiskLevelConfig | null;
  canProceed: boolean;
  needConfirmation: boolean;
  isBlocked: boolean;
  
  // Actions
  checkCommand: (command: string) => Promise<SecurityCheckResponse>;
  clearResult: () => void;
  clearError: () => void;
}

/**
 * 创建上下文
 */
const SecurityContext = createContext<SecurityContextType | null>(null);

/**
 * 安全检测Provider组件
 * 
 * @param children 子组件
 * @author 小新
 */
export const SecurityProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  // ==================== State ====================
  const [lastCheckResult, setLastCheckResult] = useState<SecurityCheckResponse | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ==================== Getters ====================
  
  /**
   * 当前分数
   */
  const currentScore = lastCheckResult?.data?.score ?? null;

  /**
   * 当前风险等级配置
   */
  const currentRiskLevel = currentScore !== null ? getRiskLevel(currentScore) : null;

  /**
   * 是否可以直接执行（0-6分）
   */
  const canProceed = currentRiskLevel?.canProceed ?? false;

  /**
   * 是否需要弹窗确认（7-8分）
   */
  const needConfirmation = currentRiskLevel?.level === 'HIGH';

  /**
   * 是否被直接拒绝（9-10分）
   */
  const isBlocked = currentRiskLevel?.level === 'CRITICAL';

  // ==================== Actions ====================
  
  /**
   * 检查命令安全性
   * 
   * @param command 要检查的命令
   * @returns 检查结果
   * @author 小新
   */
  const checkCommand = useCallback(async (command: string): Promise<SecurityCheckResponse> => {
    setIsChecking(true);
    setError(null);
    
    try {
      const result = await securityApi.checkCommand(command);
      setLastCheckResult(result);
      
      if (!result.success) {
        setError(result.error || '安全检查失败');
      }
      
      return result;
    } catch (err: any) {
      const errorMsg = err?.message || '安全检查请求失败';
      setError(errorMsg);
      
      const errorResult: SecurityCheckResponse = {
        success: false,
        error: errorMsg
      };
      setLastCheckResult(errorResult);
      
      return errorResult;
    } finally {
      setIsChecking(false);
    }
  }, []);

  /**
   * 清空检查结果
   * @author 小新
   */
  const clearResult = useCallback(() => {
    setLastCheckResult(null);
    setError(null);
  }, []);

  /**
   * 清空错误信息
   * @author 小新
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  // ==================== Context Value ====================
  const value: SecurityContextType = {
    // State
    lastCheckResult,
    isChecking,
    error,
    
    // Getters
    currentScore,
    currentRiskLevel,
    canProceed,
    needConfirmation,
    isBlocked,
    
    // Actions
    checkCommand,
    clearResult,
    clearError
  };

  return (
    <SecurityContext.Provider value={value}>
      {children}
    </SecurityContext.Provider>
  );
};

/**
 * 使用安全检测上下文的Hook
 * 
 * @returns 安全检测上下文
 * @throws 如果在Provider外使用会抛出错误
 * @author 小新
 */
export const useSecurity = (): SecurityContextType => {
  const context = useContext(SecurityContext);
  if (!context) {
    throw new Error('useSecurity must be used within a SecurityProvider');
  }
  return context;
};

/**
 * 安全检测Hook（简化版）
 * 直接返回是否可以继续执行
 * 
 * @returns 检查函数和状态
 * @author 小新
 */
export const useSecurityCheck = () => {
  const security = useSecurity();
  
  return {
    ...security,
    
    /**
     * 检查命令并返回是否可以继续
     * @param command 要检查的命令
     * @returns 是否可以直接执行
     */
    checkAndCanProceed: async (command: string): Promise<boolean> => {
      const result = await security.checkCommand(command);
      
      if (!result.success || !result.data) {
        return false;
      }
      
      const riskLevel = getRiskLevel(result.data.score);
      return riskLevel.canProceed;
    }
  };
};
