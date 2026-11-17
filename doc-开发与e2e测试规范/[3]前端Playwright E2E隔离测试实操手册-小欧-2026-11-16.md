# [3] 前端 Playwright E2E 隔离测试实操手册

> 文档名称：[3]前端Playwright E2E隔离测试实操手册-小欧-2026-11-16
> 类型：可执行指导手册（唯一标准，前端所有测试验证按此执行）
> 基线：`F:\OmniAgentAs-01`（frontend/），提交 `e03f373a6`

---

## 0. 范围与关键结论

- 本手册是前端 **Playwright 真浏览器** E2E 隔离测试的**唯一执行标准**。
- 端口以**当前代码**为准：主后端 `8100`（`BACKEND_PORT` 缺省），非旧文档的 8000。
- 废弃 [1]全链路E2E测试手册 中 8000 端口描述，以其断流进程分离思想为本手册 M-B 依据。

---

## 1. 选型决策（先答"这个用例走哪套"）

```
要测的前端场景？
├─ 功能链路(发消息/查天气/切会话/刷新/回放) ──► M-A 普通模式
├─ 断线/重连/杀进程/续传 ──────────────────► M-B 断流重连
├─ 写 provider/models/settings 配置 ────────► M-C 配置隔离（必须！）
├─ 多 worktree / 临时分支验证 ─────────────► M-D 临时模式
└─ 性能测量(DOM/渲染耗时) ────────────────► M-A + CDP(见§5)
```

---

## 2. 四种模式（端口对照）

| 模式 | 页面 vite | API | 后端 | 数据隔离 | 入口 | 典型 |
|---|---|---|---|---|---|---|
| **M-A 普通** | 5173(默认) | vite proxy `/api` | 8100 | 无 | `startNormalUiEnv` | fre2e_02~05,07,13~20,22~23 |
| **M-B 断流** | 5173(hmr:false) | 独立代理 `9000` | 8100 | 无 | `startDevServer`+`startProxyServer` | fre2e_01,06 |
| **M-C 配置隔离** | 5174(hmr:false) | proxy 9001→8898 / request 直连 8898 | `8898` | ✅ 临时config副本 | `isolatedEnvHooks` | fre2e_08~12 |
| **M-D 临时** | 5273(hmr:false) | 独立代理 `9002` | 8010 | 独立 | `vite.interject.config`+`playwright.interject.config` | 临时验证 |

**端口单源铁律**：
- 主后端端口：`BACKEND_PORT` 环境变量，缺省 **8100**（`vite.config.ts` 与 `backend/start_dev.ps1` 同源）。
- api-proxy 目标：`PROXY_TARGET`/`BACKEND_PORT`，缺省回落 8100。
- 改端口只改**一个**源头，勿在多个 config 各改一半。

---

## 3. 各模式统一步骤

### 3.0 通用铁律
- **真浏览器、真后端、真 LLM、真 SQLite，禁止 Mock**（性能测量除外，见§5）。
- 测试代码不入版本库。
- Playwright `workers:1` 串行（本地并行会致真实后端探针互踩/残留）。
- 产物统一落 `frontend/e2e_case/output/`。
- 清场**只按端口精确杀**，严禁按进程名批量杀（`killPort` 已合规）。

### 3.1 M-A 普通模式
```ts
import { startNormalUiEnv, runChatFlow } from '../e2e_front_lib';
await startNormalUiEnv(FRONTEND_DIR);      // 5173复用优先
const text = await runChatFlow(chat, prompt, { diag });
```
- API 走相对路径 `/api/v1`，经 vite proxy → 8100，同源无 CORS。

### 3.2 M-B 断流重连模式
- 断流只 kill 代理 `9000` → 浏览器↔9000 RST 前端立即感知(真断线)，页面(5173 hmr:false)永活不 reload → 重连 timer 存活 → 续传必达。
- **不要**直接 target 后端断流（须杀 vite 会触发整页 reload 销毁重连）。
- 页面 API 经 `VITE_API_BASE_URL=http://localhost:9000/api/v1` 直连代理(跨域 CORS)。
- CORS：`api-proxy.ts` 自答 OPTIONS + **反射 Origin**（替换而非追加，防重复头）。

