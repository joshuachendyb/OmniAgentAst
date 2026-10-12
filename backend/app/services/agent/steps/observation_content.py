# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-12 小欧 - 新建（observation.content 启用方案 B1）。由 tool_result[] 投影出
#   content_items 对象数组; content 句子由 ObservationStep 逐条 render_line 生成,
#   本文件提供数组构造与句子渲染 — 小欧 2026-10-12
# 2026-10-12 小欧 - 北京老陈令: 参数超35截断保留(替代旧50丢弃); 正文类取首行后同样截断 — 小欧 2026-10-12
import json
from typing import Any, Dict, List

from app.logger import logger

# 参数丢弃名单: 与设计文档 3.5.6 表的丢列逐键一致, 改表即改本常量 — 小欧 2026-10-12
DROP_KEYS = frozenset({
    # 框架默认开关与基础设施（shell_type 已移出：北京老陈 2026-10-12 令加回句子显示）
    "success_codes", "ignore_case", "overwrite",
    "preserve_metadata", "extract_format", "js_render", "append_mode",
    "proxy", "headers", "conditions",
    # 长内容载荷（含 edit 的 old/new，转 lines 前先丢原文）
    "content", "data", "slides", "table_data", "body", "old_string", "new_string",
    # 结果呈现开关
    "context", "display", "include_minimized", "all_paths", "source",
    # 平台细节 / 时间范围 / 排除规则
    "hive", "output_format", "value_type", "value", "time_range", "exclude_patterns",
})

