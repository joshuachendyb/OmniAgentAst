# -*- coding: utf-8 -*-
"""
generate_chart 参数组合与内容测试 - 小欧 2026-06-24

覆盖:- 参数组合:chart_type × data类型 × title/x_label/y_label × output_path
- 单一功能:每种chart_type独立验证
- 混合内容:中英文标签,负值,零值
- 真实场景:销售趋势,用户占比,性能对比
- 边界:空数据,单值,超大数据量
- 负面:非法文件,data格式错误,labels/values长度不一致
"""
import csv
import os
import asyncio
from pathlib import Path

import pytest

from app.tools.dataanalysis.generate_chart import generate_chart


def _csv_path(tmp_path, name, rows):
    p = tmp_path / name
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return str(p)


# ============================================================
# 1. 参数组合 (8组)
# ============================================================

class TestParamCombinations:
    def test_bar_with_all_labels(self, tmp_path):
        """bar + title + x_label + y_label"""
        data = {"labels": ["Q1", "Q2", "Q3", "Q4"], "values": [100, 150, 130, 180]}
        out = str(tmp_path / "bar_all.png")
        r = generate_chart(data, chart_type="bar", title="季度销售",
                           x_label="季度", y_label="金额(元)", dest=out)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert os.path.exists(out)

    def test_line_from_csv(self, tmp_path):
        """CSV文件 → line图表"""
        csv_file = _csv_path(tmp_path, "line.csv", [
            {"month": "Jan", "sales": 100}, {"month": "Feb", "sales": 120},
            {"month": "Mar", "sales": 110}
        ])
        out = str(tmp_path / "line.png")
        r = generate_chart(csv_file, chart_type="line", dest=out)
        assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_pie_with_title(self, tmp_path):
        """pie + title"""
        data = {"labels": ["Chrome", "Firefox", "Safari"], "values": [65, 20, 15]}
        out = str(tmp_path / "pie.png")
        r = generate_chart(data, chart_type="pie", title="浏览器占比", dest=out)
        assert os.path.exists(out)

    def test_scatter_with_labels(self, tmp_path):
        """scatter + title + labels"""
        data = {"labels": [1, 2, 3, 4, 5], "values": [2, 4, 5, 4, 5]}
        out = str(tmp_path / "scatter.png")
        r = generate_chart(data, chart_type="scatter", title="散点图",
                           x_label="X轴", y_label="Y轴", dest=out)
        assert os.path.exists(out)

    def test_bar_no_optional_params(self, tmp_path):
        """bar只传必填参数"""
        data = {"labels": ["A", "B"], "values": [10, 20]}
        out = str(tmp_path / "bar_min.png")
        r = generate_chart(data, dest=out)
        assert r["llm_data"]["status"]["exec_code"] == "success"

    def test_csv_auto_output_path(self, tmp_path):
        """CSV文件不传output_path,自动在CSV同目录生成"""
        csv_file = _csv_path(tmp_path, "auto.csv", [
            {"label": "X", "value": 10}, {"label": "Y", "value": 20}
        ])
        r = generate_chart(csv_file)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        # 自动output_path 在summary中体现
        assert ".png" in r["llm_data"]["summary"]

    def test_all_chart_types(self, tmp_path):
        """所有chart_type覆盖"""
        data = {"labels": ["A", "B", "C"], "values": [10, 20, 15]}
        for ct in ["bar", "line", "pie", "scatter"]:
            out = str(tmp_path / f"{ct}.png")
            r = generate_chart(data, chart_type=ct, dest=out)
            assert r["llm_data"]["status"]["exec_code"] == "success", f"{ct} failed"

    def test_csv_with_many_columns(self, tmp_path):
        """CSV有>2列时取前两列"""
        csv_file = _csv_path(tmp_path, "multi.csv", [
            {"label": "A", "value": 10, "extra": 100, "other": 999},
            {"label": "B", "value": 20, "extra": 200, "other": 888}
        ])
        out = str(tmp_path / "multi.png")
        r = generate_chart(csv_file, dest=out)
        assert r["llm_data"]["status"]["exec_code"] == "success"


# ============================================================
# 2. 单一功能 (10个)
# ============================================================

class TestSingleFunction:
    def test_bar_chart(self, tmp_path):
        """bar柱状图"""
        data = {"labels": ["A", "B", "C"], "values": [30, 50, 20]}
        out = str(tmp_path / "bar.png")
        r = generate_chart(data, chart_type="bar", dest=out)
        assert os.path.exists(out)

    def test_line_chart(self, tmp_path):
        """line折线图"""
        data = {"labels": [1, 2, 3, 4], "values": [10, 25, 15, 30]}
        out = str(tmp_path / "line.png")
        r = generate_chart(data, chart_type="line", dest=out)
        assert os.path.exists(out)

    def test_pie_chart(self, tmp_path):
        """pie饼图"""
        data = {"labels": ["A", "B", "C"], "values": [40, 35, 25]}
        out = str(tmp_path / "pie.png")
        r = generate_chart(data, chart_type="pie", dest=out)
        assert os.path.exists(out)

    def test_scatter_chart(self, tmp_path):
        """scatter散点图"""
        data = {"labels": [1, 2, 3, 4, 5], "values": [5, 3, 4, 2, 1]}
        out = str(tmp_path / "scatter.png")
        r = generate_chart(data, chart_type="scatter", dest=out)
        assert os.path.exists(out)

    def test_chinese_labels(self, tmp_path):
        """中文标签"""
        data = {"labels": ["北京", "上海", "广州", "深圳"], "values": [100, 200, 150, 180]}
        out = str(tmp_path / "cn.png")
        r = generate_chart(data, title="城市对比", dest=out)
        assert os.path.exists(out)

    def test_negative_values(self, tmp_path):
        """负值数据"""
        data = {"labels": ["A", "B", "C"], "values": [-10, 20, -5]}
        out = str(tmp_path / "neg.png")
        r = generate_chart(data, chart_type="bar", dest=out)
        assert os.path.exists(out)

    def test_zero_values(self, tmp_path):
        """零值数据"""
        data = {"labels": ["A", "B", "C"], "values": [0, 0, 0]}
        out = str(tmp_path / "zero.png")
        r = generate_chart(data, chart_type="bar", dest=out)
        assert os.path.exists(out)

    def test_single_value(self, tmp_path):
        """单值数据"""
        data = {"labels": ["Only"], "values": [42]}
        out = str(tmp_path / "single.png")
        r = generate_chart(data, chart_type="pie", dest=out)
        assert os.path.exists(out)

    def test_many_values(self, tmp_path):
        """大量数据"""
        n = 50
        data = {"labels": [f"item{i}" for i in range(n)], "values": list(range(n))}
        out = str(tmp_path / "many.png")
        r = generate_chart(data, chart_type="bar", dest=out)
        assert os.path.exists(out)

    def test_title_only_no_labels(self, tmp_path):
        """只传title,不传x_label/y_label"""
        data = {"labels": ["A", "B"], "values": [10, 20]}
        out = str(tmp_path / "title_only.png")
        r = generate_chart(data, title="Test Chart", dest=out)
        assert os.path.exists(out)


