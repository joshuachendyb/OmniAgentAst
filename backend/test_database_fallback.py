import sys
sys.path.insert(0, '.')
import asyncio
from pathlib import Path
import tempfile

from app.tools.file.write_text_file import write_text_file
from app.tools.file.edit_text_file import edit_text_file
from app.tools.file.copy_file import copy_file
from app.services.context_vars import _current_task_id

def is_success(r): return r.get('llm_data',{}).get('status',{}).get('exec_code')=='success'
def is_error(r): return r.get('llm_data',{}).get('status',{}).get('exec_code')=='error'

async def test():
    print('='*60)
    print('数据库容错测试 - 小健 2026-06-24')
    print('='*60)
    
    _current_task_id.set("test_task")
    tmp_dir = Path(tempfile.mkdtemp())
    
    print('\n[测试1] write_text_file - 数据库不可用时仍能写入文件')
    test_file = tmp_dir / "test.txt"
    result = await write_text_file(file_path=str(test_file), content="Hello World")
    if is_success(result):
        print('  OK - 写入成功')
        # 验证文件内容
        if test_file.exists() and test_file.read_text() == "Hello World":
            print('  OK - 文件内容正确')
        else:
            print('  FAIL - 文件内容错误')
    else:
        detail = result.get('llm_data',{}).get('status',{}).get('detail','')
        print(f'  FAIL - 写入失败: {detail}')
    
    print('\n[测试2] edit_text_file - 数据库不可用时仍能编辑文件')
    result = await edit_text_file(file_path=str(test_file), old_string="Hello", new_string="Hi")
    if is_success(result):
        print('  OK - 编辑成功')
        # 验证文件内容
        if test_file.exists() and test_file.read_text() == "Hi World":
            print('  OK - 文件内容正确')
        else:
            print(f'  FAIL - 文件内容错误: {test_file.read_text()}')
    else:
        detail = result.get('llm_data',{}).get('status',{}).get('detail','')
        print(f'  FAIL - 编辑失败: {detail}')
    
    print('\n[测试3] copy_file - 数据库不可用时仍能复制文件')
    copy_file_path = tmp_dir / "copy.txt"
    result = await copy_file(source=str(test_file), destination=str(copy_file_path))
    if is_success(result):
        print('  OK - 复制成功')
        if copy_file_path.exists():
            print('  OK - 目标文件存在')
        else:
            print('  FAIL - 目标文件不存在')
    else:
        detail = result.get('llm_data',{}).get('status',{}).get('detail','')
        print(f'  FAIL - 复制失败: {detail}')
    
    print('\n' + '='*60)
    print('测试完成')
    print('='*60)

asyncio.run(test())