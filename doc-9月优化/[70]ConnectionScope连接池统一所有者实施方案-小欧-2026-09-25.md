# [70] ConnectionScope 连接池统一所有者实施方案

**文档名**: [70]ConnectionScope连接池统一所有者实施方案-小欧-2026-09-25.md  
**编写人/签名**: 小欧（资深后端开发、全架构设计与分析）  
**创建时间**: 2026-09-25 11:40:25  
**更新时间**: 2026-09-25 11:40:25  
**版本**: v1.0  
**状态**: 骨架与设计已立（第一~二章、四~五章框架）；**第三章逐文件 diff 待编写**；尚未修改程序代码  
**适用基线**: `F:\OmniAgentAs-repair` HEAD `527cfc727`（6 个 lease 半成品文件已撤销回 HEAD 的干净基线；此前 8a58edb57 起点见 [69] 文档）  
**关联问题**: 配置热重载期间活动任务仍使用已关闭的共享 `httpx.AsyncClient`（任务零感知 + 不泄漏）  
**决策依据**: [69] 文档 5.4 改判 A——北京老陈 2026-09-25 11:24 拍板，ConnectionScope 定为终局  

---

## 版本历史

| 版本 | 时间 | 签名 | 修改简介 |
|------|------|------|----------|
| v1.0 | 2026-09-25 11:40:25 | 小欧 | 建档：一章问题与目标（复用 [69] 取证与欠账分析）、二章 ConnectionScope 设计（唯一所有者/状态机/计数模型/六环节收口/reset 新语义）、三章占位（diff 待编写，需基于干净 HEAD 通读后做）、四章验证框架、五章实施与回滚；本版只写文档，未改业务源码 |

---

## 一、问题与目标

### 1.1 关联问题（摘自 [69] 1.1~1.3，取证素材复用）

- 用户可见症状：配置热重载（设置页保存/手工改 config.yaml）期间，正在流式输出的后台任务下一拍 LLM 请求报 `Cannot send a request, as the client has been closed`，任务断流失败。
- 根因：`reload_ai_config → reset()` 无条件关闭全局 `BaseAIService` 单例及其共享 httpx 连接池，而活动任务仍持有该池；"新配置生效"与"活动任务存活"两个目标通过"关旧池"硬切换，必然误伤。
- 补充：`config_helpers._update_model_ref` 曾在**写盘前**错位 `reset()`（校验失败也误关）——该修复已单独摘出入库（见 1.4 素材），HEAD 已含两处正规 `reset()` 触发点。
- 磁盘↔内存参数表一层已由 `get_config()` mtime 对账保证（[69] 5.2，2026-09-02），本方案不涉及。

### 1.2 历史欠账与演进（摘要自 [69] 5.1/5.2，全文见彼处）

三条欠账：
1. **私有字段外泄**：resolver 用 `getattr(type(...))`/`__dict__` 反射摸 `_shared_client`，`_owns_client`/`_is_snapshot` 私有标记跨层传播；
2. **资源所有权无单一归属**：创建/决议/注册/使用/关闭/停机 6 段各管一节，无一处能回答"池现在归谁、何时能关"；
3. **全局开关表达细粒度语义**：`lifecycle.reset()` 一按全按，必然误伤（[69] 病灶制度根源）。

演进：2026-06 单例 → 08-22 reset_sdk → 08-29 快照 → 09-02 mtime 对账 → 09-20 C1 共享池 → 09-25 lease 半成品（已撤销，素材保留）→ 09-25 定案重组为终局。

### 1.3 目标与非目标

**目标**：
1. 任务零感知：配置热重载不打断任何活动任务的 LLM 请求（引用计数保旧池存活至自然结束）；
2. 不泄漏：旧池在最后一个 lease 释放后必然 `aclose()`，关闭失败可重试、有日志；
3. **单一所有者**：`ConnectionScope` 成为共享连接池的唯一所有者，六环节全部经它收口（消除欠账①②）；
4. **registry 去资源化**：`task_registry` 不再持有/管理资源句柄，只存任务身份；
5. reset 新语义：由"关实例关池"改为"标记换代"（消除欠账③）。

**非目标**：
- 不动 mtime 对账与 `reload_ai_config` 触发链（已正确）；
- 不改前端、不引入新第三方依赖；
- 不追求 6 环节物理合并到单文件——收的是**所有权与调用门面**，本质分布（工厂在 service、停机在 main）保留。

### 1.4 素材与基线（摘资产执行记录，[69] 5.4 路径步骤①②已完成）

