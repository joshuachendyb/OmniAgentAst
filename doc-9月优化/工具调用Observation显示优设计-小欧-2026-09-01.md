# 工具调用 Observation 显示优设计 - 小欧 - 2026-09-01

创建时间：2026-09-01 03:06:47
编写人：小欧
状态：**北京老陈 2026-09-01 已定案（统一结构，第一行工具后接集合名），待实施**

## 版本历史

| 版本 | 时间 | 编写人 | 简介 |
|------|------|--------|------|
| v1.0 | 2026-09-01 03:06:47 | 小欧 | 初稿：问题根因 + 单/并行工具 Observation 优雅显示设计定案，待审查 |
| v1.1 | 2026-09-01 03:12:16 | 小欧 | 北京老陈定案：单/多工具统一同一结构，第一行"工具"后接集合名（并行 N 个 / 调用 1 个）；更新第三节设计定案与第六节确认 |
| v1.2 | 2026-09-01 03:13:16 | 小欧 | 北京老陈补充定案：第一行集合名后**同行**跟工具名称列表（如「并行 2 个工具 [fetchpage, fetchpage]」）；更新 3.2 UI 示意 |
| v1.3 | 2026-09-01 03:17:20 | 小欧 | 新增第七章：按定案给出的 ToolCallLine.tsx 代码 diff（设计稿，待三堂会审后实施） |
| v1.4 | 2026-09-01 03:21:01 | 小欧 | 依北京老陈要求"observation 间距风格保持之前设计好的"修正 7.2 dff：新增子行改规范字号 FontSize.SECONDARY、行高=字号+Spacing.XS、段内折不折用 XS-2 派生不写死；7.3 展开区沿用原展开样式；补 FontSize import、7.4 间距说明 |
| v1.5 | 2026-09-01 03:22:28 | 小欧 | 全文熟读一致性 + dff 三轮严格三堂会审，发现的问题**就地修正进第七节 dff**（不新增章节）：①补文件头编辑历史；②配对根基已核实(execute_tools/build_observation 均 zip 顺序)；③状态缺失中性色不显图标防误报；④getResultSummary 保留摘要兜底防退化；⑤新增子行字号统一 13 与展开区一致；⑥行号 L44→L43 |
| v1.6 | 2026-09-01 03:27:11 | 小欧 | 应北京老陈质询"实时/历史回放是否都支持"：核实右侧唯一渲染入口 RightViewer→PipelineRenderer 共用 + 落库完整 step_json 原样读出 → dff 所依赖字段实时/历史逐字段一致，天然双模式支持；7.4 就地增补"实时/历史双模式支持"说明 |
| v1.7 | 2026-09-01 03:29:38 | 小欧 | 应北京老陈要求把新 observation 渲染 UI 效果详细展示补充到文档末尾（7.5 节）：单成功/单失败/并行一败一成/三混合/折叠态/展开态 共 6 个真实场景示意 + 渲染要点 6 项 |

---

## 一、问题背景与用户反馈

### 1.1 用户反馈（北京老陈 2026-09-01）
> 工具调用 observation 显示太差劲：①`fetchpage, fetchpage 参数：{...} → 获取...` 应在下一行不要同在一行；②里面渲染看起来重复了。多轮三堂会审都没审计出来。

### 1.2 用户澄清的本质
- **不是"重复"，而是两次工具调用**（如 fetchpage 知乎失败 + 腾讯云成功）被前端表现成"同一行重复堆叠"，观感极差。
- 用户要求**好好设计**：单 tool 执行时 observation 如何显示最优雅、并行多 tool 时如何显示最优雅。

---

## 二、根因分析（已核实，非猜测）

### 2.1 数据结构（前端已持有全部所需信息）

**action 步骤**（后端 `action_handler.L944-953` 下发）：
```json
{ "type": "action", "step": N, "exec_type": "single"|"multi", "tools": [
    { "tool": "fetchpage", "target": "https://...", "params": { "url": "...", "prompt": "..." } },
    { "tool": "xxx", "target": "...", "params": { ... } }
]}
```
- `exec_type`：single = 1 个工具；multi = 并行 N 个工具。
- `tools[]`：N 个工具，每元素带 tool/target/params。
- 前端 `sseParser` 已解析到 `ExecutionStep.exec_type` / `.tools`（sseParser.ts:528-556）。

