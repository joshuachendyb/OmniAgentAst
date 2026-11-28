# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 - 小健 - ToolMetadata 新增 target_param 字段(操作对象/主参数显式声明扩展点), 供 action_handler._resolve_target_field 优先采用; 留空则按schema属性自动推导(DRY/OCP)
# 2026-10-02 - 小欧 - 删 SHELL 枚举(which 归 SYSTEM 后该分类归零; 空分类会写入 searchtool 描述误导 LLM); order 留空位号2不动, 避免 patch_search_desc 排序变化 — 小欧-2026-10-02
# 2026-10-15 - 小欧 - 跟随订正: action_kind 注释"dual"去 edit(单路径改走写线)、删"none"档(通道 A 零命中即放行); 表名 TOOL_ACTION_KINDS→PATH_ACTION_KINDS。
# 2026-10-18 - 小欧 - SafetyResult 契约迁出: 生产者已全部落 app/safety/, 契约随生产者回迁系统层 app/safety/safety_result.py(本模块不再定义/转出); 禁 backward 双份契约。
# 2026-10-19 - 小欧 - ToolMetadata 增 available/missing_deps: 注册期依赖检查的结论落元数据(原先只打warning后丢弃,
#   不可用工具照样进 LLM 工具列表, LLM 试调才知缺库)。缺库工具仍注册但对 LLM 不可见。
# 2026-10-19 - 小欧 - 新增 visible_to_llm 属性: "该不该给 LLM 看"的唯一判据(= expose_to_llm and available),
#   原先各消费方各写双判断, 新增维度需同步改多处, 漏一处即口径分裂。
# 2026-11-18 - 商量 - 新增 AGENT 分类(order 10): question/schedule 属智能体与用户/与自身计划交互, 不操作文件/网络/硬件, 落现有分类均语义错配
# 2026-11-19 - 小欧 - ToolMetadata 新增 hide_from_steps 属性(工具行是否进前端步骤流), 供框架层统一判据 visible_in_steps 消费;
#   走专用通道的工具(如 schedule→notice)注册时声明, 业务调用点零改动(OCP)
# 2026-11-20 - 小欧 - 新增 MEDIA 分类(order 11): generate_image/generate_video 走 generation 端点产多媒体, 不碰文件/网络工具链
# 2026-11-27 - 小欧 - ToolMetadata.description 放宽为 Union[str, Callable[[], str]] 并新增 resolved_description():
#   callable 描述由注册表快照动态生成(delegateagent 可用 Agent 列表), 读取方统一走解析点, 直接拼接会得到函数对象
"""
工具类型定义 — 单一定义源(OCP:新增分类只需在此文件添加)
- ToolCategory 枚举
- CATEGORY_ORDER / CATEGORY_NAMES 自动派生

拆分自 registry.py — 小沈 2026-05-29
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from app.logger import logger

# ====================================================================
# 一、工具分类枚举
# ====================================================================

class ToolCategory(Enum):
    """
    工具分类枚举

    每个成员携带 (value, order, name_cn):
    - order: 显示排序
    - name_cn: 中文名称
    """
    FILE = ("file", 0, "文件操作工具")
    FUNDAMENTAL = ("fundamental", 1, "基础工具")
    # 2026-10-02 小欧 - SHELL 分类已删, order 留空位号2不动(避免 searchtool 排序变化)
# 2026-10-18 小欧 - 新增 confirm_fn / op_param 两个字段:
#   confirm_fn  工具级确认回调(要否确认 + 弹窗文案), SQL/命令语义只有工具知道, 不放安全层;
#   op_param    操作标识参数名, 拒绝文案取该参数说清"拒的是哪个操作", 免得安全层硬编码工具名。
    NETWORK = ("network", 3, "网络请求工具")
    DESKTOP = ("desktop", 4, "桌面交互工具")
    DOCUMENT = ("document", 5, "文档操作工具")
    DATAANALYSIS = ("dataanalysis", 6, "数据分析工具")
    SYSTEM = ("system", 7, "系统管理工具")
    TIMER = ("timer", 8, "定时器工具")
    WIN_REGISTRY = ("win_registry", 9, "注册表工具")
    AGENT = ("agent", 10, "智能体交互工具")
    # 2026-11-20 小欧 - 新增 MEDIA 分类(生成图像/生成视频工具): 产出多媒体, 走 generation 端点
    MEDIA = ("media", 11, "媒体生成工具")

    def __new__(cls, value, order, name_cn):
        member = object.__new__(cls)
        member._value_ = value
        member._order = order
        member._name_cn = name_cn
        return member

    @property
    def order(self) -> int:
        return self._order

    @property
    def name_cn(self) -> str:
        return self._name_cn


CATEGORY_ORDER: List[ToolCategory] = sorted(ToolCategory, key=lambda c: c.order)

CATEGORY_NAMES: Dict[ToolCategory, str] = {cat: cat.name_cn for cat in ToolCategory}



# ====================================================================
# 二、工具元数据
# ====================================================================

@dataclass
class ToolMetadata:
    """工具元数据"""
    name: str
    #: 2026-11-27 小欧 - 允许 callable: 描述可由注册表快照动态生成(delegateagent 的可用 Agent 列表),
    #: 新增 Agent 零改描述代码; 读取方一律走 resolved_description(), 禁止直接拼接本字段。
    description: Union[str, Callable[[], str]]
    category: ToolCategory
    version: str = "1.0.0"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    expose_to_llm: bool = True
    failure_hint_fn: Optional[Callable] = None

    # 【2026-06-16 小沈】Layer 2安全字段（替代5级枚举）
    needs_confirmation: bool = False
    action_confirmation: Optional[Dict[str, bool]] = None

#: 逐调用确认策略: (params) -> (bool, str) —— 要否确认 + 弹窗原因文案。
    #: 与 needs_confirmation 互斥, 设了本项即由回调全权决定。
    #: 放工具侧而非安全层 —— 业务语义(如"哪条 SQL 算破坏")与用户可读文案只有工具知道。
    #: 文案要求: 说明「做什么 / 对什么 / 后果」, 不得只说"需确认"。
    #: 回调抛异常时安全层按需确认收(fail-closed)。
    confirm_fn: Optional[Callable] = None

    # 【2026-06-18 小健】工具依赖管理
    dependencies: List[Union[str, Dict[str, Any]]] = field(default_factory=list)

    #: 依赖是否齐备: 注册期 _check_dependencies 的结论(原先算完即丢)。
    #: False=缺库, 工具仍注册(保留历史/提示能力)但对 LLM 不可见(to_openai_tools 过滤),
    #: 直调时返回统一缺库契约, 免得 LLM 试调一次才知不可用、白耗一轮。
    available: bool = True
    #: 缺失的依赖描述(pip 规格串), 供缺库提示指名该装什么。
    missing_deps: List[str] = field(default_factory=list)

    @property
    def visible_to_llm(self) -> bool:
        """是否给 LLM 看 —— 「该不该暴露」的唯一判定点 — 小欧 2026-10-19

        此前 tool_description 两处各写 `expose_to_llm and available` 双判断, 新增维度就得
        同步改多处, 漏一处即口径分裂(清单列了签名而实际调不通)。收口为本属性后,
        各消费方只读这一个判据, 加维度只改这一处。
        """
        return self.expose_to_llm and self.available

    def resolved_description(self) -> str:
        """取描述文本 —— description 允许 callable 时的唯一解析点 — 小欧 2026-11-27

        读取方(tool_description/registry.list_tools/tool_search/tool_cache_manager)一律调本方法,
        不得直接拼接 self.description: callable 被拼进字符串会变成函数对象, 运行期才炸。
        解析异常按空串返回并留日志, 不让一个坏描述拖垮整个工具列表。
        """
        if callable(self.description):
            try:
                return str(self.description() or "")
            except Exception as e:
                logger.warning(f"[ToolMetadata] 工具 '{self.name}' 动态描述生成失败: {e}")
                return ""
        return str(self.description or "")

    # 【2026-11-19 小欧】工具行前端可见性: True=该工具的 action/observation 不在前端步骤流画工具行
    #   (走专用通道呈现, 如 schedule 清单走 notice→taskinfo 卡片)。框架层构建 tools/tool_result 视图
    #   统一读 visible_in_steps 判据, 业务调用点零改动, 新工具想隐藏只需注册时声明 hide_from_steps。
    hide_from_steps: bool = False

    # 【2026-08-18 小健】主参数(操作对象字段名): target展示自动推导的显式声明扩展点;
    # 留空则由action_handler._TARGET_PARAM_PRIORITY按input_schema.properties自动推导(DRY/OCP)
    target_param: Optional[str] = None

    #: 操作标识参数名: 拒绝/确认文案里"被拒的是哪个操作"取该参数的值。
    #: 与 target_param 的分工: target_param 标识**操作对象**(路径类工具),
    #: 本字段标识**操作本身**(execute_sql 取 sql、bash 取 command), 留空则回落 path/dest。
    #: 声明在工具侧而非散在文案函数里, 免得加工具要改安全层(OCP)。
    op_param: Optional[str] = None

    # 【2026-10-15 小欧 — 阶段三 / 2026-10-16 四表分立】动作类型(读/写/删/双路径),
    # 由 tool_constants 的 READ_PATH_TOOLS / WRITE_PATH_TOOLS / DELETE_PATH_TOOLS / DUAL_PATH_TOOLS
    # 四表在注册时按工具名赋值(registry._resolve_action_kind 依次查表)。取代原单张 PATH_ACTION_KINDS。
    #   "read"    只读, 路径检查走 read_path_check(禁区放行, 不弹授权)
    #   "write"   写入或改写, 走 write_path_check
    #   "delete"  删除, 走 delete_path_check(禁区硬拦, 永不授权)
    #   "dual"   一调用内含多个路径动作(copy/move/compress/extract/rename),
    #             走 dual_path_check 按参数分别归线; 单路径的 edit 不得进此档
    # 默认 "write" 是 fail-closed 方向: 未声明的新工具按最严档处理, 与改造前 else 分支行为一致。
    action_kind: str = "write"


    def get_failure_hint(self, tool_params: Optional[dict] = None) -> str:
        """获取工具失败时的替代建议 — 小健 2026-05-24"""
        if self.failure_hint_fn:
            try:
                return self.failure_hint_fn(tool_params)
            except Exception as e:
                logger.warning(f"[ToolMetadata] failure_hint_fn 异常: {e}")
        return ""


__all__ = [
    "ToolCategory",
    "CATEGORY_ORDER",
    "CATEGORY_NAMES",
    "ToolMetadata",
]
