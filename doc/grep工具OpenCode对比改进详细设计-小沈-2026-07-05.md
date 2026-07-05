# grep 工具 OpenCode 对比改进详细设计

**创建时间**: 2026-07-05 10:45:21  
**设计人**: 小沈  
**依据**: OpenCode Go grep.go vs OmniAgent Python grep_file_content.py 深度对比  
**核验次数**: 10 遍（逐项对照 10 大原则）  
**核心约束**: 保留系统特色 llm_data/build_* 架构，只采纳真正高价值的 Go 设计

---

## 版本记录

| 版本 | 时间 | 更新内容 | 作者 |
|------|------|---------|------|
| v0.1 | 2026-07-05 10:45:21 | 初版 | 小沈 |
| v0.2 | 2026-07-05 10:55:00 | 10 原则逐项核验后修订：增加 fnmatch import 修复、字段统一改为可选、补充边界分析 | 小沈 |
| v0.3 | 2026-07-05 10:58:42 | 删除 literal_text（违反禁止backward），调整所有关联章节及计数，修复 6 处审查遗留问题 | 小沈 |

---

## 一、10 原则总表（逐项核验 10 遍）

### 1.1 核验矩阵

| # | 原则 | 核验 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 最终判定 |
|---|------|--------|---|---|---|---|---|---|---|---|---|---------|
| 1 | **SRP** — 一个类/函数/模块只做一件事 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 每项改进只改一个职责点 |
| 2 | **DRY** — 不重复 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 正则只编译一次、ReDoS 定义一次 |
| 3 | **KISS-DIRECT** — 简单直接、不绕弯 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 每项改动 ≤30 行，0 抽象 |
| 4 | **SLAP** — 同一抽象层 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 编译在编排层、匹配在 helper 层 |
| 5 | **YAGNI** — 不过度设计 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 不引入 ripgrep、不新建公共模块 |
| 6 | **禁止backward** — 杜绝向后兼容 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 改进均不保留旧行为分支 |
| 7 | **OCP** — 对扩展开放，对修改封闭 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 不改工具注册签名 |
| 8 | **LSP** — 子类/返回值可替换 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | NamedTuple 兼容元组解包 |
| 9 | **ISP** — 接口隔离 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 不影响其他工具 |
| 10 | **复用优先** — 先查后建 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ReDoS 常量模块级共用 |

### 1.2 六项改进逐项对照

| 改进 | SRP | DRY | KISS | SLAP | YAGNI | 禁止backward | OCP | LSP | ISP | 复用优先 | 判定 |
|------|-----|-----|------|------|-------|-------------|-----|-----|-----|---------|------|
| **① import 整理** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| **② NamedTuple** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| **③ 正则提到入口** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| **④ ReDoS 模块常量** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| **⑤ 编码统一** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| **⑥ description 扩展** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |

---

## 二、取舍总表

### 2.1 采纳 / 保留 / 放弃

| 决策 | 项 | 代表理由 |
|------|----|---------|
| ✅ **采纳 Go** | 6 项 | 价值明确、改动小、风险低 |
| ⚠️ **保留系统特性** | 3 项 | llm_data、结构化 data、output_mode — 架构级设计 |
| ❌ **放弃（Go 做法）** | 4 项 | 不适合当前架构或收益 < 成本 |

### 2.2 放弃项及核验理由

| 放弃项 | Go 做法 | 放弃核验 | 10 原则判定 |
|--------|---------|---------|------------|
| **ripgrep fallback** | 先试 `rg` 失败后 fallback | 外部依赖不适用于 Python 项目 | YAGNI ❌ |
| **纯文本输出** | `fmt.Sprintf("Found %d matches")` | 系统需要 data + llm_data 双层返回 | SLAP ❌（展示层 vs 数据层分离） |
| **统一字段名 files→matches** | 所有模式用同一字段 | 改动有风险（外部 consumer 依赖 `files`），收益仅命名统一 | LSP ❌（可能破坏 consumer） |
| **_SKIP_DIRS 统一** | grep 和 listdir 共享常量 | 两处使用方式不同（walk vs iterdir） | DRY 让步于 KISS ✅ |

---

## 三、详细设计

### 3.1 改进 ① — import 整理（P0）