# FUNDAMENTAL 组成功分支三项对照(2026-10-12 小欧逐个核查, 零重复) —
# | tool       | params(进句子)                              | message(成功分支)          | 重复? |
# |------------|---------------------------------------------|----------------------------|-------|
# | bash       | command/timeout/cwd/shell_type              | 成功(纯状态词)             | 无    |
# | fetchpage  | prompt/timeout/url                          | 成功:mime,HTTP码(结果量)   | 无    |
# | notify     | title/message(正文)/duration                | 成功(纯状态词)             | 无    |
# | searchtool | query                                       | 完成:匹配N个(结果数)       | 无    |
# | searchweb  | query/num_results/allowed/blocked_domains  | 完成:N条结果(结果数)       | 无    |
# | timenow    | {}无参                                      | 成功:datetime,星期(结果值)  | 无    |
# FILE 组成功分支三项对照(2026-10-12 小欧逐个核查) —
# | tool    | params(进句子; dest有path时跳过)          | message(成功分支)          | 重复?    |
# |---------|--------------------------------------------|----------------------------|----------|
# | copy    | path+recursive(dest句子跳过)               | 成功(纯状态词)             | 无       |
# | delete  | path+force+recursive                       | 成功(纯状态词)             | 无       |
# | edit    | path+mode+encoding+行数派生                | 完成(纯状态词)             | 无       |
# | find    | path+pattern+type(offset句子跳过)          | 完成:共N个/第M-N项         | 已消     |
# | grep    | path+pattern+glob                          | 完成:N文件M行(结果量)      | 无       |
# | listdir | path+sort_by等                             | 成功:N项(结果量)           | 无       |
# | move    | path(dest句子跳过)                         | 成功(纯状态词)             | 无       |
# | read    | path(句子;limit等仅items)                  | 成功:从第X-Y行(范围)       | 已消     |
# | rename  | path(dest句子跳过)                         | 成功(纯状态词)             | 无       |
# | tree    | path+max_depth等                           | 成功:N文件(结果量)         | 无       |
# | write   | path+append+encoding                       | 成功(纯状态词)             | 无       |
# NETWORK 组成功分支三项对照(2026-10-12 小欧逐个核查, 零重复) —
# | tool     | params(进句子)                             | message(成功分支)          | 重复? |
# |----------|--------------------------------------------|----------------------------|-------|
# | download | url+timeout(+dest无path时)                 | 成功/成功:大小类型(结果量) | 无    |
# | httpget  | url+method+timeout                         | 成功:HTTP码+类型(结果量)   | 无    |
# | ping_port| host+port/mode+count+timeout               | 可达/开放等(结果态)        | 无    |
# DOCUMENT 组成功分支三项对照(2026-10-12 小欧逐个核查, 零重复) —
# | tool      | params(进句子)                            | message(成功分支)            | 重复? |
# |-----------|-------------------------------------------|------------------------------|-------|
# | compress  | path+dest(有path时dest跳)+format等        | 成功:N文件,压缩率(结果量)   | 无    |
# | extract   | path(+dest无path时)                       | 成功(纯状态词)               | 无    |
# | read_docx | path+limit等                              | 成功:N段,N字符(结果量)      | 无    |
# | read_pdf  | path(仅path进action)                      | 成功:已读X/共Y页(结果量)    | 无    |
# | read_pptx | path(仅path进action)                      | 成功:第X页(结果量)          | 无    |
# | read_xlsx | path+sheet_name                           | 成功:N行,M表(结果量)        | 无    |
# | readmedia | path                                      | 成功(纯状态词)               | 无    |
# | write_docx| path+title                                | 成功:N段,N字符(结果量)      | 无    |
# | write_pdf | path+title                                | 成功:N字符(结果量)          | 无    |
# | write_pptx| path                                      | 成功:N页(结果量)            | 无    |
# | write_xlsx| path+sheet_name                           | 成功:N行(结果量)            | 无    |
# DATAANALYSIS 组成功分支三项对照(2026-10-12 小欧逐个核查, generate_chart 1处重复待定) —
# | tool        | params(进句子)                           | message(成功分支)            | 重复? |
# |-------------|------------------------------------------|------------------------------|-------|
# | analyze_data| operations/group_by/path等               | 成功:N行,M数值列(结果量)    | 无    |
# | execute_sql | sql/path/连接串/timeout等                | 成功:影响N行(结果量)        | 无    |
# | filter_data | path/select/sort/top_n                   | 成功:原N筛出M行(结果量)     | 无    |
# | generate_chart| chart_type/dest/title/轴               | 成功:bar已保存(含chart值)   | 有    |
# | get_db_schema| 连接串/path/table                       | 成功:N个表(结果量)          | 无    |
# | query_sql   | sql/limit/path/连接串                    | 成功:N行(结果量)            | 无    |
# SYSTEM 组成功分支三项对照(2026-10-12 小欧逐个核查, 零重复) —
# | tool       | params(进句子)                            | message(成功分支)            | 重复? |
# |------------|-------------------------------------------|------------------------------|-------|
# | create_task| command/interval/schedule/task_name       | 成功(纯状态词)               | 无    |
# | delete_task| task_name                                 | 成功(纯状态词)               | 无    |
# | event_log  | level/log_name/max_events                 | 成功:N条事件(结果数)         | 无    |
# | list_tasks | state/task_name                           | 成功:共N个匹配M个(结果数)   | 无    |
# | sysinfo    | info_type                                 | 成功(纯状态词)               | 无    |
# | which      | command                                   | 找到N个/命令可用(结果态)     | 无    |
# 命令正文类: 取首行（3.5.4 长度分级）— 小欧 2026-10-12
BODY_KEYS = frozenset({"command", "sql", "query", "prompt"})

PARAM_VALUE_MAX_CHARS = 35   # 单个参数值的字符数上限, 超限截断加…保留（北京老陈 2026-10-12 新令, 替代旧50丢弃）
CONTENT_MAX_CHARS = 2048   # content 序列化后的字符数上限（D5）


def _one_line(text: str) -> str:
    """压成单行：值内换行符转空格，保"一句一行"不变式 — 小欧 2026-10-12"""
    return " ".join(str(text).split())


def _first_line(value: Any) -> str:
    """取字符串首行 — 小欧 2026-10-12"""
    lines = str(value).splitlines()
    return lines[0] if lines else ""


def _diff_line_counts(diff_text: str) -> Dict[str, int]:
    """从 unified_diff 文本统计新增/删除行数 — 小欧 2026-10-12

    算法与 edit_text_file.py:320-321 完全一致(`+` 去 `+++` 头 / `-` 去 `---` 头, 零新依赖),
    不另起 difflib 实现, 避免同一口径两处计算; 返回两个计数故用复数 counts — 小欧 2026-10-12
    """
    lines = (diff_text or "").splitlines()
    added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
    return {"lines_added": added, "lines_removed": removed}


