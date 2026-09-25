# [70] ConnectionScope 连接池统一所有者实施方案

**文档名**: [70]ConnectionScope连接池统一所有者实施方案-小欧-2026-09-25.md  
**编写人/签名**: 小欧（资深后端开发、全架构设计与分析）  
**创建时间**: 2026-09-25 11:40:25  
**更新时间**: 2026-09-25 12:15:36  
**版本**: v1.1  
**状态**: 设计定稿 + **第三章 13 个文件逐真实 diff 已落笔（基于干净 HEAD `527cfc727` 逐行精读后编写）**；尚未修改任何程序源码  
**适用基线**: `F:\OmniAgentAs-repair` HEAD `527cfc727`（6 个 lease 半成品文件已撤销回 HEAD 的干净基线；此前 8a58edb57 起点见 [69] 文档）  
**关联问题**: 配置热重载期间活动任务仍使用已关闭的共享 `httpx.AsyncClient`（任务零感知 + 不泄漏）  
**决策依据**: [69] 文档 5.4 改判 A——北京老陈 2026-09-25 11:24 拍板，ConnectionScope 定为终局  

---

## 版本历史

| 版本 | 时间 | 签名 | 修改简介 |
|------|------|------|----------|
| v1.0 | 2026-09-25 11:40:25 | 小欧 | 建档：一章问题与目标（复用 [69] 取证与欠账分析）、二章 ConnectionScope 设计（唯一所有者/状态机/计数模型/六环节收口/reset 新语义）、三章占位（diff 待编写，需基于干净 HEAD 通读后做）、四章验证框架、五章实施与回滚；本版只写文档，未改业务源码 |
| v1.1 | 2026-09-25 12:15:36 | 小欧 | ①三章落地：13 个目标文件逐真实 unified diff（3.1 client_sdk lease 落户 → 3.13 agent_runner，依赖序），全部基于 HEAD `527cfc727` 逐行精读编写，`check_doc_diff` 类校验器复核；②二章设计修正（三堂会审 YAGNI 复查）：删 `mark_config_changed`/四态状态机（`close_on_zero` 使零穿越只可能发生在退休后，状态机为冗余抽象）、删 `scope.release_lease`/`scope.resolve_session`（快照 close 直接归还 lease、查询职责留 resolver——SRP）、`__init__` 改持 `ai_service`（一代=一实例一池）、新增 `ensure_pool`/`release_owner`；③registry"ai_service"字段全仓零消费核证后删除；④runner 关闭判据改无条件（resolver 恒返回任务私有快照，`_is_snapshot` 死判据消亡）；⑤五章步骤改依赖序（client_sdk→base_service→scope→工厂/停机→resolver→registry→接线→测试），每步 `py_compile` 自检、全步后 `compileall` |

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

### 2.2 模块与核心 API（v1.1 定稿签名；实现代码在第三章 diff 落定）

- 新增模块：`backend/app/services/lifecycle/connection_scope.py`
- 吸收素材：`_SharedClientPool`/`SharedClientLease` 引用计数语义（素材文件，见 1.4；归零关闭 `close_on_zero`、释放幂等、池级线程锁；**v1.1 核查确认：素材无状态机概念，`release()` 归零即返回 True 触发 `pool.close()`——四态状态机系 v1.0 臆造冗余，已删）

```python
class ConnectionScope:
    """共享连接池唯一所有者（一代配置 = 一个 scope）。"""

    def __init__(self, ai_service: BaseAIService) -> None:
        """持本代单例（池未建）；owner lease 于 ensure_pool 建立。"""

    def ensure_pool(self) -> None:
        """建池 + 所有权移交（幂等）：单例 LLMClient.relinquish_ownership 后
        保留使用引用不关池；SharedClientLease(client) 计数起点=1（2.4 模型）。"""

    def acquire_lease(self) -> SharedClientLease:
        """任务/快照借用本代池（ref+1）；已退休/未初始化抛 RuntimeError
        （防新任务混入旧代），池已归零由素材 acquire 自身拦截。"""

    def release_owner(self) -> None:
        """换代/停机归还 owner 引用（幂等，ref-1）；归零自动 aclose。
        事件循环内 create_task（强引用防 GC 取消），无运行循环参照
        close_instance_sync 用 asyncio.run。**reset() 新语义即此调用**。"""

    async def drain(self, timeout: float = 30.0) -> None:
        """停机收口：等本代池 lease 全部归零关闭（0.1s 轮询、带超时）；
        超时记 warning 放行（不阻塞进程退出）。归零关闭由 release 触发，本函数只等。"""

    @property
    def ref_count(self) -> int: ...     # 可观测/测试断言（owner 未归还时含 1）
    @property
    def is_released(self) -> bool: ...  # 退休态（owner 已归还）
```

