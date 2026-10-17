# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-17 - 小欧 - 拆分: 自 path_1st_legality_check.py 拆出门前初查(precheck_path_legality + _EXISTENCE_PARAMS), 逻辑逐字搬迁不改; 原文件更名 path_legality_router.py(路径层 validate_tool_path)。动因: 同文件合法性/路径层两职混装易被误读(实测已致将整文件当作路径层总入口), 拆分后职责单一。_CONTENT_PARAM_KEYS 两文件共用, 上移 tool_constants.CONTENT_PARAM_KEYS(单源, 禁重复)。
# 2026-10-17 - 小欧 - 本文件历史承接原 path_1st_legality_check.py 门前初查全部条目(逐字搬迁): ①【DRY 下沉】初查原落 safety_gate 编排层, 三份重复改表忘同步即分叉, 收归本模块 ②【BUG 修复·存在性零覆盖】rename 源/edit 被改文件按 WRITE 判会跳过存在检查, _EXISTENCE_PARAMS 单源声明按 EXISTS 查 ③【BUG 修复·取错源】force 先取 normalized_params 再回落原值, params 入口 `or {}` 归一 ④【tool去检查化】纯拼写原子下沉 app.utils.path_utils, UNC 跳过盘符可达性探测, PATH_PARAM_KEYS 补 search_dir/data ⑤2026-10-17 北京老陈裁定: OpCategory/check_path_syntax_and_exists 迁往 path_utils, 三态区分并先过空值原子。
# 2026-10-17 - 小欧 - DUAL_ACTION_PARAMS 改从 tool_constants 导入(表体上移工具层, 与 DUAL_PATH_TOOLS 同层)。
"""
path_precheck — [3] 合法性初查(路径合法性: 第1层格式 + 第2层存在性)

调用链: safety_gate.check_safety_and_confirm → 本模块 precheck_path_legality
        进门即拦(省信任预查/总闸/弹窗); 失败原因交调用方按 denied 处理。
只判"格式 + 是否存在", 不判权限 —— 权限在 path_legality_router 与三线。
判定原子在 app.utils.path_utils(reject_reason_empty_path / check_path_syntax_and_exists / OpCategory)。

小欧 2026-10-17 自 path_1st_legality_check 拆出
"""

import logging
from typing import Any, Dict, Optional

from app.safety import dual_path_check
from app.tools.registry import tool_registry
from app.tools.tool_constants import PATH_PARAM_KEYS, CONTENT_PARAM_KEYS
from app.tools.tools_alias_mapper import normalize_tool_name, normalize_params
from app.utils.path_utils import (
    OpCategory,
    reject_reason_empty_path,
    check_path_syntax_and_exists,
)

logger = logging.getLogger(__name__)

# 2026-10-15 小欧 - 门前初查单源: 这些参数**虽然工具是 write 档**, 但执行期必须存在。
#   rename 的 path(源)/edit 的 path(被改文件)执行期必须存在, 若按 write 档跳过,
#   "前移省弹窗"对这两个工具即完全失效(实测: 源不存在照样走全套安检+弹窗)。
#   改此表 = 改前移范围。新增"write 档但源必须存在"工具必须登记此表, 否则前移 silently 失效。
#   2026-10-16 小欧 - tool去检查化后本模块是唯一合法性检查点, 此表权威性不变。
_EXISTENCE_PARAMS: Dict[str, set] = {
    "rename": {"path"},
    "edit": {"path"},
}


