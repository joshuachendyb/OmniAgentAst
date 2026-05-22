# Agent 2.0 最佳融合设计方案

**创建时间**: 2026-05-22 09:45:40  
**版本**: v1.0  
**作者**: 小沈  
**设计依据**: doc-agent2.0/ 下 10 份设计文档，取各方案最优设计融合

---

## 一、设计核心理念

### 1.1 三层范式选择（引1份方案6）

| 范式 | 路线 | 推荐度 |
|------|------|--------|
| **A - 意图路由** | CRSS/LLM分类 → 选定1个Agent | ❌ 淘汰 |
| **B - 全量工具** | 1个Agent + 全部工具 | ⚠️ 备选（小型项目） |
| **C - 语义发现** | 语义路由推荐类别 → Agent加载对应工具 | ✅ **推荐** |

**选择C的理由**（引5份方案8）：
- 工具隔离性好（无关工具不加载 → 降低误用风险）
- 扩展灵活（新增工具类别无需改路由逻辑）
- 性能优（每次只加载2-4个类别，LLM上下文小）
- 安全好（风险跟工具走，不跟意图走）

### 1.2 安全架构四层体系（引3份方案4、方案5、方案7）

```
用户输入
   │
   ▼
┌────────────────────────────┐
│ Layer 1: 语义路由过滤       │ ← 推荐类别，排除高风险类别
├────────────────────────────┤
│ Layer 2: 工具安全级别       │ ← ToolSafetyLevel 四级
├────────────────────────────┤
│ Layer 3: HITL 人工确认     │ ← 高耗时/破坏性操作暂停确认
├────────────────────────────┤
│ Layer 4: ToolObserver      │ ← 异常检测 + 审计日志
└────────────────────────────┘
```

### 1.3 总体架构图

```
用户输入
    │
    ▼
┌─────────────────────────────────┐
│        Semantic Router          │  ← 用 Function Calling 替代 CRSS
│  (推荐2-4个工具类别 + intent)     │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│     AgentRegistry.lookup()      │  ← 匹配 AgentProfile
│     → UnifiedReactAgent         │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   Tool Safety Layer 参数检查     │  ← 检查参数合法性
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   UnifiedReactAgent.execute()   │  ← ReAct 循环
│   ┌─────────────────────────┐   │
│   │  MessageBuilder (复用)   │   │  ← 现有代码保留
│   │  StepFactory (复用)      │   │
│   │  trim_history (复用)     │   │
│   └─────────────────────────┘   │
└────────────┬────────────────────┘
             │ (high_risk / destructive)
             ▼
┌─────────────────────────────────┐
│   HITL: SSE暂停 → 用户确认      │  ← 暂停流，发授权事件
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   ToolObserver 记录+异常检测     │  ← 全量审计
└─────────────────────────────────┘
```

---

## 二、语义路由（Semantic Router）

### 2.1 路由方式（引方案6、方案8）

**采用 Function Calling 方式替代 CRSS 正则匹配**：

```
输入: 用户消息 + 对话历史
输出: tool_calls 格式 → {categories: [...], intent: "..."}
```

**为什么弃用 CRSS**（引方案6）：
- CRSS 正则规则难维护，易遗漏
- CRSS 无法处理模糊意图
- Function Calling 自然语言理解更强

**返回格式**：
```json
{
  "categories": ["file", "document", "network"],
  "intent": "edit_file",
  "confidence": 0.92,
  "reasoning": "用户要求修改文件内容"
}
```

### 2.2 Candidates 机制（引方案9）

**预加载优化**：
- 根据信心度（confidence）决定预加载深度
- confidence > 0.9：只加载推荐的类别
- confidence 0.6-0.9：加载推荐 + 2 个最接近的备选
- confidence < 0.6：提示用户澄清

**Chat 意图回退**（引方案9）：
- 当没有匹配任何意图时，回退到 chat 意图
- 走纯对话流程，不加载任何工具
- 替代现有"网络查询失败后报错"的行为

### 2.3 意图注册表（引方案9）

**IntentRegistry** 作为单一真相源：

```python
class IntentDefinition(BaseModel):
    name: str                       # 意图名
    description: str                # 意图描述
    required_categories: list[str]  # 需要的工具类别
    is_deprecated: bool = False     # 是否废弃
    priority: int = 0               # 路由优先级

class IntentRegistry:
    _intents: dict[str, IntentDefinition]
    
    @classmethod
    def register(cls, intent: IntentDefinition): ...
    @classmethod
    def get_active(cls) -> list[IntentDefinition]: ...
    @classmethod
    def resolve(cls, semantic_result: dict) -> IntentDefinition: ...
```

