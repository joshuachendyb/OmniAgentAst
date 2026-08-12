"""
analyze_data mutual exclusion parameter and bottom-layer Bug targeted test
xiaojian-2026-06-27
2026-07-31 - 小欧 - Bug⑫修复对齐: group_by/sort_by列不存在由"静默退回/静默跳过"改为明确报错(系统功能进化, 防误导LLM), 对应测试断言同步更新

Test targets:
- file_path/data mutual exclusion: only one allowed
- Non-JSON string error
- JSON object error (must be array)
- Non-existent file path error
- Empty array, empty string, large data stability
- Invalid operations silently filtered
- group_by/sort_by/top_n/max_rows boundary behavior

Each test class >= 10 test methods, total >= 60 tests
"""
import pytest
import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from app.tools.dataanalysis.analyze_data import analyze_data
from tests.tools.param_combination.conftest import is_success, is_error
from app.tools.tool_response import is_success as r_is_success, is_error as r_is_error


# ========== Large realistic business data ==========

_SALES_DATA_100 = [
    {"product": "SmartWatch Pro", "category": "Electronics", "price": 2999, "quantity": 120, "total_sales": 359880, "region": "East"},
    {"product": "Bluetooth Earbuds Lite", "category": "Electronics", "price": 799, "quantity": 350, "total_sales": 279650, "region": "South"},
    {"product": "Mech Keyboard K8", "category": "Peripherals", "price": 599, "quantity": 200, "total_sales": 119800, "region": "East"},
    {"product": "Wireless Mouse M3", "category": "Peripherals", "price": 199, "quantity": 500, "total_sales": 99500, "region": "North"},
    {"product": "Monitor 27in", "category": "Electronics", "price": 2499, "quantity": 80, "total_sales": 199920, "region": "East"},
    {"product": "Laptop Pro", "category": "Electronics", "price": 8999, "quantity": 45, "total_sales": 404955, "region": "South"},
    {"product": "Tablet Air", "category": "Electronics", "price": 3999, "quantity": 65, "total_sales": 259935, "region": "North"},
    {"product": "Fitness Band B2", "category": "Electronics", "price": 399, "quantity": 420, "total_sales": 167580, "region": "West"},
    {"product": "Gaming Mouse G5", "category": "Peripherals", "price": 349, "quantity": 280, "total_sales": 97720, "region": "East"},
    {"product": "Mech Keyboard K10", "category": "Peripherals", "price": 899, "quantity": 150, "total_sales": 134850, "region": "South"},
    {"product": "Camera C1", "category": "Electronics", "price": 599, "quantity": 180, "total_sales": 107820, "region": "North"},
    {"product": "Router AX6", "category": "Networking", "price": 499, "quantity": 220, "total_sales": 109780, "region": "West"},
    {"product": "Switch G8", "category": "Networking", "price": 299, "quantity": 90, "total_sales": 26910, "region": "East"},
    {"product": "HDD 2TB", "category": "Storage", "price": 649, "quantity": 160, "total_sales": 103840, "region": "South"},
    {"product": "SSD 1TB", "category": "Storage", "price": 799, "quantity": 190, "total_sales": 151810, "region": "North"},
    {"product": "RAM 16G", "category": "ComputerParts", "price": 399, "quantity": 300, "total_sales": 119700, "region": "East"},
    {"product": "Power Supply", "category": "ComputerParts", "price": 149, "quantity": 400, "total_sales": 59600, "region": "West"},
    {"product": "Cooling Pad P3", "category": "ComputerParts", "price": 199, "quantity": 250, "total_sales": 49750, "region": "South"},
    {"product": "USB Hub", "category": "ComputerParts", "price": 259, "quantity": 180, "total_sales": 46620, "region": "North"},
    {"product": "ANC Headphones", "category": "Electronics", "price": 1499, "quantity": 95, "total_sales": 142405, "region": "East"},
    {"product": "Smart Speaker A1", "category": "Electronics", "price": 399, "quantity": 310, "total_sales": 123690, "region": "West"},
    {"product": "Projector P2", "category": "Electronics", "price": 4999, "quantity": 35, "total_sales": 174965, "region": "South"},
    {"product": "Printer Laser", "category": "Office", "price": 1299, "quantity": 55, "total_sales": 71445, "region": "North"},
    {"product": "Shredder 5", "category": "Office", "price": 899, "quantity": 40, "total_sales": 35960, "region": "East"},
    {"product": "Ergonomic Chair", "category": "Furniture", "price": 2599, "quantity": 30, "total_sales": 77970, "region": "South"},
    {"product": "Standing Desk", "category": "Furniture", "price": 3999, "quantity": 20, "total_sales": 79980, "region": "West"},
    {"product": "Desk Lamp LED", "category": "Office", "price": 349, "quantity": 180, "total_sales": 62820, "region": "East"},
    {"product": "Charger Fast", "category": "Electronics", "price": 199, "quantity": 450, "total_sales": 89550, "region": "North"},
    {"product": "Data Cable", "category": "Electronics", "price": 49, "quantity": 800, "total_sales": 39200, "region": "South"},
    {"product": "Phone Case Clear", "category": "PhoneAcc", "price": 29, "quantity": 1200, "total_sales": 34800, "region": "East"},
    {"product": "Tempered Glass", "category": "PhoneAcc", "price": 39, "quantity": 900, "total_sales": 35100, "region": "North"},
    {"product": "Selfie Stick BT", "category": "PhoneAcc", "price": 89, "quantity": 350, "total_sales": 31150, "region": "West"},
    {"product": "Car Mount", "category": "PhoneAcc", "price": 59, "quantity": 500, "total_sales": 29500, "region": "South"},
    {"product": "Tablet Case", "category": "PhoneAcc", "price": 79, "quantity": 280, "total_sales": 22120, "region": "East"},
    {"product": "Laptop Bag", "category": "ComputerParts", "price": 199, "quantity": 160, "total_sales": 31840, "region": "North"},
    {"product": "Mouse Pad XL", "category": "Peripherals", "price": 69, "quantity": 600, "total_sales": 41400, "region": "West"},
    {"product": "Keyboard Rest", "category": "Peripherals", "price": 89, "quantity": 220, "total_sales": 19580, "region": "East"},
    {"product": "Monitor Stand", "category": "Peripherals", "price": 299, "quantity": 85, "total_sales": 25415, "region": "South"},
    {"product": "Laptop Cooler", "category": "ComputerParts", "price": 129, "quantity": 200, "total_sales": 25800, "region": "North"},
    {"product": "WiFi Adapter USB", "category": "Networking", "price": 159, "quantity": 250, "total_sales": 39750, "region": "East"},
    {"product": "Network Camera C2", "category": "Networking", "price": 499, "quantity": 120, "total_sales": 59880, "region": "West"},
    {"product": "NAS Storage 2Bay", "category": "Storage", "price": 1999, "quantity": 25, "total_sales": 49975, "region": "South"},
    {"product": "USB Drive 64G", "category": "Storage", "price": 99, "quantity": 600, "total_sales": 59400, "region": "East"},
    {"product": "SD Card 128G", "category": "Storage", "price": 179, "quantity": 350, "total_sales": 62650, "region": "North"},
    {"product": "M.2 SSD 2TB", "category": "Storage", "price": 1599, "quantity": 40, "total_sales": 63960, "region": "West"},
    {"product": "Gaming Chair", "category": "Furniture", "price": 3999, "quantity": 15, "total_sales": 59985, "region": "East"},
    {"product": "Monitor Arm", "category": "Peripherals", "price": 199, "quantity": 180, "total_sales": 35820, "region": "South"},
    {"product": "Phone Gimbal Pro", "category": "PhoneAcc", "price": 899, "quantity": 60, "total_sales": 53940, "region": "North"},
    {"product": "Mic USB", "category": "Peripherals", "price": 399, "quantity": 100, "total_sales": 39900, "region": "East"},
    {"product": "Speaker 2.0", "category": "Electronics", "price": 699, "quantity": 130, "total_sales": 90870, "region": "West"},
    {"product": "Smart Plug WiFi", "category": "SmartHome", "price": 79, "quantity": 500, "total_sales": 39500, "region": "South"},
    {"product": "Smart Light RGB", "category": "SmartHome", "price": 129, "quantity": 350, "total_sales": 45150, "region": "East"},
    {"product": "Smart Lock FP", "category": "SmartHome", "price": 1999, "quantity": 30, "total_sales": 59970, "region": "North"},
    {"product": "Air Purifier", "category": "SmartHome", "price": 2999, "quantity": 20, "total_sales": 59980, "region": "West"},
    {"product": "Robot Vacuum L", "category": "SmartHome", "price": 3999, "quantity": 18, "total_sales": 71982, "region": "East"},
    {"product": "Electric Toothbrush H9", "category": "PersonalCare", "price": 399, "quantity": 200, "total_sales": 79800, "region": "South"},
    {"product": "Hair Dryer Ion", "category": "PersonalCare", "price": 599, "quantity": 140, "total_sales": 83860, "region": "North"},
    {"product": "Shaver S3", "category": "PersonalCare", "price": 499, "quantity": 160, "total_sales": 79840, "region": "East"},
    {"product": "Beauty Device XF", "category": "PersonalCare", "price": 1999, "quantity": 25, "total_sales": 49975, "region": "West"},
    {"product": "Massager M1", "category": "PersonalCare", "price": 899, "quantity": 80, "total_sales": 71920, "region": "South"},
    {"product": "Scale BT", "category": "PersonalCare", "price": 199, "quantity": 220, "total_sales": 43780, "region": "East"},
    {"product": "BP Monitor", "category": "Health", "price": 299, "quantity": 70, "total_sales": 20930, "region": "North"},
    {"product": "Glucose Test", "category": "Health", "price": 399, "quantity": 50, "total_sales": 19950, "region": "West"},
    {"product": "Massage Chair Lux", "category": "Health", "price": 12999, "quantity": 5, "total_sales": 64995, "region": "East"},
    {"product": "Foot Spa", "category": "Health", "price": 599, "quantity": 65, "total_sales": 38935, "region": "South"},
    {"product": "Eye Massager", "category": "Health", "price": 399, "quantity": 90, "total_sales": 35910, "region": "North"},
    {"product": "Gamepad P5", "category": "Gaming", "price": 499, "quantity": 110, "total_sales": 54890, "region": "East"},
    {"product": "Wheel Sim", "category": "Gaming", "price": 3999, "quantity": 10, "total_sales": 39990, "region": "West"},
    {"product": "VR Headset", "category": "Gaming", "price": 4999, "quantity": 8, "total_sales": 39992, "region": "South"},
    {"product": "Gaming Headset 7.1", "category": "Gaming", "price": 799, "quantity": 60, "total_sales": 47940, "region": "East"},
    {"product": "Mouse Pad RGB", "category": "Gaming", "price": 299, "quantity": 150, "total_sales": 44850, "region": "North"},
    {"product": "Monitor 144Hz", "category": "Gaming", "price": 3499, "quantity": 25, "total_sales": 87475, "region": "West"},
    {"product": "Mech Key Switch", "category": "Gaming", "price": 199, "quantity": 200, "total_sales": 39800, "region": "South"},
    {"product": "GPU Bracket", "category": "ComputerParts", "price": 5999, "quantity": 6, "total_sales": 35994, "region": "East"},
    {"product": "CPU Water Cooler", "category": "ComputerParts", "price": 899, "quantity": 35, "total_sales": 31465, "region": "North"},
    {"product": "Motherboard Z790", "category": "ComputerParts", "price": 3499, "quantity": 12, "total_sales": 41988, "region": "West"},
    {"product": "Server RAM 32G", "category": "ComputerParts", "price": 1299, "quantity": 20, "total_sales": 25980, "region": "East"},
    {"product": "Enterprise HDD 4T", "category": "Storage", "price": 2499, "quantity": 15, "total_sales": 37485, "region": "South"},
    {"product": "Rack Server", "category": "Networking", "price": 38999, "quantity": 2, "total_sales": 77998, "region": "North"},
    {"product": "UPS Power", "category": "Office", "price": 2999, "quantity": 10, "total_sales": 29990, "region": "East"},
    {"product": "Projector Screen", "category": "Office", "price": 1299, "quantity": 20, "total_sales": 25980, "region": "West"},
    {"product": "Conference Mic", "category": "Office", "price": 999, "quantity": 30, "total_sales": 29970, "region": "South"},
    {"product": "Video Camera", "category": "Office", "price": 1999, "quantity": 15, "total_sales": 29985, "region": "North"},
    {"product": "E-Board 65in", "category": "Office", "price": 8999, "quantity": 3, "total_sales": 26997, "region": "East"},
    {"product": "Cubicle Divider", "category": "Furniture", "price": 1499, "quantity": 25, "total_sales": 37475, "region": "West"},
    {"product": "File Cabinet", "category": "Furniture", "price": 899, "quantity": 30, "total_sales": 26970, "region": "South"},
    {"product": "Safe Cabinet", "category": "Furniture", "price": 2999, "quantity": 8, "total_sales": 23992, "region": "East"},
    {"product": "Coffee Machine", "category": "Office", "price": 5999, "quantity": 5, "total_sales": 29995, "region": "North"},
    {"product": "Water Dispenser", "category": "Office", "price": 1999, "quantity": 12, "total_sales": 23988, "region": "West"},
    {"product": "Microwave Oven", "category": "Office", "price": 2999, "quantity": 6, "total_sales": 17994, "region": "South"},
    {"product": "Fingerprint Lock", "category": "Office", "price": 599, "quantity": 25, "total_sales": 14975, "region": "East"},
    {"product": "Access Control", "category": "Office", "price": 3999, "quantity": 8, "total_sales": 31992, "region": "North"},
    {"product": "Walkie Talkie", "category": "Comm", "price": 399, "quantity": 60, "total_sales": 23940, "region": "West"},
    {"product": "Thermometer IR", "category": "Health", "price": 499, "quantity": 40, "total_sales": 19960, "region": "South"},
    {"product": "Sterilizer Cabinet", "category": "Office", "price": 3999, "quantity": 4, "total_sales": 15996, "region": "East"},
    {"product": "Dehumidifier", "category": "SmartHome", "price": 1999, "quantity": 15, "total_sales": 29985, "region": "North"},
    {"product": "Humidifier", "category": "SmartHome", "price": 299, "quantity": 130, "total_sales": 38870, "region": "West"},
    {"product": "Floor Fan", "category": "SmartHome", "price": 899, "quantity": 40, "total_sales": 35960, "region": "South"},
    {"product": "Heater Oil", "category": "SmartHome", "price": 799, "quantity": 35, "total_sales": 27965, "region": "East"},
    {"product": "Water Purifier RO", "category": "SmartHome", "price": 3999, "quantity": 10, "total_sales": 39990, "region": "North"},
]

