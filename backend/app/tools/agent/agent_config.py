# -*- coding: utf-8 -*-
"""agent_config — Agent 配置数据类 + AgentRegistry

小欧 2026-11-27 初版：字段、构造即校验、拒绝清单、注册表与内置 3 Agent
小欧 2026-11-28 按 TDD 落码：补四类字段类型显式校验（禁止 int()/float() 隐式强转、
tool_categories 只收 ToolCategory 集合、track_task 只收 bool），避免类型容错导致的静默失效；
同轮修正 agent_id 为全串匹配，拒绝结尾换行
小欧 2026-11-28 修正 manifest 外部输入容错：分类形状非法回落默认集合，描述非字符串直接拒绝，
提示词非字符串回落空串，消除 str() 把 null/数字变成假描述与假提示词
小欧 2026-11-28 新增 build_delegate_tool_description()：工具描述由注册表动态生成，新增 Agent 零改代码
"""
import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from app.logger import logger
from app.tools.tool_constants import DELETE_PATH_TOOLS, DUAL_PATH_TOOLS, WRITE_PATH_TOOLS
from app.tools.tool_types import ToolCategory

# 子 Agent 禁止持有的工具分类:
#   AGENT       — 用户交互（question/schedule），子 Agent 没有前端出口，也不得自行提问
#   SYSTEM      — create_task/delete_task 会动任务台账，子 Agent 能删掉父任务行
#   MEDIA       — 生成即落盘并计费，属"写"+花钱，不该出现在只读子 Agent 里
#   WIN_REGISTRY/DESKTOP/TIMER — 宿主副作用，与"干净上下文只做分析"无关
DELEGATE_DENY_CATEGORIES: Set[ToolCategory] = {
    ToolCategory.AGENT, ToolCategory.SYSTEM, ToolCategory.MEDIA,
    ToolCategory.WIN_REGISTRY, ToolCategory.DESKTOP, ToolCategory.TIMER,
}

# 子 Agent 禁止持有的工具名: 直接复用算子层既有写/删/双路径分类表(DRY), 再补 bash 与显式交互工具。
# 新增写类工具只要进 PATH_* 表, 这里自动生效, 不需要改本文件。
DELEGATE_DENY_TOOLS: Set[str] = (
    set(WRITE_PATH_TOOLS) | set(DELETE_PATH_TOOLS) | set(DUAL_PATH_TOOLS)
    | {"bash", "question", "schedule", "delegateagent"}
)

# 全串匹配：不带首尾锚点，交给 fullmatch 判定；$ 会放过结尾换行，故不用
_ID_RE = re.compile(r"[a-z][a-z0-9_]{0,31}")


