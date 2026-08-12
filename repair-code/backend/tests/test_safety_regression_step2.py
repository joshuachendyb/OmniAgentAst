# -*- coding: utf-8 -*-
"""
Safety 回归专项测试 — 步骤2 11项 + 步骤1实施后 bug 复核修复(BUG-A/B/C/D/E) — 小欧 2026-08-10

覆盖:
  [步骤2 11项] 见 doc-8月优化/项目根目录定义混乱分析报告-小欧-2026-08-09.md 步骤2 回归验证
  [BUG回归]    BUG-A(delete R6不被临时授权绕过) BUG-B(download相对dest不误拦)
               BUG-C(rename文件名dest不误拦) BUG-D(auth_path指向真正越权参数)
               BUG-E(临时授权一次一申请, 操作结束即清除)
"""
# 编辑历史:
# 2026-08-10 - 小欧 - 新建: 固化步骤2 11项回归用例 + BUG-A/B/C/D/E 修复回归; 纯Safety层单测, 不依赖真实LLM/后端
# 2026-08-10 - 小欧 - E1 扩展(第二次代码更新, 第3章设计框架): 禁区分级(系统/非系统)+读放行同步用例——
#   用例2 拆分为读放行(readtext→放行)/非系统禁区写任务级授权(writetext/copy/rename→requires_confirmation)/
#   非系统禁区删硬拦(delete→blocked); 用例3/4 dest/path 多参数指向代码库根 → 非系统禁区写任务级授权(非硬拦);
#   用例9 改为验证非系统禁区删授权仍硬拦 + 系统禁区写授权仍硬拦; 新增别名归一读放行校验
# 2026-08-10 - 小欧 - E3-E5 新增(第三次代码更新, 三堂会审 BUG-1/2/3 回归): E3 别名写工具(write_text_file等)
#   归一化后仍走路径校验(不可绕过白名单/禁区); E4 参数别名(rename.new_name/copy.dst)归一化后 dest 仍被校验;
#   E5 writetext 写保护对别名(write_text_file)同样生效(真实大文件触发, 与 test_bug_write_size_protection 同构)
import os
from pathlib import Path

import pytest

from app.services.safety.temp_auth import grant_temp_auth, clear_temp_auth


@pytest.fixture(scope="module", autouse=True)
def _ensure_tools():
    from app.tools import ensure_tools_registered
    ensure_tools_registered()
    yield


@pytest.fixture(autouse=True)
def _clean_temp_auth():
    """每个用例后清空临时授权, 防跨用例污染(临时授权本应per-request隔离)"""
    yield
    clear_temp_auth()


@pytest.fixture(scope="module")
def checker():
    from app.services.safety.tool_safety_checker import get_tool_safety_checker
    return get_tool_safety_checker()


@pytest.fixture(scope="module")
def code_root():
    from app.config import get_code_root
    return str(Path(get_code_root()).resolve())


@pytest.fixture(scope="module")
def project_root():
    from app.config import get_config
    return str(Path(get_config().get_project_root()).resolve())


class _FakeConfig:
    """模拟 config 对象(用例5/6 配置缺省/授权目录) — 小欧 2026-08-10"""

    def __init__(self, project_root=None, allowed_dirs=None):
        self._root = project_root
        self._dirs = allowed_dirs

    def get_project_root(self):
        return self._root if self._root else str(Path.home())

    def get_allowed_dirs(self):
        return list(self._dirs) if self._dirs else []


# ============================================================
# BUG-A 回归: delete R6(允许根外递归) 不受临时授权影响
# ============================================================

def test_bug_a_delete_r6_blocked_even_with_temp_auth(checker):
    """R6: 允许根外递归删除, 即使已临时授权也 blocked(BUG-A修复)"""
    grant_temp_auth(r"D:\outside", recursive=True)
    r = checker.check_before_execute("delete", {"path": r"D:\outside", "recursive": True, "force": True})
    assert r.blocked is True, f"R6应硬拦, 实际 blocked={r.blocked}"


