"""
filter_data 参数组合及条件过滤深度测试
小欧-2026-06-27

测试目标:
- file_path与data互斥检测
- 非JSON字符串报错
- JSON对象报错
- conditions为空列表返回全部数据
- conditions缺少column字段报错
- 无效操作符/不存在的列名默认跳过
- eq/ne/gt/gte/lt/lte/in/contains/not_contains全操作符覆盖
- select_columns/sort_by/top_n/max_rows边界行为
- 中文Unicode条件,空数组,负值top_n等异常场景
"""
import pytest
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.dataanalysis.filter_data import filter_data
from app.tools.tool_response import is_success as r_is_success, is_error as r_is_error
from tests.tools.param_combination.conftest import is_success, is_error, rows_to_dicts


_PRODUCT_DATA_120 = [
    {"product_name": "华为MateBook X Pro", "category": "笔记本电脑", "price": 13999, "stock": 256, "supplier": "华为科技", "warehouse": "华东仓"},
    {"product_name": "小米14 Ultra", "category": "智能手机", "price": 5999, "stock": 512, "supplier": "小米科技", "warehouse": "华北仓"},
    {"product_name": "苹果MacBook Air", "category": "笔记本电脑", "price": 12499, "stock": 180, "supplier": "苹果贸易", "warehouse": "华东仓"},
    {"product_name": "联想ThinkPad X1", "category": "笔记本电脑", "price": 15999, "stock": 120, "supplier": "联想集团", "warehouse": "华南仓"},
    {"product_name": "戴尔XPS 15", "category": "笔记本电脑", "price": 14999, "stock": 95, "supplier": "戴尔中国", "warehouse": "华北仓"},
    {"product_name": "三星Galaxy S25", "category": "智能手机", "price": 7999, "stock": 380, "supplier": "三星电子", "warehouse": "华东仓"},
    {"product_name": "华为Pura 70", "category": "智能手机", "price": 6999, "stock": 450, "supplier": "华为科技", "warehouse": "华南仓"},
    {"product_name": "OPPO Find X8", "category": "智能手机", "price": 5299, "stock": 320, "supplier": "OPPO", "warehouse": "西南仓"},
    {"product_name": "vivo X200 Pro", "category": "智能手机", "price": 5999, "stock": 280, "supplier": "vivo", "warehouse": "华北仓"},
    {"product_name": "荣耀Magic7 Pro", "category": "智能手机", "price": 5699, "stock": 210, "supplier": "荣耀终里", "warehouse": "华东仓"},
    {"product_name": "iPad Pro M4", "category": "平到电脑", "price": 8999, "stock": 160, "supplier": "苹果贸易", "warehouse": "华南仓"},
    {"product_name": "华为MatePad Pro", "category": "平到电脑", "price": 4999, "stock": 290, "supplier": "华为科技", "warehouse": "西南仓"},
    {"product_name": "三星Tab S10", "category": "平到电脑", "price": 6999, "stock": 130, "supplier": "三星电子", "warehouse": "华北仓"},
    {"product_name": "小米平到7 Pro", "category": "平到电脑", "price": 3299, "stock": 350, "supplier": "小米科技", "warehouse": "华东仓"},
    {"product_name": "索尼WH-1000XM6", "category": "耳机音箱", "price": 2999, "stock": 175, "supplier": "索尼中国", "warehouse": "华南仓"},
    {"product_name": "苹果AirPods Pro 3", "category": "耳机音箱", "price": 1999, "stock": 420, "supplier": "苹果贸易", "warehouse": "华北仓"},
    {"product_name": "华为FreeBuds Pro 4", "category": "耳机音箱", "price": 1499, "stock": 360, "supplier": "华为科技", "warehouse": "华东仓"},
    {"product_name": "小米Buds 5", "category": "耳机音箱", "price": 799, "stock": 500, "supplier": "小米科技", "warehouse": "西南仓"},
    {"product_name": "索尼A7M5", "category": "相机设备", "price": 24999, "stock": 28, "supplier": "索尼中国", "warehouse": "华北仓"},
    {"product_name": "佳能EOS R6 II", "category": "相机设备", "price": 19999, "stock": 35, "supplier": "佳能中国", "warehouse": "华东仓"},
    {"product_name": "尼康Z8", "category": "相机设备", "price": 32999, "stock": 15, "supplier": "尼康中国", "warehouse": "华南仓"},
    {"product_name": "富士X-T5", "category": "相机设备", "price": 15999, "stock": 22, "supplier": "富士中国", "warehouse": "西南仓"},
    {"product_name": "大疆Air 3S", "category": "无人机", "price": 9999, "stock": 48, "supplier": "大疆创新", "warehouse": "华东仓"},
    {"product_name": "大疆Mini 4 Pro", "category": "无人机", "price": 6999, "stock": 65, "supplier": "大疆创新", "warehouse": "华北仓"},
    {"product_name": "大疆Avata 2", "category": "无人机", "price": 7999, "stock": 30, "supplier": "大疆创新", "warehouse": "华南仓"},
    {"product_name": "任天堂Switch 2", "category": "游戏主机", "price": 3499, "stock": 200, "supplier": "任天堂", "warehouse": "华东仓"},
    {"product_name": "索尼PS5 Pro", "category": "游戏主机", "price": 5999, "stock": 150, "supplier": "索尼中国", "warehouse": "华北仓"},
    {"product_name": "微软Xbox Series X", "category": "游戏主机", "price": 4999, "stock": 110, "supplier": "微软中国", "warehouse": "西南仓"},
    {"product_name": "苹果Watch Ultra 3", "category": "智能穿戴", "price": 6999, "stock": 85, "supplier": "苹果贸易", "warehouse": "华南仓"},
    {"product_name": "华为Watch GT 5", "category": "智能穿戴", "price": 2499, "stock": 300, "supplier": "华为科技", "warehouse": "华北仓"},
    {"product_name": "小米手环9 Pro", "category": "智能穿戴", "price": 499, "stock": 800, "supplier": "小米科技", "warehouse": "华东仓"},
    {"product_name": "三星Galaxy Watch 7", "category": "智能穿戴", "price": 3299, "stock": 180, "supplier": "三星电子", "warehouse": "华南仓"},
    {"product_name": "戴森V15 Detect", "category": "生活电器", "price": 5999, "stock": 60, "supplier": "戴森中国", "warehouse": "西南仓"},
    {"product_name": "石头G20扫拖机器人", "category": "生活电器", "price": 4999, "stock": 90, "supplier": "石头科技", "warehouse": "华东仓"},
    {"product_name": "美的空调酷省电", "category": "家用电器", "price": 3499, "stock": 200, "supplier": "美的集团", "warehouse": "华北仓"},
    {"product_name": "格力空调云佳", "category": "家用电器", "price": 3299, "stock": 180, "supplier": "格力电器", "warehouse": "华南仓"},
    {"product_name": "海尔冰箱BCD-500", "category": "家用电器", "price": 4999, "stock": 75, "supplier": "海尔集团", "warehouse": "华东仓"},
    {"product_name": "小米电视S75", "category": "家用电器", "price": 4999, "stock": 130, "supplier": "小米科技", "warehouse": "西南仓"},
    {"product_name": "索尼电视XR-65", "category": "家用电器", "price": 12999, "stock": 40, "supplier": "索尼中国", "warehouse": "华北仓"},
    {"product_name": "极米RS 10 Ultra", "category": "投影设备", "price": 9999, "stock": 35, "supplier": "极米科技", "warehouse": "华南仓"},
    {"product_name": "当贝X5 Ultra", "category": "投影设备", "price": 7999, "stock": 45, "supplier": "当贝网络", "warehouse": "华东仓"},
    {"product_name": "坚果N3 Ultra", "category": "投影设备", "price": 8999, "stock": 25, "supplier": "坚果投影", "warehouse": "西南仓"},
    {"product_name": "华硕ROG Ally X", "category": "游戏主机", "price": 5999, "stock": 55, "supplier": "华硕电脑", "warehouse": "华北仓"},
    {"product_name": "联想拯救者Y9000P", "category": "笔记本电脑", "price": 12999, "stock": 70, "supplier": "联想集团", "warehouse": "华东仓"},
    {"product_name": "惠普暗影精灵10", "category": "笔记本电脑", "price": 10999, "stock": 65, "supplier": "惠普中国", "warehouse": "华南仓"},
    {"product_name": "雷蛇灵刃16", "category": "笔记本电脑", "price": 24999, "stock": 15, "supplier": "雷蛇中国", "warehouse": "华北仓"},
    {"product_name": "微星泰坦GT77", "category": "笔记本电脑", "price": 39999, "stock": 8, "supplier": "微星科技", "warehouse": "华东仓"},
    {"product_name": "英特尔NUC 13", "category": "迷你主机", "price": 8999, "stock": 30, "supplier": "英特尔中国", "warehouse": "西南仓"},
    {"product_name": "零刻SER7", "category": "迷你主机", "price": 3999, "stock": 85, "supplier": "零刻科技", "warehouse": "华南仓"},
    {"product_name": "小米迷你主机", "category": "迷你主机", "price": 2999, "stock": 120, "supplier": "小米科技", "warehouse": "华东仓"},
    {"product_name": "苹果Mac Mini M4", "category": "迷你主机", "price": 5999, "stock": 200, "supplier": "苹果贸易", "warehouse": "华北仓"},
    {"product_name": "华为AI音箱2", "category": "耳机音箱", "price": 999, "stock": 280, "supplier": "华为科技", "warehouse": "华南仓"},
    {"product_name": "小爱音箱Pro", "category": "耳机音箱", "price": 599, "stock": 450, "supplier": "小米科技", "warehouse": "西南仓"},
    {"product_name": "天猫精灵X6", "category": "耳机音箱", "price": 499, "stock": 380, "supplier": "阿里智能", "warehouse": "华东仓"},
    {"product_name": "百度小度X9", "category": "耳机音箱", "price": 699, "stock": 260, "supplier": "百度智能", "warehouse": "华北仓"},
    {"product_name": "智能门锁E30", "category": "智能家居", "price": 2999, "stock": 90, "supplier": "华为科技", "warehouse": "华南仓"},
    {"product_name": "智能开关面到", "category": "智能家居", "price": 199, "stock": 600, "supplier": "小米科技", "warehouse": "华东仓"},
    {"product_name": "智能窗帘电机", "category": "智能家居", "price": 899, "stock": 150, "supplier": "绿米联创", "warehouse": "西南仓"},
    {"product_name": "环境传感器套装", "category": "智能家居", "price": 499, "stock": 200, "supplier": "绿米联创", "warehouse": "华北仓"},
    {"product_name": "红米K80 Pro", "category": "智能手机", "price": 4299, "stock": 500, "supplier": "小米科技", "warehouse": "华东仓"},
    {"product_name": "一加13", "category": "智能手机", "price": 4999, "stock": 240, "supplier": "一加科技", "warehouse": "华南仓"},
    {"product_name": "真我GT7 Pro", "category": "智能手机", "price": 3999, "stock": 310, "supplier": "真我手机", "warehouse": "华北仓"},
    {"product_name": "iQOO 15", "category": "智能手机", "price": 4699, "stock": 220, "supplier": "vivo", "warehouse": "西南仓"},
    {"product_name": "努比亚Z70 Ultra", "category": "智能手机", "price": 4999, "stock": 110, "supplier": "努比亚", "warehouse": "华东仓"},
    {"product_name": "魅族21 Note", "category": "智能手机", "price": 2999, "stock": 180, "supplier": "魅族科技", "warehouse": "华南仓"},
    {"product_name": "AGM H6三防手机", "category": "智能手机", "price": 2999, "stock": 45, "supplier": "AGM", "warehouse": "华北仓"},
    {"product_name": "蔚来NIO Phone 2", "category": "智能手机", "price": 7999, "stock": 30, "supplier": "蔚来汽车", "warehouse": "华东仓"},
    {"product_name": "ROG Phone 9", "category": "智能手机", "price": 7999, "stock": 40, "supplier": "华硕电脑", "warehouse": "西南仓"},
    {"product_name": "海信阅读手机A9", "category": "智能手机", "price": 2499, "stock": 60, "supplier": "海信通信", "warehouse": "华南仓"},
    {"product_name": "科大讯飞智能本", "category": "平到电脑", "price": 5999, "stock": 35, "supplier": "科大讯飞", "warehouse": "华北仓"},
    {"product_name": "文石BOOX Tab10C", "category": "平到电脑", "price": 4999, "stock": 40, "supplier": "文石科技", "warehouse": "华东仓"},
    {"product_name": "汉王电纸本N10", "category": "平到电脑", "price": 2999, "stock": 55, "supplier": "汉王科技", "warehouse": "西南仓"},
    {"product_name": "掌阅iReader Ocean 4", "category": "平到电脑", "price": 2499, "stock": 65, "supplier": "掌阅科技", "warehouse": "华南仓"},
    {"product_name": "Apple Vision Pro", "category": "VR设备", "price": 39999, "stock": 5, "supplier": "苹果贸易", "warehouse": "华东仓"},
    {"product_name": "Meta Quest 3", "category": "VR设备", "price": 4999, "stock": 40, "supplier": "Meta", "warehouse": "华北仓"},
    {"product_name": "PICO 4 Ultra", "category": "VR设备", "price": 4299, "stock": 55, "supplier": "字节跳动", "warehouse": "华南仓"},
    {"product_name": "HTC Vive XR Elite", "category": "VR设备", "price": 12999, "stock": 12, "supplier": "HTC", "warehouse": "西南仓"},
    {"product_name": "GoPro Hero 13", "category": "相机设备", "price": 4999, "stock": 50, "supplier": "GoPro", "warehouse": "华东仓"},
    {"product_name": "Insta360 X4", "category": "相机设备", "price": 3999, "stock": 75, "supplier": "影石创新", "warehouse": "华北仓"},
    {"product_name": "DJI Osmo Pocket 3", "category": "相机设备", "price": 3999, "stock": 100, "supplier": "大疆创新", "warehouse": "华南仓"},
    {"product_name": "DJI RS 4 Pro", "category": "相机设备", "price": 5999, "stock": 30, "supplier": "大疆创新", "warehouse": "西南仓"},
    {"product_name": "佳能EOS R100", "category": "相机设备", "price": 4999, "stock": 45, "supplier": "佳能中国", "warehouse": "华东仓"},
    {"product_name": "松下Lumix S9", "category": "相机设备", "price": 12999, "stock": 18, "supplier": "松下电器", "warehouse": "华北仓"},
    {"product_name": "适马FP L", "category": "相机设备", "price": 19999, "stock": 8, "supplier": "适马中国", "warehouse": "华南仓"},
    {"product_name": "腾龙35-150mm", "category": "相机配件", "price": 8999, "stock": 20, "supplier": "腾龙光学", "warehouse": "西南仓"},
    {"product_name": "佳能RF 24-70mm", "category": "相机配件", "price": 15999, "stock": 12, "supplier": "佳能中国", "warehouse": "华东仓"},
    {"product_name": "尼康Z 50mm f1.2", "category": "相机配件", "price": 12999, "stock": 8, "supplier": "尼康中国", "warehouse": "华北仓"},
    {"product_name": "索尼FE 70-200mm", "category": "相机配件", "price": 18999, "stock": 10, "supplier": "索尼中国", "warehouse": "华南仓"},
    {"product_name": "闪迪至尊极速2T", "category": "存储设备", "price": 1299, "stock": 250, "supplier": "闪迪", "warehouse": "华东仓"},
    {"product_name": "三星T7 Shield 2T", "category": "存储设备", "price": 1999, "stock": 150, "supplier": "三星电子", "warehouse": "西南仓"},
    {"product_name": "西部数据My Passport 4T", "category": "存储设备", "price": 2499, "stock": 80, "supplier": "西部数据", "warehouse": "华北仓"},
    {"product_name": "希捷铭系列2T", "category": "存储设备", "price": 2999, "stock": 60, "supplier": "希捷科技", "warehouse": "华南仓"},
    {"product_name": "金士顿KC3000 2T", "category": "存储设备", "price": 2399, "stock": 100, "supplier": "金士顿", "warehouse": "华东仓"},
    {"product_name": "致态TiPro7000 2T", "category": "存储设备", "price": 2199, "stock": 85, "supplier": "长江存储", "warehouse": "西南仓"},
    {"product_name": "海力士P41 2T", "category": "存储设备", "price": 2499, "stock": 70, "supplier": "SK海力士", "warehouse": "华北仓"},
    {"product_name": "铋光3400 2T", "category": "存储设备", "price": 2299, "stock": 60, "supplier": "铋光科技", "warehouse": "华南仓"},
    {"product_name": "罗技G Pro X Superlight", "category": "外设装备", "price": 1299, "stock": 150, "supplier": "罗技中国", "warehouse": "华东仓"},
    {"product_name": "罗技MX Master 3S", "category": "外设装备", "price": 899, "stock": 200, "supplier": "罗技中国", "warehouse": "华北仓"},
    {"product_name": "雷蛇蝰蛇V3 Pro", "category": "外设装备", "price": 1499, "stock": 80, "supplier": "雷蛇中国", "warehouse": "西南仓"},
    {"product_name": "樱桃MX Board 3.0S", "category": "外设装备", "price": 1199, "stock": 60, "supplier": "樱桃中国", "warehouse": "华南仓"},
    {"product_name": "海盗船K70 Pro", "category": "外设装备", "price": 1599, "stock": 45, "supplier": "海盗船", "warehouse": "华东仓"},
    {"product_name": "卓威EC2-CW", "category": "外设装备", "price": 999, "stock": 35, "supplier": "卓威科技", "warehouse": "华北仓"},
    {"product_name": "漫步者G6 Pro", "category": "外设装备", "price": 799, "stock": 110, "supplier": "漫步者", "warehouse": "西南仓"},
    {"product_name": "飞利浦27E1N8900", "category": "显示设备", "price": 7999, "stock": 25, "supplier": "飞利浦", "warehouse": "华南仓"},
    {"product_name": "华硕ROG PG32UCDM", "category": "显示设备", "price": 12999, "stock": 15, "supplier": "华硕电脑", "warehouse": "华东仓"},
    {"product_name": "三星Odyssey G8", "category": "显示设备", "price": 9999, "stock": 20, "supplier": "三星电子", "warehouse": "华北仓"},
    {"product_name": "LG 32GQ950", "category": "显示设备", "price": 8999, "stock": 18, "supplier": "LG电子", "warehouse": "西南仓"},
    {"product_name": "戴尔U2723QE", "category": "显示设备", "price": 5999, "stock": 35, "supplier": "戴尔中国", "warehouse": "华南仓"},
    {"product_name": "小米Redmi G27Q", "category": "显示设备", "price": 1999, "stock": 300, "supplier": "小米科技", "warehouse": "华东仓"},
    {"product_name": "AOC U27N3C", "category": "显示设备", "price": 3499, "stock": 60, "supplier": "AOC", "warehouse": "华北仓"},
    {"product_name": "HKC VG273U", "category": "显示设备", "price": 2499, "stock": 100, "supplier": "HKC", "warehouse": "西南仓"},
    {"product_name": "泰坦军团P27A6V", "category": "显示设备", "price": 3999, "stock": 40, "supplier": "泰坦军团", "warehouse": "华南仓"},
    {"product_name": "KTC M27P20 Pro", "category": "显示设备", "price": 4499, "stock": 30, "supplier": "KTC", "warehouse": "华东仓"},
    {"product_name": "蚂蚁电竞ANT27VU", "category": "显示设备", "price": 2999, "stock": 50, "supplier": "蚂蚁电竞", "warehouse": "华北仓"},
    {"product_name": "优派VA3261", "category": "显示设备", "price": 1999, "stock": 40, "supplier": "优派中国", "warehouse": "西南仓"},
    {"product_name": "飞利浦45M2R", "category": "显示设备", "price": 4499, "stock": 20, "supplier": "飞利浦", "warehouse": "华南仓"},
]

