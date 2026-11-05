# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: 临时输出文件读取保护线改引用 tool_constants.SHELL_OUTPUT_FILE_MAX_BYTES(原 _MAX_OUTPUT_SZ=10MB), 功能零退化
# 2026-07-18 - 小沈 - 修复多行命令(如 python -c "..." 含换行)经 -Command - 从stdin喂入导致PowerShell解析器卡死等待输入(见 logs 2026-07-18 21:34-21:44 step=15 跑满600s超时): 改为写入.ps1文件 + 向持久pwsh喂一句【单行】dot-source投递, 多行内容留在文件内不再经stdin流, 死锁消除; 功能零退化
# 2026-07-20 - 小欧 - 门限治理: SHELL_OUTPUT_FILE_MAX_BYTES 改名 SHELL_OUTLIMIT_RAW_BYTES(私有内部常量加 INER_ 前缀); 删除 shell_engine.py 本地重复定义, 统一引用 tool_constants 单源
# 2026-07-23 - 小欧 - 北京老陈驱动: safe_read_file 去掉 10MB head+tail 限制, 改为纯读; 删 SHELL_OUTLIMIT_RAW_BYTES import (仅保留 50K/20K tool 输出截断, 不需要磁盘读限制+字符截断两层)
# 2026-07-26 - 小沈 - 超时统一: 127行timeout=30→DEFAULT_TIMEOUT_SEC, 276行timeout=5→SUBPROCESS_TIMEOUT_SHORT, 286行timeout=5→SUBPROCESS_TIMEOUT_SHORT
# 2026-07-27 - 小欧 - 安全: exec()/_ensure_alive()/_start()加env参数, PS进程不再直接copy os.environ, 由调用方传_sanitize_env()过滤API key
# 2026-07-28 - 小欧 - 欧阳两处修复: _class_lock Lock→RLock防死锁; _poll_for_file delay 5ms/×1.5/0.1→100ms/×2/1.0减少系统调用
# 2026-07-28 - 小欧 - 新增 _preprocess_command 命令预处理: PS5.1 将 && 降级为 ;(顺序执行), Windows 将 python3 降级为 python
# 2026-07-28 - 小欧 - 修复两处命令解析缺陷: python3替换改用regex单词边界(避免误伤路径/版本号/包名); &&替换改用引号感知状态机(仅替换引号外的&&, 避免误伤字符串字面量)
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
# 2026-08-06 - 小欧 - 按设计文档实施H1-H10: ①新增探活常量+_probe()响应性探活; ②_start() stderr落日志+就绪握手; ③_close()显式关stderr句柄+残留读取+清理临时文件; ④ShellPoolManager新增_sem并发限流+_slot_held槽位记录; ⑤acquire()重构(Phase0限流/Phase1持锁找空闲/Phase2解锁探活/Phase3有界重试); ⑥release()/cleanup_by_task归还前查_slot_held防计数虚高; ⑦删除死代码shell/shell_engine.py
# 2026-08-06 - 小欧 - v2.7 BugFix: acquire()复用路径漏注册_inst_map(release()会pop, 复用后release拿key=None提前return → 信号量槽位泄漏, 并发下所有acquire等满ACQUIRE_WAIT_TIMEOUT); 由test_shell_pool_manager并发用例暴露(100.89s→41.21s); 复用路径补 self._inst_map[id(inst)] = key
# 2026-08-06 - 小欧 - 三堂会审终稿8项BugFix: ①cleanup_by_task池实例清理归还信号量槽位(防teardown后limiter枯零→全链卡慢, 复证free 2→1→0→0); ②self._lock Lock→RLock, _exec拆_exec/_exec_locked统一持锁(修_probe脱锁与exec并发写stdin串扰); ③Phase1空闲超时淘汰实例close移出池锁(修持池锁taskkill阻塞全池); ④acquire加env参数+execute_shell_command传_sanitize_env()(修启动copy os.environ泄漏API key); ⑤cleanup_by_task删temp循环内count+=1(修双计); ⑥新增_READY_PROBE_TIMEOUT=10s就绪握手(修冷启动>3s被误杀); ⑦_exec写stdin前poll探活(修向死进程写管道阻塞); ⑧F保留temp兜底(治#5防卡死设计, 非bug)
# 2026-08-06 - 小欧 - v2.8 单一信号量硬限流(用户北京老陈拍板最优解, 治F): ①删除temp兜底+超时继续——拿到槽位必然可复用或新建(池满⇒busy==max⇒拿不到槽), temp是死代码; 超时继续创建temp既绕过限流又卡10s, 是烂设计; ②ACQUIRE_WAIT_TIMEOUT 10→2s; ③拿不到槽位明确抛ShellPoolBusyError(调用方except捕获转build_error返回错误, 非卡死非500); ④删_slot_held/acquired布尔, 改用_inst_map存在性判定release/cleanup单次归还防超归(BoundedSemaphore超归会ValueError); ⑤删_temp_instances结构及相关分支; ⑥删除本次临时标记DETECT-TEST-TEMP
# 2026-08-06 - 小欧 - 修复cleanup_all遗漏: 归还sem槽位(防limiter枯零, 原cleanup_all只clear容器未sem.release, 运行中teardown调用后同key acquire全卡2s超时)
# 2026-08-06 - 小欧 - 卡死场景代码标注: 系统梳理多shell并行「后台卡死」14类场景(C1-C14), 在文件头加【场景索引】总表, 并在各处理代码点加[卡死场景C#]标注(供三堂会审/回归对照)。零逻辑改动, 全测试通过
# 2026-08-06 - 小欧 - 卡死场景日志补齐: 按C1-C14逐一核对各处理事件是否落地日志, 补齐缺漏(C2/C5/C8半死/C9/C10/C11/C13/C14), 统一[卡死C#]前缀标识分支序号, 级别用warning(卡死异常事件)/debug(正常淘汰/清理失败)。涉及shell_engine.py与execute_shell_command.py, 池测试19 passed
# 2026-08-06 - 小健 - 打猎测试定位并修复v2.9三个真实Bug: ①_probe()超时路径引用self._proc.pid崩溃(_exec超时内部已_close置_proc=None, pid引用→AttributeError), 改getattr(self._proc,'pid',None); ②cleanup_by_task/cleanup_all "in检查+release"与release()锁外pop存在超归竞态(cleanup锁内判断True后、sem.release前, release线程已pop拿到key并release → 双归还BoundedSemaphore超归抛ValueError), 改原子pop(仅pop成功才release), 与release()同一所有权转移规则; ③acquire C6淘汰日志it._proc.pid对无_proc对象(Mock) AttributeError, 改getattr嵌套防御。测试: test_shell_pool_manager 19→28用例(新增半死剔除/exec自愈/槽位守恒/并发不超归/高并发sem守恒), 全shell套件266 passed
# 2026-08-06 - 小健/小欧 - v2.10打猎第5~7个真实Bug: ⑤_start失败路径stderr临时文件泄漏(C12): Popen抛异常/进程立即退出两条失败路径残留ps_*.err(初测ps_0k3lbafn.err), 加_close()后_stderr_path置None但文件仍在磁盘(内联open()句柄泄漏→Windows句柄被占无法unlink) → 重构为self._stderr_handle持句柄, Popen异常时显式关闭并置None, Popen成功后置None交接子进程, _close()同步关闭句柄+unlink临时文件; ⑥C11,execute业务模块: taskkill失败后裸proc.kill()兜底, 进程已死时ProcessLookupError冒泡中断残存读取 → try/except包住+warning防丢失(execute_shell_command.py); ⑦acquire重试×并发cleanup超归: acquire Phase2阻塞期间并发cleanup原子pop+sem.release归还槽位, acquire Phase3重试注册新实例后调用方release再归一次 → BoundedSemaphore超归ValueError(shell_engine.py:633)。修复: acquire重试前用原子_inst_map.pop判定槽是否已归还(lost_slot), 已归还则sem.acquire重取一槽供新实例; owning_slot标记actual持槽, except仅实际持有才release, 杜绝空释/超归。hunt测试params_hunt_v3 2用例确定性复现→修后绿
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
# 2026-08-07 - 小欧 - B6.1/B6.2 回归测试挖出四缺陷并根治(B6结构性缺陷, 三堂会审定稿):
#        BUG#1: `;`复合命令前段出错, $?只反映最后一条→rc漏报0(错误进err但业务层判success) — test_error_after_success_pipeline
#        BUG#2: PS5 native写stderr使$?变False→成功命令误报rc=1(PS7/PS5行为不一致) — test_ps5_native_stderr
#        BUG#3: $LASTEXITCODE跨命令残留污染(先native exit3再跑cmdlet→rc误报3) — 探测复现
#        BUG#4: throw终止性错误中断ps_cmd→rc文件不写→假超时(C8/C14)30s+杀进程+引擎重建 — 探测复现
#        B6.1修复: ①前置$global:LASTEXITCODE=0清残留(治BUG#3) ②rc判定改errs分类: LASTEXITCODE非0→取其值
#        (native真失败); errs含非NativeCommandError错误→1(cmdlet真错); NativeCommandError(native stderr)不计错
#        (治BUG#1/2) ③try/catch兜底终止性错误, catch记录文本到errs+rc=1(治BUG#4)
#        B6.2微调(探测发现B6.1块外catch致throw前stdout丢失): try/catch移入& {}块内, catch后管道不中断
#        →throw前的stdout完整落盘(实测Write-Output before; throw→out保留before), 其余语义同B6.1
#        验证: PS7/PS5双引擎9场景行为一致, B6+B6.1共41用例全绿(其中10例为四缺陷固化回归)
# 2026-08-08 - 小欧 - ParserError快速失败(北京老陈驱动, 三堂会审通过): command从内联改独立cmd.ps1文件,
#        ps_cmd内dot-source该文件+try/catch包在dot-source外层 → 解析期错误(ParserError)由运行时catch捕获
#        → rc/err文件正常落盘 → 引擎立即返回build_error, 不再空等60s假超时(问题二真病根, 详见日志挖掘报告)。
#        实证: 尾逗号语法错误命令, 裸ps1 0.68s返回 / 原内联结构空等11.77s假超时 / 本方案0.x秒rc=1+err原文。
#        普遍性: dot-source延迟解析覆盖整类ParserError(尾逗号/括号不匹配/引号未闭合/操作符错误), 非特判;
#        与BUG#4同族同根, 提炼设计原则"rc落盘无条件化"。回归护栏用例6个(4类ParserError+正常多行+throw)。
#        回归: 本结构下try/catch语义等价B6.2(throw前stdout保留), 全shell套件需重跑266 passed核对。
# 2026-08-08 - 小欧 - 临时文件.cwd竞态残留根治(v2.11, 北京老陈驱动, 实测复现): 整批shell测试全跑时
#        tmpXXX.cwd残留(单独跑零残留/整文件全跑复现). 根因: ps_cmd最后一行才写.cwd, Python侧_poll_for_file
#        (.code非空)即返回→立即unlink时PS的Out-File可能仍在写.cwd/句柄未释放→OSError→文件残留(仅.cwd泄漏,
#        与ps1/out/err/code模式一致印证"最后写入者"竞态). 修复: ①_code成功后补等.cwd非空(_CWD_WAIT_TIMEOUT=3s,
#        .cwd非空=PS完成最后Out-File句柄必已释放, 正常毫秒级不拖慢) ②抽取_safe_unlink复用函数(短退避重试
#        _UNLINK_RETRY×50ms覆盖句柄延迟释放窗口, 仍失败才warning留痕R4语义不变): _TempFiles.finally(命令级6文件)
#        与_close()(引擎级stderr文件, 原静默pass升级为重试+留痕)统一走此函数, 一处逻辑两处受益(DRY+复用优先).
#        验证: 修复前整批51测试必现tmpXXX.cwd泄漏→修复后51 passed零新增残留; 泄漏测试连跑3轮全过; 全shell套件
#        200 passed, 1 skipped零回归. 命名: _CWD_UNLINK_RETRY→_UNLINK_RETRY(作用于全部6文件, 去误导前缀, 三堂会审修正).
# 2026-09-19 - 小欧 - 落地清理链 M1-M9(设计文档核查v1.5后北京老陈令实施, 两项最高优先级缺陷):
#   M1 新增_CLEANUP_GUARD_TIMEOUT=15(守卫join上限+探针阈值)；
#   M2 新增_poll_pid_exit()有界轮询确认进程退出(替代裸wait, poll()非阻塞永不卡)；
#   M3 _kill_tree()支持快照proc参数+taskkill异常即kill兜底不变+成功后_poll_pid_exit二次确认防假活；
#   M4(并入M3) 原_close内kill+wait裸杀段删除；
#   M5 _close()复用_kill_tree(DRY单路径, 消除重复), stderr句柄/临时文件清理保持原样；
#   M6 _exec_locked超时分支改_cleanup_guarded() daemon线程守卫: 主线程快照_proc后立即置None/_alive=False,
#     join(timeout=15)有界放行+耗时探针留痕, OS级挂起不再楔死上层(修复卡死病根)；
#   M7 _probe()活异常捕获保序: _exec任何异常→_close→return False, 错误上报+重试必达；
#   M8 acquire Phase2注释硬化(契约: 失败必return False经_close销毁, release判活条件防假活回流)。
#   M9 保险丝630s保留不动(纵深最后防线)。验证: shell_engine语法+池测试全绿见会话记录。
#   合规: KISS-DIRECT(有界轮询替代原语等待)+DRY(_close至_kill_tree单路径)+禁止backward(直接强化清理链)。
#   行使权限: PATCH级自主实施(北京老陈指定最高优先级) — 小欧-2026-09-19
# 2026-09-19 - 小欧 - 五真实bug修复(北京老陈令"每bug核实3遍+修复方案3轮三堂会审", 全流程见会话记录):
#   超时分支丢stderr回收(M5契约违例, Temp积压58个ps_*.err): 抽取_discard_stderr(proc, defer_unlink)单一路径,
#     _close/M6守卫超时分支共用, 先关句柄再unlink幂等, defer_unlink时仅状态回收(_stderr_path置None), unlink延后await进程死后执行。
#   daemon线程无异常兜底(原: 异常静默死亡→is_alive()=False被误判"清理链完成"假成功+孤儿不可回收): _worker包try/except+
#     err_box留痕, _await_cleanup_guard三分支判定, 异常走主线程有界兜底_kill_tree再杀一次, 绝不假报完成。
#   _poll_pid_exit无poll异常保护(poll异常穿透_kill_tree): poll包try/except, 异常warning+return False(未确认退出, 交上层kill兜底)。
#   kill兜底只杀根树(taskkill异常时子树pwsh→cmd→ping成孤儿): 新增_kill_fallback(有界重试taskkill /T→根kill)
#     +_kill_descendants(单次Get-CimInstance快照+BFS后代强杀), 替换_kill_tree两处兜底, 总有界≤10s。
#   _cleanup_guarded join(≤15s)持锁违反"超时即逝/锁立即释放"(exec/_exec双层with self._lock包住join, 实测第二线程纯锁等待3.85s):
#     拆_cleanup_guard_start()(锁内微秒级: 快照/置死/daemon启动/stderr回收) + _await_cleanup_guard()(锁外join/兜底/观测);
#     exec锁内直调_exec_locked, await置最外层锁外; _cleanup_guarded()=start+await组合保留; __init__增_guard_ctx=None。
#     连带时序归正: _discard_stderr增defer_unlink参数(start调用defer=True仅关句柄, await join后进程必死再unlink成功);
#     命令级_TempFiles 6文件登记ctx["temp_files"], await join后补unlink(进程未死时_TempFiles.finally的_safe_unlink必失败残留)。
#   验证: 全量回归 6波42 + 池33 + 组合3689 全绿, Temp ps_*.err清零无孤儿进程(超出原计划追加波回归由测试文件承载)。 — 小欧-2026-09-19 10:40
# 2026-09-22 小欧 - constants.py 配置化迁移：shell_pool 槽位改读 tuning 配置
# 2026-10-09 - 小欧 - _CLEANUP_GUARD_TIMEOUT 15→10(北京老陈裁定「全局15 清理阀门为10」): 本值是OS级挂起时清理链最长等待的设计上限非实测值(实测365.2ms, 不可用实测替代设计阈值定档); 10s仍完整覆盖taskkill(5s)+_poll_pid_exit二次确认(5s)+unlink(0.15s)。
# 强耦合·改一须破一同步: 本值 < INSURANCE_BUFFER(15) ⇒ 保险丝恒晚于_await_cleanup_guard返回, 绝不截断补清理; 日后若调到>15须同步上调BUFFER否则临时文件残留。实测timeout=2死循环: 清理365.2ms/总3.92s(<窗口17s)/6临时文件零残留; 边界留痕: "守卫线程异常死亡"兜底分支理论最坏 join(10)+_kill_tree(≤10)=20s>15, 触发前提极苛刻不改(该兜底是清理残留最后一道, 削它属本末倒置)。compliance: KISS-DIRECT/禁止backward
# 2026-11-04 小欧 - 根治 shell 卡死全局放大(逐线程取证: 4个新建线程 CPU=0 且 _started 从未置位, 卡在 Thread.start()):
#   ① _exec_locked 删"每条命令起临时写线程"(_wrt.start() 是卡死点) → 实例级常驻 _StdinWriter 单线程, 线程创建从每命令一次降为每实例一次;
#   ② _probe 改轻量探活(proc.poll + 写通道健康), 不再复用 _exec(原探活要建6个临时文件+全套执行框架, 使 acquire 复用路径成为卡死入口);
#   ③ _start 就绪握手仍真跑一条探针(_exec): stdout=DEVNULL 无法回读, 且必须验证"能执行",
#     冷启动~1.5s 必须落在 _start 内(否则占用调用方 timeout, timeout=1 会反复重建);
#     该路径原本也走 _exec, 线程创建点已由 ① 根除, 故无新增风险。
#   验证: 池/引擎测试全绿, acquire 复用探活由秒级降至微秒级, 就绪语义与旧实现一致。
# 2026-11-04 小欧 - 根治"超时清理链自身成为死锁点"(8500 打包环境事故复盘):
#   现象: 3 次命令超时后, 3 个 shell executor 线程永久报废、7 个 pwsh 成孤儿(父进程已退出),
#         "清理链完成/超守卫/线程异常"三类日志一条都没有 —— 清理链压根没跑完; 应用随后整体僵死须人工杀进程。
#   根因: Windows 上 CreateProcessW 调用期持 loader lock 且不释放 GIL, Thread.start() 等 loader lock 无超时
#         → 二者并发即永久互锁(实证 pyspy/hang_20261104_0115: MainThread 卡 Thread.start, 看门狗卡 Popen.__init__)。
#         而超时路径恰好同时做这两件事: _cleanup_guard_start() 建清理线程 + _kill_tree() 起 taskkill/powershell。
#   修法: ① 清理链改投常驻线程(app.utils.serial_worker), 运行期零 Thread.start();
#         ② _kill_tree/_kill_fallback/_kill_descendants 删 taskkill 与 powershell 子进程, 改 psutil(Win32 API)+proc.kill();
#         ③ 新增 prewarm_shell_binaries(), 把首次 CreateProcessW 挪到启动期, 不在用户命令路径上冷启动。
#   2026-11-04 小欧 - 收口最后一处运行期建线程: _StdinWriter 的线程改由导入期预建的
#         _StdinWriterPool 租借(池耗尽才兜底新建, 且必须过 spawn_gate 闸门);
#         spawn_gate 全局串行化 Thread.start × CreateProcessW, 覆盖所有调用点(不靠逐点记忆)。
#   2026-11-04 小欧 - 分层收口: 树杀/后代清杀移入 app.utils.proc_utils(通用进程层);
#         线程池统一为 app.utils.workers.WorkerPool / ThreadLeasePool(取代 serial_worker + 两处私有池);
#         闸门改有界等待+快速失败(无限等待=僵死, 只是换个位置), 指标经 /health 暴露;
#         即: 本文件只留 shell 协议与生命周期, 不再持有通用进程/线程原语。
#         历史条目中的 taskkill/Thread.join/serial_worker/_kill_fallback/_kill_descendants/
#         _StdinWriterPool/_ShellWorkerPool 均属已删实现, 保留为变更轨迹, 勿据其理解现状。
#   2026-11-04 小欧 - 复核修正: _CLEANUP_POOL 1→3(单 worker 挂起即永久失效, 清理能力静默丧失);
#         _StdinWriter 删池耗尽兜底新建线程(兜底本身即运行期 Thread.start) → 池满判损坏;
#         删生产零调用的 _cleanup_guarded(死代码), 调用方统一 start + await 两段式。
# 2026-11-05 小欧 - 池键坍缩哨兵: acquire 收到空 task_id 时告警一次(原静默把全进程 shell 挤进同一个
#         (None, shell_type) 池), 并把 ShellPoolBusyError 文案写明"宿主并发限流", 防模型误判成文件权限问题。
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
import concurrent.futures
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from app.logger import logger, log_recovered  # ② 已自愈档 — 小欧 2026-10-06
from app.tools.tool_constants import SHELL_POOL_IDLE_TIMEOUT, SUBPROCESS_TIMEOUT_SHORT
from app.config import get_config  # 池容量按 tuning 配置计算(配置派生值留在使用方) — 2026-11-04 小欧
from app.utils.proc_utils import kill_process_tree  # 2026-11-04 小欧: 通用进程树清杀移出本文件(分层)
from app.utils.proc_io import run as proc_run  # 2026-11-04 小欧: 零线程读管道(取代 subprocess.run 的 _readerthread)
from app.utils.workers import ThreadLeasePool, WorkerPool  # 2026-11-04 小欧: 常驻线程池统一实现


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
#       → 实例级写通道 _StdinWriter(池 worker + 队列 + Event 有界等待) + 写前poll探活; 超时=写线程卡住→判死重建 — 2026-11-04 小欧
#   C6  锁内阻塞操作→拖死全池
#       → acquire evict_to_close / release close / cleanup close 全部移出池锁
#   C7  池锁↔实例锁交叉死锁
#       → 锁序固定「先池锁释放→再拿实例锁」, 从不嵌套持有(无环可成)
#   C8  半死进程(假活)复用→exec挂起
#       → _probe()轻量探活(进程存活+写通道健康, 微秒级, 不建临时文件/不起线程) + 真执行timeout兜底kill — 2026-11-04 小欧
#   C9  清理打断in-flight exec
#       → close() acquire(timeout=5)未获锁也force-kill进程; exec侧_poll_for_file有界返回
#   C10 子进程持管道→communicate挂满(仅cmd/bash分支)
#       → execute_shell_command.py: cmd poll-loop代替communicate; bash捕获TimeoutExpired→_kill_and_read_output
#   C11 kill/wait自身阻塞
#       → _kill_tree 零建进程(psutil 枚举后代 + proc.kill) + _poll_pid_exit 二次确认, _close/proc.wait 有界
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
_READY_PROBE_TIMEOUT = 10        # 就绪握手超时(秒)：首次启动慢(profile/杀软/慢盘)放宽到10s, 防误杀刚拉起进程 — 小欧 2026-08-06
_PROBE_CMD = "Write-Output __OMNI_PROBE__"   # 就绪握手探针命令：轻量、无副作用、输出唯一标记 — 小欧 2026-08-06
ACQUIRE_WAIT_TIMEOUT = 2        # acquire 并发限流等待超时(秒)：有界排队, 超时明确抛ShellPoolBusyError(不temp不卡死) — v2.8 小欧 2026-08-06
_CWD_WAIT_TIMEOUT = 3           # .cwd落地等待超时(秒)：ps_cmd最后一行才写.cwd, code有内容≠PS执行完, 等.cwd非空=PS已完成最后Out-File(句柄已释放) — v2.11 小欧 2026-08-08
_UNLINK_RETRY = 3               # 临时文件unlink失败重试次数：覆盖Out-File句柄延迟释放竞态窗口(作用于全部6个临时文件) — v2.11 小欧 2026-08-08
_UNLINK_RETRY_DELAY = 0.05      # unlink重试间隔(秒)：50ms×3≈150ms, 覆盖PS进程写完文件到句柄释放的毫秒级窗口 — v2.11 小欧 2026-08-08
_CLEANUP_GUARD_TIMEOUT = 10     # [M1] 清理链守护线程join超时(秒): M6守卫线程清理的最长等待+探针观测阈值 — 小欧 2026-09-19
                                 # 2026-10-09 - 小欧 - 15→10(北京老陈裁定「清理阀门为10」):
                                 #   清理链实测 349.7ms, 但本值是"OS级挂起时的设计上限", 不可用实测值替代设计阈值定档。
                                 #   10s 仍覆盖 _poll_pid_exit 二次确认(SUBPROCESS_TIMEOUT_SHORT=5)+unlink重试0.15s。
                                 #   2026-11-04 小欧: taskkill 已删(改 psutil+proc.kill, 不建进程), 该预算更宽裕。
                                 #   ★ 与保险丝的关系(必须同步, 否则改一破一):
                                 #     tool_retry_engine.INSURANCE_BUFFER = 15 > 本值 10,
                                 #     ⇒ bash 超时后保险丝恒晚于 _await_cleanup_guard 返回, 绝不截断补清理(:731-733)。
                                 #   若日后有人把本值调到 >15, 必须同步上调 INSURANCE_BUFFER, 否则临时文件将残留。
