"""
CRSS评分器数据定义：动作兼容矩阵 — 从crss_scorer.py提取 小健2026-05-31
"""
from app.services.tools.tool_types import ToolCategory

ACTION_DEFINITIONS = {
    "read": {
        "keywords": ['cat', 'ls', 'type', 'dir', '读取', '查看', '列出', '打开'],
        "compatibility": {
            ToolCategory.FILE: 1.5,
            ToolCategory.DOCUMENT: 1.2,
            ToolCategory.SYSTEM: 0.8,
            ToolCategory.NETWORK: 0.5,
            ToolCategory.DESKTOP: 0.5,
        }
    },
    "create": {
        "keywords": ['create', 'mkdir', 'touch', '新建', '创建', '新增', '添加'],
        "compatibility": {
            ToolCategory.FILE: 1.5,
            ToolCategory.DOCUMENT: 1.0,
        }
    },
    "delete": {
        "keywords": ['rm', 'del', 'delete', 'remove', '删除', '清除', '移除'],
        "compatibility": {
            ToolCategory.FILE: 1.5,
            ToolCategory.DOCUMENT: 1.2,
            ToolCategory.DESKTOP: 0.5,
        }
    },
    "execute": {
        "keywords": ['run', 'exec', 'execute', '运行', '执行', '启动', '编译'],
        "compatibility": {
            ToolCategory.SYSTEM: 1.5,
        }
    },
    "query": {
        "keywords": ['select', 'query', 'search', 'find', 'grep', '查询', '搜索', '查找'],
        "compatibility": {
            ToolCategory.DOCUMENT: 1.5,
            ToolCategory.SYSTEM: 1.0,
            ToolCategory.FILE: 1.0,
        }
    },
    "navigate": {
        "keywords": ['open', 'launch', 'start', '打开', '启动', '进入'],
        "compatibility": {
            ToolCategory.DESKTOP: 1.5,
            ToolCategory.FILE: 1.0,
            ToolCategory.NETWORK: 0.8,
        }
    },
    "configure": {
        "keywords": ['set', 'config', 'change', '修改', '设置', '配置', '调整'],
        "compatibility": {
            ToolCategory.SYSTEM: 1.2,
            ToolCategory.DESKTOP: 1.0,
            ToolCategory.NETWORK: 1.0,
        }
    },
    "capture": {
        "keywords": ['screenshot', 'capture', '截图', '录屏', '拍照'],
        "compatibility": {
            ToolCategory.DESKTOP: 1.5,
        }
    },
}
