# -*- coding: utf-8 -*-
# executor.py — 编排入口(v1.19 P7 引用完整性闭合: imports/信号量/构造器/分派器全部落码) — 小欧 2026-08-24
# 编辑历史:
# 2026-08-25 - 小欧/小健 三堂会审修复(北京老陈驱动, 真实 pwsh 后端/真实文件/真实参数反证, 严禁伪代码/弄虚): 逐字核查修正 7 类真实根因 bug(BUG-0 致命 + A~F)
#   BUG-0(致命): pre_execute 误调 self._is_shell_tool(实例无此法)→每次预检抛 AttributeError 被 M4 兜底静默绕过, 沙箱预检整体失效; 改模块级 _is_shell_tool(小欧)
#   BUG-A(高): _pre_execute_file_op 未调 normalize_params, 别名 src/dst/file/target/source 读不到 path→Path("")退化为复制 cwd 且对不存在源误放行(passed=True); 加别名归一 + 源存在性守卫转裁决(小欧)
#   BUG-B(中): timeout 字符串与 int 比较抛 TypeError 被兜底成"内部异常"误分类; 改 int() 归一 + 守卫①明确超时超上限转 HITL(小欧)
#   BUG-C(中): 副本重演命令裸拼 '{replica}' 致文件名含 ' 时 PowerShell 断裂误判危险型拒绝; 新增 _ps_literal_path 单引号转义(小欧)
#   BUG-D(低): 删除不存在文件误报"超过影子副本上限"; 源不存在明确"源不存在"语义(源存在性守卫, 小欧)
#   BUG-E(中): 容量只 sum(impacts.size) 漏算副本自身/误算删除释放; 改 _disk_usage 真实落盘占用(rglob 累加)(小欧)
#   BUG-F(中): F-B 扫描正则只认 C:\ 漏判 C:/ 正斜杠; _OUTSIDE_TARGET_RE 改 [\\/](小欧)
#   全部修复经"修复前 FAIL/修复后 PASS"逐类反证, 功能只增强不退化
import asyncio
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.config import get_config
from app.logger import logger
from app.tools.tools_alias_mapper import normalize_params, normalize_tool_name

from app.safety.sandbox.backend import BackendResult, JobObjectBackend
from app.safety.sandbox.workspace import FileImpact, SandboxWorkspace

_semaphore = asyncio.Semaphore(get_config().get("sandbox.max_concurrent_sandboxes", 3))   # 并发限流(3.1.3)


@dataclass
class PreCheckResult:
    passed: bool                 # 是否放行真机
    blocked_reason: str = ""     # 失败原因(喂给LLM)
    needs_ruling: bool = False   # 未完成有效验证(超时/环境性失败: 工作区缺上下文找不到文件/目标被占用等)——
                                 # 转 HITL 用户裁决而非危险型 blocked 反馈, 不作为危险拒绝;
                                 # 即 v1.7 的 timed_out 字段更名扩展(v1.10 名实相符)
    impacts: List[FileImpact] = field(default_factory=list)   # 影响文件清单(喂给LLM辅助判断) — 可变默认必须用field工厂(v1.12 F7)
    stdout_tail: str = ""        # 输出尾部(截断4096字符)
    stderr_tail: str = ""        # 错误尾部(截断4096字符; v1.22 W4: 4.2 条件1/2"stderr 原文喂 LLM"的承载字段)

# —— 第四章判定规则的真实代码落点(v1.18 按北京老陈要求全部代码化) ———
_READONLY_PREFIXES = ("get-", "ls", "cat", "type", "git status")      # 4.1#4 只读白名单前缀
_FAST_CHANNEL_FORBIDDEN = ("|", ";", "&", ">", ">>")                  # 单命令收紧(v1.10 FP1 管道/分号/调用符 + v1.17 N5 重定向)
_ENV_STDERR_PATTERNS = ("cannot find path", "does not exist",
                        "being used by another process", "找不到路径")  # 4.2 规则6 环境性失败识别(FP2)
def _is_shell_tool(tool_name: str) -> bool:
    """shell 类判定以注册表真实工具名为准(v1.25 F4 回归修正): execute_shell_command 注册名'shell'且
    category=FUNDAMENTAL(fundamental_register.py:122, 2026-07-28自SHELL迁入), 不能仅凭ToolCategory.SHELL
    判定(该枚举仅'which'); 显式列 shell 执行类归一名, 新增须同步加入本集合"""
    _shell = frozenset({"shell", "executeshellcommand", "executeshellcommandsafety"})
    return normalize_tool_name(tool_name) in _shell