# ============================================================
# 3. 真实场景 (3个)
# ============================================================

class TestRealScenarios:
    def test_sales_trend(self, tmp_path):
        """销售趋势图"""
        csv_file = _csv_path(tmp_path, "trend.csv", [
            {"month": "2024-01", "revenue": 50000},
            {"month": "2024-02", "revenue": 55000},
            {"month": "2024-03", "revenue": 60000},
            {"month": "2024-04", "revenue": 58000},
            {"month": "2024-05", "revenue": 65000},
        ])
        out = str(tmp_path / "trend.png")
        r = generate_chart(csv_file, chart_type="line", title="月度销售趋势",
                           x_label="月份", y_label="收入(元)", dest=out)
        assert os.path.exists(out)

    def test_user_distribution(self, tmp_path):
        """用户占比饼图"""
        data = {"labels": ["免费用户", "基础版", "专业版", "企业版"],
                "values": [10000, 5000, 2000, 500]}
        out = str(tmp_path / "dist.png")
        r = generate_chart(data, chart_type="pie", title="用户版本分布", dest=out)
        assert os.path.exists(out)

    def test_performance_comparison(self, tmp_path):
        """性能对比柱状图"""
        csv_file = _csv_path(tmp_path, "perf.csv", [
            {"endpoint": "/api/chat", "latency": 156},
            {"endpoint": "/api/tools", "latency": 45},
            {"endpoint": "/api/tasks", "latency": 78},
        ])
        out = str(tmp_path / "perf.png")
        r = generate_chart(csv_file, chart_type="bar", title="接口响应时间",
                           x_label="接口", y_label="延迟(ms)", dest=out)
        assert os.path.exists(out)


# ============================================================
# 4. 边界 (5个)
# ============================================================

class TestBoundary:
    def test_two_labels(self, tmp_path):
        """最小数据量2个"""
        data = {"labels": ["A", "B"], "values": [1, 2]}
        out = str(tmp_path / "min.png")
        r = generate_chart(data, dest=out)
        assert os.path.exists(out)

    def test_large_labels(self, tmp_path):
        """大量标签"""
        n = 200
        data = {"labels": [f"L{i}" for i in range(n)], "values": list(range(n))}
        out = str(tmp_path / "large.png")
        r = generate_chart(data, chart_type="bar", dest=out)
        assert os.path.exists(out)

    def test_float_values(self, tmp_path):
        """浮点数值"""
        data = {"labels": ["A", "B", "C"], "values": [1.5, 2.7, 3.14]}
        out = str(tmp_path / "float.png")
        r = generate_chart(data, dest=out)
        assert os.path.exists(out)

    def test_very_large_value(self, tmp_path):
        """超大数值"""
        data = {"labels": ["A", "B"], "values": [999999999, 1234567890]}
        out = str(tmp_path / "big.png")
        r = generate_chart(data, dest=out)
        assert os.path.exists(out)

    def test_special_chars_in_labels(self, tmp_path):
        """特殊字符标签"""
        data = {"labels": ["A&B", "C<D", "E>F"], "values": [10, 20, 30]}
        out = str(tmp_path / "special.png")
        r = generate_chart(data, dest=out)
        assert os.path.exists(out)


# ============================================================
# 5. 负面 (4个)
# ============================================================

class TestNegative:
    def test_nonexistent_csv(self):
        """不存在的CSV文件"""
        r = generate_chart("/nonexistent/data.csv")
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_dict_without_output_path(self):
        """dict内联数据无需output_path,工具自动生成默认输出 - 小欧 2026-07-12 适配当前真实行为"""
        data = {"labels": ["A"], "values": [10]}
        r = generate_chart(data)
        assert r["llm_data"]["status"]["exec_code"] == "success"
        assert ".png" in r["llm_data"]["summary"]

    def test_labels_values_length_mismatch(self, tmp_path):
        """labels和values长度不一致"""
        data = {"labels": ["A", "B", "C"], "values": [10, 20]}
        out = str(tmp_path / "mismatch.png")
        r = generate_chart(data, dest=out)
        assert r["llm_data"]["status"]["exec_code"] == "error"

    def test_empty_labels(self, tmp_path):
        """空labels"""
        data = {"labels": [], "values": []}
        out = str(tmp_path / "empty.png")
        r = generate_chart(data, dest=out)
        assert r["llm_data"]["status"]["exec_code"] == "error"
