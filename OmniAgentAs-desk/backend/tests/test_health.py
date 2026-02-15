"""
阶段1.1 测试 - 简化版
由于依赖兼容性问题，使用简化测试
"""

def test_imports():
    """TC001: 测试所有模块可以正常导入"""
    import sys
    import os
    
    # 添加backend到路径
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # 测试导入
    from app.main import app
    from app.api.v1.health import router
    
    assert app is not None
    assert router is not None

def test_fastapi_config():
    """TC002: 测试FastAPI配置正确"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app.main import app
    
    assert app.title == "OmniAgentAst API"
    assert app.version == "0.1.0"

def test_routes_exist():
    """TC003: 测试路由存在"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app.main import app
    
    routes = [route.path for route in app.routes]
    
    # 检查关键路由
    assert "/" in routes or "" in routes
    assert "/api/v1/health" in routes
    assert "/api/v1/echo" in routes

def test_cors_middleware():
    """TC004: 测试CORS中间件配置"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app.main import app
    
    # 检查中间件
    middleware_str = str(app.user_middleware)
    assert "CORSMiddleware" in middleware_str

def test_health_endpoint_structure():
    """TC005: 测试健康检查端点结构"""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app.api.v1.health import router
    
    # 检查路由有端点
    routes = [route.path for route in router.routes]
    assert "/health" in routes

def test_project_structure():
    """TC006: 测试项目文件结构完整"""
    import os
    
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    required_files = [
        "app/main.py",
        "app/api/v1/health.py",
        "requirements.txt",
        "tests/test_health.py",
    ]
    
    for file in required_files:
        full_path = os.path.join(base_path, file)
        assert os.path.exists(full_path), f"Missing file: {file}"
