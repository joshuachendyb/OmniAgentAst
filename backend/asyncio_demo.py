import asyncio
import time

print("=" * 60)
print("示例1: 基础asyncio协程")
print("=" * 60)

async def fetch_data(url, delay):
    print(f"[{time.strftime('%H:%M:%S')}] 开始获取 {url}")
    await asyncio.sleep(delay)
    print(f"[{time.strftime('%H:%M:%S')}] 完成获取 {url}")
    return f"{url} 的数据"

async def basic_example():
    result = await fetch_data("https://example.com/api", 1)
    print(f"结果: {result}")

asyncio.run(basic_example())

print()
print("=" * 60)
print("示例2: asyncio.gather 并发执行")
print("=" * 60)

async def concurrent_example():
    start = time.time()
    tasks = [
        fetch_data("https://api.github.com", 1),
        fetch_data("https://api.python.org", 2),
        fetch_data("https://api.docs.python.org", 0.5),
    ]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    print(f"并发执行总耗时: {elapsed:.2f}秒")
    print(f"结果: {results}")

asyncio.run(concurrent_example())

print()
print("=" * 60)
print("示例3: 异步上下文管理器")
print("=" * 60)

class AsyncConnection:
    def __init__(self, name):
        self.name = name
    async def __aenter__(self):
        print(f"[{time.strftime('%H:%M:%S')}] 连接 {self.name}")
        await asyncio.sleep(0.3)
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        print(f"[{time.strftime('%H:%M:%S')}] 关闭 {self.name}")
        await asyncio.sleep(0.1)
        return False

async def context_manager_example():
    async with AsyncConnection("DB-Pool-1") as conn:
        print(f"正在使用连接: {conn.name}")
        await asyncio.sleep(0.2)
        print("查询完成")

asyncio.run(context_manager_example())

print()
print("=" * 60)
print("示例4: 优雅取消任务")
print("=" * 60)

async def cancellable_task(task_name):
    try:
        for i in range(5):
            print(f"[{task_name}] 进行中... ({i+1}/5)")
            await asyncio.sleep(0.3)
    except asyncio.CancelledError:
        print(f"[{task_name}] 收到取消信号，正在清理资源...")
        raise

async def cancellation_example():
    task = asyncio.create_task(cancellable_task("Worker-A"))
    await asyncio.sleep(1)
    print(f"[{time.strftime('%H:%M:%S')}] 正在取消 Worker-A...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        print("Worker-A 已取消")

asyncio.run(cancellation_example())

print()
print("=" * 60)
print("示例5: asyncio.TaskGroup")
print("=" * 60)

async def task_group_example():
    async def worker(name, delay):
        print(f"[Worker-{name}] 开始工作，耗时{delay}秒")
        await asyncio.sleep(delay)
        print(f"[Worker-{name}] 完成")
        return f"Worker-{name} 完成"
    async with asyncio.TaskGroup() as tg:
        t1 = tg.create_task(worker("A", 0.5))
        t2 = tg.create_task(worker("B", 0.8))
        t3 = tg.create_task(worker("C", 0.3))
    print("所有任务完成!")

asyncio.run(task_group_example())

print()
print("=" * 60)
print("所有示例执行完毕!")
print("=" * 60)