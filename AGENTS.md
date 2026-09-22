# AGENTS.md - OmniAgentAs-desk
### 1.1 头条铁规：分析问题、写文档、编辑历史\注释、commit规则，升级tag
**系统命令**：本机必须使用Windows系统命令。杜绝使用Linux命令
**文档签名**：（1）文档名称: +签名+时间； （2）内容签名： +编写/ 更新人 + 签名  （3）编辑型文档， 禁止删历史版本信息。
**代码编辑历史**： 格式: 日期+署名+修改的目和逻辑说明
                  插入: 最新的编辑历史在板块最下边,<严禁中间插入>
**提交标题**:   格式 `<type>:<代码名> <description> - <签名>-<日期>`，types: feat/fix/refactor/perf/test/docs
        严令禁止 commit任何测试相关的代码文件
**打tag**：1.在version.txt文件头部插入从上一个tag以来的所有commit的变更信息的说明.2.打tag

**严禁** 用PowerShell 脚本来操作代码编辑\替换,否则导致代码编码错误

## 1.2 编码铁规（必须遵守）--代码落盘前和落盘后进行<三堂会审>= 合规\合理\关联逻辑审查
**合规检查**  严格检查代码是否遵守10大规范--合规检查,
**合理检查**  逻辑流程是否最优雅/最佳,杜绝绕来绕去
**关联逻辑检查**相关代码上上下下,前前后后的逻辑功能,必须增强且进化功能,严禁退化功能
**10大规范**  日常6条 + 重构4条:

**日常编码**  6 条规范

| 原则 | 说明 | 违反后果 |
| **SRP** — 单一职责 | 一个类/模块/函数只做一件事 | 改了 A 影响 B |
| **DRY** — 不重复 | 相同逻辑只写一次，抽取共用 | 改了 A 漏了 B |
| **KISS-DIRECT** — 简单直接＼最优雅的逻辑 | 设计简单 + 逻辑直线，不提前引入抽象，不七绕八绕 | 代码看不懂、数据流混乱 |
| **SLAP** — 同一抽象层 | 一个函数不混搭高层编排和底层细节 | 读代码像读天书 |
| **YAGNI** — 不要过度设计 | 不加用不上的接口/模式/抽象 | 废弃代码越积越多 |
| **禁止backward** | 所有代码修改/更新/重构坚决杜绝向后兼容做法 | 新旧混杂、代码混乱 |

**KISS-DIRECT（简单直接原则）详细说明**：

| 要求 | 反例（七绕八绕） | 正例（直线） |
| 设计简单 | 为了"可扩展"引入注册表，实际只有2个entry | if/elif直接分派 |
| 逻辑直线 | A→B→C→D→E，中间B/C/D只透传 | A→E直接传递 |
| 调用链直接 | `a().b().c().d().e()` 5层链式调用 | 直接调用核心函数 |
| 无中间变量 | `x=f(); y=g(x); z=h(y); return z` | `return h(g(f()))` |
| 无跳来跳去 | A调B，B调C，C回调A | 单向调用，无循环依赖 |
| 无双重解析 | dict→JSON字符串→parse→dict | 直接用dict |
| 无透传函数 | `def f(x): return g(x)` 只调一个函数 | 内联，直接调g |
| 无中间层 | 3层函数每层只调下一层 | 合并为1层 |
| 无注册表滥用 | 2-entry的OrderedDict注册表 | if/elif直接分派 |

**重构代码/框架** 4条规范：

| 原则 | 说明 | 适用场景 |
|------|------|---------|
| **OCP** — 开闭原则 | 对扩展开放，对修改封闭 | 库/框架/公共组件设计 |
| **LSP** — 里氏替换 | 子类不违反父类约定 | 继承体系 |
| **ISP** — 接口隔离 | 接口职责单一，不塞入不相关方法 | 多实现/插件系统 |
| **复用优先** | 有公用则复用，能够公用的则新建并入库 | 新增函数前必须先查FUNCTIONS.md，禁止局部重造轮子 |

### 违反后果
上述原则是必须遵守的编码纪律。违反者代码被打回重写，直到符合原则为止。

## 1.3 公用函数规范（必须遵守）

| 规则 | 说明 |
|------|------|
| **先查后建** | 写代码前先查`backend/FUNCTIONS.md`清单，有则复用，无则新建 |
| **分层存放** | 全局层`app/utils/`、Agent层`agent_utils/`、工具层`toolhelper/` |
| **禁止重复** | 相同逻辑禁止重复实现，必须使用已有公用函数 |
| **及时更新** | 新建公用函数后必须添加到FUNCTIONS.md清单 |

