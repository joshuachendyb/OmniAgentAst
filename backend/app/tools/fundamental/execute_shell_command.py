# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: shell 输出超长截断改引用 tool_constants.SHELL_OUTPUT_MAX_CHARS(30000→20000), 功能零退化
# 2026-07-20 - 小欧 - 门限治理(shell章6.4): 删除 SHELL_OUTPUT_MAX_CHARS 头尾截断, stdout/stderr 原样全量返回(Tool输出零限制3.7); 显示限量收口 observation_formatter 行×列(OBS_SHELL_MAX_ROWS/CHARS)
# 2026-07-20 - 小欧 - 门限复查: data 仅 {stdout,stderr}(returncode/shell_type/duration_ms 归 llm_data); observation_formatter #11 不再重复渲染 meta(shell_type/duration_ms/rc), 改由 _format_llm_data 在 llm_data 段统一呈现(退出码/耗时/shell类型), 严禁 data 详情与 llm_data 段重复显示; #11 仅渲染 stdout/stderr 原始输出 + 两态截断说明
# 2026-07-20 - 小欧 - 门限复查: cmd 分支补 3.4 硬安全网(与 powershell 分支 safe_read_file 对称): 新增 _safe_truncate_output 对 proc.communicate() 内存输出超 SHELL_OUTLIMIT_RAW_BYTES 仅保留头尾各半, 防下游 OOM/序列化膨胀
# 2026-07-21 - 小欧 - #14 PS版本检测: _translate_powershell_operators 改为无条件执行（删 not _PWSH_CACHE[0] 条件）
# 2026-07-23 - 小欧 - 北京老陈驱动: 新增 _truncate_shell_field
#         head-only+行边界截断(stdout=50000/stderr=20000);
#         tool_constants 新增 SHELL_OUTLIMIT_STDOUT_MAX_CHARS
#         /SHELL_OUTLIMIT_STDERR_MAX_CHARS;
#         formatter #11 读 _truncated 标记;
#         storage MAX_TOOL_RESULT_STR_LEN 提至100000;
# 2026-07-23 - 小欧 - 北京老陈驱动BugFix: output_len 传原始截断前长度而非截断后长度(bug1), 避免 LLM 被误导
# 2026-07-23 - 小欧 - 北京老陈驱动: 删 _safe_truncate_output(10MB 字节截断多余), 改直接 _decode_bytes_safe; 删 SHELL_OUTLIMIT_RAW_BYTES import; tool 层仅保留 _truncate_shell_field 50K/20K 唯一输出截断
# 2026-07-23 - 小欧 - #5 ERR_SHELL_EXEC 退出码释义映射: stderr/stdout全空时返回"退出码127(命令未找到)"等释义, 非纯数字
# 2026-07-24 - 小欧 - 北京老陈驱动BugFix:
#         _build_execute_shell_command_llm_data 重构:
#         问题: ① error分支summary直接嵌入完整_detail(可达20K stderr全文)
#             → LLM观察中"观察:"行与"✖ 错误:"行重复大段内容
#         ② warning分支hint硬编码为""，timeout的详细hint被静默丢失
#         ③ 三分支(提前返回)每次各自拼接param+调_build，代码冗余
#         修复:
#         ① 删stdout_preview/stderr_preview两个参数(YAGNI，截断不在函数内做)
#         ② error分支summary改为从_detail取第一行截断60字符(不再嵌入完整detail)
#         ③ error分支status.detail从stderr_preview[:200]改为_detail(完整detail)
#         ④ warning分支status.hint从""改为透传hint参数(timeout hint不再丢失)
#         ⑤ shell() phase5三分支合并为统一_exec_code+_detail+_hint变量+单次_build调用
#         ⑥ timeout用ERR_SHELL_TIMEOUT错误码+full detail(含超时秒数)
#         ⑦ stderr warning用_stderr_orig_len(截断前长度)替代stderr_str[:200]预览
#         ⑧ error用完整stderr_str/stdout_str(截断后全文)替代stderr_str[:200]预览

