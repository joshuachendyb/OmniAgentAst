# -*- coding: utf-8 -*-
"""
read_text_file 参数组合与内容测试 - 小健 2026-06-24

测试案范:
1. ✅ Schema驱动:按schema参数要求设计测试用例
2. ✅ 内容丰富性:测试数据来自真实业务场景,不少于100行
3. ✅ 验证完整性:验证文件创建,内容数量,样式正认,内容正认
4. ✅ 测试覆盖:参数组合,功能,边界,为面测试
5. ✅ 问题发现:测试目的是发现bug,不是为了让测试通过
"""
import pytest
import asyncio
from pathlib import Path
from app.tools.file.read_text_file import readtext
from app.tools.tool_response import is_success, is_error, is_warning


class TestReadTextFileParamCombinations:
    """参数组合测试 - 穷举所有参数组合"""

    @pytest.mark.asyncio
    async def test_only_filepath(self, setup_test_files):
        """组合1: 仅必填参数file_path(读全文)"""
        result = await readtext(path=setup_test_files["text_file"])

        assert is_success(result), f"读取失败: {result}"
        assert "data" in result
        assert "content" in result["data"]
        # 进化: total_lines 已从 data 移至 llm_data.metrics(小沈 2026-07-05 重构)
        assert "total_lines" in result["llm_data"]["metrics"]
        assert result["llm_data"]["metrics"]["total_lines"]["value"] > 100, "内容少于100行"
        assert len(result["data"]["content"]) > 0

    @pytest.mark.asyncio
    async def test_filepath_with_tail(self, setup_test_files):
        """组合2: file_path + tail(读尾部N行)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            tail=20
        )

        assert is_success(result), f"读取失败: {result}"
        # 进化: line_count 移至 llm_data.metrics.lines.value; tail 不再回显于 data
        assert result["llm_data"]["metrics"]["lines"]["value"] == 20, "tail应返回最后20行"

    @pytest.mark.asyncio
    async def test_filepath_with_positive_offset_and_limit(self, setup_test_files):
        """组合3: file_path + offset(正数)+ limit(分页)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            offset=10,
            limit=50
        )

        assert is_success(result), f"读取失败: {result}"
        # 进化: line_count/start_line/end_line 已从 data 移至 llm_data.metrics / status.message
        assert result["llm_data"]["metrics"]["lines"]["value"] == 50
        msg = result["llm_data"]["status"]["message"]
        assert "第10-59行" in msg, f"应返回第10-59行,实际: {msg}"

    @pytest.mark.asyncio
    async def test_filepath_with_encoding(self, setup_test_files):
        """组合4: file_path + encoding"""
        result = await readtext(
            path=setup_test_files["text_file"],
            encoding="utf-8"
        )

        assert is_success(result), f"读取失败: {result}"
        # 进化: encoding 不再回显于 data,使用编码后反映在 status.message
        assert "编码:utf-8" in result["llm_data"]["status"]["message"]

    @pytest.mark.asyncio
    async def test_tail_with_offset_should_error(self, setup_test_files):
        """组合5: file_path + tail + offset(应该报错)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            tail=20,
            offset=10
        )

        assert is_error(result), "tail不能与offset同时使用"
        assert "tail参数不能与offset/limit同时使用" in result["llm_data"]["status"]["detail"]

    @pytest.mark.asyncio
    async def test_positive_offset_without_limit_should_error(self, setup_test_files):
        """组合6: file_path + offset(正数)无limit(应该报错)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            offset=10
        )

        assert is_error(result), "offset为正数时必须带limit"
        # 进化: 错误detail文案已更新
        assert "offset参数必须同时提供limit参数" in result["llm_data"]["status"]["detail"]

    @pytest.mark.asyncio
    async def test_limit_without_offset_should_success(self, setup_test_files):
        """组合7: file_path + limit无offset(读前N行)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            limit=10
        )

        assert is_success(result), "limit单独使用应该成功"
        # 进化: line_count 移至 llm_data.metrics.lines.value
        assert result["llm_data"]["metrics"]["lines"]["value"] == 10

    @pytest.mark.asyncio
    async def test_offset_zero_should_error(self, setup_test_files):
        """组合8: file_path + offset=0(应该报错)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            offset=0
        )

        assert is_error(result), "offset不能为0"
        # 进化: 错误detail文案已更新
        assert "offset参数不能小于1" in result["llm_data"]["status"]["detail"]