**observation 步骤**（后端 `action_handler.L814-820` 下发）：
```json
{ "type": "observation", "step": N, "tool_result": [
    { "tool_name": "fetchpage", "llm_data": { "summary": "获取...失败", "status": { "exec_code": "error", ... } },
      "llm_data_text": "...", "data_text": "...", "other_data": {} }
]}
```
- `tool_result[]`：N 个工具的结果，**与 action.tools[] 按索引 1:1 配对**。
- 每元素含 tool_name / llm_data.summary（结果摘要）/ llm_data.status.exec_code（成功 error/success/warning）。

### 2.2 前端渲染缺陷（ToolCallLine.tsx）

| # | 缺陷 | 位置 | 后果 |
|---|------|------|------|
| ① | 概览行 `🔧 工具名 参数:{...} → 结果` 全挤在**同一个内联 span** | ToolCallLine.tsx:96-112 | 参数与 →结果超长粘连，视觉拥挤，无换行 |
| ② | `getObsSummary` 只取 `observations[0]` 即 `tool_result[0]` **首项**摘要 | ToolCallLine.tsx:49,74 | **多工具(并行)时只看第一个工具结果，其余工具结果被丢弃** |
| ③ | 不区分 single/multi，不按工具维度组织 | ToolCallLine.tsx | 并行多工具结果挤一团，观感"重复堆叠" |

### 2.3 结论
- 病根 = 前端渲染层未按"工具维度"组织，且只读首项；后端已正确下发 exec_type/tools/tool_result，**无需改后端**。
- 多轮三堂会审未发现：历来只审查"数据读取正确性（getObsSummary/tool_result 数组）"，**未审查"多工具场景下按索引配对展示"** 这一块，属审查盲区。

---

## 三、设计定案

### 3.1 设计原则
1. **前端迎合后端**：后端已下发 exec_type/tools/tool_result，前端按此渲染，不改后端。
2. **工具维度组织**：以"每个工具"为最小视觉单元。
3. **单/并行统一同一结构**（北京老陈定案）：不区分两套形态，仅第一行集合名因个数/称呼而异。
4. **每个工具独立结果**：`tool_result[i]` 与 `tools[i]` 按索引配对，每个工具各自【参数 + 状态 + 摘要】，杜绝"只看第一个"、"挤成一团"。

### 3.2 UI 示意（北京老陈 2026-09-01 定案：统一结构，第一行工具后接集合名 + 同行工具名列表）

**第一行**：`🔧 工具` 后接集合名 —— 单工具显「调用 1 个」，多工具显「并行 N 个」；集合名后**同行**再跟工具名称列表（方括号括起、逗号分隔）。

**多工具（exec_type=multi）**
```
🔧 并行 2 个工具  [fetchpage, fetchpage]
   ├─ fetchpage  参数：{...}
   │    → 获取网页失败
   ├─ fetchpage  参数：{...}
   └─    → 获取网页成功
```
- 外层第一行：`🔧 并行 N 个工具  [工具名1, 工具名2, ...]` —— 集合名与工具名列表在**同一行**。
- 内层**每个工具一个子项**，各自带【工具名 + 独立参数 + 独立状态图标(✔绿 / ✖红 / ⚠橙) + 独立结果摘要】。

**单工具（exec_type=single）** —— 同一结构，仅第一行集合名为「调用 1 个」
```
🔧 调用 1 个工具  [fetchpage]
   ├─ fetchpage  参数：{...}
   └─    → 获取网页失败
```
- 与多工具共用同一套渲染结构，仅集合名与个数不同。
- `→ 结果摘要` 独立一行、缩进显示；状态色：绿(成功)/红(失败)/橙(警告)。

### 3.3 状态图标判断
- 从每工具 `tool_result[i].llm_data.status.exec_code` 取：`success`→✔绿；`error`→✖红；`warning`→⚠橙；缺失→默认。