**意图定义**（7 活跃 + 4 废弃，引方案9）：

| 活跃意图 | 描述 | 工具类别 |
|---------|------|---------|
| edit | 文件编辑 | file |
| query | 信息查询 | file, network |
| code_analysis | 代码分析 | file, shell |
| data_process | 数据处理 | file, shell |
| system_manage | 系统管理 | system, shell |
| chat | 纯对话 | (无工具) |
| task | 多步任务 | 所有推荐类别 |

---

## 三、Agent 架构

### 3.1 AgentProfile（引方案8、方案9）

```python
class AgentProfile(BaseModel):
    name: str
    model_config: dict
    max_steps: int = 30
    allowed_categories: list[str]  # 允许的工具类别
    prompt_template: str           # 系统提示模板
    safety_level: str = "normal"   # normal | strict | relaxed
```

### 3.2 AgentRegistry（引方案9）

```python
class AgentRegistry:
    _profiles: dict[str, AgentProfile]
    
    @classmethod
    def register(cls, profile: AgentProfile): ...
    @classmethod
    def lookup(cls, categories: list[str]) -> AgentProfile: ...
```

**匹配逻辑**：
- categories 匹配度最高的 profile
- categories → intent → profile 三级匹配
- 无匹配时回退到默认 profile（chat 意图）

### 3.3 UnifiedReactAgent（引方案6、方案8）

整合现有 `BaseAgent` + `ReactAgentMixin` 为单一类：

```python
class UnifiedReactAgent(BaseAgent):
    profile: AgentProfile
    
    async def run(self, task: str) -> GenerationResult:
        # 1. 加载工具（按 categories）
        # 2. MessageBuilder 初始化
        # 3. ReAct 循环
        # 4. 返回结果
```

**核心简化**（引方案6）：
- 删工具复杂度：6 个 Agent 子类 → 1 个 UnifiedReactAgent
- 删预处理管线：PreprocessingPipeline、CRSS、command_security.py
- 删 parsers/：全部用 react_output_parser.py

### 3.4 工具加载机制（引方案8）

```python
async def load_tools(self, categories: list[str]):
    """按语义路由推荐类别加载工具"""
    for cat in categories:
        registry = ToolRegistry.get_category(cat)
        for tool in registry:
            self._available_tools[tool.name] = tool
```

---

## 四、工具安全体系

### 4.1 工具安全级别（引方案7、方案8）

```python
class ToolSafetyLevel(Enum):
    READ_ONLY    = 0   # 只读，无风险
    SAFE         = 1   # 安全写操作
    DESTRUCTIVE  = 2   # 破坏性操作（需二次确认）
    DANGEROUS    = 3   # 危险操作（需 HITL）
```

**标注规则**：每个工具在注册时声明 safety_level，风险跟工具走不跟意图。

### 4.2 参数检查层（引方案8）

```python
def check_tool_call(tool_name: str, params: dict) -> SafetyResult:
    """参数级别的安全检查"""
    # 1. 参数边界检查
    # 2. 路径注入检查
    # 3. 命令注入检查
    # 4. 资源限制检查
```

### 4.3 HITL 人工确认（引方案6、方案8）

**触发条件**：
- DANGEROUS 级别工具调用
- 高耗时操作（> 30 秒）
- 系统级修改

**交互流程**（SSE 暂停/恢复）：
```
┌──────────┐        ┌──────────┐        ┌──────────┐
│  Agent   │        │  Backend │        │  Frontend │
│          │        │          │        │          │
│ 需要确认  │ ──→   │  SS暂停  │ ──→   │ 弹确认框  │
│          │        │          │        │          │
│          │        │          │ ←──   │ 用户确认  │
│          │ ←──   │  SS恢复  │        │          │
└──────────┘        └──────────┘        └──────────┘
```

### 4.4 信任机制优化 HITL 频率（引方案6、方案8）

```python
class SessionTrustManager:
    """根据历史行为降低确认频率"""
    
    def get_trust_level(self, session_id: str) -> float:
        # 安全操作累计加分
        # 危险操作重置扣分
        pass
    
    def should_skip_hitl(self, tool: str, params: dict) -> bool:
        # trust > 0.8 且同工具连续安全使用5次 → 跳过HITL
        pass
```

