#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
七牛 AI 完整模型列表（52个模型）

【创建时间】2026-03-27
【依据】doc-多意图/LLM-Structured-Outputs-支持情况研究报告-小沈-2026-03-20.md
【API】https://api.qnaigc.com/v1

功能支持说明：
- basic: 基本调用
- response_format: Structured Outputs (JSON格式)
- tools: Function Calling
- reasoning_content: 思考过程输出

作者：小沈
"""

QINIU_CONFIG = {
    "api_base": "https://api.qnaigc.com/v1",
    "api_key": "sk-ee99b1ccb7495fd4fab4114697e69984846e5884059ae108ce0dda350a1ed9d6",
}


# ============================================================================
# 完整模型列表（52个）- 按序号排列
# ============================================================================

ALL_MODELS = [
    # 智谱AI
    {"no": 1, "id": "z-ai/glm-5", "name": "GLM-5", "provider": "智谱AI"},
    {"no": 22, "id": "z-ai/glm-4.7", "name": "GLM-4.7", "provider": "智谱AI"},
    {"no": 42, "id": "z-ai/glm-4.6", "name": "GLM-4.6", "provider": "智谱AI"},
    {"no": 4, "id": "glm-4.5-air", "name": "GLM-4.5 Air", "provider": "智谱AI"},
    {"no": 27, "id": "glm-4.5", "name": "GLM-4.5", "provider": "智谱AI"},
    
    # OpenAI
    {"no": 2, "id": "openai/gpt-5.4", "name": "GPT-5.4", "provider": "OpenAI"},
    {"no": 3, "id": "openai/gpt-5.4-mini", "name": "GPT-5.4 Mini", "provider": "OpenAI"},
    
    # MiniMax
    {"no": 5, "id": "minimax/minimax-m2.5", "name": "MiniMax M2.5", "provider": "MiniMax"},
    {"no": 21, "id": "minimax/minimax-m2.1", "name": "MiniMax M2.1", "provider": "MiniMax"},
    {"no": 41, "id": "minimax/minimax-m2", "name": "MiniMax M2", "provider": "MiniMax"},
    {"no": 28, "id": "MiniMax-M1", "name": "MiniMax M1", "provider": "MiniMax"},
    
    # NVIDIA
    {"no": 6, "id": "nvidia/nemotron-3-super-120b-a12b", "name": "Nemotron", "provider": "NVIDIA"},
    
    # 通义千问
    {"no": 7, "id": "qwen3-235b-a22b-thinking-2507", "name": "Qwen3 思考版", "provider": "通义千问"},
    {"no": 8, "id": "qwen3-coder-480b-a35b-instruct", "name": "Qwen3 Coder", "provider": "通义千问"},
    {"no": 14, "id": "qwen3-32b", "name": "Qwen3 32B", "provider": "通义千问"},
    {"no": 24, "id": "qwen3-vl-30b-a3b-thinking", "name": "Qwen3 VL 思考版", "provider": "通义千问"},
    {"no": 25, "id": "qwen3-30b-a3b-thinking-2507", "name": "Qwen3 30B 思考版", "provider": "通义千问"},
    {"no": 26, "id": "qwen3-30b-a3b-instruct-2507", "name": "Qwen3 30B", "provider": "通义千问"},
    {"no": 29, "id": "qwen3-next-80b-a3b-thinking", "name": "Qwen3 Next 思考版", "provider": "通义千问"},
    {"no": 30, "id": "qwen3-max-preview", "name": "Qwen3 Max Preview", "provider": "通义千问"},
    {"no": 31, "id": "qwen3-235b-a22b", "name": "Qwen3 235B", "provider": "通义千问"},
    {"no": 33, "id": "qwen-vl-max-2025-01-25", "name": "Qwen VL Max", "provider": "通义千问"},
    {"no": 34, "id": "qwen-max-2025-01-25", "name": "Qwen Max", "provider": "通义千问"},
    {"no": 35, "id": "qwen3-30b-a3b", "name": "Qwen3 30B", "provider": "通义千问"},
    {"no": 36, "id": "qwen2.5-vl-72b-instruct", "name": "Qwen2.5 VL", "provider": "通义千问"},
    {"no": 37, "id": "qwen2.5-vl-7b-instruct", "name": "Qwen2.5 VL 7B", "provider": "通义千问"},
    {"no": 38, "id": "qwen-turbo", "name": "Qwen Turbo", "provider": "通义千问"},
    {"no": 43, "id": "qwen3-max", "name": "Qwen3 Max", "provider": "通义千问"},
    {"no": 52, "id": "qwen3-next-80b-a3b-instruct", "name": "Qwen3 Next Instruct", "provider": "通义千问"},
    {"no": 49, "id": "qwen3-235b-a22b-instruct-2507", "name": "Qwen3 235B Instruct", "provider": "通义千问"},
    
    # Kimi
    {"no": 9, "id": "moonshotai/kimi-k2.5", "name": "Kimi K2.5", "provider": "Kimi"},
    {"no": 23, "id": "moonshotai/kimi-k2-0905", "name": "Kimi K2-0905", "provider": "Kimi"},
    {"no": 50, "id": "moonshotai/kimi-k2-thinking", "name": "Kimi K2 Thinking", "provider": "Kimi"},
    {"no": 51, "id": "kimi-k2", "name": "Kimi K2 (简化)", "provider": "Kimi"},
    
    # 美团
    {"no": 10, "id": "meituan/longcat-flash-lite", "name": "LongCat Lite", "provider": "美团"},
    
    # 字节豆包
    {"no": 11, "id": "doubao-1.5-thinking-pro", "name": "豆包思考版", "provider": "字节豆包"},
    {"no": 12, "id": "doubao-1.5-vision-pro", "name": "豆包视觉版", "provider": "字节豆包"},
    {"no": 13, "id": "doubao-seed-1.6-thinking", "name": "Seed 思考版", "provider": "字节豆包"},
    {"no": 38, "id": "doubao-seed-1.6-flash", "name": "Seed Flash", "provider": "字节豆包"},
    {"no": 39, "id": "doubao-seed-1.6", "name": "Seed", "provider": "字节豆包"},
    {"no": 45, "id": "doubao-1.5-pro-32k", "name": "豆包 Pro 32K", "provider": "字节豆包"},
    
    # DeepSeek
    {"no": 17, "id": "deepseek-r1", "name": "DeepSeek R1", "provider": "DeepSeek"},
    {"no": 18, "id": "deepseek-r1-0528", "name": "DeepSeek R1 0528", "provider": "DeepSeek"},
    {"no": 19, "id": "deepseek-v3-0324", "name": "V3.2 0324", "provider": "DeepSeek"},
    {"no": 20, "id": "deepseek/deepseek-v3.2-251201", "name": "V3.2", "provider": "DeepSeek"},
    {"no": 15, "id": "deepseek/deepseek-v3.2-exp-thinking", "name": "V3.2 Exp Thinking", "provider": "DeepSeek"},
    {"no": 16, "id": "deepseek/deepseek-v3.2-exp", "name": "V3.2 Exp", "provider": "DeepSeek"},
    {"no": 40, "id": "deepseek/deepseek-v3.1-terminus-thinking", "name": "V3.1 Thinking", "provider": "DeepSeek"},
    {"no": 46, "id": "deepseek-v3", "name": "DeepSeek V3", "provider": "DeepSeek"},
    {"no": 47, "id": "deepseek/deepseek-v3.1-terminus", "name": "V3.1", "provider": "DeepSeek"},
    {"no": 48, "id": "deepseek-v3.1", "name": "DeepSeek V3.1", "provider": "DeepSeek"},
    
    # 小米
    {"no": 44, "id": "xiaomi/mimo-v2-flash", "name": "Mimo Flash", "provider": "小米"},
]


# ============================================================================
# 测试结果（按模型ID索引）
# ============================================================================

TEST_RESULTS = {
    "z-ai/glm-4.7": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "z-ai/glm-4.6": {"basic": True, "response_format": True, "tools": True, "reasoning_content": True},
    "moonshotai/kimi-k2": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "moonshotai/kimi-k2-0905": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "moonshotai/kimi-k2-thinking": {"basic": True, "response_format": False, "tools": False, "reasoning_content": False},
    "moonshotai/kimi-k2.5": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "minimax/minimax-m2": {"basic": True, "response_format": "non_json", "tools": True, "reasoning_content": False},
    "minimax/minimax-m2.5": {"basic": True, "response_format": True, "tools": True, "reasoning_content": True},
    "MiniMax-M1": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "deepseek-v3": {"basic": True, "response_format": "non_json", "tools": True, "reasoning_content": False},
    "deepseek-v3.1": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "deepseek-r1": {"basic": True, "response_format": True, "tools": True, "reasoning_content": True},
    "qwen-turbo": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "qwen3-max": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
    "kimi-k2": {"basic": True, "response_format": True, "tools": True, "reasoning_content": False},
}


# ============================================================================
# 推荐配置
# ============================================================================

RECOMMENDED_FOR_TOOLS = [
    "z-ai/glm-4.6",
    "minimax/minimax-m2.5",
]

RECOMMENDED_FOR_INTENT = [
    "z-ai/glm-4.7",
    "moonshotai/kimi-k2.5",
]


# ============================================================================
# 便捷函数
# ============================================================================

def get_model_info(model_id: str) -> dict:
    """获取模型信息"""
    for model in ALL_MODELS:
        if model["id"] == model_id:
            result = model.copy()
            result.update(TEST_RESULTS.get(model_id, {}))
            return result
    return {"id": model_id, "name": model_id, "support": "unknown"}


def is_full_support(model_id: str) -> bool:
    """检查是否完整支持（response_format + tools + reasoning_content）"""
    result = TEST_RESULTS.get(model_id, {})
    return result.get("response_format") is True and result.get("tools") is True and result.get("reasoning_content") is True


def is_tools_support(model_id: str) -> bool:
    """检查是否支持 tools"""
    result = TEST_RESULTS.get(model_id, {})
    return result.get("tools") is True


def is_rf_support(model_id: str) -> bool:
    """检查是否支持 response_format"""
    result = TEST_RESULTS.get(model_id, {})
    return result.get("response_format") is True


# ============================================================================
# 主程序
# ============================================================================

if __name__ == "__main__":
    import sys
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 80)
    print("七牛 AI 完整模型列表（52个）")
    print("=" * 80)
    print(f"\nAPI: {QINIU_CONFIG['api_base']}")
    print(f"总模型数: {len(ALL_MODELS)}")
    print("\n" + "=" * 80)
    
    # 按提供商分组
    providers = {}
    for model in ALL_MODELS:
        p = model["provider"]
        if p not in providers:
            providers[p] = []
        providers[p].append(model)
    
    for provider, models in providers.items():
        print(f"\n【{provider}】{len(models)}个")
        print("-" * 80)
        for m in models:
            result = TEST_RESULTS.get(m["id"], {})
            rf = "✅" if result.get("response_format") is True else ("⚠️" if result.get("response_format") == "non_json" else "❌")
            tools = "✅" if result.get("tools") else "❌"
            reasoning = "✅" if result.get("reasoning_content") else "❌"
            print(f"  {m['no']:2d}. {m['id']:<45} rf:{rf} tools:{tools} reason:{reasoning}")
