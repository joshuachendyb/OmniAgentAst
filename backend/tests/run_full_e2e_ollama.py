#!/usr/bin/env python
"""
全链路E2E集成测试 v3 — 流式读取SSE，不等完整响应

小健 2026-05-23
"""
import asyncio, json, time, sys, os
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE}/api/v1/chat/stream/v2"
REPORT_DIR = Path(__file__).resolve().parent / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_TIMEOUT = 600  # 10分钟总超时

FILE_TASKS = [
    {"id":"F-01","msg":"在tests/temp_runtime_test创建test_e2e.txt写入hello e2e"},
    {"id":"F-02","msg":"读取tests/temp_runtime_test/test_e2e.txt的内容"},
    {"id":"F-03","msg":"在test_e2e.txt中搜索hello"},
    {"id":"F-04","msg":"把test_e2e.txt中的hello替换为你好"},
    {"id":"F-05","msg":"把test_e2e.txt重命名为test_renamed.txt"},
    {"id":"F-06","msg":"把test_renamed.txt复制为test_copy.txt"},
    {"id":"F-07","msg":"把test_copy.txt压缩成test_archive.zip"},
    {"id":"F-08","msg":"创建data.json文件内容为ver1"},
    {"id":"F-09","msg":"搜索tests/temp_runtime_test下所有txt文件"},
    {"id":"F-10","msg":"列出tests/temp_runtime_test目录结构"},
    {"id":"F-11","msg":"读取frontend/public/vite.svg图片信息"},
]
SHELL_TASKS = [
    {"id":"S-01","msg":"执行PowerShell的Get-Date命令"},
    {"id":"S-02","msg":"查找python命令的安装路径"},
    {"id":"S-03","msg":"创建后台shell会话执行echo hello"},
    {"id":"S-04","msg":"执行Python代码print测试成功"},
]
NET_TASKS = [
    {"id":"N-01","msg":"发送HTTP GET到httpbin.org/get"},
    {"id":"N-02","msg":"下载httpbin.org/json到本地"},
    {"id":"N-03","msg":"获取httpbin.org/html网页内容"},
    {"id":"N-04","msg":"搜索Python 3.13新特性"},
    {"id":"N-05","msg":"检查网络连通性ping 127.0.0.1"},
]
SYS_TASKS = [
    {"id":"SY-01","msg":"获取系统CPU内存磁盘信息"},
    {"id":"SY-02","msg":"查看系统网络连接状态"},
    {"id":"SY-03","msg":"查看最近Windows应用程序事件日志"},
    {"id":"SY-04","msg":"列出内存占用最多的5个进程"},
    {"id":"SY-05","msg":"查看PATH环境变量的值"},
    {"id":"SY-06","msg":"读取注册表ProductName值"},
]
DESK_TASKS = [
    {"id":"D-01","msg":"列出桌面所有打开的窗口"},
    {"id":"D-02","msg":"截取屏幕截图保存到文件"},
    {"id":"D-03","msg":"读取剪贴板内容"},
    {"id":"D-04","msg":"获取鼠标光标位置"},
    {"id":"D-05","msg":"确认键盘状态"},
    {"id":"D-06","msg":"发送系统通知E2E测试进行中"},
    {"id":"D-07","msg":"对截图进行OCR文字识别"},
    {"id":"D-08","msg":"获取活动窗口详细信息"},
]
DOC_TASKS = [
    {"id":"DOC-01","msg":"创建Excel文件含姓名和年龄"},
    {"id":"DOC-02","msg":"读取Excel文件内容"},
    {"id":"DOC-03","msg":"对Excel数据进行统计分析"},
    {"id":"DOC-04","msg":"筛选Excel中年龄大于25的数据"},
    {"id":"DOC-05","msg":"根据Excel数据生成柱状图"},
    {"id":"DOC-06","msg":"获取数据库的所有表名"},
    {"id":"DOC-07","msg":"查询数据库sessions表前5条"},
]
META_TASKS = [
    {"id":"M-01","msg":"查看read_file工具的用法"},
    {"id":"M-02","msg":"搜索文件操作相关工具"},
    {"id":"M-03","msg":"获取当前的系统时间"},
    {"id":"M-04","msg":"计算当前时间加5天后的日期"},
    {"id":"M-05","msg":"计算2026-01-01到今天的天数"},
    {"id":"M-06","msg":"查询今天是星期几是否工作日"},
    {"id":"M-07","msg":"将北京时间转为UTC时间"},
    {"id":"M-08","msg":"批量复制txt文件到子目录"},
]
CROSS_TASKS = [
    {"id":"C-01","msg":"获取时间后写入time_report.txt"},
    {"id":"C-02","msg":"搜索AI发展将结果保存到文件"},
    {"id":"C-03","msg":"获取系统信息保存到sys_report.txt"},
    {"id":"C-04","msg":"搜索时间工具后获取当前时间"},
    {"id":"C-05","msg":"查询数据库结构生成schema报告"},
    {"id":"C-06","msg":"列出目录搜索py文件读main.py"},
]
EDGE_TASKS = [
    {"id":"E-01","msg":"","desc":"空消息"},
    {"id":"E-02","msg":"读取不存在的文件路径C:/nope.txt"},
    {"id":"E-03","msg":"执行不存在的命令xyznotexist"},
    {"id":"E-04","msg":"访问不存在的网站notexist123.com"},
]
ALL_TASKS = FILE_TASKS + SHELL_TASKS + NET_TASKS + SYS_TASKS + DESK_TASKS + DOC_TASKS + META_TASKS + CROSS_TASKS + EDGE_TASKS