# 2026-07-25 - 小欧 - 截断治理: cmd_short签名移至末尾(不破坏positional传参, 保持向后兼容); main函数入口构造cmd_short + 8处传参cmd_short=cmd_short;  45行cmd_short内部fallback保留
# 2026-07-25 - 小欧 - 三堂会审修复bug×5:
#         ① fallback硬编码command[:35]/[-15:]/[:50]→改用EXECUTE_SHELL_OUTPARM_LIMIT_CMD常量
#         ② main缩写条件len>50→>_cmd_limit（防常量改后阈值不同步）
#         ③ tail=15硬编码→模块级_SHELL_CMD_TAIL常量
#         ④ head从原50(=命令总预览)修复为35(=50-15), 恢复35+15=50原内容预算(原main错误改为50+15=65超预算)
#         ⑤ build函数cmd_short删fallback+加assert强制传参(禁止backward: 保留默认值""因Python参数顺序约束, assert拦截不传参旧调用)
# 2026-07-25 - 小欧 - summary去stderr关联: error分支summary不再嵌_err_summary, summary纯摘要不拖detail; 删truncate_summary import
# 2026-07-25 - 小欧 - cmd_short改keyword-only强制传参: 删`=""`默认值+`*,`分隔, Python解释器级别强制传参(禁止backward彻底贯彻); 删assert因不再需要
# 2026-07-26 - 小沈 - 欧阳报告: 新增_auto_fix_powershell_syntax自动修复块内.Property→$_.Property(阶段1.5)
# 2026-07-27 - 小欧 - CMD增强: _resolve_safe_cwd安全回退+tempdir保底; CMD分支poll loop代替communicate阻塞; taskkill /T /F杀进程树; 阶段标注【PS专属|CMD专属|通用】; _auto_fix_cmd_syntax修复$env:VAR→%VAR%; _sanitize_env过滤API key泄露子进程
# 2026-07-27 - 小欧 - Bugfix×5: _close_if_blocks嵌套花括号深度计数; warning分支detail字段逻辑取反; bat_path加引号防空格; _PWSH_CACHE死代码删除; 阶段1.5重复执行消除
# 2026-07-27 - 小欧 - 重构: _sanitize_env常量提为模块级; cwd不存在改报错为自动回退; PS分支engine.exec传env=_sanitize_env()
# 2026-07-28 - 小欧 - 欧阳task005一轮修复4bug: BUG-03截断前存_stderr_for_diag; BUG-05删command死参数; BUG-06删_PWSH_CACHE死代码; BUG-07删cwd回退外层重复日志
# 2026-07-28 - 小欧 - 欧阳task005二轮修复4bug: BUG-02 CMD超时改立即杀进程; BUG-04深度计数简化为存在性检查; BUG-08良性stderr白名单扩展; BUG-09 safety检查传shell_type
# 2026-07-28 - 小欧 - 抽取 _kill_and_read_output 消除CMD超时两处重复代码
#         _close_if_blocks 改用深度计数+引号感知, 避免字符串内}误判
#         _cmd_powershell_mismatch_hint 补充英文匹配, 兼容非中文系统
# 2026-07-28 - 小欧 - shell_type名称改为ps7/ps5/cmd/bash; 默认ps7; 新增bash执行分支+_find_bash; 新增_auto_fix_bash_syntax;
#         _cmd_powershell_mismatch_hint→_shell_mismatch_hint全面覆盖4种shell; 路由4路分支; 语法修复4路; ps7不翻译&&(BUG#2)
# 2026-07-28 - 北京老陈 - 三堂会审重构shell()参数流:
#         ①shell_type早归一化(校验后即设ps7,消灭全文9处or""/or"ps7"冗余+2处is None冗余)
#         ②cmd变量改名stripped_command+processed_command消除与shell_type="cmd"的语义混淆
#         ③null字节检查_build调用补全缺失的shell_type/err_code/detail三参(P0修复)
#         ④语法修复/执行/安全检查/后处理统一使用processed_command
#         ⑤预处理错误路径保留command,处理后路径统一用processed_command
# 2026-07-29 - 小沈 - type加入CMD检测模式(\btype\b, CMD type=文件内容,bash type=命令类型); 修复遗留regex转义损坏(Format-Table行引号前多反斜杠)
# 2026-07-30 - 小欧 - 新增bash特征自动路由(阶段1.4): _looks_like_bash检测Linux命令→自动切换到Git Bash
#        +路径分隔符\→/转换+python3→python; 三堂会审修复: L649语法错误(\\\\n? not here),
#        DRY合并bash_keywords/path_indicators进bash_patterns
# 2026-07-30 - 小欧 - 重排阶段编号: 1.5→1.1, 1.6→1.2, 1.7→1.3, 1.8→1.4, 补齐1.1-1.4窟窿
# 2026-07-30 - 小欧 - 三路检测增强(阶段1.5):
#        +新增_looks_like_ps: 9模式PowerShell检测(Verb-Noun/$env/$global/function/$_/[Type]::/Write-/Out-/Format-)
#        +新增_looks_like_cmd: 19模式CMD检测(%VAR%/for/where/wmic/reg/attrib/tasklist/taskkill等)
#        +三路路由逻辑: PS→CMD→Bash, CMD→Bash→PS, Bash→CMD→PS
#        +增强_auto_fix_cmd_syntax: &&→&/$PWD→%CD%/$HOME→%USERPROFILE%
#        +增强_auto_fix_bash_syntax: \\→/路径转换
#        +更新bash_patterns: python3→python+ls/wc
#        +通用预处理stage1.0a: python3→python(防止重复转换)
#        +三路检测切换时logger.warning日志输出(PS→CMD/PS→Bash/CMD→Bash/CMD→PS/Bash→CMD/Bash→PS)
# 2026-08-06 - 小欧 - 最优重构stage结构(对照设计方案v3.3三堂会审):
#        ①三路检测从ps7/ps5执行分支内(旧阶段1.5死代码, cmd/bash初始类型不生效)
#         提至stage 1.1全局统一(所有shell_type生效), 先路由后校正杜绝做错方向
#        ②删除旧bash-only路由(旧阶段1.4), 三路检测完整覆盖, 不再"追加elif"(禁止backward/OCP)
#        ③python3→python收敛至stage 1.0a一处(DRY), 移除_auto_fix_bash_syntax内重复
#        ④PS语法校正保留(优于文档: {.Property→$_.Property}精准+LLM高频错, 收益>风险)
#        ⑤三路检测日志logger.warning→logger.info(路由是正常操作非异常)
# 2026-08-06 - 小欧 - 注释清晰化: stage 总览改用清晰列表(1.0/1.0a/1.1/1.2/2/3/4); 清理重复的`#stage`草案残片; _auto_fix_bash_syntax docstring精简(拆出python3注), 无逻辑改动
# 2026-08-06 - 小欧 - 三堂会审实证BugFix×4:
#        Bug5: _looks_like_cmd `\btype\b`过宽(bash/python type误判)→改`type`后带文件路径才判CMD
#        Bug6: _looks_like_ps Verb-Noun `\b[a-z]+-[a-z]+\b`过宽(foo-bar/project-x误判PS)
#             →收敛为已知cmdlet动词前缀+Test-*确切cmdlet
#        Bug7: stage 1.0a 简单re.sub替换python3破坏引号内容+DRY违规→改用shell_engine._replace_python3_safe(引号感知)
#        Bug8: Verb-Noun/pip3/python引号内误判bash→`(?:^|[;&|])\s*(python|pip3)\b`仅命令token; `\bpython\b`同理
#       修复后实证复验: test-case/echo "pip3"/echo "python is cool"不再误判; Test-Path/get-process/正常bash命令保留
# 2026-08-06 - 小欧 - v2.7三堂会审BugFix: PS分支 shell_pool.acquire() 补传 env=_sanitize_env()(原acquire启动走os.environ含API key泄漏给子进程, exec时传的env因进程存活被_ensure_alive忽略) — 与shell_engine.py acquire加env参数配套
# 2026-08-06 - 小欧 - 卡死场景日志补齐: C10(C11)分支超时/管道阻塞事件加[卡死C#]warning日志(CMD poll-loop超时/CMD communicate超时/Bash超时/taskkill异常/等退出超时), 与shell_engine.py C1-C14标注联动
# 2026-08-06 - 小健 - v2.9打猎修复: _kill_and_read_output 的 proc.wait() 无try保护(taskkill失败且进程僵死时抛TimeoutExpired冒泡到shell()的except → 丢失超时语义, 且中断残存stdout/stderr读取), 补try+warning日志, 超时后仍读残存返回
# 2026-08-06 - 小健/小欧 - v2.10打猎Bug#6(C11): _kill_and_read_output taskkill失败后裸proc.kill()兜底无保护, 进程已死/句柄失效时抛ProcessLookupError冒泡 → 中断残存stdout/stderr读取。修复: proc.kill()包try/except补warning日志, 失败后仍继续读残存返回(与引擎_kill_tree已有保护对称)。与shell_engine.py v2.10 Bug#5/#7打猎联动
# 2026-08-06 - 小欧 - 卡死C13根因修复(北京老陈21:53:36报告): ps7原生&&虽合法, 但`&&/||后接赋值语句`(如
#        `cd X && $env:PYTHONIOENCODING='utf-8'`)是PS7语法错误(ParserError), LLM高频生成 → ps1解析失败
#        → 命令从未执行 → 假超时(C8/C14杀进程) → C12 stderr残留ParserError → 池中留死实例 → 下次复用
#        探活失败C13(pid=None)。修复: 新增_fix_ps7_assignment_operators(引号感知检测&&/||后接$变量=赋值,
#        命中才复用_translate_powershell_operators翻译, 普通&&/||保持ps7原生不动), ps7分支集成; ps5分支不变。
# 2026-08-06 - 小欧 - 三路检测Bash误判修复(北京老陈22:02报告): `python "E:\test_dir\backup_integrity_check.py"`(ps7合法命令)
#        被_looks_like_bash判为bash(唯一命中`(?:^|[;&|])\s*python\b`) → 路由bash → _auto_fix_bash_syntax路径\→/转换(误)。
#        病根: 裸`python`是跨平台命令(Windows ps7/ps5/cmd同样合法), 绝非bash独有特征。修复: python判bash
#        收敛为仅当后跟Linux风格路径(/|./|~/), 即`python(?=\s+(?:\.?/|~/))`; python3(Linux独有解释器)保持判bash。
#        实证: 病根命令不再判bash留ps7; `python /tmp/x.py`/`python ./x.py`/`python3 /tmp/x.py`(经stage 1.0a转python)仍判bash。
# 2026-08-07 - 小欧 - 卡死日志三问五处修复(与shell_engine.py联动, 三堂会审定稿):
#        R0: CMD poll loop大输出死锁根治 — 仅poll不读管道, 200KB输出写满管道缓冲→子进程write阻塞→与poll互锁至超时杀树
#            且仅读回4096残存; 改非阻塞读管道(os.set_blocking(False))+自适应退避(有数据立即读/无数据指数退避上限50ms),
#            实验铁证200KB 0.1s完整读取vs原15s超时丢4096字节; communicate仅作有界收尾读清残余
#        R1: Format-Table正则扩展覆盖Format-List/Format-Wide根治C12 stderr残留(当日C12日志触发命令正是
#            `Get-Service | Format-List *`/`Get-ItemProperty | Format-List *`, 不受原Format-Table保护)
#        R2: systeminfo移出CMD特征(第4类命令列表+_looks_like_cmd正则)改走PS7根治C10表象
# 2026-08-07 - 小欧 - 三堂会审8.8复核: R0非阻塞read语义None/b''均安全无bug(熟读3遍+边界实测),
#        systeminfo三路入口均正常无退化(走PS7后无错误无卡死), 五处修改综合判定全部通过
# 2026-08-07 - 小欧 - G2普遍性根治(B6) C12管道层根治: R1枚举式保护(Format-Table/List/Wide命令名)有别名盲区
#        (fl/ft/fw漏网), 已由shell_engine.py _exec_locked ps_cmd B6管道层根治取代(命令名盲区全覆盖),
#        此处移除R1枚举保护, 单一根治点(KISS/DRY), 管道末端统一Out-String等效解决80列截断 — 与shell_engine.py联动
# 2026-08-07 - 小欧 - P08优化(北京老陈驱动 task001): 超时提示文案引导脚本化 — 复杂Python先写.py脚本文件执行(规避单行引号转义)+增大timeout(上限600); _detail已含实际超时值故hint不重复默认值 | py_compile ✓
"""
S1: execute_shell_command — 执行Shell命令（v2 引擎版）— 小欧 2026-07-05

╔══════════════════════════════════════════════════════════════════╗
║                Shell 工具编码链路分析与修复全景                     ║
║                   2026-07-07 北京老陈驱动检查                       ║
╚══════════════════════════════════════════════════════════════════╝

┌──────────────┐
│  shell() 入口 │──── command + shell_type
└──────┬───────┘
       │
       ├── shell_type in ("ps7","ps5") ────────────────────────────
       │   │
       │   ├── PersistentShell._exec()
       │   │   │
       │   │   ├── [入] stdin.write(cmd.encode("utf-8"))
       │   │   │   │   PS5.1 `-Command -` stdin
       │   │   │   │   ⚡ 实测: 不加BOM PS5.1自动识别UTF-8 ✅
       │   │   │   │   ⚡ 加BOM反而静默失败 ❌ (不修)
       │   │   │   │
       │   │   ├── [子进程] env={PYTHONIOENCODING=utf-8, PYTHONUTF8=1}
       │   │   │   │   2026-07-07 小欧 修复
       │   │   │   │   PYTHONIOENCODING: print()输出中文不抛异常
       │   │   │   │   PYTHONUTF8=1: open()默认用UTF-8避免gbk误读
       │   │   │   │
       │   │   ├── [出] > 替换为 Out-File -Encoding utf8
       │   │   │   │   2026-07-07 小欧 修复
       │   │   │   │   PS5.1用>写UTF-16LE导致中文乱码 → 统一UTF-8
       │   │   │   │
       │   │   └── [读] safe_read_file + .lstrip('\ufeff')
       │   │       2026-07-07 小欧 修复
       │   │       PS5.1 Out-File写BOM头 → 去掉ZWNBSP
       │   │       out/err/code/cwd 全部处理
       │   │
       │   └── PersistentShell 启动: -NoProfile -Command -
       │       (持久进程, 复用避免反复启动开销)
       │
       ├── shell_type="cmd" ─────────────────────────────────────
       │   │
       │   ├── [入] .bat文件写入 locale.getpreferredencoding()
       │   │   2026-07-07 小欧 修复
       │   │   改为gbk匹配cmd.exe OEM代码页,避免中文乱码
       │   │   (原用utf-8写, cmd.exe按gbk读,中文全乱)
       │   │
       │   ├── [子进程] env={PYTHONIOENCODING=utf-8, PYTHONUTF8=1}
       │   │   2026-07-07 小欧 修复
       │   │   PYTHONIOENCODING: print()输出中文不崩
       │   │   PYTHONUTF8=1: open()默认用UTF-8避免gbk误读
       │   │
       │   └── [出] proc.communicate() → _decode_bytes_safe()
       │       utf-8优先(gbk回退, latin-1兜底)
       │       Python子进程(PYTHONIOENCODING)输出UTF-8直接命中
       │
       └── shell_type="bash" ────────────────────────────────────
           │
           ├── [入] subprocess.Popen 直接传递命令字符串
           │    使用 -l 登录 shell, 自动加载 .bashrc
           │
           ├── [子进程] env 同主进程(无需设置PYTHONIOENCODING)
           │    Git Bash: /usr/bin/bash.exe
           │    WSL: /bin/bash (通过 WindowsApps 代理)
           │
           └── [出] proc.communicate() → _decode_bytes_safe()
               stdout/stderr 以 UTF-8 解码


┌────────────────────────────────────────────────────────────────┐
│  附: 系统级编码加固 (2026-07-07 小欧)                           │
├────────────────────────────────────────────────────────────────┤
│  main.py: sys.stdout.reconfigure(encoding='utf-8')             │
│    → 服务进程本身stdout设UTF-8, 日志/print中文不乱             │
└────────────────────────────────────────────────────────────────┘


【v2 改造】
  - ps7/ps5 分支改用 PersistentShell 持久引擎
  - 删除 run_in_background / _background_shells / shell_session
  - 保留 build3 + llm_data 体系不变

铁规1: helper 函数不碰 build3，只在 shell() 主函数包装
铁规2: 工具返回原始 data，前端截断在前端 yield 层
铁规3: 计时仅在 shell() 主函数
"""
# 小欧 - 2026-07-15: 新增success_codes参数+退出码判断改为`==0 or in`追加式,0永远成功
import locale
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Literal

