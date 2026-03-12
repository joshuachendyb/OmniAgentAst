#!/usr/bin/env python3
"""
错误日志分析工具
用于分析后端日志文件，提取错误信息并生成统计报告
"""

import os
import re
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import argparse
from typing import Dict, List, Tuple, Optional

# 日志目录
LOG_DIR = Path(__file__).parent / "logs"

def parse_log_line(line: str) -> Optional[Dict]:
    """
    解析日志行
    
    日志格式：
    生产模式: 2026-02-26 19:28:30,123 - ERROR - 错误消息
    调试模式: 2026-02-26 19:28:30,123 - app.utils.logger - ERROR - [file.py:123] - 错误消息
    
    Args:
        line: 日志行
        
    Returns:
        解析后的日志字典或None（如果不是有效的日志行）
    """
    line = line.strip()
    if not line:
        return None
    
    # 尝试匹配生产模式格式
    prod_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (.+)$'
    prod_match = re.match(prod_pattern, line)
    if prod_match:
        timestamp, level, message = prod_match.groups()
        return {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'logger': None,
            'filename': None,
            'lineno': None
        }
    
    # 尝试匹配调试模式格式
    debug_pattern = r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - ([^-]+) - (\w+) - \[([^:]+):(\d+)\] - (.+)$'
    debug_match = re.match(debug_pattern, line)
    if debug_match:
        timestamp, logger, level, filename, lineno, message = debug_match.groups()
        return {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'logger': logger,
            'filename': filename,
            'lineno': int(lineno)
        }
    
    return None

def analyze_log_file(file_path: Path, min_level: str = "ERROR") -> Dict:
    """
    分析单个日志文件
    
    Args:
        file_path: 日志文件路径
        min_level: 最小日志级别（ERROR, WARNING, INFO等）
        
    Returns:
        分析结果字典
    """
    level_order = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    min_level_value = level_order.get(min_level, level_order["ERROR"])
    
    results = {
        'file': str(file_path),
        'total_lines': 0,
        'error_lines': 0,
        'warning_lines': 0,
        'info_lines': 0,
        'errors_by_type': defaultdict(int),
        'errors_by_file': defaultdict(int),
        'error_messages': [],
        'recent_errors': [],
        'level_counts': defaultdict(int),
        'time_range': {'start': None, 'end': None}
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"无法读取日志文件 {file_path}: {e}")
        return results
    
    results['total_lines'] = len(lines)
    
    for line in lines:
        log_entry = parse_log_line(line)
        if not log_entry:
            continue
        
        level = log_entry['level']
        results['level_counts'][level] += 1
        
        # 更新时间范围
        timestamp = log_entry['timestamp']
        if not results['time_range']['start']:
            results['time_range']['start'] = timestamp
        results['time_range']['end'] = timestamp
        
        # 检查是否达到最小级别
        if level_order.get(level, 0) < min_level_value:
            continue
        
        if level == "ERROR":
            results['error_lines'] += 1
            message = log_entry['message']
            results['error_messages'].append({
                'timestamp': log_entry['timestamp'],
                'message': message,
                'filename': log_entry.get('filename'),
                'lineno': log_entry.get('lineno')
            })
            
            # 按错误类型分类（简单分类）
            if "HTTP" in message or "status_code" in message:
                error_type = "HTTP错误"
            elif "Connection" in message or "连接" in message:
                error_type = "连接错误"
            elif "Timeout" in message or "超时" in message:
                error_type = "超时错误"
            elif "Validation" in message or "验证" in message:
                error_type = "验证错误"
            elif "Database" in message or "数据库" in message:
                error_type = "数据库错误"
            elif "Permission" in message or "权限" in message:
                error_type = "权限错误"
            elif "File" in message or "文件" in message:
                error_type = "文件错误"
            elif "Memory" in message or "内存" in message:
                error_type = "内存错误"
            else:
                error_type = "其他错误"
            
            results['errors_by_type'][error_type] += 1
            
            # 按文件分类
            if log_entry['filename']:
                results['errors_by_file'][log_entry['filename']] += 1
        
        elif level == "WARNING":
            results['warning_lines'] += 1
    
    # 获取最近的错误（最多10个）
    results['recent_errors'] = results['error_messages'][-10:] if results['error_messages'] else []
    
    return results