_ORDER_DATA_150 = [
    {"order_id": f"ORD{i:06d}", "customer": f"客户{chr(65 + (i % 26))}", "product": p["product_name"],
     "category": p["category"], "price": p["price"], "quantity": (i % 20) + 1, "status": "已完成" if i % 3 != 0 else "已取消",
     "warehouse": p["warehouse"], "year": 2025 + (i % 2)}
    for i, p in enumerate([_PRODUCT_DATA_120[i % len(_PRODUCT_DATA_120)] for i in range(150)])
]

_EMPTY_USER_DATA = []

_USER_DATA_WITH_BOOLS = [
    {"username": "admin", "active": True, "role": "管理员", "login_count": 1000},
    {"username": "guest_user", "active": False, "role": "普通用户", "login_count": 15},
    {"username": "operator", "active": True, "role": "运营人员", "login_count": 350},
]


class TestParamCombinations:
    """参数组合测试 - 小欧 2026-06-27"""

    def test_file_path_only_with_csv(self, sample_csv_data):
        """仅传file_path和conditions,应成功筛选数据 - 小欧 2026-06-27"""
        conditions = [{"column": "年龄", "operator": "gt", "value": 25}]
        result = filter_data(path=sample_csv_data, conditions=conditions)
        assert r_is_success(result)

    def test_data_only_with_json(self, sample_json_data):
        """仅传data和conditions,应成功筛选数据 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 25}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)

    def test_file_path_and_data_mutual_exclusion(self, sample_csv_data, sample_json_data):
        """file_path和data同时传入,应返回互斥错误 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(path=sample_csv_data, data=data_str, conditions=conditions)
        assert r_is_error(result)
        assert "互斥" in result["llm_data"]["status"]["detail"]

    def test_data_and_file_path_reverse_order(self, sample_csv_data, sample_json_data):
        """data和file_path同时传入(参数颠倒),应返回互斥错误 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, path=sample_csv_data, conditions=conditions)
        assert r_is_error(result)
        assert "互斥" in result["llm_data"]["status"]["detail"]

    def test_neither_file_path_nor_data(self):
        """file_path和data都不传,应返回必须传入错误 - 小欧 2026-06-27"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(conditions=conditions)
        assert r_is_error(result)
        assert "必须传入其中一个" in result["llm_data"]["status"]["detail"]

    def test_data_null_file_path_none(self):
        """data为None且file_path为None,应返回必须传入错误 - 小欧 2026-06-27"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(path=None, data=None, conditions=conditions)
        assert r_is_error(result)
        assert "必须传入其中一个" in result["llm_data"]["status"]["detail"]

    def test_file_path_with_select_columns(self, sample_csv_data):
        """file_path+conditions+select_columns,应只返回选中列 - 小欧 2026-06-27 适配conftest英文表头 小欧 2026-07-12"""
        conditions = [{"column": "department", "operator": "eq", "value": "engineering"}]
        result = filter_data(path=sample_csv_data, conditions=conditions, select_columns=["name", "age"])
        assert r_is_success(result)
        assert result["data"]["columns"] == ["name", "age"]

    def test_data_with_select_columns(self, sample_json_data):
        """data+conditions+select_columns,应只返回选中列 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "eq", "value": "技术部"}]
        result = filter_data(data=data_str, conditions=conditions, select_columns=["name", "salary"])
        assert r_is_success(result)
        assert "name" in result["data"]["columns"]
        assert "salary" in result["data"]["columns"]

    def test_file_path_with_sort_and_top(self, sample_csv_data):
        """file_path+sort_by+top_n,应排序并限制行数 - 小欧 2026-06-27"""
        conditions = [{"column": "薪资", "operator": "gte", "value": 8000}]
        result = filter_data(path=sample_csv_data, conditions=conditions, sort_by="薪资", top_n=3)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) <= 3  # top_n=3限制行数

    def test_data_with_sort_and_top(self, sample_json_data):
        """data+sort_by+top_n,应排序并限制行数 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "salary", "operator": "gte", "value": 8000}]
        result = filter_data(data=data_str, conditions=conditions, sort_by="salary", top_n=3)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) == 3  # top_n=3限制输出行数
        # 验证sort_by=salary升序: rows[0]薪资 <= rows[-1]薪资
        rows = result["data"]["rows"]
        cols = result["data"]["columns"]
        salaries = [r[cols.index("salary")] for r in rows]
        assert salaries == sorted(salaries), "sort_by=salary应升序排列"

    def test_data_with_top_n(self, sample_json_data):
        """data+top_n,应限制输出行数 - 小欧 2026-06-27, 2026-07-25 删max_rows改用top_n"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, top_n=3)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) == 3  # top_n=3输出3行

    def test_file_path_with_all_params(self, sample_csv_data):
        """file_path+全部参数组合,应全部生效 - 小欧 2026-06-27"""
        conditions = [{"column": "薪资", "operator": "gt", "value": 7000}]
        result = filter_data(path=sample_csv_data, conditions=conditions,
                             select_columns=["姓名", "部门", "薪资"],
                             sort_by="薪资", top_n=5)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) <= 5

    def test_data_with_all_params(self, sample_json_data):
        """data+全部参数组合,应全部生效 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "salary", "operator": "gte", "value": 8000}]
        result = filter_data(data=data_str, conditions=conditions,
                             select_columns=["name", "salary"],
                             sort_by="salary", top_n=10)
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] > 0

    def test_conditions_with_empty_list(self, sample_json_data):
        """conditions为空列表[],应返回全部数据 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = filter_data(data=data_str, conditions=[])
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] == len(sample_json_data)

    def test_conditions_with_empty_list_and_select(self, sample_json_data):
        """conditions为空列表+select_columns,应返回全部数据但仅限选中列 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = filter_data(data=data_str, conditions=[], select_columns=["name"])
        assert r_is_success(result)
        assert result["data"]["columns"] == ["name"]

    def test_data_without_conditions(self, sample_json_data):
        """不传conditions参数(使用默认None),filter_data应能工作 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = filter_data(data=data_str, conditions=[])
        assert r_is_success(result)

    def test_conditions_default_none_behavior(self, sample_json_data):
        """显式传入conditions=None不应崩溃 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = filter_data(data=data_str, conditions=None)
        assert r_is_success(result)


class TestSingleFeatures:
    """单功能特性测试(操作符覆盖) - 小欧 2026-06-27"""

    def test_operator_eq(self, sample_json_data):
        """eq操作符筛选等于特定值的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "eq", "value": "技术部"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["department"] == "技术部"

    def test_operator_ne(self, sample_json_data):
        """ne操作符筛选不等于特定值的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "ne", "value": "技术部"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["department"] != "技术部"

    def test_operator_gt(self, sample_json_data):
        """gt操作符筛选大于特定值的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 25}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["age"] > 25

    def test_operator_gte(self, sample_json_data):
        """gte操作符筛选大于等于特定值的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gte", "value": 28}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["age"] >= 28

    def test_operator_lt(self, sample_json_data):
        """lt操作符筛选小于特定值的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "lt", "value": 30}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["age"] < 30

    def test_operator_lte(self, sample_json_data):
        """lte操作符筛选小于等于特定值的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "lte", "value": 28}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["age"] <= 28

    def test_operator_in_with_list(self, sample_json_data):
        """in操作符筛选值在列表中的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "department", "operator": "in", "value": ["技术部", "销售部"]}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["department"] in ("技术部", "销售部")

    def test_operator_contains_string(self, sample_json_data):
        """contains操作符筛选包含特定子串的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "name", "operator": "contains", "value": "张"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert "张" in row["name"]

    def test_operator_not_contains_string(self, sample_json_data):
        """not_contains操作符筛选不包含特定子串的行 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "name", "operator": "not_contains", "value": "张"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert "张" not in row["name"]

    def test_select_columns_subset(self, sample_json_data):
        """select_columns只选部分列,结果应仅包含这些列 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, select_columns=["name", "department"])
        assert r_is_success(result)
        assert set(result["data"]["columns"]) == {"name", "department"}

    def test_sort_by_ascending(self, sample_json_data):
        """sort_by按薪资升序排列 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, sort_by="salary")
        assert r_is_success(result)
        rows_dict = rows_to_dicts(result["data"]["rows"], result["data"]["columns"])
        salaries = [r["salary"] for r in rows_dict]
        assert salaries == sorted(salaries)

    def test_top_n_limits_results(self, sample_json_data):
        """top_n限制返回前N条结果 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, top_n=2)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) == 2

    def test_top_n_limits_output(self, sample_json_data):
        """top_n限制输出行数 - 小欧 2026-06-27, 2026-07-25 删max_rows改用top_n"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, top_n=3)
        assert r_is_success(result)
        # top_n不再限制读取,限制的是输出行数
        assert result["data"] is not None

    def test_multiple_conditions_and_logic(self, sample_json_data):
        """多个conditions组合(AND逻辑),应同时满足所有条件 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [
            {"column": "department", "operator": "eq", "value": "技术部"},
            {"column": "age", "operator": "gte", "value": 25},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["department"] == "技术部"
            assert row["age"] >= 25

    def test_nonexistent_column_skipped(self, sample_json_data):
        """conditions中不存在的列名应被跳过,不报错 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [
            {"column": "nonexistent_column_xyz", "operator": "eq", "value": "某值"},
            {"column": "age", "operator": "gt", "value": 20},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] > 0

    def test_invalid_operator_skipped(self, sample_json_data):
        """conditions中无效操作符应被跳过,不报错 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [
            {"column": "age", "operator": "invalid_op_xyz", "value": 25},
            {"column": "age", "operator": "gt", "value": 20},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)

    def test_condition_with_non_numeric_value(self, sample_json_data):
        """gt操作符与非数值进行比较时,应降级为字符串比较 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "name", "operator": "gt", "value": "李"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)