_LOCK_WAIT_GUARD = 10        # 实例锁等待护栏(秒): 等锁上限=_LOCK_WAIT_GUARD+命令timeout, 超时返回_ERROR_LOCK_BUSY — 治理层3 小欧 2026-10-04
_STDIN_WRITE_TIMEOUT = 5     # stdin写入上限(秒): 超时=存活不读(管道背压/半死) → M6守卫清理+重启 — 治理层3 小欧 2026-10-04
_STDIN_POOL_SIZE = max(32, int(get_config().get("tuning.concurrency.shell_pool_max_per_type", 8)) * 4)  # stdin写线程池: 与执行器同键同式, 不再写死32 — 2026-11-04 小欧
_STDIN_POOL_LEASE_TIMEOUT = 5  # 租借写线程上限(秒): 池满/全卡住 ⇒ 判写通道损坏, 有界失败 — 2026-11-04 小欧
_ERROR_LOCK_BUSY = {"stdout": "", "stderr": "shell instance lock busy", "exit_code": -1}   # 等锁超时明确失败,dict模式同:188 — 治理层3 小欧 2026-10-04

# 超时清理链常驻 worker: 运行期只投递, 零 Thread.start(Thread.start × CreateProcessW 会互锁)
# 3 个而非 1: proc.kill 可能 OS 级挂住, 单 worker 卡死即永久失效 → 清理能力静默丧失
_CLEANUP_POOL = WorkerPool(3, "shell-cleanup")