from app.tools.file.file_encoding import get_file_encoding
from app.tools.fundamental.execute_shell_command_safety import check_shell_command_risk
from app.services.task.task_context import get_current_task_id
from app.tools.fundamental.shell_engine import PersistentShell, shell_pool, _replace_python3_safe
from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_fc_helper import _decode_bytes_safe
from app.tools.validate.timeout_validator import validate_timeout
from app.logger import logger

from app.tools.tool_constants import (
    ERR_PARAMETER_EMPTY, ERR_PARAMETER_INVALID,
    ERR_SHELL_EXCEPTION, ERR_SHELL_EXEC,
    ERR_SHELL_INJECTION, ERR_SHELL_TIMEOUT,
    EXECUTE_SHELL_OUTPARM_LIMIT_CMD,
    SHELL_OUTLIMIT_STDOUT_MAX_CHARS,
    SHELL_OUTLIMIT_STDERR_MAX_CHARS,
    SUBPROCESS_TIMEOUT_SHORT,
)


# ── 敏感环境变量过滤常量 — 小欧 2026-07-27 ──
_STATIC_BLOCK = frozenset({
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN",
    "AZURE_OPENAI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY",
    "MISTRAL_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY",
    "PERPLEXITY_API_KEY", "COHERE_API_KEY", "FIREWORKS_API_KEY",
    "XAI_API_KEY", "OPENROUTER_API_KEY",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "GH_TOKEN", "GITHUB_TOKEN",
})
_DYNAMIC_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


def _sanitize_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """过滤子进程环境变量, 移除API key等敏感变量 — 小欧 2026-07-27

    - 静态块列表: 已知LLM/KB服务API key
    - 动态匹配: *_API_KEY / *_TOKEN / *_SECRET (以免遗漏自定义provider)
    返回过滤后拷贝, 不影响原dict。
    """
    src = base_env or dict(os.environ)
    result: Dict[str, str] = {}
    for k, v in src.items():
        if k.upper() in _STATIC_BLOCK:
            logger.debug(f"[Shell] 过滤敏感env: {k}")
            continue
        if any(k.upper().endswith(suf) for suf in _DYNAMIC_SUFFIXES):
            logger.debug(f"[Shell] 过滤敏感env(动态): {k}")
            continue
        result[k] = v
    return result


# ── cmd_short 缩写常量（头部字数 = 总预算 - 尾部保留） ──
_SHELL_CMD_TAIL = 15
_SHELL_CMD_HEAD = EXECUTE_SHELL_OUTPARM_LIMIT_CMD - _SHELL_CMD_TAIL

# ═══════════════════════════════════════════════════════
#  CWD 安全回退（参考 Hermes _resolve_safe_cwd）
# ═══════════════════════════════════════════════════════


def _resolve_safe_cwd(cwd: str) -> str:
    """cwd不存在时沿路径上溯找第一个存在的目录, 全不可达则回退临时目录 — 小欧 2026-07-27

    保证始终返回非空字符串, 调用方无需判断None。"""
    if cwd and os.path.isdir(cwd):
        return cwd
    parent = os.path.dirname(cwd) if cwd else ""
    while parent:
        if os.path.isdir(parent):
            logger.warning(f"[Shell] cwd不存在, 回退: {cwd} → {parent}")
            return parent
        next_parent = os.path.dirname(parent)
        if next_parent == parent:
            break
        parent = next_parent
    logger.warning(f"[Shell] cwd不存在且无可用上级目录, 回退临时目录: {cwd} → {tempfile.gettempdir()}")
    return tempfile.gettempdir()


# ═══════════════════════════════════════════════════════
#  PowerShell 5.1 &&/|| 翻译（来自小沈 2026-07-05）
# ═══════════════════════════════════════════════════════


def _translate_powershell_operators(command: str) -> str:
    """将 && 和 || 翻译为 PowerShell 5.1 兼容语法"""
    if '&&' not in command and '||' not in command:
        return command
    result = []
    i = 0
    n = len(command)
    in_dq = False
    in_sq = False
    depth = 0
    in_lc = False
    in_bc = False
    skip_one = False
    stop = False
    while i < n:
        ch = command[i]
        if skip_one:
            result.append(ch); i += 1; skip_one = False; continue
        if in_lc:
            result.append(ch); i += 1
            if ch == '\n': in_lc = False
            continue
        if in_bc:
            result.append(ch); i += 1
            if ch == '#' and i < n and command[i] == '>':
                result.append('>'); i += 1; in_bc = False
            continue
        if stop:
            result.append(ch); i += 1
            if ch == '\n': stop = False
            continue
        if i + 3 <= n and command[i:i+3] == '--%':
            result.append('--%'); i += 3; stop = True; continue
        if ch == '<' and i + 1 < n and command[i+1] == '#':
            result.append('<#'); i += 2; in_bc = True; continue
        if ch == '$' and i + 1 < n and command[i+1] == '(':
            result.append('$('); i += 2; depth += 1; continue
        if ch == ')' and depth > 0:
            result.append(ch); i += 1; depth -= 1; continue
        if ch == '`':
            result.append(ch); i += 1; skip_one = True; continue
        if ch == "'" and depth == 0:
            result.append(ch); i += 1; in_sq = not in_sq; continue
        if ch == '"' and depth == 0:
            result.append(ch); i += 1; in_dq = not in_dq; continue
        if ch == '#' and not in_dq and not in_sq and depth == 0:
            result.append(ch); i += 1; in_lc = True; continue
        in_outer = not in_dq and not in_sq and depth == 0 and not in_lc and not in_bc and not stop
        if in_outer and command[i:i+2] == '&&':
            result.append('; $__ok=$?; if ($__ok) { ')
            i += 2; continue
        if in_outer and command[i:i+2] == '||':
            result.append('; $__ok=$?; if (-not $__ok) { ')
            i += 2; continue
        result.append(ch)
        i += 1
    translated = ''.join(result)
    if '; if ($__ok) { ' in translated or '; if (-not $__ok) { ' in translated:
        translated = '$__ok=$true; ' + translated
        translated = _close_if_blocks(translated)
    return translated


