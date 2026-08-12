# -*- coding: utf-8 -*-
"""send_notification参数组合测试 - 小欧 2026-07-04

测试系统通知工具的参数组合、边界条件、特殊字符处理
"""

import pytest
from app.tools.tool_response import is_success, is_error


class TestNotifySchema:
    """Schema验证（不依赖win10toast）"""

    def test_missing_title(self):
        from app.tools.fundamental.send_notification import notify
        with pytest.raises(TypeError):
            notify(message="test")

    def test_missing_message(self):
        from app.tools.fundamental.send_notification import notify
        with pytest.raises(TypeError):
            notify(title="test")

    def test_missing_both(self):
        from app.tools.fundamental.send_notification import notify
        with pytest.raises(TypeError):
            notify()

    def test_duration_type_accepted(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="test", message="test", duration=5)
        assert is_success(result)


class TestNotifyEdgeCases:
    """边界条件"""

    def test_empty_title(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="", message="test")
        assert is_error(result)

    def test_empty_message(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="test", message="")
        assert is_error(result)

    def test_special_chars(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="Special<>Chars", message="<>&\"'!")
        assert is_success(result)

    def test_unicode_title(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="测试通知🔔", message="Unicode test")
        assert is_success(result)

    def test_long_title(self):
        from app.tools.fundamental.send_notification import notify
        long_title = "A" * 200
        result = notify(title=long_title, message="test")
        assert is_success(result)

    def test_long_message(self):
        from app.tools.fundamental.send_notification import notify
        long_msg = "B" * 500
        result = notify(title="test", message=long_msg)
        assert is_success(result)

    def test_duration_zero(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="test", message="test", duration=0)
        assert is_success(result)

    def test_duration_large(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="test", message="test", duration=3600)
        assert is_success(result)

    def test_return_structure(self):
        from app.tools.fundamental.send_notification import notify
        result = notify(title="test", message="test", duration=5)
        assert is_success(result)
        data = result["data"]
        assert data == {}