_LARGE_SALES_500 = _SALES_DATA_100 * 5  # 500 records
_EMPLOYEE_DATA_120 = [
    {"name": "zhangwei", "department": "TechRD", "salary": 28000, "age": 35, "years_exp": 12, "projects_completed": 28, "performance_score": 92},
    {"name": "lifang", "department": "Marketing", "salary": 22000, "age": 32, "years_exp": 9, "projects_completed": 18, "performance_score": 85},
    {"name": "wangjian", "department": "TechRD", "salary": 35000, "age": 42, "years_exp": 18, "projects_completed": 35, "performance_score": 95},
    {"name": "zhaoyun", "department": "Finance", "salary": 20000, "age": 30, "years_exp": 7, "projects_completed": 15, "performance_score": 88},
    {"name": "chenzhi", "department": "HR", "salary": 18000, "age": 28, "years_exp": 5, "projects_completed": 10, "performance_score": 80},
    {"name": "liuyang", "department": "TechRD", "salary": 25000, "age": 33, "years_exp": 10, "projects_completed": 22, "performance_score": 90},
    {"name": "sunxiao", "department": "Sales", "salary": 16000, "age": 26, "years_exp": 4, "projects_completed": 8, "performance_score": 78},
    {"name": "zhouli", "department": "Operations", "salary": 19000, "age": 29, "years_exp": 6, "projects_completed": 12, "performance_score": 82},
    {"name": "wuyun", "department": "Finance", "salary": 23000, "age": 36, "years_exp": 11, "projects_completed": 20, "performance_score": 86},
    {"name": "liming", "department": "TechRD", "salary": 32000, "age": 40, "years_exp": 16, "projects_completed": 30, "performance_score": 93},
    {"name": "liuxiao", "department": "Marketing", "salary": 15000, "age": 25, "years_exp": 3, "projects_completed": 6, "performance_score": 75},
    {"name": "yangyang", "department": "HR", "salary": 14000, "age": 24, "years_exp": 2, "projects_completed": 4, "performance_score": 72},
    {"name": "huangzhi", "department": "TechRD", "salary": 40000, "age": 45, "years_exp": 20, "projects_completed": 40, "performance_score": 97},
    {"name": "zhangxue", "department": "Operations", "salary": 17000, "age": 27, "years_exp": 5, "projects_completed": 9, "performance_score": 79},
    {"name": "machao", "department": "TechRD", "salary": 30000, "age": 38, "years_exp": 14, "projects_completed": 25, "performance_score": 91},
    {"name": "linfeng", "department": "Sales", "salary": 21000, "age": 31, "years_exp": 8, "projects_completed": 16, "performance_score": 84},
    {"name": "hexiaofeng", "department": "GM", "salary": 55000, "age": 48, "years_exp": 22, "projects_completed": 50, "performance_score": 99},
    {"name": "zhengxin", "department": "Finance", "salary": 13000, "age": 23, "years_exp": 1, "projects_completed": 2, "performance_score": 70},
    {"name": "tanwei", "department": "Marketing", "salary": 19000, "age": 30, "years_exp": 7, "projects_completed": 14, "performance_score": 83},
    {"name": "tangjian", "department": "TechRD", "salary": 27000, "age": 36, "years_exp": 12, "projects_completed": 24, "performance_score": 89},
]

