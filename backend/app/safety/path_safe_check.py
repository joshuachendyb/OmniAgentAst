# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 - 小欧 - 修复: 白名单盘符下增加系统保护目录拒绝(windows/program files/programdata等),
#    用 Path.parts[1] 精确只查盘符后第一级, 避免 C:\Users\MyProject\Program Files 误杀
# 2026-08-02 - 小欧 - 加固: _is_forbidden_path 新增磁盘根目录黑名单(C:\), 防止白名单盘符机制放行盘根删除
# 2026-08-04 - 小欧 - 盘符动态化(北京老陈驱动): 新增 get_existing_drives(当前磁盘符号列表)/get_system_drive(真实系统盘符)/_get_project_root_safety(项目根上移Safety层,恒非None);
#    _is_forbidden_path 系统目录 C: 模板运行时动态替换真实系统盘符(不漏判不误伤); get_default_allowed_paths 盘符枚举 A-J 上限改动态(get_existing_drives) — 设计文档 v1.15
# 2026-08-10 - 小欧 - 步骤1实施(⑤⑦⑧⑨⑪, 北京老陈驱动「项目根=tool工作区, 代码库根=tool禁区」): ⑤get_project_root_safety收敛走config(兜底用户主目录); ⑦代码库根_unsafe_get_code_root_roots为禁区(含父子级); ⑧工具路径参数名补dest列表; ⑨validate_tool_path遍历所有命中参数逐一校验; ⑪废除「所有现存盘符」全盘放开, 白名单=主目录+tmp+项目根+授权目录(动态懒加载)
# 2026-08-10 - 小欧 - BUG-B/C修复: 新增 _resolve_path_param 逻辑路径参数解析(download.dest=相对下载目录/rename.dest=仅文件名→真实文件系统路径),
#    validate_tool_path 校验前先解析, 消除"相对/文件名语义被当绝对路径校验→resolve到cwd→误判代码库禁区拦截"(download/rename完全不可用);
#    validate_tool_path 返回扩展为三元组 (is_valid, msg, failed_path), failed_path=首个校验失败的真实路径, 供临时授权定位真正越权参数(BUG-D修复) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - 缺陷修复(三堂会审复核发现, 第二次代码更新): _SYSTEM_PROTECTED 系统保护目录(windows/program files等)
#   写/删 返回 category 由 None → "system" — _is_forbidden_path 仅精确锁 WIN_EXACT 本身(C:\Windows), 其子路径漏过禁区判定,
#   旧返回 None 使 T2 当"白名单外可临时授权"处理(系统目录可被授权写入, 违表五「系统禁区写❌硬拦永不授权」); 读 mode 放行(与禁区读一致, 3.2.9)
# 2026-08-10 - 小欧 - 三堂会审修复(v1.45):
#   归属判定缺陷: validate_tool_path 原 `tool_name not in path_tools` 用 LLM 原始名判归属, 别名工具(list_directory/read_text_file等)
#     不在注册名集合 → 直接 return True 放行, 绕过全部路径校验; 改归一化名 normal_name 判(与 mode 推断同源, 防别名漏检补齐)
#   参数别名缺陷: 原 hit_params 直接查原始 params, PARAM_ALIASES 参数别名(rename.new_name→dest/copy.src→path/dst→dest等)
#     命中不了 PATH_PARAM_KEYS → 该参数路径越权漏检; 校验前先 normalize_params 归一化(校验对象与工具实际落盘路径一致)
#   _resolve_path_param 同步改用归一化名+归一化 params(download/rename 相对语义解析不受别名影响) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - T2 回归修复(三堂会审+回归测试复核发现, v1.45): 空路径/路径穿越返回 category 由 None → "system" —
#   validate_path 对空路径/穿越返回 (False, msg, None), T2 将 category=None 一律当"白名单外非禁区→可授权请求",
#   使空路径/穿越从 blocked 退化为可授权(违"无效/恶意路径应硬拦"); 归入 system 后 T2 硬拦永不授权,
#   与 test_bug_empty_path_not_validated / test_f5_03_path_traversal_blocked 断言对齐 — 小欧 2026-08-10
# 2026-08-11 - 小欧 - fix D1: validate_path 末段except分支 category=None→"system"(永不授权硬拦),
#   原category=None→T2当"白名单外非禁区→可授权请求"→异常/恶意路径可被grant_temp_auth放行(安全漏洞);
#   与同文件_is_forbidden_path异常返回"system"(L197-199)/空路径"system"(L230)/穿越"system"(L259)/校验异常"system"(L267)/系统保护"system"(L288)一致 — 小欧 2026-08-11
# 2026-08-11 - 小欧 - fix D1残留(实证补充, task005报告核验发现): validate_tool_path 自身兜底except分支 category=None→"system"(永不授权硬拦),
#   原返回 (False, "路径安全检查异常", None, None) — category=None → T2 当"白名单外非禁区→可授权请求"(requires_confirmation+auth_path),
#   异常/恶意路径理论上仍可被临时授权放行(与D1同源隐患); 归入"system"后 T2 硬拦永不授权, 与 validate_path 各异常分支"system"口径全链一致 — 小欧 2026-08-11
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1 迁移(盲点五定案): 本文件由 app/safety/path_safe_check.py 整体复制迁入 app/tools/security/(移动,
#   业务逻辑一字不改); 原 app.safety.temp_auth 惰性导入改 app.tools.security.temp_auth(同包内互引); 原编辑历史按规范保留。
# 2026-08-13 - 小沈 - 修复(三堂会审): validate_tool_path 遍历命中路径参数时, compress/extract/copy/move 的 src 参数
#   语义是读, 原统一用工具级 mode=write 对 src 做写校验, 白名单外 src 被要求临时授权(误拦合法读源);
#   按参数名分别推断 mode: src/source_path→read, 其余沿用工具级 mode, 增强不退化
# 2026-08-13 - 小欧 - 三堂会审修复#24: 删除死常量 ALLOWED_PATHS(合规/DRY)
#   【病根】ALLOWED_PATHS=get_default_allowed_paths() 模块级导入时计算, 仅被__all__导出(L458), 逻辑层从未引用(validate_path每次重调函数),
#     既死代码又有"配置变更后陈旧白名单"潜在风险(file_register.py:4注释亦证移除意图)
#   【改法】删除L129常量定义及__all__导出; get_default_allowed_paths 函数保留(逻辑在用), 无任何引用方依赖该常量(grep全仓仅注释/__all__)
# 2026-09-02 - 小欧 - 提示文案"准确+可读"优化(北京老陈驱动「提示文字看不懂」): 本文件返回的 msg(定位路径落区, 作
#   tool_safety_checker 用户 message 的拼接尾部)由黑话改"术语+人话"——代码库根:「路径位于受保护区域(项目代码库)」;
#   系统敏感文件/目录:「路径位于系统禁区(敏感文件/敏感目录)」; 异常:「路径安全检查异常,已拒绝访问」;
#   与前缀「该路径在受保护区域/系统禁区...」拼读通顺且保留禁区分级定位; 仅改文案不改逻辑(category 判定/hard-block 不变), 测试不断言文案, 逻辑零退化
# 2026-10-02 - 小欧 - 注册名归位: _READ_ONLY_TOOLS 文本项 read→read, 删重复的 "read" 项(合并为一条)
# 2026-10-06 - 小欧 - 去硬编码盘符(北京老陈驱动): ①import 改 FORBIDDEN_PATHS_WINDOWS_REL_EXACT/_REL_PREFIX,
#   Windows 禁用路径改为盘符前置拼接(get_system_drive() + 相对段), 去掉 .replace("C:", ...) 字符串替换
#   (旧写法一旦某条漏写盘符前缀, startswith("C:") 守卫会静默不替换→真漏拦); ②get_system_drive 的兜底值
#   收口为模块内常量 FALLBACK_SYSTEM_DRIVE(原先 3 处散落); ③_SYSTEM_PROTECTED 改用 tool_constants 的
#   SYSTEM_PROTECTED_DIR_NAMES(原先定义在 validate_path 函数体内, 每次调用重建 frozenset, 且展示层拿不到)。
# 2026-10-14 - 小欧 - bash 写目标纳入路径权限: validate_tool_path 早退前加 bash 分支, 抽命令内绝对路径
#   (_extract_abs_win_paths, 引号优先保空格)交既有 validate_path, 复用下游 system/non_system 分流。
#   病根: bash 属 FUNDAMENTAL 不在 PATH_CATEGORIES, 实测 del/Remove-Item/echo> C:\Windows\a.txt
#   在路径层与 shell 危险模式层双双放行, 与"禁止绕路用shell逃避安全检查"相悖。不解析 shell 语法。
# 2026-10-14 - 小欧 - 同日三堂会审: 修2个误报+补1个缺口+补log
#   ① 引号路径被裸正则再截断成 `E:\my` → 已授权含空格目录 `E:\my proj` 被误拦且 failed_path 报错路径;
#      改 _extract_abs_win_paths: 引号区先完整取出, 裸路径只在引号区之外扫描
#   ② 只读命令因模式里含动词字面量被误判写意图(`Select-String -Pattern "del" <路径>`);
#      判写意图改用剥引号后文本(_strip_quoted), 抽路径仍用原文(需保住含空格完整路径);
#      重定向判据改为剥引号后是否含 ">", 不用 _REDIRECT_RE(其职责是提取目标, 需保留引号)
#   ③ `$env:VAR\path` 抽不到路径 → 复用 executor 的 _resolve_env_fragment 先展开
#   ④ 违规补 warning log: 下游只记 tool=bash 缺命令原文, 安全事件查不到是哪个命令
# 2026-10-14 - 小欧 - 系统保护目录判定收归 _is_forbidden_path: 原在 validate_path 内, 而 temp_auth
#   授权守卫调 _is_forbidden_path, 两处口径不同致 C:\system32 等被 grant_temp_auth 记入授权库。
# 2026-10-14 - 小欧 - SA5标注: 本文件=权限信任框架SA5(路径权限validate_tool_path→validate_path→_is_forbidden_path系统区/非系统区/白名单,执行第5步,由SA3经_check_known_risks内调,读SA6授权is_temp_authorized) — 小欧-2026-10-14
# 2026-10-14 - 小欧 - 文档[33] 4.11-A/4.11-B/4.12-B: 4 张分类表迁 tool_constants; _QUOTED_SPAN_RE/_strip_quoted/_ABS_WIN_PATH_RES/_extract_abs_win_paths 迁 shell_static_guard(还 _QUOTED_SPAN_RE 双源债, 并消除对 executor 的越层延迟导入即架构守护红项1); is_system_protected_path 与 SYSTEM_PROTECTED_DIR_NAMES 迁 app/utils/path_utils.py
# 2026-10-14 - 小欧 - 文档[33] 4.1: 本文件由 app/tools/security/ 整文件复制升回 app/safety/(业务逻辑一字不改); 包内互引 2 处(:322/:379)由 app.tools.security.temp_auth 改同包 app.safety.temp_auth。
# 2026-10-14 小欧 - 文档[33] 4.10-1/步12: _validate_shell_write_targets 按 _DELETE_CMD_RE 命中取 mode=delete(删系统禁区由「可授权的写」降为永不授权); 补 _DELETE_CMD_RE import。
# 2026-10-15 - 小欧 - 文档[33] 5.3 核查订正两项:
#   ① 4 张分类表导入改用去私前缀名 PATH_CATEGORIES/PATH_PARAM_KEYS/READ_ONLY_TOOLS(5.3 L809 明文要求, 4.11-B 实施漏改); 调用点 3 处同步。
#   ② __all__ 删死条目 "_READ_ONLY_TOOLS": 该表已迁 tool_constants, 全仓 4 个消费方
#      (delete_safety/temp_auth/tool_safety_checker/workspace_service) 无一从本模块导入, 属 backward 再导出, 违 AGENTS 1.2 禁 backward。
#   判定逻辑零改动。— 小欧-2026-10-15
# 2026-10-15 - 小欧 - 文档[33] 5.6 核查订正: shell_static_guard 导入删死符号 _ABS_WIN_PATH_RES/_QUOTED_SPAN_RE。
#   两者迁入后在本模块无任何代码引用(AST 实证: 仅存于历史/说明注释), 纯 YAGNI 冗余导入;
#   设计 5.6 的 import 清单本就只列 5 个符号, 此处系实施多导。— 小欧-2026-10-15
# 2026-10-14 北京老陈裁定(全局收敛) - 本层为目录权限**唯一决策者**: 磁盘根/系统目录判定改调 utils 单源;
#   新增受保护根(B族)判定 → 此前只有 delete 拦它、写入不拦, 同一类别待遇随层而变。mode 透传单源, 本层不自行解释。
# 2026-10-15 北京老陈裁定(DRY) - get_default_allowed_paths 内的根集合拼装改为单源 path_utils.get_allowed_roots:
#   原内联三段(config 项目根+授权目录+会话快照)与 delete_safety/_get_protected_roots 三处重复, .resolve() 用法还各不相同。
# 2026-10-15 北京老陈裁定(分层去反向依赖) - 会话工作区快照改由本层传入 path_utils.get_allowed_roots(extra_roots):
#   快照原由 utils 直接 import app.tools.context 取, 构成「utils 反向依赖上层」(守护测试红)。
#   取数收归 app/tools/context.py 的 session_workspace_paths(), 由 safety/tools 各自传入 —— 二者均可 import tools(铁律只禁 tools→services/safety),
#   故 B 族保护范围【零损失】, 仅解开 utils 的分层依赖。
#
# 2026-10-15 北京老陈裁定 - 文档[35] 三线物理分离(阶段一) 本文件瘦身, 只保留两类职责:
#   ① 禁区分类内核 _is_forbidden_path —— 读/写/删三线共同调用, 按各自 mode 判定
#   ② 磁盘枚举与白名单构建 get_existing_drives/get_system_drive/get_default_allowed_paths/_get_project_root_safety
#      (阶段四迁往 path_scope.py, 本阶段暂留)
#   迁出四块(逐字搬迁, 业务逻辑一字不改, 仅改 import 路径):
#     validate_path(含 mode 参数) → **彻底删除**, 三线各自独立(删/写/读_path_check.py), 不留转发壳(总则四 禁止 backward)
#     公共步骤(空路径/穿越/白名单匹配) → path_check_common.py
#     _resolve_path_param + validate_tool_path + bash 通道 → path_check_entry.py
#     _validate_shell_write_targets + 6 复合工具声明表 → multi_path_check.py
#   禁区分类未迁入 path_check_common: 它按 mode 决定读放行/写删拦, 三线传入的 mode 不同, 故三线各自直调本模块。
"""
path_safe_check — 路径禁区分类内核 + 磁盘与白名单枚举

本文件瘦身后的职责(文档[35] 阶段一):

  一、禁区分类内核
     _is_forbidden_path(file_path, mode) — 判断路径属于哪一类禁区
       category ∈ {"system", "non_system", None}
         "system"    系统敏感文件/目录 + 磁盘根 + 系统保护目录
                     → 写/删永不授权; 读放行(内容敏感性交内容过滤兜底)
         "non_system" 代码库根及父子级 + 受保护根及上级
                     → 写可任务级授权, 删硬拦
         None        非禁区(白名单外 · 非禁区)

     读、写、删三条线各自直接调用本函数并传自己的固定 mode:
       read_path_check  → mode="read"
       write_path_check → mode="write"
       delete_path_check→ mode="delete"

  二、磁盘枚举与白名单构建(阶段四迁往 path_scope.py)
     get_existing_drives / get_system_drive / get_default_allowed_paths / _get_project_root_safety

已迁出的部分见文件头最后一条编辑历史。本模块不再被工具层直接 import —
工具层硬底线走 app.safety.path_guard(纯路径属性判定, 不依赖任何开关)。

九格契约表 —— 读/写/删 三条线 × 各类区域(**全链单一真源, 改一格三线皆知**)

  区域                 读(read)       写(write)          删(delete)
  ─────────────────────────────────────────────────────────────────────
  系统禁区 system       放行           硬拦 永不授权      硬拦 永不授权
  受保护区 non_system   放行           查任务级授权       硬拦 永不授权
  白名单外 None         放行           查任务级授权       查任务级授权
  ─────────────────────────────────────────────────────────────────────
  磁盘根 C:/             放行           硬拦 永不授权      硬拦 永不授权
  代码库根及父子级      放行           查任务级授权       硬拦 永不授权
  受保护根及上级        放行           查任务级授权       硬拦 永不授权
  ─────────────────────────────────────────────────────────────────────
  空路径 / 含 ..        硬拦           硬拦 永不授权      硬拦 永不授权
  任何异常              硬拦           硬拦 永不授权      硬拦 永不授权

  规则:
  ① 硬拦项 category 恒为 "system", T2 永不授权。
  ② 读线对系统目录与白名单外一律放行 —— 读不写盘无副作用, 内容敏感性由 contentFilter 兜底。
  ③ 写线只有"系统禁区"与磁盘根无授权分支, 其余越权可申请任务级授权。
  ④ 删线在**所有禁区**无授权分支(删不可逆), 仅白名单外可申请授权。
  ⑤ 另有一层更深防线在工作区边界(R6 禁删工作区外递归), 不在本表范围, 由 delete_safety 承担。

  各线的独有策略实现见: read_path_check / write_path_check / delete_path_check
  公共判定步骤见: path_check_common   路径属性判定见: path_guard   可用范围见: path_scope

小沈 2026-06-17 / 小健 2026-06-23 / 小欧 2026-07-04 起
小欧 2026-10-15 三线分离后定稿
"""

import os
from pathlib import Path
from typing import Optional, Tuple

# 2026-10-15 小欧 - 文档[35] 阶段四: 磁盘枚举与白名单构建迁 path_scope, 本模块只留禁区分类内核
from app.safety.path_scope import get_system_drive
from app.tools.tool_constants import (
    FORBIDDEN_PATHS_EXACT,
    FORBIDDEN_PATHS_PREFIX,
    FORBIDDEN_PATHS_WINDOWS_REL_EXACT,
    FORBIDDEN_PATHS_WINDOWS_REL_PREFIX,
)
# 2026-10-14 北京老陈裁定(分层去反向依赖): 会话工作区取数收归 app/tools/context.py, 由本层传入 utils 单源。
#   必须【模块级】导入 —— _is_forbidden_path 与 get_default_allowed_paths 两处都要用,
#   只写在后者函数内会导致前者 NameError, 而 fail-closed 会把它伪装成"system 已拒绝"(实测全盘误拒, 极隐蔽)。
from app.tools.context import session_workspace_paths
# 2026-10-14 小欧 - 文档[33] 4.12-B: 系统目录判定单一真源, 阶段五随 is_system_protected_path 迁往 app.safety.path_guard
from app.safety.path_guard import (
    SYSTEM_PROTECTED_DIR_NAMES,
    is_code_root_path,
    is_disk_root,
    is_protected_root_itself,
    is_system_protected_path,
)

def _is_forbidden_path(file_path: str, mode: str = "write") -> Tuple[Optional[str], Optional[str]]:
    """检查路径是否在系统敏感路径黑名单中 — 小健 2026-06-23
    扩展 (v1.43 修正): 返回值扩展为禁区类别(category, msg)

    Args:
        file_path: 待检查路径
        mode: 操作类型('read'/'write'/'delete') — 由调用方(读线/写线/删线)传入固定值,
              本函数不自行解释: 系统保护目录的放行与否已在 is_system_protected_path 内收口

    Returns:
        (category, error_message) — category ∈ {"system", "non_system", None}:
            "system" = 系统敏感目录+磁盘根(3.2.8 第1-5类, 写/删永不授权)
            "non_system" = 代码库根及父子级(3.2.8 第6类, 写可任务级授权, 删硬拦)
            None = 非禁区(白名单外·非禁区)
    """
    try:
        real_path = Path(os.path.realpath(os.path.expanduser(file_path)))
        real_path_str = str(real_path)
        real_path_lower = real_path_str.lower()

        # 磁盘根目录(C:\)黑名单 — 白名单盘符机制允许盘根操作, 此处硬阻断 — 小欧 2026-08-02
        # 判定单源 utils.is_disk_root, 各层只调用(小欧 2026-10-14 归一)
        if is_disk_root(file_path):
            return "system", f"禁止访问磁盘根目录: {file_path}"

        if os.name == 'nt':
            sys_drive = get_system_drive()  # 真实系统盘符 — 小欧 2026-08-04
            # 2026-10-06 小欧 - 常量改相对段, 盘符前置拼接, 去字符串替换
            for forbidden in FORBIDDEN_PATHS_WINDOWS_REL_EXACT:
                _f = sys_drive + forbidden
                if real_path_lower == _f.lower():
                    return "system", f"路径位于系统禁区(敏感文件): {file_path}"
            for forbidden_prefix in FORBIDDEN_PATHS_WINDOWS_REL_PREFIX:
                _f = sys_drive + forbidden_prefix
                if real_path_lower.startswith(_f.lower()):
                    return "system", f"路径位于系统禁区(敏感目录): {file_path}"
            # 2026-10-14 小欧: 系统目录判定走单源 is_system_protected_path(检测+策略同在函数内), 本层只透传 mode
            #   不再自行解释其返回值, 否则与硬底线会给出相反结论(实测读: 安全层放行/工具层拒绝)
            if is_system_protected_path(file_path, mode):
                return "system", f"路径位于系统保护目录,禁止操作: {file_path}"

        # ⑦ 代码库根禁区(tool禁区, 开关无关硬拦截): 代码库根及其子/父级全部禁止 — 小欧 2026-08-10
        # 代码库根属非系统禁区(non_system) — 判定单源 utils.is_code_root_path
        if is_code_root_path(file_path):
            return "non_system", f"路径位于受保护区域(项目代码库): {file_path}"

        # 2026-10-14 北京老陈裁定: 受保护根(项目根/授权目录)及其上级归本层判(B族可授权),
        #   此前只有删除防线拦它、写入不拦 —— 同一类别待遇随层而变, 现统一由权限层决策
        if is_protected_root_itself(file_path, session_workspace_paths()):
            return "non_system", f"路径位于受保护区域(受保护根): {file_path}"

        for forbidden in FORBIDDEN_PATHS_EXACT:
            if real_path_str == forbidden:
                return "system", f"路径位于系统禁区(敏感文件): {file_path}"
        for forbidden_prefix in FORBIDDEN_PATHS_PREFIX:
            if real_path_str.startswith(forbidden_prefix):
                return "system", f"路径位于系统禁区(敏感目录): {file_path}"

        return None, None
    except Exception as e:
        # 【修复】异常时拒绝访问而非放行 — chendyg 2026-06-26
        # 异常判定为system禁区(硬拦永不授权)
        return "system", f"路径安全检查异常,已拒绝访问: {file_path} ({e})"


__all__ = ["_is_forbidden_path"]