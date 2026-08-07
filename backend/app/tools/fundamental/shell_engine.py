# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: 临时输出文件读取保护线改引用 tool_constants.SHELL_OUTPUT_FILE_MAX_BYTES(原 _MAX_OUTPUT_SZ=10MB), 功能零退化
# 2026-07-18 - 小沈 - 修复多行命令(如 python -c "..." 含换行)经 -Command - 从stdin喂入导致PowerShell解析器卡死等待输入(见 logs 2026-07-18 21:34-21:44 step=15 跑满600s超时): 改为写入.ps1文件 + 向持久pwsh喂一句【单行】dot-source投递, 多行内容留在文件内不再经stdin流, 死锁消除; 功能零退化
# 2026-07-20 - 小欧 - 门限治理(章6.4/3.5): SHELL_OUTPUT_FILE_MAX_BYTES 改名 SHELL_OUTLIMIT_RAW_BYTES(私有内部常量加 INER_ 前缀); 删除 shell_engine.py 本地重复定义, 统一引用 tool_constants 单源
# 2026-07-23 - 小欧 - 北京老陈驱动: safe_read_file 去掉 10MB head+tail 限制, 改为纯读; 删 SHELL_OUTLIMIT_RAW_BYTES import (仅保留 50K/20K tool 输出截断, 不需要磁盘读限制+字符截断两层)
# 2026-07-26 - 小沈 - 超时统一: 127行timeout=30→DEFAULT_TIMEOUT_SEC, 276行timeout=5→SUBPROCESS_TIMEOUT_SHORT, 286行timeout=5→SUBPROCESS_TIMEOUT_SHORT
# 2026-07-27 - 小欧 - 安全: exec()/_ensure_alive()/_start()加env参数, PS进程不再直接copy os.environ, 由调用方传_sanitize_env()过滤API key
# 2026-07-28 - 小欧 - 欧阳BUG-01+BUG-12修复: _class_lock Lock→RLock防死锁; _poll_for_file delay 5ms/×1.5/0.1→100ms/×2/1.0减少系统调用
# 2026-07-28 - 小欧 - 新增 _preprocess_command 命令预处理: PS5.1 将 && 降级为 ;(顺序执行), Windows 将 python3 降级为 python
# 2026-07-28 - 小欧 - 修复Bug-2+Bug-3: python3替换改用regex单词边界(避免误伤路径/版本号/包名); &&替换改用引号感知状态机(仅替换引号外的&&, 避免误伤字符串字面量)
# 2026-07-28 - 小欧 - 删除死代码 _replace_ampersand（&&/|| 翻译已由 execute_shell_command._translate_powershell_operators 完成）
#         _replace_python3_safe 新增引号感知替换, 避免python3误改字符串字面量
#         close()/_close() 加锁约束注释, 明确调用方锁约定
# 2026-07-28 - 小欧 - shell_type名称改为ps7/ps5/cmd/bash; __init__+get_instance+_start按shell_type(ps7/ps5)选pwsh.exe/powershell.exe
# 2026-07-28 - 小欧 - 删死字段 _is_pwsh7: _start中赋值后全局无读取(旧读者 _preprocess_command 的 && 分支已删)
# 2026-07-30 - 小沈 - 去单例+ShellPoolManager分池重构: 删get_instance/_instances/_class_lock/cleanup_all_persistent_shells/_IDLE_TIMEOUT; close()改self._lock.acquire(timeout=5); 尾部新增ShellPoolManager类+shell_pool单例+atexit; _close()docstring更新timeout场景
# 2026-07-30 - 小沈 - BugFix轮: acquire() 两段式(持锁检查→解锁启动→持锁入池)解决子进程启动阻塞全池; 复用空闲实例时加alive检查; release() close()移出锁; cleanup_by_task 增加临时实例清理(self._temp_instances); 删__init__中self._key死代码
# 2026-07-30 - 小沈 - 清理: 更新PersistentShell类docstring(删"实例池+空闲清理"); 删self._last_used死字段(只写不读)
# 2026-07-30 - 小沈 - 空闲超时兜底: ShellPoolManager 新增 idle_timeout=300s + _last_used 追踪; acquire()复用前检查超时则close不放回; release()/cleanup*同步清理_last_used
# 2026-07-30 - 小沈 - except:pass补日志: _kill_tree/_close/cleanup_by_task/cleanup_all四处catch改为logger.debug记录
# 2026-07-31 - 小欧 - Shell池进程保护: ShellPoolManager新增get_all_pids()返回所有活跃PID集合,供安全检查拦截Stop-Process/taskkill/kill保护自身进程; get_all_pids()加debug日志
# 2026-08-06 - 小欧 - 按设计文档12章实施H1-H10: ①新增探活常量+_probe()响应性探活; ②_start() stderr落日志+就绪握手; ③_close()显式关stderr句柄+残留读取+清理临时文件; ④ShellPoolManager新增_sem并发限流+_slot_held槽位记录; ⑤acquire()重构(Phase0限流/Phase1持锁找空闲/Phase2解锁探活/Phase3有界重试); ⑥release()/cleanup_by_task归还前查_slot_held防计数虚高; ⑦删除死代码shell/shell_engine.py
# 2026-08-06 - 小欧 - v2.7 BugFix: acquire()复用路径漏注册_inst_map(release()会pop, 复用后release拿key=None提前return → 信号量槽位泄漏, 并发下所有acquire等满ACQUIRE_WAIT_TIMEOUT); 由test_shell_pool_manager并发用例暴露(100.89s→41.21s); 复用路径补 self._inst_map[id(inst)] = key
# 2026-08-06 - 小欧 - 三堂会审终稿8项BugFix: ①cleanup_by_task池实例清理归还信号量槽位(防teardown后limiter枯零→全链卡慢, 复证free 2→1→0→0); ②self._lock Lock→RLock, _exec拆_exec/_exec_locked统一持锁(修_probe脱锁与exec并发写stdin串扰); ③Phase1空闲超时淘汰实例close移出池锁(修持池锁taskkill阻塞全池); ④acquire加env参数+execute_shell_command传_sanitize_env()(修启动copy os.environ泄漏API key); ⑤cleanup_by_task删temp循环内count+=1(修双计); ⑥新增_READY_PROBE_TIMEOUT=10s就绪握手(修冷启动>3s被误杀); ⑦_exec写stdin前poll探活(修向死进程写管道阻塞); ⑧F保留temp兜底(治#5防卡死设计, 非bug)
# 2026-08-06 - 小欧 - v2.8 单一信号量硬限流(用户北京老陈拍板最优解, 治F): ①删除temp兜底+超时继续——拿到槽位必然可复用或新建(池满⇒busy==max⇒拿不到槽), temp是死代码; 超时继续创建temp既绕过限流又卡10s, 是烂设计; ②ACQUIRE_WAIT_TIMEOUT 10→2s; ③拿不到槽位明确抛ShellPoolBusyError(调用方except捕获转build_error返回错误, 非卡死非500); ④删_slot_held/acquired布尔, 改用_inst_map存在性判定release/cleanup单次归还防超归(BoundedSemaphore超归会ValueError); ⑤删_temp_instances结构及相关分支; ⑥删除本次临时标记DETECT-TEST-TEMP
# 2026-08-06 - 小欧 - 修复cleanup_all遗漏: 归还sem槽位(防limiter枯零, 原cleanup_all只clear容器未sem.release, 运行中teardown调用后同key acquire全卡2s超时)
# 2026-08-06 - 小欧 - 卡死场景代码标注: 系统梳理多shell并行「后台卡死」14类场景(C1-C14), 在文件头加【场景索引】总表, 并在各处理代码点加[卡死场景C#]标注(供三堂会审/回归对照)。零逻辑改动, 全测试通过
# 2026-08-06 - 小欧 - 卡死场景日志补齐: 按C1-C14逐一核对各处理事件是否落地日志, 补齐缺漏(C2/C5/C8半死/C9/C10/C11/C13/C14), 统一[卡死C#]前缀标识分支序号, 级别用warning(卡死异常事件)/debug(正常淘汰/清理失败)。涉及shell_engine.py与execute_shell_command.py, 池测试19 passed
# 2026-08-06 - 小健 - 打猎测试定位并修复v2.9三个真实Bug: ①_probe()超时路径引用self._proc.pid崩溃(_exec超时内部已_close置_proc=None, pid引用→AttributeError), 改getattr(self._proc,'pid',None); ②cleanup_by_task/cleanup_all "in检查+release"与release()锁外pop存在超归竞态(cleanup锁内判断True后、sem.release前, release线程已pop拿到key并release → 双归还BoundedSemaphore超归抛ValueError), 改原子pop(仅pop成功才release), 与release()同一所有权转移规则; ③acquire C6淘汰日志it._proc.pid对无_proc对象(Mock) AttributeError, 改getattr嵌套防御。测试: test_shell_pool_manager 19→28用例(新增半死剔除/exec自愈/槽位守恒/并发不超归/高并发sem守恒), 全shell套件266 passed
# 2026-08-06 - 小健/小欧 - v2.10打猎第5~7个真实Bug: ⑤Bug#5(_start失败路径stderr临时文件泄漏,C12): Popen抛异常/进程立即退出两条失败路径残留ps_*.err(初测ps_0k3lbafn.err), 加_close()后_stderr_path置None但文件仍在磁盘(内联open()句柄泄漏→Windows句柄被占无法unlink) → 重构为self._stderr_handle持句柄, Popen异常时显式关闭并置None, Popen成功后置None交接子进程, _close()同步关闭句柄+unlink临时文件; ⑥Bug#6(C11,execute业务模块): taskkill失败后裸proc.kill()兜底, 进程已死时ProcessLookupError冒泡中断残存读取 → try/except包住+warning防丢失(execute_shell_command.py); ⑦Bug#7(acquire重试×并发cleanup超归): acquire Phase2阻塞期间并发cleanup原子pop+sem.release归还槽位, acquire Phase3重试注册新实例后调用方release再归一次 → BoundedSemaphore超归ValueError(shell_engine.py:633)。修复: acquire重试前用原子_inst_map.pop判定槽是否已归还(lost_slot), 已归还则sem.acquire重取一槽供新实例; owning_slot标记actual持槽, except仅实际持有才release, 杜绝空释/超归。hunt测试params_hunt_v3 2用例确定性复现→修后绿
# 2026-08-06 - 小欧 - v2.11 BugFix(C13死实例放回池): C8/C14命令超时_exec_locked内部_close()置_proc=None后, release()仍将死实例放回池 → 下次acquire复用死实例_probe见_proc=None返回False → 反复[卡死C13]噪音(第二次卡死案例22:14-22:16 tasklist真实超时链的共因)。修复: release()放回池前判定实例存活(_proc is None或poll()非None即死), 死实例从池中移除+close, 杜绝复用死实例。验证: 池测试全绿(28用例)
# 2026-08-07 - 小欧 - 卡死日志三问五处修复(与execute_shell_command.py联动, 三堂会审定稿):
#        R3: ps7池上限3→8 — 当日C2日志实测同key并发达5(ps7池默认3放不下), acquire排队超2s→ShellPoolBusyError;
#            8覆盖实测并发5并留余量(每实例约40MB内存, 8≈320MB可接受)
#        R4: 临时文件清理失败debug→warning升级可见性 — 清理失败=残留句柄/文件泄漏风险, 当日残留 tmpmsj4losd.cwd
#            即此场景, 需在info级日志留痕以便溯源
# 2026-08-07 - 小欧 - 三堂会审8.8复核: R0/R1/R2/R3/R4五处修改综合判定全部通过(池8并发全成功, 全量3576+418+120+48 passed)
# 2026-08-07 - 小欧 - G2普遍性根治(B6) C12管道层根治(与execute_shell_command.py R1移除联动, 三堂会审定稿):
#        ps_cmd ForEach内成功分支直接Out-File落盘渲染FormatEntryData触发out-lineoutput→进程stderr残留→误报C12,
#        R1枚举式命令名保护有别名盲区(fl/ft/fw漏网)。B6: 错误对象[void]$errs.Add($_)(不落盘)收集+成功对象原样
#        下传→管道末端统一| Out-String -Width 4096 | Out-File(Out-String正确渲染Format对象), 错误最后单独
#        Out-File -Encoding utf8(编码可控, 规避PS5 2>写UTF-16LE乱码)。分流语义等价旧结构, 别名/变体全覆盖。
"""
PersistentShell — 持久 PowerShell 进程引擎(ps7/ps5) — 小欧 2026-07-05

【编码链路】PS分支编码修复 (2026-07-07 小欧):
  ┌─ [入] stdin.write(cmd.encode(locale.getpreferredencoding()))
  │    PS5.1 `-Command -` stdin 用系统OEM编码(中文Windows=cp936/GBK)读取
  │    UTF-8写入时中文字节被GBK错误解码 → 必须用locale编码写入
  │    非locale可编码字符用errors='replace'回退
  │
  ├─ [子进程] env={PYTHONIOENCODING=utf-8, PYTHONUTF8=1}
  │    PYTHONIOENCODING: print()输出中文不抛UnicodeEncodeError
  │    PYTHONUTF8=1: open()默认用UTF-8,避免gbk误读UTF-8代码文件
  │
  ├─ [出] > 替换为 Out-File -Encoding utf8
  │    PS5.1默认>写UTF-16LE导致中文乱码 → 统一UTF-8
  │
  └─ [读] safe_read_file + .lstrip('\ufeff')
       PS5.1 Out-File写BOM头 → 去掉ZWNBSP
       (out/err/code/cwd 全部处理)

  全景图见 execute_shell_command.py 头部注释

【架构层级】引擎层 (raw dict only，不碰 build3/llm_data)
   铁规1: 本文件只返回 raw dict，严禁调用 build_success/build_error/build_warning
   铁规2: 计时(duration_ms) 不在本文件，在 shell() 主函数

【设计原则】
  SRP: 只做进程管理 + 命令执行，tempfile/安全读取提取为独立函数
  DRY: _ERROR_NO_SHELL/_ERROR_TIMEOUT 错误常量统一
  KISS: exec() -> _ensure_alive() -> _exec() 直线调用
  YAGNI: 无 daemon 线程空闲检查，exec 时懒检测
"""

