/**
 * 应用全局状态上下文 - AppContext.tsx
 *
 * 功能：使用React Context API缓存全局API数据，避免重复调用
 * 缓存数据：会话数量、模型列表、服务状态、验证结果
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-03-12
 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from "react";
import { configApi, chatApi, sessionApi } from "../services/api";
import type { ValidateResponse } from "../services/api";

/**
 * 模型数据类型
 */
interface ModelData {
  id: number;
  provider: string;
  model: string;
  display_name: string;
  current_model: boolean;
}

/**
 * 验证结果类型
 */
interface ValidationResult {
  success: boolean;
  provider: string;
  model: string;
  message: string;
  errors: string[];
  warnings: string[];
}

/**
 * 应用全局状态类型
 */
interface AppState {
  // 会话数量
  sessionCount: number;
  sessionCountLoading: boolean;

  // 模型列表
  modelList: ModelData[];
  modelListLoading: boolean;

  // 服务状态
  serviceStatus: ValidateResponse | null;
  serviceStatusLoading: boolean;

  // 验证结果
  validationResult: ValidationResult | null;
  validationLoading: boolean;

  // 标记是否已初始化（防止重复加载）
  isInitialized: boolean;
}

/**
 * 应用全局上下文类型
 */
interface AppContextType extends AppState {
  // Actions
  refreshSessionCount: () => Promise<void>;
  refreshModelList: () => Promise<void>;
  refreshServiceStatus: () => Promise<ValidateResponse | null>;
  refreshAll: () => Promise<void>;
  refreshAfterModelChange: () => Promise<void>;
  initializeApp: () => Promise<void>;
}

/**
 * 创建上下文
 */
const AppContext = createContext<AppContextType | null>(null);

/**
 * 应用全局状态Provider组件
 *
 * @param children 子组件
 * @author 小新
 */
