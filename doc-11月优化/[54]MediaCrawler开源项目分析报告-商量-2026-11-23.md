# MediaCrawler 开源项目分析报告

> 分析人：商量（OmniAgent）  分析日期：2026-11-23
> 项目代码克隆位置：`E:\data-doc\20261120-123629-8c58\MediaCrawler`
> GitHub 仓库：https://github.com/NanmiCoder/MediaCrawler

---

## 一、项目概览

| 项目 | 值 |
|------|-----|
| 名称 | MediaCrawler 自媒体平台爬虫 |
| 作者 | NanmiCoder（relakkes@gmail.com） |
| 语言 | Python（异步 asyncio） |
| GitHub Stars | **71,683**（2026-11-23 实时） |
| GitHub Forks | **13,493** |
| 许可协议 | NON-COMMERCIAL LEARNING LICENSE 1.1（非商用学习许可，禁止商业用途） |
| 最新提交 | 94e233e（2026-11-21） |
| 代码规模 | 191 个 Python 文件，364 个总文件，约 25.2 MB |
| 核心依赖 | playwright、httpx、sqlalchemy、pandas、wordcloud、xhshow、redis |

**一句话定位**：一个功能强大的**多平台自媒体数据采集工具**，基于 Playwright 浏览器自动化，通过保留登录态的方式直接调用平台 API，**无需逆向复杂的 JS 加密算法**，大幅降低技术门槛。

---

## 二、支持的 7 大平台

| 平台 | 代号 | 代码量 | 关键词搜索 | 指定帖子ID | 二级评论 | 创作者主页 | 登录态缓存 | IP代理池 | 词云图 |
|------|------|--------|-----------|-----------|---------|-----------|-----------|---------|--------|
| 小红书 | xhs | 2197 行 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 抖音 | dy | 1386 行 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 快手 | ks | 1394 行 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| B站 | bili | 1834 行 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 微博 | wb | 1166 行 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 贴吧 | tieba | 2306 行 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| 知乎 | zhihu | 1521 行 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 三、核心技术原理（最厉害的地方）

### 1. 不做 JS 逆向，靠浏览器登录态取签名
多数爬虫靠 JS 逆向还原加密算法，MediaCrawler **反其道而行之**——让浏览器自己完成登录和签名，Python 端只负责调度和落盘。门槛从"能逆向的人"降到"会用浏览器的人"。

- **核心技术**：基于 Playwright 浏览器自动化框架登录保存登录态
- **无需 JS 逆向**：利用保留登录态的浏览器上下文环境，通过 JS 表达式获取签名参数
- **CDP 模式**：小红书、抖音等平台可选 CDP（Chrome DevTools Protocol）接入方式，用 CDPBrowserManager 管理

### 2. 小红书签名已升级为纯算法库
`media_platform/xhs/playwright_sign.py` 依赖 **xhshow** 开源库（MIT 协议，Cloxl 提供），用纯算法生成 `x-s`、`x-t`、`x-s-common`、`x-b3-traceid` 签名请求头——不再完全依赖浏览器执行 JS 取签名，性能更优。

### 3. 反爬对策体系
- **CDP 模式**：连接真实浏览器调试端口，规避自动化检测
- **IP 代理池**：`proxy/proxy_ip_pool.py` 自动创建代理池、校验 IP、自动刷新
- **请求签名**：各平台独立签名逻辑
- **stealth.min.js**：注入反检测脚本，防止网站识别爬虫

---

## 四、系统架构分析

### 1. 分层架构（清晰解耦）

```
main.py 入口（CrawlerFactory 工厂模式调度）
  ├── base/base_crawler.py  → 4 个抽象基类
  │     ├── AbstractCrawler（start/search/launch_browser）
  │     ├── AbstractLogin（begin/login_by_qrcode/login_by_mobile/login_by_cookies）
  │     ├── AbstractStore（store_content/store_comment/store_creator）
  │     └── AbstractApiClient（request/update_cookies）
  ├── media_platform/{平台}/  → 7 平台实现（core/client/login/help/field/extractor/exception/media/签名）
  ├── store/{平台}/           → 存储层（工厂+策略，8 种存储方式）
  ├── database/               → SQLAlchemy ORM + SQLite/MySQL/MongoDB
  ├── model/                  → 7 平台数据模型
  ├── proxy/                  → IP 代理池
  ├── tools/                  → 工具（app_runner/browser_launcher/cdp_browser/httpx_util 等）
  ├── api/                    → FastAPI 后端（crawler/data/websocket/crawler_manager）
  ├── webui/                  → Vue + Vite + Tailwind 前端 Web 界面
  └── config/                 → 按平台模块化配置（base + 7 平台 + db）
```

