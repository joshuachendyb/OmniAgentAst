# -*- coding: utf-8 -*-
"""
真实环境E2E测试运行器 — 零Mock，全链路验证

测试流程：
Phase 0: 环境预检（Ollama + 后端存活）
Phase 1: LLM连通性测试（真实chat/stream/tool_call）
Phase 2: 单工具调用测试（每个工具类别选典型工具，真实Agent ReAct循环）
Phase 3: 已知Bug验证（空工具名死循环等）
Phase 4: 错误收集与分析

所有测试直接发HTTP请求到运行中的后端，LLM走真实Ollama。

小健 2026-05-24
"""
import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from e2e_real.error_collector import CompositeCollector, ErrorRecord
from e2e_real.bug_tracker import BugRegistry, BugVerifier, ReportGenerator, Severity

BASE_URL = "http://127.0.0.1:8000"
CHAT_URL = f"{BASE_URL}/api/v1/chat/stream/v2"
HEALTH_URL = f"{BASE_URL}/api/v1/health"
TIMEOUT_PER_TASK = 300
PHASE1_TIMEOUT = 180

PHASE1_TESTS = [
    {"id": "LLM-1", "desc": "Ollama服务连通性", "category": "connectivity"},
    {"id": "LLM-2", "desc": "模型可用性", "category": "connectivity"},
    {"id": "LLM-3", "desc": "简单对话", "category": "llm_chat", "msg": "你好，请用一句话回复"},
    {"id": "LLM-4", "desc": "流式对话", "category": "llm_stream", "msg": "数1到5，每个数字一行"},
]

PHASE2_TESTS = [
    {"id": "F-READ",   "msg": "读取 backend/pytest.ini 文件的内容",             "expect_tool": "read_file",       "category": "file"},
    {"id": "F-LIST",   "msg": "列出 backend/tests/ 目录的内容",                "expect_tool": "list_directory",   "category": "file"},
    {"id": "F-SEARCH", "msg": "在 backend/tests/ 目录搜索 test_ 开头的py文件",  "expect_tool": "search_files",     "category": "file"},
    {"id": "F-GREP",   "msg": "在 backend/pytest.ini 文件中搜索 pytest",        "expect_tool": "grep_file_content","category": "file"},
    {"id": "S-SHELL",  "msg": "执行PowerShell命令 Get-Date",                   "expect_tool": "execute_shell_command","category": "shell"},
    {"id": "S-FIND",   "msg": "查找系统中 python 命令的安装路径",              "expect_tool": "find_command",     "category": "shell"},
    {"id": "S-CODE",   "msg": "执行Python代码 print('E2E测试成功')",           "expect_tool": "execute_code",     "category": "shell"},
    {"id": "N-HTTP",   "msg": "使用 http_request 发GET请求到 https://httpbin.org/get","expect_tool":"http_request","category":"network"},
    {"id": "SY-INFO",  "msg": "获取当前系统的CPU内存磁盘信息",                 "expect_tool": "get_system_info",  "category": "system"},
    {"id": "SY-PROC",  "msg": "列出当前占用内存最多的5个进程",                 "expect_tool": "list_processes",   "category": "system"},
    {"id": "D-WIN",    "msg": "获取当前所有打开的窗口信息",                    "expect_tool": "window_info",      "category": "desktop"},
    {"id": "DOC-READ", "msg": "读取 backend/tests/reports/ 目录下的JSON报告文件","expect_tool":"read_document","category":"document"},
    {"id": "M-TIME",   "msg": "获取当前的系统时间",                            "expect_tool": "get_time",         "category": "meta"},
    {"id": "M-CAL",    "msg": "查询今天是不是工作日",                          "expect_tool": "query_calendar",   "category": "meta"},
    {"id": "M-HELP",   "msg": "查看 read_file 工具的详细用法说明",             "expect_tool": "tool_help",        "category": "meta"},
]

PHASE3_KNOWN_BUGS = [
    {"id": "BUG-EMPTY-TOOL", "desc": "空工具名死循环", "test_msg": "hello", "category": "known_bug"},
]


async def send_chat_stream(msg: str, timeout: int = TIMEOUT_PER_TASK) -> Tuple[List[Dict], int, float, Optional[str]]:
    """发送真实HTTP POST到后端，收集SSE事件"""
    import httpx
    start = time.time()
    events = []
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            async with c.stream("POST", CHAT_URL, json={
                "messages": [{"role": "user", "content": msg}],
                "stream": True,
            }) as resp:
                status_code = resp.status_code
                if status_code != 200:
                    body = await resp.aread()
                    return [], status_code, time.time() - start, body.decode("utf-8", errors="replace")[:300]

                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            events.append(ev)
                        except json.JSONDecodeError:
                            pass
                        if events and events[-1].get("type") in ("final", "error"):
                            break

        dur = time.time() - start
        return events, 200, dur, None
    except Exception as e:
        return events, 0, time.time() - start, f"{type(e).__name__}: {str(e)[:200]}"


