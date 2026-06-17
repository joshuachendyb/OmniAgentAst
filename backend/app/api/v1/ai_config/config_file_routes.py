# -*- coding: utf-8 -*-
"""配置文件轻量路由: path/read/open-folder — 小健 2026-06-17 合并3个超短文件"""
import os
import subprocess

from . import router
from .models import ConfigPathResponse
from ._helpers import get_config_path, handle_config_errors
from fastapi import HTTPException
from app.utils.response_utils import api_success
from app.utils.logger import logger


@router.get("/config/path", response_model=ConfigPathResponse)
@handle_config_errors("获取配置路径")
async def get_config_path_endpoint():
    config_path = get_config_path()
    return ConfigPathResponse(
        config_path=str(config_path),
        config_dir=str(config_path.parent),
        exists=config_path.exists(),
    )


@router.get("/config/read")
@handle_config_errors("读取配置文件")
async def read_config_file():
    config_path = get_config_path()
    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"配置文件不存在: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    return {"config_content": content}


@router.post("/config/open-folder")
@handle_config_errors("打开配置目录")
async def open_config_folder():
    config_path = get_config_path()
    config_dir = str(config_path.parent)
    if not os.path.exists(config_dir):
        raise HTTPException(status_code=404, detail=f"配置目录不存在: {config_dir}")
    subprocess.Popen(
        ["explorer", "/e,", config_dir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    logger.info(f"已打开配置目录: {config_dir}")
    return api_success(path=config_dir)