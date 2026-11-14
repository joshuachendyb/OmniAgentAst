# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-07 - 小欧 - 文件由 param_alias_mapper.py 重命名为 tools_alias_mapper.py(名实相符: 既有工具名别名也有参数别名); import处同步更新(registry/tool_retry_engine/action_handler/test)
# 2026-11-04 - 小欧 - edit 增 model→mode 键名别名(日志实证: session 12b317fe 一次 6 条 edit 全废, LLM 把 mode 写成 model)
# 2026-07-20 - 小欧 - 删 output_mode 参数别名映射: grep 已去除 output_mode 参数(默认即 content 模式), 该别名失效, 删除死映射避免误导
# 2026-07-28 - 小欧 - BUG#19: "value":"value"是恒等映射(输入=输出无转换), 空转别名删除
# 2026-08-07 - 小欧 - 新增TOOL_NAME_ALIASES工具名别名映射+normalize_tool_name: LLM常生成变体名(write_text等), 映射到注册名(write), 防"工具未注册"误拦截(com-test 03暴露)
# 2026-08-09 - 小欧 - write_xlsx 参数别名 append→append_mode: LLM 常按布尔语义传 append, 实际实现/SCHEMA参数为 append_mode(2026-08-07 P04优化), 无映射会因未知参数被忽略导致追加失效
# 2026-08-09 - 小欧 - TOOL_NAME_ALIASES 新增 writefile/readfile 幻觉名→write/read: sensenova-flash-lite 将写/读文本工具幻觉为 writefile, 因未注册被安全检查拦截(工具未注册)致任务空转防循环失败; get_tool 归一化后走注册名正常执行, execute_tools 内扩展名纠正再兜底
# 2026-08-09 - 小欧 - TOOL_NAME_ALIASES 新增 writeetext/readetext/editetext(多一个e的拼写幻觉)→write/read/edit: sensenova-flash-lite 将 write 幻觉为 writeetext, 因未注册被拦截致任务尾部空转防循环失败(与 writefile 同源, 拼写变异变体)
# 2026-08-22 - 小欧 - TOOL_NAME_ALIASES 新增裸名 write/read/edit→write/read/edit: 实证 LLM 三轮幻觉调用裸名"write"(最自然通用名), 因不在别名表被拦截, 同名 blocked 达3次触发防死循环熔断致任务 FAILED; 归一化后若扩展名为 .docx/.pdf 等仍由 execute_tools 扩展名预检二次路由, 无歧义风险
# 2026-08-26 - 小欧 - TOOL_NAME_ALIASES 新增 write_content→write: com-test 12(任务007)实证 LLM 幻觉调用 write_content(最自然"写内容"名), 因不在别名表被安全检查以"工具未注册"拦截, 同一工具名 blocked 达3次触发防死循环熔断致任务 FAILED; 归一化后走 write 正常执行(与 writefile/writeetext 同源修复)
# 2026-10-02 - 小欧 - 注册名归位: PARAM_ALIASES 键 shell→bash; TOOL_NAME_ALIASES "bash"→"shell" 反转为 "shell"→"bash"(旧名降级为幻觉名兜底)
# 2026-11-10 - 小欧 - 网关强塞的官方13件套幻觉名收编: websearch→searchweb/glob→find/webfetch→fetchpage(参数逐字兼容; 实证 beam-free 连调 websearch×13 全被拒致19轮死循环); fetchpage.format→extract_format
# 2026-11-10 - 小欧 - 官方5件套禁用名单 UNAVAILABLE_OFFICIAL_TOOLS(question/skill/subagent/patch/execute): 13件套=3收编+5天然命中+5禁用的补集知识, 命中即定性"禁止使用"并点明全组, 防弱模型逐个试错烧轮次
# 2026-11-10 - 小欧 - 勘误: glob→find 非"参数逐字兼容"(上条表述不实)——pattern同名对齐, path官方面可选本系统必填, 缺失走schema校验反馈一轮补齐; 语义映射(文件名通配搜索)正确维持收编
# 2026-11-10 - 小欧 - 禁用名单配置化: UNAVAILABLE_OFFICIAL_TOOLS 降为内置回落默认, 新增 get_disabled_official_tools/is_disabled_tool 读 config tuning.agent.disabled_tools(形状兼容str/list, 键存在即配置为真值——清空=不禁用任何工具不兜底, 仅缺键/异常形状回落内置; get_config热生效, 同shell_readonly先例); 两消费点(handle_action/observation_builder)改经判定函数
# 2026-11-11 - 小欧 - 官方edit签名收编(camelCase): opencli上游OpenCode harness教的键名oldString/newString→
#   old_string/new_string(Pydantic默认忽略extra键, 无别名则old_string必填缺失, opencli模型的edit每条废一轮schema反馈);
#   replaceAll(bool)属跨键映射(true→mode:all/false→删键不设, EditInput缺省即once), 在normalize_params键名映射后特判
# 2026-11-13 - 商量 - 错位参数展开(expand_misplaced_params): LLM幻觉把整个edit对象塞进new_string字段(嵌套dict或XML标签串),
#   外层缺path/old_string致ERR_MISSING_PARAM; 日志实证59次edit中17次失败(29%轮次浪费), 展开后可直接执行省一轮重试;
#   $text→new_string 经PARAM_ALIASES统一映射(无特判); 通用设计: 其他tool有PARAM_ALIASES条目即自动获得展开能力。
#   判据收紧(三堂会审, 反例实证): ①承载错位的字段名本身须是已知参数名(否则 write_xlsx.data 等合法dict参数被误展开);
#   ②XML串须提取出≥2个参数且含自身规范名(否则编辑含 "</path>" 的代码时 new_string 被吞);
#   ③_EXTRA_KNOWN_KEYS 补 edit.replaceAll(不在别名表, 丢则静默只替换首处)
# 2026-11-14 - 商量 - 参数归位(更名自"错位参数展开", 名不符实: 实为把错位包装的参数解析归位到
#   schema 式顶层排布, 不是什么展开): 修重大bug — 原 expanded 从空dict起步+update()无条件覆盖,
#   顶层正确 path 被包装垃圾顶掉(HITL弹窗 path 错乱实证, 且污染信任落库); 改为: 顶层原样起步,
#   归位产物只补缺失键绝不覆盖权威值 + 承载键取解析出的自身规范值(原值是包装本体) +
#   顶层已齐全(schema式正确参数表)整体跳过零改动直返; 归位仍在键名归一化之前(错位形态下归一化
#   无意义), 产物键名经参数表直映规范名, 后续归一化对其幂等, 归一化仍是全参数唯一权威 — 商量-2026-11-14
"""
参数名别名映射 - 解决LLM返回参数名不匹配问题

小欧 2026-06-27

设计原则：
1. 对LLM友好：容错性强，不因参数名错误而失败
2. 对开发者透明：映射逻辑在工具执行前处理
3. 易于维护：别名映射表集中管理
4. 可扩展：支持添加新的别名映射
5. 有日志记录：记录映射情况，便于监控LLM行为
"""