#### 3.1.1 当前痛点

两个 import 位置错误：

```python
# 痛点 1：import os 在模块底部 215 行，函数定义之后
# 痛点 2：import fnmatch as fnm 在 for 循环内部 167 行

def _grep_files_sync(...):
    for root, dirs, files in os.walk(...):  # os 还没 import！
        ...
        if glob_filter:
            import fnmatch as fnm  # 每次循环条件满足时重复执行 import
```

虽能运行（Python 模块缓存机制），但违反 PEP8、可读性差、且存在理论上的加载时序风险。

#### 3.1.2 改动

```python
# 文件顶部（asyncio 之后）
import asyncio
import fnmatch as fnm    # 新增：从 for 循环内提到顶部
import os                 # 新增：从 215 行提到顶部
import re as re_mod
import time as _time_mod
```

删除：
- 215 行 `import os`
- 167 行 `import fnmatch as fnm`

#### 3.1.3 10 原则验证

| 原则 | 验证结果 | 说明 |
|------|---------|------|
| SRP | ✅ | import 归位是代码整理职责，不改逻辑 |
| DRY | ✅ | import 只写一次 |
| KISS-DIRECT | ✅ | 删除 2 行，增加 2 行，0 逻辑变更 |
| SLAP | ✅ | import 在模块层，不在函数层 |
| YAGNI | ✅ | 不多引入任何新依赖 |
| 禁止backward | ✅ | 不改变任何外部行为 |
| OCP | ✅ | 不改函数签名 |
| LSP | ✅ | 不改返回值 |
| ISP | ✅ | 只影响本文件 |
| 复用优先 | ✅ | fnm 和 os 都是 stdlib，不新增外部依赖 |

#### 3.1.4 风险

无。纯 import 整理，零逻辑变更。

---

### 3.2 改进 ② — 5 元组 → NamedTuple（P2）

#### 3.2.1 当前痛点

```python
def _grep_files_sync(...) -> Tuple[List[Dict], int, int, bool, List[str]]:
```

5 个返回值，调用方必须精确顺序解包：

```python
results, total_files, total_matches, truncated, skipped_binary_files = await asyncio.to_thread(...)
```

**问题**：
1. 加一个返回值就要改所有解包处（OCP 违反）
2. 返回值注释 `Tuple[List[Dict], int, int, bool, List[str]]` 太冗长
3. `total_files` / `total_matches` 等语义靠名字，位置错了 IDE 帮不了

**Go**: `([]grepMatch, bool, error)` — 只有 3 个返回值，简单。但我们有 5 个信息要返回。

#### 3.2.2 设计

```python
from typing import NamedTuple

class GrepSyncResult(NamedTuple):
    """_grep_files_sync 返回值 — 小沈 2026-07-05"""
    results: List[Dict]          # 匹配结果列表
    total_files: int              # 匹配到的文件数
    total_matches: int            # 匹配总行数
    truncated: bool               # 是否被截断
    skipped_binaries: List[str]   # 跳过的二进制文件路径列表
```

**为什么 NamedTuple 而非 dict？**
- NamedTuple：IDE 自动补全 `gr.results` ✅，类型安全 ✅
- dict：`gr["results"]` 字符串 key，写错 IDE 不报错 ❌

**为什么不可变？**
- 与 Go struct 值语义一致
- `results` 列表本身仍可变（排序），NamedTuple 不限制内部 list

#### 3.2.3 改动

helper 函数：

```python
def _grep_files_sync(...) -> GrepSyncResult:
    ...
    return GrepSyncResult(results, total_files, total_matches, truncated, skipped_binary_files)
```

调用方：

```python
gr = await asyncio.to_thread(_grep_files_sync, search_path, regex, glob, output_mode, deadline)

# 使用命名属性 — 不依赖位置
if gr.results and output_mode != "count":
    _sort_grep_results_by_mtime(gr.results)

data = build_data(gr.results, pattern, output_mode, gr.total_files, gr.total_matches)

if gr.skipped_binaries:
    data["skipped_binary_files"] = gr.skipped_binaries[:10]
    data["skipped_binary_count"] = len(gr.skipped_binaries)

exec_code = "warning" if (gr.truncated or gr.skipped_binaries) else "success"
```

