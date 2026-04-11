/**
 * 统一错误处理中心 - errorHandler.ts
 *
 * 功能：集中管理所有前端错误的分类、提示风格、重试逻辑、错误去重
 * 设计文档：前端错误统一处理中心设计-小强-2026-0411.md (v1.4)
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-11
 */

import { message } from "antd";

// ============================================
// UI配置标准 - 统一提示样式
// ============================================

/**
 * UI显示配置
 */
export const UI_CONFIG = {
  error: { duration: 5, maxCount: 1 },
  warning: { duration: 3, maxCount: 3 },
  success: { duration: 2, maxCount: 1 },
  info: { duration: 3, maxCount: 3 },
  loading: { duration: 0, maxCount: 1 },
} as const;

// ============================================
// 错误类型枚举 - 53种错误类型
// ============================================

export enum ErrorType {
  // 网络错误
  CONNECTION_REFUSED = "connection_refused",
  CONNECTION_RESET = "connection_reset",
  NETWORK_ERROR = "network_error",
  WEAK_NETWORK = "weak_network",

  // 超时错误
  REQUEST_TIMEOUT = "request_timeout",
  IDLE_TIMEOUT = "idle_timeout",

  // 服务器错误
  SERVER_500 = "server_500",
  SERVER_502 = "server_502",
  SERVER_503 = "server_503",

  // 认证错误
  AUTH_401 = "auth_401",
  AUTH_403 = "auth_403",

  // 业务错误
  SESSION_CONFLICT = "session_conflict",
  SESSION_NOT_FOUND = "session_not_found",
  VERSION_CONFLICT = "version_conflict",
  CONTENT_TOO_LONG = "content_too_long",
  RATE_LIMIT_429 = "rate_limit_429",

  // 存储错误
  QUOTA_EXCEEDED = "quota_exceeded",
  STORAGE_ERROR = "storage_error",

  // 操作错误
  SAVE_FAILED = "save_failed",
  LOAD_FAILED = "load_failed",
  SEND_FAILED = "send_failed",
  USER_MESSAGE_SAVE_FAILED = "user_message_save_failed",

  // 安全相关
  DANGEROUS_OPERATION = "dangerous_operation",
  DANGER_CONFIRM_FAIL = "danger_confirm_fail",
  SECURITY_SERVICE_DOWN = "security_service_down",
  DANGER_CANCELLED = "danger_cancelled",

  // 防抖
  DUPLICATE_CLICK = "duplicate_click",
  RETRY_WARNING = "retry_warning",

  // 任务控制
  TASK_CONTROL_FAILED = "task_control_failed",
  TASK_INTERRUPT = "task_interrupt",
  IDLE_STATE = "idle_state",

  // 会话相关
  CREATE_SESSION_FAILED = "create_session_failed",

  // 成功类型
  SAVE_SUCCESS = "save_success",
  TASK_SUCCESS = "task_success",

  // 静默处理
  REQUEST_ABORT = "request_abort",
  COMPONENT_UNMOUNTED = "component_unmounted",

  // Settings页面错误
  PROVIDER_CONFIG_ERROR = "provider_config_error",
  MODEL_CONFIG_ERROR = "model_config_error",
  ADD_PROVIDER_FAILED = "add_provider_failed",
  DELETE_PROVIDER_FAILED = "delete_provider_failed",
  UPDATE_PROVIDER_FAILED = "update_provider_failed",
  ADD_MODEL_FAILED = "add_model_failed",
  DELETE_MODEL_FAILED = "delete_model_failed",
  SWITCH_MODEL_FAILED = "switch_model_failed",
  LOAD_CONFIG_FAILED = "load_config_failed",
  SAVE_CONFIG_FAILED = "save_config_failed",
  OPEN_CONFIG_DIR_FAILED = "open_config_dir_failed",
  READ_CONFIG_FAILED = "read_config_failed",
  VALIDATE_CONFIG_FAILED = "validate_config_failed",

