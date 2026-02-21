#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
恢复所有笔记文件
"""
import subprocess
import os
import sys

def main():
    repo_dir = r"D:\2bktest\MDview\OmniAgentAs-desk"
    os.chdir(repo_dir)
    
    commit_hash = "1d51dc3"
    
    print("=== 查看提交的完整文件列表 ===")
    result = subprocess.run(
        ["git", "ls-tree", "-r", commit_hash],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    all_files = []
    for line in result.stdout.split('\n'):
        line = line.strip()
        if line:
            parts = line.split('\t')
            if len(parts) >= 2:
                filename = parts[1]
                all_files.append(filename)
                print(filename)
    
    print(f"\n=== 找到 {len(all_files)} 个文件 ===")
    
    # 寻找笔记相关的文件
    note_files = []
    for f in all_files:
        f_lower = f.lower()
        if '笔记' in f or 'debug' in f_lower or 'work' in f_lower or '日志' in f:
            note_files.append(f)
    
    print(f"\n=== 找到 {len(note_files)} 个笔记文件 ===")
    for f in note_files:
        print(f"  - {f}")
    
    # 尝试恢复这些文件
    print("\n=== 开始恢复文件 ===")
    
    # 先创建notes目录
    notes_dir = os.path.join(repo_dir, "notes")
    os.makedirs(notes_dir, exist_ok=True)
    
    for filepath in note_files:
        try:
            # 查看文件内容
            content = subprocess.check_output(
                ["git", "show", f"{commit_hash}:{filepath}"],
                stderr=subprocess.STDOUT
            )
            
            # 确定保存位置
            if 'notes/' in filepath:
                # 已经在notes目录下
                save_path = os.path.join(repo_dir, filepath)
            else:
                # 放在notes目录下
                basename = os.path.basename(filepath)
                save_path = os.path.join(notes_dir, basename)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存文件
            with open(save_path, 'wb') as f:
                f.write(content)
            
            print(f"✅ 已恢复: {filepath} -> {save_path}")
            print(f"   文件大小: {len(content)} 字节")
            
            # 预览内容
            try:
                preview = content.decode('utf-8', errors='replace')[:300]
                print(f"   预览: {preview}...")
            except:
                pass
                
        except Exception as e:
            print(f"❌ 恢复失败: {filepath}")
            print(f"   错误: {e}")
    
    # 也看看那个提交和前一个提交的diff
    print("\n=== 查看提交变更 ===")
    diff_result = subprocess.run(
        ["git", "diff", f"{commit_hash}^..{commit_hash}", "--name-only"],
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    print(diff_result.stdout)
    
    print("\n=== 完成 ===")
    print(f"恢复的文件保存在: {notes_dir}")
    print("请检查该目录！")

if __name__ == "__main__":
    main()
