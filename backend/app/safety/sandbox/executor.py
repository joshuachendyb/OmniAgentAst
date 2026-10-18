# -*- coding: utf-8 -*-
# executor.py — 编排入口(引用完整性闭合: imports/信号量/构造器/分派器全部落码) — 小欧 2026-08-24
# 编辑历史:
# 2026-08-25 - 小欧/小健 复核修复(真实 pwsh 后端/真实文件/真实参数反证): 逐字核查修正 7 类真实根因 bug(致命预检失效 + 若干类)
#   致命: pre_execute 误调 self._is_shell_tool(实例无此法)→每次预检抛 AttributeError 被捕获静默绕过, 沙箱预检整体失效; 改模块级 _is_shell_tool(小欧)
#   高危: _pre_execute_file_op 未调 normalize_params, 别名 src/dst/file/target/source 读不到 path→Path("")退化为复制 cwd 且对不存在源误放行(passed=True); 加别名归一 + 源存在性守卫转裁决(小欧)
#   中危: timeout 字符串与 int 比较抛 TypeError 被捕获成"内部异常"误分类; 改 int() 归一 + 超时超上限转 HITL(小欧)
#   中危: 副本重演命令裸拼 '{replica}' 致文件名含 ' 时 PowerShell 断裂误判危险型拒绝; 新增 _ps_literal_path 单引号转义(小欧)
#   低危: 删除不存在文件误报"超过影子副本上限"; 源不存在明确"源不存在"语义(源存在性守卫, 小欧)
#   中危: 容量只 sum(impacts.size) 漏算副本自身/误算删除释放; 改 _disk_usage 真实落盘占用(rglob 累加)(小欧)
#   中危: 越界扫描正则只认 C:\ 漏判 C:/ 正斜杠; _OUTSIDE_TARGET_RE 改 [\\/](小欧)
#   全部修复经"修复前 FAIL/修复后 PASS"逐类反证, 功能只增强不退化
# 2026-08-29 - 小沈 - 修复: shell/file_op 预检的同步 backend.run(subprocess 最长300s)经 asyncio.to_thread 离载到子线程, 释放事件循环不被冻结; 返回结构 BackendResult 不变
# 2026-09-17 小欧 - 复核: 规则5/7 blocked_reason 附带 stderr 尾部供 LLM 自纠(空则不加后缀, 截200字符)
# 2026-09-17 小欧 - 优化 reject 原因文字可读性: 类方法中5处 + shell 预检中5处 + file_op 预检中6处 reject 原因简化(去技术术语/截断过长内容)
# 2026-09-18 小欧 - TDD 过宽收敛: _READONLY_PREFIXES 常量新增五项(echo/pwd/dir/whoami/hostname);
#   _is_readonly_whitelisted 的 startswith 内联字面量改引用 _READONLY_PREFIXES 消除双源; PreCheckResult 新增 ruling_kind(默认 risky);
#   unsupported 分支置 ruling_kind="unsupported"(供沙箱 trusted 直放判据, 区分能力缺口与执行风险)
# 2026-09-18 小欧 - 弹窗过宽核查: _READONLY_PREFIXES 新增二十一项(git log/diff/show, python/node --version,
#   npm --version/ls, pip list/show/--version, docker ps/images, tasklist, ipconfig /all, systeminfo, netstat, ver,
#   test-path, kubectl get), 逐条过安全评审(任意无拼接符后缀仍只读); 否决 git branch/ipconfig 裸前缀等可写口
# 2026-10-02 - 小欧 - 注册名归位: _shell 集合 "shell"→"bash", 并清 2 个从未注册的死项(executeshellcommand/executeshellcommandsafety)
# 2026-10-04 - 小欧 - 只读白名单三元迁 app/utils/shell_readonly.py(tools 需共用、边界禁直连), 本文件同名转发零变化
# 2026-10-08 - 小欧 - 杀进程防护(事故驱动): 一旦预检在宿主真跑而词表漏判即防线自破 —
#   _scan_command_write_intent 改名 _scan_command_danger_intent 并扩职责, 前置调 shell_has_hidden_kill, 命中即转
#   HITL 不 run; 守卫2注释/日志同步"危险意图"; 新增 shell_has_hidden_kill import。旧名零残留不留别名。
# 2026-10-10 - 小欧 - 导入点位置更正: shell_has_hidden_kill / is_shell_readonly_whitelisted 由 app/utils/shell_readonly.py
#   改为 app.tools.fundamental.shell_static_guard(三类同域关注点已并回一处, 与 execute_shell_command.py /
#   shell_engine.py 同目录)。理由: 原落 utils 的依据"架构边界要求 tools 禁 import safety"经
#   tests/test_architecture_boundaries.py 实证不成立 — 该守卫只禁 "tools"→services/safety 单向,
#   safety→tools 合法(先例: path_tool_safety_checker 一直 import shell_command_risk), 无需中转 utils。
#   本文件属 app/safety, safety→tools 方向合法; 业务逻辑零变化, 仅改导入路径。
# 2026-10-14 - 小欧 - 本文件=权限信任框架之沙箱预检(pre_execute 影子副本执行, 上游 sandbox_gate.run_sandbox_gate, 总闸见 safety_checker 的 sandbox_required 置位)
# 2026-10-14 - 小欧 - 命令文本处理与工具分类符号迁出本模块(shell_static_guard 单一真源), 删本地定义改 import; 同批删已无引用的 re
import asyncio
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_config
from app.logger import logger
from app.tools.tools_alias_mapper import normalize_params, normalize_tool_name