**v1.1 删项（YAGNI 三堂会审结论）**：
- ~~`mark_config_changed()`~~ 删——owner 引用随换代立即归还后，`ref_count==0` 只可能发生在退休后，`close_on_zero` 天然实现"换代才可能关、活动任务撑住不关"，无状态可标；
- ~~`release_lease(lease)`~~ 删——快照 `close()` 即 `lease.release()`（3.2/3.13），scope 不做归还中介（KISS-DIRECT，直线不绕行）；
- ~~`resolve_session(...)`~~ 删——会话覆盖查询（DB/provider 配置）是业务查询职责，留 resolver（SRP）；resolver 改签名 `(scope, session_id)`，**资源只从 `scope.acquire_lease()` 出**，反射消亡；
- ~~`state` 四态属性~~ 删——状态可由 `is_released` + 池 `ref_count` 直接观测，不引入状态机枚举。

- `reset()`（lifecycle）新语义：工厂 `_retire_scope()`（= `scope.release_owner()` 归还 owner）+ `_instance=None`（下次 `get_service` 创建**新代 scope**），**绝不再"关旧池"**。
- `close_instance`/`close_instance_sync` 保留：关闭旧**实例**（其池所有权已 relinquish，故关闭动作天然不碰共享池）。

### 2.3 生命周期模型（v1.1 修订：无状态机，纯引用计数）

v1.0 曾画四态状态机（ACTIVE→CONFIG_CHANGED→DRAINED→CLOSED），v1.1 三堂会审证伪删除——**零穿越只可能发生在退休后**，一切状态都可由两个事实直接观测：

```
在役:  owner_lease 非 None（ref_count ≥ 1，恒 ≥1 ⇒ 池永不关）
退休:  release_owner() 后 owner_lease=None（is_released=True）
        ├─ 活动任务 lease >0 → ref_count>0 → 池存活 → 最后一个 release 归零 → aclose
        └─ 无活动任务        → ref_count=0 → 归零 → aclose（创建释放协程内完成）
停机:  drain() 只是"等上述过程结束"（0.1s 轮询 + 超时放行），不改变任何状态
非法迁移: 退休后再 acquire → ConnectionScope 抛 RuntimeError（防混代）
          池已归零后再 acquire → 素材 SharedClientLease.acquire 抛 RuntimeError（双重防线）
aclose 失败: 素材 pool.close 内 try/except + logger.warning 留痕（[69] 2.3 retry_close 语义
          经素材 close_on_zero 单次关闭 + 日志可查承接；不引入二次重试复杂度——YAGNI）
```

- 素材既有语义原样继承：`_closing` 标志、释放幂等（`lease._released`）、池级 `threading.Lock` 线程安全。

### 2.4 所有权与计数模型

| 角色 | 引用计数 | 说明 |
|------|---------|------|
| scope 自身（owner） | +1（`ensure_pool` 起点） | 随 `release_owner()`（换代/停机）归还，归还后不再保池 |
| 每个活动任务的快照 | `scope.acquire_lease()` +1 / 任务 `close()` → `lease.release()` -1 | release 幂等（重复归还不计）；**v1.1：经 base_service.close 直线归还，不经 scope 中介** |
| 同 provider 多快照共享同一池 | 各自 acquire 独立 lease 实例 | 绝不共享同一 lease 实例（[69] 设计红线，素材 `_from_pool` 天然满足） |
| 跨 provider 快照 | 不挂 scope（acquire 的 lease finally 归还） | 独占新池，归属该快照自身，随快照 close 关闭 |
| 归零 | `ref_count==0` → `aclose`（`close_on_zero`） | owner 已随换代归还 ⇒ **零穿越只可能在退休后** = "任务零感知 + 不泄漏"（v1.1 删"且 CONFIG_CHANGED/DRAINED"条件） |

### 2.5 六环节收口映射（[69] 5.3 表的具体化）

| 环节 | 现状（HEAD）落点 | 重组后 | 收口变化 |
|------|-----------------|--------|---------|
| 创建 | `service.get_service` 锁内建单例 + C1 惰性建池后**裸暴露 `_shared_client` 属性** | 锁内 `_attach_scope`：`ConnectionScope(instance)` + `ensure_pool()`（建池 + `relinquish_ownership` 移交） | 建池、所有权移交、scope 诞生同一处；裸属性暴露消亡 |
| 决议 | resolver 用 `getattr(ai_service, "_shared_client")` 反射摸池 | `resolve_session_client(scope, session_id)`：进门 `scope.acquire_lease()`，快照接走、未转移 finally 归还 | 反射消亡；**lease 只从 scope 发**；查询职责（DB/provider 配置）留 resolver（v1.1 修正：不迁 scope，SRP） |
| 注册 | `task_registry.register_task` 存 `"ai_service"` 字段（且**全仓零消费点**，v1.1 核证） | 删参数删字段，只存任务身份/状态/inbox | registry 不 import 任何资源类型；死字段直接删除（YAGNI） |
| 使用 | orchestrator 反射/`_shared_client` 属性 + runner 摸 `_is_snapshot` 私有标记 | 快照构造注入 `scope.acquire_lease()`；runner 无条件 `close()`（快照恒私有） | `_is_snapshot` 消亡；`_owns_client` 收敛回 LLMClient 类内（relinquish/公开 `client` property），跨层摸私有清零 |
| 取消 | task_runtime 经 `running_tasks["agent"].llm_client` 取消在飞 HTTP | **不变**（v1.1 核证：取消链本就不经 registry 的 ai_service 字段，零改动） | 取消只作用于任务与 HTTP response；池引用随任务结束 close 归还 |
| 停机 | `main.shutdown_event` 调裸 `reset()` | `await lifecycle.shutdown()` = `reset()`（换代归还）+ `scope.drain(30)` | 关闭等待收编进 scope.drain 单点 |

