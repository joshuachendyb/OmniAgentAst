/**
 * 聊天消息提示工具函数
 *
 * 统一管理NewChatContainer中的message.success/error/warning调用
 *
 * 错误处理说明：
 * - 所有错误提示统一使用 errorHandler 处理
 * - 禁止直接调用 message.error/warning/success/info
 * - 本文件是errorHandler的包装层，内部调用handleError/showSuccess
 *
 * @author 小新
 * @version 1.2.0
 * @since 2026-03-13
 * @update 2026-04-11 迁移到errorHandler统一处理 - by 小强
 */

import { message } from "antd";
import { ErrorType, showSuccess, handleError, classifyError, showMessage, UI_CONFIG } from "./errorHandler";

// ============================================================
// 成功提示
// ============================================================

export const showSaveSuccess = (content: string = "保存成功") => {
  showSuccess(content);
};

export const showLoadSuccess = (content: string = "加载成功") => {
  showSuccess(content);
};

export const showOperationSuccess = (content: string = "操作成功") => {
  showSuccess(content);
};

// ============================================================
// 错误提示
// ============================================================

export const showSaveError = (content: string = "保存失败，请重试") => {
  handleError({ message: content, error_type: ErrorType.SAVE_FAILED });
};

export const showLoadError = (content: string = "加载失败，请检查网络") => {
  handleError({ message: content, error_type: ErrorType.LOAD_FAILED });
};

export const showLoadRetryWarning = (retry: number, maxRetries: number = 3, key?: string) => {
  const content = `加载失败，正在重试 (${retry}/${maxRetries})...`;
  handleError({ message: content, error_type: ErrorType.RETRY_WARNING });
};

export const showLoadErrorWithKey = (content: string = "加载失败，请检查网络后重试", key?: string) => {
  handleError({ message: content, error_type: ErrorType.LOAD_FAILED });
};

export const showNetworkError = (content: string = "网络连接异常，请检查网络后重试") => {
  handleError({ message: content, error_type: ErrorType.NETWORK_ERROR });
};

export const showConflictError = (content: string = "数据冲突，请刷新页面") => {
  handleError({ message: content, error_type: ErrorType.SESSION_CONFLICT });
};

export const showSessionConflict = () => {
  handleError({ message: "会话已被其他用户修改，请刷新页面", error_type: ErrorType.SESSION_CONFLICT });
};

export const showError = (content: string) => {
  const errorType = classifyError({ message: content });
  showMessage(errorType, content);
};

// ============================================================
// 警告提示
// ============================================================

export const showWarning = (content: string) => {
  handleError({ message: content, error_type: ErrorType.WARNING });
};

export const showRetryWarning = (retry: number, maxRetries: number = 3) => {
  const content = `保存失败，正在重试 (${retry}/${maxRetries})...`;
  handleError({ message: content, error_type: ErrorType.RETRY_WARNING });
};

export const showInputWarning = (content: string) => {
  handleError({ message: content, error_type: ErrorType.WARNING });
};

// ============================================================
// 信息提示
// ============================================================

export const showInfo = (content: string) => {
  showMessage(ErrorType.INFO, content);
};

export const showCachedInfo = (content: string = "已暂存到本地") => {
  showMessage(ErrorType.INFO, content);
};

// ============================================================
// 特殊场景提示
// ============================================================

/**
 * 409版本冲突处理
 */
export const handleConflictError = (error: any): boolean => {
  if (error?.response?.status === 409) {
    showConflictError();
    return true;
  }
  return false;
};

/**
 * 保存失败并本地缓存
 */
export const handleSaveErrorWithCache = async (
  currentSessionId: string,
  data: any,
  dataType: "message" | "title",
  errorMsg: string = "保存失败"
) => {
  showSaveError(errorMsg);
  
  try {
    const cacheKey = `unsaved_${dataType}_${currentSessionId}`;
    const cached = JSON.parse(localStorage.getItem(cacheKey) || "[]");
    
    // 避免重复缓存
    const exists = cached.some((item: any) => {
      if (dataType === "message") {
        return item.assistant === data;
      }
      return item.title === data;
    });
    
    if (!exists) {
      cached.push({
        ...data,
        timestamp: Date.now(),
      });
      localStorage.setItem(cacheKey, JSON.stringify(cached));
      showCachedInfo();
    }
  } catch (cacheError) {
    console.error("本地缓存失败:", cacheError);
  }
};