import atexit
import contextlib
import locale
import os
import re as re_mod
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.logger import logger
from app.tools.tool_constants import DEFAULT_TIMEOUT_SEC, SHELL_POOL_IDLE_TIMEOUT, SUBPROCESS_TIMEOUT_SHORT


# ═══════════════════════════════════════════════════════════════════════
#  多Shell并行「后台卡死」场景索引 — C#场景 → 对应处理代码位置
#  三堂会审: 小欧 2026-08-06 (穷尽14类, 逐一核对结论: 全部处理完整/准确/正确)
#   C1  槽位泄漏→acquire全部卡满超时(旧free 2→1→0→0)
#       → 单一信号量硬限流; 守恒: release()归还/cleanup_by_task()归还/acquire异常路径归还/复用重注册_inst_map
#   C2  拿不到槽→无限等待
#       → acquire Phase0: sem.acquire(timeout=ACQUIRE_WAIT_TIMEOUT) 有界2s, 超时抛ShellPoolBusyError(调用方转build_error)
#   C3  并发写同一stdin→命令串扰/挂起
#       → PersistentShell._lock=RLock + _exec统一持锁(_exec/_probe/_start握手全重入同一锁)
#   C4  多行命令经stdin→PS解析器卡死等待输入
#       → _exec_locked: ps_cmd写.ps1文件 + 只喂一句【单行】dot-source
#   C5  向已死进程写stdin→管道阻塞
#       → _exec_locked: 写前poll探活 + BrokenPipe/OSError捕获→_EXIT_PROCESS_DIED
#   C6  锁内阻塞操作→拖死全池
#       → acquire evict_to_close / release close / cleanup close 全部移出池锁
#   C7  池锁↔实例锁交叉死锁
#       → 锁序固定「先池锁释放→再拿实例锁」, 从不嵌套持有(无环可成)
#   C8  半死进程(假活)复用→exec挂起
#       → _probe()响应性探活 + _start()就绪握手(_READY_PROBE_TIMEOUT=10s) + _poll_for_file超时兜底kill
#   C9  清理打断in-flight exec
#       → close() acquire(timeout=5)未获锁也force-kill进程; exec侧_poll_for_file有界返回
#   C10 子进程持管道→communicate挂满(仅cmd/bash分支)
#       → execute_shell_command.py: cmd poll-loop代替communicate; bash捕获TimeoutExpired→_kill_and_read_output
#   C11 kill/wait自身阻塞
#       → _kill_tree/_close/proc.wait/taskkill 全部带SUBPROCESS_TIMEOUT_SHORT有界
#   C12 临时文件/句柄泄漏→耗尽资源
#       → _TempFiles上下文finally unlink + _close显式关闭stderr句柄
#   C13 acquire Phase2与cleanup并发竞态
#       → 槽位守恒(cleanup只归还在_inst_map的实例)+_inst_map防超归; 后果仅偶发进程重启(非卡死), lock+timeout双兜底
#   C14 exec长命令(≤timeout)锁被hold
#       → close()可force-kill; exec全程有界timeout后返回(慢非卡死)
# ═══════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════
#  常量
# ═══════════════════════════════════════════════════════