  // History页面错误
  SESSION_LIST_FAILED = "session_list_failed",
  REFRESH_FAILED = "refresh_failed",
  DELETE_SESSION_FAILED = "delete_session_failed",
  BATCH_DELETE_FAILED = "batch_delete_failed",
  NAVIGATE_FAILED = "navigate_failed",

  // 其他
  BACKEND_ERROR = "backend_error",
  UNKNOWN = "unknown",

  // 通用提示类型（非错误）
  WARNING = "warning",
  INFO = "info",
}

// ============================================
// 错误配置接口
// ============================================

export interface ErrorConfig {
  retryable: boolean;
  maxRetries: number;
  retryDelay: number;
  retryBackoff?: number;
  message: string;
  description?: string;
  severity: "critical" | "warning" | "info";
  silent?: boolean;
  dedupWindow?: number;
  continueOnError?: boolean;
  deleteMessage?: boolean;
  fallbackMode?: string;
}

// ============================================
// 错误配置映射表 - ERROR_CONFIG_MAP
// ============================================

export const ERROR_CONFIG_MAP: Record<ErrorType, ErrorConfig> = {
  // 网络错误
  [ErrorType.CONNECTION_REFUSED]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    retryBackoff: 2,
    message: "服务器连接被拒绝，请检查后端服务是否运行",
    severity: "warning",
  },
  [ErrorType.CONNECTION_RESET]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    retryBackoff: 2,
    message: "连接被重置，请检查网络后重试",
    severity: "warning",
  },
  [ErrorType.NETWORK_ERROR]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1500,
    message: "网络连接失败，请检查网络后重试",
    severity: "warning",
  },
  [ErrorType.WEAK_NETWORK]: {
    retryable: true,
    maxRetries: 1,
    retryDelay: 2000,
    message: "网络不稳定，请稍后重试",
    severity: "warning",
  },

  // 超时错误
  [ErrorType.REQUEST_TIMEOUT]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    message: "请求超时，请稍后重试",
    severity: "warning",
  },
  [ErrorType.IDLE_TIMEOUT]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 500,
    message: "空闲超时，连接可能已断开",
    severity: "warning",
  },

  // 服务器错误
  [ErrorType.SERVER_500]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "服务器内部错误，请稍后刷新页面重试",
    severity: "critical",
  },
  [ErrorType.SERVER_502]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 2000,
    message: "服务器网关错误，请稍后重试",
    severity: "warning",
  },
  [ErrorType.SERVER_503]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 2000,
    message: "服务暂不可用，请稍后重试",
    severity: "warning",
  },

  // 认证错误
  [ErrorType.AUTH_401]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "API Key无效，请检查配置",
    severity: "critical",
  },
  [ErrorType.AUTH_403]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "权限不足，请检查配置",
    severity: "critical",
  },

  // 业务错误
  [ErrorType.SESSION_CONFLICT]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "会话冲突，请刷新页面重试",
    severity: "warning",
  },
  [ErrorType.SESSION_NOT_FOUND]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "会话不存在，请返回重试",
    severity: "warning",
  },
  [ErrorType.VERSION_CONFLICT]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "版本冲突，请刷新页面重试",
    severity: "warning",
  },
  [ErrorType.CONTENT_TOO_LONG]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "内容过长，请精简后重试",
    severity: "warning",
  },
  [ErrorType.RATE_LIMIT_429]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "请求太频繁，请稍后再试",
    severity: "warning",
  },

  // 存储错误
  [ErrorType.QUOTA_EXCEEDED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "存储满了，请清理空间后重试",
    severity: "warning",
  },
  [ErrorType.STORAGE_ERROR]: {
    retryable: true,
    maxRetries: 1,
    retryDelay: 500,
    message: "存储操作失败，请重试",
    severity: "warning",
  },

  // 操作错误
  [ErrorType.SAVE_FAILED]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    message: "保存失败，请重试",
    severity: "warning",
  },
  [ErrorType.LOAD_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "加载失败，请重试",
    severity: "warning",
  },
  [ErrorType.SEND_FAILED]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    message: "发送失败，请重试",
    severity: "warning",
  },
  [ErrorType.USER_MESSAGE_SAVE_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 500,
    message: "用户消息保存失败",
    severity: "warning",
    continueOnError: true,
  },

  // 安全相关
  [ErrorType.DANGEROUS_OPERATION]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "危险操作已被拦截",
    severity: "critical",
    deleteMessage: true,
  },
  [ErrorType.DANGER_CONFIRM_FAIL]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "危险操作确认失败",
    severity: "warning",
  },
  [ErrorType.SECURITY_SERVICE_DOWN]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "安全服务异常，已降级为普通模式",
    severity: "warning",
    fallbackMode: "normal",
  },
  [ErrorType.DANGER_CANCELLED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "已取消危险命令的执行",
    severity: "info",
    silent: true,
  },

  // 防抖
  [ErrorType.DUPLICATE_CLICK]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "请求处理中，请稍后再试",
    severity: "info",
    silent: true,
  },
  [ErrorType.RETRY_WARNING]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "",
    severity: "warning",
  },

  // 任务控制
  [ErrorType.TASK_CONTROL_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "暂停/继续请求失败，请重试",
    severity: "warning",
  },
  [ErrorType.TASK_INTERRUPT]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "正在中断任务...",
    severity: "info",
    silent: true,
  },
  [ErrorType.IDLE_STATE]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "当前没有进行中的任务",
    severity: "warning",
    silent: true,
  },

  // 会话相关
  [ErrorType.CREATE_SESSION_FAILED]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    message: "创建会话失败，请重试",
    severity: "warning",
  },

  // 成功类型
  [ErrorType.SAVE_SUCCESS]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "操作成功",
    severity: "info",
  },
  [ErrorType.TASK_SUCCESS]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "任务操作成功",
    severity: "info",
  },

  // 静默处理
  [ErrorType.REQUEST_ABORT]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "",
    severity: "info",
    silent: true,
  },
  [ErrorType.COMPONENT_UNMOUNTED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "",
    severity: "info",
    silent: true,
  },

  // Settings页面错误
  [ErrorType.PROVIDER_CONFIG_ERROR]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "Provider配置错误，请检查配置",
    severity: "critical",
  },
  [ErrorType.MODEL_CONFIG_ERROR]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "Model配置错误，请检查配置",
    severity: "critical",
  },
  [ErrorType.ADD_PROVIDER_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "添加Provider失败，请重试",
    severity: "warning",
  },
  [ErrorType.DELETE_PROVIDER_FAILED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "删除Provider失败",
    severity: "warning",
  },
  [ErrorType.UPDATE_PROVIDER_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "更新Provider失败，请重试",
    severity: "warning",
  },
  [ErrorType.ADD_MODEL_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "添加Model失败，请重试",
    severity: "warning",
  },
  [ErrorType.DELETE_MODEL_FAILED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "删除Model失败",
    severity: "warning",
  },
  [ErrorType.SWITCH_MODEL_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "切换模型失败，请重试",
    severity: "warning",
  },
  [ErrorType.LOAD_CONFIG_FAILED]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    message: "加载配置失败，请重试",
    severity: "warning",
  },
  [ErrorType.SAVE_CONFIG_FAILED]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    message: "保存配置失败，请重试",
    severity: "warning",
  },
  [ErrorType.OPEN_CONFIG_DIR_FAILED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "打开配置目录失败",
    severity: "warning",
  },
  [ErrorType.READ_CONFIG_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "读取配置文件失败，请重试",
    severity: "warning",
  },
  [ErrorType.VALIDATE_CONFIG_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "检测配置失败，请重试",
    severity: "warning",
  },

  // History页面错误
  [ErrorType.SESSION_LIST_FAILED]: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    message: "加载会话列表失败，请重试",
    severity: "warning",
  },
  [ErrorType.REFRESH_FAILED]: {
    retryable: true,
    maxRetries: 2,
    retryDelay: 1000,
    message: "刷新失败，请重试",
    severity: "warning",
  },
  [ErrorType.DELETE_SESSION_FAILED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "删除会话失败",
    severity: "warning",
  },
  [ErrorType.BATCH_DELETE_FAILED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "批量删除会话失败",
    severity: "warning",
  },
  [ErrorType.NAVIGATE_FAILED]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "跳转失败",
    severity: "warning",
  },

  // 其他
  [ErrorType.BACKEND_ERROR]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "后端错误，请稍后重试",
    severity: "critical",
  },
  [ErrorType.UNKNOWN]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "发生未知错误",
    severity: "warning",
  },

  // 通用提示类型（非错误）
  [ErrorType.WARNING]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "",
    severity: "warning",
  },
  [ErrorType.INFO]: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    message: "",
    severity: "info",
  },
};

