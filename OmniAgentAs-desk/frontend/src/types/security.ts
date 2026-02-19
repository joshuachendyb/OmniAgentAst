/**
 * 安全检测类型定义 - security.ts
 * 
 * 功能：定义安全检测相关的TypeScript类型和常量
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-19
 * @update 初始版本，基于阶段2.1危险等级设计文档
 */

/**
 * 安全检查响应接口
 * 后端返回格式（精简版）
 */
export interface SecurityCheckResponse {
  success: boolean;      // API是否成功调用
  data?: {
    score: number;       // 风险分数：0-10分，整数
    message: string;     // 用户可见的提示信息
  };
  error?: string;        // API调用失败时的错误信息
}

/**
 * 风险等级定义
 */
export type RiskLevelType = 'SAFE' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

/**
 * 风险等级配置
 */
export interface RiskLevelConfig {
  level: RiskLevelType;
  min: number;
  max: number;
  canProceed: boolean;   // 是否可直接执行
  ui: 'silent' | 'notification' | 'modal' | 'alert';
}

/**
 * 分数段定义（前端使用）
 * 基于设计文档第2.1.2节
 */
export const RISK_LEVELS: Record<RiskLevelType, RiskLevelConfig> = {
  SAFE: {
    level: 'SAFE',
    min: 0,
    max: 3,
    canProceed: true,
    ui: 'silent'
  },
  MEDIUM: {
    level: 'MEDIUM',
    min: 4,
    max: 6,
    canProceed: true,
    ui: 'notification'
  },
  HIGH: {
    level: 'HIGH',
    min: 7,
    max: 8,
    canProceed: false,
    ui: 'modal'
  },
  CRITICAL: {
    level: 'CRITICAL',
    min: 9,
    max: 10,
    canProceed: false,
    ui: 'alert'
  }
} as const;

/**
 * 安全检查状态
 */
export interface SecurityCheckState {
  lastCheckResult: SecurityCheckResponse | null;
  isChecking: boolean;
  error: string | null;
}

/**
 * 根据分数获取风险等级
 * @param score 风险分数（0-10）
 * @returns 风险等级配置
 * @throws 如果分数不在0-10范围内，按最高风险处理
 */
export function getRiskLevel(score: number): RiskLevelConfig {
  // 边界值检查：异常值按最高风险处理
  if (typeof score !== 'number' || isNaN(score)) {
    console.warn(`[Security] Invalid score type: ${typeof score}, defaulting to CRITICAL`);
    return RISK_LEVELS.CRITICAL;
  }
  if (score < 0 || score > 10) {
    console.warn(`[Security] Score out of range: ${score}, defaulting to CRITICAL`);
    return RISK_LEVELS.CRITICAL;
  }
  if (score <= 3) return RISK_LEVELS.SAFE;
  if (score <= 6) return RISK_LEVELS.MEDIUM;
  if (score <= 8) return RISK_LEVELS.HIGH;
  return RISK_LEVELS.CRITICAL;
}

/**
 * 安全检查请求参数
 */
export interface SecurityCheckRequest {
  command: string;
}

/**
 * 安全检测Hook返回值
 */
export interface UseSecurityCheckReturn {
  score: number;
  message: string;
  level: RiskLevelType;
  canProceed: boolean;
  ui: 'silent' | 'notification' | 'modal' | 'alert';
}
