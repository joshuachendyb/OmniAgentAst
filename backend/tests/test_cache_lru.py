# -*- coding: utf-8 -*-
"""
LRUCache通用缓存深度测试
测试时间: 2026-05-30
测试人: 小健
目的: 全面验证LRUCache的功能正确性、线程安全、边界条件、异常韧性
"""

import sys
import os
import time
import threading
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.cache import LRUCache, make_cache_key
from app.utils.logger import logger


# ===========================================================================
# 一、LRUCache 基础操作测试
# ===========================================================================

def test_set_and_get():
    """测试：set后能正确get到值"""
    cache = LRUCache(max_size=100)
    cache.set("key1", "value1")
    cache.set("key2", {"a": 1})
    v1 = cache.get("key1")
    v2 = cache.get("key2")
    if v1 != "value1":
        print("FAIL: set/get string")
        return False
    if v2 != {"a": 1}:
        print("FAIL: set/get dict")
        return False
    print("PASS")
    return True


def test_get_miss():
    """测试：不存在的key返回None"""
    cache = LRUCache(max_size=100)
    v = cache.get("nonexistent")
    if v is not None:
        print("FAIL: miss should return None")
        return False
    print("PASS")
    return True


def test_set_overwrites_existing():
    """测试：相同key覆盖旧值"""
    cache = LRUCache(max_size=100)
    cache.set("k", "old")
    cache.set("k", "new")
    v = cache.get("k")
    if v != "new":
        print("FAIL: overwrite")
        return False
    print("PASS")
    return True


def test_none_value():
    """测试：存储None值能正确返回"""
    cache = LRUCache(max_size=100)
    cache.set("k", None)
    v = cache.get("k")
    if v is not None:
        print("FAIL: None value")
        return False
    print("PASS")
    return True


def test_empty_key():
    """测试：空字符串作为key"""
    cache = LRUCache(max_size=100)
    cache.set("", "empty")
    v = cache.get("")
    if v != "empty":
        print("FAIL: empty key")
        return False
    print("PASS")
    return True


def test_zero_value():
    """测试：存储0值（falsy但非None）"""
    cache = LRUCache(max_size=100)
    cache.set("k", 0)
    v = cache.get("k")
    if v != 0:
        print("FAIL: zero value")
        return False
    print("PASS")
    return True


def test_false_value():
    """测试：存储False值"""
    cache = LRUCache(max_size=100)
    cache.set("k", False)
    v = cache.get("k")
    if v is not False:
        print("FAIL: False value")
        return False
    print("PASS")
    return True


# ===========================================================================
# 二、LRU 淘汰策略测试
# ===========================================================================

