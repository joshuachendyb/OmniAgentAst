# 前端-MessageItem优化实施详细方案

**创建时间**: 2026-04-20 21:30:00
**版本**: v1.0
**编写人**: CodeArts代码智能体
**分析范围**: frontend/src/components/Chat/MessageItem.tsx
**目标**: 提供可立即实施的、分阶段的优化方案

---

## 一、当前问题分析（已验证）

基于对代码的深入分析，确认以下6个性能问题确实存在：

### 1.1 内联样式重复创建 ✅ **确认存在**
**位置**: MessageItem.tsx 第123-132行
```typescript
// 问题代码 - 每次渲染都创建新对象
const getContentStyle = () => {
  const baseStyle: React.CSSProperties = {
    color: "#333",
    wordBreak: "break-word",
    fontSize: 13,
    lineHeight: 1.8,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
  };
  return baseStyle;
};
```

### 1.2 StepRow组件过大 ✅ **确认存在**
**位置**: MessageItem.tsx 第75-602行
- 总行数: 527行
- 包含8种type的渲染逻辑: start/thought/action_tool/observation/chunk/final/error/incident
- 功能混杂: 步骤编号、标签图标、类型特定内容、工具信息、分页控制、状态显示

### 1.3 renderToolResult函数过长 ✅ **确认存在**
**位置**: MessageItem.tsx 第610-659行
- 总行数: 50行
- 7种工具类型: list_directory, read_file, write_file, delete_file, move_file, search_files, search_file_content
- 与StepRow组件强耦合

### 1.4 匿名函数重复创建 ✅ **确认存在**
**位置**: 
- 第208-215行: onMouseEnter/onMouseLeave
- 第242-252行: IIFE包装的渲染逻辑
- 第267-272行: onClick处理

### 1.5 useState过多（NewChatContainer） ✅ **确认存在**
**位置**: NewChatContainer.tsx 第108-230行
- 已确认有20+个useState状态
- 状态管理复杂，逻辑分散

### 1.6 labelMap/iconMap重复定义 ✅ **确认存在**
**位置**: MessageItem.tsx 第82-108行
```typescript
// 每次StepRow渲染都重新创建这两个Map对象
const labelMap: Record<string, string> = { /* ... */ };
const iconMap: Record<string, string> = { /* ... */ };
```

---

## 二、优化实施原则

### 2.1 实施原则
1. **渐进式优化**：分阶段实施，每阶段可独立验证
2. **向后兼容**：不破坏现有功能
3. **性能优先**：优先解决影响渲染性能的问题
4. **代码可维护**：提高代码可读性和可维护性

### 2.2 验收标准
- ✅ 功能测试通过
- ✅ 性能提升可测量
- ✅ 代码复杂度降低
- ✅ 类型安全增强

---

## 三、分阶段实施计划

### 阶段1：快速优化（1-2天）
**目标**: 立即见效的性能优化，无需重构架构

#### 3.1.1 提取labelMap/iconMap为常量
**实施步骤**:
1. 创建 `src/components/Chat/constants/stepConstants.ts`
2. 提取labelMap和iconMap
3. 在StepRow中引用

**代码示例**:
```typescript
// src/components/Chat/constants/stepConstants.ts
export const STEP_LABEL_MAP: Record<string, string> = {
  start: "开始",
  thought: "思考",
  action_tool: "执行",
  observation: "观察",
  final: "完成",
  error: "错误",
  paused: "暂停",
  resumed: "恢复",
  interrupted: "中断",
  retrying: "重试",
  incident: "事件",
};

export const STEP_ICON_MAP: Record<string, string> = {
  start: "🚀",
  thought: "💭",
  action_tool: "⚙️",
  observation: "📋",
  final: "✅",
  error: "❌",
  paused: "⏸️",
  resumed: "▶️",
  interrupted: "⚠️",
  retrying: "🔄",
  incident: "⚡",
};
```

#### 3.1.2 使用useMemo缓存样式对象
**实施步骤**:
1. 修改 `getContentStyle` 函数
2. 使用useMemo缓存样式对象

**代码示例**:
```typescript
// MessageItem.tsx 修改第123-132行
const contentStyle = useMemo(() => {
  const baseStyle: React.CSSProperties = {
    color: "#333",
    wordBreak: "break-word",
    fontSize: 13,
    lineHeight: 1.8,
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', sans-serif",
  };
  return baseStyle;
}, []); // 空依赖数组，只创建一次
```