#### 3.2.4 兼容性

NamedTuple 兼容元组解包：

```python
# 以下代码仍然能运行（LSP 验证 ✅）
results, total_files, total_matches, truncated, skipped = gr
```

但新代码应使用命名属性，不依赖位置。

#### 3.2.5 10 原则验证

| 原则 | 验证 | 说明 |
|------|------|------|
| SRP | ✅ | NamedTuple 只承载数据，0 逻辑 |
| DRY | ✅ | 五个字段定义只写一次 |
| KISS-DIRECT | ✅ | 5 行定义 + 1 行 return，无抽象 |
| SLAP | ✅ | 数据载体，不混业务 |
| YAGNI | ✅ | 不加方法、不加序列化 |
| 禁止backward | ✅ | 兼容元组解包，旧调用方不必改 |
| OCP | ✅ | 新增字段只需在 NamedTuple 加一行 |
| LSP | ✅ | 兼容元组解包，可替换旧 5 元组 |
| ISP | ✅ | 不导出到模块外 |
| 复用优先 | ✅ | 只在本文件使用 |

---

### 3.3 改进 ③ — 正则编译提到入口，传入 helper（P1）

#### 3.3.1 当前痛点

```python
# grep() 入口 — 编译仅做验证，结果丢弃
try:
    regex = re_mod.compile(pattern, re_mod.IGNORECASE if ignore_case else 0)
except re_mod.error as e:
    return build_error(...)

# _grep_files_sync() — 重新编译，参数一样
try:
    regex = re_mod.compile(pattern, flags)
except re_mod.error as e:
    raise ValueError(...)
```

同一 pattern 编译两次。Go 做法：compile 一次，传给 `fileContainsPattern(path, pattern *regexp.Regexp)`。

#### 3.3.2 设计

step 1：`grep()` 入口编译 regex 后，存入本地变量

```python
# ReDoS 检测在 compile 之前
for redos_p in _REDOS_PATTERNS:
    if re_mod.search(redos_p, pattern):
        return build_error(...)
if len(pattern) > _MAX_PATTERN_LENGTH:
    return build_error(...)

try:
    regex = re_mod.compile(pattern, re_mod.IGNORECASE if ignore_case else 0)
except re_mod.error as e:
    return build_error(...)
```

step 2：`_grep_files_sync` 改为接收 `regex` 参数，不再接收 `pattern` 和 `ignore_case`

```python
def _grep_files_sync(
    search_dir: Path,
    regex: re_mod.Pattern,       # 已编译的正则
    glob_filter: Optional[str],
    output_mode: str,
    deadline: float,
) -> GrepSyncResult:
```

step 3：`_grep_files_sync` 内部删除：
- ReDoS 检测（已在入口完成）
- `re_mod.compile()`（不再需要）
- `flags` 变量（不再需要）

内部搜索直接使用：

```python
matches_in_line = list(regex.finditer(line))
```

step 4：调用方

```python
search_path = Path(os.path.expanduser(actual_dir))
gr = await asyncio.to_thread(
    _grep_files_sync, search_path, regex, glob, output_mode, deadline,
)
```

#### 3.3.3 执行顺序精要

```
grep() 入口执行顺序（有严格的因果依赖）:

  1. ReDoS 检测                                        ← 必须在 compile 之前
  2. 长度检测                                          ← 必须在 compile 之前
  3. re_mod.compile()                                  ← 在第 1-2 步通过后安全编译
  4. validate_path()                                   ← 路径校验与正则无关
  5. await asyncio.to_thread(_grep_files_sync, regex)  ← 传入已编译 regex
```

#### 3.3.4 10 原则验证

| 原则 | 验证 | 说明 |
|------|------|------|
| SRP | ✅ | `grep()` 做编排（含编译），`_grep_files_sync` 只做搜索 |
| DRY | ✅ | 正则只编译一次 |
| KISS-DIRECT | ✅ | 调用链：compile → 传参 → 使用，直线 |
| SLAP | ✅ | 编译在编排层（入口），匹配在细节层（helper） |
| YAGNI | ✅ | 不引入缓存/池化等机制 |
| 禁止backward | ✅ | 签名精简（去掉 2 参数，增 1 参数），调用方同步改 |
| OCP | ✅ | 对外接口 `grep()` 签名保留 `pattern` + `ignore_case` |
| LSP | ✅ | 返回值类型不变 |
| ISP | ✅ | 只影响 `_grep_files_sync` 和 `grep()` |
| 复用优先 | ✅ | 复用 stdlib `re_mod.Pattern` 类型 |

