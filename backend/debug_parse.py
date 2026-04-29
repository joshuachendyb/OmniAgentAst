from app.services.agent.react_output_parser import parse_react_response

# 从日志中提取的LLM原始返回
llm_response = '''{"content": "任务1已完成：查看了E盘下载目录，有12个项目（各种文件）。现在需要创建新目录并写入10章的秋天爱情故事小说。由于系统没有独立的创建目录工具，我将通过写入小说文件来创建新目录结构。现在开始创作小说内容", "tool_name": "write_file", "tool_params": {"file_path": "E:/下载目录/秋天爱情故事/第1章_枫叶红了.txt", "content": "第一章：枫叶红了\n\n秋天的午后，阳光懒懒地洒在林间小道上，金黄色的枫叶从树枝上飘落，如同翩翩起舞的蝴蝶。李梦琪站在树下，弯下腰捡起一片枫叶，仔细端详着叶脉的纹路。\n\n她是这座城市的白领，今年二十八岁，有着稳定的工作和不俗的收入，但感情世界却一直空白。今天是她的生日，原本应该是一个值得庆祝的日子，却因为公司临时加班，所有的计划都泡汤了。\n\n"也许这就是命吧。"她轻声自语道，眼中闪过一丝落寞。\n\n就在这时，一个低沉的男声从身后传来："小姐，你掉的东西。"'''


print("=== 测试完整parse_react_response ===")
result = parse_react_response(llm_response)
print(f"type: {result.get('type')}")
print(f"tool_name: {result.get('tool_name')}")
print(f"tool_params: {list(result.get('tool_params', {}).keys())}")

print(f"\n=== thought字段 ===")
thought = result.get('thought', '')
print(f"thought: {thought[:200] if thought else 'None'}...")
print(f"thought长度: {len(thought) if thought else 0}")

print(f"\n=== content字段 ===")
content = result.get('content', '')
print(f"content: {content[:200] if content else 'None'}...")
print(f"content长度: {len(content) if content else 0}")

print(f"\n=== reasoning字段 ===")
reasoning = result.get('reasoning', '')
print(f"reasoning: {reasoning[:200] if reasoning else 'None'}...")