import re
from typing import Any, Dict, Tuple

from app.logger import logger

PARAM_ALIASES = {
    # 路径参数统一为path后,旧规范名(file_path/dir_path/search_dir)降级为别名 — 小欧 2026-07-11
    "read": {
        "file_path": "path",
        "filepath": "path",
        "filePath": "path",  # 驼峰兜底: opencodeZen旧GATE_STUB曾用filePath — 北京老陈 2026-09-24
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    "write": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    "edit": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
        "oldString": "old_string",  # 2026-11-11 小欧: 官方edit camelCase键收编(OpenCode签名, 详见头部编辑历史)
        "newString": "new_string",
        "$text": "new_string",  # 2026-11-13 商量: LLM幻觉键(嵌套dict内$text=替换后文本), 经PARAM_ALIASES统一映射无特判
        "model": "mode",  # 键名混淆实证: session 12b317fe 6连发全废(model:"once"), 语义唯一指向mode — 2026-11-04 小欧
    },
    "readmedia": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    # 修正: 注册名为listdir(原写成list_directory,别名从未生效) — 小欧 2026-07-11
    "listdir": {
        "dir_path": "path",
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "dirpath": "path",
    },
    "tree": {
        "dir_path": "path",
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "dirpath": "path",
    },
    "find": {
        "search_dir": "path",
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "search_path": "path",
    },
    "grep": {
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "search_dir": "path",
        "search_path": "path",
    },
    # 路径参数统一为path/dest后,旧规范名(source/destination)及同义别名降级为别名 — 小欧 2026-07-12
    "compress": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "output": "dest",
        "destination": "dest",
    },
    "extract": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "archive": "path",
        "archive_path": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "output": "dest",
        "destination": "dest",
    },
    "move": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "destination": "dest",
    },
    "copy": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "destination": "dest",
    },
    "delete": {
        "file": "path",
        "filepath": "path",
        "file_path": "path",
        "target": "path",
        "source": "path",
    },
    "rename": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "new_name": "dest",
        "destination": "dest",
    },
    "bash": {
        "workdir": "cwd",
        "work_dir": "cwd",
        "working_directory": "cwd",
        "directory": "cwd",
    },
    # 路径参数统一: download 目标参数 destination_path→dest — 小欧 2026-07-12
    "download": {
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "output": "dest",
        "output_path": "dest",
        "destination_path": "dest",
    },
    # 路径参数统一: screen_capture 输出参数 output_path→dest — 小欧 2026-07-12
    "screen_capture": {
        "output": "dest",
        "output_file": "dest",
        "file": "dest",
        "filepath": "dest",
        "target": "dest",
        "path": "dest",
        "output_path": "dest",
    },
    # 路径参数统一: document 8工具文件参数 file_name→path — 小欧 2026-07-12
    "read_pdf": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "read_docx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "read_pptx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "read_xlsx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "write_docx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "write_xlsx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
        "append": "append_mode",  # LLM 常传 append(布尔), 实际参数为 append_mode — 小欧 2026-08-09
    },
    "write_pdf": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "write_pptx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "httpget": {
        "link": "url",
        "address": "url",
        "endpoint": "url",
    },
    "fetchpage": {
        "format": "extract_format",  # 2026-11-10 小欧 - 官方webfetch参数名收编(枚举值markdown/html/text一致)
        "link": "url",
        "address": "url",
        "endpoint": "url",
    },
    "create_task": {
        "program": "command",
        "path": "command",
        "executable": "command",
    },
    # 路径参数统一: generate_chart 输出参数 output_path→dest(path→data保留) — 小欧 2026-07-12
    "generate_chart": {
        "output": "dest",
        "output_file": "dest",
        "file": "dest",
        "filepath": "dest",
        "target": "dest",
        "output_path": "dest",
        "path": "data",
        "file_path": "data",
    },
    # 路径参数统一为path后,旧规范名(file_path)降级为别名 — 小欧 2026-07-11
    "analyze_data": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    "filter_data": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    # 路径参数统一: query_sql 数据库路径参数 db_path→path — 小欧 2026-07-12
    "query_sql": {
        "db_path": "path",
        "dbpath": "path",
        "database": "path",
        "database_path": "path",
    },
    # 路径参数统一: execute_sql 数据库路径参数 db_path→path — 小欧 2026-07-12
    "execute_sql": {
        "db_path": "path",
        "dbpath": "path",
        "database": "path",
        "database_path": "path",
    },
    # 路径参数统一: get_db_schema 数据库路径参数 db_path→path — 小欧 2026-07-12
    "get_db_schema": {
        "db_path": "path",
        "dbpath": "path",
        "database": "path",
        "database_path": "path",
    },
    # 路径参数统一: registry_read 键路径参数 key_path→path — 小欧 2026-07-12
    "registry_read": {
        "registry_key": "path",
        "reg_key": "path",
        "regpath": "path",
        "key_path": "path",
        "key": "path",
        "keypath": "path",
        "registry_path": "path",
    },
    # 路径参数统一: registry_write 键路径参数 key_path→path — 小欧 2026-07-12
    "registry_write": {
        "registry_key": "path",
        "reg_key": "path",
        "regpath": "path",
        "key_path": "path",
        "key": "path",
        "data": "value",
    },
    # 路径参数统一: registry_delete 键路径参数 key_path→path — 小欧 2026-07-12
    "registry_delete": {
        "registry_key": "path",
        "reg_key": "path",
        "regpath": "path",
        "key_path": "path",
        "key": "path",
    },
}