#### 3.1.3 使用useCallback包装事件处理函数
**实施步骤**:
1. 提取匿名函数为具名函数
2. 使用useCallback包装

**代码示例**:
```typescript
// 提取第208-215行的onMouseEnter/onMouseLeave
const handleMouseEnter = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
  e.currentTarget.style.background = "rgba(0,0,0,0.04)";
  e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
}, []);

const handleMouseLeave = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
  e.currentTarget.style.background = "rgba(0,0,0,0.02)";
  e.currentTarget.style.boxShadow = "none";
}, []);

// 在JSX中使用
onMouseEnter={handleMouseEnter}
onMouseLeave={handleMouseLeave}
```

#### 3.1.4 提取重复的时间格式化函数
**实施步骤**:
1. 创建 `src/utils/timeFormatters.ts`
2. 提取重复的时间格式化逻辑

**代码示例**:
```typescript
// src/utils/timeFormatters.ts
export const formatRelativeTime = (date: Date | string | number): string => {
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    if (isNaN(dateObj.getTime())) return "刚刚";
    
    const now = new Date();
    const diff = now.getTime() - dateObj.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return "刚刚";
    if (minutes < 60) return `${minutes}分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}小时前`;
    return dateObj.toLocaleDateString("zh-CN");
  } catch (error) {
    return "刚刚";
  }
};

export const formatTime = (date: Date | string | number): string => {
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    if (isNaN(dateObj.getTime())) return "刚刚";
    
    return dateObj.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (error) {
    return "刚刚";
  }
};
```

### 阶段2：组件拆分（3-5天）
**目标**: 拆分大型组件，提高可维护性

#### 3.2.1 拆分StepRow组件
**实施步骤**:
1. 创建 `src/components/Chat/StepRow/` 目录
2. 按功能拆分组件
3. 保持类型安全

**目录结构**:
```
src/components/Chat/StepRow/
├── index.tsx              # StepRow主组件（容器）
├── StepHeader.tsx         # 步骤头部（编号、标签、图标、时间戳）
├── StepContent.tsx        # 步骤内容（根据type渲染不同内容）
├── StepFooter.tsx         # 步骤底部（状态、分页、工具信息）
├── types/                 # 按类型拆分的组件
│   ├── StartStep.tsx
│   ├── ThoughtStep.tsx
│   ├── ActionToolStep.tsx
│   ├── ObservationStep.tsx
│   ├── FinalStep.tsx
│   ├── ErrorStep.tsx
│   └── IncidentStep.tsx
└── hooks/
    └── useStepData.ts     # 数据处理hook
```

**代码示例 - StepRow/index.tsx**:
```typescript
// src/components/Chat/StepRow/index.tsx
import React from 'react';
import StepHeader from './StepHeader';
import StepContent from './StepContent';
import StepFooter from './StepFooter';
import { StepRowProps } from './types';

const StepRow: React.FC<StepRowProps> = ({ step, stepIndex, expandedSteps, toggleExpand }) => {
  const { displayData, hasMore } = useStepData(step);
  
  return (
    <div 
      style={stepContainerStyle}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <StepHeader 
        step={step}
        stepIndex={stepIndex}
        expandedSteps={expandedSteps}
        toggleExpand={toggleExpand}
      />
      
      <StepContent 
        step={step}
        isExpanded={expandedSteps.get(stepIndex) ?? true}
        displayData={displayData}
      />
      
      <StepFooter 
        step={step}
        hasMore={hasMore}
        onLoadMore={handleLoadMore}
      />
    </div>
  );
};

export default React.memo(StepRow);
```

#### 3.2.2 拆分renderToolResult函数
**实施步骤**:
1. 创建 `src/components/Chat/ToolResultRenderer/` 目录
2. 为每种工具类型创建独立组件
3. 使用工厂模式

**目录结构**:
```
src/components/Chat/ToolResultRenderer/
├── index.tsx              # 主渲染器（工厂模式）
├── types/
│   ├── ListDirectoryRenderer.tsx
│   ├── ReadFileRenderer.tsx
│   ├── WriteFileRenderer.tsx
│   ├── DeleteFileRenderer.tsx
│   ├── MoveFileRenderer.tsx
│   ├── SearchFilesRenderer.tsx
│   ├── SearchFileContentRenderer.tsx
│   └── GenerateReportRenderer.tsx
└── DefaultRenderer.tsx    # 默认渲染器（JSON显示）
```

