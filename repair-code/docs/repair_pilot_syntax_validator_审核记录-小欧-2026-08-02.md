# 语法护栏(syntax_validator) 家族重建审核记录

**创建时间**: 2026-08-02 22:41:22
**编写人**: 小欧
**版本**: v1.0

---

## 1. 家族范围 (6 commits, 2026-07-21 ~ 2026-07-31)

| # | 日期 | commit | 内容 | 属组 | 审核状态 |
|---|------|--------|------|------|----------|
| 1 | 07-21 | 83379fbb | feat: syntax_validator.py 新建 + 接入 + BOM去扰 + BUG-002 | 核心 | ✅ 已重建 |
| 2 | 07-21 | c4367cfb | fix: BOM字面量/字段语义统一 + .pyw判定 | 核心 | ✅ 已重建 |
| 3 | 07-21 | 2deae4e7 | docs: FUNCTIONS.md 新增语法护栏章节 | docs | ✅ 已重建 |
| 4 | 07-24 | fbdbe775 | fix: tool_fc_helper 去除 str(e) 截断(调用方自行决定) | 核心 | ✅ 已重建 |
| 5 | 07-28 | e4ee7475 | fix: shell_prompt_templates.py 去除UTF-8 BOM(efbbbf) | 其它 | ❌ 不可重建(文件丢失) |
| 6 | 07-31 | d578de1a | refactor: tooling import 清理 | 其它 | ⚠️ 未单独实施(视为家族外) |

## 2. 放置位置(经核实,与初始假设修正)

- **模块路径**: `backend/app/tools/toolhelper/syntax_validator.py` (初始我误建于 `fundamental/`, 经
  `backend/tests/test_syntax_guardrail_deep.py:13` 的 `from app.tools.toolhelper import syntax_validator as sv`
  **校正为 toolhelper/**)。
- `__init__.py` 为空, 模块仅被直接导入, 不纳入注册表(内部纯逻辑, 符合 SRP)。

## 3. 重建要点

### 3.1 新建 `toolhelper/syntax_validator.py`
- `detect_language(file_path="", content=None) -> str` — 由 `_CODE_EXT` 映射(用 `os.path.splitext` 非 `endswith`,
  修正 `.pyw` 被 `.py` 吞的问题);未命中则看 shebang(`#!...python`);否则 `unknown`(fail-open)。
- `validate_syntax(content, language, file_path=None) -> SyntaxCheckResult` — 查 `VALIDATORS` 注册表;
  未注册语言 fail-open `valid=True`; 校验器抛任何非预期异常不 500, 降级为 `error="校验器异常: ..."`。
- `SyntaxCheckResult` — `valid/language/error/line/suggestion`;`error_text()` 统一组装(含"行"/"建议")。
- `_strip_bom` — BOM去扰(BUG-002): UTF-8 BOM(`\ufeff`)在 compile/json.loads/yaml.safe_load 前 strip。
- python 校验: `compile('exec')`, 捕 `SyntaxError`/`RecursionError`, 补建议(r'raw string' 等)。
- json 校验: `json.loads`, 错误含"JSON"。
- yaml 校验: `yaml.safe_load`, 错误含"YAML"。
- `VALIDATORS` — OCP 注册表, 新语言加一行。

### 3.2 tool_fc_helper.py
- `validate_python_content` 收敛为委托 `validate_syntax(content, "python", file_path).error_text()` — 去重(SRP),
  同时继承 BOM去扰+BUG-002, 且**无 str(e) 截断**(fbdbe775 终态)。

### 3.3 edit_text_file.py
- 内联 `compile()` 换为 `validate_syntax(...)`; **行为变更**: 语法错误对 ALL 模式(`once`/`all`)均阻断写入
  (原 `once` 仅 warning 放行)。 — 经 `test_invalid_replace_blocked` 验证。

### 3.4 write_text_file.py
- **新增护栏**:`detect_language`+`validate_syntax`(多语言: python/json/yaml)。
- 非 append 语法错误 → `build_error` 阻断; append 语法错误 → 仍写入, 降级 `build_warning` (含"语法")。
- .md/.txt 等 unknown 语言 fail-open 放行。 — 经 `TestWritetextIntegration` 7 用例验证。

## 4. 验证结果 (在临时暂存到 live backend/app 后运行, 随后已恢复至 v0.18.27 基线)

```
tests/test_syntax_validator.py            9 passed
tests/test_syntax_guardrail_deep.py      50 passed
============================== 59 passed in 1.74s ==============================
```
覆盖: detect_language(扩展名/大小写/路径含点/.pyw/shebang)、python(json/yaml BOM)、BUG-002(return outside)、
suggestion、fail-open、OCP、健壮性(validator抛RuntimeError不500, RecursionError不崩)、error_text、
writetext/edittext 真实调用链、模糊测试、合法代码不误杀。

## 5. 无法重建的 2 项 (原因为: 7.20-7.31 提交树缺失, 仅凭截断的 commit-message 推断)

- **BUG-002 原始形态**: 原 tree 缺失。经 `test_bug002_repro_return_outside` 推断为
  "顶层 return 等 SyntaxError 未被统一捕获→误写"。我实现为 `compile('exec')` 后
  `except SyntaxError/RecursionError` 全捕 — 终态可通过对应测试。
- **e4ee7475 / shell_prompt_templates.py**: 该文件在 v0.18.27 基线与 G 盘均不存在,
  它是 7.28 当天通过 `28446506e`(同日) 新建的 lost commit 的一部分, 内容完全不可恢复。
  建议后续从 E:\tmp_rec 磁盘恢复件复核, 或作废该 fix(其它 BOM 防护已由 syntax_validator 覆盖)。

## 6. 审计结论

家族核心(83379fbb + c4367cfb + 2deae4e7 + fbdbe775) **100% 复核合格** (59/59 测试绿)。
存于 `_rewrite/backend/` 待合并审核; live `backend/app` 已恢复为**pristine v0.18.27**
(`git diff HEAD -- backend/app` 为空)。

**更新时间**: 2026-08-02 22:41:22
**编写人**: 小欧
