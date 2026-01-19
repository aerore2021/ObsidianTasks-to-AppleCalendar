#!/usr/bin/env python3
"""
Obsidian Tasks 导出脚本
将 Obsidian Tasks 插件的任务导出为 iCalendar (.ics) 格式，供 Apple 日历订阅
只导出未完成的任务
"""

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse

# 配置
VAULT_PATH = "/Users/hqb/Library/Mobile Documents/iCloud~md~obsidian/Documents/Keitsii"
# 输出到本地目录（因为 launchd 无法写入 iCloud Drive）
ICS_OUTPUT_PATH = "/Users/hqb/.iflow-tasks-calendar/tasks_calendar.ics"
# iCloud 中的符号链接目标
ICS_ICLOUD_LINK = os.path.join(VAULT_PATH, "tasks_calendar.ics")

# 指定要导出的任务文件
TASK_FILES = [
    "fpga/周报/FPGA本周任务.md"
]

# 是否扫描整个 vault（当指定文件使用 Tasks 查询时需要）
SCAN_FULL_VAULT = True

def parse_task_line(line):
    """
    解析任务行，提取任务信息
    返回: {
        'done': bool,
        'text': str,
        'due_date': datetime or None,
        'done_date': datetime or None,
        'start_date': datetime or None
    }
    """
    # 匹配任务行
    # 格式: - [ ] 或 - [x] 后跟任务内容
    task_pattern = r'^\s*-\s*\[(x| )\]\s*(.+)$'
    match = re.match(task_pattern, line)
    
    if not match:
        return None
    
    done = match.group(1) == 'x'
    text = match.group(2)
    
    # 提取日期
    # 📅 due date
    # ✅ done date
    # ⏳ start date (created date)
    
    due_date = None
    done_date = None
    start_date = None
    
    # 提取 due date: 📅 YYYY-MM-DD
    due_match = re.search(r'📅\s*(\d{4}-\d{2}-\d{2})', text)
    if due_match:
        due_date = datetime.strptime(due_match.group(1), '%Y-%m-%d')
        # 从文本中移除日期 emoji
        text = re.sub(r'📅\s*\d{4}-\d{2}-\d{2}', '', text).strip()
    
    # 提取 done date: ✅ YYYY-MM-DD
    done_match = re.search(r'✅\s*(\d{4}-\d{2}-\d{2})', text)
    if done_match:
        done_date = datetime.strptime(done_match.group(1), '%Y-%m-%d')
        text = re.sub(r'✅\s*\d{4}-\d{2}-\d{2}', '', text).strip()
    
    # 提取 start date: ⏳ YYYY-MM-DD
    start_match = re.search(r'⏳\s*(\d{4}-\d{2}-\d{2})', text)
    if start_match:
        start_date = datetime.strptime(start_match.group(1), '%Y-%m-%d')
        text = re.sub(r'⏳\s*\d{4}-\d{2}-\d{2}', '', text).strip()
    
    return {
        'done': done,
        'text': text,
        'due_date': due_date,
        'done_date': done_date,
        'start_date': start_date
    }

def scan_vault_for_tasks(vault_path):
    """扫描任务文件"""
    tasks = []
    
    vault = Path(vault_path)
    
    # 忽略的目录
    ignore_dirs = {'.git', '.obsidian', '.iflow', 'appendix', 'textbook', 'claude-obsidian-skills'}
    
    # 扫描整个 vault（因为 Tasks 查询会从多个文件中收集任务）
    if SCAN_FULL_VAULT:
        print(f"📂 扫描整个 vault...")
        for md_file in vault.rglob('*.md'):
            # 跳过忽略的目录
            if any(part in md_file.parts for part in ignore_dirs):
                continue
            
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    task = parse_task_line(line)
                    if task:
                        task['source_file'] = str(md_file.relative_to(vault_path))
                        task['line_number'] = line_num
                        tasks.append(task)
            except Exception as e:
                print(f"❌ 读取错误 {md_file}: {e}")
    else:
        # 只扫描指定的文件
        for task_file in TASK_FILES:
            md_file = vault / task_file
            
            if not md_file.exists():
                print(f"⚠️  文件不存在: {task_file}")
                continue
            
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    task = parse_task_line(line)
                    if task:
                        task['source_file'] = task_file
                        task['line_number'] = line_num
                        tasks.append(task)
                        
                print(f"✅ 已扫描: {task_file} ({len([t for t in tasks if t['source_file'] == task_file])} 个任务)")
            except Exception as e:
                print(f"❌ 读取错误 {task_file}: {e}")
    
    return tasks