def test_bug_a_delete_r4_inside_confirm(checker, project_root):
    """R4: 允许根内递归 → 确认(不拦不直接放)"""
    r = checker.check_before_execute("delete", {"path": project_root, "recursive": True})
    assert r.blocked is False and r.requires_confirmation is True, \
        f"R4应确认, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


# ============================================================
# BUG-B/C 回归: download相对dest / rename文件名dest 不误拦
# ============================================================

def test_bug_b_download_relative_dest_allowed(checker):
    """download.dest 为相对下载目录路径 → 解析到项目根/download → 放行(BUG-B修复)"""
    r = checker.check_before_execute("download", {"url": "http://x.com/f.png", "dest": "aaa.png"})
    assert r.blocked is False and r.requires_confirmation is False, \
        f"download相对dest应放行, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


def test_bug_b_download_subpath_dest_allowed(checker):
    """download.dest 子路径 → 放行"""
    r = checker.check_before_execute("download", {"url": "http://x.com/f.png", "dest": "sub/x.png"})
    assert r.blocked is False and r.requires_confirmation is False


def test_bug_c_rename_filename_dest_allowed(checker, project_root):
    """rename.dest 纯文件名 → 真实路径=源同目录 → 放行(BUG-C修复)"""
    r = checker.check_before_execute("rename", {"path": os.path.join(project_root, "a.txt"), "dest": "new_name.txt"})
    assert r.blocked is False and r.requires_confirmation is False, \
        f"rename文件名dest应放行, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


# ============================================================
# BUG-D 回归: auth_path 指向真正越权参数
# ============================================================

@pytest.mark.parametrize("tool,params", [
    ("copy", {"path": r"E:\test_dir\a.txt", "dest": r"D:\out\b.txt"}),
    ("move", {"path": r"E:\test_dir\a.txt", "dest": r"D:\out\b.txt"}),
    ("compress", {"path": r"E:\test_dir\a.txt", "dest": r"D:\out.zip"}),
    ("extract", {"path": r"E:\test_dir\a.zip", "dest": r"D:\out"}),
])
def test_bug_d_auth_path_points_to_real_violator(checker, tool, params):
    """auth_path 应指向真正越权的 dest, 而非合法 path(BUG-D修复)"""
    r = checker.check_before_execute(tool, params)
    assert r.requires_confirmation is True and r.blocked is False
    assert r.auth_path == params["dest"], \
        f"{tool} auth_path应为越权dest={params['dest']!r}, 实际 {r.auth_path!r}"


# ============================================================
# BUG-E 回归: 临时授权一次一申请, 递归生效, clear后失效
# ============================================================

def test_bug_e_temp_auth_recursive_and_clear(checker):
    """授权目录递归放行其子目录树; clear后立即失效(补A一次一申请)"""
    grant_temp_auth(r"D:\娱乐\视频", recursive=True)
    for p in [r"D:\娱乐\视频", r"D:\娱乐\视频\a\b\c.txt"]:
        r = checker.check_before_execute("writetext", {"path": p, "content": "x"})
        assert r.blocked is False and r.requires_confirmation is False, \
            f"授权范围内应放行 {p}, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"
    clear_temp_auth()
    r = checker.check_before_execute("writetext", {"path": r"D:\娱乐\视频\a.txt", "content": "x"})
    assert r.requires_confirmation is True, "clear后应重新要求授权, 不得缓存复用(BUG-E修复)"


# ============================================================
# 步骤2 11项 回归
# ============================================================

def test_case1_delete_recycle_r4_confirm(checker):
    """用例1: E:\\test_dir\\_cleanup_recycle_20260809 递归删除 → R4 确认(不再 R6)"""
    r = checker.check_before_execute("delete", {"path": r"E:\test_dir\_cleanup_recycle_20260809", "recursive": True})
    assert r.blocked is False and r.requires_confirmation is True, \
        f"应为R4确认, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