### 3.4 展开态去重（消除"重复"观感）
- 展开 observation 时（ToolResultRenderer/GenericResultRenderer），**不平铺整个 tool_result 元素**，避免 `llm_data.summary` 与 `llm_data_text`、`data_text`（它们内部都含同一句摘要）三处同义文字重复。
- 只展示一次核心摘要 + 关键字段（状态/时长/其他），或对重叠字段择优单显。
- 【本项为二期，与 3.2 主展示分离，评估后再定】

---

## 四、改动范围

| 范围 | 说明 |
|------|------|
| 前端 `ToolCallLine.tsx` | getObsSummary 按索引取；→结果换行；exec_type 分派单/并行渲染；状态图标 |
| 前端可能的辅助组件 | 视需要，最小化 |
| **后端** | **不改**（exec_type/tools/tool_result 已正确下发） |
| 测试 | 新增/修正单、并行场景渲染用例（测试文件被 gitignore，不提交） |
| 关联组件 | PipelineRenderer 已把 observation 挂到 action（无需改）；孤儿 obs 弱化行保持不变 |

---

## 五、验证与风险

| 项 | 说明 |
|----|------|
| tsc / lint / format | 修改后全绿 |
| 测试 | 新增 single/multi 两条渲染路径用例，修正可能受影响的既有用例 |
| 回归风险 | 低——仅改 ToolCallLine 渲染分支；不动后端、不动 action/observation 数据契约 |
| 兼容 | 单工具 old 数据（exec_type 缺失→默认 single）走 single 分支，不退化 |

---

## 六、审查确认与待定

### 6.1 北京老陈 2026-09-01 已确认
1. 单工具与多工具**统一同一结构**（3.2 已按此更新）。
2. 第一行"工具"后接集合名：多工具显「并行 N 个工具」，单工具显「调用 1 个工具」。

### 6.2 待实施时定夺
1. 内层是否保留框线符号（├─/└─/│），还是纯缩进（暂按用户原示意保留框线）。
2. 折叠态"每工具参数+结果两行"是否足够，还是要默认展开。
3. 3.4 展开态去重（二期）是否本次一并做，还是后续单独处理。

审查通过后，本方案转为实施，并做三轮严格三堂会审。

---

## 七、代码 Diff（设计稿，待三堂会审后实施）

> 改动文件：`frontend/src/features/chat/components/pipeline/ToolCallLine.tsx`
> 不改后端。单/多工具统一结构，第一行集合名+同行工具名列表，内层每工具一个子项（工具名+参数一行、→结果独立一行缩进，各自独立状态+摘要）。

### 7.1 计算段替换（原 L43-77）

**import 说明**：新增子行字号用 13（与展开区 `13 + Spacing.XS` 一致），**无需新增 FontSize import**（保持原 `import { Colors, BorderWidth, Spacing, stepMargin }...` 不变）。

**文件头编辑历史新增**（L14 之后、JSDoc 之前）：
```diff
+// 编辑历史: 2026-09-01 小欧 - 工具观察按工具维度组织: 单/多统一结构, 第一行集合名+同行工具名列表, 内层每工具子行(独立参数+状态+摘要, 按索引与tool_result配对); 修多工具只显首项结果; 修参数结果挤一行 - 小欧-2026-09-01
```

