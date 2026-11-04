# -*- coding: utf-8 -*-
"""settings 专用 DTO（Pydantic）。

编辑历史:
  2026-09-20 - 小沈 - 新建：GET/PUT /settings 契约 DTO（5.2）
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SettingsGetResponse(BaseModel):
    groups: Dict[str, Dict[str, Dict[str, Any]]] = Field(...)
    version: str = Field("")
    mtime: float = Field(0.0)


class SchemaItem(BaseModel):
    key: str = Field(...)
    type: str = Field(...)
    label: str = Field(...)
    default: Any = Field(default=None)
    options: Optional[List[Any]] = Field(default=None)
    range: Optional[List[float]] = Field(default=None)
    step: Optional[float] = Field(default=None)
    storage: str = Field("YAML")
    restart: bool = Field(False)
    secret: bool = Field(False)
    readonly: bool = Field(False)
    notice: str = Field("")


class SchemaGroup(BaseModel):
    label: str = Field(...)
    items: List[SchemaItem] = Field(...)


class SchemaResponse(BaseModel):
    groups: Dict[str, SchemaGroup] = Field(...)


class SettingsGroupResponse(BaseModel):
    data: Dict[str, Any] = Field(...)
    sources: Dict[str, str] = Field(...)
    mtime: float = Field(0.0)


class SettingsUpdateRequest(BaseModel):
    patch: Dict[str, Any] = Field(...)


class UpdatedItem(BaseModel):
    key: str = Field(...)
    source: str = Field(...)


class SettingsUpdateResponse(BaseModel):
    ok: bool = Field(...)
    updated: List[UpdatedItem] = Field(default_factory=list)
    need_restart: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    mtime: float = Field(0.0)