/**
 * 任务控制提示
 */
export const showTaskControlMessage = (
  action: "pause" | "resume" | "interrupt",
  success: boolean,
  error?: string
) => {
  if (success) {
    if (action === "pause") {
      showSuccess("暂停请求已发送");
    } else if (action === "resume") {
      showSuccess("恢复请求已发送");
    } else if (action === "interrupt") {
      showSuccess("任务中断请求已发送");
    }
  } else {
    if (action === "pause") {
      handleError({ message: `暂停请求失败${error ? `: ${error}` : ""}`, error_type: ErrorType.TASK_CONTROL_FAILED });
    } else if (action === "resume") {
      handleError({ message: `恢复请求失败${error ? `: ${error}` : ""}`, error_type: ErrorType.TASK_CONTROL_FAILED });
    } else if (action === "interrupt") {
      handleError({ message: `中断请求失败${error ? `: ${error}` : ""}`, error_type: ErrorType.TASK_CONTROL_FAILED });
    }
  }
};

/**
 * 显示后端返回的任务控制消息（带动态内容）
 */
export const showTaskResultMessage = (action: "pause" | "resume" | "interrupt", resultMessage?: string) => {
  const defaultMessages = {
    pause: "任务已暂停",
    resume: "任务已继续",
    interrupt: "任务中断请求已发送",
  };
  showSuccess(resultMessage || defaultMessages[action]);
};

/**
 * 显示任务控制中的信息提示
 */
export const showTaskControlInfo = (content: string) => {
  showInfo(content);
};

/**
 * 显示没有进行中任务的警告
 */
export const showNoActiveTaskWarning = () => {
  showWarning("当前没有进行中的任务");
};

/**
 * 危险命令取消提示
 */
export const showDangerCancelled = () => {
  showInfo("已取消危险命令的执行");
};

/**
 * 新建会话成功提示
 */
export const showNewSessionSuccess = (title: string) => {
  showSuccess(`已创建新会话: ${title}`);
};

/**
 * 新建会话重试警告
 */
export const showNewSessionRetryWarning = (retry: number, maxRetries: number = 3) => {
  const content = `创建会话失败，正在重试 (${retry}/${maxRetries})...`;
  handleError({ message: content, error_type: ErrorType.RETRY_WARNING });
};

/**
 * 新建会话失败错误
 */
export const showNewSessionError = (errorMsg: string = "未知错误") => {
  handleError({ message: `创建会话失败: ${errorMsg}`, error_type: ErrorType.CREATE_SESSION_FAILED });
};

/**
 * 标题保存成功提示
 */
export const showTitleSaved = () => {
  showSuccess("标题已保存");
};

/**
 * 标题更新成功提示
 */
export const showTitleUpdated = () => {
  showSuccess("会话标题已更新");
};

/**
 * 标题保存提示
 */
export const showTitleSaveResult = (
  success: boolean,
  isConflict: boolean = false
) => {
  if (success) {
    showSuccess("标题已保存");
  } else if (isConflict) {
    showSessionConflict();
  } else {
    showSaveError("保存标题失败，请重试");
  }
};

/**
 * 标题更新提示
 */
export const showTitleUpdateResult = (
  success: boolean,
  isConflict: boolean = false
) => {
  if (success) {
    showSuccess("会话标题已更新");
  } else if (isConflict) {
    showSessionConflict();
  } else {
    showSaveError("更新标题失败");
  }
};

/**
 * 会话操作提示
 */
export const showSessionResult = (
  action: "create" | "load" | "refresh",
  success: boolean,
  error?: string
) => {
  if (success) {
    if (action === "create") {
      showSuccess("会话创建成功");
    } else if (action === "load") {
      showSuccess("会话加载成功");
    } else if (action === "refresh") {
      showSuccess("会话刷新成功");
    }
  } else {
    if (action === "create") {
      handleError({ message: `创建会话失败${error ? `: ${error}` : ""}`, error_type: ErrorType.CREATE_SESSION_FAILED });
    } else if (action === "load") {
      showLoadError();
    } else if (action === "refresh") {
      showLoadError("刷新会话失败");
    }
  }
};