def analyze_all_logs(days: int = 7, min_level: str = "ERROR") -> Dict:
    """
    分析指定天数内的所有日志文件
    
    Args:
        days: 分析最近多少天的日志
        min_level: 最小日志级别
        
    Returns:
        合并的分析结果
    """
    # 获取所有日志文件
    log_files = []
    for log_file in LOG_DIR.glob("app_*.log"):
        # 从文件名提取日期
        date_str = log_file.stem.replace("app_", "")
        try:
            file_date = datetime.strptime(date_str, "%Y-%m-%d")
            cutoff_date = datetime.now() - timedelta(days=days)
            if file_date >= cutoff_date:
                log_files.append((log_file, file_date))
        except ValueError:
            continue
    
    # 按日期排序（最新的在前）
    log_files.sort(key=lambda x: x[1], reverse=True)
    
    all_results = {
        'total_files': len(log_files),
        'analyzed_files': [],
        'summary': {
            'total_errors': 0,
            'total_warnings': 0,
            'errors_by_type': defaultdict(int),
            'errors_by_file': defaultdict(int),
            'daily_errors': defaultdict(int),
            'level_summary': defaultdict(int)
        }
    }
    
    for log_file, file_date in log_files:
        print(f"分析文件: {log_file.name}")
        file_results = analyze_log_file(log_file, min_level)
        all_results['analyzed_files'].append(file_results)
        
        # 汇总统计
        all_results['summary']['total_errors'] += file_results['error_lines']
        all_results['summary']['total_warnings'] += file_results['warning_lines']
        
        # 合并按类型统计
        for error_type, count in file_results['errors_by_type'].items():
            all_results['summary']['errors_by_type'][error_type] += count
        
        # 合并按文件统计
        for filename, count in file_results['errors_by_file'].items():
            all_results['summary']['errors_by_file'][filename] += count
        
        # 按日期统计
        date_key = file_date.strftime("%Y-%m-%d")
        all_results['summary']['daily_errors'][date_key] += file_results['error_lines']
        
        # 合并级别统计
        for level, count in file_results['level_counts'].items():
            all_results['summary']['level_summary'][level] += count
    
    return all_results

def generate_report(results: Dict, output_format: str = "text") -> str:
    """
    生成分析报告
    
    Args:
        results: 分析结果
        output_format: 输出格式（text, markdown）
        
    Returns:
        报告字符串
    """
    if output_format == "markdown":
        return _generate_markdown_report(results)
    else:
        return _generate_text_report(results)

