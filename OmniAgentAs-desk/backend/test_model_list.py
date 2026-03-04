#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))

import yaml
import asyncio
import logging
from app.api.v1.config import get_model_list
from app.config import get_config

# 设置日志级别
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_model_list():
    print("=== 测试模型列表 ===")
    
    # 测试 1: 加载配置
    config = get_config()
    
    # 获取配置文件路径
    from app.api.v1.config import _get_config_path
    config_path = _get_config_path()
    print(f"配置路径: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_content = f.read()
        print("配置文件内容:")
        print(config_content)
    
    print()
    
    # 测试 2: 调用 get_model_list 函数
    print("调用 get_model_list():")
    try:
        result = await get_model_list()
        
        print(f"返回类型: {type(result)}")
        print(f"返回值:")
        print(f"  模型数量: {len(result.models)}")
        
        for i, model in enumerate(result.models, 1):
            print(f"  第 {i} 个模型:")
            print(f"    id: {model.id}")
            print(f"    provider: {model.provider}")
            print(f"    model: {model.model}")
            print(f"    display_name: {model.display_name}")
            print(f"    current_model: {model.current_model}")
            print()
        
        print(f"默认提供商: {result.default_provider}")
        
        print()
        
        # 统计 current_model == True 的模型数量
        current_models = [m for m in result.models if m.current_model]
        print(f"当前使用的模型数量: {len(current_models)}")
        
        if current_models:
            print("当前使用的模型:")
            for model in current_models:
                print(f"  - {model.display_name}")
        else:
            print("没有找到当前使用的模型!")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

asyncio.run(test_model_list())