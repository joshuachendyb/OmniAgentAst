# backend/app/api/v1/types/process_start.py
# start阶段处理逻辑（Start2版本 - 带LLM调用）
# 创建时间: 2026-03-19
# 创建人: 小沈
# 检查人: 小健 2026-03-19
# 参考: doc-ReAct重构/重构Start设计与实现说明-小沈-2026-03-19.md

import json
import logging
from datetime import datetime
from typing import Any, Dict, AsyncGenerator

from app.services.shell_security import check_command_safety
from app.utils.display_name_cache import cache_display_name
from app.chat_stream import create_timestamp, get_provider_display_name

logger = logging.getLogger(__name__)


# ============================================================
# LLM系统提示词 - Start阶段专用
# ============================================================
START_SYSTEM_PROMPT = """你是一个任务分析助手。请分析用户的输入，判断以下内容：

1. 输入是否清晰明确？
2. 是否存在安全风险？（结合下面的安全检查结果判断）
3. 是否需要用户确认？

安全检查结果:
- is_safe: 是否安全（true/false）
- risk_level: 风险等级（safe/low/medium/high/critical）
- risk: 风险描述
- blocked: 是否被拦截（true/false）

请以JSON格式返回，字段说明：
- is_clear: 输入是否清晰（true/false）
- is_need_confirm: 是否需要用户确认（true/false）
- analysis: 分析内容（当is_clear=true时填写）
- clarification_question: 澄清问题（当is_clear=false时填写）
"""


# ============================================================
# 状态图标判断 - 优先级从高到低
# ============================================================
def get_status_icon(
    security_result: Dict[str, Any], 
    is_clear: bool,
    is_need_confirm_from_security: bool
) -> str:
    """
    根据条件判断状态图标（version.txt说明）
    
    优先级：
    1. blocked=true → 🚫 （安全拦截）
    2. is_clear=false → ❓ （输入含混不清）
    3. is_need_confirm_from_security=true → ⚠️ （有风险需确认）
    4. 其他 → ✅ （正常，可进入thought）
    
    Args:
        security_result: 安全检查结果字典
        is_clear: LLM返回的is_clear字段
        is_need_confirm_from_security: 安全检查返回的is_need_confirm字段
    
    Returns:
        str: 状态图标
    """
    if security_result.get('blocked', False):
        return '🚫'
    elif not is_clear:
        return '❓'
    elif is_need_confirm_from_security:
        return '⚠️'
    else:
        return '✅'


# ============================================================
# 解析LLM返回结果
# ============================================================
def parse_llm_response(content: str) -> tuple[bool, bool, str]:
    """
    解析LLM返回的JSON内容
    
    Args:
        content: LLM返回的原始内容（可能是JSON格式）
    
    Returns:
        tuple: (is_clear, is_need_confirm_from_llm, display_content)
        - is_need_confirm_from_llm: 固定为 False，不使用用户确认功能（设计文档4.3节）
    """
    try:
        result = json.loads(content)
        is_clear = result.get('is_clear', True)
        is_need_confirm_from_llm = False  # 固定为False
        
        if is_clear:
            display_content = result.get('analysis', '')
        else:
            display_content = result.get('clarification_question', '')
        
        return is_clear, is_need_confirm_from_llm, display_content
    except json.JSONDecodeError:
        # JSON解析失败，使用默认值
        return True, False, content


# ============================================================
# 组织LLM输入
# ============================================================
def build_llm_input(user_message: str, security_result: Dict[str, Any]) -> str:
    """
    构建LLM输入prompt
    
    Args:
        user_message: 用户输入的原始消息
        security_result: 安全检查结果字典
    
    Returns:
        str: 构建好的LLM prompt
    """
    is_safe = security_result.get('is_safe', True)
    risk_level = security_result.get('risk_level', '')
    risk = security_result.get('risk', '')
    blocked = security_result.get('blocked', False)
    
    prompt = f"""用户输入: {user_message}

安全检查结果:
- 是否安全: {is_safe}
- 风险等级: {risk_level}
- 风险描述: {risk}
- 是否拦截: {blocked}

请分析:
1. 用户意图是什么？
2. 输入是否清晰明确？
3. 如果不安全或输入不清晰，说明原因？
4. 是否需要用户确认？

请以JSON格式返回分析结果。"""
    
    return prompt


