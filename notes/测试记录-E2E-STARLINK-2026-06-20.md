# 测试记录-E2E-STARLINK-2026-06-20

**创建时间**: 2026-06-20 09:52:19
**测试编号**: E2E-STARLINK
**测试结果**: FAILED

---

## 1 测试基本信息

| 项目 | 内容 |
|------|------|
| 测试编号 | E2E-STARLINK |
| 任务描述 | 低空星链通信行业分析报告生成 |
| 用户命令 | `分析今年的低空星链通信行业的发展和各个国家和领域的厂商情况 汇总信息分布生成 行业报告的doc文件和行业厂商对比分析的研究对比的excel文件 存入 reports目录` |
| 执行时间 | 2026-06-20 09:52:19 |
| 执行耗时 | 374.6秒 |
| SSE总事件数 | 177 |
| LLM调用次数 | 9 |
| 逻辑步数 | 27 |
| 不重复步骤号数 | 9 |
| 测试结果 | **FAILED** |

## 2 LLM回复内容

```
LLM流式错误: API请求参数错误 (errorcode=400),请检查输入内容
```

## 3 工具调用链

list_directory -> tool_search -> search_web -> fetch_webpage -> search_web -> fetch_webpage -> fetch_webpage -> write_docx

| 序号 | 工具名 | 参数 |
|------|--------|------|
| 1 | list_directory | `{"dir_path": "G:\\OmniAgentAs-desk\\backend"}` |
| 2 | tool_search | `{"query": "文档 读写 Word Excel"}` |
| 3 | search_web | `{"query": "2026年低空星链通信行业发展现状"}` |
| 4 | fetch_webpage | `{"prompt": "提取2026年卫星通信行业发展现状、市场规模、主要厂商、竞争格局、技术趋势的关键信息", "url": "https://www.huaon.com/channel/trend/1160522.html"}` |
| 5 | search_web | `{"query": "2026低空经济卫星通信厂商 Starlink OneWeb 中国 企业对比"}` |
| 6 | fetch_webpage | `{"prompt": "提取2026年Starlink、OneWeb、千帆星座、中国星网的技术参数、卫星数量、市场规模、竞争优劣势对比", "url": "http://www.peksun.com/article/55d67712ac7dce4f22f67f076892f41b.html"}` |
| 7 | fetch_webpage | `{"prompt": "提取2026年低空经济与卫星互联网融合发展的关键信息、主要应用领域、典型企业和典型案例", "url": "https://www.163.com/dy/article/J8HE3KP90511CSHM.html"}` |
| 8 | write_docx | `{}` |

## 4 SSE事件详情

- start 步骤=1
- thought 步骤=1 工具=list_directory
- action_tool 步骤=1 工具=list_directory
- observation 步骤=1
- thought 步骤=2 工具=tool_search
- action_tool 步骤=2 工具=tool_search
- observation 步骤=2
- thought 步骤=3 工具=search_web
- action_tool 步骤=3 工具=search_web
- observation 步骤=3
- thought 步骤=4 工具=fetch_webpage
- action_tool 步骤=4 工具=fetch_webpage
- observation 步骤=4
- thought 步骤=5 工具=search_web
- action_tool 步骤=5 工具=search_web
- observation 步骤=5
- thought 步骤=6 工具=fetch_webpage
- action_tool 步骤=6 工具=fetch_webpage
- observation 步骤=6
- thought 步骤=7 工具=fetch_webpage
- action_tool 步骤=7 工具=fetch_webpage
- observation 步骤=7
- thought 步骤=8 工具=write_docx
- action_tool 步骤=8 工具=write_docx
- observation 步骤=8
- thought 步骤=9
- final 步骤=9
  ... (chunk x150)

## 5 数据库验证详情

| 检查项 | 结果 |
|--------|------|
| 会话是否存在 | True |
| 是否有效 | True |
| 创建时间 | None |
| 更新时间 | None |
| 消息顺序正确 | True |
| 消息数量 | 2 |
| 执行步骤数 | 177 |
| 步骤字段问题数 | 1 |

### 5.2 执行步骤（前15条）

