# ============================================================================
# deploy_spa.py — 同源SPA 部署脚本: 只替换 exe + _internal, 目标目录其余一律不动
# 创建: 2026-11-04 小欧 - 由临时部署脚本固化入库(北京老陈令"部署SPA的脚本可以留着")
# 用法: python backend/deploy_spa.py [--target G:\OmniAgent-SPA] [--dist <dist目录>]
#   默认 target=G:\OmniAgent-SPA, dist=backend/dist/OmniAgentBackend
#
# 编辑历史:
#   2026-11-04 小欧 - 新建。exe 原地覆盖; _internal 改覆盖合并(dirs_exist_ok=True),
#     不再 rmtree 整目录后再 copytree —— 先删后建若复制中断会留残缺目录, 程序直接起不来。
#     部署前按 exe 路径比对探测目标进程是否在跑, 在跑则只提示(PS+CMD 两套命令)后退出,
#     不自动杀进程: 占用者可能正在跑任务, 自动杀等于丢数据。
#     部署时一并同步 dist 根的 OmniAgent使用说明.md(exe 同级), 与打包后处理环节配套。
#   2026-11-06 小欧 - 部署前先清 _internal/web 再 copytree: web 是唯一随版本陈旧累积的静态资源,
#     copytree dirs_exist_ok 只覆盖同名, 目标端旧 chunk 永不清除; 其余 _internal 依赖不清理保容错。
# ============================================================================
import argparse
import shutil
import sys
from pathlib import Path
from typing import List

DEFAULT_TARGET = Path(r'G:\OmniAgent-SPA')
DEFAULT_DIST = Path(__file__).resolve().parent / 'dist' / 'OmniAgentBackend'
EXE_NAME = 'OmniAgentBackend.exe'


def _running_pids(exe: Path) -> List[int]:
    """按可执行文件路径比对, 找出正在运行的目标 exe 进程 — 小欧 2026-11-04

    比查端口可靠: 目标可能改了端口启动, 也可能别的程序先占了 8500。
    """
    try:
        import psutil
    except ImportError:
        return []
    target = str(exe).lower()
    pids: List[int] = []
    for proc in psutil.process_iter(['pid', 'exe']):
        try:
            if (proc.info.get('exe') or '').lower() == target:
                pids.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def _hint_running(target: Path, pids: List[int]) -> None:
    """提示目标 exe 正在运行并给出结束命令(不自动执行) — 小欧 2026-11-04"""
    rule = '=' * 68
    print(f'\n{rule}')
    print('[deploy_spa] 目标程序正在运行, 本次部署终止(未改动任何文件)')
    print(rule)
    print(f'  目标: {target}')
    for pid in pids:
        print(f'  运行中: PID {pid}')
    print('\n  Windows 下无法覆盖正在运行的 exe, 请先结束它:')
    for pid in pids:
        print(f'     PowerShell:  Stop-Process -Id {pid} -Force')
        print(f'     CMD:         taskkill /F /PID {pid}')
    print('\n  结束进程会中止它正在跑的任务; 若不想中断, 等任务跑完再部署。')
    print(f'{rule}\n')


def _deploy(target: Path, dist: Path) -> None:
    """执行部署: 覆盖 exe + 合并 _internal + 同步 exe 同级说明文档 — 小欧 2026-11-04

    2026-11-07 小欧 - _internal 逐文件复制: 系统运行时 DLL(MSVCP140/VCRUNTIME 等)被其他进程
      加载时无法覆盖(WinError 32), 但这些 DLL 不随版本变化, 跳过不影响运行; web/ 先清再复制
      保证前端产物不累积旧 chunk。— 小欧-2026-11-07
    """
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dist / EXE_NAME, target / EXE_NAME)
    # 前端产物 web/ 是唯一随版本陈旧累积的静态资源, 先清再复制避免旧 assets 残留
    _web = target / '_internal' / 'web'
    if _web.is_dir():
        shutil.rmtree(_web)
    # _internal 逐文件复制: 被锁的系统 DLL 跳过(不随版本变化), 其余正常覆盖
    _skipped = []
    for src in (dist / '_internal').rglob('*'):
        if src.is_dir():
            continue
        rel = src.relative_to(dist / '_internal')
        dst = target / '_internal' / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dst)
        except (PermissionError, OSError) as exc:
            _skipped.append(str(rel))
    if _skipped:
        print(f'[deploy_spa] 跳过 {len(_skipped)} 个被锁文件(系统 DLL, 不随版本变化):')
        for s in _skipped[:5]:
            print(f'  {s}')
        if len(_skipped) > 5:
            print(f'  ... 及其他 {len(_skipped) - 5} 个')
    for doc in dist.glob('OmniAgent使用说明*.md'):
        shutil.copy2(doc, target / doc.name)


def _report(target: Path, dist: Path) -> None:
    """部署后自检: 前端产物/版本/配置是否齐 — 小欧 2026-11-04"""
    internal = target / '_internal'
    assets = internal / 'web' / 'assets'
    exe = target / EXE_NAME

    print(f'--- {target} ---')
    for item in sorted(target.iterdir()):
        print(f'  {item.name:<24} {"目录" if item.is_dir() else "文件"}')
    print(f'web/index.html : {(internal / "web" / "index.html").exists()}')
    print(f'assets 文件数  : {len(list(assets.iterdir())) if assets.is_dir() else 0}')
    print(f'exe 大小 MB   : {exe.stat().st_size / 1024 / 1024:.1f}')
    print(f'config.yaml   : {(target / "config" / "config.yaml").exists()} (升级时应保留)')
    print(f'OmniAgent使用说明.md : {(target / "OmniAgent使用说明.md").exists()} (与 exe 同级)')
    ver = internal / 'version.txt'
    if ver.exists():
        print(f'包内版本      : {ver.read_text(encoding="utf-8").splitlines()[0]}')
    print(f'源包 exe 一致 : {exe.stat().st_size == (dist / EXE_NAME).stat().st_size}')


def main() -> int:
    parser = argparse.ArgumentParser(description='同源SPA 部署: 只替换 exe + _internal')
    parser.add_argument('--target', type=Path, default=DEFAULT_TARGET, help=f'部署目录(默认 {DEFAULT_TARGET})')
    parser.add_argument('--dist', type=Path, default=DEFAULT_DIST, help=f'打包产物目录(默认 {DEFAULT_DIST})')
    args = parser.parse_args()

    dist: Path = args.dist.resolve()
    target: Path = args.target.resolve()
    if not (dist / EXE_NAME).is_file() or not (dist / '_internal').is_dir():
        print(f'[deploy_spa] 打包产物不完整: {dist} 缺少 {EXE_NAME} 或 _internal')
        print('  先执行打包: frontend 下 npm run build, 再 backend 下 pyinstaller OmniAgentBackend.spec')
        return 2

    pids = _running_pids(target / EXE_NAME)
    if pids:
        _hint_running(target, pids)
        return 1

    print(f'[deploy_spa] 部署 {dist}  ->  {target}')
    try:
        _deploy(target, dist)
    except (PermissionError, shutil.Error) as exc:
        print(f'[deploy_spa] 写入失败(文件被锁或权限拒绝): {exc}')
        print('  可能原因: 目标 exe 已停但有子进程残留锁住 DLL, 或文件权限不足')
        print('  尝试: 关闭所有相关进程后重试, 或删除目标 _internal 目录后重试')
        return 3
    _report(target, dist)
    print('[deploy_spa] 部署完成')
    return 0


if __name__ == '__main__':
    sys.exit(main())