_ERROR_NO_SHELL = {"stdout": "", "stderr": "PowerShell不可用", "exit_code": -1}
_ERROR_TIMEOUT  = {"stdout": "", "stderr": "timeout", "exit_code": -1, "timed_out": True}
_EXIT_PROCESS_DIED = -2          # 进程死亡 sentinel，外部重试用
_PROBE_TIMEOUT = 3               # 响应性探活超时(秒)：半死进程3秒内无回执即判死 — 小欧 2026-08-06
_READY_PROBE_TIMEOUT = 10        # 就绪握手超时(秒)：首次启动慢(profile/杀软/慢盘)放宽到10s, 防误杀刚拉起进程 — 小欧 2026-08-06
_PROBE_CMD = "Write-Output __OMNI_PROBE__"   # 探活命令：轻量、无副作用、输出唯一标记 — 小欧 2026-08-06
ACQUIRE_WAIT_TIMEOUT = 2        # acquire 并发限流等待超时(秒)：有界排队, 超时明确抛ShellPoolBusyError(不temp不卡死) — v2.8 小欧 2026-08-06

# ═══════════════════════════════════════════════════════
#  _TempFiles — 临时文件 contextmanager
# ═══════════════════════════════════════════════════════

@contextlib.contextmanager
def _TempFiles():
    """安全创建 5 个临时文件并自动清理 — out/err/code/cwd/ps1  — [卡死场景C12] 小欧 2026-08-06"""
    paths = {}
    try:
        # ps1: 2026-07-18 小沈 新增, 存多行命令脚本(避免直接经stdin喂入导致PS卡死)
        for name in ("out", "err", "code", "cwd", "ps1"):
            f = tempfile.NamedTemporaryFile(delete=False, suffix=f".{name}",
                                             mode="w", encoding="utf-8")
            f.close()
            paths[name] = f.name
        yield type("Paths", (), paths)()
    finally:
        for p in paths.values():
            try:
                os.unlink(p)
            except OSError:
                # 2026-08-07 小欧 三堂会审定稿: debug→warning 升级可见性, 清理失败=残留句柄/文件泄漏风险,
                # 当日残留 tmpmsj4losd.cwd 即此场景, 需在info级日志留痕以便溯源
                logger.warning(f"[卡死C12] 临时文件清理失败(残留句柄?) (path={p})")