**代码示例 - ToolResultRenderer/index.tsx**:
```typescript
// src/components/Chat/ToolResultRenderer/index.tsx
import React from 'react';
import { ExecutionStep } from '../../../utils/sse';
import ListDirectoryRenderer from './types/ListDirectoryRenderer';
import ReadFileRenderer from './types/ReadFileRenderer';
// ... 导入其他渲染器
import DefaultRenderer from './DefaultRenderer';

interface ToolResultRendererProps {
  step: ExecutionStep;
  isExpanded?: boolean;
  toggleExpand?: (index: number) => void;
  stepIndex?: number;
}

const ToolResultRenderer: React.FC<ToolResultRendererProps> = ({
  step,
  isExpanded = true,
  toggleExpand,
  stepIndex,
}) => {
  const execResult = step.execution_result;
  const data = (execResult as any)?.data || execResult;
  if (!data) return null;

  const handleToggle = toggleExpand && stepIndex !== undefined 
    ? () => toggleExpand(stepIndex) 
    : undefined;

  // 工厂模式：根据tool_name选择渲染器
  switch (step.tool_name) {
    case "list_directory":
      return <ListDirectoryRenderer data={data} toolParams={step.tool_params} isExpanded={isExpanded} onToggle={handleToggle} />;
    case "read_file":
      return <ReadFileRenderer data={data} />;
    case "write_file":
      return <WriteFileRenderer data={data} />;
    case "delete_file":
      return <DeleteFileRenderer data={data} />;
    case "move_file":
      return <MoveFileRenderer data={data} />;
    case "search_files":
      return <SearchFilesRenderer data={data} />;
    case "search_file_content":
      return <SearchFileContentRenderer data={data} />;
    case "generate_report":
      return <GenerateReportRenderer data={data} isExpanded={isExpanded} onToggle={handleToggle} />;
    default:
      return <DefaultRenderer data={data} />;
  }
};

export default React.memo(ToolResultRenderer);
```

#### 3.2.3 优化NewChatContainer状态管理
**实施步骤**:
1. 分析状态相关性，分组管理
2. 使用useReducer替代多个useState
3. 创建自定义hook管理复杂状态

