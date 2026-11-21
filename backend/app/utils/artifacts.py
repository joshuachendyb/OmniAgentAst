# -*- coding: utf-8 -*-
"""产物条目唯一契约模块 — 小欧 2026-11-21

产物清单的唯一字段定义、唯一规范化、唯一去重、唯一存在性判定。
声明端(产出工具)、收集端(agent_telemetry)、读口(storage)、前端类型全部以此为准,
任何模块不得再自行解释条目字段。

字段契约(五字段):
  tool_name  工具名          —— 收集器注入, 生产者不填
  name       展示名          —— 本地取 basename; 目录取目录名; URL 取末段文件名
  path       资源地址        —— 本地绝对路径 或 http(s) URL, 唯一地址字段
  form       形态            —— file / dir / url, 唯一形态字段
  type       展示类型        —— 扩展名(小写无点) / dir / 媒体类别 / file / url

编辑历史:
2026-11-21 - 小欧 - 新建: 产物声明契约从 tool_response 三函数迁出, 落点由
  llm_data.action 改为 other_data["artifacts"]; 补 form 形态维度, type 收敛为单条
  规则, 去重键统一(URL 去签名参数/本地 normcase+abspath), 上限保留最新并告警。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import unquote, urlsplit

logger = logging.getLogger(__name__)

MAX_ARTIFACTS = 50

FORM_FILE = "file"
FORM_DIR = "dir"
FORM_URL = "url"
_FORMS = (FORM_FILE, FORM_DIR, FORM_URL)
_HTTP_PREFIXES = ("http://", "https://")


def _is_url(path: str) -> bool:
    return path.lower().startswith(_HTTP_PREFIXES)


def _ext_of(path: str) -> str:
    """小写无点扩展名; 无扩展名返回空串。"""
    base = os.path.basename(str(path or "").rstrip("\\/"))
    head, dot, ext = base.rpartition(".")
    if not dot or not head or not ext:
        return ""
    return ext.lower()


def _url_basename(url: str) -> str:
    """URL 末段文件名(去 query/fragment 并解码), 无则空串。"""
    try:
        path = urlsplit(url).path
    except ValueError:
        return ""
    return unquote(path.rsplit("/", 1)[-1]).strip()


def normalize_artifact(raw: Any) -> Optional[Dict[str, str]]:
    """任意来源条目 -> 五字段标准条目; 不可成立返回 None。

    幂等: normalize(normalize(x)) == normalize(x)。
    form 已存在则信任, 不重新探测磁盘 —— 产物声明时形态是确定的, 读口按磁盘现状
    重判会让"文件被删"把 dir 误降成 file, 历史数据必须形态稳定。
    """
    if not isinstance(raw, dict):
        return None
    path = str(raw.get("path") or "").strip()
    if not path:
        return None

    form = str(raw.get("form") or "").strip().lower()
    if form not in _FORMS:
        if _is_url(path):
            form = FORM_URL
        elif os.path.isdir(path):
            form = FORM_DIR
        else:
            form = FORM_FILE

    raw_type = str(raw.get("type") or "").strip()
    if form == FORM_URL:
        name = str(raw.get("name") or "").strip() or _url_basename(path)
        type_ = _ext_of(name) or raw_type or FORM_URL
    elif form == FORM_DIR:
        name = str(raw.get("name") or "").strip() or os.path.basename(path.rstrip("\\/")) or path
        type_ = FORM_DIR
    else:
        name = str(raw.get("name") or "").strip() or os.path.basename(path)
        type_ = _ext_of(name) or _ext_of(path) or FORM_FILE

    return {
        "tool_name": str(raw.get("tool_name") or ""),
        "name": name,
        "path": path,
        "form": form,
        "type": type_,
    }


def artifact_dedup_key(item: Dict[str, Any]) -> str:
    """去重键: 形态 + 去签名资源地址。

    URL 去 query/fragment —— 同一资源换签名参数仍是同一条;
    本地 normcase+abspath —— Windows 大小写不敏感, 相对路径归一到绝对。
    """
    form = str(item.get("form") or FORM_FILE)
    path = str(item.get("path") or "")
    if form == FORM_URL:
        try:
            parts = urlsplit(path)
        except ValueError:
            return f"{FORM_URL}:{path}"
        return f"{FORM_URL}:{parts.scheme.lower()}://{parts.netloc.lower()}{parts.path}"
    return f"{form}:{os.path.normcase(os.path.abspath(path))}"


def artifact_exists(item: Dict[str, Any]) -> bool:
    """产物是否仍可达: url 不做网络探测(抽屉渲染不能打外网请求); dir 用 isdir; file 用 isfile。"""
    form = str(item.get("form") or FORM_FILE)
    path = str(item.get("path") or "")
    if form == FORM_URL:
        return bool(path)
    if form == FORM_DIR:
        return os.path.isdir(path)
    return os.path.isfile(path)


def artifact_from_file(path: str, name: str = "") -> Dict[str, str]:
    """本地文件/目录 -> 标准条目(form 按磁盘实况: 目录 dir, 其余 file)。"""
    p = str(path or "").strip()
    item = normalize_artifact({
        "name": name,
        "path": p,
        "form": FORM_DIR if os.path.isdir(p) else FORM_FILE,
    })
    return item or {}


def artifact_from_url(url: str, kind: str = "") -> Dict[str, str]:
    """公网产物 URL -> 标准条目(name 取末段文件名, type 取后缀, 认不出用 kind)。"""
    u = str(url or "").strip()
    item = normalize_artifact({
        "name": "",
        "path": u,
        "form": FORM_URL,
        "type": _ext_of(_url_basename(u)) or str(kind or "").strip(),
    })
    return item or {}


def merge_artifacts(existing: Optional[List[Any]],
                    new_items: Optional[List[Any]]) -> List[Dict[str, str]]:
    """唯一合并入口: 规范化 + 按去重键合并(后到覆盖先到) + 保留最新 MAX_ARTIFACTS 条。

    超限丢最早而非最新 —— 长任务末尾产出的文件才是用户最关心的。
    """
    out: List[Dict[str, str]] = []
    index: Dict[str, int] = {}
    for raw in list(existing or []) + list(new_items or []):
        item = normalize_artifact(raw)
        if item is None:
            continue
        key = artifact_dedup_key(item)
        pos = index.get(key)
        if pos is None:
            index[key] = len(out)
            out.append(item)
        else:
            out[pos] = item
    if len(out) > MAX_ARTIFACTS:
        dropped = len(out) - MAX_ARTIFACTS
        out = out[-MAX_ARTIFACTS:]
        logger.warning("[artifacts] 条目超过 %d 条, 丢弃最早 %d 条", MAX_ARTIFACTS, dropped)
    return out


def declare_artifacts(other_data: Optional[Dict[str, Any]],
                      items: List[Any]) -> Dict[str, Any]:
    """声明入口(基座): 产物条目挂 other_data['artifacts'], 追加语义, 不改入参。"""
    other: Dict[str, Any] = dict(other_data or {})
    other["artifacts"] = merge_artifacts(other.get("artifacts"), items)
    return other


def declare_artifact_file(other_data: Optional[Dict[str, Any]],
                          file_path: str) -> Dict[str, Any]:
    """声明入口(便捷): 由本地路径声明单个产物。"""
    return declare_artifacts(other_data, [artifact_from_file(file_path)])


def read_declared_artifacts(result: Any) -> List[Dict[str, str]]:
    """读取口: 从工具返回体取已声明产物并规范化(收集器专用)。"""
    if not isinstance(result, dict):
        return []
    other = result.get("other_data")
    if not isinstance(other, dict):
        return []
    return merge_artifacts([], other.get("artifacts"))
