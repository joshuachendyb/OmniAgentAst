import asyncio
import os
import sys
sys.path.insert(0, 'D:/OmniAgentAs-desk/backend')

from pathlib import Path
from app.services.tools.file.file_tools import FileTools

# 创建测试文件
test_dir = Path('C:/Users/40968/Desktop/test_file_tools')
test_dir.mkdir(exist_ok=True)

async def test_all():
    tools = FileTools(session_id='test_session_123')
    session_id = 'test_session_123'
    
    # 测试1: copy_file
    print('=== 测试1: copy_file ===')
    source = test_dir / 'source.txt'
    source.write_text('hello world')
    dest = test_dir / 'dest.txt'
    
    result = await tools.copy_file(
        source_path=str(source),
        destination_path=str(dest),
        recursive=False,
        overwrite=False
    )
    print(f'success: {result.get("data", {}).get("success")}')
    if not result.get('data', {}).get('success'):
        print(f'error: {result.get("data", {}).get("error")}')
    
    # 测试2: get_file_info
    print('\n=== 测试2: get_file_info ===')
    result = await tools.get_file_info(file_path=str(source))
    print(f'success: {result.get("data", {}).get("success")}')
    if result.get('data', {}).get('success'):
        info = result['data']['info']
        print(f'name: {info.get("name")}, size: {info.get("size")}')
    
    # 测试3: create_directory
    print('\n=== 测试3: create_directory ===')
    new_dir = test_dir / 'new_subdir'
    result = await tools.create_directory(
        dir_path=str(new_dir),
        parents=True,
        exist_ok=False
    )
    print(f'success: {result.get("data", {}).get("success")}')
    print(f'exists: {new_dir.exists()}')
    
    # 测试4: file_checksum
    print('\n=== 测试4: file_checksum ===')
    result = await tools.file_checksum(
        file_path=str(source),
        algorithm='md5'
    )
    print(f'success: {result.get("data", {}).get("success")}')
    if result.get('data', {}).get('success'):
        print(f'checksum: {result["data"]["checksum"]}')
    
    # 测试5: compress_files
    print('\n=== 测试5: compress_files ===')
    result = await tools.compress_files(
        source_path=str(source),
        destination_path=str(test_dir / 'test.zip'),
        format='zip',
        compression_level=6
    )
    print(f'success: {result.get("data", {}).get("success")}')
    if result.get('data', {}).get('success'):
        print(f'compressed_size: {result["data"].get("compressed_size")}')
    else:
        print(f'error: {result.get("data", {}).get("error")}')
    
    # 测试6: compare_files
    print('\n=== 测试6: compare_files ===')
    source2 = test_dir / 'source2.txt'
    source2.write_text('hello world')
    
    result = await tools.compare_files(
        file_path1=str(source),
        file_path2=str(source2),
        algorithm='content'
    )
    print(f'success: {result.get("data", {}).get("success")}')
    if result.get('data', {}).get('success'):
        print(f'identical: {result["data"].get("identical")}')
    
    print('\n=== 集成测试完成 ===')

asyncio.run(test_all())