@dataclass
class AgentConfig:
    """子 Agent 配置 — 定义一个可委托的 Agent 实例的全部参数"""
    agent_id: str                          # 唯一标识，如 "researcher" / "reviewer" / "kb_analyst"
    description: str                       # 一句话说明（给 LLM 看，帮助主 Agent 选择委托目标）
    system_prompt: str = ""                # 子 Agent 的 system prompt
    tool_categories: Set[ToolCategory] = field(default_factory=lambda: {ToolCategory.FUNDAMENTAL})
    output_instruction: Optional[str] = None  # 输出约束（自由文本；None=默认摘要要求）
    model: Optional[str] = None            # 指定模型（None=继承父 Agent 的 LLM）
    max_steps: int = 8                     # 子 Agent 最大 ReAct 步数（有界）
    timeout_s: float = 300.0               # 墙钟超时（秒），由守卫协程强制执行
    track_task: bool = False               # 是否在 tasks 台账建行（子过程默认不建）

    def __post_init__(self) -> None:
        """构造即校验 — 非法配置在注册/委托之前失败，不留到运行期"""
        if not isinstance(self.agent_id, str) or not _ID_RE.fullmatch(self.agent_id):
            raise ValueError(f"agent_id 非法: {self.agent_id!r}（要求小写字母开头，[a-z0-9_]）")
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(f"agent_id={self.agent_id}: description 不能为空（LLM 靠它路由）")
        # 类型显式：bool 是 int 子类，必须单独排除；禁止 int()/float() 隐式强转（隐式强转会让非法类型静默通过）
        if not isinstance(self.max_steps, int) or isinstance(self.max_steps, bool):
            raise TypeError(f"agent_id={self.agent_id}: max_steps 必须为 int，收到 {type(self.max_steps).__name__}")
        if not 1 <= self.max_steps <= 30:
            raise ValueError(f"agent_id={self.agent_id}: max_steps={self.max_steps} 越界（1..30）")
        if not isinstance(self.timeout_s, (int, float)) or isinstance(self.timeout_s, bool):
            raise TypeError(f"agent_id={self.agent_id}: timeout_s 必须为数值，收到 {type(self.timeout_s).__name__}")
        if not 5 <= self.timeout_s <= 1800:
            raise ValueError(f"agent_id={self.agent_id}: timeout_s={self.timeout_s} 越界（5..1800）")
        if not isinstance(self.tool_categories, (set, frozenset)):
            raise TypeError(f"agent_id={self.agent_id}: tool_categories 必须为集合，收到 {type(self.tool_categories).__name__}")
        if not all(isinstance(c, ToolCategory) for c in self.tool_categories):
            raise TypeError(f"agent_id={self.agent_id}: tool_categories 成员必须为 ToolCategory")
        if not self.tool_categories:
            raise ValueError(f"agent_id={self.agent_id}: tool_categories 不能为空")
        self.tool_categories = set(self.tool_categories)   # 拷贝成独立集合，防调用方共享可变对象
        if not isinstance(self.track_task, bool):
            raise TypeError(f"agent_id={self.agent_id}: track_task 必须为 bool，收到 {type(self.track_task).__name__}")

    def effective_categories(self) -> Set[ToolCategory]:
        """实际生效的分类 — 拒绝分类在配置层先扣一遍（运行期还有工具元数据校验兜底）"""
        return set(self.tool_categories) - DELEGATE_DENY_CATEGORIES


