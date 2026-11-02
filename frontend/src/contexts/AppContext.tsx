// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复引号风格(双→单)、尾逗号移除、缩进统一(2空格)、空行压缩, 防止格式再次出错
// 编辑历史: 2026-09-09 小欧 - 会话页console日志治理(北京老陈指示「该清理的清理」): refreshServiceStatus 删「validateService 返回」打点
//   ——整 status 对象打印属调试残留, 已 setServiceStatus(status) 承接状态, 打点无追踪增量价值 — 小欧-2026-09-09
// 编辑历史: 2026-09-24 19:15:07 小欧 - DRY收口: 新增 switchAndRefreshModel — 切全局模型API+成功/失败刷新收口到一处,
//   顶栏 Layout.handleModelChange 与设置页 CurrentModelRefCard.onOk 两调用方只管展示逻辑, 杜绝再漏刷 modelList — 小欧-2026-09-24
// 编辑历史: 2026-11-02 小欧 - 三堂会审死链删除: validationResult/validationLoading/refreshValidation/refreshAll/ValidationResult五件全清(只被写null+死Tag恒false, 零消费方) — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 状态跟随: refreshAfterModelChange 并刷 refreshServiceStatus(零成本本地校验, 非旧外部AI API验证), 切模型后顶栏胶囊即随新配置 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 新增 healthStatus/refreshHealth: 顶栏服务胶囊状态源(/health应答与耗时), 与 serviceStatus(配置校验)分立不合流 — 小欧-2026-11-02
/**
 * 应用全局状态上下文 - AppContext.tsx
 *
 * 功能：使用React Context API缓存全局API数据，避免重复调用
 * 缓存数据：会话数量、模型列表、服务状态
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-03-12
 */

/* 2026-11-02 小欧 - 三堂会审死链删除: validationResult/validationLoading/refreshValidation/refreshAll/ValidationResult类型 五件全死(validationResult仅被写null, 锚注L209"validateConfig需要provider参数暂时跳过"), 连带壳层死Tag/ValidationDetailModal一并清: 删前会审实勘, 零行为变化 - 小欧-2026-11-02 */

import React, {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  ReactNode,
} from 'react';
import { configApi } from '../services/api/config.api';
import { chatApi, type ValidateResponse } from '../services/api/chat.api';
import { healthApi, type HealthStatus } from '../services/api/health.api';
import { sessionApi } from '../services/api/session.api';
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

  // 后端服务存活(/health: 应答+耗时), 与上面配置校验语义分立 — 2026-11-02 小欧
  healthStatus: HealthStatus | null;

  // 标记是否已初始化（防止重复加载）
  isInitialized: boolean;

  // 标记初始化错误
  initError: string | null;
}

/**
 * 应用全局上下文类型
 */
interface AppContextType extends AppState {
  // Actions
  refreshSessionCount: () => Promise<void>;
  refreshModelList: () => Promise<void>;
  refreshServiceStatus: () => Promise<ValidateResponse | null>;
  refreshHealth: () => Promise<HealthStatus | null>;
  refreshAfterModelChange: () => Promise<void>;
  // 2026-09-24 小欧 - 切全局模型收口入口: API调用+成功/失败刷新内置, 调用方不再各记刷新
  switchAndRefreshModel: (
    provider: string,
    model: string
  ) => Promise<{ success: boolean; message: string }>;
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

