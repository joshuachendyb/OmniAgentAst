#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Markdown to HTML Converter for Zhihu/Headline
"""

import markdown
import sys
import os

def convert_md_to_html(md_file_path, output_html_path=None):
    """Convert Markdown to HTML"""
    
    if not os.path.exists(md_file_path):
        print("Error: File not found " + md_file_path)
        return False
    
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    md = markdown.Markdown(extensions=[
        'tables',
        'fenced_code',
        'nl2br',
    ])
    
    html_body = md.convert(md_content)
    
    # Build HTML with optimized styles
    html_content = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Zhihu Rich Text Preview</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
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
        
        /* Optimized table styles */
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
        
        tr:last-child td {
            border-bottom: none;
        }
        
        /* Optimized code block styles */
        pre {
            background: #1e1e1e;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 20px;
            overflow-x: auto;
            font-family: "SFMono-Regular", Consolas, monospace;
            font-size: 13px;
            line-height: 1.7;
            margin: 20px 0;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        code {
            font-family: "SFMono-Regular", Consolas, monospace;
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
        
        strong {
            color: #1a1a1a;
            font-weight: bold;
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
        }
        
        .btn-copy {
            background: #0066ff;
            color: white;
        }
        
        .btn-select {
            background: #f0f0f0;
            color: #333;
        }
        
        .tips {
            background: #f0f7ff;
            border: 1px solid #b3d9ff;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="action-buttons">
        <h3>Copy Tools</h3>
        <button class="btn-select" onclick="selectAllContent()">Select All</button>
        <button class="btn-copy" onclick="copyToClipboard()">Copy</button>
    </div>
    <div class="tips">
        <strong>How to use:</strong><br>
        1. Click "Select All"<br>
        2. Press Ctrl+C to copy<br>
        3. Paste into Zhihu/Toutiao editor<br>
        4. Format will be preserved!
    </div>
    <div class="content" id="article-content">
''' + html_body + '''
    </div>
    <script>
        function selectAllContent() {
            const range = document.createRange();
            range.selectNodeContents(document.getElementById("article-content"));
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
        }
        
        async function copyToClipboard() {
            selectAllContent();
            try {
                await navigator.clipboard.writeText(window.getSelection().toString());
                alert("Copied to clipboard!");
            } catch (err) {
                alert("Copy failed. Please use Ctrl+C manually.");
            }
        }
    </script>
</body>
</html>'''
    
    if output_html_path is None:
        output_html_path = md_file_path.rsplit('.', 1)[0] + '_RichText.html'
    
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("Success! Converted to HTML.")
    print("Output: " + output_html_path)
    print("File size: %.1f KB" % (os.path.getsize(output_html_path) / 1024))
    
    return True

def main():
    if len(sys.argv) < 2:
        print("Usage: python " + sys.argv[0] + " <markdown_file>")
        sys.exit(1)
    
    md_file = sys.argv[1]
    
    if convert_md_to_html(md_file):
        print("Done!")
    else:
        print("Failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