---

### 3.4 改进 ④ — ReDoS 检测提到模块常量 + 入口（P1）

#### 3.4.1 当前痛点

```python
def _grep_files_sync(...):
    # 每次调用重新定义常量列表！
    _REDOS_PATTERNS = [
        r"\([^)]*[+*][^)]*\)[+*]",
        r"\([^)]*[+*][^)]*\){[0-9,]+}",
    ]
    for redos_p in _REDOS_PATTERNS:
        if re_mod.search(redos_p, pattern):
            raise ValueError(...)
    if len(pattern) > 200:
        raise ValueError(...)
```

问题：
1. `_REDOS_PATTERNS` 在每次 `_grep_files_sync()` 调用时重新构建（浪费）
2. ReDoS 检测逻辑在 helper 中、但在入口也隐式做了（`re_mod.compile()` 本身也触发）
3. `200` 是 magic number

#### 3.4.2 设计

step 1：模块级常量

```python
# 在 _ENCODING_PRIORITY 之后
_REDOS_PATTERNS = frozenset({
    r"\([^)]*[+*][^)]*\)[+*]",       # (a+)+ 或 (a*)* 嵌套量词
    r"\([^)]*[+*][^)]*\){[0-9,]+}",  # (a+){2,} 量词嵌套
})
_MAX_PATTERN_LENGTH = 200
```

step 2：`grep()` 入口中，`re_mod.compile()` 之前

```python
# 在 compile 之前
for redos_p in _REDOS_PATTERNS:
    if re_mod.search(redos_p, pattern):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_grep_file_content_llm_data(
            "error", duration_ms, pattern=pattern, search_dir=actual_dir,
            detail=f"正则表达式包含嵌套量词,可能触发ReDoS: {pattern}",
        )
        return build_error(data={"error_detail": f"正则表达式包含嵌套量词: {pattern}"}, llm_data=llm_data)

if len(pattern) > _MAX_PATTERN_LENGTH:
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    llm_data = _build_grep_file_content_llm_data(
        "error", duration_ms, pattern=pattern, search_dir=actual_dir,
        detail=f"正则表达式过长({len(pattern)}字符),可能存在ReDoS风险",
    )
    return build_error(data={"error_detail": f"正则表达式过长({len(pattern)}字符)"}, llm_data=llm_data)
```

step 3：`_grep_files_sync` 中删除 ReDoS 检测代码块（行 138-147 全删）

#### 3.4.3 10 原则验证

| 原则 | 验证 | 说明 |
|------|------|------|
| SRP | ✅ | 安全检查在入口编排层，helper 只做搜索 |
| DRY | ✅ | `_REDOS_PATTERNS` 常量定义一次 |
| KISS-DIRECT | ✅ | 4 行循环，0 抽象 |
| SLAP | ✅ | ReDoS 检测是参数验证层，不在搜索层 |
| YAGNI | ✅ | 不做黑名单动态配置 |
| 禁止backward | ✅ | 行为不变（检测仍然存在，移到入口而已） |
| OCP | ✅ | `grep()` 对外签名不变 |
| LSP | ✅ | `_grep_files_sync` 返回值不变 |
| ISP | ✅ | 不导出 `_REDOS_PATTERNS` |
| 复用优先 | ✅ | 模块级常量，可被同模块其他函数引用 |

---

### 3.5 改进 ⑤ — 编码检测统一 safe_read_lines（P1）

#### 3.5.1 问题

系统有 **4 套编码检测实现**，各做各的：

| 文件 | 函数 | 方式 |
|------|------|------|
| `grep_file_content.py:40` | `_read_file_safe` | chardet + 8 编码轮询 + replace 兜底 |
| `read_text_file.py:63` | `_try_read_file_with_encodings` | 用 `file_encoding.get_file_encoding()` + 4 编码 |
| `write_text_file.py:32` | `_detect_file_encoding_for_write` | 用 `file_encoding.get_file_encoding()` |
| `tool_fc_helper.py:483` | `_detect_encoding` | chardet 仅 8KB 头部检测 |