@pytest.mark.parametrize("tool,params", [
    ("readtext", {"path": r"F:\OmniAgentAs-repair\backend\a.py"}),
    ("writetext", {"path": r"F:\OmniAgentAs-repair\backend\b.py", "content": "x"}),
    ("delete", {"path": r"F:\OmniAgentAs-repair\backend\b.py", "recursive": False}),
    ("copy", {"path": r"E:\test_dir\a.txt", "dest": r"F:\OmniAgentAs-repair\backend\b.py"}),
    ("rename", {"path": r"F:\OmniAgentAs-repair\backend\a.py", "dest": "new.py"}),
])
def test_case2_code_root_zone_grading(checker, tool, params):
    """用例2(禁区分级, E1): 非系统禁区(代码库根) — 读✅放行/写⚠️任务级授权/删❌硬拦(3.2.10/表五)"""
    r = checker.check_before_execute(tool, params)
    if tool == "readtext":
        assert r.blocked is False and r.requires_confirmation is False, \
            f"{tool} 读代码库根应放行(读一律允许), 实际 blocked={r.blocked} confirm={r.requires_confirmation}"
    elif tool == "delete":
        assert r.blocked is True, f"{tool} 删代码库根应硬拦(删永不授权), 实际 blocked={r.blocked} confirm={r.requires_confirmation}"
    else:
        assert r.blocked is False and r.requires_confirmation is True, \
            f"{tool} 写代码库根应任务级授权确认, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


@pytest.mark.parametrize("tool,dest_kw", [
    ("copy", "dest"), ("move", "dest"), ("compress", "dest"), ("extract", "dest"),
])
def test_case3_dest_to_code_root_task_auth(checker, tool, dest_kw, code_root, project_root):
    """用例3(E1): copy/move/compress/extract 的 dest 指向代码库根 → 非系统禁区写任务级授权(3.2.13, 非硬拦)"""
    params = {"path": os.path.join(project_root, "a.txt"), dest_kw: os.path.join(code_root, "x.txt")}
    r = checker.check_before_execute(tool, params)
    assert r.blocked is False and r.requires_confirmation is True, \
        f"{tool} dest指向代码库根应任务级授权确认, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


def test_case4_multi_param_to_code_root_task_auth(checker, code_root):
    """用例4(E1): 同工具多路径参数(path+dest 均指向代码库根) → 非系统禁区写任务级授权(漏洞B: 全参数校验)"""
    r = checker.check_before_execute("copy", {
        "path": os.path.join(code_root, "a.py"),
        "dest": os.path.join(code_root, "b.py"),
    })
    assert r.blocked is False and r.requires_confirmation is True, \
        f"多参数指向代码库根应任务级授权确认, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


def test_case5_default_project_root_is_home(monkeypatch):
    """用例5: 配置缺省 → 项目根=用户主目录"""
    import app.config as config_mod
    monkeypatch.setattr(config_mod, "get_config", lambda: _FakeConfig(project_root=""))
    from app.services.safety.path_safe_check import _get_project_root_safety, validate_path
    root = _get_project_root_safety()
    assert str(root).lower() == str(Path.home()).lower(), f"缺省项目根应为用户主目录, 实际 {root}"
    is_valid, _, _ = validate_path(str(Path.home() / "test.txt"))
    assert is_valid is True, "主目录路径应放行"


