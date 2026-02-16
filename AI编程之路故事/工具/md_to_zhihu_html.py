#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown转富文本HTML工具
用于将Markdown文章转换为适合知乎/头条编辑器复制的HTML格式
"""

import markdown
import sys
import os

def convert_md_to_html(md_file_path, output_html_path=None):
    """将Markdown文件转换为HTML格式"""
    
    if not os.path.exists(md_file_path):
        print("❌ 错误：文件不存在 " + md_file_path)
        return False
    
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    md = markdown.Markdown(extensions=[
        'tables',
        'fenced_code',
        'nl2br',
    ])
    
    html_body = md.convert(md_content)
    
    # 构建HTML模板
    parts = []
    parts.append('<!DOCTYPE html>')
    parts.append('<html lang="zh-CN">')
    parts.append('<head>')
    parts.append('    <meta charset="UTF-8">')
    parts.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append('    <title>知乎/头条富文本预览</title>')
    parts.append('    <style>')
    
    # CSS样式
    css = """
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.8;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        
        .content {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        
        h1 {
            font-size: 28px;
            font-weight: bold;
            color: #1a1a1a;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #0066ff;
        }
        
        h2 {
            font-size: 22px;
            font-weight: bold;
            color: #1a1a1a;
            margin-top: 30px;
            margin-bottom: 15px;
            padding-left: 12px;
            border-left: 4px solid #0066ff;
        }
        
        h3 {
            font-size: 18px;
            font-weight: bold;
            color: #333;
            margin-top: 25px;
            margin-bottom: 12px;
        }
        
        h4 {
            font-size: 16px;
            font-weight: bold;
            color: #444;
            margin-top: 20px;
            margin-bottom: 10px;
        }
        
        p {
            margin-bottom: 16px;
            text-align: justify;
        }
        
        ul, ol {
            margin-bottom: 16px;
            padding-left: 24px;
        }
        
        li {
            margin-bottom: 8px;
        }
        
        /* 表格样式 - 优化 */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        
        th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
            padding: 14px 16px;
            text-align: left;
            border: none;
        }
        
        td {
            padding: 12px 16px;
            border-bottom: 1px solid #e5e7eb;
            border-right: 1px solid #e5e7eb;
        }
        
        td:last-child {
            border-right: none;
        }
        
        tr:nth-child(even) {
            background: #f9fafb;
        }
        
        tr:hover {
            background: #f3f4f6;
        }
        
        tr:last-child td {
            border-bottom: none;
        }
        
        /* 代码块样式 - 优化 */
        pre {
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            font-size: 13px;
            line-height: 1.7;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        code {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
            font-size: 14px;
            background: #f3f4f6;
            padding: 3px 8px;
            border-radius: 4px;
            color: #d63384;
            border: 1px solid #e5e7eb;
        }
        
        pre code {
            background: transparent;
            padding: 0;
            color: #d4d4d4;
            border: none;
            font-size: 13px;
            line-height: 1.7;
        }
        
        blockquote {
            border-left: 4px solid #0066ff;
            margin: 20px 0;
            padding: 10px 20px;
            background: #f8f9fa;
            color: #666;
        }
        
        hr {
            border: none;
            border-top: 2px solid #e1e4e8;
            margin: 30px 0;
        }
        
        strong {
            color: #1a1a1a;
            font-weight: bold;
        }
        
        em {
            font-style: italic;
            color: #666;
        }
        
        a {
            color: #0066ff;
            text-decoration: none;
        }
        
        a:hover {
            text-decoration: underline;
        }
        
        .action-buttons {
            position: fixed;
            top: 20px;
            right: 20px;
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 1000;
        }
        
        .action-buttons h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #666;
        }
        
        .action-buttons button {
            display: block;
            width: 100%;
            padding: 10px 15px;
            margin: 5px 0;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        .btn-copy {
            background: #0066ff;
            color: white;
        }
        
        .btn-copy:hover {
            background: #0052cc;
        }
        
        .btn-select {
            background: #f0f0f0;
            color: #333;
        }
        
        .btn-select:hover {
            background: #e0e0e0;
        }
        
        .tips {
            background: #f0f7ff;
            border: 1px solid #b3d9ff;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        
        .tips strong {
            color: #0066ff;
        }
    """
    
    parts.append(css)
    parts.append('    </style>')
    parts.append('</head>')
    parts.append('<body>')
    parts.append('    <div class="action-buttons">')
    parts.append('        <h3>📋 复制工具</h3>')
    parts.append('        <button class="btn-select" onclick="selectAllContent()">全选内容</button>')
    parts.append('        <button class="btn-copy" onclick="copyToClipboard()">复制到剪贴板</button>')
    parts.append('    </div>')
    parts.append('    <div class="tips">')
    parts.append('        <strong>💡 使用方法：</strong><br>')
    parts.append('        1. 点击"全选内容"<br>')
    parts.append('        2. 按 Ctrl+C 复制<br>')
    parts.append('        3. 打开知乎/头条编辑器，按 Ctrl+V 粘贴<br>')
    parts.append('        4. 格式会自动保留！')
    parts.append('    </div>')
    parts.append('    <div class="content" id="article-content">')
    parts.append(html_body)
    parts.append('    </div>')
    parts.append('    <script>')
    parts.append('        function selectAllContent() {')
    parts.append('            const range = document.createRange();')
    parts.append('            range.selectNodeContents(document.getElementById("article-content"));')
    parts.append('            const selection = window.getSelection();')
    parts.append('            selection.removeAllRanges();')
    parts.append('            selection.addRange(range);')
    parts.append('        }')
    parts.append('        async function copyToClipboard() {')
    parts.append('            selectAllContent();')
    parts.append('            try {')
    parts.append('                await navigator.clipboard.writeText(window.getSelection().toString());')
    parts.append('                alert("✅ 已复制到剪贴板！");')
    parts.append('            } catch (err) {')
    parts.append('                alert("❌ 复制失败，请手动按 Ctrl+C 复制");')
    parts.append('            }')
    parts.append('        }')
    parts.append('    </script>')
    parts.append('</body>')
    parts.append('</html>')
    
    html_content = '\n'.join(parts)
    
    if output_html_path is None:
        output_html_path = md_file_path.rsplit('.', 1)[0] + '_富文本预览.html'
    
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("✅ 转换成功！")
    print("📄 HTML文件：" + output_html_path)
    print("📊 文件大小：%.1f KB" % (os.path.getsize(output_html_path) / 1024))
    print("\n💡 使用说明：")
    print("   1. 用浏览器打开HTML文件")
    print("   2. 点击'全选内容'")
    print("   3. 按 Ctrl+C 复制")
    print("   4. 粘贴到知乎/头条编辑器")
    
    return True

def main():
    print("=" * 60)
    print("📝 Markdown转富文本HTML工具")
    print("=" * 60)
    print()
    
    if len(sys.argv) < 2:
        print("❌ 使用方法：")
        print("   python " + sys.argv[0] + " <markdown文件路径>")
        print()
        print("示例：")
        print("   python " + sys.argv[0] + " '文章.md'")
        print()
        
        md_files = [f for f in os.listdir('.') if f.endswith('.md')]
        if md_files:
            print("📂 当前目录可用的MD文件：")
            for i, f in enumerate(md_files, 1):
                print("   " + str(i) + ". " + f)
        
        sys.exit(1)
    
    md_file = sys.argv[1]
    
    if convert_md_to_html(md_file):
        print("\n" + "=" * 60)
        print("✨ 完成！请在浏览器中打开HTML文件查看效果")
        print("=" * 60)
    else:
        print("\n❌ 转换失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
