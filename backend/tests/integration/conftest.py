"""
集成测试框架 - conftest
小健 2026-05-21
"""
import pytest
from tests.integration._helper import ToolClient, TEMP_DIR


@pytest.fixture(scope="session")
def tool():
    return ToolClient()


@pytest.fixture(scope="session", autouse=True)
def check_backend_service():
    client = ToolClient()
    if not client.check_service():
        pytest.exit("后台服务未运行! 请先启动: cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000")


@pytest.fixture(autouse=True)
def test_workspace():
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    yield TEMP_DIR