class TestReadTextFileFeatures:
    """功能测试 - 每个功能点至少2个测试"""

    @pytest.mark.asyncio
    async def test_read_python_file(self, setup_test_files):
        """功能1: 读取Python代码文件"""
        result = await readtext(path=setup_test_files["py_file"])

        assert is_success(result)
        content = result["data"]["content"]
        assert "class UserService" in content, "未找到类定义"
        assert "async def get_user" in content, "未找到方法定义"

    @pytest.mark.asyncio
    async def test_read_markdown_file(self, setup_test_files):
        """功能2: 读取Markdown文件"""
        result = await readtext(path=setup_test_files["text_file"])

        assert is_success(result)
        content = result["data"]["content"]
        assert "# 技术审计报告" in content, "未找到标题"
        assert "## 一,执行摘要" in content, "未找到二级标题"
        assert "```python" in content, "未找到代码块"

    @pytest.mark.asyncio
    async def test_encoding_auto_detection(self, temp_input_dir):
        """功能3: 编码自动检测(GBK文件)"""
        file_path = Path(temp_input_dir) / "gbk_file.txt"
        gbk_content = "中文测试内容\n这是GBK编码的文件\n包含中文字符"
        file_path.write_text(gbk_content, encoding="gbk")

        result = await readtext(path=str(file_path))

        assert is_success(result), f"GBK编码检测失败: {result}"
        assert "中文测试内容" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_read_with_utf8_sig(self, temp_input_dir):
        """功能4: 读取UTF-8-SIG文件(带BOM)"""
        file_path = Path(temp_input_dir) / "utf8sig.txt"
        content = "UTF-8-SIG测试\n带BOM标记的文件"
        file_path.write_text(content, encoding="utf-8-sig")

        result = await readtext(path=str(file_path))

        assert is_success(result)
        assert "UTF-8-SIG测试" in result["data"]["content"]