def generate_ics(tasks, output_path):
    """生成 iCalendar 文件"""
    
    def escape_ics_text(text):
        """转义 iCalendar 特殊字符"""
        text = text.replace('\\', '\\\\')
        text = text.replace(';', '\\;')
        text = text.replace(',', '\\,')
        text = text.replace('\n', '\\n')
        return text
    
    def format_datetime(dt):
        """格式化日期时间为 iCalendar 格式"""
        return dt.strftime('%Y%m%d')
    
    # 生成当前 UTC 时间戳
    dtstamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    
    ics_content = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Obsidian Tasks Export//iFlow CLI//CN',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:Obsidian Tasks',
        'X-WR-TIMEZONE:Asia/Shanghai',
        'X-WR-CALDESC:从 Obsidian 导出的待办事项（仅未完成）',
    ]
    
    uid_counter = 1
    exported_count = 0
    
    for task in tasks:
        # 只导出未完成的任务
        if task['done']:
            continue
        
        # 只导出有截止日期的任务
        if not task['due_date']:
            continue
        
        exported_count += 1
        
        # 创建日历事件
        uid = f"task-{uid_counter}@obsidian-tasks"
        uid_counter += 1
        
        # 任务开始时间（如果有）
        dtstart = task['start_date'] if task['start_date'] else task['due_date'] - timedelta(days=1)
        
        # 任务结束时间（截止日期当天结束）
        dtend = task['due_date'] + timedelta(days=1)
        
        # 清理任务文本中的特殊字符
        clean_text = task['text']
        # 移除 wikilinks [[...]]
        clean_text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', clean_text)
        # 移除 emoji
        emojis_to_remove = ['🔽', '🔁', '⏫', '🔼', '➕', '⏳', '✅', '📅']
        for emoji in emojis_to_remove:
            clean_text = clean_text.replace(emoji, '')
        # 移除多余空格
        clean_text = re.sub(r'  +', ' ', clean_text).strip()
        
        # 添加事件
        # VEVENT 的 STATUS 合法值: TENTATIVE, CONFIRMED, CANCELLED
        description = f"来源: {task['source_file']}:{task['line_number']}"
        ics_content.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}',
            f'DTSTAMP:{dtstamp}',  # RFC 5545 必需字段
            f'DTSTART;VALUE=DATE:{format_datetime(dtstart)}',
            f'DTEND;VALUE=DATE:{format_datetime(dtend)}',
            f'SUMMARY:{escape_ics_text(clean_text)}',
            f'DESCRIPTION:{escape_ics_text(description)}',
            'STATUS:CONFIRMED',  # VEVENT 合法状态值
            'TRANSP:TRANSPARENT',
            'END:VEVENT'
        ])
    
    ics_content.append('END:VCALENDAR')
    
    # 写入文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\r\n'.join(ics_content))
    
    print(f"✅ 已导出 {exported_count} 个未完成任务到 {output_path}")
    
    # 创建符号链接到 iCloud
    try:
        if os.path.exists(ICS_ICLOUD_LINK):
            os.remove(ICS_ICLOUD_LINK)
        os.symlink(output_path, ICS_ICLOUD_LINK)
        print(f"🔗 已创建符号链接: {ICS_ICLOUD_LINK}")
    except Exception as e:
        print(f"⚠️  无法创建符号链接: {e}")

def main():
    parser = argparse.ArgumentParser(description='导出 Obsidian Tasks 到 iCalendar')
    parser.add_argument('--vault', default=VAULT_PATH, help='Obsidian vault 路径')
    parser.add_argument('--output', default=ICS_OUTPUT_PATH, help='输出 .ics 文件路径')
    
    args = parser.parse_args()
    
    print(f"📂 扫描 vault: {args.vault}")
    tasks = scan_vault_for_tasks(args.vault)
    
    # 统计任务
    total_tasks = len(tasks)
    incomplete_tasks = len([t for t in tasks if not t['done']])
    incomplete_with_due = len([t for t in tasks if not t['done'] and t['due_date']])
    
    print(f"📋 总任务数: {total_tasks}")
    print(f"📋 未完成任务: {incomplete_tasks}")
    print(f"📋 未完成且有截止日期: {incomplete_with_due}")
    
    generate_ics(tasks, args.output)

if __name__ == '__main__':
    main()
