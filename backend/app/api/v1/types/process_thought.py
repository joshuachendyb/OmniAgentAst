# backend/app/api/v1/types/process_thought.py
# thought阶段处理逻辑（Thought2版本 - 带LLM调用）
# 创建时间: 2026-03-19
# 创建人: 小沈
# 参考: doc-ReAct重构/重构Thought设计与实现说明-小沈-2026-03-19.md 第8章

import json
import logging
from typing import Any, Dict, Optional, AsyncGenerator, Tuple

from app.chat_stream_helpers import create_timestamp

logger = logging.getLogger(__name__)


# ============================================================
# SYSTEM_PROMPT - LLM系统提示词（设计文档4.2）
# ============================================================
SYSTEM_PROMPT = """你是一个任务执行助手。请根据上下文信息，决定下一步行动。

可用工具:
1. list_directory - 列出目录内容，参数: path
2. read_file - 读取文件内容，参数: path, offset(可选), limit(可选)
3. write_file - 写入文件内容，参数: path, content
4. create_directory - 创建目录，参数: path
5. delete_file - 删除文件，参数: path
6. move_file - 移动文件，参数: source, destination
7. copy_file - 复制文件，参数: source, destination
8. finish - 结束任务，参数: 无（表示任务完成）

请以JSON格式返回，字段说明：
- content: 你的思考内容（推理结论）
- action_tool: 工具名称（finish表示任务完成）
- params: 工具参数（finish时为空对象{}）
"""


# ============================================================
# build_reasoning - 生成reasoning内容
# ============================================================
def build_reasoning(prev_step: Optional[Dict]) -> str:
    """
    生成reasoning内容（文档3.2.2）
    
    传导来源对照：
    - 从 start 进入：reasoning = start.content + start.is_clear
    - 从 observation 进入：reasoning = observation.summary
    
    Args:
        prev_step: 前一阶段数据（start或observation）
    
    Returns:
        str: reasoning内容
    """
    prev_type = prev_step.get('type') if prev_step else None
    
    if prev_type is None or prev_type == 'start':
        # 从 start 进入
        start_content = prev_step.get('content', '') if prev_step else ''
        is_clear = prev_step.get('is_clear', True) if prev_step else True
        reasoning = f"""用户输入分析:
{start_content}

输入清晰度: {'是' if is_clear else '否'}
"""
    elif prev_type == 'observation':
        # 从 observation 进入
        reasoning = prev_step.get('summary', '') if prev_step else ''
    else:
        # 其他情况，使用空字符串
        reasoning = ''
    
    return reasoning


# ============================================================
# parse_llm_response - 解析LLM返回
# ============================================================
def parse_llm_response(content: str) -> Tuple[str, str, Dict]:
    """
    解析LLM返回的JSON内容（文档4.1）
    
    LLM返回格式：
    {
        "content": "用户想要查看桌面文件，我需要先列出桌面目录的内容",
        "action_tool": "list_directory",
        "params": {"path": "C:\\Users\\xxx\\Desktop"}
    }
    
    Args:
        content: LLM返回的原始内容（JSON格式）
    
    Returns:
        tuple: (llm_content, action_tool, params)
        - llm_content: LLM返回的推理结论
        - action_tool: 工具名称（默认'finish'）
        - params: 工具参数（默认{}）
    """
    try:
        result = json.loads(content)
        llm_content = result.get('content', '')
        action_tool = result.get('action_tool', 'finish')
        params = result.get('params', {})
        return llm_content, action_tool, params
    except json.JSONDecodeError:
        # JSON解析失败，使用默认值
        logger.warning(f"[process_thought] LLM返回JSON解析失败，使用默认值")
        return content, 'finish', {}


# ============================================================
# build_llm_input - 组织LLM输入
# ============================================================
def build_llm_input(reasoning: str) -> str:
    """
    构建LLM输入prompt（文档3.2.4）
    
    LLM输入项：
    - SYSTEM_PROMPT: 系统提示词（角色定义+工具列表+返回格式）
    - reasoning: 上下文信息（start.content或observation.summary）
    
    Args:
        reasoning: 上下文信息（reasoning内容）
    
    Returns:
        str: 构建好的LLM prompt
    """
    llm_prompt = f"""{SYSTEM_PROMPT}

上下文信息:
{reasoning}
"""
    return llm_prompt


# ============================================================
# build_thought_data_placeholder - 构建占位版本thought_data
# ============================================================
def build_thought_data_placeholder(step: int, timestamp: int, reasoning: str) -> Dict:
    """
    构建占位版本thought_data（文档3.2.3）
    
    第一次yield的字段：
    - type: "thought"（固定值）
    - step: 步骤序号
    - timestamp: 时间戳
    - content: "分析中..."（占位符）
    - reasoning: 传导内容
    
    注意：不发空的 action_tool 和 params
    
    Args:
        step: 步骤序号
        timestamp: 时间戳
        reasoning: 传导的reasoning内容
    
    Returns:
        dict: 占位版本thought_data
    """
    return {
        'type': 'thought',
        'step': step,
        'timestamp': timestamp,
        'content': '分析中...',
        'reasoning': reasoning,
    }


