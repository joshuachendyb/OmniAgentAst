"""
测试步骤13：_check_and_load_missing_tools方法
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_base_react_has_method():
    """测试base_react.py有_check_and_load_missing_tools方法"""
    try:
        with open("app/services/agent/base_react.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查是否有这个方法
        assert "_check_and_load_missing_tools(" in content, "应该有_check_and_load_missing_tools方法"
        assert "async def _check_and_load_missing_tools(" in content, "应该是async方法"
        
        # 检查是否有否定词检测
        assert "_should_trigger_dynamic_load(" in content, "应该有_should_trigger_dynamic_load方法"
        assert "negation_words" in content, "应该有否定词列表"
        
        # 检查是否有LLM判断
        assert "_intent_classifier" in content, "应该有意分类器"
        assert "classify(" in content, "应该调用classify方法"
        
        # 检查是否有关键词检测
        assert "trigger_keywords" in content, "应该有trigger_keywords字典"
        assert "any(kw in observation" in content, "应该有关键词检测逻辑"
        
        print("✅ test_base_react_has_method passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_base_react_run_stream_integration():
    """测试run_stream中调用了_check_and_load_missing_tools"""
    try:
        with open("app/services/agent/base_react.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 检查run_stream中是否调用了_check_and_load_missing_tools
        # 找到run_stream方法
        lines = content.split('\n')
        in_run_stream = False
        found_call = False
        
        for line in lines:
            if 'async def run_stream(' in line:
                in_run_stream = True
            if in_run_stream:
                if '_check_and_load_missing_tools(' in line:
                    found_call = True
                    break
                if line.strip() == '' and in_run_stream:
                    # 可能方法结束了
                    pass
        
        assert found_call, "run_stream应该调用_check_and_load_missing_tools"
        
        print("✅ test_base_react_run_stream_integration passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


def test_negation_words():
    """测试否定词列表是否正确"""
    try:
        with open("app/services/agent/base_react.py", "r", encoding="utf-8") as f:
            content = f.read()
        
        # 找到_should_trigger_dynamic_load方法
        lines = content.split('\n')
        in_method = False
        negation_found = False
        
        for line in lines:
            if '_should_trigger_dynamic_load(' in line:
                in_method = True
            if in_method:
                if 'negation_words' in line:
                    negation_found = True
                    # 检查是否包含关键否定词
                    assert '"不要"' in content, "应该包含'不要'"
                    assert '"不能"' in content, "应该包含'不能'"
                    assert '"not to"' in content, "应该包含'not to'"
                    break
                if line.strip().startswith('def ') and in_method:
                    break
        
        assert negation_found, "应该包含否定词列表"
        
        print("✅ test_negation_words passed")
        return True
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False


if __name__ == "__main__":
    r1 = test_base_react_has_method()
    r2 = test_base_react_run_stream_integration()
    r3 = test_negation_words()
    
    if all([r1, r2, r3]):
        print("\n✅ 所有步骤13测试通过!")
    else:
        print("\n❌ 有测试失败")
