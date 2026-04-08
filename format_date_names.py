import os
import re
import sys
from pathlib import Path

def format_name(name):
    r"""
    匹配原理：识别 20xx-xx 后面跟着“空格-xx”的情况（无论出现在名称的哪个位置）。
    正则说明：(\d{4}-\d{2})\s+-(\d{2})
    示例 1: '2021-01 -04 クロエ.png' -> '2021-01-04 クロエ.png'
    示例 2: 'クロエ (PSD) 2021-01 -04.png' -> 'クロエ (PSD) 2021-01-04.png'
    """
    pattern = r'(\d{4}-\d{2})\s+-(\d{2})'
    if re.search(pattern, name):
        # 使用 re.sub 替换所有匹配项 (以防一个名字里有多个日期)
        return re.sub(pattern, r'\1-\2', name)
    return None

def scan_and_preview(root_dir):
    changes = []
    root_path = Path(root_dir).resolve()
    
    # 使用 topdown=False (自下而上) 遍历，确保先重命名子文件/文件夹，再重命名父文件夹
    for root, dirs, files in os.walk(root_path, topdown=False):
        # 记录需要更改的文件夹
        for d in dirs:
            new_name = format_name(d)
            if new_name:
                old_full_path = os.path.join(root, d)
                new_full_path = os.path.join(root, new_name)
                changes.append(('DIR', old_full_path, new_full_path))
        
        # 记录需要更改的文件
        for f in files:
            new_name = format_name(f)
            if new_name:
                old_full_path = os.path.join(root, f)
                new_full_path = os.path.join(root, new_name)
                changes.append(('FILE', old_full_path, new_full_path))
    
    return changes

def main():
    if len(sys.argv) < 2:
        target_dir = input("请输入要检索的目录路径 (或拖入文件夹): ").strip().strip('"')
    else:
        target_dir = sys.argv[1].strip().strip('"')

    if not os.path.isdir(target_dir):
        print(f"错误: 目录 '{target_dir}' 不存在。")
        return

    print(f"正在扫描目录: {target_dir} ...")
    changes = scan_and_preview(target_dir)

    if not changes:
        print("未发现需要格式化的名称。")
        return

    # 写入预览文件
    preview_file = "re_preview_list.txt"
    try:
        with open(preview_file, "w", encoding="utf-8") as f:
            f.write(f"待处理任务总数: {len(changes)}\n")
            f.write("-" * 60 + "\n")
            for type_label, old, new in changes:
                f.write(f"类型: {type_label}\n")
                f.write(f"原路径: {old}\n")
                f.write(f"新路径: {new}\n")
                f.write("-" * 60 + "\n")
    except Exception as e:
        print(f"写入预览文件失败: {e}")
        return

    print(f"\n预览文件已生成: {os.path.abspath(preview_file)}")
    print(f"共发现 {len(changes)} 个需要修改的项目。")
    print("请打开预览文件检查。如果确认无误，请在此处输入 'yes' 开始执行重命名:")
    
    confirm = input("> ").strip().lower()
    if confirm == 'yes':
        print("\n开始执行重命名...")
        count = 0
        for _, old, new in changes:
            try:
                # 再次检查原路径是否存在 (防止在重命名过程中因父目录变动导致失效，虽然 topdown=False 已规避)
                if os.path.exists(old):
                    os.rename(old, new)
                    count += 1
                else:
                    print(f"路径已失效 (跳过): {old}")
            except Exception as e:
                print(f"重命名失败: {old} -> {new} | 错误: {e}")
        
        print(f"\n处理完成！成功重命名了 {count} 个项目。")
    else:
        print("\n操作已取消。")

if __name__ == "__main__":
    main()