```diff
-  const [open, setOpen] = useState(false);
-  const tools = action.tools || [];
-  // 2026-08-27 小欧 三堂会审: action步骤无tool_params, 参数正确来源为tools[0].params
-  const params = action.tools?.[0]?.params ?? {};
-  const paramText = JSON.stringify(params);
-  const toolName = tools.map((t) => t.tool).join(', ');
-  const obs0 = observations[0];
-  // 编辑历史: 2026-08-27 小欧 修复: 新契约 tool_result 为数组时取首项真实摘要, 不再回落字面量'[工具结果]'(BUG-C)
-  const getObsSummary = (o?: ExecutionStep): string => {
-    const tr = o?.tool_result;
-    if (tr != null) {
-      if (typeof tr === 'string') return tr;
-      if (Array.isArray(tr)) {
-        const parts = tr
-          .map((item) => {
-            if (typeof item === 'string') return item;
-            const obj = item as Record<string, unknown>;
-            const llm = (obj.llm_data || obj.llmData) as
-              | Record<string, unknown>
-              | undefined;
-            return (obj.summary as string) || (llm?.summary as string) || '';
-          })
-          .filter((s) => s);
-        if (!parts.length)
-          return (o?.summary as string) || (o?.content as string) || '';
-        if (parts.length) return parts.join('; ');
-      }
-      return (o?.summary as string) || (o?.content as string) || '';
-    }
-    return (o?.summary as string) || (o?.content as string) || '';
-  };
-  const obsSummary = getObsSummary(obs0);
-  const retryCount = action.action_retry_count;
-  const attemptLabel =
-    retryCount != null && retryCount > 0 ? `(重试${retryCount})` : '';
+  const [open, setOpen] = useState(false);
+  const tools = action.tools || [];
+  // 单 observation step 的 tool_result 数组，与 tools[] 按索引 1:1 配对（2026-09-01 小欧）
+  const obsStep = observations[0];
+  const results = (
+    Array.isArray((obsStep as ExecutionStep | undefined)?.tool_result)
+      ? ((obsStep as ExecutionStep).tool_result as unknown)
+      : []
+  ) as Array<Record<string, unknown>>;
+  const isMulti = action.exec_type === 'multi';
+  const toolCount = tools.length;
+  const collectionLabel = isMulti
+    ? `并行 ${toolCount} 个工具`
+    : `调用 1 个工具`;
+  const toolNameList = tools.map((t) => t.tool).join(', ');
+  const firstLine = `${collectionLabel}  [${toolNameList}]`;
+  // 每工具结果摘要 + 状态（按索引 i 取，杜绝只取首项）（2026-09-01 小欧）
+  // 三堂会审(2026-09-01): 保留旧 getObsSummary 摘要容错(llm_data.summary→data_text→summary→兜底'-'), 防关联退化
+  const getResultSummary = (i: number): string => {
+    const r = results[i];
+    if (!r) return '';
+    const llm = (r.llm_data || r.llmData) as Record<string, unknown> | undefined;
+    return (
+      (llm?.summary as string) ||
+      (r.data_text as string) ||
+      (r.summary as string) ||
+      ''
+    );
+  };
+  const getResultStatus = (
+    i: number
+  ): 'success' | 'error' | 'warning' | undefined => {
+    const r = results[i];
+    if (!r) return undefined;
+    const llm = (r.llm_data || r.llmData) as Record<string, unknown>;
+    const status = (llm.status || {}) as Record<string, unknown>;
+    const code = status.exec_code as string;
+    return ['success', 'error', 'warning'].includes(code)
+      ? (code as 'success' | 'error' | 'warning')
+      : undefined;
+  };
+  const retryCount = action.action_retry_count;
+  const attemptLabel =
+    retryCount != null && retryCount > 0 ? `(重试${retryCount})` : '';
+  const statusColorMap = {
+    success: Colors.SUCCESS,
+    error: Colors.ERROR,
+    warning: Colors.WARNING,
+  } as const;
+  const statusIconMap = { success: '✔', error: '✖', warning: '⚠' } as const;
```

### 7.2 概览行替换（原 L96-112：单行 span 参数→结果挤一起）

