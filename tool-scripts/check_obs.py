import json

with open('D:/temp_messages.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

msgs = data.get('messages', [])
print(f"Total messages: {len(msgs)}")

obs_found = 0
for msg in msgs:
    msg_id = msg.get('id')
    steps = msg.get('execution_steps', [])
    
    for step in steps:
        if step.get('type') == 'observation':
            obs_found += 1
            print(f"\n{'='*60}")
            print(f"message_id: {msg_id}")
            print(f"step: {step.get('step')}")
            print(f"Fields: {list(step.keys())}")
            print(f"\nFull step data:")
            print(json.dumps(step, indent=2, ensure_ascii=False))
            if obs_found >= 3:
                print("\n... (showing first 3 observations)")
                break
    if obs_found >= 3:
        break