// ============================================
// 错误去重机制 - 30秒内不重复提示
// ============================================

const ERROR_DEDUP_WINDOW = 30000;
const recentErrors = new Map<string, number>();

/**
 * 判断错误是否应该显示（30秒去重）
 * @param errorType 错误类型
 * @returns 是否应该显示
 */
export function shouldShowError(errorType: ErrorType): boolean {
  const now = Date.now();
  const lastShowTime = recentErrors.get(errorType);

  if (lastShowTime && now - lastShowTime < ERROR_DEDUP_WINDOW) {
    return false;
  }

  recentErrors.set(errorType, now);
  return true;
}

/**
 * 清理过期的错误记录
 */
export function clearExpiredErrors(): void {
  const now = Date.now();
  for (const [key, timestamp] of recentErrors.entries()) {
    if (now - timestamp >= ERROR_DEDUP_WINDOW) {
      recentErrors.delete(key);
    }
  }
}

// 定期清理过期记录
setInterval(clearExpiredErrors, ERROR_DEDUP_WINDOW);

// ============================================
// 静默处理判断 - AbortError等不需要提示
// ============================================

/**
 * 判断是否需要静默处理
 * @param error 错误对象
 * @returns 是否静默处理
 */
export function isSilentError(error: any): boolean {
  if (!error) return false;

  if (error.name === "AbortError") {
    return true;
  }

  if (error.message?.includes("canceled") || error.message?.includes("Cancelled")) {
    return true;
  }

  if (error.message?.includes("组件已卸载") || error.message?.includes("component unmounted")) {
    return true;
  }

  return false;
}