| 素材 | 位置/入库 | 用途 |
|------|----------|------|
| lease 核心两段类（`_SharedClientPool`+`SharedClientLease`，~90 行，原样） | `doc-9月优化/[70]素材-lease核心-小欧-2026-09-25.py`（已随 c9122963f 入库） | 本方案 2.2 引用计数语义吸收（不重写） |
| 6 文件全量改动 patch（30,650B） | `backup-6files未提交改动-2026-09-25.patch`（已随 527cfc727 入库） | 历史追溯/翻盘兜底 |
| config_helpers 独立修复 patch（656B） | `backup-config_helpers修复-2026-09-25.patch`（已随 527cfc727 入库） | 该修复的永久存档（HEAD 已含同内容） |
| 6 文件 stash | `stash@{0}`（本地保留至本方案定案） | 第四重兜底 |
| [69] 文档可复用块 | [69] 1.x 问题取证、2.x 状态机、3.10 测试设计、4.x 验收标准 | 直接搬入本方案三/四章 |

**基线状态验证**（2026-09-25 摘资产后实测）：`client_sdk.py` 无 `SharedClientLease`（0 处）、`_owns_client = shared_client is None` 回 HEAD；`base_service.py` 含 `def reset_sdk`；`config_helpers.py` 含 2 处 `reset()`；`git status` 干净。

---

## 二、ConnectionScope 设计

### 2.1 定位

`ConnectionScope` = 共享 httpx 连接池的**唯一所有者**：池由它创建、计数由它维护、变更由它标记、归零由它关闭、停机由它 drain。任何其他模块（resolver/registry/runner/orchestrator）**只经公开门面借用，不摸池内部**。

### 2.2 模块与核心 API（签名级设计；实现细节在第三章 diff 落定）

- 新增模块：`backend/app/services/lifecycle/connection_scope.py`
- 吸收素材：`_SharedClientPool`/`SharedClientLease` 引用计数语义（素材文件，见 1.4；归零关闭、释放幂等、线程锁）

```python
class ConnectionScope:
    """共享连接池唯一所有者。状态机见 2.3。"""

    def __init__(self, client: httpx.AsyncClient) -> None:
        """持有池的 owner 引用（计数起点=1）；state=ACTIVE。"""

    def acquire_lease(self) -> SharedClientLease:
        """活动任务/快照借用池；state=CLOSED 时抛 RuntimeError（防用已关池）。"""

    async def release_lease(self, lease: SharedClientLease) -> None:
        """归还引用；归零且已标记变更/停机 → 触发关闭。"""

    def mark_config_changed(self) -> None:
        """reset() 新语义：只标记 state=CONFIG_CHANGED，绝不主动关池。"""

    async def resolve_session(self, ai_service, session_id):
        """会话决议收口（原 resolver 反射逻辑迁入此处，经 lease 构造快照）。"""

    async def drain(self, timeout: float = 30.0) -> None:
        """停机收口：state=DRAINED，等所有 lease 归零（带超时）后关闭。"""

    @property
    def state(self) -> str: ...       # 见 2.3 四态
    @property
    def ref_count(self) -> int: ...   # 可观测性/测试断言用
```

- `reset()`（lifecycle）新语义：`mark_config_changed()` + 工厂置 `_instance=None`（下次 `get_service` 创建**新代 scope**），**不再调用 close**。
- `close_instance`/`close_instance_sync` 保留给"独占池实例"（非 scope 管辖的临时实例）。

### 2.3 状态机（复用 [69] 2.2 精神，四态收敛）

```
ACTIVE ──mark_config_changed()──▶ CONFIG_CHANGED ──ref_count==0──▶ CLOSED
   │                                    ▲
   └──drain()──▶ DRAINED ──────────────┘
                     （ref_count==0 → CLOSED；drain 带超时）
CLOSED: 执行 aclose() 一次；失败记录 warning + 状态回退可重试（吸收 [69] 2.2/2.3 retry_close 语义）
```

- 非法迁移（CLOSED 后 acquire）→ `RuntimeError("共享 httpx 客户端已关闭")`（素材既有语义）。

### 2.4 所有权与计数模型

| 角色 | 引用计数 | 说明 |
|------|---------|------|
| scope 自身（owner） | +1（起点） | 生命周期=scope 本身，不对外释放 |
| 每个活动任务的快照 | acquire +1 / release -1 | 任务 finally 必 release（幂等，重复 release 不计） |
| 同 provider 多快照共享同一池 | 各自 acquire | 绝不共享同一 lease 实例（[69] 设计红线） |
| 跨 provider 快照 | 不挂 scope | 独占新池，归属该快照自身，随快照 close 关闭 |
| 归零 | ref_count==0 且（CONFIG_CHANGED 或 DRAINED）→ CLOSED | 只标记不关、归零才关 = "任务零感知 + 不泄漏" |

### 2.5 六环节收口映射（[69] 5.3 表的具体化）