**代码示例 - 状态分组**:
```typescript
// src/components/Chat/hooks/useChatState.ts
import { useReducer } from 'react';

interface ChatState {
  // 消息相关
  messages: Message[];
  loading: boolean;
  isStreaming: boolean;
  
  // 会话相关
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  
  // UI状态
  showExecution: boolean;
  useStream: boolean;
  isPaused: boolean;
  isRetrying: boolean;
  
  // 标题编辑
  editingTitle: boolean;
  titleInput: string;
  titleLocked: boolean;
  lastSavedTitle: string;
  
  // 其他状态
  waitTime: number;
  saveStatus: 'idle' | 'saving' | 'saved' | 'error';
  retryCount: Record<string, number>;
}

type ChatAction = 
  | { type: 'SET_MESSAGES'; payload: Message[] }
  | { type: 'ADD_MESSAGE'; payload: Message }
  | { type: 'UPDATE_MESSAGE'; payload: { id: string; updates: Partial<Message> } }
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_SESSION'; payload: { id: string | null; title: string; version?: number } }
  | { type: 'SET_UI_STATE'; payload: Partial<Pick<ChatState, 'showExecution' | 'useStream' | 'isPaused' | 'isRetrying'>> }
  | { type: 'SET_TITLE_EDITING'; payload: { editing: boolean; input?: string } }
  | { type: 'INCREMENT_WAIT_TIME' }
  | { type: 'RESET_WAIT_TIME' }
  | { type: 'SET_SAVE_STATUS'; payload: ChatState['saveStatus'] }
  | { type: 'INCREMENT_RETRY_COUNT'; payload: string };

const initialState: ChatState = {
  messages: [],
  loading: false,
  isStreaming: false,
  sessionId: null,
  sessionTitle: "新会话",
  sessionVersion: 1,
  showExecution: true,
  useStream: true,
  isPaused: false,
  isRetrying: false,
  editingTitle: false,
  titleInput: "",
  titleLocked: false,
  lastSavedTitle: "",
  waitTime: 0,
  saveStatus: "idle",
  retryCount: {},
};

function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'SET_MESSAGES':
      return { ...state, messages: action.payload };
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.payload] };
    case 'UPDATE_MESSAGE':
      return {
        ...state,
        messages: state.messages.map(msg => 
          msg.id === action.payload.id ? { ...msg, ...action.payload.updates } : msg
        ),
      };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_SESSION':
      return {
        ...state,
        sessionId: action.payload.id,
        sessionTitle: action.payload.title,
        sessionVersion: action.payload.version || state.sessionVersion,
      };
    case 'SET_UI_STATE':
      return { ...state, ...action.payload };
    case 'SET_TITLE_EDITING':
      return {
        ...state,
        editingTitle: action.payload.editing,
        titleInput: action.payload.input !== undefined ? action.payload.input : state.titleInput,
      };
    case 'INCREMENT_WAIT_TIME':
      return { ...state, waitTime: state.waitTime + 1 };
    case 'RESET_WAIT_TIME':
      return { ...state, waitTime: 0 };
    case 'SET_SAVE_STATUS':
      return { ...state, saveStatus: action.payload };
    case 'INCREMENT_RETRY_COUNT':
      return {
        ...state,
        retryCount: {
          ...state.retryCount,
          [action.payload]: (state.retryCount[action.payload] || 0) + 1,
        },
      };
    default:
      return state;
  }
}

export const useChatState = () => {
  const [state, dispatch] = useReducer(chatReducer, initialState);
  
  // 提供便捷的action creators
  const actions = {
    setMessages: (messages: Message[]) => dispatch({ type: 'SET_MESSAGES', payload: messages }),
    addMessage: (message: Message) => dispatch({ type: 'ADD_MESSAGE', payload: message }),
    updateMessage: (id: string, updates: Partial<Message>) => 
      dispatch({ type: 'UPDATE_MESSAGE', payload: { id, updates } }),
    setLoading: (loading: boolean) => dispatch({ type: 'SET_LOADING', payload: loading }),
    setSession: (id: string | null, title: string, version?: number) => 
      dispatch({ type: 'SET_SESSION', payload: { id, title, version } }),
    setUiState: (uiState: Partial<Pick<ChatState, 'showExecution' | 'useStream' | 'isPaused' | 'isRetrying'>>) =>
      dispatch({ type: 'SET_UI_STATE', payload: uiState }),
    setTitleEditing: (editing: boolean, input?: string) =>
      dispatch({ type: 'SET_TITLE_EDITING', payload: { editing, input } }),
    incrementWaitTime: () => dispatch({ type: 'INCREMENT_WAIT_TIME' }),
    resetWaitTime: () => dispatch({ type: 'RESET_WAIT_TIME' }),
    setSaveStatus: (status: ChatState['saveStatus']) => 
      dispatch({ type: 'SET_SAVE_STATUS', payload: status }),
    incrementRetryCount: (key: string) => 
      dispatch({ type: 'INCREMENT_RETRY_COUNT', payload: key }),
  };
  
  return { state, dispatch, actions };
};
```

### 阶段3：架构优化（1-2周）
**目标**: 提升代码质量、类型安全和可维护性

#### 3.3.1 完善类型定义
**实施步骤**:
1. 创建完整的类型定义文件
2. 消除`as any`类型断言
3. 添加类型守卫

**代码示例 - 类型定义**:
```typescript
// src/components/Chat/types/index.ts
export type StepType = 
  | 'start'
  | 'thought'
  | 'action_tool'
  | 'observation'
  | 'chunk'
  | 'final'
  | 'error'
  | 'interrupted'
  | 'paused'
  | 'resumed'
  | 'retrying'
  | 'incident';

export interface BaseStep {
  type: StepType;
  step?: number;
  content?: string;
  timestamp: number;
  task_id?: string;
}

export interface StartStep extends BaseStep {
  type: 'start';
  user_message?: string;
  security_check?: {
    is_safe: boolean;
    risk?: string;
  };
  provider?: string;
  model?: string;
  display_name?: string;
}

export interface ThoughtStep extends BaseStep {
  type: 'thought';
  thought?: string;
  reasoning?: string;
  tool_name?: string;
  tool_params?: Record<string, any>;
}

export interface ActionToolStep extends BaseStep {
  type: 'action_tool';
  tool_name: string;
  tool_params?: Record<string, any>;
  execution_status?: 'success' | 'error';
  execution_result?: any;
  summary?: string;
  execution_time_ms?: number;
  action_retry_count?: number;
  error_message?: string;
}

// ... 其他步骤类型定义

// 类型守卫
export const isStartStep = (step: BaseStep): step is StartStep => step.type === 'start';
export const isThoughtStep = (step: BaseStep): step is ThoughtStep => step.type === 'thought';
export const isActionToolStep = (step: BaseStep): step is ActionToolStep => step.type === 'action_tool';
// ... 其他类型守卫
```