def test_lru_eviction_basic():
    """测试：超过max_size时淘汰最旧的"""
    cache = LRUCache(max_size=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("d", 4)  # 应淘汰a
    if cache.get("a") is not None:
        print("FAIL: a should be evicted")
        return False
    if cache.get("b") != 2 or cache.get("c") != 3 or cache.get("d") != 4:
        print("FAIL: b/c/d should remain")
        return False
    print("PASS")
    return True


def test_lru_get_renews():
    """测试：get操作使条目变新，不被淘汰"""
    cache = LRUCache(max_size=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.get("a")  # a变新
    cache.set("d", 4)  # 应淘汰b（最旧）
    if cache.get("a") != 1:
        print("FAIL: a should remain (was renewed)")
        return False
    if cache.get("b") is not None:
        print("FAIL: b should be evicted (oldest)")
        return False
    if cache.get("c") != 3 or cache.get("d") != 4:
        print("FAIL: c/d should remain")
        return False
    print("PASS")
    return True


def test_lru_set_renews():
    """测试：set已有key使其变新"""
    cache = LRUCache(max_size=3)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    cache.set("a", 10)  # a更新+变新
    cache.set("d", 4)  # 应淘汰b
    if cache.get("a") != 10:
        print("FAIL: a should be 10")
        return False
    if cache.get("b") is not None:
        print("FAIL: b should be evicted")
        return False
    print("PASS")
    return True


def test_lru_many_items():
    """测试：大量条目下淘汰正确"""
    N = 1000
    cache = LRUCache(max_size=100)
    for i in range(N):
        cache.set(f"k{i}", i)
    # 只剩最后100个
    if cache.get("k0") is not None:
        print("FAIL: k0 should be evicted")
        return False
    if cache.get(f"k{N-1}") != N - 1:
        print("FAIL: last key should remain")
        return False
    stats = cache.get_stats()
    if stats["size"] != 100:
        print(f"FAIL: size should be 100, got {stats['size']}")
        return False
    print("PASS")
    return True


def test_max_size_one():
    """测试：max_size=1时每个set淘汰前一个"""
    cache = LRUCache(max_size=1)
    cache.set("a", 1)
    cache.set("b", 2)
    if cache.get("a") is not None:
        print("FAIL: a should be evicted (max_size=1)")
        return False
    if cache.get("b") != 2:
        print("FAIL: b should remain")
        return False
    print("PASS")
    return True


# ===========================================================================
# 三、统计信息测试
# ===========================================================================

def test_stats_initial():
    """测试：初始统计值"""
    cache = LRUCache(max_size=100)
    s = cache.get_stats()
    if s["size"] != 0 or s["hits"] != 0 or s["misses"] != 0:
        print("FAIL: initial stats should be zero")
        return False
    print("PASS")
    return True


def test_stats_hits_misses():
    """测试：hits和misses计数正确"""
    cache = LRUCache(max_size=100)
    cache.set("k", "v")
    cache.get("k")   # hit
    cache.get("k")   # hit
    cache.get("x")   # miss
    s = cache.get_stats()
    if s["hits"] != 2:
        print(f"FAIL: hits=2 expected, got {s['hits']}")
        return False
    if s["misses"] != 1:
        print(f"FAIL: misses=1 expected, got {s['misses']}")
        return False
    print("PASS")
    return True


def test_stats_size():
    """测试：size统计正确"""
    cache = LRUCache(max_size=10)
    cache.set("a", 1)
    cache.set("b", 2)
    s = cache.get_stats()
    if s["size"] != 2:
        print(f"FAIL: size=2 expected, got {s['size']}")
        return False
    print("PASS")
    return True


def test_stats_hit_rate():
    """测试：hit_rate格式正确"""
    cache = LRUCache(max_size=100)
    cache.set("k", "v")
    cache.get("k")   # 1 hit
    cache.get("x")   # 1 miss
    s = cache.get_stats()
    rate = s["hit_rate"]
    if not isinstance(rate, str) or "%" not in rate:
        print(f"FAIL: hit_rate should be string like '50.00%', got {rate!r}")
        return False
    print("PASS")
    return True


# ===========================================================================
# 四、clear 测试
# ===========================================================================

def test_clear_empty():
    """测试：空缓存clear不报错"""
    cache = LRUCache(max_size=100)
    try:
        cache.clear()
        print("PASS")
        return True
    except Exception as e:
        print(f"FAIL: clear empty raised {e}")
        return False


def test_clear_resets_all():
    """测试：clear后所有统计归零，条目清空"""
    cache = LRUCache(max_size=100)
    cache.set("k", "v")
    cache.get("k")   # 1 hit
    cache.get("x")   # 1 miss
    cache.clear()
    s = cache.get_stats()
    if s["size"] != 0 or s["hits"] != 0 or s["misses"] != 0:
        print(f"FAIL: clear should reset stats, got {s}")
        return False
    if cache.get("k") is not None:
        print("FAIL: cleared key should return None")
        return False
    print("PASS")
    return True


# ===========================================================================
# 五、线程安全测试
# ===========================================================================

def test_concurrent_set():
    """测试：多线程并发set不崩溃"""
    cache = LRUCache(max_size=100)
    errors = []
    def worker(n):
        try:
            for i in range(100):
                cache.set(f"t{n}_k{i}", i)
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=worker, args=(j,)) for j in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        print(f"FAIL: concurrent set errors: {errors}")
        return False
    print("PASS")
    return True


def test_concurrent_get():
    """测试：多线程并发get不崩溃"""
    cache = LRUCache(max_size=100)
    for i in range(50):
        cache.set(f"k{i}", i)
    errors = []
    def worker(n):
        try:
            for i in range(100):
                cache.get(f"k{i % 50}")
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=worker, args=(j,)) for j in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        print(f"FAIL: concurrent get errors: {errors}")
        return False
    print("PASS")
    return True


