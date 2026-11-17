# AGENTS.md - OmniAgentAs-desk
### 1.1 头条铁规：代码编辑、文档签名、编辑历史\注释、commit规则，升级tag,修改补充更新文档规矩
**系统命令**：本机必须使用Windows系统命令。杜绝使用Linux命令
**打tag**：1.在version.txt文件头部插入版本汇总升级信息和从上一个tag以来的所有commit的变更信息的说明.2.打tag

**代码编辑禁令**  严禁用代码 脚本来操作代码编辑\替换,否则导致代码编码错误
**代码编辑历史**： 修改代码的修改汇总说明, 位置在代码的头部板块
                  格式: 日期+署名+修改的目和逻辑说明
                  插入: 最新的编辑历史在板块最下边,<严禁中间插入>
**注释+编辑历史信息** 只能技术术语和逻辑信息严禁插入:文档号 章节号, bug/问题序号 评审\会审\裁定等文档序号等,,严禁又臭又长,不明晰 ,过期无法理解的无意义字符
**修改补充更新文档规矩**  保证修改后全文内容通顺,章节分级逻辑合理,1:合理准确的插入修改的位置,2:章节序号应该根据新增删减的内容进行章节 序号标题的修改,3严禁不合理位置的硬插入破环内容的通顺性
**文档签名**：（1）文档名称: +签名+时间； （2）内容签名： +编写/ 更新人 + 签名  （3）编辑型文档， 禁止删历史版本信息。
**提交**:   格式 `<type>:<代码名> <description> - <签名>-<日期>`，types: feat/fix/refactor/perf/test/docs
    严令禁止commit任何测试case代码--不提交不是不可以修改错误的case 必须修改本地代
**严禁以测试代码作为锁死错误系统逻辑的修改借口**  测试用例只用于发现问题，严禁以测试代码为借口去固化错误的系统逻辑或容忍烂代码。


## 1.2 <三堂会审>合规合理关联的 5步规范
**熟读代码全文** 读取最新本地代码 熟读10遍, 复核3遍---三堂会审
**合规审查**  核查代码中的每一处 修改违反了代码10大规范哪些规范?
**合理审查**  挖掘逻辑流程是否最优雅/最佳? 从系统全局流程和逻辑高度, 是不是最差,绕来绕去
**关联审查**  核查相关上上下下,前前后后代码逻辑,哪些是退化的?哪些是很差的逻辑流程.复查的要求,功能只能正确\增强\优化, 杜绝退化
**后端为主**: 前端薄后端厚,前端迎合后端的策略,前端逻辑和参数对应后端设计和修改.

*10大规范**  日常6条 + 重构4条:

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
前端共享函数清单 frontend/FUNCTIONS_FRONT.md
后端公用函数清单`backend/FUNCTIONS.md`
| 规则 | 说明 |
|------|------|
| **先查后建** | 写代码前先查共享函数清单，有则复用，无则新建 |
| **分层存放** | 全局层`app/utils/`Agent层`agent_utils/`、工具层`toolhelper/` |
| **禁止重复** | 相同逻辑禁止重复实现，必须使用已有公用函数 |
| **及时更新** | 新建公用函数后必须添加到FUNCTIONS.md清单 |

## 1.4 拆分\重构代码**规范（必须遵守）
**核心心原则**：能复制就复制，不重写
**拆分大文件/函数时** 最安全的做法是**复制原代码逻辑，只改导入路径，不改业务逻辑**。重写会引入新错误，复制能保证行为不变。

## 1.5 文档的<一致性>审查规范（必须遵守）

**读取**  读取文档全文
**通顺**  全文上下内容逻辑必须按照人类编写理解的内容逻辑通顺,不能跳跃,混乱
**章节**  序号是为内容排列服务的,章节序号必须根据内容的新增\删除\修改进行合理调整,不能硬插


## 2.1 System & Platform

- **OS**: Windows only. Use PowerShell. No Linux/macOS commands.
- **Shell**: PowerShell 7+. Use `Select-String` instead of `grep`.
- **Python**: 3.13 at `E:\Appsw\python31311\`

---

## 2.2 Backend (workdir=`backend/`)

- 开发服务启动、测试与检查命令详见后端手册 `[1]全链路E2E测试手册-小健-2026-05-23.md`
- 提交前必过：ruff 检查（F 类零容忍）
- 开发服务用 watchfiles 方式（`start_watch.bat`），勿用 `uvicorn --reload`（Windows 上会卡死）

---

## 2.3 E2E 全链路测试

- 后端手册 `[1]全链路E2E测试手册-小健-2026-05-23.md`（v2.20）
- 前端手册 `[3]前端Playwright E2E隔离测试实操手册-小欧-2026-11-16.md`

**配置隔离铁律**：任何测试**严禁写 `config/config.yaml`**，一律经 `app/config.py` 的 `get_config_path()` 读写；测试代码只可惰性调 `get_config_path()`，**禁止硬编码配置路径**。

**数据隔离铁律**：数据目录唯一解析点 = `app/db/database.py` 的 `resolve_db_dir()`，认 `OMNIAGENT_DATA_DIR`；在 `get_conn` 内惰性解析，不在导入期冻结；测试要指向任意库走 `db._db_overrides` 覆盖口，**禁止改生产解析逻辑迁就测试**。任何走 `db.get_conn()` 的测试自动"够不到"真库。

**测试的铁律（前后端共用）**：
- 测试目的是**发现问题**，不是跑脚本；严禁看到 FAIL 跳过
- 一律真实后端 + 真实 LLM + 真实工具 + 真实 SQLite，**禁止 Mock**

---

## 2.4 Request Flow&Key Dependencies

详细架构见 `README.md` 二~六章。
技术栈与依赖版本详见 `README.md`。

---

## 2.5 Known Pitfalls

常见坑点与规避详见后端手册 `[1]全链路E2E测试手册-小健-2026-05-23.md`。

---
## 2.6 Code Conventions

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
- 提交前跑 `npm run check:full`（含 typecheck + typecheck:e2e + lint + lint:e2e + format:check）
