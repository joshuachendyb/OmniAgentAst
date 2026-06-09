# -*- coding: utf-8 -*-
"""
SessionUpdate — 从 sessions.py 拷出

拷贝来源: sessions.py 第174-178行
"""

from typing import Optional
from pydantic import BaseModel, Field


class SessionUpdate(BaseModel):
    """拷贝自 sessions.py 第174-178行"""
    title: Optional[str] = Field(None, description="会话标题", min_length=1, max_length=200)
    version: Optional[int] = Field(None, ge=1, description="乐观锁版本号")
    updated_by: Optional[str] = Field(None, description="修改者")