def _fix_ps7_assignment_operators(command: str) -> str:
    """ps7专用: 仅当 &&/|| 后接赋值语句时复用 _translate_powershell_operators 翻译, 其余保持 ps7 原生 &&。

    背景: ps7 原生支持 &&, 但 `cmd && $env:X='...'` 是 PS7 语法错误(ParserError) — LLM 高频生成
    `cd X && $env:PYTHONIOENCODING='utf-8'; python ...` → ps1 解析失败 → 命令从未执行 → 假超时
    (C8/C14 杀进程) → C12 stderr 残留 ParserError → 池中留死实例 → 下次复用探活失败(C13, pid=None)。
    修复: 引号感知检测 &&/|| 后紧跟 `$变量=`, 命中才调用翻译器(与 ps5 同路径), 不命中原样返回(ps7 原生 && 保留)。
    仅匹配赋值场景, 不匹配 `cmd && python x.py` 等合法 ps7 用法, 避免过度翻译。— 小欧 2026-08-06
    """
    if not _has_ps7_assignment_after_operator(command):
        return command
    return _translate_powershell_operators(command)


def _has_ps7_assignment_after_operator(command: str) -> bool:
    """引号感知检测: 是否存在 `&& $var=` / `|| $var=`(ps7 语法非法, LLM 高频赋值误用)。
    检测到才翻译; 普通 `&& cmd` 不命中, ps7 原生 && 保持不动。— 小欧 2026-08-06"""
    if '&&' not in command and '||' not in command:
        return False
    i = 0
    n = len(command)
    in_dq = False
    in_sq = False
    depth = 0
    in_lc = False
    in_bc = False
    skip_one = False
    stop = False
    while i < n:
        ch = command[i]
        if skip_one:
            i += 1; skip_one = False; continue
        if in_lc:
            if ch == '\n': in_lc = False
            i += 1; continue
        if in_bc:
            if ch == '#' and i < n and command[i] == '>':
                in_bc = False; i += 1; continue
            i += 1; continue
        if stop:
            if ch == '\n': stop = False
            i += 1; continue
        if i + 3 <= n and command[i:i+3] == '--%':
            i += 3; stop = True; continue
        if ch == '<' and i + 1 < n and command[i+1] == '#':
            i += 2; in_bc = True; continue
        if ch == '$' and i + 1 < n and command[i+1] == '(':
            i += 2; depth += 1; continue
        if ch == ')' and depth > 0:
            i += 1; depth -= 1; continue
        if ch == '`':
            i += 1; skip_one = True; continue
        if ch == "'" and depth == 0:
            i += 1; in_sq = not in_sq; continue
        if ch == '"' and depth == 0:
            i += 1; in_dq = not in_dq; continue
        if ch == '#' and not in_dq and not in_sq and depth == 0:
            i += 1; in_lc = True; continue
        in_outer = not in_dq and not in_sq and depth == 0 and not in_lc and not in_bc and not stop
        if in_outer and command[i:i+2] in ('&&', '||'):
            j = i + 2
            while j < n and command[j] in ' \t':
                j += 1
            if j < n and command[j] == '$':
                k = j + 1
                while k < n and (command[k].isalnum() or command[k] in '_.:'):
                    k += 1
                while k < n and command[k] in ' \t':
                    k += 1
                if k < n and command[k] == '=':
                    return True
            i += 2
            continue
        i += 1
    return False


def _close_if_blocks(s: str) -> str:
    """为翻译后的if块补上闭合} — 深度计数+引号感知(避免字符串字面量中的}误判) — 小欧 2026-07-28"""
    markers = ['; if ($__ok) { ', '; if (-not $__ok) { ']
    poses = []
    for marker in markers:
        pos = 0
        while True:
            pos = s.find(marker, pos)
            if pos == -1:
                break
            poses.append(pos)
            pos += len(marker)
    poses.sort(reverse=True)
    for pos in poses:
        marker = next(m for m in markers if s[pos:pos + len(m)] == m)
        after = s[pos + len(marker):]
        end = len(after)
        for m in markers:
            p = after.find(m)
            if p != -1 and p < end:
                end = p
        depth = 0
        has_closing = False
        in_str = None
        for ch in after[:end]:
            if in_str:
                if ch == in_str:
                    in_str = None
            else:
                if ch in ('"', "'"):
                    in_str = ch
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    if depth == 0:
                        has_closing = True
                        break
                    depth -= 1
        if not has_closing:
            s = s[:pos + len(marker) + end] + ' }' + s[pos + len(marker) + end:]
    return s


# ═══════════════════════════════════════════════════════
#  >重定向 UTF-8 转换（来自北京老陈 2026-06-30）
# ═══════════════════════════════════════════════════════

def _convert_redirect_to_utf8(command: str, cwd: Optional[str] = None) -> None:
    """Shell >重定向输出文件自动转为UTF-8"""
    target = _parse_redirect_path(command, cwd)
    if not target or not target.exists() or not target.is_file():
        return
    if target.stat().st_size > 1048576:
        return
    result = get_file_encoding(str(target))
    encoding = result.get("data", {}).get("encoding", "") if result else ""
    if encoding in ("", "utf-8", "utf-8-sig", "ascii"):
        return
    try:
        with open(target, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"[Shell] >重定向文件自动转UTF-8: {target} (原编码:{encoding})")
    except Exception as e:
        logger.warning(f"[Shell] >重定向文件转UTF-8失败: {target}: {e}")


def _parse_redirect_path(command: str, cwd: Optional[str] = None) -> Optional[Path]:
    """解析Shell命令中 >/>> 重定向的目标文件路径"""
    cleaned = re.sub(r'["\'][^"\']*["\']', '', command)
    m = re.search(r'(?<![<>])>+\s*(\S+)', cleaned)
    if not m:
        return None
    path_str = m.group(1)
    if '?' in path_str or '*' in path_str or '|' in path_str:
        return None
    p = Path(path_str)
    if not p.is_absolute():
        base = Path(cwd) if cwd else Path.cwd()
        p = base / p
    return p


# ═══════════════════════════════════════════════════════
#  llm_data 构建（来自小欧 2026-06-22）
# ═══════════════════════════════════════════════════════

def _build_execute_shell_command_llm_data(
    exec_code: str, duration_ms: int, command: str = "", returncode: int = 0,
    shell_type: str = "ps7",
    err_code: str = "", detail: str = "", timeout: int = 0, cwd: str = "",
    output_len: int = 0, stderr_len: int = 0, hint: str = "",
    *,
    cmd_short: str,
) -> Dict[str, Any]:
    """execute_shell_command 的 llm_data 构建函数
    cmd_short: 命令预览（由调用者构造传入）"""
    logger.debug(f"[Shell] _build llm: cmd_len={len(command)}, exec_code={exec_code}, rc={returncode}")
    _act_params = {"command": cmd_short}
    if shell_type:
        _act_params["shell_type"] = shell_type
    if timeout:
        _act_params["timeout"] = timeout
    if cwd:
        _act_params["cwd"] = cwd
    if exec_code == "error":
        _detail = detail or (f"退出码{returncode}" if returncode is not None else "执行异常")
        return {
            "summary": f"执行Shell命令{cmd_short}，失败",
            "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
            "status": {"exec_code": "error", "message": "执行失败", "code": err_code or ERR_SHELL_EXEC, "detail": _detail, "hint": hint if hint else "请检查命令语法和参数"},
            "duration_ms": duration_ms,
            "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
        }
    if exec_code == "warning":
        _warn_msg = detail or f"退出码{returncode}，标准错误{stderr_len}字符"
        return {
            "summary": f"执行Shell命令{cmd_short}，部分成功,提示说明: {_warn_msg}",
            "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
            "status": {"exec_code": "warning", "message": "执行成功（有警告）", "code": err_code or "", "detail": detail or f"退出码{returncode}，标准错误{stderr_len}字符", "hint": hint},
            "duration_ms": duration_ms,
            "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
        }
    return {
        "summary": f"执行Shell命令{cmd_short}，成功: 退出码{returncode}，输出{output_len}字符",
        "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
    }


