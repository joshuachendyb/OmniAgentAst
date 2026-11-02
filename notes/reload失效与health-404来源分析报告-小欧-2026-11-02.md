# reload 失效与 /health 404 来源分析报告

**创建时间**：2026-11-02 20:59:31
**编写人**：小欧
**文档类型**：分析报告（编辑型）

## 版本历史

| 版本 | 时间 | 作者 | 修改简介 |
|---|---|---|---|
| v1.0 | 2026-11-02 20:59:31 | 小欧 | 首版：查清后端 reload 失效根因、开发控制台 `/health` 404 刷屏来源，并界定与本次改动的关系 |

---

## 一、结论摘要

1. **后端服务本身是正常的**：`/health` 返回 200 healthy，py-spy 显示工作进程所有线程 idle，没有卡死、没有阻塞。
2. **`--reload` 已经死了**：不是配置错，是 uvicorn 的 Windows 重启流程卡在 `process.join()` 上，永久阻塞。从 2026-11-02 20:37:34 我保存 `health.py` 那一刻起，之后所有后端改动都不会再生效，直到手工重启父进程。
3. **开发控制台每 30 秒一条 `GET /health → 404` 与 reload 无关**：是 OpenCode 桌面端自带的 `opencode-cli` 进程在直连 `127.0.0.1:8000/health`（少了 `/api/v1` 前缀），不是本项目前端代码发的。
4. **不是 uvicorn 版本低的问题**：本地 0.46.0，最新 0.54.0，但上游 master 分支这段 `restart()` 代码与本地**一字不差**，升级无法解决。

## 二、现场时间线

| 时间 | 事件 |
|---|---|
| 2026-11-01 20:08:38 | 后端父进程 12904 启动（`--reload --reload-dir app --host 0.0.0.0 --port 8000`） |
| 2026-11-01 20:08:39 | 子进程（worker）12040 启动，此后再未更换 pid |
| 2026-11-02 20:37:34 | 小欧保存 `backend/app/api/v1/health.py`（加 `host/server_ip/pid` 字段） |
| 2026-11-02 20:38:00 起 | 开发控制台每 30 秒出现 `HTTP Exception: 404 - Not Found \| GET /health` |
| 2026-11-02 20:49:48 | 小欧仅修改该文件 mtime（不动内容）做 reload 试探，8 秒后 worker 仍为 12040 |
| 2026-11-02 20:49:56 | `/health` 仍返回旧结构（无 host/server_ip/pid） |
| 2026-11-02 20:59:31 | 本报告完成 |

## 三、reload 失效根因（代码级）

### 3.1 进程实测

```
父进程 12904  ppid=1468     start=11/01/2026 20:08:38
 └ 子进程 12040 ppid=12904   start=11/01/2026 20:08:39
```

父进程工作目录实测为 `F:\OmniAgentAs-01\backend`（`psutil.Process(12904).cwd()`），即 `--reload-dir app` 监视的正是本仓库的 `app/`。**监视目录没错。**

### 3.2 父进程栈（py-spy dump --pid 12904）

```
run (uvicorn\main.py:612)
run (uvicorn\supervisors\basereload.py:59)      ← 检测到变更，进入 restart()
restart (uvicorn\supervisors\basereload.py:98)  ← 卡在这一行
join (multiprocessing\process.py:149)
wait (multiprocessing\popen_spawn_win32.py:114)
```

`basereload.py:98` 就是 `self.process.join()`。

### 3.3 子进程栈（py-spy dump --pid 12040）

```
run (uvicorn\server.py:75)
run_until_complete (asyncio\runners.py:212)
_run_once (asyncio\base_events.py:2012)
select (selectors.py:314)
```

子进程**在正常等连接**，完全没有收到退出信号；其后 `db-txn_0/1/2`、`console-writer` 线程均为 idle。

### 3.4 机制还原（uvicorn `supervisors/basereload.py` 87-101 行）

```python
def restart(self):
    if sys.platform == "win32":
        self.is_restarting = True
        os.kill(self.process.pid, signal.CTRL_C_EVENT)   # 想用 Ctrl+C 停子进程
        sys.stdout.write(" "); sys.stdout.flush()
    else:
        self.process.terminate()
    self.process.join()        # ← 无超时；子进程不退 = 父进程永久阻塞
    self.process = get_subprocess(...)   # ← 永远执行不到
    self.process.start()
```

Windows 上 `CTRL_C_EVENT` 不是"给指定进程投递信号"，而是向 **console 进程组**广播控制台事件；由 `multiprocessing spawn` 拉起的子进程若不在同一控制台组、或事件被吞，就收不到。子进程照常服务 → `join()` 永久等待 → 父进程不再回到 `for changes in self` 循环 → **之后的文件变更全部不再处理**。

### 3.5 附带损伤：Ctrl+C 也退不掉

```python
def signal_handler(self, sig, frame):
    if sys.platform == "win32" and self.is_restarting:
        self.is_restarting = False      # 只复位标志，不清 should_exit
    else:
        self.should_exit.set()
```