# 参数值别名:大众化旧枚举值→规范值 — 小欧 2026-07-11
# 仅当旧值是大众化术语(LLM训练里常见,会自然使用)才需要兼容;自造的旧值不必处理
PARAM_VALUE_ALIASES = {
    "grep": {},
}


# 工具名别名: LLM生成的自然语言变体→注册名 — 小欧 2026-08-07
# 实测: com-test 03中LLM调用"write_text"(带下划线)被系统以"工具未注册"误拦截3次致任务失败。
# 与 PARAM_ALIASES 同款集中映射模式, 只收录实际发生+对称高频变体(YAGNI)。
TOOL_NAME_ALIASES = {
    "write_content": "write",  # LLM幻觉名→write - 小欧 2026-08-26
    "write_text": "write",
    "read_text": "read",
    "edit_text": "edit",
    "write_text_file": "write",
    "read_text_file": "read",
    "edit_text_file": "edit",
    "writefile": "write",
    "readfile": "read",
    "readtext": "read",  # 2026-10-02 小欧 - 注册名已改 read/write/edit, 旧名降级为幻觉名兜底
    "writetext": "write",
    "edittext": "edit",
    "writeetext": "write",
    "readetext": "read",
    "editetext": "edit",
    "list_directory": "listdir",
    "http_get": "httpget",
    "http_request": "httpget",
    "shell": "bash",  # 2026-10-02 小欧 - 注册名已改 bash, 旧名 shell 降级为幻觉名兜底
    "websearch": "searchweb",  # 2026-11-10 小欧 - 网关强塞的官方13件套名收编: 真联网搜索, 必填{query}逐字兼容(实证beam-free连调×13全被拒死循环)
    "glob": "find",  # 2026-11-10 小欧 - 官方glob{pattern,path?}→find(文件名通配搜索): pattern必填同名; path官方面可选本系统必填, 只传pattern时schema校验反馈补路径(一轮可纠正非死循环)
    "webfetch": "fetchpage",  # 2026-11-10 小欧 - 官方webfetch{url,format,timeout}→fetchpage, url必填同名
}

