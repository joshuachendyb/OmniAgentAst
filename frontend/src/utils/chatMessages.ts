/**
 * 聊天消息提示工具函数
 * 
 * 统一管理NewChatContainer中的message.success/error/warning调用
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-03-13
 */

import { message } from "antd";

// ============================================================
// 成功提示
// ============================================================

export const showSaveSuccess = (content: string = "保存成功") => {
  message.success(content);
};

export const showLoadSuccess = (content: string = "加载成功") => {
  message.success(content);
};

export const showOperationSuccess = (content: string = "操作成功") => {
  message.success(content);
};

// ============================================================
// 错误提示
// ============================================================

export const showSaveError = (content: string = "保存失败，请重试") => {
  message.error({
    content,
    duration: 5,
  });
};

export const showLoadError = (content: string = "加载失败，请检查网络") => {
  message.error({
    content,
    duration: 5,
  });
};

export const showNetworkError = (content: string = "网络连接异常，请检查网络后重试") => {
  message.error(content);
};

export const showConflictError = (content: string = "数据冲突，请刷新页面") => {
  message.error(content);
};

export const showSessionConflict = () => {
  message.error("会话已被其他用户修改，请刷新页面");
};

export const showError = (content: string) => {
  message.error(content);
};

// ============================================================
// 警告提示
// ============================================================

export const showWarning = (content: string) => {
  message.warning(content);
};

export const showRetryWarning = (retry: number, maxRetries: number = 3) => {
  message.warning(`保存失败，正在重试 (${retry}/${maxRetries})...`);
};

export const showInputWarning = (content: string) => {
  message.warning({
    content,
    duration: 3,
  });
};

// ============================================================
// 信息提示
// ============================================================

export const showInfo = (content: string) => {
  message.info(content);
};

export const showCachedInfo = (content: string = "已暂存到本地") => {
  message.info(content);
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
      message.success("暂停请求已发送");
    } else if (action === "resume") {
      message.success("恢复请求已发送");
    } else if (action === "interrupt") {
      message.success("任务中断请求已发送");
    }
  } else {
    if (action === "pause") {
      message.error("暂停请求失败" + (error ? `: ${error}` : ""));
    } else if (action === "resume") {
      message.error("恢复请求失败" + (error ? `: ${error}` : ""));
    } else if (action === "interrupt") {
      message.error("中断请求失败" + (error ? `: ${error}` : ""));
    }
  }
};

/**
 * 标题保存提示
 */
export const showTitleSaveResult = (
  success: boolean,
  isConflict: boolean = false
) => {
  if (success) {
    message.success("标题已保存");
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
    message.success("会话标题已更新");
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
      message.success({ content: "会话创建成功", key: "session-create" });
    } else if (action === "load") {
      message.success({ content: "会话加载成功", key: "session-load" });
    } else if (action === "refresh") {
      message.success("会话刷新成功");
    }
  } else {
    if (action === "create") {
      message.error(`创建会话失败${error ? `: ${error}` : ""}`);
    } else if (action === "load") {
      showLoadError();
    } else if (action === "refresh") {
      showLoadError("刷新会话失败");
    }
  }
};