def prewarm_shell_binaries() -> None:
    """启动期预热 ps7/ps5: 把首次 CreateProcessW(Defender 扫描/loader lock 长窗口)挪出请求路径。
    串行各跑一次 `-NoProfile -Command exit`; 有界(_READY_PROBE_TIMEOUT), 失败仅告警不阻断启动。"""
    for shell_type, exe in (("ps7", "pwsh.exe"), ("ps5", "powershell.exe")):
        path = shutil.which(exe)
        if not path:
            logger.warning(f"[Shell预热] {shell_type}({exe}) 未找到, 跳过")
            continue
        t0 = time.monotonic()
        try:
            proc_run([path, "-NoProfile", "-Command", "exit"],
                     capture_output=True, timeout=_READY_PROBE_TIMEOUT)
            logger.info(f"[Shell预热] {shell_type} 完成 ({time.monotonic() - t0:.0f}ms)")
        except Exception as e:
            logger.warning(f"[Shell预热] {shell_type} 失败(不影响启动): {e}")

# ═══════════════════════════════════════════════════════
#  _StdinWriter — 实例级 stdin 写通道(worker 来自启动期预建租约池)
# ═══════════════════════════════════════════════════════

class _StdinWriter:
    """实例级 stdin 写通道: 线程来自启动期预建池, 写操作有界等待 — 2026-11-04 小欧

    【为什么必须常驻】原 _exec_locked 每条命令 new 一个临时写线程并 join；
    事故取证(2026-11-04)显示 Thread.start() 在 Windows 线程入口偶发停顿：
    新线程 CPU=0 且 threading.Event._started 从未置位，主线程永久卡在
    threading.Thread.start() 内 → 该 executor worker 再也回不来 → 超时重试逐个烧掉
    默认 executor → getaddrinfo 也排不上 → 事件循环整体僵死。
    【当前形态】worker 由 ThreadLeasePool 在导入期建好并租借, 运行期零 Thread.start;
    命令路径只剩 queue.put + Event.wait(timeout)。池耗尽 ⇒ 写通道判损坏(有界失败),
    不再兜底新建线程 —— 兜底本身就是运行期 Thread.start, 与"运行期零建线程"自相矛盾。

    【有界语义】写线程卡在 stdin.write(管道背压/进程半死)时，调用方 wait 超时即返回，
    由 _exec_locked 判死并走守卫清理+重建；卡住的 worker 不返回即永久占用该租约槽位(不自愈)。
    """

    _SENTINEL = object()

    def __init__(self, stdin, name: str = "shell-stdin-writer"):
        self._stdin = stdin
        self._q: "queue.Queue" = queue.Queue()
        self._broken = False
        if not _STDIN_POOL.lease(self._serve, _STDIN_POOL_LEASE_TIMEOUT):
            # 池耗尽 = 已有 N 个写线程全卡死: 判写通道损坏, 由 _probe/守卫走判死重建。
            # 不兜底新建线程: 那等于运行期 Thread.start, 正是本类要消除的对象。
            self._broken = True
            logger.error(f"[Shell] stdin 写线程池耗尽({_STDIN_POOL_SIZE} 全忙/卡住) → 写通道判损坏 {name}")

    def _serve(self):
        """服务本 writer 直到收到退出哨兵(池 worker 复用入口) — 2026-11-04 小欧"""
        while True:
            item = self._q.get()
            if item is _StdinWriter._SENTINEL:
                return
            data, evt, box = item
            try:
                self._stdin.write(data)
                self._stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as e:
                box.append(e)
            finally:
                evt.set()

    def write(self, data: bytes, timeout: float) -> Optional[BaseException]:
        """有界写入：None=成功；异常实例=写失败(管道死)；TimeoutError=写线程卡住。"""
        if self._broken:
            return BrokenPipeError("stdin writer 已标记损坏")
        evt = threading.Event()
        box: list = []
        self._q.put((data, evt, box))
        if not evt.wait(timeout):
            self._broken = True     # 卡住的写线程无法自愈，后续写直接快速失败，促调用方判死重建
            return TimeoutError(f"stdin写入{timeout}s未返回")
        return box[0] if box else None

    def healthy(self) -> bool:
        """写通道健康 = 未标记损坏(仅查状态, 不做任何阻塞操作)。"""
        return not self._broken

    def stop(self):
        """投递退出哨兵(不 join)：_serve 收到即返回并归还池 worker；卡在 write 时永久占用该槽位(不自愈)。"""
        self._broken = True
        self._q.put(_StdinWriter._SENTINEL)