##1.4 拆分\重构代码**规范（必须遵守）
**核心心原则**：能复制就复制，不重写
**拆分大文件/函数时** 最安全的做法是**复制原代码逻辑，只改导入路径，不改业务逻辑**。重写会引入新错误，复制能保证行为不变。

## 1.5 前后端相关逻辑和参数规范（必须遵守）

**后端为主**: 前端迎合后端的策略,逻辑和参数对应进行设计和修改
## 1.6 代码复核 复查纪律
1. 读取最新本地代码 熟读3遍, 复核10遍
2. 复查的要求,功能只能正确\增强\优化, 杜绝退化
3. 合规检查和合理检查

## System & Platform

- **OS**: Windows only. Use PowerShell. No Linux/macOS commands.
- **Shell**: PowerShell 7+. Use `Select-String` instead of `grep`.
- **Python**: 3.13 at `E:\Appsw\python31311\`
 **Prompt logging**: 
`backend/logs/`
`backend/logs/prompt-logs/`

---

## Commands

### Backend (workdir=`backend/`)

```bash
python -m uvicorn app.main:app --reload          # dev server (port 8000)
pytest                                            # all tests
pytest -x --tb=short                              # fast fail
pytest -k test_name                               # match by name
```

### Frontend (workdir=`frontend/`)

```bash
npm run dev          # Vite dev server (port 5173)
npm run test         # Vitest
npm run test -- --run <name>  # single test
npm run lint         # ESLint
npm run format:check # Prettier
npm run check        # lint + format:check (run before commit)
npm run test:e2e     # Playwright
```

---

## E2E 全链路测试（核心要点）

> 后端完整流程见 `backend/e2etests/全链路E2E测试手册-小健-2026-05-23.md`（v2.16）。前端 E2E 见第八章。本节抽取每次 E2E 必读要点。

### 后端 E2E（pytest + 真实后端 + 真实 LLM）

**定位**：验证 API→Agent→LLM→Tool→DB→SSE 全链路，深度校验 DB 记录完整性、SSE-DB 一致性、prompt 日志对齐、token 用量追踪。76 个 case（P0-P5/PAR/重连/复合），核心 helper `e2e_helpers.py`（32 函数，2350 行）。

#### 启动后端（每次测试前必做）

1. 杀掉旧进程：`Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess -Force`
2. 独立 PowerShell 窗口启动（**不走 OpenCode bash tool**，避免日志混扰）：
   `Start-Process powershell -ArgumentList "-NoExit","-Command","cd 'F:\OmniAgentAs-repair\backend'; python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000" -WindowStyle Normal`
3. 验证：`Invoke-RestMethod http://127.0.0.1:8000/api/v1/health` 返回 200（或窗口显示 `Application startup complete`）

#### 执行脚本（铁律）

- **一次只跑一个 case**，严禁批量；核心脚本默认超时 2000s，**严禁给启动脚本另设超时**
- E2E 调真实 LLM，单次常 >120s；OpenCode bash 工具会强杀进程 → **必须用 subprocess.Popen 方式**，禁止直接 bash `python -m pytest`
- 方式：用 Python 内联脚本调 `subprocess.Popen`，bash tool timeout 设 `9007199254740991`，pytest 自行管理超时（`--timeout=2900`）；stdout/stderr 落盘 `tests/output/XXX_stdout.txt` / `XXX_stderr.txt`，结果查 junitxml
  ```
  python -c "
  import subprocess, sys, os, time
  out_dir = 'tests/output'
  os.makedirs(out_dir, exist_ok=True)
  p = subprocess.Popen(
      [sys.executable, '-m', 'pytest', 测试文件, '--timeout=2900', '-x', '--tb=short', '-v',
       f'--junitxml={out_dir}/XXX_result.xml'],
      stdout=open(f'{out_dir}/XXX_stdout.txt', 'w'),
      stderr=open(f'{out_dir}/XXX_stderr.txt', 'w'))
  deadline = time.time() + 3000
  while p.poll() is None and time.time() < deadline: time.sleep(10)
  if p.poll() is None: p.kill(); print('TIMEOUT')
  else: print(f'EXIT_CODE={p.returncode}')
  with open(f'{out_dir}/XXX_stdout.txt') as f: print(f.read())
  with open(f'{out_dir}/XXX_stderr.txt') as f:
      e = f.read()
      if e.strip(): print(e)
  "
  ```

#### 执行检查（手动，逐项验证）

按 3 项验证，全过才进入下一个 case：
1. **代码错误异常检查（最高优先级）**：查日志 traceback/ERROR、SSE 是否有 error 事件 → 有则立即停，走修复
2. **调用链分析**：工具选择/顺序/LLM 次数是否合理，输出 `[CALL CHAIN]`
3. **参数正确性**：路径/关键词等是否准确