# —— F-B 写意图扫描器(v1.19 P4 真实实现, v1.21 Z1/Z10 补重定向与词表): 只判越界写意图, 不判危险等级 ——
_WRITE_CMD_RE = re.compile(
    r"\b(?:Remove-Item|rm|ri|del|erase|rd|rmdir|Move-Item|mi|Copy-Item|cpi|cp|mv"
    r"|New-Item|ni|Set-Content|Add-Content|ac|Out-File|Expand-Archive"
    r"|reg(?:\.exe)?(?=\s|$)|setx|regedit(?:\.exe)?(?=\s|$))\b",
    re.IGNORECASE)
# v1.23 V-A: reg/regedit 的边界由 (?=\s|$) 前瞻断言(不消耗字符)——原 (?:\s|$) 会把尾随空格
# 吃进 group(0)("reg " ∉ _REGISTRY_SYSTEM_VERBS), 致 v1.22 W1 注册表特判永不命中、红洞未堵。
# 前瞻后 group(0)="reg" 干净可查集合; 双空格场景亦因 lookahead 不消费而照常命中。
_REDIRECT_RE = re.compile(r">>?\s*\"?([^\"\r\n<>|;]+)")   # v1.21 Z1: 重定向目标提取(> 与 >> 同权)
_OUTSIDE_TARGET_RE = re.compile(
    r"(?:"
    r"\b[a-z]:[\\/]"                 # 绝对盘符 C:\ D:\ / C:/ D:/ (正斜杠亦属越界写, 防逃逸)
    r"|\\\\[\w.\-]+\\"               # UNC \\host\share\
    r"|\bhk(?:lm|cu|cr|u|cc):[\\/]"  # 注册表驱动器 HKLM:/HKCU: 等
    r"|\$env:[\w]+[\\/]"             # $env:XXX\ 展开(解析前形态)
    r"|[\"']?~[\\/]"                 # ~ 家目录展开
    r")", re.IGNORECASE)
_SANDBOX_SELF_RE = re.compile(r"omniagent_sandbox", re.IGNORECASE)   # N7 carve-out 标识
_REGISTRY_SYSTEM_VERBS = frozenset({"reg", "reg.exe", "regedit", "regedit.exe", "setx"})
# v1.22 W1: 注册表/系统配置写动词命中即拦——命令行写法目标多为无冒号 `HKLM\...`,
# 不匹配带冒号的 _OUTSIDE_TARGET_RE; 且 Job Object 完全不隔离注册表/环境变量,
# 沙箱内真实执行=真写系统。与 G1/2.4「registry 类只静态分析不动态执行」同哲学, 无需看目标形态。


def _resolve_env_fragment(fragment: str) -> str:
    """目标窗口内 $env:XXX → 实际值(FP3 豁免判定前先展开, 防 $env:TEMP 逃过盘符正则)"""
    return re.sub(r"\$env:(\w+)", lambda m: os.environ.get(m.group(1), m.group(0)), fragment,
                  flags=re.IGNORECASE)


def _ps_literal_path(p) -> str:
    """PowerShell -LiteralPath 字面量引号: 单引号包裹, 内部单引号转义为 '' (防路径含 ' 时命令行断裂)"""
    return "'" + str(p).replace("'", "''") + "'"


def _is_outside_write_target(tail: str) -> Optional[bool]:
    """越界写意图三态判定(v1.21 Z1 抽出共用): True=越界 / False=%TEMP%豁免 / None=非越界(相对路径)"""
    tail = _resolve_env_fragment(tail).lstrip("\"' ").lower()
    if not _OUTSIDE_TARGET_RE.search(tail):
        return None                      # 相对路径写: 正常进沙箱预检
    temp_root = tempfile.gettempdir().lower().rstrip("\\/")
    if tail.startswith(temp_root):
        if _SANDBOX_SELF_RE.search(tail):
            return True                  # N7: 删沙箱自身必须命中
        return False                     # FP3: %TEMP% 其余写豁免(pip/npm 合法行为)
    return True                          # 命中越界写意图: 转 HITL 裁决