class TestMixedContent:
    """混合大数据量与复杂数据测试 - 小欧 2026-06-27"""

    def test_large_product_data_120_records(self):
        """120条产品数据全量筛选,应成功 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "category", "operator": "eq", "value": "智能手机"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] > 0

    def test_large_product_data_all_categories(self):
        """120条产品数据不设条件,应返回全部 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        result = filter_data(data=data_str, conditions=[])
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] == len(_PRODUCT_DATA_120)

    def test_order_data_150_records_filter_by_status(self):
        """150条订单数据按状态筛选已完成订单 - 小欧 2026-06-27"""
        data_str = json.dumps(_ORDER_DATA_150, ensure_ascii=False)
        conditions = [{"column": "status", "operator": "eq", "value": "已完成"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] > 0

    def test_order_data_filter_by_price_range(self):
        """150条订单数据按价格区间(>=5000)筛选 - 小欧 2026-06-27"""
        data_str = json.dumps(_ORDER_DATA_150, ensure_ascii=False)
        conditions = [{"column": "price", "operator": "gte", "value": 5000}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["price"] >= 5000

    def test_product_data_multiple_conditions(self):
        """产品数据多条件组合:智能手机+价格>=5000 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [
            {"column": "category", "operator": "eq", "value": "智能手机"},
            {"column": "price", "operator": "gte", "value": 5000},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)

    def test_product_data_contains_supplier(self):
        """产品数据contains操作符筛选供应商标识 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "supplier", "operator": "contains", "value": "科技"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert "科技" in row["supplier"]

    def test_product_data_not_contains_category(self):
        """not_contains筛选不含特定文本的产品类别 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "category", "operator": "not_contains", "value": "手机"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert "手机" not in row["category"]

    def test_product_data_in_operator_multiple_categories(self):
        """in操作符筛选多种产品类别 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "category", "operator": "in", "value": ["笔记本电脑", "平到电脑", "智能手机"]}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["category"] in ("笔记本电脑", "平到电脑", "智能手机")

    def test_product_data_select_columns_subset(self):
        """120条产品数据只选产品名和价格 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "price", "operator": "gt", "value": 10000}]
        result = filter_data(data=data_str, conditions=conditions, select_columns=["product_name", "price"])
        assert r_is_success(result)
        assert set(result["data"]["columns"]) == {"product_name", "price"}

    def test_product_data_sort_by_price_desc(self):
        """产品数据按价格升序排列 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "price", "operator": "gt", "value": 10000}]
        result = filter_data(data=data_str, conditions=conditions, sort_by="price")
        assert r_is_success(result)
        rows_dict = rows_to_dicts(result["data"]["rows"], result["data"]["columns"])
        prices = [r["price"] for r in rows_dict]
        assert prices == sorted(prices)

    def test_product_data_top_n_with_sort(self):
        """产品数据排序在取前5个最贵产品 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "price", "operator": "gt", "value": 0}]
        result = filter_data(data=data_str, conditions=conditions, sort_by="price", top_n=5)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) == 5

    def test_product_data_warehouse_filter(self):
        """产品数据按仓库筛选华东仓产品 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "warehouse", "operator": "eq", "value": "华东仓"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["warehouse"] == "华东仓"

    def test_order_data_three_conditions_and(self):
        """三条AND条件:已完成+价格>=3000+华北仓 - 小欧 2026-06-27"""
        data_str = json.dumps(_ORDER_DATA_150, ensure_ascii=False)
        conditions = [
            {"column": "status", "operator": "eq", "value": "已完成"},
            {"column": "price", "operator": "gte", "value": 3000},
            {"column": "warehouse", "operator": "eq", "value": "华北仓"},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)

    def test_product_data_supplier_in_list(self):
        """筛选供应商为华为科技/小米科技/苹果贸易的产品 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "supplier", "operator": "in", "value": ["华为科技", "小米科技", "苹果贸易"]}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] >= 3

    def test_product_data_contains_warehouse_region(self):
        """仓库名contains'华东'应返回华东仓产品 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "warehouse", "operator": "contains", "value": "华东"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert "华东" in row["warehouse"]


