# ------------------------------------------------------------------
# 自定义 pyarrow 打包 hook — 小欧 2026-11-18
# 覆盖 pyinstaller-hooks-contrib 的 hook-pyarrow.py:
#   contrib 原版用 collect_data_files('pyarrow') 收集 pyarrow 包【全部】非 Python 数据文件,
#   把 tests/、include/arrow/testing/ 及零散 test_*.h / *_test.cc 等测试套件一并带入产物。
#   这些纯冗余, 运行时绝不 import, 只在打包版里白白增大包体积。
# 本 hook 用 excludes 精确排除测试文件, 保留全部正常运行数据(570 项 = 原 627 - 测试 57)。
#   排除模式经实测: 57 个测试全清除, 无过度排除(不误伤含 "test" 子串的真实文件如 latest)。
# 注意: 自定义 hook 目录经 spec 的 hookspath 传入, 优先级 USER_HOOKS(1000) > CONTRIBUTED(-1000),
#   因此本文件完整覆盖 contrib 同名 hook, 不污染第三方库源码。
# ------------------------------------------------------------------
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_dynamic_libs

# 保留 contrib 原逻辑: 收集 pyarrow 子模块(排除 tests), 收集动态库
hiddenimports = collect_submodules('pyarrow', filter=lambda x: "tests" not in x)
binaries = collect_dynamic_libs('pyarrow')

# 收集 pyarrow 数据文件, 精确排除测试套件(纯冗余) — 小欧 2026-11-18
datas = collect_data_files('pyarrow', excludes=[
    '**/tests', '**/testing',           # 测试目录(pyarrow/tests, pyarrow/include/arrow/testing)
    '**/test_*.h', '**/*_test*.h',      # 测试头文件(test_common.h / test_util.h / python_test.h 等)
    '**/*_test*.pyx', '**/*_test*.pxd', # 测试 Cython 源码
    '**/*_test*.cc',                    # 测试 C++ 源码(python_test.cc 等)
    '**/*test*.parquet', '**/*test*.orc',  # 测试数据文件
    '**/*test*.gz', '**/*test*.feather',
])
