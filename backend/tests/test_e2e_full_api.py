#!/usr/bin/env python
"""
全链路E2E测试 — 真实路径：HTTP POST → 后端Chat → Agent → LLM → Tool
不走mock，不走直接函数调用

小健 2026-05-23
"""
import asyncio, json, sys, time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE}/api/v1/chat/stream/v2"
HEALTH_URL = f"{BASE}/api/v1/health"
TIMEOUT_PER_TASK = 600  # 每个任务最多等10分钟

# GUI类工具暂时不测（北京老陈指示）
# 文件操作等tool依赖task context，但有7个文件工具走Agent不会报无task_id

TASKS = [
    # ===== FILE (10个，排除有副作用的临时文件读写) =====
    {"id":"F1", "msg":"读取 tests/temp_runtime_test/test_direct.txt 文件的内容","expect":"read_file"},
    {"id":"F2", "msg":"在 tests/temp_runtime_test/ 目录搜索所有 .txt 文件","expect":"search_files"},
    {"id":"F3", "msg":"列出 tests/temp_runtime_test/ 目录的内容","expect":"list_directory"},
    {"id":"F4", "msg":"在 tests/temp_runtime_test/test_direct.txt 中搜索 hello","expect":"grep_file_content"},
    {"id":"F5", "msg":"在 tests/temp_runtime_test/ 目录下写一个 test_api.txt 内容为hello","expect":"write_text_file"},
    {"id":"F6", "msg":"把 test_api.txt 的内容从 hello 改成 world","expect":"edit_file"},
    {"id":"F7", "msg":"把 test_api.txt 复制为 test_api_copy.txt","expect":"file_operation"},
    {"id":"F8", "msg":"把 test_api_copy.txt 重命名为 test_api_final.txt","expect":"rename_file"},
    {"id":"F9", "msg":"读取 frontend/public/vite.svg 媒体文件信息","expect":"read_media_file"},
    {"id":"F10","msg":"把 tests/temp_runtime_test/ 的json文件读取为JSON格式","expect":"data_file_format"},

    # ===== SHELL (4个) =====
    {"id":"S1", "msg":"执行PowerShell命令 Get-Date 获取当前日期时间","expect":"execute_shell_command"},
    {"id":"S2", "msg":"查找系统中 python 命令的安装路径","expect":"find_command"},
    {"id":"S3", "msg":"执行Python代码 print(\"E2E测试成功\")","expect":"execute_code"},
    {"id":"S4", "msg":"创建一个后台shell会话 echo hello world","expect":"shell_session"},

    # ===== NETWORK (5个) =====
    {"id":"N1", "msg":"使用 http_request 工具发送GET请求到 https://httpbin.org/get","expect":"http_request"},
    {"id":"N2", "msg":"获取 https://httpbin.org/html 网页内容","expect":"fetch_webpage"},
    {"id":"N3", "msg":"从 https://httpbin.org/json 下载JSON文件到本地","expect":"download_file"},
    {"id":"N4", "msg":"搜索 Python 3.13 新特性的相关信息","expect":"search_web"},
    {"id":"N5", "msg":"检查 127.0.0.1 的网络连通性 ping","expect":"network_diagnose"},

    # ===== SYSTEM (9个) =====
    {"id":"SY1","msg":"获取当前系统的CPU内存磁盘信息","expect":"get_system_info"},
    {"id":"SY2","msg":"查看系统当前的网络连接状态","expect":"net_connections"},
    {"id":"SY3","msg":"查看 Windows 应用程序事件日志最近5条","expect":"event_log"},
    {"id":"SY4","msg":"列出当前占用内存最多的5个进程","expect":"list_processes"},
    {"id":"SY5","msg":"读取系统 PATH 环境变量的值","expect":"get_env"},
    {"id":"SY6","msg":"设置一个临时的环境变量 TEST_API=hello","expect":"set_env"},
    {"id":"SY7","msg":"读取注册表 Windows 版本信息 ProductName","expect":"registry_control"},
    {"id":"SY8","msg":"列出当前所有运行中的服务","expect":"service_control"},
    {"id":"SY9","msg":"列出系统中所有计划任务","expect":"task_control"},

    # ===== DESKTOP (只测无副作用的6个，GUI类暂不测) =====
    {"id":"D1", "msg":"获取当前所有打开的窗口信息","expect":"window_info"},
    {"id":"D2", "msg":"读取当前剪贴板的内容","expect":"clipboard_control"},
    {"id":"D3", "msg":"获取鼠标当前的位置","expect":"mouse_control"},
    {"id":"D4", "msg":"获取当前活动窗口的详细信息","expect":"window_control"},
    {"id":"D5", "msg":"查看键盘当前的状态","expect":"keyboard_control"},
    {"id":"D6", "msg":"对 tests/temp_runtime_test/screenshot.png 进行OCR文字识别","expect":"ocr"},

    # ===== DOCUMENT (8个) =====
    {"id":"DOC1","msg":"读取 tests/temp_runtime_test/e2e_data.json 文件","expect":"read_document"},
    {"id":"DOC2","msg":"创建一个Word文档 tests/temp_runtime_test/test_e2e.docx 内容为E2E测试","expect":"write_document"},
    {"id":"DOC3","msg":"分析数据 [名称Alice年龄30, 名称Bob年龄25] 的统计信息","expect":"analyze_data"},
    {"id":"DOC4","msg":"从数据中筛选出名称等于Alice的记录","expect":"filter_data"},
    {"id":"DOC5","msg":"根据数据 [类别A值10, 类别B值20] 生成柱状图","expect":"generate_chart"},
    {"id":"DOC6","msg":"获取数据库中大语言模型对话sessions表的表结构","expect":"get_db_schema"},
    {"id":"DOC7","msg":"查询数据库中有哪些表","expect":"query_sql"},
    {"id":"DOC8","msg":"执行SQL查询 SELECT 1 验证数据库连接","expect":"execute_sql"},

    # ===== META (9个) =====
    {"id":"M1", "msg":"查看 read_file 工具的详细用法说明","expect":"tool_help"},
    {"id":"M2", "msg":"搜索与文件操作相关的工具列表","expect":"tool_search"},
    {"id":"M3", "msg":"获取当前的系统时间","expect":"get_time"},
    {"id":"M4", "msg":"计算 2026-05-23 12:00:00 加5天后的日期","expect":"time_add"},
    {"id":"M5", "msg":"计算 2026-01-01 到 2026-05-23 之间相差多少天","expect":"time_diff"},
    {"id":"M6", "msg":"查询 2026-05-23 是不是工作日","expect":"query_calendar"},
    {"id":"M7", "msg":"把北京时间 2026-05-23 12:00:00 转换成UTC时间","expect":"timezone_convert"},
    {"id":"M8", "msg":"列出所有正在运行的定时器","expect":"timer"},
    {"id":"M9", "msg":"执行多步pipeline: 先获取时间再获取系统信息","expect":"pipeline"},
]

