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
#        缺陷1: `;`复合命令前段出错, $?只反映最后一条→rc漏报0(错误进err但业务层判success) — test_error_after_success_pipeline
#        缺陷2: PS5 native写stderr使$?变False→成功命令误报rc=1(PS7/PS5行为不一致) — test_ps5_native_stderr
#        缺陷3: $LASTEXITCODE跨命令残留污染(先native exit3再跑cmdlet→rc误报3) — 探测复现
#        缺陷4: throw终止性错误中断ps_cmd→rc文件不写→假超时30s+杀进程+引擎重建 — 探测复现
#        B6.1修复: ①前置$global:LASTEXITCODE=0清残留(治缺陷3) ②rc判定改errs分类: LASTEXITCODE非0→取其值
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
#   合规: KISS-DIRECT(有界轮询替代原原语等待)+DRY(_close至_kill_tree单路径)+禁止backward(直接强化清理链)。
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
# 2026-11-05 小欧 - 池键坍缩哨兵: acquire 收到空 task_id 时告警一次(原静默把全进程 shell 挤进同一个
#         (None, shell_type) 池), 并把 ShellPoolBusyError 文案写明"宿主并发限流", 防模型误判成文件权限问题。
# 2026-11-06 小欧 - 结构性修正: ①匿名(空task_id)请求不再进池(无任务生命周期即无会话语义, 由调用方走一次性子进程),
#         哨兵改计数告警(原置位后永久静默, 复发零线索); ②新增 max_total 跨 key 全局实例闸门, 新建前超量则
#         LRU 淘汰最久空闲实例(原上限=max_per_type×key数, 隔离修好后内存失去总量控制), 全忙不可淘汰则明确失败;
#         ③acquire 新增 wait_timeout 接入外层剩余预算(原硬编码 2s 不知外层 deadline, 排队可撑破保险丝)。
#         附带挖出并修复 v2.7 既有 bug: 锁外 close 循环变量同名 inst 覆盖当前实例, 淘汰发生后返回的是死实例、
#         新实例滞留池中永久 busy(槽位泄漏), 改名 dead; 该缺陷在原 idle 淘汰路径同样存在, LRU 使其必现而暴露。
# 2026-11-06 小欧 - 去池化(用户拍板): LLM 工具契约从不承诺跨命令状态保持(cwd 参数+;串联已覆盖换目录),
#         并发与共享可变状态天然冲突, 交互式场景池也接不住(exec 靠完成信号临时文件无 stdin 交互)。
#         故删除 PersistentShell/ShellPoolManager/shell_pool/_StdinWriter/_STDIN_POOL/ThreadLeasePool 依赖/
#         atexit/按 key 分池/_inst_map/LRU/idle 回收/探活/cleanup_by_task 全套池机制(约 800 行)。
#         execute_shell_command 改为每条命令独立子进程跑完即销毁 + 全局一个 BoundedSemaphore 管内存(见该文件)。
#         本文件瘦身为支撑模块, 仅保留: prewarm_shell_binaries(启动预热)、_replace_python3_safe(命令规范化)、
#         get_pool_pids_snapshot(返回空集, 保留安全链签名; 去池后无被托管的常驻进程)。
# 2026-11-06 小欧 - 三堂会审(YAGNI): 删去池化后零调用的死函数 safe_read_file/_TempFiles/_poll_for_file/
#         _poll_pid_exit/_safe_unlink 及常量 _UNLINK_RETRY/_UNLINK_RETRY_DELAY, 连带删 import contextlib/tempfile/os/subprocess
"""shell_engine — shell 支撑函数(去池化后) — 小欧 2026-11-06

【为什么不再有持久池】LLM 工具契约不承诺跨命令状态(cwd 参数 + `;`/`&&` 串联已覆盖换目录),
并发与共享可变状态天然冲突, 交互式场景 exec 模型也接不住。每条命令独立子进程跑完即销毁 +
全局一个 BoundedSemaphore 管内存, 卡死只毁自己这次调用, 不传染。详见 execute_shell_command.py。

【本文件职责】仅留被外部复用的 shell 支撑函数, 不再持有进程池/引擎/线程原语。
"""

import shutil
import time
from typing import Optional

from app.logger import logger
from app.utils.proc_io import run as proc_run  # 零线程读管道(取代 subprocess.run 的 _readerthread)

# ═══════════════════════════════════════════════════════
#  常量(仅保留支撑函数所需)
# ═══════════════════════════════════════════════════════

_READY_PROBE_TIMEOUT = 10        # 就绪握手超时(秒): prewarm 用, 首次启动慢放宽到10s 防误杀 — 小欧 2026-08-06



# ═══════════════════════════════════════════════════════
#  prewarm_shell_binaries — 启动期预热
# ═══════════════════════════════════════════════════════

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
#  get_pool_pids_snapshot — 安全链 PID 快照(去池化后返回空集)
# ═══════════════════════════════════════════════════════

def get_pool_pids_snapshot() -> Optional[set]:
    """返回受托管的常驻 shell 进程 PID 集合, 供安全检查拦截 Stop-Process/taskkill 保护自身进程。

    去池化后无被托管的常驻进程, 返回空集; 安全链仍保护当前进程+父进程(shell_process_guard
    对空集=常态不告警, 对 None=上游未递入才告警)。保留函数签名避免动 safety_gate/tool_facade 调用点。 — 2026-11-06 小欧
    """
    return set()