  // 后端服务存活(/health) — 2026-11-02 小欧
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);

  // 标记是否已初始化
  const [isInitialized, setIsInitialized] = useState(false);

  // 标记初始化错误
  const [initError, setInitError] = useState<string | null>(null);

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
      console.warn('刷新会话数量失败:', error);
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
        console.warn('getModelList 返回数据格式异常:', modelData);
        setModelList([]);
      }
    } catch (error) {
      console.warn('刷新模型列表失败:', error);
      setModelList([]);
    } finally {
      setModelListLoading(false);
    }
  }, []);

  /**
   * 刷新服务状态
   * @author 小新
   */
  const refreshServiceStatus =
    useCallback(async (): Promise<ValidateResponse | null> => {
      setServiceStatusLoading(true);
      try {
        const status = await chatApi.validateService();
        setServiceStatus(status);
        return status;
      } catch (error) {
        console.warn('刷新服务状态失败:', error);
        setServiceStatus(null);
        return null;
      } finally {
        setServiceStatusLoading(false);
      }
    }, []);

  /**
   * 刷新后端服务存活状态(/health) — 2026-11-02 小欧
   * 只探"后端能不能应答", 不看配置内容也不看DB; 失败置 null 由视图派生离线态
   */
  const refreshHealth = useCallback(async (): Promise<HealthStatus | null> => {
    try {
      const health = await healthApi.checkHealth();
      setHealthStatus(health);
      return health;
    } catch (error) {
      console.warn('刷新后端服务状态失败:', error);
      setHealthStatus(null);
      return null;
    }
  }, []);

  /**
   * 串行刷新方法（解决时序问题）
   * 用于切换模型后的状态刷新
   * @author 小新
   * @update 2026-04-07 小强修复：不再调用 refreshServiceStatus() 实际调用AI API验证
   *         直接用 _validate_config_integrity 结果（后端已处理），只刷新模型列表获取打*信息
   */
  const refreshAfterModelChange = useCallback(async () => {
    // ============================================================
    // 【小强修复 2026-04-07】
    // 修改说明：
    // 之前：先调用 refreshServiceStatus() 实际调用AI API验证新配置
    // 现在：不再调用AI API验证，直接刷新模型列表
    //
    // 原因：用户要求切换模型时不再调用外部AI API做验证，
    //       后端 update_config 已使用 _validate_config_integrity 结果
    //       决定是否删除备份，前端只需刷新模型列表获取打*信息
    // ============================================================

    // 2026-11-02 小欧 - 状态跟随: 切模型后配置状态胶囊同步刷新(零成本本地校验, 非旧"外部AI API验证"), 杜绝滞留旧态 — 小欧-2026-11-02
    // 1. 刷新模型列表（后端已验证配置文件完整性）+ 配置状态（顶栏胶囊）
    await Promise.all([refreshModelList(), refreshServiceStatus()]);
  }, [refreshModelList, refreshServiceStatus]);

  // 2026-09-24 小欧 - DRY收口: 切全局模型唯一入口, 成功→refreshAfterModelChange刷★,
  //   失败→后端已回滚刷列表; 两调用方(顶栏/设置页)只传provider/model, 不再各记刷新 — 小欧-2026-09-24
  const switchAndRefreshModel = useCallback(
    async (
      provider: string,
      model: string
    ): Promise<{ success: boolean; message: string }> => {
      const r = await configApi.switchCurrentModel(provider, model);
      if (r.success) {
        await refreshAfterModelChange();
      } else {
        // 切换失败时后端已回滚配置，刷新模型列表获取回滚后的模型
        await refreshModelList();
      }
      return r;
    },
    [refreshAfterModelChange, refreshModelList]
  );

  /**
   * 初始化应用（只在首次加载时调用）
   * 按正确顺序调用API，确保依赖关系
   * @author 小新
   */
  const initializeApp = useCallback(async () => {
    // 防止重复调用（React Strict Mode会导致useEffect运行两次）
    if (initInProgressRef.current) {
      return;
    }
    // 如果有错误，允许重试初始化
    if (isInitialized && !initError) {
      return;
    }

    // 如果是重试，先重置状态
    if (initError) {
      setIsInitialized(false);
      setInitError(null);
    }

    initInProgressRef.current = true;
    setInitError(null); // 重置错误状态
    setModelListLoading(true);
    setServiceStatusLoading(true);
    setSessionCountLoading(true);

    try {
      // 1. 只获取模型列表和会话数，不调用验证服务（由用户手动点击"检查服务"按钮）
      await Promise.all([refreshModelList(), refreshSessionCount()]);

      setIsInitialized(true);
      console.log('[AppContext] 初始化完成');
    } catch (error) {
      console.error('[AppContext] 初始化失败:', error);
      const errorMsg =
        error instanceof Error ? error.message : '初始化失败，请检查网络连接';
      setInitError(errorMsg);
    } finally {
      initInProgressRef.current = false;
      setModelListLoading(false);
      setServiceStatusLoading(false);
      setSessionCountLoading(false);
    }
  }, [isInitialized, initError, refreshModelList, refreshSessionCount]);

  // ==================== Context Value ====================
  const value: AppContextType = {
    // State
    sessionCount,
    sessionCountLoading,
    modelList,
    modelListLoading,
    serviceStatus,
    serviceStatusLoading,
    healthStatus,
    isInitialized,
    initError,

    // Actions
    refreshSessionCount,
    refreshModelList,
    refreshServiceStatus,
    refreshHealth,
    refreshAfterModelChange,
    switchAndRefreshModel,
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
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};

export default AppContext;