| 环节 | 现状（HEAD）落点 | 重组后 | 收口变化 |
|------|-----------------|--------|---------|
| 创建 | `service.get_service` 锁内建单例+惰性建池 | 锁内 `ConnectionScope(client)` 创建 | 建池与 scope 诞生同一处 |
| 决议 | resolver 反射摸 `_shared_client` | `scope.resolve_session(...)` | 反射消失，lease 由 scope 发 |
| 注册 | task_registry 存 llm_client/snapshot 并管理 | 只存任务身份（task_id/状态），**资源句柄只在 scope** | registry 不 import 资源类型 |
| 使用 | orchestrator/runner 直接持 snapshot+私有标记 | 快照构造注入 `scope.acquire_lease()` | `_owns_client`/`_is_snapshot` 消亡 |
| 取消 | task_runtime 打 registry 里的对象 | 取消只作用于任务与 HTTP response，池引用随任务结束 release | 取消不再关心池 |
| 停机 | lifecycle `_close_tasks` + main 散点 | `await scope.drain()` 单点 | 关闭任务集合收编进 scope |

### 2.6 reset 换代模型（配置代 generation）

1. 配置变更触发 `reload_ai_config → reset()`；
2. `reset()` = 旧 scope `mark_config_changed()`（标记，不关）+ 工厂 `_instance=None`；
3. **新请求** → `get_service()` → 创建**新一代 scope**（新池、新配置参数）→ 任务用新池；
4. **旧任务**继续持有旧 scope 的 lease → 请求照常 → 全部结束 release 归零 → 旧 scope 自动 `aclose()`；
5. 结果：新配置即时生效（新请求即新代），旧任务零感知，旧池不泄漏。

---

## 三、逐文件实施 diff（待编写）

**状态**：待编写。编写前置（不可跳）：
1. 基于干净 HEAD `527cfc727` 逐文件通读全部目标源码（client_sdk/base_service/resolver/service/lifecycle/task_registry/task_runtime/stream_orchestrator/agent_runner/main/llm `__init__`）；
2. 按 2.5 映射逐文件出真实 unified diff（含新增 `connection_scope.py` 全文）；
3. diff 对 HEAD 基线过 `check_doc_diff` 类校验（真实、非伪代码、禁 `...`）。

目标文件清单沿用 [69] 1.4（11 个生产文件 + 新增 connection_scope.py + 6 个测试文件同步）。

---

## 四、验证测试（框架；用例从 [69] 3.10/4.x 移植改造）

### 4.1 静态验证

```powershell
python -m compileall -q app
```

检查：`_owns_client`/`_is_snapshot`/`_shared_client` 反射在生产代码无引用；resolver 无 `getattr(type(...))`/`__dict__`；registry 不 import 资源类型；`reset()` 无 `close` 调用（只标记）。

### 4.2 定向单元测试（从 [69] 3.10 六个测试文件移植，断言按 scope API 改造）

- 计数正确性：acquire/release/归零/幂等 release；
- 换代：`mark_config_changed` 后旧 scope 不关、新 scope 生效、归零后旧池关闭；
- 决议：`resolve_session` 全路径（覆盖/无覆盖/配置失败/DB 异常）guard 不泄漏；
- 状态机：CLOSED 后 acquire 抛错、close 失败可重试；
- registry：不含资源句柄字段、取消只作用于任务。

### 4.3 场景与 E2E（移植 [69] 4.3~4.5 场景表）

- 同/异 Provider 双任务 + reload、任务取消并发 reload、drain 停机等；
- 真实 reload E2E：流式任务运行中改配置 → 任务不中断 + 新请求新配置 + 旧池归零关闭（观测 `ref_count` 日志）。

### 4.4 验收基准（移植 [69] 4.7，全部满足才允许提交）

任务零感知、旧池归零必关、关闭失败有日志可重试、无裸 client 入口、无反射无私有标记、registry 无资源、真实 E2E 通过。

---

## 五、实施步骤与回滚

**步骤**（每步独立可验证）：
1. 新增 `connection_scope.py`（吸收素材核心 + 2.2 API + 2.3 状态机）+ 单测；
2. 工厂与 reset 换代（service/lifecycle/main）；
3. resolver 决议收口；
4. snapshot/lease 注入（base_service/client_sdk）；
5. registry 去资源化 + 取消链（task_registry/task_runtime）；
6. orchestrator/runner 接线；
7. 测试移植与全量验证（4.2→4.3）。

**回滚**：本方案实施全部为新 commit；若翻盘（[69] 5.4 省可证伪），`git revert` 实施序列即可；摘资产三重备份（素材/patch/stash）在此之前始终保留。

**文档签名**: 小欧  
**更新时间**: 2026-09-25 11:40:25