def _generate_text_report(results: Dict) -> str:
    """生成文本格式报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("错误日志分析报告")
    lines.append("=" * 60)
    lines.append(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"分析文件数: {results['total_files']}")
    lines.append("")
    
    summary = results['summary']
    lines.append("摘要统计:")
    lines.append(f"  总错误数: {summary['total_errors']}")
    lines.append(f"  总警告数: {summary['total_warnings']}")
    lines.append("")
    
    if summary['errors_by_type']:
        lines.append("按错误类型分类:")
        for error_type, count in sorted(summary['errors_by_type'].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {error_type}: {count}")
        lines.append("")
    
    if summary['errors_by_file']:
        lines.append("按文件分类（前10个）:")
        sorted_files = sorted(summary['errors_by_file'].items(), key=lambda x: x[1], reverse=True)[:10]
        for filename, count in sorted_files:
            lines.append(f"  {filename}: {count}")
        lines.append("")
    
    if summary['daily_errors']:
        lines.append("每日错误统计:")
        for date_str, count in sorted(summary['daily_errors'].items()):
            lines.append(f"  {date_str}: {count}")
        lines.append("")
    
    if summary['level_summary']:
        lines.append("日志级别统计:")
        for level, count in sorted(summary['level_summary'].items()):
            lines.append(f"  {level}: {count}")
        lines.append("")
    
    # 显示最近文件的详细错误
    if results['analyzed_files']:
        latest_file = results['analyzed_files'][0]
        if latest_file['recent_errors']:
            lines.append("最近的错误（最新文件）:")
            for i, error in enumerate(latest_file['recent_errors'], 1):
                lines.append(f"  {i}. [{error['timestamp']}] {error['message']}")
                if error['filename']:
                    lines.append(f"     文件: {error['filename']}:{error['lineno']}")
            lines.append("")
    
    lines.append("=" * 60)
    return "\n".join(lines)

def _generate_markdown_report(results: Dict) -> str:
    """生成Markdown格式报告"""
    lines = []
    lines.append("# 错误日志分析报告")
    lines.append("")
    lines.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**分析文件数**: {results['total_files']}")
    lines.append("")
    
    summary = results['summary']
    lines.append("## 摘要统计")
    lines.append("")
    lines.append(f"- **总错误数**: {summary['total_errors']}")
    lines.append(f"- **总警告数**: {summary['total_warnings']}")
    lines.append("")
    
    if summary['errors_by_type']:
        lines.append("## 按错误类型分类")
        lines.append("")
        lines.append("| 错误类型 | 数量 |")
        lines.append("|----------|------|")
        for error_type, count in sorted(summary['errors_by_type'].items(), key=lambda x: x[1], reverse=True):
            lines.append(f"| {error_type} | {count} |")
        lines.append("")
    
    if summary['errors_by_file']:
        lines.append("## 按文件分类（前10个）")
        lines.append("")
        lines.append("| 文件 | 错误数 |")
        lines.append("|------|--------|")
        sorted_files = sorted(summary['errors_by_file'].items(), key=lambda x: x[1], reverse=True)[:10]
        for filename, count in sorted_files:
            lines.append(f"| {filename} | {count} |")
        lines.append("")
    
    if summary['daily_errors']:
        lines.append("## 每日错误统计")
        lines.append("")
        lines.append("| 日期 | 错误数 |")
        lines.append("|------|--------|")
        for date_str, count in sorted(summary['daily_errors'].items()):
            lines.append(f"| {date_str} | {count} |")
        lines.append("")
    
    if summary['level_summary']:
        lines.append("## 日志级别统计")
        lines.append("")
        lines.append("| 级别 | 数量 |")
        lines.append("|------|------|")
        for level, count in sorted(summary['level_summary'].items()):
            lines.append(f"| {level} | {count} |")
        lines.append("")
    
    # 显示最近文件的详细错误
    if results['analyzed_files']:
        latest_file = results['analyzed_files'][0]
        if latest_file['recent_errors']:
            lines.append("## 最近的错误（最新文件）")
            lines.append("")
            for i, error in enumerate(latest_file['recent_errors'], 1):
                lines.append(f"{i}. **{error['timestamp']}** - {error['message']}")
                if error['filename']:
                    lines.append(f"   - 文件: `{error['filename']}:{error['lineno']}`")
            lines.append("")
    
    return "\n".join(lines)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="错误日志分析工具")
    parser.add_argument("--days", type=int, default=7, help="分析最近多少天的日志（默认7天）")
    parser.add_argument("--level", type=str, default="ERROR", 
                       choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                       help="最小日志级别（默认ERROR）")
    parser.add_argument("--format", type=str, default="text",
                       choices=["text", "markdown"],
                       help="输出格式（默认text）")
    parser.add_argument("--output", type=str, help="输出文件路径（不指定则输出到控制台）")
    
    args = parser.parse_args()
    
    # 检查日志目录
    if not LOG_DIR.exists():
        print(f"错误：日志目录不存在: {LOG_DIR}")
        sys.exit(1)
    
    # 分析日志
    print(f"正在分析最近{args.days}天的日志（最小级别: {args.level}）...")
    results = analyze_all_logs(days=args.days, min_level=args.level)
    
    # 生成报告
    report = generate_report(results, output_format=args.format)
    
    # 输出报告
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"报告已保存到: {args.output}")
        except Exception as e:
            print(f"保存报告失败: {e}")
            print("\n报告内容:")
            print(report)
    else:
        print(report)

if __name__ == "__main__":
    main()