_NO_NUMERIC_DATA = [
    {"employee_id": "E001", "department_name": "TechRD", "position": "Sr Engineer", "city": "Beijing"},
    {"employee_id": "E002", "department_name": "Marketing", "position": "Sales Lead", "city": "Shanghai"},
    {"employee_id": "E003", "department_name": "Finance", "position": "Analyst", "city": "Shenzhen"},
]

_MIXED_NULL_DATA = [
    {"name": "ProductA", "price": 100, "category": "Food", "stock": 50},
    {"name": "ProductB", "price": None, "category": "Drink", "stock": 200},
    {"name": "ProductC", "price": 300, "category": None, "stock": 0},
    {"name": "ProductD", "price": 400, "category": "Daily", "stock": None},
    {"name": "ProductE", "price": None, "category": None, "stock": None},
]

_CHINESE_SALES_DATA = [
    {"product_name": "MateBook X Pro", "sales_region": "East", "unit_price": 13999, "sales_qty": 256, "sales_amount": 3583744},
    {"product_name": "Mi 14 Ultra", "sales_region": "North", "unit_price": 5999, "sales_qty": 512, "sales_amount": 3071488},
]


class TestParamCombinations:
    """Parameter mutual exclusion combination test -- xiaojian 2026-06-27"""

    def test_file_path_only_with_csv(self, sample_csv_data):
        """Only file_path pointing to valid CSV -- xiaojian 2026-06-27"""
        result = analyze_data(path=sample_csv_data)
        assert r_is_success(result), f"expected success but got error: {result}"
        assert "statistics" in result["data"]

    def test_data_only_with_json(self, sample_json_data):
        """Only data with valid JSON array -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert "statistics" in result["data"]

    def test_file_path_and_data_mutual_exclusion(self, sample_csv_data, sample_json_data):
        """Both file_path and data -- should error mutual exclusion -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(path=sample_csv_data, data=data_str)
        assert r_is_error(result)
        assert "\u4e92\u65a5" in result["llm_data"]["status"]["detail"]

    def test_data_and_file_path_reverse_order(self, sample_csv_data, sample_json_data):
        """data and file_path both provided (reversed order) -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, path=sample_csv_data)
        assert r_is_error(result)
        assert "\u4e92\u65a5" in result["llm_data"]["status"]["detail"]

    def test_neither_file_path_nor_data(self):
        """Neither file_path nor data -- should error -- xiaojian 2026-06-27"""
        result = analyze_data()
        assert r_is_error(result)
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_data_null_file_path_none(self):
        """data=None and file_path=None -- should error -- xiaojian 2026-06-27"""
        result = analyze_data(path=None, data=None)
        assert r_is_error(result)
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_file_path_with_operations(self, sample_csv_data):
        """file_path + operations -- xiaojian 2026-06-27"""
        result = analyze_data(path=sample_csv_data, operations=["mean", "std"])
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert "mean" in stats
        assert "std" in stats

    def test_data_with_operations(self, sample_json_data):
        """data + operations -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["max", "min"])
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert "max" in stats
        assert "min" in stats

    def test_file_path_with_group_by(self, sample_csv_data):
        """file_path + group_by -- xiaojian 2026-06-27"""
        result = analyze_data(path=sample_csv_data, group_by="department", operations=["mean"])
        assert r_is_success(result)
        assert "grouped_statistics" in result["data"]

    def test_data_with_all_optional_params(self, sample_json_data):
        """data + all optional params -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["mean", "count"], group_by="department", sort_by="salary", top_n=3)
        assert r_is_success(result)

    def test_file_path_with_excel_file(self, sample_csv_data):
        """CSV file (not xlsx) path should also work -- xiaojian 2026-06-27"""
        result = analyze_data(path=sample_csv_data)
        assert r_is_success(result)


class TestSingleFeatures:
    """Single feature property test -- xiaojian 2026-06-27"""

    def test_data_non_existent_file_path(self):
        """file_path pointing to non-existent file -- xiaojian 2026-06-27"""
        result = analyze_data(path="E:/nonexistent_data_file_2026.csv")
        assert r_is_error(result)
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_data_non_json_string(self):
        """data is plain text, not JSON -- xiaojian 2026-06-27"""
        result = analyze_data(data="This is plain text, not JSON format data")
        assert r_is_error(result)
        assert "JSON" in result["llm_data"]["status"]["detail"]

    def test_data_json_object_not_array(self):
        """data is JSON object (not array) -- xiaojian 2026-06-27"""
        result = analyze_data(data=json.dumps({"key": "value", "number": 100}))
        assert r_is_error(result)
        assert "JSON" in result["llm_data"]["status"]["detail"]

    def test_data_empty_json_array(self):
        """data is empty JSON array [] -- xiaojian 2026-06-27"""
        result = analyze_data(data="[]")
        assert r_is_success(result)
        data = result["data"]
        assert "row_count" not in data
        assert data.get("statistics", {}) == {}

    def test_data_empty_list_operations_none(self):
        """data is empty array with operations=None -- xiaojian 2026-06-27"""
        result = analyze_data(data="[]", operations=None)
        assert r_is_success(result)
        assert "row_count" not in result["data"]

    def test_data_invalid_operation_filtered(self, sample_json_data):
        """operations contains invalid ops -- should be silently filtered -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["invalid_op_xyz", "mean"])
        assert r_is_success(result)
        assert "mean" in result["data"]["statistics"]

    def test_data_all_six_operations_default(self, sample_json_data):
        """operations=None uses all 6 operations -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        for op in ("mean", "sum", "count", "min", "max", "std"):
            assert op in stats, f"missing operation: {op}"

    def test_data_group_by_nonexistent_column(self, sample_json_data):
        """group_by pointing to non-existent column rejected -- xiaojian 2026-06-27, updated 2026-07-31 小欧(Bug⑫: 原静默退回非分组统计, 改为明确报错防误导LLM)"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="nonexistent_column_name")
        assert r_is_error(result)
        assert "nonexistent_column_name" in (result["llm_data"]["status"]["detail"] or "")

    def test_data_sort_by_valid_column(self, sample_json_data):
        """sort_by ascending -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="salary")
        assert r_is_success(result)

    def test_data_sort_by_nonexistent_column(self, sample_json_data):
        """sort_by pointing to non-existent column rejected -- xiaojian 2026-06-27, updated 2026-07-31 小欧(Bug⑫: 原静默跳过排序, 改为明确报错防误导LLM)"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="column_not_exist")
        assert r_is_error(result)
        assert "column_not_exist" in (result["llm_data"]["status"]["detail"] or "")

    def test_data_top_n_zero(self, sample_json_data):
        """top_n=0 rejected (ge=1) -- xiaojian 2026-06-27, updated 2026-07-21"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=0)
        assert r_is_error(result)


class TestMixedContent:
    """Mixed large data volume and Chinese content test -- xiaojian 2026-06-27"""

    def test_large_sales_data_100_records(self):
        """100 real sales records full analysis -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert len(result["data"]["columns"]) > 0

    def test_large_sales_data_500_records(self):
        """500 sales records analysis -- xiaojian 2026-06-27"""
        data_str = json.dumps(_LARGE_SALES_500, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert len(result["data"]["columns"]) > 0

    def test_employee_data_with_department_grouping(self):
        """120 employee records grouped by department -- xiaojian 2026-06-27"""
        data_str = json.dumps(_EMPLOYEE_DATA_120, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="department", operations=["mean"])
        assert r_is_success(result)
        assert "grouped_statistics" in result["data"]

    def test_employee_data_with_performance_sort(self):
        """Employee data sorted by performance_score -- xiaojian 2026-06-27"""
        data_str = json.dumps(_EMPLOYEE_DATA_120, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="performance_score")
        assert r_is_success(result)

    def test_chinese_column_names_analysis(self):
        """Chinese column names JSON data -- xiaojian 2026-06-27"""
        data_str = json.dumps(_CHINESE_SALES_DATA, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert "sum" in stats

    def test_mixed_null_values_analysis(self):
        """Data with None values -- xiaojian 2026-06-27"""
        data_str = json.dumps(_MIXED_NULL_DATA, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert "mean" in stats

    def test_sales_data_group_by_region(self):
        """100 sales records grouped by region -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="region", operations=["sum"])
        assert r_is_success(result)
        groups = result["data"]["grouped_statistics"]
        assert "East" in groups or "North" in groups or "South" in groups

    def test_sales_data_top_n_10(self):
        """100 sales records with top_n=10 -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=10)
        assert r_is_success(result)
        assert "statistics" in result["data"]
        # 统计基于全量数据(100条),非head后10条 — 小欧 2026-07-25
        assert result["data"]["row_count"] == 100
        assert result["llm_data"]["metrics"]["row_count"]["value"] == 100
        assert result["data"]["statistics"]["count"]["price"] == 100

    def test_sales_data_top_n_50(self):
        """100 records with top_n=50 -- xiaojian 2026-06-27, 小欧 2026-07-25 删max_rows改用top_n"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=50)
        assert r_is_success(result)
        # 统计基于全量数据(100条) — 小欧 2026-07-25
        assert result["data"]["row_count"] == 100
        assert result["llm_data"]["metrics"]["row_count"]["value"] == 100

    def test_employee_data_with_all_operations(self):
        """120 employee records all 6 operations -- xiaojian 2026-06-27"""
        data_str = json.dumps(_EMPLOYEE_DATA_120, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        for op in ("mean", "sum", "count", "min", "max", "std"):
            assert op in stats


class TestRealScenarios:
    """Real business scenario simulation test -- xiaojian 2026-06-27"""

    def test_analyze_sales_by_region(self):
        """Scenario1: sales sum by region -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="region", operations=["sum", "count"])
        assert r_is_success(result)
        groups = result["data"]["grouped_statistics"]
        assert len(groups) >= 4

    def test_compute_avg_salary_by_department(self):
        """Scenario2: average salary by department -- xiaojian 2026-06-27"""
        data_str = json.dumps(_EMPLOYEE_DATA_120, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="department", operations=["mean"])
        assert r_is_success(result)
        groups = result["data"]["grouped_statistics"]
        for dept in ("TechRD", "Marketing", "Finance"):
            assert dept in groups

    def test_find_min_max_prices_by_category(self):
        """Scenario3: min/max price by category -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="category", operations=["min", "max"])
        assert r_is_success(result)
        groups = result["data"]["grouped_statistics"]
        assert len(groups) > 0

    def test_top_5_most_expensive_products(self):
        """Scenario4: top 5 most expensive (sort_by + top_n) -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="price", top_n=5)
        assert r_is_success(result)
        assert "statistics" in result["data"]

    def test_total_sales_sum_by_region(self):
        """Scenario5: total sales sum by region -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="region", operations=["sum", "count"])
        assert r_is_success(result)

    def test_employee_performance_statistics(self):
        """Scenario6: employee performance stats -- xiaojian 2026-06-27"""
        data_str = json.dumps(_EMPLOYEE_DATA_120, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["mean", "max", "min", "std"])
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert stats["mean"]["performance_score"] > 0

    def test_product_inventory_analysis(self):
        """Scenario7: product SKU inventory stats -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["sum", "mean", "max", "min"])
        assert r_is_success(result)

    def test_sales_data_top_n_10_with_all_params(self):
        """Scenario8: top 10 rows -- xiaojian 2026-06-27, 小欧 2026-07-25 删max_rows改用top_n"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=10, group_by="region", operations=["count"])
        assert r_is_success(result)

    def test_engineer_headcount_by_department(self):
        """Scenario9: headcount by department -- xiaojian 2026-06-27"""
        data_str = json.dumps(_EMPLOYEE_DATA_120, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="department", operations=["count"])
        assert r_is_success(result)

    def test_sales_profit_margin_analysis(self):
        """Scenario10: total_sales field stats -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["mean", "std"])
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert stats["mean"]["total_sales"] > 0


