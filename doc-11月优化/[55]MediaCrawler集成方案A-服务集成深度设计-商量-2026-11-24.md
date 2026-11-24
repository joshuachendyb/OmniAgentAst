# MediaCrawler 集成方案A-服务集成深度设计

**一句话定位**: 把 MediaCrawler 作为**独立常驻服务**（独立 venv + FastAPI）运行，OmniAgent 通过新增 `media_crawler` 工具封装 HTTP 调用该服务。零依赖冲突、零代码改动 MediaCrawler。

**文档签名**: 商量 2026-11-24
**关联文档**: [54]MediaCrawler开源项目分析报告 / [11]第三方CLI模型接入网关技术方案（端口与进程生命周期先例）

---

## 一、方案A总体架构

```
┌───────────────────────── OmniAgent 进程 (8100) ─────────────────────────┐
│  用户对话 → LLM → media_crawler 工具(HTTP封装)                          │
│                    │                                                    │
│                    │  httpx POST/GET (localhost:8080)                   │
│                    ▼                                                    │
│  tools/media/media_crawler.py   ← 新增封装工具                          │
│  tools/media/media_schema.py    ← 新增请求/响应模型                     │
│  tools/media/media_register.py  ← 注册到 ToolCategory.MEDIA             │
└─────────────────────────────────────────────────────────────────────────┘
                    │ HTTP (127.0.0.1:8080)
                    ▼
┌─────────────── MediaCrawler 独立进程 (独立 venv) ───────────────┐
│  uvicorn api.main:app --port 8080  (常驻)                      │
│    │                                                           │
│    ├── POST /crawler/start  → crawler_manager.start()          │
│    ├── POST /crawler/stop   → crawler_manager.stop()           │
│    ├── GET  /crawler/status → crawler_manager.get_status()     │
│    └── GET  /crawler/logs   → crawler_manager.logs             │
│          │                                                     │
│          ▼  subprocess.Popen("uv run python main.py ...")      │
│    爬虫子进程 (Playwright 浏览器, 独立于 API 进程)               │
│          │                                                     │
│          ▼                                                     │
│    数据落盘 → 爬取结果文件 (JSONL/JSON/CSV/SQLite...)          │
└────────────────────────────────────────────────────────────────┘
```

**关键点**: 爬虫实际运行在 **API 进程的子进程**里（`crawler_manager.py` 用 `subprocess.Popen("uv run python main.py ...")`），所以 MediaCrawler 的 FastAPI 只是"控制面"，真正的爬取在独立子进程。这天然实现了三层隔离：OmniAgent 进程 / MediaCrawler API 进程 / 爬虫子进程。

---

## 二、MediaCrawler API 接口总表（已核实源码）

来源: `E:\source-code\MediaCrawler\api\routers\crawler.py` + `api\schemas\crawler.py`

### 2.1 端点总表

| 方法 | 路径 | 请求体 | 响应 | 说明 |
|------|------|--------|------|------|
| POST | `/crawler/start` | `CrawlerStartRequest` | `{status, message}` | 启动爬虫任务；已运行返回 400 |
| POST | `/crawler/stop` | 无 | `{status, message}` | 停止爬虫任务；未运行返回 400 |
| GET | `/crawler/status` | 无 | `CrawlerStatusResponse` | 查询状态 idle/running/stopping/error |
| GET | `/crawler/logs?limit=100` | 无 | `{logs: [LogEntry]}` | 最近日志（保留 500 条） |

### 2.2 CrawlerStartRequest 请求字段（方案A封装需透传）

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| platform | enum | 必填 | xhs/dy/ks/bili/wb/tieba/zhihu |
| login_type | enum | qrcode | qrcode/phone/cookie |
| crawler_type | enum | search | search/detail/creator |
| keywords | str | "" | 搜索关键词（search 模式） |
| specified_ids | str | "" | 笔记/视频ID列表（detail 模式，逗号分隔） |
| creator_ids | str | "" | 创作者ID列表（creator 模式，逗号分隔） |
| start_page | int | 1 | 起始页 |
| enable_comments | bool | True | 是否抓评论 |
| enable_sub_comments | bool | False | 是否抓二级评论 |
| enable_media | bool | False | 是否抓媒体 |
| save_option | enum | jsonl | csv/db/json/jsonl/sqlite/mongodb/excel |
| cookies | str | "" | cookie 登录态 |
| headless | bool | False | 无头模式 |
| max_notes_count | int | None | 最大笔记数 (1~10000) |
| max_comments_count | int | None | 最大评论数/单笔记 (1~10000) |