// ============================================
// 统一显示函数
// ============================================

/**
 * 统一显示错误/警告/成功提示
 * @param errorType 错误类型
 * @param customMessage 可选的自定义消息
 */
export function showMessage(errorType: ErrorType, customMessage?: string): void {
  const config = ERROR_CONFIG_MAP[errorType];

  if (config.silent) {
    return;
  }

  if (!shouldShowError(errorType)) {
    return;
  }

  const displayMessage = customMessage || config.message;

  switch (config.severity) {
    case "critical":
      message.error({
        content: displayMessage,
        duration: UI_CONFIG.error.duration,
      });
      break;
    case "warning":
      message.warning({
        content: displayMessage,
        duration: UI_CONFIG.warning.duration,
      });
      break;
    case "info":
      if (displayMessage) {
        message.info({
          content: displayMessage,
          duration: UI_CONFIG.info.duration,
        });
      }
      break;
  }
}

/**
 * 显示成功提示
 * @param msg 成功消息
 */
export function showSuccess(msg: string = "操作成功"): void {
  message.success({
    content: msg,
    duration: UI_CONFIG.success.duration,
  });
}

// ============================================
// 错误分类函数
// ============================================

/**
 * 根据错误对象分类错误类型
 * @param error 错误对象
 * @returns 错误类型
 */