def precheck_path_legality(tool_name: str, params: Dict[str, Any]) -> Optional[str]:
    """[3] 合法性初查: 第1层格式 + 第2层存在性 — 小欧 2026-10-15
    上游 [2] 处理范围门(仅 PATH_TOOLS 到此); 命中即拦, 省 [4] 总闸/[5] 弹窗; 失败原因交调用方按 denied 处理。
    只取"是否存在", 警告层(第3层)完全不跑 —— 门前参数不全(content/recursive/overwrite 等),
    且警告要贴近执行才有意义。执行期工具内 validate_path 原样全跑(第2层复查防 TOCTOU + 第3层警告)。

    op 知识与本文件同源: 单动作读/删 → EXISTS; write → WRITE(跳过存在) + _EXISTENCE_PARAMS
    补"write 档但源必须存在"的两个工具; dual 按 DUAL_ACTION_PARAMS 逐参数分 op。
    读档用 EXISTS 而非 READ_FILE/LIST_DIR: 单动作 read 兼文件与目录, EXISTS 是唯一公分母
    (本模块是唯一合法性检查点, 宁可口径宽一格由执行期自然失败, 不可误杀合法目录/文件)。

    返回 None = 通过(或不归本层管, 由 path_legality_router 裁决); 返回 str = 失败原因。
    """
    params = params or {}
    try:
        normal_name = normalize_tool_name(tool_name)
        # bash 是命令通道(走 shell_path_check.check_shell_permission), 本层不查文件路径
        if normal_name == "bash":
            return None
        # 2026-10-17 小欧 - 未注册/范围已在上游判, 本层恒拿到已注册路径工具 meta, 不再复判。
        meta = tool_registry.get_tool(normal_name)
        normalized_params, _ = normalize_params(normal_name, params)
        must_exist_keys = _EXISTENCE_PARAMS.get(normal_name, set())
        force = bool(normalized_params.get("force", params.get("force", False)))

        if meta.action_kind == "dual":
            from app.tools.tool_constants import DUAL_ACTION_PARAMS
            param_map = DUAL_ACTION_PARAMS.get(normal_name)
            if param_map is None:
                return None                                            # 表外交总闸 fail-closed
            for key, action in param_map.items():
                # 2026-10-17 北京老陈裁定(补到本层): 三态区分(没传/非法值/合法 str); 空值交底层原子 reject_reason_empty_path 判,
                #   原 `if value is None: continue` 把"没传"与"显式传 None"混同, 会放行到执行期崩栈。
                if key not in normalized_params:
                    continue                                # 真没传
                value = normalized_params[key]
                if key in CONTENT_PARAM_KEYS and not isinstance(value, str):
                    continue                            # data 内容型参数: 内联结构非路径
                if isinstance(value, str):
                    value = dual_path_check.resolve_path_param(
                        normal_name, key, value, normalized_params)
                real_path = value
                if action == "read":
                    op = OpCategory.EXISTS
                elif action == "delete":
                    op = OpCategory.EXISTS
                else:
                    op = OpCategory.WRITE                              # 写目标只查格式
                    if key in must_exist_keys:
                        op = OpCategory.EXISTS
                # 空值交底层原子(唯一真源), 不在本层重复实现
                _empty = reject_reason_empty_path(real_path)
                if _empty:
                    return _empty
                ok, err = check_path_syntax_and_exists(op, real_path, force=force)
                if not ok:
                    return err
            return None

        if meta.action_kind == "read":
            op = OpCategory.EXISTS
        elif meta.action_kind == "delete":
            op = OpCategory.EXISTS
        elif meta.action_kind == "write":
            op = OpCategory.WRITE
        else:
            return None                                                # 未知档位交总闸 fail-closed
        for key in PATH_PARAM_KEYS:
            if key not in normalized_params:
                continue                                    # 真没传(不得用 get(key) is None 判, 见 dual 分支裁定)
            value = normalized_params[key]
            if key in CONTENT_PARAM_KEYS and not isinstance(value, str):
                continue                                # data 内容型参数: 内联结构非路径
            # 空值交底层原子(唯一真源)
            _empty = reject_reason_empty_path(value)
            if _empty:
                return _empty
            if isinstance(value, str):
                value = dual_path_check.resolve_path_param(
                    normal_name, key, value, normalized_params)
            this_op = OpCategory.EXISTS if key in must_exist_keys else op
            ok, err = check_path_syntax_and_exists(this_op, value, force=force)
            if not ok:
                return err
        return None
    except Exception as e:
        logger.warning("[path_precheck] 门前初查自身异常, 已放行交总闸兜底: %s", e)
        return None                                                    # 初查自身异常不拦路: 总闸+执行期两道还在


__all__ = ["precheck_path_legality"]