### 4.5 ToolObserver（引方案5、方案8）

```python
class ToolObserver:
    """全量工具调用审计"""
    
    async def record(self, session_id: str, tool_name: str, 
                     params: dict, result: dict, duration: float):
        # 记录到审计日志
        # 异常检测（重复失败、异常参数模式）
        # 触发告警
        pass
```

---

## 五、预处理管线重构

### 5.1 PipelineContext（引方案3）

```python
@dataclass
class PipelineContext:
    raw_text: str
    corrected_text: str | None = None
    intent: str | None = None
    categories: list[str] | None = None
    safety_result: SafetyResult | None = None
    metadata: dict = field(default_factory=dict)
```

### 5.2 TextCorrectorV2（引方案3）

**规则级文本矫正**，不依赖 LLM：
- 安全关键词优先级标记（`keyword:action` → action 作为 intent）
- 拼写修正
- 中英文混合优化

### 5.3 意图检测简化（引方案3）

聊天启发式（快速判断 chat 意图）：
```
长度 < 5 且无动词 → chat
含"你好/谢谢/再见" → chat
其他 → 走语义路由
```

---

## 六、重复执行消除（引方案10）

### 6.1 失败计数器 + 增强失败观测

```python
class FailureTracker:
    """追踪工具调用失败次数"""
    
    max_retries: int = 2  # 同工具同参数最大重试
    
    def should_retry(self, tool: str, params: dict) -> bool:
        pass
    
    def get_failure_observation(self, tool: str, params: dict) -> str:
        """返回增强的失败信息，含失败原因和建议"""
        pass
```

### 6.2 成功结果缓存 + 去重执行

```python
class ResultCache:
    """同参数同工具的结果缓存"""
    
    def get(self, tool: str, params: dict) -> Any | None:
        pass
    
    def set(self, tool: str, params: dict, result: Any):
        pass
```

### 6.3 工具 summary 去重（引方案10）

从 53KB → 2KB：
```python
def dedup_summary(steps: list[Step]) -> str:
    """只保留每个工具最近一次调用的结果摘要"""
    seen = {}
    for step in steps:
        if step.type == "observation":
            seen[step.tool_name] = step.summary
    return "\n".join(f"[{k}] {v}" for k, v in seen.items())
```

### 6.4 trim_history 优化（引方案10）

```
阈值: 15 → 30（保留更多上下文）
移除策略: 保留 system + 最近 N 轮 user/assistant，只删 observation
```

---

## 七、清理计划（引方案9）

### 7.1 可删除的代码

| 模块 | 文件 | 原因 |
|------|------|------|
| PreprocessingPipeline | `services/preprocessing/` | 语义路由替代 |
| CRSS 分类器 | `services/intents/` | Function Calling 替代 |
| command_security.py | `services/safety/` | 工具安全级别替代 |
| parsers/ | `agent/parsers/` | 已废弃，用 react_output_parser.py |
| 旧的 Agent 子类 | `agent/*_agent.py` | UnifiedReactAgent 替代 |
| 旧的意图定义 | `services/intents/` | IntentRegistry 替代 |

### 7.2 保留的代码

| 模块 | 文件 | 原因 |
|------|------|------|
| MessageBuilder | `agent/message_builder.py` | 核心逻辑，无需改 |
| StepFactory | `agent/step_factory.py` | 步骤工厂，复用 |
| ToolRegistry | `tools/registry.py` | 工具注册表，复用 |
| react_output_parser.py | `agent/` | LLM 输出解析，复用 |
| _response.py | `tools/_response.py` | 工具返回格式，复用 |

---

## 八、实施路线图（引方案5、方案8）

### Phase 0：准备（Days 1-3）
- [ ] 创建 AgentProfile / AgentRegistry / IntentRegistry 数据结构
- [ ] 创建 UnifiedReactAgent 框架（先作为新类，不删旧代码）
- [ ] 创建 ToolSafetyLayer / ToolObserver 框架
- [ ] 写单元测试覆盖新类

### Phase 1：语义路由替换 CRSS（Days 4-7）
- [ ] 实现 Function Calling 语义路由
- [ ] 保留 CRSS 作为 fallback（灰度切换）
- [ ] 实现 Candidates 预加载
- [ ] 测试语义路由准确率

