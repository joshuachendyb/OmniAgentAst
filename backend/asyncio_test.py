import asyncio
import time

print("=" * 60)
print("Python asyncio 异步编程验证测试")
print("=" * 60)

# ============================
# 测试1：基本协程
# ============================
print("
>>> 测试1: 基本协程")
async def say_hello():
    print("[1] Hello")
    await asyncio.sleep(1)
    print("[1] World")

asyncio.run(say_hello())

# ============================
# 测试2：并发执行多个任务
# ============================
print("
>>> 测试2: 并发执行多个任务 (gather)")

async def task1():
    print("[2] Task 1 started")
    await asyncio.sleep(1)
    print("[2] Task 1 finished")
    return "Task 1 result"

async def task2():
    print("[2] Task 2 started")
    await asyncio.sleep(2)
    print("[2] Task 2 finished")
    return "Task 2 result"

async def task3():
    print("[2] Task 3 started")
    await asyncio.sleep(1.5)
    print("[2] Task 3 finished")
    return "Task 3 result"

start_time = time.time()
results = asyncio.run(asyncio.gather(task1(), task2(), task3()))
elapsed = time.time() - start_time
print(f"
  结果: {results}")
print(f"  总耗时: {elapsed:.2f} 秒 (理论上应约2秒，而非5秒)")

# ============================
# 测试3：超时控制
# ============================
print("
>>> 测试3: 超时控制")

async def long_task():
    print("[3] Long task started")
    await asyncio.sleep(10)
    print("[3] Long task finished")

try:
    asyncio.run(asyncio.wait_for(long_task(), timeout=2))
except asyncio.TimeoutError:
    print("  [3] Task timed out after 2 seconds!")

# ============================
# 测试4：异步队列
# ============================
print("
>>> 测试4: 异步队列")

async def producer(queue):
    for i in range(5):
        await queue.put(i)
        print(f"[4] Produced: {i}")
        await asyncio.sleep(0.1)

async def consumer(queue):
    consumed = []
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=0.5)
            consumed.append(item)
            print(f"[4] Consumed: {item}")
        except asyncio.TimeoutError:
            break
    return consumed

async def run_queue_test():
    queue = asyncio.Queue()
    consumer_task = asyncio.create_task(consumer(queue))
    await producer(queue)
    consumed = await consumer_task
    return consumed

consumed_items = asyncio.run(run_queue_test())
print(f"  总共消费: {len(consumed_items)} 个项目")

# ============================
# 测试5：同步 vs 异步性能对比
# ============================
print("
>>> 测试5: 同步 vs 异步性能对比")

def sync_fetch_simulate(url):
    print(f"  [5] Sync fetching: {url}")
    time.sleep(1)
    print(f"  [5] Sync done: {url}")
    return f"Data from {url}"

async def async_fetch_simulate(url):
    print(f"  [5] Async fetching: {url}")
    await asyncio.sleep(1)
    print(f"  [5] Async done: {url}")
    return f"Data from {url}"

# 同步版本
print("  --- 同步版本 ---")
start_sync = time.time()
sync_urls = [f"https://example.com/{i}" for i in range(1, 6)]
sync_results = [sync_fetch_simulate(url) for url in sync_urls]
sync_elapsed = time.time() - start_sync
print(f"  同步版本总耗时: {sync_elapsed:.2f} 秒")

# 异步版本
print("  --- 异步版本 ---")
start_async = time.time()
async_results = asyncio.run(asyncio.gather(*(async_fetch_simulate(url) for url in sync_urls)))
async_elapsed = time.time() - start_async
print(f"  异步版本总耗时: {async_elapsed:.2f} 秒")

# 总结
print("
" + "=" * 60)
print("📊 性能对比总结")
print("=" * 60)
print(f"  同步版本耗时: {sync_elapsed:.2f} 秒")
print(f"  异步版本耗时: {async_elapsed:.2f} 秒")
speedup = sync_elapsed / async_elapsed if async_elapsed > 0 else float('inf')
print(f"  加速比: {speedup:.2f}x")
print(f"  节省时间: {sync_elapsed - async_elapsed:.2f} 秒")
print("=" * 60)
print("✅ 所有测试完成!")