def test_case6_allowed_dirs_operations_pass(monkeypatch, checker):
    """用例6: 授权目录内操作 → 放行(白名单+删除判定)"""
    import app.config as config_mod
    monkeypatch.setattr(config_mod, "get_config", lambda: _FakeConfig(project_root=r"E:\test_dir", allowed_dirs=[r"D:\授权目录"]))
    r = checker.check_before_execute("copy", {"path": r"D:\授权目录\a.txt", "dest": r"D:\授权目录\b.txt"})
    assert r.blocked is False and r.requires_confirmation is False, "授权目录内copy应放行"
    r = checker.check_before_execute("delete", {"path": r"D:\授权目录\sub", "recursive": True})
    assert r.blocked is False and r.requires_confirmation is True, "授权目录内递归删除应为R4确认"
    r = checker.check_before_execute("delete", {"path": r"D:\授权目录\a.txt", "recursive": False})
    assert r.blocked is False and r.requires_confirmation is False, "授权目录内普通删除应为R3免确认"


def test_case7_unallowed_drive_not_silently_allowed(checker):
    """用例7: 未授权盘位置 → 不得直接放行(需临时授权确认)"""
    r = checker.check_before_execute("writetext", {"path": r"D:\娱乐\视频\a.txt", "content": "x"})
    assert r.blocked or r.requires_confirmation, "未授权盘位置不得直接放行"


def test_case8_temp_auth_one_request_recursive(checker):
    """用例8: 临时授权一次一申请支持递归; clear后重新申请"""
    grant_temp_auth(r"D:\娱乐\视频", recursive=True)
    r = checker.check_before_execute("copy", {"path": r"D:\娱乐\视频\a.txt", "dest": r"D:\娱乐\视频\sub\b.txt"})
    assert r.blocked is False and r.requires_confirmation is False, "临时授权内递归应放行"
    clear_temp_auth()
    r = checker.check_before_execute("copy", {"path": r"D:\娱乐\视频\a.txt", "dest": r"D:\娱乐\视频\b.txt"})
    assert r.requires_confirmation is True, "clear后需重新申请(不缓存复用)"


def test_case9_forbidden_zone_not_authorized_for_delete(checker, code_root):
    """用例9(E1): 非系统禁区删即使临时授权也→硬拦; 系统禁区写/删授权也→硬拦(3.2.9/3.2.10, 授权无效)"""
    # 非系统禁区删: 已任务级授权代码库根, 删仍硬拦(删永不授权)
    grant_temp_auth(code_root, recursive=True)
    r = checker.check_before_execute("delete", {"path": os.path.join(code_root, "a.py"), "recursive": False})
    assert r.blocked is True, "非系统禁区删即使授权也硬拦(删永不授权)"
    # 系统禁区写: 授权无效, 硬拦(如 C:\Windows)
    r = checker.check_before_execute("writetext", {"path": r"C:\Windows\a.txt", "content": "x"})
    assert r.blocked is True, "系统禁区写即使授权也硬拦(永不授权)"


def test_case10_allowed_dirs_containing_code_root_rejected():
    """用例10: allowed_dirs 含代码库根 → 配置加载报错"""
    from app.config import Config, _get_code_root
    cfg = Config()
    cfg._config_data = {"app": {"allowed_dirs": [str(_get_code_root())]}}
    with pytest.raises(ValueError):
        cfg.get_allowed_dirs()


def test_case11_no_project_named_code_root_fn():
    """用例11: 全项目已无 project 命名的代码库根函数(名实分离完成)"""
    import app.config as config_mod
    assert not hasattr(config_mod, "get_default_project_root"), "get_default_project_root 已废弃应移除"
    assert not hasattr(config_mod, "_get_project_root"), "_get_project_root 已改名 _get_code_root"
    assert hasattr(config_mod, "get_code_root") and hasattr(config_mod, "_get_code_root")


def test_e1_alias_normalize_read_allow(checker, code_root):
    """E1(9.3.8): LLM传 list_directory/read_text_file 别名 → 归一后读代码库根放行(发现5, P2 normalize_tool_name)"""
    cases = [
        ("list_directory", {"path": code_root}),
        ("read_text_file", {"path": os.path.join(code_root, "a.py")}),
    ]
    for tool, params in cases:
        r = checker.check_before_execute(tool, params)
        assert r.blocked is False and r.requires_confirmation is False, \
            f"别名 {tool} 读代码库根应放行(读一律允许), 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