_STDIN_POOL = ThreadLeasePool(_STDIN_POOL_SIZE, "shell-stdin")


# ═══════════════════════════════════════════════════════
#  _TempFiles — 临时文件 contextmanager
# ═══════════════════════════════════════════════════════

def _safe_unlink(path: str) -> bool:
    """安全删除临时文件：unlink失败短退避重试, 覆盖句柄延迟释放竞态 — [卡死场景C12] v2.11 小欧 2026-08-08

    背景: PS进程Out-File写完文件后句柄尚有毫秒级释放窗口, Python侧立即unlink会OSError→文件残留
    (实测整批shell测试触发tmpXXX.cwd残留)。重试仍失败才warning留痕(R4语义), 返回False供调用方感知。
    复用点: _TempFiles.finally(命令级6文件) 与 _close()(引擎级stderr文件) 统一走此函数, 一处逻辑两处受益。
    """
    for attempt in range(_UNLINK_RETRY):
        try:
            os.unlink(path)
            return True
        except OSError:
            if attempt == _UNLINK_RETRY - 1:
                # 2026-08-07 小欧 三堂会审定稿: debug→warning 升级可见性, 清理失败=残留句柄/文件泄漏风险,
                # 当日残留 tmpmsj4losd.cwd 即此场景, 需在info级日志留痕以便溯源
                logger.warning(f"[卡死C12] 临时文件清理失败(残留句柄?) (path={path})")
                return False
            time.sleep(_UNLINK_RETRY_DELAY)
    return False