from app.safety.sandbox.backend import BackendResult, JobObjectBackend
from app.safety.sandbox.workspace import FileImpact, SandboxWorkspace
# 2026-10-16 小欧 - 接线: shell 静态判定符号随整文件下沉到 app.safety.shell_command_process,
#   并跟正名。全部正名直用, 不留 as 旧名别名(禁止 backward, 旧名零残留),
#   故下方调用点同步正名。本模块是「越界写扫描 + 只读直通」两个消费方之一, 故随只读白名单一并下沉(不留越层 import)。
# 2026-10-18 小欧 订正(SRP 拆分后): shell_command_process.py 已按职责删除, 符号现分居
#   shell_sandbox_tables(越界表) / shell_readonly(只读白名单) / shell_tool_classify(工具分类) /
#   shell_text_atoms(文本原子) / shell_parse(动作解析); 下方 import 即现行真源。
from app.safety.shell_process_guard import shell_has_hidden_kill  # 2026-10-16: 自杀检查已归并 guard(不可隔离动词同源)
from app.safety.shell_sandbox_tables import (
    SHELL_OUTSIDE_TARGET_RE,
    SHELL_REDIRECT_RE,
    SHELL_REGISTRY_SYSTEM_VERBS,
    SHELL_SANDBOX_SELF_RE,
    SHELL_WRITE_INTENT_RE,
)
from app.safety.shell_readonly import is_shell_readonly_whitelisted
from app.safety.shell_tool_classify import is_shell_tool, shell_registry_key_exists
from app.safety.shell_text_atoms import shell_ps_literal_path, shell_resolve_env_fragment

_semaphore = asyncio.Semaphore(get_config().get("sandbox.max_concurrent_sandboxes", 3))   # 并发限流


@dataclass
class PreCheckResult:
    passed: bool                 # 是否放行真机
    blocked_reason: str = ""     # 失败原因(喂给LLM)
    needs_ruling: bool = False   # 未完成有效验证(超时/环境性失败: 工作区缺上下文找不到文件/目标被占用等);
                                 # 转 HITL 用户裁决而非危险型 blocked 反馈, 不作为危险拒绝;
                                 # 即原 timed_out 字段更名扩展(名实相符)
    ruling_kind: str = "risky"   # 裁决类型: risky=执行风险(受信也仍弹) / unsupported=能力缺口(受信直放) — 小欧-2026-09-18
    impacts: List[FileImpact] = field(default_factory=list)   # 影响文件清单(喂给LLM辅助判断) — 可变默认必须用field工厂
    stdout_tail: str = ""        # 输出尾部(截断4096字符)
    stderr_tail: str = ""        # 错误尾部(截断4096字符; 承载"stderr 原文喂 LLM"的字段)