# 参数主次排序: 主体 > 路径 > 其余字母序（3.4.1）— 小欧 2026-10-12
PARAM_ORDER = ["command", "sql", "query", "prompt", "pattern", "operations",
               "method", "path", "dest"]


def _order_params(out: Dict[str, Any]) -> Dict[str, Any]:
    """按主次排序 params: P0 主体 > P1 路径 > P2 其余字母序 — 小欧 2026-10-12"""
    first = [k for k in PARAM_ORDER if k in out]
    rest = sorted(k for k in out if k not in PARAM_ORDER)
    return {k: out[k] for k in first + rest}


def _pick_params(action: Dict[str, Any]) -> Dict[str, Any]:
    """按 3.5.6 表逐键取 params: 丢列跳过 / 正文类取首行后截断 / 其余超35截断保留 — 小欧 2026-10-12"""
    params = action.get("params")
    if not isinstance(params, dict):
        return {}
    out: Dict[str, Any] = {}
    for key, val in params.items():
        if key in DROP_KEYS:
            continue
        if isinstance(val, (list, dict)):
            continue
        if isinstance(val, bool) or val is None or isinstance(val, (int, float)):
            out[key] = val
            continue
        if key in BODY_KEYS:
            text = _one_line(_first_line(val))
            if len(text) > PARAM_VALUE_MAX_CHARS:
                text = text[:PARAM_VALUE_MAX_CHARS] + "…"
            out[key] = text
            continue
        text = _one_line(str(val))
        if len(text) > PARAM_VALUE_MAX_CHARS:
            text = text[:PARAM_VALUE_MAX_CHARS] + "…"
        out[key] = text
    return _order_params(out)


def _build_item(element: Dict[str, Any]) -> Dict[str, Any]:
    """单个 tool_result 元素 → 一条 content 记录（7 字段；全 .get 兜底, 绝不抛异常）— 小欧 2026-10-12"""
    llm = element.get("llm_data")
    llm = llm if isinstance(llm, dict) else {}
    action = llm.get("action")
    action = action if isinstance(action, dict) else {}
    status = llm.get("status")
    status = status if isinstance(status, dict) else {}

    tool = action.get("tool") or element.get("tool_name") or ""
    duration = llm.get("duration_ms")
    duration = duration if isinstance(duration, (int, float)) else 0

    item: Dict[str, Any] = {
        "tool": str(tool),
        "tool_zh": str(action.get("tool_zh") or tool),
        "exec_code": str(status.get("exec_code") or "unknown"),
        "message": str(status.get("message") or ""),
        "params": _pick_params(action),
        "duration_ms": duration,
        "detail": str(status.get("detail") or ""),
    }

    if tool == "edit":  # edit 特例: 原文不进 content, 改出行数增减（3.5.3）
        metrics = llm.get("metrics")
        metrics = metrics if isinstance(metrics, dict) else {}
        added = metrics.get("added")
        removed = metrics.get("removed")
        if isinstance(added, dict) and isinstance(removed, dict):
            item["params"].update({
                "lines_added": added.get("value"),
                "lines_removed": removed.get("value"),
            })
        elif metrics.get("diff"):
            item["params"].update(_diff_line_counts(metrics.get("diff")))
        else:
            logger.debug("[observation_content] edit 无 added/removed/diff, 无法统计行数: tool=%r", tool)
    return item


PATH_LIKE = frozenset({"path", "dest"})  # 句子内 path 类参数（D9: 只取第一个）
COMMAND_MAX_CHARS = 35   # 句子内 command 超长截断并加 …（D9）

# message 已含参数键的工具: 句子内跳过这些键, content_items 照旧全留 — 小欧 2026-10-12
# read 的 message 自带范围(实际起止行), 句子再渲 limit/offset/tail/encoding 即重复
# find 带 offset 时 message 自带"第M-N项"(由 offset 算出), 句子再渲 offset 即重复
MSG_DUP_KEYS = {
    "read": frozenset({"limit", "offset", "tail", "encoding"}),
    "find": frozenset({"offset"}),
}


