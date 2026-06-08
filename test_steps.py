#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试所有Step类的to_dict方法 - 小沈 2026-06-08"""
import sys
sys.path.insert(0, 'backend')

from app.services.agent.steps import ThoughtStep, ActionToolStep, ObservationStep, FinalStep, ErrorStep, ChunkStep
import json

def test_step(step_class, name, **kwargs):
    try:
        step = step_class(**kwargs)
        result = step.to_dict()
        print(f"✅ {name}: {json.dumps(result, ensure_ascii=False)[:100]}")
        return True
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

print("=" * 60)
print("测试所有Step类的to_dict方法")
print("=" * 60)

results = []

# 测试ThoughtStep
results.append(test_step(ThoughtStep, "ThoughtStep", step=1, content='test', thought='test', reasoning='test'))

# 测试ActionToolStep
results.append(test_step(ActionToolStep, "ActionToolStep", step=2, tool_name='test_tool', tool_params={'a': 1}))

# 测试ObservationStep
results.append(test_step(ObservationStep, "ObservationStep", step=3, observation='test', tool_name='test_tool', tool_params={'a': 1}))

# 测试FinalStep
results.append(test_step(FinalStep, "FinalStep", step=4, response='test', thought='test'))

# 测试ErrorStep
results.append(test_step(ErrorStep, "ErrorStep", step=5, error_type='test', error_message='test'))

# 测试ChunkStep
results.append(test_step(ChunkStep, "ChunkStep", step=6, content='test'))

print("=" * 60)
print(f"总计: {sum(results)}/{len(results)} 通过")
print("=" * 60)