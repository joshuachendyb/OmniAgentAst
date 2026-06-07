# OmniAgentAs-desk 运行时测试 - 发现问题清单
> 测试时间: 2026-05-21 | 测试类型: 真实ReAct Loop全工具运行时测试

## 严重问题 (Critical)

### BUG-1: LLM API 429限流后无重试机制，直接返回错误给用户
- **现象**: 当LLM API返回429 (FreeUsageLimitError)时，系统直接将错误信息返回给用户：`"[错误] ⚠️ API请求过于频繁 (errorcode=429)，请稍后再试或更换模型"`
- **影响**: 用户收到的是原始错误信息而非正常响应，体验极差
- **日志证据**: `llm_core.py - [chat_stream] HTTP 429 error response: {"type":"error","error":{"type":"FreeUsageLimitError"...}}`
- **发生频率**: 测试期间623次429错误，**100%的请求都受影响**
- **根因**: `llm_core.py` 的 `chat_stream` 方法遇到429直接抛异常，没有指数退避重试

### BUG-2: 429导致能力探测失败 → 所有LLM策略降级为text模式
- **现象**: CapabilityDetector在探测LLM能力(tools/response_format)时遇到429，判定为"不支持"，所有策略降级为text
- **影响**: 
  - 工具调用不走function calling，而是靠LLM自由文本输出+解析器提取
  - 效率大幅下降(text模式需要注入完整工具Schema到Prompt，token消耗大)
  - 准确率下降(自由文本解析比结构化API调用更容易出错)
- **日志证据**: `[CapabilityDetector] _probe_tools: HTTP 429 → ❌ 不支持 → 最终策略: text (降级为text模式)`
- **发生频率**: 46次全部降级为text，**0次使用tools/response_format策略**

### BUG-3: SSE事件缺少工具执行中间步骤(thought/action_tool/observation)
- **现象**: SSE流只发送2个事件: `start` → `final`，中间的`thought`、`action_tool`、`observation`事件全部缺失
- **影响**: 前端无法展示Agent的思考过程和工具调用过程，用户体验差
- **根因**: 429导致LLM直接返回错误消息，ReAct循环第一轮就触发`answer/implicit`退出，没有进入工具调用阶段
- **注意**: 这是一个**级联问题**，根因是BUG-1和BUG-2

## 高优先级问题 (High)

### BUG-4: tool/execute端点参数字段名不一致
- **现象**: 端点期望`params`字段，但常见习惯使用`parameters`
- **实际接口**: `{"tool_name": "xxx", "params": {...}}`
- **常见误用**: `{"tool_name": "xxx", "parameters": {...}}` → 静默失败(参数为空dict)
- **修复建议**: 同时支持`params`和`parameters`字段，或改用更明确的`parameters`并更新文档

### BUG-5: tool/execute端点参数名与Pydantic Schema不一致
- **现象**: Pydantic InputSchema定义的参数名(如`path`, `action`)与实际工具函数签名的参数名(如`file_paths`, `dir_path`)不一致
- **影响**: 即使字段名正确，参数映射也可能失败
- **示例**: 
  - `read_file`: Schema用`path`，函数签名用`file_paths`
  - `list_directory`: Schema用`path`，函数签名用`dir_path`
  - `search_files`: Schema用`path`+`pattern`，函数签名用`search_dir`+`pattern`
  - `network_diagnose`: Schema用`target`+`action`，函数签名用`host`+`action`
- **当前通过的工具**: `get_time`, `list_windows`, `screen_capture`, `query_calendar` (参数名恰好一致)

### BUG-6: message_saver持续报404错误
- **现象**: 91次`[Save] 保存失败: 404: 会话不存在: xxx`
- **影响**: 聊天消息无法持久化保存，刷新后对话丢失
- **根因**: 测试时未通过sessions API预先创建会话，导致session_id在DB中不存在
- **涉及**: 44个不存在的会话ID