---

### 前端 E2E（Playwright + 真实浏览器 + 真实后端）

**定位**：验证浏览器 UI→SSE 流→UI 渲染→断线重连全链路。8 个 case（fre2e_01~08），公共库 `e2e_front_lib/`（4 模块：POM/进程控制/SSE 诊断/普通会话封装）。

#### 架构特点

| 角色 | 进程 | 职责 |
|------|------|------|
| 页面服务 A | vite dev `:5173`（hmr:false） | 永活服务页面，**全程不杀** |
| 后端代理 B | `e2e_case/api-proxy.ts :9000→8000` | 页面 API/SSE 直连目标（断线测试用） |
| 后端 C | uvicorn `:8000` | 内存任务持有者 |

断线测试原理：`killPort(9000)` 杀 B → 浏览器↔A 完好、仅 API 链路断（真 TCP RST）→ C 任务后台存活 → 重启 B → 前端退避 `GET /chat/stream/{task_id}?after_seq=` 断点续传。

#### 执行方式

```bash
npx playwright test fre2e_01_reconnect_ui.spec.ts --headed --reporter=line   # 单 case
npm run test:e2e      # 整组（先 lint + format）
npm run test:e2e:ui   # UI 模式
npm run test:e2e:debug # 调试模式
```

#### 关键机制

| 机制 | 说明 |
|------|------|
| 日志对账防假通过 | `logBaseOf` 记基线 → `readLogSince` 只读本轮新增 → 断言重连端点 `after_seq>0` |
| 真进程断流 | `killPort(9000)` 产生真实 TCP RST；禁 `setOffline`（无法断 in-flight SSE） |
| run-on 检测 | `hasAdjacentDup` 逐行检测行内相邻重复（6~30 步滑动窗口） |
| 诊断挂满+失败即打 | 开头必 `attachStreamDiag`；任何一步失败先 `printDiag` 打全量证据链再 throw |

---

### 铁律（前后端共用）

- 测试目的是**发现问题**，不是跑脚本；严禁看到 FAIL 跳过
- 一律真实后端 + 真实 LLM + 真实工具 + 真实 SQLite（`~/.omniagent/chat_history.db`），**禁止 Mock**

---

## Request Flow

FastAPI `/api/v1` → `stream_orchestrator.py`(SSE 编排) → `agent_runner` → `UniversalAgent.run_react_cycle()` → SSE。详细架构见 `README.md` 二~六章。

---## Key Dependencies

| Layer | Tech | Notes |
|-------|------|-------|
| Backend | FastAPI, Uvicorn, SQLAlchemy, aiosqlite | SQLite `~/.omniagent/chat_history.db` |
| | **httpx==0.26.0, httpcore==1.0.1** | **LOCKED** — 0.28.1 breaks TLS |
| | Pydantic v2 | Tool schemas |
| Frontend | React 18, TypeScript 5, Vite | |
| | Ant Design 5, Axios, React Router | |
| | Vitest, Playwright, ESLint, Prettier | |

**Server URLs**: Backend `http://127.0.0.1:8000` | API docs `http://127.0.0.1:8000/docs` | Frontend `http://localhost:5173`

---

## Known Pitfalls

| Pitfall | Detail |
|---------|--------|
| **httpx version lock** | `httpx==0.26.0` required. Don't upgrade — 0.28.1+ upgrades httpcore which breaks TLS. |
| **Tool impl vs registration** | Functions in `{cat}_tools.py`, registration in `{cat}_register.py`. Don't confuse them. |
| **`_loaded_categories`** | Per-agent set for tool loading. Initialized to `{FUNDAMENTAL, FILE}`. |



## Git Workflow

```bash
# Commit format: <type>:<文件名> <description> - <签名>-<日期>
# types: feat/fix/refactor/perf/test/docs

# Tag (PATCH only without asking):
# 1. Insert 从上一个tag以来的所有commit summary into version.txt (project root, append at top)
# 2. git tag v{major}.{minor}.{patch+1}
```

`version.txt` is append-only, oldest at bottom.

---## Code Conventions

### Python
- snake_case functions/vars, PascalCase classes, UPPER_SNAKE_CASE constants
- Type hints required; use `Optional[X]` (not `X | None`)
- Tools return `{code, data, message}` structured responses
- Comments: must include author + date

### TypeScript/React
- PascalCase components, camelCase functions/vars
- kebab-case filenames (`my-component.tsx`)
- No default exports for components
- Use `@/` alias for absolute imports
- Run `npm run check` before commit

-