#### 3.3.2 创建样式hook
**实施步骤**:
1. 创建 `useStepStyles` hook
2. 缓存样式对象
3. 提供类型安全的样式访问

**代码示例**:
```typescript
// src/components/Chat/hooks/useStepStyles.ts
import { useMemo } from 'react';
import { 
  getStepStyle, 
  getStepTitleStyle, 
  getStepContentStyle,
  getStepLabelStyle,
  getStepBadgeStyle,
  getTimestampStyle,
  StepType 
} from '../../../utils/stepStyles';

export const useStepStyles = (stepType: StepType) => {
  const styles = useMemo(() => ({
    container: getStepStyle(stepType),
    title: getStepTitleStyle(stepType),
    content: getStepContentStyle(stepType, 'primary'),
    contentSecondary: getStepContentStyle(stepType, 'secondary'),
    label: getStepLabelStyle(stepType),
    badge: getStepBadgeStyle(stepType),
    timestamp: getTimestampStyle(stepType),
  }), [stepType]);

  return styles;
};

// 使用示例
const StepHeader: React.FC<StepHeaderProps> = ({ step }) => {
  const styles = useStepStyles(step.type as StepType);
  
  return (
    <div style={styles.container}>
      <span style={styles.badge}>步骤{step.step}</span>
      <span style={styles.label}>{STEP_ICON_MAP[step.type]} {STEP_LABEL_MAP[step.type]}</span>
      {step.timestamp && (
        <span style={styles.timestamp}>
          ⏰ {formatTimestamp(step.timestamp)}
        </span>
      )}
    </div>
  );
};
```

#### 3.3.3 添加错误边界
**实施步骤**:
1. 创建ErrorBoundary组件
2. 包装关键组件
3. 提供友好的错误回退UI

**代码示例**:
```typescript
// src/components/common/ErrorBoundary.tsx
import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      
      return (
        <div style={{
          padding: '20px',
          background: '#fff1f0',
          border: '1px solid #ffa39e',
          borderRadius: '8px',
          color: '#cf1322',
        }}>
          <h3>组件渲染出错</h3>
          <p>{this.state.error?.message}</p>
          <button 
            onClick={() => this.setState({ hasError: false })}
            style={{
              marginTop: '10px',
              padding: '5px 10px',
              background: '#1890ff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

// 使用示例
const StepRowWithErrorBoundary: React.FC<StepRowProps> = (props) => (
  <ErrorBoundary fallback={<div>步骤渲染出错，请稍后重试</div>}>
    <StepRow {...props} />
  </ErrorBoundary>
);
```

---

## 四、实施优先级和时间估算

### 4.1 优先级排序
1. **P0（立即实施）**: 阶段1的所有优化
   - 预计时间: 1-2天
   - 影响: 立即提升性能，无风险
   - 验收标准: 功能测试通过，性能测试提升

2. **P1（本周内）**: 阶段2的组件拆分
   - 预计时间: 3-5天
   - 影响: 提高可维护性，中等风险
   - 验收标准: 组件拆分完成，功能测试通过

3. **P2（下周）**: 阶段3的架构优化
   - 预计时间: 1-2周
   - 影响: 提升代码质量，高风险
   - 验收标准: 类型安全完善，错误边界添加，测试覆盖

### 4.2 风险控制
1. **阶段1**: 无风险，纯优化
2. **阶段2**: 中等风险，需要仔细测试组件拆分
3. **阶段3**: 高风险，需要充分测试类型安全和错误处理

### 4.3 测试策略
1. **单元测试**: 每个拆分后的组件
2. **集成测试**: 组件组合功能
3. **性能测试**: 渲染性能对比
4. **回归测试**: 确保现有功能不受影响