def _fix_encoding(text: str) -> str:
    """编码修复：检测并修复中文乱码 — 小沈 2026-07-08  — 北京老陈 2026-07-09 修复:去掉CJK双通道检测(会产生误报)"""
    if not text:
        return text
    try:
        text.encode('utf-8')
        return text
    except UnicodeEncodeError:
        for enc in ('gbk', 'gb2312', 'latin-1'):
            try:
                return text.encode('latin-1').decode(enc)
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        return text


# 注意: OBS_SHELL_MAX_ROWS×OBS_SHELL_MAX_ROW_CHARS=200K
#       展示上限, tool截断50K目前保守对齐,
#       试用后再视需调整(北京老陈 2026-07-23)
def _truncate_shell_field(text: str, max_chars: int) -> tuple[str, bool]:
    """shell 工具输出截断(head-only+行边界): 超 max_chars 保留文首至最近行尾, 末尾追加截断说明 — 小欧 2026-07-23
    注意: OBS_SHELL_MAX_ROWS(200)×OBS_SHELL_MAX_ROW_CHARS(1000)=200K 是formatter展示上限;
          tool截断50K(stdout)/20K(stderr)为存储保护值, 低于展示上限; 试用后按需调整(北京老陈 2026-07-23)"""
    if len(text) <= max_chars:
        return text, False
    cut = text[:max_chars].rfind('\n')
    if cut <= 0:
        cut = max_chars
    head = text[:cut]
    note = f"\n...[shell输出截断: 原文{len(text)}字符, 保留{cut}字符]...\n"
    return head + note, True


# 已知良性stderr模式白名单（不触发warning）— 小欧 2026-07-08
_BENIGN_STDERR_PATTERNS = [
    "Non-authoritative answer",
    "DeprecationWarning",
    "UserWarning",
    "FutureWarning",
    "Info:",
    "Note:",
]

def _filter_benign_stderr(stderr: str) -> str:
    """过滤已知良性stderr行 — 小欧 2026-07-08"""
    if not stderr:
        return ""
    lines = stderr.splitlines()
    filtered = [l for l in lines if not any(p in l for p in _BENIGN_STDERR_PATTERNS)]
    return "\n".join(filtered)


def _shell_mismatch_hint(shell_type: str, stderr: str) -> str:
    """检测shell语法混用，返回针对性hint — 小欧 2026-07-28"""
    _not_found = r'(不是内部或外部命令|不是可运行的程序|not recognized|not an internal|is not recognized|not a valid command|command not found)'
    if not re.search(_not_found, stderr, re.IGNORECASE):
        return ""
    if shell_type == "cmd":
        return "命令可能包含PowerShell语法，建议设置shell_type='ps7'或shell_type='ps5'"
    elif shell_type in ("ps7", "ps5"):
        return "命令可能包含CMD语法，建议设置shell_type='cmd'"
    elif shell_type == "bash":
        return "命令可能包含Windows本地语法，建议设置shell_type='ps7'或shell_type='cmd'"
    return ""


def _auto_fix_cmd_syntax(command: str) -> str:
    """自动修复LLM生成的CMD命令中已知错误模式 — 小欧 2026-07-27

    当前覆盖：
    - $env:VAR → %VAR%（LLM常把PS环境变量语法带到CMD）
    - && → &（链式操作符）
    - $PWD → %CD%（当前目录）
    - $HOME → %USERPROFILE%（用户目录）"""
    if not command:
        return command
    fixed = command
    fixed = re.sub(r'\$env:(\w+)', r'%\1%', fixed)
    fixed = re.sub(r'(?<![>&])&&(?![&>])', '&', fixed)
    fixed = re.sub(r'\$PWD', '%CD%', fixed, flags=re.IGNORECASE)
    fixed = re.sub(r'\$HOME', '%USERPROFILE%', fixed, flags=re.IGNORECASE)
    if fixed != command:
        logger.warning(f"[Shell] 自动修复CMD语法: $env:VAR→%VAR%, &&→&, $PWD→%CD%, $HOME→%USERPROFILE%, cmd={command[:100]}")
        return fixed
    return command


def _auto_fix_powershell_syntax(command: str) -> str:
    """自动修复LLM生成的PowerShell命令中已知错误模式 — 小沈 2026-07-26

    当前覆盖：
    - 脚本块{...}内 .Property → $_.Property（LLM常漏写$_）"""
    if not command:
        return command
    # { .Property → { $_.Property (花括号开头的.缺$_)
    # 必须排除 {{.Name}} 转义双花括号(模板语法),用(?<!\{)\{(?!\{)确保仅匹配单{ — 小沈 2026-07-26
    if re.search(r'(?<!\{)\{(?!\{)\s*\.\w+', command):
        fixed = re.sub(r'(?<!\{)\{(?!\{)\s*\.(\w+)', r'{ $_.\1', command)
        if fixed != command:
            logger.warning(f"[Shell] 自动修复PS语法: 块内.Property→$_.Property, cmd={command[:100]}")
            return fixed
    return command


def _auto_fix_bash_syntax(command: str) -> str:
    """自动修复LLM生成的Bash命令中已知错误模式 — 小欧 2026-07-28; 2026-08-06 精简

    当前覆盖：
    - Windows反斜杠 → 正斜杠（Git Bash下\\t会被解释为制表符）

    注: python3→python 已在 stage 1.0a 统一处理，此处不再重复（DRY）"""
    if not command or sys.platform != "win32":
        return command
    fixed = command
    # 路径分隔符：Windows反斜杠 → 正斜杠（防止\\t被解释为制表符）
    fixed = fixed.replace('\\', '/')
    if fixed != command:
        logger.warning(f"[Shell] 自动修复bash语法: 路径转换\\→/, cmd={command[:100]}")
        return fixed
    return command


def _find_bash() -> Optional[str]:
    """查找可用bash解释器（Git Bash->bin/bash.exe, 其次PATH中的bash, 最后SHELL环境变量中找bash）— 小欧 2026-07-28"""
    git = shutil.which("git")
    if git:
        git_bash = os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe")
        if os.path.isfile(git_bash):
            return git_bash
    path_bash = shutil.which("bash")
    if path_bash:
        return path_bash
    shell_env = os.environ.get("SHELL")
    if shell_env and os.path.isfile(shell_env) and 'bash' in os.path.basename(shell_env).lower():
        return shell_env
    return None


# ═══════════════════════════════════════════════════════
#  _kill_and_read_output — 超时后杀进程+读残存输出 (DRY抽取)
# ═══════════════════════════════════════════════════════

def _kill_and_read_output(proc: subprocess.Popen) -> tuple[bytes, bytes]:
    """CMD超时后 杀进程树 + 等退出 + 读残存 stdout/stderr — 小欧 2026-07-28 — [卡死场景C11] 小欧 2026-08-06"""
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True, timeout=SUBPROCESS_TIMEOUT_SHORT,
        )
    except Exception as e:
        logger.warning(f"[卡死C11] taskkill异常 → proc.kill()兜底 (pid={proc.pid}): {e}")
        try:
            proc.kill()   # v2.10 BugFix(小健 2026-08-06): 兜底kill本身可能抛(进程已死/句柄失效), 必须受保护, 否则异常冒泡中断残存读取
        except Exception as ke:
            logger.warning(f"[卡死C11] proc.kill()兜底也失败(进程可能已死/句柄失效), 直接读残存 (pid={proc.pid}): {ke}")
    try:
        proc.wait(timeout=SUBPROCESS_TIMEOUT_SHORT)
    except Exception as e:
        logger.warning(f"[卡死C11] 等退出超时/异常 → 读残存继续 (pid={proc.pid}): {e}")
    try:
        stdout_b = proc.stdout.read() if proc.stdout else b""
    except Exception:
        stdout_b = b""
    try:
        stderr_b = proc.stderr.read() if proc.stderr else b""
    except Exception:
        stderr_b = b""
    return stdout_b, stderr_b


# ═══════════════════════════════════════════════════════
#  _looks_like_bash — 检测命令是否像bash命令
# ═══════════════════════════════════════════════════════


