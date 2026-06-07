# -*- coding: utf-8 -*-
"""
重构清理验证测试 — 小沈 2026-05-21

覆盖 19.6 检查点 1/4/9：
  检查点1：旧代码彻底删除（防两套并存）
  检查点4：conversation_history 引用零遗漏
  检查点9：prompt_logger 调用点未被破坏

测试策略：
  - 基于 ast 静态分析，不依赖运行时
  - 每次重构后运行，确保无残留
"""
import ast
import pathlib

# 项目根目录（test_refactor_cleanup.py 在 backend/tests/ 下）
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
BASE_REACT = PROJECT_ROOT / "app" / "services" / "agent" / "base_react.py"
AGENT_DIR = PROJECT_ROOT / "app" / "services" / "agent"


def _read_source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


# =============================================================================
# 检查点1：旧代码彻底删除
# =============================================================================

class TestNoLegacyMethods:
    """检查点1：确认 base_react.py 中无已迁入 MessageBuilder 的旧方法残留"""

    LEGACY_METHODS = [
        "_add_observation_to_history",
        "_get_observation_budget",
        "_smart_truncate",
        "_trim_history",
        "_format_llm_data",
    ]

    def _get_function_def_names(self, source: str) -> set:
        """只匹配函数定义（def xxx），不匹配注释/字符串中的引用"""
        tree = ast.parse(source)
        return {node.name for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef)}

    def _get_any_reference(self, source: str, name: str) -> bool:
        """检查是否有函数定义（非注释/字符串中的引用）"""
        return name in self._get_function_def_names(source)

    def test_no_legacy_methods_in_base_react(self):
        """检查点1：5个旧方法名不应作为函数定义出现在 base_react.py 中"""
        source = _read_source(BASE_REACT)
        found = [m for m in self.LEGACY_METHODS if self._get_any_reference(source, m)]
        assert not found, f"以下旧方法仍有函数定义残留: {found}"


# =============================================================================
# 检查点4：conversation_history 引用零遗漏
# =============================================================================

class TestConversationHistoryRefs:
    """检查点4：非 message_builder.py 文件中 self.conversation_history 应通过 @property 透传

    允许白名单：
      - message_builder.py（拥有者）
      - base_react.py（定义 @property）
      - file_react.py（继承 BaseAgent，通过 @property 透传）
      其他文件必须通过 message_builder.conversation_history 访问。
    """

    ALLOWED_FILES = {
        "message_builder.py",  # 拥有者，self.conversation_history 是直接属性
        "base_react.py",       # 定义了 @property conversation_history
        "file_react.py",       # 继承 BaseAgent，通过继承获得 @property
        "__init__.py",
    }

    def _find_bare_refs(self) -> list:
        """查找白名单外文件中 self.conversation_history 裸引用"""
        bad = []
        for f in AGENT_DIR.rglob("*.py"):
            if f.name in self.ALLOWED_FILES:
                continue
            source = f.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Attribute):
                    continue
                if node.attr != "conversation_history":
                    continue
                val = node.value
                if isinstance(val, ast.Attribute) and "message_builder" in ast.dump(val):
                    continue
                if isinstance(val, ast.Name) and val.id == "self":
                    bad.append((str(f), node.lineno))
        return bad

    def test_no_bare_conversation_history_refs(self):
        """检查点4：所有 self.conversation_history 应通过 @property 或 message_builder 代理"""
        bad_refs = self._find_bare_refs()
        assert not bad_refs, (
            f"以下文件有裸 self.conversation_history 引用（未走 @property 透传）:\n"
            + "\n".join(f"  {f}:{line}" for f, line in bad_refs)
        )


# =============================================================================
# 检查点9：prompt_logger 调用点未被破坏
# =============================================================================

class TestPromptLoggerCalls:
    """检查点9：确认 base_react.py 中 prompt_logger.log_observation() 调用仍完整"""

    def test_prompt_logger_calls_intact(self):
        """检查点9：log_observation() 至少应有两处调用（主工具+并行工具）"""
        source = _read_source(BASE_REACT)
        # 主工具用 prompt_logger.log_observation(，并行工具用 _p_logger.log_observation(
        count = source.count("log_observation(")
        assert count >= 2, (
            f"log_observation() 调用不足2处（当前{count}处），"
            "可能重构时被意外删除"
        )

    def test_prompt_logger_import_exists(self):
        """确保 prompt_logger 的 import 语句仍在"""
        source = _read_source(BASE_REACT)
        assert "from app.utils.prompt_logger import get_prompt_logger" in source, (
            "prompt_logger import 语句被删除"
        )

    def test_prompt_logger_call_has_observation_content(self):
        """每次 prompt_logger.log_observation() 调用都应包含 observation_content 参数"""
        source = _read_source(BASE_REACT)
        tree = ast.parse(source)

        class LogCallVisitor(ast.NodeVisitor):
            def __init__(self_visitor):
                self_visitor.calls = []

            def visit_Call(self_visitor, node):
                if (isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "prompt_logger"
                        and node.func.attr == "log_observation"):
                    keywords = {kw.arg for kw in node.keywords if kw.arg}
                    self_visitor.calls.append(keywords)
                self_visitor.generic_visit(node)

        visitor = LogCallVisitor()
        visitor.visit(tree)
        for keywords in visitor.calls:
            assert "observation_content" in keywords, (
                f"prompt_logger.log_observation() 缺少 observation_content 参数"
            )