class TestReadTextFileBoundary:
    """边界测试 - 特殊字符,长内容,空值等"""

    @pytest.mark.asyncio
    async def test_special_characters(self, temp_input_dir):
        """边界1: 特殊字符"""
        file_path = Path(temp_input_dir) / "special.txt"
        content = "特殊字符:<>&\"'\\n中文:测试\nemoji:🎉🎊\\n制表符:\\t内容"
        file_path.write_text(content, encoding="utf-8")

        result = await readtext(path=str(file_path))

        assert is_success(result)
        assert "特殊字符" in result["data"]["content"]
        assert "🎉" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_long_lines(self, temp_input_dir):
        """边界2: 超长行 — 治理(2026-07-20 小欧): Tool层零限制, 截断唯一收口于 observation_formatter;
        单行超宽由 formatter 按 OBS_READTEXT_MAX_ROW_CHARS 截断并标注原长; 超大文件由 offset/limit 分页读取"""
        file_path = Path(temp_input_dir) / "long_line.txt"
        long_line = "A" * 10000
        content = f"{long_line}\n第二行内容"
        file_path.write_text(content, encoding="utf-8")

        result = await readtext(path=str(file_path))

        assert is_success(result)
        # 治理后: Tool 返回完整内容(零限制), 不在 Tool 层做字符截断
        assert long_line in result["data"]["content"], "Tool层应零限制返回完整内容"
        # 截断收口于 formatter: 单行超宽被截断并标注原长, 避免超大 observation 误导 LLM
        from app.services.agent.observation_formatter import build_observation_text
        obs = build_observation_text(result, tool_name="readtext", tool_params={"file_path": str(file_path)})
        assert "已截断" in obs, "formatter 应截断超长行"
        assert "原" in obs, "formatter 应标注原始长度"

    @pytest.mark.asyncio
    async def test_empty_lines(self, temp_input_dir):
        """边界3: 空行文件"""
        file_path = Path(temp_input_dir) / "empty_lines.txt"
        content = "\n\n\n\n\n"
        file_path.write_text(content, encoding="utf-8")

        result = await readtext(path=str(file_path))

        assert is_success(result)
        # 进化: total_lines 移至 llm_data.metrics.total_lines.value
        assert result["llm_data"]["metrics"]["total_lines"]["value"] == 5

    @pytest.mark.asyncio
    async def test_offset_exceeds_file_length(self, setup_test_files):
        """边界4: offset超出文件长度"""
        result = await readtext(
            path=setup_test_files["text_file"],
            offset=9999,
            limit=10
        )

        assert is_warning(result), "offset超出范围应返回warning"
        assert "超出文件范围" in result["llm_data"]["status"]["detail"]

    @pytest.mark.asyncio
    async def test_limit_zero_should_error(self, setup_test_files):
        """边界5: limit=0(应该报错)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            offset=10,
            limit=0
        )

        assert is_error(result), "limit必须>=1"

    @pytest.mark.asyncio
    async def test_limit_negative_should_error(self, setup_test_files):
        """边界6: limit为为数(应该报错)"""
        result = await readtext(
            path=setup_test_files["text_file"],
            offset=10,
            limit=-5
        )

        assert is_error(result), "limit必须>=1"


class TestReadTextFileNegative:
    """为面测试 - 错误路径,权限问题等"""

    @pytest.mark.asyncio
    async def test_file_not_exist(self, temp_output_dir):
        """为面1: 文件不存在"""
        result = await readtext(path=f"{temp_output_dir}/not_exist.txt")

        assert is_error(result)
        # 进化: 错误detail文案已更新(路径不存在)
        assert "路径不存在" in result["llm_data"]["status"]["detail"]

    @pytest.mark.asyncio
    async def test_read_directory_should_error(self, temp_input_dir):
        """为面2: 读取目录(应该报错)"""
        result = await readtext(path=str(temp_input_dir))

        assert is_error(result)
        # 目录应被拒绝;detail含被拒路径即可(避免跨文件中文编码不一致比较)
        assert str(temp_input_dir) in result["llm_data"]["status"]["detail"]

    @pytest.mark.asyncio
    async def test_invalid_encoding(self, setup_test_files):
        """为面3: 无效编码"""
        result = await readtext(
            path=setup_test_files["text_file"],
            encoding="invalid-encoding-12345"
        )

        # 应该回退到自动检测或报错
        # 根据实现,可能是success(自动检测)或error
        # 这里验证不会崩溃
        assert "llm_data" in result

    @pytest.mark.asyncio
    async def test_empty_filepath_should_error(self):
        """为面4: 空文件路径"""
        result = await readtext(path="")

        assert is_error(result)

    @pytest.mark.asyncio
    async def test_binary_file_should_error(self, temp_input_dir):
        """为面5: 读取二进制文件(应该报错)"""
        file_path = Path(temp_input_dir) / "test.png"
        file_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        result = await readtext(path=str(file_path))

        assert is_error(result), "二进制文件应该被拒绝"
        assert "媒体文件" in result["llm_data"]["status"]["detail"] or "二进制" in result["llm_data"]["status"]["detail"]


class TestReadTextFileRealScenarios:
    """真实场景测试 - 使用真实业务数据"""

    @pytest.mark.asyncio
    async def test_read_log_file_tail(self, temp_input_dir):
        """真实场景1: 读取日志文件尾部(查看最新日志)"""
        log_file = Path(temp_input_dir) / "app.log"
        log_content = "\n".join([
            f"2026-06-24 10:{i:02d}:00 INFO - Processed request {i}"
            for i in range(100)
        ])
        log_file.write_text(log_content, encoding="utf-8")

        result = await readtext(
            path=str(log_file),
            tail=20
        )

        assert is_success(result)
        # 进化: line_count 移至 llm_data.metrics.lines.value
        assert result["llm_data"]["metrics"]["lines"]["value"] == 20
        # 验证是最新的20行
        assert "Processed request 99" in result["data"]["content"]

    @pytest.mark.asyncio
    async def test_read_code_with_pagination(self, setup_test_files):
        """真实场景2: 分页读取大代码文件"""
        result_page1 = await readtext(
            path=setup_test_files["text_file"],
            offset=1,
            limit=50
        )

        result_page2 = await readtext(
            path=setup_test_files["text_file"],
            offset=51,
            limit=50
        )

        assert is_success(result_page1)
        assert is_success(result_page2)
        # 进化: start_line/end_line 已移至 status.message(格式"第X-Y行")
        msg1 = result_page1["llm_data"]["status"]["message"]
        assert "第1-50行" in msg1, f"第1页应返回第1-50行,实际: {msg1}"
        msg2 = result_page2["llm_data"]["status"]["message"]
        assert "第51-100行" in msg2, f"第2页应返回第51-100行,实际: {msg2}"

    @pytest.mark.asyncio
    async def test_read_config_file(self, setup_test_files):
        """真实场景3: 读取配置文件"""
        result = await readtext(path=setup_test_files["json_file"])

        assert is_success(result)
        content = result["data"]["content"]
        assert '"name": "test"' in content
        assert '"version": "1.0.0"' in content


class TestReadTextFileMetrics:
    """Metrics验证测试 - 验证返回的统计信息"""

    @pytest.mark.asyncio
    async def test_metrics_structure(self, setup_test_files):
        """验证metrics结构"""
        result = await readtext(path=setup_test_files["text_file"])

        assert is_success(result)
        llm_data = result["llm_data"]

        # 验证metrics存在
        assert "metrics" in llm_data
        metrics = llm_data["metrics"]

        # 验证lines metric
        assert "lines" in metrics
        assert "value" in metrics["lines"]
        assert "text" in metrics["lines"]
        assert metrics["lines"]["value"] > 0

        # 验证bytes metric
        assert "bytes" in metrics
        assert metrics["bytes"]["value"] > 0

    @pytest.mark.asyncio
    async def test_action_structure(self, setup_test_files):
        """验证action结构"""
        result = await readtext(path=setup_test_files["text_file"])

        assert is_success(result)
        action = result["llm_data"]["action"]

        assert action["tool"] == "readtext"
        assert action["tool_zh"] == "读取"
        assert "target" in action
        assert "params" in action