# 官方13件套中明确禁用的5个工具: 无诚实对应能力不收编, 命中即反馈"禁止使用"并点明全组, 防弱模型逐个试错 — 小欧-2026-11-10
UNAVAILABLE_OFFICIAL_TOOLS = ("question", "skill", "subagent", "patch", "execute")


def get_disabled_official_tools() -> tuple:
    """生效的禁用工具名单 — 小欧-2026-11-10

    真值源 = 配置 `tuning.agent.disabled_tools`。语义(用户拍板):
      **键存在即以配置为唯一真值: 清空(空串/空表/全空白) → 空元组 = 不禁用任何工具, 不兜底**;
      仅缺键/配置不可读/形状异常 → 回落内置 UNAVAILABLE_OFFICIAL_TOOLS(存量配置保升级前行为)。
    形状兼容两种(设置页 textarea 落盘会把文本按行拆成 YAML list, 手写 yaml 常是字符串):
      str → 按 , ; 换行 拆;  list/tuple → 逐元素取串, 元素内部再按 , ; 拆。
    读取用 get_config()(内部 mtime 缓存)热生效; 只影响未注册工具被拒时的措辞, 拦不住已注册工具。
    """
    try:
        from app.config import get_config  # 延迟导入: 本模块为叶子, 不给上层加导入依赖
        raw = get_config().get("tuning.agent.disabled_tools")  # 不给默认值: 缺键(None)与清空("")是两种语义
    except Exception:                      # 配置不可读 → 用内置默认, fail-safe 保持既有口径不突变
        return UNAVAILABLE_OFFICIAL_TOOLS
    if raw is None or not isinstance(raw, (str, list, tuple)):
        return UNAVAILABLE_OFFICIAL_TOOLS  # 缺键/数字布尔等异常形状 → 不猜, 用内置
    chunks = [raw] if isinstance(raw, str) else [str(x) for x in raw]
    parts: list = []
    for c in chunks:
        for p in c.replace(";", ",").replace("\n", ",").split(","):
            p = p.strip()
            if p:
                parts.append(p)
    return tuple(parts)                     # 拆完全空(清空) → () = 不禁用任何工具, 不兜底