### Phase 2：工具安全体系（Days 8-12）
- [ ] 给每个工具标注 ToolSafetyLevel
- [ ] 实现 ToolSafetyLayer 参数检查
- [ ] 实现 HITL SSE 暂停/恢复流程
- [ ] 实现 SessionTrustManager
- [ ] 实现 ToolObserver 审计

### Phase 3：Agent 统一化（Days 13-18）
- [ ] 实现 UnifiedReactAgent 完整逻辑
- [ ] 逐个迁移旧 Agent 子类
- [ ] 删除 PreprocessingPipeline / CRSS / command_security.py
- [ ] 删除 parsers/ / 旧 Agent 子类 / 旧意图定义
- [ ] 全量集成测试

### Phase 4：优化（Days 19-21）
- [ ] 实施重复执行消除方案
- [ ] 实现 ResultCache
- [ ] 实现 dedup_summary
- [ ] 优化 trim_history 阈值
- [ ] 性能测试

### Phase 5：收尾（Days 22-25）
- [ ] 全量测试回归
- [ ] 死代码清理验收
- [ ] 设计文档归档
- [ ] 文档更新

---

## 九、设计决策汇总

| 决策点 | 选项 | 选择 | 来源 |
|--------|------|------|------|
| 路由方式 | CRSS / Function Calling | **Function Calling** | 方案6 |
| 工具策略 | 意图路由 / 全量工具 / 语义发现 | **语义发现(方案C)** | 方案6、方案7、方案8 |
| 安全层数 | 2层 / 3层 / 4层 | **4层** | 方案4、方案5、方案7 |
| 安全判定 | 自动化 / HITL | **HITL（含信任优化）** | 方案6、方案8 |
| 预处理管线 | 保留 / 废弃 | **废弃** | 方案6 |
| 黑名单 | 保留 / 废弃 | **废弃** | 方案6 |
| Agent 子类 | 保留6个 / 统一1个 | **统一1个** | 方案6、方案8 |
| 类型文件 | 保留 / 废弃 | **废弃** | 方案6 |
| 意图注册 | 分散 / IntentRegistry | **IntentRegistry** | 方案9 |
| 重复执行 | 不处理 / 8方案 | **8方案综合** | 方案10 |
| trim_history | 15→30 + observation-only | **30阈值 + 去重** | 方案10 |
| Session Trust | 不实现 / 实现 | **实现降HITL频率** | 方案6、方案8 |

---

## 十、预期效果

| 指标 | 当前（v0.13.x） | 重构后 | 来源 |
|------|----------------|--------|------|
| Agent 子类数 | 6 | **1**（UnifiedReactAgent） | 方案6 |
| 安全层数 | 1层（黑名单） | **4层** | 方案4 |
| 代码行数 | ~3000行（管线+Agent） | **~1500行**（-50%） | 方案7 |
| 路由方式 | CRSS 正则 | **Function Calling** | 方案6 |
| 重复执行 | 有 | **消除** | 方案10 |
| 上下文大小 | ~53KB | **~2KB**（summary去重） | 方案10 |
| HITL 频率 | 无HITL | **高频自动跳过**（信任机制） | 方案6 |
| 工具类别隔离 | 无 | **语义隔离** | 方案8 |

---

## 版本历史

| 版本 | 时间 | 作者 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-05-22 09:45:40 | 小沈 | 初始版本，综合10份方案最优设计 |

---

**设计依据文件列表**：
1. `全Agent自包含激进方案-小沈-2026-05-20.md` — 极简理念
2. `三大核心管线完美重构方案-小沈-2026-05-20.md` — PipelineContext、双层安全
3. `两个方案对比分析与融合建议-小沈-2026-05-20.md` — 4层安全、信任机制
4. `三合一方案对齐分析-小沈-2026-05-20.md` — 三维度正交、Phase路线图
5. `预处理管线重构方案-小沈-2026-05-20.md` — TextCorrectorV2
6. `Agent高级调度与安全防护架构重构方案-小沈-2026-05-20.md` — Function Calling路由、HITL
7. `Agent架构根本性重构方案-小沈-2026-05-20.md` — 三种范式分析、53%代码缩减
8. `Agent融合架构重构方案-方案C-小沈-2026-05-20.md` — ToolSafetyLevel、Observer、14天计划
9. `Agent与意图分类架构重构方案-小沈-2026-05-20.md` — IntentRegistry、Candidates
10. `Agent重复执行深度分析-2026-05-14.md` — 重复执行消除8方案
