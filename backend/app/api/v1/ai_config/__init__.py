"""routes子模块包 - 配置管理API"""
from fastapi import APIRouter

router = APIRouter()

# 导出路由
from .get_system_config import get_system_config
from .update_config import update_config
from .validate_config import validate_config
from .get_model_list import get_model_list
from .get_full_config import get_full_config
from .delete_provider import delete_provider
from .delete_model import delete_model
from .update_model import update_model
from .update_provider import update_provider
from .add_model import add_model
from .add_provider import add_provider
from .fix_config import fix_config
from .get_config_path import get_config_path
from .open_config_folder import open_config_folder
from .read_config_file import read_config_file

# 导出模型
from .models import (
    SecurityConfig, ConfigUpdate, ConfigResponse,
    ConfigValidateRequest, ConfigValidateResponse,
    ModelInfo, ModelListResponse,
    ProviderInfo, FullConfigResponse, ProviderUpdate,
    ModelAddRequest, ProviderAddRequest,
    ConfigFixResponse, FullConfigValidationResponse, ConfigPathResponse,
)