def _basename(value: Any) -> str:
    """路径含分隔符时只取文件名（Windows/Unix 均处理）— 小欧 2026-10-12"""
    import ntpath
    import posixpath
    text = str(value)
    return ntpath.basename(text) or posixpath.basename(text) or text


# 参数中文显示映射: 只作用于 content 句子渲染（3.4.2）, content_items 存原始键值 — 小欧 2026-10-12
# 共 84 条 = 保留列 82 键 + edit 派生 2 键, 与 3.4.2 表逐条对应, 句子里不出现任何英文键名
PARAM_ZH = {
    # 路径裸值（3.4.2.1, PATH_LIKE 分支先取文件名再套用本模板）
    "path": "{v}",
    "dest": "{v}",
    # 中文模板（3.4.2.2）
    "timeout": "超时{v}秒",
    "limit": "前{v}条",
    "offset": "从第{v}条起",
    "tail": "末{v}行",
    "sort_by": "按{v}排序",
    "top_n": "前{v}条",
    "num_results": "取{v}条",
    "max_depth": "最深{v}层",
    "page": "第{v}页",
    "slide": "第{v}页",
    # edit 派生量（3.4.2.4，与文档用字一致：新增/删除）
    "lines_added": "新增{v}行",
    "lines_removed": "删除{v}行",
    # 自由文本裸值（3.4.2.3, 值自解释，不加标签；command 仍受 35 截断约束）
    "command": "{v}",
    "sql": "{v}",
    "prompt": "{v}",
    "query": "{v}",
    "pattern": "{v}",
    "message": "{v}",
    "title": "{v}",
    "url": "{v}",
    "text_or_keys": "{v}",
    "callback": "{v}",
    # 中文显示（3.4.2.5）
    "action": "操作{v}",
    "allowed_domains": "允许域名{v}",
    "amount": "数量{v}",
    "append": "追加{v}",
    "blocked_domains": "屏蔽域名{v}",
    "button": "按键{v}",
    "chart_type": "图表{v}",
    "clicks": "点击{v}次",
    "confirm_ddl": "确认{v}",
    "connection_string": "连接串{v}",
    "connection_type": "连接类型{v}",
    "count": "次数{v}",
    "cwd": "目录{v}",
    "delay": "延迟{v}秒",
    "delta": "增量{v}",
    "direction": "方向{v}",
    "dry_run": "试运行{v}",
    "duration": "持续{v}秒",
    "encoding": "编码{v}",
    "end": "结束{v}",
    "filter_title": "过滤标题{v}",
    "force": "强制{v}",
    "format": "格式{v}",
    "glob": "通配{v}",
    "group_by": "按{v}分组",
    "height": "高度{v}",
    "host": "主机{v}",
    "include_hidden": "含隐藏{v}",
    "info_type": "信息{v}",
    "interval": "间隔{v}秒",
    "level": "级别{v}",
    "log_name": "日志{v}",
    "max_events": "最多{v}条",
    "method": "方法{v}",
    "mode": "模式{v}",
    "name": "名称{v}",
    "operations": "操作{v}",
    "pages": "页数{v}",
    "password": "密码{v}",
    "port": "端口{v}",
    "recursive": "递归{v}",
    "region": "区域{v}",
    "schedule": "计划{v}",
    "select_columns": "取列{v}",
    "sheet_name": "表{v}",
    "shell_type": "Shell{v}",
    "start": "开始{v}",
    "state": "状态{v}",
    "table_name": "表名{v}",
    "task_name": "任务{v}",
    "timer_id": "定时器{v}",
    "type": "类型{v}",
    "unit": "单位{v}",
    "value_name": "值名{v}",
    "width": "宽度{v}",
    "window_title": "窗口{v}",
    "x": "横坐标{v}",
    "x_label": "横轴{v}",
    "y": "纵坐标{v}",
    "y_label": "纵轴{v}",
    "year": "年份{v}",
}