export function classifyError(error: any): ErrorType {
  if (!error) {
    return ErrorType.UNKNOWN;
  }

  if (error.name === "AbortError") {
    return ErrorType.REQUEST_ABORT;
  }

  if (error.message?.includes("组件已卸载") || error.message?.includes("component unmounted")) {
    return ErrorType.COMPONENT_UNMOUNTED;
  }

  if (error.response?.status) {
    const status = error.response.status;
    switch (status) {
      case 401:
        return ErrorType.AUTH_401;
      case 403:
        return ErrorType.AUTH_403;
      case 404:
        return ErrorType.SESSION_NOT_FOUND;
      case 409:
        return ErrorType.SESSION_CONFLICT;
      case 429:
        return ErrorType.RATE_LIMIT_429;
      case 500:
        return ErrorType.SERVER_500;
      case 502:
        return ErrorType.SERVER_502;
      case 503:
        return ErrorType.SERVER_503;
    }
  }

  if (error.message) {
    const msg = error.message.toLowerCase();
    if (msg.includes("connection refused") || msg.includes("err_connection_refused")) {
      return ErrorType.CONNECTION_REFUSED;
    }
    if (msg.includes("connection reset") || msg.includes("err_connection_reset")) {
      return ErrorType.CONNECTION_RESET;
    }
    if (msg.includes("network") || msg.includes("fetch") || msg.includes("网络")) {
      return ErrorType.NETWORK_ERROR;
    }
    if (msg.includes("timeout") || msg.includes("超时")) {
      return ErrorType.REQUEST_TIMEOUT;
    }
    if (msg.includes("idle") || msg.includes("空闲")) {
      return ErrorType.IDLE_TIMEOUT;
    }
    if (msg.includes("quota") || msg.includes("storage") || msg.includes("存储")) {
      return ErrorType.QUOTA_EXCEEDED;
    }
  }

  if (error.error_type) {
    switch (error.error_type) {
      case "empty_response":
        return ErrorType.BACKEND_ERROR;
      case "timeout":
        return ErrorType.REQUEST_TIMEOUT;
      case "network":
        return ErrorType.NETWORK_ERROR;
      case "server":
        return ErrorType.SERVER_500;
    }
  }

  if (error.code === "ECONNABORTED") {
    return ErrorType.REQUEST_TIMEOUT;
  }

  return ErrorType.UNKNOWN;
}

// ============================================
// 错误处理结果
// ============================================

export interface ActionResult {
  handled: boolean;
  shouldContinue?: boolean;
  deleteMessage?: boolean;
  fallbackMode?: string;
  errorType?: ErrorType;
}

// ============================================
// 统一错误处理入口
// ============================================

export interface ErrorContext {
  source?: "api" | "sse" | "manual";
  onRetry?: () => void;
  continueOnError?: boolean;
}

/**
 * 统一错误处理入口
 * @param error 原始错误对象
 * @param context 错误上下文
 * @returns 处理结果
 */
export function handleError(error: any, context: ErrorContext = {}): ActionResult {
  if (isSilentError(error)) {
    return { handled: true };
  }

  const errorType = classifyError(error);
  const config = ERROR_CONFIG_MAP[errorType];

  showMessage(errorType);

  const result: ActionResult = {
    handled: true,
    errorType,
  };

  if (config.deleteMessage) {
    result.deleteMessage = true;
  }

  if (config.fallbackMode) {
    result.fallbackMode = config.fallbackMode;
  }

  if (config.continueOnError || context.continueOnError) {
    result.shouldContinue = true;
  }

  if (config.retryable && context.onRetry) {
    let retryCount = 0;
    const maxRetries = config.maxRetries;

    const retry = () => {
      if (retryCount < maxRetries) {
        retryCount++;
        const delay = config.retryDelay * Math.pow(config.retryBackoff || 1, retryCount - 1);
        setTimeout(() => {
          context.onRetry?.();
        }, delay);
      }
    };

    retry();
  }

  return result;
}

// ============================================
// API错误处理
// ============================================

/**
 * API错误处理函数
 * @param error axios错误对象
 * @param options 选项
 */