# ============================================================
# process_start - Start2版本（带LLM调用）
# ============================================================
async def process_start(
    request: Any,                 # ChatRequest
    ai_service: Any,              # AIService
    task_id: str,                 # 任务ID
    step_counter: Any,            # 步骤计数器（引用）
    current_execution_steps: Any, # 执行步骤列表（引用）
    current_content: Any,         # 当前内容（引用）
    save_func: Any,               # 保存到数据库的函数
    add_step_func: Any,           # 添加步骤到数据库的函数
    next_step: Any                # next_step()函数（外部传入）
) -> AsyncGenerator[dict, None]:
    """
    处理start阶段（Start2版本 - 带LLM调用）
    
    功能流程：
    1. 构建 display_name
    2. security_check
    3. step_counter = 0, next_step()
    4. 构建 start_data
    5. yield start_data（第一次）
    6. 保存数据库
    7. if not is_safe → yield error, return
    
    安全通过后：
    8. 组织LLM输入
    9. 调用LLM
    10. 读取LLM返回
    11. yield {content, is_clear, is_need_confirm, status_icon}（第二次）
    
    Args:
        request: ChatRequest 用户请求
        ai_service: AIService AI服务
        task_id: str 任务ID
        step_counter: 步骤计数器（引用）
        current_execution_steps: 执行步骤列表（引用）
        current_content: 当前内容（引用）
        save_func: 保存到数据库的函数
        add_step_func: 添加步骤到数据库的函数
        next_step: next_step()函数（外部传入）
    
    Yields:
        dict: start_data / error_data / content_data
        第二次yield: {content, is_clear, is_need_confirm, status_icon}
    """
    # 1. 构建 display_name（AI显示名称）
    display_name = f"{get_provider_display_name(ai_service.provider)} ({ai_service.model})"
    
    # 缓存 display_name
    if request.session_id:
        cache_display_name(request.session_id, display_name)
    
    # 2. 执行 security_check → 安全检查结果
    last_message = request.messages[-1].content if request.messages else ""
    security_result = check_command_safety(last_message)
    
    # 4. 构建 start_data 字典
    start_data = {
        'type': 'start',
        'step': next_step(),
        'timestamp': create_timestamp(),
        'display_name': display_name,
        'provider': ai_service.provider,
        'model': ai_service.model,
        'task_id': task_id,
        'security_check': {
            'is_safe': security_result.get('is_safe', True),
            'risk_level': security_result.get('risk_level'),
            'risk': security_result.get('risk'),
            'blocked': security_result.get('blocked', False)
        }
    }
    
    logger.info(f"[Step start] 发送start步骤 - step={start_data['step']}, model={ai_service.model}, provider={ai_service.provider}, task_id={task_id[:8]}..., security_check.is_safe={security_result.get('is_safe', True)}")
    
    # 5. yield start_data（第一次）
    yield start_data
    
    # 6. 保存到数据库
    current_execution_steps.append(start_data)
    await save_func(current_execution_steps, current_content)
    
    # 7. if not is_safe → yield error, return
    if not security_result.get('is_safe', True):
        risk = security_result.get('risk', '未知风险')
        error_data = {
            'type': 'error',
            'step': next_step(),
            'code': 'SECURITY_BLOCKED',
            'message': f'危险操作需确认: {risk}',
            'error_type': 'security',
            'details': f"risk_level: {security_result.get('risk_level')}",
            'retryable': False,
            'timestamp': create_timestamp(),
            'model': request.model,
            'provider': request.provider
        }
        logger.info(f"[Step error] 发送error步骤(安全检测拦截) - step={error_data['step']}, code={error_data['code']}, message={error_data['message']}, retryable={error_data['retryable']}")
        yield error_data
        
        # 保存error步骤到数据库
        error_step = {
            'type': 'error',
            'step': error_data['step'],
            'code': error_data['code'],
            'message': error_data['message'],
            'error_type': error_data['error_type'],
            'timestamp': create_timestamp()
        }
        await add_step_func(error_step, f"错误: {error_data['message']}")
        return
    
    # ============================================================
    # 【Start2新增】安全通过后，调用LLM获取分析结果
    # ============================================================
    
    # 8. 组织LLM输入
    llm_input = build_llm_input(last_message, security_result)
    
    # 9. 调用LLM（流式调用）
    logger.info(f"[Start2] 开始LLM调用分析...")
    llm_content = ""
    try:
        async for chunk in ai_service.stream(START_SYSTEM_PROMPT + "\n\n" + llm_input):
            llm_content += chunk
    except Exception as e:
        logger.error(f"[Start2] LLM调用失败: {e}", exc_info=True)
        # LLM调用失败时，使用默认值并提供fallback内容
        display_content = "（LLM分析暂时不可用）"
        is_need_confirm_from_security = security_result.get('is_need_confirm', False)
        status_icon = get_status_icon(security_result, True, is_need_confirm_from_security)
        
        # 第二次yield：提供fallback内容给前端
        yield {
            'content': display_content,
            'is_clear': True,
            'is_need_confirm_from_security': is_need_confirm_from_security,
            'is_need_confirm_from_llm': False,  # 固定为False
            'status_icon': status_icon
        }
        
        # 保存start_analysis步骤到数据库
        start_analysis_step = {
            'type': 'start_analysis',
            'step': next_step(),
            'timestamp': create_timestamp(),
            'content': display_content,
            'is_clear': True,
            'is_need_confirm_from_security': is_need_confirm_from_security,
            'is_need_confirm_from_llm': False,  # 固定为False
            'status_icon': status_icon
        }
        await add_step_func(start_analysis_step, display_content)
        
        # 返回完成
        yield {'_start_complete': True, 'is_safe': True, 'display_name': display_name}
        return
    
    logger.info(f"[Start2] LLM调用完成，content长度={len(llm_content)}")
    
    # 10. 读取LLM返回（is_need_confirm_from_llm固定为False，设计文档4.3节）
    is_clear, is_need_confirm_from_llm, display_content = parse_llm_response(llm_content)
    
    # 11. 获取安全检查的 is_need_confirm（用于状态图标判断）
    is_need_confirm_from_security = security_result.get('is_need_confirm', False)
    
    # 12. 判断状态图标
    status_icon = get_status_icon(security_result, is_clear, is_need_confirm_from_security)
    
    # 第二次yield：content + 状态信息（version.txt说明：包含两个独立字段）
    yield {
        'content': display_content,
        'is_clear': is_clear,
        'is_need_confirm_from_security': is_need_confirm_from_security,
        'is_need_confirm_from_llm': is_need_confirm_from_llm,  # 固定为False
        'status_icon': status_icon
    }
    
    # 保存start阶段的分析结果到数据库
    # 🔴 is_need_confirm_from_security和is_need_confirm_from_llm保留用于数据库存储
    start_analysis_step = {
        'type': 'start_analysis',
        'step': next_step(),
        'timestamp': create_timestamp(),
        'content': display_content,
        'is_clear': is_clear,
        'is_need_confirm_from_security': security_result.get('is_need_confirm', False),
        'is_need_confirm_from_llm': False,  # 固定为False（设计文档4.3节）
        'status_icon': status_icon
    }
    await add_step_func(start_analysis_step, display_content)
    
    # 返回 is_safe 标志和 display_name，供主流程判断
    yield {'_start_complete': True, 'is_safe': True, 'display_name': display_name}