def test_concurrent_mixed():
    """测试：多线程混合set/get/clear"""
    cache = LRUCache(max_size=50)
    errors = []
    def worker(n):
        try:
            for i in range(200):
                if i % 5 == 0:
                    cache.clear()
                elif i % 3 == 0:
                    cache.get(f"k{i % 60}")
                else:
                    cache.set(f"k{i % 60}", i)
        except Exception as e:
            errors.append(e)
    threads = [threading.Thread(target=worker, args=(j,)) for j in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        print(f"FAIL: concurrent mixed errors: {errors}")
        return False
    print("PASS")
    return True


def test_stats_consistency_under_concurrency():
    """测试：并发下统计值不出现负数等异常"""
    cache = LRUCache(max_size=100)
    def worker():
        for _ in range(500):
            cache.set("k", "v")
            cache.get("k")
            cache.get("miss")
    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    s = cache.get_stats()
    if s["hits"] < 0 or s["misses"] < 0 or s["size"] < 0:
        print(f"FAIL: negative stats under concurrency: {s}")
        return False
    print("PASS")
    return True


# ===========================================================================
# 六、异常韧性测试
# ===========================================================================

def test_cache_resilience_bad_key():
    """测试：None作为key不导致崩溃（内部异常被吞）"""
    cache = LRUCache(max_size=100)
    try:
        cache.set(None, "v")
        # OrderedDict 接收 None key 会抛 TypeError, 内层被捕获
        v = cache.get(None)
        print("PASS (exception caught)")
        return True
    except Exception as e:
        print(f"FAIL: None key raised {e}")
        return False


def test_cache_survives_internal_error():
    """测试：内部异常后缓存仍可用"""
    cache = LRUCache(max_size=100)
    cache.set("a", 1)
    # 触发内部异常 - 传入特殊值
    cache.set(42, "int_key")  # int key也能工作
    cache.set("b", 2)
    if cache.get("a") != 1 or cache.get("b") != 2:
        print("FAIL: cache unusable after internal errors")
        return False
    print("PASS")
    return True


# ===========================================================================
# 七、make_cache_key 测试
# ===========================================================================

def test_make_cache_key_string():
    """测试：字符串生成key"""
    k = make_cache_key("hello")
    if not isinstance(k, str) or len(k) != 32:  # MD5 hex = 32 chars
        print(f"FAIL: key should be 32-char hex, got {k!r}")
        return False
    print("PASS")
    return True


def test_make_cache_key_dict():
    """测试：字典生成key（sorted keys保证一致）"""
    k1 = make_cache_key({"b": 2, "a": 1})
    k2 = make_cache_key({"a": 1, "b": 2})
    if k1 != k2:
        print(f"FAIL: dicts with same content should have same key: {k1} != {k2}")
        return False
    print("PASS")
    return True


def test_make_cache_key_deterministic():
    """测试：相同输入产生相同key"""
    data = {"name": "test", "value": 42, "nested": [1, 2, 3]}
    k1 = make_cache_key(data)
    k2 = make_cache_key(data)
    if k1 != k2:
        print("FAIL: same data should produce same key")
        return False
    print("PASS")
    return True


def test_make_cache_key_different_keys():
    """测试：不同输入产生不同key"""
    k1 = make_cache_key("hello")
    k2 = make_cache_key("world")
    if k1 == k2:
        print("FAIL: different data should produce different keys")
        return False
    print("PASS")
    return True


def test_make_cache_key_list():
    """测试：列表输入"""
    k = make_cache_key([1, 2, 3])
    if not isinstance(k, str) or len(k) != 32:
        print(f"FAIL: list key format wrong: {k!r}")
        return False
    print("PASS")
    return True


def test_make_cache_key_nested():
    """测试：嵌套结构"""
    data = {
        "level1": {
            "level2": {
                "value": 99
            }
        },
        "items": [{"id": 1}, {"id": 2}]
    }
    try:
        k = make_cache_key(data)
        if not isinstance(k, str) or len(k) != 32:
            print(f"FAIL: nested key format wrong: {k!r}")
            return False
        print("PASS")
        return True
    except Exception as e:
        print(f"FAIL: nested data raised {e}")
        return False


def test_make_cache_key_none():
    """测试：None输入"""
    try:
        k = make_cache_key(None)
        if not isinstance(k, str):
            print(f"FAIL: None key should be str, got {type(k)}")
            return False
        print("PASS")
        return True
    except Exception as e:
        print(f"FAIL: None raised {e}")
        return False


def test_make_cache_key_unserializable():
    """测试：不可序列化对象回退到id()"""
    class Unserializable:
        pass
    obj = Unserializable()
    try:
        k = make_cache_key(obj)
        if not isinstance(k, str):
            print(f"FAIL: fallback key should be str, got {type(k)}")
            return False
        print("PASS")
        return True
    except Exception as e:
        print(f"FAIL: unserializable raised {e}")
        return False


# ===========================================================================
# 八、大对象与边界测试
# ===========================================================================

def test_large_dict():
    """测试：1000个key的dict作为value"""
    cache = LRUCache(max_size=100)
    large = {f"k{i}": f"v{i}" for i in range(1000)}
    try:
        cache.set("large", large)
        v = cache.get("large")
        if v["k999"] != "v999":
            print("FAIL: large dict roundtrip")
            return False
        print("PASS")
        return True
    except Exception as e:
        print(f"FAIL: large dict raised {e}")
        return False


def test_many_operations():
    """测试：大量set/get操作不泄漏"""
    cache = LRUCache(max_size=100)
    for i in range(10000):
        cache.set(f"k{i}", i)
        cache.get(f"k{i-1}")
    stats = cache.get_stats()
    if stats["size"] > 100:
        print(f"FAIL: size exceeded max_size: {stats['size']} > 100")
        return False
    # get操作10000次，set操作不计数，所以hits+misses应≈10000
    total = stats["hits"] + stats["misses"]
    if total < 9900 or total > 10100:
        print(f"FAIL: get ops should be ~10000, got {total}: {stats}")
        return False
    print("PASS")
    return True


# ===========================================================================
# 测试调度
# ===========================================================================

ALL_TESTS = [
    ("基础操作", [
        ("set/get字符串", test_set_and_get),
        ("get不存在的key", test_get_miss),
        ("覆盖已有key", test_set_overwrites_existing),
        ("存储None值", test_none_value),
        ("空字符串key", test_empty_key),
        ("存储0值", test_zero_value),
        ("存储False值", test_false_value),
    ]),
    ("LRU淘汰策略", [
        ("基本淘汰", test_lru_eviction_basic),
        ("get刷新LRU", test_lru_get_renews),
        ("set刷新LRU", test_lru_set_renews),
        ("大量条目淘汰正确", test_lru_many_items),
        ("max_size=1", test_max_size_one),
    ]),
    ("统计信息", [
        ("初始统计", test_stats_initial),
        ("命中/未命中计数", test_stats_hits_misses),
        ("size统计", test_stats_size),
        ("命中率格式", test_stats_hit_rate),
    ]),
    ("clear操作", [
        ("清空空缓存", test_clear_empty),
        ("clear重置所有", test_clear_resets_all),
    ]),
    ("线程安全", [
        ("并发set", test_concurrent_set),
        ("并发get", test_concurrent_get),
        ("混合set/get/clear", test_concurrent_mixed),
        ("并发下统计一致性", test_stats_consistency_under_concurrency),
    ]),
    ("异常韧性", [
        ("None key不崩溃", test_cache_resilience_bad_key),
        ("内部异常后用可用", test_cache_survives_internal_error),
    ]),
    ("make_cache_key函数", [
        ("字符串输入", test_make_cache_key_string),
        ("字典sorted keys", test_make_cache_key_dict),
        ("确定性(相同输入→相同输出)", test_make_cache_key_deterministic),
        ("不同输入→不同输出", test_make_cache_key_different_keys),
        ("列表输入", test_make_cache_key_list),
        ("嵌套结构", test_make_cache_key_nested),
        ("None输入", test_make_cache_key_none),
        ("不可序列化对象fallback", test_make_cache_key_unserializable),
    ]),
    ("大对象与边界", [
        ("大dict作为value", test_large_dict),
        ("10000次set/get操作", test_many_operations),
    ]),
]


def run_all():
    passed = 0
    failed = 0
    for group_name, tests in ALL_TESTS:
        print(f"\n{'='*60}")
        print(f"  [{group_name}]")
        print(f"{'='*60}")
        for name, func in tests:
            sys.stdout.write(f"  {name:30s} ")
            sys.stdout.flush()
            try:
                result = func()
            except Exception as e:
                print(f"  CRASHED: {e}")
                failed += 1
                continue
            if result:
                passed += 1
            else:
                failed += 1
    return passed, failed


if __name__ == "__main__":
    import sys
    print("=" * 60)
    print("  LRUCache 深度测试")
    print(f"  测试时间: 2026-05-30")
    print(f"  测试人: 小健")
    print("=" * 60)
    passed, failed = run_all()
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"  测试总结")
    print(f"{'='*60}")
    print(f"  总计: {total}  通过: {passed}  失败: {failed}")
    if failed == 0:
        print(f"  ✅ 全部通过 - LRUCache功能正确")
    else:
        print(f"  ❌ 有 {failed} 个测试失败")
    print(f"{'='*60}")
    sys.exit(0 if failed == 0 else 1)
