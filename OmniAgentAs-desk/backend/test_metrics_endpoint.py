#!/usr/bin/env python3
"""
测试监控指标端点
"""
import asyncio
import httpx
import subprocess
import time
import sys
import os

async def test_metrics_endpoint():
    """启动服务器并测试/metrics端点"""
    # 切换到backend目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 启动uvicorn服务器
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", 
         "--host", "127.0.0.1", "--port", "8000", "--log-level", "error"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    print("启动服务器...")
    # 等待服务器启动
    time.sleep(3)
    
    client = httpx.AsyncClient(timeout=10.0)
    try:
        # 测试 /api/v1/metrics
        print("测试 /api/v1/metrics...")
        response = await client.get("http://127.0.0.1:8000/api/v1/metrics")
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"成功: {data.get('success', False)}")
            print(f"总指标数: {data.get('total_metrics', 0)}")
            print(f"指标摘要键: {list(data.get('metrics', {}).keys())}")
        else:
            print(f"响应内容: {response.text}")
        
        # 测试 /api/v1/metrics/health
        print("\n测试 /api/v1/metrics/health...")
        response = await client.get("http://127.0.0.1:8000/api/v1/metrics/health")
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"健康状态: {response.json().get('status', 'unknown')}")
        
        # 测试 /api/v1/metrics/raw
        print("\n测试 /api/v1/metrics/raw...")
        response = await client.get("http://127.0.0.1:8000/api/v1/metrics/raw")
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"原始指标键: {list(data.get('metrics', {}).keys())}")
            
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.aclose()
        # 停止服务器
        print("\n停止服务器...")
        proc.terminate()
        proc.wait(timeout=5)
        if proc.poll() is None:
            proc.kill()
        print("测试完成")

if __name__ == "__main__":
    asyncio.run(test_metrics_endpoint())