# 只读白名单常量与判定已迁 app.safety.shell_readonly(2026-10-04 小欧, 单源见该模块; 2026-10-18 订正路径)
_ENV_STDERR_PATTERNS = ("cannot find path", "does not exist",
                        "being used by another process", "找不到路径")  # 环境性失败识别
# 2026-10-14 小欧 - _is_shell_tool 已迁 shell_static_guard, 原定义删(改由文件头 import)。
#   2026-10-18 小欧 订正: 该符号现居 app.safety.shell_tool_classify。


def _attach_stderr_tail(reason: str, stderr_tail: str) -> str:
    """危险型拒绝 reason 附 stderr 尾部供 LLM 自纠(stderr 原文随行),
    空则不加后缀避免悬空分隔符; 截 200 字符收敛进 LLM 反馈(全文已存 PreCheckResult.stderr_tail) — 小欧-2026-09-17"""
    tail = (stderr_tail or "").strip()
    if not tail:
        return reason
    return f"{reason} | {tail[:200]}"

# 2026-10-14 小欧 - 越界扫描器全套正则与 _resolve_env_fragment/_ps_literal_path 已迁 shell_static_guard, 原定义删。

def _is_outside_write_target(tail: str) -> Optional[bool]:
    """越界写意图三态判定: True=越界 / False=%TEMP%豁免 / None=非越界(相对路径)"""
    tail = shell_resolve_env_fragment(tail).lstrip("\"' ").lower()
    if not SHELL_OUTSIDE_TARGET_RE.search(tail):
        return None                      # 相对路径写: 正常进沙箱预检
    temp_root = tempfile.gettempdir().lower().rstrip("\\/")
    if tail.startswith(temp_root):
        if SHELL_SANDBOX_SELF_RE.search(tail):
            return True                  # 删沙箱自身必须命中
        return False                     # %TEMP% 其余写豁免(pip/npm 合法行为)
    return True                          # 命中越界写意图: 转 HITL 裁决


def _scan_command_danger_intent(command: str) -> bool:
    """危险意图扫描核心(预检不改状态): 越界写意图 或 不可隔离动词 → True 不运行 backend。

    2026-10-08 小欧 改名 write→danger 并扩职责(事故驱动): 原只判"越界写"漏杀进程类, 而预检是在宿主真跑,
    词表一漏即防线自破。两类一律只转 HITL 不判等级, 词表为持续维护项。
    重定向 `>`/`>>` 目标与写动词参数走同一套越界判定, 堵死
    `Get-Date > D:\\evil.ps1` 无写动词穿透全链路的逃逸(白名单侧已堵, 此为扫描器侧)。"""
    if shell_has_hidden_kill(command):
        return True                         # 2026-10-08 小欧: 杀进程/停服务绝不进 run(预检真跑=防线自破)
    for match in SHELL_WRITE_INTENT_RE.finditer(command):
        if match.group(0).rstrip().lower() in SHELL_REGISTRY_SYSTEM_VERBS:   # rstrip 双保险
            return True                     # 注册表/系统配置写无法被沙箱隔离, 命中即转裁决
        verdict = _is_outside_write_target(command[match.end(): match.end() + 200])   # 写动词后目标窗口
        if verdict is True:
            return True
    for match in SHELL_REDIRECT_RE.finditer(command):
        # 重定向 RHS 即写目标: 越界(D:\ 等)或篡改沙箱自身(自身豁免已并入判定)均命中;
        # %TEMP% 其余(False)与相对路径(None)放行进沙箱
        if _is_outside_write_target(match.group(1)) is True:
            return True
    return False                            # 无越界写意图: 正常预检


