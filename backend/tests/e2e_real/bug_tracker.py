# -*- coding: utf-8 -*-
"""
问题记录与验证系统 — 自动记录发现的Bug，验证修复，生成报告

核心设计：
1. BugRecord: 单条Bug记录，含严重级别、验证状态、修复状态
2. BugRegistry: Bug注册表，支持添加/验证/修复标记/导出
3. BugVerifier: 自动验证器 — 对已知Bug执行验证逻辑
4. ReportGenerator: 生成Markdown+JSON双格式报告

小健 2026-05-24
"""
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    DESIGN = "design"


class VerifyStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FIXED = "fixed"
    WONTFIX = "wontfix"
    CANNOT_REPRODUCE = "cannot_reproduce"


@dataclass
class BugRecord:
    bug_id: str
    title: str
    severity: Severity
    description: str
    verify_status: VerifyStatus = VerifyStatus.PENDING
    fix_status: str = "open"
    discovered_at: str = ""
    discovered_by: str = ""
    evidence: List[str] = field(default_factory=list)
    location: str = ""
    root_cause: str = ""
    fix_description: str = ""
    fix_commit: str = ""
    verify_log: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bug_id": self.bug_id,
            "title": self.title,
            "severity": self.severity.value,
            "description": self.description,
            "verify_status": self.verify_status.value,
            "fix_status": self.fix_status,
            "discovered_at": self.discovered_at,
            "discovered_by": self.discovered_by,
            "evidence": self.evidence[:5],
            "location": self.location,
            "root_cause": self.root_cause,
            "fix_description": self.fix_description,
            "fix_commit": self.fix_commit,
        }


class BugRegistry:
    """Bug注册表"""

    def __init__(self):
        self._bugs: Dict[str, BugRecord] = {}
        self._counter = 0

    def add(
        self,
        title: str,
        severity: Severity,
        description: str,
        discovered_by: str = "",
        evidence: Optional[List[str]] = None,
        location: str = "",
    ) -> BugRecord:
        self._counter += 1
        bug_id = f"BUG-E2E-{self._counter:03d}"
        bug = BugRecord(
            bug_id=bug_id,
            title=title,
            severity=severity,
            description=description,
            discovered_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            discovered_by=discovered_by,
            evidence=evidence or [],
            location=location,
        )
        self._bugs[bug_id] = bug
        return bug

    def confirm(self, bug_id: str, evidence: Optional[str] = None) -> bool:
        bug = self._bugs.get(bug_id)
        if not bug:
            return False
        bug.verify_status = VerifyStatus.CONFIRMED
        if evidence:
            bug.evidence.append(evidence)
        return True

    def mark_fixed(self, bug_id: str, fix_description: str = "", fix_commit: str = "") -> bool:
        bug = self._bugs.get(bug_id)
        if not bug:
            return False
        bug.fix_status = "fixed"
        bug.verify_status = VerifyStatus.FIXED
        bug.fix_description = fix_description
        bug.fix_commit = fix_commit
        return True

    def mark_cannot_reproduce(self, bug_id: str, verify_log: str = "") -> bool:
        bug = self._bugs.get(bug_id)
        if not bug:
            return False
        bug.verify_status = VerifyStatus.CANNOT_REPRODUCE
        bug.verify_log = verify_log
        return True

    def get(self, bug_id: str) -> Optional[BugRecord]:
        return self._bugs.get(bug_id)

    def all_bugs(self) -> List[BugRecord]:
        return list(self._bugs.values())

    def by_severity(self, severity: Severity) -> List[BugRecord]:
        return [b for b in self._bugs.values() if b.severity == severity]

    def confirmed_bugs(self) -> List[BugRecord]:
        return [b for b in self._bugs.values() if b.verify_status == VerifyStatus.CONFIRMED]

    def unfixed_bugs(self) -> List[BugRecord]:
        return [b for b in self._bugs.values() if b.fix_status != "fixed" and b.verify_status != VerifyStatus.CANNOT_REPRODUCE]

    def summary(self) -> Dict[str, Any]:
        bugs = list(self._bugs.values())
        return {
            "total": len(bugs),
            "by_severity": {s.value: len(self.by_severity(s)) for s in Severity},
            "confirmed": len(self.confirmed_bugs()),
            "unfixed": len(self.unfixed_bugs()),
            "fixed": len([b for b in bugs if b.fix_status == "fixed"]),
        }


