#!/usr/bin/env python3
"""
测试日志格式和配置
小健测试用
"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.logger import logger


def test_logger():
    """测试日志输出格式"""
    print("=" * 80)
    print("日志功能测试")
    print("=" * 80)
    
    # 测试各级别日志
    logger.debug("这是 DEBUG 级别的日志")
    logger.info("这是 INFO 级别的日志")
    logger.warning("这是 WARNING 级别的日志")
    logger.error("这是 ERROR 级别的日志")
    
    print("\n" + "=" * 80)
    print("测试完成，请查看日志文件: backend/logs/app_YYYY-MM-DD.log")
    print("=" * 80)
    
    # 显示日志文件位置
    log_dir = Path(__file__).parent / "logs"
    if log_dir.exists():
        log_files = sorted(log_dir.glob("app_*.log"))
        if log_files:
            print(f"\n找到 {len(log_files)} 个日志文件:")
            for log_file in log_files[-3:]:  # 显示最近3个
                print(f"  - {log_file.name} ({log_file.stat().st_size} bytes)")
        else:
            print("\n日志文件不存在，请运行程序生成")
    else:
        print("\n日志目录不存在")


if __name__ == "__main__":
    test_logger()
