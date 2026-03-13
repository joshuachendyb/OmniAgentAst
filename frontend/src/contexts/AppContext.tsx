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
  refreshServiceStatus: () => Promise<void>;
  refreshAll: () => Promise<void>;
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
      if (modelData.models) {
        setModelList(modelData.models);
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
  const refreshServiceStatus = useCallback(async () => {
    setServiceStatusLoading(true);
    try {
      const status = await chatApi.validateService();
      setServiceStatus(status);
    } catch (error) {
      console.warn("刷新服务状态失败:", error);
      setServiceStatus(null);
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
      const validation = await configApi.validateFullConfig();
      setValidationResult(validation);
    } catch (error) {
      console.warn("刷新验证结果失败:", error);
      setValidationResult(null);
    } finally {
      setValidationLoading(false);
    }
  }, []);

  /**
   * 刷新所有数据（组合方法）
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
      let validation: ValidationResult;
      try {
        validation = await configApi.validateFullConfig();
        setValidationResult(validation);
      } catch (err) {
        console.warn("配置验证失败:", err);
        validation = {
          success: false,
          provider: "",
          model: "",
          message: "配置验证接口调用失败",
          errors: ["配置验证接口调用失败"],
          warnings: [],
        };
        setValidationResult(validation);
      }

      // 2. 验证成功才获取模型列表
      if (!validation || !validation.success) {
        setModelList([]);
        setServiceStatus(null);
        setSessionCount(0);
        setIsInitialized(true);
        return;
      }

      // 3. 并行获取模型列表和服务状态
      const [modelData, status] = await Promise.all([
        configApi.getModelList(),
        chatApi.validateService(),
      ]);

      if (modelData.models) {
        setModelList(modelData.models);
      }
      setServiceStatus(status);

      // 4. 获取会话数量
      try {
        const sessionData = await sessionApi.listSessions(1, 1, undefined, true);
        setSessionCount(sessionData.total);
      } catch (err) {
        console.warn("获取会话数量失败:", err);
        setSessionCount(0);
      }

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