def analyze_events(events: List[Dict], expect_tool: str = "") -> Dict[str, Any]:
    """深度分析SSE事件 — 远超"有事件就通过"的宽松断言"""
    analysis = {
        "event_count": len(events),
        "types": [e.get("type", "") for e in events],
        "has_start": False,
        "has_final": False,
        "has_error": False,
        "has_thought": False,
        "has_action_tool": False,
        "has_observation": False,
        "tools_called": [],
        "final_response": "",
        "error_message": "",
        "step_count": 0,
        "consecutive_chunks": 0,
        "issues": [],
    }

    for ev in events:
        t = ev.get("type", "")
        if t == "start":
            analysis["has_start"] = True
        elif t == "final":
            analysis["has_final"] = True
            analysis["final_response"] = ev.get("response", "")[:500]
        elif t == "error":
            analysis["has_error"] = True
            analysis["error_message"] = ev.get("message", "")
        elif t == "thought":
            analysis["has_thought"] = True
            analysis["step_count"] += 1
        elif t == "action_tool":
            analysis["has_action_tool"] = True
            tn = ev.get("tool_name", "")
            if tn:
                analysis["tools_called"].append(tn)
            else:
                analysis["issues"].append("空工具名（BUG: 空工具名死循环）")
            analysis["step_count"] += 1
        elif t == "observation":
            analysis["has_observation"] = True
            analysis["step_count"] += 1
        elif t == "chunk":
            analysis["consecutive_chunks"] += 1

    if not analysis["has_start"]:
        analysis["issues"].append("缺少start事件")

    if not analysis["has_final"] and not analysis["has_error"]:
        analysis["issues"].append("缺少final/error结束事件")

    if analysis["step_count"] == 0 and analysis["consecutive_chunks"] == 0:
        analysis["issues"].append("无任何思考/工具/观察步骤")

    if expect_tool and expect_tool not in analysis["tools_called"]:
        analysis["issues"].append(f"期望工具{expect_tool}未调用，实际调用: {analysis['tools_called']}")

    error_kw = ["429", "500", "错误", "失败", "exception", "rate_limit"]
    if any(kw in analysis["final_response"].lower() for kw in error_kw):
        analysis["issues"].append(f"final含错误关键词")

    return analysis