### 2. 存储层设计（工厂 + 策略模式，优秀）
`XhsStoreFactory.STORES` 字典映射 8 种存储方式：
```python
STORES = {
    "csv": XhsCsvStoreImplement,
    "db": XhsDbStoreImplement,
    "postgres": XhsDbStoreImplement,
    "json": XhsJsonStoreImplement,
    "jsonl": XhsJsonlStoreImplement,
    "sqlite": XhsSqliteStoreImplement,
    "mongodb": XhsMongoStoreImplement,
    "excel": XhsExcelStoreImplement,
}
```
每种存储实现继承 `AbstractStore`，接口/实现分离，新增存储方式只需加一个类 + 一行字典。

### 3. 配置模块化
`config/` 按平台拆分（base_config + bilibili/dy/ks/tieba/weibo/xhs/zhihu 各一 + db_config），避免巨型配置文件，符合 SRP 单一职责。

### 4. 异步高并发
基于 asyncio 的异步架构，各平台爬虫用 `async_playwright` + httpx 异步客户端，高效并发爬取。

---

## 五、为什么它"厉害"（核心价值总结）

1. **降门槛**：不做 JS 逆向，靠浏览器登录态取签名，让普通开发者也能爬取主流平台
2. **多平台覆盖**：7 大中文社交媒体平台一套框架，代码复用高
3. **架构规范**：抽象基类 + 工厂模式 + 策略模式 + 模块化配置，分层清晰，扩展性强
4. **多存储支持**：CSV/JSON/JSONL/SQLite/MySQL/MongoDB/Excel 8 种落盘方式自由切换
5. **反爬完善**：CDP 模式 + IP 代理池 + 请求签名 + 反检测脚本
6. **工程化完备**：Web 界面（Vue/FastAPI）、词云图生成、媒体下载、异步文件写入、测试
7. **社区认可**：71,683 Stars / 13,493 Forks，是中文社交媒体爬虫领域最受欢迎的开源项目之一

---

## 六、注意事项（合规）

- **许可协议**：NON-COMMERCIAL LEARNING LICENSE 1.1，**禁止商业用途**，与 OSI 开源协议不兼容
- **免责声明**：仅供学习和研究使用，禁止大规模爬取或破坏平台运营
- **合规风险**：爬虫可能违反平台使用条款，存在法律风险（项目 README 明确提示）
- **付费版**：MediaCrawlerPro（断点续爬/多账号/去 Playwright/AI Agent）为订阅制，开源版功能受限

---

## 七、结论

**是的，MediaCrawler 确实很厉害。** 它是目前最全面的中文社交媒体开源爬虫工具：
- 技术路线聪明（不做 JS 逆向，靠浏览器登录态取签名）
- 架构规范（抽象基类 + 工厂 + 策略 + 模块化配置）
- 覆盖广（7 大平台）、存储多（8 种方式）、反爬全（CDP/代理池/签名）
- 社区认可度高（71K+ Stars）

代码已克隆到 `E:\source-code\MediaCrawler`，可直接研究分析。

---

## 八、集成到 OmniAgent 可行性研究

### 8.1 结论：可行，但必须隔离运行（不能同环境安装）

MediaCrawler **可以集成**到 OmniAgent，但**不能直接 pip install 进 OmniAgent 的 Python 环境**——存在依赖版本硬冲突，必须隔离运行。

### 8.2 依赖冲突分析（关键）

| 依赖 | OmniAgent 版本 | MediaCrawler 版本 | 结论 |
|------|---------------|-------------------|------|
| httpx | `==0.26.0` | `==0.28.1` | ❌ **硬冲突** |
| pandas | `>=3.0.0` | `==2.2.3` | ❌ **硬冲突** |
| playwright | `>=1.59.0` | `>=1.61.0` | ✅ 可兼容 |
| fastapi | `>=0.109,<1` | `==0.110.2` | ✅ 可兼容 |
| sqlalchemy | `>=2.0.25,<3` | `>=2.0.43` | ✅ 可兼容 |
| pydantic | `>=2.5.3,<3` | `>=2.13.4` | ✅ 可兼容 |

