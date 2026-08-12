# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A1 后半面 tools/security 包(A1 盲点四/五定案)。
#   path_safe_check.py + temp_auth.py 由 app/safety 整体迁移(P6 复制, 逻辑零改动, 仅改 import 路径);
#   safety_result.py 由 tool_safety_checker.py 复制 SafetyResult dataclass(供 tools 层 Shell 风险检查与 safety 层 checker 共享)。
"""
tools/security — 工具层安全能力包(A1 迁入)

归属(4.1.7 定案, 小欧 2026-08-12):
  - path_safe_check.py: 工具参数层面的路径安全校验(工具层内部闭环, 依赖 tool_registry 合法);
  - temp_auth.py: 白名单外路径临时授权(ContextVar, task 绑定);
  - safety_result.py: 安全检查结果 dataclass(协议数据契约)。

依赖方向: 仅依赖 app.tools.* / app.config / app.logger / stdlib, 无 app.safety / app.services 残留。
"""