class E2ERealTestRunner:
    """真实环境E2E测试主运行器"""

    def __init__(self):
        self.registry = BugRegistry()
        self.verifier = BugVerifier(self.registry)
        self.collector = CompositeCollector()
        self.results: Dict[str, Any] = {}
        self._start_time = datetime.now()

    def _print_header(self, phase: str, desc: str):
        print(f"\n{'='*70}")
        print(f"  {phase}: {desc}")
        print(f"{'='*70}")

    async def run(self):
        """执行全部测试阶段"""
        print(f"\n{'#'*70}")
        print(f"#  OmniAgentAs-desk E2E真实环境测试")
        print(f"#  启动: {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"#  零Mock — 全部使用真实Ollama LLM + 真实HTTP请求")
        print(f"{'#'*70}")

        phase0_ok = await self._phase0_env_check()
        if not phase0_ok:
            print("\n[FATAL] 环境预检失败，终止测试")
            return

        await self._phase1_llm_connectivity()
        await self._phase2_tool_tests()
        await self._phase3_known_bug_verify()
        self._phase4_error_analysis()

        self._generate_report()

    async def _phase0_env_check(self) -> bool:
        """Phase 0: 环境预检"""
        self._print_header("Phase 0", "环境预检")
        all_ok = True

        import httpx
        try:
            r = await httpx.AsyncClient(timeout=5).get(HEALTH_URL)
            if r.status_code == 200:
                print(f"  [OK] 后端服务运行中")
            else:
                print(f"  [FAIL] 后端服务异常: HTTP {r.status_code}")
                all_ok = False
        except Exception as e:
            print(f"  [FAIL] 后端服务不可达: {e}")
            all_ok = False

        try:
            r = await httpx.AsyncClient(timeout=5).get("http://localhost:11434/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                if "qwen2.5:1.5b" in models:
                    print(f"  [OK] Ollama运行中, 模型: {models}")
                else:
                    print(f"  [FAIL] qwen2.5:1.5b不可用, 现有: {models}")
                    all_ok = False
            else:
                print(f"  [FAIL] Ollama异常: HTTP {r.status_code}")
                all_ok = False
        except Exception as e:
            print(f"  [FAIL] Ollama不可达: {e}")
            all_ok = False

        proc_errors = self.collector.process.collect()
        for e in proc_errors:
            print(f"  [WARN] {e.message}")

        return all_ok

    async def _phase1_llm_connectivity(self):
        """Phase 1: LLM连通性"""
        self._print_header("Phase 1", "LLM连通性测试")
        self.results["phase1"] = {}

        for test in PHASE1_TESTS:
            tid = test["id"]
            print(f"\n  [{tid}] {test['desc']}... ", end="", flush=True)

            if test["category"] == "connectivity":
                import httpx
                if tid == "LLM-1":
                    try:
                        r = await httpx.AsyncClient(timeout=10).get("http://localhost:11434/")
                        ok = r.status_code == 200 and "Ollama" in r.text
                        print("OK" if ok else "FAIL")
                        self.results["phase1"][tid] = {"status": "OK" if ok else "FAIL"}
                    except Exception as e:
                        print(f"FAIL: {e}")
                        self.results["phase1"][tid] = {"status": "FAIL", "error": str(e)}
                elif tid == "LLM-2":
                    try:
                        r = await httpx.AsyncClient(timeout=10).get("http://localhost:11434/api/tags")
                        models = [m["name"] for m in r.json().get("models", [])]
                        ok = "qwen2.5:1.5b" in models
                        print(f"OK models={models}" if ok else f"FAIL models={models}")
                        self.results["phase1"][tid] = {"status": "OK" if ok else "FAIL"}
                    except Exception as e:
                        print(f"FAIL: {e}")
                        self.results["phase1"][tid] = {"status": "FAIL", "error": str(e)}
                continue

            events, status, dur, err = await send_chat_stream(test["msg"], timeout=PHASE1_TIMEOUT)
            analysis = analyze_events(events)

            ok = analysis["has_start"] and (analysis["has_final"] or analysis["has_action_tool"])
            issues_str = "; ".join(analysis["issues"]) if analysis["issues"] else ""
            print(f"{'OK' if ok else 'FAIL'} {dur:.1f}s events={len(events)} {issues_str}")

            if not ok:
                bug = self.registry.add(
                    title=f"LLM测试失败: {test['desc']}",
                    severity=Severity.CRITICAL,
                    description=f"LLM基础能力异常: {issues_str}",
                    discovered_by="e2e_real",
                    evidence=[f"HTTP {status}, events={analysis['types']}"],
                )
                print(f"    -> {bug.bug_id}")

            self.results["phase1"][tid] = {
                "status": "OK" if ok else "FAIL",
                "dur": round(dur, 1),
                "events": len(events),
                "issues": analysis["issues"],
            }

    async def _phase2_tool_tests(self):
        """Phase 2: 单工具调用测试"""
        self._print_header("Phase 2", "工具调用测试（真实Agent ReAct循环）")
        self.results["phase2"] = {}
        total = len(PHASE2_TESTS)
        passed = 0

        for i, test in enumerate(PHASE2_TESTS, 1):
            tid = test["id"]
            print(f"\n  [{i}/{total}] [{tid}] {test['msg'][:55]}")
            print(f"    期望工具: {test['expect_tool']} | 发送中...", end="", flush=True)

            events, status, dur, err = await send_chat_stream(test["msg"])
            analysis = analyze_events(events, expect_tool=test["expect_tool"])

            ok = (
                analysis["has_start"]
                and (analysis["has_final"] or analysis["has_action_tool"])
                and len(analysis["issues"]) == 0
            )
            if ok:
                passed += 1

            issues_str = "; ".join(analysis["issues"][:3]) if analysis["issues"] else ""
            tools_str = ",".join(analysis["tools_called"][:3])
            print(f" {'OK' if ok else 'FAIL'} | {dur:.1f}s | tools=[{tools_str}] {issues_str}")

            if not ok:
                sev = Severity.HIGH if analysis["has_error"] else Severity.MEDIUM
                bug = self.registry.add(
                    title=f"工具测试失败: {test['expect_tool']}",
                    severity=sev,
                    description=f"Agent未能正确调用{test['expect_tool']}: {issues_str}",
                    discovered_by="e2e_real",
                    evidence=[f"实际调用: {analysis['tools_called']}", f"issues: {analysis['issues']}"],
                    location=test["category"],
                )
                print(f"    -> {bug.bug_id}")

            self.results["phase2"][tid] = {
                "status": "OK" if ok else "FAIL",
                "dur": round(dur, 1),
                "tools_called": analysis["tools_called"],
                "issues": analysis["issues"],
                "event_types": analysis["types"][:10],
            }

            await asyncio.sleep(1)

        self.results["phase2_summary"] = {"total": total, "passed": passed, "failed": total - passed}
        print(f"\n  Phase2结果: {passed}/{total} 通过")

    async def _phase3_known_bug_verify(self):
        """Phase 3: 已知Bug验证"""
        self._print_header("Phase 3", "已知Bug验证")
        self.results["phase3"] = {}

        for bug_test in PHASE3_KNOWN_BUGS:
            tid = bug_test["id"]
            print(f"\n  [{tid}] {bug_test['desc']}...")
            print(f"    发送: '{bug_test['test_msg']}'...", end="", flush=True)

            events, status, dur, err = await send_chat_stream(bug_test["test_msg"], timeout=120)
            analysis = analyze_events(events)

            empty_tool = "空工具名" in " ".join(analysis["issues"])
            no_final = not analysis["has_final"] and not analysis["has_error"]
            too_many_chunks = analysis["consecutive_chunks"] > 5
            too_many_steps = analysis["step_count"] > 10

            bug_still_exists = empty_tool or no_final or too_many_chunks or too_many_steps

            evidence_parts = []
            if empty_tool:
                evidence_parts.append("发现空工具名")
            if no_final:
                evidence_parts.append("无final结束事件")
            if too_many_chunks:
                evidence_parts.append(f"连续chunk={analysis['consecutive_chunks']}")
            if too_many_steps:
                evidence_parts.append(f"步骤数={analysis['step_count']}")

            evidence_str = "; ".join(evidence_parts) if evidence_parts else "Bug已修复或未触发"
            print(f" {'STILL_EXISTS' if bug_still_exists else 'FIXED/NOT_REPRODUCED'} | {dur:.1f}s | {evidence_str}")

            if bug_still_exists:
                bug = self.registry.add(
                    title=bug_test["desc"],
                    severity=Severity.CRITICAL,
                    description=f"已知Bug仍然存在: {evidence_str}",
                    discovered_by="e2e_real_phase3",
                    evidence=evidence_parts,
                    location="base_react.py",
                )
                self.registry.confirm(bug.bug_id, evidence=evidence_str)
                print(f"    -> {bug.bug_id} [CONFIRMED]")

            self.results["phase3"][tid] = {
                "still_exists": bug_still_exists,
                "evidence": evidence_str,
                "dur": round(dur, 1),
                "analysis": {
                    "empty_tool": empty_tool,
                    "no_final": no_final,
                    "too_many_chunks": too_many_chunks,
                    "too_many_steps": too_many_steps,
                    "tools_called": analysis["tools_called"],
                },
            }

    def _phase4_error_analysis(self):
        """Phase 4: 错误收集与分析"""
        self._print_header("Phase 4", "错误收集与分析")
        self.results["phase4"] = {}

        since = self._start_time
        all_errors = self.collector.collect_flat(sse_events=None, since=since)

        error_count = len(all_errors)
        by_source = {}
        for e in all_errors:
            by_source[e.source] = by_source.get(e.source, 0) + 1

        print(f"  自 {since.strftime('%H:%M:%S')} 以来收集到 {error_count} 条错误/警告")
        for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"    {src}: {cnt}条")

        if all_errors:
            print(f"\n  --- 最新10条 ---")
            for e in all_errors[:10]:
                print(f"    [{e.level}] {e.source}: {e.message[:80]}")

            critical_errors = [e for e in all_errors if e.level in ("ERROR", "CRITICAL")]
            if critical_errors:
                print(f"\n  发现 {len(critical_errors)} 条ERROR级别错误，注册为Bug")
                for ce in critical_errors[:5]:
                    self.registry.add(
                        title=f"运行时错误: {ce.message[:60]}",
                        severity=Severity.HIGH,
                        description=ce.message,
                        discovered_by="error_collector",
                        evidence=[f"source={ce.source}, level={ce.level}"],
                        location=ce.file_path,
                    )

        self.results["phase4"] = {
            "error_count": error_count,
            "by_source": by_source,
            "critical_count": len([e for e in all_errors if e.level in ("ERROR", "CRITICAL")]),
        }

    def _generate_report(self):
        """生成最终报告"""
        self._print_header("报告", "生成测试报告")

        reporter = ReportGenerator(self.registry)
        md_path = reporter.generate(test_results=self.results)

        summary = self.registry.summary()
        print(f"\n  Bug统计:")
        for sev, cnt in summary["by_severity"].items():
            if cnt > 0:
                print(f"    {sev}: {cnt}个")
        print(f"  确认: {summary['confirmed']} | 未修复: {summary['unfixed']} | 已修复: {summary['fixed']}")
        print(f"\n  报告路径: {md_path}")
        print(f"\n  结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


async def main():
    runner = E2ERealTestRunner()
    await runner.run()


if __name__ == "__main__":
    asyncio.run(main())