class AgentRegistry:
    """AgentConfig 注册表 — 管理所有可委托的子 Agent 配置"""

    def __init__(self):
        self._configs: Dict[str, AgentConfig] = {}

    def register(self, config: AgentConfig, *, replace: bool = False) -> None:
        """注册一个 AgentConfig — 重名默认报错（插件覆盖同名 Agent 必须显式 replace=True）"""
        if config.agent_id in self._configs and not replace:
            raise ValueError(f"agent_id 已存在: {config.agent_id}（覆盖需 replace=True）")
        self._configs[config.agent_id] = config

    def unregister(self, agent_id: str) -> bool:
        """注销一个 Agent — 插件卸载/热重载用；不存在的 id 返回 False"""
        return self._configs.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> Optional[AgentConfig]:
        """按 agent_id 获取配置"""
        return self._configs.get(agent_id)

    def list_configs(self) -> List[AgentConfig]:
        """列出全部配置 — 供工具描述动态生成（新增 Agent 不需要改描述代码）"""
        return list(self._configs.values())

    def list_available(self) -> List[str]:
        """列出所有可用 agent_id（供 LLM 看）"""
        return list(self._configs.keys())

    def load_from_manifest(self, path: str) -> Optional[AgentConfig]:
        """从插件 manifest.json 加载 — 任何不合法都返回 None 并 warning，不抛"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"[AgentRegistry] 读取 manifest 失败({path}): {e}")
            return None

        try:
            if not isinstance(data, dict):
                raise ValueError("manifest 顶层必须是对象")
            raw_categories = data.get("tool_categories", ["fundamental"])
            if not isinstance(raw_categories, (list, tuple, set)):
                logger.warning(f"[AgentRegistry] 工具分类形状非法，回落 fundamental({path})")
                raw_categories = ["fundamental"]
            categories: Set[ToolCategory] = set()
            for name in raw_categories:
                try:
                    categories.add(ToolCategory(str(name)))
                except ValueError:
                    logger.warning(f"[AgentRegistry] 未知工具分类 {name!r}，跳过")
            description = data.get("description", "")
            if not isinstance(description, str):
                raise ValueError(f"description 须为字符串，收到 {type(description).__name__}")
            system_prompt = data.get("system_prompt", "")
            if not isinstance(system_prompt, str):
                logger.warning(f"[AgentRegistry] system_prompt 形状非法，回落空串({path})")
                system_prompt = ""
            config = AgentConfig(
                agent_id=str(data["name"]),
                description=description,
                system_prompt=system_prompt,
                tool_categories=categories or {ToolCategory.FUNDAMENTAL},
                output_instruction=data.get("output_instruction"),
                model=data.get("model"),
                max_steps=int(data.get("max_steps", 8)),
                timeout_s=float(data.get("timeout_s", 300)),
                track_task=False,   # 插件不得自开台账
            )
        except Exception as e:     # 缺 name / 类型错 / 校验不过 → 跳过该插件
            logger.warning(f"[AgentRegistry] manifest 不合法已跳过({path}): {e}")
            return None
        try:
            self.register(config)
        except ValueError as e:
            logger.warning(f"[AgentRegistry] 与已有 Agent 冲突已跳过({path}): {e}")
            return None
        return config


# 全局单例（测试用 reset_agent_registry 复位，避免用例之间串态）
_agent_registry: Optional[AgentRegistry] = None

def get_agent_registry() -> AgentRegistry:
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
        _register_builtin_agents(_agent_registry)
    return _agent_registry


def reset_agent_registry() -> None:
    """丢弃单例（连同已加载插件配置）— 仅供测试与插件热重载使用"""
    global _agent_registry
    _agent_registry = None


def _register_builtin_agents(registry: AgentRegistry) -> None:
    """内置 Agent 注册（3 个内置子 Agent）"""
    registry.register(AgentConfig(
        agent_id="researcher",
        description="独立搜索研究员：用网络搜索工具多路并行搜索，回传结构化摘要",
        tool_categories={ToolCategory.NETWORK, ToolCategory.FUNDAMENTAL},
        max_steps=10,
        timeout_s=240,
    ))
    registry.register(AgentConfig(
        agent_id="reviewer",
        description="独立审查员：用文件读取+搜索工具在干净上下文中审查代码/方案，回传结论",
        tool_categories={ToolCategory.FUNDAMENTAL, ToolCategory.FILE},
        output_instruction="按「结论 / 依据 / 风险 / 建议」四段输出，逐条列明出处（文件:行号）",
        max_steps=12,
        timeout_s=300,
    ))
    registry.register(AgentConfig(
        agent_id="kb_analyst",
        description="知识库分析师：检索知识库做多域对照分析，回传结论摘要",
        tool_categories={ToolCategory.FUNDAMENTAL, ToolCategory.FILE},
        max_steps=10,
        timeout_s=240,
    ))


def build_delegate_tool_description() -> str:
    """生成委托工具描述 — 可用 agent 列表实时取自注册表，新增 Agent 无需改代码"""
    items = "；".join(
        f"{c.agent_id}({c.description})" for c in get_agent_registry().list_configs()
    )
    return (
        "委托子Agent执行独立任务。子Agent拥有独立上下文与只读工具子集"
        "（不能写文件、不能执行命令、不能向用户提问）。"
        "适用于：并行搜索不同来源、独立审查验证、工具专精任务、知识库多域对照分析。"
        "参数：agent_id(见下) + task(自包含任务描述，≤500字) + context(可选附加信息) + wait(默认同步等待结果)。"
        "子Agent完成后回传摘要和token用量，父Agent整合结果继续。"
        f"可用agent_id：{items or '（注册表为空）'}。"
    )