class BugVerifier:
    """Bug验证器 — 对每个Bug执行验证逻辑"""

    def __init__(self, registry: BugRegistry):
        self.registry = registry
        self._verifiers: Dict[str, Callable] = {}

    def register_verifier(self, bug_id: str, verifier: Callable[[], bool]):
        self._verifiers[bug_id] = verifier

    def verify(self, bug_id: str) -> bool:
        bug = self.registry.get(bug_id)
        if not bug:
            return False
        verifier = self._verifiers.get(bug_id)
        if not verifier:
            return False
        try:
            still_exists = verifier()
            if still_exists:
                self.registry.confirm(bug_id, evidence="验证确认：Bug仍然存在")
                return True
            else:
                self.registry.mark_cannot_reproduce(bug_id, verify_log="验证通过：Bug已不存在")
                return False
        except Exception as e:
            bug.verify_log = f"验证异常: {e}"
            return False

    def verify_all(self) -> Dict[str, bool]:
        results = {}
        for bug_id in list(self._verifiers.keys()):
            results[bug_id] = self.verify(bug_id)
        return results


class ReportGenerator:
    """报告生成器 — Markdown + JSON"""

    def __init__(self, registry: BugRegistry, output_dir: Optional[Path] = None):
        self.registry = registry
        self.output_dir = output_dir or Path(__file__).resolve().parent.parent / "reports"

    def generate(self, test_results: Optional[Dict[str, Any]] = None) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._generate_json(ts, test_results)
        md_path = self._generate_markdown(ts, test_results)
        return md_path

    def _generate_json(self, ts: str, test_results: Optional[Dict[str, Any]]):
        data = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": self.registry.summary(),
            "bugs": [b.to_dict() for b in self.registry.all_bugs()],
            "test_results": test_results,
        }
        path = self.output_dir / f"e2e_real_report_{ts}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _generate_markdown(self, ts: str, test_results: Optional[Dict[str, Any]]) -> Path:
        summary = self.registry.summary()
        lines = [
            f"# E2E真实环境测试报告",
            f"",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**测试环境**: Ollama qwen2.5:1.5b + FastAPI",
            f"**零Mock**: 全部使用真实LLM调用和真实HTTP请求",
            f"",
            f"## 摘要",
            f"",
            f"| 指标 | 值 |",
            f"|------|-----|",
        ]
        for k, v in summary.items():
            if isinstance(v, dict):
                v = ", ".join(f"{kk}={vv}" for kk, vv in v.items())
            lines.append(f"| {k} | {v} |")

        lines.extend(["", "## Bug清单", ""])

        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.DESIGN]:
            bugs = self.registry.by_severity(sev)
            if not bugs:
                continue
            lines.append(f"### {sev.value.upper()} ({len(bugs)}个)")
            lines.append("")
            for b in bugs:
                status_icon = {
                    VerifyStatus.CONFIRMED: "[CONFIRMED]",
                    VerifyStatus.FIXED: "[FIXED]",
                    VerifyStatus.CANNOT_REPRODUCE: "[CANT_REPRODUCE]",
                    VerifyStatus.WONTFIX: "[WONTFIX]",
                    VerifyStatus.PENDING: "[PENDING]",
                }.get(b.verify_status, "[?]")
                lines.append(f"#### {b.bug_id}: {b.title} {status_icon}")
                lines.append(f"- **描述**: {b.description}")
                lines.append(f"- **位置**: {b.location or '未知'}")
                if b.evidence:
                    lines.append(f"- **证据**: {b.evidence[0][:200]}")
                if b.root_cause:
                    lines.append(f"- **根因**: {b.root_cause}")
                if b.fix_description:
                    lines.append(f"- **修复**: {b.fix_description}")
                lines.append("")

        if test_results:
            lines.extend(["", "## 测试结果详情", ""])
            lines.append(f"```json")
            lines.append(json.dumps(test_results, ensure_ascii=False, indent=2)[:3000])
            lines.append(f"```")

        path = self.output_dir / f"e2e_real_report_{ts}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