class SandboxExecutor:
    def __init__(self) -> None:
        cfg = get_config()   # 配置缺省值对齐
        self.workspace_root = Path(tempfile.gettempdir()) / "omniagent_sandbox"
        self.max_timeout_sec = cfg.get("sandbox.max_timeout_sec", 300)
        self.default_timeout_sec = cfg.get("sandbox.default_timeout_sec", 60)
        self.max_workspace_mb = cfg.get("sandbox.max_workspace_mb", 500)
        self.max_shadow_mb = cfg.get("sandbox.max_shadow_mb", 100)

    def _dispatch_backend(self) -> JobObjectBackend:
        """直线 if 分派(KISS-DIRECT); backend 键为扩展位预留, 当前唯一合法值 job_object"""
        backend_key = get_config().get("sandbox.backend", "job_object")
        if backend_key != "job_object":
            raise ValueError(f"未知 sandbox.backend 配置值: {backend_key}(当前仅支持 job_object)")
        return JobObjectBackend(process_memory_limit_mb=get_config().get("sandbox.process_memory_limit_mb", 2048))

    async def pre_execute(self, tool_name: str, params: Dict) -> PreCheckResult:
        # 沙箱预检唯一触发依据=safety_result.sandbox_required, 上游 run_sandbox_gate — 小欧-2026-10-14
        # 总开关唯一判定点: 入口单点短路; checker 四条置位路径不读配置,
        # 开关在唯一入口生效不存在遗漏分支; False 时返回 passed=True, 行为与实施前完全一致
        if not get_config().get("sandbox.enabled", True):
            logger.info(f"[sandbox][exec] 总开关关闭, 直通免预检: tool={tool_name}")
            return PreCheckResult(passed=True)
        logger.info(f"[sandbox][exec] 预检开始: tool={tool_name}, 类型={'shell' if is_shell_tool(tool_name) else 'file_op'}")
        async with _semaphore:   # 并发限流(默认3 可配置)
            if is_shell_tool(tool_name):   # 原为 self.is_shell_tool(实例无此法, 致每次预检抛 AttributeError 被静默绕过)
                # 统一入口(action_handler 唯一调用点): shell 类→_pre_execute_shell
                timeout_sec = params.get("timeout") or get_config().get("sandbox.default_timeout_sec", 60)
                return await self._pre_execute_shell(params.get("command", ""), params, timeout_sec)
            # 文件类→_pre_execute_file_op
            return await self._pre_execute_file_op(tool_name, params)

    def _classify(self, result: BackendResult, impacts: List[FileImpact]) -> PreCheckResult:
        """判定分流算法代码化(顺序靠前优先; 规则1预扫描与守卫1已在 run 前返回, 不入本方法)"""
        if result.timed_out:
            # 规则2 超时: run 被硬上限截断, 未完成有效验证(数据来源 BackendResult.timed_out)
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"执行预检超时（超过{self.max_timeout_sec}秒）",
                                  impacts=impacts,
                                  stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
        escaped = [i for i in impacts if not self._in_workspace_or_temp(i.path)]
        if result.rc == 0 and not escaped:
            # 规则3 放行: rc==0 且影响面全部落在工作区或系统临时目录(%TEMP% 豁免)
            return PreCheckResult(passed=True, impacts=impacts)
        if escaped:
            # 规则4 越界交用户裁决(不限 rc)。
            # diff_impacts 只在工作区 rglob, 本分支当前不可达(防御性预留);
            # 运行期越界探测完全依赖 run 前的危险意图预扫描(守卫2); 未来外扩 %TEMP%/全盘增量扫描后才可激活
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason="操作影响范围超出沙箱",
                                  impacts=impacts,
                                  stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
        if impacts:
            # 规则5 危险型: rc!=0 且 impacts 非空且全在工作区内("非空"前置, 防空集陷阱);
            # stderr 尾部随反馈下发
            return PreCheckResult(passed=False,
                                  blocked_reason=_attach_stderr_tail("沙箱内执行失败，影响了文件", result.stderr_tail),
                                  impacts=impacts,
                                  stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
        if any(p in result.stderr_tail.lower() for p in _ENV_STDERR_PATTERNS):
            # 规则6 环境性失败: 非命令有害, 转用户裁决避免 LLM 原样重发死循环
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason="环境问题导致验证未完成",
                                  stderr_tail=result.stderr_tail)
        # 规则7 其余 rc!=0: 危险型反馈 LLM 自纠(stderr 原文随行)
        return PreCheckResult(passed=False,
                              blocked_reason=_attach_stderr_tail("沙箱内执行失败", result.stderr_tail),
                              stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)

    def _in_workspace_or_temp(self, path: str) -> bool:
        """允许域判定: 沙箱工作区 + 系统临时目录(%TEMP%)"""
        resolved = str(Path(os.path.abspath(os.path.expandvars(path)))).lower()
        return (resolved.startswith(str(self.workspace_root).lower())
                or resolved.startswith(tempfile.gettempdir().lower()))

    async def _pre_execute_shell(self, command: str, params: Dict, timeout_sec: int) -> PreCheckResult:
        """shell 类预检(唯一完整实现): 守卫1超上限 → 守卫2危险意图扫描 → 白名单 → run → finally 清理"""
        # 守卫1: 声明 timeout 超硬上限 -> 不创建工作区、不运行 backend, 直接转 HITL
        # timeout 可能由 LLM 以字符串返回, 必须归一为 int 再比较, 否则 str>int 抛 TypeError 被捕获成"内部异常"误分类
        declared = params.get("timeout")
        if declared is not None:
            try:
                declared = int(declared)
            except (TypeError, ValueError):
                declared = None
        if declared and declared > self.max_timeout_sec:
            logger.warning(f"[sandbox][exec] 声明timeout超硬上限转HITL: declared={declared}s, 上限={self.max_timeout_sec}s")
            return PreCheckResult(
                passed=False, needs_ruling=True,
                blocked_reason=f"工具执行超时设置不合理（{declared}秒），请调整后重试",
            )
        # 守卫2: 命令文本危险意图扫描(越界写 + 杀进程/停服务) -> 不运行 backend, 直接转 HITL(预检不改状态)
        if _scan_command_danger_intent(command):
            logger.warning(f"[sandbox][exec] 命令含危险意图, 转HITL: command_head={command[:120]!r}")
            return PreCheckResult(
                passed=False, needs_ruling=True,
                blocked_reason="命令包含危险操作，需要用户确认",
            )
        # 白名单快速通道(定序: 必须在危险意图扫描之后判定, 防重定向逃逸绕过扫描)
        if is_shell_readonly_whitelisted(command):
            logger.info(f"[sandbox][exec] 只读白名单直通放行真机: command_head={command[:120]!r}")
            return PreCheckResult(passed=True)   # 只读直通: 免预检放行真机
        backend = self._dispatch_backend()
        workspace = SandboxWorkspace(max_workspace_mb=self.max_workspace_mb,
                                     max_shadow_mb=self.max_shadow_mb)
        workspace.create()
        try:
            # timeout_sec 可能由 LLM 以字符串返回, 归一为 int 再夹取硬上限, 否则 min(str,int) 抛 TypeError
            try:
                _to = int(timeout_sec)
            except (TypeError, ValueError):
                _to = self.default_timeout_sec
            logger.info(f"[sandbox][exec] shell 预检 run 启动: timeout={min(_to, self.max_timeout_sec)}s")
            # 2026-08-29 小沈: 同步 subprocess 经 to_thread 离载子线程, 事件循环不被冻结(并发任务不被延迟)
            result = await asyncio.to_thread(backend.run, command, workspace.path, min(_to, self.max_timeout_sec))
            logger.info(f"[sandbox][exec] shell 预检 run 结束: rc={result.rc}, timed_out={result.timed_out}")
            impacts = workspace.diff_impacts()
            used = self._disk_usage(workspace.path)   # 以工作区真实磁盘占用来判定容量(防副本自身漏算/删除误算)
            if not workspace.check_capacity(used):
                # 工作区上限接线(原方法存在但无人调用), 超限拒绝预检转 HITL 强确认
                logger.warning(f"[sandbox][exec] 工作区超上限转HITL: used={used}B, 上限={self.max_workspace_mb}MB")
                return PreCheckResult(passed=False, needs_ruling=True,
                                       blocked_reason=f"沙箱工作区写入数据量超限（{used}字节）",
                                       impacts=impacts,
                                       stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
            return self._classify(result, impacts)   # 判定分流算法(规则2-7)
        except OSError as exc:
            # Job Object 收编失败(进程已提权等, assign 上抛非静默) → 升级 HITL 强确认而非静默放行
            logger.warning(f"[sandbox][exec] Job Object 收编失败转HITL: {exc}")
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason="沙箱环境配置异常，需要用户确认")
        except Exception as exc:
            # 非 OSError 异常(编码/内部错误/注入测试)不得穿透到 action_handler 炸掉整批调用,
            # 统一转 needs_ruling 交用户裁决(资源由下方 finally 回收, 对齐异常注入用例)
            logger.warning(f"[sandbox][exec] 预检内部异常转HITL: {exc}")
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason="沙箱预检器内部异常，需要用户确认")
        finally:
            backend.cleanup()      # TerminateJobObject 杀树 + CloseHandle(句柄守恒; 含 proc 补充收割)
            try:
                workspace.destroy()
            except OSError as exc:
                # 销毁最终失败仅告警不抛: finally 中 raise 会覆盖已生成的放行结果,
                # 把无害磁盘残留(仅占 %TEMP%)升级成整次调用报错
                logger.warning(f"[sandbox] workspace destroy failed(残留 %TEMP%, 无功能影响): {exc}")

    async def _pre_execute_file_op(self, tool_name: str, params: Dict) -> PreCheckResult:
        """Phase 2: 高危文件操作预检 — delete/copy/move 影子副本预演 + registry 静态分析"""
        normalized = normalize_tool_name(tool_name)
        if normalized not in ("registrywrite", "registrydelete", "delete", "copy", "move"):
            # 未支持的操作类型不猜分支: 原 write/extractarchive 落入 else 被当 move
            # 重演副本, rc=0 产生虚假 passed=True 放行(预检形同虚设); 一律转用户裁决
            logger.warning(f"[sandbox][exec] 未支持操作类型转HITL: op={normalized}")
            return PreCheckResult(passed=False, needs_ruling=True,
                                  ruling_kind="unsupported",           # 能力缺口标记, 供沙箱受信直放判据 — 小欧-2026-09-18
                                  blocked_reason=f"沙箱预检器暂不支持此操作类型: {normalized}")
        # 参数别名归一(与真实工具分发一致: tools_alias_mapper.PARAM_ALIASES 将 src/file/target/source
        # 等映射到 path/dest)。不归一则读不到源路径, 会以 Path("") 退化为复制当前工作目录, 预检形同虚设
        params = normalize_params(normalized, params)[0]
        if normalized in ("registrywrite", "registrydelete"):
            # 注册表无法影子副本(局限): 仅静态检查: 键存在性/值类型/递归范围统计, 不做动态试删
            reg_path = params.get("path") or params.get("key", "")
            exists = shell_registry_key_exists(reg_path)            # winreg 标准库只读探测(实施时落地)
            return PreCheckResult(
                passed=True,
                blocked_reason=f"registry 静态分析(仅报告不试删): key={reg_path}, 存在={exists}",
                impacts=[])
        _backend = None
        src = Path(params.get("path") or params.get("source_path") or "")
        if not src.exists():
            # 源不存在: 无法做有效预演(复制不存在的源无任何意义), 转 HITL 裁决而非退化为复制 cwd 误放行
            logger.info(f"[sandbox][exec] 源不存在转HITL: {src}")
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"源文件不存在，无法执行操作: {src.name}")
        _backend = self._dispatch_backend()   # 若此处异常, finally 判 None 不误清
        workspace = SandboxWorkspace(max_workspace_mb=self.max_workspace_mb,
                                     max_shadow_mb=self.max_shadow_mb)
        workspace.create()
        try:
            replica = workspace.shadow_copy(src)
            if replica == src:
                # 超限跳过副本 → 未完成有效验证转裁决(降级规则, 同通道)
                logger.warning(f"[sandbox][exec] 目标超影子副本上限转HITL: {src}, 上限={self.max_shadow_mb}MB")
                return PreCheckResult(passed=False, needs_ruling=True,
                                      blocked_reason=f"文件过大（超过{self.max_shadow_mb}MB），无法在沙箱中验证")
            workspace.snapshot_files()   # 以副本为 diff 基线, 防副本自身被误报为 added 影响面
            op_result = await self._replay_file_op_on_replica(_backend, normalized, params, replica, workspace.path)
            impacts = workspace.diff_impacts()
            used = self._disk_usage(workspace.path)   # 以工作区真实磁盘占用来判定容量(防副本自身漏算/删除误算)
            if not workspace.check_capacity(used):
                # 工作区上限接线(同 shell 流程)
                logger.warning(f"[sandbox][exec] 工作区超上限转HITL(file_op): used={used}B, 上限={self.max_workspace_mb}MB")
                return PreCheckResult(passed=False, needs_ruling=True,
                                       blocked_reason=f"沙箱工作区写入数据量超限（{used}字节）",
                                       impacts=impacts, stderr_tail=op_result.stderr_tail)
            return self._classify(op_result, impacts)   # 复用同一套判定分流算法(DRY)
        except OSError as exc:
            # 影子副本/重演失败(源被占用/不可读等) → 未完成有效验证转裁决, 不穿透炸批(对齐 shell 流)
            logger.warning(f"[sandbox][exec] 影子副本预演失败转HITL: {exc}")
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason="文件操作预演失败，需要用户确认")
        except Exception as exc:
            # 非 OSError 异常同样不穿透(对齐 shell 流)
            logger.warning(f"[sandbox][exec] 文件预检内部异常转HITL: {exc}")
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason="文件预检器内部异常，需要用户确认")
        finally:
            if _backend is not None:
                try:
                    _backend.cleanup()   # 复用后端清理契约(句柄守恒; 对齐 shell 流, 防 file_op 路径孤儿进程/资源残留)
                except Exception:
                    pass
            workspace.destroy()

    @staticmethod
    async def _replay_file_op_on_replica(backend: JobObjectBackend, normalized: str,
                                    params: Dict, replica: Path, workspace: Path) -> BackendResult:
        """对工作区副本执行与原操作等价的动作 → BackendResult。
        复用 backend.run(原为手写 Popen: 无 Job 包裹、TimeoutExpired 未接会泄漏进程、
        且经 self 调用模块函数本会 AttributeError), Job 包裹/超时杀树/cleanup 契约全部复用(DRY)。
        2026-08-29 小沈: 改为 async, 内部 backend.run 经 asyncio.to_thread 离载子线程, 事件循环不被冻结
        delete→删除副本树; copy/move→在副本内重演目标变换。"""
        logger.info(f"[sandbox][exec] 重演文件操作: op={normalized}, replica={replica}")
        if normalized == "delete":
            replay_cmd = f"Remove-Item -LiteralPath {shell_ps_literal_path(replica)} -Recurse -Force"
        elif normalized == "copy":
            dest = replica.parent / Path(params.get("dest", params.get("path", "copied"))).name
            replay_cmd = f"Copy-Item -LiteralPath {shell_ps_literal_path(replica)} -Destination {shell_ps_literal_path(dest)} -Force"
        else:   # move: 副本内自移即验证可行性
            moved = replica.parent / "moved"
            replay_cmd = f"Move-Item -LiteralPath {shell_ps_literal_path(replica)} -Destination {shell_ps_literal_path(moved)} -Force"
        return await asyncio.to_thread(backend.run, replay_cmd, workspace, 60)

    def _disk_usage(self, ws_path) -> int:
        """工作区真实磁盘占用(字节): 容量判定应以实际落盘文件为准, 既包含影子副本自身占用,
        又不会把"删除影响"误算为已用(删除是释放而非占用), 修正容量口径欠额放行/超额误拦"""
        total = 0
        for p in Path(ws_path).rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total


_executor: Optional["SandboxExecutor"] = None


def get_sandbox_executor() -> "SandboxExecutor":
    """模块级单例(__init__.py 导出; action_handler 唯一调用入口)"""
    global _executor
    if _executor is None:
        _executor = SandboxExecutor()
    return _executor


# 2026-10-14 小欧 - _registry_key_exists 已迁 shell_static_guard, 原定义删。
