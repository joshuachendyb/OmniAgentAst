# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-17 - 小欧 - 拆分: 自 path_1st_legality_check.py 拆出门前初查(precheck_path_legality + _EXISTENCE_PARAMS), 逻辑逐字搬迁不改; 原文件更名 path_legality_router.py(路径层 validate_tool_path)。动因: 同文件合法性/路径层两职混装易被误读(实测已致将整文件当作路径层总入口), 拆分后职责单一。_CONTENT_PARAM_KEYS 两文件共用, 上移 tool_constants.CONTENT_PARAM_KEYS(单源, 禁重复)。
# 2026-10-17 - 小欧 - 本文件历史承接原 path_1st_legality_check.py 门前初查全部条目(逐字搬迁): ①【DRY 下沉】初查原落 safety_gate 编排层, 三份重复改表忘同步即分叉, 收归本模块 ②【BUG 修复·存在性零覆盖】rename 源/edit 被改文件按 WRITE 判会跳过存在检查, _EXISTENCE_PARAMS 单源声明按 EXISTS 查 ③【BUG 修复·取错源】force 先取 normalized_params 再回落原值, params 入口 `or {}` 归一 ④【tool去检查化】纯拼写原子下沉 app.utils.path_utils, UNC 跳过盘符可达性探测, PATH_PARAM_KEYS 补 search_dir/data ⑤2026-10-17: OpCategory/check_path_syntax_and_exists 迁往 path_utils, 三态区分并先过空值原子。
# 2026-10-17 - 小欧 - DUAL_ACTION_PARAMS 改从 tool_constants 导入(表体上移工具层, 与 DUAL_PATH_TOOLS 同层)。
# 2026-10-18 - 小欧 - 参数归一前置: 删 normalize_params 与 PATH_PARAM_KEYS/CONTENT_PARAM_KEYS; 单线直接取 path(缺则 dest),
#   dual 内容守卫改类型判断(data 内联 dict/list 跳过, None 仍交空值原子); force 直接取 params。
# 2026-10-18 - 小欧 - 去存在性: 门前初查只判第1层格式(空值/盘符/保留字符/保留名), 不再判存在性/类型。
#   存在性属运行时前置条件, 本层在所有工具执行之前跑, 同批兄弟产出(如 rename 改名后的新路径)此刻尚未落地, 早判必误拦;
#   存在性改由各工具执行时刻自检(check_path_four_level(EXISTS) / src.exists())。删 _EXISTENCE_PARAMS 与按动作分档的 op, op 恒 WRITE。
"""
path_precheck — [3] 门前合法性初查(仅第1层格式: 空值/盘符/保留字符/保留名)

调用链: safety_gate.check_safety_and_confirm → 本模块 precheck_path_legality
        进门即拦(省信任预查/总闸/弹窗); 失败原因交调用方按 denied 处理。
只判"格式", 不判存在性/类型/权限 —— 存在性由各工具执行时刻自检(本层早于执行, 判之必误拦同批兄弟产出),
权限与禁区在 path_legality_router 与三线。
判定原子在 app.utils.path_utils(reject_reason_empty_path / check_path_syntax_and_exists / OpCategory)。

小欧 2026-10-17 自 path_1st_legality_check 拆出 / 2026-10-18 去存在性
"""

import logging
from typing import Any, Dict, Optional

from app.safety import dual_path_check
from app.tools.registry import tool_registry
from app.tools.tools_alias_mapper import normalize_tool_name
from app.utils.path_utils import (
    OpCategory,
    reject_reason_empty_path,
    check_path_syntax_and_exists,
)

logger = logging.getLogger(__name__)


def precheck_path_legality(tool_name: str, params: Dict[str, Any]) -> Optional[str]:
    """[3] 门前合法性初查: 仅第1层格式(空值/盘符/保留字符/保留名) — 小欧 2026-10-15 建 / 2026-10-18 去存在性
    上游 [2] 处理范围门(仅 PATH_TOOLS 到此); 命中即拦, 省 [4] 总闸/[5] 弹窗; 失败原因交调用方按 denied 处理。

    只判格式, **不判存在性/类型**: 存在性是运行时前置条件, 而本层处于所有工具执行**之前**,
    同批兄弟调用的产出(如 rename 改名后的新路径)此刻尚未落地, 在此早判必误拦合法调用;
    存在性改由各工具在其执行时刻自检(check_path_four_level(EXISTS) / src.exists())。
    权限/禁区/穿越不属本层(由 path_legality_router 与三线判); 警告层(第3层)门前不跑(参数不全且要贴执行)。

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

        # 待查路径参数: dual 按声明表取全部路径键; 单线一调用只有一条路径(path 优先, download/screen_capture 缺则 dest)
        if meta.action_kind == "dual":
            from app.tools.tool_constants import DUAL_ACTION_PARAMS
            param_map = DUAL_ACTION_PARAMS.get(normal_name)
            if param_map is None:
                return None                                            # 表外交总闸 fail-closed
            keys = [k for k in param_map if k in params]
        elif meta.action_kind in ("read", "write", "delete"):
            _key = "path" if "path" in params else "dest"
            keys = [_key] if _key in params else []
        else:
            return None                                                # 未知档位交总闸 fail-closed

        for key in keys:
            value = params[key]
            if value is not None and not isinstance(value, str):
                continue                                # 内容型(如 generate_chart.data 内联 dict/list): 非路径
            # 空值交底层原子(唯一真源); 显式 None 与空串皆在此拦下
            _empty = reject_reason_empty_path(value)
            if _empty:
                return _empty
            real_path = dual_path_check.resolve_path_param(normal_name, key, value, params)
            ok, err = check_path_syntax_and_exists(OpCategory.WRITE, real_path)
            if not ok:
                return err
        return None
    except Exception as e:
        logger.warning("[path_precheck] 门前初查自身异常, 已放行交总闸兜底: %s", e)
        return None                                                    # 初查自身异常不拦路: 总闸+执行期两道还在


__all__ = ["precheck_path_legality"]