def _scan_command_write_intent(command: str) -> bool:
    """F-B 核心(保 2.1 预检不改状态): 写动词/重定向目标 越界 → True 不运行 backend。
    v1.21 Z1: 重定向 `>`/`>>` 目标与写动词参数走同一套越界判定——堵死
    `Get-Date > D:\\evil.ps1` 无写动词穿透全链路的逃逸(N5 白名单侧已堵, 此为扫描器侧)。
    正则风格参考 execute_shell_command_safety.py 既有危险命令匹配; 本扫描只判"越界写意图"不判危险等级;
    Job Object 非硬墙(2.5.1)物理拦不住越界写, run 前本预扫描是唯一防线, 词表为持续维护项(见 R7)。"""
    for match in _WRITE_CMD_RE.finditer(command):
        if match.group(0).rstrip().lower() in _REGISTRY_SYSTEM_VERBS:   # v1.23 V-A: rstrip 双保险
            return True                     # v1.22 W1: 注册表/系统配置写无法被沙箱隔离, 命中即转裁决
        verdict = _is_outside_write_target(command[match.end(): match.end() + 200])   # 写动词后目标窗口
        if verdict is True:
            return True
    for match in _REDIRECT_RE.finditer(command):
        # 重定向 RHS 即写目标(Z1): 越界(D:\ 等)或篡改沙箱自身(N7 carve-out 已并入判定)均命中;
        # %TEMP% 其余(False)与相对路径(None)放行进沙箱
        if _is_outside_write_target(match.group(1)) is True:
            return True
    return False                            # 无越界写意图: 正常预检


def _is_readonly_whitelisted(command: str) -> bool:
    """4.1#4 只读白名单快速通道判定(必须在 _scan_command_write_intent 之后调用, 定序防重定向逃逸绕过扫描)"""
    lowered = command.strip().lower()
    if not lowered.startswith(("get-", "ls", "cat", "type", "git status")):
        return False
    return not any(op in command for op in _FAST_CHANNEL_FORBIDDEN)