```diff
       <span style={{ cursor: 'pointer' }} onClick={() => setOpen((v) => !v)}>
-        🔧 {toolName} {attemptLabel}
-        <span style={{ color: Colors.TEXT.SECONDARY }}>
-          {' '}
-          参数：{paramText.slice(0, 60)}
-          {paramText.length > 60 ? '…' : ''}
-        </span>
-        {obsSummary && (
-          <span style={{ color: Colors.SUCCESS }}>
-            {' '}
-            → {obsSummary.slice(0, 40)}
-          </span>
-        )}
+        🔧 {firstLine} {attemptLabel}
         <span style={{ marginLeft: Spacing.SM, color: Colors.PRIMARY }}>
           {open ? '▲' : '▼'}
         </span>
       </span>
+      {/* 每工具子行：工具名+参数一行，→结果独立一行缩进（2026-09-01 小欧） */}
+      {/* 间距遵循 stepStyles 既有 observation 风格(2026-08-30 定案): 字号 13(与展开区统一, 非12), 行高=字号13+Spacing.XS, 段内折不折=Spacing.XS-2, 间距一律 Spacing 常量派生 */}
+      <div style={{ marginTop: Spacing.XS }}>
+        {tools.map((t, i) => {
+          const paramText = JSON.stringify(t.params ?? {});
+          const sum = getResultSummary(i);
+          const st = getResultStatus(i);
+          // 三堂会审(2026-09-01): 状态缺失时用中性文字色、不显图标, 防误报成功
+          const color = st ? statusColorMap[st] : Colors.TEXT.PRIMARY;
+          const icon = st ? `${statusIconMap[st]} ` : '';
+          const isLast = i === tools.length - 1;
+          const branch = isLast ? '└─' : '├─';
+          const sub = isLast ? '   ' : '│  ';
+          return (
+            <div
+              key={i}
+              style={{ marginTop: Spacing.XS, paddingLeft: Spacing.SM }}
+            >
+              <div
+                style={{
+                  fontSize: 13,
+                  lineHeight: `${13 + Spacing.XS}px`,
+                  color: Colors.TEXT.PRIMARY,
+                }}
+              >
+                {branch} {t.tool}{' '}
+                <span style={{ color: Colors.TEXT.SECONDARY }}>
+                  参数：{paramText.slice(0, 60)}
+                  {paramText.length > 60 ? '…' : ''}
+                </span>
+              </div>
+              {sum && (
+                <div
+                  style={{
+                    marginTop: Spacing.XS - 2, /* 段内折不折 2=XS-2 */
+                    paddingLeft: Spacing.SM,
+                    lineHeight: `${13 + Spacing.XS}px`,
+                    color,
+                    fontSize: 13,
+                  }}
+                >
+                  {sub}   {icon}{sum.slice(0, 60)}
+                </div>
+              )}
+            </div>
+          );
+        })}
+      </div>
```

### 7.3 展开区适配（原 L127-149 observations.map → 按工具逐项完整结果）

```diff
-          {observations.map((o, idx) => (
-            <div key={idx} style={{ marginTop: Spacing.XS }}>
-              {' '}
-              {/* 观察块间 4=XS */}
-              <div
-                style={{
-                  color: Colors.TEXT.SECONDARY,
-                  lineHeight: `${13 + Spacing.XS}px`,
-                  marginBottom: Spacing.XS,
-                }}
-              >
-                观察{observations.length > 1 ? ` ${idx + 1}` : ''}：
-              </div>
-              {/* 2026-08-27 小欧 三堂会审: 富渲染tool_result可达, 有tool_result走ToolResultRenderer否则纯文本 */}
-              {Array.isArray(o.tool_result) && o.tool_result.length > 0 ? (
-                <ToolResultRenderer step={o} />
-              ) : typeof o.tool_result === 'string' ? (
-                <CollapsibleText text={o.tool_result} />
-              ) : (
-                <CollapsibleText text={o.content ?? ''} />
-              )}
-            </div>
-          ))}
+          {tools.map((t, i) => {
+            // 单工具完整结果：构造仅含该工具 tool_result 的临时 step 交给 ToolResultRenderer
+            const singleResult = results[i] ? [results[i]] : [];
+            const singleStep = {
+              ...(obsStep as ExecutionStep),
+              tool_result: singleResult,
+            };
+            return (
+              <div key={i} style={{ marginTop: Spacing.XS }}>
+                <div
+                  style={{
+                    color: Colors.TEXT.SECONDARY,
+                    lineHeight: `${13 + Spacing.XS}px`,
+                    marginBottom: Spacing.XS,
+                  }}
+                >
+                  {t.tool} 结果：
+                </div>
+                {singleResult.length > 0 ? (
+                  <ToolResultRenderer step={singleStep} />
+                ) : (
+                  <CollapsibleText text={obsStep?.content ?? ''} />
+                )}
+              </div>
+            );
+          })}
```