def is_disabled_tool(tool_name: str) -> bool:
    """禁用判定: 命中生效名单→措辞升格"禁止使用"; 注册判定仍在认领层, 本名单不拦截 — 小欧-2026-11-10"""
    return tool_name in get_disabled_official_tools()


def normalize_tool_name(tool_name: str) -> str:
    """工具名别名归一化: LLM生成的变体名→注册名 — 小欧 2026-08-07

    与 normalize_params 同模式: 集中映射表 + 日志记录, 便于监控LLM行为。
    无别名命中时原样返回(不改变原工具名语义)。
    """
    if tool_name in TOOL_NAME_ALIASES:
        _canonical = TOOL_NAME_ALIASES[tool_name]
        logger.info(f"[tool_name_alias] {tool_name}→{_canonical}")
        return _canonical
    return tool_name


# XML 闭标签分割: 按 </tag> 切串, 奇数段=文本(去开标签后即值), 偶数段=标签名 — 商量 2026-11-13
_XML_CLOSE_SPLIT = re.compile(r"</([A-Za-z_$][\w]*)>")
_XML_OPEN_PREFIX = re.compile(r"^<[^>]+>")

# 显式参数但不在 PARAM_ALIASES 的工具键: edit.replaceAll 由 normalize_params 跨键特判(true→mode:all),
# 无别名条目; 归位时须一并识别, 否则该键被丢弃后只替换第一处而非全部(静默错误比失败更糟) — 商量 2026-11-13
_EXTRA_KNOWN_KEYS = {"edit": {"replaceAll"}}


def _parse_xml_packed_params(value: str, known_keys: set, aliases: dict) -> Dict[str, str]:
    """从 XML 标签包装串中解析参数键值对(宽容: 允许无开标签, 如 'text</newString>') — 商量 2026-11-13

    LLM 偶尔把 edit 参数序列化成 XML 标签串塞进单个字段:
      '### 1.6...</newString><old_string>### 1.5...</old_string><path>F:\\...</path>'
    按 </tag> 分割后, 每段文本(去掉开标签前缀)即对应参数值, 标签名经 aliases 映射为规范名。
    只收标签名命中已知参数名的段, 其余段丢弃(防未知键泄漏到顶层触发非法参数)。
    """
    parts = _XML_CLOSE_SPLIT.split(value)
    result = {}
    for i in range(0, len(parts) - 1, 2):
        text = parts[i]
        tag = parts[i + 1]
        if tag in known_keys or tag in aliases:
            target = aliases.get(tag, tag)
            text = _XML_OPEN_PREFIX.sub("", text)  # 去掉开标签(如有)
            if text:
                result[target] = text
    return result