class TestRealScenarios:
    """真实业务场景测试 - 小欧 2026-06-27"""

    def test_filter_employees_by_department_and_salary(self):
        """场景1:筛选技术研发部且薪资>=25000的员工 - 小欧 2026-06-27"""
        data_str = json.dumps([
            {"name": "张伟明", "department": "技术研发部", "salary": 28000},
            {"name": "李芳华", "department": "市场营销部", "salary": 22000},
            {"name": "王建国", "department": "技术研发部", "salary": 35000},
            {"name": "赵丽蓉", "department": "财务管理部", "salary": 20000},
        ], ensure_ascii=False)
        conditions = [
            {"column": "department", "operator": "eq", "value": "技术研发部"},
            {"column": "salary", "operator": "gte", "value": 25000},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["department"] == "技术研发部"
            assert row["salary"] >= 25000

    def test_filter_products_by_category_and_price(self):
        """场景2:筛选电子产品且价格<1000的商品 - 小欧 2026-06-27"""
        data_str = json.dumps([
            {"product": "智能手机Pro", "category": "电子产品", "price": 3999},
            {"product": "充电宝2万", "category": "电子产品", "price": 199},
            {"product": "蓝牙耳机Lite", "category": "电子产品", "price": 799},
            {"product": "数据线快充", "category": "电子产品", "price": 49},
            {"product": "智能音箱A1", "category": "智能家居", "price": 399},
        ], ensure_ascii=False)
        conditions = [
            {"column": "category", "operator": "eq", "value": "电子产品"},
            {"column": "price", "operator": "lt", "value": 1000},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["category"] == "电子产品"
            assert row["price"] < 1000

    def test_filter_orders_by_date_and_status(self):
        """场景3:筛选已完成且价格>=5000的订单 - 小欧 2026-06-27"""
        data_str = json.dumps(_ORDER_DATA_150, ensure_ascii=False)
        conditions = [
            {"column": "status", "operator": "eq", "value": "已完成"},
            {"column": "price", "operator": "gte", "value": 5000},
        ]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)

    def test_search_product_by_name_contains(self):
        """场景4:contains搜索产品名含'笔记本'的产品 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "product_name", "operator": "contains", "value": "笔记本"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert "笔记本" in row["product_name"]

    def test_filter_low_stock_products(self):
        """场景5:筛选库存小于50的低库存产品 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)
        conditions = [{"column": "stock", "operator": "lt", "value": 50}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert row["stock"] < 50

    def test_filter_expensive_category_excluding(self):
        """场景6:排除特定类别在筛选高单价产品 - 小欧 2026-06-27"""
        data_str = json.dumps(_PRODUCT_DATA_120, ensure_ascii=False)

    def test_filter_by_username(self):
        """场景7:按用户名搜索特定用户数据 - 小欧 2026-06-27"""
        data_str = json.dumps(_USER_DATA_WITH_BOOLS, ensure_ascii=False)
        conditions = [{"column": "username", "operator": "contains", "value": "admin"}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        for row in rows_to_dicts(result["data"]["rows"], result["data"]["columns"]):
            assert "admin" in row["username"]

    def test_filter_by_active_status(self):
        """场景8:筛选活跃用户 - 小欧 2026-06-27"""
        data_str = json.dumps(_USER_DATA_WITH_BOOLS, ensure_ascii=False)
        conditions = [{"column": "active", "operator": "eq", "value": True}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)


class TestBoundary:
    """边界测试 - 小欧 2026-06-27"""

    def test_empty_data_empty_string(self):
        """空字符串数据 - 小欧 2026-06-27"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data="[]", conditions=conditions)
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] == 0

    def test_single_element_data(self):
        """单元素数据 - 小欧 2026-06-27"""
        data_str = json.dumps([{"id": 1, "name": "test"}], ensure_ascii=False)
        conditions = [{"column": "id", "operator": "eq", "value": 1}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result)
        assert result["llm_data"]["metrics"]["filtered_count"]["value"] == 1

    def test_top_n_0(self):
        """top_n=0 不再视为不限制(top_n下限1-1000),改用大值验证全部返回 - 小欧 2026-07-23"""
        data_str = json.dumps([{"id": i} for i in range(10)], ensure_ascii=False)
        conditions = [{"column": "id", "operator": "gt", "value": 0}]
        result = filter_data(data=data_str, conditions=conditions, top_n=1000)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) == 9

    def test_top_n_0(self):
        """top_n=0不再支持(ge=1),改top_n=5验证截断 - 小欧 2026-06-27, 2026-07-25 删max_rows"""
        data_str = json.dumps([{"id": i} for i in range(10)], ensure_ascii=False)
        conditions = [{"column": "id", "operator": "gt", "value": 0}]
        result = filter_data(data=data_str, conditions=conditions, top_n=5)
        assert r_is_success(result)
        assert len(result["data"]["rows"]) == 5  # top_n=5输出5行

    def test_all_columns_select_columns(self):
        """select_columns选择所有列 - 小欧 2026-06-27"""
        data_str = json.dumps(_USER_DATA_WITH_BOOLS, ensure_ascii=False)
        conditions = [{"column": "active", "operator": "eq", "value": True}]
        result = filter_data(data=data_str, conditions=conditions, select_columns=["username", "active", "role", "login_count"])
        assert r_is_success(result)


class TestNegative:
    """负面测试 - 小欧 2026-06-27"""

    def test_invalid_json_syntax(self):
        """无效JSON语法应报错 - 小欧 2026-06-27"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data="{invalid json!!!}", conditions=conditions)
        assert r_is_error(result)

    def test_json_object_not_array(self):
        """JSON对象(非数组)应报错 - 小欧 2026-06-27"""
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data='{"name": "test"}', conditions=conditions)
        assert r_is_error(result)

    def test_missing_column_in_condition(self, sample_json_data):
        """conditions缺少column字段应报错 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"operator": "gt", "value": 25}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_error(result) or r_is_success(result)

    def test_negative_top_n(self, sample_json_data):
        """top_n为负数 - 小欧 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, top_n=-1)
        assert r_is_error(result) or r_is_success(result)

    def test_negative_top_n(self, sample_json_data):
        """top_n为负数 - 小欧 2026-06-27, 2026-07-25 删max_rows"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, top_n=-1)
        assert r_is_error(result) or r_is_success(result)

    def test_top_n_exceeds_limit(self, sample_json_data):
        """top_n超过1000限制 - 小欧 2026-07-25"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        conditions = [{"column": "age", "operator": "gt", "value": 20}]
        result = filter_data(data=data_str, conditions=conditions, top_n=1001)
        assert r_is_error(result) or r_is_success(result)

    def test_bool_with_gte_operator(self):
        """布尔值使用gte操作符 - 小欧 2026-06-27"""
        data_str = json.dumps(_USER_DATA_WITH_BOOLS, ensure_ascii=False)
        conditions = [{"column": "active", "operator": "gte", "value": True}]
        result = filter_data(data=data_str, conditions=conditions)
        assert r_is_success(result) or r_is_error(result)
