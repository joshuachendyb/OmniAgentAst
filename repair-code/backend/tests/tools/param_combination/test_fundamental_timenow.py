# -*- coding: utf-8 -*-
"""time_now参数组合测试 - 小欧 2026-07-04 — 小欧 2026-07-06 data已清空，仅验证summary"""

import time
import pytest
from app.tools.tool_response import is_success, is_error


class TestTimeNowNormal:
    """正常调用"""

    def test_no_params(self, temp_output_dir):
        from app.tools.fundamental.time_now import timenow
        result = timenow()
        assert is_success(result)
        assert result["data"] == {}
        assert "当前时间" in result["llm_data"]["summary"]

    def test_multiple_calls_consistent(self, temp_output_dir):
        from app.tools.fundamental.time_now import timenow
        r1 = timenow()
        time.sleep(0.01)
        r2 = timenow()
        assert "当前时间" in r1["llm_data"]["summary"]
        assert "当前时间" in r2["llm_data"]["summary"]


class TestTimeNowError:
    """错误参数"""

    def test_no_args_passed(self, temp_output_dir):
        from app.tools.fundamental.time_now import timenow
        result = timenow()
        assert is_success(result)

    def test_extra_arg_rejected(self):
        from app.tools.fundamental.time_now import timenow
        with pytest.raises(TypeError):
            timenow(format="%Y-%m-%d")