def restore_misplaced_params(tool_name: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """参数归位: LLM 幻觉把参数对象错位塞进单个参数字段(嵌套 dict / XML 标签包装)时,
    解析归位回 schema 式顶层平铺 — 商量 2026-11-14(更名自"错位参数展开", 名不符实)

    实证形态(edit, deepseek-v4.1-flash, session 37dcf0a6, 59次edit中17次失败/29%轮次浪费):
    1. 嵌套 dict: {'new_string': {'old_string':..., 'path':..., '$text':...}}
    2. XML 标签串: {'new_string': 'val</newString><old_string>...</old_string><path>...</path>'}

    铁律(2026-11-14 商量, 用户实证 HITL 弹窗 path 错乱):
      ① 顶层正确参数是权威: 归位产物只补顶层缺失键, 绝不覆盖已有顶层值
         (原 expanded.update() 无条件覆盖把正确 path 顶成垃圾, 属重大bug);
      ② 顶层已齐全(schema 式正确参数表)不需归位, 直接原样返回零改动;
         XML 分支额外须有顶层缺失键佐证(字符串本可能是合法正文, 编辑正文恰含
         完整参数标签字面量时不得误吞); dict 装进字符串参数恒为错位, 无需佐证;
      ③ 承载键自身取解析出的自身规范值(原值是包装本体, 不是合法参数值);
         别名承载键(如 newString)归位后须移除原键(包装本体不留残, 否则归一化把
         别名键再映回规范键造成二次污染), 且顶层已有正确规范值时不覆盖(铁律①)。

    顺序契约: 归位在键名归一化之前(错位形态下键名归一化无意义); 归位用 PARAM_ALIASES
    参数表识别键名并直映规范名, 产物键名已规范, 后续键名归一化对其幂等(规范键原样通过),
    归一化仍是全参数唯一权威。

    Returns:
        (restored_params, has_restore) — 无需归位时原样返回 (params, False)
    """
    if not params or tool_name not in PARAM_ALIASES:
        return params, False

    aliases = PARAM_ALIASES[tool_name]
    known_keys = set(aliases.keys()) | set(aliases.values()) | _EXTRA_KNOWN_KEYS.get(tool_name, set())

    restored = dict(params)  # 判据①前提: 顶层原样起步, 正确参数零改动
    has_restore = False
    mapped = []

    for key, value in params.items():
        if key not in known_keys:            # 只有已知参数键才可能承载错位(防误伤合法dict参数)
            continue
        canonical_key = aliases.get(key, key)
        if isinstance(value, dict):
            # dict 装进字符串参数恒为错位, 无需缺失佐证(承载键归位由下方 ek==canonical_key 承担)
            extracted = {
                aliases.get(k, k): v
                for k, v in value.items()
                if k in known_keys
            }
        elif isinstance(value, str) and "</" in value:
            extracted = _parse_xml_packed_params(value, known_keys, aliases)
            # XML 判据: ≥2 参数且含自身规范名(单个 "</xxx>" 只是正文里的字面量);
            # 且须有顶层缺失键佐证 — 字符串本可能是合法正文, 顶层齐全时不得动它
            if len(extracted) < 2 or canonical_key not in extracted:
                continue
            if not any(ek != canonical_key and ek not in restored for ek in extracted):
                continue
        else:
            continue
        if not extracted:
            continue                          # dict 内无可识别键: 不归位不删键(fail-visible 留原样)
        for ek, ev in extracted.items():
            if ek == canonical_key and (key == canonical_key or ek not in restored):
                # 判据③: 承载键归位(原值是包装本体); 别名承载键且顶层已有正确规范值时不覆盖(铁律①)
                restored[ek] = ev
                mapped.append(f"{key}→{ek}")
                has_restore = True
            elif ek != canonical_key and ek not in restored:
                # 判据①: 只补缺失, 绝不覆盖顶层权威值
                restored[ek] = ev
                mapped.append(f"{key}→{ek}")
                has_restore = True
        if key != canonical_key:
            restored.pop(key, None)           # 判据③: 别名承载键包装本体移除(防归一化二次映回污染)
            has_restore = True

    if not has_restore:
        return params, False                 # 铁律②: 无归位原样直返(原引用, 正确参数表零改动)
    logger.info(f"[param_restore] {tool_name}: 错位参数归位 {mapped}")
    return restored, has_restore


def normalize_params(tool_name: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    规范化参数名 - 将LLM返回的参数名映射为Schema要求的参数名

    Args:
        tool_name: 工具名称
        params: LLM返回的参数字典

    Returns:
        (normalized_params, has_mapping)
        - normalized_params: 规范化后的参数字典
        - has_mapping: 是否发生了映射
    """
    if not params:
        return params, False

    # 参数归位(嵌套 dict / XML 标签包装 → schema 式顶层平铺), 在键名映射之前:
    #   错位形态下键名归一化无意义, 必须先归位; 归位产物键名已规范, 下方映射对其幂等 — 商量 2026-11-14
    params, _ = restore_misplaced_params(tool_name, params)

    if tool_name not in PARAM_ALIASES and tool_name not in PARAM_VALUE_ALIASES:
        return params, False

    aliases = PARAM_ALIASES.get(tool_name, {})
    normalized = {}
    has_mapping = False
    mapped_keys = []

    for key, value in params.items():
        if key in aliases:
            normalized_key = aliases[key]
            if normalized_key in params and normalized_key != key:
                logger.debug(
                    f"[param_alias] {tool_name}: 参数 '{key}' 被忽略，"
                    f"因为规范名称 '{normalized_key}' 已存在"
                )
                continue

            normalized[normalized_key] = value
            has_mapping = True
            mapped_keys.append(f"{key}→{normalized_key}")
        else:
            normalized[key] = value

    if has_mapping:
        logger.info(
            f"[param_alias] {tool_name}: 参数名映射 {mapped_keys}"
        )

    # 2026-11-11 小欧 - 官方edit跨键收编: replaceAll(bool)→mode(true→all/false→删键不设, EditInput缺省即once);
    #   OpenCode签名无mode键, replaceAll与本系统mode枚举是同一开关的两种形状, 值依赖改名故不能进PARAM_ALIASES
    if tool_name == "edit" and "replaceAll" in normalized:
        if normalized.pop("replaceAll"):
            normalized["mode"] = "all"

    # 参数值别名映射(在名映射后、schema校验前) — 小欧 2026-07-11
    value_aliases = PARAM_VALUE_ALIASES.get(tool_name, {})
    if value_aliases:
        mapped_values = []
        for pname, vmap in value_aliases.items():
            if pname in normalized and normalized[pname] in vmap:
                old_v = normalized[pname]
                normalized[pname] = vmap[old_v]
                has_mapping = True
                mapped_values.append(f"{pname}:{old_v}→{vmap[old_v]}")
        if mapped_values:
            logger.info(
                f"[param_alias] {tool_name}: 参数值映射 {mapped_values}"
            )

    return normalized, has_mapping


def get_param_aliases(tool_name: str) -> Dict[str, str]:
    """获取工具的参数别名映射"""
    return PARAM_ALIASES.get(tool_name, {})


def add_param_alias(tool_name: str, alias: str, canonical: str) -> None:
    """
    添加参数别名

    Args:
        tool_name: 工具名称
        alias: 别名（LLM可能返回的名称）
        canonical: 规范名称（Schema要求的名称）
    """
    if tool_name not in PARAM_ALIASES:
        PARAM_ALIASES[tool_name] = {}
    PARAM_ALIASES[tool_name][alias] = canonical
    logger.info(f"[param_alias] 添加别名: {tool_name}.{alias} → {canonical}")


def get_all_aliases() -> Dict[str, Dict[str, str]]:
    """获取所有工具的参数别名映射"""
    return PARAM_ALIASES.copy()