export const AppProvider: React.FC<{ children: ReactNode }> = ({
  children,
}) => {
  // ==================== State ====================

  // 会话数量
  const [sessionCount, setSessionCount] = useState(0);
  const [sessionCountLoading, setSessionCountLoading] = useState(false);

  // 模型列表
  const [modelList, setModelList] = useState<ModelData[]>([]);
  const [modelListLoading, setModelListLoading] = useState(false);

  // 服务状态
  const [serviceStatus, setServiceStatus] = useState<ValidateResponse | null>(
    null
  );
  const [serviceStatusLoading, setServiceStatusLoading] = useState(false);

  // 验证结果
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(
    null
  );
  const [validationLoading, setValidationLoading] = useState(false);

  // 标记是否已初始化
  const [isInitialized, setIsInitialized] = useState(false);

  // 标记初始化是否正在进行中（防止React Strict Mode重复调用）
  const initInProgressRef = useRef(false);

  // ==================== Actions ====================

  /**
   * 刷新会话数量
   * @author 小新
   */
  const refreshSessionCount = useCallback(async () => {
    setSessionCountLoading(true);
    try {
      const response = await sessionApi.listSessions(1, 1, undefined, true);
      setSessionCount(response.total);
    } catch (error) {
      console.warn("刷新会话数量失败:", error);
      setSessionCount(0);
    } finally {
      setSessionCountLoading(false);
    }
  }, []);

  /**
   * 刷新模型列表
   * @author 小新
   */
  const refreshModelList = useCallback(async () => {
    setModelListLoading(true);
    try {
      const modelData = await configApi.getModelList();
      // 【小新修复 2026-03-14】添加可选链检查，避免 modelData 为 null 时报错
      if (modelData?.models && Array.isArray(modelData.models)) {
        setModelList(modelData.models);
      } else {
        console.warn("getModelList 返回数据格式异常:", modelData);
        setModelList([]);
      }
    } catch (error) {
      console.warn("刷新模型列表失败:", error);
      setModelList([]);
    } finally {
      setModelListLoading(false);
    }
  }, []);

  /**
   * 刷新服务状态
   * @author 小新
   */
  const refreshServiceStatus = useCallback(async (): Promise<ValidateResponse | null> => {
    setServiceStatusLoading(true);
    try {
      const status = await chatApi.validateService();
      setServiceStatus(status);
      return status;
    } catch (error) {
      console.warn("刷新服务状态失败:", error);
      setServiceStatus(null);
      return null;
    } finally {
      setServiceStatusLoading(false);
    }
  }, []);

  /**
   * 刷新验证结果
   * @author 小新
   */
  const refreshValidation = useCallback(async () => {
    setValidationLoading(true);
    try {
      // validateConfig 需要 provider 参数，暂时跳过验证
      // 验证功能在 Settings 页面使用单独的 validateConfig 调用
      setValidationResult(null);
    } catch (error) {
      console.warn("刷新验证结果失败:", error);
      setValidationResult(null);
    } finally {
      setValidationLoading(false);
    }
  }, []);

  /**
   * 刷新所有数据（并行方法）
   * @author 小新
   */
  const refreshAll = useCallback(async () => {
    await Promise.all([
      refreshSessionCount(),
      refreshModelList(),
      refreshServiceStatus(),
      refreshValidation(),
    ]);
  }, [refreshSessionCount, refreshModelList, refreshServiceStatus, refreshValidation]);

  /**
   * 串行刷新方法（解决时序问题）
   * 先验证服务，成功后再刷新列表
   * 用于切换模型后的状态刷新
   * @author 小新
   */
  const refreshAfterModelChange = useCallback(async () => {
    // 1. 先刷新服务状态（会验证新配置是否有效）
    const status = await refreshServiceStatus();
    
    // 2. 根据验证结果决定是否刷新列表
    // refreshServiceStatus 返回验证后的 status
    // 如果验证成功，status 不为 null
    // 如果验证失败，status 为 null，此时不刷新列表
    
    // 3. 只有验证成功才刷新模型列表（获取最新的 current_model 标记）
    if (status) {
      await Promise.all([
        refreshModelList(),
        refreshSessionCount(),
      ]);
    }
  }, [refreshServiceStatus, refreshModelList, refreshSessionCount]);

  /**
   * 初始化应用（只在首次加载时调用）
   * 按正确顺序调用API，确保依赖关系
   * @author 小新
   */
  const initializeApp = useCallback(async () => {
    // 防止重复调用（React Strict Mode会导致useEffect运行两次）
    if (initInProgressRef.current) {
      console.log("[AppContext] 初始化进行中，跳过");
      return;
    }
    if (isInitialized) {
      console.log("[AppContext] 已初始化，跳过");
      return;
    }

    initInProgressRef.current = true;
    console.log("[AppContext] 开始初始化...");
    setValidationLoading(true);
    setModelListLoading(true);
    setServiceStatusLoading(true);
    setSessionCountLoading(true);

    try {
      // 1. 先验证完整配置
      // validateConfig 需要 provider 参数，暂时跳过验证
      setValidationResult(null);

      // 2. 并行获取所有数据
      await Promise.all([
        refreshModelList(),
        refreshServiceStatus(),
        refreshSessionCount(),
      ]);
      
      setIsInitialized(true);
      console.log("[AppContext] 初始化完成");
    } catch (error) {
      console.error("[AppContext] 初始化失败:", error);
    } finally {
      initInProgressRef.current = false;
      setValidationLoading(false);
      setModelListLoading(false);
      setServiceStatusLoading(false);
      setSessionCountLoading(false);
    }
  }, [isInitialized]);

  // ==================== Context Value ====================
  const value: AppContextType = {
    // State
    sessionCount,
    sessionCountLoading,
    modelList,
    modelListLoading,
    serviceStatus,
    serviceStatusLoading,
    validationResult,
    validationLoading,
    isInitialized,

    // Actions
    refreshSessionCount,
    refreshModelList,
    refreshServiceStatus,
    refreshAll,
    refreshAfterModelChange,
    initializeApp,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};

/**
 * 使用应用全局上下文的Hook
 *
 * @returns 应用全局上下文
 * @throws 如果在Provider外使用会抛出错误
 * @author 小新
 */
export const useApp = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
};

export default AppContext;