def _looks_like_bash(command: str) -> bool:
    """检测命令是否包含bash特有模式（Linux风格语法）
    
    检测Linux风格语法特征，确定是否应该路由到bash:
    - 特定命令: mkdir -p, find . -name, grep, head -n, tail -n, chmod
    - 解释器: python3, pip3, apt, conda
    - 网络工具: wget, curl -o
    - 配置命令: ./configure, Makefile
    - 注意: cmd.exe的目标命令如dir, tasklist, systeminfo显示为非bash
    
    Args:
        command: 要检查的命令字符串
        
    Returns:
        bool: 如果检测到bash特征返回True，否则False
    """
    if not command:
        return False
        
    cmd_lower = command.lower()
    
    # bash特有命令（Linux风格语法）— 正则匹配灵活覆盖各种变体
    bash_patterns = [
        r'\bmkdir -p\b',           # mkdir -p 目录
        r'\bfind\b.*-name\b',      # find . -name
        r'\bgrep\b',               # grep
        r'\bgrep -E\b',           # grep -E
        r'\bhead\b',              # head -n
        r'\btail\b',              # tail -n
        r'\bchmod\b',             # chmod
        r'(?:^|[;&|])\s*python(?=\s+(?:\.?/|~/))',  # python+Linux风格路径(/|./|~/): 裸python是跨平台命令(Windows ps7同样合法), 仅当带Linux风格路径才判bash — 小欧 2026-08-06 BugFix
        r'(?:^|[;&|])\s*python3\b',      # python3(Linux独有解释器, Windows无python3可执行) — 小欧 2026-08-06
        r'(?:^|[;&|])\s*python\s3\b',    # python 3 (space)
        r'(?:^|[;&|])\s*pip3\b',    # pip3(要求作为命令起始token, 避免echo "pip3"误判) — 小欧 2026-08-06 Bug6修正
        r'\bapt\b',               # apt
        r'\bapt-get\b',           # apt-get
        r'\bconda\b',             # conda
        r'\bdep\b',               # dep
        r'\bwget\b',              # wget
        r'\bcurl\b.*?-o\b',       # curl -o
        r'\b\./.*configure\b',    # ./configure
        r'\b\./Makefile\b',       # ./Makefile
        r'\b\./setup\.py\b',       # setup.py
        r'\bmake\b',              # make命令
        r'\bcmake\b',             # cmake命令
        r'\brm\s+-rf\b',          # rm -rf
        r'\bmv\s+.*\.\.\b',       # mv ./to/../
        # ── v2.0新增: ls/wc（CMD用dir/find /c替代，bash独有） ── 小欧 2026-07-30
        r'\bls\b',                # ls -la（CMD用dir）
        r'\bwc\b',                # wc -l（CMD用find /c）
    ]
    
    for pattern in bash_patterns:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return True

    return False


def _looks_like_ps(command: str) -> bool:
    """检测命令是否像PowerShell命令
    
    检测Windows PowerShell特有语法特征，确定是否应该路由到PowerShell:
    - Verb-Noun cmdlet: Get-Process, Set-Content, Select-Object
    - PS环境变量: $env:PATH, $env:USERPROFILE
    - PS全局变量: $global:MyVar
    - PS函数定义: function MyFunc { ... }
    - PS自动变量: $_
    - .NET类型调用: [Math]::Round(), [Environment]::GetFolderPath()
    - Write-* cmdlets: Write-Host, Write-Output, Write-Error, Write-Warning
    - Out-* cmdlets: Out-String, Out-File, Out-Default
    - Format-* cmdlets: Format-Table, Format-List, Format-Wide
    
    Args:
        command: 要检查的命令字符串
        
    Returns:
        bool: 如果检测到PowerShell特征返回True，否则False
    """
    if not command:
        return False

    cmd_lower = command.lower()

    # PowerShell特有命令（Windows PowerShell语法）— 正则匹配灵活覆盖各种变体
    ps_patterns = [
        # Verb-Noun cmdlet: 只匹配PowerShell已知动词前缀, 避免误判普通连字符命名(如project-x/hello-world) — 小欧 2026-08-06 Bug6修复
        r'\b(?:get|set|new|add|remove|select|write|read|start|stop|restart|invoke|convert|copy|move|format|clear|output|enter|exit|wait|prompt|show|hide|ping|trace|assert|join|sort|group)-[a-z]{2,}\b',
        r'\btest-(?:path|connection|json|netconnection|service|webrequest|modulemanifest)\b',  # Test-*确切cmdlet(避免test-case误判) — 小欧 2026-08-06
        r'\$env:\w+',                   # PS环境变量: $env:PATH, $env:USERPROFILE
        r'\$global:\w+',                # PS全局变量: $global:MyVar
        r'\bfunction\s+\w+',           # PS函数定义
        r'\$_',                        # PS自动变量: $_
        r'\[.*?\]::',                  # .NET类型调用: [Math]::Round(), [Environment]::GetFolderPath()
        r'\bwrite-(host|output|error|warning)\b',   # Write-* cmdlets
        r'\bout-(string|file|default)\b',           # Out-* cmdlets
        r'\bformat-(table|list|wide)\b',            # Format-* cmdlets
    ]

    for pattern in ps_patterns:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return True

    return False


def _looks_like_cmd(command: str) -> bool:
    """检测命令是否像CMD命令
    
    检测Windows CMD特有语法特征，确定是否应该路由到CMD:
    - Windows特有环境变量: %PATH%, %TEMP%等（CMD才有的变量引用语法）
    - CMD特有循环语法: for %i in, for /f %i in
    - CMD特有命令: where, wmic, reg query/add/delete/import/export, attrib, tasklist, taskkill, msieexec, diskpart, bcdedit, echo %var, set var=value, pushd/popd, assoc/ftype, findstr
      (注: systeminfo 已于 2026-08-07 移出CMD特征, 改走PS7引擎 — 小欧 三堂会审定稿)
    - CMD特有入口点: cmd.exe /c
    - CMD特有文件操作: copy, del, rd
    
    Args:
        command: 要检查的命令字符串
        
    Returns:
        bool: 如果检测到CMD特征返回True，否则False
    """
    if not command:
        return False

    cmd_lower = command.lower()

    # CMD特有命令（Windows CMD语法）— 正则匹配灵活覆盖各种变体
    cmd_patterns = [
        r'%\w+%',                      # 环境变量: %PATH%, %TEMP%等
        r'\bfor\b(?:/\w+)*\s+%[a-z]\s+in\b',  # FOR循环: for %i in, for /f %i in
        r'\bwhere\s+\w+',             # 命令查找: where git, where python
        r'\bwmic\b',                   # Windows管理工具
        r'\breg\s+(query|add|delete|import|export)\b',  # 注册表操作
        r'\battrib\b',                 # 文件属性操作
        r'\btasklist\b',               # 进程列出
        r'\btaskkill\b',               # 进程终止
        r'\bmsiexec\b',                # MSI安装程序
        r'\bdiskpart\b',               # 磁盘分区
        r'\bbcdedit\b',                # 启动配置
        r'\becho\s+%',                 # 输出环境变量: echo %PATH%
        r'\bset\s+\w+=',              # 变量定义: set MYVAR=value
        r'\bpushd\b\|\bpopd\b',       # 目录栈操作
        r'\bassoc\b\|\bftype\b',       # 文件关联: assoc, ftype
        r'\btype\s+\S+[.\/\\]\S+',     # 文件内容显示(CMD type=cat; 仅当带文件路径时判CMD, 避免bash/python type误判) — 小沈 2026-07-29, 小欧 2026-08-06 Bug5修复
        r'\bfindstr\b',                # 字符串搜索
        r'\bcmd\.exe\b',               # CMD入口点
        r'\b(copy|del|rd)\b',          # 文件操作
    ]

    for pattern in cmd_patterns:
        if re.search(pattern, cmd_lower, re.IGNORECASE):
            return True

    return False


# ═══════════════════════════════════════════════════════
#  shell() — 主函数（v2 引擎版）
# ═══════════════════════════════════════════════════════