class SandboxExecutor:
    def __init__(self) -> None:
        cfg = get_config()   # 配置缺省值兜底对齐 3.2.4 M4
        self.workspace_root = Path(tempfile.gettempdir()) / "omniagent_sandbox"
        self.max_timeout_sec = cfg.get("sandbox.max_timeout_sec", 300)
        self.default_timeout_sec = cfg.get("sandbox.default_timeout_sec", 60)
        self.max_workspace_mb = cfg.get("sandbox.max_workspace_mb", 500)
        self.max_shadow_mb = cfg.get("sandbox.max_shadow_mb", 100)

    def _dispatch_backend(self) -> JobObjectBackend:
        """直线 if 分派(KISS-DIRECT); backend 键为扩展位预留(2.3), 当前唯一合法值 job_object"""
        backend_key = get_config().get("sandbox.backend", "job_object")
        if backend_key != "job_object":
            raise ValueError(f"未知 sandbox.backend 配置值: {backend_key}(当前仅支持 job_object)")
        return JobObjectBackend(process_memory_limit_mb=get_config().get("sandbox.process_memory_limit_mb", 2048))

    async def pre_execute(self, tool_name: str, params: Dict) -> PreCheckResult:
        # 4.1#5 总开关唯一判定点(v1.10): 入口单点短路——checker 四条置位路径不读配置,
        # 开关在唯一入口生效不存在遗漏分支; False 时返回 passed=True, 行为与实施前完全一致
        if not get_config().get("sandbox.enabled", True):
            return PreCheckResult(passed=True)
        async with _semaphore:   # 并发限流(3.1.3, 默认3 可配置)
            if _is_shell_tool(tool_name):   # BUG修复: 原为 self._is_shell_tool(实例无此法, 致每次预检抛 AttributeError 被 M4 兜底静默绕过)
                # 统一入口(action_handler 唯一调用点): shell 类→_pre_execute_shell
                timeout_sec = params.get("timeout") or get_config().get("sandbox.default_timeout_sec", 60)
                return await self._pre_execute_shell(params.get("command", ""), params, timeout_sec)
            # 文件类→_pre_execute_file_op
            return await self._pre_execute_file_op(tool_name, params)

    def _classify(self, result: BackendResult, impacts: List[FileImpact]) -> PreCheckResult:
        """4.2 判定分流算法代码化(顺序靠前优先; 规则1预扫描与守卫①已在 run 前返回, 不入本方法)"""
        if result.timed_out:
            # 规则2 超时: run 被硬上限截断, 未完成有效验证(数据来源 BackendResult.timed_out, v1.17 N4)
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"预检超硬上限{self.max_timeout_sec}s被截断",
                                  impacts=impacts,
                                  stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
        escaped = [i for i in impacts if not self._in_workspace_or_temp(i.path)]
        if result.rc == 0 and not escaped:
            # 规则3 放行: rc==0 且影响面全部落在工作区或系统临时目录(%TEMP% 豁免, v1.10 FP3)
            return PreCheckResult(passed=True, impacts=impacts)
        if escaped:
            # 规则4 越界交用户裁决(v1.18 N11: 不限 rc)。
            # v1.21 Z2 明示: diff_impacts 只在工作区 rglob, 本分支当前不可达(防御性预留)——
            # 运行期越界探测完全依赖 run 前的 F-B 预扫描(守卫②); 未来外扩 %TEMP%/全盘增量扫描后才可激活
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason="检测到工作区外影响: " + ", ".join(i.path for i in escaped),
                                  impacts=impacts,
                                  stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
        if impacts:
            # 规则5 危险型: rc!=0 且 impacts 非空且全在工作区内("非空"前置=v1.17 N6 防空集陷阱);
            # v1.22 W4: stderr 尾部随反馈下发(4.2 条件1/2 承诺的承载)
            return PreCheckResult(passed=False,
                                  blocked_reason=(f"沙箱内试执行失败(rc={result.rc})且产生工作区影响面"
                                                  f" | stderr: ...{result.stderr_tail[-256:]}"),
                                  impacts=impacts,
                                  stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
        if any(p in result.stderr_tail.lower() for p in _ENV_STDERR_PATTERNS):
            # 规则6 环境性失败: 非命令有害, 转用户裁决避免 LLM 原样重发死循环(v1.10 FP2)
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"未完成有效验证(环境性): ...{result.stderr_tail[-256:]}",
                                  stderr_tail=result.stderr_tail)
        # 规则7 其余 rc!=0: 危险型反馈 LLM 自纠(stderr 原文随行, v1.22 W4)
        return PreCheckResult(passed=False,
                              blocked_reason=(f"沙箱内试执行失败(rc={result.rc})"
                                              f" | stderr: ...{result.stderr_tail[-256:]}"),
                              stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)

    def _in_workspace_or_temp(self, path: str) -> bool:
        """4.2 条件3 允许域判定: 沙箱工作区 ∪ 系统临时目录(%TEMP%)"""
        resolved = str(Path(os.path.abspath(os.path.expandvars(path)))).lower()
        return (resolved.startswith(str(self.workspace_root).lower())
                or resolved.startswith(tempfile.gettempdir().lower()))

    async def _pre_execute_shell(self, command: str, params: Dict, timeout_sec: int) -> PreCheckResult:
        """shell 类预检(唯一完整实现, v1.20 整体化): 守卫①超上限 → 守卫②F-B扫描 → 白名单 → run → finally 清理"""
        # 守卫①(F-A): 声明 timeout 超硬上限 -> 不创建工作区、不运行 backend, 直接转 HITL(4.1#7)
        # timeout 可能由 LLM 以字符串返回, 必须归一为 int 再比较, 否则 str>int 抛 TypeError 被兜底成"内部异常"误分类
        declared = params.get("timeout")
        if declared is not None:
            try:
                declared = int(declared)
            except (TypeError, ValueError):
                declared = None
        if declared and declared > self.max_timeout_sec:
            return PreCheckResult(
                passed=False, needs_ruling=True,
                blocked_reason=f"工具声明 timeout={declared}s 超硬上限 {self.max_timeout_sec}s, 等待不可接受, 转用户裁决",
            )
        # 守卫②(F-B): 命令文本越界写意图扫描 -> 不运行 backend, 直接转 HITL(保 2.1 预检不改状态)
        if _scan_command_write_intent(command):
            return PreCheckResult(
                passed=False, needs_ruling=True,
                blocked_reason="命令含越界写意图(绝对路径/UNC/注册表驱动器/$env/~/), sandbox 不执行, 转用户裁决",
            )
        # 白名单快速通道(v1.17 N3/N5 定序: 必须在 F-B 扫描之后判定, 防重定向逃逸绕过扫描)
        if _is_readonly_whitelisted(command):
            return PreCheckResult(passed=True)   # 只读直通: 免预检放行真机(4.1#4)
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
            result = backend.run(command, workspace.path, min(_to, self.max_timeout_sec))
            impacts = workspace.diff_impacts()
            used = self._disk_usage(workspace.path)   # 以工作区真实磁盘占用来判定容量(防副本自身漏算/删除误算)
            if not workspace.check_capacity(used):
                # v1.22 W5: 3.1.1 工作区上限接线(原方法存在但无人调用)——超限拒绝预检转 HITL 强确认
                return PreCheckResult(passed=False, needs_ruling=True,
                                       blocked_reason=f"沙箱工作区写入 {used} 字节超上限 {self.max_workspace_mb}MB, 转用户裁决",
                                       impacts=impacts,
                                       stdout_tail=result.stdout_tail, stderr_tail=result.stderr_tail)
            return self._classify(result, impacts)   # 4.2 判定分流算法(规则2-7)
        except OSError as exc:
            # R3(v1.19 P6): Job Object 收编失败(进程已提权等, assign 上抛非静默) → 升级 HITL 强确认而非静默放行
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"Job Object 收编失败, 转用户裁决: {exc}")
        except Exception as exc:
            # v1.21 Z9: 非 OSError 异常(编码/内部错误/注入测试)不得穿透到 action_handler 炸掉整批调用,
            # 统一转 needs_ruling 交用户裁决(资源由下方 finally 回收, 对齐 8.5 异常注入用例)
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"预检器内部异常, 未完成有效验证: {exc}")
        finally:
            backend.cleanup()      # TerminateJobObject 杀树 + CloseHandle(8.7 句柄守恒断言; v1.21 Z4 含 proc 兜底收割)
            try:
                workspace.destroy()
            except OSError as exc:
                # v1.21 Z5: 销毁最终失败仅告警不抛——finally 中 raise 会覆盖已生成的放行结果,
                # 把无害磁盘残留(R5: 仅占 %TEMP%)升级成整次调用报错, 与 R5 承诺矛盾
                logger.warning(f"[sandbox] workspace destroy failed(残留 %TEMP%, 无功能影响): {exc}")

    async def _pre_execute_file_op(self, tool_name: str, params: Dict) -> PreCheckResult:
        """Phase 2(v1.19 P5): 高危文件操作预检 — delete/copy/move 影子副本预演 + registry 静态分析"""
        normalized = normalize_tool_name(tool_name)
        if normalized not in ("registrywrite", "registrydelete", "delete", "copy", "move"):
            # v1.23 V-B: 未支持的操作类型不猜分支——原 writetext/extractarchive 落入 else 被当 move
            # 重演副本, rc=0 产生虚假 passed=True 放行(预检形同虚设); 一律转用户裁决
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"沙箱预检器未支持该操作类型: {normalized}, 转用户裁决")
        # 参数别名归一(与真实工具分发一致: tools_alias_mapper.PARAM_ALIASES 将 src/file/target/source
        # 等映射到 path/dest)。不归一则读不到源路径, 会以 Path("") 退化为复制当前工作目录, 预检形同虚设(BUG-A)
        params = normalize_params(normalized, params)[0]
        if normalized in ("registrywrite", "registrydelete"):
            # 注册表无法影子副本(2.4 局限明示): 仅静态检查——键存在性/值类型/递归范围统计, 不做动态试删
            reg_path = params.get("path") or params.get("key", "")
            exists = _registry_key_exists(reg_path)            # winreg 标准库只读探测(实施时落地)
            return PreCheckResult(
                passed=True,
                blocked_reason=f"registry 静态分析(仅报告不试删): key={reg_path}, 存在={exists}",
                impacts=[])
        _backend = None
        src = Path(params.get("path") or params.get("source_path") or "")
        if not src.exists():
            # 源不存在: 无法做有效预演(复制不存在的源无任何意义), 转 HITL 裁决而非退化为复制 cwd 误放行(BUG-A/BUG-D)
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"源不存在，沙箱预检未完成有效验证: {src}")
        _backend = self._dispatch_backend()   # _backend=None 兜底: 若此处异常, finally 判 None 不误清
        workspace = SandboxWorkspace(max_workspace_mb=self.max_workspace_mb,
                                     max_shadow_mb=self.max_shadow_mb)
        workspace.create()
        try:
            replica = workspace.shadow_copy(src)
            if replica == src:
                # 超限跳过副本 → 未完成有效验证转裁决(3.1.1 降级规则, FP4 同通道)
                return PreCheckResult(passed=False, needs_ruling=True,
                                      blocked_reason=f"目标超过影子副本上限{self.max_shadow_mb}MB, 未完成有效验证: {src}")
            workspace.snapshot_files()   # v1.21 Z3: 以副本为 diff 基线, 防副本自身被误报为 added 影响面
            op_result = self._replay_file_op_on_replica(_backend, normalized, params, replica, workspace.path)
            impacts = workspace.diff_impacts()
            used = self._disk_usage(workspace.path)   # 以工作区真实磁盘占用来判定容量(防副本自身漏算/删除误算)
            if not workspace.check_capacity(used):
                # v1.22 W5: 工作区上限接线(同 shell 流程)
                return PreCheckResult(passed=False, needs_ruling=True,
                                      blocked_reason=f"沙箱工作区写入 {used} 字节超上限 {self.max_workspace_mb}MB, 转用户裁决",
                                      impacts=impacts, stderr_tail=op_result.stderr_tail)
            return self._classify(op_result, impacts)   # 复用同一套判定分流算法(DRY)
        except OSError as exc:
            # v1.22 W2: 影子副本/重演失败(源被占用/不可读等) → 未完成有效验证转裁决, 不穿透炸批(对齐 shell 流 Z9)
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"影子副本预演失败, 转用户裁决: {exc}")
        except Exception as exc:
            # v1.22 W2: 非 OSError 异常同样不穿透(对齐 shell 流 Z9)
            return PreCheckResult(passed=False, needs_ruling=True,
                                  blocked_reason=f"文件预检器内部异常, 未完成有效验证: {exc}")
        finally:
            if _backend is not None:
                try:
                    _backend.cleanup()   # 复用后端清理契约(8.7 句柄守恒断言; 对齐 shell 流 Z4, 防 file_op 路径孤儿进程/R5 资源残留)
                except Exception:
                    pass
            workspace.destroy()

    @staticmethod
    def _replay_file_op_on_replica(backend: JobObjectBackend, normalized: str,
                                    params: Dict, replica: Path, workspace: Path) -> BackendResult:
        """对工作区副本执行与原操作等价的动作 → BackendResult。
        v1.22 W3: 复用 backend.run(原为手写 Popen——无 Job 包裹、TimeoutExpired 未接会泄漏进程、
        且经 self 调用模块函数本会 AttributeError), Job 包裹/超时杀树/cleanup 契约全部复用(DRY)。
        delete→删除副本树; copy/move→在副本内重演目标变换。"""
        if normalized == "delete":
            replay_cmd = f"Remove-Item -LiteralPath {_ps_literal_path(replica)} -Recurse -Force"
        elif normalized == "copy":
            dest = replica.parent / Path(params.get("dest", params.get("path", "copied"))).name
            replay_cmd = f"Copy-Item -LiteralPath {_ps_literal_path(replica)} -Destination {_ps_literal_path(dest)} -Force"
        else:   # move: 副本内自移即验证可行性
            moved = replica.parent / "moved"
            replay_cmd = f"Move-Item -LiteralPath {_ps_literal_path(replica)} -Destination {_ps_literal_path(moved)} -Force"
        return backend.run(replay_cmd, workspace, 60)

    def _disk_usage(self, ws_path) -> int:
        """工作区真实磁盘占用(字节): 容量判定应以实际落盘文件为准, 既包含影子副本自身占用,
        又不会把"删除影响"误算为已用(删除是释放而非占用)——修正容量口径欠额放行/超额误拦(BUG-E)"""
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
    """模块级单例(__init__.py 导出; M3 action_handler 唯一调用入口)"""
    global _executor
    if _executor is None:
        _executor = SandboxExecutor()
    return _executor


# —— Phase 2 辅助(v1.21 Z3: 消除幽灵引用, 原调用无定义) ——

def _registry_key_exists(reg_path: str) -> bool:
    """registry 静态分析(2.4 局限明示): winreg 标准库只读探测键存在性, 不做任何写/删。
    v1.22 W6: 根键名归一去冒号——兼容 `HKLM:\\Software`(PowerShell 冒号形态)与 `HKLM\\Software`(reg.exe 形态)。"""
    import winreg
    root_map = {"HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE, "HKLM": winreg.HKEY_LOCAL_MACHINE,
                "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER, "HKCU": winreg.HKEY_CURRENT_USER}
    parts = reg_path.replace("/", "\\").split("\\", 1)
    root = root_map.get(parts[0].upper().rstrip(":"))
    if root is None or len(parts) < 2:
        return False
    try:
        with winreg.OpenKey(root, parts[1].lstrip("\\")):
            return True
    except OSError:
        return False
