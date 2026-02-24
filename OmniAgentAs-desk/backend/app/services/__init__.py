"""
AI服务工厂
根据配置创建通用AI服务实例 - 支持无限provider

配置验证：
1. 配置文件是否存在
2. provider 配置是否存在
3. 必要字段是否存在（api_key, model, api_base）
4. 验证结果上报前端显示

================================================================================
【重要！统一Fallback逻辑 - 所有代码编写人员必须遵守！】

逻辑规则：
1. 只有当 ai.provider 存在 且 ai.model 存在 且 ai.model 在 ai.provider 的 models 列表中
   时，才使用 ai.provider + ai.model
2. 否则（任何一个条件不满足：ai.provider不存在/ai.model不存在/ai.model不在列表中）
   统一fallback到：模型列表的第一个 模型provider+model
3. 禁止有"当前provider"的概念和理解，容易引起逻辑错误
4. 所有相关代码必须按照此逻辑实现，不能再次犯错误！
================================================================================

================================================================================
【绝对禁止！硬编码Provider名称 - 所有代码编写人员必须遵守！】

禁止事项：
1. 绝对禁止在代码中硬编码具体的provider名称（如"zhipuai"、"opencode"、"longcat"等）
2. 所有provider必须从配置文件中动态遍历，不能写死
3. 配置文件里有什么provider，代码就处理什么provider
4. 这是通用程序，不是只给这几个provider用的！

正确做法：
ai_config = config.get('ai', {})
for provider_name in ai_config.keys():
    if provider_name == 'provider' or provider_name == 'model':
        continue
    provider_data = ai_config.get(provider_name, {})
    # 处理这个provider
================================================================================

================================================================================
【变量命名规范 - 所有代码编写人员必须遵守！】

禁止事项：
1. 禁止使用单独的"provider"变量名来表示模型信息
2. 模型信息 = provider + model，两者缺一不可
3. 单独的"provider"容易引起误解，让人以为只是处理provider
4. 涉及模型的变量名必须明确表示是模型信息

正确命名：
- final_provider, final_model  - 分别表示provider和model
- fallback_provider, fallback_model  - 分别表示fallback的provider和model
- current_provider, current_model  - 分别表示当前的provider和model

错误命名（禁止）：
- current_provider  - 单独用，容易误解为只是provider
- fallback_provider  - 单独用，容易误解
================================================================================
"""

import os
import re
import asyncio
import threading
from dataclasses import dataclass
from typing import Optional

import yaml

from .base import BaseAIService


# 支持的provider列表（动态从配置文件读取，不硬编码）
# 不再硬编码provider列表，配置文件里有什么就支持什么


@dataclass
class ConfigValidationResult:
    """配置验证结果"""
    success: bool
    provider: str
    model: str
    message: str
    errors: list  # 错误列表，用于前端显示
    warnings: list  # 警告列表