### 2.6 reset 换代模型（配置代 generation）

1. 配置变更触发 `reload_ai_config → reset()`；
2. `reset()` = `reset_instance()` 锁内 `_retire_scope()`（即 `scope.release_owner()` **归还 owner 引用**，幂等；v1.1 修正：不是"标记"而是"归还"——归还后零穿越才可能发生）+ 工厂 `_instance=None`；
3. **新请求** → `get_service()` → 锁内 `_attach_scope` 创建**新一代 scope**（新池、新配置参数）→ 新任务用新池；
4. **旧任务**继续持有旧 scope 的 lease → 请求照常 → 全部结束 release 归零 → 旧池在最后一个 release 协程内自动 `aclose()`；
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

检查：`_owns_client`/`_is_snapshot`/`_shared_client` 反射在生产代码无引用；resolver 无 `getattr(type(...))`/`__dict__`；registry 不 import 资源类型、不存 `ai_service` 字段；`reset()` 无 `close` 调用（只经 `_retire_scope` 归还 owner）；全仓无 `mark_config_changed`/`scope.resolve_session`/`scope.release_lease`/`state` 状态机残留。

### 4.2 定向单元测试（从 [69] 3.10 六个测试文件移植，断言按 scope API 改造）

- 计数正确性：`acquire_lease`/快照 `close`→release/归零/幂等 release/`ref_count` 观测；
- 换代：`reset()` 后旧 scope `is_released=True` 且旧池存活（活动任务撑住）、新 scope 生效、旧任务全结束后旧池归零关闭；
- 决议：`resolve_session_client(scope, ...)` 全路径（覆盖/无覆盖/配置失败/DB 异常）guard 不泄漏；同 provider 多快照互不归还（`_from_pool` 独立 lease）；跨 provider finally 归还（含 race 用例）；
- 非法迁移：退休 scope `acquire_lease` 抛 RuntimeError、素材池归零后 acquire 抛 RuntimeError；
- registry：不含 `ai_service`/`llm_client`/`snapshot` 资源句柄字段、取消只作用于任务；
- 停机：`drain()` 超时放行、归零后 `is_released` 恒 True。

### 4.3 场景与 E2E（移植 [69] 4.3~4.5 场景表）

- 同/异 Provider 双任务 + reload、任务取消并发 reload、drain 停机等；
- 真实 reload E2E：流式任务运行中改配置 → 任务不中断 + 新请求新配置 + 旧池归零关闭（观测 `ref_count` 日志）。

### 4.4 验收基准（移植 [69] 4.7，全部满足才允许提交）

任务零感知、旧池归零必关、关闭失败有日志可重试、无裸 client 入口、无反射无私有标记、registry 无资源、真实 E2E 通过。

---

## 五、实施步骤与回滚

**步骤**（v1.1 改为依赖序，8 步；每步末 `python -m py_compile <本步文件>` 自检，全步后 4.1 `compileall`）：
1. **3.1 client_sdk**：`SharedClientLease`/`_SharedClientPool` 落户 + `relinquish_ownership()` + `client` property；
2. **3.2 base_service**：`ensure_client_pool()`（建池+移交+返回 client）、`_shared_client` 收编、snapshot 构造接 lease、`close()` 三分支、reset_sdk 改走 lease；
3. **3.3 `llm/__init__.py`**：导出 `SharedClientLease`（resolver/type 提示用）；
4. **3.4 connection_scope.py**：新增（依赖 1~3 的 API）；
5. **3.5~3.9 工厂与停机**：service（`_attach_scope`/`_retire_scope`/`get_scope`/set_instance 改造）→ lifecycle.py（`shutdown()`）→ `lifecycle/__init__` → `services/__init__` → main（`shutdown_event`）；
6. **3.10 resolver**：`resolve_session_client(scope, ...)` 改签名 + acquire/transferred/finally；
7. **3.11~3.13 接线**：task_registry 删 ai_service → orchestrator（`get_scope`/注册参数/resolve 传参）→ agent_runner（无条件 close）；
8. **测试移植**（4.2 六文件改造 + 4.3 场景）+ 全量 4.1 验证。

**回滚**：本方案实施全部为新 commit；若翻盘（[69] 5.4 省可证伪），`git revert` 实施序列即可；摘资产三重备份（素材/patch/stash）在此之前始终保留。

**文档签名**: 小欧  
**更新时间**: 2026-09-25 12:15:36