@contextlib.contextmanager
def _TempFiles():
    """安全创建 6 个临时文件并自动清理 — out/err/code/cwd/ps1/cmd  — [卡死场景C12] 小欧 2026-08-06"""
    paths = {}
    try:
        # ps1: 2026-07-18 小沈 新增, 存多行命令脚本(避免直接经stdin喂入导致PS卡死)
        # cmd: 2026-08-08 小欧 新增, 存LLM原始命令(独立文件), 供framework dot-source —
        #   解析期错误(ParserError)在dot-source运行时抛出, 可被外层try/catch捕获(内联则catch接不住→假超时)
        #   ⚠ 后缀必须.ps1(非.cmd): PowerShell dot-source对.cmd文件走cmd.exe批处理而非PS解析器,
        #     ParserError捕获失效(回归测试10用例当场抓出, tmpXXX.cmd→"not recognized") — 小欧 2026-08-08
        for name, suffix in (
            ("out", ".out"), ("err", ".err"), ("code", ".code"),
            ("cwd", ".cwd"), ("ps1", ".ps1"), ("cmd", ".ps1"),
        ):
            f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix,
                                             mode="w", encoding="utf-8")
            f.close()
            paths[name] = f.name
        yield type("Paths", (), paths)()
    finally:
        for p in paths.values():
            # v2.11 小欧 2026-08-08: unlink失败=句柄延迟释放竞态(实测整批shell测试触发tmpXXX.cwd残留) —
            #   PS进程Out-File写完文件后句柄尚有毫秒级释放窗口, Python侧立即unlink会OSError→文件残留。
            #   修复: 统一走_safe_unlink短退避重试覆盖该窗口(与_close()的stderr清理共享同一逻辑)
            _safe_unlink(p)


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