def _zh_param(key: str, text: str) -> str:
    """单个参数 → 句子片段: 中文模板优先, 不在表内走 键=值 兜底 — 小欧 2026-10-12"""
    template = PARAM_ZH.get(key)
    if template:
        return template.format(v=text)
    return f"{key}={text}"


# 布尔参数肯定/否定词（3.4.2.6, 句子里不出现 True/False）— 小欧 2026-10-12
BOOL_ZH = {
    "append": ("追加", "覆盖"),
    "confirm_ddl": ("已确认", "未确认"),
    "dry_run": ("试运行", "正式执行"),
    "force": ("强制", "不强制"),
    "include_hidden": ("含隐藏", "不含隐藏"),
    "recursive": ("递归", "不递归"),
}


def _zh_value(key: str, val: Any) -> str:
    """单个参数值 → 句子片段: 布尔查 BOOL_ZH, 其余走 _zh_param — 小欧 2026-10-12"""
    if isinstance(val, bool) and key in BOOL_ZH:
        pos, neg = BOOL_ZH[key]
        return pos if val else neg
    text = "" if val is None else _one_line(str(val))
    if key == "command" and len(text) > COMMAND_MAX_CHARS:
        text = text[:COMMAND_MAX_CHARS] + "…"
    if not text:
        return ""
    return _zh_param(key, text)


def render_line(item: Dict[str, Any]) -> str:
    """单个 item → 一句人话（顺序固定：工具名 中文名 参数 结果短句 耗时；参数遵 D9）— 小欧 2026-10-12"""
    tool = str(item.get("tool") or "")
    tool_zh = str(item.get("tool_zh") or "")
    parts = [tool]
    if tool_zh and tool_zh != tool:
        parts.append(tool_zh)
    params = item.get("params") or {}
    shown = []
    seen_path = False
    dup_skip = MSG_DUP_KEYS.get(tool, frozenset())
    has_path = "path" in params and params.get("path") not in (None, "")
    for key, val in params.items():
        if key in dup_skip:
            continue  # message 已含该参数, 句子跳过, content_items 保留 — 小欧 2026-10-12
        if key == "dest" and has_path:
            continue  # 有 path 时 dest 不进句子, 只留一个路径信息; content_items 照旧全留 — 小欧 2026-10-12
        text = "" if val is None else _one_line(str(val))
        if key in PATH_LIKE:
            if seen_path:
                continue
            seen_path = True
            if "/" in text or "\\" in text:
                text = _basename(text)
            if not text:
                continue
            shown.append(text)  # path 类只显示值, 不加键名前缀（D9⑦）
            continue
        frag = _zh_value(key, val)
        if frag:
            shown.append(frag)
    if shown:
        parts.append(" | ".join(shown))
    message = _one_line(item.get("message") or "")
    if message:
        parts.append(message)
    duration = item.get("duration_ms")
    if isinstance(duration, (int, float)) and duration > 0:
        parts.append(f"({duration / 1000:.1f}s)")
    return " ".join(p for p in parts if p)


def build_content_items(tool_result: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """tool_result[] → content_items 对象数组（唯一真身）。纯函数, 不抛异常 — 小欧 2026-10-12"""
    items: List[Dict[str, Any]] = []
    for element in tool_result or []:
        if not isinstance(element, dict):
            continue
        try:
            items.append(_build_item(element))
        except Exception as exc:
            logger.warning("[observation_content] 单元素投影失败已降级: %s: %r",
                           type(exc).__name__, exc)
            items.append({"tool": str(element.get("tool_name") or ""), "tool_zh": "",
                          "exec_code": "unknown", "message": "", "params": {},
                          "duration_ms": 0, "detail": ""})

    for idx in range(len(items) - 1, -1, -1):  # 体积兜底: 只置空 params, 绝不删行（D5）
        if len(json.dumps(items, ensure_ascii=False)) <= CONTENT_MAX_CHARS:
            break
        if items[idx].get("params"):
            items[idx]["params"] = {}
    if len(json.dumps(items, ensure_ascii=False)) > CONTENT_MAX_CHARS:
        logger.warning("[observation_content] content 超 %d 字符且 params 已全部置空: tool_count=%d",
                       CONTENT_MAX_CHARS, len(items))
    return items