def safe_read_file(path: str) -> str:
    """读取文件内容(utf-8), OSError返回空串 — 小欧 2026-07-23"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# ═══════════════════════════════════════════════════════
#  _poll_for_file — 指数退避轮询
# ═══════════════════════════════════════════════════════

def _poll_for_file(path: str, timeout: int) -> bool:
    """轮询直到文件非空或超时 — 指数退避 100ms→1s"""
    deadline = time.time() + timeout
    delay = 0.1
    while time.time() < deadline:
        try:
            if os.path.getsize(path) > 0:
                return True
        except OSError:
            pass
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(delay, remaining))
        delay = min(delay * 2, 1.0)
    return False


# ═══════════════════════════════════════════════════════
#  _replace_python3_safe — 引号感知 python3→python 替换
# ═══════════════════════════════════════════════════════

def _replace_python3_safe(command: str) -> tuple[str, int]:
    """引号感知的 python3→python 替换(仅替换引号外的python3) — 小欧 2026-07-28

     返回 (替换后命令, 替换次数) 方便调用方日志记录。"""
    result = []
    in_single = False
    in_double = False
    count = 0
    i = 0
    n = len(command)
    while i < n:
        c = command[i]
        if c == "'" and not in_double:
            in_single = not in_single
            result.append(c)
            i += 1
        elif c == '"' and not in_single:
            in_double = not in_double
            result.append(c)
            i += 1
        elif not in_single and not in_double:
            # 引号外: 匹配 python3 (word boundary 语义)
            if (i == 0 or command[i - 1] in ' \t;|&') and \
               i + 7 <= n and command[i:i + 7] == 'python3' and \
               (i + 7 >= n or command[i + 7] in ' \t;|&'):
                result.append('python')
                i += 7
                count += 1
                continue
            result.append(c)
            i += 1
        else:
            result.append(c)
            i += 1
    return ''.join(result), count


# ═══════════════════════════════════════════════════════
#  PersistentShell — 核心类
# ═══════════════════════════════════════════════════════

class PersistentShell:
    """持久 PowerShell 进程(ps7/ps5) — 自动重启(exec内2次retry+_ensure_alive)

    用法:
        engine = shell_pool.acquire("task_id", "ps7", workdir="C:/work")
        result = engine.exec("Get-ChildItem", timeout=DEFAULT_TIMEOUT_SEC)
        shell_pool.release(engine)
        # result = {"stdout": ..., "stderr": ..., "exit_code": 0}
    """

    def __init__(self, workdir: str, shell_type: str = "ps7"):
        if shell_type not in ("ps7", "ps5"):
            raise ValueError(f"PersistentShell 仅支持 ps7/ps5, 收到: {shell_type}")
        self._proc: Optional[subprocess.Popen] = None
        self._alive = False
        self._lock = threading.RLock()   # [卡死场景C3] v2.7 BugFix(小欧 2026-08-06): Lock→RLock, 使 _exec(含probe/start就绪握手)可重入统一持锁, 修 _probe 脱锁与 exec 并发写 stdin → 杜绝多shell并行时命令串扰/挂起
        self._cwd = workdir or os.getcwd()
        self._shell_type = shell_type
        self._stderr_path: Optional[str] = None   # stderr 日志文件路径(半死可观测) — 小欧 2026-08-06
        self._stderr_handle = None                # v2.10 BugFix(小健 2026-08-06): 持stderr句柄引用, Popen异常时显式关闭防句柄泄漏(详见_start)

    # ── 公共方法 ────────────────────────────────

    def exec(self, command: str, timeout: int = 60, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        with self._lock:
            for attempt in range(2):
                if not self._ensure_alive(env):
                    if attempt == 0:
                        self._close()
                        continue
                    return dict(_ERROR_NO_SHELL)
                result = self._exec(command, timeout)
                if result.get("exit_code") != _EXIT_PROCESS_DIED:
                    return result
                self._close()
            return dict(_ERROR_NO_SHELL)

    def close(self):
        """关闭实例并终止进程。先尝试获取 self._lock（最多等5秒），超时也 force-kill。— [卡死场景C9/C14] 小欧 2026-08-06"""
        locked = self._lock.acquire(timeout=5)
        if not locked:
            logger.warning(f"[卡死C9/C14] 清理时锁被hold超过5s(exec长命令占用) → force-kill 进程 (pid={self._proc.pid if self._proc else None})")
        try:
            self._close()
        finally:
            if locked:
                self._lock.release()

    @property
    def current_dir(self) -> str:
        return self._cwd

    # ── 进程生命周期 ────────────────────────────

    def _ensure_alive(self, env: Optional[Dict[str, str]] = None) -> bool:
        if self._alive and self._proc and self._proc.poll() is None:
            return True
        return self._start(env)

    def _probe(self, env: Optional[Dict[str, str]] = None, timeout: Optional[int] = None) -> bool:
        """响应性探活(纯探测, 不重建)：进程死或半死返回 False, 由调用方决定重建。— [卡死场景C8] 小欧 2026-08-06
        复用 _exec 机制(DRY)：半死时 _exec 内部 _poll_for_file 超时 → 自动 _kill_tree+_close。
        timeout 可选: 就绪握手传 _READY_PROBE_TIMEOUT(首次启动慢), 探活默认 _PROBE_TIMEOUT。 — 小欧 2026-08-06
        返回 True=健康可复用; False=进程不可用(可能已被 _exec 销毁)。 — 小欧 2026-08-06"""
        if self._proc is None or self._proc.poll() is not None:
            return False                      # 进程已死/未启动 → 不可复用
        result = self._exec(_PROBE_CMD, timeout=timeout or _PROBE_TIMEOUT)   # 复用现有执行机制
        if result.get("timed_out"):
            logger.warning(f"[卡死C8] 探活失败(半死)→已销毁 (pid={getattr(self._proc, 'pid', None)})")
            self._close()                     # 半死销毁(重建由调用方负责)
            return False
        return "__OMNI_PROBE__" in result.get("stdout", "")

    def _start(self, env: Optional[Dict[str, str]] = None) -> bool:
        self._close()
        if self._shell_type == "ps7":
            pwsh = shutil.which("pwsh.exe")
        else:  # "ps5"
            pwsh = shutil.which("powershell.exe")
        if not pwsh:
            logger.error(f"[PersistentShell] {self._shell_type}(pwsh.exe/powershell.exe) 未找到")
            return False
        try:
            # 设PYTHONIOENCODING保证子Python进程输出中文时不抛UnicodeEncodeError — 小欧 2026-07-07
            # PYTHONUTF8=1让open()默认用UTF-8而非gbk,避免读UTF-8代码文件乱码 — 小欧 2026-07-07
            base_env = env if env is not None else os.environ
            child_env = {**base_env, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            # ① stderr: DEVNULL → 日志文件(可观测半死原因) — 治#2 小欧 2026-08-06
            fd, self._stderr_path = tempfile.mkstemp(suffix=".err", prefix="ps_", text=True)
            os.close(fd)
            # [卡死C12] v2.10 BugFix(小健 2026-08-06): stderr句柄不再内联给Popen(否则Popen异常时句柄泄漏,
            # Windows下已占用文件不可unlink → 临时文件泄漏累积); 存局部句柄供 _start 失败路径显式关闭
            stderr_handle = open(self._stderr_path, "w", encoding="utf-8", errors="replace")
            self._stderr_handle = stderr_handle
            try:
                self._proc = subprocess.Popen(
                    [pwsh, "-NoProfile", "-Command", "-"],
                    stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                    stderr=stderr_handle,
                    cwd=self._cwd, env=child_env,
                )
            except Exception:
                # Popen异常: 句柄尚在父进程未移交 → 显式关闭再抛出, 供外层except清理临时文件
                try:
                    stderr_handle.close()
                except Exception:
                    pass
                self._stderr_handle = None
                raise
            self._stderr_handle = None   # 移交子进程后由 _close/进程代管
            for _ in range(40):
                if self._proc.poll() is None:
                    break
                time.sleep(0.025)
            else:
                # [卡死C12] v2.10 BugFix(小健 2026-08-06): 进程启动后立即退出 → _close() 清理已mkstemp的_stderr_path临时文件, 防泄漏
                logger.error("[PersistentShell] 进程启动后立即退出, 已清理临时stderr文件")
                self._alive = False
                self._close()
                return False
            self._alive = True
            # ② 就绪握手：启动后立即纯探测一次，未就绪则销毁(调用方重建) — 治#3 小欧 2026-08-06
            # v2.7 BugFix(小欧 2026-08-06): 握手用 _READY_PROBE_TIMEOUT(10s), 避免冷启动>3s被误杀
            # [卡死场景C8] 半死进程假活防护: 冷启动慢/杀软/慢盘不误杀, 真半死则销毁重建 — 小欧 2026-08-06
            if not self._probe(env, timeout=_READY_PROBE_TIMEOUT):
                logger.error("[PersistentShell] 就绪握手失败，进程未就绪")
                self._close()
                return False
            logger.info(f"[PersistentShell] 进程就绪 (pid={self._proc.pid}, stderr={self._stderr_path}, cwd={self._cwd}, shell_type={self._shell_type})")
            return True
        except Exception as e:
            logger.error(f"[PersistentShell] 启动失败: {e}")
            self._alive = False
            # [卡死C12] v2.10 BugFix(小健 2026-08-06): Popen异常时 _stderr_path 已在mkstemp创建但未清理 → _close() 清理临时文件, 防temp目录累积泄漏
            self._close()
            return False

    # ── 命令预处理 ──────────────────────────────

    def _preprocess_command(self, command: str) -> str:
        """预处理命令, 修复常见跨平台/跨PS版本不兼容 — 小欧 2026-07-28
        注: PS5 的 &&/|| 翻译已在 execute_shell_command._translate_powershell_operators 完成, 此处不再重复 — 小欧 2026-07-28"""
        if sys.platform == "win32":
            new_cmd, count = _replace_python3_safe(command)
            if count:
                logger.debug(f"[PersistentShell] python3 → python (x{count})")
            command = new_cmd
        return command

    # ── 命令执行 ────────────────────────────────

    def _exec(self, command: str, timeout: int) -> Dict[str, Any]:
        # [卡死场景C3] v2.7 BugFix(小欧 2026-08-06): _exec 统一持锁(RLock可重入)。
        # 原 exec() 持锁调 _exec、而 acquire 复用路径 _probe() 脱锁调 _exec →
        # 两处可并发写同一 stdin → 命令交错/串扰。收敛为所有 _exec 调用统一持锁。
        with self._lock:
            return self._exec_locked(command, timeout)

    def _exec_locked(self, command: str, timeout: int) -> Dict[str, Any]:
        command = self._preprocess_command(command)
        with _TempFiles() as paths:
            # 用Out-File -Encoding utf8取代>避免PS5.1写UTF-16LE导致中文乱码 — 小欧 2026-07-07
            # 设置$OutputEncoding为UTF8避免PS5.1用GBK解读子进程UTF-8输出导致乱码 — 小欧 2026-07-07
            # $OutputEncoding+Out-File -Width 4096解决PS5.1 Format-Table因控制台宽度不足(默认80列)输出空白 — 小欧 2026-07-08
            # [卡死C12] 2026-08-07 小欧 G2普遍性根治(B6): ForEach内成功分支直接Out-File落盘,
            # Out-File渲染FormatEntryData触发out-lineoutput→进程stderr残留→误报C12(别名fl/ft/fw亦触发)。
            # B6: 错误对象[void]$errs.Add($_)(不落盘), 成功对象原样下传→管道末端统一
            # | Out-String -Width 4096 | Out-File(Out-String正确渲染Format对象), 错误最后单独
            # Out-File -Encoding utf8(编码可控, 规避PS5 2>写UTF-16LE乱码)。分流语义等价旧结构。
            ps_cmd = (
                f'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $OutputEncoding=[System.Text.Encoding]::UTF8; $global:rc=0; '
                f'$errs = New-Object System.Collections.ArrayList; '
                f'& {{ {command}; if (-not $?) {{ $global:rc = if ($LASTEXITCODE) {{ $LASTEXITCODE }} else {{ 1 }} }} }} 2>&1 | '
                f'ForEach-Object {{ if ($_ -is [System.Management.Automation.ErrorRecord]) {{ [void]$errs.Add($_) }} else {{ $_ }} }} | '
                f'Out-String -Width 4096 | Out-File -FilePath "{paths.out}" -Encoding utf8 -Width 4096; '
                f'if ($errs.Count) {{ $errs | Out-String -Width 4096 | Out-File -FilePath "{paths.err}" -Encoding utf8 -Width 4096 }}; '
                f'$global:rc | Out-File -FilePath "{paths.code}" -Encoding utf8; '
                f'(Get-Location).Path | Out-File -FilePath "{paths.cwd}" -Encoding utf8'
            )
            try:
                # [卡死场景C4] 修复(小沈 2026-07-18): 多行命令(如 python -c "..." 含换行)直接经 -Command - 从stdin喂入时,
                # PowerShell解析器会卡死等待输入, 导致命令跑满timeout(见 logs 2026-07-18 step=15 跑满600s)。
                # 改为: 将ps_cmd(含多行内容)以UTF-8-BOM写入.ps1文件, 再向持久pwsh喂一句【单行】dot-source
                # (& { . "path.ps1" }), 多行内容留在文件内不再经stdin流 → 死锁消除。单行命令亦正常。
                with open(paths.ps1, "w", encoding="utf-8-sig") as _ps1:
                    _ps1.write(ps_cmd)
                feed = f'& {{ . "{paths.ps1}" }}\n'
                # [卡死场景C5] v2.7 BugFix(小欧 2026-08-06): 写 stdin 前 poll 探活, 防向已死进程写管道被阻塞。
                # 进程已死时 pipe 写端会阻塞/报错, 提前返回 _EXIT_PROCESS_DIED 让 exec() 走重启分支。
                if self._proc is None or self._proc.poll() is not None:
                    logger.warning(f"[卡死C5] 写stdin前探活: 进程已死, 返回_EXIT_PROCESS_DIED → 走重启分支 (pid={self._proc.pid if self._proc else None})")
                    return {"stdout": "", "stderr": "", "exit_code": _EXIT_PROCESS_DIED}
                self._proc.stdin.write(feed.encode(locale.getpreferredencoding(), errors="replace"))
                self._proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                logger.warning(f"[卡死C5] 向死进程写stdin触发管道异常(BrokenPipe/OSError/ValueError) → 返回_EXIT_PROCESS_DIED, 走重启分支")
                return {"stdout": "", "stderr": "", "exit_code": _EXIT_PROCESS_DIED}

            # [卡死场景C8/C14] 有界兜底: 命令超时(含半死/死循环/锁被hold) → 杀进程树+close, 返回timeout(非永久阻塞) — 小欧 2026-08-06
            if not _poll_for_file(paths.code, timeout):
                logger.warning(f"[卡死C8/C14] 命令超时{timeout}s未出结果(半死/死循环/锁被hold) → 杀进程树+close, 返回timeout(非永久阻塞)")
                self._kill_tree()
                self._close()
                return dict(_ERROR_TIMEOUT)

            # .lstrip('\ufeff') 去掉PS5.1 Out-File -Encoding utf8写的BOM — 小欧 2026-07-07
            stdout = safe_read_file(paths.out).lstrip('\ufeff')
            stderr = safe_read_file(paths.err).lstrip('\ufeff')
            code_raw = safe_read_file(paths.code).strip().lstrip('\ufeff')
            cwd_raw = safe_read_file(paths.cwd).strip().lstrip('\ufeff')
            if cwd_raw:
                self._cwd = cwd_raw
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": int(code_raw) if code_raw else 0,
            }

    # ── 清理 ────────────────────────────────────

    def _kill_tree(self):
        # [卡死场景C11] taskkill 自带 timeout 有界, 防自身阻塞 — 小欧 2026-08-06
        if self._proc and self._proc.poll() is None:
            try:
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(self._proc.pid)],
                    capture_output=True, timeout=SUBPROCESS_TIMEOUT_SHORT,
                )
            except Exception as e:
                logger.warning(f"[卡死C11] taskkill异常 → proc.kill()兜底 (pid={self._proc.pid}): {e}")
                try:
                    self._proc.kill()
                except Exception:
                    pass

    def _close(self):
        """内部关闭, 不持锁。调用方尽量持有 self._lock（close()超时5s未获取到锁也会force-kill）。— [卡死场景C9/C11/C12] 小欧 2026-08-06"""
        if self._proc:
            try:
                if self._proc.poll() is None:
                    self._proc.kill()
                    self._proc.wait(timeout=SUBPROCESS_TIMEOUT_SHORT)   # [卡死场景C11] wait有界, 防kill后阻塞 — 小欧 2026-08-06
            except Exception as e:
                logger.warning(f"[卡死C11] 关闭进程失败(pid={self._proc.pid}): {e}")
            # [卡死场景C12] v2.7 修复(问题3): 显式关闭 stderr 句柄(在置 None 前), 防半死场景 wait 超时后句柄残留→unlink 失败 — 小欧 2026-08-06
            try:
                if self._proc.stderr is not None:
                    self._proc.stderr.close()
            except Exception:
                pass
            self._proc = None
            self._alive = False
        # [卡死场景C12] v2.10 BugFix(小健 2026-08-06): Popen异常未移交句柄时 _stderr_handle 残留 → 显式关闭, 防Windows下临时文件被占用无法unlink
        if self._stderr_handle is not None:
            try:
                self._stderr_handle.close()
            except Exception:
                pass
            self._stderr_handle = None
        # [卡死场景C12] 半死可观测：close 前读取 stderr 残留并记录，随后清理临时文件 — 小欧 2026-08-06
        if self._stderr_path:
            tail = safe_read_file(self._stderr_path).strip()
            if tail:
                logger.warning(f"[卡死C12] 关闭时 stderr 残留(半死证据): {tail[:200]}")
            try:
                os.unlink(self._stderr_path)
            except OSError:
                pass
            self._stderr_path = None


# ═══════════════════════════════════════════════════════
#  ShellPoolManager — 按 (task_id, shell_type) 分池
# ═══════════════════════════════════════════════════════

class ShellPoolBusyError(RuntimeError):
    """同 key 并发槽位耗尽：acquire 等待 ACQUIRE_WAIT_TIMEOUT 后明确失败。
    单一信号量硬限流(v2.8)：绝不临时创建绕过限流，绝不无限等待。调用方捕获转 build_error 返回。— 小欧 2026-08-06"""


class ShellPoolManager:
    """Shell实例池管理器 — 按 (task_id, shell_type) 分池，任务隔离 + 同类型并行"""

    def __init__(self, max_per_type: int = 3, idle_timeout: Optional[int] = SHELL_POOL_IDLE_TIMEOUT):
        self._pool: Dict[tuple, List[PersistentShell]] = defaultdict(list)
        self._busy: Dict[tuple, set] = defaultdict(set)
        self._inst_map: Dict[int, tuple] = {}
        self._lock = threading.Lock()
        self._max_per_type = max_per_type
        self._sem: Dict[tuple, threading.BoundedSemaphore] = defaultdict(lambda: threading.BoundedSemaphore(self._max_per_type))
        # 空闲超时兜底: 实例放回池后超过 idle_timeout 秒无人 acquire 则 close（防孤魂野鬼）
        self._idle_timeout = idle_timeout
        self._last_used: Dict[int, float] = {}  # id(inst) → release 时间戳

    def _pool_key(self, task_id: str, shell_type: str) -> tuple:
        return (task_id, shell_type)

    def _make_shell(self, shell_type: str, workdir: str = None) -> PersistentShell:
        """创建 PersistentShell 实例（解锁执行，不持池锁）"""
        return PersistentShell(workdir, shell_type)

    def acquire(self, task_id: str, shell_type: str, workdir: str = None,
                env: Optional[Dict[str, str]] = None) -> PersistentShell:
        """获取一个空闲 PersistentShell 实例（按 task_id + shell_type 分池）
        env: 子进程环境变量(调用方传 _sanitize_env() 过滤 API key)。— v2.7 BugFix(小欧 2026-08-06)
        单一信号量硬限流(v2.8, 治#5/#F):  [卡死场景C1/C2/C7]
          Phase0: sem.acquire(有界等待) — 同key并发≤max_per_type; 超时明确抛ShellPoolBusyError
                  (拿到槽位⇒活跃acquire<max⇒池满则必有空闲复用/未满则新建, temp分支不可达, 已删)
          Phase1(持锁): 仅找空闲实例+空闲超时兜底, 零耗时(治#6)
          Phase2(解锁): 复用→_probe()探活; 新建→_start()启动
          Phase3: 探活/启动失败→剔除销毁→有界重试
        槽位生命周期: acquire 拿1槽; release/cleanup 各归还1次(_inst_map存在性判定防超归)
        锁序防死锁(C7): 先取池锁(Phase1) → 释放后再拿实例锁(Phase2), 从不嵌套持有两把锁
        """  # 小欧 2026-08-06 v2.8
        key = self._pool_key(task_id, shell_type)
        sem = self._sem[key]
        # [卡死场景C2] Phase0: 拿不到槽位 → 明确失败, 绝不temp绕过限流、绝不无限等待 — 小欧 2026-08-06
        # 有界等待: 同key并发排队最多 ACQUIRE_WAIT_TIMEOUT(2s), 超时抛ShellPoolBusyError → 调用方except转build_error(非卡死非500)
        if not sem.acquire(timeout=ACQUIRE_WAIT_TIMEOUT):
            logger.warning(f"[卡死C2] 池槽位耗尽, 同key并发排队超{ACQUIRE_WAIT_TIMEOUT}s → 明确失败(key={key}, 上限={self._max_per_type}), 拒temp绕过/无限等")
            raise ShellPoolBusyError(
                f"[ShellPool] 同key并发槽位耗尽(key={key}, 上限={self._max_per_type}): "
                f"等待{ACQUIRE_WAIT_TIMEOUT}s未获槽位, 请降低并发或稍后重试"
            )
        max_attempts = self._max_per_type + 2   # 有界重试: 防 pwsh 不可用时无限循环 — 小欧 2026-08-06
        # v2.10 BugFix(小健 2026-08-06): owning_slot 追踪本 acquire 当前是否持槽。
        # 竞态根因: 本 acquire 已 acquire 1槽后, Phase2阻塞期间并发 cleanup 也可 pop 同一实例注册并
        # sem.release()(槽被外部归还)。此后 acquire 若重试并注册新实例, 调用方 release(X) 会再归一次
        # → BoundedSemaphore 超归 ValueError。修复: 重试前检测槽是否已被外部归还, 是则重新 acquire;
        # except 仅释放实际持有的槽(owning_slot), 避免空释。 — 小健 2026-08-06
        owning_slot = True
        try:
            for _ in range(max_attempts):
                evict_to_close = []   # v2.7 BugFix(小欧 2026-08-06): 空闲超时淘汰的实例收集到锁外 close, 防持池锁阻塞全池
                # ── Phase1(持锁): 仅找空闲实例+空闲超时兜底, 零耗时(治#6) ──
                with self._lock:
                    pool = self._pool[key]
                    busy = self._busy[key]
                    inst = None
                    for it in list(pool):
                        if id(it) not in busy:
                            if self._idle_timeout is not None:
                                last = self._last_used.get(id(it), 0)
                                if time.time() - last > self._idle_timeout:
                                    pool.remove(it)
                                    self._inst_map.pop(id(it), None)
                                    self._last_used.pop(id(it), None)
                                    evict_to_close.append(it)
                                    logger.debug(f"[卡死C6] 空闲超时淘汰实例(锁外close不阻塞全池) (pid={getattr(getattr(it, '_proc', None), 'pid', None)}, idle={self._idle_timeout}s)")
                                    continue
                            busy.add(id(it))
                            self._inst_map[id(it)] = key
                            inst = it
                            fresh = False
                            break
                    if inst is None:
                        inst = self._make_shell(shell_type, workdir)
                        if len(pool) < self._max_per_type:
                            pool.append(inst)
                            busy.add(id(inst))
                            self._inst_map[id(inst)] = key
                            self._last_used[id(inst)] = time.time()
                            fresh = True
                        else:
                            # v2.8: 拿到槽位⇒活跃acquire<max⇒池满必有空闲复用, 此分支不可达(防御)
                            raise RuntimeError(f"[ShellPool] 内部不一致: 池满且无空闲(key={key}), 应不可达")
                # [卡死场景C6] 锁外 close 空闲超时淘汰实例, 不阻塞全池 — v2.7 BugFix(小欧 2026-08-06)
                for inst in evict_to_close:
                    inst.close()
                # ── Phase2(解锁): 新建→_start; 复用→_probe ──
                ok = inst._start(env) if fresh else inst._probe(env)   # v2.7 BugFix: env 透传, 防 API key 泄漏 — 小欧 2026-08-06
                if ok:
                    return inst
                # [卡死场景C13] Phase3: 失败→销毁剔除→有界重试
                # v2.10 BugFix(小健 2026-08-06): 剔除实例时用原子 pop 判断槽是否已被外部(cleanup)归还。
                #   - pop 返回 key(本acquire仍持有) → 槽归本 acquire, 重试继承持有, 不额外偿碰 sem
                #   - pop 返回 None(cleanup已 pop+release) → 槽被外部归还, 重试前须重新 acquire, 否则
                #     新实例 release 会再放一次 → 超归 ValueError
                logger.warning(f"[卡死C13] Phase探活/启动失败 → 销毁剔除实例并重试 (shell={shell_type}, task_id={task_id}, pid={getattr(getattr(inst, '_proc', None), 'pid', None)})")
                with self._lock:
                    pool = self._pool[key]
                    busy = self._busy[key]
                    if inst in pool:
                        pool.remove(inst)
                    busy.discard(id(inst))
                    lost_slot = self._inst_map.pop(id(inst), None) is None
                    self._last_used.pop(id(inst), None)
                inst.close()
                if lost_slot:
                    # 槽已由外部(cleanup)归还 → 重新取得一槽, 供重试的新实例占用(不额外超归/泄漏)
                    owning_slot = False
                    if not sem.acquire(timeout=ACQUIRE_WAIT_TIMEOUT):
                        logger.warning(f"[卡死C2] 重试前重新取槽超时(同 key 并acquire返回新并发) (key={key}, 上限={self._max_per_type}) → 明确失败")
                        raise RuntimeError(f"[ShellPool] 重试重新取槽超时(key={key}, 上限={self._max_per_type})")
                    owning_slot = True
            raise RuntimeError(
                f"[ShellPool] 连续 {max_attempts} 次获取 Shell 失败 (shell={shell_type}, task_id={task_id})"
            )
        except Exception:
            # [卡死场景C1] 异常路径归还实际持有的槽位, 防泄漏 → 限流器不枯零 — 小欧 2026-08-06
            if owning_slot:
                sem.release()
            raise

    def release(self, inst: PersistentShell):
        """释放实例回池 — 归还信号量槽位(v2.8: 单一信号量, 无temp无slot_held)"""
        key = self._inst_map.pop(id(inst), None)
        if key is None:
            return   # 已释放/未跟踪, 防 double-release 超归(BoundedSemaphore超归会ValueError)
        sem = self._sem.get(key)
        should_close = False
        with self._lock:
            busy_set = self._busy.get(key)
            if busy_set is None:
                should_close = True
            else:
                busy_set.discard(id(inst))
                pool = self._pool.get(key, [])
                if inst not in pool:
                    should_close = True
                else:
                    # [卡死C13] v2.11 BugFix(小欧 2026-08-06): 死实例(C8/C14超时_close置_proc=None / 进程自然退出)
                    # 一律不放回池, 直接close。否则下次acquire复用死实例 → _probe见_proc=None返回False → 反复C13噪音。
                    if inst._proc is None or inst._proc.poll() is not None:
                        pool.remove(inst)
                        self._last_used.pop(id(inst), None)
                        should_close = True
                    else:
                        # 池实例放回: 记录时间戳供空闲超时兜底
                        self._last_used[id(inst)] = time.time()
        # [卡死场景C6] Bug#3 修复: close() 在锁外执行，不阻塞全池操作 — 小欧 2026-08-06
        if should_close:
            inst.close()
        if sem is not None:
            # [卡死场景C1] 归还槽位(本 acquire 占用的 1 槽), _inst_map 已pop保证单次(不超归) — v2.8 小欧 2026-08-06
            sem.release()

    def cleanup_by_task(self, task_id: str):
        """关闭某个任务的所有实例 — 任务结束时调用; 归还信号量槽位(防limiter枯零)"""
        count = 0
        close_list = []
        with self._lock:
            # ── 池中实例 ──
            keys_to_remove = [k for k in self._pool if k[0] == task_id]
            for key in keys_to_remove:
                sem = self._sem.get(key)
                for inst in self._pool[key]:
                    # [卡死场景C1] v2.8: 仅归还仍持槽位的实例。release已还的(release时_pop了_inst_map)不再归还, 防超归。
                    # 此前 bug: 只 pop _slot_held 不 sem.release → 每次 task teardown 丢1个token,
                    # sem._value 永久下滑至0 → 之后所有 acquire 卡满 ACQUIRE_WAIT_TIMEOUT 走temp。
                    # v2.9 BugFix(小欧 2026-08-06): "in检查"与"release"之间并发release锁外pop会双归还超归,
                    # 改为原子 pop(只有pop成功才release), 与release()的"pop成功才还槽"同一所有权转移规则。
                    if sem is not None and self._inst_map.pop(id(inst), None) is not None:
                        sem.release()
                    self._last_used.pop(id(inst), None)
                    close_list.append(inst)
                del self._pool[key]
                self._busy.pop(key, None)
        # [卡死场景C6] 锁外 close，不阻塞全池 — 小欧 2026-08-06
        for inst in close_list:
            try:
                inst.close()
                count += 1
            except Exception as e:
                logger.debug(f"关闭Shell实例失败: {e}")
        return count

    def cleanup_all(self) -> int:
        """关闭所有池中实例 — atexit 安全网 + 运行中 teardown 兜底"""
        close_list = []
        with self._lock:
            for key, lst in list(self._pool.items()):
                sem = self._sem.get(key)
                for inst in lst:
                    # [卡死场景C1] v2.8 修复: 归还仍持槽位的实例(slot 泄漏是 limiter 枯零根源)
                    # v2.9 BugFix(小欧 2026-08-06): 原子pop防与release()并发时的超归竞态, 同cleanup_by_task
                    if sem is not None and self._inst_map.pop(id(inst), None) is not None:
                        sem.release()
                    self._inst_map.pop(id(inst), None)
                    close_list.append(inst)
            self._pool.clear()
            self._busy.clear()
            self._inst_map.clear()
            self._last_used.clear()
        for inst in close_list:
            try:
                inst.close()
            except Exception as e:
                logger.debug(f"atexit清理Shell实例失败: {e}")
        return len(close_list)

    def get_all_pids(self) -> set:
        """返回所有活跃shell实例的PID集合(供安全检查保护自身进程) — 小欧 2026-07-31"""
        pids = set()
        with self._lock:
            for key, pool in self._pool.items():
                for inst in pool:
                    if inst._proc and inst._proc.poll() is None:
                        pids.add(inst._proc.pid)
        if pids:
            logger.debug(f"[ShellPool] get_all_pids: {len(pids)} 个活跃PID: {pids}")
        return pids


# 2026-08-07 小欧 三堂会审定稿(R3): 3→8 — 当日C2日志实测同key并发达5(ps7池默认3放不下),
# acquire排队超2s→ShellPoolBusyError; 8覆盖实测并发5并留余量(每实例约40MB内存, 8≈320MB可接受)
shell_pool = ShellPoolManager(max_per_type=8)


atexit.register(shell_pool.cleanup_all)