---

## 五、代码示例：完整实施

### 5.1 阶段1完整代码示例

**stepConstants.ts**:
```typescript
// src/components/Chat/constants/stepConstants.ts
export const STEP_LABEL_MAP: Record<string, string> = {
  start: "开始",
  thought: "思考",
  action_tool: "执行",
  observation: "观察",
  final: "完成",
  error: "错误",
  paused: "暂停",
  resumed: "恢复",
  interrupted: "中断",
  retrying: "重试",
  incident: "事件",
} as const;

export const STEP_ICON_MAP: Record<string, string> = {
  start: "🚀",
  thought: "💭",
  action_tool: "⚙️",
  observation: "📋",
  final: "✅",
  error: "❌",
  paused: "⏸️",
  resumed: "▶️",
  interrupted: "⚠️",
  retrying: "🔄",
  incident: "⚡",
} as const;

export const STEP_TYPES = Object.keys(STEP_LABEL_MAP) as Array<keyof typeof STEP_LABEL_MAP>;
```

**timeFormatters.ts**:
```typescript
// src/utils/timeFormatters.ts
export const formatRelativeTime = (date: Date | string | number): string => {
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    if (isNaN(dateObj.getTime())) return "刚刚";
    
    const now = new Date();
    const diff = now.getTime() - dateObj.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return "刚刚";
    if (minutes < 60) return `${minutes}分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}小时前`;
    return dateObj.toLocaleDateString("zh-CN");
  } catch (error) {
    return "刚刚";
  }
};

export const formatTime = (date: Date | string | number): string => {
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    if (isNaN(dateObj.getTime())) return "刚刚";
    
    return dateObj.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (error) {
    return "刚刚";
  }
};

export const formatTimestamp = (timestamp: number | string): string => {
  const date = new Date(timestamp);
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
};
```

### 5.2 修改后的StepRow组件（阶段1优化后）

```typescript
// MessageItem.tsx 中的StepRow组件（优化后）
import React, { useState, useMemo, useCallback } from "react";
import { STEP_LABEL_MAP, STEP_ICON_MAP } from "./constants/stepConstants";
import { formatRelativeTime, formatTime } from "../../utils/timeFormatters";

const StepRow: React.FC<StepRowProps> = ({ step, taskId: _taskId, stepIndex = 0, expandedSteps, toggleExpand }) => {
  const [_isLoadingMore, _setIsLoadingMore] = useState(false);
  const [_showAllData, setShowAllData] = useState(false);

  // 使用全局Map读取展开状态
  const isExpanded = expandedSteps.get(stepIndex) ?? true;
  
  // 使用常量，不再每次渲染创建
  const effectiveType = step.type === 'incident' ? (step as any).incident_value || 'incident' : step.type;
  const label = STEP_LABEL_MAP[effectiveType] || STEP_LABEL_MAP[step.type] || "步骤";
  const icon = STEP_ICON_MAP[effectiveType] || STEP_ICON_MAP[step.type] || "";

  const executionResult = step.execution_result;
  
  // 使用useMemo缓存样式
  const badgeStyle = useMemo(() => getStepBadgeStyle(effectiveType as StepType), [effectiveType]);
  const labelStyle = useMemo(() => getStepLabelStyle(effectiveType as StepType), [effectiveType]);
  const contentStyle = useMemo(() => getStepContentStyle(effectiveType as StepType, "primary"), [effectiveType]);
  
  // 使用useCallback包装事件处理
  const handleLoadMore = useCallback(() => {
    setShowAllData(true);
  }, []);

  const handleMouseEnter = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.background = "rgba(0,0,0,0.04)";
    e.currentTarget.style.boxShadow = "0 2px 8px rgba(0,0,0,0.08)";
  }, []);

  const handleMouseLeave = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.currentTarget.style.background = "rgba(0,0,0,0.02)";
    e.currentTarget.style.boxShadow = "none";
  }, []);

  // 使用useMemo缓存分页数据
  const { displayData, hasMore } = useMemo(() => {
    const rawData = executionResult as any;
    const allData = rawData?.matches || rawData?.entries || rawData?.results || [];
    const FRONTEND_PAGE_SIZE = 100;
    
    if (_showAllData) {
      return { displayData: allData, hasMore: false };
    }
    
    if (allData.length > FRONTEND_PAGE_SIZE) {
      return { displayData: allData.slice(0, FRONTEND_PAGE_SIZE), hasMore: true };
    }
    
    return { displayData: allData, hasMore: false };
  }, [executionResult, _showAllData]);

  // 使用useCallback包装工具信息渲染函数
  const renderToolInfo = useCallback((toolName: string | undefined, toolParams: Record<string, any> | undefined, options?: {
    prefix?: string;
    bgColor?: string;
  }) => {
    const prefix = options?.prefix || '';
    const bgColor = options?.bgColor || 'rgba(0,0,0,0.03)';
    
    if (!toolName && !toolParams) return null;
    
    return (
      <div style={{ 
        display: 'flex', 
        alignItems: 'center', 
        flexWrap: 'wrap', 
        gap: 10,
      }}>
        {toolName && (
          <span style={{ fontWeight: FontWeight.MEDIUM }}>
            {prefix}{toolName}
          </span>
        )}
        {toolParams && Object.keys(toolParams).length > 0 && (
          <span style={{ 
            color: '#595959',
            fontSize: 11,
            fontFamily: 'Consolas, Monaco, "Courier New", monospace',
            background: bgColor,
            padding: '2px 6px',
            borderRadius: 4,
            maxWidth: '60%',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'inline-block',
          }}>
            {JSON.stringify(toolParams)}
          </span>
        )}
      </div>
    );
  }, []);

  // ... 其余渲染逻辑保持不变，但使用优化后的变量和函数
};
```