# ============================================================
# update_thought_data - 更新为完整数据
# ============================================================
def update_thought_data(
    thought_data: Dict,
    llm_content: str,
    action_tool: str,
    params: Dict
) -> Dict:
    """
    更新thought_data为完整数据（文档3.2.6）
    
    第二次yield的字段：
    - type: "thought"（不变）
    - step: 步骤序号（不变）
    - timestamp: 时间戳（不变）
    - content: llm_content（替换）
    - reasoning: 传导内容（不变）
    - action_tool: 工具名称（新增）
    - params: 工具参数（新增）
    
    Args:
        thought_data: 原始thought_data字典
        llm_content: LLM返回的推理结论
        action_tool: LLM返回的工具名称
        params: LLM返回的工具参数
    
    Returns:
        dict: 更新后的完整版thought_data
    """
    thought_data.update({
        'content': llm_content,
        'action_tool': action_tool,
        'params': params
    })
    return thought_data


# ============================================================
# process_thought - 主函数
# ============================================================
async def process_thought(
    prev_step: Optional[Dict],       # 前一阶段数据（start或observation）
    ai_service: Any,                # AIService
    task_id: str,                   # 任务ID
    step_counter: Any,              # 步骤计数器（引用）
    current_execution_steps: Any,    # 执行步骤列表（引用）
    current_content: Any,            # 当前内容（引用）
    save_func: Any,                 # 保存到数据库的函数
    add_step_func: Any,             # 添加步骤到数据库的函数
    next_step: Any                  # next_step()函数
) -> AsyncGenerator[dict, None]:
    """
    处理thought阶段（文档1.1流程）
    
    流程：
    1. 判断前一阶段类型
    2. 生成 reasoning 内容
    3. 构建 thought_data 字典（含"分析中..."占位）
    4. yield thought_data（第一次，发送给前端）
    5. 保存到数据库
    6. 组织LLM输入（reasoning + 工具列表 + 任务说明）
    7. 调用LLM（流式响应）
    8. LLM返回：content + reasoning + action_tool + params
    9. 更新 thought_data（替换占位为content）
    10. yield thought_data（第二次，发送给前端）
    11. 更新数据库
    12. 返回 action_tool 判断结果
    
    Args:
        prev_step: 前一阶段数据（start或observation）
        ai_service: AIService
        task_id: 任务ID
        step_counter: 步骤计数器（引用）
        current_execution_steps: 执行步骤列表（引用）
        current_content: 当前内容（引用）
        save_func: 保存到数据库的函数
        add_step_func: 添加步骤到数据库的函数
        next_step: next_step()函数
    
    Yields:
        dict: 阶段数据字典
        第一次yield: 占位版thought_data
        第二次yield: 完整版thought_data
        第三次yield: {'_thought_complete': True, 'action_tool': xxx, 'params': xxx}
    """
    # 步骤1：判断前一阶段类型（文档3.2.1）
    # prev_step 已在调用方获取，直接使用
    
    # 步骤2：生成 reasoning 内容
    reasoning = build_reasoning(prev_step)
    logger.info(f"[Step thought] reasoning来源: {prev_step.get('type') if prev_step else 'None'}")
    
    # 步骤3：构建占位版 thought_data
    step = next_step()
    timestamp = create_timestamp()
    thought_data = build_thought_data_placeholder(step, timestamp, reasoning)
    logger.info(f"[Step thought] 发送thought步骤 - step={thought_data['step']}, content={thought_data['content']}")
    
    # 步骤4：yield thought_data（第一次，占位版）
    yield thought_data
    
    # 步骤5：保存到数据库
    current_execution_steps.append(thought_data)
    await save_func(current_execution_steps, current_content)
    
    # 步骤6：组织LLM输入
    llm_prompt = build_llm_input(reasoning)
    
    # 步骤7：调用LLM（流式响应）
    logger.info(f"[Step thought] 开始LLM调用...")
    llm_content = ""
    action_tool = 'finish'
    params = {}
    llm_success = False
    
    try:
        async for chunk in ai_service.stream(llm_prompt):
            llm_content += chunk
        llm_success = True
    except Exception as e:
        logger.error(f"[Step thought] LLM调用失败: {e}", exc_info=True)
        # LLM调用失败，使用默认值，跳过解析
        llm_content = "（LLM分析暂时不可用）"
        action_tool = 'finish'
        params = {}
    
    logger.info(f"[Step thought] LLM调用完成，content长度={len(llm_content)}")
    
    # 步骤8：解析LLM返回（仅在LLM调用成功时解析）
    if llm_success:
        llm_content, action_tool, params = parse_llm_response(llm_content)
    logger.info(f"[Step thought] LLM解析结果 - action_tool={action_tool}, params={params}")
    
    # 步骤9：更新 thought_data（完整版）
    thought_data = update_thought_data(thought_data, llm_content, action_tool, params)
    
    # 步骤10：yield thought_data（第二次，完整版）
    logger.info(f"[Step thought] 发送完整thought步骤 - step={thought_data['step']}, content={thought_data['content'][:50]}...")
    yield thought_data
    
    # 步骤11：更新数据库
    await add_step_func(thought_data, llm_content)
    
    # 步骤12：判断 action_tool（设计文档1.1步骤12）
    # finish → 进入 final（ReAct退出点）
    # 其他工具 → 进入 action_tool 阶段
    if action_tool == 'finish':
        # 返回 finish 标志，主流程进入 final
        yield {
            '_thought_complete': True,
            '_next_phase': 'final',
            'action_tool': 'finish',
            'params': params
        }
    else:
        # 返回工具信息，主流程进入 action_tool
        yield {
            '_thought_complete': True,
            '_next_phase': 'action_tool',
            'action_tool': action_tool,
            'params': params
        }
