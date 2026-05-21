import asyncio, traceback
from app.config import AppConfig
from app.services.agent.file_react import FileReactAgent
from app.models.file_operations.schema import FileSession

async def test():
    config = AppConfig()
    agent = FileReactAgent(config=config, task_id="test123")
    
    async for event in agent.run_stream("查看 README.md 文件内容"):
        if event.get("type") == "error":
            print(f"ERROR: {event}")
            traceback.print_exc()

asyncio.run(test())
