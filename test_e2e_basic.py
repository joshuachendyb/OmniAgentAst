#!/usr/bin/env python3
"""基础E2E测试执行器 - 按照测试手册要求执行P0测试"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加backend目录到Python路径
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from e2emodel.e2e_helpers import (
    ensure_backend_ready, send_chat, check_db,
    verify_consistency, verify_steps, check_logs,
    print_report, write_test_record,
    get_security_enabled, set_security_enabled,
    assert_stream_ended,
)

async def run_e2e_test():
    """运行基础E2E测试"""
    print("=" * 60)
    print("OmniAgentAs-desk 基础E2E测试执行器")
    print("=" * 60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 检查后端状态
    print("检查后端服务状态...")
    if not ensure_backend_ready():
        print("❌ 错误: 后端服务未启动或不可用")
        print("   请先启动后端服务: python -m uvicorn backend/app/main:app --reload")
        return False
    
    print("✅ 后端服务可用")
    print()
    
    try:
        # P0-01: 核心链路验证 - 自我介绍
        print("🚀 开始执行 P0-01: 核心链路验证 - 自我介绍")
        print("-" * 60)
        
        orig_security = get_security_enabled()
        set_security_enabled(False)
        
        passed = False
        r = None
        sid = None
        db = {}
        ci = []
        si = []
        lc = {"errors": [], "tracebacks": []}
        elapsed = 0.0
        error_info = None
        
        user_input = "详细介绍一下你自己，你能做什么"
        print(f"用户输入: {user_input}")
        
        result = await send_chat(user_input)
        sid = result["session_id"]
        elapsed = result["total_time_ms"] / 1000.0
        r = result
        
        print(f"SSE事件: {result['total_steps']} events, {result['logical_step_count']} logical steps")
        print(f"流结束类型: {assert_stream_ended(result)}")
        print(f"是否出错: {result['has_error']}")
        
        # L1 MUST层验证
        assert result["total_steps"] >= 2, f"至少start+final(MUST), got {result['total_steps']}"
        assert result["unique_step_numbers"] < 50, f"疑似死循环: {result['unique_step_numbers']}步(MUST)"
        
        # L2 SHOULD层验证
        resp = result["response_text"]
        assert len(resp) > 10, f"回复太短({len(resp)}字)(SHOULD)"
        key_terms = ["助手", "AI", "可以", "能够", "帮助"]
        assert any(t in resp for t in key_terms), "回复与自我介绍无关(SHOULD)"
        
        # 数据库验证
        db = check_db(sid)
        assert db["session_exists"], "session必须保存到DB(MUST)"
        assert db["is_valid"], f"is_valid必须为true(MUST), got {db['is_valid']}"
        assert db["has_user_message"], "必须有user消息(MUST)"
        assert db["has_assistant_message"], "必须有assistant消息(MUST)"
        assert db["message_order_correct"], "消息顺序必须user在前(MUST)"
        assert len(db["step_field_issues"]) == 0, f"step字段不完整(MUST): {db['step_field_issues']}"
        assert len(db["time_issues"]) == 0, f"时间异常(MUST): {db['time_issues']}"
        
        # 一致性验证
        ci = verify_consistency(result, sid)
        assert len(ci) == 0, f"一致性验证失败(MUST): {ci}"
        
        # 步骤合理性验证
        si = verify_steps(result, sid)
        assert len(si) == 0, f"步骤合理性异常: {si}"
        
        # 日志检查
        lc = check_logs(datetime.now(), sid)
        assert len(lc["errors"]) == 0, f"日志不应有ERROR(MUST): {lc['errors'][:3]}"
        assert len(lc["tracebacks"]) == 0, f"日志不应有traceback(MUST)"
        assert lc["session_records_found"], "日志应有session操作记录(SHOULD)"
        
        print_report(
            "E2E-P0-01", "核心链路验证-自我介绍", result, db, lc,
            ci, si, True, elapsed,
            extra={"LLM calls": result["llm_call_count"], "SSE total": result["total_steps"]},
        )
        
        passed = True
        print(f"✅ P0-01 PASSED")
        
    except Exception as e:
        passed = False
        import traceback
        error_info = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ P0-01 FAILED: {error_info[:500]}")
        raise
        
    finally:
        if orig_security is not None:
            set_security_enabled(orig_security)
        
        if sid:
            write_test_record(
                "E2E-P0-01", "核心链路验证-自我介绍",
                user_input, r or {}, db, ci, si, lc, passed, elapsed,
                error_info=error_info,
            )
    
    print()
    print("=" * 60)
    print(f"测试完成: {'✅ PASSED' if passed else '❌ FAILED'}")
    print("=" * 60)
    
    return passed

async def main():
    """主函数"""
    try:
        success = await run_e2e_test()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ 测试被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试执行失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