---

## 六、验收检查清单

### 6.1 阶段1验收清单
- [ ] labelMap/iconMap提取为常量
- [ ] 所有内联样式函数使用useMemo缓存
- [ ] 所有事件处理函数使用useCallback包装
- [ ] 时间格式化函数提取到utils
- [ ] 功能测试通过
- [ ] 性能测试显示提升

### 6.2 阶段2验收清单
- [ ] StepRow组件拆分完成
- [ ] renderToolResult函数拆分完成
- [ ] NewChatContainer状态管理优化
- [ ] 所有拆分后的组件功能测试通过
- [ ] 集成测试通过
- [ ] 代码复杂度降低（通过代码分析工具验证）

### 6.3 阶段3验收清单
- [ ] 完整的类型定义文件
- [ ] 消除所有`as any`类型断言
- [ ] 添加类型守卫函数
- [ ] 创建样式hook
- [ ] 添加错误边界组件
- [ ] 单元测试覆盖率达到80%以上
- [ ] 性能测试显示进一步提升

---

## 七、性能监控指标

### 7.1 监控指标
1. **渲染次数**: 使用React DevTools监控组件重渲染次数
2. **渲染时间**: 使用Performance API测量关键路径渲染时间
3. **内存使用**: 监控组件内存占用
4. **包大小**: 监控构建后的包大小变化

### 7.2 基准测试
1. **优化前基准**: 记录当前性能数据
2. **阶段1后**: 对比性能提升
3. **阶段2后**: 对比性能提升
4. **阶段3后**: 最终性能数据

### 7.3 预期提升
1. **阶段1**: 预计减少30%不必要的重渲染
2. **阶段2**: 预计减少50%组件渲染时间
3. **阶段3**: 预计提升开发体验和代码质量

---

## 八、回滚计划

### 8.1 回滚条件
1. 功能测试失败
2. 性能不升反降
3. 出现严重bug
4. 用户反馈体验变差

### 8.2 回滚步骤
1. 立即停止部署
2. 回滚到上一个稳定版本
3. 分析问题原因
4. 修复问题后重新测试

### 8.3 应急联系人
- 前端负责人: XXX
- 测试负责人: XXX
- 产品负责人: XXX

---

## 九、总结

本方案提供了从简单到复杂、从快速优化到架构重构的完整实施路径。建议按照以下顺序实施：

1. **立即开始阶段1**：快速优化，无风险，立即见效
2. **本周内完成阶段2**：组件拆分，提高可维护性
3. **下周开始阶段3**：架构优化，提升代码质量

每个阶段都有明确的验收标准和回滚计划，确保实施过程可控、风险可管理。

**版本历史**
| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-04-20 21:30:00 | CodeArts代码智能体 | 初始版本，详细实施方案 |

**更新时间**: 2026-04-20 21:30:00
**编写人**: CodeArts代码智能体