### 3.3 M-C 配置隔离模式（三进程栈）
```ts
const hooks = isolatedEnvHooks(FRONTEND_DIR);   // beforeAll起 / afterAll拆
// 页面 ISO_PAGE(5174)、API直连 ISO_API(8898)、写配置落盘路径 isoConfigPath()
```
- 真 config 只读拷临时副本 → 隔离后端 `OMNIAGENT_CONFIG_PATH` 改道 → **物理够不到真 config**。
- 副本里 provider/api_key 仍是真值(可用真实模型)，隔离的只是**写**的落点。
- 拆栈自动删副本，**真配置全程不可写、免还原**。
- 端口未占用在起栈前内置校验，被占显式报错。

### 3.4 M-D 临时模式
- `vite.interject.config`(5273) + `playwright.interject.config`(baseURL 显式指 5273)。
- 注释标明"验证完删除，不入库"。

---

## 4. 复用设施速查（e2e_front_lib）

| 文件 | 提供 | 用途 |
|---|---|---|
| `normal-chat.ts` | `startNormalUiEnv`/`runChatFlow` | 普通链路启动+消息流 |
| `isolated-env.ts` | `isolatedEnvHooks`/`ISO_PAGE`/`ISO_API`/`isoConfigPath` | 配置隔离栈 |
| `process.ts` | `startDevServer`/`startProxyServer`/`ensureDevServer`/`killPort`/`waitPortUp/Down` | 进程/端口控制 |
| `api-proxy.ts` | 独立后端代理(透传+CORS反射) | M-B/M-C 的 API 链路 |
| `page-anchors.ts` | 左侧任务列表/地址栏读取 | 会话页断言锚点 |
| `stream-diag.ts` | 全链路诊断(网络+SSE console) | 失败取证 |
| `auth.ts`/`global-setup.ts` | 访问口令注入+storageState | 鉴权统一注入 |

---

## 5. 性能测量专项（CDP 抓耗时）

> 参考 [46] 实测方法。前端卡顿定位：用 Playwright + CDP 抓**主线程 CPU Profile + 请求瀑布 + longtask**，区分"渲染慢"vs"等数据慢"。

```ts
import { chromium } from '@playwright/test';
const cdp = await ctx.newCDPSession(page);
await cdp.send('Profiler.enable');
await cdp.send('Profiler.start');
// ... goto + 操作 ...
const { profile } = await cdp.send('Profiler.stop'); // 解析self-time定位热点
```
- **关键判据**：`(idle)` 占比高 → 等网络数据（瓶颈在接口/数据量，非渲染）；真实渲染函数占比高 → 渲染层问题。
- 请求瀑布看哪些请求 `>1s`；对比 `/messages`(可能70MB+) vs `/tasks`(278KB) 的量级差异定位数据爆炸。

---

## 6. 常见陷阱

| 陷阱 | 后果 | 规避 |
|---|---|---|
| 写配置没走 M-C | 测试值写真 config.yaml(进程被杀即永久残留) | 凡写配置一律 M-C |
| 断流直接 target 后端 | 续传语义失真 | M-B 独立代理 9000 |
| CORS 重复头 | 浏览器拒收 | 代理反射 Origin 替换 |
| 端口按 8000 旧文档写 | 连不上(当前8100) | 用 BACKEND_PORT 缺省8100 |
| localhost↔IPv6 | vite 健康误判 | ensureDevServer 用 127.0.0.1 严格200 |
| 断言硬编码真 config 路径 | 写真配置当验收 | M-C 用 isoConfigPath() |

---

## 7. 新增用例落地清单

1. `e2e_case/fre2e_XX_场景.spec.ts`，按 §1 选模式。
2. beforeAll 按模式起环境(M-A/M-B/M-C/M-D)。
3. 断言用 `page-anchors`；失败自动 `printDiag`。
4. 产物自动落 `e2e_case/output/`。
5. 跑：`cd frontend && npx playwright test fre2e_XX`.
6. 验证 `tsc/eslint/prettier` 全绿 + Playwright 串行通过。

---

> 编写人：小欧；日期：2026-11-16
> 关联：[2]隔离方法固化标准（端口一致），[46]性能优化方案（性能测量方法）