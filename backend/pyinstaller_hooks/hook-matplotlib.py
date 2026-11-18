# ------------------------------------------------------------------
# 自定义 matplotlib 打包 hook — 小欧 2026-11-18
# 覆盖 PyInstaller 内置 hook-matplotlib.py:
#   内置原版用 (mpl_data_dir(), "matplotlib/mpl-data") 整目录收集 mpl-data,
#   把 stylelib/_classic_test_patch.mplstyle(测试样式, 运行时绝不加载)一并带入产物。
# 本 hook 用 collect_data_files(subdir='mpl-data') 收集, 经 excludes 排除该测试样式。
#   实测: mpl-data 无 .py/.pyc, collect_data_files 与整目录收集等效(199 项, 排除后 198 项)。
#   保留内置 delvewheel 逻辑(matplotlib>=3.7 Windows wheel 的 DLL 加载顺序文件)。
# 注意: 自定义 hook 目录经 spec 的 hookspath 传入, 优先级 USER_HOOKS(1000) > UPSTREAM(0),
#   因此本文件完整覆盖内置同名 hook, 不污染 PyInstaller 源码。
# ------------------------------------------------------------------
from PyInstaller import compat
from PyInstaller.utils import hooks as hookutils
from PyInstaller.utils.hooks import collect_data_files


# 收集 mpl-data, 排除测试样式 _classic_test_patch.mplstyle(纯冗余) — 小欧 2026-11-18
datas = collect_data_files('matplotlib', subdir='mpl-data', excludes=['**/_classic_test_patch.mplstyle'])

binaries = []

# Windows PyPI wheels for `matplotlib` >= 3.7.0 use `delvewheel`.
if compat.is_win and hookutils.check_requirement('matplotlib >= 3.7.0'):
    delvewheel_datas, delvewheel_binaries = hookutils.collect_delvewheel_libs_directory('matplotlib')

    datas += delvewheel_datas
    binaries += delvewheel_binaries