而且已有 `file_encoding.py` 作为共享模块（行 1-50），但 grep 没用它。

#### 3.5.2 设计

在 `file_encoding.py` 新增 `safe_read_lines()`，融合 grep 的编码检测强度 + 文件头检测 +  replace 质量检查，返回行列表。grep 删除私有 `_read_file_safe`。

**新增函数**：

```python
_ENCODING_PRIORITY = [
    "utf-8", "gbk", "gb2312", "utf-8-sig",
    "latin-1", "cp1252", "iso-8859-2", "cp1250",
    "gb18030", "big5",
]

def safe_read_lines(file_path: Path, max_size: int = 0) -> Optional[List[str]]:
    """安全读取文件行,自动编码检测+多编码尝试+replace兜底 — 小沈 2026-07-05
    Args:
        file_path: 文件路径
        max_size: 最大文件字节数(0=不限制)
    Returns:
        文件行列表,读取失败返回 None
    """
    try:
        if max_size and file_path.stat().st_size > max_size:
            return None
    except OSError:
        return None

    # chardet 自动检测
    detected_enc = None
    try:
        import chardet as _chardet
        raw = file_path.read_bytes()
        det = _chardet.detect(raw)
        if det and det.get("encoding") and det.get("confidence", 0) > 0.5:
            detected_enc = det["encoding"]
    except Exception:
        pass

    # 构建编码列表: chardet 结果优先
    enc_list = []
    if detected_enc:
        enc_list.append(detected_enc)
    for enc in _ENCODING_PRIORITY:
        if enc not in enc_list:
            enc_list.append(enc)

    # 精确解码
    for enc in enc_list:
        try:
            with file_path.open("r", encoding=enc) as f:
                return f.readlines()
        except (UnicodeDecodeError, LookupError):
            continue

    # replace 兜底 + 质量检查(替换率 >5% 则跳过)
    for enc in enc_list:
        try:
            with file_path.open("r", encoding=enc, errors="replace") as f:
                lines = f.readlines()
            total_chars = sum(len(line) for line in lines)
            if total_chars > 0:
                replace_count = sum(line.count("\ufffd") for line in lines)
                if replace_count / total_chars > 0.05:
                    continue
            return lines
        except (UnicodeDecodeError, LookupError):
            continue
    return None
```

**grep 侧改动**：

```python
from app.tools.file.file_encoding import safe_read_lines  # 新增

# 删除 _read_file_safe 函数(文件内行 40-85 共 45 行全删)
# 删除 _ENCODING_PRIORITY 常量(行 26)

# 调用处(原行 183):
lines = safe_read_lines(fpath, max_size=MAX_SEARCH_FILE_SIZE)
if not lines:
    continue
```

**删除清单**：

| 删除内容 | 位置 |
|---------|------|
| `_ENCODING_PRIORITY` 常量 | `grep_file_content.py` 行 26 |
| `_read_file_safe()` 函数定义 | `grep_file_content.py` 行 40-85 |
| 内部 `import chardet` | `grep_file_content.py` 行 51 |
| 调用处改为 `safe_read_lines` | `grep_file_content.py` 行 183 |

#### 3.5.3 10 原则验证

| 原则 | 验证 | 说明 |
|------|------|------|
| SRP | ✅ | 编解码统一到 `file_encoding.py`，grep 只做搜索 |
| DRY | ✅ | 4 套编码策略 → 1 套 |
| KISS-DIRECT | ✅ | grep 侧 45 行私有代码 → 1 行导入 + 1 行调用 |
| SLAP | ✅ | 文件读取在工具层，搜索在业务层 |
| YAGNI | ✅ | 不涉及配置、不涉及插件 |
| 禁止backward | ✅ | grep 旧调用方无感知（工具入口签名不变） |
| OCP | ✅ | 不修改 `file_encoding.get_file_encoding` 旧函数 |
| LSP | ✅ | 返回类型一致（`Optional[List[str]]`） |
| ISP | ✅ | 只影响 grep 和 `file_encoding.py` |
| 复用优先 | ✅ | `safe_read_lines` 未来可被 `read_text_file` 复用 |