### 7.4 说明
- **唯一取数源**：`results = obsStep.tool_result[]`（与 `tools[]` 索引配对），`getResultSummary(i)` / `getResultStatus(i)` 按索引取，**修复多工具只显示首项结果的旧病**。
- **单/多统一**：`isMulti` 仅影响第一行集合名（并行 N 个 / 调用 1 个），内层结构完全一致。
- **状态色/图标**：从 `llm_data.status.exec_code` 得出 success✔绿 / error✖红 / warning⚠橙；**状态缺失→中性文字色、不显图标**（三堂会审防误报成功）。
- **兼容**：老数据无 `exec_type` → 走 "调用 1 个工具"；无 observation/tool_result → `results=[]` 时每工具只显参数子行、结果留空。`getResultSummary` 保留摘要兜底（llm_data.summary→data_text→summary），不退化。
- **配对根基已核实（三堂会审 2026-09-01）**：后端 `action_handler.execute_tools`（L642-649 按原序填回 results）与 `build_observation`（L770 zip(all_calls, results) 顺序 append tool_result）均与 `tools[]` 同一 all_calls 顺序 → `tools[i]` 与 `tool_result[i]` 索引严格一致，配对可靠。
- **间距风格遵循既有 observation 规范（stepStyles 2026-08-30 定案）**：新增子行字号 13（与展开区 `13 + Spacing.XS` 统一，不用 12 造成同一行两档字号割裂），行高=13+Spacing.XS；段内折不折用 `Spacing.XS - 2` 派生，不写死 2；工具块间 Spacing.XS(4)，缩进 Spacing.SM，标签底线 Spacing.XS(4)；展开区(7.3)沿用原 observation 展开样式（`13 + Spacing.XS` 原样保留，不改观感）。
- **展开态去重（二期）**：3.4 所述字段重叠去重本次不并入 7.3，后续单独处理。
- **实时/历史双模式支持（已核实 2026-09-01）**：右侧查看区唯一渲染入口 `RightViewer`（L172）把"实时任务(liveSteps 回放)"与"历史回放"**共用同一个 PipelineRenderer→ToolCallLine**；且两者数据结构完全一致——后端同一 ActionStep/ObservationStep，落库 `append_execution_step` 存**完整 step_json**（storage.py L58/L324，5.1 铁律不截断），历史加载 `load_execution_steps`（L344-359）按 step_index **原样读出无删减**。故 dff 所依赖的 `exec_type/tools/tool_result` 在实时与历史中逐字段一致，**该 UI 天然同时支持两种模式，无需按模式分支**。注：仅对更早版本遗留的旧 `action_tool` 结构历史数据（非当前系统生成）不适用——此为系统"禁止 backward"既定决策（stepStyles L200 action_tool 须被拒），非本次 dff 引入的退化。

### 7.5 渲染 UI 效果详细展示（北京老陈定案版，2026-09-01 03:28:42 小欧）

> 以下为按新设计实际渲染的效果示意。颜色语义：绿=成功/红=失败/橙=警告/中性灰=无状态；框线 ├─/└─ 区分工具次序（最后一项用 └─ 收尾，非最后用 ├─；子结果行用 │ 前导对齐）。字号 13、行高=13+4、间距按既有规范。

#### 场景 A · 单工具成功（exec_type=single，折叠态）
```
🔧 调用 1 个工具  [fetchpage] ▼
   └─ fetchpage  参数：{ "url": "https://cloud.tencent.com/...", "prompt": "..." }
      → ✔ 获取网页https://cloud.tencent.com/developer/article/2587122成功
```

#### 场景 B · 单工具失败（exec_type=single，折叠态）
```
🔧 调用 1 个工具  [fetchpage] ▼
   └─ fetchpage  参数：{ "url": "https://zhuanlan.zhihu.com/...", "js_render": false }
      → ✖ 获取https://zhuanlan.zhihu.com/p/...网页失败 (HTTP 403)
```