export function handleApiError(
  error: any,
  options?: {
    onRetry?: () => void;
    showError?: boolean;
  }
): ActionResult {
  if (isSilentError(error)) {
    return { handled: true };
  }

  const errorType = classifyError(error);
  const config = ERROR_CONFIG_MAP[errorType];

  if (options?.showError !== false) {
    showMessage(errorType);
  }

  const result: ActionResult = {
    handled: true,
    errorType,
  };

  if (config.continueOnError) {
    result.shouldContinue = true;
  }

  if (config.retryable && options?.onRetry) {
    let retryCount = 0;
    const maxRetries = config.maxRetries;

    const retry = () => {
      if (retryCount < maxRetries) {
        retryCount++;
        setTimeout(() => {
          options?.onRetry?.();
        }, config.retryDelay);
      }
    };

    retry();
  }

  return result;
}

// ============================================
// SSE错误处理
// ============================================

export interface SSEErrorContext {
  reconnectAttempts: number;
  maxRetries?: number;
  onReconnect?: () => void;
}

/**
 * SSE错误处理函数
 * @param error SSE错误对象
 * @param context SSE错误上下文
 */
export function handleSSEError(error: any, context: SSEErrorContext): ActionResult {
  if (isSilentError(error)) {
    return { handled: true };
  }

  const errorType = classifyError(error);
  const config = ERROR_CONFIG_MAP[errorType];

  const maxRetries = context.maxRetries ?? config.maxRetries;
  const canRetry = config.retryable && context.reconnectAttempts < maxRetries;

  if (canRetry) {
    const retryMessage = `正在重试 (${context.reconnectAttempts + 1}/${maxRetries})...`;
    message.warning(retryMessage);

    if (context.onReconnect) {
      const delay = config.retryDelay * Math.pow(config.retryBackoff || 2, context.reconnectAttempts);
      setTimeout(() => {
        context.onReconnect?.();
      }, delay);
    }

    return { handled: true, errorType };
  }

  showMessage(errorType);

  return {
    handled: true,
    errorType,
  };
}

// ============================================
// 特殊场景处理函数
// ============================================

/**
 * 处理危险操作
 */
export function handleDangerousOperation(): ActionResult {
  showMessage(ErrorType.DANGEROUS_OPERATION);
  return {
    handled: true,
    deleteMessage: true,
    errorType: ErrorType.DANGEROUS_OPERATION,
  };
}

/**
 * 处理安全服务降级
 */
export function handleSecurityServiceDown(): ActionResult {
  showMessage(ErrorType.SECURITY_SERVICE_DOWN);
  return {
    handled: true,
    fallbackMode: "normal",
    errorType: ErrorType.SECURITY_SERVICE_DOWN,
  };
}

/**
 * 处理用户消息保存失败但继续发送
 */
export function handleUserMessageSaveFailed(): ActionResult {
  showMessage(ErrorType.USER_MESSAGE_SAVE_FAILED);
  return {
    handled: true,
    shouldContinue: true,
    errorType: ErrorType.USER_MESSAGE_SAVE_FAILED,
  };
}

/**
 * 处理重复点击
 */
export function handleDuplicateClick(): ActionResult {
  showMessage(ErrorType.DUPLICATE_CLICK);
  return {
    handled: true,
    shouldContinue: false,
    errorType: ErrorType.DUPLICATE_CLICK,
  };
}

/**
 * 处理存储满
 */
export function handleQuotaExceeded(): ActionResult {
  showMessage(ErrorType.QUOTA_EXCEEDED);
  return {
    handled: true,
    errorType: ErrorType.QUOTA_EXCEEDED,
  };
}

// ============================================
// 导出所有函数
// ============================================

export default {
  ErrorType,
  UI_CONFIG,
  ERROR_CONFIG_MAP,
  classifyError,
  shouldShowError,
  isSilentError,
  showMessage,
  showSuccess,
  handleError,
  handleApiError,
  handleSSEError,
  handleDangerousOperation,
  handleSecurityServiceDown,
  handleUserMessageSaveFailed,
  handleDuplicateClick,
  handleQuotaExceeded,
};