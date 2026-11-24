# MediaCrawler 集成方案B-代码集成深度研究

**一句话定位**: 把 MediaCrawler 作为**代码**集成进 OmniAgent。研究结论：**B1 同进程库嵌入不可行**（三重硬障碍），**B2 CLI 子进程封装可行**但登录态无法复用。方案 A（服务集成）仍是推荐路径。

**文档签名**: 商量 2026-11-24
**关联文档**: [54]MediaCrawler开源项目分析报告 / [55]MediaCrawler集成方案A-服务集成深度设计

---

## 一、方案B的两个子形态

| 子形态 | 集成方式 | 可行性 |
|--------|---------|--------|
| **B1 同进程库嵌入** | `import` MediaCrawler 模块，在 OmniAgent 进程内直接实例化爬虫类 | ❌ **不可行**（三重硬障碍） |
| **B2 CLI 子进程封装** | OmniAgent 用 subprocess 启动 `python main.py` 一次性爬取 | ✅ 可行（但登录态不可复用） |

---

## 二、B1 同进程库嵌入：不可行，三重硬障碍

### 障碍1：依赖版本硬冲突（无法同进程共存）

| 依赖 | OmniAgent 要求 | MediaCrawler 要求 | 冲突 |
|------|---------------|-------------------|------|
| httpx | `==0.26.0` | `==0.28.1` | ❌ 硬冲突 |
| pandas | `>=3.0.0` | `==2.2.3` | ❌ 硬冲突 |

`pip install mediacrawler` 进 OmniAgent 环境会**升级 httpx、降级 pandas**，直接破坏 OmniAgent 的 network 层（`http_client_sdk.py` 用 httpx）和 dataanalysis 层（用 pandas）。**同进程 import 必然炸**，这是最根本障碍。

### 障碍2：模块级全局配置污染（运行时改全局变量）

`config/__init__.py` 是 `from .base_config import *`，所有配置是**模块级全局变量**：

```python
# config/base_config.py (已核实)
PLATFORM = "xhs"              # 平台
KEYWORDS = "编程副业,编程兼职"  # 关键词
LOGIN_TYPE = "qrcode"         # 登录方式
SAVE_DATA_OPTION = "jsonl"    # 存储方式
HEADLESS = False              # 无头
CRAWLER_MAX_NOTES_COUNT = 15  # 抓取数量
...
```

爬虫运行时**直接修改这些模块全局变量**（`config.PLATFORM = "dy"` 等）。若同进程嵌入 OmniAgent，爬虫会污染 OmniAgent 进程的全局配置空间，且**无法隔离并发**——两个爬虫任务同时跑会互相覆盖 `PLATFORM`/`KEYWORDS`。

### 障碍3：嵌套事件循环冲突

MediaCrawler 的 `main()` 是 `asyncio.run(main())`；OmniAgent 也是 asyncio 事件循环。**同进程内调用 `asyncio.run()` 会抛 `RuntimeError: asyncio.run() cannot be called from a running event loop`**。除非把 MediaCrawler 的 `main()` 改成 `await` 风格并侵入其代码，否则无法在 OmniAgent 事件循环里直接跑。

### 障碍1~3 结论

B1 需要**同时**解决依赖隔离（需独立 venv 但同进程 import 就失效）、全局配置重构（侵入改 `config/`）、事件循环改写（侵入改 `main.py`/`cmd_arg.py`）——等于**重写 MediaCrawler 的架构**，违背"能复制就复制不重写"原则，且引入大量新错误风险。**判定不可行**。

---

## 三、B2 CLI 子进程封装：可行但登录态不可复用

### 3.1 原理

OmniAgent 用 subprocess 启动 `python main.py --platform xhs ...`，等待进程退出，读取产物文件。**每次调用起一个全新进程**。

### 3.2 实现（复用 OmniAgent 现成的 proc_io.py 零线程安全执行）