class TestBoundary:
    """Boundary value test -- xiaojian 2026-06-27"""

    def test_empty_string_data(self):
        """Empty string data -- should error -- xiaojian 2026-06-27"""
        result = analyze_data(data="")
        assert r_is_error(result)

    def test_data_single_numeric_column(self):
        """Single numeric column -- xiaojian 2026-06-27"""
        single_col = [{"value": 10}, {"value": 20}, {"value": 30}, {"value": 40}, {"value": 50}]
        data_str = json.dumps(single_col, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert stats["mean"]["value"] == 30.0
        assert stats["max"]["value"] == 50
        assert stats["min"]["value"] == 10
        assert stats["sum"]["value"] == 150

    def test_data_non_numeric_columns_only(self):
        """Only non-numeric columns -- xiaojian 2026-06-27"""
        data_str = json.dumps(_NO_NUMERIC_DATA, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert result["data"]["statistics"] == {}

    def test_data_group_by_with_none_values(self):
        """group_by column contains None values -- xiaojian 2026-06-27"""
        data_str = json.dumps(_MIXED_NULL_DATA, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="category", operations=["mean"])
        assert r_is_success(result)

    def test_data_top_n_negative_one(self):
        """top_n=-1 rejected (ge=1) -- xiaojian 2026-06-27, updated 2026-07-21"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=-1)
        assert r_is_error(result)

    def test_data_top_n_zero(self):
        """top_n=0 rejected (ge=1) -- xiaojian 2026-06-27, 小欧 2026-07-25 删max_rows改用top_n"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=0)
        assert r_is_error(result)

    def test_data_with_nan_in_numeric_column(self):
        """Numeric column with NaN/None values -- xiaojian 2026-06-27"""
        data_str = json.dumps(_MIXED_NULL_DATA, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert "mean" in stats

    def test_data_single_record(self):
        """Only 1 record -- xiaojian 2026-06-27"""
        single = [{"product": "TestProduct", "price": 999, "quantity": 1}]
        data_str = json.dumps(single, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert result["data"]["statistics"]["count"]["price"] >= 1

    def test_data_unicode_chinese_json(self):
        """Unicode Chinese JSON data -- xiaojian 2026-06-27"""
        unicode_data = '[{"\\u4ea7\\u54c1": "\\u667a\\u80fd\\u624b\\u8868", "\\u4ef7\\u683c": 2999}]'
        result = analyze_data(data=unicode_data)
        assert r_is_success(result)
        assert "columns" in result["data"]

    def test_data_very_large_volume_1000_rows(self):
        """1500 rows large data -- xiaojian 2026-06-27"""
        large_data = [{"id": i, "value": i * 1.5} for i in range(1500)]
        data_str = json.dumps(large_data)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert len(result["data"]["columns"]) > 0

    def test_data_with_top_n(self):
        """top_n set -- xiaojian 2026-06-27, 小欧 2026-07-25 删max_rows"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=5)
        assert r_is_success(result)
        assert "statistics" in result["data"]


class TestNegative:
    """Negative / exception scenario test -- xiaojian 2026-06-27"""

    def test_data_malformed_json(self):
        """Malformed JSON string -- xiaojian 2026-06-27"""
        result = analyze_data(data='[{name: "zhangsan", age: 25}]')
        assert r_is_error(result)

    def test_data_json_boolean_value(self):
        """JSON boolean value true (not array) -- xiaojian 2026-06-27"""
        result = analyze_data(data="true")
        assert r_is_error(result)
        assert "JSON" in result["llm_data"]["status"]["detail"]

    def test_data_json_number_value(self):
        """JSON number (not array) -- xiaojian 2026-06-27"""
        result = analyze_data(data="12345")
        assert r_is_error(result)
        assert "JSON" in result["llm_data"]["status"]["detail"]

    def test_data_json_null_value(self):
        """JSON null (not array) -- xiaojian 2026-06-27"""
        result = analyze_data(data="null")
        assert r_is_error(result)
        assert "JSON" in result["llm_data"]["status"]["detail"]

    def test_file_path_with_operations_invalid(self, sample_csv_data):
        """file_path + all invalid operations -- xiaojian 2026-06-27"""
        result = analyze_data(path=sample_csv_data, operations=["bad_op_1", "bad_op_2"])
        assert r_is_success(result)
        stats = result["data"].get("statistics", {})
        assert stats == {} or all(k not in stats for k in ("mean", "sum"))

    def test_file_path_invalid_extension(self):
        """Non-existent file path -- xiaojian 2026-06-27"""
        result = analyze_data(path="Z:/completely_invalid_path_xyz.csv")
        assert r_is_error(result)
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_data_all_operations_invalid(self, sample_json_data):
        """All operations invalid -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["nonexistent_op", "fake_op"])
        assert r_is_success(result)
        stats = result["data"].get("statistics", {})
        assert stats == {} or all(k not in stats for k in ("mean", "sum", "count", "min", "max", "std"))

    def test_file_path_pointing_to_directory(self):
        """file_path points to directory -- xiaojian 2026-06-27"""
        result = analyze_data(path="C:/Windows")
        assert r_is_error(result)
        error_msg = result["llm_data"]["status"].get("detail", "")
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_data_nested_json_objects(self):
        """Data with nested objects -- xiaojian 2026-06-27"""
        nested = [{"id": 1, "details": {"color": "red", "size": "L"}}]
        data_str = json.dumps(nested, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)

    def test_data_with_boolean_fields(self):
        """Data with boolean fields -- xiaojian 2026-06-27"""
        bool_data = [{"item": "ProductA", "active": True, "price": 100}, {"item": "ProductB", "active": False, "price": 200}]
        data_str = json.dumps(bool_data, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)

    def test_file_path_with_top_n_only(self, sample_csv_data):
        """file_path + top_n only -- xiaojian 2026-06-27"""
        result = analyze_data(path=sample_csv_data, top_n=3)
        assert r_is_success(result)
        assert "statistics" in result["data"]

    def test_data_with_sort_and_group_by(self, sample_json_data):
        """data + sort_by + group_by combination -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="salary", group_by="department", operations=["mean"])
        assert r_is_success(result)

    def test_employee_data_sort_by_age(self):
        """Employee data sorted by age -- xiaojian 2026-06-27"""
        employees = [{"name": "a", "age": 40}, {"name": "b", "age": 25}, {"name": "c", "age": 35}]
        data_str = json.dumps(employees, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="age")
        assert r_is_success(result)

    def test_data_std_operation_single_column(self, sample_json_data):
        """std operation on single column -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["std"])
        assert r_is_success(result)
        assert "std" in result["data"]["statistics"]

    def test_data_count_operation_only(self, sample_json_data):
        """count operation only -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["count"])
        assert r_is_success(result)
        assert result["data"]["statistics"]["count"]["age"] >= 1

    def test_file_path_with_top_n_limited(self, sample_csv_data):
        """file_path + top_n limit -- xiaojian 2026-06-27, 小欧 2026-07-25 删max_rows改用top_n"""
        result = analyze_data(path=sample_csv_data, top_n=2)
        assert r_is_success(result)
        assert "statistics" in result["data"]

    def test_data_duplicate_operations(self, sample_json_data):
        """Duplicate operations in list -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["mean", "mean", "sum", "sum"])
        assert r_is_success(result)
        assert "mean" in result["data"]["statistics"]
        assert "sum" in result["data"]["statistics"]

    def test_data_with_all_numeric_fields(self):
        """All numeric fields data -- xiaojian 2026-06-27"""
        nums = [{"a": 10, "b": 100}, {"a": 20, "b": 200}, {"a": 30, "b": 300}]
        data_str = json.dumps(nums)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert "a" in result["data"]["statistics"]["mean"]
        assert "b" in result["data"]["statistics"]["mean"]

    def test_data_decimal_values_precision(self):
        """Decimal precision should be preserved -- xiaojian 2026-06-27"""
        precise = [{"val": 1.23456}, {"val": 2.34567}, {"val": 3.45678}]
        data_str = json.dumps(precise)
        result = analyze_data(data=data_str, operations=["mean"])
        assert r_is_success(result)
        mean_val = result["data"]["statistics"]["mean"]["val"]
        assert abs(mean_val - 2.34567) < 0.001

    def test_data_group_by_with_mixed_types(self):
        """group_by column with mixed types -- xiaojian 2026-06-27"""
        mixed = [{"group": "A", "val": 10}, {"group": "B", "val": 20}, {"group": "A", "val": 30}]
        data_str = json.dumps(mixed, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="group", operations=["mean"])
        assert r_is_success(result)
        assert "grouped_statistics" in result["data"]

    def test_data_empty_operations_list(self, sample_json_data):
        """operations is empty list -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=[])
        assert r_is_success(result)
        assert result["data"]["statistics"] == {}

    def test_data_single_string_column(self):
        """Only string column data -- xiaojian 2026-06-27"""
        strs = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        data_str = json.dumps(strs, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert result["data"]["statistics"] == {}

    def test_data_negative_values_in_numeric_column(self):
        """Negative values in numeric column -- xiaojian 2026-06-27"""
        neg = [{"val": -10}, {"val": -20}, {"val": 0}, {"val": 30}]
        data_str = json.dumps(neg)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert result["data"]["statistics"]["min"]["val"] == -20
        assert result["data"]["statistics"]["max"]["val"] == 30
        assert result["data"]["statistics"]["sum"]["val"] == 0

    def test_data_sales_mean_by_product_category(self):
        """Sales mean price by category -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="category", operations=["mean"])
        assert r_is_success(result)
        assert "grouped_statistics" in result["data"]

    def test_data_operations_with_filtered_invalid(self, sample_json_data):
        """Mixed valid and invalid operations -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, operations=["valid_op_invalid", "mean", "sum", "bad_op"])
        assert r_is_success(result)
        assert "mean" in result["data"]["statistics"]
        assert "sum" in result["data"]["statistics"]

    def test_data_top_n_larger_than_total(self, sample_json_data):
        """top_n larger than total rows -- xiaojian 2026-06-27, updated 2026-07-21 (le=1000)"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, top_n=1000)
        assert r_is_success(result)
        assert "statistics" in result["data"]

    def test_data_group_by_valid_with_sort(self, sample_json_data):
        """group_by + sort combination -- xiaojian 2026-06-27"""
        data_str = json.dumps(sample_json_data, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="department", sort_by="salary")
        assert r_is_success(result)

    def test_file_path_non_csv_extension_valid(self):
        """Non-existent file path even with correct extension -- xiaojian 2026-06-27"""
        result = analyze_data(path="E:/data_analysis_2026_fake_data.csv")
        assert r_is_error(result)
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_data_large_sales_with_sort_by_quantity(self):
        """Large sales data sorted by quantity -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="quantity")
        assert r_is_success(result)

    def test_data_with_zero_only_numeric(self):
        """All-zero numeric columns -- xiaojian 2026-06-27"""
        zeros = [{"val": 0}, {"val": 0}, {"val": 0}]
        data_str = json.dumps(zeros)
        result = analyze_data(data=data_str, operations=["mean", "sum", "min", "max"])
        assert r_is_success(result)
        assert result["data"]["statistics"]["mean"]["val"] == 0.0
        assert result["data"]["statistics"]["sum"]["val"] == 0
        assert result["data"]["statistics"]["min"]["val"] == 0
        assert result["data"]["statistics"]["max"]["val"] == 0

    def test_data_group_by_column_is_numeric(self):
        """group_by column is numeric type -- xiaojian 2026-06-27"""
        gb = [{"group": 1, "val": 10}, {"group": 2, "val": 20}, {"group": 1, "val": 30}]
        data_str = json.dumps(gb)
        result = analyze_data(data=data_str, group_by="group", operations=["mean"])
        assert r_is_success(result)
        assert "grouped_statistics" in result["data"]

    def test_data_mixed_string_numeric_columns(self):
        """Mixed string/numeric columns -- xiaojian 2026-06-27"""
        mixed = [{"name": "ProductA", "price": 100, "desc": "Good"}, {"name": "ProductB", "price": 200, "desc": "Sale"}]
        data_str = json.dumps(mixed, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert "price" in result["data"]["statistics"]["mean"]

    def test_data_with_null_only_in_column(self):
        """Column with all null values -- xiaojian 2026-06-27"""
        nulls = [{"a": None, "b": 1}, {"a": None, "b": 2}]
        data_str = json.dumps(nulls)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert "a" not in result["data"]["statistics"]["mean"]

    def test_data_file_path_with_sort_and_group(self, sample_csv_data):
        """file_path + sort_by + group_by all three -- xiaojian 2026-06-27"""
        result = analyze_data(path=sample_csv_data, sort_by="salary", group_by="department", operations=["mean"])
        assert r_is_success(result)

    def test_data_empty_object_in_array(self):
        """Array contains empty object {} -- xiaojian 2026-06-27"""
        mixed_with_empty = [{"a": 1}, {}, {"a": 3}]
        data_str = json.dumps(mixed_with_empty)
        result = analyze_data(data=data_str)
        assert r_is_success(result)

    def test_data_top_n_with_group_by(self):
        """top_n + group_by combination -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="region", operations=["sum"], top_n=3)
        assert r_is_success(result)

    def test_data_very_large_quantity_column(self):
        """Large quantity column values -- xiaojian 2026-06-27"""
        large_nums = [{"id": i, "val": i * 1000000} for i in range(100)]
        data_str = json.dumps(large_nums)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert result["data"]["statistics"]["max"]["val"] > 0

    def test_data_sort_then_group_by_valid(self):
        """Sort then group_by -- xiaojian 2026-06-27"""
        data_str = json.dumps(_EMPLOYEE_DATA_120, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="salary", group_by="department", operations=["mean"])
        assert r_is_success(result)

    def test_data_all_operations_on_large_set(self):
        """All 6 operations on large dataset -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        stats = result["data"]["statistics"]
        assert "mean" in stats and "sum" in stats and "count" in stats
        assert "min" in stats and "max" in stats and "std" in stats

    def test_file_path_invalid_unicode_path(self):
        """Unicode path to non-existent file -- xiaojian 2026-06-27"""
        result = analyze_data(path="E:/test_nonexist_2026.csv")
        assert r_is_error(result)
        assert "detail" in result.get("llm_data", {}).get("status", {})

    def test_data_long_string_columns(self):
        """Long string columns should not participate in numeric stats -- xiaojian 2026-06-27"""
        long_strs = [{"id": 1, "content": "A very long string for testing"}, {"id": 2, "content": "Another long string for testing"}]
        data_str = json.dumps(long_strs, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)

    def test_data_large_group_by_many_groups(self):
        """group_by produces 200 groups -- xiaojian 2026-06-27"""
        many_groups = [{"group": f"G{i:04d}", "val": i} for i in range(200)]
        data_str = json.dumps(many_groups)
        result = analyze_data(data=data_str, group_by="group", operations=["count"])
        assert r_is_success(result)
        groups = result["data"]["grouped_statistics"]
        assert len(groups) == 200

    def test_data_sort_by_string_column(self):
        """Sort by string column -- xiaojian 2026-06-27"""
        strs = [{"name": "Charlie"}, {"name": "Alice"}, {"name": "Bob"}, {"name": "David"}, {"name": "Eve"}]
        data_str = json.dumps(strs, ensure_ascii=False)
        result = analyze_data(data=data_str, sort_by="name")
        assert r_is_success(result)

    def test_data_min_max_same_value(self):
        """All values identical min=max -- xiaojian 2026-06-27"""
        same = [{"val": 42}, {"val": 42}, {"val": 42}]
        data_str = json.dumps(same)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert result["data"]["statistics"]["min"]["val"] == 42
        assert result["data"]["statistics"]["max"]["val"] == 42

    def test_data_group_by_two_operations(self):
        """group_by with mean + sum -- xiaojian 2026-06-27"""
        data_str = json.dumps(_SALES_DATA_100, ensure_ascii=False)
        result = analyze_data(data=data_str, group_by="category", operations=["mean", "sum"])
        assert r_is_success(result)

    def test_data_with_extra_whitespace_in_json(self):
        """JSON with extra whitespace -- xiaojian 2026-06-27"""
        data_str = '  \n  [{"value":10},{"value":20}]  \n  '
        result = analyze_data(data=data_str)
        assert r_is_success(result)
        assert "columns" in result["data"]

    def test_data_mixed_pandas_convert_types(self):
        """Mixed type data auto-detection -- xiaojian 2026-06-27"""
        mixed_types = [{"name": "Product", "price": "99.5", "quantity": "10"}, {"name": "Product2", "price": "199.5", "quantity": "20"}]
        data_str = json.dumps(mixed_types, ensure_ascii=False)
        result = analyze_data(data=data_str)
        assert r_is_success(result)