### 2.3 请求→命令行 参数映射（`_build_command` 已核实）

```
uv run python main.py
  --platform {platform} --lt {login_type} --type {crawler_type}
  --save_data_option {save_option}
  [--keywords {keywords}]        # 仅 search 且有 keywords
  [--specified_id {specified_ids}]  # 仅 detail 且有 specified_ids
  [--creator_id {creator_ids}]   # 仅 creator 且有 creator_ids
  [--start {start_page}]         # 仅 start_page != 1
  --get_comment {true/false}
  --get_sub_comment {true/false}
  --get_media {true/false}
  [--crawler_max_notes_count {max_notes_count}]
  [--max_comments_count_singlenotes {max_comments_count}]
  [--cookies {cookies}]
  --headless {true/false}
```

**注意**: `_build_command` 用 `uv run python main.py`——意味着 MediaCrawler 的 venv 必须用 **uv 管理**（有 `uv.lock`），且 API 进程的 cwd 必须是项目根 `E:\source-code\MediaCrawler`。

---

## 三、MediaCrawler 服务部署步骤（独立 venv）

```powershell
# 1. 进入项目根
cd E:\source-code\MediaCrawler

# 2. 用 uv 创建独立 venv 并安装依赖（uv.lock 已锁定版本）
uv sync

# 3. 安装 Playwright 浏览器（爬虫核心引擎）
uv run playwright install chromium

# 4. 配置 .env（从 .env.example 复制，按需改）
Copy-Item .env.example .env

# 5. 启动 API 服务（常驻，独立进程）
uv run uvicorn api.main:app --host 127.0.0.1 --port 8080
```

**端口规划**（参考 [11] 的端口事实）: MediaCrawler API 用 **8080**，避开 OmniAgent 的 8100 / 8000 开发 / 8500 打包 / 9000 E2E。若 8080 被占，可在封装工具里配置 `MEDIA_CRAWLER_BASE_URL` 环境变量改端口。

**启动方式**: 参考 [11] 的 **M1 自管**（脚本/快捷方式/计划任务启动），不采用宿主托管——避免 OmniAgent 启动链被 MediaCrawler 启动失败拖挂。

---

## 四、OmniAgent 侧封装设计（新增3个文件）

### 4.1 `backend/app/tools/media/media_crawler.py`（新增，工具实现）

封装 HTTP 调用 MediaCrawler API，复用现有 `http_client_sdk.py` 的 httpx 客户端。

```python
# -*- coding: utf-8 -*-
"""MediaCrawler 服务集成工具 — 商量 2026-11-24
封装 HTTP 调用独立 MediaCrawler FastAPI 服务(127.0.0.1:8080)。
零依赖冲突: MediaCrawler 在独立 venv, 本文件只用 httpx(OmniAgent 已有)。
"""
from typing import Any, Dict, Optional
import httpx
from app.logger import logger
from app.tools.network.http_client_sdk import check_network  # 复用连通性检查

BASE_URL = "http://127.0.0.1:8080"  # 可用环境变量 MEDIA_CRAWLER_BASE_URL 覆盖
TIMEOUT = 30.0

async def media_crawler_start(platform: str, crawler_type: str = "search",
                              keywords: str = "", specified_ids: str = "",
                              creator_ids: str = "", start_page: int = 1,
                              enable_comments: bool = True,
                              enable_sub_comments: bool = False,
                              enable_media: bool = False,
                              save_option: str = "jsonl",
                              login_type: str = "qrcode",
                              cookies: str = "", headless: bool = False,
                              max_notes_count: Optional[int] = None,
                              max_comments_count: Optional[int] = None) -> Dict[str, Any]:
    """启动 MediaCrawler 爬虫任务(异步, 立即返回, 结果落盘到 MediaCrawler 数据目录)"""
    payload = {
        "platform": platform, "crawler_type": crawler_type,
        "login_type": login_type, "keywords": keywords,
        "specified_ids": specified_ids, "creator_ids": creator_ids,
        "start_page": start_page, "enable_comments": enable_comments,
        "enable_sub_comments": enable_sub_comments, "enable_media": enable_media,
        "save_option": save_option, "cookies": cookies, "headless": headless,
        "max_notes_count": max_notes_count, "max_comments_count": max_comments_count,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/crawler/start", json=payload)
        resp.raise_for_status()
        return resp.json()

async def media_crawler_stop() -> Dict[str, Any]:
    """停止 MediaCrawler 爬虫任务"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(f"{BASE_URL}/crawler/stop")
        resp.raise_for_status()
        return resp.json()

async def media_crawler_status() -> Dict[str, Any]:
    """查询 MediaCrawler 爬虫状态"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/crawler/status")
        resp.raise_for_status()
        return resp.json()

async def media_crawler_logs(limit: int = 100) -> Dict[str, Any]:
    """查询 MediaCrawler 最近日志"""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get(f"{BASE_URL}/crawler/logs", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()
```

