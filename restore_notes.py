#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
恢复丢失的笔记文件
"""
import subprocess
import os
import sys

def main():
    commit_hash = "1d51dc3"
    repo_dir = r"D:\2bktest\MDview\OmniAgentAs-desk"
    
    os.chdir(repo_dir)
    
    # 查看提交的所有文件
    print("=== 查看提交内容 ===")
    result = subprocess.run(
        ["git", "show", "--name-only", commit_hash],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(result.stdout)
    
    print("\n=== 查看git ls-files ===")
    result2 = subprocess.run(
        ["git", "ls-tree", "-r", commit_hash],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(result2.stdout)
    
    # 尝试恢复那个笔记文件
    print("\n=== 尝试恢复笔记文件 ===")
    import re
    files_output = result2.stdout
    
    # 寻找包含"笔记"或"debug"的文件
    for line in files_output.split('\n'):
        if '笔记' in line or 'debug' in line.lower() or 'work' in line.lower():
            print(f"找到文件: {line}")
            
            # 提取文件名
            parts = line.split('\t')
            if len(parts) >= 2:
                filename = parts[1]
                print(f"提取的文件名: {filename}")
                
                # 尝试查看文件内容
                try:
                    content = subprocess.check_output(
                        ["git", "show", f"{commit_hash}:{filename}"],
                        stderr=subprocess.STDOUT
                    )
                    
                    # 保存到笔记目录
                    notes_dir = os.path.join(repo_dir, "OmniAgentAs-desk", "调试笔记")
                    os.makedirs(notes_dir, exist_ok=True)
                    
                    # 简单命名
                    output_path = os.path.join(notes_dir, "工作笔记-2026-02-21-恢复.md")
                    
                    with open(output_path, 'wb') as f:
                        f.write(content)
                    
                    print(f"文件已恢复到: {output_path}")
                    
                    # 也显示内容预览
                    print("\n=== 文件内容预览 ===")
                    try:
                        print(content.decode('utf-8', errors='replace')[:500])
                    except:
                        pass
                        
                except Exception as e:
                    print(f"恢复时出错: {e}")

if __name__ == "__main__":
    main()
