
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-25 - 小欧 - description去冗余: 移除与类型声明重复的必填/可选/默认描述(5处)
# 2026-07-30 - 小沈 - ToolSearchInput: 新增类docstring(含分类列表示例), query description从"工具名称类型的关键词"改为"备用工具的关键词", 与注册端/prompt端语义对齐
# 2026-07-31 - 小欧 - ShellInput: 新增Windows命令弃用提醒(wmic/w32tm), command description补充弃用命令注意事项
"""
FUNDAMENTAL Schema - 基础工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容

示例：query_calendar有多个使用方式，适合添加docstring说明
"""
# Merged schema - 小欧 2026-06-18

from pydantic import BaseModel, Field
from typing import Optional, Literal

class ToolSearchInput(BaseModel):
    """当前工具列表缺少可用工具,搜索备用工具并注入工具列表, 关键词为工具或者类型的名称 
- 数据分析→搜"数据分析 图表"
- 数据库→搜"数据库 SQL"
- 网络→搜"网络 搜索 http"
- 系统→搜"系统 进程 注册表 任务"
- 桌面→搜"桌面 窗口"
- 时间- 搜"时间 定时"
- 文档- 搜"文档读写"
"""
    query: str = Field(..., description="备用工具的关键词，1-3个词即可")


class TimeNowInput(BaseModel):
    pass


class SendNotificationInput(BaseModel):
    title: str = Field(
        ..., description="通知标题"
    )
    message: str = Field(
        ..., description="通知正文"
    )
    duration: int = Field(
        default=5,
        description="通知显示时长(秒)"
    )


class GetSystemInfoInput(BaseModel):
    info_type: Optional[Literal["basic", "cpu", "memory", "disk", "network", "all"]] = Field(
        default="all",
        description="系统信息类型:basic(基础)/cpu/内存/磁盘/网络/all(全部)"
    )


class ShellInput(BaseModel):
    """Shell命令执行 - 语法翻译、安全检查、编码处理

    【语法注意事项-ps7/ps5】
    - ps7: 原生支持 && 和 || 链式操作
    - ps5: 不支持 &&/||, 引擎自动翻译: &&→; if ($?) { cmd2 }, ||→; if (-not $?) { cmd2 }
    - 管道变量用 $_.Property 形式, 注意下划线不要遗漏

    【语法注意事项-cmd】
    - 环境变量引用用 %variable% 形式;支持 && 串联多命令

    【语法注意事项-bash】
    - 路径分隔符用正斜杠/, 不是反斜杠\\
    - 环境变量引用用 $VAR 形式
    - 支持 && 和 || 串联多命令

    【Windows命令弃用提醒】
    - wmic: Windows 10/11 已弃用, 使用 Get-CimInstance 替代
    - w32tm: 如果不可用 使用 [DateTime]::Now 替代

    【安全检查】分级安全检查:
    - HIGH风险(拒绝): 递归删除、格式化、关机等
    - MEDIUM风险(警告): 其他危险命令

    【编码处理】
    - 中文命令/路径直接使用, 无需额外编码设置

    【返回值结构】
    - stdout: 标准输出内容
    - stderr: 标准错误内容
    - returncode: 退出码(0=成功)
    - shell_type: 实际使用的shell类型
    """
    command: str = Field(
        ..., description="命令字符串。多个命令用;分隔。注意:本机Python解释器命令为python,禁止使用python3。"
                         "Windows命令注意: wmic已弃用, 如果w32tm服务不可用, 推荐使用PowerShell 7 (Get-CimInstance/Get-Counter) 替代"
    )
    shell_type: Optional[Literal["ps7", "ps5", "cmd", "bash"]] = Field(
        default="ps7",
        description="命令解释器: ps7=PowerShell 7+(推荐/默认), ps5=PowerShell 5.1, cmd=cmd.exe, bash=Git Bash/WSL"
    )
    timeout: int = Field(
        default=60, ge=1, le=600, description="超时时间(秒);上限10分钟"
    )
    cwd: Optional[str] = Field(
        default=None, description="需要在特定目录下执行命令的工作目录(绝对路径).不设置则使用当前目录"
    )
    success_codes: Optional[list[int]] = Field(
        default=None,
        description="额外视为成功的退出码(0始终算成功,无需列出)。"
               "当命令用非零退出码表达业务结果(如校验工具返回1=有问题)时,"
               "在此追加如[1,2]防止被误判为执行失败。不传则只认0。"
    )


__all__ = [
    "ToolSearchInput",
    "TimeNowInput",
    "SendNotificationInput",
    "GetSystemInfoInput",
    "ShellInput",
]