async def run_task(task):
    import httpx
    start = time.time()
    events = []
    tools = []
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_PER_TASK) as c:
            async with c.stream("POST", CHAT_URL, json={
                "messages": [{"role":"user","content":task["msg"]}], "stream": True
            }) as resp:
                if resp.status_code != 200:
                    return task["id"], "FAIL", [], [], f"HTTP {resp.status_code}", 0
                step_count = 0
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            events.append(ev)
                            t = ev.get("type","")
                            if t == "action_tool":
                                tn = ev.get("tool_name","")
                                step = ev.get("step", "")
                                if tn: tools.append({"tool": tn, "step": step})
                                step_count += 1
                            if t in ("final","error") or step_count >= 20:
                                break
                        except: pass
        dur = time.time()-start
        final = any(e.get("type")=="final" for e in events)
        error = next((e.get("message","") for e in events if e.get("type")=="error"), None)
        tool_names = [t["tool"] for t in tools]
        ok = final and not error
        status = "OK" if ok else "FAIL"
        return task["id"], status, tool_names, events[:3], error or "", round(dur, 1)
    except Exception as e:
        return task["id"], "FAIL", [], [], f"{type(e).__name__}: {str(e)[:120]}", round(time.time()-start, 1)

async def main():
    import httpx
    # 检查后端
    try:
        r = await httpx.AsyncClient(timeout=5).get(HEALTH_URL)
        assert r.status_code==200
        print(f"[OK] 后端运行中 | {len(TASKS)} tasks | 超时 {TIMEOUT_PER_TASK}s/任务")
    except:
        print("[FATAL] 后端未启动，请先启动 uvicorn"); return

    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    results = []
    total = len(TASKS)
    for i, task in enumerate(TASKS, 1):
        print(f"\n[{i}/{total}] {task['id']}: {task['msg'][:60]}")
        print(f"  期望工具: {task['expect']}")
        print(f"  发送中... ", end="", flush=True)
        tid, status, tools, events, err, dur = await run_task(task)
        results.append((tid, status, tools, err, dur, task))
        tool_str = ", ".join(tools[:5]) if tools else "(无)"
        print(f"{status} | {dur}s | tools: [{tool_str}]")
        if err:
            print(f"  错误: {err[:120]}")
        await asyncio.sleep(1)  # 请求间休息1秒

    # 汇总
    passed = sum(1 for r in results if r[1]=="OK")
    failed = total - passed
    print(f"\n{'='*70}")
    print(f"结果汇总")
    print(f"{'='*70}")
    print(f"总任务: {total} | 通过: {passed} | 失败: {failed} | 通过率: {passed/total*100:.1f}%")
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if failed:
        print(f"\n--- 失败清单 ---")
        for r in results:
            if r[1]!="OK":
                print(f"  [{r[0]}] {r[5]['expect']:25s} dur={r[4]}s tools={r[2]}")
                if r[3]: print(f"    err: {r[3][:120]}")

    # 写入报告
    report = {
        "end": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total, "passed": passed, "failed": failed,
        "rate": f"{passed/total*100:.1f}%",
        "timeout_per_task": TIMEOUT_PER_TASK,
        "results": [{
            "id": r[0], "status": r[1], "tools_called": r[2],
            "expect_tool": r[5]["expect"], "error": r[3][:200], "dur": r[4]
        } for r in results],
    }
    rp = Path(__file__).resolve().parent / "reports" / f"e2e_api_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    rp.parent.mkdir(parents=True, exist_ok=True)
    with open(rp, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n报告: {rp}")

if __name__ == "__main__":
    asyncio.run(main())