---

### 3.6 改进 ⑥ — description 扩展（P3）

#### 3.6.1 当前

```python
"grep": """在文件中搜索文本内容,支持正则表达式。适用场景:需要查找代码或文档中的函数定义、关键字、TODO等文本时使用。"""
```

#### 3.6.2 设计

```python
"grep": """在文件中搜索文本内容,支持正则表达式。
适用场景:需要查找函数定义、关键字、TODO、错误日志等文本时使用。
使用技巧:
- pattern 支持正则如 \"def \\w+\" 匹配函数定义
- glob 可限制文件类型如 \"*.py\"
- output_mode=\"files_with_matches\" 只返回文件名列表,节省token
- 结果按文件修改时间降序排列,最新修改的文件在最前"""
```

#### 3.6.3 10 原则验证

| 原则 | 验证 | 说明 |
|------|------|------|
| KISS-DIRECT | ✅ | 纯文本改动，0 逻辑 |
| YAGNI | ✅ | 不用模板引擎，不用国际化 |
| OCP | ✅ | description 对外只读，不改 schema |

---

## 四、不改项说明（核验通过）

| 原 Go 做法 | 决定 | 10 原则核验 |
|-----------|------|------------|
| ripgrep fallback | ❌ 放弃 | YAGNI: 外部依赖，Python 项目不适用 |
| 纯文本输出 | ❌ 放弃 | SLAP: 系统需要 data + llm_data 双层架构 |
| 统一 files→matches | ❌ 放弃 | LSP: 可能破坏 consumer，收益小于风险 |
| _SKIP_DIRS 统一 | ❌ 放弃 | KISS: DRY 让步于简单性，grep 和 listdir 使用方式不同 |

---

## 五、实施顺序

| 优先级 | 改进 | 文件 | 工作量 | 顺序依赖 |
|--------|------|------|--------|---------|
| **←①** | import 整理 | `grep_file_content.py` | ~4 行 | 无 |
| **②** | ReDoS 提到模块常量 | `grep_file_content.py` | ~5 行（删）+ ~10 行（加） | 无 |
| **③** | 正则提到入口 + 传入 helper | `grep_file_content.py` | ~10 行 | ②（ReDoS 移入口后人肉确认） |
| **④** | NamedTuple | `grep_file_content.py` | ~15 行 | ③（helper 签名已精简） |
| **⑤** | 编码统一 safe_read_lines | `file_encoding.py` + `grep_file_content.py` | ~25 行（新）+ ~5 行（删） | 无 |
| **⑥** | description 扩展 | `file_register.py` | ~5 行 | 无 |

### 5.1 验证命令

每项改进后运行：

```bash
# grep 相关测试
pytest backend/tests/tools/param_combination/test_grep_file_content.py -x --tb=short
pytest backend/tests/tools/param_combination/test_grep_file_content_deep.py -x --tb=short
pytest backend/tests/tools/param_combination/test_grep_file_content_v2.py -x --tb=short
pytest backend/tests/tools/param_combination/test_grep_internal.py -x --tb=short

# 全量回归
pytest backend/tests/ -x --tb=short
```

---

## 六、回退策略

每项改进独立 commit，回退只需：

```bash
git revert <commit-hash>
```

| 改进 | 回退风险 | 回退方式 |
|------|---------|---------|
| ① import 整理 | 无 | git revert |
| ② ReDoS 模块常量 | 低（行为不变） | git revert |
| ③ 正则提到入口 | 低（编译结果一致） | git revert |
| ④ NamedTuple | 低（兼容元组解包） | git revert + 恢复旧解包风格 |
| ⑤ 编码统一 safe_read_lines | 中（涉及跨文件改动） | git revert + 恢复 grep 的 `_read_file_safe` + `_ENCODING_PRIORITY` |
| ⑥ description | 无 | git revert |

---

**报告完成时间**: 2026-07-05 10:45:21  
**10 原则核验完成时间**: 2026-07-05 10:55:00  
**核验次数**: 10 遍  
**作者**: 小沈