def _poll_pid_exit(proc: Optional["subprocess.Popen"], timeout: int, interval: float = 0.1) -> bool:
    """有界轮询确认进程已退出：替代裸 `proc.wait(timeout)` 的二次确认。
    背景: proc.kill/proc.wait 可能在 Windows 内核级原语上静默挂起(无异常无返回) → 本轮询
    poll() 为纯查询不阻塞, 超 timeout 秒即返回 False, 绝不永久阻塞 — 小欧 2026-09-19
    修复(小欧 2026-09-19) poll() 抛异常(句柄失效/ProcessLookupError/OSError)必须本地化:
    poll 异常=进程状态未知 → 立即返回 False(未确认退出), 让上层 kill 兜底(宁可多杀也不假死);
    绝不把底层异常透传给清理 worker/二次确认层(否则误判为清理链异常, 触发多余兜底重杀)."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            exited = proc is None or proc.poll() is not None
        except Exception as e:
            # 异常本地化: 查询中断即终止轮询, 返回未确认(False), 由上层致命兜底决定再杀 — 小欧 2026-09-19
            logger.warning(f"[M2] pid 确认轮询 poll() 异常(句柄失效?) → 未确认退出, 交上层兜底 (proc={proc and getattr(proc, 'pid', None)}, err={e!r})")
            return False
        if exited:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(interval, max(0, deadline - time.monotonic())))


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
        self._stdin_writer: Optional[_StdinWriter] = None   # 实例级常驻写线程(命令路径零线程创建) — 2026-11-04 小欧
        self._guard_ctx: Optional[dict] = None    # [守卫拆分 小欧 2026-09-19] 守卫拆分上下文: 见 _cleanup_guard_start/_await_cleanup_guard

    # ── 公共方法 ────────────────────────────────

    def exec(self, command: str, timeout: int = 60, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        # [守卫拆分 小欧 2026-09-19] 原封装: 外层 with self._lock 包裹整个 exec(含 _exec 内 await) →
        # 守卫 join(≤15s) 仍被 exec 外层锁包住, 同实例并发调用最长阻塞 15s(违反"锁立即释放"承诺, wave6 实测3.85s)。
        # 修复: 本层直调 _exec_locked(锁内仅微秒级 start), join/兜底(_await_cleanup_guard) 放最外层锁外。
        _t_enter = time.perf_counter()
        logger.info(f"[Shell打点] exec进入 cmd={command[:80]!r} timeout={timeout} (pid={getattr(getattr(self, '_proc', None), 'pid', None)})")  # 治理观测: 进入段之前落盘, 卡死时末行即断点 — 小欧 2026-10-04
        result = None
        # 治理层3(2026-10-04 小欧): 等锁有界, 上限=_LOCK_WAIT_GUARD+timeout; 持有方异常时明确失败, 不无限排队。
        if not self._lock.acquire(timeout=_LOCK_WAIT_GUARD + timeout):
            logger.warning(f"[卡死C3b] 实例锁等待{_LOCK_WAIT_GUARD + timeout}s超时 → 返回shell instance lock busy (cmd={command[:64]!r})")
            return dict(_ERROR_LOCK_BUSY)
        try:
            logger.info(f"[Shell打点] exec持锁(等待{int((time.perf_counter() - _t_enter) * 1000)}ms) cmd={command[:80]!r}")  # 治理观测: 进入→持锁间隔=等锁耗时 — 小欧 2026-10-04
            for attempt in range(2):
                if not self._ensure_alive(env):
                    if attempt == 0:
                        self._close()
                        continue
                    return dict(_ERROR_NO_SHELL)
                result = self._exec_locked(command, timeout)
                if result.get("exit_code") != _EXIT_PROCESS_DIED:
                    break
                self._close()
            else:
                return dict(_ERROR_NO_SHELL)
        finally:
            self._lock.release()
        if result and result.get("timed_out"):
            self._await_cleanup_guard()       # 锁外: join(≤_CLEANUP_GUARD_TIMEOUT) + 异常兜底 + 观测留痕, 不阻塞任何调用方
        logger.info(f"[Shell打点] exec返回 elapsed={int((time.perf_counter() - _t_enter) * 1000)}ms exit_code={result.get('exit_code') if isinstance(result, dict) else None} cmd={command[:80]!r}")  # 治理观测 — 小欧 2026-10-04
        return result

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

    def _probe(self) -> bool:
        """轻量探活(纯状态查询, 微秒级, 不建临时文件/不起线程/不执行命令) — 2026-11-04 小欧

        判据: 进程存活(poll) + stdin 写通道健康(_StdinWriter 未损坏且线程存活)。
        【为什么不再复用 _exec】原实现每探活一次就要建 6 个临时文件、走完整执行框架、
        再起一个写线程 —— 使 acquire 复用路径本身成为卡死入口(本次事故 step4 即
        acquire→_probe→_exec→Thread.start 卡住)，且正常路径白付秒级开销。
        【半死进程怎么办】探活不再验证"命令能否执行"，这类实例在真执行时由
        _poll_for_file(timeout) 捕获 → 守卫杀进程 → release 判死剔除 → 下次重建。
        代价是偶发一次 timeout，换来探活零成本、零卡死风险。
        【M7 保序】任何异常都不得逃逸出本方法，统一判不可用并销毁。"""
        try:
            if self._proc is None or self._proc.poll() is not None:
                return False                      # 进程已死/未启动 → 不可复用
            w = self._stdin_writer
            if w is None or not w.healthy():
                logger.warning(f"[卡死C8] 探活失败(stdin写通道不可用)→销毁 (pid={getattr(self._proc, 'pid', None)})")
                self._close()
                return False
            return True
        except Exception as e:                    # [M7] 异常本地化: 上报必达, 绝不向上抛 — 小欧 2026-11-04
            logger.warning(f"[卡死C8] 探活异常→销毁重建 (err={e!r})")
            try:
                self._close()
            except Exception:
                pass
            return False

    def _ready_handshake(self) -> bool:
        """启动就绪握手: 真跑一条探针命令, 确认 pwsh 已能执行(不只是管道可写) — 2026-11-04 小欧

        【为什么必须真执行】① stdout 是 DEVNULL, 无法靠回读输出判就绪, 只能看结果文件;
        ② "管道可写"不等于"能执行": profile 损坏/解析器异常只有真跑一条才暴露;
        ③ 冷启动实测约1.5s, 必须落在 _start 内 —— 否则这1.5s会占用调用方的 timeout 预算,
           timeout=1 的命令在重启后必然再次超时, 陷入"超时→重建→再超时"的恶性循环。
        【为什么现在安全】旧实现的问题不在本路径, 而在 _exec_locked 每条命令都新建写线程
        (Thread.start 是事故卡死点); 该点已由实例级常驻 _StdinWriter 根除, 故此处复用
        _exec 不再有任何线程创建。且本方法只在新建实例时走一次(_probe 热路径已改轻量状态查询)。
        【M7 保序】异常不外抛, 统一判未就绪。"""
        try:
            result = self._exec(_PROBE_CMD, timeout=_READY_PROBE_TIMEOUT)
        except Exception as e:                    # [M7] 异常本地化 — 小欧 2026-11-04
            logger.warning(f"[卡死C8] 就绪握手异常→判未就绪: {e!r}")
            return False
        if result.get("timed_out"):
            logger.warning("[卡死C8] 就绪握手超时(冷启动过慢/进程半死)→判未就绪")
            return False
        return "__OMNI_PROBE__" in (result.get("stdout") or "")

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
            # ② 常驻写线程 + 就绪握手(轻量)：启动后立即投一条探针确认管道可写、进程未秒退 — 2026-11-04 小欧
            # v2.7 BugFix(小欧 2026-08-06): 握手用 _READY_PROBE_TIMEOUT(10s), 避免冷启动>3s被误杀
            self._stdin_writer = _StdinWriter(self._proc.stdin)
            if not self._ready_handshake():
                # ② 补偿已完整: 半死进程被 _close 销毁并由调用方重建, 无泄漏无损坏 → RECOVERED(②)
                log_recovered(logger, "[PersistentShell] 就绪握手失败，进程未就绪(已销毁待重建)")
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
        # [守卫拆分 小欧 2026-09-19] 超时守卫 join/兜底 移到锁外(_await_cleanup_guard): 锁内仅微秒级 start,
        # 使"锁立即释放"契约成立(实测修复前第二线程被 join 阻塞 3s; 修复后立即放行).
        # 治理层3(2026-10-04 小欧): 同exec等锁有界; _probe调用拿不到锁→返回lock busy→stdout无探活标记→判False走C13重建。
        if not self._lock.acquire(timeout=_LOCK_WAIT_GUARD + timeout):
            logger.warning(f"[卡死C3b] _exec实例锁等待{_LOCK_WAIT_GUARD + timeout}s超时 → 返回shell instance lock busy (cmd={command[:64]!r})")
            return dict(_ERROR_LOCK_BUSY)
        try:
            result = self._exec_locked(command, timeout)
        finally:
            self._lock.release()
        if result.get("timed_out"):
            self._await_cleanup_guard()       # 锁外: join(≤_CLEANUP_GUARD_TIMEOUT) + 异常兜底 + 观测留痕, 不阻塞任何调用方
        return result

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
            # [B6.1] 2026-08-07 小欧 回归测试挖出B6四缺陷并根治(三堂会审定稿):
            #   BUG#1: `;`复合命令前段出错,$?只反映最后一条→rc漏报0(错误进err但业务层判success)
            #   BUG#2: PS5 native写stderr使$?变False→成功命令误报rc=1(PS7/PS5行为不一致)
            #   BUG#3: $LASTEXITCODE跨命令残留污染(先native exit3再跑cmdlet→rc误报3)
            #   BUG#4: throw终止性错误中断ps_cmd→rc文件不写→假超时(C8/C14)30s+杀进程+引擎重建
            # 修复: ①前置$global:LASTEXITCODE=0清残留(BUG#3) ②rc判定改errs分类:
            #   LASTEXITCODE非0→取其值(native真失败); errs含非NativeCommandError错误→1(cmdlet真错);
            #   NativeCommandError(native stderr)不计错(BUG#1/2) ③try/catch移入& {}块内兜底
            #   终止性错误, catch记录文本到errs+rc=1, 块内catch后管道不中断→throw前的stdout完整
            #   落盘不丢失(BUG#4, 实测Write-Output before; throw→out保留before)
            # ① LLM原始命令(含可能语法错误) → 独立 cmd.ps1 (UTF-8-BOM, 与ps_cmd同)
            #    解析期错误(ParserError)发生时, 错误属于cmd.ps1 → dot-source运行时抛出 → 外层catch可捕获
            with open(paths.cmd, "w", encoding="utf-8-sig") as _cmd:
                _cmd.write(command)
            # ② 执行框架 ps_cmd: dot-source cmd.ps1 + try/catch在dot-source外层(B6.3)
            ps_cmd = (
                f'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; $OutputEncoding=[System.Text.Encoding]::UTF8; '
                f'$global:rc=0; $errs = New-Object System.Collections.ArrayList; $global:LASTEXITCODE = 0; '
                f'& {{ try {{ . "{paths.cmd}" }} catch {{ $global:rc = 1; [void]$errs.Add($_) }} }} 2>&1 | '
                f'ForEach-Object {{ if ($_ -is [System.Management.Automation.ErrorRecord]) {{ [void]$errs.Add($_) }} else {{ $_ }} }} | '
                f'Out-String -Width 4096 | Out-File -FilePath "{paths.out}" -Encoding utf8 -Width 4096; '
                f'if ($global:LASTEXITCODE -ne 0) {{ $global:rc = $global:LASTEXITCODE }} '
                f'else {{ foreach ($ee in $errs) {{ if ($ee.FullyQualifiedErrorId -notlike "NativeCommandError") '
                f'{{ $global:rc = 1; break }} }} }}; '
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
                # 2026-11-04 小欧 - 根治: 原此处每条命令 new 一个临时写线程并 join(Thread.start 是事故卡死点)。
                #   改由实例级常驻 _StdinWriter 投递(队列+Event有界等待): 命令路径零线程创建。
                #   超时=写线程卡住(管道背压/半死) → M6守卫清理+重启, 不再无限阻塞。
                _w = self._stdin_writer
                if _w is None:
                    logger.warning("[卡死C5] stdin写通道缺失(实例未就绪) → 返回_EXIT_PROCESS_DIED, 走重启分支")
                    return {"stdout": "", "stderr": "", "exit_code": _EXIT_PROCESS_DIED}
                _wr_err = _w.write(feed.encode(locale.getpreferredencoding(), errors="replace"), _STDIN_WRITE_TIMEOUT)
                if isinstance(_wr_err, TimeoutError):
                    logger.warning(f"[卡死C5b] stdin写入{_STDIN_WRITE_TIMEOUT}s未返回(写线程卡住/管道背压) → M6守卫清理+重启 (pid={self._proc.pid if self._proc else None})")
                    self._cleanup_guard_start()
                    return {"stdout": "", "stderr": "", "exit_code": _EXIT_PROCESS_DIED}
                if _wr_err is not None:
                    raise _wr_err
            except (BrokenPipeError, OSError, ValueError):
                logger.warning("[卡死C5] 向死进程写stdin触发管道异常(BrokenPipe/OSError/ValueError) → 返回_EXIT_PROCESS_DIED, 走重启分支")
                return {"stdout": "", "stderr": "", "exit_code": _EXIT_PROCESS_DIED}

            # [卡死场景C8/C14] 有界兜底: 命令超时(含半死/死循环/锁被hold) → 守卫清理, 返回timeout(非永久阻塞) — 小欧 2026-08-06
            # [M6 重写 小欧 2026-09-19] 同线程 try/finally 无法拦截 OS 级挂起 → 清理整体移入后台执行:
            #   主线程快照 _proc 并立即置 _proc=None/_alive=False(防假活回流到池, 配合 release 判活/满足 M8 契约)
            #   → 清理投常驻 worker(psutil 树杀+二次确认) → 主线程仅做有界等待(≤_CLEANUP_GUARD_TIMEOUT), 超时即放行.
            if not _poll_for_file(paths.code, timeout):
                logger.warning(f"[卡死C8/C14] 命令超时{timeout}s未出结果(半死/死循环/锁被hold) → 守卫清理, 返回timeout(非永久阻塞)")
                # [守卫拆分 小欧 2026-09-19] 原 _cleanup_guarded() 持锁 join(≤15s) → 阻塞其他调用方;
                # 现仅启动守卫(start, 微秒级), join/兜底由 _exec 在锁外调 _await_cleanup_guard 完成.
                # [命令级文件时序 小欧 2026-09-19] 进程未死时 _TempFiles.finally 的 _safe_unlink 必失败(句柄占用)
                # → 将本次 6 个命令级临时文件登记进 ctx, await(join 后进程必死) 再补清理
                self._cleanup_guard_start()            # 锁内微秒级: 快照+置None+投递常驻清理 worker+stderr回收
                if self._guard_ctx is not None:
                    self._guard_ctx["temp_files"] = [paths.out, paths.err, paths.code, paths.cwd, paths.ps1, paths.cmd]
                return dict(_ERROR_TIMEOUT)
            # [卡死场景C12] v2.11 小欧 2026-08-08: .code有内容≠PS命令执行完 — ps_cmd最后一行才写.cwd,
            #   此时立即读/unlink存在竞态: Out-File写.cwd中句柄未释放→unlink失败→文件残留(实测tmpXXX.cwd)。
            #   等.cwd非空=PS已执行完最后一条Out-File(句柄必已释放), 再读/清理才安全; 超时仅3s不拖慢成功路径
            _poll_for_file(paths.cwd, timeout=_CWD_WAIT_TIMEOUT)

            # .lstrip('\ufeff') 去掉PS5.1 Out-File -Encoding utf8写的BOM — 小欧 2026-07-07
            stdout = safe_read_file(paths.out).lstrip('\ufeff')
            stderr = safe_read_file(paths.err).lstrip('\ufeff')
            code_raw = safe_read_file(paths.code).strip().lstrip('\ufeff')
            cwd_raw = safe_read_file(paths.cwd).strip().lstrip('\ufeff')
            if cwd_raw:
                self._cwd = cwd_raw
            # [B6.3] ParserError快速失败留痕(北京老陈指示"纠偏容错必须可见"): 解析期语法错误经dot-source
            #   由外层catch捕获后rc=1+err落盘, 此处打warning标记"LLM命令语法错误快速失败", 供日志统计/
            #   回溯(对齐C8/C14超时可见性; 正常命令与运行期错误不触发此日志, 不污染常规路径) — 小欧 2026-08-08
            if "ParserError" in stderr:
                logger.warning(f"[卡死B6.3] ParserError快速失败(LLM命令解析期语法错误) cmd={command[:100]!r} err={stderr[:200]!r}")
            return {
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": int(code_raw) if code_raw else 0,
            }

    # ── 清理 ────────────────────────────────────

    def _cleanup_guard_start(self):
        """[守卫拆分 小欧 2026-09-19] 守卫启动段(锁内, 微秒级): 快照→置None/alive→投递常驻清理 worker→discard_stderr.
        不等待、不观测、立即返回 → 锁持有时长从 ≤15s 降至微秒级, 满足『超时即逝/锁立即释放』契约;
        观测与异常兜底全部移到 _await_cleanup_guard(锁外) 执行.
        [2026-11-04 小欧] 清理动作改投 _CLEANUP_POOL(导入期建好的常驻线程), 本段不再 Thread.start()。"""
        ctx = {}
        ctx["proc"] = self._proc                        # 快照后方可置 None
        ctx["pid"] = getattr(self._proc, 'pid', None)
        self._proc = None
        self._alive = False
        self._discard_stdin()                           # 投哨兵归还池 worker(不 join) — 2026-11-04 小欧

        def _job_fn():
            # 复用 M3 _kill_tree(传快照): 决不触碰 self._proc — 小欧 2026-09-19
            proc_to_kill = ctx["proc"]
            if proc_to_kill is None:
                return
            try:
                self._kill_tree(proc_to_kill)
            except Exception as e:
                # [异常兜底 小欧 2026-09-19] 清理异常必须留痕, 否则静默死亡被误判为"清理链完成"(假成功)
                logger.error(f"[BUG-2] 清理线程异常(pid={ctx['pid']}): {e} — 待主线程有界兜底")
                raise                   # 回填给 Job, 供 _await_cleanup_guard 走兜底分支

        ctx["start"] = time.monotonic()                 # [M6] perf 探针 t0
        # [常驻线程 2026-11-04 小欧] 原 threading.Thread(...).start() 在 Windows 上等 loader lock 且无超时,
        #   与 CreateProcessW 并发即永久互锁(8500 事故: 3 次超时烧掉 3 个 executor 槽) → 改投常驻 worker。
        ctx["job"] = _CLEANUP_POOL.submit(_job_fn)
        # [超时分支回收 小欧 2026-09-19] 超时后 stderr 句柄+临时文件回收(契约: 清理完全保留).
        # [时序修正 小欧 2026-09-19] 进程未死前 unlink 必失败(句柄仍被持有) → defer_unlink:
        # 仅关句柄+状态回收, unlink 延后到 await(join 后进程必死) 执行.
        ctx["stderr_path"] = self._stderr_path
        self._discard_stderr(None, defer_unlink=True)
        self._guard_ctx = ctx

    def _await_cleanup_guard(self):
        """[守卫拆分 小欧 2026-09-19] 守卫等待/观测/兜底段(锁外): 有界等待(≤守卫阈值) + 三分支判定 + 异常兜底.
        运行在锁外 → 长等待与兜底不再阻塞任何 acquire/exec 调用方, 锁立即释放契约成立.
        [2026-11-04 小欧] 等待对象由 Thread.join 改为常驻 worker 的 Future(同为有界), 语义三态不变。"""
        ctx = self._guard_ctx or {}
        self._guard_ctx = None
        job = ctx.get("job")
        if job is None:
            return
        pid = ctx.get("pid")
        # concurrent.futures.wait 而非 fut.result(timeout): 后者抛的 TimeoutError 与任务自身抛的
        # TimeoutError 同类型, 无法区分"等待超时"与"任务内超时" → 用 not_done 显式判定。
        _, not_done = concurrent.futures.wait([job], timeout=_CLEANUP_GUARD_TIMEOUT)
        err = None if not_done else job.exception()
        _elapsed = time.monotonic() - ctx.get("start", time.monotonic())
        # [时序修正 小欧 2026-09-19] join 后进程已死(或兜底已杀) → OS 释放文件句柄 → 延迟 unlink 成功率高
        sp = ctx.get("stderr_path")
        if sp:
            _safe_unlink(sp)
        # [命令级文件时序 小欧 2026-09-19] _TempFiles 在进程未死时 unlink 失败残留 → join 后补清理(幂等: 已删则跳过)
        for tf in ctx.get("temp_files", []):
            if os.path.exists(tf):
                _safe_unlink(tf)
        if not_done:
            logger.error(f"[卡死C8/C14] 清理链超守卫阈值{_CLEANUP_GUARD_TIMEOUT}s仍在清理(OS级挂起) → 已放行, 后台线程继续 (pid={pid})")
        elif err is not None:
            # [异常兜底 小欧 2026-09-19] daemon 线程异常死亡 → 不再假报"清理链完成";
            # 异常场景证明 _kill_tree 可返回(非 OS 挂死) → 主线程有界兜底重试一次(≤10s)
            # 2026-10-09 - 小欧 - 边界留痕(北京老陈裁定 BUFFER=15/守卫=10 后新增, 只标注不改逻辑):
            #   本分支理论最坏 = join(10) + 兜底 _kill_tree(≤10) = 20s > INSURANCE_BUFFER(15),
            #   即保险丝理论上可能早于本兜底返回而掐断(to_thread 线程不会被强杀, 只是结果被丢弃)。
            #   触发前提极苛刻: 守卫线程先耗满 10s 且恰好抛异常。实测清理链 349.7ms, 属理论边界非现实路径。
            #   不改动的理由: 兜底本身是"清理进程残留"的最后一道, 削它换保险丝对齐属本末倒置;
            #   且此路径下进程残留有 release/GC 兜底(:749 已留痕)。若日后见到相关误报再议。
            logger.error(f"[卡死C8/C14] 清理线程异常死亡(pid={pid}) → 主线程有界兜底清理一次 (err={err!r})")
            try:
                self._kill_tree(ctx["proc"])
                logger.warning(f"[卡死C8/C14] 兜底清理重试完成 → 进程树已清 (pid={pid})")
            except Exception as e:
                logger.error(f"[卡死C8/C14] 兜底重试仍失败(pid={pid}) → 进程残留不可静默 (err={e!r}) — 留痕待后续 release/GC 路径回收")
        else:
            logger.warning(f"[卡死C8/C14] 清理链完成, 耗时={_elapsed * 1000:.1f}ms (pid={pid})")

    def _kill_tree(self, proc: Optional["subprocess.Popen"] = None):
        """终止进程树并二次确认: 纯 psutil + proc.kill, 零子进程 — 2026-11-04 小欧

        CreateProcessW 持 loader lock 且不还 GIL, 与 Thread.start() 并发即永久互锁; 清理链只在
        "已出事"时走, 再建进程等于往火里浇油。杀=kill_process_tree(通用层), 验=_poll_pid_exit(本层)。
        【与旧实现的差异】旧 taskkill 失败有二级重试(外部进程特有失败模式); psutil 是直接 API,
        失败即 OS 级挂起, 重试无意义 → 仅留痕, 由守卫与 /health 指标暴露。
        """
        target = proc if proc is not None else self._proc
        kill_process_tree(target)
        if target is not None and not _poll_pid_exit(target, SUBPROCESS_TIMEOUT_SHORT):
            logger.warning(f"[卡死C11] kill 后 {SUBPROCESS_TIMEOUT_SHORT}s 进程仍在(OS级挂起) (pid={getattr(target, 'pid', None)})")

    def _discard_stderr(self, proc: Optional["subprocess.Popen"] = None, defer_unlink: bool = False):
        """[超时分支回收 小欧 2026-09-19] 回收 stderr 句柄与临时文件(单一路径, _close 与 M6 守卫超时分支共用).
        契约: 'stderr 句柄关闭、_stderr_handle、_stderr_path、临时文件清理 = 完全保留原逻辑, 只替换杀进程段'.
        M6 实施时 _cleanup_guarded 漏调 _close → stderr 临时文件/句柄永久残留(实测 Temp 积压 ps_*.err 58个).
        时序: 先关句柄再 unlink(_safe_unlink 兜底重试); 幂等; 不触碰 self._proc.
        [时序修正 小欧 2026-09-19] 守卫拆分后 start(锁内,微秒级) 先于 daemon 杀进程 → 此时 unlink 必失败
        (文件句柄仍被进程持有) → 增 defer_unlink=True: 仅关句柄+状态回收(_stderr_path置None), unlink 延后到
        _await_cleanup_guard(join后进程必死) 执行; 默认 False 保持 _close 即时清理语义. — 小欧 2026-09-19
        """
        # stderr 句柄: Popen 传文件对象时 Windows 下 proc.stderr 为 None, 此处防御性关闭(排除残留)
        if proc is not None and getattr(proc, 'stderr', None) is not None:
            try:
                proc.stderr.close()
            except Exception:
                pass
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
            if defer_unlink:
                # [时序修正 小欧 2026-09-19] 状态回收置None, unlink 交由 await(进程死后)延迟执行
                self._stderr_path = None
            else:
                # v2.11 小欧 2026-08-08: 静默pass→_safe_unlink统一重试+留痕(引擎级stderr文件同样存在句柄延迟释放竞态,
                # 升级为与命令级临时文件一致的健壮清理, 残留可见可溯源)
                _safe_unlink(self._stderr_path)
                self._stderr_path = None

    def _close(self):
        """内部关闭, 不持锁。调用方尽量持有 self._lock（close()超时5s未获取到锁也会force-kill）。— [卡死场景C9/C11/C12] 小欧 2026-08-06"""
        if self._proc:
            try:
                # [M5] 复用 _kill_tree(树杀+二次确认, DRY 不重造); 原 kill+wait 段已删除 — 小欧 2026-09-19
                self._kill_tree()
            except Exception as e:
                logger.warning(f"[卡死C11] 关闭进程失败(pid={self._proc.pid}): {e}")
            self._proc = None
            self._alive = False
        # 2026-11-04 小欧 - 写线程回收: 先投哨兵再清引用, 空闲线程立即退出(卡在write的随进程销毁自灭)
        self._discard_stdin()
        # [超时分支回收 小欧 2026-09-19] stderr 句柄+临时文件回收统一走 _discard_stderr(与守卫超时分支共用, DRY)
        self._discard_stderr(self._proc)

    def _discard_stdin(self):
        """回收 stdin 写通道: 投哨兵释放租约(幂等, 不 join) — 2026-11-04 小欧"""
        w = self._stdin_writer
        self._stdin_writer = None
        if w is not None:
            w.stop()


# ═══════════════════════════════════════════════════════
#  ShellPoolManager — 按 (task_id, shell_type) 分池
# ═══════════════════════════════════════════════════════

class ShellPoolBusyError(RuntimeError):
    """同 key 并发槽位耗尽：acquire 等待 ACQUIRE_WAIT_TIMEOUT 后明确失败。
    单一信号量硬限流(v2.8)：绝不临时创建绕过限流，绝不无限等待。调用方捕获转 build_error 返回。— 小欧 2026-08-06"""


_EMPTY_TASK_ID_WARNED = False


def _warn_empty_task_id() -> None:
    """空 task_id 只告警一次: 池键退化为 (None, shell_type), 全进程共用同一组槽位 — 2026-11-05 小欧"""
    global _EMPTY_TASK_ID_WARNED
    if _EMPTY_TASK_ID_WARNED:
        return
    _EMPTY_TASK_ID_WARNED = True
    logger.warning("[ShellPool] acquire 收到空 task_id: 池键退化为 (None, shell_type), "
                   "全进程 shell 共用同一组并发槽位(跨任务互相挤占)。"
                   "排查调用线程是否丢了 ContextVar(task_id): 走 WorkerPool 必须 copy_context")


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

    def has_session(self, task_id: str, shell_type: str) -> bool:
        """只读查询该key下是否存在池实例(存在⇒任务可能已有会话态); 不取槽/不探活/不改池状态 — 治理层2 小欧 2026-10-04"""
        with self._lock:
            return bool(self._pool.get(self._pool_key(task_id, shell_type)))

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
          Phase2(解锁): 复用→_probe()轻量探活; 新建→_start()启动
          Phase3: 探活/启动失败→剔除销毁→有界重试
        槽位生命周期: acquire 拿1槽; release/cleanup 各归还1次(_inst_map存在性判定防超归)
        锁序防死锁(C7): 先取池锁(Phase1) → 释放后再拿实例锁(Phase2), 从不嵌套持有两把锁
        """  # 小欧 2026-08-06 v2.8
        key = self._pool_key(task_id, shell_type)
        if not task_id:      # 2026-11-05 小欧 - 池键坍缩哨兵: 空 task_id 会让全进程共用一个池, 并发即超时
            _warn_empty_task_id()
        sem = self._sem[key]
        # [卡死场景C2] Phase0: 拿不到槽位 → 明确失败, 绝不temp绕过限流、绝不无限等待 — 小欧 2026-08-06
        # 有界等待: 同key并发排队最多 ACQUIRE_WAIT_TIMEOUT(2s), 超时抛ShellPoolBusyError → 调用方except转build_error(非卡死非500)
        if not sem.acquire(timeout=ACQUIRE_WAIT_TIMEOUT):
            logger.warning(f"[卡死C2] 池槽位耗尽, 同key并发排队超{ACQUIRE_WAIT_TIMEOUT}s → 明确失败(key={key}, 上限={self._max_per_type}), 拒temp绕过/无限等")
            raise ShellPoolBusyError(
                f"[ShellPool] 同任务并行 shell 超过上限({self._max_per_type} 个, key={key}): "
                f"等待{ACQUIRE_WAIT_TIMEOUT}s 未获槽位。这是宿主并发限流, 不是文件权限问题; "
                f"请减少同时发出的 shell 数量, 或改为串行重试"
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
                # ── Phase2(解锁): 新建→_start; 复用→_probe(轻量探活, 不执行命令/不建临时文件/不起线程) ──
                ok = inst._start(env) if fresh else inst._probe()   # v2.7 BugFix: env 透传, 防 API key 泄漏 — 小欧 2026-08-06
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
        # [卡死场景C6] 修复: close() 在锁外执行，不阻塞全池操作 — 小欧 2026-08-06
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


def get_pool_pids_snapshot() -> Optional[set]:
    """池 PID 快照（现取现用，调用方不得缓存跨命令复用）— 小欧 2026-10-16（[36]4.4 步骤3前置）"""
    try:
        return set(shell_pool.get_all_pids() or ())
    except Exception:
        return None  # 池未初始化退化为仅自身+父进程，不拖垮预检


# 2026-08-07 小欧 三堂会审定稿(R3): 3→8 — 当日日志实测同key并发达5(ps7池默认3放不下),
# acquire排队超2s→ShellPoolBusyError; 8覆盖实测并发5并留余量(每实例约40MB内存, 8≈320MB可接受)
# 2026-09-22 小欧 - v2.0：shell_pool 槽位改读 tuning 配置
shell_pool = ShellPoolManager(max_per_type=get_config().get("tuning.concurrency.shell_pool_max_per_type", 8))


atexit.register(shell_pool.cleanup_all)