### BUG-7: security/check端点与SSE start事件返回格式不一致
- **security/check端点**: `{"success": true, "data": {"score": 3, "message": "操作安全"}}`
- **SSE start事件**: `{"security_check": {"is_safe": true, "risk_level": "safe", "blocked": false}}`
- **影响**: 前端需要两套不同的逻辑来处理安全检查结果，增加维护成本
- **修复建议**: 统一为`is_safe`/`risk_level`/`blocked`格式

## 中优先级问题 (Medium)

### BUG-8: security/check的score阈值语义不清晰
- **现象**: `echo hello` 返回score=5, message="操作存在风险，请注意"，但实际是安全的
- **问题**: score=3是"安全"，score=5是"有风险"，score=10是"危险"，但`echo hello`不应被标记为有风险
- **根因**: 操作类型权重中EXEC(执行)权重5-10，`echo`被归类为执行操作

### BUG-9: operations API缺少必填参数的清晰错误提示
- **现象**: GET `/api/v1/operations` 返回422，但错误信息`"Field required"`对前端不够友好
- **影响**: 前端开发需要猜参数名
- **修复建议**: 在OpenAPI文档中标记为必填，或提供默认值

### BUG-10: tool/list返回缺少inputSchema
- **现象**: tool/list只返回`required_params`和`optional_params`(字段名列表)，不返回完整的Pydantic inputSchema
- **影响**: 前端无法构建动态表单、无法做参数校验、无法知道参数类型
- **修复建议**: 添加`inputSchema`字段，包含完整的JSON Schema

## 低优先级问题 (Low)

### BUG-11: CRSS意图检测中desktop意图包含ToolCategory枚举值
- **现象**: 意图分布中有`desktop(ToolCategory.DESKTOP)`这样的格式，应该是纯粹的字符串`desktop`
- **日志**: `[RouteFallback] CRSS阶段1 → intent=desktop(ToolCategory.DESKTOP)`
- **影响**: 可能导致意图匹配失败

### BUG-12: Adapter跳过null/invalid消息但没有日志级别区分
- **现象**: `Null message at index 1, skipping` / `Invalid message object at index 1`
- **影响**: 如果是正常的空消息(如前端初始化)，不应WARNING；如果是异常数据，应该ERROR
- **修复建议**: 区分"前端传空消息"(INFO)和"数据损坏"(ERROR)

## 设计问题 (Design)

### DESIGN-1: 429限流处理策略缺失
- **现状**: 无重试、无退避、无降级到其他provider、无排队机制
- **建议**: 
  1. 添加指数退避重试(3次, 间隔1s/2s/4s)
  2. 支持自动切换到备用provider
  3. 请求排队/限流器(避免同时发送过多请求)

### DESIGN-2: 能力探测应在服务启动时缓存
- **现状**: 每个Agent初始化时都做能力探测，429时探测失败
- **建议**: 服务启动时探测一次并缓存结果，429时使用缓存的能力信息

### DESIGN-3: ReAct循环中429应有专门处理
- **现状**: 429错误和普通错误一样处理，导致循环立即退出
- **建议**: 429应触发等待+重试继续循环，而非直接终止

## 测试方法论问题

### TEST-1: 之前的测试报告"119/119通过"掩盖了真实问题
- **原因**: 测试断言过于宽松——只要SSE返回了事件就算"通过"
- **实际情况**: 大部分测试的SSE只有start+final两个事件，final内容是429错误消息
- **改进**: 应验证final内容不含错误信息、验证工具步骤存在、验证SSE事件数>2

### TEST-2: 未验证ReAct循环是否真正执行了工具
- **现状**: `steps=0, tools=[]` 在所有测试中都出现，但没有被标记为问题
- **改进**: 应断言`steps_count > 0`和`len(tools_invoked) > 0`

## 统计摘要

| 级别 | 数量 | 编号 |
|------|------|------|
| Critical | 3 | BUG-1, BUG-2, BUG-3 |
| High | 4 | BUG-4, BUG-5, BUG-6, BUG-7 |
| Medium | 3 | BUG-8, BUG-9, BUG-10 |
| Low | 2 | BUG-11, BUG-12 |
| Design | 3 | DESIGN-1, DESIGN-2, DESIGN-3 |
| Test方法 | 2 | TEST-1, TEST-2 |
| **总计** | **17** | |