因为卡在 `restart()` 里时 `is_restarting` 一直是 `True`，此时在控制台按 Ctrl+C 只会把标志复位，不会 `set()` 退出事件；而父进程本就阻塞在 `join()`，`should_exit` 根本没人读。**这条进程只能 kill，不能优雅退出。**

### 3.6 是不是版本低？

- 本地：`uvicorn 0.46.0`，`watchfiles 1.2.0`
- 最新：`uvicorn 0.54.0`（`pip index versions uvicorn` 实测）
- 小欧拉取上游 master 的 `uvicorn/supervisors/basereload.py` 逐行比对：`restart()`、`signal_handler()` 与本地 0.46.0 **完全相同**，`join()` 仍无超时。

**结论：升级不修这个问题。** 这是上游在 Windows 上的结构性缺陷，不是版本陈旧。

## 四、`/health` 404 刷屏的来源

### 4.1 抓取方法

在 30 秒节拍前后每 50 毫秒轮询 `Get-NetTCPConnection -RemotePort 8000`，记录 pid 与本地端口。

### 4.2 抓到的全部客户端

| 时间 | 状态 | 进程 | 说明 |
|---|---|---|---|
| 20:54:57 | Established | pid=17328 `node`（Vite dev server） 61502→8000 | 长连接，承载 `/api/*` 代理流量（正常） |
| 20:54:59 | Established | pid=8100 `opencode-cli` 63143→8000 | **短连接，30 秒一次** |
| 20:55:29 | Established | pid=8100 `opencode-cli` 57544→8000 | 同上，间隔正好 30 秒 |

后端日志 404 出现在 `:00` 与 `:30`（`20:54:59.4` 发出、日志记 `20:55:00`），**与 opencode-cli 的连接节拍完全对齐**。

### 4.3 责任界定

- `opencode-cli.exe serve --service`（父进程为 OpenCode 桌面端 `OpenCode.exe`）每 30 秒连一次 `127.0.0.1:8000/health`。
- 本项目前端所有探活路径都是 `/api/v1/health`（`health.api.ts:31` 走 axios baseURL `/api/v1`；`utils/network.ts:32` 传的 `API_BASE_URL` 含 `/api/v1`），**不会产生裸 `/health`**。
- 本项目后端只把 router 挂在 `/api/v1` 下（`health.py:69` 的 `@router.get("/health")` 经 `_mount(..., "api/v1" 前缀)`），裸 `/health` 必然 404，这与 2026-11-01 提交 40480e0 的"动态挂载收窄"设计一致，是**预期行为**，不是 bug。

**结论：这批 404 是 OpenCode 桌面端自身进程的探测行为，属于工具侧噪音，与本项目代码、与 reload 失效均无因果关系。**

## 五、与本次改动的关系

| 事项 | 是否本次改动引起 |
|---|---|
| `/health` 缺 `host/server_ip/pid` | 是：改动已写入 `health.py`，但因 reload 卡死未被加载 |
| reload 卡死 | 否：uvicorn Windows 重启流程缺陷；本次只是**恰好**由保存 `health.py` 触发 |
| 控制台 30 秒 404 刷屏 | 否：来源为 opencode-cli 的外部探测 |

## 六、处置建议

1. **恢复 reload 必须手工重启**：卡在 `join()` 的父进程无法自行恢复，`Ctrl+C` 也退不掉，只能 kill 12904 与 12040 后重新启动。
2. **重启后确认**：`GET /api/v1/health` 应出现 `"host"`、`"server_ip"`、`"pid"` 三个字段。
3. **降低复发**：改后端代码前后用 `py-spy dump --pid <父进程>` 扫一眼是否停在 `basereload.py:98`；若停住，直接重启而不是反复保存文件。
4. **404 噪音**：与本项目无关，不建议为此在 8000 上补一条裸 `/health` 路由（会破坏"API 只走 /api/v1"的收敛口径）。若要静音，应在 OpenCode 侧改探测地址。
5. **前端已做容错**：服务胶囊与配置胶囊的 Tooltip 行数固定，后端字段缺失时显示 `未上报` / `—`，不依赖 reload 是否生效。

## 七、证据附录

```text
# 1) /health 实际返回（20:49:56）
{"status":"healthy","timestamp":"2026-11-02T20:49:56.777675","version":"1.5.4","db_status":"healthy"}

# 2) 进程树
pid=12904 ppid=1468  start=11/01/2026 20:08:38   python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000
pid=12040 ppid=12904 start=11/01/2026 20:08:39

# 3) 父进程 cwd
CWD = F:\OmniAgentAs-01\backend

# 4) 版本
uvicorn 0.46.0 / watchfiles 1.2.0 / 最新 0.54.0

# 5) mtime 试探（20:49:48 改 mtime，20:49:56 复查）
改动前 worker: 12040
改动后 worker: 12040     ← 未重启
```

---

**编写人**：小欧
**签名**：小欧-2026-11-02 20:59:31