| 序号 | 步骤号 | 类型 | 工具 | 状态 |
|------|--------|------|------|--------|
| 1 | 1 | start |  |  |
| 2 | 1 | chunk |  |  |
| 3 | 1 | chunk |  |  |
| 4 | 1 | chunk |  |  |
| 5 | 1 | chunk |  |  |
| 6 | 1 | chunk |  |  |
| 7 | 1 | chunk |  |  |
| 8 | 1 | chunk |  |  |
| 9 | 1 | chunk |  |  |
| 10 | 1 | chunk |  |  |
| 11 | 1 | chunk |  |  |
| 12 | 1 | chunk |  |  |
| 13 | 1 | chunk |  |  |
| 14 | 1 | chunk |  |  |
| 15 | 1 | chunk |  |  |
| ... | (剩余162条) | | | |

### 5.3 步骤数据内容(action_tool)

**步骤1: list_directory**
- 参数: `{"dir_path": "G:\\OmniAgentAs-desk\\backend"}`
- 观察结果: `Tool execution succeeded`

**步骤2: tool_search**
- 参数: `{"query": "文档 读写 Word Excel"}`
- 观察结果: `Tool execution succeeded`

**步骤3: search_web**
- 参数: `{"query": "2026年低空星链通信行业发展现状"}`
- 观察结果: `Tool execution succeeded`

**步骤4: fetch_webpage**
- 参数: `{"prompt": "提取2026年卫星通信行业发展现状、市场规模、主要厂商、竞争格局、技术趋势的关键信息", "url": "https://www.huaon.com/channel/trend/1160522.html"}`
- 观察结果: `Tool execution succeeded`

**步骤5: search_web**
- 参数: `{"query": "2026低空经济卫星通信厂商 Starlink OneWeb 中国 企业对比"}`
- 观察结果: `Tool execution succeeded`

**步骤6: fetch_webpage**
- 参数: `{"prompt": "提取2026年Starlink、OneWeb、千帆星座、中国星网的技术参数、卫星数量、市场规模、竞争优劣势对比", "url": "http://www.peksun.com/article/55d67712ac7dce4f22f67f076892f41b.html"}`
- 观察结果: `Tool execution succeeded`

**步骤7: fetch_webpage**
- 参数: `{"prompt": "提取2026年低空经济与卫星互联网融合发展的关键信息、主要应用领域、典型企业和典型案例", "url": "https://www.163.com/dy/article/J8HE3KP90511CSHM.html"}`
- 观察结果: `Tool execution succeeded`

**步骤8: write_docx**
- 参数: `{}`
- 观察结果: `缺少必需参数: write_docx, 缺失: ['file_name']`

## 6 验证结果

| 验证项 | 结果 | 说明 |
|--------|------|------|
| 流结束 | final | - |
| 是否有error事件 | PASS | - |
| 回复内容 | PASS | 42字 |
| 数据库验证 | PASS | - |
| SSE-DB一致性 | PASS | 0个问题 |
| DB-Prompt日志一致性 | PASS | PASS |
| 步骤字段完整性 | FAIL | 1个问题 |
| 步骤合理性 | PASS | 0个问题 |
| 日志中ERROR | PASS | 0条 |
| 日志中异常堆栈 | PASS | 0条 |

## 失败详情

**异常信息**:

```
AssertionError: 必须生成doc行业报告文件(MUST), 目录: G:\OmniAgentAs-desk\backend\reports
assert 0 > 0
 +  where 0 = len([])
Traceback (most recent call last):
  File "G:\OmniAgentAs-desk\backend\tests\test_e2e_starlink_industry_analysis.py", line 104, in test_e2e_starlink_industry_analysis
    assert len(doc_files) > 0, f"必须生成doc行业报告文件(MUST), 目录: {reports_dir}"
AssertionError: 必须生成doc行业报告文件(MUST), 目录: G:\OmniAgentAs-desk\backend\reports
assert 0 > 0
 +  where 0 = len([])

```

## 7 三方一致性（DB/应用日志/Prompt日志）

| 对比项 | DB | SSE | 日志 | 是否匹配 |
|--------|-----|-----|------|----------|
| 工具数量 | 8 | 8 | 1次LLM调用 | PASS |
| 工具名称 | ['list_directory', 'tool_search', 'search_web', 'fetch_webpage', 'search_web'] | ['list_directory', 'tool_search', 'search_web', 'fetch_webpage', 'search_web'] | - | PASS |
| 观察结果数 | 8 | 8 | - | PASS |
| Prompt日志文件 | - | - | ['prompt_656+20260620_094605.json'] | PASS |

---
**更新时间**: 2026-06-20 09:52:19
