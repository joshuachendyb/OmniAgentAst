"""兼容旧导入路径：app.api.v1.chat。"""

from app.api.v1.intent_detector import detect_file_operation_intent

__all__ = ["detect_file_operation_intent"]
