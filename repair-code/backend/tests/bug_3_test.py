"""
测试 _trim_to_budget 中 assistant 消息在 tool 之前的重复添加 bug
"""
from app.services.agent.message_builder import MessageBuilder

mb = MessageBuilder(max_context_tokens=50000)
mb.init_history("system prompt", "user task")

# 添加足够多的消息
asst1 = {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "read"}}], "content": "let me read"}
tool1 = {"role": "tool", "tool_call_id": "call_1", "content": "Observation: file content"}
asst2 = {"role": "assistant", "content": "这是最终回答"}

mb.conversation_history.extend([tool1, asst1, asst2])

# 关键构造: assistant3 在 tool2 之在(更新), 循环从右(新)往左(旧)扫时重复添加
asst3 = {"role": "assistant", "tool_calls": [{"id": "call_2", "function": {"name": "write"}}], "content": "let me write"}
tool2 = {"role": "tool", "tool_call_id": "call_2", "content": "Observation: written ok"}

# 布局: [tool1, asst1, asst2, tool2, asst3]
# 从右扫: asst3(新) -> tool2 -> asst2 -> asst1 -> tool1(旧)
mb.conversation_history.extend([tool2, asst3])

system_msgs, user_msgs, obs_list, assistant_msgs = mb._classify_messages()
print(f"system={len(system_msgs)} user={len(user_msgs)} obs={len(obs_list)} asst={len(assistant_msgs)}")

# 用小 budget 触发裁剪
budget = 200
result = mb._trim_to_budget(obs_list, assistant_msgs, budget)
print(f"\n=== 裁剪结果 (budget={budget}) ===")
for i, m in enumerate(result):
    print(f"  [{i}] role={m.get('role')} tc_id={m.get('tool_call_id','')} tcs={bool(m.get('tool_calls'))}")

# 检查重复
ids_seen = set()
dups = 0
for m in result:
    mid = id(m)
    if mid in ids_seen:
        dups += 1
        print(f"  DUPLICATE: role={m.get('role')}")
    ids_seen.add(mid)
print(f"重复消息数: {dups}")

assert dups == 0, f"发现 {dups} 条重复消息"
print("=> PASS: 无重复")