def test_e2_task_dir_auth_removed():
    """E2(9.3.8, 撤销后): 任务中目录解析功能点已去掉(北京老陈 2026-08-10) — _parse_task_auth_paths 不存在,
    目录权限全部走 LLM 工具参数路径进临时名单(3.2.12)"""
    import app.services.agent.initialize_run_state as irmod
    import app.services.agent.react_cycle as rcmod
    assert not hasattr(irmod, "_parse_task_auth_paths"), "_parse_task_auth_paths 已撤销应移除"
    assert not hasattr(irmod, "_TASK_PATH_RE"), "_TASK_PATH_RE 已撤销应移除"
    # R1 clear_temp_auth 保留(task 级清零点, 工具级临时授权仍需)
    import re
    src = open(rcmod.__file__, encoding="utf-8").read()
    assert re.search(r"clear_temp_auth\(\)", src), "R1 clear_temp_auth 应保留(task 级清零点)"


# ============================================================
# E3-E5 (三堂会审 BUG-1/2/3 回归, 北京老陈 2026-08-10): 别名不可绕过安全校验
# ============================================================

def test_e3_alias_write_tool_cannot_bypass_path_check(checker, code_root):
    """E3(BUG-1): LLM 传写工具别名(如 write_text_file/writefile) → 归一化后仍走路径校验 —
    原 `tool_name not in path_tools` 用原始名判, 别名不在注册名集合 → 直接放行绕过白名单/禁区"""
    for alias in ("write_text_file", "writefile", "writeetext"):
        r = checker.check_before_execute(alias, {"path": os.path.join(code_root, "b.py"), "content": "x"})
        assert r.blocked is False and r.requires_confirmation is True, \
            f"别名 {alias} 写代码库根应任务级授权确认(非绕过放行), 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


def test_e4_alias_param_cannot_bypass_dest_check(checker, code_root):
    """E4(BUG-3): LLM 传参数别名(如 rename 的 new_name/copy 的 dst) → 归一化后 dest 仍被校验 —
    原 hit_params 直接查原始 params, 别名参数命中不了 _PATH_PARAM_KEYS → 越权 dest 漏检"""
    # rename: new_name 别名指向代码库根(非法目标) → 归一化 dest 后应任务级授权确认
    r = checker.check_before_execute("rename", {"path": r"E:\test_dir\a.txt", "new_name": "new.py"})
    assert r.blocked is False and r.requires_confirmation is False, \
        f"rename new_name 纯文件名应放行, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"
    # copy: dst 别名指向代码库根 → 归一化 dest 后应任务级授权确认(非绕过放行)
    r = checker.check_before_execute("copy", {"src": r"E:\test_dir\a.txt", "dst": os.path.join(code_root, "b.py")})
    assert r.blocked is False and r.requires_confirmation is True, \
        f"copy dst 别名指向代码库根应任务级授权确认, 实际 blocked={r.blocked} confirm={r.requires_confirmation}"


def test_e5_alias_read_write_protect_applies(checker):
    """E5(BUG-2): writetext 写保护对别名(write_text_file)同样生效 —
    原 `tool_name == _WRITE_RISK_TOOL("writetext")` 用原始名, 别名不触发写入大小保护"""
    # 真实创建大文件, 再用别名写远小于20%的内容 → 应触发写保护 blocked(与 test_bug_write_size_protection 同构)
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("A" * 5000)
        tmp_path = f.name
    try:
        grant_temp_auth(os.path.dirname(tmp_path), recursive=True)
        r = checker.check_before_execute("write_text_file", {"path": tmp_path, "content": "tiny"})
        assert r.blocked is True, f"别名 write_text_file 写保护应生效(新内容远小于旧内容), 实际 blocked={r.blocked}"
    finally:
        os.unlink(tmp_path)