### 4.2 `backend/app/tools/media/media_schema.py`（新增，输入模型）

参考现有 `GenerateImageInput` 风格，用 pydantic 定义 `MediaCrawlerStartInput` 等，供 `media_register.py` 的 `input_model` 使用。

### 4.3 `backend/app/tools/media/media_register.py`（修改，注册）

在现有 `MEDIA_TOOL_DESCRIPTIONS` / `MEDIA_INPUT_MODELS` / `MEDIA_TOOL_EXAMPLES` 三个 dict 里追加 `media_crawler_start` / `media_crawler_stop` / `media_crawler_status` / `media_crawler_logs` 四个工具，`_register_media_tools()` 的 `tool_methods` 里追加。

### 4.4 工具分类

`ToolCategory.MEDIA`（已有），无需新增分类。

---

## 五、调用链时序（方案A）

```
用户: "爬取小红书'护肤'前10篇笔记"
 → LLM 生成 tool_calls: media_crawler_start(platform=xhs, keywords=护肤, max_notes_count=10)
 → OmniAgent 工具调度器 → media_crawler.py 的 media_crawler_start()
 → httpx POST http://127.0.0.1:8080/crawler/start  (body=CrawlerStartRequest)
 → MediaCrawler API → crawler_manager.start() → subprocess.Popen("uv run python main.py --platform xhs --type search --keywords 护肤 --crawler_max_notes_count 10 ...")
 → 爬虫子进程启动 Playwright 浏览器 → 扫码/登录 → 爬取 → 落盘 JSONL
 → 返回 {status: ok, message: Crawler started successfully}
 → LLM 收到结果 → 回复用户 "已启动爬取任务, 可查询状态"
```

**产物路径**: MediaCrawler 默认落盘到 `E:\source-code\MediaCrawler\data\{platform}_{crawler_type}\`（`SAVE_DATA_PATH` 可配置）。OmniAgent 侧通过 `media_crawler_status`/`media_crawler_logs` 轮询任务完成，再用现有 `file` 工具读取产物文件给 LLM 分析。

---

## 六、方案A优缺点

### 优点
1. **零依赖冲突**: MediaCrawler 独立 venv，httpx/pandas 版本不污染 OmniAgent
2. **零代码改动 MediaCrawler**: 完全用其自带 FastAPI，无需改一行
3. **登录态可复用**: API 进程常驻，扫码一次登录，后续爬取免登录（`SAVE_LOGIN_STATE=True`）
4. **进程隔离三层**: OmniAgent / API进程 / 爬虫子进程，崩溃不扩散
5. **异步任务控制**: start/stop/status/logs 全有现成 API，天然支持长任务
6. **复用 [11] 网关先例**: 独立进程 + 端口分配 + 生命周期管理已有成熟模式

### 缺点
1. **多一个常驻服务**: 需手动/计划任务启动 MediaCrawler API，增加运维点
2. **端口占用**: 需确保 8080 空闲
3. **首次登录手动**: 扫码/手机验证码需人工介入（qrcode 模式下浏览器弹窗）
4. **Playwright 资源**: 浏览器进程占用内存（约 200MB+），爬取期间显著

---

## 七、方案A实施清单（待用户决策后执行）

| 步骤 | 动作 | 产出 |
|------|------|------|
| 1 | `cd E:\source-code\MediaCrawler; uv sync` | 独立 venv 装好依赖 |
| 2 | `uv run playwright install chromium` | 浏览器引擎 |
| 3 | 复制 .env.example → .env，按需改 | 配置 |
| 4 | 启动 `uv run uvicorn api.main:app --port 8080` | 常驻服务 |
| 5 | 新增 `backend/app/tools/media/media_crawler.py` | 工具实现 |
| 6 | 新增 `backend/app/tools/media/media_schema.py` | 输入模型 |
| 7 | 修改 `backend/app/tools/media/media_register.py` | 注册4工具 |
| 8 | 冒烟测试: 调 media_crawler_start 验证 | 端到端通 |

**签名**: 商量 2026-11-24