```python
# -*- coding: utf-8 -*-
"""MediaCrawler CLI 子进程封装 — 商量 2026-11-24
用 OmniAgent 的 proc_io.run() 零线程安全执行 MediaCrawler 的 main.py。
注意: 每次调用起新进程, 登录态不可复用, 需每次扫码或传 cookie。
"""
import sys
from typing import Any, Dict, Optional
from app.logger import logger
from app.utils.proc_io import run, isolation_kwargs  # 复用零线程子进程安全执行

MEDIA_CRAWLER_DIR = r"E:\source-code\MediaCrawler"
MEDIA_CRAWLER_PYTHON = r"E:\source-code\MediaCrawler\.venv\Scripts\python.exe"  # 独立venv的python

async def media_crawler_cli(platform: str, keywords: str = "",
                            crawler_type: str = "search", specified_ids: str = "",
                            creator_ids: str = "", start_page: int = 1,
                            save_option: str = "jsonl", headless: bool = True,
                            cookies: str = "",
                            max_notes_count: Optional[int] = None) -> Dict[str, Any]:
    """一次性 CLI 爬取(同步阻塞, 需设较长超时)"""
    cmd = [MEDIA_CRAWLER_PYTHON, "main.py",
           "--platform", platform, "--lt", "cookie" if cookies else "qrcode",
           "--type", crawler_type, "--save_data_option", save_option,
           "--get_comment", "true", "--headless", "true" if headless else "false"]
    if keywords:
        cmd += ["--keywords", keywords]
    if specified_ids:
        cmd += ["--specified_id", specified_ids]
    if creator_ids:
        cmd += ["--creator_id", creator_ids]
    if start_page != 1:
        cmd += ["--start", str(start_page)]
    if max_notes_count is not None:
        cmd += ["--crawler_max_notes_count", str(max_notes_count)]
    if cookies:
        cmd += ["--cookies", cookies]

    result = run(cmd, cwd=MEDIA_CRAWLER_DIR, timeout=600, **isolation_kwargs())
    # result.stdout/stderr 含爬取日志; 产物落盘到 MEDIA_CRAWLER_DIR\data\
    return {"exit_code": result.returncode, "stdout_tail": result.stdout[-2000:], "stderr_tail": result.stderr[-2000:]}
```

**关键**: 必须用 MediaCrawler **独立 venv 的 python**（`.venv\Scripts\python.exe`），不能用 OmniAgent 的 python——否则依赖冲突。cwd 必须是 MediaCrawler 项目根。

### 3.3 B2 的登录态问题

- **每次调用起新进程** → 浏览器上下文全新 → 登录态不保留
- 要么每次 `--lt qrcode` 扫码（体验差）
- 要么每次 `--lt cookie --cookies "{cookie串}"`（需先手动抓 cookie 存到 OmniAgent 配置）
- MediaCrawler 的 `SAVE_LOGIN_STATE=True` 会把登录态存到 `{platform}_user_data_dir`，但 **B2 每次新进程读同一 user_data_dir**——理论上可复用，但 `ENABLE_CDP_MODE`/`CDP_CONNECT_EXISTING` 等配置会干扰，实测需验证

### 3.4 B2 优缺点

**优点**:
1. 实现最简单，不引入常驻服务
2. 复用 OmniAgent `proc_io.run()` 零线程安全执行（已解决 Windows 子进程卡死问题）
3. 进程结束后资源全释放，无内存驻留

**缺点**:
1. **每次付进程启动 + 浏览器启动代价**（约 5~15 秒）
2. **登录态难复用**，每次需扫码或手动 cookie
3. 同步阻塞，需长超时（爬取可能数分钟），不适合交互式对话
4. 无法中途 stop/status——一次性进程，无控制面
5. 并发=1（一次一个进程），无法并行多平台

---

## 四、两方案对比矩阵

| 维度 | 方案A 服务集成 | 方案B2 CLI子进程 |
|------|---------------|-----------------|
| 依赖冲突 | ✅ 零（独立venv） | ✅ 零（独立venv python） |
| 代码改动 MediaCrawler | ✅ 零 | ✅ 零 |
| 代码改动 OmniAgent | 3文件（新增2+改1） | 2文件（新增2） |
| 登录态复用 | ✅ 服务常驻，扫码一次 | ❌ 每次扫码/手动cookie |
| 任务控制 | ✅ start/stop/status/logs | ❌ 无控制面 |
| 资源驻留 | 常驻API+按需爬虫进程 | 进程用完即释放 |
| 响应速度 | 快（服务已起） | 慢（每次起进程） |
| 运维点 | +1常驻服务 | 无 |
| 并发能力 | 可扩展多平台排队 | 并发=1 |
| 长任务适配 | ✅ 天然异步 | ❌ 同步阻塞 |
| 复杂度 | 中 | 低 |
| **推荐** | ⭐ **推荐** | 备选 |

## 五、结论与推荐

1. **B1 同进程库嵌入：不可行**——httpx/pandas 依赖硬冲突 + 模块级全局配置污染 + 嵌套事件循环，三重障碍，需重写 MediaCrawler 架构，违背"复制不重写"原则。
2. **B2 CLI 子进程封装：可行但登录态不可复用**——适合一次性、低频、非交互的爬取；不适合需要登录态复用、任务控制、长任务的场景。
3. **方案A 服务集成：推荐**——零依赖冲突、零代码改动 MediaCrawler、登录态可复用、任务控制完整、天然支持长任务，复用 [11] 网关先例。缺点是 +1 常驻服务。
4. **最终建议**: 采用**方案A**（独立 venv + FastAPI 常驻 + OmniAgent 封装 HTTP）。若只需一次性低频爬取且能接受每次扫码，B2 可作轻量备选。

**签名**: 商量 2026-11-24