def shell(
    command: str, shell_type: Literal["ps7", "ps5", "cmd", "bash", None] = "ps7",
    timeout: int = 60, cwd: Optional[str] = None,
    success_codes: Optional[list[int]] = None,
) -> Dict[str, Any]:
    """执行 Shell 命令（v2: 持久引擎版）

    参数:
        command:     命令字符串
        shell_type:  "ps7"(默认), "ps5", "cmd" 或 "bash"
        timeout:     超时秒数，默认 60，范围 1-600
        cwd:         工作目录绝对路径

    返回:
        build_success / build_error / build_warning 标准格式
        data: {stdout, stderr}（原始输出; returncode/shell_type/duration_ms 仅在 llm_data, 不在 data）
        llm_data: 完整 status/metrics/summary（含 returncode/exit_code、shell_type、duration_ms）
    """
    # ── 阶段 1【通用】: 参数校验 ──
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "shell")
    t0 = _time_mod.perf_counter()
    _cmd_limit = EXECUTE_SHELL_OUTPARM_LIMIT_CMD
    cmd_short = (command[:_SHELL_CMD_HEAD] + "..." + command[-_SHELL_CMD_TAIL:]) if command and len(command) > _cmd_limit else (command[:_cmd_limit] if command else "(空命令)")

    if not timeout_valid:
        llm = _build_execute_shell_command_llm_data("error", 0, command, -1,
            shell_type, ERR_PARAMETER_INVALID, timeout_err,
            timeout=timeout, cwd=cwd or "", hint="请检查timeout参数", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)

    if shell_type not in ("ps7", "ps5", "cmd", "bash", None):
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1,
            shell_type, ERR_PARAMETER_INVALID, "shell_type仅支持ps7/ps5/cmd/bash",
            timeout=timeout, cwd=cwd or "", hint="shell_type仅支持ps7/ps5/cmd/bash", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)
    if shell_type is None:
        shell_type = "ps7"

    stripped_command = command.strip() if command else ""
    processed_command = stripped_command
    
    # ── 阶段 1.0a【通用】: 通用预处理 — 小欧 2026-07-30; 2026-08-06 引号感知修复(Bug7) ──
    #  python3 → python（引号感知，仅替换引号外的python3；复用shell_engine._replace_python3_safe，DRY）
    processed_command, _python3_cnt = _replace_python3_safe(processed_command)

    if not stripped_command:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command or "", -1,
            shell_type, ERR_PARAMETER_EMPTY, "要执行的命令不能为空",
            timeout=timeout, cwd=cwd or "", hint="请提供要执行的命令", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)

    if "\x00" in command:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1,
            shell_type, ERR_PARAMETER_INVALID, "命令包含空字符(null byte),拒绝执行",
            timeout=timeout, cwd=cwd or "", hint="命令不能包含空字符(null byte)", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)

    if cwd and not os.path.isdir(cwd):
        cwd = _resolve_safe_cwd(cwd)

    # ── 阶段总览 ── 小欧 2026-08-06
    #   stage 1.0  参数校验
    #   stage 1.0a 通用预处理（python3→python，仅此一处）
    #   stage 1.1  三路检测+路由（所有 shell_type 统一、先路由后校正）
    #   stage 1.2  按最终 shell_type 校正：
    #                - cmd     → _auto_fix_cmd_syntax
    #                - bash    → _auto_fix_bash_syntax
    #                - ps7/ps5 → _auto_fix_powershell_syntax（保留，优于文档）
    #   stage 2    安全检查
    #   stage 3    执行（ps7/ps5引擎 / cmd.bat / bash登录shell，三路无嵌套检测）
    #   stage 4    后处理
    #
    # ── 阶段 1.1【通用】: 三路类型检测 + 路由 ── 小欧 2026-07-29 v2.0; 2026-08-06 位置修正 ──
    #  以LLM选的shell_type为"第一猜测"，匹配则直接执行；不匹配则尝试其他类型。
    #  路由只改shell_type，不做语法校正（交由 stage 1.2）；"都不像"保持原type让LLM承担。
    if shell_type in ("ps7", "ps5"):
        # ── PS分支：最接近PS，其次CMD，最后Bash ──
        if _looks_like_ps(processed_command):
            pass  # 匹配PS语法→保持shell_type，直接执行
        elif _looks_like_cmd(processed_command):
            logger.info(f"[Shell] 三路检测: PS→CMD, cmd={cmd_short}")
            shell_type = "cmd"
        elif _looks_like_bash(processed_command) and _find_bash():
            logger.info(f"[Shell] 三路检测: PS→Bash, cmd={cmd_short}")
            shell_type = "bash"
    elif shell_type == "cmd":
        # ── CMD分支：最接近CMD，其次Bash，最后PS ──
        if _looks_like_cmd(processed_command):
            shell_type = "cmd"  # 保持不变
        elif _looks_like_bash(processed_command) and _find_bash():
            logger.info(f"[Shell] 三路检测: CMD→Bash, cmd={cmd_short}")
            shell_type = "bash"
        elif _looks_like_ps(processed_command):
            logger.info(f"[Shell] 三路检测: CMD→PS, cmd={cmd_short}")
            shell_type = "ps7"
    elif shell_type == "bash":
        # ── Bash分支：最接近Bash，其次CMD，最后PS ──
        if _looks_like_bash(processed_command) and _find_bash():
            shell_type = "bash"  # 保持不变
        elif _looks_like_cmd(processed_command):
            logger.info(f"[Shell] 三路检测: Bash→CMD, cmd={cmd_short}")
            shell_type = "cmd"
        elif _looks_like_ps(processed_command):
            logger.info(f"[Shell] 三路检测: Bash→PS, cmd={cmd_short}")
            shell_type = "ps7"

    # ── 阶段 1.2【通用】: 语法自动修复（按最终shell_type校正，路由已完成） ──
    # PS校正保留: {.Property→$_.Property}模式极精准(仅匹配{ .word缺$_)，LLM高频错误，收益>风险
    if shell_type in ("ps7", "ps5"):
        _fixed = _auto_fix_powershell_syntax(processed_command)
        if _fixed != processed_command:
            processed_command = _fixed
    elif shell_type == "cmd":
        _fixed = _auto_fix_cmd_syntax(processed_command)
        if _fixed != processed_command:
            processed_command = _fixed
    elif shell_type == "bash":
        _fixed = _auto_fix_bash_syntax(processed_command)
        if _fixed != processed_command:
            processed_command = _fixed

    # ── 阶段 2【通用】: 安全检查 ──
    safety = check_shell_command_risk(processed_command, shell_type, protected_pids=shell_pool.get_all_pids())
    if safety:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        if safety.blocked:
            llm = _build_execute_shell_command_llm_data("error", d, processed_command, -1,
                shell_type, ERR_SHELL_INJECTION, safety.message,
                timeout=timeout, cwd=cwd or "", hint="命令被安全规则拦截", cmd_short=cmd_short)
            return build_error(data={}, llm_data=llm)
        if safety.requires_confirmation:
            logger.warning(f"[Shell] 中风险命令已放行（需用户确认）: {safety.message}")

    # ── 阶段 3【PS/CMD分支】: 执行 ──
    try:
        if shell_type in ("ps7", "ps5"):  # ── 【PS7/PS5专属】: 持久进程引擎 — 小欧 2026-07-28 ──
            # BUG#2修复: ps5需要翻译&&→;if($?){cmd2}; ps7原生支持&&无需翻译 — 小欧 2026-07-28
            # v2.11 BugFix(小欧 2026-08-06): ps7 `&& $env:X='utf-8'`是PS7语法错误(ParserError)导致命令
            # 从未执行→假超时(C8/C14)→连锁C13; 仅此赋值场景复用翻译器兜底, 其余&&保持ps7原生 — 小欧 2026-08-06
            if shell_type == "ps5":
                processed_command = _translate_powershell_operators(processed_command)
            else:
                processed_command = _fix_ps7_assignment_operators(processed_command)
            # [卡死C12] 2026-08-07 小欧: R1枚举式保护(Format-Table/List/Wide)已由shell_engine.py
            # _exec_locked 的 B6 管道层根治取代(命令名盲区fl/ft/fw全部覆盖), 此处移除, 单一根治点(KISS)
            # (B6管道末端统一| Out-String -Width 4096, 等效解决80列截断, 比命令层追加更彻底) — 小欧 2026-08-07

            task_id = get_current_task_id()
            # v2.7 BugFix(小欧 2026-08-06): acquire 传入 _sanitize_env(), 修复持久进程启动时
            # 直接 copy os.environ(含 API key) 泄漏给子进程的问题(此前仅 exec 时传 env, 进程存活时被忽略)。
            engine = shell_pool.acquire(task_id, shell_type, workdir=cwd, env=_sanitize_env())
            try:
                result = engine.exec(processed_command, timeout, env=_sanitize_env())
            finally:
                shell_pool.release(engine)
            stdout_str = _fix_encoding(result.get("stdout", ""))
            stderr_str = _fix_encoding(result.get("stderr", ""))
            returncode = result.get("exit_code", -1)
            timed_out = result.get("timed_out", False)

        elif shell_type == "cmd":  # ── 【CMD专属】: .bat + subprocess ──
            # 写入 temp .bat 执行，绕过 cmd.exe /c 的引号解析 bug — 小欧 2026-07-05
            # cmd.exe读.bat用的是系统OEM编码(中文Win=gbk)，utf-8写入会乱 — 小欧 2026-07-07
            bat_encoding = locale.getpreferredencoding()
            bat_fd, bat_path = tempfile.mkstemp(suffix='.bat', text=True)
            try:
                with os.fdopen(bat_fd, 'w', encoding=bat_encoding, errors='replace') as f:
                    f.write('@echo off\r\n')
                    f.write(processed_command + '\r\n')
                    f.write('exit /b %errorlevel%\r\n')
                child_env = _sanitize_env()
                child_env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
                proc = subprocess.Popen(
                    f'"{bat_path}"', shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd=cwd, env=child_env,)
                timed_out = False
                try:
                    # [卡死场景C10-v2] poll loop + 非阻塞读管道(防大输出写满缓冲死锁)
                    # + 防start /b子进程持管道挂满communicate — 小欧 2026-08-07 三堂会审定稿
                    # 实验铁证: 仅poll不读管道, 200KB输出写满管道缓冲→子进程write阻塞→
                    # 与poll互锁至超时杀树且仅读回4096残存; 自适应读+递增退避则0.1s完整读取
                    _deadline = _time_mod.time() + timeout
                    _drain_out: list = []
                    _drain_err: list = []
                    if proc.stdout:
                        os.set_blocking(proc.stdout.fileno(), False)  # Windows管道支持非阻塞
                    if proc.stderr:
                        os.set_blocking(proc.stderr.fileno(), False)
                    _poll_sleep = 0.001
                    while _time_mod.time() < _deadline and proc.poll() is None:
                        _read_any = False
                        for _stream, _buf in ((proc.stdout, _drain_out), (proc.stderr, _drain_err)):
                            if _stream is None:
                                continue
                            try:
                                while True:  # 一次读到空, 减少空轮询
                                    _chunk = _stream.read(65536)
                                    if not _chunk:
                                        break
                                    _buf.append(_chunk)
                                    _read_any = True
                            except (BlockingIOError, OSError):
                                pass
                        if _read_any:  # 有数据立即再读, 防子进程再次写满阻塞
                            _poll_sleep = 0.001
                        else:  # 无数据指数退避, 上限50ms防忙轮询
                            _poll_sleep = min(_poll_sleep * 2, 0.05)
                        _time_mod.sleep(min(_poll_sleep, max(0, _deadline - _time_mod.time())))
                    if proc.poll() is None:
                        timed_out = True
                        logger.warning(f"[卡死C10] CMD命令超时{timeout}s(子进程持管道/死循环) → 杀进程树+读残存 (cmd={cmd_short})")
                        stdout_b, stderr_b = _kill_and_read_output(proc)
                    else:
                        # [卡死场景C11] communicate有界收尾: 读清进程退出后残余管道 — 小欧 2026-08-06/08-07
                        _tail_out, _tail_err = proc.communicate(timeout=SUBPROCESS_TIMEOUT_SHORT)
                        if _tail_out:
                            _drain_out.append(_tail_out)
                        if _tail_err:
                            _drain_err.append(_tail_err)
                        stdout_b = b"".join(_drain_out)
                        stderr_b = b"".join(_drain_err)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    logger.warning(f"[卡死C10] CMD communicate超时 → 杀进程树+读残存 (cmd={cmd_short})")
                    stdout_b, stderr_b = _kill_and_read_output(proc)
            finally:
                try:
                    os.unlink(bat_path)
                except OSError:
                    pass
            stdout_str = _fix_encoding(_decode_bytes_safe(stdout_b))
            stderr_str = _fix_encoding(_decode_bytes_safe(stderr_b))
            returncode = proc.returncode if proc.returncode is not None else -1

        else:  # ── 【bash专属】: subprocess + 登录shell ──
            bash_exe = _find_bash()
            if not bash_exe:
                d = int((_time_mod.perf_counter() - t0) * 1000)
                llm = _build_execute_shell_command_llm_data("error", d, processed_command, -1,
                    shell_type, ERR_SHELL_EXCEPTION, "bash解释器未找到(Git Bash/WSL)",
                    timeout=timeout, cwd=cwd or "", hint="请检查Git Bash或WSL是否安装", cmd_short=cmd_short)
                return build_error(data={}, llm_data=llm)
            child_env = _sanitize_env()
            proc = subprocess.Popen(
                [bash_exe, "-l", "-c", processed_command],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd, env=child_env,
            )
            timed_out = False
            try:
                # [卡死场景C10] bash分支: communicate有界timeout, 超时→_kill_and_read_output(杀进程树+读残存) — 小欧 2026-08-06
                stdout_b, stderr_b = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                logger.warning(f"[卡死C10] Bash命令超时{timeout}s → 杀进程树+读残存 (cmd={cmd_short})")
                stdout_b, stderr_b = _kill_and_read_output(proc)
            stdout_str = _fix_encoding(_decode_bytes_safe(stdout_b))
            stderr_str = _fix_encoding(_decode_bytes_safe(stderr_b))
            returncode = proc.returncode if proc.returncode is not None else -1

        # ── 阶段 4【通用】: 后处理(UTF-8 编码修复) ──
        # 小欧 2026-07-20: 依 3.7 铁律删除 SHELL_OUTPUT_MAX_CHARS 头尾截断; 工具输出截断收口于阶段 4.5(50K/20K) — 2026-07-23 小欧更新
        if returncode == 0 and '>' in command:
            _convert_redirect_to_utf8(command, cwd)

        d = int((_time_mod.perf_counter() - t0) * 1000)
        # ── 阶段 4.5【通用】: Tool 输出截断 — 小欧 2026-07-23 ──
        _stdout_orig_len = len(stdout_str)
        _stderr_orig_len = len(stderr_str)
        _stderr_for_diag = stderr_str[:2000] if len(stderr_str) > 2000 else stderr_str  # 截断前保存原始值用于诊断(如PS/CMD混用检测) — 小欧 2026-07-28
        stdout_str, stdout_trunc = _truncate_shell_field(stdout_str, SHELL_OUTLIMIT_STDOUT_MAX_CHARS)
        stderr_str, stderr_trunc = _truncate_shell_field(stderr_str, SHELL_OUTLIMIT_STDERR_MAX_CHARS)
        data: Dict[str, Any] = {
            "stdout": stdout_str, "stderr": stderr_str,
        }
        if stdout_trunc or stderr_trunc:
            data["_truncated"] = True

        # ── 阶段 5【通用】: 构建 llm_data（截断已由阶段4.5统一处理，此处只判定状态+构建detail+调1次）
        _EXIT_CODE_MEANING = {
            1: "通用错误", 2: "命令语法错误", 3: "配置错误",
            5: "拒绝访问", 127: "命令未找到", 9009: "命令未找到(cmd)",
            3221225786: "程序崩溃(STATUS_DATATYPE_MISALIGNMENT)",
        }
        _exec_code = "success"
        _err_code = ""
        _detail = ""
        _hint = ""

        if timed_out:
            _exec_code = "warning"
            _err_code = ERR_SHELL_TIMEOUT
            _detail = f"命令执行超时({timeout}秒)"
            # 引导脚本化+增大超时 — 小欧 2026-08-07
            _hint = ("命令执行超时，建议: "
                     "1. 复杂代码请先写入相应的代码脚本文件再执行(规避单行引号转义) "
                     "2. 增大timeout参数(上限600) 3. 分步执行")
        elif returncode == 0 or returncode in (success_codes or []):
            stderr_clean = stderr_str.strip()
            if stderr_clean:
                benign_filtered = _filter_benign_stderr(stderr_str)
                if not benign_filtered.strip():
                    data["stderr"] = ""
                else:
                    _exec_code = "warning"
                    _detail = f"退出码{returncode}，标准错误{_stderr_orig_len}字符"
        else:
            _exec_code = "error"
            _err_code = ERR_SHELL_EXEC
            _detail = (stderr_str if stderr_str.strip()
                       else (stdout_str if stdout_str.strip()
                             else f"退出码{returncode}({_EXIT_CODE_MEANING.get(returncode, '未知错误')})"))
            if stderr_str.strip():
                if re.search(r"(command not found|not recognized|'[^']+' is not recognized|不是内部|不是可运行)", stderr_str, re.IGNORECASE):
                    _detail = f"[命令未找到] {_detail}"
                elif re.search(r"(syntax error|语法错误|parse error|unexpected token)", stderr_str, re.IGNORECASE):
                    _detail = f"[语法错误] {_detail}"
                elif re.search(r"(permission denied|access denied|拒绝访问|elevated)", stderr_str, re.IGNORECASE):
                    _detail = f"[权限错误] {_detail}"
            _hint = _shell_mismatch_hint(shell_type, _stderr_for_diag) or "请检查命令语法和参数"

        # 只调 1 次 _build_..._llm_data
        llm = _build_execute_shell_command_llm_data(
            _exec_code, d, processed_command, returncode,
            shell_type, _err_code, _detail,
            timeout=timeout, cwd=cwd or "",
            output_len=_stdout_orig_len, stderr_len=_stderr_orig_len, hint=_hint,
            cmd_short=cmd_short,
        )
        if _exec_code == "error":
            return build_error(data=data, llm_data=llm)
        if _exec_code == "warning":
            return build_warning(data=data, llm_data=llm)
        return build_success(data=data, llm_data=llm)

    except Exception as e:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, processed_command, -1,
            shell_type, ERR_SHELL_EXCEPTION, str(e),
            timeout=timeout, cwd=cwd or "", hint="命令执行异常,请检查命令和系统环境", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)