**结论**：httpx 与 pandas 版本硬冲突，MediaCrawler 必须**独立 venv** 运行，与 OmniAgent 环境隔离。

### 8.3 MediaCrawler 自带完整 HTTP API（天然集成点）

MediaCrawler 内置 FastAPI 服务（`api/main.py`），提供完整爬取控制接口，且 `crawler_manager` 内部用 **subprocess 隔离爬虫子进程**（天然符合隔离要求）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/crawler/start` | POST | 启动爬取（CrawlerStartRequest 参数） |
| `/api/crawler/stop` | POST | 停止爬取 |
| `/api/crawler/status` | GET | 查询状态 |
| `/api/crawler/logs` | GET | 获取日志 |
| `/api/health` | GET | 健康检查 |
| `/api/config/platforms` | GET | 平台列表 |
| `/api/config/options` | GET | 配置选项 |

`CrawlerStartRequest` 请求模型字段（`api/schemas/crawler.py`）：
```python
platform: PlatformEnum          # xhs/dy/ks/bili/wb/tieba/zhihu
login_type: LoginTypeEnum       # qrcode/mobile/cookies
crawler_type: CrawlerTypeEnum   # search/detail/creator
keywords: str                   # 搜索关键词
specified_ids: str              # 指定帖子ID（逗号分隔）
creator_ids: str                # 创作者ID（逗号分隔）
start_page: int = 1
enable_comments: bool = True
enable_sub_comments: bool = False
enable_media: bool = False
save_option: SaveDataOptionEnum # csv/json/jsonl/sqlite/mysql/mongodb/excel
```

### 8.4 推荐集成方案：独立进程网关 + HTTP API（方案 A）

参考 OmniAgent 已有的第三方 CLI 接入先例（文档 [11] 第三方 CLI 模型接入网关），采用**独立进程网关**模式：

```
OmniAgent LLM
    │  调用 media_crawler 工具
    ▼
OmniAgent 工具层（新增 media_crawler.py 工具，封装 HTTP 调用）
    │  POST /api/crawler/start 等
    ▼
MediaCrawler 独立进程（独立 venv + uvicorn 启动 FastAPI）
    │  subprocess 隔离
    ▼
爬虫子进程（Playwright 浏览器 + 各平台爬虫）
```

**实施步骤**：
1. MediaCrawler 建立独立 venv：`python -m venv .venv` + `pip install -e .` + `playwright install`
2. 启动其 FastAPI 服务：`uvicorn api.main:app --port <port>`（作为独立进程，常驻复用登录态）
3. OmniAgent 新增 `media_crawler` 工具（`backend/app/tools/media/`），封装 HTTP 调用（start/stop/status/logs）
4. 工具 schema 对齐 `CrawlerStartRequest` 字段（platform/crawler_type/keywords/save_option 等）

**优点**：零依赖冲突、隔离安全、登录态可复用（服务常驻）、异步任务控制（start/stop/status）
**缺点**：需维护一个常驻服务进程

### 8.5 备选方案：CLI 子进程封装（方案 B）

OmniAgent 通过 shell 调用 MediaCrawler 的 `main.py`（独立 venv）：
```
python main.py --platform xhs --type search --keyword xxx
```
**优点**：实现最简单，无常驻服务
**缺点**：每次启动 Playwright 浏览器开销大，无法复用登录态

### 8.6 集成建议

- **推荐方案 A**（独立进程网关 + HTTP API）：依赖隔离最干净、登录态可复用、有异步任务控制
- 集成时注意 **MediaCrawler 许可协议禁止商业用途**，仅供学习研究使用
- 集成后 OmniAgent 用户可通过对话直接驱动爬取（如"爬取小红书'护肤'关键词笔记"），爬取结果落盘后由 OmniAgent 读取展示

**结论**：MediaCrawler 可集成到 OmniAgent，采用独立进程网关 + HTTP API 方式（方案 A），依赖隔离、零侵入、复用登录态，是可行的集成路径。