#### 场景 C · 并行多工具 · 一失败一成功（exec_type=multi，折叠态）—— 即用户反馈的真实场景
```
🔧 并行 2 个工具  [fetchpage, fetchpage] ▼
   ├─ fetchpage  参数：{ "url": "https://zhuanlan.zhihu.com/p/1916...", "timeout": 30 }
   │    → ✖ 获取网络失败，HTTP 403
   ├─ fetchpage  参数：{ "url": "https://cloud.tencent.com/...", "timeout": 30 }
   └─    → ✔ 获取网页成功，200
```
> 原来"fetchpage, fetchpage 参数：{...} → 结果"挤成一团、且只显示第一个工具结果——现在**每个工具独立一行**，各自参数+各自状态+各自结果，失败红成功绿一眼可辨。

#### 场景 D · 并行多工具 · 成功/失败/警告混合（exec_type=multi，折叠态）
```
🔧 并行 3 个工具  [read_file, list_directory, lookup_code] ▼
   ├─ read_file  参数：{ "path": "F:/Project/src/main.ts" }
   │    → ✔ 读取文件成功（6 行）
   ├─ list_directory  参数：{ "path": "F:/Project/src" }
   │    → ⚠ 目录存在但部分条目无权限
   └─ lookup_code  参数：{ "keyword": "execute_tools" }
      → ✖ 未找到匹配项
```

#### 场景 E · 单工具 · 折叠态 → 展开态（点 ▾ 展开后追加完整结果）
**折叠态：**
```
🔧 调用 1 个工具  [fetchpage] ▾
   └─ fetchpage  参数：{ "url": "https://cloud.tencent.com/...", "timeout": 30 }
      → ✔ 获取网页成功，200
```
**展开态（或 点 ▲ 收起）：**
```
🔧 调用 1 个工具  [fetchpage] ▲
   └─ fetchpage  参数：{ "url": "https://cloud.tencent.com/...", "timeout": 30 }
      → ✔ 获取网页成功，200
   参数：
   {"url":"https://cloud.tencent.com/developer/article/2587122","extract_format":"markdown","js_render":false,"timeout":30,"prompt":"提取2025年AI大模型技术前沿展望的核心趋势"}
   fetchpage 结果：
   (此处为 ToolResultRenderer 渲染的完整结果内容，如 title/摘要/正文结构)
```

#### 场景 F · 并行多工具 · 展开态（每工具独立完整结果）
```
🔧 并行 2 个工具  [fetchpage, fetchpage] ▲
   ├─ fetchpage  参数：{ "url": "https://zhuanlan.zhihu.com/..." }
   │    → ✖ 获取网络失败，HTTP 403
   │    fetchpage 结果：
   │    (该工具完整失败结果详情)
   └─ fetchpage  参数：{ "url": "https://cloud.tencent.com/..." }
       → ✔ 获取网页成功，200
       fetchpage 结果：
       (该工具完整的成功结果详情：标题/章节/正文)
```

#### 渲染要点说明
1. **第一行（集合行）**：`🔧 并行 N 个工具  [工具名1, 工具名2]` 或 `🔧 调用 1 个工具  [工具名]`——集合名与工具名列表**同一行**，机器可读、一眼知数量与工具。
2. **每工具子行**（折叠态即展示）：
   - 参数行：`├─/└─ 工具名  参数：{压缩60字}`；
   - 结果行：`│/空格  → ✔/✖/⚠ 摘要(60字)`，独立一行缩进，状态着色。
   - 最后一项工具用 `└─` 收尾，中间项用 `├─`，结果行前导 `│`。
3. **状态语义**：成功✔绿 / 失败✖红 / 警告⚠橙；**状态缺失→中性灰、不显图标**（防误报）。
4. **展开态**：在折叠态基础上追加「参数：完整JSON」+ 每工具「工具名 结果：」下的完整 ToolResultRenderer 渲染（每工具独立，不再混在一块）。
5. **间距/字号**：字号 13、行高=13+Spacing.XS、段内折不折 Spacing.XS-2、工具块间 Spacing.XS、缩进 Spacing.SM——全部遵循既有 observation 规范。
6. **单/多统一**：除第一行集合名（并行 N 个 / 调用 1 个）外，内层渲染结构完全一致，代码只写一套，按 `exec_type` 拼第一行文案。
