import os
import shutil
import dateparser
import re
from pathlib import Path
import argparse
from tqdm import tqdm
from datetime import datetime

# 日期解析缓存
DATE_CACHE = {}

# 常见的日期正则模式
DATE_PATTERNS = [
    r'(\d{4}[.\-_]\d{1,2}[.\-_]\d{1,2})', # 2023-07-15, 2023.7.15
    r'(\d{1,2}[.\-_]\d{1,2}[.\-_]\d{2,4})', # 15-07-2023, 23.07.15
    r'(\d{8})',                           # 20230715
    r'(\d{4}年\d{1,2}月\d{1,2}日)',       # 2023年7月15日
]

def extract_date_from_text(text):
    """从文本中提取并解析日期，返回 (格式化日期, 原始匹配文本)"""
    if text in DATE_CACHE:
        return DATE_CACHE[text]
    
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            # 针对 8 位纯数字特殊处理
            if date_str.isdigit() and len(date_str) == 8:
                dt = dateparser.parse(date_str, date_formats=['%Y%m%d'])
            else:
                dt = dateparser.parse(date_str, settings={'DATE_ORDER': 'YMD', 'PREFER_DAY_OF_MONTH': 'first'})
            
            if dt and 1900 <= dt.year <= 2100:
                res = dt.strftime('%Y-%m-%d')
                DATE_CACHE[text] = (res, date_str)
                return res, date_str
    
    DATE_CACHE[text] = (None, None)
    return None, None

def clean_segment(segment, main_date=None):
    """移除片段开头的日期，并智能筛除片段中与主日期相同的冗余日期"""
    if not segment:
        return ""
    
    # 1. 首先尝试移除片段开头的任何有效日期
    for pattern in DATE_PATTERNS:
        match = re.match(pattern, segment)
        if match:
            date_str = match.group(1)
            if date_str.isdigit() and len(date_str) == 8:
                dt = dateparser.parse(date_str, date_formats=['%Y%m%d'])
            else:
                dt = dateparser.parse(date_str, settings={'DATE_ORDER': 'YMD', 'PREFER_DAY_OF_MONTH': 'first'})
            
            if dt and 1900 <= dt.year <= 2100:
                segment = segment[match.end():]
                break

    # 2. 如果提供了主日期，则移除片段中所有解析后等于主日期的子串
    if main_date:
        for pattern in DATE_PATTERNS:
            matches = list(re.finditer(pattern, segment))
            for m in reversed(matches):
                d_str = m.group(1)
                if d_str.isdigit() and len(d_str) == 8:
                    dt = dateparser.parse(d_str, date_formats=['%Y%m%d'])
                else:
                    dt = dateparser.parse(d_str, settings={'DATE_ORDER': 'YMD', 'PREFER_DAY_OF_MONTH': 'first'})
                
                if dt and dt.strftime('%Y-%m-%d') == main_date:
                    segment = segment[:m.start()] + segment[m.end():]
    
    # 压缩连续的空格和分隔符
    segment = re.sub(r'[ .\-_]{2,}', ' ', segment)
    return segment.strip(' .-_')

def extract_date_from_segments(segments):
    """从路径片段中提取第一个识别到的日期（倒序优先）"""
    for segment in reversed(segments):
        date_res, _ = extract_date_from_text(segment)
        if date_res:
            return date_res
    return None

