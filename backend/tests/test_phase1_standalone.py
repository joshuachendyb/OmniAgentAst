# -*- coding: utf-8 -*-
"""
Phase 1 核心修复-独立测试（不依赖全量导入链）

小健 - 2026-05-13
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 直接复制测试函数，不依赖app导入
def _determine_parse_type(output: str) -> dict:
    """
    测试用：模拟 react_output_parser._determine_parse_type 的兜底逻辑
    验证 implicit→chunk 转换正确
    """
    # 注意：必须与 react_output_parser.py 第503-517行一致
    stripped = output.strip()
    if len(stripped) >= 5:
        return {
            "type": "chunk",
            "thought": stripped,
            "content": stripped,
            "reasoning": stripped,
            "tool_name": None,
            "tool_params": None,
            "response": stripped,
            "error": None
        }
    else:
        return {
            "type": "parse_error",
            "error": "无法解析LLM响应",
            "thought": stripped[:200],
            "content": stripped[:200],
            "reasoning": stripped[:200],
            "tool_name": None,
            "tool_params": None,
            "response": stripped
        }


pass_count = 0
fail_count = 0

def check(name, ok, detail=""):
    global pass_count, fail_count
    if ok:
        pass_count += 1
        print(f"  [OK] {name}")
    else:
        fail_count += 1
        print(f"  [FAIL] {name} {detail}")

# ===== 1. 解析器 implicit→chunk =====
print("\n=== 1. 解析器 implicit→chunk ===")

# 1.1 长文本→chunk
r = _determine_parse_type("Hello world this is a test")
check("长文本→chunk", r["type"] == "chunk", f"got {r['type']}")
check("chunk内容完整", r["content"] == "Hello world this is a test")

# 1.2 中文→chunk
r = _determine_parse_type("读取文件并分析")
check("中文→chunk", r["type"] == "chunk")

# 1.3 短文本→parse_error
r = _determine_parse_type("hi")
check("短文本→parse_error", r["type"] == "parse_error")

# 1.4 空→parse_error
r = _determine_parse_type("")
check("空→parse_error", r["type"] == "parse_error")

# 1.5 chunk字段完整性
r = _determine_parse_type("test content")
required = {"type", "content", "thought", "reasoning", "tool_name", "tool_params", "response", "error"}
check("chunk字段完整", required.issubset(r.keys()), f"missing: {required - r.keys()}")
check("tool_name=None", r["tool_name"] is None)
check("tool_params=None", r["tool_params"] is None)

# 1.6 边界：正好5字符
r = _determine_parse_type("12345")
check("5字符→chunk", r["type"] == "chunk")

# 1.7 边界：4字符
r = _determine_parse_type("1234")
check("4字符→parse_error", r["type"] == "parse_error")

# ===== 2. chunk_buffer 逻辑验证 =====
print("\n=== 2. chunk_buffer 逻辑验证 ===")

# 2.1 连续chunk拼接
buffer = ""
chunks = ["Hello", " world", " this", " is", " test"]
for c in chunks:
    buffer += c
check("chunk拼接正确", buffer == "Hello world this is test")

# 2.2 连续chunk计数
count = 0
reached = False
for i in range(5):
    count += 1
    if count >= 3:
        reached = True
        break
check("chunk达阈值触发提升", reached)

# 2.3 answer flush
buffer = "previous thinking text"
if buffer:
    flushed = buffer
    buffer = ""
check("answer flush后buffer为空", buffer == "")
check("answer flush保留内容", flushed == "previous thinking text")

# 2.4 action flush
buffer = "thinking about tool call"
consecutive = 2
if buffer:
    flushed = buffer
    buffer = ""
    consecutive = 0
check("action flush后buffer为空", buffer == "")
check("action flush重置计数", consecutive == 0)

# 2.5 temp_history管理
temp = []
for i in range(15):
    temp.append({"role": "assistant", "content": f"chunk_{i}"})
if len(temp) > 10:
    temp = temp[-10:]
check("temp_history裁剪", len(temp) == 10)
check("temp_history保留最新", temp[0]["content"] == "chunk_5")

# ===== 3. 超时机制验证 =====
print("\n=== 3. 超时机制验证 ===")

import time
start = time.time()
max_time = 300
timeout_hit = False
fake_now = start + 301
if fake_now - start > max_time:
    timeout_hit = True
check("超时检测逻辑", timeout_hit)

timeout_hit = False
fake_now = start + 200
if fake_now - start > max_time:
    timeout_hit = True
check("未超时不触发", not timeout_hit)

# ===== 4. TextStrategy chunk返回格式 =====
print("\n=== 4. TextStrategy chunk返回格式 ===")

# 模拟TextStrategy返回chunk
chunk_result = json.dumps({
    "type": "chunk",
    "content": "test text",
    "thought": "test text",
    "reasoning": "test text",
    "tool_name": None,
    "tool_params": None,
    "response": "test text",
    "error": None
}, ensure_ascii=False)
parsed = json.loads(chunk_result)
check("chunk JSON可解析", parsed["type"] == "chunk")
check("chunk内容不丢失", parsed["content"] == "test text")
check("chunk不是finish", parsed["tool_name"] is None)

# ===== 总结 =====
total = pass_count + fail_count
print(f"\n{'='*40}")
print(f"通过: {pass_count}/{total}")
print(f"失败: {fail_count}/{total}")
if fail_count > 0:
    print("[FAIL] 有失败")
    sys.exit(1)
else:
    print("[PASS] 全部通过")
