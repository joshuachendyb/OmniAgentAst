# tests/validate/test_timeout_validator.py
# 小欧矆 2026-06-27

import pytest
from app.tools.validate.timeout_validator import validate_timeout, TIMEOUT_RANGES_SECONDS


class TestValidateTimeout:
    """validate_timeout() full coverage test"""

    # 鈹查鈹查 闆?璐因查?鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    @pytest.mark.parametrize("bad_timeout", [0, -1, -100])
    def test_zero_or_negative(self, bad_timeout):
        is_valid, msg, _ = validate_timeout(bad_timeout, "httpget")
        assert is_valid is False
        assert "timeout\u5fc5\u987b\u4e3a\u6b63\u6574\u6570\uff08\u79d2\uff09\uff0c\u6536\u5230" in msg

    # 钄查钄查 非炴暣整锛?钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查钄查
    @pytest.mark.parametrize("non_int", [1.5, 3.0, "30", None, [], {}])
    def test_non_integer(self, non_int):
        is_valid, msg, _ = validate_timeout(non_int, "httpget")
        assert is_valid is False
        assert "timeout\u5fc5\u987b\u4e3a\u6b63\u6574\u6570\uff08\u79d2\uff09\uff0c\u6536\u5230" in msg

    # 鈹查鈹查 你庝簬中嬮檺 鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    def test_below_minimum(self):
        is_valid, msg, _ = validate_timeout(0, "httpget")
        assert is_valid is False
        # Below lower bound
        assert "timeout\u5fc5\u987b\u4e3a\u6b63\u6574\u6570\uff08\u79d2\uff09\uff0c\u6536\u5230" in msg

    @pytest.mark.parametrize("tool,range_", list(TIMEOUT_RANGES_SECONDS.items()))
    def test_below_min_for_each_tool(self, tool, range_):
        lo, _ = range_
        is_valid, msg, _ = validate_timeout(lo - 1, tool)
        if lo - 1 <= 0:
            assert is_valid is False
            assert "timeout\u5fc5\u987b\u4e3a\u6b63\u6574\u6570\uff08\u79d2\uff09\uff0c\u6536\u5230" in msg
        else:
            assert is_valid is False
            assert f"{tool}\u7684timeout\u4e0d\u80fd\u5c0f\u4e8e{lo}\u79d2" in msg

    # 鈹查鈹查 楂樹簬中婇檺 鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    @pytest.mark.parametrize("tool,range_", list(TIMEOUT_RANGES_SECONDS.items()))
    def test_above_max_for_each_tool(self, tool, range_):
        _lo, hi = range_
        is_valid, msg, _ = validate_timeout(hi + 1, tool)
        assert is_valid is False
        assert f"{tool}\u7684timeout\u4e0d\u80fd\u5927\u4e8e{hi}\u79d2" in msg

    # 鈹查鈹查 否堟硶鍊?鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    @pytest.mark.parametrize("tool,range_", list(TIMEOUT_RANGES_SECONDS.items()))
    def test_valid_timeout_for_each_tool(self, tool, range_):
        lo, hi = range_
        # 中嬮檺
        ok, msg, _ = validate_timeout(lo, tool)
        assert ok is True
        assert msg is None
        # 中婇檺
        ok, msg, _ = validate_timeout(hi, tool)
        assert ok is True
        assert msg is None
        # 中棿鍊?
        mid = (lo + hi) // 2
        ok, msg, _ = validate_timeout(mid, tool)
        assert ok is True
        assert msg is None

    # 鈹查鈹查 宸茬煡宸ュ叿鍏蜂綋鑼冨洿,堟樉异忛獙请侊,渚夸簬闃呰,?鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    def test_http_request_range(self):
        assert validate_timeout(1, "httpget")[0] is True
        assert validate_timeout(300, "httpget")[0] is True
        assert validate_timeout(0, "httpget")[0] is False
        assert validate_timeout(301, "httpget")[0] is False

    def test_download_file_range(self):
        assert validate_timeout(5, "download")[0] is True
        assert validate_timeout(3600, "download")[0] is True
        assert validate_timeout(4, "download")[0] is False
        assert validate_timeout(3601, "download")[0] is False

    def test_fetch_webpage_range(self):
        assert validate_timeout(1, "fetchpage")[0] is True
        assert validate_timeout(120, "fetchpage")[0] is True
        assert validate_timeout(0, "fetchpage")[0] is False
        assert validate_timeout(121, "fetchpage")[0] is False

    def test_ping_port_range(self):
        assert validate_timeout(1, "ping_port")[0] is True
        assert validate_timeout(30, "ping_port")[0] is True
        assert validate_timeout(0, "ping_port")[0] is False
        assert validate_timeout(31, "ping_port")[0] is False

    def test_execute_shell_command_range(self):
        assert validate_timeout(1, "shell")[0] is True
        assert validate_timeout(600, "shell")[0] is True
        assert validate_timeout(0, "shell")[0] is False
        assert validate_timeout(601, "shell")[0] is False

    # execute_code removed in refactoring -- 小欧 2026-07-05

    # 鈹查鈹查 未煡宸ュ叿否?鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查鈹查
    def test_unknown_tool_name(self):
        assert validate_timeout(9999, "non_existent_tool") == (True, None, None)
        assert validate_timeout(0, "non_existent_tool")[0] is False  # 件死牎验我整存暟