def generate_preview(source_dir, target_dir):
    """生成重命名预览映射"""
    preview_data = []
    source_path = Path(source_dir)
    target_path = Path(target_dir)
    used_names = set()

    # 第一步：快速预统计
    print("正在扫描目录...")
    all_files = []
    # 忽略的文件名
    ignored_files = {'.ds_store', 'thumbs.db', 'desktop.ini'}
    
    for root, dirs, files in os.walk(source_dir):
        # 严格排除“合并”文件夹本身及其内容
        if os.path.abspath(root).startswith(os.path.abspath(target_dir)):
            continue
        for file in files:
            if file.lower() in ignored_files:
                continue
            all_files.append((root, file))
    
    if not all_files:
        return []

    print(f"共发现 {len(all_files)} 个待处理文件，开始分析命名规则...")

    # 第二步：正式解析
    with tqdm(total=len(all_files), desc="分析日期与路径", unit="个") as pbar:
        for root, file in all_files:
            file_path = Path(root) / file
            try:
                relative_path = file_path.relative_to(source_path)
                # 获取所有路径片段（文件夹名 + 文件名）
                segments = list(relative_path.parts)
                
                # 提取主日期（从末端开始找最相关的日期）
                main_date = extract_date_from_segments(segments)
                
                final_parts = []
                accepted_tokens = []
                if main_date:
                    final_parts.append(main_date)
                    accepted_tokens.append(main_date)
                
                def is_token_redundant(token, accepted):
                    if not token: 
                        return True
                    
                    token_lower = token.lower()
                    
                    # 1. 完全一致则冗余 (忽略大小写)
                    for acc in accepted:
                        if token_lower == acc.lower():
                            return True
                            
                    # 2. 对于较长的文字块（包含字母或汉字/假名等），进行宽容的相互包含去重
                    if len(token) >= 2 and re.search(r'[^\W\d_]', token):
                        for acc in accepted:
                            acc_lower = acc.lower()
                            # 只要文字块相互包含，即视为冗余（剔除重复或被包含的子文字块）
                            if token_lower in acc_lower or (len(acc) >= 2 and acc_lower in token_lower):
                                return True
                                
                    return False

                # 处理每个片段，进行清理
                for i, segment in enumerate(segments):
                    # 如果是最后一个片段（文件名），去掉后缀再清理
                    is_file = (i == len(segments) - 1)
                    seg_to_clean = Path(segment).stem if is_file else segment
                    
                    cleaned = clean_segment(seg_to_clean, main_date=main_date)
                    
                    # 如果清理后不为空，则加入命名
                    if cleaned:
                        # 额外检查：如果清理后的内容和主日期完全一致且不是唯一内容，则跳过以防重复
                        if main_date and cleaned == main_date and (not is_file or len(segments) > 1):
                            continue
                        
                        # 用带捕获组的正则切分，保留原始分隔符 (空格, _, -)
                        parts = re.split(r'([\s_\-]+)', cleaned)
                        kept_parts = []
                        last_sep = ""
                        
                        for idx, part in enumerate(parts):
                            # 偶数索引为有效词元，奇数索引为分隔符
                            if idx % 2 == 0:
                                token = part
                                if not token:
                                    continue
                                
                                if not is_token_redundant(token, accepted_tokens):
                                    accepted_tokens.append(token)
                                    if kept_parts:
                                        kept_parts.append(last_sep if last_sep else " ")
                                    kept_parts.append(token)
                            else:
                                last_sep = part
                        
                        if kept_parts:
                            final_parts.append("".join(kept_parts))

                # 过滤连续重复的片段（兜底）
                unique_parts = []
                for p in final_parts:
                    if not unique_parts or p != unique_parts[-1]:
                        unique_parts.append(p)
                
                final_stem = "_".join(unique_parts)
                suffix = file_path.suffix
                new_name = final_stem + suffix
                
                # 处理同名冲突
                counter = 1
                while new_name in used_names or (target_path / new_name).exists():
                    new_name = f"{final_stem}_{counter}{suffix}"
                    counter += 1
                
                used_names.add(new_name)
                preview_data.append((str(file_path), new_name))
            except Exception:
                pass # 静默跳过错误文件
            
            pbar.update(1)
                
    return preview_data

def execute_move(preview_data, target_dir):
    """执行文件移动"""
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    
    with tqdm(total=len(preview_data), desc="正在移动文件至'合并'目录", unit="个") as pbar:
        for old_path_str, new_name in preview_data:
            old_path = Path(old_path_str)
            dest_path = target_path / new_name
            
            # 最终去重校验
            counter = 1
            stem = dest_path.stem
            suffix = dest_path.suffix
            while dest_path.exists():
                dest_path = target_path / f"{stem}_{counter}{suffix}"
                counter += 1
                
            try:
                shutil.move(str(old_path), str(dest_path))
            except Exception:
                pass
            
            pbar.update(1)

def main():
    parser = argparse.ArgumentParser(description="万能文件智能重命名与提取工具")
    parser.add_argument("source", nargs='?', help="源目录")
    parser.add_argument("--run", action="store_true", help="直接执行")
    
    args = parser.parse_args()

    # 交互式获取路径
    source_input = args.source
    if not source_input:
        print("\n=== 万能文件智能重命名与提取工具 ===")
        print("提示: 请输入或拖入文件夹路径。")
        source_input = input("请输入源文件夹路径: ").strip().strip('"').strip("'")
    
    source_dir = os.path.abspath(source_input)
    # 自动设置目标目录为源目录下的“合并”文件夹
    target_dir = os.path.join(source_dir, "合并")
    
    if not os.path.exists(source_dir):
        print(f"\n[错误] 路径不存在: {source_dir}")
        input("按回车键退出...")
        return

    print(f"\n[1/2] 扫描分析中...")
    preview_data = generate_preview(source_dir, target_dir)
    
    if not preview_data:
        print("\n未扫描到可处理的文件。")
        input("按回车键退出...")
        return

    # 写入预览文件
    preview_file = "preview_list.txt"
    try:
        with open(preview_file, "w", encoding="utf-8") as f:
            f.write(f"待处理总数: {len(preview_data)}\n")
            f.write(f"目标目录: {target_dir}\n")
            f.write("=" * 60 + "\n\n")
            for old, new in preview_data:
                f.write(f"{old}\n  >>> {new}\n\n")
        print(f"\n[2/2] 预览列表已生成: {preview_file}")
        print(f"      共计分析了 {len(preview_data)} 个文件。")
    except Exception as e:
        print(f"生成预览失败: {e}")
    
    # 确认执行
    if not args.run:
        print("\n[待命] 请检查 'preview_list.txt' 确认命名方案。")
        confirm = input("\n确认并开始【移动】文件吗？(输入 y 开始 / 其它键退出): ").strip().lower()
        if confirm != 'y':
            print("操作已取消。")
            return

    print("\n正在移动并整理文件...")
    execute_move(preview_data, target_dir)
    print(f"\n[完成] 所有文件已移至: {target_dir}")
    input("\n整理完毕，按回车键退出...")

if __name__ == "__main__":
    main()