async def run_one(task):
    import httpx
    start = time.time()
    txt = task.get("desc", task["msg"])
    events = []
    try:
        async with httpx.AsyncClient(timeout=TOTAL_TIMEOUT) as c:
            async with c.stream("POST", CHAT_URL, json={
                "messages": [{"role":"user","content":txt}], "stream": True
            }) as resp:
                if resp.status_code != 200:
                    return task["id"], False, 0, [], f"HTTP {resp.status_code}", time.time()-start
                step_count = 0
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            events.append(ev)
                            t = ev.get("type","")
                            if t == "action_tool":
                                step_count += 1
                            if t in ("final","error") or step_count >= 10:
                                break
                        except: pass
        dur = time.time()-start
        steps = sum(1 for e in events if e.get("type")=="action_tool")
        tools = [e.get("tool_name","") for e in events if e.get("type")=="action_tool" and e.get("tool_name")]
        final = any(e.get("type")=="final" for e in events)
        err = next((e.get("message","") for e in events if e.get("type")=="error"), "")
        ok = final or (not err and steps>0) or (not err and len(events)>0)
        return task["id"], ok, steps, tools, err, dur
    except Exception as e:
        dur = time.time()-start
        return task["id"], False, 0, [], str(e)[:100], dur

async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n全链路E2E测试 v3 | Ollama qwen2.5:1.5b | {len(ALL_TASKS)} tasks | timeout {TOTAL_TIMEOUT}s")
    print(f"启动: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    import httpx
    try:
        r = await httpx.AsyncClient(timeout=5).get(f"{BASE}/api/v1/health")
        assert r.status_code==200
        print("[OK] 后端运行中\n")
    except:
        print("[FATAL] 后端未启动"); sys.exit(1)

    results, passed, failed, covered = [], 0, 0, set()
    total = len(ALL_TASKS)

    for i,task in enumerate(ALL_TASKS):
        tid = task["id"]
        desc = (task.get("desc") or task["msg"])[:55]
        print(f"[{i+1}/{total}] {tid}: {desc}  ... ", end="", flush=True)
        id_, ok, steps, tools, err, dur = await run_one(task)
        results.append((id_,ok,steps,tools,err,dur))
        if ok: passed+=1; [covered.add(t) for t in tools]
        else: failed+=1
        tag = "[OK]" if ok else "[FAIL]"
        ts_ = ",".join(tools[:4]) if tools else "-"
        e = f" | {err[:60]}" if err else ""
        print(f"{tag} steps={steps} tools=[{ts_}] {dur:.0f}s{e}")
        await asyncio.sleep(0.5)

    dur_t = sum(r[5] for r in results)
    print(f"\n=== SUMMARY ===")
    print(f"结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total: {total} | Pass: {passed} | Fail: {failed} | Rate: {passed/total*100:.1f}%")
    print(f"Tools covered: {len(covered)} | {sorted(covered)}")
    if failed:
        print(f"\n--- FAILURES ---")
        for r in results:
            if isinstance(r, tuple) and not r[1]:
                print(f"  [{r[0]}] steps={r[2]} err={r[4][:80]}")

    rp = REPORT_DIR/f"e2e_v3_{ts}.json"
    with open(rp,"w",encoding="utf-8") as f:
        json.dump({
            "end": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "total":total,"passed":passed,"failed":failed,
            "rate":f"{passed/total*100:.1f}%",
            "tools_covered":len(covered),"tools":sorted(covered),
            "results":[{
                "id":r[0],"ok":r[1],"steps":r[2],"tools":r[3],"err":r[4],"dur":round(r[5],1)
            } for r in results],
        },f,ensure_ascii=False,indent=2)
    print(f"\nReport: {rp}")

if __name__=="__main__":
    import sys
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[INTERRUPTED]")
        sys.exit(2)