class AIServiceFactory:
    """AI服务工厂 - 一个通用类支持所有OpenAI兼容API"""
    
    _instance: Optional[BaseAIService] = None
    _current_provider: str = ""
    _config: Optional[dict] = None
    _lock: threading.Lock = threading.Lock()
    
    @classmethod
    def get_config_path(cls, config_path: Optional[str] = None) -> str:
        """获取配置文件路径"""
        if config_path is not None:
            return config_path
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        return os.path.join(base_dir, "config", "config.yaml")
    
    @classmethod
    def _get_fallback_provider_and_model(cls, ai_config: dict) -> tuple[str, str]:
        """
        获取 fallback 的 provider 和 model（统一 Fallback 逻辑）
        
        Args:
            ai_config: ai 配置字典
            
        Returns:
            tuple: (fallback_provider, fallback_model)
        """
        fallback_provider = ''
        fallback_model = ''
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'models' in provider_data and provider_data['models']:
                fallback_provider = provider_name
                fallback_model = provider_data['models'][0]
                break
        return fallback_provider, fallback_model
    
    @classmethod
    def load_config(cls, config_path: Optional[str] = None) -> dict:
        """加载配置文件"""
        if cls._config is not None:
            return cls._config
            
        actual_path = cls.get_config_path(config_path)
        
        try:
            with open(actual_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
                config = loaded_config if loaded_config is not None else {}
        except Exception as e:
            print(f"[AIServiceFactory] 警告: 无法加载配置文件 {actual_path}: {e}")
            config = {
                "ai": {}
            }
        
        return config
    
    @classmethod
    def validate_config(cls, config_path: Optional[str] = None) -> ConfigValidationResult:
        """
        完整配置验证
        
        验证项：
        1. 配置文件是否存在
        2. ai 配置块是否存在
        3. provider 字段是否存在
        4. provider 配置是否存在
        5. api_key 是否存在
        6. model 是否存在
        7. api_base 是否存在
        
        Returns:
            ConfigValidationResult: 包含成功状态、错误列表、警告列表
        """
        errors = []
        warnings = []
        provider = "unknown"
        model = ""
        
        # 1. 检查配置文件是否存在
        actual_path = cls.get_config_path(config_path)
        if not os.path.exists(actual_path):
            errors.append(f"配置文件不存在: {actual_path}")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="配置文件不存在",
                errors=errors,
                warnings=warnings
            )
        
        # 2. 加载配置
        try:
            config = cls.load_config(config_path)
        except Exception as e:
            errors.append(f"配置文件加载失败: {str(e)}")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="配置文件加载失败",
                errors=errors,
                warnings=warnings
            )
        
        # 3. 检查 ai 配置块
        ai_config = config.get("ai")
        if not ai_config:
            errors.append("配置文件缺少 'ai' 配置块")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="缺少 ai 配置块",
                errors=errors,
                warnings=warnings
            )
        
        if not isinstance(ai_config, dict):
            errors.append("'ai' 配置块格式错误，应为字典类型")
            return ConfigValidationResult(
                success=False,
                provider=provider,
                model=model,
                message="ai 配置块格式错误",
                errors=errors,
                warnings=warnings
            )
        
        # ====================================================================
        # 【统一Fallback逻辑 - 必须遵守！】
        # 先找第一个有models的provider作为fallback（动态遍历，不是硬编码！）
        fallback_provider, fallback_model = cls._get_fallback_provider_and_model(ai_config)
        
        # 如果没有找到任何provider，保持空值
        # 不再硬编码默认provider，让配置文件完全控制
        # ====================================================================
        
        # 4. 检查 provider 字段是否存在
        selected_provider = ai_config.get("provider")
        if not selected_provider:
            errors.append("ai.provider 字段为空，请在配置文件中设置 ai.provider")
            return ConfigValidationResult(
                success=False,
                provider=fallback_provider if fallback_provider else "unknown",
                model=fallback_model,
                message="ai.provider 未设置",
                errors=errors,
                warnings=warnings
            )
        
        # 5. 检查 model 字段是否存在
        selected_model = ai_config.get("model")
        if not selected_model:
            errors.append("ai.model 字段为空，请在配置文件中设置 ai.model")
            return ConfigValidationResult(
                success=False,
                provider=selected_provider,
                model="",
                message="ai.model 未设置",
                errors=errors,
                warnings=warnings
            )
        
        # 6. 检查 provider 配置块是否存在
        selected_provider_config = ai_config.get(selected_provider)
        if not selected_provider_config:
            errors.append(f"ai.{selected_provider} 配置块不存在，请在配置文件中添加 ai.{selected_provider} 配置块")
            return ConfigValidationResult(
                success=False,
                provider=selected_provider,
                model=selected_model,
                message=f"ai.{selected_provider} 配置块不存在",
                errors=errors,
                warnings=warnings
            )
        
        # 7. 检查 provider 配置块格式是否正确
        if not isinstance(selected_provider_config, dict):
            errors.append(f"ai.{selected_provider} 配置格式错误，应该是字典类型（当前是 {type(selected_provider_config).__name__} 类型）")
            return ConfigValidationResult(
                success=False,
                provider=selected_provider,
                model=selected_model,
                message=f"ai.{selected_provider} 配置格式错误",
                errors=errors,
                warnings=warnings
            )
        
        # 8. 检查 model 是否在 provider 的 models 列表中
        provider_models = selected_provider_config.get("models", [])
        if selected_model not in provider_models:
            available_models = ", ".join(provider_models) if provider_models else "（空）"
            errors.append(f"model '{selected_model}' 不在 ai.{selected_provider}.models 列表中。可用的 model: {available_models}")
            return ConfigValidationResult(
                success=False,
                provider=selected_provider,
                model=selected_model,
                message=f"model '{selected_model}' 无效",
                errors=errors,
                warnings=warnings
            )
        
        # 9. 确定最终使用的 provider 和 model（都验证通过了，就用选择的）
        final_provider = selected_provider
        final_model = selected_model
        
        # api_key
        api_key = selected_provider_config.get("api_key")
        if not api_key:
            errors.append(f"provider '{final_provider}' 缺少 api_key 配置")
        elif not isinstance(api_key, str) or api_key.strip() == "":
            errors.append(f"provider '{final_provider}' 的 api_key 为空")
        
        # 不再检查provider下的model，因为已经没有这个字段了
        
        # api_base
        api_base = selected_provider_config.get("api_base")
        if not api_base:
            warnings.append(f"provider '{final_provider}' 未配置 api_base，将使用默认值")
        
        # 10. 构建结果
        if errors:
            return ConfigValidationResult(
                success=False,
                provider=final_provider,
                model=final_model,
                message=f"配置验证失败: {len(errors)} 个错误",
                errors=errors,
                warnings=warnings
            )
        
        message = f"配置验证通过: provider={final_provider}, model={final_model}"
        if warnings:
            message += f" ({len(warnings)} 个警告)"
        
        return ConfigValidationResult(
            success=True,
            provider=final_provider,
            model=final_model,
            message=message,
            errors=errors,
            warnings=warnings
        )
    
    @classmethod
    def get_service(cls, config_path: Optional[str] = None) -> BaseAIService:
        """获取AI服务实例 - 带完整配置验证"""
        cls._instance = None
        
        # 先进行配置验证
        validation = cls.validate_config(config_path)
        
        if not validation.success:
            print(f"[AIServiceFactory] 配置验证失败:")
            for error in validation.errors:
                print(f"  ❌ {error}")
            for warning in validation.warnings:
                print(f"  ⚠️ {warning}")
            # 仍然创建实例，但会记录错误
            cls._current_provider = validation.provider
        else:
            print(f"[AIServiceFactory] {validation.message}")
            for warning in validation.warnings:
                print(f"  ⚠️ {warning}")
        
        with cls._lock:
            config = cls.load_config(config_path)
            ai_config = config.get("ai", {})
            
            # ====================================================================
            # 【统一Fallback逻辑 - 必须遵守！】
            # 1. 找第一个有models的provider作为fallback（动态遍历，不是硬编码！）
            fallback_provider, fallback_model = cls._get_fallback_provider_and_model(ai_config)
            
            # 如果没有找到任何provider，保持空值
            # 不再硬编码默认provider，让配置文件完全控制
            
            # 2. 检查 ai.provider 和 ai.model 是否有效
            selected_provider = ai_config.get('provider', '')
            selected_model = ai_config.get('model', '')
            
            is_valid = (
                selected_provider and 
                selected_provider in ai_config and 
                'models' in ai_config[selected_provider] and 
                selected_model and 
                selected_model in ai_config[selected_provider]['models']
            )
            
            # 3. 使用有效配置或fallback
            if is_valid:
                final_provider = selected_provider
                final_model = selected_model
            else:
                final_provider = fallback_provider
                final_model = fallback_model
            # ====================================================================
            
            cls._current_provider = final_provider
            
            print(f"[AIServiceFactory] 创建服务实例: provider={final_provider}, model={final_model}")
            
            provider_config = ai_config.get(final_provider, {})
            
            # 只有当provider配置完全不存在时才fallback
            if not provider_config:
                for key, val in ai_config.items():
                    if key != "provider" and isinstance(val, dict) and val.get("api_key"):
                        print(f"[AIServiceFactory] 警告: provider={final_provider} 配置不存在，使用 {key}")
                        final_provider = key
                        provider_config = val
                        break
            
            if not provider_config:
                print(f"[AIServiceFactory] 错误: 未找到任何有效的provider配置")
                provider_config = {}
            
            cls._instance = BaseAIService(
                api_key=provider_config.get("api_key", ""),
                model=final_model,
                api_base=provider_config.get("api_base", "https://api.openai.com/v1"),
                provider=final_provider,  # 新增：传递provider
                timeout=provider_config.get("timeout", 30)
            )
        
        return cls._instance
    
    @classmethod
    def switch_provider(cls, provider: str, config_path: Optional[str] = None):
        """切换AI提供商"""
        print(f"[AIServiceFactory] 切换提供商: {provider}")
        
        with cls._lock:
            old_provider = cls._current_provider
            
            if cls._instance is not None:
                try:
                    asyncio.create_task(cls._instance.close())
                except Exception as e:
                    print(f"[AIServiceFactory] 关闭旧实例出错: {e}")
            
            cls._instance = None
            cls._current_provider = provider
            
            actual_path = cls.get_config_path(config_path)
            try:
                with open(actual_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                pattern = r'(ai:\s*\n[^#]*provider:\s*["\']?)(\w+)(["\']?)'
                match = re.search(pattern, content)
                if match:
                    new_content = content[:match.start(2)] + provider + content[match.end(2):]
                else:
                    new_content = re.sub(r'(provider:\s*["\']?)(\w+)(["\']?)', rf'\g<1>{provider}\g<3>', content, count=1)
                
                with open(actual_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
            except Exception as e:
                print(f"[AIServiceFactory] 警告: 无法更新配置文件: {e}")
        
        try:
            new_service = cls.get_service(config_path)
            print(f"[AIServiceFactory] 新实例创建成功: {provider}")
            return new_service
        except Exception as e:
            print(f"[AIServiceFactory] 创建新实例失败，回滚到旧提供商: {old_provider}")
            with cls._lock:
                cls._current_provider = old_provider
                cls._instance = None
            raise e
    
    @classmethod
    def get_current_provider(cls) -> str:
        """获取当前使用的AI提供商"""
        if cls._current_provider:
            return cls._current_provider
        
        try:
            config = cls.load_config()
            return config.get("ai", {}).get("provider", "unknown")
        except:
            return "unknown"
    
    @classmethod
    def reset(cls):
        """重置工厂状态"""
        cls._instance = None
        cls._current_provider = ""
        cls._config = None
        print("[AIServiceFactory] 工厂状态已重置")
